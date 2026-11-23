"""Documented branches: annotation, form properties, graph composition and configuration."""
from specification import episode,cp,taskcp,click,fill,select,check,upload,downloaded,projection,pdf_checks

def annotations():
    start=[upload('single.pdf'),{'do':'wheel','x':1100,'y':600,'delta_y':600},click('Annotate')]
    finish=[{'do':'wait','seconds':2},{'do':'click','target':{'aria':'Toggle Pointer Mode'}},{'do':'wait','seconds':1},click('Download Edited PDF'),downloaded('.pdf')]
    cps=[]
    for key,tool in [('ink','Ink'),('ink-highlight','Ink Highlighter')]:
        cps.append(cp(key,'edit-pdf',f'Add one freehand {"highlighter" if key=="ink-highlight" else "ink"} stroke in the blank middle of single.pdf, then download the edited PDF.',start+[{'do':'click','target':{'aria':tool}},{'do':'drag','x':540,'y':370,'to_x':700,'to_y':440,'via':[[580,420],[620,360],[660,425]]}]+finish,
                      pdf_checks(raster=False)+[projection('pdf-base-preserved',input='single.pdf')]+[projection('pdf-annotation-details')],['single.pdf']))
    cps.append(cp('comment','edit-pdf','Place a comment in the blank middle of single.pdf with the exact text "Inspect the eastern dock", then download the edited PDF.',start+[{'do':'click','target':{'aria':'Comment','nth':1}},{'do':'pointer','x':620,'y':400},{'do':'click','target':{'aria':'Comment','nth':2}},{'do':'fill','target':{'placeholder':'Add comment...'},'value':'Inspect the eastern dock'},{'do':'press','key':'Enter'}]+finish,
                  pdf_checks(raster=False)+[projection('pdf-base-preserved',input='single.pdf')]+[projection('pdf-comment-content')],['single.pdf']))
    cps.append(cp('free-text','edit-pdf','Add a text annotation reading "Dock inspected" in the blank middle of single.pdf, then download it.',start+[{'do':'click','target':{'aria':'Text'}},{'do':'drag','x':540,'y':370,'to_x':740,'to_y':440},{'do':'fill','target':{'text':'Insert text'},'value':'Dock inspected'},{'do':'pointer','x':780,'y':500}]+finish,
                  pdf_checks(raster=False)+[projection('pdf-base-preserved',input='single.pdf',added_text='Dock inspected')]+[projection('pdf-added-text',pattern=r'Dock|inspected')],['single.pdf']))
    return [episode('annotations-more','editing',cps)]

def graph_operations():
    cps=[]
    for key,file in [('chain','report.pdf'),('redact-text','single.pdf'),('redact-area','single.pdf'),('branch','report.pdf')]:
        recipe=[click('Import'),upload('flow-'+key+'.json'),{'do':'pointer','x':400,'y':185},upload(file,target={'text':'Upload PDFs'}),click('Run'),downloaded()]
        checks=pdf_checks()+([projection('pdf-redacted',absent=['Harbor Map'],present=['Anchor'])] if key.startswith('redact') else [projection('pdf-word-layout',tol=2)])
        cps.append(cp(key,'pdf-workflow',f'Import flow-{key}.json, supply {file} to its PDF Input node, and execute the graph without changing options.',recipe,checks,['flow-'+key+'.json',file]))
    cps.append(cp('merge','pdf-workflow','Import flow-merge.json. Supply chapter-a.pdf to the upper PDF Input and chapter-b.pdf to the lower PDF Input. Run the graph.',[click('Import'),upload('flow-merge.json'),{'do':'pointer','x':400,'y':185},upload('chapter-a.pdf',target={'text':'Upload PDFs'}),{'do':'pointer','x':400,'y':485},upload('chapter-b.pdf',target={'text':'Upload PDFs'}),click('Run'),downloaded()],pdf_checks(),['flow-merge.json','chapter-a.pdf','chapter-b.pdf']))
    return [episode('workflow-composition','workflow',cps)]

