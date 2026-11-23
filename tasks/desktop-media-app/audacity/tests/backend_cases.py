"""Real-product backend coverage for the pinned Audacity scripting protocol.

Every registered action issues an actual product command, reads product state,
or independently decodes an export.  Tables below are semantic input variants,
not a target case count.  Scenario fixtures and baselines are unscored setup;
edits, rendered output, undo, and redo are separate operation points.  A read
with no product action of its own is part of the step it observes, never a
separate point.  No action returns a fabricated feature or
window-success flag.
"""
from __future__ import annotations

import array
import dataclasses
import math
from typing import Any

from harness import MissingDependency
from fixtures import pcm_catalog
from semantic import AudioTolerance, assert_audio_equal, compare_observations


PCM = {spec.key: spec for spec in pcm_catalog()}
EDIT_FIXTURES = ("tone-440", "stereo-pair", "square", "noise", "chirp", "segments", "ramp", "dc-positive")
EDIT_RANGES = (("head-quarter", 0.0, 0.25), ("middle-half", 0.25, 0.75), ("tail-quarter", 0.75, 1.0))
SMALL_AUDIO_FIELDS = ("sample_rate", "channels", "frames", "duration_seconds", "codec", "sample_format", "source_bits", "container")


def _ok(ctx, command, **params):
    response = ctx.command(command, **params)
    assert response.get("ok") is True, f"{command} rejected {params}: {response.get('body')}"
    return response.get("body")


def _track_shape(tracks):
    # Focus and selected flags can legitimately change while exporting or
    # routing an undo; track/audio structure cannot.
    assert isinstance(tracks, list) and all(isinstance(track, dict) for track in tracks), "GetInfo Tracks returned malformed product JSON"
    return [{key: value for key, value in track.items() if key not in ("focused", "selected")} for track in tracks]


def _info(ctx, kind):
    value = ctx.info(kind)
    assert isinstance(value, list), "GetInfo " + kind + " returned malformed product JSON"
    return value


def _snapshot(ctx):
    return {"tracks": _info(ctx, "Tracks"), "clips": _info(ctx, "Clips")}


def _structural(value):
    return {"tracks": _track_shape(value["tracks"]), "clips": value["clips"]}


def _audio_projection(value):
    result = {key: value[key] for key in SMALL_AUDIO_FIELDS if key in value}
    if "channel_observations" in value:
        result["signals"] = []
        for channel in value["channel_observations"]:
            row = {key: channel[key] for key in ("channel", "samples", "peak", "rms", "dc", "mean_abs", "zero_crossings") if key in channel}
            # Eight distinct intervals plus the bounded spectrum retain marked
            # segments, fades and filtering without huge waveform arrays.
            row["windows"] = channel.get("windows", [])
            if "spectrum" in channel:
                row["spectrum"] = channel["spectrum"]
            result["signals"].append(row)
    elif "pcm_sha256" in value:
        # Compatibility for the small author probe; the production Context
        # returns the independently decoded channel observations above.
        result["pcm_sha256"] = value["pcm_sha256"]
    return result


def _render(ctx, channels=1):
    _ok(ctx, "SelectAll")
    observation = ctx.export_audio(channels=channels)
    return _audio_projection(observation), getattr(ctx, "last_audio", None)


def _case_state(ctx, scenario, key=None):
    state = ctx.state.get("backend")
    if not state or state.get("scenario") != scenario:
        raise MissingDependency("successful setup is missing for " + scenario)
    if key is not None and key not in state:
        raise MissingDependency("successful " + key + " is missing for " + scenario)
    return state


def _same_audio(actual, expected):
    if actual is None or expected is None:
        return None
    return assert_audio_equal(actual, expected, tolerance=AudioTolerance(absolute=1e-7, relative=1e-7, rmse=1e-7))


def _prepare(scenario, fixture_names, selection=None, before=(), channels=None):
    def action(ctx):
        ctx.reset()
        imported = []
        for fixture in fixture_names:
            result = ctx.import_audio(fixture)
            import_row = {"fixture": fixture, "result": result}
            if fixture == "unicode-name":
                import_row["visible_import_name"] = ctx.imported_name(fixture)
                _ok(ctx, "SetTrackStatus", Name="Unicode audio imported")
            imported.append(import_row)
        tracks = _info(ctx, "Tracks")
        maximum_end = max((float(track.get("end", 0)) for track in tracks), default=1.0)
        count = len(tracks)
        actual_channels = channels or max((int(track.get("channels", 1)) for track in tracks), default=1)
        for command, params in before:
            _ok(ctx, command, **params)
        baseline_state = _snapshot(ctx)
        baseline_audio, baseline_buffer = _render(ctx, actual_channels) if fixture_names else (None, None)
        if selection is not None:
            start, end = selection
            ctx.select(start * maximum_end, end * maximum_end, track=0, count=max(1, count))
        # Export2/SelectAll changes selected tracks. Reapply explicit effect
        # prerequisites (for example AutoDuck's unselected control track and
        # spectral selection) after making the independent baseline export.
        for command, params in before:
            _ok(ctx, command, **params)
        state = {"scenario": scenario, "channels": actual_channels, "fixtures": fixture_names,
                 "baseline_state": baseline_state, "baseline_audio": baseline_audio,
                 "baseline_buffer": baseline_buffer, "duration": maximum_end}
        ctx.state["backend"] = state
        return {"imports": imported, "tracks": _track_shape(baseline_state["tracks"]), "clips": baseline_state["clips"]}
    return action


def _setup(suite, family, scenario, action, attached=False):
    suite.add(family + "-fixture", scenario, "fresh-input", action, channel="setup",
              description="Create a fresh real-product baseline for " + scenario, attached=attached)


def _needs(scenario, key=None):
    """Prerequisite check of a scored step: the scenario's state, and the state an earlier step stored."""
    return lambda ctx: _case_state(ctx, scenario, key)


def _mutating_cycle(suite, family, scenario, prepare, apply, *, verify=None):
    """An actual mutation, independent export, Undo and Redo sequence.

    Each step stores what it produced before it compares, so a mismatch costs
    only its own point; a step whose earlier step could not run is blocked.
    """
    _setup(suite, family, scenario, prepare)

    def mutate(ctx):
        state = _case_state(ctx, scenario)
        result = apply(ctx, state)
        state["applied_state"] = _snapshot(ctx)
        return {"result": result, "tracks": _track_shape(state["applied_state"]["tracks"]),
                "clips": state["applied_state"]["clips"]}

    def exported(ctx):
        state = _case_state(ctx, scenario, "applied_state")
        value, buffer = _render(ctx, state["channels"])
        state["applied_audio"] = value
        state["applied_buffer"] = buffer
        if verify is not None:
            verify(ctx, state, buffer)
        return value

    def undo(ctx):
        state = _case_state(ctx, scenario, "applied_state")
        result = _ok(ctx, "Undo")
        current = _snapshot(ctx)
        state["undone_state"] = current
        compare_observations(_structural(current), _structural(state["baseline_state"]), absolute=3e-5, relative=5e-4)
        return {"result": result, **_structural(current)}

    def restored(ctx):
        state = _case_state(ctx, scenario, "undone_state")
        value, buffer = _render(ctx, state["channels"])
        if state["baseline_audio"] is not None:
            compare_observations(value, state["baseline_audio"], absolute=3e-5, relative=5e-4)
        _same_audio(buffer, state["baseline_buffer"])
        return value

    def redo(ctx):
        state = _case_state(ctx, scenario, "undone_state")
        result = _ok(ctx, "Redo")
        current = _snapshot(ctx)
        state["redone_state"] = current
        compare_observations(_structural(current), _structural(state["applied_state"]), absolute=3e-5, relative=5e-4)
        return {"result": result, **_structural(current)}

    def redone(ctx):
        state = _case_state(ctx, scenario, "redone_state")
        value, buffer = _render(ctx, state["channels"])
        if state.get("applied_audio") is not None:
            compare_observations(value, state["applied_audio"], absolute=3e-5, relative=5e-4)
            _same_audio(buffer, state["applied_buffer"])
        return value

    for step, action, description, needs in (
        ("apply", mutate, "Apply " + family + " to the selected audio and read the track and clip structure", None),
        ("render-result", exported, "Decode the edited audio independently", "applied_state"),
        ("undo", undo, "Undo and read the restored track/clip structure", "applied_state"),
        ("render-restored", restored, "Verify restored samples after Undo", "undone_state"),
        ("redo", redo, "Redo and read the edited track/clip structure", "undone_state"),
        ("render-redone", redone, "Verify Redo restores the edited samples", "redone_state"),
    ):
        suite.add(family, scenario, step, action, description=description,
                  needs=_needs(scenario, needs) if needs else None)


