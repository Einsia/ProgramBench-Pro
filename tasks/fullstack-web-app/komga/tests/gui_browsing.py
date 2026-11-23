from specification import episode,step,go,click,fill
from program import request


def build():
    w=[]
    steps=[]
    for name,title,path,text in [('all-series','Browse all series','/libraries/all/series',['Atlas','Beacon','Café 漫画','Delta','Evergreen','Folio']),('all-books','Browse all books','/libraries/all/books',['Atlas chapter 1','Beacon chapter 1']),('collections','Browse collections','/libraries/all/collections',['Shared World','Other Worlds']),('readlists','Browse reading lists','/libraries/all/readlists',['Opening arc','Later arc'])]:
        steps.append(step(name,title+'.',title+' shows the corresponding populated catalog.',[go(path)],visible=text))
    w.append(episode('gui-catalogs','catalog-navigation',steps))
    steps=[]
    for i,query in enumerate(['Atlas','café','Beacon','chapter 2']):
        steps.append(step('query-'+str(i),'Search the library for '+repr(query)+'.','Visible results match '+repr(query)+' and retain the matching titles.',[go('/dashboard'),fill('Search',query),{'op':'press','key':'Enter'},{'op':'wait','seconds':1}],visible=[query] if query!='café' else ['Café']))
    w.append(episode('gui-search','search',steps))
    path='/book/${b01.id}/read'
    steps=[step('start','Open Atlas chapter 1 in the comic reader at its first page.','The reader displays the first red comic page.',[go(path),{'op':'wait','seconds':1}],request('/api/v1/books/${b01.id}',fields=['readProgress.page'],want={'readProgress':{'page':1}}))]
    for page in (2,3,4):
        steps.append(step('page-'+str(page),'Advance to page '+str(page)+' of the current comic.','The comic reader displays page '+str(page)+' with the appropriate page image.',[{'op':'press','key':'ArrowRight'},{'op':'wait','seconds':.5}],request('/api/v1/books/${b01.id}',fields=['readProgress.page','readProgress.completed'],want={'readProgress':{'page':page}}),depends=[steps[-1]['id']]))
    steps.append(step('return','Return to the details of Atlas chapter 1 after finishing it.','The book details indicate that reading is complete.',[go('/book/${b01.id}')],request('/api/v1/books/${b01.id}',fields=['readProgress.completed'],want={'readProgress':{'completed':True}}),visible=['Atlas chapter 1'],depends=['page-4']))
    w.append(episode('gui-reader','comic-reader',steps))
    w.append(episode('gui-reader-incognito','comic-reader',[
        step('read','Open Atlas chapter 2 in incognito reading mode.','The comic opens in the reader with incognito mode visibly identified.',[go('/book/${b02.id}/read?incognito=true'),{'op':'point','x':640,'y':450}],request('/api/v1/books/${b02.id}',fields=['readProgress'],want={'readProgress':None})),
        step('advance','Advance to the second page in incognito mode.','The second page is displayed while incognito mode remains active.',[{'op':'press','key':'ArrowRight'},{'op':'wait','seconds':.5}],request('/api/v1/books/${b02.id}',fields=['readProgress'],want={'readProgress':None}),depends=['read']),
        step('return','Return to the book details.','Atlas chapter 2 is still presented as unread.',[go('/book/${b02.id}')],request('/api/v1/books/${b02.id}',fields=['readProgress'],want={'readProgress':None}),visible=['Atlas chapter 2'],depends=['advance']),
    ]))
    for kind,key,title in [('pdf','Vector','Vector'),('epub','Journal','Harbor Journal')]:
        path='/book/${books.'+key+'.id}'
        w.append(episode('gui-'+kind,'document-reader',[
            step('details','Open the '+kind.upper()+' book '+title+'.','The document details show its title and format.',[go(path)],visible=[title,kind.upper()]),
            step('read','Open '+title+' for reading.','The reader displays the document’s first page or chapter.',[go(path+('/read-epub' if kind=='epub' else '/read')),{'op':'wait','seconds':2}],visible=['The sailors arrive'] if kind=='epub' else (),depends=['details']),
            step('return','Return to '+title+' details.','The document remains accessible with its title and format.',[go(path)],visible=[title,kind.upper()],depends=['read']),
        ],formats=True))
    steps=[]
    for i,(label,path,terms) in enumerate([('book analysis','/media-management/analysis',['Media Analysis','Broken']),('duplicate file analysis','/media-management/duplicate-files',['Duplicate','Copy']),('history','/history',['Atlas','Atlas chapter 3'])]):
        steps.append(step('view-'+str(i),'Inspect the '+label+' page for this populated library.','The '+label+' page visibly presents the corresponding results or records.',[go(path)],visible=terms))
    w.append(episode('gui-media-history','media-administration',steps,setup=[{'id':'bad-media','kind':'bad-media'}]))
    return w
