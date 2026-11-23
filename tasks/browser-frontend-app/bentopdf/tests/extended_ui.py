"""Editing, persistence, and file round trips exposed by normal product controls."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def viewer():
    start=[upload('single.pdf'),{'do':'wheel','x':1200,'y':600,'delta_y':650}]
    finish=[{'do':'click','target':{'title':'Save'}},downloaded('.pdf')]
    result=episode('viewer-annotations','editing',[
        cp('highlight','form-filler','In the viewer, highlight the word "Harbor" in the heading of single.pdf in yellow, then save the PDF.',start+[{'do':'click','target':{'title':'Highlight'}},{'do':'drag','x':344,'y':193,'to_x':450,'to_y':193}]+finish,
           pdf_checks(raster=False)+[projection('pdf-base-preserved',input='single.pdf'),projection('pdf-highlight-text')],['single.pdf']),
        cp('blue-highlight','form-filler','Highlight the word "Harbor" in the heading of single.pdf in blue, then save.',start+[{'do':'click','target':{'title':'Highlight'}},{'do':'click','target':{'title':'Blue'}},{'do':'drag','x':344,'y':193,'to_x':450,'to_y':193}]+finish,
           pdf_checks(raster=False)+[projection('pdf-base-preserved',input='single.pdf'),projection('pdf-highlight-text')],['single.pdf']),
        cp('search','form-filler','Find the word "Harbor" in single.pdf and leave the search matches visible.',start+[{'do':'click','target':{'title':'Find in Document'}},{'do':'fill','target':{'placeholder':'Find in document…'},'value':'Harbor'},{'do':'press','key':'Enter'}],[],['single.pdf'],'The viewer reports the matching occurrences of Harbor and highlights a match.'),
    ])
    result['budget'].update(calls=240,tokens=4000000)
    return [result]

def text_editing():
    base=[upload('search.pdf'),{'do':'click','target':{'title':'Find & replace'}},{'do':'fill','target':{'placeholder':'Find'},'value':'Harbor'},{'do':'fill','target':{'placeholder':'Replace with'},'value':'Cedar'}]
    return [episode('text-edit-history','editing',[
        cp('single','edit-pdf-text','Replace just the first match of "Harbor" with "Cedar" in search.pdf, using case-sensitive search, and export.',base+[check('Match case'),click('Replace'),click('Export'),downloaded()],pdf_checks(),['search.pdf']),
        cp('undo','edit-pdf-text','Replace every exact-case "Harbor" with "Cedar" in search.pdf, then undo the replacement and export the restored document.',base+[check('Match case'),click('Replace All'),{'do':'press','key':'Control+Z'},click('Export'),downloaded()],
           [dict(p,requires=['single/pdf-text']) for p in pdf_checks()],['search.pdf'],companions=['single/pdf-text']),
    ])]

def form_roundtrip():
    create=[upload('single.pdf'),click('Text'),{'do':'pointer','x':650,'y':600},{'do':'pointer','x':650,'y':600},fill('Field Name','visitor'),fill('Tooltip / Help Text','Visitor')]
    return [episode('form-roundtrip','forms',[
        cp('fill-created','form-creator','Create a text field named visitor (tooltip Visitor) on single.pdf. Save the form, reopen its download in Form Filler, enter "Ada Finch" in that field and save the filled form.',create+[click('Download PDF Form'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650},{'do':'fill','target':{'title':'Visitor'},'value':'Ada Finch'},click('Save & Download Filled Form'),downloaded(),{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}],
           [projection('pdf-field-value',field='visitor',value='Ada Finch'),projection('pdf-base-preserved',input='single.pdf')],['single.pdf']),
        cp('blank','form-creator','Create a new A5 PDF form with two pages, add one text field on the second page, and download it.',[click('Create Blank PDF'),select('Page Size:','a5'),click('Start Creating'),click('Add Page'),click('Text'),{'do':'pointer','x':650,'y':600},click('Download PDF Form'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}],
           [projection('pdf-count'),projection('pdf-size'),projection('pdf-widget-pages')],[],'The saved A5 document opens with two pages.'),
    ])]

def template_lifecycle():
    setup=[click('Import'),upload('workflow-rotate.json'),click('Save'),fill('Template Name','Harbor rotation'),click('Save',nth=1),{'do':'close-success'}]
    return [episode('workflow-templates','workflow',[
        cp('restart','pdf-workflow','Import workflow-rotate.json and save it as "Harbor rotation". Restart the application, reopen Workflow Builder, load that template and export it.',setup+[{'do':'restart'},{'do':'open','path':'/pdf-workflow.html'},click('Load'),click('Load',nth=1),{'do':'close-success'},click('Export'),downloaded('.json')],[projection('workflow-json')],['workflow-rotate.json']),
        cp('delete','pdf-workflow','Import workflow-rotate.json and save it as "Harbor rotation", then delete that saved template. Leave the template list open.',setup+[click('Load'),{'do':'pointer','x':818,'y':445},{'do':'close-success'}],[],['workflow-rotate.json'],'The template list no longer contains Harbor rotation.'),
    ])]

def compare_filters():
    pair=[upload('chapter-a.pdf',target={'text':'First PDF','contains':True}),upload('chapter-b.pdf',target={'text':'Second PDF','contains':True})]
    return [episode('comparison-navigation','inspection',[
        cp('search','compare-pdfs','Compare chapter-a.pdf and chapter-b.pdf. Search the change list for "Alpha" and leave its matching change visible.',pair+[{'do':'fill','target':{'placeholder':'Search changes...'},'value':'Alpha'}],[],['chapter-a.pdf','chapter-b.pdf'],'The change list shows the replacement of Alpha Cove with Delta Island after applying the search.'),
        cp('overlay','compare-pdfs','Compare chapter-a.pdf and chapter-b.pdf in Overlay view, then navigate to the next page of differences.',pair+[click('Overlay'),{'do':'click','target':{'title':'Next page'}}],[],['chapter-a.pdf','chapter-b.pdf'],'The second comparison page is shown in overlay mode with its differences available.'),
        cp('filter','compare-pdfs','Compare chapter-a.pdf and chapter-b.pdf on the first page, then hide the Headers category in the difference list.',pair+[click('1 Headers'),{'do':'wheel','x':1200,'y':600,'delta_y':450}],[],['chapter-a.pdf','chapter-b.pdf'],'The header change is filtered out and the list says that no changes match the filter.',companions=['search/visible']),
    ])]

def build():return viewer()+text_editing()+form_roundtrip()+template_lifecycle()+compare_filters()
