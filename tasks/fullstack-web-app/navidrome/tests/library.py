# Deterministic music library for the program checks (task-owned; not part of the runtime).
# Tagged mp3, flac, ogg and wav files with covers, lyrics and a playlist, built with numpy, soundfile and mutagen,
# which the verifier image has installed. Every build produces the same bytes.
import struct
import tempfile
import zlib
from pathlib import Path

import numpy as np
import soundfile as sf
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TALB, TCMP, TCON, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK, TSOP, USLT
from mutagen.oggvorbis import OggVorbis

RATE = 44100
NL = chr(10)
COVERS = {'red': (200, 30, 30), 'blue': (30, 60, 200), 'green': (30, 160, 60), 'gold': (220, 180, 30),
          'purple': (120, 40, 160), 'teal': (20, 150, 150)}
FORMATS = {'mp3': ('MP3', 'MPEG_LAYER_III'), 'flac': ('FLAC', 'PCM_16'), 'ogg': ('OGG', 'VORBIS'), 'wav': ('WAV', 'PCM_16')}


def png(color, size=48):
    # A plain colour square; the colour tells covers apart.
    row = bytes([0]) + bytes(color) * size

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    header = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    signature = bytes([137, 80, 78, 71, 13, 10, 26, 10])
    return signature + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(row * size, 9)) + chunk(b'IEND', b'')


def tone(freq, seconds):
    t = np.arange(int(RATE * seconds)) / RATE
    return (0.3 * np.sin(2 * np.pi * freq * t)).astype('float32')


def pair(value):
    return value if isinstance(value, tuple) else (value, None)


def number(value):
    n, total = pair(value)
    return str(n) + ('/' + str(total) if total else '')


def track(path, freq, seconds=1.0, **tags):
    return {'path': path, 'freq': freq, 'seconds': seconds, 'tags': tags or None}


def tracks():
    first = dict(artist=['Alpha Artist'], albumartist='Alpha Artist', album='First Album', year=2001, genre=['Rock'],
                 cover='red')
    second = dict(artist=['Beta Band'], albumartist='Beta Band', album='Second Album', year=2010, genre=['Electronic'])
    mixtape = dict(albumartist='Various Artists', album='Mixtape', year=2020, genre=['Pop'], compilation=True)
    third = dict(artist=['Gamma Trio', 'Guest One'], albumartist='Gamma Trio', album='Third Album', year=1999,
                 genre=['Jazz', 'Blues'], sortartist='Trio, Gamma', cover='green')
    duo = dict(artist=['Delta Duo'], albumartist='Delta Duo', album='First Album', year=2005, genre=['Folk'])
    accents = dict(artist=['Ünïcode Ärtist'], albumartist='Ünïcode Ärtist', album='Café Ω', year=2015,
                   genre=['Ambient'], cover='gold')
    return [
        track('Alpha Artist/First Album/01 Opening.mp3', 220, 1.0, title='Opening', track=(1, 3),
              lyrics='Line one' + NL + 'Line two', **first),
        track('Alpha Artist/First Album/02 Middle.mp3', 247, 2.0, title='Middle', track=(2, 3), **first),
        track('Alpha Artist/First Album/03 Closing.mp3', 262, 3.0, title='Closing', track=(3, 3), **first),
        track('Beta Band/Second Album/CD1/01 Intro.flac', 262, 1.0, title='Intro', track=(1, 2), disc=(1, 2), **second),
        track('Beta Band/Second Album/CD1/02 Drift.flac', 294, 2.0, title='Drift', track=(2, 2), disc=(1, 2), **second),
        track('Beta Band/Second Album/CD2/01 Reprise.flac', 330, 1.0, title='Reprise', track=(1, 1), disc=(2, 2), **second),
        track('Various/Mixtape/01 Single A.ogg', 330, 1.0, artist=['Gamma'], title='Single A', track=(1, 3), **mixtape),
        track('Various/Mixtape/02 Single B.ogg', 349, 1.0, artist=['Delta'], title='Single B', track=(2, 3), **mixtape),
        track('Various/Mixtape/03 Single C.ogg', 392, 2.0, artist=['Gamma'], title='Single C', track=(3, 3), **mixtape),
        track('Gamma Trio/Third Album/01 Blue Hour.mp3', 440, 1.0, title='Blue Hour', track=(1, 2), **third),
        track('Gamma Trio/Third Album/02 Late Train.mp3', 494, 1.0, title='Late Train', track=(2, 2), **third),
        track('Delta Duo/First Album/01 Echo.flac', 523, 1.0, title='Echo', track=(1, 1), **duo),
        track('Unicode/Café Ω/01 Naïve Ω.flac', 587, 1.0, title='Naïve Ω', track=(1, 1), **accents),
        track('Untagged/loose track.mp3', 659, 1.0),
        track('Samples/click.wav', 784, 0.5),
    ]


def extras():
    # Files that are not audio: a folder cover, a lyrics file next to its song and a playlist.
    return {
        'Beta Band/Second Album/cover.png': png(COVERS['blue']),
        'Delta Duo/First Album/01 Echo.lrc': ('[00:00.00]Hello' + NL + '[00:01.00]World' + NL).encode(),
        'Playlists/Favourites.m3u': NL.join(['#EXTM3U', '../Alpha Artist/First Album/01 Opening.mp3',
                                             '../Beta Band/Second Album/CD1/01 Intro.flac', '']).encode(),
    }


