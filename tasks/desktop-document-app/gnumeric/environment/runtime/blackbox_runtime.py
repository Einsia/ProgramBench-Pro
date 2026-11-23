"""Shared black-box runtime helpers.

The same runtime drives the reference for exploration and your application for
self-tests and evaluation. Each instance uses one solution directory. This
module provides:

- the standard command line (defaults are the reference container's values);
- the product process: start.sh as one process group, optionally as another
  user, with an allow-listed environment, private instance directories and a
  bounded output log;
- surface-generic readiness probes;
- validation of requests against the machine-readable help (blackbox-v2);
- path redaction, the RPC audit log and the listening Unix socket.

The product-specific RPC server and operations stay in the task's broker.
"""
import argparse
from contextlib import contextmanager
import errno
import http.client
import json
import math
import os
from pathlib import Path
import pwd
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import threading
import time
import urllib.error
import urllib.request

PROTOCOL = 'blackbox-v2'
KIT_VERSION = '1.0.0'
ENV_ALLOW = ('PATH', 'LANG', 'LC_ALL', 'TZ', 'NODE_PATH', 'PLAYWRIGHT_BROWSERS_PATH')
LOG_HEAD = 2_000_000
LOG_TAIL = 2_000_000
KINDS = ('gui', 'observe', 'lifecycle', 'http', 'files', 'info')
TYPES = {'string': str, 'integer': int, 'number': (int, float), 'boolean': bool, 'object': dict, 'array': list}


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON object key: ' + key)
        value[key] = item
    return value


def _finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError('JSON numbers must be finite')
    return parsed


def _reject_constant(value):
    raise ValueError('non-finite JSON value is not allowed: ' + value)


def strict_json_loads(document):
    """Parse JSON text/bytes, rejecting duplicate keys and non-finite numbers at any depth."""
    return json.loads(document, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant,
                      parse_float=_finite_float)


def options(parser=None, **defaults):
    """Standard runtime options. Defaults are the reference container's values."""
    values = dict(solution='/app/solution', state='/reference/state', socket='/blackbox/reference.sock',
                  socket_mode='0666', log_dir='/reference', user='', work='/reference/work', port=3000,
                  ready_timeout=75.0)
    values.update(defaults)
    p = parser or argparse.ArgumentParser(description='Black-box runtime for one solution directory.')
    p.add_argument('--solution', default=values['solution'], help='solution directory containing start.sh')
    p.add_argument('--state', default=values['state'],
                   help='instance root: DATA_DIR and the private HOME, TMPDIR and XDG directories live inside')
    p.add_argument('--socket', default=values['socket'], help='Unix socket of the RPC interface')
    p.add_argument('--socket-mode', default=values['socket_mode'], help='octal permissions of the socket')
    p.add_argument('--log-dir', default=values['log_dir'], help='bounded product.log and rpc-audit.jsonl')
    p.add_argument('--user', default=values['user'], help='run the product as this user (the runtime must be root)')
    p.add_argument('--work', default=values['work'], help='private runtime scratch (browser downloads, sessions)')
    p.add_argument('--port', type=int, default=values['port'], help='PORT given to the product')
    p.add_argument('--ready-timeout', type=float, default=values['ready_timeout'],
                   help='seconds the product has to become ready after a start')
    return p


def layout(state):
    """Private directories of one product instance; reset deletes them all."""
    root = Path(state)
    return {'DATA_DIR': root / 'data', 'HOME': root / 'home', 'TMPDIR': root / 'tmp',
            'XDG_CACHE_HOME': root / 'cache', 'XDG_CONFIG_HOME': root / 'config'}


def _entry_name(name):
    name = os.fspath(name)
    if not isinstance(name, str) or name in ('', '.', '..') or '/' in name or '\x00' in name:
        raise ValueError('expected one directory entry name')
    return name


