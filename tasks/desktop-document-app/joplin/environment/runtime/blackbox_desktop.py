"""Shared native-desktop parts of black-box runtimes.

Vendored byte-identically into the environment/runtime/ of every desktop task.
A task runtime (its broker) owns the product, its guards and its non-GUI
operations; this module supplies what every desktop runtime shares:

- DesktopSession: one private X11 desktop (Xvfb, a D-Bus session bus, Openbox,
  the AT-SPI accessibility bus and optionally a PulseAudio null sink), run as
  the product user, with the environment the product needs;
- Desktop: the observer and actuator. AT-SPI discovery and X11 input run in a
  helper process under the product user (AT-SPI peers accept only their own
  user). Every accessibility query runs in a short-lived child connected only
  for that query: a long-lived assistive connection stops receiving answers
  once a modal dialog opens or closes (seen with GTK 3 and wxWidgets), while a
  fresh connection observes the application as an ordinary idle desktop.
  Input is ordinary X11 keyboard and pointer events (xdotool); activate is the
  control's default accessible action;
- one observation shape, the shared GUI operation specs (blackbox-v2 help
  fields) and the desktop readiness predicate.

The same runtime drives the reference for exploration and your application for
self-tests and evaluation, with identical readiness, observations and operations.

Runtime-side API: DesktopSession(user, screen, maximize, audio).start(), .env(),
.close(); Desktop(session, **options) with observe(tree), screenshot(region),
windows(), act(request) for the GUI operations of operations(screen),
resolve(target), inspect(), set_text(target, text, confirm), clipboard(target,
limit), ready(minimum) and close(). Failures raise DesktopError (.timeout when
the desktop did not answer in time).
"""
import argparse
import base64
import ctypes
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import pwd
import re
import select
import shutil
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime

MODULE = Path(__file__).resolve()
WINDOW_ROLES = ('frame', 'window', 'dialog', 'file chooser', 'alert')
TOP_ROLES = ('frame', 'window', 'dialog')
LAYOUT_ROLES = ('panel', 'filler', 'unknown', 'scroll pane', 'viewport', 'section')
VIEWPORT_ROLES = ('scroll pane', 'layered pane', 'canvas', 'viewport')
MENU_ROLES = ('menu', 'popup menu', 'menu bar')
# Hidden GtkIconView/list children can report Showing=False after a model
# change while keeping real geometry inside their scrolled viewport.
LATE_ROLES = ('icon', 'canvas item', 'list item', 'table cell')
STATE_NAMES = ('focused', 'selected', 'checked', 'pressed', 'expanded', 'editable', 'active', 'indeterminate', 'busy',
               'modal')
WM_APPLICATIONS = ('openbox', 'xfwm4', 'gnome-shell', 'mutter')
BUTTONS = {'left': 1, 'middle': 2, 'right': 3}
MODIFIERS = {'Shift': 'shift', 'Control': 'ctrl', 'Alt': 'alt'}
CHECKABLE_ROLES = ('check box', 'toggle button', 'radio button', 'check menu item', 'radio menu item')
MAX_TEXT_INPUT = 20_000
MAX_VIA = 60
MAX_SCREENSHOT = 8 * 1024 * 1024
# atspi_timeouts: libatspi method-call timeout and the grace after an application starts during which calls may block
# for the D-Bus default of 25 s (library defaults 800 ms and 15 s; null keeps them).
DEFAULTS = {'atspi_timeouts': [800, 3000], 'query_timeout': 35.0, 'settle': 0.35,
            'compact_nodes': 450, 'tree_nodes': 5000, 'depth': 40, 'name_chars': 200, 'text_chars': 600,
            'tree_text_chars': 4096}


class DesktopError(RuntimeError):
    """An operation could not be performed on the desktop."""

    def __init__(self, message, *, timeout=False):
        super().__init__(message)
        self.timeout = timeout


# -- session ------------------------------------------------------------------------------------------------------


def account(user=''):
    return pwd.getpwnam(user) if user else pwd.getpwuid(os.geteuid())


def as_user(user):
    """Popen keyword arguments that run a child as the product user (only needed when we are root)."""
    entry = account(user)
    if os.geteuid() == 0 and entry.pw_uid != 0:
        return {'user': entry.pw_uid, 'group': entry.pw_gid, 'extra_groups': []}
    return {}


def openbox_config(maximize=True, center_dialogs=True):
    """The system Openbox configuration with one desktop, no root-window menu, no program launchers and, when asked,
    ordinary application windows maximized (dialogs keep their own size) and dialogs centered on the screen (the
    same place as over a maximized parent, without racing the parent's maximization)."""
    source = Path('/etc/xdg/openbox/rc.xml')
    text = source.read_text() if source.is_file() else '<openbox_config xmlns="http://openbox.org/3.4/rc"></openbox_config>'
    text = re.sub(r'(<desktops>.*?<number>)\d+(</number>)', r'\g<1>1\g<2>', text, count=1, flags=re.S)
    text = re.sub(r'<context name="Root">.*?</context>', '<context name="Root"/>', text, count=1, flags=re.S)
    text = re.sub(r'<keybind key="[^"]*">(?:(?!</keybind>).)*?(?:Execute|ToggleShowDesktop)(?:(?!</keybind>).)*</keybind>',
                  '', text, flags=re.S)
    rules = ''
    if maximize:
        rules += '<application class="*" type="normal"><maximized>true</maximized></application>'
    if center_dialogs:
        rules += ('<application class="*" type="dialog"><position force="yes"><x>center</x><y>center</y></position>'
                  '</application>')
    if rules:
        text, count = re.subn(r'<applications>', '<applications>' + rules, text, count=1)
        if not count:
            text = text.replace('</openbox_config>', '<applications>' + rules + '</applications></openbox_config>', 1)
    return text


def _kill_group(proc, grace=2.0):
    if proc is None:
        return
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(wait)
            break
        except subprocess.TimeoutExpired:
            continue


