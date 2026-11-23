"""Reviewed user goals on the desktop interface: goals, acceptance conditions, setup and program checks.

Reference recipes (reference/recipes.py) implement these goals for the pinned
standard answer; goals are authored here and never translated from a click
trace. Setup writes each episode's starting library through the local API and
uploads its input files into the inbox; goals name items by their titles,
files by their absolute paths and values exactly. Program checks read the
resulting library through the API, the files written into the outbox and the
clipboard; they never feed back into the evaluator's judgement.
"""
import re

import library

from evaluation.contract import files_path
U = '/api/users/0'
K = library.key


def inbox(key):
    """The runtime's inbox of one episode (its exchange folders sit beside the product's instance directory)."""
    return files_path('inbox', instance=False)


def outbox(key):
    return files_path('outbox', instance=False)


HINTS = ('Commit single-line item fields by pressing Enter or moving focus. In multiline fields such as notes '
         'and annotation comments, Enter inserts a line break; move focus to finish editing. Library data, exported '
         'files and the clipboard are checked separately: judge what the interface shows, without re-opening files or repeating a '
         'command to compare. When a goal names a file, type exactly that full path in the file dialog (Control+L '
         'opens the location field of an Open dialog; the name field of a Save dialog accepts a full path). Prefer '
         'control refs over guessed coordinates; some row buttons appear only while the pointer is over the row. '
         'Close confirmation dialogs only as a goal asks.')


# ------------------------------------------------------------------------------------------------- checks
def find(value, view, field='title', path=f'{U}/items?includeTrashed=1', item_type=None):
    step = {'kind': 'find', 'field': field, 'value': value, 'path': path, 'view': view}
    if item_type:
        step['itemType'] = item_type
    return step


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:48]


def item(title, fields, description, field='title', item_type=None, aspect=None):
    """The item whose field equals title: the named fields of its data."""
    return {'description': description, 'aspect': aspect or 'item-' + slug(title),
            'check': {'steps': [find(title, f'fields:{fields}', field=field, item_type=item_type)]}}


def items(path, view, description, aspect):
    return {'description': description, 'aspect': aspect, 'check': {'steps': [{'method': 'GET', 'path': path,
                                                                               'view': [view]}]}}


def children(title, fields, description, aspect='children'):
    return {'description': description, 'aspect': aspect, 'check': {'steps': [
        find(title, [], 'title'), {'method': 'GET', 'path': U + '/items/{found}/children', 'view': [f'unordered:fields:{fields}']}]}}


def collection(name, fields, description):
    return {'description': description, 'aspect': 'collection-' + slug(name),
            'check': {'steps': [find(name, f'fields:{fields}', field='name', path=f'{U}/collections')]}}


def collection_items(name, description, aspect=None):
    return {'description': description, 'aspect': aspect or 'members-' + slug(name), 'check': {'steps': [
        find(name, [], field='name', path=f'{U}/collections'),
        {'method': 'GET', 'path': U + '/collections/{found}/items/top', 'view': ['unordered:fields:title']}]}}


def absent(title, description, field='title'):
    """No item (not even in the trash) has this title."""
    return {'description': description, 'aspect': 'absent-' + slug(title), 'check': {'steps': [
        {'method': 'GET', 'path': f'{U}/items?includeTrashed=1', 'view': [f'absent:{field}={title}']}]}}


def tags(description, path=f'{U}/tags', aspect='tags'):
    return {'description': description, 'aspect': aspect, 'check': {'steps': [{'method': 'GET', 'path': path,
                                                                               'view': ['tag-names']}]}}


# ------------------------------------------------------------------------------------------------ builders
def step(key, goal, acceptance, recipe, checks=(), *, depends=(), lifecycle=None, requires=None):
    """One checkpoint. requires binds a frontend assertion suffix to companion points of the same episode (an
    aspect of this checkpoint, or 'checkpoint/aspect')."""
    cp = {'id': key, 'goal': goal, 'acceptance': [acceptance] if isinstance(acceptance, str) else list(acceptance),
          'recipe': list(recipe), 'checks': list(checks), 'depends_on': list(depends)}
    if lifecycle:
        cp['lifecycle'] = lifecycle
    if requires:
        cp['requires'] = {suffix: list(points) for suffix, points in requires.items()}
    return cp


def episode(key, feature, steps, *, objects=None, libraries=(), files=(), session='', notes=''):
    setup = [{'id': 'api', 'op': 'api-ready'}]
    if libraries:
        setup.append({'id': 'library', 'op': 'library', 'libraries': list(libraries)})
    if objects:
        content = {k: v for k, v in objects.items() if k != 'files'}
        setup.append(dict({'id': 'objects', 'op': 'objects', 'content': content},
                          **({'files': objects['files']} if objects.get('files') else {})))
    if files:
        setup.append({'id': 'inputs', 'op': 'upload', 'area': 'inbox', 'files': sorted(set(files))})
    for cp in steps:
        cp['depends_on'] = ['setup:' + item['id'] for item in setup] + list(cp['depends_on'])
        cp['assertions'] = []
        for i, text in enumerate(cp.pop('acceptance')):
            suffix = 'visible' if i == 0 else f'visible-{i + 1}'
            cp['assertions'].append({'id': f'{key}/{cp["id"]}/{suffix}', 'channel': 'frontend', 'method': 'agent',
                                     'requirement': text})
        for check in cp.pop('checks'):
            cp['assertions'].append({'id': f'{key}/{cp["id"]}/{check["aspect"]}', 'channel': 'backend',
                                     'method': 'program', 'requirement': check['description'],
                                     'check': check['check']})
    ids = {a['id'] for cp in steps for a in cp['assertions']}
    for cp in steps:
        for suffix, points in cp.pop('requires', {}).items():
            point = next(a for a in cp['assertions'] if a['id'] == f'{key}/{cp["id"]}/{suffix}')
            point['requires'] = [f'{key}/{cp["id"]}/{p}' if '/' not in p else f'{key}/{p}' for p in points]
            assert all(r in ids for r in point['requires']), point['requires']
    for cp in steps:
        for suffix, companions in COMPANIONS.get((key, cp['id']), {}).items():
            assertion = next(a for a in cp['assertions'] if a['id'].endswith('/' + suffix))
            assertion['requires'] = [f'{key}/{cp["id"]}/{other}' for other in companions]
            assert all(other in ids for other in assertion['requires'])
    documents = {name: {'path': f'{inbox(key)}/{name}', 'content': DESCRIPTIONS.get(name, 'input file')}
                 for name in files}
    start = ('The application has just started with a fresh data directory' +
             (', a library prepared for this episode' if (libraries or objects) else ' and an empty library') +
             (' and input files in the inbox' if files else '') + '. ')
    n = len(steps)
    return {'id': key, 'feature': feature, 'execution': 'gui',
            'initial_state': 'Fresh application process with a fresh DATA_DIR and a private desktop session; '
                             'setup writes the listed library through the local API and uploads the listed files '
                             'into the inbox before the first goal.' + (' ' + notes if notes else ''),
            'setup': setup,
            'inputs': {'input_folder': inbox(key), 'output_folder': outbox(key), 'documents': documents},
            'session': start + (session + ' ' if session else '') + 'Work on the goals in order. ' + HINTS,
            'allowed_equivalents': ['Menus, toolbar buttons, context menus, keyboard shortcuts, drag and drop and '
                                    'item pane controls that reach the same product command are equivalent.',
                                    'Items may be selected with clicks or keyboard navigation; panes may be resized.',
                                    'Typing a full path into a file chooser is equivalent to browsing to it.'],
            'forbidden_bypasses': ['Do not use terminals, other applications, private files or hidden state.',
                                   'Do not recreate a missing product command by other means (for example by '
                                   'retyping an item instead of duplicating it, or editing files outside the '
                                   'application).'],
            'budget': {'calls': min(200, 70 + 40 * n), 'seconds': min(2400, 900 + 300 * n),
                       'tokens': min(3_000_000, 1_000_000 + 500_000 * n)},
            'checkpoints': steps}


# Companion points make unchanged objects and visually silent commands count only with their result.
COMPANIONS = {('export-rdf-notes', 'export'): {'visible': ['rdf']},
 ('export-cff-endnote', 'cff'): {'visible': ['cff']},
 ('export-cff-endnote', 'endnote'): {'visible': ['endnote']},
 ('bibliography-rtf', 'rtf'): {'visible': ['rtf']},
 ('bibliography-html', 'html'): {'visible': ['html']},
 ('bibliography-clipboard', 'copy'): {'visible': ['text', 'html']},
 ('quick-copy', 'bibliography'): {'visible': ['text']},
 ('quick-copy', 'citation'): {'visible': ['text']},
 ('quick-copy', 'setting'): {'visible': ['text']},
 ('tags-automatic', 'delete'): {'visible': ['tags', 'item-coral-reef-survey'], 'item-kelp-forests': ['tags']},
 ('item-duplicate', 'duplicate'): {'item-the-design-of-everyday-things': ['item-the-design-of-everyday-things-revised']},
 ('item-trash', 'trash'): {'item-kept-manual': ['item-obsolete-manual']},
 ('item-trash', 'empty'): {'item-kept-manual': ['absent-obsolete-manual']},
 ('item-undo', 'redo'): {'item-redo-handbook': ['item-undo-handbook']},
 ('items-edit-multiple', 'catalog'): {'item-quicksort': ['catalog']},
 ('items-edit-multiple', 'call-number'): {'item-algorithms': ['item-quicksort']},
 ('item-create-section', 'section'): {'item-patterns-of-discovery': ['item-observation']},
 ('import-ris', 'import'): {'collections': ['article', 'book', 'section']},
 ('search-saved-edit', 'delete'): {'item-molecular-structure-of-nucleic-acids': ['searches']},
 ('attach-titles', 'normalize'): {'children-wetland-maps': ['children']},
 ('attach-link-file', 'link'): {'visible': ['children']},
 ('attach-link-file', 'convert'): {'visible': ['children'], 'original-file': ['children']},
 ('rtf-scan', 'scan'): {'visible': ['rtf']}}


DESCRIPTIONS = {
    'reader.pdf': 'three-page PDF; each page has a heading "Chapter N: Reading Closely" and the sentences "The quick '
                  'brown fox jumps over the lazy dog.", "This is page N of the sample document." and "Highlight this '
                  'sentence for later reference."',
    'paper.pdf': 'two-page PDF titled "Quantum Gardening" by Ada Lovelace',
    'notes.pdf': 'one-page PDF titled "Field Notes" by Rachel Carson',
    'references.bib': 'BibTeX file with five entries: Knuth 1968 (book), Shannon 1948 (article), Lamport 1978 '
                      '(inproceedings), Noether 1907 (phdthesis) and an Example Consortium 2020 dataset (misc)',
    'references.ris': 'RIS file with three records: Moore 1965 (journal article), Carson 1962 (book) and Dijkstra '
                      '1987 (book chapter)',
    'references.json': 'CSL JSON file with three items: von Neumann 1928 (article), Wiener 1948 (book) and a web page',
    'references.txt': 'Refer/BibIX file with two records: Turing 1950 (journal article) and Brooks 1975 (book)',
    'pubmed.nbib': 'MEDLINE/PubMed record of a 2004 journal article by Walker and Stickgold',
    'mods.xml': 'MODS XML file with one book: Berners-Lee, Weaving the Web (1999)',
    'scan.rtf': 'RTF document with the citation markers {Knuth, 1968} and {Turing, 1936}',
    'references.rdf': 'Zotero RDF containing Archive Studies, a child note and the Source Papers collection',
    'endnote.xml': 'Endnote XML containing Endnote Survey by Alan Turing (1950)',
    'minimal.csl': 'CSL citation style "Bench Minimal Author-Year"',
}


def obj(number, item_type='book', title='', creators=(), **fields):
    """An episode's own setup item (key GI...)."""
    data = {'key': K('GI', number), 'version': 0, 'itemType': item_type,
            'creators': [dict(zip(('creatorType', 'firstName', 'lastName'), c)) if len(c) == 3
                         else {'creatorType': c[0], 'name': c[1]} for c in creators],
            'dateAdded': library.stamp(number), 'dateModified': library.stamp(number)}
    if title:
        data['title'] = title
    data.update(fields)
    return data


# ------------------------------------------------------------------------------------------------ recipes
def r(op, **fields):
    return dict({'op': op}, **fields)


LIB = r('library')


def new_item(type_label):
    return [LIB, r('menu', path=['File', 'New Item', type_label]), r('wait', seconds=1.5)]


def select(title):
    return r('item', title=title)


def field(label, value):
    return r('field', label=label, value=value)


def creator(last, first, row=0):
    return [r('click', target={'role': 'entry', 'name': '(last)', 'nth': row}), r('key', key='Control+a'),
            r('type', value=last), r('key', key='Tab'), r('key', key='Control+a'), r('type', value=first),
            r('key', key='Return'), r('wait', seconds=0.5)]


def hover_creator(row):
    return r('raw', request={'op': 'move', 'target': {'role': 'entry', 'name': '(last)', 'nth': row}, 'seconds': 0.4})


