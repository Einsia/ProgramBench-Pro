"""Additional offline product episodes."""
def extend(add):
    from specification import step,menu,key,tool,color,drag,text
    def check(name,value):return {'op':'check','name':name,'roles':['toggle button'],'value':value}
    add('snapping-grid','snapping',[
        step('free','With grid snapping off, draw a rectangle with opposite corners roughly (112,116) and (395,281) points on this 600 by 400 point page.',
             'A rectangle appears while grid snapping is off.',[tool('Draw Rectangle'),check('Grid Snapping',False),drag((112,116),(395,281))],aspects=['grid-off','counts']),
        step('snapped','Undo that rectangle. Set the grid size to 1 cm and grid snapping tolerance to 1, turn grid snapping on, and draw the same rectangle near those corners.',
             'A rectangle appears with grid snapping enabled.',[key('Control+Z'),{'op':'pref','tab':'Drawing Area','scroll':600,'fields':{'Grid size':1.0,'Grid snapping tolerance':1.0}},check('Grid Snapping',True),drag((112,116),(395,281))],aspects=['grid-on','counts'],depends=['free'])])
    add('snapping-rotation','snapping',[
        step('free','With rotation snapping off, draw a straight line from roughly (80,100) to (480,110) points on the page.',
             'A long nearly horizontal line is visible with rotation snapping off.',[tool('Draw Line'),check('Rotation Snapping',False),drag((80,100),(480,110))],aspects=['rotation-off','counts']),
        step('snapped','Enable rotation snapping. Draw another line from roughly (80,250) toward (480,260), letting it snap to horizontal.',
             'Two separate lines are visible and rotation snapping is enabled.',[check('Rotation Snapping',True),drag((80,250),(480,260))],aspects=['rotation-on','counts'],depends=['free'])])
    zigzag=[[80+i*25,100+(20 if i%2 else -20)] for i in range(17)]
    add('input-stabilization','stabilization',[
        step('raw','Disable input stabilization (Averaging method None). Draw a continuous zigzag in the upper half, alternating between y=80 and y=120 every 25 points from x=80 through x=480.',
             'An angular zigzag stroke is visible.',[{'op':'pref','tab':'Input System','fields':{'Averaging method':'None'}},tool('Pen'),{'op':'drag','points':zigzag}],aspects=['counts']),
        step('smooth','Set input stabilization to Arithmetic mean, Buffersize 40. Repeat the same zigzag motion 150 points lower on the page.',
             'A second stroke appears below the first with visibly reduced jitter.',[{'op':'pref','tab':'Input System','fields':{'Averaging method':'Arithmetic mean','Buffersize':40}},{'op':'drag','points':[[x,y+150] for x,y in zigzag]}],aspects=['stabilized','counts'],depends=['raw'])])
    add('guides-drawing','drawing-guides',[
        step('ruler','Use the setsquare guide to draw a long straight horizontal pen line along its longest edge. Hide the guide afterward.',
             'A straight pen line remains after hiding the setsquare.',[{'op':'guide-draw','guide':'Setsquare'}],aspects=['ruler-line','counts']),
        step('arc','Use the compass guide to draw a circular arc of at least half a circle. Hide the guide afterward.',
             'A circular arc is visible alongside the earlier straight line.',[{'op':'guide-draw','guide':'Compass'}],aspects=['compass-arc','counts'],depends=['ruler'])])
    add('pdf-internal-navigation','pdf-navigation',[
        step('bookmark','Use the PDF contents/bookmarks to navigate to Detail Two under Section One.',
             'Destination 2 is displayed.',[{'op':'bookmark','parent':'Section One','name':'Detail Two'}],save=False),
        step('link','Go to the first page and follow its GO TO FOUR internal PDF link.',
             'Destination 4 is displayed after following the link.',[menu('Navigation','First Page'),{'op':'pdf-link','x':200,'y':220,'page':4}],save=False,depends=['bookmark'])],opened='nav.pdf')
    # Partially overlapping objects make every stacking change visible.
    for slug,command,target,point in [('front','Bring to Front','red',(70,110)),('forward','Bring Forward','red',(70,110)),
                                      ('backward','Send Backward','blue',(470,310)),('back','Send to Back','blue',(470,310))]:
        name=slug+'.pdf'
        colors={'front':['#cc3333','#cc3333','#cc3333','#2244cc'],'forward':['#cc3333','#2244cc','#2244cc','#2244cc'],
                'backward':['#228844','#2244cc','#228844','#228844'],'back':['#228844','#cc3333','#228844','#228844']}
        samples=[[200,180],[270,120],[265,220],[400,180]]
        add('stack-'+slug,'object-order',[
            step('arrange',f'Select the {target} rectangle and use {command}. Export the result to {{outbox}}/{name}.',
                 f'The overlap reflects the {target} rectangle being moved with {command}.',
                 [tool('Select Object'),{'op':'canvas-click','x':point[0],'y':point[1]},menu('Edit','Arrange Selection',command),key('Escape'),{'op':'export','name':name}],
                 save=False,aspects=['export-render'],artifact={'name':name,'kind':'export'},expect={'export-colors':{'positions':samples,'colors':colors[slug]}}),
            step('undo','Undo the stacking change and export to {outbox}/original.pdf.','The original overlapping order is restored.',
                 [key('Control+Z'),{'op':'export','name':'original.pdf'}],save=False,aspects=['export-render'],artifact={'name':'original.pdf','kind':'export'},depends=['arrange'],expect={'export-colors':{'positions':samples,'colors':['#228844','#2244cc','#2244cc','#2244cc']}})],opened='overlap.xopp')
    add('palette-data','palettes',[
        step('select','In the palette preferences select Orchard, supplied by {inbox}/custom.gpl. Draw one Forest-colored pen line across the upper half.',
             'A dark green line is visible and the Orchard palette colors are available.',
             [{'op':'palette','name':'Orchard'},tool('Pen'),color('Forest'),drag((90,120),(450,120))],aspects=['stroke-styles'],expect={'strokes':1}),
        step('persist','The application restarted. Dismiss any recovery prompt, open {outbox}/select.xopp, and add a Berry-colored line below the green line.',
             'The original green line and a new berry-colored line are visible, using the retained palette.',
             [{'op':'dismiss-recovery'},{'op':'open','name':'select.xopp','area':'outbox'},{'op':'normal'},tool('Pen'),color('Berry'),drag((90,240),(450,240))],aspects=['stroke-styles'],expect={'strokes':2},depends=['select'],lifecycle='restart')],inputs=['custom.gpl'])
    add('toolbar-custom','toolbar-customization',[
        step('custom','Copy the Portrait toolbar layout to a custom layout, then remove the Print button from that custom toolbar. Leave the edited toolbar in use.',
             'The custom toolbar is active, retains the editing tools and has no Print button.',
             [{'op':'toolbar-copy','source':'Portrait'},{'op':'toolbar-remove','tool':'Print'}],save=False),
        step('restart','The application restarted. Dismiss any recovery prompt and open {inbox}/blank.xopp. Using the customized toolbar, select Text and add "Custom tools" near the upper left.',
             'The custom toolbar remains usable after restart, with Print absent, and Custom tools appears on the page.',
             [{'op':'dismiss-recovery'},{'op':'open','name':'blank.xopp'},{'op':'normal'},text('Custom tools')],aspects=['texts'],expect={'texts':['Custom tools']},depends=['custom'],lifecycle='restart')])
    add('mouse-button-map','mouse-mapping',[
        step('mapped','Map the right mouse button to Highlighter in Mouse preferences. With Pen as the normal tool, use a right-button drag to draw a horizontal highlight in the upper half.',
             'The stroke made with the right button is a highlight, while the normal selected tool remains Pen.',
             [{'op':'mouse-map','tool':'Highlighter'},tool('Pen'),dict(drag((90,100),(450,100)),button='right')],aspects=['stroke-styles'],expect={'strokes':1}),
        step('normal','Use the normal left button to draw a second line below it.','The lower line is a normal pen stroke alongside the earlier highlighter stroke.',
             [drag((90,240),(450,240))],aspects=['stroke-styles'],expect={'strokes':2},depends=['mapped'])])
    add('layer-navigation','navigation',[
        step('previous','Move to the previous layer (Middle), and add "On middle" in unused space at the bottom.',
             'On middle is added to the Middle layer.',[menu('Navigation','Previous Layer'),text('On middle',80,330)],aspects=['texts']),
        step('next','Move to the next layer (Top), and add "On top" at the bottom.',
             'On top is added to the Top layer.',[menu('Navigation','Next Layer'),text('On top',300,330)],aspects=['texts'],depends=['previous']),
        step('top','Move to the previous layer twice, then use Top Layer and add "Top again" near the upper right.',
             'Top again belongs to the Top layer.',[menu('Navigation','Previous Layer'),menu('Navigation','Previous Layer'),menu('Navigation','Top Layer'),text('Top again',330,50)],aspects=['texts'],depends=['next'])],opened='layer-nav.xopp')
    add('annotated-navigation','navigation',[
        step('next','Go to the next annotated page.','Annotation 2 is displayed on page 2.',[menu('Navigation','Next Annotated Page')],save=False),
        step('again','Go to the next annotated page again.','Annotation 4 is displayed on page 4.',[menu('Navigation','Next Annotated Page')],save=False,depends=['next']),
        step('previous','Go to the previous annotated page.','Annotation 2 is displayed again.',[menu('Navigation','Previous Annotated Page')],save=False,depends=['again']),
        step('goto','Use Go to Page to go to page 3.','The unannotated red-tinted third page is current.',[{'op':'goto','page':3}],save=False,depends=['previous'])],opened='annotated.xopp')
    add('selection-alternatives','selection',[
        step('object','Use object selection to select and delete Alpha note without removing the rectangle or Beta note.',
             'Alpha note is gone while Beta note and the rectangle remain.',[tool('Select Object'),{'op':'canvas-click','x':140,'y':90},key('Delete')],aspects=['texts','counts'],expect={'texts':['Beta note'],'strokes':1}),
        step('restore','Undo the deletion.','Alpha note is restored.',[key('Control+Z')],aspects=['texts'],depends=['object'])],opened='objects.xopp')
    add('multilayer-lasso','layers',[
        step('lower','Without manually changing the active Upper notes layer, use multi-layer region selection to surround the lower-layer text at upper left, then delete it.',
             'Lower layer disappears while Upper layer remains.',[tool('Select Multi-Layer Region'),drag((60,65),(275,65),(275,140),(60,140),(60,65)),key('Delete')],aspects=['texts'],expect={'texts':['Upper layer']}),
        step('undo','Undo the deletion.','Both layer texts are restored.',[key('Control+Z')],aspects=['texts'],depends=['lower'])],opened='layers.xopp')
    add('pdf-rectangle-copy','pdf',[
        step('copy','Use rectangular PDF text selection to select the title on the first page, copy it, and select the title again so the selection remains visible.',
             'The first-page title is selected as a rectangular text region.',
             [tool('Select Text In Rectangle'),drag((25,32),(260,60)),{'op':'click','name':'Copy selected text','roles':['push button']},drag((25,32),(260,60))],
             save=False,aspects=['clipboard-text'],artifact={'kind':'clipboard'})],opened='normal.pdf')
    add('layout-directions','view-layout',[
        step('columns','Display the notebook in two columns. Reduce zoom until the page arrangement is visible.',
             'Pages occupy two columns.',[menu('View','Cols/Rows','Set Columns','2 Columns'),*[menu('View','Zoom Out') for _ in range(5)]],save=False),
        step('reverse','Reverse the horizontal order to right-to-left.','The ordering within the visible row reverses.',[menu('View','Layout','Right to Left')],save=False,depends=['columns']),
        step('rows','Choose a horizontal layout with one row, keeping several pages visible.','Pages are arranged in a single horizontal row.',[menu('View','Layout','Horizontal'),menu('View','Cols/Rows','Set Rows','1 Row'),*[menu('View','Zoom Out') for _ in range(2)]],save=False,depends=['reverse'])],opened='pages.xopp')
    add('template-file','page-templates',[
        step('save','Define a new-page template with size 500 by 300 points, Graph background and paper color #FFF4CC. Disable copying the current page size/background, save the template as {outbox}/stationery.xopt, add a page and write "Stationery one".',
             'The new landscape page has yellow grid paper and contains Stationery one.',
             [{'op':'template-save','name':'stationery.xopt'},menu('Journal','New Page After'),{'op':'page-width','value':500},text('Stationery one',50,60)],aspects=['sizes','backgrounds','texts'],expect={'sizes':[[500,300],[500,300]]}),
        step('load','Open {inbox}/blank.xopp, load {outbox}/stationery.xopt as the page template, and add a page after the blank page. Write "Loaded template" on it.',
             'The new page uses the loaded landscape yellow grid template and shows Loaded template.',
             [{'op':'open','name':'blank.xopp'},{'op':'template-load','name':'stationery.xopt'},menu('Journal','New Page After'),{'op':'page-width','value':500},text('Loaded template',50,60)],
             aspects=['sizes','backgrounds','texts'],depends=['save'],expect={'sizes':[[600,400],[500,300]],'paper-colors':['#ffffff','#fff4cc']}),
        step('persist','The application restarted. Dismiss any recovery prompt, open {inbox}/blank.xopp and add a page using the retained template. Write "Retained template" on the added page.',
             'The added page retains the landscape yellow grid template and contains Retained template.',
             [{'op':'dismiss-recovery'},{'op':'open','name':'blank.xopp'},menu('Journal','New Page After'),{'op':'page-width','value':500},text('Retained template',50,60)],
             aspects=['sizes','backgrounds','texts'],depends=['load'],lifecycle='restart',expect={'sizes':[[600,400],[500,300]],'paper-colors':['#ffffff','#fff4cc']})],opened='template-input.xopp',inputs=['blank.xopp'])
    add('discard-recent','lifecycle',[
        step('saved','Add "Kept note" and save the document.','Kept note is visible.',[text('Kept note')],aspects=['texts']),
        step('discard','Add "Throw away", request a new notebook, and discard the unsaved changes. Reopen the saved document from Recent Documents.',
             'The reopened saved notebook contains Kept note without Throw away.',[text('Throw away',100,220),{'op':'new-discard'},{'op':'recent','name':'saved.xopp'}],aspects=['texts'],depends=['saved'],expect={'texts':['Kept note']})])
    add('image-transparency','images',[
        step('insert','Insert {inbox}/alpha.png on the yellow graph paper.','The background grid remains visible through the transparent parts of the picture.',[{'op':'image','name':'alpha.png','x':160,'y':100}],aspects=['images','image-alpha','backgrounds']),
        step('reopen','Reopen {outbox}/insert.xopp.','The reopened picture retains transparent areas over the graph paper.',
             [{'op':'open','name':'insert.xopp','area':'outbox'}],aspects=['images','image-alpha'],depends=['insert'])],opened='graph.xopp',inputs=['alpha.png'])
    wf=add('overwrite','lifecycle',[
        step('refuse','Add "Replacement draft". Try saving over {outbox}/existing.xopp, refuse the replacement, and cancel the save dialog.',
             'Replacement draft remains in the editor after refusing the replacement.',
             [text('Replacement draft'),{'op':'overwrite','name':'existing.xopp','replace':False}],save=False,aspects=['texts'],artifact={'name':'existing.xopp','kind':'native'},expect={'texts':['Alpha note','Beta note']}),
        step('replace','Save over {outbox}/existing.xopp, this time confirm replacement, then reopen the file.',
             'The reopened file contains Replacement draft.',
             [{'op':'overwrite','name':'existing.xopp','replace':True},{'op':'open','area':'outbox','name':'existing.xopp'}],save=False,aspects=['texts'],artifact={'name':'existing.xopp','kind':'native'},expect={'texts':['Replacement draft']},depends=['refuse'])])
    wf['setup'].append({'id':'existing','op':'upload','area':'outbox','files':[{'name':'existing.xopp','fixture':'objects.xopp'}]})
    for cp in wf['checkpoints']:cp['depends_on'].append('setup:existing')
    wf=add('save-on-quit','lifecycle',[
        step('quit','Add "Saved on exit", then quit. When asked about the unsaved document, save it as {outbox}/quit.xopp.',
             'The application has exited and its editor window is no longer present.',
             [text('Saved on exit'),{'op':'save-quit','name':'quit.xopp'}],save=False,aspects=['texts'],
             artifact={'name':'quit.xopp','kind':'native'},expect={'texts':['Saved on exit']}),
        step('reopen','The application has restarted. Open {outbox}/quit.xopp.',
             'The document saved when quitting opens with Saved on exit.',
             [{'op':'dismiss-recovery'},{'op':'open','name':'quit.xopp','area':'outbox'},menu('Navigation','First Page'),menu('View','Zoom to Fit')],
             aspects=['texts'],expect={'texts':['Saved on exit']},depends=['quit'],lifecycle='restart')],opened=None)
    wf['checkpoints'][0]['assertions'][0]['requires']=['gui-save-on-quit/quit/texts']
