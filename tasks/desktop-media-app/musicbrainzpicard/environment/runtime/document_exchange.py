"""Document storage operations anchored to directory descriptors."""
from contextlib import ExitStack
import os
from pathlib import Path
import stat

import blackbox_runtime as runtime


def prepare(product, areas):
    account = product.account()
    root_owner = 0 if product.switching() else account.pw_uid
    root_group = 0 if product.switching() else account.pw_gid
    with runtime.owned_directory(product.config.state, 'files', uid=root_owner,
                                 gid=root_group, mode=0o711) as root:
        for name in areas:
            with runtime.owned_directory(root, name, uid=account.pw_uid, gid=account.pw_gid):
                pass


def relative(root, path):
    return str(Path(path).relative_to(root))


def read(root, path, limit):
    return runtime.read_file(root, relative(root, path), limit=limit)


def file_info(root, path):
    with runtime.open_relative(root, relative(root, path)) as fd:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('expected a regular document with one link')
        return info


def write(root, path, payload, account, *, mode=0o600, mtime=None):
    parts = Path(relative(root, path)).parts
    if not parts or '..' in parts:
        raise ValueError('expected a relative document path')
    with ExitStack() as stack:
        folder = stack.enter_context(runtime.open_directory(root))
        for name in parts[:-1]:
            folder = stack.enter_context(runtime.owned_directory(
                folder, name, uid=account.pw_uid, gid=account.pw_gid, mode=0o755))
        runtime.atomic_write(folder, parts[-1], payload, uid=account.pw_uid,
                             gid=account.pw_gid, mode=mode)
        if mtime is not None:
            with runtime.open_relative(folder, parts[-1]) as fd:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != account.pw_uid:
                    raise ValueError('document changed during timestamp update')
                runtime.set_metadata(fd, ns=(int(mtime * 1_000_000_000),) * 2)


def entries(root, *, limit=10000, depth=32):
    """Yield relative names and opened metadata, skipping links and special files."""
    remaining = [limit]

    def visit(folder, prefix, levels):
        for name, listed in runtime.list_directory(folder):
            if remaining[0] <= 0:
                return
            path = prefix / name
            try:
                if stat.S_ISDIR(listed.st_mode) and levels:
                    with runtime.open_relative(folder, name, directory=True) as child:
                        remaining[0] -= 1
                        yield str(path), os.fstat(child)
                        yield from visit(child, path, levels - 1)
                elif stat.S_ISREG(listed.st_mode):
                    with runtime.open_relative(folder, name) as fd:
                        info = os.fstat(fd)
                        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                            continue
                        remaining[0] -= 1
                        yield str(path), info
            except (OSError, ValueError):
                continue
    with runtime.open_directory(root) as folder:
        yield from visit(folder, Path(), depth)


def remove(root, path):
    with runtime.open_directory(root) as folder:
        name = relative(root, path)
        with runtime.open_relative(folder, name) as fd:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('expected a regular document with one link')
        runtime.unlink_entry(folder, name)
