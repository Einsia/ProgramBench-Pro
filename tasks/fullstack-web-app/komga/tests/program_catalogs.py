from program import Builder,request


def build():
    result=[]
    b=Builder('api-referential',library=True)
    b.setup.append({'id':'search-state','kind':'search-state'})
    for version in ('v1','v2'):
        for field,queries in {'authors':['Ada','Dana','林'],'authors/names':['Ada','Dana'],'authors/roles':['writer','penciller'],'genres':['adventure','history'],'languages':['en','fr'],'publishers':['North','South'],'age-ratings':['0','12'],'tags':['volume','bright'],'sharing-labels':['family','adult']}.items():
            path='/api/'+version+'/'+field
            b.get(version+'-'+field.replace('/','-')+'-all',path,unordered=True)
            if (version=='v1' and field not in {'authors','authors/names'}) or (version=='v2' and field in {'age-ratings','authors/roles'}):queries=[]
            for i,q in enumerate(queries):b.get(version+'-'+field.replace('/','-')+'-q'+str(i),path,params={'search':q},unordered=True)
            if version=='v2':
                filters=([{'series_id':'${s0.id}'},{'series_id':'${s2.id}'}] if field in {'authors','authors/names','tags'} else [])+[{'page':0,'size':1},{'page':1,'size':1}]
                for i,params in enumerate(filters):
                    b.get(version+'-'+field.replace('/','-')+'-filter'+str(i),path,params=params)
    for field in ('notable-entities','notable-entities/names','notable-entities/kinds'):
        params_list=[{}, {'series_id':'${s0.id}'},{'page':0,'size':1}]+([] if field.endswith('/kinds') else [{'search':'Star'},{'kind':'character'}])
        for i,params in enumerate(params_list):
            b.get(field.replace('/','-')+'-'+str(i),'/api/v3/'+field,params=params)
    b.get('series-years','/api/v2/series/release-years')
    for path in ['/api/v1/series/alphabetical-groups','/api/v1/series/release-dates','/api/v1/books/duplicates']:
        b.get(path.replace('/','-'),path)
    result.append(b.build())
    b=Builder('api-opds',library=True)
    b.setup.append({'id':'list-identities','kind':'list-identities'})
    b.setup.append({'id':'search-state','kind':'search-state'})
    for version,routes in [('v1.2',['catalog','libraries','series','series/latest','books/latest','collections','readlists','publishers','ondeck','keep-reading','series/${s0.id}','series/${s2.id}','libraries/${lib.id}']),('v2',['catalog','libraries','libraries/browse','libraries/books/latest','libraries/series/latest','libraries/collections','libraries/readlists','libraries/on-deck','libraries/keep-reading','series/${s0.id}','series/${s2.id}','libraries/${lib.id}'])]:
        for i,route in enumerate(routes):b.get(version+'-'+str(i),'/opds/'+version+'/'+route,**({'xml':True} if version=='v1.2' else {'opds_recommended':True} if route in ('catalog','libraries','libraries/${lib.id}') else {}))
        for search in ('Atlas','café','no matching title'):
            b.get(version+'-search-'+str(len(b.cases)),'/opds/'+version+'/search',params={'query':search},**({'xml':True} if version=='v1.2' else {}))
        for page in (0,1,2):b.get(version+'-paging-'+str(page),'/opds/'+version+('/series' if version=='v1.2' else '/libraries/browse'),params={'page':page,'size':2},**({'xml':True} if version=='v1.2' else {}))
        b.get(version+'-anonymous','/opds/'+version+'/catalog',auth=None,status=401)
    result.append(b.build())
    return result
