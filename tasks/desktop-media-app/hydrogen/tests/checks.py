"""Public setup and the independent program checks of GUI checkpoints.

Setup uploads the episode's input documents (verifier-made songs, patterns, playlists' songs, a drum kit and the
samples they play) and opens the starting song with OSC. Checks read the song the application holds (saved with
OSC /Hydrogen/SAVE_SONG_AS into the project area), product files the GUI wrote into the runtime's document areas
(retrieved with list_files/download) and the settings file; their results are never shown to the evaluator.
Projections keep only the state the checkpoint's goal produces: notes by position and instrument name, pattern and
instrument fields by name, file locations as tokens of the document areas.
"""
import io
from html.parser import HTMLParser
import re
import struct
import tarfile
import time

import audio
import fixtures
import songs as S
from harness import audio_observation
from render_cases import instrument

KICK, SNARE, HAT, CLAP = range(4)
Q = 48


# ----------------------------------------------------------------- input documents
def kit(ctx):
    return [instrument(ctx, 'kick.wav', 0, name='Kick'), instrument(ctx, 'snare.wav', 1, name='Snare'),
            instrument(ctx, 'hat.wav', 2, name='Hat'), instrument(ctx, 'click.wav', 3, name='Clap')]


def beat(ctx):
    return S.Song(kit(ctx), [S.Pattern('Verse'), S.Pattern('Fill')], sequence=[['Verse']], name='Beat', mode='pattern',
                  author='verifier', license='CC0').xml()


