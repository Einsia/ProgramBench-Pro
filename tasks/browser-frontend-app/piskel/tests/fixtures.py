"""Sprites that the program episodes load, and the pure-Python codecs used to build and read .piskel documents.

A sprite here is {'name', 'fps', 'w', 'h', 'layers': [{'name', 'opacity', 'frames': [rows]}]} where a frame is a
list of h rows of w (r, g, b, a) tuples. Fixtures are built from small pixel maps so each one is easy to review.
"""
import base64
import json
import struct
import zlib
import io
import sys

T = (0, 0, 0, 0)
PALETTE = {
    '.': T,
    'k': (0, 0, 0, 255),
    'w': (255, 255, 255, 255),
    'r': (255, 0, 0, 255),
    'g': (0, 255, 0, 255),
    'b': (0, 0, 255, 255),
    'y': (255, 255, 0, 255),
    'm': (255, 0, 255, 255),
    'c': (0, 255, 255, 255),
    'o': (255, 128, 0, 255),
    'p': (128, 0, 128, 255),
    'n': (136, 68, 34, 255),
    's': (128, 128, 128, 255),
    'h': (255, 0, 0, 128),
}


# -- PNG ------------------------------------------------------------------------------------------------
def png_bytes(w, h, rows):
    raw = b''.join(b'\x00' + bytes(v for px in row for v in px) for row in rows)

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def png_rgba(data):
    """Decode a non-interlaced 8-bit PNG (colour types 0, 2, 3, 4, 6) to (w, h, rows of RGBA tuples)."""
    # Independent candidates can emit any valid PNG encoding, including 1-bit
    # palettes, interlacing and colour-key transparency. Pillow is verifier-only.
    sys.path.insert(0, '/opt/verifier-lib')
    try:
        from PIL import Image
    except ImportError:
        pass
    else:
        image = Image.open(io.BytesIO(data))
        if image.format != 'PNG':
            raise ValueError('not a PNG file')
        rgba = image.convert('RGBA')
        w, h = rgba.size
        px = list(rgba.getdata())
        return w, h, [px[y*w:(y+1)*w] for y in range(h)]
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG file')
    pos, idat, plte, trns = 8, b'', None, None
    w = h = depth = ctype = None
    while pos < len(data):
        n = struct.unpack('>I', data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
            if depth != 8 or interlace:
                raise ValueError('unsupported PNG layout')
        elif kind == b'PLTE':
            plte = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif kind == b'tRNS':
            trns = body
        elif kind == b'IDAT':
            idat += body
        elif kind == b'IEND':
            break
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * channels
    prev = bytearray(stride)
    rows = []
    i = 0
    for _ in range(h):
        ftype = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if ftype == 1:
                line[x] = (line[x] + a) & 255
            elif ftype == 2:
                line[x] = (line[x] + b) & 255
            elif ftype == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif ftype == 4:
                line[x] = (line[x] + _paeth(a, b, c)) & 255
        prev = line
        row = []
        for x in range(w):
            px = line[x * channels:(x + 1) * channels]
            if ctype == 6:
                row.append(tuple(px))
            elif ctype == 2:
                row.append((px[0], px[1], px[2], 255))
            elif ctype == 0:
                row.append((px[0], px[0], px[0], 255))
            elif ctype == 4:
                row.append((px[0], px[0], px[0], px[1]))
            else:
                alpha = trns[px[0]] if trns is not None and px[0] < len(trns) else 255
                row.append(tuple(plte[px[0]]) + (alpha,))
        rows.append(row)
    return w, h, rows


# -- .piskel documents (model version 2: per layer, chunks of frames laid out left to right) ------------
def blank(w, h):
    return [[T] * w for _ in range(h)]


def grid(text, w=None, h=None):
    """Frame from a pixel map: one string per row, one PALETTE letter per pixel; padded with transparency."""
    lines = [ln.strip() for ln in text.strip().splitlines()]
    w = w or max(len(ln) for ln in lines)
    h = h or len(lines)
    rows = blank(w, h)
    for y, ln in enumerate(lines[:h]):
        for x, ch in enumerate(ln[:w]):
            rows[y][x] = PALETTE[ch]
    return rows


def layer(name, frames, opacity=1):
    return {'name': name, 'opacity': opacity, 'frames': frames}


def sprite(name, layers, fps=12, hidden=()):
    w, h = len(layers[0]['frames'][0][0]), len(layers[0]['frames'][0])
    return {'name': name, 'fps': fps, 'w': w, 'h': h, 'layers': layers, 'hidden': list(hidden)}


def encode(sp, description=''):
    """Serialize a sprite exactly as Piskel 0.15.0 lays out its own files (one chunk per layer)."""
    w, h = sp['w'], sp['h']
    out = []
    for ly in sp['layers']:
        n = len(ly['frames'])
        strip = [[px for f in ly['frames'] for px in f[y]] for y in range(h)]
        b64 = 'data:image/png;base64,' + base64.b64encode(png_bytes(w * n, h, strip)).decode()
        chunk = {'layout': [[i] for i in range(n)], 'base64PNG': b64}
        out.append(json.dumps({'name': ly['name'], 'opacity': ly['opacity'], 'frameCount': n, 'chunks': [chunk]}))
    return json.dumps({'modelVersion': 2, 'piskel': {
        'name': sp['name'], 'description': description, 'fps': sp['fps'], 'height': h, 'width': w,
        'layers': out, 'hiddenFrames': list(sp.get('hidden', []))}})


def decode(text):
    """Read a .piskel document (model version 2) into the sprite shape above, plus its description."""
    doc = json.loads(text)
    if doc.get('modelVersion') != 2:
        raise ValueError(f"unsupported modelVersion {doc.get('modelVersion')!r}")
    p = doc['piskel']
    w, h = int(p['width']), int(p['height'])
    if w < 1 or h < 1:
        raise ValueError('document dimensions must be positive')
    layers = []
    for raw in p['layers']:
        ly = json.loads(raw) if isinstance(raw, str) else raw
        count = int(ly['frameCount'])
        if count < 1:
            raise ValueError('a layer must contain frames')
        frames = [None] * count
        chunks = ly.get('chunks')
        if chunks is None and 'base64PNG' in ly:
            chunks = [{'base64PNG': ly['base64PNG'], 'layout': [[i] for i in range(count)]}]
        if not isinstance(chunks, list) or not chunks:
            raise ValueError('missing frame chunks')
        for chunk in chunks:
            data = chunk['base64PNG'].split(',', 1)[1]
            cw, ch, rows = png_rgba(base64.b64decode(data))
            layout = chunk['layout']
            if not isinstance(layout, list) or not layout or not all(isinstance(c, list) and c for c in layout):
                raise ValueError('invalid chunk layout')
            if any(len(c) != len(layout[0]) for c in layout):
                raise ValueError('ragged chunk layout')
            if (cw, ch) != (len(layout) * w, len(layout[0]) * h):
                raise ValueError('chunk dimensions do not match its frame layout')
            for col, cells in enumerate(layout):
                for row, index in enumerate(cells):
                    if index is None:
                        continue
                    if type(index) is not int or not 0 <= index < count:
                        raise ValueError('frame index outside the declared frame count')
                    if frames[index] is not None:
                        raise ValueError('duplicate frame index')
                    frames[index] = [rows[row * h + y][col * w:(col + 1) * w] for y in range(h)]
        if any(f is None for f in frames):
            raise ValueError(f"layer {ly.get('name')!r} misses frames")
        layers.append({'name': ly['name'], 'opacity': ly.get('opacity', 1), 'frames': frames})
    return {'name': p['name'], 'description': p.get('description', ''), 'fps': p['fps'], 'w': w, 'h': h,
            'layers': layers, 'hidden': list(p.get('hiddenFrames') or [])}


# -- named fixtures ---------------------------------------------------------------------------------------
def one(name, text, w=None, h=None, fps=12):
    return sprite(name, [layer('Layer 1', [grid(text, w, h)])], fps)


BLANK = one('blank', '........', 8, 8)

# Distinct colours in distinct places: fills, swaps, picks, transforms and exports all have something to move.
REGIONS = one('regions', '''
    rrrr....
    rrrr....
    rrrr.bb.
    rrrr.bb.
    ....gggg
    .kk.g..g
    .kk.g..g
    ....gggg
''')

# Asymmetric in both axes so flips, rotations and moves are distinguishable from each other.
ARROW = one('arrow', '''
    rr......
    rrr.....
    r.rr....
    r..rr...
    r...b...
    ........
    .......g
    ......gg
''')

# Non-square: rotation and resize must keep the 6x4 canvas.
WIDE = one('wide', '''
    rrr...
    r.bb..
    r..bb.
    ggg..y
''')

ANIM = sprite('anim', [layer('Layer 1', [
    grid('r.......\n' + '........\n' * 7, 8, 8),
    grid('.g......\n.g......\n' + '........\n' * 6, 8, 8),
    grid('..b.....\n..b.....\n..b.....\n' + '........\n' * 5, 8, 8),
])], fps=6)

LAYERS = sprite('layers', [
    layer('back', [grid('''
        bbbbbbbb
        b......b
        b......b
        b......b
        b......b
        b......b
        b......b
        bbbbbbbb''')]),
    layer('front', [grid('''
        ........
        ........
        ..rr....
        ..rr....
        ....gg..
        ....gg..
        ........
        ........''')], opacity=0.5),
])

# Two layers by three frames, every cell different: frame/layer operations must keep the right cells together.
GRID = sprite('grid', [
    layer('base', [grid('r.......\n' + '........\n' * 7, 8, 8), grid('g.......\n' + '........\n' * 7, 8, 8),
                   grid('b.......\n' + '........\n' * 7, 8, 8)]),
    layer('top', [grid('.......y\n' + '........\n' * 7, 8, 8), grid('.......m\n' + '........\n' * 7, 8, 8),
                  grid('.......c\n' + '........\n' * 7, 8, 8)]),
], fps=8)

# Large central shapes remain visible under timeline frame-number badges.
CLONE_VISIBLE = sprite('clone-visible', [layer('base', [
    grid('........\n..rrr...\n..rrr...\n..rrr...\n........\n........\n........\n........'),
    grid('........\n........\n........\n...ggg..\n...ggg..\n...ggg..\n........\n........'),
    grid('........\n........\n..bbb...\n..b.b...\n..bbb...\n........\n........\n........'),
]), layer('top', [
    grid('........\n........\n........\n........\n........\n........\n......yy\n......yy'),
    grid('........\n........\n........\n........\n........\n........\n......mm\n.......m'),
    grid('........\n........\n........\n........\n........\n........\n......c.\n......cc'),
])], fps=8)
PREVIEW = sprite('preview', [layer('Layer 1', [
    [[PALETTE['r' if x < 35 and y < 25 else 'g' if y < 25 else 'b'] for x in range(70)] for y in range(45)]
])])

# Shades for lighten/darken: pure colours, mid grey, black and white (each lightens or darkens differently).
SHADES = one('shades', '''
    rrrrssss
    rrrrssss
    opopkwkw
    opopkwkw
    ........
    ........
    yyyyyyyy
    nnnnnnnn
''')

# Red pixels that do not touch each other: the colour swap tool replaces them all, the paint bucket only one.
SPOTS = one('spots', '''
    r.r.r.r.
    ........
    .b.r.b..
    ........
    r.r.r.r.
    ...g....
    .r...r..
    ........
''')


def cell(text):
    return grid(text, 8, 8)


# Two layers by two frames with red in every cell at a different place and a green marker that must stay.
MULTI = sprite('multi', [
    layer('base', [cell('r.....g.\nr.......'), cell('.r....g.\n.r......')]),
    layer('top', [cell('..r...g.\n..r.....'), cell('...r..g.\n...r....')]),
])

# A diagonal barrier: with 4-connected filling the two triangles stay separate.
DIAG = one('diag', '''
    .......k
    ......k.
    .....k..
    ....k...
    ...k....
    ..k.....
    .k......
    k.......
''')

# Content in one corner, for centring.
CORNER = one('corner', '''
    rrg.....
    rr......
    ........
    ........
    ........
    ........
    ........
    ........
''')

# Content in the middle, for cropping.
MIDDLE = one('middle', '''
    ........
    ........
    ...rg...
    ...b....
    ....y...
    ........
    ........
    ........
''')

ODD = one('odd', '.......', 7, 5)
BIG = one('big', '................', 16, 16)

FIXTURES = {s['name']: s for s in (BLANK, REGIONS, ARROW, WIDE, ANIM, LAYERS, GRID, SHADES, SPOTS, MULTI, DIAG,
                                   CORNER, MIDDLE, ODD, BIG)}


def text(name, description=''):
    return encode(FIXTURES[name], description)
