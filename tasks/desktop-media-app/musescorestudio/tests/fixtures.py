'''Deterministic score fixtures for the MuseScore Studio black-box benchmark.

Fixtures are generated from small specifications and never checked in as binary files. MusicXML documents are
written as text and MIDI files byte by byte in pure Python; the product own command line turns them into
projects. Everything is a function of the specifications below, so a record run and a compare run give the
application identical bytes.
'''
from __future__ import annotations

import hashlib
import struct
from xml.dom import minidom
from xml.sax.saxutils import escape, quoteattr

NL = chr(10)
QUOTE = chr(34)
# Divisions per quarter note: whole 48, half 24, quarter 12, eighth 6, sixteenth 3, triplet eighth 4.
DIVISIONS = 12
KINDS = {'whole': 48, 'half': 24, 'quarter': 12, 'eighth': 6, '16th': 3}
ACCIDENTALS = {-2: 'flat-flat', -1: 'flat', 0: 'natural', 1: 'sharp', 2: 'double-sharp'}
UNICODE_TITLE = chr(0xC9) + 'tude ' + chr(0x4E50) + chr(0x8C31)


def el(name, *children, **attrs):
    '''An XML element: attributes as keywords (None is left out), children as already escaped text or elements.'''
    shown = ''.join(' %s=%s' % (key, quoteattr(str(value))) for key, value in attrs.items() if value is not None)
    body = ''.join(children)
    return '<%s%s>%s</%s>' % (name, shown, body, name) if body else '<%s%s/>' % (name, shown)


def t(name, value, **attrs):
    '''An element with escaped text.'''
    return el(name, escape(str(value)), **attrs)


# -- items of a measure ---------------------------------------------------------------------------------------
def n(step, octave, kind='quarter', alter=0, dots=0, **extra):
    '''A pitched note. extra: tie (start, stop, both), chord, voice, staff, lyric (text or (text, syllabic)),
    tuplet ((actual, normal) plus an optional start or stop), articulation (list of names), show (print the accidental),
    grace (a grace note: no duration), slur (start or stop), fermata.'''
    return dict(extra, t='note', step=step, octave=octave, kind=kind, alter=alter, dots=dots)


def r(kind='quarter', dots=0, **extra):
    '''A rest. extra: measure (a whole-measure rest; its kind must fill the bar), voice, staff.'''
    return dict(extra, t='rest', kind=kind, dots=dots)


def dyn(mark):
    return dict(t='dyn', mark=mark)


def tempo(bpm):
    return dict(t='tempo', bpm=bpm)


def words(text):
    return dict(t='words', text=text)


def back(length):
    return dict(t='back', duration=length)


def harmony(root, kind='major', alter=0):
    '''A chord symbol before the next note.'''
    return dict(t='harmony', root=root, kind=kind, alter=alter)


def wedge(kind):
    '''A hairpin: crescendo, diminuendo or stop.'''
    return dict(t='wedge', kind=kind)


def segno():
    return dict(t='segno')


def coda():
    return dict(t='coda')


def jump(text, **sound):
    '''A jump instruction as words with its playback meaning (dalsegno, tocoda, fine).'''
    return dict(t='jump', text=text, sound=sound)


def duration(item):
    if item.get('grace'):
        return 0
    total = half = KINDS[item['kind']]
    for _ in range(item.get('dots', 0)):
        half /= 2
        total += half
    tuplet = item.get('tuplet')
    if tuplet:
        total = total * tuplet[1] / tuplet[0]
    assert total == int(total), item
    return int(total)


