'''GUI episodes: hashing, generators, downloads and dates driven by an evaluator.'''
import fam_gen
from gbuild import be, cp, episode
from pbuild import fields, multi, outs, shape, toggles

NL = chr(10)
FENCE = chr(96) * 3
INPUTS = {'type': 'inputs'}
WAIT = {'do': 'wait', 'seconds': 1.0}
GOT = {'do': 'download'}


def block(*rows):
    return NL + FENCE + NL + NL.join(rows) + NL + FENCE + NL


def fill(value, label=None, placeholder=None):
    step = {'do': 'fill', 'value': value}
    step.update({'label': label} if label is not None else {'placeholder': placeholder})
    return step


def click(text):
    return {'do': 'click', 'text': text}


def switch(index):
    return {'do': 'click', 'role': 'switch', 'nth': index}


def download(*parts):
    return {'type': 'download', 'parts': list(parts)}


# -- hash text ----------------------------------------------------------------------------------------
HASH_IN = 'Your string to hash...'
HASH_SEEN = multi(inputs=INPUTS, hashes=outs(labels=True, allow_empty=True))


def hashing():
    page = '/hash-text'
    shown = 'The hashes follow the text.'
    return episode('gui-hash', 'crypto', [
        cp('md5', 'On the hash text page, hash this text:' + block('hello') + 'Read its MD5 hash.', 'The MD5 hash is 5d41402abc4b2a76b9719d911017c592.',
           [fill('hello', placeholder=HASH_IN)], [be('hashes', shown, HASH_SEEN)], page=page),
        cp('sha1', 'On the hash text page, hash this text:' + block('abc') + 'Read its SHA1 hash.', 'The SHA1 hash is a9993e364706816aba3e25717850c26c9cd0d89d.',
           [fill('abc', placeholder=HASH_IN)], [be('hashes', 'The SHA1 hash follows the text.', multi(sha1=outs(start=1, stop=2, labels=True)))], page=page),
        cp('md5-abc', 'On the hash text page, hash this text:' + block('abc') + 'Read its MD5 hash.', 'The MD5 hash is 900150983cd24fb0d6963f7d28e17f72.',
           [fill('abc', placeholder=HASH_IN)], [be('hashes', 'The MD5 hash follows the text.', multi(md5=outs(start=0, stop=1, labels=True)))], page=page),
    ])


# -- generators ---------------------------------------------------------------------------------------
def generators():
    return episode('gui-generators', 'generator', [
        cp('uuid-v4', 'On the UUIDs generator, generate three version 4 UUIDs at once.', 'Three UUIDs are listed, one per line, and each is a version 4 UUID.',
           [fill('3', placeholder='UUID quantity')],
           [be('uuids', 'Three version 4 UUIDs are shown.', shape('output', patterns={'match': fam_gen.uuid_lines(4, 3)}, lines=True, only_patterns=True))], page='/uuid-generator'),
        cp('uuid-v5', 'On the UUIDs generator, generate a version 5 UUID in the DNS namespace for the name www.example.com.', 'The page shows the UUID 2ed6657d-e927-568b-95e1-2665a8aea6a2.',
           [click('v5'), click('DNS'), fill('www.example.com', placeholder='Name')],
           [be('uuid', 'The UUID follows the version, the namespace and the name.', multi(inputs=INPUTS, output=outs()))], page='/uuid-generator'),
        cp('token-digits', 'On the token generator, make a token that contains only digits.', 'The token is 64 characters long and made only of digits.',
           [switch(0), switch(1)],
           [be('token', 'The token is made only of digits.', multi(token=shape('output', patterns={'match': fam_gen.charset(fam_gen.DIGITS, 64)}, only_patterns=True), switches=toggles()))], page='/token-generator'),
        cp('ulid-json', 'On the ULID generator, make three ULIDs and show them as a JSON list.', 'The page shows a JSON list of three ULIDs.',
           [fill('3', placeholder='Please Input'), click('JSON')],
           [be('ulids', 'Three ULIDs are shown inside a JSON list.', shape('block', patterns={'match': fam_gen.ulid_json(3)}, only_patterns=True))], page='/ulid-generator'),
    ])


# -- downloads ----------------------------------------------------------------------------------------
def downloads():
    return episode('gui-downloads', 'generator', [
        cp('qr', 'On the QR code generator, save the QR code of the text hello world as an image file.', 'An image file is downloaded and it is the QR code of the text hello world.',
           [fill('hello world', label='Text:'), WAIT, click('Download qr-code'), GOT],
           [be('png', 'The saved file is the QR code image of the text.', multi(file=download('name', 'sha256', 'image'), input=fields('Text:')))], page='/qrcode-generator'),
        cp('svg', 'On the SVG placeholder generator, make a placeholder 300 wide and 200 high with the custom text Card and save it as a file.', 'An SVG file is downloaded; it is 300 wide and 200 high and shows the text Card.',
           [fill('300', placeholder='SVG width...'), fill('200', placeholder='SVG height...'), fill('Card', label='Custom text'), click('Download svg'), GOT],
           [be('file', 'The saved file follows the size and the text.', multi(file=download('name', 'text')))], page='/svg-placeholder-generator'),
    ])


# -- date-time converter ------------------------------------------------------------------------------
DATE_IN = 'Put your date string here...'
DATE_SEEN = multi(input=fields(DATE_IN), formats=outs(labels=True, allow_empty=True))


def dates():
    page = '/date-converter'
    shown = 'The date is shown in every format.'
    return episode('gui-date', 'converter', [
        cp('unix', 'On the date-time converter, convert this date and time:' + block('2024-02-29T12:30:45Z') + 'Read its Unix timestamp.', 'The Unix timestamp is 1709209845.',
           [fill('2024-02-29T12:30:45Z', placeholder=DATE_IN)], [be('formats', shown, DATE_SEEN)], page=page),
        cp('from-rfc', 'On the date-time converter, convert this date and time:' + block('Thu, 29 Feb 2024 12:30:45 GMT') + 'Read its ISO 8601 form.', 'The ISO 8601 form is 2024-02-29T12:30:45Z.',
           [fill('Thu, 29 Feb 2024 12:30:45 GMT', placeholder=DATE_IN)], [be('formats', shown, DATE_SEEN)], page=page),
        cp('epoch', 'On the date-time converter, convert this Unix timestamp:' + block('0') + 'Read its ISO 8601 form.', 'The ISO 8601 form is 1970-01-01T00:00:00Z.',
           [fill('0', placeholder=DATE_IN)], [be('formats', shown, DATE_SEEN)], page=page),
        cp('invalid', 'On the date-time converter, type the text not a date.', 'The page flags the text as an invalid date and shows no converted value.',
           [fill('not a date', placeholder=DATE_IN)], [be('formats', 'The invalid text is flagged and every format is empty.', DATE_SEEN, ['unix/formats'])], page=page, requires=['unix/formats']),
    ])


def build():
    return [hashing(), generators(), downloads(), dates()]