def put_pair(audio, name, total_name, value):
    n, total = pair(value)
    audio[name] = [str(n)]
    if total:
        audio[total_name] = [str(total)]


def tag_id3(path, t):
    tags = ID3()
    tags.add(TIT2(encoding=3, text=[t['title']]))
    tags.add(TPE1(encoding=3, text=t['artist']))
    tags.add(TALB(encoding=3, text=[t['album']]))
    tags.add(TRCK(encoding=3, text=[number(t['track'])]))
    if 'albumartist' in t:
        tags.add(TPE2(encoding=3, text=[t['albumartist']]))
    if 'disc' in t:
        tags.add(TPOS(encoding=3, text=[number(t['disc'])]))
    if 'year' in t:
        tags.add(TDRC(encoding=3, text=[str(t['year'])]))
    if 'genre' in t:
        tags.add(TCON(encoding=3, text=t['genre']))
    if t.get('compilation'):
        tags.add(TCMP(encoding=3, text=['1']))
    if 'sortartist' in t:
        tags.add(TSOP(encoding=3, text=[t['sortartist']]))
    if 'lyrics' in t:
        tags.add(USLT(encoding=3, lang='eng', desc='', text=t['lyrics']))
    if 'cover' in t:
        tags.add(APIC(encoding=3, mime='image/png', type=3, desc='', data=png(COVERS[t['cover']])))
    tags.save(str(path), v1=0, v2_version=4)


def tag_vorbis(audio, t):
    audio['title'] = [t['title']]
    audio['artist'] = t['artist']
    audio['album'] = [t['album']]
    put_pair(audio, 'tracknumber', 'tracktotal', t['track'])
    if 'albumartist' in t:
        audio['albumartist'] = [t['albumartist']]
    if 'disc' in t:
        put_pair(audio, 'discnumber', 'disctotal', t['disc'])
    if 'year' in t:
        audio['date'] = [str(t['year'])]
    if 'genre' in t:
        audio['genre'] = t['genre']
    if t.get('compilation'):
        audio['compilation'] = ['1']
    if 'sortartist' in t:
        audio['artistsort'] = [t['sortartist']]
    if 'lyrics' in t:
        audio['lyrics'] = [t['lyrics']]


OGG_SERIAL = 0x4E445032


def ogg_crc_table():
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = ((r << 1) ^ 0x04C11DB7) if r & 0x80000000 else (r << 1)
            r &= 0xFFFFFFFF
        table.append(r)
    return table


OGG_CRC = ogg_crc_table()


def ogg_crc(data):
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ OGG_CRC[((crc >> 24) & 0xFF) ^ byte]
    return crc


def fix_ogg_serial(path, serial=OGG_SERIAL):
    # libsndfile picks a random Ogg stream serial number; rewrite it and the page checksums so builds are identical.
    data = bytearray(Path(path).read_bytes())
    offset = 0
    while offset < len(data):
        if data[offset:offset + 4] != b'OggS':
            raise ValueError('not an Ogg page at ' + str(offset))
        segments = data[offset + 26]
        size = 27 + segments + sum(data[offset + 27:offset + 27 + segments])
        data[offset + 14:offset + 18] = struct.pack('<I', serial)
        data[offset + 22:offset + 26] = bytes(4)
        data[offset + 22:offset + 26] = struct.pack('<I', ogg_crc(bytes(data[offset:offset + size])))
        offset += size
    Path(path).write_bytes(bytes(data))


def write_track(root, spec):
    path = Path(root) / spec['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    kind = path.suffix[1:]
    fmt, subtype = FORMATS[kind]
    sf.write(str(path), tone(spec['freq'], spec['seconds']), RATE, format=fmt, subtype=subtype)
    tags = spec['tags']
    if not tags:
        return
    if kind == 'mp3':
        tag_id3(path, tags)
    elif kind == 'flac':
        audio = FLAC(str(path))
        tag_vorbis(audio, tags)
        if 'cover' in tags:
            picture = Picture()
            picture.type = 3
            picture.mime = 'image/png'
            picture.desc = ''
            picture.data = png(COVERS[tags['cover']])
            audio.add_picture(picture)
        audio.save()
    elif kind == 'ogg':
        audio = OggVorbis(str(path))
        tag_vorbis(audio, tags)
        audio.save()
        fix_ogg_serial(path)
    else:
        raise ValueError('no tags are written to ' + kind + ' files')


def build(root):
    # Write the whole library below root; returns the sorted relative paths.
    for spec in tracks():
        write_track(root, spec)
    for relative, data in extras().items():
        target = Path(root) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob('*') if p.is_file())


def materialize():
    # The library as {relative path: bytes}, built in a scratch directory.
    with tempfile.TemporaryDirectory(prefix='navidrome-library-') as scratch:
        names = build(scratch)
        return {name: (Path(scratch) / name).read_bytes() for name in names}
