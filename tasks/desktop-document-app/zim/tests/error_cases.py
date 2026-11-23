'''Error paths of the product command line: an empty search query, a notebook that does not exist, an export without an output location and an export of a page that does not exist.

Each scenario uploads the core notebook (a setup row). A scored row is the exit code and the printed lines of one run (checks.run), or the projection of a positive run. Rows whose result is an error exit or an empty result count together with a positive row of the same scenario, so a candidate that fails or prints nothing everywhere cannot pass them.
'''
import checks
import export_cases as ex
import search_cases as sc


def _search_raw(query):
    def action(ctx):
        return checks.run(ctx.cli('search', ctx.state['nb'], query), ctx.root)
    return action


def _search_missing(ctx):
    return checks.run(ctx.cli('search', ctx.path('inbox', 'no-such-notebook'), 'apple'), ctx.root)


def _export_without_output(ctx):
    return checks.run(ctx.cli('export', ctx.state['nb']), ctx.root)


def build(suite):
    family = scenario = 'search-errors'
    suite.add(family, scenario, 'prepare', sc._prepare('core'), channel='setup',
              description='Upload the core notebook and build its index.')
    word = suite.add(family, scenario, 'word', sc._search('apple'), needs=sc._needs,
                     description='Search the core notebook for apple, a word that occurs on one page: the positive search that the error rows count with.')
    suite.add(family, scenario, 'empty-query', _search_raw(''), needs=sc._needs, requires=(word,),
              description='A search with an empty query fails with an error message (counts with the positive search).')
    suite.add(family, scenario, 'missing-notebook', _search_missing, needs=sc._needs, requires=(word,),
              description='A search of a notebook folder that does not exist fails with an error message (counts with the positive search).')
    family = scenario = 'export-errors'
    ex.prepare(suite, family, scenario, 'core')
    suite.add(family, scenario, 'run-notes', ex._run('err-notes.html', 'html', 'Default', (), page='Notes'), channel='setup',
              description='Export the page Notes to one html file (unscored: the run observation repeats the other single page runs).')
    shown = suite.add(family, scenario, 'text-notes', ex._page(''), needs=ex._ready,
                      description='Text of the html file written for the page Notes: the positive export that the error rows count with.')
    suite.add(family, scenario, 'no-output', _export_without_output, needs=ex._needs, requires=(shown,),
              description='An export without an output location fails with an error message (counts with the page export).')
    suite.add(family, scenario, 'missing-page', ex._run('err-missing.html', 'html', 'Default', (), page='Projects:Nothing'), needs=ex._needs, requires=(shown,),
              description='Exporting a page that does not exist exits without an error and writes no file (counts with the page export).')
