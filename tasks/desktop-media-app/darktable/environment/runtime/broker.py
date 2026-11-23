#!/usr/bin/env python3
'''darktable desktop runtime: command-line export, documents and application lifecycle.

Operations use the running application and its ordinary document interfaces.
'''
from __future__ import annotations

import base64
import http.server
import json
import os
from pathlib import Path
import re
import signal
import socketserver
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import blackbox_desktop as desktop  # noqa: E402
import exchange  # noqa: E402
from documents import Documents

PRODUCT = 'darktable 5.6.2'
SCREEN = (1440, 900)
SETTLE = 0.5
NL = chr(10)
MAX_REQUEST = 11_200_000
MAX_FILE = 8_000_000
RPC_SECONDS = 90
CLI_SECONDS = 75
MAX_IN_FLIGHT = 8
MAX_TEXT = 200_000
MAX_LISTED = 400
# Uploaded documents keep a fixed modification time: the product dates images without
# EXIF data by their file time.
UPLOAD_MTIME = 1704067200
AREAS = ('inputs', 'outputs')
IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.jpe', '.png', '.tif', '.tiff', '.webp', '.exr', '.pfm', '.ppm', '.pgm', '.pnm',
                  '.pbm', '.hdr', '.avif', '.heic', '.heif', '.jxl', '.j2k', '.jp2', '.j2c', '.gif', '.bmp', '.qoi',
                  '.dng', '.cr2', '.cr3', '.nef', '.arw', '.orf', '.rw2', '.raf', '.pef', '.srw')
# Documents: images, sidecars, styles, GPS tracks, tag lists, LUTs and watermarks; no code, plug-in or library.
UPLOAD_SUFFIXES = IMAGE_SUFFIXES + ('.xmp', '.dtstyle', '.gpx', '.txt', '.cube', '.3dl', '.svg', '.icc', '.icm')
DOWNLOAD_SUFFIXES = IMAGE_SUFFIXES + ('.xmp', '.dtstyle', '.gpx', '.txt', '.pdf', '.xcf', '.tex', '.html', '.css',
                                      '.js', '.json', '.csv', '.svg', '.cube', '.3dl', '.icc', '.icm')
NOISE = ('-CRITICAL **', 'Gtk-WARNING', 'Gdk-WARNING', 'GLib-GObject', 'dbus-daemon', 'SpiRegistry', '[styles] importing')
# The product's own command-line options (darktable-cli --help): (names, value kind, summary).
OPTIONS = (
    (('--width',), 'integer', 'Maximum width of the export; 0 = full resolution (default 0).'),
    (('--height',), 'integer', 'Maximum height of the export; 0 = full resolution (default 0).'),
    (('--bpp',), 'integer', 'Unsupported by the product (it prints a notice).'),
    (('--hq',), 'boolean', 'High-quality processing: 0, 1, false or true (default true).'),
    (('--upscale',), 'boolean', 'Allow upscaling to --width/--height: 0, 1, false or true (default false).'),
    (('--export_masks',), 'boolean', 'Export masks: 0, 1, false or true (default false).'),
    (('--style',), 'text', 'Apply this style (name) to the export.'),
    (('--style-overwrite',), 'flag', 'The style replaces the history stack instead of being appended.'),
    (('--apply-custom-presets',), 'boolean', 'Apply custom presets: 0, 1, false or true (default true).'),
    (('--out-ext',), 'extension', 'Output file extension; takes precedence over the output name.'),
    (('--import',), 'document', 'An input image (repeatable) instead of the positional input.'),
    (('--icc-type',), 'text', 'Output ICC profile type (see --help icc-type).'),
    (('--icc-file',), 'document', 'Output ICC profile file (an uploaded document).'),
    (('--icc-intent',), 'text', 'Output rendering intent (see --help icc-intent).'),
    (('--verbose',), 'flag', 'Print the history stack of the first image.'),
    (('-h', '--help'), 'help', 'Print the usage; optionally followed by icc-type or icc-intent.'),
    (('-v', '--version'), 'flag', 'Print the version.'),
    (('--core',), 'core', 'Product core options follow: --conf KEY=VALUE with a key from cli_conf_keys.'),
)
BY_NAME = {name: (names[-1], kind) for names, kind, _ in OPTIONS for name in names}
# Settings a command-line run may override with --core --conf KEY=VALUE.
CONF_KEYS = re.compile(r'plugins/imageio/format/[a-z0-9]+/[a-z_]+|plugins/imageio/storage/disk/overwrite|'
                       r'plugins/darkroom/lut3d/def_path|'
                       r'plugins/lighttable/metadata/(title|description|creator|publisher|rights|notes|version_name)_flag|'
                       r'plugins/lighttable/export/(pixel_interpolator|pixel_interpolator_warp|'
                       r'high_quality_processing|force_lcms2|icctype|iccintent|iccprofile|metadata_flags)|'
                       r'compress_xmp_tags|metadata/resolution|ui/detect_mono_exif|ui_last/ignore_exif_rating')
