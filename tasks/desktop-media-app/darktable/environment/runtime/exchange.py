"""Document operations anchored to the runtime's directory-descriptor helpers."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat

import blackbox_runtime as runtime


@contextmanager
def directory(root, relative, account, *, mode=0o700):
    """Prepare each directory component while retaining its parent descriptor."""
    parts = Path(relative).parts
    if Path(relative).is_absolute() or not parts or '..' in parts:
        raise ValueError('expected a relative directory below the instance root')
    def descend(parent, remaining):
        with runtime.owned_directory(parent, remaining[0], uid=account.pw_uid,
                                     gid=account.pw_gid, mode=mode) as fd:
            if len(remaining) == 1:
                yield fd
            else:
                yield from descend(fd, remaining[1:])
    with runtime.open_directory(root) as root_fd:
        yield from descend(root_fd, parts)


def prepare(product, areas):
    account = product.account()
    with directory(product.config.state, 'files', account) as root_fd:
        for area in areas:
            with directory(root_fd, area, account):
                pass


def read_regular(path, limit):
    path = Path(path)
    return runtime.read_file(path.parent, path.name, limit=limit)


def write_regular(path, payload, account=None):
    path = Path(path)
    runtime.atomic_write(path.parent, path.name, payload,
                         uid=account.pw_uid if account else None,
                         gid=account.pw_gid if account else None, mode=0o600)


def file_info(path, limit):
    path = Path(path)
    with runtime.open_relative(path.parent, path.name) as fd:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('expected a bounded regular document with one link')
        return info


def inventory(root, suffixes, limit, *, recursive=False, max_files=4000, max_depth=24):
    """Return relative names and validated metadata without following directory or file links."""
    found = []
    def walk(parent, prefix, depth):
        if depth > max_depth or len(found) >= max_files:
            return
        for name, info in runtime.list_directory(parent):
            if len(found) >= max_files:
                break
            try:
                if recursive and stat.S_ISDIR(info.st_mode):
                    with runtime.open_relative(parent, name, directory=True) as child:
                        walk(child, prefix + name + '/', depth + 1)
                elif stat.S_ISREG(info.st_mode) and Path(name).suffix.casefold() in suffixes:
                    with runtime.open_relative(parent, name) as fd:
                        current = os.fstat(fd)
                        if stat.S_ISREG(current.st_mode) and current.st_nlink == 1 and current.st_size <= limit:
                            found.append((prefix + name, current))
            except (OSError, ValueError):
                continue
    try:
        with runtime.open_directory(root) as fd:
            walk(fd, '', 0)
    except (OSError, ValueError):
        pass
    return found
