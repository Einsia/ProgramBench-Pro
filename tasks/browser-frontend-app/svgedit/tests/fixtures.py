"""Hidden verifier documents and input files (independent of the public samples in environment/samples).

Every drawable element of a fixture has a known interior point in document
coordinates, so scripted checks can select it with a pointer click (target
{"document": true}) whatever the candidate's page layout.
"""
import base64
import math
import struct
import zlib

NS = 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'


def png(width, height, colour=(200, 40, 40, 255)):
    """A solid-colour RGBA PNG."""
    row = b'\x00' + bytes(colour) * width
    raw = row * height

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def data_url(data, mime='image/png'):
    return 'data:' + mime + ';base64,' + base64.b64encode(data).decode()


TILE = data_url(png(4, 4, (40, 120, 200, 255)))
# A 50 x 30 orange baseline JPEG.
JPEG = base64.b64decode(
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMU'
    'FRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU'
    'FBQUFBQUFBT/wAARCAAeADIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUF'
    'BAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVW'
    'V1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi'
    '4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAEC'
    'AxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVm'
    'Z2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq'
    '8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDqKKKK/lQ/qUKKKKACiiigAooooAKKKKACiiigAooooAKKKKAP/9k=')


def doc(body, width=640, height=480, extra=''):
    return f'<svg {NS} width="{width}" height="{height}"{extra}>{body}</svg>'


# -- one element of each kind, side by side; (id, kind, markup, interior point) ---------------------
ELEMENTS = [
    ('r1', 'rect', '<rect id="r1" x="40" y="40" width="100" height="60" fill="#3366cc"/>', (90, 70)),
    ('c1', 'circle', '<circle id="c1" cx="230" cy="70" r="35" fill="#33aa55"/>', (230, 70)),
    ('e1', 'ellipse', '<ellipse id="e1" cx="360" cy="70" rx="60" ry="30" fill="#cc8833"/>', (360, 70)),
    ('l1', 'line', '<line id="l1" x1="450" y1="45" x2="600" y2="95" stroke="#aa3333" stroke-width="10"/>', (525, 70)),
    ('pl1', 'polyline', '<polyline id="pl1" points="40,150 80,190 120,150 160,190" fill="none" stroke="#5555aa" '
                        'stroke-width="10"/>', (60, 170)),
    ('pg1', 'polygon', '<polygon id="pg1" points="230,140 280,210 180,210" fill="#aa55aa"/>', (230, 190)),
    ('p1', 'path', '<path id="p1" d="M320 140 L420 140 L370 210 Z" fill="#55aaaa"/>', (370, 160)),
    ('p2', 'path', '<path id="p2" d="M450 210 C470 140 560 140 580 210 Z" fill="#aaaa55"/>', (515, 190)),
    ('t1', 'text', '<text id="t1" x="50" y="290" font-family="serif" font-size="28" fill="#222222">Alpha</text>',
     (85, 281)),
    ('t2', 'text', '<text id="t2" x="200" y="285" font-family="serif" font-size="22" fill="#224422">'
                   '<tspan id="t2a" x="200" y="285">One</tspan><tspan id="t2b" x="200" y="310">Two</tspan></text>',
     (216, 278)),
    ('i1', 'image', f'<image id="i1" x="330" y="250" width="60" height="40" xlink:href="{TILE}"/>', (360, 270)),
    ('u1', 'use', '<use id="u1" xlink:href="#s1" x="430" y="250"/>', (455, 270)),
    ('g1', 'g', '<g id="g1"><rect id="g1r" x="510" y="250" width="40" height="40" fill="#996633"/>'
                '<circle id="g1c" cx="585" cy="270" r="18" fill="#339966"/></g>', (530, 270)),
    ('a1', 'a', '<a id="a1" xlink:href="https://example.org/"><rect id="a1r" x="40" y="360" width="80" height="50" '
                'fill="#cc3366"/></a>', (80, 385)),
    ('fo1', 'foreignObject', '<foreignObject id="fo1" x="200" y="350" width="120" height="60">'
                             '<div xmlns="http://www.w3.org/1999/xhtml">Note</div></foreignObject>', (260, 380)),
]
DEFS = ('<defs><symbol id="s1" viewBox="0 0 50 40" width="50" height="40"><rect width="50" height="40" '
        'fill="#6666cc"/></symbol></defs>')
