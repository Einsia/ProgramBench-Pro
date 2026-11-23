"""Program episodes: reading every storage format and the command-line export, checked without an evaluator.

The verifier writes the input documents itself (fixtures.py) in each storage
format, uploads them into the inbox and runs the product's own command-line
export through the runtime's export operation. Every export is one
checkpoint; its aspects are backend points:

- read-<document>: the document in the XML, SQLite and multiple-files formats
  (and protected 7-Zip variants for some), each exported to plain text with
  one file per node (written file names; one point per node file), and to
  HTML with one page per node (written files, node index, one point per node
  page).
- export-<document>: the XML document exported to a single text file, a
  single HTML file (one point per node section, plus the section order) and
  PDF (words, link targets).
- export-options and export-errors: repeated exports into the same folder,
  overwriting, file names with spaces, protected documents with the right,
  a wrong or no password, damaged and empty documents.
"""
import fixtures

from evaluation.contract import files_path
# Pages whose content is not product behaviour in the reference environment: LaTeX equations render to an image
# only with a TeX installation (absent), so their HTML image is an icon of the desktop theme.
SKIP_HTML = {('media', 148)}
# PDF word lists are compared for documents whose words do not depend on line wrapping or bidirectional layout.
PDF_DOCUMENTS = ('formatting', 'lists', 'codeboxes', 'tables', 'links', 'node-types', 'kitchen')
HTML_ALL_FORMATS = ('formatting', 'codeboxes', 'tables', 'media', 'node-types')
PROTECTED = ('kitchen', 'node-types', 'media')


def inbox(key):
    return files_path('inbox', instance=False)


def nodes_of(document):
    """(id, display name, depth) of every node in tree order (a shared node shows its master's name)."""
    by_id = {n.id: n for n, _, _, _ in fixtures.walk(document.nodes)}
    return [(n.id, by_id[n.master].name if n.master else n.name, level) for n, _, level, _ in fixtures.walk(document.nodes)]


def check(kind, aspect, description, **fields):
    return {'kind': kind, 'aspect': aspect, 'description': description, **fields}


def export_checks(key, name, document, fmt, export, single=False, password=None, folder=None, skip=()):
    """Assertions of one command-line export of an input document."""
    stem = name + fixtures.EXTENSION[fmt]
    base = {'document': f'{inbox(key)}/{stem}', 'format': export, 'folder': folder or f'{fmt}-{export}{"-single" if single else ""}'}
    if single:
        base['single_file'] = True
    if password is not None:
        base['password'] = password
    label = {'ctd': 'XML', 'ctb': 'SQLite', 'folder': 'multiple-files', 'ctz': 'protected XML', 'ctx': 'protected SQLite'}[fmt]
    lead = f'The {label} document {stem} exported'
    items = []
    if export == 'txt' and not single:
        items.append(check('export', 'files', f'{lead} to plain text with one file per node writes exactly the expected '
                                              'file names (node hierarchy, names cleaned for file names, node ids).', **base))
        for node_id, node_name, depth in nodes_of(document):
            items.append(check('export', f'node-text:{node_id}', f'{lead} to plain text: the file of node "{node_name}" '
                               '(id ' + str(node_id) + ') holds its header and its text, tables, code boxes and equations '
                               'as plain text.', **base))
    elif export == 'html' and not single:
        items.append(check('export', 'files', f'{lead} to HTML with one page per node writes the expected node '
                                              'documents and index; incidental implementation assets are ignored.', **base))
        items.append(check('export', 'index', f'{lead} to HTML: the index lists every node in tree order and nesting, '
                                              'each linked to its page.', **base))
        for node_id, node_name, depth in nodes_of(document):
            if (name, node_id) in skip:
                continue
            items.append(check('export', f'node-page:{node_id}', f'{lead} to HTML: the page of node "{node_name}" shows '
                               'its title and its text with the expected formatting, paragraphs, lists, tables, code, '
                               'images, embedded files, anchors and links.', **base))
    elif export == 'html':
        items.append(check('export', 'section-order', f'{lead} to a single HTML file holds one section per node in '
                                                      'tree order.', **base))
        for node_id, node_name, depth in nodes_of(document):
            if (name, node_id) in skip:
                continue
            items.append(check('export', f'section:{node_id}', f'{lead} to a single HTML file: the section of node '
                               f'"{node_name}" has its title, its tree level and its formatted content.', **base))
    elif export == 'txt':
        items.append(check('export', 'single-text', f'{lead} to a single plain text file holds every node in tree order '
                                                    'with its level header and plain-text content.', **base))
    else:
        items.append(check('export', 'pdf-words', f'{lead} to PDF contains the words of every node title and of its '
                                                  'content.', **base))
        if any(isinstance(item, tuple) and item[1].get('link', '').startswith(('webs', 'file', 'fold'))
               for node, _, _, _ in fixtures.walk(document.nodes) for item in node.content) or name == 'media':
            items.append(check('export', 'pdf-links', f'{lead} to PDF carries the web, file and folder link targets of '
                                                      'the document as PDF links.', **base))
    return items