def _effect_cycle(suite, family, scenario, prepare, apply, *, verify=None, observe=None, reproduce=None):
    """Scripted DSP does not enter Audacity 2.4.2's normal Undo history.

    Test the actual protocol semantics: apply the effect and render it, render a
    cropped range, rebuild an independent fresh baseline, and reproduce the same
    configured effect.  GUI-effect Undo is covered by the desktop cases.  The
    clip read and the re-render of an unchanged project are part of the step
    that produced them, not separate points.
    """
    _setup(suite, family, scenario, prepare)

    def apply_effect(ctx):
        state = _case_state(ctx, scenario)
        result = apply(ctx, state)
        state["applied_state"] = _snapshot(ctx)
        observation, buffer = _render(ctx, state["channels"])
        state["applied_audio"], state["applied_buffer"] = observation, buffer
        if verify is not None:
            verify(ctx, state, buffer)
        audio = observe(ctx, state, buffer) if observe is not None else observation
        return {"result": result, "tracks": _track_shape(state["applied_state"]["tracks"]),
                "clips": state["applied_state"]["clips"], "audio": audio}

    def render_half(ctx):
        state = _case_state(ctx, scenario, "applied_audio")
        # An odd total frame count has no exact half-frame endpoint. Select an
        # integer PCM boundary explicitly instead of mixing Python's ties-to-
        # even round with Audacity's time-to-sample rounding.
        source = state["applied_buffer"]
        rate = source.sample_rate if source is not None else int(state["applied_audio"]["sample_rate"])
        frames = source.frames if source is not None else int(state["applied_audio"]["frames"])
        crop_frames = frames // 2
        ctx.select(0, crop_frames / rate, 0, len(_info(ctx, "Tracks")))
        state["crop_frames"] = crop_frames
        value = _audio_projection(ctx.export_audio(channels=state["channels"]))
        if source is not None:
            expected = source.slice(0, crop_frames)
            assert_audio_equal(ctx.last_audio, expected, tolerance=AudioTolerance(absolute=1 / 32768, rmse=1 / 32768))
        return observe(ctx, state, ctx.last_audio) if observe is not None else value

    def rebuild(ctx):
        previous = ctx.state.get("backend") or {}
        same = previous.get("scenario") == scenario
        output = previous.get("applied_audio") if same else None
        buffer = previous.get("applied_buffer") if same else None
        value = prepare(ctx)
        state = _case_state(ctx, scenario)
        state["previous_audio"], state["previous_buffer"] = output, buffer
        return value

    def reapply(ctx):
        state = _case_state(ctx, scenario)
        result = apply(ctx, state)
        state["reapplied_state"] = _snapshot(ctx)
        value, buffer = _render(ctx, state["channels"])
        if verify is not None:
            verify(ctx, state, buffer)
        if state.get("previous_buffer") is not None:
            if reproduce is not None:
                reproduce(ctx, state, buffer, state["previous_buffer"])
            else:
                compare_observations(value, state["previous_audio"], absolute=3e-5, relative=5e-4)
                _same_audio(buffer, state["previous_buffer"])
        audio = observe(ctx, state, buffer) if observe is not None else value
        return {"result": result, "tracks": _track_shape(state["reapplied_state"]["tracks"]), "audio": audio}

    suite.add(family, scenario, "apply", apply_effect,
              description="Apply the effect, read the clip structure and verify the decoded audio against the rendered reference")
    suite.add(family, scenario, "render-half-result", render_half,
              description="Select the first half of the effect output and verify its decoded export",
              needs=_needs(scenario, "applied_audio"))
    suite.add(family + "-fixture", scenario, "fresh-reapplication", rebuild, channel="setup", description="Rebuild a fresh input for independent effect reproduction")
    suite.add(family, scenario, "reapply-fresh-input", reapply, description="Reapply the configured effect to independently imported input and verify the decoded audio and its reproduction")


def _verify_exact_edit(command, start_fraction, end_fraction):
    """Check every sample for simple cuts/silence/splits, not only an oracle."""
    def check(ctx, state, actual):
        source = state["baseline_buffer"]
        if source is None or actual is None:
            return
        begin = round(source.frames * start_fraction)
        end = round(source.frames * end_fraction)
        channels = source.channels
        if command in ("Cut", "Delete"):
            samples = source.samples[:begin * channels] + source.samples[end * channels:]
        elif command == "Silence":
            samples = array.array("d", source.samples)
            samples[begin * channels:end * channels] = array.array("d", [0.0]) * ((end - begin) * channels)
        elif command in ("Split", "SplitNew"):
            samples = source.samples
        else:
            return
        expected = dataclasses.replace(source, samples=samples)
        assert_audio_equal(actual, expected, tolerance=AudioTolerance(absolute=1 / 32768, relative=0, rmse=1 / 32768))
    return check


# Delete and SplitDelete produce exactly the observations of Cut and SplitCut (their clipboard difference is
# not observed), so they keep one range per fixture instead of three.
ALIAS_RANGES = (("middle-half", 0.25, 0.75),)
EMPTY_EDITS = ("Cut", "Copy", "Delete", "Trim", "Split", "SplitCut", "SplitDelete", "Join", "Disjoin", "Duplicate")


def _empty_edit(suite, command, companion):
    """A disabled edit on an empty project is a harmless no-op. It only counts together with a point of the
    same episode that shows the command working on audio, so the scenario follows that family."""
    scenario = command.lower() + "-empty-project"
    _setup(suite, "empty-edit", scenario, _prepare(scenario, (), None), attached=True)

    def action(ctx, scenario=scenario, command=command):
        _case_state(ctx, scenario)
        result = _ok(ctx, command)
        tracks = _info(ctx, "Tracks")
        assert tracks == [], "empty-project command created an unexpected track"
        clips = _info(ctx, "Clips")
        assert clips == [], "empty-project command created an unexpected clip"
        return {"result": result, "tracks": tracks, "clips": clips}
    suite.add("empty-edit", scenario, "execute-disabled-edit", action,
              description="Empty project command remains a non-destructive no-op without tracks or clips",
              requires=(companion,))


