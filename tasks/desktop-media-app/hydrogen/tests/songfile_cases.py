"""Reading and writing song and pattern documents: verifier-made documents opened through OSC and saved again.

Each scored row uploads one document variant, opens it (/Hydrogen/OPEN_SONG, or /Hydrogen/OPEN_PATTERN into a known
song), saves the result with /Hydrogen/SAVE_SONG_AS and compares the parts of the saved song the variant is about:
current and legacy spellings, defaults of missing elements, values outside their ranges, references to missing
patterns, instruments or files. Documents the product refuses leave the open song unchanged; those rows count
together with a row that opens a valid document.
"""
from __future__ import annotations

import re

import songs as S
from harness import MissingDependency
from render_cases import instrument, layer, notes, upload_samples

FAMILY = 'songfile-documents'


def prepare(ctx):
    ctx.fresh()
    upload_samples(ctx)
    ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)


def base(ctx, **song):
    """A three-instrument verifier song; options override song fields."""
    kit = [instrument(ctx, 'kick.wav', 0, name='Kick'), instrument(ctx, 'snare.wav', 1, name='Snare'),
           instrument(ctx, 'hat.wav', 2, name='Hat')]
    values = dict(name='File song', author='verifier', mode='song')
    values.update(song)
    patterns = values.pop('patterns', [S.Pattern('Main', [S.Note(0, 0), S.Note(48, 1), S.Note(96, 0, velocity=0.6),
                                                          S.Note(144, 1)])])
    return S.Song(values.pop('instruments', kit), patterns, **values)


def select(projection, parts):
    out = {}
    for item in parts:
        if isinstance(item, tuple):
            key, fields = item
            if key == 'instruments':
                out[key] = [{f: i[f] for f in fields} for i in projection[key]]
            elif key == 'patterns':
                out[key] = [{f: p[f] for f in fields} for p in projection[key]]
            else:
                out[key] = {f: projection[key][f] for f in fields}
        else:
            out[item] = projection[item]
    return out


class Load:
    """Upload a document, open it (a song, or a pattern into the open song) and read selected parts back."""

    def __init__(self, document, parts, *, kind='song', before=None):
        self.document, self.parts, self.kind, self.before = document, parts, kind, before

    def __call__(self, ctx):
        if self.before is not None:
            self.before(ctx)
        text = self.document(ctx)
        suffix = '.h2song' if self.kind == 'song' else '.h2pattern'
        name = ctx.unique('document', suffix)
        ctx.upload(name, text.encode('utf-8') if isinstance(text, str) else text)
        if self.kind == 'song':
            ctx.open_song(name)
        else:
            ctx.osc('/Hydrogen/OPEN_PATTERN', name, wait=0.8)
        return select(ctx.song(), self.parts)


def open_known(ctx):
    """In-step precondition of refusal rows: a known valid song is open."""
    name = ctx.upload('known.h2song', base(ctx, name='Known song', bpm=101.0).xml())
    ctx.open_song(name)


def add(suite, scenario, step, action, description, requires=()):
    return suite.add(FAMILY, scenario, step, action, description=description, requires=requires)


def xml_edit(builder, *edits):
    """A document builder followed by literal text replacements (old, new[, count])."""
    def build(ctx):
        text = builder(ctx).xml() if not isinstance(builder, str) else builder
        for edit in edits:
            old, new = edit[0], edit[1]
            count = edit[2] if len(edit) > 2 else 1
            if old not in text:
                raise AssertionError('verifier document template lacks ' + old)
            text = text.replace(old, new, count)
        return text
    return build


def remove_elements(builder, *names):
    def build(ctx):
        text = builder(ctx).xml()
        for name in names:
            text = re.sub(rf'\s*<{name}>[^<]*</{name}>', '', text)
            text = re.sub(rf'\s*<{name}/>', '', text)
        return text
    return build


