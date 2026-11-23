"""Private file RPC between an offline Harbor verifier and a host model bridge.

Only model observations/tool responses cross this channel. The API key stays on
the host. No Docker socket, inference HTTP listener or shell is exposed inside
the candidate's namespace.

The evaluator model, effort and endpoint are runtime configuration of the
bridge (written to config.json and recorded in the run outputs); they are not
part of the frozen bundle. A provider that does not answer within a request's
deadline makes the run invalid (unavailable.json); it is never reported as an
exhausted evaluator budget.
"""
import argparse
import dataclasses
import json
import os
from pathlib import Path
import time
import uuid
import concurrent.futures
import sys

try:
    from .model_client import PROTOCOLS, Budget, BudgetExceeded, ModelClient, ModelError, ProviderUnavailable, credential
except ImportError:
    from model_client import PROTOCOLS, Budget, BudgetExceeded, ModelClient, ModelError, ProviderUnavailable, credential

REQUEST_DEADLINE = 900   # seconds the bridge may spend on one request, provider retries included
def preflight_tools():
    # Exercise the actual nested enum schemas that the evaluator sends. A noop
    # tool accepted by a gateway does not establish compatibility with these.
    if __package__:
        from .agent import FINISH, report_tool
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from evaluation.agent import FINISH, report_tool
    return [FINISH, report_tool(['preflight'])]


ATTEMPT_TIMEOUT = 180    # seconds of one provider attempt
TRANSIENT = ('TimeoutError', 'model transport failed', 'HTTP 408', 'HTTP 429', 'HTTP 500', 'HTTP 502', 'HTTP 503',
             'HTTP 504', 'HTTP 520', 'HTTP 521', 'HTTP 522', 'HTTP 523', 'HTTP 524', 'HTTP 529')


def atomic_json(path, value):
    temporary = path.with_suffix('.pending')
    with temporary.open('x') as f:
        json.dump(value, f)
    temporary.chmod(0o644)  # parent is owner-only; host must read root-written requests
    temporary.replace(path)


class SpoolClient:
    """Verifier side: one request file per model call; waits for the bridge's response file."""

    def __init__(self, directory, budget, *, episode='main', monitor=None):
        self.directory, self.budget, self.episode = Path(directory), budget, episode
        self.monitor = Path(monitor) if monitor else None
        self.wait_total = 0.0

    def mark(self, since):
        """Expose time spent waiting for the model, so the episode wall limit can exclude it."""
        if self.monitor:
            pending = self.monitor.with_suffix('.pending')
            pending.write_text(json.dumps({'total': round(self.wait_total, 3), 'since': since}))
            pending.replace(self.monitor)

    def complete(self, messages, tools, *, timeout=None):
        if self.budget.calls >= self.budget.max_calls or self.budget.tokens >= self.budget.max_tokens:
            raise BudgetExceeded('episode model budget exhausted')
        request_id = uuid.uuid4().hex
        request = self.directory / f'request-{request_id}.json'
        response = self.directory / f'response-{request_id}.json'
        created = time.time()
        self.budget.calls += 1
        atomic_json(request, {'episode': self.episode, 'messages': messages, 'tools': tools,
                              'timeout': ATTEMPT_TIMEOUT, 'created': created, 'deadline': created + REQUEST_DEADLINE})
        started = time.monotonic()
        self.mark(time.time())
        try:
            until = started + REQUEST_DEADLINE + 60
            while not response.exists():
                if time.monotonic() > until:
                    raise ProviderUnavailable('model bridge did not answer within the request deadline')
                time.sleep(.1)
            result = json.loads(response.read_text())
        finally:
            self.wait_total += time.monotonic() - started
            self.mark(None)
        if 'error' in result:
            if result.get('kind') == 'budget_exhausted':
                raise BudgetExceeded(result['error'])
            raise ProviderUnavailable(result['error'])
        usage = result['usage']
        # A received reply is never discarded; budgets are enforced before each call.
        self.budget.tokens += usage['total_tokens']
        return result['message'], usage


