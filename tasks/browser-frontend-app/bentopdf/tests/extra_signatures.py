"""Handwritten and image signatures through the visible signature dialog."""
from specification import episode,cp,click,fill,upload,downloaded,projection,pdf_checks

def build():
    start=[upload('single.pdf'),{'do':'wheel','x':1200,'y':600,'delta_y':650},{'do':'click','target':{'title':'Add signature'}},{'do':'click','target':{'title':'Add new signature'}}]
    end=[click('Add'),{'do':'pointer','x':650,'y':440},click('Save & Download Signed PDF'),downloaded(),{'do':'close-success'},{'do':'reopen-result'},{'do':'wheel','x':1200,'y':600,'delta_y':650}]
    return [episode('signature-inputs','security',[
        cp('draw','sign-pdf','Draw a simple V-shaped signature (one stroke down to a low point, then back up), describe it as "Harbor V", add it to single.pdf and save. Reopen the exported PDF in Form Filler.',start+[{'do':'click','target':{'text':'Draw','role':'tab'}},{'do':'drag','x':440,'y':350,'to_x':760,'to_y':350,'via':[[600,465]]},{'do':'fill','target':{'label':'Description (alt text)'},'value':'Harbor V'}]+end,
           pdf_checks()+[projection('pdf-mark',input='single.pdf',gray=True,stroke_shape=True)],['single.pdf'],'The saved PDF displays a V-shaped signature.'),
        cp('image','sign-pdf','Use stamp.png as an image signature on single.pdf with description "Harbor symbol", save it and reopen the exported PDF in Form Filler.',start+[{'do':'click','target':{'text':'Image','role':'tab'}},upload('stamp.png',target={'text':'Or browse image files'}),{'do':'fill','target':{'label':'Description (alt text)'},'value':'Harbor symbol'}]+end,
           pdf_checks()+[projection('pdf-mark',input='single.pdf')],['single.pdf','stamp.png'],'The saved PDF displays the supplied image signature.'),
    ])]
