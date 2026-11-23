"""GUI goals and reference routes. Pixel precision and file contents use program companions.

Each goal starts with its own prepared sprite. Recipes use public keyboard,
visible-control, pointer and file operations. The evaluator may choose any
visible route producing the requested result.
"""
import copy
import json
from pathlib import Path
import program as P
import program_extra as X
import program_episodes as W
import fixtures as F

SESSION = ('Each checkpoint starts from a fresh editor with the sprite described by the goal. Sprite coordinates '
           'are zero-based columns and rows, (0, 0) at the top left. pointer/drag accept target {"sprite": true}. '
           'Use the visible application, keyboard, pointer and provided input files. Native prompt answers must be '
           'set with dialog before the opening action. A toolbar may use icons named by tooltips in the snapshot.')
EQUIVALENTS = ['Any visible route to the requested result is valid, including tools, menus, fields and keyboard shortcuts.',
               'Different wording, layouts, icons and dialog designs are valid.']
BYPASSES = ['Do not replace a requested tool or command by manually recreating its result.',
            'Do not call scripting or document APIs to pursue the GUI goal.']
INITIAL = 'Fresh browser profile; the stated sprite is loaded before each goal.'


def goal(cid, text, acceptance, fixture, recipe, checks=(), prep=()):
    return {'id':cid, 'goal':text, 'acceptance':acceptance, 'fixture':F.encode(fixture) if fixture is not None else None,
            'recipe':list(recipe), 'steps':list(prep), 'checks':list(checks)}


def be(name, requirement, spec):
    return {'name':name, 'requirement':requirement, 'check':spec}


def episode(ident, feature, cases, files=()):
    out=[]
    for c in cases:
        assertions=[{'id':f'{ident}/{c["id"]}/visible','channel':'frontend','method':'agent','requirement':c['acceptance']}]
        for b in c['checks']:
            assertions.append({'id':f'{ident}/{c["id"]}/{b["name"]}','channel':'backend','method':'program',
                               'requirement':b['requirement'],'check':b['check']})
        out.append({k:v for k,v in c.items() if k not in ('acceptance','checks')} |
                   {'assertions':assertions,'depends_on':['setup:editor']})
    n=len(out)
    return {'id':ident,'feature':feature,'execution':'gui','initial_state':INITIAL,'setup':[{'id':'editor'}],
            'inputs':{'files':list(files)},'session':SESSION,'allowed_equivalents':EQUIVALENTS,
            'forbidden_bypasses':BYPASSES,'budget':{'calls':50+40*n,'tokens':500_000+700_000*n,'seconds':400+300*n},
            'checkpoints':out}


