"""Program observations of the drawing and of product files, and their tolerant comparison.

Reads go through the runtime only: the api operation (getSvgString, loadFromString)
for the drawing, snapshot + download for product files. Observations are
projections of svgmodel.Doc that ignore representation details (see svgmodel);
'raw' observations exist for the few points whose subject is SVG-edit's own
rewriting of attributes.
"""
import base64
import io
import json
import math
import re
import sys

import svgmodel as M

sys.path.insert(0, '/opt/verifier-lib')

DEFAULT_PAINT = {'fill': '#000000', 'stroke': 'none', 'stroke-width': 1.0, 'opacity': 1.0, 'fill-opacity': 1.0,
                 'stroke-opacity': 1.0, 'stroke-dasharray': 'none', 'stroke-linejoin': 'miter',
                 'stroke-linecap': 'butt'}
INHERITED = ('fill', 'stroke', 'stroke-width', 'fill-opacity', 'stroke-opacity', 'stroke-dasharray',
             'stroke-linejoin', 'stroke-linecap')
FONT_DEFAULT = {'font-family': 'serif', 'font-size': 16.0, 'font-weight': 400, 'font-style': 'normal',
                'text-anchor': 'start', 'text-decoration': 'none'}
WEIGHTS = {'normal': 400, 'bold': 700, 'bolder': 700, 'lighter': 300}
HEX = re.compile(r'#[0-9a-f]{6}')


class Reader:
    """The drawing of the current checkpoint, read once through the runtime api operation."""

    def __init__(self, broker):
        self.broker = broker
        self.cache = None

    def reset(self):
        self.cache = None

    def source(self):
        if self.cache is None:
            answer = self.broker.call({'op': 'api', 'method': 'getSvgString'})
            if 'svg' not in answer:
                raise AssertionError('getSvgString gave no drawing: ' + str(answer)[:200])
            self.cache = answer['svg']
        return self.cache

    def doc(self):
        return M.Doc(self.source())


# -- projections -------------------------------------------------------------------------------------
def effective_paint(doc, el):
    """Paint after inheritance from ancestors, with SVG initial values for anything unset."""
    chain = []
    node = el
    while node is not None and node is not doc.root:
        chain.append(node)
        node = doc.parent.get(node)
    values = dict(DEFAULT_PAINT)
    opacity = 1.0
    for node in reversed(chain):
        a = M.attrs(node)
        for key in INHERITED:
            if key in a and a[key] not in ('inherit', ''):
                values[key] = a[key]
        if 'opacity' in a and M.num(a['opacity']) is not None:
            opacity *= M.num(a['opacity'])
    out = {}
    for key, value in values.items():
        if key in ('fill', 'stroke'):
            out[key] = M.colour(value) if isinstance(value, str) else value
        elif key == 'stroke-dasharray':
            text = str(value).strip().lower()
            out[key] = 'none' if text in ('none', '', '0') else ','.join(
                M.NUMBER.findall(text)) if M.NUMBER.findall(text) else text
        elif key in ('stroke-linejoin', 'stroke-linecap'):
            out[key] = str(value).strip().lower()
        elif key != 'opacity':
            number = M.num(value) if isinstance(value, str) else value
            out[key] = M.r(number, 3) if number is not None else str(value)
    out['opacity'] = M.r(opacity, 3)
    if out.get('stroke-width') == 0:  # a zero-width stroke draws nothing
        out['stroke'] = 'none'
    if out['stroke'] == 'none':  # stroke details are invisible without a stroke
        for key in ('stroke-width', 'stroke-opacity', 'stroke-dasharray', 'stroke-linejoin', 'stroke-linecap'):
            out.pop(key, None)
    if out['fill'] == 'none':
        out.pop('fill-opacity', None)
    return out


def paint_ref(doc, value):
    """A url(#id) paint as the referenced server's content (ids are not compared)."""
    match = re.fullmatch(r'url\(\s*#([^)]+)\)', value or '')
    if not match:
        return value
    el = doc.ids.get(match.group(1).strip())
    if el is None:
        return 'url(missing)'
    return {'server': M.name(el), 'attrs': {k: server_value(k, v) for k, v in sorted(M.attrs(el).items()) if k != 'id'},
            'stops': [{k: server_value(k, v) for k, v in sorted(M.attrs(s).items()) if k != 'id'}
                      for s in el if M.name(s) == 'stop']}


def server_value(key, value):
    """A paint-server attribute in comparable form: colours normalised, plain numbers as numbers."""
    if key in ('stop-color', 'color', 'flood-color', 'lighting-color'):
        return M.colour(value)
    if M.NUMBER.fullmatch(value.strip()):
        return M.r(float(value), 4)
    return value.strip()


