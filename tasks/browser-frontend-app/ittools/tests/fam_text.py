'''Program episodes: math evaluator, chmod calculator, list converter, lorem ipsum generator, string obfuscator.'''
from pbuild import NL, bind, blocks, box, case, changed, choose, click, clip, copy_after, fields, fill, lines, multi, outs, point, reload, remember, shape, switch, toggles, episode

DEFAULT = 'Open the page without typing.'
INPUTS = {'type': 'inputs'}
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412) + ' ' + chr(10003)
APOS = chr(39)


# -- Math evaluator -------------------------------------------------------------------------------------
MATH_PAGE = '/math-evaluator'
MATH_IN = 'Your math expression (ex: 2*sqrt(6) )...'
MATH_SEEN = multi(input=INPUTS, result=lines(skip=2))


def math_evaluator():
    def one(cid, goal, text, requirement, requires=()):
        return case(cid, goal, MATH_PAGE, [fill(text, placeholder=MATH_IN)], [point('result', requirement, MATH_SEEN, requires)])

    shown = 'The value of the expression is shown in a result card.'
    refused = 'An expression that cannot be evaluated shows no result card.'
    cases = [
        case('default', DEFAULT, MATH_PAGE, [], [point('result', 'The page opens with an empty expression and no result card.', MATH_SEEN)]),
        one('sum', 'Type 1+2*3.', '1+2*3', 'Multiplication binds tighter than addition.'),
    ]
    plain = [
        ('parentheses', 'Type (1+2)*3.', '(1+2)*3'),
        ('sqrt', 'Type 2*sqrt(6).', '2*sqrt(6)'),
        ('trig', 'Type sin(pi/2) + cos(0).', 'sin(pi/2) + cos(0)'),
        ('power', 'Type 2^10.', '2^10'),
        ('factorial', 'Type 5!.', '5!'),
        ('modulo', 'Type 17 mod 5.', '17 mod 5'),
        ('round', 'Type round(2.5678, 2).', 'round(2.5678, 2)'),
        ('log', 'Type log(1000, 10).', 'log(1000, 10)'),
        ('max-abs', 'Type max(abs(-7), 3, 5).', 'max(abs(-7), 3, 5)'),
        ('constant', 'Type e^2.', 'e^2'),
        ('zero', 'Type 0.', '0'),
        ('negative-power', 'Type -3^2.', '-3^2'),
        ('large', 'Type 123456789 * 987654321.', '123456789 * 987654321'),
        ('huge-power', 'Type 2^100.', '2^100'),
        ('scientific', 'Type 1e3 + 1.', '1e3 + 1'),
        ('decimal', 'Type 0.1 + 0.2.', '0.1 + 0.2'),
        ('infinity', 'Type 1/0.', '1/0'),
        ('not-a-number', 'Type 0/0.', '0/0'),
        ('complex', 'Type sqrt(-4).', 'sqrt(-4)'),
        ('unit', 'Type 2 inch to cm.', '2 inch to cm'),
        ('unit-sum', 'Type 1 km + 500 m.', '1 km + 500 m'),
        ('determinant', 'Type det([1, 2; 3, 4]).', 'det([1, 2; 3, 4])'),
        ('matrix-product', 'Type [1, 2; 3, 4] * [5; 6].', '[1, 2; 3, 4] * [5; 6]'),
        ('comparison', 'Type 5 > 3 and 2 > 4.', '5 > 3 and 2 > 4'),
        ('assignment', 'Type x = 4 and x * 2 on two lines.', 'x = 4' + NL + 'x * 2'),
        ('two-lines', 'Type 1 + 1 and 2 + 2 on two lines.', '1 + 1' + NL + '2 + 2'),
        ('spaces', 'Type 1 +    2 with extra spaces.', '1 +    2'),
    ]
    for cid, goal, text in plain:
        cases.append(one(cid, goal, text, shown))
    bad = (('undefined-name', 'Type notdefined + 1.', 'notdefined + 1'), ('syntax', 'Type 2 + with nothing after it.', '2 +'),
           ('unknown-function', 'Type nosuchfunction(3).', 'nosuchfunction(3)'), ('unit-clash', 'Type 2 inch + 3 kg.', '2 inch + 3 kg'))
    for cid, goal, text in bad:
        cases.append(one(cid, goal, text, refused, ['sum/result']))
    return episode('math-evaluator', 'calculator', cases)


