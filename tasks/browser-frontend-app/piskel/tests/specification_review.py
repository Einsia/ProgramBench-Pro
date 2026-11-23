"""Offline preferences, palette components, storage deletion, exports and batch image input."""
import copy
from specification import goal, episode, be
import fixtures as F
import program as P
import program_extra as X
import program_episodes as W


def unchanged():
    return [be('document','View preferences leave all artwork unchanged.',P.ALL),
            be('opacity','View opacity leaves every stored layer opacity unchanged.',{'type':'opacities'})]


def grid_color(color):
    return [X.drawer('preferences'),P.control(text='Grid',exact=True),
            {'op':'check','target':{'label':'Enable grid'},'checked':True},
            X.ui('click',{'title':'3px','scope':'Grid size'}),X.ui('click',{'title':color,'scope':'Grid color'}),
            X.drawer('preferences')]


def views():
    goals=[]
    for color in ('red','blue'):
        goals.append(goal('grid-'+color,f'Enable the drawing grid with 3px lines colored {color}.',
                          'The drawing grid is clearly visible in the requested color.',F.ARROW,grid_color(color),
                          [be('pixels','Changing the grid leaves the sprite pixels intact.',P.ALL)]))
    goals.append(goal('grid-persist','A blue grid with 3px lines is prepared. Reload the page and show the same grid over the drawing area.',
                      'The grid color and line width persist across reload.',F.ARROW,[{'op':'reload'}],
                      prep=grid_color('blue')))
    for value in (0,1):
        recipe=[X.drawer('preferences'),X.ui('press',{'semantic':'Layer opacity'},key='Home' if value==0 else 'End'),X.drawer('preferences')]
        goals.append(goal('layer-preview-'+str(value),f'Set the preview opacity of other layers to {value}, keeping the selected back layer and all saved layer opacity values unchanged.',
                          'Other-layer artwork is hidden.' if value==0 else 'Other-layer artwork is clearly visible at full preview opacity.',
                          F.LAYERS,recipe,unchanged()))
    goals.append(goal('preview-persist','The preview opacity of other layers is set to 1. Reload the page, then show this preference.',
                      'The other-layer preview opacity setting remains at 1 after reload.',F.LAYERS,
                      [{'op':'reload'},X.drawer('preferences')],
                      [be('setting','The persisted preview opacity is one.',{'type':'control','match':{'semantic':'Layer opacity'},'fields':['value']})],
                      prep=[X.drawer('preferences'),X.ui('press',{'semantic':'Layer opacity'},key='End'),X.drawer('preferences')]))
    return episode('gui-view-preferences','preferences',goals)


def component(name,value):
    return [X.ui('fill',{'editable':True,'component':name},value=str(value)),*P.key('Tab')]


def components():
    goals=[]
    for cid,values in [('hue',[('H',210),('S',75),('V',80)]),('saturation',[('H',30),('S',40),('V',90)]),
                       ('value',[('H',120),('S',80),('V',35)]),('red',[('R',200),('G',40),('B',80)]),
                       ('green',[('R',20),('G',180),('B',60)]),('blue',[('R',50),('G',80),('B',220)]),
                       ('red-boundary',[('R',999),('G',80),('B',40)])]:
        assignment=', '.join(f'{key}={value}' for key,value in values)
        recipe=[P.control(title='Create a new palette'),W.fill_palette_name('Components')]
        recipe += [step for key,value in values for step in component(key,value)]
        recipe += [P.control(text='Save',exact=True),*P.key('1'),P.tool('pen'),P.tap(3,3),
                   P.control(title='Manage this palette'),P.control(text='Download as file',exact=True),
                   {'op':'wait-download','suffix':'.gpl'},P.control(text='Cancel',exact=True)]
        goals.append(goal(cid,f'Create a palette named Components. Set its first color using {assignment}. Save it, paint pixel (3, 3) with the color, then export the palette as GPL.',
                          'The edited palette can paint with its color and is offered as a GPL download.',F.BLANK,recipe,
                          [be('pixel','The painted pixel uses the component values.',{'type':'pixel','x':3,'y':3}),
                           be('palette','The exported palette stores the component values.',X.dl('gpl'))]))
    goals.append(goal('cancel','The palette Imported colors is prepared. Change the first color red component to 99 in the palette editor, then cancel the edit. Paint pixel (3, 3) with the first saved palette color.',
                      'Cancel preserves the saved palette color, which still paints.',F.BLANK,
                      [P.control(title='Manage this palette'),*component('R',99),P.control(text='Cancel',exact=True),*P.key('1'),P.tool('pen'),P.tap(3,3)],
                      [be('pixel','The canceled component edit does not replace the saved color.',{'type':'pixel','x':3,'y':3})],
                      prep=W.palette_import('colors.gpl')))
    result=episode('gui-palette-components','colours',goals)
    result['checkpoints'][-1]['assertions'][-1]['requires']=['gui-palette-components/red/pixel']
    return result


