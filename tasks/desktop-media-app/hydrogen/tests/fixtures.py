"""Deterministic verifier fixtures: the sample library uploaded to the candidate and kept privately for checks.

Every sample is synthesized here (NumPy) and written as WAV; the other formats are encoded from those WAVs by the
verifier's own FFmpeg. The catalog is generated once per verifier run in its private temporary directory.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np

import audio

ROOT = Path(__file__).resolve().parent


def wav(*channels, rate=audio.RATE, bits=16, fmt='int'):
    return audio.wav_bytes(list(channels), rate=rate, bits=bits, fmt=fmt)


def library():
    """name -> bytes of every sample document the program and GUI episodes upload."""
    t = audio
    out = {
        'click.wav': wav(t.click()),
        'click-quiet.wav': wav(t.click(amp=0.3)),
        'tone220.wav': wav(t.tone(220, 0.5, 0.5)),
        'tone440.wav': wav(t.tone(440, 0.5, 0.5)),
        'tone660.wav': wav(t.tone(660, 0.5, 0.5)),
        'tone880.wav': wav(t.tone(880, 0.5, 0.5)),
        'long440.wav': wav(t.tone(440, 3.0, 0.5)),
        'decay330.wav': wav(t.decaying(330, 1.0, 0.8, 0.15)),
        'noise.wav': wav(t.noise(1.0, 0.5)),
        'square110.wav': wav(t.square(110, 1.0, 0.4)),
        'ramp.wav': wav(t.ramp(0.5)),
        'dc.wav': wav(t.constant(0.5, 0.5)),
        'stereo.wav': wav(t.tone(440, 0.5, 0.5), t.tone(660, 0.5, 0.3)),
        'tone440-48k.wav': wav(t.tone(440, 0.5, 0.5, rate=48000), rate=48000),
        'tone440-22k.wav': wav(t.tone(440, 0.5, 0.5, rate=22050), rate=22050),
        'tone440-96k.wav': wav(t.tone(440, 0.5, 0.5, rate=96000), rate=96000),
        'tone440-8bit.wav': wav(t.tone(440, 0.5, 0.5), bits=8),
        'tone440-24bit.wav': wav(t.tone(440, 0.5, 0.5), bits=24),
        'tone440-32bit.wav': wav(t.tone(440, 0.5, 0.5), bits=32),
        'tone440-float.wav': wav(t.tone(440, 0.5, 0.5), fmt='float'),
        'layer220.wav': wav(t.tone(220, 0.4, 0.6)),
        'layer330.wav': wav(t.tone(330, 0.4, 0.6)),
        'layer550.wav': wav(t.tone(550, 0.4, 0.6)),
        'layer770.wav': wav(t.tone(770, 0.4, 0.6)),
        'kick.wav': wav(t.decaying(60, 0.4, 0.9, 0.08)),
        'snare.wav': wav(t.noise(0.25, 0.6, seed=11) * np.exp(-np.arange(int(0.25 * audio.RATE)) / 3000)),
        'hat.wav': wav(t.noise(0.08, 0.4, seed=13) * np.exp(-np.arange(int(0.08 * audio.RATE)) / 600)),
        'pad.wav': wav(t.tone(330, 1.5, 0.4) + t.tone(495, 1.5, 0.2)),
    }
    base = out['tone440.wav']
    encoded = {'tone440.flac': ('.flac', ()), 'tone440.ogg': ('.ogg', ('-c:a', 'libvorbis', '-q:a', '6')),
               'tone440.aiff': ('.aiff', ()), 'tone440.au': ('.au', ()), 'tone440.caf': ('.caf', ()),
               'tone440.w64': ('.w64', ()), 'tone440.mp3': ('.mp3', ('-b:a', '192k'))}
    for name, (suffix, extra) in encoded.items():
        out[name] = audio.encode(base, suffix, extra)
    return out


def catalog():
    """(directory, names) of the generated sample library, built once per run in the private TMPDIR."""
    source = b''.join((ROOT / name).read_bytes() for name in ('fixtures.py', 'audio.py'))
    base = Path(os.environ.get('TMPDIR', '/tmp')) / ('hydrogen-fixtures-' + hashlib.sha256(source).hexdigest()[:16])
    if (base / 'catalog.json').is_file():
        return base, json.loads((base / 'catalog.json').read_text())
    base.parent.mkdir(parents=True, exist_ok=True)
    with open(str(base) + '.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not (base / 'catalog.json').is_file():
            work = Path(tempfile.mkdtemp(prefix='fixtures-', dir=base.parent))
            names = {}
            for name, data in library().items():
                (work / name).write_bytes(data)
                names[name] = hashlib.sha256(data).hexdigest()
            (work / 'catalog.json').write_text(json.dumps(names, sort_keys=True))
            shutil.rmtree(base, ignore_errors=True)
            work.rename(base)
    return base, json.loads((base / 'catalog.json').read_text())


def sample(name):
    base, names = catalog()
    if name not in names:
        raise KeyError('unknown verifier sample ' + name)
    return (base / name).read_bytes()