def note_xml(item):
    kids = []
    if item.get('grace'):
        kids.append(el('grace', slash='yes'))
    if item.get('chord'):
        kids.append(el('chord'))
    if item['t'] == 'rest':
        kids.append(el('rest', measure='yes' if item.get('measure') else None))
    else:
        pitch = [t('step', item['step'])]
        if item['alter']:
            pitch.append(t('alter', item['alter']))
        pitch.append(t('octave', item['octave']))
        kids.append(el('pitch', *pitch))
    if not item.get('grace'):
        kids.append(t('duration', duration(item)))
    tie = item.get('tie')
    if tie in ('stop', 'both'):
        kids.append(el('tie', type='stop'))
    if tie in ('start', 'both'):
        kids.append(el('tie', type='start'))
    kids.append(t('voice', item.get('voice', 1)))
    kids.append(t('type', item['kind']))
    kids += [el('dot')] * item.get('dots', 0)
    if item.get('show'):
        kids.append(t('accidental', ACCIDENTALS[item['alter']]))
    tuplet = item.get('tuplet')
    if tuplet:
        kids.append(el('time-modification', t('actual-notes', tuplet[0]), t('normal-notes', tuplet[1])))
    if item.get('staff'):
        kids.append(t('staff', item['staff']))
    notations = []
    if tie in ('stop', 'both'):
        notations.append(el('tied', type='stop'))
    if tie in ('start', 'both'):
        notations.append(el('tied', type='start'))
    if tuplet and len(tuplet) > 2 and tuplet[2]:
        notations.append(el('tuplet', type=tuplet[2]))
    if item.get('slur'):
        notations.append(el('slur', type=item['slur'], number='1'))
    marks = item.get('articulation')
    if marks:
        notations.append(el('articulations', *[el(mark) for mark in marks]))
    if item.get('fermata'):
        notations.append(t('fermata', 'normal', type='upright'))
    if notations:
        kids.append(el('notations', *notations))
    lyric = item.get('lyric')
    if lyric:
        # One verse as text or (text, syllabic[, 'extend']), or a list of verses numbered from 1.
        verses = lyric if isinstance(lyric, list) else [lyric]
        for number, verse in enumerate(verses, 1):
            if verse is None:
                continue
            verse = (verse, 'single') if isinstance(verse, str) else tuple(verse)
            parts = [t('syllabic', verse[1]), t('text', verse[0])]
            if 'extend' in verse[2:]:
                parts.append(el('extend'))
            kids.append(el('lyric', *parts, number=str(number)))
    return el('note', *kids)


def direction_xml(item):
    kind = item['t']
    if kind == 'dyn':
        return el('direction', el('direction-type', el('dynamics', el(item['mark']))), placement='below')
    if kind == 'tempo':
        metronome = el('metronome', t('beat-unit', 'quarter'), t('per-minute', item['bpm']))
        return el('direction', el('direction-type', metronome), el('sound', tempo=item['bpm']), placement='above')
    if kind == 'words':
        return el('direction', el('direction-type', t('words', item['text'])), placement='above')
    if kind == 'back':
        return el('backup', t('duration', item['duration']))
    if kind == 'harmony':
        root = [t('root-step', item['root'])] + ([t('root-alter', item['alter'])] if item['alter'] else [])
        return el('harmony', el('root', *root), t('kind', item['kind']))
    if kind == 'wedge':
        return el('direction', el('direction-type', el('wedge', type=item['kind'])), placement='below')
    if kind in ('segno', 'coda'):
        return el('direction', el('direction-type', el(kind)), el('sound', **{kind: kind}), placement='above')
    if kind == 'jump':
        return el('direction', el('direction-type', t('words', item['text'])), el('sound', **item['sound']),
                  placement='above')
    raise ValueError('unknown item ' + kind)


def attributes_xml(attrs, first):
    kids = []
    if first:
        kids.append(t('divisions', DIVISIONS))
    if 'fifths' in attrs:
        key = [t('fifths', attrs['fifths'])]
        if attrs.get('mode'):
            key.append(t('mode', attrs['mode']))
        kids.append(el('key', *key))
    if 'time' in attrs:
        kids.append(el('time', t('beats', attrs['time'][0]), t('beat-type', attrs['time'][1])))
    if 'staves' in attrs:
        kids.append(t('staves', attrs['staves']))
    for number, sign, line in attrs.get('clefs', ()):
        kids.append(el('clef', t('sign', sign), t('line', line), number=number))
    if 'transpose' in attrs:
        diatonic, chromatic = attrs['transpose']
        kids.append(el('transpose', t('diatonic', diatonic), t('chromatic', chromatic)))
    return el('attributes', *kids) if kids else ''


