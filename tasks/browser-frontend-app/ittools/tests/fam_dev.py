'''Program episodes: color converter, regex tester, SQL prettify, meta tag generator and MAC address lookup.'''
from pbuild import NL, bind, blocks, box, case, choose, click, clip, fields, fill, lines, multi, point, reload, toggles, episode

DEFAULT = 'Open the page without typing.'
APOS = chr(39)
BS = chr(92)
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412) + ' ' + chr(10003)
EMOJI = chr(128512)


# -- Color converter ------------------------------------------------------------------------------------
COLOR_PAGE = '/color-converter'
COLOR_FIELDS = ('hex:', 'rgb:', 'hsl:', 'hwb:', 'lch:', 'cmyk:', 'name:')
COLOR_SEEN = multi(colors=fields(*COLOR_FIELDS), text=lines(skip=2))


def color_converter():
    def one(cid, label, value, requirement, requires=()):
        goal = 'Type %s in the %s field.' % (value, label[:-1])
        return case(cid, goal, COLOR_PAGE, [fill(value, label=label)], [point('colors', requirement, COLOR_SEEN, requires)])

    cases = [case('default', DEFAULT, COLOR_PAGE, [], [point('colors', 'The page opens with a sample colour shown in every format.', COLOR_SEEN)])]
    follow = 'The other fields are rewritten from the typed colour.'
    for cid, label, value in (
        ('hex-red', 'hex:', '#ff0000'), ('hex-short', 'hex:', '#f80'), ('hex-alpha', 'hex:', '#ff000080'),
        ('hex-upper', 'hex:', '#3366CC'), ('hex-black', 'hex:', '#000000'), ('hex-white', 'hex:', '#ffffff'),
        ('hex-gray', 'hex:', '#808080'), ('rgb-red', 'rgb:', 'rgb(255, 0, 0)'), ('rgb-mixed', 'rgb:', 'rgb(12, 34, 56)'),
        ('rgb-alpha', 'rgb:', 'rgba(255, 0, 0, 0.5)'), ('hsl-red', 'hsl:', 'hsl(0, 100%, 50%)'),
        ('hsl-blue', 'hsl:', 'hsl(210, 50%, 40%)'), ('hsl-alpha', 'hsl:', 'hsla(120, 100%, 25%, 0.4)'),
        ('hwb-red', 'hwb:', 'hwb(0, 0%, 0%)'), ('lch-red', 'lch:', 'lch(53.24, 104.55, 40.85)'),
        ('cmyk-red', 'cmyk:', 'cmyk(0, 100%, 100%, 0)'), ('name-red', 'name:', 'red'),
        ('name-purple', 'name:', 'rebeccapurple'), ('name-tomato', 'name:', 'tomato'),
    ):
        cases.append(one(cid, label, value, follow))
    maybe = 'The page shows what it makes of the typed colour.'
    for cid, label, value in (
        ('hex-no-hash', 'hex:', 'ff8800'), ('rgb-over', 'rgb:', 'rgb(300, 0, 0)'), ('rgb-spaces', 'rgb:', 'rgb(255 128 0)'),
        ('hwb-spaces', 'hwb:', 'hwb(210 20% 30%)'), ('lch-percent', 'lch:', 'lch(50% 40 200)'),
        ('cmyk-device', 'cmyk:', 'device-cmyk(10% 20% 30% 40%)'), ('name-mixed-case', 'name:', 'Navy'),
        ('name-transparent', 'name:', 'transparent'),
    ):
        cases.append(one(cid, label, value, maybe))
    for cid, label, value in (('bad-hex', 'hex:', '#12345'), ('bad-rgb', 'rgb:', 'rgb(1, 2)'),
                              ('bad-hsl', 'hsl:', 'not a colour'), ('bad-name', 'name:', 'notacolour')):
        cases.append(one(cid, label, value, 'A value that is not a colour is flagged with a message and the other fields keep their values.', ['hex-red/colors']))
    cases.append(case('cleared', 'Clear the hex field.', COLOR_PAGE, [fill('', label='hex:')],
                      [point('colors', 'The page shows what happens to the other fields when one is cleared.', COLOR_SEEN, ['hex-red/colors'])]))
    return episode('color-converter', 'converter', cases)


