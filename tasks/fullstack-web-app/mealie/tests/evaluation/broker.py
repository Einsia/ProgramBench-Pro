"""The task's black-box runtime seen from the verifier.

BrokerClient speaks the runtime's RPC; BrokerRuntime launches one runtime for
one episode (as root, driving the workspace's copy of the candidate as the
candidate user); BrokerSurface is the evaluator's interface: exactly the GUI
operations the runtime offers the model on the reference, with the runtime's
own observation formats. Setup and program checks use the client's other
channels (api/http, download, restart, reset, status, ...).
"""
import base64
import http.client
import json
import mimetypes
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from .contract import InfrastructureError, ObservationUnavailable

ENV_ALLOW = ('PATH', 'LANG', 'LC_ALL', 'TZ', 'NODE_PATH', 'PLAYWRIGHT_BROWSERS_PATH')
MIME = {'.excalidraw': 'application/json', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.pdf': 'application/pdf',
        '.txt': 'text/plain', '.csv': 'text/csv', '.wav': 'audio/wav', '.mp3': 'audio/mpeg'}


class BrokerError(RuntimeError):
    """The runtime rejected or failed one request; product behaviour, not a verifier fault."""

    def __init__(self, status, error, detail):
        super().__init__(f'{error}: {detail}')
        self.status, self.error, self.detail = status, error, str(detail or '')

    @property
    def timeout(self):
        return self.status == 408


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class BrokerClient:
    def __init__(self, socket_path, *, timeout=120):
        self.path, self.timeout, self.calls = str(socket_path), timeout, 0

    def call(self, request, *, timeout=None):
        self.calls += 1
        wait = timeout or self.timeout
        connection = UnixConnection(self.path, wait)
        try:
            connection.request('POST', '/rpc', json.dumps(request).encode(), {'Content-Type': 'application/json'})
            response = connection.getresponse()
            body, status = response.read(), response.status
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise InfrastructureError('black-box runtime is not reachable (' + type(exc).__name__ + ')') from None
        except socket.timeout:
            raise BrokerError(408, 'ClientTimeout', f'the runtime did not answer within {wait:g} s') from None
        except (OSError, http.client.HTTPException) as exc:
            raise InfrastructureError('black-box runtime connection failed (' + type(exc).__name__ + ')') from None
        finally:
            connection.close()
        try:
            value = json.loads(body)
        except ValueError:
            raise InfrastructureError(f'black-box runtime returned invalid JSON (HTTP {status})') from None
        if status != 200:
            value = value if isinstance(value, dict) else {}
            raise BrokerError(status, value.get('error', 'Error'), value.get('detail', ''))
        return value


