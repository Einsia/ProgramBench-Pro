'''GUI episodes: developer tool pages driven by an evaluator (JSON diff, regex tester, benchmark, parsers, SQL).'''
import base64
import json

from gbuild import be, cp, episode
from pbuild import blocks, fields, lines, multi, outs, toggles

NL = chr(10)
BT = chr(96)
FENCE = BT * 3
BS = chr(92)
INPUTS = {'type': 'inputs'}


def block(*rows):
    return NL + FENCE + NL + NL.join(rows) + NL + FENCE + NL


def fill(value, label=None, placeholder=None, nth=0):
    step = {'do': 'fill', 'value': value}
    step.update({'label': label} if label is not None else {'placeholder': placeholder})
    if nth:
        step['nth'] = nth
    return step


def prefill(value, label=None, placeholder=None, nth=0):
    target = {'label': label} if label is not None else {'placeholder': placeholder}
    if nth:
        target['nth'] = nth
    return {'op': 'fill', 'target': target, 'value': value}


def click(text, nth=0):
    step = {'do': 'click', 'text': text}
    if nth:
        step['nth'] = nth
    return step


def switch(index=0):
    return {'do': 'click', 'role': 'switch', 'nth': index}


def tick(index):
    return {'do': 'click', 'role': 'checkbox', 'nth': index}


def pick(current, option):
    return {'do': 'choose', 'current': current, 'option': option}


# -- JSON diff ----------------------------------------------------------------------------------------
LEFT, RIGHT = 'Your first JSON', 'Your JSON to compare'
DIFF_SEEN = multi(inputs=fields(LEFT, RIGHT), switches=toggles(), result=lines(start=RIGHT))


def json_diff():
    page = '/json-diff'
    first = json.dumps({'a': 1, 'b': 2})
    second = json.dumps({'a': 1, 'b': 3})
    wide_a = json.dumps({'a': 1, 'b': 2, 'c': 3})
    wide_b = json.dumps({'a': 1, 'b': 5, 'c': 3, 'd': 4})

    def docs(left, right):
        return [fill(left, label=LEFT), fill(right, label=RIGHT)]

    return episode('gui-json-diff', 'diff', [
        cp('changed', 'On the JSON diff page, compare these two documents. First document:' + block(first) + 'Second document:' + block(second),
           'The page shows that the value of b changed from 2 to 3.', docs(first, second),
           [be('result', 'The comparison shows the changed value of b.', DIFF_SEEN)], page=page),
        cp('same', 'On the JSON diff page, compare this document with itself:' + block(first),
           'The page says that the two documents are the same.', docs(first, first),
           [be('result', 'The page reports that the documents are the same.', DIFF_SEEN, ['changed/result'])], page=page, requires=['changed/result']),
        cp('only-changes', 'The JSON diff page compares these two documents. First document:' + block(wide_a) + 'Second document:' + block(wide_b) +
           'Show only the differences between them.',
           'Only the keys b and d are listed; the unchanged keys a and c are hidden.', [switch()],
           [be('result', 'Only the changed and added keys stay in the comparison.', DIFF_SEEN, ['changed/result'])],
           page=page, steps=[prefill(wide_a, label=LEFT), prefill(wide_b, label=RIGHT)], requires=['changed/result']),
        cp('invalid', 'On the JSON diff page, type the text not json as the first document and this document as the second:' + block(second),
           'The page flags the first document as invalid JSON and shows no comparison.', docs('not json', second),
           [be('result', 'The invalid document is flagged and nothing is compared.', DIFF_SEEN, ['changed/result'])], page=page, requires=['changed/result']),
    ])


# -- Regex tester -------------------------------------------------------------------------------------
RE_LABEL, TXT_LABEL = 'Regex to test:', 'Text to match:'
RE_SEEN = multi(result=lines(start='Matches', stop='Sample matching text'))


def regex():
    page = '/regex-tester'
    digit = BS + 'd'

    def run(pattern, text, *ticks):
        return [tick(i) for i in ticks] + [fill(pattern, label=RE_LABEL), fill(text, label=TXT_LABEL)]

    year = '(?<year>' + digit + '{4})-(?<month>' + digit + '{2})'
    return episode('gui-regex', 'tester', [
        cp('digits', 'On the regex tester, find all the numbers in the text a1 b22 c333 with the pattern ' + BT + digit + '+' + BT + '.',
           'The tester lists three matches: 1, 22 and 333.', run(digit + '+', 'a1 b22 c333'),
           [be('matches', 'The matches follow the pattern and the text.', RE_SEEN)], page=page),
        cp('ignore-case', 'On the regex tester, find abc in the text ABC abc Abc, ignoring the letter case.',
           'The tester lists three matches: ABC, abc and Abc.', run('abc', 'ABC abc Abc', 1),
           [be('matches', 'The matches ignore the letter case.', RE_SEEN)], page=page),
        cp('groups', 'On the regex tester, find dates in the text 2024-02 and 1999-12 with the pattern ' + BT + year + BT + '.',
           'The tester lists two matches and shows the groups year and month of each.', run(year, '2024-02 and 1999-12'),
           [be('matches', 'The matches show their named groups.', RE_SEEN)], page=page),
        cp('no-match', 'On the regex tester, search for xyz in the text abc.',
           'The tester says that there is no match.', run('xyz', 'abc'),
           [be('matches', 'No match is listed.', RE_SEEN, ['digits/matches'])], page=page, requires=['digits/matches']),
        cp('invalid', 'On the regex tester, type an open parenthesis as the pattern and abc as the text.',
           'The tester flags the pattern as invalid and lists no match.', run('(', 'abc'),
           [be('matches', 'The invalid pattern is flagged.', RE_SEEN, ['digits/matches'])], page=page, requires=['digits/matches']),
    ])


