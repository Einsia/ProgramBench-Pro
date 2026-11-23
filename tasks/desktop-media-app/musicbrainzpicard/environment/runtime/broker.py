#!/usr/bin/env python3
"""MusicBrainz Picard 3.0.3 desktop, command and document exchange runtime.

All application responses come from the running application.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shlex
import signal
import stat
import socketserver
import subprocess
import sys
import threading
import time
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import document_exchange as exchange
import blackbox_desktop as desktop  # noqa: E402

PRODUCT = 'MusicBrainz Picard 3.0.3'
SCREEN = (1440, 900)
SETTLE = 0.5
MAX_REQUEST = 12_000_000
MAX_FILE = 8_000_000
MAX_COMMAND_FILES = 20
MAX_OUTPUT = 200_000
MAX_LISTED = 3000
RPC_SECONDS = 90
MAX_IN_FLIGHT = 8
COMMAND_SECONDS = 30
CLI_SECONDS = 60
QUIT_SECONDS = 20
AREAS = ('inputs', 'outputs')
NAME = re.compile(r'[A-Za-z_]{1,40}')
# Remote commands whose argument names a file or folder: it must lie in the document folders.
PATH_COMMANDS = {'LOAD', 'REMOVE', 'FROM_FILE', 'WRITE_LOGS', 'LOOKUP_CD'}
# Documents the folders exchange: audio and video files the product tags, images, profiles (.toml), sessions
# (.mbps.gz), remote-command files and other plain text, script packages, configuration backups made by the product.
AUDIO_SUFFIXES = ('.mp3', '.mp2', '.m2a', '.flac', '.oga', '.ogg', '.opus', '.spx', '.ogv', '.ogx', '.m4a', '.m4b',
                  '.m4p', '.m4r', '.m4v', '.mp4', '.3g2', '.aac', '.ac3', '.eac3', '.wma', '.wmv', '.asf', '.ape',
                  '.mpc', '.mp+', '.wv', '.ofr', '.ofs', '.tak', '.tta', '.aif', '.aiff', '.aifc', '.wav', '.dsf',
                  '.dff', '.mid', '.kar')
IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.pdf')
TEXT_SUFFIXES = ('.txt', '.toml', '.ptsp', '.pnsp', '.pts', '.yaml', '.yml', '.cue', '.log', '.nfo', '.m3u', '.m3u8')
UPLOAD_SUFFIXES = AUDIO_SUFFIXES + IMAGE_SUFFIXES + TEXT_SUFFIXES + ('.mbps.gz',)
DOWNLOAD_SUFFIXES = UPLOAD_SUFFIXES + ('.ini', '.gz')
CLI_FLAGS = {'--yes', '-y', '--no-color', '--debug', '-h', '--help', '-v', '--version', '-V', '--long-version'}
CLI_SUBCOMMANDS = {'profiles': {'list', 'export', 'import'}, 'completions': None}
# The options of profiles export and import, spelled out in full: option -> whether it takes a value.
CLI_VERB_OPTIONS = {'export': {'-o': True, '--output': True, '--mode': True, '-h': False, '--help': False},
                    'import': {'--enable': False, '--no-enable-tagger-scripts': False, '--replace': True,
                               '-h': False, '--help': False}}
CHOOSER_KEYS = {'return', 'enter', 'kp_enter', 'escape', 'ctrl+a', 'tab', 'shift+tab'}
CHOOSER_ACCEPT = ('open', 'save', 'choose', 'ok', 'select')
# Settings that name an executable: the product starts it as a program. Only the default (empty) is accepted.
EXECUTABLE_SETTINGS = {'acoustid_fpcalc'}
# Settings that name a folder the product reads or writes: they must lie in the document folders.
PATH_SETTINGS = {'move_files_to', 'session_folder_path', 'starting_directory_path', 'autobackup_directory'}
# A text field whose content the product runs as a program as soon as it changes (Options > Fingerprinting).
EXECUTABLE_FIELDS = re.compile(r'fingerprint calculator', re.I)
# The question the product asks before it imports the profile it read from the clipboard (a file import asks the
# same question in a window of another title).
CLIPBOARD_TITLE = re.compile(r'import from clipboard', re.I)
CLIPBOARD_IMPORT = re.compile(r'enable this profile after import', re.I)


def component(value, what):
    if (not isinstance(value, str) or value in ('', '.', '..') or '/' in value or '\\' in value
            or len(value.encode()) > 255 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError(f'{what} must be one name without path separators or control characters')
    return value


def chord(key):
    return '+'.join(part.strip() for part in str(key).casefold().replace('control', 'ctrl').split('+'))


def capped(data):
    text = data.decode('utf-8', errors='replace')
    return text if len(text) <= MAX_OUTPUT else text[:MAX_OUTPUT] + '\n[... output truncated ...]\n'


def operations():
    """Help specs: the shared desktop operations plus this product's channels."""
    ops = {
        'help': {'kind': 'info', 'summary': 'This description of operations, fields, folders and limits.',
                 'fields': {}},
        'status': {'kind': 'lifecycle', 'fields': {},
                   'summary': 'Whether the application is running and ready (an accessible window).'},
        'reset': {'kind': 'lifecycle', 'fields': {},
                  'summary': 'Fresh instance: new desktop session, empty data and empty document folders; the '
                             'application is started again.'},
        'restart': {'kind': 'lifecycle', 'fields': {},
                    'summary': 'Relaunch the application with the same data and document folders (also after it '
                               'quit).'},
        'command': {'kind': 'http',
                    'summary': 'Run the product\'s remote-command line "start.sh -e NAME [ARGUMENT]" for the running '
                               'application (Picard\'s -e option) and wait for that command line to exit; the '
                               'running application executes the command asynchronously. NAME help prints the '
                               'command list. After QUIT the call also waits for the application to exit.',
                    'fields': {
                        'name': {'type': 'string', 'required': True,
                                 'description': 'Command name, for example LOAD, CLUSTER, REMOVE, QUIT or help.'},
                        'argument': {'type': 'string',
                                     'description': 'One argument. Files and folders are absolute paths in the '
                                                    'document folders.'}}},
        'cli': {'kind': 'http',
                'summary': 'Run the product\'s "picard-cli" with these arguments (no terminal, empty standard '
                           'input) and return its exit code, standard output and standard error.',
                'fields': {'args': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                    'description': 'Arguments, for example ["profiles", "list"] or ["--yes", '
                                                   '"profiles", "import", "<inputs>/profile.toml", "--enable"]. '
                                                   'Files are absolute paths in the document folders.'}}},
        'upload': {'kind': 'files',
                   'summary': 'Place one document in the input folder (optionally in a subfolder), replacing a '
                              'document of the same name.',
                   'fields': {
                       'filename': {'type': 'string', 'required': True,
                                    'description': 'Document name: a basename with a supported suffix (audio, '
                                                   'image, .toml, .mbps.gz, .txt and other text documents).'},
                       'folder': {'type': 'string',
                                  'description': 'Optional relative subfolder of the input folder, for example '
                                                 '"Artist/Album" (created as needed).'},
                       'base64': {'type': 'string', 'required': True,
                                  'description': f'File bytes, base64 encoded, at most {MAX_FILE} bytes.'}}},
        'list_files': {'kind': 'files', 'fields': {},
                       'summary': 'The files and folders in the input and output folders (relative paths, sizes, '
                                  'modification times, refs for download).'},
        'download': {'kind': 'files', 'summary': 'Retrieve one listed file as body_base64.',
                     'fields': {'ref': {'type': 'string', 'required': True,
                                        'description': 'A ref from list_files.'}}},
    }
    for op, spec in desktop.operations(SCREEN).items():
        ops[op] = spec
    return runtime.check_operations(ops)