# -- Regex tester ---------------------------------------------------------------------------------------
REGEX_PAGE = '/regex-tester'
RE_LABEL, TXT_LABEL = 'Regex to test:', 'Text to match:'
G, I, M, S, U, V = 0, 1, 2, 3, 4, 5
D, W = BS + 'd', BS + 'w'
RE_SEEN = multi(inputs=fields(RE_LABEL, TXT_LABEL), boxes=toggles(), result=lines(start='Matches', stop='Sample matching text'))


def regex_tester():
    def run(cid, goal, regex, text, requirement, flags=(), requires=(), page=REGEX_PAGE, before=()):
        steps = [box(i) for i in flags] + list(before)
        if regex is not None:
            steps.append(fill(regex, label=RE_LABEL))
        steps.append(fill(text, label=TXT_LABEL))
        return case(cid, goal, page, steps, [point('matches', requirement, RE_SEEN, requires)])

    listed = 'Every match is listed with its position, its value, its captures and its groups.'
    cases = [case('default', DEFAULT, REGEX_PAGE, [], [point('matches', 'The page opens with both fields empty, the default flags ticked and no match.', RE_SEEN)])]
    lines3 = 'one' + NL + 'two' + NL + 'three'
    rows = [
        ('digits', 'Type a digit pattern and a text with three numbers.', D + '+', 'a1 b22 c333', listed, ()),
        ('captures', 'Type a pattern with two numbered captures.', '(' + D + '+)-(' + D + '+)', '10-20 and 30-40', listed, ()),
        ('named', 'Type a pattern with named groups.', '(?<year>' + D + '{4})-(?<month>' + D + '{2})', '2024-02 and 1999-12', listed, ()),
        ('both', 'Type a pattern with a named group and a numbered capture.', '(?<key>[a-z]+)=(' + D + '+)', 'a=1,bb=22', listed, ()),
        ('alternation', 'Type cat|dog.', 'cat|dog', 'cat dog bird', listed, ()),
        ('lazy', 'Type a lazy pattern for tags.', '<.+?>', '<a><b>', listed, ()),
        ('greedy', 'Type a greedy pattern for tags.', '<.+>', '<a><b>', listed, ()),
        ('backreference', 'Type a pattern with a back reference.', '(' + W + ')' + BS + '1', 'aabbcd', listed, ()),
        ('lookahead', 'Type a pattern with a lookahead.', 'a(?=b)', 'ab ac ab', listed, ()),
        ('anchors', 'Type a pattern anchored at both ends.', '^' + W + '+$', 'one', listed, ()),
        ('boundary', 'Type a pattern with word boundaries.', BS + 'b' + W + '{3}' + BS + 'b', 'cat catalog dog', listed, ()),
        ('many', 'Type a pattern for numbers and a text with twelve of them.', D + ' ', ' '.join(str(n) for n in range(1, 13)) + ' ', listed, ()),
        ('no-match', 'Type a pattern that is not in the text.', 'xyz', 'abc', 'A pattern that is not in the text shows that there is no match.', ()),
        ('empty-text', 'Type a pattern and leave the text empty.', 'a', '', 'An empty text shows that there is no match.', ()),
        ('empty-match', 'Type a pattern that can match nothing.', 'a*', 'baab', 'The page shows what it makes of a pattern that can match an empty string.', ()),
        ('global-off', 'Untick Global search, type a digit pattern and a text with three numbers.', D + '+', 'a1 b22 c333', 'Without the global flag the page shows what it lists for the text.', (G,)),
        ('ignore-case', 'Tick Case-insensitive search, type abc and a text in three cases.', 'abc', 'ABC abc Abc', 'Matches ignore letter case.', (I,)),
        ('case-sensitive', 'Type abc and a text in three cases.', 'abc', 'ABC abc Abc', 'Matches respect letter case.', ()),
        ('multiline', 'Tick Multiline, type a line start pattern and a text of three lines.', '^' + W + '+', lines3, 'Each line start is an anchor.', (M,)),
        ('single-line', 'Type a line start pattern and a text of three lines.', '^' + W + '+', lines3, 'Only the start of the text is an anchor.', ()),
        ('dot-all', 'Type a.b and a text with a line break between the letters.', 'a.b', 'a' + NL + 'b', 'By default a dot also matches a line break.', ()),
        ('dot-no-all', 'Untick Singleline, type a.b and a text with a line break between the letters.', 'a.b', 'a' + NL + 'b', 'Without the Singleline flag a dot does not match a line break.', (S,)),
        ('unicode-on', 'Type a dot and a text with an emoji.', '.', 'a' + EMOJI, 'With the Unicode flag an emoji counts as one character.', ()),
        ('unicode-off', 'Untick Unicode, type a dot and a text with an emoji.', '.', 'a' + EMOJI, 'Without the Unicode flag the page shows what it lists for an emoji.', (U,)),
        ('unicode-sets', 'Untick Unicode, tick Unicode Sets and type a set difference.', '[' + W + '--' + D + ']+', 'abc123def', 'Unicode Sets allows set operations in a class.', (U, V)),
        ('sets-ignored', 'Tick Unicode Sets while Unicode stays ticked and type a set difference.', '[' + W + '--' + D + ']+', 'abc123def', 'The page shows what it lists when both flags are ticked.', (V,)),
        ('case-and-lines', 'Tick Case-insensitive and Multiline and type a line start pattern.', '^a', 'a' + NL + 'A' + NL + 'b', 'Both flags apply together.', (I, M)),
        ('unicode-text', 'Type a word pattern and a text with non-Latin letters.', W + '+', UNI, 'The page shows what it lists for non-Latin text.', ()),
    ]
    for cid, goal, regex, text, requirement, flags in rows:
        cases.append(run(cid, goal, regex, text, requirement, flags))
    for cid, goal, regex in (('bad-paren', 'Type an open parenthesis.', '('), ('bad-bracket', 'Type an open bracket.', '['),
                             ('bad-quantifier', 'Type a lone star.', '*'), ('bad-group-name', 'Type a group name that starts with a digit.', '(?<1a>x)')):
        cases.append(run(cid, goal, regex, 'abc', 'A pattern that is not valid is flagged with a message and no match is listed.', (), ['digits/matches']))
    cases.append(run('query', 'Open the page with the pattern a+ in the address and type a text.', None, 'caaab', 'The pattern from the address is used.', page=REGEX_PAGE + '?regex=a%2B'))
    cases.append(run('query-digits', 'Open the page with a digit pattern in the address and type a text.', None, 'x12y345', 'The pattern from the address is used.', page=REGEX_PAGE + '?regex=%5Cd%2B'))
    cases.append(run('stored', 'Type a digit pattern, reload the page and type a text.', None, '5 55', 'The pattern is kept after reloading the page.', before=[fill(D + '+', label=RE_LABEL), reload()]))
    return episode('regex-tester', 'tester', bind(cases, {'no-match': 'digits/matches', 'empty-text': 'digits/matches', 'empty-match': 'digits/matches', 'dot-no-all': 'dot-all/matches', 'sets-ignored': 'unicode-sets/matches'}))


