"""The verifier's own reading of tagged audio files (mutagen), as normalized dumps for program checks.

A dump lists every tag field a file carries, in a form that does not depend on how a writer laid the tag out:
ID3 frames by their identifying key (frame id plus description, language or owner) with their text values,
encodings only where a check asks for them; Vorbis comments by upper-cased key; MP4 atoms (free-form atoms
decoded as text); ASF attributes; APEv2 items; RIFF INFO chunks of WAVE files. Images are reduced to type, MIME
type, description and the SHA-256 and pixel size of the picture data. Padding, frame order and the order of
distinct keys are ignored; the order of values within one field is kept.
"""
import base64
import hashlib
import io
import struct

FAMILY = {'.mp3': 'id3', '.mp2': 'id3', '.tta': 'id3', '.aiff': 'id3', '.aif': 'id3', '.wav': 'id3', '.dsf': 'id3',
          '.dff': 'id3', '.flac': 'vorbis', '.ogg': 'vorbis', '.opus': 'vorbis', '.spx': 'vorbis', '.oga': 'vorbis',
          '.m4a': 'mp4', '.mp4': 'mp4', '.wma': 'asf', '.ape': 'ape', '.mpc': 'ape', '.wv': 'ape', '.ofr': 'ape',
          '.tak': 'ape', '.aac': 'ape', '.ac3': 'ape', '.mid': 'none'}
ENCODINGS = {0: 'latin-1', 1: 'utf-16', 2: 'utf-16be', 3: 'utf-8'}


def picture_summary(data, mime='', kind=None, desc=''):
    size = image_size(data)
    value = {'sha256': hashlib.sha256(data).hexdigest()[:16], 'mime': str(mime), 'size': size}
    if kind is not None:
        value['type'] = int(kind)
    if desc:
        value['desc'] = str(desc)
    return value


def image_size(data):
    """Pixel size of a JPEG or PNG picture, or None."""
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        return list(struct.unpack('>II', data[16:24]))
    if data[:2] == b'\xff\xd8':
        index = 2
        while index+9 < len(data):
            if data[index] != 0xff:
                index += 1
                continue
            marker = data[index+1]
            if marker in (0xc0, 0xc1, 0xc2):
                height, width = struct.unpack('>HH', data[index+5:index+9])
                return [width, height]
            length = struct.unpack('>H', data[index+2:index+4])[0]
            index += 2+length
    return None


def _id3_frames(tags, encodings=False):
    fields = {}
    for frame in tags.values():
        fid = frame.FrameID
        key = frame.HashKey
        if fid == 'APIC':
            value = picture_summary(frame.data, frame.mime, frame.type, frame.desc)
            fields.setdefault('APIC', []).append(value)
            continue
        if fid in ('TMCL', 'TIPL', 'IPLS'):
            values = [f'{role}={name}' for role, name in frame.people]
        elif fid == 'UFID':
            values = [frame.data.decode('utf-8', 'replace')]
            key = 'UFID:'+frame.owner
        elif fid == 'POPM':
            values = [f'rating={frame.rating} count={getattr(frame, "count", 0)}']
            key = 'POPM:'+frame.email
        elif fid in ('COMM', 'USLT'):
            text = frame.text if isinstance(frame.text, str) else '\n'.join(str(t) for t in frame.text)
            values = [text]
            key = f'{fid}:{frame.desc}:{frame.lang}'
        elif fid == 'TXXX':
            values = [str(t) for t in frame.text]
            key = 'TXXX:'+frame.desc
        elif fid.startswith('W'):
            values = [frame.url]
            if fid == 'WXXX':
                key = 'WXXX:'+frame.desc
        elif hasattr(frame, 'text'):
            values = [str(t) for t in frame.text]
        else:
            values = [repr(frame)]
        if encodings and hasattr(frame, 'encoding'):
            values = values+[f'<encoding {ENCODINGS.get(int(frame.encoding), int(frame.encoding))}>']
        fields.setdefault(key, []).extend(values)
    return fields


def _id3_v1(data):
    """The ID3v1 tag at the end of the file as its fields, or None."""
    if len(data) < 128 or data[-128:-125] != b'TAG':
        return None
    tag = data[-128:]
    text = lambda b: b.split(b'\0', 1)[0].decode('latin-1').rstrip()
    value = {'title': text(tag[3:33]), 'artist': text(tag[33:63]), 'album': text(tag[63:93]),
             'year': text(tag[93:97]), 'genre': tag[127]}
    if tag[125] == 0 and tag[126] != 0:
        value['comment'], value['track'] = text(tag[97:125]), tag[126]
    else:
        value['comment'] = text(tag[97:127])
    return value


def _riff_info(data):
    """RIFF LIST/INFO entries of a WAVE file."""
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        return None
    found, index = {}, 12
    while index+8 <= len(data):
        cid, size = data[index:index+4], struct.unpack('<I', data[index+4:index+8])[0]
        body = data[index+8:index+8+size]
        if cid == b'LIST' and body[:4] == b'INFO':
            inner = 4
            while inner+8 <= len(body):
                key, length = body[inner:inner+4], struct.unpack('<I', body[inner+4:inner+8])[0]
                found[key.decode('latin-1')] = body[inner+8:inner+8+length].split(b'\0', 1)[0].decode('cp1252',
                                                                                                    'replace')
                inner += 8+length+(length % 2)
        index += 8+size+(size % 2)
    return found or None


