"""Deterministic audio fixtures for the LMMS black-box benchmark.

Fixtures are generated from signal parameters, rather than checked-in binary
files. PCM fixtures do not need third-party packages. Encoded inputs use the
pinned image's FFmpeg and explicitly disable timestamp/tag metadata; their
semantic decoded samples, not container bytes, should be compared by tests.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import wave
from typing import Mapping, Sequence


DEFAULT_RATE = 44_100
DEFAULT_WIDTH = 2
_MAX_FRAMES = 5_760_000  # 30 seconds at 192 kHz, a bounded local fixture.


@dataclasses.dataclass(frozen=True)
class Signal:
    """One deterministic signal per channel.

    Frequencies are Hz; amplitude/DC offset are normalised to full scale.
    ``segments`` uses (seconds, waveform, frequency, amplitude) tuples. A
    stereo fixture may use different Signal objects so channel loss, swapping
    and mono downmixes cannot accidentally pass an import/export assertion.
    """

    waveform: str = "sine"
    frequency: float = 440.0
    end_frequency: float = 880.0
    amplitude: float = 0.375
    offset: float = 0.0
    phase: float = 0.0
    seed: int = 1729
    segments: tuple[tuple[float, str, float, float], ...] = ()

    def samples(self, frames: int, rate: int) -> list[float]:
        return signal_samples(self, frames, rate)


@dataclasses.dataclass(frozen=True)
class FixtureSpec:
    """Semantic input variant independent of a verifier's case IDs."""

    key: str
    filename: str
    rate: int = DEFAULT_RATE
    frames: int = DEFAULT_RATE
    signals: tuple[Signal, ...] = (Signal(),)
    width: int = DEFAULT_WIDTH
    sample_format: str = "pcm"
    metadata: tuple[tuple[str, str], ...] = ()
    encoding: str = "wav"
    invalid: str | None = None

    @property
    def channels(self) -> int:
        return len(self.signals)

    def describe(self) -> dict[str, object]:
        return {
            "key": self.key,
            "filename": self.filename,
            "sample_rate": self.rate,
            "channels": self.channels,
            "frames": self.frames,
            "duration_ms": round(self.frames * 1000 / self.rate),
            "sample_width": self.width,
            "sample_format": self.sample_format,
            "waveforms": [signal.waveform for signal in self.signals],
            "encoding": self.encoding,
            "invalid": self.invalid,
        }


def _check_shape(frames: int, rate: int, channels: int) -> None:
    if type(frames) is not int or not 0 <= frames <= _MAX_FRAMES:
        raise ValueError("frames must be a bounded non-negative integer")
    if type(rate) is not int or not 8_000 <= rate <= 192_000:
        raise ValueError("rate is outside the supported fixture range")
    if type(channels) is not int or not 1 <= channels <= 8:
        raise ValueError("channels must be between 1 and 8")


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _clip(value: float, width: int = DEFAULT_WIDTH) -> int:
    limit = 1 << (8 * width - 1)
    return max(-limit, min(limit - 1, int(round(value))))


