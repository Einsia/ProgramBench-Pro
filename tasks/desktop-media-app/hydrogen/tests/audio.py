"""Verifier-made samples and the independent decoding and projection of rendered audio.

Samples are synthesized with NumPy and written as WAV by this module; other input formats are encoded from those
WAVs by the verifier's own FFmpeg. Rendered and exported files are decoded by FFmpeg/ffprobe into float64 frames;
projections reduce them to the values a point compares (format, frame count, per-channel levels in time windows,
onsets, dominant frequency, band energies, short excerpts), each with a declared tolerance.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from evaluation.contract import InfrastructureError

RATE = 44100
DECODE_SECONDS = 60


class DecodeFailure(AssertionError):
    """The artifact could not be decoded as audio (a candidate defect, the point fails)."""


# -- synthesis ---------------------------------------------------------------------------------------------------
def tone(freq, seconds, amp=0.5, rate=RATE, phase=0.0):
    t = np.arange(int(round(seconds * rate))) / rate
    return amp * np.sin(2 * np.pi * freq * t + phase)


def decaying(freq, seconds, amp=0.8, tau=0.08, rate=RATE):
    t = np.arange(int(round(seconds * rate))) / rate
    return amp * np.exp(-t / tau) * np.sin(2 * np.pi * freq * t)


def click(seconds=0.05, amp=0.9, rate=RATE):
    """A short burst with a sharp onset and a known decay: frame 0 is the loudest sample."""
    n = int(round(seconds * rate))
    t = np.arange(n) / rate
    return amp * np.exp(-t / 0.004) * np.cos(2 * np.pi * 1500 * t)


def noise(seconds, amp=0.4, seed=7, rate=RATE):
    rng = np.random.default_rng(seed)
    return amp * (rng.random(int(round(seconds * rate))) * 2 - 1)


def square(freq, seconds, amp=0.4, rate=RATE):
    t = np.arange(int(round(seconds * rate))) / rate
    return amp * np.sign(np.sin(2 * np.pi * freq * t + 1e-9))


def ramp(seconds, start=-0.5, end=0.5, rate=RATE):
    n = int(round(seconds * rate))
    return np.linspace(start, end, n, endpoint=False)


def constant(seconds, level=0.5, rate=RATE):
    return np.full(int(round(seconds * rate)), float(level))


def wav_bytes(channels, rate=RATE, bits=16, fmt='int'):
    """WAV of one or more equal-length channels (lists of float arrays), deterministic header."""
    data = np.stack([np.asarray(c, dtype=np.float64) for c in channels], axis=1)
    frames, count = data.shape
    if fmt == 'float':
        payload = data.astype('<f4').tobytes()
        format_tag, bits = 3, 32
    elif bits == 8:
        payload = (np.clip(np.round(data * 127 + 128), 0, 255)).astype(np.uint8).tobytes()
        format_tag = 1
    elif bits == 16:
        payload = np.clip(np.round(data * 32767), -32768, 32767).astype('<i2').tobytes()
        format_tag = 1
    elif bits == 24:
        ints = np.clip(np.round(data * 8388607), -8388608, 8388607).astype('<i4').reshape(-1)
        raw = ints.astype('<i4').tobytes()
        payload = b''.join(raw[i:i + 3] for i in range(0, len(raw), 4))
        format_tag = 1
    elif bits == 32:
        payload = np.clip(np.round(data * 2147483647), -2147483648, 2147483647).astype('<i4').tobytes()
        format_tag = 1
    else:
        raise ValueError('unsupported sample depth')
    block = count * bits // 8
    header = b'RIFF' + struct.pack('<I', 36 + len(payload)) + b'WAVE'
    header += b'fmt ' + struct.pack('<IHHIIHH', 16, format_tag, count, rate, rate * block, block, bits)
    header += b'data' + struct.pack('<I', len(payload))
    return header + payload


def encode(wav, suffix, extra=(), work=None):
    """Encode WAV bytes with the verifier's FFmpeg into another container (deterministic flags)."""
    directory = Path(tempfile.mkdtemp(prefix='enc-', dir=work or os.environ.get('TMPDIR')))
    try:
        source, target = directory / 'in.wav', directory / ('out' + suffix)
        source.write_bytes(wav)
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
                   '-map_metadata', '-1', '-fflags', '+bitexact', '-flags:a', '+bitexact', *extra, str(target)]
        done = subprocess.run(command, capture_output=True, timeout=60)
        if done.returncode != 0 or not target.is_file():
            raise InfrastructureError('the verifier could not encode a fixture: ' + done.stderr.decode()[-300:])
        return target.read_bytes()
    finally:
        for item in directory.iterdir():
            item.unlink()
        directory.rmdir()


# -- decoding ------------------------------------------------------------------------------------------------------
def probe(path):
    done = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                           'stream=codec_name,sample_rate,channels,sample_fmt,bits_per_sample,bits_per_raw_sample'
                           ':format=format_name', '-of', 'json', str(path)], capture_output=True, timeout=30)
    if done.returncode != 0:
        raise DecodeFailure('the file is not audio that FFmpeg can read')
    info = json.loads(done.stdout or b'{}')
    streams = [s for s in info.get('streams', []) if s.get('codec_name')]
    if not streams:
        raise DecodeFailure('the file holds no audio stream')
    stream = streams[0]
    bits = stream.get('bits_per_raw_sample') or stream.get('bits_per_sample') or 0
    return {'container': info.get('format', {}).get('format_name', ''), 'codec': stream.get('codec_name'),
            'rate': int(stream.get('sample_rate') or 0), 'channels': int(stream.get('channels') or 0),
            'sample_format': stream.get('sample_fmt'), 'bits': int(bits)}


