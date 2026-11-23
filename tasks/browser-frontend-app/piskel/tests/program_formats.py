"""Document-format compatibility, metadata, layout and load/save round trips."""
import copy
import json
import base64
from program import F, case, episode, point, pix, meta, SIZE, HIDDEN

# The frame 'r.r.\n.rr.\n....' (4x3) as Pillow 11.3.0 saved it for the frozen manifest: a palette image (index 0
# black and transparent, index 1 red) at bit depth 1 and 4, and an RGB image whose transparent pixels are the colour
# key (0, 255, 255). Frozen bytes: other Pillow versions choose other row filters for the same pixels.
ENCODED_PNG = {
    'indexed-1bit': 'iVBORw0KGgoAAAANSUhEUgAAAAQAAAADAQMAAACOOjyFAAAABlBMVEUAAAD/AAAb/40iAAAAAXRSTlMAQObYZgAAAA5JREFUeJxjWMCQ'
                    'wMAAAARGAQHUgOXMAAAAAElFTkSuQmCC',
    'indexed-4bit': 'iVBORw0KGgoAAAANSUhEUgAAAAQAAAADBAMAAABG2rP1AAAAMFBMVEUAAAD/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
                    'AAAAAAAAAAAAAAAiquwRAAAAAXRSTlMAQObYZgAAABFJREFUeJxjEBBgYBRgYGAAAAE+ADJgfaKXAAAAAElFTkSuQmCC',
    'rgb-colorkey': 'iVBORw0KGgoAAAANSUhEUgAAAAQAAAADCAIAAAA7ljmRAAAABnRSTlMAAAD/AP/9PNzxAAAAG0lEQVR4nGP4z8DA8P8/hISyIBxGhv//'
                    'GWAAAEj5DfRInaDjAAAAAElFTkSuQmCC',
}


def document_points(sp, metadata=True):
    out = [point('size', 'Document dimensions survive serialization.', SIZE),
           point('structure', 'The exact layer count and frame count in every layer survive.', {'type': 'structure'})]
    if metadata:
        out += [point('name', 'Document name survives serialization.', meta('name')),
                point('description', 'Document description survives serialization.', meta('description')),
                point('fps', 'Animation frame rate survives serialization.', meta('fps')),
                point('hidden', 'Preview exclusion list survives serialization.', HIDDEN)]
    for li, ly in enumerate(sp['layers']):
        out += [point(f'layer-{li}-name', 'Layer name and order are retained.', {'type': 'layer-name', 'layer': li}),
                point(f'layer-{li}-opacity', 'Layer opacity is retained.', {'type': 'opacity', 'layer': li})]
        for fi, frame in enumerate(ly['frames']):
            out += [point(f'layer-{li}-frame-{fi}', 'Decoded pixel content of this frame.', pix(li, fi))]
    return out


def encoded_variant(sp, variant):
    doc = json.loads(F.encode(sp, 'Sprite format fixture\n多帧'))
    if variant == 'unchunked':
        for i, text in enumerate(doc['piskel']['layers']):
            ly = json.loads(text)
            ly['base64PNG'] = ly.pop('chunks')[0]['base64PNG']
            doc['piskel']['layers'][i] = json.dumps(ly)
    elif variant in ('vertical', 'separate', 'reversed', 'grid', 'chunk-grid'):
        for i, original in enumerate(sp['layers']):
            ly = json.loads(doc['piskel']['layers'][i]); frames = original['frames']
            w, h, n = sp['w'], sp['h'], len(frames)
            def chunk(indices, cols):
                rows = (len(indices) + cols - 1)//cols
                image = F.blank(w * cols, h * rows)
                layout = [[None] * rows for _ in range(cols)]
                for j, index in enumerate(indices):
                    x, y = j % cols, j // cols
                    layout[x][y] = index
                    for yy in range(h): image[y*h+yy][x*w:(x+1)*w] = frames[index][yy]
                return {'layout': layout, 'base64PNG': 'data:image/png;base64,' +
                        base64.b64encode(F.png_bytes(w*cols, h*rows, image)).decode()}
            if variant == 'separate': ly['chunks'] = [chunk([j], 1) for j in range(n)]
            elif variant == 'reversed': ly['chunks'] = [chunk(list(range(n-1, -1, -1)), n)]
            elif variant == 'vertical': ly['chunks'] = [chunk(list(range(n)), 1)]
            elif variant == 'chunk-grid': ly['chunks'] = [chunk(list(range(3,n)), 2), chunk(list(range(3)), 2)]
            else: ly['chunks'] = [chunk(list(range(n)), 2)]
            doc['piskel']['layers'][i] = json.dumps(ly)
    return json.dumps(doc)


def encoding_cases():
    cases=[]
    for count,variant in [(4,'grid'),(5,'grid'),(5,'chunk-grid')]:
        sp=copy.deepcopy(F.GRID)
        for li,ly in enumerate(sp['layers']):
            ly['frames']=[F.blank(5,3) for _ in range(count)]
            for fi,frame in enumerate(ly['frames']):
                frame[fi%3][(fi+li)%5]=F.PALETTE['rgbymc'[fi+li]]
        sp['w'],sp['h']=5,3
        cases.append(case(f'{variant}-{count}','Load a multi-row, multi-column atlas and round-trip every frame.',None,
                          [{'op':'load','piskel':encoded_variant(sp,variant)},{'op':'roundtrip'}],document_points(sp,metadata=False)))
    for variant in ('indexed-1bit','indexed-4bit','rgb-colorkey'):
        sp=F.one(variant,'r.r.\n.rr.\n....',4,3)
        document=json.loads(F.encode(sp));ly=json.loads(document['piskel']['layers'][0])
        ly['chunks'][0]['base64PNG']='data:image/png;base64,'+ENCODED_PNG[variant]
        document['piskel']['layers'][0]=json.dumps(ly)
        cases.append(case(variant,'Load and round-trip a PNG with palette or color-key transparency.',None,
                          [{'op':'load','piskel':json.dumps(document)},{'op':'roundtrip'}],document_points(sp,metadata=False)))
    return episode('format-encoding','file-format',cases)


