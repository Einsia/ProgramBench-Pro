'''Program episodes: URL, HTML entities, binary, Unicode, NATO, Roman numerals, bases, cases, slugs, numeronyms, percentages, temperatures and text statistics.'''
from fam_hash import UNI
from pbuild import NL, bind, case, click, clip, fields, fill, lines, multi, out, outs, point, episode

INPUTS = {'type': 'inputs'}
Q, DQ = chr(39), chr(34)


def url_encoder():
    e_in, e_out, d_in, d_out = 'Your string :', 'Your string encoded :', 'Your encoded string :', 'Your string decoded :'
    page = '/url-encoder'

    def enc(cid, goal, req, text, extra=(), check=None):
        return case(cid, goal, page, [fill(text, label=e_in)] + list(extra), [point('encoded', req, check or fields(e_out))])

    def dec(cid, goal, req, text, extra=(), check=None, requires=()):
        return case(cid, goal, page, [fill(text, label=d_in)] + list(extra), [point('decoded', req, check or fields(d_out), requires)])

    return episode('url-encoder', 'web', [
        enc('encode-words', 'Type Fish & chips 50% off into the string to encode.', 'The text is percent-encoded.', 'Fish & chips 50% off'),
        enc('encode-reserved', 'Type a text with reserved characters.', 'Reserved characters are encoded and unreserved ones stay.', 'a=1&b=2/c?d#e+f;g,h~i!j*k(l)m' + Q + 'n'),
        enc('encode-unicode', 'Type a text with non-Latin characters.', 'Characters are encoded as UTF-8 bytes.', UNI),
        enc('encode-percent', 'Type a text with a percent sign.', 'A percent sign is encoded.', '100% sure'),
        dec('decode-words', 'Type Fish%20%26%20chips%2050%25%20off into the string to decode.', 'Percent escapes are decoded.', 'Fish%20%26%20chips%2050%25%20off'),
        dec('decode-unicode', 'Type the escaped form of a text with non-Latin characters.', 'UTF-8 escapes are decoded to characters.', '%E6%97%A5%E6%9C%AC%20%E2%9C%93'),
        dec('decode-plus', 'Type a text with a plus sign and escapes.', 'A plus sign stays a plus sign.', 'a+b%2Bc'),
        case('decode-invalid', 'Type a malformed escape into the string to decode.', page, [fill('%E0%A4%A', label=d_in)], [
            point('result', 'Nothing is decoded from a malformed escape.', fields(d_out), ['decode-words/decoded']),
            point('message', 'The field reports that the string cannot be parsed.', lines(start=d_in, stop=d_out), ['decode-words/decoded'])]),
        enc('copy-encoded', 'Type hello world and press the first Copy button.', 'The button puts the encoded text on the clipboard.', 'hello world', [click('Copy')], clip()),
        dec('copy-decoded', 'Type hello%20world and press the second Copy button.', 'The button puts the decoded text on the clipboard.', 'hello%20world', [click('Copy', nth=1)], clip()),
    ])


def html_entities():
    page = '/html-entities'

    def esc(cid, goal, req, text):
        return case(cid, goal, page, [fill(text, placeholder='The string to escape')], [point('escaped', req, fields('Your string escaped'))])

    def unesc(cid, goal, req, text, requires=()):
        return case(cid, goal, page, [fill(text, placeholder='The string to unescape')], [point('unescaped', req, fields('Your string unescaped'), requires)])

    return episode('html-entities', 'web', [
        esc('tags', 'Type an HTML tag with attributes and an apostrophe.', 'Angle brackets, ampersands and quotes are escaped.', '<a href=' + DQ + 'x?a=1&b=2' + DQ + '>Tom & Jerry' + Q + 's</a>'),
        esc('plain', 'Type a text without special characters.', 'Text without special characters is unchanged.', 'plain words 123'),
        esc('unicode', 'Type a text with non-Latin characters and an ampersand.', 'Only the special characters are escaped.', UNI + ' & more'),
        unesc('named', 'Type a text with the named entities amp, lt, gt and quot.', 'The five basic entities are decoded.', '&lt;b&gt;Tom &amp; Jerry&lt;/b&gt; &quot;hi&quot; &#39;x&#39;'),
        unesc('numeric', 'Type a text with a hexadecimal and a decimal entity and a named entity the tool does not know.', 'Only the basic entities are decoded.', '&#x41; &#66; &copy; &amp;', ['named/unescaped']),
    ])