def referenced(doc, value):
    match = re.fullmatch(r'\s*url\(\s*#([^)]+?)\s*\)\s*', value or '')
    return doc.ids.get(match.group(1)) if match else None


def gradient_chain(doc, el):
    """A gradient's attributes and stops, following href inheritance."""
    attrs, stops, seen = {}, None, set()
    while el is not None and id(el) not in seen:
        seen.add(id(el))
        a = M.attrs(el)
        for key, value in a.items():
            attrs.setdefault(key, value)
        if stops is None:
            found = [s for s in el if M.name(s) == 'stop']
            stops = found or None
        el = doc.ids.get((a.get('href') or '').lstrip('#')) if a.get('href', '').startswith('#') else None
    return attrs, stops or []


def paint_server(doc, value):
    """A fill's paint server: its kind, geometry and spread (gradient units' defaults applied)."""
    el = referenced(doc, value)
    if el is None:
        return {'kind': 'colour', 'value': M.colour(value) if value else None}
    kind = M.name(el)
    attrs, stops = gradient_chain(doc, el)
    out = {'kind': kind, 'spread': (attrs.get('spreadMethod') or 'pad').strip(), 'stops': len(stops)}
    if kind == 'linearGradient':
        defaults = {'x1': 0.0, 'y1': 0.0, 'x2': 1.0, 'y2': 0.0}
    elif kind == 'radialGradient':
        defaults = {'cx': 0.5, 'cy': 0.5, 'r': 0.5}
    else:
        return out
    for key, default in defaults.items():
        value = attrs.get(key)
        if value is not None and value.strip().endswith('%'):
            number = float(value.strip()[:-1]) / 100
        else:
            number = M.num(value, default)
        out[key] = M.r(number, 3)
    return out


def gradient_geometry(doc, el):
    """Where the element's fill gradient lies in document coordinates, however it is written: a linear gradient's
    end points, a radial gradient's centre, focal point and horizontal and vertical radius (bounding-box units
    resolved against the element's own box, gradientTransform and the element's transforms applied)."""
    grad = referenced(doc, M.attrs(el).get('fill'))
    if grad is None or M.name(grad) not in ('linearGradient', 'radialGradient'):
        return None
    attrs, _ = gradient_chain(doc, grad)
    user = (attrs.get('gradientUnits') or '').strip() == 'userSpaceOnUse'
    m = M.ctm(doc, el)
    if not user:
        shape = M.outline(doc, el, M.IDENTITY)
        pts = shape.get('points') or [seg[i:i + 2] for seg in shape.get('path', []) for i in range(1, len(seg) - 1, 2)
                                      if seg and seg[0] not in ('A', 'Z')]
        if not pts:
            return None
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        m = M.multiply(m, (max(xs) - min(xs), 0, 0, max(ys) - min(ys), min(xs), min(ys)))
    m = M.multiply(m, M.parse_transform(attrs.get('gradientTransform') or ''))

    def value(key, default, axis):
        text = attrs.get(key)
        if text is not None and text.strip().endswith('%'):
            share = float(text.strip()[:-1]) / 100
            return share if not user else M.length(doc, text, axis, default)
        return M.num(text, default)

    def at(x, y):
        px, py = M.apply(m, x, y)
        return [M.r(px, 1), M.r(py, 1)]
    if M.name(grad) == 'linearGradient':
        x2 = value('x2', None, 'x')
        if x2 is None:
            x2 = 1.0 if not user else doc.size()[0]
        return {'kind': 'linear', 'from': at(value('x1', 0.0, 'x'), value('y1', 0.0, 'y')),
                'to': at(x2, value('y2', 0.0, 'y'))}
    half = 0.5 if not user else None
    cx = value('cx', half if half is not None else doc.size()[0] / 2, 'x')
    cy = value('cy', half if half is not None else doc.size()[1] / 2, 'y')
    radius = value('r', half if half is not None else M.length(doc, '50%', 'xy'), 'xy')
    centre = M.apply(m, cx, cy)
    ex, ey = M.apply(m, cx + radius, cy), M.apply(m, cx, cy + radius)
    return {'kind': 'radial', 'centre': at(cx, cy), 'focus': at(value('fx', cx, 'x'), value('fy', cy, 'y')),
            'radii': [M.r(math.hypot(ex[0] - centre[0], ex[1] - centre[1]), 1),
                      M.r(math.hypot(ey[0] - centre[0], ey[1] - centre[1]), 1)]}


def blur_of(doc, value):
    el = referenced(doc, value)
    if el is None or M.name(el) != 'filter':
        return None
    blur = next((c for c in el.iter() if M.name(c) == 'feGaussianBlur'), None)
    if blur is None:
        return {'filter': True, 'deviation': None}
    numbers = [float(v) for v in M.NUMBER.findall(M.attrs(blur).get('stdDeviation') or '')]
    return {'filter': True, 'deviation': M.r(numbers[0], 2) if numbers else None}


