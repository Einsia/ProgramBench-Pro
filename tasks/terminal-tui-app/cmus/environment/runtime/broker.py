#!/usr/bin/env python3
"""cmus black-box runtime: PTY, native Unix control socket, and confined media/state exchange."""
from __future__ import annotations

import base64
import codecs
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import select
import shlex
import socket
import signal
import shutil
import stat
import struct
import subprocess
import sys
import termios
import threading
import time
import unicodedata

import http.server
import socketserver

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blackbox_runtime as runtime  # noqa: E402
import safe_fs  # noqa: E402

import pyte  # noqa: E402
from pyte.screens import Margins  # noqa: E402
from wcwidth import wcwidth  # noqa: E402

PRODUCT = 'cmus'
COLUMNS, ROWS = 120, 36
TERM = 'xterm-256color'
MAX_REQUEST_BYTES = 12 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_KEY_BATCH, MAX_TEXT, MAX_STYLES = 256, 4096, 400
RPC_TIMEOUT_SEC, QUIET, SETTLE_MAX = 90, 0.15, 2.0
DECCKM = 1 << 5
ORIGIN = '/workspace'
CLI_OPTIONS = ('--help', '--version', '--plugins')
STATE_FILES = ('rc','autosave','lib.pl','queue.pl','resume','command-history','search-history','playlists')
EXTENSIONS = {'.wav','.flac','.fla','.mp3','.ogg','.opus','.m4a','.aac','.aiff','.aif','.wv','.cue','.m3u','.m3u8','.pls','.list','.txt'}
TEXT_EXTENSIONS = {'.cue','.m3u','.m3u8','.pls','.list','.txt'}


# -- keys ------------------------------------------------------------------------------------------------------
SIMPLE = {'enter': '\r', 'return': '\r', 'escape': '\x1b', 'esc': '\x1b', 'tab': '\t', 'backspace': '\x7f',
          'bs': '\x7f', 'space': ' ', 'colon': ':', 'slash': '/'}
CURSOR = {'up': 'A', 'down': 'B', 'right': 'C', 'left': 'D', 'home': 'H', 'end': 'F'}
TILDE = {'insert': 2, 'delete': 3, 'pageup': 5, 'pagedown': 6, 'f5': 15, 'f6': 17, 'f7': 18, 'f8': 19, 'f9': 20,
         'f10': 21, 'f11': 23, 'f12': 24}
SS3_FUNCTION = {'f1': 'P', 'f2': 'Q', 'f3': 'R', 'f4': 'S'}
ALIASES = {'arrowup': 'up', 'arrowdown': 'down', 'arrowleft': 'left', 'arrowright': 'right', 'del': 'delete',
           'ins': 'insert', 'pgup': 'pageup', 'pgdn': 'pagedown', 'page_up': 'pageup', 'page_down': 'pagedown',
           'return': 'enter'}
MODIFIERS = {'control': 'ctrl', 'ctrl': 'ctrl', 'alt': 'alt', 'meta': 'alt', 'option': 'alt', 'shift': 'shift'}
KEY_NAMES = ['Enter', 'Escape', 'Tab', 'Backspace', 'Space', 'Up', 'Down', 'Left', 'Right', 'Home', 'End',
             'PageUp', 'PageDown', 'Insert', 'Delete'] + [f'F{i}' for i in range(1, 13)]
KEY_HELP = ('One key: a single printable character (for example j, :, / or Q), or a name: ' + ', '.join(KEY_NAMES) +
            ' (case-insensitive), optionally combined with Control+, Alt+ or Shift+ (for example Control+U, '
            'Alt+f, Shift+Tab).')


def split_key(name):
    if len(name) == 1:
        return set(), name
    if '+' in name[:-1]:
        parts = name.split('+')
        if parts[-1] == '' and name.endswith('++'):
            parts = parts[:-2] + ['+']
    else:
        match = re.fullmatch(r'(?i)((?:(?:control|ctrl|alt|meta|option|shift)-)+)(.+)', name)
        parts = (match.group(1).split('-')[:-1] + [match.group(2)]) if match else [name]
    mods = set()
    for part in parts[:-1]:
        if part.lower() not in MODIFIERS:
            raise ValueError(f'unknown modifier {part!r} in key {name!r}')
        mods.add(MODIFIERS[part.lower()])
    return mods, parts[-1]