def barline_xml(location, style, repeat=None, ending=None):
    kids = [t('bar-style', style)]
    if ending:
        kids.append(el('ending', number=ending[0], type=ending[1]))
    if repeat:
        kids.append(el('repeat', direction=repeat))
    return el('barline', *kids, location=location)


def measure_xml(number, spec, first):
    '''One measure. spec: attrs, items, left (repeat), right (repeat or final), ending (number of a volta that
    starts here; with right set it also ends here, otherwise it is left open with discontinue).'''
    kids = []
    ending = spec.get('ending')
    if spec.get('left') == 'repeat':
        kids.append(barline_xml('left', 'heavy-light', 'forward'))
    elif ending:
        kids.append(barline_xml('left', 'regular', ending=(ending, 'start')))
    kids.append(attributes_xml(spec.get('attrs', {}), first))
    for item in spec.get('items', ()):
        kids.append(note_xml(item) if item['t'] in ('note', 'rest') else direction_xml(item))
    right = spec.get('right')
    close = (ending, 'stop' if right else 'discontinue') if ending else None
    if right == 'repeat':
        kids.append(barline_xml('right', 'light-heavy', 'backward', ending=close))
    elif right == 'final':
        kids.append(barline_xml('right', 'light-heavy', ending=close))
    elif close:
        kids.append(barline_xml('right', 'regular', ending=close))
    return el('measure', *kids, number=number)


def measures_xml(instrument_spec):
    '''The measures of one part; every measure must fill exactly one bar of the current time signature.'''
    bar, out = None, []
    for number, spec in enumerate(instrument_spec['measures'], 1):
        time = spec.get('attrs', {}).get('time')
        if time:
            bar = DIVISIONS * 4 * time[0] // time[1]
        items = spec.get('items', ())
        total = sum(duration(i) for i in items if i['t'] in ('note', 'rest') and not i.get('chord'))
        total -= sum(i['duration'] for i in items if i['t'] == 'back')
        assert total == bar, (instrument_spec['name'], number, total, bar)
        out.append(measure_xml(number, spec, number == 1))
    return out


def score_xml(score):
    head = []
    if score.get('title'):
        head.append(el('work', t('work-title', score['title'])))
    ident = []
    if score.get('composer'):
        ident.append(t('creator', score['composer'], type='composer'))
    if score.get('copyright'):
        ident.append(t('rights', score['copyright']))
    if ident:
        head.append(el('identification', *ident))
    listing, body = [], []
    for index, spec in enumerate(score['parts'], 1):
        listing.append(el('score-part', t('part-name', spec['name']), id='P%d' % index))
        body.append(el('part', *measures_xml(spec), id='P%d' % index))
    root = el('score-partwise', *head, el('part-list', *listing), *body, version='3.1')
    declaration = '<?xml version=' + QUOTE + '1.0' + QUOTE + ' encoding=' + QUOTE + 'UTF-8' + QUOTE + '?>'
    return (declaration + NL + root + NL).encode('utf-8')


def m(*items, **spec):
    return dict(spec, items=list(items))


def instrument(name, *measures):
    return dict(name=name, measures=list(measures))


def bar_attrs(fifths=0, time=(4, 4), clef='treble', **more):
    clefs = {'treble': [(None, 'G', 2)], 'bass': [(None, 'F', 4)]}[clef]
    return dict(more, fifths=fifths, time=time, clefs=clefs)