GOALS = {'animation/delete-1': 'Delete the second frame from the animation.',
 'animation/exclude-1': 'Exclude the second frame from animation preview without deleting its data.',
 'browser-storage/reload': 'Set the title to Stored animation and description to persistent description. Save '
                           'in the browser, reload the page, then reopen that browser save.',
 'browser-storage/restart': 'Set the title to Stored animation and description to persistent description. Save '
                            'in the browser, reload the page, then reopen that browser save.',
 'export-gif/animation': 'Export the animation as a GIF at original size, looping repeatedly.',
 'export-gif/once': 'Export the animation as a GIF at original size, with looping disabled.',
 'export-gif/scaled': 'Export the animation as a GIF at scale 2, looping repeatedly.',
 'export-other/pixi': 'Export a PixiJS movie with a separate PNG, two spritesheet columns, and original '
                      'resolution.',
 'export-other/pixi-inline': 'Export a PixiJS movie with the PNG embedded as a data URI, one spritesheet '
                             'column, at original resolution.',
 'export-png/scaled': 'Export the whole animation as a PNG spritesheet with two columns at scale 2.',
 'export-png/selected': 'Select the second animation frame and export only that frame as a PNG at original '
                        'size.',
 'export-png/sheet': 'Export the whole animation as a PNG spritesheet with three columns at original size.',
 'export-png/two-columns': 'Export the whole animation as a PNG spritesheet with two columns at original size.',
 'export-png/vertical': 'Export the whole animation as a PNG spritesheet with one column at original size.',
 'export-zip/frames': 'Export all frames to a ZIP at original size, with filename prefix walk_. Do not split '
                      'by layers.',
 'export-zip/layers': 'Export all frames to a ZIP at original size, with prefix walk_, split by layers, '
                      'indexed by layer numbers.',
 'export-zip/names': 'Export all frames to a ZIP at original size, with prefix walk_, split by layers, indexed '
                     'by layer names.',
 'import-combine/animation': 'Import motion.gif and combine its animation as new frames after the current '
                             'first frame.',
 'import-combine/expand': 'Import wide.png at original size and combine it as a new frame after the current '
                          'frame; expand the canvas to fit, anchored at the top left.',
 'import-combine/image-centre': 'Import small.png at original size and combine it as a new frame after the '
                                'current frame, centered in the current canvas.',
 'import-combine/keep': 'Import wide.png at original size and combine it as a new frame after the current '
                        'frame; keep the existing 2 by 2 canvas, cropping from the middle.',
 'import-combine/project-existing': 'Import actor.piskel from the inputs and combine it into existing frames '
                                    'starting at the current first frame.',
 'import-combine/project-frames': 'Import actor.piskel from the inputs and combine it with the current '
                                  'animation as new frames immediately after the current first frame.',
 'import-replace/offset': 'Import sheet.png from the inputs as a spritesheet with frame size 4 by 3 and offset '
                          'x=1, y=1; replace the sprite.',
 'import-replace/resize-8-6-0': 'Import small.png from the inputs as one image resized to 8 by 6, with '
                                'smoothing disabled, replacing the sprite.',
 'import-replace/resize-8-6-1': 'Import small.png from the inputs as one image resized to 8 by 6, with '
                                'smoothing enabled, replacing the sprite.',
 'import-replace/sheet': 'Import tiles.png from the inputs as a spritesheet with frame size 4 by 3 and zero '
                         'offset; replace the current sprite.',
 'palettes/colors-gpl': 'Import colors.gpl from the inputs as a palette named Imported colors. Paint pixels '
                        '(1, 1), (2, 1), (3, 1) with its first, second and third colors respectively, then '
                        'download the palette as a GPL file.',
 'palettes/colors-pal': 'Import colors.pal from the inputs as a palette named Imported colors. Paint pixels '
                        '(1, 1), (2, 1), (3, 1) with its first, second and third colors respectively, then '
                        'download the palette as a GPL file.',
 'palettes/colors-txt': 'Import colors.txt from the inputs as a palette named Imported colors. Paint pixels '
                        '(1, 1), (2, 1), (3, 1) with its first, second and third colors respectively, then '
                        'download the palette as a GPL file.',
 'palettes/next': 'Import colors.gpl as a palette named Imported colors. Select its first color, cycle forward '
                  'once, and paint pixel (4, 4).',
 'palettes/palette-png': 'Import palette.png from the inputs as a palette named Imported colors. Paint pixels '
                         '(1, 1), (2, 1), (3, 1) with its first, second and third colors respectively, then '
                         'download the palette as a GPL file.',
 'palettes/persist': 'Import colors.gpl as a palette named Imported colors. Reload the page, select the saved '
                     'palette, and paint pixel (4, 4) using its second color.',
 'palettes/previous': 'Import colors.gpl as a palette named Imported colors. Select its third color, cycle '
                      'backward once, and paint pixel (4, 4).',
 'preferences/color-format-rgb': 'Set color format to RGB, reload the page, then show that setting again.',
 'preferences/default-size': 'Set the default sprite size to width 20 and height 12, then reload to create a '
                             'fresh sprite.',
 'preferences/max-fps-60': 'Set Maximum FPS to 60, reload the page, then show that setting again.',
 'preferences/tile-mode': 'Enable tile mode, reload the page, then show the tile-mode setting.',
 'resize/anchor-4': 'Enlarge the canvas to 12 by 12, without resizing its content; anchor the original artwork '
                    'in the middle.',
 'resize/ratio': 'Resize the 6 by 4 sprite to width 12, with aspect ratio maintained and canvas content '
                 'resized.',
 'save-file/animation': 'Set the title to animation and the description to exactly:\n'
                        '```text\n'
                        'Three frames\n'
                        'Two layers\n'
                        '```\n'
                        'Save as a .piskel file.',
 'save-file/nonsquare': 'Set the title to nonsquare and the description to wide, then save as a .piskel file.',
 'save-file/unicode': 'Set the title to unicode and the description to exactly:\n'
                      '```text\n'
                      '星 / café 🎨\n'
                      'line 2\n'
                      '```\n'
                      'Save as a .piskel file.'}


