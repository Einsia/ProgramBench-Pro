"""Program episodes: no evaluator. Each checkpoint reopens the editor, loads its drawing through
window.svgEditor.loadFromString, applies a scripted stimulus made only of keyboard shortcuts, pointer input in
document coordinates, lifecycle operations and file drops, and reads the result with getSvgString or a product
download.

A point that only verifies a rejection or that something stayed unchanged names, in `requires`, a positive point
of the same episode (C6). Representation points ('raw' checks) exist only where SVG-edit's own rewriting of the
markup is the behaviour; all other points compare representation-independent projections (svgmodel).
"""
import base64

import fixtures as F

INITIAL = ('Fresh editor page. Each checkpoint starts from a fresh browser profile (reset, then the entry page with '
           'its first-visit storage prompt answered with the default) and loads its own drawing through the editor '
           'API, so checkpoints do not depend on each other.')


# -- stimulus helpers ----------------------------------------------------------------------------------
def click(x, y, count=1, modifiers=None):
    step = {'op': 'pointer', 'target': {'document': True}, 'x': x, 'y': y}
    if count != 1:
        step['click_count'] = count
    if modifiers:
        step['modifiers'] = modifiers
    return step


def select(ident):
    return click(*F.POINTS[ident])


def drag(x0, y0, x1, y1, modifiers=None, via=None, steps=8):
    step = {'op': 'drag', 'target': {'document': True}, 'x': x0, 'y': y0, 'to_x': x1, 'to_y': y1, 'steps': steps}
    if modifiers:
        step['modifiers'] = modifiers
    if via:
        step['via'] = [list(p) for p in via]
    return step


def canvas_drag(x0, y0, x1, y1):
    return {'op': 'drag', 'target': {'ref': 'canvas0'}, 'x': x0, 'y': y0, 'to_x': x1, 'to_y': y1, 'steps': 8}


def key(name, times=1):
    return [{'op': 'press', 'key': name} for _ in range(times)]


def typed(text):
    return {'op': 'type', 'value': text}


def settle():
    return {'op': 'wait', 'seconds': 0.5}


def drop(x, y, name, data, mime):
    return {'op': 'drop', 'target': {'document': True}, 'x': x, 'y': y, 'filename': name, 'mime_type': mime,
            'base64': base64.b64encode(data).decode()}


EMPTY_CLICK = click(600, 455)  # a point of the page that no fixture covers


# -- builders -----------------------------------------------------------------------------------------
def point(name, requirement, check, requires=(), tol=None):
    check = dict(check)
    if tol is not None:
        check['tol'] = tol
    return {'name': name, 'requirement': requirement, 'check': check, 'requires': list(requires)}


def case(cid, goal, fixture, steps, points):
    return {'id': cid, 'goal': goal, 'fixture_svg': fixture, 'steps': list(steps), 'points': points}


def episode(key_, feature, cases):
    checkpoints = []
    for c in cases:
        assertions = []
        for p in c.pop('points'):
            a = {'id': f'{key_}/{c["id"]}/{p["name"]}', 'channel': 'backend', 'method': 'program',
                 'requirement': p['requirement'], 'check': p['check']}
            if p['requires']:
                a['requires'] = [f'{key_}/{r}' for r in p['requires']]
            assertions.append(a)
        checkpoints.append({**c, 'assertions': assertions, 'depends_on': ['setup:editor']})
    return {'id': key_, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL,
            'setup': [{'id': 'editor'}], 'inputs': {}, 'checkpoints': checkpoints}


def multi(**checks):
    return {'type': 'multi', 'checks': checks}


def element(ident, *parts):
    return {'type': 'element', 'id': ident, 'parts': list(parts or ('outline', 'paint'))}


def new(*parts, index=-1):
    return {'type': 'new', 'index': index, 'parts': list(parts or ('outline', 'paint'))}


def raw(ident, *attrs):
    return {'type': 'raw', 'id': ident, 'attrs': list(attrs)}


def attributes(ident, *names):
    return {'type': 'attributes', 'id': ident, 'names': list(names)}


def present(*kinds):
    return {'type': 'present', 'kinds': list(kinds)}


TOP = {'type': 'top', 'parts': ['outline']}
LAYERS = {'type': 'layers'}
DOCUMENT = {'type': 'document'}
COUNT = {'type': 'count'}
ROOT = {'type': 'root'}
ROOT_UNITS = {'type': 'root-units'}
SVGNS = '{http://www.w3.org/2000/svg}'


