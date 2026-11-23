"""Program episodes: no evaluator. Each checkpoint opens the editor in a fresh browser profile, loads its sprite
through the editor API (loadPiskel), applies a scripted stimulus and reads the result with getPiskel, the snapshot or
a product download.

Stimuli are keyboard shortcuts, pointer input in sprite pixel coordinates (target {"sprite": true}, with the right
button or held modifier keys where the tool defines them), clicks on controls found by the reference's visible names
(tooltip, label or text; case-insensitive substring unless noted), file drops and lifecycle operations.

A point that only verifies a refusal or an unchanged state names, in `requires`, a positive point of the same
episode.
"""
import base64

import fixtures as F

INITIAL = ('Fresh editor page. Each checkpoint starts from a fresh browser profile (reset, then the entry page) and '
           'loads its own sprite through the editor API, so checkpoints do not depend on each other.')

TOOLS = {'pen': 'p', 'mirror': 'v', 'bucket': 'b', 'swap': 'a', 'eraser': 'e', 'stroke': 'l', 'rect': 'r',
         'circle': 'c', 'move': 'm', 'shape-select': 'z', 'rect-select': 's', 'lasso': 'h', 'lighten': 'u',
         'dither': 't', 'picker': 'o'}


# -- stimulus helpers ----------------------------------------------------------------------------------
def tool(name):
    return {'op': 'press', 'key': TOOLS[name]}


def tap(x, y, button=None, mods=None):
    """A click on sprite pixel (x, y)."""
    step = {'op': 'pointer', 'action': 'click', 'target': {'sprite': True}, 'x': x, 'y': y}
    if button:
        step['button'] = button
    if mods:
        step['modifiers'] = list(mods)
    return step


def drag(x0, y0, x1, y1, button=None, mods=None, via=None, steps=None):
    """Press on sprite pixel (x0, y0), pass the `via` pixels in order, release on (x1, y1)."""
    step = {'op': 'drag', 'target': {'sprite': True}, 'x': x0, 'y': y0, 'to_x': x1, 'to_y': y1}
    if button:
        step['button'] = button
    if mods:
        step['modifiers'] = list(mods)
    if via:
        step['via'] = [list(p) for p in via]
    if steps:
        step['steps'] = steps
    return step


def key(name, times=1):
    return [{'op': 'press', 'key': name} for _ in range(times)]


def pick(x, y, button=None):
    """Take a colour from the sprite with the colour picker (left: primary, right: secondary)."""
    return [tool('picker'), tap(x, y, button)]


def control(mods=None, nth=None, exact=False, **locator):
    """A click on a control found by its visible name."""
    target = dict(locator)
    if not exact:
        target['exact'] = False
    if nth is not None:
        target['nth'] = nth
    step = {'op': 'click', 'target': target}
    if mods:
        step['modifiers'] = list(mods)
    return step


def fill(value, **locator):
    return {'op': 'fill', 'target': {**locator, 'exact': False}, 'value': str(value)}


def settle(seconds=0.5):
    return {'op': 'wait', 'seconds': seconds}


def drop(name, data, mime, x=4, y=4):
    """Drop a file on sprite pixel (x, y), as when dragging it from the desktop."""
    return {'op': 'drop', 'target': {'sprite': True}, 'x': x, 'y': y, 'filename': name, 'mime_type': mime,
            'base64': base64.b64encode(data).decode()}


# -- builders -----------------------------------------------------------------------------------------
def point(name, requirement, check, requires=(), tol=None):
    check = dict(check)
    if tol is not None:
        check['tol'] = tol
    return {'name': name, 'requirement': requirement, 'check': check, 'requires': list(requires)}


def case(cid, goal, fixture, steps, points):
    """fixture: a sprite from fixtures, loaded through the editor API before the steps (None keeps the new sprite)."""
    return {'id': cid, 'goal': goal, 'fixture': None if fixture is None else F.encode(fixture),
            'steps': list(steps), 'points': points}


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


def pix(layer=0, frame=0):
    return {'type': 'pixels', 'layer': layer, 'frame': frame}


def meta(*keys):
    return {'type': 'meta', 'keys': list(keys)}


PIX = pix()
ALL = {'type': 'all'}
SIZE = {'type': 'size'}
FRAMES = {'type': 'frames'}
LAYERS = {'type': 'layers'}
HIDDEN = {'type': 'hidden'}


def drawn(cid, goal, fixture, steps, requirement, requires=()):
    """A case whose subject is the pixels of the first frame of the first layer."""
    return case(cid, goal, fixture, steps, [point('pixels', requirement, PIX, requires=requires)])
