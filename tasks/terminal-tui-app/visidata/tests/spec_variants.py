'''Variant families: one command or option applied to every column, every row position or many option values,
driven through batch replays and conversions (vd -b -p LOG.vdj and vd -b IN -o OUT).

Every point has its own column, row, format or file, so an implementation that gets one case wrong differs from the
reference on that point alone. The expected values come from the frozen reference; the requirement text describes
the behaviour and must also hold for an equivalent reimplementation.
'''
import base64
import json
import zlib

from spec_core import *
from spec_logs import case, checkpoint
from spec_matrix import MIX_ROWS, SORT_COLS

E, N, O, EURO, SNOW = chr(0xe9), chr(0xf1), chr(0xeb), chr(0x20ac), chr(0x2603)
LAST = len(SORT_COLS) - 1
ROWS = len(MIX_ROWS) - 1
ACCENT_ROWS = [['id', 'name'], ['1', 'caf' + E], ['2', 'se' + N + 'or'], ['3', 'Zo' + O]]
EURO_ROWS = [['id', 'price'], ['1', EURO + '5'], ['2', '7' + EURO]]
TSV_ROWS = [['id', 'text', 'note'], ['1', 'a,b', 'comma'], ['2', 'say ' + Q + 'hi' + Q, 'quote'],
            ['3', 'semi;pipe|#:', 'delims'], ['4', 'plain', 'x']]
LINES = ['# note', 'x,y,z', 'a,b,c', 'd,e,f', 'g,h,i', 'j,k,l']
FLOAT_FORMATS = ['{:.0f}', '{:.1f}', '{:.3f}', '{:.4f}', '{:08.2f}', '{:+.1f}', '{:.2e}']
DATE_FORMATS = ['%Y', '%m/%d', '%d %B %Y', '%a %d %b', '%y%m%d', '%j', '%U', '%B', '%A']
CURRENCY_FORMATS = ['%.3f']
JSON_SHAPES = {
    'unicode.json': json.dumps([{'k': 'caf' + E, 'j': 'line' + NL + 'two'}, {'k': 'snow' + SNOW, 'j': 'tab' + TAB + 'x'}]),
    'numbers.json': json.dumps([{'n': 1}, {'n': -2.5}, {'n': 3.0}, {'n': 450.0}, {'n': 12345678901234567890}, {'n': True},
                                {'n': None}, {'n': 'str'}]),
    'nestlist.json': json.dumps([[{'a': 1}, {'a': 2}], [{'a': 3}]]),
    'keys.json': json.dumps([{'b': 1, 'a': 2}, {'c': 3, 'b': 4}, {'a': 5}]),
    'strings.jsonl': NL.join(json.dumps(x) for x in [{'s': 'q' + Q + 'uote'}, {'s': 'back' + chr(92) + 'slash'}, {'s': ''}]) + NL,
}


def M(longname, col='', row='', inp=''):
    return entry(longname, col, row, inp, sheet='mix')


def mix(name, entries, requirement, **kw):
    return case(name, entries, requirement, opens='mix.csv', **kw)


def family(key_, feature, cases):
    files = {'mix.csv': f(csv_text(MIX_ROWS))}
    files.update({'c-' + c['name'] + '.vdj': f(c['log']) for c in cases})
    return program(key_, feature, files, [checkpoint(c) for c in cases])


def columns():
    cases = []
    for n, col in enumerate(SORT_COLS):
        cases.append(mix('hide-' + col, [M('hide-col', col)], 'Hiding the %s column leaves it out of the saved sheet.' % col))
        cases.append(mix('rename-' + col, [M('rename-col', col, inp='new_' + col)], 'Renaming the %s column changes only its header.' % col))
        cases.append(mix('freeze-' + col, [M('freeze-col', col)], 'Freezing the %s column adds a column with its current values.' % col))
        if n >= 1:
            cases.append(mix('key-' + col, [M('key-col-on', col), M('key-col-on', SORT_COLS[(n + 2) % 7 or 3])], 'Making %s and then %s key columns puts both at the left in that order.' % (col, SORT_COLS[(n + 2) % 7 or 3])))
            cases.append(mix('left-' + col, [M('slide-left', col)], 'Sliding %s left swaps it with its left neighbour.' % col))
        if n >= 2:
            cases.append(mix('left2-' + col, [M('slide-left', col), M('slide-left', col)], 'Sliding %s left twice moves it two places.' % col))
        if n >= 3:
            cases.append(mix('leftmost-' + col, [M('slide-leftmost', col)], 'Sliding %s to the far left makes it the first column.' % col))
        if n <= LAST - 2:
            cases.append(mix('right2-' + col, [M('slide-right', col), M('slide-right', col)], 'Sliding %s right twice moves it two places.' % col))
        if n <= LAST - 3:
            cases.append(mix('rightmost-' + col, [M('slide-rightmost', col)], 'Sliding %s to the far right makes it the last column.' % col))
    return cases