# -- import: document structure and normalisation ------------------------------------------------------
def import_structure():
    d = F.doc
    loose = d('<rect id="lr" x="20" y="30" width="80" height="40" fill="#336699"/><g id="lg"><title>Pair</title>'
              '<circle id="lc" cx="200" cy="80" r="25"/><rect id="lq" x="240" y="60" width="30" height="30"/></g>',
              500, 400)
    layered = ('<svg ' + F.NS + ' width="500" height="400"><g class="layer"><title>Back</title><rect id="ba" x="10" '
               'y="10" width="50" height="50"/></g><g><rect id="pa" x="100" y="10" width="40" height="40"/></g>'
               '<g class="layer" id="hl" style="display:none"><title>Hidden</title><circle id="hc" cx="300" cy="100" '
               'r="30"/></g><g class="layer"><title>Front</title><ellipse id="fe" cx="200" cy="300" rx="60" ry="20"/>'
               '</g></svg>')
    inkscape = ('<svg ' + F.NS + ' xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" width="400" height="300">'
                '<sodipodi:namedview id="nv" pagecolor="#ffffff"/><g id="il" inkscape:label="Sketch" '
                'inkscape:groupmode="layer"><rect id="ir" x="20" y="20" width="60" height="40" inkscape:label="box"/>'
                '</g></svg>')
    cases = [
        case('loose', 'Load a drawing whose shapes are not in any layer.', loose, [], [
            point('layer', 'Content outside layers is placed in a new layer named "Layer 1".', LAYERS),
            point('group-title', 'A group keeps its title and its children.',
                  element('lg', 'outline', 'title'), requires=['loose/layer']),
        ]),
        case('layered', 'Load a drawing with layer groups, a hidden layer and a plain top-level group.', layered, [], [
            point('layers', 'Layer groups keep their titles and order; a plain top-level group is wrapped into a new '
                            'last layer named "Layer 1"; the hidden layer stays hidden.', LAYERS),
            point('hidden', 'A layer hidden with a style declaration is written with display="none".',
                  raw('hl', 'display', 'style'), requires=['layered/layers']),
        ]),
        case('inkscape', 'Load an Inkscape drawing with an Inkscape layer and editor metadata.', inkscape, [], [
            point('not-layer', 'Groups marked as Inkscape layers are not taken as layers; they stay groups inside '
                               '"Layer 1".', LAYERS),
            point('foreign', 'Elements and attributes of the Inkscape and Sodipodi namespaces are removed.',
                  multi(elements=present('{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}namedview'),
                        attributes=attributes('ir', '{http://www.inkscape.org/namespaces/inkscape}label', 'x')),
                  requires=['inkscape/not-layer']),
        ]),
    ]
    for unit, width, height in (('cm', '12cm', '8cm'), ('mm', '150mm', '90mm'), ('in', '5in', '3in'),
                                ('pt', '360pt', '270pt'), ('pc', '30pc', '20pc')):
        cases.append(case('size-' + unit, f'Load a drawing whose size is given in {unit}.',
                          '<svg ' + F.NS + f' width="{width}" height="{height}"><rect id="u1" x="1cm" y="10mm" '
                          'width="1in" height="36pt"/></svg>', [], [
                              point('size', f'The document size given in {unit} is converted to pixels.', ROOT_UNITS)]))
    cases[-1]['points'].append(point('element-units', 'Lengths with units on elements are kept as written.',
                                     raw('u1', 'text:x', 'text:y', 'text:width', 'text:height'),
                                     requires=['size-pc/size']))
    cases += [
        case('size-invalid', 'Load a drawing whose width is negative and whose height is zero.',
             '<svg ' + F.NS + ' width="-50" height="0"><rect id="v0" x="10" y="10" width="20" height="20"/></svg>', [], [
                 point('size', 'A negative or zero document size is replaced by 100 x 100.', ROOT)]),
        case('viewbox-only', 'Load a drawing that has a viewBox but no width or height.',
             '<svg ' + F.NS + ' viewBox="0 0 320 180"><rect id="v1" x="10" y="10" width="60" height="40"/></svg>', [], [
                 point('size', 'The document size is taken from the viewBox.', ROOT)]),
        case('viewbox-scaled', 'Load a drawing whose width and height differ from its viewBox.',
             '<svg ' + F.NS + ' width="800" height="500" viewBox="0 0 400 250"><rect id="v2" x="10" y="10" width="60" '
             'height="40"/></svg>', [], [
                 point('size', 'The document size becomes the viewBox size (the outer scaling is dropped).', ROOT)]),
        case('no-size', 'Load a drawing with neither size nor viewBox.',
             '<svg ' + F.NS + '><rect id="v3" x="5" y="15" width="60" height="20"/></svg>', [], [
                 point('size', 'A drawing without size or viewBox is sized to the extent of its content.', ROOT)]),
        case('style', 'Load shapes styled with style declarations.',
             d('<rect id="s1" x="10" y="10" width="80" height="50" style="fill:#ff6600;stroke:#0000ff;stroke-width:3;'
               'opacity:0.5"/><text id="s2" x="20" y="120" style="font-size:20px;font-family:Arial;'
               'font-weight:bold">Styled</text>'), [], [
                 point('shape', 'Style declarations of a shape become presentation attributes.',
                       raw('s1', 'style', 'colour:fill', 'colour:stroke', 'stroke-width', 'opacity')),
                 point('text', 'Font declarations of a text become presentation attributes.',
                       raw('s2', 'style', 'length:font-size', 'text:font-family', 'weight:font-weight')),
             ]),
        case('rounding', 'Load shapes whose numbers have many decimals.',
             d('<rect id="n1" x="10.126" y="20.2049" width="30.5555" height="40.001" rx="3.333"/>'
               '<circle id="n2" cx="101.23456" cy="102.34567" r="13.45678"/>'
               '<path id="n3" d="M1.23456 2.34567 L 10.98765 20.12345"/>'
               '<polygon id="n4" points="301.23456,2.34567 303.45678,4.56789 309,9"/>'
               '<line id="n5" x1="400.12345" y1="10" x2="450" y2="60" stroke="#000" stroke-width="1.23456" '
               'opacity="0.98765"/>'
               '<rect id="n7" x="1e1" y="+7" width="5.0" height="0.50e2"/>'), [], [
                 point('rect', 'Rectangle geometry is rounded to 2 decimals.',
                       raw('n1', 'x', 'y', 'width', 'height', 'rx'), tol=0.0005),
                 point('circle', 'Circle geometry is rounded to 2 decimals.', raw('n2', 'cx', 'cy', 'r'), tol=0.0005),
                 point('path', 'Path coordinates are rounded to 2 decimals.', raw('n3', 'exact:d'), tol=0.0005),
                 point('points', 'Polygon points are kept unrounded.', raw('n4', 'numbers:points'),
                       requires=['rounding/rect'], tol=0.000005),
                 point('presentation', 'Stroke width and opacity are rounded to 2 decimals.',
                       raw('n5', 'stroke-width', 'opacity', 'x1'), tol=0.0005),
                 point('notation', 'Numbers in exponent or signed notation are written as plain decimals.',
                       raw('n7', 'decimal:x', 'decimal:y', 'decimal:width', 'decimal:height')),
             ]),
        case('ids', 'Load shapes without ids and with a duplicated id.',
             d('<rect x="10" y="10" width="20" height="20"/><rect id="dup" x="40" y="10" width="20" height="20"/>'
               '<rect id="dup" x="70" y="10" width="20" height="20"/><circle id="keep" cx="120" cy="20" r="10"/>'
               '<g><rect x="150" y="10" width="20" height="20"/></g>'), [], [
                 point('assigned', 'Every element gets an id, ids are unique (a repeated id is renamed) and given ids '
                                   'are kept.', {'type': 'ids', 'kept': ['dup', 'keep']}),
             ]),
        case('meta', 'Load a drawing with a document title, description and metadata.',
             d('<title>Site plan</title><desc>Ground floor</desc><metadata><note>draft</note></metadata>'
               '<rect id="m1" x="10" y="10" width="40" height="40"><title>Tip</title></rect>'), [], [
                 point('kept', 'The document title, description and metadata are kept.',
                       {'type': 'root-children', 'tags': ['title', 'desc', 'metadata']}),
                 point('element-title', 'An element keeps its own title.', {'type': 'child-tags', 'id': 'm1'},
                       requires=['meta/kept']),
             ]),
        case('defs', 'Load a drawing with one used and one unused gradient.',
             d('<defs><linearGradient id="used"><stop offset="0" stop-color="#ff0000"/><stop offset="1" '
               'stop-color="#0000ff"/></linearGradient><radialGradient id="spare"><stop offset="0" '
               'stop-color="#00ff00"/></radialGradient></defs><rect id="g1x" x="10" y="10" width="100" height="60" '
               'fill="url(#used)"/>'), [], [
                 point('used', 'A referenced gradient is kept with its stops.', element('g1x', 'paint')),
                 point('unused', 'An unreferenced gradient is removed.', present('radialGradient', 'linearGradient'),
                       requires=['defs/used']),
             ]),
        case('nested', 'Load a drawing containing a nested svg element.',
             d('<svg id="inner" x="50" y="40" width="200" height="100" viewBox="0 0 20 10"><rect id="nr" width="10" '
               'height="10" fill="#884400"/></svg>'), [], [
                 point('wrapped', 'A nested svg element is placed inside a new group.', LAYERS),
             ]),
        case('xlink', 'Load a drawing that references with xlink:href.',
             d('<defs><symbol id="sy" viewBox="0 0 10 10" width="10" height="10"><circle cx="5" cy="5" r="5"/>'
               '</symbol></defs><use id="xu" xlink:href="#sy" x="20" y="20" width="40" height="40"/>'
               f'<image id="xi" xlink:href="{F.TILE}" x="100" y="20" width="16" height="16"/>'), [], [
                 point('href', 'xlink:href references are written as href.', raw('xu', 'text:href', 'xlink:href')),
             ]),
        case('transforms', 'Load shapes that carry transforms.',
             d('<rect id="tr1" x="10" y="20" width="30" height="40" transform="translate(5,6)"/>'
               '<circle id="tr2" cx="150" cy="50" r="15" transform="matrix(1 0 0 1 3 4)"/>'), [], [
                 point('kept', 'Transforms are kept as written when a drawing is loaded.',
                       raw('tr1', 'transform-kind', 'x')),
             ]),
        case('unicode', 'Load a text with non-Latin characters and escaped markup.',
             d('<text id="uc" x="10" y="40" font-size="20">Café 你好 ✓ &amp; &lt;tag&gt;</text>'), [], [
                 point('text', 'Text content, including non-Latin characters and escaped markup characters, is kept.',
                       {'type': 'textcontent', 'id': 'uc'})]),
        case('gradient-href', 'Load a gradient that inherits its stops from another gradient, and a gradient '
                              'defined inside a layer.',
             '<svg ' + F.NS + ' width="640" height="480"><defs><linearGradient id="base"><stop offset="0" '
             'stop-color="#ff0000"/><stop offset="1" stop-color="#0000ff"/></linearGradient><linearGradient '
             'id="child" xlink:href="#base" x2="0" y2="1"/></defs><g class="layer"><title>Paint</title><defs>'
             '<radialGradient id="inner"><stop offset="0" stop-color="#ffffff"/><stop offset="1" '
             'stop-color="#000000"/></radialGradient></defs><rect id="gh" width="50" height="50" fill="url(#child)"/>'
             '<circle id="gi" cx="120" cy="30" r="25" fill="url(#inner)"/></g></svg>', [], [
                 point('inherited', 'A gradient that references another gradient keeps that reference (its stops come '
                                    'from the referenced gradient).', {'type': 'element', 'id': 'gh',
                                                                       'parts': ['server']}),
                 point('in-layer', 'A gradient defined inside a layer keeps working.',
                       {'type': 'element', 'id': 'gi', 'parts': ['server']}),
             ]),
        case('user-gradients', 'Load shapes filled with gradients defined in user space, one of them with a '
                               'gradient transform.', F.USER_GRADIENTS, [], [
                 point('linear', 'A user-space linear gradient keeps its place on the shape.',
                       element('ug1', 'vector'), tol=1.0),
                 point('radial', 'A user-space radial gradient keeps its centre, focus and radius.',
                       element('ug2', 'vector'), tol=1.0),
                 point('transformed', 'A gradient transform is kept in effect.', element('ug3', 'vector'), tol=1.0),
             ]),
        case('zero-size', 'Load shapes of zero width or radius.',
             d('<rect id="z1" x="10" y="10" width="0" height="10"/><circle id="z2" cx="50" cy="50" r="0"/>'
               '<rect id="z3" x="80" y="10" width="20" height="20"/>'), [], [
                 point('kept', 'Shapes of zero size are kept.', {'type': 'ids-present', 'ids': ['z1', 'z2', 'z3']})]),
        case('root-attributes', 'Load a drawing whose root element carries extra attributes.',
             d('<rect id="ra" width="5" height="5"/>', extra=' preserveAspectRatio="xMinYMin" version="1.1" '
               'id="rootid" class="doc" style="background:#eeeeee" x="5"'), [], [
                 point('filtered', 'The root keeps preserveAspectRatio, version and class and drops id, style, x and '
                                   'unknown attributes.',
                       {'type': 'root-attributes', 'names': ['preserveAspectRatio', 'version', 'class', 'id', 'style',
                                                             'x']})]),
        case('group-paint', 'Load a group that sets fill, stroke and opacity for its child.',
             d('<g id="gp1" opacity="0.5" fill="#0000ff" stroke="#ff0000" stroke-width="3"><rect id="gp2" x="10" '
               'y="10" width="50" height="50"/></g>'), [], [
                 point('inherited', 'The child inherits the group\'s fill, stroke and opacity.',
                       {'type': 'element', 'id': 'gp2', 'parts': ['paint']})]),
        case('hidden', 'Load shapes hidden with display and with visibility.',
             d('<rect id="hd" width="5" height="5" display="none"/><rect id="hv" x="9" width="5" height="5" '
               'visibility="hidden"/>'), [], [
                 point('display', 'display="none" is kept.', raw('hd', 'display')),
                 point('visibility', 'The visibility attribute is removed.', raw('hv', 'visibility'),
                       requires=['hidden/display']),
             ]),
        case('arc', 'Load paths with elliptical arc and horizontal/vertical line commands.',
             d('<path id="pa1" d="M10 10 A 20 30 45 1 0 50 50 Z"/><path id="pa2" d="m100,10 h20 v20 h-20 z"/>'), [], [
                 point('arc', 'An elliptical arc keeps its radii, rotation, flags and end point.',
                       element('pa1', 'outline')),
                 point('lines', 'Horizontal and vertical line commands are kept as the same outline.',
                       element('pa2', 'outline')),
             ]),
        case('relative-image', 'Load an image that references a file by a relative address.',
             d('<image id="ri" href="pics/photo.png" x="0" y="0" width="20" height="20"/>'), [], [
                 point('href', 'The relative image address is kept as written (not resolved or embedded).',
                       raw('ri', 'text:href'))]),
        case('layer-transform', 'Load a layer group that carries a transform.',
             '<svg ' + F.NS + ' width="640" height="480"><g class="layer" id="lt" transform="translate(10,20)">'
             '<title>Moved</title><rect id="lr2" width="5" height="5"/></g></svg>', [], [
                 point('kept', 'A layer keeps its transform.', raw('lt', 'transform'))]),
        case('layer-names', 'Load layers with equal names and a layer without a title.',
             '<svg ' + F.NS + ' width="640" height="480"><g class="layer"><title>Same</title><rect id="ln1" '
             'width="5" height="5"/></g><g class="layer"><title>Same</title><circle id="ln2" r="3" cx="9" cy="9"/>'
             '</g><g class="layer"><rect id="ln3" x="20" width="5" height="5"/></g></svg>', [], [
                 point('layers', 'Layers with equal names stay separate and a layer without a title stays a layer '
                                 'without a title.', LAYERS)]),
        case('malformed', 'Try to load text that is not well-formed XML over a loaded drawing.', loose, [], [
            point('rejected', 'Malformed input is rejected and the drawing stays as it was.',
                  {'type': 'load', 'svg': '<svg xmlns="http://www.w3.org/2000/svg"><rect x="1"'},
                  requires=['loose/layer']),
        ]),
        case('not-svg', 'Try to load an HTML document over a loaded drawing.', loose, [], [
            point('rejected', 'A document whose root is not svg is rejected and the drawing stays as it was.',
                  {'type': 'load', 'svg': '<html><body><p>not a drawing</p></body></html>'},
                  requires=['loose/layer']),
        ]),
    ]
    # Points that would also hold for a drawing echoed back unchanged count only together with the import's
    # positive normalisation (loose content wrapped into "Layer 1").
    for c in cases:
        for p in c['points']:
            if (c['id'], p['name']) in ECHOED and not p['requires']:
                p['requires'] = ['loose/layer']
    return episode('import-structure', 'import', cases)