SONG = ('song', ('bpm', 'volume', 'muted', 'metronome_volume', 'name', 'author', 'notes', 'license', 'loop', 'mode',
                 'timeline', 'pan_law', 'k_norm', 'humanize', 'swing', 'playback', 'action_mode'))
MIXER = ('instruments', ('name', 'volume', 'muted', 'soloed', 'pan', 'gain', 'pitch_offset', 'random_pitch',
                         'apply_velocity', 'filter', 'adsr', 'mute_group', 'midi_out', 'stop_note', 'selection',
                         'hihat', 'fx'))
LAYERS = ('instruments', ('name', 'components'))
NOTES = ('patterns', ('name', 'size', 'denominator', 'info', 'category', 'notes'))


def song_properties(suite):
    suite.setup(FAMILY, 'properties', prepare, 'Fresh instance with the verifier samples')
    add(suite, 'properties', 'all-fields', Load(lambda ctx: base(
        ctx, bpm=97.5, volume=0.8, metronome_volume=0.3, name='Ünïcode & <Song> "Ⅱ"', author='A & B',
        notes='First line\nSecond line\twith a tab', license='CC BY-SA', loop=True, pan_law='POLAR_CONST_POWER',
        k_norm=2.5, humanize_time=0.2, humanize_velocity=0.1, swing=0.25, action_mode=1).xml(), [SONG]),
        'Open a song whose properties all differ from the defaults (Unicode and markup characters in the texts)')
    add(suite, 'properties', 'out-of-range', Load(lambda ctx: base(
        ctx, bpm=900.0, volume=3.0, metronome_volume=-1.0, swing=2.0, humanize_time=-0.5, k_norm=0.0).xml(), [SONG]),
        'Open a song whose tempo, volumes, swing, humanize and k norm lie outside their ranges')
    add(suite, 'properties', 'minimal', Load(lambda ctx: '<?xml version="1.0" encoding="UTF-8"?>\n<song>\n'
                                            ' <instrumentList/>\n <patternList/>\n</song>\n',
                                            [SONG, 'instruments', 'patterns', 'sequence']),
        'Open a song that holds nothing but empty instrument and pattern lists')
    add(suite, 'properties', 'missing-elements', Load(remove_elements(
        lambda ctx: base(ctx), 'bpm', 'volume', 'name', 'author', 'license', 'mode', 'pan_law_type', 'swing_factor',
        'loopEnabled'), [SONG]), 'Open a song that lacks the tempo, volume, texts, mode, pan law, swing and loop elements')
    add(suite, 'properties', 'pattern-mode-flag', Load(xml_edit(lambda ctx: base(ctx), ('<mode>song</mode>',
                                                                                     '<mode>pattern</mode>')),
                                                       [SONG]), 'Open a song stored in pattern mode')
    add(suite, 'properties', 'unknown-pan-law', Load(xml_edit(lambda ctx: base(ctx),
                                                              ('RATIO_STRAIGHT_POLYGONAL', 'SPIRAL_PAN')), [SONG]),
        'Open a song that names an unknown pan law')
    add(suite, 'properties', 'playback-track', Load(lambda ctx: base(
        ctx, playback_track=ctx.inputs('pad.wav'), playback_enabled=True, playback_volume=0.35).xml(), [SONG]),
        'Open a song with an enabled playback track (pad.wav at volume 0.35)')
    add(suite, 'properties', 'playback-track-missing', Load(lambda ctx: base(
        ctx, playback_track=ctx.inputs('no-such-track.wav'), playback_enabled=True, playback_volume=0.5).xml(),
        [SONG]), 'Open a song whose playback track file does not exist')


