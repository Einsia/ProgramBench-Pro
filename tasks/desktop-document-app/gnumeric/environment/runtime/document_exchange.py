"""Document exchange operations anchored to directory descriptors."""
from contextlib import ExitStack
import os
from pathlib import Path
import stat

import blackbox_runtime as runtime


def open_directory(path, parent=None):
    """Return a caller-owned fd after checking every directory component."""
    manager = runtime.open_directory(path) if parent is None else runtime.open_relative(parent, path, directory=True)
    try:
        with manager as fd:
            return os.dup(fd)
    except OSError as exc:
        raise ValueError('the exchange directory is not a plain accessible folder') from exc


def _writable_for_removal(fd):
    """Restore this account's directory permissions before a local reset."""
    runtime.set_metadata(fd, mode=0o700)
    for name, info in runtime.list_directory(fd):
        if stat.S_ISDIR(info.st_mode):
            with runtime.open_relative(fd, name, directory=True) as child:
                _writable_for_removal(child)


def prepare(rt, clear):
    """Keep the exchange container private to its owner and prepare writable areas."""
    owner = {'uid': 0, 'gid': 0} if os.geteuid() == 0 else {}
    application = {'uid': rt.account.pw_uid, 'gid': rt.account.pw_gid}
    with runtime.open_directory(rt.files.parent, create=True) as parent:
        with runtime.owned_directory(parent, rt.files.name, mode=0o711, **owner) as root:
            for name in rt.areas:
                if clear:
                    if os.geteuid() != 0:
                        try:
                            with runtime.open_relative(root, name, directory=True) as previous:
                                _writable_for_removal(previous)
                        except (FileNotFoundError, NotADirectoryError):
                            pass
                    runtime.remove_entry(root, name, missing_ok=True)
                with runtime.owned_directory(root, name, mode=0o755, **application):
                    pass


def write(rt, area, relative, content, *, read_only=False, timestamp):
    """Create parents through fds and install a complete single regular document."""
    components = relative.split('/')
    if not components or any(not p or p in ('.', '..') for p in components):
        raise ValueError('invalid relative document name')
    application = {'uid': rt.account.pw_uid, 'gid': rt.account.pw_gid}
    protected = {'uid': 0, 'gid': 0} if os.geteuid() == 0 else {}
    with ExitStack() as stack:
        directory = stack.enter_context(runtime.open_directory(rt.areas[area]))
        locked = None
        if read_only:
            locked = stack.enter_context(runtime.owned_directory(directory, 'read-only', mode=0o700, **protected))
            directory = locked
        try:
            for component in components[:-1]:
                directory = stack.enter_context(runtime.owned_directory(directory, component, mode=0o755, **application))
            name = components[-1]
            try:
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('the destination must be one regular file')
            except FileNotFoundError:
                pass
            runtime.atomic_write(directory, name, content, mode=0o444 if read_only else 0o644,
                                 **(protected if read_only else application))
            with runtime.open_relative(directory, name) as fd:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('the document changed during upload')
                runtime.set_metadata(fd, ns=(int(timestamp*1_000_000_000),)*2)
        finally:
            if locked is not None:
                runtime.set_metadata(locked, mode=0o555)


def read(rt, area, relative, *, limit, read_only=False):
    """Read a bounded single regular document without following links."""
    path = 'read-only/' + relative if read_only else relative
    with runtime.open_directory(rt.areas[area]) as root:
        return runtime.read_file(root, path, limit=limit)


def flat_listing(rt, area, *, limit):
    """List ordinary exchange documents, including the protected subdirectory."""
    result = []
    with runtime.open_directory(rt.areas[area]) as root:
        groups = [(False, runtime.list_directory(root))]
        try:
            groups.append((True, runtime.list_directory(root, 'read-only')))
        except (FileNotFoundError, NotADirectoryError):
            pass
        for locked, entries in groups:
            for name, info in entries:
                if len(result) >= limit:
                    break
                if not name.startswith('.') and stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    path = rt.areas[area] / ('read-only' if locked else '') / name
                    result.append({'name': name, 'size': info.st_size, 'path': str(path), 'read_only': locked})
    return {'area': area, 'files': result}


def walk(parent, *, limit, depth_limit):
    """Return relative regular files, subdirectories and truncation from one fd tree."""
    files, folders = [], []
    truncated = False

    def visit(fd, prefix, depth):
        nonlocal truncated
        for name, info in runtime.list_directory(fd):
            if name.startswith('.'):
                continue
            if len(files) >= limit:
                truncated = True
                return
            relative = prefix + name
            if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                files.append((relative, info))
            elif stat.S_ISDIR(info.st_mode) and depth < depth_limit:
                with runtime.open_relative(fd, name, directory=True) as child:
                    folders.append(relative)
                    visit(child, relative+'/', depth+1)
    with runtime.open_directory(parent) as fd:
        visit(fd, '', 0)
    return files, folders, truncated
