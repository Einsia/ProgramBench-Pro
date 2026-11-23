"""Layer, transform, size, file and persistence episodes through public runtime operations."""
import copy
from program import (F, case, episode, point, drawn, pix, meta, control, fill, key, tool, tap, drag,
                     settle, pick, PIX, ALL, SIZE, LAYERS, FRAMES, HIDDEN)


def ui(action='click', match=None, **kw):
    return {'op': 'ui', 'action': action, 'match': match or {}, **kw}


def field(label, value, enter=False, scope=None):
    match = {'semantic': label, 'editable': True}
    if label in ('Width', 'Height'):
        match['scope'] = scope or 'Resize'
        if scope is None:
            match['exclude_scope'] = 'Default size'
    elif scope:
        match['scope'] = scope
    return ui('fill', match, value=str(value), enter=enter)


def drawer(name):
    return control(title={'export': 'EXPORT Export as Image', 'save': 'SAVE Save',
                          'resize': 'RESIZE Resize', 'import': 'IMPORT Import', 'preferences': 'PREFERENCES'}[name], exact=name=='preferences')


def dialog(text=None, response='accept'):
    return {'op': 'dialog', 'response': response, **({'text': str(text)} if text is not None else {})}


def dl(fmt, parts=(), only=(), **kw):
    return {'type': 'download', 'format': fmt, 'parts': list(parts), 'only': list(only), **kw}


def export(fmt, scale=1, columns=None, selected=False, loop=True, split=False, names=False, prefix=None, inline=False):
    out = [drawer('export')]
    if scale != 1:
        out += [ui('press', {'label': 'Scale'}, key='Home')]
        out += [ui('press', {'label': 'Scale'}, key='ArrowRight') for _ in range(scale - 1)]
    out += [control(text={'png': 'PNG', 'gif': 'GIF', 'zip': 'Zip', 'c': 'Others', 'pixi': 'PNG'}[fmt], exact=True)]
    if fmt in ('png', 'pixi'):
        if columns is not None:
            out += [field('Columns', columns), *key('Tab')]
        if fmt == 'pixi':
            out += [{'op': 'check', 'target': {'label': 'Inline spritesheet as data-uri'}, 'checked': inline}]
        out += [ui('click', {'semantic':'Download','scope':'PixiJS Movie export' if fmt=='pixi' else
                             'Selected frame export' if selected else 'Spritesheet file export'})]
    elif fmt == 'gif':
        out += [{'op': 'check', 'target': {'label': 'Loop repeatedly'}, 'checked': loop}, control(text='Download', exact=True)]
    elif fmt == 'zip':
        if prefix is not None:
            out += [fill(prefix, placeholder='PNG file prefix')]
        out += [{'op': 'check', 'target': {'label': 'Split by layers'}, 'checked': split}]
        if split:
            out += [{'op': 'check', 'target': {'label': 'Index by layer names'}, 'checked': names}]
        out += [control(text='Download ZIP', exact=True)]
    else:
        out += [control(text='Download C file', exact=True)]
    return out + [{'op': 'wait-download', 'suffix': '.' + ('zip' if fmt == 'pixi' else fmt)}]


def resize(w, h, content=False, anchor=0, ratio=False):
    # The anchor cells are visible arrows; the nine titles expose their origin.
    steps = [drawer('resize'), {'op': 'check', 'target': {'label': 'Maintain aspect ratio'}, 'checked': ratio},
             {'op': 'check', 'target': {'label': 'Resize canvas content'}, 'checked': content}, field('Width', w)]
    if not ratio:
        steps += [field('Height', h)]
    if anchor:
        steps += [control(title=('top left', 'top', 'top right', 'middle left', 'middle', 'middle right', 'bottom left', 'bottom',
                                 'bottom right')[anchor], exact=True)]
    return steps + [control(text='Resize', exact=True)]


def layer_select(name):
    # Clicking the name is the documented selection action; the enclosing row's centre can be empty.
    return control(text=name, exact=True)


def rename(name):
    return [control(title='Edit layer name'), ui('fill', {'editable': True, 'focused': True}, value=name, enter=True)]


def opacity(value, layer_name='back'):
    return [dialog(value), ui('click', {'title': 'Layer opacity', 'contains': True, 'near': layer_name})]


