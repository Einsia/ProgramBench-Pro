"""Deterministic public document inputs, built without importing the product."""
import base64
import gzip
import io
import math
import xml.etree.ElementTree as ET
import zipfile


def stroke(points, *, tool='pen', color='#224488ff', width=3, **attrs):
    node = ET.Element('stroke', tool=tool, color=color, width=str(width), **{k: str(v) for k, v in attrs.items()})
    node.text = ' '.join(f'{n:g}' for point in points for n in point)
    return node


def text(value, x=35, y=40, *, font='Sans', size=20, color='#202020ff'):
    node = ET.Element('text', font=font, size=str(size), x=str(x), y=str(y), color=color)
    node.text = value
    return node


def picture(kind='color', size=(120, 80), fmt='PNG'):
    from PIL import Image, ImageDraw
    image = Image.new('RGBA', size, (255, 255, 255, 0) if kind == 'alpha' else (250, 239, 207, 255))
    d = ImageDraw.Draw(image)
    w, h = size
    d.rectangle((w*.05, h*.10, w*.45, h*.65), fill=(205, 28, 40, 255))
    d.ellipse((w*.50, h*.30, w*.95, h*.95), fill=(20, 70, 200, 130 if kind == 'alpha' else 255))
    d.line((0, h-2, w-1, 0), fill=(10, 125, 70, 255), width=4)
    if kind == 'gray':
        image = image.convert('L')
    if fmt == 'JPEG':
        image = image.convert('RGB')
    out = io.BytesIO()
    image.save(out, format=fmt)
    return out.getvalue()


def image(kind='color', box=(30, 40, 240, 180), fmt='PNG'):
    n = ET.Element('image', **dict(zip(('left', 'top', 'right', 'bottom'), map(str, box))))
    n.text = base64.b64encode(picture(kind, fmt=fmt)).decode()
    return n


def page(elements=(), *, size=(360, 280), style='plain', color='#ffffffff', config=None, layers=None, background=None):
    n = ET.Element('page', width=str(size[0]), height=str(size[1]))
    bg = dict(type='solid', color=color, style=style) if background is None else dict(background)
    if config is not None:
        bg['config'] = config
    ET.SubElement(n, 'background', **bg)
    for name, children in (layers if layers is not None else [('Notes', elements)]):
        layer = ET.SubElement(n, 'layer', name=name)
        layer.extend(children)
    return n


def document(pages, encoding='gzip', version='4'):
    root = ET.Element('xournal', creator='Notebook document', fileversion=version)
    ET.SubElement(root, 'title').text = 'Notes'
    root.extend(pages)
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    if encoding == 'plain':
        return data
    if encoding == 'zip':
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, content in [('mimetype', b'application/xournal++'), ('META-INF/version', b'current=4\nmin=1'), ('content.xml', data)]:
                info = zipfile.ZipInfo(name, (2024, 1, 1, 0, 0, 0))
                z.writestr(info, content)
        return out.getvalue()
    return gzip.compress(data, mtime=0)


def pdf(kind='normal'):
    import pymupdf as fitz
    doc = fitz.open()
    sizes = [(360, 280), (280, 360), (420, 240)] if kind != 'single' else [(360, 280)]
    if kind == 'fractional':
        sizes = [(301.25, 219.75), (127.5, 300.25)]
    for i, (w, h) in enumerate(sizes):
        p = doc.new_page(width=w, height=h)
        p.insert_text((30, 55), f'Chapter {i+1}: paper notes', fontsize=18, color=(.1, .2, .45))
        p.insert_text((30, 100), 'Review this sentence and annotate it.', fontsize=12)
        p.draw_rect(fitz.Rect(30, 135, w-30, h-30), color=(.1, .6, .3), width=3)
        p.draw_circle(fitz.Point(w-60, h-60), 15, color=(.8, .1, .2), fill=(.8, .1, .2))
        if kind == 'rotated':
            p.set_rotation((i+1)*90 % 360)
        if kind == 'cropped':
            p.set_cropbox(fitz.Rect(10, 10, w-10, h-10))
        if kind == 'images':
            p.insert_image(fitz.Rect(55, 135, w-55, h-35), stream=picture())
    if kind == 'navigation':
        doc.set_toc([[1, f'Chapter {i+1}', i+1] for i in range(len(doc))])
        doc[0].insert_link({'kind': fitz.LINK_URI, 'from': fitz.Rect(30, 30, 250, 60), 'uri': 'https://example.invalid/notes'})
        doc[1].insert_link({'kind': fitz.LINK_GOTO, 'from': fitz.Rect(30, 80, 250, 110), 'page': 2, 'to': fitz.Point(0,0)})
    doc.set_metadata({'title': 'Paper notes', 'author': 'Sample Author', 'creationDate': 'D:20240101000000Z', 'modDate': 'D:20240101000000Z'})
    return doc.tobytes(deflate=True, no_new_id=True)