def key_bytes(name, application_cursor=False):
    """Terminal input of one key or chord, as an xterm sends it."""
    if not isinstance(name, str) or not name or len(name) > 32:
        raise ValueError('each key must be a key name or one character')
    mods, base = split_key(name)
    if not base:
        raise ValueError(f'invalid key {name!r}')
    code = 1 + ('shift' in mods) + 2 * ('alt' in mods) + 4 * ('ctrl' in mods)
    if len(base) == 1:
        if not base.isprintable():
            raise ValueError(f'{name!r} is not a printable key; use a key name such as Enter or Tab')
        char = base
        if 'shift' in mods:
            if not char.isalpha():
                raise ValueError(f'Shift is only supported with letters and named keys: {name!r}')
            char = char.upper()
        if 'ctrl' in mods:
            if char.isalpha():
                char = chr(ord(char.upper()) & 0x1f)
            elif char in '@[\\]^_ ':
                char = chr(ord(char) & 0x1f) if char != ' ' else '\x00'
            elif char == '?':
                char = '\x7f'
            else:
                raise ValueError(f'unsupported control chord {name!r}')
        return ('\x1b' if 'alt' in mods else '') + char
    key = ALIASES.get(base.lower(), base.lower())
    if key in SIMPLE:
        sequence = SIMPLE[key]
        if mods - {'alt'}:
            if mods == {'shift'} and key == 'tab':
                return '\x1b[Z'
            if mods == {'ctrl'} and key == 'space':
                return '\x00'
            if mods == {'ctrl'} and key == 'backspace':
                return '\x08'
            raise ValueError(f'unsupported chord {name!r}')
        return ('\x1b' if 'alt' in mods else '') + sequence
    if key in CURSOR:
        if code > 1:
            return f'\x1b[1;{code}{CURSOR[key]}'
        return ('\x1bO' if application_cursor else '\x1b[') + CURSOR[key]
    if key in SS3_FUNCTION:
        return f'\x1b[1;{code}{SS3_FUNCTION[key]}' if code > 1 else '\x1bO' + SS3_FUNCTION[key]
    if key in TILDE:
        return f'\x1b[{TILDE[key]};{code}~' if code > 1 else f'\x1b[{TILDE[key]}~'
    raise ValueError(f'unknown key {name!r}; see help for key names')


# -- terminal emulation ----------------------------------------------------------------------------------------
ALTERNATE_SCREEN = {47, 1047, 1049}


class XtermScreen(pyte.Screen):
    """pyte 0.8.2 plus the xterm-256color behaviour curses applications rely on."""

    def __init__(self, columns, lines):
        super().__init__(columns, lines)
        self.last_graphic = None
        self.saved_primary = None

    def draw(self, data):
        run = []
        for char in data:
            width = wcwidth(char)
            if width > 0 or (width == 0 and unicodedata.combining(char)):
                run.append(char)
                continue
            if run:
                super().draw(''.join(run))
                self.last_graphic = run[-1]
                run = []
            if width == 0:
                self.join_previous(char)
        if run:
            super().draw(''.join(run))
            self.last_graphic = run[-1]

    def join_previous(self, char):
        line = self.buffer[self.cursor.y]
        x = min(self.cursor.x, self.columns)
        for column in (x - 1, x - 2):
            if column >= 0 and line[column].data:
                line[column] = line[column]._replace(data=line[column].data + char)
                return

    def scroll_up(self, count=None, *rest, **_):
        if rest:
            return
        top, bottom = self.margins or Margins(0, self.lines - 1)
        for _ in range(min(max(count or 1, 1), self.lines)):
            for y in range(top, bottom):
                self.buffer[y] = self.buffer[y + 1]
            self.buffer.pop(bottom, None)
        self.dirty.update(range(self.lines))

    def scroll_down(self, count=None, *rest, **_):
        if rest:
            return
        top, bottom = self.margins or Margins(0, self.lines - 1)
        for _ in range(min(max(count or 1, 1), self.lines)):
            for y in range(bottom, top, -1):
                self.buffer[y] = self.buffer[y - 1]
            self.buffer.pop(top, None)
        self.dirty.update(range(self.lines))

    def repeat_character(self, count=None, *rest, **_):
        if self.last_graphic and not rest:
            self.draw(self.last_graphic * min(max(count or 1, 1), self.columns * self.lines))

    def set_mode(self, *modes, **kwargs):
        if kwargs.get('private') and ALTERNATE_SCREEN & set(modes) and self.saved_primary is None:
            self.saved_primary = ({y: dict(line) for y, line in self.buffer.items()}, self.cursor.x, self.cursor.y)
            self.buffer.clear()
            self.dirty.update(range(self.lines))
        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes, **kwargs):
        if kwargs.get('private') and ALTERNATE_SCREEN & set(modes) and self.saved_primary is not None:
            lines, x, y = self.saved_primary
            self.saved_primary = None
            self.buffer.clear()
            for row, cells in lines.items():
                if row < self.lines:
                    self.buffer[row].update(cells)
            self.cursor.x, self.cursor.y = min(x, self.columns), min(y, self.lines - 1)
            self.dirty.update(range(self.lines))
        super().reset_mode(*modes, **kwargs)


