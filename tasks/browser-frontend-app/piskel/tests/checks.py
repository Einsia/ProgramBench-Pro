"""Program observations of the open sprite and of product files, and their comparison.

Reads go through the runtime only: the api operation (getPiskel) for the sprite in the
editor, snapshot + download for product files (PNG, animated GIF, .piskel, ZIP), and the
snapshot for the few points whose subject is what the page shows (title, frame counter).
Pixels are compared exactly; a pixel is '.' when transparent, else 'rrggbb' when opaque
or 'rrggbbaa'.
"""
import base64
import io
import json
import math
import sys
import zipfile
import re

import fixtures as F

sys.path.insert(0, '/opt/verifier-lib')


def token(px):
    r, g, b, a = px
    if a == 0:
        return '.'
    return f'{r:02x}{g:02x}{b:02x}' + ('' if a == 255 else f'{a:02x}')


def grid_of(rows):
    return [' '.join(token(px) for px in row) for row in rows]


class Reader:
    """The sprite of the current checkpoint, read once through the runtime api operation."""

    def __init__(self, broker):
        self.broker = broker
        self.cache = None

    def reset(self):
        self.cache = None

    def sprite(self):
        if self.cache is None:
            answer = self.broker.call({'op': 'api', 'method': 'getPiskel'})
            text = answer.get('piskel')
            if not isinstance(text, str):
                raise AssertionError('getPiskel returned no document: ' + json.dumps(answer)[:200])
            try:
                self.cache = F.decode(text)
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                raise AssertionError(f'the editor document could not be read: {exc}'[:300])
        return self.cache


def observe(ctx, cp, spec):
    kind = spec['type']
    if kind == 'listed-documents':
        import ui
        snap = ctx.broker.call({'op':'snapshot'})
        controls = [c for c in snap.get('controls',[]) if ui.semantic(c,spec.get('action','Load'))]
        found=set()
        for c in controls:
            for group in c.get('context','').split(' | '):
                hits=[name for name in spec['names'] if name.casefold() in group.casefold()]
                if len(hits)==1:
                    found.add(hits[0]);break
        return {'present':{name:name in found for name in spec['names']}}
    if kind == 'palette-names':
        snap = ctx.broker.call({'op': 'snapshot'})
        options = [c['options'] for c in snap.get('controls', []) if c.get('options') and
                   any(o.get('label') == 'Current colors' for o in c['options'])]
        assert options, 'no palette selector'
        return {'names': [o['label'] for o in options[0]]}
    if kind == 'load-result':
        result = ctx.state.get('load_result', {})
        assert type(result.get('loaded')) is bool, 'loadPiskel returned no result'
        return {'loaded': result['loaded']}
    if kind == 'control':
        import ui
        c = ui.resolve(ctx, spec['match'])
        return {key: c.get(key) for key in spec['fields']}
    if kind == 'download':
        return observe_download(ctx, spec)
    if kind == 'page':
        return observe_page(ctx, spec)
    sp = ctx.state['reader'].sprite()
    if kind == 'pixels':
        return {'grid': grid_of(frame_of(sp, spec.get('layer', 0), spec.get('frame', 0)))}
    if kind == 'pixel':
        rows = frame_of(sp, spec.get('layer', 0), spec.get('frame', 0))
        return {'pixel': token(rows[spec['y']][spec['x']])}
    if kind == 'size':
        return {'width': sp['w'], 'height': sp['h']}
    if kind == 'frames':
        return {'frames': len(sp['layers'][0]['frames']) if sp['layers'] else 0}
    if kind == 'layers':
        names = [ly['name'] for ly in sp['layers']]
        if 'generated' in spec:
            index = spec['generated']
            assert 0 <= index < len(names), 'new layer is missing'
            assert isinstance(names[index], str) and names[index].strip(), 'new layer has no name'
            names[index] = '<generated name>'
        return {'layers': names}
    if kind == 'structure':
        return {'layer_count': len(sp['layers']), 'frame_counts': [len(ly['frames']) for ly in sp['layers']]}
    if kind == 'opacity':
        return {'opacity': round(float(layer_of(sp, spec['layer'])['opacity']), 3)}
    if kind == 'opacities':
        return {'opacities': [round(float(ly['opacity']), 3) for ly in sp['layers']]}
    if kind == 'layer-name':
        return {'name': layer_of(sp, spec['layer'])['name']}
    if kind == 'layer-frames':
        return {'frames': len(layer_of(sp, spec['layer'])['frames'])}
    if kind == 'meta':
        return {key: sp[key] for key in spec['keys']}
    if kind == 'hidden':
        return {'hidden': sorted(sp['hidden'])}
    if kind == 'all':
        # Every frame of every layer, for points about a whole document (round trips, undo).
        return {'layers': [{'frames': [grid_of(f) for f in ly['frames']]} for ly in sp['layers']]}
    raise ValueError('unknown check type ' + kind)