# -- freehand tools ---------------------------------------------------------------------------------------------
def pen():
    a = F.ANIM
    cases = [
        drawn('click', 'Press P and click pixel (3, 4) of the empty sprite.', F.BLANK, [tool('pen'), tap(3, 4)],
              'A click with the pen paints the clicked pixel in the primary colour (black by default).'),
        drawn('right-click', 'Press P and right-click the red pixel (1, 1).', F.REGIONS,
              [tool('pen'), tap(1, 1, 'right')],
              'The right button paints with the secondary colour (transparent by default): the pixel is cleared.'),
        drawn('diagonal', 'Press P and drag quickly from pixel (0, 0) to (7, 7) (one pointer move).', F.BLANK,
              [tool('pen'), drag(0, 0, 7, 7, steps=1)],
              'The pen fills the gap between pointer positions: a fast drag paints a continuous line.'),
        drawn('shallow', 'Press P and drag quickly from pixel (0, 1) to (7, 4) (one pointer move).', F.BLANK,
              [tool('pen'), drag(0, 1, 7, 4, steps=1)], 'The filled gap of a shallow move is a straight pixel line.'),
        drawn('size-2', 'Press ] once, then P, then click pixel (3, 3).', F.BLANK,
              [*key(']'), tool('pen'), tap(3, 3)], 'Pen size 2 paints a 2 x 2 block at the clicked pixel.'),
        drawn('size-3', 'Press ] twice, then P, then click pixel (3, 3).', F.BLANK,
              [*key(']', 2), tool('pen'), tap(3, 3)], 'Pen size 3 paints a 3 x 3 block around the clicked pixel.'),
        drawn('size-4', 'Press ] three times, then P, then click pixel (3, 3).', F.BLANK,
              [*key(']', 3), tool('pen'), tap(3, 3)], 'Pen size 4 paints a 4 x 4 block.'),
        drawn('size-7', 'Press ] six times, then P, then click pixel (3, 3).', F.BLANK,
              [*key(']', 6), tool('pen'), tap(3, 3)], '] keeps growing the pen past the four preset sizes (7 x 7).'),
        drawn('size-min', 'Press [ once, then P, then click pixel (3, 3).', F.BLANK,
              [*key('['), tool('pen'), tap(3, 3)], 'The pen size does not go below 1.', requires=['click/pixels']),
        drawn('size-down', 'Press ] three times and [ once, then P, then click pixel (3, 3).', F.BLANK,
              [*key(']', 3), *key('['), tool('pen'), tap(3, 3)], '[ decreases the pen size by one (to 3).'),
        drawn('size-drag', 'Press ] once, then P, then drag from pixel (1, 1) to (6, 1).', F.BLANK,
              [*key(']'), tool('pen'), drag(1, 1, 6, 1)], 'A drag with pen size 2 paints a two pixels thick line.'),
        drawn('edge', 'Press ] three times, then P, then click the corner pixel (7, 7).', F.BLANK,
              [*key(']', 3), tool('pen'), tap(7, 7)], 'A large pen at the border paints only pixels inside the sprite.'),
        drawn('outside', 'Press P and drag from pixel (2, 2) to the right, beyond the sprite, to (9, 2).', F.BLANK,
              [tool('pen'), drag(2, 2, 9, 2)], 'A drag leaving the sprite paints the part inside the sprite.'),
        case('next-frame', 'With three frames, press the down arrow, then P, then click pixel (5, 5).', a,
             [*key('ArrowDown'), tool('pen'), tap(5, 5)], [
                 point('second', 'The down arrow selects the next frame, and the pen paints on it.', pix(0, 1)),
                 point('first', 'The first frame is unchanged.', pix(0, 0), requires=['next-frame/second'])]),
        case('previous-frame', 'With three frames, press the down arrow twice and the up arrow once, then P, then '
             'click pixel (5, 5).', a, [*key('ArrowDown', 2), *key('ArrowUp'), tool('pen'), tap(5, 5)], [
                 point('second', 'The up arrow selects the previous frame.', pix(0, 1)),
                 point('third', 'The third frame is unchanged.', pix(0, 2), requires=['previous-frame/second'])]),
        case('layer', 'With two layers, press P and click pixel (0, 4).', F.LAYERS, [tool('pen'), tap(0, 4)], [
            point('current', 'After a sprite is opened the pen paints on its first layer.', pix(0, 0)),
            point('other', 'The other layer is unchanged.', pix(1, 0), requires=['layer/current'])]),
    ]
    return episode('pen', 'drawing', cases)


