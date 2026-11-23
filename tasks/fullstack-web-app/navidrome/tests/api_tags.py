'''Tag matrix: how the product reads the tags of mp3 (ID3 2.4 and 2.3), flac and ogg files into songs, albums, artists
and genres.

The fixture adds the tagged files (rich tags, split and multiple artists and genres, dates, special characters, missing
and extra track and disc numbers, a compilation, release types, parental advisories, moods and ReplayGain values) to the
library and runs a full scan. Every case then reads one result, and no case depends on another: a file the product does
not list fails only the cases that read it.'''
import base64
import tempfile
import time
from pathlib import Path

from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.id3 import COMM, ID3, TBPM, TCOM, TDOR, TDRC, TDRL, TEXT, TIPL, TIT1, TLAN, TMCL, TPE3, TPUB, TSO2, TSOA, TSOC, TSOT, TSRC, TSST, TXXX

import library
from api_browse import slug

Q = chr(34)
MBZ = '8f3d4b1a-2c6e-4d7f-9a10-000000000001'
MBZ_OGG = '8f3d4b1a-2c6e-4d7f-9a10-000000000002'
PAGE = {'_start': 0, '_end': 200, '_sort': 'path', '_order': 'ASC'}
BY_NAME = {'_start': 0, '_end': 200, '_sort': 'name', '_order': 'ASC'}
SONG = ['title', 'artist', 'albumArtist', 'genre', 'genres', 'year', 'date', 'releaseDate', 'originalDate', 'originalYear', 'releaseYear',
        'bpm', 'comment', 'trackNumber', 'discNumber', 'discSubtitle', 'sortTitle', 'sortAlbumName', 'sortAlbumArtistName',
        'orderTitle', 'mbzAlbumId', 'rgTrackGain', 'rgTrackPeak', 'rgAlbumGain', 'rgAlbumPeak', 'explicitStatus', 'compilation',
        'participants', 'tags']
ALBUM = ['name', 'albumArtist', 'minYear', 'maxYear', 'date', 'originalDate', 'releaseDate', 'songCount', 'discs', 'genres',
         'mbzAlbumId', 'sortAlbumName', 'compilation', 'explicitStatus', 'participants', 'tags']
