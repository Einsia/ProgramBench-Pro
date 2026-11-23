"""GUI episodes: reviewed user goals with acceptance conditions, prepared drawings, reference recipes and
independent program companions.

Each checkpoint starts from a fresh browser profile with its drawing loaded through the editor API (prepare);
when a goal starts from a selection, the selection is made by scripted clicks in document coordinates. The
evaluator then pursues the goal with the editor's own controls. Program companions read the resulting drawing
through getSvgString or the product download the goal produced. Recipes (record only) drive the pinned standard
through the same runtime operations; the control names they use belong to the standard, never to a candidate.
A point that only verifies a refusal or an unchanged state names a positive point of its episode in `requires`.
"""
import fixtures as F

SESSION = ('Each checkpoint starts with a fresh editor showing the drawing the goal describes; when the goal says '
           'something is selected, it already is. Use the editor\'s visible controls, menus, panels, dialogs, '
           'pointer and keyboard. Drawing coordinates in goals are document units (the rulers show them); '
           'pointer and drag also accept target {"document": true} with x/y in those units.')
EQUIVALENTS = ['Any visible route to the same result is valid: toolbar button, menu, context menu, keyboard '
               'shortcut, property field or dialog.',
               'Different labels, icons, layouts and dialog designs are valid.']
BYPASSES = ['Do not edit the drawing source or call programmatic interfaces unless the goal asks for the source '
            'editor.', 'Do not recreate a missing command by other means.']
INITIAL = ('Fresh editor in a fresh browser profile; the checkpoint\'s drawing is loaded and the stated selection '
           'is made before the goal starts.')


# -- recipe and preparation helpers -----------------------------------------------------------------------
def T(title, **extra):
    return {'do': 'click', 'title': title, **extra}


def X(text, **extra):
    return {'do': 'click', 'text': text, **extra}


def fill(value, **spec):
    return {'do': 'fill', 'value': str(value), **spec}


def select_option(value, **spec):
    return {'do': 'select', 'value': value, **spec}


def menu(item):
    return {'do': 'menu', 'item': item}


def press(key):
    return {'do': 'press', 'key': key}


def dclick(x, y, **extra):
    return {'do': 'pointer', 'x': x, 'y': y, **extra}


def ddrag(x0, y0, x1, y1, **extra):
    return {'do': 'drag', 'x': x0, 'y': y0, 'to_x': x1, 'to_y': y1, 'steps': 8, **extra}


def answer(value=None, action='accept'):
    step = {'do': 'dialog', 'action': action}
    if value is not None:
        step['value'] = value
    return step


def picker(which, hex_value, alpha=None):
    steps = [T('Change fill color' if which == 'fill' else 'Change stroke color'), fill(hex_value, label='#:')]
    if alpha is not None:
        steps.append(fill(alpha, title='Enter A “Alpha” Value (0-100)'))
    return steps + [T('Commit To This Color Selection')]


def palette(index, stroke=False):
    """Click one swatch of the bottom palette (15-pixel squares after a 4-pixel border)."""
    step = {'do': 'pointer-on', 'title': 'Click to change fill color, shift-click to change stroke color',
            'x': 11.5 + 15 * index, 'y': 11}
    if stroke:
        step['modifiers'] = ['Shift']
    return step


def flyout(group, tool):
    """Choose a tool from a tool group: activate the group, open it, pick the tool."""
    return [T(group), T(group), T(tool)]


def click(x, y, modifiers=None, count=1):
    step = {'op': 'pointer', 'target': {'document': True}, 'x': x, 'y': y}
    if modifiers:
        step['modifiers'] = modifiers
    if count != 1:
        step['click_count'] = count
    return step


def selecting(*points):
    """Preparation: select the elements at these document points (the first by click, others by Shift+click)."""
    steps = [click(*points[0])]
    steps += [click(*p, modifiers=['Shift']) for p in points[1:]]
    return steps


ALL = [{'op': 'pointer', 'target': {'document': True}, 'x': 630, 'y': 470}, {'op': 'press', 'key': 'a'}]


# -- program companions -------------------------------------------------------------------------------------
def element(ident, *parts):
    return {'type': 'element', 'id': ident, 'parts': list(parts or ('outline',))}


def new(*parts, index=-1):
    return {'type': 'new', 'index': index, 'parts': list(parts)}


def raw_new(*attrs):
    return {'type': 'raw', 'attrs': list(attrs)}


def raw(ident, *attrs):
    return {'type': 'raw', 'id': ident, 'attrs': list(attrs)}


def multi(**checks):
    return {'type': 'multi', 'checks': checks}


TOP = {'type': 'top', 'parts': ['outline']}
LAYERS = {'type': 'layers'}
ROOT = {'type': 'root'}
DOCUMENT = {'type': 'document'}
COUNT = {'type': 'count'}


def be(name, requirement, check, tol=None, requires=()):
    return {'name': name, 'requirement': requirement, 'check': check, 'tol': tol, 'requires': list(requires)}


def cp(cid, goal, acceptance, fixture, recipe, checks=(), prep=(), requires=()):
    return {'id': cid, 'goal': goal, 'acceptance': acceptance, 'fixture_svg': fixture, 'steps': list(prep),
            'recipe': list(recipe), 'checks': list(checks), 'requires': list(requires)}


# Companions whose expected state is the starting state (the element that stays put during an alignment, the
# untouched end of a line, the outline kept by reorient, the drawing restored by undo) count only together with a
# point of the same goal that verifies a change.
UNCHANGED = {
    'gui-geometry/line/start': 'gui-geometry/line/end',
    'gui-align/left/small': 'gui-align/left/medium', 'gui-align/right/large': 'gui-align/right/small',
    'gui-align/top/small': 'gui-align/top/medium', 'gui-align/bottom/large': 'gui-align/bottom/small',
    'gui-align-relative/largest-bottom/large': 'gui-align-relative/largest-bottom/small',
    'gui-align-relative/smallest-top/small': 'gui-align-relative/smallest-top/medium',
    'gui-align-relative/distribute-h/small': 'gui-align-relative/distribute-h/medium',
    'gui-align-relative/distribute-h/large': 'gui-align-relative/distribute-h/medium',
    'gui-align-relative/distribute-v/small': 'gui-align-relative/distribute-v/medium',
    'gui-align-relative/distribute-v/large': 'gui-align-relative/distribute-v/medium',
    'gui-flip-convert/reorient/outline': 'gui-flip-convert/reorient/no-rotation',
    'gui-clipboard/undo/restored': 'gui-clipboard/redo/moved',
}


def episode(key, feature, checkpoints, files=()):
    out = []
    for c in checkpoints:
        assertions = [{'id': f'{key}/{c["id"]}/visible', 'channel': 'frontend', 'method': 'agent',
                       'requirement': c['acceptance']}]
        if c['requires']:
            assertions[0]['requires'] = [f'{key}/{r}' for r in c['requires']]
        for b in c['checks']:
            check = dict(b['check'])
            if b['tol'] is not None:
                check['tol'] = b['tol']
            a = {'id': f'{key}/{c["id"]}/{b["name"]}', 'channel': 'backend', 'method': 'program',
                 'requirement': b['requirement'], 'check': check}
            if b['requires']:
                a['requires'] = [f'{key}/{r}' for r in b['requires']]
            elif a['id'] in UNCHANGED:
                a['requires'] = [UNCHANGED[a['id']]]
            assertions.append(a)
        out.append({'id': c['id'], 'goal': c['goal'], 'fixture_svg': c['fixture_svg'], 'steps': c['steps'],
                    'recipe': c['recipe'], 'assertions': assertions, 'depends_on': ['setup:editor']})
    n = len(out)
    return {'id': key, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL,
            'setup': [{'id': 'editor'}], 'inputs': {'files': list(files)}, 'session': SESSION,
            'allowed_equivalents': EQUIVALENTS, 'forbidden_bypasses': BYPASSES,
            'budget': {'calls': 30 + 30 * n, 'tokens': 400_000 + 500_000 * n, 'seconds': 300 + 240 * n},
            'checkpoints': out}


E = F.EMPTY
R, RP = F.G_RECT, F.G_RECT_POINT
M, MP = F.G_MULTI, F.G_MULTI_POINTS


# -- drawing tools ------------------------------------------------------------------------------------------
def draw_shapes():
    return episode('gui-draw-shapes', 'drawing', [
        cp('rect', 'Draw a rectangle with the rectangle tool of the tool bar.',
           'A new rectangle appears on the drawing.', E, [T('Square/Rect Tool'), ddrag(200, 150, 360, 260)],
           [be('kind', 'One new rectangle exists.', new())]),
        cp('square', 'Draw a square with the square tool (in the rectangle tool group).',
           'A new square (equal width and height) appears on the drawing.', E,
           [*flyout('Square/Rect Tool', 'Square Tool'), ddrag(200, 150, 330, 250)],
           [be('square', 'The new rectangle has equal width and height.', new('shape'))]),
        cp('freehand-rect', 'Draw a rectangle with the free-hand rectangle tool (in the rectangle tool group).',
           'A new rectangle appears on the drawing.', E,
           [*flyout('Square/Rect Tool', 'Free-Hand Rectangle'), ddrag(200, 150, 360, 260)],
           [be('kind', 'One new rectangle exists.', new())]),
        cp('ellipse', 'Draw an ellipse with the ellipse tool.', 'A new ellipse appears on the drawing.', E,
           [T('Ellipse/Circle Tool'), ddrag(300, 220, 400, 280)],
           [be('kind', 'One new ellipse exists.', new())]),
        cp('circle', 'Draw a circle with the circle tool (in the ellipse tool group).',
           'A new circle appears on the drawing.', E,
           [*flyout('Ellipse/Circle Tool', 'Circle'), ddrag(300, 220, 360, 280)],
           [be('kind', 'One new circle exists.', new('shape'))]),
        cp('freehand-ellipse', 'Draw an ellipse with the free-hand ellipse tool (in the ellipse tool group).',
           'A new ellipse appears on the drawing.', E,
           [*flyout('Ellipse/Circle Tool', 'Free-Hand Ellipse'), ddrag(240, 180, 420, 300)],
           [be('kind', 'One new ellipse exists.', new())]),
    ])


def draw_lines():
    return episode('gui-draw-lines', 'drawing', [
        cp('line', 'Draw a straight line with the line tool.', 'A new straight line appears on the drawing.', E,
           [T('Line Tool [L]'), ddrag(120, 300, 420, 180)],
           [be('kind', 'One new line exists.', new())]),
        cp('pencil', 'Draw a free-hand stroke with the pencil tool.', 'A new free-hand stroke appears.', E,
           [T('Pencil Tool [Q]'), ddrag(120, 300, 420, 200, via=[[180, 240], [260, 280], [340, 220]])],
           [be('stroke', 'One new open path without fill exists.', new('paint'))]),
        cp('triangle', 'With the path tool, draw a closed triangle (three corners, closed by clicking the first '
                       'corner again).', 'A new closed triangle appears.', E,
           [T('Path Tool [P]'), dclick(200, 300), dclick(400, 300), dclick(300, 140), dclick(200, 300),
            {'do': 'wait', 'seconds': 0.5}],
           [be('closed', 'One new closed path of three straight segments exists.', new('shape'))]),
        cp('text', 'Add the text "Lighthouse" to the drawing with the text tool.',
           'The text "Lighthouse" appears on the drawing.', E,
           [T('Text Tool [T]'), dclick(320, 240), {'do': 'type', 'value': 'Lighthouse'}, press('Escape')],
           [be('content', 'A new text element contains "Lighthouse".', {'type': 'text', 'parts': ['text']})]),
        cp('image-url', 'Insert an image with the image tool at (200, 150), giving it the address ' + F.TILE + ' .',
           'A small blue image appears at (200, 150).', E,
           [answer(F.TILE), T('Image Tool'), ddrag(200, 150, 360, 270)],
           [be('address', 'The new image uses the given address.', raw_new('link:href'))]),
        cp('image', 'Insert an image with the image tool; accept the image address the editor proposes.',
           'A new image appears on the drawing.', E,
           [T('Image Tool'), ddrag(240, 160, 400, 320)],
           [be('kind', 'One new image element exists.', new())]),
    ])


