"""Persisted preferences and user-defined transaction fields."""
from spec_common import episode,step,row,info,count

S='Settings'
M='Custom Field Manager'
F='New/Edit Custom Field'


def preferences():
    general=[{'op':'open','path':['Tools','Settings…'],'window':S}]
    result=[episode('settings-general','settings',[
        step('save','Set the database user name to Morgan Household, the displayed date format to DD/MM/YYYY, and the financial year start to April 6. Save and reopen Settings to display the saved general preferences.',
             'The general preferences show Morgan Household, DD/MM/YYYY, first day 6 and first month Apr.',
             general+[{'op':'fill','window':S,'label':'User Name','value':'Morgan Household'},
                      {'op':'choose','window':S,'value':'DD/MM/YYYY','nth':0},
                      {'op':'fill','window':S,'label':'First Day','role':'spin button','value':'6','commit':True},
                      {'op':'choose','window':S,'label':'First Month','value':'Apr'}, {'op':'close','window':S}]+general,
             [info('USERNAME','Morgan Household'),info('DATEFORMAT','%d/%m/%Y'),info('FINANCIAL_YEAR_START_DAY','6'),info('FINANCIAL_YEAR_START_MONTH','4')],modal_end=True),
        step('restart','After this restart, show the saved general preferences again.',
             'The restarted application retains the user name, date format and April 6 financial-year start.',
             general, lifecycle='restart',depends=['save'],modal_end=True),
    ])]
    result.append(episode('settings-transaction-defaults','settings',[
        step('defaults','In transaction preferences set Default Status to Follow Up, enable using the original date when duplicating transactions, and enable using time in transaction recording. Save and reopen the transaction preferences.',
             'The saved preferences show Follow Up as the default status and both requested date/time options enabled.',
             general+[{'op':'settings-tab','name':'Transactions'}, {'op':'choose','window':S,'label':'Default Status','value':'Follow Up'},
                      {'op':'check','window':S,'name':'Use Original Date when Duplicating Transactions'},
                      {'op':'check','window':S,'name':"Use 'Time' in transaction recording/reporting"}, {'op':'close','window':S}]+general+
                     [{'op':'settings-tab','name':'Transactions'}],modal_end=True),
        step('new','Create a withdrawal of 16.25 in Everyday Checking to Cafe Luna, with notes Timed coffee. Keep the offered status and date, but set its time to 09:30:00.',
             'The account view shows the new withdrawal with the follow-up status and its Timed coffee notes.',
             [{'op':'close','window':S}, {'op':'nav','path':['Bank Accounts','Everyday Checking']},
              {'op':'new-transaction','amount':'16.25','payee':'Cafe Luna','notes':'Timed coffee','button':None},
              {'op':'time','window':'New Transaction','value':'09:30:00'},
              {'op':'transaction-form','button':'Save'}],
             [row('trx',{'notes':'Timed coffee'},amount=16.25,status='F',time='09:30:00')],depends=['defaults']),
        step('duplicate','Duplicate April power in Everyday Checking, change only its notes to Copied historical bill, and save.',
             'The account view shows the copied City Power transaction with its Copied historical bill notes.',
             [{'op':'row','index':3}, {'op':'button','window':'Money Manager Ex','name':'Duplicate'},
              {'op':'transaction-form','notes':'Copied historical bill','button':'Save'}],
             [row('trx',{'notes':'Copied historical bill'},date='2026-04-20',amount=64.1,payee='City Power')],depends=['defaults']),
    ]))
    return result


def fields():
    add=[{'op':'open','path':['Tools','Custom Field Manager…'],'window':M}, {'op':'manager-menu','window':M,'name':'Add'}]
    return [episode('custom-field-manage','custom-fields',[
        step('define','Create a String custom field named Project, with tooltip Project reference and default General.',
             'The custom-field manager lists Project as a String field.',
             add+[{'op':'fill','window':F,'label':'Name','value':'Project'}, {'op':'fill','window':F,'label':'Tooltip','value':'Project reference'},
                  {'op':'fill','window':F,'label':'Default','value':'General'}, {'op':'close','window':F}],
             [row('field',{'description':'Project'},type='String',kind='Transaction',tooltip='Project reference',default='General')]),
        step('assign','Set Project to Apollo on the transaction April salary in Everyday Checking. Save and reopen that transaction with its custom fields visible.',
             'The reopened April salary transaction shows the checked Project field with value Apollo.',
             [{'op':'close','window':M,'button':'Close'}, {'op':'nav','path':['Bank Accounts','Everyday Checking']}, {'op':'row','index':0}, {'op':'press','key':'Return'},
              {'op':'custom-fields','values':{'Project':'Apollo'}}, {'op':'close','window':'Edit Transaction','button':'Save'},
              {'op':'row','index':0}, {'op':'press','key':'Return'}, {'op':'custom-fields'}],
             [row('trx',{'notes':'April salary'},fields={'Project':'Apollo'})],depends=['define'],modal_end=True),
        step('rename','Rename the custom field Project to Initiative, retaining its existing values.',
             'The custom-field manager lists Initiative in place of Project.',
             [{'op':'close','window':'Edit Transaction','button':'Cancel'}, {'op':'open','path':['Tools','Custom Field Manager…'],'window':M},
              {'op':'manager-menu','window':M,'name':'Edit'}, {'op':'fill','window':F,'label':'Name','value':'Initiative'}, {'op':'close','window':F}],
             [row('field',{'description':'Initiative'},type='String'),row('trx',{'notes':'April salary'},fields={'Initiative':'Apollo'})],depends=['assign']),
    ])]