def mirror():
    cases = [
        drawn('click', 'Press V and click pixel (1, 2).', F.BLANK, [tool('mirror'), tap(1, 2)],
              'The vertical mirror pen paints the pixel and its mirror image across the vertical axis.'),
        drawn('ctrl', 'Press V and Control+click pixel (1, 2).', F.BLANK, [tool('mirror'), tap(1, 2, mods=['Control'])],
              'With Control the pen mirrors across the horizontal axis instead.'),
        drawn('shift', 'Press V and Shift+click pixel (1, 2).', F.BLANK, [tool('mirror'), tap(1, 2, mods=['Shift'])],
              'With Shift the pen mirrors across both axes: four pixels.'),
        drawn('drag', 'Press V and drag from pixel (0, 0) to (3, 3).', F.BLANK, [tool('mirror'), drag(0, 0, 3, 3)],
              'A mirror pen drag paints the line and its mirror image.'),
        drawn('odd', 'On a 7 x 5 sprite press V, click pixel (1, 1) and then the middle pixel (3, 2).', F.ODD,
              [tool('mirror'), tap(1, 1), tap(3, 2)],
              'On an odd width the mirror is counted from the far edge; the middle column mirrors onto itself.'),
        drawn('size-2', 'Press ] once, then V, then click pixel (1, 1).', F.BLANK,
              [*key(']'), tool('mirror'), tap(1, 1)], 'The mirror image of a 2 x 2 block is also a 2 x 2 block.'),
        drawn('right', 'Press V and right-click the red pixel (1, 2).', F.REGIONS,
              [tool('mirror'), tap(1, 2, 'right')],
              'The right button paints the secondary colour (transparent) on the pixel and its mirror image.'),
    ]
    return episode('mirror-pen', 'drawing', cases)


def eraser():
    cases = [
        drawn('click', 'Press E and click the red pixel (1, 1).', F.REGIONS, [tool('eraser'), tap(1, 1)],
              'The eraser clears the clicked pixel to transparent.'),
        drawn('drag', 'Press E and drag from pixel (0, 0) to (7, 7).', F.REGIONS, [tool('eraser'), drag(0, 0, 7, 7)],
              'Dragging the eraser clears every pixel along the path.'),
        drawn('size-3', 'Press ] twice, then E, then click pixel (5, 5).', F.REGIONS,
              [*key(']', 2), tool('eraser'), tap(5, 5)], 'Eraser size 3 clears a 3 x 3 block.'),
        drawn('right', 'Press E and right-click the blue pixel (5, 2).', F.REGIONS, [tool('eraser'), tap(5, 2, 'right')],
              'The right button erases as well.'),
        case('frame', 'With three frames, press the down arrow, then E, then click pixel (1, 1).', F.ANIM,
             [*key('ArrowDown'), tool('eraser'), tap(1, 1)], [
                 point('second', 'The eraser clears the pixel on the selected frame.', pix(0, 1))]),
    ]
    return episode('eraser', 'drawing', cases)
# -- shape tools ----------------------------------------------------------------------------------------------
def stroke():
    cases = [
        drawn('horizontal', 'Press L and drag from pixel (1, 3) to (6, 3).', F.BLANK, [tool('stroke'), drag(1, 3, 6, 3)],
              'The stroke tool draws a straight line between the press and the release pixel.'),
        drawn('vertical', 'Press L and drag from pixel (2, 0) to (2, 7).', F.BLANK, [tool('stroke'), drag(2, 0, 2, 7)],
              'A vertical stroke covers the whole column between the two pixels.'),
        drawn('diagonal', 'Press L and drag from pixel (0, 7) to (7, 0).', F.BLANK, [tool('stroke'), drag(0, 7, 7, 0)],
              'A 45 degree stroke is a staircase of single pixels.'),
        drawn('shallow', 'Press L and drag from pixel (0, 2) to (7, 5).', F.BLANK, [tool('stroke'), drag(0, 2, 7, 5)],
              'A shallow stroke steps one row at a time, with one pixel per column.'),
        drawn('steep', 'Press L and drag from pixel (1, 0) to (4, 7).', F.BLANK, [tool('stroke'), drag(1, 0, 4, 7)],
              'A steep stroke has one pixel per row.'),
        drawn('reverse', 'Press L and drag from pixel (7, 5) to (0, 2).', F.BLANK, [tool('stroke'), drag(7, 5, 0, 2)],
              'A stroke drawn from right to left joins the same two pixels.'),
        drawn('detour', 'Press L and drag from pixel (1, 1) through (6, 6) and (0, 7) to (6, 1).', F.BLANK,
              [tool('stroke'), drag(1, 1, 6, 1, via=[(6, 6), (0, 7)])],
              'Only the press and release pixels count: the pointer path in between leaves no pixels.'),
        drawn('straight', 'Press L and Shift+drag from pixel (1, 1) to (6, 2).', F.BLANK,
              [tool('stroke'), drag(1, 1, 6, 2, mods=['Shift'])], 'With Shift the stroke snaps to a horizontal line.'),
        drawn('straight-diagonal', 'Press L and Shift+drag from pixel (1, 1) to (5, 6).', F.BLANK,
              [tool('stroke'), drag(1, 1, 5, 6, mods=['Shift'])], 'With Shift the stroke snaps to the 45 degree diagonal.'),
        drawn('size-2', 'Press ] once, then L, then drag from pixel (1, 1) to (6, 4).', F.BLANK,
              [*key(']'), tool('stroke'), drag(1, 1, 6, 4)], 'With pen size 2 the stroke is two pixels thick.'),
        drawn('single', 'Press L and click pixel (4, 4).', F.BLANK, [tool('stroke'), tap(4, 4)],
              'A click without moving draws a single pixel.'),
        drawn('right', 'Press L and right-drag from pixel (0, 1) to (7, 1).', F.REGIONS,
              [tool('stroke'), drag(0, 1, 7, 1, 'right')],
              'A right-button stroke uses the secondary colour (transparent): it clears the line.'),
    ]
    return episode('stroke', 'drawing', cases)