def checkpoint(cid, goal, checks, depends=('setup:inputs',), requires=None):
    return {'id': cid, 'goal': goal, 'checks': checks, 'depends_on': list(depends), 'requires': requires or {}}


def episode(key, feature, steps, files, setup=()):
    """files: input entries (fixtures.input_files) uploaded before the first checkpoint; setup: more upload items
    with a 'before' checkpoint."""
    setup = [{'id': 'inputs', 'op': 'upload', 'area': 'inbox', 'files': list(files)}, *setup]
    checkpoints = []
    for step in steps:
        assertions = []
        for c in step['checks']:
            assertions.append({'id': f'{key}/{step["id"]}/{c["aspect"]}', 'channel': 'backend', 'method': 'program',
                               'requirement': c['description'], 'check': c})
        for aspect, companions in step['requires'].items():
            point = next(a for a in assertions if a['id'] == f'{key}/{step["id"]}/{aspect}')
            point['requires'] = [f'{key}/{p}' for p in companions]
        checkpoints.append({'id': step['id'], 'goal': step['goal'], 'depends_on': step['depends_on'],
                            'assertions': assertions})
    return {'id': key, 'feature': feature, 'execution': 'program',
            'initial_state': 'Fresh application process, desktop session and empty DATA_DIR; the input documents are '
                             'uploaded into the inbox before the first checkpoint.',
            'setup': setup, 'inputs': {}, 'checkpoints': checkpoints}


def read_episodes():
    episodes = []
    for name in fixtures.CORPUS:
        key = f'read-{name}'
        document = fixtures.document(name)
        formats = ['ctd', 'ctb', 'folder'] + (['ctz', 'ctx'] if name in PROTECTED else [])
        steps = []
        for fmt in formats:
            password = fixtures.PASSWORD if fmt in ('ctz', 'ctx') else None
            steps.append(checkpoint(f'{fmt}-txt', f'Export {name}{fixtures.EXTENSION[fmt]} to plain text, one file per node.',
                                    export_checks(key, name, document, fmt, 'txt', password=password)))
            if fmt == 'ctd' or (fmt in ('ctb', 'folder') and name in HTML_ALL_FORMATS):
                steps.append(checkpoint(f'{fmt}-html', f'Export {name}{fixtures.EXTENSION[fmt]} to HTML, one page per node.',
                                        export_checks(key, name, document, fmt, 'html', skip=SKIP_HTML)))
        episodes.append(episode(key, 'storage-formats', steps, [{'document': name, 'format': fmt} for fmt in formats]))
    return episodes


def export_episodes():
    episodes = []
    for name in fixtures.CORPUS:
        key = f'export-{name}'
        document = fixtures.document(name)
        steps = [checkpoint('txt-single', f'Export {name}.ctd to a single plain text file.',
                            export_checks(key, name, document, 'ctd', 'txt', single=True)),
                 checkpoint('html-single', f'Export {name}.ctd to a single HTML file.',
                            export_checks(key, name, document, 'ctd', 'html', single=True, skip=SKIP_HTML))]
        if name in PDF_DOCUMENTS:
            steps.append(checkpoint('pdf', f'Export {name}.ctd to PDF.', export_checks(key, name, document, 'ctd', 'pdf')))
        episodes.append(episode(key, 'command-line-export', steps, [{'document': name, 'format': 'ctd'}]))
    return episodes