class XtermStream(pyte.Stream):
    csi = dict(pyte.Stream.csi, S='scroll_up', T='scroll_down', b='repeat_character')


def flags(style):
    fg, bg, bold, italics, underscore, reverse = style
    names = [n for n, v in (('bold', bold), ('italic', italics), ('underline', underscore), ('reverse', reverse)) if v]
    return names + (['fg=' + str(fg)] if fg != 'default' else []) + (['bg=' + str(bg)] if bg != 'default' else [])


class Terminal:
    def __init__(self, columns, rows):
        self.columns, self.rows = columns, rows
        self.screen = XtermScreen(columns, rows)
        self.stream = XtermStream(self.screen)
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.lock = threading.Lock()
        self.last_output = time.monotonic()
        self.received = 0

    def feed(self, data):
        with self.lock:
            self.stream.feed(self.decoder.decode(data))
            self.last_output = time.monotonic()
            self.received += len(data)

    def resize(self, columns, rows):
        with self.lock:
            self.columns, self.rows = columns, rows
            self.screen.resize(rows, columns)

    def application_cursor(self):
        with self.lock:
            return DECCKM in self.screen.mode

    def line(self, y):
        row, out, skip = self.screen.buffer[y], [], False
        for x in range(self.columns):
            if skip:
                skip = False
                continue
            data = row[x].data or ' '
            out.append(data)
            skip = wcwidth(data[0]) == 2
        return ''.join(out).rstrip()

    def drawn(self):
        with self.lock:
            return any(self.line(y).strip() for y in range(self.rows))

    def observe(self, process, redact):
        with self.lock:
            lines = [redact(self.line(y)) for y in range(self.rows)]
            spans = []
            for y in range(self.rows):
                row, current = [], None
                for x in range(self.columns):
                    cell = self.screen.buffer[y][x]
                    style = (cell.fg, cell.bg, cell.bold, cell.italics, cell.underscore, cell.reverse)
                    if current and current[2] == style:
                        current[1] = x + 1
                    else:
                        current = [x, x + 1, style]
                        row.append(current)
                spans.append(row)

            def text(y, start, end):
                return ''.join(self.screen.buffer[y][x].data for x in range(start, end))
            weight = {}
            for y, row in enumerate(spans):
                for start, end, style in row:
                    visible = len(text(y, start, end).strip())
                    if visible:
                        weight[style] = weight.get(style, 0) + visible
            base = max(weight, key=weight.get) if weight else None
            styles = []
            for y, row in enumerate(spans):
                for start, end, style in row:
                    value = text(y, start, end)
                    if style == base or not value.strip() or (base is None and not flags(style)):
                        continue
                    styles.append({'row': y, 'columns': [start, end], 'text': redact(value),
                                   'style': flags(style) or ['default']})
            cursor = self.screen.cursor
            result = {'size': [self.columns, self.rows],
                      'cursor': {'row': cursor.y, 'column': min(cursor.x, self.columns - 1),
                                 'hidden': bool(cursor.hidden)},
                      'screen': [f'{y:02d}|{line}' for y, line in enumerate(lines)],
                      'styles': styles[:MAX_STYLES]}
            if len(styles) > MAX_STYLES:
                result['styles_truncated'] = True
            if base is not None and flags(base):
                result['base_style'] = flags(base)
        result['process'] = process
        return result


def blank_observation(process):
    return {'size': [COLUMNS, ROWS], 'cursor': {'row': 0, 'column': 0, 'hidden': False},
            'screen': [f'{y:02d}|' for y in range(ROWS)], 'styles': [], 'process': process}