ID3_EXTRA = [
    TDRC(encoding=3, text=['2001-03-02']), TDRL(encoding=3, text=['2002-05-06']), TDOR(encoding=3, text=['1995-03-04']),
    TCOM(encoding=3, text=['Comp One', 'Comp Two']), TEXT(encoding=3, text=['Lyric Writer']), TPE3(encoding=3, text=['Conductor Name']),
    TSOT(encoding=3, text=['Rich, The']), TSOA(encoding=3, text=['Album, Rich']), TSO2(encoding=3, text=['Artist, Tagged']),
    TSOC(encoding=3, text=['One, Comp']), COMM(encoding=3, lang='eng', desc='', text=['A comment']), TBPM(encoding=3, text=['120']),
    TIT1(encoding=3, text=['Grouping']), TSST(encoding=3, text=['Subtitle']), TLAN(encoding=3, text=['eng']),
    TSRC(encoding=3, text=['USABC2600001']), TPUB(encoding=3, text=['Label Name']),
    TXXX(encoding=3, desc='MusicBrainz Album Id', text=[MBZ]), TXXX(encoding=3, desc='REPLAYGAIN_TRACK_GAIN', text=['-6.50 dB']),
    TIPL(encoding=3, people=[['producer', 'Producer One'], ['engineer', 'Engineer One']]),
    TMCL(encoding=3, people=[['guitar', 'Guitarist One']]),
]
FLAC_EXTRA = {
    'date': ['2001-03-02'], 'originaldate': ['1995-03-04'], 'releasedate': ['2002-05-06'], 'composer': ['Comp One', 'Comp Two'],
    'lyricist': ['Lyric Writer'], 'conductor': ['Conductor Name'], 'titlesort': ['Rich Flac, The'], 'albumsort': ['Album, Rich'],
    'albumartistsort': ['Artist, Tagged'], 'composersort': ['One, Comp'], 'comment': ['A comment'], 'bpm': ['120'],
    'grouping': ['Grouping'], 'discsubtitle': ['Subtitle'], 'language': ['eng'], 'isrc': ['USABC2600002'], 'label': ['Label Name'],
    'musicbrainz_albumid': [MBZ], 'replaygain_track_gain': ['-6.50 dB'], 'producer': ['Producer One'],
    'performer': ['Guitarist One (guitar)'],
}
SPECS = [
    dict(path='Tags/Rich/01 Rich.mp3', title='Rich', freq=300, extra=ID3_EXTRA),
    dict(path='Tags/Rich/02 Rich Flac.flac', title='Rich Flac', freq=310, extra=FLAC_EXTRA, tags=dict(track=(2, 2))),
    dict(path='Tags/Split/01 Split.mp3', title='Split', freq=320,
         tags=dict(artist=['Split One/Split Two'], albumartist='Split Group', album='Split Album', genre=['Rock;Pop'], track=(1, 2))),
    dict(path='Tags/Split/02 Feat.mp3', title='Feat', freq=330,
         tags=dict(artist=['Lead Singer feat. Guest Star'], albumartist='Split Group', album='Split Album', genre=['Jazz/Blues'], track=(2, 2))),
    dict(path='Tags/Dates/01 Year Only.mp3', title='Year Only', freq=340, tags=dict(album='Dates Album', year=2003, track=(1, 3))),
    dict(path='Tags/Dates/02 Full Date.mp3', title='Full Date', freq=350, extra=[TDRC(encoding=3, text=['2004-07-08'])],
         tags=dict(album='Dates Album', year=2004, track=(2, 3))),
    dict(path='Tags/Dates/03 No Date.mp3', title='No Date', freq=360, without=('year',), tags=dict(album='Dates Album', track=(3, 3))),
    dict(path='Tags/Chars/01 Chars.mp3', title='Quote ' + Q + ' & <b> Ω 日本語', freq=380,
         tags=dict(artist=['Chars ' + Q + 'Artist' + Q], albumartist='Chars ' + Q + 'Artist' + Q, album='Chars & <Album>')),
    dict(path='Tags/Track/01 No Track.mp3', title='No Track', freq=390, drop=('TRCK',), tags=dict(album='Track Album')),
    dict(path='Tags/Track/02 Disc Three.mp3', title='Disc Three', freq=400, tags=dict(album='Track Album', track=(5, 9), disc=(3, 4))),
    # Vorbis comments of an Ogg file.
    dict(path='Tags/Ogg/01 Rich Ogg.ogg', title='Rich Ogg', freq=410, tags=dict(album='Ogg Album', artist=['Ogg Artist'], albumartist='Ogg Artist'),
         extra={'date': ['2001-03-02'], 'originaldate': ['1995-03-04'], 'composer': ['Comp Three'], 'comment': ['Ogg comment'],
                'bpm': ['98'], 'discsubtitle': ['Side A'], 'label': ['Ogg Label'], 'musicbrainz_albumid': [MBZ_OGG]}),
    # Several artists, album artists and genres given as separate values.
    dict(path='Tags/Multi/01 Multi Artists.flac', title='Multi Artists', freq=420,
         tags=dict(album='Multi Album', artist=['Ann Artist', 'Ben Artist'], albumartist='Ann Artist', track=(1, 2)),
         extra={'albumartist': ['Ann Artist', 'Ben Artist'], 'artists': ['Ann Artist', 'Ben Artist']}),
    dict(path='Tags/Multi/02 Many Genres.flac', title='Many Genres', freq=430,
         tags=dict(album='Multi Album', artist=['Ann Artist'], albumartist='Ann Artist', genre=['Rock', 'Jazz', 'Folk'], track=(2, 2)),
         extra={'albumartist': ['Ann Artist', 'Ben Artist']}),
    # ID3 version 2.3: the year frame and the slash between artists.
    dict(path='Tags/V23/01 Version Three.mp3', title='Version Three', freq=440, v23=True,
         tags=dict(album='V23 Album', artist=['Vee One/Vee Two'], albumartist='Vee One', year=1987, track=(3, 12), disc=(2, 3))),
    # A compilation without an album artist.
    dict(path='Tags/Comp/01 Comp One.mp3', title='Comp One', freq=450, without=('albumartist',),
         tags=dict(album='Comp Album', artist=['Solo One'], compilation=True, track=(1, 2))),
    dict(path='Tags/Comp/02 Comp Two.mp3', title='Comp Two', freq=460, without=('albumartist',),
         tags=dict(album='Comp Album', artist=['Solo Two'], compilation=True, track=(2, 2))),
    # Release type, status and catalogue number.
    dict(path='Tags/Live/01 Live Track.flac', title='Live Track', freq=470,
         tags=dict(album='Live Album', artist=['Live Band'], albumartist='Live Band'),
         extra={'releasetype': ['album', 'live'], 'releasestatus': ['official'], 'catalognumber': ['CAT-001']}),
    # Parental advisory: explicit and clean.
    dict(path='Tags/Advisory/01 Explicit Song.mp3', title='Explicit Song', freq=480, extra=[TXXX(encoding=3, desc='ITUNESADVISORY', text=['1'])],
         tags=dict(album='Advisory Album', artist=['Advisory Artist'], albumartist='Advisory Artist', track=(1, 2))),
    dict(path='Tags/Advisory/02 Clean Song.mp3', title='Clean Song', freq=490, extra=[TXXX(encoding=3, desc='ITUNESADVISORY', text=['2'])],
         tags=dict(album='Advisory Album', artist=['Advisory Artist'], albumartist='Advisory Artist', track=(2, 2))),
    # Moods and the album and track ReplayGain values.
    dict(path='Tags/Mood/01 Mood Song.flac', title='Mood Song', freq=500,
         tags=dict(album='Mood Album', artist=['Mood Artist'], albumartist='Mood Artist'),
         extra={'mood': ['Happy', 'Calm'], 'replaygain_album_gain': ['-3.20 dB'], 'replaygain_album_peak': ['0.912'],
                'replaygain_track_gain': ['-2.10 dB'], 'replaygain_track_peak': ['0.801']}),
]
ALBUMS = ['Rich Album', 'Split Album', 'Dates Album', 'Track Album', 'Chars & <Album>', 'Ogg Album', 'Multi Album', 'V23 Album',
          'Comp Album', 'Live Album', 'Advisory Album', 'Mood Album']