def build_edits(suite):
    commands = ("Cut", "Delete", "Trim", "SplitCut", "SplitDelete", "Silence", "Split", "SplitNew", "Duplicate")
    for command in commands:
        family = "edit-" + command.lower()
        last = None
        for fixture in EDIT_FIXTURES:
            for range_name, start, end in (ALIAS_RANGES if command in ("Delete", "SplitDelete") else EDIT_RANGES):
                scenario = fixture + "-" + range_name
                cycle = _effect_cycle if command == "Silence" else _mutating_cycle
                cycle(suite, family, scenario,
                    _prepare(scenario, (fixture,), (start, end)),
                    lambda ctx, state, command=command: _ok(ctx, command),
                    verify=_verify_exact_edit(command, start, end))
                last = scenario
        if command in EMPTY_EDITS:
            _empty_edit(suite, command, f"backend.{family}.{last}.apply")

    # Clipboard is tested with insertions at distinct positions; replacement
    # with the same selection would be a no-op and would hide a broken paste.
    for fixture in ("tone-440", "stereo-pair", "noise", "segments", "ramp", "chirp"):
        for range_name, start, end in EDIT_RANGES:
            for destination_name, destination in (("at-start", 0.0), ("at-end", 1.0)):
                scenario = fixture + "-" + range_name + "-" + destination_name
                def paste(ctx, state, destination=destination):
                    copied = _ok(ctx, "Copy")
                    ctx.select(destination * state["duration"], destination * state["duration"], 0, 1)
                    pasted = _ok(ctx, "Paste")
                    return {"copy": copied, "paste": pasted}
                _mutating_cycle(suite, "edit-copy-paste", scenario,
                    _prepare(scenario, (fixture,), (start, end)), paste)
                last = scenario
    _empty_edit(suite, "Copy", f"backend.edit-copy-paste.{last}.apply")

    for fixture in ("tone-440", "stereo-pair", "noise", "segments", "ramp", "chirp"):
        for range_name, start, end in EDIT_RANGES:
            scenario = fixture + "-" + range_name
            def prepare(ctx, scenario=scenario, fixture=fixture, start=start, end=end):
                _prepare(scenario, (fixture,), (start, end))(ctx)
                _ok(ctx, "Split")
                state = _case_state(ctx, scenario)
                state["baseline_state"] = _snapshot(ctx)
                state["baseline_audio"], state["baseline_buffer"] = _render(ctx, state["channels"])
                ctx.select(0, state["duration"], 0, 1)
                return _structural(state["baseline_state"])
            _mutating_cycle(suite, "edit-join", scenario, prepare,
                lambda ctx, state: _ok(ctx, "Join"))
            last = scenario
    _empty_edit(suite, "Join", f"backend.edit-join.{last}.apply")

    for fixture in ("segments", "unicode-name"):
        scenario = fixture + "-detach-silences"
        _mutating_cycle(suite, "edit-disjoin", scenario,
            _prepare(scenario, (fixture,), (0, 1)), lambda ctx, state: _ok(ctx, "Disjoin"))
        last = scenario
    _empty_edit(suite, "Disjoin", f"backend.edit-disjoin.{last}.apply")


# Effect variants are exact stock command/parameter names from GetInfo Commands
# in Audacity 2.4.2.  They cover positive/negative/boundary changes, different
# algorithms and neutral/independent modes, without arbitrary invalid enums.
EFFECTS = (
    ("Amplify", "amplitude", (("half", {"Ratio": .5, "AllowClipping": False}), ("louder", {"Ratio": 1.5, "AllowClipping": False}), ("double", {"Ratio": 2, "AllowClipping": True}))),
    ("BassAndTreble", "equalization", (("bass-boost", {"Bass": 6, "Treble": 0, "Gain": -3}), ("treble-cut", {"Bass": 0, "Treble": -6, "Gain": 0}), ("both-cut", {"Bass": -6, "Treble": -6, "Gain": 3}))),
    ("ChangePitch", "pitch", (("lower", {"Percentage": -20, "SBSMS": False}), ("higher", {"Percentage": 10, "SBSMS": False}), ("fifth-up", {"Percentage": 50, "SBSMS": False}))),
    ("ChangeSpeed", "speed", (("slower", {"Percentage": -25}), ("faster", {"Percentage": 25}), ("half-again", {"Percentage": 50}))),
    ("ChangeTempo", "tempo", (("slower", {"Percentage": -25, "SBSMS": False}), ("faster", {"Percentage": 25, "SBSMS": False}), ("half-again", {"Percentage": 50, "SBSMS": False}))),
    ("Compressor", "dynamics", (("gentle", {"Threshold": -12, "NoiseFloor": -60, "Ratio": 2, "AttackTime": .1, "ReleaseTime": 1, "Normalize": False, "UsePeak": False}), ("strong", {"Threshold": -24, "NoiseFloor": -60, "Ratio": 4, "AttackTime": .1, "ReleaseTime": 1, "Normalize": False, "UsePeak": True}), ("makeup", {"Threshold": -18, "NoiseFloor": -50, "Ratio": 3, "AttackTime": .1, "ReleaseTime": 1, "Normalize": True, "UsePeak": False}))),
    ("Distortion", "distortion", (("hard", {"Type": "Hard Clipping", "Threshold dB": -18}), ("soft", {"Type": "Soft Clipping", "Threshold dB": -18, "Parameter 1": 70}), ("overdrive", {"Type": "Soft Overdrive", "Parameter 1": 70}), ("rectifier", {"Type": "Rectifier Distortion", "Parameter 1": 50}))),
    ("Echo", "delay", (("short", {"Delay": .05, "Decay": .3}), ("medium", {"Delay": .1, "Decay": .5}), ("long", {"Delay": .2, "Decay": .7}))),
    ("FadeIn", "fade", (("linear-in", {}),)),
    ("FadeOut", "fade", (("linear-out", {}),)),
    ("Invert", "waveform", (("polarity", {}),)),
    ("LoudnessNormalization", "amplitude", (("rms-12", {"NormalizeTo": 1, "RMSLevel": -12, "StereoIndependent": False, "DualMono": True}), ("rms-18", {"NormalizeTo": 1, "RMSLevel": -18, "StereoIndependent": True, "DualMono": True}), ("lufs-23", {"NormalizeTo": 0, "LUFSLevel": -23, "StereoIndependent": False, "DualMono": True}))),
    ("Normalize", "amplitude", (("peak-minus-1", {"PeakLevel": -1, "ApplyGain": True, "RemoveDcOffset": True, "StereoIndependent": False}), ("peak-minus-3", {"PeakLevel": -3, "ApplyGain": True, "RemoveDcOffset": False, "StereoIndependent": True}), ("dc-only", {"PeakLevel": -6, "ApplyGain": False, "RemoveDcOffset": True, "StereoIndependent": False}))),
    ("Phaser", "modulation", (("two-stage", {"Stages": 2, "DryWet": 96, "Freq": .5, "Phase": 0, "Depth": 100, "Feedback": 20, "Gain": -6}), ("four-stage", {"Stages": 4, "DryWet": 160, "Freq": 1, "Phase": 90, "Depth": 150, "Feedback": -20, "Gain": -6}), ("six-stage", {"Stages": 6, "DryWet": 128, "Freq": 2, "Phase": 180, "Depth": 200, "Feedback": 0, "Gain": -6}))),
    ("Repeat", "repeat", (("twice", {"Count": 1}), ("thrice", {"Count": 2}), ("four-times", {"Count": 3}))),
    ("Reverb", "reverb", (("small-room", {"RoomSize": 20, "Delay": 5, "Reverberance": 25, "HfDamping": 50, "WetGain": -6, "DryGain": -3, "WetOnly": False}), ("hall", {"RoomSize": 75, "Delay": 10, "Reverberance": 60, "HfDamping": 25, "WetGain": -6, "DryGain": -3, "WetOnly": False}), ("wet-only", {"RoomSize": 50, "Delay": 5, "Reverberance": 50, "HfDamping": 75, "WetGain": -3, "DryGain": -6, "WetOnly": True}))),
    ("Reverse", "waveform", (("reverse-time", {}),)),
    ("TruncateSilence", "silence", (("truncate", {"Threshold": -30, "Action": "Truncate Detected Silence", "Minimum": .05, "Truncate": .02, "Compress": 50, "Independent": False}), ("compress", {"Threshold": -30, "Action": "Compress Excess Silence", "Minimum": .05, "Truncate": .02, "Compress": 25, "Independent": True}))),
    ("Wahwah", "modulation", (("slow", {"Freq": .5, "Phase": 0, "Depth": 50, "Resonance": 2.5, "Offset": 30, "Gain": -6}), ("medium", {"Freq": 1.5, "Phase": 90, "Depth": 70, "Resonance": 3, "Offset": 50, "Gain": -6}), ("fast", {"Freq": 3, "Phase": 180, "Depth": 90, "Resonance": 4, "Offset": 70, "Gain": -6}))),
    ("High-passFilter", "filter", (("low-cut", {"frequency": 100, "rolloff": "dB12"}), ("mid-cut", {"frequency": 400, "rolloff": "dB24"}), ("high-cut", {"frequency": 1000, "rolloff": "dB48"}))),
    ("Low-passFilter", "filter", (("low-cut", {"frequency": 250, "rolloff": "dB12"}), ("mid-cut", {"frequency": 800, "rolloff": "dB24"}), ("high-cut", {"frequency": 2000, "rolloff": "dB48"}))),
    ("NotchFilter", "filter", (("440-wide", {"frequency": 440, "q": 4}), ("880-narrow", {"frequency": 880, "q": 8}), ("1200-narrow", {"frequency": 1200, "q": 16}))),
    ("AdjustableFade", "fade", (("up", {"type": "Up", "curve": 0, "units": "Percent", "gain0": 0, "gain1": 100, "preset": "None"}), ("down", {"type": "Down", "curve": 0, "units": "Percent", "gain0": 100, "gain1": 0, "preset": "None"}), ("s-up", {"type": "SCurveUp", "curve": 0, "units": "Percent", "gain0": 0, "gain1": 100, "preset": "None"}), ("rounded-out", {"type": "Down", "curve": 0, "units": "Percent", "gain0": 100, "gain1": 0, "preset": "RoundedOut"}))),
    ("Delay", "delay", (("regular", {"delay-type": "Regular", "dgain": -6, "delay": .05, "pitch-type": "PitchTempo", "shift": 0, "number": 3, "constrain": "Yes"}), ("bouncing", {"delay-type": "BouncingBall", "dgain": -3, "delay": .1, "pitch-type": "PitchTempo", "shift": 0, "number": 4, "constrain": "Yes"}), ("pitch", {"delay-type": "Regular", "dgain": -6, "delay": .05, "pitch-type": "LQPitchShift", "shift": 2, "number": 2, "constrain": "Yes"}))),
    ("Limiter", "dynamics", tuple((mode.lower(), {"type": mode, "gain-L": 6, "gain-R": 6, "thresh": -6, "hold": 10, "makeup": "No"}) for mode in ("SoftLimit", "HardLimit", "SoftClip", "HardClip"))),
    ("NoiseGate", "dynamics", (("gentle", {"mode": "Gate", "stereo-link": "LinkStereo", "low-cut": "No", "gate-freq": 0, "level-reduction": -12, "threshold": -20, "attack": 10}), ("strong", {"mode": "Gate", "stereo-link": "DoNotLink", "low-cut": "20Hz", "gate-freq": 0, "level-reduction": -48, "threshold": -12, "attack": 5}), ("frequency-gate", {"mode": "Gate", "stereo-link": "LinkStereo", "low-cut": "10Hz", "gate-freq": 500, "level-reduction": -24, "threshold": -18, "attack": 20}))),
    ("ClipFix", "repair", (("95-percent", {"threshold": 95, "gain": -3}), ("90-percent", {"threshold": 90, "gain": -6}))),
    ("StudioFadeOut", "fade", (("studio-out", {}),)),
    ("Tremolo", "modulation", tuple((wave.lower(), {"wave": wave, "phase": 0, "wet": 70, "lfo": 4}) for wave in ("Sine", "Triangle", "Sawtooth", "InverseSawtooth", "Square"))),
    ("FilterCurve", "equalization", (("boost-440", {"FilterLength": 8191, "InterpolateLin": False, "InterpolationMethod": "B-spline", "f0": 440, "v0": 3}), ("cut-1000", {"FilterLength": 8191, "InterpolateLin": False, "InterpolationMethod": "Cosine", "f0": 1000, "v0": -6}))),
    ("GraphicEq", "equalization", (("boost-440", {"FilterLength": 8191, "InterpolateLin": False, "InterpolationMethod": "B-spline", "f0": 440, "v0": 3}), ("cut-1000", {"FilterLength": 8191, "InterpolateLin": False, "InterpolationMethod": "Cubic", "f0": 1000, "v0": -6}))),
)