def graph_validation():
    good=cp('valid','pdf-workflow','Import workflow-rotate.json, supply report.pdf, and execute it.',[click('Import'),upload('workflow-rotate.json'),{'do':'pointer','x':400,'y':185},upload('report.pdf',target={'text':'Upload PDFs'}),click('Run'),downloaded()],pdf_checks(),['workflow-rotate.json','report.pdf'])
    encrypted=cp('encrypted','pdf-workflow','Import flow-encrypt.json. Set the encryption node user password to "harbor-secret" and owner password to "harbor-owner", supply report.pdf to PDF Input, and run the graph.',[click('Import'),upload('flow-encrypt.json'),{'do':'pointer','x':650,'y':185},fill('User Password','harbor-secret'),fill('Owner Password','harbor-owner'),{'do':'pointer','x':400,'y':185},upload('report.pdf',target={'text':'Upload PDFs'}),click('Run'),downloaded()],pdf_checks()+[projection('pdf-encryption')],['flow-encrypt.json','report.pdf'],password='harbor-secret')
    cps=[good,encrypted]
    for key,file,label,companion in [('cycle','flow-cycle.json','circular dependency','valid/pdf-count'),('missing-password','flow-encrypt.json','missing encryption password','encrypted/pdf-encryption')]:
        negative=projection('no-download','An invalid workflow does not produce an output.');negative['requires']=[companion]
        goal=f'Import {file}, supply report.pdf, and try running the graph.'+(' Leave the encryption passwords empty.' if key=='missing-password' else '')
        cps.append(cp(key,'pdf-workflow',goal,[click('Import'),upload(file),{'do':'pointer','x':400,'y':185},upload('report.pdf',target={'text':'Upload PDFs'}),click('Run'),{'do':'wait-text','text':'Error'}],[negative],[file,'report.pdf'],f'The application reports the {label} and does not claim successful execution.',companions=[companion]))
    return [episode('workflow-errors','workflow',cps)]

def bookmarks():
    base=[upload('bookmarks.pdf'),click('Extract Existing Bookmarks'),click('Confirm')]
    finish=[click('Save PDF with Bookmarks'),downloaded(),{'do':'close-success'},{'do':'reopen-result','path':'/bookmark.html'},click('Extract Existing Bookmarks'),click('Confirm')]
    cps=[]
    for key,actions,goal in [
        ('rename',[fill('Title','Harbor Introduction')],'Rename Introduction to "Harbor Introduction".'),
        ('style',[select('Color','blue'),select('Style','bold-italic')],'Make Introduction blue and bold italic.'),
    ]:
        cps.append(cp(key,'bookmark','Load the existing bookmarks in bookmarks.pdf. '+goal+' Save the PDF.',base+[{'do':'click','target':{'title':'Edit','nth':0}}]+actions+[click('Confirm')]+finish,pdf_checks()+[projection('pdf-bookmarks'),projection('pdf-bookmark-style')],['bookmarks.pdf']))
    for ext in ['csv','json']:
        cps.append(cp('import-'+ext,'bookmark',f'Open report.pdf, import bookmark-import.{ext}, then save the PDF with the imported bookmark hierarchy.',[upload('report.pdf'),click('Import'),click('Import '+ext.upper()),upload('bookmark-import.'+ext),click('OK')]+finish,pdf_checks()+[projection('pdf-bookmarks'),projection('pdf-bookmark-style')],['report.pdf','bookmark-import.'+ext]))
    cps.append(cp('search','bookmark','Load the existing bookmarks from bookmarks.pdf and search them for "North".',base+[{'do':'fill','target':{'placeholder':'Search bookmarks...'},'value':'North'}],[],['bookmarks.pdf'],'The bookmark panel shows the North entries and filters unrelated entries.'))
    cps.append(cp('child','bookmark','Load the existing bookmarks in bookmarks.pdf, add a child bookmark named "Dock notes" beneath Introduction, pointing to page 1, and save.',base+[{'do':'click','target':{'title':'Add child','nth':0}},fill('Title','Dock notes'),click('Confirm')]+finish,pdf_checks()+[projection('pdf-bookmarks')],['bookmarks.pdf']))
    for c in cps:
        if c['id']!='search':c['goal']+=' Reopen the saved PDF in the bookmark tool and display its bookmarks.'
    return [episode('bookmark-editing','metadata',cps)]

