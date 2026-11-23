"""Verifier-made Hydrogen documents: songs, patterns, drumkits, playlists, and the projections of saved ones.

Builders write the XML the way Hydrogen 1.2.x stores it (element names and nesting of the product's own saves);
optional legacy forms (pan_L/pan_R, drumkitLookup, no components, key/octave spellings) are produced on request so
that the same builder exercises the product's readers of older files. Projections parse a saved document into the
semantic values a point compares: numbers rounded, file locations reduced to tokens, no generated identifiers.
"""
from __future__ import annotations

import dataclasses
import io
import os
import tarfile
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath
from xml.sax.saxutils import escape

PAN_LAWS = ('RATIO_STRAIGHT_POLYGONAL', 'RATIO_CONST_POWER', 'RATIO_CONST_SUM', 'LINEAR_STRAIGHT_POLYGONAL',
            'LINEAR_CONST_POWER', 'LINEAR_CONST_SUM', 'POLAR_STRAIGHT_POLYGONAL', 'POLAR_CONST_POWER',
            'POLAR_CONST_SUM', 'QUADRATIC_STRAIGHT_POLYGONAL', 'QUADRATIC_CONST_POWER', 'QUADRATIC_CONST_SUM',
            'LINEAR_CONST_K_NORM', 'POLAR_CONST_K_NORM', 'RATIO_CONST_K_NORM', 'QUADRATIC_CONST_K_NORM')