OPERATIONS = operations()
GUI_GUARDED = {op for op, spec in OPERATIONS.items() if spec['kind'] == 'gui'} - {'zoom', 'wait'}
NOTES = [
    'DOCUMENT_FOLDERS',
    'command runs "start.sh -e NAME [ARGUMENT]" with the application\'s own environment; it needs a running '
    'application (status ready). A command line that does not exit within %d s is stopped.' % COMMAND_SECONDS,
    'cli runs "picard-cli" with the application\'s own environment; it does not need a running application. '
    'Allowed: the global options -y/--yes, --no-color, --debug, -h, -v and -V, and the subcommands "profiles" '
    '(list, export, import) and "completions". A run is stopped after %d s.' % CLI_SECONDS,
    'File dialogs are confined to the document folders: type the absolute path of a document or folder in the '
    'dialog\'s file-name field and confirm with Return or the dialog\'s Open/Save/Choose button; other navigation '
    'inside a file dialog is refused.',
    'A typed or filled absolute path outside the document folders is refused wherever it is typed; so are profile, '
    'session and command documents (also a profile imported from the clipboard) that name other places. picard-cli '
    'profiles export and import take their options spelled out in full (-o/--output, --mode, --enable, '
    '--no-enable-tagger-scripts, --replace).',
    'The file browser pane (View > File Browser) shows the whole file system, and the Fingerprinting options page '
    'starts the program its fingerprint calculator field names; both are closed on sight (the Options dialog without '
    'saving), and the request then fails.',
    'Popup context menus (right click) are drawn on the screen but do not appear in observe; use the screenshot '
    'and coordinates or the keyboard to operate them.',
    'restart keeps the data and the document folders; reset discards them.',
]
LIMITS = {'file_bytes': MAX_FILE, 'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_SECONDS,
          'command_seconds': COMMAND_SECONDS, 'cli_seconds': CLI_SECONDS, 'output_characters': MAX_OUTPUT,
          'command_files': MAX_COMMAND_FILES, 'command_document_bytes': MAX_FILE,
          'listed_entries': MAX_LISTED, 'screen': list(SCREEN), 'ready_seconds': None}