def run_export(key, document, fmt, folder, **options):
    return {'document': f'{inbox(key)}/{document}', 'format': fmt, 'folder': folder, **options}


def options_episode():
    key = 'export-options'
    one = run_export(key, 'doc.ctd', 'txt', 'r')
    steps = [
        checkpoint('txt-first', 'Export doc.ctd to plain text (one file per node) into the folder r.', [
            check('export', 'files', 'The first plain-text export into r writes the folder doc.ctd_TXT with one file per '
                  'node.', **one),
            check('export', 'file-text:doc.ctd_TXT/One_1.txt', 'The node file holds the first version of the text.', **one)]),
        checkpoint('txt-second', 'Export doc.ctd to plain text into r again, without overwriting.', [
            check('export', 'files', 'Exporting again without overwriting keeps doc.ctd_TXT and writes a second folder '
                  'with the suffix 002.', **one)], depends=('txt-first',)),
        checkpoint('txt-third', 'Export doc.ctd to plain text into r a third time, without overwriting.', [
            check('export', 'files', 'A third export writes the suffix 003 and keeps the earlier folders.', **one)],
            depends=('txt-second',)),
    ]
    two = run_export(key, 'doc.ctd', 'txt', 'r', overwrite=True)
    steps.append(checkpoint('txt-overwrite', 'After doc.ctd changed (second version), export it to plain text into r '
                            'with overwriting.', [
        check('export', 'files', 'Overwriting reuses doc.ctd_TXT (now with a file for the added node) and writes no '
              'new numbered folder.', **two),
        check('export', 'file-text:doc.ctd_TXT/One_1.txt', 'The overwritten node file holds the second version.', **two),
        check('export', 'file-text:doc.ctd_TXT/Two_2.txt', 'The added node has its own file.', **two),
        check('export', 'file-text:doc.ctd_TXT002/One_1.txt', 'The numbered earlier export keeps the first version.', **two)],
        depends=('txt-third', 'setup:second-version')))
    single = run_export(key, 'single.ctd', 'txt', 's', single_file=True)
    pdf = run_export(key, 'single.ctd', 'pdf', 's')
    html = run_export(key, 'single.ctd', 'html', 's', single_file=True)
    steps += [
        checkpoint('single-txt', 'Export single.ctd to one plain text file in the folder s.', [
            check('export', 'file-text:single.ctd.txt', 'The single text file single.ctd.txt holds the first version.',
                  **single)]),
        checkpoint('single-pdf', 'Export single.ctd to PDF in the folder s.', [
            check('export', 'pdf-words', 'single.ctd.pdf contains the words of the first version.', **pdf)]),
        checkpoint('single-html', 'Export single.ctd to one HTML file in the folder s.', [
            check('export', 'section:1', 'The single HTML file has the section of node One with the first version.',
                  **html)]),
    ]
    later = [
        checkpoint('single-txt-again', 'After single.ctd changed, export it to one plain text file in s again '
                   '(without overwriting).', [
            check('export', 'file-text:single.ctd.txt', 'A single text export replaces single.ctd.txt with the second '
                  'version.', **single)], depends=('single-txt', 'setup:single-second')),
        checkpoint('pdf-keep', 'Export the changed single.ctd to PDF in s without overwriting.', [
            check('export', 'pdf-words', 'Without overwriting, the existing single.ctd.pdf is kept with the first '
                  'version.', **pdf)], depends=('single-pdf', 'setup:single-second'),
            requires={'pdf-words': ['single-pdf/pdf-words', 'pdf-overwrite/pdf-words']}),
        checkpoint('pdf-overwrite', 'Export the changed single.ctd to PDF in s with overwriting.', [
            check('export', 'pdf-words', 'With overwriting, single.ctd.pdf holds the second version.',
                  **dict(pdf, overwrite=True))], depends=('single-pdf', 'setup:single-second')),
        checkpoint('html-again', 'Export the changed single.ctd to one HTML file in s again.', [
            check('export', 'files', 'A second single-file HTML export without overwriting writes the numbered folder '
                  'single.ctd_HTML002 and keeps the first.', **html)], depends=('single-html', 'setup:single-second')),
    ]
    spaces_html = run_export(key, 'my notes.ctd', 'html', 'w')
    spaces_txt = run_export(key, 'my notes.ctd', 'txt', 'w-txt', single_file=True)
    spaces = [
        checkpoint('spaces-html', 'Export "my notes.ctd" (a name with a space) to HTML in the folder w.', [
            check('export', 'files', 'The HTML export folder of "my notes.ctd" is named with an underscore for the space.',
                  **spaces_html)]),
        checkpoint('spaces-txt', 'Export "my notes.ctd" to one plain text file in w-txt.', [
            check('export', 'files', 'The single text file keeps the document name with its space.', **spaces_txt)]),
    ]
    files = [{'document': 'version-one', 'format': 'ctd', 'as': 'doc'},
             {'document': 'version-one', 'format': 'ctd', 'as': 'single'},
             {'document': 'kitchen', 'format': 'ctd', 'as': 'my notes'}]
    setup = [{'id': 'second-version', 'op': 'upload', 'area': 'inbox', 'before': 'txt-overwrite',
              'files': [{'document': 'version-two', 'format': 'ctd', 'as': 'doc'}]},
             {'id': 'single-second', 'op': 'upload', 'area': 'inbox', 'before': 'single-txt-again',
              'files': [{'document': 'version-two', 'format': 'ctd', 'as': 'single'}]}]
    return episode(key, 'command-line-export', steps + later + spaces, files, setup)