def number(value):
    """A float the way Qt writes it (shortest form, no trailing zeros)."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    text = repr(float(value))
    if text.endswith('.0'):
        text = text[:-2]
    return text


def element(name, value, indent):
    if value is None:
        return ''
    if isinstance(value, bool):
        text = 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        text = number(value)
    else:
        text = escape(str(value))
    pad = ' ' * indent
    return f'{pad}<{name}>{text}</{name}>\n' if text != '' else f'{pad}<{name}/>\n'


@dataclasses.dataclass
class Layer:
    filename: str
    min: float = 0.0
    max: float = 1.0
    gain: float = 1.0
    pitch: float = 0.0
    modified: bool = False
    smode: str = 'forward'
    startframe: int = 0
    loopframe: int = 0
    loops: int = 0
    endframe: int = 0
    rubber: int = 0
    rubberdivider: float = 1.0
    rubbersettings: int = 4
    rubberpitch: float = 0.0
    volume_envelope: tuple = ()
    pan_envelope: tuple = ()

    def xml(self, indent, full=True):
        out = ' ' * indent + '<layer>\n'
        i = indent + 1
        out += element('filename', self.filename, i)
        if full:
            out += element('ismodified', self.modified, i)
            out += element('smode', self.smode, i)
            out += element('startframe', self.startframe, i)
            out += element('loopframe', self.loopframe, i)
            out += element('loops', self.loops, i)
            out += element('endframe', self.endframe, i)
            out += element('userubber', self.rubber, i)
            out += element('rubberdivider', self.rubberdivider, i)
            out += element('rubberCsettings', self.rubbersettings, i)
            out += element('rubberPitch', self.rubberpitch, i)
        out += element('min', self.min, i) + element('max', self.max, i)
        out += element('gain', self.gain, i) + element('pitch', self.pitch, i)
        if full:
            for frame, value in self.volume_envelope:
                out += ' ' * i + f'<volume>\n{element("volume-position", frame, i + 1)}' \
                       f'{element("volume-value", value, i + 1)}' + ' ' * i + '</volume>\n'
            for frame, value in self.pan_envelope:
                out += ' ' * i + f'<pan>\n{element("pan-position", frame, i + 1)}' \
                       f'{element("pan-value", value, i + 1)}' + ' ' * i + '</pan>\n'
        return out + ' ' * indent + '</layer>\n'


@dataclasses.dataclass
class Component:
    layers: list
    id: int = 0
    gain: float = 1.0

    def xml(self, indent, full=True):
        out = ' ' * indent + '<instrumentComponent>\n'
        out += element('component_id', self.id, indent + 1) + element('gain', self.gain, indent + 1)
        for layer in self.layers:
            out += layer.xml(indent + 1, full)
        return out + ' ' * indent + '</instrumentComponent>\n'


@dataclasses.dataclass
class Instrument:
    id: int
    name: str
    components: list
    volume: float = 1.0
    muted: bool = False
    soloed: bool = False
    pan: float = 0.0
    legacy_pan: tuple | None = None
    pitch_offset: float = 0.0
    random_pitch: float = 0.0
    gain: float = 1.0
    apply_velocity: bool = True
    filter_active: bool = False
    filter_cutoff: float = 1.0
    filter_resonance: float = 0.0
    attack: int = 0
    decay: int = 0
    sustain: float = 1.0
    release: int = 1000
    mute_group: int = -1
    midi_channel: int = -1
    midi_note: int = 36
    stop_note: bool = False
    selection: str = 'VELOCITY'
    hihat: int = -1
    lower_cc: int = 0
    higher_cc: int = 127
    fx: tuple = (0.0, 0.0, 0.0, 0.0)
    drumkit: str | None = None
    drumkit_path: str | None = None
    drumkit_lookup: int | None = None
    extra: str = ''

    def xml(self, indent, full=True):
        i = indent + 1
        out = ' ' * indent + '<instrument>\n' + element('id', self.id, i) + element('name', self.name, i)
        if full:
            out += element('drumkitPath', self.drumkit_path, i) + element('drumkit', self.drumkit, i)
            out += element('drumkitLookup', self.drumkit_lookup, i)
        out += element('volume', self.volume, i) + element('isMuted', self.muted, i)
        out += element('isSoloed', self.soloed, i)
        if self.legacy_pan is not None:
            out += element('pan_L', self.legacy_pan[0], i) + element('pan_R', self.legacy_pan[1], i)
        else:
            out += element('pan', self.pan, i)
        out += element('pitchOffset', self.pitch_offset, i) + element('randomPitchFactor', self.random_pitch, i)
        out += element('gain', self.gain, i) + element('applyVelocity', self.apply_velocity, i)
        out += element('filterActive', self.filter_active, i) + element('filterCutoff', self.filter_cutoff, i)
        out += element('filterResonance', self.filter_resonance, i)
        out += element('Attack', self.attack, i) + element('Decay', self.decay, i)
        out += element('Sustain', self.sustain, i) + element('Release', self.release, i)
        out += element('muteGroup', self.mute_group, i) + element('midiOutChannel', self.midi_channel, i)
        out += element('midiOutNote', self.midi_note, i) + element('isStopNote', self.stop_note, i)
        out += element('sampleSelectionAlgo', self.selection, i) + element('isHihat', self.hihat, i)
        out += element('lower_cc', self.lower_cc, i) + element('higher_cc', self.higher_cc, i)
        for n, level in enumerate(self.fx):
            out += element(f'FX{n + 1}Level', level, i)
        out += self.extra
        for component in self.components:
            out += component.xml(i, full)
        return out + ' ' * indent + '</instrument>\n'


@dataclasses.dataclass
class Note:
    position: int
    instrument: int = 0
    velocity: float = 0.8
    pan: float = 0.0
    legacy_pan: tuple | None = None
    leadlag: float = 0.0
    pitch: float = 0.0
    key: str = 'C0'
    length: int = -1
    note_off: bool = False
    probability: float = 1.0

    def xml(self, indent):
        i = indent + 1
        out = ' ' * indent + '<note>\n' + element('position', self.position, i) + element('leadlag', self.leadlag, i)
        out += element('velocity', self.velocity, i)
        if self.legacy_pan is not None:
            out += element('pan_L', self.legacy_pan[0], i) + element('pan_R', self.legacy_pan[1], i)
        else:
            out += element('pan', self.pan, i)
        out += element('pitch', self.pitch, i) + element('key', self.key, i) + element('length', self.length, i)
        out += element('instrument', self.instrument, i) + element('note_off', self.note_off, i)
        out += element('probability', self.probability, i)
        return out + ' ' * indent + '</note>\n'


@dataclasses.dataclass
class Pattern:
    name: str
    notes: list = dataclasses.field(default_factory=list)
    size: int = 192
    denominator: int = 4
    info: str = ''
    category: str = 'not_categorized'

    def xml(self, indent):
        i = indent + 1
        out = ' ' * indent + '<pattern>\n' + element('name', self.name, i) + element('info', self.info, i)
        out += element('category', self.category, i) + element('size', self.size, i)
        out += element('denominator', self.denominator, i)
        if self.notes:
            out += ' ' * i + '<noteList>\n' + ''.join(n.xml(i + 1) for n in self.notes) + ' ' * i + '</noteList>\n'
        else:
            out += ' ' * i + '<noteList/>\n'
        return out + ' ' * indent + '</pattern>\n'


@dataclasses.dataclass
class Song:
    instruments: list
    patterns: list
    sequence: list = None            # list of columns, each a list of pattern names
    bpm: float = 120.0
    volume: float = 0.5
    muted: bool = False
    metronome_volume: float = 0.5
    name: str = 'Verifier song'
    author: str = 'verifier'
    notes: str = ''
    license: str = 'CC0'
    loop: bool = False
    mode: str = 'song'
    playback_track: str = ''
    playback_enabled: bool = False
    playback_volume: float = 0.0
    timeline: bool = False
    tempo_markers: tuple = ()        # (column, bpm)
    tags: tuple = ()                 # (column, text)
    pan_law: str = 'RATIO_STRAIGHT_POLYGONAL'
    k_norm: float = 1.33333
    humanize_time: float = 0.0
    humanize_velocity: float = 0.0
    swing: float = 0.0
    components: tuple = ((0, 'Main', 1.0),)
    virtual: tuple = ()              # (pattern name, (member names...))
    velocity_path: tuple = ()        # (x, y) points of the velocity automation path
    version: str = '1.2.7'
    action_mode: int = 0
    extra: str = ''

    def xml(self):
        out = '<?xml version="1.0" encoding="UTF-8"?>\n<song>\n'
        out += element('version', self.version, 1) + element('bpm', self.bpm, 1) + element('volume', self.volume, 1)
        out += element('isMuted', self.muted, 1) + element('metronomeVolume', self.metronome_volume, 1)
        out += element('name', self.name, 1) + element('author', self.author, 1) + element('notes', self.notes, 1)
        out += element('license', self.license, 1) + element('loopEnabled', self.loop, 1)
        out += element('patternModeMode', True, 1)
        out += element('playbackTrackFilename', self.playback_track, 1)
        out += element('playbackTrackEnabled', self.playback_enabled, 1)
        out += element('playbackTrackVolume', self.playback_volume, 1) + element('action_mode', self.action_mode, 1)
        out += element('isPatternEditorLocked', False, 1) + element('isTimelineActivated', self.timeline, 1)
        out += element('mode', self.mode, 1) + element('pan_law_type', self.pan_law, 1)
        out += element('pan_law_k_norm', self.k_norm, 1) + element('humanize_time', self.humanize_time, 1)
        out += element('humanize_velocity', self.humanize_velocity, 1) + element('swing_factor', self.swing, 1)
        out += self.extra
        if self.components is not None:
            out += ' <componentList>\n'
            for cid, cname, cvolume in self.components:
                out += '  <drumkitComponent>\n' + element('id', cid, 3) + element('name', cname, 3)
                out += element('volume', cvolume, 3) + '  </drumkitComponent>\n'
            out += ' </componentList>\n'
        out += ' <instrumentList>\n' + ''.join(i.xml(2) for i in self.instruments) + ' </instrumentList>\n'
        out += ' <patternList>\n' + ''.join(p.xml(2) for p in self.patterns) + ' </patternList>\n'
        if self.virtual:
            out += ' <virtualPatternList>\n'
            for name, members in self.virtual:
                out += '  <pattern>\n' + element('name', name, 3)
                out += ''.join(element('virtual', m, 3) for m in members) + '  </pattern>\n'
            out += ' </virtualPatternList>\n'
        else:
            out += ' <virtualPatternList/>\n'
        sequence = self.sequence if self.sequence is not None else [[p.name] for p in self.patterns[:1]]
        out += ' <patternSequence>\n'
        for column in sequence:
            if column:
                out += '  <group>\n' + ''.join(element('patternID', name, 3) for name in column) + '  </group>\n'
            else:
                out += '  <group/>\n'
        out += ' </patternSequence>\n <ladspa/>\n'
        if self.tempo_markers:
            out += ' <BPMTimeLine>\n'
            for column, bpm in self.tempo_markers:
                out += '  <newBPM>\n' + element('BAR', column, 3) + element('BPM', bpm, 3) + '  </newBPM>\n'
            out += ' </BPMTimeLine>\n'
        else:
            out += ' <BPMTimeLine/>\n'
        if self.tags:
            out += ' <timeLineTag>\n'
            for column, tag in self.tags:
                out += '  <newTAG>\n' + element('BAR', column, 3) + element('TAG', tag, 3) + '  </newTAG>\n'
            out += ' </timeLineTag>\n'
        else:
            out += ' <timeLineTag/>\n'
        out += ' <automationPaths>\n'
        if self.velocity_path:
            out += '  <path adjust="velocity">\n'
            out += ''.join(f'   <point x="{number(x)}" y="{number(y)}"/>\n' for x, y in self.velocity_path)
            out += '  </path>\n'
        else:
            out += '  <path adjust="velocity"/>\n'
        out += ' </automationPaths>\n</song>\n'
        return out


def pattern_file(pattern, *, drumkit='Verifier kit', author='verifier', license='CC0', version='1.2.7'):
    """A pattern document (.h2pattern) the way Pattern > Export writes it."""
    out = '<?xml version="1.0" encoding="UTF-8"?>\n'
    out += '<drumkit_pattern xmlns="http://www.hydrogen-music.org/drumkit_pattern" ' \
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    out += element('drumkit_name', drumkit, 1) + element('author', author, 1) + element('license', license, 1)
    out += pattern.xml(1)
    return out + '</drumkit_pattern>\n'


def drumkit_xml(name, instruments, *, author='verifier', info='', license='CC0', image='', image_license='',
                components=((0, 'Main', 1.0),), namespace=True, legacy=False):
    """drumkit.xml of a drumkit folder. legacy writes the pre-0.9.7 form: layers directly in the instrument."""
    attributes = ' xmlns="http://www.hydrogen-music.org/drumkit" ' \
                 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' if namespace else ''
    out = f'<?xml version="1.0" encoding="UTF-8"?>\n<drumkit_info{attributes}>\n'
    out += element('name', name, 1) + element('author', author, 1) + element('info', info, 1)
    out += element('license', license, 1) + element('image', image, 1) + element('imageLicense', image_license, 1)
    if components is not None and not legacy:
        out += ' <componentList>\n'
        for cid, cname, cvolume in components:
            out += '  <drumkitComponent>\n' + element('id', cid, 3) + element('name', cname, 3)
            out += element('volume', cvolume, 3) + '  </drumkitComponent>\n'
        out += ' </componentList>\n'
    out += ' <instrumentList>\n'
    for instrument in instruments:
        if legacy:
            text = instrument.xml(2, full=False)
            layers = ''.join(layer.xml(3, full=False) for component in instrument.components
                             for layer in component.layers)
            start = text.index('   <instrumentComponent>')
            end = text.rindex('</instrumentComponent>\n') + len('</instrumentComponent>\n')
            out += text[:start] + layers + text[end:]
        else:
            out += instrument.xml(2, full=False)
    out += ' </instrumentList>\n</drumkit_info>\n'
    return out


def archive(folder, files, *, compression='gz', mtime=1_700_000_000):
    """A .h2drumkit archive: folder/name entries with fixed metadata (deterministic bytes)."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.GNU_FORMAT) as tar:
        directory = tarfile.TarInfo(folder)
        directory.type, directory.mode, directory.mtime = tarfile.DIRTYPE, 0o755, mtime
        tar.addfile(directory)
        for name in sorted(files):
            data = files[name]
            data = data.encode('utf-8') if isinstance(data, str) else data
            info = tarfile.TarInfo(f'{folder}/{name}')
            info.size, info.mode, info.mtime = len(data), 0o644, mtime
            tar.addfile(info, io.BytesIO(data))
    data = raw.getvalue()
    if compression == 'gz':
        import gzip
        return gzip.compress(data, mtime=0)
    if compression == 'bz2':
        import bz2
        return bz2.compress(data)
    if compression == 'xz':
        import lzma
        return lzma.compress(data)
    return data


