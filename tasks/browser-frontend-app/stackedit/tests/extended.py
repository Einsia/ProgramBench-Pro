"""State transitions and settings exercised through public editor and file channels."""
from pathlib import Path
from specification import cp,episode,T,X,M,F,S,P,C,W,R,SOURCE,RENDER,fenced


def settings_route(yaml):
    return [M('Settings'),C(yaml),X('Ok'),T('Close side bar')]


def property_route(yaml):
    return [M('File properties'),X('YAML properties'),C(yaml),{'do':'modal-ok'},T('Close side bar')]


def backup_export():
    return [W(),M('Workspace backups'),X('Export workspace backup'),{'do':'download','suffix':'.json'}]


def backup_import(name):
    return [M('Workspace backups'),X('Import workspace backup'),{'do':'upload','file':name},T('Close side bar')]


def settings_cases():
    points=[]
    for cid,props in [('metadata','title: New harbor\nauthor: Ada\ntags: [water, maps]\n'),
                      ('preset','extensions:\n  preset: commonmark\n'),
                      ('unicode','title: "海岸 Café"\nsummary: |\n  First line\n  Second line\n')]:
        yaml='newFileProperties: |\n'+''.join('  '+line+'\n' for line in props.splitlines())+'newFileContent: "A ==marked== :smile: note."\n'
        points.append(cp('new-properties-'+cid,'Set these application defaults, create a new file named Draft, then export it as Jekyll HTML:\n'+fenced(yaml,'yaml'),
            'Draft is created and its Jekyll document is downloaded with the new-file properties.',settings_route(yaml)+[{'do':'new-file','name':'Draft'},M('Import/export'),X('Export as HTML'),{'op':'select','target':{'label':'Template'},'value':'jekyllSite'},X('Ok'),{'do':'download','suffix':'.html'}],checks=[{'type':'download','suffix':'.html','format':'jekyllSite'}]))
    for flag in [True,False]:
        yaml='editor:\n  listAutoNumber: '+str(flag).lower()
        points.append(cp('numbering-'+str(flag).lower(),'Set listAutoNumber to '+str(flag).lower()+'. In the existing ordered list, put the caret after North, press Enter and type Middle. Leave the source visible.',
            'The source contains North, Middle and South; its list markers follow the configured automatic-numbering behavior.',settings_route(yaml)+[{'do':'selection','start':8,'end':8},P('Enter'),{'op':'type','value':'Middle'}],text='1. North\n2. South',checks=[SOURCE]))
    for cid,source,sequence in [('right','', ['=','=','>',' ']),('left','', ['<','=','=',' '])]:
        points.append(cp('expand-'+cid,'In the empty editor, type '+('`==> `' if cid=='right' else '`<== `')+' as consecutive keystrokes, including the trailing space, to use the default text expansion.',
            'The typed shortcut expands to its corresponding arrow.',[{'op':'type','value':c} for c in sequence],text=source,selection=[0,0],checks=[SOURCE]))
    yaml="shortcuts:\n  'h h space':\n    method: expand\n    params: ['hh ', 'Harbor home ']\n"
    points.append(cp('custom-expansion','Configure the following text expansion, then type `hh ` as consecutive keystrokes in the empty editor:\n'+fenced(yaml,'yaml'),
        'The source contains the configured expansion Harbor home.',settings_route(yaml)+[{'do':'selection','start':0,'end':0}]+[{'op':'type','value':c} for c in 'hh '],text='',checks=[SOURCE]))
    return [episode('gui-settings-behavior-'+str(i//4+1),'settings',points[i:i+4]) for i in range(0,len(points),4)]


def conversion_cases():
    rows=[('setext','headingStyle','setext','convert-heading.html'),('bullet','bulletListMarker','+','convert-list.html'),
          ('rule','hr','***','convert-rule.html'),('indented','codeBlockStyle','indented','convert-code.html'),
          ('fence','fence','~~~','convert-code.html'),('emphasis','emDelimiter','*','convert-emphasis.html'),
          ('strong','strongDelimiter','__','convert-strong.html'),('reference','linkStyle','referenced','convert-link.html'),
          ('collapsed','linkReferenceStyle','collapsed','convert-link.html'),('shortcut','linkReferenceStyle','shortcut','convert-link.html')]
    points=[]
    import json
    for cid,key,value,name in rows:
        yaml='turndown:\n  '+key+': '+json.dumps(value)+'\n'
        if key=='linkReferenceStyle':yaml+='  linkStyle: referenced\n'
        html=(Path(__file__).parent/'fixtures'/name).read_text()
        points.append(cp(cid,'Apply these HTML conversion settings and reload to activate them:\n'+fenced(yaml,'yaml')+'\nSelect the document source and replace it by pasting this HTML through the rich-text clipboard. Leave the generated Markdown visible:\n'+fenced(html,'html'),
            'The imported content is editable Markdown and uses the requested conversion option.',settings_route(yaml)+[{'op':'reload'},{'do':'selection','start':0,'end':32},{'op':'paste','html':html}],checks=[{'type':'conversion','style':cid}]))
    return [episode('gui-conversion-'+str(i//5+1),'imports',points[i:i+5],sorted({r[3] for r in rows})) for i in range(0,len(points),5)]


def workspace_cases():
    new=lambda kind,name:{'do':'new-'+kind,'name':name}
    moved=[R('Root note'),new('folder','Voyages'),new('file','Tide'),S('Travels with the folder.'),X('Root note'),new('folder','Archive'),{'do':'drag-text','text':'Voyages','to':'Archive'}, {'do':'tree-child','parent':'Archive','child':'Voyages'},{'do':'tree-child','parent':'Voyages','child':'Tide'},X('Tide')]
    points=[cp('move-folder','Rename the initial file Root note. Create a root folder Voyages containing Tide with source `Travels with the folder.` and another root folder Archive. Move Voyages into Archive and open Tide with both folders expanded.',
        'Archive contains Voyages, which still contains Tide and its original text.',moved,checks=[SOURCE])]
    for confirm in [False,True]:
        recipe=[R('Before reset'),S('Keep this before reset.'),M('Reset application'),X('Yes, clean' if confirm else 'No')]
        if confirm:recipe += [W(),{'do':'dismiss-tour'},S('Fresh after reset.'),R('After reset'),T('Toggle explorer')]
        else:recipe += [T('Close side bar'),S('Keep this before reset. Still editable.'),T('Toggle explorer')]
        points.append(cp('reset-'+('confirm' if confirm else 'cancel'),
            'Rename the document Before reset and replace its source with `Keep this before reset.`. Invoke Reset application and '+('confirm. In the fresh workspace, create/edit a document named After reset with source `Fresh after reset.` and show the explorer.' if confirm else 'cancel. Append ` Still editable.` to the retained source and show the explorer.'),
            'The workspace '+('contains After reset with Fresh after reset. and no Before reset document.' if confirm else 'still contains Before reset with Keep this before reset. Still editable.'),recipe,checks=[SOURCE]))
    temporary=[{'name':'Temp north','text':'Temporary north note.'},{'name':'Temp south','text':'Temporary south note.'}]
    for cid in ['delete','clear','cancel']:
        action=[T('Toggle explorer'),{'do':'tree-child','parent':'Temp','child':'Temp north'},X('Temp north') if cid!='clear' else X('Temp'),T('Delete'),X('No' if cid=='cancel' else 'Yes, delete all' if cid=='clear' else 'Yes, delete')]
        if cid=='cancel':action += [X('Temp north'),S('Temporary north note. Still editable.')]
        elif cid=='delete':action += [X('Temp south')]
        else:action += [{'do':'new-file','name':'Permanent note'},S('A fresh permanent note.')]
        points.append(cp('temporary-'+cid,
            'Two temporary embedding documents, Temp north and Temp south, have been opened. '+{'delete':'Permanently delete Temp north, then open Temp south.','clear':'Permanently clear all temporary files, then create Permanent note in the main workspace with source `A fresh permanent note.`.','cancel':'Attempt to delete Temp north but cancel the confirmation; append ` Still editable.` to its source.'}[cid],
            {'delete':'Temp north is absent from Temp while Temp south retains Temporary south note.','clear':'Temp has no documents and Permanent note contains A fresh permanent note.','cancel':'Temp north is retained with Temporary north note. Still editable. and Temp south remains.'}[cid],action,text=None,temporary=temporary,checks=[SOURCE]))
    return [episode('gui-workspace-transitions','workspace',points[:3]),episode('gui-temporary-files','workspace',points[3:])]


def backup_cases():
    points=[]
    for cid,name in [('tree','workspace-tree.json'),('legacy','legacy-backup.json')]:
        tree=[T('Close side bar'),T('Toggle explorer')]+([X('Voyages'),X('海岸 Café')] if cid=='tree' else [])
        points.append(cp('import-'+cid,'Rename the initial document Existing note. Import '+name+' as a workspace backup, then export the resulting workspace as a new backup. Leave the explorer visible with imported folders expanded.',
            'The explorer shows the imported documents alongside Existing note and a new workspace backup is downloaded.',[R('Existing note')]+backup_import(name)+backup_export()+tree,text='Existing root note.',checks=[{'type':'backup','part':p} for p in ['folders','names','contents','properties']],carry_download='captured-'+cid+'.json'))
        points.append(cp('roundtrip-'+cid,'Rename the initial document Fresh note. Import captured-'+cid+'.json, the exact backup downloaded in the preceding checkpoint, into this fresh workspace; export the merged workspace as a new backup. Leave the explorer visible with imported folders expanded.',
            'The explorer shows the restored documents alongside Fresh note and Existing note, and a new backup is downloaded.',[R('Fresh note')]+backup_import('captured-'+cid+'.json')+backup_export()+tree,text='Fresh root note.',checks=[{'type':'backup','part':p} for p in ['folders','names','contents','properties']],depends_on=['import-'+cid]))
    # Invalid imports are paired with a positive import and an explicit edit:
    # preserving only an unchanged blank workspace cannot satisfy these points.
    for cid,name in [('truncated','backup-truncated.json'),('wrong-type','backup-null.json')]:
        points.append(cp('invalid-'+cid,'Rename the initial document Original note. Import legacy-backup.json as a workspace backup, then attempt to import '+name+'. Open Legacy note, append ` Still editable.` to its source, and export a backup.',
            'Legacy note remains usable after the invalid backup and includes the appended text; a backup is downloaded.',[R('Original note')]+backup_import('legacy-backup.json')+backup_import(name)+[T('Toggle explorer'),X('Legacy note'),S('# Legacy\n\nAn imported legacy note. Still editable.')]+backup_export(),checks=[{'type':'backup','part':'contents'}]))
    return [episode('gui-backup-structure','backup',points[:4],['workspace-tree.json','legacy-backup.json']),episode('gui-backup-invalid','backup',points[4:],['legacy-backup.json','backup-truncated.json','backup-null.json'])]


def layout_cases():
    doc='\n\n'.join('## Beacon '+str(i).zfill(2)+'\n\nStation '+str(i).zfill(2)+' — a distinct coastal marker.\n\n'+('Sailing toward this harbor. '*6) for i in range(1,36))
    points=[]
    for enabled in [True,False]:
        points.append(cp('sync-'+str(enabled).lower(),'Set scroll synchronization '+('on' if enabled else 'off')+', return both panes to the document start, then scroll the source editor well down the document while leaving the preview untouched.',
            'The source shows later Beacon sections and the preview '+('moves to the corresponding part of the document.' if enabled else 'remains at Beacon 01 near the beginning.'),[{'do':'selection','start':0,'end':0},P('Control+Home'),W()]+([] if enabled else [T('Toggle scroll sync')])+[{'do':'scroll-source','delta':2600},W()],text=doc))
    points.append(cp('focus','Enable focus mode, put the caret at the end of the document, and type ` FOCUS HERE`. Leave the caret on that line.',
        'The active line with FOCUS HERE is placed near the middle of the editor viewing area and remains editable.',[T('Toggle focus mode'),{'do':'selection','start':len(doc),'end':len(doc)},{'op':'type','value':' FOCUS HERE'},W()],text=doc,checks=[SOURCE]))
    points.append(cp('focus-off','Enable focus mode and then turn it off. Put the caret at the end of the document and type ` END HERE`.',
        'The final edited line appears near the bottom of the editor with END HERE, outside centered focus mode.',[T('Toggle focus mode'),T('Toggle focus mode'),{'do':'selection','start':len(doc),'end':len(doc)},{'op':'type','value':' END HERE'},W()],text=doc,checks=[SOURCE]))
    points.append(cp('contents-jump','Use the table of contents to navigate to Beacon 30, then close the contents panel.',
        'The reading preview is at the Beacon 30 section, showing its heading and Station 30 text.',[M('Table of contents'),{'op':'wheel','x':1150,'y':600,'delta_y':5000},{'op':'pointer','action':'click','x':1060,'y':672},T('Close side bar'),W()],text=doc))
    return [episode('gui-layout-long-document','view',points)]


def metadata_cases():
    values=[('scalars','title: Harbor publication\nauthor: Ada Lovelace\nstatus: draft\ndate: 2024-01-02\n'),
            ('lists','tags: [harbor, tide]\ncategories: [travel, sea]\n'),
            ('unicode','title: "海岸 Café"\nauthor: "Zoë \\"Z\\""\n'),
            ('multiline','excerpt: |\n  First harbor line.\n  Second harbor line.\n')]
    points=[]
    for cid,props in values:
        points.append(cp('jekyll-'+cid,'Set these document properties and export the document using the Jekyll HTML template:\n'+fenced(props,'yaml'),
            'The document is exported with its supplied metadata.',property_route(props)+[M('Import/export'),X('Export as HTML'),{'op':'select','target':{'label':'Template'},'value':'jekyllSite'},X('Ok'),{'do':'download','suffix':'.html'}],text='# Publication\n\nA **harbor** report.',checks=[{'type':'download','suffix':'.html','format':'jekyllSite'}]))
    props='title: Properties are separate\ntags: [harbor, tide]\n'
    points.append(cp('markdown','Set these file properties, then export as Markdown:\n'+fenced(props,'yaml'),
        'A Markdown document is downloaded with its source content.',property_route(props)+[M('Import/export'),X('Export as Markdown'),{'do':'download','suffix':'.md'}],text='# Source\n\nBody stays distinct from metadata.',checks=[{'type':'download','suffix':'.md'}]))
    return [episode('gui-metadata-export','exports',points)]


def embedding_cases():
    points=[]
    for cid,text,recipe,goal in [
      ('replace','Original text.',[S('# Changed\n\nA **bold** harbor.')],'Replace the embedded document with this Markdown:\n'+fenced('# Changed\n\nA **bold** harbor.')),
      ('clear','Remove all of this.',[S('')],'Clear all content in the embedded editor.'),
      ('unicode','Original text.',[S('海岸 Café 🌊')],'Replace the embedded document with `海岸 Café 🌊`.'),
    ]:
        points.append(cp(cid,goal,'The embedded editor shows the requested document name or content.',recipe,text=text,
            embedding={'name':'Embedded note','properties':'title: Embedded title\nstatus: draft\n'},checks=[{'type':'embedding','field':k} for k in ['name','text','html','properties']]))
    return [episode('gui-embedding-edit','embedding',points)]


def build():
    episodes=settings_cases()+conversion_cases()+workspace_cases()+backup_cases()+layout_cases()+metadata_cases()+embedding_cases()
    for w in episodes:
        if w['id']=='gui-backup-structure':w['budget'].update(calls=250,tokens=4000000)
        if w['id']=='gui-backup-invalid':w['budget'].update(calls=180,tokens=3000000)
    return episodes
