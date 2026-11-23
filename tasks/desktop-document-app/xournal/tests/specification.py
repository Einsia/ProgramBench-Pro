"""User goals and functional acceptance; recipes are private recording instructions."""
import program
import copy

from evaluation.contract import files_path
HINTS=('Use any equivalent visible commands. Inspect the whole page at a convenient zoom before drawing. '
       'Click a newly inserted page to activate it before entering text. '
       'Approximate drawing placement and shape are sufficient unless the goal supplies exact text or settings. '
       'Finish text editing before changing tools or saving. Keep each requested drawing distinct. '
       'When saving, replace the entire suggested filename with the full path given. '
       'Do not reopen saved files unless a goal asks for it. Files are checked separately. '
       'Wait for the canvas to redraw before repeating an action. Goals build on earlier state only where stated.')


def menu(*p):return {'op':'menu','path':list(p)}
def key(k):return {'op':'key','key':k}
def tool(n):return {'op':'tool','name':n}
def color(n):return {'op':'color','name':n}
def drag(*p):return {'op':'drag','points':[list(point) for point in p]}
def text(value,x=85,y=80):return {'op':'text','value':value,'x':x,'y':y}


def step(cid, goal, visible, actions, *, aspects=(), expect=None, save=True, depends=(), lifecycle=None, artifact=None):
    return dict(id=cid,goal=goal,acceptance=[visible] if isinstance(visible,str) else visible,recipe=actions,
                aspects=list(aspects),expect=expect or {},save=save,depends_on=list(depends),lifecycle=lifecycle,artifact=artifact)


