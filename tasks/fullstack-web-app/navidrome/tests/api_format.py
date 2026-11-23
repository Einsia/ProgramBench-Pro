'''OpenSubsonic response formats and request conventions: XML (also the default), JSONP, the .view suffix, form and query posts, the version and client parameters and unknown operations.

The same reads are made in every format. XML is parsed and reduced to its elements, ids and the attributes that carry business data; JSONP is unwrapped and compared like JSON. Refusals and parameter checks are bound to a positive point of the same episode.'''
import json
import urllib.parse
import xml.etree.ElementTree as ET

from api_browse import album_of, artist_of, slug, song_of
from harness import PASSWORDS, resolve

PAGE = {'_start': 0, '_end': 50, '_sort': 'path', '_order': 'ASC'}
KEEP = {'status', 'version', 'type', 'openSubsonic', 'code', 'valid', 'id', 'name', 'title', 'album', 'artist', 'artistId', 'albumId',
        'songCount', 'albumCount'}
CALLBACK = 'pbpCallback'
WRONG = 'Wrong-Password-2026!'
COMPANIONS = {}
DEPENDS = {}


def element(node, root=False):
    item = {'tag': node.tag.split('}')[-1], 'attrs': {k: v for k, v in sorted(node.attrib.items()) if k in KEEP}}
    if root:
        item['namespace'] = node.tag[1:].split('}')[0] if node.tag.startswith('{') else ''
    text = (node.text or '').strip()
    if text:
        item['value'] = text
    children = sorted((element(x) for x in node), key=lambda x: (x['tag'], str(x['attrs'].get('name') or x['attrs'].get('title') or ''), str(x.get('value', ''))))
    if children:
        item['children'] = children
    return item


def view(c, answer):
    kind = (answer['headers'].get('content-type') or '').split(';')[0]
    body = answer['body']
    seen = {'status': answer['status'], 'type': kind}
    if kind == 'application/xml' and isinstance(body, str):
        try:
            seen['xml'] = c.norm.clean(element(ET.fromstring(body), True))
        except ET.ParseError:
            raise AssertionError('the XML reply is not well formed') from None
    elif kind == 'application/javascript' and isinstance(body, str):
        text = body.strip()
        assert text.startswith(CALLBACK + '(') and text.endswith(')'), 'the JSONP reply is not wrapped in the callback'
        try:
            inner = json.loads(text[len(CALLBACK) + 1:-1])
        except ValueError:
            raise AssertionError('the JSONP reply does not hold JSON') from None
        seen['jsonp'] = c.observe_subsonic({'status': 200, 'body': inner})['reply']
    elif isinstance(body, dict):
        seen['json'] = c.observe_subsonic(answer)['reply']
    return seen


def case(s, family, scenario, step, op, fmt='xml', callback=None, user='admin', password=None, query=None, method='GET', form=False,
         suffix='', client=True, version=True, status=None):
    def action(c, relaxed=False):
        assert not relaxed, 'format checks are scored cases'
        values = {'u': user, 'p': password if password is not None else PASSWORDS[user]}
        if client:
            values['c'] = 'pbp-check'
        if version:
            values['v'] = '1.16.1'
        if fmt:
            values['f'] = fmt
        if callback:
            values['callback'] = callback
        values.update(resolve(query or {}, c))
        encoded = urllib.parse.urlencode(values, doseq=True)
        path = '/rest/' + op + suffix
        if form:
            answer = c.http(method, path, raw=encoded, content_type='application/x-www-form-urlencoded')
        else:
            answer = c.http(method, path + '?' + encoded)
        if status is not None:
            assert answer['status'] == status, 'expected HTTP %s, received %s' % (status, answer['status'])
        return view(c, answer)
    return s.add(family, scenario, step, action, description='format check: %s %s' % (op, step))


def build(s):
    nat, sub = s.nat, s.sub
    nat('format-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    sub('format-fixture', 'library', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50, save='albums')
    sub('format-fixture', 'library', 'artists', 'getArtists', save='artists')
    reads = [
        ('ping', {}), ('getLicense', {}), ('getMusicFolders', {}), ('getGenres', {}), ('getArtists', {}),
        ('getAlbumList2', {'type': 'alphabeticalByName', 'size': 3}),
        ('getAlbum', {'id': album_of('Third Album', 'Gamma Trio')}),
        ('getArtist', {'id': artist_of('Gamma Trio')}),
        ('getSong', {'id': song_of('Opening')}),
        ('search3', {'query': 'Gamma'}), ('getPlaylists', {}), ('getStarred2', {}),
    ]
    baseline = case(s, 'format-json', 'ping', 'baseline', 'ping', fmt='json')
    for op, query in reads:
        case(s, 'format-xml', op, 'explicit', op, fmt='xml', query=query)
        case(s, 'format-jsonp', op, 'callback', op, fmt='jsonp', callback=CALLBACK, query=query)
    for op, query in reads[:4]:
        case(s, 'format-default', op, 'no-f', op, fmt=None, query=query)
    case(s, 'format-default', 'ping', 'unknown-format', 'ping', fmt='yaml')
    for op, query in reads[:6]:
        case(s, 'format-view', op, 'suffix', op, fmt='json', suffix='.view', query=query)
    for op, query in reads[:4]:
        case(s, 'format-post', op, 'form', op, fmt='json', method='POST', form=True, query=query)
    for op, query in reads[4:6]:
        case(s, 'format-post', op, 'query', op, fmt='json', method='POST', query=query)
    refused = [
        case(s, 'format-errors', 'getAlbum', 'xml-missing-id', 'getAlbum', fmt='xml'),
        case(s, 'format-errors', 'getSong', 'xml-missing-id', 'getSong', fmt='xml'),
        case(s, 'format-errors', 'getSong', 'jsonp-missing-id', 'getSong', fmt='jsonp', callback=CALLBACK),
        case(s, 'format-errors', 'ping', 'xml-wrong-password', 'ping', fmt='xml', user='bob', password=WRONG),
        case(s, 'format-errors', 'ping', 'jsonp-wrong-password', 'ping', fmt='jsonp', callback=CALLBACK, user='bob', password=WRONG),
        case(s, 'format-errors', 'ping', 'jsonp-without-callback', 'ping', fmt='jsonp'),
        case(s, 'format-errors', 'ping', 'no-version', 'ping', fmt='json', version=False),
        case(s, 'format-errors', 'ping', 'no-client', 'ping', fmt='json', client=False),
        case(s, 'format-errors', 'noSuchOperation', 'json', 'noSuchOperation', fmt='json', status=404),
        case(s, 'format-errors', 'noSuchOperation', 'xml', 'noSuchOperation', fmt='xml', status=404),
    ]
    for cid in refused:
        COMPANIONS[cid] = [baseline]
