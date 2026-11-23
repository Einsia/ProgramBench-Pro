'''Scanning: how the product follows changes of the music folder.

Every case changes the library through the black-box library operations, runs one scan (quick or full) and observes the
state the step is about once the scan has finished: the songs and albums it touched, the missing files and the library
totals, plus lyrics, a cover or the playlists where the step is about them. The library operations of every step always
run, so the folder is the same at every step whatever the product did before; no case gates another. A step that a
product without the feature passes (nothing changes) is bound to an earlier step that shows the change.'''
import base64
import tempfile
import time
from pathlib import Path

import library
import normalize

NL = chr(10)
ROWS = {'_start': 0, '_end': 100, '_sort': 'path', '_order': 'ASC'}
SONG = ['title', 'path', 'missing']
ALBUM = ['name', 'albumArtist', 'songCount', 'missing']
PLAYLIST = ['name', 'songCount', 'sync', 'path']
STATS = ['totalSongs', 'totalAlbums', 'totalArtists', 'totalMissingFiles']
LOOSE = 'Untagged/loose track.mp3'
CLICK = 'Samples/click.wav'
MOVED = 'Samples/Moved/click.wav'
FIRST = 'Alpha Artist/First Album/01 Opening.mp3'
BETA_COVER = 'Beta Band/Second Album/cover.png'
GOLD = library.png(library.COVERS['gold'])
SECOND = 'Alpha Artist/First Album/02 Middle.mp3'
ADDED = library.track('Epsilon Ensemble/Fifth Album/01 Prelude.mp3', 300, 1.0, title='Prelude', track=(1, 1),
                      artist=['Epsilon Ensemble'], albumartist='Epsilon Ensemble', album='Fifth Album', year=2022,
                      genre=['Classical'])
COMPANIONS = {}
DEPENDS = {}


def put(c, path, data, mtime=None):
    request = {'op': 'library_put', 'path': path, 'base64': base64.b64encode(data).decode()}
    if mtime:
        request['mtime'] = mtime
    answer = c.call(request)
    assert answer.get('size') == len(data), 'library_put ' + path


def drop(c, path):
    c.call({'op': 'library_delete', 'path': path})


def made(spec):
    with tempfile.TemporaryDirectory() as folder:
        library.write_track(Path(folder), spec)
        return (Path(folder) / spec['path']).read_bytes()


def spec_of(name, **tags):
    base = next(t for t in library.tracks() if t['path'] == name)
    return {**base, 'tags': {**base['tags'], **tags}}


def view(c, paths=None, albums=None, totals=True):
    '''The library after a scan: the songs whose path starts with one of paths (all songs without paths), the albums
    named in albums (all without), the missing files and the library totals.'''
    rows = c.native('GET', 'song', params=ROWS)['body']
    if paths is not None:
        rows = [x for x in rows if str(x.get('path') or '').startswith(tuple(paths))]
    seen = {'songs': sorted(normalize.project(rows, SONG), key=lambda x: (x.get('path') or '', x.get('title') or ''))}
    if albums != ():
        found = c.native('GET', 'album', params={**ROWS, '_sort': 'name'})['body']
        if albums is not None:
            found = [x for x in found if x.get('name') in albums]
        seen['albums'] = sorted(normalize.project(found, ALBUM), key=lambda x: (x.get('name') or '', x.get('albumArtist') or ''))
    seen['missing'] = sorted(normalize.project(c.native('GET', 'missing', params=ROWS)['body'], ['path']), key=lambda x: x.get('path') or '')
    if totals:
        seen['library'] = normalize.project(c.native('GET', 'library/1')['body'], STATS)
    return c.norm.clean(seen)


def lyrics(c):
    song = next(x['id'] for x in c.native('GET', 'song', params=ROWS)['body'] if x['title'] == 'Closing')
    return {'byId': c.observe_subsonic(c.subsonic('getLyricsBySongId', id=song)),
            'byName': c.observe_subsonic(c.subsonic('getLyrics', artist='Alpha Artist', title='Closing'))}


