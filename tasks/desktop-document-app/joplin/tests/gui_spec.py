"""Functional user goals; recipes are deliberately separate from acceptance."""
import fixtures
from evaluation.contract import files_path

RIVER = '# River survey\n\nThree oak trees grow beside the river.\n\nNorth bank: 2 trees.\nSouth bank: 1 tree.'
ORCHARD = '# Orchard plan\n\nPlant two apple trees and three pear trees.\n\nBring a shovel and water.'
PACKING = '- [ ] Bring a map\n- [x] Fill the water bottle\n- [ ] Pack lunch'
SEED = [dict(title='River survey', body=RIVER, tags='botany', author='Ada Lovelace'),
        dict(title='Orchard plan', body=ORCHARD, tags='botany,planning'),
        dict(title='Packing list', body=PACKING, is_todo=1)]


def note(title, **values):
    return {'kind': 'note', 'title': title, 'values': values}


def check(kind, **kwargs):
    return {'kind': kind, **kwargs}


def step(key, goal, visible, recipe, checks=(), *, depends=(), lifecycle=None, modal=False):
    result = {'id': key, 'goal': goal, 'acceptance': [visible] if isinstance(visible, str) else visible,
              'recipe': recipe, 'checks': list(checks), 'depends_on': list(depends)}
    if lifecycle:
        result['lifecycle'] = lifecycle
    if modal:
        result['modal_end'] = True
    return result


def episode(key, feature, steps, *, notes=None, books=None, selected='River survey', files=()):
    inbox = files_path('inbox', instance=False)
    outbox = files_path('outbox', instance=False)
    seed = {'id': 'fixtures', 'books': books or ['Workbench', 'Archive'], 'notes': SEED if notes is None else notes,
            'files': list(files)}
    for cp in steps:
        cp['depends_on'].insert(0, 'setup:fixtures')
        cp['assertions'] = [{'id': f'{key}/{cp["id"]}/visible-{i+1}', 'channel': 'frontend', 'method': 'agent',
                             'requirement': text} for i, text in enumerate(cp.pop('acceptance'))]
        for i, item in enumerate(cp['checks']):
            for aspect in (list(item.get('values', {})) or [item['kind']]):
                cp['assertions'].append({'id': f'{key}/{cp["id"]}/data-{i+1}-{aspect}', 'channel': 'backend',
                    'method': 'program', 'requirement': f'The {item["kind"]} result preserves the requested {aspect}.',
                    'check': item, 'aspect': aspect})
        cp['goal'] = cp['goal'].replace('$INBOX', inbox).replace('$OUTBOX', outbox)
    preparation = (f'Before the first goal select the note "{selected}". ' if selected else
                   'Before the first goal select notebook "Workbench". ')
    n = len(steps)
    return {'id': key, 'feature': feature, 'execution': 'gui',
        'initial_state': 'A fresh profile with the listed fixture notebooks, notes and uploaded documents.',
        'setup': [seed], 'selected': selected,
        'inputs': {'inbox': inbox, 'outbox': outbox, 'notes': seed['notes'], 'books': seed['books'],
                   'files': {name: inbox+'/'+name for name in files}},
        'session': preparation + 'Dismiss any first-use informational notice while keeping Markdown rendering enabled. '
        'Work through the goals in order. Note edits save automatically; allow them to finish before leaving the note. '
        'Multiline inputs are exact text between the fences. For a file dialog enter the complete path supplied by '
        'the goal. In a directory chooser, verify that the selected folder is the one named by the goal; '
        'path completion may otherwise leave a parent or child folder selected. A single click on a folder '
        'followed by confirmation selects it. Menus, shortcuts, context menus and toolbar operations that achieve the same result are equivalent. '
        'A goal asking to inspect a dialog leaves it open; otherwise finish the operation before closing the checkpoint.',
        'allowed_equivalents': ['Any visible user-interface route that achieves the goal is equivalent.',
                               'The implementation may use different controls and visual design.'],
        'forbidden_bypasses': ['Use the application interface; do not use a terminal, scripts or another application.'],
        'budget': {'calls': min(400,220+45*n), 'tokens': 1000000+250000*n, 'seconds': 1200+240*n},
        'checkpoints': steps}