def signal_samples(spec: Signal, frames: int, rate: int) -> list[float]:
    """Generate one channel as normalised floats; no global RNG is used."""
    _check_shape(frames, rate, 1)
    amplitude = _finite(spec.amplitude, "amplitude")
    offset = _finite(spec.offset, "offset")
    frequency = _finite(spec.frequency, "frequency")
    end_frequency = _finite(spec.end_frequency, "end_frequency")
    phase = _finite(spec.phase, "phase")
    if spec.waveform not in {"sine", "square", "triangle", "saw", "silence", "dc", "noise", "impulse", "ramp", "chirp", "segments"}:
        raise ValueError(f"unknown fixture waveform {spec.waveform!r}")
    if spec.waveform in {"sine", "square", "triangle", "saw", "chirp"} and not (0 <= frequency < rate / 2 and 0 <= end_frequency < rate / 2):
        raise ValueError("fixture frequency must be below Nyquist")
    if spec.waveform == "segments":
        result: list[float] = []
        for duration, waveform, freq, amp in spec.segments:
            count = round(_finite(duration, "segment duration") * rate)
            if count < 0:
                raise ValueError("segment duration must not be negative")
            child = Signal(waveform=waveform, frequency=freq, amplitude=amp, seed=spec.seed)
            result.extend(signal_samples(child, min(count, max(0, frames - len(result))), rate))
            if len(result) >= frames:
                break
        return result + [offset] * (frames - len(result))
    rng = random.Random(spec.seed)
    duration = frames / rate if frames else 0.0
    result = []
    for index in range(frames):
        cycles = frequency * index / rate + phase / (2 * math.pi)
        if spec.waveform == "sine":
            value = math.sin(2 * math.pi * cycles)
        elif spec.waveform == "square":
            value = 1.0 if math.sin(2 * math.pi * cycles) >= 0 else -1.0
        elif spec.waveform == "triangle":
            value = 1.0 - 4.0 * abs((cycles % 1.0) - 0.5)
        elif spec.waveform == "saw":
            value = 2.0 * (cycles % 1.0) - 1.0
        elif spec.waveform in {"silence", "dc"}:
            value = 0.0
        elif spec.waveform == "noise":
            value = rng.uniform(-1.0, 1.0)
        elif spec.waveform == "impulse":
            value = 1.0 if index == min(frames - 1, int(frequency)) else 0.0
        elif spec.waveform == "ramp":
            value = -1.0 + 2.0 * index / max(1, frames - 1)
        elif spec.waveform == "chirp":
            at = index / rate
            phase_cycles = frequency * at + 0.5 * (end_frequency - frequency) * at * at / max(duration, 1 / rate)
            value = math.sin(2 * math.pi * phase_cycles + phase)
        else:  # Validated above; guards future waveform additions.
            raise ValueError(f"unimplemented fixture waveform {spec.waveform!r}")
        result.append(offset + amplitude * value)
    return result


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return kind + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) % 2 else b"")


def write_audio(
    path: str | Path,
    rate: int,
    channels: Sequence[Sequence[float]],
    *,
    width: int = DEFAULT_WIDTH,
    sample_format: str = "pcm",
    metadata: Mapping[str, str] | None = None,
) -> Path:
    """Write RIFF/WAVE PCM8/16/24/32 or IEEE float32 from normalised samples.

    Channel samples are not silently downmixed. ``metadata`` stores UTF-8 LIST
    INFO chunks so metadata preservation can be assessed independently of
    audio. Float fixtures use a standard IEEE-float fmt and fact chunk.
    """
    count = len(channels)
    frames = len(channels[0]) if count else 0
    _check_shape(frames, rate, count)
    if any(len(track) != frames for track in channels):
        raise ValueError("all channels must have the same frame count")
    if width not in {1, 2, 3, 4}:
        raise ValueError("PCM width must be 1, 2, 3 or 4 bytes")
    if sample_format not in {"pcm", "float"} or (sample_format == "float" and width != 4):
        raise ValueError("sample_format must be pcm or 32-bit float")
    payload = bytearray()
    scale = 1 << (8 * width - 1)
    for index in range(frames):
        for track in channels:
            value = _finite(track[index], "sample")
            if sample_format == "float":
                payload.extend(struct.pack("<f", value))
            else:
                integer = _clip(value * scale, width)
                if width == 1:
                    payload.append(integer + 128)
                else:
                    payload.extend(integer.to_bytes(width, "little", signed=True))
    format_tag = 3 if sample_format == "float" else 1
    align = count * width
    fmt = struct.pack("<HHIIHH", format_tag, count, rate, rate * align, align, width * 8)
    chunks = [_chunk(b"fmt ", fmt)]
    if sample_format == "float":
        chunks.append(_chunk(b"fact", struct.pack("<I", frames)))
    info = bytearray(b"INFO")
    tags = {"artist": "IART", "title": "INAM", "album": "IPRD", "year": "ICRD", "genre": "IGNR", "comment": "ICMT"}
    for key, text in (metadata or {}).items():
        tag = tags.get(key, key if len(key) == 4 else None)
        if tag is None or not isinstance(text, str):
            raise ValueError("WAV metadata key/text is invalid")
        info.extend(_chunk(tag.encode("ascii"), text.encode("utf-8") + b"\0"))
    if len(info) > 4:
        chunks.append(_chunk(b"LIST", bytes(info)))
    chunks.append(_chunk(b"data", bytes(payload)))
    body = b"WAVE" + b"".join(chunks)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    return destination


