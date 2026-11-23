'''Projections of MuseScore Studio outputs: MusicXML, MIDI, mscx and mscz, score metadata, element JSON and audio.

Each function turns product bytes into plain JSON data that holds only what the format defines. Layout, identifiers,
dates, platform values and software banners are dropped, so an independent implementation that behaves the same lands
on an equal projection; everything else stays exact. A malformed input raises SemanticError, which fails only the point
that asked for it.
'''
from __future__ import annotations

import io
import json
import math
import os
import re
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction
from pathlib import Path

FLOAT_TOLERANCE = 0.005


class SemanticError(AssertionError):
    '''An output that is not what its format requires.'''


def words_of(value):
    return ' '.join((value or '').split())


def text(node, path, default=None):
    found = node.find(path)
    if found is None or found.text is None:
        return default
    return words_of(found.text)


def number(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return value


def parse_xml(data):
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise SemanticError('not well-formed XML: ' + str(exc)[:80]) from None


# -- MusicXML ---------------------------------------------------------------------------------------------------
def fraction(value, divisions):
    return str(Fraction(int(value), divisions))


def attributes_item(node):
    item = {'t': 'attributes'}
    for name, path in (('fifths', 'key/fifths'), ('mode', 'key/mode'), ('beats', 'time/beats'),
                       ('beat-type', 'time/beat-type'), ('staves', 'staves')):
        value = text(node, path)
        if value is not None:
            item[name] = value
    clefs = [[clef.get('number', '1'), text(clef, 'sign'), text(clef, 'line')] for clef in node.findall('clef')]
    if clefs:
        item['clefs'] = clefs
    transpose = node.find('transpose')
    if transpose is not None:
        item['transpose'] = [int(text(transpose, 'diatonic', '0')), int(text(transpose, 'chromatic', '0'))]
    return item


def note_item(note, divisions):
    rest = note.find('rest')
    item = {'t': 'rest' if rest is not None else 'note'}
    if rest is not None and rest.get('measure') == 'yes':
        item['measure_rest'] = True
    if note.find('chord') is not None:
        item['chord'] = True
    if note.find('grace') is not None:
        item['grace'] = True
    pitch = note.find('pitch')
    if pitch is not None:
        item['pitch'] = [text(pitch, 'step'), int(float(text(pitch, 'alter', '0'))), int(text(pitch, 'octave', '0'))]
    duration = text(note, 'duration')
    if duration is not None:
        item['duration'] = fraction(duration, divisions)
    for name in ('voice', 'type', 'staff', 'accidental'):
        value = text(note, name)
        if value is not None:
            item[name] = value
    if note.findall('dot'):
        item['dots'] = len(note.findall('dot'))
    modification = note.find('time-modification')
    if modification is not None:
        item['tuplet'] = [text(modification, 'actual-notes'), text(modification, 'normal-notes')]
    ties = sorted(tie.get('type') for tie in note.findall('tie'))
    if ties:
        item['ties'] = ties
    notations = note.find('notations')
    if notations is not None:
        marks = sorted(mark.tag for group in notations.findall('articulations') for mark in group)
        if marks:
            item['articulations'] = marks
        brackets = [bracket.get('type') for bracket in notations.findall('tuplet')]
        if brackets:
            item['tuplet_brackets'] = brackets
        slurs = sorted(slur.get('type') for slur in notations.findall('slur'))
        if slurs:
            item['slurs'] = slurs
        if notations.find('fermata') is not None:
            item['fermata'] = True
    lyrics = [[lyric.get('number', '1'), text(lyric, 'syllabic'), text(lyric, 'text')]
              + (['extend'] if lyric.find('extend') is not None else []) for lyric in note.findall('lyric')]
    if lyrics:
        item['lyrics'] = lyrics
    return item


def direction_item(node):
    item = {'t': 'direction'}
    dynamics = [mark.tag for group in node.findall('direction-type/dynamics') for mark in group]
    if dynamics:
        item['dynamics'] = dynamics
    shown = [words_of(words.text) for words in node.findall('direction-type/words')]
    if shown:
        item['words'] = shown
    metronome = node.find('direction-type/metronome')
    if metronome is not None:
        item['metronome'] = [text(metronome, 'beat-unit'), number(text(metronome, 'per-minute'))]
    for name in ('segno', 'coda'):
        if node.find('direction-type/' + name) is not None:
            item[name] = True
    wedges = [wedge.get('type') for wedge in node.findall('direction-type/wedge')]
    if wedges:
        item['wedges'] = wedges
    sound = node.find('sound')
    if sound is not None and sound.get('tempo'):
        item['tempo'] = number(sound.get('tempo'))
    if sound is not None:
        jumps = sorted(name for name in ('dalsegno', 'dacapo', 'tocoda', 'fine') if sound.get(name) is not None)
        if jumps:
            item['jumps'] = jumps
    return item if len(item) > 1 else None


def harmony_item(node):
    root = node.find('root')
    item = {'t': 'harmony', 'kind': text(node, 'kind')}
    if root is not None:
        item['root'] = [text(root, 'root-step'), int(float(text(root, 'root-alter', '0')))]
    return item


def barline_item(node):
    item = {'t': 'barline', 'location': node.get('location', 'right')}
    style = text(node, 'bar-style')
    if style:
        item['style'] = style
    repeat = node.find('repeat')
    if repeat is not None:
        item['repeat'] = repeat.get('direction')
    ending = node.find('ending')
    if ending is not None:
        item['ending'] = [ending.get('number'), ending.get('type')]
    return item


def musicxml_project(data):
    root = parse_xml(data)
    if root.tag != 'score-partwise':
        raise SemanticError('the root element is ' + root.tag + ', not score-partwise')
    names = {sp.get('id'): text(sp, 'part-name') for sp in root.findall('part-list/score-part')}
    people = {creator.get('type'): words_of(creator.text) for creator in root.findall('identification/creator')}
    parts = []
    for part in root.findall('part'):
        divisions, measures = 1, []
        for measure in part.findall('measure'):
            items = []
            for child in measure:
                tag = child.tag
                if tag == 'attributes':
                    value = text(child, 'divisions')
                    if value:
                        divisions = int(value)
                    item = attributes_item(child)
                    if len(item) > 1:
                        items.append(item)
                elif tag == 'note':
                    items.append(note_item(child, divisions))
                elif tag == 'direction':
                    item = direction_item(child)
                    if item:
                        items.append(item)
                elif tag == 'barline':
                    items.append(barline_item(child))
                elif tag == 'harmony':
                    items.append(harmony_item(child))
                elif tag in ('backup', 'forward'):
                    items.append({'t': tag, 'duration': fraction(text(child, 'duration', '0'), divisions)})
            measures.append({'number': measure.get('number'), 'items': items})
        parts.append({'name': names.get(part.get('id')), 'measures': measures})
    return {'title': text(root, 'work/work-title'), 'movement': text(root, 'movement-title'), 'people': people,
            'rights': text(root, 'identification/rights'), 'parts': parts}


# -- MIDI --------------------------------------------------------------------------------------------------------
def vlq(body, pos):
    value = 0
    while True:
        byte = body[pos]
        pos += 1
        value = (value << 7) | (byte & 127)
        if not byte & 128:
            return value, pos


def midi_track(body):
    pos, tick, status = 0, 0, 0
    name, tempos, signatures, keys, programs = None, [], [], [], set()
    open_notes, notes, stray = {}, [], 0
    while pos < len(body):
        delta, pos = vlq(body, pos)
        tick += delta
        byte = body[pos]
        if byte == 255:
            kind, size = body[pos + 1], body[pos + 2]
            data = body[pos + 3:pos + 3 + size]
            pos += 3 + size
            if kind == 3 and name is None:
                name = data.decode('latin-1')
            elif kind == 81 and size == 3:
                tempos.append([tick, round(60000000 / int.from_bytes(data, 'big'), 2)])
            elif kind == 88 and size >= 2:
                signatures.append([tick, data[0], 2 ** data[1]])
            elif kind == 89 and size == 2:
                keys.append([tick, struct.unpack('b', data[:1])[0], data[1]])
            continue
        if byte in (240, 247):
            size, pos = vlq(body, pos + 1)
            pos += size
            continue
        if byte & 128:
            status = byte
            pos += 1
        if not status:
            raise SemanticError('a MIDI event without a status byte')
        kind, channel = status >> 4, status & 15
        size = 1 if kind in (12, 13) else 2
        args = body[pos:pos + size]
        pos += size
        if len(args) < size:
            raise SemanticError('truncated MIDI event')
        if kind == 12:
            programs.add((channel, args[0]))
        elif kind == 9 and args[1] > 0:
            open_notes.setdefault((channel, args[0]), []).append((tick, args[1]))
        elif kind == 8 or (kind == 9 and args[1] == 0):
            queue = open_notes.get((channel, args[0]))
            if queue:
                start, velocity = queue.pop(0)
                notes.append([start, tick - start, args[0], velocity, channel])
            else:
                stray += 1
    return {'name': name, 'notes': sorted(notes), 'programs': sorted([c, p] for c, p in programs),
            'tempos': tempos, 'timesigs': signatures, 'keys': keys,
            'unfinished': sum(len(queue) for queue in open_notes.values()), 'stray_offs': stray}


def midi_project(data):
    if data[:4] != b'MThd' or len(data) < 14:
        raise SemanticError('not a MIDI file')
    fmt, count, division = struct.unpack('>HHH', data[8:14])
    pos, tracks = 14, []
    try:
        for _ in range(count):
            if data[pos:pos + 4] != b'MTrk':
                raise SemanticError('missing track chunk')
            size = struct.unpack('>I', data[pos + 4:pos + 8])[0]
            tracks.append(midi_track(data[pos + 8:pos + 8 + size]))
            pos += 8 + size
    except (IndexError, struct.error):
        raise SemanticError('truncated MIDI file') from None
    return {'format': fmt, 'division': division, 'tracks': tracks}


# -- mscx and mscz -------------------------------------------------------------------------------------------------
def strip(node):
    item = [node.tag]
    if node.attrib:
        item.append(dict(sorted(node.attrib.items())))
    body = words_of(node.text)
    children = [strip(child) for child in node if child.tag != 'eid']
    if body:
        item.append(body)
    if children:
        item.append(children)
    return item


def mscx_project(data):
    root = parse_xml(data)
    score = root.find('Score')
    if root.tag != 'museScore' or score is None:
        raise SemanticError('not a MuseScore score document')
    tags = {tag.get('name'): words_of(tag.text) for tag in score.findall('metaTag')
            if tag.get('name') not in ('creationDate', 'platform') and words_of(tag.text)}
    parts = []
    for part in score.findall('Part'):
        instrument = part.find('Instrument')
        parts.append({'trackName': text(part, 'trackName'), 'instrument': instrument.get('id') if instrument is not None else None,
                      'longName': text(part, 'Instrument/longName'), 'instrumentId': text(part, 'Instrument/instrumentId'),
                      'staves': len(part.findall('Staff'))})
    staves = [{'id': staff.get('id'), 'content': [strip(child) for child in staff if child.tag != 'eid']}
              for staff in score.findall('Staff')]
    other = [strip(child) for child in score if child.tag not in ('Part', 'Staff', 'metaTag', 'eid')]
    return {'version': root.get('version'), 'tags': tags, 'parts': parts, 'staves': staves, 'other': other}


def mscz_project(data):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise SemanticError('not a zip archive') from None
    with archive:
        names = sorted(archive.namelist())
        members = [name for name in names if name.endswith('.mscx') and '/' not in name]
        if len(members) != 1:
            raise SemanticError('an mscz holds exactly one top-level mscx document')
        # The score document is named after the output file, which never belongs to the observation.
        return {'entries': ['score.mscx' if name == members[0] else name for name in names if not name.startswith('Thumbnails/')],
                'score': mscx_project(archive.read(members[0]))}


# -- metadata and element JSON -------------------------------------------------------------------------------------
def meta_project(stdout):
    try:
        data = json.loads(stdout)
    except ValueError:
        raise SemanticError('the metadata output is not JSON') from None
    if not isinstance(data, dict) or not isinstance(data.get('metadata'), dict):
        raise SemanticError('the metadata output has no metadata object')
    return data['metadata']


def element_key(element):
    return [element.get('measureIdx', -1), element.get('staffIdx', -1), element.get('voiceIdx', -1),
            element.get('beat', -1), json.dumps(element, sort_keys=True)]


def elements_project(stdout):
    try:
        data = json.loads(stdout)
    except ValueError:
        raise SemanticError('the elements output is not JSON') from None
    if not isinstance(data, list) or not all(isinstance(part, dict) for part in data):
        raise SemanticError('the elements output is not a list of parts')
    return [{'partId': part.get('partId'), 'instrumentId': part.get('instrumentId'),
             'elements': sorted(part.get('elements', []), key=element_key)} for part in data]


# -- audio -----------------------------------------------------------------------------------------------------------
def run_tool(args):
    done = subprocess.run(args, capture_output=True, timeout=120)
    if done.returncode != 0:
        raise SemanticError('decoder failed: ' + done.stderr.decode('utf-8', 'replace')[-160:])
    return done.stdout


# Audio is compared as music, not as samples: the format facts exactly, the length within LENGTH_SECONDS, and per
# 50 ms frame the strongest pitches (harmonic sum over a semitone grid) and the level relative to the loudest frame.
# A rendering with other instruments but the same notes, timing and dynamics lands within the rules of audio_compare.
AUDIO_RATE = 22050
AUDIO_HOP = 0.05
AUDIO_SIZE = 4096
AUDIO_FLOOR_DB = -30.0
AUDIO_MIDI = (28, 100)


def audio_pitches(x):
    '''Per frame: up to four [midi, strength] pairs (strength relative to the strongest pitch), the frame levels and the peak level.'''
    import numpy
    hop = int(AUDIO_RATE * AUDIO_HOP)
    window = numpy.hanning(AUDIO_SIZE)
    midis = numpy.arange(*AUDIO_MIDI)
    f0 = 440.0 * 2 ** ((midis - 69) / 12)
    pad = numpy.concatenate([numpy.zeros(AUDIO_SIZE // 2), x, numpy.zeros(AUDIO_SIZE)])
    centre = AUDIO_SIZE // 2
    level = numpy.array([numpy.sqrt(numpy.mean(pad[s + centre - hop // 2:s + centre + hop // 2] ** 2) + 1e-20)
                         for s in range(0, len(x), hop)])
    peak = float(level.max()) if len(level) else 0.0
    frames = []
    for index, start in enumerate(range(0, len(x), hop)):
        if peak <= 0 or 20 * math.log10(level[index] / peak) < AUDIO_FLOOR_DB:
            frames.append([])
            continue
        work = numpy.abs(numpy.fft.rfft(pad[start:start + AUDIO_SIZE] * window))
        chosen, first = [], None
        for _ in range(4):
            salience = numpy.zeros(len(midis))
            for k in range(1, 5):
                bins = numpy.round(f0 * k * AUDIO_SIZE / AUDIO_RATE).astype(int)
                ok = bins < len(work)
                salience[ok] += (0.8 ** (k - 1)) * work[bins[ok]]
            best = int(numpy.argmax(salience))
            first = salience[best] if first is None else first
            if first <= 0 or salience[best] < 0.1 * first:
                break
            chosen.append([int(midis[best]), round(float(salience[best] / first), 1)])
            for k in range(1, 5):
                middle = int(round(f0[best] * k * AUDIO_SIZE / AUDIO_RATE))
                work[max(0, middle - 3):middle + 4] = 0.0
        frames.append(chosen)
    return frames, level, peak


def audio_project(data, suffix):
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as work:
        path = Path(work) / ('audio' + suffix)
        path.write_bytes(data)
        probe = json.loads(run_tool(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries',
                                     'stream=codec_name,sample_rate,channels,sample_fmt,bit_rate', '-of', 'json', str(path)]))
        streams = probe.get('streams') or []
        if not streams:
            raise SemanticError('no audio stream')
        stream = streams[0]
        native = run_tool(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-'])
        mono = run_tool(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', str(AUDIO_RATE), '-'])
    import numpy
    codec = stream['codec_name']
    try:
        result = {'observation': 'audio', 'codec': codec, 'rate': int(stream['sample_rate']),
                  'channels': int(stream['channels'])}
    except (KeyError, TypeError, ValueError):
        raise SemanticError('the audio stream has no rate or channel count') from None
    if codec.startswith('pcm') or codec == 'flac':
        result['sample_format'] = stream.get('sample_fmt')
    if codec == 'mp3':
        result['bit_rate'] = int(stream.get('bit_rate') or 0)
    result['seconds'] = round(len(native) / 4 / result['rate'], 3)
    frames, level, peak = audio_pitches(numpy.frombuffer(mono, dtype='<f4').astype('float64'))
    result['peak_dbfs'] = round(20 * math.log10(peak + 1e-12), 1)
    result['db'] = [max(-99, int(round(20 * math.log10(value / peak)))) if peak > 0 else -99 for value in level]
    result['pitches'] = frames
    return result


# -- comparison ------------------------------------------------------------------------------------------------------
def walk(actual, expected, path):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise SemanticError(path + ': expected an object')
        if set(actual) != set(expected):
            raise SemanticError(path + ': keys differ ' + str(sorted(set(actual) ^ set(expected)))[:120])
        for key in expected:
            walk(actual[key], expected[key], path + '.' + str(key))
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise SemanticError(path + ': list shape differs')
        for index, (left, right) in enumerate(zip(actual, expected)):
            walk(left, right, path + '[' + str(index) + ']')
        return
    if isinstance(expected, bool) or isinstance(actual, bool):
        if actual is not expected:
            raise SemanticError(path + ': ' + repr(actual) + ' != ' + repr(expected))
        return
    if isinstance(expected, (int, float)):
        if not isinstance(actual, (int, float)) or not math.isfinite(actual):
            raise SemanticError(path + ': expected a finite number')
        limit = 0.0 if isinstance(expected, int) and isinstance(actual, int) else FLOAT_TOLERANCE
        if abs(actual - expected) > limit + 1e-9:
            raise SemanticError(path + ': ' + repr(actual) + ' != ' + repr(expected))
        return
    if actual != expected:
        raise SemanticError(path + ': ' + repr(actual)[:80] + ' != ' + repr(expected)[:80])


AUDIO_FORMAT = ('observation', 'codec', 'rate', 'channels', 'sample_format', 'bit_rate')
AUDIO_SCORED_DB = -20
AUDIO_SILENT_DBFS = -60
AUDIO_MIN_FRAMES = 4
AUDIO_SHARE = 0.7
AUDIO_START_SECONDS = 0.2
AUDIO_LENGTH_SECONDS = 0.15
AUDIO_LEVEL_DB = 10
AUDIO_ATTACK_FRAMES = 6
AUDIO_ONSET_FRAMES = 4


def audio_runs(expected):
    '''Runs of at least AUDIO_MIN_FRAMES frames of the recording with the same strongest pitch class and the same set
    of strong pitch classes, where it sounds within AUDIO_SCORED_DB of its loudest frame: the notes and chords.'''
    out, current = [], None
    for index, (pitches, db) in enumerate(zip(expected['pitches'], expected['db'])):
        key = ((pitches[0][0] % 12,) + tuple(sorted({p % 12 for p, strength in pitches if strength >= 0.5}))
               if pitches and db >= AUDIO_SCORED_DB else None)
        if key is not None and current is not None and current[0] == key:
            current[2] = index + 1
            continue
        if current is not None:
            out.append(current)
        current = [key, index, index + 1] if key is not None else None
    if current is not None:
        out.append(current)
    return [item for item in out if item[2] - item[1] >= AUDIO_MIN_FRAMES]


def first_sound(item):
    found = [i for i, (p, db) in enumerate(zip(item['pitches'], item['db'])) if p and db >= AUDIO_SCORED_DB]
    return found[0] * AUDIO_HOP if found else None


def audio_compare(actual, expected):
    '''Format facts exact; length within AUDIO_LENGTH_SECONDS; the first sound within AUDIO_START_SECONDS; for every note
    run of the recording: one of its pitch classes heard in AUDIO_SHARE of its frames, each pitch class that enters
    heard at its onset, one of its pitches in the recorded octave, and its loudest frame within AUDIO_LEVEL_DB of the
    recorded level (both relative to the loudest frame of the rendering).'''
    for key in ('pitches', 'db', 'seconds', 'peak_dbfs'):
        if not isinstance(actual.get(key), type(expected[key])):
            raise SemanticError('expected an audio observation')
    for key in AUDIO_FORMAT:
        if actual.get(key) != expected.get(key):
            raise SemanticError('audio %s: %r != %r' % (key, actual.get(key), expected.get(key)))
    if abs(actual['seconds'] - expected['seconds']) > AUDIO_LENGTH_SECONDS:
        raise SemanticError('audio length %.3f s != %.3f s' % (actual['seconds'], expected['seconds']))
    if actual['peak_dbfs'] < AUDIO_SILENT_DBFS:
        raise SemanticError('audio is silent')
    reference, got = first_sound(expected), first_sound(actual)
    if got is None:
        raise SemanticError('audio has no pitched sound')
    if abs(got - reference) > AUDIO_START_SECONDS:
        raise SemanticError('audio starts sounding at %.2f s, not %.2f s' % (got, reference))
    previous = set()
    for key, begin, end in audio_runs(expected):
        span = range(begin, min(end, len(actual['pitches'])))
        heard = {i: {p % 12 for p, _strength in actual['pitches'][i]} for i in span}
        chord = set(key)
        if sum(1 for i in span if chord & heard[i]) < AUDIO_SHARE * (end - begin):
            raise SemanticError('audio pitch classes %s at %.2f s are not heard' % (sorted(chord), begin * AUDIO_HOP))
        onset = [i for i in span if i < begin + AUDIO_ONSET_FRAMES]
        for pitch_class in sorted(chord - previous):
            if sum(pitch_class in heard[i] for i in onset) < min(2, len(onset)):
                raise SemanticError('audio pitch class %d entering at %.2f s is not heard' % (pitch_class, begin * AUDIO_HOP))
        previous = chord
        mine = {p for i in span for p, _s in actual['pitches'][i] if p % 12 in chord}
        theirs = {p for i in range(begin, end) for p, _s in expected['pitches'][i] if p % 12 in chord}
        if not mine & theirs:
            raise SemanticError('audio at %.2f s sounds in another octave' % (begin * AUDIO_HOP))
        early = max(0, begin - AUDIO_ATTACK_FRAMES)
        mine_db = actual['db'][early:min(end, len(actual['db']))]
        if not mine_db or abs(max(mine_db) - max(expected['db'][early:end])) > AUDIO_LEVEL_DB:
            raise SemanticError('audio level at %.2f s differs by more than %d dB' % (begin * AUDIO_HOP, AUDIO_LEVEL_DB))


def compare(actual, expected):
    '''Counts, strings and shapes exact; floats within 0.005; audio by audio_compare.'''
    actual = json.loads(json.dumps(actual))
    if isinstance(expected, dict) and expected.get('observation') == 'audio':
        if not isinstance(actual, dict) or actual.get('observation') != 'audio':
            raise SemanticError('expected an audio observation')
        audio_compare(actual, expected)
        return
    walk(actual, expected, '$')


# -- compressed MusicXML, PDF, SVG and MEI ---------------------------------------------------------------------------
MEI = '{http://www.music-encoding.org/ns/mei}'
XML_ID = '{http://www.w3.org/XML/1998/namespace}id'
SVG = '{http://www.w3.org/2000/svg}'


def mxl_project(data):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise SemanticError('not a zip archive') from None
    with archive:
        names = sorted(archive.namelist())
        if 'META-INF/container.xml' not in names:
            raise SemanticError('the archive has no container description')
        roots = [node.get('full-path') for node in parse_xml(archive.read('META-INF/container.xml')).iter('rootfile')]
        if len(roots) != 1 or roots[0] not in names:
            raise SemanticError('the container does not name exactly one score document')
        return {'entries': names, 'root': roots[0], 'score': musicxml_project(archive.read(roots[0]))}


def pdf_project(data):
    '''Page count and page sizes read from the page tree; dates, fonts and byte layout are not part of the observation.'''
    if not data.startswith(b'%PDF-'):
        raise SemanticError('not a PDF document')
    pages = len(re.findall(rb'/Type\s*/Page(?![A-Za-z])', data))
    if not pages:
        raise SemanticError('the PDF document has no pages')
    boxes = {tuple(round(float(value), 1) for value in box.decode().split())
             for box in re.findall(rb'/MediaBox\s*\[([^\]]*)\]', data)}
    return {'pages': pages, 'sizes': [list(box) for box in sorted(boxes)]}


def svg_project(data):
    '''Page size, title and the number of drawn elements per class; coordinates and generator banner are dropped.'''
    root = parse_xml(data)
    if root.tag != SVG + 'svg':
        raise SemanticError('the root element is ' + root.tag + ', not svg')
    classes = {}
    for node in root.iter():
        name = node.get('class')
        if name:
            classes[name] = classes.get(name, 0) + 1
    title = root.find(SVG + 'title')
    return {'width': root.get('width'), 'height': root.get('height'), 'viewBox': root.get('viewBox'),
            'title': words_of(title.text) if title is not None else None, 'classes': classes}


def mei_node(node):
    '''One MEI element without its identifiers; attributes that point at an identifier go with them.'''
    attrs = {key: value for key, value in node.attrib.items() if key != XML_ID and not value.startswith('#')}
    item = {'tag': node.tag.removeprefix(MEI), 'attrs': attrs}
    text = words_of(node.text)
    if text:
        item['text'] = text
    children = [mei_node(child) for child in node]
    if children:
        item['children'] = children
    return item


def mei_project(data):
    root = parse_xml(data)
    if root.tag != MEI + 'mei':
        raise SemanticError('the root element is ' + root.tag + ', not mei')
    music = root.find(MEI + 'music')
    if music is None:
        raise SemanticError('the MEI document has no music element')
    title = root.find(MEI + 'meiHead/' + MEI + 'fileDesc/' + MEI + 'titleStmt/' + MEI + 'title')
    return {'version': root.get('meiversion'), 'title': words_of(''.join(title.itertext())) if title is not None else None,
            'music': mei_node(music)}


def png_project(data):
    '''Width, height and bit depth read from the image header; pixels are not part of the observation.'''
    if len(data) < 33 or not data.startswith(b'\x89PNG\r\n\x1a\n') or data[12:16] != b'IHDR':
        raise SemanticError('not a PNG image')
    width, height = struct.unpack('>II', data[16:24])
    return {'width': width, 'height': height, 'depth': data[24], 'color': data[25]}


def transposed_project(stdout):
    '''The standard output of a transposing export: the score document of the archive it carries and the page structure of the PDF it carries.'''
    import base64
    try:
        data = json.loads(stdout)
    except ValueError:
        raise SemanticError('the transposition output is not JSON') from None
    if not isinstance(data, dict):
        raise SemanticError('the transposition output is not an object')
    result = {'keys': sorted(data)}
    try:
        if 'mscz' in data:
            result['score'] = mscz_project(base64.b64decode(data['mscz']))['score']
        if 'pdf' in data:
            result['pdf'] = pdf_project(base64.b64decode(data['pdf']))
    except (ValueError, TypeError):
        raise SemanticError('the transposition output holds an invalid document') from None
    return result


def json_object(stdout, what):
    try:
        data = json.loads(stdout)
    except ValueError:
        raise SemanticError('the %s output is not JSON' % what) from None
    if not isinstance(data, dict):
        raise SemanticError('the %s output is not an object' % what)
    return data


def embedded(value, what):
    '''A document that a JSON output carries as base64.'''
    import base64
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise SemanticError('the %s output holds an invalid document' % what) from None


def version_project(stdout):
    '''The standard output of a version option: its text, without line layout.'''
    text = words_of(stdout)
    if not text:
        raise SemanticError('the version output is empty')
    return {'text': text}


def parts_project(stdout):
    '''The standard output of the score parts mode: the part names, the score document of each part and the stored open flags; identifiers are dropped.'''
    data = json_object(stdout, 'parts')
    names, files, meta = data.get('parts'), data.get('partsBin'), data.get('partsMeta')
    if not all(isinstance(item, list) for item in (names, files, meta)):
        raise SemanticError('the parts output has no part lists')
    return {'keys': sorted(data), 'parts': names, 'scores': [mscz_project(embedded(item, 'parts'))['score'] for item in files],
            'meta': [[item.get('partName'), item.get('open')] for item in meta if isinstance(item, dict)]}


def parts_pdf_project(stdout):
    '''The standard output of the score parts PDF mode: the part names, the page structure of each part PDF, of the score PDF and of the full score PDF, and the postfix; the path of the score is reduced to its file name.'''
    data = json_object(stdout, 'parts PDF')
    names, files = data.get('parts'), data.get('partsBin')
    if not isinstance(names, list) or not isinstance(files, list):
        raise SemanticError('the parts PDF output has no part lists')
    return {'keys': sorted(data), 'parts': names, 'pdfs': [pdf_project(embedded(item, 'parts PDF')) for item in files],
            'score': str(data.get('score')).rsplit('/', 1)[-1], 'scoreBin': pdf_project(embedded(data.get('scoreBin'), 'parts PDF')),
            'full': pdf_project(embedded(data.get('scoreFullBin'), 'parts PDF')), 'postfix': data.get('scoreFullPostfix')}


def media_project(stdout):
    '''The standard output of the score media mode: the kinds of media it carries, the page counts and the two position documents (element count, pages and the events with their positions); coordinates are layout and are dropped. The images, the PDF, the MIDI file, the MusicXML and the metadata equal the standalone exports and are observed there.'''
    data = json_object(stdout, 'media')
    result = {'keys': sorted(data), 'pngs': len(data.get('pngs') or []), 'svgs': len(data.get('svgs') or [])}
    for key in ('sposXML', 'mposXML'):
        root = parse_xml(embedded(data.get(key), 'media'))
        elements = list(root.iter('element'))
        events = list(root.iter('event'))
        result[key] = {'elements': len(elements), 'pages': sorted({str(item.get('page')) for item in elements}),
                       'events': [[item.get('elid'), item.get('position')] for item in events]}
    return result


def mnx_project(data):
    '''An MNX document (JSON). The product draws its object identifiers at random on every export, so every identifier
    is replaced by its order of first appearance and every string that names an identifier follows it; the rest of the
    document stays exact.'''
    try:
        document = json.loads(data)
    except ValueError:
        raise SemanticError('the MNX document is not JSON') from None
    if not isinstance(document, dict) or 'mnx' not in document:
        raise SemanticError('the MNX document has no mnx header')
    names = {}

    def collect(value):
        if isinstance(value, dict):
            identifier = value.get('id')
            if isinstance(identifier, str) and identifier not in names:
                names[identifier] = 'id%d' % len(names)
            # Key order is free in JSON: number the identifiers in sorted key order.
            for key in sorted(value):
                collect(value[key])
        elif isinstance(value, list):
            for item in value:
                collect(item)

    def rename(value):
        if isinstance(value, dict):
            return {key: rename(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rename(item) for item in value]
        if isinstance(value, str):
            return names.get(value, value)
        return value
    collect(document)
    return rename(document)


LRC_LINE = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)')
LRC_TAG = re.compile(r'\[([a-z]+):(.*)\]')


def lrc_project(data):
    '''A lyrics file (LRC): its ID tags, and per line its time in seconds and its text (enhanced word times included).'''
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise SemanticError('the lyrics file is not UTF-8 text') from None
    lines, tags = [], []
    for line in text.splitlines():
        if not line.strip():
            continue
        match = LRC_LINE.fullmatch(line.strip())
        if match is None:
            tag = LRC_TAG.fullmatch(line.strip())
            if tag is None:
                raise SemanticError('not a timed lyrics line: ' + line[:60])
            tags.append([tag.group(1), words_of(tag.group(2))])
            continue
        lines.append([round(int(match.group(1)) * 60 + float(match.group(2)), 2), words_of(match.group(3))])
    if not lines:
        raise SemanticError('the lyrics file has no lines')
    return {'tags': tags, 'lines': lines}


__all__ = ['SemanticError', 'audio_project', 'compare', 'elements_project', 'lrc_project', 'meta_project', 'mei_project',
           'media_project', 'midi_project', 'mnx_project', 'mscx_project', 'mscz_project', 'musicxml_project', 'mxl_project',
           'parts_pdf_project', 'parts_project', 'pdf_project', 'png_project', 'svg_project', 'transposed_project',
           'version_project']