# -- SQL prettify ---------------------------------------------------------------------------------------
SQL_PAGE = '/sql-prettify'
SQL_IN = 'Put your SQL query here...'
SQL_SEEN = multi(input=fields(SQL_IN), output=blocks())
SQL_EMPTY = multi(input=fields(SQL_IN), output=blocks(allow_empty=True))
STD, UPPER, STANDARD = 'Standard SQL', 'UPPERCASE', 'Standard'
JOIN = 'select a.id, b.name from a inner join b on a.id = b.a_id where a.x > 1 and b.y in (1,2,3) order by a.id desc limit 10'
MIXED = 'Select A From T Where B = 1 And C In (1, 2) Order By A'


def sql_prettify():
    def run(cid, goal, query, requirement, before=(), seen=SQL_SEEN, requires=()):
        steps = list(before) + ([fill(query, placeholder=SQL_IN)] if query is not None else [])
        return case(cid, goal, SQL_PAGE, steps, [point('sql', requirement, seen, requires)])

    shown = 'The query is shown laid out over several lines with its keywords in capitals.'
    cases = [run('default', DEFAULT, None, 'The page opens with a sample query already formatted.')]
    for cid, goal, query in (
        ('join', 'Type a query with a join.', JOIN),
        ('insert', 'Type an insert statement.', 'insert into t (a, b) values (1, ' + APOS + 'x' + APOS + '), (2, ' + APOS + 'y' + APOS + ')'),
        ('update', 'Type an update statement.', 'update t set a = 1, b = ' + APOS + 'x' + APOS + ' where id = 5'),
        ('delete', 'Type a delete with a sub query.', 'delete from t where id in (select id from u where flag = 1)'),
        ('create', 'Type a create table statement.', 'create table t (id int primary key, name varchar(50) not null, created timestamp default current_timestamp)'),
        ('cte', 'Type a query with two common table expressions.', 'with x as (select 1 as a), y as (select 2 as b) select * from x, y'),
        ('group', 'Type a query with grouping.', 'select dept, count(*) as n, avg(salary) from emp group by dept having count(*) > 2 order by n'),
        ('case', 'Type a query with a case expression.', 'select case when a > 1 then ' + APOS + 'big' + APOS + ' else ' + APOS + 'small' + APOS + ' end as size from t'),
        ('comments', 'Type a query with a line comment and a block comment.', 'select 1 -- note' + NL + 'from t /* block */ where x = 1'),
        ('two-statements', 'Type two statements.', 'select 1; select 2;'),
        ('union', 'Type two queries joined by union all.', 'select a from t union all select b from u'),
        ('already-pretty', 'Type a query that is already laid out.', 'SELECT' + NL + '  a,' + NL + '  b' + NL + 'FROM' + NL + '  t;'),
        ('unicode', 'Type a query with non-Latin text.', 'select ' + APOS + UNI + APOS + ' as word from t'),
    ):
        cases.append(run(cid, goal, query, shown))
    for cid, option, query in (
        ('bigquery', 'GCP BigQuery', 'select * from `proj.ds.tbl` where d >= date(2024, 1, 1)'),
        ('db2', 'IBM DB2', 'select * from t fetch first 5 rows only'),
        ('hive', 'Apache Hive', 'select * from t lateral view explode(arr) x as item'),
        ('mariadb', 'MariaDB', 'select `a` from `t` limit 5, 10'),
        ('mysql', 'MySQL', 'select `a` from `t` where b regexp ' + APOS + 'x' + APOS + ' limit 5 offset 10'),
        ('n1ql', 'Couchbase N1QL', 'select * from `bucket` use keys [1, 2]'),
        ('plsql', 'Oracle PL/SQL', 'select a from t where rownum < 5 connect by prior id = parent_id'),
        ('postgresql', 'PostgreSQL', 'select a::int, b from t where c ilike ' + APOS + '%x%' + APOS + ' limit 5'),
        ('redshift', 'Amazon Redshift', 'select a from t order by 1 limit 3'),
        ('spark', 'Spark', 'select * from t distribute by a sort by b'),
        ('sqlite', 'sqlite', 'select * from t where a glob ' + APOS + 'x*' + APOS + ' limit 3'),
        ('tsql', 'SQL Server Transact-SQL', 'select top 10 [a], [b] from [t] with (nolock) where c = @p'),
    ):
        cases.append(run('dialect-' + cid, 'Choose %s and type a query.' % option, query, 'The query is laid out with the rules of the chosen dialect.', [choose(STD, option)]))
    for cid, option in (('lower', 'lowercase'), ('preserve', 'Preserve')):
        cases.append(run('keywords-' + cid, 'Choose %s for the keyword case and type a query in mixed case.' % option, MIXED,
                         'Keywords follow the chosen keyword case.', [choose(UPPER, option)]))
    cases.append(run('keywords-upper', 'Type a query in mixed case.', MIXED, 'Keywords are shown in capitals.'))
    for cid, option in (('left', 'Tabular left'), ('right', 'Tabular right')):
        cases.append(run('indent-' + cid, 'Choose %s for the indent style and type a query with a join.' % option, JOIN,
                         'The query is laid out in the chosen indent style.', [choose(STANDARD, option)]))
    cases.append(run('combined', 'Choose PostgreSQL, lowercase keywords and Tabular right, then type a query with a join.', JOIN,
                     'The dialect, the keyword case and the indent style apply together.',
                     [choose(STD, 'PostgreSQL'), choose(UPPER, 'lowercase'), choose(STANDARD, 'Tabular right')]))
    cases.append(run('empty', 'Clear the query.', '', 'An empty query shows no formatted text.', (), SQL_EMPTY, ['join/sql']))
    cases.append(run('open-quote', 'Type a query with a quote that is never closed.', 'select ' + APOS + 'abc from t',
                     'The page shows what it makes of a query it cannot read.', (), SQL_EMPTY, ['join/sql']))
    return episode('sql-prettify', 'formatter', cases)