def playlist(paths, *, relative=False):
    out = '<?xml version="1.0" encoding="UTF-8"?>\n<playlist xmlns="http://www.hydrogen-music.org/playlist" ' \
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    out += element('name', 'verifier', 1) + ' <songs>\n'
    for path in paths:
        out += '  <song>\n' + element('path', path, 3) + element('scriptPath', '', 3)
        out += element('scriptEnabled', False, 3) + '  </song>\n'
    return out + ' </songs>\n</playlist>\n'


# -- projections of documents the product wrote -----------------------------------------------------------------
def local(tag):
    return tag.split('}')[-1] if isinstance(tag, str) else ''


def child(node, name):
    for item in node:
        if local(item.tag) == name:
            return item
    return None


def children(node, name):
    return [item for item in node if local(item.tag) == name]


def text(node, name, default=None):
    item = child(node, name) if node is not None else None
    if item is None:
        return default
    return ''.join(item.itertext())


def real(value, digits=4):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number != number or number in (float('inf'), float('-inf')):
        return str(number)
    rounded = round(number, digits)
    return 0.0 if rounded == 0 else rounded


def flag(value):
    if value is None:
        return None
    return str(value).strip().casefold() in ('true', '1')


def parse(data):
    """The root element of a document the product wrote; AssertionError when it is not well-formed XML."""
    if isinstance(data, bytes):
        data = data.decode('utf-8', 'replace')
    try:
        return ET.fromstring(data.encode('utf-8'))
    except ET.ParseError as exc:
        raise AssertionError(f'the document is not well-formed XML: {exc}') from None