def song_instruments(suite):
    suite.setup(FAMILY, 'instruments', prepare, 'Fresh instance with the verifier samples')

    def full(ctx):
        inst = instrument(ctx, 'tone440.wav', 0, name='Full', volume=0.7, muted=True, soloed=True, pan=-0.35,
                          pitch_offset=-3.5, random_pitch=0.2, gain=1.7, apply_velocity=False, filter_active=True,
                          filter_cutoff=0.4, filter_resonance=0.6, attack=1000, decay=2000, sustain=0.5, release=5000,
                          mute_group=3, midi_channel=9, midi_note=42, stop_note=True, selection='ROUND_ROBIN', hihat=2,
                          lower_cc=10, higher_cc=90, fx=(0.1, 0.2, 0.3, 0.4))
        return base(ctx, instruments=[inst], patterns=[S.Pattern('P', notes(0))])
    add(suite, 'instruments', 'all-fields', Load(lambda ctx: full(ctx).xml(), [MIXER]),
        'Open a song whose instrument settings all differ from the defaults')
    add(suite, 'instruments', 'out-of-range', Load(lambda ctx: base(ctx, instruments=[instrument(
        ctx, 'tone440.wav', 0, volume=3.5, gain=9.0, pan=-2.0, pitch_offset=40.0, filter_cutoff=1.5,
        filter_resonance=-0.5, attack=200000, decay=-5, sustain=1.5, release=10)],
        patterns=[S.Pattern('P', notes(0))]).xml(), [MIXER]),
        'Open a song whose instrument volume, gain, pan, pitch, filter and envelope lie outside their ranges')
    for pair in ((0.5, 1.0), (1.0, 0.2), (0.0, 0.0), (-1.0, 0.5), (0.3, 0.3)):
        add(suite, 'instruments', f'legacy-pan-{pair[0]:g}-{pair[1]:g}', Load(lambda ctx, p=pair: base(
            ctx, instruments=[instrument(ctx, 'tone440.wav', 0, legacy_pan=p)],
            patterns=[S.Pattern('P', notes(0))]).xml(), [('instruments', ('pan',))]),
            f'Open a song whose instrument pan is stored as pan_L {pair[0]:g}, pan_R {pair[1]:g}')
    add(suite, 'instruments', 'missing-fields', Load(remove_elements(
        lambda ctx: base(ctx), 'volume', 'isMuted', 'pan', 'gain', 'applyVelocity', 'filterActive', 'filterCutoff',
        'Attack', 'Release', 'muteGroup', 'isStopNote', 'sampleSelectionAlgo', 'midiOutNote', 'FX1Level'),
        [MIXER]), 'Open a song whose instruments lack most of their settings')
    add(suite, 'instruments', 'sparse-ids', Load(lambda ctx: S.Song(
        [instrument(ctx, 'kick.wav', 5, name='Five'), instrument(ctx, 'snare.wav', 9, name='Nine')],
        [S.Pattern('P', [S.Note(0, 5), S.Note(48, 9), S.Note(96, 7)])], name='Sparse').xml(),
        [('instruments', ('name',)), ('patterns', ('notes',))]),
        'Open a song whose instruments have ids 5 and 9 and whose notes refer to 5, 9 and the missing 7')
    add(suite, 'instruments', 'layers', Load(lambda ctx: base(ctx, instruments=[instrument(ctx, '', layers=[
        layer(ctx, 'layer220.wav', min=0.0, max=0.3, gain=0.5, pitch=-2.0),
        layer(ctx, 'layer330.wav', min=0.3, max=0.65, gain=1.2, pitch=0.5),
        layer(ctx, 'layer550.wav', min=0.65, max=1.0, gain=2.0, pitch=7.0)])],
        patterns=[S.Pattern('P', notes(0))]).xml(), [LAYERS]),
        'Open a song with an instrument of three velocity layers with their own gain and pitch')
    add(suite, 'instruments', 'edited-layer', Load(lambda ctx: base(ctx, instruments=[instrument(ctx, '', layers=[
        layer(ctx, 'ramp.wav', modified=True, smode='pingpong', startframe=100, loopframe=2000, loops=3,
              endframe=20000, rubber=0, rubberdivider=2.0, rubbersettings=2, rubberpitch=0.5,
              volume_envelope=((0, 100), (300, 40), (841, 0)), pan_envelope=((0, 50), (841, 80)))])],
        patterns=[S.Pattern('P', notes(0))]).xml(), [LAYERS]),
        'Open a song with an edited sample layer (loop frames, ping-pong mode, envelopes, stretch settings)')
    add(suite, 'instruments', 'layer-out-of-range', Load(lambda ctx: base(ctx, instruments=[instrument(
        ctx, '', layers=[layer(ctx, 'tone440.wav', min=-0.5, max=1.7, gain=-1.0, pitch=60.0)])],
        patterns=[S.Pattern('P', notes(0))]).xml(), [LAYERS]),
        'Open a song with a layer whose velocity range, gain and pitch lie outside their ranges')
    add(suite, 'instruments', 'missing-sample', Load(lambda ctx: base(ctx, instruments=[instrument(
        ctx, '', layers=[layer(ctx, 'no-such-sample.wav'), layer(ctx, 'tone440.wav', min=0.5)])],
        patterns=[S.Pattern('P', notes(0))]).xml(), [LAYERS]),
        'Open a song whose first layer names a sample that does not exist')
    add(suite, 'instruments', 'relative-sample', Load(lambda ctx: base(ctx, instruments=[S.Instrument(
        0, 'Relative', [S.Component([S.Layer('./tone440.wav')])])], patterns=[S.Pattern('P', notes(0))]).xml(),
        [LAYERS]), 'Open a song whose sample is named relative to the song file (./tone440.wav)')

    def two_components(ctx):
        inst = instrument(ctx, '', components=[S.Component([layer(ctx, 'kick.wav')], id=0, gain=0.8),
                                               S.Component([layer(ctx, 'snare.wav')], id=1, gain=1.3)])
        return base(ctx, instruments=[inst], patterns=[S.Pattern('P', notes(0))],
                    components=((0, 'Close', 0.9), (1, 'Room', 0.4)))
    add(suite, 'instruments', 'components', Load(lambda ctx: two_components(ctx).xml(), ['components', LAYERS]),
        'Open a song with two drumkit components (Close, Room) used by one instrument')
    add(suite, 'instruments', 'no-component-list', Load(lambda ctx: base(ctx, components=None).xml(),
                                                        ['components', LAYERS]),
        'Open a song that has no component list')

    def legacy_layers(ctx):
        text = base(ctx).xml()
        # Before 0.9.7 the layers sat directly in the instrument.
        text = re.sub(r'\s*<instrumentComponent>\s*<component_id>0</component_id>\s*<gain>1</gain>(.*?)</instrumentComponent>',
                      lambda m: m.group(1), text, flags=re.S)
        return re.sub(r'\s*<componentList>.*?</componentList>', '', text, flags=re.S)
    add(suite, 'instruments', 'legacy-direct-layers', Load(legacy_layers, ['components', LAYERS]),
        'Open a song in the pre-0.9.7 form: layers directly in the instruments, no components')


