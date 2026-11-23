"""Own one product's descendants, including children that create new sessions.

A dedicated Linux child subreaper keeps orphaned descendants attached to this
instance. No process-name, user-wide, or process-group kill is needed. The
private control socket is never inherited by the application.
"""
import ctypes
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time


class RuntimeCleanupError(RuntimeError):
    """The runtime could not stop an instance or clear its private state."""


def _send(control, value):
    control.sendall(json.dumps(value).encode() + b'\n')


def _receive(stream):
    line = stream.readline(1_000_000)
    if not line or not line.endswith(b'\n'):
        raise RuntimeCleanupError('product supervisor closed its control channel')
    return json.loads(line)


class ProductProcess:
    """Popen-like launcher whose wait includes every owned descendant's exit."""

    def __init__(self, command, *, cwd, env, stdout, stderr, **credentials):
        control, child = socket.socketpair()
        self.control, self.stream = control, control.makefile('rb')
        self.returncode = None
        self.finished = False
        self.failure = None
        try:
            self.supervisor = subprocess.Popen(
                [sys.executable, '-I', '-B', str(Path(__file__).resolve()), str(child.fileno())],
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, env=env,
                pass_fds=(child.fileno(),), start_new_session=True)
        except OSError as exc:
            self.stream.close()
            control.close()
            raise RuntimeCleanupError('could not launch the product supervisor') from exc
        finally:
            child.close()
        try:
            control.settimeout(15)
            _send(control, dict(command=command, cwd=cwd, env=env, credentials=credentials))
            status = _receive(self.stream)
            if 'launch_error' in status:
                self.supervisor.wait(5)
                raise OSError(status['errno'], status['launch_error'])
            if 'pid' not in status:
                raise RuntimeCleanupError(status.get('cleanup_error', 'product supervisor did not start'))
            self.pid = status['pid']
            control.settimeout(None)
        except BaseException:
            self.stream.close()
            control.close()  # EOF also asks the supervisor to stop its descendants.
            try:
                self.supervisor.wait(22)
            except subprocess.TimeoutExpired:
                self._abort_supervisor()
            raise

    def _abort_supervisor(self):
        """Bound failure handling too; target only this exact Popen child."""
        self.supervisor.kill()
        try:
            self.supervisor.wait(5)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeCleanupError('product supervisor did not exit after SIGKILL') from exc
        finally:
            self.stream.close()
            self.control.close()

    def _finish(self):
        if not self.finished:
            try:
                status = _receive(self.stream)
                if 'cleanup_error' in status:
                    raise RuntimeCleanupError(status['cleanup_error'])
                self.returncode = status['returncode']
            except Exception as exc:
                self.failure = exc
            finally:
                self.finished = True
                self.stream.close()
                self.control.close()
        if self.failure is not None:
            raise self.failure
        return self.returncode

    def poll(self):
        return None if self.supervisor.poll() is None else self._finish()

    def wait(self, timeout=None):
        self.supervisor.wait(timeout)
        return self._finish()

    def stop(self, grace):
        if self.supervisor.poll() is None:
            try:
                _send(self.control, {'stop': max(0., float(grace))})
            except BrokenPipeError:
                pass
        try:
            self.wait(max(0., grace) + 7)
        except subprocess.TimeoutExpired as exc:
            self._abort_supervisor()
            raise RuntimeCleanupError('product descendants did not stop within the cleanup deadline') from exc


def _process(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()
        return int(fields[1]), int(fields[19])  # parent PID, birth time
    except (FileNotFoundError, ProcessLookupError):
        return None


def _descendants():
    snapshot = {}
    for entry in Path('/proc').iterdir():
        if entry.name.isdecimal():
            info = _process(int(entry.name))
            if info:
                snapshot[int(entry.name)] = info
    owned = {os.getpid()}
    while True:
        children = {pid for pid, (parent, _) in snapshot.items() if parent in owned}
        if children <= owned:
            return {pid: snapshot[pid] for pid in owned if pid != os.getpid()}
        owned.update(children)


def _signal_owned(pid, identity, signum):
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        # A PID might have been recycled between the snapshot and pidfd_open.
        # Once identity is verified, the pidfd cannot target a replacement.
        if _process(pid) == identity:
            try:
                signal.pidfd_send_signal(fd, signum)
            except ProcessLookupError:
                pass
    finally:
        os.close(fd)


def _reap(child):
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if not pid:
            return
        if pid == child.pid:
            child.returncode = os.waitstatus_to_exitcode(status)


def _stop_descendants(child, grace, control, stream):
    deadline = time.monotonic() + grace
    sent = set()
    while True:
        _reap(child)
        descendants = _descendants()
        if not descendants:
            return
        now = time.monotonic()
        if select.select([control], [], [], 0)[0]:
            try:
                deadline = min(deadline, now + _receive(stream)['stop'])
            except RuntimeCleanupError:
                deadline = min(deadline, now + .1)
        signum = signal.SIGTERM if now < deadline else signal.SIGKILL
        for pid, identity in descendants.items():
            key = (pid, identity, signum)
            if key not in sent:
                _signal_owned(pid, identity, signum)
                sent.add(key)
        if now >= deadline + 5:
            raise RuntimeCleanupError('product descendants remained after SIGKILL')
        time.sleep(.02)


def _supervise(control):
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeCleanupError('product supervision requires Linux pidfd support')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise RuntimeCleanupError('could not enable the per-instance child subreaper')
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    stream = control.makefile('rb')
    request = _receive(stream)
    try:
        child = subprocess.Popen(request['command'], cwd=request['cwd'], env=request['env'],
                                 stdin=subprocess.DEVNULL, **request['credentials'])
    except OSError as exc:
        _send(control, {'launch_error': exc.strerror or str(exc), 'errno': exc.errno})
        return
    _send(control, {'pid': child.pid})
    grace = 10.
    try:
        while child.poll() is None and not stopping:
            if select.select([control], [], [], .05)[0]:
                try:
                    grace = _receive(stream)['stop']
                except RuntimeCleanupError:  # The owner exited or closed the channel.
                    pass
                break
    finally:
        _stop_descendants(child, grace, control, stream)
    _send(control, {'returncode': child.wait()})


if __name__ == '__main__':
    with socket.socket(fileno=int(sys.argv[1])) as control:
        try:
            _supervise(control)
        except BaseException as exc:
            try:
                _send(control, {'cleanup_error': f'{type(exc).__name__}: {exc}'})
            except BrokenPipeError:
                pass