class Places:
    """Reduces file locations in saved documents to tokens: the document areas and the library are public
    locations of an instance; the factory data of any implementation is one token."""

    def __init__(self, files_root, library_root=None):
        self.files_root = str(files_root).rstrip('/')
        self.library_root = str(library_root).rstrip('/') if library_root else None

    def token(self, value):
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return ''
        normal = os.path.normpath(value) if value.startswith('/') else value
        if normal.startswith(self.files_root + '/'):
            return '<files>/' + normal[len(self.files_root) + 1:]
        if self.library_root and normal.startswith(self.library_root + '/'):
            return '<library>/' + normal[len(self.library_root) + 1:]
        if value.startswith('/'):
            parts = PurePosixPath(normal).parts
            if 'drumkits' in parts:
                return '<drumkits>/' + '/'.join(parts[parts.index('drumkits') + 1:])
            return '<elsewhere>/' + PurePosixPath(normal).name
        return value


def note_projection(node):
    pan = text(node, 'pan')
    return {'position': int(float(text(node, 'position', '0'))), 'instrument': int(float(text(node, 'instrument', '-1'))),
            'velocity': real(text(node, 'velocity')), 'pan': real(pan) if pan is not None else None,
            'leadlag': real(text(node, 'leadlag')), 'pitch': real(text(node, 'pitch')),
            'key': text(node, 'key'), 'length': int(float(text(node, 'length', '-1'))),
            'note_off': flag(text(node, 'note_off')), 'probability': real(text(node, 'probability'))}


