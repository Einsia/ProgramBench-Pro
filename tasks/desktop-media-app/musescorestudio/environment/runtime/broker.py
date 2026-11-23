#!/usr/bin/env python3
"""MuseScore Studio 4.7.6 desktop, command and document exchange runtime.

All application responses come from the running application.
"""
from __future__ import annotations

import base64
import http.server
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import socketserver
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import document_exchange as exchange
import blackbox_desktop as desktop  # noqa: E402

PRODUCT = 'MuseScore Studio 4.7.6'
SCREEN = (1440, 900)
SETTLE = 0.5
NL = chr(10)
MAX_REQUEST = 11_200_000
MAX_FILE = 8_000_000
RPC_SECONDS = 90
CONVERT_SECONDS = 75
MAX_IN_FLIGHT = 8
MAX_TEXT = 1_500_000
MAX_LISTED = 400
AREAS = ('inputs', 'outputs', 'projects')
# Uploaded documents are scores, MIDI, style files and conversion jobs; no code, plug-in or library suffix.
UPLOAD_SUFFIXES = ('.mscz', '.mscx', '.mxl', '.musicxml', '.xml', '.mid', '.midi', '.kar', '.mei', '.mnx', '.gp',
                   '.gp3', '.gp4', '.gp5', '.gpx', '.ptb', '.cap', '.capx', '.bww', '.mgu', '.sgu', '.ove', '.scw',
                   '.mss', '.json', '.txt')
DOWNLOAD_SUFFIXES = ('.mscz', '.mscx', '.mss', '.musicxml', '.mxl', '.xml', '.mid', '.midi', '.mei', '.mnx', '.wav',
                     '.flac', '.ogg', '.mp3', '.pdf', '.png', '.svg', '.lrc', '.brf', '.json', '.txt')
NOISE = ('findlib:', 'Using fallback for library', '/lib/x86_64-linux-gnu/', 'dbus-daemon', 'SpiRegistry')
# Windows closed on sight, before and after every input operation: the print dialog has a free output-path field,
# and Preferences holds free folder and file fields (plug-in, SoundFont, VST3, template and style folders, the FFmpeg
# library location) that the document-area guard cannot confine (the GTK file choosers are confined separately).
UNSAFE_DIALOGS = ('Print', 'Preferences')
CHOOSER_KEYS = {'ctrl+a', 'ctrl+l', 'escape', 'return', 'enter'}
POPUP_KEYS = {'up', 'down', 'home', 'end', 'page_up', 'page_down', 'pageup', 'pagedown', 'prior', 'next', 'return',
              'enter', 'escape'}
CHOOSER_BUTTONS = ('cancel', 'open', 'save', 'select', 'choose', 'ok', 'replace')
CHOOSER_PICK = ('save', 'open', 'select', 'choose')
CHOOSER_FORMATS = re.compile('.')
JOB_KEYS = ('in', 'out', 'transpose', 'page', 'visibleParts', 'copyright', 'tracksDiff')
# The product's own command-line options that convert passes through: (names, value kind, summary).
OPTIONS = (
    (('-o', '--export-to'), 'output', 'Export the score to this file; the format follows the file suffix.'),
    (('-j', '--job'), 'job', 'Process a conversion job: an uploaded .json document that lists in/out pairs as absolute document paths.'),
    (('-P', '--export-score-parts'), 'flag', 'With -o file.pdf: export the score and its parts.'),
    (('-f', '--force'), 'flag', 'The product force option.'),
    (('--score-meta',), 'flag', 'Export score metadata as a JSON document printed on standard output.'),
    (('--score-elements',), 'flag', 'Print the score elements as JSON.'),
    (('--score-media',), 'flag', 'The product score-media mode.'),
    (('--score-parts',), 'flag', 'Generate parts data for the given score and save them to separate mscz files.'),
    (('--score-parts-pdf',), 'flag', 'Export the score parts as PDF documents.'),
    (('--score-transpose',), 'json', 'Transpose the score with these JSON options and export it.'),
    (('--transpose',), 'json', 'Transpose options (JSON) used with -o.'),
    (('--page',), 'integer', 'Export only this page with -o.'),
    (('--region',), 'text', 'Export only this score region (JSON text) with -o.'),
    (('--unroll-repeats',), 'flag', 'Unroll repeats.'),
    (('-S', '--style'), 'document', 'Load this style file (an uploaded .mss).'),
    (('-M', '--midi-operations'), 'document', 'MIDI import operations file.'),
    (('--highlight-config',), 'document', 'Highlight configuration for --score-media.'),
    (('--sound-profile',), 'text', 'Sound profile name.'),
    (('-r', '--image-resolution'), 'number', 'Output resolution (DPI) for image export.'),
    (('-T', '--trim-image'), 'integer', 'Trim image margins (pixels).'),
    (('-b', '--bitrate'), 'integer', 'Bitrate in kbps with -o file.mp3.'),
    (('--musicxml-use-default-font',), 'flag', 'MusicXML import: use the default font.'),
    (('--musicxml-infer-text-type',), 'flag', 'MusicXML import: infer the text type.'),
    (('--gp-linked',), 'flag', 'Guitar Pro import: create linked tablature staves.'),
    (('--gp-experimental',), 'flag', 'Guitar Pro import: experimental features.'),
    (('-t', '--test-mode'), 'flag', 'Set the test mode flag for all files.'),
    (('--template-mode',), 'flag', 'Save in template mode, no page size.'),
    (('-v', '--version'), 'flag', 'Print the version.'),
    (('--long-version',), 'flag', 'Print detailed version information.'),
)
BY_NAME = {name: (names[-1], kind) for names, kind, _ in OPTIONS for name in names}
# A run needs one of these: without one the product starts its desktop window, which convert never wants.
MODES = {'--export-to', '--job', '--score-meta', '--score-elements', '--score-media', '--score-parts',
         '--score-parts-pdf', '--score-transpose', '--version', '--long-version'}