def layers():
    tri = copy.deepcopy(F.GRID)
    tri['layers'].append(F.layer('high', [F.cell('...p....'), F.cell('...o....'), F.cell('...w....')]))
    cases = [case('create', 'Create a layer in the three-frame sprite.', F.GRID,
                  [control(title='Create a layer')], [point('names', 'An additional named layer exists.', {'type':'layers','generated':1}),
                   point('content', 'Each frame of the new layer is transparent.', {'type': 'layer-frames', 'layer': 1}),
                   point('frame-0', 'The first new frame is empty.', pix(1, 0)),
                   point('frame-2', 'The third new frame is empty.', pix(1, 2))]),
             case('clone', 'Clone the current layer.', F.GRID, [control(title='Create a layer', mods=['Shift'])],
                  [point('names', 'The cloned layer has its own nonempty name.', {'type':'layers','generated':1}),
                   *[point(f'frame-{i}', 'The clone preserves this animation frame.', pix(1, i)) for i in range(3)]]),
             case('delete', 'Select top, then delete the selected layer.', F.GRID,
                  [layer_select('top'), control(title='Delete selected layer')], [point('remaining', 'Only base remains.', LAYERS),
                   point('content', 'The surviving animation is intact.', ALL)]),
             case('merge', 'Select front and merge it with the layer below.', F.LAYERS,
                  [layer_select('front'), control(title='Merge with layer below')],
                  [point('names', 'The upper layer is removed after merging.', LAYERS),
                   point('pixels', 'Merging combines the foreground opacity with the lower pixels.', PIX)]),
             case('merge-animation', 'Merge top into base in the animation.', F.GRID,
                  [layer_select('top'), control(title='Merge with layer below')],
                  [point('frames', 'Merging composes every frame.', ALL)]),
             case('up', 'Move base one layer up.', tri, [control(title='Move layer up')],
                  [point('order', 'The layer moves one slot upward.', LAYERS)]),
             case('top', 'Move base to the top.', tri, [control(title='Move layer up', mods=['Shift'])],
                  [point('order', 'Shift moves the layer all the way to the top.', LAYERS)]),
             case('down', 'Select high and move it one layer down.', tri,
                  [layer_select('high'), control(title='Move layer down')], [point('order', 'The layer moves one slot down.', LAYERS)]),
             case('bottom', 'Select high and move it to the bottom.', tri,
                  [layer_select('high'), control(title='Move layer down', mods=['Shift'])],
                  [point('order', 'Shift moves the layer to the bottom.', LAYERS)]),
             case('selected-draw', 'Select top and paint pixel (3, 3).', F.GRID,
                  [layer_select('top'), tool('pen'), tap(3, 3)], [point('pixels', 'Painting changes the selected upper layer.', pix(1))]),
             case('rename', 'Rename base to foreground.', F.GRID, rename('foreground'), [point('name', 'Layer name changes.', LAYERS)]),
             case('unicode-name', 'Rename base to 星 / café 🎨.', F.GRID, rename('星 / café 🎨'),
                  [point('name', 'Unicode and punctuation in names survive.', LAYERS)])]
    for value in (0, .25, .75, 1, -1, 2, 'invalid'):
        cid = 'opacity-' + str(value).replace('.', '-')
        cases.append(case(cid, f'Set the back layer opacity to {value}.', F.LAYERS, opacity(value),
                          [point('value', 'The layer stores the accepted opacity, bounded to its supported interval.',
                                 {'type': 'opacity', 'layer': 0})]))
    return episode('layers', 'layers', cases)