class DesktopSession:
    """One private X11 desktop run as the product user.

    screen: (width, height) of the single screen; maximize: ordinary application windows open maximized;
    center_dialogs: dialogs open centered on the screen; audio: also run a PulseAudio null sink.
    Root creates sessions below a root-owned container, selected by BLACKBOX_DESKTOP_ROOT
    or an explicit root. Other users retain their private /tmp session layout.
    display None picks a free number from first_display.
    """

    def __init__(self, *, user='', screen=(1280, 900), depth=24, maximize=True, center_dialogs=True, audio=False,
                 display=None, first_display=100, root=None, log_dir=None):
        self.user, self.screen, self.depth, self.maximize, self.audio = user, tuple(screen), depth, maximize, audio
        self.center_dialogs = center_dialogs
        self.requested, self.first_display, self.requested_root = display, first_display, root
        self.log_dir = Path(log_dir) if log_dir else None
        self.account = account(user)
        self.display = self.root = None
        self.processes = {}
        self.variables = {}
        self._paths = {}
        self._handles = ExitStack()
        self._container_fd = None

    # Paths and environment -----------------------------------------------------------------------------------------
    @property
    def number(self):
        return int(self.display.lstrip(':'))

    def _free_display(self):
        if self.requested:
            number = int(str(self.requested).lstrip(':'))
            if Path(f'/tmp/.X11-unix/X{number}').exists() or Path(f'/tmp/.X{number}-lock').exists():
                if subprocess.run(['xdpyinfo', '-display', f':{number}'], capture_output=True, timeout=5).returncode == 0:
                    raise DesktopError(f'display :{number} is already in use')
                for stale in (Path(f'/tmp/.X11-unix/X{number}'), Path(f'/tmp/.X{number}-lock')):
                    try:
                        stale.unlink()
                    except OSError:
                        pass
            return number
        for number in range(self.first_display, self.first_display + 400):
            if not Path(f'/tmp/.X11-unix/X{number}').exists() and not Path(f'/tmp/.X{number}-lock').exists():
                return number
        raise DesktopError('no free X11 display number')

    def _directory(self, path, mode=0o700):
        path = Path(path)
        if os.geteuid() == 0:
            parent = self._container_fd if path == self.root else self._paths[path.parent]
            fd = self._handles.enter_context(runtime.owned_directory(parent, path.name, uid=0, gid=0, mode=mode))
            self._paths[path] = fd
            return path
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(mode)
        return path

    def base_env(self):
        root = self.root
        env = {k: os.environ[k] for k in ('PATH', 'LANG', 'LC_ALL', 'TZ') if k in os.environ}
        env.update(HOME=str(root / 'home'), USER=self.account.pw_name, LOGNAME=self.account.pw_name,
                   DISPLAY=self.display, XDG_RUNTIME_DIR=str(root / 'runtime'),
                   XDG_CONFIG_HOME=str(root / 'config'), XDG_CACHE_HOME=str(root / 'cache'), PYTHONDONTWRITEBYTECODE='1',
                   DBUS_SESSION_BUS_ADDRESS=f'unix:path={root}/session.sock')
        return env

    def env(self):
        """Variables the product (and the desktop helper) needs; a task may add its own on top."""
        env = {'DISPLAY': self.display, 'DBUS_SESSION_BUS_ADDRESS': f'unix:path={self.root}/session.sock',
               'XDG_RUNTIME_DIR': str(self.root / 'runtime'), 'GDK_BACKEND': 'x11', 'GTK_MODULES': 'gail:atk-bridge',
               'NO_AT_BRIDGE': '0', 'GTK_A11Y': 'always', 'QT_ACCESSIBILITY': '1',
               'QT_LINUX_ACCESSIBILITY_ALWAYS_ON': '1', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC'}
        env.update(self.variables)
        return env

    def _log(self, name):
        if self.log_dir is None:
            return subprocess.DEVNULL
        self.log_dir.mkdir(parents=True, exist_ok=True)
        return (self.log_dir / f'desktop-{name}.log').open('ab')

    def _spawn(self, name, args, env=None, stdout=None):
        log = self._log(name)
        try:
            proc = subprocess.Popen(args, env=env or self.base_env(), stdin=subprocess.DEVNULL,
                                    stdout=stdout or log, stderr=log, start_new_session=True, **as_user(self.user))
        finally:
            if log is not subprocess.DEVNULL:
                log.close()
        self.processes[name] = proc
        return proc

    def _run(self, args, timeout=5, env=None):
        return subprocess.run(args, env=env or self.base_env(), capture_output=True, timeout=timeout, **as_user(self.user))

    def _wait(self, name, predicate, seconds, failure):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            proc = self.processes.get(name)
            if proc is not None and proc.poll() is not None:
                raise DesktopError(f'{failure} ({name} exited with status {proc.returncode})')
            try:
                if predicate():
                    return
            except (OSError, subprocess.SubprocessError):
                pass
            time.sleep(.05)
        raise DesktopError(failure)

    # Lifecycle ----------------------------------------------------------------------------------------------------
    def start(self):
        if os.geteuid() == 0:
            with runtime.owned_directory('/tmp', '.X11-unix', uid=0, gid=0, mode=0o1777):
                pass
        number = self._free_display()
        self.display = f':{number}'
        if os.geteuid() == 0:
            container = Path(self.requested_root or os.environ.get('BLACKBOX_DESKTOP_ROOT', '/run/blackbox-desktop'))
            with runtime.open_directory(container.parent, create=True) as parent_fd:
                self._container_fd = self._handles.enter_context(
                    runtime.owned_directory(parent_fd, container.name, uid=0, gid=0, mode=0o711))
            root = container / f'display-{number}'
            runtime.remove_entry(self._container_fd, root.name, missing_ok=True)
        else:
            root = Path(self.requested_root) if self.requested_root else Path(f'/tmp/blackbox-desktop-{number}')
            if root.is_symlink() or (root.exists() and not root.is_dir()):
                raise DesktopError('the desktop session directory is not a directory')
            if root.exists():
                shutil.rmtree(root)
        self.root = root
        for path in (root, root / 'runtime', root / 'home', root / 'cache', root / 'config', root / 'config' / 'openbox'):
            self._directory(path)
        try:
            conf = Path('/usr/share/dbus-1/session.conf').read_text()
            conf = re.sub(r'<listen>.*?</listen>', f'<listen>unix:path={self.root}/session.sock</listen>', conf, count=1)
            self._write(self.root / 'session.conf', conf)
            self._write(self.root / 'config' / 'openbox' / 'rc.xml', openbox_config(self.maximize, self.center_dialogs))
            if os.geteuid() == 0:
                for fd in self._paths.values():
                    os.fchown(fd, self.account.pw_uid, self.account.pw_gid)
                    os.fchmod(fd, 0o700)
            self._start_services(number)
        except BaseException:
            self.close()
            raise
        return self

    def _start_services(self, number):
        width, height = self.screen
        self._spawn('xvfb', ['Xvfb', self.display, '-screen', '0', f'{width}x{height}x{self.depth}', '-ac',
                             '-nolisten', 'tcp', '-noreset'])
        self._wait('xvfb', lambda: self._run(['xdpyinfo', '-display', self.display]).returncode == 0, 15,
                   'the X server did not start')
        self._spawn('dbus', ['dbus-daemon', f'--config-file={self.root}/session.conf', '--nofork'])
        self._wait('dbus', lambda: (self.root / 'session.sock').exists(), 10, 'the D-Bus session bus did not start')
        self._spawn('openbox', ['openbox', '--sm-disable', '--config-file', str(self.root / 'config/openbox/rc.xml')])
        self._wait('openbox', lambda: self._run(['wmctrl', '-m']).returncode == 0, 15,
                   'the window manager did not start')
        self._spawn('atspi', ['/usr/libexec/at-spi-bus-launcher', '--launch-immediately'])
        bus = self.root / 'runtime' / 'at-spi' / f'bus_{number}'
        try:
            self._wait('atspi', bus.exists, 10, 'the accessibility bus did not start')
            self.variables['AT_SPI_BUS_ADDRESS'] = f'unix:path={bus}'
        except DesktopError:
            # Older launchers do not use the display-numbered socket; ask the launcher itself.
            reply = self._run(['dbus-send', '--session', '--print-reply=literal', '--dest=org.a11y.Bus', '/org/a11y/bus',
                               'org.a11y.Bus.GetAddress'], timeout=10)
            address = reply.stdout.decode(errors='replace').strip()
            if reply.returncode or not address.startswith('unix:'):
                raise
            self.variables['AT_SPI_BUS_ADDRESS'] = address
        if self.audio:
            sink = self.root / 'runtime' / 'pulse.native'
            self._spawn('pulseaudio', ['pulseaudio', '--daemonize=no', '--exit-idle-time=-1',
                                       '--load=module-null-sink sink_name=null_sink',
                                       f'--load=module-native-protocol-unix auth-anonymous=1 socket={sink}'])
            self._wait('pulseaudio', sink.exists, 10, 'the audio sink did not start')
            self.variables['PULSE_SERVER'] = f'unix:{sink}'

    def _write(self, path, text):
        path = Path(path)
        if os.geteuid() == 0:
            runtime.write_owned_file(self._paths[path.parent], path.name, text,
                                     uid=self.account.pw_uid, gid=self.account.pw_gid, replace=True)
            return
        path.write_text(text)
        path.chmod(0o600)

    def alive(self):
        proc = self.processes.get('xvfb')
        return proc is not None and proc.poll() is None

    def service_pids(self):
        return [p.pid for p in self.processes.values() if p.poll() is None]

    def close(self):
        for name in ('pulseaudio', 'atspi', 'openbox', 'dbus', 'xvfb'):
            _kill_group(self.processes.pop(name, None))
        if self.root is not None:
            # D-Bus activated services and the accessibility bus daemons can leave their process group; their command
            # lines or environment name this session's private directory.
            marker = str(self.root).encode()
            uid = self.account.pw_uid
            for entry in Path('/proc').iterdir():
                if not entry.name.isdigit() or int(entry.name) == os.getpid():
                    continue
                try:
                    if entry.stat().st_uid != uid:
                        continue
                    if marker in (entry / 'cmdline').read_bytes() or marker in (entry / 'environ').read_bytes():
                        os.kill(int(entry.name), signal.SIGKILL)
                except OSError:
                    continue
            if self._container_fd is not None:
                try:
                    runtime.remove_entry(self._container_fd, self.root.name, missing_ok=True)
                finally:
                    self._handles.close()
                    self._container_fd = None
                    self._paths.clear()
            elif os.geteuid() != 0:
                shutil.rmtree(self.root, ignore_errors=True)
        if self.display:
            for stale in (Path(f'/tmp/.X11-unix/X{self.number}'), Path(f'/tmp/.X{self.number}-lock')):
                try:
                    stale.unlink()
                except OSError:
                    pass


# -- help (blackbox-v2 field specs shared by desktop runtimes) ----------------------------------------------------


def operations(screen):
    """GUI and observation operations of a desktop runtime, as blackbox-v2 help specs. A task broker merges them
    into its help (it may leave some out) and adds its lifecycle, file and product operations."""
    width, height = screen
    number = lambda text, required=False: dict({'type': 'number', 'description': text}, **({'required': True} if required else {}))
    target = {'type': ['string', 'object'],
              'description': 'A control: a ref from the latest observe (for example "e3fa09c1b"), or an object with ref; or with '
                             'role and/or name (name matches the name, text or description, exactly unless exact is '
                             'false); label is the same as name; text matches a substring; optional nth (zero-based '
                             'among the matches, default 0) and within (ref of an ancestor). Objects other than ref are '
                             'matched against a fresh observation and leave the refs of the latest observe valid.'}
    required = dict(target, required=True)
    point = f'Screen pixels as in the screenshot (x 0-{width - 1}, y 0-{height - 1}).'
    button = {'type': 'string', 'enum': list(BUTTONS), 'description': 'Mouse button; default left.'}
    held = {'type': 'array', 'items': {'type': 'string', 'enum': list(MODIFIERS)},
            'description': 'Keys held during the action: Shift, Control, Alt.'}
    return {
        'observe': {'kind': 'observe', 'summary': 'Accessibility snapshot of the desktop: screen [w,h], the product '
                    'windows (ref, title, active, bounds), the focused control and the visible controls (ref, role, name, '
                    'text, description, value, states, bounds [x,y,w,h] in screen pixels). Unnamed layout containers are '
                    'left out unless tree is true. Refs are valid until the next observe.',
                    'fields': {'tree': {'type': 'boolean', 'description': 'Every visible node, with parent, window and '
                                        'depth links (for scripts); default false.'}}},
        'screenshot': {'kind': 'observe', 'summary': f'PNG of the whole {width}x{height} screen as png_base64; after '
                       'zoom, or with region, a magnified view of that rectangle only.',
                       'fields': {'region': {'type': 'array', 'items': {'type': 'number'},
                                             'description': 'Optional [x0, y0, x1, y1] rectangle (at least 20x20 pixels) '
                                                            'to show magnified.'}}},
        'windows': {'kind': 'observe', 'summary': 'The product windows: ref (for focus_window and maximize), title, '
                    'active, bounds [x,y,w,h].', 'fields': {}},
        'click': {'kind': 'gui', 'summary': 'Click a control (at the centre of its visible part) or a screen point.',
                  'fields': {'target': dict(target, description=target['description'] + ' Or give x and y.'),
                             'x': number('x of the point. ' + point), 'y': number('y of the point. ' + point),
                             'button': button,
                             'click_count': {'type': 'integer', 'enum': [1, 2, 3],
                                             'description': 'Number of clicks (2 = double click); default 1.'},
                             'modifiers': held}},
        'activate': {'kind': 'gui', 'summary': "Invoke a control's default accessible action, as assistive technology "
                     'would (for example when a click does not reach a menu item or button).',
                     'fields': {'target': required}},
        'fill': {'kind': 'gui', 'summary': 'Replace the text of an editable control: click it, select all, type the '
                 'value (a spin button is committed with Tab afterwards).',
                 'fields': {'target': required, 'value': {'type': 'string', 'required': True,
                                                          'description': f'Replacement text, at most {MAX_TEXT_INPUT} '
                                                                         'characters; empty clears the field.'}}},
        'type': {'kind': 'gui', 'summary': 'Type text as key presses into the focused control, or click the target '
                 'first. Multi-line text is pasted through the clipboard.',
                 'fields': {'target': dict(target, description=target['description'] + ' Optional.'),
                            'value': {'type': 'string', 'required': True,
                                      'description': f'Text, at most {MAX_TEXT_INPUT} characters.'}}},
        'press': {'kind': 'gui', 'summary': 'Press a key or chord such as Return, Escape, Tab, Delete, F11, Control+S, '
                  'Control+Shift+S, Alt+Return, Shift+F10 or Alt+Tab; with a target it is clicked first.',
                  'fields': {'target': dict(target, description=target['description'] + ' Optional.'),
                             'key': {'type': 'string', 'required': True, 'description': 'Key name or chord (+ joins '
                                     'keys; Control, Shift and Alt are modifiers).'}}},
        'check': {'kind': 'gui', 'summary': 'Set a check box, toggle or radio button to the wanted state (clicked only '
                  'when it differs).',
                  'fields': {'target': required, 'checked': {'type': 'boolean', 'description': 'Wanted state; '
                                                                                               'default true.'}}},
        'move': {'kind': 'gui', 'summary': 'Move the pointer onto a control or point and rest there (tooltips, '
                 'submenus).',
                 'fields': {'target': dict(target, description=target['description'] + ' Or give x and y.'),
                            'x': number('x. ' + point), 'y': number('y. ' + point),
                            'seconds': number('Seconds to rest, 0-3; default 0.3.')}},
        'drag': {'kind': 'gui', 'summary': 'Press at the start, pass through via points, release at the end.',
                 'fields': {'target': dict(target, description='Start control (instead of x, y). ' + target['description']),
                            'x': number('Start x. ' + point), 'y': number('Start y. ' + point),
                            'to_target': dict(target, description='End control (instead of to_x, to_y).'),
                            'to_x': number('End x. ' + point), 'to_y': number('End y. ' + point),
                            'via': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}},
                                    'description': f'Up to {MAX_VIA} intermediate [x, y] points, in order.'},
                            'button': button, 'modifiers': held,
                            'seconds': number('Duration of the movement, 0.1-10; default 0.6.')}},
        'scroll': {'kind': 'gui', 'summary': 'Turn the mouse wheel over a control or point (at the pointer when neither '
                   'is given): 100 per notch, at least one notch for any nonzero delta, at most 25.',
                   'fields': {'target': dict(target, description=target['description'] + ' Optional.'),
                              'x': number('x. ' + point), 'y': number('y. ' + point),
                              'delta_x': number('Horizontal amount, positive scrolls right; default 0.'),
                              'delta_y': number('Vertical amount, positive scrolls down; default 0.')}},
        'zoom': {'kind': 'gui', 'summary': 'Show the rectangle x,y to to_x,to_y magnified in the next screenshot only '
                 '(observations report it; coordinates of every operation stay full-screen).',
                 'fields': {'x': number('Left. ' + point, True), 'y': number('Top. ' + point, True),
                            'to_x': number('Right.', True), 'to_y': number('Bottom.', True)}},
        'focus_window': {'kind': 'gui', 'summary': 'Activate a product window (raise it and give it keyboard focus).',
                         'fields': {'window': {'type': 'string', 'required': True,
                                               'description': 'Window ref from the latest observe or windows.'}}},
        'maximize': {'kind': 'gui', 'summary': 'Maximize a product window (the active one by default).',
                     'fields': {'window': {'type': 'string', 'description': 'Window ref; default the active window.'}}},
        'wait': {'kind': 'gui', 'summary': 'Wait for the product to update (rendering, dialogs, saving).',
                 'fields': {'seconds': number('Seconds, 0-5; default 0.5.')}},
    }