ECHOED = {('meta', 'kept'), ('defs', 'used'), ('transforms', 'kept'), ('unicode', 'text'),
          ('gradient-href', 'inherited'), ('gradient-href', 'in-layer'), ('zero-size', 'kept'),
          ('group-paint', 'inherited'), ('hidden', 'display'), ('arc', 'arc'), ('arc', 'lines'),
          ('relative-image', 'href'), ('layer-transform', 'kept'), ('layer-names', 'layers'),
          ('user-gradients', 'linear'), ('user-gradients', 'radial'), ('user-gradients', 'transformed')}


# -- import: element whitelist ----------------------------------------------------------------------------
ELEMENTS_DOC = F.doc(
    '<defs>'
    '<linearGradient id="dl" x1="0" y1="0" x2="1" y2="1" spreadMethod="reflect" gradientTransform="rotate(10)" '
    'foo="1"><stop id="ds" offset="0.2" stop-color="#ff0000" stop-opacity="0.5" foo="1"/><stop offset="1" '
    'stop-color="#0000ff"/></linearGradient>'
    '<radialGradient id="dr" cx="0.5" cy="0.5" r="0.4" fx="0.3" fy="0.3" foo="1"><stop offset="0" '
    'stop-color="#ffffff"/><stop offset="1" stop-color="#000000"/></radialGradient>'
    '<pattern id="dp" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(20)" foo="1">'
    '<rect width="4" height="4" fill="#999999"/></pattern>'
    '<clipPath id="dc" clipPathUnits="userSpaceOnUse" foo="1"><rect x="0" y="0" width="600" height="400"/></clipPath>'
    '<mask id="dm" maskUnits="userSpaceOnUse" x="0" y="0" width="640" height="480" foo="1"><rect width="640" '
    'height="480" fill="#ffffff"/></mask>'
    '<marker id="dk" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto" markerUnits="strokeWidth" '
    'foo="1"><path d="M0,0 L6,3 L0,6 z"/></marker>'
    '<symbol id="dy" viewBox="0 0 10 10" width="10" height="10" foo="1"><circle cx="5" cy="5" r="5"/></symbol>'
    '<filter id="f1" x="-0.1" y="-0.1" width="1.2" height="1.2" filterUnits="objectBoundingBox" foo="1">'
    '<feGaussianBlur in="SourceGraphic" stdDeviation="2" result="b"/><feOffset in="b" dx="2" dy="3" result="o"/>'
    '<feMerge><feMergeNode in="o"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    '<filter id="f2"><feFlood flood-color="#ff0000" flood-opacity="0.5" result="fl"/><feComposite in="fl" '
    'in2="SourceGraphic" operator="in" result="c"/><feBlend in="c" in2="SourceGraphic" mode="multiply"/>'
    '<feColorMatrix type="saturate" values="0.5"/></filter>'
    '<filter id="f3"><feTurbulence baseFrequency="0.05" numOctaves="2" result="t"/><feDisplacementMap '
    'in="SourceGraphic" in2="t" scale="5" xChannelSelector="R" yChannelSelector="G"/><feMorphology operator="dilate" '
    'radius="1"/><feTile/></filter>'
    '<filter id="f4"><feComponentTransfer><feFuncR type="linear" slope="0.5"/></feComponentTransfer>'
    '<feConvolveMatrix order="3" kernelMatrix="0 1 0 1 -4 1 0 1 0"/></filter>'
    '<filter id="f5"><feDiffuseLighting surfaceScale="2" diffuseConstant="1" lighting-color="#ffffff">'
    '<fePointLight x="10" y="10" z="20"/></feDiffuseLighting><feSpecularLighting specularExponent="10" '
    'surfaceScale="2"><feDistantLight azimuth="45" elevation="30"/></feSpecularLighting><feImage href="#er"/>'
    '<feDropShadow dx="2" dy="2"/></filter>'
    '</defs>'
    '<rect id="er" x="10" y="10" width="60" height="40" rx="6" ry="4" fill="url(#dl)" filter="url(#f1)" foo="1"/>'
    '<circle id="ec" cx="120" cy="30" r="20" fill="url(#dr)" filter="url(#f2)" foo="1"/>'
    '<ellipse id="ee" cx="190" cy="30" rx="30" ry="15" fill="url(#dp)" filter="url(#f3)" foo="1"/>'
    '<line id="el" x1="240" y1="10" x2="320" y2="50" stroke="#000000" marker-start="url(#dk)" marker-end="url(#dk)" '
    'foo="1"/>'
    '<polyline id="epl" points="10,80 40,110 70,80" fill="none" stroke="#000000" marker-mid="url(#dk)" foo="1"/>'
    '<polygon id="epg" points="100,80 140,110 90,120" fill-rule="evenodd" filter="url(#f4)" foo="1"/>'
    '<path id="ep" d="M160 80 L220 80 L190 120 Z" fill-rule="nonzero" stroke-miterlimit="8" filter="url(#f5)" '
    'foo="1"/>'
    '<text id="et" x="240" y="100" textLength="80" lengthAdjust="spacingAndGlyphs" letter-spacing="1" '
    'word-spacing="2" text-decoration="underline" dominant-baseline="middle" foo="1">Text <tspan id="ets" dx="2" '
    'dy="1" rotate="5" font-weight="bold" foo="1">span</tspan></text>'
    '<path id="etl" d="M10 160 L300 160" fill="none"/>'
    '<text id="etp" x="0" y="0"><textPath id="etq" href="#etl" startOffset="10" foo="1">along the path</textPath>'
    '</text>'
    f'<image id="ei" x="330" y="80" width="40" height="30" preserveAspectRatio="xMidYMid slice" href="{F.TILE}" '
    'foo="1"/>'
    '<use id="eu" href="#dy" x="390" y="80" width="30" height="30" foo="1"/>'
    '<a id="ea" href="https://example.org/a" target="_blank" foo="1"><rect id="ear" x="10" y="200" width="40" '
    'height="30"/></a>'
    '<switch id="esw" systemLanguage="en" foo="1"><rect id="eswr" x="60" y="200" width="40" height="30"/></switch>'
    '<foreignObject id="efo" x="120" y="200" width="100" height="50" font-size="14" foo="1">'
    '<div xmlns="http://www.w3.org/1999/xhtml">Hi</div></foreignObject>'
    '<g id="eg" font-size="12" text-anchor="middle" fill="#123456" clip-path="url(#dc)" mask="url(#dm)" foo="1">'
    '<rect id="egr" x="240" y="200" width="40" height="30"/></g>'
    '<style id="est" type="text/css">.c{fill:#00ff00}</style>')
WHITELIST = [
    ('rect', 'er', ('x', 'y', 'width', 'height', 'rx', 'ry', 'fill', 'filter', 'foo')),
    ('circle', 'ec', ('cx', 'cy', 'r', 'fill', 'filter', 'foo')),
    ('ellipse', 'ee', ('cx', 'cy', 'rx', 'ry', 'fill', 'filter', 'foo')),
    ('line', 'el', ('x1', 'y1', 'x2', 'y2', 'marker-start', 'marker-end', 'foo')),
    ('polyline', 'epl', ('points', 'marker-mid', 'foo')),
    ('polygon', 'epg', ('points', 'fill-rule', 'filter', 'foo')),
    ('path', 'ep', ('d', 'fill-rule', 'stroke-miterlimit', 'filter', 'foo')),
    ('text', 'et', ('x', 'y', 'textLength', 'lengthAdjust', 'letter-spacing', 'word-spacing', 'text-decoration',
                    'dominant-baseline', 'foo')),
    ('tspan', 'ets', ('dx', 'dy', 'rotate', 'font-weight', 'foo')),
    ('textPath', 'etq', ('href', 'startOffset', 'foo')),
    ('image', 'ei', ('x', 'y', 'width', 'height', 'preserveAspectRatio', 'href', 'foo')),
    ('use', 'eu', ('href', 'x', 'y', 'width', 'height', 'foo')),
    ('a', 'ea', ('href', 'target', 'foo')),
    ('switch', 'esw', ('systemLanguage', 'foo')),
    ('foreignObject', 'efo', ('x', 'y', 'width', 'height', 'font-size', 'foo')),
    ('g', 'eg', ('font-size', 'text-anchor', 'fill', 'clip-path', 'mask', 'foo')),
    ('linearGradient', 'dl', ('x1', 'y1', 'x2', 'y2', 'spreadMethod', 'gradientTransform', 'foo')),
    ('stop', 'ds', ('offset', 'stop-color', 'stop-opacity', 'foo')),
    ('radialGradient', 'dr', ('cx', 'cy', 'r', 'fx', 'fy', 'foo')),
    ('pattern', 'dp', ('width', 'height', 'patternUnits', 'patternTransform', 'foo')),
    ('clipPath', 'dc', ('clipPathUnits', 'foo')),
    ('mask', 'dm', ('maskUnits', 'x', 'y', 'width', 'height', 'foo')),
    ('marker', 'dk', ('markerWidth', 'markerHeight', 'refX', 'refY', 'orient', 'markerUnits', 'foo')),
    ('symbol', 'dy', ('viewBox', 'width', 'height', 'foo')),
    ('filter', 'f1', ('x', 'y', 'width', 'height', 'filterUnits', 'foo')),
]
PRIMITIVES = [
    ('blur-offset-merge', ('feGaussianBlur', 'feOffset', 'feMerge', 'feMergeNode')),
    ('flood-composite-blend-matrix', ('feFlood', 'feComposite', 'feBlend', 'feColorMatrix')),
    ('turbulence-displacement-morphology-tile', ('feTurbulence', 'feDisplacementMap', 'feMorphology', 'feTile')),
    ('transfer-convolve', ('feComponentTransfer', 'feFuncR', 'feConvolveMatrix')),
    ('lighting-image-shadow', ('feDiffuseLighting', 'feSpecularLighting', 'fePointLight', 'feDistantLight', 'feImage',
                               'feDropShadow')),
]


