"""Verifier-side harness: the candidate's command lines, documents and desktop through the black-box runtime.

Program episodes (remote commands, picard-cli, sessions), public setup and the independent checks of GUI
checkpoints reach the candidate only through the task's runtime: command (start.sh -e), cli (picard-cli), upload,
list_files and download (the document folders), observe (the accessible desktop), reset and restart. These are the
channels the model has on the reference. Nothing in this module is shown to the evaluator agent or the candidate.
"""
import base64
import dataclasses
import gzip
import json
from pathlib import Path
import re
import time

from evaluation.broker import BrokerError
from evaluation.contract import InfrastructureError

# Seconds a product file may take to appear after the command or dialog that wrote it.
FILE_SECONDS = 15
SESSION_NAME = 'autosave.mbps.gz'
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
DATE = re.compile(r'\b20\d\d-\d\d-\d\d\b')


class MissingDependency(AssertionError):
    """A required earlier operation of the same scenario did not complete."""


@dataclasses.dataclass
class Case:
    id: str
    family: str
    scenario: str
    channel: str
    description: str
    action: object
    needs: object = None
    requires: tuple = ()


class Suite:
    """Ordered program operations; setup rows prepare, scored rows are program assertions."""

    def __init__(self):
        self.cases = []
        self.ids = set()

    def add(self, family, scenario, step, action, channel='backend', description='', needs=None, requires=()):
        identifier = f'{channel}.{family}.{scenario}.{step}'
        if identifier in self.ids:
            raise ValueError('duplicate case '+identifier)
        self.ids.add(identifier)
        self.cases.append(Case(identifier, family, scenario, channel, description or step, action, needs,
                               tuple(requires)))
        return identifier


class Context:
    """State shared by the program cases and the GUI setup/checks of one episode."""

    def __init__(self, broker, out, scratch):
        self.broker = broker
        self.out = Path(out)
        self.scratch = Path(scratch)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.state = {}
        self.current_case = ''
        self.raw = []
        self.cache = {}
        folders = self.call({'op': 'help'}).get('document_folders') or {}
        if set(folders) != {'inputs', 'outputs'}:
            raise InfrastructureError('the runtime help names no document folders')
        self.inputs, self.outputs = folders['inputs'], folders['outputs']

    # -- runtime channels -------------------------------------------------------------------------------------
    def call(self, request, timeout=None):
        return self.broker.call(request, timeout=timeout)

    def trace(self, entry):
        self.raw.append({'case': self.current_case, **entry})
        if len(self.raw) >= 200:
            self.flush()

    def flush(self):
        if self.raw:
            with (self.out/'protocol.jsonl').open('a') as stream:
                for entry in self.raw:
                    stream.write(json.dumps(entry, ensure_ascii=False)+'\n')
            self.raw = []

    def close(self):
        self.flush()

    def upload(self, name, data, folder=''):
        request = {'op': 'upload', 'filename': name, 'base64': base64.b64encode(data).decode()}
        if folder:
            request['folder'] = folder
        try:
            self.call(request)
        except BrokerError as exc:
            if 'is in use' in exc.detail:
                # The place of the document is taken by what the application made of the input folder.
                raise AssertionError('the document could not be placed: '+exc.detail[:300]) from None
            raise InfrastructureError('the runtime refused a verifier document: '+exc.detail) from None
        self.trace({'upload': f'{folder}/{name}' if folder else name, 'size': len(data)})
        return self.input_path(f'{folder}/{name}' if folder else name)

    def input_path(self, relative):
        return f'{self.inputs}/{relative}'

    def command(self, name, argument=''):
        """One remote command line; product rejections are observations, broker errors are not raised here."""
        request = {'op': 'command', 'name': name, **({'argument': argument} if argument else {})}
        try:
            result = self.call(request, timeout=120)
        except BrokerError as exc:
            result = {'error': exc.detail}
        self.trace({'command': name, 'argument': argument, 'exit_code': result.get('exit_code'),
                    'error': result.get('error')})
        return result

    def cli(self, *args):
        try:
            result = self.call({'op': 'cli', 'args': list(args)}, timeout=120)
        except BrokerError as exc:
            result = {'error': exc.detail}
        self.trace({'cli': list(args), 'exit_code': result.get('exit_code'), 'error': result.get('error')})
        return result

    def status(self):
        return self.call({'op': 'status'})

    def restart(self):
        status = self.call({'op': 'restart'}, timeout=180)
        self.trace({'restart': status.get('ready')})
        if not status.get('ready'):
            raise AssertionError('the application did not come back after a restart: '+str(status.get('detail')))
        return status

    def reset(self):
        status = self.call({'op': 'reset'}, timeout=180)
        self.trace({'reset': status.get('ready')})
        self.cache.clear()
        if not status.get('ready'):
            raise AssertionError('the application did not start on a fresh instance: '+str(status.get('detail')))
        return status

    def listing(self):
        return self.call({'op': 'list_files'})

    def download(self, ref):
        got = self.call({'op': 'download', 'ref': ref})
        return base64.b64decode(got.get('body_base64', ''))

    def tree(self, area):
        """Relative paths of the files and folders of one document folder: {path: 'folder' | size}."""
        listing = self.listing()
        return {e['path']: ('folder' if e['type'] == 'folder' else e.get('size')) for e in listing.get(area, [])}

    def fetch(self, area, relative, wait=0.0):
        """Bytes of one file of a document folder, or None when it does not exist (waits up to `wait` s)."""
        deadline = time.monotonic()+wait
        while True:
            listing = self.listing()
            for entry in listing.get(area, []):
                if entry['type'] == 'file' and entry['path'] == relative:
                    return self.download(entry['ref'])
            if time.monotonic() >= deadline:
                return None
            time.sleep(.5)

    # -- product state ----------------------------------------------------------------------------------------
    def quit_session(self, restart=True, quits_itself=False, previous_session=None):
        """Quit the application with its own QUIT command and read the session it saved on exit (the
        session folder is the output folder); then start it again with the same data. When the commands already
        made the application quit (quits_itself), no further QUIT is sent: a remote command line without a
        running application is not part of the contract. For that case, previous_session is captured before
        issuing those commands, since the application can have finished writing by the time they return."""
        before = previous_session if quits_itself else self.fetch('outputs', SESSION_NAME)
        result = {'quit': 'by the commands'} if quits_itself else self.command('QUIT')
        deadline = time.monotonic()+20
        while self.status().get('running') and time.monotonic() < deadline:
            time.sleep(.3)
        running = self.status().get('running')
        data = self.fetch('outputs', SESSION_NAME, wait=3)
        if restart:
            self.restart()
        if running:
            raise AssertionError('the application did not exit after QUIT: '+json.dumps(result)[:300])
        if data is None:
            raise AssertionError('no session was saved in the session folder on exit')
        if before is not None and data == before:
            raise AssertionError('the session file was not rewritten on exit')
        return decode_session(data)

    def normalize(self, text):
        """Replace this instance's document-folder prefixes with stable names."""
        if not isinstance(text, str):
            return text
        return text.replace(self.inputs, '<inputs>').replace(self.outputs, '<outputs>')


def decode_session(data):
    try:
        import yaml
        return yaml.safe_load(gzip.decompress(data).decode('utf-8'))
    except Exception as exc:
        raise AssertionError(f'the session file is not gzip-compressed YAML: {type(exc).__name__}') from None


def compare(actual, expected):
    """Program observations compare exactly after each check's own projection."""
    if actual != expected:
        raise AssertionError('observation differs from the reference: '
                             + json.dumps(actual, ensure_ascii=False, sort_keys=True)[:1500])
