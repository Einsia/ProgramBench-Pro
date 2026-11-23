from specification import episode,step,go,click,fill
from program import request


def build():
    w=[]
    for kind,key,base in [('book','b01','books'),('series','s0','series')]:
        path='/'+kind+'/${'+key+'.id}';api='/api/v1/'+base+'/${'+key+'.id}'
        steps=[]
        for action,done in [('Mark as read',True),('Mark as unread',False)]:
            fields=['readProgress'] if kind=='book' else ['booksReadCount','booksUnreadCount']
            want={'readProgress':{'completed':True}} if kind=='book' and done else {'readProgress':None} if kind=='book' else {'booksReadCount':3 if done else 0,'booksUnreadCount':0 if done else 3}
            steps.append(step('read' if done else 'unread',action+' for '+('Atlas chapter 1' if kind=='book' else 'the whole Atlas series')+'.','The '+kind+' visibly has '+('completed' if done else 'unread')+' reading status.',[go(path),{'op':'point','x':332,'y':96},click(action),{'op':'wait','seconds':.5},go(path)],request(api,fields=fields,want=want),visible=['Atlas'],depends=['read'] if not done else []))
        steps.append(step('refresh','Refresh the current details.','The saved unread state remains visible.',[{'op':'reload'}],request(api,fields=fields,want=want),visible=['Atlas'],depends=['unread']))
        w.append(episode('gui-mark-'+kind,'reading-progress',steps))
    for kind,key in [('book','b01'),('series','s0')]:
        path='/'+kind+'/${'+key+'.id}';entity='readlists' if kind=='book' else 'collections';noun='read list' if kind=='book' else 'collection';name='New weekend '+noun
        w.append(episode('gui-create-'+entity,'reading-organization',[
            step('create','Create '+noun+' '+repr(name)+' containing '+('Atlas chapter 1' if kind=='book' else 'Atlas')+'.','The newly created '+noun+' is accessible and contains the selected member.',[go(path),{'op':'point','x':332,'y':96},click('Add to '+noun),fill('Search or create '+noun,name),click('Create'),go('/libraries/all/'+entity),click(name)],request('/api/v1/'+entity,where={'name':name},fields=['name'],save='newlist'),visible=[name,'Atlas']),
            step('refresh','Refresh the new '+noun+'.','The new '+noun+' retains its name and member.',[{'op':'reload'}],visible=[name,'Atlas'],depends=['create']),
        ]))
    for label,value,field in [('Status','Ended','status'),('Reading Direction','Right to left','readingDirection')]:
        expected='ENDED' if field=='status' else 'RIGHT_TO_LEFT'
        w.append(episode('gui-series-'+field,'metadata-editing',[
            step('change','Set the Atlas series '+label.lower()+' to '+value+'.','The Atlas series visibly uses '+value+' for '+label.lower()+'.',[go('/series/${s0.id}'),{'op':'edit','kind':'series'},{'op':'select','label':label,'value':value},{'op':'save'},go('/series/${s0.id}')],request('/api/v1/series/${s0.id}',fields=['metadata.'+field],want={'metadata':{field:expected}}),visible=[value]),
            step('refresh','Refresh Atlas details.','The changed '+label.lower()+' remains visible.',[{'op':'reload'}],visible=[value],depends=['change']),
        ]))
    for kind,key in [('book','b01'),('series','s0')]:
        api='/api/v1/'+('books' if kind=='book' else 'series')+'/${'+key+'.id}'
        w.append(episode('gui-tags-'+kind,'metadata-editing',[
            step('tag','Add the tag ocean to '+('Atlas chapter 1' if kind=='book' else 'Atlas')+'.','The new tag ocean is visibly associated with the '+kind+'.',[go('/'+kind+'/${'+key+'.id}'),{'op':'edit','kind':kind},click('Tags'),{'op':'tag-add','value':'ocean'},{'op':'save'},go('/'+kind+'/${'+key+'.id}')],request(api,fields=['metadata.tags'],contains={'metadata.tags':['ocean']}),visible=['Ocean']),
            step('refresh','Refresh the details.','The saved ocean tag remains visible.',[{'op':'reload'}],visible=['Ocean'],depends=['tag']),
        ]))
    # Follow visible metadata links: filters must narrow real, mixed-population fixtures.
    steps=[]
    for key,text,expected in [('publisher','North Press',['Atlas','Café 漫画','Evergreen']),('genre','Adventure',['Atlas','Delta']),('language','English',['Atlas','Delta']),('writer','Ada Rivers',['Atlas','Delta'])]:
        steps.append(step(key,'From Atlas details, browse other series with the same '+key+' '+text+'.','The library is filtered to series matching '+text+'.',[go('/series/${s0.id}'),click(text)],visible=expected))
    w.append(episode('gui-metadata-filters','filtering',steps))
    return w
