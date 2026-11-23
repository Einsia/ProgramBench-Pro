'''Observation normalization for the program checks (task-owned, not part of the runtime).

Generated identities become typed aliases that must keep their relationships across an episode, wall-clock values keep
only whether they are set, and media properties that depend on a decoder are compared as an independent implementation
can compute them. Everything else is business data and compares exactly.
'''
import datetime
import json
import re
from collections import Counter

# A cover id names the object whose image it is: a kind prefix, the identity of that object (any form) and, for the
# cover of one disc, the disc number. A trailing version suffix (_...) is timing, not content.
COVER = re.compile(r'(mf|al|ar|pl|sh|dc)-(.+)')
DISC = re.compile(r'(.+):([0-9]+)(?:_[0-9A-Za-z]+)?')
VERSION = re.compile(r'_[0-9A-Za-z]+$')
COVER_KIND = {'mf': 'song', 'al': 'album', 'ar': 'artist', 'pl': 'playlist', 'sh': 'share', 'dc': 'album'}
# Share resources are named by their kind.
RESOURCE_KIND = {'album': 'album', 'song': 'song', 'media_file': 'song', 'playlist': 'playlist', 'artist': 'artist'}
# Members that hold objects of a known kind: their identities belong to that kind wherever they appear.
CONTAINER = {'artists': 'artist', 'albumArtists': 'artist', 'participants': 'artist', 'artist': 'artist', 'album': 'album',
             'song': 'song', 'entry': 'song', 'genres': 'genre'}
# Library roll-ups whose counting rules (which folders and files count) belong to one check of their own.
ROLLUP = {'totalFolders', 'totalFiles', 'folderCount'}
# Text members that hold a JSON document: compared as the document, not as its spelling.
JSON_TEXT = {'scrobbleFilter', 'lyrics'}
# Fields that hold the identity of another object.
KIND = {'albumId': 'album', 'albumArtistId': 'artist', 'artistId': 'artist', 'folderId': 'folder', 'parent': 'album',
        'userId': 'user', 'ownerId': 'user', 'playlistId': 'playlist', 'songId': 'song', 'mediaId': 'song',
        'mediaFileId': 'song'}
# Supplied or displayed business text: never mistaken for an identity.
LITERAL = {'title', 'name', 'album', 'artist', 'albumArtist', 'displayArtist', 'displayAlbumArtist', 'displayComposer',
           'comment', 'description', 'genre', 'userName', 'username', 'email', 'streamUrl', 'homePageUrl', 'homepageUrl',
           'lyrics', 'value', 'path', 'sortName', 'tagName', 'tagValue', 'suffix', 'contentType', 'codec', 'owner',
           'libraryName', 'libraryPath', 'orderAlbumName', 'orderArtistName', 'orderTitle', 'orderAlbumArtistName'}
# Wall-clock observations: only whether they are set survives.
CLOCK = {'created', 'createdAt', 'updatedAt', 'birthTime', 'importedAt', 'changed', 'lastScanAt', 'lastScanStartedAt',
         'expiresAt', 'expires', 'lastVisited', 'lastLoginAt', 'lastAccessAt', 'externalInfoUpdatedAt', 'lastScan',
         'playDate', 'playedAt', 'played', 'starred', 'starredAt', 'ratedAt', 'lastSeen', 'lastSeenAt', 'submissionTime', 'lastModified'}
SECRET = {'token', 'subsonicToken', 'subsonicSalt', 'password', 'newPassword', 'currentPassword', 'apiKey'}
# Values derived from the image or the scan run: their presence is the behaviour.
OPAQUE = {'imageHash', 'thumbHash', 'dominantColor', 'imageWidth', 'imageHeight', 'elapsedTime', 'serverVersion'}
SECONDS = {'duration', 'totalDuration'}
# Artist artwork is resolved by a background worker: until it has run the product still offers a cover and an image url,
# afterwards it knows there is none. Whether they are present depends on timing, so artist objects do not keep them.
VOLATILE = {'coverArt', 'artistImageUrl'}


def unordered(values):
    '''Observation marker: membership with multiplicity, never order.'''
    return {'@unordered': list(values)}


def mark_unordered(value, path):
    '''Mark the list at the dotted path of an observation (also below lists) as a membership comparison.'''
    head, _, rest = path.partition('.')
    if isinstance(value, list):
        for item in value:
            mark_unordered(item, path)
    elif isinstance(value, dict) and head in value:
        if rest:
            mark_unordered(value[head], rest)
        elif isinstance(value[head], list):
            value[head] = unordered(value[head])


