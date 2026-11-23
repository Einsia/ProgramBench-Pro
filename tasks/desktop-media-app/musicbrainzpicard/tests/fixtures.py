"""Deterministic input documents: small audio files of every format the product tags, cover images, profiles,
sessions and command files.

Audio comes from the verifier's own FFmpeg (bit-exact flags, no container metadata) or, for formats FFmpeg cannot
write (Monkey's Audio, Musepack, OptimFROG, TAK, DSF, DSDIFF, MIDI), from minimal hand-made stream headers followed
by silence; tags are written with the verifier's mutagen in exactly the raw form a fixture asks for. Documents are
generated once per verifier run in a private temporary directory and uploaded to the runtime's input folder.
"""
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import zlib

FRONT_JPEG = (
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYn'
    'KSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgo'
    'KCgoKCgoKCj/wAARCABAAEADASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAAAAMG/8QAFhABAQEAAAAAAAAAAAAAAAAAABES'
    '/8QAFgEBAQEAAAAAAAAAAAAAAAAAAAUH/8QAFhEBAQEAAAAAAAAAAAAAAAAAABMU/9oADAMBAAIRAxEAPwDFUqdKjQaNoUpU6Uga'
    'FKVOlIGhSlTpSBoTpUtGlmCHoVpUtGiBoVpUtGiBoVpUtGiBoTpU6VYgh6FKVOlIGhSlTpSBoUpU6UgaE9Gk6Vagh6FNGk6UgaFN'
    'Gk6UgaFNGk6UgaH/2Q=='
)
BACK_PNG = (
    'iVBORw0KGgoAAAANSUhEUgAAADAAAAAgAQMAAABuGmlfAAAABlBMVEUggEDw4EAVX5X6AAAAEklEQVQI12NgIBf8BwJ6UuQBAOZ1'
    'P8FrsX/oAAAAAElFTkSuQmCC'
)
LARGE_JPEG = (
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0d'
    'Hx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4e'
    'Hh4eHh4eHh7/wAARCAEsASwDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAAAAMH/8QAFxABAQEBAAAAAAAAAAAAAAAAABIR'
    'Yf/EABkBAQEBAQEBAAAAAAAAAAAAAAAEAgMFBv/EABYRAQEBAAAAAAAAAAAAAAAAAAAREv/aAAwDAQACEQMRAD8AwOSVZJfT7edE'
    'pJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJ'
    'NkSklWSTZEpJVkk2RKSVZJNkSklWSTZFpJWklLtuIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIj'
    'JK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyLSSrJKXbcSklWSTZEpJVkk2RKSVZ'
    'JNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEp'
    'JVkk2RKSVZJNkWklaSU23SIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrS'
    'SbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyLSSrJKXbcSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2R'
    'KSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkWklaS'
    'Uu3SIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsi'
    'MkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyLSSrJKXbpEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSV'
    'ZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZFpJWklNtuIyStJJsiMkrSSb'
    'IjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIyStJJsiMkrSSbIjJK0kmyIySt'
    'JJsiMkrSSbIjJK0kmyLSSrJKXbpEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2'
    'RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZFpJXklNtuISSvJJsiEkrySbIhJK8kmyISSvJJsiEk'
    'rySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmy'
    'KySrJKXbpEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZEpJ'
    'Vkk2RKSVZJNkSklWSTZEpJVkk2RKSVZJNkSklWSTZFpJXklLtuISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJ'
    'siEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyKySrPCeJttxKSVZ4Tw'
    '2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2'
    'RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2RKSVZ4Tw2ReSVZJS7dIlJKskmyJSSrJJsiUkqySbIlJKskmyJSSrJJs'
    'iUkqySbIlJKskmyJSSrJJsiUkqySbIlJKskmyJSSrJJsiUkqySbIlJKskmyJSSrJJsiUkqySbIlJKskmyJSSrJJsiUkqySbItJK0'
    'kptukRklaSTZEZJWkk2RGSVpJNkRklaSTZEZJWkk2RGSVpJNkRklaSTZEZJWkk2RGSVpJNkRklaSTZEZJWkk2RGSVpJNkRklaSTZ'
    'EZJWkk2RGSVpJNkRklaSTZEZJWkk2RGSVpJNkWklWSUu24lJKskmyJSSrJJsiUkqySbIlJKskmyJSSrJJsiUkqySbIlJKskmyJSS'
    'rJJsiUkqySbIlJKskmyJSSrJJsiUkqySbIlJKskmyJSSrJJsiUkqySbIlJKskmyJSSrJJsiUkqySbItJK0kpdukRklaSTZEZJWkk'
    '2RGSVpJNkRklaSTZEZJWkk2RGSVpJNkRklaSTZEZJWkk2RGSVpJNkRklaSTZEZJWkk2RGSVpJNkRklaSTZEZJWkk2RGSVpJNkRkl'
    'aSTZEZJWkk2RGSVpJNkVkleSU224hJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8km'
    'yISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIhJK8kmyISSvJJsiEkrySbIrJKuGJtNxKSVcMNESklXDDREpJVww0RKSVcMNESk'
    'lXDDREpJVww0RKSVcMNESklXDDREpJVww0RKSVcMNESklXDDREpJVww0RKSVcMNESklXDDREpJVww0RKSVcMNESklXDDREpJVww0'
    'R//Z'
)
IMAGES = {'front.jpg': FRONT_JPEG, 'back.png': BACK_PNG, 'large.jpg': LARGE_JPEG}
MIMES = {'.jpg': 'image/jpeg', '.png': 'image/png'}


