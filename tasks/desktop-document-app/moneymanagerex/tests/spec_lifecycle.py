"""New ledgers, save-as copies, encryption and database maintenance."""
from spec_common import episode,step,row,rows,info,document,count,inbox,outbox


def build():
    result=[]
    key='database-new'
    result.append(episode(key,'database',[
        step('create',f'Create a new database at {outbox(key)}/fresh.mmb with US dollar as base currency and user name River Household. Complete the offered account wizard with a Checking account named Starter Cash and initial balance 250.',
             'The new database dashboard lists Starter Cash with balance 250.',
             [{'op':'new-database','path':'outbox/fresh.mmb'}, {'op':'new-account','name':'Starter Cash','wizard_open':True},
              {'op':'account-dialog','balance':'250'}],
             [info('USERNAME','River Household',file='fresh.mmb',area='outbox'),row('account',{'name':'Starter Cash'},file='fresh.mmb',area='outbox',
                   type='Checking',currency='USD',balance=250)]),
        step('save-as',f'Save a separate copy of the open database to {outbox(key)}/household-copy.mmb, keeping it unencrypted.',
             'The application opens the saved copy and still shows Starter Cash with balance 250.',
             [{'op':'menu','path':['File','Save Database As…']},{'op':'file-dialog','path':'outbox/household-copy.mmb'},{'op':'wait','seconds':1}],
             [row('account',{'name':'Starter Cash'},file='household-copy.mmb',area='outbox',type='Checking',balance=250),
              info('USERNAME','River Household',file='household-copy.mmb',area='outbox')],depends=['create']),
    ],ledger=None))
    key='database-encryption'
    result.append(episode(key,'database',[
        step('encrypt',f'Save the current database as an encrypted database at {outbox(key)}/secure.emb with password river-copper-26.',
             'The encrypted database opens and displays the existing account dashboard.',
             [{'op':'save-encrypted','path':'outbox/secure.emb','password':'river-copper-26'}],
             [[{'kind':'encrypted','file':'secure.emb','area':'outbox','slug':'encrypted-document',
                'password':'river-copper-26','wrong_password':'incorrect-copper',
                'description':'The encrypted document authenticates and decodes with the correct password only, preserving all ledger data.'}]]),
        step('wrong-password',f'Try to open {outbox(key)}/secure.emb with the incorrect password wrong-password. Leave the rejection message visible.',
             'The application rejects the incorrect password and does not open the ledger.',
             [{'op':'press','key':'Control+o'},{'op':'file-dialog','path':'outbox/secure.emb'},
              {'op':'text-prompt','window':'MMEX: Encrypted Database','value':'wrong-password'}],
             depends=['encrypt'],modal_end=True,requires={'visible':['encrypt/encrypted-document','decrypt/trx-june-split-shop-amount']}),
        step('reopen',f'Dismiss the password error, then open {outbox(key)}/secure.emb with the correct password river-copper-26.',
             'The reopened encrypted ledger displays the original accounts and balances.',
             [{'op':'alert','button':'OK'},{'op':'button','window':'Money Manager Ex 1.9.4 64-bit','name':'Open Existing Database'},
              {'op':'file-dialog','path':'outbox/secure.emb'},
              {'op':'text-prompt','window':'MMEX: Encrypted Database','value':'river-copper-26'}, {'op':'wait','seconds':1}],depends=['encrypt']),
        step('decrypt',f'Use the database decryption operation on {outbox(key)}/secure.emb with its password, saving the unencrypted result to {outbox(key)}/decrypted.mmb.',
             'The decrypted database opens with the original accounts and transaction information.',
             [{'op':'menu','path':['Tools','Database','Decrypt Encrypted Database…']}, {'op':'file-dialog','path':'outbox/secure.emb'},
              {'op':'text-prompt','window':'MMEX: Encrypted Database','value':'river-copper-26'}, {'op':'file-dialog','path':'outbox/decrypted.mmb'},
              {'op':'alert','button':'OK'}, {'op':'press','key':'Control+o'}, {'op':'file-dialog','path':'outbox/decrypted.mmb'}, {'op':'wait','seconds':1}],
             [row('trx',{'notes':'June split shop'},file='decrypted.mmb',area='outbox',amount=95.2,payee='Grocer'),
              row('account',{'name':'Everyday Checking'},file='decrypted.mmb',area='outbox',balance=2500,currency='USD')],depends=['reopen']),
    ]))
    key='database-optimize'
    result.append(episode(key,'database',[
        step('optimize','Optimize the current database through the database tools. Leave the result visible.',
             'The optimization result reports a smaller database, with the ledger contents preserved.',
             [{'op':'menu','path':['Tools','Database','Optimize Database…']}, {'op':'alert','button':'Yes'}, {'op':'wait','seconds':1}],
             [row('trx',{'notes':'June split shop'},amount=95.2,category=''),count('trx',{},17),
              [{'kind':'compact','slug':'unused-pages-reclaimed','description':'Optimization reclaims unused pages and reduces document size.',
                'expect':{'reclaimed':True,'valid':True}}]],modal_end=True),
    ],ledger='fragmented'))
    result[-1]['checkpoints'][0]['measure_database']={'file':'ledger.mmb'}
    return result
