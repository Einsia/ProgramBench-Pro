"""Serializer-neutral measurements of public product outputs."""
import base64
import gzip
import io
import math
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
import pymupdf as fitz


def raster(image):
    image = image.convert('RGBA')
    paper = Image.new('RGBA', image.size, (255, 255, 255, 255))
    paper.alpha_composite(image)
    size = (max(1, round(image.width * min(1, 360 / max(image.size)))), max(1, round(image.height * min(1, 360 / max(image.size)))))
    rgb = paper.convert('RGB').resize(size, Image.Resampling.LANCZOS)
    b = io.BytesIO()
    rgb.save(b, format='PNG')
    return {'size': list(size), 'png': base64.b64encode(b.getvalue()).decode()}


def compare_raster(actual, expected):
    a = Image.open(io.BytesIO(base64.b64decode(actual['png']))).convert('RGB')
    e = Image.open(io.BytesIO(base64.b64decode(expected['png']))).convert('RGB')
    if a.size != e.size:
        a = a.resize(e.size, Image.Resampling.LANCZOS)
    aa = np.asarray(a.filter(ImageFilter.GaussianBlur(.7)), dtype=float)
    ee = np.asarray(e.filter(ImageFilter.GaussianBlur(.7)), dtype=float)
    diff = np.max(np.abs(aa-ee), axis=2)
    colors,counts=np.unique(np.asarray(e)[::4,::4].reshape(-1,3),axis=0,return_counts=True)
    background=colors[int(counts.argmax())].astype(float)
    ink = np.max(np.abs(ee-background), axis=2) > 22
    denominator = max(20, int(ink.sum()))
    # Normalize against the ink rather than the whole mostly blank page: a missing
    # stroke/text/image must fail. Blur tolerates antialiasing and subpixel placement.
    bad = int((diff > 38).sum()) / denominator
    error = float(np.maximum(diff-6,0).sum()) / denominator
    expected_ink=float(np.maximum(np.max(np.abs(ee-background),axis=2)-6,0).sum())
    actual_ink=float(np.maximum(np.max(np.abs(aa-background),axis=2)-6,0).sum())
    assert expected_ink<20 or actual_ink>=expected_ink*.45,'rendered foreground is missing'
    assert bad <= .16 and error <= 20, f'rendered content differs (area {bad:.3f}, ink-normalized error {error:.2f})'


def normalize_text(s):
    return unicodedata.normalize('NFC', s).replace('\r\n', '\n').strip('\n')


def pdf(data):
    doc = fitz.open(stream=data, filetype='pdf')
    pages = []
    for p in doc:
        spans=[]
        for block in p.get_text('dict')['blocks']:
            if block['type']!=0:continue
            for line in block['lines']:
                merged=[]
                for original in line['spans']:
                    if not original['text'].strip():continue
                    span=dict(original)
                    if merged and all(span[k]==merged[-1][k] for k in ('size','color')) and \
                            (int(span['flags'])&(2|8|16))==(int(merged[-1]['flags'])&(2|8|16)):
                        merged[-1]['text']+=span['text']
                    else:merged.append(span)
                spans.extend(merged)
        pix = p.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        pages.append({'size': [round(p.rect.width, 3), round(p.rect.height, 3)],
                      'text': normalize_text(p.get_text('text')),
                      'spans': [{'text': normalize_text(s['text']), 'origin': [round(x, 2) for x in s['origin']],
                                 'size': round(s['size'], 2), 'style': int(s['flags']) & (2|8|16), 'color': s['color']} for s in spans],
                      'render': raster(Image.frombytes('RGB', [pix.width, pix.height], pix.samples))})
    links=[]
    for index,p in enumerate(doc):
        for link in p.get_links():
            value={'page':index,'kind':link['kind'],'rect':[round(v,2) for v in link['from']]}
            if 'uri' in link:value['uri']=link['uri']
            if link.get('kind')==fitz.LINK_GOTO:value['destination']=link.get('page')
            links.append(value)
    result = {'kind': 'pdf', 'pages': pages, 'outline':doc.get_toc(), 'links':links}
    doc.close()
    return result


def bitmap(data):
    image = Image.open(io.BytesIO(data))
    image.load()
    alpha = np.asarray(image.convert('RGBA'))[:, :, 3]
    return {'kind': 'image', 'size': list(image.size), 'render': raster(image),
            'alpha': {'transparent_fraction': round(float((alpha < 16).mean()), 4),
                      'partial_fraction': round(float(((alpha >= 16) & (alpha < 250)).mean()), 4)}}