def image(name):
    return base64.b64decode(''.join(IMAGES[name]))


# -- audio -------------------------------------------------------------------------------------------------------
# kind -> (suffix, FFmpeg arguments or None for a hand-made stream)
KINDS = {
    'mp3': ('.mp3', ['-c:a', 'libmp3lame', '-b:a', '64k', '-write_xing', '0', '-id3v2_version', '0',
                     '-write_id3v1', '0']),
    'mp2': ('.mp2', ['-c:a', 'mp2', '-b:a', '64k', '-f', 'mp2']),
    'flac': ('.flac', ['-c:a', 'flac']),
    'ogg': ('.ogg', ['-c:a', 'libvorbis', '-q:a', '0']),
    'opus': ('.opus', ['-c:a', 'libopus', '-b:a', '32k']),
    'spx': ('.spx', ['-c:a', 'libspeex', '-ar', '16000']),
    'oggflac': ('.oga', ['-c:a', 'flac', '-f', 'ogg']),
    'm4a': ('.m4a', ['-c:a', 'aac', '-b:a', '64k', '-f', 'mp4']),
    'alac': ('.m4a', ['-c:a', 'alac', '-f', 'mp4']),
    'wma': ('.wma', ['-c:a', 'wmav2', '-b:a', '64k', '-f', 'asf']),
    'wv': ('.wv', ['-c:a', 'wavpack', '-f', 'wv']),
    'tta': ('.tta', ['-c:a', 'tta', '-f', 'tta']),
    'aiff': ('.aiff', ['-c:a', 'pcm_s16be', '-f', 'aiff']),
    'wav': ('.wav', ['-c:a', 'pcm_s16le', '-f', 'wav']),
    'ac3': ('.ac3', ['-c:a', 'ac3', '-b:a', '96k', '-f', 'ac3']),
    'aac': ('.aac', ['-c:a', 'aac', '-b:a', '64k', '-f', 'adts']),
    'ape': ('.ape', None),
    'mpc': ('.mpc', None),
    'ofr': ('.ofr', None),
    'tak': ('.tak', None),
    'dsf': ('.dsf', None),
    'dff': ('.dff', None),
    'mid': ('.mid', None),
}
FAMILY = {'mp3': 'id3', 'mp2': 'id3', 'tta': 'id3', 'aiff': 'id3', 'wav': 'id3', 'dsf': 'id3', 'dff': 'id3',
          'flac': 'vorbis', 'ogg': 'vorbis', 'opus': 'vorbis', 'spx': 'vorbis', 'oggflac': 'vorbis',
          'm4a': 'mp4', 'alac': 'mp4', 'wma': 'asf', 'ape': 'ape', 'mpc': 'ape', 'wv': 'ape', 'ofr': 'ape',
          'tak': 'ape', 'aac': 'ape', 'ac3': 'ape', 'mid': 'none'}


