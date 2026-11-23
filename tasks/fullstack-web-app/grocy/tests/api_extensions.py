"""Typed custom fields, user-defined objects, data files, calendar and system interfaces."""
import datetime
import hashlib
import re
import struct
import zlib
import io
from PIL import Image
from harness import Ref,pathref,resolve,b64,unordered,subset
from common import foundation,fx,product,objpath,readback
from api_stock import route,LOG_FIELDS


PALETTES = [((220,35,45),(25,185,65),(35,55,210),(240,190,30)),
            ((30,180,190),(180,30,160),(230,110,20),(35,190,70)),
            ((90,30,200),(220,150,25),(20,145,60),(190,35,55)),
            ((25,75,160),(190,30,90),(140,195,40),(215,125,35)),
            ((210,75,15),(45,155,190),(120,35,160),(65,200,85))]


def png(width=24,height=12,palette=0):
    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    colors=PALETTES[palette]
    rows=b''.join(b'\0'+b''.join(bytes(colors[(2 if y>=height//2 else 0)+(1 if x>=width//2 else 0)]) for x in range(width)) for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')


def image_observation(content,palette):
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            assert image.format=='PNG','expected PNG'
            width,height=image.size
            assert 1<=width<=100 and 1<=height<=100,'unexpected decoded dimensions'
            rgb=image.convert('RGBA')
            points=[(0,0),(width-1,0),(0,height-1),(width-1,height-1)]
            for point,color in zip(points,PALETTES[palette]):
                pixel=rgb.getpixel(point)
                assert pixel[3]>=250 and max(abs(a-b) for a,b in zip(pixel[:3],color))<=24,'resized content differs from input pattern'
    except (OSError,ValueError,SyntaxError) as exc:
        raise AssertionError('invalid or truncated PNG output') from exc
    return {'width':width,'height':height,'input_pattern_preserved':True}


def calendar(c,path='calendar/ical',actor='admin'):
    r,p=c.request('GET',path,actor=actor)
    assert r.status_code==200 and 'BEGIN:VCALENDAR' in r.text,'not an iCalendar document'
    unfolded=re.sub(r'\r?\n[ \t]','',r.text)
    events=[]
    for block in unfolded.split('BEGIN:VEVENT')[1:]:
        event={}
        for line in block.split('END:VEVENT')[0].splitlines():
            if ':' not in line:continue
            key,value=line.split(':',1)
            if key.split(';')[0] in ('SUMMARY','DTSTART','DTEND','DURATION','DESCRIPTION'):
                event[key]=value
        assert event.get('SUMMARY') and any(k.startswith('DTSTART') for k in event),'calendar event lacks its title/date'
        events.append(event)
    assert events,'calendar fixtures must produce events'
    return {'events':unordered(events)}


def build(s):
    f=foundation(s)
    variants=[('text-single-line',['Alpha Ω','Beta']),('text-multi-line',['First\nSecond','Third\nFourth']),
      ('number-integral',['0','-12']),('number-decimal',['0.125','-3.75']),('number-currency',['12.50','0']),
      ('date',['2026-03-10','2024-02-29']),('datetime',['2026-03-10 09:00:00','2026-04-01 15:30:00']),
      ('checkbox',['1','0']),('preset-list',['Red','Blue']),('preset-checklist',['Red,Blue','Green']),
      ('link',['https://example.test/manual','https://example.test/guide']),
      ('link-with-title',['https://example.test/manual;Manual','https://example.test/guide;Guide']),
      ('file',['guide.pdf','readme.txt']),('image',['front.png','back.jpg'])]
    for kind,values in variants:
        s.needs=list(f['needs'])
        ef,e=fx(s,kind,'equipment',{'name':'Custom '+kind},'equipment-'+kind)
        uf,u=fx(s,kind,'userfields',{'entity':'equipment','name':'field_'+kind.replace('-','_'),'caption':'Field '+kind,
             'type':kind,'config':'Red,Blue,Green' if kind.startswith('preset') else '',
             'show_as_column_in_tables':1,'input_required':1,'sort_number':3},'field-'+kind)
        retkey='retained_'+kind.replace('-','_')
        guard,_=fx(s,kind,'userfields',{'entity':'equipment','name':retkey,'caption':'Retained label','type':'text-single-line'},'retained-'+kind)
        s.needs=[ef,uf,guard]
        key='field_'+kind.replace('-','_');path=pathref('userfields/equipment/{id}',id=e)
        previous=None
        for index,value in enumerate(values):
            previous=s.api('userfields',kind,'value-'+str(index),'PUT',path,body={key:value,retkey:'Keep '+kind},status=204,
                           after=readback(path,[key,retkey],{key:value,retkey:'Keep '+kind}))
            s.api('userfields',kind,'object-projection-'+str(index),'GET',objpath('equipment',e),fields=['name','userfields'],hint='equipment',needs=[previous])
        s.api('userfields',kind,'unknown-field','PUT',path,body={'undefined_field':'not defined'},status=400,requires=[previous],after=readback(path,[key],{key:values[-1]}))
        removed=s.api('userfields',kind,'remove-definition','DELETE',objpath('userfields',u),status=204,requires=[previous])
        s.api('userfields',kind,'other-fields-retained','GET',path,needs=[removed,previous],requires=[previous],
              want={retkey:'Keep '+kind},check=lambda c,r,p,key=key: assert_absent(p,key))
    # Custom collections use their documented userentity name in the userfield interface.
    s.needs=list(f['needs'])
    ef,e=fx(s,'custom','userentities',{'name':'books','caption':'Books','description':'Reading shelf','show_in_sidebar_menu':1},'books')
    uf,_=fx(s,'custom','userfields',{'entity':'userentity-books','name':'title','caption':'Title','type':'text-single-line'},'book-title')
    vf,_=fx(s,'custom','userfields',{'entity':'userentity-books','name':'rating','caption':'Rating','type':'number-integral'},'book-rating')
    of,o=fx(s,'custom','userobjects',{'userentity_id':e},'book')
    s.needs=f['needs']+[ef,uf,vf,of]
    path=pathref('userfields/userentity-books/{id}',id=o)
    a=s.api('custom','collection','write','PUT',path,body={'title':'A book Ω','rating':'4'},status=204,after=readback(path,['title','rating'],{'title':'A book Ω','rating':'4'}))
    s.api('custom','collection','partial-update','PUT',path,body={'rating':'5'},status=204,needs=[a],after=readback(path,['title','rating'],{'title':'A book Ω','rating':'5'}))
    s.api('custom','collection','list','GET','objects/userobjects',params={'query[]':pathref('userentity_id={id}',id=e)},fields=['userentity_id'],hint='userobjects')
    # Same basenames coexist in all five groups, with different text and image content.
    groups=['equipmentmanuals','recipepictures','productpictures','userfiles','userpictures']
    uploads={};images={}
    for index,group in enumerate(groups):
        s.needs=[]
        content=('Document '+group+'\nUnicode Ω 中文\n').encode()
        uploads[group]=s.api('files',group,'upload','PUT','files/'+group+'/'+b64('shared.txt'),raw=content,content_type='application/octet-stream',status=204)
        images[group]=s.api('files',group,'image-upload','PUT','files/'+group+'/'+b64('picture.png'),raw=png(palette=index),content_type='image/png',status=204)
    for index,group in enumerate(groups):
        content=('Document '+group+'\nUnicode Ω 中文\n').encode();path='files/'+group+'/'+b64('shared.txt');uploaded=uploads[group]
        def exact(c,r,p,expected=content):assert r.content==expected,'file bytes changed or groups share storage'
        s.api('files',group,'read','GET',path,hint='bytes',check=exact,needs=[uploaded])
        s.api('files',group,'download-name','GET',path+'_'+b64('renamed.txt'),hint='bytes',check=exact,needs=[uploaded])
        s.api('files',group,'duplicate-refused','PUT',path,raw=b'Other bytes',content_type='application/octet-stream',status=400,requires=[uploaded],needs=[uploaded])
        s.api('files',group,'original-preserved','GET',path,hint='bytes',check=exact,needs=[uploaded])
        imagepath='files/'+group+'/'+b64('picture.png')
        for label,params in [('width',{'best_fit_width':6}),('fit',{'best_fit_width':8,'best_fit_height':8}),('large',{'best_fit_width':100,'best_fit_height':100})]:
            def dimension(c,path=imagepath,params=params,index=index):
                r,p=c.request('GET',path,params={'force_serve_as':'picture',**params})
                assert r.status_code==200,'image response failed'
                return image_observation(r.content,index)
            s.add('images',group,label,dimension,needs=[images[group]],description='Decode resized image and preserve quadrant pattern in '+group+' '+label)
    for index,group in enumerate(groups):
        path='files/'+group+'/'+b64('shared.txt');imagepath='files/'+group+'/'+b64('picture.png')
        deleted=s.api('files',group,'delete','DELETE',path,status=204,needs=[uploads[group]],requires=[uploads[group]])
        s.api('files',group,'gone','GET',path,status=404,needs=[deleted],requires=[uploads[group]])
        removed=s.api('files',group,'remove-image','DELETE',imagepath,status=204,needs=[images[group]],requires=[images[group]])
        s.api('files',group,'resized-gone','GET',imagepath,params={'force_serve_as':'picture','best_fit_width':6},status=404,needs=[removed],requires=[images[group]])
        for survivor in groups[index+1:]:
            si=groups.index(survivor)
            def retained(c,survivor=survivor,si=si):
                r,p=c.request('GET','files/'+survivor+'/'+b64('shared.txt'))
                assert r.status_code==200 and r.content==('Document '+survivor+'\nUnicode Ω 中文\n').encode(),'deleting one group changed another'
                rr,_=c.request('GET','files/'+survivor+'/'+b64('picture.png'),params={'force_serve_as':'picture','best_fit_width':6})
                assert rr.status_code==200,'other group image cache removed'
                return {'text_preserved':True,'image':image_observation(rr.content,si)}
            s.add('file-isolation',group,'preserve-'+survivor,retained,needs=[deleted,removed,uploads[survivor],images[survivor]],description='Deleting '+group+' preserves same-basename data and resize cache in '+survivor)
    # Time offsets are relative to the same running clock; compare offset arithmetic, not ticking seconds.
    s.needs=[]
    for offset in [0,3600,-3600,86400,-86400,19800]:
        def timecheck(c,offset=offset):
            before,b=c.request('GET','system/time');r,p=c.request('GET','system/time',params={'offset':offset})
            after,a=c.request('GET','system/time')
            assert all(x.status_code==200 for x in [before,r,after]),'time endpoint failed'
            assert b['timestamp']+offset<=p['timestamp']<=a['timestamp']+offset,'incorrect offset arithmetic'
            assert p['offset']==offset,'offset not returned'
            return {'timezone':p['timezone'],'offset':p['offset'],'day':p['time_local'][:10]}
        s.add('system','time','offset-'+str(offset).replace('-','minus'),timecheck,description='System clock UTC offset '+str(offset))
    s.api('system','time','invalid-offset','GET','system/time',params={'offset':'invalid'},status=400)
    s.api('system','settings','aggregate','GET','user/settings',fields=['night_mode','stock_due_soon_days','calendar_color_products'],hint='user-settings')
    s.api('system','settings','config','GET','system/config',fields=['MODE','DEFAULT_LOCALE','CURRENCY','ENERGY_UNIT','BASE_PATH','BASE_URL',
          'FEATURE_FLAG_STOCK','FEATURE_FLAG_RECIPES','FEATURE_FLAG_CHORES','FEATURE_FLAG_TASKS','FEATURE_FLAG_BATTERIES','FEATURE_FLAG_CALENDAR'])
    def api_spec(c):
        r,p=c.request('GET','openapi/specification')
        assert r.status_code==200 and isinstance(p,dict),'OpenAPI document missing'
        assert 'paths' in p and '/objects/{entity}' in p['paths'],'OpenAPI paths missing'
        return {'interfaces':sorted(p['paths']), 'entities':sorted(p['components']['schemas']['ExposedEntity']['enum'])}
    s.add('system','documentation','openapi',api_spec,description='Machine-readable API interface and exposed entity documentation')
    # Export a populated calendar and exercise its narrowly scoped public sharing token.
    s.needs=list(f['needs'])
    pf,p=fx(s,'calendar','products',product(f,'Calendar milk'),'calendar-p')
    tf,t=fx(s,'calendar','tasks',{'name':'Calendar appointment','due_date':'2026-03-12 12:00:00'},'calendar-t')
    rf,r=fx(s,'calendar','recipes',{'name':'Calendar supper'},'calendar-r')
    mf,m=fx(s,'calendar','meal_plan',{'day':'2026-03-13','recipe_id':r,'type':'recipe','section_id':f['section']},'calendar-m')
    nf,n=fx(s,'calendar','meal_plan',{'day':'2026-03-14','type':'note','note':'Guests Ω','section_id':f['section']},'calendar-n')
    stock=s.api('calendar-fixture','stock','purchase','POST',route(p,'/add'),body={'amount':2,'best_before_date':'2026-03-15'})
    s.needs=f['needs']+[pf,tf,rf,mf,nf,stock]
    exported=s.add('calendar','export','events',calendar,description='iCalendar dates, event types and escaped titles for stock, tasks and meals')
    def sharing(c):
        r,p=c.request('GET','calendar/ical/sharing-link')
        assert r.status_code==200 and p.get('url'),'sharing URL missing'
        from urllib.parse import urlsplit
        parsed=urlsplit(p['url']);path=parsed.path+'?'+parsed.query
        assert path.startswith('/api/calendar/ical?secret='),'unexpected sharing URL'
        c.state['calendar-link']=path
        return calendar(c,path,actor=None)
    shared=s.add('calendar','sharing','public-export',sharing,description='Calendar sharing link exports the same events without a login',needs=[exported])
    def scoped(c):
        from urllib.parse import parse_qs,urlsplit
        key=parse_qs(urlsplit(c.state['calendar-link']).query)['secret'][0]
        r,p=c.request('GET','objects/products',actor=None,headers={'GROCY-API-KEY':key})
        assert r.status_code==401,'calendar secret must not grant ordinary API access'
        return {'status':r.status_code}
    s.add('calendar','sharing','scope',scoped,description='Calendar-only token cannot read ordinary inventory API',needs=[shared],requires=[shared])


def assert_absent(value,key):
    assert key not in value,"deleted field is still present"
