'''More formats and commands: compressed and archived inputs, further loaders, the vds round trip, duplicated
sheets, contracting nested columns, metasheets, dives from frequency tables, bulk commands of the columns sheet,
row and column commands with counts, frozen copies, and cursor movement keys.

Batch points run vd -b IN -o OUT or vd -b -p LOG.vdj; key points restart the application, open a file with the
o key and read the cursor position. Every point has its own input, column, row or count, so a missing or wrong
rule differs from the reference on that point alone. The expected values come from the frozen reference; the
requirement text describes the behaviour and must also hold for an equivalent reimplementation.
'''
import base64
import bz2
import gzip
import io
import json
import lzma
import tarfile
import zipfile

from spec_core import *
from spec_convert import TRICKY_ROWS
from spec_logs import ASC, DESC, case, checkpoint
from spec_matrix import MIX_ROWS
from spec_tui import POSITION, K, P, go

TSV = plain([['id', 'name'], ['1', 'ann'], ['2', 'bo']])
DEEP = json.dumps([{'id': 1, 'a': {'b': {'c': 1, 'd': 2}, 'e': 3}}, {'id': 2, 'a': {'b': {'c': 4}, 'e': 5}}])
TOML = NL.join(['title = "demo"', 'count = 3', '', '[owner]', 'name = "ann"', 'since = 2021-05-01', '',
                '[[items]]', 'id = 1', 'name = "pen"', 'tags = ["a", "b"]', '', '[[items]]', 'id = 2', 'name = "ink"']) + NL
EML = NL.join(['From: Ann <ann@example.com>', 'To: Bo <bo@example.com>', 'Subject: Hello',
               'Date: Tue, 02 Jan 2024 10:00:00 +0000', 'MIME-Version: 1.0', 'Content-Type: multipart/mixed; boundary="XX"', '',
               '--XX', 'Content-Type: text/plain', '', 'first part', '--XX', 'Content-Type: text/csv; name="t.csv"',
               'Content-Disposition: attachment; filename="t.csv"', '', 'a,b', '1,2', '--XX--', ''])
ORG = NL.join(['#+TITLE: Notes', '* Top one', 'text under one', '** Child a', 'child text', '* Top two :tag:', 'more']) + NL
GEO = json.dumps({'type': 'FeatureCollection', 'features': [
    {'type': 'Feature', 'properties': {'name': 'p', 'n': 1}, 'geometry': {'type': 'Point', 'coordinates': [1.5, 2.5]}},
    {'type': 'Feature', 'properties': {'name': 'q', 'n': 2}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]}}]})
JRNL = NL.join(['[2024-01-02 10:00] First entry.', 'Body of the first.', '', '[2024-01-03 11:30] Second @tag entry.', 'Body two.', '']) + NL
UNITS = csv_text([['n', 'si', 'cur', 'loc', 'd'], ['3', '1.5k', '$3.50', '1,234.5', '2024-01-05'], ['12', '2M', '4', '2.5', '2023-12-31'],
                  ['', '3', chr(0x20ac) + '5', '7', ''], ['7.5', '500m', '-$2', '1,000', '2024-02-29']])
ERRS = csv_text([['id', 'n'], ['1', '5'], ['2', 'x'], ['3', '7']])
PETS = csv_text(PETS_ROWS)
DM = csv_text([['k', 'd'], ['a', '05/01/2024'], ['b', '12/02/2023'], ['c', '31/12/2023'], ['d', '02/03/2024'], ['e', 'x']])
RUNS_ROWS = [['k', 'v', 'n'], ['a', 'x1', '1'], ['a', 'x2', '5'], ['a', 'y3', ''], ['b', 'y4', '3'], ['b', 'z5', '9'],
             ['c', 'z6', ''], ['', 'w7', '4'], ['d', 'w8', '2']]


def zipped(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, text in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=(2024, 1, 2, 3, 4, 5)), text)
    return buffer.getvalue()