def stroke_pages():
    """Different geometric/serialization branches, not a Cartesian parameter grid."""
    cases = []
    def add(name, nodes, **kw):
        cases.append((name, page(nodes, **kw)))
    for width in [.35, 1.41, 6, 18]:
        add('width-'+str(width).replace('.', '-'), [stroke([(40, 80), (300, 160)], width=width)])
    for cap in ['round', 'butt', 'square']:
        add('cap-'+cap, [stroke([(60, 80), (280, 180)], width=20, capStyle=cap)])
    for style in ['dash', 'dot', 'dashdot', 'cust: 2 7 12 4']:
        add('style-'+style.split(':')[0], [stroke([(35, 90), (310, 90), (250, 210)], width=5, style=style)])
    for name, points in [('dot', [(150, 130), (150, 130)]), ('zigzag', [(40, 70), (100, 200), (170, 60), (250, 200), (315, 80)]),
                         ('clipped', [(-40, 50), (400, 240)]), ('crossing', [(40, 50), (300, 230), (300, 50), (40, 230)]),
                         ('closed', [(60, 60), (280, 60), (280, 210), (60, 210), (60, 60)])]:
        add(name, [stroke(points, width=6)])
    for fill in [0, 128, 255]:
        add('fill-'+str(fill), [stroke([(55, 55), (300, 90), (150, 230), (55, 55)], width=5, fill=fill, color='#cc3344ff')])
    for name, widths in [('rising', '5 1 3 6 12'), ('falling', '5 14 10 4 1'), ('wave', '4 2 10 2 10')]:
        add('pressure-'+name, [stroke([(40, 140), (130, 100), (220, 160), (310, 140)], width=widths)])
    for color in ['black', 'blue', 'red', 'green', 'gray', 'lightblue', 'lightgreen', 'magenta', 'orange', 'yellow', 'white']:
        add('named-'+color, [stroke([(45, 80), (300, 200)], color=color, width=14)], color='#606060ff' if color == 'white' else '#ffffffff')
    add('highlight-over-text', [text('Important words', 40, 105, size=25), stroke([(35, 125), (310, 125)], tool='highlighter', color='#ffff007f', width=24)])
    add('highlight-overlap', [stroke([(50, 100), (300, 170)], tool='highlighter', color='#ffdd007f', width=30),
                              stroke([(50, 170), (300, 100)], tool='highlighter', color='#33dd447f', width=30)])
    add('eraser-file', [stroke([(40, 100), (300, 190)], width=24), stroke([(170, 50), (170, 230)], tool='eraser', color='#ffffffff', width=30)])
    return cases


def text_pages():
    cases = []
    def add(name, value, **kw):
        cases.append((name, page([text(value, **kw)])))
    for font in ['Sans', 'Serif', 'Monospace', 'Sans Bold', 'Sans Italic', 'Sans Bold Italic', 'Serif Bold', 'Monospace Bold']:
        add('font-'+font.lower().replace(' ', '-'), 'Paper notes 0123', font=font)
    for size in [5, 9.5, 12, 28, 48, 72]:
        add('size-'+str(size).replace('.', '-'), 'Ab9', size=size)
    for name, value in [('multiline', 'First line\nSecond line\nThird line'), ('blank-line', 'First\n\nThird'),
                        ('spaces', 'left     right'), ('punctuation', '<&> "quoted" / path'),
                        ('latin', 'Café naïve Ångström'), ('greek', 'Ελληνικά αβγ'), ('cyrillic', 'Заметки Москва'),
                        ('cjk', '中文笔记 日本語'), ('arabic', 'مرحبا بالعالم'), ('combining', 'Cafe\u0301 A\u030a'),
                        ('rtl-mixed', 'שלום 123 notes')]:
        add(name, value)
    for name, x, y in [('origin', 0, 0), ('fractional', 33.75, 65.125), ('clipped-left', -20, 80), ('clipped-bottom', 30, 268)]:
        add(name, 'Positioned text', x=x, y=y)
    for name, color in [('red', '#c02030ff'), ('green', '#228844ff'), ('blue', '#2244ccff'), ('alpha-ignored', '#80339940')]:
        add(name, 'Colored words', color=color)
    return cases


