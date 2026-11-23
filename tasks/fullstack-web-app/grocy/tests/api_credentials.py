"""Public key usage and browser session lifecycle, with no private database reads."""
import urllib.parse
from harness import Ref,resolve,pathref
from api_users import userfixture
from reference.ui import UI

class BrowserSession:
    def __init__(self,broker,name):self.broker,self.name=broker,name
    def call(self,request):return self.broker.call({**request,'session':self.name})

def ui(c,name):return UI(BrowserSession(c.broker,name))

def key_on_page(browser,description):
    for line in browser.snapshot()['text'].splitlines():
        cells=[x.strip() for x in line.split('\t')]
        if description in cells:
            index=cells.index(description)
            assert index+1<len(cells) and cells[index+1],'key is not visible beside its description'
            return cells[index+1]
    raise AssertionError('generated key missing from public key list')

def create_key(c,name,owner,password):
    browser=ui(c,'keys-'+owner)
    if not c.state.get('browser-'+owner):browser.sign_in(owner,password);c.state['browser-'+owner]=True
    browser.goto('/manageapikeys');browser.click_button('Add');browser.fill(name,name='description');browser.click_button('OK')
    browser.require(name)
    key=key_on_page(browser,name);c.state[name]=key
    return {'key_created':bool(key)}

def read_as_key(c,name):
    r,p=c.request('GET','user',actor='token:'+name)
    assert r.status_code==200 and isinstance(p,list) and len(p)==1,'key did not authenticate'
    return {'username':p[0]['username']}

def revoke_key(c,name,owner):
    browser=ui(c,'keys-'+owner);browser.goto('/manageapikeys')
    browser.fill(name,placeholder='Search');browser.call('wait',seconds=1)
    browser.click(title='Delete this item');browser.click_button('Yes');browser.call('wait',seconds=.5)
    r,p=c.request('GET','user',actor='token:'+name)
    assert r.status_code==401,'revoked key still authenticates'
    return {'revoked_status':401}

def build(s):
    who,uid=userfixture(s,'keyowner','Key','Owner')
    first=s.add('credentials','admin','create',lambda c:create_key(c,'Admin tablet','admin','admin'),description='Create an administrator API key through its visible management form',needs=[])
    valid=s.add('credentials','admin','authenticate',lambda c:read_as_key(c,'Admin tablet'),description='A generated API key authenticates its administrator owner',needs=[first])
    s.api('credentials','admin','read-products','GET','objects/products',actor='token:Admin tablet',needs=[valid])
    def query_key(c):
        r,p=c.request('GET','user',actor=None,params={'GROCY-API-KEY':c.state['Admin tablet']})
        assert r.status_code==200 and p[0]['username']=='admin','documented query-key authentication failed'
        return {'query_auth_owner':'admin'}
    s.add('credentials','admin','query-auth',query_key,needs=[valid],description='API key query parameter authenticates the same owner')
    second=s.add('credentials','admin','second-key',lambda c:create_key(c,'Admin kitchen','admin','admin'),description='Create a second independent key',needs=[first])
    def distinct(c):
        assert c.state['Admin tablet']!=c.state['Admin kitchen'],'generated keys collide'
        return read_as_key(c,'Admin kitchen')
    second_valid=s.add('credentials','admin','second-auth',distinct,needs=[second],description='The second key is distinct and usable')
    revoked=s.add('credentials','admin','revoke-first',lambda c:revoke_key(c,'Admin tablet','admin'),needs=[valid,second_valid],description='Revoking one key prevents its further use')
    s.add('credentials','admin','other-survives',lambda c:read_as_key(c,'Admin kitchen'),needs=[revoked],description='Revoking the first key preserves the second key')
    # Owner permissions are evaluated on each API-key request.
    ownerkey=s.add('credentials','owner','create',lambda c:create_key(c,'Owner device','keyowner','Local-password-42!'),needs=who,description='Create a key belonging to another account')
    ownerauth=s.add('credentials','owner','authenticate',lambda c:read_as_key(c,'Owner device'),needs=[ownerkey],description='The other user key identifies its own account')
    hierarchy=s.api('credential-fixture','owner','hierarchy','GET','objects/permission_hierarchy',save='key-permissions',needs=[])
    def perm(c,name):return next(x['id'] for x in c.state['key-permissions'] if x['name']==name)
    stripped=s.api('credentials','owner','limit-permissions','PUT',pathref('users/{id}/permissions',id=uid),body={'permissions':[]},status=204,needs=[ownerauth])
    denied=s.api('credentials','owner','write-denied','POST','objects/locations',actor='token:Owner device',body={'name':'Key location'},status=[400,403],needs=[stripped])
    grant=s.api('credentials','owner','grant-master','POST',pathref('users/{id}/permissions',id=uid),body={'permission_id':lambda c:perm(c,'MASTER_DATA_EDIT')},status=204,needs=[denied,hierarchy])
    allowed=s.api('credentials','owner','write-allowed','POST','objects/locations',actor='token:Owner device',body={'name':'Key location'},save='key-location',hint='locations',needs=[grant])
    s.api('credentials','owner','saved-write','GET',pathref('objects/locations/{id}',id=Ref('key-location','created_object_id')),actor='token:Owner device',fields=['name'],want={'name':'Key location'},needs=[allowed])
    next(x for x in s.cases if x.id==denied).requires=(allowed,)
    restored=s.api('credentials','owner','restore-admin','PUT',pathref('users/{id}/permissions',id=uid),body={'permissions':[lambda c:perm(c,'ADMIN')]},status=204,needs=[allowed,hierarchy])
    s.add('credentials','owner','revoke',lambda c:revoke_key(c,'Owner device','keyowner'),needs=[restored],description='A user can revoke their generated key and authentication stops')
    # Browser sessions can be listed and revoked using the ordinary UI. The product API intentionally hides their rows.
    def session_login(c):
        browser=ui(c,'revocable');browser.sign_in('keyowner','Local-password-42!');browser.goto('/stockoverview')
        assert browser.url.startswith('/stockoverview'),'login did not create session'
        return {'authenticated_page':True}
    login=s.add('sessions','browser','login',session_login,needs=who+[restored],description='A new browser session signs in with correct account credentials')
    def list_sessions(c):
        browser=ui(c,'revocable');browser.goto('/user/'+str(resolve(uid,c))+'/sessions')
        browser.require('Sessions','This session','access')
        return {'current_session_listed':True}
    listed=s.add('sessions','browser','list',list_sessions,needs=[login],description='Session management visibly identifies the active browser session')
    def revoke_session(c):
        browser=ui(c,'revocable');snap=browser.snapshot()
        # The current session badge is visible text; use the row's public controls and geometry.
        browser.fill('This session',placeholder='Search');browser.call('wait',seconds=1)
        browser.click(title='Delete this item');browser.click_button('Yes');browser.call('wait',seconds=.5)
        browser.goto('/stockoverview');assert browser.url.startswith('/login'),'revoked browser session still enters stock overview'
        return {'revoked_requires_login':True}
    revoked_session=s.add('sessions','browser','revoke',revoke_session,needs=[listed],description='Revoking the current session requires signing in again')
    relog=s.add('sessions','browser','relogin',session_login,needs=[revoked_session],description='Correct credentials can create a new session after revocation')
    def logout(c):
        browser=ui(c,'revocable');browser.goto('/logout');browser.goto('/stockoverview')
        assert browser.url.startswith('/login'),'logout left session authenticated'
        return {'logged_out':True}
    s.add('sessions','browser','logout',logout,needs=[relog],description='Logout invalidates the browser session')