def tarred(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, text in members.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(data), T, 0o640
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


US, RS = chr(0x241f), chr(0x241e)
USV = RS.join(US.join(row) for row in [['id', 'name', 'note'], ['1', 'ann', 'a,b'], ['2', 'bo', 'tab' + chr(9) + 'here']]) + RS
JSONLA = NL.join(json.dumps(row) for row in [['id', 'name', 'n'], [1, 'ann', 2.5], [2, 'bo', None], [3, 'cy', [1, 2]]]) + NL
MBOX = NL.join(['From ann@example.com Tue Jan  2 10:00:00 2024', 'From: Ann <ann@example.com>', 'To: Bo <bo@example.com>', 'Subject: one',
                'Date: Tue, 02 Jan 2024 10:00:00 +0000', '', 'body one', '',
                'From bo@example.com Wed Jan  3 11:00:00 2024', 'From: Bo <bo@example.com>', 'Cc: Cy <cy@example.com>', 'Subject: two', '',
                'body two', 'second line', '']) + NL
GREP = NL.join(json.dumps({'type': 'match', 'data': {'path': {'text': path}, 'lines': {'text': text + NL}, 'line_number': n, 'absolute_offset': 0,
                                                     'submatches': [{'match': {'text': 'ab'}, 'start': 0, 'end': 2}]}})
               for path, n, text in (('a.txt', 3, 'ab one'), ('b/c.txt', 12, 'abc two'))) + NL
ARCHIVE = zipped({'a.csv': 'x,y' + NL + '1,2' + NL + '3,4' + NL, 'sub/b.tsv': TSV})
TRICKY = csv_text(TRICKY_ROWS).encode('utf-8')
# gzip.compress(data, mtime=0) of TRICKY, TSV and DEEP as CPython 3.12 wrote it for the frozen manifest: zlib's header
# with OS byte 3, where Python 3.10 and 3.13+ write 255. Frozen bytes, so the manifest does not depend on the Python
# or zlib version.
T_CSV_GZ = base64.b64decode(
    'H4sIAAAAAAACAxXKuw3CMBAG4Jqbwrr6b3iDmOZiH8pJ8QPsiESiYwlWYA42YRKU7is+C2g6NaTclNYog1jCRBuwoGP4HKPQFlxldsy9MTNu45J3'
    '4PbINFjSykj6WER7eLl+P+73fmFM5nNQOsC5IiFocA61iNdKR0BjaTOd0KRb9XrXBXRG1WiXYkWfCDpYrPQHPnf+aqQAAAA=')
S_TSV_GZ = base64.b64decode('H4sIAAAAAAACA8tM4cxLzE3lMuRMzMvjMuJMyucCAI5nSMwTAAAA')
D_JSON_GZ = base64.b64decode('H4sIAAAAAAACA4uuVspMUbJSMNRRUEoE0tVKSWAyGSoGkjOqBTJSgQzjWiALqsEIiwYTmELT2tpYAMGU3glaAAAA')
assert [gzip.decompress(x) for x in (T_CSV_GZ, S_TSV_GZ, D_JSON_GZ)] == [TRICKY, TSV.encode(), DEEP.encode()], \
    'stale gzip fixtures'
FILES = {'mix.csv': csv_text(MIX_ROWS), 'deep.json': DEEP, 'units.csv': UNITS, 'errs.csv': ERRS, 'pets.csv': PETS, 'dm.csv': DM,
         't.csv.gz': T_CSV_GZ, 't.csv.bz2': bz2.compress(TRICKY), 't.csv.xz': lzma.compress(TRICKY),
         's.tsv.gz': S_TSV_GZ, 'd.json.gz': D_JSON_GZ,
         'arch.zip': ARCHIVE, 'pack.tar': tarred({'a.csv': 'x,y' + NL + '1,2' + NL, 'docs/b.txt': 'hello' + NL}),
         'u.usv': USV, 'l.jsonla': JSONLA, 'm.mbox': MBOX, 'g.grep': GREP, 'c.toml': TOML, 'm.eml': EML, 'n.org': ORG, 'g.geojson': GEO, 'j.jrnl': JRNL}


def M(longname, col='', row='', inp='', sheet='mix'):
    return entry(longname, col, row, inp, sheet=sheet)


def U(longname, col='', row='', inp='', sheet='units'):
    return entry(longname, col, row, inp, sheet=sheet)


def D(longname, col='', inp=''):
    return entry(longname, col, '', inp, sheet='deep')


def read(name, args, requirement):
    out = 'rd-' + name + '.tsv'
    return step('rd-' + name, 'Read the input ' + name + ' and save it as a tsv file.', [batch(args, out)],
                [('file', requirement, file_(out, 'text'))])


def family(key_, feature, items):
    '''items are checkpoints or replay cases; the cases bring their command logs as fixtures.'''
    files = {name: f(data) for name, data in FILES.items()}
    checkpoints = []
    for item in items:
        if 'log' in item:
            files['c-' + item['name'] + '.vdj'] = f(item['log'])
            checkpoints.append(checkpoint(item))
        else:
            files.update(item.pop('_logs', {}))
            checkpoints.append(item)
    return program(key_, feature, files, checkpoints)


def formats():
    cps = [read(name, [path], text) for name, path, text in (
        ('gz-csv', 't.csv.gz', 'A gzip-compressed csv file is decompressed and read as csv.'),
        ('bz2-csv', 't.csv.bz2', 'A bzip2-compressed csv file is decompressed and read as csv.'),
        ('xz-csv', 't.csv.xz', 'An xz-compressed csv file is decompressed and read as csv.'),
        ('gz-tsv', 's.tsv.gz', 'The format of a compressed file comes from the extension before the compression suffix.'),
        ('gz-json', 'd.json.gz', 'A compressed json file is read as json.'),
        ('zip-list', 'arch.zip', 'A zip archive opens as a list of its members with their directory, name, extension and sizes.'),
        ('toml', 'c.toml', 'A toml file opens as one row of its top-level keys, with tables and arrays as nested values.'),
        ('eml', 'm.eml', 'An email file opens as a list of its MIME parts with file name, content type and payload.'),
        ('org', 'n.org', 'An org file opens as a list of its top-level entries with their tags and child counts.'),
        ('geojson', 'g.geojson', 'A geojson file opens as one row per feature with the feature properties as columns.'),
        ('jrnl', 'j.jrnl', 'A jrnl file opens as one row per entry with date, time, title, body and tags.'),
        ('tar', 'pack.tar', 'A tar archive opens as a list of its members with name, extension, size, time, type and mode.'),
        ('usv', 'u.usv', 'A usv file splits fields at the unit separator and rows at the record separator, keeping commas and tabs.'),
        ('jsonla', 'l.jsonla', 'A jsonla file takes the column names from its first array and one row from each further array.'),
        ('mbox', 'm.mbox', 'An mbox file opens as one row per message with its headers and payload.'),
        ('grep', 'g.grep', 'A grep file (ripgrep json output) opens as one row per match with file, line number and text.'))]
    cps.append(step('wr-jira', 'Save mix.csv as a jira table.', [batch(['mix.csv'], 'wr-mix.jira')],
                    [('file', 'The jira saver writes a header row between double bars and padded cells between single bars.',
                      file_('wr-mix.jira', 'text'))]))
    cps += [case('zip-member-%d' % row, [entry('open-row', row=str(row), sheet='arch')],
                 'Opening a row of a zip listing reads that member in the format of its extension.', opens='arch.zip')
            for row in (0, 1)]
    vds = case('vds-roundtrip', [M('type-int', 'qty'), M('type-float', 'price'), M('key-col-on', 'city'), M('save-sheet', inp='keep.vds'),
                                 open_entry('keep.vds'), entry('open-row', row='0', sheet='keep')],
               'A sheet saved as vds and opened again keeps its column types and key columns.', opens='mix.csv')
    cps.append(vds)
    cps.append(step('vds-index', 'Read the saved vds file and save its sheet list as a tsv file.', [batch(['keep.vds'], 'vds-index.tsv')],
                    [('file', 'A vds file opens as the list of the sheets it holds with their sizes and keys.', file_('vds-index.tsv', 'text'))],
                    depends=['cmd-vds-roundtrip']))
    return cps


def sheets():
    first = [M('sort-desc', 'city', inp=DESC + 'city'), M('select-row', row='1'), M('select-row', row='2')]
    names = {'dup-rows': 'mix_copy', 'dup-rows-deep': 'mix_deepcopy', 'dup-selected': 'mix_selectedref',
             'dup-selected-deep': 'mix_selecteddeepcopy'}
    cases = []
    for cmd, copy in names.items():
        shared = 'shares' if 'deep' not in cmd else 'does not share'
        own = [M('edit-cell', 'city', str(3 + len(cases) // 2), 'S%d' % len(cases))] if 'deep' in cmd else []
        cases.append(case(cmd + '-source', first + [M(cmd), M('edit-cell', 'name', '0', 'ZZ', sheet=copy), M('quit-sheet', sheet=copy)] + own,
                          '%s opens a copy that %s its rows with the source, so an edit in the copy %s the source.'
                          % (cmd, shared, 'changes' if 'deep' not in cmd else 'leaves'), opens='mix.csv'))
        if cmd == 'dup-selected-deep':
            cases.append(case(cmd + '-copy', first + [M(cmd), M('edit-cell', 'name', '0', 'ZZ', sheet=copy)],
                              '%s copies only the selected rows and the copy takes the edit.' % cmd,
                              opens='mix.csv'))
    errs = [entry('addcol-expr', 'n', inp='int(n)', sheet='errs')]
    cases += [
        case('describe-all', [open_entry('errs.csv'), entry('describe-all', sheet='errs')],
             'describe-all describes the columns of every open sheet.', opens='mix.csv'),
        case('columns-all', [open_entry('errs.csv'), entry('columns-all', sheet='errs')],
             'columns-all lists the columns of every open sheet with the sheet name.', opens='mix.csv'),
        case('columns-selected', [open_entry('errs.csv'), entry('sheets-stack', sheet='errs'), entry('select-row', row='1', sheet='sheets'),
                                  entry('columns-selected', sheet='sheets')],
             'columns-selected lists only the columns of the sheets selected on the sheets sheet.', opens='mix.csv'),
        case('cmdlog-sheet', [M('sort-desc', 'qty', inp=DESC + 'qty'), M('freq-col', 'city'), entry('cmdlog-sheet', sheet='mix_city_freq')],
             'The command log of a sheet includes the commands of the sheets it came from.', opens='mix.csv'),
        case('cmdlog-sheet-only', [M('sort-desc', 'qty', inp=DESC + 'qty'), M('freq-col', 'city'), entry('cmdlog-sheet-only', sheet='mix_city_freq')],
             'The sheet-only command log lists only the commands run on that sheet.', opens='mix.csv'),
        case('describe-errors', errs + [entry('describe-sheet', sheet='errs')],
             'The describe sheet counts the cells whose computation failed.', opens='errs.csv'),
        case('describe-select-cell', errs + [entry('describe-sheet', sheet='errs'), entry('select-cell', 'errors', '2', sheet='errs_describe'),
                                             entry('quit-sheet', sheet='errs_describe'), entry('dup-selected', sheet='errs')],
             'select-cell on the describe sheet selects the source rows counted in that cell.', opens='errs.csv'),
        case('describe-unselect-cell', errs + [entry('select-rows', sheet='errs'), entry('describe-sheet', sheet='errs'),
                                               entry('unselect-cell', 'errors', '2', sheet='errs_describe'), entry('quit-sheet', sheet='errs_describe'),
                                               entry('dup-selected', sheet='errs')],
             'unselect-cell on the describe sheet unselects the source rows counted in that cell.', opens='errs.csv'),
        case('select-error-col', errs + [entry('select-row', row='0', sheet='errs'), entry('select-error-col', 'int(n)', sheet='errs'),
                                         entry('dup-selected', sheet='errs')],
             'select-error-col adds the rows whose cell in the column failed to the selection.', opens='errs.csv'),
        case('error-cell-none', errs + [entry('error-cell', 'int(n)', '0', sheet='errs')],
             'Asking for the error of a cell that has none stops the replay.', opens='errs.csv', fails=True),
        case('dive-selected', [M('freq-col', 'city'), M('select-row', row='0', sheet='mix_city_freq'), M('select-row', row='2', sheet='mix_city_freq'),
                               M('dive-selected', sheet='mix_city_freq')],
             'Diving into the selected bins opens the source rows of those bins.', opens='mix.csv'),
        case('dive-except', [M('freq-col', 'city'), M('dive-except', row='0', sheet='mix_city_freq')],
             'dive-except opens the source rows outside the cursor bin.', opens='mix.csv'),
        case('dive-except-selected', [M('freq-col', 'city'), M('select-row', row='0', sheet='mix_city_freq'), M('select-row', row='1', sheet='mix_city_freq'),
                                      M('dive-except-selected', sheet='mix_city_freq')],
             'dive-except-selected opens the source rows outside the selected bins.', opens='mix.csv'),
        case('undo-last-quit', [M('freq-col', 'city'), M('quit-sheet', sheet='mix_city_freq'), M('undo-last-quit')],
             'undo-last-quit reopens the most recently closed sheet.', opens='mix.csv'),
        case('jump-prev', [M('sort-desc', 'qty', inp=DESC + 'qty'), M('delete-row', row='3'), M('freq-col', 'city'), M('jump-prev', sheet='mix_city_freq')],
             'jump-prev returns to the previous sheet without closing the current one.', opens='mix.csv'),
        case('join-sheets-all', [open_entry('errs.csv'), entry('join-sheets-all', inp='append', sheet='errs')],
             'Joining all sheets with append stacks the rows of every open sheet under the union of their columns.', opens='mix.csv'),
        case('open-cell', [entry('open-cell', 'a', '1', sheet='deep')],
             'open-cell opens the nested value of the cursor cell as its own sheet of keys and values.', opens='deep.json'),
        case('sheets-all', [open_entry('errs.csv'), entry('quit-sheet', sheet='errs'), M('sheets-all')],
             'sheets-all lists every sheet opened in the session, including the ones already closed.', opens='mix.csv'),
        case('cmdlog-all', [M('sort-desc', 'qty', inp=DESC + 'qty'), open_entry('errs.csv'), entry('sort-asc', 'n', inp=ASC + 'n', sheet='errs'),
                            entry('cmdlog-all', sheet='errs')],
             'cmdlog-all lists the commands of every sheet in the session.', opens='mix.csv'),
        case('describe-selected', [open_entry('errs.csv'), entry('sheets-stack', sheet='errs'), entry('select-row', row='1', sheet='sheets'),
                                   entry('describe-selected', sheet='sheets')],
             'describe-selected describes only the columns of the sheets selected on the sheets sheet.', opens='mix.csv'),
        case('save-selected', [M('edit-cell', 'city', '0', 'Q'), open_entry('errs.csv'), entry('sheets-stack', sheet='errs'),
                               entry('select-row', row='1', sheet='sheets'), entry('select-row', row='2', sheet='sheets'),
                               entry('save-selected', inp='both/', sheet='sheets')],
             'save-selected to a directory writes one file per selected sheet, named after the sheet.', opens='mix.csv',
             saved=[('both/errs.tsv', 'tsv'), ('both/mix.tsv', 'tsv')]),
    ]
    return cases


def bulk():
    '''Commands of the columns sheet that act on the selected source columns; every case selects other columns.'''
    def cs(name, cmd, rows, pre=(), post=(), mode='json', text=''):
        picks = [U('select-row', row=str(r), sheet='units_columns') for r in rows]
        steps = list(pre) + [U('columns-sheet')] + picks + [U(cmd, sheet='units_columns'), U('quit-sheet', sheet='units_columns')] + list(post)
        if mode == 'json':  # JSON keeps the typed values (numbers, error markers) that a tsv file shows as text
            target = 'cs-' + name + '.json'
            return case('cs-' + name, steps + [U('save-sheet', inp=target)], text, opens='units.csv', saved=[(target, 'json')])
        return case('cs-' + name, steps, text, opens='units.csv', mode=mode)
    columns = 'n si cur loc d'.split()
    def which(rows):
        return ' and '.join(columns[r] for r in rows)
    cases = []
    for cmd, rows in (('type-int-selected', [0, 3]), ('type-float-selected', [0, 1]), ('type-floatsi-selected', [1, 2]),
                      ('type-currency-selected', [2, 3]), ('type-len-selected', [3, 4]), ('type-date-selected', [4])):
        cases.append(cs(cmd, cmd, rows, text='%s on the columns sheet types only the selected columns (%s); a JSON save shows the typed values.'
                        % (cmd, which(rows))))
    cases += [
        cs('type-string-selected', 'type-string-selected', [0], pre=[U('type-int', 'n'), U('type-currency', 'cur')],
           text='type-string-selected turns only the selected typed column back into text.'),
        cs('type-any-selected', 'type-any-selected', [4], pre=[U('type-float', 'n'), U('type-len', 'd')],
           text='type-any-selected turns only the selected typed column back into raw values.'),
        cs('hide-selected', 'hide-selected', [1, 3], mode='tsv', text='hide-selected hides the selected source columns.'),
        cs('key-selected', 'key-selected', [2, 0], post=[U('sort-keys-asc')], mode='tsv',
           text='key-selected makes the selected columns key columns, in the order of the source.'),
        cs('key-off-selected', 'key-off-selected', [0], pre=[U('key-col-on', 'cur'), U('key-col-on', 'n')], post=[U('sort-keys-desc')], mode='tsv',
           text='key-off-selected removes only the selected columns from the keys.'),
        cs('aggregate-cols', 'aggregate-cols', [0, 3], pre=[U('type-float', 'n'), U('type-floatlocale', 'loc')], post=[U('freq-col', 'd')], mode='tsv',
           text='aggregate-cols adds the chosen aggregator to every selected column, shown in frequency tables.'),
    ]
    Q = lambda name, col='', inp='': entry(name, col, '', inp, sheet='dm')
    custom = [Q('type-customdate', 'd', inp='%d/%m/%Y')]
    cases += [
        case('customdate-sort', custom + [Q('sort-asc', 'd', inp=ASC + 'd')],
             'type-customdate parses the column with the given format, so it sorts by date; an unparsable cell sorts first.', opens='dm.csv'),
        case('customdate-json', custom + [Q('save-sheet', inp='cd.json')],
             'type-customdate keeps the cells in their own format and marks an unparsable cell as an error.', opens='dm.csv',
             saved=[('cd.json', 'json')]),
        case('customdate-selected', [Q('columns-sheet'), entry('select-row', row='1', sheet='dm_columns'),
                                     entry('type-customdate-selected', inp='%d/%m/%Y', sheet='dm_columns'), entry('quit-sheet', sheet='dm_columns'),
                                     Q('sort-desc', 'd', inp=DESC + 'd')],
             'type-customdate-selected on the columns sheet gives the selected columns the custom date format.', opens='dm.csv'),
    ]
    return cases


def contracting():
    expanded = [D('expand-col', 'a'), D('expand-col', 'a.b')]
    return [
        case('contract-cols', [D('expand-cols-depth', inp='0'), D('contract-cols')],
             'contract-cols removes the child columns of every expanded column and shows the parent again.', opens='deep.json'),
        case('contract-col', expanded + [D('contract-col', 'a.b.c')],
             'contract-col removes one level: the children of a.b go and a.b shows again.', opens='deep.json'),
        case('contract-col-sibling', expanded + [D('contract-col', 'a.e')],
             'contract-col on a first-level child shows the parent again and keeps the deeper children of its sibling.', opens='deep.json'),
    ]


def rows_and_columns():
    upper = M('addcol-expr', 'id', inp='name.upper()')
    return [
        case('add-rows-1', [M('add-rows', row='2', inp='1')], 'add-rows with a count of one adds one empty row below the cursor row.', opens='mix.csv'),
        case('add-rows-3', [M('add-rows', row='5', inp='3')], 'add-rows adds the given number of empty rows below the cursor row.', opens='mix.csv'),
        case('rename-cols-row', [M('rename-cols-row', row='0')], 'rename-cols-row names the columns after the cells of the cursor row.',
             opens='mix.csv', args=['--header', '0']),
        case('rename-cols-rows', [M('select-row', row='3'), M('select-row', row='1'), M('rename-cols-row')],
             'With selected rows, rename-cols-row joins their cells into the column names.', opens='mix.csv', args=['--header', '0']),
        case('setcol-freeze', [upper, M('setcol-freeze', 'name.upper()'), M('edit-cell', 'name', '0', 'zed')],
             'A column frozen in place keeps its values when the cells it was computed from change.', opens='mix.csv'),
        case('freeze-sheet', [upper, M('freeze-sheet'), entry('edit-cell', 'name', '1', 'zed', sheet="mix'")],
             'freeze-sheet opens a copy with every computed column evaluated, and the copy takes edits.', opens='mix.csv'),
        case('key-col-off', [M('key-col-on', 'city'), M('key-col-on', 'qty'), M('key-col-off', 'city'), M('sort-keys-asc')],
             'key-col-off removes one column from the keys and leaves the others.', opens='mix.csv'),
        case('slide-left-n', [M('slide-left-n', 'price', inp='3')], 'slide-left-n moves the column left by the count.', opens='mix.csv'),
        case('slide-right-n', [M('slide-right-n', 'name', inp='2')], 'slide-right-n moves the column right by the count.', opens='mix.csv'),
        case('slide-up-n', [M('slide-up-n', row='5', inp='3')], 'slide-up-n moves the row up by the count.', opens='mix.csv'),
        case('sort-asc-change', [M('sort-desc', 'city', inp=DESC + 'city'), M('sort-asc-add', 'id'), M('sort-asc-change', 'city')],
             'sort-asc-change turns the city key ascending and keeps the second key.', opens='mix.csv'),
        case('sort-asc-change-new', [M('sort-desc', 'city', inp=DESC + 'city'), M('sort-asc-change', 'name')],
             'sort-asc-change on a column that is not a key replaces the last key.', opens='mix.csv'),
        case('width-input', [M('resize-col-input', 'city', inp='15'), M('columns-sheet')],
             'resize-col-input sets the width of the cursor column, listed on the columns sheet.', opens='mix.csv'),
        case('widths-input', [M('resize-cols-input', inp='5'), M('columns-sheet')],
             'resize-cols-input sets the width of every visible column.', opens='mix.csv'),
    ]


def moves():
    at = lambda text: [('pos', text, POSITION)]
    return [
        go('next-value', 'On the third row of the city column, move to the next row with a different city using >.', K('Right', 'Right', 'Down', 'Down', '>'),
           at('> moves down the column to the next row whose value differs.')),
        go('prev-value', 'On the last row of the city column, move up to the previous row with a different city using <.', K('Right', 'Right', 'g', 'j', '<'),
           at('< moves up the column to the previous row whose value differs.')),
        go('next-selected', 'Select the third and sixth rows, go to the first row and move to the next selected row with }.',
           K('Down', 'Down', 's', 'Down', 'Down', 's', 'g', 'k', '}'), at('} moves to the next selected row.')),
        go('prev-selected', 'Select the third and sixth rows, go to the last row and move to the previous selected row with {.',
           K('Down', 'Down', 's', 'Down', 'Down', 's', 'g', 'j', '{'), at('{ moves to the previous selected row.')),
        go('col-regex', 'Move to the first column whose name matches am using c.', P('c', 'am'), at('c moves to the next column whose name matches the pattern.')),
        go('row-number', 'In the name column, move to row number 2 with z then r.', K('Right') + P(['z', 'r'], '2'),
           at('z then r moves to the given zero-based row number and keeps the column.')),
        go('col-number', 'Move to column number 4 with z then c.', P(['z', 'c'], '4'), at('z then c moves to the given zero-based column number.')),
        go('search-all-cols', 'Search every column for Oslo with g then /.', P(['g', '/'], 'Oslo'), at('g then / searches all visible columns and moves to the match.')),
        go('search-keys', 'Make city a key column, go back to the first column and search the keys for Oslo with r.',
           K('Right', 'Right', '!', 'g', 'h') + P('r', 'Oslo'), at('r searches the key columns and moves to the matching row.')),
        go('search-expr', 'Search the name column for the row where the expression name.startswith("f") is true, with z then /.',
           K('Right') + P(['z', '/'], 'name.startswith("f")'), at('z then / moves to the next row where the expression is true.')),
        go('search-expr-back', 'In the name column, go to the last row and search backward for the row where city == "Berlin" is true, with z then ?.',
           K('Right', 'g', 'j') + P(['z', '?'], 'city == "Berlin"'), at('z then ? moves up to the previous row where the expression is true.')),
        go('search-all-back', 'Search every column backward for Berlin with g then ?.', P(['g', '?'], 'Berlin'),
           at('g then ? searches all visible columns backward, wrapping to the last match.')),
    ]


def episodes():
    from spec_tui import FIXTURES as TUI_FILES
    groups = [('more-formats', 'conversion', formats()), ('more-sheets', 'sheets', sheets()), ('more-bulk', 'columns', bulk()),
              ('more-contract', 'columns', contracting()), ('more-rows-cols', 'rows', rows_and_columns())]
    return [family(*group) for group in groups] + [
        program('tui-moves', 'navigation', {name: f(data) for name, data in TUI_FILES.items()}, moves())]
