'''Lyrics files next to the songs: plain text, LRC (with offsets, empty and repeated lines), TTML, SRT and other text,
and which source wins when a song has several.

The fixture adds the lyrics files and runs a full scan; every case then reads one song, so no case depends on another.
The library already has a song with embedded lyrics (Opening) and one with an LRC file (Echo).'''
import base64
import time

from api_browse import song_of

NL = chr(10)
PAGE = {'_start': 0, '_end': 50, '_sort': 'title', '_order': 'ASC'}
FILES = {
    'Alpha Artist/First Album/03 Closing.txt': 'Plain first line' + NL + 'Plain second line' + NL,
    'Alpha Artist/First Album/01 Opening.lrc': '[00:00.50]Sidecar wins' + NL + '[00:01.00]Over embedded' + NL,
    'Delta Duo/First Album/01 Echo.txt': 'Echo text' + NL,
    'Beta Band/Second Album/CD1/01 Intro.ttml': ('<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml" xml:lang="en"><body><div>'
                                                 '<p begin="00:00:01.000" end="00:00:02.000">TTML line</p></div></body></tt>'),
    'Beta Band/Second Album/CD1/02 Drift.srt': '1' + NL + '00:00:01,000 --> 00:00:02,000' + NL + 'SRT line' + NL + NL,
    'Gamma Trio/Third Album/01 Blue Hour.yaml': 'lyrics: yaml line' + NL,
    'Gamma Trio/Third Album/02 Late Train.lrc': ('[ar:Gamma Trio]' + NL + '[ti:Late Train]' + NL + '[offset:+500]' + NL +
                                                 '[00:01.00]Offset line' + NL + '[00:02.00]' + NL + '[00:03.00]After a gap' + NL),
    'Various/Mixtape/01 Single A.lrc': '[00:01.00][00:03.00]Repeated line' + NL + '[00:02.00]Middle line' + NL,
}
SONGS = [('closing', 'Closing'), ('opening', 'Opening'), ('echo', 'Echo'), ('intro', 'Intro'), ('drift', 'Drift'),
         ('blue-hour', 'Blue Hour'), ('late-train', 'Late Train'), ('single-a', 'Single A')]
COMPANIONS = {}
DEPENDS = {}


def prepare(c, relaxed=False):
    for path, text in FILES.items():
        data = text.encode()
        answer = c.call({'op': 'library_put', 'path': path, 'base64': base64.b64encode(data).decode()})
        assert answer.get('size') == len(data), 'library_put ' + path
    c.rescan(True)
    time.sleep(1.0)


def build(s):
    nat, sub = s.nat, s.sub
    nat('lyrics-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    s.add('lyrics-fixture', 'library', 'files', prepare, description='add the lyrics files to the library and run a full scan')
    reads = {}
    for step, title in SONGS:
        reads[title] = sub('lyrics', 'getLyricsBySongId', step, 'getLyricsBySongId', id=song_of(title))
    for step, artist, title in (('plain', 'Alpha Artist', 'Closing'), ('sidecar-over-embedded', 'Alpha Artist', 'Opening')):
        sub('lyrics', 'getLyrics', step, 'getLyrics', artist=artist, title=title)
    # The song keeps its embedded lyrics in the native API even when a file next to it wins.
    nat('lyrics', 'native', 'embedded', 'GET', lambda c: 'song/' + song_of('Opening')(c), status=200, fields=['title', 'lyrics'],
        hint='song')