def import_elements():
    points = [point(kind, f'A {kind} element is kept with the attributes SVG-edit supports for it; others are '
                          'removed.', attributes(ident, *names)) for kind, ident, names in WHITELIST]
    points += [point('filter-' + name, 'Filter primitives SVG-edit supports are kept; unsupported ones are removed.',
                     present(*kinds), requires=['all/rect']) for name, kinds in PRIMITIVES]
    points.append(point('style', 'A style element is kept with its rules.', {'type': 'textcontent', 'id': 'est'},
                        requires=['all/rect']))
    return episode('import-elements', 'import', [case('all', 'Load a drawing using every supported element kind, '
                                                              'each with one unsupported attribute.', ELEMENTS_DOC,
                                                       [], points)])


# -- import: content that is removed ------------------------------------------------------------------------
SANITIZE_DOC = F.doc(
    '<script id="sx">window.foo = 1</script>'
    '<rect id="cr" x="10" y="10" width="50" height="50" onclick="go()" onmouseover="go()" data-role="box" foo="bar"/>'
    '<rect id="ca" x="80" y="10" width="50" height="50"><animate attributeName="x" from="80" to="200" dur="1s"/>'
    '<set attributeName="fill" to="red"/><animateTransform attributeName="transform" type="rotate" from="0" to="90" '
    'dur="1s"/></rect>'
    '<foreignObject id="cf" x="10" y="80" width="300" height="150"><div xmlns="http://www.w3.org/1999/xhtml">'
    '<p>para</p><span>span</span><iframe src="/x"></iframe><object data="/y"></object><embed src="/z"/>'
    '<table><tr><td>cell</td></tr></table><input value="v"/><h1>Head</h1><ul><li>item</li></ul></div>'
    '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi><mo>=</mo><mn>2</mn></math></foreignObject>'
    '<use id="cu" href="other.svg#icon" x="10" y="250"/><use id="cl" href="#cr" x="200" y="0"/>')
HTML = '{http://www.w3.org/1999/xhtml}'


def import_content():
    p = [
        point('wrapped', 'The loaded content is placed in "Layer 1".', LAYERS),
        point('script', 'Script elements are removed.', present('script'), requires=['all/wrapped']),
        point('events', 'Event handler attributes are removed.', attributes('cr', 'onclick', 'onmouseover', 'x'),
              requires=['all/wrapped']),
        point('data-attributes', 'data-* attributes are kept; unknown attributes are removed.',
              attributes('cr', 'data-role', 'foo'), requires=['all/wrapped']),
        point('animation', 'Animation elements are removed.', present('animate', 'set', 'animateTransform'),
              requires=['all/wrapped']),
        point('html-kept', 'Basic HTML (div, p, span, headings, lists) inside foreignObject is kept.',
              present('html:div', 'html:p', 'html:span', 'html:h1', 'html:ul', 'html:li'), requires=['all/wrapped']),
        point('html-embedded', 'Embedded content (iframe, object, embed) inside foreignObject is removed.',
              present('html:iframe', 'html:object', 'html:embed'), requires=['all/wrapped']),
        point('html-other', 'Other HTML elements are removed but their text is kept.',
              multi(elements=present('html:table', 'html:td', 'html:input'), text={'type': 'textcontent', 'id': 'cf'}),
              requires=['all/wrapped']),
        point('mathml', 'MathML inside foreignObject is kept.', present('math:math', 'math:mi', 'math:mo', 'math:mn'),
              requires=['all/wrapped']),
        point('external-use', 'A use element referencing another file is removed; a local reference is kept.',
              {'type': 'ids-present', 'ids': ['cu', 'cl']}, requires=['all/wrapped']),
    ]
    return episode('import-content', 'import', [case('all', 'Load a drawing with scripts, event handlers, '
                                                             'animations, embedded HTML and MathML.', SANITIZE_DOC,
                                                      [], p)])


# -- keyboard editing: move ---------------------------------------------------------------------------------
REWRITE = {'rect': ('x', 'y', 'width', 'height', 'transform'), 'circle': ('cx', 'cy', 'r', 'transform'),
           'ellipse': ('cx', 'cy', 'rx', 'ry', 'transform'), 'line': ('x1', 'y1', 'x2', 'y2', 'transform'),
           'polyline': ('points', 'transform'), 'polygon': ('points', 'transform'), 'path': ('d', 'transform'),
           'text': ('x', 'y', 'transform'), 'image': ('x', 'y', 'width', 'height', 'transform'),
           'use': ('x', 'y', 'transform'), 'g': ('transform',), 'a': ('transform',),
           'foreignObject': ('x', 'y', 'width', 'height', 'transform')}
REWRITE_TEXT = {k: 'into its coordinates, without adding a transform' for k in REWRITE}
REWRITE_TEXT.update(g='as a translation in the group\'s transform', use='as a translation in its transform',
                    a='into the coordinates of the linked content')
KIND_NAMES = {'rect': 'rectangle', 'circle': 'circle', 'ellipse': 'ellipse', 'line': 'line', 'polyline': 'polyline',
              'polygon': 'polygon', 'path': 'path', 'text': 'text', 'image': 'image', 'use': 'use (symbol instance)',
              'g': 'group', 'a': 'link', 'foreignObject': 'foreignObject'}
LABELS = {'p2': 'curved path', 't2': 'text with tspans'}


def label(ident):
    return LABELS.get(ident, KIND_NAMES[F.KIND[ident]])


def keyboard_move():
    cases = []
    for ident, kind, _, _ in F.ELEMENTS:
        name = label(ident)
        cases.append(case('move-' + ident, f'Select the {name} by clicking it and press ArrowRight.', F.kinds_doc(),
                          [select(ident), *key('ArrowRight')], [
                              point('moved', f'ArrowRight moves the selected {name} 1 unit to the right.',
                                    element(ident, 'outline'), tol=0.05),
                              point('rewritten', f'The move of the {name} is written {REWRITE_TEXT[kind]}.',
                                    raw(ident, *REWRITE[kind]), requires=[f'move-{ident}/moved'], tol=0.05),
                          ]))
    cases.append(case('move-shift', 'Select the rectangle and press Shift+ArrowDown.', F.kinds_doc(['r1']),
                      [select('r1'), *key('Shift+ArrowDown')], [
                          point('moved', 'Shift+ArrowDown moves the selection 10 units down.', element('r1', 'outline'))]))
    for name, (ident, _, pt) in F.TRANSFORMED.items():
        what = name.replace('-', ' ').replace('foreign', 'foreignObject')
        kind = F.TRANSFORMED[name][1].split()[0].lstrip('<')
        cases.append(case('move-' + name, f'Select the {what} and press ArrowRight.', F.transformed_doc(name),
                          [click(*pt), *key('ArrowRight')], [
                              point('moved', f'ArrowRight moves the {what} 1 unit to the right in the drawing.',
                                    element(ident, 'outline'), tol=0.05),
                              point('rewritten', f'The move of the {what} keeps its transform type and is written '
                                                 'the way SVG-edit rewrites transformed elements.',
                                    raw(ident, *REWRITE[kind]), requires=[f'move-{name}/moved'], tol=0.05),
                          ]))
    g = F.USER_GRADIENT_POINTS
    cases += [
        case('move-user-gradient', 'Select the rectangle filled with a user-space linear gradient and press '
                                   'Shift+ArrowRight.', F.USER_GRADIENTS, [click(*g['ug1']), *key('Shift+ArrowRight')], [
                 point('follows', 'The gradient moves with the rectangle (its vector is 10 units further right).',
                       element('ug1', 'outline', 'vector'), tol=1.0)]),
        case('move-user-radial', 'Select the circle filled with a user-space radial gradient and press '
                                 'Shift+ArrowDown.', F.USER_GRADIENTS, [click(*g['ug2']), *key('Shift+ArrowDown')], [
                 point('follows', 'The radial gradient (centre, focus, radius) moves 10 units down with the circle.',
                       element('ug2', 'outline', 'vector'), tol=1.0)]),
        case('move-units', 'Select the rectangle whose lengths are given in in, cm and mm and press ArrowRight.',
             F.UNIT_LENGTHS, [click(*F.UNIT_POINTS['ua']), *key('ArrowRight')], [
                 point('moved', 'A rectangle sized in absolute units moves 1 unit (px) to the right.',
                       element('ua', 'outline'), tol=0.05),
                 point('rewritten', 'After the move its x, y, width and height are written in user units (px).',
                       raw('ua', 'x', 'y', 'width', 'height'), requires=['move-units/moved'], tol=0.05),
             ]),
        case('move-percent', 'Select the rectangle whose lengths are percentages of the page and press ArrowRight.',
             F.UNIT_LENGTHS, [click(*F.UNIT_POINTS['ub']), *key('ArrowRight')], [
                 point('moved', 'A rectangle sized in percentages of the page moves 1 unit to the right; after the '
                                'move its lengths are written in user units (px).',
                       multi(outline=element('ub', 'outline'), attributes=raw('ub', 'x', 'y', 'width', 'height')),
                       tol=0.05),
             ]),
    ]
    return episode('keyboard-move', 'keyboard-editing', cases)


