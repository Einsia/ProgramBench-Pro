'''Program episodes: UUID, ULID, token, BIP39, bcrypt, encryption and OTP tools.'''
import math
import re

from pbuild import NL, bind, carry, case, changed, choose, click, clip, clock, controls, copy_after, fields, fill, lines, multi, outs, point, reload, remember, shape, source, switch, toggles, wait, episode

DEFAULT = 'Open the page without typing.'
INPUTS = {'type': 'inputs'}
HEX = '[0-9a-f]'
QUOTE = chr(34)
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412) + ' ' + chr(10003)


def pattern_of(source, pattern, name=None, full=False, **extra):
    '''A shape check of one source; only the pattern facts are kept unless full is set.'''
    spec = {'patterns': {'match': pattern}}
    if name is not None:
        spec['name'] = name
    spec.update(extra)
    if not full:
        spec['only_patterns'] = True
    return shape(source, **spec)


OUT0, BLOCK0 = {'from': 'output', 'index': 0}, {'from': 'block', 'index': 0}


# -- UUID generator -------------------------------------------------------------------------------------
UUID_PAGE = '/uuid-generator'
QTY = 'UUID quantity'
NAME = 'Name'
NAMESPACE = 'Namespace'
DNS_NS = '6ba7b810-9dad-11d1-80b4-00c04fd430c8'


def uuid_pat(version, group4=None):
    return '%s{8}-%s{4}-%d%s{3}-%s-%s{12}' % (HEX, HEX, version, HEX, group4 or '[89ab]' + HEX + '{3}', HEX)


def uuid_lines(version, n, clockseq=False):
    return NL.join(uuid_pat(version, '80%02x' % i if clockseq else None) for i in range(n))


def uuid_generator():
    def one(cid, goal, steps, seen, requirement, requires=()):
        return case(cid, goal, UUID_PAGE, steps, [point('uuids', requirement, seen, requires)])

    def random_ids(version, n, source='output', full=False, clockseq=False):
        return pattern_of(source, uuid_lines(version, n, clockseq), full=full, lines=True)

    def qty(n):
        return fill(str(n), placeholder=QTY)

    exact = multi(inputs=INPUTS, output=outs())
    cases = [
        one('default', DEFAULT, [], random_ids(4, 1), 'The page opens with one version 4 UUID.'),
        one('v4-five', 'Set the quantity to 5.', [qty(5)], random_ids(4, 5), 'Five version 4 UUIDs are shown, one per line.'),
        one('v4-fifty', 'Set the quantity to 50.', [qty(50)], random_ids(4, 50, full=True), 'Fifty version 4 UUIDs are shown and no two are the same.'),
        one('v4-refresh', 'Press Refresh.', [remember(OUT0), click('Refresh')], multi(uuids=random_ids(4, 1), changed=changed(OUT0)), 'Refresh shows a new valid UUID.'),
        one('v4-copy', 'Set the quantity to 3 and press Copy.', [qty(3), click('Copy')], random_ids(4, 3, 'clipboard'), 'Copy puts every UUID on the clipboard, one per line.'),
        one('nil', 'Choose NIL.', [click('NIL')], exact, 'NIL gives the all-zero UUID.'),
        one('nil-three', 'Choose NIL and set the quantity to 3.', [click('NIL'), qty(3)], exact, 'NIL repeats the all-zero UUID once per line.'),
        one('v1', 'Choose v1.', [click('v1')], random_ids(1, 1, clockseq=True), 'A version 1 UUID is shown.'),
        one('v1-four', 'Choose v1 and set the quantity to 4.', [click('v1'), qty(4)], random_ids(1, 4, clockseq=True), 'Each line has its own clock sequence counted up from zero.'),
        one('v1-refresh', 'Choose v1 and press Refresh.', [click('v1'), remember(OUT0), click('Refresh')], multi(uuids=random_ids(1, 1, clockseq=True), changed=changed(OUT0)), 'Refresh shows a new version 1 UUID.'),
        one('stored', 'Choose v1, set the quantity to 2 and reload the page.', [click('v1'), qty(2), reload()], random_ids(1, 2, clockseq=True), 'The version and the quantity are kept after reloading the page.'),
        one('stored-v3', 'Choose v3 and reload the page.', [click('v3'), reload()], exact, 'The version is kept after reloading while the namespace and name go back to their defaults.'),
    ]
    for ver in ('v3', 'v5'):
        pick = [click(ver)]

        def named(ns, name, extra=(), pick=pick):
            return pick + [click(ns), fill(name, placeholder=NAME)] + list(extra)

        cases += [
            one(ver + '-default', 'Choose %s without typing a name.' % ver, pick, exact, 'The default URL namespace and an empty name give a fixed UUID.'),
            one(ver + '-dns', 'Choose %s, the DNS namespace and the name www.example.com.' % ver, named('DNS', 'www.example.com'), exact, 'The same namespace and name always give the same UUID.'),
            one(ver + '-url', 'Choose %s, the URL namespace and a web address as the name.' % ver, named('URL', 'https://example.org/page'), exact, 'The URL namespace gives its own UUID.'),
            one(ver + '-oid', 'Choose %s, the OID namespace and an object identifier as the name.' % ver, named('OID', '1.3.6.1.4.1.343'), exact, 'The OID namespace gives its own UUID.'),
            one(ver + '-x500', 'Choose %s, the X500 namespace and a distinguished name as the name.' % ver, named('X500', 'cn=John Doe'), exact, 'The X500 namespace gives its own UUID.'),
            one(ver + '-unicode', 'Choose %s, the DNS namespace and a name with non-Latin characters.' % ver, named('DNS', UNI), exact, 'A name with non-Latin characters is hashed as UTF-8.'),
            one(ver + '-three', 'Choose %s, the DNS namespace, a name and a quantity of 3.' % ver, named('DNS', 'repeat', [qty(3)]), exact, 'The same UUID is repeated once per line.'),
            one(ver + '-custom', 'Choose %s and type the DNS namespace by hand with the name hello.' % ver, pick + [fill(DNS_NS, placeholder=NAMESPACE), fill('hello', placeholder=NAME)], exact, 'A namespace typed by hand is used.'),
            one(ver + '-invalid', 'Choose %s and type a namespace that is not a UUID.' % ver, pick + [fill('not-a-uuid', placeholder=NAMESPACE), fill('hello', placeholder=NAME)], multi(inputs=INPUTS, output=outs(allow_empty=True), text=lines()), 'An invalid namespace gives no UUID and shows a message.', [ver + '-custom/uuids']),
        ]
    return episode('uuid-generator', 'generator', cases)


