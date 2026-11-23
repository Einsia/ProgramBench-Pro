"""Semantic model of an SVG drawing for program checks.

The drawing text (from svgEditor.svgCanvas.getSvgString() or a saved file) is
parsed and normalised so that equivalent representations compare equal:
attribute order, whitespace, number formatting, colour spelling, href versus
xlink:href, style declarations versus presentation attributes, relative versus
absolute path commands and attribute-versus-transform placement are all
normalised. Geometry is reported as the element's effective outline in document
coordinates (its own transform and its ancestors' applied).
"""
import math
import re
import xml.etree.ElementTree as ET

SVG = 'http://www.w3.org/2000/svg'
PREFIXES = {SVG: '', 'http://www.w3.org/1999/xlink': 'xlink:', 'http://www.w3.org/XML/1998/namespace': 'xml:',
            'http://www.w3.org/1999/xhtml': 'html:', 'http://www.w3.org/1998/Math/MathML': 'math:',
            'http://svg-edit.googlecode.com': 'se:'}
COLOURS = {'black': '#000000', 'white': '#ffffff', 'red': '#ff0000', 'lime': '#00ff00', 'green': '#008000',
           'blue': '#0000ff', 'yellow': '#ffff00', 'cyan': '#00ffff', 'aqua': '#00ffff', 'magenta': '#ff00ff',
           'fuchsia': '#ff00ff', 'gray': '#808080', 'grey': '#808080', 'silver': '#c0c0c0', 'maroon': '#800000',
           'olive': '#808000', 'navy': '#000080', 'purple': '#800080', 'teal': '#008080', 'orange': '#ffa500'}
UNITS = {'px': 1.0, '': 1.0, 'in': 96.0, 'cm': 96 / 2.54, 'mm': 96 / 25.4, 'pt': 96 / 72, 'pc': 16.0}
GRAPHIC = ('rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path', 'text', 'image', 'use',
           'foreignObject')
CONTAINERS = ('g', 'a', 'switch', 'svg')
PAINT = ('fill', 'stroke', 'stroke-width', 'opacity', 'fill-opacity', 'stroke-opacity', 'stroke-dasharray',
         'stroke-linejoin', 'stroke-linecap', 'fill-rule', 'stroke-miterlimit', 'stroke-dashoffset')
FONT = ('font-family', 'font-size', 'font-weight', 'font-style', 'text-anchor', 'text-decoration',
        'letter-spacing', 'word-spacing', 'textLength', 'lengthAdjust')
NUMBER = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')


class Doc:
    """A parsed drawing."""

    def __init__(self, text):
        if not isinstance(text, str) or not text.strip():
            raise AssertionError('the drawing is empty')
        try:
            self.root = ET.fromstring(text.encode('utf-8') if text.lstrip().startswith('<?xml') else text)
        except ET.ParseError as exc:
            raise AssertionError('the drawing is not well-formed XML: ' + str(exc)[:200]) from None
        if name(self.root) != 'svg':
            raise AssertionError('the drawing root is not an svg element')
        self.ids = {}
        for el in self.root.iter():
            ident = el.get('id')
            if ident and ident not in self.ids:
                self.ids[ident] = el
        self.parent = {child: parent for parent in self.root.iter() for child in parent}

    def by_id(self, ident):
        el = self.ids.get(ident)
        if el is None:
            raise AssertionError(f'no element with id {ident!r}')
        return el

    def size(self):
        """The document size in user units (the viewBox when present)."""
        box = [float(v) for v in NUMBER.findall(self.root.get('viewBox') or '')]
        if len(box) == 4 and box[2] > 0 and box[3] > 0:
            return box[2], box[3]
        return num(self.root.get('width'), 100.0) or 100.0, num(self.root.get('height'), 100.0) or 100.0

    def layers(self):
        """The drawing's layers: top-level groups marked class="layer" or carrying a title (SVG-edit's layers)."""
        return [el for el in self.root if name(el) == 'g' and ('layer' in (el.get('class') or '').split()
                                                                or any(name(c) == 'title' for c in el))]

    def content(self):
        """Drawable elements in document order inside the layers (or directly under the root)."""
        return [el for el in self.root.iter() if name(el) in GRAPHIC and not inside(self, el, ('defs', 'symbol',
                                                                                                   'marker', 'pattern',
                                                                                                   'clipPath', 'mask'))]


