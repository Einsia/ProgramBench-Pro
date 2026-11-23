"""Import/export and signal-generator coverage for real Audacity.

This module is deliberately independent of the identity matrix.  A row is a
semantic dimension (fixture format, selection range, channel count, or output
codec), and each row drives the real product through ``Context.command``.  The
only audio truth comes from the fixture file and the independent decoder in
``semantic.py``; no project XML, Audacity blockfile, or hidden oracle state is
read.
"""
from __future__ import annotations

import array
import dataclasses
import math
from typing import Any

from harness import MissingDependency
from fixtures import encoded_catalog, invalid_catalog, pcm_catalog
from semantic import AudioTolerance, assert_audio_equal, audio_observe, decode_audio


PCM = {spec.key: spec for spec in pcm_catalog()}
ENCODED = {spec.key: spec for spec in encoded_catalog()}
INVALID = {spec.key: spec for spec in invalid_catalog()}

# A raw stream has no self-describing container.  Audacity's ordinary Import2
# command must reject it unless a user chooses a raw format and supplies its
# rate/width/channel parameters; it is therefore part of negative coverage.
ENCODED_IMPORT = tuple(key for key in ENCODED if key != "encoded-raw")


def _spec(key: str):
    return PCM.get(key) or ENCODED.get(key) or INVALID.get(key)


def _state(ctx: Any, name: str) -> dict[str, Any]:
    value = ctx.state.get("import-export:" + name)
    if not isinstance(value, dict):
        raise MissingDependency("setup did not complete for " + name)
    return value


def _tracks(ctx: Any) -> list[dict[str, Any]]:
    value = ctx.info("Tracks")
    if not isinstance(value, list):
        raise AssertionError("GetInfo Tracks did not return a list")
    return value


def _channel_count(rows: list[dict[str, Any]]) -> int:
    return sum(max(1, int(row.get("channels", 1))) for row in rows)


def _setup_import(ctx: Any, name: str, *, scenario: str) -> dict[str, Any]:
    # Import/export cases own an empty project, including its metadata. Merely
    # deleting tracks leaves tags from an earlier import attached to Audacity,
    # so every scenario starts in a fresh instance (runtime reset).
    ctx.fresh("import/export scenario " + scenario)
    ctx.new_scenario(scenario)
    document = ctx.fixture_name(name)
    result = ctx.import_audio(name)
    unicode_name = None
    if name == "unicode-name":
        # Audacity 2.4.2's GetInfo JSON encoder corrupts a track row whose name
        # has non-ASCII bytes. Verify the real import through its public name
        # and exported samples, then rename the selected track through the
        # public product command before querying Tracks. Never record the raw
        # upstream buffer as a supposedly valid observation.
        unicode_name = ctx.imported_name(name)
        ctx.require("SetTrackStatus", Name="Unicode audio imported")
    rows = _tracks(ctx)
    spec = _spec(name)
    assert rows, "Import2 reported success without a visible track"
    if spec is not None and spec.frames >= 0:
        assert _channel_count(rows) == spec.channels, f"import channel count differs for {name}"
    baseline = decode_audio(ctx.reference_fixture(name))
    value = {
        "fixture": name,
        "document": document,
        "import_result": result,
        "tracks": rows,
        "clips": ctx.info("Clips"),
        "baseline": baseline,
        "unicode_name": unicode_name,
    }
    ctx.state["import-export:" + scenario] = value
    return {
        "fixture": name,
        "tracks": rows,
        "clips": value["clips"],
        "sample_rate": baseline.sample_rate,
        "channels": baseline.channels,
        "frames": baseline.frames,
        **({"unicode_name": unicode_name} if unicode_name else {}),
    }


def _select_all(ctx: Any) -> None:
    response = ctx.command("SelectAll")
    assert response.get("ok") is True, response


