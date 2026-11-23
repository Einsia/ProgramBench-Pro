'''Verifier-side harness of the Zim suite: the candidate notebook, command line and desktop through the black-box runtime.

Program episodes and the independent checks of GUI checkpoints reach the candidate only through the task runtime:
upload and download (the exchange folders), list_files, cli (the command line of the product), clipboard_text, observe,
restart and reset. These are the channels the model has on the reference. A scenario notebook lives in a folder of its
own below the inbox, so a scenario never has to remove files: it uploads a fixture below a fresh folder name and runs
the command line on that folder. Nothing in this module is shown to the evaluator agent or the candidate.
'''
import base64
import dataclasses
import json
from pathlib import Path
import shutil
import time

from evaluation.broker import BrokerError
from evaluation.contract import InfrastructureError

NL = chr(10)
AREAS = ('inbox', 'outbox', 'notebook')
# Seconds a product file may take to appear (and stop growing) in an exchange folder after the action that wrote it.
FILE_SECONDS = 20
# Files per exchange folder kept below the runtime limit; a fresh instance (runtime reset) empties the folders.
FOLDER_LIMIT = 1400
FRESH_LIMIT = 100


class MissingDependency(AssertionError):
    '''A required earlier operation of the same scenario did not complete.'''


class State(dict):
    def __missing__(self, key):
        raise MissingDependency('missing successful prerequisite ' + str(key))


@dataclasses.dataclass
class Case:
    id: str
    family: str
    scenario: str
    channel: str
    description: str
    action: object
    needs: object = None
    attached: bool = False
    requires: tuple = ()


class Suite:
    '''Ordered program operations; setup rows prepare, scored rows are program assertions.

    needs(ctx) checks the in-scenario prerequisites of a scored row before it runs (an unmet one blocks only that row);
    requires names earlier scored rows of the same episode that a row counts together with (companions); attached
    scenarios stay in the same episode as the scenario before them.'''

    def __init__(self):
        self.cases = []
        self.ids = set()

    def add(self, family, scenario, step, action, channel='backend', description='', needs=None, attached=False,
            requires=()):
        identifier = f'{channel}.{family}.{scenario}.{step}'
        if identifier in self.ids:
            raise ValueError('duplicate case ' + identifier)
        self.ids.add(identifier)
        self.cases.append(Case(identifier, family, scenario, channel, description or step, action, needs, attached,
                               tuple(requires)))
        return identifier


def short(value, limit=160):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text.replace(NL, ' | ')[:limit]


