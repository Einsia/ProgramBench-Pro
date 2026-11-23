"""File exchange through directory descriptors anchored by the runtime."""
from contextlib import contextmanager, ExitStack
import base64
import ctypes
import hashlib
import os
from pathlib import Path
import stat
import blackbox_runtime as runtime


@contextmanager
def directory(root, parts=(), *, create=False, uid=None, gid=None, mode=0o755):
    with ExitStack() as stack:
        fd = stack.enter_context(runtime.open_directory(root))
        for part in parts:
            if not part or part in ('.', '..') or '/' in part:
                raise ValueError('invalid directory component')
            try:
                child = stack.enter_context(runtime.open_relative(fd, part, directory=True))
            except FileNotFoundError:
                if not create:
                    raise
                child = stack.enter_context(runtime.owned_directory(fd, part, uid=uid, gid=gid, mode=mode))
            fd = child
        yield fd


def read(parent, name, *, limit, uid=None):
    with runtime.open_relative(parent, name) as fd:
        info = os.fstat(fd)
        # Native file-manager hardlinks remain observable only for application-owned files.
        links = max(1, info.st_nlink) if uid is not None and info.st_uid == uid else 1
        return runtime.read_bounded(fd, limit=limit, max_links=links)


def snapshot(root, parts, action, *, origin, max_read, max_hash, max_entries,
             uid=None, excluded=(), casefold=True, outside='[outside the workspace]'):
    root = Path(root)
    def logical(rel):
        return origin + ('/' + '/'.join(rel) if rel else '')
    def describe(fd, name, rel, info=None):
        info = info or os.stat(name, dir_fd=fd, follow_symlinks=False)
        mode = info.st_mode
        kind = ('symlink' if stat.S_ISLNK(mode) else 'directory' if stat.S_ISDIR(mode)
                else 'file' if stat.S_ISREG(mode) else 'other')
        row = {'path': logical(rel), 'name': rel[-1] if rel else origin, 'type': kind,
               'size': info.st_size if kind == 'file' else 0, 'mode': stat.S_IMODE(mode)}
        if kind == 'file':
            row['sha256'] = (hashlib.sha256(read(fd, name, limit=max_hash, uid=uid)).hexdigest()
                             if info.st_size <= max_hash else None)
        elif kind == 'symlink':
            target = os.readlink(name, dir_fd=fd)
            if target.startswith('/'):
                try:
                    target = logical(Path(target).relative_to(root).parts)
                except ValueError:
                    target = outside
            row['target'] = target
        return row
    with directory(root) as root_fd:
        if action == 'stat':
            if not parts:
                return describe(root_fd, '.', (), os.fstat(root_fd))
            with directory(root_fd, parts[:-1]) as fd:
                return describe(fd, parts[-1], tuple(parts))
        if action == 'read':
            content = read(root_fd, '/'.join(parts), limit=max_read, uid=uid)
            return {'path': logical(parts), 'size': len(content), 'text': content.decode('utf-8', 'replace'),
                    'body_base64': base64.b64encode(content).decode()}
        if action not in ('list', 'tree'):
            raise ValueError('action must be list, tree, stat or read')
        entries = []
        def visit(fd, rel):
            rows = runtime.list_directory(fd)
            rows.sort(key=lambda item: (item[0].casefold(), item[0]) if casefold else item[0])
            for name, info in rows:
                if name in excluded:
                    continue
                if len(entries) >= max_entries:
                    raise ValueError('the directory tree exceeds the entry limit')
                child_rel = tuple(rel) + (name,)
                entries.append(describe(fd, name, child_rel, info))
                if action == 'tree' and stat.S_ISDIR(info.st_mode):
                    with runtime.open_relative(fd, name, directory=True) as child:
                        visit(child, child_rel)
        with directory(root_fd, parts) as fd:
            visit(fd, parts)
        if action == 'tree':
            entries.sort(key=lambda row: row['path'])
        return {'path': logical(parts), 'entries': entries}


def link_metadata(parent, name, *, uid=None, gid=None, stamp=None):
    """Set metadata on an opened link itself, even if its directory entry changes."""
    fd = os.open(name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    try:
        if not stat.S_ISLNK(os.fstat(fd).st_mode):
            raise ValueError('the link changed during setup')
        libc = ctypes.CDLL(None, use_errno=True)
        flags = 0x1000 | 0x100  # AT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW
        if uid is not None and os.geteuid() == 0:
            if libc.fchownat(fd, b'', uid, gid if gid is not None else -1, flags) != 0:
                raise OSError(ctypes.get_errno(), 'could not set link ownership')
        if stamp is not None:
            class Timespec(ctypes.Structure):
                _fields_ = [('seconds', ctypes.c_long), ('nanoseconds', ctypes.c_long)]
            seconds, nanoseconds = divmod(int(stamp * 1e9), 1_000_000_000)
            times = (Timespec * 2)(Timespec(seconds, nanoseconds), Timespec(seconds, nanoseconds))
            if libc.utimensat(fd, b'', times, flags) != 0:
                raise OSError(ctypes.get_errno(), 'could not set link modification time')
    finally:
        os.close(fd)


def place(root, entries, components, *, uid=None, gid=None, replace_symlinks=False):
    with directory(root) as root_fd:
        for name, value in entries.items():
            parts = components(name)
            if not parts:
                raise ValueError('a file path must be below the exchange directory')
            with directory(root_fd, parts[:-1], create=True, uid=uid, gid=gid) as parent:
                leaf = parts[-1]
                try:
                    info = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    info = None
                link = isinstance(value, dict) and 'symlink' in value
                if info and stat.S_ISLNK(info.st_mode) and not (link and replace_symlinks):
                    raise ValueError('cannot replace a symbolic link')
                stamp = value.get('mtime') if isinstance(value, dict) else None
                if link:
                    if info is not None:
                        runtime.unlink_entry(parent, leaf)
                    os.symlink(value['symlink'], leaf, dir_fd=parent)
                    link_metadata(parent, leaf, uid=uid, gid=gid, stamp=stamp)
                elif value is None or (isinstance(value, dict) and value.get('dir')):
                    with directory(parent, [leaf], create=True, uid=uid, gid=gid) as child:
                        if stamp is not None:
                            runtime.set_metadata(child, ns=(int(stamp * 1e9), int(stamp * 1e9)))
                else:
                    if info and stat.S_ISDIR(info.st_mode):
                        raise ValueError('a directory is in the way of the file')
                    content = (value.encode('utf-8') if isinstance(value, str) else
                               value['text'].encode('utf-8') if 'text' in value else
                               base64.b64decode(value['base64'], validate=True))
                    mode = value.get('mode', 0o644) if isinstance(value, dict) else 0o644
                    if isinstance(mode, str):
                        mode = int(mode, 8)
                    runtime.atomic_write(parent, leaf, content, uid=uid, gid=gid, mode=mode)
                    if stamp is not None:
                        with runtime.open_relative(parent, leaf) as file_fd:
                            info = os.fstat(file_fd)
                            if info.st_nlink != 1 or (uid is not None and info.st_uid != uid):
                                raise ValueError('the file changed during setup')
                            runtime.set_metadata(file_fd, ns=(int(stamp * 1e9), int(stamp * 1e9)))