# ------------------------------------------------------------------------------------------------- items
def item_episodes():
    flows = []
    k = 'item-create-book'
    flows.append(episode(k, 'items', [
        step('create', 'In My Library, create a new item of type Book with the title "Thinking in Systems", the author '
                       'Donella Meadows (last name "Meadows", first name "Donella"), the date "2008" and the publisher '
                       '"Chelsea Green".',
             'A Book item titled "Thinking in Systems" is listed, and its details show the author Meadows, Donella, '
             'the date 2008 and the publisher Chelsea Green.',
             [*new_item('Book'), r('type', value='Thinking in Systems'), r('key', key='Return'), r('wait', seconds=0.5),
              *creator('Meadows', 'Donella'), field('Date', '2008'), field('Publisher', 'Chelsea Green')],
             [item('Thinking in Systems', 'itemType,title,creators,date,publisher,place',
                   'The new item is a Book with the given title, author, date and publisher.')]),
        step('edit', 'Change the publisher of "Thinking in Systems" to "Earthscan" and set its place to "London".',
             'The details of "Thinking in Systems" show the publisher Earthscan and the place London.',
             [select('Thinking in Systems'), field('Publisher', 'Earthscan'), field('Place', 'London')],
             [item('Thinking in Systems', 'itemType,title,creators,date,publisher,place',
                   'The item keeps its title, author and date and has the new publisher and place.')],
             depends=['create']),
        step('reopen', 'The application was restarted with the same data. Select "Thinking in Systems" again.',
             'After the restart "Thinking in Systems" is still listed with the publisher Earthscan and the place '
             'London.',
             [LIB, select('Thinking in Systems')],
             [item('Thinking in Systems', 'itemType,title,creators,date,publisher,place',
                   'After a restart the item is unchanged.')],
             depends=['edit'], lifecycle='restart'),
    ]))

    k = 'item-create-article'
    flows.append(episode(k, 'items', [
        step('create', 'In My Library, create a Journal Article titled "Sleep and Memory Consolidation" by Matthew '
                       'Walker (last name "Walker", first name "Matthew") and Robert Stickgold (last name "Stickgold", '
                       'first name "Robert"), in that author order. Set the publication to "Journal of Sleep Research", '
                       'the volume to "12", the issue to "4", the pages to "101-110", the date to "2004-04" and the DOI '
                       'to "10.1111/jsr.2004.12".',
             ['A Journal Article "Sleep and Memory Consolidation" is listed with the authors Walker and Stickgold in '
              'that order.',
              'Its details show the publication Journal of Sleep Research, volume 12, issue 4, pages 101-110, date '
              '2004-04 and the DOI 10.1111/jsr.2004.12.'],
             [*new_item('Journal Article'), r('type', value='Sleep and Memory Consolidation'), r('key', key='Return'),
              r('wait', seconds=0.5), *creator('Walker', 'Matthew'), hover_creator(0),
              r('click', target={'role': 'push button', 'name': 'Create'}), r('wait', seconds=0.5),
              r('type', value='Stickgold'), r('key', key='Tab'), r('type', value='Robert'), r('key', key='Return'),
              r('wait', seconds=0.5), field('Publication', 'Journal of Sleep Research'), field('Volume', '12'),
              field('Issue', '4'), field('Pages', '101-110'), field('Date', '2004-04'),
              field('DOI', '10.1111/jsr.2004.12')],
             [item('Sleep and Memory Consolidation', 'itemType,title,creators',
                   'The item is a Journal Article with the two authors in order.', aspect='authors'),
              item('Sleep and Memory Consolidation', 'publicationTitle,volume,issue,pages,date,DOI',
                   'The publication, volume, issue, pages, date and DOI are stored.', aspect='publication')]),
    ]))

    k = 'item-creators'
    base = [obj(1, 'book', 'Patterns of Software', [('author', 'Richard', 'Gabriel')], date='1996',
                publisher='Oxford University Press')]
    flows.append(episode(k, 'items', [
        step('add-editor', 'Add a second creator to "Patterns of Software": the editor Grace Hopper (last name '
                           '"Hopper", first name "Grace"), after the author Richard Gabriel.',
             '"Patterns of Software" lists the author Gabriel, Richard followed by the editor Hopper, Grace.',
             [LIB, select('Patterns of Software'), hover_creator(0), r('click', target={'role': 'push button',
                                                                                         'name': 'Create'}),
              r('wait', seconds=0.5), r('type', value='Hopper'), r('key', key='Tab'), r('type', value='Grace'),
              r('key', key='Return'), r('wait', seconds=0.5),
              r('click', target={'role': 'push button', 'name': 'Author', 'nth': 1}),
              r('click', target={'role': 'menu item', 'name': 'Editor'}), r('wait', seconds=0.5)],
             [item('Patterns of Software', 'creators', 'The creators are the author Gabriel and then the editor Hopper.')]),
        step('move-up', 'Move the editor Grace Hopper above the author Richard Gabriel in the creator list of '
                        '"Patterns of Software".',
             'The creator list of "Patterns of Software" now starts with the editor Hopper, Grace, followed by the '
             'author Gabriel, Richard.',
             [LIB, select('Patterns of Software'), hover_creator(1),
              r('click', target={'role': 'push button', 'name': 'Open context menu', 'nth': 2}),
              r('click', target={'role': 'menu item', 'name': 'Move Up'}), r('wait', seconds=0.5)],
             [item('Patterns of Software', 'creators', 'The editor now comes first, the author second.')],
             depends=['add-editor']),
        step('single-field', 'Turn the author of "Patterns of Software" into a single-field name and replace it with '
                             '"Software Patterns Group".',
             'The author of "Patterns of Software" is shown as the single name Software Patterns Group; the editor '
             'Hopper, Grace is unchanged.',
             [LIB, select('Patterns of Software'), hover_creator(1),
              r('click', target={'role': 'push button', 'name': 'Switch to Single Field', 'nth': 1}),
              r('wait', seconds=0.5), r('click', target={'role': 'entry', 'text': 'Richard Gabriel'}),
              r('key', key='Control+a'), r('type', value='Software Patterns Group'), r('key', key='Return'),
              r('wait', seconds=0.5)],
             [item('Patterns of Software', 'creators', 'The author is the single-field name, the editor unchanged.')],
             depends=['move-up']),
        step('remove', 'Remove the editor Grace Hopper from "Patterns of Software".',
             '"Patterns of Software" has only the author Software Patterns Group left.',
             [LIB, select('Patterns of Software'), hover_creator(0),
              r('click', target={'role': 'push button', 'name': 'Delete', 'nth': 0}), r('wait', seconds=0.5)],
             [item('Patterns of Software', 'creators', 'Only the single-field author remains.')],
             depends=['single-field']),
    ], objects={'items': base}))

    k = 'item-type-change'
    base = [obj(2, 'journalArticle', 'Category Theory for Programmers', [('author', 'Bartosz', 'Milewski')],
                publicationTitle='Programming Essays', volume='3', pages='11-42', date='2014', ISSN='1234-5678')]
    flows.append(episode(k, 'items', [
        step('to-section', 'Change the item type of "Category Theory for Programmers" from Journal Article to Book '
                           'Section.',
             '"Category Theory for Programmers" is now a Book Section; its title, author, date and pages are kept and '
             'the former publication appears as the book title.',
             [LIB, select('Category Theory for Programmers'),
              r('click', target={'role': 'combo box', 'name': 'Item Type'}),
              r('click', target={'role': 'menu item', 'name': 'Book Section'}), r('wait', seconds=1.0),
              r('confirm-if', title='Zotero', button='OK')],
             [item('Category Theory for Programmers', 'itemType,title,creators,date,pages,bookTitle,volume,ISSN',
                   'The item became a book section; mapped fields moved, fields the type lacks are handled the '
                   'product\'s way.')]),
    ], objects={'items': base}))

    k = 'item-text-fields'
    base = [obj(3, 'webpage', 'Garden Birds of Europe', [('author', 'Rachel', 'Carson')], websiteTitle='Birding Notes')]
    abstract = 'Robins return early.\nWrens stay all winter.'
    flows.append(episode(k, 'items', [
        step('abstract', 'Set the abstract of "Garden Birds of Europe" to ' + text_value(abstract),
             'The abstract of "Garden Birds of Europe" shows both lines.',
             [LIB, select('Garden Birds of Europe'), r('click', target={'role': 'entry', 'name': 'Abstract'}),
              r('key', key='Control+a'), r('type', value=abstract), r('click', target={'role': 'entry', 'name': 'Title',
                                                                                        'nth': 1}),
              r('key', key='Escape'), r('wait', seconds=0.5)],
             [item('Garden Birds of Europe', 'abstractNote', 'The abstract holds both lines.')]),
        step('fields', 'Set the URL of "Garden Birds of Europe" to "https://birds.example.org/europe", its short title '
                       'to "Garden Birds" and its language to "en".',
             'The details of "Garden Birds of Europe" show the URL https://birds.example.org/europe, the short title '
             'Garden Birds and the language en.',
             [LIB, select('Garden Birds of Europe'), field('URL', 'https://birds.example.org/europe'),
              field('Short Title', 'Garden Birds'), field('Language', 'en')],
             [item('Garden Birds of Europe', 'url,shortTitle,language,websiteTitle',
                   'URL, short title and language are stored.')]),
        step('extra', 'Set the Extra field of "Garden Birds of Europe" to ' + text_value('Original date: 1962\nNote: illustrated'),
             'The Extra field of "Garden Birds of Europe" shows both lines.',
             [LIB, select('Garden Birds of Europe'), r('click', target={'role': 'entry', 'name': 'Extra'}),
              r('key', key='Control+a'), r('type', value='Original date: 1962\nNote: illustrated'),
              r('click', target={'role': 'entry', 'name': 'Title', 'nth': 1}), r('key', key='Escape'),
              r('wait', seconds=0.5)],
             [item('Garden Birds of Europe', 'extra', 'Extra holds both lines.')]),
    ], objects={'items': base}))

    k = 'item-dates'
    base = [obj(4, 'book', 'Calendar Studies', [('author', 'Ada', 'Lovelace')])]
    flows.append(episode(k, 'items', [
        step('us-date', 'Set the date of "Calendar Studies" to "3/5/2021".',
             'The date of "Calendar Studies" shows 3/5/2021.',
             [LIB, select('Calendar Studies'), field('Date', '3/5/2021')],
             [{'description': 'The date is stored as typed and parsed as 2021-03-05.', 'aspect': 'date',
               'check': {'steps': [find('Calendar Studies', ['fields:date', 'meta:parsedDate'])]}}]),
        step('month-date', 'Change the date of "Calendar Studies" to "March 1999".',
             'The date of "Calendar Studies" shows March 1999.',
             [LIB, select('Calendar Studies'), field('Date', 'March 1999')],
             [{'description': 'The date is stored as typed and parsed as 1999-03.', 'aspect': 'date',
               'check': {'steps': [find('Calendar Studies', ['fields:date', 'meta:parsedDate'])]}}],
             depends=['us-date']),
    ], objects={'items': base}))

    k = 'item-duplicate'
    base = [obj(5, 'book', 'The Design of Everyday Things', [('author', 'Don', 'Norman')], date='1988',
                publisher='Basic Books', tags=[{'tag': 'design'}])]
    flows.append(episode(k, 'items', [
        step('duplicate', 'Duplicate the item "The Design of Everyday Things" with the application\'s Duplicate Item '
                          'command, then change the title of the copy to "The Design of Everyday Things (Revised)" and '
                          'its date to "2013".',
             ['Both "The Design of Everyday Things" and "The Design of Everyday Things (Revised)" are listed.',
              'The revised copy shows the author Norman, Don, the publisher Basic Books and the date 2013.'],
             [LIB, r('context', target={'item': 'The Design of Everyday Things'},
                     path=['Duplicate Item']), r('wait', seconds=1.5),
              field('Title', 'The Design of Everyday Things (Revised)'), field('Date', '2013')],
             [item('The Design of Everyday Things', 'itemType,creators,date,publisher,tags',
                   'The original item is unchanged.'),
              item('The Design of Everyday Things (Revised)', 'itemType,creators,date,publisher,tags',
                   'The copy keeps the creators, publisher and tags, with the new title and date.')]),
    ], objects={'items': base}))

    k = 'item-trash'
    base = [obj(6, 'book', 'Obsolete Manual', date='1990'), obj(7, 'book', 'Kept Manual', date='1991')]
    flows.append(episode(k, 'trash', [
        step('trash', 'Move the item "Obsolete Manual" to the trash.',
             'The Trash lists "Obsolete Manual".',
             [LIB, r('context', target={'item': 'Obsolete Manual'}, path=['Move Item to Trash…']),
              r('confirm', button='OK'), r('wait', seconds=1.0), r('collection', name='Trash')],
             [item('Obsolete Manual', 'title,deleted', 'The item is in the trash.'),
              item('Kept Manual', 'title,deleted', 'The other item is not in the trash.')]),
        step('restore', 'Restore "Obsolete Manual" from the trash to the library.',
             '"Obsolete Manual" is listed in My Library again.',
             [r('collection', name='Trash'), r('context', target={'item': 'Obsolete Manual'},
                                                 path=['Restore to Library']), r('wait', seconds=1.0), LIB],
             [item('Obsolete Manual', 'title,deleted', 'The item is out of the trash.')], depends=['trash']),
        step('empty', 'Move "Obsolete Manual" to the trash again and then empty the trash, deleting it permanently.',
             'The Trash is empty.',
             [LIB, r('context', target={'item': 'Obsolete Manual'}, path=['Move Item to Trash…']),
              r('confirm', button='OK'), r('wait', seconds=1.0),
              r('context', target={'collection': 'Trash'}, path=['Empty Trash']),
              r('confirm', button='OK'), r('wait', seconds=1.5), LIB, r('collection', name='Trash')],
             [absent('Obsolete Manual', 'The item is deleted permanently.'),
              item('Kept Manual', 'title,deleted', 'The other item remains in the library.')],
             depends=['restore'], requires={'visible': ['absent-obsolete-manual', 'item-kept-manual']}),
    ], objects={'items': base}))

    k = 'item-undo'
    base = [obj(8, 'book', 'Undo Handbook', date='2001'), obj(9, 'book', 'Redo Handbook', date='2002')]
    flows.append(episode(k, 'trash', [
        step('trash', 'Move "Undo Handbook" to the trash.',
             '"Undo Handbook" is no longer listed in My Library.',
             [LIB, r('context', target={'item': 'Undo Handbook'}, path=['Move Item to Trash…']),
              r('confirm', button='OK'), r('wait', seconds=1.0)],
             [item('Undo Handbook', 'title,deleted', 'The item is in the trash.')]),
        step('undo', 'Undo the last action with the application\'s Undo command.',
             '"Undo Handbook" is listed in My Library again.',
             [LIB, r('menu', path=['Edit', 'Undo Trash Item']), r('wait', seconds=1.0)],
             [item('Undo Handbook', 'title,deleted', 'The item is restored by Undo.')], depends=['trash']),
        step('redo', 'Redo the undone action with the application\'s Redo command.',
             '"Undo Handbook" is no longer listed in My Library; "Redo Handbook" still is.',
             [LIB, r('menu', path=['Edit', 'Redo Trash Item']), r('wait', seconds=1.0)],
             [item('Undo Handbook', 'title,deleted', 'The item is back in the trash after Redo.'),
              item('Redo Handbook', 'title,deleted', 'The other item is untouched.')], depends=['undo']),
    ], objects={'items': base}))

    k = 'item-merge'
    base = [obj(10, 'book', 'Gödel, Escher, Bach', [('author', 'Douglas', 'Hofstadter')], date='1979',
                publisher='Basic Books', tags=[{'tag': 'mind'}]),
            obj(11, 'book', 'Godel, Escher, Bach', [('author', 'Douglas R.', 'Hofstadter')], date='1979',
                place='New York', ISBN='978-0-465-02656-2', tags=[{'tag': 'music'}])]
    flows.append(episode(k, 'items', [
        step('merge', 'In the Duplicate Items view, merge the two versions of "Gödel, Escher, Bach", keeping the '
                      'version with the title "Gödel, Escher, Bach" (with ö) as the master item and taking the ISBN '
                      '978-0-465-02656-2 and the place New York from the other version.',
             ['Only one "Gödel, Escher, Bach" remains in My Library.',
              'The merged item shows the publisher Basic Books, the place New York and the ISBN 978-0-465-02656-2.'],
             [r('collection', name='Duplicate Items'), r('wait', seconds=1.5),
              r('item', title='Gödel, Escher, Bach'), r('wait', seconds=1.0),
              r('merge-fields', values={'Place': 'New York', 'ISBN': '978-0-465-02656-2'}),
              r('click', target={'role': 'push button', 'name': 'Merge 2 items'}), r('wait', seconds=1.5), LIB,
              select('Gödel, Escher, Bach')],
             [item('Gödel, Escher, Bach', 'itemType,creators,date,publisher,place,ISBN,tags,deleted',
                   'The master keeps its fields, takes the chosen ones and both tags.'),
              item('Godel, Escher, Bach', 'title,deleted', 'The other version is in the trash.')]),
    ], objects={'items': base}))

    k = 'item-related'
    base = [obj(12, 'book', 'Structure and Interpretation of Computer Programs', [('author', 'Harold', 'Abelson')],
                date='1985'),
            obj(13, 'book', 'How to Design Programs', [('author', 'Matthias', 'Felleisen')], date='2001')]
    flows.append(episode(k, 'items', [
        step('relate', 'Mark "How to Design Programs" as related to "Structure and Interpretation of Computer '
                       'Programs".',
             'The related items of "Structure and Interpretation of Computer Programs" include "How to Design '
             'Programs".',
             [LIB, select('Structure and Interpretation of Computer Programs'),
              r('add-related', title='How to Design Programs'),
              r('raw', request={'op': 'scroll', 'x': 1080, 'y': 600, 'delta_y': 2500})],
             [item('Structure and Interpretation of Computer Programs', 'relations',
                   'The first item records the relation.'),
              item('How to Design Programs', 'relations', 'The relation is recorded on the other item too.')]),
        step('unrelate', 'Remove that relation again.',
             'Structure and Interpretation of Computer Programs no longer lists How to Design Programs as related.',
             [LIB, select('Structure and Interpretation of Computer Programs'),
              r('remove-related', title='How to Design Programs')],
             [item('Structure and Interpretation of Computer Programs', 'relations', 'The relation is removed.'),
              item('How to Design Programs', 'relations', 'The relation is removed on the other side too.')],
             depends=['relate']),
    ], objects={'items': base}))

    k = 'items-edit-multiple'
    flows.append(episode(k, 'items', [
        step('catalog', 'Open the collection "Reading List", select all of its items and, with the application\'s '
                        'command for editing several items at once, set their Library Catalog to "Example Catalog".',
             'The selected item Algorithms shows Library Catalog Example Catalog.',
             [r('collection', name='Reading List'), select('Algorithms'), r('key', key='Control+a'),
              r('wait', seconds=0.8), r('click', target={'role': 'push button', 'name': 'Edit Multiple Items…'}),
              r('wait', seconds=1.0), r('click', target={'role': 'entry', 'name': 'Library Catalog'}),
              r('type', value='Example Catalog'), r('key', key='Return'), r('wait', seconds=0.8),
              r('click', target={'role': 'push button', 'name': 'Done'}), r('wait', seconds=1.0),
              select('Algorithms'), r('show-field', name='Library Catalog')],
             [{'description': 'Every item of Reading List has the library catalog.', 'aspect': 'catalog',
               'check': {'steps': [find('Reading List', [], field='name', path=f'{U}/collections'),
                                   {'method': 'GET', 'path': U + '/collections/{found}/items/top',
                                    'view': ['unordered:fields:title,libraryCatalog']}]}},
              item('Quicksort', 'title,libraryCatalog', 'An item outside Reading List keeps its catalog.')]),
        step('call-number', 'In My Library, select just "Quicksort" and "The Art of Computer Programming" and set the '
                            'Call Number of both to "QA76.6" in the same way.',
             'The selected item Quicksort shows Call Number QA76.6.',
             [LIB, select('Quicksort'), r('item', title='The Art of Computer Programming', modifiers=['Control']),
              r('wait', seconds=0.8), r('click', target={'role': 'push button', 'name': 'Edit Multiple Items…'}),
              r('wait', seconds=1.0), r('click', target={'role': 'entry', 'name': 'Call Number'}),
              r('type', value='QA76.6'), r('key', key='Return'), r('wait', seconds=0.8),
              r('click', target={'role': 'push button', 'name': 'Done'}), r('wait', seconds=1.0),
              select('Quicksort'), r('show-field', name='Call Number')],
             [item('Quicksort', 'title,callNumber', 'Quicksort has the call number.'),
              item('The Art of Computer Programming', 'title,callNumber', 'The other selected item has it too.'),
              item('Algorithms', 'title,callNumber', 'An item that was not selected has no call number.')]),
    ], libraries=['query']))

    k = 'item-create-section'
    base = [obj(14, 'book', 'Patterns of Discovery', [('author', 'Norwood', 'Hanson'), ('editor', 'Mary', 'Hesse')],
                date='1958', publisher='Cambridge University Press', place='Cambridge', ISBN='978-0-521-05197-2',
                numPages='241', language='en')]
    flows.append(episode(k, 'items', [
        step('section', 'Create a book section of the book "Patterns of Discovery" with the application\'s command '
                        'for that, and give the new section the title "Observation".',
             'A Book Section titled Observation is listed; its details show the book title Patterns of Discovery and '
             'the book\'s publication details.',
             [LIB, r('context', target={'item': 'Patterns of Discovery'}, path=['Create Book Section']),
              r('wait', seconds=1.5), r('type', value='Observation'), r('key', key='Return'), r('wait', seconds=1.0)],
             [item('Observation', 'itemType,title,bookTitle,creators,date,publisher,place,ISBN,language,numPages',
                   'The section takes over the book\'s details, with the book\'s authors as book authors.'),
              item('Patterns of Discovery', 'itemType,title,creators,numPages', 'The book itself is unchanged.')]),
    ], objects={'items': base}))
    return flows


