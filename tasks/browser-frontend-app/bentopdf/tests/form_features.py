"""Form filling and page-level document inspection."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def form_filling():
    cps=[]
    cases=[('name',{'do':'fill','target':{'title':'Visitor name'},'value':'Sam Reed'},'Fill Visitor name with "Sam Reed".'),
           ('date',{'do':'fill','target':{'title':'Visit date'},'value':'2026-01-15'},'Fill Visit date with "2026-01-15".'),
           ('notes',{'do':'fill','target':{'title':'Notes'},'value':'Arriving by boat.\nTwo passengers.'},'Fill Notes with exactly two lines: "Arriving by boat." and "Two passengers.".'),
           ('member',{'do':'check','target':{'title':'Member'},'checked':True},'Check the Member checkbox.'),
           ('destination',{'do':'select','target':{'title':'Destination'},'value':'Maple'},'Choose Maple as the Destination.'),
           ('travel',{'do':'check','target':{'type':'radio','nth':1},'checked':True},'Choose Bus as the Travel mode.')]
    for key,action,goal in cases:
        cps.append(cp(key,'form-filler','Open forms.pdf. '+goal+' Save the filled form as PDF.',[upload('forms.pdf'),{'do':'wheel','x':1100,'y':600,'delta_y':650},action,click('Save & Download Filled Form'),downloaded('.pdf')],[projection('pdf-forms'),projection('pdf-count'),projection('pdf-size'),projection('pdf-raster',tol=16)],['forms.pdf']))
    return [episode('fill-forms','forms',cps)]

def inspect():
    cps=[]
    for key,label in [('points','pt'),('inches','in'),('millimeters','mm'),('pixels','px')]:
        cps.append(cp(key,'page-dimensions',f'Inspect mixed.pdf page dimensions in {key}, then export the measurements as CSV.',[upload('mixed.pdf'),{'do':'select','target':{'option':label},'value':label},click('Export to CSV'),downloaded('.csv')],[projection('csv')],['mixed.pdf']))
    return [episode('page-dimensions','inspection',cps)]

def attachments():
    return [episode('attachments','metadata',[
      cp('add-text','add-attachments','Attach notes.txt to report.pdf and download the PDF with the embedded attachment.',[upload('report.pdf'),upload('notes.txt',target={'text':'Click or drop files to attach','contains':True}),click('Add Attachments'),downloaded()],pdf_checks()+[projection('pdf-attachments')],['report.pdf','notes.txt']),
      cp('add-json','add-attachments','Attach data.json to report.pdf and download the PDF with the embedded attachment.',[upload('report.pdf'),upload('data.json',target={'text':'Click or drop files to attach','contains':True}),click('Add Attachments'),downloaded()],pdf_checks()+[projection('pdf-attachments')],['report.pdf','data.json']),
      cp('extract-batch','extract-attachments','Extract attachments from attachments.pdf and binary-attachments.pdf together, including the embedded PNG.',[upload('attachments.pdf',stage=True),upload('binary-attachments.pdf'),click('Extract Attachments'),downloaded()],[projection('archive'),projection('archive-names'),projection('attachment-bytes')],['attachments.pdf','binary-attachments.pdf']),
    ])]

def table_of_contents():
    return [episode('table-of-contents','metadata',[
      taskcp('default','table-of-contents','Generate a table of contents from bookmarks.pdf with the default settings.','bookmarks.pdf',[],'Generate Table of Contents',pdf_checks()+[projection('pdf-bookmarks')]),
    ])]

def build():return form_filling()+inspect()+attachments()+table_of_contents()