# -- keyboard editing: rotate ---------------------------------------------------------------------------------
def keyboard_rotate():
    cases = []
    for ident, kind, _, _ in F.ELEMENTS:
        name = label(ident)
        tol = 0.5 if kind in ('text', 'foreignObject', 'use', 'a', 'g') else 0.1
        cases.append(case('rotate-' + ident, f'Select the {name} and press Control+ArrowRight three times.',
                          F.kinds_doc(), [select(ident), *key('Control+ArrowRight', 3)], [
                              point('rotated', f'Control+ArrowRight rotates the {name} clockwise by 1 degree per press '
                                               'around the centre of its bounding box.', element(ident, 'outline'),
                                    tol=tol)]))
    cases.append(case('rotate-left', 'Select the rectangle and press Control+ArrowLeft three times.', F.kinds_doc(['r1']),
                      [select('r1'), *key('Control+ArrowLeft', 3)], [
                          point('rotated', 'Control+ArrowLeft rotates counter-clockwise by 1 degree per press.',
                                element('r1', 'outline'), tol=0.1)]))
    for name in ('rect-rotated', 'rect-scaled', 'group-rotated'):
        ident, _, pt = F.TRANSFORMED[name]
        what = name.replace('-', ' ')
        cases.append(case('rotate-' + name, f'Select the {what} and press Control+ArrowRight three times.',
                          F.transformed_doc(name), [click(*pt), *key('Control+ArrowRight', 3)], [
                              point('rotated', f'Rotating the {what} adds to its existing transform.',
                                    element(ident, 'outline'), tol=0.1)]))
    return episode('keyboard-rotate', 'keyboard-editing', cases)


# -- keyboard editing: clone, delete, order, multi-selection, clipboard ------------------------------------------
def keyboard_edit():
    k = F.kinds_doc
    cases = [
        case('clone', 'Select the rectangle and press D.', k(['r1', 'c1']), [select('r1'), *key('d')], [
            point('offset', 'D duplicates the selection 20 units right and down with the same style.', new()),
            point('ids', 'The duplicate gets its own id; ids stay unique.', {'type': 'ids', 'kept': ['r1', 'c1']},
                  requires=['clone/offset']),
        ]),
        case('clone-gradient', 'Select the gradient-filled rectangle and press D.', F.GRADIENT,
             [click(300, 220), *key('d')], [
                 point('fill', 'The duplicate keeps the gradient fill.', new('outline', 'paint'))]),
        case('clone-group', 'Select the group and press D.', k(['g1']), [select('g1'), *key('d')], [
            point('children', 'Duplicating a group duplicates its children, moved 20 units right and down.',
                  new('outline', 'paint'))]),
        case('clone-use', 'Select the symbol instance and press D.', k(['u1']), [select('u1'), *key('d')], [
            point('instance', 'Duplicating a symbol instance gives another instance of the same symbol.',
                  new('outline', 'href'))]),
        case('clone-text', 'Select the text with tspans and press D.', k(['t2']), [select('t2'), *key('d')], [
            point('text', 'Duplicating a text keeps its lines.', new('outline', 'text'), tol=0.5)]),
        case('alt-arrow', 'Select the rectangle and press Alt+ArrowRight.', k(['r1']), [select('r1'),
                                                                                         *key('Alt+ArrowRight')], [
            point('copy', 'Alt+ArrowRight leaves the rectangle in place and adds a copy moved 1 unit right.', TOP)]),
        case('alt-drag', 'Drag the rectangle by (50, 20) while holding Alt.', k(['r1']),
             [select('r1'), drag(90, 70, 140, 90, modifiers=['Alt'])], [
                 point('copy', 'Dragging with Alt leaves the rectangle in place and drops a copy at the new place.',
                       TOP)]),
        case('delete', 'Select the circle and press Delete.', k(['r1', 'c1']), [select('c1'), *key('Delete')], [
            point('removed', 'Delete removes the selected element.', TOP)]),
        case('forward', 'Select the bottom rectangle and press Control+].', F.STACK,
             [click(*F.STACK_POINTS['sa']), *key('Control+BracketRight')], [
                 point('order', 'Control+] moves the selection one step up in the stacking order.', TOP)]),
        case('backward', 'Select the top rectangle and press Control+[.', F.STACK,
             [click(*F.STACK_POINTS['sc']), *key('Control+BracketLeft')], [
                 point('order', 'Control+[ moves the selection one step down in the stacking order.', TOP)]),
        case('select-all', 'Press A and then Delete in a drawing with two layers.', F.TWO_LAYERS,
             [EMPTY_CLICK, *key('a'), *key('Delete')], [
                 point('current-layer', 'A selects everything in the current (top) layer only; other layers keep '
                                        'their content.', LAYERS)]),
        case('multi-move', 'Press A, then ArrowRight.', k(['r1', 'c1', 'pg1']), [EMPTY_CLICK, *key('a'),
                                                                                  *key('ArrowRight')], [
            point('moved', 'Arrow keys move every selected element.', TOP)]),
        case('multi-clone', 'Press A, then C.', k(['r1', 'c1']), [EMPTY_CLICK, *key('a'), *key('c')], [
            point('copies', 'C duplicates a multiple selection, each copy 20 units right and down.', TOP)]),
        case('copy-paste', 'Select the rectangle, press Control+C, then Control+V.', k(['r1']),
             [select('r1'), *key('Control+c'), *key('Control+v')], [
                 point('pasted', 'Copy and paste adds a copy of the rectangle with the same size and style.',
                       new('size', 'paint'))]),
        case('paste-after-reload', 'Select the rectangle, press Control+C, reload the page, then press Control+V.',
             k(['r1']), [select('r1'), *key('Control+c'), {'op': 'reload'}, *key('Control+v')], [
                 point('pasted', 'The clipboard survives a reload of the page: Control+V pastes the copied rectangle.',
                       new('size', 'paint'), requires=['copy-paste/pasted'])]),
        case('cut', 'Select the rectangle and press Control+X.', k(['r1', 'c1']), [select('r1'), *key('Control+x')], [
            point('removed', 'Control+X removes the selection.', TOP)]),
        case('cut-paste', 'Select the rectangle, press Control+X, then Control+V.', k(['r1', 'c1']),
             [select('r1'), *key('Control+x'), *key('Control+v')], [
                 point('pasted', 'A cut element can be pasted back (same size and style).', new('size', 'paint'))]),
    ]
    return episode('keyboard-edit', 'keyboard-editing', cases)


# -- keyboard editing: group and ungroup ----------------------------------------------------------------------
def keyboard_group():
    cases = [
        case('group', 'Press A, then G.', F.STACK, [EMPTY_CLICK, *key('a'), *key('g')], [
            point('grouped', 'G groups a multiple selection, keeping the stacking order inside the group.', TOP)]),
        case('ungroup', 'Select the group and press G.', F.kinds_doc(['g1']), [select('g1'), *key('g')], [
            point('children', 'G on a selected group ungroups it: its children return to the layer.', TOP)]),
    ]
    for name, rewritten in (('group-translated', True), ('group-scaled', False), ('group-rotated', True)):
        ident, _, pt = F.TRANSFORMED[name]
        what = name.replace('-', ' ')
        child = {'group-translated': 'tu1', 'group-scaled': 'tw1', 'group-rotated': 'tg1'}[name]
        points = [point('kept', f'Ungrouping a {what} keeps every child where it was drawn.', TOP, tol=0.05)]
        if rewritten:
            points.append(point('rewritten', f'The {what} transform is moved onto each child the way SVG-edit writes '
                                             'it.', raw(child, 'transform-kind', 'transform', 'x', 'y'),
                                requires=[f'ungroup-{name}/kept'], tol=0.05))
        cases.append(case('ungroup-' + name, f'Select the {what} and press G.', F.transformed_doc(name),
                          [click(*pt), *key('g')], points))
    e = F.GROUP_EFFECT_POINTS
    cases += [
        case('ungroup-opacity', 'Select the half-transparent group and press G.', F.GROUP_EFFECTS,
             [click(*e['go']), *key('g')], [
                 point('opacity', 'The group is dissolved and its opacity is multiplied into each child, so the '
                                  'children look the same (0.5, and 0.5 x 0.6 for the child with its own opacity).',
                       multi(top=TOP, plain=element('go1', 'paint'), own=element('go2', 'paint')), tol=0.005)]),
        case('ungroup-blur', 'Select the blurred group and press G.', F.GROUP_EFFECTS,
             [click(*e['gf']), *key('g')], [
                 point('blur', 'Ungrouping passes the group\'s blur on: a child with its own blur gets the sum of both '
                               'deviations, the last child without one gets the group\'s blur.',
                       multi(own=element('gf2', 'blur'), plain=element('gf3', 'blur')), tol=0.01)]),
    ]
    return episode('keyboard-group', 'keyboard-editing', cases)