def examples(inputs, outputs):
    return [{'op': 'upload', 'filename': 'track.flac', 'folder': 'Artist/Album', 'base64': '<base64 bytes>'},
            {'op': 'command', 'name': 'LOAD', 'argument': f'{inputs}/Artist'},
            {'op': 'command', 'name': 'CLUSTER'},
            {'op': 'command', 'name': 'help'},
            {'op': 'cli', 'args': ['profiles', 'list']},
            {'op': 'cli', 'args': ['--yes', 'profiles', 'export', 'My profile', '-o', f'{outputs}/profile.toml']},
            {'op': 'observe'},
            {'op': 'click', 'target': {'role': 'menu item', 'name': 'File'}},
            {'op': 'press', 'key': 'Control+o'},
            {'op': 'type', 'value': f'{inputs}/Artist/Album/track.flac'},
            {'op': 'press', 'key': 'Return'},
            {'op': 'list_files'}]


class PicardProduct(runtime.Product):
    """start.sh with the instance layout plus the owned document folders."""

    def prepare(self, fresh):
        super().prepare(fresh)
        exchange.prepare(self, AREAS)

        account = self.account()
        with runtime.open_directory(self.directories['HOME']) as home:
            for name in ('Documents', 'Music'):
                with runtime.owned_directory(home, name, uid=account.pw_uid, gid=account.pw_gid):
                    pass


