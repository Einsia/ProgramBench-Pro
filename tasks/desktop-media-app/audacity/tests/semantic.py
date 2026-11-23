#!/usr/bin/env python3
"""Semantic observations used by Audacity case modules.

These helpers intentionally inspect exported artifacts rather than pixels or
widget labels.  They keep case actions short and make it possible to add many
audio/editing scenarios while preserving one canonical interpretation of WAV,
JSON project and file observations.
"""
from __future__ import annotations

import hashlib
import array
import dataclasses
import cmath
import json
import math
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from typing import Any, Iterable, Mapping, Sequence

from evaluation.contract import InfrastructureError


class SemanticError(AssertionError):
    """An exported artifact is syntactically valid but semantically wrong."""


class DecoderUnavailable(RuntimeError):
    """The independent decoder could not process one artifact (for example it timed out on a candidate file);
    that point fails. A missing decoder or full verifier storage is an InfrastructureError instead."""


@dataclasses.dataclass
class AudioBuffer:
    """Interleaved decoded samples, normalised to signed full scale.

    Integer PCM values are represented exactly by binary64 for 8/16/24/32-bit
    input. IEEE float input keeps its decoded value; no limiter, normaliser,
    dither, resampler or downmix is applied by the observer.
    """

    sample_rate: int
    channels: int
    samples: array.array
    codec: str = "pcm"
    sample_format: str = "dbl"
    source_bits: int | None = None
    channel_layout: str = ""
    container: str = ""
    tags: dict[str, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        if self.samples.typecode != "d":
            self.samples = array.array("d", self.samples)
        if self.sample_rate <= 0 or self.channels <= 0:
            raise SemanticError("audio rate and channel count must be positive")
        if len(self.samples) % self.channels:
            raise SemanticError("decoded sample count is not channel-aligned")
        if any(not math.isfinite(value) for value in self.samples):
            raise SemanticError("audio contains non-finite decoded samples")

    @property
    def frames(self) -> int:
        return len(self.samples) // self.channels

    @property
    def duration(self) -> float:
        return self.frames / self.sample_rate

    def channel(self, index: int) -> array.array:
        if not 0 <= index < self.channels:
            raise IndexError("audio channel index out of range")
        return self.samples[index :: self.channels]

    def slice(self, start: int, end: int) -> "AudioBuffer":
        if not (0 <= start <= end <= self.frames):
            raise SemanticError(f"invalid frame selection [{start}, {end})")
        return dataclasses.replace(self, samples=self.samples[start * self.channels : end * self.channels])

    def canonical_pcm(self) -> bytes:
        """Return decoded binary64 PCM only, independent of container bytes."""

        data = array.array("d", self.samples)
        # Canonicalise negative zero: it is the same audio sample as +0, but
        # IEEE bit representations differ. Samples are otherwise untouched.
        for index, value in enumerate(data):
            if value == 0:
                data[index] = 0.0
        if sys.byteorder != "little":
            data.byteswap()
        return data.tobytes()


@dataclasses.dataclass(frozen=True)
class AudioTolerance:
    """Declared comparison tolerance for a single audio scenario.

    Exact edits use the default zero tolerance. DSP/float effects may opt into
    a small absolute/relative sample error and RMSE cap; values are validated
    rather than letting NaN or an infinite bound make every sample pass.
    """

    absolute: float = 0.0
    relative: float = 0.0
    rmse: float = 0.0
    frame_delta: int = 0
    compare_layout: bool = True

    def __post_init__(self):
        for name in ("absolute", "relative", "rmse"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"audio tolerance {name} must be finite and non-negative")
        if type(self.frame_delta) is not int or self.frame_delta < 0:
            raise ValueError("audio frame_delta must be a non-negative integer")


def _decoder_binary(name: str) -> str:
    binary = shutil.which(name)
    if not binary:
        raise InfrastructureError(f"independent audio observer requires {name}")
    return binary


def _probe(path: pathlib.Path, *, timeout: float) -> dict[str, Any]:
    command = [
        _decoder_binary("ffprobe"),
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries",
        "stream=codec_name,sample_fmt,sample_rate,channels,channel_layout,bits_per_sample,bits_per_raw_sample:stream_tags:format=format_name:format_tags",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DecoderUnavailable(f"cannot probe audio: {exc}") from exc
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace")[-500:]
        raise SemanticError(f"audio probe rejected {path.name}: {message}")
    try:
        probe = json.loads(result.stdout)
        if not probe.get("streams"):
            raise ValueError("no audio stream")
        stream = probe["streams"][0]
        rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        if not 1 <= channels <= 64 or not 1 <= rate <= 768_000:
            raise ValueError("unbounded audio rate/channel count")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SemanticError(f"invalid audio metadata in {path.name}: {exc}") from exc
    return probe


def decode_audio(
    path: str | pathlib.Path,
    *,
    timeout: float = 30.0,
    max_decoded_bytes: int = 256 * 1024 * 1024,
) -> AudioBuffer:
    """Decode WAV/float/AIFF/FLAC/Ogg/MP3 through the independent FFmpeg.

    The decoder preserves native sample rate and channel count, outputs
    binary64 little-endian PCM, and selects the first audio stream explicitly.
    Output is spooled to a temporary file with a size limit, so malformed or
    excessive inputs cannot allocate an unbounded Python byte string.
    """

    source = pathlib.Path(path)
    if not source.is_file():
        raise SemanticError(f"expected audio artifact was not created: {source.name}")
    if max_decoded_bytes <= 0:
        raise ValueError("max_decoded_bytes must be positive")
    probe = _probe(source, timeout=timeout)
    stream = probe["streams"][0]
    command = [
        _decoder_binary("ffmpeg"),
        "-hide_banner", "-v", "error", "-nostdin",
        "-i", str(source),
        "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-acodec", "pcm_f64le", "-f", "f64le",
        "-fs", str(max_decoded_bytes + 8),
        "pipe:1",
    ]
    with tempfile.TemporaryFile() as decoded:
        try:
            result = subprocess.run(
                command,
                stdout=decoded,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DecoderUnavailable(f"cannot decode audio: {exc}") from exc
        size = decoded.tell()
        if size > max_decoded_bytes:
            raise SemanticError("decoded audio exceeds the bounded observer limit")
        if result.returncode:
            message = result.stderr.decode("utf-8", "replace")[-500:]
            if 'no space left on device' in message.lower() or 'disk quota exceeded' in message.lower():
                raise InfrastructureError('independent decoder temporary storage unavailable: '+message)
            raise SemanticError(f"audio decoder rejected {source.name}: {message}")
        if size % 8:
            raise SemanticError("independent decoder returned an incomplete PCM sample")
        decoded.seek(0)
        samples = array.array("d")
        samples.frombytes(decoded.read())
        if sys.byteorder != "little":
            samples.byteswap()
    bit_depth = stream.get("bits_per_raw_sample") or stream.get("bits_per_sample")
    try:
        bits = int(bit_depth) if bit_depth is not None else None
        if bits == 0:
            bits = None
    except (TypeError, ValueError):
        bits = None
    # Preserve supplied metadata but omit implementation-only encoder and
    # generated timestamps. Candidate tag values are otherwise not rewritten.
    excluded = {"encoder", "creation_time", "date-eng"}
    tags = {
        str(key).lower(): str(value)
        for section in (probe.get("format", {}).get("tags", {}), stream.get("tags", {}))
        for key, value in section.items()
        if str(key).lower() not in excluded
    }
    return AudioBuffer(
        sample_rate=int(stream["sample_rate"]),
        channels=int(stream["channels"]),
        samples=samples,
        codec=str(stream.get("codec_name", "")),
        sample_format=str(stream.get("sample_fmt", "")),
        source_bits=bits,
        channel_layout=str(stream.get("channel_layout", "")),
        container=str(probe.get("format", {}).get("format_name", "")),
        tags=tags,
    )


def _as_buffer(value: AudioBuffer | str | pathlib.Path) -> AudioBuffer:
    return value if isinstance(value, AudioBuffer) else decode_audio(value)


def _sample_stats(values: Sequence[float]) -> dict[str, float | int]:
    count = len(values)
    if not count:
        return {"samples": 0, "peak": 0.0, "rms": 0.0, "dc": 0.0, "mean_abs": 0.0, "zero_crossings": 0}
    peak = max(abs(value) for value in values)
    dc = math.fsum(values) / count
    rms = math.sqrt(math.fsum(value * value for value in values) / count)
    mean_abs = math.fsum(abs(value) for value in values) / count
    crossings = sum((left < 0 <= right) or (right < 0 <= left) for left, right in zip(values, values[1:]))
    return {
        "samples": count,
        "peak": round(peak, 12),
        "rms": round(rms, 12),
        "dc": round(dc, 12),
        "mean_abs": round(mean_abs, 12),
        "zero_crossings": crossings,
    }


def _fft(values: Sequence[float]) -> list[complex]:
    """Radix-2 FFT used by the independent bounded spectral observer."""

    count = len(values)
    if count == 0 or count & (count - 1):
        raise ValueError("FFT input length must be a positive power of two")
    transformed = [complex(value) for value in values]
    j = 0
    for i in range(1, count):
        bit = count >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            transformed[i], transformed[j] = transformed[j], transformed[i]
    width = 2
    while width <= count:
        root = cmath.exp(-2j * math.pi / width)
        half = width // 2
        for start in range(0, count, width):
            factor = 1 + 0j
            for offset in range(half):
                even = transformed[start + offset]
                odd = transformed[start + offset + half] * factor
                transformed[start + offset] = even + odd
                transformed[start + offset + half] = even - odd
                factor *= root
        width *= 2
    return transformed


def _spectral_observe(values: Sequence[float], rate: int, *, bins: int = 1024) -> dict[str, Any]:
    """Wideband energy over five fixed, Hann-windowed positions.

    Welch-style averaging retains enough frequency information to distinguish
    high/low pass, EQ, pitch and noise/effect mutations. It is intentionally
    bounded to 5 × 1024 samples per channel, independent of clip duration.
    """

    if bins < 32 or bins & (bins - 1):
        raise ValueError("spectral bins must be a power of two of at least 32")
    window = [0.5 - 0.5 * math.cos(2 * math.pi * index / (bins - 1)) for index in range(bins)]
    power = [0.0] * (bins // 2 + 1)
    span = max(0, len(values) - bins)
    starts = sorted({round(span * fraction) for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)})
    for start in starts:
        chunk = [
            (values[start + offset] if start + offset < len(values) else 0.0) * window[offset]
            for offset in range(bins)
        ]
        fft = _fft(chunk)
        for index in range(len(power)):
            power[index] += abs(fft[index]) ** 2
    factor = sum(value * value for value in window) * max(1, len(starts)) * bins
    power = [value / factor for value in power]
    total = math.fsum(power)
    frequencies = [index * rate / bins for index in range(len(power))]
    centroid = math.fsum(hz * value for hz, value in zip(frequencies, power)) / total if total else 0.0
    spread = math.sqrt(math.fsum((hz - centroid) ** 2 * value for hz, value in zip(frequencies, power)) / total) if total else 0.0
    dominant = frequencies[max(range(len(power)), key=power.__getitem__)] if total else 0.0
    nyquist = rate / 2
    # Fixed frequency edges provide useful absolute-band semantics; bins above
    # the input's Nyquist are omitted, rather than being claimed as observed.
    edges = sorted({0.0, *[float(edge) for edge in (100, 250, 500, 1000, 2000, 4000, 8000, 16000) if edge < nyquist], nyquist})
    bands = []
    for low, high in zip(edges, edges[1:]):
        energy = math.fsum(
            value
            for hz, value in zip(frequencies, power)
            if low <= hz < high or high == nyquist and hz == high
        )
        bands.append(
            {"low_hz": low, "high_hz": high, "energy": round(energy, 14), "ratio": round(energy / total, 12) if total else 0.0}
        )
    return {
        "fft_bins": bins,
        "sampled_windows": len(starts),
        "total_energy": round(total, 14),
        "centroid_hz": round(centroid, 6),
        "spread_hz": round(spread, 6),
        "dominant_hz": round(dominant, 6),
        "bands": bands,
    }


def audio_observe(
    value: AudioBuffer | str | pathlib.Path,
    *,
    windows: int = 8,
    waveform_points: int = 64,
    spectrum: bool = True,
) -> dict[str, Any]:
    """Observe stable sample semantics for mono/multichannel exported audio.

    ``decoded_pcm_sha256`` fingerprints canonical decoded samples, never the
    container/header bytes. Cases requiring exact edits should additionally
    use :func:`assert_audio_equal` against their expected PCM buffer; effects
    can declare :class:`AudioTolerance` rather than weakening every case.
    """

    buffer = _as_buffer(value)
    if type(windows) is not int or not 1 <= windows <= 128:
        raise ValueError("windows must be between 1 and 128")
    if type(waveform_points) is not int or not 1 <= waveform_points <= 1024:
        raise ValueError("waveform_points must be between 1 and 1024")
    channel_observations = []
    for index in range(buffer.channels):
        samples = buffer.channel(index)
        count = len(samples)
        partitions = []
        for partition in range(windows):
            start = round(count * partition / windows)
            end = round(count * (partition + 1) / windows)
            partitions.append({"start_frame": start, "end_frame": end, **_sample_stats(samples[start:end])})
        # Fixed-size min/max/RMS envelopes retain local shape and timing.
        # Unlike a few raw sampled values, an impulse cannot fall between all
        # observation points and disappear from the expected waveform.
        envelope = []
        for point in range(waveform_points):
            start = round(count * point / waveform_points)
            end = round(count * (point + 1) / waveform_points)
            chunk = samples[start:end]
            envelope.append(
                {
                    "start_frame": start,
                    "end_frame": end,
                    "min": round(min(chunk, default=0.0), 12),
                    "max": round(max(chunk, default=0.0), 12),
                    "rms": _sample_stats(chunk)["rms"],
                }
            )
        observation = {"channel": index, **_sample_stats(samples), "windows": partitions, "waveform": envelope}
        if spectrum:
            observation["spectrum"] = _spectral_observe(samples, buffer.sample_rate)
        channel_observations.append(observation)
    return {
        "sample_rate": buffer.sample_rate,
        "channels": buffer.channels,
        "channel_layout": buffer.channel_layout,
        "frames": buffer.frames,
        "duration_seconds": round(buffer.duration, 12),
        "codec": buffer.codec,
        "sample_format": buffer.sample_format,
        "source_bits": buffer.source_bits,
        "container": buffer.container,
        "decoded_pcm_sha256": hashlib.sha256(buffer.canonical_pcm()).hexdigest(),
        "tags": buffer.tags,
        "channel_observations": channel_observations,
    }


def assert_audio_equal(
    actual: AudioBuffer | str | pathlib.Path,
    expected: AudioBuffer | str | pathlib.Path,
    *,
    tolerance: AudioTolerance | None = None,
) -> dict[str, Any]:
    """Compare every decoded PCM sample and report meaningful error metrics.

    Rate and channel count are exact. Channel layout is exact when both
    containers supply one; a mono/stereo WAV which omits the redundant layout
    is allowed to compare with an equivalent FLAC which names that layout.
    Container bytes, headers, tags, encoder names and timestamps do not enter
    a PCM equality assertion.
    """

    got = _as_buffer(actual)
    wanted = _as_buffer(expected)
    bounds = tolerance or AudioTolerance()
    if got.sample_rate != wanted.sample_rate:
        raise SemanticError(f"sample rate {got.sample_rate} != {wanted.sample_rate}")
    if got.channels != wanted.channels:
        raise SemanticError(f"channel count {got.channels} != {wanted.channels}")
    if bounds.compare_layout and got.channel_layout and wanted.channel_layout and got.channel_layout != wanted.channel_layout:
        raise SemanticError(f"channel layout {got.channel_layout!r} != {wanted.channel_layout!r}")
    frame_difference = got.frames - wanted.frames
    if abs(frame_difference) > bounds.frame_delta:
        raise SemanticError(f"frame count {got.frames} != {wanted.frames} (allowed delta {bounds.frame_delta})")
    count = min(len(got.samples), len(wanted.samples))
    max_absolute = 0.0
    # Kahan accumulation avoids allocating one Python float for every sample
    # in a bounded 8-channel/30-second clip.
    squared_error_sum = 0.0
    squared_error_correction = 0.0
    first_mismatch: tuple[int, float, float, float] | None = None
    for index in range(count):
        observed = got.samples[index]
        reference = wanted.samples[index]
        error = abs(observed - reference)
        max_absolute = max(max_absolute, error)
        squared_error = error * error - squared_error_correction
        next_sum = squared_error_sum + squared_error
        squared_error_correction = (next_sum - squared_error_sum) - squared_error
        squared_error_sum = next_sum
        allowed = bounds.absolute + bounds.relative * abs(reference)
        if error > allowed and first_mismatch is None:
            first_mismatch = (index, observed, reference, allowed)
    rmse = math.sqrt(squared_error_sum / max(1, count))
    if first_mismatch is not None:
        index, observed, reference, allowed = first_mismatch
        frame, channel = divmod(index, got.channels)
        raise SemanticError(
            f"PCM sample differs at frame {frame}, channel {channel}: {observed:.12g} != {reference:.12g}; "
            f"allowed {allowed:.3g}, maximum error {max_absolute:.3g}, RMSE {rmse:.3g}"
        )
    if bounds.rmse and rmse > bounds.rmse:
        raise SemanticError(f"PCM RMSE {rmse:.12g} exceeds {bounds.rmse:.12g}")
    return {
        "sample_rate": got.sample_rate,
        "channels": got.channels,
        "frames": got.frames,
        "compared_samples": count,
        "frame_delta": frame_difference,
        "maximum_absolute_error": round(max_absolute, 14),
        "rmse": round(rmse, 14),
        "exact": bounds.absolute == bounds.relative == bounds.rmse == 0 and frame_difference == 0,
    }


def compare_observations(
    actual: Any,
    expected: Any,
    *,
    absolute: float = 0.0,
    relative: float = 0.0,
    tolerances: Mapping[str, tuple[float, float]] | None = None,
    ignore: Iterable[str] = (),
    path: str = "$",
) -> None:
    """Compare persisted JSON observations with explicit numeric tolerances.

    Dictionary/list shape, strings, booleans and integer values stay exact. Floats
    use the given bounds; a per-field-path ``tolerances`` map can scope relaxed
    DSP values without relaxing unrelated metadata such as frame counts.
    """

    if not math.isfinite(absolute) or not math.isfinite(relative) or absolute < 0 or relative < 0:
        raise ValueError("comparison tolerances must be finite and non-negative")
    ignored = set(ignore)
    if path in ignored:
        return
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            raise SemanticError(f"{path}: expected object")
        expected_keys = {key for key in expected if f"{path}.{key}" not in ignored}
        actual_keys = {key for key in actual if f"{path}.{key}" not in ignored}
        if expected_keys != actual_keys:
            raise SemanticError(f"{path}: object keys differ")
        for key in expected_keys:
            compare_observations(actual[key], expected[key], absolute=absolute, relative=relative, tolerances=tolerances, ignore=ignored, path=f"{path}.{key}")
        return
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
            raise SemanticError(f"{path}: sequence shape differs")
        for index, (observed, reference) in enumerate(zip(actual, expected)):
            compare_observations(observed, reference, absolute=absolute, relative=relative, tolerances=tolerances, ignore=ignored, path=f"{path}[{index}]")
        return
    if isinstance(expected, float):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual) or not math.isfinite(expected):
            raise SemanticError(f"{path}: expected finite numeric observation")
        abs_bound, rel_bound = (tolerances or {}).get(path, (absolute, relative))
        if not math.isfinite(abs_bound) or not math.isfinite(rel_bound) or abs_bound < 0 or rel_bound < 0:
            raise ValueError(f"{path}: comparison tolerance must be finite and non-negative")
        if not math.isclose(actual, expected, abs_tol=abs_bound, rel_tol=rel_bound):
            raise SemanticError(f"{path}: {actual!r} != {expected!r} (abs {abs_bound}, rel {rel_bound})")
        return
    # JSON numbers have one semantic type: 1 and 1.0 are equivalent. Counts
    # still compare exactly, without the floating DSP tolerance; bool stays
    # distinct from numbers, unlike ordinary Python ==.
    if type(expected) is int:
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual) or actual != expected:
            raise SemanticError(f"{path}: {actual!r} != {expected!r}")
        return
    if type(actual) is not type(expected) or actual != expected:
        raise SemanticError(f"{path}: {actual!r} != {expected!r}")


def _pcm_values(payload: bytes, width: int) -> tuple[int, ...]:
    if width == 1:
        # WAV's 8-bit PCM is unsigned.  Normalise it to signed values so peak
        # and mean_abs have the same interpretation as 16/24/32-bit PCM.
        return tuple(value - 128 for value in payload)
    if width == 2:
        if len(payload) % 2:
            raise SemanticError("16-bit PCM payload has an odd byte count")
        return struct.unpack("<%dh" % (len(payload) // 2), payload)
    if width == 3:
        if len(payload) % 3:
            raise SemanticError("24-bit PCM payload is not aligned")
        values = []
        for offset in range(0, len(payload), 3):
            raw = int.from_bytes(payload[offset : offset + 3], "little", signed=False)
            values.append(raw - (1 << 24) if raw & (1 << 23) else raw)
        return tuple(values)
    if width == 4:
        if len(payload) % 4:
            raise SemanticError("32-bit PCM payload has an incomplete sample")
        return struct.unpack("<%di" % (len(payload) // 4), payload)
    raise SemanticError(f"unsupported PCM sample width: {width} bytes")


def wav_observe(path: str | pathlib.Path, *, require_pcm: bool = True) -> dict[str, Any]:
    """Read deterministic WAV metadata and PCM fingerprints.

    ``frames`` counts per-channel frames, while ``sample_count`` counts scalar
    samples.  The distinction matters for stereo fixtures and avoids assuming
    that every file is mono 16-bit PCM.
    """

    path = pathlib.Path(path)
    if not path.exists():
        raise SemanticError(f"expected WAV was not created: {path.name}")
    try:
        with wave.open(str(path), "rb") as stream:
            channels = stream.getnchannels()
            width = stream.getsampwidth()
            rate = stream.getframerate()
            frames = stream.getnframes()
            payload = stream.readframes(frames)
            compression = stream.getcomptype()
            name = stream.getcompname()
    except (EOFError, wave.Error) as exc:
        # Python's wave module in the pinned Ubuntu image does not decode
        # IEEE-float or every WAVE_FORMAT_EXTENSIBLE header. The independent
        # FFmpeg decoder covers those formats without treating their bytes as
        # signed integers.
        try:
            decoded = decode_audio(path)
        except DecoderUnavailable:
            raise
        except SemanticError:
            raise SemanticError(f"invalid WAV {path.name}: {exc}") from exc
        if decoded.container != "wav":
            raise SemanticError(f"expected a WAV container, got {decoded.container!r}") from exc
        bits = decoded.source_bits or (32 if decoded.codec.startswith("pcm_f32") else 64 if decoded.codec.startswith("pcm_f64") else 0)
        peak = max((abs(value) for value in decoded.samples), default=0.0)
        mean_abs = math.fsum(abs(value) for value in decoded.samples) / max(1, len(decoded.samples))
        return {
            "format": "wav",
            "channels": decoded.channels,
            "sample_width": bits // 8 if bits else None,
            "sample_rate": decoded.sample_rate,
            "frames": decoded.frames,
            "sample_count": len(decoded.samples),
            "duration_ms": round(decoded.duration * 1000),
            "compression": "NONE",
            "compression_name": "not compressed",
            "peak": round(peak, 12),
            "mean_abs": round(mean_abs, 12),
            "silent": peak == 0,
            # This is decoded PCM rather than a header/file hash; the general
            # observer always reports the same semantic fingerprint field.
            "pcm_sha256": hashlib.sha256(decoded.canonical_pcm()).hexdigest(),
        }
    except OSError as exc:
        raise SemanticError(f"invalid WAV {path.name}: {exc}") from exc
    if channels < 1 or rate < 1 or frames < 0:
        raise SemanticError("WAV has invalid channel/rate/frame metadata")
    if require_pcm and compression != "NONE":
        raise SemanticError(f"compressed WAV is not supported: {compression}")
    values = _pcm_values(payload, width) if compression == "NONE" else ()
    peak = max((abs(value) for value in values), default=0)
    mean_abs = sum(abs(value) for value in values) / max(1, len(values))
    return {
        "format": "wav",
        "channels": channels,
        "sample_width": width,
        "sample_rate": rate,
        "frames": frames,
        "sample_count": len(values),
        "duration_ms": round(frames * 1000 / rate),
        "compression": compression,
        "compression_name": name,
        "peak": peak,
        "mean_abs": round(mean_abs, 6),
        "silent": peak == 0,
        "pcm_sha256": hashlib.sha256(payload).hexdigest(),
    }


def assert_wav(
    path: str | pathlib.Path,
    expected: Mapping[str, Any] | None = None,
    *,
    allow_hash: Iterable[str] = (),
    require_non_silent: bool = False,
) -> dict[str, Any]:
    """Observe a WAV and assert selected semantic fields.

    ``allow_hash`` can contain volatile fields such as ``pcm_sha256`` for a
    lossy/export-format case.  All fields in ``expected`` are compared by
    default, which makes accidental broad tolerances visible in the case code.
    """

    observation = wav_observe(path)
    if require_non_silent and observation["silent"]:
        raise SemanticError("expected non-silent audio")
    ignored = set(allow_hash)
    for key, value in (expected or {}).items():
        if key in ignored:
            continue
        if key not in observation:
            raise SemanticError(f"WAV observation has no field {key!r}")
        if observation[key] != value:
            raise SemanticError(
                f"{pathlib.Path(path).name}: {key} {observation[key]!r} != {value!r}"
            )
    return observation


def audio_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Return stable semantic deltas for a before/after edit pair."""

    fields = ("channels", "sample_width", "sample_rate", "frames", "duration_ms", "peak", "mean_abs")
    return {field: after.get(field) - before.get(field) for field in fields if isinstance(after.get(field), (int, float)) and isinstance(before.get(field), (int, float))}


def sha256_file(path: str | pathlib.Path) -> str:
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_observe(path: str | pathlib.Path) -> Any:
    """Load a UTF-8 JSON artifact with a semantic error on malformed data."""

    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SemanticError(f"invalid JSON artifact {path}: {exc}") from exc


def json_subset(actual: Any, expected: Any, *, path: str = "$", ignore: Iterable[str] = ()) -> None:
    """Assert that ``actual`` contains an expected JSON shape.

    Lists are compared in order and scalars are exact.  This is deliberately a
    narrow helper: order-insensitive assertions should be made explicitly in a
    case with a sorted projection rather than hidden in a generic comparator.
    """

    ignored = set(ignore)
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            raise SemanticError(f"{path}: expected object, got {type(actual).__name__}")
        for key, wanted in expected.items():
            if key in ignored:
                continue
            if key not in actual:
                raise SemanticError(f"{path}: missing key {key!r}")
            json_subset(actual[key], wanted, path=f"{path}.{key}", ignore=ignored)
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise SemanticError(f"{path}: list shape differs")
        for index, (got, wanted) in enumerate(zip(actual, expected)):
            json_subset(got, wanted, path=f"{path}[{index}]", ignore=ignored)
        return
    if actual != expected:
        raise SemanticError(f"{path}: {actual!r} != {expected!r}")


def finite_number(value: Any, *, name: str = "value") -> float:
    """Validate a JSON numeric observation without accepting booleans/NaN."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SemanticError(f"{name} must be a finite number")
    if not math.isfinite(float(value)):
        raise SemanticError(f"{name} must be finite")
    return float(value)