# -- product in a pseudo-terminal ------------------------------------------------------------------------------
class TerminalProduct(runtime.Product):
    def __init__(self, config, *, log):
        super().__init__(config, log=log, env={'TERM':TERM,'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC'})
        self.terminal=self.master=self.reader=self.pulse=None
        self.closing=threading.Event()

    @property
    def workspace(self): return Path(self.directories['DATA_DIR'])/'workspace'
    @property
    def cmus_config(self): return Path(self.directories['DATA_DIR'])/'config'/'cmus'
    @property
    def cmus_socket(self): return Path(self.directories['DATA_DIR'])/'control.sock'

    def environment(self):
        env=super().environment()
        data=Path(self.directories['DATA_DIR'])
        env.update(COLUMNS=str(COLUMNS),LINES=str(ROWS),HOME=str(self.workspace),CMUS_SOCKET=str(self.cmus_socket),
                   XDG_CONFIG_HOME=str(data/'config'),XDG_CACHE_HOME=str(data/'cache'),
                   PULSE_SERVER='unix:'+str(data/'pulse.sock'),XDG_RUNTIME_DIR=str(data/'run'))
        return env

    def identity(self):
        a=self.account()
        return dict(user=a.pw_uid,group=a.pw_gid,extra_groups=[]) if self.switching() else {}

    def prepare(self,fresh):
        super().prepare(fresh)
        account = self.account()
        for parts in (('workspace',), ('workspace', 'inbox'), ('workspace', 'outbox'), ('config',), ('cache',), ('run',)):
            with safe_fs.directory(self.directories['DATA_DIR'], parts, create=True,
                                   uid=account.pw_uid, gid=account.pw_gid, mode=0o700):
                pass

    def start(self,fresh=False):
        self.stop();self.prepare(fresh)
        self.ready=False;self.starts+=1;self.terminal=Terminal(COLUMNS,ROWS)
        script=self.solution/'start.sh'
        if not script.is_file(): self.detail='start.sh does not exist in the solution directory';return False
        # A real PulseAudio null sink supplies ordinary, real-time audio output without a sound device.
        data=Path(self.directories['DATA_DIR'])
        for name in ('pulse.sock','control.sock'):
            runtime.unlink_entry(data, name, missing_ok=True)
        self.pulse=subprocess.Popen(['pulseaudio','--daemonize=no','--exit-idle-time=-1','--use-pid-file=no','-n',
            '-L','module-native-protocol-unix socket='+str(data/'pulse.sock')+' auth-anonymous=1',
            '-L','module-null-sink sink_name=default'],env=self.environment(),cwd=str(self.workspace),
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,**self.identity())
        deadline=time.monotonic()+5
        while not (data/'pulse.sock').exists() and self.pulse.poll() is None and time.monotonic()<deadline:time.sleep(.03)
        master,slave=pty.openpty()
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',ROWS,COLUMNS,0,0))
        if self.switching():os.fchown(slave,self.account().pw_uid,self.account().pw_gid)
        try:
            self.proc=subprocess.Popen(['setsid','--ctty',str(script)],cwd=str(self.workspace),env=self.environment(),
                stdin=slave,stdout=slave,stderr=slave,umask=0o077,**self.identity())
        except OSError as exc:
            os.close(master);self.proc=None;self.detail='start.sh could not be executed: '+str(exc.strerror);return False
        finally:os.close(slave)
        os.set_blocking(master,False);self.master=master;self.closing=threading.Event()
        self.reader=threading.Thread(target=self.pump,args=(master,self.terminal,self.closing),daemon=True);self.reader.start()
        self.detail='starting';return True

    def pump(self,fd,terminal,closing):
        while not closing.is_set():
            try:
                ready,_,_=select.select([fd],[],[],.1)
                if not ready:continue
                data=os.read(fd,65536)
                if not data:return
            except BlockingIOError:continue
            except (OSError,ValueError):return
            terminal.feed(data);self.log.write(data)

    def stop(self,grace=5):
        if self.running():
            try: native(self,'quit',timeout=1)
            except Exception: pass
            try:self.proc.wait(2)
            except subprocess.TimeoutExpired:pass
        super().stop(grace)
        self.closing.set()
        if self.reader:self.reader.join(1);self.reader=None
        if self.master is not None:
            try:os.close(self.master)
            except OSError:pass
            self.master=None
        if self.pulse:
            try:os.killpg(self.pulse.pid,signal.SIGTERM);self.pulse.wait(2)
            except (ProcessLookupError,subprocess.TimeoutExpired):
                try:os.killpg(self.pulse.pid,signal.SIGKILL);self.pulse.wait(2)
                except (ProcessLookupError,subprocess.TimeoutExpired):pass
            self.pulse=None

    def write(self,data):
        if not self.running() or self.master is None:raise ValueError('application is not running; use restart')
        pending=memoryview(data.encode());deadline=time.monotonic()+5
        while pending:
            try:pending=pending[os.write(self.master,pending[:4096]):]
            except BlockingIOError:
                if time.monotonic()>deadline:raise ValueError('application did not read its terminal input')
                time.sleep(.01)

    def resize(self,cols,rows):
        if not self.running():raise ValueError('application is not running')
        self.terminal.resize(cols,rows);fcntl.ioctl(self.master,termios.TIOCSWINSZ,struct.pack('HHHH',rows,cols,0,0))
    def control_ready(self):
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                sock.settimeout(.1);sock.connect(str(self.cmus_socket))
            return True
        except OSError:return False
    def process(self):
        return 'running' if self.running() else ('not started' if self.proc is None else f'exited with status {self.proc.returncode}')