def marker_of(doc, value):
    """A marker's identity: SVG-edit's marker type when recorded, else the kinds of its drawing."""
    el = referenced(doc, value)
    if el is None:
        return None
    a = M.attrs(el)
    return a.get('se_type') or '+'.join(M.name(c) for c in el if isinstance(c.tag, str))


def effective_font(el):
    a = M.attrs(el)
    out = dict(FONT_DEFAULT)
    for key in FONT_DEFAULT:
        if key in a:
            value = a[key].strip().lower()
            if key == 'font-size':
                out[key] = M.r(M.num(value), 2) if M.num(value) is not None else value
            elif key == 'font-weight':
                out[key] = WEIGHTS.get(value, int(value) if value.isdigit() else value)
            elif key == 'font-family':
                out[key] = ','.join(p.strip().strip('\'"') for p in value.split(','))
            else:
                out[key] = value
    for key in ('letter-spacing', 'word-spacing', 'textLength'):
        if key in a and M.num(a[key]) is not None:
            out[key] = M.r(M.num(a[key]), 2)
    if 'lengthAdjust' in a:
        out['lengthAdjust'] = a['lengthAdjust'].strip()
    return out


def project(doc, el, parts):
    kind = M.name(el)
    out = {'kind': kind}
    if kind in M.CONTAINERS:
        if 'children' in parts or 'outline' in parts:
            out['children'] = [project(doc, c, parts) for c in el if M.name(c) in M.GRAPHIC + M.CONTAINERS]
        if 'title' in parts:
            out['title'] = next((M.text_content(c) for c in el if M.name(c) == 'title'), None)
        if kind == 'a' and 'href' in parts:
            out['href'] = M.attrs(el).get('href')
        return out
    if 'outline' in parts:
        out.update(M.outline(doc, el))
    if 'shape' in parts:
        shape = M.outline(doc, el)
        a = M.attrs(el)
        facts = {}
        if kind == 'rect':
            w, h = M.num(a.get('width'), 0), M.num(a.get('height'), 0)
            facts['square'] = abs(w - h) < 0.5
            facts['rounded'] = (M.num(a.get('rx'), 0) or 0) > 0
        elif kind == 'ellipse':
            facts['circular'] = abs(M.num(a.get('rx'), 0) - M.num(a.get('ry'), 0)) < 0.5
        elif kind == 'path':
            segments = M.parse_path(a.get('d'))
            facts['closed'] = any(cmd == 'Z' for cmd, _ in segments)
            facts['curved'] = any(cmd in ('C', 'Q', 'A') for cmd, _ in segments)
            facts['subpaths'] = sum(1 for cmd, _ in segments if cmd == 'M')
            facts['nodes'] = sum(1 for cmd, _ in M.clean_segments(segments) if cmd != 'Z')
        elif kind in ('polygon', 'polyline'):
            # Distinct vertices: repeated points (a closing repeat, SVG-edit's star repeating its first corners)
            # are not extra corners.
            facts['points'] = len({(round(x, 1), round(y, 1)) for x, y in M.points_list(a.get('points'))})
        out['shape'] = facts
    if 'corners' in parts:
        # A polygon's geometry whatever corner it is written from, in either direction, with repeats or not.
        out['corners'] = M.corners(M.outline(doc, el).get('points') or [])
    if 'size' in parts or 'ends' in parts:
        shape = M.outline(doc, el)
        pts = shape.get('points') or [seg[i:i + 2] for seg in shape.get('path', []) for i in range(1, len(seg) - 1, 2)
                                      if seg and seg[0] != 'A' and seg[0] != 'Z'] or ([shape['anchor']] if 'anchor' in shape else [])
        if 'size' in parts and pts:
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            out['size'] = [M.r(max(xs) - min(xs)), M.r(max(ys) - min(ys))]
        if 'ends' in parts and pts:
            out['ends'] = [pts[0], pts[-1]]
    if 'server' in parts:
        out['server'] = paint_server(doc, M.attrs(el).get('fill'))
    if 'vector' in parts:
        out['vector'] = gradient_geometry(doc, el)
    if 'blur' in parts:
        out['blur'] = blur_of(doc, M.attrs(el).get('filter'))
    if 'markers' in parts:
        out['markers'] = {pos: marker_of(doc, M.attrs(el).get('marker-' + pos)) for pos in ('start', 'mid', 'end')}
    if 'title' in parts:
        out['title'] = next((M.text_content(c) for c in el if M.name(c) == 'title'), None)
    if 'paint' in parts:
        paint = effective_paint(doc, el)
        for key in ('fill', 'stroke'):
            if isinstance(paint.get(key), str) and paint[key].startswith('url('):
                paint[key] = paint_ref(doc, M.attrs(el).get(key) or paint[key])
        out['paint'] = paint
    if 'text' in parts and kind == 'text':
        out['text'] = M.text_content(el)
    if 'font' in parts and kind == 'text':
        out['font'] = effective_font(el)
    if 'href' in parts and kind in ('image', 'use'):
        href = M.attrs(el).get('href') or ''
        out['href'] = 'data:' + href.split(';')[0][5:] if href.startswith('data:') else href
    return out