def rectangle():
    cases = [
        drawn('outline', 'Press R and drag from pixel (1, 1) to (5, 4).', F.BLANK, [tool('rect'), drag(1, 1, 5, 4)],
              'The rectangle tool draws the outline of the rectangle spanned by the press and release pixels.'),
        drawn('reverse', 'Press R and drag from pixel (5, 4) to (1, 1).', F.BLANK, [tool('rect'), drag(5, 4, 1, 1)],
              'Dragging up and to the left draws the same rectangle.'),
        drawn('square', 'Press R and Shift+drag from pixel (1, 1) to (6, 3).', F.BLANK,
              [tool('rect'), drag(1, 1, 6, 3, mods=['Shift'])], 'With Shift the rectangle keeps a 1 to 1 ratio.'),
        drawn('flat', 'Press R and drag from pixel (2, 3) to (6, 3).', F.BLANK, [tool('rect'), drag(2, 3, 6, 3)],
              'A rectangle one pixel high is a line.'),
        drawn('size-2', 'Press ] once, then R, then drag from pixel (1, 1) to (6, 6).', F.BLANK,
              [*key(']'), tool('rect'), drag(1, 1, 6, 6)], 'With pen size 2 the outline is two pixels thick.'),
        drawn('right', 'Press R and right-drag from pixel (0, 0) to (3, 3).', F.REGIONS,
              [tool('rect'), drag(0, 0, 3, 3, 'right')],
              'A right-button rectangle uses the secondary colour (transparent): the red square loses its border.'),
        drawn('over', 'Press R and drag from pixel (2, 2) to (6, 6).', F.REGIONS, [tool('rect'), drag(2, 2, 6, 6)],
              'The outline is painted over existing pixels; the inside is left as it was.'),
        drawn('clip', 'Press R and drag from pixel (4, 4) to the right edge beyond the sprite, at (9, 6).', F.BLANK,
              [tool('rect'), drag(4, 4, 9, 6)], 'Parts of the rectangle outside the sprite are dropped.'),
    ]
    return episode('rectangle', 'drawing', cases)


def circle():
    cases = [
        drawn('ellipse', 'Press C and drag from pixel (0, 0) to (7, 4).', F.BLANK, [tool('circle'), drag(0, 0, 7, 4)],
              'The circle tool draws the outline of the ellipse inscribed in the dragged box.'),
        drawn('circle', 'Press C and Shift+drag from pixel (0, 0) to (7, 4).', F.BLANK,
              [tool('circle'), drag(0, 0, 7, 4, mods=['Shift'])], 'With Shift the ellipse keeps a 1 to 1 ratio.'),
        drawn('small', 'Press C and drag from pixel (2, 2) to (4, 4).', F.BLANK, [tool('circle'), drag(2, 2, 4, 4)],
              'A 3 x 3 circle.'),
        drawn('flat', 'Press C and drag from pixel (0, 2) to (7, 5).', F.BLANK, [tool('circle'), drag(0, 2, 7, 5)],
              'An ellipse twice as wide as high.'),
        drawn('large', 'On a 16 x 16 sprite press C and drag from pixel (1, 2) to (14, 13).', F.BIG,
              [tool('circle'), drag(1, 2, 14, 13)], 'A large ellipse.'),
        drawn('size-2', 'Press ] once, then C, then drag from pixel (0, 0) to (7, 7).', F.BLANK,
              [*key(']'), tool('circle'), drag(0, 0, 7, 7)], 'With pen size 2 the outline is two pixels thick.'),
        drawn('reverse', 'Press C and drag from pixel (7, 4) to (0, 0).', F.BLANK, [tool('circle'), drag(7, 4, 0, 0)],
              'Dragging up and to the left draws the same ellipse.'),
        drawn('right', 'Press C and right-drag from pixel (0, 0) to (7, 7).', F.REGIONS,
              [tool('circle'), drag(0, 0, 7, 7, 'right')],
              'A right-button circle uses the secondary colour (transparent).'),
    ]
    return episode('circle', 'drawing', cases)
