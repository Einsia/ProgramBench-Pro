"""Isolated restart episode using public API and independently checked bytes."""
import base64
from harness import Ref,pathref


def build(s):
    a=s.api;rp='repos/alice/durable'
    a('restart-fixture','repository','create','POST','user/repos','alice',body={'name':'durable','private':True,'auto_init':True},status=201)
    a('restart-fixture','writer','grant','PUT',rp+'/collaborators/bob','alice',body={'permission':'write'},status=204)
    a('restart-fixture','issue','create','POST',rp+'/issues','bob',body={'title':'Durable issue','body':'Durable body Ω'},status=201,save='durable-issue')
    a('restart-fixture','file','create','POST',rp+'/contents/keep.txt','bob',body={'content':base64.b64encode(b'durable file\n').decode(),'message':'Durable commit'},status=201,save='durable-file')
    a('restart-fixture','release','create','POST',rp+'/releases','alice',body={'tag_name':'v-durable','target_commitish':'main','name':'Durable release'},status=201,save='durable-release')
    a('restart-fixture','org','create','POST','orgs','alice',body={'username':'durable-org','visibility':'private'},status=201)
    a('restart-fixture','label','create','POST',rp+'/labels','alice',body={'name':'durable-label','color':'aabbcc'},status=201,save='durable-label')
    def restart(c):
        # Runtime op restart: a fresh process of the application on the same DATA_DIR.
        assert c.running(),'the application is not running before the restart'
        c.restart_server();assert c.running(),'the application is not running after the restart'
        return {'fresh_process':True,'same_data_directory':True}
    s.add('persistence','restart','process',restart,channel='restart',description='Restart the application without replacing DATA_DIR.')
    a('persistence','repository','read','GET',rp,'alice',status=200,want={'name':'durable','private':True})
    a('persistence','permission','read','GET',rp+'/collaborators/bob/permission','alice',status=200,want={'permission':'write'})
    a('persistence','issue','read','GET',pathref(rp+'/issues/{n}',n=Ref('durable-issue','number')),'bob',status=200,want={'title':'Durable issue','body':'Durable body Ω'})
    a('persistence','file','read','GET',rp+'/contents/keep.txt','bob',status=200,want={'content':base64.b64encode(b'durable file\n').decode()})
    a('persistence','release','read','GET',pathref(rp+'/releases/{id}',id=Ref('durable-release','id')),'alice',status=200,want={'name':'Durable release'})
    a('persistence','organization','read','GET','orgs/durable-org','alice',status=200,want={'username':'durable-org','visibility':'private'})
    a('persistence','label','read','GET',pathref(rp+'/labels/{id}',id=Ref('durable-label','id')),'alice',status=200,want={'name':'durable-label','color':'aabbcc'})
    a('persistence','denied','anonymous','GET',rp,None,status=404)
