"""Descriptor-based, no-follow reads of explicit exchange roots."""
import hashlib
import os
from pathlib import PurePosixPath
import stat
from contextlib import contextmanager, ExitStack
import blackbox_runtime as runtime

@contextmanager
def directory(product, root, parts=(), *, create=False):
    account=product.account()
    with ExitStack() as stack:
        fd=stack.enter_context(runtime.open_directory(root))
        for name in parts:
            if name in ('', '.', '..') or '/' in name:raise ValueError('invalid directory component')
            created=False
            if create:
                try:os.mkdir(name,0o700,dir_fd=fd);created=True
                except FileExistsError:pass
            child=stack.enter_context(runtime.open_relative(fd,name,directory=True))
            if created:runtime.set_metadata(child,mode=0o755,uid=account.pw_uid,gid=account.pw_gid)
            fd=child
        yield fd

def parent(root,name):
    parts=PurePosixPath(name).parts
    if not parts or any(p in ('/','..','.') for p in parts):raise ValueError('invalid relative path')
    with runtime.open_directory(root) as root_fd:fd=os.dup(root_fd)
    try:
        for p in parts[:-1]:
            next_fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=next_fd
        return fd,parts[-1]
    except BaseException:os.close(fd);raise

def read(root,name,limit=1048576):
    return runtime.read_file(root,name,limit=limit)

def entry(dfd,leaf,path):
    info=os.stat(leaf,dir_fd=dfd,follow_symlinks=False)
    kind='symlink' if stat.S_ISLNK(info.st_mode) else 'directory' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'other'
    result={'path':path,'type':kind,'mode':stat.S_IMODE(info.st_mode)}
    if kind=='file':
        result['size']=info.st_size
        if info.st_size<=1048576:
            data=runtime.read_file(dfd,leaf,limit=1048576)
            result['sha256']=hashlib.sha256(data).hexdigest()
    elif kind=='symlink':
        target=os.readlink(leaf,dir_fd=dfd)
        result['target']='[outside workspace]' if target.startswith('/') else target
    return result

def inspect(root,name,tree=False):
    if not tree:
        fd,leaf=parent(root,name)
        try:return entry(fd,leaf,name)
        finally:os.close(fd)
    if name:
        fd,leaf=parent(root,name)
        try:top=os.open(leaf,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
        finally:os.close(fd)
    else:
        with runtime.open_directory(root) as root_fd:top=os.dup(root_fd)
    result=[]
    def visit(fd,prefix):
        for leaf in sorted(os.listdir(fd)):
            if leaf=='.git':continue
            path=prefix+'/'+leaf if prefix else leaf
            e=entry(fd,leaf,path);result.append(e)
            if len(result)>10000:raise ValueError('tree exceeds 10000 entries')
            if e['type']=='directory':
                child=os.open(leaf,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
                try:visit(child,path)
                finally:os.close(child)
    try:visit(top,name)
    finally:os.close(top)
    return {'entries':result}