def layer_of(sp, index):
    if not -len(sp['layers']) <= index < len(sp['layers']):
        raise AssertionError(f"the sprite has {len(sp['layers'])} layers; layer {index} does not exist")
    return sp['layers'][index]


def frame_of(sp, li, fi):
    frames = layer_of(sp, li)['frames']
    if not -len(frames) <= fi < len(frames):
        raise AssertionError(f'the sprite has {len(frames)} frames; frame {fi} does not exist')
    return frames[fi]


def observe_page(ctx, spec):
    """What the page shows: a visible text that contains the expected words."""
    snap = ctx.broker.call({'op': 'snapshot'})
    texts = [' '.join(str(c.get(k) or '') for k in ('text', 'label', 'title', 'value'))
             for c in snap.get('controls', [])]
    texts.append(snap.get('title') or '')
    texts.append(snap.get('text') or '')
    return {'shown': any(spec['text'].lower() in t.lower() for t in texts)}


# -- product files ------------------------------------------------------------------------------------
def take_download(ctx, suffixes):
    """The newest pending product download with one of the suffixes (retrieved once, kept for the checkpoint)."""
    files = ctx.state.setdefault('files', {})
    key = tuple(suffixes)
    if key in files:
        return files[key]
    snap = ctx.broker.call({'op': 'snapshot'})
    pending = [d for d in snap.get('downloads', []) if d['filename'].lower().endswith(suffixes)]
    if not pending:
        raise AssertionError('no download ending in ' + '/'.join(suffixes) + ' was produced')
    item = ctx.broker.call({'op': 'download', 'ref': pending[-1]['ref']})
    files[key] = (item['filename'], base64.b64decode(item['body_base64']))
    return files[key]


def png_grid(data):
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(data))
        assert image.format == 'PNG', 'not a PNG'
        rgba = image.convert('RGBA')
        w, h = rgba.size
        px = list(rgba.getdata())
        rows = [px[y*w:(y+1)*w] for y in range(h)]
    except Exception as exc:
        raise AssertionError(f'the PNG could not be decoded: {exc}'[:300])
    return w, h, rows


