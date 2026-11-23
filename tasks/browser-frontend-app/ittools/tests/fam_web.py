'''Program episodes: URL parser, JWT parser, Outlook SafeLink decoder, email normalizer.'''
import base64
import json

from pbuild import NL, blocks, case, click, clip, fields, fill, lines, multi, outs, point, episode

DEFAULT = 'Open the page without typing.'
INPUTS = {'type': 'inputs'}
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412)


# -- URL parser -----------------------------------------------------------------------------------------
URL_PAGE = '/url-parser'
URL_LABEL = 'Your url to parse:'
URL_SEEN = multi(input=fields(URL_LABEL), parts=outs(labels=True))
URL_EMPTY = multi(input=fields(URL_LABEL), parts=outs(labels=True, allow_empty=True))


def url_parser():
    def one(cid, goal, text, requirement):
        return case(cid, goal, URL_PAGE, [fill(text, label=URL_LABEL)], [point('parts', requirement, URL_SEEN)])

    split = 'The address is split into its parts and every query pair is listed.'
    cases = [
        case('default', DEFAULT, URL_PAGE, [], [point('parts', 'The page opens with an example address already split.', URL_SEEN)]),
        one('full', 'Type an address with credentials, a port, a path, a query and a fragment.',
            'https://user:secret@example.org:8443/a/b/c.html?x=1&y=2#frag', split),
        one('plain', 'Type http://example.org.', 'http://example.org', 'An address with only a host has the root path and no other parts.'),
        one('https-port', 'Type https://example.org:443/.', 'https://example.org:443/', 'The default port of the scheme is not shown as a port.'),
        one('http-port', 'Type http://example.org:80/x.', 'http://example.org:80/x', 'The default port of the scheme is not shown as a port.'),
        one('ftp', 'Type ftp://ftp.example.org/pub/file.txt.', 'ftp://ftp.example.org/pub/file.txt', split),
        one('mailto', 'Type mailto:someone@example.org?subject=Hi.', 'mailto:someone@example.org?subject=Hi', split),
        one('file', 'Type file:///home/user/doc.txt.', 'file:///home/user/doc.txt', split),
        one('ipv6', 'Type http://[2001:db8::1]:8080/.', 'http://[2001:db8::1]:8080/', split),
        one('repeated', 'Type a query with a repeated key and an empty value.', 'https://example.org/?a=1&a=2&b=', 'Repeated keys are listed once with the last value.'),
        one('encoded', 'Type a query with percent-encoded values.', 'https://example.org/?q=hello%20world&e=a%26b', 'Query values are listed decoded.'),
        one('plus', 'Type a query with a plus sign.', 'https://example.org/?q=a+b', 'A plus sign in a value is listed as a space.'),
        one('idn', 'Type an address with a non-ASCII host.', 'https://b' + chr(252) + 'cher.example/', 'A non-ASCII host is shown in its ASCII form.'),
        one('spaces-path', 'Type an address with a space in the path.', 'https://example.org/a b/c', 'A space in the path is shown encoded.'),
        one('uppercase', 'Type HTTPS://EXAMPLE.ORG/Path.', 'HTTPS://EXAMPLE.ORG/Path', 'The scheme and host are shown in lowercase and the path keeps its case.'),
        one('dots', 'Type a path with dot segments.', 'https://example.org/a/./b/../c', 'Dot segments are resolved in the path.'),
        one('username', 'Type an address with only a username.', 'https://admin@example.org/', 'A username without a password leaves the password empty.'),
        one('data', 'Type a data address.', 'data:text/plain;base64,SGVsbG8=', 'A data address has a protocol and a path.'),
        one('hash-only', 'Type an address with only a fragment.', 'https://example.org/#only', 'A fragment is not one of the listed parts.'),
        one('trim', 'Type an address with spaces around it.', '  https://example.org/trim  ', 'Spaces around the address are ignored.'),
    ]
    for cid, goal, text in (('refused', 'Type text that is not an address.', 'not a url'),
                            ('no-scheme', 'Type example.org/path.', 'example.org/path')):
        cases.append(case(cid, goal, URL_PAGE, [fill(text, label=URL_LABEL)], [
            point('parts', 'An invalid address leaves every part empty.', URL_EMPTY, ['full/parts']),
            point('message', 'An invalid address is flagged with a message.', lines(start=URL_LABEL), ['full/parts'])]))
    return episode('url-parser', 'parser', cases)


# -- JWT parser -----------------------------------------------------------------------------------------
JWT_PAGE = '/jwt-parser'
JWT_LABEL = 'JWT to decode'
JWT_SEEN = multi(input=fields(JWT_LABEL), table=lines(start=JWT_LABEL))


