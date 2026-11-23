"""Verifier-side harness: the candidate's OSC interface, command line, documents and desktop through the runtime.

Program episodes, public setup and the independent checks of GUI checkpoints reach the candidate only through the
task's runtime: osc (one OSC message and its feedback), cli (the product command line through start.sh), upload,
list_files and download (the document areas), settings (the settings file), observe, reset and restart. These are
the channels the model has on the reference. Nothing in this module is shown to the evaluator agent or the candidate.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import time

from evaluation.broker import BrokerError
from evaluation.contract import InfrastructureError
import audio
import songs

FILE_SECONDS = 12
RESET_SECONDS = 180


class MissingDependency(AssertionError):
    """A required earlier step of the same scenario did not complete."""


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
    """Ordered program operations; setup rows prepare, scored rows are program assertions."""

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

    def setup(self, family, scenario, action, description='', attached=False):
        return self.add(family, scenario, 'prepare', action, channel='setup',
                        description=description or 'Prepare ' + scenario, attached=attached)


class Context:
    """State shared by the program cases and the GUI setup/checks of one episode."""

    def __init__(self, broker, out, scratch):
        self.broker = broker
        self.out = Path(out)
        self.scratch = Path(scratch)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.state = State()
        self.current_case = ''
        self.raw = []
        self.uploaded = {}
        self.serial = 0
        self.successful = set()
        self._areas = None

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
                    stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
            self.raw = []

    def areas(self):
        """The runtime's document areas (public: help names them)."""
        if self._areas is None:
            notes = self.call({'op': 'help'}).get('notes', [])
            found = {}
            for note in notes:
                for name in ('inputs', 'outputs', 'projects'):
                    match = re.search(rf'\b{name} (/[^\s,]+)', note)
                    if match:
                        found[name] = match.group(1).rstrip('.')
            if set(found) != {'inputs', 'outputs', 'projects'}:
                raise InfrastructureError('the runtime help does not name its document areas')
            self._areas = found
        return self._areas

    def inputs(self, name=''):
        return self.areas()['inputs'] + ('/' + name if name else '')

    def places(self):
        root = str(Path(self.areas()['inputs']).parent)
        return songs.Places(root)

    # -- documents ----------------------------------------------------------------------------------------------
    def upload(self, filename, data):
        data = data.encode('utf-8') if isinstance(data, str) else data
        digest = hashlib.sha256(data).hexdigest()
        if self.uploaded.get(filename) == digest:
            return filename
        try:
            self.call({'op': 'upload', 'filename': filename, 'base64': base64.b64encode(data).decode()})
        except BrokerError as exc:
            raise InfrastructureError('the runtime refused a verifier document: ' + exc.detail) from None
        self.uploaded[filename] = digest
        self.trace({'upload': filename, 'size': len(data)})
        return filename

    def pending(self):
        return self.call({'op': 'list_files'}).get('downloads', [])

    def download(self, ref):
        got = self.call({'op': 'download', 'ref': ref})
        return base64.b64decode(got.get('body_base64', ''))

    def take(self, path, refs=(), wait=FILE_SECONDS):
        """Bytes of the newest product file at this document path (relative to the document root, for example
        outputs/x.wav), once it stopped changing; AssertionError when it never appears."""
        deadline = time.monotonic() + wait
        data = None
        refs = [r for r in refs or () if r.get('path') == path]
        while True:
            if not refs:
                refs = [r for r in self.pending() if r.get('path') == path]
            if refs:
                for ref in refs:
                    data = self.download(ref['ref'])
                time.sleep(0.3)
                refs = [r for r in self.pending() if r.get('path') == path]
                if not refs:
                    return data
                continue
            if data is not None:
                return data
            if time.monotonic() >= deadline:
                raise AssertionError(f'expected file {path} was not written')
            time.sleep(0.25)

    def drain(self):
        """Forget pending downloads (files of earlier steps)."""
        for ref in self.pending():
            try:
                self.download(ref['ref'])
            except BrokerError:
                pass

    def unique(self, stem, suffix):
        self.serial += 1
        return f'{stem}-{self.serial:04d}{suffix}'

    # -- OSC and command line -----------------------------------------------------------------------------------
    def osc(self, address, *args, wait=0.4):
        try:
            reply = self.call({'op': 'osc', 'address': address, 'args': list(args), 'wait': wait})
        except BrokerError as exc:
            self.trace({'osc': address, 'args': list(args), 'error': exc.detail[:300]})
            raise AssertionError(f'OSC {address} was not delivered: {exc.detail[:300]}') from None
        feedback = reply.get('feedback', []) if isinstance(reply, dict) else []
        self.trace({'osc': address, 'args': list(args), 'feedback': len(feedback)})
        return feedback

    def cli(self, action, **fields):
        try:
            reply = self.call({'op': 'cli', 'action': action, **fields}, timeout=150)
        except BrokerError as exc:
            self.trace({'cli': action, 'fields': fields, 'error': exc.detail[:300]})
            raise AssertionError(f'the command line {action} did not run: {exc.detail[:300]}') from None
        if not isinstance(reply, dict) or not isinstance(reply.get('exit_code'), int):
            raise AssertionError('the command line returned no exit status')
        self.trace({'cli': action, 'fields': fields, 'exit_code': reply['exit_code'],
                    'downloads': [d.get('path') for d in reply.get('downloads', [])]})
        return reply

    def save_song(self, name=None):
        """The current song as the product saves it (OSC SAVE_SONG_AS into the output area)."""
        name = name or self.unique('state', '.h2song')
        self.osc('/Hydrogen/SAVE_SONG_AS', name, wait=0.3)
        return self.take('projects/' + name if '/' not in name else name)

    def song(self, name=None):
        return songs.song_projection(self.save_song(name), self.places())

    def open_song(self, filename):
        self.osc('/Hydrogen/OPEN_SONG', filename, wait=1.0)

    def settings(self):
        try:
            return self.call({'op': 'settings'}).get('body', '')
        except BrokerError as exc:
            raise AssertionError('the settings file is not available: ' + exc.detail[:200]) from None

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def restart(self):
        status = self.call({'op': 'restart'}, timeout=RESET_SECONDS)
        self.trace({'lifecycle': 'restart', 'ready': status.get('ready')})
        assert status.get('ready'), 'the application did not come back after a restart: ' + str(status.get('detail'))
        return status

    def fresh(self):
        """A fresh instance (runtime reset): new data, library, settings and document areas."""
        status = self.call({'op': 'reset'}, timeout=RESET_SECONDS)
        self.uploaded.clear()
        self.trace({'lifecycle': 'reset', 'ready': status.get('ready')})
        if not status.get('ready'):
            raise MissingDependency('the application did not start in a fresh instance: ' + str(status.get('detail')))
        return status

    # -- audio -------------------------------------------------------------------------------------------------
    def decode(self, data, name):
        path = self.scratch / 'audio' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        try:
            return audio.decode(path)
        finally:
            path.unlink(missing_ok=True)

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