def tiles(rows, w, h, cols, count):
    """Frames laid out in a sheet of `cols` columns, each w x h, row-major."""
    out = []
    for i in range(count):
        x0, y0 = (i % cols) * w, (i // cols) * h
        out.append(grid_of([row[x0:x0 + w] for row in rows[y0:y0 + h]]))
    return out


def gif_frames(data):
    from PIL import Image, ImageSequence
    try:
        image = Image.open(io.BytesIO(data))
        if image.format != 'GIF':
            raise AssertionError(f'not a GIF ({image.format})')
        frames, delays = [], []
        for frame in ImageSequence.Iterator(image):
            rgba = frame.convert('RGBA')
            px = list(rgba.getdata())
            w, h = rgba.size
            frames.append(grid_of([px[y * w:(y + 1) * w] for y in range(h)]))
            delays.append(int(frame.info.get('duration', 0)))
        return image.size, frames, delays, image.info.get('loop')
    except AssertionError:
        raise
    except Exception as exc:
        raise AssertionError(f'the GIF could not be decoded: {exc}'[:300])


def observe_download(ctx, spec):
    fmt = spec['format']
    parts = spec.get('parts', ())
    out = {}
    if fmt == 'png':
        name, data = take_download(ctx, ('.png',))
        w, h, rows = png_grid(data)
        out['size'] = [w, h]
        if 'grid' in parts:
            out['grid'] = grid_of(rows)
        if 'tiles' in parts:
            t = spec['tiles']
            out['tiles'] = tiles(rows, t['w'], t['h'], t['cols'], t['count'])
    elif fmt == 'gif':
        name, data = take_download(ctx, ('.gif',))
        size, frames, delays, loop = gif_frames(data)
        out['size'] = list(size)
        out['frames'] = len(frames)
        if 'grid' in parts:
            out['grids'] = frames
        if 'delay' in parts:
            # GIF stores hundredths of a second; one unit either way is the same frame rate.
            out['delays'] = [round(d / 10) for d in delays]
        if 'loop' in parts:
            out['loop'] = {'mode': 'once' if loop is None else 'infinite' if loop == 0 else 'finite',
                           'repeats': loop}
    elif fmt == 'piskel':
        name, data = take_download(ctx, ('.piskel',))
        try:
            sp = F.decode(data.decode('utf-8'))
        except Exception as exc:
            raise AssertionError(f'the .piskel file could not be read: {exc}'[:300])
        for key in ('name', 'description', 'fps', 'hidden'):
            if key in parts:
                out[key] = sp[key]
        if 'size' in parts:
            out['size'] = [sp['w'], sp['h']]
        if 'layers' in parts:
            out['layers'] = [{'name': ly['name'], 'opacity': round(float(ly['opacity']), 3),
                              'frames': [grid_of(f) for f in ly['frames']]} for ly in sp['layers']]
    elif fmt == 'zip':
        name, data = take_download(ctx, ('.zip',))
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
            members = sorted(n for n in archive.namelist() if not n.endswith('/'))
            out['count'] = len(members)
            if 'grid' in parts:
                out['grids'] = [grid_of(png_grid(archive.read(n))[2]) for n in members]
            if 'names' in parts:
                out['names'] = members
        except zipfile.BadZipFile as exc:
            raise AssertionError(f'the ZIP could not be read: {exc}')
    elif fmt == 'c':
        name, data = take_download(ctx, ('.c',))
        text = data.decode('utf-8')
        parsed = c_array(text)
        out['pixels'] = parsed['pixels']
        if 'dimensions' in parts:
            out['dimensions'] = parsed['dimensions']
    elif fmt == 'gpl':
        name, data = take_download(ctx, ('.gpl',))
        text = data.decode('utf-8')
        assert text.startswith('GIMP Palette'), 'not a GIMP palette'
        out['colors'] = [list(map(int, m)) for m in re.findall(r'^\s*(\d+)\s+(\d+)\s+(\d+)\b', text, re.M)]
        assert out['colors'], 'empty exported palette'
    elif fmt == 'pixi':
        name, data = take_download(ctx, ('.zip',))
        archive = zipfile.ZipFile(io.BytesIO(data))
        metadata = [n for n in archive.namelist() if n.endswith('.json')]
        assert len(metadata) == 1, 'spritesheet archive has no unique JSON metadata'
        doc = json.loads(archive.read(metadata[0]))
        frames = doc['frames']
        items = list(frames.items()) if isinstance(frames, dict) else [(f.get('filename', str(i)), f) for i, f in enumerate(frames)]
        def frame_number(item):
            numbers = re.findall(r'\d+', item[0].rsplit('/', 1)[-1].rsplit('.', 1)[0])
            assert numbers, 'frame identifier has no animation index'
            return int(numbers[-1])
        items.sort(key=frame_number)
        indices = [frame_number(item) for item in items]
        assert len(set(indices)) == len(indices), 'duplicate animation frame identifier'
        image_name = doc['meta']['image']
        if image_name.startswith('data:'):
            out['image_mode'] = 'inline'
            image_data = base64.b64decode(image_name.split(',', 1)[1])
        else:
            out['image_mode'] = 'external'
            image_data = archive.read(image_name)
        w, h, rows = png_grid(image_data)
        out['size'] = [w, h]
        out['rectangles'] = []
        out['frames'] = []
        for key, frame in items:
            rect = frame['frame']
            x, y, fw, fh = (rect[k] for k in ('x', 'y', 'w', 'h'))
            assert all(type(v) is int for v in (x, y, fw, fh)), 'non-integer frame rectangle'
            assert 0 <= x < w and 0 <= y < h and fw > 0 and fh > 0 and x+fw <= w and y+fh <= h, 'frame outside spritesheet'
            out['rectangles'].append({'index': frame_number((key, frame)), 'x':x, 'y':y, 'w':fw, 'h':fh})
            out['frames'].append({'index': frame_number((key, frame)), 'size': [fw, fh],
                                  'pixels': grid_of([r[x:x+fw] for r in rows[y:y+fh]])})
    else:
        raise ValueError('unknown download format ' + fmt)
    if 'name' in parts and fmt != 'piskel':
        out['name'] = name
    if 'stem' in parts:
        # The saved file name starts with the sprite name; the rest (a timestamp) is free.
        out['stem'] = name.lower().startswith(spec['stem'].lower())
    if spec.get('only'):
        out = {key: out[key] for key in spec['only']}
    return out


def c_array(text):
    """Read generated C integer constants without executing candidate code."""
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    constant = r'[+-]?(?:0[xX][0-9a-fA-F]+|0[bB][01]+|[0-9]+)[uUlL]*'
    def integer(token):
        token = re.sub(r'[uUlL]+$', '', token.strip())
        sign = -1 if token.startswith('-') else 1
        unsigned = token.lstrip('+-')
        base = 16 if unsigned.lower().startswith('0x') else 2 if unsigned.lower().startswith('0b') else 8 if len(unsigned)>1 and unsigned.startswith('0') else 10
        return sign * int(unsigned, base)
    dimensions = {}
    for key, value in re.findall(r'^\s*#define\s+\w*?(WIDTH|HEIGHT|FRAME_COUNT)\s+\(?\s*(' + constant + r')\s*\)?\s*$', text, re.M):
        dimensions[key.lower()] = integer(value)
    assert set(dimensions) == {'width', 'height', 'frame_count'}, 'missing C dimensions'
    arrays = re.findall(r'\b\w+\s*(?:\[[^\]]*\]\s*)+\s*=\s*(\{.*?\})\s*;', text, re.S)
    assert len(arrays) == 1, 'expected one C pixel array'
    body = arrays[0]
    values = [integer(v) for v in re.findall(constant, body)]
    residue = re.sub(constant, '', body)
    assert not re.sub(r'[\s{},()]', '', residue), 'unsupported C initializer expression'
    assert values and all(0 <= v <= 0xffffffff for v in values), 'invalid packed C pixels'
    assert len(values) == math.prod(dimensions.values()), 'C array size disagrees with its dimensions'
    return {'pixels': values, 'dimensions': dimensions}


def compare(actual, expected, tol, path='observation'):
    """Structural equality with numeric tolerance; AssertionError names the first difference."""
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if actual != expected:
            raise AssertionError(f'{path}: expected {json.dumps(expected)[:160]}, got {json.dumps(actual)[:160]}')
        return
    if isinstance(expected, (int, float)):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual) \
                or abs(actual - expected) > tol:
            raise AssertionError(f'{path}: expected {expected} (±{tol}), got {json.dumps(actual)[:80]}')
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise AssertionError(f'{path}: expected {len(expected)} items, got '
                                 f'{len(actual) if isinstance(actual, list) else json.dumps(actual)[:80]}')
        for i, (a, e) in enumerate(zip(actual, expected)):
            compare(a, e, tol, f'{path}[{i}]')
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise AssertionError(f'{path}: expected an object')
        missing = sorted(set(expected) - set(actual))
        if missing:
            raise AssertionError(f'{path}: missing keys {missing[:5]}')
        for key in expected:
            compare(actual[key], expected[key], tol, f'{path}.{key}')
        return
    raise AssertionError(f'{path}: unsupported value')