def lookup(value, path):
    for part in path.split('.'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def project(value, fields):
    '''Keep only the named (dotted) fields of an object or of every object of a list; a field the product leaves out stays absent (the alias comparison then fails a candidate that lacks it).'''
    if fields is None:
        return value
    if isinstance(value, list):
        return [project(item, fields) for item in value]
    out = {}
    for name in fields:
        try:
            out[name] = lookup(value, name)
        except (KeyError, IndexError, TypeError, ValueError):
            continue  # an optional field the product leaves out is simply absent
    return out


class Normalize:
    def __init__(self, base):
        self.base = base
        self.ids = {}
        self.next = Counter()

    def identity(self, kind, value):
        if value in (None, 0, ''):
            return value
        key = (kind, str(value))
        if key not in self.ids:
            self.next[kind] += 1
            self.ids[key] = '@' + kind + ':' + str(self.next[kind])
        return self.ids[key]

    def cover_target(self, kind, rest):
        # The identity part of a cover id, in whatever form the product gives its identities. A trailing version
        # suffix (_...) appears once the background worker has resolved the image: it is timing, not content, so it
        # is dropped unless it belongs to an identity the product has already shown.
        if (kind, rest) not in self.ids and VERSION.search(rest) and VERSION.sub('', rest):
            rest = VERSION.sub('', rest)
        return self.identity(kind, rest)

    def text(self, s):
        # Identities are recognized by the field that holds them (member), never by their shape inside a text.
        s = s.replace(self.base, '@origin').replace(chr(13) + chr(10), chr(10))
        return re.sub(r'/share/img/[A-Za-z0-9._-]+', '/share/img/@token', s)

    @staticmethod
    def kind(obj, hint):
        keys = obj.keys()
        if 'streamUrl' in keys:
            return 'radio'
        if 'resourceType' in keys and 'resourceIds' in keys:
            return 'share'
        if 'userName' in keys and 'isAdmin' in keys:
            return 'user'
        if obj.get('mediaType') == 'song' or ('suffix' in keys and 'title' in keys):
            return 'song'
        if 'owner' in keys or 'ownerId' in keys:
            return 'playlist'
        if 'songCount' in keys and ('isCompilation' in keys or 'compilation' in keys):
            return 'album'
        if 'albumCount' in keys and 'name' in keys:
            return 'artist'
        if 'tagName' in keys:
            return 'tag'
        return hint

    def member(self, name, value, kind):
        if name in SECRET:
            return '@secret' if value else value
        if name in CLOCK and isinstance(value, (int, float)) and not isinstance(value, bool):
            return '@time' if value else '@unset'
        if name in CLOCK and (value is None or isinstance(value, str)):
            # A clock that was never set reads as unset whether it is absent, null, empty or the zero time.
            if not value or value.startswith('0001-'):
                return '@unset'
            datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
            return '@time'
        if name in OPAQUE:
            return '@opaque' if value not in (None, '', 0, False) else value
        if name in SECONDS and type(value) in (int, float):
            return int(round(value))
        if name == 'roles' and isinstance(value, list):
            return sorted(str(x) for x in value)
        if name == 'bitRate':
            assert type(value) is int and value >= 0, 'bitRate must be a nonnegative integer'
            return '@nonnegative'
        # Playback position grows with the time since the report, player numbers follow the order players were created and
        # minutes-ago turns over with the wall clock: only that they are nonnegative integers is compared.
        if name in ('positionMs', 'playerId', 'minutesAgo') and type(value) is int and value >= 0:
            return '@nonnegative'
        if name in JSON_TEXT and isinstance(value, str) and value.strip():
            try:
                return {'@json': self.clean(json.loads(value), name, name)}
            except ValueError:
                pass
        if name == 'id' and (isinstance(value, str) or type(value) is int):
            return self.identity(kind, value)
        if name in KIND and (isinstance(value, str) or type(value) is int):
            return self.identity(KIND[name], value)
        if name == 'coverArt' and isinstance(value, str):
            found = COVER.fullmatch(value)
            if found:
                prefix, rest, disc = found[1], found[2], ''
                parts = DISC.fullmatch(rest) if prefix == 'dc' else None
                if parts:
                    rest, disc = parts[1], ':' + parts[2]
                return prefix + '-' + self.cover_target(COVER_KIND[prefix], rest) + disc
        if name == 'current' and isinstance(value, str):
            # The song the play queue stands at.
            return self.identity('song', value)
        return self.clean(value, CONTAINER.get(name) or (kind if kind != 'object' else name), name)

    def clean(self, v, hint='object', key=''):
        if key in LITERAL and isinstance(v, str):
            return {'@literal': v.replace(chr(13) + chr(10), chr(10))}
        if isinstance(v, dict):
            assert not {'@literal', '@unordered', '@json'} & v.keys(), 'a response cannot supply an observation marker'
            kind = self.kind(v, hint)
            volatile = VOLATILE if kind == 'artist' or key == 'artist' else ()
            # Identities first, so a cover id or a link met in the same object resolves to them.
            first = sorted(v.items(), key=lambda item: (item[0] != 'id' and item[0] not in KIND, item[0]))
            out = {name: self.member(name, value, kind) for name, value in first if name not in volatile and name not in ROLLUP}
            if kind == 'share' and isinstance(v.get('resourceIds'), str):
                resource = RESOURCE_KIND.get(str(v.get('resourceType')), 'id')
                out['resourceIds'] = ','.join(self.identity(resource, x) for x in v['resourceIds'].split(','))
            return dict(sorted(out.items()))
        if isinstance(v, list):
            return [self.clean(item, hint, key) for item in v]
        if isinstance(v, str):
            return self.text(v)
        return v


class AliasGraph:
    '''Compare opaque identities by a persistent typed bijection, not by counters.

    Response objects may carry fields the reference does not have; every reference field must be present and
    equal. Data-keyed maps (participants, tags, stats, roles) and empty objects stay exact.'''

    TOKEN = re.compile(r'@[A-Za-z][A-Za-z0-9_.%+-]*:[0-9]+')
    FIELD = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
    MAPS = {'participants', 'tags', 'stats', 'roles'}
    EMPTY = ('', None, '@unset', [], {}, {'@literal': ''})

    def __init__(self):
        self.forward = {}
        self.reverse = {}

    def compare(self, actual, expected):
        forward, reverse = dict(self.forward), dict(self.reverse)

        def walk(a, e, path, parent=None):
            if type(a) in (int, float) and type(e) in (int, float):
                assert a == e, path + ': different numeric value'
                return
            assert type(a) is type(e), path + ': different value type'
            if isinstance(e, dict):
                markers = ({'@literal'}, {'@unordered'}, {'@json'})
                if e.keys() in markers or a.keys() in markers or not e or parent in self.MAPS \
                        or not all(self.FIELD.match(k) for k in e):
                    assert a.keys() == e.keys(), path + ': different fields'
                else:
                    # A member the reference leaves empty or unset may also be left out.
                    missing = sorted(k for k in set(e) - set(a) if e[k] not in self.EMPTY)
                    assert not missing, path + ': missing fields ' + ', '.join(missing[:5])
                if e.keys() == {'@literal'}:
                    assert isinstance(a['@literal'], str) and a['@literal'] == e['@literal'], path + ': different business text'
                    return
                if e.keys() == {'@unordered'}:
                    av, ev = a['@unordered'], e['@unordered']
                    assert isinstance(av, list) and isinstance(ev, list) and len(av) == len(ev), path + ': different collection length'
                    todo = sorted(ev, key=lambda x: -sum(m[0] in forward for m in self.TOKEN.finditer(json.dumps(x))))

                    def match(index, remaining):
                        if index == len(todo):
                            return True
                        for pos in remaining:
                            saved_forward, saved_reverse = dict(forward), dict(reverse)
                            try:
                                walk(av[pos], todo[index], path + '{member}')
                                if match(index + 1, [x for x in remaining if x != pos]):
                                    return True
                            except AssertionError:
                                pass
                            forward.clear()
                            forward.update(saved_forward)
                            reverse.clear()
                            reverse.update(saved_reverse)
                        return False

                    assert match(0, list(range(len(av)))), path + ': unordered membership or identity relationships differ'
                    return
                for k in e:
                    if k in a:
                        walk(a[k], e[k], path + '.' + k, k)
            elif isinstance(e, list):
                assert len(a) == len(e), path + ': different collection length'
                for i, (av, ev) in enumerate(zip(a, e)):
                    walk(av, ev, path + '[' + str(i) + ']', parent)
            elif isinstance(e, str):
                at, et = list(self.TOKEN.finditer(a)), list(self.TOKEN.finditer(e))
                assert self.TOKEN.split(a) == self.TOKEN.split(e) and len(at) == len(et), path + ': different text or link'
                for am, em in zip(at, et):
                    av, ev = am[0], em[0]
                    assert av.rsplit(':', 1)[0] == ev.rsplit(':', 1)[0], path + ': different identity namespace'
                    assert forward.get(ev, av) == av and reverse.get(av, ev) == ev, path + ': inconsistent identity relationship'
                    forward[ev] = av
                    reverse[av] = ev
            else:
                assert a == e, path + ': different value'

        walk(actual, expected, '$')
        self.forward, self.reverse = forward, reverse
