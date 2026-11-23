"""Reviewed goals, acceptance conditions, setup and program checks for MarkText.

Program episodes drive the standard answer (and, at compare time, the
candidate) deterministically through the runtime and score the documents it
writes; they carry no frontend points. GUI episodes state a user goal with
frontend acceptance and backend companions; the reference recipe here drives
the pinned standard only and is never the candidate's frontend contract.
The canonical serialized output is captured by the record, not written here.
"""
from __future__ import annotations

import fixtures

from evaluation.contract import files_path


def inbox(key):
    return files_path('inbox', instance=False)


def outbox(key):
    return files_path('outbox', instance=False)


INITIAL = ('Fresh MarkText process with an empty untitled document, an empty DATA_DIR and a private desktop '
           'session; the listed input files are in the inbox before the first goal.')

HINTS = ('The editor is a what-you-see-is-what-you-get Markdown editor: typing Markdown produces formatted content '
         'and the document is saved back as Markdown. The application menu is the button at the top left (or F10). '
         'When a goal names an output file, type exactly that full path into the save dialog and confirm with the '
         'button in its bottom bar. Judge the visible result as a user would; the saved and exported files are '
         'checked separately, so there is no need to reopen them.')

EQUIV = ['Menus, toolbar controls, keyboard shortcuts and the command palette that reach the same command are '
         'equivalent.',
         'Text may be selected with the mouse or the keyboard; the editor body may be focused by clicking it.',
         'Typing a full path into a file dialog is equivalent to browsing to it.']
FORBID = ['Do not use a terminal, other applications, developer tools, or files outside the inbox and outbox.',
          'Do not recreate a missing command by editing the Markdown by hand when the goal asks for a specific '
          'editor command.']


# -- program episodes ---------------------------------------------------------------------------------------------


def markdown_check(name, description):
    return {'kind': 'markdown', 'path': f'inbox/{name}', 'aspect': 'content', 'description': description,
            'expect': {'nonempty': True}}


def program(key, feature, checkpoints, *, inputs=(), setup=()):
    setup_items = ([{'id': 'inputs', 'op': 'upload', 'area': 'inbox', 'files': sorted(set(inputs))}] if inputs else []) \
        + list(setup)
    seen = set()
    for cp in checkpoints:
        cp['depends_on'] = ['setup:' + item['id'] for item in setup_items] + list(cp.get('depends_on', []))
        cp['assertions'] = []
        used = [c['aspect'] for c in cp['checks']]
        for check in cp['checks']:
            artifact = (check.get('path') or check.get('folder') or check['kind']).split('/')[-1].rsplit('.', 1)[0]
            suffix = check['aspect'] if used.count(check['aspect']) == 1 else f"{artifact}-{check['aspect']}"
            aid = f'{key}/{cp["id"]}/{suffix}'
            assert aid not in seen, aid
            seen.add(aid)
            cp['assertions'].append({'id': aid, 'channel': 'backend', 'method': 'program',
                                     'requirement': check['description'], 'check': check})
    return {'id': key, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL,
            'setup': setup_items, 'inputs': {'input_folder': inbox(key), 'output_folder': outbox(key), 'documents': {}},
            'checkpoints': checkpoints}


def roundtrip(key, feature, names):
    """One program episode: open each fixture, mark it modified, save it back and compare the canonical Markdown."""
    checkpoints = []
    for name in names:
        checkpoints.append({
            'id': name,
            'goal': f'Open {name} in the editor and save it unchanged; the document is re-serialized to canonical '
                    'Markdown.',
            'drive': [{'op': 'open', 'files': [name]}, {'op': 'dirty'}, {'op': 'save'}],
            'checks': [markdown_check(name, f'Saving {name} writes MarkText\'s canonical Markdown serialization of '
                                            'the document.')],
        })
    return program(key, feature, checkpoints, inputs=names)