# -- fill tools -----------------------------------------------------------------------------------------------
def bucket():
    cases = [
        drawn('enclosed', 'Press B and click inside the green ring at pixel (5, 5).', F.REGIONS,
              [tool('bucket'), tap(5, 5)], 'The bucket fills the enclosed transparent area with the primary colour.'),
        drawn('background', 'Press B and click the transparent pixel (7, 0).', F.REGIONS,
              [tool('bucket'), tap(7, 0)],
              'The fill spreads to side neighbours only: transparent areas touching it only at a corner stay empty.'),
        drawn('colour', 'Press B and click the green ring at pixel (7, 4).', F.REGIONS, [tool('bucket'), tap(7, 4)],
              'Clicking a coloured area replaces the whole connected area of that colour.'),
        drawn('same', 'Press B and click the black block at pixel (1, 5).', F.REGIONS, [tool('bucket'), tap(1, 5)],
              'Filling an area with its own colour changes nothing.', requires=['enclosed/pixels']),
        drawn('right', 'Press B and right-click the red area at pixel (0, 0).', F.REGIONS,
              [tool('bucket'), tap(0, 0, 'right')],
              'A right click fills with the secondary colour (transparent): the red area is cleared.'),
        drawn('diagonal', 'Press B and click pixel (0, 0) above the diagonal line.', F.DIAG, [tool('bucket'), tap(0, 0)],
              'A one pixel diagonal line stops the fill: only the triangle above it is filled.'),
        drawn('single', 'Press B and click one of the separate red pixels, (2, 0).', F.SPOTS,
              [tool('bucket'), tap(2, 0)], 'The bucket changes only the clicked area, not other pixels of the same colour.'),
        case('frame', 'With three frames, press the down arrow, then B, then click pixel (4, 4).', F.ANIM,
             [*key('ArrowDown'), tool('bucket'), tap(4, 4)], [
                 point('second', 'The bucket fills on the selected frame.', pix(0, 1)),
                 point('first', 'The first frame is unchanged.', pix(0, 0), requires=['frame/second'])]),
    ]
    return episode('paint-bucket', 'drawing', cases)


def colour_swap():
    m = F.MULTI
    cases = [
        drawn('frame', 'Press A and click the red pixel (0, 0).', F.SPOTS, [tool('swap'), tap(0, 0)],
              'The magic bucket replaces every pixel of the clicked colour in the frame, touching or not.'),
        drawn('transparent', 'Press A and click the transparent pixel (1, 0).', F.SPOTS, [tool('swap'), tap(1, 0)],
              'Clicking a transparent pixel paints every transparent pixel of the frame.'),
        drawn('right', 'Press A and right-click the red pixel (0, 0).', F.SPOTS, [tool('swap'), tap(0, 0, 'right')],
              'A right click replaces the colour with the secondary colour (transparent).'),
        case('plain', 'With two layers and two frames, press A and click the red pixel (0, 0).', m,
             [tool('swap'), tap(0, 0)], [
                 point('current', 'The red pixels of the current layer and frame turn black.', pix(0, 0)),
                 point('other-layer', 'Other layers keep their red.', pix(1, 0), requires=['plain/current']),
                 point('other-frame', 'Other frames keep their red.', pix(0, 1), requires=['plain/current'])]),
        case('layers', 'With two layers and two frames, press A and Control+click the red pixel (0, 0).', m,
             [tool('swap'), tap(0, 0, mods=['Control'])], [
                 point('other-layer', 'With Control the colour is replaced in every layer of the current frame.',
                       pix(1, 0)),
                 point('other-frame', 'Other frames keep their red.', pix(0, 1), requires=['layers/other-layer'])]),
        case('frames', 'With two layers and two frames, press A and Shift+click the red pixel (0, 0).', m,
             [tool('swap'), tap(0, 0, mods=['Shift'])], [
                 point('other-frame', 'With Shift the colour is replaced in every frame of the current layer.',
                       pix(0, 1)),
                 point('other-layer', 'Other layers keep their red.', pix(1, 0), requires=['frames/other-frame'])]),
        case('everywhere', 'With two layers and two frames, press A and Control+Shift+click the red pixel (0, 0).', m,
             [tool('swap'), tap(0, 0, mods=['Control', 'Shift'])], [
                 point('all', 'With Control and Shift the colour is replaced in every layer and frame.', ALL)]),
    ]
    return episode('colour-swap', 'drawing', cases)