class BrokerRuntime:
    """One task runtime for one episode. It stays in the worker's process group, so the scheduler's
    signals reach it; the product runs in its own session as the candidate user."""

    def __init__(self, task, workspace, logs, *, solution, instance, user):
        self.task, self.workspace, self.logs = task, Path(workspace), Path(logs)
        self.solution, self.instance, self.user = Path(solution), Path(instance), user
        self.socket = self.workspace / 'runtime' / 'broker.sock'
        self.client = BrokerClient(self.socket)
        self.proc = None

    def command(self):
        work = self.workspace / 'runtime' / 'work'
        command = list(self.task.RUNTIME_COMMAND)
        # Isolated Python ignores PYTHONDONTWRITEBYTECODE; keep the installed
        # runtime tree unchanged through an explicit interpreter option.
        if Path(command[0]).name.startswith('python') and '-B' not in command:
            command.insert(1, '-B')
        return [*command, '--solution', str(self.solution), '--state', str(self.instance),
                '--socket', str(self.socket), '--socket-mode', '0600', '--log-dir', str(self.logs),
                '--user', self.user, '--work', str(work), *getattr(self.task, 'RUNTIME_ARGS', ())]

    def start(self, timeout):
        self.logs.mkdir(parents=True, exist_ok=True)
        private = self.workspace / 'runtime'
        for name in ('home', 'tmp'):
            (private / name).mkdir(parents=True, exist_ok=True)
        env = {k: os.environ[k] for k in ENV_ALLOW if k in os.environ}
        env.update(HOME=str(private / 'home'), TMPDIR=str(private / 'tmp'), PYTHONDONTWRITEBYTECODE='1',
                   BLACKBOX_DESKTOP_ROOT=str(self.workspace / 'desktop'))
        with (self.logs / 'runtime.log').open('ab') as log:
            self.proc = subprocess.Popen(self.command(), env=env, stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise InfrastructureError(f'black-box runtime exited with status {self.proc.returncode}; see runtime.log')
            if self.socket.exists():
                try:
                    return self.client.call({'op': 'status'}, timeout=30)
                except (InfrastructureError, BrokerError):
                    pass
            time.sleep(.2)
        raise InfrastructureError(f'black-box runtime did not come up within {timeout:g} s')

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.proc is None or self.proc.poll() is not None:
            return
        self.proc.send_signal(signal.SIGTERM)
        try:
            self.proc.wait(20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(10)


GUIDES = {
    'browser': '''Interface: the application's pages in a browser (Chromium, 1280x900 viewport),
operated through its black-box interface. Each observation is the interface's
page snapshot (visible text; controls with refs, labels, values, states and
bounds [x,y,w,h] in viewport pixels; pending downloads and file chooser) plus a
viewport screenshot. Target controls with a ref from the latest observation, or
by role (with name), label, placeholder or visible text. pointer, drag and wheel
take viewport coordinates from the screenshot, or coordinates inside a target's
box when a target is given. press and type without a target act on the focused
element. Content drawn on a canvas is visible only in the screenshot. To supply
a file, use the product's file control and answer the file chooser with upload
and one of the listed inputs. Trust executed inputs instead of repeatedly
re-checking them. Do not call APIs or open developer tools.
''',
    'desktop': '''Interface: the application's windows on a Linux desktop, operated through its
black-box interface. Each observation is the interface's accessibility snapshot
(screen size, the application's windows, and visible controls with refs, roles,
names, descriptions, values, states and bounds [x,y,w,h] in screen pixels) plus
a full-screen screenshot. Target controls with a ref from the latest
observation, or act at screenshot coordinates; controls without accessible data
are still operable by coordinates. Use menus, dialogs, keyboard shortcuts and
file choosers as a user would. activate invokes a control's default accessible
action. scroll turns the mouse wheel at a point (positive delta_y scrolls down,
100 per notch). To read small text or hit small controls precisely, zoom into a
screen rectangle: the next observation image shows only that region, magnified
(its image entry says so), while every operation keeps full-screen coordinates.
Trust executed inputs instead of repeatedly re-checking them. Do not use
terminals, other applications or private files.
''',
    'terminal': '''Interface: the application in a terminal, operated through its black-box
interface. Each observation is the interface's screen snapshot. Operate it with
keys, chords and literal text as a keyboard user would. Trust executed inputs
instead of repeatedly re-checking them. Do not run shell commands or other programs.
''',
}
NOT_GUI = ('filename', 'mime_type', 'base64')


def field_schema(field):
    schema = {k: field[k] for k in ('type', 'enum', 'items') if k in field}
    if isinstance(schema.get('type'), list):
        schema = {'anyOf': [{'type': t} for t in schema['type']], **{k: v for k, v in schema.items() if k != 'type'}}
    return schema


def merged_field_schema(fields):
    """Union the legal types/enums of a shared field across all its operations.

    One unrestricted enum permits all values. Conflicting or missing item
    schemas remove the item restriction; the runtime still validates each
    selected operation against its own complete specification.
    """
    kinds = []
    for field in fields:
        value = field.get('type', [])
        for kind in value if isinstance(value, list) else [value]:
            if kind not in kinds:
                kinds.append(kind)
    merged = {'type': kinds[0] if len(kinds) == 1 else kinds}
    if all('enum' in field for field in fields):
        values = {}
        for field in fields:
            for value in field['enum']:
                values.setdefault(json.dumps(value, sort_keys=True), value)
        merged['enum'] = list(values.values())
    items = fields[0].get('items')
    if items is not None and all(field.get('items') == items for field in fields):
        merged['items'] = items
    return field_schema(merged)


def tool(surface, specs, hidden=(), upload=False):
    """The evaluator's single tool, derived from the runtime's machine-readable help."""
    properties, uses, descriptions, fields_by_name = {}, {}, {}, {}
    for op, spec in specs.items():
        for name, field in spec.get('fields', {}).items():
            if name in hidden or (upload and op == 'upload' and name in NOT_GUI):
                continue
            fields_by_name.setdefault(name, []).append(field)
            descriptions.setdefault(name, field['description'])
            uses.setdefault(name, []).append(op + ('*' if field.get('required') else ''))
    properties = {name: merged_field_schema(fields) for name, fields in fields_by_name.items()}
    if upload:
        properties['file'] = {'type': 'string'}
        descriptions['file'] = 'Name of one file from the inputs listed in the observation.'
        uses['file'] = ['upload*']
    for name in properties:
        properties[name]['description'] = f'{descriptions[name]} [{", ".join(uses[name])}]'
    properties = {'op': {'type': 'string', 'enum': list(specs),
                         'description': ' '.join(f'{op}: {spec["summary"]}' for op, spec in specs.items())},
                  **properties}
    return {'type': 'function', 'function': {
        'name': surface,
        'description': "One operation of the application's black-box interface (fields marked * are required "
                       'for that operation). A fresh observation follows every operation.',
        'parameters': {'type': 'object', 'additionalProperties': False, 'properties': properties, 'required': ['op']}}}


class BrokerSurface:
    """Evaluator surface: the task-whitelisted GUI operations of the runtime and its own observations."""

    def __init__(self, client, task, directory, *, inputs=None):
        self.client, self.task, self.directory = client, task, Path(directory)
        self.inputs = Path(inputs) if inputs else None
        self.session = dict(getattr(task, 'SESSION', {}) or {})
        operations = client.call({'op': 'help'}).get('operations', {})
        wrong = [op for op in task.GUI_OPS if operations.get(op, {}).get('kind') != 'gui']
        if wrong:
            raise InfrastructureError('runtime help does not describe GUI operations: ' + ', '.join(wrong))
        self.ops = tuple(task.GUI_OPS)
        self.upload = 'upload' in self.ops and {'filename', 'base64'} <= set(operations['upload'].get('fields', {}))
        self.TOOL = tool(task.SURFACE, {op: operations[op] for op in self.ops}, set(self.session), self.upload)
        self.GUIDE = GUIDES[task.SURFACE] + getattr(task, 'GUIDE_NOTES', '')
        self.observe_op, self.image_op = task.OBSERVE
        self.timeouts = 0
        self.directory.mkdir(parents=True, exist_ok=True)

    def files(self):
        return sorted(p.name for p in self.inputs.iterdir() if p.is_file()) if self.inputs and self.inputs.is_dir() else []

    def observe(self):
        try:
            obs = self.client.call({'op': self.observe_op, **self.session})
            png = None
            if self.image_op:
                png = base64.b64decode(self.client.call({'op': self.image_op, **self.session})['png_base64'])
        except BrokerError as exc:
            raise ObservationUnavailable('the interface could not be observed: ' + exc.detail[:300]) from None
        files = self.files()
        if files and isinstance(obs, dict):
            obs = dict(obs, inputs=files)
        return obs, png

    def action(self, a):
        if not isinstance(a, dict) or a.get('op') not in self.ops:
            raise ValueError('unknown operation; use one of ' + ', '.join(self.ops))
        request = dict(a)
        if self.upload and request['op'] == 'upload':
            name = request.pop('file', None)
            if not isinstance(name, str) or name not in self.files():
                raise ValueError('upload names one file listed in inputs')
            data = (self.inputs / name).read_bytes()
            request.update(filename=name, base64=base64.b64encode(data).decode(),
                           mime_type=MIME.get(Path(name).suffix.lower()) or mimetypes.guess_type(name)[0]
                           or 'application/octet-stream')
        if set(request) & set(self.session):
            raise ValueError('the session is fixed')
        request.update(self.session)
        try:
            self.client.call(request)
        except BrokerError as exc:
            if not exc.timeout:
                self.timeouts = 0
                return {'status': 'error', 'reason': exc.detail[:600]}
            self.timeouts += 1
            if self.timeouts >= 2:
                raise ObservationUnavailable('the application stopped responding to input') from None
            return {'status': 'uncertain', 'reason': 'The operation timed out. Inspect the next observation before repeating it.'}
        self.timeouts = 0
        with (self.directory / 'actions.jsonl').open('a') as f:
            f.write(json.dumps(a, ensure_ascii=False) + '\n')
        return {'status': 'executed'}
