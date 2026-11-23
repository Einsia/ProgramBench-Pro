"""Image import, animation controls, palettes and durable preferences."""
import copy
from program import F, case, episode, point, pix, meta, control, key, tool, tap, drag, settle, ALL, SIZE, FRAMES, HIDDEN
from program_extra import ui, field, drawer, export, dl


def input_file(filename, drop=False):
    suffix = filename.rsplit('.', 1)[-1]
    mime = {'png':'image/png', 'jpg':'image/jpeg', 'bmp':'image/bmp', 'gif':'image/gif'}.get(suffix, 'application/octet-stream')
    return {'op': 'input', 'action': 'drop' if drop else 'upload', 'filename': filename, 'mime_type': mime,
            **({'target': {'sprite': True}, 'x': 4, 'y': 4} if drop else {})}


def import_steps(filename, mode='replace', drop=False, w=None, h=None, smooth=False, sheet=None, keep=False, anchor=None,
                 existing=False):
    piskel = filename.endswith('.piskel')
    steps = [input_file(filename, True)] if drop else [drawer('import'),
        control(text='Browse .piskel files' if piskel else 'Browse images', exact=True), input_file(filename)]
    # The palette is populated asynchronously; the import wizard uses it to choose its empty-canvas route.
    steps.insert(0, {'op': 'wait-text-gone', 'text': 'No color in this palette'})
    if drop:
        return steps
    if filename.endswith(('.png', '.jpg', '.bmp', '.gif')):
        if sheet:
            fw, fh, ox, oy = sheet
            steps += [{'op': 'check', 'target': {'label': 'Import as spritesheet'}, 'checked': True},
                      ui('fill', {'editable':True,'dimension':['Frame size','width']}, value=str(fw)),
                      ui('fill', {'editable':True,'dimension':['Frame size','height']}, value=str(fh)),
                      ui('fill', {'editable':True,'dimension':['Offset','width']}, value=str(ox)),
                      ui('fill', {'editable':True,'dimension':['Offset','height']}, value=str(oy))]
        elif w is not None:
            steps += [ui('fill', {'editable':True,'dimension':['Resize to','width']}, value=str(w)),
                      ui('fill', {'editable':True,'dimension':['Resize to','height']}, value=str(h)),
                      ui('check', {'semantic':'Smooth resize'}, checked=smooth)]
        steps += [control(text='next', exact=True)]
    steps += [control(text='Replace' if mode=='replace' else 'Combine', exact=True)]
    if mode == 'combine':
        # Equal sizes skip the adjustment step; callers mark that with anchor='same'.
        if anchor != 'same':
            if keep:
                steps += [control(text='Keep canvas size', exact=False)]
            if anchor:
                steps += [control(title=anchor, exact=True)]
            steps += [control(text='next', exact=True)]
        if existing:
            steps += [{'op':'check','target':{'label':'in existing frames'},'checked':True}]
        steps += [control(text='import', exact=True)]
    return steps


def imports():
    cases=[]
    for name in ('small.png','small.bmp','small.jpg','wide.png','wide.bmp','wide.jpg','motion.gif','actor.piskel'):
        points=[point('size','Imported canvas dimensions.',SIZE), point('frames','Imported animation length.',FRAMES),
                point('content','Imported image and layer content.',ALL)]
        cases.append(case(name.replace('.','-'),'Replace the sprite with the input file '+name+'.',F.REGIONS,
                          import_steps(name),points))
    cases += [case('drop-piskel','Drop actor.piskel onto the editor and replace the sprite.',F.REGIONS,
                   import_steps('actor.piskel',drop=True),[point('content','Dropped project opens with all layers and frames.',ALL)]),
              case('drop-png','Drop small.png at pixel (4, 4) of the current frame.',F.REGIONS,
                   import_steps('small.png',drop=True),[point('size','Image dimensions.',SIZE),point('content','Dropped pixels.',ALL)])]
    for w,h,smooth in [(8,6,False),(8,6,True),(2,2,False),(2,2,True),(12,3,False)]:
        cases.append(case(f'resize-{w}-{h}-{int(smooth)}','Import small.png at the requested resolution.',F.REGIONS,
                          import_steps('small.png',w=w,h=h,smooth=smooth),[point('size','Import resize dimensions.',SIZE),
                                                                                     point('content','Import resampling.',ALL)]))
    for cid,name,sheet in [('sheet','tiles.png',(4,3,0,0)),('offset','sheet.png',(4,3,1,1)),
                           ('single-row','tiles.png',(4,6,0,0)),('single-column','tiles.png',(8,3,0,0))]:
        cases.append(case(cid,'Import '+name+' as a spritesheet with specified frame size and offset.',F.REGIONS,
                          import_steps(name,sheet=sheet),[point('size','Frame dimensions.',SIZE),
                           point('frames','Number of extracted frames.',FRAMES),point('content','Sheet frame order and pixels.',ALL)]))
    out=[episode('import-replace','import',cases)]
    cases=[]
    for cid,fixture,name,anchor,keep,existing in [
        ('project-frames',F.ANIM,'actor.piskel','same',False,False),
        ('project-existing',F.ANIM,'actor.piskel','same',False,True),
        ('image-top-left',F.GRID,'small.png','top left',False,False),
        ('image-centre',F.GRID,'small.png','middle',False,False),
        ('image-bottom',F.GRID,'small.png','bottom right',False,True),
        ('expand',F.one('tiny','rg\n.b',2,2),'wide.png','top left',False,False),
        ('keep',F.one('tiny','rg\n.b',2,2),'wide.png','middle',True,False),
        ('animation',F.GRID,'motion.gif','same',False,False)]:
        cases.append(case(cid,'Combine '+name+' with the current sprite using the specified placement.',fixture,
                          import_steps(name,mode='combine',anchor=anchor,keep=keep,existing=existing),
                          [point('size','Combined canvas dimensions.',SIZE),point('frames','Combined timeline length.',FRAMES),
                           point('content','Merged frames and layers retain both documents.',ALL)]))
    out.append(episode('import-combine','import',cases))
    return out


