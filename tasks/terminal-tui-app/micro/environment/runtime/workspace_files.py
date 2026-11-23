"""Descriptor-based workspace access using the runtime's confined file helpers."""
from contextlib import contextmanager, ExitStack
import base64
import hashlib
import os
import stat

import blackbox_runtime as runtime


@contextmanager
def directory(product, root, parts=(), *, create=False):
    """Hold each directory descriptor until the operation using it finishes."""
    account = product.account()
    with ExitStack() as stack:
        fd = stack.enter_context(runtime.open_directory(root))
        for name in parts:
            if name in ('', '.', '..') or '/' in name:
                raise ValueError('invalid directory component')
            created = False
            if create:
                try:
                    os.mkdir(name, 0o700, dir_fd=fd)
                    created = True
                except FileExistsError:
                    pass
            child = stack.enter_context(runtime.open_relative(fd, name, directory=True))
            if created:
                runtime.set_metadata(child, mode=0o755, uid=account.pw_uid, gid=account.pw_gid)
            fd = child
        yield fd


def write(product, parent, name, data, *, mode=0o644, mtime=None):
    """Atomically install a regular file and set metadata through its descriptor."""
    try:
        existing = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        existing = None
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise ValueError('cannot replace a symlink or a directory: ' + name)
    account = product.account()
    runtime.atomic_write(parent, name, data, mode=0o600, uid=account.pw_uid, gid=account.pw_gid)
    with runtime.open_relative(parent, name) as fd:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('file changed during placement')
        ns = (int(mtime * 1_000_000_000),) * 2 if mtime is not None else None
        runtime.set_metadata(fd, mode=mode, ns=ns, uid=account.pw_uid, gid=account.pw_gid)


def _name(fd, name, aliases):
    choices = [name] + [name.replace(shown, real) for shown, real in aliases if shown in name]
    for choice in choices:
        if choice in ('', '.', '..') or '/' in choice:
            raise ValueError('invalid path component')
        try:
            os.stat(choice, dir_fd=fd, follow_symlinks=False)
            return choice
        except FileNotFoundError:
            pass
    return name


def inspect(root, parts, action, *, origin, read_limit, hash_limit, tree_limit, redact=str, aliases=()):
    """Observe a workspace without following links during traversal or reads."""
    root_text = os.fspath(root)

    def shown(parts):
        return origin + ('/' + '/'.join(parts) if parts else '')

    def entry(fd, name, parts, info):
        mode = info.st_mode
        kind = ('symlink' if stat.S_ISLNK(mode) else 'directory' if stat.S_ISDIR(mode)
                else 'file' if stat.S_ISREG(mode) else 'other')
        result = dict(path=shown(parts), name=name if parts else origin, type=kind,
                      size=info.st_size if kind == 'file' else 0, mode=stat.S_IMODE(mode))
        if kind == 'file':
            result['sha256'] = (hashlib.sha256(runtime.read_file(fd, name, limit=hash_limit)).hexdigest()
                                if info.st_size <= hash_limit else None)
        elif kind == 'symlink':
            target = os.readlink(name, dir_fd=fd)
            if target.startswith('/'):
                target = origin + target[len(root_text):] if target == root_text or target.startswith(root_text+'/') else '[outside the workspace]'
            result['target'] = target
        return result

    def clean(item):
        return {key: redact(value) if key in ('path', 'name', 'target') else value for key, value in item.items()}

    with ExitStack() as stack:
        fd = stack.enter_context(runtime.open_directory(root))
        actual = []
        for component in parts[:-1]:
            name = _name(fd, component, aliases)
            fd = stack.enter_context(runtime.open_relative(fd, name, directory=True))
            actual.append(name)
        name = _name(fd, parts[-1], aliases) if parts else None
        if name is not None:
            actual.append(name)
        info = os.stat(name, dir_fd=fd, follow_symlinks=False) if name is not None else os.fstat(fd)
        if action == 'stat':
            return clean(entry(fd, name, actual, info))
        if action == 'read':
            if name is None:
                raise ValueError('read needs a file')
            content = runtime.read_file(fd, name, limit=read_limit)
            return {'path': redact(shown(actual)), 'size': len(content),
                    'text': content.decode('utf-8', 'replace'), 'body_base64': base64.b64encode(content).decode()}
        if action not in ('list', 'tree'):
            raise ValueError('action must be list, tree, stat or read')
        if name is not None:
            fd = stack.enter_context(runtime.open_relative(fd, name, directory=True))
        found = []

        def visit(parent, prefix):
            entries = sorted(runtime.list_directory(parent), key=lambda item: (item[0].casefold(), item[0]))
            for leaf, metadata in entries:
                rel = prefix + [leaf]
                found.append((rel, entry(parent, leaf, rel, metadata)))
                if len(found) > tree_limit:
                    raise ValueError('workspace entry limit exceeded')
                if action == 'tree' and stat.S_ISDIR(metadata.st_mode):
                    with runtime.open_relative(parent, leaf, directory=True) as child:
                        visit(child, rel)
        visit(fd, actual)
        if action == 'tree':
            found.sort(key=lambda item: '/'.join(item[0]))
        return {'path': redact(shown(actual)), 'entries': [clean(item) for _, item in found]}


def drop_escaping_links(root, *, origin, limit=20000):
    """Validate link targets and remove escaping entries using held parent fds."""
    escaped = []
    visited = 0
    with runtime.open_directory(root) as root_fd:
        top = os.path.realpath('/proc/self/fd/' + str(root_fd))

        def visit(fd, parts):
            nonlocal visited
            for name, info in runtime.list_directory(fd):
                visited += 1
                if visited > limit:
                    raise ValueError('workspace entry limit exceeded')
                if stat.S_ISLNK(info.st_mode):
                    target = os.path.realpath('/proc/self/fd/' + str(fd) + '/' + name)
                    if target != top and not target.startswith(top + '/'):
                        runtime.unlink_entry(fd, name)
                        escaped.append('/'.join(parts + [name]))
                elif stat.S_ISDIR(info.st_mode):
                    with runtime.open_relative(fd, name, directory=True) as child:
                        visit(child, parts + [name])
        visit(root_fd, [])
    if escaped:
        raise ValueError('symlink target must resolve inside ' + origin + ': ' + ', '.join(sorted(escaped)))