def polystar():
    return episode('gui-polystar', 'drawing', [
        cp('star', 'Draw a star with the star tool (in the polygon/star tool group) using its default settings.',
           'A new five-pointed star appears.', E,
           [*flyout('Polygone/Star Tool', 'Star Tool'), ddrag(320, 240, 400, 240)],
           [be('points', 'The new star has 10 corners (5 points).', new('shape'))]),
        cp('star-7', 'Draw a star with 7 points (set the number of points before drawing).',
           'A new seven-pointed star appears.', E,
           [*flyout('Polygone/Star Tool', 'Star Tool'), fill(7, label='points'), ddrag(320, 240, 400, 240)],
           [be('points', 'The new star has 14 corners (7 points).', new('shape'))]),
        cp('hexagon', 'Draw a regular hexagon with the polygon tool (6 sides).', 'A new hexagon appears.', E,
           [*flyout('Polygone/Star Tool', 'Polygon Tool'), fill(6, label='sides'), ddrag(320, 240, 400, 240)],
           [be('points', 'The new polygon has 6 corners.', new('shape'))]),
        cp('triangle', 'Draw a regular triangle with the polygon tool (3 sides).', 'A new triangle appears.', E,
           [*flyout('Polygone/Star Tool', 'Polygon Tool'), fill(3, label='sides'), ddrag(320, 240, 400, 240)],
           [be('points', 'The new polygon has 3 corners.', new('shape'))]),
        cp('pointiness', 'Draw a five-pointed star with pointiness 1.5 by dragging from its centre (320, 240) to '
                         '(400, 240).', 'A new, rather blunt five-pointed star appears.', E,
           [*flyout('Polygone/Star Tool', 'Star Tool'), fill(1.5, label='Pointiness'), ddrag(320, 240, 400, 240)],
           [be('outline', 'The star\'s inner corners lie on a circle 1.5 times smaller than its outer corners.',
               new('corners'), tol=0.5)]),
        cp('radial-shift', 'Draw a five-pointed star with a radial shift of 20 by dragging from its centre (320, 240) '
                           'to (400, 240).', 'A new, twisted five-pointed star appears.', E,
           [*flyout('Polygone/Star Tool', 'Star Tool'), fill(20, label='Radial Shift'), ddrag(320, 240, 400, 240)],
           [be('outline', 'The star\'s inner corners are twisted by the radial shift.', new('corners'), tol=0.5)]),
    ])


SHAPE_CATEGORIES = ['basic', 'animal', 'arrow', 'dialog_balloon', 'electronics', 'flowchart', 'game', 'math', 'misc',
                    'music', 'object', 'raphael_1', 'raphael_2', 'symbol']


def shape_library(key, categories):
    def goal(category):
        if category == 'basic':
            return ('Open the shape library and draw its first "basic" shape (the heart) by dragging from (250, 180) '
                    'to (390, 300).', [T('Shape library [null]')])
        return (f'Open the shape library, switch to the "{category}" category and draw its first shape by dragging '
                'from (250, 180) to (390, 300).', [T('Shape library [null]'), X(category)])
    cps = []
    for category in categories:
        text, steps = goal(category)
        cps.append(cp(category.replace('_', '-'), text, f'A new shape from the {category} category appears on the '
                                                        'drawing.', E,
                      steps + [{'do': 'click-nth', 'title': 'title', 'nth': 0}, ddrag(250, 180, 390, 300)],
                      [be('shape', f'One new path with the outline of the first {category} shape is drawn into the '
                                   'dragged box.', new('shape'))]))
    return episode(key, 'drawing', cps)


def eyedropper():
    pair = F.doc('<rect id="ea" x="100" y="120" width="160" height="110" fill="#e69138" stroke="#38761d" '
                 'stroke-width="8"/><ellipse id="eb" cx="450" cy="300" rx="90" ry="60" fill="#cccccc"/>')
    return episode('gui-eyedropper', 'style', [
        cp('copy', 'The orange rectangle is selected. Use the eye dropper tool to give the grey ellipse the '
                   'rectangle\'s fill and stroke.',
           'The ellipse now has the rectangle\'s orange fill and green stroke.', pair,
           [T('Eye Dropper Tool [ctrl+I]'), dclick(450, 300)],
           [be('paint', 'The ellipse has the rectangle\'s fill, stroke and stroke width.', element('eb', 'paint'))],
           prep=selecting((180, 175))),
    ])


# -- paint -----------------------------------------------------------------------------------------------------
def paint_fill():
    return episode('gui-paint-fill', 'style', [
        cp('hex', 'The rectangle is selected. Set its fill colour to #2e8b57 with the fill colour picker.',
           'The rectangle is filled with sea green (#2e8b57).', R, picker('fill', '2e8b57'),
           [be('fill', 'The rectangle\'s fill is #2e8b57.', element('gr', 'paint'))], prep=selecting(RP)),
        cp('palette', 'The rectangle is selected. Make its fill yellow by clicking the yellow swatch of the colour '
                      'palette.', 'The rectangle is filled with yellow.', R, [palette(8)],
           [be('fill', 'The rectangle\'s fill is #ffff00.', element('gr', 'paint'))], prep=selecting(RP)),
        cp('none', 'The rectangle is selected. Remove its fill (no fill) using the palette.',
           'The rectangle has no fill; only its outline remains.', R, [palette(0)],
           [be('fill', 'The rectangle has no fill.', element('gr', 'paint'))], prep=selecting(RP)),
        cp('alpha', 'The rectangle is selected. In the fill colour picker keep the colour but set its alpha to 50 %.',
           'The rectangle\'s fill is half transparent.', R, picker('fill', '3366cc', alpha=50),
           [be('opacity', 'The rectangle\'s fill opacity is 0.5.', element('gr', 'paint'), tol=0.01)],
           prep=selecting(RP)),
        cp('rgb', 'The rectangle is selected. In the fill colour picker set R 200, G 100 and B 0.',
           'The rectangle is filled with orange-brown (#c86400).', R,
           [T('Change fill color'), fill(200, title='Enter A “Red” Value (0-255)'),
            fill(100, title='Enter A “Green” Value (0-255)'), fill(0, title='Enter A “Blue” Value (0-255)'),
            T('Commit To This Color Selection')],
           [be('fill', 'The rectangle\'s fill is #c86400.', element('gr', 'paint'))], prep=selecting(RP)),
        cp('hsv', 'The rectangle is selected. In the fill colour picker set H 120, S 100 and V 50.',
           'The rectangle is filled with dark green (pure green at half brightness).', R,
           [T('Change fill color'), fill(120, title='Enter A “Hue” Value (0-360°)'),
            fill(100, title='Enter A “Saturation” Value (0-100%)'), fill(50, title='Enter A “Value” Value (0-100%)'),
            T('Commit To This Color Selection')],
           [be('fill', 'The rectangle\'s fill is pure green at half brightness (#007f00 or #008000).',
               element('gr', 'paint'))], prep=selecting(RP)),
    ])


def paint_stroke():
    return episode('gui-paint-stroke', 'style', [
        cp('hex', 'The rectangle is selected. Set its stroke colour to #ff00ff with the stroke colour picker.',
           'The rectangle\'s outline is magenta.', R, picker('stroke', 'ff00ff'),
           [be('stroke', 'The rectangle\'s stroke is #ff00ff.', element('gr', 'paint'))], prep=selecting(RP)),
        cp('palette', 'The rectangle is selected. Make its stroke orange by Shift-clicking the orange swatch of the '
                      'palette.', 'The rectangle\'s outline is orange.', R, [palette(7, stroke=True)],
           [be('stroke', 'The rectangle\'s stroke is #ff7f00.', element('gr', 'paint'))], prep=selecting(RP)),
        cp('none', 'The rectangle is selected. Remove its stroke (set the stroke to "none", not to a transparent '
                   'colour).', 'The rectangle has no outline.', R,
           [palette(0, stroke=True)],
           [be('stroke', 'The rectangle has no stroke.', element('gr', 'paint'))], prep=selecting(RP)),
        cp('alpha', 'The rectangle is selected. In the stroke colour picker keep the colour but set its alpha to 50 %.',
           'The rectangle\'s outline is half transparent.', R, picker('stroke', '1a1a1a', alpha=50),
           [be('opacity', 'The rectangle\'s stroke opacity is 0.5.', element('gr', 'paint'), tol=0.01)],
           prep=selecting(RP)),
        cp('width', 'The rectangle is selected. Set its stroke width to 12.', 'The rectangle\'s outline is thicker.',
           R, [fill(12, context='Change stroke width by 1, shift-click to change by 0.1')],
           [be('width', 'The rectangle\'s stroke width is 12.', element('gr', 'paint'))], prep=selecting(RP)),
    ])


def gradients():
    def grad(kind):
        return [T('Change fill color'), X(kind)]
    commit = [{'do': 'click', 'text': 'OK', 'tag': 'input'}]
    return episode('gui-gradients', 'style', [
        cp('linear', 'The rectangle is selected. Fill it with a linear gradient (default gradient settings).',
           'The rectangle shows a linear colour gradient.', R, grad('Linear Gradient') + commit,
           [be('server', 'The rectangle is filled with a linear gradient.', element('gr', 'server'))],
           prep=selecting(RP)),
        cp('radial', 'The rectangle is selected. Fill it with a radial gradient (default gradient settings).',
           'The rectangle shows a radial colour gradient.', R, grad('Radial Gradient') + commit,
           [be('server', 'The rectangle is filled with a radial gradient.', element('gr', 'server'))],
           prep=selecting(RP)),
        # The vector spans only the left half, so the spread method decides what fills the right half.
        cp('reflect', 'The rectangle is selected. Fill it with a linear gradient whose end point is (0.5, 0) and '
                      'whose spread method is "Reflect".',
           'The gradient runs across the rectangle\'s left half and is mirrored back across its right half.', R,
           grad('Linear Gradient') + [fill('0.5', title='Enter ending x value between 0.0 and 1.0'),
                                      select_option('reflect', context='Change fill color', options=True)] + commit,
           [be('spread', 'The linear gradient ends half way across and spreads with "reflect".',
               element('gr', 'server'))],
           prep=selecting(RP)),
        cp('repeat', 'The rectangle is selected. Fill it with a linear gradient whose end point is (0.5, 0) and '
                     'whose spread method is "Repeat".',
           'The gradient runs across the rectangle\'s left half and starts over across its right half.', R,
           grad('Linear Gradient') + [fill('0.5', title='Enter ending x value between 0.0 and 1.0'),
                                      select_option('repeat', context='Change fill color', options=True)] + commit,
           [be('spread', 'The linear gradient ends half way across and spreads with "repeat".',
               element('gr', 'server'))],
           prep=selecting(RP)),
        cp('vertical', 'The rectangle is selected. Fill it with a vertical linear gradient: begin point (0, 0), '
                       'end point (0, 1).', 'The rectangle\'s gradient runs from top to bottom.', R,
           grad('Linear Gradient') + [fill('0', title='Enter ending x value between 0.0 and 1.0'),
                                      fill('1', title='Enter ending y value between 0.0 and 1.0')] + commit,
           [be('vector', 'The gradient vector runs from (0, 0) to (0, 1).', element('gr', 'server'))],
           prep=selecting(RP)),
        cp('radius', 'The rectangle is selected. Fill it with a radial gradient whose radius is 30 %.',
           'The rectangle shows a small radial gradient.', R,
           grad('Radial Gradient') + [fill(30, label='%', context='Change fill color', nth=0)] + commit,
           [be('radius', 'The radial gradient\'s radius is 0.3.', element('gr', 'server'), tol=0.01)],
           prep=selecting(RP)),
    ])


# The line join and cap lists show the current value as their title; their panel context is stable.
# The join and cap list buttons are named after their current value (a div at first, an image after a choice).
JOIN = {'do': 'click', 'title': 'Linejoin:', 'prefix': True, 'tag': ['div', 'img']}
CAP = {'do': 'click', 'title': 'Linecap:', 'prefix': True, 'tag': ['div', 'img']}