def scores():
    '''Name to score specification; each becomes name.musicxml.'''
    out = {}
    out['scale-c'] = dict(parts=[instrument('Piano',
        m(n('C', 4), n('D', 4), n('E', 4), n('F', 4), attrs=bar_attrs()),
        m(n('G', 4), n('A', 4), n('B', 4), n('C', 5)))])
    out['scale-g-34'] = dict(parts=[instrument('Piano',
        m(n('G', 4), n('A', 4), n('B', 4), attrs=bar_attrs(1, (3, 4))),
        m(n('C', 5), n('D', 5), n('E', 5)),
        m(n('F', 5, alter=1), n('E', 5), n('D', 5), right='final'))])
    out['c-minor-eighths'] = dict(parts=[instrument('Piano',
        m(n('C', 5, 'eighth'), n('D', 5, 'eighth'), n('E', 5, 'eighth', alter=-1), n('F', 5, 'eighth'),
          n('G', 5, 'eighth'), n('A', 5, 'eighth', alter=-1), n('B', 5, 'eighth', alter=-1), n('C', 6, 'eighth'),
          attrs=bar_attrs(-3, (4, 4), mode='minor')),
        m(n('C', 6, 'half'), r('half')))])
    out['accidentals'] = dict(parts=[instrument('Piano',
        m(n('C', 4, alter=1, show=True), n('D', 4, alter=-1, show=True), n('E', 4, show=True),
          n('F', 4, alter=2, show=True), attrs=bar_attrs()),
        m(n('G', 4, alter=-2, show=True), n('A', 4, alter=1), n('B', 4, alter=-1), n('C', 5)))])
    out['rhythms'] = dict(parts=[instrument('Piano',
        m(n('C', 4, 'half'), n('D', 4), r(), attrs=bar_attrs()),
        m(n('E', 4, dots=1), n('F', 4, 'eighth'), n('G', 4), n('A', 4, 'eighth'), n('B', 4, 'eighth')),
        m(n('C', 5, '16th'), n('B', 4, '16th'), n('A', 4, '16th'), n('G', 4, '16th'), n('D', 5, 'eighth'),
          n('C', 5, 'eighth'), n('F', 4, 'half')),
        m(n('C', 4, 'whole')))])
    out['ties'] = dict(parts=[instrument('Piano',
        m(n('C', 4, 'half'), n('D', 4), n('E', 4, tie='start'), attrs=bar_attrs()),
        m(n('E', 4, 'half', tie='stop'), n('F', 4, 'half')))])
    out['tuplets'] = dict(parts=[instrument('Piano',
        m(n('C', 4, 'eighth', tuplet=(3, 2, 'start')), n('D', 4, 'eighth', tuplet=(3, 2)),
          n('E', 4, 'eighth', tuplet=(3, 2, 'stop')), n('F', 4), n('G', 4, 'half'), attrs=bar_attrs()),
        m(n('C', 5, tuplet=(3, 2, 'start')), n('B', 4, tuplet=(3, 2)), n('A', 4, tuplet=(3, 2, 'stop')),
          n('G', 4, 'half')))])
    out['dynamics-tempo'] = dict(parts=[instrument('Piano',
        m(tempo(90), dyn('mf'), words('dolce'), n('C', 4), n('D', 4), n('E', 4), n('F', 4), attrs=bar_attrs()),
        m(dyn('f'), n('G', 4, articulation=['staccato']), n('A', 4, articulation=['accent']),
          n('B', 4, articulation=['tenuto']), n('C', 5)),
        m(dyn('pp'), n('C', 5, 'half'), n('G', 4, 'half'), right='final'))])
    out['lyrics'] = dict(parts=[instrument('Voice',
        m(n('E', 4, lyric=('Hel', 'begin')), n('G', 4, lyric=('lo', 'end')), n('C', 5, 'half', lyric='world'),
          attrs=bar_attrs()),
        m(n('B', 4, lyric=('good', 'begin')), n('A', 4, lyric=('night', 'end')), n('G', 4, 'half', lyric='now')))])
    out['chords'] = dict(parts=[instrument('Piano',
        m(n('C', 4), n('E', 4, chord=True), n('G', 4, chord=True), n('F', 4), n('A', 4, chord=True),
          n('C', 5, chord=True), n('G', 4, 'half'), n('B', 4, chord=True), n('D', 5, chord=True),
          attrs=bar_attrs()))])
    out['two-parts'] = dict(parts=[
        instrument('Violin',
                   m(n('C', 5), n('D', 5), n('E', 5), n('F', 5), attrs=bar_attrs()),
                   m(n('G', 5, 'half'), n('E', 5, 'half'))),
        instrument('Cello',
                   m(n('C', 3, 'half'), n('G', 2, 'half'), attrs=bar_attrs(clef='bass')),
                   m(n('C', 3, 'whole')))])
    grand = dict(fifths=0, time=(4, 4), staves=2, clefs=[(1, 'G', 2), (2, 'F', 4)])
    out['piano-grand'] = dict(parts=[instrument('Piano',
        m(n('C', 5, staff=1), n('D', 5, staff=1), n('E', 5, staff=1), n('F', 5, staff=1), back(48),
          n('C', 3, 'whole', staff=2, voice=5), attrs=grand),
        m(n('G', 4, 'half', staff=1), n('E', 4, 'half', staff=1), back(48),
          n('C', 3, 'half', staff=2, voice=5), n('G', 2, 'half', staff=2, voice=5)))])
    out['repeats'] = dict(parts=[instrument('Piano',
        m(n('C', 4), n('D', 4), n('E', 4), n('F', 4), attrs=bar_attrs(), left='repeat'),
        m(n('G', 4), n('A', 4), n('B', 4), n('C', 5), right='repeat'),
        m(n('D', 5, 'half'), n('B', 4, 'half')),
        m(n('C', 5, 'whole'), right='final'))])
    out['bass-clef'] = dict(parts=[instrument('Bass',
        m(n('C', 2), n('E', 2), n('G', 2), n('C', 3), attrs=bar_attrs(clef='bass')),
        m(n('F', 2, 'half'), n('C', 2, 'half')))])
    out['titled'] = dict(title='Test Piece', composer='A. Composer', copyright='Copyright 2026 Test',
                         parts=[instrument('Flute',
                                           m(n('A', 4), n('B', 4), n('C', 5), n('D', 5), attrs=bar_attrs()),
                                           m(n('E', 5, 'whole')))])
    out['unicode-title'] = dict(title=UNICODE_TITLE, composer=UNICODE_TITLE,
                                parts=[instrument('Flute', m(n('G', 4, 'whole'), attrs=bar_attrs()))])
    # Features beyond the basic notation: each fixture isolates one family so a wrong reading shows in its own points.
    out['two-voices'] = dict(parts=[instrument('Piano',
        m(n('E', 5), n('F', 5), n('G', 5, 'half'), back(48), n('C', 4, 'half', voice=2), n('G', 3, 'half', voice=2),
          attrs=bar_attrs()),
        m(n('A', 5, 'half'), n('G', 5, 'half'), back(48), n('F', 3, voice=2), n('G', 3, voice=2),
          n('C', 4, 'half', voice=2)))])
    out['grace-notes'] = dict(parts=[instrument('Piano',
        m(n('D', 5, 'eighth', grace=True), n('C', 5), n('E', 4), n('B', 4, '16th', grace=True), n('A', 4, 'half'),
          attrs=bar_attrs()),
        m(n('A', 4, 'eighth', grace=True), n('G', 4, 'whole')))])
    out['measure-rests'] = dict(parts=[instrument('Piano',
        m(n('C', 5), n('E', 5), n('G', 5, 'half'), attrs=bar_attrs()),
        m(r('whole', measure=True)), m(r('whole', measure=True)),
        m(n('C', 5, 'whole'), right='final'))])
    out['voltas'] = dict(parts=[instrument('Piano',
        m(n('C', 4), n('D', 4), n('E', 4), n('F', 4), attrs=bar_attrs(), left='repeat'),
        m(n('G', 4, 'half'), n('E', 4, 'half'), ending='1', right='repeat'),
        m(n('A', 4, 'half'), n('B', 4, 'half'), ending='2'),
        m(n('C', 5, 'whole'), right='final'))])
    out['segno-coda'] = dict(parts=[instrument('Piano',
        m(n('C', 4), n('D', 4), n('E', 4), n('F', 4), attrs=bar_attrs()),
        m(segno(), n('G', 4), n('A', 4), n('B', 4), n('C', 5)),
        m(n('D', 5, 'half'), jump('To Coda', tocoda='coda'), n('B', 4, 'half')),
        m(n('A', 4, 'half'), n('F', 4, 'half'), jump('D.S. al Coda', dalsegno='segno')),
        m(coda(), n('C', 5, 'whole'), right='final'))])
    out['clef-change'] = dict(parts=[instrument('Cello',
        m(n('C', 3), n('E', 3), n('G', 3), n('C', 4), attrs=bar_attrs(clef='bass')),
        m(n('E', 4), n('G', 4), n('C', 5, 'half'), attrs={'clefs': [(None, 'G', 2)]}),
        m(n('A', 4), n('F', 4), n('D', 4), n('B', 3), attrs={'clefs': [(None, 'F', 4)]}),
        m(n('C', 3, 'whole'), right='final'))])
    out['key-change'] = dict(parts=[instrument('Piano',
        m(n('C', 4), n('E', 4), n('G', 4), n('C', 5), attrs=bar_attrs()),
        m(n('D', 4), n('F', 4, alter=1), n('A', 4), n('D', 5), attrs={'fifths': 2}),
        m(n('E', 4, alter=-1), n('G', 4), n('B', 4, alter=-1), n('E', 5, alter=-1), attrs={'fifths': -3}),
        m(n('E', 5, 'whole', alter=-1), right='final'))])
    out['tempo-changes'] = dict(parts=[instrument('Piano',
        m(tempo(80), n('C', 4), n('D', 4), n('E', 4), n('F', 4), attrs=bar_attrs()),
        m(tempo(160), n('G', 4), n('A', 4), n('B', 4), n('C', 5)),
        m(tempo(60), n('C', 5, 'half'), n('G', 4, 'half'), right='final'))])
    out['slurs-hairpins'] = dict(parts=[instrument('Violin',
        m(dyn('p'), wedge('crescendo'), n('C', 5, slur='start'), n('D', 5), n('E', 5), n('F', 5, slur='stop'),
          attrs=bar_attrs()),
        m(wedge('stop'), dyn('f'), n('G', 5, slur='start'), wedge('diminuendo'), n('F', 5), n('E', 5),
          n('D', 5, slur='stop')),
        m(wedge('stop'), dyn('mp'), n('C', 5, 'whole', fermata=True), right='final'))])
    out['chord-symbols'] = dict(parts=[instrument('Guitar',
        m(harmony('C'), n('E', 4, 'half'), harmony('A', 'minor'), n('C', 5, 'half'), attrs=bar_attrs()),
        m(harmony('F'), n('F', 4, 'half'), harmony('G', 'dominant'), n('B', 4, 'half')),
        m(harmony('B', 'major', -1), n('D', 5, 'half'), harmony('C'), n('C', 5, 'half'), right='final'))])
    out['lyrics-verses'] = dict(parts=[instrument('Voice',
        m(n('G', 4, lyric=['Twin', 'Up']), n('G', 4, lyric=['kle', 'a']), n('D', 5, lyric=['twin', 'bove']),
          n('D', 5, lyric=['kle', 'the']), attrs=bar_attrs()),
        m(n('E', 5, lyric=['lit', 'world']), n('E', 5, lyric=['tle', 'so']), n('D', 5, 'half', lyric=['star', 'high']),
          right='final'))])
    out['lyrics-melisma'] = dict(parts=[instrument('Voice',
        m(tempo(72), n('C', 5, lyric=('Glo', 'begin')), n('D', 5), n('E', 5), n('F', 5, lyric=('ri', 'middle')),
          attrs=bar_attrs()),
        m(n('G', 5, 'half', lyric=('a', 'end', 'extend')), n('F', 5), n('E', 5)),
        m(tempo(120), n('D', 5, lyric='in'), n('C', 5, lyric='ex'), n('B', 4, 'half', lyric='cel'), right='final'))])
    # A B flat clarinet: written a major second above the sounding pitch (MusicXML transpose -1 diatonic, -2 chromatic).
    out['clarinet-bb'] = dict(parts=[instrument('Clarinet in B' + chr(0x266D),
        m(n('D', 4), n('E', 4), n('F', 4, alter=1), n('G', 4), attrs=bar_attrs(2, transpose=(-1, -2))),
        m(n('A', 4), n('B', 4), n('C', 5, alter=1), n('D', 5), right='final'))])
    return out


