'''Export of single markup constructs: one page per construct, exported to every text format, one scored row per exported page file.

Each scenario uploads a notebook with one tiny page per markup construct (a setup row), exports it once in one format and reads the
exported file of every page; a row is the scrubbed text of one exported file, so each row is one distinct observation of how the
product renders one construct in one format.
'''
import export_cases as ex
import fixtures

Q = chr(39)
TAB = chr(9)
BS = chr(92)
DQ = chr(34)
FAMILY = 'export-markup'
FORMATS = (('html', 'Default', 'html'), ('markdown', 'Default', 'md'), ('rst', 'Default', 'rst'), ('latex', 'Article', 'tex'))
SNIPPETS = (
    ('Strong', ('**strong words** around',)),
    ('Emphasis', ('//emphasis words// around',)),
    ('Mark', ('__marked words__ around',)),
    ('Strike', ('~~struck words~~ around',)),
    ('Code', ('inline ' + Q * 2 + 'code words' + Q * 2 + ' here',)),
    ('Subscript', ('H_{2}O formula',)),
    ('Superscript', ('x^{2} power',)),
    ('Nested', ('**strong //both// strong** and __mark ~~strike~~ mark__',)),
    ('Heading2', ('===== Second level =====', 'text below')),
    ('Heading3', ('==== Third level ====', 'text below')),
    ('Heading4', ('=== Fourth level ===', 'text below')),
    ('Heading5', ('== Fifth level ==', 'text below')),
    ('Bullets', ('* one', '* two', TAB + '* nested', '* three')),
    ('Numbers', ('1. one', '2. two', TAB + 'a. sub', '3. three')),
    ('Letters', ('a. first', 'b. second', 'c. third')),
    ('Checkboxes', ('[ ] open', '[*] done', '[x] cancelled', '[>] moved', '[<] elsewhere')),
    ('NestedChecks', ('[ ] parent', TAB + '[*] child done', TAB + '[ ] child open')),
    ('Verbatim', (Q * 3, 'line one', '  indented line', Q * 3)),
    ('Rule', ('before', '-----', 'after')),
    ('PageLink', ('see [[Home]] now',)),
    ('AliasLink', ('see [[Home|the home page]] now',)),
    ('SubLink', ('see [[+Child]] now',)),
    ('AbsoluteLink', ('see [[:Markup:Strong]] now',)),
    ('HeadingLink', ('see [[#second-level]] now',)),
    ('UrlLink', ('visit https://example.org/path?q=1 today',)),
    ('MailLink', ('write mailto:a@example.org today',)),
    ('FileLink', ('open [[./notes/file.txt]] today',)),
    ('Image', ('picture {{./pic.png}} here',)),
    ('Anchor', ('target ##anchorname here',)),
    ('Tags', ('tags @tagone @tag_two here',)),
    ('DatedTask', ('[ ] task @tagone <2026-02-01',)),
    ('Paragraphs', ('first paragraph', '', 'second paragraph', '', '', 'third after two blank lines')),
    ('Unicode', ('café crème 日本語 ñ',)),
    ('Escapes', ('less < greater > and & ampersand say ' + DQ + 'quoted' + DQ,)),
    ('LatexChars', ('100% sure # hash $ dollar _ under ' + BS + ' backslash ~ tilde { brace }',)),
    ('Long', ('long ' * 60,)),
    ('EmptyPage', ()),
    ('Indented', (TAB + 'indented paragraph', TAB + TAB + 'deeper paragraph')),
    ('HeadingStrong', ('===== Heading with **strong** =====',)),
    ('ListMarkup', ('* item with [[Home]]', '* item with **strong**', '1. numbered with //emphasis//')),
    ('CheckMarkup', ('[*] done with **strong** and [[Home]]',)),
    ('LinkInVerbatim', (Q * 3, '[[Home]] **not strong**', Q * 3)),
    ('InlineInCode', ('x ' + Q * 2 + '**not strong**' + Q * 2 + ' y',)),
)


def _files():
    files = {'Home.txt': fixtures.page('====== Home ======', 'Markup notebook.')}
    for name, lines in SNIPPETS:
        files['Markup/' + name + '.txt'] = fixtures.page('====== ' + name + ' ======', *lines)
    files['notebook.zim'] = fixtures.CONFIG.format(name='Markup')
    return {path: text.encode('utf-8') for path, text in files.items()}


def _prepare(ctx):
    ctx.state.clear()
    ctx.state['nb'] = ctx.notebook(_files())
    ctx.cli('index', '-f', ctx.state['nb'])
    return {'pages': len(SNIPPETS)}


def build(suite):
    for fmt, template, ext in FORMATS:
        scenario = 'markup-' + fmt
        suite.add(FAMILY, scenario, 'prepare', _prepare, channel='setup',
                  description='Upload the markup notebook of one page per construct and build its index.')
        suite.add(FAMILY, scenario, 'run', ex._run('mk-' + fmt, fmt, template, ('-r',)), needs=ex._needs,
                  description=f'Export the markup notebook as {fmt} with the {template} template: exit code, printed lines and files written.')
        for name, _lines in SNIPPETS:
            suite.add(FAMILY, scenario, 'page-' + name.lower(), ex._page('Markup/' + name + '.' + ext), needs=ex._ready,
                      description=f'Exported {fmt} text of the page that holds the construct {name}.')