def dump(data, suffix, *, encodings=False, seektable=False):
    """Normalized tag dump of one file's bytes; seektable adds the number of seek points of a FLAC file (None
    without a SEEKTABLE block)."""
    import mutagen
    from mutagen import apev2, id3
    suffix = suffix.lower()
    family = FAMILY.get(suffix, 'none')
    handle = io.BytesIO(data)
    result = {'family': family, 'fields': {}}
    if family == 'id3':
        if suffix in ('.mp3', '.mp2', '.tta'):
            # The frames exactly as written: no ID3v2.3 to 2.4 translation, no merged ID3v1 fields.
            tags = id3.ID3()
            try:
                tags.load(handle, translate=False, load_v1=False)
            except id3.ID3NoHeaderError:
                tags = None
            result['id3v1'] = _id3_v1(data)
            try:
                result['ape'] = sorted(apev2.APEv2(io.BytesIO(data)).keys())
            except Exception:
                result['ape'] = None
        else:
            # AIFF, WAVE, DSF and DSDIFF carry one ID3v2 tag in a chunk (or at the metadata offset): read it as
            # written, without version translation.
            tags = None
            for marker in (b'ID3\x04\x00', b'ID3\x03\x00'):
                offset = data.find(marker)
                if offset >= 0:
                    tags = id3.ID3()
                    tags.load(io.BytesIO(data[offset:]), translate=False, load_v1=False)
                    break
            if suffix == '.wav':
                result['riff_info'] = _riff_info(data)
        if tags is not None:
            result['id3_version'] = '.'.join(str(v) for v in tags.version[:2])
            result['fields'] = _id3_frames(tags, encodings)
    elif family == 'vorbis':
        audio = mutagen.File(handle)
        if audio is not None and audio.tags is not None:
            fields = {}
            for key, value in audio.tags:
                key = key.upper()
                if key == 'METADATA_BLOCK_PICTURE':
                    from mutagen.flac import Picture
                    try:
                        picture = Picture(base64.b64decode(value))
                        fields.setdefault('PICTURE', []).append(picture_summary(picture.data, picture.mime,
                                                                                picture.type, picture.desc))
                    except Exception:
                        fields.setdefault(key, []).append('<invalid picture>')
                    continue
                fields.setdefault(key, []).append(value)
            for picture in getattr(audio, 'pictures', []):
                fields.setdefault('PICTURE', []).append(picture_summary(picture.data, picture.mime, picture.type,
                                                                        picture.desc))
            result['fields'] = fields
        if suffix == '.flac':
            try:
                result['id3'] = sorted(id3.ID3(io.BytesIO(data)).keys())
            except Exception:
                result['id3'] = None
            if seektable:
                table = getattr(audio, 'seektable', None) if audio is not None else None
                result['seektable'] = None if table is None else len(table.seekpoints)
    elif family == 'mp4':
        audio = mutagen.File(handle)
        fields = {}
        for key, values in (audio.tags or {}).items():
            out = []
            for value in values if isinstance(values, list) else [values]:
                if key == 'covr':
                    out.append(picture_summary(bytes(value), {13: 'image/jpeg', 14: 'image/png'}.get(
                        value.imageformat, str(value.imageformat))))
                elif key in ('trkn', 'disk'):
                    out.append('/'.join(str(v) for v in value))
                elif isinstance(value, bytes):
                    out.append(value.decode('utf-8', 'replace'))
                elif isinstance(value, bool):
                    out.append(str(value).lower())
                else:
                    out.append(str(value))
            fields[key] = out
        result['fields'] = fields
    elif family == 'asf':
        audio = mutagen.File(handle)
        fields = {}
        for key, values in (audio.tags or {}).items():
            out = []
            for value in values:
                if key == 'WM/Picture':
                    raw = bytes(value.value)
                    kind, size = struct.unpack_from('<bi', raw)
                    rest = raw[5:]
                    mime, rest = rest.split(b'\0\0', 1) if b'\0\0' in rest else (rest, b'')
                    out.append({'type': kind, 'sha256': hashlib.sha256(raw[-size:]).hexdigest()[:16],
                                'size': image_size(raw[-size:])})
                else:
                    out.append(str(value.value) if not isinstance(value.value, bytes) else
                               value.value.decode('utf-8', 'replace'))
            fields[key] = out
        result['fields'] = fields
    elif family == 'ape':
        try:
            tags = apev2.APEv2(handle)
        except Exception:
            tags = None
        fields = {}
        for key, value in (tags or {}).items():
            if value.kind == apev2.BINARY:
                raw = bytes(value.value)
                name, _, picture = raw.partition(b'\0')
                fields[key] = [{'filename': name.decode('utf-8', 'replace'), **picture_summary(picture)}]
            else:
                fields[key] = list(value)
        result['fields'] = fields
    return result


def dump_bytes(data, name, *, encodings=False, seektable=False):
    suffix = '.'+name.rsplit('.', 1)[-1] if '.' in name else ''
    try:
        return dump(data, suffix, encodings=encodings, seektable=seektable)
    except Exception as exc:
        raise AssertionError(f'{name} cannot be read as {suffix} audio: {type(exc).__name__}: {exc}'[:300]) from None