def playlists(c):
    rows = c.native('GET', 'playlist', params={**ROWS, '_sort': 'name'})['body']
    return c.norm.clean(sorted(normalize.project(rows, PLAYLIST), key=lambda x: x.get('name') or ''), 'playlist')


def cover_of(c, artist):
    albums = c.reply(c.subsonic('getAlbumList2', type='alphabeticalByName', size=100))['albumList2']['album']
    album = next(x for x in albums if x.get('artist') == artist)
    ident = album.get('coverArt') or 'al-' + album['id']
    return {'coverArt': bool(album.get('coverArt')), **c.observe_bytes(c.subsonic('getCoverArt', id=ident, binary=True, fmt=None))}


def wait_cover(c, artist, wanted, timeout=25.0):
    '''The product resolves album covers in the background after a scan (the old cover or the placeholder is still served for a few seconds), so the cover is read until it shows the wanted state and once more after a pause. A cover that never gets there is returned as it is, which fails the comparison.'''
    deadline = time.monotonic() + timeout
    state = cover_of(c, artist)
    while time.monotonic() < deadline:
        if wanted(state):
            time.sleep(1.5)
            again = cover_of(c, artist)
            if again == state:
                return again
            state = again
        else:
            time.sleep(0.5)
            state = cover_of(c, artist)
    return state