def svg(data, folder):
    root = ET.fromstring(data)
    def length(s):
        m = re.fullmatch(r'([0-9.eE+-]+)(pt|px|mm|cm|in)?', s or '')
        assert m, 'SVG has no usable dimensions'
        factors = {'pt': 1, 'px': .75, 'mm': 72/25.4, 'cm': 72/2.54, 'in': 72, None: .75}
        return float(m[1])*factors[m[2]]
    sizes = [length(root.get('width')), length(root.get('height'))]
    out = subprocess.run(['rsvg-convert', '--format=png', '--width=480'], input=data, capture_output=True, timeout=25)
    assert out.returncode == 0 and out.stdout.startswith(b'\x89PNG'), 'SVG could not be rendered'
    value = bitmap(out.stdout)
    value.update(kind='svg', size=sizes)
    return value


def native(data):
    if data.startswith(b'\x1f\x8b'):
        data = gzip.decompress(data)
    root = ET.fromstring(data)
    assert root.tag == 'xournal', 'not a notebook'
    pages = []
    for p in root.findall('page'):
        bg = dict(p.find('background').attrib)
        layers = []
        for layer in p.findall('layer'):
            children = []
            for el in layer:
                attrs = dict(el.attrib)
                for key in ('ts', 'fn'):
                    attrs.pop(key, None)
                item = {'kind': el.tag, 'attrs': attrs}
                if el.tag == 'stroke':
                    points = list(map(float, (el.text or '').split()))
                    assert len(points) >= 2 and len(points) % 2 == 0, 'unreadable stroke points'
                    xs, ys = points[::2], points[1::2]
                    item['points']=[list(p) for p in zip(xs,ys)]
                    item['box'] = [min(xs), min(ys), max(xs), max(ys)]
                    item['ends'] = [xs[0], ys[0], xs[-1], ys[-1]]
                    widths=list(map(float,attrs.get('width','1').split()))
                    if min(xs)==max(xs) and min(ys)==max(ys) and (not any(widths) or attrs.get('capStyle','round')=='butt'):
                        # A butt cap does not paint a point with no segment.
                        # Round/square caps of nonzero width remain visible dots.
                        continue
                elif el.tag == 'text':
                    item['text'] = normalize_text(el.text or '')
                elif el.tag in ('image', 'teximage'):
                    item['image'] = bitmap(base64.b64decode(el.text or ''))
                children.append(item)
            layers.append({'name': layer.get('name', ''), 'items': children})
        pages.append({'size': [float(p.get('width')), float(p.get('height'))], 'background': bg, 'layers': layers})
    assert pages, 'notebook has no pages'
    return {'kind': 'native', 'pages': pages}


def measure(data, suffix, folder=None):
    if suffix == '.pdf':
        return pdf(data)
    if suffix in ('.xopp', '.xoj'):
        return native(data)
    if suffix == '.svg':
        return svg(data, folder)
    return bitmap(data)


def numeric(a, e, tolerance=.5):
    if isinstance(e, list):
        assert isinstance(a, list) and len(a) == len(e), 'number of measured values differs'
        for x, y in zip(a, e):
            numeric(x, y, tolerance)
    else:
        assert isinstance(a, (float, int)) and math.isfinite(a) and abs(a-e) <= tolerance, f'{a!r} differs from {e!r}'


def compare(actual, expected):
    kind = expected['aspect']
    assert actual.get('aspect') == kind, 'observation aspect differs'
    a, e = actual['value'], expected['value']
    if kind == 'render':
        compare_raster(a, e)
    elif kind in ('geometry', 'positions', 'font-sizes'):
        numeric(a, e, 1.5 if kind == 'positions' else .6)
    elif kind == 'alpha':
        for key in e:
            numeric(a[key], e[key], .025)
    elif kind == 'text-colors':
        assert isinstance(a,list) and len(a)==len(e),'text color count differs'
        for actual_color,expected_color in zip(a,e):
            assert isinstance(actual_color,int) and 0<=actual_color<=0xffffff,'invalid RGB color'
            numeric([(actual_color>>shift)&255 for shift in (16,8,0)],
                    [(expected_color>>shift)&255 for shift in (16,8,0)],2)
    else:
        assert a == e, f'{kind} differs: {str(a)[:250]} != {str(e)[:250]}'
