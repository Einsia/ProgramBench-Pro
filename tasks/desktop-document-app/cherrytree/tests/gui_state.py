"""Settings persistence, GUI export scopes and shared-node semantics."""
from specification import action as A, key as K, menu as M, node as N, select as S, typed as T, saved as D, step as C, episode as W, outbox


def build():
    result=[]
    def add(k,f,cps,**kw):result.append(W(k,f,cps,**kw))
    save=A('save')
    button=lambda name:A('button',name=name)
    click=lambda role,name:A('click',role=role,name=name)
    k='preferences-persist'
    prefcheck={'kind':'file','path':'preferences.cfg','content':'ini','aspect':'all',
               'keys':['editor.show_line_numbers','editor.line_wrapping'],
               'description':'Exported preferences retain line numbers enabled and wrapping disabled.'}
    add(k,'preferences',[
        C('set',f'In text-editor preferences enable line numbers and disable line wrapping. Export these preferences to '
          f'{outbox(k)}/preferences.cfg, then leave the text-editor preferences visible for inspection.',
          ['Line numbers are enabled in editor preferences.','Line wrapping is disabled in editor preferences.'],
          [M('File','Preferences','Preferences'),A('check',name='Show Line Numbers'),
           A('check',name='Use Line Wrapping',checked=False),button('Close'),
           M('File','Preferences','Export Preferences...'),A('file',path='outputs/preferences.cfg',save=True),
           M('File','Preferences','Preferences')],[prefcheck]),
        C('restart','The application has been restarted. Reopen text-editor preferences to inspect the saved settings.',
          ['Line numbers are still enabled after restart.','Line wrapping remains disabled after restart.'],
          [M('File','Preferences','Preferences')],depends=('set',),lifecycle='restart'),
    ])
    add('nodes-shared','shared-nodes',[
        C('share','Create a shared copy of Archive and save. Leave the tree expanded.',
          'Two tree entries share the Archive note.',
          [N('Archive'),M('Tree','Create Shared Node'),M('Tree','Expand All Nodes'),save],D(('tree','node:Archive#2'))),
        C('edit','At the end of the second Archive entry, append "Shared update." as a new paragraph below the existing text. Save, then select the original Archive.',
          'The original Archive displays the appended text because both entries share their content.',
          [N('Archive',1),A('select',node=None),K('Control+End'),T('Shared update.'),save,N('Archive')],
          D(('content:Archive','content:Archive#2')),depends=('share',)),
    ])
    for fmt,label in [('txt','Export to Plain Text'),('html','Export To HTML'),('pdf','Export To PDF'),('ctd','Export To CherryTree')]:
        k='gui-export-'+fmt
        if fmt in ('html','txt'):
            base={'kind':'export','run':False,'document':outbox(k)+'/notebook.ctd','format':fmt,
                  'folder':'exports','ignore':['seed.txt']}
            aspects=['files']+(['index'] if fmt=='html' else [])+[('node-page:' if fmt=='html' else 'node-text:')+str(i) for i in (2,3,4)]
            checks=[dict(base,aspect=aspect,description='The GUI exports the Projects branch with its two child notes: '+aspect) for aspect in aspects]
            finish=[button('OK'),A('file',path='outputs/exports')]
            if fmt == 'html':
                finish[-1]['verify_location'] = True
                finish[-1]['reopen'] = [button('Cancel'), M('File','Export','Export To HTML'),
                                       click('radio button','Selected Node and Subnodes'), button('OK')]
            location=outbox(k)+'/exports'
            shown_folder='outputs/exports/Projects_'+('TXT' if fmt=='txt' else 'HTML')
            shown='The exported Projects, Garden and Kitchen files are visible in the output folder.'
        elif fmt=='pdf':
            checks=[{'kind':'file','path':'branch.pdf','content':'pdf','aspect':'words',
                     'description':'The PDF export contains the Projects branch and its child-note words.'}]
            finish=[button('OK'),A('file',path='outputs/branch.pdf',save=True)]
            location=outbox(k)+'/branch.pdf'
            shown_folder='outputs'
            shown='The exported branch.pdf is visible in the output folder.'
        else:
            checks=D(('tree','node:Projects','node:Projects/Garden','node:Projects/Kitchen'),path='branch.ctd')
            finish=[button('OK'),click('radio button','Single XML File (.ctd)'),button('OK'),
                    A('file',path='outputs/branch.ctd',save=True)]
            location=outbox(k)+'/branch.ctd'
            shown_folder='outputs'
            shown='The exported branch.ctd is visible in the output folder.'
        file_mode = ('using the Single XML File (.ctd) format' if fmt == 'ctd' else
                     'using separate files per node if the format offers that option')
        w=W(k,'gui-export',[
            C('scope',f'Select Projects and configure a {fmt.upper()} export of that node and its subnodes. '
              'Include node names when available. Leave the export scope options visible.',
              'The export is configured for Projects and its child notes rather than the entire tree.',
              [N('Projects'),M('File','Export',label),click('radio button','Selected Node and Subnodes')]),
            C('export',f'Finish that export to {location}, {file_mode}. '
              'Then inspect the resulting file names with the file-attachment chooser (it lists all file types). '
              'Leave that chooser open without attaching anything.',
              shown,finish+[A('browse',path=shown_folder)],checks,depends=('scope',)),
        ])
        w['setup'].append({'id':'export-folder','op':'upload','area':'outbox','files':[{'text':'output directory\n','as':'exports/seed.txt'}]})
        w['checkpoints'][-1]['depends_on'].append('setup:export-folder')
        result.append(w)
    return result
