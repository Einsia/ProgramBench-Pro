'''Artwork: uploaded images of playlists, radio stations and artists, an artist image file in the music folder and the
size parameter of the cover art endpoint.

Pictures are compared by which fixture picture they are; an image the product draws itself (its placeholder) only has to
be an image that is none of them, and a resized fixture picture is compared by its size. Each upload and removal is a
scored write bound to the read of the cover it changes; each read needs its write.'''
import base64
import time

import library
from api_browse import album_of, artist_of

PURPLE = library.png(library.COVERS['purple'])
TEAL = library.png(library.COVERS['teal'])
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def upload(data, name):
    return {'files': {'image': {'filename': name, 'base64': base64.b64encode(data).decode(), 'mime_type': 'image/png'}}}


def cover(s, step, ident, wait=None, text='', **query):
    def action(c, relaxed=False):
        assert not relaxed, 'artwork checks are scored cases'
        seen = c.observe_bytes(c.subsonic('getCoverArt', binary=True, fmt=None, id=ident(c), **query))
        deadline = time.monotonic() + 25.0
        while wait and not wait(seen) and time.monotonic() < deadline:
            time.sleep(1.0)
            seen = c.observe_bytes(c.subsonic('getCoverArt', binary=True, fmt=None, id=ident(c), **query))
        return seen
    return s.add('artwork', 'cover', step, action, description=text or 'subsonic getCoverArt ' + step)


def sized(s, step, ident, size):
    def action(c, relaxed=False):
        assert not relaxed, 'artwork checks are scored cases'
        return c.observe_picture(c.subsonic('getCoverArt', binary=True, fmt=None, id=ident(c), size=size))
    return s.add('artwork', 'size', step, action, description='subsonic getCoverArt %s at size %s' % (step, size))


def artist_file(c, relaxed=False):
    answer = c.call({'op': 'library_put', 'path': 'Beta Band/artist.png', 'base64': base64.b64encode(TEAL).decode()})
    assert answer.get('size') == len(TEAL), 'library_put artist.png'
    c.rescan(True)


def build(s):
    nat, sub = s.nat, s.sub
    sub('artwork-fixture', 'library', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50, save='albums')
    sub('artwork-fixture', 'library', 'artists', 'getArtists', save='artists')
    nat('artwork-fixture', 'library', 'playlist', 'POST', 'playlist', body={'name': 'Pictured', 'comment': '', 'public': False}, save='pl')
    nat('artwork-fixture', 'library', 'radio', 'POST', 'radio', body={'name': 'Pictured FM', 'streamUrl': 'http://stream.example.test/p'},
        save='radio')
    playlist = lambda c: 'pl-' + c.state['pl']['id']
    radio = lambda c: 'ra-' + c.state['radio']['id']
    alpha = artist_of('Alpha Artist')

    # -- a playlist image: uploaded, shown, removed ----------------------------------------------------------------------
    before = cover(s, 'playlist-before-upload', playlist)
    added = nat('artwork', 'upload', 'playlist', 'POST', lambda c: 'playlist/%s/image' % c.state['pl']['id'], multipart=upload(PURPLE, 'cover.png'),
                status=200)
    shown = need(cover(s, 'playlist-uploaded', playlist), added)
    COMPANIONS[added] = [shown]
    COMPANIONS[before] = [shown]
    need(sub('artwork', 'playlist', 'cover-id', 'getPlaylist', id=lambda c: c.state['pl']['id'], fields=['playlist']), added)
    removed = need(nat('artwork', 'remove', 'playlist', 'DELETE', lambda c: 'playlist/%s/image' % c.state['pl']['id'], status=200), added)
    COMPANIONS[removed] = [need(cover(s, 'playlist-removed', playlist), removed)]

    # -- a radio station image -------------------------------------------------------------------------------------------
    station = nat('artwork', 'upload', 'radio', 'POST', lambda c: 'radio/%s/image' % c.state['radio']['id'], multipart=upload(TEAL, 'logo.png'),
                  status=200)
    COMPANIONS[station] = [need(cover(s, 'radio-uploaded', radio), station)]

    # -- an artist image: uploaded and removed, and an image file next to the music -----------------------------------------
    pictured = nat('artwork', 'upload', 'artist', 'POST', lambda c: 'artist/%s/image' % alpha(c), multipart=upload(PURPLE, 'artist.png'),
                   status=200)
    artist_shown = need(cover(s, 'artist-uploaded', lambda c: 'ar-' + alpha(c)), pictured)
    COMPANIONS[pictured] = [artist_shown]
    dropped = need(nat('artwork', 'remove', 'artist', 'DELETE', lambda c: 'artist/%s/image' % alpha(c), status=200), pictured)
    COMPANIONS[dropped] = [need(cover(s, 'artist-removed', lambda c: 'ar-' + alpha(c)), dropped)]
    s.add('artwork-fixture', 'library', 'artist-file', artist_file, description='add an artist image file to the folder of Beta Band and run a full scan')
    cover(s, 'artist-file', lambda c: 'ar-' + artist_of('Beta Band')(c), wait=lambda seen: seen.get('picture') == 'teal',
          text='subsonic getCoverArt of an artist with an image file in its folder')

    # -- the size parameter: a smaller copy, never a larger one ------------------------------------------------------------
    third = lambda c: 'al-' + album_of('Third Album', 'Gamma Trio')(c)
    sized(s, 'album-smaller', third, 16)
    cover(s, 'album-larger-request', third, text='subsonic getCoverArt of a 48 pixel cover at size 100', size=100)
