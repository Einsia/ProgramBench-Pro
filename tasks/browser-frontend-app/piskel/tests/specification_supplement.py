from specification import goal,episode,be
import program as P
import program_extra as X
import program_episodes as W
import fixtures as F


def remap():
 return [P.control(title='Keyboard shortcuts',exact=True),P.control(text='Pen tool',exact=True),*P.key('q'),*P.key('Escape'),P.settle(.6)]


def build():
 out=[]
 cases=[
  goal('remap','Change the Pen tool shortcut to Q, then use Q to draw a mark at pixel (3, 3).',
       'The custom shortcut activates the pen and a mark appears.',F.BLANK,
       remap()+[P.tool('eraser'),*P.key('q'),P.tap(3,3)],
       [be('paint','Remapped shortcut paints.',{'type':'pixel','x':3,'y':3})]),
  goal('persist','The Pen tool has been remapped to Q. Reload the page, then use Q to paint pixel (3, 3).',
       'The customized shortcut remains usable after reload.',F.BLANK,
       [{'op':'reload'},P.tool('eraser'),*P.key('q'),P.tap(3,3)],
       [be('paint','Persistent shortcut paints.',{'type':'pixel','x':3,'y':3})],prep=remap()),
  goal('restore','The Pen tool has been remapped to Q. Restore the default keyboard shortcuts, then use P to paint pixel (3, 3).',
       'Restoring the defaults makes the original pen shortcut usable.',F.BLANK,
       [P.control(title='Keyboard shortcuts',exact=True),X.ui('click',{'text':'Restore default shortcuts'}),*P.key('Escape'),
        P.tool('eraser'),*P.key('p'),P.tap(3,3)],
       [be('paint','Restored pen shortcut paints.',{'type':'pixel','x':3,'y':3})],prep=remap()),
 ]
 out.append(episode('gui-shortcut-settings','preferences',cases))
 paletteprep=W.palette_import('colors.gpl')
 cases=[
  goal('edit-color','Edit the first color of Imported colors to #6622aa, save the palette, then use its first color to paint pixel (3, 3).',
       'The palette color is changed and can paint.',F.BLANK,
       [P.control(title='Manage this palette'),X.ui('fill',{'editable':True,'value_pattern':r'#[0-9a-fA-F]{3,8}'},value='#6622aa'),*P.key('Tab'),P.control(text='Save',exact=True),
        *P.key('1'),P.tool('pen'),P.tap(3,3)], [be('paint','Edited color is used.',P.pix())],prep=paletteprep),
  goal('add-color','Add #6622aa as a fifth color of Imported colors, save, then paint pixel (3, 3) with the fifth color.',
       'A new palette color is available and can paint.',F.BLANK,
       [P.control(title='Manage this palette'),X.ui('click',{'text':'+','scope':'Edit Palette'}),
        X.ui('fill',{'editable':True,'value_pattern':r'#[0-9a-fA-F]{3,8}'},value='#6622aa'),*P.key('Tab'),P.control(text='Save',exact=True),
        *P.key('5'),P.tool('pen'),P.tap(3,3)], [be('paint','Added color is used.',P.pix())],prep=paletteprep),
  goal('remove-color','Remove the first color from Imported colors, save, then paint pixel (3, 3) with the new first color.',
       'A palette color is removed and the remaining colors are usable.',F.BLANK,
       [P.control(title='Manage this palette'),X.ui('pointer',{'tag':'li','text':'X','nth':0},rx=.88,ry=.12),P.control(text='Save',exact=True),
        *P.key('1'),P.tool('pen'),P.tap(3,3)], [be('paint','Next palette color moves to first.',P.pix())],prep=paletteprep),
 ]
 out.append(episode('gui-palette-colors','colours',cases,['colors.gpl']))
 saved=[X.drawer('save'),X.field('Title :','Stored animation'),P.control(text='Save in Browser',exact=True),P.settle(.5)]
 cases=[goal('overwrite','The browser already contains Stored animation. Paint pixel (3, 3), overwrite that browser save, reload, then reopen it.',
   'The reopened browser save contains the new mark.',F.ARROW,
   [X.drawer('save'),P.tool('pen'),P.tap(3,3),X.drawer('save'),P.control(text='Save in Browser',exact=True),P.settle(.5),{'op':'reload'},
    X.drawer('import'),P.control(text='Browse local saves',exact=True),P.control(text='Load',exact=True)],
   [be('pixels','Overwritten save contains the edited sprite.',P.pix())],prep=saved)]
 out.append(episode('gui-storage-more','persistence',cases))
 return out