def text_value(value):
    """Render an exact text input unambiguously for the evaluator."""
    if '\n' not in value:
        return '"' + value + '"'
    return ('exactly the lines between the ``` fences (the line breaks are part of the text).\n```\n' + value
            + '\n```\n')


# ------------------------------------------------------------------------------------------------- notes
def note_episodes():
    flows = []
    k = 'note-child'
    base = [obj(20, 'book', 'Silent Spring', [('author', 'Rachel', 'Carson')], date='1962')]
    flows.append(episode(k, 'notes', [
        step('add', 'Add a child note to "Silent Spring" with two paragraphs: "Pesticides harm songbirds." and '
                    '"Published in 1962."',
             '"Silent Spring" has a child note whose text shows both paragraphs.',
             [LIB, r('context', target={'item': 'Silent Spring'}, path=['Add Note']),
              r('wait', seconds=2.0), r('type', value='Pesticides harm songbirds.'), r('key', key='Return'),
              r('type', value='Published in 1962.'), r('wait', seconds=1.5)],
             [children('Silent Spring', 'itemType,note', 'The child note holds both paragraphs.')]),
        step('bold', 'In the same note, add a third paragraph with the bold text "Read again."',
             'The note of "Silent Spring" shows a third paragraph "Read again." in bold.',
             [LIB, r('open-child', title='Silent Spring', child='Pesticides harm songbirds.'),
              r('note-append', text='Read again.', bold=True)],
             [children('Silent Spring', 'itemType,note', 'The note gains a bold third paragraph.')],
             depends=['add']),
    ], objects={'items': base}))

    k = 'note-standalone'
    flows.append(episode(k, 'notes', [
        step('add', 'In the collection "Reading List", create a standalone note (not attached to any item) with the '
                    'text "Books to borrow this month".',
             'A note "Books to borrow this month" is listed in the collection Reading List as an item of its own.',
             [r('collection', name='Reading List'), r('menu', path=['File', 'New Note', 'New Standalone Note']),
              r('wait', seconds=2.0), r('type', value='Books to borrow this month'), r('wait', seconds=1.5)],
             [{'description': 'A standalone note with the text exists in the collection.', 'aspect': 'note',
               'check': {'steps': [find('Books to borrow this month', 'fields:itemType,note,parentItem,collections',
                                        field='note-text', path=f'{U}/items?itemType=note')]}}]),
    ], libraries=['query']))

    k = 'note-format'
    base = [obj(21, 'book', 'The Sea Around Us', [('author', 'Rachel', 'Carson')], date='1951')]
    flows.append(episode(k, 'notes', [
        step('list', 'Add a child note to "The Sea Around Us" that starts with a Heading 1 heading "Summary", followed by a '
                     'bulleted list with the two entries "Tides shape the coast" and "Currents move heat".',
             '"The Sea Around Us" has a child note showing the heading Summary above a bulleted list with the two '
             'entries.',
             [LIB, r('context', target={'item': 'The Sea Around Us'}, path=['Add Note']), r('wait', seconds=2.5),
              r('type', value='# Summary'), r('key', key='Return'), r('type', value='- Tides shape the coast'),
              r('key', key='Return'), r('type', value='Currents move heat'), r('wait', seconds=1.5)],
             [children('The Sea Around Us', 'itemType,note', 'The note holds the heading and the bulleted list.')]),
        step('numbered', 'Below the bulleted list, in the same note, add a numbered list with the entries "Read '
                         'chapter 1" and "Read chapter 2".',
             'The note shows a numbered list (1. Read chapter 1, 2. Read chapter 2) below the bulleted list.',
             [r('note-end'), r('key', key='Return'), r('key', key='Return'), r('type', value='1. Read chapter 1'),
              r('key', key='Return'), r('type', value='Read chapter 2'), r('wait', seconds=1.5)],
             [children('The Sea Around Us', 'itemType,note', 'The note gains the numbered list after the bulleted '
                                                             'list.')], depends=['list']),
    ], objects={'items': base}))
    return flows


# --------------------------------------------------------------------------------------------- collections
C = library.COLLECTION_KEYS


def collection_tree(description, aspect='collections'):
    return {'description': description, 'aspect': aspect,
            'check': {'steps': [{'method': 'GET', 'path': f'{U}/collections', 'view': ['collection-tree']}]}}


def new_collection(name, parent=None):
    steps = []
    if parent:
        steps.append(r('context', target={'collection': parent}, path=['New Subcollection…']))
    else:
        steps += [LIB, r('click', target={'role': 'push button', 'name': 'New Collection…'})]
    steps += [r('window', title='New Collection'), r('fill', target={'role': 'entry', 'name': 'Name:'}, value=name),
              r('click', target={'role': 'push button', 'name': 'Create Collection'}), r('wait', seconds=1.0)]
    return steps


