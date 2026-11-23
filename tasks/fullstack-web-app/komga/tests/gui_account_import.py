from specification import episode,step,go,click,fill
from program import request
from common import READER

CBL=b'<ReadingList><Name>Ordered voyage</Name><Books><Book Series="Atlas" Number="3" Volume="2020"/><Book Series="Beacon" Number="1" Volume="2021"/></Books></ReadingList>'


def build():
    new='New-Reader-2026!'
    w=episode('gui-self-password','account-security',[
        step('change','Change your own reader@example.test password to New-Reader-2026!, then sign in with that new password.','The new password signs in successfully and the account page identifies reader@example.test.',[go('/account/me'),click('Change Password'),fill('New password',new),fill('Repeat new password',new),{'op':'click','text':'Change Password','nth':1},{'op':'logout'},{'op':'login','auth':[READER[0],new]},go('/account/me')],request('/api/v2/users/me',auth=[READER[0],new],fields=['email'],want={'email':READER[0]}),visible=[READER[0]]),
        step('refresh','Refresh the signed-in account page.','The reader account remains authenticated.',[{'op':'reload'}],visible=[READER[0]],depends=['change']),
        step('activity','Open your authentication activity and inspect your recent sign-in.','The account activity shows successful authentication for this reader.',[go('/account/authentication-activity')],visible=['Password'],depends=['change'])
    ],library=False,setup=[{'id':'reader','kind':'reader'}])
    w['auth']=READER;w['inputs']={'email':READER[0],'password':READER[1]}
    c=episode('gui-comicrack-import','comicrack-import',[
        step('match','Import the supplied read-order.cbl file and match its entries to your library.','The matched entries identify Atlas chapter 3 followed by Beacon chapter 1.',[go('/import/readlist'),{'op':'cbl-upload'},click('Match')],visible=['Atlas chapter 3','Beacon chapter 1']),
        step('create','Create the matched reading list named Ordered voyage, keeping the supplied order.','Ordered voyage contains the two matched books in the requested order.',[click('Create'),go('/libraries/all/readlists'),click('Ordered voyage')],request('/api/v1/readlists',where={'name':'Ordered voyage'},fields=['name','bookIds','ordered'],want={'bookIds':['${b03.id}','${b11.id}'],'ordered':True}),visible=['Ordered voyage','Atlas','Beacon'],depends=['match']),
        step('refresh','Refresh Ordered voyage.','The saved reading list retains both books and their order.',[{'op':'reload'}],visible=['Ordered voyage','Atlas','Beacon'],depends=['create'])
    ]);c['input_cbl']=True
    return [w,c]
