"""Additional offline user journeys identified from the pinned product manual."""
import json


def build(episode,step,check,note):
    w=[]
    w.append(episode('import-onenote','offline OneNote import',[
        step('import','Import $INBOX/formatting.one using the OneNote importer, continue past any compatibility notice, then open Bold & italic.',
             ['The imported Bold & italic page is available.','The page includes the words Bold and italic with their formatting.'],
             [{'op':'import','path':'inbox/formatting.one','format':'ONE - OneNote Notebook','title':'Bold & italic'},
              {'op':'viewer'}],[check('imported',title='Bold & italic',text='Bold and italic and bold italic.')])],
        notes=[],selected=None,files=['formatting.one']))
    enex=episode('import-enex-complete','multi-note ENEX import',[
        step('import','Import $INBOX/multi-note.enex as Markdown and open ENEX source.',
             ['Both ENEX source and ENEX target are available.','ENEX source displays its bold observation, internal note link and image.'],
             [{'op':'import','path':'inbox/multi-note.enex','format':'ENEX - Evernote Export File (as Markdown)','title':'ENEX source'},
              {'op':'viewer'}],[])],notes=[],selected=None,files=['multi-note.enex'])
    cp=enex['checkpoints'][0];item={'kind':'enex-complete'};cp['checks']=[item]
    cp['assertions'] += [{'id':'import-enex-complete/import/data-'+key,'channel':'backend','method':'program',
        'requirement':req,'check':item,'aspect':key} for key,req in {
        'titles':'Both source pages retain their titles.','content':'Both page bodies preserve their text and formatting.',
        'authors':'Each page keeps its distinct author.','dates':'Explicit created and updated dates are preserved.',
        'tags':'Each page keeps its assigned tags.','resource':'The embedded image retains its bytes.',
        'link':'The source link resolves to the imported target note.'}.items()]
    w.append(enex)
    import archives
    for fmt,menu,filename in [('jex','JEX - Joplin Export File','field-backup.jex'),('raw','RAW - Joplin Export Directory',None)]:
        wf=episode('archive-'+fmt,'complete notebook backup',[
            step('backup','Export Workbench including its Field trips sub-notebook as '+fmt.upper()+' to $OUTBOX'+('/'+filename if filename else '')+'.',
                 'The export finishes and the original Trip log remains available.',
                 [{'op':'archive-export','format':menu,'filename':filename}],[]),
            step('restore','Import that backup as an additional notebook tree and open the imported Trip log.',
                 ['An additional notebook tree contains Trip log and the Field trips sub-notebook.',
                  'The imported Trip log retains its note link, image and text attachment.'],
                 [{'op':'archive-import','format':menu,'filename':filename}],[],depends=('backup',))],
            notes=[],books=['Workbench'],selected='Trip log')
        wf['setup'][0]['archive']=True
        for cp in wf['checkpoints']:
            item={'kind':'archive-export' if cp['id']=='backup' else 'archive-import','format':fmt,'filename':filename}
            cp['checks']=[item]
            cp['assertions'] += [{'id':wf['id']+'/'+cp['id']+'/data-'+key,'channel':'backend','method':'program',
                                'requirement':value,'check':item,'aspect':key} for key,value in archives.ASPECTS.items()]
        w.append(wf)
    md=episode('archive-markdown','nested Markdown directory import',[
        step('export','Export Workbench including its Field trips sub-notebook as Markdown into $OUTBOX.',
             'The export completes while Trip log remains available.',
             [{'op':'archive-export','format':'MD - Markdown','filename':None}],
             [check('markdown-tree-export')]),
        step('import','Import that Markdown directory as an additional notebook tree and open the imported Trip log.',
             ['The imported tree contains both Trip log and Field trips / Trip plan.',
              'Trip log retains its image and link to Trip plan.'],
             [{'op':'archive-import','format':'MD - Markdown (Directory)','filename':None}],[],depends=('export',))],
        notes=[],books=['Workbench'],selected='Trip log')
    md['setup'][0]['archive']='markdown';cp=md['checkpoints'][1];item={'kind':'archive-import','format':'markdown'};cp['checks']=[item]
    cp['assertions'] += [{'id':'archive-markdown/import/data-'+key,'channel':'backend','method':'program',
                        'requirement':archives.ASPECTS[key],'check':item,'aspect':key} for key in ['notes','folders','resources','links']]
    w.append(md)
    lines='pear\napple\nplum'
    w.append(episode('editor-commands','editor commands and clipboard',[
        step('sort','Sort all lines of Commands alphabetically.','The lines read apple, pear, plum in that order.',
             [{'op':'select-body'},{'op':'press','key':'Control+Alt+s'},{'op':'blur'}],
             [note('Commands',body='apple\npear\nplum')]),
        step('swap','Move the first line down by one line.','Pear precedes apple and plum remains last.',
             [{'op':'line','line':0,'key':'Alt+Down'},{'op':'blur'}],[note('Commands',body='pear\napple\nplum')],depends=('sort',)),
        step('cut','Select and cut the complete note body.','The note body is empty.',
             [{'op':'select-body'},{'op':'press','key':'Control+X'},{'op':'blur'}],
             [note('Commands',body=''),check('clipboard',text='pear\napple\nplum')],depends=('swap',)),
        step('paste','Paste the cut text back into Commands.','All three lines return in their previous order.',
             [{'op':'focus-body'},{'op':'press','key':'Control+V'},{'op':'blur'}],
             [note('Commands',body='pear\napple\nplum')],depends=('cut',))],notes=[{'title':'Commands','body':lines}],selected='Commands'))
    replace='oak Oak oaks\noak oak\nmap-12 map-34'
    w.append(episode('editor-replace','find and replace match modes',[
        step('whole','Replace all whole-word, case-sensitive occurrences of oak with elm, preserving Oak and oaks.',
             'The text reads elm Oak oaks, then elm elm; the map line is unchanged.',
             [{'op':'replace','find':'oak','replacement':'elm','whole':True,'case':True,'regex':False}],
             [note('Replace lab',body='elm Oak oaks\nelm elm\nmap-12 map-34')]),
        step('regex','Using regular-expression replace, change map followed by a hyphen and digits to route everywhere.',
             'The final line reads route route, while both earlier lines are retained.',
             [{'op':'replace','find':r'map-\d+','replacement':'route','whole':False,'case':False,'regex':True}],
             [note('Replace lab',body='elm Oak oaks\nelm elm\nroute route')],depends=('whole',))],
        notes=[{'title':'Replace lab','body':replace}],selected='Replace lab'))
    samples=[
        ('toc','[toc]\n\n# Journey\n\n## North bank\n\nObserve the trees.\n\n## South bank\n\nCount the reeds.',
         ['A table of contents links to Journey, North bank and South bank.','The corresponding heading hierarchy is visible.']),
        ('mark','Keep ==the marked phrase== visible.', ['The marked phrase is visibly highlighted.']),
        ('chemistry',r'$\ce{2H2 + O2 -> 2H2O}$',['The chemical reaction displays subscripts and a reaction arrow.']),
        ('music','```abc\nX:1\nT:Field melody\nM:4/4\nL:1/4\nK:C\nC D E F | G A B c |\n```',
         ['Field melody is rendered as musical notation with a staff and notes.']),
    ]
    steps=[]
    for key,body,visible in samples:
        steps.append(step(key,'Replace Extensions with this Markdown and inspect the rendered result:\n````\n'+body+'\n````',
                          visible,[{'op':'editor'},{'op':'body','value':body},{'op':'viewer'}],[note('Extensions',body=body)]))
    w.append(episode('markdown-builtins','built-in Markdown extensions',steps,
                      notes=[{'title':'Extensions','body':'Initial document.'}],selected='Extensions'))
    enabled='Water H~2~O, area m^2^, :smile:, ++added++ and (c).'
    w.append(episode('markdown-options','Markdown extension preferences',[
        step('enable','Enable the built-in Sub, Sup, Emoji, Insert and Typographer Markdown extensions. Replace Options with this text and view it:\n```\n'+enabled+'\n```',
             ['The 2 in H2O is a subscript and the 2 in m2 is a superscript.',
              'A smile emoji, inserted text and a copyright symbol are displayed.'],
             [{'op':'markdown-options','options':['Sub','Sup','Emoji','Insert','Typographer'],'enabled':True},
              {'op':'body','value':enabled},{'op':'viewer'}],[note('Options',body=enabled)]),
        step('disable','Disable the Sub and Sup extensions, then view the same document.',
             'H~2~O and m^2^ appear literally, while the other enabled extensions remain rendered.',
             [{'op':'markdown-options','options':['Sub','Sup'],'enabled':False},{'op':'viewer'}],depends=('enable',))],
        notes=[{'title':'Options','body':'Initial document.'}],selected='Options'))
    samples=[
        ('definitions',['Deflist'],'Oak\n: A broadleaf tree.\n\nElm\n: Another tree.',
         ['Oak and Elm appear as definition terms with their definitions below.']),
        ('abbreviation',['Abbr'],'*[GPS]: Global Positioning System\n\nUse GPS in the field.',
         ['GPS appears as an abbreviation; hovering it reveals Global Positioning System.']),
        ('screenplay',['Fountain'],'```fountain\nINT. FOREST - DAY\n\nADA\nWe counted three trees.\n```',
         ['A screenplay scene heading and ADA dialogue are typeset.']),
        ('multitable',['Multitable'],'| Area | Count |\n| --- | --- |\n| North and south ||\n| Oak | 3 |',
         ['The North and south cell spans both columns, and the Oak row has its own Count cell.']),
    ]
    steps=[]
    for key,options,body,visible in samples:
        actions=[{'op':'markdown-options','options':options,'enabled':True},{'op':'editor'},
                 {'op':'body','value':body},{'op':'viewer'}]
        if key=='abbreviation':actions.append({'op':'hover-text','text':'GPS'})
        steps.append(step(key,'Enable '+', '.join(options)+' and render this document:\n````\n'+body+'\n````'+
                          (' Hover GPS to inspect its expansion.' if key=='abbreviation' else ''),
                          visible,actions,[note('Extensions',body=body)]))
    w.append(episode('markdown-additional','additional built-in document syntax',steps,
                      notes=[{'title':'Extensions','body':'Initial document.'}],selected='Extensions'))
    w.append(episode('rich-editing','rich text formatting and conversion',[
        step('bold','Switch Rich lab to the rich text editor and make its sentence bold.',
             ['The sentence is editable as rich text.','Amber forest is shown in bold.'],
             [{'op':'press','key':'Control+Alt+E'},{'op':'rich-select'},{'op':'press','key':'Control+B'},{'op':'blur'}],
             [check('markup',title='Rich lab',tag='strong',text='Amber forest')]),
        step('italic','Make the same sentence italic while retaining bold.', 'The sentence is both bold and italic.',
             [{'op':'rich-select'},{'op':'press','key':'Control+I'},{'op':'blur'}],
             [check('markup',title='Rich lab',tag='em',also='strong',text='Amber forest')],depends=('bold',)),
        step('markdown','Switch back to Markdown editing and inspect the formatted sentence.',
             'The sentence and both formatting styles survive the editor switch.',
             [{'op':'press','key':'Control+Alt+E'},{'op':'viewer'}],
             [check('markup',title='Rich lab',tag='em',also='strong',text='Amber forest')],depends=('italic',))],
        notes=[{'title':'Rich lab','body':'Amber forest'}],selected='Rich lab'))
    w.append(episode('rich-table','rich text table editing',[
        step('edit','Switch Table lab to rich text and change the Oak cell to Birch.',
             ['The table is editable in rich text.','Birch replaces Oak while both counts and the Elm row remain.'],
             [{'op':'press','key':'Control+Alt+E'},{'op':'rich-cell','old':'Oak','value':'Birch'}],
             [check('table',title='Table lab',rows=[['Plant','Count'],['Birch','3'],['Elm','7']])]),
        step('append','Add a new final table row containing Pine and 2.',
             'Pine and its count 2 appear as a third data row.',
             [{'op':'rich-table-row','last':'7','values':['Pine','2']}],
             [check('table',title='Table lab',rows=[['Plant','Count'],['Birch','3'],['Elm','7'],['Pine','2']])],depends=('edit',)),
        step('markdown','Switch back to Markdown and view the table.',
             'The edited table retains all three rows and their counts.',
             [{'op':'press','key':'Control+Alt+E'},{'op':'viewer'}],
             [check('table',title='Table lab',rows=[['Plant','Count'],['Birch','3'],['Elm','7'],['Pine','2']])],depends=('append',))],
        notes=[{'title':'Table lab','body':'| Plant | Count |\n| --- | --- |\n| Oak | 3 |\n| Elm | 7 |'}],selected='Table lab'))
    history=episode('history-restore','previous note versions',[
        step('preview','Open the previous versions of History journal and preview the revision from 14 January 2026 at 08:00 UTC.',
             ['The previous-version viewer identifies History journal.','The preview shows Previous survey: two oak trees.'],
             [{'op':'history-preview'}],modal=True),
        step('restore','Restore that previous version as a separate note and open the restored copy.',
             ['A restored History journal is available in Restored Notes.','The restored content says Previous survey: two oak trees.'],
             [{'op':'history-restore'}],
             [check('history-copy',title='History journal',old='Previous survey: two oak trees.',current='Current survey: four oak trees.')],depends=('preview',))],
        notes=[{'title':'History journal','body':'Current survey: four oak trees.'}],selected='History journal')
    history['setup'][0]['history']={'title':'History journal','body':'Previous survey: two oak trees.','time':1768377600000}
    w.append(history)
    canvas={'nodes':[{'id':'alpha','type':'text','text':'Source card','x':0,'y':0,'width':220,'height':140},
                     {'id':'beta','type':'text','text':'Destination card','x':420,'y':0,'width':220,'height':140}], 'edges':[]}
    body='```jsoncanvas\n'+json.dumps(canvas)+'\n```'
    w.append(episode('whiteboard-graph','whiteboard connections and promotion',[
        step('connect','Connect Source card to Destination card with a forward arrow.',
             'An arrow connects Source card to Destination card.',[{'op':'whiteboard-connect'}],
             [check('canvas-edges',title='Route map',edges=[{'from':'Source card','to':'Destination card','fromEnd':'none','toEnd':'arrow','label':''}])]),
        step('label','Label that connection "Field route" and make its arrows bidirectional.',
             ['The connection is labelled Field route.','Arrowheads appear at both ends.'],
             [{'op':'whiteboard-edge','label':'Field route','direction':'bidirectional'}],
             [check('canvas-edges',title='Route map',edges=[{'from':'Source card','to':'Destination card','fromEnd':'arrow','toEnd':'arrow','label':'Field route'}])],depends=('connect',)),
        step('flip','Make the labelled connection one-way from Destination card to Source card, preserving its label.',
             'The Field route arrow points from Destination card to Source card.',
             [{'op':'click','name':'Swap source and target','role':'push button'},
              {'op':'click','name':'Arrow at target','role':'toggle button'}],
             [check('canvas-edges',title='Route map',edges=[{'from':'Destination card','to':'Source card','fromEnd':'none','toEnd':'arrow','label':'Field route'}])],depends=('label',)),
        step('delete','Delete the connection while keeping both cards.',
             'Both text cards remain and no connection joins them.',
             [{'op':'whiteboard-delete-edge'}],
             [check('canvas-edges',title='Route map',edges=[])],depends=('flip',)),
        step('promote','Promote Destination card into an ordinary note.',
             ['Destination card is available as a note.','The whiteboard now links to that note.'],
             [{'op':'whiteboard-promote','text':'Destination card'}],
             [note('Destination card',body='Destination card',parent='Workbench'),
              check('canvas-promoted',title='Route map',target='Destination card')],depends=('delete',))],
        notes=[{'title':'Route map','body':body}],selected='Route map'))
    w.append(episode('workspace-preferences','workspace visibility and persistence',[
        step('hide','Hide the note list while keeping the note and notebook sidebar visible.',
             'The note list is hidden and the current note remains readable.',
             [{'op':'menu','items':['View','Toggle note list F11']},{'op':'note-list-state','visible':False}]),
        step('restart','After restarting, open River survey and verify that the note list is still hidden.',
             ['The note list remains hidden.','River survey remains available and readable.'],
             [{'op':'wait-note'},{'op':'note-list-state','visible':False}],lifecycle='restart',depends=('hide',)),
        step('restore','Show the note list again, then hide the menu bar.',
             ['The note list is visible again.','The application menu bar is hidden.'],
             [{'op':'menu','items':['View','Toggle note list F11']},{'op':'note-list-state','visible':True},
              {'op':'press','key':'Control+Shift+M'}],depends=('restart',)),
        step('menu','Show the menu bar again.', 'The File, Edit and View menus are available again.',
             [{'op':'press','key':'Control+Shift+M'}],depends=('restore',))],
        notes=[{'title':'River survey','body':'# River survey\n\nThree oak trees grow beside the river.\n\nNorth bank: 2 trees.\nSouth bank: 1 tree.'}],
        selected='River survey'))
    for item in w:
        item['budget']={'calls':400,'tokens':3_000_000,'seconds':2700}
    return w