def ffmpeg(path, args, seconds, freq, channels, rate):
    source = f'sine=frequency={freq}:sample_rate={rate}:duration={seconds}'
    layout = ['-ac', str(channels)]
    command = ['ffmpeg', '-loglevel', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i', source, *layout,
               '-map_metadata', '-1', '-fflags', '+bitexact', '-flags:a', '+bitexact', *args, str(path)]
    done = subprocess.run(command, capture_output=True, timeout=120)
    if done.returncode:
        raise RuntimeError('ffmpeg failed: ' + done.stderr.decode(errors='replace')[-400:])


def monkeys_audio(seconds, rate=44100, channels=2):
    """Monkey's Audio 3.99 header (descriptor + header), then silence."""
    blocks = int(seconds*rate)
    per_frame = 73728*4
    frames = max(1, -(-blocks//per_frame))
    final = blocks-(frames-1)*per_frame
    head = bytearray(76)
    head[0:4] = b'MAC '
    struct.pack_into('<H', head, 4, 3990)
    struct.pack_into('<I', head, 8, 52)
    struct.pack_into('<I', head, 12, 24)
    struct.pack_into('<IIIHHI', head, 56, per_frame, final, frames, 16, channels, rate)
    return bytes(head)+bytes(2048)


def musepack(seconds, rate=44100):
    """Musepack SV7 stream header, then silence."""
    frames = int(seconds*rate+576)//1152
    head = bytearray(32)
    head[0:4] = b'MP+\x17'
    struct.pack_into('<II', head, 4, frames, 0)
    return bytes(head)+bytes(2048)


def optimfrog(seconds, rate=44100, channels=2):
    head = bytearray(76)
    head[0:4] = b'OFR '
    struct.pack_into('<IIHBBIH', head, 4, 15, int(seconds*rate)*channels, 0, 2, channels-1, rate, 0x0230)
    return bytes(head)+bytes(2048)


class _Bits:
    """Least-significant-bit-first writer (TAK metadata)."""

    def __init__(self):
        self.value, self.count = 0, 0

    def put(self, value, bits):
        self.value |= (value & ((1 << bits)-1)) << self.count
        self.count += bits

    def data(self):
        return self.value.to_bytes((self.count+7)//8, 'little')


def tak(seconds, rate=44100, channels=2):
    samples = int(seconds*rate)
    info = _Bits()
    info.put(2, 6)          # codec
    info.put(0, 4)          # profile
    info.put(0, 4)          # frame duration
    info.put(samples, 35)
    info.put(0, 3)          # data type
    info.put(rate-6000, 18)
    info.put(16-8, 5)
    info.put(channels-1, 4)
    info.put(0, 1)
    body = info.data()
    body = body+bytes(max(0, 10-len(body)))
    stream_info = body+bytes(3)  # CRC
    def block(kind, payload):
        size = len(payload)
        return bytes([kind & 0x7f])+struct.pack('<I', size)[:3]+payload
    encoder = bytes([3, 2, 2])+bytes(3)
    return b'tBaK'+block(1, stream_info)+block(4, encoder)+block(0, b'')+bytes(2048)


def dsf(seconds, rate=2822400, channels=2):
    block = 4096
    samples = int(seconds*rate)
    blocks = max(1, -(-samples//(block*8)))
    data = bytes(blocks*block*channels)
    fmt = struct.pack('<4sQIIIIIIQI4s', b'fmt ', 52, 1, 0, 2 if channels == 2 else 1, channels, rate, 1, samples,
                      block, b'\0\0\0\0')
    data_chunk = struct.pack('<4sQ', b'data', 12+len(data))+data
    total = 28+len(fmt)+len(data_chunk)
    return struct.pack('<4sQQQ', b'DSD ', 28, total, 0)+fmt+data_chunk


def dsdiff(seconds, rate=2822400, channels=2):
    def chunk(cid, payload):
        pad = b'\0' if len(payload) % 2 else b''
        return cid+struct.pack('>Q', len(payload))+payload+pad
    fver = chunk(b'FVER', struct.pack('>I', 0x01050000))
    prop = chunk(b'PROP', b'SND '+chunk(b'FS  ', struct.pack('>I', rate))
                 + chunk(b'CHNL', struct.pack('>H', channels)+b'SLFTSRGT'[:4*channels])
                 + chunk(b'CMPR', b'DSD '+b'\x0enot compressed\x00'))
    sound = chunk(b'DSD ', bytes(int(seconds*rate)//8*channels))
    body = b'DSD '+fver+prop+sound
    return b'FRM8'+struct.pack('>Q', len(body))+body


def midi(seconds):
    """One track: tempo 500000 us per quarter at 480 ticks, notes spanning the duration."""
    ticks = int(seconds*960)
    def var(value):
        out = [value & 0x7f]
        value >>= 7
        while value:
            out.insert(0, (value & 0x7f) | 0x80)
            value >>= 7
        return bytes(out)
    track = (b'\x00\xff\x51\x03\x07\xa1\x20' + b'\x00\x90\x3c\x40' + var(ticks) + b'\x80\x3c\x40'
             + b'\x00\xff\x2f\x00')
    return b'MThd'+struct.pack('>IHHH', 6, 0, 1, 480)+b'MTrk'+struct.pack('>I', len(track))+track


HANDMADE = {'ape': monkeys_audio, 'mpc': musepack, 'ofr': optimfrog, 'tak': tak, 'dsf': dsf, 'dff': dsdiff,
            'mid': midi}


def make_audio(kind, path, seconds=1.0, freq=440, channels=1, rate=44100):
    suffix, args = KINDS[kind]
    path = Path(path)
    if args is None:
        path.write_bytes(HANDMADE[kind](seconds))
    else:
        ffmpeg(path, args, seconds, freq, channels, rate)
    return path


# -- tags ---------------------------------------------------------------------------------------------------------
def _id3_frame(spec, images):
    from mutagen import id3
    name, *args = spec
    encoding = 3
    if name == 'TXXX':
        desc, text = args
        return id3.TXXX(encoding=encoding, desc=desc, text=text if isinstance(text, list) else [text])
    if name == 'COMM':
        lang, desc, text = args
        return id3.COMM(encoding=encoding, lang=lang, desc=desc, text=[text])
    if name == 'USLT':
        lang, desc, text = args
        return id3.USLT(encoding=encoding, lang=lang, desc=desc, text=text)
    if name == 'UFID':
        owner, data = args
        return id3.UFID(owner=owner, data=data.encode() if isinstance(data, str) else data)
    if name == 'POPM':
        email, rating, count = args
        return id3.POPM(email=email, rating=rating, count=count)
    if name in ('TMCL', 'TIPL', 'IPLS'):
        people = [list(p) for p in args[0]]
        return getattr(id3, name)(encoding=encoding, people=people)
    if name == 'APIC':
        kind, desc, picture = args
        return id3.APIC(encoding=encoding, mime=MIMES[Path(picture).suffix], type=kind, desc=desc,
                        data=images(picture))
    if name.startswith('W') and name != 'WXXX':
        return getattr(id3, name)(url=args[0])
    if name == 'WXXX':
        desc, url = args
        return id3.WXXX(encoding=encoding, desc=desc, url=url)
    text = args[0]
    return getattr(id3, name)(encoding=encoding, text=text if isinstance(text, list) else [text])


def id3v1(fields):
    """A raw ID3v1.1 tag (title, artist, album, year, comment, track, genre)."""
    text = lambda name, size: fields.get(name, '').encode('latin-1')[:size].ljust(size, b'\0')
    return (b'TAG'+text('title', 30)+text('artist', 30)+text('album', 30)+text('year', 4)+text('comment', 28)
            + b'\0'+bytes([fields.get('track', 0)])+bytes([fields.get('genre', 255)]))


def _write_id3(kind, path, spec, images):
    from mutagen import id3, aiff, dsf as m_dsf, dsdiff as m_dff, wave, trueaudio
    if spec.get('only_v1'):
        with open(path, 'ab') as stream:
            stream.write(id3v1(spec.get('v1fields', {})))
        return
    tags = id3.ID3()
    for frame in spec.get('frames', []):
        tags.add(_id3_frame(frame, images))
    version = spec.get('version', 4)
    if kind in ('mp3', 'mp2', 'tta'):
        tags.save(str(path), v2_version=version, v1=2 if spec.get('v1') else 0, padding=lambda info: 256)
    else:
        opener = {'aiff': aiff.AIFF, 'wav': wave.WAVE, 'dsf': m_dsf.DSF, 'dff': m_dff.DSDIFF}[kind]
        audio = opener(str(path))
        if audio.tags is None:
            audio.add_tags()
        for frame in tags.values():
            audio.tags.add(frame)
        audio.save(v2_version=version, padding=lambda info: 256)


def _write_vorbis(kind, path, spec, images):
    from mutagen import flac, oggvorbis, oggopus, oggspeex, oggflac
    opener = {'flac': flac.FLAC, 'ogg': oggvorbis.OggVorbis, 'opus': oggopus.OggOpus, 'spx': oggspeex.OggSpeex,
              'oggflac': oggflac.OggFLAC}[kind]
    audio = opener(str(path))
    if audio.tags is None:
        audio.add_tags()
    audio.tags.clear()
    for key, value in spec.get('fields', []):
        if value == '__FRONT_JPEG_BASE64__':
            value = base64.b64encode(images('front.jpg')).decode('ascii')
        audio.tags.append((key, value))
    for kind_, desc, picture in spec.get('pictures', []):
        pic = flac.Picture()
        pic.type, pic.mime, pic.desc, pic.data = kind_, MIMES[Path(picture).suffix], desc, images(picture)
        if isinstance(audio, flac.FLAC):
            audio.add_picture(pic)
        else:
            audio.tags.append(('METADATA_BLOCK_PICTURE', base64.b64encode(pic.write()).decode('ascii')))
    if isinstance(audio, flac.FLAC):
        if spec.get('empty_seektable'):
            # A SEEKTABLE block without seek points (as some encoders write it).
            table = flac.SeekTable(None)
            table.seekpoints = []
            audio.metadata_blocks = [b for b in audio.metadata_blocks if not isinstance(b, flac.SeekTable)]
            audio.metadata_blocks.insert(1, table)
            audio.seektable = table
        audio.save(padding=lambda info: 256)
    else:
        audio.save()


def _write_mp4(path, spec, images):
    from mutagen import mp4
    audio = mp4.MP4(str(path))
    if audio.tags is None:
        audio.add_tags()
    for key, value in spec.get('atoms', {}).items():
        values = value if isinstance(value, list) else [value]
        if key.startswith('----:'):
            values = [mp4.MP4FreeForm(v.encode('utf-8')) for v in values]
        elif key in ('trkn', 'disk'):
            values = [tuple(v) for v in values]
        elif key in ('cpil', 'pgap', 'pcst'):
            values = bool(values[0])
        elif key == 'covr':
            values = [mp4.MP4Cover(images(v), imageformat=mp4.MP4Cover.FORMAT_PNG if v.endswith('.png')
                                   else mp4.MP4Cover.FORMAT_JPEG) for v in values]
        audio.tags[key] = values
    audio.save()


def _write_asf(path, spec, images):
    from mutagen import asf
    audio = asf.ASF(str(path))
    for key, value in spec.get('attributes', {}).items():
        values = value if isinstance(value, list) else [value]
        if key == 'WM/Picture':
            out = []
            for kind_, desc, picture in values:
                data = images(picture)
                mime = MIMES[Path(picture).suffix]
                blob = (struct.pack('<bi', kind_, len(data)) + mime.encode('utf-16-le')+b'\0\0'
                        + desc.encode('utf-16-le')+b'\0\0'+data)
                out.append(asf.ASFByteArrayAttribute(blob))
            values = out
        elif isinstance(values[0], bool):
            values = [asf.ASFBoolAttribute(v) for v in values]
        elif isinstance(values[0], int):
            values = [asf.ASFDWordAttribute(v) for v in values]
        audio.tags[key] = values
    audio.save()


def _write_ape(path, spec, images):
    from mutagen import apev2
    tags = apev2.APEv2()
    for key, value in spec.get('items', {}).items():
        if isinstance(value, (tuple, list)) and len(value) == 3 and value[0] == 'binary':
            _, filename, picture = value
            tags[key] = apev2.APEValue(filename.encode('utf-8')+b'\0'+images(picture), apev2.BINARY)
        else:
            tags[key] = value if isinstance(value, list) else str(value)
    tags.save(str(path))


def _riff_info(path, fields):
    """Append a RIFF LIST/INFO chunk to a WAVE file (mutagen does not write RIFF INFO)."""
    payload = b'INFO'
    for key, value in fields:
        text = value.encode('cp1252')+b'\0'
        if len(text) % 2:
            text += b'\0'
        payload += key.encode('ascii')+struct.pack('<I', len(value.encode('cp1252'))+1)+text
    data = bytearray(Path(path).read_bytes())
    data += b'LIST'+struct.pack('<I', len(payload))+payload
    struct.pack_into('<I', data, 4, len(data)-8)
    Path(path).write_bytes(bytes(data))


def write_tags(kind, path, spec, images=image):
    """Write the raw tag layout of one fixture; spec keys depend on the tag family."""
    if not spec:
        return
    if 'riff' in spec:
        _riff_info(path, spec['riff'])
    if 'id3' in spec:
        _write_id3(kind if kind in ('aiff', 'wav', 'dsf', 'dff') else 'mp3', path, spec['id3'], images)
    if 'vorbis' in spec:
        _write_vorbis(kind, path, spec['vorbis'], images)
    if 'mp4' in spec:
        _write_mp4(path, spec['mp4'], images)
    if 'asf' in spec:
        _write_asf(path, spec['asf'], images)
    if 'ape' in spec:
        _write_ape(path, spec['ape'], images)


# -- documents ------------------------------------------------------------------------------------------------------
def toml_string(value):
    return json.dumps(value, ensure_ascii=False)


def toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return toml_string(value)
    if isinstance(value, (list, tuple)):
        return '[' + ', '.join(toml_value(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{' + ', '.join(f'{toml_string(k)} = {toml_value(v)}' for k, v in value.items()) + '}'
    raise TypeError(f'no TOML form for {value!r}')


def literal(text):
    if "'''" in text:
        raise ValueError('a literal TOML string cannot contain three quotes')
    return "'''" + text + "'''"


def profile(title, settings=None, naming=None, tagging=(), enable_tagger_scripts=None, extra_profile=None,
            raw_settings=None):
    """A Picard profile document (TOML) as the product exports it."""
    lines = ['[profile]', f'title = {toml_string(title)}', 'format_version = 1']
    for key, value in (extra_profile or {}).items():
        lines.append(f'{key} = {toml_value(value)}')
    if settings or raw_settings:
        lines += ['', '[settings]']
        for key, value in (settings or {}).items():
            lines.append(f'{key} = {toml_value(value)}')
        lines += list(raw_settings or [])
    if naming or tagging or enable_tagger_scripts is not None:
        lines += ['', '[scripts]']
        if enable_tagger_scripts is not None:
            lines.append(f'enable_tagger_scripts = {toml_value(enable_tagger_scripts)}')
    if naming:
        lines += ['', '[scripts.naming]']
        for key, value in naming.items():
            lines.append(f'{key} = {literal(value) if key == "script" else toml_value(value)}')
    for script in tagging:
        lines += ['', '[[scripts.tagging]]']
        for key, value in script.items():
            lines.append(f'{key} = {literal(value) if key == "script" else toml_value(value)}')
    return ('\n'.join(lines)+'\n').encode('utf-8')


def session(items, options=None):
    """A Picard session document (.mbps.gz): gzip-compressed YAML as the product saves it."""
    import yaml
    value = {'version': 1,
             'options': dict(options or {'rename_files': False, 'move_files': False, 'enable_tag_saving': True}),
             'items': items, 'album_track_overrides': {}, 'album_overrides': {}, 'unmatched_albums': [],
             'expanded_albums': [], 'mb_cache': {}}
    text = yaml.dump(value, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return gzip.compress(text.encode('utf-8'), mtime=0)


# -- fixture store --------------------------------------------------------------------------------------------------
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]


def store():
    """The verifier-private fixture directory of this run (keyed by this module's source)."""
    source = Path(__file__).read_bytes()
    base = Path(os.environ.get('TMPDIR', '/tmp'))/('picard-fixtures-'+hashlib.sha256(source).hexdigest()[:16])
    base.mkdir(parents=True, exist_ok=True)
    return base


def audio_file(kind, tags=None, seconds=1.0, freq=440, channels=1, rate=44100):
    """Bytes of one tagged audio fixture (cached by its specification)."""
    spec = {'kind': kind, 'tags': tags or {}, 'seconds': seconds, 'freq': freq, 'channels': channels, 'rate': rate}
    path = store()/(digest(spec)+KINDS[kind][0])
    if not path.is_file():
        work = path.with_name(path.stem+'.part'+path.suffix)
        make_audio(kind, work, seconds, freq, channels, rate)
        write_tags(kind, work, tags or {})
        work.replace(path)
    return path.read_bytes()