GOALS.update({'center/center-current': 'Center the content of the current layer in the current frame.',
 'center/center-everything': 'Center content in all layers and all animation frames.',
 'crop/all-frames': 'Crop the entire sprite to the bounds of all content across every layer and frame.',
 'crop/content': 'Crop the sprite to fit its non-transparent content.',
 'crop/selection': 'Select the rectangle from (1, 1) to (5, 4), then crop the sprite to that selection.',
 'flip/horizontal-current': 'Flip the current layer of the current frame horizontally.',
 'flip/horizontal-everything': 'Flip all layers in all animation frames horizontally.',
 'flip/vertical-current': 'Flip the current layer of the current frame vertically.',
 'flip/vertical-everything': 'Flip all layers in all animation frames vertically.',
 'rotate/ccw-current': 'Rotate the current layer of the current frame counter-clockwise.',
 'rotate/ccw-everything': 'Rotate all layers in all animation frames counter-clockwise.',
 'rotate/cw-current': 'Rotate the current layer of the current frame clockwise.',
 'rotate/cw-everything': 'Rotate all layers in all animation frames clockwise.',
 'rotate/nonsquare': 'Rotate the current 6 by 4 image counter-clockwise.'})


GOALS.update({'resize/grow': 'Resize the canvas to 12 by 10, keeping the artwork at its original size, anchored at the top left.', 'resize/shrink': 'Resize the canvas to 5 by 6, keeping the artwork at its original size, anchored at the top left.', 'resize/upscale': 'Resize the canvas to 16 by 16, scaling its content to fit.', 'resize/downscale': 'Resize the canvas to 4 by 4, scaling its content to fit.', 'resize/stretch': 'Resize the canvas to 12 by 6, scaling its content to fit.'})


GOALS.update({'flip/vertical-current': 'Mirror the current layer of the current frame across the vertical centre line (exchange left and right).', 'flip/horizontal-current': 'Mirror the current layer of the current frame across the horizontal centre line (exchange top and bottom).', 'flip/vertical-everything': 'Mirror all layers in all animation frames across the vertical centre line (exchange left and right).', 'flip/horizontal-everything': 'Mirror all layers in all animation frames across the horizontal centre line (exchange top and bottom).'})