# The text anchor list shows the current anchor as its title.
# A list opened by its button stays open after a choice and swallows the next click on the canvas, so recipes click
# the button again to close it before selecting the next element.
ANCHOR = {'do': 'click', 'title': 'Align the text in', 'prefix': True, 'tag': 'img'}


def item(title):
    return {'do': 'click', 'title': title, 'tag': 'se-list-item'}


def stroke_style():
    lines, lp = F.G_LINES, F.G_LINE_POINTS
    poly, pp = F.G_POLYLINES, F.G_POLYLINE_POINTS
    dashes = [('dotted', '...', '2,2'), ('dashed', '--', '5,5'), ('dash-dot', '-.', '5,2,2,2'),
              ('dash-dot-dot', '-..', '5,2,2,2,2,2')]
    first = selecting(lp['ln0'])
    cps = [cp(name, f'The first line is selected. Give it the {name} stroke style ({label}).',
              f'The first line is drawn {name}.', lines, [select_option(value, title='Change stroke dash style')],
              [be('dash', f'The first line has the {name} dash pattern.', element('ln0', 'paint'))], prep=first)
           for name, label, value in dashes]
    cps += [
        cp('solid', 'The dashed line is selected. Make its stroke solid again (no dash pattern).',
           'The line is drawn solid.', F.G_STYLED, [select_option('none', title='Change stroke dash style')],
           [be('dash', 'The line has no dash pattern.', element('sd', 'paint'))],
           prep=selecting(F.G_STYLED_POINTS['sd'])),
        cp('join-round', 'The upper zig-zag line is selected. Give it round line joins.',
           'The corners of the upper zig-zag are rounded.', poly, [JOIN, item('Linejoin: Round'), JOIN],
           [be('join', 'The upper line has round joins.', element('pa', 'paint'))], prep=selecting(pp['pa'])),
        cp('join-bevel', 'The upper zig-zag line is selected. Give it bevel line joins.',
           'The corners of the upper zig-zag are cut off.', poly, [JOIN, item('Linejoin: Bevel'), JOIN],
           [be('join', 'The upper line has bevel joins.', element('pa', 'paint'))], prep=selecting(pp['pa'])),
        cp('join-miter', 'The zig-zag line with round joins is selected. Give it miter (pointed) joins.',
           'The corners of the zig-zag are pointed.', F.G_STYLED, [JOIN, item('Linejoin: Miter'), JOIN],
           [be('join', 'The line has miter joins.', element('sj', 'paint'))],
           prep=selecting(F.G_STYLED_POINTS['sj'])),
        cp('cap-round', 'The first line is selected. Give it round line caps.',
           'The ends of the first line are rounded.', lines, [CAP, item('Linecap: Round'), CAP],
           [be('cap', 'The first line has round caps.', element('ln0', 'paint'))], prep=first),
        cp('cap-square', 'The first line is selected. Give it square line caps.',
           'The ends of the first line are squared off beyond its end points.', lines,
           [CAP, item('Linecap: Square'), CAP],
           [be('cap', 'The first line has square caps.', element('ln0', 'paint'))], prep=first),
        cp('cap-butt', 'The line with round caps is selected. Give it butt (flat) caps.',
           'The ends of the line are cut flat at its end points.', F.G_STYLED, [CAP, item('Linecap: Butt'), CAP],
           [be('cap', 'The line has butt caps.', element('sc', 'paint'))], prep=selecting(F.G_STYLED_POINTS['sc'])),
    ]
    return episode('gui-stroke-style', 'style', cps)


def effects():
    group = F.G_GROUP
    return episode('gui-effects', 'style', [
        cp('opacity', 'The rectangle is selected. Set its opacity to 40 %.', 'The rectangle is see-through.', R,
           [fill(40, context='Change selected item opacity')],
           [be('opacity', 'The rectangle\'s opacity is 0.4.', element('gr', 'paint'), tol=0.01)], prep=selecting(RP)),
        cp('blur', 'The rectangle is selected. Give it a gaussian blur of 50.',
           'The rectangle looks clearly blurred (soft, fuzzy edges).', R,
           [fill(50, context='Change gaussian blur value')],
           [be('blur', 'The rectangle gets a gaussian blur filter whose deviation SVG-edit derives from the blur '
                       'value 50 (5).', element('gr', 'blur'))],
           prep=selecting(RP)),
        cp('radius', 'The rectangle is selected. Give it rounded corners with a corner radius of 25.',
           'The rectangle\'s corners are rounded.', R, [fill(25, context='Change Rectangle Corner Radius')],
           [be('radius', 'The rectangle\'s corner radius is 25.', raw('gr', 'rx', 'ry'))], prep=selecting(RP)),
        cp('angle', 'The rectangle is selected. Rotate it by 30 degrees with the rotation angle field.',
           'The rectangle is turned by 30 degrees.', R, [fill(30, context='Change rotation angle')],
           [be('rotation', 'The rectangle is rotated 30 degrees about its centre.', element('gr', 'outline'), tol=0.1)],
           prep=selecting(RP)),
        cp('group-opacity', 'The group (a rectangle and a circle) is selected. Set the group\'s opacity to 50 %.',
           'Both shapes of the group are half transparent.', group, [fill(50, context='Change selected item opacity')],
           [be('opacity', 'The group carries opacity 0.5; its children keep theirs.',
               multi(group=raw('gg', 'opacity'), child=raw('gga', 'opacity')))], prep=selecting((260, 205))),
    ])


def markers():
    line, poly = F.G_LINES, F.G_POLYLINES

    def marker(position, kind):
        # Each marker list shows its current marker as title; its panel context names the position.
        return [{'do': 'click', 'context': f'tools.{position}_marker_list_opts', 'tag': 'div'},
                {'do': 'click', 'title': f'tools.mkr_{kind}', 'context': f'tools.{position}_marker_list_opts',
                 'tag': 'se-list-item'}]
    return episode('gui-markers', 'style', [
        cp('end-arrow', 'The first line is selected. Put an arrow head (right arrow marker) at its end.',
           'The first line ends in an arrow head.', line, marker('end', 'rightarrow'),
           [be('marker', 'The line has a right-arrow end marker and no other marker.', element('ln0', 'markers'))],
           prep=selecting(F.G_LINE_POINTS['ln0'])),
        cp('start-circle', 'The first line is selected. Put a filled circle marker at its start.',
           'The first line starts with a filled circle.', line, marker('start', 'mcircle'),
           [be('marker', 'The line has a circle start marker and no other marker.', element('ln0', 'markers'))],
           prep=selecting(F.G_LINE_POINTS['ln0'])),
        cp('mid-box', 'The upper zig-zag line is selected. Put a box marker at each of its middle corners.',
           'Boxes are drawn at the middle corners of the zig-zag line.', poly, marker('mid', 'box'),
           [be('marker', 'The zig-zag line has box mid markers and no other marker.', element('pa', 'markers'))],
           prep=selecting(F.G_POLYLINE_POINTS['pa'])),
        cp('start-open-arrow', 'The first line is selected. Put an open left arrow marker at its start.',
           'The first line starts with an open arrow.', line, marker('start', 'leftarrow_o'),
           [be('marker', 'The line has an open left-arrow start marker and no other marker.',
               element('ln0', 'markers'))], prep=selecting(F.G_LINE_POINTS['ln0'])),
        cp('end-open-box', 'The first line is selected. Put an open box marker at its end.',
           'The first line ends in an open box.', line, marker('end', 'box_o'),
           [be('marker', 'The line has an open box end marker and no other marker.', element('ln0', 'markers'))],
           prep=selecting(F.G_LINE_POINTS['ln0'])),
        cp('end-open-circle', 'The second line is selected. Put an open circle marker at its end.',
           'The second line ends in an open circle.', line, marker('end', 'mcircle_o'),
           [be('marker', 'The line has an open circle end marker and no other marker.', element('ln1', 'markers'))],
           prep=selecting(F.G_LINE_POINTS['ln1'])),
        cp('end-open-arrow', 'The first line is selected. Put an open right arrow marker at its end.',
           'The first line ends in an open arrow head.', line, marker('end', 'rightarrow_o'),
           [be('marker', 'The line has an open right-arrow end marker and no other marker.',
               element('ln0', 'markers'))], prep=selecting(F.G_LINE_POINTS['ln0'])),
        cp('start-arrow', 'The lower zig-zag line is selected. Put a left arrow marker at its start.',
           'The lower zig-zag starts with an arrow.', poly, marker('start', 'leftarrow'),
           [be('marker', 'The line has a left-arrow start marker and no other marker.', element('pb', 'markers'))],
           prep=selecting(F.G_POLYLINE_POINTS['pb'])),
        cp('mid-circle', 'The lower zig-zag line is selected. Put filled circle markers at its middle corners.',
           'Circles are drawn at the middle corners of the lower zig-zag.', poly, marker('mid', 'mcircle'),
           [be('marker', 'The line has circle mid markers and no other marker.', element('pb', 'markers'))],
           prep=selecting(F.G_POLYLINE_POINTS['pb'])),
        cp('remove', 'The first line is selected. Put a right arrow marker at its end, then remove it again (no '
                     'marker).', 'The first line has no marker.', line,
           # The marker list stays open after a choice, so the second choice is made in the open list.
           marker('end', 'rightarrow') + marker('end', 'nomarker')[1:],
           [be('marker', 'The line has no marker.', element('ln0', 'markers'), requires=['end-arrow/marker'])],
           prep=selecting(F.G_LINE_POINTS['ln0']), requires=['end-arrow/marker']),
    ])


# -- geometry and identity fields ---------------------------------------------------------------------------------
def geometry():
    circle = F.doc('<circle id="gc" cx="200" cy="200" r="60" fill="#cc9933"/>')
    ellipse = F.doc('<ellipse id="ge" cx="320" cy="240" rx="120" ry="60" fill="#cc6633"/>')
    line = F.doc('<line id="gl" x1="100" y1="100" x2="300" y2="200" stroke="#222222" stroke-width="6"/>')
    return episode('gui-geometry', 'geometry', [
        cp('position', 'The rectangle is selected. Move it to x 100, y 80 with the position fields.',
           'The rectangle\'s top-left corner is at (100, 80).', R, [fill(100, label='x'), fill(80, label='y')],
           [be('x', 'The rectangle\'s left edge is at x 100.', {'type': 'box', 'id': 'gr', 'facet': 'x'}),
            be('y', 'The rectangle\'s top edge is at y 80.', {'type': 'box', 'id': 'gr', 'facet': 'y'})],
           prep=selecting(RP)),
        cp('size', 'The rectangle is selected. Make it 260 wide and 90 high with the size fields.',
           'The rectangle is 260 by 90.', R, [fill(260, label='w'), fill(90, label='h')],
           [be('width', 'The rectangle is 260 wide.', {'type': 'box', 'id': 'gr', 'facet': 'width'}),
            be('height', 'The rectangle is 90 high.', {'type': 'box', 'id': 'gr', 'facet': 'height'})],
           prep=selecting(RP)),
        cp('circle', 'The circle is selected. Set its centre to (300, 260) and its radius to 90.',
           'The circle is larger and centred at (300, 260).', circle,
           [fill(300, label='cx'), fill(260, label='cy'), fill(90, label='r')],
           [be('centre-x', 'The circle\'s centre is at x 300.', {'type': 'box', 'id': 'gc', 'facet': 'cx'}),
            be('centre-y', 'The circle\'s centre is at y 260.', {'type': 'box', 'id': 'gc', 'facet': 'cy'}),
            be('radius', 'The circle\'s radius is 90.', {'type': 'box', 'id': 'gc', 'facet': 'rx'})],
           prep=selecting((200, 200))),
        cp('ellipse', 'The ellipse is selected. Set its horizontal radius to 60 and its vertical radius to 150.',
           'The ellipse is now taller than wide.', ellipse, [fill(60, label='rx'), fill(150, label='ry')],
           [be('rx', 'The ellipse\'s horizontal radius is 60.', {'type': 'box', 'id': 'ge', 'facet': 'rx'}),
            be('ry', 'The ellipse\'s vertical radius is 150.', {'type': 'box', 'id': 'ge', 'facet': 'ry'})],
           prep=selecting((320, 240))),
        cp('line', 'The line is selected. Move its end point to (500, 100).', 'The line ends at (500, 100).', line,
           [fill(500, label='x2'), fill(100, label='y2')],
           [be('start', 'The line still starts at (100, 100).', {'type': 'ends', 'id': 'gl', 'facet': 'start'}),
            be('end', 'The line ends at (500, 100).', {'type': 'ends', 'id': 'gl', 'facet': 'end'})],
           prep=selecting((200, 150))),
        cp('image', 'The image is selected. Make it 160 wide and 120 high.', 'The image is 160 by 120.', F.G_IMAGE,
           [fill(160, label='w'), fill(120, label='h')],
           [be('width', 'The image is 160 wide.', {'type': 'box', 'id': 'gi', 'facet': 'width'}),
            be('height', 'The image is 120 high.', {'type': 'box', 'id': 'gi', 'facet': 'height'})],
           prep=selecting((280, 210))),
        cp('path-position', 'The triangle path is selected. Move it to x 300, y 300 with the position fields.',
           'The triangle\'s bounding box starts at (300, 300).', M, [fill(300, label='x'), fill(300, label='y')],
           [be('x', 'The triangle\'s left edge is at x 300.', {'type': 'box', 'id': 'mp', 'facet': 'x'}),
            be('y', 'The triangle\'s top edge is at y 300.', {'type': 'box', 'id': 'mp', 'facet': 'y'})],
           prep=selecting(MP['mp'])),
        cp('group-position', 'The group (brown rectangle and green circle) is selected. Move it to x 40, y 40 with the '
                             'position fields.', 'The group\'s bounding box starts at (40, 40).', M,
           [fill(40, label='x'), fill(40, label='y')],
           [be('moved', 'Both members of the group moved together so that the group starts at (40, 40).',
               {'type': 'children', 'id': 'mgp', 'parts': ['outline']})], prep=selecting(MP['mgp'])),
    ])