# Dialogs with unsafe capabilities are handled by field/path guards and launcher confinement.
UNSAFE_DIALOGS = ()
CHOOSER_KEYS = {'ctrl+a', 'ctrl+l', 'escape', 'return', 'enter'}
POPUP_KEYS = {'up', 'down', 'home', 'end', 'page_up', 'page_down', 'pageup', 'pagedown', 'prior', 'next', 'return',
              'enter', 'escape'}
CHOOSER_BUTTONS = ('cancel', 'open', 'save', 'select', 'choose', 'ok', 'replace', 'import', 'export', '_open',
                   '_save', '_select', '_cancel', 'select as destination')
CHOOSER_PICK = ('save', 'open', 'select', 'choose', 'import', 'export', 'select as destination')
# Folder variables of output patterns; they name places inside the document folder.
PATTERN_ROOTS = ('$(FILE_FOLDER)', '$(HOME)', '$(HOME_FOLDER)', '$(PICTURES_FOLDER)', '$(DESKTOP_FOLDER)')


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
    lines = [line for line in text.splitlines() if line.strip() and not any(mark in line for mark in NOISE)]
    return NL.join(lines)[-6000:]


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
                 'summary': 'This description of operations, fields, cli options and limits.'},
        'status': {'kind': 'lifecycle', 'fields': {},
                   'summary': 'Whether the application is running and ready (an accessible window).'},
        'reset': {'kind': 'lifecycle', 'fields': {},
                  'summary': 'Fresh instance: new desktop session, empty configuration and library, and an empty '
                             'document folder; the application is started again.'},
        'restart': {'kind': 'lifecycle', 'fields': {},
                    'summary': 'Quit and relaunch the application with the same configuration, library and '
                               'documents.'},
        'cli': {'kind': 'http',
                'summary': 'Run the product command-line exporter once (start.sh darktable-cli with these arguments, '
                           'no window) on documents of the document folder and return its exit code, standard '
                           'output, a log tail and the files it wrote (refs for download). See cli_options.',
                'fields': {'args': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                    'description': 'darktable-cli arguments, 1 to 40: input images (an uploaded name '
                                                   'or an absolute document path, or a folder of the document '
                                                   'folder), an optional XMP sidecar document, the output (a name in '
                                                   'the output area or an absolute document path; it may hold '
                                                   'variables) and options from cli_options.'}}},
        'upload': {'kind': 'files',
                   'summary': 'Place one document (an image, XMP sidecar, style, GPX track, LUT, ICC profile or text) in the '
                              'input area, replacing a document of the same name; the import dialog and cli accept '
                              'it by name or absolute path.',
                   'fields': {
                       'filename': {'type': 'string', 'required': True,
                                    'description': 'Document name: a basename with one of the suffixes in help.'},
                       'base64': {'type': 'string', 'required': True,
                                  'description': f'File bytes, base64 encoded, at most {MAX_FILE} bytes.'}}},
        'list_files': {'kind': 'files', 'fields': {},
                       'summary': 'Uploaded input names and the pending downloads: files the application or cli '
                                  'wrote or changed anywhere in the document folder since they were last listed '
                                  '(exports, XMP sidecars, styles), each with a ref and its path relative to the '
                                  'document folder.'},
        'documents': {'kind': 'files', 'fields': {},
                      'summary': 'Current regular document files, including inputs and saved sidecars. '
                                 'Returns filename paths relative to the document folder and byte sizes. '
                                 'This is a current inventory, independent of pending downloads.'},
        'read_file': {'kind': 'files',
                      'summary': 'Read the current bytes of a document in the exchange folder, including an '
                                 'unchanged previously downloaded file. Returns body_base64; no private state.',
                      'fields': {'filename': {'type': 'string', 'required': True,
                                              'description': 'A filename from documents, relative to the document folder.'}}},
        'mkdir': {'kind':'files','summary':'Create an empty directory inside the document exchange folder.',
                  'fields':{'directory':{'type':'string','required':True,
                                         'description':'Relative document directory, for example outputs/styles.'}}},
        'download': {'kind': 'files', 'summary': 'Retrieve a pending download once, as body_base64.',
                     'fields': {'ref': {'type': 'string', 'required': True,
                                        'description': 'A ref from list_files or from a cli reply.'}}},
    }
    for op, spec in desktop.operations(SCREEN).items():
        ops[op] = spec
    return runtime.check_operations(ops)


