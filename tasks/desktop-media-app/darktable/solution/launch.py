#!/usr/bin/env python3
"""Launch the pinned darktable 5.6.2 product from the installed runtime.

    start.sh [DOCUMENT ...]          the desktop application (darktable [IMAGE_FILE | IMAGE_FOLDER])
    start.sh darktable-cli ARGUMENT ...  the product's command-line exporter (the AppImage convention)

It maps the public environment to darktable's own options: the configuration and library live in
DATA_DIR/darktable (--configdir), thumbnails in XDG_CACHE_HOME (--cachedir). The desktop configuration is
seeded once with the first-run answers (no welcome assistant, no OpenCL probe on a machine without GPUs). The
command-line exporter uses its own configuration directory DATA_DIR/darktable-cli: darktable locks its
configuration while the desktop application runs, so a second process must not share it (upstream behaviour).
Both run the bundled executables directly with the environment of the AppImage's own GTK launcher hook.

OpenMP threads follow the CPU quota of the container. Landlock support is required; rights follow the available kernel ABI:
the process may write only inside its instance directories and the desktop session, and it may execute only
programs of this package (the product starts no helper programs in the reference: no audio player, mail
client, printer or updater).
"""
from __future__ import annotations

import ctypes
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys

RC = '''ui/show_welcome_screen=FALSE
opencl=FALSE
'''
CLI_RC = '''opencl=FALSE
'''
# Settings held for the whole desktop session (darktable --conf: they take precedence over darktablerc and the
# preferences): no OpenCL runtime library, no external library or model folder for the AI back end, no audio
# player program, and the import dialog offers the home folder and no mounted drives as places.
PINNED = ('opencl=FALSE', 'opencl_library=', 'plugins/ai/enabled=FALSE',
          'plugins/ai/ort_library_path=', 'plugins/ai/models_path=',
          'plugins/lighttable/audio_player=', 'ui_last/import_dialog_show_mounted=FALSE',
          'ui_last/import_dialog_show_pictures=FALSE', 'ui_last/import_dialog_show_home=TRUE')
# The runtime kills the process group 10 s after its stop signal.
QUIT_SECONDS = 7


def threads():
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()[:2]
        if quota != 'max':
            return max(1, math.ceil(int(quota) / int(period)))
    except (OSError, ValueError):
        pass
    return max(1, min(len(os.sched_getaffinity(0)), 8))


def environment(appdir: Path):
    usr = appdir / 'usr'
    env = dict(os.environ)
    env.update(APPDIR=str(appdir), GTK_DATA_PREFIX=str(appdir), GTK_THEME='Adwaita:light', GDK_BACKEND='x11',
               XDG_DATA_DIRS=f'{usr}/share:/usr/share', GSETTINGS_SCHEMA_DIR=str(usr / 'share/glib-2.0/schemas'),
               GI_TYPELIB_PATH=str(usr / 'lib/girepository-1.0'), GTK_EXE_PREFIX=str(usr),
               GTK_PATH=str(usr / 'lib/gtk-3.0'), GTK_IM_MODULE_FILE=str(usr / 'lib/gtk-3.0/3.0.0/immodules.cache'),
               GDK_PIXBUF_MODULE_FILE=str(usr / 'lib/gdk-pixbuf-2.0/2.10.0/loaders.cache'),
               GIO_EXTRA_MODULES=str(usr / 'lib/gio/modules'), OMP_NUM_THREADS=str(threads()),
               OMP_THREAD_LIMIT=str(threads()), OMP_MAX_ACTIVE_LEVELS='1')
    for key, sub in (('CAMLIBS', 'libgphoto2'), ('IOLIBS', 'libgphoto2_port')):
        folders = sorted(p for p in (usr / 'lib' / sub).glob('*') if p.is_dir()) if (usr / 'lib' / sub).is_dir() else []
        if folders:
            env[key] = str(folders[0])
    return env


# -- Landlock (Linux 5.13+): confine writes and program execution -------------------------------------------------
_EXECUTE, _WRITE_FILE, _READ_FILE, _READ_DIR = 1 << 0, 1 << 1, 1 << 2, 1 << 3
_WRITE_RIGHTS = sum(1 << i for i in (1, 4, 5, 6, 7, 8, 9, 10, 11, 12))  # write, remove, make *
_PATH_BENEATH = 1


class _Ruleset(ctypes.Structure):
    _fields_ = [('handled_access_fs', ctypes.c_uint64)]


class _Beneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]