def text_to_binary():
    e_in, e_out, d_in, d_out = 'Enter text to convert to binary', 'Binary from your text', 'Enter binary to convert to text', 'Text from your binary'
    page = '/text-to-binary'

    def enc(cid, goal, req, text, extra=(), check=None):
        return case(cid, goal, page, [fill(text, label=e_in)] + list(extra), [point('binary', req, check or fields(e_out))])

    def dec(cid, goal, req, text, extra=(), check=None, requires=()):
        return case(cid, goal, page, [fill(text, label=d_in)] + list(extra), [point('text', req, check or fields(d_out), requires)])

    return episode('text-to-binary', 'converter', [
        enc('encode-hello', 'Type Hello.', 'Each character is written as eight bits separated by spaces.', 'Hello'),
        enc('accent', 'Type a character with an accent.', 'A character above 127 is written with its own code.', 'caf' + chr(233)),
        enc('wide', 'Type a Chinese character.', 'A wide character is written with its full code.', chr(26085) + 'a'),
        enc('lines', 'Type two lines.', 'A line break is a character too.', 'a' + NL + 'b'),
        dec('decode-hello', 'Type the eight-bit groups of Hello separated by spaces.', 'The groups are read as characters.', '01001000 01100101 01101100 01101100 01101111'),
        dec('joined', 'Type sixteen bits without a space.', 'The bits are cut into groups of eight.', '0100100001100101', requires=['decode-hello/text']),
        dec('separators', 'Type two groups separated by commas.', 'Any character other than 0 and 1 is ignored.', '01001000,01100101', requires=['decode-hello/text']),
        case('invalid', 'Type seven bits.', page, [fill('0100100', label=d_in)], [
            point('result', 'A length that is not a multiple of eight gives no text.', fields(d_out), ['decode-hello/text']),
            point('message', 'The field says that the binary must be a multiple of 8 bits.', lines(start=d_in, stop=d_out), ['decode-hello/text'])]),
        enc('copy-binary', 'Type Hi and press Copy binary to clipboard.', 'The button puts the binary text on the clipboard.', 'Hi', [click('Copy binary to clipboard')], clip()),
        dec('copy-text', 'Type 0100100001101001 and press Copy text to clipboard.', 'The button puts the decoded text on the clipboard.', '0100100001101001', [click('Copy text to clipboard')], clip()),
    ])


def text_to_unicode():
    e_in, e_out, d_in, d_out = 'Enter text to convert to unicode', 'Unicode from your text', 'Enter unicode to convert to text', 'Text from your Unicode'
    page = '/text-to-unicode'

    def enc(cid, goal, req, text, extra=(), check=None):
        return case(cid, goal, page, [fill(text, label=e_in)] + list(extra), [point('unicode', req, check or fields(e_out))])

    def dec(cid, goal, req, text, extra=(), check=None, requires=()):
        return case(cid, goal, page, [fill(text, label=d_in)] + list(extra), [point('text', req, check or fields(d_out), requires)])

    return episode('text-to-unicode', 'converter', bind([
        enc('ascii', 'Type Hello Avengers.', 'Each character becomes a decimal entity.', 'Hello Avengers'),
        enc('accent', 'Type a text with an accent and a Chinese character.', 'Characters above 127 are written with their code.', chr(233) + chr(26085)),
        enc('emoji', 'Type a smiling face emoji.', 'A character outside the basic plane is written as two entities.', chr(128512)),
        enc('blank', 'Type only spaces.', 'A text of spaces gives no output.', '   '),
        dec('basic', 'Type &#72;&#105; into the unicode field.', 'Decimal entities are decoded.', '&#72;&#105;'),
        dec('mixed', 'Type a text that mixes plain letters and entities, one of them hexadecimal.', 'Only decimal entities are decoded.', 'a&#98;c&#x41;d', requires=['basic/text']),
        dec('pair', 'Type the two entities of the smiling face emoji.', 'Two entities of a surrogate pair give one character.', '&#55357;&#56832;', requires=['basic/text']),
        enc('copy-unicode', 'Type Hi and press Copy unicode to clipboard.', 'The button puts the entities on the clipboard.', 'Hi', [click('Copy unicode to clipboard')], clip()),
    ], {'blank': 'ascii/unicode'}))