def song_patterns(suite):
    suite.setup(FAMILY, 'patterns', prepare, 'Fresh instance with the verifier samples')
    add(suite, 'patterns', 'attributes', Load(lambda ctx: base(ctx, patterns=[
        S.Pattern('Seven', notes(0, 84), size=168, denominator=8, info='seven eighths', category='odd'),
        S.Pattern('Long', notes(0, 300), size=384, info='two bars'), S.Pattern('Short', notes(0), size=48)],
        sequence=[['Seven'], ['Long'], ['Short']]).xml(), [NOTES]),
        'Open a song with patterns of 168 (eighth-note denominator), 384 and 48 ticks')
    add(suite, 'patterns', 'note-fields', Load(lambda ctx: base(ctx, patterns=[S.Pattern('Notes', [
        S.Note(0, 0, velocity=0.25, pan=-0.6, leadlag=0.3, pitch=0.5, key='Fs1', length=24, probability=0.75),
        S.Note(12, 1, velocity=1.0, pan=0.9, leadlag=-1.0, key='Bf-2', length=96, probability=0.0),
        S.Note(36, 2, velocity=0.0, key='E3'), S.Note(60, 0, note_off=True, velocity=0.0)])]).xml(), [NOTES]),
        'Open a song whose notes use every note field')
    add(suite, 'patterns', 'note-out-of-range', Load(lambda ctx: base(ctx, patterns=[S.Pattern('Odd', [
        S.Note(0, 0, velocity=1.6, pan=-3.0, leadlag=2.0, pitch=80.0, key='C5', probability=1.5),
        S.Note(250, 1, velocity=-0.2, key='Xx0', length=-7), S.Note(-12, 2)])]).xml(), [NOTES]),
        'Open a song whose notes have values outside their ranges, a key name the product does not know and '
        'positions outside the pattern')
    add(suite, 'patterns', 'legacy-note-pan', Load(lambda ctx: base(ctx, patterns=[S.Pattern('Pairs', [
        S.Note(0, 0, legacy_pan=(1.0, 0.5)), S.Note(48, 1, legacy_pan=(0.25, 1.0)),
        S.Note(96, 2, legacy_pan=(0.5, 0.5))])]).xml(), [NOTES]),
        'Open a song whose note pans are stored as pan_L/pan_R pairs')
    add(suite, 'patterns', 'missing-note-fields', Load(remove_elements(
        lambda ctx: base(ctx), 'leadlag', 'pan', 'pitch', 'key', 'length', 'note_off', 'probability', 'velocity'),
        [NOTES]), 'Open a song whose notes hold only a position and an instrument')
    add(suite, 'patterns', 'duplicate-notes', Load(lambda ctx: base(ctx, patterns=[S.Pattern('Twice', [
        S.Note(0, 0), S.Note(0, 0), S.Note(0, 0, key='C1'), S.Note(48, 1, velocity=0.4), S.Note(48, 1, velocity=0.9)])]
    ).xml(), [NOTES]), 'Open a song with several notes on the same position and instrument')
    add(suite, 'patterns', 'unicode-names', Load(lambda ctx: base(ctx, patterns=[
        S.Pattern('Ref─rain ♪', notes(0)), S.Pattern('Bridge "B" & <C>', notes(48), info='ñ ü ß', category='Ⅳ')],
        sequence=[['Ref─rain ♪'], ['Bridge "B" & <C>']]).xml(), [NOTES, 'sequence']),
        'Open a song whose pattern names, infos and categories use Unicode and markup characters')
    add(suite, 'patterns', 'duplicate-pattern-names', Load(lambda ctx: base(ctx, patterns=[
        S.Pattern('Same', notes(0)), S.Pattern('Same', notes(96))], sequence=[['Same'], ['Same']]).xml(),
        [NOTES, 'sequence']), 'Open a song with two patterns of the same name')

    def legacy_093(ctx):
        """The 0.9.3 pattern form: notes grouped in sequenceList/sequence elements."""
        text = base(ctx).xml()
        return text.replace('<noteList>', '<sequenceList>\n    <sequence>\n     <noteList>').replace(
            '</noteList>', '</noteList>\n    </sequence>\n   </sequenceList>')
    add(suite, 'patterns', 'legacy-sequence-list', Load(legacy_093, [NOTES]),
        'Open a song in the 0.9.3 form, whose pattern notes sit in sequenceList/sequence elements')