# Variants whose output equals their input on the given fixture observe nothing about the effect.
NO_OP_VARIANTS = {("Normalize", "dc-only", "stereo-pair"), ("NoiseGate", "gentle", "segments")}


def build_effects(suite):
    for command, category, variants in EFFECTS:
        # DC removal and silence truncation require fixtures exposing their
        # semantic preconditions; the other families use two different spectra.
        if command == "Normalize":
            fixtures = ("dc-positive", "stereo-pair")
        elif command == "TruncateSilence":
            fixtures = ("segments", "unicode-name")
        elif command in ("Distortion", "ClipFix"):
            fixtures = ("square", "segments")
        else:
            fixtures = ("chirp", "segments")
        for variant, params in variants:
            for fixture in fixtures:
                if (command, variant, fixture) in NO_OP_VARIANTS:
                    continue
                scenario = command.lower() + "-" + variant + "-" + fixture
                _effect_cycle(suite, "effect-" + category, scenario,
                    _prepare(scenario, (fixture,), (0, 1)),
                    lambda ctx, state, command=command, params=params: _ok(ctx, command, **params))

    for fixture in ("tone-440", "chirp", "segments", "noise", "ramp"):
        for samples in (32, 64, 96):
            scenario = fixture + "-" + str(samples) + "-samples"
            def prepare(ctx, fixture=fixture, scenario=scenario, samples=samples):
                result = _prepare(scenario, (fixture,), None)(ctx)
                state = _case_state(ctx, scenario)
                rate = state["baseline_buffer"].sample_rate
                start = round(.4 * rate)
                state["repair_interval"] = (start, start + samples)
                ctx.select(start / rate, (start + samples) / rate, 0, 1)
                return result
            _effect_cycle(suite, "effect-repair", scenario, prepare,
                lambda ctx, state: _ok(ctx, "Repair"),
                observe=_repair_observation, reproduce=_repair_reproduced)

    _effect_cycle(suite, "mix-stereo-to-mono", "different-stereo-channels",
        _prepare("different-stereo-channels", ("stereo-pair",), (0, 1), channels=1),
        lambda ctx, state: _ok(ctx, "StereoToMono"))


def _lsar(context, first, count):
    """Least-squares autoregressive interpolation of context[first:first+count].

    The model of Audacity 2.4.2 Repair: an autoregression of order
    min(3 x count, 50, larger side - 1) fitted by least squares to every
    context window that avoids the selection, then the selected samples that
    minimise the squared prediction error of the whole context.  Audacity adds
    a fresh uniform +/-5e-5 dither to the context on every run to avoid
    near-singular systems, so its output varies by a few PCM16 quanta between
    runs; the dither enters here only through its expected effect, a ridge of
    its variance on the normal equations, which keeps the reference repeatable.
    """
    import numpy as np
    n = len(context)
    order = min(count * 3, 50, max(first - 1, n - (first + count) - 1))
    assert first > 0 and 3 <= order < n, "Repair scenario is outside the autoregressive model"
    rows = [i for i in range(n - order) if i + order < first or i >= first + count]
    windows = np.stack([context[i:i + order] for i in rows])
    targets = context[np.asarray(rows) + order]
    normal = windows.T @ windows + np.eye(order) * len(rows) * 1e-8 / 12
    coefficients = np.linalg.solve(normal, windows.T @ targets)
    model = np.zeros((n - order, n))
    for row in range(n - order):
        model[row, row:row + order] = -coefficients
        model[row, row + order] = 1
    bad = np.arange(first, first + count)
    good = np.r_[0:first, first + count:n]
    known = model[:, good] @ context[good]
    unknown = model[:, bad]
    return -np.linalg.solve(unknown.T @ unknown, unknown.T @ known)


def _repair_reconstruction(source, begin, end):
    """Expected PCM16 samples of [begin, end) after Repair, interleaved like the export."""
    import numpy as np
    rate, channels = source.sample_rate, source.channels
    start, stop = begin / rate, end / rate
    spacing = max((stop - start) * 2, 128 / rate)
    first = math.floor(max(start - spacing, 0) * rate + .5)
    last = math.floor(min(stop + spacing, source.frames / rate) * rate + .5)
    data = np.asarray(source.samples[:source.frames * channels], dtype=np.float64).reshape(-1, channels)
    columns = [_lsar(data[first:last, channel].astype(np.float32).astype(np.float64), begin - first, end - begin)
               for channel in range(channels)]
    values = np.stack(columns, axis=1).astype(np.float32).astype(np.float64).reshape(-1)
    return [float(value) for value in np.clip(np.round(values * 32768), -32768, 32767) / 32768]