# -- Chmod calculator -----------------------------------------------------------------------------------
CHMOD_PAGE = '/chmod-calculator'
CHMOD_SEEN = multi(result=lines(skip=2), command=outs(), boxes=toggles())


def ticks(mode):
    '''Box numbers for a symbolic mode: the boxes run row by row (read, write, execute), each row owner, group, public.'''
    return [row * 3 + col for col in range(3) for row in range(3) if mode[col * 3 + row] != '-']


def chmod_calculator():
    def one(cid, mode):
        goal = 'Tick the boxes that make up %s.' % mode
        return case(cid, goal, CHMOD_PAGE, [box(i) for i in ticks(mode)],
                    [point('result', 'The octal number, the symbolic form and the chmod command follow the ticked boxes.', CHMOD_SEEN)])

    cases = [case('default', DEFAULT, CHMOD_PAGE, [], [point('result', 'The page opens with no box ticked and the mode 000.', CHMOD_SEEN)])]
    modes = (('owner-all', 'rwx------'), ('group-all', '---rwx---'), ('public-all', '------rwx'), ('all', 'rwxrwxrwx'),
             ('mode-755', 'rwxr-xr-x'), ('mode-644', 'rw-r--r--'), ('mode-600', 'rw-------'), ('mode-400', 'r--------'),
             ('mode-750', 'rwxr-x---'), ('mode-775', 'rwxrwxr-x'), ('mode-111', '--x--x--x'), ('mode-222', '-w--w--w-'),
             ('mode-444', 'r--r--r--'), ('mode-421', 'r---w---x'), ('write-public', '-------w-'))
    for cid, mode in modes:
        cases.append(one(cid, mode))
    cases.append(case('untick', 'Tick the owner read box and tick it again.', CHMOD_PAGE, [box(0), box(0)],
                      [point('result', 'Ticking a box twice clears it.', CHMOD_SEEN)]))
    cases.append(case('untick-one', 'Tick all nine boxes and untick the public execute box.', CHMOD_PAGE, [box(i) for i in range(9)] + [box(8)],
                      [point('result', 'Unticking one box lowers only the public digit.', CHMOD_SEEN)]))
    cases.append(case('copy', 'Tick the boxes of rwxr-xr-x and press the copy button of the command.', CHMOD_PAGE,
                      [box(i) for i in ticks('rwxr-xr-x')] + [copy_after('Input text')],
                      [point('copied', 'The chmod command is copied to the clipboard.', multi(copied=clip(), command=outs()))]))
    return episode('chmod-calculator', 'calculator', bind(cases, {'untick': 'owner-all/result'}))


# -- List converter -------------------------------------------------------------------------------------
LIST_PAGE = '/list-converter'
LIST_IN = 'Your input data'
SEP = 'Separator'
SORT = 'Sort alphabetically'
LIST_FIELDS = ('Separator', 'Item prefix', 'Item suffix', 'List prefix', 'List suffix')
LIST_SEEN = multi(settings=toggles(), output=blocks())
TRIM, UNIQUE, LOWER, BREAKS = 0, 1, 2, 3