def identity():
    return episode('gui-identity', 'geometry', [
        cp('id', 'The rectangle is selected. Change its id to "harbor-wall".',
           'The id field shows harbor-wall for the rectangle.', R, [fill('harbor-wall', label='id'), press('Enter')],
           [be('id', 'The rectangle\'s id is harbor-wall.', {'type': 'ids-present', 'ids': ['harbor-wall', 'gr']})],
           prep=selecting(RP), requires=['id/id']),
        cp('class', 'The rectangle is selected. Give it the class "wall".', 'The class field shows wall.', R,
           [fill('wall', label='class'), press('Enter')],
           [be('class', 'The rectangle\'s class is wall.', raw('gr', 'class'))], prep=selecting(RP),
           requires=['class/class']),
        cp('label', 'The group is selected. Give it the label "Garden bed".', 'The group\'s label shows Garden bed.',
           F.G_GROUP, [fill('Garden bed', label='label'), press('Enter')],
           [be('title', 'The group carries the title "Garden bed".', element('gg', 'title'))],
           prep=selecting((260, 205)), requires=['label/title']),
        cp('text-position', 'The text "Sample" is selected. Move it to x 100, y 400 with the position fields.',
           'The text now sits at the lower left.', M, [fill(100, label='x'), fill(400, label='y')],
           [be('position', 'The text is anchored at (100, 400).', element('mt'), tol=0.5)],
           prep=selecting(MP['mt'])),
    ])


# -- text ---------------------------------------------------------------------------------------------------------------
FONTS = ['Serif', 'Sans-serif', 'Cursive', 'Fantasy', 'Monospace', 'Courier', 'Helvetica', 'Times']


# Families the evaluation browser draws with the same face as the fixture's Verdana fallback: only the font field
# shows the change.
SAME_FACE = {'Serif', 'Cursive', 'Fantasy', 'Times'}


def font_family():
    texts, tp = F.G_TEXTS_PLAIN, F.G_TEXT_POINTS
    return episode('gui-font-family', 'text', [
        cp(font.lower(), f'The first line of text is selected. Set its font family to {font}.',
           f'The font field shows {font} while the first line is selected.' if font in SAME_FACE
           else f'The first line is shown in the {font} font.', texts,
           [select_option(font, label='Font:')],
           [be('family', f'The first line uses font family {font}.', element('tx0', 'font'))],
           prep=selecting(tp['tx0']), requires=[f'{font.lower()}/family'] if font in SAME_FACE else [])
        for font in FONTS])


def text_font():
    texts, tp = F.G_TEXTS, F.G_TEXT_POINTS
    first = selecting(tp['tx0'])
    return episode('gui-text-font', 'text', [
        cp('size', 'The first line of text is selected. Set its font size to 48.', 'The first line is larger.', texts,
           [fill(48, context='Change Font Size')],
           [be('size', 'The first line has font size 48.', element('tx0', 'font'))], prep=first),
        cp('bold', 'The first line of text is selected. Make it bold with the text style button.',
           'The first line is bold.', texts, [T('Bold Text [B]')],
           [be('bold', 'The first line is bold.', {'type': 'font', 'id': 'tx0', 'facet': 'font-weight'})],
           prep=first),
        cp('italic', 'The first line of text is selected. Make it italic with the text style button.',
           'The first line is italic.', texts, [T('Italic Text [I]')],
           [be('italic', 'The first line is italic.', {'type': 'font', 'id': 'tx0', 'facet': 'font-style'})],
           prep=first),
        cp('underline', 'The first line of text is selected. Underline it.', 'The first line is underlined.', texts,
           [T('Underline')],
           [be('decoration', 'The first line has text decoration underline.', element('tx0', 'font'))], prep=first),
        cp('line-through', 'The first line of text is selected. Strike it through.',
           'The first line is struck through.', texts, [T('Line-Through')],
           [be('decoration', 'The first line has text decoration line-through.', element('tx0', 'font'))],
           prep=first),
        cp('overline', 'The first line of text is selected. Give it an overline.', 'The first line has a line above '
                                                                                  'it.', texts, [T('Overline')],
           [be('decoration', 'The first line has text decoration overline.', element('tx0', 'font'))], prep=first),
    ])


def text_layout():
    texts, tp = F.G_TEXTS, F.G_TEXT_POINTS
    return episode('gui-text-layout', 'text', [
        cp('anchor-middle', 'The first line of text is selected. Anchor it at its middle (text anchor middle).',
           'The first line is centred on its anchor point.', texts,
           [ANCHOR, item('Align the text in middle'), ANCHOR],
           [be('anchor', 'The first line is anchored in the middle.', element('tx0', 'font'))],
           prep=selecting(tp['tx0'])),
        cp('anchor-end', 'The first line of text is selected. Anchor it at its end (text anchor end).',
           'The first line ends at its anchor point.', texts,
           [ANCHOR, item('Align the text in end'), ANCHOR],
           [be('anchor', 'The first line is anchored at its end.', element('tx0', 'font'))],
           prep=selecting(tp['tx0'])),
        cp('anchor-start', 'The centred text is selected. Anchor it at its start (text anchor start).',
           'The text now begins at its anchor point.', F.G_TEXT_MIDDLE,
           [ANCHOR, item('Align the text in start'), ANCHOR],
           [be('anchor', 'The text is anchored at its start.', element('tm', 'font'))],
           prep=selecting(F.G_TEXT_MIDDLE_POINT)),
        cp('letter', 'The first line of text is selected. Set its letter spacing to 6.',
           'The letters of the first line are spaced out.', texts, [fill(6, context='Change the letter spacing')],
           [be('spacing', 'The first line has letter spacing 6.', element('tx0', 'font'))], prep=selecting(tp['tx0'])),
        cp('word', 'The first line of text is selected. Set its word spacing to 20.',
           'The words of the first line are further apart.', texts, [fill(20, context='Change the word spacing')],
           [be('spacing', 'The first line has word spacing 20.', element('tx0', 'font'))], prep=selecting(tp['tx0'])),
        cp('length', 'The first line of text is selected. Make it exactly 300 wide by setting its text length to 300 '
                     'with length adjust "Spacing & Glyphs".', 'The first line is stretched to 300 units.', texts,
           [fill(300, context='Lets you specify the width of the space into which the text will draw'),
            select_option('spacingAndGlyphs', label='Length adjust')],
           [be('length', 'The first line has text length 300.', {'type': 'font', 'id': 'tx0', 'facet': 'textLength'}),
            be('adjust', 'The first line adjusts spacing and glyphs.',
               {'type': 'font', 'id': 'tx0', 'facet': 'lengthAdjust'})],
           prep=selecting(tp['tx0'])),
        cp('length-spacing', 'The first line of text is selected. Make it 300 wide by setting its text length to '
                             '300 with length adjust "Spacing" (only the gaps between letters grow).',
           'The letters of the first line are spread over 300 units.', texts,
           [fill(300, context='Lets you specify the width of the space into which the text will draw'),
            select_option('spacing', label='Length adjust')],
           [be('adjust', 'The first line has text length 300 and adjusts only the spacing.',
               multi(length={'type': 'font', 'id': 'tx0', 'facet': 'textLength'},
                     adjust={'type': 'font', 'id': 'tx0', 'facet': 'lengthAdjust'}))],
           prep=selecting(tp['tx0'])),
        cp('edit', 'Change the text of the first line from "Line 1" to "Harbor" by editing it on the drawing.',
           'The first line reads Harbor.', texts,
           [dclick(*tp['tx0'], click_count=2), press('ControlOrMeta+A'), {'do': 'type', 'value': 'Harbor'},
            press('Escape')],
           [be('content', 'The first line reads "Harbor".', {'type': 'textcontent', 'id': 'tx0'})]),
    ])


# -- arrange -----------------------------------------------------------------------------------------------------
THREE, TP = F.G_THREE, F.G_THREE_POINTS
ABC = [element(k) for k in ('ka', 'kb', 'kc')]


def align_checks(what):
    return [be(name, f'The {label} rectangle is {what}.', check)
            for name, label, check in zip(('small', 'medium', 'large'), ('small', 'medium', 'large'), ABC)]


def align_multi():
    rows = [('left', 'Align Left', 'aligned on the common left edge'),
            ('center', 'Align Center', 'centred on the common vertical centre line'),
            ('right', 'Align Right', 'aligned on the common right edge'),
            ('top', 'Align Top', 'aligned on the common top edge'),
            ('middle', 'Align Middle', 'centred on the common horizontal centre line'),
            ('bottom', 'Align Bottom', 'aligned on the common bottom edge')]
    return episode('gui-align', 'arrange', [
        cp(key, f'All three rectangles are selected. {button} them (relative to the selected objects).',
           f'The three rectangles are {what}.', THREE, [T(button)], align_checks(what), prep=ALL)
        for key, button, what in rows])