def native(product,command,timeout=8):
    """The real cmus-remote wire protocol: one command line, an empty response line as terminator."""
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout);sock.connect(str(product.cmus_socket));sock.sendall(command.encode()+b'\n')
        reply=bytearray()
        while True:
            data=sock.recv(65536)
            if not data:raise ValueError('native control interface closed before its response ended')
            reply.extend(data)
            if len(reply)>MAX_FILE_BYTES:raise ValueError('native control response exceeded 8 MiB')
            if reply==b'\n' or reply.endswith(b'\n\n'):return bytes(reply[:-1]).decode('utf-8','replace')


def printable(value,field,limit=4096):
    if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError(field+' must be bounded printable text')
    return value


def parts(value):
    printable(value,'path')
    if value==ORIGIN or value in ('','.'):return []
    if value.startswith(ORIGIN+'/'):value=value[len(ORIGIN)+1:]
    if value.startswith('/') or '\\' in value:raise ValueError('path must stay inside /workspace')
    out=value.split('/')
    if any(p in ('','..','.') or len(p.encode())>240 for p in out):raise ValueError('invalid workspace path')
    return out


def entry(path, name):
    with runtime.open_directory(path.parent) as parent:
        info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
    kind = 'symlink' if stat.S_ISLNK(info.st_mode) else 'directory' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'other'
    return {'name': name, 'type': kind, 'size': info.st_size if kind == 'file' else 0, 'mode': stat.S_IMODE(info.st_mode)}


def files(product, request, redact):
    path = request.get('path', ORIGIN)
    components = parts(path)
    action = request.get('action', 'list')
    if action == 'read' and Path(path).suffix.lower() not in EXTENSIONS:
        raise ValueError('file type is not available for download')
    result = safe_fs.snapshot(product.workspace, components, action, origin=ORIGIN,
                              max_read=MAX_FILE_BYTES, max_hash=0, max_entries=4096,
                              uid=product.account().pw_uid, casefold=False)
    if action == 'read':
        content = base64.b64decode(result['body_base64'])
        out = {'path': path}
        if Path(path).suffix.lower() in TEXT_EXTENSIONS:
            out['text'] = redact(content.decode('utf-8', 'replace'))
            content = out['text'].encode()
        out.update(body_base64=base64.b64encode(content).decode(), size=len(content))
        return out
    def compact(row, name):
        return {**{k: row[k] for k in ('type', 'size', 'mode')}, 'name': name}
    if action == 'stat':
        return compact(result, components[-1] if components else product.workspace.name)
    prefix = result['path'].rstrip('/') + '/'
    return {'path': path, 'entries': sorted([compact(row, row['path'][len(prefix):])
                                             for row in result['entries']], key=lambda row: row['name'])}


