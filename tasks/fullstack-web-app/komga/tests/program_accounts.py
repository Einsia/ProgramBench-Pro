from program import Builder,request
from common import AUTH,READER


def build():
    b=Builder('api-accounts')
    b.get('admin-identity','/api/v2/users/me',fields=['email','roles','sharedAllLibraries'])
    b.get('claimed','/api/v1/claim',auth=None,fields=['isClaimed'])
    b.get('claim-twice','/api/v1/claim',method='POST',auth=None,headers={'X-Komga-Email':'second@example.test','X-Komga-Password':'Another!'},status=400)
    b.get('create-reader','/api/v2/users',method='POST',body={'email':READER[0],'password':READER[1],'roles':['PAGE_STREAMING','FILE_DOWNLOAD']},save='reader',fields=['email','roles'])
    for who,auth in [('admin',AUTH),('reader',READER),('anonymous',None),('wrong',[READER[0],'Wrong!'])]:
        for path in ['/api/v2/users/me','/api/v2/users','/api/v1/settings','/api/v1/libraries','/api/v2/users/me/api-keys']:
            status=401 if who in ('anonymous','wrong') else 403 if who=='reader' and path=='/api/v2/users' else 200
            fields=['email','roles'] if path.endswith('/me') and status==200 else None
            b.get(who+'-'+path.replace('/','-'),path,auth=auth,status=status,**({'fields':fields} if fields else {}))
    for i,(email,password) in enumerate([('not-an-email','valid'),('valid@example.test',''),(READER[0],'new-password')]):
        b.get('invalid-user-'+str(i),'/api/v2/users',method='POST',body={'email':email,'password':password,'roles':[]},status=400)
    for i,roles in enumerate([[],['PAGE_STREAMING'],['FILE_DOWNLOAD'],['ADMIN'],['PAGE_STREAMING','FILE_DOWNLOAD']]):
        b.add('roles-'+str(i),{'kind':'mutation','write':request('/api/v2/users/${reader.id}','PATCH',{'roles':roles}),'read':request('/api/v2/users/me',auth=READER,fields=['roles','sharedAllLibraries'])})
    for i,restriction in enumerate([{'ageRestriction':{'age':12,'restriction':'ALLOW_ONLY'}},{'ageRestriction':{'age':18,'restriction':'EXCLUDE'}},{'ageRestriction':None},{'labelsAllow':['family','school']},{'labelsExclude':['adult']},{'labelsAllow':None,'labelsExclude':None},{'sharedLibraries':{'all':False,'libraryIds':[]}},{'sharedLibraries':{'all':True,'libraryIds':[]}}]):
        b.add('restriction-'+str(i),{'kind':'mutation','write':request('/api/v2/users/${reader.id}','PATCH',restriction),'read':request('/api/v2/users/me',auth=READER)})
    for i,password in enumerate(['New-Password-2026!','Unicode-密碼-Ω']):
        old=READER[1] if i==0 else 'New-Password-2026!'
        b.add('password-'+str(i),{'kind':'compound','steps':[request('/api/v2/users/${reader.id}/password','PATCH',{'password':password}),request('/api/v2/users/me',auth=[READER[0],password],fields=['email']),request('/api/v2/users/me',auth=[READER[0],old],status=401)]})
    b.add('password-restore',{'kind':'mutation','write':request('/api/v2/users/${reader.id}/password','PATCH',{'password':READER[1]}),'read':request('/api/v2/users/me',auth=READER,fields=['email'])})
    for i,label in enumerate(['Reader client','Tablet client','阅读 Ω']):
        b.get('key-create-'+str(i),'/api/v2/users/me/api-keys',method='POST',body={'comment':label},auth=READER,save='key'+str(i),fields=['comment'])
    b.get('duplicate-key-comment','/api/v2/users/me/api-keys',method='POST',body={'comment':'Reader client'},auth=READER,status=400)
    b.get('keys-list','/api/v2/users/me/api-keys',auth=READER,unordered=True)
    for i in range(3):
        b.get('key-auth-'+str(i),'/api/v2/users/me',auth=None,headers={'X-API-Key':'${key'+str(i)+'.key}'},fields=['email','roles'])
        b.get('key-delete-'+str(i),'/api/v2/users/me/api-keys/${key'+str(i)+'.id}',method='DELETE',auth=READER)
        b.get('key-revoked-'+str(i),'/api/v2/users/me',auth=None,headers={'X-API-Key':'${key'+str(i)+'.key}'},status=401)
    b.get('delete-reader','/api/v2/users/${reader.id}',method='DELETE')
    b.get('deleted-login','/api/v2/users/me',auth=READER,status=401)
    b.get('self-delete','/api/v2/users/${admin.id}',method='DELETE',status=403)
    for cp in b.cases:
        if cp['id']!='create-reader' and any(x in str(cp['spec']) for x in ('reader@example.test','${reader.')):cp['depends_on'].append('create-reader')
        if cp['id'].startswith('key-revoked-'):cp['depends_on'].append(cp['id'].replace('key-revoked-','key-delete-'))
        if cp['id']=='deleted-login':cp['depends_on'].append('delete-reader')
        if cp['id'].startswith('password-1'):cp['depends_on'].append('password-0')
    return [b.build()]