def decode(path):
    """(info, frames as float64 array [n, channels]) of an audio file, decoded without resampling."""
    info = probe(path)
    if info['rate'] <= 0 or info['channels'] <= 0:
        raise DecodeFailure('the audio stream has no rate or channels')
    try:
        done = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-f', 'f64le', '-acodec',
                               'pcm_f64le', '-'], capture_output=True, timeout=DECODE_SECONDS)
    except subprocess.TimeoutExpired:
        raise DecodeFailure('decoding the file took too long') from None
    except FileNotFoundError:
        raise InfrastructureError('the verifier FFmpeg is missing') from None
    if done.returncode != 0:
        raise DecodeFailure('FFmpeg could not decode the file: ' + done.stderr.decode(errors='replace')[-200:])
    data = np.frombuffer(done.stdout, dtype='<f8')
    if data.size % info['channels']:
        raise DecodeFailure('decoded samples are not channel-aligned')
    frames = data.reshape(-1, info['channels'])
    if not np.all(np.isfinite(frames)):
        raise DecodeFailure('decoded audio holds non-finite samples')
    return info, frames


# -- projections -----------------------------------------------------------------------------------------------------
def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def windows(channel, size, limit=None):
    count = len(channel) // size if limit is None else min(limit, len(channel) // size)
    return [round(rms(channel[i * size:(i + 1) * size]), 5) for i in range(count)]


def onsets(channel, threshold=0.02, gap=2048):
    """Frames where the signal first exceeds the threshold after at least `gap` quiet frames."""
    loud = np.flatnonzero(np.abs(channel) > threshold)
    found, last = [], None
    for index in loud:
        if last is None or index - last > gap:
            found.append(int(index))
        last = index
    return found[:64]


def dominant(channel, rate, lo=40.0, hi=8000.0):
    """Frequency of the strongest spectral peak (Hann window, quadratic interpolation)."""
    if len(channel) < 1024:
        return 0.0
    x = channel[:min(len(channel), 65536)] * np.hanning(min(len(channel), 65536))
    spectrum = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1.0 / rate)
    band = (freqs >= lo) & (freqs <= hi)
    if not band.any() or spectrum[band].max() <= 1e-9:
        return 0.0
    index = int(np.flatnonzero(band)[np.argmax(spectrum[band])])
    if 0 < index < len(spectrum) - 1:
        a, b, c = spectrum[index - 1], spectrum[index], spectrum[index + 1]
        shift = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
        index = index + shift
    return round(float(index * rate / len(x)), 2)


def bands(channel, rate, edges=(0, 250, 500, 1000, 2000, 4000, 8000, 16000)):
    """Share of the signal energy in octave-like bands (sums to about 1 for a non-silent channel)."""
    if len(channel) < 256:
        return [0.0] * (len(edges) - 1)
    spectrum = np.abs(np.fft.rfft(channel[:min(len(channel), 262144)])) ** 2
    freqs = np.fft.rfftfreq(min(len(channel), 262144), 1.0 / rate)
    total = float(spectrum.sum()) or 1.0
    return [round(float(spectrum[(freqs >= lo) & (freqs < hi)].sum()) / total, 4)
            for lo, hi in zip(edges, edges[1:])]


def project(info, frames, spec):
    """The observation of one rendered file. spec selects the features: window (frames per RMS window, default
    1024), limit (windows), onsets (threshold), pitch (seconds range), bands, excerpt (start, count)."""
    rate, count = info['rate'], frames.shape[0]
    out = {'format': {'codec': info['codec'], 'container': info['container'].split(',')[0], 'rate': rate,
                      'channels': info['channels'], 'bits': info['bits']}, 'frames': count}
    size = spec.get('window', 1024)
    channels = [frames[:, c] for c in range(frames.shape[1])]
    out['peak'] = [round(float(np.max(np.abs(c))) if len(c) else 0.0, 5) for c in channels]
    out['rms'] = [round(rms(c), 5) for c in channels]
    out['windows'] = [windows(c, size, spec.get('limit')) for c in channels]
    if 'onsets' in spec:
        out['onsets'] = [onsets(c, spec['onsets']) for c in channels]
    if 'pitch' in spec:
        start, end = spec['pitch']
        out['pitch'] = [dominant(c[int(start * rate):int(end * rate)], rate) for c in channels]
    if spec.get('bands'):
        out['bands'] = [bands(c, rate) for c in channels]
    if 'excerpt' in spec:
        start, length = spec['excerpt']
        out['excerpt'] = [[round(float(v), 5) for v in c[start:start + length]] for c in channels]
    return out


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized_observation(info, frames):
    """Rate/depth-independent timing, envelope and spectrum for lossless exports and archived samples."""
    rate = 22050
    result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'f64le',
                             '-ar', str(info['rate']), '-ac', str(info['channels']), '-i', 'pipe:0',
                             '-ar', str(rate), '-f', 'f64le', 'pipe:1'],
                            input=np.asarray(frames, dtype='<f8').tobytes(), capture_output=True,
                            timeout=DECODE_SECONDS)
    if result.returncode:
        raise DecodeFailure('audio could not be resampled for content analysis')
    data = np.frombuffer(result.stdout, dtype='<f8').reshape(-1, info['channels'])
    observed = project(dict(info, rate=rate), data, {'window': 1103, 'onsets': 0.02, 'bands': True})
    observed['format'] = {k: observed['format'][k] for k in ('container', 'channels')}
    return {'kind': 'audio', 'observation': observed,
            'tolerance': {'frames': 1024, 'level': [0.012, 0.08], 'onsets': 220, 'bands': 0.05}}
