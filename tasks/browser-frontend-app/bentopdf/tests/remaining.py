"""Further format conversions and document operations."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def formats():
 out=[]
 out.append(episode('open-document-formats','conversion',[
  taskcp('odt','odt-to-pdf','Convert report.odt to PDF.','report.odt',[],'Convert to PDF'),
  taskcp('ods','ods-to-pdf','Convert stations.ods to PDF.','stations.ods',[],'Convert to PDF'),
  taskcp('odp','odp-to-pdf','Convert slides.odp to PDF.','slides.odp',[],'Convert to PDF'),
  taskcp('odg','odg-to-pdf','Convert drawing.odg to PDF.','drawing.odg',[],'Convert to PDF'),
  taskcp('powerpoint','powerpoint-to-pdf','Convert harbor.pptx to PDF using the PowerPoint conversion tool.','harbor.pptx',[],'Convert to PDF'),
 ]))
 out.append(episode('more-formats','conversion',[
  taskcp('psd','psd-to-pdf','Convert chart.psd to PDF.','chart.psd',[],'Convert to PDF',pdf_checks(text=False)),
  taskcp('xps','xps-to-pdf','Convert drawing.xps to PDF.','drawing.xps',[],'Convert to PDF',pdf_checks(text=False)),
  taskcp('gif','image-to-pdf','Convert chart.gif to PDF with the default settings.','chart.gif',[],'Convert to PDF',pdf_checks(text=False)),
  taskcp('ppm','image-to-pdf','Convert chart.ppm to PDF with the default settings.','chart.ppm',[],'Convert to PDF',pdf_checks(text=False)),
 ]))
 out.append(episode('export-documents','conversion',[
  taskcp('word','pdf-to-word','Convert report.pdf to a Word DOCX document.','report.pdf',[],'Convert to DOCX',[projection('office-xml',member='word/document.xml'),projection('download-format')]),
  taskcp('excel','pdf-to-excel','Convert the table in table.pdf to Excel.','table.pdf',[],'Convert to Excel',[projection('office-text',texts=['Cedar','Maple','42','17']),projection('download-format')]),
  taskcp('ai','prepare-pdf-for-ai','Extract report.pdf for an AI pipeline using the default format.','report.pdf',[],'Extract for AI',[projection('json-page-text'),projection('download-format')]),
  taskcp('json','pdf-to-json','Export single.pdf to JSON using the default settings.','single.pdf',[],'Convert to JSON',[projection('json-structure'),projection('download-format')]),
 ]))
 return out

def combine():
 out=[]
 out.append(episode('alternate-and-package','organize',[
  cp('alternate','alternate-merge','Select chapter-a.pdf and chapter-b.pdf together, in that order, and interleave their pages. Keep all remaining pages when one input ends.',[upload('chapter-a.pdf',stage=True),upload('chapter-b.pdf'),click('Mix Pages'),downloaded()],pdf_checks()+[projection('pdf-bookmarks')],['chapter-a.pdf','chapter-b.pdf']),
  cp('alternate-labels','alternate-merge','Interleave labels.pdf and chapter-b.pdf, preserving original page labels.',[upload('labels.pdf',stage=True),upload('chapter-b.pdf'),check('Keep original page labels',contains=True),click('Mix Pages'),downloaded()],pdf_checks()+[projection('pdf-labels')],['labels.pdf','chapter-b.pdf']),
  cp('zip','pdf-to-zip','Package chapter-a.pdf and chapter-b.pdf together into a ZIP archive.',[upload('chapter-a.pdf',stage=True),upload('chapter-b.pdf'),click('Create ZIP Archive'),downloaded('.zip')],pdf_checks()+[projection('archive-names')],['chapter-a.pdf','chapter-b.pdf']),
 ]))
 for mode in ['overlay','underlay']:
  out.append(episode('pdf-'+mode,'geometry',[
   cp('all','overlay-pdf',f'Use report.pdf as the base and single.pdf as the {mode}. Apply it to every base page, looping the one-page input.',[upload('report.pdf',target={'text':'Upload base PDF'}),upload('single.pdf',target={'text':'Upload overlay/underlay PDF'}),select('Mode',mode),click('Apply Overlay / Underlay'),downloaded()],pdf_checks(),['report.pdf','single.pdf']),
  ]))
 out.append(episode('blank-removal','organize',[
  cp('detected','remove-blank-pages','Detect blank pages in blank-pages.pdf using the default sensitivity, then remove all detected blank pages.',[upload('blank-pages.pdf'),click('Detect Blank Pages'),click('Remove Selected Blank Pages'),downloaded()],pdf_checks(),['blank-pages.pdf']),
 ]))
 return out

def layer_attachments():
 out=[]
 out.append(episode('edit-attachments','metadata',[
  taskcp('remove-all','edit-attachments','Remove all attachments from attachments.pdf and save the updated PDF.','attachments.pdf',[click('Remove All Attachments')],'Save Changes',pdf_checks()+[projection('pdf-attachments')]),
 ]))
 out.append(episode('layers','editing',[
  cp('add','pdf-layers','Load layers.pdf, add a layer named "Review", and download the modified PDF.',[upload('layers.pdf'),click('Load Layers'),{'do':'wait','seconds':2},{'do':'fill','target':{'placeholder':'Enter new layer name...'},'value':'Review'},click('Add Layer'),click('Download Modified PDF'),downloaded()],pdf_checks()+[projection('pdf-layers')],['layers.pdf']),
  cp('hide','pdf-layers','Load layers.pdf, hide only the Survey markers layer, then download the modified PDF.',[upload('layers.pdf'),click('Load Layers'),{'do':'wait','seconds':2},check('Survey markers',False),click('Download Modified PDF'),downloaded()],pdf_checks(text=False)+[projection('pdf-layer-state')],['layers.pdf']),
 ]))
 return out

def create_forms():
 cps=[]
 for key,name in [('text','Text'),('checkbox','Checkbox'),('dropdown','Dropdown'),('date','Date')]:
  cps.append(cp(key,'form-creator',f'Open single.pdf in the form creator. Add one {name.lower()} field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field.',[upload('single.pdf'),click(name),{'do':'pointer','x':650,'y':600},click('Download PDF Form'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}],pdf_checks(raster=False)+[projection('pdf-field-types'),projection('pdf-base-preserved',input='single.pdf')],['single.pdf'],acceptance=f'A new {name.lower()} field is visible on the page and a PDF form is downloaded.'))
 return [episode('create-forms','forms',cps)]

def build():return formats()+combine()+layer_attachments()+create_forms()