# -- Meta tag generator ---------------------------------------------------------------------------------
META_PAGE = '/og-meta-generator'
META_SEEN = multi(tags=blocks())
TITLE_PH = 'Enter the title of your website...'
DESC_PH = 'Enter the description of your website...'
URL_PH = 'Enter the url of your website...'
IMG_PH = 'The url of your website social image...'
ALT_PH = 'The alternative text of your website social image...'
WIDTH_PH = 'Width in px of your website social image...'
HEIGHT_PH = 'Height in px of your website social image...'
SITE_PH = 'The name of the Twitter account of the site (ex: @ittoolsdottech)...'
CREATOR_PH = 'The name of the Twitter account of the creator (ex: @cthmsst)...'
CARD = 'Summary with large image'


def meta_tag_generator():
    def run(cid, goal, steps, requirement):
        return case(cid, goal, META_PAGE, steps, [point('tags', requirement, META_SEEN)])

    def texts(*pairs):
        return [fill(value, placeholder=ph) for ph, value in pairs]

    cases = [run('default', DEFAULT, [], 'The page opens with the tags of a website with a large image Twitter card.')]
    cases += [
        run('title', 'Type a title.', texts((TITLE_PH, 'My Site')), 'The title is written into the title and social tags.'),
        run('description', 'Type a description.', texts((DESC_PH, 'A short description of the site')), 'The description is written into the tags.'),
        run('url', 'Type a page address.', texts((URL_PH, 'https://example.org/page')), 'The address is written into the tags.'),
        run('general', 'Type a title, a description and a page address.', texts((TITLE_PH, 'My Site'), (DESC_PH, 'About the site'), (URL_PH, 'https://example.org/')),
            'The three general fields appear together.'),
        run('special', 'Type a title with an ampersand, an apostrophe and angle brackets.', texts((TITLE_PH, 'Tom & Jerry' + APOS + 's <best> show')),
            'Special characters are written into the tags the way the page escapes them.'),
        run('unicode', 'Type a title with non-Latin characters.', texts((TITLE_PH, UNI)), 'Non-Latin characters are kept in the tags.'),
        run('image', 'Type an image address, an alternative text, a width and a height.',
            texts((IMG_PH, 'https://example.org/og.png'), (ALT_PH, 'A picture'), (WIDTH_PH, '1200'), (HEIGHT_PH, '630')), 'The image fields are written into the tags.'),
        run('twitter-accounts', 'Type a Twitter site account and a creator account.', texts((SITE_PH, '@site'), (CREATOR_PH, '@maker')),
            'The accounts are written into the Twitter tags.'),
        run('card-summary', 'Choose the Summary card type.', [choose(CARD, 'Summary')], 'The Twitter card tag follows the chosen card type.'),
        run('card-app', 'Choose the Application card type.', [choose(CARD, 'Application')], 'The Twitter card tag follows the chosen card type.'),
        run('card-player', 'Choose the Player card type.', [choose(CARD, 'Player')], 'The Twitter card tag follows the chosen card type.'),
        run('everything', 'Fill the general, image and Twitter fields and choose the Summary card type.',
            texts((TITLE_PH, 'My Site'), (DESC_PH, 'About the site'), (URL_PH, 'https://example.org/'), (IMG_PH, 'https://example.org/og.png'), (SITE_PH, '@site'))
            + [choose(CARD, 'Summary')], 'All the sections apply together.'),
    ]
    kinds = (
        ('article', 'Article', [('Writers of the article...', 'Jane Doe'), ('A high-level section name. E.g. Technology..', 'Technology'), ('When the article was first published...', '2024-02-29')]),
        ('book', 'Book', [('Who wrote this book...', 'John Smith'), ('The International Standard Book Number...', '9781234567897')]),
        ('profile', 'Profile', [('Enter the first name of the person...', 'Ada'), ('Enter the last name of the person...', 'Lovelace')]),
        ('song', 'Song', [('The duration of the song...', '215'), ('The album this song is from...', 'https://example.org/album')]),
        ('album', 'Music album', [('The song on this album...', 'https://example.org/song'), ('The musician that made this song...', 'https://example.org/artist')]),
        ('playlist', 'Playlist', [('The creator of this playlist...', 'https://example.org/user')]),
        ('radio', 'Radio station', [('The creator of this radio station...', 'https://example.org/dj')]),
        ('movie', 'Movie', [('Tag words associated with this movie...', 'action'), ('The date the movie was released...', '2024-01-01')]),
        ('episode', 'Episode', [('Which series this episode belongs to...', 'https://example.org/series')]),
        ('tv-show', 'TV show', [('Tag words associated with this movie...', 'drama')]),
        ('other-video', 'Other video', [('Tag words associated with this movie...', 'misc')]),
    )
    for cid, option, pairs in kinds[:3]:
        cases.append(run('type-' + cid, 'Choose the page type %s and fill its extra fields.' % option, [choose('Website', option)] + texts(*pairs),
                         'The page type is written into the tags together with the extra fields of that type.'))
        cases.append(run('type-only-' + cid, 'Choose the page type %s.' % option, [choose('Website', option)], 'The page type is written into the tags.'))
    cases.append(run('type-reset', 'Choose Article, type an author, then choose Book.',
                     [choose('Website', 'Article')] + texts(('Writers of the article...', 'Jane Doe')) + [choose('Article', 'Book')],
                     'Changing the page type clears the fields of the previous type.'))
    return episode('meta-tag-generator', 'generator', bind(cases, {'type-reset': 'type-article/tags'}))


