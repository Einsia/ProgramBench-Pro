"""Require filesystem and program-execution confinement for the reference application."""
import ctypes
import os
from pathlib import Path


class Ruleset(ctypes.Structure):
    _fields_ = [('handled_access_fs', ctypes.c_uint64)]


class Beneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]


def confine(binary, package):
    """Allow instance writes and execution of the selected product binary only.

    Product libraries and resources remain readable. The launcher has already
    finished setup; no shell, editor, converter or plugin-host executable is
    available to the product after this call. Forking and threads remain usable.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = libc.syscall(444, None, ctypes.c_size_t(0), ctypes.c_uint32(1))
    if abi < 1:
        raise SystemExit('the application requires Landlock support')
    execute, read_file, read_dir = 1, 4, 8
    writes = sum(1 << i for i in (1, 4, 5, 6, 7, 8, 9, 10, 11, 12))
    if abi >= 2:
        writes |= 1 << 13  # cross-directory reparenting
    if abi >= 3:
        writes |= 1 << 14  # truncation
    handled = execute | read_file | read_dir | writes
    ruleset = Ruleset(handled)
    fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), ctypes.c_uint32(0))
    if fd < 0:
        raise SystemExit('could not create application confinement')
    roots = {Path(os.environ[k]).resolve() for k in
             ('DATA_DIR', 'HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
              'XDG_RUNTIME_DIR', 'PBP_FILES_DIR', 'PBP_AUDIO_PIPE_DIR') if os.environ.get(k)}
    if os.environ.get('DATA_DIR'):
        roots.add(Path(os.environ['DATA_DIR']).resolve().parent / 'files')
    writable = roots | {Path('/dev/null'), Path('/dev/shm')}
    readable = {Path(p) for p in ('/usr', '/lib', '/lib64', '/etc', '/proc', '/sys', '/dev')}
    readable.add(Path(package) / 'runtime')
    preload = Path(package) / 'lmms_cpus.so'
    if preload.exists():
        readable.add(preload)
    entries = [(p, writes | read_file | read_dir) for p in writable]
    entries += [(p, read_file | read_dir) for p in readable]
    entries += [(Path(binary), execute | read_file), (Path('/lib64/ld-linux-x86-64.so.2').resolve(), execute | read_file)]
    try:
        for path, access in entries:
            try:
                parent = os.open(path, os.O_PATH | os.O_CLOEXEC)
            except FileNotFoundError:
                continue
            try:
                if not path.is_dir():
                    access &= execute | read_file | (1 << 1) | (1 << 14)
                access &= handled
                rule = Beneath(access, parent)
                if libc.syscall(445, fd, ctypes.c_int(1), ctypes.byref(rule), ctypes.c_uint32(0)) != 0:
                    raise SystemExit('could not configure application confinement')
            finally:
                os.close(parent)
        if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(446, fd, ctypes.c_uint32(0)) != 0:
            raise SystemExit('could not apply application confinement')
    finally:
        os.close(fd)