def align_relative():
    return episode('gui-align-relative', 'arrange', [
        cp('page-left', 'All three rectangles are selected. Align their left edges with the left edge of the page.',
           'The three rectangles touch the left edge of the page.', THREE,
           [select_option('page', label='relative to:'), T('Align Left')], align_checks('at the page\'s left edge'),
           prep=ALL),
        cp('largest-bottom', 'All three rectangles are selected. Align their bottoms with the bottom of the largest '
                             'rectangle.', 'The bottoms of all rectangles line up with the bottom of the largest (blue) '
                                           'rectangle, which stays in place.', F.G_THREE_MIXED,
           [select_option('largest', label='relative to:'), T('Align Bottom')],
           align_checks('aligned with the bottom of the largest rectangle'), prep=ALL),
        cp('smallest-top', 'All three rectangles are selected. Align their tops with the top of the smallest '
                           'rectangle.', 'The tops of all rectangles line up with the top of the smallest (red) '
                                         'rectangle, which stays in place.', F.G_THREE_MIXED,
           [select_option('smallest', label='relative to:'), T('Align Top')],
           align_checks('aligned with the top of the smallest rectangle'), prep=ALL),
        cp('distribute-h', 'All three rectangles are selected. Distribute them horizontally (equal gaps).',
           'The horizontal gaps between the rectangles are equal.', THREE, [T('tools.align_distrib_horiz')],
           align_checks('distributed with equal horizontal gaps'), prep=ALL),
        cp('distribute-v', 'All three rectangles are selected. Distribute them vertically (equal gaps).',
           'The vertical gaps between the rectangles are equal.', THREE, [T('tools.align_distrib_verti')],
           align_checks('distributed with equal vertical gaps'), prep=ALL),
        cp('single-right', 'The rectangle is selected. Align it to the right edge of the page with the '
                           'editor\'s align command (not the position fields).',
           'The rectangle touches the right edge of the page.', R,
           [T('Align Left'), {'do': 'click', 'title': 'Align Right', 'tag': 'se-list-item'}],
           [be('position', 'The rectangle\'s right edge is at the page\'s right edge.', element('gr'))],
           prep=selecting(RP)),
        cp('single-bottom', 'The rectangle is selected. Align it to the bottom edge of the page with the '
                            'editor\'s align command (not the position fields).',
           'The rectangle touches the bottom edge of the page.', R,
           [T('Align Left'), {'do': 'click', 'title': 'Align Bottom', 'tag': 'se-list-item'}],
           [be('position', 'The rectangle\'s bottom edge is at the page\'s bottom edge.', element('gr'))],
           prep=selecting(RP)),
        cp('single-top', 'The rectangle is selected. Align it to the top edge of the page with the '
                         'editor\'s align command (not the position fields).',
           'The rectangle touches the top edge of the page.', R,
           [T('Align Left'), {'do': 'click', 'title': 'Align Top', 'tag': 'se-list-item'}],
           [be('position', 'The rectangle\'s top edge is at the page\'s top edge.', element('gr'))],
           prep=selecting(RP)),
        cp('single-center', 'The rectangle is selected. Centre it horizontally on the page (align center) '
                            'with the editor\'s align command.',
           'The rectangle is centred between the left and right of the page.', F.G_RECT_OFF,
           [T('Align Left'), {'do': 'click', 'title': 'Align Center', 'tag': 'se-list-item'}],
           [be('position', 'The rectangle is horizontally centred on the page.', element('gr'))],
           prep=selecting(F.G_RECT_OFF_POINT)),
        cp('single-left', 'The rectangle is selected. Align it to the left edge of the page with the '
                          'editor\'s align command (not the position fields).',
           'The rectangle touches the left edge of the page.', R,
           [T('Align Left'), {'do': 'click', 'title': 'Align Left', 'tag': 'se-list-item'}],
           [be('position', 'The rectangle\'s left edge is at the page\'s left edge.', element('gr'))],
           prep=selecting(RP)),
        cp('single-middle', 'The rectangle is selected. Centre it vertically on the page (align middle) with '
                            'the editor\'s align command.',
           'The rectangle is centred between the top and bottom of the page.', R,
           [T('Align Left'), {'do': 'click', 'title': 'Align Middle', 'tag': 'se-list-item'}],
           [be('position', 'The rectangle is vertically centred on the page.', element('gr'))],
           prep=selecting(RP)),
    ])


def flip_convert():
    flips = ('fr', 'fe', 'fp', 'ft')
    sel = selecting(F.G_FLIP_POINT)
    conv = F.G_CONVERT
    first = [('vr', (100, 80)), ('vq', (260, 80)), ('ve', (440, 80)), ('vc', (100, 240))]
    second = [('vl', (265, 245)), ('vg', (440, 260)), ('vp', (150, 390))]

    def converting(items):
        steps = []
        for _, p in items:
            steps += [dclick(*p), T('Convert to Path')]
        return steps
    return episode('gui-flip-convert', 'arrange', [
        cp('flip-h', 'The group (rectangle, ellipse, triangle and the text "Sample") is selected. Flip it '
                     'horizontally.', 'The group is mirrored left to right (the text reads backwards).', F.G_FLIP,
           [T('Flip Horizontally')],
           [be(k, f'The {n} is mirrored horizontally about the group\'s centre.', element(k), tol=0.5)
            for k, n in zip(flips, ('rectangle', 'ellipse', 'triangle', 'text'))], prep=sel),
        cp('flip-v', 'The group (rectangle, ellipse, triangle and the text "Sample") is selected. Flip it '
                     'vertically.', 'The group is mirrored top to bottom (the text is upside down).', F.G_FLIP,
           [T('Flip Vertically')],
           [be(k, f'The {n} is mirrored vertically about the group\'s centre.', element(k), tol=0.5)
            for k, n in zip(flips, ('rectangle', 'ellipse', 'triangle', 'text'))], prep=sel),
        cp('flip-single', 'The triangle is selected. Flip it horizontally.', 'The triangle is mirrored left to right.',
           M, [T('Flip Horizontally')],
           [be('outline', 'The triangle is mirrored about its own centre.', element('mp'))], prep=selecting(MP['mp'])),
        cp('flip-single-v', 'The triangle is selected. Flip it vertically.', 'The triangle is mirrored top to bottom.',
           M, [T('Flip Vertically')],
           [be('outline', 'The triangle is mirrored about its own horizontal centre line.', element('mp'))],
           prep=selecting(MP['mp'])),
        cp('to-path-1', 'Convert the plain rectangle, the rounded rectangle, the ellipse and the circle to paths.',
           'The four shapes look the same but are now paths.', conv, converting(first),
           [be(k, f'The {n} is replaced by a path with the same outline.', {'type': 'converted', 'point': p})
            for (k, p), n in zip(first, ('rectangle', 'rounded rectangle', 'ellipse', 'circle'))]),
        cp('to-path-2', 'Convert the line, the triangle and the zig-zag line to paths.',
           'The three shapes look the same but are now paths.', conv, converting(second),
           [be(k, f'The {n} is replaced by a path with the same outline.', {'type': 'converted', 'point': p})
            for (k, p), n in zip(second, ('line', 'triangle', 'zig-zag line'))]),
        cp('reorient', 'The rotated path is selected. Reorient it so that its rotation becomes 0 while it keeps its '
                       'look.', 'The path looks the same and the rotation angle shows 0.',
           F.doc('<path id="rp" d="M260 200 L380 200 L320 290 Z" fill="#55aaaa" transform="rotate(25 320 245)"/>'),
           [T('Reorient path')],
           [be('outline', 'The path keeps its outline.', element('rp'), tol=0.1),
            be('no-rotation', 'The path no longer carries a rotation.', raw('rp', 'transform'))],
           prep=selecting((320, 230))),
    ])


def arrange():
    stack, sp = F.STACK, F.STACK_POINTS
    return episode('gui-arrange', 'arrange', [
        cp('group', 'All three rectangles are selected. Group them with the group button.',
           'The three rectangles are now one group.', stack, [T('Group Elements [G]')],
           [be('grouped', 'The three rectangles form one group, in their original order.', TOP)], prep=ALL),
        cp('ungroup', 'The group is selected. Ungroup it with the ungroup button.',
           'The rectangle and circle are separate again.', F.G_GROUP, [T('Ungroup Elements')],
           [be('ungrouped', 'The group\'s children are back in the layer.', TOP)], prep=selecting((260, 205))),
        cp('front', 'The bottom (red) rectangle is selected. Bring it to the front.',
           'The red rectangle is drawn above the others.', stack, [T('Bring to Front [Ctrl+Shift+]]')],
           [be('order', 'The red rectangle is last in the stacking order.', TOP)], prep=selecting(sp['sa'])),
        cp('back', 'The top (blue) rectangle is selected. Send it to the back.',
           'The blue rectangle is drawn below the others.', stack, [T('Send to Back [Ctrl+Shift+[]')],
           [be('order', 'The blue rectangle is first in the stacking order.', TOP)], prep=selecting(sp['sc'])),
        cp('forward', 'Bring the bottom (red) rectangle one step forward using the context menu.',
           'The red rectangle is now above the green one but below the blue one.', stack,
           [dclick(*sp['sa'], button='right'), {'do': 'click', 'text': 'Bring Forward', 'prefix': True}],
           [be('order', 'The red rectangle moved one step up in the stacking order.', TOP)]),
        cp('backward', 'Send the top (blue) rectangle one step backward using the context menu.',
           'The blue rectangle is now below the green one but above the red one.', stack,
           [dclick(*sp['sc'], button='right'), {'do': 'click', 'text': 'Send Backward', 'prefix': True}],
           [be('order', 'The blue rectangle moved one step down in the stacking order.', TOP)]),
    ])


def context_menu():
    stack, sp = F.STACK, F.STACK_POINTS

    def menu_item(x, y, text):
        return [dclick(x, y, button='right'), {'do': 'click', 'text': text, 'prefix': True}]
    return episode('gui-context-menu', 'arrange', [
        cp('cut', 'Cut the bottom (red) rectangle using its context menu (right-click it).',
           'The red rectangle is gone.', stack, menu_item(*sp['sa'], 'Cut'),
           [be('removed', 'The red rectangle is removed; the others stay.', TOP)]),
        cp('copy-paste', 'Copy the top (blue) rectangle with its context menu, then paste it with the context menu of '
                         'an empty spot at (520, 120).', 'A second blue rectangle appears.', stack,
           menu_item(*sp['sc'], 'Copy') + menu_item(520, 120, 'Paste'),
           [be('pasted', 'A copy of the blue rectangle with the same size and colour is added.',
               new('size', 'paint'))]),
        cp('delete', 'Delete the middle (green) rectangle using its context menu.', 'The green rectangle is gone.',
           stack, menu_item(*sp['sb'], 'Delete'),
           [be('removed', 'The green rectangle is removed; the others stay.', TOP)]),
        cp('group', 'All three rectangles are selected. Group them using the context menu.',
           'The three rectangles form one group.', stack, menu_item(*sp['sb'], 'Group'),
           [be('grouped', 'The three rectangles are inside one new group, in their stacking order.', TOP)],
           prep=ALL),
        cp('ungroup', 'The group is selected. Ungroup it using its context menu.',
           'The rectangle and the circle are separate again.', F.G_GROUP, menu_item(260, 205, 'Ungroup'),
           [be('ungrouped', 'The group\'s members are top-level elements again.', TOP)],
           prep=selecting((260, 205))),
        cp('front', 'Bring the bottom (red) rectangle to the front using its context menu.',
           'The red rectangle is drawn above the others.', stack, menu_item(*sp['sa'], 'Bring to Front'),
           [be('order', 'The red rectangle is the topmost element.', TOP)]),
        cp('back', 'Send the top (blue) rectangle to the back using its context menu.',
           'The blue rectangle is drawn below the others.', stack, menu_item(*sp['sc'], 'Send to Back'),
           [be('order', 'The blue rectangle is the bottom element.', TOP)]),
    ])


