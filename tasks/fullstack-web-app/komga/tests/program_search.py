from program import Builder,request


def condition(field,op,value=None):
    v={'operator':op}
    if value is not None:v['value']=value
    return {field:v}


def build():
    result=[]
    for entity in ('books','series'):
        b=Builder('api-search-'+entity,library=True)
        # Deliberately varied stored state: progress/status/labels and null metadata.
        b.setup.append({'id':'search-state','kind':'search-state'})
        b.setup.append({'id':'mixed','kind':'search-population'})
        path='/api/v1/'+entity+'/list'
        b.get('catalog',path,method='POST',body={},catalog=True)
        conditions=[]
        def addcond(field,ops,values):
            for op in ops:
                for value in values:
                    c=condition(field,op,value);conditions.append((field+'-'+op+'-'+str(len(conditions)),c))
        for f in (['title'] if entity=='books' else ['title','titleSort']):
            addcond(f,['is','isNot','beginsWith','doesNotBeginWith','contains','doesNotContain','endsWith','doesNotEndWith'],['Atlas' if entity=='series' else 'Atlas chapter 1','Café','a'])
        addcond('libraryId',['is','isNot'],['${lib.id}','missing-library'])
        addcond('readStatus',['is','isNot'],['READ','UNREAD','IN_PROGRESS'])
        addcond('author',['is','isNot'],[{'name':'Ada Rivers'},{'role':'penciller'},{'name':'Chloé 林','role':'writer'}])
        addcond('tag',['is','isNot'],['bright','dark','volume-2'] if entity=='books' else ['alpha','beta'])
        for f in (['deleted','oneShot'] if entity=='books' else ['deleted','oneShot','complete']):addcond(f,['isTrue','isFalse'],[None])
        for f in ['tag']+(['ageRating','genre','sharingLabel'] if entity=='series' else []):addcond(f,['isNull','isNotNull'],[None])
        if entity=='books':
            addcond('seriesId',['is','isNot'],['${s0.id}','${s2.id}'])
            addcond('numberSort',['is','isNot','lessThan','greaterThan'],[1,2,2.5,3])
            addcond('mediaStatus',['is','isNot'],['READY','ERROR'])
            addcond('mediaProfile',['is','isNot'],['DIVINA','EPUB','PDF'])
            addcond('poster',['is','isNot'],[{'type':'GENERATED','selected':True},{'type':'USER_UPLOADED'}])
        else:
            addcond('publisher',['is','isNot'],['North Press','South Press'])
            addcond('language',['is','isNot'],['en','fr','ja'])
            addcond('genre',['is','isNot'],['adventure','fantasy','history'])
            addcond('ageRating',['is','isNot','lessThan','greaterThan'],[0,12,17])
            addcond('seriesStatus',['is','isNot'],['ONGOING','ENDED','ABANDONED','HIATUS'])
            addcond('sharingLabel',['is','isNot'],['family','adult'])
        for op in ('before','after'):
            for date in ('2020-01-15T00:00:00Z','2022-06-01T00:00:00Z','2025-03-15T23:59:59Z'):
                conditions.append(('date-'+str(len(conditions)),{'releaseDate':{'operator':op,'dateTime':date}}))
        for name,c in conditions:b.get(name,path,method='POST',body={'condition':c},catalog=True)
        # Boolean combinations pair independent axes; both AND and OR have visible populations.
        axes=[condition('author','is',{'name':'Ada Rivers'}),condition('readStatus','is','READ'),condition('title','contains','a'),condition('tag','is','bright' if entity=='books' else 'alpha')]
        for i,c in enumerate(axes):
            for j,d in enumerate(axes[i+1:],i+1):
                for op in ('allOf','anyOf'):
                    b.get(f'compound-{i}-{j}-{op}',path,method='POST',body={'condition':{op:[c,d]}},catalog=True)
        for search in ['Atlas','ATLAS','café','漫画','chapter 2','South','absent phrase']:
            b.add('text-'+str(len(b.cases)),{'kind':'search-observation','request':request(path,method='POST',body={'fullTextSearch':search},catalog=True)})
        # Page boundaries and sort keys use multiple distinct values and stable tie groups.
        sorts=['metadata.title','metadata.titleSort','name','booksCount'] if entity=='series' else ['metadata.title','metadata.numberSort','name','metadata.releaseDate']
        for sort in sorts:
            for direction in ('asc','desc'):
                for page,size in [(0,2),(1,2),(2,3),(0,50)]:
                    b.get(f'page-{sort}-{direction}-{page}-{size}',path,method='POST',body={},params={'sort':[sort+','+direction,'name,asc'],'page':page,'size':size},catalog=True,unordered=False)
        # Legacy filters are independent compatibility behavior, not translations hidden in the runtime.
        legacy={'search':['Atlas','café','missing'],'read_status':['READ','UNREAD','IN_PROGRESS'],'tag':['bright','volume-2']}
        if entity=='series':legacy.update(publisher=['North Press','South Press'],language=['en','fr','ja'],genre=['adventure','history'],status=['ENDED','HIATUS'],age_rating=['0','17'],complete=['true','false'],search_regex=['^A,TITLE','a$,TITLE_SORT'])
        for field,values in legacy.items():
            for value in values:b.add('legacy-'+field+'-'+str(len(b.cases)),{'kind':'search-observation','request':request('/api/v1/'+entity,params={field:value},catalog=True)} if field=='search' else request('/api/v1/'+entity,params={field:value},catalog=True))
        for field,val in [('read_status','INVALID'),('media_status' if entity=='books' else 'status','WRONG')]:
            b.get('invalid-'+field,'/api/v1/'+entity,params={field:val},status=400)
        endpoints=['/api/v1/books/latest','/api/v1/books/ondeck'] if entity=='books' else ['/api/v1/series/latest','/api/v1/series/new','/api/v1/series/updated']
        for i,ep in enumerate(endpoints):b.get('discovery-'+str(i),ep,params={'size':100},catalog=True)
        if entity=='series':b.get('structured-alphabet-groups','/api/v1/series/list/alphabetical-groups',method='POST',body={})
        for cp in b.cases:
            spec=cp['spec'].get('request',cp['spec'])
            if spec.get('catalog') and not ({'page','size','unpaged'} & spec.get('params',{}).keys()):spec['params']={**spec.get('params',{}),'size':100}
        for cp in b.cases[1:]:cp['assertions'][0]['requires']=[b.key+'/catalog/result']
        result.append(b.build())
    return result