def upload(product, request):
    name = printable(request['filename'], 'filename', 240)
    if not name or name in ('.', '..') or '/' in name or '\\' in name:
        raise ValueError('filename must be a basename')
    if Path(name).suffix.lower() not in EXTENSIONS:
        raise ValueError('file type is not accepted')
    content = base64.b64decode(request['base64'], validate=True)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError('upload exceeds 8 MiB')
    if Path(name).suffix.lower() in TEXT_EXTENSIONS:
        content = content.replace(ORIGIN.encode(), str(product.workspace).encode())
    components = parts(request.get('directory', 'inbox'))
    account = product.account()
    with safe_fs.directory(product.workspace, components, create=True, uid=account.pw_uid, gid=account.pw_gid) as parent:
        runtime.atomic_write(parent, name, content, uid=account.pw_uid, gid=account.pw_gid, mode=0o600)
        stamp = request.get('mtime', 1704067200)
        with runtime.open_relative(parent, name) as fd:
            info = os.fstat(fd)
            if info.st_nlink != 1 or info.st_uid != account.pw_uid:
                raise ValueError('the uploaded file changed during setup')
            runtime.set_metadata(fd, ns=(int(stamp * 1e9), int(stamp * 1e9)))
    return {'path': ORIGIN + '/' + '/'.join(components + [name]), 'size': len(content)}