def frames_more():
    cases=[]
    for frame in (0,1,2):
        cases.append(case('delete-'+str(frame),'Delete the specified frame from both layers.',F.GRID,
                          [{'op':'hover','target':{'text':str(frame+1)}},
                           control(title='Delete this frame')],
                          [point('count','One frame is removed.',FRAMES),
                           point('content','The correct frame is removed in every layer.',ALL)]))
    for frame in (0,1,2):
        cases.append(case('exclude-'+str(frame),'Exclude this frame from animation preview.',F.GRID,
                          [control(text=str(frame+1),exact=True)],
                          [point('hidden','The specified frame is excluded.',HIDDEN)]))
    cases.append(case('reorder','Move the first timeline frame after the third.',F.GRID,
        [ui('drag-to',{'title':'Toggle for preview','text':'1'},to={'title':'Toggle for preview','text':'3'},
            dx=50,dy=50,to_dx=50,to_dy=80)],
        [point('content','Frame reordering applies to every layer.',ALL)]))
    fps_fixture=copy.deepcopy(F.ANIM);fps_fixture['fps']=12
    for fps in (0,1,6,18,24):
        cases.append(case('fps-'+str(fps),f'Set animation speed to {fps} FPS.',fps_fixture,
            [ui('press',{'label':'FPS','contains':True},key='End' if fps>12 else 'Home')]+
            [ui('press',{'label':'FPS','contains':True},key='ArrowLeft' if fps>12 else 'ArrowRight') for _ in range(24-fps if fps>12 else fps)],
            [point('fps','The animation rate follows the control.',meta('fps'))]))
    return episode('animation','frames',cases)


def palette_import(name):
    return [control(title='Create a new palette'),control(text='Import from file',exact=True),input_file(name),
            fill_palette_name('Imported colors'),control(text='Save',exact=True),
            {'op':'wait-control','match':{'has_option':'Imported colors'}},settle(.4)]


def fill_palette_name(name):
    return ui('fill',{'placeholder':'palette name ...'},value=name)


def palettes():
    cases=[]
    for filename in ('colors.gpl','colors.pal','colors.txt','palette.png'):
        cases.append(case(filename.replace('.','-'),'Import the palette, use its colors, and export it.',F.BLANK,
            palette_import(filename)+key('1')+[tool('pen'),tap(1,1)]+key('2')+[tap(2,1)]+key('3')+[tap(3,1)]+
            [control(title='Manage this palette'),control(text='Download as file',exact=True),{'op':'wait-download','suffix':'.gpl'}],
            [point('pixels','Imported colors can be used to paint.',pix()),point('palette','GPL export contains the palette colors.',dl('gpl'))]))
    for cid,chords in [('next',['1','>']),('previous',['3','<']),('wrap-next',['4','>']),('wrap-previous',['1','<'])]:
        cases.append(case(cid,'Select and cycle through the imported palette, then paint.',F.BLANK,
                          palette_import('colors.gpl')+[s for k in chords for s in key(k)]+[tool('pen'),tap(4,4)],
                          [point('color','Palette cycling selects the expected paint color.',pix())]))
    cases.append(case('persist','Import a palette, reload, select it and paint with its second color.',F.BLANK,
        palette_import('colors.gpl')+[{'op':'reload'},ui('select',{'has_option':'Imported colors'},value='Imported colors'),
                                    *key('2'),tool('pen'),tap(4,4)],
        [point('color','The custom palette survives a page reload.',pix())]))
    return episode('palettes','colours',cases)


def preferences():
    cases=[]
    for value in ('48','60','120'):
        cases.append(case('max-fps-'+value,'Set and persist the maximum animation speed.',F.ANIM,
            [drawer('preferences'),field('Maximum FPS',value),*key('Tab'),{'op':'reload'},drawer('preferences')],
            [point('maximum','Maximum FPS survives reload.',{'type':'control','match':{'label':'Maximum FPS'},'fields':['value']})]))
    for value in ('rgb','hex'):
        cases.append(case('color-format-'+value,'Choose the color notation and reload.',F.REGIONS,
            [drawer('preferences'),{'op':'select','target':{'label':'Color format'},'value':value},{'op':'reload'},drawer('preferences')],
            [point('notation','Color format preference survives reload.',{'type':'control','match':{'label':'Color format'},'fields':['value']})]))
    cases.append(case('tile-mode','Enable tile mode, reload and inspect the setting.',F.ARROW,
        [drawer('preferences'),control(text='Tile mode',exact=True),{'op':'check','target':{'label':'Enable tile mode'},'checked':True},
         {'op':'reload'},drawer('preferences'),control(text='Tile mode',exact=True)],
        [point('enabled','Tile mode remains enabled.',{'type':'control','match':{'label':'Enable tile mode'},'fields':['checked']})]))
    cases.append(case('default-size','Set the default drawing size and reload to a fresh sprite.',None,
        [drawer('resize'),field('Width',20,scope='Default size'),field('Height',12,scope='Default size'),control(text='Set default',exact=True),{'op':'reload'}],
        [point('size','A fresh sprite uses the configured default size.',SIZE)]))
    return episode('preferences','preferences',cases)


def build():
    return [*imports(),frames_more(),palettes(),preferences()]