def from_program(source, definitions, files=()):
    """Reuse a reviewed stimulus as a reference route; state reads remain program companions."""
    lookup={c['id']:c for c in source['checkpoints']}
    cases=[]
    for entry in definitions:
        cid,acceptance,*override=entry
        cp=copy.deepcopy(lookup[cid])
        checks=[be(a['id'].rsplit('/',1)[-1],a['requirement'],a['check']) for a in cp['assertions']]
        c={'id':cid,'goal':override[0] if override else cp['goal'],'acceptance':acceptance,'fixture':cp['fixture'],
           'recipe':cp['steps'],'steps':[],'checks':checks}
        if source['id'] == 'lighten':
            # Strong visible changes; single-step color precision is program-only.
            if cid == 'darken':
                c['goal'] = 'Use the darken tool on the gray pixel (4, 0), with eight separate clicks.'
                c['recipe'] = [P.tool('lighten')] + [P.tap(4, 0, mods=['Control']) for _ in range(8)]
            else:
                x, y = (2, 2) if cid == 'size-2' else (0, 0)
                c['goal'] = f'Use the lighten tool on pixel ({x}, {y}), with eight separate clicks.'
                c['recipe'] = ([*P.key(']')] if cid == 'size-2' else []) + [P.tool('lighten')] + [P.tap(x, y) for _ in range(8)]
                if cid == 'size-2': c['goal'] = 'Set brush size 2, then ' + c['goal'].lower()
        if source['id'] == 'mirror-pen' and cid == 'drag':
            for check in c['checks']:
                check['check'].update(freehand_radius=1, mirror_axis='vertical')
        c['goal'] = GOALS.get(source['id'] + '/' + cid, c['goal'])
        if source['id'] == 'palettes' and cid in ('colors-gpl', 'colors-pal', 'colors-txt', 'palette-png'):
            c['recipe'].append(P.control(text='Cancel', exact=True))
            c['goal'] += ' Close the palette editor to view the painted pixels.'
        if source['id'] == 'import-combine' and cid != 'project-existing':
            c['recipe'] += P.key('ArrowDown')
            c['goal'] += ' Select the first newly imported frame to view it.'
        cases.append(c)
    return episode('gui-'+source['id'],source['feature'],cases,files)


def drawing():
    definitions={
      'pen': [('click','A new black mark appears on the canvas.'),('right-click','The targeted red area gains a transparent opening.'),
              ('diagonal','A diagonal stroke appears.'),('size-3','A broad square mark appears.'),
              ('size-drag','A thick horizontal stroke appears.'),('edge','A broad mark reaches the canvas corner.')],
      'mirror-pen': [('click','A pair of marks appears mirrored across the canvas.'),('ctrl','A vertically arranged mirrored pair appears.'),
                 ('shift','Four mirrored marks appear.'),('drag','Two mirrored strokes appear.'),
                 ('odd','Mirrored marks and a centre mark appear on the non-square canvas.')],
      'eraser': [('click','Part of the colored drawing is erased.'),('drag','A path through the colored drawing is erased.'),
                 ('size-3','A larger square region is erased.'),('right','The blue area has a transparent opening.')],
      'stroke': [('horizontal','A horizontal line appears.'),('vertical','A vertical line appears.'),
                 ('diagonal','A diagonal line appears.'),('detour','The result is a straight line connecting the final endpoints.'),
                 ('straight','A straight constrained stroke appears.'),('size-2','A thicker line appears.')],
      'rectangle': [('outline','A rectangular outline appears.'),('square','A square outline appears.'),
                    ('size-2','A rectangle with a thicker border appears.'),('over','A rectangular outline appears over the existing artwork.'),
                    ('right','The colored area loses its rectangular border.')],
      'circle': [('ellipse','An elliptical outline appears.'),('circle','A circular outline appears.'),
                 ('large','A large ellipse appears.'),('size-2','A circle with a thicker outline appears.')],
      'paint-bucket': [('enclosed','The inside of the green ring is filled.'),('background','A connected background region is filled.'),
                       ('colour','The connected green area changes color.'),('right','The red area is cleared.'),
                       ('diagonal','One side of the diagonal barrier is filled.')],
      'colour-swap': [('frame','All separated red areas in the current image change color.'),
                      ('transparent','The transparent areas are filled while existing colored marks remain.'),
                      ('right','The separated red areas become transparent.'),('layers','The color replacement is visible in the layered drawing.')],
      'lighten': [('lighten','A part of the red area becomes lighter.'),('darken','A part of the gray area becomes darker.'),
('size-2','A square area becomes lighter.')],
      'dithering': [('drag','The painted rows show an alternating checkerboard pattern.'),
                    ('right','The alternate checkerboard phase appears.'),('size-2','A small checkerboard mark appears.')],
      'colours': [('pick','The picked blue color is used for a new mark.'),('pick-secondary','The right mouse button paints in the picked green color.'),
                  ('swap','Painting after exchanging the two colors produces the requested colored and transparent marks.'),
                  ('reset','A new black mark appears after restoring the default colors.')],
      'move': [('right','The artwork is shifted right and down.'),('left','The artwork is shifted left and up.'),
               ('wrap','The moved artwork wraps around the canvas edges.'),('everything','The artwork is moved across the animation.')],
      'selection': [('delete','The selected rectangular area is cleared.'),('copy-paste','A copy of the selected content appears elsewhere.'),
                    ('cut-paste','The selected content moves to another location.'),('move-content','Dragging the selection moves its content.'),
                    ('other-frame','Copied content appears on another animation frame.'),('shape','The selected green shape is removed.'),
                    ('lasso','The area enclosed by the lasso is cleared.')],
      'undo': [('pen','The most recent mark is removed while the earlier mark remains.'),
               ('twice','Both newly drawn marks are removed.'),('redo','The undone mark reappears.'),
               ('redo-cleared','A new mark remains after replacing the undone action.'),
               ('bucket','The filled area returns to its earlier appearance.'),('move','The moved artwork returns to its original position.')],
      'frames': [('new','An additional empty frame appears in the timeline.'),('duplicate','A duplicate frame appears in the timeline.'),
                 ('duplicate-second','A copy of the second frame appears beside it.'),
                 ('new-selected','The newly created frame contains a painted mark.'),('add-button','An empty frame appears at the end of the timeline.')]
    }
    builders=[P.pen,P.mirror,P.eraser,P.stroke,P.rectangle,P.circle,P.bucket,P.colour_swap,P.lighten,P.dithering,
              P.colours,P.move,P.selection,P.undo,P.frames]
    return [from_program(w,definitions[w['id']]) for w in (fn() for fn in builders)]