# -- comparison ------------------------------------------------------------------------------------------------------
AUDIO_DEFAULT = {'frames': 1024, 'level': (0.004, 0.03), 'onsets': 3, 'pitch': 0.01, 'bands': 0.03, 'excerpt': 0.003}


def close(actual, expected, absolute, relative):
    return math.isclose(actual, expected, abs_tol=absolute, rel_tol=relative)


def compare_audio(actual, expected, tolerance, path):
    tol = dict(AUDIO_DEFAULT, **(tolerance or {}))
    assert isinstance(actual, dict), f'{path}: expected an audio observation'
    assert actual.get('format') == expected['format'], \
        f'{path}.format: {actual.get("format")} differs from {expected["format"]}'
    assert abs(int(actual.get('frames', -1)) - expected['frames']) <= tol['frames'], \
        f'{path}.frames: {actual.get("frames")} differs from {expected["frames"]} by more than {tol["frames"]}'
    absolute, relative = tol['level']
    for key in ('peak', 'rms'):
        got, want = actual.get(key), expected[key]
        assert isinstance(got, list) and len(got) == len(want), f'{path}.{key}: channel count differs'
        for index, (a, b) in enumerate(zip(got, want)):
            assert close(a, b, absolute, relative), f'{path}.{key}[{index}]: {a} differs from {b}'
    got, want = actual.get('windows'), expected['windows']
    assert isinstance(got, list) and len(got) == len(want), f'{path}.windows: channel count differs'
    for channel, (a, b) in enumerate(zip(got, want)):
        slack = tol['frames'] // 512 + 2
        assert abs(len(a) - len(b)) <= slack, f'{path}.windows[{channel}]: length differs'
        for index, (x, y) in enumerate(zip(a, b)):
            assert close(x, y, absolute, relative), \
                f'{path}.windows[{channel}][{index}]: level {x} differs from {y} (abs {absolute}, rel {relative})'
    if 'onsets' in expected:
        got, want = actual.get('onsets'), expected['onsets']
        for channel, (a, b) in enumerate(zip(got or [], want)):
            assert len(a) == len(b), f'{path}.onsets[{channel}]: {len(a)} onsets instead of {len(b)}'
            for x, y in zip(a, b):
                assert abs(x - y) <= tol['onsets'], f'{path}.onsets[{channel}]: onset {x} differs from {y}'
    if 'pitch' in expected:
        for channel, (a, b) in enumerate(zip(actual.get('pitch') or [], expected['pitch'])):
            assert close(a, b, 0.5, tol['pitch']), f'{path}.pitch[{channel}]: {a} Hz differs from {b} Hz'
    if 'bands' in expected:
        for channel, (a, b) in enumerate(zip(actual.get('bands') or [], expected['bands'])):
            for band, (x, y) in enumerate(zip(a, b)):
                assert abs(x - y) <= tol['bands'], f'{path}.bands[{channel}][{band}]: {x} differs from {y}'
    if 'excerpt' in expected:
        for channel, (a, b) in enumerate(zip(actual.get('excerpt') or [], expected['excerpt'])):
            assert len(a) == len(b), f'{path}.excerpt[{channel}]: length differs'
            worst = max((abs(x - y) for x, y in zip(a, b)), default=0.0)
            assert worst <= tol['excerpt'], f'{path}.excerpt[{channel}]: samples differ by {worst:.5f}'


