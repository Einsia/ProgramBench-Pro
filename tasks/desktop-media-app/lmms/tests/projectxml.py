'''Self-contained LMMS 1.2.2 project XML for verifier fixtures.

No factory file is read: a candidate has none, and a fixture has to mean the same thing for the reference and for any
implementation. Positions and lengths are in ticks (48 per beat, 192 per bar); one step of a beat pattern is 12 ticks.
A model that is automated is written as a child element with an id and a value, as the product itself saves it, and
the automation pattern points at that id.
'''
import base64
import itertools
import struct
import xml.etree.ElementTree as ET
import zlib

TICKS_PER_BEAT = 48
TICKS_PER_BAR = 192
STEP_TICKS = 12
DEFAULT_KEY = 57
KINDS = {'instrument': 0, 'beat': 1, 'sample': 2, 'automation': 5, 'hidden': 6}
CONTROLS = {'amplifier': 'AmplifierControls'}
NL = chr(10)
HEADER = '<?xml version=' + chr(34) + '1.0' + chr(34) + '?>' + NL + '<!DOCTYPE lmms-project>' + NL


def seconds_to_ticks(seconds, bpm):
    return round(seconds * bpm / 60 * TICKS_PER_BEAT)


def ticks_to_seconds(ticks, bpm):
    return ticks * 60 / (bpm * TICKS_PER_BEAT)


