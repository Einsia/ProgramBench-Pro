'''Loaders, savers and their options, driven through the batch command-line channel (vd -b IN -o OUT).

Every checkpoint runs one batch conversion and reads the written file back through the workspace inspector. The
expected values come from the frozen reference; the fixtures give each rule an input on which a wrong
implementation writes something different (quotes, commas, newlines, tabs, non-ASCII text, empty cells).
'''
import base64
import json
import zlib

from spec_core import *

TRICKY_ROWS = [
    ['id', 'text', 'note'], ['1', 'plain', 'x'], ['2', 'a,b', 'comma'], ['3', 'say ' + Q + 'hi' + Q, 'quote'],
    ['4', 'two' + NL + 'lines', 'newline'], ['5', 'caf' + chr(0xe9) + ' ' + chr(0x2603), 'unicode'],
    ['6', '  padded  ', 'spaces'], ['7', '', 'empty'], ['8', 'tab' + TAB + 'here', 'tab'],
    ['9', 'semi;pipe|', 'delims']]
DATA_JSON = json.dumps([{'id': 1, 'name': 'ann', 'tags': ['a', 'b'], 'meta': {'k': 1}},
                        {'id': 2, 'name': 'bo', 'tags': [], 'meta': {'k': 2}}])
LINES_JSONL = NL.join(json.dumps(x) for x in [{'a': 1, 'b': 'x'}, {'a': 2, 'c': True}]) + NL
SHAPES = {
    'dictroot.json': json.dumps({'a': {'x': 1, 'y': 'p'}, 'b': {'x': 2, 'y': 'q'}}),
    'scalars.json': json.dumps([1, 2, 'three', None, True]),
    'lists.json': json.dumps([[1, 2], [3, 4]]),
    'nested.jsonl': json.dumps({'a': {'b': 1}, 'c': [1, 2]}) + NL + json.dumps({'a': {'b': 2}, 'c': []}) + NL,
    'ragged.tsv': plain([['a', 'b', 'c'], ['1', '2'], ['3', '4', '5', '6']]),
    'bom.csv': (chr(0xfeff) + 'id,name' + NL + '1,x' + NL).encode('utf-8'),
    'qnl.csv': 'id,t' + NL + '1,' + Q + 'two' + NL + 'lines' + Q + NL,
    'dupheads.csv': 'a,a,b' + NL + '1,2,3' + NL,
    'emptyhead.csv': 'a,,c' + NL + '1,2,3' + NL,
    'blank.csv': 'a,b' + NL + '1,2' + NL + NL + '3,4' + NL,
    'spaces.csv': 'a, b' + NL + '1, ' + Q + 'x y' + Q + NL,
    'crlf.csv': 'a,b' + CR + NL + '1,2' + CR + NL,
    'empty.csv': '',
    'onlyheader.csv': 'a,b' + NL,
}


# people.sqlite, zlib-compressed: the 12288-byte database file that sqlite3 serialize() wrote for the frozen manifest
# after: create table people (id integer, name text, score real, note text); insert into people values
# (1, 'ann', 1.5, 'x'), (2, 'bo', 2.0, NULL), (3, 'cy', NULL, ''); create table pets (owner integer, kind text);
# insert into pets values (1, 'cat'), (1, 'dog'), (2, 'fish'); create view v as select name from people.
# Frozen bytes: serialize() needs Python 3.11 and its page layout belongs to the SQLite library.
PEOPLE_DB = (
    'eNrt2DFPwkAUB/C7VgoM5CSkIWxvhMimu6DpYMKiEh2Mw1EObCw90l4Kjn4Wv5Szg5uJI6M9S4JxcpTk/0uu7/rS+6fru+vLUWQUzXS6kIaO'
    '2SHjnA2IWMllO3Z/8OOdsz9q2MPiiIkXIYsCAAAAAAAA8J+duJ4vRO0+j9Qqz8+vguE4oJuL4JZykhllKlahoUQuinE61QtaKr2M1cDx2r7P'
    'lZGTWC2Vyexyt6fHw7NRQLZDXb1KVEpRYtRcpX16jJIpGbU2vTtebXc6/Lm5jbCp5dP5FWN71I2mu5Tvv7EpfcpCnSpKlYyLtjZlu1fO5q9M'
    'fIi3ogAAAAAAAADAHqm5Fd5kDTd8qjvFjjNnop0mr9RbVSGT5HRTfrYu5/93JjbisygAAAAAAAAAsMe3AS73nVmUPXiOW29N9dzjRQ2l+QLx'
    '5F1m')