class Broker:
    def __init__(self, config):
        self.config = config
        self.state = Path(config.state)
        self.log = runtime.BoundedLog(config.log_dir)
        self.product = PicardProduct(config, log=self.log)
        self.session = self.desk = None
        self.refs = {}
        self.lock = threading.RLock()
        self.hide = runtime.redactor(config.solution, config.state, config.work, config.log_dir,
                                     Path(__file__).resolve().parent, '/app/solution', '/reference')

    def read_document(self, path, limit=None):
        return exchange.read(self.state / 'files', path, MAX_FILE if limit is None else limit)

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def area(self, name):
        return self.state/'files'/name

    def start_session(self):
        if self.session is not None:
            self.session.close()
        if self.desk is not None:
            self.desk.close()
        self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, maximize=True, audio=True,
                                              log_dir=Path(self.config.log_dir)/'desktop').start()
        self.desk = desktop.Desktop(self.session, settle=SETTLE, log_dir=Path(self.config.log_dir)/'desktop', pointer_guard=self.guard_pointer)

    def start(self, fresh):
        """Start (fresh: a new desktop session and empty instance) and wait for an accessible window."""
        self.product.stop()
        if fresh or self.session is None or not self.session.alive():
            self.start_session()
        if fresh:
            self.refs.clear()
        self.product.extra = {key: value for key, value in self.session.env().items()
                              if key not in ('HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'DATA_DIR')}
        self.product.extra['PBP_DOCUMENTS_ROOT'] = str(self.state / 'files')
        if self.product.start(fresh):
            runtime.wait_until(self.product, lambda: self.desk.ready(minimum=(200, 150)),
                               failure=f'the application showed no accessible window within '
                                       f'{self.config.ready_timeout:g} s')
        return self.status()

    def status(self):
        return self.product.status()

    def close(self):
        self.product.stop()
        if self.desk is not None:
            self.desk.close()
        if self.session is not None:
            self.session.close()

    # -- the product's command lines ----------------------------------------------------------------------------
    def tool(self, argv, timeout):
        """Run one of the solution's programs as the product user, with the application's environment."""
        kwargs = {}
        if self.product.switching():
            account = self.product.account()
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        try:
            proc = subprocess.Popen(argv, cwd=str(self.product.solution), env=self.product.environment(),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True, **kwargs)
        except OSError as exc:
            raise ValueError(f'{Path(argv[0]).name} could not be executed ({exc.strerror or exc})') from None
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()
            raise ValueError(f'{Path(argv[0]).name} did not finish within {timeout:g} s and was stopped') from None
        finally:
            # A command line may leave helpers in its process group; they never outlive the call.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        return {'exit_code': proc.returncode, 'stdout': capped(out), 'stderr': capped(err)}

    def command(self, data):
        name, argument = data['name'], data.get('argument', '')
        if not NAME.fullmatch(name):
            raise ValueError('a command name is letters and underscores')
        if not isinstance(argument, str) or len(argument) > 4096 or any(ord(c) < 32 for c in argument):
            raise ValueError('the argument is one line of text')
        upper = name.upper()
        if upper == 'HELP':
            return self.tool([str(self.product.solution/'start.sh'), '-e', name], COMMAND_SECONDS)
        if upper in PATH_COMMANDS and argument.strip():
            self.command_path(upper, argument.strip())
        if not self.product.running():
            raise ValueError('the application is not running; use restart or reset')
        result = self.tool([str(self.product.solution/'start.sh'), '-e', name, *([argument] if argument else [])],
                           COMMAND_SECONDS)
        if upper == 'QUIT' and result['exit_code'] == 0:
            deadline = time.monotonic()+QUIT_SECONDS
            while self.product.running() and time.monotonic() < deadline:
                time.sleep(.2)
        result['application_running'] = self.product.running()
        return result

    def command_path(self, name, argument, seen=None, budget=None):
        """Validate a remote-command argument that names a file; a command file is validated line by line."""
        if name == 'LOAD' and re.match(r'(?i)(mbid|https?)://', argument):
            return
        text = argument
        if argument[:5].casefold() == 'file:':
            url = urlsplit(argument)
            if url.netloc or url.query or url.fragment:
                raise ValueError('file URLs must name local documents without a query or fragment')
            text = unquote(url.path)
        path = self.document_path(text, where='a command argument')
        if name == 'FROM_FILE':
            self.command_file(path, set() if seen is None else seen, budget)

    def command_file(self, path, seen, budget=None):
        if path in seen:
            return
        if len(seen) >= MAX_COMMAND_FILES:
            raise ValueError(f'command documents reference more than {MAX_COMMAND_FILES} files')
        if budget is None:
            budget = {'bytes': 0}
        seen.add(path)
        try:
            if not path.is_file():
                return
            payload = self.read_document(path, MAX_FILE - budget['bytes'])
        except OSError:
            return
        budget['bytes'] += len(payload)
        if budget['bytes'] > MAX_FILE:
            raise ValueError('command documents exceed the total byte limit')
        lines = payload.decode('utf-8', errors='replace').splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                parts = shlex.split(line)
            except ValueError:
                raise ValueError('a command file line cannot be parsed') from None
            if not parts:
                continue
            for argument in parts[1:]:
                if parts[0].upper() in PATH_COMMANDS and argument.strip():
                    self.command_path(parts[0].upper(), argument.strip(), seen, budget)

    def cli(self, data):
        args = data['args']
        if not isinstance(args, list) or len(args) > 40 or not all(
                isinstance(a, str) and len(a) <= 4096 and not any(ord(c) < 32 for c in a) for a in args):
            raise ValueError('args are at most 40 one-line strings')
        rest = list(args)
        while rest and rest[0].startswith('-'):
            flag = rest.pop(0)
            if flag not in CLI_FLAGS:
                raise ValueError('global option not available: ' + flag[:40])
        if rest:
            command = rest.pop(0)
            if command not in CLI_SUBCOMMANDS:
                raise ValueError('picard-cli subcommand not available: ' + command[:40])
            verbs = CLI_SUBCOMMANDS[command]
            if verbs is not None and rest and not rest[0].startswith('-'):
                if rest[0] not in verbs:
                    raise ValueError(f'{command} command not available: ' + rest[0][:40])
                if rest[0] in ('export', 'import'):
                    self.cli_paths(rest[0], rest[1:])
        return self.tool([str(self.product.solution/'picard-cli'), *args], CLI_SECONDS)

    def cli_paths(self, verb, args):
        """profiles export and import take only the options of CLI_VERB_OPTIONS; the file of an export (-o/--output)
        and of an import (FILE) lies in the document folders."""
        options, positional, index = CLI_VERB_OPTIONS[verb], [], 0
        while index < len(args):
            item = args[index]
            index += 1
            if not item.startswith('-'):
                positional.append(item)
                continue
            name, joined, value = item.partition('=') if item.startswith('--') else (item, '', '')
            if name not in options or (joined and not options[name]):
                raise ValueError(f'profiles {verb} option not available: {item[:40]}')
            if options[name] and not joined:
                if index >= len(args):
                    break  # the product reports the missing value
                value, index = args[index], index+1
            if name in ('-o', '--output'):
                self.document_path(value, where='an output file')
        if verb == 'import':
            for item in positional[:1]:
                path = self.document_path(item, where='a profile file')
                if path.is_file():
                    self.check_profile(self.read_document(path))

    # -- documents ----------------------------------------------------------------------------------------------
    def inside(self, value):
        """Whether an absolute path lies in the document folders (dot segments removed first)."""
        path = os.path.normpath(str(value))
        root = str(self.state/'files')
        return path == root or path.startswith(root+os.sep)

    def document_path(self, value, *, where):
        """Validate text that names a document: an absolute path in the document folders."""
        text = str(value).strip()
        if '\x00' in text or '://' in text or text.startswith('~'):
            raise ValueError(f'{where} accepts absolute document paths only (no URLs or home folders)')
        path = Path(os.path.normpath(text))
        if not path.is_absolute() or not self.inside(path):
            raise ValueError(f'{where} is confined to the document folders: use an absolute path under '
                             f'{self.area("inputs")} or {self.area("outputs")}')
        if any(part.is_symlink() for part in (Path(text), *Path(text).parents)):
            raise ValueError(f'{where} may not traverse symbolic links')
        if not self.inside(path.resolve()):
            raise ValueError(f'{where} resolves outside the document folders')
        return path

    def check_strings(self, value, key=''):
        """Folder settings a document sets lie in the document folders; executable settings stay empty."""
        if isinstance(value, dict):
            for name, item in value.items():
                self.check_strings(item, str(name))
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                self.check_strings(item, key)
            return
        if not isinstance(value, str):
            return
        if key in EXECUTABLE_SETTINGS and value.strip():
            raise ValueError(f'the setting {key} names a program and cannot be set')
        if key in PATH_SETTINGS and value.strip():
            self.document_path(value, where=f'the value of {key}')

    def check_profile(self, payload):
        try:
            import tomli
            data = tomli.loads(payload.decode('utf-8'))
        except Exception:
            return  # the product reports invalid TOML itself
        self.check_strings(data)

    def check_session(self, payload):
        try:
            import yaml
            data = yaml.safe_load(gzip.decompress(payload).decode('utf-8'))
        except Exception:
            return  # the product reports an unreadable session itself
        for item in (data or {}).get('items', []) if isinstance(data, dict) else []:
            if isinstance(item, dict) and isinstance(item.get('file_path'), str):
                self.document_path(item['file_path'], where='a session file path')
        self.check_strings(data.get('options', {}) if isinstance(data, dict) else {})

    def upload(self, data):
        filename = component(data['filename'], 'filename')
        lower = filename.casefold()
        if not lower.endswith(UPLOAD_SUFFIXES):
            raise ValueError('uploads are audio files, images, profiles (.toml), sessions (.mbps.gz) or text '
                             'documents; see help')
        payload = base64.b64decode(data['base64'], validate=True)
        if len(payload) > MAX_FILE:
            raise ValueError(f'upload exceeds {MAX_FILE} bytes')
        if lower.endswith(('.toml', '.ptsp', '.pnsp', '.pts', '.yaml', '.yml')):
            self.check_profile(payload)
        if lower.endswith('.mbps.gz'):
            self.check_session(payload)
        if lower.endswith('.txt'):
            # Remote-command files (FROM_FILE) are validated when they are used; configuration text is refused.
            text = payload.decode('utf-8', errors='replace')
            if re.search(r'(?m)^\s*\[(setting|persist|profiles|application)\]\s*$', text):
                raise ValueError('configuration files cannot be uploaded')
        parts = [component(part, 'folder name') for part in str(data.get('folder') or '').strip('/').split('/') if part]
        if len(parts) > 8:
            raise ValueError('a folder is at most 8 levels deep')
        target = self.area('inputs').joinpath(*parts, filename)
        exchange.write(self.area('inputs'), target, payload, self.product.account())
        return {'uploaded': True, 'path': str(target), 'size': len(payload)}

    def entries(self):
        found = []
        for area in AREAS:
            for relative, info in exchange.entries(self.area(area), limit=MAX_LISTED + 1):
                kind = 'folder' if stat.S_ISDIR(info.st_mode) else 'file'
                ref = 'f' + hashlib.sha256(f'{area}/{relative}'.encode()).hexdigest()[:12]
                found.append((area, relative, kind, self.area(area) / relative, ref, info))
                if len(found) >= MAX_LISTED:
                    return found, True
        return found, False

    def list_files(self):
        found, truncated = self.entries()
        self.refs = {ref: path for _area, _relative, kind, path, ref, _info in found if kind == 'file'}
        listing = {area: [] for area in AREAS}
        for area, relative, kind, path, ref, info in found:
            listing[area].append({'path': relative, 'type': kind,
                                  **({'size': info.st_size, 'mtime': round(info.st_mtime, 3), 'ref': ref}
                                     if kind == 'file' else {})})
        return {**listing, 'truncated': truncated, 'folders': {area: str(self.area(area)) for area in AREAS}}

    def download(self, data):
        ref = data['ref']
        path = self.refs.get(ref)
        if path is None:
            found, _ = self.entries()
            path = next((p for _a, _r, kind, p, r, _i in found if r == ref and kind == 'file'), None)
        if path is None:
            raise ValueError('unknown download reference; use list_files')
        if not path.name.casefold().endswith(DOWNLOAD_SUFFIXES):
            raise ValueError('this file type is not downloadable')
        payload = self.read_document(path)
        return {'path': str(path), 'size': len(payload), 'body_base64': base64.b64encode(payload).decode()}

    # -- desktop guards -------------------------------------------------------------------------------------------
    @staticmethod
    def tree_of(nodes):
        by_ref = {n['ref']: n for n in nodes}
        children = {}
        for n in nodes:
            children.setdefault(n.get('parent'), []).append(n)
        return by_ref, children

    @staticmethod
    def descendants(children, ref):
        stack, seen = [ref], []
        while stack:
            for child in children.get(stack.pop(), []):
                seen.append(child)
                stack.append(child['ref'])
        return seen

    def choosers(self, nodes):
        """Open file dialogs: GTK file choosers and Qt file dialogs (a dialog with a "Look in" folder list and a
        file-name field)."""
        _by_ref, children = self.tree_of(nodes)
        found = {}
        for node in nodes:
            if node['role'] == 'file chooser':
                found[node['ref']] = node
            elif node['role'] in ('dialog', 'window', 'frame') and node.get('parent') is None:
                inner = self.descendants(children, node['ref'])
                names = {(n['role'], str(n.get('name', '')).rstrip(':').casefold()) for n in inner}
                if ('label', 'look in') in names or ('list', 'sidebar') in names:
                    found[node['ref']] = node
        return found

    def inspect(self):
        return self.desk.inspect().get('nodes', [])

    @staticmethod
    def filename_field(node):
        return node.get('role') in ('text', 'entry') and 'editable' in node.get('states', []) \
            and str(node.get('name', '')).rstrip(':').casefold() not in ('search', 'look in')

    def chooser_parts(self, nodes, window):
        _by_ref, children = self.tree_of(nodes)
        inner = self.descendants(children, window['ref'])
        fields = [n for n in inner if self.filename_field(n)]
        named = [f for f in fields if str(f.get('name', '')).rstrip(':').casefold() in ('file name', 'directory',
                                                                                        'name', 'folder')]
        buttons = [n for n in inner if n['role'] in ('push button', 'button')]
        return named or fields, buttons

    def confirm(self, chooser):
        """Check the typed path of the open file dialog, then set it and press the dialog's accept button in one
        accessibility request (the public refs are renewed)."""
        nodes = self.desk.observe(tree=True).get('nodes', [])
        window = next((n for n in nodes if n.get('parent') is None and n['role'] == chooser['role']
                       and n.get('name') == chooser.get('name')), None)
        if window is None:
            raise ValueError('the file dialog closed')
        fields, buttons = self.chooser_parts(nodes, window)
        if not fields:
            raise ValueError('the file dialog shows no file-name field')
        typed = str(fields[0].get('text') or '').strip()
        if not typed:
            raise ValueError('type an absolute document path in the file-name field before confirming (for '
                             f'example {self.area("inputs")}/track.flac)')
        path = self.document_path(typed, where='a file dialog')
        if path.is_symlink():
            raise ValueError('the chosen path is a symbolic link')
        title = str(window.get('name', ''))
        if 'configuration' in title.casefold() and path.suffix.casefold() != '.ini' and not path.is_dir():
            raise ValueError('configuration backups are .ini files the application saved')
        accept = [b for b in buttons if str(b.get('name', '')).rstrip('.…').casefold() in CHOOSER_ACCEPT]
        self.desk.set_text({'ref': fields[0]['ref']}, str(path),
                           confirm={'ref': accept[0]['ref']} if accept else None)
        if not accept:
            self.desk.act({'op': 'press', 'key': 'Return'})
        return {'confirmed': str(path), 'note': 'refs were renewed; observe again'}

    def file_browser(self, nodes):
        """The file browser pane: a tree that lists the file-system root."""
        _by_ref, children = self.tree_of(nodes)
        for node in nodes:
            if node['role'] in ('tree', 'tree table', 'table'):
                cells = {str(c.get('name', '')) for c in self.descendants(children, node['ref'])
                         if c['role'] in ('table cell', 'tree item', 'list item')}
                if {'/', 'etc', 'usr'} <= cells or {'/', 'proc', 'tmp'} <= cells:
                    return node
        return None

    def close_file_browser(self):
        """Hide the file browser pane through its View menu toggle, then fail the request."""
        for _ in range(3):
            if self.file_browser(self.inspect()) is None:
                break
            try:
                self.desk.act({'op': 'press', 'key': 'Escape'})
                self.desk.act({'op': 'click', 'target': {'role': 'menu item', 'name': 'View'}})
                self.desk.act({'op': 'click', 'target': {'role': 'menu item', 'name': 'File Browser'}})
            except desktop.DesktopError:
                pass
        raise ValueError('the file browser pane shows the whole file system and was closed; open documents '
                         'through file dialogs and the document folders')

    def fingerprinting_page(self, nodes):
        """The Fingerprinting options page is showing: its fingerprint calculator field (the controls of hidden
        pages are not in the tree)."""
        return next((n for n in nodes if n['role'] in ('text', 'entry')
                     and EXECUTABLE_FIELDS.search(str(n.get('name', '')))), None)

    def close_options(self, nodes, reason):
        """Leave the Options dialog on its first page and close it without saving, then fail the request."""
        for _ in range(3):
            if self.fingerprinting_page(nodes) is None:
                break
            try:
                self.desk.act({'op': 'click', 'target': {'role': 'table cell', 'name': 'General'}})
                self.desk.act({'op': 'click', 'target': {'role': 'push button', 'name': 'Cancel'}})
            except desktop.DesktopError:
                try:
                    self.desk.act({'op': 'press', 'key': 'Escape'})
                except desktop.DesktopError:
                    pass
            nodes = self.inspect()
        raise ValueError(reason)

    def clipboard_import(self, nodes):
        """The product asks whether to enable the profile it read from the clipboard: the profile must not name
        folders outside the document folders or a program. When it does (or the clipboard cannot be read), the
        application is restarted before the profile is imported."""
        _by_ref, children = self.tree_of(nodes)
        if not any(node.get('parent') is None and CLIPBOARD_TITLE.search(str(node.get('name', '')))
                   and any(CLIPBOARD_IMPORT.search(str(n.get('name', ''))+' '+str(n.get('text', '')))
                           for n in [node, *self.descendants(children, node['ref'])]) for node in nodes):
            return
        try:
            import tomli
            self.check_strings(tomli.loads(self.desk.clipboard('UTF8_STRING', 1_000_000).decode('utf-8')))
            return
        except Exception as exc:  # noqa: BLE001 - any doubt stops the import
            self.log.note(f'clipboard profile refused: {type(exc).__name__}: {exc}')
            problem = str(exc) if type(exc) is ValueError else 'the clipboard could not be checked'
        # Killed at once: a product asked to quit would answer its question and import the profile first.
        try:
            os.killpg(self.product.proc.pid, signal.SIGKILL)
        except (AttributeError, ProcessLookupError, PermissionError):
            pass
        self.start(False)
        raise ValueError(f'a profile from the clipboard was not imported ({problem}); the application was restarted '
                         'with its saved settings')

    def guard(self, nodes):
        """Places of the interface that reach outside the document folders."""
        if self.fingerprinting_page(nodes) is not None:
            self.close_options(nodes, 'the Fingerprinting options page starts the program its fingerprint calculator '
                                      'field names and was closed without saving the options')
        self.clipboard_import(nodes)

    def guard_pointer(self, event):
        """Check every pointer target, including implicit clicks and drag destinations."""
        request = event['pointer']
        nodes = self.inspect()
        points = [request]
        if request['op'] == 'drag':
            points += [{'target': request['to_target']}] if request.get('to_target') is not None else [
                {'x': request.get('to_x'), 'y': request.get('to_y')}]
            points += [{'x': x, 'y': y} for x, y in request.get('via', [])]
        for point in points:
            node = self.desk.resolve(point['target']) if point.get('target') is not None else (
                desktop.node_at({'nodes': nodes}, point['x'], point['y'])
                if point.get('x') is not None and point.get('y') is not None else None)
            if node is None:
                continue
            label = str(node.get('name', '')).replace('&', '').strip().rstrip('.…').casefold()
            if EXECUTABLE_FIELDS.search(label) or any(term in label for term in (
                    'open in system media player', 'open containing folder', 'lookup in browser')):
                raise ValueError('external application controls are not available')
        if not self.choosers(nodes) or request['op'] == 'move':
            return
        if request['op'] not in ('click', 'activate') or request.get('target') is None:
            raise ValueError('file dialog navigation is not available')
        node = self.desk.resolve(request['target'])
        label = str(node.get('name', '')).rstrip('.…').casefold()
        if self.filename_field(node) or node['role'] in ('button', 'push button') and label == 'cancel':
            return
        raise ValueError('confirm file dialogs through their checked document path')

    def gui(self, op, data):
        request = {key: value for key, value in data.items() if key != 'op'}
        if op in ('type', 'fill'):
            single = str(request.get('value', '')).strip()
            if '\n' not in single and single.startswith(('/', '~')):
                self.document_path(single, where='a typed path')
            if '\n' not in single and single[:5].casefold() == 'file:':
                # A file URL (for example in the cover art URL dialog) names a path as well.
                from urllib.parse import unquote, urlparse
                self.document_path(unquote(urlparse(single).path) or '/', where='a typed file URL')
            if '\n' not in single and '/' in single and '..' in Path(single).parts:
                raise ValueError('typed paths name places inside the document folders without ".." segments')
        if op not in GUI_GUARDED:
            return self.desk.act({'op': op, **request})
        nodes = self.inspect()
        self.guard(nodes)
        target = request.get('target')
        record = None
        if target is not None:
            try:
                record = self.desk.resolve(target)
            except desktop.DesktopError:
                record = None
        if op in ('type', 'fill', 'press'):
            focused = record or next((n for n in nodes if 'focused' in n.get('states', [])
                                      and n['role'] in ('text', 'entry', 'combo box')), None)
            if focused is not None and EXECUTABLE_FIELDS.search(str(focused.get('name', ''))) and \
                    (op != 'press' or chord(request.get('key', '')) not in ('tab', 'shift+tab', 'escape')):
                raise ValueError('the fingerprint calculator field names a program and cannot be edited')
        choosers = self.choosers(nodes)
        if choosers and op != 'move':
            chooser = next(iter(choosers.values()))
            if op in ('type', 'fill'):
                if record is not None and not self.filename_field(record):
                    raise ValueError('text in a file dialog goes into its file-name field')
                value = str(request.get('value', '')).strip()
                if value:
                    self.document_path(value, where='a file dialog')
                if op == 'type':
                    # A save dialog pre-fills a name: a typed path names the whole document.
                    self.desk.act({'op': 'press', 'key': 'Control+a', **({'target': target} if target else {})})
                    request.pop('target', None)
            elif op == 'press':
                key = chord(request.get('key', ''))
                if key not in CHOOSER_KEYS or (record is not None and not self.filename_field(record)):
                    raise ValueError('keys in a file dialog are limited to Return, Escape, Tab and Control+A')
                if key in ('return', 'enter', 'kp_enter'):
                    return self.confirm(chooser)
            elif op in ('click', 'activate'):
                if record is None:
                    raise ValueError('coordinate input is not available in a file dialog; target its controls')
                label = str(record.get('name', '')).rstrip('.…').casefold()
                if record['role'] in ('push button', 'button'):
                    if label in CHOOSER_ACCEPT:
                        return self.confirm(chooser)
                    if label != 'cancel':
                        raise ValueError('file dialog navigation is not available')
                elif not self.filename_field(record):
                    raise ValueError('file dialog navigation is not available')
            else:
                raise ValueError('file dialog navigation is not available')
        result = self.desk.act({'op': op, **request})
        if op != 'move':
            after = self.inspect()
            if self.file_browser(after) is not None:
                self.close_file_browser()
            self.guard(after)
        return result

    # -- dispatch -----------------------------------------------------------------------------------------------
    def notes(self):
        folders = ', '.join(f'{area} {self.area(area)}' for area in AREAS)
        return [f'Document folders: {folders}. Uploads arrive in the input folder; the application reads, saves, '
                'renames and moves files there and in the output folder, and every file in both folders can be '
                'listed and downloaded.' if note == 'DOCUMENT_FOLDERS' else note for note in NOTES]

    def help(self):
        limits = dict(LIMITS, ready_seconds=self.config.ready_timeout)
        return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=limits, notes=self.notes(),
                                     examples=examples(self.area('inputs'), self.area('outputs')),
                                     document_folders={area: str(self.area(area)) for area in AREAS},
                                     upload_suffixes=list(UPLOAD_SUFFIXES))

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
        if op == 'command':
            return self.command(data)
        if op == 'cli':
            return self.cli(data)
        if op == 'upload':
            return self.upload(data)
        if op == 'list_files':
            return self.list_files()
        if op == 'download':
            return self.download(data)
        if op == 'observe':
            return self.desk.observe(**{k: v for k, v in data.items() if k != 'op'})
        if op == 'windows':
            return {'windows': self.desk.windows()}
        if op == 'screenshot':
            return self.desk.screenshot(**{k: v for k, v in data.items() if k != 'op'})
        return self.gui(op, data)

    def redact(self, text):
        """Text with private filesystem locations replaced; document paths stay readable (they are public)."""
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
        server.audit.record(op, code, time.monotonic()-started)
        self.reply(code, value)


def main(argv=None):
    config = runtime.options(state='/reference/state', log_dir='/reference', work='/reference/work',
                             ready_timeout=30.0).parse_args(argv)
    Path(config.work).mkdir(parents=True, exist_ok=True)
    # SIGTERM ends the runtime through the finally
    # block, which stops the product and closes the desktop session.
    runtime.exit_on_sigterm()
    broker = Broker(config)
    server = None
    try:
        # A product that fails to start is reported by status; the runtime keeps serving.
        broker.start(True)
        server = Server(runtime.listen(config.socket, config.socket_mode), broker)
        server.audit = runtime.Audit(Path(config.log_dir)/'rpc-audit.jsonl')
        server.serve_forever()
    finally:
        broker.close()
        if server is not None:
            server.server_close()


if __name__ == '__main__':
    main()