def build(s):
    def step(scenario, name, change, full=False, focus=None, extra=None, text=''):
        # focus: the view arguments of what the step is about (None: the whole library).
        def action(c, relaxed=False):
            assert not relaxed, 'scan checks are scored cases'
            change(c)
            c.rescan(full)
            observed = view(c, **(focus or {})) if focus is not False else {}
            if extra:
                observed['extra'] = extra(c)
            return observed
        return s.add('scan', scenario, name, action, description=text or ('library after ' + name))

    # -- a new file, then scans that find nothing to do ---------------------------------------------------------------
    added = step('added', 'quick', lambda c: put(c, ADDED['path'], made(ADDED)),
                 focus={'paths': ['Epsilon Ensemble/'], 'albums': ['Fifth Album']}, text='quick scan after a tagged song file is added')
    COMPANIONS[step('unchanged', 'quick', lambda c: None, text='quick scan of an unchanged library')] = [added]
    COMPANIONS[step('unchanged', 'full', lambda c: None, full=True, text='full scan of an unchanged library')] = [added]

    # -- a deleted file stays in the library as a missing file ------------------------------------------------------------
    loose = {'paths': ['Untagged/'], 'albums': ['[Unknown Album]']}
    removed = step('removed', 'quick-marks-missing', lambda c: drop(c, LOOSE), focus=loose, text='quick scan after a song file is deleted')
    COMPANIONS[step('removed', 'full-keeps-missing', lambda c: None, full=True, focus=loose,
                    text='full scan while the song file stays deleted')] = [removed]
    COMPANIONS[step('removed', 'restored', lambda c: put(c, LOOSE, c.library_files()[LOOSE]), full=True, focus=loose,
                    text='full scan after the deleted song file is restored')] = [removed]

    # -- a moved file ---------------------------------------------------------------------------------------------------------
    step('moved', 'quick', lambda c: c.call({'op': 'library_move', 'from': CLICK, 'to': MOVED}),
         focus={'paths': ['Samples/'], 'albums': (), 'totals': False}, text='quick scan after a song file is moved to another folder')

    # -- changed tags: the quick scan follows the modification time, the full scan reads every file -------------------------
    retag = {'paths': ['Alpha Artist/First Album/'], 'albums': (), 'totals': False}
    newer = step('retag', 'newer-mtime-quick', lambda c: put(c, FIRST, made(spec_of(FIRST, title='Opening Retitled')), mtime=1700000100),
                 focus=retag, text='quick scan after a tag change with a newer modification time')
    COMPANIONS[step('retag', 'same-mtime-quick', lambda c: put(c, SECOND, made(spec_of(SECOND, title='Middle Retitled'))),
                    focus=retag, text='quick scan after a tag change that keeps the modification time')] = [newer]
    step('retag', 'same-mtime-full', lambda c: None, full=True, focus=retag,
         text='full scan after a tag change that kept the modification time')

    # -- ignore rules -------------------------------------------------------------------------------------------------------------
    samples = {'paths': ['Samples/'], 'albums': ()}
    hidden = step('ignore', 'ndignore-added', lambda c: put(c, 'Samples/.ndignore', b'*' + NL.encode()), full=True, focus=samples,
                  text='full scan after an ignore file hides a folder')
    COMPANIONS[step('ignore', 'ndignore-removed', lambda c: drop(c, 'Samples/.ndignore'), full=True, focus=samples,
                    text='full scan after the ignore file is removed')] = [hidden]

    # -- files next to the music ----------------------------------------------------------------------------------------------------
    sidecar = ('[00:00.00]Closing words' + NL + '[00:02.00]Second line' + NL).encode()
    step('sidecar', 'lyrics', lambda c: put(c, 'Alpha Artist/First Album/03 Closing.lrc', sidecar), full=True, focus=False, extra=lyrics,
         text='full scan after a lyrics file is added next to a song, then its lyrics')
    step('sidecar', 'folder-cover', lambda c: put(c, 'Delta Duo/First Album/cover.png', c.library_files()[BETA_COVER]),
         full=True, focus=False, extra=lambda c: wait_cover(c, 'Delta Duo', lambda s: s['picture'] == 'blue'),
         text='full scan after a cover image is added to an album folder, then the album cover once it is resolved')
    replaced = step('sidecar', 'folder-cover-replaced', lambda c: put(c, BETA_COVER, GOLD, mtime=1700000900), full=True, focus=False,
                    extra=lambda c: wait_cover(c, 'Beta Band', lambda s: s['picture'] == 'gold'),
                    text='full scan after the cover image of an album folder is replaced, then the album cover once it is resolved')
    COMPANIONS[step('sidecar', 'folder-cover-removed', lambda c: drop(c, BETA_COVER), full=True, focus=False,
                    extra=lambda c: wait_cover(c, 'Beta Band', lambda s: s['picture'] is None),
                    text='full scan after the cover image of an album folder is deleted, then the album cover once it is resolved')] = [replaced]

    # -- playlist files ----------------------------------------------------------------------------------------------------------------
    road = NL.join(['#EXTM3U', '../Gamma Trio/Third Album/01 Blue Hour.mp3', '../Nowhere/Missing.mp3',
                    '../Delta Duo/First Album/01 Echo.flac', '']).encode()
    short = NL.join(['#EXTM3U', '../Alpha Artist/First Album/03 Closing.mp3', '']).encode()
    imported = step('playlist', 'import', lambda c: put(c, 'Playlists/Road.m3u', road), full=True, focus=False, extra=playlists,
                    text='full scan after a playlist file is added, then the playlists')
    step('playlist', 'edit', lambda c: put(c, 'Playlists/Favourites.m3u', short, mtime=1700000500), full=True, focus=False,
         extra=playlists, text='full scan after a playlist file is shortened, then the playlists')
    COMPANIONS[step('playlist', 'file-deleted', lambda c: drop(c, 'Playlists/Road.m3u'), full=True, focus=False, extra=playlists,
                    text='full scan after a playlist file is deleted, then the playlists')] = [imported]

    # -- identical content and an emptied folder --------------------------------------------------------------------------------------
    step('duplicate', 'copy', lambda c: put(c, 'Copies/Opening copy.mp3', c.library_files()[FIRST]), full=True,
         focus={'paths': ['Copies/', 'Alpha Artist/First Album/01'], 'albums': ['First Album']},
         text='full scan after a song file is copied to another folder')
    step('removed', 'last-file-in-folder', lambda c: drop(c, MOVED), full=True, focus={'paths': ['Samples/'], 'albums': ()},
         text='full scan after the last file of a folder is deleted')
