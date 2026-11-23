'''Public export and backup bytes survive download, re-upload, import and restore.'''
import base64
from harness import Ref,pathref
from api_files import pattern_png,upload

FIELDS=['name','description','recipeServings','recipeIngredient','recipeInstructions','notes','nutrition']


def download(c,key,path):
    r,p=c.request('GET',path,actor=None if 'utils/download' in path else 'admin')
    assert r.status_code==200,'download failed'
    c.state[key]=r.content
    obs=c.archive(r.content)
    assert obs['is_zip'] and obs['members'],'empty or invalid exported archive'
    return obs


def build(s):
    a=s.api
    fx='roundtrip-fixture'
    a(fx,'data','recipe','POST','recipes',body={'name':'Travel Soup'})
    a(fx,'data','body','PATCH','recipes/travel-soup',body={
        'description':'Pack this recipe intact.','recipeServings':4,
        'recipeIngredient':[{'quantity':2,'note':'carrots'},{'quantity':3,'note':'tomatoes'}],
        'recipeInstructions':[{'summary':'Simmer','text':'Simmer for thirty minutes.'}],
        'notes':[{'title':'Packing','text':'Keep chilled.'}],'nutrition':{'calories':'240'}})
    a(fx,'data','image','PUT','recipes/travel-soup/image',multipart={
        'fields':{'extension':'png'},'files':{'image':upload('soup.png',pattern_png(),'image/png')}})
    a(fx,'data','read','GET','recipes/travel-soup',save='original')
    a(fx,'data','asset','POST','recipes/travel-soup/assets',multipart={
        'fields':{'name':'Travel notes','icon':'mdi-file','extension':'txt'},
        'files':{'file':upload('travel.txt',b'Use the insulated bag.\n','text/plain')}},save='asset')
    s.add('roundtrip','single','download',lambda c:download(c,'zip','recipes/travel-soup/exports?template_name=zip'))
    a('roundtrip','single','remove','DELETE','recipes/travel-soup',hint='none')
    a('roundtrip','single','import','POST','recipes/create/zip',status=201,
      multipart=lambda c:{'files':{'archive':upload('travel.zip',c.state['zip'],'application/zip')}})
    a('roundtrip','single','recipe','GET','recipes/travel-soup',fields=FIELDS,save='imported')
    a('roundtrip','single','image','GET',pathref('media/recipes/{r}/images/original.webp',r=Ref('imported','id')),
      actor=None,hint='image')
    a(fx,'backup','self','GET','users/self',save='backup-user')
    a(fx,'backup','avatar','POST',pathref('users/{u}/image',u=Ref('backup-user','id')),
      multipart={'files':{'profile':upload('backup-avatar.png',pattern_png(180,180),'image/png')}})
    a('roundtrip','backup','create','POST','admin/backups',status=201,hint='none')
    a('roundtrip','backup','list','GET','admin/backups',save='backups')
    a('roundtrip','backup','token','GET',pathref('admin/backups/{n}',n=Ref('backups','imports',0,'name')),save='backup-token')
    s.add('roundtrip','backup','download',lambda c:download(c,'backup','utils/download?token='+c.state['backup-token']['fileToken']))
    a('roundtrip','backup','remove','DELETE','recipes/travel-soup',hint='none')
    a('roundtrip','backup','upload','POST','admin/backups/upload',multipart=lambda c:{'files':{
        'archive':upload('downloaded-backup.zip',c.state['backup'],'application/zip')}})
    a('roundtrip','backup','restore','POST','admin/backups/downloaded-backup.zip/restore',hint='none')
    a('roundtrip','backup','recipe','GET','recipes/travel-soup',fields=FIELDS,save='restored')
    a('roundtrip','backup','image','GET',pathref('media/recipes/{r}/images/original.webp',r=Ref('restored','id')),actor=None,hint='image')
