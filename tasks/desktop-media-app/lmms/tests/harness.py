'''Verifier-side harness: the candidate's command line, documents and desktop through the black-box runtime.

Program episodes (renders, project dumps and upgrades), public setup and the independent checks of GUI checkpoints
reach the candidate only through the task's runtime: cli (the product command line, run through start.sh), upload,
list_files and download (the owned document areas), settings, observe (the accessible desktop), reset and restart.
These are the channels the model has on the reference. Nothing in this module is shown to the evaluator agent or the
candidate.
'''
import base64
import dataclasses
import hashlib
import json
import math
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from evaluation.broker import BrokerError
from evaluation.contract import InfrastructureError
from fixtures import FixtureSpec, Signal, write_fixture
from semantic import audio_observe, compare_observations, decode_audio

EXPORT_SECONDS = 10
FILE_SECONDS = 15
# Documented tolerances: linear signal paths compare within 2.5 LSB of 16 bit or a relative 1e-3; a check that observes
# DSP-heavy output declares its own bounds.
ABSOLUTE = 2.5 / 32768
RELATIVE = 1e-3
# Window geometry and ids are not behaviour; they differ between a saved project and its upgrade.
GEOMETRY = frozenset(('x', 'y', 'width', 'height', 'visible', 'minimized', 'maximized'))
TEXT_KEYS = frozenset(('name', 'src', 'label', 'text', 'userwavefile', 'type', 'version', 'creator', 'creatorversion'))
SORTED_CHILDREN = frozenset(('note', 'time'))
# Verifier-made samples, generated from signal parameters; the candidate gets uploaded copies of them.
SAMPLES = {
    'tone-440': FixtureSpec('tone-440', 'tone-440.wav', signals=(Signal(frequency=440, amplitude=0.5),)),
    'tone-880': FixtureSpec('tone-880', 'tone-880.wav', signals=(Signal(frequency=880, amplitude=0.4),)),
    'square-220': FixtureSpec('square-220', 'square-220.wav', signals=(Signal(waveform='square', frequency=220, amplitude=0.25),)),
    'ramp': FixtureSpec('ramp', 'ramp.wav', signals=(Signal(waveform='ramp', amplitude=0.5),)),
    'impulse': FixtureSpec('impulse', 'impulse.wav', signals=(Signal(waveform='impulse', frequency=100, amplitude=0.5),)),
    'stereo-pair': FixtureSpec('stereo-pair', 'stereo-pair.wav',
                               signals=(Signal(frequency=440, amplitude=0.3), Signal(frequency=880, amplitude=0.2))),
    'rate-48000': FixtureSpec('rate-48000', 'rate-48000.wav', rate=48000, frames=48000,
                              signals=(Signal(frequency=330, amplitude=0.5),)),
    'tone-2s': FixtureSpec('tone-2s', 'tone-2s.wav', frames=88200, signals=(Signal(frequency=440, amplitude=0.5),)),
    'rate-48000-high': FixtureSpec('rate-48000-high', 'rate-48000-high.wav', rate=48000, frames=48000,
                                   signals=(Signal(frequency=10000, amplitude=0.5),)),
    'rate-22050': FixtureSpec('rate-22050', 'rate-22050.wav', rate=22050, frames=22050,
                              signals=(Signal(frequency=330, amplitude=0.5),)),
}


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


@dataclasses.dataclass
class Rendered:
    '''One render through the command line: the exit status and text are reported, the written file decides.'''
    exit_code: int
    output: str
    audio: object = None
    size: int = 0