# -- ULID generator -------------------------------------------------------------------------------------
ULID_PAGE = '/ulid-generator'
ULID = '[0-9A-HJKMNP-TV-Z]{26}'
STAMP = '(?P<stamp>[0-9A-HJKMNP-TV-Z]{10})'
TAIL = '[0-9A-HJKMNP-TV-Z]{16}'


def ulid_raw(n):
    return NL.join([ULID] * n)


def ulid_json(n):
    body = re.escape(QUOTE + ',' + NL + '  ' + QUOTE).join([ULID] * n)
    return re.escape('[' + NL + '  ' + QUOTE) + body + re.escape(QUOTE + NL + ']')


def ulid_generator():
    def one(cid, goal, steps, seen, requirement):
        return case(cid, goal, ULID_PAGE, steps, [point('ulids', requirement, seen)])

    def raw(n, source='block', full=False, pattern=None):
        return pattern_of(source, pattern or ulid_raw(n), full=full, lines=True)

    def listed(n, source='block'):
        return pattern_of(source, ulid_json(n))

    def qty(n):
        return fill(str(n), placeholder='Please Input')

    same_time = NL.join([STAMP + TAIL] + ['(?P=stamp)' + TAIL] * 3)
    cases = [
        one('default', DEFAULT, [], raw(1), 'The page opens with one ULID.'),
        one('five', 'Set the quantity to 5.', [qty(5)], raw(5), 'Five ULIDs are shown, one per line.'),
        one('hundred', 'Set the quantity to 100.', [qty(100)], raw(100, full=True), 'One hundred distinct ULIDs are shown.'),
        one('same-time', 'Set the quantity to 4.', [qty(4)], raw(4, pattern=same_time), 'ULIDs made at the same moment share the same time part.'),
        one('json', 'Choose JSON.', [click('JSON')], listed(1), 'One ULID is shown inside a JSON list.'),
        one('json-three', 'Choose JSON and set the quantity to 3.', [click('JSON'), qty(3)], listed(3), 'Three ULIDs are shown as an indented JSON list.'),
        one('json-back', 'Choose JSON and then Raw again.', [click('JSON'), click('Raw')], raw(1), 'Raw goes back to one ULID per line.'),
        one('refresh', 'Press Refresh.', [remember(BLOCK0), click('Refresh')], multi(ulids=raw(1), changed=changed(BLOCK0)), 'Refresh shows a new ULID.'),
        one('copy-raw', 'Set the quantity to 3 and press Copy.', [qty(3), click('Copy')], raw(3, 'clipboard'), 'Copy puts every ULID on the clipboard, one per line.'),
        one('copy-json', 'Choose JSON, set the quantity to 2 and press Copy.', [click('JSON'), qty(2), click('Copy')], listed(2, 'clipboard'), 'Copy puts the JSON list on the clipboard.'),
        one('stored', 'Choose JSON, set the quantity to 4 and reload the page.', [click('JSON'), qty(4), reload()], listed(4), 'The format and the quantity are kept after reloading the page.'),
    ]
    return episode('ulid-generator', 'generator', bind(cases, {'json-back': 'json/ulids'}))


