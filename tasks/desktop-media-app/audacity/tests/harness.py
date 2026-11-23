"""Verifier-side harness: the candidate's scripting, documents and desktop through the black-box runtime.

Program episodes (scripting replies, decoded audio, persistence), public setup
and the independent checks of GUI checkpoints reach the candidate only through
the task's runtime: script (the product's scripting FIFO), upload, list_files
and download (the owned document areas), observe (the accessible desktop),
reset and restart. These are the channels the model has on the reference.
Nothing in this module is shown to the evaluator agent or the candidate.
"""
import base64
import dataclasses
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from evaluation.broker import BrokerError
from evaluation.contract import InfrastructureError
from fixtures import generate_catalog
from semantic import audio_observe, compare_observations, decode_audio

ROOT = Path(__file__).resolve().parent
# Reply text of action commands is optional in the scripting contract: only query
# commands carry an observable body.
QUERY_COMMANDS = {'GetInfo', 'GetPreference'}
# Seconds a product file may take to appear in the owned output area after the command or dialog that wrote it.
EXPORT_SECONDS = 10
FILE_SECONDS = 15
# A soft scenario reset that fails falls back to a fresh instance (runtime reset), at most this often per
# episode without a working scripting endpoint afterwards.
FRESH_LIMIT = 200


class MissingDependency(AssertionError):
    """A required earlier operation of the same scenario did not complete."""


class State(dict):
    def __missing__(self, key):
        raise MissingDependency('missing successful prerequisite '+str(key))


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
    """Ordered program operations; setup rows prepare, scored rows are program assertions.

    needs(ctx) checks the in-scenario prerequisites of a scored row before it runs (an unmet one blocks only that
    row); requires names earlier scored rows of the same episode that a row counts together with (companions);
    attached scenarios stay in the same episode as the scenario before them."""

    def __init__(self):
        self.cases = []
        self.ids = set()

    def add(self, family, scenario, step, action, channel='backend', description='', needs=None, attached=False,
            requires=()):
        identifier = f'{channel}.{family}.{scenario}.{step}'
        if identifier in self.ids:
            raise ValueError('duplicate case '+identifier)
        self.ids.add(identifier)
        self.cases.append(Case(identifier, family, scenario, channel, description or step, action, needs, attached,
                               tuple(requires)))
        return identifier