def nato():
    page = '/text-to-nato-alphabet'
    label = 'Your text to convert to NATO phonetic alphabet'

    def one(cid, goal, req, text, extra=(), check=None):
        return case(cid, goal, page, [fill(text, label=label)] + list(extra), [point('words', req, check or lines(start='Your text in NATO phonetic alphabet'))])

    return episode('text-to-nato-alphabet', 'converter', [
        one('hello', 'Type Hello.', 'Each letter becomes its NATO word, separated by spaces.', 'Hello'),
        one('mixed', 'Type letters, digits, a space and punctuation.', 'Characters without a NATO word stay as typed.', 'abc XYZ 123!'),
        one('accent', 'Type a text with accented letters.', 'Accented letters are not NATO letters.', 'na' + chr(239) + 've ' + chr(241)),
        one('copy', 'Type Echo and press Copy NATO string.', 'The button puts the NATO text on the clipboard.', 'Echo', [click('Copy NATO string')], clip()),
    ])


def roman():
    page = '/roman-numeral-converter'

    def arabic(cid, goal, req, n, extra=(), check=None, requires=()):
        return case(cid, goal, page, [fill(n, placeholder='Please Input')] + list(extra), [point('roman', req, check or lines(start='Arabic to roman', stop='Roman to arabic'), requires)])

    def numeral(cid, goal, req, text, extra=(), check=None, requires=()):
        return case(cid, goal, page, [fill(text, placeholder='Input text')] + list(extra), [point('arabic', req, check or lines(start='Roman to arabic'), requires)])

    return episode('roman-numeral-converter', 'converter', [
        arabic('to-roman', 'Type 1994 as the number.', 'The number is written with subtractive notation.', '1994'),
        arabic('max', 'Type 3999 as the number.', 'The largest number that can be written.', '3999'),
        arabic('four', 'Type 4 as the number.', 'Four is IV.', '4'),
        arabic('over', 'Type 4000 as the number.', 'A number above 3999 gives no numeral and a message.', '4000', requires=['to-roman/roman']),
        numeral('to-arabic', 'Type MMXXIV as the numeral.', 'The numeral is read as a number.', 'MMXXIV'),
        numeral('subtractive', 'Type CDXLIV as the numeral.', 'Subtractive pairs are read correctly.', 'CDXLIV', requires=['to-arabic/arabic']),
        numeral('invalid', 'Type IIII as the numeral.', 'A numeral that is not in canonical form is refused with a message.', 'IIII', requires=['to-arabic/arabic']),
        numeral('lowercase', 'Type xlii as the numeral.', 'Lowercase letters are not accepted.', 'xlii', requires=['to-arabic/arabic']),
        arabic('copy-roman', 'Type 2024 and press the first Copy button.', 'The button puts the numeral on the clipboard.', '2024', [click('Copy')], clip()),
    ])


