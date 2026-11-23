'''Export with custom template files through the command line of the product: page and loop variables, IF and ELSE, the single file mode, a page argument, other formats, unknown names and broken syntax.

One scenario uploads the core notebook and nine template files below fresh inbox folders (a setup row) and exports with --template and the absolute path of a template file. A run whose observation (exit code, printed lines, files written) repeats a run of another family is an unscored setup row; a scored row is the scrubbed text of one exported file (the version text of the generator is replaced) or a run with a distinct observation.
'''
import os

import checks
import export_cases as ex
import fixtures

NL = chr(10)
DQ = chr(34)
FAMILY = 'export-templates'
SCENARIO = 'templates'


def tpl(*lines):
    return NL.join(lines) + NL


TEMPLATES = {
    'basic.html': tpl('HEAD [% title %] [% generator.name %]', '[% FOREACH page IN pages %]PAGE:[% page.name %]|[% page.title %]', '[% page.body %]', '[% END %]'),
    'if.html': tpl('[% FOREACH page IN pages %][% IF page.name == ' + DQ + 'Home' + DQ + ' %]HOME:[% page.title %][% ELSE %]OTHER:[% page.name %][% END %]', '[% END %]'),
    'loop.html': tpl('[% FOREACH page IN pages %][% loop.count %]/[% loop.size %] i=[% loop.index %] first=[% loop.first %] last=[% loop.last %] odd=[% loop.odd %] [% page.name %]', '[% END %]'),
    'attrs.html': tpl('[% FOREACH page IN pages %][% page.name %]|[% page.basename %]|[% page.namespace %]|[% page.heading %]', '[% END %]'),
    'content.html': tpl('[% FOREACH page IN pages %][% page.content %]', '[% END %]'),
    'nopages.html': tpl('no loop here [% title %]'),
    'unknown.html': tpl('[% FOREACH page IN pages %][% nonexistent %]|[% page.nonexistent %]', '[% END %]'),
    'broken.html': tpl('[% FOREACH page IN pages %]open'),
    'plain.txt': tpl('[% FOREACH page IN pages %]== [% page.name %] ==', '[% page.body %]', '[% END %]'),
}


def _prepare(ctx):
    ctx.state.clear()
    folder = ctx.notebook(fixtures.notebook('core'))
    inputs = 'tpl-' + os.path.basename(folder)
    for name, text in TEMPLATES.items():
        ctx.upload('inbox', inputs + '/' + name, text.encode('utf-8'))
    ctx.cli('index', '-f', folder)
    ctx.state['nb'] = folder
    ctx.state['tpl'] = inputs
    return {'templates': len(TEMPLATES)}


def _run(target, fmt, template, extra=(), page=None):
    def action(ctx):
        args = ['-o', ctx.path('outbox', target), '--format', fmt, '--template', ctx.path('inbox', ctx.state['tpl'] + '/' + template)]
        args += list(extra) + [ctx.state['nb']]
        if page:
            args.append(page)
        got = ctx.cli('export', *args)
        names = sorted(ctx.listing('outbox', target))
        if got['exit_code'] == 0:
            ctx.state['out'] = target
        return {'run': checks.run(got, ctx.root), 'files': [name[len(target) + 1:] for name in names]}
    return action


def build(suite):
    def add_run(step, target, fmt, template, extra=(), page=None, text=''):
        suite.add(FAMILY, SCENARIO, step, _run(target, fmt, template, extra, page), channel='setup', description=text)

    def add_text(step, relative, text):
        return suite.add(FAMILY, SCENARIO, step, ex._page(relative), needs=ex._ready, description=text)

    suite.add(FAMILY, SCENARIO, 'prepare', _prepare, channel='setup', description='Upload the core notebook and the template files and build the index.')
    add_run('run-basic', 't-basic', 'html', 'basic.html', ('-r',), text='Export the core notebook as html with a custom template that prints the title, the generator name, the page name, the page title and the page body.')
    first = add_text('basic-home', 'Home.html', 'Exported text of Home.html with the custom basic template: header line, page name, page title and body.')
    add_text('basic-alpha', 'Projects/Alpha.html', 'Exported text of Projects/Alpha.html with the custom basic template: the title of a page below a section is its own name.')
    add_text('basic-notes', 'Notes.html', 'Exported text of Notes.html with the custom basic template: inline markup and a code block in the body.')
    add_run('run-if', 't-if', 'html', 'if.html', ('-r',), text='Export the core notebook with a custom template that has an IF and an ELSE branch on the page name.')
    add_text('if-home', 'Home.html', 'The IF branch of the custom template applies to the page named Home.')
    add_text('if-alpha', 'Projects/Alpha.html', 'The ELSE branch of the custom template applies to every other page.')
    add_run('run-attrs', 't-attrs', 'html', 'attrs.html', ('-r',), text='Export the core notebook with a custom template that prints the name, base name, namespace and heading of each page.')
    add_text('attrs-home', 'Home.html', 'Page attributes of a top level page: the namespace is empty.')
    add_text('attrs-alpha', 'Projects/Alpha.html', 'Page attributes of a page below a section: base name and namespace.')
    add_text('attrs-unicode', 'Café/Naïve_日本語.html', 'Page attributes of a page whose name has accented and Japanese characters.')
    add_run('run-content', 't-content', 'html', 'content.html', ('-r',), text='Export the core notebook with a custom template that prints only the content of each page.')
    add_text('content-home', 'Home.html', 'The content variable holds the page with its first heading, without any template text.')
    add_run('run-nopages', 't-nopages', 'html', 'nopages.html', ('-r',), text='Export the core notebook with a custom template that has no loop over the pages.')
    add_text('nopages-notes', 'Notes.html', 'A template without a loop is written once for every exported page with the title of that page.')
    suite.add(FAMILY, SCENARIO, 'run-unknown', _run('t-unknown', 'html', 'unknown.html', ('-r',)), needs=ex._needs, requires=(first,),
              description='A custom template with names that do not exist prints warnings and still writes the files (counts with the first custom template text).')
    add_text('unknown-home', 'Home.html', 'Names that do not exist in a custom template print as None.')
    add_run('run-loop', 't-loop.html', 'html', 'loop.html', ('-s',), text='Export the whole core notebook to one file with a custom template that prints the loop variables.')
    add_text('loop-all', '', 'Loop counters of the single file export: count, size, index, first, last and odd for every page, in the order of the pages.')
    add_run('run-all', 't-all.html', 'html', 'basic.html', ('-s',), text='Export the whole core notebook to one file with the custom basic template.')
    add_text('all-basic', '', 'Single file export with the custom basic template: the title is the name of the notebook and the links point to anchors in the same file.')
    add_run('run-page', 't-page.html', 'html', 'basic.html', (), 'Projects:Alpha', text='Export one page with the custom basic template.')
    add_text('page-alpha', '', 'Text of the single page exported with the custom basic template.')
    for fmt, ext in (('markdown', 'md'), ('rst', 'rst'), ('latex', 'tex')):
        add_run('run-' + fmt, 't-' + fmt, fmt, 'plain.txt', ('-r',), text=f'Export the core notebook as {fmt} with a custom plain template.')
        add_text('plain-' + fmt, 'Home.' + ext, f'Home page exported as {fmt} through the custom plain template: the body is written in the chosen format.')
    suite.add(FAMILY, SCENARIO, 'run-broken', _run('t-broken', 'html', 'broken.html', ('-r',)), needs=ex._needs, requires=(first,),
              description='A custom template with an unterminated loop fails with an error message and writes no page files (counts with the first custom template text).')