def name(el):
    tag = el.tag
    if not isinstance(tag, str):
        return ''
    if tag.startswith('{'):
        ns, local = tag[1:].split('}', 1)
        return PREFIXES.get(ns, '{' + ns + '}') + local
    return tag


def attrs(el):
    """Attributes with namespace prefixes, href unified, style declarations merged (style wins)."""
    out = {}
    for key, value in el.attrib.items():
        if key.startswith('{'):
            ns, local = key[1:].split('}', 1)
            key = PREFIXES.get(ns, '{' + ns + '}') + local
        out[key] = value.strip()
    if 'xlink:href' in out and 'href' not in out:
        out['href'] = out['xlink:href']
    out.pop('xlink:href', None)
    for decl in out.pop('style', '').split(';'):
        if ':' in decl:
            key, value = decl.split(':', 1)
            if key.strip():
                out[key.strip()] = value.strip()
    return out


def inside(doc, el, tags):
    parent = doc.parent.get(el)
    while parent is not None:
        if name(parent) in tags:
            return True
        parent = doc.parent.get(parent)
    return False


def num(value, default=None):
    """A length in px (absolute units converted), or default."""
    if value is None:
        return default
    match = re.fullmatch(r'\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-z%]*)\s*', str(value))
    if not match:
        return default
    unit = match.group(2)
    if unit not in UNITS:
        return default
    return float(match.group(1)) * UNITS[unit]


def length(doc, value, axis, default=None):
    """A length in px; a percentage refers to the document width (axis 'x'), height ('y') or normalised diagonal."""
    if isinstance(value, str) and value.strip().endswith('%'):
        try:
            share = float(value.strip()[:-1]) / 100
        except ValueError:
            return default
        w, h = doc.size()
        return share * (w if axis == 'x' else h if axis == 'y' else math.hypot(w, h) / math.sqrt(2))
    return num(value, default)


def r(value, digits=2):
    if value is None:
        return None
    value = round(float(value), digits)
    return 0.0 if value == 0 else value


def colour(value):
    """Normalised paint: #rrggbb, none, url:<summary>, or the raw lower-case value."""
    if value is None:
        return None
    v = value.strip().lower()
    if v in COLOURS:
        return COLOURS[v]
    if re.fullmatch(r'#[0-9a-f]{3}', v):
        return '#' + ''.join(c * 2 for c in v[1:])
    if re.fullmatch(r'#[0-9a-f]{6}', v):
        return v
    match = re.fullmatch(r'rgba?\(\s*([\d.]+%?)\s*,?\s*([\d.]+%?)\s*,?\s*([\d.]+%?)(?:\s*[,/]\s*([\d.]+%?))?\s*\)', v)
    if match:
        parts = []
        for x in match.groups()[:3]:
            parts.append(round(float(x[:-1]) * 2.55) if x.endswith('%') else round(float(x)))
        return '#' + ''.join(f'{min(255, max(0, p)):02x}' for p in parts)
    return v


# -- transforms --------------------------------------------------------------------------------------
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def multiply(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2, a * e2 + c * f2 + e,
            b * e2 + d * f2 + f)


