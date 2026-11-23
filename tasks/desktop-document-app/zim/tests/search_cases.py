'''Page search through the command line of the product: query syntax, keywords, options, scores and result order.

Every scenario uploads its own notebook below a fresh inbox folder (a setup row) and searches that folder; a scored row is one
search run and its projection (checks.search): the result set, or the order and the score groups when the run asks for them.
'''
import checks
import fixtures

CORE = (
    ('word', 'alpha', 'A single word matches the text and the names of pages.'),
    ('or', 'gamma OR delta', 'OR lists the pages that contain either word.'),
    ('phrase', '"alpha project"', 'A quoted phrase matches only pages that contain it.'),
    ('name-prefix', 'Name:Projects', 'The name keyword matches a name segment anywhere in the full page name.'),
    ('tag-keyword', 'tag: a', 'The tag keyword lists the pages that carry a tag.'),
    ('tag-team', '@team', 'A tag shared by several pages lists all of them.'),
    ('tag-exact', '@b@', 'A tag between two at signs must match exactly.'),
    ('links-from', 'links: Home', 'The links keyword lists the pages that link to the given page.'),
    ('content', 'content: gamma', 'The content keyword matches page text.'),
    ('content-case', 'content:= gamma', 'The equals operator makes a content match case sensitive, so GAMMA in capitals does not match.'),
    ('group', '(alpha OR beta) AND gamma', 'Brackets group terms; AND binds tighter than OR without them.'),
    ('not', 'NOT alpha', 'NOT lists the pages that do not contain a word, including section pages.'),
    ('glob-unicode', 'caf*', 'A glob matches the name of a page with accented letters.'),
    ('unicode', '日本語', 'A word in another script matches page text and names.'),
    ('delta', 'delta', 'A word on a journal page and on a page with a Unicode path.'),
    ('journal-glob', 'name: Journal:*', 'A star in a name does not cross name segments.'),
    ('plus', '+apple +cherry', 'A leading plus requires a word, so both words must occur.'),
)

TASKS = (
    ('label', 'TODO', 'A task label is searchable text.'),
    ('tag-dev', '@dev', 'A tag on task lines lists the pages that carry it.'),
    ('summary', 'weekly summary', 'Two words on a journal page.'),
    ('journal-and', 'journal AND task', 'AND over words of one page.'),
)

LINKS = (
    ('links-from', 'links: Area:First', 'Pages that link to a sub page.'),
    ('links-to-second', 'linksto: Area:Second', 'The linksto keyword for a page with a link alias.'),
    ('links-to-home', 'linksto: Home', 'A page that is linked from several places.'),
    ('name-area', 'name: Area', 'The name keyword lists a section and its sub pages.'),
    ('tag-moved', '@moved', 'A tag on one page.'),
    ('text-loose', 'Loose', 'A word that is a page name and appears as a link target.'),
)

SCENARIOS = (('core', CORE), ('tasks', TASKS), ('links', LINKS))


def _prepare(key):
    def action(ctx):
        ctx.state.clear()
        folder = ctx.notebook(fixtures.notebook(key))
        # The index is built on demand; running it first keeps the searches independent of the first build.
        ctx.cli('index', '-f', folder)
        ctx.state['nb'] = folder
        ctx.state['key'] = key
        return {'notebook': key}
    return action


def _needs(ctx):
    return ctx.state['nb']


def _search(query, options=(), ordered=None):
    def action(ctx):
        got = ctx.cli('search', *options, ctx.state['nb'], query)
        return checks.search(got, scores='-s' in options, ordered=ordered, root=ctx.root)
    return action


def build(suite):
    for scenario, rows in SCENARIOS:
        family = 'search-' + scenario
        suite.add(family, scenario, 'prepare', _prepare(scenario), channel='setup',
                  description='Upload the ' + scenario + ' notebook and build its index.')
        ids = {}
        for step, query, text in rows:
            ids[step] = suite.add(family, scenario, step, _search(query), needs=_needs,
                                  description=f'Search the {scenario} notebook for {query}: {text}')
        if scenario == 'core':
            first = next(iter(ids.values()))
            suite.add(family, scenario, 'no-match', _search('zzzzqq'), needs=_needs, requires=(first,),
                      description=f'A word that occurs nowhere finds no page in the {scenario} notebook (counts with the first search).')