def clipboard():
    pair, pp = F.G_PAIR, F.G_PAIR_POINTS
    return episode('gui-clipboard', 'arrange', [
        cp('duplicate', 'The rectangle is selected. Duplicate it with the duplicate button.',
           'A copy of the rectangle appears slightly offset.', pair, [T('Duplicate Element(s) [D]')],
           [be('copy', 'A copy of the rectangle is added 20 units right and down.', new('outline', 'paint'))],
           prep=selecting(pp['gr'])),
        cp('delete', 'The rectangle is selected. Delete it with the delete button.', 'Only the ellipse remains.', pair,
           [T('Delete Element(s) [Delete/Backspace]')],
           [be('removed', 'The rectangle is removed.', TOP)], prep=selecting(pp['gr'])),
        cp('cut-paste', 'Cut the rectangle and paste it back, both with the context menu.',
           'The rectangle is shown again (pasted).', pair,
           [dclick(*pp['gr'], button='right'), {'do': 'click', 'text': 'Cut', 'prefix': True},
            dclick(600, 100, button='right'), {'do': 'click', 'text': 'Paste', 'exact': True}],
           [be('pasted', 'A rectangle of the same size and colour is in the drawing again.', new('size', 'paint'))]),
        cp('paste-in-place', 'Copy the rectangle and use "Paste in Place" from the context menu.',
           'A second rectangle lies exactly on top of the original.', pair,
           [dclick(*pp['gr'], button='right'), {'do': 'click', 'text': 'Copy', 'prefix': True},
            dclick(*pp['gr'], button='right'), {'do': 'click', 'text': 'Paste in Place', 'exact': True}],
           [be('copy', 'The pasted copy has exactly the original\'s position and size.', new('outline', 'paint'))]),
        cp('multi-duplicate', 'Both shapes are selected. Duplicate them with the duplicate button.',
           'Copies of both shapes appear slightly offset.', pair, [T('Duplicate Element(s) [C]')],
           [be('copies', 'Copies of both shapes are added 20 units right and down.', TOP)], prep=ALL),
        cp('undo', 'The rectangle has just been moved 10 units right (by preparation). Undo that move with the '
                   'undo button.', 'The rectangle is back at its original place.', pair, [T('Undo [ctrl+Z]')],
           [be('restored', 'The rectangle is back at its original position.', element('gr'))],
           prep=[*selecting(pp['gr']), {'op': 'press', 'key': 'Shift+ArrowRight'}]),
        cp('redo', 'The rectangle\'s 10-unit move was just undone (by preparation). Redo it with the redo button.',
           'The rectangle is 10 units to the right of its original place.', pair, [T('Redo [ctrl+Y]')],
           [be('moved', 'The rectangle is 10 units right of its original position.', element('gr'))],
           prep=[*selecting(pp['gr']), {'op': 'press', 'key': 'Shift+ArrowRight'}, {'op': 'press', 'key': 'Control+z'}]),
    ])


def selection():
    stack, sp = F.STACK, F.STACK_POINTS
    return episode('gui-selection', 'selection', [
        cp('drag-move', 'Move the green rectangle 100 units to the right by dragging it.',
           'The green rectangle is 100 units further right.', stack, [ddrag(300, 190, 400, 190)],
           [be('moved', 'The green rectangle moved 100 units right.', element('sb'), tol=1.0)]),
        cp('shift-select', 'Select the red and the blue rectangles together (not the green one) and delete them.',
           'Only the green rectangle remains.', stack,
           [dclick(*sp['sa']), dclick(*sp['sc'], modifiers=['Shift']), press('Delete')],
           [be('remaining', 'Only the green rectangle remains.', TOP)]),
        cp('shift-deselect', 'All three rectangles are selected. Remove the green one from the selection with '
                             'Shift+click, then delete the selection.', 'Only the green rectangle remains.', stack,
           [dclick(*sp['sb'], modifiers=['Shift']), press('Delete')],
           [be('remaining', 'Shift+click on a selected element removes it from the selection.', TOP)], prep=ALL),
        cp('band', 'Select all three rectangles by dragging a selection box around them and delete them.',
           'The drawing is empty.', stack, [ddrag(80, 80, 440, 360), press('Delete')],
           [be('empty', 'No element remains.', COUNT)], requires=['band/empty']),
    ])


def links():
    return episode('gui-links', 'arrange', [
        cp('link', 'The rectangle is selected. Make it a hyperlink to https://example.org/harbor.',
           'The rectangle is now a link (the link URL field shows the address).', R,
           [answer('https://example.org/harbor'), T('Make (hyper)link')],
           [be('link', 'The rectangle is wrapped in a link to https://example.org/harbor.',
               {'type': 'top', 'parts': ['outline', 'href']})], prep=selecting(RP), requires=['link/link']),
        cp('edit-link', 'The link around the rectangle is selected. Change its address to https://example.org/pier.',
           'The link URL field shows the new address.',
           F.doc('<a id="la" href="https://example.org/old"><rect id="lr" x="220" y="160" width="200" height="120" '
                 'fill="#3366cc"/></a>'),
           [fill('https://example.org/pier', title='Set link URL (leave empty to remove)')],
           [be('href', 'The link points to https://example.org/pier.', raw('la', 'text:href'))],
           prep=selecting((320, 220)), requires=['edit-link/href']),
        cp('remove-link', 'The link around the rectangle is selected. Remove the link (empty its address) so that '
                          'the rectangle is no longer a link.', 'The rectangle is shown as before but is no longer a '
                                                                'link.',
           F.doc('<a id="la" href="https://example.org/old"><rect id="lr" x="220" y="160" width="200" height="120" '
                 'fill="#3366cc"/></a>'),
           [fill('', title='Set link URL (leave empty to remove)')],
           [be('unlinked', 'The rectangle is no longer inside a link.', TOP)],
           prep=selecting((320, 220)), requires=['remove-link/unlinked']),
        cp('unlink-use', 'The symbol instance (orange circle) is selected. Break its link to the symbol (make it '
                         'unique).', 'The circle looks the same but is no longer an instance.', F.G_USE,
           [T('Break link to reference element (make unique)')],
           [be('unique', 'The instance is replaced by its own copy of the circle.', {'type': 'leaves'})],
           prep=selecting((310, 230)),
           requires=['unlink-use/unique']),
    ])


def path_edit():
    path, pp = F.G_PATH, F.G_PATH_POINT
    curve = F.G_CURVE
    edit = selecting(pp) + [click(*pp)]
    node1 = [dclick(220, 160, action='down'), dclick(220, 160, action='up')]
    return episode('gui-path-edit', 'paths', [
        cp('node-xy', 'The zig-zag path is in node editing mode. Move its node at (220, 160) (the first top corner) '
                      'to (240, 100) with the node coordinate fields.', 'The first top corner of the path is now at '
                                                                         '(240, 100).', path,
           node1 + [fill(240, label='x', context="Change node's x coordinate"),
                    fill(100, label='y', context="Change node's y coordinate")],
           [be('path', 'The path\'s second node is at (240, 100); the other nodes stay.', element('gp'))], prep=edit),
        cp('segment', 'The zig-zag path is in node editing mode. Make its first segment (from the lower left end up '
                      'to the node at (220, 160)) a curve.',
           'The first segment becomes a curve segment: the segment type field shows Curve and the segment gets two '
           'control handles.', path,
           node1 + [select_option('6', title='Change Segment type')],
           [be('curve', 'The path\'s first segment is a curve.', element('gp', 'shape'))], prep=edit),
        cp('straighten', 'The shape with a curved top is in node editing mode. Make its curved segment (ending at '
                         'the node at (360, 300)) straight.', 'The curved top becomes a straight edge.', F.G_CURVE2,
           [dclick(360, 300, action='down'), dclick(360, 300, action='up'),
            select_option('4', title='Change Segment type')],
           [be('straight', 'The path has no curved segment any more.', element('gk', 'shape'))],
           prep=selecting(F.G_CURVE2_POINT) + [click(*F.G_CURVE2_POINT)]),
        cp('clone', 'The zig-zag path is in node editing mode. Clone its node at (220, 160).',
           'The path has one more node.', path, node1 + [T('Clone Node')],
           [be('nodes', 'The path has one more node.', element('gp', 'shape'))], prep=edit),
        cp('delete', 'The zig-zag path is in node editing mode. Delete its second node.',
           'The path has one node fewer.', path, node1 + [T('Delete Node')],
           [be('nodes', 'The path has one node fewer and keeps its other nodes.', element('gp'))], prep=edit),
        cp('close', 'The zig-zag path is in node editing mode. Close it, so that its last node connects back to its '
                    'first node.', 'The zig-zag is now a closed outline.', path,
           node1 + [T('Open/close sub-path')],
           [be('closed', 'The path is closed and keeps its four nodes.', element('gp'))], prep=edit),
        cp('node-drag', 'The zig-zag path is in node editing mode. Drag its second node from (220, 160) to '
                        '(220, 80).', 'The second corner of the zig-zag is higher.', path, [ddrag(220, 160, 220, 80)],
           [be('path', 'The path\'s second node is at (220, 80); the other nodes stay.', element('gp'), tol=1.0)],
           prep=edit),
    ])


# -- layers -----------------------------------------------------------------------------------------------------
LAYER_HINT = ' Use the layers list in the side panel and leave Layer View off.'


def layer_goal(checkpoint):
    return dict(checkpoint, goal=checkpoint['goal'] + LAYER_HINT)


PANEL = [T('Click to open side panel')]


RELOAD = [{'op': 'reload-drawing'}]


def layers_basic():
    lay = F.G_LAYERS
    return episode('gui-layers', 'layers', [layer_goal(c) for c in [
        cp('new', 'Add a new layer named "Overlay".', 'The layers list shows a new layer Overlay.', lay,
           PANEL + [answer('Overlay'), T('New Layer')],
           [be('layers', 'A new layer "Overlay" is added above the others.', LAYERS)], prep=RELOAD),
        cp('rename', 'Rename the layer "Land" to "Field".', 'The layers list shows Field instead of Land.', lay,
           PANEL + [X('Land'), answer('Field'), T('Rename Layer')],
           [be('layers', 'The layer "Land" is now called "Field" and keeps its content.', LAYERS)], prep=RELOAD),
        cp('delete', 'Delete the layer "Land".', 'The layer Land and its ellipse are gone.', lay,
           PANEL + [X('Land'), T('Delete Layer')],
           [be('layers', 'The layer "Land" and its content are removed.', LAYERS)], prep=RELOAD),
        cp('up', 'Move the layer "Sky" up one step in the layer order.', 'Sky is now listed above Land.', lay,
           PANEL + [X('Sky'), T('Move Layer Up')],
           [be('layers', 'The layer "Sky" moved one step up (above "Land").', LAYERS)], prep=RELOAD),
        cp('down', 'Move the layer "Notes" down one step in the layer order.', 'Notes is now listed below Land.', lay,
           PANEL + [X('Notes'), T('Move Layer Down')],
           [be('layers', 'The layer "Notes" moved one step down (below "Land").', LAYERS)], prep=RELOAD),
    ]])


def layers_more():
    lay, lp = F.G_LAYERS, F.G_LAYER_POINTS
    return episode('gui-layers-more', 'layers', [layer_goal(c) for c in [
        cp('hide', 'Hide only the layer "Notes", using the visibility toggle next to its name in the layers list.',
           'The text North and the white rectangle are no longer shown; the sky and the land are still shown.', lay,
           PANEL + [{'do': 'pointer-near', 'text': 'Notes', 'dx': -14}],
           [be('layers', 'The layer "Notes" is hidden.', LAYERS)], prep=RELOAD),
        cp('show', 'The layer "Notes" is hidden. Show it again with its visibility toggle in the layers list.',
           'The text North and the white rectangle are shown again.', F.G_LAYERS_HIDDEN,
           PANEL + [{'do': 'pointer-near', 'text': 'Notes', 'dx': -14}],
           [be('layers', 'The layer "Notes" is visible.', LAYERS)], prep=RELOAD),
        cp('move-to', 'The white rectangle (layer "Notes") is selected. Move it to the layer "Sky".',
           'The white rectangle now belongs to Sky.', lay,
           PANEL + [select_option('Sky', label='Move elements to:'), X('Ok')],
           [be('layers', 'The white rectangle is in the layer "Sky".', LAYERS)],
           prep=RELOAD + selecting(lp['yr'])),
        cp('duplicate', 'Duplicate the layer "Land" (accept the proposed name).',
           'A copy of the layer Land is listed.', lay,
           PANEL + [X('Land'), T('More options'), X('Duplicate Layer...')],
           [be('layers', 'A copy of "Land" with its own copy of the ellipse is added.', LAYERS)], prep=RELOAD),
        cp('merge-down', 'Merge the layer "Notes" down into the layer below it.',
           'Notes is gone and its content belongs to Land.', lay,
           PANEL + [X('Notes'), T('More options'), X('Merge Down')],
           [be('layers', 'The content of "Notes" is merged into "Land".', LAYERS)], prep=RELOAD),
        cp('merge-all', 'Merge all layers into one.', 'Only one layer remains, holding all shapes.', lay,
           PANEL + [T('More options'), X('Merge All')],
           [be('layers', 'All content is in a single layer.', LAYERS)], prep=RELOAD),
        cp('draw-into', 'Make "Sky" the current layer and draw a rectangle in it.',
           'A new rectangle is drawn into the layer Sky.', lay,
           PANEL + [X('Sky'), T('Square/Rect Tool'), ddrag(60, 260, 160, 330)],
           [be('layers', 'The new rectangle is in the layer "Sky".', LAYERS)], prep=RELOAD),
    ]])