# -- observation utilities for task guards and scripts (tree observations) --------------------------------------


def stable_refs(items):
    """Public refs of one raw snapshot: they depend only on each node's place in the accessibility tree (AT-SPI path),
    its role and its name, so the same screen always gets the same refs (results are reproducible however many
    observations came before) and a ref stays valid while its node is unchanged. Equal keys get -2, -3... in tree
    order."""
    refs, used = [], set()
    for item in items:
        key = json.dumps([item['path'], item['role'], item['name']], ensure_ascii=False).encode()
        base = 'e' + hashlib.sha256(key).hexdigest()[:8]
        ref, count = base, 1
        while ref in used:
            count += 1
            ref = f'{base}-{count}'
        used.add(ref)
        refs.append(ref)
    return refs


def bounds_contain(bounds, x, y):
    bx, by, bw, bh = bounds
    return bx <= x < bx + bw and by <= y < by + bh


def node_at(observation, x, y):
    """The node of a tree observation under a screen point: nodes of the active (or modal) top-level window win over
    windows below it, then the deepest node."""
    nodes = observation.get('nodes', ())
    by_ref = {node['ref']: node for node in nodes}

    def top(node):
        seen = set()
        while node.get('parent') in by_ref and node['ref'] not in seen:
            seen.add(node['ref'])
            node = by_ref[node['parent']]
        return node
    best, rank = None, None
    for node in nodes:
        if bounds_contain(node.get('visible') or node['bounds'], x, y):
            states = set(top(node).get('states', ()))
            key = (bool(states & {'active', 'modal'}), node.get('depth', 0))
            if rank is None or key >= rank:
                best, rank = node, key
    return best


def ancestors(observation, ref):
    """Nodes from the given node up to its top-level window (tree observations)."""
    by_ref = {node['ref']: node for node in observation.get('nodes', ())}
    chain, seen = [], set()
    while ref in by_ref and ref not in seen:
        seen.add(ref)
        chain.append(by_ref[ref])
        ref = by_ref[ref].get('parent')
    return chain


# -- runtime side ---------------------------------------------------------------------------------------------------