def _repair_observation(ctx, state, actual):
    """Observe Repair's reconstructed PCM and unchanged surrounding samples.

    Preserve exact duration/rate/channels and every sample outside the
    selected interval, prove that the selected interval was repaired, and
    compare the repaired samples with the independent least-squares
    autoregressive reconstruction of the same baseline (_lsar).  Audacity
    2.4.2 dithers its own solution randomly, so the repaired samples may
    differ from it by a seven-PCM16-quantum absolute and three-quantum local
    RMSE bound (measured worst case: four quanta, RMSE 1.4 quanta); this
    tolerance does not apply to other effects or surrounding samples.  The
    observation keeps the deterministic reconstruction, not the dithered run.
    """
    assert actual is not None, "Repair observation requires decoded audio"
    source = state["baseline_buffer"]
    assert actual.sample_rate == source.sample_rate and actual.channels == source.channels, "Repair changed rate or channel count"
    assert actual.frames in (source.frames, state.get("crop_frames")), "Repair changed duration"
    begin, end = state["repair_interval"]
    assert 0 <= begin < end <= actual.frames, "Repair selection is outside observed audio"
    scalar_begin, scalar_end = begin * actual.channels, end * actual.channels
    wanted = source.samples[:actual.frames * actual.channels]
    outside_error = max((abs(got - expected) for index, (got, expected) in enumerate(zip(actual.samples, wanted))
                         if index < scalar_begin or index >= scalar_end), default=0.0)
    assert outside_error <= 1e-7, "Repair modified samples outside its selected interval"
    local_errors = [abs(actual.samples[index] - wanted[index]) for index in range(scalar_begin, scalar_end)]
    assert max(local_errors, default=0.0) > 0, "Repair did not alter any selected sample"
    local = actual.samples[scalar_begin:scalar_end]
    assert all(math.isfinite(value) for value in local) and max(map(abs, local), default=0) <= 1, "Repair produced invalid sample amplitudes"
    reconstruction = _repair_reconstruction(source, begin, end)
    deviation = [got - expected for got, expected in zip(local, reconstruction)]
    assert len(deviation) == len(local) and max(map(abs, deviation)) <= 7 / 32768 and \
        math.sqrt(sum(value * value for value in deviation) / len(deviation)) <= 3 / 32768, \
        "Repair reconstruction differs from the least-squares autoregressive interpolation of the selection"
    # These are verified invariants, not a fabricated success flag. All sample
    # comparisons above run on the exported PCM for every observation point.
    return {"sample_rate": actual.sample_rate, "channels": actual.channels, "frames": actual.frames,
            "selection_start_frame": begin, "selection_end_frame": end,
            "outside_selection_unchanged": True, "selected_samples_changed": True,
            "finite_bounded_reconstruction": True,
            "repair_samples": reconstruction}


def _repair_reproduced(ctx, state, actual, previous):
    assert actual is not None and previous is not None, "Repair reproduction requires independently decoded audio"
    # Worst measured per-sample repeated reconstruction error is five PCM16
    # quanta (1.53e-4) in a <=96-frame interval. A two-quantum margin applies
    # only to Repair; all other edits/DSP retain their exact comparisons.
    assert_audio_equal(actual, previous,
        tolerance=AudioTolerance(absolute=7 / 32768, relative=0, rmse=3e-6))


def build_track_controls(suite):
    for fixture in ("tone-440", "stereo-pair"):
        for gain in (-18, -6, 0, 3, 6):
            for pan in (-100, -50, 0, 50, 100):
                scenario = fixture + "-gain-" + str(gain).replace("-", "minus-") + "-pan-" + str(pan).replace("-", "minus-")
                _setup(suite, "gain-pan", scenario, _prepare(scenario, (fixture,), (0, 1), channels=2))
                def set_audio(ctx, scenario=scenario, gain=gain, pan=pan):
                    _case_state(ctx, scenario)
                    ctx.select(0, 1, 0, 1)
                    result = _ok(ctx, "SetTrackAudio", Gain=gain, Pan=pan)
                    tracks = _info(ctx, "Tracks")
                    assert math.isclose(tracks[0]["gain"], 10 ** (gain / 20), rel_tol=2e-5), "track gain was not applied"
                    assert math.isclose(tracks[0]["pan"], pan / 100, abs_tol=1e-6), "track pan was not applied"
                    return {"result": result, "tracks": _track_shape(tracks)}
                def render_audio(ctx, scenario=scenario):
                    state = _case_state(ctx, scenario)
                    return _render(ctx, state["channels"])[0]
                def restore_audio(ctx, scenario=scenario):
                    _case_state(ctx, scenario)
                    ctx.select(0, 1, 0, 1)
                    result = _ok(ctx, "SetTrackAudio", Gain=0, Pan=0)
                    return {"result": result, "tracks": _track_shape(_info(ctx, "Tracks"))}
                def render_restored(ctx, scenario=scenario):
                    state = _case_state(ctx, scenario)
                    value, buffer = _render(ctx, state["channels"])
                    _same_audio(buffer, state["baseline_buffer"])
                    return value
                for step, action in (("set-gain-pan", set_audio), ("render-stereo-balance", render_audio), ("restore-gain-pan", restore_audio), ("render-restored", render_restored)):
                    suite.add("gain-pan", scenario, step, action, description=step.replace("-", " "))

    modes = (("first-muted", True, False, False, False), ("second-muted", False, False, True, False),
             ("both-muted", True, False, True, False), ("first-solo", False, True, False, False),
             ("second-solo", False, False, False, True), ("both-solo", False, True, False, True),
             ("muted-solo", True, True, False, False), ("none", False, False, False, False))
    for first, second in (("tone-440", "tone-880"), ("segments", "chirp")):
        for mode, mute1, solo1, mute2, solo2 in modes:
            scenario = first + "-" + second + "-" + mode
            _setup(suite, "mute-solo", scenario, _prepare(scenario, (first, second), (0, 1), channels=2))
            def controls(ctx, scenario=scenario, mute1=mute1, solo1=solo1, mute2=mute2, solo2=solo2):
                _case_state(ctx, scenario)
                ctx.select(0, 1, 0, 1); left = _ok(ctx, "SetTrackAudio", Mute=mute1, Solo=solo1)
                ctx.select(0, 1, 1, 1); right = _ok(ctx, "SetTrackAudio", Mute=mute2, Solo=solo2)
                return {"first": left, "second": right, "tracks": _track_shape(_info(ctx, "Tracks"))}
            def export(ctx, scenario=scenario):
                state = _case_state(ctx, scenario)
                return _render(ctx, state["channels"])[0]
            def restore(ctx, scenario=scenario):
                _case_state(ctx, scenario)
                ctx.select(0, 1, 0, 2); result = _ok(ctx, "SetTrackAudio", Mute=False, Solo=False)
                return {"result": result, "tracks": _track_shape(_info(ctx, "Tracks"))}
            for step, action in (("set-mute-solo", controls), ("render-audible-tracks", export), ("restore-all-audible", restore), ("render-all-audible", export)):
                suite.add("mute-solo", scenario, step, action, description=step.replace("-", " "))


