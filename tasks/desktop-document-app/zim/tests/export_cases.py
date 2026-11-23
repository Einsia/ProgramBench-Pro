'''Page export through the command line of the product: the format and template matrix, export options and refusals.

Every scenario uploads its own notebook below a fresh inbox folder (a setup row) and exports it into a folder of the outbox. A scored
row is one export run (exit code, printed lines, the files written) or the text of one exported file. Texts are projected by
checks.scrub and the version text of the generator is replaced, so the product version is not part of the behaviour.
'''
import checks
import fixtures

COMBOS = (('html', 'Default', 'html'), ('html', 'Default_with_index', 'html'), ('html', 'Presentation', 'html'),
          ('html', 'Print', 'html'), ('html', 'ZeroFiveEight', 'html'), ('html', 'SlideShow_(S5)', 'html'),
          ('markdown', 'Default', 'md'), ('rst', 'Default', 'rst'), ('latex', 'Article', 'tex'), ('latex', 'Report', 'tex'),
          ('latex', 'Part', 'tex'))
SMALL = (('html', 'Default', 'html'), ('markdown', 'Default', 'md'), ('rst', 'Default', 'rst'), ('latex', 'Article', 'tex'))
NOTEBOOKS = (('core', COMBOS), ('formats', SMALL))
# Runs whose observation equals the run of the first template of the same format stay as unscored setup rows (the page rows need their output).
SAME_RUN = {('core', 'html', 'Default_with_index'), ('core', 'html', 'Presentation'), ('core', 'html', 'Print'), ('core', 'html', 'ZeroFiveEight'), ('core', 'latex', 'Report'), ('core', 'latex', 'Part')}


def safe(value):
    return ''.join(c if c.isalnum() else '-' for c in value).strip('-')


def page_files(key, ext):
    '''Output file names of the page files of a fixture notebook (section pages are listed by the run row).'''
    return [path[:-len('.txt')] + '.' + ext for path in sorted(fixtures.notebook(key)) if path.endswith('.txt')]


def project(ctx, text):
    return checks.scrub(text, ctx.root).replace('Zim 0.77.2', 'Zim <version>')


def _prepare(key):
    def action(ctx):
        ctx.state.clear()
        ctx.state['nb'] = ctx.notebook(fixtures.notebook(key))
        ctx.state['key'] = key
        ctx.cli('index', '-f', ctx.state['nb'])
        return {'notebook': key}
    return action


def _needs(ctx):
    return ctx.state['nb']


def _ready(ctx):
    return ctx.state['out']


def _run(target, fmt, template=None, extra=(), page=None, brief=False):
    def action(ctx):
        args = ['-o', ctx.path('outbox', target), '--format', fmt]
        if template:
            args += ['--template', template]
        args += list(extra) + [ctx.state['nb']]
        if page:
            args.append(page)
        got = ctx.cli('export', *args)
        names = sorted(ctx.listing('outbox', target))
        if got['exit_code'] == 0:
            ctx.state['out'] = target
        run = {'exit_code': got['exit_code']} if brief else checks.run(got, ctx.root)
        return {'run': run, 'files': [name[len(target) + 1:] for name in names]}
    return action


def _page(relative):
    def action(ctx):
        out = ctx.state['out']
        name = out + '/' + relative if relative else out
        return {'text': project(ctx, ctx.text('outbox', name))}
    return action


def prepare(suite, family, scenario, key):
    suite.add(family, scenario, 'prepare', _prepare(key), channel='setup',
              description='Upload the ' + key + ' notebook and build its index.')
    return scenario


def matrix(suite):
    for key, combos in NOTEBOOKS:
        family = 'export-' + key
        for fmt, template, ext in combos:
            label = safe(fmt + '-' + template)
            scenario = prepare(suite, family, key + '-' + label, key)
            same = (key, fmt, template) in SAME_RUN
            suite.add(family, scenario, 'run', _run('m-' + key + '-' + label, fmt, template, ('-r',)), needs=None if same else _needs, channel='setup' if same else 'backend',
                      description=f'Export the {key} notebook as {fmt} with the {template} template: exit code, printed lines and files written.')
            for relative in page_files(key, ext):
                suite.add(family, scenario, 'page-' + safe(relative), _page(relative), needs=_ready,
                          description=f'Exported text of {relative} ({fmt}, {template} template, {key} notebook).')


def options(suite):
    family = 'export-options'
    s = prepare(suite, family, 'single-page', 'core')
    suite.add(family, s, 'run', _run('single.html', 'html', 'Default', (), page='Projects:Alpha'), needs=_needs,
              description='Export one page without its sub pages to a single html file.')
    suite.add(family, s, 'text', _page(''), needs=_ready, description='Text of the single exported page file.')
    s = prepare(suite, family, 'section', 'core')
    suite.add(family, s, 'run', _run('section.md', 'markdown', 'Default', ('-r',), page='Projects'), channel='setup',
              description='Export a page with the recursive option as markdown: the run writes one file, not a folder.')
    suite.add(family, s, 'text', _page(''), needs=_ready, description='Text of the file that the recursive export of one page writes.')
    for fmt, template, ext in SMALL:
        s = prepare(suite, family, 'single-file-' + fmt, 'core')
        suite.add(family, s, 'run', _run('all.' + ext, fmt, template, ('-s',)), channel='setup',
                  description=f'Export the whole notebook to one {fmt} file.')
        suite.add(family, s, 'text', _page(''), needs=_ready, description=f'Text of the single {fmt} file with every page.')
    s = prepare(suite, family, 'index-page', 'core')
    suite.add(family, s, 'run', _run('indexed', 'html', 'Default', ('-r', '--index-page', 'Index')), needs=_needs,
              description='Export as html with an index page that lists the exported pages.')
    for relative in ('Index.html', 'Home.html'):
        suite.add(family, s, 'page-' + safe(relative), _page(relative), needs=_ready,
                  description=f'Exported text of {relative} next to the generated index page.')
    s = prepare(suite, family, 'overwrite', 'core')
    suite.add(family, s, 'first', _run('over.html', 'html', 'Default', (), page='Projects:Beta'), channel='setup',
              description='Export one page to an html file that does not exist yet (unscored: the run observation equals the single page run).')
    shown = suite.add(family, s, 'text-first', _page(''), needs=_ready,
                      description='Text of the file that the first export of the page Beta wrote.')
    suite.add(family, s, 'refused', _run('over.html', 'html', 'Default', (), page='Projects:Alpha', brief=True), needs=_ready, requires=(shown,),
              description='Exporting another page to the same file without the overwrite option fails (counts with the text of the first export).')
    suite.add(family, s, 'forced', _run('over.html', 'html', 'Default', ('-O',), page='Home', brief=True), needs=_ready,
              description='The overwrite option replaces the existing export file with another page.')
    suite.add(family, s, 'text-forced', _page(''), needs=_ready, description='Text of the file after the forced export: the page Home replaced the page Beta.')
    s = prepare(suite, family, 'bad-input', 'core')
    good = suite.add(family, s, 'good', _run('good', 'html', 'Default', ('-r',)), needs=_needs,
                     description='A valid export of the notebook as html.')
    suite.add(family, s, 'bad-template', _run('bad-template', 'html', 'Nope', ('-r',), brief=True), needs=_needs, requires=(good,),
              description='An unknown template name fails and writes no page files (counts with the valid export).')


def build(suite):
    matrix(suite)
    options(suite)