def formats():
    cases = []
    sample = copy.deepcopy(F.GRID)
    for variant in ('normal', 'unchunked', 'vertical', 'separate', 'reversed', 'grid'):
        fixture = copy.deepcopy(F.GRID if variant != 'grid' else sample)
        encoded = encoded_variant(fixture, variant)
        c = case(variant, 'Load the document, serialize and reload it.', None,
                 [{'op': 'load', 'piskel': encoded}, {'op': 'roundtrip'}], document_points(fixture))
        cases.append(c)
    return episode('format-layout', 'file-format', cases)


def dimensions():
    cases = []
    for w, h in [(1, 1), (1, 9), (9, 1), (2, 3), (3, 2), (7, 5), (17, 19), (32, 32), (65, 33), (128, 64)]:
        frames = []
        for i in range(2):
            rows = F.blank(w, h)
            for x, y, color in [(0, 0, 'r'), (w-1, h-1, 'g'), (w//2, h//2, 'b')]:
                rows[y][x] = F.PALETTE[color if i == 0 else {'r':'y','g':'m','b':'c'}[color]]
            frames.append(rows)
        sp = F.sprite(f'{w}x{h}', [F.layer('size', frames)], fps=7)
        cases.append(case(f'{w}x{h}', 'Load and round-trip a sprite with edge and centre pixels.', sp,
                          [{'op': 'roundtrip'}], [point('size', 'Dimensions survive.', SIZE),
                           point('structure', 'No layer or frame is added or lost.', {'type': 'structure'}),
                           point('first', 'First frame retains edges and transparency.', pix(0, 0)),
                           point('second', 'Second frame remains distinct.', pix(0, 1))]))
    return episode('format-size', 'file-format', cases)


def metadata():
    cases = []
    for cid, name, desc, fps, opacity, hidden in [
        ('unicode', '星 / café 🎨', 'naïve\n第二行', 7, .35, [1]),
        ('entities', 'A & B < C > D', 'quotes "double" and \'single\'', 18, .75, [0, 2]),
        ('empty', '', '', 1, 0, []), ('spaces', '  spaced name  ', ' leading and trailing ', 24, 1, [2]),
        ('fast', 'speed', '60 fps document', 60, .01, [0]),
        ('linebreak', 'name\nnext', 'a\tb\nc', 12, .999, [1, 2])]:
        sp = copy.deepcopy(F.GRID); sp['name'] = name; sp['fps'] = fps; sp['hidden'] = hidden
        sp['layers'][0]['name'] = name or 'empty title'; sp['layers'][0]['opacity'] = opacity
        c = case(cid, 'Round-trip names, description, speed, opacity and preview selection.', None,
                 [{'op': 'load', 'piskel': F.encode(sp, desc)}, {'op': 'roundtrip'}], document_points(sp))
        cases.append(c)
    return episode('format-metadata', 'file-format', cases)


def backward():
    cases = []
    for version in (0, 1):
        for cid, sp in [('nonsquare', F.WIDE), ('animation', F.ANIM), ('multilayer', F.GRID)]:
            def grid(frame):
                # Old pixel grids are column-major colour strings.
                return [[('rgba(0, 0, 0, 0)' if frame[y][x][3] == 0 else '#%02x%02x%02x' % frame[y][x][:3])
                         for y in range(sp['h'])] for x in range(sp['w'])]
            if version == 0:
                doc = [grid(f) for f in sp['layers'][0]['frames']]
                expected = copy.deepcopy(sp); expected['layers'] = expected['layers'][:1]
            else:
                doc = {'modelVersion': 1, 'piskel': {'width': sp['w'], 'height': sp['h'], 'layers': [json.dumps({
                    'name': ly['name'], 'frames': [json.dumps(grid(f)) for f in ly['frames']]}) for ly in sp['layers']]}}
                expected = sp
            cases.append(case(f'v{version}-{cid}', f'Load the historical v{version} document format.', None,
                              [{'op': 'load', 'piskel': json.dumps(doc)}, {'op': 'roundtrip'}],
                              document_points(expected, metadata=False)))
    return episode('format-backward', 'file-format', cases)


def invalid():
    cases = [case('valid', 'Load a valid sprite through the public document API.', F.BLANK,
                  [{'op': 'load-result', 'piskel': F.encode(F.ARROW)}],
                  [point('loaded', 'Valid document is accepted.', {'type': 'load-result'}),
                   point('pixels', 'Accepted data is exposed as a sprite.', pix())])]
    for cid, text in [('syntax', '{'), ('null', 'null'), ('scalar', '42'), ('object', '{}'),
                      ('version', '{"modelVersion":99}'), ('missing-piskel', '{"modelVersion":2}'),
                      ('missing-layers', '{"modelVersion":2,"piskel":{"width":8,"height":8}}')]:
        cases.append(case(cid, 'Attempt to load an invalid document and then read the editor.', F.ARROW,
                          [{'op': 'load-result', 'piskel': text}],
                          [point('rejected', 'Invalid document reports failure.', {'type': 'load-result'}, requires=['valid/loaded']),
                           point('preserved', 'A rejected load preserves the current sprite.', pix(), requires=['valid/pixels'])]))
    return episode('format-errors', 'file-format', cases)


def build():
    return [formats(), dimensions(), metadata(), backward(), invalid(), encoding_cases()]