def bases():
    page = '/base-converter'
    result = multi(values=outs(labels=True), text=lines(skip=2))

    def one(cid, goal, req, value, base, extra=(), requires=()):
        steps = [fill(value, label='Input number'), fill(base, placeholder='Put your input base here (ex: 10)')] + list(extra)
        return case(cid, goal, page, steps, [point('values', req, result, requires)])

    return episode('integer-base-converter', 'converter', [
        one('decimal', 'Type 255 in base 10.', 'The number is shown in bases 2, 8, 10, 16, 64 and the custom base.', '255', '10'),
        one('hex', 'Type ff in base 16.', 'Digits above 9 are read as letters.', 'ff', '16', requires=['decimal/values']),
        one('binary', 'Type 1010 in base 2.', 'A binary number is converted.', '1010', '2', requires=['decimal/values']),
        one('base36', 'Type zz in base 36.', 'Letters up to z are digits in base 36.', 'zz', '36', requires=['decimal/values']),
        one('base64', 'Type z+ in base 64.', 'Base 64 uses upper-case letters, plus and slash after the lower-case letters.', 'z+', '64', requires=['decimal/values']),
        one('big', 'Type a 30-digit number in base 10.', 'Numbers beyond the safe integer range are exact.', '123456789012345678901234567890', '10', requires=['decimal/values']),
        one('invalid', 'Type 9 in base 8.', 'A digit that does not belong to the base is reported and the results are empty.', '9', '8', requires=['decimal/values']),
        one('empty', 'Clear the number.', 'An empty number is zero.', '', '10', requires=['decimal/values']),
        one('custom', 'Type 100 in base 10 and set the custom output base to 7.', 'The custom base field shows the number in base 7.', '100', '10', [fill('7', placeholder='Please Input')], ['decimal/values']),
    ])


def case_converter():
    page = '/case-converter'

    def one(cid, goal, req, text, requires=()):
        return case(cid, goal, page, [fill(text, label='Your string:')], [point('formats', req, INPUTS, requires)])

    return episode('case-converter', 'converter', [
        one('words', 'Type Hello wide World.', 'The string is shown in every case style.', 'Hello wide World'),
        one('mixed', 'Type a string that mixes separators and camel case.', 'Words are split at separators and case changes.', 'hello_world-fooBar baz', ['words/formats']),
        one('acronym', 'Type XMLHttpRequest42go.', 'Letters and digits are split into words.', 'XMLHttpRequest42go', ['words/formats']),
        one('accents', 'Type a text with accented letters.', 'Accented letters are kept.', chr(220) + 'n' + chr(239) + 'c' + chr(246) + 'd' + chr(233) + ' stra' + chr(223) + 'e', ['words/formats']),
        one('empty', 'Clear the string.', 'An empty string gives empty results.', '', ['words/formats']),
    ])


def slugify():
    def one(cid, goal, req, text, requires=()):
        return case(cid, goal, '/slugify-string', [fill(text, label='Your string to slugify')], [point('slug', req, fields('Your slug'), requires)])

    return episode('slugify-string', 'web', [
        one('words', 'Type My file path.', 'Words are lower-cased and joined with hyphens.', 'My file path'),
        one('accents', 'Type a text with accents and an ampersand.', 'Accents are removed and the ampersand is written as a word.', 'Cr' + chr(232) + 'me br' + chr(251) + 'l' + chr(233) + 'e & ' + chr(220) + 'ber', ['words/slug']),
        one('symbols', 'Type a text with symbols and extra spaces.', 'Symbols and repeated spaces collapse into single hyphens.', '  --Hello,   World!!  ', ['words/slug']),
        one('emoji', 'Type a text with an emoji.', 'The emoji is written as its name.', chr(129412) + ' unicorn ' + chr(10084), ['words/slug']),
    ])


def numeronym():
    def one(cid, goal, req, text, requires=()):
        return case(cid, goal, '/numeronym-generator', [fill(text, placeholder='Enter a word, e.g. ' + Q + 'internationalization' + Q)], [point('numeronym', req, out(0), requires)])

    return episode('numeronym-generator', 'text', [
        one('long', 'Type internationalization.', 'The first and last letters surround the count of letters between them.', 'internationalization'),
        one('local', 'Type localization.', 'The same rule applies to any long word.', 'localization', ['long/numeronym']),
        one('three', 'Type cat.', 'A word of three letters or fewer stays as it is.', 'cat', ['long/numeronym']),
        one('four', 'Type abcd.', 'A word of four letters gets the count 2.', 'abcd', ['long/numeronym']),
        one('phrase', 'Type two words.', 'A text with a space is abbreviated as one word.', 'hello world', ['long/numeronym']),
    ])