def parse_transform(text):
    m = IDENTITY
    if not text:
        return m
    for kind, args in re.findall(r'(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)', text):
        v = [float(x) for x in NUMBER.findall(args)]
        if kind == 'matrix' and len(v) == 6:
            t = tuple(v)
        elif kind == 'translate' and v:
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif kind == 'scale' and v:
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif kind == 'rotate' and v:
            a = math.radians(v[0])
            t = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) >= 3:
                t = multiply(multiply((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif kind == 'skewX' and v:
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif kind == 'skewY' and v:
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            continue
        m = multiply(m, t)
    return m


def apply(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def ctm(doc, el):
    """Cumulative transform from the element's coordinates to document coordinates (root svg excluded)."""
    chain = []
    node = el
    while node is not None and node is not doc.root:
        chain.append(node)
        node = doc.parent.get(node)
    m = IDENTITY
    for node in reversed(chain):
        a = attrs(node)
        if name(node) == 'svg':  # nested svg viewport offset
            m = multiply(m, (1, 0, 0, 1, num(a.get('x'), 0), num(a.get('y'), 0)))
        m = multiply(m, parse_transform(a.get('transform')))
    return m


# -- path data ---------------------------------------------------------------------------------------
def parse_path(d):
    """Absolute segments [(cmd, [numbers])] with H/V as L, S as C, T as Q; arcs keep their parameters."""
    tokens = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|' + NUMBER.pattern, d or '')
    out, i, cmd = [], 0, None
    x = y = sx = sy = 0.0
    last_c = last_q = None

    def take(n):
        nonlocal i
        vals = []
        while len(vals) < n:
            if i >= len(tokens) or re.fullmatch(r'[A-Za-z]', tokens[i]):
                raise AssertionError('malformed path data')
            vals.append(float(tokens[i]))
            i += 1
        return vals

    while i < len(tokens):
        if re.fullmatch(r'[A-Za-z]', tokens[i]):
            cmd = tokens[i]
            i += 1
        elif cmd is None:
            raise AssertionError('malformed path data')
        rel = cmd.islower()
        c = cmd.upper()
        if c == 'Z':
            out.append(('Z', []))
            x, y = sx, sy
            last_c = last_q = None
            continue
        if c == 'M':
            nx, ny = take(2)
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            sx, sy = x, y
            out.append(('M', [x, y]))
            cmd = 'l' if rel else 'L'
            last_c = last_q = None
        elif c in 'LHV':
            if c == 'L':
                nx, ny = take(2)
                x, y = (x + nx, y + ny) if rel else (nx, ny)
            elif c == 'H':
                (nx,) = take(1)
                x = x + nx if rel else nx
            else:
                (ny,) = take(1)
                y = y + ny if rel else ny
            out.append(('L', [x, y]))
            last_c = last_q = None
        elif c in 'CS':
            if c == 'C':
                x1, y1, x2, y2, nx, ny = take(6)
                if rel:
                    x1, y1, x2, y2, nx, ny = x1 + x, y1 + y, x2 + x, y2 + y, nx + x, ny + y
            else:
                x2, y2, nx, ny = take(4)
                if rel:
                    x2, y2, nx, ny = x2 + x, y2 + y, nx + x, ny + y
                x1, y1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
            out.append(('C', [x1, y1, x2, y2, nx, ny]))
            last_c, last_q = (x2, y2), None
            x, y = nx, ny
        elif c in 'QT':
            if c == 'Q':
                x1, y1, nx, ny = take(4)
                if rel:
                    x1, y1, nx, ny = x1 + x, y1 + y, nx + x, ny + y
            else:
                nx, ny = take(2)
                if rel:
                    nx, ny = nx + x, ny + y
                x1, y1 = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
            out.append(('Q', [x1, y1, nx, ny]))
            last_q, last_c = (x1, y1), None
            x, y = nx, ny
        elif c == 'A':
            rx, ry, rot, large, sweep, nx, ny = take(7)
            if rel:
                nx, ny = nx + x, ny + y
            out.append(('A', [rx, ry, rot, large, sweep, nx, ny]))
            x, y = nx, ny
            last_c = last_q = None
    return out


def clean_segments(segments):
    """Path segments with a cubic whose control points sit on its own end points written as the straight segment it
    draws, and without a straight segment back to the sub-path's start right before Z (it is redundant)."""
    straight, pos, first = [], (0.0, 0.0), (0.0, 0.0)
    for cmd, vals in segments:
        if cmd == 'C' and all(abs(u - v) < 0.06 for u, v in zip(vals[:4], (*pos, *vals[4:6]))):
            cmd, vals = 'L', vals[4:6]
        straight.append((cmd, vals))
        if cmd == 'M':
            first = (vals[0], vals[1])
        pos = first if cmd == 'Z' else (vals[-2], vals[-1])
    segments = straight
    cleaned, start = [], None
    for i, (cmd, vals) in enumerate(segments):
        if cmd == 'M':
            start = (vals[0], vals[1])
        nxt = segments[i + 1][0] if i + 1 < len(segments) else None
        if cmd == 'L' and nxt == 'Z' and start and abs(vals[0] - start[0]) < 0.06 and abs(vals[1] - start[1]) < 0.06:
            continue
        cleaned.append((cmd, vals))
    return cleaned


def path_points(segments, m, digits=2):
    """The path as transformed command/point lists (control points included; arcs by radii, rotation, flags and
    end point), without a redundant closing segment."""
    out = []
    for cmd, vals in clean_segments(segments):
        if cmd == 'Z':
            out.append(['Z'])
        elif cmd == 'A':
            px, py = apply(m, vals[5], vals[6])
            out.append(['A', r(vals[0], digits), r(vals[1], digits), r(vals[2], digits), int(vals[3]), int(vals[4]),
                        r(px, digits), r(py, digits)])
        else:
            pts = []
            for k in range(0, len(vals), 2):
                px, py = apply(m, vals[k], vals[k + 1])
                pts += [r(px, digits), r(py, digits)]
            out.append([cmd] + pts)
    return out


def path_extremes(segments, m):
    """Points of a path in document coordinates that bound it: the segment end points and the turning points of every
    curve and arc in x and y (control points do not count)."""
    out, pos, first = [], (0.0, 0.0), (0.0, 0.0)
    for cmd, vals in segments:
        if cmd == 'Z':
            pos = first
            continue
        if cmd == 'M':
            first = (vals[0], vals[1])
        elif cmd in ('C', 'Q'):
            out += bezier_extremes([apply(m, *pos)] + [apply(m, vals[k], vals[k + 1]) for k in range(0, len(vals), 2)])
        elif cmd == 'A':
            out += arc_extremes(pos, vals, m)
        pos = (vals[-2], vals[-1])
        out.append(apply(m, *pos))
    return out


def bezier_extremes(ctrl):
    """Turning points in x and y of a quadratic or cubic Bezier curve given by its control points."""
    def at(t):
        pts = list(ctrl)
        while len(pts) > 1:
            pts = [((1 - t) * p[0] + t * q[0], (1 - t) * p[1] + t * q[1]) for p, q in zip(pts, pts[1:])]
        return pts[0]
    ts = []
    for axis in (0, 1):
        v = [p[axis] for p in ctrl]
        # The derivative as a * t^2 + b * t + c (scaled).
        if len(v) == 4:
            a, b, c = -v[0] + 3 * v[1] - 3 * v[2] + v[3], 2 * (v[0] - 2 * v[1] + v[2]), v[1] - v[0]
        else:
            a, b, c = 0.0, v[0] - 2 * v[1] + v[2], v[1] - v[0]
        if abs(a) < 1e-12:
            if abs(b) > 1e-12:
                ts.append(-c / b)
        elif b * b - 4 * a * c >= 0:
            root = math.sqrt(b * b - 4 * a * c)
            ts += [(-b + root) / (2 * a), (-b - root) / (2 * a)]
    return [at(t) for t in ts if 0 < t < 1]


def arc_extremes(start, vals, m):
    """Turning points in x and y (document coordinates) of an elliptical arc from start with the A parameters."""
    rx, ry, rot, large, sweep, x2, y2 = vals
    x1, y1 = start
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0 or (abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9):
        return []
    # Centre parameterisation (SVG implementation notes F.6.5), radii scaled up when too small.
    cos, sin = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cos * dx + sin * dy, -sin * dx + cos * dy
    grow = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if grow > 1:
        rx, ry = rx * math.sqrt(grow), ry * math.sqrt(grow)
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, (rx * rx * ry * ry - den) / den)) if den else 0.0
    if bool(large) == bool(sweep):
        coef = -coef
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx, cy = cos * cxp - sin * cyp + (x1 + x2) / 2, sin * cxp + cos * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    t1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    # In document coordinates the arc is centre + u cos t + v sin t for t from t1 to t1 + dt.
    a, b, c, d = m[:4]
    u = (a * rx * cos + c * rx * sin, b * rx * cos + d * rx * sin)
    v = (-a * ry * sin + c * ry * cos, -b * ry * sin + d * ry * cos)
    centre = apply(m, cx, cy)
    out = []
    for axis in (0, 1):
        turn = math.atan2(v[axis], u[axis])
        for t in (turn, turn + math.pi):
            if ((t - t1) if dt >= 0 else (t1 - t)) % (2 * math.pi) <= abs(dt):
                out.append((centre[0] + u[0] * math.cos(t) + v[0] * math.sin(t),
                            centre[1] + u[1] * math.cos(t) + v[1] * math.sin(t)))
    return out


def points_list(text):
    vals = [float(v) for v in NUMBER.findall(text or '')]
    return [(vals[k], vals[k + 1]) for k in range(0, len(vals) - 1, 2)]


# -- projections -------------------------------------------------------------------------------------
def text_content(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


def outline(doc, el, m=None):
    """Effective outline of one drawable element in document coordinates."""
    m = ctm(doc, el) if m is None else m
    a = attrs(el)
    kind = name(el)
    def ln(key, axis, default=None):
        return length(doc, a.get(key), axis, default)
    if kind in ('rect', 'image', 'foreignObject', 'use'):
        x, y = ln('x', 'x', 0), ln('y', 'y', 0)
        w, h = ln('width', 'x'), ln('height', 'y')
        if kind == 'use':
            ref = doc.ids.get((a.get('href') or '').lstrip('#'))
            if ref is not None and w is None:
                ra = attrs(ref)
                w, h = num(ra.get('width')), num(ra.get('height'))
                if w is None and name(ref) in ('rect', 'image'):
                    m = multiply(m, (1, 0, 0, 1, num(ra.get('x'), 0), num(ra.get('y'), 0)))
                    w, h = num(ra.get('width')), num(ra.get('height'))
        w, h = w or 0.0, h or 0.0
        pts = [apply(m, *p) for p in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]
    elif kind in ('circle', 'ellipse'):
        cx, cy = ln('cx', 'x', 0), ln('cy', 'y', 0)
        rx = ln('r', 'xy', 0) if kind == 'circle' else ln('rx', 'x', 0)
        ry = ln('r', 'xy', 0) if kind == 'circle' else ln('ry', 'y', 0)
        pts = [apply(m, *p) for p in ((cx - rx, cy), (cx, cy - ry), (cx + rx, cy), (cx, cy + ry))]
    elif kind == 'line':
        pts = [apply(m, ln('x1', 'x', 0), ln('y1', 'y', 0)), apply(m, ln('x2', 'x', 0), ln('y2', 'y', 0))]
    elif kind in ('polyline', 'polygon'):
        pts = [apply(m, *p) for p in points_list(a.get('points'))]
    elif kind == 'path':
        return {'path': path_points(parse_path(a.get('d')), m)}
    elif kind == 'text':
        x = num((a.get('x') or '0').split()[0].rstrip(','), 0) if a.get('x') else 0.0
        y = num((a.get('y') or '0').split()[0].rstrip(','), 0) if a.get('y') else 0.0
        px, py = apply(m, x, y)
        # Rotation and signed scale of the text's matrix (a mirrored text has a negative vertical scale).
        angle = r(math.degrees(math.atan2(m[1], m[0])), 1)
        sx = math.hypot(m[0], m[1])
        sy = (m[0] * m[3] - m[1] * m[2]) / sx if sx else 0.0
        return {'anchor': [r(px), r(py)], 'angle': 180.0 if angle == -180.0 else angle, 'scale': [r(sx, 3), r(sy, 3)]}
    else:
        return {}
    pts = [[r(px), r(py)] for px, py in pts]
    if kind in ('rect', 'circle', 'ellipse'):
        pts = canonical_ring(pts)
    return {'points': pts}


def canonical_ring(pts):
    """Corner points of a symmetric shape (rectangle, circle, ellipse) from the lowest corner, clockwise on screen:
    a mirrored copy written with a transform and one written with plain attributes give the same list."""
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if area < 0:
        pts = pts[::-1]
    start = min(range(len(pts)), key=lambda i: (pts[i][0], pts[i][1]))
    return pts[start:] + pts[:start]


def corners(pts, tol=0.06):
    """The distinct corners of a closed outline as a ring (see canonical_ring): a corner repeated anywhere in the
    list (a closing repeat, SVG-edit's star repeating its first corners) counts once."""
    out = []
    for p in pts:
        if all(abs(p[0] - q[0]) > tol or abs(p[1] - q[1]) > tol for q in out):
            out.append(p)
    return canonical_ring(out) if len(out) > 2 else out


def paint(el, keys=PAINT):
    a = attrs(el)
    out = {}
    for key in keys:
        if key in a:
            value = a[key]
            out[key] = colour(value) if key in ('fill', 'stroke') else (r(num(value)) if num(value) is not None
                                                                         and key not in ('stroke-dasharray',) else
                                                                         re.sub(r'[\s,]+', ',', value.strip().lower()))
    return out


def element(doc, el, *, geometry=True, style=True, text=True):
    """Projection of one element (containers include their children)."""
    kind = name(el)
    out = {'kind': kind}
    if kind in CONTAINERS:
        out['children'] = [element(doc, c, geometry=geometry, style=style, text=text) for c in el
                           if name(c) in GRAPHIC + CONTAINERS]
        if style:
            p = paint(el)
            if p:
                out['paint'] = p
        title = next((text_content(c) for c in el if name(c) == 'title'), None)
        if title:
            out['title'] = title
        if kind == 'a':
            out['href'] = attrs(el).get('href')
        return out
    if geometry:
        out.update(outline(doc, el))
    if style:
        p = paint(el)
        if p:
            out['paint'] = p
    if kind == 'text' and text:
        out['text'] = text_content(el)
        font = {k: v for k, v in attrs(el).items() if k in FONT}
        if font:
            out['font'] = {k: (r(num(v)) if k in ('font-size', 'letter-spacing', 'word-spacing', 'textLength')
                               and num(v) is not None else v.strip().lower()) for k, v in font.items()}
    return out


def layer_summary(doc):
    """Layers with their titles, visibility and contents."""
    out = []
    for layer in doc.layers():
        a = attrs(layer)
        title = next((text_content(c) for c in layer if name(c) == 'title'), None)
        out.append({'title': title, 'hidden': a.get('display') == 'none' or a.get('visibility') == 'hidden',
                    'content': [element(doc, c) for c in layer if name(c) in GRAPHIC + CONTAINERS]})
    return out


def kinds(doc):
    """Element kinds of the whole document in document order (namespaced names kept)."""
    return [name(el) for el in doc.root.iter() if isinstance(el.tag, str)]