def segment(value):
    raw = json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def token(header, payload, signature='c2lnbmF0dXJl'):
    return '.'.join([segment(header), segment(payload), signature])


def jwt_parser():
    hs = {'alg': 'HS256', 'typ': 'JWT'}

    def one(cid, goal, text, requirement):
        return case(cid, goal, JWT_PAGE, [fill(text, label=JWT_LABEL)], [point('table', requirement, JWT_SEEN)])

    cases = [
        case('default', DEFAULT, JWT_PAGE, [], [point('table', 'The page opens with an example token already decoded.', JWT_SEEN)]),
        one('basic', 'Paste a token with a subject, a name and an issued-at time.',
            token(hs, {'sub': '42', 'name': 'Ada Lovelace', 'iat': 1700000000}),
            'The header and payload claims are listed with their descriptions and the time is shown as a date.'),
        one('times', 'Paste a token with issued-at, not-before and expiration times and registered claims.',
            token(hs, {'iss': 'issuer.example', 'aud': 'audience', 'jti': 'abc-123', 'iat': 1700000000, 'nbf': 1700000100, 'exp': 1700003600}),
            'The three times are shown as dates and the registered claims carry their descriptions.'),
        one('header-extra', 'Paste a token whose header has a key id.', token({'alg': 'HS384', 'typ': 'JWT', 'kid': 'key-1'}, {'sub': 'a'}),
            'A header claim without a description is listed with its value only.'),
        one('objects', 'Paste a token with an object claim and a list claim.',
            token(hs, {'address': {'city': 'Paris', 'zip': '75001'}, 'roles': ['admin', 'dev']}),
            'Object and list claims are shown as indented JSON.'),
        one('flags', 'Paste a token with an e-mail, a verified flag and a locale.',
            token(hs, {'email': 'a@b.example', 'email_verified': True, 'locale': 'en'}), 'Booleans are shown as text and the claims carry their descriptions.'),
        one('custom', 'Paste a token with claims that are not registered.', token(hs, {'custom_claim': 'x', 'count': 3, 'none': None}),
            'Unregistered claims are listed with their values only.'),
        one('unicode', 'Paste a token with non-Latin text in the payload.', token(hs, {'name': UNI}), 'Non-Latin characters are shown as they are.'),
        one('bad-time', 'Paste a token whose expiration is not a number.', token(hs, {'exp': 'soon'}), 'A time that is not a number is shown as an invalid date.'),
    ]
    for alg in ('RS256', 'ES384', 'PS512', 'none', 'XX999'):
        cases.append(one('alg-' + alg.lower(), 'Paste a token signed with %s.' % alg, token({'alg': alg, 'typ': 'JWT'}, {'sub': 'a'}),
                         'The algorithm is named and described when it is a known one.'))
    refusals = (('refused', 'Paste text that is not a token.', 'not a token'),
                ('empty', 'Clear the token.', ''),
                ('one-part', 'Paste only the header part of a token.', segment(hs)),
                ('bad-payload', 'Paste a token whose payload is not base64.', segment(hs) + '.!!!.c2ln'))
    for cid, goal, text in refusals:
        cases.append(case(cid, goal, JWT_PAGE, [fill(text, label=JWT_LABEL)],
                          [point('message', 'A value that is not a token is flagged with a message and no claims are listed.',
                                 lines(start=JWT_LABEL), ['basic/table'])]))
    return episode('jwt-parser', 'parser', cases)


# -- Outlook SafeLink decoder ---------------------------------------------------------------------------
SAFE_PAGE = '/safelink-decoder'
SAFE_LABEL = 'Your input Outlook SafeLink Url:'
SAFE_SEEN = multi(input=fields(SAFE_LABEL), output=blocks())
SAFE_EMPTY = multi(input=fields(SAFE_LABEL), output=blocks(allow_empty=True))
SAFE_HOST = 'https://eur01.safelinks.protection.outlook.com/'