def top_level(doc):
    """Top-level drawable elements in order: the children of every layer and anything drawn outside a layer."""
    out, layers = [], doc.layers()
    for el in doc.root:
        if any(el is layer for layer in layers):
            out += [c for c in el if M.name(c) in M.GRAPHIC + M.CONTAINERS]
        elif M.name(el) in M.GRAPHIC + M.CONTAINERS:
            out.append(el)
    return out


def fixture_ids(fixture):
    try:
        return set(M.Doc(fixture).ids)
    except AssertionError:
        return set()


def raw(doc, el, names):
    a = M.attrs(el)
    raw_attrs = {}
    for key, value in el.attrib.items():
        if key.startswith('{'):
            ns, local = key[1:].split('}', 1)
            key = M.PREFIXES.get(ns, '{' + ns + '}') + local
        raw_attrs[key] = value
    out = {}
    for key in names:
        if key == 'transform':
            text = raw_attrs.get('transform')
            out[key] = None if not text else [M.r(v, 4) for v in M.parse_transform(text)]
        elif key == 'transform-kind':
            text = raw_attrs.get('transform') or ''
            out[key] = sorted(set(re.findall(r'(matrix|translate|scale|rotate|skewX|skewY)', text)))
        elif key == 'd':
            out[key] = M.path_points(M.parse_path(raw_attrs.get('d')), M.IDENTITY) if 'd' in raw_attrs else None
        elif key == 'exact:d':
            # Absolute path coordinates as written (unrounded, to 5 decimals), relative and absolute commands alike.
            out[key] = [[seg[0]] + [round(v, 5) for v in seg[1:]] for seg in M.path_points(
                M.parse_path(raw_attrs.get('d')), M.IDENTITY, digits=5)] if 'd' in raw_attrs else None
        elif key == 'points':
            out[key] = [[M.r(x), M.r(y)] for x, y in M.points_list(raw_attrs.get('points'))] \
                if 'points' in raw_attrs else None
        elif key.startswith('text:'):
            out[key] = raw_attrs.get(key[5:])
        elif key.startswith('link:'):
            # A reference as the drawing resolves it (href, or xlink:href without href), full value.
            out[key] = a.get(key[5:])
        elif key.startswith('colour:'):
            # A colour as written, normalised (#rrggbb, rgb() and names compare equal).
            out[key] = M.colour(raw_attrs.get(key[7:]))
        elif key.startswith('length:'):
            out[key] = M.r(M.num(raw_attrs.get(key[7:])), 4)
        elif key.startswith('weight:'):
            value = (raw_attrs.get(key[7:]) or '').strip().lower()
            out[key] = WEIGHTS.get(value, int(value) if value.isdigit() else value or None)
        elif key.startswith('decimal:'):
            # Whether a number is written in plain decimal notation (no exponent, no plus sign), and its value.
            value = (raw_attrs.get(key[8:]) or '').strip()
            out[key] = {'plain': bool(re.fullmatch(r'-?\d+(?:\.\d+)?', value)),
                        'value': M.r(float(value), 4) if M.NUMBER.fullmatch(value) else None}
        elif key.startswith('numbers:'):
            # Every number of a list attribute, unrounded (to 5 decimals).
            out[key] = [round(float(v), 5) for v in M.NUMBER.findall(raw_attrs.get(key[8:]) or '')]
        else:
            value = raw_attrs.get(key)
            if value is not None and re.fullmatch(r'\s*[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?\s*', value):
                out[key] = M.r(float(value), 4)
            else:
                out[key] = value
    return out