POINTS = {ident: point for ident, _, _, point in ELEMENTS}
KIND = {ident: kind for ident, kind, _, _ in ELEMENTS}


def kinds_doc(only=None):
    chosen = [markup for ident, _, markup, _ in ELEMENTS if only is None or ident in only]
    return doc(DEFS + ''.join(chosen))


def rotate_point(x, y, angle, cx, cy):
    a = math.radians(angle)
    return (cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a))


# -- transformed elements (one per document); (id, markup, interior point) ----------------------------
TRANSFORMED = {
    'rect-rotated': ('tr', '<rect id="tr" x="250" y="200" width="140" height="80" fill="#3366cc" '
                           'transform="rotate(30 320 240)"/>', rotate_point(330, 240, 30, 320, 240)),
    'rect-scaled': ('ts', '<rect id="ts" x="100" y="100" width="80" height="50" fill="#3366cc" '
                          'transform="scale(2)"/>', (280, 250)),
    'rect-matrix': ('tm', '<rect id="tm" x="0" y="0" width="100" height="60" fill="#3366cc" '
                          'transform="matrix(0.8 0.3 -0.3 0.8 250 180)"/>', (281, 219)),
    'path-rotated': ('tp', '<path id="tp" d="M260 200 L380 200 L320 290 Z" fill="#55aaaa" '
                           'transform="rotate(-20 320 245)"/>', rotate_point(320, 230, -20, 320, 245)),
    'group-rotated': ('tg', '<g id="tg" transform="rotate(45 320 240)"><rect id="tg1" x="280" y="200" width="80" '
                            'height="80" fill="#996633"/><circle id="tg2" cx="320" cy="240" r="15" fill="#339966"/></g>',
                      rotate_point(300, 220, 45, 320, 240)),
    'group-translated': ('tu', '<g id="tu" transform="translate(40 30)"><rect id="tu1" x="250" y="180" width="60" '
                               'height="60" fill="#996633"/><path id="tu2" d="M330 180 L390 180 L360 240 Z" '
                               'fill="#339966"/><text id="tu3" x="250" y="280" font-size="20">Inner</text></g>',
                         (320, 240)),
    'group-scaled': ('tw', '<g id="tw" transform="matrix(1.5 0 0 1.5 -100 -80)"><rect id="tw1" x="200" y="200" '
                           'width="60" height="40" fill="#996633"/><circle id="tw2" cx="300" cy="220" r="20" '
                           'fill="#339966"/></g>', (245, 250)),
}


ROT = 'transform="rotate(30 320 240)"'
TRANSFORMED.update({
    'circle-rotated': ('kc', f'<circle id="kc" cx="320" cy="240" r="50" fill="#33aa55" {ROT}/>', (320, 240)),
    'ellipse-rotated': ('ke', f'<ellipse id="ke" cx="320" cy="240" rx="90" ry="40" fill="#cc8833" {ROT}/>',
                        (320, 240)),
    'line-rotated': ('kl', f'<line id="kl" x1="220" y1="240" x2="420" y2="240" stroke="#aa3333" stroke-width="12" '
                           f'{ROT}/>', rotate_point(370, 240, 30, 320, 240)),
    'image-rotated': ('ki', f'<image id="ki" x="280" y="210" width="80" height="60" xlink:href="{TILE}" {ROT}/>',
                      (320, 240)),
    'use-rotated': ('ku', '<use id="ku" xlink:href="#s1" x="295" y="220" ' + ROT + '/>', (320, 240)),
    'foreign-rotated': ('kf', '<foreignObject id="kf" x="260" y="210" width="120" height="60" ' + ROT + '>'
                              '<div xmlns="http://www.w3.org/1999/xhtml">Note</div></foreignObject>', (320, 240)),
    'circle-scaled': ('sc', '<circle id="sc" cx="160" cy="120" r="25" fill="#33aa55" transform="scale(2)"/>',
                      (320, 240)),
    'path-scaled': ('sp', '<path id="sp" d="M130 100 L190 100 L160 150 Z" fill="#55aaaa" transform="scale(2)"/>',
                    (320, 230)),
    'text-scaled': ('st', '<text id="st" x="140" y="125" font-family="serif" font-size="20" transform="scale(2)">'
                          'Big</text>', (310, 236)),
    'line-scaled': ('sl', '<line id="sl" x1="110" y1="120" x2="210" y2="120" stroke="#aa3333" stroke-width="8" '
                          'transform="scale(2)"/>', (320, 240)),
})


