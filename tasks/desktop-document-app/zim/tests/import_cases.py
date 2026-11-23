'''Page import through the command line of the product: single files, sub pages, name clashes and header handling.

Every scenario uploads its own notebook and the import inputs below fresh inbox folders (a setup row), imports through the command
line and observes the page files of the notebook folder. Creation dates are left out of the projection.
'''
import os

import checks
import fixtures

INPUTS = ('plain.txt', 'second.txt', 'unicode.txt', 'bare.txt')
FAMILY = 'import-pages'


def _prepare(key):
    def action(ctx):
        ctx.state.clear()
        folder = ctx.notebook(fixtures.notebook(key))
        inputs = 'in-' + os.path.basename(folder)
        for name, data in fixtures.inputs(*INPUTS).items():
            ctx.upload('inbox', inputs + '/' + name, data)
        ctx.state['nb'] = folder
        ctx.state['inputs'] = inputs
        ctx.cli('index', '-f', folder)
        return {'notebook': key}
    return action


def _needs(ctx):
    return ctx.state['nb']


def _imported(ctx):
    return ctx.state['done']


def _import(page, names, extra=(), brief=False):
    def action(ctx):
        files = [ctx.path('inbox', ctx.state['inputs'] + '/' + n) for n in names]
        got = ctx.cli('import', *extra, ctx.state['nb'], page, *files)
        if got['exit_code'] == 0:
            ctx.state['done'] = True
        folder = os.path.basename(ctx.state['nb'])
        pages = sorted(n[len(folder) + 1:] for n in ctx.listing('inbox', folder) if n.endswith('.txt'))
        run = {'exit_code': got['exit_code']} if brief else checks.run(got, ctx.root)
        return {'run': run, 'pages': pages}
    return action


def _page(relative):
    def action(ctx):
        name = os.path.basename(ctx.state['nb']) + '/' + relative
        return {'page': checks.page_file(ctx.text('inbox', name), dates=False)}
    return action


def _search(query):
    def action(ctx):
        return checks.search(ctx.cli('search', ctx.state['nb'], query), root=ctx.root)
    return action


def build(suite):
    def start(scenario):
        suite.add(FAMILY, scenario, 'prepare', _prepare('core'), channel='setup',
                  description='Upload the core notebook and the import inputs.')
        return scenario

    s = start('single')
    run = suite.add(FAMILY, s, 'run', _import('Imp:One', ['plain.txt']), needs=_needs,
                    description='Import one text file as a new page: exit code and the page files of the notebook.')
    suite.add(FAMILY, s, 'page', _page('Imp/One.txt'), needs=_imported,
              description='The imported page file keeps the text of the input file.')
    suite.add(FAMILY, s, 'search', _search('emphasis'), needs=_imported,
              description='The imported text can be found by a search of the notebook.')
    s = start('clash')
    first = suite.add(FAMILY, s, 'first', _import('Imp:Taken', ['second.txt']), needs=_needs,
                      description='Import a file as a page name that is free.')
    suite.add(FAMILY, s, 'refused', _import('Imp:Taken', ['plain.txt'], brief=True), needs=_imported, requires=(first,),
              description='Importing under a page name that exists fails and keeps the page (counts with the first import).')
    suite.add(FAMILY, s, 'kept', _page('Imp/Taken.txt'), needs=_imported,
              description='After the refused import the page still has the text of the first file.')
    suite.add(FAMILY, s, 'assubpage', _import('Imp:Taken', ['plain.txt'], ('--assubpage',)), needs=_imported,
              description='The assubpage option imports the file below the existing page.')
    s = start('many')
    suite.add(FAMILY, s, 'run', _import('Imp:Many:', ['plain.txt', 'second.txt']), needs=_needs,
              description='Import two files below a section name that ends with a colon.')
    s = start('unicode')
    suite.add(FAMILY, s, 'run', _import('Imp:Uni', ['unicode.txt']), needs=_needs,
              description='Import a file with accented letters and Japanese text.')
    suite.add(FAMILY, s, 'page', _page('Imp/Uni.txt'), needs=_imported,
              description='The imported page keeps accented and Japanese characters.')
    suite.add(FAMILY, s, 'search', _search('日本語'), needs=_imported,
              description='A word in another script from the imported page is found by search.')
    s = start('bare')
    suite.add(FAMILY, s, 'run', _import('Imp:Bare', ['bare.txt']), needs=_needs,
              description='Import a text file that has no wiki header lines.')
    suite.add(FAMILY, s, 'page', _page('Imp/Bare.txt'), needs=_imported,
              description='The page file written for a headerless input: header fields and body.')
    s = start('top')
    suite.add(FAMILY, s, 'run', _import('Fresh', ['second.txt']), needs=_needs,
              description='Import a file as a new top level page.')
    s = start('missing')
    good = suite.add(FAMILY, s, 'good', _import('Imp:Ok', ['plain.txt']), needs=_needs,
                     description='A valid import into the notebook.')
    suite.add(FAMILY, s, 'missing-file', _import('Imp:Gone', ['absent.txt'], brief=True), needs=_imported, requires=(good,),
              description='Importing a file that does not exist fails and creates no page (counts with the valid import).')
