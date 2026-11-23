from program import Builder,request


def build():
    result=[]
    for entity,member,keys in [('collections','seriesIds',['s0','s1','s2']),('readlists','bookIds',['b01','b21','b02'])]:
        b=Builder('api-'+entity,library=True)
        base='/api/v1/'+entity;child='series' if entity=='collections' else 'books'
        for variant,title in [('plain','Weekend shelf'),('unicode','阅读 café Ω'),('ordered','Crossing order')]:
            key='item-'+variant;path=base+'/${'+key+'.id}'
            ids=['${'+k+'.id}' for k in keys]
            body={'name':title,'ordered':variant=='ordered',member:ids}
            if entity=='readlists':body['summary']='Stories across libraries'
            b.get(variant+'-create',base,method='POST',body=body,save=key)
            b.get(variant+'-details',path)
            for params in ({'page':0,'size':2},{'page':1,'size':2},{'unpaged':'true'},{'sort':'name,desc'}):
                b.get(variant+'-members-'+str(len(b.cases)),path+'/'+child,params=params,catalog=True,unordered=False)
            for i,newids in enumerate([ids[::-1],ids[:1],ids[1:],ids]):
                b.mutate(variant+'-membership-'+str(i),path,{member:newids},path+'/'+child,catalog=True,unordered=False)
            for i,v in enumerate([True,False]):b.mutate(variant+'-order-'+str(i),path,{'ordered':v},fields=['ordered',member])
            if entity=='readlists':
                for i,summary in enumerate(['Summary\nSecond line Ω','']):b.mutate(variant+'-summary-'+str(i),path,{'summary':summary},fields=['summary'])
                for book in keys:
                    for direction in ('next','previous'):
                        b.get(variant+'-'+book+'-'+direction,path+'/books/${'+book+'.id}/'+direction,status=[200,404],fields=['name'])
                b.get(variant+'-download-archive',path+'/file',binary=True,bytes=True,zip=True)
            else:
                b.get(variant+'-series-memberships','/api/v1/series/${s0.id}/collections',unordered=True)
            for search in [title.split(' ')[0],title.split(' ')[-1],'missing']:
                b.add(variant+'-search-'+str(len(b.cases)),{'kind':'eventually','read':request(base,params={'search':search,'size':50},catalog=True,item_fields=['name','ordered'],want={'totalElements':0 if search=='missing' else 1})})
            b.mutate(variant+'-rename',path,{'name':title+' edited'},fields=['name'])
            b.add(variant+'-restart',{'kind':'restart','read':request(path,fields=['name','ordered',member])})
            b.get(variant+'-delete',path,method='DELETE')
            b.get(variant+'-gone',path,status=404)
        for i,body in enumerate([{'name':'','ordered':False,member:['${'+keys[0]+'.id}']},{'name':'Empty','ordered':False,member:[]},{'name':'Unknown','ordered':False,member:['missing-object']}]):
            if entity=='readlists':body['summary']=''
            b.get('invalid-'+str(i),base,method='POST',body=body,status=500 if i==2 else [200,400])
        for cp in b.cases:
            name=cp['id']
            if name.startswith('invalid-'):continue
            variant=name.split('-',1)[0]
            if '-order-' in name or name.endswith('-series-memberships'):
                cp['depends_on'].append(variant+'-membership-3')
            if name.endswith('-gone'):cp['depends_on'].append(variant+'-delete')
            if name.endswith('-restart'):cp['spec']['compare_before']=True
        result.append(b.build())
    return result