def write_pcm(path: str | Path, channels: int, rate: int, samples: list[list[int]] | list[int], *, width: int = DEFAULT_WIDTH) -> Path:
    """Compatibility helper accepting signed integer samples per channel."""
    if channels == 1 and (not samples or isinstance(samples[0], int)):
        tracks = [list(samples)]
    else:
        tracks = [list(track) for track in samples]  # type: ignore[arg-type]
        if len(tracks) != channels:
            raise ValueError("one sample list is required per channel")
    scale = 1 << (8 * width - 1)
    normalised = [[_clip(value, width) / scale for value in track] for track in tracks]
    return write_audio(path, rate, normalised, width=width)


def tone(path: str | Path, *, frequency: float = 440.0, duration_ms: int = 1_000, rate: int = DEFAULT_RATE, amplitude: int = 12_000) -> Path:
    frames = max(0, int(round(rate * max(0, duration_ms) / 1_000)))
    # Keep these PCM values bit-identical; the general Signal API uses round
    # when converting normalised floats, while this fixture uses int.
    values = [int(amplitude * math.sin(2 * math.pi * frequency * index / rate)) for index in range(frames)]
    return write_pcm(path, 1, rate, values)


def silence(path: str | Path, *, duration_ms: int = 500, rate: int = DEFAULT_RATE) -> Path:
    frames = max(0, int(round(rate * max(0, duration_ms) / 1_000)))
    return write_pcm(path, 1, rate, [0] * frames)


def stereo_pair(path: str | Path, *, duration_ms: int = 1_000, rate: int = DEFAULT_RATE) -> Path:
    frames = max(0, int(round(rate * max(0, duration_ms) / 1_000)))
    left = [int(10_000 * math.sin(2 * math.pi * 440 * index / rate)) for index in range(frames)]
    right = [int(8_000 * math.sin(2 * math.pi * 880 * index / rate)) for index in range(frames)]
    return write_pcm(path, 2, rate, [left, right])


def impulse(path: str | Path, *, frames: int = 44_100, rate: int = DEFAULT_RATE) -> Path:
    values = [0] * max(0, int(frames))
    if values:
        values[0] = 16_000
    return write_pcm(path, 1, rate, values)


def ramp(path: str | Path, *, frames: int = 44_100, rate: int = DEFAULT_RATE) -> Path:
    count = max(0, int(frames))
    values = [_clip(-16_000 + (32_000 * index / max(1, count - 1))) for index in range(count)]
    return write_pcm(path, 1, rate, values)


def read_audio(path: str | Path) -> tuple[int, list[list[float]], dict[str, object]]:
    """Read generated PCM/float WAV without relying on Python wave support."""
    raw = Path(path).read_bytes()
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("fixture is not RIFF/WAVE")
    if struct.unpack_from("<I", raw, 4)[0] + 8 != len(raw):
        raise ValueError("fixture RIFF length is inconsistent")
    fmt = None
    data = None
    metadata: dict[str, str] = {}
    position = 12
    while position + 8 <= len(raw):
        kind = raw[position : position + 4]
        length = struct.unpack_from("<I", raw, position + 4)[0]
        begin = position + 8
        chunk = raw[begin : begin + length]
        if len(chunk) != length:
            raise ValueError("fixture chunk is truncated")
        if kind == b"fmt ":
            if length < 16:
                raise ValueError("fixture fmt is truncated")
            fmt = struct.unpack_from("<HHIIHH", chunk, 0)
        elif kind == b"data":
            data = chunk
        elif kind == b"LIST" and chunk[:4] == b"INFO":
            info_position = 4
            while info_position + 8 <= len(chunk):
                tag = chunk[info_position : info_position + 4].decode("ascii")
                tag_length = struct.unpack_from("<I", chunk, info_position + 4)[0]
                value = chunk[info_position + 8 : info_position + 8 + tag_length]
                metadata[tag] = value.rstrip(b"\0").decode("utf-8", errors="replace")
                info_position += 8 + tag_length + (tag_length % 2)
        position = begin + length + (length % 2)
    if fmt is None or data is None:
        raise ValueError("fixture is missing fmt or data")
    format_tag, channels, rate, byte_rate, align, bits = fmt
    width = bits // 8
    if channels < 1 or rate < 1 or align < 1:
        raise ValueError("fixture WAV channel/rate/alignment is invalid")
    if format_tag not in {1, 3} or width not in {1, 2, 3, 4} or align != channels * width or byte_rate != rate * align or len(data) % align:
        raise ValueError("fixture WAV format/alignment is invalid")
    if format_tag == 3 and width != 4:
        raise ValueError("only IEEE float32 fixture WAV is supported")
    frames = len(data) // align
    tracks: list[list[float]] = [[] for _ in range(channels)]
    scale = 1 << (bits - 1)
    for frame in range(frames):
        for channel in range(channels):
            at = (frame * channels + channel) * width
            part = data[at : at + width]
            if format_tag == 3:
                value = struct.unpack("<f", part)[0]
            elif width == 1:
                value = (part[0] - 128) / scale
            else:
                value = int.from_bytes(part, "little", signed=True) / scale
            tracks[channel].append(value)
    details = {"sample_format": "float" if format_tag == 3 else "pcm", "sample_width": width, "metadata": metadata, "pcm_sha256": hashlib.sha256(data).hexdigest()}
    return rate, tracks, details


