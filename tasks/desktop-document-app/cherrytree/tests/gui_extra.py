"""Storage, embedded objects, links, search, imports and application lifecycle goals."""
from specification import action as A, key as K, menu as M, node as N, select as S, typed as T, saved as D, step as C, episode as W, outbox, inbox
import fixtures


def build():
    result=[]
    def add(k,f,cps,**kw):result.append(W(k,f,cps,**kw))
    save=A('save')
    end=A('end')
    button=lambda name:A('button',name=name)
    field=lambda value,**kw:A('field',value=value,**kw)
    click=lambda role,name:A('click',role=role,name=name)
    add('text-colors','rich-text',[
        C('foreground','Color "Meeting notes" red (#e01b24) in Inbox and save.',
          'The heading is red while the remaining text retains its original color.',
          [S('Meeting notes'),A('color',value='#e01b24'),K('Right'),save],D()),
        C('background','Give "Buy milk and eggs." a yellow (#f9f06b) background and save.',
          'The shopping sentence has a yellow background distinct from the surrounding text.',
          [S('Buy milk and eggs.'),A('color',value='#f9f06b',background=True),K('Right'),save],D()),
    ])
    add('insert-codebox','codeboxes',[
        C('insert','At the end of Inbox insert a plain-text code box, 500 pixels wide and 100 high, with line numbers. '
          'Enter exactly these two lines and save:\n```\nprint("ready")\nprint(2 + 3)\n```',
          ['A separate code box appears after the reminder text.','It displays the two code lines with line numbers.'],
          [end,K('Shift+Alt+D'),click('radio button','Plain Text'),A('check',name='Show Line Numbers'),
           button('OK'),T('print("ready")\nprint(2 + 3)'),save],D()),
        C('copy','Copy the code box content using its content-copy command. Paste it as plain text on a new line in Archive and save.',
          'Archive displays the two copied code lines after its original sentence.',
          [A('last-object'),M('Edit','CodeBox','Copy CodeBox Content'),A('end',node='Archive'),K('Return'),M('Edit','Paste as Plain Text'),save],
          [{'kind':'clipboard','aspect':'text','description':'The clipboard holds the two code lines.'}]+D(('content:Archive',),ignore_plain_blank_lines=True),
          depends=('insert',),requires={'visible-1':['copy/text','copy/content:Archive']}),
        C('keep','Remove the code box while keeping its content in the note, then save.',
          'The two code lines now appear as note text without the enclosing code box.',
          [A('last-object'),M('Edit','CodeBox','Delete CodeBox Keep Content'),save],D(),depends=('insert',)),
    ])
    k='insert-table'
    add(k,'tables',[
        C('csv',f'At the end of Inbox insert a table by importing {inbox(k)}/inventory.csv. Save.',
          ['The note contains a table with Item and Count columns.', 'Its data rows are Apples / 3 and Pears / 8.'],
          [end,K('Shift+Alt+H'),A('check',name='Import from CSV File'),button('OK'),A('file',path='inputs/inventory.csv'),save],D(ignore_trailing_widget_newlines=True)),
        C('row','Append an empty row after the Pears row of the table, then save.',
          'The table has a new blank row following the two populated data rows.',
          [A('control',role='text',text='Pears'),M('Edit','Table','Add Row'),save],D(ignore_trailing_widget_newlines=True),depends=('csv',)),
        C('export',f'Export the table to {outbox(k)}/inventory.csv, then show that file in the attachment chooser and leave the chooser open.',
          'The output folder visibly contains inventory.csv.',
          [M('Edit','Table','Table Export...'),A('file',path='outputs/inventory.csv',save=True),A('browse',path='outputs',node='Inbox')],
          [{'kind':'file','path':'inventory.csv','content':'csv','aspect':'rows','description':'CSV preserves every table row and cell.'}],depends=('row',),requires={'visible-1':['export/rows']}),
    ],inputs=[{'text':'Item,Count\nApples,3\nPears,8\n','as':'inventory.csv'}])
    k='insert-image'
    add(k,'images',[
        C('insert',f'At the end of Inbox insert the image {inbox(k)}/card.png and save.',
          'The note displays an orange rectangular image with a blue mark in its upper-left corner.',
          [end,K('Shift+Alt+I'),A('file',path='inputs/card.png'),A('confirm',name='OK'),save],D()),
        C('undo','Undo the image insertion, leaving the document open.',
          'Inbox displays its original text without the appended image.',[K('Control+Z')],depends=('insert',),
          requires={'visible-1':['insert/content:Inbox']}),
        C('redo',f'Redo insertion of the image and save as {outbox(k)}/redone.ctd.',
          'The orange image with its blue mark reappears after the note text.',
          [K('Control+Y'),A('save-as',path='outputs/redone.ctd')],D(path='redone.ctd'),depends=('undo',)),
    ],inputs=[{'image':'card','as':'card.png'}])
    k='insert-attachment'
    add(k,'embedded-files',[
        C('attach',f'At the end of Inbox embed {inbox(k)}/plan.txt as a file attachment and save.',
          'The note shows an embedded file named plan.txt after the reminders.',
          [end,K('Shift+Alt+E'),A('file',path='inputs/plan.txt'),save],D()),
    ],inputs=[{'text':'Monday: outline\nTuesday: review\n','as':'plan.txt'}])
    add('insert-latex','latex',[
        C('insert','At the end of Inbox insert a LaTeX object containing exactly "x^2 + y^2 = z^2" and save. '
          'Then reopen that object for editing.',
          'The LaTeX editor shows the equation text stored in the note.',
          [end,M('Insert','Insert Latex...'),field('x^2 + y^2 = z^2'),button('OK'),save,
           A('edit-icon')],D()),
    ])
    add('links-web','links',[
        C('link','Link the words "Meeting notes" in Inbox to https://example.com/notes and save.',
          'Meeting notes is visibly a hyperlink in the note.',
          [S('Meeting notes'),A('link',target='https://example.com/notes'),K('Right'),save],D()),
        C('edit','Change that hyperlink target to https://example.com/planning, save, and leave its link editor open.',
          'The link editor shows the updated web address for Meeting notes.',
          [S('Meeting notes'),A('link',target='https://example.com/planning'),K('Right'),save,S('Meeting notes'),K('Control+L')],
          D(),depends=('link',)),
    ])
    add('links-node','links',[
        C('link','Turn "Meeting notes" into a link to Garden, then save.',
          'Meeting notes is visibly linked in Inbox.',
          [S('Meeting notes'),A('link',target='Garden',kind='node'),K('Right'),save],D()),
        C('follow','Follow that link to Garden.',
          'Garden is selected and displays the planting and watering reminders.',
          [S('Meeting notes'),K('Right'),A('control',role='text',text='Meeting notes',link=True)],depends=('link',)),
    ])
    add('insert-anchor','anchors',[
        C('anchor','At the beginning of Garden insert an anchor named planting, then save.',
          'An anchor marker is visible at the start of the Garden note.',
          [A('select',node='Garden'),K('Shift+Alt+A'),field('planting'),button('OK'),save],D(('content:Projects/Garden',))),
        C('link','Link "Meeting notes" in Inbox to the planting anchor in Garden. Save and leave the link editor open.',
          'The link editor targets Garden and names the planting anchor.',
          [S('Meeting notes'),A('link',target='Garden',kind='node',anchor='planting'),K('Right'),save,
           S('Meeting notes'),K('Control+L')],D(),depends=('anchor',)),
    ])
    add('insert-toc','table-of-contents',[
        C('toc','In Inbox make Meeting notes a level-1 heading and Buy milk and eggs. a level-2 heading. '
          'Insert a table of contents for this node at its end, then save.',
          ['The two named paragraphs are headings.','A table of contents at the end links to both headings.'],
          [S('Meeting notes'),K('Control+1'),S('Buy milk and eggs.'),K('Control+2'),end,
           M('Insert','Insert TOC and Headers Collapsors...'),button('OK'),save],D()),
    ])
    add('insert-special','text-insertion',[
        C('rule','Insert a horizontal rule on its own new line immediately below the last reminder in Inbox and save.',
          'A horizontal separator appears after the text.',[end,K('Control+R'),save],D(ignore_terminal_newlines=True)),
        C('symbol','At the end of Inbox insert the special character ★ using the special-character chooser and save.',
          'A star character appears after the separator.',
          [end,M('Insert','Insert Special Character...'),click('table cell','★'),button('OK'),save],
          D(ignore_terminal_newlines=True),depends=('rule',)),
    ])
    for fmt in ('ctd','ctb','ctz','ctx','folder'):
        k='storage-'+fmt
        name='saved'+fixtures.EXTENSION[fmt]
        protection= ' Use password cherry-7z.' if fmt in ('ctz','ctx') else ''
        fmt_name={'ctd':'unprotected XML','ctb':'unprotected SQLite','ctz':'password-protected XML','ctx':'password-protected SQLite',
                  'folder':'multiple-files folder'}[fmt]
        checks=D(('format','tree','node:Overview','node:Overview/Tasks','node:Overview/Script','node:Media','node:Ünïcødé','bookmarks'),
                 path=name,**({'password':fixtures.PASSWORD} if protection else {}))
        add(k,'document-storage',[
            C('save',f'Save the opened document as a {fmt_name} document at {outbox(k)}/{name}.{protection} '
              'Select Overview afterwards.',
              'The saved document is open and Overview displays its heading and styled project text.',
              [A('save-as',path='outputs/'+name,format=fmt),N('Overview')],checks),
            C('reopen',f'Reopen {outbox(k)}/{name} through the application. Supply cherry-7z if a password is requested. '
              'Select Tasks under Overview.',
              'The reopened Tasks note displays its task list and Task / Owner table.',
              [A('open',path='outputs/'+name,folder=fmt=='folder',password=fixtures.PASSWORD),N('Tasks')],depends=('save',)),
        ],document='kitchen')
    add('search-current','search',[
        C('find','Find "plumber" in Inbox and select the first match.',
          'The plumber occurrence is highlighted in the Inbox text.',
          [N('Inbox'),A('find',text='plumber',first=True)]),
        C('replace','Replace "plumber" with "electrician" throughout Inbox and save.',
          'The reminder now says Call the electrician tomorrow.',
          [A('find',text='plumber',replacement='electrician'),A('dismiss'),save],D()),
        C('regex','In Inbox use the regular expression `milk[ ]+and[ ]+eggs` and replacement `bread` to replace all matches, then save.',
          'The two space-separated shopping lines say Buy bread.; the tab-separated line and Keep milk and eggplant. remain unchanged.',
          [A('find',text='milk[ ]+and[ ]+eggs',replacement='bread',options=[['Regular Expression',True]]),
           A('dismiss'),save],D()),
    ],document='search-notebook')
    add('search-tree','search',[
        C('names','Find nodes whose names contain "Garden". Leave the match results visible.',
          'Search results identify the Garden node under Projects.',
          [A('find',text='Garden',names=True)]),
        C('all','Close the results and find "the" across all node contents. Leave the results visible.',
          'The result list includes matches from Inbox and Kitchen.',
          [A('dismiss'),A('find',text='the',multiple=True,options=[['Node Name and Tags',False]])]),
    ])
    add('quick-selection','navigation',[
        C('choose','Use quick node selection to navigate to Kitchen.',
          'Kitchen is selected and displays Paint the cabinets.',
          [M('Search','Quick Node Selection...'),field('Kitchen'),K('Return')]),
        C('back','Return to the previously visited Inbox using navigation history.',
          'Inbox is selected and its reminder text is visible.',[M('Tree','Go Back')],depends=('choose',)),
    ])
    add('view-tree','view',[
        C('hide','Hide the tree explorer while reading Inbox.',
          'The note text remains visible with more horizontal space and the node tree is hidden.',[K('F9')]),
        C('show','Show the tree explorer again and expand all nodes.',
          'The tree is visible with Garden and Kitchen beneath Projects, alongside the editor.',
          [K('F9'),M('Tree','Expand All Nodes')],depends=('hide',)),
        C('collapse','Collapse all tree branches.',
          'The roots remain visible while Garden and Kitchen are hidden within Projects.',
          [M('Tree','Collapse All Nodes')],depends=('show',)),
    ])
    add('tree-info','document-information',[
        C('info','Show the tree information for this document.',
          ['The document information reports six nodes in total.','It distinguishes five rich-text nodes and one code node.'],
          [M('File','Tree Info')]),
    ])
    add('quit-cancel','lifecycle',[
        C('question','Append "Unsaved reminder." to Inbox, then request to quit. Leave the save-changes question open.',
          'The application asks what to do with unsaved changes.',
          [end,T('Unsaved reminder.'),M('File','Quit')]),
        C('cancel','Cancel quitting and save the document.',
          'The application stays open with Unsaved reminder. in Inbox.',
          [button('Cancel'),save],D(),depends=('question',)),
    ])
    from imports import episodes
    return result + episodes()