COMPANIONS = {}
DEPENDS = {}


def make(work, spec):
    tags = dict(artist=['Tagged Artist'], albumartist='Tagged Artist', album='Rich Album', year=2001, genre=['Rock'], track=(1, 1))
    tags.update(spec.get('tags', {}))
    for key in spec.get('without', ()):
        tags.pop(key, None)
    library.write_track(work, library.track(spec['path'], spec['freq'], 1.0, title=spec['title'], **tags))
    target = work / spec['path']
    extra, drop = spec.get('extra'), spec.get('drop', ())
    if isinstance(extra, dict):
        audio = OggVorbis(str(target)) if target.suffix == '.ogg' else FLAC(str(target))
        for key, value in extra.items():
            audio[key] = value
        audio.save()
        if target.suffix == '.ogg':
            library.fix_ogg_serial(target)
    elif extra or drop or spec.get('v23'):
        audio = ID3(str(target))
        for name in drop:
            audio.delall(name)
        for frame in extra or ():
            audio.add(frame)
        if spec.get('v23'):
            audio.update_to_v23()
        audio.save(str(target), v1=0, v2_version=3 if spec.get('v23') else 4)
    return target.read_bytes()


def cover_map(c):
    '''Which of the tagged songs offer a cover id right now.'''
    rows = [x for x in c.native('GET', 'song', params=PAGE)['body'] if str(x.get('path', '')).startswith('Tags/')]
    return {x['id']: bool((c.reply(c.subsonic('getSong', id=x['id'])).get('song') or {}).get('coverArt')) for x in rows}