def build():
    w = []
    w.append(episode('notebook-create', 'notebooks', [
        step('create', 'Create a notebook named "Research".', 'Research is available as a notebook.',
             [{'op': 'new-notebook', 'title': 'Research'}], [check('folder', title='Research', parent='')]),
        step('child', 'Create a sub-notebook named "Field trips" inside Research.',
             ['Field trips is available as a notebook.', 'Its parent is Research.'],
             [{'op': 'new-notebook', 'title': 'Field trips', 'parent': 'Research'}],
             [check('folder', title='Field trips', parent='Research')], depends=('create',)),
        step('rename', 'Rename Research to "Research archive".', 'The parent notebook now appears as Research archive.',
             [{'op': 'rename-book', 'old': 'Research', 'title': 'Research archive'}],
             [check('folder', title='Research archive', parent='')], depends=('child',))], notes=[], selected=None))
    w.append(episode('notebook-tree', 'notebook navigation', [
        step('collapse', 'Collapse Workbench so its sub-notebook is hidden.', 'Workbench can be collapsed while remaining available.',
             [{'op': 'collapse-book', 'title': 'Workbench'}]),
        step('expand', 'Expand Workbench and open its sub-notebook Field trips.',
             ['Field trips is reachable under Workbench.', 'Its note Trail journal is available.'],
             [{'op': 'expand-book', 'title': 'Workbench'}, {'op': 'book', 'title': 'Field trips'}], depends=('collapse',)),
        step('rename', 'Rename the Field trips notebook to "Excursions".', 'The nested notebook is now named Excursions.',
             [{'op': 'rename-book', 'old': 'Field trips', 'title': 'Excursions'}],
             [check('folder', title='Excursions', parent='Workbench')])],
        books=['Workbench','Archive',{'title':'Field trips','parent':'Workbench'}],
        notes=[{'title':'Trail journal','body':'A quiet trail.','book':'Field trips'}], selected=None))
    w.append(episode('note-create', 'note creation', [
        step('create', 'Create a note in Workbench titled "Morning journal" with this body:\n```\nA bright morning.\n\nThe garden is quiet.\n```',
             ['Morning journal is listed and opened.', 'Both paragraphs are visible in the note.'],
             [{'op':'book','title':'Workbench'},{'op':'new-note','title':'Morning journal','body':'A bright morning.\n\nThe garden is quiet.'}],
             [note('Morning journal', body='A bright morning.\n\nThe garden is quiet.', parent='Workbench')]),
        step('rename', 'Rename Morning journal to "Morning journal — revised".', 'The selected note uses the revised title.',
             [{'op':'title','value':'Morning journal — revised'}], [note('Morning journal — revised',body='A bright morning.\n\nThe garden is quiet.')], depends=('create',)),
        step('edit', 'Replace its body with exactly:\n```\nCafé by the river.\n中文笔记 — 日本語メモ.\n```',
             'The revised note displays both lines of multilingual text.',
             [{'op':'body','value':'Café by the river.\n中文笔记 — 日本語メモ.'}],
             [note('Morning journal — revised',body='Café by the river.\n中文笔记 — 日本語メモ.')], depends=('rename',))]))
    w.append(episode('note-edit-history', 'editing undo redo and clipboard', [
        step('replace', 'Replace River survey body with "Five trees were counted.".', 'The note displays the replacement sentence.',
             [{'op':'body','value':'Five trees were counted.'}], [note('River survey',body='Five trees were counted.')]),
        step('undo', 'Undo that body replacement.', 'The original river survey content is visible again.',
             [{'op':'press','key':'Control+Z'}], [note('River survey',body=RIVER)], depends=('replace',)),
        step('redo', 'Redo the body replacement.', 'The replacement sentence is visible again.',
             [{'op':'focus-body'},{'op':'press','key':'Control+Shift+Z'}], [note('River survey',body='Five trees were counted.')], depends=('undo',)),
        step('copy', 'Select and copy the complete note body.', 'The sentence is selected in the editor.',
             [{'op':'select-body'},{'op':'press','key':'Control+C'}],
             [check('clipboard',text='Five trees were counted.')], depends=('redo',))]))
    w.append(episode('note-duplicate', 'duplicate notes', [
        step('duplicate', 'Duplicate River survey.', 'A second copy of River survey is available.',
             [{'op':'context','title':'River survey','items':['Duplicate']},{'op':'note','title':'River survey - Copy'}],
             [note('River survey - Copy',body=RIVER),note('River survey',body=RIVER)]),
        step('rename-copy', 'Rename the selected duplicate to "River survey copy" and replace its body with "Edited copy only.".',
             ['The duplicate has the new title.', 'The duplicate displays Edited copy only.'],
             [{'op':'title','value':'River survey copy'},{'op':'body','value':'Edited copy only.'}],
             [note('River survey copy',body='Edited copy only.'),note('River survey',body=RIVER)], depends=('duplicate',))]))
    w.append(episode('note-move', 'move notes', [
        step('move', 'Move River survey into Archive, then open it there.',
             ['River survey is available in Archive.', 'The moved note retains its river survey content.'],
             [{'op':'move-note','title':'River survey','book':'Archive'}], [note('River survey',parent='Archive',body=RIVER)])]))
    w.append(episode('note-trash', 'trash and restore', [
        step('delete', 'Move River survey to Trash, then open Trash.', 'River survey is available in Trash.',
             [{'op':'delete-note','title':'River survey'},{'op':'book','title':'Trash'}], [note('River survey',deleted=True)]),
        step('inspect', 'Open the trashed River survey note.', 'The trashed note still displays its river survey content.',
             [{'op':'select-list','title':'River survey'}], [note('River survey',body=RIVER,deleted=True)], depends=('delete',)),
        step('restore', 'Restore River survey from Trash and open it in Workbench.',
             ['River survey is active again in Workbench.', 'The restored note retains its contents.'],
             [{'op':'restore-note','title':'River survey','book':'Workbench'}],
             [note('River survey',body=RIVER,parent='Workbench',deleted=False)], depends=('inspect',))]))
    w.append(episode('todo-create-complete', 'to-dos', [
        step('create', 'Create a to-do titled "Buy notebooks" with body "Two squared notebooks." in Workbench.',
             ['Buy notebooks is available as an incomplete to-do.', 'Its body is visible.'],
             [{'op':'book','title':'Workbench'},{'op':'new-note','title':'Buy notebooks','body':'Two squared notebooks.','todo':True}],
             [note('Buy notebooks',body='Two squared notebooks.',is_todo=1,completed=False)]),
        step('complete', 'Mark Buy notebooks complete.', 'Buy notebooks is shown as completed.',
             [{'op':'todo-check','title':'Buy notebooks','checked':True}], [note('Buy notebooks',completed=True)], depends=('create',)),
        step('reopen', 'Mark Buy notebooks incomplete again.', 'Buy notebooks is shown as pending again.',
             [{'op':'todo-check','title':'Buy notebooks','checked':False}], [note('Buy notebooks',completed=False)], depends=('complete',))]))
    w.append(episode('todo-convert', 'note and to-do conversion', [
        step('to-note', 'Convert Packing list from a to-do to an ordinary note.', 'Packing list is shown as an ordinary note.',
             [{'op':'context','title':'Packing list','items':['Switch between note and to-do type']}], [note('Packing list',is_todo=0,body=PACKING)]),
        step('to-todo', 'Convert Packing list back to a to-do.', 'Packing list again has a to-do completion control.',
             [{'op':'context','title':'Packing list','items':['Switch between note and to-do type']}], [note('Packing list',is_todo=1)], depends=('to-note',))], selected='Packing list'))
    w.append(episode('tags-edit', 'note tagging', [
        step('add', 'Add the tag "fieldwork" to River survey, keeping its existing botany tag.',
             'The note shows both botany and fieldwork tags.', [{'op':'add-tag','tag':'fieldwork'}],
             [check('tags',title='River survey',tags=['botany','fieldwork'])]),
        step('another', 'Also tag River survey with "planning".', 'The note shows all three tags, including planning.',
             [{'op':'add-tag','tag':'planning'}], [check('tags',title='River survey',tags=['botany','fieldwork','planning'])], depends=('add',)),
        step('remove', 'Remove only the fieldwork tag from River survey.',
             ['Fieldwork is removed from this note.', 'Botany and planning remain attached.'],
             [{'op':'remove-tag','tag':'fieldwork'}], [check('tags',title='River survey',tags=['botany','planning'])], depends=('another',))]))
    w.append(episode('tags-navigation', 'tag navigation and rename', [
        step('filter', 'Open the botany tag to see its notes.', 'Both River survey and Orchard plan are available under botany.',
             [{'op':'tag','title':'botany'}]),
        step('rename', 'Rename the botany tag to "plants".', 'The tag is now named plants.',
             [{'op':'rename-tag','old':'botany','title':'plants'}], [check('tags',title='River survey',tags=['plants'])]),
        step('open', 'Open Orchard plan from the plants tag.', 'The tagged Orchard plan note is displayed with its content.',
             [{'op':'tag','title':'plants'},{'op':'select-list','title':'Orchard plan'}], depends=('rename',))]))

    formats = [
        ('markdown-inline','inline Markdown',[
            ('emphasis','**Bold oak** and *quiet elm* and ~~old plan~~.', ['Bold oak is emphasized strongly.', 'Quiet elm is italic and old plan is struck through.']),
            ('code','Use `tree_count = 3` and [the guide](https://example.invalid/guide).', ['The inline code is distinguishable from prose.', 'The guide is presented as a link.']),
            ('escape',r'Literal \*stars\* and \[brackets\], plus café 中文.', ['The escaped stars and brackets appear as literal text.', 'The multilingual text is readable.'])]),
        ('markdown-blocks','block Markdown',[
            ('headings','# Survey\n\n## North bank\n\n### Oak trees\n\nThree trees counted.', ['The three headings have a visible hierarchy.', 'The observation appears as a paragraph.']),
            ('quote','> First observation.\n>\n> Second observation.\n\nOutside the quotation.', ['The two quoted paragraphs are grouped as a quotation.', 'The final paragraph is outside the quotation.']),
            ('lists','- Oak\n- Elm\n  - Young elm\n\n1. Count trees\n2. Record results', ['The plant list includes a nested item.', 'The two work steps form an ordered list.'])]),
        ('markdown-tables','tables and fenced code',[
            ('table','| Plant | Count |\n| :--- | ---: |\n| Oak | 3 |\n| Elm | 7 |', ['Plant and Count are table headings.', 'The Oak and Elm rows retain their respective counts.']),
            ('fence','```python\ncount = 3\nprint(count)\n```\n\nThe code counts trees.', ['The code block retains both lines and indentation.', 'The explanatory paragraph is separate from the code.'])]),
    ]
    for key, feature, cases in formats:
        steps=[]
        for name, body, acceptance in cases:
            steps.append(step(name, 'Replace the body of Formatting with the following Markdown and inspect its formatted presentation:\n```\n'+body+'\n```',
                              acceptance,[{'op':'body','value':body},{'op':'blur'}], [note('Formatting',body=body)]))
        w.append(episode(key,feature,steps,notes=[{'title':'Formatting','body':'Initial text.'}],selected='Formatting'))
    w.append(episode('markdown-checklist','in-note checklists',[
        step('render','Open Packing list and inspect its checklist.', ['The three checklist items are visible.', 'Fill the water bottle is completed while the others are pending.'],
             [{'op':'note','title':'Packing list'},{'op':'blur'}]),
        step('toggle','Mark Bring a map complete in the note body.', 'Bring a map and Fill the water bottle are now completed.',
             [{'op':'body-checkbox','label':'Bring a map'}], [check('checklist',title='Packing list',checked=['Bring a map','Fill the water bottle'])])],selected='Packing list'))
    w.append(episode('formatting-toolbar','formatting commands',[
        step('bold','Make all text in Formatting bold.', 'The complete sentence is bold.',
             [{'op':'select-body'},{'op':'press','key':'Control+B'},{'op':'blur'}], [check('markup',title='Formatting',tag='strong',text='Amber forest')]),
        step('italic','Make that same text italic as well as bold.', 'The sentence is both bold and italic.',
             [{'op':'select-text','text':'Amber forest','offset':2},{'op':'press','key':'Control+I'},{'op':'blur'}],
             [check('markup',title='Formatting',tag='em',also='strong',text='Amber forest')], depends=('bold',)),
        step('undo','Undo the italic formatting while retaining the bold formatting.', 'The sentence is bold without italics.',
             [{'op':'focus-body'},{'op':'press','key':'Control+Z'},{'op':'blur'}], depends=('italic',))],
        notes=[{'title':'Formatting','body':'Amber forest'}],selected='Formatting'))
    w.append(episode('rich-text','rich text editor',[
        step('switch','Switch River survey to the rich text editor.', ['The note can be edited in rich text.', 'Its heading and paragraphs remain readable.'],
             [{'op':'press','key':'Control+Alt+E'}]),
        step('edit','Replace its rich text body with "A rich text observation.".', 'The rich text editor displays the new sentence.',
             [{'op':'rich-body','value':'A rich text observation.'}], [check('plain-body',title='River survey',text='A rich text observation.')], depends=('switch',))]))
    w.append(episode('editor-lines','line editing',[
        step('duplicate','Duplicate the middle line of Lines.', 'The middle line appears twice in sequence.',
             [{'op':'line','key':'Control+Shift+D','line':1}], [note('Lines',body='apple\npear\npear\nplum')]),
        step('delete','Delete one of the two pear lines.', 'One pear line remains between apple and plum.',
             [{'op':'line','key':'Control+D','line':1}], [note('Lines',body='apple\npear\nplum')], depends=('duplicate',)),
        step('indent','Indent the pear line once.', 'The middle line is indented relative to its neighbors.',
             [{'op':'line','key':'Control+]','line':1}], [check('indented',title='Lines',text='pear')], depends=('delete',)),
        step('outdent','Remove that indentation.', 'All three lines are again aligned.',
             [{'op':'line','key':'Control+[','line':1}], [note('Lines',body='apple\npear\nplum')], depends=('indent',))],
        notes=[{'title':'Lines','body':'apple\npear\nplum'}],selected='Lines'))
    w.append(episode('global-search','search all notes',[
        step('term','Find notes containing "pear" using the application search.', 'Orchard plan appears as a matching note.',
             [{'op':'search','query':'pear'}]),
        step('filter','Search for "type:todo".', 'Packing list appears as a to-do search result.',
             [{'op':'search','query':'type:todo'}]),
        step('tag','Search for "tag:botany".', 'Both River survey and Orchard plan appear in the results.',
             [{'op':'search','query':'tag:botany'}]),
        step('open','Open Orchard plan from those results.', ['Orchard plan is selected.', 'Its orchard planning text is visible.'],
             [{'op':'select-list','title':'Orchard plan'}], depends=('tag',))]))
    w.append(episode('goto-anything','quick navigation',[
        step('note','Use quick navigation to open Orchard plan.', 'The Orchard plan note and its content are visible.',
             [{'op':'goto','query':'Orchard plan'}]),
        step('other','Use quick navigation to open Packing list.', 'Packing list is opened with its checklist.',
             [{'op':'goto','query':'Packing list'}])]))
    w.append(episode('local-find','find in a note',[
        step('find','Find "river" within River survey.', 'The in-note search identifies a river match.',
             [{'op':'local-find','query':'river'}]),
        step('next','Move to the next occurrence of river.', 'Another river occurrence is selected or highlighted.',
             [{'op':'press','key':'Return'}], depends=('find',)),
        step('close','Close in-note search and replace "Three" with "Four" in the note body.', 'The observation now says Four oak trees.',
             [{'op':'press','key':'Escape'},{'op':'body','value':RIVER.replace('Three','Four')}],
             [note('River survey',body=RIVER.replace('Three','Four'))])]))
    w.append(episode('note-sorting','note list ordering',[
        step('title','Sort Workbench notes by title in ascending order.', 'The note list follows ascending title order.',
             [{'op':'sort','direction':'ascending'}]),
        step('reverse','Reverse that title order.', 'The note list follows descending title order.',
             [{'op':'sort','direction':'descending'}], depends=('title',)),
        step('details','Show the detailed note list.', 'The note list provides note titles and additional note details.',
             [{'op':'menu','items':['View','Note list style','Detailed']}])],
        notes=[{'title':'Orchard plan','body':ORCHARD},{'title':'River survey','body':RIVER}],
        selected='River survey'))
    w.append(episode('workspace-layout','workspace controls',[
        step('sidebar','Hide the notebook sidebar.', 'Notebook navigation is hidden and the note remains accessible.',
             [{'op':'press','key':'F10'}]),
        step('restore','Restore the notebook sidebar.', 'Notebook navigation is available again with Workbench and Archive.',
             [{'op':'press','key':'F10'}], depends=('sidebar',)),
        step('preview','Show the note in the viewer layout.', 'The rendered note can be read without its editing controls.',
             [{'op':'viewer'}])]))
    w.append(episode('note-properties','note properties',[
        step('inspect','Open the properties of River survey for inspection.', ['The properties identify the selected note.', 'Created and updated dates and the markup format are visible.'],
             [{'op':'click','name':'Note properties','role':'push button'}], modal=True),
        step('url','Set the note source URL to https://example.invalid/survey and leave its properties open for inspection.', 'The source URL is visible in the note properties.',
             [{'op':'property-url','url':'https://example.invalid/survey'}], [note('River survey',source_url='https://example.invalid/survey')], depends=('inspect',),modal=True)]))
    w.append(episode('note-statistics','note statistics',[
        step('stats','Inspect the statistics of River survey.', ['The statistics report the note\'s word and character counts.', 'Editor and viewer statistics are distinguishable.'],
             [{'op':'menu','items':['Note','Statistics']}], modal=True)]))
    w.append(episode('note-attachments','attach files and images',[
        step('file','Attach $INBOX/plain.txt to River survey.', 'The note displays a link to the plain.txt attachment.',
             [{'op':'attach','path':'inbox/plain.txt'}], [check('attachments',title='River survey',names=['plain.txt'])]),
        step('image','Also attach $INBOX/diagram.png and show the image in the note.', ['The attached diagram is visible.', 'The text attachment remains available.'],
             [{'op':'attach','path':'inbox/diagram.png'},{'op':'blur'}],
             [check('attachments',title='River survey',names=['plain.txt','diagram.png'])],depends=('file',))],files=('plain.txt','diagram.png')))
    w.append(episode('internal-link','links between notes',[
        step('link','Add a link to Orchard plan at the end of River survey.', 'The note includes a link named Orchard plan.',
             [{'op':'note-link','title':'Orchard plan'}], [check('note-link',title='River survey',target='Orchard plan')]),
        step('follow','Follow that link to Orchard plan.', 'Orchard plan opens with its orchard planning content.',
             [{'op':'follow-link','title':'Orchard plan'}], depends=('link',))]))
    imports = [('markdown','field-note.md','MD - Markdown (File)','field-note','Imported field note'),
               ('text','plain.txt','TXT - Text document (File)','plain','First imported line.'),
               ('html','clipped.html','HTML - HTML document (File)','clipped','River survey'),
               ('front-matter','front-matter.md','MD - Markdown + Front Matter (File)','Front matter journal','Observations'),
               ('enex-markdown','sample.enex','ENEX - Evernote Export File (as Markdown)','Evernote field journal','Imported observation.'),
               ('enex-html','sample.enex','ENEX - Evernote Export File (as HTML)','Evernote field journal','Imported observation.')]
    for key, file, menu, title, text in imports:
        w.append(episode('import-'+key,'document import',[
            step('import',f'Import $INBOX/{file} as {key.replace("-"," ")} and open the imported note.',
                 ['The imported note is available and opened.', f'Its content includes {text}.'],
                 [{'op':'import','path':'inbox/'+file,'format':menu,'title':title}],
                 [check('imported',title=title,text=text)])],files=(file,),notes=[],selected=None))
    exports = [('jex','JEX - Joplin Export File','archive.jex','JEX - Joplin Export File'),
               ('raw','RAW - Joplin Export Directory',None,'RAW - Joplin Export Directory'),
               ('markdown','MD - Markdown',None,'MD - Markdown (Directory)'),
               ('front-matter','MD - Markdown + Front Matter',None,'MD - Markdown + Front Matter (Directory)'),
               ('html','HTML - HTML File','archive.html','HTML - HTML document (File)'),
               ('html-directory','HTML - HTML Directory',None,'HTML - HTML document (Directory)')]
    for key, menu, filename, importer in exports:
        if key == 'raw':
            w.append(episode('roundtrip-raw','document export and reimport',[
                step('backup-edit','Save a RAW backup of River survey in $OUTBOX, then rename the working note to "Archived draft" and replace its body with "Draft revision.".',
                     ['The working note is now named Archived draft.', 'The working note displays Draft revision.'],
                     [{'op':'export-raw'},{'op':'title','value':'Archived draft'},{'op':'body','value':'Draft revision.'}],
                     [check('export',format='raw',filename=None),note('Archived draft',body='Draft revision.')]),
                step('restore','Permanently remove Archived draft, then restore the backup by importing the RAW directory $OUTBOX and open River survey.',
                     ['River survey is available again with its original title.', 'Its original river survey heading and paragraphs are restored.'],
                     [{'op':'delete-permanent','title':'Archived draft'},{'op':'import','path':'outbox/','format':'RAW - Joplin Export Directory','title':'River survey','directory':True}],
                     [note('River survey',body=RIVER),check('note-count',title='Archived draft',count=0)],depends=('backup-edit',))]))
            continue
        target='$OUTBOX/'+filename if filename else '$OUTBOX'
        w.append(episode('roundtrip-'+key,'document export and reimport',[
            step('roundtrip',f'Keep a {key.replace("-"," ")} copy of River survey at {target}, then import that copy and open the imported note.',
                 ['The reimported copy is available in the application.', 'The copy preserves the river survey heading and paragraphs.'],
                 [{'op':'roundtrip','format':menu,'filename':filename,'importer':importer}],
                 [check('export',format=key,filename=filename),check('imported-copy',text='Three oak trees',minimum=2)])]))
    w.append(episode('theme-persistence','appearance preferences',[
        step('dark','Select the Dark application theme and return to River survey.',
             ['The application displays the selected dark theme.', 'River survey remains readable.'],
             [{'op':'theme','value':'Dark'},{'op':'note','title':'River survey'}]),
        step('restart','After the application restarts, open River survey and inspect its appearance.',
             ['The selected dark theme is retained.', 'River survey and its content remain available.'],
             [{'op':'note','title':'River survey'}],[note('River survey',body=RIVER)],depends=('dark',),lifecycle='restart'),
        step('light','Change back to the Light application theme.', 'The application displays the selected light theme.',
             [{'op':'theme','value':'Light'}])]))
    w.append(episode('todo-alarm','to-do alarm dialog',[
        step('inspect','Open the alarm editor for Packing list.', 'An alarm date and time can be set for the to-do.',
             [{'op':'click','name':'Set alarm','role':'push button'}],modal=True),
        step('set','Set the alarm to 20 January 2026 at 09:30 UTC.', 'The to-do shows the configured alarm date and time.',
             [{'op':'alarm','date':'20/01/2026','time':'09:30'}],
             [note('Packing list',todo_due=1768901400000)],depends=('inspect',)),
        step('clear','Remove that alarm from Packing list.', 'The to-do again offers to set an alarm.',
             [{'op':'clear-alarm'}],[note('Packing list',todo_due=0)],depends=('set',))],selected='Packing list'))
    w.append(episode('markdown-extended','extended Markdown rendering',[
        step('math','Replace Formatting with the following and view its rendered form:\n```\nEnergy: $E = mc^2$.\n\n$$a^2 + b^2 = c^2$$\n```',
             ['The inline equation is rendered as mathematics with a superscript exponent.', 'The second equation is displayed separately.'],
             [{'op':'body','value':'Energy: $E = mc^2$.\n\n$$a^2 + b^2 = c^2$$'},{'op':'viewer'}]),
        step('footnote','Replace Formatting with the following and view its rendered form:\n```\nA field observation.[^1]\n\n[^1]: Recorded by Ada.\n```',
             ['The observation has a footnote reference.', 'The footnote text Recorded by Ada is available.'],
             [{'op':'editor'},{'op':'body','value':'A field observation.[^1]\n\n[^1]: Recorded by Ada.'},{'op':'viewer'}]),
        step('diagram','Replace Formatting with a Mermaid graph connecting Oak to Elm, then view it. Use this source:\n```\n```mermaid\ngraph LR\n  Oak --> Elm\n```\n```',
             ['The diagram contains Oak and Elm nodes.', 'A directed connection goes from Oak to Elm.'],
             [{'op':'editor'},{'op':'body','value':'```mermaid\ngraph LR\n  Oak --> Elm\n```'},{'op':'viewer'}])],notes=[{'title':'Formatting','body':'Initial text.'}],selected='Formatting'))
    w.append(episode('pdf-attachment','PDF export and attachment',[
        step('export-attach','Export River survey as a PDF to $OUTBOX/survey.pdf, then attach that PDF to Orchard plan.',
             ['Orchard plan contains a link to the survey.pdf attachment.', 'Orchard plan retains its own planning text.'],
             [{'op':'export-pdf','filename':'survey.pdf'},{'op':'note','title':'Orchard plan'},{'op':'attach','path':'outbox/survey.pdf'}],
             [check('export',format='pdf',filename='survey.pdf'),check('attachments',title='Orchard plan',names=['survey.pdf'])])]))
    w.append(episode('whiteboard','whiteboards and note cards',[
        step('create','Create a whiteboard named "Field map" containing a text card that says "Survey the north bank.".',
             ['Field map is available as a whiteboard.', 'Its text card displays Survey the north bank.'],
             [{'op':'new-whiteboard','title':'Field map','text':'Survey the north bank.'}],
             [check('whiteboard',title='Field map',texts=['Survey the north bank.'],groups=0,links=[])]),
        step('edit','Change that card text to "Survey both banks.".', 'The text card displays the revised instruction.',
             [{'op':'whiteboard-text','old':'Survey the north bank.','text':'Survey both banks.'}],
             [check('whiteboard',title='Field map',texts=['Survey both banks.'],groups=0,links=[])],depends=('create',)),
        step('group','Add a group to Field map.', 'The whiteboard contains a visible group container.',
             [{'op':'click','name':'Add a group','role':'push button'}],
             [check('whiteboard',title='Field map',texts=['Survey both banks.'],groups=1,links=[])],depends=('edit',)),
        step('link','Add Orchard plan to Field map as a note card.', 'The whiteboard includes a card for Orchard plan.',
             [{'op':'whiteboard-note','title':'Orchard plan'}],
             [check('whiteboard',title='Field map',texts=['Survey both banks.'],groups=1,links=['Orchard plan'])],depends=('group',))],
        notes=[{'title':'Orchard plan','body':ORCHARD},{'title':'River survey','body':RIVER}],selected='River survey'))
    for item in w:
        if item['id']=='whiteboard': item['budget']['tokens']=2_500_000
        if item['id']=='note-duplicate':item['checkpoints'][0]['checks'][0]['selector']='new-copy'
        if item['id']=='roundtrip-front-matter':
            metadata={'title':'River survey','author':'Ada Lovelace','created':1704164645000,
                      'updated':1738555506000,'tags':['botany','fieldwork']}
            seed=[dict(title='River survey',body=RIVER,author=metadata['author'],
                       user_created_time=metadata['created'],user_updated_time=metadata['updated'],
                       tags=','.join(metadata['tags']))]
            item['setup'][0]['notes']=seed;item['inputs']['notes']=seed
            cp=item['checkpoints'][0]
            cp['goal']+=' Preserve the title, author, created/updated dates and both tags in the Front Matter copy.'
            cp['checks'][0]['metadata']=metadata
            extra=check('metadata-copies',title='River survey',metadata=metadata)
            cp['checks'].append(extra)
            cp['assertions'].append({'id':item['id']+'/roundtrip/data-3-metadata-copies','channel':'backend',
                'method':'program','requirement':'The imported copy preserves explicit author, dates and tags.',
                'check':extra,'aspect':'metadata-copies'})
        if item['id']=='global-search':
            readiness=[{'query':'pear','titles':['Orchard plan']},
                       {'query':'tag:botany','titles':['Orchard plan','River survey']},
                       {'query':'type:todo','titles':['Packing list']}]
            item['setup'][0]['searches']=readiness
            for cp in item['checkpoints']:
                for action in cp['recipe']:
                    if action['op']=='search':
                        action['titles']=next(x['titles'] for x in readiness if x['query']==action['query'])
    import gui_more
    return w+gui_more.build(episode,step,check,note)
