#!/usr/bin/env python3
'''Hydrogen desktop runtime: OSC, command-line actions, documents and application lifecycle.

Operations use the running application and its ordinary document interfaces.
'''
from __future__ import annotations

import base64
import bz2
import errno
import gzip
import html
import http.server
import io
import json
import lzma
import math
import os
from pathlib import Path
import re
import select
import signal
import socket
import socketserver
import stat
import struct
import subprocess
import sys
import tarfile
import threading
import time
import xml.etree.ElementTree as ElementTree
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import blackbox_desktop as desktop  # noqa: E402
import exchange  # noqa: E402

PRODUCT = 'Hydrogen 1.2.7'
SCREEN = (1440, 900)
SETTLE = 0.5
MAX_REQUEST = 5_600_000
MAX_FILE = 4_000_000
MAX_DOWNLOAD = 16_000_000
MAX_UNPACKED = 64_000_000
RPC_SECONDS = 115
CLI_SECONDS = 100
MAX_IN_FLIGHT = 8
AREAS = ('inputs', 'outputs', 'projects')
SPACE = ' ' + chr(9) + chr(10) + chr(13)
QUOTES = chr(39) + chr(34)
TOKEN = re.compile('/[^' + re.escape(SPACE + QUOTES + '<>()[]{},;') + ']*')
XML_SUFFIXES = ('.h2song', '.h2pattern', '.h2playlist', '.h2theme')
AUDIO_SUFFIXES = ('.wav', '.wave', '.flac', '.ogg', '.oga', '.opus', '.mp3', '.aif', '.aiff', '.aifc', '.au', '.snd',
                  '.caf', '.voc', '.w64')
UPLOAD_SUFFIXES = XML_SUFFIXES + ('.h2drumkit',) + AUDIO_SUFFIXES + ('.mid', '.midi', '.png', '.jpg', '.jpeg')
DOWNLOAD_SUFFIXES = UPLOAD_SUFFIXES + ('.xml', '.ly', '.bak', '.txt')
# Elements of Hydrogen documents that name files or folders, and those that must stay empty (LADSPA plug-ins and
# playlist scripts are not available here).
PATH_ELEMENTS = ('filename', 'drumkitPath', 'drumkit_path', 'last_loaded_drumkit', 'playbackTrackFilename', 'path',
                 'image', 'drumkit')
ARCHIVE_MAGIC = (b'PK\x03\x04', b'PK\x05\x06', b"7z\xbc\xaf'\x1c", b'070707', b'070701', b'070702', b'!<arch>',
                 b'Rar!', b'MSCF', b'xar!', b'\xed\xab\xee\xdb', b'\x1f\x9d', b'\x28\xb5\x2f\xfd', b'LZIP', b'\x89LZO')
ACTIONS = ('export', 'check', 'legacy-check', 'upgrade', 'extract', 'install', 'version', 'help')
CHOOSER_FORMAT = re.compile('[(][*][.]')
CHOOSER_BUTTONS = ('cancel', 'open', 'save', 'choose', 'ok')
CHOOSER_KEYS = {'ctrl+a', 'escape', 'return', 'enter', 'up', 'down', 'home', 'end', 'tab', 'shift+tab', 'backspace',
                'delete', 'left', 'right'}
CONFIRM_KEYS = {'return', 'enter', 'space', 'kp_enter'}
# Playlist scripts run programs, and the drumkit repository list takes addresses of any kind: their menus, buttons
# and dialogs are closed on sight.
SCRIPT_TITLES = ('New Script', 'Add Script to selected Song', 'Set your Default Editor', 'Edit repository settings')
SCRIPT_ITEMS = ('Scripts', 'Add Script to selected song', 'Edit selected Script', 'Remove selected Script',
                'Create a new Script')
REPOSITORY_BUTTON = 'Edit server list'
# Dialogs with a file or folder field of their own (not a file chooser): their confirming buttons need a path inside
# the document areas.
PATH_DIALOGS = {'Export song': 'Export', 'Export midi': 'Export', 'Export Drumkit': 'Export',
                'SoundLibrary Properties': 'OK', 'Sound Library import': 'Install'}
BROWSER_TITLE = 'Audio File Browser'

NUMBER, TEXT = 'number', 'text'
SONG, SONG_TARGET, PATTERN, KIT, KIT_FILE, FOLDER = 'song', 'song-target', 'pattern', 'kit', 'kit-file', 'folder'
FLAG = ((), (NUMBER,))
OSC_COMMANDS = {
    **{name: FLAG for name in ('PLAY', 'PLAY_STOP_TOGGLE', 'PLAY_PAUSE_TOGGLE', 'STOP', 'PAUSE', 'RECORD_READY',
                               'RECORD_STROBE_TOGGLE', 'RECORD_STROBE', 'RECORD_EXIT', 'MUTE', 'UNMUTE', 'MUTE_TOGGLE',
                               'NEXT_BAR', 'PREVIOUS_BAR', 'BEATCOUNTER', 'TAP_TEMPO', 'PLAYLIST_NEXT_SONG',
                               'PLAYLIST_PREV_SONG', 'TOGGLE_METRONOME', 'UNDO_ACTION', 'REDO_ACTION', 'SAVE_SONG',
                               'SAVE_PREFERENCES', 'QUIT', 'CLEAR_SELECTED_INSTRUMENT', 'CLEAR_PATTERN')},
    **{name: ((NUMBER,),) for name in ('BPM', 'BPM_DECR', 'BPM_INCR', 'MASTER_VOLUME_ABSOLUTE', 'MASTER_VOLUME_RELATIVE',
                                       'SELECT_NEXT_PATTERN', 'SELECT_ONLY_NEXT_PATTERN', 'SELECT_AND_PLAY_PATTERN',
                                       'PLAYLIST_SONG', 'SELECT_INSTRUMENT', 'TIMELINE_ACTIVATION',
                                       'TIMELINE_DELETE_MARKER', 'JACK_TRANSPORT_ACTIVATION',
                                       'JACK_TIMEBASE_MASTER_ACTIVATION', 'SONG_MODE_ACTIVATION',
                                       'LOOP_MODE_ACTIVATION', 'RELOCATE', 'REMOVE_PATTERN', 'CLEAR_INSTRUMENT',
                                       'NOTE_OFF')},
    **{name: ((NUMBER, NUMBER),) for name in ('INSTRUMENT_PITCH', 'TIMELINE_ADD_MARKER', 'NOTE_ON',
                                              'SONG_EDITOR_TOGGLE_GRID_CELL')},
    'NEW_SONG': ((SONG_TARGET,),), 'OPEN_SONG': ((SONG,),), 'SAVE_SONG_AS': ((SONG_TARGET,),),
    'NEW_PATTERN': ((TEXT,),), 'OPEN_PATTERN': ((PATTERN,),),
    'LOAD_DRUMKIT': ((KIT,), (KIT, NUMBER)), 'UPGRADE_DRUMKIT': ((KIT_FILE,), (KIT_FILE, FOLDER)),
    'VALIDATE_DRUMKIT': ((KIT_FILE,), (KIT_FILE, NUMBER)), 'EXTRACT_DRUMKIT': ((KIT_FILE,), (KIT_FILE, FOLDER)),
}
OSC_STRIP_COMMANDS = {
    **{name: ((NUMBER,),) for name in ('STRIP_VOLUME_ABSOLUTE', 'STRIP_VOLUME_RELATIVE', 'PAN_ABSOLUTE',
                                       'PAN_ABSOLUTE_SYM', 'PAN_RELATIVE', 'FILTER_CUTOFF_LEVEL_ABSOLUTE')},
    'STRIP_MUTE_TOGGLE': FLAG, 'STRIP_SOLO_TOGGLE': FLAG,
}
OSC_ADDRESS = re.compile(r'/Hydrogen/([A-Z_]+)(?:/([1-9][0-9]{0,3}))?')
ARGUMENT_HELP = {NUMBER: 'number (sent as a 32-bit float)', TEXT: 'text',
                 SONG: 'song document: a name in the input, project or output area, or an absolute document path',
                 SONG_TARGET: 'song file to write: a name (project area) or an absolute document path',
                 PATTERN: 'pattern document: a name in the input, project or output area, or an absolute document path',
                 KIT: 'drumkit name, or a drumkit folder given as an absolute document path',
                 KIT_FILE: 'drumkit document (.h2drumkit file or drumkit folder): a name in the input, output or '
                           'project area, or an absolute document path',
                 FOLDER: 'target folder: a name (output area) or an absolute document path'}