# -- document, preferences, view -----------------------------------------------------------------------------------
DOCPROPS = [menu('Document Properties (shift+D)')]


def document():
    return episode('gui-document', 'document', [
        cp('title', 'Set the document title to "Harbor plan" in the document properties, confirm, then open the '
                    'document properties again.',
           'The reopened document properties show the title Harbor plan.', M,
           DOCPROPS + [fill('Harbor plan', label='Title:', enter=False), X('OK')] + DOCPROPS,
           [be('title', 'The drawing carries the title "Harbor plan".', {'type': 'root-children', 'tags': ['title']})]),
        cp('size', 'Make the canvas 800 wide and 500 high in the document properties.', 'The page is 800 by 500.', M,
           DOCPROPS + [fill(800, label='Width', enter=False), fill(500, label='Height', enter=False), X('OK')],
           [be('size', 'The document is 800 by 500.', ROOT)]),
        cp('predefined', 'Choose the predefined canvas size 1024x768 in the document properties.',
           'The page is 1024 by 768.', M, DOCPROPS + [select_option('1024x768', has_option='1024x768'), X('OK')],
           [be('size', 'The document is 1024 by 768.', ROOT)]),
        cp('predefined-800', 'Choose the predefined canvas size 800x600 in the document properties.',
           'The page is 800 by 600.', M, DOCPROPS + [select_option('800x600', has_option='800x600'), X('OK')],
           [be('size', 'The document is 800 by 600.', ROOT)]),
        cp('predefined-640', 'The page is 400 by 300. Choose the predefined canvas size 640x480 in the document '
                             'properties.', 'The page is 640 by 480.', F.G_SMALL,
           DOCPROPS + [select_option('640x480', has_option='640x480'), X('OK')],
           [be('size', 'The document is 640 by 480.', ROOT)]),
        cp('predefined-1280', 'Choose the predefined canvas size 1280x960 in the document properties.',
           'The page is 1280 by 960.', M, DOCPROPS + [select_option('1280x960', has_option='1280x960'), X('OK')],
           [be('size', 'The document is 1280 by 960.', ROOT)]),
        cp('predefined-1600', 'Choose the predefined canvas size 1600x1200 in the document properties.',
           'The page is 1600 by 1200.', M, DOCPROPS + [select_option('1600x1200', has_option='1600x1200'), X('OK')],
           [be('size', 'The document is 1600 by 1200.', ROOT)]),
        cp('fit', 'Fit the canvas to the content (document properties, predefined size "Fit to Content").',
           'The page shrinks to the bounding box of the shapes.', M,
           DOCPROPS + [select_option('content', has_option='content'), X('OK')],
           [be('size', 'The document size equals the content\'s bounding box.', ROOT, tol=1.0)]),
        cp('embed', 'In the document properties choose to embed included images, then save the drawing as SVG.',
           'An SVG file is downloaded.', F.G_IMAGE,
           DOCPROPS + [{'do': 'check', 'label': 'Embed data (local files)'}, X('OK'), menu('Save SVG (S)'),
                       {'do': 'download', 'suffix': '.svg'}],
           [be('images', 'The saved file embeds the image as PNG data.', {'type': 'download', 'format': 'svg',
                                                                          'parts': ['images']})]),
    ])


PREFS = [menu('Editor Preferences')]


def preferences():
    return episode('gui-preferences', 'preferences', [
        cp('snapping', 'Turn on grid snapping with a snapping step of 50 in the editor preferences, then draw a '
                       'rectangle by dragging from (110, 130) to (290, 240).',
           'A new rectangle is drawn whose corners lie on the 50-unit grid.', E,
           PREFS + [{'do': 'check', 'label': 'Snapping on/off'}, fill(50, label='Snapping Step-Size:', enter=False),
                    X('OK'), T('Square/Rect Tool'), ddrag(110, 130, 290, 240)],
           [be('snapped', 'The new rectangle\'s position and size are multiples of 50.', new('outline'))]),
        cp('snap-keys', 'The rectangle is selected. Turn on grid snapping with a snapping step of 50 in the editor '
                        'preferences, then press the right arrow key once.',
           'The rectangle moves right and snaps onto the 50-unit grid (its corners lie on grid lines).', R,
           PREFS + [{'do': 'check', 'label': 'Snapping on/off'}, fill(50, label='Snapping Step-Size:', enter=False),
                    X('OK'), press('ArrowRight')],
           [be('moved', 'With snapping on, the arrow key moves the rectangle right and snaps it onto the 50-unit '
                        'grid.', element('gr'))],
           prep=selecting(RP)),
        cp('unit', 'Set the base unit to centimetres in the editor preferences, then set the selected rectangle\'s '
                   'width to 5 (cm).', 'The width field shows 5 and the rectangle is 5 cm wide.', R,
           PREFS + [select_option('cm', label='Base Unit:'), X('OK'), fill(5, label='w')],
           [be('width', 'The rectangle is 5 cm (188.98 px) wide.', element('gr'), tol=0.1),
            be('document', 'With centimetres as base unit the document size is written in centimetres '
                           '(16.93cm x 12.7cm).', {'type': 'root-units'}, tol=0.02)], prep=selecting(RP)),
        cp('unit-in', 'Set the base unit to inches in the editor preferences, then set the selected rectangle\'s '
                      'height to 2 (in).', 'The height field shows 2 and the rectangle is 2 inches high.', R,
           PREFS + [select_option('in', label='Base Unit:'), X('OK'), fill(2, label='h')],
           [be('height', 'The rectangle is 2 in (192 px) high.', element('gr'), tol=0.1)], prep=selecting(RP)),
        cp('unit-mm', 'Set the base unit to millimetres in the editor preferences, then set the selected '
                      'rectangle\'s width to 50 (mm).', 'The width field shows 50 and the rectangle is 50 mm wide.', R,
           PREFS + [select_option('mm', label='Base Unit:'), X('OK'), fill(50, label='w')],
           [be('width', 'The rectangle is 50 mm (188.98 px) wide.', element('gr'), tol=0.1)], prep=selecting(RP)),
        cp('unit-pt', 'Set the base unit to points in the editor preferences, then set the selected rectangle\'s '
                      'width to 100 (pt).', 'The width field shows 100 and the rectangle is 100 pt wide.', R,
           PREFS + [select_option('pt', label='Base Unit:'), X('OK'), fill(100, label='w')],
           [be('width', 'The rectangle is 100 pt (133.33 px) wide.', element('gr'), tol=0.1)], prep=selecting(RP)),
        cp('unit-pc', 'Set the base unit to picas in the editor preferences, then set the selected rectangle\'s '
                      'height to 10 (pc).', 'The height field shows 10 and the rectangle is 10 pc high.', R,
           PREFS + [select_option('pc', label='Base Unit:'), X('OK'), fill(10, label='h')],
           [be('height', 'The rectangle is 10 pc (160 px) high.', element('gr'), tol=0.1)], prep=selecting(RP)),
        cp('background', 'Change the editor background (canvas colour) to black in the editor preferences.',
           'The page (canvas) background is black.', M,
           PREFS + [{'do': 'pointer', 'x': 602, 'y': 395, 'viewport': True}, X('OK')], []),
        cp('language', 'Switch the editor language to French in the editor preferences and reload the page.',
           'After the reload the editor\'s interface has switched to French (exact wording not required).', M,
           PREFS + [select_option('fr', label='Language:'), X('OK'), X('Ok'), {'do': 'reload'}], []),
    ])


def view():
    return episode('gui-view', 'view', [
        cp('wireframe', 'Switch to wireframe mode.', 'All shapes are shown as thin outlines without fill.', M,
           [T('Wireframe Mode [F]')], []),
        cp('zoom-field', 'Set the zoom level to 200 %.', 'The drawing is shown twice as large and the zoom field '
                                                          'shows 200.', M,
           [fill(200, title='Change zoom level')], []),
        cp('grid', 'Show the grid.', 'A grid is drawn over the page.', M, [T('Show/Hide Grid')], []),
        cp('layer-view', 'Make "Notes" the current layer and turn on layer view so that only the current layer is '
                         'shown.', 'Only the Notes layer is shown: the blue sky band and the green land are hidden '
                                   'and the text North remains.', F.G_LAYERS,
           PANEL + [X('Notes'), T('Enable/Disable Layer View [Ctrl+Shift+L]')], [], prep=RELOAD),
        cp('zoom-tool', 'Use the zoom tool to zoom into the region around the ellipse.',
           'The view is zoomed in on the ellipse.', M, [T('Zoom Tool [Z/Alt+wheels]'), ddrag(240, 50, 400, 150)], []),
    ])


# -- source, files, export, persistence, errors ----------------------------------------------------------------
SOURCE_NEW = ('<svg width="640" height="480" xmlns="http://www.w3.org/2000/svg">\n <g class="layer">\n  '
              '<title>Layer 1</title>\n  <rect fill="#ff9900" height="120" id="gr" stroke="#1a1a1a" stroke-width="4" '
              'width="200" x="220" y="160"/>\n  <circle cx="100" cy="100" fill="#00aa66" id="added" r="40"/>\n </g>\n'
              '</svg>')


def source():
    return episode('gui-source', 'source', [
        cp('apply', 'Open the source editor, replace the source with the text below, and apply it.\n```\n'
                    + SOURCE_NEW + '\n```', 'The rectangle is orange and a green circle is added.', R,
           [T('Edit Source [U]'), {'do': 'fill', 'tag': 'textarea', 'value': SOURCE_NEW, 'enter': False},
            X('Apply Changes')],
           [be('rect', 'The rectangle\'s fill is #ff9900.', element('gr', 'paint')),
            be('circle', 'The circle from the source is added.', element('added', 'outline', 'paint'))]),
        cp('invalid', 'Open the source editor, replace the source with "<svg><rect" (not valid SVG), apply it and '
                      'let the editor revert to the original source.',
           'After the revert the source editor is closed and the drawing still shows the unchanged blue '
           'rectangle.', R,
           [T('Edit Source [U]'), {'do': 'fill', 'tag': 'textarea', 'value': '<svg><rect', 'enter': False},
            X('Apply Changes'), X('Ok')],
           [be('unchanged', 'The drawing is unchanged.', DOCUMENT, requires=['apply/rect'])],
           requires=['apply/rect']),
        cp('cancel', 'Open the source editor, change the rectangle\'s width in the source to 50, then cancel.',
           'The source editor is closed and the rectangle keeps its width.', R,
           [T('Edit Source [U]'), {'do': 'fill', 'tag': 'textarea', 'value': SOURCE_NEW.replace('width="200"',
                                                                                                'width="50"'),
                                   'enter': False}, X('Cancel'), {'do': 'maybe-click', 'text': 'Ok'}],
           [be('unchanged', 'The rectangle keeps its width of 200.', element('gr'), requires=['apply/rect'])],
           requires=['apply/rect']),
    ])