# -- Token generator ------------------------------------------------------------------------------------
TOKEN_PAGE = '/token-generator'
UPPER = 'ABCDEFGHIJKLMOPQRSTUVWXYZ'
LOWER = 'abcdefghijklmopqrstuvwxyz'
DIGITS = '0123456789'
SYMBOLS = '.,;:!?./-' + QUOTE + chr(39) + '#{([-|' + chr(92) + '@)]=}*+'


def charset(chars, n):
    if not chars:
        return ''
    return '[' + ''.join(re.escape(c) for c in sorted(set(chars))) + ']{%d}' % n


def token_generator():
    def one(cid, goal, steps, chars, n, requirement, page=TOKEN_PAGE, source='output', new=False):
        seen = multi(token=pattern_of(source, charset(chars, n)), switches=toggles())
        if new:
            steps = [remember(OUT0)] + list(steps)
            seen['checks']['changed'] = changed(OUT0)
        return case(cid, goal, page, steps, [point('token', requirement, seen)])

    plain = UPPER + LOWER + DIGITS
    long_page = TOKEN_PAGE + '?length=512'
    cases = [
        one('default', DEFAULT, [], plain, 64, 'The page opens with a 64 character token of letters and digits.'),
        one('length-1', 'Open the page with the length set to 1 in the address.', [], plain, 1, 'A length of 1 gives a one character token.', TOKEN_PAGE + '?length=1'),
        one('length-8', 'Open the page with the length set to 8 in the address.', [], plain, 8, 'The length from the address gives the token length.', TOKEN_PAGE + '?length=8'),
        one('length-200', 'Open the page with the length set to 200 in the address.', [], plain, 200, 'The length from the address gives the token length.', TOKEN_PAGE + '?length=200'),
        one('length-512', 'Open the page with the length set to 512 in the address.', [], plain, 512, 'The longest length gives a 512 character token.', long_page),
        one('no-upper', 'Turn off the uppercase switch.', [switch(0)], LOWER + DIGITS, 64, 'Only lower case letters and digits are used.'),
        one('no-lower', 'Turn off the lowercase switch.', [switch(1)], UPPER + DIGITS, 64, 'Only capital letters and digits are used.'),
        one('no-numbers', 'Turn off the numbers switch.', [switch(2)], UPPER + LOWER, 64, 'Only letters are used.'),
        one('numbers-only', 'Turn off the uppercase and lowercase switches.', [switch(0), switch(1)], DIGITS, 64, 'Only digits are used.'),
        one('upper-only', 'Set the length to 512 and keep only the uppercase switch on.', [switch(1), switch(2)], UPPER, 512, 'Only capital letters are used from the upstream alphabet, which has no N.', long_page),
        one('lower-only', 'Set the length to 512 and keep only the lowercase switch on.', [switch(0), switch(2)], LOWER, 512, 'Only lower case letters are used from the upstream alphabet, which has no n.', long_page),
        one('symbols-only', 'Keep only the symbols switch on.', [switch(0), switch(1), switch(2), switch(3)], SYMBOLS, 64, 'Only the listed symbols are used.'),
        one('with-symbols', 'Turn on the symbols switch.', [switch(3)], plain + SYMBOLS, 64, 'Letters, digits and symbols are used.'),
        one('symbols-long', 'Set the length to 512 and turn on the symbols switch.', [switch(3)], plain + SYMBOLS, 512, 'A long token draws on every class.', long_page),
        one('nothing', 'Turn off the uppercase, lowercase and numbers switches.', [switch(0), switch(1), switch(2)], '', 0, 'With every class off the token is empty.'),
        one('query-flags', 'Open the page with a length, no uppercase and symbols set in the address.', [], LOWER + DIGITS + SYMBOLS, 20, 'The switches and the length can be set from the address.', TOKEN_PAGE + '?length=20&uppercase=false&symbols=true'),
        one('refresh', 'Press Refresh.', [click('Refresh')], plain, 64, 'Refresh shows a new token of the same kind.', new=True),
        one('copy', 'Press Copy.', [click('Copy')], plain, 64, 'Copy puts the token on the clipboard.', source='clipboard'),
        one('copy-digits', 'Keep only the numbers switch on and press Copy.', [switch(0), switch(1), click('Copy')], DIGITS, 64, 'The copied token follows the switches.', source='clipboard'),
        one('reload', 'Turn off the uppercase switch and reload the page.', [switch(0), reload()], LOWER + DIGITS, 64, 'The switch stays off after reloading the page.'),
    ]
    return episode('token-generator', 'generator', cases)


