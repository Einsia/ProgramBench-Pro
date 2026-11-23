"""Deterministic notebook fixtures of the Zim suite, created by the verifier before an episode's first goal.

A fixture is an ordinary wiki notebook: page files below the notebook folder of the episode's runtime, uploaded through
the runtime's notebook area. Every page carries the standard header with one fixed creation date, so a fixture is the same
in every run. Pages use the original wiki markup (Content-Type text/x-zim-wiki). Nothing in this module reads the
application; the expected results come from the standard answer's recorded observations.
"""
from __future__ import annotations

NL = '\n'
Q = chr(39)
HEADER = NL.join(['Content-Type: text/x-zim-wiki', 'Wiki-Format: zim 0.6', 'Creation-Date: 2026-01-01T00:00:00+00:00', '', ''])
CONFIG = NL.join(['[Notebook]', 'version=0.4', 'name={name}', 'interwiki=', 'home=Home', 'icon=', 'document_root=', 'shared=True',
                  'endofline=unix', 'disable_trash=False', 'profile=', ''])


def page(*lines):
    """One page file: the standard header, the lines and a final line break."""
    return HEADER + NL.join(lines) + NL


# -- core notebook: links, tags, tasks, lists, verbatim, a journal page and a Unicode path ---------------------------------
CORE = {
    'Home.txt': page('====== Home ======', 'Welcome page with alpha and a link to [[Projects:Alpha]] and [[Notes]].',
                     'External https://example.org/x and tag @start.'),
    'Projects.txt': page('====== Projects ======', 'Index of projects: [[+Alpha]] and [[+Beta]]. gamma appears here once.'),
    'Projects/Alpha.txt': page('====== Alpha ======', 'The alpha project plans a launch. Owner @a @team.',
                               '[ ] TODO write the alpha plan @team <2026-02-01', '[*] done the first step', '', 'Back to [[Home]].'),
    'Projects/Beta.txt': page('====== Beta ======', 'The beta project follows alpha later. GAMMA in capitals. Owner @b @team.',
                              '* bullet one', '* bullet two', '\t* nested bullet', '1. first', '2. second'),
    'Notes.txt': page('====== Notes ======',
                      'Plain notes: **bold** //italic// __marked__ ~~struck~~ and ' + Q * 2 + 'verbatim' + Q * 2 + '.',
                      'Table of words: apple banana cherry. See [[Projects:Beta|the beta page]].',
                      Q * 3, 'code block alpha', Q * 3),
    'Journal/2026/01/15.txt': page('====== 2026-01-15 ======', 'Journal entry about gamma and delta.', '[ ] FIXME check the journal @a'),
    'Café/Naïve_日本語.txt': page('====== Naïve ======',
                                                      'Unicode page: café crème 日本語 delta.'),
}

# -- one page that uses every inline and block markup of the original wiki format ---------------------------------------
FORMATS = {
    'Home.txt': page('====== Home ======', 'See [[Formats]].'),
    'Formats.txt': page(
        '====== Formats ======', '===== Second level =====', '==== Third level ====', '=== Fourth level ===', '== Fifth level ==', '',
        '**strong** //emphasis// __mark__ ~~strike~~ ' + Q * 2 + 'code' + Q * 2 + ' H_{2}O x^{2}', '',
        '* bullet one', '* bullet two', '\t* nested bullet', '1. numbered one', '2. numbered two', 'a. lettered one', 'b. lettered two', '',
        '[ ] open', '[*] done', '[x] not done', '[>] moved', '[<] moved elsewhere', '\t[ ] nested open', '',
        Q * 3, 'verbatim block', '  keeps   spacing', Q * 3, '', '-----', '',
        'Links: [[Home]], [[Home|shown text]], [[+Child]], [[:Formats]], [[#second-level]], https://example.org/page, mailto:a@example.org.',
        'Tags @one @two_words and an image {{./pic.png}} with an anchor ##target.'),
    'Formats/Child.txt': page('====== Child ======', 'A sub page of [[:Formats]].'),
}