OPERATIONS = specs()
GUI_GUARDED = {op for op, spec in OPERATIONS.items() if spec['kind'] == 'gui'} - {'zoom', 'wait', 'move'}
NOTES = [
    'cli runs the product own command-line exporter (start.sh darktable-cli with the given arguments) on documents '
    'of the document folder; no product behaviour is simulated.',
    'DOCUMENT_AREAS',
    'The application home folder is the document folder: the import dialog lists it as its home place.',
    'File dialogs accept document locations: name a document or folder by '
    'typing its absolute path in the file-name field (Control+L opens the location field) and confirm; navigation '
    'elsewhere is refused and a dialog confirms only inside the document folder.',
    'A typed or filled absolute path, or an export folder pattern, outside the document folder is refused wherever '
    'it is typed.',
    'After an export, a sidecar write or a cli run, list_files shows the new or changed files with refs (a path '
    'relative to the document folder); download retrieves each once.',
    'restart keeps the configuration, library and documents; reset discards them.',
    'The application is a GTK program: its windows, panels, buttons, sliders and text fields are reachable through '
    'accessibility; the image area is visible in screenshots and operated by coordinates.',
]
LIMITS = {'file_bytes': MAX_FILE, 'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_SECONDS,
          'cli_seconds': CLI_SECONDS, 'screen': list(SCREEN), 'ready_seconds': None}


def examples(inputs, outputs):
    '''Request examples for help; the paths name this runtime own document areas.'''
    inputs, outputs = str(inputs), str(outputs)
    return [{'op': 'upload', 'filename': 'photo.jpg', 'base64': '<base64 bytes>'},
            {'op': 'cli', 'args': ['photo.jpg', 'photo.png']},
            {'op': 'cli', 'args': [inputs + '/photo.jpg', inputs + '/photo.jpg.xmp', outputs + '/$(FILE_NAME)_edit.tif',
                                   '--width', '800', '--core', '--conf', 'plugins/imageio/format/tiff/bpp=16']},
            {'op': 'cli', 'args': ['--version']},
            {'op': 'list_files'},
            {'op': 'download', 'ref': 'd1'},
            {'op': 'observe'},
            {'op': 'press', 'key': 'Control+Shift+i'},
            {'op': 'type', 'value': inputs + '/photo.jpg'}]
def directories(state):
    '''The instance layout; the product home folder is the document folder, and the user data folder (GTK
    recent files) is private.'''
    dirs = runtime.layout(state)
    dirs['HOME'] = Path(state) / 'files'
    dirs['XDG_DATA_HOME'] = Path(state) / 'userdata'
    return dirs


class DarktableProduct(runtime.Product):
    '''start.sh with the instance layout plus the owned document areas.'''

    def prepare(self, fresh):
        super().prepare(fresh)
        exchange.prepare(self, AREAS)