def state(product, request, redact):
    name = request['file']
    if name not in STATE_FILES:
        raise ValueError('unknown cmus state file')
    rel = ['config', 'cmus', name]
    if name == 'playlists' and request.get('name'):
        value = printable(request['name'], 'playlist name', 240)
        if '/' in value or '\\' in value or value in ('.', '..'):
            raise ValueError('playlist name must be a basename')
        rel.append(value)
    try:
        with safe_fs.directory(product.directories['DATA_DIR'], rel[:-1]) as parent:
            info = os.stat(rel[-1], dir_fd=parent, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                with runtime.open_relative(parent, rel[-1], directory=True) as folder:
                    entries = []
                    for child, st in runtime.list_directory(folder):
                        kind = 'symlink' if stat.S_ISLNK(st.st_mode) else 'directory' if stat.S_ISDIR(st.st_mode) else 'file' if stat.S_ISREG(st.st_mode) else 'other'
                        entries.append({'name':child,'type':kind,'size':st.st_size if kind=='file' else 0,'mode':stat.S_IMODE(st.st_mode)})
                return {'exists':True,'file':name,'entries':sorted(entries,key=lambda row:row['name'])}
            content = safe_fs.read(parent, rel[-1], limit=MAX_FILE_BYTES, uid=product.account().pw_uid)
    except FileNotFoundError:
        return {'exists':False,'file':name}
    return {'exists':True,'file':name,'text':redact(content.decode('utf-8','replace'))}


def field(kind,description,required=False,**kw):return dict(type=kind,description=description,**({'required':True} if required else {}),**kw)
def op(kind,summary,**fields):return dict(kind=kind,summary=summary,fields=fields)
OPERATIONS=runtime.check_operations({
 'help':op('info','Describe all operations, fields, limits and reference controls.'),
 'status':op('lifecycle','Report whether the application is running and has drawn its terminal.'),
 'reset':op('lifecycle','Start a new application instance with fresh data and an empty inbox/outbox.'),
 'restart':op('lifecycle','Restart start.sh with existing data, saving through the native quit command first.'),
 'screen':op('observe','Observe the settled terminal rows NN|text, style spans, cursor and process state.'),
 'key':op('gui','Press a key and observe the settled terminal.',key=field('string',KEY_HELP,True)),
 'keys':op('gui','Press 1-256 keys in order and observe the settled terminal.',keys=field('array',KEY_HELP,True,items={'type':'string'})),
 'type':op('gui','Type literal printable text and observe the settled terminal.',text=field('string','1-4096 printable characters; Enter is a separate key.',True)),
 'wait':op('gui','Wait for asynchronous output and observe the terminal.',seconds=field('number','0-3 seconds, default 0.2.')),
 'resize':op('gui','Resize the terminal and observe the result.',columns=field('integer','40-240 columns.',True),rows=field('integer','10-80 rows.',True)),
 'remote':op('info','Send one native cmus-remote command to CMUS_SOCKET and return stdout.',command=field('string','One line of at most 1000 UTF-8 bytes. status, format_print and save -L - are native commands. Paths prefixed /workspace are translated to the instance workspace.',True)),
 'upload':op('files','Upload an audio or playlist file into the workspace.',filename=field('string','Basename of the uploaded file.',True),base64=field('string','Base64 bytes, at most 8 MiB decoded. In text/playlist files, /workspace path aliases expand to the instance path; reads map them back.',True),directory=field('string','Workspace-relative folder; default inbox. Parents are created.'),mtime=field('integer','Fixed Unix modification time; default 1704067200.')),
 'workspace':op('files','List, stat or read user media and playlist files without following links.',action=field('string','Default list.',enum=['list','tree','stat','read']),path=field('string','Workspace-relative path or /workspace; default workspace root.')),
 'state':op('files','Read the native cmus persistent text files and named playlists.',file=field('string','Native filename under DATA_DIR/config/cmus.',True,enum=list(STATE_FILES)),name=field('string','For file=playlists, read a particular playlist basename.')),
 'cli':op('info','Run start.sh with one native terminating command-line option.',option=field('string','The option passed as one argument to start.sh.',True,enum=list(CLI_OPTIONS))),
 'manual':op('info','Read the upstream user documentation also available through the reference help.',page=field('string','Manual page.',True,enum=['cmus','cmus-remote','cmus-tutorial'])),
})
REFERENCE_CONTROLS={
 'version':'cmus 2.13.0',
 'keys':'Views 1-7: library tree, sorted library, playlists, queue, browser, filters, settings. Tab switches panes. j/k or Down/Up move, g/G or Home/End jump, Space marks tracks or expands tree items, Enter activates. a: copy to library; y: copy to marked playlist; e: append to queue; E: prepend to queue. D or Delete removes, p/P moves. x plays, c pauses, v stops, b/z move tracks, B/Z move albums, +/- changes volume. m cycles scope, r repeat, s shuffle, f follow, C continue, M source, o sorted playback. : opens commands; / and ? search, n/N navigate matches, F and L start filters.',
 'commands':'The same cmus commands work in the : console and the native remote interface. add -l/-p/-q/-Q, save -l/-L/-p/-q, load -l, pl-create/import/export/rename/delete, filter/live-filter/fset/factivate, mark/unmark/invert, set/toggle, bind/unbind/showbind, view, player-play/pause/pause-playback/stop/next/prev, seek, vol, mute, update-cache, win-* navigation and editing. The remote-only commands status and format_print expose playback metadata, settings and format strings. Full syntax is in manual(cmus) and manual(cmus-remote).',
 'boundaries':'External program execution and reading/writing outside the instance data are blocked. Built-in themes remain available. Playback uses a PulseAudio null sink. Uploaded audio is decoded by the ordinary cmus plugins.'}

class Runtime:
    def __init__(self,config):
        self.config=config;self.lock=threading.RLock();self.log=runtime.BoundedLog(config.log_dir)
        self.audit=runtime.Audit(Path(config.log_dir)/'rpc-audit.jsonl');self.product=TerminalProduct(config,log=self.log)
        p=self.product
        self.roots=sorted([(str(p.workspace),ORIGIN),(str(p.cmus_config),'[config]'),(str(p.directories['DATA_DIR']),'[data]'),(str(config.state),'[private]'),(str(config.solution),'[private]'),(str(config.work),'[private]'),(str(config.log_dir),'[private]'),(str(HERE),'[private]')],key=lambda x:-len(x[0]))
    def redact(self,s):
        for root,name in self.roots:s=str(s).replace(root,name)
        return s
    def redact_value(self,v):
        if isinstance(v,str):return self.redact(v)
        if isinstance(v,list):return [self.redact_value(x) for x in v]
        if isinstance(v,dict):return {k:self.redact_value(x) for k,x in v.items()}
        return v
    def start(self,fresh=True):
        if self.product.start(fresh):runtime.wait_until(self.product,lambda:self.product.control_ready() and self.product.terminal.drawn(),deadline=self.config.ready_timeout,failure='application did not draw its interface')
        return self.redact_value(self.product.status())
    def close(self):self.product.stop()
    def observe(self):
        terminal=self.product.terminal
        if terminal is None:return blank_observation(self.product.process())
        end=time.monotonic()+SETTLE_MAX
        while time.monotonic()<end and time.monotonic()-terminal.last_output<QUIET:time.sleep(.02)
        return terminal.observe(self.product.process(),self.redact)
    def dispatch(self,data):
        which=runtime.validate(OPERATIONS,data)
        if which=='help':return runtime.help_document(PRODUCT,'terminal',OPERATIONS,reference_controls=REFERENCE_CONTROLS,limits={'request_bytes':MAX_REQUEST_BYTES,'file_bytes':MAX_FILE_BYTES,'file_extensions':sorted(EXTENSIONS)},notes=['/workspace is a display alias; it is expanded in remote commands and typed text. All media paths may also be relative to the current browser directory.','Startup contract: start.sh draws the terminal and listens to the native cmus line protocol on CMUS_SOCKET. XDG_CONFIG_HOME is DATA_DIR/config, media lives in DATA_DIR/workspace.'])
        if which=='manual':return {'page':data['page'],'text':json.loads((HERE/'manuals.json').read_text())[data['page']]}
        if which=='status':return self.redact_value(self.product.status())
        with self.lock:
            if which in ('restart','reset'):return self.start(which=='reset')
            if which=='screen':return self.observe()
            if which in ('key','keys'):
                keys=[data['key']] if which=='key' else data['keys']
                if not 1<=len(keys)<=MAX_KEY_BATCH:raise ValueError('keys must contain 1-256 keys')
                raw=''.join(key_bytes(k,self.product.terminal.application_cursor() if self.product.terminal else False) for k in keys)
                self.product.write(raw);time.sleep(.04);return self.observe()
            if which=='type':
                s=printable(data['text'],'text',MAX_TEXT)
                if not s:raise ValueError('text cannot be empty')
                self.product.write(s.replace(ORIGIN,str(self.product.workspace)));time.sleep(.04);return self.observe()
            if which=='wait':
                seconds=data.get('seconds',.2)
                if not 0<=seconds<=3:raise ValueError('wait takes 0-3 seconds')
                time.sleep(seconds);return self.observe()
            if which=='resize':
                if not 40<=data['columns']<=240 or not 10<=data['rows']<=80:raise ValueError('invalid terminal size')
                self.product.resize(data['columns'],data['rows']);time.sleep(.04);return self.observe()
            if which=='remote':
                s=printable(data['command'],'command',1000).replace(ORIGIN,str(self.product.workspace))
                if len(s.encode())>1000:raise ValueError('native command exceeds 1000 bytes')
                try:answer=native(self.product,s)
                except (OSError,TimeoutError):raise ValueError('native control interface did not respond') from None
                return {'stdout':self.redact(answer)}
            if which=='upload':return upload(self.product,data)
            if which=='workspace':return files(self.product,data,self.redact)
            if which=='state':return state(self.product,data,self.redact)
            if which=='cli':
                try:
                    p=subprocess.run([str(self.product.solution/'start.sh'),data['option']],cwd=self.product.workspace,env=self.product.environment(),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=8,**self.product.identity())
                except subprocess.TimeoutExpired:raise ValueError('command-line invocation timed out') from None
                return {'exit_code':p.returncode,'stdout':self.redact(p.stdout[:MAX_FILE_BYTES].decode('utf-8','replace'))}
        raise ValueError('unknown operation')

class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):daemon_threads=True
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*args):pass
    def reply(self,status,value):
        body=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.send_header('Connection','close');self.end_headers();self.wfile.write(body)
    def do_GET(self):self.reply(404,{'error':'NotFound','detail':'POST JSON to /rpc'})
    def do_POST(self):
        began=time.monotonic();rt=self.server.runtime;code=200;which='invalid'
        try:
            self.connection.settimeout(RPC_TIMEOUT_SEC)
            size=int(self.headers.get('Content-Length') or 0)
            if self.path!='/rpc':raise ValueError('POST JSON to /rpc')
            if self.headers.get('Transfer-Encoding') or not 0<size<=MAX_REQUEST_BYTES:raise ValueError('request exceeds allowed size')
            data=runtime.strict_json_loads(self.rfile.read(size));which=data.get('op','invalid') if isinstance(data,dict) else 'invalid';value=rt.dispatch(data)
        except Exception as exc:code=400;value={'error':type(exc).__name__,'detail':rt.redact(str(exc))[:500]}
        try:self.reply(code,value)
        finally:rt.audit.record(str(which)[:40],code,time.monotonic()-began)

def main():
    config=runtime.options(socket_mode='0600',ready_timeout=30).parse_args()
    rt=Runtime(config);runtime.exit_on_sigterm()
    Path(config.work).mkdir(parents=True,exist_ok=True,mode=0o700)
    Path(config.work).chmod(0o700)
    try:
        rt.start();sock=runtime.listen(config.socket,config.socket_mode)
        server=Server(config.socket,Handler,bind_and_activate=False);server.socket.close();server.socket=sock;server.runtime=rt
        try:server.serve_forever(poll_interval=.2)
        finally:server.server_close()
    finally:
        rt.close()
        try:os.unlink(config.socket)
        except OSError:pass
if __name__=='__main__':main()