def rows():
    cases = []
    for r in range(ROWS):
        cases.append(mix('delete-%02d' % r, [M('delete-row', row=r)], 'Deleting row %d removes exactly that row.' % r))
        cases.append(mix('add-%02d' % r, [M('add-row', row=r)], 'A new empty row is inserted below row %d.' % r))
        cases.append(mix('copy-%02d' % r, [M('copy-row', row=r), M('paste-after', row=ROWS - 1 - r)],
                         'Row %d copied and pasted below row %d appears in its new place.' % (r, ROWS - 1 - r)))
        cases.append(mix('edit-%02d' % r, [M('edit-cell', SORT_COLS[r % 7], row=r, inp='E%d' % r)],
                         'Editing the %s cell of row %d replaces only that value.' % (SORT_COLS[r % 7], r)))
        cases.append(mix('pick-%02d' % r, [M('select-row', row=r), M('dup-selected')], 'Selecting row %d and duplicating the selection keeps only that row.' % r))
    for r in range(1, ROWS):
        cases.append(mix('up-%02d' % r, [M('slide-up', row=r)], 'Sliding row %d up swaps it with the row above.' % r))
    for r in range(ROWS - 2):
        cases.append(mix('down2-%02d' % r, [M('slide-down-n', row=r, inp='2')], 'Sliding row %d down by two moves it two places.' % r))
    for r in range(2, ROWS):
        cases.append(mix('top-%02d' % r, [M('slide-top', row=r)], 'Sliding row %d to the top makes it the first row.' % r))
    for r in range(ROWS - 3):
        cases.append(mix('bottom-%02d' % r, [M('slide-bottom', row=r)], 'Sliding row %d to the bottom makes it the last row.' % r))
    return cases


def formats():
    cases = []
    for n, fmt in enumerate(FLOAT_FORMATS):
        cases.append(mix('ff%d' % n, [M('type-float', 'price')], 'The float display format %s sets how every float cell is shown.' % fmt,
                         args=['--disp-float-fmt', fmt]))
    for n, fmt in enumerate(DATE_FORMATS):
        cases.append(mix('df%d' % n, [M('type-date', 'day')], 'The date display format %s sets how every date cell is shown.' % fmt,
                         args=['--disp-date-fmt', fmt]))
    for n, fmt in enumerate(CURRENCY_FORMATS):
        cases.append(mix('cf%d' % n, [M('type-currency', 'price')], 'A currency column is shown with two decimals even when the currency display format %s is given.' % fmt,
                         args=['--disp-currency-fmt', fmt]))
    return cases


# types.sqlite, zlib-compressed: the 16384-byte database file that sqlite3 serialize() wrote for the frozen manifest
# after: create table alpha (i integer, r real, t text, n integer); insert into alpha values (1, 1.5, 'x', NULL),
# (-2, 2.0, '', 0), (3, 1e10, 'caf' + E, 7); create table beta (k text primary key, v real); insert into beta values
# ('a', 0.1), ('b', NULL). Frozen bytes: serialize() needs Python 3.11 and its page layout belongs to the SQLite
# library.
TYPES_DB = (
    'eNrt171KA0EQB/DZ3Vw+1LgihGunM4E0YheLmEi6gKjpw55u9Min5ylJo8+hLyBW1tY+gq8g2FiIIAiCeHdBRCvbyP8HO8N+zrazu930Q8ud'
    'YdA3Ia/REglBG8w0laJv8tdc0B/l9RUpXSF9oyv6jAAAAAAAAABmSF2m3UJB+KHxetazUYqG2txp1FoNbtXqzQbHK1zscmjHIY8Cv2+CCXft'
    'pMynHFjTK62otLteEOQP9u34+KgXteJtcxIOk3k7vt5ejWPcdmfjolsi7bquOE+Kmt7o0CRB/iibLHHRZ38Q2gMblDlIypU5TL5S5sHXVikf'
    'Par0Peln/RglAAAAAAAAAJgNy8oRjisUydb8A+2Zzt11JiMdIfLZD7konFxGU/VtenYc9/9SP5F+iQIAAAAAAAAAzLyUVJq8BaF0xlRvL2KX'
    'c0n//0r6PQoAAAAAAAAA8H84SgtPppTOmU8hWFwf')


def types_db():
    return zlib.decompress(base64.b64decode(TYPES_DB))