def saved(name,sprite):
    return [{'op':'load','piskel':F.encode(sprite)},X.drawer('save'),X.field('Title :',name),
            P.control(text='Save in Browser',exact=True),P.settle(.5)]


def storage():
    names=['Amber save','Azure save']
    prep=saved(names[0],F.ARROW)+saved(names[1],F.REGIONS)
    browse=[X.drawer('import'),P.control(text='Browse local saves',exact=True)]
    remove=[X.dialog(response='accept'),X.ui('click',{'semantic':'Delete','scope':names[0]})]
    goals=[goal('delete','Two browser saves are prepared: Amber save and Azure save. Delete Amber save and leave the list open.',
                'Only Azure save remains in the browser-save list.',None,browse+remove,
                [be('list','Only the requested stored document is removed.',{'type':'listed-documents','names':names})],prep=prep),
           goal('delete-persist','Two browser saves are prepared. Delete Amber save, reload, then load Azure save.',
                'The remaining Azure save reopens after deletion and reload.',None,
                browse+remove+[{'op':'reload'}]+browse+[X.ui('click',{'semantic':'Load','scope':names[1]})],
                [be('pixels','The other saved artwork survives.',P.ALL)],prep=prep),
           goal('cancel-delete','Two browser saves are prepared. Start deleting Amber save, then cancel the confirmation and leave the list open.',
                'Both browser saves remain available after cancellation.',None,
                browse+[X.dialog(response='dismiss'),X.ui('click',{'semantic':'Delete','scope':names[0]})],
                [be('list','Cancel retains both saved works.',{'type':'listed-documents','names':names})],prep=prep)]
    return episode('gui-storage-delete','persistence',goals)


def backups():
    first=copy.deepcopy(F.ARROW);first['name']='Backup amber'
    second=copy.deepcopy(F.REGIONS);second['name']='Backup azure'
    wait=[P.settle(3) for _ in range(22)]
    prep=[{'op':'load','piskel':F.encode(first)}]+wait+[{'op':'reload'},{'op':'load','piskel':F.encode(second)}]+wait+[{'op':'reload'},{'op':'load','piskel':F.encode(F.BLANK)}]
    browse=[X.drawer('import'),P.control(text='Browse backups',exact=True)]
    names=['Backup amber','Backup azure']
    goals=[goal('delete-session','Two automatic backup sessions are prepared: Backup amber and Backup azure. Delete Backup amber, then leave the session list open.',
                'Backup amber is removed while Backup azure remains available.',None,
                browse+[X.dialog(response='accept'),X.ui('click',{'semantic':'Delete','scope':names[0]})],
                [be('list','The requested session is removed without deleting the other one.',{'type':'listed-documents','action':'View','names':names})],prep=prep),
           goal('delete-reload','Delete the prepared Backup amber session, reload, then restore Backup azure.',
                'The remaining backup restores its artwork after deletion and reload.',None,
                browse+[X.dialog(response='accept'),X.ui('click',{'semantic':'Delete','scope':names[0]}),{'op':'reload'}]+browse+
                [X.ui('click',{'semantic':'View','scope':names[1]}),P.control(text='Load',exact=True)],
                [be('pixels','The surviving session restores its original pixels.',P.ALL)],prep=prep)]
    return episode('gui-backup-delete','persistence',goals)


def exports():
    goals=[]
    for cid,mode in [('data-uri','data URI'),('resolution','explicit resolution')]:
        recipe=[X.drawer('export')]
        if cid=='resolution':
            recipe += [X.ui('fill',{'editable':True,'dimension':['Resolution','width']},value='12'),*P.key('Tab')]
        recipe += [P.control(text='PNG',exact=True),X.field('Columns',2),*P.key('Tab'),
                   X.ui('click',{'semantic':'Open' if cid=='data-uri' else 'Download',
                                 'scope':'Spritesheet data-uri export' if cid=='data-uri' else 'Spritesheet file export'}),
                   {'op':'wait-download','suffix':'.png'}]
        goals.append(goal(cid,'Open the complete animation as a PNG spritesheet data URI with two columns at original resolution.' if cid=='data-uri' else
                          'Export the animation as a PNG spritesheet with two columns and per-frame resolution 12 by 12.',
                          'The requested spritesheet image is offered by the editor.',F.GRID,recipe,
                          [be('size','The exported resolution is correct.',X.dl('png',only=['size'])),
                           be('pixels','The image includes every frame in the requested layout.',X.dl('png',['grid'],only=['grid']))]))
    return episode('gui-export-resolution','export',goals)


def build():
    return [views(),components(),storage(),backups(),exports()]