def safelink_decoder():
    def one(cid, goal, text, requirement, requires=(), seen=SAFE_SEEN):
        return case(cid, goal, SAFE_PAGE, [fill(text, label=SAFE_LABEL)], [point('output', requirement, seen, requires)])

    cases = [
        case('default', DEFAULT, SAFE_PAGE, [], [point('output', 'The page opens with an empty input and an error as the output.', SAFE_SEEN)]),
        one('decode', 'Paste a SafeLink that wraps an address with a query.',
            SAFE_HOST + '?url=https%3A%2F%2Fit-tools.tech%2Fdocs%3Fa%3D1%26b%3D2&data=05%7C01%7Cuser%40example.org&sdata=abc&reserved=0',
            'The wrapped address is shown decoded.'),
        one('region', 'Paste a SafeLink from another region that wraps an http address.',
            'https://nam12.safelinks.protection.outlook.com/?url=http%3A%2F%2Fexample.org%2F&data=x', 'The wrapped address is shown decoded.'),
        one('order', 'Paste a SafeLink whose url parameter comes last.',
            SAFE_HOST + '?data=05%7C01&reserved=0&url=https%3A%2F%2Fexample.org%2Flast', 'The wrapped address is found wherever the parameter stands.'),
        one('encoded', 'Paste a SafeLink that wraps an address with encoded characters.',
            SAFE_HOST + '?url=https%3A%2F%2Fexample.org%2Fcaf%25C3%25A9%20menu&data=x', 'Characters are decoded once, so inner encoding is kept.'),
        one('spaces', 'Paste a SafeLink with spaces around it.', '  ' + SAFE_HOST + '?url=https%3A%2F%2Fexample.org%2Ftrim&data=x  ',
            'Spaces around the link are ignored.'),
        one('no-url', 'Paste a SafeLink without a url parameter.', SAFE_HOST + '?data=05&reserved=0', 'A SafeLink with no wrapped address shows no address.', ['decode/output'], SAFE_EMPTY),
        one('other-host', 'Paste a link that is not a SafeLink.', 'https://example.org/?url=https%3A%2F%2Fit-tools.tech',
            'A link that is not a SafeLink is refused with an error.', ['decode/output']),
        one('not-url', 'Paste text that only names the SafeLink host.', 'foo.safelinks.protection.outlook.com', 'Text that is not an address is refused with an error.', ['decode/output']),
    ]
    return episode('safelink-decoder', 'decoder', cases)


# -- Email normalizer -----------------------------------------------------------------------------------
EMAIL_PAGE = '/email-normalizer'
EMAIL_IN = 'Put your emails here (one per line)...'
EMAIL_SEEN = multi(input=INPUTS, output=outs(allow_empty=True))


def email_normalizer():
    def one(cid, goal, text, requirement, after=(), seen=EMAIL_SEEN, requires=()):
        return case(cid, goal, EMAIL_PAGE, [fill(text, placeholder=EMAIL_IN)] + list(after), [point('result', requirement, seen, requires)])

    shown = 'The address is shown in its normalized form.'
    cases = [
        case('default', DEFAULT, EMAIL_PAGE, [], [point('result', 'The page opens with empty fields and nothing normalized.', EMAIL_SEEN)]),
        one('gmail', 'Type First.Last+news@gmail.com.', 'First.Last+news@gmail.com', shown),
        one('googlemail', 'Type someone.name@googlemail.com.', 'someone.name@googlemail.com', shown),
        one('plain', 'Type User@Example.COM.', 'User@Example.COM', shown),
        one('outlook', 'Type Name+tag@outlook.com.', 'Name+tag@outlook.com', shown),
        one('yahoo', 'Type name-tag@yahoo.com.', 'name-tag@yahoo.com', shown),
        one('icloud', 'Type name+tag@icloud.com.', 'name+tag@icloud.com', shown),
        one('proton', 'Type name+tag@proton.me.', 'name+tag@proton.me', shown),
        one('multiple', 'Type four addresses, one per line.', NL.join(['A.B+x@gmail.com', 'Mixed@Example.ORG', 'c.d@googlemail.com', 'e+f@outlook.com']),
            'Each line is normalized on its own line.'),
        one('invalid', 'Type text that is not an address.', 'not an email', 'A line that cannot be parsed is reported with the line itself.'),
        one('mixed', 'Type a valid address, an invalid line and another valid address.', NL.join(['a.b@gmail.com', 'oops', 'x@example.org']),
            'Only the line that cannot be parsed is reported.'),
        one('blank-line', 'Type two addresses with an empty line between them.', NL.join(['a.b@gmail.com', '', 'x@example.org']),
            'An empty line is reported as one that cannot be parsed.'),
        one('spaces', 'Type an address with spaces around it.', '  spaced.name@gmail.com  ', 'Spaces around the address are handled.'),
        one('unicode', 'Type an address with non-Latin text.', 'caf' + chr(233) + '@example.org', 'A non-ASCII local part is handled.'),
        one('clear', 'Type an address and press Clear emails.', 'a.b@gmail.com', 'Clear emails empties the input and the result.', [click('Clear emails')], requires=['gmail/result']),
        one('copy', 'Type an address and press Copy normalized emails.', 'a.b+x@gmail.com', 'The normalized text is copied to the clipboard.',
            [click('Copy normalized emails')], multi(output=outs(), copied=clip()), ['gmail/result']),
    ]
    return episode('email-normalizer', 'normalizer', cases)


def build():
    return [url_parser(), jwt_parser(), safelink_decoder(), email_normalizer()]