# -- Benchmark builder --------------------------------------------------------------------------------
BENCH_SEEN = multi(inputs=INPUTS, table=lines(skip=2))


def benchmark():
    page = '/benchmark-builder'
    return episode('gui-benchmark', 'builder', [
        cp('unit', 'On the benchmark builder, set the unit to ms.', 'The means and variances of the ranking carry the unit ms.',
           [fill('ms', label='Unit')], [be('table', 'The unit is added to every mean and variance.', BENCH_SEEN)], page=page),
        cp('rename', 'On the benchmark builder, rename the first suite to Alpha.', 'The ranking lists a suite named Alpha.',
           [fill('Alpha', label='Suite name')], [be('table', 'The new name is shown in the ranking.', BENCH_SEEN)], page=page),
        cp('add-measure', 'On the benchmark builder, add a measure with the value 30 to the first suite.',
           'The first suite counts three samples and its mean is 15.',
           [click('Add a measure'), fill('30', placeholder='Set your measure...', nth=2)],
           [be('table', 'The new measure is counted in the first suite.', BENCH_SEEN)], page=page),
        cp('delete-suite', 'On the benchmark builder, delete the first suite.', 'Only the second suite is left in the ranking.',
           [click('Delete suite')], [be('table', 'Only one suite is ranked.', BENCH_SEEN)], page=page),
        cp('add-suite', 'On the benchmark builder, add a third suite after the first one.', 'Three suites are listed.',
           [click('Add suite')], [be('table', 'A new suite joins the ranking.', BENCH_SEEN, ['delete-suite/table'])], page=page, requires=['delete-suite/table']),
        cp('reset', 'On the benchmark builder, reset the suites so that both are empty.', 'Both suites show zero samples.',
           [click('Reset suites')], [be('table', 'Both suites are empty.', BENCH_SEEN, ['unit/table'])], page=page, requires=['unit/table']),
    ])


# -- JWT and URL parsers ------------------------------------------------------------------------------
def segment(value):
    raw = json.dumps(value, separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


TOKEN = segment({'alg': 'HS256', 'typ': 'JWT'}) + '.' + segment({'sub': '42', 'name': 'Ada Lovelace'}) + '.c2lnbmF0dXJl'
JWT_LABEL = 'JWT to decode'
JWT_SEEN = multi(input=fields(JWT_LABEL), table=lines(start=JWT_LABEL))
URL_LABEL = 'Your url to parse:'
URL_SEEN = multi(input=fields(URL_LABEL), parts=outs(labels=True, allow_empty=True))


def parsers():
    address = 'https://user:secret@example.org:8443/a/b?x=1&y=2#frag'
    return episode('gui-parsers', 'parser', [
        cp('jwt', 'On the JWT parser, decode this token:' + block(TOKEN),
           'The page lists the claim sub with the value 42 and the claim name with the value Ada Lovelace.',
           [fill(TOKEN, label=JWT_LABEL)], [be('table', 'The header and payload claims are listed.', JWT_SEEN)], page='/jwt-parser'),
        cp('jwt-invalid', 'On the JWT parser, type the text not a token.', 'The page flags the text as an invalid token and lists no claim.',
           [fill('not a token', label=JWT_LABEL)], [be('table', 'The invalid token is flagged.', JWT_SEEN, ['jwt/table'])], page='/jwt-parser', requires=['jwt/table']),
        cp('url', 'On the URL parser, split this address into its parts:' + block(address),
           'The page shows the host example.org, the port 8443, the path /a/b, the user user, the password secret and the parameters x and y.',
           [fill(address, label=URL_LABEL)], [be('parts', 'The address is split into its parts.', URL_SEEN)], page='/url-parser'),
        cp('url-invalid', 'On the URL parser, type the text not a url.', 'The page flags the text as an invalid address and shows no part.',
           [fill('not a url', label=URL_LABEL)], [be('parts', 'The invalid address is flagged.', URL_SEEN, ['url/parts'])], page='/url-parser', requires=['url/parts']),
    ])


# -- SQL formatter ------------------------------------------------------------------------------------
SQL_IN = 'Put your SQL query here...'
SQL_SEEN = multi(input=fields(SQL_IN), output=blocks(allow_empty=True))


def sql():
    page = '/sql-prettify'
    query = 'select a, b from t where c = 1 order by a'
    return episode('gui-sql', 'formatter', [
        cp('format', 'On the SQL formatter, format this query:' + block(query),
           'The query is shown over several lines with SELECT, FROM, WHERE and ORDER BY in capital letters.',
           [fill(query, placeholder=SQL_IN)], [be('output', 'The query is laid out over several lines with capital keywords.', SQL_SEEN)], page=page),
        cp('lowercase', 'On the SQL formatter, format this query with its keywords in lower case:' + block(query),
           'The query is shown over several lines with its keywords in lower case.',
           [fill(query, placeholder=SQL_IN), pick('UPPERCASE', 'lowercase')],
           [be('output', 'The keywords are written in lower case.', SQL_SEEN, ['format/output'])], page=page, requires=['format/output']),
        cp('empty', 'On the SQL formatter, clear the query.', 'The page shows no formatted query.',
           [fill('', placeholder=SQL_IN)], [be('output', 'No formatted text is shown.', SQL_SEEN, ['format/output'])], page=page, requires=['format/output']),
    ])


def build():
    return [json_diff(), regex(), benchmark(), parsers(), sql()]