def transformed_doc(name):
    return doc(DEFS + TRANSFORMED[name][1])


# -- documents for ordering, layers, clipboard ---------------------------------------------------------
STACK = doc('<rect id="sa" x="100" y="100" width="160" height="120" fill="#cc3333"/>'
            '<rect id="sb" x="180" y="160" width="160" height="120" fill="#33cc33"/>'
            '<rect id="sc" x="260" y="220" width="160" height="120" fill="#3333cc"/>')
STACK_POINTS = {'sa': (120, 120), 'sb': (200, 255), 'sc': (400, 320)}
TWO_LAYERS = ('<svg ' + NS + ' width="640" height="480">'
              '<g class="layer"><title>Base</title><rect id="la" x="60" y="60" width="120" height="80" fill="#aa4444"/>'
              '</g><g class="layer"><title>Top</title><circle id="lb" cx="400" cy="300" r="50" fill="#44aa44"/>'
              '<rect id="lc" x="440" y="80" width="90" height="60" fill="#4444aa"/></g></svg>')
GRADIENT = doc('<defs><linearGradient id="gr1" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ff8800"/>'
               '<stop offset="1" stop-color="#0088ff"/></linearGradient></defs>'
               '<rect id="gq" x="200" y="160" width="200" height="120" fill="url(#gr1)"/>')
MARKED = doc('<defs><marker id="mk1" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">'
             '<path d="M0 0 L6 3 L0 6 Z" fill="#000000"/></marker></defs>'
             '<line id="ml" x1="150" y1="240" x2="450" y2="240" stroke="#000000" stroke-width="6" marker-end="url(#mk1)"/>')
EMPTY = doc('')


# -- GUI episodes ---------------------------------------------------------------------------------------------
G_RECT = doc('<rect id="gr" x="220" y="160" width="200" height="120" fill="#3366cc" stroke="#1a1a1a" '
             'stroke-width="4"/>')
G_RECT_POINT = (320, 220)
G_PAIR = doc('<rect id="gr" x="120" y="120" width="160" height="100" fill="#3366cc"/>'
             '<ellipse id="ge" cx="460" cy="330" rx="80" ry="45" fill="#cc6633"/>')
G_PAIR_POINTS = {'gr': (200, 170), 'ge': (460, 330)}
# Several kinds side by side for operations on a multiple selection.
G_MULTI = doc('<rect id="mr" x="60" y="60" width="120" height="80" fill="#3366cc"/>'
              '<ellipse id="me" cx="320" cy="100" rx="70" ry="40" fill="#cc6633"/>'
              '<path id="mp" d="M450 60 L560 60 L470 150 Z" fill="#33aa55"/>'
              '<polygon id="mg" points="120,250 170,285 150,345 90,345 70,285" fill="#aa55aa"/>'
              '<line id="ml" x1="240" y1="260" x2="400" y2="340" stroke="#333333" stroke-width="6"/>'
              '<text id="mt" x="470" y="320" font-family="serif" font-size="32" fill="#222222">Sample</text>'
              '<g id="mgp"><rect id="mgr" x="260" y="390" width="70" height="50" fill="#996633"/>'
              '<circle id="mgc" cx="370" cy="415" r="25" fill="#339966"/></g>')
G_MULTI_POINTS = {'mr': (120, 100), 'me': (320, 100), 'mp': (505, 85), 'mg': (120, 300), 'ml': (320, 300),
                  'mt': (520, 310), 'mgp': (295, 415)}