def lighten():
    cases = [
        drawn('lighten', 'Press U and click the red pixel (0, 0).', F.SHADES, [tool('lighten'), tap(0, 0)],
              'The lighten tool makes the clicked pixel lighter by one step.'),
        drawn('darken', 'Press U and Control+click the grey pixel (4, 0).', F.SHADES,
              [tool('lighten'), tap(4, 0, mods=['Control'])], 'With Control the tool darkens instead.'),
        drawn('twice', 'Press U and click the red pixel (0, 0) twice, as two separate clicks.', F.SHADES,
              [tool('lighten'), tap(0, 0), tap(0, 0)], 'Each click lightens the pixel by one more step.',
              requires=['lighten/pixels']),
        drawn('once', 'Press U and Shift+drag from pixel (0, 7) to (7, 7) and back to (0, 7).', F.SHADES,
              [tool('lighten'), drag(0, 7, 0, 7, mods=['Shift'], via=[(7, 7)])],
              'With Shift each pixel is changed only once per drag, however often the pointer passes it.',
              requires=['lighten/pixels']),
        drawn('limits', 'Press U, click the white pixel (5, 2), then Control+click the black pixel (4, 2).', F.SHADES,
              [tool('lighten'), tap(5, 2), tap(4, 2, mods=['Control'])],
              'White cannot get lighter and black cannot get darker.', requires=['lighten/pixels']),
        drawn('transparent', 'Press U and click the transparent pixel (2, 4).', F.SHADES, [tool('lighten'), tap(2, 4)],
              'Transparent pixels are left alone.', requires=['lighten/pixels']),
        drawn('size-2', 'Press ] once, then U, then click pixel (1, 1).', F.SHADES,
              [*key(']'), tool('lighten'), tap(1, 1)], 'With pen size 2 a 2 x 2 block is lightened.'),
    ]
    return episode('lighten', 'drawing', cases)


def dithering():
    cases = [
        drawn('drag', 'Press T and drag from pixel (0, 0) to (7, 0), then from (0, 1) to (7, 1).', F.REGIONS,
              [tool('dither'), drag(0, 0, 7, 0), drag(0, 1, 7, 1)],
              'The dithering tool paints a checkerboard: primary colour on alternate pixels, secondary (transparent) on '
              'the others.'),
        drawn('right', 'Press T and right-drag from pixel (0, 0) to (7, 0), then from (0, 1) to (7, 1).', F.REGIONS,
              [tool('dither'), drag(0, 0, 7, 0, 'right'), drag(0, 1, 7, 1, 'right')],
              'With the right button the two colours of the checkerboard trade places.'),
        drawn('size-2', 'Press ] once, then T, then click pixel (3, 3).', F.BLANK,
              [*key(']'), tool('dither'), tap(3, 3)], 'With pen size 2 the checkerboard covers a 2 x 2 block.'),
    ]
    return episode('dithering', 'drawing', cases)


def colours():
    r = F.REGIONS
    cases = [
        drawn('pick', 'Press O and click the blue pixel (5, 2); then press P and click pixel (0, 5).', r,
              [*pick(5, 2), tool('pen'), tap(0, 5)], 'The colour picker makes the clicked colour the primary colour.'),
        drawn('pick-secondary', 'Press O and right-click the green pixel (5, 4); then press P and right-click pixel (0, 5).',
              r, [*pick(5, 4, 'right'), tool('pen'), tap(0, 5, 'right')],
              'A right click with the colour picker sets the secondary colour.'),
        drawn('pick-transparent', 'Press O and click the transparent pixel (4, 0); then press P and click pixel (0, 0).',
              r, [*pick(4, 0), tool('pen'), tap(0, 0)], 'Picking a transparent pixel makes the pen erase.'),
        drawn('swap', 'Press O, click the blue pixel (5, 2), press X, then press P, click pixel (0, 0) and right-click '
              'pixel (0, 5).', r, [*pick(5, 2), *key('x'), tool('pen'), tap(0, 0), tap(0, 5, 'right')],
              'X swaps the primary and secondary colours.'),
        drawn('reset', 'Press O, click the blue pixel (5, 2), press D, then press P and click pixel (0, 5).', r,
              [*pick(5, 2), *key('d'), tool('pen'), tap(0, 5)], 'D restores the default colours (black primary).'),
        drawn('reset-secondary', 'Press O, right-click the blue pixel (5, 2), press D, then press P and right-click '
              'pixel (1, 1).', r, [*pick(5, 2, 'right'), *key('d'), tool('pen'), tap(1, 1, 'right')],
              'D also restores the transparent secondary colour.'),
        case('layer', 'With two layers, press O and click pixel (2, 2), where only the upper layer is red; then press '
             'P and click pixel (0, 4).', F.LAYERS, [*pick(2, 2), tool('pen'), tap(0, 4)], [
                 point('pixels', 'The colour picker reads the current layer, not the combined image.', pix(0, 0))]),
    ]
    return episode('colours', 'colours', cases)