# -- observation dispatcher ----------------------------------------------------------------------------
def observe(ctx, cp, spec):
    reader = ctx.state['reader']
    kind = spec['type']
    if kind == 'multi':
        return {name: observe(ctx, cp, sub) for name, sub in spec['checks'].items()}
    if kind == 'converted':
        doc = reader.doc()
        x, y = spec['point']
        found = None
        for el in top_level(doc):
            box = bounds(doc, el)
            if box and box[0] - 1 <= x <= box[2] + 1 and box[1] - 1 <= y <= box[3] + 1:
                found = el
        if found is None:
            raise AssertionError('no element covers the point ' + str(spec['point']))
        out = {'kind': M.name(found), 'bounds': [M.r(v, 1) for v in bounds(doc, found)]}
        if M.name(found) == 'path':
            segments = M.parse_path(M.attrs(found).get('d'))
            out['closed'] = any(cmd == 'Z' for cmd, _ in segments)
        return out
    if kind == 'box':
        doc = reader.doc()
        box = bounds(doc, doc.by_id(spec['id']))
        if box is None:
            raise AssertionError('the element has no measurable outline')
        x0, y0, x1, y1 = box
        facets = {'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0, 'cx': (x0 + x1) / 2, 'cy': (y0 + y1) / 2,
                  'rx': (x1 - x0) / 2, 'ry': (y1 - y0) / 2}
        return {spec['facet']: M.r(facets[spec['facet']], 2)}
    if kind == 'ends':
        doc = reader.doc()
        shape = M.outline(doc, doc.by_id(spec['id']))
        pts = shape.get('points') or []
        if len(pts) < 2:
            raise AssertionError('the element has no end points')
        return {spec['facet']: pts[0] if spec['facet'] == 'start' else pts[-1]}
    if kind == 'font':
        doc = reader.doc()
        font = effective_font(doc.by_id(spec['id']))
        return {spec['facet']: font.get(spec['facet'])}
    if kind == 'root-attributes':
        doc = reader.doc()
        names = set()
        for key in doc.root.attrib:
            if key.startswith('{'):
                ns, local = key[1:].split('}', 1)
                key = M.PREFIXES.get(ns, '{' + ns + '}') + local
            names.add(key)
        return {'kept': sorted(k for k in spec['names'] if k in names),
                'dropped': sorted(k for k in spec['names'] if k not in names)}
    if kind == 'textcontent':
        return {'text': M.text_content(reader.doc().by_id(spec['id']))}
    if kind == 'ids-present':
        doc = reader.doc()
        return {'present': sorted(i for i in spec['ids'] if i in doc.ids),
                'absent': sorted(i for i in spec['ids'] if i not in doc.ids)}
    if kind == 'child-tags':
        doc = reader.doc()
        return {'children': [[M.name(c), M.text_content(c)] for c in doc.by_id(spec['id'])]}
    if kind == 'element':
        doc = reader.doc()
        return project(doc, doc.by_id(spec['id']), spec.get('parts', ('outline', 'paint')))
    if kind == 'new':
        doc = reader.doc()
        known = fixture_ids(cp.get('fixture_svg', ''))
        new = [el for el in top_level(doc) if el.get('id') not in known]
        index = spec.get('index', -1)
        if not new or not -len(new) <= index < len(new):
            raise AssertionError(f'expected a new element (index {index}); found {len(new)} new elements')
        out = project(doc, new[index], spec.get('parts', ('outline', 'paint')))
        out['new_elements'] = len(new)
        return out
    if kind == 'raw':
        doc = reader.doc()
        if 'id' in spec:
            el = doc.by_id(spec['id'])
        else:
            known = fixture_ids(cp.get('fixture_svg', ''))
            new = [el for el in top_level(doc) if el.get('id') not in known]
            if not new:
                raise AssertionError('expected a new element')
            el = new[spec.get('index', -1)]
        return {'kind': M.name(el), **raw(doc, el, spec['attrs'])}
    if kind == 'children':
        doc = reader.doc()
        parent = doc.by_id(spec['id']) if 'id' in spec else doc.root
        return {'children': [project(doc, c, spec.get('parts', ('outline',))) for c in parent
                             if M.name(c) in M.GRAPHIC + M.CONTAINERS]}
    if kind == 'top':
        doc = reader.doc()
        known = fixture_ids(cp.get('fixture_svg', ''))
        items = []
        for el in top_level(doc):
            entry = project(doc, el, spec.get('parts', ('outline',)))
            if spec.get('ids', True):
                entry['id'] = el.get('id') if el.get('id') in known else 'new'
            items.append(entry)
        return {'top': items}
    if kind == 'layers':
        doc = reader.doc()
        known = fixture_ids(cp.get('fixture_svg', ''))
        out = []
        for layer in doc.layers():
            a = M.attrs(layer)
            entry = {'title': next((M.text_content(c) for c in layer if M.name(c) == 'title'), None),
                     'hidden': a.get('display') == 'none' or a.get('visibility') == 'hidden',
                     'content': [el.get('id') if el.get('id') in known else M.name(el)
                                 for el in layer if M.name(el) in M.GRAPHIC + M.CONTAINERS]}
            if spec.get('class'):
                entry['class'] = a.get('class')
            out.append(entry)
        return {'layers': out}
    if kind == 'root':
        doc = reader.doc()
        a = M.attrs(doc.root)
        out = {'width': M.r(M.num(a.get('width')), 2), 'height': M.r(M.num(a.get('height')), 2)}
        if spec.get('viewBox'):
            out['viewBox'] = [M.r(float(v), 2) for v in M.NUMBER.findall(a.get('viewBox') or '')] or None
        return out
    if kind == 'root-units':
        # The document size as written: number and unit of the root's width and height.
        doc = reader.doc()
        out = {}
        for key in ('width', 'height'):
            match = re.fullmatch(r'\s*([-+]?(?:\d+\.?\d*|\.\d+))\s*([a-z%]*)\s*', doc.root.get(key) or '')
            out[key] = [M.r(float(match.group(1)), 2), match.group(2) or 'px'] if match else None
        return out
    if kind == 'root-children':
        doc = reader.doc()
        out = {}
        for tag in spec['tags']:
            el = next((c for c in doc.root if M.name(c) == tag), None)
            out[tag] = None if el is None else M.text_content(el)
        return out
    if kind == 'present':
        doc = reader.doc()
        names = set(M.kinds(doc))
        return {'present': sorted(k for k in spec['kinds'] if k in names),
                'absent': sorted(k for k in spec['kinds'] if k not in names)}
    if kind == 'attributes':
        # Which of the listed attributes an element carries (raw names, href unified, style kept as style).
        doc = reader.doc()
        el = doc.by_id(spec['id'])
        names = set()
        for key in el.attrib:
            if key.startswith('{'):
                ns, local = key[1:].split('}', 1)
                key = M.PREFIXES.get(ns, '{' + ns + '}') + local
            names.add('href' if key in ('xlink:href', 'href') else key)
        out = {'kind': M.name(el), 'kept': sorted(k for k in spec['names'] if k in names),
               'dropped': sorted(k for k in spec['names'] if k not in names)}
        if spec.get('values'):
            a = M.attrs(el)
            out['values'] = {k: (M.r(M.num(a[k]), 2) if M.num(a.get(k)) is not None else a[k])
                             for k in spec['values'] if k in a}
        return out
    if kind == 'ids':
        doc = reader.doc()
        drawable = [el for el in doc.root.iter() if M.name(el) in M.GRAPHIC + M.CONTAINERS + ('tspan',)
                    and el is not doc.root and not (M.name(el) == 'g' and el in doc.layers())]
        ids = [el.get('id') for el in drawable]
        out = {'all_have_ids': all(ids), 'unique': len([i for i in ids if i]) == len(set(i for i in ids if i))}
        if spec.get('kept'):
            out['kept'] = sorted(i for i in spec['kept'] if i in doc.ids)
        facets = spec.get('facets')
        return {k: v for k, v in out.items() if not facets or k in facets}
    if kind == 'text':
        doc = reader.doc()
        known = fixture_ids(cp.get('fixture_svg', ''))
        texts = [el for el in doc.root.iter() if M.name(el) == 'text']
        if 'id' in spec:
            el = doc.by_id(spec['id'])
        else:
            new = [el for el in texts if el.get('id') not in known]
            if not new:
                raise AssertionError('no new text element')
            el = new[-1]
        return project(doc, el, spec.get('parts', ('text',)))
    if kind == 'document':
        doc = reader.doc()
        a = M.attrs(doc.root)
        return {'size': [M.r(M.num(a.get('width')), 2), M.r(M.num(a.get('height')), 2)],
                'layers': [{'title': next((M.text_content(c) for c in layer if M.name(c) == 'title'), None),
                            'content': [project(doc, el, ('outline', 'paint', 'text'))
                                        for el in layer if M.name(el) in M.GRAPHIC + M.CONTAINERS]}
                           for layer in doc.layers()]}
    if kind == 'count':
        doc = reader.doc()
        return {'top_level': len(top_level(doc))}
    if kind == 'extent':
        # The newest object by the area its shapes cover, whatever element writes it (instance, group, drawing).
        doc = reader.doc()
        known = fixture_ids(cp.get('fixture_svg', ''))
        new = [el for el in top_level(doc) if el.get('id') not in known]
        if not new:
            raise AssertionError('expected a new element')
        box = drawn_box(doc, new[-1])
        if box is None:
            raise AssertionError('the new element covers no measurable area')
        return {'extent': [M.r(v) for v in box], 'new_elements': len(new)}
    if kind == 'leaves':
        # Every drawn shape by its effective outline, whatever groups or links wrap it.
        doc = reader.doc()
        return {'leaves': [project(doc, el, spec.get('parts', ('outline',))) for el in leaf_shapes(doc)]}
    if kind == 'load':
        before = reader.source()
        answer = ctx.broker.call({'op': 'api', 'method': 'loadFromString', 'svg': spec['svg']})
        reader.reset()
        after = reader.source()
        return {'loaded': bool(answer.get('loaded')), 'drawing_unchanged': project_all(before) == project_all(after)}
    if kind == 'download':
        return observe_download(ctx, spec)
    raise ValueError('unknown check type ' + kind)