# -- MAC address lookup ---------------------------------------------------------------------------------
MAC_PAGE = '/mac-address-lookup'
MAC_LABEL = 'MAC address:'
MAC_SEEN = multi(input=fields(MAC_LABEL), text=lines(skip=2))


def mac_address_lookup():
    def one(cid, goal, mac, requirement, after=(), seen=MAC_SEEN, requires=()):
        return case(cid, goal, MAC_PAGE, [fill(mac, label=MAC_LABEL)] + list(after), [point('vendor', requirement, seen, requires)])

    shown = 'The vendor of the address is looked up from its first three bytes.'
    cases = [case('default', DEFAULT, MAC_PAGE, [], [point('vendor', 'The page opens with an example address and its vendor.', MAC_SEEN)])]
    for cid, mac in (('cisco', '00:00:0C:12:34:56'), ('vmware', '00:50:56:AB:CD:EF'), ('virtualbox', '08:00:27:11:22:33'),
                     ('hyperv', '00:15:5D:01:02:03'), ('raspberry', 'B8:27:EB:00:00:01'), ('google', '3C:5A:B4:00:00:01'),
                     ('apple', 'F0:18:98:00:00:01'), ('lowercase', '00:50:56:ab:cd:ef'), ('dashes', '00-50-56-AB-CD-EF'),
                     ('three-bytes', '00:50:56'), ('spaces', '  00:50:56:AB:CD:EF  '), ('unknown', '02:00:00:00:00:01')):
        cases.append(one(cid, 'Type %s.' % mac.strip(), mac, shown))
    cases.append(one('copy', 'Type a known address and press Copy vendor info.', '00:50:56:AB:CD:EF', 'The vendor details are copied to the clipboard.',
                     [click('Copy vendor info')], multi(copied=clip(), input=fields(MAC_LABEL)), ['vmware/vendor']))
    for cid, goal, mac in (('bad-words', 'Type text that is not an address.', 'not a mac'), ('bad-one-byte', 'Type 00:50.', '00:50'),
                           ('bad-no-separator', 'Type an address without separators.', '005056abcdef'), ('bad-dots', 'Type an address with dots.', '0050.56ab.cdef'),
                           ('bad-hex', 'Type an address with letters outside the hexadecimal range.', 'zz:zz:zz:zz:zz:zz'), ('empty', 'Clear the address.', '')):
        cases.append(one(cid, goal, mac, 'An address that is not valid is flagged with a message.', (), MAC_SEEN, ['vmware/vendor']))
    return episode('mac-address-lookup', 'lookup', cases)


def build():
    return [color_converter(), regex_tester(), sql_prettify(), meta_tag_generator(), mac_address_lookup()]
