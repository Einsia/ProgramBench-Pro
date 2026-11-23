'''Successful local password-reset and independent user ratings.'''
from harness import Ref,pathref


def build(s):
    a=s.api;fx='identity-fixture'
    for user in ['alice','bob']:
        a(fx,'users',user,'POST','admin/users',body={'username':user,'fullName':user.title(),'email':user+'@example.com',
          'password':user.title()+'Password1','admin':False},save=user,
          before=lambda c,u=user:c.creds.update({u:u.title()+'Password1'}))
    a(fx,'recipe','create','POST','recipes',body={'name':'Rated Soup'})
    a(fx,'recipe','read','GET','recipes/rated-soup',save='recipe')
    for user,rating in [('alice',2),('bob',5)]:
        a('identity-ratings',user,'set','POST',pathref('users/{i}/ratings/rated-soup',i=Ref(user,'id')),
          actor=user,body={'rating':rating,'isFavorite':user=='alice'},status=200)
        a('identity-ratings',user,'self','GET','users/self/ratings',actor=user,status=200)
        a('identity-ratings',user,'by-id','GET',pathref('users/{i}/ratings',i=Ref(user,'id')),actor=user,status=200)
    a('identity-ratings','aggregate','recipe','GET','recipes/rated-soup',fields=['rating'])
    a('identity-ratings','alice','change','POST',pathref('users/{i}/ratings/rated-soup',i=Ref('alice','id')),
      actor='alice',body={'rating':4,'isFavorite':False})
    a('identity-ratings','bob','unchanged','GET','users/self/ratings',actor='bob')
    a('identity-ratings','aggregate','changed','GET','recipes/rated-soup',fields=['rating'])
    a('identity-reset','token','generate','POST','admin/users/password-reset-token',body={'email':'alice@example.com'},status=201,save='reset')
    a('identity-reset','password','reset','POST','users/reset-password',actor=None,status=200,
      body={'token':Ref('reset','token'),'email':'alice@example.com','password':'NewAlicePassword2','passwordConfirm':'NewAlicePassword2'})
    a('identity-reset','password','old-refused','POST','auth/token',actor=None,status=401,
      form={'username':'alice','password':'AlicePassword1'})
    a('identity-reset','password','new-accepted','POST','auth/token',actor=None,status=200,
      form={'username':'alice','password':'NewAlicePassword2'},fields=['token_type'])
    a('identity-reset','password','other-unaffected','POST','auth/token',actor=None,status=200,
      form={'username':'bob','password':'BobPassword1'},fields=['token_type'])
    a('identity-reset','token','reuse','POST','users/reset-password',actor=None,status=None,
      body={'token':Ref('reset','token'),'email':'alice@example.com','password':'ReuseAlicePassword3','passwordConfirm':'ReuseAlicePassword3'})