def compare_stroke(actual, expected, radius=1, mirror_axis=None):
    def parse(doc):
        rows=[r.split() for r in doc['grid']]
        assert rows and rows[0] and all(len(r)==len(rows[0]) for r in rows), 'invalid raster'
        colors={c for row in rows for c in row if c!='.'}
        assert colors, 'no painted stroke'
        points={c:{(x,y) for y,row in enumerate(rows) for x,v in enumerate(row) if v==c} for c in colors}
        return len(rows[0]),len(rows),points
    aw,ah,aa=parse(actual);ew,eh,ee=parse(expected)
    assert (aw,ah)==(ew,eh), 'sprite dimensions differ'
    assert aa.keys()==ee.keys(), 'stroke colors differ'
    for color,ep in ee.items():
        ap=aa[color]
        if mirror_axis == 'vertical':
            assert {(aw-1-x,y) for x,y in ap} == ap, 'stroke is not mirrored across the vertical axis'
        bounds=lambda pts:(min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts))
        assert bounds(ap)==bounds(ep), 'stroke endpoints or extent differ'
        assert len(ep)*.75<=len(ap)<=len(ep)*1.5, 'stroke area differs'
        for left,right in ((ap,ep),(ep,ap)):
            assert all(any(abs(x-u)+abs(y-v)<=radius for u,v in right) for x,y in left), 'stroke path differs'