def structure():
    out=[from_program(X.layers(),[
        ('create','A new layer appears and becomes available for drawing.'),('clone','A cloned layer appears with the same content.'),
        ('delete','The selected layer is removed and the remaining layer is visible.'),
        ('merge','The two layers become a single combined layer.'),('merge-animation','The animation layers are merged.'),
        ('up','The selected layer moves up in the layer order.'),('top','The selected layer becomes the topmost layer.'),
        ('down','The selected layer moves down in the layer order.'),('bottom','The selected layer becomes the bottom layer.'),
        ('selected-draw','The selected upper layer contains the new mark.'),('rename','The layer shows its new name.'),
        ('unicode-name','The layer shows the supplied Unicode name.'),
        ('opacity-0-25','The selected layer opacity changes to one quarter.'),('opacity-0-75','The selected layer opacity changes to three quarters.')])]
    for w in X.transforms():
        if w['id']=='flip': defs=[('vertical-current','The image is mirrored left to right.'),('horizontal-current','The image is mirrored top to bottom.'),
                                ('vertical-everything','The layered animation is mirrored left to right.'),('horizontal-everything','The layered animation is mirrored top to bottom.')]
        elif w['id']=='rotate': defs=[('ccw-current','The image is rotated counter-clockwise.'),('cw-current','The image is rotated clockwise.'),
                                    ('ccw-everything','The layered animation is rotated.'),('nonsquare','The non-square artwork is rotated.')]
        elif w['id']=='center': defs=[('center-current','The artwork is centered in its canvas.'),('center-everything','The layered animation is centered.')]
        elif w['id']=='clone-frames': defs=[('clone','The current layer image is copied throughout the timeline.')]
        else: defs=[('content','The canvas is cropped around its artwork.'),('selection','The canvas is cropped to the selected rectangle.'),
                    ('all-frames','The animation is cropped to its combined content bounds.')]
        out.append(from_program(w,defs))
    out.append(from_program(X.resizing(),[
        ('grow','The canvas is larger while the artwork keeps its size.'),('shrink','The canvas is cropped to a smaller size.'),
        ('upscale','The artwork and canvas are enlarged together.'),('downscale','The artwork and canvas are reduced together.'),
        ('stretch','The artwork is stretched to a wider canvas.'),('anchor-4','The original artwork is centered in an enlarged canvas.'),
        ('ratio','The canvas and artwork double in size while keeping their aspect ratio.')]))
    return out