def editing(key, feature, cases):
    """One program episode: open a source document, select its text, apply an editor command by its keyboard
    shortcut, and compare the resulting saved Markdown. Each case is (cid, source_text, select, keys)."""
    checkpoints = []
    setup_files = []
    for cid, source, select, keys in cases:
        fn = f'{cid}.md'
        setup_files.append({'name': fn, 'text': source})
        drive = [{'op': 'open', 'files': [fn]}]
        drive.append({'op': 'select-all'} if select == 'all' else {'op': 'focus'})
        drive += [{'op': 'key', 'key': k} for k in keys]
        drive += [{'op': 'dirty'}, {'op': 'save'}]
        checkpoints.append({
            'id': cid,
            'goal': f'In the open document, apply the {cid} command and save; the document changes accordingly.',
            'drive': drive,
            'checks': [markdown_check(fn, f'The {cid} command transforms the document as MarkText does, saved as '
                                          'Markdown.')],
        })
    setup = [{'id': 'inputs', 'op': 'upload', 'area': 'inbox', 'files': setup_files}]
    return program(key, feature, checkpoints, setup=setup)


def copy_markdown(key, feature, names):
    """One program episode: open each fixture, select all and copy; the clipboard holds the canonical Markdown.

    A different candidate-portable channel than the file save: a document that is not re-serialized on copy (an
    echo of the input) differs from the frozen canonical Markdown of these non-canonical fixtures.
    """
    checkpoints = []
    for name in names:
        checkpoints.append({
            'id': name,
            'goal': f'Open {name}, select the whole document and copy it; the clipboard holds MarkText\'s canonical '
                    'Markdown serialization.',
            'drive': [{'op': 'open', 'files': [name]}, {'op': 'select-all'},
                      {'op': 'key', 'key': 'Control+C', 'settle': 0.9}],
            'checks': [{'kind': 'clipboard-text', 'aspect': 'text',
                        'description': f'Copying {name} places MarkText\'s canonical Markdown of the document on the '
                                       'clipboard.', 'expect': {'nonempty': True}}],
        })
    return program(key, feature, checkpoints, inputs=names)


def copy_html(key, feature, names, *, wait_for_copy=False):
    """One program episode: open each fixture, select all and copy as HTML; the clipboard holds the rendered HTML.

    Covers the rendering of every construct family, including those the round-trip preserves verbatim (emphasis,
    inline code, links, images, thematic breaks, math, raw HTML). The exported body is normalized to a semantic
    tree (no ids/styles/classes), so it is deterministic and candidate-portable.
    """
    checkpoints = []
    for name in names:
        checkpoints.append({
            'id': name,
            'goal': f'Open {name}, select the whole document and copy it as HTML; the clipboard holds the rendered '
                    'HTML of the document.',
            'drive': [{'op': 'open', 'files': [name]}] + (
                [{'op': 'copy-html-ready'}] if wait_for_copy else
                [{'op': 'select-all'}, {'op': 'key', 'key': 'Control+Shift+C', 'settle': 0.9}]),
            'checks': [{'kind': 'clipboard-html', 'aspect': 'body',
                        'description': f'Copying {name} as HTML renders the document structure.'},
                       {'kind': 'clipboard-html', 'aspect': 'text',
                        'description': f'Copying {name} as HTML includes the document text.',
                        'expect': {'nonempty': True}}],
        })
    return program(key, feature, checkpoints, inputs=names)


# -- GUI episodes -------------------------------------------------------------------------------------------------


def gui_checkpoint(cid, goal, acceptance, recipe, checks=(), *, depends=(), lifecycle=None, modal_end=False,
                   requires=None):
    flat = [c for item in checks for c in (item if isinstance(item, list) else [item])]
    cp = {'id': cid, 'goal': goal, 'acceptance': [acceptance] if isinstance(acceptance, str) else list(acceptance),
          'recipe': list(recipe), 'checks': flat, 'depends_on': list(depends)}
    if lifecycle:
        cp['lifecycle'] = lifecycle
    if modal_end:
        cp['modal_end'] = True
    if requires:
        cp['requires'] = {suffix: list(points) for suffix, points in requires.items()}
    return cp