def song_sequence(suite):
    suite.setup(FAMILY, 'sequence', prepare, 'Fresh instance with the verifier samples')
    three = [S.Pattern('A', notes(0)), S.Pattern('B', notes(48)), S.Pattern('C', notes(96))]
    columns = add(suite, 'sequence', 'columns', Load(lambda ctx: base(ctx, patterns=list(three), sequence=[
        ['A', 'B'], [], ['C'], ['A', 'B', 'C'], [], []]).xml(), ['sequence']),
        'Open a song whose columns hold two, none, one and three patterns, ending with empty columns')
    add(suite, 'sequence', 'unknown-pattern', Load(lambda ctx: base(ctx, patterns=list(three), sequence=[
        ['A', 'Missing'], ['Missing'], ['C']]).xml(), ['sequence']),
        'Open a song whose sequence names a pattern the song does not have')

    def flat(ctx):
        text = base(ctx, patterns=list(three), sequence=[['A'], ['C'], ['B']]).xml()
        return re.sub(r'<patternSequence>.*?</patternSequence>',
                      '<patternSequence>\n  <patternID>A</patternID>\n  <patternID>C</patternID>\n'
                      '  <patternID>B</patternID>\n </patternSequence>', text, flags=re.S)
    add(suite, 'sequence', 'legacy-flat', Load(flat, ['sequence']),
        'Open a song whose sequence is the legacy flat list of pattern ids', requires=(columns,))
    add(suite, 'sequence', 'virtual', Load(lambda ctx: base(ctx, patterns=list(three) + [S.Pattern('V', [])],
                                                            sequence=[['V'], ['A']],
                                                            virtual=(('V', ('A', 'C')), ('B', ('Missing', 'A')))).xml(),
                                           ['virtual', 'sequence']),
        'Open a song with virtual patterns, one of them naming a missing pattern')
    add(suite, 'sequence', 'timeline', Load(lambda ctx: base(ctx, timeline=True, tempo_markers=(
        (3, 80.0), (0, 120.0), (1, 95.5), (3, 70.0), (6, 500.0)), tags=((2, 'Chorus'), (0, 'Intro ☆'),
                                                                       (2, 'Second tag'))).xml(),
        ['markers', 'tags', ('song', ('timeline',))]),
        'Open a song with unsorted tempo markers (two on one column, one above 400 BPM) and tags')
    add(suite, 'sequence', 'velocity-path', Load(lambda ctx: base(ctx, velocity_path=(
        (0.0, 1.0), (1.5, 0.25), (4.0, 0.6), (2.0, 1.4))).xml(), ['velocity_path']),
        'Open a song with an unsorted velocity automation path, one point above 1')