def pattern_projection(node):
    note_list = child(node, 'noteList')
    notes = [note_projection(n) for n in children(note_list, 'note')] if note_list is not None else []
    notes.sort(key=lambda n: (n['position'], n['instrument'], n['key'] or '', n['velocity'] or 0))
    return {'name': text(node, 'name'), 'info': text(node, 'info') or '', 'category': text(node, 'category'),
            'size': int(float(text(node, 'size', '0'))), 'denominator': int(float(text(node, 'denominator', '4'))),
            'notes': notes}


def pan_value(node):
    pan = text(node, 'pan')
    if pan is not None:
        return real(pan)
    left, right = text(node, 'pan_L'), text(node, 'pan_R')
    if left is None or right is None:
        return None
    left, right = float(left), float(right)
    # The ratio pan that pan_L/pan_R stand for (the product's conversion of the legacy pair).
    if left >= right:
        return real((right / left) - 1 if left else 0.0)
    return real(1 - (left / right) if right else 0.0)


def layer_projection(node, places):
    out = {'filename': places.token(text(node, 'filename')), 'min': real(text(node, 'min')),
           'max': real(text(node, 'max')), 'gain': real(text(node, 'gain')), 'pitch': real(text(node, 'pitch'))}
    if child(node, 'ismodified') is not None:
        out.update(modified=flag(text(node, 'ismodified')), smode=text(node, 'smode'),
                   frames=[int(float(text(node, k, '0'))) for k in ('startframe', 'loopframe', 'loops', 'endframe')],
                   rubber=[int(float(text(node, 'userubber', '0'))), real(text(node, 'rubberdivider')),
                           int(float(text(node, 'rubberCsettings', '0'))), real(text(node, 'rubberPitch'))],
                   volume=[[int(float(text(v, 'volume-position', '0'))), int(float(text(v, 'volume-value', '0')))]
                           for v in children(node, 'volume')],
                   pan=[[int(float(text(v, 'pan-position', '0'))), int(float(text(v, 'pan-value', '0')))]
                        for v in children(node, 'pan')])
    return out


