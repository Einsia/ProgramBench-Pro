"""Transport for the product's documented scripting FIFO protocol (mod-script-pipe line protocol)."""
from __future__ import annotations
import json, math, os, pathlib, re, select, stat, time
import blackbox_runtime as runtime

MAX_REPLY = 4_000_000
SUFFIXES = ('.to.{uid}', '.to_pipe_{uid}')


class PipeError(RuntimeError):
    """The scripting endpoint is missing, not a FIFO, or stopped answering."""


def encode(name, params=None):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', name):
        raise ValueError('invalid product command identifier')
    parts = []
    for key, value in (params or {}).items():
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9 _-]*', key):
            raise ValueError('invalid product parameter')
        if isinstance(value, bool):
            value = '1' if value else '0'
        elif isinstance(value, (int, float)):
            if not math.isfinite(value):
                raise ValueError('product parameter must be finite')
            value = str(value)
        elif isinstance(value, str):
            if any(ord(c) < 32 for c in value):
                raise ValueError('control characters in product parameter')
            value = '"'+value.replace('\\', '\\\\').replace('"', '\\"')+'"'
        else:
            raise ValueError('product parameter must be a scalar')
        parts.append(f'{key}={value}')
    return (name+': '+' '.join(parts)+'\n').encode()


class PipeClient:
    """One connection to the endpoints of one application process in one directory."""

    def __init__(self, directory, uid):
        self.directory, self.uid = pathlib.Path(directory), uid
        self.reader = self.writer = None
        self.buffer = b''
        self.inodes = None

    def connect(self, deadline):
        """Open named pipes through a retained no-follow parent directory descriptor."""
        while True:
            found = False
            try:
                with runtime.open_directory(self.directory) as parent:
                    for suffix in SUFFIXES:
                        to = 'audacity_script_pipe' + suffix.format(uid=self.uid)
                        back = 'audacity_script_pipe' + suffix.replace('.to', '.from').format(uid=self.uid)
                        try:
                            infos = [os.stat(name, dir_fd=parent, follow_symlinks=False) for name in (to, back)]
                        except FileNotFoundError:
                            continue
                        found = True
                        if not all(stat.S_ISFIFO(info.st_mode) for info in infos):
                            raise PipeError('scripting endpoints must be named pipes')
                        try:
                            self.writer = os.open(to, os.O_WRONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
                            self.reader = os.open(back, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
                            opened = (os.fstat(self.writer), os.fstat(self.reader))
                            if not all(stat.S_ISFIFO(info.st_mode) for info in opened):
                                raise PipeError('scripting endpoints changed while connecting')
                            self.inodes = ((to, opened[0].st_ino), (back, opened[1].st_ino))
                            return self
                        except (OSError, PipeError) as exc:
                            self.close()
                            if isinstance(exc, PipeError):
                                raise
            except FileNotFoundError:
                pass
            if time.monotonic() >= deadline:
                raise PipeError('the application exposed no scripting pipes in PBP_AUDIO_PIPE_DIR' if not found
                                else 'the application did not open its scripting pipes')
            time.sleep(.05)

    def close(self):
        for fd in (self.reader, self.writer):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self.reader = self.writer = None
        self.buffer = b''

    def unlink_stale(self):
        """Unlink stopped endpoint entries without following any path component."""
        try:
            with runtime.open_directory(self.directory) as parent:
                for name, inode in self.inodes or ():
                    try:
                        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                        if stat.S_ISFIFO(info.st_mode) and info.st_ino == inode:
                            runtime.unlink_entry(parent, name, missing_ok=True)
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            pass

    def command(self, name, params, timeout):
        """One request; returns {'ok', 'body'}. A reply that does not complete closes the channel."""
        line = encode(name, params)
        deadline = time.monotonic()+timeout
        pending = memoryview(line)
        while pending:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise PipeError('scripting request write timed out')
            if select.select([], [self.writer], [], min(.2, remaining))[1]:
                try:
                    pending = pending[os.write(self.writer, pending):]
                except BlockingIOError:
                    continue
                except OSError as exc:
                    raise PipeError('scripting request could not be written: '+exc.strerror) from None
        data = self.buffer
        while True:
            marker = re.search(rb'BatchCommand finished: ([^\r\n]+)\r?\n\r?\n', data)
            if marker:
                text = data[:marker.start()].decode('utf-8', errors='replace').strip()
                self.buffer = data[marker.end():].lstrip(b'\r\n')
                ok = marker.group(1).strip() == b'OK'
                try:
                    body = json.loads(text) if text else None
                except (json.JSONDecodeError, RecursionError):
                    body = text
                return {'ok': ok, 'body': body}
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise PipeError(f'product command {name} did not answer within {timeout:g} s')
            if select.select([self.reader], [], [], min(.2, remaining))[0]:
                try:
                    chunk = os.read(self.reader, 65536)
                except OSError as exc:
                    raise PipeError('scripting reply could not be read: '+exc.strerror) from None
                if chunk:
                    data += chunk
                    if len(data) > MAX_REPLY:
                        raise PipeError('scripting reply exceeds 4 MB')
                else:
                    time.sleep(.03)