@contextmanager
def open_directory(directory, *, create=False):
    """Yield an owned directory descriptor; close it when the context ends.

    Accept a path or an already open directory descriptor (which is duplicated).
    Every path component is opened with O_DIRECTORY | O_NOFOLLOW. Parent links
    and '..' components are refused. With create=True, missing components are
    created with mode 0700; existing components keep their owner and mode.
    """
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    if isinstance(directory, int):
        fd = os.dup(directory)
    else:
        path = Path(directory)
        if '..' in path.parts:
            raise ValueError('directory paths must not contain parent components')
        fd = os.open('/' if path.is_absolute() else '.', flags)
        try:
            for part in path.parts:
                if part in ('/', '.'):
                    continue
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = child
        except BaseException:
            os.close(fd)
            raise
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise NotADirectoryError('expected a directory descriptor')
        yield fd
    finally:
        os.close(fd)


@contextmanager
def owned_directory(parent, name, *, uid=None, gid=None, mode=0o700):
    """Create/open one real child directory, set its owner/mode, and yield its fd.

    parent is a directory path or fd; name is a single entry name. Existing
    links and non-directory entries are unlinked and replaced, never followed.
    Ownership and permissions are applied only to the opened descriptor. Pass
    uid/gid to transfer ownership when running as root; other users keep their
    current ownership. The descriptor stays open until the context ends: use
    it for nested owned_directory/write_owned_file calls instead of reopening
    a writable path. Concurrent replacement may fail the operation safely.
    """
    name = _entry_name(name)
    with open_directory(parent) as parent_fd:
        for _ in range(32):
            try:
                os.mkdir(name, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            try:
                fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=parent_fd)
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    continue
                if exc.errno not in (errno.ELOOP, errno.ENOTDIR):
                    raise
                try:
                    os.unlink(name, dir_fd=parent_fd)
                except (FileNotFoundError, IsADirectoryError):
                    pass
                continue
            break
        else:
            raise RuntimeError('directory entry changed during setup')
        try:
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                raise NotADirectoryError(name)
            if os.geteuid() == 0 and (uid is not None or gid is not None):
                os.fchown(fd, uid if uid is not None else -1, gid if gid is not None else -1)
            os.fchmod(fd, mode)
            yield fd
        finally:
            os.close(fd)


def write_owned_file(parent, name, data, *, uid=None, gid=None, mode=0o600, replace=False):
    """Write a new regular file and transfer its ownership through its fd.

    parent is a real directory path or fd and name is one entry name. data is
    bytes or UTF-8 text. Creation uses O_CREAT | O_EXCL | O_NOFOLLOW; an existing
    entry is refused unless replace=True, which unlinks that entry first (it
    never opens its contents and refuses directories). The file stays private
    while being written. fchmod/fchown set the final permissions and ownership
    before closing it. Non-root callers retain their current ownership.
    """
    name = _entry_name(name)
    payload = data.encode('utf-8') if isinstance(data, str) else bytes(data)
    with open_directory(parent) as parent_fd:
        if replace:
            try:
                os.unlink(name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=parent_fd)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            if os.geteuid() == 0 and (uid is not None or gid is not None):
                os.fchown(stream.fileno(), uid if uid is not None else -1, gid if gid is not None else -1)


def _relative_parts(relative):
    value = os.fspath(relative)
    if not isinstance(value, str) or os.path.isabs(value) or '\x00' in value or '..' in value.split('/'):
        raise ValueError('expected a relative path without parent components')
    return tuple(part for part in value.split('/') if part not in ('', '.'))


@contextmanager
def open_relative(parent, relative, *, directory=False):
    """Open an existing relative path below a directory path/fd and yield its fd.

    Absolute paths and parent components are refused. Every component uses
    O_NOFOLLOW and intermediate components use O_DIRECTORY. The final entry is
    opened read-only and nonblocking; directory=True also requires O_DIRECTORY
    and permits '.' to refer to parent. No file is created or truncated. The
    context closes the returned descriptor. Check its type before reading.
    """
    parts = _relative_parts(relative)
    with open_directory(parent) as root_fd:
        if not parts:
            if not directory:
                raise ValueError('expected a file path')
            yield root_fd
            return
        with open_directory(root_fd) as initial:
            fd = os.dup(initial)
            try:
                for index, part in enumerate(parts):
                    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                    if directory or index < len(parts) - 1:
                        flags |= os.O_DIRECTORY
                    child = os.open(part, flags, dir_fd=fd)
                    os.close(fd)
                    fd = child
                yield fd
            finally:
                os.close(fd)