def song_versions(suite):
    suite.setup(FAMILY, 'versions', prepare, 'Fresh instance with the verifier samples')
    for version in ('0.9.3', '0.9.6', '1.2.0', '9.9.9'):
        add(suite, 'versions', f'version-{version}', Load(lambda ctx, v=version: base(ctx, version=v, bpm=111.0).xml(),
                                                          [('song', ('bpm', 'name')), LAYERS]),
            f'Open a song document that declares product version {version}')

    def drumkit_names(ctx):
        kit = [instrument(ctx, 'kick.wav', 0, name='Named', drumkit='GMRockKit'),
               instrument(ctx, 'snare.wav', 1, name='Lookup', drumkit='TR808EmulationKit', drumkit_lookup=1),
               instrument(ctx, 'hat.wav', 2, name='Missing kit', drumkit='No Such Kit',
                          drumkit_path=ctx.inputs('drumkits/No Such Kit'))]
        return base(ctx, instruments=kit).xml()
    add(suite, 'versions', 'drumkit-references', Load(drumkit_names, [('instruments', ('name', 'drumkit',
                                                                                       'components'))]),
        'Open a song whose instruments name the factory kits (by name, by lookup) and a kit that does not exist')


def refusals(suite):
    suite.setup(FAMILY, 'refusals', prepare, 'Fresh instance with the verifier samples')
    positive = add(suite, 'refusals', 'valid', Load(lambda ctx: base(ctx, name='Valid song', bpm=133.0).xml(),
                                                    [('song', ('name', 'bpm'))]),
                   'Open a valid verifier song')
    for step, document, description in (
            ('malformed', '<?xml version="1.0"?>\n<song><bpm>99</bpm>\n', 'a song document that is not well-formed'),
            ('not-a-song', '<?xml version="1.0"?>\n<drumkit_info><name>x</name></drumkit_info>\n',
             'a well-formed document whose root is not a song'),
            ('empty', '', 'an empty song document')):
        add(suite, 'refusals', step, Load(lambda ctx, d=document: d, [('song', ('name', 'bpm'))], before=open_known),
            f'With a known song open, try to open {description}', requires=(positive,))

    def missing(ctx):
        open_known(ctx)
        ctx.open_song('no-such-file.h2song')
        return select(ctx.song(), [('song', ('name', 'bpm'))])
    add(suite, 'refusals', 'missing-file', missing, 'With a known song open, try to open a song file that does not '
                                                    'exist', requires=(positive,))