class Context:
    '''State shared by the program cases and the GUI setup/checks of one episode.'''

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
        self.decoded = {}
        self.files = {}
        self.documents = None

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
                    stream.write(json.dumps(entry, ensure_ascii=False) + chr(10))
            self.raw = []

    # -- documents ---------------------------------------------------------------------------------------------
    def areas(self):
        '''The absolute document areas of this runtime instance, read from its help (a public channel).'''
        if self.documents is None:
            notes = self.call({'op': 'help'}).get('notes', [])
            note = next((n for n in notes if n.startswith('Document areas:')), None)
            if note is None:
                raise InfrastructureError('the runtime help does not name the document areas')
            found = {}
            for part in note[len('Document areas:'):].split('. ')[0].split(','):
                name, path = part.strip().split(' ', 1)
                found[name] = path.strip()
            if set(found) != {'inputs', 'outputs', 'projects'}:
                raise InfrastructureError('the runtime help names unexpected document areas')
            self.documents = found
        return self.documents

    def path(self, area, name):
        return self.areas()[area] + '/' + name

    def upload(self, filename, data):
        try:
            self.call({'op': 'upload', 'filename': filename, 'base64': base64.b64encode(data).decode()})
        except BrokerError as exc:
            raise InfrastructureError('the runtime refused a verifier document: ' + exc.detail) from None
        self.uploaded.add(filename)
        self.trace({'upload': filename, 'size': len(data)})

    def sample(self, key):
        '''(absolute document path, decoded original) of a verifier sample; uploaded on first use of an instance.'''
        spec = SAMPLES[key]
        if key not in self.decoded:
            path = write_fixture(spec, self.scratch / 'samples')
            self.decoded[key] = (path, decode_audio(path))
        path, audio = self.decoded[key]
        if spec.filename not in self.uploaded:
            self.upload(spec.filename, path.read_bytes())
        return self.path('inputs', spec.filename), audio

    def project(self, name, content):
        '''Upload a project document (XML text or the bytes of a compressed project); returns its absolute path.'''
        self.upload(name, content if isinstance(content, bytes) else content.encode('utf-8'))
        return self.path('inputs', name)

    def pending(self):
        return self.call({'op': 'list_files'}).get('downloads', [])

    def download(self, ref):
        got = self.call({'op': 'download', 'ref': ref})
        return got.get('filename'), base64.b64decode(got.get('body_base64', ''))

    def take(self, filename, refs=(), wait=EXPORT_SECONDS):
        '''Bytes of the newest product file of this name in the owned areas, once it stopped changing.'''
        refs = [r for r in refs or () if r.get('filename') == filename]
        deadline = time.monotonic() + wait
        data = None
        while True:
            if not refs:
                refs = [r for r in self.pending() if r.get('filename') == filename]
            if refs:
                for ref in refs:
                    _name, data = self.download(ref['ref'])
                refs = []
                # A file still being written is listed again with a new ref once its size or time changes.
                time.sleep(.3)
                refs = [r for r in self.pending() if r.get('filename') == filename]
                if not refs:
                    return data
                continue
            if data is not None:
                return data
            if time.monotonic() >= deadline:
                raise AssertionError(f'expected file {filename} was not written')
            time.sleep(.25)

    def fetch(self, filename, wait=FILE_SECONDS):
        '''A product file written through the GUI (for example a native export), as a verifier-private copy.'''
        pending = [r for r in self.pending() if r.get('filename') == filename]
        if filename not in self.files or pending:
            data = self.take(filename, pending, wait=wait)
            target = self.scratch / 'files' / f'{len(self.files):03d}-{hashlib.sha256(filename.encode()).hexdigest()[:12]}'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            self.files[filename] = target
        return self.files[filename]

    def collect(self):
        '''Drain every pending product file (after GUI operations), newest content per name.'''
        for ref in self.pending():
            name, data = self.download(ref['ref'])
            target = self.scratch / 'files' / f'{len(self.files):03d}-{hashlib.sha256(str(name).encode()).hexdigest()[:12]}'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            self.files[name] = target

    # -- command line ------------------------------------------------------------------------------------------
    def cli(self, action, project, output=None, **options):
        '''One action of the product command line: exit status, text output, XML body (dump, upgrade) and the files
        it wrote by name.'''
        request = {'op': 'cli', 'action': action, 'project': project}
        request.update({key: value for key, value in options.items() if value is not None})
        if output is not None:
            request['output'] = output
        record = {'cli': action, 'project': project, 'output': output, 'options': options}
        try:
            reply = self.call(request, timeout=130)
            files = {}
            for item in reply.get('downloads', []):
                name, data = self.download(item['ref'])
                files[name] = data
        except BrokerError as exc:
            self.trace({**record, 'error': exc.detail[:300]})
            raise AssertionError(f'{action} did not complete: {exc.detail[:300]}') from None
        if not isinstance(reply.get('exit_code'), int):
            raise AssertionError(f'{action} returned no exit status')
        self.trace({**record, 'exit_code': reply['exit_code'], 'text': str(reply.get('output', ''))[:400],
                    'files': {name: len(data) for name, data in files.items()}})
        return {'exit_code': reply['exit_code'], 'output': str(reply.get('output', '')), 'body': reply.get('body'),
                'files': files}

    def render(self, xml, name, fmt='wav', **options):
        '''Render a generated project; the written file is decoded by the verifier's own FFmpeg.'''
        self.serial += 1
        stem = f'{name}-{self.serial:05d}'
        project = self.project(stem + '.mmp', xml)
        output = f'{stem}.{fmt}'
        reply = self.cli('render', project, output=output, format=fmt, **options)
        data = reply['files'].get(output)
        audio = None
        if data is not None:
            path = self.scratch / 'renders' / output
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            audio = decode_audio(path)
            self.audit_artifact(path, audio)
            path.unlink()
        return Rendered(reply['exit_code'], reply['output'], audio, len(data or b''))

    def audit_artifact(self, path, audio):
        path = Path(path)
        assert path.is_file() and audio.frames >= 0 and audio.channels > 0 and audio.sample_rate > 0
        with (self.out / 'artifacts.jsonl').open('a') as stream:
            stream.write(json.dumps({'case': self.current_case, 'file': path.name,
                                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'decoded': True,
                                     'frames': audio.frames, 'sample_rate': audio.sample_rate,
                                     'channels': audio.channels}) + chr(10))

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def restart(self):
        '''Relaunch the application with the same instance data (runtime restart).'''
        status = self.call({'op': 'restart'}, timeout=180)
        self.trace({'lifecycle': 'restart', 'ready': status.get('ready')})
        assert status.get('ready'), 'the application did not come back after a restart: ' + str(status.get('detail'))
        return status

    def fresh(self, reason=''):
        '''A fresh instance: runtime reset (new data, inputs and outputs).'''
        status = self.call({'op': 'reset'}, timeout=180)
        self.uploaded.clear()
        self.files.clear()
        self.trace({'lifecycle': 'reset', 'reason': reason[:200], 'ready': status.get('ready')})
        assert status.get('ready'), 'the application did not start in a fresh instance: ' + str(status.get('detail'))

    def settings(self):
        try:
            return self.call({'op': 'settings'}).get('body', '')
        except BrokerError as exc:
            raise AssertionError('the settings file could not be read: ' + exc.detail[:300]) from None

    # -- desktop -----------------------------------------------------------------------------------------------
    def observe(self):
        try:
            return self.call({'op': 'observe'})
        except BrokerError as exc:
            raise AssertionError('the desktop could not be observed: ' + exc.detail[:300]) from None

    def window_titles(self):
        try:
            windows = self.call({'op': 'windows'}).get('windows', [])
        except BrokerError as exc:
            raise AssertionError('the desktop windows could not be listed: ' + exc.detail[:300]) from None
        return [str(w.get('title', '')) for w in windows]

    def close(self):
        self.flush()
        shutil.rmtree(self.scratch, ignore_errors=True)