def files():
    defs={
      'export-png':[('sheet','A PNG spritesheet is offered as a download.'),('vertical','A vertical PNG spritesheet is offered as a download.'),
                    ('two-columns','A PNG spritesheet arranged in two columns is offered as a download.'),
                    ('scaled','An enlarged PNG spritesheet is offered as a download.'),('selected','The selected frame is offered as a PNG download.')],
      'export-gif':[('animation','An animated GIF is offered as a download.'),('once','A GIF configured to play once is offered as a download.'),
                    ('scaled','An enlarged GIF is offered as a download.')],
      'export-zip':[('frames','A ZIP archive of animation frames is offered as a download.'),
                    ('layers','A ZIP archive split into layers is offered as a download.'),
                    ('names','A ZIP archive indexed by layer names is offered as a download.')],
      'export-other':[('c-animation','A C source file containing the animation is offered as a download.'),
                      ('pixi','A PixiJS movie archive is offered as a download.'),('pixi-inline','A PixiJS movie with inline image data is offered as a download.')],
    }
    out=[from_program(w,defs[w['id']]) for w in X.exports()]
    out.append(from_program(X.save_file(),[
        ('animation','The sprite is offered as a .piskel file with its title.'),('unicode','The sprite is offered as a .piskel file.'),
        ('nonsquare','The non-square sprite is offered as a .piskel download.')]))
    out.append(from_program(X.persistence(),[
        ('reload','The saved animation can be reopened after reloading the page.')]))
    imported=W.imports()
    files=['small.png','small.bmp','small.jpg','wide.png','motion.gif','actor.piskel','tiles.png','sheet.png']
    out.append(from_program(imported[0],[
        ('small-png','The imported PNG replaces the artwork.'),('small-bmp','The imported bitmap replaces the artwork.'),
        ('small-jpg','The imported JPEG replaces the artwork.'),('motion-gif','The imported GIF appears as multiple animation frames.'),
        ('actor-piskel','The project opens with its layers and frames.'),

        ('resize-8-6-0','The imported image appears enlarged with crisp pixel edges.'),
        ('resize-8-6-1','The imported image appears enlarged with smoothing.'),
        ('sheet','The spritesheet appears as separate animation frames.'),('offset','The offset spritesheet appears as separate frames.')],files))
    out.append(from_program(imported[1],[
        ('project-frames','The imported project adds its frames to the existing animation.'),
        ('project-existing','The imported project combines with existing frames.'),
        ('image-centre','The imported image is centered in the combined sprite.'),
        ('expand','The combined sprite expands to fit the imported image.'),
        ('keep','The imported image is cropped into the retained canvas.'),
        ('animation','The imported GIF adds animation frames.')],files))
    return out