# -- BIP39 passphrase generator -------------------------------------------------------------------------
BIP_PAGE = '/bip39-generator'
ENTROPY = 'Your string...'
MNEMONIC = 'Your mnemonic...'
ZEROS = '0' * 32
PHRASE = ' '.join(['abandon'] * 11 + ['about'])
LANGUAGES = ('Chinese simplified', 'Chinese traditional', 'Czech', 'French', 'Italian', 'Japanese', 'Korean', 'Portuguese', 'Spanish')


def bip39_generator():
    plain = multi(entropy=fields(ENTROPY), passphrase=fields(MNEMONIC))
    noted = multi(entropy=fields(ENTROPY), passphrase=fields(MNEMONIC), text=lines(skip=2))
    random_seen = multi(entropy=pattern_of('field', HEX + '{32}', name=ENTROPY), passphrase=pattern_of('field', '[a-z]+( [a-z]+){11}', name=MNEMONIC))

    def entropy_case(cid, goal, value, requirement, seen=plain, requires=(), extra=()):
        return case(cid, goal, BIP_PAGE, [fill(value, placeholder=ENTROPY)] + list(extra), [point('result', requirement, seen, requires)])

    def phrase_case(cid, goal, value, requirement, requires=(), before=()):
        return case(cid, goal, BIP_PAGE, list(before) + [fill(value, placeholder=MNEMONIC)], [point('result', requirement, noted, requires)])

    cases = [
        case('default', DEFAULT, BIP_PAGE, [], [point('result', 'The page opens with a random 16 byte entropy and its 12 word English passphrase.', random_seen)]),
        case('refresh', 'Press the refresh button that follows the entropy.', BIP_PAGE, [remember(source('field', name=ENTROPY)), copy_after(ENTROPY)],
             [point('result', 'Refresh makes a new random entropy and passphrase.', multi(result=random_seen, changed=changed(source('field', name=ENTROPY))))]),
        entropy_case('zeros', 'Type 32 zeros as the entropy.', ZEROS, 'The entropy gives its 12 word passphrase.'),
        entropy_case('sevens', 'Type the entropy 7f repeated 16 times.', '7f' * 16, 'The entropy gives its 12 word passphrase.'),
        entropy_case('eights', 'Type the entropy 80 repeated 16 times.', '80' * 16, 'The entropy gives its 12 word passphrase.'),
        entropy_case('ones', 'Type the entropy ff repeated 16 times.', 'ff' * 16, 'The entropy gives its 12 word passphrase.'),
        entropy_case('upper', 'Type an entropy in capital letters.', 'ABCDEF0123456789' * 2, 'Capital hexadecimal letters are handled.', noted),
        entropy_case('nonhex', 'Type 32 letters z as the entropy.', 'z' * 32, 'An entropy that is not hexadecimal is flagged.', noted, ['zeros/result']),
        entropy_case('empty', 'Clear the entropy.', '', 'An empty entropy shows no passphrase.', noted, ['zeros/result']),
    ]
    for size in (16, 20, 24, 28, 30, 36, 40, 48, 56, 64):
        cases.append(entropy_case('hex-%d' % size, 'Type an entropy of %d hexadecimal characters.' % size, ('0123456789abcdef' * 4)[:size], 'The page shows what it makes of an entropy of %d characters.' % size, noted, ['zeros/result']))
    cases += [
        phrase_case('from-12', 'Type the 12 word passphrase abandon ... about.', PHRASE, 'A valid passphrase gives its entropy.'),
        phrase_case('from-18', 'Type a valid 18 word passphrase.', ' '.join(['abandon'] * 17 + ['agent']), 'A valid 18 word passphrase gives its entropy.'),
        phrase_case('from-24', 'Type a valid 24 word passphrase.', ' '.join(['abandon'] * 23 + ['art']), 'A valid 24 word passphrase gives its entropy.'),
        phrase_case('from-uppercase', 'Type the 12 word passphrase in capital letters.', PHRASE.upper(), 'Capital letters in the passphrase are handled.', ['from-12/result']),
        phrase_case('from-spaces', 'Type the 12 word passphrase with two spaces between the words.', '  '.join(PHRASE.split()), 'Extra spaces between the words are handled.', ['from-12/result']),
        phrase_case('from-checksum', 'Type twelve times abandon.', ' '.join(['abandon'] * 12), 'A passphrase with a wrong checksum is refused with a message.', ['from-12/result']),
        phrase_case('from-unknown', 'Type a passphrase whose last word is not in the list.', ' '.join(['abandon'] * 11 + ['zzzz']), 'An unknown word is refused with a message.', ['from-12/result']),
        phrase_case('from-short', 'Type three words.', 'abandon abandon abandon', 'Too few words are refused with a message.', ['from-12/result']),
        phrase_case('from-empty', 'Clear the passphrase.', '', 'An empty passphrase leaves the entropy empty.', ['from-12/result']),
        phrase_case('wrong-language', 'Choose French and type the English passphrase.', PHRASE, 'A passphrase from another language is refused with a message.', ['from-12/result'], [choose('English', 'French', search='French', current_nth=1)]),
    ]
    for lang in LANGUAGES:
        cases.append(entropy_case('lang-' + lang.lower().replace(' ', '-'), 'Type 32 zeros and choose %s.' % lang, ZEROS, 'The passphrase is written with the %s word list.' % lang, plain, (), [choose('English', lang, search=lang, current_nth=1)]))
    cases += [
        case('copy-entropy', 'Type 32 zeros and press the second button after the entropy.', BIP_PAGE, [fill(ZEROS, placeholder=ENTROPY), copy_after(ENTROPY, nth=1)], [point('copied', 'The entropy is copied to the clipboard.', clip())]),
        case('copy-passphrase', 'Type 32 zeros and press the button after the passphrase.', BIP_PAGE, [fill(ZEROS, placeholder=ENTROPY), copy_after(MNEMONIC)], [point('copied', 'The passphrase is copied to the clipboard.', clip())]),
    ]
    return episode('bip39-generator', 'generator', cases)


