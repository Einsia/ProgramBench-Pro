"""Behavioral PDF episodes. Inputs and controls are exercised through the common runtime."""
from copy import deepcopy

def click(text,**kw):return {'do':'click','target':{'text':text,**kw}}
def fill(label,value,**kw):return {'do':'fill','target':{'label':label,**kw},'value':str(value)}
def select(label,value,**kw):return {'do':'select','target':{'label':label,**kw},'value':value}
def check(label,checked=True,**kw):return {'do':'check','target':{'label':label,**kw},'checked':checked}
def upload(file,**kw):return {'do':'upload','file':file,**kw}
def downloaded(suffix=None):return {'do':'download',**({'suffix':suffix} if suffix else {})}
def projection(kind,requirement=None,**kw):
    descriptions={
      'pdf-count':'Output documents contain the requested number and grouping of pages.',
      'pdf-size':'Effective output page dimensions match the requested transformation.',
      'pdf-text':'The output retains or transforms the page text in the requested order.',
      'pdf-text-set':'The output contains the expected text on each page.',
      'pdf-raster':'The output preserves the relevant text and graphical content at the resulting positions.',
      'pdf-bookmarks':'The resulting bookmark hierarchy and page targets match the operation.',
      'pdf-labels':'Output page labels match the requested numbering.',
      'archive':'The output archive contains the requested files and formats.',
      'image-size':'Output images have the requested pixel dimensions.',
      'image-format':'Output images use the requested encoding.',
      'image-content':'Output images preserve the expected page appearance.',
    }
    return {'check':{'kind':kind,**kw},'requirement':requirement or descriptions.get(kind,kind)}
def pdf_checks(text=True,raster=True):
    return [projection('pdf-count'),projection('pdf-size',tol=1.5)]+([projection('pdf-text')] if text else [])+([projection('pdf-raster',tol=16)] if raster else [])
def cp(cid,path,goal,recipe,checks,files,acceptance=None,**kw):
    return {'id':cid,'path':'/'+path+'.html','goal':goal,'recipe':recipe,'checks':checks,'files':files,
            'acceptance':acceptance or 'The requested operation is completed and its new output file is available in the download list.',**kw}
def taskcp(cid,page,goal,file,actions,button,checks=None,suffix=None,**kw):
    files=[file] if isinstance(file,str) else list(file)
    ups=[upload(f,add=i>0) for i,f in enumerate(files)]
    download=downloaded(suffix)
    if page in {'word-to-pdf','excel-to-pdf','powerpoint-to-pdf','rtf-to-pdf','odt-to-pdf','ods-to-pdf','odp-to-pdf','odg-to-pdf'}:download['timeout']=600
    return cp(cid,page,goal,ups+actions+[click(button),download],pdf_checks() if checks is None else checks,files,**kw)
def episode(wid,feature,cps):
    checkpoints=[]
    files=sorted({f for c in cps for f in c['files']})
    for c in cps:
        c=deepcopy(c);checks=c.pop('checks');c.pop('files');acceptance=c.pop('acceptance')
        points=[{'id':wid+'/'+c['id']+'/visible','channel':'frontend','method':'agent','requirement':acceptance}]
        for i,p in enumerate(checks):
            name=p.get('name',p['check']['kind'])
            if any(a['id']==wid+'/'+c['id']+'/'+name for a in points):name+=str(i+1)
            a={'id':wid+'/'+c['id']+'/'+name,'channel':'backend','method':'program','requirement':p['requirement'],'check':p['check']}
            if p.get('requires'):a['requires']=[wid+'/'+r for r in p['requires']]
            points.append(a)
        if c.get('companions'):points[0]['requires']=[wid+'/'+r for r in c.pop('companions')]
        c['assertions']=points;checkpoints.append(c)
    n=len(cps)
    return {'id':wid,'feature':feature,'execution':'gui','initial_state':'Fresh application and browser profile. Each independent checkpoint opens its stated tool page with no file loaded.',
            'setup':[],'inputs':{'files':files},'session':'Each goal begins on its tool page. Upload the exact named input files using the visible interface, set the requested options, and produce the requested result. Page numbers are one-based. Do not substitute other inputs. Downloaded files appear in the observation. Use any equivalent visible route.',
            'allowed_equivalents':['Different wording, controls, layouts and equivalent visible operation routes are accepted.','Generated filenames are incidental unless the goal explicitly supplies one.'],
            'forbidden_bypasses':['Do not modify an input file, invent a replacement document or recreate a missing processing tool by hand.'],
            'budget':{'calls':40+55*n,'tokens':500000+1000000*n,'seconds':450+400*n},'checkpoints':checkpoints}