# -- keyboard editing: undo and redo ------------------------------------------------------------------------------
UNDO_OPS = [
    ('move', F.kinds_doc(['r1', 'c1']), [select('r1'), *key('ArrowRight')]),
    ('rotate', F.kinds_doc(['r1', 'c1']), [select('r1'), *key('Control+ArrowRight')]),
    ('clone', F.kinds_doc(['r1', 'c1']), [select('r1'), *key('d')]),
    ('delete', F.kinds_doc(['r1', 'c1']), [select('r1'), *key('Delete')]),
    ('group', F.STACK, [EMPTY_CLICK, *key('a'), *key('g')]),
    ('ungroup', F.kinds_doc(['g1']), [select('g1'), *key('g')]),
    ('order', F.STACK, [click(*F.STACK_POINTS['sa']), *key('Control+BracketRight')]),
    ('paste', F.kinds_doc(['r1']), [select('r1'), *key('Control+c'), *key('Control+v')]),
    ('draw', F.EMPTY, [*key('r'), drag(100, 100, 220, 180)]),
    ('resize', F.resize_doc('rect'), [click(320, 220), drag(421, 281, 461, 311)]),
]
# A pasted copy lands at the centre of the visible work area, so its redo counts by size and style, not position.
REDO_CHECKS = {'paste': multi(original=element('r1'), copy=new('size', 'paint'))}


def keyboard_undo():
    cases = []
    for op, fixture, steps in UNDO_OPS:
        # The restored drawing equals the starting one, so the point counts together with the redo of the change.
        cases.append(case('undo-' + op, f'Perform the {op} and press Control+Z.', fixture,
                          [*steps, *key('Control+z')], [
                              point('restored', f'Control+Z undoes the {op}.', DOCUMENT, tol=0.05,
                                    requires=[f'redo-{op}/reapplied'])]))
        cases.append(case('redo-' + op, f'Perform the {op}, press Control+Z, then Control+Y.', fixture,
                          [*steps, *key('Control+z'), *key('Control+y')], [
                              point('reapplied', f'Control+Y redoes the undone {op}.', REDO_CHECKS.get(op, DOCUMENT),
                                    tol=0.05)]))
    cases += [
        case('undo-steps', 'Select the rectangle, press ArrowRight three times, then Control+Z once.',
             F.kinds_doc(['r1']), [select('r1'), *key('ArrowRight', 3), *key('Control+z')], [
                 point('one-step', 'Each arrow press is one undo step.', element('r1', 'outline'))]),
        case('undo-sequence', 'Move the rectangle, duplicate it, then press Control+Z twice.', F.kinds_doc(['r1']),
             [select('r1'), *key('ArrowRight'), *key('d'), *key('Control+z', 2)], [
                 point('both', 'Undo steps back through different kinds of changes in order.', DOCUMENT,
                       requires=['redo-clone/reapplied'])]),
        case('redo-cleared', 'Move the rectangle right, undo, move it down, then press Control+Y.',
             F.kinds_doc(['r1']), [select('r1'), *key('ArrowRight'), *key('Control+z'), select('r1'),
                                   *key('ArrowDown'), *key('Control+y')], [
                 point('cleared', 'A new change clears what could be redone.', element('r1', 'outline'),
                       requires=['redo-move/reapplied'])]),
    ]
    return episode('keyboard-undo', 'keyboard-editing', cases)


# -- keyboard editing: text --------------------------------------------------------------------------------------
def text_keys():
    text_tool = [*key('t'), click(150, 200)]
    cases = [
        case('bold', 'Select the text and press B.', F.kinds_doc(['t1']), [select('t1'), *key('b')], [
            point('weight', 'B makes the selected text bold.', element('t1', 'font'))]),
        case('italic', 'Select the text and press I.', F.kinds_doc(['t1']), [select('t1'), *key('i')], [
            point('style', 'I makes the selected text italic.', element('t1', 'font'))]),
        case('bold-twice', 'Select the text and press B twice.', F.kinds_doc(['t1']), [select('t1'), *key('b', 2)], [
            point('weight', 'Pressing B again makes the text normal weight again.', element('t1', 'font'),
                  requires=['bold/weight'])]),
        case('typed', 'With the text tool, click at (150, 200), type "Wave" and press Escape.', F.EMPTY,
             [*text_tool, typed('Wave'), *key('Escape')], [
                 point('text', 'The text tool creates a text with the typed content at the clicked point.',
                       {'type': 'text', 'parts': ['text', 'outline']}, tol=0.5),
                 point('font', 'A new text has SVG-edit\'s default font, size, anchor and colour.',
                       {'type': 'text', 'parts': ['font', 'paint']}, requires=['typed/text']),
             ]),
        case('backspace', 'Type "Waves" with the text tool, press Backspace, then Escape.', F.EMPTY,
             [*text_tool, typed('Waves'), *key('Backspace'), *key('Escape')], [
                 point('text', 'Backspace deletes the character before the cursor.', {'type': 'text'})]),
        case('insert', 'Type "Wave", press ArrowLeft twice, type "X", then Escape.', F.EMPTY,
             [*text_tool, typed('Wave'), *key('ArrowLeft', 2), typed('X'), *key('Escape')], [
                 point('text', 'Arrow keys move the text cursor; typing inserts at the cursor.', {'type': 'text'})]),
        case('delete-forward', 'Type "Wave", press ArrowLeft twice, Delete, then Escape.', F.EMPTY,
             [*text_tool, typed('Wave'), *key('ArrowLeft', 2), *key('Delete'), *key('Escape')], [
                 point('text', 'Delete removes the character after the cursor.', {'type': 'text'})]),
        case('replace', 'Type "Wave", press Shift+ArrowLeft twice, type "nt", then Escape.', F.EMPTY,
             [*text_tool, typed('Wave'), *key('Shift+ArrowLeft', 2), typed('nt'), *key('Escape')], [
                 point('text', 'Shift+arrow selects characters; typing replaces the selection.', {'type': 'text'})]),
        case('edit-existing', 'Double-click inside the word "Alpha" after its second letter, type "Z", then Escape.',
             # Inside the left half of the "p" (78 to 92 wide), clear of the glyph's middle where caret rules differ.
             F.kinds_doc(['t1']), [click(81, 281, count=2), typed('Z'), *key('Escape')], [
                 point('text', 'Double-clicking a text edits it at the clicked position.', element('t1', 'text'))]),
    ]
    return episode('text-keys', 'text', cases)


# -- drawing tools with keyboard and pointer --------------------------------------------------------------------------
def draw_tools():
    e = F.EMPTY
    cases = [
        case('rect', 'Press R and drag from (100, 100) to (260, 180).', e, [*key('r'), drag(100, 100, 260, 180)], [
            point('geometry', 'R and a drag draw a rectangle spanning the drag.', new('outline')),
            point('style', 'New shapes get the default fill (red), stroke (black) and stroke width (5).',
                  new('paint'), requires=['rect/geometry']),
        ]),
        case('square', 'Press R and drag from (100, 100) to (260, 180) holding Shift.', e,
             [*key('r'), drag(100, 100, 260, 180, modifiers=['Shift'])], [
                 point('geometry', 'Holding Shift draws a square on the longer side of the drag.', new('outline'))]),
        case('rect-reversed', 'Press R and drag from (260, 180) back to (100, 100).', e,
             [*key('r'), drag(260, 180, 100, 100)], [
                 point('geometry', 'A rectangle dragged up and left spans the drag with positive width and height.',
                       new('outline'))]),
        case('line-reversed', 'Press L and drag from (300, 350) back to (100, 300).', e,
             [*key('l'), drag(300, 350, 100, 300)], [
                 point('geometry', 'A line keeps the drag direction: it starts where the drag started.', new('ends'))]),
        case('ellipse', 'Press E and drag from (300, 200) to (380, 250).', e, [*key('e'), drag(300, 200, 380, 250)], [
            point('geometry', 'E and a drag draw an ellipse centred on the drag start.', new('outline'))]),
        case('circle', 'Press E and drag from (300, 200) to (380, 250) holding Shift.', e,
             [*key('e'), drag(300, 200, 380, 250, modifiers=['Shift'])], [
                 point('geometry', 'Holding Shift draws a circle-shaped ellipse.', new('outline'))]),
        case('line', 'Press L and drag from (100, 300) to (300, 350).', e, [*key('l'), drag(100, 300, 300, 350)], [
            point('geometry', 'L and a drag draw a line between the drag points.', new('outline')),
            point('style', 'New lines have no fill and the default black stroke of width 5.', new('paint'),
                  requires=['line/geometry']),
        ]),
        case('line-snap', 'Press L and drag from (100, 300) to (300, 350) holding Shift.', e,
             [*key('l'), drag(100, 300, 300, 350, modifiers=['Shift'])], [
                 point('geometry', 'Holding Shift snaps the line angle to a multiple of 45 degrees.', new('outline'),
                       tol=0.1)]),
        case('pencil', 'Press Q and drag through (150, 90), (200, 150), (250, 180) to (300, 200), starting at '
                       '(100, 100).', e,
             [*key('q'), drag(100, 100, 300, 200, via=[(150, 90), (200, 150), (250, 180)])], [
                 # The smoothed stroke stops up to about 9 units short of the release point in the reference.
                 point('ends', 'The pencil draws a path from the drag start to near its end.', new('ends'), tol=12),
                 point('style', 'A freehand path has no fill and the default stroke.', new('paint'),
                       requires=['pencil/ends']),
             ]),
        case('path-closed', 'Press P, click (100, 100), (200, 100), (150, 180), then (100, 100) again.', e,
             [*key('p'), click(100, 100), click(200, 100), click(150, 180), click(100, 100), settle()], [
                 point('shape', 'Clicking the first node again closes the path.', new('outline', 'paint'))]),
        case('path-curve', 'Press P, click (100, 100), drag from (200, 100) to (260, 60), click (150, 180), then '
                           '(100, 100).', e,
             [*key('p'), click(100, 100), drag(200, 100, 260, 60), click(150, 180), click(100, 100), settle()], [
                 point('shape', 'Dragging while placing a node makes a curved segment.', new('outline'))]),
        case('path-open', 'Press P, click (100, 100), (200, 100), then double-click (250, 200).', e,
             [*key('p'), click(100, 100), click(200, 100), click(250, 200, count=2), settle()], [
                 point('shape', 'A double-click ends an open path at that point.', new('outline'))]),
        case('path-escape', 'Press P, click (100, 100) and (200, 100), then press Escape.', e,
             [*key('p'), click(100, 100), click(200, 100), *key('Escape'), settle()], [
                 point('nothing', 'Escape before the path is finished creates no path.', COUNT,
                       requires=['path-closed/shape'])]),
        case('path-snap', 'Press P, click (100, 100), Shift+click (200, 130), click (150, 200), then (100, 100).', e,
             [*key('p'), click(100, 100), click(200, 130, modifiers=['Shift']), click(150, 200), click(100, 100),
              settle()], [
                 point('shape', 'Holding Shift while placing a path node snaps the segment to a multiple of 45 degrees '
                                '(keeping its length).', new('outline'), tol=0.5)]),
        case('alt-keeps-tool', 'Press R, drag from (100, 100) to (200, 160) holding Alt, then drag from (300, 100) to '
                               '(400, 160).', e,
             [*key('r'), drag(100, 100, 200, 160, modifiers=['Alt']), drag(300, 100, 400, 160)], [
                 point('two', 'Holding Alt while finishing a shape keeps the drawing tool, so the next drag draws a '
                              'second rectangle.', TOP, requires=['rect/geometry'])]),
        case('repeat', 'Press R, draw a rectangle, then drag again on empty canvas.', e,
             [*key('r'), drag(100, 100, 160, 140), drag(300, 300, 380, 360)], [
                 point('select-tool', 'After a shape is drawn the editor returns to the selection tool, so a second '
                                      'drag on empty canvas draws nothing.', TOP, requires=['rect/geometry'])]),
        case('selected', 'Press R, draw a rectangle, then press Delete.', e,
             [*key('r'), drag(100, 100, 160, 140), *key('Delete')], [
                 point('deleted', 'A newly drawn shape is selected, so Delete removes it.', COUNT,
                       requires=['rect/geometry'])]),
        case('zoom-in', 'Press Control+ArrowUp, press R and drag 160 x 80 screen pixels on the drawing area.', e,
             [*key('Control+ArrowUp'), *key('r'), canvas_drag(500, 300, 660, 380)], [
                 point('size', 'Control+ArrowUp zooms in 2x: the same screen drag draws half the size.',
                       new('size'), tol=1.0)]),
        case('zoom-out', 'Press Control+ArrowDown, press R and drag 160 x 80 screen pixels on the drawing area.', e,
             [*key('Control+ArrowDown'), *key('r'), canvas_drag(500, 300, 660, 380)], [
                 point('size', 'Control+ArrowDown zooms out 2x: the same screen drag draws twice the size.',
                       new('size'), tol=2.0)]),
        case('outside', 'Press R and drag from (-80, -60) to (-20, -20), outside the page.', e,
             [*key('r'), drag(-80, -60, -20, -20)], [
                 point('geometry', 'Shapes can be drawn outside the page area.', new('outline'))]),
    ]
    return episode('draw-tools', 'drawing', cases)