# Shapes that convert to paths.
G_CONVERT = doc('<rect id="vr" x="40" y="40" width="120" height="80" fill="#3366cc"/>'
                '<rect id="vq" x="200" y="40" width="120" height="80" rx="20" ry="20" fill="#3399cc"/>'
                '<ellipse id="ve" cx="440" cy="80" rx="70" ry="40" fill="#cc6633"/>'
                '<circle id="vc" cx="100" cy="240" r="50" fill="#cc9933"/>'
                '<line id="vl" x1="200" y1="200" x2="330" y2="290" stroke="#333333" stroke-width="6"/>'
                '<polygon id="vg" points="440,190 500,290 380,290" fill="#aa55aa"/>'
                '<polyline id="vp" points="60,360 120,420 180,360 240,420" fill="none" stroke="#5555aa" '
                'stroke-width="6"/>')
# Three rectangles of different sizes for align and distribute.
G_THREE = doc('<rect id="ka" x="60" y="80" width="60" height="40" fill="#cc3333"/>'
              '<rect id="kb" x="240" y="200" width="110" height="70" fill="#33cc33"/>'
              '<rect id="kc" x="430" y="300" width="160" height="110" fill="#3333cc"/>')
G_THREE_POINTS = {'ka': (90, 100), 'kb': (295, 235), 'kc': (510, 355)}
# The same three sizes where the largest is not the lowest and the smallest not the highest, so aligning to the
# largest or smallest one differs from aligning to the selection's bounds.
G_THREE_MIXED = doc('<rect id="ka" x="60" y="330" width="60" height="40" fill="#cc3333"/>'
                    '<rect id="kb" x="240" y="60" width="110" height="70" fill="#33cc33"/>'
                    '<rect id="kc" x="430" y="170" width="160" height="110" fill="#3333cc"/>')
G_TEXTS = doc(''.join(f'<text id="tx{i}" x="80" y="{90 + 80 * i}" font-family="serif" font-size="36" '
                      f'fill="#222222">Line {i + 1}</text>' for i in range(4)))
G_TEXT_POINTS = {f'tx{i}': (130, 78 + 80 * i) for i in range(4)}
G_LINES = doc(''.join(f'<line id="ln{i}" x1="80" y1="{90 + 90 * i}" x2="520" y2="{90 + 90 * i}" stroke="#222222" '
                      f'stroke-width="8"/>' for i in range(4)))
G_LINE_POINTS = {f'ln{i}': (300, 90 + 90 * i) for i in range(4)}
G_POLYLINES = doc('<polyline id="pa" points="80,140 200,60 320,140 440,60" fill="none" stroke="#222222" '
                  'stroke-width="14"/><polyline id="pb" points="80,340 200,260 320,340 440,260" fill="none" '
                  'stroke="#222222" stroke-width="14"/>')
G_POLYLINE_POINTS = {'pa': (140, 100), 'pb': (140, 300)}
G_PATH = doc('<path id="gp" d="M120 320 L220 160 L340 320 L460 160" fill="none" stroke="#224488" stroke-width="6"/>')
G_PATH_POINT = (170, 240)
G_CURVE = doc('<path id="gq" d="M120 300 C180 120 300 120 360 300 Z" fill="#88aa44" stroke="#224422" '
              'stroke-width="3"/>')
G_LAYERS = ('<svg ' + NS + ' width="640" height="480">'
            '<g class="layer"><title>Sky</title><rect id="ys" x="0" y="0" width="640" height="200" fill="#9fd3ff"/></g>'
            '<g class="layer"><title>Land</title><ellipse id="yl" cx="320" cy="380" rx="300" ry="90" fill="#7cbf5a"/></g>'
            '<g class="layer"><title>Notes</title><text id="yn" x="60" y="120" font-size="28">North</text>'
            '<rect id="yr" x="420" y="60" width="120" height="70" fill="#ffffff"/></g></svg>')
G_LAYER_POINTS = {'yn': (100, 110), 'yr': (480, 95)}
G_GROUP = doc('<g id="gg"><rect id="gga" x="200" y="160" width="120" height="90" fill="#996633"/>'
              '<circle id="ggb" cx="400" cy="300" r="50" fill="#339966"/></g>')
