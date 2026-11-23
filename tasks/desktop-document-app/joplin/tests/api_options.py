"""Explicit identities, conflicts, relative clipping URLs and resource reverse links."""
import time

from fixtures import png
from harness import Ref, Suite, aspects, b64, checked, project
from semantics import markdown_structure


def build():
    s=Suite('protocol-options','API identities conflicts and reverse relationships')
    def setup(c):
        c.call('POST','/folders',body={'title':'Options'},save='book')
        for key,extra in [('ordinary',{}),('conflict',{'is_conflict':1}),
                          ('deleted',{'deleted_time':1768478400000}),
                          ('both',{'is_conflict':1,'deleted_time':1768478400000})]:
            c.call('POST','/notes',body={'title':key,'body':'Option fixture '+key,'parent_id':Ref('book'),**extra},save=key)
            if extra:
                c.call('PUT','/notes/{'+key+'}',body=extra)
                actual=c.call('GET','/notes/{'+key+'}',query={'fields':','.join(extra)})['body']
                for field,wanted in extra.items():checked(actual[field],wanted)
    s.setup('options',setup)
    for index,nid in enumerate(['0123456789abcdef0123456789abcdef','abcdef0123456789abcdef0123456789']):
        key='explicit-'+str(index)
        def create(c,nid=nid,key=key):
            value=c.call('POST','/notes',body={'id':nid,'title':key,'body':'Explicit identity body','parent_id':Ref('book')},save=key)['body']
            return aspects(id=lambda:checked(value['id'],nid),title=lambda:value['title'],body=lambda:value['body'])
        s.add(key,'Create a note with an explicit hexadecimal ID',create,
              {'id':'The supplied ID is retained exactly.','title':'The title is saved.','body':'The body is saved.'},
              expected={'title':key,'body':'Explicit identity body'})
        s.request(key+'-read','Read the note using the supplied ID','GET','/notes/'+nid,
                  query={'fields':'id,title,body,parent_id'},fields=('id','title','body','parent_id'),depends=(key,))
    def duplicate(c):
        response=c.call('POST','/notes',body={'id':'0123456789abcdef0123456789abcdef','title':'Duplicate request'},ok=False)
        rows=c.all('/notes',fields='id,title',query={'include_conflicts':1,'include_deleted':1})
        return aspects(status=lambda:checked(response['status']>=400,True),
                       matching=lambda:project([x for x in rows if x['id']=='0123456789abcdef0123456789abcdef'],['id','title'],c))
    s.add('duplicate-id','Submit an already existing explicit note ID',duplicate,
          {'status':'An existing identity cannot be created a second time.','matching':'The original identity and title remain unchanged.'},
          depends=('explicit-0',),expected={'status':True})
    for deleted,conflicts in [(0,0),(0,1),(1,0),(1,1)]:
        def listing(c,deleted=deleted,conflicts=conflicts):
            rows=c.all('/notes',fields='id,title,is_conflict,deleted_time',
                       query={'include_deleted':deleted,'include_conflicts':conflicts})
            fixture={c.values[x]['id'] for x in ('ordinary','conflict','deleted','both')}
            rows=[x for x in rows if x['id'] in fixture]
            return aspects(members=lambda:project(rows,['id','title'],c),
                           conflicts=lambda:sorted(x['title'] for x in rows if x['is_conflict']),
                           deleted=lambda:sorted(x['title'] for x in rows if x['deleted_time']))
        s.add(f'listing-{deleted}-{conflicts}','List ordinary, conflict and trashed notes with explicit inclusion flags',listing,
              {'members':'The flags select the requested note classes.','conflicts':'Conflict inclusion is independent of trash.',
               'deleted':'Trash inclusion is independent of conflicts.'},
              expected={'conflicts':sorted((['conflict']+(['both'] if deleted else [])) if conflicts else []),
                        'deleted':sorted((['deleted']+(['both'] if conflicts else [])) if deleted else [])})
    for index,(base,url) in enumerate([
        ('https://example.invalid/guide/page','next.html'),
        ('https://example.invalid/guide/','../index.html'),
        ('https://example.invalid/guide/page','/root?q=oak#leaf'),
        ('https://example.invalid/guide/page','#section'),
        ('https://example.invalid/guide/page','https://other.invalid/destination')]):
        key='relative-link-'+str(index)
        s.request(key,'Resolve a clipped relative link against base_url','POST','/notes',save=key,
                  body={'title':key,'parent_id':Ref('book'),'base_url':base,
                        'body_html':'<p><a href="'+url+'">Destination</a></p>','convert_to':'markdown'},
                  fields=('body','markup_language'),transforms={'body':markdown_structure},expected={'markup_language':1})
        s.request(key+'-stored','Read the converted clipping from the stored note','GET','/notes/{'+key+'}',
                  query={'fields':'body,title'},fields=('body','title'),depends=(key,),transforms={'body':markdown_structure})
    def resource_setup(c):
        c.call('POST','/resources',multipart={'filename':'shared.png','base64':b64(png()),'props':{'title':'Shared diagram'}},save='resource')
        for key in ('image-one','image-two'):
            c.call('POST','/notes',body={'title':key,'parent_id':Ref('book'),
                       'body':'![Shared](:/'+c.values['resource']['id']+')'},save=key)
        end=time.monotonic()+120
        while True:
            value=c.call('GET','/resources/{resource}/notes')['body']
            items=value.get('items',value) if isinstance(value,dict) else value
            ids={x['id'] if isinstance(x,dict) else x for x in items}
            if ids=={c.values[x]['id'] for x in ('image-one','image-two')}:break
            if time.monotonic()>=end:raise AssertionError('resource relations did not settle')
            time.sleep(.5)
    s.setup('shared-resource',resource_setup,before='resource-notes')
    def reverse(c):
        value=c.call('GET','/resources/{resource}/notes')['body']
        items=value.get('items',value) if isinstance(value,dict) else value
        return {'notes':sorted(c.clean(x['id'] if isinstance(x,dict) else x) for x in items)}
    s.add('resource-notes','Read all notes referencing a shared resource',reverse,
          {'notes':'The reverse relation includes both note IDs.'},expected={'notes':['@image-one','@image-two']})
    return s