def organize():
    out=[]
    out.append(episode('merge','organize',[
      taskcp('documents','merge-pdf','Merge chapter-a.pdf followed by chapter-b.pdf into one PDF, using all pages.', ['chapter-a.pdf','chapter-b.pdf'],[],'Merge PDFs',pdf_checks()+[projection('pdf-bookmarks')]),
      taskcp('ranges','merge-pdf','Merge pages 2-3 of chapter-a.pdf followed by page 1 of chapter-b.pdf into one PDF.', ['chapter-a.pdf','chapter-b.pdf'],[{'do':'fill','target':{'placeholder':'Leave blank for all pages','nth':0},'value':'2-3'},{'do':'fill','target':{'placeholder':'Leave blank for all pages','nth':1},'value':'1'}],'Merge PDFs',pdf_checks()+[projection('pdf-bookmarks')]),
      taskcp('labels','merge-pdf','Merge labels.pdf followed by chapter-b.pdf and preserve original page labels.', ['labels.pdf','chapter-b.pdf'],[check('Keep original page labels',contains=True)],'Merge PDFs',pdf_checks()+[projection('pdf-labels')]),
      taskcp('fonts','merge-pdf','Merge font-1.pdf and font-2.pdf with duplicate-font removal enabled.', ['font-1.pdf','font-2.pdf'],[check('Remove duplicate fonts')],'Merge PDFs',pdf_checks()+[projection('pdf-font-reuse')]),
    ]))
    out.append(episode('split','organize',[
      taskcp('combined-range','split-pdf','From report.pdf, extract pages 1-2 and 4 into one combined PDF.','report.pdf',[fill('Page Range','1-2,4')],'Split PDF'),
      taskcp('separate-ranges','split-pdf','Split report.pdf into one PDF for pages 1-2 and another for page 4, delivered together.','report.pdf',[fill('Page Range','1-2,4'),check('One PDF per range')],'Split PDF',pdf_checks()+[projection('archive')]),
      taskcp('all-pages','split-pdf','Split every page of mixed.pdf into its own PDF.','mixed.pdf',[select('Split Mode','all')],'Split PDF',pdf_checks()+[projection('archive')]),
      taskcp('even-odd','split-pdf','Extract the even-numbered pages of report.pdf into a new PDF.','report.pdf',[select('Split Mode','even-odd'),check('Even Pages')],'Split PDF',pdf_checks()),
      taskcp('bookmarks-all','split-pdf','Split bookmarks.pdf at bookmarks from every level, including the nested bookmarks.','bookmarks.pdf',[select('Split Mode','bookmarks'),select('Bookmark Level','all')],'Split PDF',pdf_checks()+[projection('archive')]),
      taskcp('bookmarks','split-pdf','Split bookmarks.pdf at its top-level bookmarks.','bookmarks.pdf',[select('Split Mode','bookmarks'),select('Bookmark Level','0')],'Split PDF',pdf_checks()+[projection('archive')]),
    ]))
    out.append(episode('extract-delete','organize',[
      taskcp('extract','extract-pages','Extract pages 2 and 4 from report.pdf using the Extract Pages tool.','report.pdf',[fill('Enter pages to extract','2,4',contains=True)],'Extract & Download ZIP',pdf_checks()+[projection('archive')]),
      taskcp('extract-range','extract-pages','Extract pages 2-5 from mixed.pdf.','mixed.pdf',[fill('Enter pages to extract','2-5',contains=True)],'Extract & Download ZIP',pdf_checks()+[projection('archive')]),
      taskcp('delete','delete-pages','Delete pages 2 and 4 from report.pdf and download the remainder.','report.pdf',[fill('Enter pages to delete','2,4',contains=True)],'Delete Pages & Download'),
      taskcp('delete-range','delete-pages','Delete pages 2-4 from mixed.pdf.','mixed.pdf',[fill('Enter pages to delete','2-4',contains=True)],'Delete Pages & Download'),
      taskcp('reverse','reverse-pages','Reverse the page order of mixed.pdf.','mixed.pdf',[],'Reverse Pages'),
    ]))
    out.append(episode('rotate','organize',[
      taskcp('clockwise','rotate-pdf','Rotate all pages of mixed.pdf clockwise by 90 degrees.','mixed.pdf',[click('Right')],'Apply Rotations'),
      taskcp('counterclockwise','rotate-pdf','Rotate all pages of report.pdf counter-clockwise by 90 degrees.','report.pdf',[click('Left')],'Apply Rotations'),
      taskcp('half-turn','rotate-pdf','Rotate all pages of report.pdf by 180 degrees.','report.pdf',[click('Right'),click('Right')],'Apply Rotations'),
      taskcp('custom-angle','rotate-custom','Rotate all pages of report.pdf by 30 degrees using custom rotation.','report.pdf',[{'do':'fill','target':{'type':'number','nth':0},'value':'30'},click('Apply to All')],'Apply Rotations'),
      taskcp('custom-negative','rotate-custom','Rotate all pages of single.pdf by -15 degrees using custom rotation.','single.pdf',[{'do':'fill','target':{'type':'number','nth':0},'value':'-15'},click('Apply to All')],'Apply Rotations'),
    ]))
    out.append(episode('blank-duplex','organize',[
      taskcp('blank-front','add-blank-page','Insert two blank pages before the first page of report.pdf.','report.pdf',[fill('Insert after page',0),fill('Number of blank pages',2)],'Add Blank Pages'),
      taskcp('blank-middle','add-blank-page','Insert one blank page after page 2 of mixed.pdf.','mixed.pdf',[fill('Insert after page',2)],'Add Blank Pages'),
      taskcp('blank-end','add-blank-page','Append three blank pages after page 4 of report.pdf.','report.pdf',[fill('Insert after page',4),fill('Number of blank pages',3)],'Add Blank Pages'),
      taskcp('duplex-reversed','duplex-collate','Collate report.pdf as a duplex scan with the front block ending after page 2 and the back block reversed.','report.pdf',[fill('Split after page',2)],'Collate PDF'),
      taskcp('duplex-kept','duplex-collate','Collate report.pdf as a duplex scan split after page 2, keeping the back block in its existing order.','report.pdf',[fill('Split after page',2),select('Back block order','keep')],'Collate PDF'),
    ]))
    return out