def background_pages():
    cases = []
    for style in ['plain', 'ruled', 'lined', 'staves', 'graph', 'dotted', 'isodotted', 'isograph']:
        cases.append((style, page([text('Notes', 100, 110)], style=style)))
    configurations = [('lined-right', 'lined', 'm1=-72'), ('lined-colors', 'lined', 'f1=#008844,f2=#dd6600,r1=33,m1=44'),
                      ('ruled-spacing', 'ruled', 'r1=36,lw=2'), ('graph-border', 'graph', 'm1=40,rm=1'),
                      ('graph-bold', 'graph', 'm1=20,rm=1,bli=5,blw=2'), ('graph-color', 'graph', 'f1=#227744,r1=22'),
                      ('dotted-wide', 'dotted', 'r1=30,lw=3'), ('iso-dots', 'isodotted', 'r1=32,lw=3'),
                      ('iso-lines', 'isograph', 'r1=28,lw=2'), ('staves-spacing', 'staves', 'r1=14,lw=1')]
    for name, style, config in configurations:
        cases.append((name, page([text('Notes', 100, 110)], style=style, config=config)))
    for color in ['blue', 'pink', 'green', 'orange', 'yellow', '#203040ff', '#e8d8c8ff']:
        cases.append(('color-'+color.lstrip('#'), page([stroke([(40, 80), (300, 190)], color='#cc3366ff', width=8)], style='graph', color=color)))
    return cases


def image_pages():
    cases = []
    for name, kind, box, fmt in [('png', 'color', (30, 40, 240, 180), 'PNG'), ('jpeg', 'color', (30, 40, 240, 180), 'JPEG'),
                               ('alpha', 'alpha', (30, 40, 240, 180), 'PNG'), ('gray', 'gray', (30, 40, 240, 180), 'PNG'),
                               ('stretched', 'color', (50, 40, 315, 95), 'PNG'), ('clipped', 'color', (-40, 190, 220, 340), 'PNG'),
                               ('fractional', 'alpha', (13.25, 28.75, 241.5, 199.25), 'PNG')]:
        cases.append((name, page([image(kind, box, fmt)], style='graph')))
    cases.append(('overlap', page([image(), image('alpha', (145, 110, 330, 240)), text('Front', 200, 145)])))
    return cases


def layer_pages(count=4):
    colors = ['#cc2222ff', '#22aa44ff', '#2255ccff', '#aa3399ff']
    return [page(size=(330+i*15, 260+i*10), color='#fff4d8ff', style='graph',
                 layers=[(f'Layer {j+1}', [text(f'Page {i+1} layer {j+1}', 30, 30+j*45, color=colors[j]),
                                          stroke([(220-j*25, 50+j*35), (290, 100+j*30)], color=colors[j], width=8)])
                         for j in range(i % count + 1)]) for i in range(count)]


def gui(name):
    from fixtures_revision import get
    extra=get(name)
    if extra is not None:return extra
    if name.endswith('.pdf'):
        return pdf(name.removesuffix('.pdf'))
    if name.endswith('.png'):
        return picture('alpha' if name.startswith('alpha') else 'color')
    if name == 'broken.xopp':
        return b'This is not a notebook.\n'
    if name == 'blank.xopp':
        pages = [page(size=(600, 400))]
    elif name == 'objects.xopp':
        pages = [page([text('Alpha note', 90, 75, size=24), text('Beta note', 330, 240, size=24),
                       stroke([(80, 180), (240, 180), (240, 270), (80, 270), (80, 180)], color='#cc3333ff', width=5)], size=(600, 400))]
    elif name == 'strokes.xopp':
        pages = [page([stroke([(80, 90), (430, 90)], width=9, color='#cc3333ff'),
                       stroke([(80, 180), (430, 180)], width=9, color='#2244ccff'),
                       stroke([(80, 270), (430, 270)], width=9, color='#228844ff')], size=(600, 400))]
    elif name == 'layers.xopp':
        pages = [page(size=(600, 400), layers=[('Lower notes', [text('Lower layer', 80, 90, size=30, color='#cc3333ff')]),
                                              ('Upper notes', [text('Upper layer', 280, 240, size=30, color='#2244ccff')])])]
    elif name == 'pages.xopp':
        pages = [page([text(f'Page {i+1}', 100, 110, size=48)], size=(600, 400), color=c) for i, c in enumerate(['#fff4ccff', '#e4f5ffff', '#e8ffe0ff'])]
    elif name == 'rich.xopp':
        pages = [p for _, p in [*stroke_pages()[:8], *text_pages()[:5], *background_pages()[:8], *image_pages()[:3]]]
    else:
        raise ValueError('unknown fixture '+name)
    return document(pages)
