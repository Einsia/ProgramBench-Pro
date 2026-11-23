'''Program episodes: hashes, HMAC, Basic auth header and Base64 of text.'''
import base64

from pbuild import (NL, address, case, choose, click, clip, copy_after, fields, fill, lines, out, outs, point, reload,
                    switch, toggles, episode)

HASHES = ['MD5', 'SHA1', 'SHA256', 'SHA224', 'SHA512', 'SHA384', 'SHA3', 'RIPEMD160']
UNI = 'Zażółć gęślą jaźń 日本語 ✓'
LONG = 'The quick brown fox jumps over the lazy dog. ' * 12
HASH_FIELD = 'Your text to hash:'


def digest_points(form):
    return [point(name.lower(), '%s digest of the text, shown as %s.' % (name, form), out(i))
            for i, name in enumerate(HASHES)]


def hash_text():
    def one(cid, goal, text, page='/hash-text', form='hexadecimal digits', extra_steps=(), extra_points=()):
        steps = [fill(text, label=HASH_FIELD)] + list(extra_steps)
        return case(cid, goal, page, steps, digest_points(form) + list(extra_points))

    cases = [
        one('abc', 'Type abc into the text field.', 'abc'),
        one('unicode', 'Type a text with accented, Chinese and symbol characters.', UNI),
        one('long', 'Type a text of more than 500 characters.', LONG),
        one('binary', 'Open the page with the binary digest encoding in its address and type abc.', 'abc',
            '/hash-text?encoding=Bin', 'binary digits'),
        one('base64', 'Open the page with the Base64 digest encoding in its address and type abc.', 'abc',
            '/hash-text?encoding=Base64', 'Base64'),
        one('base64url', 'Open the page with the url-safe Base64 digest encoding in its address and type abc.', 'abc',
            '/hash-text?encoding=Base64url', 'url-safe Base64'),
        one('choose-base64', 'Type abc and choose the Base64 digest encoding from the list.', 'abc', form='Base64',
            extra_steps=[choose('Hexadecimal (base 16)', 'Base64 (base 64)')],
            extra_points=[point('address', 'The chosen digest encoding is kept in the address as the encoding query.',
                                address(), requires=['choose-base64/md5'])]),
        case('empty', 'Open the page without typing.', '/hash-text', [],
             [point('all', 'With no text the digests are those of the empty string.', outs())]),
        case('lines', 'Type two lines of text.', '/hash-text',
             [fill('first line' + NL + 'second line', label=HASH_FIELD)],
             [point('all', 'A text with a line break is hashed together with the break.', outs())]),
    ]
    for i in (0, 2, 7):
        name = HASHES[i]
        cases.append(case('copy-' + name.lower(), 'Type abc and press the copy button of the %s result.' % name, '/hash-text',
                          [fill('abc', label=HASH_FIELD), copy_after('Input text', field_nth=i)],
                          [point('clipboard', 'The copy button puts the %s digest on the clipboard.' % name, clip())]))
    return episode('hash-text', 'crypto', cases)


def hmac():
    text, key = 'The quick brown fox jumps over the lazy dog', 'secret key'
    t_label, k_label, r_label = 'Plain text to compute the hash', 'Secret key', 'HMAC of your text'

    def one(cid, goal, requirement, extra=(), t=text, k=key, check=None):
        steps = [fill(t, label=t_label), fill(k, label=k_label)] + list(extra)
        return case(cid, goal, '/hmac-generator', steps, [point('hmac', requirement, check or fields(r_label))])

    cases = [one('sha256', 'Type a text and a secret key.', 'The HMAC uses SHA-256 and is shown in hexadecimal.')]
    for algo in ('MD5', 'RIPEMD160', 'SHA1', 'SHA3', 'SHA224', 'SHA384', 'SHA512'):
        cases.append(one(algo.lower(), 'Type a text and a key and choose %s as the hashing function.' % algo,
                         'The HMAC uses %s with the secret key, in hexadecimal.' % algo, [choose('SHA256', algo)]))
    for cid, label, form in (('binary', 'Binary (base 2)', 'binary digits'), ('base64', 'Base64 (base 64)', 'Base64'),
                             ('base64url', 'Base64-url (base 64 with url safe chars)', 'url-safe Base64')):
        cases.append(one(cid, 'Type a text and a key and choose the %s output encoding.' % form,
                         'The SHA-256 HMAC is shown as %s.' % form, [choose('Hexadecimal (base 16)', label)]))
    cases.append(one('empty-key', 'Type a text and leave the secret key empty.', 'An empty key is a valid key.', k=''))
    cases.append(one('unicode', 'Type a text and a key with non-Latin characters.',
                     'Text and key are used as UTF-8 text.', t=UNI, k=UNI))
    cases.append(one('copy', 'Type a text and a key and press Copy HMAC.', 'The copy button puts the HMAC on the clipboard.',
                     [click('Copy HMAC')], check=clip()))
    return episode('hmac-generator', 'crypto', cases)