def geometry():
    out=[]
    out.append(episode('n-up','geometry',[
      taskcp('two','n-up-pdf','Place two pages per sheet from report.pdf on Letter paper, with the default automatic orientation.','report.pdf',[select('Pages per Sheet','2')],'Create N-Up PDF'),
      taskcp('four-landscape','n-up-pdf','Place four pages per sheet from mixed.pdf on A4 paper in landscape orientation.','mixed.pdf',[select('Output Page Size','A4'),select('Orientation','landscape')],'Create N-Up PDF'),
      taskcp('nine','n-up-pdf','Place nine pages per sheet from mixed.pdf on A3 paper.','mixed.pdf',[select('Pages per Sheet','9'),select('Output Page Size','A3')],'Create N-Up PDF'),
      taskcp('borders','n-up-pdf','Create a four-up PDF from report.pdf on Letter paper with borders around the placed pages.','report.pdf',[check('Add Border')],'Create N-Up PDF',pdf_checks()+[projection('pdf-line-layout',tol=2),projection('pdf-word-layout',tol=2)]),
      taskcp('no-margins','n-up-pdf','Create a four-up PDF from report.pdf on Letter paper with margins disabled.','report.pdf',[check('Add Margins',False)],'Create N-Up PDF',pdf_checks()+[projection('pdf-word-layout',tol=2),projection('pdf-line-layout',tol=2)]),
    ]))
    sizecps=[]
    for name,size,orientation in [('a4','A4','portrait'),('letter','Letter','landscape'),('legal','Legal','portrait'),('a3','A3','landscape'),('a5','A5','auto')]:
        sizecps.append(taskcp(name,'fix-page-size',f'Resize all pages of mixed.pdf to {size}, using {orientation} orientation and Fit mode.','mixed.pdf',[select('Target Page Size',size),select('Orientation',orientation)],'Fix Page Size'))
    sizecps.append(taskcp('fill','fix-page-size','Resize all pages of mixed.pdf to A4 portrait using Fill (Crop) mode.','mixed.pdf',[select('Orientation','portrait'),check('Fill (Crop) Fills the page, may crop content.')],'Fix Page Size',pdf_checks(text=False)))
    out.append(episode('page-size','geometry',sizecps))
    out.append(episode('divide-combine','geometry',[
      taskcp('vertical','divide-pages','Divide every page of report.pdf into left and right halves.','report.pdf',[],'Divide Pages',pdf_checks(text=False)),
      taskcp('horizontal','divide-pages','Divide every page of report.pdf into top and bottom halves.','report.pdf',[select('Split Direction','horizontal')],'Divide Pages',pdf_checks(text=False)),
      taskcp('selected','divide-pages','Divide only pages 2-3 of report.pdf into left and right halves, keeping other pages.','report.pdf',[fill('Pages to Divide','2-3')],'Divide Pages',pdf_checks(text=False)),
      taskcp('combine-vertical','combine-single-page','Combine all pages of mixed.pdf into one vertical continuous page with zero spacing.','mixed.pdf',[],'Combine Pages',pdf_checks(text=False)),
      taskcp('combine-horizontal','combine-single-page','Combine all pages of report.pdf into one horizontal page with 20 pixels of spacing and separator lines.','report.pdf',[select('Layout Direction','horizontal'),fill('Spacing (pixels)',20),check('Add Separator Lines')],'Combine Pages',pdf_checks(text=False)),
    ]))
    out.append(episode('poster','geometry',[
      taskcp('two','posterize-pdf','Posterize single.pdf into one row and two columns on A4 output pages.','single.pdf',[],'Posterize PDF',pdf_checks(text=False)+[projection('pdf-color-geometry',tol=2)]),
      taskcp('four','posterize-pdf','Posterize single.pdf into two rows and two columns on Letter pages.','single.pdf',[fill('Rows',2),select('Page Size','Letter')],'Posterize PDF',pdf_checks(text=False)),
      taskcp('overlap','posterize-pdf','Posterize single.pdf into two columns on A4 pages with 18 points of overlap.','single.pdf',[fill('Overlap (for assembly)',18)],'Posterize PDF',pdf_checks(text=False)+[projection('pdf-color-geometry',tol=2)]),
      taskcp('selected','posterize-pdf','Posterize only page 2 of report.pdf into two rows and one column on A5 pages.','report.pdf',[fill('Rows',2),fill('Columns',1),select('Page Size','A5'),fill('Page Range (optional)','2')],'Posterize PDF',pdf_checks(text=False)),
    ]))
    out.append(episode('booklet','geometry',[
      taskcp('standard','pdf-booklet','Create a 1×2 booklet from report.pdf on Letter paper with no pre-rotation.','report.pdf',[click('Generate Preview')],'Create Booklet',pdf_checks()+[projection('pdf-word-layout',tol=2)]),
      taskcp('a4','pdf-booklet','Create a 1×2 booklet from bookmarks.pdf on A4 paper.','bookmarks.pdf',[select('Paper Size','A4'),click('Generate Preview')],'Create Booklet'),
      cp('clockwise','pdf-booklet','Preview report.pdf as a Letter booklet with pages pre-rotated clockwise by 90 degrees.',[upload('report.pdf'),check('Rotate clockwise (90°)'),click('Generate Preview'),{'do':'wheel','x':1100,'y':650,'delta_y':550}],[],['report.pdf'],'The booklet preview shows the pages turned sideways with the requested pre-rotation.'),
      taskcp('four-up','pdf-booklet','Create a 2×2 booklet layout from bookmarks.pdf on A3 paper.','bookmarks.pdf',[select('Paper Size','A3'),check('2×2'),click('Generate Preview')],'Create Booklet'),
    ]))
    return out