def read_bounded(fd, *, limit, max_links=1):
    """Read at most limit bytes from an open regular file's current position.

    Validate the opened entry's type, link count (1..max_links), and complete
    size before reading. Also enforce the byte limit while reading in case the
    file grows. The caller retains ownership of fd. Special files are refused.
    """
    if type(limit) is not int or limit < 0 or type(max_links) is not int or max_links < 1:
        raise ValueError('limit and max_links must be nonnegative/positive integers')
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_nlink <= max_links:
        raise ValueError('expected a regular file with an allowed link count')
    if info.st_size > limit:
        raise ValueError('file exceeds the size limit')
    data = bytearray()
    while True:
        chunk = os.read(fd, min(1024 * 1024, limit + 1 - len(data)))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError('file exceeds the size limit')


def read_file(parent, relative, *, limit, max_links=1):
    """Open without following links, validate, and return bounded regular-file bytes."""
    with open_relative(parent, relative) as fd:
        return read_bounded(fd, limit=limit, max_links=max_links)


def list_directory(parent, relative='.'):
    """Return sorted (name, lstat_result) entries from an opened directory.

    Entry metadata never follows links. Entries removed during enumeration are
    skipped; callers must still validate the descriptor when opening an entry.
    """
    with open_relative(parent, relative, directory=True) as fd:
        entries = []
        for name in sorted(os.listdir(fd)):
            try:
                entries.append((name, os.stat(name, dir_fd=fd, follow_symlinks=False)))
            except FileNotFoundError:
                pass
        return entries


@contextmanager
def _relative_parent(parent, relative):
    parts = _relative_parts(relative)
    if not parts:
        raise ValueError('expected a child entry path')
    with open_relative(parent, '/'.join(parts[:-1]) or '.', directory=True) as fd:
        yield fd, parts[-1]


def unlink_entry(parent, relative, *, missing_ok=False):
    """Unlink one non-directory entry below parent, without following any links."""
    with _relative_parent(parent, relative) as (fd, name):
        try:
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            if not missing_ok:
                raise


def remove_entry(parent, relative, *, missing_ok=False):
    """Remove a child entry or directory tree through its parent descriptor.

    Intermediate links are refused. A final link is unlinked, never traversed.
    Directory contents are opened with O_DIRECTORY | O_NOFOLLOW and removed
    relative to those descriptors. Removal errors propagate.
    """
    with _relative_parent(parent, relative) as (fd, name):
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                try:
                    for entry in os.listdir(child):
                        remove_entry(child, entry, missing_ok=True)
                    os.rmdir(name, dir_fd=fd)
                finally:
                    os.close(child)
            else:
                os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            if not missing_ok:
                raise


def set_metadata(fd, *, mode=None, ns=None, uid=None, gid=None):
    """Set owner, mode and/or (atime_ns, mtime_ns) on a regular-file/directory fd.

    No path is reopened. Ownership is changed only by root; other callers keep
    their current ownership. The caller retains the descriptor.
    """
    if not (stat.S_ISREG(os.fstat(fd).st_mode) or stat.S_ISDIR(os.fstat(fd).st_mode)):
        raise ValueError('metadata changes require a regular file or directory descriptor')
    if os.geteuid() == 0 and (uid is not None or gid is not None):
        os.fchown(fd, uid if uid is not None else -1, gid if gid is not None else -1)
    if mode is not None:
        os.fchmod(fd, mode)
    if ns is not None:
        os.utime(fd, ns=ns)


