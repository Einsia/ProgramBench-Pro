#!/usr/bin/env python3
"""Expose the protected reference RPC only inside the solving container.

The reference product must retain its root-only socket. This fixed-target relay
is installed only in the agent image, never in the reference or verifier image.
"""
import fcntl
import os
from pathlib import Path
import pwd
import select
import signal
import socket
import socketserver
import stat
import subprocess
import sys
import threading

TARGET = '/blackbox/reference.sock'
PUBLIC = '/run/pbp-reference/reference.sock'


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        # Bound both stalled callers and the number of live relay threads.
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
                upstream.settimeout(180)
                self.request.settimeout(180)
                upstream.connect(TARGET)
                peers = {self.request: upstream, upstream: self.request}
                readable = set(peers)
                while readable:
                    ready, _, _ = select.select(list(readable), [], [], 180)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if data:
                            peers[source].sendall(data)
                        else:
                            readable.remove(source)
                            peers[source].shutdown(socket.SHUT_WR)
        except OSError:
            # A reset or a reference restart affects this connection only.
            return


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    request_queue_size = 64

    def __init__(self, path):
        self.slots = threading.BoundedSemaphore(64)
        super().__init__(path, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def prepare_socket():
    if os.geteuid() != 0:
        raise RuntimeError('agent entrypoint must start as root; model commands run as agent')
    directory = Path(PUBLIC).parent
    directory.mkdir(mode=0o755, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('unsafe agent relay directory')
    lock = os.open(str(directory / 'relay.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # A container restart can leave a stale socket; the lock prevents replacing
    # a live relay, and the directory is never writable by the solving user.
    path = Path(PUBLIC)
    try:
        info = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0:
            raise RuntimeError('unsafe existing agent relay socket')
        path.unlink()
    return lock


def main(argv=None):
    command = list(sys.argv[1:] if argv is None else argv)
    if not command:
        raise SystemExit('agent entrypoint requires a command')
    lock = prepare_socket()
    child = None
    stopping = threading.Event()

    def forward(number, _frame):
        stopping.set()
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, number)
            except ProcessLookupError:
                pass

    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, forward)
    try:
        with Server(PUBLIC) as server:
            os.chown(PUBLIC, 0, pwd.getpwnam('agent').pw_gid)
            os.chmod(PUBLIC, 0o660)
            relay = threading.Thread(target=server.serve_forever, daemon=True)
            relay.start()
            if stopping.is_set():
                return 143
            child = subprocess.Popen(command, start_new_session=True)
            try:
                while child.poll() is None:
                    if stopping.wait(.2) or not relay.is_alive():
                        os.killpg(child.pid, signal.SIGTERM)
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            child.wait()
                        return 143 if stopping.is_set() else 1
                return child.returncode if child.returncode >= 0 else 128 - child.returncode
            finally:
                server.shutdown()
                relay.join(timeout=2)
    finally:
        Path(PUBLIC).unlink(missing_ok=True)
        os.close(lock)


if __name__ == '__main__':
    sys.exit(main())