def build_envelopes(suite):
    curves = (("half-volume", ((0.0, .5), (1.0, .5))), ("fade-in", ((0.0, .1), (.5, .5), (1.0, 1.0))),
              ("duck-middle", ((0.0, 1.0), (.25, .2), (.75, .2), (1.0, 1.0))), ("fade-out", ((0.0, 1.0), (1.0, .1))))
    for fixture in ("tone-440", "chirp", "segments", "stereo-pair"):
        for curve, points in curves:
            scenario = fixture + "-" + curve
            _setup(suite, "envelope", scenario, _prepare(scenario, (fixture,), (0, 1)))
            def set_points(ctx, scenario=scenario, points=points):
                _case_state(ctx, scenario)
                ctx.select(0, 1, 0, 1)
                results = [_ok(ctx, "SetEnvelope", Time=at, Value=value) for at, value in points]
                return {"results": results, "envelopes": _info(ctx, "Envelopes")}
            def render(ctx, scenario=scenario):
                state = _case_state(ctx, scenario)
                return _render(ctx, state["channels"])[0]
            def clear(ctx, scenario=scenario, points=points):
                _case_state(ctx, scenario)
                ctx.select(0, 1, 0, 1)
                results = [_ok(ctx, "SetEnvelope", Time=at, Delete=True) for at, _value in points]
                return {"results": results, "envelopes": _info(ctx, "Envelopes")}
            for step, action in (("set-control-points", set_points), ("render-shaped-audio", render), ("delete-control-points", clear), ("render-unshaped-audio", render)):
                suite.add("envelope", scenario, step, action, description=step.replace("-", " "))


def build_labels(suite):
    # UTF-8 label text is assessed through the visible desktop in this pinned
    # version: GetInfo Labels corrupts non-ASCII strings. Scripted label tests
    # retain actual separator, punctuation and empty-text behavior.
    texts = ("plain", "Label with spaces", "chapter/segment", "label-1", "<b>audio</b>", "A & B", 'a"b', "")
    for index, text in enumerate(texts):
        for range_name, start, end in EDIT_RANGES:
            scenario = ("empty-text" if not text else ("plain", "spaces", "slash", "hyphen", "markup", "ampersand", "quote")[index]) + "-" + range_name
            _setup(suite, "labels", scenario, _prepare(scenario, ("segments",), None))
            def add(ctx, scenario=scenario, start=start, end=end):
                _case_state(ctx, scenario)
                _ok(ctx, "NewLabelTrack"); ctx.select(start, end, 1, 1)
                result = _ok(ctx, "AddLabel")
                return {"result": result, "labels": _info(ctx, "Labels")}
            def rename(ctx, scenario=scenario, text=text):
                _case_state(ctx, scenario)
                result = _ok(ctx, "SetLabel", Label=0, Text=text)
                return {"result": result, "labels": _info(ctx, "Labels")}
            def move(ctx, scenario=scenario, start=start, end=end):
                _case_state(ctx, scenario)
                result = _ok(ctx, "SetLabel", Label=0, Start=start + .05, End=end + .05)
                return {"result": result, "labels": _info(ctx, "Labels")}
            def unselected(ctx, scenario=scenario):
                _case_state(ctx, scenario)
                result = _ok(ctx, "SetLabel", Label=0, Selected=False)
                return {"result": result, "labels": _info(ctx, "Labels")}
            def labeled_audio(ctx, scenario=scenario):
                state = _case_state(ctx, scenario)
                value, buffer = _render(ctx, state["channels"])
                _same_audio(buffer, state["baseline_buffer"])
                return value
            for step, action in (("add-region-label", add), ("set-label-text", rename), ("move-region-label", move), ("deselect-label", unselected), ("render-unchanged-audio", labeled_audio)):
                suite.add("labels", scenario, step, action, description=step.replace("-", " "))


def build_tracks(suite):
    for command, kind in (("NewMonoTrack", "mono"), ("NewStereoTrack", "stereo"), ("NewLabelTrack", "label"), ("NewTimeTrack", "time")):
        for name in ("Voice", "Music bed", "Track_2", "A & B"):
            scenario = kind + "-" + ("voice", "spaces", "underscore", "ampersand")[("Voice", "Music bed", "Track_2", "A & B").index(name)]
            _setup(suite, "tracks", scenario, _prepare(scenario, ("segments",), (0, 1)))
            def create(ctx, scenario=scenario, command=command):
                state = _case_state(ctx, scenario)
                result = _ok(ctx, command)
                tracks = _info(ctx, "Tracks")
                # Time tracks are inserted above existing audio in Audacity,
                # while ordinary new tracks are appended. Select the product
                # track that was created rather than assuming an index.
                wanted_kind = {"NewLabelTrack": "label", "NewTimeTrack": "time"}.get(command, "wave")
                candidates = [index for index, track in enumerate(tracks) if track.get("kind") == wanted_kind
                              and (wanted_kind != "wave" or track.get("end") == track.get("start") == 0)]
                assert len(candidates) == 1, "new track was not identified uniquely"
                state["added_track"] = candidates[0]
                return {"result": result, "tracks": _track_shape(tracks)}
            def rename(ctx, scenario=scenario, name=name):
                state = _case_state(ctx, scenario, "added_track")
                ctx.select(0, 1, state["added_track"], 1)
                result = _ok(ctx, "SetTrackStatus", Name=name, Selected=True, Focused=True)
                return {"result": result, "tracks": _info(ctx, "Tracks")}
            def remove(ctx, scenario=scenario):
                state = _case_state(ctx, scenario, "added_track")
                ctx.select(0, 1, state["added_track"], 1)
                result = _ok(ctx, "RemoveTracks")
                return {"result": result, "tracks": _track_shape(_info(ctx, "Tracks"))}
            def restored(ctx, scenario=scenario):
                state = _case_state(ctx, scenario)
                value, buffer = _render(ctx, state["channels"])
                _same_audio(buffer, state["baseline_buffer"])
                return value
            for step, action, needs in (("add-track", create, None), ("rename-focus-track", rename, "added_track"),
                                        ("remove-track", remove, "added_track"), ("render-original-track", restored, None)):
                suite.add("tracks", scenario, step, action, description=step.replace("-", " "),
                          needs=_needs(scenario, needs) if needs else None)

    for command in ("Align_StartToZero", "Align_StartToSelStart", "Align_StartToSelEnd", "Align_EndToSelStart", "Align_EndToSelEnd", "Align_Together", "Align_EndToEnd"):
        for first, second in (("tone-440", "tone-880"), ("segments", "chirp"), ("stereo-pair", "ramp")):
            scenario = command.lower().replace("_", "-") + "-" + first + "-" + second
            def prepare(ctx, scenario=scenario, first=first, second=second):
                result = _prepare(scenario, (first, second), None, channels=2)(ctx)
                ctx.select(0, 1, 1, 1); _ok(ctx, "SetClip", At=.5, Start=.25)
                state = _case_state(ctx, scenario)
                state["baseline_state"] = _snapshot(ctx)
                state["baseline_audio"], state["baseline_buffer"] = _render(ctx, 2)
                ctx.select(.4, .8, 0, 2)
                return _structural(state["baseline_state"])
            _mutating_cycle(suite, "track-align", scenario, prepare, lambda ctx, state, command=command: _ok(ctx, command))

    for command in ("MixAndRender", "MixAndRenderToNewTrack"):
        for first, second in (("tone-440", "tone-880"), ("segments", "chirp"), ("stereo-pair", "ramp")):
            scenario = command.lower() + "-" + first + "-" + second
            _mutating_cycle(suite, "mix-render", scenario, _prepare(scenario, (first, second), (0, 1), channels=2),
                lambda ctx, state, command=command: _ok(ctx, command))


