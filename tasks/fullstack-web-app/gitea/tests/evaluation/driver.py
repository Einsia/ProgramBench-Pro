"""Generic episode worker: one episode, one fresh runtime instance, task hooks.

run.py starts one worker per episode, one at a time, through the task's thin
worker.py (`main(Hooks())`). The driver owns what must be uniform across
tasks: the per-episode workspace (a fresh copy of the solution and a fresh
instance directory), the task's black-box runtime driving that copy, setup
scope, dependency gating, companion points, exception
classification, crash recovery, the wall-clock limit, record and
compare, and the output files. Hooks supply only product specifics.

Exceptions in task hooks:
- AssertionError in check() or judge(): the point fails (result_mismatch);
- any other exception in check()/judge(): the point fails (program_exception,
  traceback kept as evidence);
- any exception in setup()/prepare()/restarted(): that setup item or checkpoint
  preparation failed; only declared dependents are blocked;
- InfrastructureError, ProviderUnavailable: verifier fault, the run is invalid;
- CandidateTimeout: raised by the driver itself at the wall-clock limit.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import time
import traceback

from . import task
from .agent import Agent
from .bridge import SpoolClient
from .broker import BrokerError, BrokerRuntime, BrokerSurface
from .contract import (CandidateTimeout, Evidence, InfrastructureError, ObservationUnavailable, apply_companions,
                       assertions, gate, read_frozen_evidence, result, write)
from .model_client import Budget, BudgetExceeded, ProviderUnavailable

CANDIDATE_USER = 'agent'
VERIFIER_FAULTS = (InfrastructureError, ProviderUnavailable)


class Hooks:
    """Task-specific episode steps. Override what the task's episodes need."""

    def start(self, ctx):
        """Per-episode task resources (for example a verifier-owned decoding page)."""

    def inputs(self, ctx):
        """Write the goal's input files into ctx.inputs (offered to the evaluator and to recipes)."""

    def setup(self, ctx, item):
        """Apply one unscored episode setup item through runtime channels; raise to mark it failed."""
        raise NotImplementedError('setup item without a task hook: ' + item['id'])

    def prepare(self, ctx, checkpoint):
        """Unscored per-checkpoint preparation; an exception blocks only this checkpoint."""

    def begin(self, ctx, checkpoint):
        """Before a GUI checkpoint is operated (for example capture the saved state)."""

    def recipe(self, ctx, checkpoint):
        """Record mode: drive the standard answer through runtime GUI operations."""
        raise NotImplementedError('GUI checkpoint without a reference recipe')

    def collect(self, ctx, checkpoint):
        """After operations and evidence, before program checks (downloads, settled state)."""

    def check(self, ctx, checkpoint, assertion):
        """One backend assertion: return its observation; AssertionError means mismatch."""
        raise NotImplementedError('backend assertion without a task check')

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        """Compare an observation with the frozen one; raise AssertionError on mismatch."""
        assert actual == expected, f'observation differs from the reference: {actual!r}'

    def after(self, ctx, checkpoint):
        """After the checkpoint's program checks."""

    def restarted(self, ctx):
        """After the driver restarted a crashed product (same instance data)."""

    def close(self, ctx):
        """Release per-episode task resources."""


class Context:
    """What hooks receive for one episode."""

    def __init__(self, episode, mode, out, evidence, runtime, inputs):
        self.episode, self.mode, self.out, self.evidence, self.runtime = episode, mode, out, evidence, runtime
        self.broker = runtime.client
        self.inputs = inputs
        self.surface = None
        self.state = {}
        self.events = []

    @property
    def record(self):
        return self.mode == 'record'

    @property
    def gui(self):
        return self.episode['execution'] != 'program'

    def pump(self, seconds):
        time.sleep(seconds)

    def status(self):
        return self.broker.call({'op': 'status'})

    def restart(self):
        """Restart the product with the same instance data; returns the runtime status."""
        return self.broker.call({'op': 'restart'})

    def note(self, kind, **fields):
        self.events.append({'kind': kind, 'time': round(time.time(), 3), **fields})