def add_text():
    out=[]
    num=[]
    for key,pos in [('bottom-center','bottom-center'),('top-left','top-left'),('top-right','top-right'),('bottom-right','bottom-right')]:
        num.append(taskcp(key,'page-numbers',f'Add page numbers to report.pdf at {key.replace("-"," ")}, with the default font and number-only format.','report.pdf',[select('Position',pos)],'Add Page Numbers',pdf_checks()+[projection('pdf-number-layout',tol=2)]))
    num.append(taskcp('total','page-numbers','Add bottom-center page numbers to report.pdf in the format current page / total pages, with 18-point text colored #cc2222.','report.pdf',[select('Format','page_x_of_y'),fill('Font Size',18),fill('Color','#cc2222')],'Add Page Numbers',pdf_checks()+[projection('pdf-text-style',margin_only=True,tol=1.5),projection('pdf-number-layout',tol=2)]))
    out.append(episode('page-numbers','annotation',num))
    headers=[]
    for label,text in [('Header Left','Harbor Survey'),('Header Center','Cedar Station'),('Header Right','Archive Copy'),('Footer Left','Prepared by Ada'),('Footer Center','Internal Review'),('Footer Right','End of Notes')]:
        headers.append(taskcp(label.lower().replace(' ','-'),'header-footer',f'Add the text "{text}" in the {label.lower()} of every page in report.pdf.','report.pdf',[fill(label,text)],'Add Header & Footer',pdf_checks()+[projection('pdf-text-position',word=text.split()[0],tol=3)]))
    out.append(episode('header-footer','annotation',headers))
    out.append(episode('header-bates','annotation',[
      taskcp('selected','header-footer','Add "Harbor Survey" in the header center and "Archive Copy" in the footer right of only pages 2-3 of report.pdf, using size 16 and blue #2244aa.','report.pdf',[fill('Page Range (optional)','2-3'),fill('Font Size',16),fill('Font Color','#2244aa'),fill('Header Center','Harbor Survey'),fill('Footer Right','Archive Copy')],'Add Header & Footer',pdf_checks()+[projection('pdf-text-style',text='Harbor Survey',pages=[1,2],margin_only=True)]),
      taskcp('bates','bates-numbering','Add Bates numbers to report.pdf, starting from 125 with the default six-digit style.','report.pdf',[fill('Bates Starts From',125)],'Apply Bates Numbers',pdf_checks()+[projection('pdf-added-text',pattern=r'00012[5-8]')]),
      taskcp('bates-batch','bates-numbering','Add sequential Bates numbers across chapter-a.pdf and chapter-b.pdf, starting at 97 and using the four-digit Bates style.',['chapter-a.pdf','chapter-b.pdf'],[select('Select Style','bates-4'),fill('Bates Starts From',97)],'Apply Bates Numbers',pdf_checks()+[projection('archive')]),
      taskcp('bates-custom','bates-numbering','Number report.pdf using the custom Bates template "HBR-[BATES]-[PAGE]", starting at 10, placed in the header right with Courier font at 14 points.','report.pdf',[select('Select Style','custom'),fill('Customize Style','HBR-[BATES]-[PAGE]'),fill('Bates Starts From',10),select('Position','top-right'),select('Font','Courier'),fill('Font Size',14)],'Apply Bates Numbers',pdf_checks()+[projection('pdf-text-style',text='HBR')]),
    ]))
    return out

def build():
    return organize()+geometry()+add_text()