def confine(writable, executable):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = libc.syscall(444, None, ctypes.c_size_t(0), ctypes.c_uint32(1))
    if abi < 1:
        raise SystemExit('darktable requires Landlock support for filesystem and execution confinement')
    handled = _EXECUTE | _WRITE_RIGHTS
    if abi >= 2:
        handled |= 1 << 13  # refer
    if abi >= 3:
        handled |= 1 << 14  # truncate
    ruleset = _Ruleset(handled)
    fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.c_size_t(ctypes.sizeof(ruleset)), ctypes.c_uint32(0))
    if fd < 0:
        raise SystemExit('darktable_start: could not create the Landlock ruleset')
    rules = [(p, handled & ~_EXECUTE) for p in writable] + [(p, _EXECUTE) for p in executable]
    for path, access in rules:
        try:
            parent = os.open(path, os.O_PATH | os.O_CLOEXEC)
        except OSError:
            continue
        rule = _Beneath(access if os.path.isdir(path) else access & (_EXECUTE | _WRITE_FILE | (1 << 14)), parent)
        if libc.syscall(445, fd, _PATH_BENEATH, ctypes.byref(rule), ctypes.c_uint32(0)) != 0:
            raise SystemExit(f'darktable_start: could not add a Landlock rule ({ctypes.get_errno()})')
        os.close(parent)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(446, fd, ctypes.c_uint32(0)) != 0:
        raise SystemExit('darktable_start: could not apply the Landlock ruleset')
    os.close(fd)


def instance_roots():
    """The private instance directories the runtime supplied, and the desktop session directory."""
    keys = ('DATA_DIR', 'HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_RUNTIME_DIR')
    return sorted({str(Path(os.environ[k]).resolve()) for k in keys if os.environ.get(k)})


def main() -> None:
    package = Path(__file__).resolve().parent
    appdir = package / 'runtime'
    cli = sys.argv[1:2] == ['darktable-cli']
    args = sys.argv[2:] if cli else sys.argv[1:]
    binary = appdir / 'usr' / 'bin' / ('darktable-cli' if cli else 'darktable')
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit(f'reference darktable executable is unavailable: {binary}')
    data = Path(os.environ.get('DATA_DIR') or Path.home() / '.local/share/darktable-data').resolve()
    config = data / ('darktable-cli' if cli else 'darktable')
    config.mkdir(parents=True, exist_ok=True)
    rc = config / 'darktablerc'
    if not rc.exists():
        rc.write_text(CLI_RC if cli else RC)
    cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache').resolve() / ('darktable-cli' if cli else 'darktable')
    cache.mkdir(parents=True, exist_ok=True)
    env = environment(appdir)
    writable = instance_roots() + ['/dev/null', '/dev/shm']
    # The dynamic loader is executed with every program.
    executable = [str(appdir), '/usr/bin/locale', os.path.realpath('/lib64/ld-linux-x86-64.so.2')]
    if cli:
        # Upstream enumerates FILE profiles from config/color/out at startup.
        # Stage the explicitly requested public ICC document there before the
        # exporter starts; --icc-file still names the same user document.
        if '--icc-file' in args:
            index=args.index('--icc-file')+1
            if index<len(args):
                profile=Path(args[index])
                public=Path(os.environ['HOME']).resolve()
                if profile.is_file() and not profile.is_symlink() and profile.resolve().is_relative_to(public):
                    output_profiles=config/'color/out';output_profiles.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(profile,output_profiles/profile.name)
        # Core options follow --core, where the private configuration directory is added.
        if '--core' in args:
            cut = args.index('--core') + 1
            argv = args[:cut] + ['--threads', str(threads()), '--configdir', str(config), '--cachedir', str(cache)] + args[cut:]
        else:
            argv = args + ['--core', '--threads', str(threads()), '--configdir', str(config), '--cachedir', str(cache)]
        confine(writable, executable)
        os.execve(str(binary), [str(binary), *argv], env)
    # One desktop instance owns this configuration; a lock left by a stopped process is stale.
    for name in ('data.db.lock', 'library.db.lock'):
        try:
            (config / name).unlink()
        except FileNotFoundError:
            pass
    pinned = [item for entry in PINNED for item in ('--conf', entry)]
    argv = ['--threads', str(threads()), '--configdir', str(config), '--cachedir', str(cache), *pinned, *args]
    raise SystemExit(desktop(binary, argv, env, writable, executable))


def desktop(binary, argv, env, writable, executable):
    """Run the desktop application as a child in its own process group. A stop signal asks it to quit through
    its own D-Bus remote interface (org.darktable.service.Remote.Quit), so it shuts down as after File > Quit
    and saves its configuration; it is killed if it has not exited within QUIT_SECONDS."""
    libc = ctypes.CDLL(None, use_errno=True)

    def child_setup():
        os.setpgid(0, 0)
        libc.prctl(1, signal.SIGKILL, 0, 0, 0)  # PR_SET_PDEATHSIG: never outlive the launcher
        confine(writable, executable)

    child = subprocess.Popen([str(binary), *argv], env=env, preexec_fn=child_setup)
    stopping = []

    def stop(signum, _frame):
        if stopping or child.poll() is not None:
            return
        stopping.append(signum)
        subprocess.run(['dbus-send', '--session', '--dest=org.darktable.service', '--type=method_call',
                        '/darktable', 'org.darktable.service.Remote.Quit'], env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=False)
        try:
            child.wait(QUIT_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)

    for name in ('SIGTERM', 'SIGINT', 'SIGHUP'):
        signal.signal(getattr(signal, name), stop)
    while True:
        try:
            status = child.wait()
            break
        except InterruptedError:
            continue
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except OSError:
        pass
    return 128 - status if status < 0 else status


if __name__ == '__main__':
    main()
