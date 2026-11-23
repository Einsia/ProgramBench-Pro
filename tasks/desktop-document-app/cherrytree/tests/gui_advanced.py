"""Local editing features: each goal has a visible result and public persisted evidence."""
from specification import action as A,key as K,menu as M,node as N,select as S,typed as T,saved as D,step as C,episode as W,outbox,inbox


def build():
    result=[];save=A('save');button=lambda n:A('button',name=n);field=lambda v,**kw:A('field',value=v,**kw)
    click=lambda role,name:A('click',role=role,name=name)
    def add(k,feature,steps,**kw):result.append(W(k,feature,steps,**kw))
    def filecheck(path,kind,aspect,description):return {'kind':'file','path':path,'content':kind,'aspect':aspect,'description':description}
    def tablecell(text):return A('control',role='text',text=text)
    # Images and attachments have asymmetric pixel/byte content.
    k='image-transform'
    add(k,'image-editing',[
        C('rotate','Rotate the Image node picture 90 degrees clockwise and save.',
          'The rectangular image is now taller than wide, with the former lower-left blue corner at the upper left.',
          [A('image-edit',turn='Right'),save],D(('content:Image',))),
        C('scale','Resize the Image node picture to width 80 pixels, preserving its proportions, and save.',
          'The image is visibly smaller with the same four colored quadrants.',
          [A('image-edit',width=80),save],D(('content:Image',))),
        C('flip','Flip the Image node picture horizontally and save.',
          'The top-left quadrant is green and the top-right quadrant is red.',
          [A('image-edit',flip='Horizontally'),save],D(('content:Image',))),
        C('export',f'Save the Image picture to {outbox(k)}/picture.png and show that output in the attachment chooser.',
          'picture.png is present in the output folder.',
          [A('object-menu',node='Image',command='Save Image as PNG...'),A('file',path='outputs/picture.png',save=True),A('browse',path='outputs',node='Image')],
          [filecheck('picture.png','png','all','The saved PNG has the original dimensions and decoded colored pixels.')]),
    ],document='advanced')
    k='attachment-save'
    add(k,'embedded-files',[
        C('save',f'Save the embedded plan.txt in Attachment to {outbox(k)}/extracted.txt, then show it in the attachment chooser.',
          'extracted.txt is visible in the output folder.',
          [A('object-menu',node='Attachment',command='Save As...'),A('file',path='outputs/extracted.txt',save=True),A('browse',path='outputs',node='Attachment')],
          [filecheck('extracted.txt','binary','all','The extracted attachment is byte-identical to the embedded original.')]),
    ],document='advanced')
    k='table-columns'
    add(k,'table-editing',[
        C('move','In Table move the Count column to the left of Item and save.',
          'The column order is Count, Item, Note; values follow their columns.',
          [N('Table'),tablecell('Count'),M('Edit','Table','Move Column Left'),save],D(('content:Table',))),
        C('add','In Table add an empty column immediately after Count and save.',
          'A blank column separates Count and Note.',
          [N('Table'),tablecell('Count'),M('Edit','Table','Add Column'),save],D(('content:Table',))),
        C('delete','In Table delete the Note column and save.',
          'Only Item and Count remain with all three data rows.',
          [N('Table'),tablecell('Note'),M('Edit','Table','Delete Column'),A('confirm',name='Yes'),save],D(('content:Table',))),
    ],document='advanced')
    k='table-properties'
    add(k,'table-editing',[
        C('properties','Change Table to the lightweight interface with default column width 90 pixels. Save and reopen its table properties.',
          'The table properties show Lightweight Interface enabled and default width 90.',
          [A('last-object',node='Table'),M('Edit','Table','Edit Table Properties...'),field(90,role='spin button'),A('check',name='Lightweight Interface (much faster for large tables)'),button('OK'),A('confirm',name='Yes'),save,
           A('last-object',node='Table'),M('Edit','Table','Edit Table Properties...')],D(('content:Table',))),
    ],document='advanced')
    k='table-rows'
    add(k,'table-editing',[
        C('sort','Sort Table data rows by Item ascending, retaining the header, then save.',
          'Data rows are Apple, Mango, Zebra beneath the header.',
          [N('Table'),tablecell('Zebra'),M('Edit','Table','Sort Rows Ascending'),save],D(('content:Table',))),
        C('copy','Copy the entire Apple row and paste a copy immediately after Mango. Save.',
          'The table contains a second Apple row after Mango, with the same Count and Note.',
          [N('Table'),tablecell('Apple'),M('Edit','Table','Copy Row'),tablecell('Mango'),M('Edit','Table','Paste Row'),save],D(('content:Table',))),
        C('cut','Move the entire Zebra row after Mango using row cut and paste. Save.',
          'Data rows are Apple, Mango, Zebra, with exactly one Zebra row.',
          [N('Table'),tablecell('Zebra'),M('Edit','Table','Cut Row'),tablecell('Mango'),M('Edit','Table','Paste Row'),save],D(('content:Table',))),
        C('up','Move the Mango row above Apple and save.',
          'The row order is Zebra, Mango, Apple below the header.',
          [N('Table'),tablecell('Mango'),M('Edit','Table','Move Row Up'),save],D(('content:Table',))),
    ],document='advanced')
    k='codebox-files'
    add(k,'codeboxes',[
        C('load',f'Load {inbox(k)}/new-code.txt into the existing Code node code box, replacing its text. Save.',
          'The code box contains the new greeting function and its call.',
          [A('last-object',node='Code'),M('Edit','CodeBox','CodeBox Load From Text File...'),A('file',path='inputs/new-code.txt'),save],D(('content:Code',))),
        C('export',f'Save the Code code box text to {outbox(k)}/code.txt and show the output in the attachment chooser.',
          'code.txt is visible in the output folder.',
          [A('last-object',node='Code'),M('Edit','CodeBox','CodeBox Save To Text File...'),A('file',path='outputs/code.txt',save=True),A('browse',path='outputs',node='Code')],
          [filecheck('code.txt','text','text','The exported text is the loaded multi-line program.')],depends=('load',)),
        C('properties','Change the Code code box syntax to python3, width 320 pixels, height 160 pixels, and show line numbers. Save and leave its properties open.',
          'Code box properties show python3, the requested dimensions and enabled line numbers.',
          [A('last-object',node='Code'),M('Edit','CodeBox','Change CodeBox Properties...'),A('language',name='python3'),field(320,role='spin button'),field(160,index=1,role='spin button'),A('check',name='Show Line Numbers'),button('OK'),save,
           A('last-object',node='Code'),M('Edit','CodeBox','Change CodeBox Properties...')],D(('content:Code',))),
    ],document='advanced',inputs=[{'text':'def greet(name):\n    return "Hello " + name\n\nprint(greet("Ada"))\n','as':'new-code.txt'}])
    k='rich-object-clipboard'
    add(k,'rich-clipboard',[
        C('copy','Copy all content of Rich with ordinary rich-text Copy, then paste it after the initial line of Destination and save.',
          'Destination shows the styled title, link, colored image, code box and table after its initial line.',
          [A('select',node='Rich'),K('Control+A'),K('Control+C'),A('end',node='Destination'),K('Control+V'),save],
          D(('content:Destination',),ignore_terminal_newlines=True)+D(('content:Rich',))),
        C('cut','Cut all of Rich with ordinary Cut, paste into Destination after its initial line, and save.',
          'Destination displays the cut styled text and all three embedded objects after its initial line.',
          [A('select',node='Rich'),K('Control+A'),K('Control+X'),A('end',node='Destination'),K('Control+V'),save],
          D(('content:Destination',),ignore_terminal_newlines=True)+D(('content:Rich',))),
    ],document='advanced')
    k='text-cleanup'
    add(k,'text-tools',[
        C('strip','Strip trailing spaces from Cleanup and save.',
          'Cleanup retains its two text lines after trailing whitespace is removed.',
          [N('Cleanup'),M('Tools','Strip Trailing Spaces'),A('dismiss'),save],D(('text:Cleanup',)),requires={'visible-1':['strip/text:Cleanup']}),
        C('tabs','Replace all tabs with spaces in Cleanup and save.',
          'The indentation and gap between beta and gamma are represented by spaces.',
          [N('Cleanup'),M('Tools','Replace Tabs with Spaces'),A('dismiss'),save],D(('text:Cleanup',)),requires={'visible-1':['tabs/text:Cleanup']}),
    ],document='advanced')
    k='tree-reparent-paste'
    add(k,'node-tree',[
        C('parent','Move Garden from Projects to be a child of Archive and save.',
          'Garden is under Archive while Kitchen remains under Projects.',
          [N('Garden'),A('reparent',parent='Archive'),M('Tree','Expand All Nodes'),save],D(('tree','node:Archive/Garden'))),
        C('paste','Copy Projects and its subnodes, then paste the copied branch immediately after Archive at root level. Save.',
          'A second Projects branch follows Archive at root level, with Garden and Kitchen; the original Projects remains.',
          [N('Projects'),M('Tree','Copy Node and Subnodes'),N('Archive'),M('Tree','Paste Node and Subnodes'),M('Tree','Expand All Nodes'),save],D(('tree',))),
        C('siblings','Sort only the children of Projects descending by name and save.',
          'Kitchen precedes Garden under Projects; root node order remains Inbox, Projects, Archive, Script.',
          [N('Garden'),M('Tree','Nodes Sort','Sort Siblings Descending'),save],D(('tree',))),
    ])
    k='readonly-effects'
    add(k,'node-properties',[
        C('lock','Make Inbox read-only, then attempt to append "SHOULD NOT APPEAR" using the editor. Dismiss any read-only notice and save.',
          'Inbox is visibly locked and retains its original reminders.',
          [N('Inbox'),M('Tree','Toggle Read Only'),A('end'),T('SHOULD NOT APPEAR'),A('dismiss'),save],D(('content:Inbox','props:Inbox')),requires={'visible-1':['unlock/content:Inbox']}),
        C('unlock','Unlock Inbox and append "Writable again." at its end, then save.',
          'The appended Writable again. sentence is visible in Inbox.',
          [N('Inbox'),M('Tree','Toggle Read Only'),A('end'),T('Writable again.'),save],D(('content:Inbox','props:Inbox')),depends=('lock',)),
    ])
    k='search-multiple'
    add(k,'search',[
        C('whole','Across all node contents, replace the case-sensitive whole word "cat" with "fox", respecting exclusions. Save.',
          'Alpha shows fox catapult CAT, preserving the different-case and partial-word text.',
          [A('find',text='cat',replacement='fox',multiple=True,options=[['Match Case',True],['Whole Word',True],['Node Name and Tags',False],['Override Exclusions',False]]),A('dismiss'),save,N('Alpha')],
          D(('text:Alpha','text:Alpha/Child','text:Excluded','text:Excluded/Nested','text:Other'))),
        C('subtree','Select Alpha and replace the whole word "cat" with "pet" only in Alpha and its children, case sensitively. Save.',
          'Alpha shows pet catapult CAT after the subtree replacement.',
          [N('Alpha'),A('find',text='cat',replacement='pet',multiple=True,options=[['Match Case',True],['Whole Word',True],['Node Name and Tags',False],['Only Selected Node and Subnodes',True]]),A('dismiss'),save,N('Alpha')],
          D(('text:Alpha','text:Alpha/Child','text:Excluded','text:Other'))),
        C('override','Across all node contents, replace case-sensitive whole-word cat with dog, overriding search exclusions. Save.',
          'Excluded now reads dog secret.',
          [A('find',text='cat',replacement='dog',multiple=True,options=[['Match Case',True],['Whole Word',True],['Node Name and Tags',False],['Only Selected Node and Subnodes',False],['Override Exclusions',True]]),A('dismiss'),save,N('Excluded')],
          D(('text:Alpha','text:Alpha/Child','text:Excluded','text:Excluded/Nested','text:Other'))),
    ],document='search-tree')
    return result