G_USE = doc('<defs><symbol id="sm" viewBox="0 0 60 60" width="60" height="60"><circle cx="30" cy="30" r="28" '
            'fill="#ee8800"/></symbol></defs><use id="gu" href="#sm" x="280" y="200"/>')
G_IMAGE = doc(f'<image id="gi" x="240" y="180" width="80" height="60" href="{TILE}"/>')
G_CONNECTED = doc('<rect id="ca" x="80" y="160" width="140" height="100" fill="#3366cc"/>'
                  '<ellipse id="cb" cx="480" cy="300" rx="80" ry="50" fill="#cc6633"/>')
G_ART = doc('<rect id="ar" x="40" y="40" width="200" height="140" fill="#ff0000"/>'
            '<circle id="ac" cx="460" cy="140" r="90" fill="#0000ff"/>'
            '<path id="ap" d="M60 440 L300 260 L560 440 Z" fill="#00aa00"/>')
G_SMALL = doc('<rect id="sr" x="20" y="20" width="160" height="80" fill="#ff8800"/>'
              '<circle id="sc" cx="300" cy="150" r="60" fill="#0088ff"/>', 400, 300)
G_FLIP = doc('<g id="fg"><rect id="fr" x="120" y="120" width="120" height="80" fill="#3366cc"/>'
             '<ellipse id="fe" cx="360" cy="160" rx="70" ry="40" fill="#cc6633"/>'
             '<path id="fp" d="M420 260 L520 260 L470 340 Z" fill="#33aa55"/>'
             '<text id="ft" x="140" y="320" font-family="serif" font-size="32" fill="#222222">Sample</text></g>')
G_FLIP_POINT = (180, 160)


# -- resizing and rotating with the selection grips; (id, markup, interior point or None for band selection) -------
# Unstroked shapes: at zoom 1 the grips sit 1 unit outside the corners of the bounding box (220, 160)-(420, 280).
RESIZE = {
    'rect': ('zr', '<rect id="zr" x="220" y="160" width="200" height="120" fill="#3366cc"/>', (320, 220)),
    'ellipse': ('ze', '<ellipse id="ze" cx="320" cy="220" rx="100" ry="60" fill="#cc8833"/>', (320, 220)),
    'circle': ('zc', '<circle id="zc" cx="320" cy="220" r="60" fill="#33aa55"/>', (320, 220)),
    'line': ('zl', '<line id="zl" x1="220" y1="160" x2="420" y2="280" stroke="#aa3333"/>', None),
    'path': ('zp', '<path id="zp" d="M220 160 L420 160 L320 280 Z" fill="#55aaaa"/>', (320, 190)),
    'polygon': ('zg', '<polygon id="zg" points="320,160 420,280 220,280" fill="#aa55aa"/>', (320, 250)),
    'image': ('zi', f'<image id="zi" x="220" y="160" width="200" height="120" href="{TILE}"/>', (320, 220)),
    'use': ('zu', '<use id="zu" href="#s1" x="220" y="160"/>', (245, 180)),
    'group': ('zq', '<g id="zq"><rect id="zq1" x="220" y="160" width="80" height="120" fill="#996633"/>'
                    '<circle id="zq2" cx="370" cy="220" r="50" fill="#339966"/></g>', (260, 220)),
    'rotated': ('zt', '<rect id="zt" x="220" y="160" width="200" height="120" fill="#3366cc" '
                      'transform="rotate(30 320 220)"/>', (320, 220)),
}


def resize_doc(kind):
    return doc(DEFS + RESIZE[kind][1])


# -- gradients in user space, lengths with units, groups with opacity and blur --------------------------------------
USER_GRADIENTS = doc(
    '<defs><linearGradient id="ul" gradientUnits="userSpaceOnUse" x1="220" y1="0" x2="420" y2="0">'
    '<stop offset="0" stop-color="#ff0000"/><stop offset="1" stop-color="#0000ff"/></linearGradient>'
    '<radialGradient id="ur" gradientUnits="userSpaceOnUse" cx="150" cy="380" r="60" fx="130" fy="370">'
    '<stop offset="0" stop-color="#ffff00"/><stop offset="1" stop-color="#008800"/></radialGradient>'
    '<linearGradient id="ut" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="100" y2="0" '
    'gradientTransform="translate(450 0) scale(1.5)"><stop offset="0" stop-color="#000000"/>'
    '<stop offset="1" stop-color="#ffffff"/></linearGradient></defs>'
    '<rect id="ug1" x="220" y="160" width="200" height="120" fill="url(#ul)"/>'
    '<circle id="ug2" cx="150" cy="380" r="60" fill="url(#ur)"/>'
    '<rect id="ug3" x="450" y="320" width="150" height="100" fill="url(#ut)"/>')