class Desktop:
    """Observer and actuator of one session: a helper process as the product user, one request at a time."""

    def __init__(self, session, *, excluded_pids=(), log_dir=None, pointer_guard=None, **options):
        unknown = set(options) - set(DEFAULTS)
        if unknown:
            raise ValueError('unknown desktop options: ' + ', '.join(sorted(unknown)))
        self.session = session
        self.options = dict(DEFAULTS, **options)
        self.excluded = list(excluded_pids)
        self.log_dir = Path(log_dir) if log_dir else None
        self.lock = threading.RLock()
        self.proc = None
        self.serial = 0
        self.last = None
        self.pointer_guard = pointer_guard
        self._guarding_pointer = False

    def _guard_pointer(self, op, fields):
        """Validate every pointer-producing operation through one public hook.

        pointer_guard(event) receives operation (the original operation name),
        request (the complete original request), and pointer (the pointer action
        to validate). Targeted type/press, fill and check supply a click action;
        other pointer operations keep their own fields, including drag paths.
        The hook may inspect/resolve controls and must raise to refuse an action.
        It must only validate, never execute another pointer action. Assign the
        hook at construction or set desktop.pointer_guard during setup.
        """
        request = {'op': op, **fields}
        if op in ('type', 'press') and fields.get('target') is None:
            return
        if op in ('type', 'press', 'fill', 'check'):
            pointer = {'op': 'click', 'target': fields.get('target')}
        elif op in ('click', 'activate', 'move', 'drag', 'scroll'):
            pointer = dict(request)
        else:
            return
        if self.pointer_guard is None:
            return
        if self._guarding_pointer:
            raise DesktopError('a pointer guard must validate without executing input')
        self._guarding_pointer = True
        try:
            self.pointer_guard({'operation': op, 'request': request, 'pointer': pointer})
        finally:
            self._guarding_pointer = False

    # Helper process --------------------------------------------------------------------------------------------
    def _spawn(self):
        config = dict(self.options, screen=list(self.session.screen), excluded=self.excluded + self.session.service_pids())
        env = dict(self.session.base_env(), **self.session.env())
        log = subprocess.DEVNULL
        if self.log_dir is not None:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log = (self.log_dir / 'desktop-helper.log').open('ab')
        try:
            self.proc = subprocess.Popen([sys.executable, '-B', '-I', str(MODULE), 'helper', json.dumps(config)], env=env,
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                         start_new_session=True, **as_user(self.session.user))
        finally:
            if log is not subprocess.DEVNULL:
                log.close()
        self.buffer = b''

    def _stop_helper(self):
        if self.proc is not None:
            _kill_group(self.proc, grace=1.0)
            for stream in (self.proc.stdin, self.proc.stdout):
                try:
                    stream.close()
                except OSError:
                    pass
        self.proc = None

    def close(self):
        with self.lock:
            self._stop_helper()

    def call(self, op, timeout=None, **fields):
        """One helper request; DesktopError for failures, with timeout=True when the desktop stopped answering."""
        with self.lock:
            self._guard_pointer(op, fields)
            if self.proc is None or self.proc.poll() is not None:
                self._spawn()
            self.serial += 1
            limit = timeout or (self.options['query_timeout'] + 20)
            payload = json.dumps({'id': self.serial, 'op': op, **fields}, ensure_ascii=False).encode() + b'\n'
            try:
                self.proc.stdin.write(payload)
                self.proc.stdin.flush()
            except OSError:
                self._stop_helper()
                raise DesktopError('the desktop helper is not available') from None
            deadline = time.monotonic() + limit
            while b'\n' not in self.buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stop_helper()
                    raise DesktopError(f'the desktop did not answer within {limit:g} s', timeout=True)
                ready, _, _ = select.select([self.proc.stdout], [], [], remaining)
                if ready:
                    chunk = os.read(self.proc.stdout.fileno(), 1 << 20)
                    if not chunk:
                        self._stop_helper()
                        raise DesktopError('the desktop helper exited')
                    self.buffer += chunk
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                answer = json.loads(line)
            except ValueError:
                self._stop_helper()
                raise DesktopError('the desktop helper answered invalid JSON') from None
            if answer.get('id') != self.serial:
                self._stop_helper()
                raise DesktopError('the desktop helper answered out of order')
            if not answer.get('ok'):
                raise DesktopError(answer.get('detail') or 'desktop operation failed', timeout=bool(answer.get('timeout')))
            return answer['result']

    # Convenience --------------------------------------------------------------------------------------------------
    def observe(self, tree=False):
        self.last = self.call('observe', tree=bool(tree))
        return self.last

    def screenshot(self, region=None):
        return self.call('screenshot', **({'region': region} if region is not None else {}))

    def windows(self):
        return self.call('windows')['windows']

    def act(self, request):
        """Run one GUI operation request (already validated against operations())."""
        op = request['op']
        fields = {k: v for k, v in request.items() if k != 'op'}
        # One accessibility query to resolve a target, then the input itself.
        timeout = self.options['query_timeout'] + 30
        if op in ('type', 'fill'):
            timeout += len(str(fields.get('value', ''))) * 0.06
        elif op == 'drag':
            timeout += self.options['query_timeout'] + 10
        return self.call(op, timeout=timeout, **fields)

    def resolve(self, target):
        """Details of the node a target designates: id, role, name, text, description, bounds, visible, states, parent,
        window, window_role and chain ([role, name] from the node up to its top-level window). Object targets are
        matched against a fresh private observation, so the caller's refs stay valid."""
        return self.call('resolve', target=target)

    def inspect(self):
        """A private tree observation (ids i<n> instead of refs) for guards; the public refs stay valid."""
        return self.call('inspect')

    def set_text(self, target, text, confirm=None):
        """Set an editable control's text through AT-SPI and verify it; then optionally invoke the default action of
        the confirm target. One accessibility connection serves the whole step."""
        return self.call('set_text', timeout=3 * self.options['query_timeout'] + 30, target=target, text=text,
                         **({'confirm': confirm} if confirm is not None else {}))

    def clipboard(self, target, limit):
        """Raw bytes of one standard clipboard target (for example UTF8_STRING or image/png), bounded by limit."""
        return base64.b64decode(self.call('clipboard', target=target, limit=int(limit))['base64'])

    def ready(self, minimum=(200, 150)):
        """Desktop readiness: a frame, window or dialog of the product is reachable through AT-SPI."""
        try:
            nodes = self.call('inspect')['nodes']
        except DesktopError:
            return False
        return any(node['role'] in TOP_ROLES and node['bounds'][2] >= minimum[0] and node['bounds'][3] >= minimum[1]
                   for node in nodes)


# -- helper process (product user) ------------------------------------------------------------------------------


def _run(args, *, data=None, timeout=10):
    try:
        done = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise DesktopError(f'{args[0]} did not finish within {timeout:g} s', timeout=True) from None
    except FileNotFoundError:
        raise DesktopError(f'{args[0]} is not installed') from None
    if done.returncode:
        raise DesktopError(f'{args[0]} failed: ' + (done.stderr or done.stdout).decode(errors='replace')[-300:].strip())
    return done.stdout


def _text(value, limit):
    try:
        return ('' if value is None else str(value))[:limit]
    except Exception:
        return ''


def _value(obj, names, default=''):
    for name in names:
        try:
            value = getattr(obj, name)
            return value() if callable(value) else value
        except Exception:
            continue
    return default