def basic_auth():
    def one(cid, goal, requirement, user, password, extra=(), check=None):
        steps = [fill(user, label='Username'), fill(password, label='Password')] + list(extra)
        return case(cid, goal, '/basic-auth-generator', steps,
                    [point('header', requirement, check or lines(start='Authorization header:'))])

    return episode('basic-auth-generator', 'web', [
        one('simple', 'Type a user name and a password.', 'The header carries the Base64 of user:password.', 'alice', 's3cret'),
        one('colon', 'Type a password that contains a colon.', 'The password is taken as typed.', 'bob', 'pa:ss:word'),
        one('unicode', 'Type a user name and a password with non-Latin characters.', 'The pair is encoded as UTF-8.', UNI, UNI),
        one('no-user', 'Type only a password.', 'An empty user name gives a header with a leading colon.', '', 'secret'),
        one('long', 'Type a long user name and a long password.', 'Long values are encoded completely.', 'u' * 60, 'p' * 90),
        one('copy', 'Type a user name and a password and press Copy header.',
            'The copy button puts the complete header on the clipboard.', 'alice', 's3cret', [click('Copy header')], clip()),
    ])


def base64_text():
    enc, enc_out, dec, dec_out = 'String to encode', 'Base64 of string', 'Base64 string to decode', 'Decoded string'
    page = '/base64-string-converter'

    def encode(cid, goal, requirement, text, extra=(), check=None, requires=(), after=()):
        steps = list(extra) + [fill(text, label=enc)] + list(after)
        return case(cid, goal, page, steps, [point('encoded', requirement, check or fields(enc_out), requires)])

    def decode(cid, goal, requirement, text, extra=(), check=None, requires=(), after=()):
        steps = list(extra) + [fill(text, label=dec)] + list(after)
        return case(cid, goal, page, steps, [point('decoded', requirement, check or fields(dec_out), requires)])

    uni64 = base64.b64encode(UNI.encode('utf-8')).decode('ascii')
    cases = [
        encode('encode-ascii', 'Type hello world into the string to encode.', 'The text is encoded to Base64.', 'hello world'),
        encode('encode-unicode', 'Type a text with non-Latin characters.', 'The text is encoded as UTF-8 bytes.', UNI),
        encode('encode-lines', 'Type two lines.', 'A line break is encoded with the text.', 'line one' + NL + 'line two'),
        encode('encode-pad-one', 'Type a text of one byte.', 'Padding with two equals signs.', 'a'),
        encode('encode-pad-two', 'Type a text of two bytes.', 'Padding with one equals sign.', 'ab'),
        encode('encode-standard', 'Type a text whose encoding contains plus and slash.', 'Standard Base64 uses plus, slash and padding.', '>>>??'),
        encode('encode-url-safe', 'Turn on Encode URL safe and type the same text.', 'URL-safe Base64 replaces plus and slash.', '>>>??',
               [switch(0)]),
        decode('decode-ascii', 'Type aGVsbG8gd29ybGQ= into the string to decode.', 'The Base64 text is decoded.', 'aGVsbG8gd29ybGQ='),
        decode('decode-unicode', 'Type the Base64 of a text with non-Latin characters.', 'The bytes are read as UTF-8.', uni64),
        decode('decode-url-safe', 'Turn on Decode URL safe and type URL-safe Base64.', 'URL-safe Base64 is decoded.', 'Pj4-Pz8', [switch(1)]),
        case('decode-invalid', 'Type text that is not Base64 into the string to decode.', page, [fill('###', label=dec)], [
            point('result', 'Nothing is decoded from invalid text.', fields(dec_out), ['decode-ascii/decoded']),
            point('message', 'The field reports that the Base64 string is invalid.', lines(start=dec, stop=dec_out),
                  ['decode-ascii/decoded'])]),
        case('persist-switch', 'Turn on Encode URL safe and reload the page.', page, [switch(0), reload()],
             [point('switches', 'The switch state is kept after a reload.', toggles())]),
        encode('copy-encoded', 'Type hello and press Copy base64.', 'The copy button puts the Base64 text on the clipboard.',
               'hello', check=clip(), after=[click('Copy base64')]),
        decode('copy-decoded', 'Type aGVsbG8= and press Copy decoded string.', 'The copy button puts the decoded text on the clipboard.',
               'aGVsbG8=', check=clip(), after=[click('Copy decoded string')]),
    ]
    return episode('base64-string-converter', 'converter', cases)


def build():
    return [hash_text(), hmac(), basic_auth(), base64_text()]