def gui():
    result=[]
    def add(name,feature,steps,opened='blank.xopp',inputs=(),normal=True):
        wid='gui-'+name
        inbox=files_path('inbox', instance=False);outbox=files_path('outbox', instance=False)
        files=sorted(set(([opened] if opened else [])+list(inputs)))
        saved_names={original['id']+'.xopp':f'document-{index}.xopp'
                     for index,original in enumerate(steps,1) if original['save']}
        cps=[]
        for output_number, original in enumerate(steps, 1):
            cp=copy.deepcopy(original)
            for old,new in saved_names.items():
                cp['goal']=cp['goal'].replace('{outbox}/'+old,'{outbox}/'+new)
            for action in cp['recipe']:
                if action.get('area')=='outbox' or action.get('op')=='recent':
                    action['name']=saved_names.get(action.get('name'),action.get('name'))
            cp['goal']=cp['goal'].replace('{inbox}',inbox).replace('{outbox}',outbox)
            cp['depends_on']=['setup:inputs']+cp['depends_on'] if files else cp['depends_on']
            if cp.pop('save'):
                filename=f'document-{output_number}.xopp'
                cp['goal']+=f' Save the notebook as {outbox}/{filename}.'
                cp['recipe'].append({'op':'save','name':filename})
                cp['artifact']={'name':filename,'kind':'native'}
            cp['assertions']=[{'id':f'{wid}/{cp["id"]}/visible-{i+1}','channel':'frontend','method':'agent','requirement':s}
                              for i,s in enumerate(cp.pop('acceptance'))]
            for aspect in cp.pop('aspects'):
                cp['assertions'].append({'id':f'{wid}/{cp["id"]}/{aspect}','channel':'backend','method':'program',
                                         'requirement':f'The saved output preserves the requested {aspect}.','aspect':aspect})
            if cp['lifecycle'] is None:cp.pop('lifecycle')
            cps.append(cp)
        result.append({'id':wid,'feature':feature,'execution':'gui','opened':opened,'normal':normal,
                       'initial_state':'Fresh application and data directory; the listed files are in the inbox.',
                       'setup':[{'id':'inputs','op':'upload','files':files}] if files else [],
                       'inputs':{'input_folder':inbox,'output_folder':outbox,'files':files},
                       'session':('Unscored preparation: open '+inbox+'/'+opened+' as the current notebook. ' if opened else 'The application has just started. ')+HINTS,
                       'allowed_equivalents':['Menus, toolbars, keyboard shortcuts and equivalent visible controls may be used.','Drawing coordinates and zoom may differ while the requested content and relationships remain visible.'],
                       'forbidden_bypasses':['Do not use a terminal, other applications or private state.','Do not replace a requested editing command with reconstructing the entire document.'],
                       'budget':{'calls':400,'tokens':max(4_000_000,1_000_000+1_000_000*len(cps)),'seconds':max(1800,900+450*len(cps))},
                       'checkpoints':cps})
        return result[-1]
    # Drawing and tools.
    add('pen-widths','drawing',[
        step('blue','Draw a medium blue freehand rising line in the upper half of the blank page.','A blue freehand line is visible in the upper half.',
             [tool('Pen'),color('Blue'),drag((90,140),(220,80),(330,140))],aspects=['stroke-styles','counts'],expect={'strokes':1}),
        step('red','Add a thick red freehand line in the middle, below the blue line.','Both lines are visible; the new red line is below the blue line.',
             [color('Red'),{'op':'click','name':'Thick','roles':['toggle button']},drag((90,210),(330,210))],aspects=['stroke-styles'],depends=['blue'],expect={'strokes':2}),
        step('green','Add a fine green line near the bottom.','Three separate colored lines are visible, including a green lower line.',
             [color('Green'),{'op':'click','name':'Fine','roles':['toggle button']},drag((90,300),(330,300))],aspects=['stroke-styles'],depends=['red'],expect={'strokes':3})])
    add('line-styles','drawing',[
        step('dash','Draw a red dashed straight horizontal line in the upper half.','A red horizontal line is visible in the upper half.',
             [tool('Draw Line'),color('Red'),menu('Tools','Pen Options','dashed'),drag((80,100),(450,100))],aspects=['stroke-styles']),
        step('dots','Add a blue dotted horizontal line below it.','A separate blue horizontal line appears below the red line.',
             [color('Blue'),menu('Tools','Pen Options','dotted'),drag((80,200),(450,200))],aspects=['stroke-styles'],depends=['dash']),
        step('dashdot','Add a green dash-dot horizontal line below both.','Three separate horizontal lines appear in red, blue and green order from top to bottom.',
             [color('Green'),menu('Tools','Pen Options','dash-/ dotted'),drag((80,300),(450,300))],aspects=['stroke-styles'],depends=['dots'])])
    add('highlighter','drawing',[
        step('mark','Highlight the words Alpha note with a yellow highlighter stroke.','Alpha note remains readable under a yellow highlight.',
             [tool('Highlighter'),color('Yellow'),drag((85,90),(230,90))],aspects=['stroke-styles','texts'],expect={'strokes':2}),
        step('undo','Undo that highlighting.','Alpha note is visible again without the yellow highlight.',[key('Control+Z')],aspects=['counts'],depends=['mark'],expect={'strokes':1})],opened='objects.xopp')
    for slug,label in [('rectangle','Draw Rectangle'),('ellipse','Draw Ellipse'),('arrow','Draw Arrow'),('double-arrow','Draw Double Arrow'),
                       ('coordinates','Draw Coordinate System'),('line','Draw Line')]:
        shown={'rectangle':'a rectangular outline','ellipse':'an elliptical outline','arrow':'an arrow with one arrowhead',
               'double-arrow':'an arrow with arrowheads at both ends','coordinates':'a coordinate system with intersecting axes', 'line':'one straight line'}[slug]
        add('shape-'+slug,'shapes',[
            step('draw',f'Draw {shown} in blue in the central area of the page.',f'The page contains {shown} in blue.',
                 [tool(label),color('Blue'),drag((130,100),(420,280))],aspects=['stroke-styles','counts']),
            step('redo','Undo the drawing, then redo it.','The drawing is restored on the page.',[key('Control+Z'),key('Control+Y')],aspects=['counts'],depends=['draw'])])
    add('filled-shape','shapes',[
        step('fill','Draw a filled red rectangle in the center of the page.','A red rectangle has a visibly filled interior.',
             [tool('Draw Rectangle'),color('Red'),{'op':'click','name':'Fill','roles':['toggle button']},drag((130,100),(420,280))],aspects=['stroke-styles']),
        step('unfilled','Add a separate unfilled blue rectangle at the left side.','A blue outline with an empty interior appears alongside the filled red rectangle.',
             [{'op':'click','name':'Fill','roles':['toggle button']},color('Blue'),drag((30,120),(100,250))],aspects=['stroke-styles'],depends=['fill'])])
    for mode,description in [('standard','erase only a short middle segment'),('delete strokes','remove the entire stroke'),('whiteout','cover a short middle segment with white')]:
        slug=mode.replace(' ','-')
        add('eraser-'+slug,'eraser',[
            step('erase',f'Use the eraser mode that will {description} of the upper red line; touch its middle without affecting the blue or green lines.',
                 'The upper red line is erased as requested while the two lower lines remain visible.',
                 [tool('Eraser'),menu('Tools','Eraser Options',mode),drag((250,70),(250,110))],aspects=['counts','stroke-styles']),
            step('undo','Undo the erasing.','All three complete colored lines are visible again.',[key('Control+Z')],aspects=['counts'],depends=['erase'],expect={'strokes':3})],opened='strokes.xopp')
    # Text and embedded images.
    add('text-create','text',[
        step('write','Add the text "Notebook café — 東京" near the upper left.','The requested text appears as a text object.',
             [text('Notebook café — 東京')],aspects=['texts','text-styles'],expect={'texts':['Notebook café — 東京']}),
        step('lines','Add a separate text object below it with exactly these three lines:\n```\nFirst line\nSecond line\nThird line\n```',
             'The page shows the original text and a separate three-line text object.',[text('First line\nSecond line\nThird line',85,180)],
             aspects=['texts'],depends=['write'],expect={'texts':['Notebook café — 東京','First line\nSecond line\nThird line']})])
    add('text-edit','text',[
        step('replace','Edit the Alpha note text object so that it reads "Revised heading".','Revised heading replaces Alpha note; Beta note remains.',
             [tool('Text'),{'op':'canvas-click','x':130,'y':90},key('Control+A'),{'op':'type','value':'Revised heading'},key('Escape')],aspects=['texts']),
        step('undo','Undo the text edit.','Alpha note is restored, and Beta note remains.',[key('Control+Z')],aspects=['texts'],depends=['replace'])],opened='objects.xopp')
    add('text-font','text',[
        step('font','Add "Large serif heading" near the upper left in Serif Bold, size 28.','A large bold serif heading is visible.',
             [{'op':'font','name':'Serif Bold','size':28},text('Large serif heading')],aspects=['texts','text-styles']),
        step('mono','Add "Code 0123" below it in Monospace, size 18.','The page has a second text object in a monospaced font.',
             [{'op':'font','name':'Monospace','size':18},text('Code 0123',85,200)],aspects=['texts','text-styles'],depends=['font'])])
    add('image-insert','images',[
        step('insert','Insert {inbox}/picture.png into the upper half of the blank page.','The colored picture is visible on the page.',
             [{'op':'image','name':'picture.png'}],aspects=['images','counts'],expect={'images':1}),
        step('alpha','Insert {inbox}/alpha.png as a second image in the lower half.','Two images are visible, including the image with transparent areas.',
             [{'op':'image','name':'alpha.png','x':320,'y':240}],aspects=['images','counts'],depends=['insert'],expect={'images':2})],inputs=['picture.png','alpha.png'])
    # Selection, clipboard and history.
    add('selection-move','selection',[
        step('move','Select Alpha note and move it from the upper left to the upper right, keeping the other objects in place.',
             'Alpha note is now at the upper right; the rectangle and Beta note remain in place.',
             [tool('Select Rectangle'),drag((75,65),(235,115)),drag((150,90),(430,90)),key('Escape')],aspects=['texts','counts','text-regions']),
        step('undo','Undo the move.','Alpha note returns to the upper left.',[key('Control+Z')],aspects=['text-regions'],depends=['move'])],opened='objects.xopp')
    add('selection-color','selection',[
        step('color','Select the red rectangle and change its stroke color to blue.','The rectangle is now blue; both text objects remain.',
             [tool('Select Rectangle'),drag((65,165),(255,285)),color('Blue'),key('Escape')],aspects=['stroke-styles','texts']),
        step('undo','Undo the rectangle color change.','The rectangle is red again.',[key('Control+Z')],aspects=['stroke-styles'],depends=['color'])],opened='objects.xopp')
    for action in ['Copy','Cut']:
        slug=action.lower()
        add(slug+'-paste','clipboard',[
            step(slug,f'Select Alpha note and {slug} it. Keep the selection visible when copying.', 'Alpha note is selected while the other objects remain visible.' if action=='Copy' else 'Alpha note is removed while the other objects remain.',
                 [tool('Select Rectangle'),drag((75,65),(235,115)),key('Control+C' if action=='Copy' else 'Control+X')],
                 aspects=['texts'] if action=='Cut' else ['clipboard-text','clipboard-image'],save=action=='Cut',
                 artifact=None if action=='Cut' else {'kind':'clipboard','image':True}),
            step('paste','Paste the text object and move the pasted object into the upper right.','A pasted Alpha note is visible at the upper right.',
                 [key('Control+V'),drag((300,200),(430,90)),key('Escape')],aspects=['texts','counts','text-regions'],depends=[slug])],opened='objects.xopp')
    add('delete-history','history',[
        step('delete','Select all objects on the current layer and delete them.','The page is blank.',[tool('Select Rectangle'),key('Control+A'),key('Delete')],aspects=['counts'],expect={'texts':[],'strokes':0}),
        step('undo','Undo the deletion.','The two text objects and red rectangle are restored.',[key('Control+Z')],aspects=['texts','counts'],depends=['delete']),
        step('branch','Add "New branch" near the bottom while keeping the restored objects, then attempt Redo once.',
             'The original objects and New branch are visible together.',[text('New branch',300,330),key('Control+Y')],aspects=['texts'],depends=['undo'])],opened='objects.xopp')
    add('lasso','selection',[
        step('select','Use a freeform region selection around Alpha note and delete it without deleting the rectangle or Beta note.',
             'Alpha note is gone, while the rectangle and Beta note remain.',[tool('Select Region'),drag((65,60),(245,60),(245,125),(65,125),(65,60)),key('Delete')],aspects=['texts','counts']),
        step('undo','Undo the deletion.','All original objects are restored.',[key('Control+Z')],aspects=['texts'],depends=['select'])],opened='objects.xopp')
    add('vertical-space','selection',[
        step('space','Insert additional vertical space between the upper text and the lower objects, moving the lower objects down.',
             'The gap below Alpha note has increased and the lower objects have moved down.',
             [tool('Vertical Space'),drag((300,140),(300,200)),key('Escape')],aspects=['text-regions']),
        step('undo','Undo the vertical-space change.','The original spacing is restored.',[key('Control+Z')],aspects=['text-regions'],depends=['space'])],opened='objects.xopp')
    # Pages and stationery.
    add('page-insert','pages',[
        step('after','Insert a new page after the current first page, and write "Inserted" on the new page.','The notebook has four pages and the new page shows Inserted.',
             [menu('Journal','New Page After'),menu('Navigation','First Page'),menu('Navigation','Next Page'),text('Inserted')],aspects=['counts','texts'],expect={'pages':4,'texts':['Page 1','Inserted','Page 2','Page 3']}),
        step('before','Insert a new page before the current page, and write "Before" on it.','A fifth page has been added before Inserted and shows Before.',
             [menu('Journal','New Page Before'),menu('Navigation','First Page'),menu('Navigation','Next Page'),text('Before')],aspects=['texts','counts'],depends=['after'],expect={'pages':5,'texts':['Page 1','Before','Inserted','Page 2','Page 3']}),
        step('end','Add a new page at the end and write "Last" on it.','The sixth and final page shows Last.',
             [menu('Journal','New Page at End'),menu('Navigation','Last Page'),text('Last')],aspects=['texts','counts'],depends=['before'],expect={'pages':6,'texts':['Page 1','Before','Inserted','Page 2','Page 3','Last']})],opened='pages.xopp')
    add('page-duplicate','pages',[
        step('duplicate','Duplicate the current first page.','There are four pages, beginning with two copies of Page 1.',
             [menu('Journal','Duplicate Page')],aspects=['counts','texts','backgrounds'],expect={'pages':4}),
        step('undo','Undo the duplication.','The notebook has the original three pages again.',[key('Control+Z')],aspects=['counts','texts'],depends=['duplicate'],expect={'pages':3})],opened='pages.xopp')
    add('page-delete','pages',[
        step('delete','Delete the first page.','The notebook now begins with Page 2 and has two pages.',[menu('Journal','Delete Page')],aspects=['texts','counts'],expect={'pages':2}),
        step('undo','Undo the deletion.','Page 1 is restored before Page 2 and Page 3.',[key('Control+Z')],aspects=['texts','counts'],depends=['delete'],expect={'pages':3})],opened='pages.xopp')
    add('paper-format','paper',[
        step('a5','Change the current page paper format to A5 portrait.','The page has changed to portrait A5 proportions.',
             [{'op':'page-format','name':'A5'}],aspects=['sizes'],expect={'sizes':[[419.52756,595.27559]]}),
        step('letter','Change the current page to US Letter landscape.','The current page is now landscape US Letter.',
             [{'op':'page-format','name':'US Letter','landscape':True}],aspects=['sizes'],depends=['a5'],expect={'sizes':[[792,612]]}),
        step('undo','Undo the most recent paper-format change.','The previous A5 portrait format is restored.',[key('Control+Z')],aspects=['sizes'],depends=['letter'],expect={'sizes':[[419.52756,595.27559]]})])
    add('paper-backgrounds','paper',[
        step('graph','Change the page background to Graph.','The page shows a square grid.',[menu('Journal','Paper Background','Graph')],aspects=['backgrounds']),
        step('dots','Change the background to Dotted.','The page shows a regular pattern of dots.',[menu('Journal','Paper Background','Dotted')],aspects=['backgrounds'],depends=['graph']),
        step('music','Change the background to Staves.','The page shows musical staves.',[menu('Journal','Paper Background','Staves')],aspects=['backgrounds'],depends=['dots']),
        step('plain','Change the background back to Plain and add the word "Plain".','The page shows Plain on unruled paper.',[menu('Journal','Paper Background','Plain'),text('Plain')],aspects=['backgrounds','texts'],depends=['music'])])
    # Layers.
    add('layer-add','layers',[
        step('above','Add a layer above Upper notes, name it Comments, and write "Top comment" on it.',
             'A layer named Comments contains the new text above the existing content.',
             [menu('Journal','Add a Layer above the active layer'),{'op':'rename-layer','name':'Comments'},text('Top comment',80,170)],
             aspects=['layer-names','texts'],expect={'layers':3}),
        step('below','Add a layer below Comments, name it Middle, and write "Middle comment" on it.',
             'A layer named Middle appears below Comments and contains Middle comment.',
             [menu('Journal','Add a layer below the active layer'),{'op':'rename-layer','name':'Middle'},text('Middle comment',290,100)],
             aspects=['layer-names','texts'],depends=['above'],expect={'layers':4})],opened='layers.xopp')
    add('layer-rename-delete','layers',[
        step('rename','Rename the active Upper notes layer to "Review café".','The layer name is Review café and its content remains visible.',
             [{'op':'rename-layer','name':'Review café'}],aspects=['layer-names','texts']),
        step('delete','Delete the renamed layer.','The upper-layer text is gone and the lower-layer text remains.',[menu('Journal','Delete Layer')],aspects=['texts','layer-names'],depends=['rename']),
        step('undo','Undo the layer deletion.','The renamed layer and its text are restored.',[key('Control+Z')],aspects=['texts','layer-names'],depends=['delete'])],opened='layers.xopp')
    add('layer-merge','layers',[
        step('merge','Merge the active upper layer down into the lower layer.','Both text objects remain visible in a single layer.',
             [menu('Journal','Merge Layer Down')],aspects=['counts','texts'],expect={'layers':1}),
        step('undo','Undo the merge.','The two layers are restored with their original text objects.',[key('Control+Z')],aspects=['layer-names','texts'],depends=['merge'],expect={'layers':2})],opened='layers.xopp')
    add('multilayer-select','layers',[
        step('delete','Without manually changing the active Upper notes layer, use a selection that can find objects on other layers to select the lower-layer text near the upper left, then delete it.',
             'Lower layer is removed while Upper layer remains visible.',
             [tool('Select Multi-Layer Rectangle'),drag((60,65),(275,140)),key('Delete')],aspects=['texts','counts'],expect={'texts':['Upper layer']}),
        step('undo','Undo the deletion.','Both original text objects reappear on their layers.',[key('Control+Z')],aspects=['texts'],depends=['delete'])],opened='layers.xopp')
    # Imports and exports.
    add('open-rich','documents',[
        step('open','Open {inbox}/rich.xopp and go to its last page.','The notebook opens with 24 pages and its last page shows an embedded picture.',
             [{'op':'open','name':'rich.xopp'},menu('Navigation','Last Page')],aspects=['counts','texts','stroke-styles','images','backgrounds','sizes'],expect={'pages':24}),
        step('reopen','Open {outbox}/open.xopp again and go to the first page.','The saved notebook reopens and its first page shows the original stroke.',
             [{'op':'open','name':'open.xopp','area':'outbox'},menu('Navigation','First Page')],aspects=['counts','stroke-styles'],depends=['open'])],opened=None,inputs=['rich.xopp'])
    add('pdf-annotation','pdf',[
        step('open','Open {inbox}/normal.pdf for annotation.','The PDF opens with its three pages and the first chapter text visible.',
             [{'op':'open','name':'normal.pdf'}],aspects=['counts','backgrounds'],expect={'pages':3}),
        step('annotate','Add "Reviewed" near the upper right of the first PDF page.','Reviewed appears over the PDF page while its original content remains.',
             [text('Reviewed',210,110)],aspects=['texts','backgrounds'],depends=['open'])],opened=None,inputs=['normal.pdf'],normal=False)
    for fmt in ['PDF','PNG','SVG','XOJ']:
        name={'PDF':'export.pdf','PNG':'export.png','SVG':'export.svg','XOJ':'export.xoj'}[fmt]
        aspects=['export-count','export-geometry','export-render'] if fmt!='XOJ' else ['counts','texts','stroke-styles']
        preview=([{'op':'open','name':name,'area':'outbox'}] if fmt in ('PDF','XOJ') else
                 [key('Control+N'),{'op':'image','name':name,'area':'outbox'}])
        preview_goal=(f'Open {{outbox}}/{name} to inspect it.' if fmt in ('PDF','XOJ') else
                      f'Create a new notebook and insert {{outbox}}/{name} as an image so that its exported content is visible.')
        add('export-'+fmt.lower(),'export',[
            step('export',f'Export the current notebook as {fmt} to {{outbox}}/{name}. '+preview_goal,
                 'The exported content is displayed again with both text labels and the red rectangle.',[{'op':'export','name':name,'format':fmt},*preview],aspects=aspects,save=False,
                 artifact={'name':name,'kind':'native' if fmt=='XOJ' else 'export'}),
            step('edit','Add "After export" in unused space below the displayed exported content.','The original content and After export are visible together.',
                 [text('After export',290,330)],aspects=['texts'],depends=['export'])],opened='objects.xopp')
    # Navigation, view and lifecycle.
    add('navigation','navigation',[
        step('last','Go to the last page.','Page 3 is the current page.',[menu('Navigation','Last Page')],save=False),
        step('first','Go to the first page.','Page 1 is the current page.',[menu('Navigation','First Page')],save=False,depends=['last']),
        step('next','Go to the next page.','Page 2 is the current page.',[menu('Navigation','Next Page')],save=False,depends=['first'])],opened='pages.xopp')
    add('view-zoom','view',[
        step('zoom','Enlarge the view so the contents appear larger.','The content is displayed at a larger magnification.',[menu('View','Zoom In'),menu('View','Zoom In')],save=False),
        step('fullscreen','Enter fullscreen mode.','The application fills the screen without ordinary window decorations.',[menu('View','Fullscreen')],save=False,depends=['zoom']),
        step('restore','Leave fullscreen and fit the page to the available view.','The ordinary application window is restored and the page fits the view.',[key('F11'),menu('View','Zoom to Fit')],save=False,depends=['fullscreen'])],opened='objects.xopp')
    add('save-restart','lifecycle',[
        step('save','Add "Persistent notebook" near the upper left.','The requested text is visible.',[text('Persistent notebook')],aspects=['texts'],expect={'texts':['Persistent notebook']}),
        step('reopen','The application has restarted. Dismiss any recovery prompt without replacing the explicitly saved file, then open {outbox}/save.xopp.',
             'The saved notebook opens with Persistent notebook still present.',
             [{'op':'click','name':'Delete file','roles':['push button']},{'op':'open','name':'save.xopp','area':'outbox'}],
             aspects=['texts'],depends=['save'],lifecycle='restart')])
    add('open-error','errors',[
        step('error','Try to open {inbox}/broken.xopp and leave the application response visible.','The application reports that the file cannot be opened as a notebook.',
             [{'op':'open','name':'broken.xopp'}],save=False),
        step('recover','Dismiss the error and open {inbox}/objects.xopp.','The valid notebook opens with two text objects and a red rectangle.',
             [{'op':'click','name':'OK','roles':['push button']},{'op':'open','name':'objects.xopp'}],aspects=['texts','counts'],depends=['error'])],opened=None,inputs=['broken.xopp','objects.xopp'])
    from spec_extra import extend
    extend(add)
    from spec_revision import extend as extend_revision
    extend_revision(add)
    # History must expose the intermediate removed state to both channels.
    histories={'gui-shape-'+s for s in ('rectangle','ellipse','arrow','double-arrow','coordinates','line')}
    histories.update(('gui-spline','gui-shape-recognition'))
    for episode in result:
        if episode['id'] not in histories:continue
        first,combined=episode['checkpoints'];wid=episode['id']
        undo=copy.deepcopy(combined);redo=copy.deepcopy(combined)
        for cp,cid,command,goal,acceptance,dependency in (
                (undo,'undo','Control+Z','Undo the drawing so the page becomes blank.','The drawing has disappeared and the page is blank.',first['id']),
                (redo,'redo','Control+Y','Redo the drawing to restore it.','The original drawing is visible again.','undo')):
            filename='document-2.xopp' if cid=='undo' else 'document-3.xopp'
            output=files_path('outbox',filename,instance=False)
            cp.update(id=cid,goal=goal+f' Save as {output}.',
                      recipe=[*[key(command) for _ in range(2 if wid=='gui-shape-recognition' else 1)],{'op':'save','name':filename}],
                      artifact={'name':filename,'kind':'native'},depends_on=['setup:inputs',dependency],
                      expect={'strokes':0} if cid=='undo' else {})
            for a in cp['assertions']:
                suffix=a['id'].rsplit('/',1)[-1];a['id']=f'{wid}/{cid}/{suffix}'
                if a['channel']=='frontend':a['requirement']=acceptance
        episode['checkpoints']=[first,undo,redo]
        episode['budget']['seconds']=2250
    # Only constrain properties named by these goals. Erasing a short white
    # segment permits any suitable eraser width; upper right denotes a region.
    projections={
        'gui-eraser-whiteout/erase/stroke-styles':{'eraser_width_unspecified':True},
        'gui-cut-paste/paste/text-regions':{'upper_right_text':'Alpha note'},
        'gui-copy-paste/paste/text-regions':{'placement':'copy-right'},
        'gui-selection-move/move/text-regions':{'placement':'move-right'},
        'gui-selection-move/undo/text-regions':{'placement':'restored'},
        'gui-vertical-space/space/text-regions':{'placement':'space'},
        'gui-vertical-space/undo/text-regions':{'placement':'space-restored'},
    }
    for episode in result:
        for cp in episode['checkpoints']:
            for assertion in cp['assertions']:
                if assertion['id'] in projections:assertion['projection']=projections[assertion['id']]
                if assertion.get('aspect')=='stroke-styles':
                    if episode['id']=='gui-mouse-button-map':assertion['projection']={'fields':['tool']}
                    if episode['id']=='gui-palette-data':assertion['projection']={'fields':['tool','color']}
                    if episode['id']=='gui-shape-coordinates':assertion['projection']={'fields':['tool','color'],'unique':True}
                if episode['id']=='gui-shape-coordinates' and cp['id'] in ('draw','redo') and assertion.get('aspect')=='counts':
                    assertion['aspect']='coordinate-axes'
                    assertion['id']=assertion['id'].removesuffix('counts')+'coordinate-axes'
                    assertion['requirement']='The saved drawing contains two straight intersecting coordinate axes.'
                if episode['id'].startswith('gui-stack-') and assertion.get('aspect')=='export-render':
                    assertion['aspect']='export-overlap-colors'
                    assertion['id']=assertion['id'].removesuffix('export-render')+'export-overlap-colors'
                    assertion['projection']={'positions':[[200,180],[270,120],[265,220],[400,180]]}
                    assertion['requirement']='The exported overlapping regions reflect the requested object order.'
    return result


def build():
    return program.build()+gui()