# -- pointer selection and editing ---------------------------------------------------------------------------------
def pointer_edit():
    s = F.STACK_POINTS
    cases = [
        case('topmost', 'Click where the two lower rectangles overlap, then press Delete.', F.STACK,
             [click(220, 190), *key('Delete')], [
                 point('removed', 'A click selects the topmost element under the pointer.', TOP)]),
        case('shift-click', 'Click the bottom rectangle, Shift+click the top one, then press Delete.', F.STACK,
             [click(*s['sa']), click(*s['sc'], modifiers=['Shift']), *key('Delete')], [
                 point('removed', 'Shift+click adds an element to the selection.', TOP)]),
        case('shift-toggle', 'Click the bottom rectangle, Shift+click the top one, Shift+click the bottom one again, '
                             'then press Delete.', F.STACK,
             [click(*s['sa']), click(*s['sc'], modifiers=['Shift']), click(*s['sa'], modifiers=['Shift']),
              *key('Delete')], [
                 point('removed', 'Shift+click on a selected element removes it from the selection.', TOP,
                       requires=['shift-click/removed'])]),
        case('band', 'Drag a selection box from (90, 90) to (350, 290), then press Delete.', F.STACK,
             [drag(90, 90, 350, 290), *key('Delete')], [
                 point('removed', 'A selection box selects the elements it touches.', TOP)]),
        case('deselect', 'Click the bottom rectangle, click an empty spot, then press Delete.', F.STACK,
             [click(*s['sa']), EMPTY_CLICK, *key('Delete')], [
                 point('kept', 'Clicking empty canvas clears the selection.', TOP, requires=['topmost/removed'])]),
        case('cycle-back', 'Click the top rectangle, press Shift+O twice, then Delete.', F.STACK,
             [click(*s['sc']), *key('Shift+O', 2), *key('Delete')], [
                 point('removed', 'Shift+O selects the previous element in the stacking order.', TOP)]),
        case('cycle-wrap', 'Click the bottom rectangle, press Shift+O, then Delete.', F.STACK,
             [click(*s['sa']), *key('Shift+O'), *key('Delete')], [
                 point('removed', 'From the bottom element Shift+O wraps around to the topmost element.', TOP)]),
        case('drag-move', 'Drag the bottom rectangle from (120, 120) to (170, 140).', F.STACK,
             [drag(120, 120, 170, 140)], [
                 point('moved', 'Dragging an element moves it by the drag distance.', element('sa', 'outline'))]),
        case('group-child', 'Double-click the group, click its rectangle and press ArrowRight.', F.kinds_doc(['g1']),
             [click(530, 270, count=2), click(530, 270), *key('ArrowRight')], [
                 point('moved', 'Inside a double-clicked group, single children can be selected and moved.',
                       {'type': 'children', 'id': 'g1', 'parts': ['outline']})]),
        case('rotated-group-child', 'Double-click the rotated group, click its square and press ArrowRight.',
             F.transformed_doc('group-rotated'),
             [click(*F.TRANSFORMED['group-rotated'][2], count=2), click(*F.TRANSFORMED['group-rotated'][2]),
              *key('ArrowRight')], [
                 point('moved', 'A child of a rotated group moves in the drawing\'s direction.',
                       element('tg1', 'outline'), tol=0.05),
                 point('rewritten', 'The child\'s move is written in the group\'s coordinate system.',
                       raw('tg1', 'x', 'y', 'transform'), requires=['rotated-group-child/moved'], tol=0.05),
             ]),
        case('path-node', 'Double-click the triangle path and drag its first node from (320, 140) to (300, 120).',
             F.kinds_doc(['p1']), [click(370, 160, count=2), drag(320, 140, 300, 120)], [
                 point('node', 'In path edit mode a node can be dragged to a new position.', element('p1', 'outline'))]),
        case('eyedropper', 'Select the triangle, press Control+I, then click the rectangle.', F.kinds_doc(['r1', 'pg1']),
             [select('pg1'), *key('Control+i'), select('r1')], [
                 point('paint', 'The eyedropper copies paint between the selected and the clicked element.',
                       multi(rect=element('r1', 'paint'), triangle=element('pg1', 'paint')))]),
    ]
    return episode('pointer-edit', 'selection', cases)


# -- resizing and rotating with the selection grips ----------------------------------------------------------------
GRIP_REWRITE = {'rect': ('x', 'y', 'width', 'height', 'transform'), 'ellipse': ('cx', 'cy', 'rx', 'ry', 'transform'),
                'circle': ('cx', 'cy', 'r', 'transform'), 'line': ('x1', 'y1', 'x2', 'y2', 'transform'),
                'path': ('d', 'transform'), 'polygon': ('points', 'transform'),
                'image': ('x', 'y', 'width', 'height', 'transform'), 'use': ('x', 'y', 'transform')}