def bridge(argv=None):
    ap = argparse.ArgumentParser(description='Host-only model bridge for the offline Harbor verifier')
    ap.add_argument('--spool', required=True, type=Path)
    ap.add_argument('--api-key-file', type=Path)
    ap.add_argument('--base-url', required=True,
                    help='HTTPS base URL of the chat-completions endpoint; /chat/completions is appended')
    ap.add_argument('--model', default='kimi-k3', help='evaluator model (the tasks were validated with kimi-k3)')
    ap.add_argument('--effort', default='high', help='reasoning effort sent with every request')
    ap.add_argument('--protocol', default='openai-chat', choices=sorted(PROTOCOLS))
    ap.add_argument('--max-calls', type=int, default=400, help='independent bridge ceiling per episode; worker applies frozen episode budget')
    ap.add_argument('--max-tokens', type=int, default=8_000_000, help='independent bridge ceiling per episode; worker applies frozen episode budget')
    ap.add_argument('--concurrency', type=int, default=2)
    ap.add_argument('--idle-timeout', type=float, default=172_800,
                    help='seconds without a new request before the bridge exits; must exceed the longest gap between '
                         'requests: the agent phase plus the program episodes before the first GUI episode')
    ap.add_argument('--no-preflight', action='store_true',
                    help='skip the start-up request that checks endpoint, credential and model')
    args = ap.parse_args(argv)
    directory = args.spool.resolve()
    if directory.exists() and any(directory.iterdir()):
        ap.error('use a fresh private bridge directory')
    directory.mkdir(parents=True, exist_ok=True);directory.chmod(0o700)
    key = credential(args.api_key_file);clients = {}
    # Check the configuration now instead of at the first GUI episode, hours later: the client validates the URL
    # and credential, and one minimal request in the evaluation dialect must succeed. config.json, the readiness
    # signal, is written only afterwards.
    try:
        probe = ModelClient(key, base_url=args.base_url, model=args.model, effort=args.effort, protocol=args.protocol,
                            max_tokens=1024, budget=Budget(1, 1_000_000))
        if not args.no_preflight:
            probe.complete([{'role': 'user', 'content': 'Reply with the single word OK.'}], preflight_tools(), timeout=ATTEMPT_TIMEOUT)
    except (ModelError, ValueError) as exc:
        ap.exit(2, f'bridge: evaluator check failed: {exc}\n')
    atomic_json(directory / 'config.json', {k: getattr(args, k) for k in ('base_url','model','effort','protocol','max_calls','max_tokens','concurrency')})

    def request(path):
        started = time.time()
        try:
            if path.is_symlink() or path.stat().st_size > 12_000_000:
                raise ModelError('invalid model request file')
            req = json.loads(path.read_text());name = req.get('episode', 'main')
            client = clients.setdefault(name, ModelClient(key, base_url=args.base_url, model=args.model, effort=args.effort,
                                                          protocol=args.protocol, budget=Budget(args.max_calls, args.max_tokens)))
            deadline = req.get('deadline', started + REQUEST_DEADLINE)
            attempts, last = 0, 'no attempt'
            # Provider outages are retried until the request deadline; then the run is invalid.
            while True:
                remaining = deadline - time.time()
                if remaining <= 1:
                    raise ProviderUnavailable(f'provider did not answer before the request deadline ({last})')
                attempts += 1
                try:
                    message, usage = client.complete(req['messages'], req['tools'], timeout=min(req.get('timeout', ATTEMPT_TIMEOUT), remaining))
                    break
                except BudgetExceeded:
                    raise
                except ModelError as exc:
                    last = str(exc)
                    # A gateway can answer 400 transiently; retry it a little before declaring the provider unavailable.
                    retry_400 = 'HTTP 400' in last and attempts < 3
                    if not retry_400 and not any(code in last for code in TRANSIENT):
                        raise ProviderUnavailable(last) from None
                    pause = 10 * attempts if ('HTTP 429' in last or 'HTTP 400' in last) else min(30, 2 ** attempts)
                    time.sleep(max(0, min(pause, deadline - time.time() - 1)))
            usage = dict(usage, attempts=attempts, queue_seconds=round(max(0.0, started - req.get('created', started)), 3))
            result = {'message': message, 'usage': usage}
        except BudgetExceeded as exc:
            result = {'error': str(exc), 'kind': 'budget_exhausted'}
        except Exception as exc:
            error = str(exc) if isinstance(exc, ModelError) else f'bridge failure ({type(exc).__name__})'
            result = {'error': error, 'kind': 'provider_unavailable'}
            # A broken or silent inference service invalidates the run; stop
            # scheduling fresh episodes instead of manufacturing failures.
            try:
                with (directory / 'unavailable.json').open('x') as f:
                    json.dump({'error': error, 'request': path.name, 'time': time.time()}, f)
            except FileExistsError:
                pass
        atomic_json(path.with_name(path.name.replace('request-', 'response-')), result)
    seen = set();last = time.monotonic();active = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        while time.monotonic() - last < args.idle_timeout:
            if (directory / 'finished.json').exists() and not active:
                break
            for path in sorted(directory.glob('request-*.json')):
                if path.name in seen:
                    continue
                seen.add(path.name);last = time.monotonic();active[pool.submit(request, path)] = path
            for future in list(active):
                if future.done():
                    future.result();active.pop(future)
            time.sleep(.1)
    atomic_json(directory / 'usage.json', {name: dataclasses.asdict(client.budget) for name, client in clients.items()})
    return 0


if __name__ == '__main__':
    raise SystemExit(bridge())