def collection_episodes():
    flows = []
    k = 'collection-create'
    flows.append(episode(k, 'collections', [
        step('create', 'Create a new top-level collection named "Physics".',
             'A collection Physics is listed under My Library.',
             new_collection('Physics'),
             [collection('Physics', 'name,parentCollection', 'A top-level collection Physics exists.')]),
        step('subcollection', 'Create a subcollection named "Quantum" inside "Physics".',
             'Physics contains a subcollection Quantum.',
             new_collection('Quantum', parent='Physics'),
             [collection('Quantum', 'name,parentCollection', 'Quantum exists with Physics as its parent.'),
              collection_tree('The collection tree has Physics at the top with Quantum inside.')],
             depends=['create']),
    ]))

    k = 'collection-rename-move'
    flows.append(episode(k, 'collections', [
        step('rename', 'Rename the collection "Reading List" to "To Read".',
             'The collection formerly called Reading List is now listed as To Read, with the same items.',
             [r('context', target={'collection': 'Reading List'}, path=['Rename']),
              r('wait', seconds=0.8), r('key', key='Control+a'), r('type', value='To Read'), r('key', key='Return'),
              r('wait', seconds=1.0), r('collection', name='To Read')],
             [collection_items('To Read', 'The renamed collection keeps its items.'),
              collection_tree('The tree shows To Read instead of Reading List.')]),
        step('move', 'Move the collection "Theory of Computation" out of "Computer Science" so that it becomes a '
                     'top-level collection.',
             'Theory of Computation is listed at the top level of My Library and no longer inside Computer Science.',
             [r('context', target={'collection': 'Theory of Computation'}, path=['Move To', 'My Library']),
              r('wait', seconds=1.0)],
             [collection('Theory of Computation', 'name,parentCollection', 'The collection has no parent any more.'),
              collection_tree('The tree has Theory of Computation at the top level.')], depends=['rename']),
    ], libraries=['query']))

    k = 'collection-membership'
    flows.append(episode(k, 'collections', [
        step('add', 'Add the item "The Origin of Species" to the collection "Reading List" (it stays in Biology as '
                    'well).',
             'The collection Reading List lists The Origin of Species.',
             [LIB, r('context', target={'item': 'The Origin of Species'},
                     path=['Add to Collection', 'Reading List']), r('wait', seconds=1.0),
              r('collection', name='Reading List')],
             [item('The Origin of Species', 'collections', 'The item is in Biology and Reading List.'),
              collection_items('Reading List', 'Reading List now includes The Origin of Species.')]),
        step('remove', 'Remove the item "As We May Think" from the collection "Reading List" without deleting it.',
             'Reading List no longer lists As We May Think.',
             [r('collection', name='Reading List'),
              r('context', target={'item': 'As We May Think'}, path=['Remove Item from Collection…']),
              r('confirm', button='OK'), r('wait', seconds=1.0)],
             [item('As We May Think', 'collections,deleted', 'The item is in no collection and not in the trash.'),
              collection_items('Reading List', 'Reading List no longer includes the item.')],
             depends=['add']),
    ], libraries=['query']))

    k = 'collection-delete'
    flows.append(episode(k, 'collections', [
        step('delete', 'Delete the collection "Empty Collection".',
             'Empty Collection is no longer listed; the other collections remain.',
             [r('context', target={'collection': 'Empty Collection'}, path=['Delete Collection…']),
              r('confirm', button='Delete Collection'), r('wait', seconds=1.0)],
             [collection_tree('Empty Collection is gone, the others remain.')]),
        step('delete-items', 'Delete the collection "Biology" together with its items.',
             'Biology is no longer listed, and its items (for example The Origin of Species) are in the Trash.',
             [r('context', target={'collection': 'Biology'}, path=['Delete Collection and Items…']),
              r('confirm', button='Delete Collection and Items'), r('wait', seconds=1.5), r('collection', name='Trash')],
             [collection_tree('Biology is gone.'),
              items(f'{U}/items/trash', 'unordered:fields:title', 'The items of Biology are in the trash.', 'trash')], depends=['delete']),
    ], libraries=['query']))

    k = 'collection-subitems'
    flows.append(episode(k, 'collections', [
        step('show', 'Make collections show the items of their subcollections as well, then open the collection '
                     '"Computer Science".',
             'Computer Science lists, besides its own items, the items of Algorithms, Graph Algorithms and Theory of '
             'Computation (for example The Art of Computer Programming and On Computable Numbers).',
             [r('menu', path=['View', 'Show Items from Subcollections']), r('wait', seconds=1.0),
              r('collection', name='Computer Science'), r('wait', seconds=1.0)]),
        step('hide', 'Turn the display of subcollection items off again, keeping "Computer Science" open.',
             'Computer Science lists only its own items again (On Computable Numbers is no longer listed there).',
             [r('menu', path=['View', 'Show Items from Subcollections']), r('wait', seconds=1.0),
              r('collection', name='Computer Science'), r('wait', seconds=1.0)], depends=['show']),
    ], libraries=['query']))

    k = 'collection-undo'
    flows.append(episode(k, 'collections', [
        step('add', 'Add the item "Quicksort" to the collection "Reading List".',
             'Reading List lists Quicksort.',
             [LIB, r('context', target={'item': 'Quicksort'}, path=['Add to Collection',
                                                                                      'Reading List']),
              r('wait', seconds=1.0), r('collection', name='Reading List')],
             [item('Quicksort', 'collections', 'Quicksort is in Algorithms and Reading List.')]),
        step('undo', 'Undo that with the application\'s Undo command.',
             'Reading List no longer lists Quicksort.',
             [r('menu', path=['Edit', 'Undo Add to Collection']), r('wait', seconds=1.0),
              LIB, r('collection', name='Reading List')],
             [item('Quicksort', 'collections', 'Quicksort is back in Algorithms only.')], depends=['add']),
    ], libraries=['query']))

    k = 'collection-trash'
    reading = {'description': 'The collection Reading List is marked as deleted, not removed.', 'aspect': 'collection',
               'check': {'steps': [{'method': 'GET', 'path': f'{U}/collections/{C["Reading List"]}',
                                    'view': ['fields:name,parentCollection,deleted']}]}}
    flows.append(episode(k, 'collections', [
        step('delete', 'Delete the collection "Reading List" (without its items).',
             'Reading List is no longer listed among the collections, and the Trash lists it.',
             [r('context', target={'collection': 'Reading List'}, path=['Delete Collection…']),
              r('confirm', button='Delete Collection'), r('wait', seconds=1.0), r('collection', name='Trash')],
             [reading, collection_tree('Reading List is no longer among the collections.')]),
        step('restore', 'Restore the collection "Reading List" from the Trash.',
             'Reading List is listed among the collections again and still holds its items (for example As We May '
             'Think).',
             [r('collection', name='Trash'), r('context', target={'item': 'Reading List'}, path=['Restore to Library']),
              r('wait', seconds=1.0), r('collection', name='Reading List')],
             [dict(reading, description='The collection Reading List is no longer marked as deleted.'),
              collection_tree('Reading List is among the collections again.'),
              collection_items('Reading List', 'Reading List still holds its items.')], depends=['delete']),
    ], libraries=['query']))

    k = 'collection-copy'
    flows.append(episode(k, 'collections', [
        step('copy', 'Copy the collection "Algorithms", with its subcollection and items, into the collection '
                     '"Biology"; the original stays where it is.',
             'Biology now contains a collection Algorithms with the subcollection Graph Algorithms, and Computer '
             'Science still contains its Algorithms collection.',
             [r('context', target={'collection': 'Algorithms'}, path=['Copy To', 'Biology']), r('wait', seconds=1.5),
              r('collection', name='Biology'), r('key', key='Right'), r('key', key='Down'),
              r('key', key='Right'), r('wait', seconds=0.5)],
             [collection_tree('The copy and its subcollection sit in Biology beside the originals.'),
              {'description': 'The copy holds the items of the original Algorithms collection.', 'aspect': 'members-copy',
               'check': {'steps': [find('Algorithms', [], field='name', path=f'{U}/collections/{C["Biology"]}/collections'),
                                   {'method': 'GET', 'path': U + '/collections/{found}/items/top',
                                    'view': ['unordered:fields:title']}]}}]),
        step('new-collection', 'Put the item "Quicksort" into a new top-level collection named "Sorting", creating the '
                               'collection from the item\'s Add to Collection menu.',
             'A collection Sorting is listed, and it contains Quicksort.',
             [LIB, r('context', target={'item': 'Quicksort'}, path=['Add to Collection', 'New Collection…']),
              r('window', title='New Collection'), r('fill', target={'role': 'entry', 'name': 'Name:'}, value='Sorting'),
              r('click', target={'role': 'push button', 'name': 'Create Collection'}), r('wait', seconds=1.0),
              r('collection', name='Sorting'), LIB, r('collection', name='Sorting')],
             [collection('Sorting', 'name,parentCollection', 'A top-level collection Sorting exists.'),
              collection_items('Sorting', 'Sorting holds Quicksort.'),
              item('Quicksort', 'collections', 'Quicksort remains in both Algorithms copies and joins Sorting.')], depends=['copy']),
    ], libraries=['query']))
    return flows


# --------------------------------------------------------------------------------------------------- tags
def tag_episodes():
    flows = []
    k = 'tags-item'
    base = [obj(30, 'book', 'Thinking in Systems', [('author', 'Donella', 'Meadows')], date='2008')]
    flows.append(episode(k, 'tags', [
        step('add', 'Add the tags "systems" and "ecology" to "Thinking in Systems".',
             'The tags of "Thinking in Systems" are ecology and systems.',
             [LIB, select('Thinking in Systems'), r('section-add', section='Tags'), r('type', value='systems'),
              r('key', key='Return'), r('wait', seconds=0.5), r('type', value='ecology'), r('key', key='Return'),
              r('wait', seconds=0.5), r('key', key='Escape'), r('wait', seconds=0.8)],
             [item('Thinking in Systems', 'tags', 'The item has the two manual tags.')]),
        step('remove', 'Remove the tag "ecology" from "Thinking in Systems".',
             '"Thinking in Systems" has only the tag systems left.',
             [LIB, select('Thinking in Systems'), r('remove-tag', tag='ecology')],
             [item('Thinking in Systems', 'tags', 'Only the systems tag remains.')], depends=['add']),
    ], objects={'items': base}))

    k = 'tags-rename-delete'
    flows.append(episode(k, 'tags', [
        step('rename', 'Rename the tag "classic" to "canon" everywhere in the library.',
             'The tag selector lists canon instead of classic.',
             [LIB, r('context', target={'role': 'check box', 'name': 'classic'}, path=['Rename Tag…']),
              r('wait', seconds=1.0), r('type', value='canon'), r('key', key='Return'), r('wait', seconds=1.5)],
             [tags('The tag list has canon and no classic.'),
              items(f'{U}/items?tag=canon', 'unordered:fields:title', 'The items formerly tagged classic are tagged canon.',
                    'tagged')]),
        step('delete', 'Delete the tag "chess" from the library.',
             'The tag chess is no longer listed in the tag selector.',
             [LIB, r('context', target={'role': 'check box', 'name': 'chess'}, path=['Delete Tag…']),
              r('confirm', button='OK'), r('wait', seconds=1.5)],
             [tags('The tag list no longer has chess.'),
              item('Computer Beats Champion in Chess Rematch', 'tags', 'The formerly tagged item lost the tag.')], depends=['rename']),
    ], libraries=['query']))

    k = 'tags-color'
    flows.append(episode(k, 'tags', [
        step('color', 'Assign a color to the tag "genetics", in the first color position.',
             'The tag genetics is shown colored (at the top of the tag selector), and items tagged genetics show the '
             'color in the item list.',
             [LIB, r('context', target={'role': 'check box', 'name': 'genetics'}, path=['Assign Color…']),
              r('window', title='Choose a Tag Color'), r('click', target={'role': 'push button', 'name': 'Set Color'}),
              r('wait', seconds=1.0)]),
        step('apply', 'With the item "Algorithms" selected, add the colored tag to it using the colored tag\'s '
                      'keyboard shortcut (the key of its position, 1).',
             'The item Algorithms now shows the colored genetics tag.',
             [LIB, select('Algorithms'), r('key', key='1'), r('wait', seconds=1.0)],
             [item('Algorithms', 'tags', 'Algorithms gained the genetics tag.')], depends=['color']),
    ], libraries=['query']))

    k = 'tags-filter'
    flows.append(episode(k, 'tags', [
        step('select', 'In My Library, show only the items tagged "classic" by selecting that tag in the tag '
                       'selector.',
             'Only the items with the tag classic are listed (The Art of Computer Programming, On Computable Numbers, '
             'As We May Think, The Origin of Species, Molecular Structure of Nucleic Acids, Letter to the Editor on '
             'Goto Statements).',
             [LIB, r('click', target={'role': 'check box', 'name': 'classic'}), r('wait', seconds=1.0)]),
        step('two-tags', 'Select the tag "genetics" as well, keeping "classic" selected.',
             'Only items that have both tags are listed: Molecular Structure of Nucleic Acids.',
             [r('click', target={'role': 'check box', 'name': 'genetics'}), r('wait', seconds=1.0)],
             depends=['select']),
        step('filter', 'Deselect both tags, then type "gen" into the tag selector\'s filter field.',
             'All items are listed again, and the tag selector shows only the tags containing gen (artificial '
             'intelligence and genetics).',
             [r('click', target={'role': 'check box', 'name': 'genetics'}),
              r('click', target={'role': 'check box', 'name': 'classic'}), r('wait', seconds=0.5),
              r('click', target={'role': 'entry', 'name': 'Filter Tags'}), r('type', value='gen'),
              r('wait', seconds=1.0)], depends=['two-tags']),
    ], libraries=['query']))

    k = 'tags-automatic'
    base = [obj(31, 'journalArticle', 'Coral Reef Survey', [('author', 'Sylvia', 'Earle')], date='2001',
                tags=[{'tag': 'oceans'}, {'tag': 'coral', 'type': 1}]),
            obj(32, 'journalArticle', 'Deep Sea Vents', [('author', 'Robert', 'Ballard')], date='1977',
                tags=[{'tag': 'oceans'}, {'tag': 'geology', 'type': 1}]),
            obj(33, 'book', 'Kelp Forests', [('author', 'Paul', 'Dayton')], date='1985',
                tags=[{'tag': 'ecology', 'type': 1}])]
    flows.append(episode(k, 'tags', [
        step('hide', 'Make the tag selector stop showing automatically added tags.',
             'The tag selector lists only the manual tag oceans; coral, geology and ecology are no longer shown.',
             [LIB, r('click', target={'role': 'push button', 'name': 'Actions'}),
              r('click', target={'role': 'check menu item', 'name': 'Show Automatic'}), r('wait', seconds=1.0)],
             [item('Coral Reef Survey', 'tags', 'Hiding automatic tags preserves them.', aspect='automatic-kept')],
             requires={'automatic-kept': ['visible']}),
        step('show', 'Show automatically added tags in the tag selector again.',
             'The tag selector lists coral, geology and ecology again, alongside oceans.',
             [r('click', target={'role': 'push button', 'name': 'Actions'}),
              r('click', target={'role': 'check menu item', 'name': 'Show Automatic'}), r('wait', seconds=1.0)],
             depends=['hide']),
        step('delete', 'Delete all automatically added tags of the library with the tag selector\'s command for '
                       'that.',
             'With automatic tags shown, the tag selector lists only oceans.',
             [r('click', target={'role': 'push button', 'name': 'Actions'}),
              r('click', target={'role': 'check menu item', 'name': 'Delete Automatic Tags in This Library…'}),
              r('confirm', button='OK'), r('wait', seconds=1.0)],
             [tags('The library\'s only tag is oceans.'),
              item('Coral Reef Survey', 'tags', 'Coral Reef Survey keeps only its manual tag.'),
              item('Kelp Forests', 'tags', 'Kelp Forests has no tags left.')]),
    ], objects={'items': base}))
    return flows


# ------------------------------------------------------------------------------------------------- search
def search_items(name, description, aspect='results', fields='title'):
    return {'description': description, 'aspect': aspect, 'check': {'steps': [
        find(name, [], field='name', path=f'{U}/searches'),
        {'method': 'GET', 'path': U + '/searches/{found}/items',
         'view': [('' if 'note' in fields else 'top:') + f'unordered:fields:{fields}']}]}}


def saved_search(name, description, aspect='search'):
    return {'description': description, 'aspect': aspect,
            'check': {'steps': [find(name, 'fields:name,conditions', field='name', path=f'{U}/searches')]}}


def advanced_search(result_type=None, match=None):
    steps = [r('click', target={'role': 'push button', 'name': 'Advanced Search'}), r('wait', seconds=1.0)]
    if result_type:
        steps += [r('click', target={'role': 'combo box', 'name': 'Result type'}),
                  r('click', target={'role': 'menu item', 'name': result_type}), r('wait', seconds=0.5)]
    if match:
        steps += [r('click', target={'role': 'combo box', 'name': 'Match'}),
                  r('click', target={'role': 'menu item', 'name': match}), r('wait', seconds=0.5)]
    return steps


def save_search(name):
    return [r('click', target={'role': 'push button', 'name': 'Save Search…'}), r('wait', seconds=1.0),
            r('type', value=name), r('key', key='Return'), r('wait', seconds=1.5), r('collection', name=name)]