def files():
    garden = (F.__file__.rsplit('/', 1)[0] + '/fixtures/garden.svg')
    return episode('gui-files', 'files', [
        cp('new', 'Start a new image (discard the current drawing).', 'The drawing is empty.', M,
           [menu('New Image (N)'), X('Ok')],
           [be('empty', 'The drawing is empty and has the default size.', DOCUMENT)], requires=['new/empty']),
        cp('new-cancel', 'Choose "New Image" but cancel when asked to confirm.', 'The drawing is unchanged.', R,
           [menu('New Image (N)'), X('Cancel')],
           [be('kept', 'The drawing is unchanged.', element('gr'), requires=['new/empty'])], requires=['new/empty']),
        cp('open', 'Open the file garden.svg from the inputs.', 'The garden drawing is shown.', R,
           [menu('Open SVG'), X('Ok'), {'do': 'upload', 'file': 'garden.svg'}],
           [be('document', 'The drawing is the content of garden.svg.', DOCUMENT)]),
        cp('open-cancel', 'Choose "Open SVG" but cancel when asked to confirm.', 'The drawing is unchanged.', R,
           [menu('Open SVG'), X('Cancel')],
           [be('kept', 'The drawing is unchanged.', element('gr'), requires=['open/document'])],
           requires=['open/document']),
        cp('import-svg', 'Import the file garden.svg from the inputs into the current drawing.',
           'The garden drawing is added on top of the rectangle.', R,
           [menu('Import SVG'), {'do': 'upload', 'file': 'garden.svg'}],
           [be('added', 'The imported drawing is added as one new object; the rectangle stays.',
               multi(kept=element('gr', 'outline'), added={'type': 'extent'}))]),
        cp('import-png', 'Import the image tile.png from the inputs into the current drawing.',
           'A blue tile image is added.', R,
           [menu('Import SVG'), {'do': 'upload', 'file': 'tile.png', 'mime': 'image/png'}],
           [be('added', 'A new 48 x 32 image is added.', new('size'))]),
        cp('import-jpeg', 'Import the image photo.jpg from the inputs into the current drawing.',
           'An orange photo is added.', R,
           [menu('Import SVG'), {'do': 'upload', 'file': 'photo.jpg', 'mime': 'image/jpeg'}],
           [be('added', 'A new 50 x 30 image is added.', new('size'))]),
        cp('import-text', 'Try to import the text file readme.txt from the inputs.',
           'Nothing is added to the drawing.', R,
           [menu('Import SVG'), {'do': 'upload', 'file': 'readme.txt', 'mime': 'text/plain'}],
           [be('unchanged', 'Nothing is added.', COUNT, requires=['import-png/added'])], requires=['import-png/added']),
    ], files=['garden.svg', 'tile.png', 'photo.jpg', 'readme.txt'])


def save():
    return episode('gui-save', 'files', [
        cp('save', 'Save the drawing as an SVG file.', 'An SVG file is downloaded.', M,
           [menu('Save SVG (S)'), {'do': 'download', 'suffix': '.svg'}],
           [be('file', 'The saved file is named untitled.svg and starts with an XML declaration.',
               {'type': 'download', 'format': 'svg', 'parts': ['name', 'declaration']}),
            be('content', 'The saved file contains the drawing.', {'type': 'download', 'format': 'svg',
                                                                    'parts': ['document']})]),
        cp('save-as', 'Use "Save as SVG" to save the drawing.', 'An SVG file is downloaded.', R,
           [menu('Save as SVG'), {'do': 'download', 'suffix': '.svg'}],
           [be('content', 'The saved file contains the drawing.', {'type': 'download', 'format': 'svg',
                                                                    'parts': ['document']})]),
    ])


ART = F.G_ART
SAMPLES = [(140, 110), (460, 140), (300, 400), (620, 20)]


def export():
    def exporting(kind, quality=None):
        steps = [menu('Export'), select_option(kind, label='Select an image type for export:', has_option=kind)]
        if quality is not None:
            steps.append(fill(quality, label='Quality:', enter=False))
        return steps + [X('OK'), {'do': 'download', 'suffix': ''}]
    def raster(kind, tol):
        base = {'type': 'download', 'format': kind}
        return [be('format', f'The exported file is a {kind.upper()} image.', dict(base, parts=['format'])),
                be('size', 'The image is 640 x 480 pixels.', dict(base, parts=['size'])),
                be('content', 'The image shows the red rectangle, blue circle and green triangle, and the uncovered '
                              'background as SVG-edit renders it for this format.',
                   dict(base, parts=['samples'], points=SAMPLES), tol=tol)]
    return episode('gui-export', 'export', [
        cp('png', 'Export the drawing as a PNG image.', 'The PNG export is produced.', ART, exporting('PNG'),
           raster('png', 8)),
        cp('jpeg', 'Export the drawing as a JPEG image with quality 30.', 'The JPEG export is produced.', ART,
           exporting('JPEG', 30),
           raster('jpeg', 24) + [be('quality', 'The JPEG uses quality 30.',
                                    {'type': 'download', 'format': 'jpeg', 'parts': ['quality']})]),
        cp('bmp', 'Export the drawing as a BMP image.', 'The BMP export is produced.', ART, exporting('BMP'),
           raster('bmp', 8)[1:]),
        cp('webp', 'Export the drawing as a WEBP image.', 'The WEBP export is produced.', ART, exporting('WEBP'),
           raster('webp', 24)),
        cp('pdf', 'Export the drawing as PDF.', 'A PDF file is downloaded.', F.G_ART_TITLED, exporting('PDF'),
           [be('pdf', 'The PDF has one 640 x 480 page.', {'type': 'download', 'format': 'pdf',
                                                         'parts': ['pages', 'size']}),
            be('title', 'The PDF\'s document title is the drawing\'s title "Harbour chart".',
               {'type': 'download', 'format': 'pdf', 'parts': ['title']})]),
        cp('hidden-layer', 'The layer "Notes" is hidden. Export the drawing as a PNG image.',
           'The PNG export is produced.', F.G_LAYERS_HIDDEN, exporting('PNG'),
           [be('content', 'The hidden layer is left out of the image: the sky shows where the white rectangle of '
                          '"Notes" is, the land ellipse is drawn and the uncovered area stays transparent.',
               {'type': 'download', 'format': 'png', 'parts': ['samples'], 'points': [(480, 95), (320, 380),
                                                                                       (20, 300)]}, tol=8)]),
        cp('image', 'The drawing contains an image. Export it as a PNG image.', 'The PNG export is produced.',
           F.G_IMAGE, exporting('PNG'),
           [be('content', 'The exported image shows the embedded picture (blue) on a transparent background.',
               {'type': 'download', 'format': 'png', 'parts': ['samples'], 'points': [(280, 210), (100, 100)]},
               tol=8)]),
        cp('small-png', 'The drawing is 400 x 300. Export it as a PNG image.', 'The PNG export is produced.',
           F.G_SMALL, exporting('PNG'),
           [be('image', 'The PNG is 400 x 300.', {'type': 'download', 'format': 'png', 'parts': ['size']})]),
        cp('pdf-portrait', 'The drawing is 300 wide and 500 high. Export it as PDF.', 'A PDF file is downloaded.',
           F.doc('<rect id="pr" x="20" y="20" width="260" height="460" fill="#3366cc"/>', 300, 500), exporting('PDF'),
           [be('page', 'The PDF page is 300 x 500 (portrait).', {'type': 'download', 'format': 'pdf',
                                                                 'parts': ['size']})]),
    ])


def persistence():
    return episode('gui-persistence', 'persistence', [
        cp('reload', 'The rectangle is selected. Make its fill yellow with the palette, then reload the page.',
           'After the reload the yellow rectangle is shown again.', R, [palette(8), {'do': 'reload'}],
           [be('kept', 'After the reload the rectangle is restored with its yellow fill.', element('gr', 'paint'))],
           prep=selecting(RP)),
        cp('store-both', 'The editor asks how to store data. Choose to store both preferences and content, then '
                         'draw a rectangle by dragging from (100, 100) to (220, 200) and reload the page.',
           'After the reload the new rectangle is shown again.', E,
           [select_option('prefsAndContent', has_option='prefsAndContent'), X('OK'), T('Square/Rect Tool'),
            ddrag(100, 100, 220, 200), {'do': 'reload'}],
           [be('restored', 'After the reload the drawn rectangle is restored.', TOP)], prep=[{'op': 'no-consent'}]),
        cp('no-store', 'The editor asks how to store data. Choose not to store preferences or content, then draw a '
                       'rectangle and reload the page.', 'After the reload the drawing is empty.', E,
           [select_option('noPrefsOrContent', has_option='noPrefsOrContent'), X('OK'), T('Square/Rect Tool'),
            ddrag(100, 100, 220, 200), {'do': 'reload'}, {'do': 'maybe-click', 'text': 'OK'}],
           [be('not-restored', 'After the reload no drawing is restored.', COUNT, requires=['reload/kept'])],
           prep=[{'op': 'no-consent'}], requires=['reload/kept']),
        cp('cancel', 'The editor asks how to store data. Cancel that question, then draw a rectangle and reload the '
                     'page.', 'After the reload the drawing is empty and the editor asks again.', E,
           [X('Cancel'), T('Square/Rect Tool'), ddrag(100, 100, 220, 200), {'do': 'reload'}],
           [be('not-restored', 'Without an answer to the storage question the drawing is not restored.', COUNT,
               requires=['reload/kept'])], prep=[{'op': 'no-consent'}], requires=['reload/kept']),
        cp('prefs-only', 'The editor asks how to store data. Choose to store only preferences, then draw a '
                         'rectangle and reload the page.', 'After the reload the drawing is empty.', E,
           [select_option('prefsOnly', has_option='prefsOnly'), X('OK'), T('Square/Rect Tool'),
            ddrag(100, 100, 220, 200), {'do': 'reload'}],
           [be('not-restored', 'With only preferences stored, the drawing is not restored.', COUNT,
               requires=['reload/kept'])], prep=[{'op': 'no-consent'}], requires=['reload/kept']),
    ])


def errors():
    lay = F.G_LAYERS
    return episode('gui-errors', 'errors', [
        cp('width', 'The rectangle is selected. Set its width to 300 with the width field.', 'The rectangle is 300 '
                                                                                             'wide.', R,
           [fill(300, label='w')], [be('width', 'The rectangle is 300 wide.', element('gr'))], prep=selecting(RP)),
        cp('invalid-width', 'The rectangle is selected. Type "abc" into its width field and press Enter.',
           'The value is rejected: the width field shows 200 again and the rectangle keeps its width.', R,
           [fill('abc', label='w'), {'do': 'maybe-click', 'text': 'Ok'}],
           [be('unchanged', 'The rectangle keeps its width.', element('gr'), requires=['width/width'])],
           prep=selecting(RP), requires=['width/width']),
        cp('layer', 'Add a new layer named "Overlay".' + LAYER_HINT, 'A layer Overlay is listed.', lay,
           PANEL + [answer('Overlay'), T('New Layer')], [be('layers', 'A layer "Overlay" is added.', LAYERS)],
           prep=RELOAD),
        cp('duplicate-name', 'Try to add a new layer named "Sky" (a name that already exists).' + LAYER_HINT,
           'The editor refuses with a message that the name exists; no layer is added.', lay,
           PANEL + [answer('Sky'), T('New Layer'), {'do': 'expect-dialog', 'type': 'alert'}],
           [be('unchanged', 'No layer is added.', LAYERS, requires=['layer/layers'])], requires=['layer/layers'],
           prep=RELOAD),
        cp('invalid-size', 'Try to set the canvas width to "wide" in the document properties.',
           'The editor reports an invalid value and the canvas keeps its size.', M,
           DOCPROPS + [fill('wide', label='Width', enter=False), X('OK'), {'do': 'maybe-click', 'text': 'Ok'}],
           [be('unchanged', 'The document keeps its size.', ROOT, requires=['width/width'])],
           requires=['width/width']),
    ])


def build():
    return [draw_shapes(), draw_lines(), polystar(), shape_library('gui-shape-library', SHAPE_CATEGORIES[:7]),
            shape_library('gui-shape-library-2', SHAPE_CATEGORIES[7:]), eyedropper(), paint_fill(), paint_stroke(),
            gradients(), stroke_style(), effects(), markers(), geometry(), identity(), font_family(), text_font(),
            text_layout(), align_multi(), align_relative(), flip_convert(), arrange(), context_menu(), clipboard(),
            selection(), links(),
            path_edit(), layers_basic(), layers_more(), document(), preferences(), view(), source(), files(), save(),
            export(), persistence(), errors()]