def settle_covers(c, window=10.0, timeout=60.0):
    '''The product resolves cover art in the background after a scan: a song without any image keeps offering a cover id until its worker has found out that there is none, one album after the other. The cover ids are read until they have stopped changing for a while, so every case sees the settled state; a product that keeps changing runs into the timeout and the cases compare what it shows.'''
    deadline = time.monotonic() + timeout
    last, since = None, time.monotonic()
    while time.monotonic() < deadline:
        now = cover_map(c)
        if now != last:
            last, since = now, time.monotonic()
        elif time.monotonic() - since >= window:
            return
        time.sleep(1.0)


def prepare(c, relaxed=False):
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        for spec in SPECS:
            data = make(work, spec)
            answer = c.call({'op': 'library_put', 'path': spec['path'], 'base64': base64.b64encode(data).decode()})
            assert answer.get('size') == len(data), 'library_put ' + spec['path']
    c.rescan(True)
    time.sleep(2.0)
    settle_covers(c)
    c.state['tagsongs'] = [x for x in c.native('GET', 'song', params=PAGE)['body'] if str(x.get('path', '')).startswith('Tags/')]
    c.state['tagalbums'] = c.native('GET', 'album', params=BY_NAME)['body']


def song_id(title):
    def find(c):
        found = [x['id'] for x in c.state['tagsongs'] if x.get('title') == title]
        assert found, 'the song is not listed: ' + title
        return found[0]
    return find


def song_path(title):
    return lambda c: 'song/' + song_id(title)(c)


def album_id(name):
    def find(c):
        found = [x['id'] for x in c.state['tagalbums'] if x.get('name') == name]
        assert found, 'the album is not listed: ' + name
        return found[0]
    return find


def album_path(name):
    return lambda c: 'album/' + album_id(name)(c)


def build(s):
    nat, sub = s.nat, s.sub
    s.add('tags-fixture', 'library', 'files', prepare, description='add the tagged files to the library and run a full scan')
    for spec in SPECS:
        title = spec['title']
        nat('tags', 'song', slug(title), 'GET', song_path(title), status=200, fields=SONG, hint='song')
        sub('tags-subsonic', 'getSong', slug(title), 'getSong', id=song_id(title), unordered=['song.contributors'])
    for name in ALBUMS:
        nat('tags', 'album', slug(name), 'GET', album_path(name), status=200, fields=ALBUM, hint='album')
        sub('tags-subsonic', 'getAlbum', slug(name), 'getAlbum', id=album_id(name), unordered=['album.song.contributors'])
    nat('tags', 'list', 'songs', 'GET', 'song', params=PAGE, status=200, fields=['title', 'path'])
    nat('tags', 'list', 'albums', 'GET', 'album', params=BY_NAME, status=200, fields=['name', 'albumArtist', 'songCount'])
    nat('tags', 'list', 'artists', 'GET', 'artist', params=BY_NAME, status=200, fields=['name'])
    nat('tags', 'list', 'genres', 'GET', 'genre', params=BY_NAME, status=200, fields=['name'])
    sub('tags-subsonic', 'getGenres', 'all', 'getGenres', unordered=['genres.genre'])
    sub('tags-subsonic', 'getArtists', 'all', 'getArtists')
    for query in ('Rich', 'Guest', 'Comp One'):
        sub('tags-subsonic', 'search3', slug(query), 'search3', query=query,
            unordered=['searchResult3.song.contributors', 'searchResult3.song', 'searchResult3.album', 'searchResult3.artist'])