def pattern_documents(suite):
    suite.setup(FAMILY, 'pattern-files', prepare, 'Fresh instance with the verifier samples')
    names = lambda: [('patterns', ('name', 'size', 'denominator', 'info', 'category', 'notes')), 'sequence']

    def into_song(ctx):
        name = ctx.upload('pattern-host.h2song', base(ctx, name='Pattern host').xml())
        ctx.open_song(name)
    pattern = S.Pattern('Imported', [S.Note(0, 0, velocity=0.7), S.Note(72, 1, pan=0.5, key='D0'),
                                     S.Note(150, 2, length=12)], size=192, info='from file', category='fills')
    positive = add(suite, 'pattern-files', 'current', Load(lambda ctx: S.pattern_file(pattern), names(), kind='pattern',
                                                           before=into_song),
                   'Open a pattern document into a song (/Hydrogen/OPEN_PATTERN)')
    add(suite, 'pattern-files', 'same-name', Load(lambda ctx: S.pattern_file(S.Pattern('Main', notes(24))), names(),
                                                  kind='pattern', before=into_song),
        'Open a pattern document whose pattern has the name of a pattern of the song')
    add(suite, 'pattern-files', 'unknown-instruments', Load(lambda ctx: S.pattern_file(S.Pattern(
        'Wide', [S.Note(0, 0), S.Note(24, 7), S.Note(48, 2)])), names(), kind='pattern', before=into_song),
        'Open a pattern document whose notes refer to an instrument the song does not have')
    add(suite, 'pattern-files', 'odd-meter', Load(lambda ctx: S.pattern_file(S.Pattern(
        'Five', notes(0, 120), size=120, denominator=8)), names(), kind='pattern', before=into_song),
        'Open a pattern document of 120 ticks in eighths')

    def legacy(ctx):
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<drumkit_pattern>\n'
                ' <pattern_for_drumkit>Verifier kit</pattern_for_drumkit>\n <pattern>\n'
                '  <pattern_name>Legacy</pattern_name>\n  <category>old</category>\n  <size>96</size>\n'
                '  <noteList>\n   <note>\n    <position>0</position>\n    <velocity>0.6</velocity>\n'
                '    <pan_L>1</pan_L>\n    <pan_R>0.5</pan_R>\n    <pitch>0</pitch>\n    <key>C0</key>\n'
                '    <length>-1</length>\n    <instrument>1</instrument>\n   </note>\n  </noteList>\n'
                ' </pattern>\n</drumkit_pattern>\n')
    add(suite, 'pattern-files', 'legacy', Load(legacy, names(), kind='pattern', before=into_song),
        'Open a pattern document in the legacy form (pattern_name, pan_L/pan_R, no denominator)')
    add(suite, 'pattern-files', 'unicode', Load(lambda ctx: S.pattern_file(S.Pattern(
        'Füll ♫ "x"', notes(0, 48), info='ä & <b>', category='Ⅶ')), names(), kind='pattern', before=into_song),
        'Open a pattern document whose name, info and category use Unicode and markup characters')
    add(suite, 'pattern-files', 'malformed', Load(lambda ctx: '<?xml version="1.0"?>\n<drumkit_pattern><pattern>',
                                                  names(), kind='pattern', before=into_song),
        'Try to open a pattern document that is not well-formed', requires=(positive,))


def build(suite):
    song_properties(suite)
    song_instruments(suite)
    song_patterns(suite)
    song_sequence(suite)
    song_versions(suite)
    refusals(suite)
    pattern_documents(suite)