USER_GRADIENT_POINTS = {'ug1': (320, 220), 'ug2': (150, 380), 'ug3': (525, 370)}
UNIT_LENGTHS = doc('<rect id="ua" x="1in" y="2cm" width="50mm" height="1in" fill="#3366cc"/>'
                   '<rect id="ub" x="10%" y="50%" width="25%" height="20%" fill="#cc3333"/>')
UNIT_POINTS = {'ua': (150, 100), 'ub': (100, 260)}
GROUP_EFFECTS = doc(
    '<defs><filter id="gb"><feGaussianBlur stdDeviation="3"/></filter>'
    '<filter id="cb"><feGaussianBlur stdDeviation="2"/></filter></defs>'
    '<g id="go" opacity="0.5"><rect id="go1" x="100" y="100" width="100" height="80" fill="#cc3333"/>'
    '<rect id="go2" x="220" y="100" width="100" height="80" fill="#33cc33" opacity="0.6"/></g>'
    '<g id="gf" filter="url(#gb)"><rect id="gf1" x="100" y="300" width="100" height="80" fill="#cc3333"/>'
    '<rect id="gf2" x="220" y="300" width="100" height="80" fill="#33cc33" filter="url(#cb)"/>'
    '<rect id="gf3" x="340" y="300" width="100" height="80" fill="#3333cc"/></g>')
GROUP_EFFECT_POINTS = {'go': (150, 140), 'gf': (150, 340)}
G_ART_TITLED = doc('<title>Harbour chart</title><rect id="ar" x="40" y="40" width="200" height="140" fill="#ff0000"/>'
                   '<circle id="ac" cx="460" cy="140" r="90" fill="#0000ff"/>'
                   '<path id="ap" d="M60 440 L300 260 L560 440 Z" fill="#00aa00"/>')
G_LAYERS_HIDDEN = G_LAYERS.replace('<g class="layer"><title>Notes</title>',
                                   '<g class="layer" display="none"><title>Notes</title>')
# Text lines in a family none of the editor's font choices sets, so every choice is a change.
G_TEXTS_PLAIN = G_TEXTS.replace('font-family="serif"', 'font-family="Verdana"')
G_TEXT_MIDDLE = doc('<text id="tm" x="320" y="200" font-family="serif" font-size="36" fill="#222222" '
                    'text-anchor="middle">Middle line</text>')
G_TEXT_MIDDLE_POINT = (290, 188)
# Strokes that already use a non-default dash, join or cap.
G_STYLED = doc('<line id="sd" x1="80" y1="90" x2="520" y2="90" stroke="#222222" stroke-width="8" '
               'stroke-dasharray="5,5"/>'
               '<polyline id="sj" points="80,260 200,180 320,260 440,180" fill="none" stroke="#222222" '
               'stroke-width="14" stroke-linejoin="round"/>'
               '<line id="sc" x1="80" y1="400" x2="520" y2="400" stroke="#222222" stroke-width="14" '
               'stroke-linecap="round"/>')
G_STYLED_POINTS = {'sd': (302, 90), 'sj': (140, 220), 'sc': (300, 400)}
G_CURVE2 = doc('<path id="gk" d="M120 300 C180 120 300 120 360 300 L240 400 Z" fill="#88aa44" stroke="#224422" '
               'stroke-width="3"/>')
G_CURVE2_POINT = (240, 320)
# The same rectangle away from the page centre (for centring goals).
G_RECT_OFF = G_RECT.replace('x="220" y="160"', 'x="60" y="60"')
G_RECT_OFF_POINT = (160, 120)