def people_db():
    return zlib.decompress(base64.b64decode(PEOPLE_DB))


def fixtures():
    files = {
        'sample.csv': SAMPLE, 'sample.tsv': plain(SAMPLE_ROWS), 'pets.csv': csv_text(PETS_ROWS),
        'semi.csv': csv_text(SAMPLE_ROWS, ';'), 'pipe.tsv': plain(SAMPLE_ROWS, '|'), 'pipe.psv': plain(SAMPLE_ROWS, '|'),
        'tricky.csv': csv_text(TRICKY_ROWS),
        'tricky2.csv': csv_text([['id', 'text'], ['1', 'two' + NL + 'lines'], ['2', 'tab' + TAB + 'here']]),
        'tabs2.tsv': plain([['id', 'text'], ['1', 'a,b'], ['2', 'say ' + Q + 'hi' + Q], ['3', 'plain']]),
        'data.json': DATA_JSON, 'lines.jsonl': LINES_JSONL, 'people.sqlite': people_db(),
        'fixed.txt': NL.join(['id  name   city', '1   alice  Paris', '2   bob    Berlin']) + NL,
        'plain.txt': 'line one' + NL + 'line two' + NL,
        'latin1.csv': ('id,name' + NL + '1,caf' + chr(0xe9) + NL).encode('latin-1'),
    }
    files.update(SHAPES)
    return {name: f(data) for name, data in files.items()}


# (extension, projection of the written file)
SAVERS = [('tsv', 'text'), ('csv', 'csv'), ('json', 'json'), ('jsonl', 'jsonl'), ('jsonla', 'jsonl'),
          ('ndjson', 'jsonl'), ('sqlite', 'sqlite'), ('md', 'text'), ('html', 'text'), ('fixed', 'text'),
          ('psv', 'text'), ('lsv', 'text'), ('usv', 'text')]


def savers():
    cps = []
    for ext, mode in SAVERS:
        out = 'out.' + ext
        cps.append(step('to-' + ext, 'Convert tricky.csv to ' + ext + ' with a batch run.', [batch(['tricky.csv'], out)],
                        [('file', 'The ' + ext + ' file holds the converted table.', file_(out, mode))]))
    return cps