def atomic_write(parent, relative, data, *, uid=None, gid=None, mode=0o600):
    """Write bytes/UTF-8 text to a new temporary file and atomically replace a child.

    The temporary entry is in the destination directory, created exclusively
    with O_NOFOLLOW and mode 0600. rename uses directory descriptors for both
    names. Only after the complete file is installed is its fd assigned the
    requested owner/mode. Destination links are replaced as entries, never
    followed; destination directories are refused. Temporary entries are cleaned
    on failure. A concurrently changed directory may make the operation fail.
    """
    payload = data.encode('utf-8') if isinstance(data, str) else bytes(data)
    with _relative_parent(parent, relative) as (fd, name):
        pending = '.pending-' + secrets.token_hex(16)
        opened = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=fd)
        try:
            with os.fdopen(opened, 'wb') as stream:
                stream.write(payload)
                stream.flush()
                os.rename(pending, name, src_dir_fd=fd, dst_dir_fd=fd)
                set_metadata(stream.fileno(), uid=uid, gid=gid, mode=mode)
        finally:
            try:
                os.unlink(pending, dir_fd=fd)
            except FileNotFoundError:
                pass


def copy_file(source_parent, source, destination_parent, destination, *, limit, uid=None, gid=None, mode=0o600):
    """Copy a bounded regular file between two directory paths/descriptors.

    Source traversal, type/link/size checks and destination replacement all use
    descriptor helpers. The complete source is read before atomically installing
    the destination. Use this for either direction of an exchange operation.
    """
    data = read_file(source_parent, source, limit=limit)
    atomic_write(destination_parent, destination, data, uid=uid, gid=gid, mode=mode)
    return len(data)