def search_episodes():
    flows = []
    k = 'search-quick'
    flows.append(episode(k, 'search', [
        step('creator', 'In My Library, use the quick search to find items matching "Dijkstra".',
             'The list shows the Dijkstra items (A Note on Two Problems in Connexion with Graphs, Notes on Structured '
             'Programming, Letter to the Editor on Goto Statements) and no unrelated items.',
             [LIB, r('click', target={'role': 'entry', 'name': 'Quick Search'}), r('type', value='Dijkstra'),
              r('key', key='Return'), r('wait', seconds=1.5)]),
        step('everything', 'Use the quick search mode that includes attachment full text, and search for "lazy dog".',
             'Reading Practice is found through the text of its PDF attachment; unrelated items are not listed.',
             [r('click', target={'role': 'push button', 'name': 'Quick Search mode'}),
              r('click', target={'role': 'radio menu item', 'name': 'Everything'}), r('wait', seconds=0.5),
              r('click', target={'role': 'entry', 'name': 'Quick Search'}), r('key', key='Control+a'),
              r('type', value='lazy dog'), r('key', key='Return'), r('wait', seconds=1.5)], depends=['creator']),
    ], libraries=['query'], objects={'items': READER_ITEMS, 'files': [
        {'key': K('GA', 1), 'name': 'reader.pdf', 'fulltext': 'The quick brown fox jumps over the lazy dog.'}]}))

    k = 'search-advanced-save'
    flows.append(episode(k, 'search', [
        step('search', 'Open the advanced search, and find the items whose creator contains "Dijkstra" and whose '
                       'item type is not Letter.',
             'The search results show A Note on Two Problems in Connexion with Graphs and Notes on Structured '
             'Programming, but not the letter.',
             [LIB, r('click', target={'role': 'push button', 'name': 'Advanced Search'}), r('wait', seconds=1.0),
              r('condition', row=0, condition='Creator', operator='contains', value='Dijkstra'),
              r('click', target={'role': 'push button', 'name': 'Add Condition'}), r('wait', seconds=0.5),
              r('condition', row=1, condition='Item Type', operator='is not', choice='Letter'),
              r('click', target={'role': 'push button', 'name': 'Search'}), r('wait', seconds=1.5)]),
        step('save', 'Save this search under the name "Dijkstra papers".',
             'A saved search Dijkstra papers is listed in the collections pane; opening it lists the same two items.',
             [r('click', target={'role': 'push button', 'name': 'Save Search…'}), r('wait', seconds=1.0),
              r('type', value='Dijkstra papers'), r('key', key='Return'), r('wait', seconds=1.5),
              r('collection', name='Dijkstra papers')],
             [search_items('Dijkstra papers', 'The saved search finds the two items.')], depends=['search']),
    ], libraries=['query']))

    k = 'search-saved-edit'
    saved = [{'key': K('GS', 1), 'version': 0, 'name': 'Classic works',
              'conditions': [{'condition': 'tag', 'operator': 'is', 'value': 'classic'}]}]
    flows.append(episode(k, 'search', [
        step('edit', 'Edit the saved search "Classic works": rename it to "Genetics works" and make it find items '
                     'tagged "genetics" instead of "classic".',
             'The saved search is listed as Genetics works, and opening it lists the items tagged genetics '
             '(Evolutionary Dynamics of Small Populations, Molecular Structure of Nucleic Acids).',
             [r('context', target={'collection': 'Classic works'}, path=['Edit Search']),
              r('wait', seconds=1.5), r('fill', target={'role': 'entry', 'name': 'Name:'}, value='Genetics works'),
              r('fill', target={'role': 'entry', 'name': 'Value'}, value='genetics'), r('key', key='Escape'),
              r('click', target={'role': 'push button', 'name': 'Save'}), r('wait', seconds=1.5),
              r('collection', name='Genetics works'), LIB, r('collection', name='Genetics works')],
             [search_items('Genetics works', 'The renamed search finds the genetics items.')]),
        step('delete', 'Delete the saved search "Genetics works" (the items themselves stay).',
             'Genetics works is no longer listed in the collections pane, and My Library lists Molecular Structure of Nucleic Acids.',
             [r('context', target={'collection': 'Genetics works'}, path=['Delete Search…']),
              r('confirm', button='Delete Search'), r('wait', seconds=1.0), LIB],
             [{'description': 'The saved search is moved to the trash.', 'aspect': 'searches',
               'check': {'steps': [find('Genetics works', 'fields:name,deleted', field='name',
                                        path=f'{U}/searches')]}},
              item('Molecular Structure of Nucleic Acids', 'title,deleted', 'The items are not deleted.')],
             depends=['edit'], requires={'visible': ['searches', 'item-molecular-structure-of-nucleic-acids']}),
    ], libraries=['query'], objects={'searches': saved}))

    k = 'search-result-types'
    flows.append(episode(k, 'search', [
        step('notes', 'With the advanced search, find the notes (not the items) whose text contains "model", and save '
                      'the search as "Model notes".',
             'A saved search Model notes is listed, and it finds the note about the double helix model.',
             [LIB, *advanced_search(result_type='notes'),
              r('condition', row=0, condition='Note', operator='contains', value='model'),
              r('click', target={'role': 'push button', 'name': 'Search'}), r('wait', seconds=1.5),
              *save_search('Model notes')],
             [saved_search('Model notes', 'The saved search keeps the result type and the note condition.'),
              search_items('Model notes', 'The saved search finds the note.', fields='itemType,note,parentItem')]),
        step('any', 'With a new advanced search for top-level items, find the items whose title contains "Programming" '
                    'or whose tag is exactly "genetics" (either condition is enough), and save it as "Programming or '
                    'genetics".',
             'A saved search Programming or genetics is listed; it finds the items with Programming in the title '
             '(for example Notes on Structured Programming) and those tagged genetics.',
             [LIB, *advanced_search(result_type='top-level items', match='any'),
              r('condition', row=0, condition='Title', operator='contains', value='Programming'),
              r('click', target={'role': 'push button', 'name': 'Add Condition'}), r('wait', seconds=0.5),
              r('condition', row=1, condition='Tag', operator='is', value='genetics'),
              r('click', target={'role': 'push button', 'name': 'Search'}), r('wait', seconds=1.5),
              *save_search('Programming or genetics')],
             [saved_search('Programming or genetics', 'The saved search matches any of its two conditions.'),
              search_items('Programming or genetics', 'The saved search finds the items of either condition.')]),
    ], libraries=['query']))
    return flows


# ------------------------------------------------------------------------------------------------- export
def exported(key, filename, reader, aspects):
    """Aspects of one exported file: (aspect, description, select path) each."""
    shared = {'steps': [{'kind': 'download', 'filename': filename, 'view': [f'format:{reader}']}]}
    return [{'description': description, 'aspect': aspect,
             'check': {'share': filename, 'shared': shared, 'select': [0] + list(select)}}
            for aspect, description, select in aspects]


def export_dialog(fmt, path, notes=None):
    steps = [r('window', title='Export…'), r('click', target={'role': 'combo box', 'name': 'Format:'}),
             r('click', target={'role': 'menu item', 'name': fmt}), r('wait', seconds=0.5)]
    if notes is not None:
        steps.append(r('check', target={'role': 'check box', 'name': 'Export Notes'}, checked=notes))
    steps += [r('click', target={'role': 'push button', 'name': 'OK'}), r('save-file', path=path), r('wait', seconds=1.5)]
    return steps


SMALL = [obj(40, 'book', 'The Mythical Man-Month', [('author', 'Frederick', 'Brooks')], date='1975',
             publisher='Addison-Wesley', place='Reading, MA', tags=[{'tag': 'software'}]),
         obj(41, 'journalArticle', 'Go To Statement Considered Harmful', [('author', 'Edsger', 'Dijkstra')],
             date='1968-03', publicationTitle='Communications of the ACM', volume='11', issue='3', pages='147-148',
             DOI='10.1145/362929.362947'),
         obj(42, 'thesis', 'A Symbolic Analysis of Relay and Switching Circuits', [('author', 'Claude', 'Shannon')],
             date='1940', university='Massachusetts Institute of Technology', thesisType='Master\'s thesis')]
SOFTWARE = obj(43, 'computerProgram', 'Example Sorter', [('programmer', 'Margaret', 'Hamilton')], date='2022-05-01',
               versionNumber='2.1.0', company='Example Labs', programmingLanguage='Python',
               url='https://example.org/sorter', abstractNote='A small library of sorting routines.')
SMALL_NOTES = [{'key': K('GN', 1), 'version': 0, 'itemType': 'note', 'parentItem': K('GI', 41),
                'note': '<p>The original letter to the editor.</p>'}]


def export_episodes():
    flows = []
    k = 'export-library-bibtex'
    flows.append(episode(k, 'export', [
        step('export', f'Export the whole library in BibTeX format to the file {outbox(k)}/library.bib.',
             'The export finishes without an error message.',
             [LIB, r('menu', path=['File', 'Export Library…']), *export_dialog('BibTeX', 'outbox/library.bib')],
             exported(k, 'library.bib', 'bibtex', [
                 ('keys', 'The file holds one entry per item, with the generated citation keys.',
                  [{'map': 'key'}, 'sorted']),
                 ('book', 'The book entry carries its fields.', [{'where': {'type': 'book'}}, 'fields']),
                 ('article', 'The article entry carries its fields.', [{'where': {'type': 'article'}}, 'fields']),
                 ('thesis', 'The master\'s thesis entry carries its fields.',
                  [{'where': {'type': 'mastersthesis'}}, 'fields'])]),
             requires={'visible': ['keys']}),
    ], objects={'items': SMALL}))

    k = 'export-collection-ris'
    flows.append(episode(k, 'export', [
        step('export', f'Export the collection "Biology" in RIS format to the file {outbox(k)}/biology.ris.',
             'The export finishes without an error message.',
             [r('context', target={'collection': 'Biology'}, path=['Export…']),
              *export_dialog('RIS', 'outbox/biology.ris')],
             exported(k, 'biology.ris', 'ris', [
                 ('titles', 'The file holds one record per item of Biology.', [{'map': 'TI'}, 'sorted']),
                 ('article', 'The DNA article record carries its fields.',
                  [{'where': {'TI': ['Molecular Structure of Nucleic Acids']}}]),
                 ('thesis', 'The thesis record carries its fields.',
                  [{'where': {'TI': ['Evolutionary Dynamics of Small Populations']}}]),
                 ('report', 'The report with an institutional author carries its fields.',
                  [{'where': {'TI': ['Global Health Statistics']}}])]),
             requires={'visible': ['titles']}),
    ], libraries=['query']))

    k = 'export-items-csljson'
    flows.append(episode(k, 'export', [
        step('export', 'Select the items "The Mythical Man-Month" and "Go To Statement Considered Harmful" together '
                       f'and export just these two items as CSL JSON to the file {outbox(k)}/selected.json.',
             'Both items are shown selected and the export finishes without an error message.',
             [LIB, select('The Mythical Man-Month'), r('item', title='Go To Statement Considered Harmful',
                                                        modifiers=['Control']),
              r('context', target={'item': 'Go To Statement Considered Harmful'},
                path=['Export Items…']),
              *export_dialog('CSL JSON', 'outbox/selected.json')],
             exported(k, 'selected.json', 'csljson', [
                 ('titles', 'The file holds exactly the two selected items.', [{'map': 'title'}, 'sorted']),
                 ('book', 'The book is exported with its CSL fields.', [{'where': {'title': 'The Mythical Man-Month'}}]),
                 ('article', 'The article is exported with its CSL fields.',
                  [{'where': {'title': 'Go To Statement Considered Harmful'}}])]),
             requires={'visible': ['titles']}),
    ], objects={'items': SMALL}))

    k = 'export-rdf-notes'
    flows.append(episode(k, 'export', [
        step('export', f'Export the whole library as Zotero RDF, including notes, to the file {outbox(k)}/library.rdf.',
             'The export finishes without an error message.',
             [LIB, r('menu', path=['File', 'Export Library…']),
              *export_dialog('Zotero RDF', 'outbox/library.rdf', notes=True)],
             [{'description': 'The RDF document describes the items, their creators and the note.', 'aspect': 'rdf',
               'check': {'steps': [{'kind': 'download', 'filename': 'library.rdf', 'view': ['format:rdf_zotero']}]}}]),
    ], objects={'items': SMALL, 'children': SMALL_NOTES}))

    k = 'export-cff-endnote'
    flows.append(episode(k, 'export', [
        step('cff', f'Export the whole library in the CFF format to the file {outbox(k)}/citation.cff.',
             'The export finishes without an error message.',
             [LIB, r('menu', path=['File', 'Export Library…']), *export_dialog('CFF', 'outbox/citation.cff')],
             [{'description': 'The CFF document describes the software item with its fields.', 'aspect': 'cff',
               'check': {'steps': [{'kind': 'download', 'filename': 'citation.cff', 'view': ['format:text']}]}}]),
        step('endnote', f'Export the whole library as Endnote XML to the file {outbox(k)}/library.xml.',
             'The export finishes without an error message.',
             [LIB, r('menu', path=['File', 'Export Library…']), *export_dialog('Endnote XML', 'outbox/library.xml')],
             exported(k, 'library.xml', 'xml', [
                 ('endnote', 'The Endnote XML document holds one record per item with its fields.',
                  [3, 0, 3, 'sorted'])])),
    ], objects={'items': SMALL + [SOFTWARE]}))
    return flows


# ------------------------------------------------------------------------------------------------- import
def import_file(path, new_collection=True):
    steps = [LIB, r('menu', path=['File', 'Import…']), r('window', title='Import'),
             r('click', target={'role': 'push button', 'name': 'Next'}), r('open-file', path=path),
             r('wait', seconds=1.0)]
    steps.append(r('check', target={'role': 'check box', 'name': 'Place imported collections and items into new '
                                                                 'collection'}, checked=new_collection))
    steps += [r('click', target={'role': 'push button', 'name': 'Next'}), r('wait', seconds=2.0),
              r('click', target={'role': 'push button', 'name': 'Finish'}), r('wait', seconds=1.0)]
    return steps


def imported(title, fields, description, aspect):
    return item(title, fields, description, aspect=aspect)


IMPORT_FIELDS = 'itemType,title,creators,date,publisher,place,publicationTitle,volume,issue,pages,DOI,ISBN,tags'


