"""Offline HTTP feed behavior through the runtime's public loopback fixture service."""
from spec_common import F,cache,cp,point,episode

BASE='http://127.0.0.1:48081'
FEED=F.rss('HTTP Feed',[F.item('First HTTP article','http-1',F.day(2),'Original body')])
UPDATED=F.rss('HTTP Feed',[F.item('Updated HTTP article','http-1',F.day(3),'Updated body'),
                           F.item('Second HTTP article','http-2',F.day(4),'New body')])

def requests(path=None,headers=None):
    result={'kind':'http_requests','fields':['path','method','status']}
    if path:result['path']=path
    if headers:result.update(fields=['path','headers'],headers=headers)
    return result


def make(name,routes,checkpoints,config=''):
    files={'.newsboat/urls':BASE+'/feed\n','.newsboat/config':config+'\n'}
    return episode(name,'http-feeds',checkpoints,files=files,load=False,
                    setup=[{'id':'http','op':'drive','steps':[{'http_source':routes}]}])


def build():
    out=[]
    for status in [200,301,302,307,308]:
        routes={'/feed':[{'status':status,'body':FEED,'headers':{'Content-Type':'application/rss+xml'}}]}
        if status!=200:
            routes['/feed'][0].update(body='',headers={'Location':'/target'})
            routes['/target']=[{'body':FEED,'headers':{'Content-Type':'application/rss+xml'}}]
        out.append(make('http-status-'+str(status),routes,[
            cp('reload','Load the HTTP feed with this status or redirect.',[{'cli':['-x','reload']}],
               [point('articles',cache('guid title content',nonempty=True)),point('requests',requests())])]))
    for name,headers in [('etag',{'ETag':'"feed-v1"'}),('modified',{'Last-Modified':'Mon, 01 Jan 2024 00:00:00 GMT'}),
                         ('both',{'ETag':'"feed-v1"','Last-Modified':'Mon, 01 Jan 2024 00:00:00 GMT'})]:
        out.append(make('http-conditional-'+name,{'/feed':[{'body':FEED,'headers':headers},{'status':304}]},[
            cp('load','Load and cache the feed validators.',[{'cli':['-x','reload']}],[point('articles',cache('guid title',nonempty=True))]),
            cp('not-modified','Reload using cached validators and a 304 response.',[{'cli':['-x','reload']}],
               [point('retained',cache('guid title',nonempty=True)),point('conditional-headers',requests('/feed',['If-None-Match','If-Modified-Since']))],depends=['load'])]))
    for status in [404,500]:
        out.append(make('http-error-'+str(status),{'/feed':[{'body':FEED},{'status':status,'body':'Unavailable'}]},[
            cp('load','Cache the first successful feed response.',[{'cli':['-x','reload']}],[point('articles',cache('guid title',nonempty=True))]),
            cp('error','Keep cached articles when reload fails.',[{'cli':['-x','reload']}],
               [point('retained',cache('guid title',nonempty=True)),point('status',requests())],depends=['load'])],config='download-retries 1'))
    out.append(make('http-content-update',{'/feed':[{'body':FEED},{'body':UPDATED}]},[
        cp('first','Load the initial feed.',[{'cli':['-x','reload']}],[point('articles',cache('guid title',nonempty=True))]),
        cp('update','Load changed content and a new article.',[{'cli':['-x','reload']}],
           [point('updated',cache('title content',{'guid':'http-1'},nonempty=True)),point('added',cache('title unread',{'guid':'http-2'},nonempty=True))],depends=['first'])]))
    for retries in [1,2]:
        out.append(make('http-retry-'+str(retries),{'/feed':[{'body':''},{'body':FEED}]},[
            cp('retry','Retry an empty HTTP response with the configured attempt limit.',[{'cli':['-x','reload']}],
               [point('requests',requests()),point('cache',cache('guid title'))])],config='download-retries '+str(retries)))
    out.append(make('http-custom-agent',{'/feed':[{'body':FEED}]},[
        cp('header','Send the configured HTTP user agent.',[{'cli':['-x','reload']}],
           [point('header',requests('/feed',['User-Agent'])),point('loaded',cache('guid title',nonempty=True))])],config='user-agent "Local reader"'))
    out.append(make('http-cookie-cache',{'/feed':[{'body':FEED,'headers':{'Set-Cookie':'reader=one; Path=/'}},{'body':FEED}]},[
        cp('first','Receive a cookie while fetching the feed.',[{'cli':['-x','reload']}],[point('loaded',cache('guid title',nonempty=True))]),
        cp('reuse','Send the stored cookie on the next reload.',[{'cli':['-x','reload']}],
           [point('cookie',requests('/feed',['Cookie']))],depends=['first'])],config='cookie-cache "cookies.txt"'))
    return out