def candidate_account(user=CANDIDATE_USER):
    return pwd.getpwnam(user)


def _entries(path):
    try:
        return {entry.name for entry in Path(path).iterdir()}
    except OSError:
        return set()


try:
    _HOME = Path(candidate_account().pw_dir)
except KeyError:
    _HOME = None
# What the image ships in the candidate account's home, taken before any episode runs. The runtime gives every
# instance a private HOME, so anything a candidate adds to the account's home came through an absolute path and would
# otherwise reach the next episode; kill_candidate removes it.
HOME_BASELINE = _entries(_HOME) if _HOME else set()


def candidate_processes(uid):
    pids = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            for line in (entry / 'status').read_text().splitlines():
                if line.startswith('Uid:'):
                    if int(line.split()[1]) == uid:
                        pids.append(int(entry.name))
                    break
        except (OSError, ValueError):
            pass
    return pids


def kill_candidate(user=CANDIDATE_USER):
    """Every process of the candidate user (serial execution: nothing else runs as that user), then the files it
    left in shared temporary directories and the files it added to its account's home."""
    account = candidate_account(user)
    for _ in range(10):
        pids = candidate_processes(account.pw_uid)
        if not pids:
            break
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        time.sleep(.2)
    for root in (Path('/tmp'), Path('/var/tmp'), Path('/dev/shm')) + ((_HOME,) if _HOME and not _HOME.is_symlink() else ()):
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if root == _HOME and entry.name in HOME_BASELINE:
                continue
            try:
                if entry.lstat().st_uid != account.pw_uid:
                    continue
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink()
            except OSError:
                pass


def prepare_workspace(root, solution, user=CANDIDATE_USER):
    """root/solution = a fresh copy of the solution (candidate-owned); root/instance = product state root (the
    runtime creates it); root/runtime = the runtime's private directory (root only)."""
    account = candidate_account(user)
    root.mkdir(parents=True, exist_ok=False)
    root.chmod(0o711)
    copy = root / 'solution'
    if solution.is_dir():
        done = subprocess.run(['cp', '-a', '--', str(solution), str(copy)], capture_output=True, text=True)
        if done.returncode != 0:
            raise InfrastructureError('could not copy the solution: ' + done.stderr[-300:])
        subprocess.run(['chown', '-hR', f'{account.pw_uid}:{account.pw_gid}', str(copy)], check=True)
    else:
        copy.mkdir()
    copy.chmod(0o755)
    (root / 'runtime').mkdir(mode=0o700)
    return copy, root / 'instance'


def describe(exc):
    return f'{type(exc).__name__}: {exc}'[:1500]


