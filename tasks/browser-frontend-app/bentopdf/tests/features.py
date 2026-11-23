"""Additional document, conversion, security and automation coverage."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def watermarks():
    cps=[]
    for key,pos in [('center','Center'),('top-left','Top Left'),('bottom-right','Bottom Right')]:
        cps.append(taskcp(key,'add-watermark',f'Add the text watermark "HARBOR" at {pos.lower()} on every page of report.pdf, with size 36, opacity 0.6 and angle 0.','report.pdf',[fill('Text','HARBOR'),fill('Font Size',36),fill('Opacity:',.6,contains=True),fill('Angle:',0,contains=True),click(pos)],'Add Watermark',pdf_checks()+[projection('pdf-change',input='report.pdf',tol=.06)]))
    cps.append(taskcp('tiled','add-watermark','Add a tiled text watermark "DRAFT" on report.pdf, using size 32, opacity 0.4 and the default -45 degree angle.','report.pdf',[fill('Text','DRAFT'),fill('Font Size',32),fill('Opacity:',.4,contains=True),click('Tiled')],'Add Watermark',pdf_checks()+[projection('pdf-change',input='report.pdf',tol=.06)]))
    cps.append(taskcp('range','add-watermark','Add the text watermark "REVIEW" only to pages 2-3 of report.pdf, using size 32, angle 0 and opacity 0.8.','report.pdf',[fill('Page Range','2-3'),fill('Text','REVIEW'),fill('Font Size',32),fill('Opacity:',.8,contains=True),fill('Angle:',0,contains=True)],'Add Watermark',pdf_checks()+[projection('pdf-change',input='report.pdf',tol=.06)]))
    return [episode('watermarks','annotation',cps)]

def colors():
    out=[]
    out.append(episode('document-colors','color',[
      taskcp('background','background-color','Change the background of color.pdf to pale blue #cce5ff.','color.pdf',[fill('Background Color','#cce5ff')],'Change Background Color',pdf_checks()+[projection('pdf-text-style')]),
      taskcp('text','text-color','Change all text in color.pdf to green #228833.','color.pdf',[fill('New Text Color','#228833')],'Change Text Color',pdf_checks(text=False)),
      taskcp('invert','invert-colors','Invert the colors in color.pdf.','color.pdf',[],'Invert Colors',pdf_checks(text=False)),
      taskcp('grayscale','pdf-to-greyscale','Convert color.pdf to greyscale.','color.pdf',[],'Convert to Greyscale',pdf_checks(text=False)),
    ]))
    values=[('brightness',25),('contrast',30),('saturation',-70),('hue-shift',45),('temperature',30),('tint',25),('gamma',1.5),('sepia',70)]
    for group,items in [('tone',values[:4]),('balance',values[4:])]:
        out.append(episode('color-'+group,'color',[
          taskcp(name,'adjust-colors',f'On color.pdf, set the {name.replace("-"," ")} adjustment to {value}, leaving other adjustments at their defaults, and apply.','color.pdf',[{'do':'fill','target':{'type':'range','nth':[n for n,_ in values].index(name)},'value':str(value)}],'Apply Color Adjustments',pdf_checks(text=False)+[projection('pdf-color-grid',tol=4)]) for name,value in items]))
    out.append(episode('scanner-effect','color',[
      taskcp('default','scanner-effect','Apply the default scanner effect to color.pdf.','color.pdf',[],'Apply Scanner Effect',pdf_checks(text=False)+[projection('pdf-rasterized')]),
      taskcp('grayscale','scanner-effect','Apply a grayscale scanner effect to color.pdf with the default noise and rotation settings.','color.pdf',[click('Gray')],'Apply Scanner Effect',pdf_checks(text=False)+[projection('pdf-rasterized')]),
    ]))
    return out

def metadata():
    out=[];cps=[]
    for key,label,val in [('title','Title','Harbor Archive'),('author','Author','Ada Finch and Sam Reed'),('subject','Subject','Winter coastal survey'),('keywords','Keywords (comma-separated)','harbor, winter, research'),('creator','Creator','Harbor Studio'),('producer','Producer','Archive Pipeline')]:
        cps.append(taskcp(key,'edit-metadata',f'Set the {label.split(" (")[0].lower()} of report.pdf to "{val}" and save the updated PDF.','report.pdf',[fill(label,val)],'Save Metadata',[projection('pdf-metadata',fields=[key]),projection('pdf-text'),projection('pdf-raster',tol=16),projection('pdf-count')]))
    out.append(episode('metadata-fields','metadata',cps))
    out.append(episode('metadata-cleanup','metadata',[
      taskcp('remove','remove-metadata','Remove metadata from report.pdf.','report.pdf',[],'Remove All Metadata',[projection('pdf-metadata',fields=['title','author','subject','keywords']),projection('pdf-text'),projection('pdf-raster',tol=16),projection('pdf-count')]),
      cp('view','view-metadata','Open report.pdf and inspect its document title, author, subject and keywords.',[upload('report.pdf')],[],['report.pdf'],'The metadata view visibly presents the document title, author, subject and keywords from the input.'),
      cp('copy','view-metadata','Open report.pdf and copy its document metadata as JSON using the application.',[upload('report.pdf'),click('Copy Metadata as JSON',contains=True)],[projection('clipboard-json',fields=['Title','Author','Subject','Keywords'])],['report.pdf'],'The metadata view is populated and the copy operation confirms that metadata was copied.'),
    ]))
    labelcps=[]
    for key,style in [('roman-lower','LowercaseRoman'),('roman-upper','UppercaseRoman'),('letters-lower','LowercaseLetters'),('letters-upper','UppercaseLetters')]:
        labelcps.append(taskcp(key,'add-page-labels',f'Apply {key.replace("-"," ")} page labels to all pages of report.pdf, starting at 1.','report.pdf',[{'do':'select','target':{'option':style},'value':style}],'Add Page Labels',[projection('pdf-labels'),projection('pdf-count'),projection('pdf-text'),projection('pdf-raster',tol=16)]))
    labelcps.append(taskcp('prefix','add-page-labels','Apply decimal page labels with prefix "HBR-" and start value 10 to all pages of report.pdf.','report.pdf',[{'do':'fill','target':{'placeholder':'Optional prefix, e.g. A-'},'value':'HBR-'},{'do':'fill','target':{'type':'number'},'value':'10'}],'Add Page Labels',[projection('pdf-labels'),projection('pdf-count'),projection('pdf-text'),projection('pdf-raster',tol=16)]))
    out.append(episode('page-labels','metadata',labelcps))
    return out

def security():
    out=[]
    out.append(episode('passwords','security',[
      taskcp('encrypt','protect-pdf','Encrypt report.pdf with the opening password "sailboat" and owner password "harbor-owner".','report.pdf',[fill('User Password (Required)','sailboat'),fill('Owner Password (Optional)','harbor-owner')],'Encrypt PDF',pdf_checks()+[projection('pdf-encryption')],password='sailboat'),
      taskcp('user-only','protect-pdf','Encrypt chapter-b.pdf with the opening password "Cedar-2026" and leave the optional owner password empty.','chapter-b.pdf',[fill('User Password (Required)','Cedar-2026')],'Encrypt PDF',pdf_checks()+[projection('pdf-encryption')],password='Cedar-2026'),
      taskcp('decrypt','unlock-pdf','Unlock encrypted.pdf with its password "sailboat" and download the unencrypted PDF.','encrypted.pdf',[fill('Password','sailboat',contains=True)],'Decrypt PDF',pdf_checks()+[projection('pdf-encryption')]),
      taskcp('restrictions','remove-restrictions','Remove restrictions from restricted.pdf. It has no opening password; its owner password is "harbor-owner" if requested.','restricted.pdf',[],'Remove Restrictions',pdf_checks()+[projection('pdf-encryption')]),
    ]))
    cps=[]
    for key,label in [('print','Allow Printing'),('copy','Allow Copying Text'),('modify','Allow Modifying'),('annotate','Allow Annotating'),('forms','Allow Filling Forms'),('assembly','Allow Document Assembly')]:
        cps.append(taskcp(key,'change-permissions',f'Set owner password "harbor-owner" for report.pdf and disable only {label.lower()}, leaving the other permission switches enabled and the opening password empty.','report.pdf',[fill('New Owner Password *','harbor-owner'),check(label,False)],'Change Permissions',[projection('pdf-permissions'),projection('pdf-encryption'),projection('pdf-text'),projection('pdf-raster',tol=16)],password='harbor-owner'))
    out.append(episode('permissions','security',cps))
    out.append(episode('sanitize-flatten','security',[
      taskcp('annotations','remove-annotations','Remove annotations from annotated.pdf.','annotated.pdf',[],'Remove Annotations',[projection('pdf-annotations'),projection('pdf-text'),projection('pdf-raster',tol=16),projection('pdf-count')]),
      taskcp('flatten','flatten-pdf','Flatten the form fields of forms.pdf into static page content.','forms.pdf',[],'Flatten PDF(s)',[projection('pdf-forms'),projection('pdf-count'),projection('pdf-size'),projection('pdf-raster',tol=16)]),
      taskcp('sanitize-annotations','sanitize-pdf','Sanitize annotated.pdf with the default options.','annotated.pdf',[],'Sanitize PDF',[projection('pdf-annotations'),projection('pdf-links'),projection('pdf-metadata',fields=['title','author','subject','keywords']),projection('pdf-text'),projection('pdf-raster',tol=16)]),
      taskcp('sanitize-attachments','sanitize-pdf','Sanitize attachments.pdf with the default options.','attachments.pdf',[],'Sanitize PDF',[projection('pdf-attachments'),projection('pdf-metadata',fields=['title','author']),projection('pdf-text'),projection('pdf-raster',tol=16)]),
    ]))
    return out

def optimize():
    out=[]
    cps=[]
    for key in ['light','balanced','aggressive','extreme']:
        cps.append(taskcp(key,'compress-pdf',f'Compress photo.pdf using the Condense algorithm at the {key} level.','photo.pdf',[select('Compression Level',key)],'Compress PDF',pdf_checks(text=False)+[projection('pdf-image-size'),projection('pdf-compressed',input='photo.pdf'),projection('pdf-image-quality',tol=1.5)]))
    out.append(episode('compression','optimization',cps))
    out.append(episode('optimization','optimization',[
      taskcp('linearize','linearize-pdf','Linearize report.pdf for fast web viewing.','report.pdf',[],'Linearize PDF(s)',pdf_checks()+[projection('pdf-linearized')]),
      taskcp('repair','repair-pdf','Repair the damaged header and cross-reference offsets of repairable.pdf and download the repaired PDF.','repairable.pdf',[],'Repair PDF',pdf_checks()+[projection('pdf-repaired')]),
      taskcp('font-outline','font-to-outline','Convert fonts in report.pdf into outlines.','report.pdf',[],'Convert to Outlines',pdf_checks(text=False)+[projection('pdf-fonts-outlined')]),
      taskcp('deskew','deskew-pdf','Straighten the tilted scan in skewed.pdf using the default deskew settings.','skewed.pdf',[],'Deskew PDF',pdf_checks(text=False)+[projection('pdf-deskew-angle',tol=.75)]),
    ]))
    out.append(episode('rasterize','optimization',[
      taskcp('screen','rasterize-pdf','Rasterize color.pdf at 72 DPI with PNG images.','color.pdf',[select('DPI (Resolution)','72')],'Rasterize PDF',pdf_checks(text=False)+[projection('pdf-rasterized'),projection('pdf-image-size')]),
      taskcp('print','rasterize-pdf','Rasterize color.pdf at 150 DPI with JPEG images.','color.pdf',[select('Image Format','jpeg')],'Rasterize PDF',pdf_checks(text=False)+[projection('pdf-rasterized'),projection('pdf-image-size')]),
      taskcp('gray','rasterize-pdf','Rasterize color.pdf at 72 DPI in grayscale.','color.pdf',[select('DPI (Resolution)','72'),check('Convert to Grayscale')],'Rasterize PDF',pdf_checks(text=False)+[projection('pdf-rasterized'),projection('pdf-image-size')]),
    ]))
    out.append(episode('archival','optimization',[
      taskcp('pdfa1','pdf-to-pdfa','Convert report.pdf using the PDF/A-1b preset.','report.pdf',[{'do':'select','target':{'option':'PDF/A-1b'},'value':'PDF/A-1b'}],'Convert to PDF/A',pdf_checks()+[projection('pdf-archival',part=1)]),
      taskcp('pdfa2','pdf-to-pdfa','Convert report.pdf using the PDF/A-2b preset.','report.pdf',[],'Convert to PDF/A',pdf_checks()+[projection('pdf-archival',part=2)]),
      taskcp('pdfa3','pdf-to-pdfa','Convert report.pdf using the PDF/A-3b preset.','report.pdf',[{'do':'select','target':{'option':'PDF/A-3b'},'value':'PDF/A-3b'}],'Convert to PDF/A',pdf_checks()+[projection('pdf-archival',part=3)]),
    ]))
    return out

def image_exports():
    out=[]
    cps=[]
    for ext,name in [('jpg','JPEG'),('png','PNG'),('webp','WebP'),('bmp','BMP')]:
        cps.append(taskcp(ext,'pdf-to-'+ext,f'Convert every page of chapter-b.pdf to {name} images with default settings.','chapter-b.pdf',[],'Convert',[projection('image-format'),projection('image-size'),projection('image-content',tol=16),projection('archive')]))
    out.append(episode('pdf-images','conversion',cps))
    out.append(episode('image-options','conversion',[
      taskcp('png-scale','pdf-to-png','Convert chapter-b.pdf to PNG images at scale 1.','chapter-b.pdf',[fill('Image Scale',1)],'Convert',[projection('image-format'),projection('image-size'),projection('image-content',tol=16),projection('archive')]),
      taskcp('jpeg-low','pdf-to-jpg','Convert color.pdf to JPEG with image quality 0.3.','color.pdf',[fill('Image Quality',.3)],'Convert',[projection('image-format'),projection('image-size'),projection('image-content',tol=20),projection('archive')]),
      taskcp('webp-low','pdf-to-webp','Convert color.pdf to WebP with image quality 0.4.','color.pdf',[fill('Image Quality',.4)],'Convert',[projection('image-format'),projection('image-size'),projection('image-content',tol=20),projection('archive')]),
      taskcp('cbz','pdf-to-cbz','Convert chapter-b.pdf into a comic-book CBZ archive with the default settings.','chapter-b.pdf',[],'Convert',[projection('image-format'),projection('image-size'),projection('image-content',tol=16),projection('archive')]),
    ]))
    cps=[]
    for name,compression,color in [('lzw','lzw','rgb'),('deflate','deflate','rgb'),('mono','ccittfax4','bw'),('gray','lzw','greyscale')]:
        cps.append(taskcp(name,'pdf-to-tiff',f'Convert color.pdf to TIFF at 72 DPI with {compression} compression and {color} color mode.','color.pdf',[fill('DPI (Resolution)',72),select('Compression',compression),select('Color Mode',color)],'Convert',[projection('image-format'),projection('image-size'),projection('image-content',tol=16),projection('image-frames'),projection('image-compression')]))
    out.append(episode('tiff','conversion',cps))
    return out

def input_conversion():
    out=[];cps=[]
    for ext,tool in [('jpg','jpg'),('png','png'),('webp','webp'),('bmp','bmp'),('tiff','tiff'),('svg','svg')]:
        cps.append(taskcp(ext,tool+'-to-pdf',f'Convert chart.{ext} to PDF using the default settings.','chart.'+ext,[],'Convert to PDF',pdf_checks(text=False)))
    out.append(episode('images-to-pdf','conversion',cps))
    out.append(episode('documents-to-pdf','conversion',[
      taskcp('docx','word-to-pdf','Convert report.docx to PDF.','report.docx',[],'Convert to PDF'),
      taskcp('rtf','rtf-to-pdf','Convert note.rtf to PDF.','note.rtf',[],'Convert to PDF'),
      taskcp('xlsx','excel-to-pdf','Convert stations.xlsx to PDF.','stations.xlsx',[],'Convert to PDF'),
      taskcp('csv','csv-to-pdf','Convert data.csv to PDF.','data.csv',[],'Convert to PDF'),
      taskcp('email','email-to-pdf','Convert mail.eml to PDF with the default settings.','mail.eml',[],'Convert to PDF'),
    ]))
    out.append(episode('ebooks-to-pdf','conversion',[
      taskcp('epub','epub-to-pdf','Convert book.epub to PDF.','book.epub',[],'Convert to PDF'),
      taskcp('fb2','fb2-to-pdf','Convert book.fb2 to PDF.','book.fb2',[],'Convert to PDF'),
      taskcp('comic','cbz-to-pdf','Convert comic.cbz to PDF.','comic.cbz',[],'Convert to PDF',pdf_checks(text=False)),
      taskcp('xml','xml-to-pdf','Convert data.xml to a PDF document.','data.xml',[],'Convert to PDF'),
    ]))
    cps=[]
    for key,font,size,paper in [('default','helv',12,'A4'),('courier','cour',16,'Letter'),('times','times',18,'A5'),('tiro','tiro',14,'Legal')]:
        cps.append(taskcp(key,'txt-to-pdf',f'Convert notes.txt to PDF using font {font}, size {size} and {paper} paper.','notes.txt',[select('Font Family',font),fill('Font Size',size),select('Page Size',paper)],'Create PDF',pdf_checks()+[projection('pdf-text-style')]))
    out.append(episode('text-to-pdf','conversion',cps))
    out.append(episode('markdown','conversion',[
      cp('document','markdown-to-pdf','Import notes.md into the Markdown editor and export it as PDF.',[upload('notes.md',target={'text':'Upload'}),click('Export PDF'),downloaded()],pdf_checks(text=False)+[projection('pdf-word-layout',tol=2)],['notes.md']),
      cp('typed','markdown-to-pdf','Replace the Markdown with the exact text below and export as PDF.\n```markdown\n# Cedar Harbor\n\n**42 boats** arrived at noon.\n\n- Timber\n- Grain\n```',[{'do':'fill','target':{'tag':'textarea'},'value':'# Cedar Harbor\n\n**42 boats** arrived at noon.\n\n- Timber\n- Grain\n'},click('Export PDF'),downloaded()],pdf_checks(text=False)+[projection('pdf-word-layout',tol=2)],[]),
    ]))
    return out

def extraction():
    out=[]
    out.append(episode('extract-text','extraction',[
      taskcp('text','pdf-to-text','Extract plain text from report.pdf.','report.pdf',[],'Extract Text',[projection('text'),projection('download-format')]),
      taskcp('batch','pdf-to-text','Extract text from chapter-a.pdf and chapter-b.pdf together.',['chapter-a.pdf','chapter-b.pdf'],[],'Extract Text',[projection('text'),projection('archive')]),
      taskcp('markdown','pdf-to-markdown','Convert report.pdf into Markdown.','report.pdf',[],'Convert to Markdown',[projection('text-contains',texts=['Cedar','Bluewater','Coral','Driftwood']),projection('download-format')]),
      taskcp('svg','pdf-to-svg','Convert each page of chapter-b.pdf to SVG.','chapter-b.pdf',[],'Convert to SVG',[projection('archive'),projection('svg-content',tol=12)]),
    ]))
    out.append(episode('ocr','extraction',[
      cp('english-text','ocr-pdf','Run English OCR on scan.pdf with default resolution, then download the recognized text.',[upload('scan.pdf'),check('English'),click('Start OCR'),{'do':'wait','seconds':3},click('Download as .txt'),downloaded('.txt')],[projection('text-contains',texts=['HARBOR','2026','Cedar','42']),projection('download-format')],['scan.pdf']),
      cp('searchable','ocr-pdf','Run English OCR on scan.pdf, then download the searchable PDF.',[upload('scan.pdf'),check('English'),click('Start OCR'),{'do':'wait','seconds':3},click('Download Searchable PDF',contains=True),downloaded('.pdf')],pdf_checks()+[projection('pdf-rasterized')],['scan.pdf']),
    ]))
    out.append(episode('extract-data','extraction',[
      cp('images','extract-images','Extract the embedded images from color.pdf and download all extracted images as a ZIP.',[upload('color.pdf'),click('Extract Images'),click('OK'),click('Download All (ZIP)'),downloaded('.zip')],[projection('image-size'),projection('image-content',tol=16),projection('archive')],['color.pdf']),
      taskcp('tables','extract-tables','Extract the table from table.pdf with the default output format.','table.pdf',[],'Extract Tables',[projection('text-contains',texts=['Cedar','42','Maple','17']),projection('archive')]),
      taskcp('csv','pdf-to-csv','Convert the table in table.pdf to CSV.','table.pdf',[],'Convert to CSV',[projection('text-contains',texts=['Cedar','42','Maple','17']),projection('archive')]),
      taskcp('attachments','extract-attachments','Extract both embedded attachments from attachments.pdf.','attachments.pdf',[],'Extract Attachments',[projection('archive'),projection('archive-names'),projection('text-contains',texts=['Pier inspection: complete.','"north":3'])]),
    ]))
    return out

def build():return watermarks()+colors()+metadata()+security()+optimize()+image_exports()+input_conversion()+extraction()