def basename(value):
    if (not isinstance(value, str) or Path(value).name != value or chr(92) in value or value in ('', '.', '..')
            or len(value) > 255 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError('a file name must be a basename without path separators or control characters')
    return value


def chord(key):
    return '+'.join(part.strip() for part in str(key).casefold().replace('control', 'ctrl').split('+'))


read_regular = exchange.read_regular
write_regular = exchange.write_regular


# -- OSC (Open Sound Control 1.0 messages over UDP) ------------------------------------------------------------------
def osc_string(text):
    data = text.encode('utf-8') + b'\0'
    return data + b'\0' * (-len(data) % 4)


def osc_encode(address, arguments):
    tags, payload = ',', b''
    for value in arguments:
        if isinstance(value, str):
            tags += 's'
            payload += osc_string(value)
        else:
            tags += 'f'
            payload += struct.pack('>f', float(value))
    return osc_string(address) + osc_string(tags) + payload


def osc_decode(data):
    def string(at):
        end = data.index(b'\0', at)
        return data[at:end].decode('utf-8', 'replace'), (end // 4 + 1) * 4
    address, at = string(0)
    tags, at = string(at) if at < len(data) else (',', at)
    arguments = []
    for tag in tags[1:]:
        if tag == 'f':
            value = struct.unpack('>f', data[at:at + 4])[0]
            arguments.append(round(value, 6) if math.isfinite(value) else str(value))
            at += 4
        elif tag == 'i':
            arguments.append(struct.unpack('>i', data[at:at + 4])[0])
            at += 4
        elif tag == 'd':
            value = struct.unpack('>d', data[at:at + 8])[0]
            arguments.append(round(value, 9) if math.isfinite(value) else str(value))
            at += 8
        elif tag == 'h':
            arguments.append(struct.unpack('>q', data[at:at + 8])[0])
            at += 8
        elif tag == 's':
            value, at = string(at)
            arguments.append(value)
        elif tag in 'TF':
            arguments.append(tag == 'T')
        elif tag in 'NI':
            arguments.append(None)
        else:
            raise ValueError('unsupported OSC argument type ' + tag)
    return {'address': address, 'args': arguments}


OSC_ENDPOINT = {
    'transport': 'OSC 1.0 messages over UDP. The application listens on 127.0.0.1, port PORT (the runtime supplies '
                 'PORT), from the moment its window is reachable.',
    'addresses': 'The addresses and argument signatures of osc_commands; <strip> is an instrument number counted from 1.',
    'arguments': 'Numbers are sent as 32-bit floats (type tag f) and text as strings (type tag s). File arguments '
                 'reaching the application are absolute paths.',
    'feedback': 'The application sends its feedback messages to the address and port the message came from; the '
                'first message from a new sender registers it.',
}
CLI_ENDPOINT = {
    'invocation': 'The application start.sh is also run with the arguments of the product command line h2cli: '
                  'start.sh <h2cli options>, from the solution folder, with the environment of the application '
                  '(same HOME and DATA_DIR; TMPDIR is a scratch folder of that call). Standard output, standard error '
                  'and the exit status form the reply.',
    'actions': {'export': '-s <song> | -p <playlist>, -o <output file>, optional -r <rate>, -b <bits>, '
                          '-I <interpolation>, --compression-level <level>, -k <drumkit name>',
                'check': '-c <drumkit>', 'legacy-check': '-l <drumkit>', 'upgrade': '-u <drumkit> [-t <folder>]',
                'extract': '-x <drumkit> [-t <folder>]', 'install': '-i <drumkit>', 'version': '--version',
                'help': '--help'},
}
NOTES = [
    'osc, cli and the desktop operate the same application data; no product behaviour is simulated.',
    'DOCUMENT_AREAS',
    'File dialogs (Open song, Save song, Open Pattern, Import drumkit, Export song Browse and the like) are confined to '
    'the document areas: type an absolute document path into the File name field and confirm with Return or the '
    'Open/Save button; the dialog navigation controls and the sidebar are refused, and a dialog that opens elsewhere is '
    'moved into the project area first.',
    'Fields of the application that hold a file or folder (the Export song and Export midi file names, the Export '
    'Drumkit path, the drumkit file of Sound Library import, the Audio File Browser folder, a drumkit image) take '
    'absolute document paths; a dialog is confirmed only while its '
    'path lies in the document areas. A typed path outside the document areas is refused wherever it is typed.',
    'Playlist scripts (the Scripts menu of the Playlist Browser and its dialogs) run programs and are not available, '
    'nor is editing the online drumkit repository list; their windows are closed and the request fails. The '
    'application has no sound card: audio plays to a silent output.',
    'Uploaded XML text uses UTF-8. Songs, patterns, playlists, themes and drumkits may only name files inside the document areas, the '
    'application library or its factory data, use no LADSPA plug-in and no playlist script; drumkits are tar archives '
    '(optionally compressed) of ordinary files and folders.',
    'After a native save or export, and after osc and cli, list_files shows the new files (up to 16,000,000 bytes) '
    'with refs; download retrieves each once. settings returns the settings file of the application.',
    'restart keeps uploaded inputs, outputs, projects, settings and the library; reset discards them.',
]
LIMITS = {'upload_bytes': MAX_FILE, 'download_bytes': MAX_DOWNLOAD, 'request_bytes': MAX_REQUEST,
          'rpc_seconds': RPC_SECONDS, 'cli_seconds': CLI_SECONDS, 'osc_wait_seconds': 5, 'screen': list(SCREEN),
          'ready_seconds': None}


def osc_catalog():
    def signature(spec):
        return [ARGUMENT_HELP[kind] for kind in spec]
    rows = [{'address': '/Hydrogen/' + name, 'arguments': [signature(s) for s in specs]}
            for name, specs in sorted(OSC_COMMANDS.items())]
    rows += [{'address': '/Hydrogen/' + name + '/<strip>', 'arguments': [signature(s) for s in specs]}
             for name, specs in sorted(OSC_STRIP_COMMANDS.items())]
    return rows


def specs():
    '''Help specs: the shared desktop operations plus the channels of this product.'''
    integer = lambda text: {'type': 'integer', 'description': text}
    document = lambda text: {'type': 'string', 'description': text}
    ops = {
        'help': {'kind': 'info', 'summary': 'This description of operations, fields, the OSC catalog and limits.',
                 'fields': {}},
        'status': {'kind': 'lifecycle', 'fields': {},
                   'summary': 'Whether the application is running and ready (an accessible window).'},
        'reset': {'kind': 'lifecycle', 'fields': {},
                  'summary': 'Fresh instance: new desktop session and empty data, library, settings, inputs, outputs '
                             'and projects; the application is started again.'},
        'restart': {'kind': 'lifecycle', 'fields': {},
                    'summary': 'Relaunch the application with the same data, library, settings, inputs, outputs and '
                               'projects.'},
        'osc': {'kind': 'http',
                'summary': 'Send one OSC message to the application (see osc_commands and osc_endpoint) and '
                           'return the feedback messages it sent back while the runtime listened.',
                'fields': {
                    'address': {'type': 'string', 'required': True,
                                'description': 'OSC address from osc_commands, for example /Hydrogen/BPM or '
                                               '/Hydrogen/STRIP_VOLUME_ABSOLUTE/2.'},
                    'args': {'type': 'array', 'items': {'type': ['number', 'string']},
                             'description': 'Arguments in the order of one of the signatures of the address; default '
                                            'none.'},
                    'wait': {'type': 'number',
                             'description': 'Seconds to listen for feedback after sending, 0-5; default 0.5 (the '
                                            'runtime keeps listening while messages arrive).'}}},
        'cli': {'kind': 'http',
                'summary': 'Run one action of the product command line h2cli (see cli_endpoint): returns '
                           'exit_code and the text output; files it wrote in the document areas are listed in '
                           'downloads.',
                'fields': {
                    'action': {'type': 'string', 'required': True, 'enum': list(ACTIONS),
                               'description': 'The command line action.'},
                    'song': document('export: song document (-s): a name in the input, project or output area, or an '
                                     'absolute document path.'),
                    'playlist': document('export: playlist document (-p) instead of a song.'),
                    'output': document('export: output file (-o); a name goes to the output area. Its suffix chooses '
                                       'the format.'),
                    'rate': integer('export: sample rate in Hz (-r).'),
                    'bits': integer('export: sample depth in bits (-b).'),
                    'interpolation': integer('export: interpolation mode (-I).'),
                    'compression_level': {'type': 'number', 'description': 'export: compression level 0.0-1.0 '
                                                                           '(--compression-level).'},
                    'kit': {'type': 'string', 'description': 'export: drumkit name to load (-k).'},
                    'drumkit': document('check, legacy-check, upgrade, extract, install: drumkit document '
                                        '(.h2drumkit file or drumkit folder) in the document areas.'),
                    'target': document('upgrade, extract: target folder (-t); a name goes to the output area.')}},
        'upload': {'kind': 'files',
                   'summary': 'Place one document (song, pattern, playlist, theme, drumkit, audio, MIDI or image) in the '
                              'input area, replacing a document of the same name.',
                   'fields': {
                       'filename': {'type': 'string', 'required': True,
                                    'description': 'Document name: a basename with one of the suffixes ' +
                                                   ' '.join(UPLOAD_SUFFIXES) + '.'},
                       'base64': {'type': 'string', 'required': True,
                                  'description': f'File bytes, base64 encoded, at most {MAX_FILE} bytes.'}}},
        'list_files': {'kind': 'files', 'fields': {},
                       'summary': 'Uploaded input names and the pending downloads: files the application or cli wrote '
                                  'or changed in the document areas since they were last listed, each with a ref.'},
        'download': {'kind': 'files', 'summary': 'Retrieve a pending download once, as body_base64.',
                     'fields': {'ref': {'type': 'string', 'required': True,
                                        'description': 'A ref from list_files or from a cli reply.'}}},
        'settings': {'kind': 'files', 'fields': {},
                     'summary': 'The settings file of the application (hydrogen.conf in the .hydrogen folder of HOME) '
                                'as text in body.'},
    }
    for op, spec in desktop.operations(SCREEN).items():
        ops[op] = spec
    return runtime.check_operations(ops)


OPERATIONS = specs()
GUI_GUARDED = {op for op, spec in OPERATIONS.items() if spec['kind'] == 'gui'} - {'zoom', 'wait', 'move'}


def examples(inputs):
    return [{'op': 'osc', 'address': '/Hydrogen/BPM', 'args': [132]},
            {'op': 'osc', 'address': '/Hydrogen/STRIP_VOLUME_ABSOLUTE/1', 'args': [0.5]},
            {'op': 'osc', 'address': '/Hydrogen/SAVE_SONG_AS', 'args': ['beat.h2song']},
            {'op': 'cli', 'action': 'export', 'song': 'beat.h2song', 'output': 'beat.wav', 'bits': 24},
            {'op': 'cli', 'action': 'check', 'drumkit': 'kit.h2drumkit'},
            {'op': 'observe'},
            {'op': 'press', 'key': 'Control+o'},
            {'op': 'fill', 'target': {'role': 'text', 'name': 'File name:'}, 'value': f'{inputs}/song.h2song'},
            {'op': 'press', 'key': 'Return'},
            {'op': 'upload', 'filename': 'song.h2song', 'base64': '<base64 bytes>'},
            {'op': 'list_files'},
            {'op': 'settings'}]


def local_name(tag):
    return tag.split('}')[-1] if isinstance(tag, str) else ''


def markup_text(payload):
    '''The text of a payload that an XML reader could take for a document (None for binary data).'''
    if payload[:4] in (b'\x00\x00\xfe\xff', b'\xff\xfe\x00\x00') or payload[:2] in (b'\xff\xfe', b'\xfe\xff') or \
            payload[:4] in (b'<\x00?\x00', b'\x00<\x00?', b'<\x00\x00\x00', b'\x00\x00\x00<'):
        raise DocumentError('documents are UTF-8 encoded')
    head = payload[:4096].lstrip(b'\xef\xbb\xbf \t\r\n')
    if not head.startswith(b'<'):
        return None
    declaration = re.match(br'\s*<\?xml\b[^?]*\?>', head, re.I)
    if declaration:
        encoding = re.search(br'''encoding\s*=\s*["']([^"']+)["']''', declaration.group(0), re.I)
        if encoding and encoding.group(1).lower().replace(b'_', b'-') not in (b'utf-8', b'utf8', b'ascii', b'us-ascii'):
            raise DocumentError('documents are UTF-8 encoded')
    return payload.decode('utf-8', 'replace')


class DocumentError(ValueError):
    '''An uploaded document names something outside the allowed places or carries unsupported content.'''


class HydrogenProduct(runtime.Product):
    '''start.sh with the instance layout plus the owned document areas.'''

    def prepare(self, fresh):
        super().prepare(fresh)
        exchange.prepare(self, AREAS)


class Broker:
    def __init__(self, config):
        self.config = config
        self.state = Path(config.state)
        self.log = runtime.BoundedLog(config.log_dir)
        directories = {**runtime.layout(config.state), 'PBP_FILES_DIR': self.state / 'files'}
        self.product = HydrogenProduct(config, log=self.log, directories=directories)
        self.session = self.desk = None
        self.downloads, self.seen, self.serial, self.commands = {}, {}, 0, 0
        self.osc_socket = None
        self.lock = threading.RLock()
        self.roots = [config.solution, config.state, config.work, config.log_dir, str(Path(__file__).resolve().parent),
                      '/app/solution', '/reference']
        self.hide = runtime.redactor(*self.roots)

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def area(self, name):
        return self.state / 'files' / name

    def library(self):
        return self.state / 'home' / '.hydrogen' / 'data'

    def factory(self):
        return Path(self.config.solution) / 'runtime' / 'usr' / 'share' / 'hydrogen' / 'data'

    def start_session(self):
        if self.session is not None:
            self.session.close()
        if self.desk is not None:
            self.desk.close()
        self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, maximize=True, audio=True,
                                              log_dir=Path(self.config.log_dir) / 'desktop', ).start()
        self.desk = desktop.Desktop(self.session, settle=SETTLE, log_dir=Path(self.config.log_dir) / 'desktop', pointer_guard=self.guard_pointer)
        self.hide = runtime.redactor(*self.roots, str(self.session.root))

    def settle(self, seconds=8.0):
        '''After readiness: wait until the set of product windows stays the same for 1.5 seconds.'''
        end, last, since = time.monotonic() + seconds, None, time.monotonic()
        while time.monotonic() < end:
            try:
                now = sorted(self.titles())
            except desktop.DesktopError:
                now = None
            if now != last:
                last, since = now, time.monotonic()
            elif time.monotonic() - since >= 1.5:
                return
            time.sleep(0.3)

    def start(self, fresh):
        '''Start (fresh: a new desktop session and empty instance) and wait for an accessible window.'''
        self.product.stop()
        if fresh or self.session is None or not self.session.alive():
            self.start_session()
        if fresh:
            self.downloads.clear()
            self.seen.clear()
        self.close_osc()
        self.product.extra = {key: value for key, value in self.session.env().items()
                              if key not in ('HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'DATA_DIR')}
        # Sound goes to the session's silent PulseAudio output. ALSA devices are not configured at all: an ALSA
        # device name typed in the preferences opens nothing (ALSA plug-in devices could write files or pipes).
        self.product.extra['ALSA_CONFIG_PATH'] = '/dev/null'
        started = self.product.start(fresh)
        if started:
            runtime.wait_until(self.product, lambda: self.desk.ready(minimum=(200, 150)),
                               failure=f'the application showed no accessible window within '
                                       f'{self.config.ready_timeout:g} s')
            if self.product.ready:
                self.settle()
        return self.status()

    def status(self):
        return self.product.status()

    def close(self):
        self.product.stop()
        self.close_osc()
        if self.desk is not None:
            self.desk.close()
        if self.session is not None:
            self.session.close()

    # -- documents ----------------------------------------------------------------------------------------------
    def inside(self, value):
        '''Whether an absolute path lies in the files folder (dot segments removed first).'''
        path = os.path.normpath(str(value))
        root = str(self.state / 'files')
        return path == root or path.startswith(root + os.sep)

    def document_path(self, value, *, where):
        """Normalize an absolute document path and validate every existing component."""
        text = str(value).strip()
        if (not text.startswith('/') or text.startswith('//') or '://' in text or '\\' in text
                or len(text) > 4000 or any(ord(c) < 32 for c in text)):
            raise ValueError(f'{where} accepts absolute document paths only')
        path = Path(os.path.normpath(text))
        root = Path(os.path.normpath(str(self.state / 'files')))
        if not path.is_relative_to(root):
            raise ValueError(f'{where} is confined to the document folder {root}')
        # Check the original path too: normalization must not hide a link before a parent step.
        original = Path(text)
        if any(part.is_symlink() for part in (original, *original.parents)):
            raise ValueError(f'{where} does not follow symbolic links')
        if original.resolve() != path or root.resolve() != root:
            raise ValueError(f'{where} does not resolve to the document folder')
        return path

    def resolve_document(self, value, where, search, default):
        '''A document name (looked up in the search areas) or an absolute document path.'''
        text = str(value)
        if '/' in text:
            return self.document_path(text, where=where)
        name = basename(text)
        for area in search:
            if (self.area(area) / name).exists():
                return self.document_path(str(self.area(area) / name), where=where)
        return self.document_path(str(self.area(default) / name), where=where)

    def make_directory(self, path):
        relative = Path(path).relative_to(self.state)
        with exchange.directory(self.state, relative, self.product.account()):
            pass

    def allowed_reference(self, value, where):
        '''A file or folder named inside an uploaded document: empty, relative without parent steps, or an absolute
        path in the document areas, the application library or the factory data.'''
        text = value.strip()
        if not text or text == '-':
            return
        if chr(92) in text or any(ord(c) < 32 for c in text) or text.startswith('~') or '://' in text:
            raise DocumentError(f'{where} must be a plain file name or a document path')
        if '..' in Path(text).parts:
            raise DocumentError(f'{where} must not step into parent folders')
        if not text.startswith('/'):
            return
        normal = os.path.normpath(text)
        for root in (self.state / 'files', self.library(), self.factory()):
            root = str(root)
            if normal == root or normal.startswith(root + os.sep):
                original = Path(text)
                if any(p.is_symlink() for p in (original, *original.parents)) or str(original.resolve()) != normal:
                    raise DocumentError(f'{where} does not follow symbolic links')
                return
        raise DocumentError(f'{where} names a file outside the document areas, the library and the factory data')

    @staticmethod
    def element_text(value):
        '''The text content of an element the way an XML parser reads it: comments and processing instructions
        dropped, CDATA kept literally, nested markup removed, references decoded.'''
        value = re.sub(r'<!--.*?-->|<\?.*?\?>', '', value, flags=re.S)
        parts = re.split(r'<!\[CDATA\[(.*?)\]\]>', value, flags=re.S)
        return ''.join(part if index % 2 else html.unescape(re.sub(r'<[^>]*>', '', part))
                       for index, part in enumerate(parts))

    def check_values(self, values, name):
        for element, value in values:
            if element in ('drumkit', 'image') and re.search(r'[/\\]', value):
                raise DocumentError(f'{name}: <{element}> must be a plain name')
            self.allowed_reference(value, f'{name}: <{element}>')

    def check_markup(self, text, name):
        '''Path and plug-in rules for the XML documents of Hydrogen (songs, patterns, playlists, themes, drumkits).'''
        if re.search(r'<!DOCTYPE|<!ENTITY', text, flags=re.I):
            raise DocumentError(f'{name}: document type declarations are not accepted')
        values, libraries, scripts, enabled = [], [], [], []
        playlist = re.search(r'<playlist[\s>/]', text) is not None
        for element in PATH_ELEMENTS:
            for value in re.findall(rf'<{element}(?:\s[^>]*)?>(.*?)</{element}\s*>', text, flags=re.S):
                values.append((element, self.element_text(value)))
        if playlist:
            # The legacy playlist form names each song in a <song> element of a <next> entry.
            for block in re.findall(r'<next(?:\s[^>]*)?>(.*?)</next\s*>', text, flags=re.S):
                for value in re.findall(r'<song(?:\s[^>]*)?>(.*?)</song\s*>', block, flags=re.S):
                    values.append(('song', self.element_text(value)))
        for block in re.findall(r'<fx(?:\s[^>]*)?>(.*?)</fx\s*>', text, flags=re.S):
            libraries += [self.element_text(v) for v in re.findall(r'<filename(?:\s[^>]*)?>(.*?)</filename\s*>', block,
                                                                     flags=re.S)]
        script_tags = ('scriptPath', 'script') if playlist else ('scriptPath',)
        enabled_tags = ('scriptEnabled', 'enabled') if playlist else ('scriptEnabled',)
        for tag in script_tags:
            scripts += [self.element_text(v) for v in re.findall(rf'<{tag}(?:\s[^>]*)?>(.*?)</{tag}\s*>', text,
                                                                  flags=re.S)]
        for tag in enabled_tags:
            enabled += [self.element_text(v) for v in re.findall(rf'<{tag}(?:\s[^>]*)?>(.*?)</{tag}\s*>', text,
                                                                  flags=re.S)]
        try:
            root = ElementTree.fromstring(text.encode('utf-8'))
        except ElementTree.ParseError:
            root = None
        if root is not None:
            playlist = playlist or local_name(root.tag) == 'playlist'
            for node in root.iter():
                tag = local_name(node.tag)
                content = ''.join(node.itertext())
                if tag in PATH_ELEMENTS:
                    values.append((tag, content))
                elif playlist and tag == 'next':
                    values += [('song', ''.join(c.itertext())) for c in node if local_name(c.tag) == 'song']
                elif tag == 'fx':
                    libraries += [''.join(child.itertext()) for child in node.iter() if local_name(child.tag) == 'filename']
                elif tag == 'scriptPath' or (playlist and tag == 'script'):
                    scripts.append(content)
                elif tag == 'scriptEnabled' or (playlist and tag == 'enabled'):
                    enabled.append(content)
        self.check_values(values, name)
        if any(value.strip() not in ('', '-') for value in libraries):
            raise DocumentError(f'{name}: LADSPA plug-ins are not available')
        # The playlist editor writes the placeholder "no Script" for entries without a script.
        if any(value.strip().casefold() not in ('', 'no script') for value in scripts) or \
                any(value.strip().casefold() not in ('', 'false', '0') for value in enabled):
            raise DocumentError(f'{name}: playlist scripts are not available')

    @staticmethod
    def unpacked(payload):
        '''The payload with gzip, bzip2 and xz layers removed (bounded).'''
        data = payload
        for _ in range(3):
            try:
                if data[:2] == b'\x1f\x8b':
                    data = gzip.GzipFile(fileobj=io.BytesIO(data)).read(MAX_UNPACKED + 1)
                elif data[:3] == b'BZh':
                    data = bz2.BZ2Decompressor().decompress(data, MAX_UNPACKED + 1)
                elif data[:6] == b'\xfd7zXZ\x00':
                    data = lzma.LZMADecompressor().decompress(data, MAX_UNPACKED + 1)
                else:
                    return data
            except (OSError, EOFError, lzma.LZMAError, ValueError):
                return data
            if len(data) > MAX_UNPACKED:
                raise DocumentError('the archive unpacks to more than the allowed size')
        return data

    def check_archive(self, payload, name):
        '''A drumkit archive: a tar archive (optionally gzip, bzip2 or xz compressed) of regular files and folders
        with relative member names, no executable files and no programs.'''
        inner = self.unpacked(payload)
        if any(inner.startswith(magic) for magic in ARCHIVE_MAGIC) or inner[0x8001:0x8006] == b'CD001':
            raise DocumentError(f'{name}: drumkits are tar archives')
        is_tar = len(inner) >= 512 and inner[257:262] == b'ustar'
        try:
            archive = tarfile.open(fileobj=io.BytesIO(payload), mode='r:*')
        except (tarfile.TarError, OSError, EOFError, lzma.LZMAError):
            if is_tar:
                raise DocumentError(f'{name}: the tar archive cannot be read completely') from None
            if inner.startswith(b'\x7fELF'):
                raise DocumentError(f'{name}: programs are not accepted')
            return
        total, count = 0, 0
        try:
            for member in archive:
                count += 1
                total += max(0, member.size)
                if count > 2000 or total > MAX_UNPACKED:
                    raise DocumentError(f'{name}: the archive is too large')
                parts = Path(member.name).parts
                if (member.name.startswith('/') or '..' in parts or chr(92) in member.name
                        or any(ord(c) < 32 for c in member.name)):
                    raise DocumentError(f'{name}: archive members must have relative names inside the archive')
                if member.isdir():
                    continue
                if not member.isreg() or member.issparse():
                    raise DocumentError(f'{name}: archive members must be regular files or folders')
                if member.mode & 0o111:
                    raise DocumentError(f'{name}: archive members must not be executable')
                stream = archive.extractfile(member)
                content = stream.read(MAX_UNPACKED + 1) if stream else b''
                if content.startswith(b'\x7fELF'):
                    raise DocumentError(f'{name}: programs are not accepted')
                markup = markup_text(content)
                if markup is not None:
                    self.check_markup(markup, f'{name}:{member.name}')
        except (tarfile.TarError, OSError, EOFError, lzma.LZMAError, zlib.error):
            raise DocumentError(f'{name}: the tar archive cannot be read completely') from None
        finally:
            archive.close()

    def check_upload(self, filename, payload):
        '''Every upload: no programs; drumkit archives checked member by member; anything an XML reader could take
        for a document (whatever its name) follows the path, plug-in and script rules.'''
        lower = filename.casefold()
        if payload.startswith(b'\x7fELF'):
            raise DocumentError('programs are not accepted as documents')
        if lower.endswith('.h2drumkit'):
            self.check_archive(payload, filename)
            return
        text = markup_text(payload)
        if text is not None:
            self.check_markup(text, filename)

    def upload(self, data):
        filename = basename(data['filename'])
        if not filename.casefold().endswith(UPLOAD_SUFFIXES):
            raise ValueError('uploads are Hydrogen, audio, MIDI or image documents (suffixes ' +
                             ' '.join(UPLOAD_SUFFIXES) + ')')
        payload = base64.b64decode(data['base64'], validate=True)
        if len(payload) > MAX_FILE:
            raise ValueError(f'upload exceeds {MAX_FILE} bytes')
        self.check_upload(filename, payload)
        target = self.area('inputs') / filename
        write_regular(target, payload, self.product.account() if self.product.switching() else None)
        info = exchange.file_info(target, MAX_FILE)
        self.seen[str(target)] = (info.st_mtime_ns, info.st_size)
        return {'uploaded': True, 'filename': filename, 'size': len(payload)}

    def validate_document(self, path):
        """Recheck existing document contents before the product consumes them."""
        if path.is_dir():
            for name, _ in exchange.inventory(path, XML_SUFFIXES + ('.xml',), MAX_FILE, recursive=True):
                self.check_upload(name, read_regular(path / name, MAX_FILE))
            return
        try:
            payload = read_regular(path, MAX_DOWNLOAD)
        except FileNotFoundError:
            return
        self.check_upload(path.name, payload)

    def register(self, path):
        info = exchange.file_info(path, MAX_DOWNLOAD)
        self.seen[str(path)] = (info.st_mtime_ns, info.st_size)
        for ref, known in list(self.downloads.items()):
            if known == path:
                del self.downloads[ref]
        self.serial += 1
        ref = f'd{self.serial}'
        self.downloads[ref] = path
        return {'ref': ref, 'filename': path.name, 'size': info.st_size,
                'path': str(path.relative_to(self.state / 'files'))}

    def scan(self):
        """Register bounded regular documents found through directory descriptors."""
        found = []
        for area in AREAS:
            directory = self.area(area)
            for name, info in exchange.inventory(directory, DOWNLOAD_SUFFIXES, MAX_DOWNLOAD, recursive=True):
                path = directory / name
                if self.seen.get(str(path)) == (info.st_mtime_ns, info.st_size):
                    continue
                try:
                    found.append(self.register(path))
                except (OSError, ValueError):
                    continue
        return found

    def list_files(self):
        self.scan()
        pending = []
        for ref, path in self.downloads.items():
            try:
                info = exchange.file_info(path, MAX_DOWNLOAD)
            except (OSError, ValueError):
                continue
            item = {'ref': ref, 'filename': path.name, 'size': info.st_size}
            item['path'] = str(path.relative_to(self.state / 'files'))
            pending.append(item)
        names = [name for name, _ in exchange.inventory(self.area('inputs'), UPLOAD_SUFFIXES, MAX_FILE)]
        return {'inputs': names, 'downloads': pending}

    def download(self, data):
        ref = data['ref']
        if ref not in self.downloads:
            raise ValueError('unknown download reference; use list_files')
        path = self.downloads.pop(ref)
        try:
            payload = read_regular(path, MAX_DOWNLOAD)
        except (OSError, ValueError):
            raise ValueError('the file is no longer available or exceeds the download limit') from None
        return {'filename': path.name, 'size': len(payload), 'body_base64': base64.b64encode(payload).decode()}

    def settings(self):
        try:
            payload = read_regular(self.state / 'home' / '.hydrogen' / 'hydrogen.conf', MAX_FILE)
        except (OSError, ValueError):
            raise ValueError('the application has not written its settings file yet') from None
        return {'filename': 'hydrogen.conf', 'body': payload.decode('utf-8', 'replace')}

    # -- OSC ----------------------------------------------------------------------------------------------------
    def close_osc(self):
        if self.osc_socket is not None:
            self.osc_socket.close()
            self.osc_socket = None

    def osc_endpoint(self):
        if self.osc_socket is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', 0))
            sock.connect(('127.0.0.1', int(self.config.port)))
            self.osc_socket = sock
        return self.osc_socket

    def osc_argument(self, kind, value):
        if kind == NUMBER:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                    or abs(value) > 3.0e38:
                raise ValueError('OSC numbers must be finite')
            return float(value)
        if not isinstance(value, str) or len(value) > 1000 or any(ord(c) < 32 for c in value):
            raise ValueError('OSC text must be at most 1000 characters without control characters')
        if kind == TEXT:
            if value.strip().startswith(('/', '~')) or '://' in value:
                self.document_path(value, where='OSC text')
            return value
        if kind == KIT and '/' not in value:
            if not value or value in ('.', '..'):
                raise ValueError('a drumkit name is required')
            return value
        where = 'an OSC file argument'
        if kind == SONG:
            path = self.resolve_document(value, where, ('inputs', 'projects', 'outputs'), 'inputs')
        elif kind == SONG_TARGET:
            path = self.resolve_document(value, where, (), 'projects')
        elif kind == PATTERN:
            path = self.resolve_document(value, where, ('inputs', 'projects', 'outputs'), 'inputs')
        elif kind in (KIT, KIT_FILE):
            path = self.resolve_document(value, where, ('inputs', 'outputs', 'projects'), 'inputs')
        else:
            path = self.resolve_document(value, where, (), 'outputs')
        if kind in (SONG, PATTERN, KIT, KIT_FILE):
            self.validate_document(path)
        return str(path)

    def osc(self, data):
        match = OSC_ADDRESS.fullmatch(str(data['address']))
        command = match and match.group(1)
        if match is None or (match.group(2) is None and command not in OSC_COMMANDS) or \
                (match.group(2) is not None and command not in OSC_STRIP_COMMANDS):
            raise ValueError('unknown OSC address; see osc_commands in help')
        signatures = (OSC_STRIP_COMMANDS if match.group(2) else OSC_COMMANDS)[command]
        arguments = data.get('args', [])
        if not isinstance(arguments, list):
            raise ValueError('args must be an array')
        candidates = [s for s in signatures if len(s) == len(arguments)
                      and all((kind == NUMBER) == (isinstance(value, (int, float)) and not isinstance(value, bool))
                              for kind, value in zip(s, arguments))]
        if not candidates:
            raise ValueError('the arguments match no signature of ' + match.group(0) + '; see osc_commands in help')
        values = [self.osc_argument(kind, value) for kind, value in zip(candidates[0], arguments)]
        wait = data.get('wait', 0.5)
        if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not 0 <= wait <= 5:
            raise ValueError('wait must be 0-5 seconds')
        if not self.product.running():
            raise ValueError('the application is not running; use restart or reset')
        sock = self.osc_endpoint()
        while select.select([sock], [], [], 0)[0]:
            try:
                sock.recv(65536)
            except OSError:
                break
        try:
            sock.send(osc_encode(match.group(0), values))
        except OSError as exc:
            self.close_osc()
            raise ValueError(f'the OSC message could not be sent ({errno.errorcode.get(exc.errno, exc.errno)})') from None
        feedback, start, quiet = [], time.monotonic(), None
        while len(feedback) < 4000:
            now = time.monotonic()
            limit = start + float(wait) if quiet is None else min(quiet + 0.25, start + float(wait) + 3.0)
            if now >= limit:
                break
            ready = select.select([sock], [], [], limit - now)[0]
            if not ready:
                break
            try:
                packet = sock.recv(65536)
            except ConnectionRefusedError:
                self.close_osc()
                raise ValueError('the application does not accept OSC messages on PORT (UDP)') from None
            except OSError:
                break
            try:
                message = osc_decode(packet)
            except (ValueError, IndexError, struct.error):
                message = {'address': '(undecodable message)', 'args': []}
            if message['address'] == '#bundle':
                message = {'address': '(bundle)', 'args': []}
            feedback.append(message)
            quiet = time.monotonic()
        return {'sent': {'address': match.group(0), 'args': [v if isinstance(v, str) else round(v, 6)
                                                            for v in values]},
                'feedback': feedback}

    # -- command line ---------------------------------------------------------------------------------------------
    def snapshot(self):
        files = {}
        for area in AREAS:
            root = self.area(area)
            for name, info in exchange.inventory(root, DOWNLOAD_SUFFIXES, MAX_DOWNLOAD, recursive=True):
                files[str(root / name)] = (info.st_mtime_ns, info.st_size)
        return files

    def cli_arguments(self, data):
        action = data['action']
        allowed = {'export': {'song', 'playlist', 'output', 'rate', 'bits', 'interpolation', 'compression_level', 'kit'},
                   'check': {'drumkit'}, 'legacy-check': {'drumkit'}, 'upgrade': {'drumkit', 'target'},
                   'extract': {'drumkit', 'target'}, 'install': {'drumkit'}, 'version': set(), 'help': set()}[action]
        extra = sorted(set(data) - {'op', 'action'} - allowed)
        if extra:
            raise ValueError(f'{action} takes no ' + ', '.join(extra))
        for key in ('rate', 'bits', 'interpolation'):
            if key in data and abs(data[key]) > 10_000_000:
                raise ValueError(f'{key} is out of range')
        if 'compression_level' in data and (not math.isfinite(data['compression_level'])
                                            or abs(data['compression_level']) > 1000):
            raise ValueError('compression_level is out of range')
        search = ('inputs', 'projects', 'outputs')
        if action == 'version':
            return ['--version'], None
        if action == 'help':
            return ['--help'], None
        if action == 'export':
            if ('song' in data) == ('playlist' in data):
                raise ValueError('export needs either song or playlist')
            if 'output' not in data:
                raise ValueError('export needs output: a name or an absolute document path')
            argv = (['-s', str(self.resolve_document(data['song'], 'the song', search, 'inputs'))] if 'song' in data
                    else ['-p', str(self.resolve_document(data['playlist'], 'the playlist', search, 'inputs'))])
            target = self.resolve_document(data['output'], 'the output', ('outputs',), 'outputs')
            argv += ['-o', str(target)]
            for key, flag in (('rate', '-r'), ('bits', '-b'), ('interpolation', '-I'),
                              ('compression_level', '--compression-level')):
                if key in data:
                    argv += [flag, str(data[key])]
            if 'kit' in data:
                kit = str(data['kit'])
                if not kit or '/' in kit or chr(92) in kit or kit in ('.', '..') or any(ord(c) < 32 for c in kit):
                    raise ValueError('kit is a drumkit name')
                argv += ['-k', kit]
            return argv, target
        if 'drumkit' not in data:
            raise ValueError(f'{action} needs drumkit: a document name or an absolute document path')
        drumkit = self.resolve_document(data['drumkit'], 'the drumkit', ('inputs', 'outputs', 'projects'), 'inputs')
        flag = {'check': '-c', 'legacy-check': '-l', 'upgrade': '-u', 'extract': '-x', 'install': '-i'}[action]
        argv = [flag, str(drumkit)]
        target = None
        if 'target' in data:
            target = self.resolve_document(data['target'], 'the target folder', (), 'outputs')
            argv += ['-t', str(target)]
        return argv, target

    @staticmethod
    def clean_output(text):
        '''Product text without terminal colours, progress redraws and the audio/MIDI driver probing of the host.'''
        lines = []
        for line in text.replace('\r\n', '\n').split('\n'):
            line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', line.split('\r')[-1]).rstrip()
            if not line or line.startswith('ALSA lib ') or 'qt.network.ssl' in line or re.search(
                    r'\[(PulseAudioDriver|AlsaAudioDriver|PortAudioDriver|JackAudioDriver|AlsaMidiDriver|PortMidiDriver)'
                    r'::|\[AudioEngine::createAudioDriver\]|alsaMidiDriver_thread|checkJackSupport|'
                    r'Cannot connect to server|jack server|JackShm', line):
                continue
            lines.append(line)
        return '\n'.join(lines)

    def cli(self, data):
        argv, target = self.cli_arguments(data)
        for key in ('song', 'playlist', 'drumkit'):
            if key in data:
                self.validate_document(self.resolve_document(data[key], 'an input document', AREAS, 'inputs'))
        before = self.snapshot()
        self.commands += 1
        self.make_directory(self.state / 'cli')
        scratch = self.state / 'cli' / str(self.commands)
        runtime.remove_entry(self.state, str(scratch.relative_to(self.state)), missing_ok=True)
        for path in (scratch,):
            self.make_directory(path)
        env = self.product.environment()
        env.update({key: value for key, value in self.session.env().items()
                    if key not in ('HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'DATA_DIR')})
        env.update(TMPDIR=str(scratch))
        kwargs = {}
        if self.product.switching():
            account = self.product.account()
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        solution = Path(self.config.solution)
        try:
            proc = subprocess.Popen([str(solution / 'start.sh'), *argv], cwd=str(solution), env=env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    start_new_session=True, **kwargs)
        except OSError as exc:
            runtime.remove_entry(self.state, str(scratch.relative_to(self.state)), missing_ok=True)
            raise ValueError(f'start.sh could not be executed ({type(exc).__name__})') from None
        try:
            try:
                out, _ = proc.communicate(timeout=CLI_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                raise ValueError(f'the command did not finish within {CLI_SECONDS} s') from None
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            runtime.remove_entry(self.state, str(scratch.relative_to(self.state)), missing_ok=True)
        code = proc.returncode if proc.returncode >= 0 else 128 - proc.returncode
        result = {'exit_code': code, 'output': self.clean_output(out[-2_000_000:].decode('utf-8', 'replace'))[-8000:]}
        after = self.snapshot()
        changed = sorted(path for path, mark in after.items() if before.get(path) != mark)
        files = []
        for name in changed:
            path = Path(name)
            try:
                info = exchange.file_info(path, MAX_DOWNLOAD)
            except (OSError, ValueError):
                continue
            if stat.S_ISREG(info.st_mode) and info.st_size <= MAX_DOWNLOAD and \
                    path.suffix.casefold() in DOWNLOAD_SUFFIXES:
                files.append(self.register(path))
        result['downloads'] = files
        return result

    # -- desktop ------------------------------------------------------------------------------------------------
    def titles(self):
        return [str(w.get('title', '')) for w in self.desk.windows()]

    @staticmethod
    def filename_field(node):
        return (node.get('role') in ('text', 'entry') and 'editable' in node.get('states', [])
                and str(node.get('name', '')).rstrip(':').casefold() in ('file name', 'folder', 'directory'))

    @staticmethod
    def members(nodes, top):
        return [n for n in nodes if n.get('window') == top['ref']]

    def is_chooser(self, members):
        return (any(n.get('role') == 'label' and str(n.get('name', '')).rstrip(':').casefold() == 'look in'
                    for n in members) and any(self.filename_field(n) for n in members))

    def chooser(self, nodes):
        '''(dialog, its nodes) of an open Qt file dialog, found by its Look in label and File name field.'''
        for top in nodes:
            if top.get('role') == 'dialog':
                members = self.members(nodes, top)
                if self.is_chooser(members):
                    return top, members
        return None

    def dialog(self, nodes, title):
        for top in nodes:
            if top.get('role') == 'dialog' and str(top.get('name', '')).startswith(title):
                return top, self.members(nodes, top)
        return None

    def dialog_folder(self, members):
        combos = [n for n in members if n.get('role') == 'combo box' and not CHOOSER_FORMAT.search(str(n.get('name', '')))]
        if not combos:
            raise ValueError('the file dialog shows no folder')
        return str(min(combos, key=lambda n: n['bounds'][1]).get('name', ''))

    def dialog_control(self, top, target):
        '''The node a target designates; it must be inside the given dialog.'''
        if target is None:
            raise ValueError('coordinate input is not available in a file dialog; target its controls')
        record = self.desk.resolve(target)
        chain = record.get('chain', [])
        if not chain or chain[-1][0] != 'dialog' or chain[-1][1] != top.get('name'):
            raise ValueError('the control is outside the active file dialog')
        return record

    def confirm_chooser(self, members):
        """Validate the completed path and existing document before confirming a dialog."""
        field = next((n for n in members if self.filename_field(n)), None)
        typed = str(field.get('text') or '').strip() if field else ''
        if not typed:
            return
        text = typed if typed.startswith('/') else os.path.join(self.dialog_folder(members), typed)
        path = self.document_path(text, where='a file dialog')
        if path.suffix.casefold() in XML_SUFFIXES + ('.h2drumkit',):
            self.validate_document(path)

    def in_chooser(self, op, request, top, members):
        '''Rules of an open file dialog: only its File name field, file type list and buttons can be used.'''
        target = request.get('target')
        if op in ('type', 'fill'):
            if op == 'fill' or target is not None:
                if target is None or not self.filename_field(self.dialog_control(top, target)):
                    raise ValueError('text in a file dialog goes into its File name field')
            if op == 'type' and '/' in str(request.get('value', '')):
                # A dialog pre-fills a name and selects only its stem: a typed path replaces the whole field.
                self.desk.act({'op': 'press', 'key': 'Control+a', **({'target': target} if target is not None else {})})
            return
        if op in ('focus_window', 'maximize'):
            return
        if op == 'press':
            key = chord(request.get('key', ''))
            if key not in CHOOSER_KEYS or target is not None:
                raise ValueError('keys in a file dialog are limited to ' + ', '.join(sorted(CHOOSER_KEYS)))
            if key in ('return', 'enter'):
                self.confirm_chooser(members)
            elif key in ('backspace', 'delete'):
                field = next((n for n in members if self.filename_field(n)), None)
                if field is None or 'focused' not in field.get('states', []):
                    raise ValueError('delete keys act only inside the File name field of a file dialog')
            return
        if op in ('click', 'activate'):
            node = self.dialog_control(top, target)
            role, label = node.get('role'), str(node.get('name', ''))
            if role in ('push button', 'button'):
                cleaned = label.rstrip('.' + chr(8230)).casefold()
                if cleaned not in CHOOSER_BUTTONS:
                    raise ValueError('file dialog navigation is not available')
                if cleaned != 'cancel':
                    self.confirm_chooser(members)
            elif role in ('combo box', 'list item'):
                if not CHOOSER_FORMAT.search(label):
                    raise ValueError('file dialog navigation is not available')
            elif not self.filename_field(node):
                raise ValueError('file dialog navigation is not available')
            return
        raise ValueError('file dialog navigation is not available')

    def keep_chooser_inside(self, members):
        '''A file dialog that opened outside the document areas is moved into the project area.'''
        if self.inside(self.dialog_folder(members)):
            return
        field = next(n for n in members if self.filename_field(n))
        selector = {'role': 'text', 'name': field.get('name', '')}
        self.desk.act({'op': 'fill', 'target': selector, 'value': str(self.area('projects'))})
        self.desk.act({'op': 'press', 'key': 'Return'})
        again = self.chooser(self.desk.inspect().get('nodes', []))
        if again is None or not self.inside(self.dialog_folder(again[1])):
            self.desk.act({'op': 'press', 'key': 'Escape'})
            raise ValueError('file dialogs are confined to the document areas')
        self.desk.act({'op': 'fill', 'target': selector, 'value': ''})

    @staticmethod
    def editable_texts(members):
        return sorted((n for n in members if n.get('role') in ('text', 'entry') and 'editable' in n.get('states', [])
                       and 'disabled' not in n.get('states', [])), key=lambda n: (n['bounds'][1], n['bounds'][0]))

    def path_field(self, title, members):
        '''The path field of a dialog that holds one: the field beside the Image label of the drumkit properties,
        otherwise the first editable field.'''
        fields = self.editable_texts(members)
        if title == 'SoundLibrary Properties':
            label = next((n for n in members if n.get('role') == 'label' and n.get('name') == 'Image'), None)
            if label is None:
                return None
            row = [n for n in fields if abs(n['bounds'][1] - label['bounds'][1]) <= 6]
            return row[0] if row else None
        return fields[0] if fields else None

    def check_path_text(self, text, where, *, base=None):
        text = str(text or '').strip()
        if not text:
            return
        if '..' in Path(text).parts or chr(92) in text or text.startswith('~') or '://' in text:
            raise ValueError(f'{where} must be an absolute document path')
        if text.startswith('/'):
            self.document_path(text, where=where)
        elif base is not None:
            self.document_path(os.path.join(base, text), where=where)
        elif '/' in text:
            raise ValueError(f'{where} must be an absolute document path')

    def clicked(self, request, nodes):
        '''The node a click or activate designates (a private observation for coordinates).'''
        if request.get('target') is not None:
            return self.desk.resolve(request['target'])
        if 'x' in request and 'y' in request:
            return desktop.node_at({'nodes': nodes}, request['x'], request['y'])
        return None

    def guard_path_dialog(self, op, request, title, top, members, nodes):
        '''A dialog with a path field of its own: confirmation needs the path inside the document areas.'''
        confirm = PATH_DIALOGS[next(t for t in PATH_DIALOGS if title.startswith(t))]
        field = self.path_field(title, members)
        where = f'the path of {title}'
        confirming = False
        if op in ('click', 'activate'):
            node = self.clicked(request, nodes)
            confirming = bool(node) and node.get('role') in ('push button', 'button') and \
                str(node.get('name', '')).rstrip('.' + chr(8230)) == confirm
        elif op == 'press':
            key = chord(request.get('key', ''))
            confirming = key in CONFIRM_KEYS or key.startswith('alt+')
        if confirming and field is not None:
            text = field.get('text') or ''
            if title.startswith('SoundLibrary Properties'):
                if '/' in text or chr(92) in text:
                    self.check_path_text(text, where)
            else:
                self.check_path_text(text, where)
                if not str(text).strip():
                    raise ValueError(f'{where} is empty: enter an absolute path in the output area')

    def browser_folder(self, members):
        fields = self.editable_texts(members)
        return fields[0] if fields else None

    def guard_browser(self, op, request, members, nodes):
        '''The Audio File Browser lists one folder of the file system: it stays inside the document areas.'''
        if op in ('click', 'activate'):
            node = self.clicked(request, nodes)
            if node and node.get('role') in ('push button', 'button') and node.get('name') in ('Up', 'Home'):
                raise ValueError('the Audio File Browser stays in the document areas: type a document folder in its '
                                 'path field instead')
            if node and node.get('role') in ('push button', 'button') and node.get('name') == 'Open':
                self.confirm_browser(members)
        if op == 'press' and chord(request.get('key', '')) in CONFIRM_KEYS:
            self.confirm_browser(members)

    def folder_shown(self, text):
        '''A folder the Audio File Browser may open: an existing folder in the document areas (for a folder that does
        not exist the browser lists the root of the file system).'''
        text = str(text or '').strip()
        return bool(text) and text.startswith('/') and '..' not in Path(text).parts and self.inside(text) and \
            Path(os.path.normpath(text)).is_dir()

    def confirm_browser(self, members):
        fields = self.editable_texts(members)
        folder = str(fields[0].get('text') or '') if fields else ''
        self.check_path_text(folder, 'the Audio File Browser folder')
        if folder.strip() and not self.folder_shown(folder):
            raise ValueError('the Audio File Browser folder must be an existing document folder: type the folder, '
                             'then choose the file in the list')
        if len(fields) > 1:
            self.check_path_text(fields[1].get('text') or '', 'the Audio File Browser file name', base=folder)

    def fill_node(self, node, value):
        '''Replace the text of a field found in a private observation (its id is not a public ref).'''
        x, y, w, h = node.get('visible') or node['bounds']
        self.desk.act({'op': 'click', 'x': x + max(1, w // 2), 'y': y + max(1, h // 2)})
        self.desk.act({'op': 'press', 'key': 'Control+a'})
        self.desk.act({'op': 'type', 'value': value})

    def keep_browser_inside(self, members):
        '''An Audio File Browser that shows a folder outside the document areas is moved to the input area.'''
        field = self.browser_folder(members)
        if field is None:
            return
        folder = str(field.get('text') or '').strip()
        listed_root = any(n.get('role') == 'table cell' and str(n.get('name', '')).startswith('/') for n in members)
        if folder and self.inside(folder.rstrip('/') or '/') and not listed_root:
            return
        self.fill_node(field, str(self.area('inputs')) + '/')
        self.desk.act({'op': 'press', 'key': 'Return'})
        again = self.dialog(self.desk.inspect().get('nodes', []), BROWSER_TITLE)
        moved = again and self.browser_folder(again[1])
        if not moved or not self.folder_shown(moved.get('text')):
            raise ValueError('the Audio File Browser is confined to the document areas')

    def wmctrl(self, *args):
        return subprocess.run(['wmctrl', *args], env={**os.environ, **self.session.env()}, capture_output=True, timeout=10)

    def close_scripts(self, nodes):
        '''Playlist script menus and dialogs run programs, the repository list takes any address: close them and
        fail the request.'''
        titles = [t for t in self.titles() if any(t.startswith(label) for label in SCRIPT_TITLES)]
        menu = any(n.get('role') == 'menu item' and n.get('name') in SCRIPT_ITEMS[1:] for n in nodes)
        if not titles and not menu:
            return
        self.desk.act({'op': 'press', 'key': 'Escape'})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            left = [t for t in self.titles() if any(t.startswith(label) for label in SCRIPT_TITLES)]
            if not left:
                break
            for title in left:
                self.wmctrl('-F', '-c', title)
            time.sleep(0.3)
        raise ValueError('playlist scripts and the repository list are not available')

    def refuse_scripts(self, op, request, nodes):
        if op in ('click', 'activate'):
            node = self.clicked(request, nodes)
            if node and node.get('role') in ('menu item', 'menu') and node.get('name') in SCRIPT_ITEMS:
                raise ValueError('playlist scripts are not available')

    def refuse_repository(self, op, request, nodes):
        if op in ('click', 'activate'):
            node = self.clicked(request, nodes)
            if node and node.get('role') in ('push button', 'button') and node.get('name') == REPOSITORY_BUTTON:
                raise ValueError('the drumkit repository list cannot be edited here')

    @staticmethod
    def active_window(nodes):
        return next((n for n in nodes if n.get('role') in desktop.WINDOW_ROLES and n.get('parent') is None
                     and 'active' in n.get('states', [])), None)

    def after_gui(self):
        nodes = self.desk.inspect().get('nodes', [])
        self.close_scripts(nodes)
        active = self.active_window(nodes)
        if active is None or active.get('role') != 'dialog':
            return
        members = self.members(nodes, active)
        if self.is_chooser(members):
            self.keep_chooser_inside(members)
        elif str(active.get('name', '')).startswith(BROWSER_TITLE):
            self.keep_browser_inside(members)

    def typed_text(self, value):
        '''Typed text is passed through unchanged; a file system path in it must stay in the document areas,
        wherever it is typed (a file dialog or one of the product's own path fields).'''
        text = str(value)
        if chr(92) in text and ('/' in text or text.strip().startswith(chr(92))):
            raise ValueError('typed text does not contain backslash paths; document paths use /')
        stripped = text.strip()
        if stripped.startswith(('/', '~')) or '://' in stripped:
            self.document_path(stripped, where='a typed document path')
        elif '/' in stripped and '..' in Path(stripped).parts:
            raise ValueError('typed paths must be absolute document paths')

    def guard_pointer(self, event):
        """Apply path-dialog rules to the pointer part of every input operation."""
        request = event['pointer']
        op = request['op']
        nodes = self.desk.inspect().get('nodes', [])
        self.refuse_scripts(op, request, nodes)
        self.refuse_repository(op, request, nodes)
        active = self.active_window(nodes)
        if active is None or active.get('role') != 'dialog':
            return
        title = str(active.get('name', ''))
        members = self.members(nodes, active)
        if any(title.startswith(label) for label in SCRIPT_TITLES):
            node = self.clicked(request, nodes) if op in ('click', 'activate') else None
            if node and str(node.get('name', '')).casefold() in ('cancel', 'no', 'close'):
                return
            raise ValueError('playlist scripts and the repository list are not available')
        if self.is_chooser(members):
            if op != 'move':
                self.in_chooser(op, request, active, members)
        elif any(title.startswith(label) for label in PATH_DIALOGS):
            if op == 'drag':
                raise ValueError('drag input is not available in path dialogs')
            self.guard_path_dialog(op, request, title, active, members, nodes)
        elif title.startswith(BROWSER_TITLE):
            if op == 'drag':
                raise ValueError('drag input is not available in the file browser')
            self.guard_browser(op, request, members, nodes)

    def gui(self, op, data):
        request = {key: value for key, value in data.items() if key != 'op'}
        if op in ('type', 'fill'):
            self.typed_text(request.get('value', ''))
        guarded = op in GUI_GUARDED
        if guarded:
            # The rules of the active window apply: a file dialog, a dialog with a path field of its own, the Audio
            # File Browser or the Playlist Browser. A message box over them only answers.
            nodes = self.desk.inspect().get('nodes', [])
            active = self.active_window(nodes)
            if active is not None and active.get('role') == 'dialog':
                title, members = str(active.get('name', '')), self.members(nodes, active)
                if self.is_chooser(members):
                    self.in_chooser(op, request, active, members)
                elif any(title.startswith(label) for label in PATH_DIALOGS):
                    self.guard_path_dialog(op, request, title, active, members, nodes)
                    if title.startswith('Sound Library import'):
                        self.refuse_repository(op, request, nodes)
                elif title.startswith(BROWSER_TITLE):
                    self.guard_browser(op, request, members, nodes)
                elif title.startswith('Playlist Browser'):
                    self.refuse_scripts(op, request, nodes)
        result = self.desk.act({'op': op, **request})
        if op in GUI_GUARDED:
            self.after_gui()
        return result

    # -- dispatch -----------------------------------------------------------------------------------------------
    def notes(self):
        areas = ', '.join(f'{area} {self.area(area)}' for area in AREAS)
        return [f'Document areas: {areas}. Uploads arrive in the input area; the application reads and writes them as '
                'ordinary files (its working folder is the files folder that holds them), and files it leaves in the '
                'document areas can be downloaded.'
                if note == 'DOCUMENT_AREAS' else note for note in NOTES]

    def help(self):
        limits = dict(LIMITS, ready_seconds=self.config.ready_timeout)
        return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=limits, notes=self.notes(),
                                     examples=examples(self.area('inputs')), osc_endpoint=OSC_ENDPOINT,
                                     osc_commands=osc_catalog(), cli_endpoint=CLI_ENDPOINT)

    def dispatch(self, data):
        op = runtime.validate(OPERATIONS, data)
        if op == 'help':
            return self.help()
        if op == 'status':
            return self.status()
        if op == 'reset':
            return self.start(True)
        if op == 'restart':
            return self.start(False)
        if op == 'osc':
            return self.osc(data)
        if op == 'cli':
            return self.cli(data)
        if op == 'upload':
            return self.upload(data)
        if op == 'list_files':
            return self.list_files()
        if op == 'download':
            return self.download(data)
        if op == 'settings':
            return self.settings()
        if op in ('observe', 'windows', 'screenshot'):
            self.after_gui()
        if op == 'observe':
            return self.desk.observe(**{k: v for k, v in data.items() if k != 'op'})
        if op == 'windows':
            return {'windows': self.desk.windows()}
        if op == 'screenshot':
            return self.desk.screenshot(**{k: v for k, v in data.items() if k != 'op'})
        return self.gui(op, data)

    def redact(self, text):
        '''Text with private filesystem locations replaced; document paths stay readable (they are public).'''
        text = str(text)
        if '/' not in text:
            return text
        return TOKEN.sub(lambda m: m.group(0) if self.inside(m.group(0)) else self.hide(m.group(0)), text)

    def clean(self, value):
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if isinstance(value, dict):
            return {key: (item if key in ('png_base64', 'body_base64') else self.clean(item))
                    for key, item in value.items()}
        return value


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

    def __init__(self, sock, broker):
        super().__init__('blackbox', Handler, bind_and_activate=False)
        self.socket.close()
        self.socket, self.address_family = sock, sock.family
        self.server_name, self.server_port = 'localhost', 0
        self.broker = broker
        self.in_flight = 0
        self.count = threading.Lock()


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def address_string(self):
        return 'blackbox'

    def reply(self, code, value):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        server, broker, started, op = self.server, self.server.broker, time.monotonic(), None
        with server.count:
            busy = server.in_flight >= MAX_IN_FLIGHT
            if not busy:
                server.in_flight += 1
        if busy:
            self.reply(429, {'error': 'Busy', 'detail': 'too many pending requests'})
            return
        try:
            if self.path != '/rpc':
                raise ValueError('unknown RPC endpoint')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_REQUEST:
                raise ValueError('request size outside limits')
            data = runtime.strict_json_loads(self.rfile.read(length))
            op = data.get('op', 'help') if isinstance(data, dict) else None
            outcome, done = {}, threading.Event()

            def work():
                try:
                    if not broker.lock.acquire(timeout=RPC_SECONDS):
                        raise TimeoutError
                    try:
                        outcome['value'] = broker.clean(broker.dispatch(data))
                    finally:
                        broker.lock.release()
                except BaseException as exc:
                    outcome['error'] = exc
                finally:
                    done.set()
            threading.Thread(target=work, daemon=True).start()
            if not done.wait(RPC_SECONDS):
                code, value = 408, {'error': 'TimeoutError', 'detail': 'black-box request deadline exceeded'}
            elif 'error' in outcome:
                exc = outcome['error']
                if isinstance(exc, TimeoutError) or getattr(exc, 'timeout', False) is True:
                    code, value = 408, {'error': 'TimeoutError', 'detail': 'black-box request deadline exceeded'}
                else:
                    code, value = 400, {'error': type(exc).__name__, 'detail': broker.redact(str(exc))[:600]}
            else:
                code, value = 200, outcome['value']
        except Exception as exc:
            code, value = 400, {'error': type(exc).__name__, 'detail': broker.redact(str(exc))[:600]}
        finally:
            with server.count:
                server.in_flight -= 1
        server.audit.record(op, code, time.monotonic() - started)
        self.reply(code, value)


def main(argv=None):
    config = runtime.options(state='/reference/state', log_dir='/reference', work='/reference/work',
                             ready_timeout=30.0).parse_args(argv)
    Path(config.work).mkdir(parents=True, exist_ok=True)
    # SIGTERM ends the process through the finally
    # block, which stops the product and closes the desktop session.
    runtime.exit_on_sigterm()
    broker = Broker(config)
    server = None
    try:
        # A product that fails to start is reported by status; the runtime keeps serving.
        broker.start(True)
        server = Server(runtime.listen(config.socket, config.socket_mode), broker)
        server.audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
        server.serve_forever()
    finally:
        broker.close()
        if server is not None:
            server.server_close()


if __name__ == '__main__':
    main()