# -- move and selections --------------------------------------------------------------------------------------
def move():
    m = F.MULTI
    cases = [
        drawn('right', 'Press M and drag from pixel (0, 0) to (2, 1).', F.ARROW, [tool('move'), drag(0, 0, 2, 1)],
              'The move tool shifts the whole frame by the dragged distance; pixels pushed out are dropped.'),
        drawn('left', 'Press M and drag from pixel (4, 4) to (1, 3).', F.ARROW, [tool('move'), drag(4, 4, 1, 3)],
              'Moving left and up works the same way.'),
        drawn('wrap', 'Press M and Alt+drag from pixel (0, 0) to (3, 2).', F.ARROW,
              [tool('move'), drag(0, 0, 3, 2, mods=['Alt'])],
              'With Alt pixels pushed out on one side come back on the other side.'),
        case('plain', 'With two layers and two frames, press M and drag from pixel (0, 0) to (1, 2).', m,
             [tool('move'), drag(0, 0, 1, 2)], [
                 point('current', 'Only the current layer and frame move.', pix(0, 0)),
                 point('other-layer', 'Other layers stay.', pix(1, 0), requires=['plain/current']),
                 point('other-frame', 'Other frames stay.', pix(0, 1), requires=['plain/current'])]),
        case('layers', 'With two layers and two frames, press M and Control+drag from pixel (0, 0) to (1, 2).', m,
             [tool('move'), drag(0, 0, 1, 2, mods=['Control'])], [
                 point('other-layer', 'With Control every layer of the current frame moves.', pix(1, 0)),
                 point('other-frame', 'Other frames stay.', pix(0, 1), requires=['layers/other-layer'])]),
        case('frames', 'With two layers and two frames, press M and Shift+drag from pixel (0, 0) to (1, 2).', m,
             [tool('move'), drag(0, 0, 1, 2, mods=['Shift'])], [
                 point('other-frame', 'With Shift every frame of the current layer moves.', pix(0, 1)),
                 point('other-layer', 'Other layers stay.', pix(1, 0), requires=['frames/other-frame'])]),
        case('everything', 'With two layers and two frames, press M and Control+Shift+drag from pixel (0, 0) to (1, 2).',
             m, [tool('move'), drag(0, 0, 1, 2, mods=['Control', 'Shift'])], [
                 point('all', 'With Control and Shift every layer and frame moves.', ALL)]),
    ]
    return episode('move', 'drawing', cases)


def selection():
    r = F.REGIONS
    cases = [
        drawn('delete', 'Press S, drag from pixel (0, 0) to (2, 2), then press Delete.', r,
              [tool('rect-select'), drag(0, 0, 2, 2), *key('Delete')],
              'Delete clears the pixels inside a rectangle selection.'),
        drawn('copy-paste', 'Press S, drag from pixel (0, 0) to (1, 1), press Control+C, drag the selection from '
              '(0, 0) to (5, 5), then press Control+V.', r,
              [tool('rect-select'), drag(0, 0, 1, 1), *key('Control+c'), drag(0, 0, 5, 5), *key('Control+v')],
              'Copy and paste puts the copied pixels where the selection was moved; the original stays.'),
        drawn('cut-paste', 'Press S, drag from pixel (0, 0) to (1, 1), press Control+X, drag the selection from '
              '(0, 0) to (5, 5), then press Control+V.', r,
              [tool('rect-select'), drag(0, 0, 1, 1), *key('Control+x'), drag(0, 0, 5, 5), *key('Control+v')],
              'Cut clears the selected pixels; paste puts them at the moved selection.'),
        drawn('move-content', 'Press S, drag from pixel (0, 0) to (3, 3), Shift+drag the selection from (1, 1) to (5, 5), '
              'then press Enter.', r,
              [tool('rect-select'), drag(0, 0, 3, 3), drag(1, 1, 5, 5, mods=['Shift']), *key('Enter')],
              'Dragging a selection with Shift carries its pixels along; Enter puts them down.'),
        case('other-frame', 'With three frames, press S, drag from pixel (0, 0) to (1, 1), press Control+C, press the '
             'down arrow, then press Control+V.', F.ANIM,
             [tool('rect-select'), drag(0, 0, 1, 1), *key('Control+c'), *key('ArrowDown'), *key('Control+v')], [
                 point('second', 'A selection copied on one frame is pasted onto the selected frame.', pix(0, 1))]),
        drawn('shape', 'Press Z, click the green ring at pixel (5, 4), then press Delete.', r,
              [tool('shape-select'), tap(5, 4), *key('Delete')],
              'The shape selection selects the connected area of the clicked colour; Delete clears exactly that area.'),
        drawn('lasso', 'Press H, drag from pixel (0, 0) through (7, 0) to (0, 7), then press Delete.', r,
              [tool('lasso'), drag(0, 0, 0, 7, via=[(7, 0)]), *key('Delete')],
              'The lasso selects the pixels inside the traced outline; Delete clears them.'),
    ]
    return episode('selection', 'selection', cases)


