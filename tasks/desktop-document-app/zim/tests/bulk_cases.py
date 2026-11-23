'''Bulk page search through the command line of the product on a generated notebook of 60 pages.

One scenario uploads the generated notebook (fixtures.bulk: three sections, a fixed pseudo random choice of four words and one tag per page, a link on every fifth page) and builds its index (unscored). Each scored row is one search run and its projection (checks.search): the result set, or the score groups when the run asks for an order.
'''
import checks
import fixtures

COUNT = 60
FAMILY = 'bulk-search'
SECTIONS = ('Red', 'Green', 'Blue')


def _prepare(ctx):
    ctx.state.clear()
    folder = ctx.notebook(fixtures.notebook('bulk-%d' % COUNT))
    ctx.cli('index', '-f', folder)
    ctx.state['nb'] = folder
    return {'pages': COUNT}


def _needs(ctx):
    return ctx.state['nb']


def _search(query, options=(), ordered=None):
    def action(ctx):
        got = ctx.cli('search', *options, ctx.state['nb'], query)
        return checks.search(got, scores='-s' in options, ordered=ordered, root=ctx.root)
    return action


def build(suite):
    scenario = 'bulk'

    def row(step, query, text, options=(), ordered=None, requires=()):
        return suite.add(FAMILY, scenario, step, _search(query, options, ordered), needs=_needs, requires=requires,
                         description=f'Search the bulk notebook of {COUNT} pages for {query}: {text}')

    suite.add(FAMILY, scenario, 'prepare', _prepare, channel='setup',
              description=f'Upload the generated bulk notebook of {COUNT} pages and build its index.')
    words = fixtures.WORDS
    tags = fixtures.TAGS
    word_rows, tag_rows = {}, {}
    for word in words:
        found = row('word-' + word, word, 'a word that the generator puts on a share of the pages.')
        word_rows[word] = found
    for tag in tags:
        tag_rows[tag] = row('tag-' + tag, '@' + tag, 'the at sign form of a tag that several pages carry.')
    for section in SECTIONS:
        row('section-' + section.lower(), 'section: Bulk:' + section, 'the pages of one section and the section page itself.')
    for word in words:
        for tag in tags:
            if (word, tag) == ('omega', 'team'):
                continue
            pair = (word_rows[word], tag_rows[tag]) if (word, tag) == ('epsilon', 'blue') else ()
            row(f'and-{word}-{tag}', f'{word} @{tag}', 'a word together with a tag: both must match.', requires=pair)
    for left, right in zip(words, words[1:]):
        row(f'or-{left}-{right}', f'{left} OR {right}', 'either of two words.')
    for word in words:
        row('scored-' + word, word, 'with scores, highest score first.', ('-s', '--sorted'), 'score')
    for number in range(0, COUNT, 5):
        section = SECTIONS[number % 3]
        source = f'Bulk:{section}:Item{number:03d}'
        target = f'Bulk:{section}:Item{(number + 1) % COUNT:03d}'
        row(f'links-{number:03d}', 'links: ' + source, 'the pages that the given page links to.')
        if number != 5:
            row(f'linksto-{number:03d}', 'linksto: ' + target, 'the pages that link to the given page.')