# -- observations ----------------------------------------------------------------------------------------------
def signal_projection(audio, windows=8, spectrum=True):
    '''Bounded projection of decoded audio: format, length and per channel peak, RMS, DC, window levels and spectrum.
    Header bytes, tags and sample hashes never enter it.'''
    observed = audio_observe(audio, windows=windows, waveform_points=8, spectrum=spectrum)
    rows = []
    for channel in observed['channel_observations']:
        row = {key: channel[key] for key in ('peak', 'rms', 'dc')}
        row['windows'] = [{key: w[key] for key in ('peak', 'rms', 'dc')} for w in channel['windows']]
        if spectrum:
            band = channel['spectrum']
            row['spectrum'] = {'centroid_hz': band['centroid_hz'], 'band_ratios': [b['ratio'] for b in band['bands']]}
        rows.append(row)
    return {'sample_rate': audio.sample_rate, 'channels': audio.channels, 'frames': audio.frames,
            'codec': audio.codec, 'sample_format': audio.sample_format, 'signals': rows}


def number(value):
    '''A numeric attribute as a rounded float so that formatting does not matter; anything else stays text.'''
    try:
        parsed = float(value)
    except ValueError:
        return value
    return round(parsed, 6) if math.isfinite(parsed) else value


def normalize(node, paths):
    '''A project element without ids, window geometry and environment-dependent document paths.'''
    attributes = {}
    for key, value in sorted(node.attrib.items()):
        if key in GEOMETRY or key == 'id':
            continue
        if key in TEXT_KEYS:
            for token, area in paths.items():
                value = value.replace(area, token)
            attributes[key] = value
        else:
            attributes[key] = number(value)
    children = [normalize(child, paths) for child in node]
    if children and all(child['tag'] in SORTED_CHILDREN for child in children):
        children.sort(key=lambda child: json.dumps(child, sort_keys=True))
    result = {'tag': node.tag, 'attrs': attributes, 'children': children}
    text = (node.text or '').strip()
    if text:
        result['text'] = text
    return result


def project_projection(xml_text, paths=None):
    '''Normalized projection of project XML (the body of dump or upgrade, or a saved project file).'''
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise AssertionError('the project XML does not parse: ' + str(exc)[:200]) from None
    return normalize(root, paths or {})


def compare(actual, expected, *, frames=0, absolute=ABSOLUTE, relative=RELATIVE):
    '''Documented tolerance: counts, strings and shapes exact; floats within the absolute bound or the relative one;
    frames within the declared slack (lengths of resampled or oversampled output).'''
    actual = json.loads(json.dumps(actual))
    if (frames and isinstance(actual, dict) and isinstance(expected, dict) and type(actual.get('frames')) is int
            and type(expected.get('frames')) is int and abs(actual['frames'] - expected['frames']) <= frames):
        actual['frames'] = expected['frames']
    compare_observations(actual, expected, absolute=absolute, relative=relative)


__all__ = ['ABSOLUTE', 'RELATIVE', 'SAMPLES', 'Case', 'Context', 'MissingDependency', 'Rendered', 'State', 'Suite',
           'compare', 'project_projection', 'signal_projection']