def fixtures():
    files = {
        'mix.csv': csv_text(MIX_ROWS), 'tricky.tsv': plain(TSV_ROWS), 'accent.csv': csv_text(ACCENT_ROWS),
        'euro.csv': csv_text(EURO_ROWS), 'accent-latin1.csv': csv_text(ACCENT_ROWS).encode('latin-1'),
        'accent-utf16.csv': csv_text(ACCENT_ROWS).encode('utf-16'), 'accent-sig.csv': csv_text(ACCENT_ROWS).encode('utf-8-sig'),
        'euro-cp1252.csv': csv_text(EURO_ROWS).encode('cp1252'), 'lines.csv': NL.join(LINES) + NL, 'types.sqlite': types_db(),
    }
    files.update(JSON_SHAPES)
    return {name: f(data) for name, data in files.items()}


def convert(cid, args, out, mode, requirement):
    return step(cid, 'Convert with the case ' + cid + '.', [batch(args, out)], [('file', requirement, file_(out, mode))])


def conversions():
    cps = []
    for k in (0, 1, 3, 4, 8):
        cps.append(convert('json-indent-%d' % k, ['--json-indent', str(k), 'mix.csv'], 'ji%d.json' % k, 'text', 'JSON output is indented by %d spaces.' % k))
    for delim in (';', '|', ':', '#'):
        cps.append(convert('csv-out-' + str(ord(delim)), ['--csv-delimiter', delim, 'tricky.tsv'], 'co%d.csv' % ord(delim), 'text',
                           'The csv delimiter %s separates the saved cells and decides which cells need quotes.' % delim))
    for mode in (1,):
        cps.append(convert('csv-quoting-%d' % mode, ['--csv-quoting', str(mode), 'tricky.tsv'], 'cq%d.csv' % mode, 'text',
                           'Csv quoting mode %d decides which saved cells are quoted.' % mode))
    for quote in (chr(39), '~'):
        cps.append(convert('csv-quotechar-%d' % ord(quote), ['--csv-quotechar', quote, 'tricky.tsv'], 'cc%d.csv' % ord(quote), 'text',
                           'The csv quote character %s wraps the cells that need quotes.' % quote))
    for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'utf-16', 'utf-16-le', 'utf-16-be', 'utf-32'):
        cps.append(convert('save-enc-' + enc, ['--save-encoding', enc, 'accent.csv'], 'se-%s.tsv' % enc, 'bytes',
                           'The %s save encoding sets the bytes written for the accented table.' % enc))
    for enc in ('cp1252', 'utf-8'):
        cps.append(convert('save-euro-' + enc, ['--save-encoding', enc, 'euro.csv'], 'ee-%s.tsv' % enc, 'bytes',
                           'The %s save encoding sets the bytes written for the euro sign.' % enc))
    for name, enc in (('accent-latin1.csv', 'latin-1'), ('accent-utf16.csv', 'utf-16'), ('euro-cp1252.csv', 'cp1252')):
        cps.append(convert('read-' + name.replace('.', '-'), ['--encoding', enc, name], 'rd-' + name.replace('.csv', '.tsv'), 'text',
                           'The %s input encoding decodes the file the way the reference does.' % enc))
    cps.append(convert('read-accent-sig', ['accent-sig.csv'], 'rd-sig.tsv', 'text', 'A UTF-8 byte order mark is not part of the first header.'))
    for skip in range(4):
        for header in range(4):
            cps.append(convert('lines-%d-%d' % (skip, header), ['--skip', str(skip), '--header', str(header), 'lines.csv'], 'lines-%d-%d.tsv' % (skip, header), 'text',
                               'Skipping %d lines and taking %d header rows builds the table the way the reference does.' % (skip, header)))
    for name in JSON_SHAPES:
        stem = name.replace('.', '-')
        cps.append(convert('vj-' + stem, [name], 'vj-%s.tsv' % stem, 'text', 'The input %s loads the way the reference loads it.' % name))
    for sheet in ('alpha', 'beta'):
        cps.append(convert('sq-' + sheet, ['types.sqlite', '+types:%s::' % sheet], 'sq-%s.tsv' % sheet, 'text', 'The SQLite table %s loads with its column types.' % sheet))
    cps.append(convert('sq-index', ['types.sqlite'], 'sq-index.tsv', 'text', 'Opening a SQLite file lists its tables with their sizes.'))
    return program('vr-convert', 'conversion', fixtures(), cps)


def episodes():
    return [family('vr-columns', 'columns', columns()), family('vr-rows', 'rows', rows()),
            family('vr-formats', 'types', formats()), conversions()]