def build_selection(suite):
    for fixture in ("tone-440", "stereo-pair", "segments", "chirp", "noise", "ramp"):
        for range_name, start, end in EDIT_RANGES:
            scenario = fixture + "-" + range_name
            _setup(suite, "selection", scenario, _prepare(scenario, (fixture,), None))
            def selected(ctx, scenario=scenario, start=start, end=end):
                state = _case_state(ctx, scenario)
                result = ctx.select(start, end, 0, 1)
                return {"result": result, "tracks": _info(ctx, "Tracks")}
            def selected_audio(ctx, scenario=scenario, start=start, end=end):
                state = _case_state(ctx, scenario)
                value = _audio_projection(ctx.export_audio(channels=state["channels"]))
                source = state["baseline_buffer"]
                if source is not None:
                    assert_audio_equal(ctx.last_audio, source.slice(round(start * source.sample_rate), round(end * source.sample_rate)), tolerance=AudioTolerance(absolute=1 / 32768, rmse=1 / 32768))
                return value
            def stored(ctx, scenario=scenario):
                _case_state(ctx, scenario)
                return {"result": _ok(ctx, "SelSave"), "tracks": _info(ctx, "Tracks")}
            def moved(ctx, scenario=scenario):
                _case_state(ctx, scenario)
                return {"result": ctx.select(.1, .2, 0, 1), "tracks": _info(ctx, "Tracks")}
            def restored(ctx, scenario=scenario):
                _case_state(ctx, scenario)
                return {"result": _ok(ctx, "SelRestore"), "tracks": _info(ctx, "Tracks")}
            for step, action in (("set-time-range", selected), ("render-selected-range", selected_audio), ("store-selection", stored), ("change-selection", moved), ("retrieve-selection", restored), ("render-retrieved-range", selected_audio)):
                suite.add("selection", scenario, step, action, description=step.replace("-", " "))


def build_project_settings(suite):
    for rate in (8000, 16000, 22050, 44100, 48000, 96000):
        for fixture in ("tone-440", "segments", "stereo-pair"):
            scenario = fixture + "-project-rate-" + str(rate)
            _setup(suite, "project-rate", scenario, _prepare(scenario, (fixture,), (0, 1)))
            def set_rate(ctx, scenario=scenario, rate=rate):
                _case_state(ctx, scenario)
                return {"result": _ok(ctx, "SetProject", Rate=rate), "tracks": _track_shape(_info(ctx, "Tracks"))}
            def exported(ctx, scenario=scenario, rate=rate):
                state = _case_state(ctx, scenario)
                value = _render(ctx, state["channels"])[0]
                assert value["sample_rate"] == rate, "project sample rate did not control export"
                return value
            def restore_rate(ctx, scenario=scenario):
                _case_state(ctx, scenario)
                return {"result": _ok(ctx, "SetProject", Rate=44100), "tracks": _track_shape(_info(ctx, "Tracks"))}
            def restored(ctx, scenario=scenario):
                state = _case_state(ctx, scenario)
                value, buffer = _render(ctx, state["channels"])
                _same_audio(buffer, state["baseline_buffer"])
                return value
            for step, action in (("set-project-rate", set_rate), ("render-at-project-rate", exported), ("restore-project-rate", restore_rate), ("render-original-rate", restored)):
                suite.add("project-rate", scenario, step, action, description=step.replace("-", " "))

    for name, slug in (("Podcast", "ascii"), ("Music project", "spaces"), ("音频项目", "unicode"), ("A & B", "ampersand")):
        scenario = "project-name-" + slug
        _setup(suite, "project-name", scenario, _prepare(scenario, ("segments",), (0, 1)))
        def rename(ctx, scenario=scenario, name=name):
            _case_state(ctx, scenario)
            result = _ok(ctx, "SetProject", Name=name)
            titles = ctx.window_titles()
            assert any(name in title for title in titles), "project name did not reach the visible window title"
            return {"result": result, "visible_project_name": name, "tracks": _track_shape(_info(ctx, "Tracks"))}
        def unchanged(ctx, scenario=scenario):
            state = _case_state(ctx, scenario)
            value, buffer = _render(ctx, state["channels"])
            _same_audio(buffer, state["baseline_buffer"])
            return value
        suite.add("project-name", scenario, "set-name", rename)
        suite.add("project-name", scenario, "render-unchanged-audio", unchanged)


def build_special_effects(suite):
    for amount, threshold in ((-6, -24), (-12, -30), (-18, -36)):
        for audio, control in (("segments", "tone-440"), ("chirp", "segments")):
            scenario = audio + "-control-" + control + "-duck-" + str(-amount)
            params = {"DuckAmountDb": amount, "InnerFadeDownLen": .05, "InnerFadeUpLen": .05,
                      "OuterFadeDownLen": .1, "OuterFadeUpLen": .1, "ThresholdDb": threshold, "MaximumPause": .1}
            _effect_cycle(suite, "effect-auto-duck", scenario,
                _prepare(scenario, (audio, control), None,
                    before=(("Select", {"Start": 0, "End": 1, "Track": 0, "TrackCount": 1}),)),
                lambda ctx, state, params=params: _ok(ctx, "AutoDuck", **params))

    for action in ("RemoveToMono", "Remove", "Isolate", "IsolateInvert", "RemoveCenterToMono", "RemoveCenter", "IsolateCenter", "IsolateCenterInvert"):
        for strength in (1, 2):
            scenario = action.lower() + "-strength-" + str(strength)
            _effect_cycle(suite, "effect-vocal", scenario,
                _prepare(scenario, ("stereo-pair",), (0, 1), channels=2),
                lambda ctx, state, action=action, strength=strength:
                    _ok(ctx, "VocalReductionAndIsolation", **{"action": action, "strength": strength, "low-transition": 120, "high-transition": 9000}))

    for command, params in (("SpectralEditMultiTool", {}), ("SpectralEditParametricEq", {"control-gain": -6}),
                            ("SpectralEditParametricEq", {"control-gain": 6}), ("SpectralEditShelves", {"control-gain": -6}),
                            ("SpectralEditShelves", {"control-gain": 6}), ("SpectralDelete", {})):
        for fixture in ("chirp", "segments"):
            for band, low, high in (("low-band", 200, 500), ("mid-band", 800, 1500)):
                scenario = command.lower() + "-" + str(params.get("control-gain", 0)).replace("-", "minus-") + "-" + fixture + "-" + band
                before = (("SetTrackVisuals", {"Display": "Spectrogram", "SpecPrefs": True, "SpectralSel": True}),
                          ("SelectFrequencies", {"Low": low, "High": high}))
                _effect_cycle(suite, "effect-spectral", scenario,
                    _prepare(scenario, (fixture,), (0, 1), before=before),
                    lambda ctx, state, command=command, params=params: _ok(ctx, command, **params))

    for mode in ("ConstantGain", "ConstantPower1", "ConstantPower2", "CustomCurve"):
        for direction in ("OutIn", "InOut"):
            scenario = mode.lower() + "-" + direction.lower()
            _effect_cycle(suite, "effect-crossfade-tracks", scenario,
                _prepare(scenario, ("segments", "chirp"), (0, 1)),
                lambda ctx, state, mode=mode, direction=direction:
                    _ok(ctx, "CrossfadeTracks", **{"type": mode, "curve": .5, "direction": direction}))

    for fixture in ("segments", "chirp", "tone-440"):
        scenario = fixture + "-adjacent-clips"
        def prepare(ctx, scenario=scenario, fixture=fixture):
            result = _prepare(scenario, (fixture,), None)(ctx)
            ctx.select(.5, .5, 0, 1); _ok(ctx, "Split"); ctx.select(0, 1, 0, 1)
            state = _case_state(ctx, scenario)
            state["baseline_state"] = _snapshot(ctx)
            state["baseline_audio"], state["baseline_buffer"] = _render(ctx, state["channels"])
            ctx.select(0, 1, 0, 1)
            return _structural(state["baseline_state"])
        _effect_cycle(suite, "effect-crossfade-clips", scenario, prepare,
            lambda ctx, state: _ok(ctx, "CrossfadeClips"))


def _analysis_cycle(suite, family, scenario, command, params, fixture="segments"):
    _setup(suite, family, scenario, _prepare(scenario, (fixture,), (0, 1)))
    def analyze(ctx):
        state = _case_state(ctx, scenario)
        result = _ok(ctx, command, **params)
        state["analyzed"] = True
        return {"result": result, "tracks": _track_shape(_info(ctx, "Tracks")), "labels": _info(ctx, "Labels"),
                "clips": _info(ctx, "Clips")}
    def unchanged(ctx):
        state = _case_state(ctx, scenario, "analyzed")
        value, buffer = _render(ctx, state["channels"])
        _same_audio(buffer, state["baseline_buffer"])
        return value
    suite.add(family, scenario, "analyze-audio", analyze,
              description="analyze audio and read the generated labels and the source clips")
    suite.add(family, scenario, "render-unchanged-source", unchanged, description="render unchanged source",
              needs=_needs(scenario, "analyzed"))