def compare_values(actual, expected, path='$', absolute=1e-4, relative=1e-4):
    if isinstance(expected, dict):
        if expected.get('kind') == 'audio' and 'observation' in expected:
            assert isinstance(actual, dict) and actual.get('kind') == 'audio', f'{path}: expected audio'
            compare_audio(actual.get('observation'), expected['observation'], expected.get('tolerance'), path)
            return
        assert isinstance(actual, dict), f'{path}: expected an object, got {type(actual).__name__}'
        assert set(actual) == set(expected), f'{path}: fields {sorted(actual)} differ from {sorted(expected)}'
        for key in expected:
            compare_values(actual[key], expected[key], f'{path}.{key}', absolute, relative)
        return
    if isinstance(expected, list):
        assert isinstance(actual, list), f'{path}: expected a list'
        assert len(actual) == len(expected), f'{path}: {len(actual)} items instead of {len(expected)}'
        for index, (a, b) in enumerate(zip(actual, expected)):
            compare_values(a, b, f'{path}[{index}]', absolute, relative)
        return
    if isinstance(expected, float) and not isinstance(expected, bool):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool), f'{path}: expected a number'
        assert close(float(actual), expected, absolute, relative), f'{path}: {actual} differs from {expected}'
        return
    if isinstance(expected, int) and not isinstance(expected, bool) and isinstance(actual, float):
        assert actual == expected, f'{path}: {actual} differs from {expected}'
        return
    assert actual == expected, f'{path}: {actual!r} differs from {expected!r}'


def compare(actual, expected):
    """Exact shapes and texts; numbers of documents within 1e-4; audio observations within their declared
    tolerances (format exact, frame count, levels per window, onsets, pitch, band shares, excerpts)."""
    if isinstance(expected, dict) and 'tolerance' in expected and 'value' in expected and set(expected) == {'value', 'tolerance'}:
        assert isinstance(actual, dict) and 'value' in actual, '$: expected a tolerant observation'
        tolerance = expected['tolerance']
        compare_values(actual['value'], expected['value'], '$', tolerance.get('abs', 1e-4), tolerance.get('rel', 1e-4))
        return
    compare_values(actual, expected)


def audio_observation(info, frames, spec=None, tolerance=None):
    value = {'kind': 'audio', 'observation': audio.project(info, frames, spec or {})}
    if tolerance:
        value['tolerance'] = tolerance
    return value


__all__ = ['Case', 'Context', 'MissingDependency', 'State', 'Suite', 'compare', 'audio_observation']
