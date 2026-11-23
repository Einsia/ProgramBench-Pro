#!/usr/bin/env python3
"""Public black-box client. Contains no implementation of any product.

Sends one JSON request to a black-box runtime and prints the JSON answer.
The default target is the reference. With --target self the same request goes
to your own /app/solution, driven by the same runtime code the evaluation uses:
the runtime is started on first use as your user, with private state, logs and
socket under /tmp/blackbox-self, and reused by later requests.
Start with: blackbox '{"op":"help"}'
"""
import argparse
import base64
import fcntl
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time

DEFAULT_SOCKET = '/blackbox/reference.sock'
RUNTIME = Path(os.environ.get('BLACKBOX_RUNTIME', '/opt/blackbox/runtime'))
sys.path.insert(0, str(RUNTIME))
from blackbox_runtime import strict_json_loads
SELF_ROOT = Path(os.environ.get('BLACKBOX_SELF_ROOT', '/tmp/blackbox-self'))
SELF_SOLUTION = '/app/solution'
SELF_START_SECONDS = 300


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def call(request, socket_path=None, timeout=120):
    """Send one request; returns the decoded JSON answer (errors are {"error", "detail"} objects)."""
    connection = UnixConnection(socket_path or os.environ.get('BLACKBOX_SOCKET', DEFAULT_SOCKET), timeout)
    try:
        connection.request('POST', '/rpc', json.dumps(request).encode(), {'Content-Type': 'application/json'})
        return json.loads(connection.getresponse().read())
    finally:
        connection.close()


# -- --target self: the same runtime on your own /app/solution ------------------------------------------------------
def self_root():
    """The private 0700 directory of the self runtime, owned by the current user."""
    try:
        SELF_ROOT.mkdir(mode=0o700, parents=True)
    except FileExistsError:
        pass
    info = SELF_ROOT.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise SystemExit(f'{SELF_ROOT} must be a directory owned by the current user')
    if stat.S_IMODE(info.st_mode) != 0o700:
        SELF_ROOT.chmod(0o700)
    return SELF_ROOT


def answers(path):
    try:
        call({'op': 'status'}, str(path), timeout=15)
        return True
    except (OSError, ValueError, http.client.HTTPException):
        return False


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def stop_self(root=None):
    """Stop a running self runtime (it stops its product); returns whether one was running."""
    root = root or SELF_ROOT
    pid_file = root / 'runtime.pid'
    try:
        pid = int(pid_file.read_text())
    except (OSError, ValueError):
        pid = None
    running = False
    if pid:
        try:
            os.killpg(pid, signal.SIGTERM)
            running = True
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                os.killpg(pid, 0)
                time.sleep(.2)
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    # The runtime stops its product on SIGTERM; a product it could not stop is found by its DATA_DIR.
    marker = b'DATA_DIR=' + str(root / 'instance').encode()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid == os.geteuid() and marker in (entry / 'environ').read_bytes():
                os.kill(int(entry.name), signal.SIGKILL)
                running = True
        except OSError:
            continue
    for path in (pid_file, root / 'reference.sock'):
        try:
            path.unlink()
        except OSError:
            pass
    return running


def start_self():
    """Socket of the self runtime, starting it first if it is not answering."""
    root = self_root()
    sock = root / 'reference.sock'
    if sock.exists() and answers(sock):
        return sock
    with (root / 'start.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if sock.exists() and answers(sock):
            return sock
        stop_self(root)
        entry = RUNTIME / 'broker.py'
        if not entry.is_file():
            raise SystemExit(f'the black-box runtime is not installed at {RUNTIME}')
        logs = root / 'logs'
        logs.mkdir(mode=0o700, exist_ok=True)
        command = [sys.executable, '-B', '-I', str(entry), '--solution', SELF_SOLUTION, '--state', str(root / 'instance'),
                   '--socket', str(sock), '--socket-mode', '0600', '--log-dir', str(logs), '--work', str(root / 'work'),
                   '--port', str(free_port())]
        with (logs / 'runtime.log').open('ab') as log:
            proc = subprocess.Popen(command, cwd=str(root), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        (root / 'runtime.pid').write_text(str(proc.pid))
        print(f'starting the self runtime on {SELF_SOLUTION} (logs in {logs})', file=sys.stderr)
        deadline = time.monotonic() + SELF_START_SECONDS
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise SystemExit(f'the self runtime exited with status {proc.returncode}; see {logs / "runtime.log"}')
            if sock.exists() and answers(sock):
                return sock
            time.sleep(.5)
        stop_self(root)
        raise SystemExit(f'the self runtime did not start within {SELF_START_SECONDS} s; see {logs / "runtime.log"}')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Send one JSON request to the offline product black box. '
                                                 'Use {"op":"help"} for the protocol.')
    parser.add_argument('request', nargs='?', help='JSON object; read from standard input if omitted or -')
    parser.add_argument('--out', help='save screenshot or binary product data (png_base64/body_base64) to this file')
    parser.add_argument('--target', choices=('reference', 'self'), default='reference',
                        help='reference (default) or self: your own /app/solution through the same runtime, '
                             'started on first use')
    parser.add_argument('--stop', action='store_true', help='with --target self: stop the self runtime')
    args = parser.parse_args(argv)
    if args.stop:
        if args.target != 'self':
            parser.error('--stop only applies to --target self')
        print(json.dumps({'stopped': stop_self()}))
        return 0
    request = strict_json_loads(sys.stdin.read() if args.request in (None, '-') else args.request)
    result = call(request, str(start_self())) if args.target == 'self' else call(request)
    if isinstance(result, dict) and args.out:
        field = 'png_base64' if isinstance(result.get('png_base64'), str) else 'body_base64'
        if isinstance(result.get(field), str):
            with open(args.out, 'wb') as stream:
                stream.write(base64.b64decode(result.pop(field)))
            result['saved_to'] = args.out
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Product HTTP errors are observations (nested under body/status). A broker
    # rejection or timeout is a failed request and fails the command.
    return 1 if isinstance(result, dict) and 'error' in result else 0


if __name__ == '__main__':
    raise SystemExit(main())