class BoundedLog:
    """Product output: the first `head` bytes, then a rotating tail of at most two `tail`-byte files."""

    def __init__(self, directory, name='product.log', head=LOG_HEAD, tail=LOG_TAIL):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.head_path = self.directory / name
        self.tail_path = self.directory / (name + '.tail')
        self.previous_path = self.directory / (name + '.tail.1')
        self.head, self.tail = head, tail
        self.head_written = self.head_path.stat().st_size if self.head_path.exists() else 0
        self.tail_written = self.tail_path.stat().st_size if self.tail_path.exists() else 0
        self.dropped = 0
        self.lock = threading.Lock()
        self.threads = []

    def note(self, text):
        self.write(('[runtime] ' + text + '\n').encode())

    def write(self, data):
        with self.lock:
            if self.head_written < self.head:
                part = data[:self.head - self.head_written]
                with self.head_path.open('ab') as f:
                    f.write(part)
                self.head_written += len(part)
                data = data[len(part):]
            if not data:
                return
            if self.tail_written + len(data) > self.tail:
                if self.previous_path.exists():
                    self.dropped += self.previous_path.stat().st_size
                if self.tail_path.exists():
                    self.tail_path.replace(self.previous_path)
                marker = f'[... {self.dropped} earlier bytes of output dropped ...]\n'.encode()
                self.tail_path.write_bytes(marker)
                self.tail_written = len(marker)
            data = data[-self.tail:]
            with self.tail_path.open('ab') as f:
                f.write(data)
            self.tail_written += len(data)

    def pump(self, fd):
        def run():
            with os.fdopen(fd, 'rb', buffering=0) as stream:
                while True:
                    try:
                        chunk = stream.read(65536)
                    except OSError:
                        return
                    if not chunk:
                        return
                    self.write(chunk)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.threads.append(thread)

    def wait(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        for thread in self.threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        self.threads = [t for t in self.threads if t.is_alive()]


class Product:
    """The solution's start.sh as one process group with a private instance layout."""

    def __init__(self, config, *, log, env=None, directories=None, host='127.0.0.1'):
        self.config = config
        self.log = log
        self.extra = dict(env or {})
        self.directories = directories or layout(config.state)
        self.host = host
        self.proc = None
        self.ready = False
        self.detail = 'not started'
        self.starts = 0

    @property
    def solution(self):
        return Path(self.config.solution)

    def account(self):
        return pwd.getpwnam(self.config.user) if self.config.user else pwd.getpwuid(os.geteuid())

    def switching(self):
        return bool(self.config.user) and os.geteuid() == 0 and self.account().pw_uid != 0

    def environment(self):
        account = self.account()
        env = {k: os.environ[k] for k in ENV_ALLOW if k in os.environ}
        env.update(HOST=self.host, PORT=str(self.config.port), USER=account.pw_name, LOGNAME=account.pw_name,
                   SHELL='/bin/bash', PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
        env.update({key: str(path) for key, path in self.directories.items()})
        env.update(self.extra)
        return env

    def prepare(self, fresh):
        root = Path(self.config.state)
        account = self.account()
        if os.geteuid() != 0:
            if fresh and root.exists():
                shutil.rmtree(root)
            for path in [root, *self.directories.values()]:
                path.mkdir(parents=True, exist_ok=True)
                path.chmod(0o700)
            return

        # The instance container belongs to the runtime; only its children are
        # handed to the application. All changes stay attached to open fds.
        with open_directory(root.parent, create=True) as parent_fd:
            with owned_directory(parent_fd, root.name, uid=0, gid=0, mode=0o711) as root_fd:
                if fresh:
                    for name in os.listdir(root_fd):
                        remove_entry(root_fd, name, missing_ok=True)

                def prepare_child(parent, parts):
                    with owned_directory(parent, parts[0], uid=account.pw_uid, gid=account.pw_gid) as fd:
                        if len(parts) > 1:
                            prepare_child(fd, parts[1:])

                for path in self.directories.values():
                    relative = Path(path).relative_to(root)
                    if not relative.parts or '..' in relative.parts:
                        raise ValueError('instance directories must be below the instance root')
                    prepare_child(root_fd, relative.parts)

    def start(self, fresh=False):
        """Launch start.sh; returns False when it could not even be executed."""
        self.stop()
        self.prepare(fresh)
        self.ready, self.starts = False, self.starts + 1
        script = self.solution / 'start.sh'
        if not script.is_file():
            self.detail = 'start.sh does not exist in the solution directory'
            self.log.note(self.detail)
            return False
        kwargs = {}
        if self.switching():
            account = self.account()
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        read, write = os.pipe()
        try:
            self.proc = subprocess.Popen([str(script)], cwd=str(self.solution), env=self.environment(),
                                         stdin=subprocess.DEVNULL, stdout=write, stderr=write,
                                         start_new_session=True, **kwargs)
        except OSError as exc:
            os.close(read)
            self.proc = None
            self.detail = f'start.sh could not be executed ({type(exc).__name__}: {exc.strerror or exc})'
            self.log.note(self.detail)
            return False
        finally:
            os.close(write)
        self.log.pump(read)
        self.log.note(f'start {self.starts}: pid {self.proc.pid}')
        self.detail = 'starting'
        return True

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self, grace=10.0):
        proc, self.ready = self.proc, False
        if proc is None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(grace)
        except subprocess.TimeoutExpired:
            pass
        # The launcher may have exited while children remain in its process group.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            pass
        self.log.wait(2.0)

    def status(self):
        running = self.running()
        code = None if self.proc is None or running else self.proc.returncode
        detail = self.detail
        if not running and self.proc is not None and self.ready:
            detail = f'the application exited with status {code}'
        return {'ready': bool(self.ready and running), 'running': running, 'exit_code': code, 'detail': detail}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def wait_http(product, *, path='/', deadline=None):
    """Web readiness: GET path on PORT answers with an HTTP status below 500."""
    limit = product.config.ready_timeout if deadline is None else deadline
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    url = f'http://127.0.0.1:{product.config.port}{path}'

    def ready():
        try:
            with opener.open(url, timeout=2) as response:
                return response.status < 500
        except urllib.error.HTTPError as exc:
            return exc.code < 500
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
            return False
    return wait_until(product, ready, deadline=limit,
                      failure=f'the application did not answer HTTP on PORT within {limit:g} s')


def wait_until(product, predicate, *, deadline=None, interval=0.25, failure='the application did not become ready'):
    """Generic readiness loop for desktop and terminal runtimes; stores the outcome on the product."""
    limit = product.config.ready_timeout if deadline is None else deadline
    end = time.monotonic() + limit
    while True:
        if not product.running():
            code = None if product.proc is None else product.proc.returncode
            if product.proc is not None:
                product.detail = f'start.sh exited with status {code} before the application was ready'
            product.ready = False
            return False
        try:
            if predicate():
                product.ready, product.detail = True, 'ready'
                return True
        except Exception:
            pass
        if time.monotonic() >= end:
            product.ready, product.detail = False, failure
            return False
        time.sleep(interval)


def validate(operations, request):
    """Check one request against the help's operation specs; returns the operation name."""
    if not isinstance(request, dict):
        raise ValueError('RPC request must be a JSON object')
    op = request.get('op', 'help')
    if not isinstance(op, str) or op not in operations:
        raise ValueError('Unknown operation; use help')
    fields = operations[op].get('fields', {})
    unknown = sorted(set(request) - {'op'} - set(fields))
    if unknown:
        raise ValueError(f'Unknown field for {op}: {", ".join(unknown)}; see help')
    for name, spec in fields.items():
        if name not in request:
            if spec.get('required'):
                raise ValueError(f'{op} requires {name}')
            continue
        value = request[name]
        kinds = spec.get('type')
        if kinds:
            allowed = kinds if isinstance(kinds, list) else [kinds]
            if not any(isinstance(value, TYPES[k]) and not (isinstance(value, bool) and k in ('integer', 'number'))
                       for k in allowed):
                raise ValueError(f'{op}.{name} must be {" or ".join(allowed)}')
        if 'enum' in spec and value not in spec['enum']:
            raise ValueError(f'{op}.{name} must be one of {", ".join(map(str, spec["enum"]))}')
    return op


def check_operations(operations):
    """Check a broker's help specifications during setup."""
    for op, spec in operations.items():
        assert spec.get('kind') in KINDS, op
        assert isinstance(spec.get('summary'), str) and spec['summary'], op
        for name, field in spec.get('fields', {}).items():
            kinds = field.get('type')
            assert kinds and all(k in TYPES for k in (kinds if isinstance(kinds, list) else [kinds])), (op, name)
            assert isinstance(field.get('description'), str) and field['description'], (op, name)
    return operations


def redactor(*paths):
    """Replace private filesystem roots in error details."""
    roots = sorted({str(Path(p)) for p in paths if p and str(p) != '/'}, key=len, reverse=True)

    def redact(text):
        text = str(text)
        for root in roots:
            text = text.replace(root, '[private]')
        return text
    return redact


class Audit:
    """RPC audit log (operation, status, duration; never bodies); rotated at `limit` bytes."""

    def __init__(self, path, limit=10_000_000):
        self.path = Path(path)
        self.limit = limit
        self.lock = threading.Lock()

    def record(self, op, status, seconds):
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size > self.limit:
                self.path.replace(self.path.with_name(self.path.stem + '.previous.jsonl'))
            with self.path.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'time': time.time(), 'op': op, 'status': status,
                                    'seconds': round(seconds, 3)}) + '\n')


def listen(path, mode):
    """Bind the RPC socket with its final permissions (no world-accessible window)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    previous = os.umask(0o177)
    try:
        sock.bind(str(target))
    finally:
        os.umask(previous)
    os.chmod(target, int(str(mode), 8))
    sock.listen(128)
    return sock


def exit_on_sigterm():
    """Turn SIGTERM into SystemExit so a runtime's cleanup (stopping the product, closing a desktop session) runs.

    Call it before serving. uvicorn restores the previous handler after its graceful shutdown and raises the
    signal again; with the default handler the process would end before its finally blocks."""
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)


def help_document(product, surface, operations, **extra):
    """The machine-readable help every runtime returns for op help."""
    return {'protocol': PROTOCOL, 'runtime_version': KIT_VERSION, 'product': product, 'surface': surface,
            'operations': operations, **extra}
