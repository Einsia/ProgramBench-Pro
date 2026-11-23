"""Batch image drops and complete saved-document round trips."""
import copy
import fixtures as F
import program as P
import program_extra as X
import program_formats as D


def batch():
    names=['batch-red.png','batch-green.png','batch-blue.png']
    cases=[]
    for cid,order,position in [('after-first',names,0),('reverse',names[::-1],0),
                               ('after-middle',names,1),('after-last',names,2)]:
        recipe=[P.settle(1.5)]+P.key('ArrowDown',position)
        recipe += [{'op':'inputs','action':'drop','filenames':order,'target':{'sprite':True},'x':0,'y':0},P.settle(1)]
        cases.append(P.case(cid,'Drop three images together after the selected frame.',F.ANIM,recipe,
                           [P.point('structure','The complete layer and frame counts include the batch.',{'type':'structure'}),
                            P.point('content','The document reflects the batch drop at the selected position.',P.ALL)]))
    return P.episode('import-batch','import',cases)


def saved_documents():
    cases=[]
    for cid,names,hidden in [('duplicate-names',['same','same'],[0,2]),('different-lengths',['short','long'],[1])]:
        sp=copy.deepcopy(F.GRID);sp['hidden']=hidden
        for ly,name in zip(sp['layers'],names):ly['name']=name
        if cid=='different-lengths':sp['layers'][0]['frames']=sp['layers'][0]['frames'][:2]
        cases.append(P.case(cid,'Save and reopen a project while preserving names, frame visibility and complete structure.',sp,
                            [X.drawer('save'),P.control(text='Save as .piskel',exact=True),
                             {'op':'wait-download','suffix':'.piskel'},{'op':'reload-download'}],D.document_points(sp)))
    invalid=copy.deepcopy(F.GRID);invalid['layers'][0]['name']=''
    cases.append(P.case('empty-name','Try loading a layer with an empty name and retain the current valid document.',F.ARROW,
                        [{'op':'load-result','piskel':F.encode(invalid)}],
                        [P.point('rejected','An empty layer name is rejected.',{'type':'load-result'},requires=['duplicate-names/structure']),
                         P.point('preserved','The existing document survives a rejected load.',P.ALL,requires=['duplicate-names/structure'])]))
    return P.episode('save-structure','save',cases)


def build():
    return [batch(),saved_documents()]
