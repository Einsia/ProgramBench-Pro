"""PDF annotations and direct text editing through the ordinary application pages."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def annotations():
    cps=[]
    for name,tool in [('rectangle','Rectangle'),('circle','Circle'),('line','Line'),('arrow','Arrow')]:
        cps.append(cp(name,'edit-pdf',f'Open single.pdf in the PDF Editor. Add one {name} annotation in the blank middle area of the page, then download the edited PDF.',[upload('single.pdf'),{'do':'wheel','x':1100,'y':600,'delta_y':600},click('Shapes'),{'do':'click','target':{'aria':tool}},{'do':'drag','x':530,'y':360,'to_x':700,'to_y':440},click('Download Edited PDF'),downloaded('.pdf')],
            [projection('pdf-count'),projection('pdf-size'),projection('pdf-text'),projection('pdf-annotation-details')],['single.pdf'],acceptance=f'A new {name} annotation appears on the page and the edited PDF is downloaded.'))
    return [episode('editor-shapes','editing',cps)]

def replace_text():
    cps=[]
    for key,find,replace,options in [('all','Harbor','Cedar',[]),('whole','Harbor','Bay',[check('Whole word')]),('case','Harbor','Port',[check('Match case')]),('number','42','63',[])]:
        file='search.pdf' if key in {'whole','case'} else 'single.pdf'
        cps.append(cp(key,'edit-pdf-text',f'Open {file} in Edit PDF Text. Replace every occurrence of "{find}" with "{replace}"'+(' with whole-word matching.' if key=='whole' else ' with case-sensitive matching.' if key=='case' else '.')+' Export the edited PDF.',[upload(file),{'do':'click','target':{'title':'Find & replace'}},{'do':'fill','target':{'placeholder':'Find'},'value':find},{'do':'fill','target':{'placeholder':'Replace with'},'value':replace}]+options+[click('Replace All'),click('Export'),downloaded('.pdf')],pdf_checks()+[projection('pdf-text-style')],[file]))
    return [episode('edit-text-replace','editing',cps)]

def text_style():
    cps=[]
    for key,title,value in [('size','Font size','26'),('color','Custom text color','#2244aa')]:
        cps.append(cp(key,'edit-pdf-text',f'Open single.pdf in Edit PDF Text. Select the heading "Harbor Map", set its {key} to {value}, and export.',[upload('single.pdf'),{'do':'select-text-block','x':180,'y':165},{'do':'fill','target':{'title':title},'value':value},{'do':'press','key':'Enter'},click('Export'),downloaded('.pdf')],pdf_checks()+[projection('pdf-text-style',text='Harbor Map')],['single.pdf']))
    for key,title in [('italic','Italic'),('underline','Underline'),('strike','Strikethrough')]:
        cps.append(cp(key,'edit-pdf-text',f'Open single.pdf in Edit PDF Text. Select the heading "Harbor Map", apply {key}, and export.',[upload('single.pdf'),{'do':'select-text-block','x':180,'y':165},{'do':'click','target':{'title':title}},click('Export'),downloaded('.pdf')],pdf_checks()+([projection('pdf-decoration',text='Harbor Map',tol=.08)] if key in {'underline','strike'} else [projection('pdf-text-style',text='Harbor Map')]),['single.pdf']))
    return [episode('edit-text-style','editing',cps)]

def build():return annotations()+replace_text()+text_style()
