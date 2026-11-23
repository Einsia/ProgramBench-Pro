"""Cropping, visual comparisons, and validation outcomes."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def build():
 out=[]
 out.append(episode('crop','geometry',[
  taskcp('margin','crop-pdf','Crop single.pdf using the initial crop selection (remove the outer ten percent on every edge), then download it.','single.pdf',[],'Crop & Download',pdf_checks()),
  cp('flat','crop-pdf','Try cropping single.pdf with Flattening Crop enabled, using the initial selection.',[upload('single.pdf'),check('Flattening Crop',contains=True),click('Crop & Download')],[dict(projection('no-download','The failed conversion creates no download.'),requires=['margin/pdf-count'])],['single.pdf'],'The application reports a cropping error.',companions=['margin/pdf-count']),
  taskcp('all','crop-pdf','Crop every page of report.pdf using the initial crop selection, applying it to all pages.','report.pdf',[check('Apply to all pages')],'Crop & Download',pdf_checks()),
 ]))
 pair=[upload('chapter-a.pdf',target={'text':'First PDF','contains':True}),upload('chapter-b.pdf',target={'text':'Second PDF','contains':True})]
 out.append(episode('compare-pdfs','inspection',[
  cp('side-by-side','compare-pdfs','Compare chapter-a.pdf with chapter-b.pdf side by side, then export a split-view PDF of the comparison.',pair+[click('Side-by-Side'),click('Export'),click('Split view'),downloaded()],pdf_checks(text=False),['chapter-a.pdf','chapter-b.pdf']),
  cp('alternating','compare-pdfs','Compare chapter-a.pdf with chapter-b.pdf and export the comparison as alternating pages.',pair+[click('Export'),click('Alternating'),downloaded()],pdf_checks(text=False),['chapter-a.pdf','chapter-b.pdf']),
  cp('left','compare-pdfs','Compare chapter-a.pdf with chapter-b.pdf, then export the left document from the comparison.',pair+[click('Export'),click('Left Document'),downloaded()],pdf_checks(text=False),['chapter-a.pdf','chapter-b.pdf']),
 ]))
 positive=taskcp('valid','extract-pages','Extract page 2 of report.pdf.','report.pdf',[fill('Enter pages to extract','2',contains=True)],'Extract & Download ZIP',pdf_checks())
 neg=projection('no-download','An invalid page range does not create a document.');neg['requires']=['valid/pdf-count']
 out.append(episode('validation','validation',[
  positive,
  cp('outside-range','extract-pages','Try to extract page 99 from the four-page report.pdf.',[upload('report.pdf'),fill('Enter pages to extract','99',contains=True),click('Extract & Download ZIP')],[neg],['report.pdf'],'A visible error explains that the page selection is invalid.',companions=['valid/pdf-count']),
  cp('malformed','extract-pages','Try to open broken.pdf, which is an incomplete PDF file.',[upload('broken.pdf')],[neg],['broken.pdf'],'The application visibly rejects the invalid PDF input.',companions=['valid/pdf-count']),
 ]))
 out.append(episode('stamps','editing',[
  cp('image','add-stamps','Place stamp.png in the blank middle of single.pdf using the image-stamp tool, then save the stamped PDF and reopen the exported file in Form Filler to inspect the result.',[upload('single.pdf'),{'do':'wheel','x':1100,'y':650,'delta_y':780},{'do':'click','target':{'title':'Stamp'}},upload('stamp.png',target={'text':'Upload'}),{'do':'pointer','x':650,'y':460},click('Save Stamped PDF'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}],
     [projection('pdf-count'),projection('pdf-size'),projection('pdf-text'),projection('pdf-mark',input='single.pdf')],['single.pdf','stamp.png'],'A new image stamp is visible on the page and the stamped PDF is downloaded.'),
 ]))
 out.append(episode('heic','conversion',[
  taskcp('convert','heic-to-pdf','Convert chart.heic to PDF using the default settings.','chart.heic',[],'Convert to PDF',pdf_checks(text=False)),
 ]))
 out.append(episode('pdf-json-roundtrip','conversion',[taskcp('import','json-to-pdf','Convert pdf-structure.json, a PDF exported as JSON, back into a PDF.','pdf-structure.json',[],'Convert to PDF')]))
 out.append(episode('mobi','conversion',[taskcp('ebook','mobi-to-pdf','Convert raven.mobi to PDF.','raven.mobi',[],'Convert to PDF',pdf_checks())]))
 morefields=[]
 for key,name in [('radio','Radio'),('list','List'),('button','Button'),('signature','Signature'),('image','Image'),('barcode','Barcode')]:
  morefields.append(cp(key,'form-creator',f'Open single.pdf in the form creator. Add one {name.lower()} field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field.',[upload('single.pdf'),click(name),{'do':'pointer','x':650,'y':600},click('Download PDF Form'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}],pdf_checks(raster=False)+[projection('pdf-base-preserved',input='single.pdf')]+([projection('pdf-barcode-content',tol=15)] if key=='barcode' else [projection('pdf-field-types')]),['single.pdf'],acceptance=f'A new {name.lower()} field is visible and a PDF form is downloaded.'))
 out.append(episode('more-form-fields','forms',morefields))
 out.append(episode('language','preferences',[
  cp('french','index','Switch the application interface to French and leave the tools catalog visible.',[click('English'),click('Français'),{'do':'wait','seconds':1}],[],[],'The tools catalog and interface controls are displayed in French.'),
 ]))
 return out