def _intersect(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return [x0, y0, max(0, x1 - x0), max(0, y1 - y0)]


class Accessibility:
    """AT-SPI queries: a walk of the visible accessibility tree, and the default action of one node by path."""

    def __init__(self, timeouts=None):
        try:
            import pyatspi
            from gi.repository import Atspi
            if timeouts:
                Atspi.set_timeout(int(timeouts[0]), int(timeouts[1]))
        except Exception as exc:
            raise DesktopError('AT-SPI is not available (python3-pyatspi, at-spi2-core)') from exc
        self.atspi, self.Atspi = pyatspi, Atspi

    def _children(self, obj):
        _value(obj, ('name', 'get_name', 'getName'))
        try:
            count = int(obj.childCount)
        except Exception:
            try:
                count = int(obj.getChildCount())
            except Exception:
                count = 0
        for index in range(max(0, min(count, 2000))):
            try:
                child = obj.getChildAtIndex(index)
            except Exception:
                continue
            if child is not None:
                yield index, child

    def _role(self, obj):
        try:
            name = obj.getRoleName()
            if name:
                return _text(name, 64).casefold()
        except Exception:
            pass
        return 'unknown'

    def _states(self, obj):
        try:
            state = obj.getState()
        except Exception:
            return set()
        names = set()
        for name in STATE_NAMES + ('showing', 'visible', 'sensitive', 'enabled'):
            constant = getattr(self.atspi, 'STATE_' + name.upper().replace('-', '_'), None)
            try:
                if constant is not None and state.contains(constant):
                    names.add(name)
            except Exception:
                continue
        return names

    def _bounds(self, obj):
        try:
            box = obj.queryComponent().getExtents(self.atspi.DESKTOP_COORDS)
            return [int(box.x), int(box.y), max(0, int(box.width)), max(0, int(box.height))]
        except Exception:
            return [0, 0, 0, 0]

    def _pid(self, obj):
        for name in ('get_process_id', 'getProcessId'):
            method = getattr(obj, name, None)
            if callable(method):
                try:
                    value = int(method())
                    if value > 0:
                        return value
                except Exception:
                    pass
        return None

    def snapshot(self, limits):
        """Raw visible nodes in tree order: role, name, text, description, value, states, bounds, visible part,
        depth, path (child indices from the desktop) and parent index."""
        width, height = limits['screen']
        screen = [0, 0, width, height]
        try:
            desktop = self.atspi.Registry.getDesktop(0)
        except Exception as exc:
            raise DesktopError('cannot connect to the accessibility bus') from exc
        nodes, visited, truncated = [], [0], False
        cap, max_depth, text_limit = limits['nodes'], limits['depth'], limits['text']
        excluded = set(limits.get('excluded', ()))

        def walk(obj, depth, path, parent, viewport):
            nonlocal truncated
            if len(nodes) >= cap or visited[0] >= cap * 4:
                truncated = True
                return
            visited[0] += 1
            # Role first: GI registers a returned proxy lazily, and reading its cached state or children before a
            # public property can block until the next event-loop iteration.
            role = self._role(obj)
            states = self._states(obj)
            box = self._bounds(obj)
            if 'showing' not in states:
                late = ('visible' in states and role in LATE_ROLES and viewport is not None
                        and _intersect(box, viewport)[2] > 0 and _intersect(box, viewport)[3] > 0)
                if not late:
                    return
            if role in MENU_ROLES:
                viewport = None
            visible = _intersect(box, viewport) if viewport is not None else None
            if role in VIEWPORT_ROLES and box[2] > 0 and box[3] > 0:
                viewport = box if viewport is None else _intersect(box, viewport)
            onscreen = box[2] > 0 and box[3] > 0 and _intersect(box, screen)[2] > 0 and _intersect(box, screen)[3] > 0
            index = parent
            if onscreen:
                name = _text(_value(obj, ('name', 'get_name', 'getName')), text_limit).strip()
                description = _text(_value(obj, ('description', 'get_description', 'getDescription')), text_limit).strip()
                text = ''
                try:
                    iface = obj.queryText()
                    text = iface.getText(0, min(int(iface.characterCount), text_limit))
                except Exception:
                    pass
                item = {'role': role, 'name': name, 'text': _text(text, text_limit), 'description': description,
                        'states': sorted(states), 'bounds': box, 'depth': depth, 'path': path, 'parent': parent}
                try:
                    item['value'] = round(float(obj.queryValue().currentValue), 4)
                except Exception:
                    pass
                if visible is not None and visible != box:
                    item['visible'] = visible
                nodes.append(item)
                index = len(nodes) - 1
            if depth >= max_depth:
                truncated = True
                return
            for position, child in self._children(obj):
                walk(child, depth + 1, path + [position], index, viewport)

        for app_index, app in self._children(desktop):
            name = _text(_value(app, ('name', 'get_name', 'getName')), 80)
            if name in WM_APPLICATIONS or self._pid(app) in excluded:
                continue
            # Drop cached properties of this application before the walk. (Disabling the cache with
            # set_cache_mask(Cache.NONE) instead stalls the first query of a newly started GTK application.)
            try:
                app.clear_cache()
            except Exception:
                pass
            for index, child in self._children(app):
                walk(child, 1, [app_index, index], None, None)
        return {'nodes': nodes, 'truncated': truncated}

    def locate(self, path, role, name):
        obj = self.atspi.Registry.getDesktop(0)
        try:
            for index in path:
                obj = obj.getChildAtIndex(index)
        except Exception:
            obj = None
        if obj is None or self._role(obj) != role or _text(_value(obj, ('name', 'get_name', 'getName')), 4096).strip() != name:
            raise DesktopError('stale control reference; observe again')
        return obj

    def activate(self, path, role, name):
        obj = self.locate(path, role, name)
        try:
            action = obj.queryAction()
            count = action.nActions
        except Exception:
            count = 0
        if not count:
            raise DesktopError('the control has no accessible action')
        action.doAction(0)
        return {'done': True}

    def set_text(self, path, role, name, text, confirm=None):
        """Replace the text of an editable node through AT-SPI, verify it, then optionally run the default action
        of a second node (for example a dialog's Open button), all on one connection."""
        obj = self.locate(path, role, name)
        try:
            obj.queryComponent().grabFocus()
        except Exception:
            pass
        try:
            editable = obj.queryEditableText()
        except Exception:
            raise DesktopError('the control is not editable text') from None
        if not editable.setTextContents(text):
            raise DesktopError('the control refused the text')
        iface = obj.queryText()
        if iface.getText(0, int(iface.characterCount)) != text:
            raise DesktopError('the control shows different text after the change')
        if confirm:
            # Toolkits update a dialog's affirmative button after the text change; wait until it is enabled.
            button = self.locate(confirm['path'], confirm['role'], confirm['name'])
            deadline = time.monotonic() + 3
            while 'sensitive' not in self._states(button) and time.monotonic() < deadline:
                time.sleep(.1)
            self.activate(confirm['path'], confirm['role'], confirm['name'])
        return {'done': True}

    def perform(self, request):
        op = request['op']
        if op == 'snapshot':
            return self.snapshot(request['limits'])
        if op == 'activate':
            return self.activate(request['path'], request['role'], request['name'])
        if op == 'set_text':
            return self.set_text(request['path'], request['role'], request['name'], request['text'],
                                 request.get('confirm'))
        raise DesktopError('unknown accessibility request')


def accessibility_child():
    """Per-request mode: one accessibility query on a connection that lives only for this process."""
    request = json.loads(sys.stdin.buffer.read(4_000_000))
    try:
        answer = {'ok': True, 'result': Accessibility(timeouts=request.get('timeouts')).perform(request)}
    except Exception as exc:
        answer = {'ok': False, 'detail': str(exc)[:600]}
    sys.stdout.write(json.dumps(answer, ensure_ascii=False))
    sys.stdout.flush()


KEYS = {'control': 'ctrl', 'ctrl': 'ctrl', 'controlormeta': 'ctrl', 'cmd': 'ctrl', 'shift': 'shift', 'alt': 'alt',
        'return': 'Return', 'enter': 'Return', 'escape': 'Escape', 'esc': 'Escape', 'tab': 'Tab', 'space': 'space',
        'backspace': 'BackSpace', 'delete': 'Delete', 'del': 'Delete', 'insert': 'Insert', 'ins': 'Insert',
        'up': 'Up', 'down': 'Down', 'left': 'Left', 'right': 'Right', 'arrowup': 'Up', 'arrowdown': 'Down',
        'arrowleft': 'Left', 'arrowright': 'Right', 'pageup': 'Prior', 'pgup': 'Prior', 'pagedown': 'Next',
        'pgdn': 'Next', 'home': 'Home', 'end': 'End', 'menu': 'Menu', 'contextmenu': 'Menu', 'plus': 'plus',
        'minus': 'minus', 'comma': 'comma', 'period': 'period', 'slash': 'slash', 'backslash': 'backslash',
        'equal': 'equal', 'semicolon': 'semicolon', 'apostrophe': 'apostrophe', 'grave': 'grave'}
SYMBOLS = {'+': 'plus', '-': 'minus', ',': 'comma', '.': 'period', '/': 'slash', '\\': 'backslash', '=': 'equal',
           ';': 'semicolon', "'": 'apostrophe', '`': 'grave', '[': 'bracketleft', ']': 'bracketright', ' ': 'space'}
LAUNCHERS = re.compile(r'^(super|meta|hyper|win|xf86.*)$', re.I)


def keysym(chord):
    """'Control+Shift+S' style chords as xdotool key names; launcher keys are refused."""
    if not isinstance(chord, str) or not chord or len(chord) > 80:
        raise DesktopError('key must be a key name or chord of at most 80 characters')
    value = chord.strip()
    if value in ('+', '-'):
        return SYMBOLS[value]
    if value.endswith('++'):
        value = value[:-2] + '+plus'
    parts = [part.strip() for part in value.split('+')]
    if any(not part for part in parts):
        raise DesktopError('invalid key chord')
    keys = []
    for part in parts:
        low = part.casefold().replace('_', '') if len(part) > 1 else part
        if LAUNCHERS.match(part.replace('_L', '').replace('_R', '')):
            raise DesktopError('desktop launcher keys are not available')
        if low in KEYS:
            keys.append(KEYS[low])
        elif len(part) == 1 and part in SYMBOLS:
            keys.append(SYMBOLS[part])
        elif len(part) == 1 and part.isprintable():
            keys.append(part.lower() if len(parts) > 1 else part)
        elif re.fullmatch(r'[fF](?:[1-9]|1[0-2])', part):
            keys.append(part.upper())
        elif re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{1,30}', part):
            keys.append(part)
        else:
            raise DesktopError('unknown key ' + part[:20])
    return '+'.join(keys)


class Helper:
    """Runs as the product user; answers one JSON request per line."""

    def __init__(self, config):
        self.config = config
        self.width, self.height = config['screen']
        self.refs, self.inspected, self.windows_map, self.counter, self.zoom = {}, {}, {}, 0, None

    # Accessibility --------------------------------------------------------------------------------------------------
    def _accessibility(self, request):
        """One accessibility query in a child process with its own short-lived connection."""
        request = dict(request, timeouts=self.config.get('atspi_timeouts'))
        try:
            done = subprocess.run([sys.executable, '-B', '-I', str(MODULE), 'atspi'], input=json.dumps(request).encode(),
                                  capture_output=True, timeout=self.config['query_timeout'])
        except subprocess.TimeoutExpired:
            raise DesktopError('the accessibility query did not finish within %g s' % self.config['query_timeout'],
                               timeout=True) from None
        try:
            answer = json.loads(done.stdout)
        except ValueError:
            raise DesktopError('the accessibility query failed: ' + done.stderr.decode(errors='replace')[-300:]) from None
        if not answer.get('ok'):
            raise DesktopError(answer.get('detail') or 'the accessibility query failed')
        return answer['result']

    def _snapshot(self):
        limits = {'screen': [self.width, self.height], 'depth': self.config['depth'],
                  'nodes': self.config['tree_nodes'], 'excluded': self.config.get('excluded', []),
                  'text': self.config['tree_text_chars']}
        return self._accessibility({'op': 'snapshot', 'limits': limits})

    def _build(self, raw, tree, ids):
        """Observation nodes and per-node details (path, ancestry) of one raw snapshot; ids(index) names node i."""
        nodes, records, names, truncated = [], {}, {}, raw['truncated']
        for index, item in enumerate(raw['nodes']):
            ref = names[index] = ids(index)
            parent = names.get(item['parent']) if item['parent'] is not None else None
            above = records.get(parent)
            window = ref if item['role'] in WINDOW_ROLES else (above['window'] if above else None)
            states = set(item['states'])
            public = [name for name in STATE_NAMES if name in states]
            if 'sensitive' not in states:
                public.append('disabled')
            records[ref] = {'id': ref, 'path': item['path'], 'role': item['role'], 'name': item['name'],
                            'text': item['text'], 'description': item['description'], 'bounds': item['bounds'],
                            'visible': item.get('visible'), 'states': public, 'parent': parent, 'window': window,
                            'window_role': item['role'] if window == ref else records[window]['role'] if window else None,
                            'chain': [[item['role'], item['name']]] + (above['chain'] if above else [])}
            keep = tree or bool(item['name'] or item['text'] or item['description'] or 'value' in item) \
                or item['role'] not in LAYOUT_ROLES
            if not keep:
                continue
            if not tree and len(nodes) >= self.config['compact_nodes']:
                truncated = True
                continue
            short = self.config['name_chars']
            node = {'ref': ref, 'role': item['role'], 'name': item['name'] if tree else item['name'][:short]}
            for key, limit in (('text', self.config['text_chars']), ('description', short)):
                value = item[key]
                if value and value.strip() != item['name']:
                    node[key] = value if tree else value[:limit]
            if 'value' in item:
                node['value'] = item['value']
            if public:
                node['states'] = public
            node['bounds'] = item['bounds']
            if 'visible' in item:
                node['visible'] = item['visible']
            if tree:
                node['depth'] = item['depth']
                if parent:
                    node['parent'] = parent
                if window and window != ref:
                    node['window'] = window
            nodes.append(node)
        focused = next((n['ref'] for n in nodes if 'focused' in n.get('states', ())), None)
        return {'screen': [self.width, self.height], 'windows': self.list_windows(), 'focused': focused,
                'nodes': nodes, 'truncated': bool(truncated)}, records

    def observe(self, tree=False):
        """A public observation. Refs come from each node's tree position, role and name (stable_refs); refs of
        nodes that are no longer shown, or changed, are refused as stale."""
        raw = self._snapshot()
        refs = stable_refs(raw['nodes'])
        observation, self.refs = self._build(raw, tree, lambda index: refs[index])
        if self.zoom:
            observation['image'] = {'region': list(self.zoom), 'note': 'the next screenshot shows only this rectangle, '
                                    'magnified; operations use full-screen coordinates'}
        return observation

    def inspect(self):
        """A private tree observation (ids i<n>) for runtime guards and target matching; public refs stay valid."""
        observation, self.inspected = self._build(self._snapshot(), True, lambda index: f'i{index + 1}')
        return observation

    def resolve(self, target):
        """Details of the node a target designates: a ref of the latest observe, or a match in a fresh private
        observation (resolving never invalidates the caller's refs)."""
        if isinstance(target, str):
            if not re.fullmatch(r'e[0-9a-f]{8}(?:-\d+)?', target):
                raise DesktopError('a string target must be a ref such as e3fa09c1b; use an object for names')
            target = {'ref': target}
        if not isinstance(target, dict):
            raise DesktopError('target must be a ref or an object')
        known = {'ref', 'role', 'name', 'label', 'text', 'nth', 'exact', 'within'}
        if set(target) - known:
            raise DesktopError('unknown target keys: ' + ', '.join(sorted(set(target) - known)))
        if 'ref' in target:
            if set(target) - {'ref'}:
                raise DesktopError('a ref target takes no other keys')
            record = self.refs.get(target['ref'])
            if record is None:
                raise DesktopError('unknown or stale control ref; observe again')
            return record
        if not any(k in target for k in ('role', 'name', 'label', 'text')):
            raise DesktopError('a target needs ref, role, name, label or text')
        for key in ('role', 'name', 'label', 'text', 'within'):
            if key in target and (not isinstance(target[key], str) or len(target[key]) > 4096):
                raise DesktopError(f'target {key} must be a string')
        nth = target.get('nth', 0)
        if type(nth) is not int or not 0 <= nth <= 100:
            raise DesktopError('target nth must be an integer 0-100')
        exact = target.get('exact')
        if exact is not None and type(exact) is not bool:
            raise DesktopError('target exact must be a boolean')
        prefix = None
        if 'within' in target:
            if target['within'] not in self.refs:
                raise DesktopError('within must be a ref of the latest observe')
            prefix = self.refs[target['within']]['path']
        self.inspect()
        norm = lambda value: ' '.join(str(value or '').casefold().split())

        def same(record, wanted, default_exact):
            exactly = default_exact if exact is None else exact
            values = [norm(record[key]) for key in ('name', 'text', 'description') if record[key]]
            return any(value == norm(wanted) if exactly else norm(wanted) in value for value in values)
        matches = []
        for record in self.inspected.values():
            if prefix is not None and record['path'][:len(prefix)] != prefix:
                continue
            role = record['role']
            if 'role' in target and not (norm(role) == norm(target['role'])
                                         or (norm(target['role']) == 'button' and role == 'push button')):
                continue
            if 'name' in target and not same(record, target['name'], True):
                continue
            if 'label' in target and not same(record, target['label'], True):
                continue
            if 'text' in target and not same(record, target['text'], False):
                continue
            matches.append(record)
        if nth >= len(matches):
            raise DesktopError('no visible control matches the target')
        return matches[nth]

    def set_text(self, request):
        record = self.resolve(request.get('target'))
        text = request.get('text')
        if not isinstance(text, str) or len(text) > MAX_TEXT_INPUT:
            raise DesktopError(f'text must be at most {MAX_TEXT_INPUT} characters')
        confirm = None
        if request.get('confirm') is not None:
            other = self.resolve(request['confirm'])
            confirm = {'path': other['path'], 'role': other['role'], 'name': other['name']}
        return self._accessibility({'op': 'set_text', 'path': record['path'], 'role': record['role'],
                                    'name': record['name'], 'text': text, 'confirm': confirm})

    # Geometry ----------------------------------------------------------------------------------------------------
    def _coordinate(self, value, name, high):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise DesktopError(f'{name} must be a number')
        number = int(round(value))
        if not 0 <= number < high:
            raise DesktopError(f'{name} is outside the screen')
        return number

    def _point(self, request, target_key='target', x_key='x', y_key='y', required=True):
        if request.get(target_key) is not None:
            if x_key in request or y_key in request:
                raise DesktopError(f'give either {target_key} or {x_key}/{y_key}')
            record = self.resolve(request[target_key])
            box = record.get('visible') or record['bounds']
            if box[2] <= 0 or box[3] <= 0:
                raise DesktopError('the control has no visible area')
            x, y = box[0] + max(1, box[2] // 2), box[1] + max(1, box[3] // 2)
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise DesktopError('the control is outside the screen')
            return (x, y), record
        if x_key in request or y_key in request:
            return (self._coordinate(request.get(x_key), x_key, self.width),
                    self._coordinate(request.get(y_key), y_key, self.height)), None
        if required:
            raise DesktopError(f'give {target_key} or {x_key} and {y_key}')
        return None, None

    @staticmethod
    def _held(request):
        modifiers = request.get('modifiers', [])
        if not isinstance(modifiers, list) or any(m not in MODIFIERS for m in modifiers):
            raise DesktopError('modifiers are Shift, Control and Alt')
        return [MODIFIERS[m] for m in dict.fromkeys(modifiers)]

    @staticmethod
    def _wrap(held, args):
        return [*(x for key in held for x in ('keydown', key)), *args, *(x for key in reversed(held) for x in ('keyup', key))]

    def _xdotool(self, args, timeout=20):
        _run(['xdotool', *args], timeout=timeout)

    # Windows ----------------------------------------------------------------------------------------------------
    def list_windows(self):
        try:
            raw = _run(['wmctrl', '-lGp'], timeout=5).decode(errors='replace')
        except DesktopError:
            return []
        try:
            active = int(_run(['xdotool', 'getactivewindow'], timeout=5).strip() or 0)
        except (DesktopError, ValueError):
            active = None
        excluded = set(self.config.get('excluded', []))
        result, mapping, seen = [], {}, {}
        for line in raw.splitlines()[:100]:
            fields = line.split(None, 8)
            if len(fields) < 8:
                continue
            try:
                window, pid = int(fields[0], 16), int(fields[2])
                x, y, w, h = (int(v) for v in fields[3:7])
            except ValueError:
                continue
            if pid in excluded:
                continue
            title = _text(fields[8] if len(fields) > 8 else '', 200)
            # Like control refs, window refs depend only on what is shown (title and its occurrence in the window
            # manager's list), never on X resource ids, so the same desktop always gets the same refs.
            seen[title] = seen.get(title, 0) + 1
            ref = 'w' + hashlib.sha256(json.dumps([title, seen[title]], ensure_ascii=False).encode()).hexdigest()[:8]
            mapping[ref] = window
            result.append({'ref': ref, 'title': title, 'active': window == active, 'bounds': [x, y, w, h]})
        self.windows_map = mapping
        return result

    def _window(self, ref, default_active=False):
        if ref is None and default_active:
            try:
                return int(_run(['xdotool', 'getactivewindow'], timeout=5).strip())
            except (DesktopError, ValueError):
                raise DesktopError('no window is active') from None
        if not isinstance(ref, str) or ref not in self.windows_map:
            self.list_windows()
        if ref not in self.windows_map:
            raise DesktopError('unknown window ref; observe again')
        return self.windows_map[ref]

    def ensure_focus(self):
        """Before untargeted keyboard input: if no window has the keyboard focus, activate the topmost product window."""
        try:
            _run(['xdotool', 'getactivewindow'], timeout=5)
            return
        except DesktopError:
            pass
        windows = self.list_windows()
        try:
            stacking = _run(['xprop', '-root', '_NET_CLIENT_LIST_STACKING'], timeout=5).decode()
            order = [int(v, 16) for v in re.findall(r'0x[0-9a-f]+', stacking)]
        except (DesktopError, ValueError):
            order = []
        known = {w for w in self.windows_map.values()}
        for window in reversed(order):
            if window in known:
                self._xdotool(['windowactivate', str(window)])
                time.sleep(.15)
                return
        if windows:
            self._xdotool(['windowactivate', str(self.windows_map[windows[-1]['ref']])])
            time.sleep(.15)

    # Output -----------------------------------------------------------------------------------------------------
    def screenshot(self, region=None):
        data = _run(['import', '-window', 'root', 'png:-'], timeout=20)
        if not data.startswith(b'\x89PNG'):
            raise DesktopError('the screenshot is not a PNG image')
        if region is None and self.zoom:
            region = self.zoom
        self.zoom = None
        result = {'width': self.width, 'height': self.height}
        if region is not None:
            x0, y0, x1, y1 = self._region(region)
            factor = max(1, min(4, self.width // (x1 - x0), self.height // (y1 - y0)))
            data = _run(['convert', 'png:-', '-crop', f'{x1 - x0}x{y1 - y0}+{x0}+{y0}', '+repage', '-filter', 'point',
                         '-resize', f'{100 * factor}%', 'png:-'], data=data, timeout=20)
            result.update(region=[x0, y0, x1, y1], factor=factor, width=(x1 - x0) * factor, height=(y1 - y0) * factor)
        if len(data) > MAX_SCREENSHOT:
            raise DesktopError('the screenshot exceeds 8 MiB')
        result['png_base64'] = base64.b64encode(data).decode()
        return result

    def _region(self, region):
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            raise DesktopError('region is [x0, y0, x1, y1]')
        x0, x1 = sorted((self._coordinate(region[0], 'x0', self.width), self._coordinate(region[2], 'x1', self.width + 1)))
        y0, y1 = sorted((self._coordinate(region[1], 'y0', self.height), self._coordinate(region[3], 'y1', self.height + 1)))
        if x1 - x0 < 20 or y1 - y0 < 20:
            raise DesktopError('a zoom rectangle is at least 20x20 pixels')
        return x0, y0, x1, y1

    def clipboard(self, target, limit):
        if not isinstance(target, str) or not re.fullmatch(r'[A-Za-z0-9_./+-]{1,64}', target):
            raise DesktopError('invalid clipboard target')
        process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-out', '-target', target],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        content, deadline = bytearray(), time.monotonic() + 5
        try:
            while True:
                if time.monotonic() > deadline:
                    raise DesktopError('the clipboard owner did not answer within 5 s', timeout=True)
                ready, _, _ = select.select([process.stdout], [], [], .1)
                if not ready:
                    continue
                piece = os.read(process.stdout.fileno(), 65536)
                if not piece:
                    if process.wait(timeout=2) != 0:
                        raise DesktopError('the clipboard holds no ' + target + ' data')
                    return {'base64': base64.b64encode(bytes(content)).decode()}
                content.extend(piece)
                if len(content) > limit:
                    raise DesktopError('the clipboard data exceeds its size limit')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
            process.stdout.close()

    # Input --------------------------------------------------------------------------------------------------------
    def click(self, request):
        (x, y), _ = self._point(request)
        button = BUTTONS.get(request.get('button', 'left'))
        count = request.get('click_count', 1)
        if button is None or count not in (1, 2, 3) or type(count) is not int:
            raise DesktopError('invalid button or click_count')
        held = self._held(request)
        self._xdotool(['mousemove', str(x), str(y), 'sleep', '0.05',
                       *self._wrap(held, ['click', '--repeat', str(count), '--delay', '80', str(button)])])
        return {'x': x, 'y': y}

    def activate(self, request):
        record = self.resolve(request.get('target'))
        return self._accessibility({'op': 'activate', 'path': record['path'], 'role': record['role'],
                                    'name': record['name']})

    def type_text(self, value):
        if not isinstance(value, str) or len(value) > MAX_TEXT_INPUT or '\x00' in value:
            raise DesktopError(f'text must be at most {MAX_TEXT_INPUT} characters')
        if not value:
            return
        if '\n' in value:
            # Multi-line text is pasted, as a user would.
            subprocess.run(['xclip', '-selection', 'clipboard', '-in'], input=value.encode(), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=10, check=True)
            self._xdotool(['key', '--clearmodifiers', 'ctrl+v'])
            return
        # Non-ASCII keysyms are remapped per character; a longer delay keeps a later remap from overtaking an earlier
        # key event.
        delay = '12' if value.isascii() else '40'
        self._xdotool(['type', '--clearmodifiers', '--delay', delay, '--', value], timeout=30 + len(value) * 0.05)

    def type(self, request):
        if request.get('target') is not None:
            self.click({'target': request['target']})
        else:
            self.ensure_focus()
        self.type_text(request.get('value'))
        return {'characters': len(request.get('value') or '')}

    def fill(self, request):
        record = self.resolve(request.get('target'))
        box = record.get('visible') or record['bounds']
        if box[2] <= 0 or box[3] <= 0:
            raise DesktopError('the control has no visible area')
        if record['role'] == 'spin button':
            # The accessible box includes the +/- buttons; click the text at its leading edge.
            x, y = box[0] + min(10, max(2, box[2] // 10)), box[1] + box[3] // 2
        else:
            x, y = box[0] + max(1, box[2] // 2), box[1] + max(1, box[3] // 2)
        self._xdotool(['mousemove', str(x), str(y), 'sleep', '0.05', 'click', '1'])
        self._xdotool(['key', '--clearmodifiers', 'ctrl+a'])
        value = request.get('value')
        if value == '':
            self._xdotool(['key', '--clearmodifiers', 'BackSpace'])
        else:
            self.type_text(value)
        if record['role'] == 'spin button':
            # Spin buttons commit their numeric value on focus loss.
            self._xdotool(['key', '--clearmodifiers', 'Tab'])
        return {'characters': len(value or '')}

    def press(self, request):
        chord = keysym(request.get('key'))
        if request.get('target') is not None:
            self.click({'target': request['target']})
        else:
            self.ensure_focus()
        self._xdotool(['key', '--clearmodifiers', '--delay', '60', chord])
        return {'key': chord}

    def check(self, request):
        record = self.resolve(request.get('target'))
        if record['role'] not in CHECKABLE_ROLES:
            raise DesktopError('check requires a check box, toggle, radio button or checkable menu item')
        wanted = request.get('checked', True)
        if type(wanted) is not bool:
            raise DesktopError('checked must be a boolean')
        if ('checked' in record.get('states', ())) != wanted:
            box = record.get('visible') or record['bounds']
            if box[2] <= 0 or box[3] <= 0:
                raise DesktopError('the control has no visible area')
            self._xdotool(['mousemove', str(box[0] + max(1, box[2] // 2)), str(box[1] + max(1, box[3] // 2)), 'sleep',
                           '0.05', 'click', '1'])
            return {'changed': True}
        return {'changed': False}

    def move(self, request):
        (x, y), _ = self._point(request)
        seconds = request.get('seconds', .3)
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 <= seconds <= 3:
            raise DesktopError('seconds must be 0-3')
        self._xdotool(['mousemove', str(x), str(y)])
        time.sleep(float(seconds))
        return {'x': x, 'y': y}

    def drag(self, request):
        (sx, sy), _ = self._point(request)
        (ex, ey), _ = self._point(request, 'to_target', 'to_x', 'to_y')
        via = request.get('via', [])
        if not isinstance(via, list) or len(via) > MAX_VIA or not all(isinstance(p, list) and len(p) == 2 for p in via):
            raise DesktopError(f'via is a list of at most {MAX_VIA} [x, y] points')
        points = [(sx, sy), *((self._coordinate(p[0], 'via x', self.width), self._coordinate(p[1], 'via y', self.height))
                              for p in via), (ex, ey)]
        seconds = request.get('seconds', .6)
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not .1 <= seconds <= 10:
            raise DesktopError('seconds must be 0.1-10')
        button = BUTTONS.get(request.get('button', 'left'))
        if button is None:
            raise DesktopError('invalid button')
        steps = []
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            count = max(2, min(30, math.ceil(math.hypot(bx - ax, by - ay) / 30)))
            steps.extend((round(ax + (bx - ax) * i / count), round(ay + (by - ay) * i / count)) for i in range(1, count + 1))
        steps = steps[:300]
        pause = f'{max(.005, float(seconds) / max(1, len(steps))):.3f}'
        moves = [x for px, py in steps for x in ('mousemove', str(px), str(py), 'sleep', pause)]
        self._xdotool([*self._wrap(self._held(request), ['mousemove', str(sx), str(sy), 'sleep', '0.05', 'mousedown',
                                                          str(button), 'sleep', '0.1', *moves, 'sleep', '0.1', 'mouseup',
                                                          str(button)])], timeout=30 + seconds)
        return {'from': [sx, sy], 'to': [ex, ey]}

    def scroll(self, request):
        point, _ = self._point(request, required=False)
        actions = []
        for key, (negative, positive) in (('delta_y', (4, 5)), ('delta_x', (6, 7))):
            amount = request.get(key, 0)
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount):
                raise DesktopError(f'{key} must be a number')
            notches = min(25, max(1 if amount else 0, round(abs(amount) / 100)))
            if notches:
                actions += ['click', '--repeat', str(notches), '--delay', '60', str(positive if amount > 0 else negative)]
        if not actions:
            raise DesktopError('give delta_y or delta_x')
        lead = ['mousemove', str(point[0]), str(point[1]), 'sleep', '0.05'] if point else []
        self._xdotool([*lead, *actions])
        return {'done': True}

    def zoom_op(self, request):
        self.zoom = list(self._region([request.get('x'), request.get('y'), request.get('to_x'), request.get('to_y')]))
        return {'zoom': list(self.zoom)}

    def focus_window(self, request):
        self._xdotool(['windowactivate', str(self._window(request.get('window')))])
        return {'done': True}

    def maximize(self, request):
        window = self._window(request.get('window'), default_active=True)
        _run(['wmctrl', '-i', '-r', hex(window), '-b', 'add,maximized_vert,maximized_horz'], timeout=5)
        return {'done': True}

    def wait(self, request):
        seconds = request.get('seconds', .5)
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 <= seconds <= 5:
            raise DesktopError('seconds must be 0-5')
        time.sleep(float(seconds))
        return {'seconds': seconds}

    INPUT = ('click', 'activate', 'type', 'fill', 'press', 'check', 'move', 'drag', 'scroll', 'focus_window', 'maximize')

    def handle(self, request):
        op = request.get('op')
        if op == 'observe':
            return self.observe(bool(request.get('tree')))
        if op == 'screenshot':
            return self.screenshot(request.get('region'))
        if op == 'windows':
            return {'windows': self.list_windows()}
        if op == 'resolve':
            record = self.resolve(request.get('target'))
            return {k: v for k, v in record.items() if k != 'path'}
        if op == 'inspect':
            return self.inspect()
        if op == 'set_text':
            result = self.set_text(request)
            time.sleep(self.config['settle'])
            return result
        if op == 'clipboard':
            return self.clipboard(request.get('target'), request.get('limit', 400_000))
        if op == 'zoom':
            return self.zoom_op(request)
        if op == 'wait':
            return self.wait(request)
        if op in self.INPUT:
            result = getattr(self, op)(request)
            time.sleep(self.config['settle'])
            return result
        raise DesktopError('unknown desktop operation')


def helper_main(config):
    # The product runs as this user; forbid ptrace and /proc access to this process's pipes.
    try:
        if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'prctl')
    except (OSError, AttributeError) as exc:
        sys.stderr.write(f'cannot protect the desktop helper: {exc}\n')
        return 2
    helper = Helper(config)
    for line in iter(lambda: sys.stdin.buffer.readline(4_000_000), b''):
        request_id = None
        try:
            request = json.loads(line)
            request_id = request.get('id')
            answer = {'id': request_id, 'ok': True, 'result': helper.handle(request)}
        except DesktopError as exc:
            answer = {'id': request_id, 'ok': False, 'detail': str(exc)[:600], 'timeout': exc.timeout}
        except Exception as exc:
            answer = {'id': request_id, 'ok': False, 'detail': f'{type(exc).__name__}: {exc}'[:600]}
        sys.stdout.write(json.dumps(answer, ensure_ascii=False) + '\n')
        sys.stdout.flush()
    return 0


def session_main(args):
    """A development desktop for the product user (for example your own container): start the session, run
    the command inside it, stop the session when the command ends."""
    width, height = (int(v) for v in args.screen.lower().split('x')[:2])
    session = DesktopSession(user=args.user, screen=(width, height), display=args.display, root=args.root,
                             maximize=not args.no_maximize, center_dialogs=not args.no_center_dialogs,
                             audio=args.audio).start()
    stop = lambda *_: (_ for _ in ()).throw(SystemExit(143))
    signal.signal(signal.SIGTERM, stop)
    try:
        env = dict(os.environ, **session.env())
        return subprocess.call(args.command, env=env, **as_user(args.user))
    finally:
        session.close()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['helper']:
        return helper_main(json.loads(argv[1]))
    if argv[:1] == ['atspi']:
        accessibility_child()
        return 0
    parser = argparse.ArgumentParser(description='Private desktop session for a desktop product.')
    sub = parser.add_subparsers(dest='mode', required=True)
    session = sub.add_parser('session')
    session.add_argument('--display')
    session.add_argument('--root')
    session.add_argument('--screen', default='1280x900')
    session.add_argument('--user', default='')
    session.add_argument('--audio', action='store_true')
    session.add_argument('--no-maximize', action='store_true')
    session.add_argument('--no-center-dialogs', action='store_true')
    session.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command[:1] == ['--']:
        args.command = args.command[1:]
    if not args.command:
        parser.error('give the command to run inside the session')
    return session_main(args)


if __name__ == '__main__':
    raise SystemExit(main())