def observe(path: str | Path) -> dict[str, object]:
    """Return semantic metadata for generated PCM/IEEE-float fixtures."""
    rate, channels, details = read_audio(path)
    frames = len(channels[0]) if channels else 0
    values = [value for track in channels for value in track]
    width = int(details["sample_width"])
    peak = max((abs(value) for value in values), default=0.0)
    # Preserve the original interface's integer peak for signed-16 samples.
    integer_peak = int(round(peak * (1 << (width * 8 - 1)))) if details["sample_format"] == "pcm" else peak
    return {
        "format": "wav",
        "channels": len(channels),
        "sample_width": width,
        "sample_format": details["sample_format"],
        "sample_rate": rate,
        "frames": frames,
        "duration_ms": round(frames * 1000 / max(1, rate)),
        "pcm_sha256": details["pcm_sha256"],
        "peak": integer_peak,
        "non_silent": peak > 0.0,
        "metadata": details["metadata"],
    }


ENCODERS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "aiff": ("aiff", "pcm_s16be", ()),
    "flac": ("flac", "flac", ("-compression_level", "5")),
    "ogg": ("ogg", "libvorbis", ("-q:a", "4")),
    "mp3": ("mp3", "libmp3lame", ("-b:a", "128k", "-write_xing", "1")),
    "mp3-vbr": ("mp3", "libmp3lame", ("-q:a", "3", "-write_xing", "1")),
    "caf": ("caf", "pcm_s16le", ()),
    "raw": ("s16le", "pcm_s16le", ()),
}


