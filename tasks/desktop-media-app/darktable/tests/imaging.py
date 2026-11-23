'''Image codecs and projections used by the verifier (pure Python and NumPy).

PNG (all colour types, 1-16 bit, Adam7), PNM (P1-P6, 8 and 16 bit), PFM and a small PNG writer for fixtures.
Other containers are decoded through ImageMagick of the verifier image into 16-bit PNG first. A projection keeps
what an image shows at a scale an independent implementation can reproduce: its size and channels, the mean of each
channel in a grid of cells, and robust per-channel statistics.
'''
from __future__ import annotations

import struct
import zlib

import numpy as np

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class ImageError(AssertionError):
    '''Bytes that are not a valid image of the expected kind.'''


# -- PNG ----------------------------------------------------------------------------------------------------------
def png_chunks(data):
    if data[:8] != PNG_SIGNATURE:
        raise ImageError('not a PNG file')
    pos, out = 8, []
    while pos + 8 <= len(data):
        length, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise ImageError('truncated PNG chunk')
        out.append((kind.decode('latin-1'), body))
        pos += 12 + length
        if kind == b'IEND':
            break
    return out


def _unfilter(raw, width, height, bpp, rowbytes):
    out = np.zeros((height, rowbytes), dtype=np.uint8)
    prior = np.zeros(rowbytes, dtype=np.int32)
    pos = 0
    for y in range(height):
        if pos + 1 + rowbytes > len(raw):
            raise ImageError('truncated PNG image data')
        kind = raw[pos]
        line = np.frombuffer(raw, dtype=np.uint8, count=rowbytes, offset=pos + 1).astype(np.int32)
        pos += 1 + rowbytes
        if kind == 0:
            row = line
        elif kind == 1:
            row = line.copy()
            for x in range(bpp, rowbytes):
                row[x] = (row[x] + row[x - bpp]) & 255
        elif kind == 2:
            row = (line + prior) & 255
        elif kind == 3:
            row = line.copy()
            for x in range(rowbytes):
                left = row[x - bpp] if x >= bpp else 0
                row[x] = (row[x] + ((left + prior[x]) >> 1)) & 255
        elif kind == 4:
            row = line.copy()
            for x in range(rowbytes):
                a = row[x - bpp] if x >= bpp else 0
                b = prior[x]
                c = prior[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[x] = (row[x] + pred) & 255
        else:
            raise ImageError('unknown PNG filter type %d' % kind)
        out[y] = row
        prior = row
    return out, pos


def _samples(rows, width, depth, channels):
    if depth == 16:
        return rows.view('>u2').reshape(rows.shape[0], width * channels)[:, :width * channels].astype(np.float64) / 65535.0
    if depth == 8:
        return rows[:, :width * channels].astype(np.float64) / 255.0
    bits = np.unpackbits(rows, axis=1)
    per = width * channels
    values = np.zeros((rows.shape[0], per), dtype=np.int32)
    for i in range(depth):
        values = (values << 1) | bits[:, i:per * depth:depth][:, :per]
    return values.astype(np.float64) / (2 ** depth - 1)


def decode_png(data):
    '''PNG bytes to (array HxWxC float64 in [0,1] before palette expansion, info dict).'''
    chunks = png_chunks(data)
    if not chunks or chunks[0][0] != 'IHDR':
        raise ImageError('PNG without IHDR')
    width, height, depth, ctype, _comp, _filt, interlace = struct.unpack('>IIBBBBB', chunks[0][1])
    if ctype not in CHANNELS or depth not in (1, 2, 4, 8, 16) or width == 0 or height == 0:
        raise ImageError('unsupported PNG header')
    channels = CHANNELS[ctype]
    palette = next((body for kind, body in chunks if kind == 'PLTE'), None)
    try:
        raw = zlib.decompress(b''.join(body for kind, body in chunks if kind == 'IDAT'))
    except zlib.error:
        raise ImageError('corrupt PNG image data') from None
    bitspp = depth * channels
    bpp = max(1, bitspp // 8)
    if not interlace:
        rows, _ = _unfilter(raw, width, height, bpp, (width * bitspp + 7) // 8)
        pixels = _samples(rows, width, depth, channels).reshape(height, width, channels)
    else:
        pixels = np.zeros((height, width, channels))
        pos = 0
        for x0, y0, dx, dy in ADAM7:
            w, h = (width - x0 + dx - 1) // dx, (height - y0 + dy - 1) // dy
            if w <= 0 or h <= 0:
                continue
            rows, used = _unfilter(raw[pos:], w, h, bpp, (w * bitspp + 7) // 8)
            pos += used
            pixels[y0::dy, x0::dx] = _samples(rows, w, depth, channels).reshape(h, w, channels)
    if ctype == 3:
        if palette is None:
            raise ImageError('palette PNG without PLTE')
        table = np.frombuffer(palette, dtype=np.uint8).reshape(-1, 3).astype(np.float64) / 255.0
        index = np.rint(pixels[..., 0] * (2 ** depth - 1)).astype(int)
        if index.max() >= len(table):
            raise ImageError('palette index out of range')
        pixels = table[index]
    texts = {}
    for kind, body in chunks:
        if kind == 'tEXt' and b'\0' in body:
            key, value = body.split(b'\0', 1)
            texts[key.decode('latin-1')] = value.decode('latin-1')
        elif kind == 'iTXt' and b'\0' in body:
            key, rest = body.split(b'\0', 1)
            if len(rest) >= 2:
                compressed, rest = rest[0], rest[2:]
                _lang, _, rest = rest.partition(b'\0')
                _tkey, _, value = rest.partition(b'\0')
                try:
                    value = zlib.decompress(value) if compressed else value
                except zlib.error:
                    value = b''
                texts[key.decode('latin-1')] = value.decode('utf-8', 'replace')
        elif kind == 'zTXt' and b'\0' in body:
            key, value = body.split(b'\0', 1)
            try:
                texts[key.decode('latin-1')] = zlib.decompress(value[1:]).decode('latin-1')
            except zlib.error:
                pass
    info = {'width': width, 'height': height, 'bit_depth': depth, 'color_type': ctype, 'interlace': interlace,
            'chunks': sorted({kind for kind, _ in chunks}), 'texts': texts,
            'icc': next((body for kind, body in chunks if kind == 'iCCP'), None)}
    return pixels, info


def encode_png(pixels, depth=16, texts=None, icc=None):
    '''A float array HxWxC in [0,1] (C = 1, 2, 3 or 4) to PNG bytes, filter 0, optional tEXt and iCCP chunks.'''
    pixels = np.asarray(pixels, dtype=np.float64)
    if pixels.ndim == 2:
        pixels = pixels[..., None]
    height, width, channels = pixels.shape
    ctype = {1: 0, 2: 4, 3: 2, 4: 6}[channels]
    scale = 65535 if depth == 16 else 255
    values = np.clip(np.rint(pixels * scale), 0, scale).astype('>u2' if depth == 16 else np.uint8)
    rows = b''.join(b'\0' + values[y].tobytes() for y in range(height))

    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    out = PNG_SIGNATURE + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, ctype, 0, 0, 0))
    if icc is not None:
        out += chunk(b'iCCP', b'icc\0\0' + zlib.compress(icc, 9))
    for key, value in (texts or {}).items():
        out += chunk(b'tEXt', key.encode('latin-1') + b'\0' + value.encode('latin-1'))
    return out + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b'')


# -- PNM and PFM --------------------------------------------------------------------------------------------------
def _tokens(data, count, pos):
    out = []
    while len(out) < count:
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b'#':
            while pos < len(data) and data[pos:pos + 1] not in (b'\n', b'\r'):
                pos += 1
            continue
        start = pos
        while pos < len(data) and not data[pos:pos + 1].isspace() and data[pos:pos + 1] != b'#':
            pos += 1
        if start == pos:
            raise ImageError('truncated PNM header')
        out.append(data[start:pos])
    return out, pos + 1


def decode_pnm(data):
    magic = data[:2]
    if magic not in (b'P5', b'P6', b'P2', b'P3'):
        raise ImageError('not a binary or ASCII PGM/PPM file')
    channels = 3 if magic in (b'P6', b'P3') else 1
    (width, height, maxval), pos = _tokens(data, 3, 2)
    width, height, maxval = int(width), int(height), int(maxval)
    if not (0 < maxval < 65536) or width <= 0 or height <= 0:
        raise ImageError('invalid PNM header')
    count = width * height * channels
    if magic in (b'P2', b'P3'):
        values, _ = _tokens(data, count, pos - 1)
        array = np.array([int(v) for v in values], dtype=np.float64)
    else:
        dtype = '>u2' if maxval > 255 else np.uint8
        size = count * (2 if maxval > 255 else 1)
        if len(data) - pos < size:
            raise ImageError('truncated PNM image data')
        array = np.frombuffer(data, dtype=dtype, count=count, offset=pos).astype(np.float64)
    return array.reshape(height, width, channels) / maxval, {'width': width, 'height': height, 'maxval': maxval,
                                                              'magic': magic.decode()}


def decode_pfm(data):
    magic = data[:2]
    if magic not in (b'PF', b'Pf'):
        raise ImageError('not a PFM file')
    channels = 3 if magic == b'PF' else 1
    (width, height, scale), pos = _tokens(data, 3, 2)
    width, height, scale = int(width), int(height), float(scale)
    if width <= 0 or height <= 0 or scale == 0:
        raise ImageError('invalid PFM header')
    count = width * height * channels
    if len(data) - pos < count * 4:
        raise ImageError('truncated PFM image data')
    array = np.frombuffer(data, dtype='<f4' if scale < 0 else '>f4', count=count, offset=pos).astype(np.float64)
    # PFM stores rows bottom to top.
    return array.reshape(height, width, channels)[::-1], {'width': width, 'height': height, 'endian': 'little' if scale < 0 else 'big'}


def encode_pfm(pixels):
    pixels = np.asarray(pixels, dtype='<f4')
    height, width = pixels.shape[:2]
    magic = 'PF' if pixels.ndim == 3 and pixels.shape[2] == 3 else 'Pf'
    return ('%s\n%d %d\n-1.0\n' % (magic, width, height)).encode() + pixels[::-1].tobytes()


# -- projections --------------------------------------------------------------------------------------------------
GRID = (6, 8)


def projection(pixels, grid=GRID):
    '''Size, channels, per-channel means of a rows x columns grid of cells, and robust statistics.'''
    pixels = np.asarray(pixels, dtype=np.float64)
    height, width, channels = pixels.shape
    rows, cols = grid
    ys = np.linspace(0, height, rows + 1).astype(int)
    xs = np.linspace(0, width, cols + 1).astype(int)
    cells = []
    for i in range(rows):
        for j in range(cols):
            block = pixels[ys[i]:max(ys[i + 1], ys[i] + 1), xs[j]:max(xs[j + 1], xs[j] + 1)]
            cells.append([round(float(v), 5) for v in block.reshape(-1, channels).mean(axis=0)])
    flat = pixels.reshape(-1, channels)
    stats = {'mean': [round(float(v), 5) for v in flat.mean(axis=0)],
             'std': [round(float(v), 5) for v in flat.std(axis=0)],
             'p02': [round(float(v), 5) for v in np.percentile(flat, 2, axis=0)],
             'p98': [round(float(v), 5) for v in np.percentile(flat, 98, axis=0)]}
    detail = np.abs(np.diff(pixels, axis=1)).mean() + np.abs(np.diff(pixels, axis=0)).mean() if width > 1 and height > 1 else 0.0
    return {'width': width, 'height': height, 'channels': channels, 'cells': cells, 'stats': stats,
            'detail': round(float(detail), 5)}


def distance(a, b):
    '''Largest absolute difference between two projections of the same shape (inf when the shapes differ).'''
    if (a['width'], a['height'], a['channels']) != (b['width'], b['height'], b['channels']):
        return float('inf')
    if len(a['cells'])!=len(b['cells']) or set(a['stats'])!=set(b['stats']):
        return float('inf')
    for left,right in [*zip(a['cells'],b['cells']),*((a['stats'][k],b['stats'][k]) for k in b['stats'])]:
        if len(left)!=len(right) or not np.isfinite(left).all():
            return float('inf')
    if not np.isfinite(a['detail']):return float('inf')
    worst = abs(a['detail'] - b['detail'])
    for left, right in zip(a['cells'], b['cells']):
        worst = max(worst, max(abs(x - y) for x, y in zip(left, right)))
    for key in a['stats']:
        worst = max(worst, max(abs(x - y) for x, y in zip(a['stats'][key], b['stats'][key])))
    return worst
