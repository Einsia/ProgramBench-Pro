'''Verifier-side harness: the candidate command line, documents and desktop through the black-box runtime.

Program episodes (exit codes and parsed outputs), public setup and the independent checks of GUI checkpoints reach the
candidate only through the task runtime: convert (the product command line), upload, list_files and download (the owned
document areas), windows (the desktop), reset and restart. These are the channels the model has on the reference.
Nothing in this module is shown to the evaluator agent or the candidate.
'''
import base64
import dataclasses
import json
import re
import shutil
import time
from pathlib import Path

from evaluation.broker import BrokerError
from evaluation.contract import InfrastructureError
import fixtures
import semantic

# Seconds a product file may take to appear in the owned output area after the command or dialog that wrote it.
FILE_SECONDS = 15
CONVERT_SECONDS = 120
# A fresh instance (runtime reset) is only a fallback; at most this often per episode.
FRESH_LIMIT = 200
AREA_NOTE = re.compile(r'(inputs|outputs|projects) (/[^ ,]+)')
SUFFIX_KIND = {'musicxml': 'musicxml', 'xml': 'musicxml', 'mid': 'mid', 'midi': 'mid', 'mscx': 'mscx', 'mscz': 'mscz',
               'mxl': 'mxl', 'pdf': 'pdf', 'png': 'png', 'svg': 'svg', 'mei': 'mei', 'mnx': 'mnx', 'lrc': 'lrc'}