def run(args, hooks):
    import suite
    record_mode = args.mode == 'record'
    if record_mode:
        manifest, oracle = suite.build(), None
    else:
        manifest, oracle, _meta = suite.load(args.truth)
    episode = next(w for w in manifest['episodes'] if w['id'] == args.episode)
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    evidence = Evidence(out / 'evidence', episode['id'])
    rows, record = {}, {'program': {}, 'frontend': {}}
    setup_ok = {}
    stats = {'setup_calls': 0, 'program_calls': 0, 'setup_seconds': 0., 'model_calls': 0, 'tokens': 0, 'gui_actions': 0,
             'model_seconds': 0., 'model_wait_seconds': 0., 'reference_gui_events': 0, 'candidate_restarts': 0}
    order = [a['id'] for a in assertions(episode)]
    by_cp = {cp['id']: cp for cp in episode['checkpoints']}
    runtime = ctx = agent = client = None
    current = {'checkpoint': None}
    cause = None
    started = time.monotonic()

    def on_term(signum, frame):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        raise CandidateTimeout('the episode reached its wall-clock limit')
    signal.signal(signal.SIGTERM, on_term)

    def save_progress():
        write(out / 'rows-progress.json', [rows[i] for i in order if i in rows])

    def add(a, cp, status, reason='', evidence_ids=(), kind=None):
        rows[a['id']] = result(a, episode, cp, status, reason, evidence_ids, failure_kind=kind)

    def block(cp, reason, kind):
        for a in cp['assertions']:
            if a['id'] not in rows:
                add(a, cp, 'blocked', reason, kind=kind)

    def program_failure(cp, a, exc):
        if isinstance(exc, AssertionError):
            add(a, cp, 'fail', describe(exc), kind='result_mismatch')
        else:
            trace = evidence.text(cp['id'], 'program-exception', traceback.format_exc())
            add(a, cp, 'fail', describe(exc), [trace], kind='program_exception')

    def counted(key, function, *call_args):
        before = runtime.client.calls
        try:
            return function(*call_args)
        finally:
            stats[key] += runtime.client.calls - before

    def recover(cp):
        """Restart a crashed product so later checkpoints are judged on their own."""
        try:
            status = ctx.status()
        except BrokerError:
            return
        if status.get('running'):
            return
        t = time.monotonic()
        try:
            status = counted('setup_calls', ctx.restart)
            stats['candidate_restarts'] += 1
            ctx.note('candidate_restart', after=cp['id'], ready=status.get('ready'), detail=status.get('detail'))
            if ctx.gui and status.get('ready'):
                counted('setup_calls', ctx.broker.call, {**task.START, **getattr(task, 'SESSION', {})})
            hooks.restarted(ctx)
        except VERIFIER_FAULTS:
            raise
        except Exception as exc:
            ctx.note('candidate_restart_failed', after=cp['id'], reason=describe(exc))
        finally:
            stats['setup_seconds'] += time.monotonic() - t

    def apply_setup(item):
        """One unscored setup item; a failure blocks only the checkpoints that declare setup:<id>."""
        t = time.monotonic()
        try:
            counted('setup_calls', hooks.setup, ctx, item)
            setup_ok[item['id']] = True
        except VERIFIER_FAULTS:
            raise
        except Exception as exc:
            setup_ok[item['id']] = False
            ctx.note('setup_failed', setup=item['id'], reason=describe(exc), traceback=traceback.format_exc())
        finally:
            stats['setup_seconds'] += time.monotonic() - t

    def run_checkpoint(cp):
        current['checkpoint'] = cp['id']
        failed = [d for d in cp.get('depends_on', []) if not gate(d, episode, rows, setup_ok)]
        if failed:
            setup_only = all(d.startswith('setup:') for d in failed)
            block(cp, 'Required ' + ('setup' if setup_only else 'earlier point') + ' did not pass: ' + ', '.join(failed),
                  'setup_failure' if setup_only else 'dependency')
            return
        frontend = [a for a in cp['assertions'] if a['channel'] == 'frontend']
        backend = [a for a in cp['assertions'] if a['channel'] == 'backend']
        t = time.monotonic()
        try:
            if cp.get('lifecycle') == 'restart':
                status = counted('setup_calls', ctx.restart)
                if not status.get('ready'):
                    raise AssertionError('the application did not come back after a restart: ' + str(status.get('detail')))
            counted('setup_calls', hooks.prepare, ctx, cp)
        except VERIFIER_FAULTS:
            raise
        except Exception as exc:
            block(cp, 'Checkpoint preparation failed: ' + describe(exc), 'setup_failure')
            stats['setup_seconds'] += time.monotonic() - t
            recover(cp)
            return
        stats['setup_seconds'] += time.monotonic() - t
        if ctx.gui and frontend:
            try:
                counted('setup_calls', hooks.begin, ctx, cp)
            except VERIFIER_FAULTS:
                raise
            except Exception as exc:
                ctx.note('begin_failed', checkpoint=cp['id'], reason=describe(exc))
            if record_mode:
                before = evidence.add(cp['id'], 'reference-before', *ctx.surface.observe())
                error = None
                calls = runtime.client.calls
                try:
                    hooks.recipe(ctx, cp)
                except VERIFIER_FAULTS:
                    raise
                except Exception as exc:
                    error = (exc, evidence.text(cp['id'], 'recipe-exception', traceback.format_exc()))
                stats['reference_gui_events'] += runtime.client.calls - calls
                after = evidence.add(cp['id'], 'reference-after', *ctx.surface.observe())
                record['frontend'][cp['id']] = {'before': evidence.items[before], 'after': evidence.items[after]}
                for a in frontend:
                    if error:
                        add(a, cp, 'fail', 'Reference recipe failed: ' + describe(error[0]), [error[1]], 'program_exception')
                    else:
                        add(a, cp, 'pass', 'Reference recipe completed; its program checks follow.', [before, after])
            else:
                pair = oracle['frontend'][episode['id'] + '/' + cp['id']]

                def frozen(role):
                    return read_frozen_evidence(args.truth, pair[role])
                try:
                    reports, _ = agent.checkpoint(cp, {'before': frozen('before'), 'after': frozen('after')})
                    by_id = {r['id']: r for r in reports}
                    for a in frontend:
                        report = by_id[a['id']]
                        add(a, cp, report['status'], report['reason'], report['evidence'], 'agent_verdict')
                except BudgetExceeded as exc:
                    for a in frontend:
                        add(a, cp, 'unresolved', describe(exc), kind='budget')
                except ObservationUnavailable as exc:
                    for a in frontend:
                        add(a, cp, 'unresolved', describe(exc), kind='observation')
                except ValueError as exc:
                    for a in frontend:
                        add(a, cp, 'unresolved', describe(exc), kind='report_protocol')
            try:
                counted('program_calls', hooks.collect, ctx, cp)
            except VERIFIER_FAULTS:
                raise
            except Exception as exc:
                ctx.note('collect_failed', checkpoint=cp['id'], reason=describe(exc))
        for a in backend:
            calls = runtime.client.calls
            try:
                observation = hooks.check(ctx, cp, a)
                eid = evidence.add(cp['id'], 'program-actual', observation)
                if record_mode:
                    record['program'][a['id']] = observation
                else:
                    hooks.judge(ctx, cp, a, observation, oracle['program'][a['id']])
                add(a, cp, 'pass', evidence_ids=[eid])
            except VERIFIER_FAULTS:
                raise
            except Exception as exc:
                program_failure(cp, a, exc)
            finally:
                stats['program_calls'] += runtime.client.calls - calls
        try:
            counted('program_calls', hooks.after, ctx, cp)
        except VERIFIER_FAULTS:
            raise
        except Exception as exc:
            ctx.note('after_failed', checkpoint=cp['id'], reason=describe(exc))
        apply_companions(episode, rows)
        recover(cp)

    try:
        solution, instance = prepare_workspace(args.state, Path(args.start).parent)
        runtime = BrokerRuntime(task, args.state, args.state / 'runtime' / 'logs', solution=solution, instance=instance,
                                user=CANDIDATE_USER)
        status = runtime.start(task.READY_SECONDS + 60)
        inputs = out / 'inputs'
        inputs.mkdir()
        ctx = Context(episode, args.mode, out, evidence, runtime, inputs)
        hooks.start(ctx)
        if not status.get('ready'):
            cause = ('blocked', 'The application did not start: ' + str(status.get('detail')), 'candidate_start')
        else:
            hooks.inputs(ctx)
            for item in episode.get('setup', []):
                if not item.get('before'):
                    apply_setup(item)
            if ctx.gui:
                try:
                    counted('setup_calls', runtime.client.call, {**task.START, **getattr(task, 'SESSION', {})})
                except BrokerError as exc:
                    ctx.note('start_page_failed', reason=describe(exc))
                ctx.surface = BrokerSurface(runtime.client, task, out, inputs=inputs)
                if not record_mode:
                    budget = episode['budget']
                    client = SpoolClient(args.spool, Budget(budget['calls'], budget['tokens']), episode=episode['id'],
                                         monitor=out / 'model-wait.json')
                    agent = Agent(client, ctx.surface, evidence, episode, out)
            for cp in episode['checkpoints']:
                for item in episode.get('setup', []):
                    if item.get('before') == cp['id']:
                        apply_setup(item)
                run_checkpoint(cp)
                current['checkpoint'] = None
                save_progress()
                print(json.dumps({'episode': episode['id'], 'checkpoint': cp['id'],
                                  'passed': sum(r['passed'] for r in rows.values()), 'points': len(rows)}), flush=True)
    except CandidateTimeout as exc:
        cause = ('blocked', str(exc), 'candidate_timeout')
        if current['checkpoint']:
            for a in by_cp[current['checkpoint']]['assertions']:
                if a['id'] not in rows:
                    add(a, by_cp[current['checkpoint']], 'fail', str(exc), kind='candidate_timeout')
    except VERIFIER_FAULTS as exc:
        write(out / 'infrastructure-error.json', {'type': type(exc).__name__, 'reason': str(exc),
                                                  'traceback': traceback.format_exc()})
        cause = ('blocked', 'Verifier fault: ' + str(exc), 'infrastructure')
    except Exception as exc:
        write(out / 'worker-error.json', {'type': type(exc).__name__, 'reason': str(exc), 'traceback': traceback.format_exc()})
        cause = ('blocked', 'Verifier fault: ' + str(exc), 'infrastructure')
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        def collect_logs():
            source = args.state / 'runtime' / 'logs'
            if source.is_dir():
                shutil.copytree(source, out / 'runtime', dirs_exist_ok=True)

        for step in (lambda: ctx and hooks.close(ctx), lambda: runtime and runtime.stop(), kill_candidate, collect_logs,
                     lambda: shutil.rmtree(args.state, ignore_errors=True)):
            try:
                step()
            except BaseException:
                pass
        if agent is not None:
            stats.update(model_calls=client.budget.calls, tokens=client.budget.tokens, gui_actions=agent.actions,
                         model_seconds=round(agent.seconds, 3), model_wait_seconds=round(client.wait_total, 3))
    status_kind, reason, kind = cause or ('blocked', 'Episode stopped before this point.', 'infrastructure')
    for cp in episode['checkpoints']:
        for a in cp['assertions']:
            if a['id'] not in rows:
                add(a, cp, status_kind, reason, kind=kind)
    apply_companions(episode, rows)
    ordered = [rows[i] for i in order]
    (out / 'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ordered))
    write(out / 'record.json', record)
    write(out / 'events.json', ctx.events if ctx else [])
    write(out / 'setup.json', setup_ok)
    stats['elapsed_seconds'] = round(time.monotonic() - started, 3)
    write(out / 'usage.json', stats)
    write(out / 'status.json', {'passed': all(r['passed'] for r in ordered),
                                'infrastructure_error': (out / 'infrastructure-error.json').exists()
                                or (out / 'worker-error.json').exists(),
                                'candidate_timeout': bool(cause and cause[2] == 'candidate_timeout'),
                                'source_episode': episode['id']})


def main(hooks):
    ap = argparse.ArgumentParser(description='Run one episode in a fresh runtime instance.')
    ap.add_argument('--episode', required=True)
    ap.add_argument('--mode', choices=['record', 'compare'], required=True)
    ap.add_argument('--start', default='/app/solution/start.sh')
    ap.add_argument('--state', type=Path, required=True, help='fresh per-episode workspace directory')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--truth', type=Path, default=Path('/tests/data'))
    ap.add_argument('--spool', type=Path, default=Path('/model'))
    try:
        argv = sys.argv[1:]
        if argv == ['--request-stdin']:
            argv = json.load(sys.stdin)
            if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
                raise ValueError('worker request must be a list of arguments')
        run(ap.parse_args(argv), hooks)
    except CandidateTimeout:
        pass
    return 0