def bounds(doc, el, m=None):
    """Box of an element's outline in document coordinates: its corners, or a path's end points and the turning
    points of its curves and arcs (control points do not count)."""
    m = M.ctm(doc, el) if m is None else m
    if M.name(el) == 'path':
        pts = M.path_extremes(M.parse_path(M.attrs(el).get('d')), m)
    else:
        pts = M.outline(doc, el, m).get('points')
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def drawn_box(doc, el, m=None):
    """The box an object's shapes cover in document coordinates, whatever element writes it: a group or link by its
    parts, an instance (use) or nested drawing (svg) by the shapes it shows in its viewport. Texts are left out."""
    m = M.ctm(doc, el) if m is None else m
    kind, a = M.name(el), M.attrs(el)
    if kind in ('g', 'a', 'switch'):
        boxes = [drawn_box(doc, c, child_matrix(m, c)) for c in el]
    elif kind in ('use', 'svg'):
        ref = doc.ids.get((a.get('href') or '').lstrip('#')) if kind == 'use' else el
        if ref is None:
            return None
        if kind == 'use':
            m = M.multiply(m, (1, 0, 0, 1, M.num(a.get('x'), 0), M.num(a.get('y'), 0)))
        if M.name(ref) in ('symbol', 'svg'):
            ra = M.attrs(ref)
            width = M.num(a.get('width')) if kind == 'use' and M.num(a.get('width')) else M.num(ra.get('width'))
            height = M.num(a.get('height')) if kind == 'use' and M.num(a.get('height')) else M.num(ra.get('height'))
            inner = M.multiply(m, viewbox_matrix(ra, width, height))
            boxes = [drawn_box(doc, c, child_matrix(inner, c)) for c in ref]
        else:
            boxes = [drawn_box(doc, ref, child_matrix(m, ref))]
    elif kind in M.GRAPHIC and kind != 'text':
        boxes = [bounds(doc, el, m)]
    else:
        return None
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def child_matrix(m, el):
    """The transform of a child element given its parent's: a nested drawing's offset, then its own transform."""
    a = M.attrs(el)
    if M.name(el) == 'svg':
        m = M.multiply(m, (1, 0, 0, 1, M.num(a.get('x'), 0), M.num(a.get('y'), 0)))
    return M.multiply(m, M.parse_transform(a.get('transform')))