def _correlation(actual: Any, expected: Any, *, max_lag: int = 2048) -> float:
    """Match lossily decoded content despite documented codec delay/padding."""
    if not expected.frames:
        return 1.0 if not actual.frames else 0.0
    scores = []
    for channel in range(expected.channels):
        reference = expected.channel(channel)
        observed = actual.channel(channel)
        stride = max(8, min(len(reference), len(observed)) // 1500)

        def score(lag: int) -> float:
            first = max(0, -lag)
            last = min(len(reference), len(observed) - lag)
            if last - first < min(32, len(reference)):
                return -1.0
            total_x = total_y = product = 0.0
            for index in range(first, last, stride):
                x, y = reference[index], observed[index + lag]
                total_x += x * x
                total_y += y * y
                product += x * y
            if not total_x or not total_y:
                return 1.0 if not total_x and not total_y else 0.0
            return product / math.sqrt(total_x * total_y)

        candidates = range(-max_lag, max_lag + 1, 32)
        lag = max(candidates, key=score)
        lag = max(range(max(-max_lag, lag - 32), min(max_lag, lag + 32) + 1, 4), key=score)
        lag = max(range(max(-max_lag, lag - 4), min(max_lag, lag + 4) + 1), key=score)
        scores.append(score(lag))
    return min(scores)


def _default_multichannel_mix(baseline: Any) -> Any:
    # Audacity imports >2-channel audio as N independent mono tracks. With
    # Export2's default mixer every mono track contributes to each output
    # channel. Per-track export below also verifies each source channel before
    # checking this real multichannel output policy.
    samples = array.array("d")
    for frame in range(baseline.frames):
        mixed = max(-1.0, min(32767 / 32768, sum(baseline.samples[frame * baseline.channels : (frame + 1) * baseline.channels])))
        samples.extend([mixed] * baseline.channels)
    return dataclasses.replace(baseline, samples=samples, channel_layout="")


def _selection_export(ctx: Any, name: str, scenario: str, *, extension: str = "wav", channels: int | None = None, start: float | None = None, end: float | None = None) -> dict[str, Any]:
    state = _state(ctx, scenario)
    baseline = state["baseline"]
    if start is None or end is None:
        _select_all(ctx)
        expected = baseline
    else:
        first = round(start * baseline.sample_rate)
        last = round(end * baseline.sample_rate)
        ctx.select(first / baseline.sample_rate, last / baseline.sample_rate, 0, len(state["tracks"]))
        expected = baseline.slice(first, last)
    if baseline.channels > 2:
        for index in range(baseline.channels):
            ctx.select(0, baseline.duration, index, 1)
            ctx.export_audio(channels=1, extension="wav")
            wanted = dataclasses.replace(baseline, channels=1, samples=baseline.channel(index), channel_layout="")
            assert_audio_equal(ctx.last_audio, wanted, tolerance=AudioTolerance(absolute=1 / 32768 + 1e-7, compare_layout=False))
        _select_all(ctx)
        expected = _default_multichannel_mix(expected)
    observed = ctx.export_audio(channels=channels or baseline.channels, extension=extension)
    actual = ctx.last_audio
    assert actual is not None
    lossy_source = name in {"encoded-ogg", "encoded-mp3", "encoded-mp3-vbr"}
    if extension in {"ogg", "mp3"} or lossy_source:
        # Lossy codecs retain exact shape and broad signal statistics, but not
        # every sample.  Compare duration/rate/layout exactly and ensure the
        # result is still recognisably the source signal.
        assert actual.sample_rate == expected.sample_rate
        assert actual.channels == expected.channels
        assert abs(actual.frames - expected.frames) <= max(1, expected.sample_rate // 20)
        source = audio_observe(expected, spectrum=False)
        rendered = audio_observe(actual, spectrum=False)
        for left, right in zip(source["channel_observations"], rendered["channel_observations"]):
            assert abs(left["rms"] - right["rms"]) < 0.08, f"{extension} changed signal energy unexpectedly"
        assert _correlation(actual, expected) > .90, f"{extension} replaced or shifted the source signal"
    else:
        assert_audio_equal(actual, expected, tolerance=AudioTolerance(absolute=1 / 32768 + 1e-7, rmse=1 / 32768 + 1e-7, frame_delta=1, compare_layout=baseline.channels <= 2))
    tags = decode_audio(ctx.last_export).tags
    if name == "wav-info":
        for key, value in baseline.tags.items():
            # The pinned Linux importer preserves ASCII INFO fields but drops
            # this fixture's UTF-8 title. Assert preservation for the supported
            # fields and freeze the actual tag map for the Unicode behavior.
            if value.isascii():
                assert tags.get(key) == value, f"export lost {key} metadata"
    return {
        "format": extension,
        "fixture": name,
        "sample_rate": observed["sample_rate"],
        "channels": observed["channels"],
        "frames": observed["frames"],
        "duration_seconds": observed["duration_seconds"],
        "codec": observed["codec"],
        "container": observed["container"],
        "tags": tags,
    }


def _add_import_family(suite: Any, name: str) -> None:
    scenario = name.replace("_", "-")

    def setup(ctx: Any, name=name, scenario=scenario):
        return _setup_import(ctx, name, scenario=scenario)

    def state(ctx: Any, scenario=scenario):
        value = _state(ctx, scenario)
        rows = _tracks(ctx)
        assert _channel_count(rows) == value["baseline"].channels
        return {"tracks": rows, "clips": ctx.info("Clips")}

    def render(ctx: Any, name=name, scenario=scenario):
        return _selection_export(ctx, name, scenario)

    suite.add("import-fixture", scenario, "fresh-input", setup, channel="setup", description="Import a deterministic fixture through Import2")
    suite.add("import-fixture", scenario, "visible-track-state", state, description="Read public track and clip state after import")
    suite.add("import-fixture", scenario, "roundtrip-wav", render, description="Export imported audio and compare decoded samples")


def _add_encoded_export_family(suite: Any, fixture: str, extension: str) -> None:
    scenario = fixture + "-" + extension

    def setup(ctx: Any, fixture=fixture, scenario=scenario):
        return _setup_import(ctx, fixture, scenario=scenario)

    def full(ctx: Any, fixture=fixture, scenario=scenario, extension=extension):
        return _selection_export(ctx, fixture, scenario, extension=extension)

    def selected(ctx: Any, fixture=fixture, scenario=scenario, extension=extension):
        return _selection_export(ctx, fixture, scenario, extension=extension, start=.125, end=.875)

    def repeated(ctx: Any, fixture=fixture, scenario=scenario, extension=extension):
        # New output refs are required for every command.  Repeating the same
        # selection catches stale export files and stale selection state.
        first = _selection_export(ctx, fixture, scenario, extension=extension, start=.25, end=.75)
        second = _selection_export(ctx, fixture, scenario, extension=extension, start=.25, end=.75)
        assert first["frames"] == second["frames"]
        assert first["sample_rate"] == second["sample_rate"]
        return {"first": first, "second": second}

    suite.add("export-fixture", scenario, "fresh-input", setup, channel="setup", description="Import source before format export")
    suite.add("export-fixture", scenario, "full-selection", full, description=f"Export the complete selection as {extension}")
    suite.add("export-fixture", scenario, "partial-selection", selected, description=f"Export a bounded middle range as {extension}")
    suite.add("export-fixture", scenario, "repeat-selection", repeated, description=f"Repeat {extension} export with independent artifacts")


def _set_aiff_preference(ctx: Any) -> dict[str, Any]:
    # Linux Audacity 2.4.2 registers AIFF in libsndfile but leaves it hidden
    # from the ordinary extension list. The documented SetPreference command
    # selects SF_FORMAT_AIFF; this is product state, not a private file edit.
    response = ctx.command("SetPreference", Name="/FileFormats/ExportFormat_SF1", Value="131072", Reload=False)
    assert response.get("ok") is True, response
    return {"preference": "AIFF", "result": response.get("body")}


def _add_aiff_family(suite: Any, fixture: str) -> None:
    scenario = fixture + "-aiff"

    def setup(ctx: Any, fixture=fixture, scenario=scenario):
        value = _setup_import(ctx, fixture, scenario=scenario)
        value["aiff"] = _set_aiff_preference(ctx)
        return {"fixture": fixture, "tracks": value["tracks"], "preference": value["aiff"]}

    def export(ctx: Any, fixture=fixture, scenario=scenario):
        return _selection_export(ctx, fixture, scenario, extension="aiff")

    suite.add("export-fixture", scenario, "fresh-input-aiff", setup, channel="setup", description="Select the documented Linux AIFF exporter")
    suite.add("export-fixture", scenario, "full-selection-aiff", export, description="Export exact PCM through the AIFF exporter")


def _generator_action(ctx: Any, scenario: str, command: str, params: dict[str, Any]) -> dict[str, Any]:
    ctx.new_scenario(scenario)
    response = ctx.require("NewMonoTrack")
    ctx.select(0, .5, 0, 1)
    result = ctx.command(command, **params)
    assert result.get("ok") is True, f"generator {command} unavailable: {result}"
    tracks = _tracks(ctx)
    assert tracks and float(tracks[0].get("end", 0)) > 0, f"generator {command} created no visible audio"
    _select_all(ctx)
    observed = ctx.export_audio(channels=1, extension="wav")
    audio = ctx.last_audio
    assert audio is not None
    stats = audio_observe(audio, spectrum=True)
    assert audio.sample_rate == 44100 and audio.channels == 1
    expected_frames = 11025 if command == "Pluck" else 22050
    assert audio.frames == expected_frames, f"{command} generated an incorrect duration"
    if command == "Silence":
        assert all(row["peak"] == 0 for row in stats["channel_observations"]), "Silence generator produced non-silent samples"
    else:
        assert any(row["peak"] > 1e-4 for row in stats["channel_observations"]), f"{command} produced silence"
    if command in {"Tone", "Chirp"}:
        assert stats["channel_observations"][0]["spectrum"]["total_energy"] > 1e-6
    if command == "Tone":
        frequency = params["Frequency"]
        row = stats["channel_observations"][0]
        assert abs(row["zero_crossings"] / (2 * audio.duration) - frequency) < 5
        amplitude = params["Amplitude"]
        wanted_rms = amplitude / math.sqrt(2) if params["Waveform"] == "Sine" else amplitude
        assert abs(row["rms"] - wanted_rms) < .002
    if command == "Chirp":
        values = audio.channel(0)
        quarter = max(1, len(values) // 4)
        crossing = lambda sequence: sum((a < 0 <= b) or (b < 0 <= a) for a, b in zip(sequence, sequence[1:]))
        first_frequency = crossing(values[:quarter]) / (2 * quarter / audio.sample_rate)
        last_frequency = crossing(values[-quarter:]) / (2 * quarter / audio.sample_rate)
        assert last_frequency > first_frequency * 2, "Chirp did not change frequency over time"
    if command in {"Noise", "Pluck"}:
        row = stats["channel_observations"][0]
        if command == "Noise":
            assert .01 < row["rms"] < .15
            assert abs(row["dc"]) < .02
            if params["Type"] == "White":
                assert .09 < row["rms"] < .14
                assert row["spectrum"]["centroid_hz"] > 5000
            else:
                assert row["spectrum"]["centroid_hz"] < 6000
        else:
            values = audio.channel(0)
            n = max(1, len(values) // 4)
            early = sum(value * value for value in values[:n]) / n
            late = sum(value * value for value in values[-n:]) / n
            assert early > late * 1.5, "Pluck did not decay"
        # Audacity's white/pink noise and Nyquist Pluck seed are not controlled
        # by a public parameter. Record the independent assertions and exact
        # output shape, not unstable sample hashes or random FFT envelopes.
        return {"command": command, "tracks": tracks, "sample_rate": audio.sample_rate, "channels": audio.channels, "frames": audio.frames, "signal_invariants": "passed"}
    return {"command": command, "tracks": tracks, "export": observed, "signal": stats["channel_observations"][0]}


def _add_generator_family(suite: Any, command: str, params: dict[str, Any], slug: str) -> None:
    scenario = "generator-" + slug

    def action(ctx: Any, scenario=scenario, command=command, params=params):
        return _generator_action(ctx, scenario, command, params)

    suite.add("generator", scenario, "fresh-generated-signal", action, description=f"Generate and independently decode {command}")


def _bounded_error_command(ctx: Any, command: str, **params: Any) -> dict[str, Any]:
    """Run an import whose file the product may reject.

    The runtime acknowledges the product's visible "Error Importing" message
    while the scripting command runs and returns it as a notification; the
    command's own OK/Failed status is the observation.
    """
    response = ctx.command(command, **params)
    assert isinstance(response, dict) and isinstance(response.get("ok"), bool), "Import2 returned no public status"
    return response


def _add_invalid_family(suite: Any, name: str, companion: str | None = None) -> str:
    scenario = "invalid-" + name.replace("invalid-", "")

    def action(ctx: Any, name=name, scenario=scenario):
        ctx.new_scenario(scenario)
        document = ctx.fixture_name(name)
        response = _bounded_error_command(ctx, "Import2", Filename=document)
        rows = _tracks(ctx)
        # libsndfile accepts an oversized RIFF size and a truncated data chunk:
        # the importer reads available complete frames rather than rejecting
        # the whole file. Freeze that actual behavior and verify its safe PCM.
        if name in {"invalid-bad-riff-size", "invalid-truncated-data"}:
            assert response.get("ok") is True, f"readable malformed fixture was rejected: {name}"
            assert rows and _channel_count(rows) == 1
            _select_all(ctx)
            observed = ctx.export_audio()
            wanted = decode_audio(ctx.reference_fixture(name))
            assert_audio_equal(ctx.last_audio, wanted, tolerance=AudioTolerance(absolute=1 / 32768 + 1e-7, compare_layout=False))
            return {"fixture": name, "accepted_available_frames": True, "tracks": rows, "frames": observed["frames"]}
        assert response.get("ok") is False, f"invalid fixture unexpectedly imported: {name}"
        assert rows == [], f"failed import left tracks behind for {name}"
        return {"fixture": name, "rejected": True, "tracks": rows}

    step = "available-complete-frames" if name in {"invalid-bad-riff-size", "invalid-truncated-data"} else "safe-rejection"
    # A rejection counts only together with a point that shows the same import path accepting audio.
    return suite.add("negative-import", scenario, step, action, channel="backend",
                     description="Check real malformed/missing import status and safe frame handling",
                     requires=(companion,) if companion and step == "safe-rejection" else ())


def _add_valid_import_control(suite: Any) -> str:
    """The positive companion of the rejection points: the same import path accepts an ordinary WAV."""
    scenario = "valid-tone"

    def action(ctx: Any):
        ctx.new_scenario(scenario)
        response = _bounded_error_command(ctx, "Import2", Filename=ctx.fixture_name("tone-440"))
        assert response.get("ok") is True, "a valid WAV import was rejected"
        rows = _tracks(ctx)
        assert rows and _channel_count(rows) == 1, "a valid WAV import did not create one mono track"
        _select_all(ctx)
        observed = ctx.export_audio()
        wanted = decode_audio(ctx.reference_fixture("tone-440"))
        assert_audio_equal(ctx.last_audio, wanted, tolerance=AudioTolerance(absolute=1 / 32768 + 1e-7, compare_layout=False))
        return {"fixture": "tone-440", "accepted": True, "tracks": rows, "frames": observed["frames"]}
    return suite.add("negative-import", scenario, "valid-import-control", action, channel="backend",
                     description="Import an ordinary WAV through the same path and decode the exported samples")


def build(suite: Any) -> Any:
    """Register semantic import/export/generator operations in ``suite``."""
    # All generated catalogue members are covered. Empty audio also exports a
    # valid zero-frame WAV, so its container, rate and channel count are tested.
    for name in sorted(PCM):
        _add_import_family(suite, name)

    # Lossless and lossy output codecs use distinct assertions.  AIFF is a
    # Linux preference path; the remaining formats are available by extension.
    for name in ("tone-440", "stereo-pair", "segments", "rate-48000"):
        for extension in ("flac", "ogg", "mp3"):
            _add_encoded_export_family(suite, name, extension)
        _add_aiff_family(suite, name)
    for name in ENCODED_IMPORT:
        _add_import_family(suite, name)

    for command, params, slug in (
        ("Tone", {"Frequency": 440, "Amplitude": .25, "Waveform": "Sine", "Interpolation": "Linear"}, "tone-sine"),
        ("Tone", {"Frequency": 220, "Amplitude": .2, "Waveform": "Square", "Interpolation": "Linear"}, "tone-square"),
        ("Chirp", {"StartFreq": 100, "EndFreq": 2_000, "StartAmp": .25, "EndAmp": .2, "Waveform": "Sine", "Interpolation": "Linear"}, "chirp-linear"),
        ("Silence", {}, "silence"),
        ("Noise", {"Type": "White", "Amplitude": .2}, "noise-white"),
        ("Noise", {"Type": "Pink", "Amplitude": .2}, "noise-pink"),
        ("DtmfTones", {"Sequence": "12#", "Duty Cycle": 55, "Amplitude": .2}, "dtmf"),
        ("Pluck", {"pitch": 69, "fade": "Gradual", "dur": .25}, "pluck"),
    ):
        _add_generator_family(suite, command, params, slug)

    control = _add_valid_import_control(suite)
    for name in sorted(INVALID) + ["encoded-raw"]:
        _add_invalid_family(suite, name, control)
    return suite


__all__ = ["build"]