def gui(key, feature, steps, *, inputs=(), opened=(), setup=(), session=None, notes=''):
    setup_items = ([{'id': 'inputs', 'op': 'upload', 'area': 'inbox', 'files': sorted(set(inputs))}] if inputs else []) \
        + list(setup)
    opened_paths = [f'{inbox(key)}/{name}' for name in opened]
    for cp in steps:
        cp['depends_on'] = ['setup:' + item['id'] for item in setup_items] + list(cp['depends_on'])
        cp['assertions'] = []
        for i, text in enumerate(cp['acceptance']):
            suffix = 'visible' if len(cp['acceptance']) == 1 else f'visible-{i + 1}'
            cp['assertions'].append({'id': f'{key}/{cp["id"]}/{suffix}', 'channel': 'frontend', 'method': 'agent',
                                     'requirement': text})
        used = [check['aspect'] for check in cp['checks']]
        for check in cp['checks']:
            artifact = (check.get('path') or check.get('folder') or check['kind']).split('/')[-1].rsplit('.', 1)[0]
            suffix = check['aspect'] if used.count(check['aspect']) == 1 else f"{artifact}-{check['aspect']}"
            cp['assertions'].append({'id': f'{key}/{cp["id"]}/{suffix}', 'channel': 'backend', 'method': 'program',
                                     'requirement': check['description'], 'check': check})
    ids = {a['id'] for cp in steps for a in cp['assertions']}
    for cp in steps:
        for suffix, points in cp.pop('requires', {}).items():
            point = next(a for a in cp['assertions'] if a['id'] == f'{key}/{cp["id"]}/{suffix}')
            point['requires'] = [f'{key}/{cp["id"]}/{p}' if '/' not in p else f'{key}/{p}' for p in points]
            assert all(r in ids for r in point['requires']), point['requires']
    n = len(steps)
    if session is None:
        if opened:
            names = ', '.join(opened)
            session = (f'The application has started and the document(s) {names} are already open in the editor. '
                       'Work on the goals in order. ' + HINTS)
        else:
            session = ('The application has started with an empty untitled document. ' + HINTS)
    return {'id': key, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL,
            'setup': setup_items, 'opened_paths': opened_paths,
            'inputs': {'input_folder': inbox(key), 'output_folder': outbox(key),
                       'documents': {name: {'path': f'{inbox(key)}/{name}'} for name in inputs}},
            'session': session, 'allowed_equivalents': EQUIV, 'forbidden_bypasses': FORBID,
            'budget': {'calls': min(160, 55 + 30 * n), 'seconds': min(1800, 540 + 210 * n),
                       'tokens': min(1_500_000, 500_000 + 250_000 * n)},
            'checkpoints': steps}


# -- build ---------------------------------------------------------------------------------------------------------