def errors_episode():
    key = 'export-errors'
    good = run_export(key, 'locked.ctz', 'txt', 'good', single_file=True, password=fixtures.PASSWORD, seconds=30)
    steps = [
        checkpoint('password-right', 'Export the protected locked.ctz with its password to one text file.', [
            check('export', 'single-text', 'With the right password the protected document is exported.', **good)]),
        checkpoint('password-wrong', 'Export locked.ctz with a wrong password.', [
            check('export', 'files', 'With a wrong password nothing is exported.',
                  **dict(good, folder='wrong', password='not-the-password', seconds=15))],
            requires={'files': ['password-right/single-text']}),
        checkpoint('password-missing', 'Export locked.ctz without a password.', [
            check('export', 'files', 'Without a password nothing is exported.',
                  **{k: v for k, v in dict(good, folder='missing', seconds=15).items() if k != 'password'})],
            requires={'files': ['password-right/single-text']}),
        checkpoint('valid', 'Export the valid valid.ctd to one text file.', [
            check('export', 'single-text', 'A valid XML document is exported.',
                  **run_export(key, 'valid.ctd', 'txt', 'valid', single_file=True))]),
    ]
    for cid, name, what in (('truncated', 'truncated.ctd', 'a truncated XML document'),
                            ('not-xml', 'sentence.ctd', 'a text file that is not XML'),
                            ('empty-file', 'zero.ctd', 'an empty file'),
                            ('bad-sqlite', 'broken.ctb', 'a damaged SQLite document'),
                            ('wrong-extension', 'xml-inside.ctb', 'an XML document named as SQLite')):
        steps.append(checkpoint(cid, f'Export {name} ({what}) to one text file.', [
            check('export', 'files', f'Exporting {what} writes no text file.',
                  **run_export(key, name, 'txt', cid, single_file=True, seconds=15))],
            requires={'files': ['valid/single-text']}))
    empty = run_export(key, 'empty-tree.ctd', 'txt', 'empty', single_file=True)
    steps.append(checkpoint('empty-tree', 'Export empty-tree.ctd (a document without nodes) to one text file.', [
        check('export', 'files', 'A document without nodes is exported as one empty text file named after it.', **empty)]))
    files = [{'document': 'kitchen', 'format': 'ctz', 'as': 'locked'}, {'document': 'kitchen', 'format': 'ctd', 'as': 'valid'},
             {'raw': 'truncated-xml', 'as': 'truncated.ctd'}, {'raw': 'not-xml', 'as': 'sentence.ctd'},
             {'raw': 'empty-file', 'as': 'zero.ctd'}, {'raw': 'bad-sqlite', 'as': 'broken.ctb'},
             {'copy': 'kitchen', 'as': 'xml-inside.ctb'}, {'document': 'empty-tree', 'format': 'ctd'}]
    return episode(key, 'export-errors', steps, files)


def build():
    return read_episodes() + export_episodes() + [options_episode(), errors_episode()]