# -- frames and undo ------------------------------------------------------------------------------------------
def frames():
    a = F.ANIM
    cases = [
        case('new', 'With three frames, press N.', a, [*key('n')], [
            point('frames', 'N adds an empty frame.', ALL)]),
        case('duplicate', 'With three frames, press Shift+N.', a, [*key('Shift+N')], [
            point('frames', 'Shift+N inserts a copy of the current frame after it.', ALL)]),
        case('duplicate-second', 'With three frames, press the down arrow, then Shift+N.', a,
             [*key('ArrowDown'), *key('Shift+N')], [
                 point('frames', 'The copy of the second frame comes right after it.', ALL)]),
        case('new-selected', 'With three frames, press N, then P, then click pixel (4, 4).', a,
             [*key('n'), tool('pen'), tap(4, 4)], [
                 point('frames', 'The new frame becomes the selected frame.', ALL)]),
        case('down-clamped', 'With three frames, press the down arrow three times, then P, then click pixel (4, 4).', a,
             [*key('ArrowDown', 3), tool('pen'), tap(4, 4)], [
                 point('frames', 'The down arrow at the last frame keeps that frame selected.', ALL)]),
        case('up-clamped', 'With three frames, press the up arrow, then P, then click pixel (4, 4).', a,
             [*key('ArrowUp'), tool('pen'), tap(4, 4)], [
                 point('frames', 'The up arrow at the first frame keeps that frame selected.', ALL)]),
        case('layers', 'With two layers and three frames, press Shift+N.', F.GRID, [*key('Shift+N')], [
            point('frames', 'A duplicated frame is duplicated in every layer.', ALL)]),
        case('add-button', 'With three frames, click the "Add new frame" button.', a,
             [control(text='Add new frame')], [
                 point('frames', 'The "Add new frame" button adds an empty frame at the end.', ALL)]),
    ]
    return episode('frames', 'frames', cases)


def undo():
    b = F.BLANK
    two = [tool('pen'), tap(1, 1), tap(2, 2)]
    cases = [
        drawn('pen', 'Press P, click pixels (1, 1) and (2, 2), then press Control+Z.', b, [*two, *key('Control+z')],
              'Control+Z undoes the last pen click only.'),
        drawn('twice', 'Press P, click pixels (1, 1) and (2, 2), then press Control+Z twice.', b,
              [*two, *key('Control+z', 2)], 'Each Control+Z undoes one more action.', requires=['pen/pixels']),
        drawn('redo', 'Press P, click pixels (1, 1) and (2, 2), press Control+Z, then Control+Y.', b,
              [*two, *key('Control+z'), *key('Control+y')], 'Control+Y redoes the undone action.',
              requires=['pen/pixels']),
        drawn('redo-shift', 'Press P, click pixels (1, 1) and (2, 2), press Control+Z, then Control+Shift+Z.', b,
              [*two, *key('Control+z'), *key('Control+Shift+Z')], 'Control+Shift+Z also redoes.',
              requires=['pen/pixels']),
        drawn('redo-cleared', 'Press P, click pixel (1, 1), press Control+Z, click pixel (3, 3), then press Control+Y.',
              b, [tool('pen'), tap(1, 1), *key('Control+z'), tap(3, 3), *key('Control+y')],
              'A new action after an undo discards the redo history.', requires=['pen/pixels']),
        drawn('bucket', 'Press B, click pixel (5, 5) inside the green ring, then press Control+Z.', F.REGIONS,
              [tool('bucket'), tap(5, 5), *key('Control+z')], 'A fill is undone as a whole.', requires=['pen/pixels']),
        drawn('move', 'Press M, drag from pixel (0, 0) to (2, 1), then press Control+Z.', F.ARROW,
              [tool('move'), drag(0, 0, 2, 1), *key('Control+z')], 'A move is undone as a whole.',
              requires=['pen/pixels']),
        drawn('selection', 'Press S, drag from pixel (0, 0) to (2, 2), press Delete, then press Control+Z.', F.REGIONS,
              [tool('rect-select'), drag(0, 0, 2, 2), *key('Delete'), *key('Control+z')],
              'Clearing a selection can be undone.', requires=['pen/pixels']),
        case('new-frame', 'With three frames, press N, then Control+Z.', F.ANIM, [*key('n'), *key('Control+z')], [
            point('frames', 'Adding a frame can be undone.', FRAMES, requires=['pen/pixels'])]),
        case('duplicate', 'With three frames, press Shift+N, then Control+Z.', F.ANIM,
             [*key('Shift+N'), *key('Control+z')], [
                 point('frames', 'Duplicating a frame can be undone.', ALL, requires=['pen/pixels'])]),
        case('frames', 'With three frames, press P and click pixel (5, 5), press the down arrow, click pixel (6, 6), '
             'then press Control+Z.', F.ANIM,
             [tool('pen'), tap(5, 5), *key('ArrowDown'), tap(6, 6), *key('Control+z')], [
                 point('frames', 'Undo reverts the last action, on the frame where it happened.', ALL)]),
    ]
    return episode('undo', 'history', cases)
# -- EPISODES --


def build():
    import program_extra
    import program_formats
    import program_episodes
    import program_review
    return [pen(), mirror(), eraser(), stroke(), rectangle(), circle(), bucket(), colour_swap(), lighten(),
            dithering(), colours(), move(), selection(), frames(), undo()] + program_extra.build() + program_formats.build() + program_episodes.build()+program_review.build()
