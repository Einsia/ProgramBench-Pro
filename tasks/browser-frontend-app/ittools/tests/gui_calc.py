'''GUI episodes: URL, binary, NATO and text statistics tools driven by an evaluator.'''
from gbuild import be, cp, episode
from pbuild import fields, lines, multi

NL = chr(10)
FENCE = chr(96) * 3
ENC, DEC = 'Your string :', 'Your encoded string :'
ENC_OUT, DEC_OUT = 'Your string encoded :', 'Your string decoded :'
BIN_IN, BIN_OUT = 'Enter text to convert to binary', 'Binary from your text'
BITS_IN, BITS_OUT = 'Enter binary to convert to text', 'Text from your binary'
NATO_IN = 'Your text to convert to NATO phonetic alphabet'
STATS_IN = 'Your text...'


def block(*rows):
    return NL + FENCE + NL + NL.join(rows) + NL + FENCE + NL


def fill(value, label=None, placeholder=None):
    step = {'do': 'fill', 'value': value}
    step.update({'label': label} if label is not None else {'placeholder': placeholder})
    return step


def url():
    page = '/url-encoder'
    return episode('gui-url', 'encoder', [
        cp('encode', 'On the URL encoder, encode this text:' + block('a b&c'), 'The encoded string is a%20b%26c.',
           [fill('a b&c', label=ENC)],
           [be('encoded', 'The text is shown percent-encoded.', multi(input=fields(ENC), output=fields(ENC_OUT)))], page=page),
        cp('decode', 'On the URL encoder, decode this text:' + block('caf%C3%A9%20menu'), 'The decoded string is caf' + chr(233) + ' menu.',
           [fill('caf%C3%A9%20menu', label=DEC)],
           [be('decoded', 'The text is shown decoded.', multi(input=fields(DEC), output=fields(DEC_OUT)))], page=page),
        cp('decode-invalid', 'On the URL encoder, decode this text:' + block('%E0%A4%A'), 'The page flags the text as malformed and shows no decoded string.',
           [fill('%E0%A4%A', label=DEC)],
           [be('decoded', 'The malformed text is flagged and nothing is decoded.', multi(input=fields(DEC), output=fields(DEC_OUT), text=lines(skip=2)), ['decode/decoded'])],
           page=page, requires=['decode/decoded']),
    ])


def binary():
    page = '/text-to-binary'
    return episode('gui-binary', 'encoder', [
        cp('to-binary', 'On the text to binary page, convert this text to binary:' + block('Hi'), 'The binary form is 01001000 01101001.',
           [fill('Hi', label=BIN_IN)],
           [be('binary', 'The text is shown as eight-bit groups.', multi(input=fields(BIN_IN), output=fields(BIN_OUT)))], page=page),
        cp('to-text', 'On the text to binary page, convert this binary to text:' + block('01001000 01101001'), 'The text is Hi.',
           [fill('01001000 01101001', label=BITS_IN)],
           [be('text', 'The binary is shown as text.', multi(input=fields(BITS_IN), output=fields(BITS_OUT)))], page=page),
    ])


def nato():
    page = '/text-to-nato-alphabet'
    seen = multi(input=fields(NATO_IN), words=lines(start='Your text in NATO phonetic alphabet'))
    seen_empty = multi(input=fields(NATO_IN), words=lines(skip=2))
    return episode('gui-nato', 'encoder', [
        cp('bc', 'On the NATO alphabet page, spell this text:' + block('bc'), 'The page lists the code words Bravo and Charlie.',
           [fill('bc', label=NATO_IN)], [be('words', 'The code words follow the letters.', seen)], page=page),
        cp('empty', 'On the NATO alphabet page, spell this text and then clear it:' + block('bc'), 'The page lists no code words.',
           [fill('bc', label=NATO_IN), fill('', label=NATO_IN)],
           [be('words', 'No code word is listed.', seen_empty, ['bc/words'])], page=page, requires=['bc/words']),
    ])


def stats():
    page = '/text-statistics'
    seen = multi(text=lines(skip=2))
    return episode('gui-stats', 'analyser', [
        cp('three-words', 'On the text statistics page, analyse this text:' + block('one two three'),
           'The page shows a character count of 13, a word count of 3 and a line count of 1.',
           [fill('one two three', placeholder=STATS_IN)], [be('counts', 'The counts follow the text.', seen)], page=page),
        cp('two-lines', 'On the text statistics page, analyse this text:' + block('a b', 'c'),
           'The page shows a word count of 3 and a line count of 2.',
           [fill('a b' + NL + 'c', placeholder=STATS_IN)], [be('counts', 'The counts follow the text.', seen, ['three-words/counts'])],
           page=page, requires=['three-words/counts']),
    ])


def build():
    return [url(), binary(), nato(), stats()]
