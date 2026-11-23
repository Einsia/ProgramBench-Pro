"""Interactive color entry, palette editing, view settings and backup recovery."""
from specification import goal, episode, be
import program as P
import program_extra as X
import program_episodes as W
import fixtures as F


def build():
    colors=[]
    for cid,which,value,button in [('hex','primary','#123abc',None),('short-hex','primary','#0f0',None),
                                   ('rgb','primary','rgb(210, 90, 40)',None),('secondary','secondary','#8844cc','right'),
                                   ('white','primary','#ffffff',None),('black','secondary','#000000','right')]:
        colors.append(goal(cid,f'Set the {which} color to {value}, then paint pixel (3, 3) with it.',
                           'The color chooser accepts the requested color and a new mark uses it.',F.BLANK,
                           [*([{'op':'color','which':which,'value':'#8844cc'}] if cid=='black' else []),{'op':'color','which':which,'value':value},P.tool('pen'),P.tap(3,3,button)],
                           [be('pixel','The painted pixel has the requested color.',P.pix())]))
    colors.append(goal('swap','Set the primary color to #ee4400 and the secondary to #22aaff. Exchange the colors, then paint pixel (3, 3) with the left button.',
                       'After the colors are exchanged, the new mark uses the former secondary color.',F.BLANK,
                       [{'op':'color','value':'#ee4400'},{'op':'color','which':'secondary','value':'#22aaff'},*P.key('x'),P.tool('pen'),P.tap(3,3)],
                       [be('pixel','The former secondary color is used.',P.pix())]))
    colors.append(goal('reset','Set the primary color to #ee4400, restore the default colors, then paint pixel (3, 3).',
                       'A new black mark appears after the defaults are restored.',F.BLANK,
                       [{'op':'color','value':'#ee4400'},*P.key('d'),P.tool('pen'),P.tap(3,3)],
                       [be('pixel','Default primary is black.',P.pix())]))
    out=[episode('gui-color-entry','colours',colors)]
    palette=[
      goal('create','Create a palette named Custom ink containing the color #336699. Use that color to paint pixel (3, 3).',
           'A custom palette is available and its color can paint.',F.BLANK,
           [P.control(title='Create a new palette'),W.fill_palette_name('Custom ink'),
            X.ui('fill',{'editable':True,'value_pattern':r'#[0-9a-fA-F]{3,8}'},value='#336699'),*P.key('Tab'),P.control(text='Save',exact=True),
            *P.key('1'),P.tool('pen'),P.tap(3,3)], [be('pixel','The palette color paints.',P.pix())]),
      goal('rename','The palette Imported colors is prepared. Rename it to Renamed colors.',
           'The palette is available under its new name.',F.BLANK,
           [P.control(title='Manage this palette'),W.fill_palette_name('Renamed colors'),P.control(text='Save',exact=True)],
           [be('names','Renamed palette is listed.',{'type':'palette-names'})], prep=W.palette_import('colors.gpl')),
      goal('delete','Delete the prepared palette Imported colors.',
           'The custom palette is removed and the current-colors palette is available.',F.BLANK,
           [P.control(title='Manage this palette'),P.control(text='Delete',exact=True)],
           [be('names','Deleted palette is absent.',{'type':'palette-names'})], prep=W.palette_import('colors.gpl')),
    ]
    out.append(episode('gui-palette-edit','colours',palette,files=['colors.gpl']))
    selections=[
      goal('reselect-rect','A rectangle over the red region is selected. Select a new rectangle from (4, 4) to (7, 7), then delete its pixels.',
           'The newly selected green region is cleared while the red region remains.',F.REGIONS,
           [P.drag(4,4,7,7),*P.key('Delete')],[be('pixels','The replacement selection is cleared.',P.pix())],
           prep=[P.tool('rect-select'),P.drag(0,0,3,3)]),
      goal('move-outline','A rectangle from (0, 0) to (3, 3) is selected. Move only its outline by (1, 1), then delete the newly selected pixels.',
           'The moved selection determines the erased region, leaving the original top and left edges.',F.REGIONS,
           [P.drag(1,1,2,2),*P.key('Delete')],[be('pixels','Moving the outline changes the deleted region.',P.pix())],
           prep=[P.tool('rect-select'),P.drag(0,0,3,3)]),
    ]
    selections.append(goal('copy-layer','A red rectangle is selected on the front layer. Copy it to the back layer at the same position.',
                           'The selected content is copied to the other layer.',F.LAYERS,
                           [*P.key('Control+c'),X.layer_select('back'),*P.key('Control+v')],
                           [be('pixels','Copied pixels reach the other layer.',P.pix(0))],
                           prep=[X.layer_select('front'),P.tool('rect-select'),P.drag(2,2,3,3)]))
    out.append(episode('gui-selection-more','selection',selections))
    view=[]
    for cid,label,recipe in [
      ('pan','Pan the viewport down and right without moving or changing the sprite pixels.',[*P.key('Shift+ArrowDown'),*P.key('Shift+ArrowRight')]),
      ('preview-native','Set the animation preview to native size.',P.key('Alt+1')),
      ('preview-full','Set the animation preview to full size, filling the preview area.',P.key('Alt+3')),
      ('layer-preview','Show the other layers while editing the current layer.',P.key('Alt+l')),
      ('dark-background','Choose the dark, low-contrast canvas background.',[X.drawer('preferences'),P.control(title='dark / low contrast',exact=True),X.drawer('preferences')]),
      ('grid-size','Enable the drawing grid and set its line size to 3px.',[X.drawer('preferences'),P.control(text='Grid',exact=True),P.control(title='3px',exact=True),X.drawer('preferences'),*P.key('Alt+g')]),
      ('grid-spacing','Enable the drawing grid and set its spacing to 4px.',[X.drawer('preferences'),P.control(text='Grid',exact=True),X.ui('click',{'title':'4px','scope':'Grid spacing'}),X.drawer('preferences'),*P.key('Alt+g')]),
      ('tile-mask','Enable tile mode and set its mask opacity to the maximum.',[X.drawer('preferences'),P.control(text='Tile mode',exact=True),
       {'op':'check','target':{'label':'Enable tile mode'},'checked':True},X.ui('press',{'label':'Mask opacity'},key='End'),X.drawer('preferences')]),
    ]:
        preview_fixture = F.sprite('preview', [F.layer('Layer 1', [[[F.PALETTE['r' if x<35 and y<25 else 'g' if y<25 else 'b'] for x in range(70)] for y in range(45)]])])
        view.append(goal(cid,label,'The viewport moves down and right across the unchanged artwork.' if cid=='pan' else 'The requested view setting is visibly applied.',F.LAYERS if cid=='layer-preview' else preview_fixture if cid in ('preview-full','pan') else F.ARROW,
                         recipe,prep=P.key('Alt+l') if cid=='layer-preview' else P.key('+',12) if cid=='pan' else P.key('Alt+2') if cid=='preview-native' else [X.drawer('preferences'),P.control(title='light / high contrast',exact=True),X.drawer('preferences')] if cid=='dark-background' else ()))
    out.append(episode('gui-view-settings','view',view))
    backup=goal('restore','An automatic backup of the arrow sprite has been prepared, and the canvas now shows an unrelated blank sprite. Browse the backup and restore the arrow.',
                'The original arrow artwork is restored from the automatic backup.',F.ARROW,
                [X.drawer('import'),P.control(text='Browse backups',exact=True),P.control(text='View',exact=True),P.control(text='Load',exact=True)],
                [be('pixels','Recovered backup contains the original image.',P.pix())],
                prep=[P.settle(3) for _ in range(22)]+[{'op':'reload'},{'op':'load','piskel':F.encode(F.BLANK)}])
    out.append(episode('gui-backup','persistence',[backup]))
    return out