PROJECTIONS = {
    'musicxml': semantic.musicxml_project,
    'mid': semantic.midi_project,
    'mscx': semantic.mscx_project,
    'mscz': semantic.mscz_project,
    'mxl': semantic.mxl_project,
    'pdf': semantic.pdf_project,
    'svg': semantic.svg_project,
    'mei': semantic.mei_project,
    'png': semantic.png_project,
    'mnx': semantic.mnx_project,
    'lrc': semantic.lrc_project,
}
STDOUT_PROJECTIONS = {'meta': semantic.meta_project, 'elements': semantic.elements_project,
                      'transposed': semantic.transposed_project, 'version': semantic.version_project,
                      'parts': semantic.parts_project, 'partspdf': semantic.parts_pdf_project,
                      'media': semantic.media_project}


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

    needs(ctx) checks the in-scenario prerequisites of a scored row before it runs (an unmet one blocks only that
    row); requires names earlier scored rows of the same episode that a row counts together with (companions);
    attached scenarios stay in the same episode as the scenario before them.'''

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


class Context:
    '''State shared by the program cases and the GUI setup and checks of one episode.'''

    def __init__(self, broker, out, scratch):
        self.broker = broker
        self.out = Path(out)
        self.scratch = Path(scratch)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.state = State()
        self.current_case = ''
        self.serial = 0
        self.raw = []
        self.successful = set()
        self.uploaded = set()
        self.projects = {}
        self.files = {}
        self.areas = None
        self.fresh_starts = 0
        # Verifier-private fixture bytes; the application gets uploaded copies.
        self.catalog = fixtures.catalog()

    # -- runtime channels --------------------------------------------------------------------------------------
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
                    stream.write(json.dumps(entry, ensure_ascii=False) + chr(10))
            self.raw = []

    def area(self, name):
        '''Absolute path of a document area, as the runtime help names it (job documents need absolute paths).'''
        if self.areas is None:
            notes = self.call({'op': 'help'}).get('notes', [])
            found = {key: value.rstrip('.') for note in notes for key, value in AREA_NOTE.findall(note)}
            if set(found) != {'inputs', 'outputs', 'projects'}:
                raise InfrastructureError('the runtime help does not name the document areas')
            self.areas = found
        return self.areas[name]

    # -- documents ---------------------------------------------------------------------------------------------
    def upload(self, filename, data):
        try:
            self.call({'op': 'upload', 'filename': filename, 'base64': base64.b64encode(data).decode()})
        except BrokerError as exc:
            raise InfrastructureError('the runtime refused a verifier document: ' + exc.detail) from None
        self.uploaded.add(filename)
        self.trace({'upload': filename, 'size': len(data)})

    def fixture(self, name):
        '''The document name of a fixture in the runtime input area (uploaded on first use).'''
        if name not in self.catalog:
            raise InfrastructureError('unknown verifier fixture ' + name)
        if name not in self.uploaded:
            self.upload(name, self.catalog[name])
        return name

    def document(self, name, data):
        '''Upload a document the verifier builds itself (a job, a style file, a damaged score).'''
        self.upload(name, data)
        return name

    def name(self, stem, suffix):
        '''A unique output name; names never enter an observation.'''
        self.serial += 1
        return '%s-%05d%s' % (stem, self.serial, suffix)

    def pending(self):
        return self.call({'op': 'list_files'}).get('downloads', [])

    def download(self, ref):
        got = self.call({'op': 'download', 'ref': ref})
        return got.get('filename'), base64.b64decode(got.get('body_base64', ''))

    def take(self, rel, reply=None, wait=FILE_SECONDS):
        '''Bytes of the newest product file at this path (relative to the owned files folder, for example
        outputs/a.mid), from the refs of a convert reply or of list_files.'''
        deadline = time.monotonic() + wait
        while True:
            refs = [d for d in (reply or {}).get('downloads', []) if d.get('filename') == rel]
            refs = refs or [d for d in self.pending() if d.get('filename') == rel]
            if refs:
                try:
                    return self.download(refs[-1]['ref'])[1]
                except BrokerError:
                    reply = None
            if time.monotonic() >= deadline:
                raise AssertionError('expected file ' + rel + ' was not written')
            time.sleep(0.25)

    def collect(self):
        '''Drain every pending product file (after GUI operations or scripted runs), newest content per path.'''
        for ref in self.pending():
            name, data = self.download(ref['ref'])
            self.files[name] = data

    def fetch(self, rel, wait=FILE_SECONDS):
        '''A product file written through the GUI (for example a native save), once it stopped changing.'''
        deadline = time.monotonic() + wait
        while True:
            self.collect()
            if rel in self.files:
                time.sleep(0.3)
                self.collect()
                return self.files[rel]
            if time.monotonic() >= deadline:
                raise AssertionError('expected file ' + rel + ' was not written')
            time.sleep(0.25)

    # -- the product command line ------------------------------------------------------------------------------
    def convert(self, *args):
        '''One product command line through the runtime; returns exit_code, ok, stdout, log and downloads.'''
        record = {'convert': list(args)}
        try:
            reply = self.call({'op': 'convert', 'args': list(args)}, timeout=CONVERT_SECONDS)
        except BrokerError as exc:
            self.trace({**record, 'error': exc.detail[:300]})
            raise AssertionError('convert did not complete: ' + exc.detail[:300]) from None
        if not isinstance(reply, dict) or type(reply.get('exit_code')) is not int:
            raise AssertionError('convert returned no exit code')
        self.trace({**record, 'exit_code': reply['exit_code'], 'files': [d.get('filename') for d in reply.get('downloads', [])]})
        return reply

    def produce(self, source, suffix, *options):
        '''Convert an uploaded or produced document to one output file; returns (reply, bytes).'''
        out = self.name(Path(source).stem, suffix)
        reply = self.convert(source, *options, '-o', out)
        assert reply['exit_code'] == 0, 'the product exited with status ' + str(reply['exit_code'])
        return reply, self.take('outputs/' + out, reply)

    def project_of(self, fixture):
        '''The fixture imported into a project document (mscz) in the output area; cached per scenario.'''
        if fixture not in self.projects:
            self.fixture(fixture)
            out = Path(fixture).stem + '.mscz'
            reply = self.convert(fixture, '-o', out)
            assert reply['exit_code'] == 0, 'the product could not import ' + fixture
            self.projects[fixture] = out
        return self.projects[fixture]

    def produce_pages(self, source, suffix, *options):
        '''A paged output (svg, png): the product writes one file per page, named <name>-<page><suffix>; returns the reply and the pages in order.'''
        stem = self.name(Path(source).stem, '')
        reply = self.convert(source, *options, '-o', stem + suffix)
        assert reply['exit_code'] == 0, 'the product exited with status ' + str(reply['exit_code'])
        found = {}
        for item in reply.get('downloads', []):
            match = re.fullmatch('outputs/' + re.escape(stem) + r'-(\d+)' + re.escape(suffix), item.get('filename', ''))
            if match:
                found[int(match.group(1))] = item['filename']
        assert found, 'the product wrote no page files'
        return reply, [self.take(found[number], reply) for number in sorted(found)]

    def produce_mscx(self, source):
        '''The score document (mscx) of a project: a directory format, so each export gets its own folder in the output area.'''
        stem = Path(source).stem
        folder = self.name(stem, '-mscx')
        reply = self.convert(source, '-o', '%s/%s/%s.mscx' % (self.area('outputs'), folder, stem))
        assert reply['exit_code'] == 0, 'the product exited with status ' + str(reply['exit_code'])
        return reply, self.take('outputs/%s/%s.mscx' % (folder, stem), reply)

    def project(self, name, data):
        '''The projection of a product file, chosen by its suffix.'''
        kind = SUFFIX_KIND.get(Path(name).suffix[1:].lower())
        if kind is None:
            raise AssertionError('no projection for ' + name)
        return PROJECTIONS[kind](data)

    def audio(self, name, data):
        return semantic.audio_project(data, Path(name).suffix.lower())

    def stdout_projection(self, kind, reply):
        assert reply['exit_code'] == 0, 'the product exited with status ' + str(reply['exit_code'])
        return STDOUT_PROJECTIONS[kind](reply.get('stdout', ''))

    def refusal(self, reply):
        '''What a failed run shows: its exit code and the kinds of files it left behind.'''
        return {'exit_code': reply['exit_code'], 'left': sorted(Path(d['filename']).suffix for d in reply.get('downloads', []))}

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def restart(self):
        '''Relaunch the application with the same instance data (runtime restart).'''
        status = self.call({'op': 'restart'}, timeout=180)
        self.trace({'lifecycle': 'restart', 'ready': status.get('ready')})
        assert status.get('ready'), 'the application did not come back after a restart: ' + str(status.get('detail'))
        return status

    def fresh(self, reason=''):
        '''A fresh instance: runtime reset (new data, inputs and outputs).'''
        if self.fresh_starts >= FRESH_LIMIT:
            raise MissingDependency('too many fresh application starts in this episode')
        self.fresh_starts += 1
        status = self.call({'op': 'reset'}, timeout=180)
        self.uploaded.clear()
        self.projects.clear()
        self.files.clear()
        self.trace({'lifecycle': 'reset', 'reason': reason[:200], 'ready': status.get('ready')})
        if not status.get('ready'):
            raise MissingDependency('the application did not start in a fresh instance: ' + str(status.get('detail')))

    def new_scenario(self, name):
        '''Scenario boundary: command-line runs keep no state, so only the scenario cache is cleared.'''
        self.state.clear()
        self.projects.clear()
        self.state['scenario'] = name

    def require_success(self, identifier):
        if identifier not in self.successful:
            raise MissingDependency('missing successful operation ' + identifier)

    # -- desktop -----------------------------------------------------------------------------------------------
    def window_titles(self):
        try:
            windows = self.call({'op': 'windows'}).get('windows', [])
        except BrokerError as exc:
            raise AssertionError('the desktop windows could not be listed: ' + exc.detail[:300]) from None
        return [str(w.get('title', '')) for w in windows]

    def close(self):
        self.flush()
        shutil.rmtree(self.scratch, ignore_errors=True)


compare = semantic.compare

__all__ = ['Case', 'Context', 'MissingDependency', 'State', 'Suite', 'compare']