def import_episodes():
    flows = []
    k = 'import-bibtex'
    flows.append(episode(k, 'import', [
        step('import', f'Import the BibTeX file {inbox(k)}/references.bib into a new collection.',
             'A new collection named after the file (references) lists the five imported items, among them The Art of '
             'Computer Programming and A Mathematical Theory of Communication.',
             import_file('inbox/references.bib', True),
             [collection('references', 'name,parentCollection', 'The import created the collection references.'),
              imported('The Art of Computer Programming', IMPORT_FIELDS, 'The book entry became a Book.', 'book'),
              imported('A Mathematical Theory of Communication', IMPORT_FIELDS, 'The article became a Journal Article.',
                       'article'),
              imported('Time, Clocks, and the Ordering of Events in a Distributed System', IMPORT_FIELDS,
                       'The inproceedings entry became a Conference Paper.', 'conference'),
              imported('Über die Bildung des Formensystems der ternären biquadratischen Form',
                       'itemType,title,creators,date,university,thesisType', 'LaTeX accents are decoded in the thesis.',
                       'thesis'),
              imported('An Example Dataset', 'itemType,title,creators,date,url,extra', 'The misc entry is imported.',
                       'misc')]),
    ], files=['references.bib']))

    k = 'import-ris'
    flows.append(episode(k, 'import', [
        step('import', f'Import the RIS file {inbox(k)}/references.ris directly into My Library, without creating a '
                       'new collection.',
             'The three imported items (Cramming More Components onto Integrated Circuits, Silent Spring and The '
             'Humble Programmer) are listed in My Library and no new collection was created.',
             import_file('inbox/references.ris', False),
             [imported('Cramming More Components onto Integrated Circuits', IMPORT_FIELDS + ',collections',
                       'The journal record is imported.', 'article'),
              imported('Silent Spring', IMPORT_FIELDS + ',collections', 'The book record is imported.', 'book'),
              imported('The Humble Programmer', IMPORT_FIELDS + ',bookTitle,collections',
                       'The chapter record is imported as a Book Section.', 'section'),
              collection_tree('No collection was created.')]),
    ], files=['references.ris']))

    k = 'import-csljson-mods'
    flows.append(episode(k, 'import', [
        step('csljson', f'Import the CSL JSON file {inbox(k)}/references.json into a new collection.',
             'A new collection references lists the three imported items, among them Cybernetics.',
             import_file('inbox/references.json', True),
             [imported('The Mathematical Theory of Games', IMPORT_FIELDS, 'The article is imported.', 'article'),
              imported('Cybernetics', IMPORT_FIELDS, 'The book is imported.', 'book'),
              imported('Example Domain', 'itemType,title,url,accessDate,websiteTitle', 'The web page is imported.',
                       'webpage'), collection_items('references', 'The three imported items belong to references.')]),
        step('mods', f'Import the MODS file {inbox(k)}/mods.xml into a new collection.',
             'A new collection mods lists the imported book Weaving the Web by Berners-Lee.',
             import_file('inbox/mods.xml', True),
             [imported('Weaving the Web', IMPORT_FIELDS.replace(',ISBN', ''), 'The MODS record is imported as a Book.', 'book'),
              collection('mods', 'name,parentCollection', 'The import created the collection mods.')]),
    ], files=['references.json', 'mods.xml']))

    k = 'import-medline-refer'
    flows.append(episode(k, 'import', [
        step('medline', f'Import the PubMed/MEDLINE file {inbox(k)}/pubmed.nbib into My Library without a new '
                        'collection.',
             'The article Example of a MEDLINE record about sleep and memory is listed with the authors Walker and '
             'Stickgold.',
             import_file('inbox/pubmed.nbib', False),
             [imported('Example of a MEDLINE record about sleep and memory.', IMPORT_FIELDS + ',abstractNote,extra,'
                       'journalAbbreviation,language,collections', 'The MEDLINE record is imported with its fields.', 'article')]),
        step('refer', f'Import the Refer/BibIX file {inbox(k)}/references.txt into My Library without a new '
                      'collection.',
             'The items Computing Machinery and Intelligence and The Mythical Man-Month are listed.',
             import_file('inbox/references.txt', False),
             [imported('Computing Machinery and Intelligence', IMPORT_FIELDS + ',collections', 'The journal record is imported.',
                       'article'),
              imported('The Mythical Man-Month', IMPORT_FIELDS + ',collections', 'The book record is imported.', 'book')]),
    ], files=['pubmed.nbib', 'references.txt']))
    return flows


# ---------------------------------------------------------------------------------------------- citations
def bibliography_dialog(style, mode=None, method='Copy to Clipboard', path=None):
    steps = [r('window', title='Zotero - Create Citation/Bibliography'),
             r('choose', name=style), r('wait', seconds=0.5)]
    if mode:
        steps.append(r('click', target={'role': 'radio button', 'name': mode}))
    steps += [r('click', target={'role': 'radio button', 'name': method}),
              r('click', target={'role': 'push button', 'name': 'OK'}), r('wait', seconds=1.5)]
    if path:
        steps += [r('save-file', path=path), r('wait', seconds=1.0)]
    return steps


def clipboard(target, reader, description, aspect):
    return {'description': description, 'aspect': aspect,
            'check': {'steps': [{'kind': 'clipboard', 'target': target, 'view': [f'format:{reader}']}]}}


APA = 'APA Style 7th edition'
CHICAGO_AD = 'Chicago Manual of Style 18th edition (author-date)'
IEEE = 'IEEE Reference Guide version 11.29.2023'


def select_small():
    return [LIB, select('Go To Statement Considered Harmful'), r('key', key='Control+a'), r('wait', seconds=0.5)]


def citation_episodes():
    flows = []
    k = 'bibliography-rtf'
    flows.append(episode(k, 'citation', [
        step('rtf', 'Select all items in My Library and create a bibliography from them in the APA Style 7th '
                    f'edition, saved as RTF to the file {outbox(k)}/bibliography.rtf.',
             'The bibliography dialog closes without an error message after saving.',
             [*select_small(), r('context', target={'item': 'Go To Statement Considered Harmful'},
                                 path=['Create Bibliography from Items…']),
              *bibliography_dialog(APA, method='Save as RTF', path='outbox/bibliography.rtf')],
             [{'description': 'The RTF document holds the three APA entries in order.', 'aspect': 'rtf',
               'check': {'steps': [{'kind': 'download', 'filename': 'bibliography.rtf', 'view': ['format:rtf']}]}}]),
    ], objects={'items': SMALL}))

    k = 'bibliography-html'
    flows.append(episode(k, 'citation', [
        step('html', 'Select all items in My Library and create citations (not a bibliography) from them in the '
                     'Chicago Manual of Style 18th edition (author-date), saved as HTML to the file '
                     f'{outbox(k)}/citations.html.',
             'The dialog closes without an error message after saving.',
             [*select_small(), r('context', target={'item': 'Go To Statement Considered Harmful'},
                                 path=['Create Bibliography from Items…']),
              *bibliography_dialog(CHICAGO_AD, mode='Citations', method='Save as HTML', path='outbox/citations.html')],
             [{'description': 'The HTML document holds the three author-date citations.', 'aspect': 'html',
               'check': {'steps': [{'kind': 'download', 'filename': 'citations.html', 'view': ['format:html-text']}]}}]),
    ], objects={'items': SMALL}))

    k = 'bibliography-clipboard'
    flows.append(episode(k, 'citation', [
        step('copy', 'Create a bibliography of the item "Go To Statement Considered Harmful" in the IEEE style and '
                     'copy it to the clipboard.',
             'The dialog closes without an error message.',
             [LIB, r('context', target={'item': 'Go To Statement Considered Harmful'},
                     path=['Create Bibliography from Item…']), *bibliography_dialog(IEEE)],
             [clipboard('text', 'text', 'The clipboard holds the IEEE entry as text.', 'text'),
              clipboard('html', 'bib', 'The clipboard holds the IEEE entry as HTML.', 'html')]),
    ], objects={'items': SMALL}))

    k = 'quick-copy'
    flows.append(episode(k, 'citation', [
        step('bibliography', 'Copy the bibliography entry of "The Mythical Man-Month" to the clipboard with the '
                             'quick copy command (in the default format).',
             'The item "The Mythical Man-Month" is selected; the copy command gives no error.',
             [LIB, select('The Mythical Man-Month'), r('key', key='Control+Shift+c'), r('wait', seconds=1.5)],
             [clipboard('text', 'text', 'The clipboard holds the default-style bibliography entry.', 'text')]),
        step('citation', 'Copy the citation of "The Mythical Man-Month" to the clipboard with the quick copy command.',
             'The item is selected; the copy command gives no error.',
             [LIB, select('The Mythical Man-Month'), r('key', key='Control+Shift+a'), r('wait', seconds=1.5)],
             [clipboard('text', 'text', 'The clipboard holds the default-style citation.', 'text')]),
        step('format', 'Set the quick copy item format to APA Style 7th edition in the application settings.',
             'The quick copy format setting shows APA Style 7th edition.',
             [r('menu', path=['Edit', 'Settings']), r('window', title='Zotero Settings'),
              r('click', target={'role': 'list item', 'name': 'Export'}), r('wait', seconds=1.0),
              r('click', target={'role': 'combo box', 'name': 'Item Format:'}),
              r('click', target={'role': 'menu item', 'name': APA}), r('wait', seconds=1.0)]),
        step('setting', 'With the selected quick copy format, copy the bibliography entry of "The Mythical '
                        'Man-Month" to the clipboard.',
             'The Mythical Man-Month is selected and the copy command finishes without an error.',
             [r('key', key='Control+w'), r('wait', seconds=1.0), LIB, select('The Mythical Man-Month'),
              r('key', key='Control+Shift+c'), r('wait', seconds=1.5)],
             [clipboard('text', 'text', 'The clipboard holds the APA bibliography entry.', 'text')], depends=['format']),
    ], objects={'items': SMALL}))

    k = 'rtf-scan'
    flows.append(episode(k, 'citation', [
        step('scan', f'Use the application\'s RTF Scan tool on {inbox(k)}/scan.rtf, writing the result to '
                     f'{outbox(k)}/scanned.rtf, with the citations formatted in APA Style 7th edition.',
             'The RTF Scan reports that it is complete.',
             [LIB, r('menu', path=['Tools', 'RTF Scan']), r('window', title='RTF Scan'),
              r('click', target={'role': 'push button', 'name': 'Choose Input File'}), r('open-file', path='inbox/scan.rtf'),
              r('click', target={'role': 'push button', 'name': 'Choose Output File'}),
              r('save-file', path='outbox/scanned.rtf'), r('click', target={'role': 'push button', 'name': 'Next'}),
              r('wait', seconds=2.0), r('click', target={'role': 'push button', 'name': 'Next'}), r('wait', seconds=1.5),
              r('choose', name=APA),
              r('click', target={'role': 'push button', 'name': 'Next'}), r('wait', seconds=3.0)],
             [{'description': 'The output replaces the markers with APA citations and adds the bibliography.',
               'aspect': 'rtf', 'check': {'steps': [{'kind': 'download', 'filename': 'scanned.rtf',
                                                     'view': ['format:rtf']}]}}]),
    ], libraries=['query'], files=['scan.rtf']))

    k = 'report'
    flows.append(episode(k, 'citation', [
        step('report', 'Generate a report from the item "Notes on Structured Programming".',
             'A report of Notes on Structured Programming is shown, listing its item type, authors and editors, '
             'book title, publisher, place, date and pages.',
             [LIB, r('context', target={'item': 'Notes on Structured Programming'},
                     path=['Generate Report from Item…']), r('wait', seconds=3.0)]),
    ], libraries=['query']))
    return flows


# -------------------------------------------------------------------------------------------- attachments
READER_ITEMS = [obj(50, 'book', 'Reading Practice', [('author', 'Ada', 'Lovelace')], date='2019'),
                {'key': K('GA', 1), 'version': 0, 'itemType': 'attachment', 'parentItem': K('GI', 50),
                 'linkMode': 'imported_file', 'title': 'Full Text PDF', 'contentType': 'application/pdf',
                 'filename': 'reader.pdf'}]


def annotations(description, aspect='annotations'):
    return {'description': description, 'aspect': aspect, 'check': {'steps': [
        {'method': 'GET', 'path': U + '/items?itemType=annotation',
         'view': ['unordered:fields:parentItem,annotationType,annotationText,annotationComment,annotationColor,'
                  'annotationPageLabel,tags']}]}}