def additional():
    out=[from_program(W.frames_more(),[
        ('delete-1','The middle frame is removed from the timeline.'),('exclude-1','The second frame is excluded from preview.'),
        ('reorder','The first frame moves to the end of the timeline.'),('fps-0','Animation preview is paused.'),
        ('fps-6','The displayed animation speed is six frames per second.'),('fps-18','The animation speed changes to eighteen frames per second.')])]
    out.append(from_program(W.palettes(),[
        ('colors-gpl','An imported GPL palette is available, its colors paint, and the palette is offered for download.'),
        ('colors-pal','An imported PAL palette is available and its colors can be used.'),
        ('colors-txt','An imported Paint.NET palette is available and its colors can be used.'),
        ('palette-png','Colors extracted from the image form a usable palette.'),
        ('next','Cycling forward through the palette changes the painting color.'),
        ('previous','Cycling backward through the palette changes the painting color.'),
        ('persist','The imported palette remains usable after reloading.')], ['colors.gpl','colors.pal','colors.txt','palette.png']))
    out.append(from_program(W.preferences(),[
        ('max-fps-60','The configured maximum frame rate survives a reload.'),
        ('color-format-rgb','The RGB color notation remains selected after a reload.'),
        ('tile-mode','Tile mode remains enabled after a reload.'),('default-size','The new sprite uses the configured default dimensions.')]))
    view=[]
    for cid,text,acceptance,recipe in [
        ('shortcuts','Open the keyboard shortcut reference.','The editor shows its keyboard shortcut reference.',
         [P.control(title='Keyboard shortcuts')]),
        ('onion','Enable onion skinning on the second animation frame.','Another frame is visible as an onion-skin overlay.',
         [*P.key('ArrowDown'),*P.key('Alt+o')]),
        ('zoom-in','Increase the canvas zoom.','The sprite is visibly magnified.',P.key('+',2)),
        ('zoom-out','Decrease the canvas zoom.','The sprite is shown at a smaller scale.',P.key('-',3)),
        ('fit','Zoom out, then fit the sprite to the available drawing area.','The sprite is fitted to the drawing area.',
         [*P.key('-',3),*P.key('0')]),
        ('preview-best','Set the animation preview to the best integer scale that fits its preview area.','The preview uses a fitted integer scale.',P.key('Alt+2')),
        ('grid','Enable a grid over the drawing.','A grid is visible over the artwork.',P.key('Alt+g')),
        ('tile','Enable tiled drawing mode.','The artwork is repeated around the central tile.',
         [X.drawer('preferences'),P.control(text='Tile mode',exact=True),
          {'op':'check','target':{'label':'Enable tile mode'},'checked':True},X.drawer('preferences')]),
        ('background','Use the light high-contrast canvas background.','Transparent areas use the selected canvas background.',
         [X.drawer('preferences'),P.control(title='light / high contrast',exact=True),X.drawer('preferences')])]:
        view.append(goal(cid,text,acceptance,F.PREVIEW if cid=='preview-best' else F.ANIM if cid=='onion' else F.ARROW,recipe,prep=P.key('Alt+1') if cid=='preview-best' else P.key('-',5) if cid=='zoom-in' else ()))
    out.append(episode('gui-view','view',view))
    return out


def build():
    import specification_extra
    import specification_supplement
    import specification_review
    episodes = drawing()+structure()+files()+additional()+specification_extra.build()+specification_supplement.build()+specification_review.build()
    # Bound each independent evaluator session below the host bridge ceiling.
    # Checkpoints prepare fresh state and carry no cross-checkpoint dependencies.
    result = []
    for wf in episodes:
        checkpoints = wf['checkpoints']
        if len(checkpoints) <= 8:
            result.append(wf)
            continue
        split = (len(checkpoints) + 1) // 2
        for suffix, group in [('a', checkpoints[:split]), ('b', checkpoints[split:])]:
            part = copy.deepcopy(wf)
            part['id'] = wf['id'] + '-' + suffix
            part['checkpoints'] = copy.deepcopy(group)
            for cp in part['checkpoints']:
                for assertion in cp['assertions']:
                    assertion['id'] = part['id'] + assertion['id'][len(wf['id']):]
            n = len(group)
            part['budget'] = {'calls': 50+40*n, 'tokens': 500_000+700_000*n, 'seconds': 400+300*n}
            result.append(part)
    for wf in result:
        # Visible group context increases observation size. Reserve sufficient space for exploration
        # and for the provider retry wall time included by the fixed kit's time estimator.
        wf['budget'] = {'calls':400, 'tokens':8_000_000, 'seconds':12000}
    return result