# -- Bcrypt ---------------------------------------------------------------------------------------------
BCRYPT_PAGE = '/bcrypt'
PLAIN = 'Your string:'
ROUNDS = 'Salt rounds...'
OTHER = 'Your string to compare...'
OTHER_HASH = 'Your hash to compare...'
VECTOR = '$2a$05$CCCCCCCCCCCCCCCCCCCCC.E5YPO9kmyuRGyh0XouQYb4YMJKvyOeW'
VECTOR_2 = '$2a$05$CCCCCCCCCCCCCCCCCCCCC.VGOzA784oUp/Z0DY336zx7pLYAy0lwK'


def hash_pat(rounds):
    return '[$]2a[$]%02d[$][./A-Za-z0-9]{53}' % rounds


def bcrypt_hash():
    def made(cid, goal, steps, rounds, requirement, source='output'):
        seen = pattern_of(source, hash_pat(rounds), index=0)
        return case(cid, goal, BCRYPT_PAGE, steps, [point('hash', requirement, seen)])

    def compare(cid, goal, text, hashed, requirement, requires=()):
        steps = [fill(text, placeholder=OTHER), fill(hashed, placeholder=OTHER_HASH)]
        return case(cid, goal, BCRYPT_PAGE, steps, [point('match', requirement, multi(text=lines(skip=2)), requires)])

    def back(cid, goal, text, other, requirement, requires=()):
        steps = [fill(text, label=PLAIN), wait(0.5), carry(OUT0, placeholder=OTHER_HASH), fill(other, placeholder=OTHER)]
        seen = multi(hash=pattern_of('output', hash_pat(10), index=0), match=lines(skip=2))
        return case(cid, goal, BCRYPT_PAGE, steps, [point('hash', requirement, seen, requires)])

    def rounds_step(n):
        return fill(str(n), placeholder=ROUNDS)

    typed = [fill('hello world', label=PLAIN)]
    cases = [
        made('default', DEFAULT, [], 10, 'The page opens with a bcrypt hash of the empty string at 10 rounds.'),
        back('text', 'Type hello world, then compare hello world with the hash shown.', 'hello world', 'hello world', 'A typed string is hashed at 10 rounds and matches its hash.'),
        back('unicode', 'Type a string with non-Latin characters, then compare it with the hash shown.', UNI, UNI, 'A string with non-Latin characters is hashed and matches its hash.'),
        back('long', 'Type a string of 100 letters, then compare it with the hash shown.', 'a' * 100, 'a' * 100, 'A long string is hashed and matches its hash.'),
        back('text-other', 'Type hello world, then compare hello there with the hash shown.', 'hello world', 'hello there', 'The hash of one string does not match another.', ['text/hash']),
        made('rounds-4', 'Type hello world and set the salt rounds to 4.', typed + [rounds_step(4)], 4, 'The hash records 04 as its cost.'),
        made('rounds-6', 'Type hello world and set the salt rounds to 6.', typed + [rounds_step(6)], 6, 'The hash records 06 as its cost.'),
        made('rounds-8', 'Type hello world and set the salt rounds to 8.', typed + [rounds_step(8)], 8, 'The hash records 08 as its cost.'),
        made('rounds-12', 'Type hello world and set the salt rounds to 12.', typed + [rounds_step(12)], 12, 'The hash records 12 as its cost.'),
        case('copy', 'Type hello world, press Copy hash, then compare hello world with the copied hash.', BCRYPT_PAGE,
             typed + [wait(0.5), click('Copy hash'), carry(source('clipboard'), placeholder=OTHER_HASH), fill('hello world', placeholder=OTHER)],
             [point('hash', 'Copy hash puts the hash on the clipboard and it matches the typed string.',
                    multi(copied=pattern_of('clipboard', hash_pat(10)), match=lines(start='Do they match ?', count=1)))]),
        compare('compare-empty', 'Leave both compare fields empty.', '', '', 'Two empty fields do not match.', ['compare-yes/match']),
        compare('compare-yes', 'Type U*U and a known hash of it.', 'U*U', VECTOR, 'A string and its hash match.'),
        compare('compare-yes-2', 'Type U*U* and a known hash of it.', 'U*U*', VECTOR_2, 'A second string and its hash match.'),
        compare('compare-version', 'Type U*U and the same hash with the 2b version marker.', 'U*U', VECTOR.replace('$2a$', '$2b$'), 'The 2b version marker is accepted.', ['compare-yes/match']),
        compare('compare-wrong', 'Type U*V and the hash of U*U.', 'U*V', VECTOR, 'A different string does not match.', ['compare-yes/match']),
        compare('compare-case', 'Type u*u and the hash of U*U.', 'u*u', VECTOR, 'Letter case matters.', ['compare-yes/match']),
        compare('compare-space', 'Type U*U with a trailing space and the hash of U*U.', 'U*U ', VECTOR, 'A trailing space matters.', ['compare-yes/match']),
        compare('compare-bad-hash', 'Type U*U and a hash that is not a hash.', 'U*U', 'not a hash', 'A value that is not a bcrypt hash does not match.', ['compare-yes/match']),
        compare('compare-cut', 'Type U*U and a cut off hash.', 'U*U', VECTOR[:-1], 'A hash that is one character short does not match.', ['compare-yes/match']),
    ]
    return episode('bcrypt', 'crypto', cases)