# -- task list notebook: checkboxes, labels, tags, priorities and dates ---------------------------------------------------
TASKS = {
    'Home.txt': page('====== Home ======', 'Task overview, see [[Work]] and [[Journal:2026:01:15]].'),
    'Work.txt': page('====== Work ======',
                     '[ ] TODO call the client @phone <2026-03-01', '[ ] FIXME repair the build @dev >2026-01-10 <2026-01-20',
                     '[ ] !! plain high priority task', '[ ] !!! top priority @dev', '[*] done task @dev', '[x] dropped task',
                     '[ ] parent task', '\t[ ] child one', '\t[*] child two', '[ ] waiting for review @waiting'),
    'Journal/2026/01/15.txt': page('====== 2026-01-15 ======', '[ ] TODO journal task due today', '[ ] write the weekly summary @home'),
}

# -- link and rename notebook: pages that link to each other in several ways ---------------------------------------------
LINKS = {
    'Home.txt': page('====== Home ======', 'Start: [[Area:First]] [[Area:Second]] [[:Loose]]'),
    'Area.txt': page('====== Area ======', 'Section page. Children: [[+First]] [[+Second]].'),
    'Area/First.txt': page('====== First ======', 'Next is [[Second]]; up is [[:Area]]; home is [[:Home]].'),
    'Area/Second.txt': page('====== Second ======', 'Back to [[First]] and to [[Area:First]]. A tag @moved.'),
    'Loose.txt': page('====== Loose ======', 'Linked from Home only. Also [[Area:Second|the second page]].'),
}

# -- import inputs (uploaded into the inbox) ---------------------------------------------------------------------------
INPUTS = {
    'plain.txt': page('====== Imported ======', 'Imported text with alpha and //emphasis//.'),
    'second.txt': page('====== Second Import ======', 'Another imported page about gamma.'),
    'unicode.txt': page('====== Café ======', 'Unicode import: naïve 日本語.'),
    'bare.txt': 'bare text without a header' + NL,
    'snippet.txt': 'Snippet line one.' + NL + 'Snippet line two.' + NL,
}

# -- search option notebook: one word inside longer words, in capitals and in a page name; the pages are not in name order ------
SEARCH = {
    'Zeta.txt': page('====== Zeta ======', 'Hunting cat and catalog and CAT in capitals. @Mixed'),
    'Mango/Cat.txt': page('====== Cat ======', 'The cat sat on the mat. @mixed'),
    'Alpha.txt': page('====== Alpha ======', 'cat Cat cat sat twice. @mixed @Other'),
    'Delta.txt': page('====== Delta ======', 'category scatter concatenate only.'),
    'beta.txt': page('====== beta ======', 'The CAT sat. See [[Zeta]].'),
    'Home.txt': page('====== Home ======', 'Start page.'),
}

NOTEBOOKS = {'core': CORE, 'formats': FORMATS, 'tasks': TASKS, 'links': LINKS, 'search': SEARCH}
WORDS = ('alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'theta', 'kappa', 'lambda', 'sigma', 'tau', 'omega')
TAGS = ('red', 'green', 'blue', 'team', 'later')


def bulk(count):
    """count deterministic pages in three sections for volume cases (a fixed linear congruence picks words and tags)."""
    state, pages = 20260115, {'Home.txt': page('====== Home ======', 'Bulk notebook.')}
    for number in range(count):
        state = (state * 1103515245 + 12345) % 2147483648
        picks = [WORDS[(state >> shift) % len(WORDS)] for shift in (3, 7, 11, 15)]
        tag = TAGS[(state >> 19) % len(TAGS)]
        section = ('Red', 'Green', 'Blue')[number % 3]
        link = f'[[:Bulk:{section}:Item{(number + 1) % count:03d}]]' if number % 5 == 0 else ''
        pages[f'Bulk/{section}/Item{number:03d}.txt'] = page(
            f'====== Item {number:03d} ======', ' '.join(picks) + f' item{number:03d} @{tag} {link}'.rstrip())
    return pages


def notebook(key, name=None):
    """Relative file name -> bytes of one fixture notebook, with its notebook.zim."""
    pages = bulk(int(key[len('bulk-'):])) if key.startswith('bulk-') else NOTEBOOKS[key]
    files = {path: text.encode('utf-8') for path, text in pages.items()}
    files['notebook.zim'] = CONFIG.format(name=name or key.replace('-', ' ').title()).encode('utf-8')
    return files


def inputs(*names):
    return {name: INPUTS[name].encode('utf-8') for name in names}


def page_names(key):
    """Page names (colon separated, without markup files) of a fixture notebook."""
    return sorted(path[:-len('.txt')].replace('_', ' ').replace('/', ':') for path in notebook(key) if path.endswith('.txt'))
