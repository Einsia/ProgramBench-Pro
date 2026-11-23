"""Public setup and independent program checks for GUI checkpoints.

Setup uses only the documented scripting commands and the episode's input
documents, through the black-box runtime. Checks read public scripting state,
product files the GUI wrote into the runtime's owned areas (retrieved with
list_files/download) and independently decoded audio; their results are never
shown to the agent. Expected audio is computed from the verifier-private
fixture originals.
"""
import array
import dataclasses
import math
from semantic import AudioBuffer, AudioTolerance, assert_audio_equal, audio_observe, decode_audio

EXACT = 1/32768+1e-7


def setup(ctx, operations):
    for op in operations:
        kind = op['op']
        if kind == 'import':
            ctx.import_audio(op['file'])
        elif kind == 'select':
            ctx.select(op['start'], op['end'], op.get('track', 0), op.get('count', 1))
        elif kind == 'command':
            if op.get('optional'):
                # Cosmetic preparation (for example zoom to fit); never decisive.
                try:
                    ctx.command(op['command'], **op.get('params', {}))
                except AssertionError:
                    pass
            else:
                ctx.require(op['command'], **op.get('params', {}))
        else:
            raise ValueError('unknown setup operation '+kind)


# ----------------------------------------------------------------- expected audio
def frame(buffer, seconds):
    return max(0, min(buffer.frames, round(seconds*buffer.sample_rate)))


def splice(buffer, start, end, replacement=None):
    width = buffer.channels
    values = buffer.samples[:start*width]
    values.extend(replacement if replacement is not None else array.array('d'))
    values.extend(buffer.samples[end*width:])
    return dataclasses.replace(buffer, samples=values)


def expected_audio(ctx, spec):
    """Apply exactly specified edits to a decoded fixture: cut, silence, paste, gain, reverse, trim, mix."""
    source = decode_audio(ctx.reference_fixture(spec['source']))
    current = dataclasses.replace(source, samples=array.array('d', source.samples))
    for op, *args in spec.get('ops', []):
        width = current.channels
        if op == 'cut':
            current = splice(current, frame(current, args[0]), frame(current, args[1]))
        elif op == 'silence':
            a, b = frame(current, args[0]), frame(current, args[1])
            current = splice(current, a, b, array.array('d', [0.0])*((b-a)*width))
        elif op == 'insert-silence':
            a, count = frame(current, args[0]), round(args[1]*current.sample_rate)
            current = splice(current, a, a, array.array('d', [0.0])*(count*width))
        elif op == 'paste':
            # paste source[t0:t1] (original fixture timeline) at position `at` ('end' = current end)
            at, t0, t1 = args
            a = current.frames if at == 'end' else frame(current, at)
            piece = source.samples[frame(source, t0)*width:frame(source, t1)*width]
            current = splice(current, a, a, array.array('d', piece))
        elif op == 'trim':
            current = current.slice(frame(current, args[0]), frame(current, args[1]))
        elif op == 'gain':
            factor = 10**(args[0]/20)
            a, b = (frame(current, args[1]), frame(current, args[2])) if len(args) > 1 else (0, current.frames)
            values = array.array('d', current.samples)
            for i in range(a*width, b*width):
                values[i] *= factor
            current = dataclasses.replace(current, samples=values)
        elif op == 'reverse':
            a, b = (frame(current, args[0]), frame(current, args[1])) if args else (0, current.frames)
            values = array.array('d', current.samples)
            for i in range(b-a):
                values[(a+i)*width:(a+i+1)*width] = current.samples[(b-1-i)*width:(b-i)*width]
            current = dataclasses.replace(current, samples=values)
        elif op == 'repeat':
            values = array.array('d', current.samples)
            for _ in range(args[0]):
                values.extend(current.samples)
            current = dataclasses.replace(current, samples=values)
        elif op == 'downmix':
            values = array.array('d', (sum(current.samples[i*width:(i+1)*width])/width for i in range(current.frames)))
            current = dataclasses.replace(current, channels=1, samples=values, channel_layout='')
        elif op == 'mix':
            other = decode_audio(ctx.reference_fixture(args[0]))
            assert other.sample_rate == current.sample_rate and other.channels == current.channels
            length = max(current.frames, other.frames)*width
            values = array.array('d', [0.0])*length
            for buffer in (current, other):
                for i, v in enumerate(buffer.samples):
                    values[i] += v
            current = dataclasses.replace(current, samples=array.array('d', (max(-1.0, min(32767/32768, v)) for v in values)))
        else:
            raise ValueError('unknown expected-audio operation '+op)
    return current