# -- Encrypt and decrypt text ---------------------------------------------------------------------------
ENC_PAGE = '/encryption'
TEXT = 'Your text:'
KEY = 'Your secret key:'
CIPHER = 'Your encrypted text:'
PLAIN_OUT = 'Your decrypted text:'
SAMPLE = 'Lorem ipsum dolor sit amet'
GOOD = 'U2FsdGVkX1/EC3+6P5dbbkZ3e1kQ5o2yzuU0NHTjmrKnLBEwreV489Kr0DIB+uBs'
BLOCKS = {'AES': 16, 'TripleDES': 8}


def cipher_pattern(algorithm, text):
    size = len(text.encode())
    block = BLOCKS.get(algorithm)
    total = 16 + ((size // block + 1) * block if block else size)
    chars = 4 * math.ceil(total / 3)
    pad = (3 - total % 3) % 3
    return 'U2FsdGVkX1[89+/][A-Za-z0-9+/]{%d}' % (chars - 11 - pad) + ('={%d}' % pad if pad else '')


def encryption():
    def encrypt(cid, goal, steps, algorithm, text, requirement, key=None):
        # Then the ciphertext is decrypted in the decrypt section with the same algorithm and key.
        # The encrypt section is set first: once it shows the algorithm, the only select still showing AES is the
        # one of the decrypt section (a select chosen first leaves its option list in the page).
        after = [algo(algorithm)] if algorithm != 'AES' else []
        after += ([fill(key, label=KEY, nth=1)] if key is not None else []) + [wait(0.5), carry(OUT0, label=CIPHER)]
        seen = multi(cipher=pattern_of('output', cipher_pattern(algorithm, text), index=0), back=fields(PLAIN_OUT))
        return case(cid, goal + ' Decrypt the ciphertext with the same algorithm and key.', ENC_PAGE, list(steps) + after,
                    [point('cipher', requirement + ' Decrypting it gives the text back.', seen)])

    def decrypt(cid, goal, steps, requirement):
        seen = multi(result=outs(start=1, allow_empty=True, labels=True), text=lines())
        return case(cid, goal, ENC_PAGE, steps, [point('result', requirement, seen, ['default/result'])])

    def algo(name, nth=0):
        return choose('AES', name, current_nth=nth)

    shown = multi(cipher=pattern_of('output', cipher_pattern('AES', SAMPLE), index=0), page=fields(TEXT, KEY, (KEY, 1), CIPHER, PLAIN_OUT))
    cases = [
        case('default', DEFAULT, ENC_PAGE, [], [point('result', 'The page opens with a sample text encrypted with AES and a sample ciphertext already decrypted.', shown)]),
        encrypt('aes-short', 'Type abc as the text.', [fill('abc', label=TEXT)], 'AES', 'abc', 'A short text gives one block of AES ciphertext.'),
        encrypt('aes-empty', 'Clear the text.', [fill('', label=TEXT)], 'AES', '', 'An empty text still gives one block of ciphertext.'),
        encrypt('aes-block', 'Type exactly 16 characters.', [fill('0123456789abcdef', label=TEXT)], 'AES', '0123456789abcdef', 'A text of one full block gets a whole extra block of padding.'),
        encrypt('aes-unicode', 'Type a text with non-Latin characters.', [fill(UNI, label=TEXT)], 'AES', UNI, 'The ciphertext length follows the UTF-8 length of the text.'),
        encrypt('aes-long', 'Type a text of 200 letters.', [fill('x' * 200, label=TEXT)], 'AES', 'x' * 200, 'A long text gives a long ciphertext.'),
        encrypt('aes-lines', 'Type a text of two lines.', [fill('one' + NL + 'two', label=TEXT)], 'AES', 'one' + NL + 'two', 'A line break counts as a character.'),
        encrypt('aes-key', 'Type Meet at noon as the text and another secret key.', [fill('Meet at noon', label=TEXT), fill('another key', label=KEY)], 'AES', 'Meet at noon',
                'Another key still gives a ciphertext of the same shape.', key='another key'),
        encrypt('aes-empty-key', 'Type Meet at noon as the text and clear the secret key.', [fill('Meet at noon', label=TEXT), fill('', label=KEY)], 'AES', 'Meet at noon',
                'An empty key is accepted.', key=''),
        encrypt('tripledes', 'Choose TripleDES.', [algo('TripleDES')], 'TripleDES', SAMPLE, 'TripleDES pads to blocks of 8 bytes.'),
        encrypt('tripledes-block', 'Choose TripleDES and type exactly 8 characters.', [algo('TripleDES'), fill('12345678', label=TEXT)], 'TripleDES', '12345678', 'A text of one full block gets a whole extra block of padding.'),
        encrypt('tripledes-unicode', 'Choose TripleDES and type a text with non-Latin characters.', [algo('TripleDES'), fill(UNI, label=TEXT)], 'TripleDES', UNI, 'The ciphertext length follows the UTF-8 length of the text.'),
        encrypt('rabbit', 'Choose Rabbit.', [algo('Rabbit')], 'Rabbit', SAMPLE, 'Rabbit is a stream cipher without padding.'),
        encrypt('rabbit-long', 'Choose Rabbit and type a text of 200 letters.', [algo('Rabbit'), fill('x' * 200, label=TEXT)], 'Rabbit', 'x' * 200, 'A long text gives a ciphertext as long as the text.'),
        encrypt('rc4', 'Choose RC4.', [algo('RC4')], 'RC4', SAMPLE, 'RC4 is a stream cipher without padding.'),
        encrypt('rc4-empty', 'Choose RC4 and clear the text.', [algo('RC4'), fill('', label=TEXT)], 'RC4', '', 'An empty text gives only the header.'),
        encrypt('rc4-unicode', 'Choose RC4 and type a text with non-Latin characters.', [algo('RC4'), fill(UNI, label=TEXT)], 'RC4', UNI, 'The ciphertext length follows the UTF-8 length of the text.'),
        decrypt('wrong-key', 'Type another secret key in the decrypt section.', [fill('not my key', label=KEY, nth=1)], 'A wrong key gives no readable text.'),
        decrypt('key-space', 'Add a trailing space to the secret key of the decrypt section.', [fill('my secret key ', label=KEY, nth=1)], 'A trailing space makes it a different key.'),
        decrypt('empty-key', 'Clear the secret key of the decrypt section.', [fill('', label=KEY, nth=1)], 'An empty key gives no readable text.'),
        decrypt('empty-cipher', 'Clear the encrypted text.', [fill('', label=CIPHER)], 'An empty ciphertext gives an empty result.'),
        decrypt('truncated', 'Cut the sample ciphertext short.', [fill(GOOD[:30], label=CIPHER)], 'A cut off ciphertext gives no readable text.'),
        decrypt('as-tripledes', 'Choose TripleDES in the decrypt section.', [algo('TripleDES', 1)], 'The wrong algorithm gives no readable text.'),
        decrypt('as-rabbit', 'Choose Rabbit in the decrypt section.', [algo('Rabbit', 1)], 'The wrong algorithm gives no readable text.'),
        decrypt('as-rc4', 'Choose RC4 in the decrypt section.', [algo('RC4', 1)], 'The wrong algorithm gives no readable text.'),
    ]
    return episode('encryption', 'crypto', cases)


# -- OTP code generator ---------------------------------------------------------------------------------
OTP_PAGE = '/otp-generator'
SECRET = 'Secret'
OTP_SECRET = {'from': 'field', 'name': 'Secret'}
OTP_FIELDS = ('Secret', 'Secret in hexadecimal', 'Epoch', 'Count:', 'Padded hex:')
STANDARD = 'JBSWY3DPEHPK3PXP'
RFC = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'


def otp_generator():
    seen = multi(fields=fields(*OTP_FIELDS), text=lines(skip=2, reading='all'))
    # The copy tooltip is transient, so a copy point reads the clipboard and the fields, not the page text.
    copied = multi(copied=clip(), fields=fields(*OTP_FIELDS))
    random_seen = multi(secret=pattern_of('field', '[A-Z2-7]{16}', name=SECRET), hex=pattern_of('field', HEX + '{20}', name='Secret in hexadecimal'), clock=fields('Epoch', 'Count:', 'Padded hex:'))

    def fixed(cid, goal, secret, requirement, after=(), spec=None, requires=()):
        steps = [fill(secret, label=SECRET), wait(1.0)] + list(after)
        return case(cid, goal, OTP_PAGE, steps, [point('result', requirement, spec or seen, requires)])

    def later(seconds):
        return [clock(seconds), wait(1.0)]

    cases = [
        case('default', DEFAULT, OTP_PAGE, [], [point('result', 'The page opens with a random 16 character secret, its hexadecimal form and the fixed time counters.', random_seen)]),
        case('refresh', 'Press the refresh button inside the secret field.', OTP_PAGE, [remember(OTP_SECRET), copy_after(SECRET)],
             [point('result', 'Refresh makes a new random secret.', multi(result=random_seen, changed=changed(OTP_SECRET)))]),
        case('refresh-twice', 'Press the refresh button inside the secret field twice.', OTP_PAGE, [copy_after(SECRET), remember(OTP_SECRET), copy_after(SECRET)],
             [point('result', 'Each refresh makes a new random secret.', multi(result=random_seen, changed=changed(OTP_SECRET)))]),
        fixed('standard', 'Type the secret JBSWY3DPEHPK3PXP.', STANDARD, 'The codes before, at and after the current moment follow from the secret.'),
        fixed('rfc', 'Type the secret of the RFC 6238 test key.', RFC, 'The codes follow from the secret.'),
        fixed('lowercase', 'Type the secret in lower case.', STANDARD.lower(), 'A lower case secret gives the same codes as upper case.', requires=['standard/result']),
        fixed('short', 'Type a short secret.', 'MFRGG', 'A short secret still gives codes.'),
        fixed('padded', 'Type a secret with equals signs at the end.', 'JBSWY3DP====', 'A secret with padding is flagged with a message.', requires=['standard/result']),
        fixed('digits', 'Type a secret with the digits 0 1 8 and 9.', '0189', 'A secret outside the base32 alphabet is flagged with a message.', requires=['standard/result']),
        fixed('empty', 'Clear the secret.', '', 'An empty secret asks for a secret.', requires=['standard/result']),
        fixed('same-window', 'Type the secret and let 22 seconds pass.', STANDARD, 'Within the same 30 second window the codes stay the same.', later(22), requires=['standard/result']),
        fixed('next-window', 'Type the secret and let 23 seconds pass.', STANDARD, 'The next window moves every code one place.', later(23), requires=['standard/result']),
        fixed('half-minute', 'Type the secret and let 30 seconds pass.', STANDARD, 'Thirty seconds move the counter by one.', later(30), requires=['standard/result']),
        fixed('one-minute', 'Type the secret and let 60 seconds pass.', STANDARD, 'Sixty seconds move the counter by two.', later(60), requires=['standard/result']),
        fixed('one-hour', 'Type the secret and let one hour pass.', STANDARD, 'An hour moves the counter by 120.', later(3600), requires=['standard/result']),
        fixed('one-day', 'Type the secret and let one day pass.', STANDARD, 'A day moves the counter by 2880.', later(86400), requires=['standard/result']),
        fixed('copy-previous', 'Type the secret and press the previous code.', STANDARD, 'The previous code is copied to the clipboard.', [copy_after(SECRET, nth=1)], copied, ['standard/result']),
        fixed('copy-current', 'Type the secret and press the current code.', STANDARD, 'The current code is copied to the clipboard.', [copy_after(SECRET, nth=2)], copied, ['standard/result']),
        fixed('copy-next', 'Type the secret and press the next code.', STANDARD, 'The next code is copied to the clipboard.', [copy_after(SECRET, nth=3)], copied, ['standard/result']),
    ]
    return episode('otp-code-generator-and-validator', 'generator', cases)


def build():
    return [uuid_generator(), ulid_generator(), token_generator(), bip39_generator(), bcrypt_hash(), encryption(), otp_generator()]