def viewbox_matrix(a, width, height):
    """The mapping of a viewBox into a width x height viewport (preserveAspectRatio, default xMidYMid meet)."""
    box = [float(v) for v in M.NUMBER.findall(a.get('viewBox') or '')]
    if len(box) != 4 or box[2] <= 0 or box[3] <= 0 or not width or not height:
        return M.IDENTITY
    align, *mode = (a.get('preserveAspectRatio') or 'xMidYMid meet').split()
    if align == 'none':
        sx, sy = width / box[2], height / box[3]
    else:
        sx = sy = (max if mode and mode[0] == 'slice' else min)(width / box[2], height / box[3])
    tx, ty = -box[0] * sx, -box[1] * sy
    if 'xMid' in align:
        tx += (width - box[2] * sx) / 2
    elif 'xMax' in align:
        tx += width - box[2] * sx
    if 'YMid' in align:
        ty += (height - box[3] * sy) / 2
    elif 'YMax' in align:
        ty += height - box[3] * sy
    return (sx, 0.0, 0.0, sy, tx, ty)


def leaf_shapes(doc):
    """The drawn shapes in document order with layers, groups and links unwrapped (an instance is a shape)."""
    out = []

    def walk(el):
        if M.name(el) in M.CONTAINERS:
            for c in el:
                walk(c)
        elif M.name(el) in M.GRAPHIC:
            out.append(el)
    for el in top_level(doc):
        walk(el)
    return out


def project_all(text):
    doc = M.Doc(text)
    return [project(doc, el, ('outline', 'paint', 'text')) for el in top_level(doc)]


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
    data = base64.b64decode(item['body_base64'])
    files[key] = (item['filename'], data)
    return files[key]


