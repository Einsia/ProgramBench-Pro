"""Formatting reuse, TOC, preferences and export-scope episodes."""
from specification import action as A,key as K,menu as M,node as N,select as S,typed as T,saved as D,step as C,episode as W,outbox,inbox


def build():
    result=[];save=A('save');button=lambda n:A('button',name=n)
    def add(k,f,steps,**kw):result.append(W(k,f,steps,**kw))
    add('format-reuse','rich-text',[
        C('clone','In Format make Source phrase bold and italic. Clone that combined formatting and apply it to Target phrase, then save.',
          'Source phrase and Target phrase are both bold and italic; Latest phrase is unchanged.',
          [S('Source phrase','Format'),K('Control+B'),K('Control+I'),K('Left'),M('Format','Format Clone'),S('Target phrase','Format'),M('Format','Format Latest'),K('Right'),save],D(('content:Format',))),
        C('latest','Apply the same latest format to Latest phrase and save.',
          'All three phrases now use the same bold italic format.',
          [S('Latest phrase','Format'),M('Format','Format Latest'),K('Right'),save],D(('content:Format',)),depends=('clone',)),
    ],document='advanced')
    add('toc-collapse','table-of-contents',[
        C('create','At the end of Headings insert a table of contents and header collapsors for that node. Save.',
          'The table of contents links to Chapter, Section and Detail, and their body text is visible.',
          [A('end',node='Headings'),M('Insert','Insert TOC and Headers Collapsors...'),button('OK'),save],D(('content:Headings',))),
        C('collapse','Collapse the TOC headers in Headings.',
          'Chapter remains visible while the lower-level headings and body text are hidden.',
          [A('select',node='Headings'),K('Control+A'),M('Format','Collapse TOC Headers'),A('assert-editor',contains='Chapter',absent='Section body')],
          depends=('create',),requires={'visible-1':['expand/visible-1']}),
        C('expand','Expand the TOC headers again.',
          'Section, Detail and all three body paragraphs are visible again.',
          [A('select',node='Headings'),K('Control+A'),M('Format','Expand TOC Headers'),A('assert-editor',contains='Detail body')],depends=('collapse',)),
    ],document='advanced')
    add('format-occurrence','rich-text',[
        C('middle','In Repeated, make only the middle occurrence of "same phrase" bold and save.',
          'The middle phrase is bold; the first and third occurrences remain plain.',
          [A('select',node='Repeated',start=14,length=11),K('Control+B'),K('Right'),save],D(('content:Repeated',))),
    ],document='advanced')
    k='preferences-import'
    settings={'kind':'file','path':'after.cfg','content':'ini','aspect':'all','keys':['editor.show_line_numbers','editor.line_wrapping'],
              'description':'Imported preferences restore both requested editor settings.'}
    add(k,'preferences',[
        C('roundtrip',f'Enable line numbers and disable line wrapping, then export preferences to {outbox(k)}/saved.cfg. '
          f'Reverse both settings, import saved.cfg to restore them, export the restored preferences to {outbox(k)}/after.cfg, '
          'and leave Text and Code preferences open.',
          'Imported preferences have line numbers enabled and wrapping disabled.',
          [M('File','Preferences','Preferences'),A('check',name='Show Line Numbers'),A('check',name='Use Line Wrapping',checked=False),button('Close'),
           M('File','Preferences','Export Preferences...'),A('file',path='outputs/saved.cfg',save=True),
           M('File','Preferences','Preferences'),A('check',name='Show Line Numbers',checked=False),A('check',name='Use Line Wrapping'),button('Close'),
           M('File','Preferences','Import Preferences...'),A('file',path='outputs/saved.cfg'),A('confirm',name='Yes'),A('dismiss'),
           M('File','Preferences','Export Preferences...'),A('file',path='outputs/after.cfg',save=True),M('File','Preferences','Preferences')],[settings]),
        C('restart','After restart, inspect Text and Code preferences.',
          'Line numbers remain enabled and wrapping remains disabled after restart.',
          [M('File','Preferences','Preferences')],depends=('roundtrip',),lifecycle='restart'),
    ])
    for scope,key_,select,include in [('Selected Text Only','selection',True,False),('Selected Node Only','node',False,False),('All the Tree','all',False,True)]:
        k='export-scope-'+key_
        prepare=[S('Call the plumber tomorrow.') if select else N('Inbox')]
        w=W(k,'gui-export',[
            C('export',f'Export {"only the selected sentence Call the plumber tomorrow." if select else "only Inbox" if key_=="node" else "the entire tree"} '
              f'to the plain-text file {outbox(k)}/scope.txt. {"Include" if include else "Omit"} node names. '
              'Then display the exported file in the attachment chooser and leave the chooser open.',
              'The export folder contains the requested plain-text output.',
              prepare+[A('export',kind='txt',path='outputs/scope.txt',scope=scope,single=True,include=include),A('browse',path='outputs',node='Inbox')],
              [{'kind':'file','path':'scope.txt','content':'text','aspect':'text','description':'The text export contains exactly the requested scope and node-name policy.'}])
        ])
        w['setup'].append({'id':'export-folder','op':'upload','area':'outbox','files':[{'text':'folder\n','as':'exports/seed.txt'}]})
        w['checkpoints'][0]['depends_on'].append('setup:export-folder');result.append(w)
    add('timestamp','text-tools',[
        C('insert','At the end of Archive insert the current timestamp with the application command and save.',
          'Archive shows the timestamp for the runtime clock, 2024-01-01 at 12:00 UTC.',
          [A('end',node='Archive'),M('Insert','Insert Timestamp'),save],D(('content:Archive',))),
    ])
    add('node-syntax-inherit','node-properties',[
        C('inherit','Change Projects to Plain Text and make its children inherit that syntax. Save and select Garden.',
          'Garden is a plain-text node retaining its planting and watering reminders.',
          [N('Projects'),K('F2'),A('properties',syntax='Plain Text'),M('Tree','Children Inherit Syntax'),A('confirm',name='Yes'),save,N('Garden')],
          D(('props:Projects','props:Projects/Garden','props:Projects/Kitchen','text:Projects/Garden'))),
    ])
    k='new-document'
    add(k,'document-storage',[
        C('create',f'Create a rich-text root note called First Note with content "A fresh start." and save a new XML document to {outbox(k)}/new.ctd.',
          'The saved new document shows First Note with A fresh start.',
          [A('add',name='First Note',text='A fresh start.'),A('save-as',path='outputs/new.ctd')],D(('format','tree','content:First Note'),path='new.ctd')),
    ],empty=True,opened=False)
    add('quit-discard','lifecycle',[
        C('discard','Append "Discard this edit." in Inbox, request to quit and discard the unsaved change.',
          'The application closes after discarding the unsaved edit.',
          [A('end'),T('Discard this edit.'),M('File','Quit'),button('Discard')],requires={'visible-1':['restart/visible-1']}),
        C('restart','The application has restarted. Open Inbox.',
          'Inbox contains only its original reminders; Discard this edit. is absent.',
          [N('Inbox')],D(('content:Inbox',)),depends=('discard',),lifecycle='restart'),
    ])
    return result