def form_properties():
    cps=[]
    for key,actions,goal in [
        ('default',[fill('Value','Cedar Harbor')],'set its default value to "Cedar Harbor"'),
        ('required',[check('Required')],'make it required'),
        ('readonly',[fill('Value','Read-only note'),check('Read Only')],'set its value to "Read-only note" and make it read-only'),
        ('length',[fill('Max Length (0 for unlimited)',12)],'limit its text to 12 characters'),
        ('appearance',[fill('Font Size',18),fill('Text Color','#2244aa'),select('Alignment','center')],'use font size 18, text color #2244aa and centered alignment'),
    ]:
        cps.append(cp(key,'form-creator','Open single.pdf, add a text field named "visitor", '+goal+', and download the form. Reopen the saved form in Form Filler.',[upload('single.pdf'),click('Text'),{'do':'pointer','x':650,'y':600},{'do':'pointer','x':650,'y':600},fill('Field Name','visitor')]+actions+[click('Download PDF Form'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}],
                      [projection('pdf-count'),projection('pdf-size'),projection('pdf-widget-state'),projection('pdf-base-preserved',input='single.pdf')],['single.pdf']))
    cps.append(cp('options','form-creator','Open single.pdf and add a dropdown named "port" with exactly the options Cedar, Maple and Elm, defaulting to Maple. Download the form and reopen it in Form Filler.',[upload('single.pdf'),click('Dropdown'),{'do':'pointer','x':650,'y':600},{'do':'pointer','x':650,'y':600},fill('Field Name','port'),fill('Options (One per line or comma separated)','Cedar\nMaple\nElm'),select('Selected Option','Maple'),click('Download PDF Form'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}],[projection('pdf-widget-state'),projection('pdf-base-preserved',input='single.pdf')],['single.pdf']))
    return [episode('form-properties','forms',cps)]

def compression():
    return [episode('compression-options','optimization',[
        taskcp('photon','compress-pdf','Compress photo.pdf using the Photon algorithm and Balanced level.','photo.pdf',[select('Compression Algorithm','photon')],'Compress PDF',pdf_checks(text=False)+[projection('pdf-rasterized'),projection('pdf-image-size'),projection('pdf-image-quality',tol=2)]),
        taskcp('custom','compress-pdf','Compress photo.pdf with Condense, custom output quality 40, target DPI 100 and processing threshold 120 DPI.','photo.pdf',[click('Custom Settings'),fill('Output Quality',40),fill('Resize Images To',100),fill('Only Process Above',120)],'Compress PDF',pdf_checks()+[projection('pdf-image-size'),projection('pdf-image-quality',tol=2)]),
        taskcp('gray','compress-pdf','Compress photo.pdf with Condense at Balanced level and convert to grayscale.','photo.pdf',[check('Convert to Grayscale')],'Compress PDF',pdf_checks()+[projection('pdf-image-color')]),
    ])]

def watermarks():
    cps=[]
    for key,extra,goal in [('single',[],'centered single'),('tiled',[click('Tiled')],'tiled'),('flatten',[check('Flatten watermark')],'flattened centered single')]:
        recipe=[upload('single.pdf'),click('Image'),upload('stamp.png',target={'label':'Watermark Image'}),fill('Scale:',60,contains=True),fill('Opacity:',.7,contains=True)]+extra+[click('Add Watermark'),downloaded()]
        cps.append(cp(key,'add-watermark',f'Apply stamp.png as a {goal} image watermark on single.pdf, with scale 60% and opacity 0.7.',recipe,pdf_checks(text=key!='flatten')+[projection('pdf-mark',input='single.pdf')]+([projection('pdf-rasterized')] if key=='flatten' else []),['single.pdf','stamp.png']))
    return [episode('image-watermarks','annotation',cps)]

def passwords():
    good=taskcp('correct','unlock-pdf','Decrypt encrypted.pdf with password "sailboat".','encrypted.pdf',[fill('PDF Password','sailboat')],'Decrypt PDF',pdf_checks()+[projection('pdf-encryption')])
    neg=projection('no-download','An incorrect password does not produce a decrypted file.');neg['requires']=['correct/pdf-count']
    return [episode('password-errors','security',[
        good,cp('incorrect','unlock-pdf','Try to decrypt encrypted.pdf with the incorrect password "wrong-password".',[upload('encrypted.pdf'),fill('PDF Password','wrong-password'),click('Decrypt PDF'),{'do':'wait-text','text':'Unable to decrypt'}],[neg],['encrypted.pdf'],'The application reports that the password is invalid.',companions=['correct/pdf-count']),
        cp('tampered','validate-signature-pdf','Validate tampered.pdf, which has been altered after signing.',[upload('tampered.pdf'),{'do':'wait','seconds':2},{'do':'wheel','x':1200,'y':600,'delta_y':650}],[],['tampered.pdf'],'The signature validation identifies that document integrity is not valid.'),
    ])]

def build():return annotations()+graph_operations()+graph_validation()+bookmarks()+form_properties()+compression()+watermarks()+passwords()