def list_converter():
    def one(cid, goal, text, requirement, before=()):
        return case(cid, goal, LIST_PAGE, list(before) + [fill(text, label=LIST_IN)], [point('result', requirement, LIST_SEEN)])

    abc = NL.join(['one', 'two', 'three'])
    dup = NL.join(['a', 'b', 'a', 'c', 'b'])
    spaced = NL.join(['  a  ', ' b', 'c  ', ' a'])
    mixed = NL.join(['Banana', 'apple', 'Cherry', 'BANANA', 'apple'])
    gaps = NL.join(['a', '', '', 'b', '  ', 'c'])
    wrap_item = [fill(APOS, placeholder='Item prefix'), fill(APOS, placeholder='Item suffix')]
    wrap_list = [fill('[', placeholder='List prefix'), fill(']', placeholder='List suffix')]
    cases = [
        case('default', DEFAULT, LIST_PAGE, [], [point('settings', 'The page opens with trimming and duplicate removal on, lowercase and line breaks off, a comma and space separator and no wrapping.',
                                                       multi(toggles=toggles(), fields=fields(*LIST_FIELDS)))]),
        one('basic', 'Type three lines.', abc, 'Lines are joined with a comma and a space.'),
        one('unique', 'Type five lines with repeats.', dup, 'Repeated lines are removed and the first of each is kept.'),
        one('keep-duplicates', 'Turn off Remove duplicates and type five lines with repeats.', dup, 'Repeated lines are kept.', [switch(UNIQUE)]),
        one('trim', 'Type lines with spaces around them.', spaced, 'Spaces around each line are removed.'),
        one('no-trim', 'Turn off Trim list items and type the same lines.', spaced, 'Spaces around each line are kept.', [switch(TRIM)]),
        one('lowercase', 'Turn on Convert to lowercase and type mixed case lines.', mixed, 'Lines are lowercased before repeats are dropped.', [switch(LOWER)]),
        one('line-breaks', 'Turn on Keep line breaks and type three lines.', abc, 'Each item ends with the separator and a line break.', [switch(BREAKS)]),
        one('empty-lines', 'Type lines with empty and blank lines between them.', gaps, 'Empty and blank lines are left out.'),
        one('sort-asc', 'Choose Sort ascending and type mixed case lines.', mixed, 'Lines are sorted in ascending order.', [choose(SORT, 'Sort ascending')]),
        one('sort-desc', 'Choose Sort descending and type mixed case lines.', mixed, 'Lines are sorted in descending order.', [choose(SORT, 'Sort descending')]),
        one('sort-numbers', 'Choose Sort ascending and type numbers of different length.', NL.join(['10', '9', '100', '1']), 'Numbers are sorted as text.', [choose(SORT, 'Sort ascending')]),
        one('separator', 'Set the separator to a pipe with spaces and type three lines.', abc, 'Items are joined with the typed separator.', [fill(' | ', label=SEP)]),
        one('separator-empty', 'Clear the separator and type three lines.', abc, 'Items are joined with nothing between them.', [fill('', label=SEP)]),
        one('item-wrap', 'Set the item prefix and suffix to an apostrophe and type three lines.', abc, 'Every item is wrapped.', wrap_item),
        one('list-wrap', 'Set the list prefix to a bracket and the list suffix to a closing bracket and type three lines.', abc, 'The whole list is wrapped.', wrap_list),
        one('list-wrap-breaks', 'Turn on Keep line breaks, wrap the list in brackets and type three lines.', abc, 'The list wrapper sits on its own lines.', [switch(BREAKS)] + wrap_list),
        one('combined', 'Turn on lowercase and line breaks, sort ascending, wrap items and use a semicolon.', mixed, 'All options apply together.',
            [switch(LOWER), switch(BREAKS), choose(SORT, 'Sort ascending'), fill(';', label=SEP)] + wrap_item),
        one('unicode', 'Type lines with non-Latin text.', NL.join(['caf' + chr(233), chr(26085) + chr(26412), chr(10003)]), 'Non-Latin text is kept.'),
        one('single', 'Type one line.', 'only', 'A single item has no separator.'),
        one('stored', 'Turn off Remove duplicates, reload the page and type five lines with repeats.', dup, 'The switch stays off after reloading.', [switch(UNIQUE), reload()]),
        one('stored-separator', 'Set the separator to a semicolon, reload the page and type three lines.', abc, 'The separator is kept after reloading.', [fill(';', label=SEP), reload()]),
        one('stored-sort', 'Choose Sort descending, reload the page and type mixed case lines.', mixed, 'The sort order is kept after reloading.', [choose(SORT, 'Sort descending'), reload()]),
    ]
    return episode('list-converter', 'converter', cases)


# -- Lorem ipsum generator ------------------------------------------------------------------------------
LOREM_PAGE = '/lorem-ipsum-generator'
FIRST = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit[.]'
SENTENCE = '[A-Z][a-z]*( [a-z]+){7,13}[.]'
PLAIN = SENTENCE + '( ' + SENTENCE + '){2,6}'
STARTED = FIRST + '( ' + SENTENCE + '){2,6}'


LOREM_OUT = {'from': 'output', 'index': 0}


def lorem_seen(pattern, source='output'):
    return multi(text=shape(source, patterns={'text': pattern}, only_patterns=True), toggles=toggles())


