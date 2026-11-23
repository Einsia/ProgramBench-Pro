from program import Builder,request
from common import READER


def ext(family,action,**kw):return {'kind':'extension','family':family,'action':action,**kw}


def build():
    result=[]
    for entity,key in [('books','b01'),('series','s0'),('collections','shelf'),('readlists','queue')]:
        b=Builder('api-posters-'+entity,library=True);b.setup.append({'id':'lists','kind':'extra-lists'})
        path='/api/v1/'+entity+'/${'+key+'.id}'
        previous=None
        for action in ['upload-a','upload-b','list','select-b','select-a','invalid-selection','delete-b','restart','delete-a']:
            b.add(action,ext('posters',action,path=path),depends=[previous] if previous else []);previous=action
        result.append(b.build())
    b=Builder('api-comicrack',library=True);b.setup.append({'id':'comicrack','kind':'comicrack'})
    for extension in ['xml','cbl']:
        b.add('exact-'+extension,ext('comicrack','match',extension=extension,expected=['${b01.id}']))
    b.add('multiple-order',ext('comicrack','match',entries=[['Atlas','3','2020'],['Beacon','1','2021'],['Atlas','1','2020']],expected=['${b03.id}','${b11.id}','${b01.id}']))
    b.add('absent',ext('comicrack','match',entries=[['Absent','99','2020']],matches=[0]),depends=['exact-cbl'])
    b.add('mixed-known-unknown',ext('comicrack','match',entries=[['Atlas','2','2020'],['Absent','9','2020']],matches=[1,0],expected=['${b02.id}']))
    b.add('create-matched-list',ext('comicrack','create',entries=[['Atlas','3','2020'],['Beacon','1','2021'],['Atlas','1','2020']],expected=['${b03.id}','${b11.id}','${b01.id}']))
    b.add('ambiguous-setup',ext('comicrack','ambiguous-fixture'))
    b.add('ambiguous-match',ext('comicrack','match',entries=[['Atlas','1']],matches=[2]),depends=['ambiguous-setup'])
    result.append(b.build())
    b=Builder('api-list-progress',library=True);b.setup.extend([{'id':'reader','kind':'reader'},{'id':'lists','kind':'extra-lists'}])
    previous=None
    for i in [0,1,2,4]:
        cp='read-through-'+str(i);b.add(cp,ext('mihon-list','set',index=i,expect=[n<i for n in range(4)]),depends=[previous] if previous else [])
        b.add('other-user-'+str(i),ext('mihon-list','read',reader=True,expect=[False]*4),depends=[cp]);previous=cp
    b.add('invalid-negative',ext('mihon-list','invalid'),depends=[previous])
    b.add('persist',ext('mihon-list','restart'),depends=[previous])
    result.append(b.build())
    b=Builder('api-account-security');b.setup.append({'id':'reader','kind':'reader'})
    b.add('self-password',ext('self-password','change'))
    b.add('invalid-password',ext('self-password','invalid'),depends=['self-password'])
    b.add('unicode-password',ext('self-password','change',password='Reader-密碼-Ω!'),depends=['self-password'])
    b.add('persist-password',ext('self-password','restart'),depends=['unicode-password'])
    b.add('authentication-activity',ext('self-password','activity'),depends=['unicode-password'])
    b.add('other-user-protected',ext('self-password','cross-password'),depends=['unicode-password'])
    result.append(b.build())
    b=Builder('api-archives-import',library=True)
    b.add('series-archive',ext('archive','download'))
    for mode in ['COPY','MOVE']:
        b.add('import-'+mode.lower(),ext('imports','import',mode=mode,name='Imported-'+mode,number=2 if mode=='MOVE' else 1))
    result.append(b.build())
    b=Builder('api-single-duplicate',library=True);b.setup.append({'id':'hash','kind':'duplicate-hash'})
    b.add('matches',ext('duplicate-single','matches'))
    b.add('remove-one',ext('duplicate-single','delete'),depends=['matches'])
    b.add('other-matches-remain',ext('duplicate-single','remaining'),depends=['remove-one'])
    result.append(b.build())
    return result