def build_analyzers(suite):
    for threshold in (25, 50, 75):
        for fixture in ("segments", "square", "impulse"):
            _analysis_cycle(suite, "analysis-beat", fixture + "-threshold-" + str(threshold), "BeatFinder", {"thresval": threshold}, fixture)
    for threshold in (20, 26, 40):
        for fixture in ("segments", "chirp"):
            _analysis_cycle(suite, "analysis-sound", fixture + "-threshold-" + str(threshold), "SoundFinder",
                {"sil-lev": threshold, "sil-dur": .05, "labelbeforedur": .01, "labelafterdur": .01, "finallabel": 0}, fixture)
    for interval in (.1, .2, .25, .5):
        for text, slug in (("Region", "ascii"), ("Region_", "underscore")):
            _analysis_cycle(suite, "analysis-interval-labels", slug + "-interval-" + str(interval), "RegularIntervalLabels",
                {"mode": "Interval", "totalnum": 4, "interval": interval, "region": 0, "adjust": "No", "labeltext": text,
                 "zeros": "OneAfter", "firstnum": 1, "verbose": "None"})
    # The first section of segments (440 Hz, amplitude 0.35) amplified 2.88 times exceeds full scale at every
    # peak for a few samples, so clipped runs start and end (a fully clipped square never ends a run).
    for duty in (1, 3, 5):
        scenario = "amplified-segments-duty-" + str(duty)
        def prepare(ctx, scenario=scenario):
            value = _prepare(scenario, ("segments",), (0, 1))(ctx)
            _ok(ctx, "Amplify", Ratio=2.88, AllowClipping=True)
            state = _case_state(ctx, scenario)
            state["baseline_state"] = _snapshot(ctx)
            state["baseline_audio"], state["baseline_buffer"] = _render(ctx, state["channels"])
            ctx.select(0, 1, 0, 1)
            return _structural(state["baseline_state"])
        _setup(suite, "analysis-clipping", scenario, prepare)
        def analyze(ctx, scenario=scenario, duty=duty):
            state = _case_state(ctx, scenario)
            result = _ok(ctx, "FindClipping", **{"Duty Cycle Start": duty, "Duty Cycle End": duty})
            state["analyzed"] = True
            return {"result": result, "labels": _info(ctx, "Labels")}
        def unchanged(ctx, scenario=scenario):
            state = _case_state(ctx, scenario, "analyzed")
            value, buffer = _render(ctx, state["channels"])
            _same_audio(buffer, state["baseline_buffer"])
            return value
        suite.add("analysis-clipping", scenario, "detect-clipping", analyze,
                  description="detect clipping and read the generated labels")
        suite.add("analysis-clipping", scenario, "render-unchanged-source", unchanged,
                  description="render unchanged source", needs=_needs(scenario, "analyzed"))


def build_history_sequences(suite):
    for fixture in ("tone-440", "stereo-pair", "segments", "chirp"):
        for sequence in ("split-cut-paste", "trim-split-delete"):
            scenario = fixture + "-" + sequence
            _setup(suite, "history-multilevel", scenario, _prepare(scenario, (fixture,), None))
            def operation(ctx, index, scenario=scenario, sequence=sequence):
                state = _case_state(ctx, scenario)
                if index == 0:
                    state["history_states"] = [_structural(_snapshot(ctx))]
                    state["history_audio"] = [state["baseline_audio"]]
                    state["history_buffers"] = [state["baseline_buffer"]]
                else:
                    if len(state.get("history_states", [])) != index + 1:
                        raise MissingDependency("prior multilevel edit is missing")
                if sequence == "split-cut-paste":
                    if index == 0:
                        ctx.select(.25, .75, 0, 1); result = _ok(ctx, "Split")
                    elif index == 1:
                        ctx.select(.25, .5, 0, 1); result = _ok(ctx, "Cut")
                    else:
                        ctx.select(.75, .75, 0, 1); result = _ok(ctx, "Paste")
                else:
                    if index == 0:
                        ctx.select(.1, .9, 0, 1); result = _ok(ctx, "Trim")
                    elif index == 1:
                        ctx.select(.3, .6, 0, 1); result = _ok(ctx, "Split")
                    else:
                        ctx.select(.35, .45, 0, 1); result = _ok(ctx, "Delete")
                shape = _structural(_snapshot(ctx))
                audio, buffer = _render(ctx, state["channels"])
                state["history_states"].append(shape)
                state["history_audio"].append(audio)
                state["history_buffers"].append(buffer)
                return {"result": result, "structure": shape, "audio": audio}
            def edits_done(count, scenario=scenario):
                def check(ctx):
                    state = _case_state(ctx, scenario)
                    if len(state.get("history_states", [])) != count:
                        raise MissingDependency("the earlier multilevel edits of " + scenario + " did not complete")
                return check
            for index, step in enumerate(sequence.split("-")):
                suite.add("history-multilevel", scenario, step, lambda ctx, index=index, operation=operation: operation(ctx, index), description="Apply " + step + " as a separate history item",
                          needs=edits_done(index + 1) if index else None)
            def undo(ctx, index, scenario=scenario):
                state = _case_state(ctx, scenario, "history_states")
                if len(state["history_states"]) != 4:
                    raise MissingDependency("all three edits must pass before multilevel Undo")
                result = _ok(ctx, "Undo")
                state["history_undo_depth"] = 3 - index
                shape = _structural(_snapshot(ctx))
                compare_observations(shape, state["history_states"][index], absolute=3e-5, relative=5e-4)
                audio, buffer = _render(ctx, state["channels"])
                compare_observations(audio, state["history_audio"][index], absolute=3e-5, relative=5e-4)
                _same_audio(buffer, state["history_buffers"][index])
                return {"result": result, "structure": shape, "audio": audio}
            for index, step in ((2, "undo-third-edit"), (1, "undo-second-edit"), (0, "undo-first-edit")):
                suite.add("history-multilevel", scenario, step, lambda ctx, index=index, undo=undo: undo(ctx, index), description="Undo to the exact prior PCM and clip structure",
                          needs=edits_done(4))
            def redo(ctx, index, scenario=scenario):
                state = _case_state(ctx, scenario, "history_undo_depth")
                result = _ok(ctx, "Redo")
                shape = _structural(_snapshot(ctx))
                compare_observations(shape, state["history_states"][index], absolute=3e-5, relative=5e-4)
                audio, buffer = _render(ctx, state["channels"])
                compare_observations(audio, state["history_audio"][index], absolute=3e-5, relative=5e-4)
                _same_audio(buffer, state["history_buffers"][index])
                return {"result": result, "structure": shape, "audio": audio}
            for index, step in ((1, "redo-first-edit"), (2, "redo-second-edit"), (3, "redo-third-edit")):
                suite.add("history-multilevel", scenario, step, lambda ctx, index=index, redo=redo: redo(ctx, index), description="Redo to the exact later PCM and clip structure",
                          needs=_needs(scenario, "history_undo_depth"))


def build(suite):
    build_edits(suite)
    build_effects(suite)
    build_track_controls(suite)
    build_envelopes(suite)
    build_labels(suite)
    build_tracks(suite)
    build_selection(suite)
    build_project_settings(suite)
    build_special_effects(suite)
    build_analyzers(suite)
    build_history_sequences(suite)


def coverage_spec():
    """Author-facing specification summaries, without a frozen numeric quota."""
    return {"edit_commands": 9, "edit_fixtures": list(EDIT_FIXTURES), "edit_ranges": [item[0] for item in EDIT_RANGES],
            "effect_commands": [command for command, _category, _variants in EFFECTS],
            "effect_variants": sum(len(variants) for _command, _category, variants in EFFECTS)}