def percentage():
    def step(x, y, group):
        return [fill(x, placeholder='X' if group < 2 else 'From', nth=group if group < 2 else 0), fill(y, placeholder='Y' if group < 2 else 'To', nth=group if group < 2 else 0)]

    def one(cid, goal, req, group, x, y, requires=()):
        return case(cid, goal, '/percentage-calculator', step(x, y, group), [point('results', req, outs(), requires)])

    return episode('percentage-calculator', 'math', [
        one('of', 'Ask what 10 percent of 200 is.', 'The value is X percent of Y.', 0, '10', '200'),
        one('of-decimal', 'Ask what 12.5 percent of 33 is.', 'Decimal numbers are accepted.', 0, '12.5', '33', ['of/results']),
        one('part', 'Ask what percent 5 is of 20.', 'The share is 100 times X divided by Y.', 1, '5', '20', ['of/results']),
        one('part-zero', 'Ask what percent 5 is of 0.', 'Dividing by zero gives no result.', 1, '5', '0', ['part/results']),
        one('increase', 'Ask for the change from 50 to 75.', 'An increase is a positive percentage.', 2, '50', '75', ['of/results']),
        one('decrease', 'Ask for the change from 80 to 60.', 'A decrease is a negative percentage.', 2, '80', '60', ['of/results']),
        one('from-zero', 'Ask for the change from 0 to 5.', 'A change from zero gives no result.', 2, '0', '5', ['increase/results']),
    ])


def temperature():
    scales = ['Kelvin', 'Celsius', 'Fahrenheit', 'Rankine', 'Delisle', 'Newton', 'Reaumur', 'Romer']

    def one(cid, goal, req, scale, value, requires=()):
        step = fill(value, placeholder='Please Input', nth=scales.index(scale))
        return case(cid, goal, '/temperature-converter', [step], [point('scales', req, INPUTS, requires)])

    return episode('temperature-converter', 'measurement', [
        one('celsius', 'Type 100 in the Celsius field.', 'All other scales follow, rounded down to two decimals.', 'Celsius', '100'),
        one('fahrenheit', 'Type 212 in the Fahrenheit field.', 'The other scales follow.', 'Fahrenheit', '212', ['celsius/scales']),
        one('kelvin', 'Type 300 in the Kelvin field.', 'The other scales follow.', 'Kelvin', '300', ['celsius/scales']),
        one('rankine', 'Type 500 in the Rankine field.', 'The other scales follow.', 'Rankine', '500', ['celsius/scales']),
        one('delisle', 'Type 150 in the Delisle field.', 'The other scales follow.', 'Delisle', '150', ['celsius/scales']),
        one('newton', 'Type 33 in the Newton field.', 'The other scales follow.', 'Newton', '33', ['celsius/scales']),
        one('reaumur', 'Type 80 in the Reaumur field.', 'The other scales follow.', 'Reaumur', '80', ['celsius/scales']),
        one('romer', 'Type 60 in the Romer field.', 'The other scales follow.', 'Romer', '60', ['celsius/scales']),
        one('minus-forty', 'Type -40 in the Celsius field.', 'Celsius and Fahrenheit meet at minus forty.', 'Celsius', '-40', ['celsius/scales']),
    ])


def text_statistics():
    def one(cid, goal, req, text, requires=()):
        return case(cid, goal, '/text-statistics', [fill(text, placeholder='Your text...')], [point('counts', req, lines(skip=2), requires)])

    return episode('text-statistics', 'text', [
        one('words', 'Type hello world.', 'Characters, words, lines and bytes are counted.', 'hello world'),
        one('lines', 'Type three lines, one of them empty.', 'Lines are counted at every line break.', 'one' + NL + NL + 'two three', ['words/counts']),
        one('unicode', 'Type a text with accents and a Chinese character.', 'The byte size counts UTF-8 bytes.', UNI, ['words/counts']),
        one('spaces', 'Type words separated by several spaces.', 'Words are separated by runs of white space.', 'a   b    c', ['words/counts']),
        one('kilobytes', 'Type a text of more than 1000 characters.', 'The byte size is shown in a larger unit.', 'x' * 1500, ['words/counts']),
    ])


def build():
    return [url_encoder(), html_entities(), text_to_binary(), text_to_unicode(), nato(), roman(), bases(), case_converter(), slugify(), numeronym(), percentage(), temperature(), text_statistics()]
