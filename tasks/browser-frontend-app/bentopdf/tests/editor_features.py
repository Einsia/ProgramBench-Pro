"""Page organization, bookmark editing and workflow documents."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def organize_more():
    cps=[]
    for name,actions,goal in [
      ('duplicate',[{'do':'click','target':{'title':'Duplicate Page','nth':1}}],'Duplicate page 2 of report.pdf and save the result.'),
      ('delete',[{'do':'click','target':{'title':'Delete Page','nth':1}}],'Delete page 2 of report.pdf in the organizer and save the result.'),
      ('reorder',[fill('Page Order (comma-separated)','4,1,3,2'),click('Apply Order'),{'do':'maybe-ok'}],'Reorder report.pdf to pages 4, 1, 3, 2 and save.'),
      ('repeat-order',[fill('Page Order (comma-separated)','2,4,1,3'),click('Apply Order'),{'do':'wait-text','text':'Pages have been reordered'},{'do':'close-success'},{'do':'click','target':{'title':'Duplicate Page','nth':0}},{'do':'click','target':{'title':'Delete Page','nth':4}}],'Set the page order of report.pdf to 2, 2, 4, 1, repeating page 2, and save.'),
    ]:
        checks=pdf_checks()
        if name=='repeat-order':checks[2]=projection('pdf-text',sequence_from='report.pdf',page_order=[2,2,4,1])
        cps.append(taskcp(name,'organize-pdf',goal,'report.pdf',actions,'Save Changes',checks))
    out=[episode('organizer','organize',cps)]
    cps=[]
    for name,actions,goal in [
      ('rotate-all',[click('Select All'),click('Right')],'Rotate all four pages of report.pdf clockwise and export.'),
      ('duplicate-all',[click('Select All'),click('Duplicate')],'Duplicate all four pages of report.pdf and export the eight-page result.'),
      ('add-blank',[click('Add Blank Page')],'Add a blank page to report.pdf and export the result.'),
      ('undo-redo',[click('Select All'),click('Right'),click('Undo'),click('Redo')],'Rotate all pages of report.pdf clockwise, undo the rotation, redo it, then export.'),
      ('selected',[{'do':'wait-text','text':'Page 4'},{'do':'click','target':{'tag':'button','text':'','nth':1}},click('Download Selected')],'Select only page 2 of report.pdf and download the selected page.'),
    ]:
        end=[] if name=='selected' else [click('Export PDF')]
        cps.append(cp(name,'pdf-multi-tool',goal,[upload('report.pdf',target={'text':'Upload PDFs'})]+actions+end+[downloaded()],pdf_checks(),['report.pdf']))
    out.append(episode('multi-tool','organize',cps));return out

def bookmarks():
    standard=[upload('bookmarks.pdf'),click('Extract Existing Bookmarks'),click('Confirm')]
    out=[]
    cps=[cp('add','bookmark','Add a bookmark named "Harbor overview" pointing to page 1 of report.pdf, then save the PDF.',[upload('report.pdf'),{'do':'fill','target':{'placeholder':'Bookmark title...'},'value':'Harbor overview'},click('Add to Page 1'),click('Save PDF with Bookmarks'),downloaded()],pdf_checks()+[projection('pdf-bookmarks')],['report.pdf'])]
    cps.append(cp('page-target','bookmark','Add a bookmark "Coral station" pointing to page 3 of report.pdf, then save.',[upload('report.pdf'),fill('Go to:',3),click('Go'),{'do':'fill','target':{'placeholder':'Bookmark title...'},'value':'Coral station'},click('Add to Page 3'),click('Save PDF with Bookmarks'),downloaded()],pdf_checks()+[projection('pdf-bookmarks')],['report.pdf']))
    cps.append(cp('extract-save','bookmark','Load the existing bookmarks from bookmarks.pdf into the editor and save the PDF with that hierarchy.',standard+[click('Save PDF with Bookmarks'),downloaded()],pdf_checks()+[projection('pdf-bookmarks')],['bookmarks.pdf']))
    out.append(episode('bookmarks','metadata',cps))
    out.append(episode('bookmark-files','metadata',[
      cp('csv','bookmark','Extract the existing bookmark hierarchy of bookmarks.pdf and export it as CSV.',standard+[click('Export'),click('Export CSV'),downloaded('.csv')],[projection('csv')],['bookmarks.pdf']),
      cp('json','bookmark','Extract the existing bookmark hierarchy of bookmarks.pdf and export it as JSON.',standard+[click('Export'),click('Export JSON'),downloaded('.json')],[projection('bookmark-json')],['bookmarks.pdf']),
    ]))
    return out

def workflow_documents():
    out=[]
    choices=[('rotate','mixed.pdf',[]),('reverse','mixed.pdf',[]),('extract','report.pdf',[]),('delete','report.pdf',[]),('blank','report.pdf',[]),
             ('metadata','report.pdf',[projection('pdf-metadata',fields=['title','author'])]),('nup','mixed.pdf',[]),('watermark','report.pdf',[projection('pdf-mark',input='report.pdf',gray=True)]),
             ('flatten','forms.pdf',[projection('pdf-forms')]),('annotations','annotated.pdf',[projection('pdf-annotations')]),('linearize','report.pdf',[projection('pdf-linearized')]),
             ('booklet','bookmarks.pdf',[]),('background','color.pdf',[]),('sanitize','annotated.pdf',[projection('pdf-annotations'),projection('pdf-links')]),('repair','repairable.pdf',[projection('pdf-repaired')]),('page-numbers','report.pdf',[]),('split','report.pdf',[]),('crop','report.pdf',[])]
    for group in range(3):
        cps=[]
        for key,file,extra in choices[group*6:group*6+6]:
            wf='workflow-'+key+'.json'
            recipe=[click('Import'),upload(wf),{'do':'pointer','x':400,'y':185},upload(file,target={'text':'Upload PDFs'}),click('Run'),downloaded()]
            checks=pdf_checks(text=key not in {'flatten','crop'})+extra
            cps.append(cp(key,'pdf-workflow',f'Import {wf}, supply {file} to its PDF Input node, and run the workflow without changing its processing options.',recipe,checks,[wf,file]))
        out.append(episode('workflow-processing-'+str(group+1),'workflow',cps))
    out.append(episode('workflow-files','workflow',[
      cp('roundtrip','pdf-workflow','Import workflow-rotate.json and export the loaded workflow as JSON.',[click('Import'),upload('workflow-rotate.json'),click('Export'),downloaded('.json')],[projection('workflow-json')],['workflow-rotate.json']),
      cp('crop-roundtrip','pdf-workflow','Import workflow-crop.json and export the loaded workflow as JSON.',[click('Import'),upload('workflow-crop.json'),click('Export'),downloaded('.json')],[projection('workflow-json')],['workflow-crop.json']),
      cp('save-reload','pdf-workflow','Import workflow-rotate.json, save it as a template named "Harbor rotation", reload the page, load that template, then export it.',[click('Import'),upload('workflow-rotate.json'),click('Save'),{'do':'fill','target':{'label':'Template Name'},'value':'Harbor rotation'},click('Save',nth=1),{'do':'reload'},click('Load'),click('Load',nth=1),{'do':'maybe-ok'},click('Export'),downloaded('.json')],[projection('workflow-json')],['workflow-rotate.json']),
    ]))
    return out

def build():return organize_more()+bookmarks()+workflow_documents()
