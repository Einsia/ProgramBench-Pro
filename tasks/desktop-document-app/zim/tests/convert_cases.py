'''Notebook conversion through the command line of the product (convert-notebook): markdown and wiki formats, the extension
option and refusals.

Every scenario uploads its own notebook below a fresh inbox folder (a setup row) and converts it in place. The command is
experimental and runs with the real clock (the runtime lifts the fixed clock for it); its output and the converted files do not
depend on the date, because the creation dates come from the page headers of the fixtures. A scored row is one conversion run
with the file names of the notebook folder afterwards, or the text of one converted file.
'''
import os

import checks
import fixtures

NL = chr(10)
FAMILY = 'convert-notebook'


def _prepare(key):
    def action(ctx):
        ctx.state.clear()
        ctx.state['nb'] = ctx.notebook(fixtures.notebook(key))
        ctx.state['key'] = key
        return {'notebook': key}
    return action


def _needs(ctx):
    return ctx.state['nb']


def _done(ctx):
    return ctx.state['done']


def _folder(ctx):
    return os.path.basename(ctx.state['nb'])


def _names(ctx):
    folder = _folder(ctx)
    return sorted(name[len(folder) + 1:] for name in ctx.listing('inbox', folder))


def _convert(options, brief=False):
    def action(ctx):
        got = ctx.cli('convert-notebook', *options, ctx.state['nb'])
        if got['exit_code'] == 0:
            ctx.state['done'] = True
        run = {'exit_code': got['exit_code']} if brief else checks.run(got, ctx.root)
        return {'run': run, 'files': _names(ctx)}
    return action


def _file(relative):
    def action(ctx):
        text = checks.scrub(ctx.text('inbox', _folder(ctx) + '/' + relative), ctx.root)
        return {'lines': checks.lines(text.rstrip(NL))}
    return action


def _config(ctx):
    text = ctx.text('inbox', _folder(ctx) + '/notebook.zim')
    return {'settings': [line for line in checks.lines(text) if line.startswith('default_file')]}


def _search(query):
    def action(ctx):
        return checks.search(ctx.cli('search', ctx.state['nb'], query), root=ctx.root)
    return action


def build(suite):
    def start(scenario, key):
        suite.add(FAMILY, scenario, 'prepare', _prepare(key), channel='setup', description='Upload the ' + key + ' notebook.')
        return scenario

    def pages(scenario, names, note, requires=()):
        for relative in names:
            suite.add(FAMILY, scenario, 'file-' + relative.replace('/', '-'), _file(relative), needs=_done, requires=requires,
                      description=f'Text of {relative} {note}.')

    s = start('core-markdown', 'core')
    first = suite.add(FAMILY, s, 'run', _convert(('--format', 'markdown')), needs=_needs,
                      description='Convert the core notebook to markdown: exit code, printed lines and the file names afterwards.')
    suite.add(FAMILY, s, 'config', _config, needs=_done,
              description='The notebook configuration records the markdown format and its file extension.')
    pages(s, ('Home.md', 'Notes.md', 'Projects/Alpha.md', 'Projects/Beta.md', 'Journal/2026/01/15.md', 'Café/Naïve_日本語.md'),
          'after the conversion to markdown')
    suite.add(FAMILY, s, 'search', _search('alpha'), needs=_done,
              description='A search of the converted notebook finds the pages that contain the word.')
    suite.add(FAMILY, s, 'back', _convert(('--format', 'zim-wiki'), brief=True), needs=_done, requires=(first,),
              description='Convert the notebook back to the wiki format: exit code and the file names afterwards (counts with the first conversion).')
    pages(s, ('Notes.txt', 'Projects/Alpha.txt'), 'after the round trip back to the wiki format', requires=(first,))

    s = start('formats-markdown', 'formats')
    suite.add(FAMILY, s, 'run', _convert(('--format', 'markdown')), needs=_needs,
              description='Convert the notebook with every inline and block markup to markdown.')
    pages(s, ('Formats.md', 'Formats/Child.md', 'Home.md'), 'of the formats notebook after the conversion')

    s = start('tasks-markdown', 'tasks')
    suite.add(FAMILY, s, 'run', _convert(('--format', 'markdown')), needs=_needs,
              description='Convert the task notebook with checkbox lists, tags and dates to markdown.')
    pages(s, ('Work.md', 'Journal/2026/01/15.md', 'Home.md'), 'of the task notebook after the conversion')

    s = start('extension', 'core')
    suite.add(FAMILY, s, 'run', _convert(('--format', 'markdown', '--extension', '.markdown')), needs=_needs,
              description='Convert to markdown with an explicit file extension: exit code and the file names.')
    suite.add(FAMILY, s, 'config', _config, needs=_done,
              description='The notebook configuration records the chosen file extension.')

    s = start('refusals', 'links')
    good = suite.add(FAMILY, s, 'good', _convert(('--format', 'markdown')), needs=_needs,
                     description='A valid conversion of the notebook to markdown.')
    suite.add(FAMILY, s, 'bad-format', _convert(('--format', 'pdf'), brief=True), needs=_done, requires=(good,),
              description='An unknown target format fails and leaves the converted files as they are (counts with the valid conversion).')
