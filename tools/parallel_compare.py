#!/usr/bin/env python3
"""Compare an immutable candidate in independent serial verifier containers.

Works with every tasks/<category>/<task> verifier. No Docker socket, model
credential or sibling state is exposed inside a verifier. Full and selected
episode runs use the same execution path; only complete full runs get reward.
Record remains the existing serial test.sh --mode record entry point.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import tomllib
import uuid

from parallel_support import (FORMAT, check_lane_identity, check_resume, completed,
                              digest, fingerprints, parent_finished, partition, read, validate_rows, write)

HERE = Path(__file__).resolve().parent
STOP = threading.Event()
BRIDGE_FILES = ('__init__.py', 'bridge.py', 'model_client.py', 'agent.py', 'contract.py', 'task.py')


def snapshot_bridge(task, engine):
    """Keep the real checkpoint preflight's package imports self-contained."""
    package = engine / 'evaluation'
    package.mkdir()
    for name in BRIDGE_FILES:
        shutil.copy2(task / 'tests/evaluation' / name, package / name)


def command(argv, **kw):
    return subprocess.run([str(x) for x in argv], check=True, **kw)


def capture(argv, **kw):
    return command(argv, stdout=subprocess.PIPE, text=True, **kw).stdout


def external(path, task=None):
    path = Path(path).resolve()
    protected = [HERE.parent]
    if task is not None:
        protected.append(Path(task).resolve())
    if any(path.is_relative_to(root) for root in protected):
        raise ValueError('generated output must be outside the tool checkout and task directory')
    return path


def volume(source, target, readonly=False):
    # --mount uses comma-separated arguments; reject ambiguous host paths.
    if ',' in str(source):
        raise ValueError('Docker bind paths cannot contain commas')
    return ['--mount', 'type=bind,src='+str(source)+',dst='+target+(',readonly' if readonly else '')]


def policy(task):
    env = dict(os.environ)
    prefix = re.sub('[^A-Z0-9]', '', task.name.upper())
    for suffix in ('VERIFIER_STATE', 'VERIFIER_TMP', 'MODEL_RPC_STORAGE', 'VERIFIER_EXCHANGE'):
        env.pop(prefix+'_'+suffix, None)
    config = json.loads(capture(['docker', 'compose', '-f', task/'tests/docker-compose.yaml', '-f', '-',
                                 'config', '--format', 'json'], env=env,
                                input=json.dumps({'services': {'main': {'image': 'policy-inspection-only'}}})))['services']['main']
    config.pop('image')
    for key in ('command', 'entrypoint'):
        if config.get(key) is None:
            config.pop(key, None)
    # Preserve task-specific security/resources, but all three data mounts are
    # explicitly replaced with private bind directories by the coordinator.
    supported = {'network_mode', 'cap_drop', 'cap_add', 'security_opt', 'shm_size',
                 'pids_limit', 'cpus', 'mem_limit', 'volumes'}
    if set(config)-supported:
        raise ValueError('unsupported verifier policy: '+str(sorted(set(config)-supported)))
    if config.get('network_mode') != 'none':
        raise ValueError('verifier must have network_mode: none')
    targets = {m['target'] for m in config['volumes']}
    required = {'/app/candidate-state', '/tmp', '/model'}
    if not required <= targets or targets-required-{'/exchange'}:
        raise ValueError('unexpected verifier mounts')
    # Harbor also applies task.toml resource limits. Preserve those in every
    # standalone lane instead of giving each container unlimited host resources.
    task_config = tomllib.loads((task/'task.toml').read_text())
    resources = task_config.get('verifier', {}).get('environment', {})
    if resources.get('cpus') is not None:
        config.setdefault('cpus', resources['cpus'])
    if resources.get('memory_mb') is not None:
        config.setdefault('mem_limit', int(resources['memory_mb']) * 1024**2)
    return dict({k: v for k, v in config.items() if k != 'volumes'},
                auxiliary_mounts=sorted(targets-required))


def docker_flags(config):
    flags = ['--network', 'none', '--user', 'root']
    for k in ('cap_drop', 'cap_add', 'security_opt'):
        for value in config.get(k, []):
            flags += ['--'+k.replace('_', '-'), str(value)]
    for key, option in [('shm_size', '--shm-size'), ('pids_limit', '--pids-limit'),
                        ('cpus', '--cpus'), ('mem_limit', '--memory')]:
        if key in config:
            flags += [option, str(config[key])]
    return flags


