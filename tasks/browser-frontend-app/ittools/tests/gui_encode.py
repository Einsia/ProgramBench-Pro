'''GUI episodes: encoders, number tools and hashing driven by an evaluator.'''
from gbuild import be, cp, episode
from pbuild import fields, lines, multi, outs

NL = chr(10)
FENCE = chr(96) * 3
APOS = chr(39)
INPUTS = {'type': 'inputs'}
ESC_IN = 'The string to escape'
UNESC_IN = 'The string to unescape'
SLUG_IN = 'Your string to slugify'
NUM_IN = 'Enter a word, e.g. ' + APOS + 'internationalization' + APOS
HASH_IN = 'Your text to hash:'
BASE_IN = 'Put your input base here (ex: 10)'


def block(*rows):
    return NL + FENCE + NL + NL.join(rows) + NL + FENCE + NL


def fill(value, label=None, placeholder=None):
    step = {'do': 'fill', 'value': value}
    step.update({'label': label} if label is not None else {'placeholder': placeholder})
    return step


def encoders():
    return episode('gui-encode', 'encoder', [
        cp('escape', 'On the HTML entities page, escape this text:' + block('<b>Hi</b>'),
           'The escaped string is &lt;b&gt;Hi&lt;/b&gt;.',
           [fill('<b>Hi</b>', placeholder=ESC_IN)],
           [be('escaped', 'The markup characters of the text are shown escaped.', fields('Your string escaped'))], page='/html-entities'),
        cp('unescape', 'On the HTML entities page, unescape this text:' + block('&lt;i&gt;x&lt;/i&gt;'),
           'The unescaped string is <i>x</i>.',
           [fill('&lt;i&gt;x&lt;/i&gt;', placeholder=UNESC_IN)],
           [be('unescaped', 'The entities are turned back into characters.', fields('Your string unescaped'))], page='/html-entities'),
        cp('slug', 'On the slugify page, make a slug of this text:' + block('Hello World'),
           'The slug is hello-world.',
           [fill('Hello World', label=SLUG_IN)],
           [be('slug', 'The slug follows the text.', fields('Your slug'))], page='/slugify-string'),
        cp('numeronym', 'On the numeronym generator, make the numeronym of the word internationalization.',
           'The numeronym is i18n.',
           [fill('internationalization', placeholder=NUM_IN)],
           [be('numeronym', 'The numeronym follows the word.', outs(labels=True))], page='/numeronym-generator'),
        cp('sha256', 'On the hash text page, hash this text:' + block('abc') + 'Read its SHA256 hash.',
           'The SHA256 hash is ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad.',
           [fill('abc', label=HASH_IN)],
           [be('hashes', 'The SHA256 hash follows the text.', outs(start=2, stop=3, labels=True))], page='/hash-text'),
    ])


def numbers():
    return episode('gui-numbers', 'converter', [
        cp('to-roman', 'On the roman numeral converter, write the number 2024 as a roman numeral.',
           'The roman numeral is MMXXIV.',
           [fill('2024', placeholder='Please Input')],
           [be('roman', 'The roman numeral follows the number.', lines(start='Arabic to roman', stop='Roman to arabic'))], page='/roman-numeral-converter'),
        cp('to-arabic', 'On the roman numeral converter, read the roman numeral MCMXC as a number.',
           'The number is 1990.',
           [fill('MCMXC', placeholder='Input text')],
           [be('arabic', 'The number follows the roman numeral.', lines(start='Roman to arabic'))], page='/roman-numeral-converter'),
        cp('base-255', 'On the integer base converter, convert the number 255 from base 10 and read it in hexadecimal and in binary.',
           'The hexadecimal form is ff and the binary form is 11111111.',
           [fill('255', label='Input number'), fill('10', placeholder=BASE_IN)],
           [be('bases', 'The converted fields follow the number.', multi(inputs=INPUTS, values=outs(labels=True)))], page='/base-converter'),
        cp('camel-snake', 'On the case converter, convert this text:' + block('hello world foo') + 'Read it in camelCase and in snake_case.',
           'The camelCase form is helloWorldFoo and the snake_case form is hello_world_foo.',
           [fill('hello world foo', label='Your string:')],
           [be('formats', 'The converted fields follow the text.', INPUTS)], page='/case-converter'),
    ])


def build():
    return [encoders(), numbers()]
