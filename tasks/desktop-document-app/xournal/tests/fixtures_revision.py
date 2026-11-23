"""Small synthetic inputs for additional desktop feature families."""
import fixtures as f


def get(name):
    if name=='custom.gpl':
        return b'GIMP Palette\nName: Orchard\nColumns: 3\n#\n25 100 70 Forest\n201 55 90 Berry\n235 170 40 Honey\n'
    if name=='overlap.xopp':
        def box(x,y,w,h,c):return f.stroke([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],color=c,width=3,fill=255)
        return f.document([f.page([box(70,75,270,220,'#cc3333ff'),box(180,140,270,140,'#228844ff'),box(240,100,230,230,'#2244ccff')],size=(600,400))])
    if name=='graph.xopp':
        return f.document([f.page(size=(600,400),style='graph',config='r1=20,lw=0.5',color='#fff4ccff')])
    if name=='layer-nav.xopp':
        return f.document([f.page(size=(600,400),layers=[(n,[f.text(n,80+i*130,90+i*70,size=24)]) for i,n in enumerate(['Bottom','Middle','Top'])])])
    if name=='annotated.xopp':
        return f.document([f.page([f.text('Annotation '+str(i+1),100,120,size=30)] if i in (1,3) else [],size=(600,400),color=c)
                           for i,c in enumerate(['#ffffccff','#ddeeffff','#ffddddff','#ddffddff'])])
    if name=='nav.pdf':
        import pymupdf as fitz
        doc=fitz.open()
        for i in range(4):
            p=doc.new_page(width=600,height=400);p.insert_text((90,150),'Destination '+str(i+1),fontsize=40)
        doc.set_toc([[1,'Section One',1],[2,'Detail Two',2],[1,'Section Three',3],[2,'Detail Four',4]])
        doc[0].insert_text((90,230),'GO TO FOUR',fontsize=24,color=(0,.2,.8))
        doc[0].insert_link({'kind':fitz.LINK_GOTO,'from':fitz.Rect(80,200,330,240),'page':3,'to':fitz.Point(0,0)})
        return doc.tobytes(deflate=True,no_new_id=True)
    if name=='template-input.xopp':
        return f.document([f.page(size=(500,300),style='graph',color='#fff4ccff')])
    return None