def transforms():
    out = []
    for name, title, base, variants in (
        ('flip', 'Flip vertically', F.MULTI, [('vertical', []), ('horizontal', ['Alt'])]),
        ('rotate', 'Counter-clockwise rotation', F.MULTI, [('ccw', []), ('cw', ['Alt'])]),
        ('center', 'Align image to the center', F.MULTI, [('center', [])])):
        cases = []
        for variant, alternate in variants:
            for scope, mods in [('current', []), ('layers', ['Control']), ('frames', ['Shift']),
                                ('everything', ['Control', 'Shift'])]:
                cps = [point(f'layer-{li}-frame-{fi}', f'{name}: {scope} scope on layer {li + 1}, frame {fi + 1}.', pix(li, fi))
                       for li in range(2) for fi in range(2)]
                cases.append(case(variant + '-' + scope, f'Apply {variant} to {scope}.', base,
                                  [control(title=title, mods=alternate + mods)], cps))
        cases.append(case('nonsquare', 'Apply the transformation to a 6 by 4 sprite.',
                          F.one('offset-wide', 'rrg...\nr.....\n......\n......', 6, 4) if name == 'center' else F.WIDE,
                          [control(title=title)], [point('pixels', 'Non-square image transformation.', PIX),
                                                 point('size', 'Transformation canvas dimensions.', SIZE)]))
        cases.append(case('undo', 'Transform the sprite and undo.', F.ARROW,
                          [control(title=title), *key('Control+z')], [point('restored', 'Undo restores the original image.', PIX,
                          requires=[variants[0][0] + '-current/layer-0-frame-0'])]))
        out.append(episode(name, 'transforms', cases))
    out.append(episode('clone-frames', 'transforms', [case('clone', 'Clone the current layer to all frames.', F.CLONE_VISIBLE,
        [control(title='Clone current layer to all frames')],
        [point(f'layer-{li}-frame-{fi}', 'The clone operation affects the specified animation cell.', pix(li, fi))
         for li in range(2) for fi in range(3)])]))
    crop_cases = []
    for cid, fixture, prep in [('content', F.MIDDLE, []), ('selection', F.REGIONS, [tool('rect-select'), drag(1, 1, 5, 4)]),
                               ('all-frames', F.GRID, []), ('nonsquare', F.WIDE, []),
                               ('selection-outside', F.ARROW, [tool('rect-select'), drag(3, 2, 9, 6)])]:
        crop_cases.append(case(cid, 'Crop to the content or the prepared selection.', fixture,
                              prep + [control(title='View more tools'), control(title='Crop the sprite')],
                              [point('size', 'The cropped canvas bounds.', SIZE), point('pixels', 'The cropped content.', ALL)]))
    out.append(episode('crop', 'transforms', crop_cases))
    return out


def resizing():
    cases = []
    for cid, w, h, content, anchor in [('grow', 12, 10, False, 0), ('shrink', 5, 6, False, 0),
                                    ('upscale', 16, 16, True, 0), ('downscale', 4, 4, True, 0),
                                    ('stretch', 12, 6, True, 0), ('one-column', 1, 8, False, 0),
                                    ('one-row', 8, 1, False, 0)]:
        cases.append(case(cid, f'Resize the sprite to {w} by {h}, content scaling {content}.', F.GRID,
                          resize(w, h, content, anchor), [point('size', 'New canvas dimensions.', SIZE),
                          *[point(f'layer-{l}-frame-{f}', 'Resizing processes this animation cell.', pix(l, f))
                            for l in range(2) for f in range(3)]]))
    for anchor in range(1, 9):
        cases.append(case(f'anchor-{anchor}', 'Enlarge the canvas with the selected anchor.', F.ARROW,
                          resize(12, 12, anchor=anchor), [point('placement', 'Anchor controls where the content is placed.', PIX)]))
    cases.append(case('ratio', 'Resize the 6 by 4 sprite to width 12 with aspect ratio preserved.', F.WIDE,
                      resize(12, 8, content=True, ratio=True), [point('size', 'Aspect ratio synchronizes height.', SIZE),
                                                            point('pixels', 'Scaled non-square content.', PIX)]))
    return episode('resize', 'resize', cases)