def instrument_projection(node, places):
    components = []
    for component in children(node, 'instrumentComponent'):
        components.append({'id': int(float(text(component, 'component_id', '-1'))),
                           'gain': real(text(component, 'gain')),
                           'layers': [layer_projection(layer, places) for layer in children(component, 'layer')]})
    legacy_layers = [layer_projection(layer, places) for layer in children(node, 'layer')]
    if legacy_layers:
        components.append({'id': None, 'gain': None, 'layers': legacy_layers})
    return {'id': int(float(text(node, 'id', '-1'))), 'name': text(node, 'name'),
            'drumkit': text(node, 'drumkit'), 'drumkit_path': places.token(text(node, 'drumkitPath')),
            'volume': real(text(node, 'volume')), 'muted': flag(text(node, 'isMuted')),
            'soloed': flag(text(node, 'isSoloed')), 'pan': pan_value(node),
            'pitch_offset': real(text(node, 'pitchOffset')), 'random_pitch': real(text(node, 'randomPitchFactor')),
            'gain': real(text(node, 'gain')), 'apply_velocity': flag(text(node, 'applyVelocity')),
            'filter': [flag(text(node, 'filterActive')), real(text(node, 'filterCutoff')),
                       real(text(node, 'filterResonance'))],
            'adsr': [real(text(node, 'Attack')), real(text(node, 'Decay')), real(text(node, 'Sustain')),
                     real(text(node, 'Release'))],
            'mute_group': int(float(text(node, 'muteGroup', '-1'))),
            'midi_out': [int(float(text(node, 'midiOutChannel', '-1'))), int(float(text(node, 'midiOutNote', '-1')))],
            'stop_note': flag(text(node, 'isStopNote')), 'selection': text(node, 'sampleSelectionAlgo'),
            'hihat': [int(float(text(node, 'isHihat', '-1'))), int(float(text(node, 'lower_cc', '0'))),
                      int(float(text(node, 'higher_cc', '127')))],
            'fx': [real(text(node, f'FX{n}Level')) for n in range(1, 5)],
            'components': components}