def bars(ticks):
    return -(-ticks // TICKS_PER_BAR) * TICKS_PER_BAR


def text(value):
    if isinstance(value, bool):
        return str(int(value))
    return str(value)


def element(tag, parent, values=None):
    node = ET.Element(tag) if parent is None else ET.SubElement(parent, tag)
    for key, value in (values or {}).items():
        node.set(key, text(value))
    return node


def note_values(item):
    '''A note is (pos, length, key) with optional volume and panning.'''
    return {'pos': item[0], 'len': item[1], 'key': item[2], 'vol': item[3] if len(item) > 3 else 100,
            'pan': item[4] if len(item) > 4 else 0}


def chain(parent, effects):
    node = element('fxchain', parent, {'numofeffects': len(effects), 'enabled': 1 if effects else 0})
    for item in effects:
        node.append(item)
    return node


def effect(name, controls=None, params=None, wet=1.0, gate=0.0, on=True):
    '''One effect of a chain; controls is the name of its controls element (see CONTROLS).'''
    node = element('effect', None, {'name': name, 'on': on, 'wet': wet, 'gate': gate, 'autoquit': 1,
                                    'autoquit_numerator': 4, 'autoquit_denominator': 4, 'syncmode': 0})
    element(controls or CONTROLS[name], node, params)
    element('key', node)
    return node


SHAPERS = ('elvol', 'elcut', 'elres')


def shape(parent, shaping):
    '''The sound shaping of an instrument track (eldata): shaping holds filter (fwet, ftype, fcut, fres) and the
    attributes of the volume (elvol), cutoff (elcut) and resonance (elres) envelope and LFO; what is not given is
    the product default.'''
    node = element('eldata', parent, shaping.get('filter'))
    for name in SHAPERS:
        if name in shaping:
            element(name, node, shaping[name])
    return node


def instrument_track(name, plugin, params=None, notes=(), patterns=(), steps=None, vol=100, pan=0, pitch=0,
                     basenote=DEFAULT_KEY, muted=False, solo=False, channel=0, effects=(), pattern_pos=0, shaping=None):
    '''An instrument track: plugin is the instrument name, params its attributes (defaults when empty), notes one
    melodic pattern at pattern_pos, patterns a list of (position, notes), steps the active steps of a beat pattern.'''
    track = element('track', None, {'type': KINDS['instrument'], 'name': name, 'muted': muted, 'solo': solo})
    inner = element('instrumenttrack', track, {'vol': vol, 'pan': pan, 'pitch': pitch, 'basenote': basenote,
                                              'fxch': channel, 'pitchrange': 1, 'usemasterpitch': 1})
    holder = element('instrument', inner, {'name': plugin})
    element(plugin, holder, params)
    if shaping:
        shape(inner, shaping)
    chain(inner, list(effects))
    if steps is not None:
        pattern = element('pattern', track, {'type': 0, 'pos': pattern_pos, 'len': TICKS_PER_BAR, 'muted': 0,
                                             'steps': 16, 'name': ''})
        for step in steps:
            element('note', pattern, {'key': DEFAULT_KEY, 'vol': 100, 'pan': 0, 'pos': step * STEP_TICKS,
                                      'len': -TICKS_PER_BAR})
    groups = list(patterns)
    if notes:
        groups.append((pattern_pos, notes))
    for start, items in groups:
        if not items:
            continue
        end = max(item[0] + item[1] for item in items)
        pattern = element('pattern', track, {'type': 1, 'pos': start, 'len': bars(end), 'muted': 0, 'steps': 16,
                                             'name': ''})
        for item in items:
            element('note', pattern, note_values(item))
    return track


def sample_track(name='Sample track', clips=(), vol=100, pan=0, muted=False, solo=False, effects=()):
    '''A sample track; a clip is (pos, length, absolute source path) with an optional muted flag (LMMS 1.2.2 saves no reversal for clips; the audio file processor has one).'''
    track = element('track', None, {'type': KINDS['sample'], 'name': name, 'muted': muted, 'solo': solo})
    inner = element('sampletrack', track, {'vol': vol, 'pan': pan})
    chain(inner, list(effects))
    for clip in clips:
        element('sampletco', track, {'pos': clip[0], 'len': clip[1], 'src': clip[2],
                                     'muted': clip[3] if len(clip) > 3 else 0})
    return track


def beat_track(name='Beat/Bassline 0', tracks=(), clips=((0, TICKS_PER_BAR),), muted=False):
    '''A beat and bassline track: its instrument tracks (with steps) and the clips that play it in the song.'''
    track = element('track', None, {'type': KINDS['beat'], 'name': name, 'muted': muted, 'solo': 0})
    inner = element('bbtrack', track)
    container = element('trackcontainer', inner, {'type': 'bbtrackcontainer', 'width': 640, 'height': 400, 'x': 610,
                                                  'y': 5, 'visible': 0, 'minimized': 0, 'maximized': 0})
    for item in tracks:
        container.append(item)
    for pos, length in clips:
        element('bbtco', track, {'pos': pos, 'len': length, 'muted': 0, 'usestyle': 1})
    return track


class Project:
    def __init__(self, bpm=140, mastervol=100, masterpitch=0, signature=(4, 4)):
        self.ids = itertools.count(1000)
        self.head = element('head', None, {'bpm': bpm, 'mastervol': mastervol, 'masterpitch': masterpitch,
                                           'timesig_numerator': signature[0], 'timesig_denominator': signature[1]})
        self.tracks = []
        self.channels = []
        master = element('fxchannel', None, {'num': 0, 'name': 'Master', 'volume': 1.0, 'muted': 0, 'soloed': 0})
        chain(master, [])
        self.channels.append(master)

    def add(self, track):
        self.tracks.append(track)
        return track

    def channel(self, number, name, volume=1.0, muted=False, effects=(), sends=((0, 1.0),)):
        node = element('fxchannel', None, {'num': number, 'name': name, 'volume': volume, 'muted': muted,
                                           'soloed': 0})
        chain(node, list(effects))
        for target, amount in sends:
            element('send', node, {'channel': target, 'amount': amount})
        self.channels.append(node)
        return node

    def automate(self, node, key, points, pos=0, length=None, prog=1, name=None):
        '''Automate the model key of node (head, instrumenttrack or sampletrack): points are (position, value) pairs
        relative to the pattern, prog is 0 discrete, 1 linear or 2 cubic.'''
        ident = next(self.ids)
        value = node.attrib.pop(key)
        element(key, node, {'id': ident, 'value': value, 'scale_type': 'linear'})
        track = element('track', None, {'type': KINDS['automation'], 'name': 'Automation track', 'muted': 0, 'solo': 0})
        element('automationtrack', track)
        end = max(point[0] for point in points)
        pattern = element('automationpattern', track, {'pos': pos, 'len': length or bars(max(end, 1)),
                                                       'name': name or key, 'prog': prog, 'tens': 1, 'mute': 0})
        for at, number in points:
            element('time', pattern, {'pos': at, 'value': number})
        element('object', pattern, {'id': ident})
        self.tracks.append(track)
        return ident

    def xml(self):
        root = ET.Element('lmms-project', {'version': '1.0', 'creator': 'LMMS', 'creatorversion': '1.2.2',
                                           'type': 'song'})
        root.append(self.head)
        song = element('song', root)
        container = element('trackcontainer', song, {'type': 'song', 'width': 600, 'height': 300, 'x': 5, 'y': 5,
                                                     'visible': 1, 'minimized': 0, 'maximized': 0})
        for track in self.tracks:
            container.append(track)
        mixer = element('fxmixer', song, {'width': 543, 'height': 335, 'x': 5, 'y': 310, 'visible': 1,
                                          'minimized': 0, 'maximized': 0})
        for channel in self.channels:
            mixer.append(channel)
        element('controllers', song)
        ET.indent(root)
        return HEADER + ET.tostring(root, encoding='unicode') + NL


def floats(values):
    # Float graph values as the product saves them: little-endian float32 numbers as base64 text.
    return base64.b64encode(struct.pack('<%df' % len(values), *values)).decode('ascii')


# The wave pattern of the Game Boy instrument (32 values from 0 to 15): the product reads it without checking that it
# exists, so every project with that instrument carries one.
GAMEBOY_WAVE = floats([i if i < 16 else 31 - i for i in range(32)])


def curve(values):
    '''The wave shape of the waveshaper and the dynamics processor: 200 little-endian floats as base64 text.'''
    assert len(values) == 200
    return base64.b64encode(struct.pack('<200f', *values)).decode('ascii')


def mmpz(xml):
    '''The compressed project file: a big-endian length of the XML, then its zlib stream.'''
    data = xml.encode('utf-8')
    return struct.pack('>I', len(data)) + zlib.compress(data)