def pointer_resize():
    """Drags that start on a grip of the selection (1 unit outside an unstroked shape's box at zoom 1)."""
    R = F.RESIZE

    def pick(kind):
        inner = R[kind][2]
        # The thin line is selected with a selection box that crosses it.
        return [drag(200, 300, 330, 210)] if inner is None else [click(*inner)]

    def resize(cid, kind, goal, start, end, requirement, shift=False, rewritten=None):
        ident = R[kind][0]
        points = [point('resized', requirement, element(ident, 'outline'), tol=0.05)]
        if rewritten:
            points.append(point('rewritten', rewritten, raw(ident, *GRIP_REWRITE[kind]), requires=[cid + '/resized'],
                                tol=0.05))
        return case(cid, goal, F.resize_doc(kind),
                    [*pick(kind), drag(*start, *end, modifiers=['Shift'] if shift else None)], points)
    corner = F.rotate_point(421, 281, 30, 320, 220)
    cases = [
        resize('rect-se', 'rect', 'Select the rectangle and drag its bottom-right grip from (421, 281) to (461, 311).',
               (421, 281), (461, 311), 'The bottom-right grip enlarges the rectangle by the drag (40 x 30); its '
                                       'top-left corner stays.',
               rewritten='The resize is written into the rectangle\'s x, y, width and height, without a transform.'),
        resize('rect-nw', 'rect', 'Select the rectangle and drag its top-left grip from (219, 159) to (189, 139).',
               (219, 159), (189, 139), 'The top-left grip moves the top-left corner by the drag; the bottom-right '
                                       'corner stays.'),
        resize('rect-e', 'rect', 'Select the rectangle and drag its right grip from (421, 220) to (471, 220).',
               (421, 220), (471, 220), 'The right grip changes only the width.'),
        resize('rect-s', 'rect', 'Select the rectangle and drag its bottom grip from (320, 281) to (320, 331).',
               (320, 281), (320, 331), 'The bottom grip changes only the height.'),
        resize('rect-shift', 'rect', 'Select the rectangle and drag its bottom-right grip from (421, 281) to '
                                     '(481, 291) holding Shift.', (421, 281), (481, 291),
               'Holding Shift keeps the proportions: both sides scale by the horizontal factor (260 x 156).',
               shift=True),
        resize('rect-past', 'rect', 'Select the rectangle and drag its right grip from (421, 220) past its left edge '
                                    'to (181, 220).', (421, 220), (181, 220),
               'Dragging a grip past the opposite edge mirrors the rectangle to the other side (x 180, width 40).'),
        resize('ellipse', 'ellipse', 'Select the ellipse and drag its bottom-right grip from (421, 281) to '
                                     '(461, 311).', (421, 281), (461, 311),
               'The ellipse grows with its box: both radii scale and its centre moves to the new box centre.',
               rewritten='The resize is written into the ellipse\'s cx, cy, rx and ry.'),
        resize('circle', 'circle', 'Select the circle and drag its bottom-right grip from (381, 281) to (421, 311).',
               (381, 281), (421, 311), 'A circle stretched unevenly stays a circle: its radius is half the smaller '
                                       'side of the new box (75) and its centre is the scaled centre.',
               rewritten='The resize is written into the circle\'s cx, cy and r.'),
        resize('circle-shift', 'circle', 'Select the circle and drag its bottom-right grip from (381, 281) to '
                                         '(421, 311) holding Shift.', (381, 281), (421, 311),
               'With Shift the circle scales evenly by the horizontal factor (radius 80).', shift=True),
        resize('line', 'line', 'Select the line with a selection box crossing it, then drag its bottom-right grip '
                               'from (421, 281) to (461, 311).', (421, 281), (461, 311),
               'Resizing a line moves the end at the dragged corner; the other end stays.',
               rewritten='The resize is written into the line\'s end-point attributes.'),
        resize('path', 'path', 'Select the triangle path and drag its bottom-right grip from (421, 281) to (461, 311).',
               (421, 281), (461, 311), 'Every node of the path is scaled with the box.',
               rewritten='The resize is written into the path data, without a transform.'),
        resize('polygon', 'polygon', 'Select the triangle polygon and drag its bottom-right grip from (421, 281) to '
                                     '(461, 311).', (421, 281), (461, 311), 'Every vertex of the polygon is scaled '
                                                                             'with the box.',
               rewritten='The resize is written into the polygon\'s points.'),
        resize('image', 'image', 'Select the image and drag its bottom-right grip from (421, 281) to (461, 311).',
               (421, 281), (461, 311), 'An image keeps its aspect ratio while resized (240 x 144).'),
        resize('image-shift', 'image', 'Select the image and drag its bottom-right grip from (421, 281) to (461, 311) '
                                       'holding Shift.', (421, 281), (461, 311),
               'With Shift an image is resized freely (240 x 150).', shift=True),
        resize('use', 'use', 'Select the symbol instance and drag its bottom-right grip from (271, 201) to '
                             '(311, 231).', (271, 201), (311, 231), 'The instance is scaled to the new box (90 x 70).',
               rewritten='The resize of a symbol instance is written as a scale in its transform.'),
        case('group', 'Select the group and drag its bottom-right grip from (421, 281) to (461, 311).',
             F.resize_doc('group'), [*pick('group'), drag(421, 281, 461, 311)], [
                 point('resized', 'Every child of the group is scaled with the group\'s box.',
                       {'type': 'children', 'id': 'zq', 'parts': ['outline']}, tol=0.05),
                 point('rewritten', 'The resize of a group is written as a scale in the group\'s transform; the '
                                    'children keep their attributes.',
                       multi(group=raw('zq', 'transform'), child=raw('zq1', 'x', 'y', 'width', 'height')),
                       requires=['group/resized'], tol=0.05),
             ]),
        resize('rotated', 'rotated', f'Select the rectangle rotated by 30 degrees and drag its bottom-right grip from '
                                     f'({corner[0]:.2f}, {corner[1]:.2f}) by (40, 30).',
               (round(corner[0], 2), round(corner[1], 2)), (round(corner[0] + 40, 2), round(corner[1] + 30, 2)),
               'A rotated rectangle is resized along its own axes (the drag is turned into the rectangle\'s '
               'direction) and stays rotated by 30 degrees.'),
        case('rotate-grip', 'Select the rectangle and drag the rotation grip above it from (320, 139) to (480, 120).',
             F.resize_doc('rect'), [*pick('rect'), drag(320, 139, 480, 120)], [
                 point('rotated', 'Dragging the rotation grip turns the shape about its centre so that the grip points '
                                  'at the pointer (about 58 degrees).', element('zr', 'outline'), tol=0.1)]),
        case('rotate-grip-shift', 'Select the rectangle and drag the rotation grip from (320, 139) to (480, 120) '
                                  'holding Shift.',
             F.resize_doc('rect'), [*pick('rect'), drag(320, 139, 480, 120, modifiers=['Shift'])], [
                 point('rotated', 'With Shift the rotation snaps to a multiple of 45 degrees.',
                       element('zr', 'outline'), tol=0.1, requires=['rotate-grip/rotated'])]),
    ]
    return episode('pointer-resize', 'selection', cases)


# -- file drop ---------------------------------------------------------------------------------------------------
DROPPED_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40"><rect id="r1" width="60" height="40" '
               b'fill="#00aa88"/><circle cx="30" cy="20" r="10" fill="#ffffff"/></svg>')


def drop_import():
    e = F.EMPTY
    png = F.png(50, 30, (255, 128, 0, 255))
    cases = [
        case('svg', 'Drop an SVG file of 60 x 40 on the drawing at (320, 240).', e,
             [drop(320, 240, 'badge.svg', DROPPED_SVG, 'image/svg+xml'), settle()], [
                 point('placed', 'A dropped SVG file is imported as one object scaled up to fit (placed at the page '
                                 'origin).', {'type': 'extent'}),
                 point('structure', 'The imported drawing is kept as a symbol with an instance referencing it.',
                       multi(kind=raw_new('transform-kind'), defs=present('symbol', 'use')),
                       requires=['svg/placed']),
             ]),
        case('png', 'Drop a 50 x 30 PNG file on the drawing at (320, 240).', e,
             [drop(320, 240, 'dot.png', png, 'image/png'), settle()], [
                 point('placed', 'A dropped PNG becomes an image at its natural size, centred on the page.',
                       new('outline')),
                 point('embedded', 'The dropped PNG is embedded as a data URL.', new('href'),
                       requires=['png/placed']),
             ]),
        case('jpeg', 'Drop a 50 x 30 JPEG file on the drawing at (320, 240).', e,
             [drop(320, 240, 'photo.jpg', F.JPEG, 'image/jpeg'), settle()], [
                 point('placed', 'A dropped JPEG becomes an image at its natural size, centred on the page.',
                       new('outline')),
                 point('embedded', 'The dropped JPEG is embedded as a data URL.', new('href'),
                       requires=['jpeg/placed']),
             ]),
        case('text-file', 'Drop a plain text file on the drawing.', e,
             [drop(320, 240, 'notes.txt', b'just text\n', 'text/plain'), settle()], [
                 point('ignored', 'A dropped file that is not an image is ignored.', COUNT, requires=['png/placed'])]),
        case('ids', 'Drop an SVG file whose ids already exist in the drawing.', F.kinds_doc(['r1']),
             [drop(320, 240, 'badge.svg', DROPPED_SVG, 'image/svg+xml'), settle()], [
                 point('unique', 'Imported content gets ids that do not clash with the drawing.',
                       {'type': 'ids', 'kept': ['r1'], 'facets': ['unique', 'kept']},
                       requires=['svg/placed'])]),
    ]
    return episode('drop-import', 'files', cases)


def raw_new(*attrs):
    return {'type': 'raw', 'attrs': list(attrs)}


# -- save and persistence ---------------------------------------------------------------------------------------
def save_persist():
    k = F.kinds_doc(['r1', 'c1', 't1'])
    svg_image = F.data_url(b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" '
                           b'fill="#ff00ff"/></svg>', 'image/svg+xml')
    with_image = F.doc(f'<image id="si" x="20" y="20" width="64" height="64" href="{svg_image}"/>')
    cases = [
        case('save', 'Click an empty spot and press S.', k, [EMPTY_CLICK, *key('s'), settle()], [
            point('file', 'S saves the drawing as an SVG file named after the document (untitled.svg) with an XML '
                          'declaration.', {'type': 'download', 'format': 'svg', 'parts': ['name', 'declaration']}),
            point('content', 'The saved file contains the drawing.', {'type': 'download', 'format': 'svg',
                                                                      'parts': ['document']}, tol=0.05),
        ]),
        case('save-image', 'Load a drawing with an SVG image and press S.', with_image, [EMPTY_CLICK, *key('s'),
                                                                                          settle()], [
            point('embedded', 'Saving embeds images as PNG data (default "Embed data").',
                  {'type': 'download', 'format': 'svg', 'parts': ['images']}, requires=['save/file'])]),
        case('reload', 'Move the rectangle with ArrowRight, then reload the page.', k,
             [select('r1'), *key('ArrowRight'), {'op': 'reload'}], [
                 point('kept', 'The drawing is kept in the browser and restored after a reload.', DOCUMENT)]),
        case('restart', 'Move the rectangle, restart the application, then reload the page.', k,
             [select('r1'), *key('ArrowRight'), {'op': 'restart'}, {'op': 'reload'}], [
                 point('kept', 'The stored drawing survives a restart of the application.', DOCUMENT)]),
        case('fresh-profile', 'Reset to a fresh browser profile and open the editor.', k,
             [{'op': 'open-editor'}], [
                 point('new-document', 'A fresh profile starts with the default empty 640 x 480 drawing.', DOCUMENT,
                       requires=['reload/kept'])]),
        case('undo-after-reload', 'Move the rectangle, reload the page, then press Control+Z.', k,
             [select('r1'), *key('ArrowRight'), {'op': 'reload'}, *key('Control+z')], [
                 point('kept', 'A reload clears the undo history.', DOCUMENT, requires=['reload/kept'])]),
    ]
    return episode('save-persist', 'persistence', cases)


def build():
    return [import_structure(), import_elements(), import_content(), keyboard_move(), keyboard_rotate(),
            keyboard_edit(), keyboard_group(), keyboard_undo(), text_keys(), draw_tools(), pointer_edit(),
            pointer_resize(), drop_import(), save_persist()]