def plain_name(value):
    if (not isinstance(value, str) or Path(value).name != value or chr(92) in value or value in ('', '.', '..')
            or len(value) > 255 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError('a file name must be a basename without path separators or control characters')
    return value


def chord(key):
    return '+'.join(part.strip() for part in str(key).casefold().replace('control', 'ctrl').split('+'))


def path_like(value):
    return value.startswith(('/', '~', '..', './')) or '://' in value


def quiet(text):
    lines = [line for line in text.splitlines() if not any(mark in line for mark in NOISE)]
    return NL.join(lines)[-4000:]


def kill(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        pass


TARGET = {'type': ['string', 'object'],
          'description': 'A control: a ref from the latest observe, or an object with ref, or role and/or name '
                         '(also label or text), optional exact (default true) and nth (0-based).'}


def specs():
    '''Help specs: the shared desktop operations plus this product's channels.'''
    ops = {
        'help': {'kind': 'info', 'fields': {},
                 'summary': 'This description of operations, fields, convert options and limits.'},
        'status': {'kind': 'lifecycle', 'fields': {},
                   'summary': 'Whether the application is running and ready (an accessible window).'},
        'reset': {'kind': 'lifecycle', 'fields': {},
                  'summary': 'Fresh instance: new desktop session and empty data, inputs, outputs and projects; the '
                             'application is started again.'},
        'restart': {'kind': 'lifecycle', 'fields': {},
                    'summary': 'Relaunch the application with the same data, uploaded inputs, outputs and projects.'},
        'convert': {'kind': 'http',
                    'summary': 'Run the product own command line once (start.sh with these arguments, no desktop '
                               'window) on documents of the owned areas and return its exit code, standard output, '
                               'a log tail and the files it wrote (refs for download). See convert_options.',
                    'fields': {'args': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                        'description': 'Command-line arguments, 1 to 40: product options from '
                                                       'convert_options and input documents (an uploaded name or an '
                                                       'absolute path in the document areas). Output paths are names '
                                                       'or absolute paths in the document areas.'}}},
        'upload': {'kind': 'files',
                   'summary': 'Place one document (score, MIDI, MusicXML, style, job JSON or text) in the input area, '
                              'replacing a document of the same name; file dialogs and convert accept it by name.',
                   'fields': {
                       'filename': {'type': 'string', 'required': True,
                                    'description': 'Document name: a basename with one of the suffixes in help.'},
                       'base64': {'type': 'string', 'required': True,
                                  'description': f'File bytes, base64 encoded, at most {MAX_FILE} bytes.'}}},
        'list_files': {'kind': 'files', 'fields': {},
                       'summary': 'Uploaded input names and the pending downloads: files the application or convert '
                                  'wrote into the output and project areas since they were last listed, each with a '
                                  'ref and its path relative to the owned files folder.'},
        'download': {'kind': 'files', 'summary': 'Retrieve a pending download once, as body_base64.',
                     'fields': {'ref': {'type': 'string', 'required': True,
                                        'description': 'A ref from list_files or from a convert reply.'}}},
    }
    for op, spec in desktop.operations(SCREEN).items():
        ops[op] = spec
    return runtime.check_operations(ops)


OPERATIONS = specs()
GUI_GUARDED = {op for op, spec in OPERATIONS.items() if spec['kind'] == 'gui'} - {'zoom', 'wait', 'move'}
NOTES = [
    'convert runs the product own command line (start.sh with the given arguments) on documents of the owned '
    'areas; no product behaviour is simulated.',
    'DOCUMENT_AREAS',
    'File dialogs are standard GTK file choosers (accessible role file chooser): name a document by typing its '
    'absolute path in the file-name field (Control+L opens the location field of an Open dialog) and confirm; '
    'navigation elsewhere is refused and a dialog confirms only inside the document areas.',
    'A typed or filled absolute path outside the document areas is refused wherever it is typed.',
    'After a save or export in the application, or a convert, list_files shows the new files with refs (a path '
    'relative to the owned files folder); download retrieves each once.',
    'The Print and Preferences dialogs are closed on sight and the request fails (they hold free folder, file and '
    'library fields).',
    'Some damaged inputs make the product wait without returning in command-line mode (an import that reports errors); convert ends it after 75 s and the request fails with a timeout error.',
    'restart keeps uploaded inputs, outputs and projects; reset discards them.',
    'The application is a Qt Quick program: its windows and file choosers are reachable through accessibility; its '
    'menus, buttons and score canvas are visible in screenshots and are operated by coordinates and keys.',
]
LIMITS = {'file_bytes': MAX_FILE, 'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_SECONDS,
          'convert_seconds': CONVERT_SECONDS, 'screen': list(SCREEN), 'ready_seconds': None}


def examples(inputs, outputs):
    '''Request examples for help; the paths name this runtime own document areas.'''
    inputs, outputs = str(inputs), str(outputs)
    return [{'op': 'upload', 'filename': 'score.mscz', 'base64': '<base64 bytes>'},
            {'op': 'convert', 'args': [inputs + '/score.mscz', '-o', outputs + '/score.musicxml']},
            {'op': 'convert', 'args': ['--long-version']},
            {'op': 'list_files'},
            {'op': 'download', 'ref': 'd1'},
            {'op': 'observe'},
            {'op': 'press', 'key': 'Control+o'},
            {'op': 'type', 'value': inputs + '/score.mscz'}]


class MuseProduct(runtime.Product):
    '''start.sh with the instance layout plus the owned document areas.'''

    def prepare(self, fresh):
        super().prepare(fresh)
        exchange.prepare(self, AREAS)


class Broker:
    def __init__(self, config):
        self.config = config
        self.state = Path(config.state)
        self.log = runtime.BoundedLog(config.log_dir)
        self.product = MuseProduct(config, log=self.log, directories=runtime.layout(config.state))
        self.session = self.desk = self.helper = None
        self.downloads, self.seen, self.serial = {}, {}, 0
        self.lock = threading.RLock()
        self.hide = runtime.redactor(config.solution, config.state, config.work, config.log_dir,
                                     Path(__file__).resolve().parent, '/app/solution', '/reference')

    def read_document(self, path, limit=None):
        return exchange.read(self.state / 'files', path, MAX_FILE if limit is None else limit)

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def area(self, name):
        return self.state / 'files' / name

    def start_session(self):
        if self.session is not None:
            self.session.close()
        if self.desk is not None:
            self.desk.close()
        self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, maximize=True, audio=True,
                                              log_dir=Path(self.config.log_dir) / 'desktop').start()
        self.desk = desktop.Desktop(self.session, settle=SETTLE, log_dir=Path(self.config.log_dir) / 'desktop', pointer_guard=self.guard_pointer)

    def start(self, fresh):
        '''Start (fresh: a new desktop session and empty instance) and wait for an accessible window.'''
        self.product.stop()
        if fresh or self.session is None or not self.session.alive():
            self.start_session()
        if fresh:
            self.downloads.clear()
            self.seen.clear()
        self.product.extra = {key: value for key, value in self.session.env().items()
                              if key not in ('HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'DATA_DIR')}
        self.product.extra['PBP_DOCUMENTS_ROOT'] = str(self.state / 'files')
        started = self.product.start(fresh)
        if started:
            runtime.wait_until(self.product, lambda: self.desk.ready(minimum=(200, 150)),
                               failure=f'the application showed no accessible window within '
                                       f'{self.config.ready_timeout:g} s')
        return self.status()

    def status(self):
        return self.product.status()

    def close(self):
        self.product.stop()
        for item in (self.desk, self.session, self.helper):
            if item is not None:
                item.close()

    # -- documents ----------------------------------------------------------------------------------------------
    def inside(self, value):
        '''Whether an absolute path lies in the document areas (dot segments removed first).'''
        path = os.path.normpath(str(value))
        root = str(self.state / 'files')
        return path == root or path.startswith(root + os.sep)

    def document_path(self, value, *, where):
        '''Validate text that names a document: an absolute path in the document areas.'''
        text = str(value).strip()
        areas = ', '.join(str(self.area(name)) for name in AREAS)
        if '\x00' in text or '://' in text or text.startswith('~'):
            raise ValueError(f'{where} accepts absolute document paths only (no URLs or home folders)')
        path = Path(os.path.normpath(text))
        if not path.is_absolute() or not self.inside(path):
            raise ValueError(f'{where} is confined to the document areas: use an absolute path under {areas}')
        if any(part.is_symlink() for part in (Path(text), *Path(text).parents)):
            raise ValueError(f'{where} may not traverse symbolic links')
        if not self.inside(path.resolve()):
            raise ValueError(f'{where} resolves outside the document areas')
        return path

    def input_document(self, value):
        if not isinstance(value, str) or not value or len(value) > 4000 or any(ord(c) < 32 for c in value):
            raise ValueError('a document is an uploaded name or an absolute document path')
        if '/' in value:
            path = self.document_path(value, where='a document argument')
        else:
            name = plain_name(value)
            path = next((self.area(a) / name for a in AREAS if (self.area(a) / name).is_file()),
                        self.area('inputs') / name)
        return self.document_path(str(path), where='a document argument')

    def output_path(self, value):
        if '/' in value:
            return self.document_path(value, where='an output argument')
        return self.document_path(str(self.area('outputs') / plain_name(value)), where='an output argument')

    def check_job(self, path):
        if path.suffix.casefold() != '.json' or not path.is_file():
            raise ValueError('a job is an uploaded .json document')
        try:
            data = runtime.strict_json_loads(self.read_document(path).decode('utf-8'))
        except (OSError, ValueError, RecursionError):
            raise ValueError('the job document is not valid JSON') from None
        if not isinstance(data, list) or not 1 <= len(data) <= 50:
            raise ValueError('a job document is a list of 1 to 50 entries')
        for entry in data:
            if not isinstance(entry, dict) or set(entry) - set(JOB_KEYS) or not isinstance(entry.get('in'), str):
                raise ValueError('each job entry is an object with in and out and optionally ' + ', '.join(JOB_KEYS[2:]))
            self.document_path(entry['in'], where='a job input')
            out = entry.get('out', [])
            items = [out] if isinstance(out, str) else out
            if not isinstance(items, list) or len(items) > 50:
                raise ValueError('out is a path or a list of paths')
            for item in items:
                if isinstance(item, str):
                    self.document_path(item, where='a job output')
                elif isinstance(item, list) and len(item) == 2 and all(isinstance(p, str) for p in item):
                    self.document_path(item[0], where='a job output')
                    if '/' in item[1] or len(item[1]) > 20:
                        raise ValueError('a part output suffix is a short text')
                else:
                    raise ValueError('out items are paths or [prefix, suffix] pairs')
            if 'tracksDiff' in entry:
                if not isinstance(entry['tracksDiff'], str):
                    raise ValueError('tracksDiff is a path')
                self.document_path(entry['tracksDiff'], where='a job output')
            if 'page' in entry and (type(entry['page']) is not int or entry['page'] < 0):
                raise ValueError('page is a whole number')
            if 'visibleParts' in entry and (not isinstance(entry['visibleParts'], list) or len(entry['visibleParts']) > 100
                                            or not all(type(p) is int for p in entry['visibleParts'])):
                raise ValueError('visibleParts is a list of whole numbers')
            if 'copyright' in entry and (not isinstance(entry['copyright'], dict)
                                         or not isinstance(entry['copyright'].get('text', ''), str)
                                         or len(entry['copyright'].get('text', '')) > 500):
                raise ValueError('copyright is an object with a short text')
            if 'transpose' in entry and not isinstance(entry['transpose'], dict):
                raise ValueError('transpose is an object')

    def option_value(self, kind, value, name):
        if not isinstance(value, str) or len(value) > 4000 or any(ord(c) < 32 for c in value):
            raise ValueError(f'invalid value for {name}')
        if kind == 'output':
            return str(self.output_path(value))
        if kind == 'document':
            return str(self.input_document(value))
        if kind == 'job':
            path = self.input_document(value)
            self.check_job(path)
            return str(path)
        if kind == 'integer':
            if not re.fullmatch('[0-9]{1,6}', value):
                raise ValueError(f'{name} takes a whole number')
            return value
        if kind == 'number':
            try:
                number = float(value)
            except ValueError:
                raise ValueError(f'{name} takes a number') from None
            if not math.isfinite(number) or not 0 < number <= 100000:
                raise ValueError(f'{name} takes a number between 0 and 100000')
            return value
        if kind == 'json':
            try:
                parsed = runtime.strict_json_loads(value)
            except (ValueError, RecursionError):
                raise ValueError(f'{name} takes a JSON document') from None
            if not isinstance(parsed, (dict, list)):
                raise ValueError(f'{name} takes a JSON object or list')
            return value
        if len(value) > 400:
            raise ValueError(f'{name} takes a short text')
        return value

    def convert_arguments(self, args):
        if not isinstance(args, list) or not 1 <= len(args) <= 40 or not all(isinstance(a, str) for a in args):
            raise ValueError('args is a list of 1 to 40 strings')
        argv, index, seen, documents = [], 0, set(), 0
        while index < len(args):
            token = args[index]
            index += 1
            if len(token) > 4000 or any(ord(c) < 32 for c in token):
                raise ValueError('invalid argument text')
            if not token.startswith('-'):
                argv.append(str(self.input_document(token)))
                documents += 1
                continue
            name, equals, inline = token.partition('=') if token.startswith('--') else (token, '', '')
            spec = BY_NAME.get(name)
            if spec is None:
                raise ValueError(f'option {name[:40]} is not available; see convert_options in help')
            kind = spec[1]
            seen.add(spec[0])
            if kind == 'flag':
                if equals:
                    raise ValueError(f'{name} takes no value')
                argv.append(name)
                continue
            if equals:
                value = inline
            else:
                if index >= len(args):
                    raise ValueError(f'{name} needs a value')
                value = args[index]
                index += 1
            argv += [name, self.option_value(kind, value, name)]
        if not seen & MODES:
            raise ValueError('convert needs a conversion option (-o, -j or a --score-* mode) or a version option; see convert_options in help')
        if not seen & {'--job', '--version', '--long-version'} and documents < 1:
            raise ValueError('convert needs an input document (an uploaded name or an absolute document path)')
        return argv

    def upload(self, data):
        filename = plain_name(data['filename'])
        if not filename.casefold().endswith(UPLOAD_SUFFIXES):
            raise ValueError('uploads are score, MIDI, style, job or text documents (suffixes '
                             + ' '.join(UPLOAD_SUFFIXES) + ')')
        payload = base64.b64decode(data['base64'], validate=True)
        if len(payload) > MAX_FILE:
            raise ValueError(f'upload exceeds {MAX_FILE} bytes')
        if payload[:4] == bytes([127, 69, 76, 70]) or payload[:2] == b'#!':
            raise ValueError('executable documents cannot be uploaded')
        target = self.area('inputs') / filename
        exchange.write(self.area('inputs'), target, payload, self.product.account())
        return {'uploaded': True, 'filename': filename, 'size': len(payload)}

    def register(self, path, info):
        stat = info
        self.seen[str(path)] = (stat.st_mtime_ns, stat.st_size)
        self.serial += 1
        ref = f'd{self.serial}'
        rel = str(path.relative_to(self.state / 'files'))
        for old in [r for r, (_rel, known) in self.downloads.items() if known == path]:
            del self.downloads[old]
        self.downloads[ref] = (rel, path)
        return {'ref': ref, 'filename': rel, 'size': stat.st_size}

    def scan(self):
        found = []
        for area in ('outputs', 'projects'):
            for relative, info in exchange.entries(self.area(area)):
                path = self.area(area) / relative
                if not stat.S_ISREG(info.st_mode) or path.suffix.casefold() not in DOWNLOAD_SUFFIXES:
                    continue
                if any(part.endswith('_saving') for part in Path(relative).parts[:-1]):
                    continue
                if info.st_size > MAX_FILE or self.seen.get(str(path)) == (info.st_mtime_ns, info.st_size):
                    continue
                found.append(self.register(path, info))
                if len(found) >= MAX_LISTED:
                    return found
        return found

    def list_files(self):
        self.scan()
        inputs = [name for name, info in runtime.list_directory(self.area('inputs'))
                  if stat.S_ISREG(info.st_mode) and info.st_nlink == 1]
        pending = []
        for ref, (relative, path) in self.downloads.items():
            try:
                info = exchange.file_info(self.state / 'files', path)
            except (OSError, ValueError):
                continue
            pending.append({'ref': ref, 'filename': relative, 'size': info.st_size})
        return {'inputs': inputs, 'downloads': pending}

    def download(self, data):
        ref = data['ref']
        if ref not in self.downloads:
            raise ValueError('unknown download reference; use list_files')
        relative, path = self.downloads.pop(ref)
        payload = self.read_document(path)
        return {'filename': relative, 'size': len(payload), 'body_base64': base64.b64encode(payload).decode()}

    # -- command-line conversion --------------------------------------------------------------------------------
    def convert_session(self):
        '''A second private desktop for command-line runs: the product needs a display and a session bus there.'''
        if self.helper is None or not self.helper.alive():
            if self.helper is not None:
                self.helper.close()
            self.helper = desktop.DesktopSession(user=self.config.user, screen=SCREEN, maximize=False, audio=False,
                                                 log_dir=Path(self.config.log_dir) / 'convert-desktop').start()
        return self.helper

    def convert_environment(self, session):
        account = self.product.account()
        base = self.state / 'convert'
        dirs = {'HOME': base / 'home', 'TMPDIR': base / 'tmp', 'XDG_CACHE_HOME': base / 'cache',
                'XDG_CONFIG_HOME': base / 'config', 'DATA_DIR': base / 'data'}
        owner = 0 if self.product.switching() else account.pw_uid
        group = 0 if self.product.switching() else account.pw_gid
        with runtime.owned_directory(self.state, 'convert', uid=owner, gid=group, mode=0o711) as parent:
            for path in dirs.values():
                with runtime.owned_directory(parent, path.name, uid=account.pw_uid, gid=account.pw_gid):
                    pass
        env = self.product.environment()
        env.update({key: str(path) for key, path in dirs.items()})
        env.update({key: value for key, value in session.env().items() if key not in dirs})
        env.pop('PULSE_SERVER', None)
        return env

    def convert(self, data):
        argv = self.convert_arguments(data['args'])
        script = self.product.solution / 'start.sh'
        if not script.is_file():
            raise ValueError('start.sh does not exist in the solution directory')
        env = self.convert_environment(self.convert_session())
        kwargs = {}
        if self.product.switching():
            account = self.product.account()
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        proc = subprocess.Popen([str(script), *argv], cwd=str(self.product.solution), env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, **kwargs)
        try:
            out, err = proc.communicate(timeout=CONVERT_SECONDS)
        except subprocess.TimeoutExpired:
            kill(proc)
            raise TimeoutError(f'the product did not finish within {CONVERT_SECONDS} s') from None
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        return {'exit_code': proc.returncode, 'ok': proc.returncode == 0,
                'stdout': out.decode('utf-8', errors='replace')[:MAX_TEXT],
                'log': quiet(err.decode('utf-8', errors='replace')), 'downloads': self.scan()}

    # -- desktop ------------------------------------------------------------------------------------------------
    def titles(self):
        return [str(w.get('title', '')) for w in self.desk.windows()]

    def chooser_state(self):
        '''Whether a file chooser is open, and the bounds of its open lists, from a private observation (the
        caller refs stay valid). A combo box list is its own top-level menu in AT-SPI.'''
        nodes = self.desk.inspect().get('nodes', [])
        if not any(n.get('role') == 'file chooser' for n in nodes):
            return False, []
        by_id = {n.get('ref'): n for n in nodes}
        popups = {n.get('parent') for n in nodes if n.get('role') == 'menu item'}
        return True, [by_id[ref]['bounds'] for ref in popups if ref in by_id and by_id[ref].get('role') == 'menu']

    @staticmethod
    def format_item(record):
        return record.get('role') == 'menu item' and bool(CHOOSER_FORMATS.search(str(record.get('name', ''))))

    def chooser_control(self, target):
        '''The node a target designates; it must be inside the open file chooser.'''
        if target is None:
            raise ValueError('coordinate input is not available in a file chooser; target its controls')
        record = self.desk.resolve(target)
        if not any(role == 'file chooser' for role, _name in record.get('chain', [])):
            raise ValueError('the control is outside the active file chooser')
        return record

    def over(self, request, popups):
        '''A wheel request whose point lies on an open list.'''
        if request.get('target') is not None:
            x, y, w, h = self.desk.resolve(request['target'])['bounds']
            point = (x + w // 2, y + h // 2)
        elif 'x' in request and 'y' in request:
            point = (request['x'], request['y'])
        else:
            return False
        return any(desktop.bounds_contain(box, *point) for box in popups)

    @staticmethod
    def filename_field(node):
        return node.get('role') in ('text', 'entry') and 'editable' in node.get('states', []) \
            and str(node.get('name', '')).rstrip(':').casefold() != 'search'

    def confirm(self):
        observed = self.desk.observe(tree=True)
        by_ref = {n['ref']: n for n in observed.get('nodes', [])}

        def inside(node):
            seen = set()
            while node is not None and node['ref'] not in seen:
                if node.get('role') == 'file chooser':
                    return True
                seen.add(node['ref'])
                node = by_ref.get(node.get('parent'))
            return False
        nodes = [n for n in observed.get('nodes', []) if inside(n)]
        entries = [n for n in nodes if self.filename_field(n)]
        buttons = [n for n in nodes if n.get('role') in ('button', 'push button')
                   and str(n.get('name', '')).casefold() in CHOOSER_PICK]
        if not entries:
            raise ValueError('the file chooser shows no file-name field')
        typed = str(entries[0].get('text') or entries[0].get('value') or '')
        path = self.document_path(typed, where='a file chooser') if typed.strip() else None
        if path is None:
            raise ValueError('type an absolute document path before confirming the file chooser (for example '
                             f'{self.area("outputs")}/name.musicxml; '
                             'Control+L opens the location field of an Open dialog)')
        if path.is_symlink():
            raise ValueError('the chooser destination is a symbolic link')
        # One accessibility request sets, verifies and confirms the checked path: GTK can briefly unpublish a
        # chooser between separate requests.
        self.desk.set_text({'ref': entries[0]['ref']}, str(path),
                           confirm={'ref': buttons[0]['ref']} if buttons else None)
        if not buttons:
            self.desk.act({'op': 'press', 'key': 'Return'})
        return {'confirmed': str(path), 'note': 'refs were renewed; observe again'}

    def forbidden(self):
        return [title for title in self.titles()
                if any(label.casefold() == title.strip().casefold() for label in UNSAFE_DIALOGS)]

    def close_titles(self, titles):
        '''Close windows by title through the window manager: Escape leaves some frames open.'''
        for title in titles:
            try:
                subprocess.run(['wmctrl', '-F', '-c', title], env={**os.environ, **self.session.env()},
                               capture_output=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                continue

    def unsafe(self):
        titles = self.forbidden()
        if not titles:
            return
        deadline = time.monotonic() + 5
        while self.forbidden() and time.monotonic() < deadline:
            self.close_titles(self.forbidden())
            time.sleep(.3)
        names = ' and '.join(sorted({title.strip() for title in titles}))
        raise ValueError(f'the {names} dialog was closed: it holds free folder, file or library fields and is outside '
                         'reference exploration')

    def guard_pointer(self, event):
        """Validate composite pointer actions without sending any input."""
        request = event['pointer']
        op = request['op']
        if self.forbidden():
            raise ValueError('this dialog is not available through the runtime')
        chooser, popups = self.chooser_state()
        if not chooser:
            return
        if popups and op in ('click', 'activate') and request.get('target') is not None \
                and self.format_item(self.desk.resolve(request['target'])):
            return
        if popups and op == 'scroll' and self.over(request, popups):
            return
        if op not in ('click', 'activate'):
            raise ValueError('file chooser navigation is not available')
        node = self.chooser_control(request.get('target'))
        label = str(node.get('name', '')).rstrip('.…').casefold()
        if node.get('role') in ('button', 'push button') and label == 'cancel':
            return
        if node.get('role') in ('combo box', 'menu item') or self.filename_field(node):
            return
        raise ValueError('file chooser navigation is not available')

    def gui(self, op, data):
        request = {key: value for key, value in data.items() if key != 'op'}
        if op in ('type', 'fill'):
            # Typed text is passed through unchanged; a filesystem path in it must stay in the document areas,
            # wherever it is typed (a file chooser or one of the product own text fields).
            value = str(request.get('value', ''))
            if chr(92) in value:
                raise ValueError('typed text does not contain backslashes; document paths use /')
            if path_like(value):
                self.document_path(value, where='a typed document path')
        if op in GUI_GUARDED:
            # A dialog that appeared after the previous operation returned is closed before this one acts.
            self.unsafe()
            chooser, popups = self.chooser_state()
            if not chooser:
                pass
            elif popups and op == 'press' and chord(request.get('key', '')) in POPUP_KEYS \
                    and request.get('target') is None:
                pass
            elif popups and op in ('click', 'activate') and request.get('target') is not None \
                    and self.format_item(self.desk.resolve(request['target'])):
                pass
            elif popups and op == 'scroll' and self.over(request, popups):
                pass
            elif op in ('type', 'fill'):
                if op == 'fill' or request.get('target') is not None:
                    if not self.filename_field(self.chooser_control(request.get('target'))):
                        raise ValueError('text in a file chooser goes into its file-name field')
                if op == 'type' and path_like(str(request.get('value', ''))):
                    # A save dialog pre-fills a name and selects only its stem, so a typed path would keep the old
                    # extension. A path names the whole document: replace the field content.
                    self.desk.act({'op': 'press', 'key': 'Control+a', **({'target': request['target']}
                                                                         if request.get('target') is not None else {})})
            elif op == 'press':
                key = chord(request.get('key', ''))
                if key not in CHOOSER_KEYS or request.get('target') is not None:
                    raise ValueError('keys in a file chooser are limited to Control+A, Control+L, Escape and Return')
                if key in ('return', 'enter'):
                    return self.confirm()
            elif op in ('click', 'activate'):
                node = self.chooser_control(request.get('target'))
                label = str(node.get('name', '')).rstrip('.').casefold()
                if node.get('role') in ('button', 'push button'):
                    if label not in CHOOSER_BUTTONS:
                        raise ValueError('file chooser navigation is not available')
                    if label != 'cancel':
                        return self.confirm()
                elif node.get('role') in ('combo box', 'menu item'):
                    pass
                elif not self.filename_field(node):
                    raise ValueError('file chooser navigation is not available')
            else:
                raise ValueError('file chooser navigation is not available')
        result = self.desk.act({'op': op, **request})
        if op in GUI_GUARDED:
            self.unsafe()
        return result

    # -- dispatch -----------------------------------------------------------------------------------------------
    def notes(self):
        areas = ', '.join(f'{area} {self.area(area)}' for area in AREAS)
        return [f'Document areas: {areas}. Uploads arrive in the input area; the application and convert read and '
                'write them as ordinary files, and files left in the output and project areas can be downloaded.'
                if note == 'DOCUMENT_AREAS' else note for note in NOTES]

    def help(self):
        limits = dict(LIMITS, ready_seconds=self.config.ready_timeout)
        options = [{'options': list(names), 'value': kind, 'summary': summary} for names, kind, summary in OPTIONS]
        return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=limits, notes=self.notes(),
                                     examples=examples(self.area('inputs'), self.area('outputs')),
                                     convert_options=options, upload_suffixes=list(UPLOAD_SUFFIXES),
                                     download_suffixes=list(DOWNLOAD_SUFFIXES),
                                     convert_contract='convert runs start.sh with the given arguments as the '
                                                      'product command line; start.sh without arguments starts the '
                                                      'desktop application.')

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
        if op == 'convert':
            return self.convert(data)
        if op == 'upload':
            return self.upload(data)
        if op == 'list_files':
            return self.list_files()
        if op == 'download':
            return self.download(data)
        if op in ('observe', 'windows', 'screenshot'):
            # A closed-on-sight dialog that opened late is never shown.
            self.unsafe()
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
        return re.sub(r'/[^\s\'"<>()\[\]{},;]*', lambda m: m.group(0) if self.inside(m.group(0))
                      else self.hide(m.group(0)), text)

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
                    code, value = 408, {'error': 'TimeoutError', 'detail': broker.redact(str(exc))[:600]
                                        or 'black-box request deadline exceeded'}
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
    # SIGTERM ends the runtime through the finally
    # block, which stops the product and closes the desktop sessions.
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