def fixture_store():
    """Deterministic fixtures generated once per run in the verifier's private temporary directory."""
    source = (ROOT/'fixtures.py').read_bytes()
    base = Path(os.environ.get('TMPDIR', '/tmp'))/('fixtures-'+hashlib.sha256(source).hexdigest()[:16])
    if (base/'catalog.json').is_file():
        return base, json.loads((base/'catalog.json').read_text())
    base.parent.mkdir(parents=True, exist_ok=True)
    with open(str(base)+'.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not (base/'catalog.json').is_file():
            work = Path(tempfile.mkdtemp(prefix='fixtures-', dir=base.parent))
            paths = generate_catalog(work, encoded=True, invalid=True)
            catalog = {key: path.name for key, path in paths.items()}
            (work/'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False))
            shutil.rmtree(base, ignore_errors=True)
            work.rename(base)
    return base, json.loads((base/'catalog.json').read_text())


def strings(value):
    """Every text of an observation (names, texts, titles, descriptions), whatever its nesting."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


class Context:
    """State shared by the program cases and the GUI setup/checks of one episode."""

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
        self.last_export = None
        self.last_audio = None
        self.uploaded = set()
        self.files = {}
        self.scripting_dead = None
        self.fresh_starts = 0
        store, catalog = fixture_store()
        # Expectations decode verifier-private originals; the application gets uploaded copies.
        self.original_fixtures = {key: store/name for key, name in catalog.items()}

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

    # -- documents ---------------------------------------------------------------------------------------------
    def reference_fixture(self, name):
        if name in self.original_fixtures:
            return self.original_fixtures[name]
        for path in self.original_fixtures.values():
            if path.name == name:
                return path
        raise InfrastructureError('unknown verifier fixture '+name)

    def fixture_name(self, name):
        """The document name of a fixture in the runtime's input area (uploaded on first use)."""
        path = self.reference_fixture(name)
        if path.name not in self.uploaded:
            self.upload(path.name, path.read_bytes())
        return path.name

    def upload(self, filename, data):
        try:
            self.call({'op': 'upload', 'filename': filename, 'base64': base64.b64encode(data).decode()})
        except BrokerError as exc:
            raise InfrastructureError('the runtime refused a verifier document: '+exc.detail) from None
        self.uploaded.add(filename)
        self.trace({'upload': filename, 'size': len(data)})

    def pending(self):
        return self.call({'op': 'list_files'}).get('downloads', [])

    def download(self, ref):
        got = self.call({'op': 'download', 'ref': ref})
        return got.get('filename'), base64.b64decode(got.get('body_base64', ''))

    def take(self, filename, refs=(), wait=EXPORT_SECONDS):
        """Bytes of the newest product file of this name in the owned areas, once it stopped changing."""
        refs = [r for r in refs or () if r.get('filename') == filename]
        deadline = time.monotonic()+wait
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
        """A product file written through the GUI (for example a native export), as a verifier-private copy."""
        pending = [r for r in self.pending() if r.get('filename') == filename]
        if filename not in self.files or pending:
            data = self.take(filename, pending, wait=wait)
            target = self.scratch/'files'/f'{len(self.files):03d}-{hashlib.sha256(filename.encode()).hexdigest()[:12]}'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            self.files[filename] = target
        return self.files[filename]

    def collect(self):
        """Drain every pending product file (after GUI operations), newest content per name."""
        for ref in self.pending():
            name, data = self.download(ref['ref'])
            target = self.scratch/'files'/f'{len(self.files):03d}-{hashlib.sha256(str(name).encode()).hexdigest()[:12]}'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            self.files[name] = target

    # -- scripting ---------------------------------------------------------------------------------------------
    def command(self, name, **params):
        if self.scripting_dead:
            raise MissingDependency('scripting endpoint unavailable: '+self.scripting_dead)
        record = {'command': name, 'params': params}
        try:
            response = self.call({'op': 'script', 'command': name, 'params': params})
        except BrokerError as exc:
            self.trace({**record, 'error': exc.detail[:300]})
            raise AssertionError(f'{name} did not complete: {exc.detail[:300]}') from None
        if not isinstance(response, dict) or not isinstance(response.get('ok'), bool):
            raise AssertionError(f'{name} returned no public status')
        self.trace({**record, 'response': {k: v for k, v in response.items() if k != 'downloads'}})
        value = {'ok': response['ok'], 'body': response.get('body') if name in QUERY_COMMANDS else None}
        for key in ('notifications', 'downloads'):
            if key in response:
                value[key] = response[key]
        return value

    def require(self, name, **params):
        response = self.command(name, **params)
        assert response['ok'], f'{name} failed'
        return response['body']

    def info(self, kind):
        return self.require('GetInfo', Type=kind, Format='JSON')

    def import_audio(self, name):
        return self.require('Import2', Filename=self.fixture_name(name))

    def select(self, start, end, track=0, count=1):
        return self.require('Select', Start=start, End=end, Track=track, TrackCount=count)

    def require_success(self, identifier):
        if identifier not in self.successful:
            raise MissingDependency('missing successful operation '+identifier)

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def restart(self):
        """Relaunch the application with the same instance data (runtime restart)."""
        status = self.call({'op': 'restart'}, timeout=180)
        self.trace({'lifecycle': 'restart', 'ready': status.get('ready')})
        assert status.get('ready'), 'the application did not come back after a restart: '+str(status.get('detail'))
        return status

    def fresh(self, reason=''):
        """A fresh instance: runtime reset (new data, inputs and outputs), then a working scripting endpoint."""
        if self.scripting_dead:
            raise MissingDependency('scripting endpoint unavailable: '+self.scripting_dead)
        if self.fresh_starts >= FRESH_LIMIT:
            raise MissingDependency('too many fresh application starts in this episode')
        self.fresh_starts += 1
        status = self.call({'op': 'reset'}, timeout=180)
        self.uploaded.clear()
        self.trace({'lifecycle': 'reset', 'reason': reason[:200], 'ready': status.get('ready')})
        if not status.get('ready'):
            self.scripting_dead = 'the application did not start in a fresh instance: '+str(status.get('detail'))
            raise MissingDependency(self.scripting_dead)
        try:
            tracks = self.info('Tracks')
        except AssertionError as exc:
            self.scripting_dead = 'no working scripting endpoint in a fresh instance: '+str(exc)
            raise MissingDependency(self.scripting_dead) from None
        assert tracks == [], 'a fresh instance does not start with an empty project'

    def reset(self):
        """Scenario boundary: remove all tracks through product commands; a fresh instance when that fails."""
        self.state.clear()
        try:
            self.command('Stop')
            self.require('SelectAll')
            # Unicode metadata may be unreadable in the real 2.4.2 pipe. Remove selected tracks before observing
            # names; on an empty project the disabled command may fail, and the empty postcondition decides.
            self.command('RemoveTracks')
            self.require('SetProject', Rate=44100)
            assert self.info('Tracks') == [], 'scenario reset retained tracks'
        except MissingDependency:
            raise
        except AssertionError as exc:
            # Leftovers of an earlier scenario or a missing helper command never decide later scenarios.
            self.fresh(str(exc))

    def new_scenario(self, name):
        self.reset()
        self.state['scenario'] = name

    # -- product files -----------------------------------------------------------------------------------------
    def export_audio(self, channels=1, extension='wav'):
        self.serial += 1
        name = f'output-{self.serial:05d}.{extension}'
        response = self.command('Export2', Filename=name, NumChannels=channels)
        assert response['ok'], 'product export failed'
        data = self.take(name, response.get('downloads'))
        path = self.scratch/'exports'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if self.last_export is not None and self.last_export != path:
            self.last_export.unlink(missing_ok=True)
        self.last_export = path
        self.last_audio = decode_audio(path)
        self.audit_artifact(path, self.last_audio)
        observation = audio_observe(self.last_audio)
        # Header bytes and file tags never enter audio truth.
        observation.pop('decoded_pcm_sha256', None)
        observation.pop('tags', None)
        return observation

    def audit_artifact(self, path, audio):
        path = Path(path)
        assert path.is_file() and audio.frames >= 0 and audio.channels > 0 and audio.sample_rate > 0
        with (self.out/'artifacts.jsonl').open('a') as stream:
            stream.write(json.dumps({'case': self.current_case, 'file': path.name,
                                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'decoded': True,
                                     'frames': audio.frames, 'sample_rate': audio.sample_rate,
                                     'channels': audio.channels})+'\n')

    # -- desktop -----------------------------------------------------------------------------------------------
    def observe(self):
        try:
            return self.call({'op': 'observe'})
        except BrokerError as exc:
            raise AssertionError('the desktop could not be observed: '+exc.detail[:300]) from None

    def visible_texts(self):
        return [text for text in strings(self.observe()) if text]

    def window_titles(self):
        try:
            windows = self.call({'op': 'windows'}).get('windows', [])
        except BrokerError as exc:
            raise AssertionError('the desktop windows could not be listed: '+exc.detail[:300]) from None
        return [str(w.get('title', '')) for w in windows]

    def imported_name(self, name):
        # The public UTF-8 name may be in a track control, editable field or window title. Do not request the
        # upstream's corrupt Unicode JSON.
        stem = Path(self.fixture_name(name)).stem
        if not any(stem in text for text in self.visible_texts()):
            tracks = self.info('Tracks')
            assert isinstance(tracks, list) and any(isinstance(track, dict) and stem in str(track.get('name', ''))
                                                    for track in tracks), \
                'imported filename is absent from public track metadata and the accessible desktop'
        return stem

    def close(self):
        self.flush()
        shutil.rmtree(self.scratch, ignore_errors=True)


def compare(actual, expected):
    """Documented tolerance: counts, strings and shapes exact; floats abs 1.5 LSB (1.5/32768) or rel 5e-4;
    zero-crossing counts within 2; Repair samples within their declared reconstruction bound."""
    tolerances = {}

    def adjust(got, wanted, path='$'):
        if isinstance(wanted, dict) and isinstance(got, dict):
            for key in wanted.keys() & got.keys():
                if key == 'repair_samples':
                    left, right = got[key], wanted[key]
                    assert isinstance(left, list) and len(left) == len(right) > 0, 'Repair sample shape differs'
                    assert all(type(v) in (int, float) and math.isfinite(v) for v in left), 'Repair samples must be finite'
                    rmse = math.sqrt(sum((a-b)**2 for a, b in zip(left, right))/len(right))
                    assert rmse <= 3/32768, 'Repair reconstruction differs from the reference PCM'
                    for i in range(len(right)):
                        tolerances[f'{path}.{key}[{i}]'] = (7/32768, 0)
                elif key == 'zero_crossings' and type(wanted[key]) is int and type(got[key]) is int \
                        and abs(got[key]-wanted[key]) <= 2:
                    got[key] = wanted[key]
                else:
                    adjust(got[key], wanted[key], f'{path}.{key}')
        elif isinstance(wanted, list) and isinstance(got, list):
            for i, (left, right) in enumerate(zip(got, wanted)):
                adjust(left, right, f'{path}[{i}]')
    actual = json.loads(json.dumps(actual))
    adjust(actual, expected)
    compare_observations(actual, expected, absolute=1.5/32768, relative=5e-4, tolerances=tolerances)


__all__ = ['Case', 'Context', 'MissingDependency', 'State', 'Suite', 'compare', 'fixture_store']