class Broker:
    def __init__(self, config):
        self.config = config
        self.state = Path(config.state)
        self.log = runtime.BoundedLog(config.log_dir)
        self.product = DarktableProduct(config, log=self.log, directories=directories(config.state))
        self.session = self.desk = None
        self.downloads, self.seen, self.serial = {}, {}, 0
        self.documents = None
        self.lock = threading.RLock()
        self.hide = runtime.redactor(config.solution, config.state, config.work, config.log_dir,
                                     Path(__file__).resolve().parent, '/app/solution', '/reference')

    # -- lifecycle ----------------------------------------------------------------------------------------------
    @property
    def root(self):
        return self.state / 'files'

    def area(self, name):
        return self.root / name

    def start_session(self):
        if self.session is not None:
            self.session.close()
        if self.desk is not None:
            self.desk.close()
        self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, maximize=True, audio=False,
                                              log_dir=Path(self.config.log_dir) / 'desktop', ).start()
        self.desk = desktop.Desktop(self.session, settle=SETTLE, log_dir=Path(self.config.log_dir) / 'desktop', pointer_guard=self.guard_pointer)

    def start(self, fresh):
        '''Start (fresh: a new desktop session and empty instance) and wait for an accessible window.'''
        self.product.stop()
        if self.documents is not None:
            self.documents.close()
            self.documents = None
        if fresh or self.session is None or not self.session.alive():
            self.start_session()
        if fresh:
            self.downloads.clear()
            self.seen.clear()
        own = set(self.product.directories)
        self.product.extra = {key: value for key, value in self.session.env().items() if key not in own}
        started = self.product.start(fresh)
        self.documents = Documents(self.root, DOWNLOAD_SUFFIXES, MAX_FILE)
        if started:
            runtime.wait_until(self.product, lambda: self.desk.ready(minimum=(400, 300)),
                               failure=f'the application showed no accessible window within '
                                       f'{self.config.ready_timeout:g} s')
        if fresh:
            # Files the first start wrote into the document folder are not downloads.
            self.baseline()
        return self.status()

    def status(self):
        return self.product.status()

    def close(self):
        self.product.stop()
        if self.documents is not None:
            self.documents.close()
        for item in (self.desk, self.session):
            if item is not None:
                item.close()
    # -- documents ----------------------------------------------------------------------------------------------
    def inside(self, value):
        '''Whether an absolute path lies in the document folder (dot segments removed first).'''
        path = os.path.normpath(str(value))
        root = str(self.root)
        return path == root or path.startswith(root + os.sep)

    def document_path(self, value, *, where):
        """Normalize an absolute document path and validate every existing component."""
        text = str(value).strip()
        if (not text.startswith('/') or text.startswith('//') or '://' in text or '\\' in text
                or len(text) > 4000 or any(ord(c) < 32 for c in text)):
            raise ValueError(f'{where} accepts absolute document paths only')
        path = Path(os.path.normpath(text))
        root = Path(os.path.normpath(str(self.root)))
        if not path.is_relative_to(root):
            raise ValueError(f'{where} is confined to the document folder {root}')
        # Check the original path too: normalization must not hide a link before a parent step.
        original = Path(text)
        if any(part.is_symlink() for part in (original, *original.parents)):
            raise ValueError(f'{where} does not follow symbolic links')
        if original.resolve() != path or root.resolve() != root:
            raise ValueError(f'{where} does not resolve to the document folder')
        return path

    def pattern(self, value, *, where):
        '''An output pattern (darktable variables allowed): a name in the output area, an absolute document path,
        or a path that starts with a folder variable (all of them name places in the document folder).'''
        text = str(value)
        if len(text) > 1000 or any(ord(c) < 32 for c in text) or chr(92) in text:
            raise ValueError(f'{where} must be a short pattern without control characters or backslashes')
        segments = re.sub(r'\$\([^)]*\)', 'v', text).split('/')
        if '..' in segments or '~' in text or '://' in text:
            raise ValueError(f'{where} may not leave the document folder (no .., ~ or URLs)')
        if text.startswith('/'):
            # The fixed folder before the first variable must lie in the document folder.
            fixed = text.split('$(', 1)[0]
            self.document_path(fixed if fixed.endswith('/') or '$(' not in text else fixed.rsplit('/', 1)[0] or '/',
                               where=where)
            return text
        if text.startswith(PATTERN_ROOTS):
            return text
        if text.startswith('$('):
            raise ValueError(f'{where} starts with a folder variable from ' + ', '.join(PATTERN_ROOTS)
                             + ', an absolute document path or a plain name')
        return str(self.area('outputs') / text)

    def input_document(self, value):
        if not isinstance(value, str) or not value or len(value) > 4000 or any(ord(c) < 32 for c in value):
            raise ValueError('a document is an uploaded name or an absolute document path')
        if '/' in value:
            path = self.document_path(value, where='a document argument')
        else:
            name = plain_name(value)
            path = next((self.area(a) / name for a in AREAS if (self.area(a) / name).exists()),
                        self.area('inputs') / name)
        return self.document_path(str(path), where='a document argument')
    def option_value(self, kind, value, name):
        if not isinstance(value, str) or len(value) > 4000 or any(ord(c) < 32 for c in value):
            raise ValueError(f'invalid value for {name}')
        if kind == 'document':
            return str(self.input_document(value))
        if kind == 'integer':
            if not re.fullmatch('-?[0-9]{1,6}', value):
                raise ValueError(f'{name} takes a whole number')
            return value
        if kind == 'boolean':
            return value
        if kind == 'extension':
            if '/' in value or len(value) > 10:
                raise ValueError(f'{name} takes a short file extension')
            return value
        if len(value) > 400:
            raise ValueError(f'{name} takes a short text')
        return value

    def core_arguments(self, args):
        '''Product core options after --core: only --conf KEY=VALUE with a key of cli_conf_keys.'''
        argv, index = [], 0
        while index < len(args):
            token = args[index]
            if token != '--conf' or index + 1 >= len(args):
                raise ValueError('after --core only --conf KEY=VALUE pairs are available; see cli_conf_keys')
            key, equals, value = args[index + 1].partition('=')
            if not equals or not CONF_KEYS.fullmatch(key) or len(value) > 400 \
                    or any(ord(c) < 32 for c in value):
                raise ValueError(f'--conf {key[:60]} is not available; see cli_conf_keys in help')
            if key == 'plugins/lighttable/export/iccprofile' and value:
                value = str(self.input_document(value))
            if key == 'plugins/darkroom/lut3d/def_path':
                value = str(self.document_path(value,where='the LUT document folder'))
            argv += ['--conf', f'{key}={value}']
            index += 2
        return argv

    def cli_arguments(self, args):
        if not isinstance(args, list) or not 1 <= len(args) <= 40 or not all(isinstance(a, str) for a in args):
            raise ValueError('args is a list of 1 to 40 strings')
        argv, positional, index = [], [], 0
        while index < len(args):
            token = args[index]
            index += 1
            if len(token) > 4000 or any(ord(c) < 32 for c in token):
                raise ValueError('invalid argument text')
            if not token.startswith('-'):
                positional.append((len(argv), token))
                argv.append(token)
                continue
            spec = BY_NAME.get(token)
            if spec is None:
                raise ValueError(f'option {token[:40]} is not available; see cli_options in help')
            canonical, kind = spec
            if kind == 'core':
                argv += ['--core', *self.core_arguments(args[index:])]
                break
            if kind == 'flag':
                argv.append(token)
                continue
            if kind == 'help':
                argv.append(token)
                if index < len(args) and args[index] in ('icc-type', 'icc-intent'):
                    argv.append(args[index])
                    index += 1
                continue
            if index >= len(args):
                # The product reports a missing value itself (it ignores the option).
                argv.append(token)
                continue
            argv += [token, self.option_value(kind, args[index], token)]
            index += 1
        # Positionals: [input] [XMP] output; the last of two or three is the output pattern.
        if len(positional) > 3:
            raise ValueError('darktable-cli takes at most three positional arguments: input, XMP sidecar, output')
        for number, (slot, token) in enumerate(positional):
            output = len(positional) >= 2 and number == len(positional) - 1 \
                or len(positional) == 1 and '--import' in argv
            argv[slot] = self.pattern(token, where='the output') if output else str(self.input_document(token))
        return argv
    def cli(self, data):
        argv = self.cli_arguments(data['args'])
        script = self.product.solution / 'start.sh'
        if not script.is_file():
            raise ValueError('start.sh does not exist in the solution directory')
        env = self.product.environment()
        kwargs = {}
        if self.product.switching():
            account = self.product.account()
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        proc = subprocess.Popen([str(script), 'darktable-cli', *argv], cwd=str(self.area('outputs')), env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, **kwargs)
        try:
            out, err = proc.communicate(timeout=CLI_SECONDS)
        except subprocess.TimeoutExpired:
            kill(proc)
            raise TimeoutError(f'the product did not finish within {CLI_SECONDS} s') from None
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        return {'exit_code': proc.returncode, 'ok': proc.returncode == 0,
                'stdout': out.decode('utf-8', errors='replace')[:MAX_TEXT],
                'log': quiet(err.decode('utf-8', errors='replace')), 'downloads': self.scan()}

    def upload(self, data):
        filename = plain_name(data['filename'])
        if not filename.casefold().endswith(UPLOAD_SUFFIXES):
            raise ValueError('uploads are image, XMP, style, GPX, LUT or text documents (suffixes '
                             + ' '.join(UPLOAD_SUFFIXES) + ')')
        payload = base64.b64decode(data['base64'], validate=True)
        if len(payload) > MAX_FILE:
            raise ValueError(f'upload exceeds {MAX_FILE} bytes')
        if payload[:4] == bytes([127, 69, 76, 70]) or payload[:2] == b'#!':
            raise ValueError('executable documents cannot be uploaded')
        target = self.area('inputs') / filename
        account = self.product.account()
        runtime.atomic_write(self.documents.fd, 'inputs/' + filename, payload,
                             uid=account.pw_uid, gid=account.pw_gid, mode=0o600)
        with runtime.open_relative(self.documents.fd, 'inputs/' + filename) as fd:
            runtime.set_metadata(fd, ns=(UPLOAD_MTIME * 1_000_000_000, UPLOAD_MTIME * 1_000_000_000))
        # An uploaded document is not a download.
        stat = self.documents.stat('inputs/' + filename)
        self.seen[str(target)] = (stat.st_mtime_ns, stat.st_size)
        return {'uploaded': True, 'filename': filename, 'size': len(payload), 'path': str(target)}

    def files(self):
        '''Regular files of the document folder (no symbolic links), in a stable order.'''
        return [self.root / item['filename'] for item in self.documents.inventory()]

    def baseline(self):
        for path in self.files():
            stat = self.documents.stat(str(path.relative_to(self.root)))
            self.seen[str(path)] = (stat.st_mtime_ns, stat.st_size)

    def register(self, path):
        stat = self.documents.stat(str(path.relative_to(self.root)))
        self.seen[str(path)] = (stat.st_mtime_ns, stat.st_size)
        self.serial += 1
        ref = f'd{self.serial}'
        rel = str(path.relative_to(self.root))
        for old in [r for r, (_rel, known) in self.downloads.items() if known == path]:
            del self.downloads[old]
        self.downloads[ref] = (rel, path)
        return {'ref': ref, 'filename': rel, 'size': stat.st_size}

    def scan(self):
        '''Register files the application or cli wrote or changed anywhere in the document folder.'''
        found = []
        for path in self.files():
            try:
                stat = self.documents.stat(str(path.relative_to(self.root)))
            except (OSError, ValueError):
                continue
            if stat.st_size > MAX_FILE or self.seen.get(str(path)) == (stat.st_mtime_ns, stat.st_size):
                continue
            if len(found) >= MAX_LISTED:
                break
            found.append(self.register(path))
        return found

    def list_files(self):
        self.scan()
        inventory = {x['filename']: x for x in self.documents.inventory()}
        inputs = sorted(n.removeprefix('inputs/') for n in inventory if n.startswith('inputs/') and n.count('/') == 1)
        pending = [{'ref': ref, **inventory[rel]} for ref, (rel, _) in self.downloads.items() if rel in inventory]
        return {'inputs': inputs, 'downloads': pending}

    def download(self, data):
        ref = data['ref']
        if ref not in self.downloads:
            raise ValueError('unknown download reference; use list_files')
        rel, _ = self.downloads.pop(ref)
        return self.documents.read(rel)
    # -- desktop ------------------------------------------------------------------------------------------------
    def typed_path(self, value):
        '''Typed text that names a place on disk must name one in the document folder: an absolute path (up to
        its first variable), a home path or a .. segment are checked wherever the text is typed.'''
        if chr(92) in value:
            raise ValueError('typed text does not contain backslashes; document paths use /')
        segments = re.sub(r'\$\([^)]*\)', 'v', value).split('/')
        if '/' in value and '..' in (s.strip() for s in segments):
            raise ValueError('typed paths may not contain .. segments')
        if path_like(value.strip()):
            fixed = value.strip().split('$(', 1)[0]
            self.document_path(fixed if '$(' not in value else (fixed.rsplit('/', 1)[0] or '/'),
                               where='a typed document path')

    def path_fields(self):
        """Current editable paths, including values assembled through ordinary keys."""
        observed = self.desk.observe(tree=True)
        chooser = any(n.get('role') == 'file chooser' for n in observed.get('nodes', []))
        if chooser:
            return []  # its confirmation has a separate, stricter path check
        fields = []
        for node in observed.get('nodes', []):
            if node.get('role') not in ('text', 'entry') or 'editable' not in node.get('states', []):
                continue
            value = str(node.get('text') or '').strip()
            label = (node.get('name', '') + ' ' + node.get('description', '')).casefold()
            explicit = any(s in label for s in ('enter the path where', 'base directory', 'base_directory',
                                                'directory pattern', 'destination folder', 'output path'))
            if explicit or path_like(value) or value.startswith(PATTERN_ROOTS) or '..' in value.split('/'):
                fields.append((node, value, explicit))
        return fields

    def validate_path_fields(self):
        """Check full field contents before any command can consume them.

        Invalid editable paths are replaced with a safe document location before
        returning an error, so later keyboard submissions cannot reuse them.
        """
        for node, value, explicit in self.path_fields():
            if not value:
                continue
            try:
                self.typed_path(value)
                if explicit or '$(' in value:
                    self.pattern(value, where='the completed path field')
                else:
                    self.document_path(value, where='the completed path field')
            except ValueError:
                try:
                    self.desk.set_text({'ref': node['ref']}, str(self.area('outputs')) + '/')
                except Exception:
                    self.product.stop()
                raise ValueError('the completed path field was outside the document folder and was reset') from None

    def chooser_state(self):
        '''Whether a file chooser is open, and the bounds of its open lists, from a private observation (the
        caller refs stay valid). A combo box list is its own top-level menu in AT-SPI.'''
        nodes = self.desk.inspect().get('nodes', [])
        if not any(n.get('role') == 'file chooser' for n in nodes):
            return False, []
        by_id = {n.get('ref'): n for n in nodes}
        popups = {n.get('parent') for n in nodes if n.get('role') == 'menu item'}
        return True, [by_id[ref]['bounds'] for ref in popups if ref in by_id and by_id[ref].get('role') == 'menu']

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

    def chooser_location(self):
        # GTK's Recent view does not submit a typed folder location. Switch to
        # the application Home (which the runtime sets to the document root)
        # before opening the location field. This is ordinary UI navigation;
        # the resulting path is still checked at every confirmation.
        nodes = self.desk.observe(tree=True).get('nodes', [])
        recent = any(n.get('role') == 'table column header' and n.get('name') == 'Accessed'
                     for n in nodes)
        if recent:
            homes = [n for n in nodes if n.get('role') == 'list item'
                     and n.get('description') == 'Open your personal folder']
            if homes:
                self.desk.act({'op': 'click', 'target': {'ref': homes[0]['ref']}})
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
                   and str(n.get('name', '')).replace('_', '').casefold() in CHOOSER_PICK]
        if not entries:
            raise ValueError('the file chooser shows no file-name field; press Control+L and type an absolute '
                             'document path')
        typed = str(entries[0].get('text') or entries[0].get('value') or '')
        path = self.document_path(typed, where='a file chooser') if typed.strip() else None
        if path is None:
            raise ValueError('type an absolute document path before confirming the file chooser (for example '
                             f'{self.area("inputs")}/photo.jpg; Control+L opens the location field)')
        if path.is_symlink():
            raise ValueError('the chooser destination is a symbolic link')
        # One accessibility request sets, verifies and confirms the checked path: GTK can briefly unpublish a
        # chooser between separate requests.
        self.desk.set_text({'ref': entries[0]['ref']}, str(path))
        if buttons:
            # Some GTK choosers give a preview response to the accessibility
            # default action. Click the validated affirmative button itself.
            if 'disabled' in buttons[0].get('states',[]):
                self.desk.act({'op':'press','key':'Return'})
            else:
                self.desk.act({'op':'click','target':{'role':buttons[0]['role'],'name':buttons[0]['name']}})
        else:
            self.desk.act({'op': 'press', 'key': 'Return'})
        return {'confirmed': str(path), 'note': 'refs were renewed; observe again'}

    def forbidden(self):
        return [title for title in (str(w.get('title', '')) for w in self.desk.windows())
                if any(label.casefold() == title.strip().casefold() for label in UNSAFE_DIALOGS)]

    def unsafe(self):
        titles = self.forbidden()
        if not titles:
            return
        deadline = time.monotonic() + 5
        while self.forbidden() and time.monotonic() < deadline:
            for title in self.forbidden():
                try:
                    subprocess.run(['wmctrl', '-F', '-c', title], env={**os.environ, **self.session.env()},
                                   capture_output=True, timeout=10)
                except (OSError, subprocess.SubprocessError):
                    continue
            time.sleep(.3)
        names = ' and '.join(sorted({title.strip() for title in titles}))
        raise ValueError(f'the {names} dialog was closed: it holds free folder or program fields and is outside '
                         'reference exploration')
    def guard_pointer(self, event):
        """Validate pointer actions, including clicks inside compound operations."""
        request = event['pointer']
        op = request['op']
        # Do not repair fields from this callback: hooks only validate.
        for node, value, explicit in self.path_fields():
            if value:
                self.typed_path(value)
                if explicit or '$(' in value:
                    self.pattern(value, where='the completed path field')
                else:
                    self.document_path(value, where='the completed path field')
        chooser, popups = self.chooser_state()
        if not chooser or op == 'move':
            return
        if popups and op in ('click', 'activate') and request.get('target') is not None \
                and self.desk.resolve(request['target']).get('role') == 'menu item':
            return
        if popups and op == 'scroll' and self.over(request, popups):
            return
        if op not in ('click', 'activate'):
            raise ValueError('file chooser navigation is not available')
        if request.get('target') is not None:
            target = self.desk.resolve(request['target'])
            if target.get('role') == 'list item' and target.get('description') == 'Open your personal folder':
                return
        node = self.chooser_control(request.get('target'))
        label = str(node.get('name', '')).rstrip('.').casefold()
        if node.get('role') in ('button', 'push button'):
            if label not in CHOOSER_BUTTONS:
                raise ValueError('file chooser navigation is not available')
            if label.replace('_', '') != 'cancel':
                nodes = self.desk.inspect().get('nodes', [])
                by_ref = {n['ref']: n for n in nodes}
                def in_chooser(node):
                    seen = set()
                    while node is not None and node['ref'] not in seen:
                        if node.get('role') == 'file chooser':
                            return True
                        seen.add(node['ref'])
                        node = by_ref.get(node.get('parent'))
                    return False
                entries = [n for n in nodes if in_chooser(n) and self.filename_field(n)]
                if not entries:
                    raise ValueError('type a document path before confirming')
                self.document_path(str(entries[0].get('text') or entries[0].get('value') or ''), where='a file chooser')
        elif node.get('role') not in ('combo box', 'menu item', 'check box') and not self.filename_field(node):
            raise ValueError('file chooser navigation is not available')

    def gui(self, op, data):
        request = {key: value for key, value in data.items() if key != 'op'}
        if op in GUI_GUARDED:
            self.validate_path_fields()
        if op in ('type', 'fill'):
            # Typed text is passed through unchanged; a filesystem path in it must stay in the document folder,
            # wherever it is typed (a file chooser, the export folder pattern or another product text field).
            self.typed_path(str(request.get('value', '')))
            # Newlines can submit a path before the post-edit validation.
            if any(c in str(request.get('value', '')) for c in ('\r', '\n')) and self.path_fields():
                raise ValueError('enter path text separately from its confirmation')
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
                    and self.desk.resolve(request['target']).get('role') == 'menu item':
                pass
            elif popups and op == 'scroll' and self.over(request, popups):
                pass
            elif op in ('type', 'fill'):
                if op == 'fill' or request.get('target') is not None:
                    if not self.filename_field(self.chooser_control(request.get('target'))):
                        raise ValueError('text in a file chooser goes into its file-name field')
                if op == 'type' and path_like(str(request.get('value', ''))):
                    # A typed path names the whole document: replace the field content.
                    self.desk.act({'op': 'press', 'key': 'Control+a', **({'target': request['target']}
                                                                         if request.get('target') is not None else {})})
            elif op == 'press':
                key = chord(request.get('key', ''))
                if key not in CHOOSER_KEYS or request.get('target') is not None:
                    raise ValueError('keys in a file chooser are limited to Control+A, Control+L, Escape and Return')
                if key == 'ctrl+l':
                    self.chooser_location()
                if key in ('return', 'enter'):
                    return self.confirm()
            elif op in ('click', 'activate'):
                node = self.chooser_control(request.get('target'))
                label = str(node.get('name', '')).rstrip('.').casefold()
                if node.get('role') in ('button', 'push button'):
                    if label not in CHOOSER_BUTTONS:
                        raise ValueError('file chooser navigation is not available')
                    if label.replace('_', '') != 'cancel':
                        return self.confirm()
                elif node.get('role') in ('combo box', 'menu item', 'check box'):
                    pass
                elif not self.filename_field(node):
                    raise ValueError('file chooser navigation is not available')
            else:
                raise ValueError('file chooser navigation is not available')
        result = self.desk.act({'op': op, **request})
        if op in GUI_GUARDED:
            self.validate_path_fields()
            self.unsafe()
        return result

    # -- dispatch -----------------------------------------------------------------------------------------------
    def notes(self):
        areas = ', '.join(f'{area} {self.area(area)}' for area in AREAS)
        return [f'Document folder {self.root} with the areas {areas}. Uploads arrive in the input area; the '
                'application and cli read and write documents as ordinary files, and files they write or change '
                'anywhere in the document folder can be downloaded.'
                if note == 'DOCUMENT_AREAS' else note for note in NOTES]

    def help(self):
        limits = dict(LIMITS, ready_seconds=self.config.ready_timeout)
        options = [{'options': list(names), 'value': kind, 'summary': summary} for names, kind, summary in OPTIONS]
        return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=limits, notes=self.notes(),
                                     examples=examples(self.area('inputs'), self.area('outputs')),
                                     cli_options=options, cli_conf_keys=CONF_KEYS.pattern,
                                     upload_suffixes=list(UPLOAD_SUFFIXES), download_suffixes=list(DOWNLOAD_SUFFIXES),
                                     cli_contract='cli runs start.sh darktable-cli with the given arguments as the '
                                                  'product command-line exporter, in the output area; start.sh '
                                                  'without arguments starts the desktop application.')

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
        if op == 'cli':
            return self.cli(data)
        if op == 'upload':
            return self.upload(data)
        if op == 'list_files':
            return self.list_files()
        if op == 'documents':
            return {'files': self.documents.inventory()}
        if op == 'read_file':
            return self.documents.read(data['filename'])
        if op == 'mkdir':
            fd=self.documents.mkdir(data['directory'], self.product.account())
            try:
                if self.product.switching():
                    account=self.product.account();os.fchown(fd,account.pw_uid,account.pw_gid)
            finally:os.close(fd)
            return {'directory':data['directory'],'path':str(self.root/data['directory'])}
        if op == 'download':
            return self.download(data)
        if op in ('observe', 'windows', 'screenshot'):
            # A closed-on-sight dialog that opened late is never shown.
            self.unsafe()
        if op == 'observe':
            return self.observe(**{k: v for k, v in data.items() if k != 'op'})
        if op == 'windows':
            return {'windows': self.desk.windows()}
        if op == 'screenshot':
            return self.desk.screenshot(**{k: v for k, v in data.items() if k != 'op'})
        return self.gui(op, data)

    def observe(self, tree=False):
        value=self.desk.observe(tree=tree)
        # Runtime-only scroll offsets, focus and wall-clock timestamps are not
        # document state. Keep geometry and semantic controls for interaction.
        value.pop('focused',None)
        timestamp_rows={n['bounds'][1] for n in value.get('nodes',[]) if n.get('role')=='label'
                        and n.get('name') in ('import timestamp','change timestamp','export timestamp','print timestamp')}
        for node in value.get('nodes',[]):
            if node.get('role')=='scroll bar':node.pop('value',None)
            if 'states' in node:
                node['states']=[s for s in node['states'] if s!='focused']
                if not node['states']:node.pop('states')
            if node.get('role')=='label' and node.get('bounds',[0,0])[1] in timestamp_rows:
                for key in ('name','text','description'):
                    text=node.get(key,'')
                    if re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d\d/',text):node[key]='[event time]'
        return value

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
                             ready_timeout=60.0).parse_args(argv)
    Path(config.work).mkdir(parents=True, exist_ok=True)
    # SIGTERM ends the process through the finally
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