# (name, arguments before the output, output extension, projection, requirement)
DETAILS = [
    ('json-indent', ['--json-indent', '2', 'sample.csv'], 'json', 'text', 'JSON output is indented by two spaces.'),
    ('json-sort-keys', ['--json-sort-keys', 'sample.csv'], 'json', 'text', 'JSON object keys are written in sorted order.'),
    ('json-ascii-default', ['tricky.csv'], 'json', 'text', 'Non-ASCII characters are written as unicode escapes by default.'),
    ('json-ascii-false', ['--json-ensure-ascii=False', 'tricky.csv'], 'json', 'text', 'Non-ASCII characters are written as they are when ensure-ascii is false.'),
    ('csv-delimiter-out', ['--csv-delimiter', ';', 'sample.tsv'], 'csv', 'text', 'The csv delimiter option separates the saved columns.'),
    ('csv-quote-all', ['--csv-quoting', '1', 'tabs2.tsv'], 'csv', 'text', 'Quoting mode 1 quotes every saved cell.'),
    ('csv-quote-default', ['tabs2.tsv'], 'csv', 'text', 'Only cells that need it are quoted by default.'),
    ('csv-lf-terminator', ['--csv-lineterminator', NL, 'tabs2.tsv'], 'csv', 'bytes', 'The csv line terminator option sets the row ending.'),
    ('csv-default-terminator', ['tabs2.tsv'], 'csv', 'bytes', 'The default csv row ending is written byte for byte.'),
    ('save-filetype', ['--save-filetype', 'json', 'sample.csv'], '', 'text', 'The save filetype option picks the format of an output without extension.'),
    ('output-filetype', ['-of', 'json', 'sample.csv'], 'dat', 'text', 'The output filetype option overrides the file extension.'),
    ('save-encoding-utf16', ['--save-encoding', 'utf-16', 'sample.csv'], 'tsv', 'bytes', 'The save encoding option sets the encoding of the written file.'),
    ('safety-first', ['--safety-first', 'tricky2.csv'], 'tsv', 'text', 'Safety mode replaces newlines and tabs inside cells.'),
    ('no-safety', ['tricky2.csv'], 'tsv', 'text', 'Without safety mode newlines and tabs inside cells are written raw.'),
    ('safety-chars', ['--safety-first', '--tsv-safe-newline', '~', '--tsv-safe-tab', '^', 'tricky2.csv'], 'tsv', 'text', 'The safe newline and safe tab options choose the replacement characters.'),
    ('html-title', ['--html-title', 'T', 'sample.csv'], 'html', 'text', 'The html title option sets the text written before the table.'),
    ('skip-initial-space-off', ['--csv-skipinitialspace=False', 'spaces.csv'], 'tsv', 'text', 'Spaces after a csv delimiter are kept when skipinitialspace is false.'),
]


def details():
    cps = []
    for name, args, ext, mode, requirement in DETAILS:
        out = name + ('.' + ext if ext else '')
        cps.append(step('opt-' + name, 'Convert with the option set ' + name + '.', [batch(args, out)],
                        [('file', requirement, file_(out, mode))]))
    return cps


LOADERS = [
    ('tsv', ['sample.tsv']), ('json-nested', ['data.json']), ('jsonl-union', ['lines.jsonl']),
    ('sqlite-index', ['people.sqlite']), ('sqlite-table', ['people.sqlite', '+people:pets::']),
    ('sqlite-view', ['people.sqlite', '+people:v::']), ('fixed-width', ['-f', 'fixed', 'fixed.txt']),
    ('plain-text', ['plain.txt']), ('psv', ['pipe.psv']), ('forced-tsv', ['-f', 'tsv', 'sample.csv']),
    ('csv-delimiter', ['--csv-delimiter', ';', 'semi.csv']), ('delimiter-short', ['-d', '|', 'pipe.tsv']),
    ('header-zero', ['--header', '0', 'sample.csv']), ('header-two', ['--header', '2', 'sample.csv']),
    ('skip-one', ['--skip', '1', 'sample.csv']), ('skip-and-header', ['--skip', '1', '--header', '2', 'sample.csv']),
    ('missing-input', ['no-such-file.csv']), ('two-inputs', ['pets.csv', 'sample.csv']),
    ('latin1-encoding', ['--encoding', 'latin-1', 'latin1.csv']), ('default-encoding', ['latin1.csv']),
] + [(name.replace('.', '-'), [name]) for name in SHAPES]


def loaders():
    cps = []
    for name, args in LOADERS:
        out = 'ld-' + name + '.tsv'
        checks = [('file', 'The ' + name + ' input is read the way the reference reads it and saved as tab separated text.', file_(out, 'text'))]
        if name == 'missing-input':
            checks.append(('message', 'The run reports that the input does not exist.', outcome(only=['output'], match='does not exist')))
        cps.append(step('ld-' + name, 'Read the input ' + name + ' and save it as a tsv file.', [batch(args, out)], checks))
    return cps


def episodes():
    files = fixtures()
    return [program('conv-savers', 'conversion', files, savers()),
            program('conv-options', 'conversion', files, details()),
            program('conv-loaders', 'conversion', files, loaders())]