def encode(source: str | Path, destination: str | Path, encoding: str, *, ffmpeg: str = "ffmpeg") -> Path:
    """Encode a bounded fixture with fixed parameters and no source tags."""
    if encoding not in ENCODERS:
        raise ValueError(f"unsupported fixture encoding {encoding!r}")
    binary = shutil.which(ffmpeg)
    if not binary:
        raise RuntimeError("FFmpeg is required to generate encoded fixtures")
    muxer, codec, options = ENCODERS[encoding]
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [binary, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact", "-threads", "1", "-c:a", codec, *options, "-f", muxer, str(target)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError("fixture encoding failed: " + result.stderr[-600:])
    return target


def decode_pcm(path: str | Path, *, rate: int = DEFAULT_RATE, channels: int = 1, raw: bool = False, ffmpeg: str = "ffmpeg") -> bytes:
    """Decode an encoded fixture to signed-16 PCM using fixed local options.

    Raw inputs intentionally carry no header and need the explicit rate and
    channel count from their FixtureSpec. Other inputs are decoded to that
    same shape, making lossless import fidelity independently inspectable.
    """
    _check_shape(0, rate, channels)
    binary = shutil.which(ffmpeg)
    if not binary:
        raise RuntimeError("FFmpeg is required to decode encoded fixtures")
    input_options = ["-f", "s16le", "-ar", str(rate), "-ac", str(channels)] if raw else []
    command = [binary, "-nostdin", "-hide_banner", "-loglevel", "error", *input_options, "-i", str(path), "-map_metadata", "-1", "-threads", "1", "-ac", str(channels), "-ar", str(rate), "-c:a", "pcm_s16le", "-f", "s16le", "-"]
    result = subprocess.run(command, capture_output=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError("fixture decoding failed: " + result.stderr.decode(errors="replace")[-600:])
    if len(result.stdout) % (channels * 2):
        raise ValueError("decoded fixture PCM is not frame aligned")
    return result.stdout


def write_fixture(spec: FixtureSpec, directory: str | Path, *, ffmpeg: str = "ffmpeg") -> Path:
    """Generate one parameterised fixture, optionally encoding/corrupting it."""
    filename = Path(spec.filename)
    if filename.name != spec.filename or spec.filename in {".", ".."}:
        raise ValueError("fixture filename must be a basename")
    _check_shape(spec.frames, spec.rate, spec.channels)
    target = Path(directory) / spec.filename
    if spec.invalid == "empty":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")
        return target
    if spec.invalid == "not-audio":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"This file is plain text, not an audio container.\n")
        return target
    channels = [signal.samples(spec.frames, spec.rate) for signal in spec.signals]
    if spec.encoding == "wav":
        write_audio(target, spec.rate, channels, width=spec.width, sample_format=spec.sample_format, metadata=dict(spec.metadata))
    else:
        with tempfile.TemporaryDirectory(prefix="lmms-fixture-") as temp:
            source = Path(temp) / "source.wav"
            write_audio(source, spec.rate, channels, width=spec.width, sample_format=spec.sample_format, metadata=dict(spec.metadata))
            encode(source, target, spec.encoding, ffmpeg=ffmpeg)
    if spec.invalid:
        raw = target.read_bytes()
        if spec.invalid == "truncated-header":
            raw = raw[:20]
        elif spec.invalid == "truncated-data":
            raw = raw[:-min(100, len(raw) // 2)]
        elif spec.invalid == "bad-riff-size":
            raw = raw[:4] + struct.pack("<I", 0x7FFFFFFF) + raw[8:]
        elif spec.invalid == "zero-channels":
            raw = raw[:22] + b"\0\0" + raw[24:]
        elif spec.invalid == "bad-format":
            raw = raw[:20] + b"\xff\xff" + raw[22:]
        else:
            raise ValueError(f"unknown invalid fixture class {spec.invalid!r}")
        target.write_bytes(raw)
    return target


def pcm_catalog() -> tuple[FixtureSpec, ...]:
    """Independent format, channel and content variants for editing scenarios."""
    sine = Signal()
    stereo = (Signal(frequency=440, amplitude=0.3), Signal(frequency=880, amplitude=0.2))
    segments = Signal(waveform="segments", segments=((0.25, "sine", 440, 0.35), (0.125, "silence", 0, 0), (0.375, "sine", 880, 0.25), (0.25, "square", 220, 0.2)))
    return (
        FixtureSpec("tone-440", "tone-440.wav", signals=(sine,)),
        FixtureSpec("tone-880", "tone-880.wav", signals=(Signal(frequency=880),)),
        FixtureSpec("stereo-pair", "stereo-pair.wav", signals=stereo),
        FixtureSpec("silence", "silence.wav", signals=(Signal(waveform="silence", amplitude=0),)),
        FixtureSpec("impulse", "impulse.wav", signals=(Signal(waveform="impulse", frequency=100, amplitude=0.5),)),
        FixtureSpec("square", "square.wav", signals=(Signal(waveform="square", frequency=220, amplitude=0.25),)),
        FixtureSpec("triangle", "triangle.wav", signals=(Signal(waveform="triangle", frequency=220, amplitude=0.3),)),
        FixtureSpec("saw", "saw.wav", signals=(Signal(waveform="saw", frequency=110, amplitude=0.25),)),
        FixtureSpec("dc-positive", "dc-positive.wav", signals=(Signal(waveform="dc", amplitude=0, offset=0.125),)),
        FixtureSpec("dc-negative", "dc-negative.wav", signals=(Signal(waveform="dc", amplitude=0, offset=-0.125),)),
        FixtureSpec("noise", "noise.wav", signals=(Signal(waveform="noise", amplitude=0.2, seed=1729),)),
        FixtureSpec("chirp", "chirp.wav", signals=(Signal(waveform="chirp", frequency=100, end_frequency=2000),)),
        FixtureSpec("segments", "segments.wav", signals=(segments,)),
        FixtureSpec("ramp", "ramp.wav", signals=(Signal(waveform="ramp", amplitude=0.5),)),
        FixtureSpec("pcm8", "pcm8.wav", width=1),
        FixtureSpec("pcm24", "pcm24.wav", width=3),
        FixtureSpec("pcm32", "pcm32.wav", width=4),
        FixtureSpec("float32", "float32.wav", width=4, sample_format="float"),
        FixtureSpec("rate-8000", "rate-8000.wav", rate=8000, frames=8000),
        FixtureSpec("rate-22050", "rate-22050.wav", rate=22050, frames=22050),
        FixtureSpec("rate-48000", "rate-48000.wav", rate=48000, frames=48000),
        FixtureSpec("rate-96000", "rate-96000.wav", rate=96000, frames=96000),
        FixtureSpec("short", "short.wav", frames=441),
        FixtureSpec("single-frame", "single-frame.wav", frames=1),
        FixtureSpec("empty-wave", "empty-wave.wav", frames=0),
        FixtureSpec("long", "long.wav", rate=16000, frames=160000),
        FixtureSpec("four-channel", "four-channel.wav", frames=22050, signals=tuple(Signal(frequency=freq, amplitude=0.1 + index * 0.04) for index, freq in enumerate((220, 440, 660, 880)))),
        FixtureSpec("eight-channel", "eight-channel.wav", frames=11025, signals=tuple(Signal(frequency=220 + index * 110, amplitude=0.1 + index * 0.02) for index in range(8))),
        FixtureSpec("unicode-name", "剪辑 空间.wav", signals=(segments,)),
        FixtureSpec("wav-info", "wav-info.wav", metadata=(("artist", "Program Bench"), ("title", "音频 metadata"), ("comment", "Deterministic fixture"))),
    )


def encoded_catalog() -> tuple[FixtureSpec, ...]:
    extensions = {"aiff": "aiff", "flac": "flac", "ogg": "ogg", "mp3": "mp3", "mp3-vbr": "mp3", "caf": "caf", "raw": "raw"}
    return tuple(FixtureSpec("encoded-" + key, "encoded-" + key + "." + extension, encoding=key) for key, extension in extensions.items())


def invalid_catalog() -> tuple[FixtureSpec, ...]:
    return tuple(FixtureSpec("invalid-" + kind, "invalid-" + kind + ".wav", invalid=kind, frames=1000) for kind in ("empty", "not-audio", "truncated-header", "truncated-data", "bad-riff-size", "zero-channels", "bad-format"))


def generate_catalog(directory: str | Path, *, encoded: bool = False, invalid: bool = True) -> dict[str, Path]:
    specs = list(pcm_catalog())
    if encoded:
        specs.extend(encoded_catalog())
    if invalid:
        specs.extend(invalid_catalog())
    return {spec.key: write_fixture(spec, directory) for spec in specs}


def generate_suite(directory: str | Path, *, encoded: bool = False, invalid: bool = False) -> dict[str, Path]:
    """Generate the public names->paths fixture suite with optional inputs.

    Short names remain available, and semantic variants keep distinct
    descriptive basenames. Use :func:`generate_catalog` when a harness wants
    semantic keys (``tone-440``) rather than literal names (``tone-440.wav``).
    No case IDs or test counts are embedded in either mapping.
    """
    root = Path(directory)
    result = {
        "tone-440-1s.wav": tone(root / "tone-440-1s.wav", frequency=440),
        "tone-880-1s.wav": tone(root / "tone-880-1s.wav", frequency=880),
        "silence-500ms.wav": silence(root / "silence-500ms.wav"),
        "stereo-pair-1s.wav": stereo_pair(root / "stereo-pair-1s.wav"),
        "impulse-1s.wav": impulse(root / "impulse-1s.wav"),
        "ramp-1s.wav": ramp(root / "ramp-1s.wav"),
    }
    result["tone.wav"] = tone(root / "tone.wav", frequency=440)
    for spec in pcm_catalog():
        result[spec.filename] = write_fixture(spec, root)
    if encoded:
        for spec in encoded_catalog():
            result[spec.filename] = write_fixture(spec, root)
    if invalid:
        for spec in invalid_catalog():
            result[spec.filename] = write_fixture(spec, root)
    return result


def selfcheck(directory: str | Path) -> dict[str, int]:
    """Check fixture format, determinism and signal properties independently."""
    root = Path(directory)
    checks = 0
    for spec in pcm_catalog():
        path = write_fixture(spec, root)
        metadata = observe(path)
        assert metadata["sample_rate"] == spec.rate and metadata["channels"] == spec.channels
        assert metadata["frames"] == spec.frames and metadata["sample_width"] == spec.width
        checks += 2
        if spec.sample_format == "pcm":
            # Verify our manual RIFF construction with a separate reader.
            with wave.open(str(path), "rb") as standard:
                assert (standard.getframerate(), standard.getnchannels(), standard.getsampwidth(), standard.getnframes()) == (spec.rate, spec.channels, spec.width, spec.frames)
            checks += 1
        rate, channels, details = read_audio(path)
        assert len(channels) == spec.channels and all(len(channel) == spec.frames for channel in channels)
        checks += 1
        again = write_fixture(spec, root / "repeat")
        assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(again.read_bytes()).digest()
        checks += 1
        if spec.key == "stereo-pair":
            assert channels[0] != channels[1]
            assert abs(max(channels[0]) - 0.3) < 0.001 and abs(max(channels[1]) - 0.2) < 0.001
            checks += 2
        if spec.key == "silence":
            assert not metadata["non_silent"]
            checks += 1
        if spec.key == "impulse":
            assert sum(value != 0 for value in channels[0]) == 1
            checks += 1
        if spec.key == "segments":
            assert all(value == 0 for value in channels[0][11025:16537])
            assert any(value != 0 for value in channels[0][16538:33074])
            checks += 2
        if spec.metadata:
            assert details["metadata"]["INAM"] == "音频 metadata"
            checks += 1
    invalid_files = 0
    for spec in invalid_catalog():
        path = write_fixture(spec, root)
        try:
            read_audio(path)
        except (ValueError, IndexError, ZeroDivisionError):
            invalid_files += 1
        else:
            raise AssertionError(f"invalid fixture accepted: {spec.key}")
        checks += 1
    original = tone(root / "original.wav")
    assert observe(original)["pcm_sha256"] == "67f4e9bb8d898e4d1385279a94b0d154c1c89ce16ac0cd81ae0bedce9927ac85"
    checks += 1
    return {"pcm_variants": len(pcm_catalog()), "invalid_variants": invalid_files, "checks": checks}


def selfcheck_encoded(directory: str | Path) -> dict[str, int]:
    """Validate exact lossless round trips and bounded lossy audio content."""
    root = Path(directory)
    checks = 0
    for spec in encoded_catalog():
        source = write_fixture(dataclasses.replace(spec, key="source", filename="source.wav", encoding="wav"), root / spec.key)
        with wave.open(str(source), "rb") as stream:
            original = stream.readframes(stream.getnframes())
        encoded = write_fixture(spec, root)
        again = write_fixture(spec, root / "repeat")
        assert encoded.stat().st_size > 0
        assert encoded.read_bytes() == again.read_bytes()
        checks += 2
        decoded = decode_pcm(encoded, rate=spec.rate, channels=spec.channels, raw=spec.encoding == "raw")
        if spec.encoding in {"aiff", "flac", "caf", "raw"}:
            assert decoded == original, f"lossless fixture changed PCM: {spec.encoding}"
            checks += 1
        else:
            samples = struct.unpack("<%dh" % (len(decoded) // 2), decoded)
            # Check duration and signal frequency/energy, rather than exact
            # bytes from a lossy encoder. A silent/replaced tone must fail.
            assert abs(len(samples) - spec.frames) < spec.rate // 20
            assert max(abs(value) for value in samples) > 5000
            energy = sum(value * value for value in samples) / max(1, len(samples))
            assert 30_000_000 < energy < 160_000_000
            projected_sine = sum(value * math.sin(2 * math.pi * 440 * index / spec.rate) for index, value in enumerate(samples))
            projected_cosine = sum(value * math.cos(2 * math.pi * 440 * index / spec.rate) for index, value in enumerate(samples))
            dominant_amplitude = 2 * math.hypot(projected_sine, projected_cosine) / max(1, len(samples))
            assert dominant_amplitude > 8500
            checks += 4
    return {"encoded_variants": len(encoded_catalog()), "checks": checks}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate and validate LMMS fixtures")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--encoded", action="store_true")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()
    if args.selfcheck:
        result = selfcheck(args.directory)
        if args.encoded:
            encoded_result = selfcheck_encoded(args.directory)
            result["encoded_variants"] = encoded_result["encoded_variants"]
            result["checks"] += encoded_result["checks"]
        print(json.dumps(result, sort_keys=True))
    else:
        paths = generate_catalog(args.directory, encoded=args.encoded)
        print(json.dumps({key: str(path) for key, path in paths.items()}, ensure_ascii=False, indent=2))