def attachments():
    from spec_common import inbox,outbox
    key='transaction-attachments'
    return [episode(key,'attachments',[
        step('add',f'Set the attachment archive folder to {outbox(key)}, disable the automatic Attachments subfolder, and save the preferences. Attach {inbox(key)}/receipt.txt to April groceries in Everyday Checking with description Grocery receipt.',
             'The attachment manager for April groceries lists Grocery receipt.',
             [{'op':'open','path':['Tools','Settings…'],'window':S}, {'op':'settings-tab','name':'Attachments'},
              {'op':'fill-text','window':S,'value':outbox(key)}, {'op':'check','window':S,'name':'Create and use Attachments subfolder','value':False},
              {'op':'close','window':S}, {'op':'nav','path':['Bank Accounts','Everyday Checking']}, {'op':'row','index':2},
              {'op':'button-described','window':'Money Manager Ex','text':'Open attachments'},
              {'op':'manager-menu','window':'Attachment Manager','name':'Add'}, {'op':'file-dialog','path':'inbox/receipt.txt'},
              {'op':'text-prompt','window':'Attachment Manager: Add Attachment','value':'Grocery receipt'}],
             [row('trx',{'notes':'April groceries'},attachments=['Grocery receipt']),
              [{'kind':'attachment-content','input':'receipt.txt','slug':'archived-content','description':'The archived attachment contains exactly the uploaded bytes.'}]]),
        step('edit','Rename the attachment description to April grocery receipt.',
             'The attachment list shows April grocery receipt.',
             [{'op':'manager-menu','window':'Attachment Manager','name':'Edit'},
              {'op':'text-prompt','window':'Attachment Manager: Edit Attachment','value':'April grocery receipt'}],
             [row('trx',{'notes':'April groceries'},attachments=['April grocery receipt']),
              [{'kind':'attachment-content','input':'receipt.txt','slug':'content-preserved','description':'Renaming the description preserves the archived document.'}]],depends=['add']),
        step('remove','Remove the attachment, confirming removal of both the file and database entry if asked, then return to the transaction list with April groceries selected.',
             'April groceries remains a withdrawal of 212.40 and no longer indicates an attached receipt.',
             [{'op':'manager-menu','window':'Attachment Manager','name':'Remove'}, {'op':'alert','button':'Yes'}, {'op':'alert','button':'Yes'}, {'op':'close','window':'Attachment Manager'}],
             [row('trx',{'notes':'April groceries'},attachments=[]),
              [{'kind':'attachment-content','input':'receipt.txt','removed':True,'slug':'payload-removed','description':'Removing the attachment also removes its archived bytes.','expect':{'remaining_payloads':0}}]],depends=['edit']),
    ],files_in=['exchange/receipt.txt'])]




def typed_fields():
    return [episode('custom-field-types','custom-fields',[
        step('values','Set these custom fields on April salary in Everyday Checking: Units 7, Tax 12.375, Approved True, Phase Final and Due 07/01/2026. Enable each field, save, then show the saved custom fields again.',
             'The reopened transaction shows Units 7, Tax 12.375, Approved True, Phase Final and the due date July 1, 2026.',
             [{'op':'nav','path':['Bank Accounts','Everyday Checking']}, {'op':'row','index':0}, {'op':'press','key':'Return'},
              {'op':'custom-fields','values':{'Units':'7','Tax':'12.375','Due':'07/01/2026'},'booleans':{'Approved':True},'choices':{'Phase':'Final'}},
              {'op':'close','window':'Edit Transaction','button':'Save'}, {'op':'row','index':0}, {'op':'press','key':'Return'}, {'op':'custom-fields'}],
             [row('trx',{'notes':'April salary'},fields={'Units':'7','Tax':'12.375','Approved':'TRUE','Phase':'Final','Due':'2026-07-01'})],modal_end=True),
    ],ledger='typed-fields')]


def build():
    return preferences()+fields()+attachments()+typed_fields()