class Context:
    '''State shared by the program cases and the GUI setup and checks of one episode.'''

    def __init__(self, broker, out, scratch):
        self.broker = broker
        self.out = Path(out)
        self.scratch = Path(scratch)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.state = State()
        self.current_case = ''
        self.raw = []
        self.successful = set()
        self.serial = 0
        self.root = None
        self.counts = dict.fromkeys(AREAS, 0)
        self.fresh_starts = 0
        self.dead = None

    # -- runtime channels -------------------------------------------------------------------------------------
    def call(self, request, timeout=None):
        return self.broker.call(request, timeout=timeout)

    def trace(self, entry):
        self.raw.append({'case': self.current_case, **entry})
        if len(self.raw) >= 200:
            self.flush()

    def flush(self):
        if self.raw:
            with (self.out / 'protocol.jsonl').open('a') as stream:
                for entry in self.raw:
                    stream.write(json.dumps(entry, ensure_ascii=False) + NL)
            self.raw = []

    # -- exchange folders -------------------------------------------------------------------------------------
    def upload(self, area, name, data):
        '''Store one file below an exchange folder (relative name, folders are created).'''
        if self.dead:
            raise MissingDependency(self.dead)
        if self.counts[area] >= FOLDER_LIMIT:
            self.fresh('the ' + area + ' is nearly full')
        try:
            got = self.call({'op': 'upload', 'area': area, 'filename': name, 'base64': base64.b64encode(data).decode()})
        except BrokerError as exc:
            raise InfrastructureError('the runtime refused a verifier document: ' + exc.detail) from None
        self.counts[area] += 1
        if self.root is None:
            self.root = Path(got['path'][:-len(name)].rstrip('/')).parent
        self.trace({'upload': area + '/' + name, 'size': len(data)})

    def prepare_root(self):
        '''The absolute folder that holds the exchange folders (learned from the answer of one tiny upload).'''
        if self.root is None:
            self.upload('inbox', 'exchange.txt', b'root')
        return self.root

    def path(self, area, relative=''):
        return str(self.prepare_root() / area / relative).rstrip('/')

    def notebook(self, files, folder=None):
        '''Upload a fixture notebook (relative name -> bytes) below a fresh folder of the inbox; returns its absolute folder.'''
        self.serial += 1
        folder = folder or f'nb{self.serial:04d}'
        for name, data in files.items():
            self.upload('inbox', folder + '/' + name, data)
        return self.path('inbox', folder)

    def read(self, area, name, wait=0):
        deadline = time.monotonic() + wait
        while True:
            try:
                got = self.call({'op': 'download', 'area': area, 'filename': name})
                return base64.b64decode(got.get('body_base64', ''))
            except BrokerError as exc:
                if time.monotonic() >= deadline:
                    raise AssertionError(f'{name} could not be read from the {area}: {exc.detail[:200]}') from None
                time.sleep(.4)

    def text(self, area, name, wait=0):
        return self.read(area, name, wait).decode('utf-8', 'replace')

    def listing(self, area, prefix=''):
        '''Sizes of the files below a folder of an area, by name relative to the area.'''
        files = self.call({'op': 'list_files', 'area': area}).get('files', [])
        self.counts[area] = max(self.counts[area], len(files))
        return {f['name']: f['size'] for f in files
                if not prefix or f['name'] == prefix or f['name'].startswith(prefix + '/')}

    def settled(self, area, name, wait=FILE_SECONDS):
        '''Bytes of a file once it exists and stopped changing (autosave writes pages in a thread).'''
        deadline = time.monotonic() + wait
        previous = None
        while True:
            size = self.listing(area).get(name)
            if size is not None and size == previous:
                return self.read(area, name)
            previous = size
            if time.monotonic() >= deadline:
                raise AssertionError(f'expected file {name} was not written to the {area}')
            time.sleep(.5)

    def tree(self, area, prefix):
        '''Every file below a folder, by name relative to it: the text of text files, the size of the others.'''
        result = {}
        for name, size in sorted(self.listing(area, prefix).items()):
            relative = name[len(prefix) + 1:] if prefix else name
            try:
                result[relative] = self.read(area, name).decode('utf-8')
            except (AssertionError, UnicodeDecodeError):
                result[relative] = size
        return result

    # -- command line -----------------------------------------------------------------------------------------
    def cli(self, command, *args, timeout=240):
        '''Run the command line of the product once; returns its exit code and printed text.'''
        request = {'op': 'cli', 'command': command, 'args': [str(a) for a in args]}
        try:
            got = self.call(request, timeout=timeout)
        except BrokerError as exc:
            self.trace({**request, 'error': exc.detail[:300]})
            raise AssertionError(f'cli {command} was refused or did not complete: {exc.detail[:300]}') from None
        self.trace({**request, 'exit_code': got.get('exit_code')})
        return {'exit_code': got.get('exit_code'), 'output': got.get('output', '')}

    # -- lifecycle --------------------------------------------------------------------------------------------
    def restart(self):
        '''Relaunch the application with the same instance data (runtime restart).'''
        status = self.call({'op': 'restart'}, timeout=180)
        self.trace({'lifecycle': 'restart', 'ready': status.get('ready')})
        assert status.get('ready'), 'the application did not come back after a restart: ' + str(status.get('detail'))
        return status

    def fresh(self, reason=''):
        '''A fresh instance (runtime reset): new data and empty exchange folders.'''
        if self.dead:
            raise MissingDependency(self.dead)
        if self.fresh_starts >= FRESH_LIMIT:
            raise MissingDependency('too many fresh application starts in this episode')
        self.fresh_starts += 1
        status = self.call({'op': 'reset'}, timeout=180)
        self.counts = dict.fromkeys(AREAS, 0)
        self.trace({'lifecycle': 'reset', 'reason': reason[:200], 'ready': status.get('ready')})
        if not status.get('ready'):
            self.dead = 'the application did not start in a fresh instance: ' + str(status.get('detail'))
            raise MissingDependency(self.dead)

    # -- desktop ----------------------------------------------------------------------------------------------
    def observe(self):
        try:
            return self.call({'op': 'observe'})
        except BrokerError as exc:
            raise AssertionError('the desktop could not be observed: ' + exc.detail[:300]) from None

    def visible_texts(self):
        return [str(n.get(key)) for n in self.observe().get('nodes', []) for key in ('name', 'text') if n.get(key)]

    def window_titles(self):
        try:
            windows = self.call({'op': 'windows'}).get('windows', [])
        except BrokerError as exc:
            raise AssertionError('the desktop windows could not be listed: ' + exc.detail[:300]) from None
        return [str(w.get('title', '')) for w in windows]

    def clipboard(self):
        try:
            return self.call({'op': 'clipboard_text'}).get('text', '')
        except BrokerError as exc:
            raise AssertionError('the clipboard could not be read: ' + exc.detail[:300]) from None

    def close(self):
        self.flush()
        shutil.rmtree(self.scratch, ignore_errors=True)


def difference(got, wanted, path='$'):
    '''The first place where two JSON values differ (empty when they are equal).'''
    if type(got) is not type(wanted):
        return f'{path}: {short(got, 80)} instead of {short(wanted, 80)}'
    if isinstance(wanted, dict):
        for key in sorted(set(got) | set(wanted)):
            if key not in got:
                return f'{path}.{key} is missing'
            if key not in wanted:
                return f'{path}.{key} is unexpected'
            found = difference(got[key], wanted[key], f'{path}.{key}')
            if found:
                return found
        return ''
    if isinstance(wanted, list):
        if len(got) != len(wanted):
            return f'{path}: {len(got)} items instead of {len(wanted)}'
        for index, (left, right) in enumerate(zip(got, wanted)):
            found = difference(left, right, f'{path}[{index}]')
            if found:
                return found
        return ''
    return '' if got == wanted else f'{path}: {short(got, 80)} instead of {short(wanted, 80)}'


def compare(actual, expected):
    '''Observations are compared exactly after a JSON round trip: the case projections already normalise the order of
    unordered results, whitespace and generated fields, so no tolerance is applied here.'''
    got = json.loads(json.dumps(actual, ensure_ascii=False))
    found = difference(got, expected)
    assert not found, 'observation differs from the reference: ' + found


__all__ = ['Case', 'Context', 'MissingDependency', 'State', 'Suite', 'compare', 'difference', 'short', 'FILE_SECONDS']
