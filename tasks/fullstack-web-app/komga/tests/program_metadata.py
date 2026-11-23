from program import Builder,request


def build():
    episodes=[]
    book={'title':['A new chapter','问题 café Ω','<b>Plain markup</b>',''], 'summary':['Line one\nLine two','Résumé & Ω',''],
          'number':['Special','0.5','12A',''], 'numberSort':[-1,0,2.5,100], 'isbn':['9780306406157','978-0-306-40615-7',''],
          'releaseDate':['1999-12-31','2024-02-29',None], 'tags':[['red','blue'],['蓝','café'],[],None],
          'authors':[[{'name':'Nora North','role':'writer'},{'name':'Ida Ink','role':'penciller'}],[{'name':'林','role':'translator'}],[],None],
          'links':[[{'label':'Reference','url':'https://example.test/book'}],[],None],
          'notableEntities':[[{'name':'Captain Star','kind':'character'},{'name':'Port North','kind':'location'}],[],None]}
    series={'title':['A series','漫画 café Ω',''], 'titleSort':['Z sort','001 sort',''], 'summary':['A complete story\nSecond line',''],
            'publisher':['New Press','Éditions 林',''], 'language':['en','fr','ja',''], 'ageRating':[0,12,18,None],
            'readingDirection':['LEFT_TO_RIGHT','RIGHT_TO_LEFT','VERTICAL','WEBTOON',None],
            'status':['ONGOING','ENDED','ABANDONED','HIATUS'], 'genres':[['Drama','Mystery'],['历史'],[],None],
            'tags':[['alpha','beta'],['café'],[],None], 'sharingLabels':[['family','school'],['adult'],[],None],
            'totalBookCount':[1,3,12,None], 'alternateTitles':[[{'label':'French','title':'Les étoiles'},{'label':'Japanese','title':'星'}],[],None],
            'links':[[{'label':'Series','url':'https://example.test/series'}],[],None]}
    for entity,fields,identifier in [('books',book,'b01'),('series',series,'s0')]:
        b=Builder('api-'+entity+'-metadata',library=True);path='/api/v1/'+entity+'/${'+identifier+'.id}'
        b.get('imported-metadata',path,fields=['metadata'])
        for field,values in fields.items():
            for i,value in enumerate(values):
                b.mutate(f'{field}-{i}',path+'/metadata',{field:value},path,fields=['metadata.'+field])
                if value=='' and field in {'title','titleSort','number'}:b.cases[-1]['spec']['write']['status']=400
            for locked in (True,False):
                b.mutate(field+'-lock-'+str(locked).lower(),path+'/metadata',{field+'Lock':locked},path,fields=['metadata.'+field+'Lock','metadata.'+field])
                b.cases[-1]['depends_on'].append(b.cases[-2]['id'])
        # Omitted fields preserve a simultaneous pair, independent of clearing behavior.
        for i,(left,right) in enumerate([('title','summary'),('tags','links')]):
            v1=fields[left][0];v2=fields[right][0]
            b.mutate(f'pair-{i}',path+'/metadata',{left:v1,right:v2},path,fields=['metadata.'+left,'metadata.'+right])
            b.mutate(f'omitted-{i}',path+'/metadata',{left:fields[left][1]},path,fields=['metadata.'+left,'metadata.'+right])
            b.cases[-1]['depends_on'].append(f'pair-{i}')
        if entity=='books':
            b.add('bulk-two-books',{'kind':'mutation','write':request('/api/v1/books/metadata','PATCH',{'${b02.id}':{'title':'Bulk two'},'${b03.id}':{'summary':'Bulk three'}}),'read':request('/api/v1/series/${s0.id}/books',catalog=True,item_fields=['name','metadata.title','metadata.summary'])})
        b.add('metadata-survives-restart',{'kind':'restart','compare_before':True,'read':request(path,fields=['metadata'])})
        episodes.append(b.build())
    return episodes
