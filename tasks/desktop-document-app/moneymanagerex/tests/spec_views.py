"""Searching, filtered lists, transaction reports and account lifecycle."""
from spec_common import episode,step,row,count,document,outbox
M='Money Manager Ex'
F='Customize Transaction Report'


def build():
    result=[]
    result.append(episode('transaction-filters','filters',[
        step('category','In Everyday Checking filter transactions to category Food, including its subcategories.',
             'The filtered account contains grocery and dining transactions, including the relevant split transaction, and excludes salaries and rent.',
             [{'op':'nav','path':['Bank Accounts','Everyday Checking']}, {'op':'button','window':M,'name':'Filter…'},
              {'op':'check','window':F,'name':'Category'}, {'op':'fill','window':F,'label':'Category','value':'Food','entry':True},
              {'op':'check','window':F,'name':'Include all subcategories'}, {'op':'close','window':F}]),
        step('status','Replace the account filter with status Follow Up only.',
             'The filtered account shows May groceries for 187.75 as the only matching transaction.',
             [{'op':'button','window':M,'name':'Filter…'}, {'op':'button','window':F,'name':'Reset'},
              {'op':'button','window':M,'name':'Filter…'},
              {'op':'check','window':F,'name':'Status'}, {'op':'choose','window':F,'label':'Status','value':'Follow Up'}, {'op':'close','window':F}]),
        step('reset','Clear the advanced filter, then use the list search to find June rent.',
             'June rent is selected and its notes are visible below the account list.',
             [{'op':'button-described','window':M,'text':'Reset filter'}, {'op':'search','window':M,'value':'June rent'}, {'op':'press','key':'Return'}]),
    ]))
    key='transaction-report-payee'
    result.append(episode(key,'transaction-reports',[
        step('report',f'Generate a Transaction Report filtered to payee Grocer across all accounts, leaving split parts separate. Export it as HTML to {outbox(key)}/report.html.',
             'The report lists the Grocer transactions, including the two parts of June split shop, and a total withdrawal of 495.35.',
             [{'op':'open','path':['Tools','Transaction Report…'],'window':F}, {'op':'check','window':F,'name':'Payee'},
              {'op':'fill','window':F,'label':'Payee','value':'Grocer','entry':True}, {'op':'close','window':F}, {'op':'export-html'}],
             [document('outbox','report.html','html-row','total','The report total for Grocer.',label='Grand Total:',count=1,expect=[-495.35]),
              document('outbox','report.html','html-has','transactions','The report includes matching transaction notes.',texts=['April groceries','May groceries','June split shop'],expect=['April groceries','May groceries','June split shop'])]),
    ]))
    result.append(episode('account-close-reopen','accounts',[
        step('close','Change Rainy Day Savings to Closed, then show its saved account status again.',
             'The reopened account information shows Rainy Day Savings with status Closed.',
             [{'op':'edit-account','account':'Rainy Day Savings','status':'Closed'},
              {'op':'edit-account','account':'Rainy Day Savings','keep_open':True}], [row('account',{'name':'Rainy Day Savings'},status='Closed')],modal_end=True),
        step('reopen','Reopen Rainy Day Savings and rename it to Emergency Savings.',
             'The dashboard lists Emergency Savings with balance 8300.',
             [{'op':'close','window':'Edit Account'}, {'op':'edit-account','account':'Rainy Day Savings','status':'Open','name':'Emergency Savings'},
              {'op':'nav','path':['All Transactions']}, {'op':'nav','path':['Dashboard']}],
             [row('account',{'name':'Emergency Savings'},status='Open'),row('trx',{'notes':'May savings'},to_account='Emergency Savings')],depends=['close']),
    ]))
    return result
