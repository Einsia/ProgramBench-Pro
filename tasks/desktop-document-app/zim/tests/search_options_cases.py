'''Search options on a designed notebook: -w, -c, -s and --sorted on queries whose words sit inside longer words, in capitals and in page names.

The scenario uploads the notebook of six pages (a setup row), which are not in name order, and builds its index. A scored row is one search run and its projection (checks.search). A row stays only when its option changes the result of the query: the result set (-w, -c), the scores (-s) or the printed order (--sorted by name, -s --sorted in score groups). Runs that repeat the observation of another row were left out.
'''
import search_cases as sc

FAMILY = 'search-options'
DQ = chr(34)
ROWS = (
    ('cat-sorted', 'cat', ('--sorted',), 'name', 'the word inside longer words and in capitals, listed by page name in code point order (capitals before lower case).'),
    ('cat-scores', 'cat', ('-s',), None, 'scores: the page named Cat scores highest, pages with several hits score more.'),
    ('cat-scores-sorted', 'cat', ('-s', '--sorted'), 'score', 'scores sorted by score: pages with equal scores form a group.'),
    ('cat-whole', 'cat', ('-w',), None, 'whole words only: the page that has the word only inside longer words drops out.'),
    ('cat-case', 'cat', ('-c',), None, 'case sensitive: only pages with the lower case word.'),
    ('cat-whole-case', 'cat', ('-w', '-c'), None, 'whole words and case sensitive together.'),
    ('cat-whole-scores', 'cat', ('-w', '-s'), None, 'whole words change the scores as well as the result set.'),
    ('cat-case-scores', 'cat', ('-c', '-s'), None, 'case sensitive matching changes the scores of the pages that stay.'),
    ('capital-case', 'Cat', ('-c',), None, 'a capitalised word is matched case sensitively: the page named Cat and the page with Cat in its text.'),
    ('capital-case-scores', 'Cat', ('-c', '-s'), None, 'scores of the case sensitive capitalised word.'),
    ('caps-case', 'CAT', ('-c',), None, 'an upper case word is matched case sensitively.'),
    ('caps-case-scores', 'CAT', ('-c', '-s'), None, 'scores of the case sensitive upper case word.'),
    ('catalog', 'catalog', (), None, 'a word that occurs only as part of a longer word on one page.'),
    ('words-scores', 'cat sat', ('-s',), None, 'two words: the scores of the pages that have both add up.'),
    ('phrase-scores', DQ + 'cat sat' + DQ, ('-s',), None, 'a quoted phrase scores differently from the same two words.'),
    ('or-scores-sorted', 'cat OR scatter', ('-s', '--sorted'), 'score', 'OR with scores sorted by score: equal scores form groups.'),
    ('or-whole-scores', 'cat OR scatter', ('-w', '-s'), None, 'OR with whole words and scores.'),
    ('tag-case-scores', '@Mixed', ('-c', '-s'), None, 'a tag keeps matching whatever its case, even when the case option is set.'),
    ('name-case-hit', 'name: Cat', ('-c',), None, 'the name keyword with the case option finds the page named with a capital.'),
    ('name-case-miss', 'name: cat', ('-c',), None, 'the same keyword in lower case finds no page (counts with the matching capital run).'),
    ('content-scores', 'content: CAT', ('-s',), None, 'the content keyword scores the text only, so the page named Cat loses its name bonus.'),
    ('not-plain', 'NOT cat', (), None, 'NOT lists the pages without the word, including the section page.'),
    ('not-whole', 'NOT cat', ('-w',), None, 'NOT with whole words also lists the page that has the word only inside longer words.'),
    ('not-case', 'NOT cat', ('-c',), None, 'NOT with the case option also lists the page that has the word only in capitals.'),
    ('not-whole-case', 'NOT cat', ('-w', '-c'), None, 'NOT with both options.'),
    ('glob-scores-sorted', 'ca*', ('-s', '--sorted'), 'score', 'a glob with scores sorted by score: five pages in four score groups.'),
)
COMPANION = {'name-case-miss': 'name-case-hit'}


def build(suite):
    scenario = 'options'
    suite.add(FAMILY, scenario, 'prepare', sc._prepare('search'), channel='setup',
              description='Upload the option notebook of six pages and build its index.')
    ids = {}
    for step, query, options, ordered, text in ROWS:
        label = ' '.join(options) or 'plain'
        companion = COMPANION.get(step)
        requires = (ids[companion],) if companion else ()
        ids[step] = suite.add(FAMILY, scenario, step, sc._search(query, options, ordered), needs=sc._needs, requires=requires,
                              description=f'Search the option notebook for {query} ({label}): {text}')