def attachment_episodes():
    flows = []
    k = 'attach-file'
    base = [obj(60, 'journalArticle', 'Quantum Gardening', [('author', 'Ada', 'Lovelace')], date='2019')]
    flows.append(episode(k, 'attachments', [
        step('attach', f'Attach a stored copy of the file {inbox(k)}/paper.pdf to the item "Quantum Gardening".',
             'Quantum Gardening has a PDF attachment listed under it.',
             [LIB, r('context', target={'item': 'Quantum Gardening'}, path=['Add Attachment', 'File']),
              r('open-file', path='inbox/paper.pdf'), r('wait', seconds=2.0)],
             [children('Quantum Gardening', 'itemType,title,linkMode,contentType,filename,md5',
                       'The stored copy is a PDF attachment, renamed after its parent.')]),
    ], objects={'items': base}, files=['paper.pdf']))

    k = 'attach-link-file'
    flows.append(episode(k, 'attachments', [
        step('link', f'Attach a link to the file {inbox(k)}/notes.pdf (not a stored copy) to the item "Quantum '
                     'Gardening".',
             'Quantum Gardening has a linked file attachment listed under it.',
             [LIB, r('context', target={'item': 'Quantum Gardening'},
                     path=['Add Attachment', 'Linked File']), r('open-file', path='inbox/notes.pdf'),
              r('wait', seconds=2.0)],
             [children('Quantum Gardening', 'itemType,title,linkMode,contentType,path',
                       'The attachment links to the file in the inbox.')]),
        step('convert', 'Convert that linked file into a stored copy with the application\'s command for that, '
                        'keeping the original file.',
             'The attachment of Quantum Gardening is now shown as a stored file.',
             [LIB, r('open-child', title='Quantum Gardening', child='PDF'),
              r('menu', path=['Tools', 'Manage Attachments', 'Convert Linked Files to Stored Files…']),
              r('confirm', button='Continue'), r('wait', seconds=1.5)],
             [children('Quantum Gardening', 'itemType,title,linkMode,contentType,filename,path,md5',
                       'The attachment is a stored file with the same content.'),
              {'description': 'The original inbox file remains with its original bytes.', 'aspect': 'original-file',
               'check': {'steps': [{'kind': 'download', 'area': 'inbox', 'filename': 'notes.pdf',
                                    'binary': True, 'view': ['sha256']}]}}], depends=['link']),
    ], objects={'items': base}, files=['notes.pdf']))

    k = 'attach-web-link'
    flows.append(episode(k, 'attachments', [
        step('link', 'Attach the web link "https://example.org/quantum" titled "Project page" to the item '
                     '"Quantum Gardening".',
             'Quantum Gardening has a link attachment titled Project page listed under it.',
             [LIB, r('context', target={'item': 'Quantum Gardening'},
                     path=['Add Attachment', 'Web Link']), r('window', title='Attach Link to URI'),
              r('type', value='https://example.org/quantum'),
              r('fill', target={'role': 'entry', 'name': 'Title:'}, value='Project page'),
              r('click', target={'role': 'push button', 'name': 'OK'}), r('wait', seconds=1.5)],
             [children('Quantum Gardening', 'itemType,title,linkMode,url', 'The link attachment keeps its URL and title.')]),
    ], objects={'items': base}))

    k = 'attach-standalone-parent'
    flows.append(episode(k, 'attachments', [
        step('add', f'In My Library, add the file {inbox(k)}/paper.pdf as a standalone stored file (not attached '
                    'to any item).',
             'The PDF is listed in My Library as an item of its own.',
             [LIB, r('click', target={'role': 'push button', 'name': 'Add Attachment'}),
              r('click', target={'role': 'menu item', 'name': 'Add File…'}), r('open-file', path='inbox/paper.pdf'),
              r('wait', seconds=2.0)],
             [items(f'{U}/items/top?itemType=attachment', 'unordered:fields:title,linkMode,contentType,filename,parentItem',
                    'A standalone PDF attachment exists.', 'standalone')]),
        step('parent', 'Create a parent item for that PDF by manual entry (without looking up an identifier), and '
                       'set the new parent item\'s title to "Quantum Gardening Notes".',
             'An item Quantum Gardening Notes is listed with the PDF as its child attachment.',
             [LIB, r('context', target={'item': 'paper. Attachment.'}, path=['Create Parent Item…']),
              r('window', title='Create Parent Item'), r('click', target={'role': 'push button', 'name': 'Manual Entry'}),
              r('wait', seconds=2.0), field('Title', 'Quantum Gardening Notes'),
              select('Quantum Gardening Notes'), r('key', key='Right'), r('wait', seconds=0.5)],
             [item('Quantum Gardening Notes', 'itemType,title', 'The manual parent item exists with the title.'),
              children('Quantum Gardening Notes', 'itemType,title,linkMode,filename',
                       'The PDF is the child of the new item.')], depends=['add']),
    ], files=['paper.pdf']))

    k = 'attach-rename'
    base = [obj(61, 'book', 'Field Notes', [('author', 'Rachel', 'Carson')], date='1950'),
            {'key': K('GA', 2), 'version': 0, 'itemType': 'attachment', 'parentItem': K('GI', 61),
             'linkMode': 'imported_file', 'title': 'Scan', 'contentType': 'application/pdf', 'filename': 'notes.pdf'}]
    flows.append(episode(k, 'attachments', [
        step('rename', 'Change the title of "Field Notes" to "Field Notes from Maine", then rename the file of its '
                       'PDF attachment from the parent\'s metadata.',
             'The parent is titled Field Notes from Maine and its attachment\'s file name follows the parent\'s '
             'creator, year and title.',
             [LIB, select('Field Notes'), field('Title', 'Field Notes from Maine'), r('wait', seconds=1.0),
              r('open-child', title='Field Notes from Maine', child='Scan'),
              r('click', target={'role': 'push button', 'name': 'Rename File to Match Parent Item'}),
              r('wait', seconds=1.5)],
             [children('Field Notes from Maine', 'title,filename,md5', 'The attachment file is renamed.')]),
    ], objects={'items': base, 'files': [{'key': K('GA', 2), 'name': 'notes.pdf'}]}))

    k = 'attach-titles'
    base = [obj(62, 'book', 'Garden Plans', [('author', 'Gertrude', 'Jekyll')], date='1908'),
            obj(63, 'book', 'Pond Notes', [('author', 'Henry', 'Thoreau')], date='1854'),
            obj(66, 'book', 'Wetland Maps', date='1900'),
            {'key': K('GA', 7), 'version': 0, 'itemType': 'attachment', 'parentItem': K('GI', 66),
             'linkMode': 'imported_file', 'title': 'notes.pdf', 'filename': 'notes.pdf',
             'contentType': 'application/pdf'},
            {'key': K('GA', 4), 'version': 0, 'itemType': 'attachment', 'parentItem': K('GI', 62),
             'linkMode': 'imported_file', 'title': 'Scan', 'contentType': 'application/pdf', 'filename': 'paper.pdf'},
            {'key': K('GA', 5), 'version': 0, 'itemType': 'attachment', 'parentItem': K('GI', 63),
             'linkMode': 'imported_file', 'title': 'notes.pdf', 'contentType': 'application/pdf',
             'filename': 'notes.pdf'}]
    flows.append(episode(k, 'attachments', [
        step('title', 'Change the title of the PDF attachment of "Garden Plans" from "Scan" to "Final plan".',
             'The attachment under Garden Plans is listed as Final plan.',
             [LIB, r('open-child', title='Garden Plans', child='Scan'), field('Title', 'Final plan'),
              r('wait', seconds=1.0)],
             [children('Garden Plans', 'title,filename', 'The attachment has the new title and keeps its file name.')]),
        step('normalize', 'Select "Pond Notes" and use the application\'s command for normalizing attachment titles '
                          'on it.',
             'The attachment under Pond Notes, formerly titled notes.pdf, is now titled PDF.',
             [LIB, select('Pond Notes'),
              r('menu', path=['Tools', 'Manage Attachments', 'Normalize Attachment Titles…']),
              r('confirm', button='Continue'), r('wait', seconds=1.5),
              r('open-child', title='Pond Notes', child='PDF')],
             [children('Pond Notes', 'title,filename', 'The attachment titled like its file is retitled PDF.'),
              children('Wetland Maps', 'title,filename', 'The eligible attachment of the unselected item keeps its title.',
                       aspect='children-wetland-maps')]),
    ], objects={'items': base, 'files': [{'key': K('GA', 4), 'name': 'paper.pdf'},
                                          {'key': K('GA', 5), 'name': 'notes.pdf'},
                                          {'key': K('GA', 7), 'name': 'notes.pdf'}]}))

    k = 'reader-annotate'
    flows.append(episode(k, 'reader', [
        step('highlight', 'Open the PDF of "Reading Practice" and highlight the sentence "The quick brown fox jumps '
                          'over the lazy dog." on page 1.',
             'The PDF is open with the sentence highlighted.',
             [LIB, r('item', title='Reading Practice', click_count=2), r('wait', seconds=5.0),
              r('click', target={'role': 'push button', 'name': 'Highlight Text'}),
              r('highlight', text='The quick brown fox jumps over the lazy dog.'), r('wait', seconds=2.0)],
             [annotations('The PDF has a highlight annotation with the sentence on page 1.')]),
        step('comment', 'Add the comment "Classic pangram" to that highlight.',
             'The highlight shows the comment Classic pangram in the annotation list.',
             [r('annotation-comment', page='Page 1', text='Classic pangram')],
             [annotations('The highlight carries the comment.')], depends=['highlight']),
        step('note', 'Go to page 2 and add a note annotation on it with the text "Check page two".',
             'Page 2 has a note annotation with the text Check page two.',
             [r('reader-page', page=2), r('click', target={'role': 'push button', 'name': 'Note Annotation'}),
              r('reader-click', page=2), r('wait', seconds=1.0), r('type', value='Check page two'),
              r('key', key='Escape'), r('wait', seconds=1.5)],
             [annotations('A note annotation with the text is on page 2.')], depends=['comment']),
    ], objects={'items': READER_ITEMS, 'files': [{'key': K('GA', 1), 'name': 'reader.pdf'}]}))

    k = 'reader-underline'
    flows.append(episode(k, 'reader', [
        step('underline', 'Open the PDF of "Reading Practice", go to page 2 and underline the sentence "Highlight this '
                          'sentence for later reference." on that page in green.',
             'Page 2 shows the sentence underlined in green.',
             [LIB, r('item', title='Reading Practice', click_count=2), r('wait', seconds=5.0), r('reader-page', page=2),
              r('click', target={'role': 'push button', 'name': 'Underline Text'}),
              r('click', target={'role': 'push button', 'name': 'Pick a Color'}),
              r('click', target={'role': 'push button', 'name': 'Green'}), r('wait', seconds=0.5),
              r('highlight', text='Highlight this sentence for later reference.'), r('wait', seconds=2.0)],
             [annotations('An underline in green with the sentence is on page 2.')]),
        step('recolor', 'Change the color of that underline to blue.',
             'The sentence on page 2 is underlined in blue.',
             [r('annotation-menu', page='Page 2', entry='Blue'), r('key', key='Escape'),
              r('raw', request={'op': 'click', 'x': 1100, 'y': 700}), r('wait', seconds=0.5)],
             [annotations('The underline is blue.')], depends=['underline']),
        step('convert', 'Turn the underline into a highlight with the application\'s command for that.',
             'The sentence on page 2 is highlighted in blue instead of underlined.',
             [r('annotation-menu', page='Page 2', entry='Convert to Highlight')],
             [annotations('The annotation is a blue highlight of the sentence.')], depends=['recolor']),
    ], objects={'items': READER_ITEMS, 'files': [{'key': K('GA', 1), 'name': 'reader.pdf'}]}))

    k = 'reader-navigation'
    flows.append(episode(k, 'reader', [
        step('page', 'Open the PDF of "Reading Practice" and go to its last page.',
             'The reader shows page 3 (Chapter 3: Reading Closely), and its page field shows 3 of 3 pages.',
             [LIB, r('item', title='Reading Practice', click_count=2), r('wait', seconds=5.0), r('reader-page', page=3)]),
        step('find', 'Search the document for the words "lazy dog".',
             'The search reports three matches, and the words lazy dog are highlighted as a match on the page.',
             [r('click', target={'role': 'push button', 'name': 'Find in Document'}), r('wait', seconds=0.8),
              r('type', value='lazy dog'), r('key', key='Return'), r('wait', seconds=1.5)], depends=['page']),
        step('thumbnails', 'Show the page thumbnails in the reader\'s sidebar.',
             'The sidebar shows a thumbnail for each of the three pages.',
             [r('key', key='Escape'), r('sidebar-tab', name='Show Thumbnails')], depends=['page']),
        step('recent', 'Return to the library and open Recently Read.',
             'Recently Read lists Reading Practice, whose PDF was opened.',
             [r('key', key='Control+w'), r('wait', seconds=0.8), r('collection', name='Recently Read')],
             depends=['page']),
    ], objects={'items': READER_ITEMS, 'files': [{'key': K('GA', 1), 'name': 'reader.pdf'}]}))

    k = 'note-from-annotations'
    notes = [{'key': K('GQ', 1), 'version': 0, 'itemType': 'annotation', 'parentItem': K('GA', 1),
              'annotationType': 'highlight', 'annotationText': 'The quick brown fox jumps over the lazy dog.',
              'annotationComment': 'Classic pangram', 'annotationColor': '#ffd400', 'annotationPageLabel': '1',
              'annotationSortIndex': '00000|000100|00100',
              'annotationPosition': '{"pageIndex":0,"rects":[[72,689.5,309.4,700.6]]}'},
             {'key': K('GQ', 2), 'version': 0, 'itemType': 'annotation', 'parentItem': K('GA', 1),
              'annotationType': 'highlight', 'annotationText': 'Highlight this sentence for later reference.',
              'annotationColor': '#5fb236', 'annotationPageLabel': '2', 'annotationSortIndex': '00001|000300|00150',
              'annotationPosition': '{"pageIndex":1,"rects":[[72,640.0,320.0,651.0]]}'}]
    flows.append(episode(k, 'reader', [
        step('note', 'Create a note from the annotations of the PDF of "Reading Practice" with the application\'s '
                     'command for that.',
             'Reading Practice has a new child note that quotes both highlighted passages (with the comment Classic '
             'pangram).',
             [LIB, r('context', target={'item': 'Reading Practice'},
                     path=['Add Note from Annotations']), r('wait', seconds=2.5)],
             [{'description': 'The new note quotes both highlights in page order with the comment.', 'aspect': 'note',
               'check': {'steps': [find('Reading Practice', [], 'title'),
                                   {'method': 'GET', 'path': U + '/items/{found}/children?itemType=note',
                                    'view': ['unordered:note-text']}]}}]),
    ], objects={'items': READER_ITEMS + notes, 'files': [{'key': K('GA', 1), 'name': 'reader.pdf'}]}))
    return flows