def song_projection(data, places):
    """Every semantic part of a saved song, for points that select the parts they observe."""
    root = parse(data)
    if local(root.tag) != 'song':
        raise AssertionError('the document is not a Hydrogen song')
    instrument_list = child(root, 'instrumentList')
    pattern_list = child(root, 'patternList')
    sequence = child(root, 'patternSequence')
    columns = []
    if sequence is not None:
        for group in children(sequence, 'group'):
            columns.append(sorted(''.join(p.itertext()) for p in children(group, 'patternID')))
        legacy = [''.join(p.itertext()) for p in children(sequence, 'patternID')]
        if legacy:
            columns = [[name] for name in legacy]
    while columns and not columns[-1]:
        columns.pop()
    virtual = {}
    for pattern in children(child(root, 'virtualPatternList') or ET.Element('x'), 'pattern'):
        members = sorted(''.join(v.itertext()) for v in children(pattern, 'virtual'))
        if members:
            virtual[text(pattern, 'name')] = members
    markers = sorted([int(float(text(n, 'BAR', '0'))), real(text(n, 'BPM'))]
                     for n in children(child(root, 'BPMTimeLine') or ET.Element('x'), 'newBPM'))
    tags = sorted([int(float(text(n, 'BAR', '0'))), text(n, 'TAG') or '']
                  for n in children(child(root, 'timeLineTag') or ET.Element('x'), 'newTAG'))
    components = [{'id': int(float(text(c, 'id', '-1'))), 'name': text(c, 'name'), 'volume': real(text(c, 'volume'))}
                  for c in children(child(root, 'componentList') or ET.Element('x'), 'drumkitComponent')]
    path = []
    automation = child(root, 'automationPaths')
    if automation is not None:
        for item in children(automation, 'path'):
            if item.get('adjust') == 'velocity':
                path = [[real(p.get('x')), real(p.get('y'))] for p in children(item, 'point')]
    return {
        'song': {'bpm': real(text(root, 'bpm')), 'volume': real(text(root, 'volume')),
                 'muted': flag(text(root, 'isMuted')), 'metronome_volume': real(text(root, 'metronomeVolume')),
                 'name': text(root, 'name'), 'author': text(root, 'author'), 'notes': text(root, 'notes'),
                 'license': text(root, 'license'), 'loop': flag(text(root, 'loopEnabled')),
                 'mode': text(root, 'mode'), 'timeline': flag(text(root, 'isTimelineActivated')),
                 'pan_law': text(root, 'pan_law_type'), 'k_norm': real(text(root, 'pan_law_k_norm'), 3),
                 'humanize': [real(text(root, 'humanize_time')), real(text(root, 'humanize_velocity'))],
                 'swing': real(text(root, 'swing_factor')),
                 'playback': [places.token(text(root, 'playbackTrackFilename')),
                              flag(text(root, 'playbackTrackEnabled')), real(text(root, 'playbackTrackVolume'))],
                 'action_mode': text(root, 'action_mode'),
                 'drumkit': text(root, 'last_loaded_drumkit_name')},
        'components': components,
        'instruments': [instrument_projection(n, places) for n in children(instrument_list, 'instrument')]
        if instrument_list is not None else [],
        'patterns': [pattern_projection(n) for n in children(pattern_list, 'pattern')]
        if pattern_list is not None else [],
        'virtual': virtual, 'sequence': columns, 'markers': markers, 'tags': tags, 'velocity_path': path,
    }


def drumkit_projection(data, places):
    root = parse(data)
    if local(root.tag) != 'drumkit_info':
        raise AssertionError('the document is not a drumkit description')
    instrument_list = child(root, 'instrumentList')
    return {'name': text(root, 'name'), 'author': text(root, 'author'), 'info': text(root, 'info') or '',
            'license': text(root, 'license'), 'image': text(root, 'image') or '',
            'image_license': text(root, 'imageLicense') or '',
            'components': [{'id': int(float(text(c, 'id', '-1'))), 'name': text(c, 'name'),
                            'volume': real(text(c, 'volume'))}
                           for c in children(child(root, 'componentList') or ET.Element('x'), 'drumkitComponent')],
            'instruments': [instrument_projection(n, places) for n in children(instrument_list, 'instrument')]
            if instrument_list is not None else []}


def pattern_document_projection(data):
    root = parse(data)
    pattern = child(root, 'pattern')
    if local(root.tag) != 'drumkit_pattern' or pattern is None:
        raise AssertionError('the document is not a Hydrogen pattern')
    return {'drumkit': text(root, 'drumkit_name'), 'license': text(root, 'license'),
            'pattern': pattern_projection(pattern)}


def playlist_projection(data, places):
    root = parse(data)
    if local(root.tag) != 'playlist':
        raise AssertionError('the document is not a Hydrogen playlist')
    songs = child(root, 'songs')
    return [{'path': places.token(text(s, 'path')), 'script': text(s, 'scriptPath') or '',
             'enabled': flag(text(s, 'scriptEnabled'))} for s in children(songs, 'song')] if songs is not None else []