def exports():
    out = []
    png_cases = []
    for cid, fixture, scale, cols, selected in [('sheet', F.GRID, 1, 3, False), ('vertical', F.GRID, 1, 1, False),
        ('two-columns', F.GRID, 1, 2, False), ('scaled', F.GRID, 2, 2, False),
        ('single', F.ARROW, 1, None, False), ('composite', F.LAYERS, 1, None, False),
        ('selected', F.GRID, 1, None, True), ('selected-scaled', F.GRID, 3, None, True),
        ('non-square', F.WIDE, 2, None, False)]:
        png_cases.append(case(cid, 'Export the prepared sprite as a PNG.', fixture,
                              ([*key('ArrowDown')] if selected else []) + export('png', scale, cols, selected),
                              [point('size', 'PNG canvas dimensions.', dl('png', only=['size'])),
                               point('pixels', 'PNG pixels and compositing.', dl('png', ['grid'], only=['grid']))]))
    out.append(episode('export-png', 'export', png_cases))
    gif_cases = []
    for cid, fixture, scale, loop in [('animation', F.ANIM, 1, True), ('once', F.GRID, 1, False),
                                     ('scaled', F.GRID, 2, True), ('composite', F.LAYERS, 1, True),
                                     ('non-square', F.WIDE, 1, True)]:
        gif_cases.append(case(cid, 'Export the prepared sprite as an animated GIF.', fixture, export('gif', scale, loop=loop),
            [point('size', 'GIF dimensions.', dl('gif', only=['size'])),
             point('frames', 'GIF animation frame count.', dl('gif', only=['frames'])),
             point('pixels', 'GIF content, frame order and transparency.', dl('gif', ['grid'], only=['grids'])),
             point('timing', 'GIF frame delay follows FPS.', dl('gif', ['delay'], only=['delays']), tol=1),
             point('loop', 'GIF repeat flag.', dl('gif', ['loop'], only=['loop']))]))
    out.append(episode('export-gif', 'export', gif_cases))
    zip_cases = []
    for cid, scale, split, names, prefix in [('frames', 1, False, False, 'walk_'), ('layers', 1, True, False, 'walk_'),
                                          ('names', 1, True, True, 'walk_'), ('scaled', 2, True, True, 'sprite_')]:
        zip_cases.append(case(cid, 'Export PNG frames in a ZIP archive.', F.GRID,
                              export('zip', scale, split=split, names=names, prefix=prefix),
                              [point('names', 'Frame and layer naming in the archive.', dl('zip', ['names'], only=['names'])),
                               point('images', 'Each exported frame contains the expected pixels.', dl('zip', ['grid'], only=['grids']))]))
    out.append(episode('export-zip', 'export', zip_cases))
    out.append(episode('export-other', 'export', [
        case('c-animation', 'Export the animation as a C array.', F.GRID, export('c'),
             [point('pixels', 'Packed C pixels preserve the frame order and compositing.', dl('c',only=['pixels'])),
              point('dimensions', 'C width, height and frame count describe the animation.', dl('c',['dimensions'],only=['dimensions']))]),
        case('c-nonsquare', 'Export a non-square sprite as a C array.', F.WIDE, export('c'),
             [point('pixels', 'C output includes the non-square image.', dl('c',only=['pixels'])),
              point('dimensions', 'C dimensions describe the non-square image.', dl('c',['dimensions'],only=['dimensions']))]),
        case('pixi', 'Export a PixiJS movie with an external PNG.', F.GRID, export('pixi', columns=2),
             [point('movie', 'PixiJS metadata addresses every frame in the PNG.', dl('pixi'))]),
        case('pixi-inline', 'Export a PixiJS movie with an inline PNG.', F.GRID, export('pixi', columns=1, inline=True),
             [point('movie', 'PixiJS metadata embeds a decodable spritesheet.', dl('pixi'))])]))
    return out


def save_file():
    cases = []
    for name, fixture, description in [('animation', F.GRID, 'Three frames\nTwo layers'),
                                     ('unicode', F.LAYERS, '星 / café 🎨\nline 2'), ('nonsquare', F.WIDE, 'wide')]:
        cases.append(case(name, f'Save the sprite with title {name} and the supplied description.', fixture,
            [drawer('save'), field('Title :', name), field('Description :', description),
             control(text='Save as .piskel', exact=True), {'op': 'wait-download', 'suffix': '.piskel'}],
            [point('name', 'The file stores the title.', dl('piskel', ['name'])),
             point('description', 'The file stores the description.', dl('piskel', ['description'])),
             point('fps', 'The file stores animation speed.', dl('piskel', ['fps'])),
             point('size', 'The file stores canvas dimensions.', dl('piskel', ['size'])),
             point('content', 'The file stores all layers, frame pixels and opacity.', dl('piskel', ['layers']))]))
    cases.append(case('roundtrip', 'Save as .piskel and reopen that file through the document API.', F.GRID,
                      [drawer('save'), control(text='Save as .piskel', exact=True),
                       {'op': 'wait-download', 'suffix': '.piskel'}, {'op': 'reload-download'}],
                      [point('document', 'Reopened saved content is editable and complete.', ALL)]))
    return episode('save-file', 'save', cases)


def persistence():
    cases = []
    for cid, between in [('reload', [{'op': 'reload'}]), ('restart', [{'op': 'restart'}, {'op': 'reload'}])]:
        cases.append(case(cid, 'Save in the browser, restart or reload, then load the browser save.', F.GRID,
             [drawer('save'), field('Title :', 'Stored animation'), field('Description :', 'persistent description'),
              control(text='Save in Browser', exact=True), settle(.5), *between, drawer('import'),
              control(text='Browse local saves', exact=True), control(text='Load', exact=True)],
             [point('name', 'Saved title survives.', meta('name')), point('description', 'Saved description survives.', meta('description')),
              point('fps', 'Saved animation speed survives.', meta('fps')), point('size', 'Saved dimensions survive.', SIZE),
              *[point(f'layer-{l}-frame-{f}', 'This saved animation cell survives.', pix(l, f)) for l in range(2) for f in range(3)]]))
    return episode('browser-storage', 'persistence', cases)


def build():
    return [layers(), *transforms(), resizing(), *exports(), save_file(), persistence()]
