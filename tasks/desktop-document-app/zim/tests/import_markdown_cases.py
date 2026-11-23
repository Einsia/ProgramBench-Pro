'''Import of markdown files through the command line of the product (--format markdown): headings, inline markup, lists, links, code blocks, quotes, rules, tables and plain text.

The scenario uploads the core notebook and eleven markdown files below a fresh inbox folder (a setup row), imports all files below one section with one run and reads the page file of each imported page, so every scored row is one distinct observation of how one markdown construct becomes wiki markup. Creation dates are left out of the projection.
'''
import os

import checks
import fixtures
import import_cases as ic

NL = chr(10)
BT = chr(96)
FAMILY = 'import-markdown'
FILES = (
    ('headings', ('# Top heading', '', '## Second heading', '', '### Third heading', '', 'Plain paragraph under the headings.')),
    ('inline', ('**bold** and *italic* and ' + BT + 'code' + BT + ' and ~~struck~~ words.',)),
    ('lists', ('- one', '- two', '  - nested', '', '1. first', '2. second')),
    ('links', ('A [link text](https://example.org/page) and <https://example.org/auto> and an image ![alt text](pic.png).',)),
    ('codeblock', (BT * 3 + 'python', 'print(1)', BT * 3, '', 'after the block')),
    ('quote', ('> quoted line', '> second quoted line', '', 'normal line')),
    ('rule', ('above', '', '---', '', 'below')),
    ('unicode', ('# Café', '', 'crème brûlée 日本語 ñ')),
    ('math', ('a_b_c and 2*3*4 and snake_case_name words.',)),
    ('headerless', ('Just a line of text without any heading.',)),
    ('table', ('| a | b |', '|---|---|', '| 1 | 2 |')),
)


def _text(lines):
    return NL.join(lines) + NL


def _prepare(ctx):
    ctx.state.clear()
    folder = ctx.notebook(fixtures.notebook('core'))
    inputs = 'in-' + os.path.basename(folder)
    for stem, lines in FILES:
        ctx.upload('inbox', inputs + '/' + stem + '.md', _text(lines).encode('utf-8'))
    ctx.cli('index', '-f', folder)
    ctx.state['nb'] = folder
    ctx.state['inputs'] = inputs
    return {'files': len(FILES)}


def _converted(stem):
    def action(ctx):
        folder = os.path.basename(ctx.state['nb'])
        names = [n for n in ctx.listing('inbox', folder) if n.endswith('/' + stem + '.txt') and '/Md/' in n]
        assert len(names) == 1, 'expected one imported page for ' + stem + ', found ' + str(names)
        return {'page': checks.page_file(ctx.text('inbox', names[0]), dates=False)}
    return action


def build(suite):
    scenario = 'markdown'
    suite.add(FAMILY, scenario, 'prepare', _prepare, channel='setup',
              description='Upload the core notebook and the markdown inputs and build the index.')
    run = suite.add(FAMILY, scenario, 'run', ic._import('Md:', [stem + '.md' for stem, _l in FILES], ('--format', 'markdown')), needs=ic._needs,
                    description='Import eleven markdown files below one section: exit code and the page files of the notebook.')
    for stem, _lines in FILES:
        suite.add(FAMILY, scenario, 'page-' + stem, _converted(stem), needs=ic._imported,
                  description=f'Page file written for the markdown input {stem}.md: header fields and body.')
    suite.add(FAMILY, scenario, 'search', ic._search('Third'), needs=ic._imported,
              description='Text of an imported markdown heading can be found by a search of the notebook.')
    suite.add(FAMILY, scenario, 'bad-format', ic._import('Md:Bad', ['inline.md'], ('--format', 'nonsense'), brief=True), needs=ic._imported, requires=(run,),
              description='An unknown import format is refused or handled without writing a markdown page (counts with the markdown import).')