def observe_download(ctx, spec):
    kind = spec['format']
    if kind == 'svg':
        name, data = take_download(ctx, ('.svg',))
        text = data.decode('utf-8', errors='replace')
        out = {}
        parts = spec.get('parts', ('declaration', 'document'))
        if 'name' in parts:
            out['name'] = name
        if 'declaration' in parts:
            out['declaration'] = text.lstrip().startswith('<?xml')
        doc = M.Doc(text)
        if 'document' in parts:
            out['document'] = [project(doc, el, ('outline', 'paint', 'text')) for el in top_level(doc)]
        if 'images' in parts:
            out['images'] = [('data:' + (M.attrs(el).get('href') or '').split(';')[0][5:]
                              if (M.attrs(el).get('href') or '').startswith('data:') else 'reference')
                             for el in doc.root.iter() if M.name(el) == 'image']
        return out
    if kind in ('png', 'jpeg', 'bmp', 'webp'):
        # The newest exported image, whatever its encoding (a browser may encode one format as another).
        name, data = take_download(ctx, ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif'))
        return image_facts(data, spec)
    if kind == 'pdf':
        name, data = take_download(ctx, ('.pdf',))
        return pdf_facts(data, spec)
    raise ValueError('unknown download format ' + kind)


def image_facts(data, spec):
    from PIL import Image
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise AssertionError('the exported file is not a readable image: ' + type(exc).__name__) from None
    out = {}
    parts = spec.get('parts', ('format', 'size', 'samples'))
    if 'format' in parts:
        out['format'] = image.format
    if 'size' in parts:
        out['size'] = list(image.size)
    rgba = image.convert('RGBA')
    if 'samples' in parts:
        out['samples'] = [list(rgba.getpixel((int(x), int(y)))) for x, y in spec['points']]
    if 'quality' in parts:
        tables = getattr(image, 'quantization', None) or {}
        luma = tables.get(0)
        out['quality'] = estimate_jpeg_quality(luma) if luma else None
    if 'lossless' in parts:
        out['lossless'] = b'VP8L' in data[:64]
    return out


def estimate_jpeg_quality(table):
    """libjpeg quality from the luminance quantisation table (inverse of its scaling)."""
    base = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56, 14, 17,
            22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92, 49, 64, 78, 87,
            103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]
    values = list(table)
    ratios = [100.0 * v / b for v, b in zip(values, base) if b]
    scale = sorted(ratios)[len(ratios) // 2]
    quality = (200 - scale) / 2 if scale <= 100 else 5000 / scale
    return int(round(max(1, min(100, quality)) / 5.0) * 5)


def pdf_facts(data, spec):
    if not data.startswith(b'%PDF-'):
        raise AssertionError('the exported file is not a PDF')
    text = data.decode('latin-1')
    out = {'pdf': True}
    parts = spec.get('parts', ('pages', 'size', 'title', 'image'))
    if 'pages' in parts:
        out['pages'] = len(re.findall(r'/Type\s*/Page(?!s)', text))
    if 'size' in parts:
        box = re.search(r'/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]', text)
        out['size'] = [M.r(float(box.group(3)) - float(box.group(1)), 1), M.r(float(box.group(4)) - float(box.group(2)), 1)] \
            if box else None
    if 'title' in parts:
        title = re.search(r'/Title\s*\((.*?)(?<!\\)\)', text, re.S)
        out['title'] = title.group(1) if title else None
    if 'image' in parts:
        image = re.search(r'/Subtype\s*/Image.*?/Width\s+(\d+).*?/Height\s+(\d+)', text, re.S) or \
            re.search(r'/Width\s+(\d+).*?/Height\s+(\d+).*?/Subtype\s*/Image', text, re.S)
        out['image'] = [int(image.group(1)), int(image.group(2))] if image else None
    return out


# -- comparison ----------------------------------------------------------------------------------------
def compare(actual, expected, tol, path='observation'):
    """Structural equality with numeric tolerance; AssertionError names the first difference."""
    if isinstance(expected, str) and isinstance(actual, str) and HEX.fullmatch(expected) and HEX.fullmatch(actual):
        # Colour-picker conversions round or truncate a channel either way; one unit per channel is the same colour.
        if any(abs(int(actual[i:i + 2], 16) - int(expected[i:i + 2], 16)) > 1 for i in (1, 3, 5)):
            raise AssertionError(f'{path}: expected {json.dumps(expected)}, got {json.dumps(actual)}')
        return
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if actual != expected:
            raise AssertionError(f'{path}: expected {json.dumps(expected)[:120]}, got {json.dumps(actual)[:120]}')
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
        extra = sorted(set(actual) - set(expected))
        if missing or extra:
            raise AssertionError(f'{path}: keys differ (missing {missing[:5]}, unexpected {extra[:5]})')
        for key in expected:
            compare(actual[key], expected[key], tol, f'{path}.{key}')
        return
    raise AssertionError(f'{path}: unsupported value')