def masked_equal(actual, expected, mask, tolerance):
    assert actual.sample_rate == expected.sample_rate and actual.channels == expected.channels, 'rate or channels differ'
    assert actual.frames == expected.frames, f'frame count {actual.frames} != {expected.frames}'
    skipped = [(frame(expected, a)*expected.channels, frame(expected, b)*expected.channels) for a, b in mask]
    for index, (got, wanted) in enumerate(zip(actual.samples, expected.samples)):
        if any(a <= index < b for a, b in skipped):
            continue
        if abs(got-wanted) > tolerance:
            raise AssertionError(f'sample {index//expected.channels} differs outside the generated region: {got:.6g} != {wanted:.6g}')


def correlation(actual, expected, max_lag=2048):
    """Best normalized correlation over a bounded lag, for lossy codecs with delay/padding."""
    scores = []
    for channel in range(expected.channels):
        reference, observed = expected.channel(channel), actual.channel(channel)
        stride = max(8, min(len(reference), len(observed))//1500)

        def score(lag):
            first, last = max(0, -lag), min(len(reference), len(observed)-lag)
            if last-first < min(32, len(reference)):
                return -1.0
            x2 = y2 = xy = 0.0
            for i in range(first, last, stride):
                x, y = reference[i], observed[i+lag]
                x2 += x*x
                y2 += y*y
                xy += x*y
            return xy/math.sqrt(x2*y2) if x2 and y2 else (1.0 if not x2 and not y2 else 0.0)
        lag = max(range(-max_lag, max_lag+1, 32), key=score)
        lag = max(range(max(-max_lag, lag-32), min(max_lag, lag+32)+1, 4), key=score)
        lag = max(range(max(-max_lag, lag-4), min(max_lag, lag+4)+1), key=score)
        scores.append(score(lag))
    return min(scores)


def lossy_equal(actual, expected):
    """Retained lossy-codec policy: exact rate/channels, duration within 50 ms, RMS and correlation."""
    assert actual.sample_rate == expected.sample_rate and actual.channels == expected.channels, 'rate or channels differ'
    assert abs(actual.frames-expected.frames) <= max(1, expected.sample_rate//20), 'lossy export duration differs'
    for channel in range(expected.channels):
        a, e = actual.channel(channel), expected.channel(channel)
        rms = lambda v: math.sqrt(sum(x*x for x in v)/max(1, len(v)))
        assert abs(rms(a)-rms(e)) < .08, 'lossy export changed signal energy'
    assert correlation(actual, expected) > .90, 'lossy export replaced or shifted the source signal'


def find_segment(actual, source, start, end, within, tolerance):
    """The export equals one contiguous input segment whose boundaries lie within `within` seconds of the request.

    GUI selections are shown to the millisecond; boundary samples within that
    display precision are equivalent user input. Interior samples stay exact.
    """
    import numpy
    assert actual.sample_rate == source.sample_rate and actual.channels == source.channels, 'rate or channels differ'
    rate, width, n = source.sample_rate, source.channels, actual.frames
    slack = round(within*rate)
    got = numpy.frombuffer(actual.samples, dtype=numpy.float64)
    src = numpy.frombuffer(source.samples, dtype=numpy.float64)
    for first in range(max(0, round(start*rate)-slack), round(start*rate)+slack+1):
        if abs(first+n-round(end*rate)) > slack or first+n > source.frames:
            continue
        window = src[first*width:(first+n)*width]
        if len(window) == len(got) and (len(got) == 0 or float(numpy.max(numpy.abs(window-got))) <= tolerance):
            return first
    raise AssertionError(f'export is not the input from {start} s to {end} s (within {within*1000:g} ms boundaries): {n} frames')


def signal_projection(audio, *, spectrum=True):
    """Bounded semantic projection for effects without a closed-form expectation."""
    observed = audio_observe(audio, spectrum=spectrum)
    signals = []
    for channel in observed['channel_observations']:
        row = {key: channel[key] for key in ('peak', 'rms', 'dc')}
        row['windows'] = [{key: w[key] for key in ('peak', 'rms', 'dc')} for w in channel['windows']]
        if spectrum:
            s = channel['spectrum']
            row['spectrum'] = {'centroid_hz': s['centroid_hz'], 'band_ratios': [b['ratio'] for b in s['bands']]}
        signals.append(row)
    return signals


def audio_result(ctx, audio, check):
    """Assert the declared expectation, then return the frozen observation."""
    value = {'sample_rate': audio.sample_rate, 'channels': audio.channels, 'frames': audio.frames}
    if check.get('lossy') or check.get('segment'):
        value.pop('frames')
    for key in ('sample_rate', 'channels', 'frames'):
        if key in check:
            assert value[key] == check[key], f'{key} {value[key]} != {check[key]}'
    if check.get('segment'):
        segment = check['segment']
        find_segment(audio, decode_audio(ctx.reference_fixture(segment['source'])), segment['start'], segment['end'],
                     segment['within'], check.get('tolerance', EXACT))
        value['samples'] = 'one contiguous input segment within the declared boundary precision'
    if check.get('expect') and check.get('mask'):
        masked_equal(audio, expected_audio(ctx, check['expect']), check['mask'], check.get('tolerance', EXACT))
        value['samples'] = 'match the input outside the generated region'
    elif check.get('expect'):
        tolerance = AudioTolerance(absolute=check.get('tolerance', EXACT), rmse=check.get('tolerance', EXACT),
                                   frame_delta=check.get('frame_delta', 0), compare_layout=False)
        assert_audio_equal(audio, expected_audio(ctx, check['expect']), tolerance=tolerance)
        value['samples'] = 'match the declared edit of the input'
    if check.get('region'):
        region = check['region']
        part = audio.slice(frame(audio, region['start']), frame(audio, region['end']))
        rms = math.sqrt(sum(v*v for v in part.samples)/max(1, len(part.samples)))
        low, high = region['rms']
        assert low <= rms <= high, f'RMS {rms:.4f} of {region["start"]}-{region["end"]} s is outside [{low}, {high}]'
        value['region_rms'] = 'within declared bounds'
    if check.get('lossy'):
        lossy_equal(audio, decode_audio(ctx.reference_fixture(check['lossy'])))
        value['frames'] = 'within 50 ms of the source'
        value['signal'] = 'recognisably the source signal'
    for name, bound in (check.get('signal') or {}).items():
        observed = audio_observe(audio, spectrum=name.startswith('dominant'))['channel_observations']
        channel = observed[bound.get('channel', 0)]
        actual = channel['spectrum']['dominant_hz'] if name == 'dominant_hz' else channel[name]
        assert abs(actual-bound['value']) <= bound['within'], f'{name} {actual:.6g} differs from {bound["value"]} by more than {bound["within"]}'
        value[name] = 'within declared bound'
    if check.get('projection'):
        value['signals'] = signal_projection(audio, spectrum=check.get('spectrum', True))
    return value


# ----------------------------------------------------------------- observers
def project_audio(ctx, check):
    ctx.require('SelectAll')
    ctx.export_audio(channels=check.get('channels', 1))
    return audio_result(ctx, ctx.last_audio, check)


def selected_audio(ctx, check):
    """Export only the current selection (the documented Export2 behavior); the selection is left unchanged."""
    ctx.export_audio(channels=check.get('channels', 1))
    return audio_result(ctx, ctx.last_audio, check)


def file_audio(ctx, check):
    path = ctx.fetch(check['path'])
    audio = decode_audio(path)
    ctx.audit_artifact(path, audio)
    value = audio_result(ctx, audio, check)
    for key, wanted in (check.get('format') or {}).items():
        actual = {'container': audio.container, 'codec': audio.codec}[key]
        assert wanted in actual.split(','), f'exported {key} {actual} is not {wanted}'
        value[key] = wanted
    return value


def close(a, b, within):
    return abs(float(a)-float(b)) <= within


def tracks(ctx, check):
    rows = ctx.info('Tracks')
    assert isinstance(rows, list), 'GetInfo Tracks returned no list'
    fields = check.get('fields', ('kind', 'channels', 'start', 'end'))
    projection = []
    for row in rows:
        item = {}
        for key in fields:
            value = row.get(key)
            item[key] = round(float(value), 3) if key in ('start', 'end', 'gain', 'pan') and value is not None else value
        projection.append(item)
    if 'expect' in check:
        assert len(projection) == len(check['expect']), f'{len(projection)} tracks, expected {len(check["expect"])}'
        for got, wanted in zip(projection, check['expect']):
            for key, value in wanted.items():
                if isinstance(value, float):
                    assert got.get(key) is not None and close(got[key], value, check.get('within', .002)), f'track {key} {got.get(key)} != {value}'
                else:
                    assert got.get(key) == value, f'track {key} {got.get(key)!r} != {value!r}'
        # Matched within the declared tolerance: freeze the requirement, not GUI-level millisecond noise.
        return {'tracks': check['expect'], 'within': check.get('within', .002)}
    return {'tracks': projection}


def clips(ctx, check):
    rows = ctx.info('Clips')
    assert isinstance(rows, list), 'GetInfo Clips returned no list'
    projection = sorted([[int(r.get('track', 0)), round(float(r['start']), 3), round(float(r['end']), 3)] for r in rows])
    if 'expect' in check:
        assert len(projection) == len(check['expect']), f'{len(projection)} clips, expected {len(check["expect"])}'
        for got, wanted in zip(projection, sorted(check['expect'])):
            assert got[0] == wanted[0] and close(got[1], wanted[1], .002) and close(got[2], wanted[2], .002), f'clip {got} != {wanted}'
        return {'clips': sorted(check['expect']), 'within': .002}
    return {'clips': projection}


def labels(ctx, check):
    rows = ctx.info('Labels')
    flat = sorted([[round(float(item[0]), 3), round(float(item[1]), 3), item[2]] for _track, items in rows for item in items])
    if 'expect' in check:
        assert len(flat) == len(check['expect']), f'{len(flat)} labels, expected {len(check["expect"])}'
        for got, wanted in zip(flat, sorted(check['expect'])):
            assert close(got[0], wanted[0], .002) and close(got[1], wanted[1], .002) and got[2] == wanted[2], f'label {got} != {wanted}'
        return {'labels': sorted(check['expect']), 'within': .002}
    return {'labels': flat}


def label_file(ctx, check):
    path = ctx.fetch(check['path'])
    text = path.read_bytes().decode('utf-8-sig')
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split('\t')
        assert len(fields) >= 3, 'label export line has fewer than three tab-separated fields'
        rows.append([round(float(fields[0]), 3), round(float(fields[1]), 3), fields[2]])
    rows.sort()
    assert len(rows) == len(check['expect']), f'{len(rows)} exported labels, expected {len(check["expect"])}'
    for got, wanted in zip(rows, sorted(check['expect'])):
        assert close(got[0], wanted[0], .002) and close(got[1], wanted[1], .002) and got[2] == wanted[2], f'exported label {got} != {wanted}'
    return {'labels': sorted(check['expect']), 'within': .002}


def preference(ctx, check):
    value = ctx.require('GetPreference', Name=check['name'])
    text = str(value).strip().lower() if isinstance(value, (bool, str)) else str(value)
    assert text == str(check['value']).lower(), f'preference {check["name"]} is {value!r}'
    return {'name': check['name'], 'value': check['value']}


def file_exists(ctx, check):
    path = ctx.fetch(check['path'])
    assert path.stat().st_size > 0, f'{check["path"]} is empty'
    return {'file': check['path'], 'written': True}


def visible_name(ctx, check):
    text = check['text']
    if not any(text in value for value in ctx.visible_texts()):
        rows = ctx.info('Tracks')
        assert any(text in str(row.get('name', '')) for row in rows), f'{text!r} is absent from public track metadata and the accessible desktop'
    return {'name': text, 'visible': True}


OBSERVERS = {'audio': project_audio, 'selected-audio': selected_audio, 'file-audio': file_audio, 'tracks': tracks, 'clips': clips, 'labels': labels,
             'label-file': label_file, 'preference': preference, 'file-exists': file_exists, 'visible-name': visible_name}


def observe(ctx, episode, checkpoint, check):
    return {'kind': check['kind'], **OBSERVERS[check['kind']](ctx, check)}
