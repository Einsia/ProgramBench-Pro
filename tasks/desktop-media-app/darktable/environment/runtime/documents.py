"""Document exchange rooted in a retained directory descriptor.

Every path component is opened without following links. Renames and link changes
cannot redirect a previously registered download to a different directory tree.
Only regular files with a public document suffix can be read.
"""
import base64
import ctypes
import os
from pathlib import PurePosixPath
import stat

import blackbox_runtime as runtime
import exchange


class _OpenHow(ctypes.Structure):
    _fields_=[('flags',ctypes.c_uint64),('mode',ctypes.c_uint64),('resolve',ctypes.c_uint64)]


class Documents:
    def __init__(self, root, suffixes, limit):
        self.root = str(root)
        self.suffixes = suffixes
        self.limit = limit
        with runtime.open_directory(root) as fd:
            self.fd = os.dup(fd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def parts(self, value):
        if not isinstance(value, str) or not value or len(value) > 4000 or '\0' in value or '\\' in value:
            raise ValueError('a document path is a relative path inside the document folder')
        parts = value.split('/')
        if any(part in ('', '.', '..') or len(part.encode()) > 255 for part in parts):
            raise ValueError('invalid relative document path')
        if PurePosixPath(value).suffix.casefold() not in self.suffixes:
            raise ValueError('the file type is not a downloadable document')
        return parts

    def open(self, name, *, flags=os.O_RDONLY, mode=0o600):
        self.parts(name)
        try:
            how=_OpenHow((flags & ~os.O_TRUNC)|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,
                         mode if flags & os.O_CREAT else 0,0x08|0x04|0x02)
            libc=ctypes.CDLL(None,use_errno=True);libc.syscall.restype=ctypes.c_long
            fd=libc.syscall(437,self.fd,ctypes.c_char_p(name.encode()),ctypes.byref(how),ctypes.sizeof(how))
            if fd<0:raise OSError(ctypes.get_errno(),'confined document open failed')
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                os.close(fd)
                raise ValueError('the document is not a regular unlinked file')
            if flags & os.O_TRUNC:
                os.ftruncate(fd,0)
            return fd
        except OSError:
            raise ValueError('the document is unavailable or its path is not confined') from None

    def stat(self, name):
        fd = self.open(name)
        try:
            return os.fstat(fd)
        finally:
            os.close(fd)

    def read(self, name):
        self.parts(name)
        data = runtime.read_file(self.fd, name, limit=self.limit)
        return {'filename': name, 'size': len(data), 'body_base64': base64.b64encode(data).decode()}

    def inventory(self):
        return [{'filename': name, 'size': info.st_size}
                for name, info in exchange.inventory(self.fd, self.suffixes, self.limit, recursive=True)]

    def mkdir(self, name, account):
        if not isinstance(name, str) or len(name) > 1000 or '\\' in name or '\0' in name:
            raise ValueError('invalid document directory')
        with exchange.directory(self.fd, name, account) as fd:
            return os.dup(fd)