# -- MIDI -----------------------------------------------------------------------------------------------------
def vlq(value):
    chunk = [value & 127]
    value >>= 7
    while value:
        chunk.append((value & 127) | 128)
        value >>= 7
    return bytes(reversed(chunk))


def track_chunk(events):
    data = bytearray()
    last = 0
    for tick, _order, raw in sorted(events):
        data += vlq(tick - last) + raw
        last = tick
    data += vlq(0) + bytes([255, 47, 0])
    return b'MTrk' + struct.pack('>I', len(data)) + bytes(data)


def tempo_event(bpm):
    return bytes([255, 81, 3]) + (60_000_000 // bpm).to_bytes(3, 'big')


def midi_file(tracks, *, division=480, bpm=120, signature=(4, 4), programs=None, tempo_changes=()):
    '''A format 1 file: a conductor track, then one track per note list of (start, length, pitch, velocity) ticks.'''
    assert len(tracks) <= 8
    programs = programs or [0] * len(tracks)
    conductor = [(0, 0, tempo_event(bpm)),
                 (0, 1, bytes([255, 88, 4, signature[0], signature[1].bit_length() - 1, 24, 8]))]
    conductor += [(tick, 0, tempo_event(value)) for tick, value in tempo_changes]
    chunks = [track_chunk(conductor)]
    for index, notes in enumerate(tracks):
        events = [(0, 0, bytes([192 | index, programs[index]]))]
        for start, length, pitch, velocity in notes:
            events.append((start, 2, bytes([144 | index, pitch, velocity])))
            events.append((start + length, 1, bytes([128 | index, pitch, 0])))
        chunks.append(track_chunk(events))
    return b'MThd' + struct.pack('>IHHH', 6, 1, len(chunks), division) + b''.join(chunks)


def midi_files():
    quarter = 480
    melody = [(i * quarter, quarter, pitch, 80) for i, pitch in enumerate([60, 62, 64, 65, 67, 69, 71, 72])]
    bass_line = [(0, 4 * quarter, 48, 70), (4 * quarter, 4 * quarter, 55, 70)]
    waltz = [(i * quarter, quarter, pitch, 80) for i, pitch in enumerate([67, 71, 74, 72, 69, 66])]
    return {
        'melody.mid': midi_file([melody]),
        'two-track.mid': midi_file([melody, bass_line], programs=[0, 32]),
        'tempo-change.mid': midi_file([melody], bpm=100, tempo_changes=[(4 * quarter, 140)]),
        'waltz.mid': midi_file([waltz], bpm=90, signature=(3, 4)),
    }


def catalog():
    '''File name to bytes of every fixture.'''
    files = {name + '.musicxml': score_xml(spec) for name, spec in scores().items()}
    files.update(midi_files())
    return files


def selfcheck():
    first, second = catalog(), catalog()
    assert first == second, 'fixtures are not deterministic'
    summary = {}
    for name, data in sorted(first.items()):
        if name.endswith('.musicxml'):
            minidom.parseString(data)
        else:
            assert data[:4] == b'MThd' and struct.unpack('>IHHH', data[4:14])[0] == 6, name
        summary[name] = hashlib.sha256(data).hexdigest()[:12]
    return summary


if __name__ == '__main__':
    for fixture, digest in selfcheck().items():
        print(digest, fixture)