def lorem_ipsum_generator():
    html = lambda pattern: '<p>' + pattern + '</p>'
    cases = [
        case('default', DEFAULT, LOREM_PAGE, [], [point('text', 'One paragraph that starts with the standard lorem ipsum sentence.', lorem_seen(STARTED))]),
        case('no-start', 'Turn off Start with lorem ipsum.', LOREM_PAGE, [switch(0)], [point('text', 'The paragraph is made only of random sentences.', lorem_seen(PLAIN))]),
        case('html', 'Turn on As html.', LOREM_PAGE, [switch(1)], [point('text', 'The paragraph is wrapped in a p element.', lorem_seen(html(STARTED)))]),
        case('html-plain', 'Turn off Start with lorem ipsum and turn on As html.', LOREM_PAGE, [switch(0), switch(1)],
             [point('text', 'Random sentences are wrapped in a p element.', lorem_seen(html(PLAIN)))]),
        case('refresh', 'Press Refresh.', LOREM_PAGE, [remember(LOREM_OUT), click('Refresh')],
             [point('text', 'Refresh makes a new paragraph with the same shape.', multi(text=lorem_seen(STARTED), changed=changed(LOREM_OUT)))]),
        case('refresh-plain', 'Turn off Start with lorem ipsum and press Refresh.', LOREM_PAGE, [switch(0), remember(LOREM_OUT), click('Refresh')],
             [point('text', 'Refresh makes a new paragraph of random sentences.', multi(text=lorem_seen(PLAIN), changed=changed(LOREM_OUT)))]),
        case('copy', 'Press Copy.', LOREM_PAGE, [click('Copy')], [point('text', 'The paragraph is copied to the clipboard.', lorem_seen(STARTED, 'clipboard'))]),
        case('copy-html', 'Turn on As html and press Copy.', LOREM_PAGE, [switch(1), click('Copy')],
             [point('text', 'The p element is copied to the clipboard.', lorem_seen(html(STARTED), 'clipboard'))]),
    ]
    return episode('lorem-ipsum-generator', 'generator', cases)


# -- String obfuscator ----------------------------------------------------------------------------------
OBF_PAGE = '/string-obfuscator'
OBF_LABEL = 'String to obfuscate:'
NUM = 'Please Input'
OBF_SEEN = multi(inputs=INPUTS, toggles=toggles(), result=lines(start=OBF_LABEL))


def first(n):
    return fill(str(n), placeholder=NUM)


def last(n):
    return fill(str(n), placeholder=NUM, nth=1)


def string_obfuscator():
    def setting(cid, goal, steps, requirement):
        return case(cid, goal, OBF_PAGE, steps, [point('result', requirement, OBF_SEEN)])

    def text(cid, goal, value, requirement, before=()):
        return case(cid, goal, OBF_PAGE, list(before) + [fill(value, label=OBF_LABEL)], [point('result', requirement, OBF_SEEN)])

    cases = [
        setting('default', DEFAULT, [], 'The page opens with a sample sentence keeping its first and last four characters and its spaces.'),
        setting('first-0', 'Set Keep first to 0.', [first(0)], 'Only the last characters stay readable.'),
        setting('last-0', 'Set Keep last to 0.', [last(0)], 'Only the first characters stay readable.'),
        setting('none', 'Set both numbers to 0.', [first(0), last(0)], 'Every character except the spaces is replaced.'),
        setting('first-10', 'Set Keep first to 10 and Keep last to 2.', [first(10), last(2)], 'The kept parts follow the two numbers.'),
        setting('keep-all', 'Set both numbers to 100.', [first(100), last(100)], 'Nothing is replaced when the kept parts cover the text.'),
        setting('spaces-off', 'Turn off Keep spaces.', [switch(0)], 'Spaces are replaced like any other character.'),
        setting('spaces-off-none', 'Turn off Keep spaces and set both numbers to 0.', [switch(0), first(0), last(0)], 'Every character including spaces is replaced.'),
        text('token', 'Type a token.', 'ghp_abc123XYZ789secret', 'The middle of a token is replaced.'),
        text('iban', 'Type an IBAN.', 'FR7630006000011234567890189', 'The middle of an IBAN is replaced.'),
        text('unicode', 'Type text with non-Latin characters.', UNI, 'Each character counts as one.'),
        text('emoji', 'Set Keep first to 2 and Keep last to 0 and type text with an emoji.', 'ab' + chr(128512) + 'cd', 'An emoji is replaced by the characters it is made of.', [first(2), last(0)]),
        text('multiline', 'Type two lines.', 'line one' + NL + 'line two', 'A line break counts as a character.'),
        text('short', 'Type abc.', 'abc', 'A string shorter than the kept parts is shown as typed.'),
        text('empty', 'Clear the text.', '', 'An empty string shows no result.'),
    ]
    return episode('string-obfuscator', 'converter', cases)


def build():
    return [math_evaluator(), chmod_calculator(), list_converter(), lorem_ipsum_generator(), string_obfuscator()]