def groove(ctx):
    verse = [S.Note(0, KICK), S.Note(2 * Q, KICK), S.Note(Q, SNARE), S.Note(3 * Q, SNARE)] + \
            [S.Note(t, HAT) for t in range(0, 4 * Q, Q // 2)]
    fill = [S.Note(0, KICK)] + [S.Note(3 * Q + t, SNARE) for t in range(0, Q, Q // 4)]
    return S.Song(kit(ctx), [S.Pattern('Verse', verse), S.Pattern('Fill', fill), S.Pattern('Ending')],
                  sequence=[['Verse'], ['Verse'], ['Verse'], ['Fill']], name='Groove', mode='song').xml()


def demo(ctx):
    instruments = [instrument(ctx, 'tone220.wav', 0, name='Low'), instrument(ctx, 'tone880.wav', 1, name='High')]
    return S.Song(instruments, [S.Pattern('Intro', [S.Note(0, 0)], size=3 * Q),
                                S.Pattern('Main', [S.Note(0, 0), S.Note(2 * Q, 0), S.Note(Q, 1), S.Note(3 * Q, 1)])],
                  sequence=[['Intro'], ['Main'], ['Main']], name='Demo Song', author='Verifier', bpm=96.0,
                  mode='song').xml()


def midi_song(ctx):
    voices = [instrument(ctx, sample, index, name=name, midi_channel=channel, midi_note=pitch)
              for index, (name, sample, channel, pitch) in enumerate((
                  ('Kick', 'kick.wav', 1, 36), ('Snare', 'snare.wav', 5, 40), ('Hat', 'hat.wav', 9, 46)))]
    a = S.Pattern('Three', [S.Note(0, 0, velocity=0.9, length=48), S.Note(0, 2, velocity=0.35, length=24),
                            S.Note(48, 1, velocity=0.6, length=72), S.Note(96, 2, velocity=0.75, length=24)], size=144)
    b = S.Pattern('Four', [S.Note(24, 0, velocity=0.4, length=24), S.Note(72, 1, velocity=0.85, length=48),
                           S.Note(144, 2, velocity=0.5, length=24)])
    return S.Song(voices, [a, b], sequence=[['Three'], ['Four']], name='Mapped rhythm', bpm=105,
                  timeline=True, tempo_markers=((1, 135.0),), mode='song').xml()



def edit_song(ctx):
    return S.Song([instrument(ctx, 'tone440.wav', 0, name='Tone'),
                   instrument(ctx, 'tone880.wav', 1, name='High')],
                  [S.Pattern('Melody', [S.Note(0, 0), S.Note(48, 0), S.Note(96, 1)], size=192)],
                  sequence=[['Melody']] * 4, name='Editing', mode='song').xml()


def sample_song(ctx):
    return S.Song([instrument(ctx, 'ramp.wav', 0, name='Ramp'),
                   instrument(ctx, 'tone440.wav', 1, name='Tone')],
                  [S.Pattern('Samples', [S.Note(0, 0), S.Note(96, 1)])], name='Samples').xml()


def single(ctx, title, sample, pattern, positions):
    return S.Song([instrument(ctx, sample, 0, name='Tone')], [S.Pattern(pattern, [S.Note(p, 0) for p in positions])],
                  name=title).xml()


def roll(ctx):
    return S.pattern_file(S.Pattern('Roll', [S.Note(2 * Q + t, 1) for t in range(0, 2 * Q, Q // 4)]),
                          drumkit='Groove kit')


def drumkit(ctx):
    from drumkit_cases import kits
    return kits()[0].archive()


DOCUMENTS = {
    'beat.h2song': beat, 'groove.h2song': groove, 'demo.h2song': demo, 'midi.h2song': midi_song,
    'editing.h2song': edit_song, 'samples.h2song': sample_song,
    'first.h2song': lambda ctx: single(ctx, 'First', 'tone440.wav', 'A', (0, 2 * Q)),
    'second.h2song': lambda ctx: single(ctx, 'Second', 'tone880.wav', 'B', (0, Q, 2 * Q, 3 * Q)),
    'roll.h2pattern': roll, 'verifier.h2drumkit': drumkit,
    'pair.h2playlist': lambda c: S.playlist([c.inputs('first.h2song'), c.inputs('second.h2song')]),
}


def document(ctx, name):
    if name in DOCUMENTS:
        return DOCUMENTS[name](ctx)
    return fixtures.sample(name)


# ----------------------------------------------------------------- setup
def scripted(c, operations):
    for op in operations:
        kind = op['op']
        if kind == 'open-song':
            c.open_song(op['file'])
            expected = S.song_projection(document(c, op['file']), c.places())['song']['name']
            deadline = time.monotonic() + 15
            while c.song(op['file'])['song']['name'] != expected:
                assert time.monotonic() < deadline, 'the requested song did not open through OSC'
                time.sleep(0.3)
            time.sleep(1.0)
        else:
            raise ValueError('unknown setup operation ' + kind)


def setup(c, episode, item):
    if item['op'] == 'documents':
        for name in item['files']:
            c.upload(name, document(c, name))
    elif item['op'] == 'scripted':
        scripted(c, item['operations'])
    else:
        raise ValueError('unknown setup item ' + str(item['op']))


def prepare(c, episode, checkpoint):
    c.gui_song = None
    if checkpoint.get('preparation'):
        scripted(c, checkpoint['preparation'])


def collect(c, episode, checkpoint, windows_before):
    c.gui_song = None


# ----------------------------------------------------------------- observations
def current(c):
    """The song the application holds, saved once per checkpoint into the project area."""
    if getattr(c, 'gui_song', None) is None:
        c.gui_song = S.song_projection(c.save_song(c.unique('check', '.h2song')), c.places())
    return c.gui_song


def names(projection):
    return {i['id']: i['name'] for i in projection['instruments']}


def pattern_named(projection, name):
    found = [p for p in projection['patterns'] if p['name'] == name]
    assert found, f'the song has no pattern {name}; its patterns are {[p["name"] for p in projection["patterns"]]}'
    return found[0]


def note_rows(projection, pattern):
    ids = names(projection)
    return sorted([n['position'], ids.get(n['instrument'], 'instrument %d' % n['instrument'])]
                  for n in pattern['notes'])


def song_fields(projection, fields):
    out = {}
    for field in fields:
        if field == 'instruments':
            out[field] = [i['name'] for i in projection['instruments']]
        elif field == 'patterns':
            out[field] = [p['name'] for p in projection['patterns']]
        elif field == 'sequence':
            out[field] = projection['sequence']
        else:
            out[field] = projection['song'][field]
    return out


def pattern_notes(c, check):
    projection = current(c)
    out = {}
    for name in check['patterns']:
        pattern = pattern_named(projection, name)
        row = {'notes': note_rows(projection, pattern)}
        for field in check.get('fields', []):
            row[field] = pattern[field]
        out[name] = row
    return {'patterns': out}


def pattern_fields(c, check):
    rows = [{f: p[f] for f in check['fields']} for p in current(c)['patterns']]
    if check.get('unordered'):
        rows.sort(key=lambda row: [str(row[f]) for f in check['fields']])
    return {'patterns': rows}


def instrument_fields(c, check):
    projection = current(c)
    if not check.get('names'):
        # Which instruments the song has; where a new one is listed is not part of the goals.
        return {'instruments': sorted(i['name'] for i in projection['instruments'])}
    by_name = {}
    for item in projection['instruments']:
        by_name.setdefault(item['name'], item)
    out = {}
    for name in check['names']:
        assert name in by_name, f'the song has no instrument {name}'
        out[name] = {field: by_name[name][field] for field in check['fields']}
    return {'instruments': out}


def instrument_count(c, check):
    present = [i['name'] for i in current(c)['instruments']]
    return {'count': len(present), 'known': sorted(name for name in check['known'] if name in present)}


def layers(c, check):
    projection = current(c)
    found = [i for i in projection['instruments'] if i['name'] == check['instrument']]
    assert found, 'the song has no instrument ' + check['instrument']
    rows = []
    for component in found[0]['components']:
        rows.append([{key: layer[key] for key in ('filename', 'min', 'max', 'gain', 'pitch')}
                     for layer in component['layers']])
    return {'components': rows}


def kit_state(c, check):
    projection = current(c)
    return {'drumkit': projection['song']['drumkit'], 'instruments': [i['name'] for i in projection['instruments']]}


def timeline(c, check):
    projection = current(c)
    values = {'markers': projection['markers'], 'tags': projection['tags'],
              'timeline': projection['song']['timeline']}
    return {field: values[field] for field in check['fields']}


def file_bytes(c, check):
    return c.take(check['path'])


def file_song(c, check):
    return song_fields(S.song_projection(file_bytes(c, check), c.places()), check['fields'])


def file_pattern(c, check):
    value = S.pattern_document_projection(file_bytes(c, check))
    pattern = value['pattern']
    # (The name stored in the file follows the file name the user typed: not compared.)
    return {'size': pattern['size'], 'denominator': pattern['denominator'],
            'notes': sorted([n['position'], n['instrument']] for n in pattern['notes'])}


def file_playlist(c, check):
    return {'songs': [row['path'] for row in S.playlist_projection(file_bytes(c, check), c.places())]}


AUDIO_SPEC = {'onsets': 0.02, 'window': 2048}


def file_audio(c, check):
    if 'path' in check:
        path = check['path']
    else:
        matches = [p for p in written(c, check) if check['contains'] in p.rsplit('/', 1)[-1]]
        assert len(matches) == 1, f'expected one written file naming {check["contains"]}, found {len(matches)}'
        path = matches[0]
    data = c.take(path)
    info, frames = c.decode(data, path.rsplit('/', 1)[-1])
    value = audio_observation(info, frames, AUDIO_SPEC)
    container = value['observation']['format']['container']
    assert check['format'] in container, f'{path} is {container}, not {check["format"]}'
    if check.get('summary'):
        # Resample onto one analysis clock: the goal permits different rates/depths, but still requires the
        # rhythm, timbre and channel content. Whole-file levels alone cannot distinguish a drum part from a tone.
        return {'audio': audio.normalized_observation(info, frames)}
    return {'audio': value}


def written(c, check):
    """The files the application wrote whose names start with the prefix, once their set stops changing."""
    folder, prefix = check['folder'], check['prefix']
    deadline = time.monotonic() + 8
    seen = None
    while True:
        found = sorted(d['path'] for d in c.pending()
                       if d.get('path', '').startswith(folder + '/' + prefix))
        if found == seen and (found or time.monotonic() >= deadline):
            return found
        seen = found
        time.sleep(0.6)


def written_files(c, check):
    """Which instruments got a file of their own (the file names carry the instrument names)."""
    paths = written(c, check)
    instruments = [i['name'] for i in current(c)['instruments']]
    named = sorted(name for name in instruments if any(name in p.rsplit('/', 1)[-1] for p in paths))
    return {'count': len(paths), 'instruments': named}


def vlq(data, at):
    value = 0
    while True:
        byte = data[at]
        at += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, at


def midi_projection(data):
    """Standard MIDI file: header, and per track its name, tempo and meter changes, notes on and off."""
    if data[:4] != b'MThd':
        raise AssertionError('the file is not a standard MIDI file')
    length = struct.unpack('>I', data[4:8])[0]
    fmt, count, division = struct.unpack('>HHH', data[8:14])
    at = 8 + length
    tracks = []
    while at + 8 <= len(data) and len(tracks) < count:
        kind, size = data[at:at + 4], struct.unpack('>I', data[at + 4:at + 8])[0]
        body = data[at + 8:at + 8 + size]
        at += 8 + size
        if kind != b'MTrk':
            continue
        track = {'name': '', 'tempo': [], 'meter': [], 'on': [], 'off': []}
        pos, tick, status = 0, 0, 0
        try:
            while pos < len(body):
                delta, pos = vlq(body, pos)
                tick += delta
                if body[pos] & 0x80:
                    status = body[pos]
                    pos += 1
                if status == 0xFF:
                    meta = body[pos]
                    size, pos = vlq(body, pos + 1)
                    payload = body[pos:pos + size]
                    pos += size
                    if meta == 0x03:
                        track['name'] = payload.decode('latin-1')
                    elif meta == 0x51:
                        track['tempo'].append([tick, int.from_bytes(payload, 'big')])
                    elif meta == 0x58:
                        track['meter'].append([tick, *payload[:2]])
                    elif meta == 0x2F:
                        break
                elif status in (0xF0, 0xF7):
                    size, pos = vlq(body, pos)
                    pos += size
                else:
                    kind = status & 0xF0
                    width = 1 if kind in (0xC0, 0xD0) else 2
                    args = body[pos:pos + width]
                    pos += width
                    if kind == 0x90 and args[1] > 0:
                        track['on'].append([tick, status & 0x0F, args[0], args[1]])
                    elif kind == 0x80 or (kind == 0x90 and args[1] == 0):
                        track['off'].append([tick, status & 0x0F, args[0]])
        except IndexError:
            raise AssertionError('a MIDI track is truncated') from None
        tracks.append(track)
    assert len(tracks) == count, f'the MIDI header names {count} tracks, the file holds {len(tracks)}'
    assert 0 < division < 32768, 'MIDI must use a positive quarter-note time division'
    tempo, meter, voices = set(), set(), []
    for track in tracks:
        for key, target in (('tempo', tempo), ('meter', meter)):
            target.update((round(row[0] / division, 8), *row[1:]) for row in track[key])
        if track['on'] or track['off']:
            voices.append({key: sorted([round(row[0] / division, 8), *row[1:]] for row in track[key])
                           for key in ('on', 'off')})
    # Track labels, empty bookkeeping tracks, PPQN and the order of simultaneous events do not change music.
    voices.sort(key=lambda track: (track['on'], track['off']))
    return {'tempo': sorted(map(list, tempo)), 'meter': sorted(map(list, meter)), 'tracks': voices}


def file_midi(c, check):
    return midi_projection(file_bytes(c, check))


def file_text(c, check):
    text = file_bytes(c, check).decode('utf-8')
    return lilypond_projection(text)


def lilypond_projection(text):
    """LilyPond musical tokens, without formatting, comments or generator bookkeeping."""
    tokens = re.findall(r'%\{.*?%\}|%[^\n]*|;[^\n]*|"(?:\\.|[^"\\])*"|\\[A-Za-z]+|'
                        r'[A-Za-z_][A-Za-z0-9_-]*|\d+(?:\.\d+)?|[^\s]', text, re.S)
    tokens = [token for token in tokens if not token.startswith(('%', ';'))]
    result, index = [], 0
    while index < len(tokens):
        if tokens[index] == '\\version':
            index += 2
        elif tokens[index:index + 2] == ['tagline', '=']:
            index += 3
        else:
            result.append(tokens[index])
            index += 1
    assert '\\score' in result and '\\drummode' in result, 'the file contains no drum score'
    return {'tokens': result}


def newest(c, folder, suffix, wait=12):
    """The path of the file with this suffix that the application wrote last into a document area."""
    deadline = time.monotonic() + wait
    while True:
        found = [d['path'] for d in c.pending() if d.get('path', '').startswith(folder + '/')
                 and d['path'].endswith(suffix)]
        if found:
            return found[-1]
        if time.monotonic() >= deadline:
            raise AssertionError(f'no {suffix} file was written into {folder}')
        time.sleep(0.3)


def file_drumkit(c, check):
    data = c.take(check['path'] if 'path' in check else newest(c, check['folder'], check['suffix']))
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as tar:
            members = {m.name: (tar.extractfile(m).read() if m.isreg() else None) for m in tar.getmembers()}
    except (tarfile.TarError, OSError, EOFError):
        raise AssertionError('the drum kit file is not a readable tar archive') from None
    files = sorted(name for name, body in members.items() if body is not None)
    xml = [name for name in files if name.endswith('drumkit.xml')]
    assert xml, 'the archive holds no drumkit.xml'
    kit_value = S.drumkit_projection(members[xml[0]], c.places())
    if check.get('metadata'):
        kit_value['info'] = rich_text(kit_value['info'])
    # Files relative to the kit folder: the folder's own name is derived from the kit name by the product.
    inside = sorted(name.split('/', 1)[1] if '/' in name else name for name in files)
    samples = {}
    for item in kit_value['instruments']:
        for component in item['components']:
            for layer in component['layers']:
                filename = layer['filename'].rsplit('/', 1)[-1]
                matches = [name for name in files if name.rsplit('/', 1)[-1] == filename]
                assert len(matches) == 1, 'the archive must contain the sample ' + filename
                info, frames = c.decode(members[matches[0]], filename)
                assert len(frames), 'the archived sample is empty: ' + filename
                samples[filename] = audio.normalized_observation(info, frames)
    return {'files': inside, 'name': kit_value['name'],
            **({key: kit_value[key] for key in ('author', 'info', 'license')} if check.get('metadata') else {}),
            'samples': samples,
            'instruments': [[i['name'], [[layer['filename'] for layer in component['layers']]
                                         for component in i['components']]] for i in kit_value['instruments']]}


def rich_text(value):
    """The visible information text; Qt's exported HTML styling is not part of the goal."""
    class Reader(HTMLParser):
        def __init__(self):
            super().__init__()
            self.skip, self.parts = False, []

        def handle_starttag(self, tag, attrs):
            if tag == 'head':
                self.skip = True

        def handle_endtag(self, tag):
            if tag == 'head':
                self.skip = False

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)
    reader = Reader()
    reader.feed(value)
    return ' '.join(' '.join(reader.parts).split())



def detailed_notes(c, check):
    projection = current(c)
    pattern = pattern_named(projection, check['pattern'])
    ids = names(projection)
    fields = check['fields']
    rows = [[n['position'], ids[n['instrument']], *[n[f] for f in fields]] for n in pattern['notes']
            if not check.get('instrument') or ids[n['instrument']] == check['instrument']]
    value = {'notes': sorted(rows, key=lambda row: repr(row))}
    return {'value': value, 'tolerance': {'abs': 0.03, 'rel': 0.0}}


def sample_settings(c, check):
    voice = next((i for i in current(c)['instruments'] if i['name'] == check['instrument']), None)
    assert voice, 'missing instrument ' + check['instrument']
    layer = voice['components'][0]['layers'][0]
    value = {field: layer[field] for field in check['fields']}
    if any(field in ('volume', 'pan') for field in value):
        for field in ('volume', 'pan'):
            if field in value:
                value[field] = [[round(x / 841, 4), round(1 - y / 91, 4)] for x, y in value[field]]
        return {'value': value, 'tolerance': {'abs': 0.05, 'rel': 0.0}}
    return value


def rendered_song(c, check):
    name = c.unique('edited', '.h2song')
    c.save_song(name)
    filename = c.unique('edited', '.wav')
    # Render the product's own project directly. Re-uploading candidate output as a verifier fixture would
    # misclassify a malformed saved document as an infrastructure fault instead of a failed product check.
    reply = c.cli('export', song=c.areas()['projects'] + '/' + name, output=filename)
    info, frames = c.decode(c.take('outputs/' + filename, reply.get('downloads')), filename)
    return {'audio': audio_observation(info, frames, check.get('spec', {'window': 2205, 'bands': True}),
                                       {'frames': 1024, 'level': (0.012, 0.08), 'bands': 0.05, 'onsets': 220})}


def settings(c, check):
    body = c.take(check['path']).decode('utf-8') if check.get('path') else c.settings()
    out = {}
    for key in check['keys']:
        match = re.search(rf'<{key}>([^<]*)</{key}>', body)
        assert match, f'the settings file has no {key}'
        out[key] = match.group(1)
    return out


OBSERVERS = {
    'song': lambda c, check: song_fields(current(c), check['fields']),
    'pattern-notes': pattern_notes,
    'patterns': pattern_fields,
    'pattern-present': lambda c, check: {'present': pattern_named(current(c), check['name'])['name']},
    'sequence': lambda c, check: {'sequence': current(c)['sequence']},
    'virtual': lambda c, check: {'virtual': current(c)['virtual']},
    'timeline': timeline,
    'instruments': instrument_fields,
    'instrument-count': instrument_count,
    'layers': layers,
    'kit': kit_state,
    'file-song': file_song,
    'file-pattern': file_pattern,
    'file-playlist': file_playlist,
    'file-audio': file_audio,
    'files': written_files,
    'file-midi': file_midi,
    'file-text': file_text,
    'file-drumkit': file_drumkit,
    'settings': settings,
    'file-xml-fields': settings,
    'detailed-notes': detailed_notes,
    'sample-settings': sample_settings,
    'rendered-song': rendered_song,
    'automation': lambda c, check: {'value': {'points': current(c)['velocity_path']},
                                    'tolerance': {'abs': 0.04, 'rel': 0.0}},
}


def observe(c, episode, checkpoint, check):
    value = OBSERVERS[check['kind']](c, check)
    if set(value) == {'value', 'tolerance'}:
        # An observation compared within its own tolerance (harness.compare).
        return value
    result = {'kind': check['kind'], **value}
    if 'tolerance' in check:
        return {'value': result, 'tolerance': {'abs': check['tolerance'], 'rel': 0.0}}
    return result
