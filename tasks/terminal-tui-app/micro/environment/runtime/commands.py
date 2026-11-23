"""Run an application command with bounded pipes and a private process group."""
import os
import selectors
import signal
import subprocess
import time


def run_bounded(argv, *, cwd, env, timeout, stream_limit, input=None,
                merge_stderr=False, total_limit=None, **kwargs):
    """Return a CompletedProcess with byte output; terminate the group on every exit.

    Pipe input and output concurrently. Output bounds apply while reading, and
    the deadline includes waiting for inherited pipes and process termination.
    The caller supplies the identity and environment of the application.
    """
    proc = subprocess.Popen(argv, cwd=cwd, env=env,
                            stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
                            start_new_session=True, **kwargs)
    selector = selectors.DefaultSelector()
    outputs = {'stdout': bytearray()}
    if not merge_stderr:
        outputs['stderr'] = bytearray()
    deadline = time.monotonic() + timeout
    pending = memoryview(input or b'')
    total = 0
    try:
        for name in outputs:
            pipe = getattr(proc, name)
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        if proc.stdin is not None:
            if pending:
                os.set_blocking(proc.stdin.fileno(), False)
                selector.register(proc.stdin, selectors.EVENT_WRITE, 'stdin')
            else:
                proc.stdin.close()
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout)
            for key, _ in selector.select(min(0.1, remaining)):
                if key.data == 'stdin':
                    try:
                        count = os.write(key.fileobj.fileno(), pending[:65536])
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        pending = memoryview(b'')
                    else:
                        pending = pending[count:]
                    if not pending:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                try:
                    chunk = os.read(key.fileobj.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                target = outputs[key.data]
                total += len(chunk)
                if len(target) + len(chunk) > stream_limit or total_limit is not None and total > total_limit:
                    raise ValueError('command output exceeded the observation limit')
                target.extend(chunk)
        proc.wait(timeout=max(0.001, deadline-time.monotonic()))
        return subprocess.CompletedProcess(argv, proc.returncode, bytes(outputs['stdout']),
                                           None if merge_stderr else bytes(outputs['stderr']))
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
        selector.close()
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None:
                pipe.close()