def build():
    episodes = []

    # Markdown serialization round-trip, one program episode per normalizing construct family.
    for family, names in fixtures.SAVE_FAMILIES.items():
        episodes.append(roundtrip('serialize-' + family, 'serialization', sorted(names)))

    # Copy-as-Markdown: the same normalizing families through the clipboard channel.
    for family, names in fixtures.SAVE_FAMILIES.items():
        episodes.append(copy_markdown('copymd-' + family, 'clipboard', sorted(names)))

    # Copy-as-HTML rendering: one program episode per construct family (covers constructs preserved verbatim on save).
    for family, names in fixtures.RENDER_FAMILIES.items():
        episodes.append(copy_html('render-' + family, 'rendering', sorted(names), wait_for_copy=family == 'quotes'))

    # Editor commands applied by keyboard shortcut, scored on the saved Markdown.
    P = 'Alpha beta gamma.\n'
    episodes.append(editing('edit-inline', 'editing', [
        ('bold', P, 'all', ['Control+B']),
        ('italic', P, 'all', ['Control+I']),
        ('underline', P, 'all', ['Control+U']),
        ('strikethrough', P, 'all', ['Control+D']),
        ('inline-code', P, 'all', ['Control+Y']),
        ('highlight', P, 'all', ['Control+Shift+H']),
        ('inline-math', P, 'all', ['Control+Shift+M']),
        ('clear-formatting', '**Alpha** and *beta* and `code` text.\n', 'all', ['Control+Shift+R']),
        ('bold-italic', P, 'all', ['Control+B', 'Control+I']),
    ]))
    episodes.append(editing('edit-heading', 'editing', [
        ('heading-1', P, 'all', ['Control+Alt+1']),
        ('heading-2', P, 'all', ['Control+Alt+2']),
        ('heading-3', P, 'all', ['Control+Alt+3']),
        ('heading-4', P, 'all', ['Control+Alt+4']),
        ('heading-5', P, 'all', ['Control+Alt+5']),
        ('heading-6', P, 'all', ['Control+Alt+6']),
        ('heading-upgrade', '## Heading two.\n', 'all', ['Control+plus']),
        ('heading-degrade', '## Heading two.\n', 'all', ['Control+minus']),
        ('heading-join-lines', 'First line.\nSecond line.\n', 'all', ['Control+Alt+1']),
    ]))
    episodes.append(editing('edit-block', 'editing', [
        ('bullet-list', P, 'all', ['Control+H']),
        ('order-list', P, 'all', ['Control+G']),
        ('task-list', P, 'all', ['Control+Shift+X']),
        ('quote-block', P, 'all', ['Control+Shift+Q']),
        ('code-fence', 'const value = 1;\n', 'all', ['Control+Shift+K']),
    ]))

    # GUI episodes: a user goal with visible acceptance and a backend companion on the saved/exported document.
    def md_check(path, desc, **expect):
        return {'kind': 'markdown', 'path': path, 'aspect': 'content', 'description': desc,
                'expect': dict(expect) or {'nonempty': True}}

    k = 'gui-bold'
    episodes.append(gui(k, 'editing', [
        gui_checkpoint('bold', f'Make the whole paragraph bold with the editor\'s Bold command, then save the document '
                       f'as {outbox(k)}/bold.md.',
                       'The paragraph text is shown in bold.',
                       [{'op': 'select-all'}, {'op': 'key', 'key': 'Control+B'}, {'op': 'save-as', 'path': 'outbox/bold.md'}],
                       [md_check('outbox/bold.md', 'The saved document shows the paragraph as bold Markdown.',
                                 nonempty=True, contains=['**'])], requires={'visible': ['content']}),
    ], inputs=['gui-para.md'], opened=['gui-para.md']))

    k = 'gui-heading'
    episodes.append(gui(k, 'editing', [
        gui_checkpoint('heading', 'Turn the paragraph into a second-level heading using the editor\'s heading command, '
                       f'then save as {outbox(k)}/heading.md.',
                       'The text is shown as a large second-level heading instead of ordinary paragraph text.',
                       [{'op': 'select-all'}, {'op': 'key', 'key': 'Control+Alt+2'}, {'op': 'save-as', 'path': 'outbox/heading.md'}],
                       [md_check('outbox/heading.md', 'The saved document starts the text with a level-2 ATX heading.',
                                 nonempty=True, contains=['## '])], requires={'visible': ['content']}),
    ], inputs=['gui-para.md'], opened=['gui-para.md']))

    k = 'gui-list'
    episodes.append(gui(k, 'editing', [
        gui_checkpoint('bullets', 'Turn the three paragraphs into a bulleted list using the editor\'s bullet-list '
                       'command.',
                       'The three lines are shown as a bulleted list.',
                       [{'op': 'select-all'}, {'op': 'key', 'key': 'Control+H'}]),
    ], inputs=['gui-items.md'], opened=['gui-items.md']))

    k = 'gui-quote'
    episodes.append(gui(k, 'editing', [
        gui_checkpoint('quote', 'Turn the paragraph into a block quote using the editor\'s quote command.',
                       'The text is shown as an indented block quote.',
                       [{'op': 'select-all'}, {'op': 'key', 'key': 'Control+Shift+Q'}]),
    ], inputs=['gui-para.md'], opened=['gui-para.md']))

    k = 'gui-type'
    episodes.append(gui(k, 'authoring', [
        gui_checkpoint('type', 'In the empty document, type a level-1 heading reading "Notes" on the first line, then '
                       'on a new paragraph type "First point." Then save the document as '
                       f'{outbox(k)}/typed.md.',
                       'The document shows "Notes" as a large heading followed by a paragraph reading "First point."',
                       [{'op': 'focus'}, {'op': 'type', 'value': '# Notes'}, {'op': 'key', 'key': 'Return'},
                        {'op': 'type', 'value': 'First point.'}, {'op': 'save-as', 'path': 'outbox/typed.md'}],
                       [md_check('outbox/typed.md', 'The saved document has a level-1 heading "Notes" and a paragraph '
                                 '"First point."', nonempty=True, contains=['# Notes', 'First point.'])],
                       requires={'visible': ['content']}),
    ]))

    k = 'gui-save'
    episodes.append(gui(k, 'file', [
        gui_checkpoint('save', f'Save the open document unchanged as {outbox(k)}/saved.md.',
                       'The document still shows its heading "Report Title" and its content unchanged.',
                       [{'op': 'save-as', 'path': 'outbox/saved.md'}],
                       [md_check('outbox/saved.md', 'The saved document keeps the heading and content of the source.',
                                 nonempty=True, contains=['# Report Title', 'bold'])], requires={'visible': ['content']}),
    ], inputs=['gui-rich.md'], opened=['gui-rich.md']))

    k = 'gui-export-html'
    episodes.append(gui(k, 'export', [
        gui_checkpoint('html', f'Export the open document to HTML with the Export command, saving it as '
                       f'{outbox(k)}/doc.html.',
                       'The document still shows its heading "Report Title", the bold and italic text and the list.',
                       [{'op': 'export', 'menu': 'Export as HTML', 'path': 'outbox/doc.html'}],
                       [{'kind': 'html', 'path': 'outbox/doc.html', 'aspect': 'text',
                         'description': 'The exported HTML contains the document\'s heading and body text.',
                         'expect': {'contains': ['Report Title', 'bold']}},
                        {'kind': 'html', 'path': 'outbox/doc.html', 'aspect': 'body',
                         'description': 'The exported HTML renders the document structure (heading, emphasis, list, quote).'}],
                       requires={'visible': ['text', 'body']}),
    ], inputs=['gui-rich.md'], opened=['gui-rich.md']))

    k = 'gui-export-pdf'
    episodes.append(gui(k, 'export', [
        gui_checkpoint('pdf', f'Export the open document to PDF with the Export command, saving it as '
                       f'{outbox(k)}/doc.pdf.',
                       'The document still shows its heading "Report Title" and its content unchanged.',
                       [{'op': 'export', 'menu': 'Export as PDF', 'path': 'outbox/doc.pdf'}],
                       [{'kind': 'pdf', 'path': 'outbox/doc.pdf', 'aspect': 'text',
                         'description': 'The exported PDF contains the document\'s heading and body text.',
                         'expect': {}}],
                       requires={'visible': ['text']}),
    ], inputs=['gui-rich.md'], opened=['gui-rich.md']))

    # More single-goal editing GUI episodes (select the whole paragraph, apply one command, save).
    def edit_gui(key, command, keys, acceptance, backend_desc, contains, source='gui-para.md', backend=True):
        # Block commands that MarkText applies to a whole-paragraph selection leave an operation-dependent trailing
        # empty item (a correct implementation operated differently will not match the exact serialization), so those
        # are judged visibly only (backend=False), without a saved-document check.
        apply = [{'op': 'select-all'}] + [{'op': 'key', 'key': x} for x in keys]
        if backend:
            cp = gui_checkpoint('do', f'Apply the editor\'s {command} command to the whole paragraph, then save the '
                                f'document as {outbox(key)}/out.md.', acceptance,
                                apply + [{'op': 'save-as', 'path': 'outbox/out.md'}],
                                [md_check('outbox/out.md', backend_desc, nonempty=True, contains=contains)],
                                requires={'visible': ['content']})
        else:
            cp = gui_checkpoint('do', f'Apply the editor\'s {command} command to the whole paragraph.', acceptance, apply)
        episodes.append(gui(key, 'editing', [cp], inputs=[source], opened=[source]))

    edit_gui('gui-italic', 'Italic', ['Control+I'], 'The paragraph text is shown in italics.',
             'The saved document wraps the text in italic Markdown.', ['*Alpha'])
    edit_gui('gui-strike', 'Strikethrough', ['Control+D'], 'The paragraph text is shown struck through.',
             'The saved document wraps the text in strikethrough Markdown.', ['~~'])
    edit_gui('gui-underline', 'Underline', ['Control+U'], 'The paragraph text is shown underlined.',
             'The saved document wraps the text in an underline tag.', ['<u>'])
    edit_gui('gui-highlight', 'Highlight', ['Control+Shift+H'], 'The paragraph text is shown highlighted.',
             'The saved document wraps the text in a highlight tag.', ['<mark>'])
    edit_gui('gui-inline-code', 'Inline Code', ['Control+Y'], 'The paragraph text is shown as inline code (monospaced).',
             'The saved document wraps the text in inline code backticks.', ['`Alpha'])
    edit_gui('gui-inline-math', 'Inline Math', ['Control+Shift+M'], 'The paragraph text is shown as an inline math formula.',
             'The saved document wraps the text in inline math dollar signs.', ['$Alpha'])
    edit_gui('gui-ordered-list', 'Ordered List', ['Control+G'], 'The lines are shown as a numbered list.',
             None, None, source='gui-items.md', backend=False)
    edit_gui('gui-task-list', 'Task List', ['Control+Shift+X'], 'The lines are shown as a checkbox task list.',
             None, None, source='gui-items.md', backend=False)
    # Judged visibly only: whether a whole-paragraph Code Fence yields the fence around the text or a paragraph
    # beside an empty fence depends on how the selection is made (an operation-dependent serialization), so the
    # saved Markdown is not checked here; code-fence serialization is covered deterministically by the program
    # edit-block episode and the code-block round-trip and export families.
    edit_gui('gui-code-fence', 'Code Fence', ['Control+Shift+K'], 'The text is shown inside a fenced code block.',
             None, None, source='gui-plain.md', backend=False)
    edit_gui('gui-heading1', 'level-1 heading', ['Control+Alt+1'], 'The text is shown as a large top-level heading.',
             'The saved document starts the text with a level-1 ATX heading.', ['# Alpha'])
    edit_gui('gui-heading3', 'level-3 heading', ['Control+Alt+3'], 'The text is shown as a third-level heading.',
             'The saved document starts the text with a level-3 ATX heading.', ['### Alpha'])

    # Authoring by typing Markdown, which the editor renders.
    k = 'gui-type-emphasis'
    episodes.append(gui(k, 'authoring', [
        gui_checkpoint('type', 'In the empty document type the sentence "This is bold and italic text." and format the '
                       'word "bold" in bold and the word "italic" in italics using the editor, then save as '
                       f'{outbox(k)}/typed.md.',
                       'The sentence is shown with "bold" in bold and "italic" in italics.',
                       [{'op': 'focus'}, {'op': 'type', 'value': 'This is **bold** and *italic* text.'},
                        {'op': 'save-as', 'path': 'outbox/typed.md'}],
                       [md_check('outbox/typed.md', 'The saved document has bold "bold" and italic "italic".',
                                 nonempty=True, contains=['**bold**', '*italic*'])], requires={'visible': ['content']}),
    ]))

    k = 'gui-type-list'
    episodes.append(gui(k, 'authoring', [
        # Judged visibly only: whether the typed list is serialized as a loose or a tight list depends on the exact
        # keystrokes, so the saved Markdown is operation-dependent and is not checked here.
        gui_checkpoint('type', 'In the empty document create a bulleted list with the three items "Apples", "Oranges" '
                       'and "Pears".',
                       'The document shows a bulleted list with the three items Apples, Oranges and Pears.',
                       [{'op': 'focus'}, {'op': 'type', 'value': '- Apples'}, {'op': 'key', 'key': 'Return'},
                        {'op': 'type', 'value': 'Oranges'}, {'op': 'key', 'key': 'Return'},
                        {'op': 'type', 'value': 'Pears'}]),
    ]))

    # Export rendering: open a document, export it to HTML, and score the rendered body (which covers the
    # rendering of constructs the Markdown round-trip preserves verbatim).
    def render_gui(key, source, acceptance, text_contains):
        episodes.append(gui(key, 'export', [
            gui_checkpoint('render', f'Export the open document to HTML with the Export command, saving it as '
                           f'{outbox(key)}/render.html.', acceptance,
                           [{'op': 'export', 'menu': 'Export as HTML', 'path': 'outbox/render.html'}],
                           [{'kind': 'html', 'path': 'outbox/render.html', 'aspect': 'body',
                             'description': 'The exported HTML renders the document structure.'},
                            {'kind': 'html', 'path': 'outbox/render.html', 'aspect': 'text',
                             'description': 'The exported HTML contains the document text.',
                             'expect': {'contains': text_contains}}],
                           requires={'visible': ['body', 'text']})],
            inputs=[source], opened=[source]))

    render_gui('gui-render-table', 'render-table.md',
               'The document shows a table with the columns Name and Age and the rows Alice/30 and Bob/25.',
               ['Name', 'Alice', 'Bob'])
    render_gui('gui-render-nested', 'render-nested.md',
               'The document shows a bulleted list with two nested sub-items under the first item.', ['child a'])
    render_gui('gui-render-links', 'render-links.md',
               'The document shows a hyperlink, an image and inline code.', ['site link'])
    render_gui('gui-render-tasks', 'render-tasks.md',
               'The document shows a task list with checkboxes, the second one checked.', ['first todo'])
    render_gui('gui-render-code', 'render-code.md',
               'The document shows a syntax-highlighted code block.', ['print'])
    render_gui('gui-render-emphasis', 'render-emphasis.md',
               'The document shows bold, italic and struck-through words.', ['bold'])
    render_gui('gui-render-headings', 'render-headings.md',
               'The document shows three headings of decreasing size, a horizontal rule and a paragraph.',
               ['Heading one', 'Heading three'])

    # A two-step editing episode (a visible transform then a save with a backend companion).
    k = 'gui-compose'
    episodes.append(gui(k, 'editing', [
        gui_checkpoint('heading', 'Turn the first paragraph ("First item here.") into a level-2 heading using the '
                       'editor\'s heading command.',
                       'The first line is shown as a second-level heading while the other lines stay as paragraphs.',
                       [{'op': 'focus'}, {'op': 'key', 'key': 'Control+Home'}, {'op': 'key', 'key': 'Shift+End'},
                        {'op': 'key', 'key': 'Control+Alt+2'}]),
        gui_checkpoint('save', f'Save the document as {outbox(k)}/composed.md.',
                       'The document shows the first line as a second-level heading and the other two lines as '
                       'ordinary paragraphs.',
                       [{'op': 'save-as', 'path': 'outbox/composed.md'}],
                       [md_check('outbox/composed.md', 'The saved document starts with a level-2 heading "First item '
                                 'here." followed by the two paragraphs.', nonempty=True,
                                 contains=['## First item here.', 'Second item here.', 'Third item here.'])],
                       requires={'visible': ['content']}),
    ], inputs=['gui-items.md'], opened=['gui-items.md']))

    return episodes