def container_state(name):
    """Establish absence from a successful daemon query, never an inspect error."""
    names = capture(['docker', 'container', 'ls', '-a', '--format', '{{.Names}}']).splitlines()
    if name not in names:
        return 'absent'
    # If it disappears between these calls, fail closed and retry on resume.
    running = capture(['docker', 'inspect', '--format', '{{.State.Running}}', name]).strip()
    if running not in ('true', 'false'):
        raise RuntimeError('Docker returned an unknown container state')
    return 'running' if running == 'true' else 'stopped'


class Coordinator:
    def __init__(self, args):
        self.args = args
        self.task = args.task.resolve()
        self.out = external(args.out, self.task)
        if self.out.exists() and any(self.out.iterdir()):
            raise ValueError('use a fresh --out; previous evidence is preserved')
        self.out.mkdir(parents=True, exist_ok=True)
        self.out.chmod(0o700)
        self.lock = (self.out/'coordinator.lock').open('w')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write(self.out/'process.json', {'pid': os.getpid(), 'started_at': time.time()})
        for name in ('tmp', 'inputs', 'lanes', 'episodes', 'engine'):
            (self.out/name).mkdir()
        self.started = time.monotonic()
        self.check_resources()
        self.name = 'pbp-compare-'+self.task.name+'-'+uuid.uuid4().hex[:12]
        self.config = policy(self.task)
        self.image = capture(['docker', 'image', 'inspect', args.image, '--format', '{{.Id}}']).strip()
        self.solution = self.out/'inputs/candidate'
        # Original submission is never chowned, mounted writable, or launched.
        shutil.copytree(args.candidate.resolve(), self.solution, symlinks=True)
        self.truth = self.out/'inputs/truth'
        shutil.copytree((args.truth or self.task/'tests/data').resolve(), self.truth, symlinks=True)
        self.truth.chmod(0o700)
        for name in ('parallel_compare.py', 'parallel_probe.py', 'parallel_support.py', 'scoring.py'):
            shutil.copy2(HERE/name, self.out/'engine'/name)
        snapshot_bridge(self.task, self.out/'engine')
        (self.out/'engine').chmod(0o700)
        self.probe('inspect')
        self.metadata = read(self.out/'metadata.json')
        if self.metadata['sources'].get('tests/evaluation/scoring.py') != digest((self.out/'engine/scoring.py').read_bytes()):
            raise ValueError('verifier scoring code differs from tools/scoring.py; rebuild the verifier image')
        self.manifest = self.metadata['manifest']
        self.episodes = {w['id']: w for w in self.manifest['episodes']}
        selected = sorted(args.episode or self.episodes)
        if len(selected) != len(set(selected)) or set(selected)-self.episodes.keys():
            raise ValueError('unknown or duplicate --episode selection')
        self.evaluator = {'model': args.model, 'effort': args.effort, 'protocol': args.protocol,
                          'base_url': args.base_url.rstrip('/'), 'max_calls': args.max_calls,
                          'max_tokens': args.max_tokens}
        for w in self.episodes.values():
            if w['execution'] != 'program' and (w['budget']['calls'] > args.max_calls or w['budget']['tokens'] > args.max_tokens):
                raise ValueError('bridge ceiling is below frozen episode budget')
        # Host bridge code must be exactly the code fingerprinted in the image.
        for name in BRIDGE_FILES:
            host = self.out/'engine/evaluation'/name
            if digest(host.read_bytes()) != self.metadata['sources']['tests/evaluation/'+name]:
                raise ValueError('host bridge differs from verifier image: '+name)
        self.identity = {'format': FORMAT, 'task': self.task.name, 'mode': 'compare',
                         'manifest_sha256': digest(self.manifest), 'sources': self.metadata['sources'],
                         'candidate': self.metadata['candidate'], 'truth': self.metadata['truth'],
                         'evaluator': self.evaluator, 'episodes': selected, 'diagnostic': bool(args.episode),
                         'image_id': self.image, 'container_policy': self.config,
                         'engine': fingerprints(self.out/'engine')}
        write(self.out/'identity.json', self.identity)
        write(self.out/'manifest.json', self.manifest)
        self.accepted, self.resumed = {}, []
        if args.resume_from:
            self.resume(args.resume_from.resolve())

    def probe(self, action, lane=None, previous=None):
        suffix = action if lane is None else action+'-'+str(lane)
        if previous is not None:
            suffix = 'resume-'+suffix
        argv = ['docker', 'run', '--rm', '--name', self.name+'-'+suffix, *docker_flags(self.config),
                *volume(self.out/'engine', '/parallel', True), *volume(self.solution, '/app/solution', True),
                *volume(self.truth, '/truth', True), *volume(self.out, '/result')]
        if previous is not None:
            argv += volume(previous, '/previous', True)
        argv += [
                '-e', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python3', self.image,
                '-B', '/parallel/parallel_probe.py', action]
        if lane is not None:
            argv += ['--lane', str(lane)]
        if previous is not None:
            argv += ['--resume-export']
        with (self.out/(suffix+'.log')).open('w') as log:
            command(argv, stdout=log, stderr=subprocess.STDOUT)

    def accept(self, source, wf, origin, expected_hashes=None):
        if expected_hashes is not None and fingerprints(source) != expected_hashes:
            raise ValueError('saved episode evidence changed: '+wf)
        if not completed(source, self.episodes[wf]):
            return False
        hashes = fingerprints(source)
        if expected_hashes is not None and hashes != expected_hashes:
            raise ValueError('saved episode evidence changed: '+wf)
        target = self.out/'episodes'/wf
        shutil.copytree(source, target)
        if fingerprints(target) != hashes:
            raise ValueError('copied evidence differs: '+wf)
        self.accepted[wf] = {'origin': origin, 'files': hashes}
        write(self.out/'accepted.json', self.accepted)
        return True

    def collect_episode(self, output, wf, exported=None):
        if not parent_finished(output, wf):
            return False
        interruption = output.parent/'interrupted.json'
        if interruption.exists() and wf not in read(interruption)['finished_before_stop']:
            return False
        exported = exported or output.parent/'collected-episodes'
        source = (exported if exported.exists() else output/'episodes')/wf
        if self.accept(source, wf, str(source)):
            return True
        # The serial parent legitimately creates final rows outside the worker
        # directory when start.sh is missing or a timed-out worker never wrote
        # its status. Preserve that verdict rather than reclassifying it as an
        # infrastructure fault. Never derive completion from partial progress.
        if not (output/'summary.json').exists() or not (output/'results.jsonl').exists():
            return False
        rows = [json.loads(s) for s in (output/'results.jsonl').read_text().splitlines()]
        rows = [r for r in rows if r['episode'] == wf]
        try:
            validate_rows(rows, self.episodes[wf])
        except (ValueError, KeyError, TypeError):
            return False
        if not any(r.get('failure_kind') in ('candidate_missing_start', 'candidate_timeout') for r in rows):
            return False
        if any((source/n).exists() for n in ('worker-error.json', 'infrastructure-error.json')):
            return False
        # Save a separate finalized view; do not rewrite the lane's raw output.
        finalized = self.out/'finalized'/wf
        finalized.parent.mkdir(exist_ok=True)
        if source.exists():
            shutil.copytree(source, finalized)
        else:
            finalized.mkdir()
        (finalized/'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
        write(finalized/'status.json', {'source_episode': wf, 'infrastructure_error': False,
                                       'passed': all(r['passed'] for r in rows), 'finalized_by_serial_parent': True})
        if not (finalized/'usage.json').exists():
            write(finalized/'usage.json', {'elapsed_seconds': 0, 'worker_usage_unavailable': True})
        write(finalized/'parent-evidence.json', {'path': str(output),
                                              'identity': digest((output/'identity.json').read_bytes()),
                                              'results': digest((output/'results.jsonl').read_bytes())})
        return self.accept(finalized, wf, str(source))

    def resume(self, previous):
        # Refuse live coordinators; changing concurrency is a resume operation,
        # never a second writer or a second assessment of a live episode.
        self.resume_lock = (previous/'coordinator.lock').open('a')
        try:
            fcntl.flock(self.resume_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('resume source coordinator is still running') from None
        for lane in (previous/'lanes').glob('*'):
            name = read(lane/'plan.json')['container']
            if container_state(name) == 'running':
                raise ValueError('resume source verifier is still running: '+name)
        check_resume(read(previous/'identity.json'), self.identity)
        accepted = read(previous/'accepted.json') if (previous/'accepted.json').exists() else {}
        for wf in self.identity['episodes']:
            if wf in accepted:
                if self.accept(previous/'episodes'/wf, wf, str(previous/'episodes'/wf), accepted[wf]['files']):
                    self.resumed.append(wf)
        # A coordinator itself may have been killed before collection. Salvage
        # completed workers from its immutable lane plan, never unfinished ones.
        for lane in sorted((previous/'lanes').glob('*')):
            plan = read(lane/'plan.json')
            output = lane/'output'
            if not (output/'identity.json').exists() or (output/'infrastructure-error.json').exists():
                continue
            check_lane_identity(read(output/'identity.json'), self.identity, plan['episodes'])
            pending = [wf for wf in plan['episodes'] if wf not in self.accepted]
            if pending:
                self.probe('export', int(lane.name), previous=previous)
            for wf in plan['episodes']:
                if wf not in self.accepted and self.collect_episode(output, wf, self.out/'resume-exports'/lane.name):
                    self.resumed.append(wf)

    def lane(self, index, assigned):
        path = self.out/'lanes'/str(index)
        path.mkdir()
        for name in ('output', 'state', 'tmp'):
            (path/name).mkdir()
        (path/'tmp').chmod(0o1777)
        solution = path/'candidate'
        name = self.name+'-'+str(index)
        write(path/'plan.json', {'episodes': sorted(assigned), 'container': name})
        bridge = None
        try:
            if STOP.is_set():
                return
            self.check_resources()
            shutil.copytree(self.solution, solution, symlinks=True)
            spool = path/'model'
            # Even pure program runs need the normal config; no API call is
            # made for them. GUI/mixed runs use the unmodified preflight.
            gui = (self.solution/'start.sh').is_file() and any(self.episodes[w]['execution'] != 'program' for w in assigned)
            if gui:
                bridge_cmd = [sys.executable, '-B', str(self.out/'engine/evaluation/bridge.py'),
                              '--spool', str(spool), '--api-key-file', str(self.args.api_key_file.resolve()),
                              '--base-url', self.args.base_url, '--model', self.args.model,
                              '--effort', self.args.effort, '--protocol', self.args.protocol,
                              '--max-calls', str(self.args.max_calls), '--max-tokens', str(self.args.max_tokens),
                              '--concurrency', '1']
                with (path/'bridge.log').open('w') as log:
                    bridge = subprocess.Popen(bridge_cmd, stdout=log, stderr=subprocess.STDOUT,
                                              env=dict(os.environ, TMPDIR=str(self.out/'tmp'), PYTHONDONTWRITEBYTECODE='1'))
                began = time.monotonic()
                while not (spool/'config.json').exists():
                    if bridge.poll() is not None or STOP.is_set() or time.monotonic()-began > 240:
                        raise RuntimeError('bridge did not become ready; see bridge.log')
                    time.sleep(.2)
                config = read(spool/'config.json')
                if {k: config[k] for k in self.evaluator} != self.evaluator:
                    raise ValueError('bridge configuration mismatch')
            else:
                spool.mkdir(mode=0o700)
                write(spool/'config.json', self.evaluator)
            argv = ['docker', 'run', '--name', name, *docker_flags(self.config),
                    *volume(solution, '/app/solution'), *volume(path/'state', '/app/candidate-state'),
                    *volume(path/'tmp', '/tmp'), *volume(path/'output', '/logs/verifier'),
                    *volume(spool, '/model'), *volume(self.truth, '/truth', True)]
            for target in self.config['auxiliary_mounts']:
                directory = path/target.lstrip('/')
                directory.mkdir()
                argv += volume(directory, target)
            argv += ['-e', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'bash', self.image,
                     '/tests/test.sh', '--mode', 'compare', '--truth', '/truth']
            for wf in assigned:
                argv += ['--episode', wf]
            with (path/'container.log').open('w') as log:
                proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)
                while proc.poll() is None:
                    if STOP.wait(.5):
                        # SIGTERM lets the serial runner retain already finished
                        # episodes; remaining work stays invalid until resume.
                        finished = [w for w in assigned if parent_finished(path/'output', w)
                                    and completed(path/'output/episodes'/w, self.episodes[w])]
                        write(path/'interrupted.json', {'finished_before_stop': finished, 'time': time.time()})
                        subprocess.run(['docker', 'stop', '-t', '35', name], stdout=log, stderr=subprocess.STDOUT)
                        break
                code = proc.wait()
            write(path/'exit.json', {'returncode': code})
        except Exception as exc:
            write(path/'host-error.json', {'type': type(exc).__name__, 'reason': str(exc)})
        finally:
            # Scoped container cleanup only. Do not remove any evidence/state.
            cleanup = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, text=True)
            uncertainty = None
            try:
                absent = container_state(name) == 'absent'
            except Exception as exc:
                absent, uncertainty = False, str(exc)
            write(path/'cleanup.json', {'returncode': cleanup.returncode, 'output': cleanup.stdout,
                                       'error': cleanup.stderr, 'container_absent': absent,
                                       'inspection_error': uncertainty})
            if bridge is not None:
                bridge.terminate()
                try:
                    bridge.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    bridge.kill()
                    bridge.wait()

    def check_resources(self):
        if shutil.disk_usage('/').free < self.args.root_reserve_gib*2**30:
            raise RuntimeError('root disk below reserve; no verifier admitted')
        if shutil.disk_usage(self.out).free < self.args.data_reserve_gib*2**30:
            raise RuntimeError('artifact disk below reserve; no verifier admitted')

    def execute(self):
        remaining = [w for w in self.identity['episodes'] if w not in self.accepted]
        durations = dict(self.metadata['durations'])
        if self.args.timings:
            for w in remaining:
                p = self.args.timings/'episodes'/w/'usage.json'
                if p.exists():
                    durations[w] = read(p)['elapsed_seconds']
        else:
            for w in remaining:
                durations[w] += self.episodes[w].get('budget', {}).get('seconds', 0)
        lanes = partition(remaining, self.args.parallelism, durations)
        write(self.out/'schedule.json', {'parallelism': self.args.parallelism, 'lanes': lanes,
                                        'resumed': self.resumed})
        with ThreadPoolExecutor(max_workers=self.args.parallelism) as pool:
            futures = [pool.submit(self.lane, i, assigned) for i, assigned in enumerate(lanes)]
            for future in as_completed(futures):
                future.result()
        for index, assigned in enumerate(lanes):
            output = self.out/'lanes'/str(index)/'output'
            if not read(output.parent/'cleanup.json')['container_absent']:
                continue
            if not (output/'identity.json').exists() or (output/'infrastructure-error.json').exists():
                continue
            check_lane_identity(read(output/'identity.json'), self.identity, assigned)
            # Runtime logs may be root-private even though point rows are group
            # readable. Export only after the verifier has stopped, using a
            # trusted offline helper; raw evidence content/modes stay untouched.
            self.probe('export', index)
            for wf in assigned:
                self.collect_episode(output, wf)
        incomplete = sorted(set(self.identity['episodes'])-self.accepted.keys())
        write(self.out/'collection.json', {'incomplete': incomplete, 'resumed': self.resumed,
                                         'parallelism': self.args.parallelism,
                                         'elapsed_seconds': time.monotonic()-self.started})
        self.probe('aggregate')
        summary = read(self.out/'summary.json')
        print(json.dumps({k: summary[k] for k in ('task', 'diagnostic', 'episode_passed', 'episode_total',
                                                 'reward', 'infrastructure_error', 'incomplete_episodes')}, ensure_ascii=False), flush=True)
        return 2 if incomplete else 0 if summary['all_passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--image', required=True, help='built verifier image; pinned by image ID for the run')
    parser.add_argument('--candidate', type=Path, required=True, help='saved candidate OR installed standard answer')
    parser.add_argument('--truth', type=Path, help='external frozen bundle; default task/tests/data')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--parallelism', type=int, choices=(1, 2, 4), default=1)
    parser.add_argument('--episode', action='append', help='select diagnostic episodes; omit for full scoring')
    parser.add_argument('--resume-from', type=Path, help='identical prior parallel run; parallelism may change')
    parser.add_argument('--timings', type=Path, help='prior verifier directory for scheduling only')
    parser.add_argument('--api-key-file', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', default='kimi-k3')
    parser.add_argument('--effort', default='high')
    parser.add_argument('--protocol', choices=['deepseek-chat', 'openai-chat'], default='openai-chat')
    parser.add_argument('--max-calls', type=int, default=400)
    parser.add_argument('--max-tokens', type=int, default=8_000_000)
    parser.add_argument('--root-reserve-gib', type=float, default=0,
                        help='minimum root-filesystem free GiB before admission; 0 disables this check')
    parser.add_argument('--data-reserve-gib', type=float, default=0,
                        help='minimum output-filesystem free GiB before admission; 0 disables this check')
    args = parser.parse_args(argv)
    if any(not 0 <= value < float('inf') for value in (args.root_reserve_gib, args.data_reserve_gib)):
        parser.error('disk reserves must be finite nonnegative GiB values')
    STOP.clear()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    try:
        return Coordinator(args).execute()
    except Exception as exc:
        print(type(exc).__name__+': '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
