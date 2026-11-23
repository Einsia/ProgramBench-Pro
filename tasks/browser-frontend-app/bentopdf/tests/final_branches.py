"""Bookmark history, existing fields, radio groups, and visible signing."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def bookmarks():
    start=[upload('bookmarks.pdf'),click('Extract Existing Bookmarks'),click('Confirm')]
    finish=[click('Save PDF with Bookmarks'),downloaded(),{'do':'close-success'},{'do':'reopen-result','path':'/bookmark.html'},click('Extract Existing Bookmarks'),click('Confirm')]
    delete=[{'do':'click','target':{'title':'Delete','nth':0}},click('Confirm')]
    return [episode('bookmark-structure','metadata',[
        cp('destination','bookmark','Change the Introduction bookmark in bookmarks.pdf to point to page 3, retaining the other bookmarks. Save the PDF.',start+[{'do':'click','target':{'title':'Edit','nth':0}},check('Set custom destination'),fill('Page',3),click('Confirm')]+finish,pdf_checks()+[projection('pdf-bookmarks')],['bookmarks.pdf']),
        cp('reorder','bookmark','Move the North Shore bookmark and its child ahead of Introduction in bookmarks.pdf, keeping their existing hierarchy and page targets. Save.',start+[{'do':'drag','x':698,'y':652,'to_x':698,'to_y':561,'via':[[698,630],[698,600],[698,575]]}]+finish,pdf_checks()+[projection('pdf-bookmarks')],['bookmarks.pdf']),
        cp('batch-style','bookmark','Make every bookmark in bookmarks.pdf green and italic using batch editing, then save.',start+[check('Batch Mode',contains=True),check('Introduction Page 1'),click('Select All'),{'do':'select','target':{'option':'Set Color...'},'value':'green'},{'do':'select','target':{'option':'Set Style...'},'value':'italic'}]+finish,pdf_checks()+[projection('pdf-bookmark-style')],['bookmarks.pdf']),
        cp('delete','bookmark','Delete Introduction from the existing bookmarks of bookmarks.pdf and save, preserving the other bookmarks.',start+delete+finish,pdf_checks()+[projection('pdf-bookmarks')],['bookmarks.pdf']),
        cp('undo','bookmark','Delete Introduction from the existing bookmarks of bookmarks.pdf, undo that deletion, then save the restored hierarchy.',start+delete+[click('Undo')]+finish,[dict(x,requires=['delete/pdf-bookmarks']) for x in pdf_checks()+[projection('pdf-bookmarks')]],['bookmarks.pdf'],companions=['delete/pdf-bookmarks']),
    ])]

def forms():
    finish=[click('Download PDF Form'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}]
    return [episode('form-editing','forms',[
        cp('existing','form-creator','Edit the existing visitor field in forms.pdf: set its value to "Ada Finch" and make it read-only. Keep the other fields, save the form and reopen it in Form Filler.',[upload('forms.pdf'),{'do':'pointer','x':700,'y':590},fill('Value','Ada Finch'),check('Read Only')]+finish,[projection('pdf-widget-state',fields=['visitor'],retain_types=True),projection('pdf-base-preserved',input='forms.pdf')],['forms.pdf']),
        cp('multiline','form-creator','Create a text field named notes on single.pdf and enable Multi-line, then save and reopen the form in Form Filler.',[upload('single.pdf'),click('Text'),{'do':'pointer','x':650,'y':600},{'do':'pointer','x':650,'y':600},fill('Field Name','notes'),{'do':'pointer','x':248,'y':763}]+finish,[projection('pdf-widget-state'),projection('pdf-base-preserved',input='single.pdf')],['single.pdf']),
        cp('radio-group','form-creator','Create a radio group named travel on single.pdf with exactly two options, Boat and Bus. Select Bus as the default, save and reopen the form in Form Filler.',[upload('single.pdf'),click('Radio'),{'do':'pointer','x':650,'y':600},{'do':'pointer','x':590,'y':600},fill('Field Name (Group Name)','travel'),fill('Export Value','Boat'),click('Radio'),{'do':'pointer','x':750,'y':700},{'do':'pointer','x':690,'y':700},select('Existing Radio Groups','travel'),fill('Export Value','Bus'),{'do':'pointer','x':248,'y':598}]+finish,[projection('pdf-radio-group'),projection('pdf-base-preserved',input='single.pdf')],['single.pdf']),
    ])]

def graphics():
    return [episode('inserted-graphics','editing',[
        cp('editor-image','edit-pdf','Insert stamp.png as an image in the blank middle of single.pdf using the PDF editor, then download the edited document.',[upload('single.pdf'),{'do':'wheel','x':1100,'y':600,'delta_y':600},click('Annotate'),{'do':'click','target':{'aria':'Stamp'}},{'do':'pointer','x':650,'y':400},upload('stamp.png'),{'do':'wait','seconds':2},{'do':'click','target':{'aria':'Toggle Pointer Mode'}},click('Download Edited PDF'),downloaded()],pdf_checks(raster=False)+[projection('pdf-mark',input='single.pdf'),projection('pdf-base-preserved',input='single.pdf')],['single.pdf','stamp.png']),
        cp('visible-digital','digital-sign-pdf','Digitally sign single.pdf with harbor.p12 (password harbor-pass), reason "Harbor approval". Enable the visible signature using the default signer-name text and first-page placement. Download the signed PDF.',[upload('single.pdf'),upload('harbor.p12',target={'text':'Upload certificate','contains':True}),fill('Certificate Password','harbor-pass'),fill('Reason','Harbor approval'),{'do':'click','target':{'type':'checkbox'}},click('Apply Digital Signature'),downloaded()],pdf_checks()+[projection('pdf-digital-signature'),projection('pdf-added-text',pattern=r'Harbor|Demo|Signer')],['single.pdf','harbor.p12']),
    ])]

def formats():
    return [episode('format-branches','conversion',[
        taskcp('xls','excel-to-pdf','Convert harbor.xls to PDF.','harbor.xls',[],'Convert to PDF'),
        taskcp('msg','email-to-pdf','Convert harbor.msg to PDF, preserving the message headers and body.','harbor.msg',[],'Convert to PDF'),
        taskcp('jpeg2000','image-to-pdf','Convert stamp.jp2 followed by chart.png to one PDF using the default settings.',['stamp.jp2','chart.png'],[],'Convert to PDF',pdf_checks(text=False)),
    ])]

def tables():
    cps=[]
    for key,label in [('csv','CSV'),('json','JSON'),('markdown','Markdown')]:
        cps.append(taskcp(key,'extract-tables',f'Extract the table in quoted-table.pdf as {label}, preserving quoted text, commas and the empty cargo cell.','quoted-table.pdf',[check(label)],'Extract Tables',[projection('table-cells',format=key)]))
    return [episode('table-formats','extraction',cps)]

def xfa():
    return [episode('xfa-forms','forms',[
        cp('fill','form-filler','Open harbor-xfa.pdf, fill Visitor name with "Ada Finch", and save the completed XFA form.',[upload('harbor-xfa.pdf'),{'do':'wheel','x':1200,'y':600,'delta_y':650},fill('Visitor name','Ada Finch'),{'do':'pointer','x':800,'y':350},click('Save & Download Filled Form'),downloaded(),{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}],
           [projection('pdf-xfa-value',field='visitor',value='Ada Finch')],['harbor-xfa.pdf']),
    ])]

def build():return bookmarks()+forms()+graphics()+formats()+tables()+xfa()