# ---------------------------------------------------------------------------------------------- view
def view_episodes():
    flows = []
    k = 'view-columns'
    flows.append(episode(k, 'view', [
        step('year', 'In My Library, show the Year column in the item list and sort the list by year, oldest first.',
             'The item list has a Year column and is ordered by year, oldest first: after the entries without a year '
             'come The Origin of Species (1859), On Computable Numbers (1936) and so on up to the newest items.',
             [LIB, r('menu', path=['View', 'Columns', 'Year']), r('wait', seconds=0.8),
              r('menu', path=['View', 'Sort By', 'Year']), r('wait', seconds=1.0),
              r('menu', path=['View', 'Sort By', 'Year']), r('wait', seconds=1.0)]),
        step('hide', 'Hide the Creator column of the item list, keeping the Year column and the sort by year.',
             'The item list shows the Title and Year columns but no Creator column; it is still ordered by year, '
             'oldest first.',
             [r('menu', path=['View', 'Columns', 'Creator']), r('wait', seconds=1.0)], depends=['year']),
    ], libraries=['query']))

    k = 'view-layout'
    flows.append(episode(k, 'view', [
        step('stacked', 'Switch the main window to the stacked layout, with the item details shown below the item '
                        'list instead of beside it.',
             'The item details pane is shown below the item list.',
             [LIB, select('Algorithms'), r('menu', path=['View', 'Layout', 'Stacked View']), r('wait', seconds=1.5)]),
        step('font', 'Make the interface font size bigger by one step.',
             'The item list and the item details are drawn with a larger font than before.',
             [r('menu', path=['View', 'Font Size', 'Bigger']), r('wait', seconds=1.5)], depends=['stacked']),
        step('reopen', 'The application was restarted with the same data. Select the book item "Algorithms" again.',
             'After the restart, selecting Algorithms shows its details below the item list.',
             [LIB, select('Algorithms'), r('wait', seconds=1.0)], depends=['font'], lifecycle='restart'),
    ], libraries=['query']))

    k = 'settings-item-pane'
    flows.append(episode(k, 'view', [
        step('header', 'In the application\'s settings, set the item pane header to show the title, creator and year; '
                       'close the settings and select the book item "Algorithms".',
             'The header above the item details of Algorithms shows its title, creators and year (Sedgewick and Wayne, '
             '2011), not only the title.',
             [r('menu', path=['Edit', 'Settings']), r('window', title='Zotero Settings'),
              r('click', target={'role': 'combo box', 'name': 'Item Pane Header:'}),
              r('click', target={'role': 'menu item', 'name': 'Title, Creator, Year'}), r('wait', seconds=0.8),
              r('key', key='Control+w'), r('wait', seconds=1.0), LIB, select('Algorithms'), r('wait', seconds=1.0)]),
    ], libraries=['query']))

    k = 'views-unfiled'
    flows.append(episode(k, 'view', [
        step('unfiled', 'Show the items of the library that are in no collection.',
             'The Unfiled Items view lists the items that belong to no collection (for example Example Data '
             'Protection Act and Untitled Draft about Garden Birds) and none of the collection members.',
             [r('collection', name='Unfiled Items'), r('wait', seconds=1.0)]),
        step('hide', 'Hide the Unfiled Items entry from the collections pane.',
             'Unfiled Items is no longer listed in the collections pane.',
             [r('context', target={'collection': 'Unfiled Items'}, path=['Hide']), r('wait', seconds=1.0)],
             depends=['unfiled']),
        step('show', 'Show the Unfiled Items entry in the collections pane again.',
             'Unfiled Items is listed in the collections pane again.',
             [r('context', target={'collection': 'My Library'}, path=['Show Unfiled Items']), r('wait', seconds=1.0)],
             depends=['hide']),
    ], libraries=['query']))

    k = 'settings-file-renaming'
    base = [obj(64, 'book', 'Field Guide to Ferns', [('author', 'Rachel', 'Carson')], date='1955'),
            {'key': K('GA', 6), 'version': 0, 'itemType': 'attachment', 'parentItem': K('GI', 64),
             'linkMode': 'imported_file', 'title': 'Scan', 'contentType': 'application/pdf', 'filename': 'notes.pdf'}]
    renaming = [r('menu', path=['Edit', 'Settings']), r('window', title='Zotero Settings'),
                r('click', target={'role': 'list item', 'name': 'General'}), r('wait', seconds=0.5),
                r('click', target={'role': 'push button', 'name': 'Configure File Renaming…'}),
                r('window', title='Configure File Renaming'), r('wait', seconds=1.0)]
    flows.append(episode(k, 'settings', [
        step('template', 'In the settings, change the filename template for renaming attachment files to '
                         '{{ year }} {{ title }}, and use the command offered there to rename the existing files of '
                         'the library to match.',
             'The PDF attachment of Field Guide to Ferns now has the file name 1955 Field Guide to Ferns.pdf.',
             [*renaming, r('raw', request={'op': 'click', 'x': 120, 'y': 380}), r('key', key='Control+a'),
              r('type', value='{{ year }} {{ title }}'), r('wait', seconds=1.5),
              r('click', target={'role': 'push button', 'name': 'Rename Files…'}), r('confirm', button='Rename Files'),
              r('click', target={'role': 'push button', 'name': 'Done'}), r('wait', seconds=0.8),
              r('key', key='Control+w'), r('wait', seconds=0.8), LIB, r('open-child', title='Field Guide to Ferns',
                                                                        child='Scan')],
             [children('Field Guide to Ferns', 'title,filename,md5', 'The stored file is renamed by the template.')]),
        step('manual', f'Turn off the automatic renaming of files, then attach a stored copy of the file '
                       f'{inbox(k)}/paper.pdf to "Field Guide to Ferns".',
             'Field Guide to Ferns has a second PDF attachment, whose file keeps the name paper.pdf.',
             [*renaming, r('check', target={'role': 'check box', 'name': 'Automatically rename files'}, checked=False),
              r('wait', seconds=0.5), r('click', target={'role': 'push button', 'name': 'Done'}), r('wait', seconds=0.8),
              r('key', key='Control+w'), r('wait', seconds=0.8), LIB,
              r('context', target={'item': 'Field Guide to Ferns'}, path=['Add Attachment', 'File']),
              r('open-file', path='inbox/paper.pdf'), r('wait', seconds=2.0)],
             [children('Field Guide to Ferns', 'title,filename,md5', 'The new attachment keeps its file name.')],
             depends=['template']),
    ], objects={'items': base, 'files': [{'key': K('GA', 6), 'name': 'notes.pdf'}]}, files=['paper.pdf']))

    k = 'settings-cite'
    base = [obj(65, 'journalArticle', 'Coral Reef Survey', [('author', 'Sylvia', 'Earle')], date='2001',
                publicationTitle='Marine Notes', volume='4', pages='10-20', url='https://reefs.example.org/survey')]
    flows.append(episode(k, 'settings', [
        step('urls', 'In the settings, make references include the URLs of paper articles; close the settings and '
                     'copy the bibliography entry of "Coral Reef Survey" (its full reference, not a citation) to the '
                     'clipboard with the quick copy command.',
             'The settings close without an error message, and Coral Reef Survey stays selected in the item list.',
             [r('menu', path=['Edit', 'Settings']), r('window', title='Zotero Settings'),
              r('click', target={'role': 'list item', 'name': 'Cite'}), r('wait', seconds=1.0),
              r('check', target={'role': 'check box', 'name': 'Include URLs of paper articles in references'}),
              r('wait', seconds=0.5), r('key', key='Control+w'), r('wait', seconds=0.8), LIB,
              select('Coral Reef Survey'), r('key', key='Control+Shift+c'), r('wait', seconds=1.0)],
             [clipboard('text', 'text', 'The entry now ends with the article\'s URL.', 'text')],
             requires={'visible': ['text']}),
        step('install', f'Install the citation style in {inbox(k)}/minimal.csl from the settings.',
             'Bench Minimal Author-Year appears among the installed citation styles.',
             [r('menu', path=['Edit', 'Settings']), r('window', title='Zotero Settings'),
              r('click', target={'role': 'list item', 'name': 'Cite'}), r('wait', seconds=1.0),
              r('click', target={'role': 'push button', 'name': 'Add from File…'}),
              r('open-file', path='inbox/minimal.csl'), r('wait', seconds=1.0)]),
        step('style', 'Create a bibliography of "Coral Reef Survey" in Bench Minimal Author-Year and copy it '
                      'to the clipboard.',
             'Coral Reef Survey is selected and the bibliography command finishes without an error.',
             [r('key', key='Control+w'), r('wait', seconds=0.8), LIB,
              r('context', target={'item': 'Coral Reef Survey'}, path=['Create Bibliography from Item…']),
              *bibliography_dialog('Bench Minimal Author-Year')],
             [clipboard('text', 'text', 'The clipboard holds the entry in the installed style.', 'text'),
              clipboard('html', 'bib', 'The HTML version of the entry follows the installed style.', 'html')],
             depends=['install'], requires={'visible': ['text']}),
    ], objects={'items': base}, files=['minimal.csl']))
    return flows


def additional_episodes():
    flows = []
    k = 'my-publications'
    flows.append(episode(k, 'collections', [
        step('add', 'Add the item "Local Research" to My Publications, confirming that this example work is yours.',
             'My Publications lists Local Research.',
             [LIB, select('Local Research'),
              r('drag', target={'role': 'tree item', 'name': 'Local Research. Book. Lovelace'},
                to_target={'role': 'tree item', 'name': 'My Publications'}, seconds=1.0),
              r('wait', seconds=0.8), r('check', target={'role': 'check box', 'name': 'I created this work.'}),
              r('click', target={'role': 'push button', 'name': 'Add to My Publications'}), r('wait', seconds=1.0),
              r('collection', name='My Publications')],
             [items(f'{U}/publications/items', 'unordered:fields:title', 'My Publications contains Local Research.', 'members'),
              item('Local Research', 'inPublications', 'The item belongs to My Publications.')]),
    ], objects={'items': [obj(80, 'book', 'Local Research', [('author', 'Ada', 'Lovelace')], date='2020')]}))

    k = 'import-clipboard'
    source = '@book{clip,title={Clipboard Methods},author={Lovelace, Ada},year={1843},publisher={Example Press}}'
    flows.append(episode(k, 'import', [
        step('import', 'Copy the BibTeX text from the standalone note beginning "@book{clip" to the clipboard, '
                       'then import it with the application’s Import from Clipboard command.',
             'A Book titled Clipboard Methods is listed with author Lovelace, Ada, date 1843 and publisher Example Press.',
             [LIB, select('@book{clip'), r('note-end'), r('key', key='Control+a'), r('key', key='Control+c'),
              r('menu', path=['File', 'Import from Clipboard']), r('wait', seconds=2.0), LIB,
              select('Clipboard Methods')],
             [item('Clipboard Methods', 'itemType,title,creators,date,publisher,collections',
                   'The clipboard text is imported as a book in My Library.')]),
    ], objects={'items': [{'key': K('GN', 90), 'version': 0, 'itemType': 'note', 'note': '<p>' + source + '</p>'}]}))

    k = 'view-density-note-font'
    flows.append(episode(k, 'view', [
        step('density', 'Set the interface density to Compact.',
             'The library rows use compact spacing.',
             [LIB, r('menu', path=['View', 'Density', 'Compact']), r('wait', seconds=1.0)]),
        step('note-font', 'Set the note font size to 24 and show the standalone note "Layout Notes".',
             'The note font size is set to 24, and Layout Notes is displayed in the larger text size.',
             [LIB, select('Layout Notes'), r('menu', path=['View', 'Note Font Size', '24']),
              r('wait', seconds=1.0), r('click', target={'role': 'menu', 'name': 'View'}),
              r('click', target={'role': 'menu', 'name': 'Note Font Size'})]),
    ], libraries=['query'], objects={'items': [{'key': K('GN', 91), 'version': 0, 'itemType': 'note',
         'note': '<p>Layout Notes</p><p>Clear text makes reading easier.</p>'}]}))

    k = 'reader-export-pdf'
    marks = [
        {'key': K('GX', 1), 'version': 0, 'itemType': 'annotation', 'parentItem': K('GA', 1),
         'annotationType': 'highlight', 'annotationText': 'The quick brown fox jumps over the lazy dog.',
         'annotationComment': 'Classic pangram', 'annotationColor': '#ffd400', 'annotationPageLabel': '1',
         'annotationSortIndex': '00000|000100|00100',
         'annotationPosition': '{"pageIndex":0,"rects":[[72,689.5,309.4,700.6]]}'},
        {'key': K('GX', 2), 'version': 0, 'itemType': 'annotation', 'parentItem': K('GA', 1),
         'annotationType': 'note', 'annotationComment': 'Check page two', 'annotationColor': '#5fb236',
         'annotationPageLabel': '2', 'annotationSortIndex': '00001|000010|00010',
         'annotationPosition': '{"pageIndex":1,"rects":[[400,500,422,522]]}'},
    ]
    flows.append(episode(k, 'reader', [
        step('export', 'Open the PDF of "Reading Practice" and save a PDF copy containing its annotations to '
                       f'{outbox(k)}/annotated.pdf.',
             'The PDF remains open and saving finishes without an error.',
             [LIB, r('item', title='Reading Practice', click_count=2), r('wait', seconds=4.0),
              r('menu', path=['File', 'Save As…']), r('save-file', path='outbox/annotated.pdf'),
              r('wait', seconds=1.5)],
             [{'description': 'The exported PDF preserves all three pages and their text.', 'aspect': 'pages',
               'check': {'steps': [{'kind': 'download', 'filename': 'annotated.pdf', 'binary': True,
                                    'view': ['pdf-pages']}]}},
              {'description': 'The exported PDF embeds the highlight and note on their pages with their comments.',
               'aspect': 'annotations', 'check': {'steps': [{'kind': 'download', 'filename': 'annotated.pdf',
                                                            'binary': True, 'view': ['pdf-annotations']}]}}],
             requires={'visible': ['pages', 'annotations']}),
    ], objects={'items': READER_ITEMS + marks, 'files': [{'key': K('GA', 1), 'name': 'reader.pdf'}]}))

    k = 'import-rdf-endnote'
    flows.append(episode(k, 'import', [
        step('rdf', f'Import {inbox(k)}/references.rdf directly into My Library, without an additional enclosing collection.',
             'The imported Source Papers collection contains Archive Studies.',
             [*import_file('inbox/references.rdf', False), r('collection', name='Source Papers')],
             [imported('Archive Studies', 'itemType,title,creators,date,publisher', 'The RDF book retains its fields.', 'book'),
              children('Archive Studies', 'itemType,note', 'The RDF child note is attached to its book.'),
              collection_items('Source Papers', 'The RDF collection contains the book.')]),
        step('endnote', f'Import {inbox(k)}/endnote.xml into a new collection.',
             'The new endnote collection lists Endnote Survey.',
             import_file('inbox/endnote.xml', True),
             [imported('Endnote Survey', 'itemType,title,creators,date,publicationTitle,volume,pages',
                       'The Endnote article retains its fields.', 'article'),
              collection_items('endnote', 'The Endnote import belongs to its new collection.')]),
    ], files=['references.rdf', 'endnote.xml']))

    k = 'reader-markup'
    def mark(kind, description):
        return items(f'{U}/items?itemType=annotation',
                     f'where:annotationType={kind}:unordered:fields:annotationType,annotationPageLabel,annotationComment',
                     description, 'annotation')
    def open_pdf(page):
        return [r('click', target={'role': 'section', 'name': 'My Library'}), LIB,
                r('item', title='Reading Practice', click_count=2), r('wait', seconds=4.0),
                r('reader-page', page=page)]
    flows.append(episode(k, 'reader', [
        step('text', 'Open the PDF of "Reading Practice" and add a text annotation reading "Review this page" '
                     'in the blank area below the text on page 1.',
             'Page 1 displays the added text Review this page.',
             [*open_pdf(1), r('click', target={'role': 'push button', 'name': 'Add Text'}),
              r('raw', request={'op': 'click', 'x': 700, 'y': 650}), r('type', value='Review this page'),
              r('key', key='Escape'), r('wait', seconds=1.0)],
             [mark('text', 'A text annotation on page 1 contains the entered text.')]),
        step('image', 'In the same PDF, add an image (area) annotation around the heading '
                      '"Chapter 2: Reading Closely" on page 2.',
             'Page 2 shows a rectangular area annotation around the chapter heading.',
             [*open_pdf(2), r('click', target={'role': 'push button', 'name': 'Select Area'}),
              r('reader-region', text='Chapter 2: Reading Closely'), r('wait', seconds=1.0)],
             [mark('image', 'An image annotation is stored on page 2.')]),
        step('ink', 'In the same PDF, draw a short freehand zigzag in the blank area below the text on page 3.',
             'Page 3 shows a freehand zigzag below its text.',
             [*open_pdf(3), r('click', target={'role': 'push button', 'name': 'Draw'}),
              r('reader-ink'), r('wait', seconds=1.0)],
             [mark('ink', 'An ink annotation is stored on page 3.')]),
    ], objects={'items': READER_ITEMS, 'files': [{'key': K('GA', 1), 'name': 'reader.pdf'}]}))

    k = 'export-note'
    note = {'key': K('GN', 80), 'version': 0, 'itemType': 'note',
            'note': '<h1>Reading Notes</h1><p>A <strong>clear</strong> summary.</p>'
                    '<ul><li>First point</li><li>Second point</li></ul>'}
    steps = []
    for name, fmt, suffix, reader in [('markdown', 'Markdown', 'md', 'text'), ('html', 'HTML', 'html', 'html-text')]:
        filename = f'notes.{suffix}'
        steps.append(step(name, f'Export the note "Reading Notes" as {fmt} to {outbox(k)}/{filename}, '
                               'without Zotero links.',
             'The note export finishes without an error.',
             [LIB, r('context', target={'item': 'Reading Notes'}, path=['Export Note…']),
              r('window', title='Export…'), r('click', target={'role': 'combo box', 'name': 'Format:'}),
              r('click', target={'role': 'menu item', 'name': fmt}),
              r('check', target={'role': 'check box', 'name': 'Include Zotero Links'}, checked=False),
              r('click', target={'role': 'push button', 'name': 'OK'}),
              r('save-file', path=f'outbox/{filename}'), r('wait', seconds=1.0)],
             [{'description': f'The {fmt} file preserves the note content.', 'aspect': 'note',
               'check': {'steps': [{'kind': 'download', 'filename': filename, 'view': [f'format:{reader}']}]}}],
             requires={'visible': ['note']}))
    flows.append(episode(k, 'notes', steps, objects={'items': [note]}))
    return flows


def build():
    return (item_episodes() + note_episodes() + collection_episodes() + tag_episodes() + search_episodes()
            + export_episodes() + import_episodes() + citation_episodes() + attachment_episodes()
            + view_episodes() + additional_episodes())
