"""Additional user episodes for configuration, document navigation and selections."""
def extend(add):
    from specification import step,menu,key,tool,color,drag,text
    add('recovery','lifecycle',[
        step('draft','Add "Recovered draft" near the upper left and leave the notebook unsaved.',
             'Recovered draft is visible in the unsaved notebook.',[text('Recovered draft')],save=False),
        step('restore','The application has restarted after an interrupted session. Restore the offered recovery document.',
             'The restored notebook contains Recovered draft.',[{'op':'click','name':'Restore file','roles':['push button']}],
             aspects=['texts'],expect={'texts':['Recovered draft']},lifecycle='restart',depends=['draft'])])
    add('toolbar-layout','view',[
        step('minimal','Choose the Minimal Top toolbar layout.','A compact toolbar appears at the top and the document remains visible.',
             [menu('Edit','Toolbars','Minimal Top')],save=False),
        step('restore','Restore the Portrait toolbar layout.','The fuller toolbar arrangement is restored.',
             [menu('Edit','Toolbars','Portrait')],save=False,depends=['minimal'])],opened='objects.xopp')
    add('default-tool','drawing',[
        step('change','Choose a thick red highlighter and draw a short mark near the top.','A red highlight mark is visible.',
             [tool('Highlighter'),color('Red'),{'op':'click','name':'Thick','roles':['toggle button']},drag((90,90),(330,90))],aspects=['stroke-styles']),
        step('default','Switch back to the default tool and draw a separate mark below it.','A normal pen mark appears below the highlight.',
             [tool('Default Tool'),drag((90,210),(330,210))],aspects=['stroke-styles'],depends=['change'])])
    updated=add('append-pdf','pdf',[
        step('open','Open {inbox}/single.pdf for annotation.','The PDF opens with its single chapter page.',
             [{'op':'open','name':'single.pdf'}],aspects=['counts','backgrounds'],expect={'pages':1}),
        step('append','The backing PDF now contains three pages. Reopen the saved notebook {outbox}/open.xopp, then append the newly available PDF pages.',
             'The notebook now has three PDF pages, including the new chapter pages.',
             [{'op':'open','name':'open.xopp','area':'outbox'},menu('Journal','Append New PDF Pages'),menu('Navigation','Last Page')],
             aspects=['counts','backgrounds'],expect={'pages':3},depends=['open'])],opened=None,inputs=['single.pdf'])
    updated['setup'].append({'id':'updated-pdf','op':'upload','before':'append','files':[{'name':'single.pdf','fixture':'normal.pdf'}]})
    updated['checkpoints'][1]['depends_on'].append('setup:updated-pdf')
    add('paper-color','paper',[
        step('color','Set the page background color to #FFE0B0.','The paper has the requested pale orange color.',
             [{'op':'paper-color','value':'#FFE0B0'}],aspects=['backgrounds'],expect={'paper-colors':['#ffe0b0']}),
        step('white','Change the paper color back to white.','White paper is restored.',[{'op':'paper-color','value':'#FFFFFF'}],aspects=['backgrounds'],depends=['color'],expect={'paper-colors':['#ffffff']})])
    add('paper-custom','paper',[
        step('custom','Set the current paper size to exactly 500 by 300 points.','The page is a wide landscape rectangle.',
             [{'op':'custom-paper','width':500,'height':300}],aspects=['sizes'],expect={'sizes':[[500,300]]}),
        step('undo','Undo the size change.','The previous page size is restored.',[key('Control+Z')],aspects=['sizes'],depends=['custom'],expect={'sizes':[[600,400]]})])
    add('layer-visibility','layers',[
        step('hide','Hide the Upper notes layer while keeping Lower notes visible. Export the visible result to {outbox}/hidden.pdf.',
             'Lower layer is visible and Upper layer is hidden.',
             [{'op':'click','name':'Layer Preview','roles':['toggle button']},{'op':'check','name':'Upper notes','roles':['check box'],'value':False},
              {'op':'export','name':'hidden.pdf'}],save=False,aspects=['export-count','export-render'],artifact={'name':'hidden.pdf','kind':'export'}),
        step('show','Show the Upper notes layer again.','Both layer texts are visible.',
             [{'op':'check','name':'Upper notes','roles':['check box'],'value':True}],save=False,depends=['hide'])],opened='layers.xopp')
    for name,action,goal,visible in [
        ('resize',drag((255,285),(340,330)),'Enlarge the red rectangle by roughly half in both dimensions, keeping its upper left corner in place.','The red rectangle is visibly larger, and the text objects remain unchanged.'),
        ('rotate',drag((270,225),(160,335)),'Rotate the red rectangle by about a quarter turn around its center.','The red rectangle is now taller than it is wide; the text objects remain unchanged.')]:
        add('selection-'+name,'selection',[
            step(name,goal,visible,[tool('Select Rectangle'),drag((65,165),(255,285)),action,key('Escape')],aspects=['stroke-boxes','counts']),
            step('undo','Undo the transformation.','The original wide rectangle is restored.',[key('Control+Z')],aspects=['stroke-boxes'],depends=[name])],opened='objects.xopp')
    add('drawing-guides','drawing',[
        step('setsquare','Show the setsquare drawing guide on the page.','A setsquare guide is visible over the page.',[tool('Setsquare')],save=False),
        step('compass','Hide the setsquare and show the compass drawing guide.','A compass guide is visible over the page.',[tool('Setsquare'),tool('Compass')],save=False,depends=['setsquare'])])
    add('spline','shapes',[
        step('draw','Draw a blue curved spline with several control points across the middle of the page. Finish editing the spline.','A continuous curved blue spline is visible.',
             [tool('Draw Spline'),color('Blue'),drag((80,180),(120,110)),drag((260,150),(290,230)),drag((450,180),(470,100)),key('Escape')],aspects=['counts','stroke-styles']),
        step('undo','Undo the spline, then redo it.','The same spline is restored.',[key('Control+Z'),key('Control+Y')],aspects=['counts'],depends=['draw'])])
    add('shape-recognition','shapes',[
        step('recognize','Use shape recognition to draw a rough rectangular loop in blue in the center.','The recognized drawing appears as a rectangular outline.',
             [tool('Shape Recognizer'),color('Blue'),drag((130,100),(420,100),(420,280),(130,280),(130,100)),{'op':'wait','seconds':1}],aspects=['counts','stroke-styles']),
        step('undo','Undo the recognized rectangle, then redo it.','The recognized rectangle is restored.',[key('Control+Z'),key('Control+Y')],aspects=['counts'],depends=['recognize'])])
    add('pdf-search','search',[
        step('chapter','Find the text "Chapter 2" in the PDF.','The second chapter page is displayed and the matching text is indicated.',
             [{'op':'search','value':'Chapter 2'}],save=False),
        step('third','Replace the query with "Chapter 3" and find it.','The third chapter page is displayed with the matching text indicated.',
             [{'op':'search','value':'Chapter 3'}],save=False,depends=['chapter'])],opened='normal.pdf')
    add('pdf-copy-highlight','pdf',[
        step('copy','Go to the first page. Select its title line and copy the selected PDF text to the clipboard. Leave the title selected afterward (select it again if needed).','The title line of the first page is selected.',
             [menu('Navigation','First Page'),tool('Select Linear Text'),drag((30,50),(245,50)),{'op':'click','name':'Copy selected text','roles':['push button']},drag((30,50),(245,50))],
             save=False,aspects=['clipboard-text'],artifact={'kind':'clipboard'}),
        step('highlight','Highlight the first page title in yellow using PDF text selection, with marker opacity set to 50%.','The title has a visible yellow highlight while remaining readable.',
             [key('Escape'),tool('Select Linear Text'),color('Yellow'),{'op':'pdf-opacity','value':50},drag((30,50),(245,50)),{'op':'click','name':'Highlight selected text','roles':['push button']}],
             aspects=['counts','stroke-styles'],depends=['copy'],expect={'marker':{'color':'#ffff00','fill':127}})],opened='normal.pdf')
    add('pdf-underline-strike','pdf',[
        step('underline','Underline the title on the first PDF page using text selection.','The first page title is visibly underlined.',
             [menu('Navigation','First Page'),tool('Select Linear Text'),drag((30,50),(245,50)),{'op':'click','name':'Underline selected text','roles':['push button']}],aspects=['stroke-styles','counts']),
        step('strike','Use text selection to strike through the sentence beginning Review this sentence.','The review sentence has a strike-through mark.',
             [tool('Select Linear Text'),drag((30,96),(245,96)),{'op':'click','name':'Strikethrough selected text','roles':['push button']}],aspects=['stroke-styles'],depends=['underline'])],opened='normal.pdf')
    add('preferences-persist','preferences',[
        step('set','Turn off automatic saving and set the proposed default save name to "Notebook". Apply the settings and show them again.',
             'The settings show automatic saving off and Notebook as the proposed save name.',
             [menu('Edit','Preferences'),{'op':'check','name':'Enable Autosaving','roles':['check box'],'value':False},
              {'op':'entry','value':'Notebook'},{'op':'click','name':'Ok','roles':['push button']},menu('Edit','Preferences')],save=False),
        step('persist','The application has restarted. Dismiss any recovery prompt and display the load/save preferences.',
             'Automatic saving remains off and the proposed save name remains Notebook.',
             [{'op':'dismiss-recovery'},menu('Edit','Preferences')],save=False,lifecycle='restart',depends=['set'])])
    add('sidebar-view','view',[
        step('hide','Hide the sidebar to give the document more screen space.','The sidebar is hidden and the document remains available.',[menu('View','Show Sidebar')],save=False),
        step('show','Show the sidebar again.','Page previews are visible beside the document again.',[menu('View','Show Sidebar')],save=False,depends=['hide'])],opened='pages.xopp')
    add('page-reorder','pages',[
        step('down','Move Page 1 down so that it comes after Page 2.','The order is Page 2, Page 1, Page 3.',[{'op':'page-move','direction':'down'}],aspects=['texts','backgrounds']),
        step('undo','Undo the page move.','The original order Page 1, Page 2, Page 3 is restored.',[key('Control+Z')],aspects=['texts'],depends=['down'])],opened='pages.xopp')
    add('page-view-modes','view',[
        step('paired','Display pages 2 and 3 side by side at a zoom where both are visible.','Two pages are arranged side by side.',
             [menu('View','Pair Pages'),*[menu('View','Zoom Out') for _ in range(5)],menu('Navigation','Next Page')],save=False),
        step('presentation','Turn off paired pages and enter presentation mode.','One page is shown for presentation.',[menu('View','Pair Pages'),menu('View','Presentation Mode')],save=False,depends=['paired'])],opened='pages.xopp')
    add('unsaved-cancel','lifecycle',[
        step('prompt','Add "Unsaved draft", then request a new notebook. Leave the application response visible.',
             'The application offers to save the unsaved draft before replacing it.',[text('Unsaved draft'),key('Control+N')],save=False),
        step('cancel','Cancel creating the new notebook and keep the draft.','Unsaved draft remains on the current page.',
             [{'op':'click','name':'Cancel','roles':['push button']}],aspects=['texts'],depends=['prompt'])])
    add('layer-transfer','layers',[
        step('down','Select the Upper layer text and move that selection to the layer below.',
             'Both text objects remain visible and the selection now belongs to Lower notes.',
             [tool('Select Rectangle'),drag((260,220),(520,290)),menu('Edit','Move Selection Layer Down'),key('Escape'),{'op':'click','name':'Layer Preview','roles':['toggle button']}],aspects=['texts']),
        step('return','Move the Upper layer text back to the Upper notes layer.','The two text objects are back on their original layers.',
             [tool('Select Rectangle'),drag((260,220),(520,290)),menu('Edit','Move Selection Layer Up'),key('Escape')],aspects=['texts'],depends=['down'])],opened='layers.xopp')
    add('page-template','paper',[
        step('template','Configure new pages to copy the current page size. Add a page after the current page and write "Same size" on it.',
             'The new page has the same landscape proportions and displays Same size.',
             [menu('Journal','Configure Page Template'),{'op':'check','name':'Copy current page size instead','roles':['check box'],'value':True},
              {'op':'click','name':'Ok','roles':['push button']},menu('Journal','New Page After'),{'op':'page-width','value':600},text('Same size')],aspects=['sizes','texts']),
        step('next','Add another new page after this one and write "Template again".','A third page has the same landscape proportions and displays Template again.',
             [menu('Journal','New Page After'),{'op':'page-width','value':600},text('Template again')],aspects=['sizes','texts'],depends=['template'])])
