#!/usr/bin/env python3
"""Start the reference wiki with external programs limited to local notebook versioning."""
import ctypes
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading


COMMANDS = {'init', 'add', 'commit', 'status', 'log', 'show', 'diff', 'blame', 'checkout', 'reset', 'config'}


def git_request(request, package):
    cwd = Path(request['cwd']).resolve()
    roots = [Path(os.environ[name]).resolve() for name in ('PBP_INBOX', 'PBP_OUTBOX', 'PBP_NOTEBOOK')
             if os.environ.get(name)]
    if not any(cwd == root or cwd.is_relative_to(root) for root in roots):
        raise ValueError('version control is limited to exchanged notebooks')
    args = request['args']
    if not isinstance(args, list) or not args or args[0] not in COMMANDS or not all(isinstance(a, str) for a in args):
        raise ValueError('only local notebook version-control commands are available')
    if args[0] == 'config' and args != ['config', 'core.quotepath', 'off']:
        raise ValueError('version-control command configuration is fixed')
    for value in args[1:]:
        if '\0' in value or value.startswith(('--exec-path', '--upload-pack', '--receive-pack', '--ext-diff')):
            raise ValueError('external version-control helpers are unavailable')
        if value.startswith('/') or value.startswith(('./', '../')):
            path = Path(value) if value.startswith('/') else cwd / value
            if not any(path.resolve() == root or path.resolve().is_relative_to(root) for root in roots):
                raise ValueError('version-control paths must stay within exchanged notebooks')
    preload = str(package / 'exec_guard.so') + (':' + os.environ['LD_PRELOAD'] if os.environ.get('LD_PRELOAD') else '')
    env = dict(os.environ, LD_PRELOAD=preload, GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0', GIT_PAGER='', GIT_EDITOR='/bin/false')
    options = ['-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0',
               '-c', 'maintenance.auto=false', '-c', 'protocol.allow=never', '-c', 'diff.external=']
    done = subprocess.run(['/usr/bin/git', *options, *args], cwd=cwd, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    return {'code': done.returncode, 'stdout': done.stdout.decode('utf-8', 'replace'),
            'stderr': done.stderr.decode('utf-8', 'replace')}


def git_service(package):
    for line in sys.stdin:
        try:
            result = git_request(json.loads(line), package)
        except Exception as exc:
            result = {'code': 1, 'stdout': '', 'stderr': str(exc)}
        print(json.dumps(result), flush=True)


def configure_programs(service):
    from zim.applications import Application
    lock = threading.Lock()

    def run(self, args=None, cwd=None, *, capture=False, input=None):
        if type(self) is not Application or self.cmd not in (('git',), ('/usr/bin/git',)) or input is not None:
            raise PermissionError('external applications and custom tools are unavailable')
        request = {'args': [str(getattr(arg, 'path', arg)) for arg in (args or ())],
                   'cwd': str(getattr(cwd, 'path', cwd) or os.getcwd())}
        with lock:
            service.stdin.write(json.dumps(request) + '\n')
            service.stdin.flush()
            result = json.loads(service.stdout.readline())
        if result['code'] and not capture:
            raise RuntimeError(result['stderr'])
        return result['stdout'].splitlines(keepends=True) if capture else None

    def pipe(self, args=None, cwd=None, input=None):
        return run(self, args, cwd, capture=True, input=input)

    def denied(*args, **kwargs):
        raise PermissionError('external applications and custom tools are unavailable')

    Application.run, Application.pipe, Application.spawn = run, pipe, denied


def main():
    package = Path(__file__).resolve().parent
    if sys.argv[1:] == ['--git-service']:
        git_service(package)
        return
    source = package / 'zim-src'
    service = subprocess.Popen([sys.executable, '-I', '-B', str(package / 'launch.py'), '--git-service'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    sys.path.insert(0, str(source))
    sys.argv[0] = str(source / 'zim.py')
    configure_programs(service)
    # The wiki cannot execute programs. A separate helper accepts only bounded local Git operations.
    ctypes.CDLL(str(package / 'exec_guard.so'))
    try:
        runpy.run_path(sys.argv[0], run_name='__main__')
    finally:
        service.stdin.close()
        service.terminate()
        service.wait()


if __name__ == '__main__':
    main()
