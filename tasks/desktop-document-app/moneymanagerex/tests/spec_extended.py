"""Additional offline operations, their cancellation paths and retained data."""
from spec_common import episode, step, row, rows, count, document, inbox, outbox


def accounts():
    change = lambda name, kind: [{'op':'account-type','name':name,'type':kind}]
    delete = lambda name, yes=True: [{'op':'account-delete','name':name,'confirm':yes}]
    return [episode('account-type-delete','accounts',[
        step('term','Change Rainy Day Savings to a Term account. Display its account properties afterwards.',
             'Rainy Day Savings is shown as a Term account, with its original 8000 opening balance.',
             change('Rainy Day Savings','Term')+[{'op':'edit-account','account':'Rainy Day Savings','keep_open':True}],
             [row('account',{'name':'Rainy Day Savings'},type='Term',balance=8000,currency='USD'),
              row('trx',{'notes':'May savings'},to_account='Rainy Day Savings',amount=300),
              row('sched',{'notes':'Reserve future'},account='Rainy Day Savings',amount=5)],modal_end=True),
        step('cash','Change Pocket Cash to a Checking account. Display its saved properties.',
             'Pocket Cash is now a Checking account with opening balance 150.',
             [{'op':'close','window':'Edit Account','button':'Cancel'}]+change('Pocket Cash','Checking')+
             [{'op':'edit-account','account':'Pocket Cash','keep_open':True}],
             [row('account',{'name':'Pocket Cash'},type='Checking',balance=150),
              row('trx',{'notes':'Cash coffee'},account='Pocket Cash',amount=12.5)],modal_end=True),
        step('cancel','Start deleting Everyday Checking, but decline the final confirmation. Return to the dashboard.',
             'Everyday Checking remains present after cancellation.',
             [{'op':'close','window':'Edit Account','button':'Cancel'}]+delete('Everyday Checking',False),
             [row('account',{'name':'Everyday Checking'},balance=2500,type='Checking'),count('trx',{'account':'Everyday Checking'},12)]),
        step('empty','Delete the empty account Empty Reserve and confirm. Return to the dashboard.',
             'Empty Reserve is removed, while the other accounts that were present before remain.',
             delete('Empty Reserve'),[count('account',{'name':'Empty Reserve'},0),count('trx',{},18)]),
        step('referenced','Delete Rainy Day Savings and confirm removal of the account and its related activity. Return to the dashboard.',
             'Rainy Day Savings disappears and the remaining accounts remain available.',
             delete('Rainy Day Savings'),[count('account',{'name':'Rainy Day Savings'},0),
              count('trx',{'notes':'May savings'},0),count('trx',{'notes':'Reserve interest'},0),count('sched',{'notes':'Reserve future'},0),
              row('trx',{'notes':'April salary'},account='Everyday Checking',amount=3200),count('trx',{},16)],depends=['term']),
    ],ledger='account-actions',budget={'calls':240,'tokens':3000000,'seconds':2400})]


def reconciliation():
    def states(values):
        return [row('trx',{'notes':name},status=value) for name,value in values.items()]
    base={'Already reconciled':'R','Shop':'','Extra pay':'','Outgoing':'','Incoming':''}
    later=dict(base,Shop='F',**{'Extra pay':'F'})
    first=dict(base,Shop='R',**{'Extra pay':'R'})
    nav=[{'op':'nav','path':['Bank Accounts','Statement']}]
    return [episode('account-reconcile','reconciliation',[
        step('cancel','Open reconciliation for Statement. Enter ending balance 1230 and mark all four pending entries cleared, but cancel the dialog without saving.',
             'The account still has reconciled balance 1100; the four pending entries retain their original unreconciled statuses.',
             nav+[{'op':'reconcile','ending':'1230','all':True,'button':'Cancel'}],states(base)),
        step('later','Reconcile Statement to an ending balance of 1260, selecting only the 40 Shop withdrawal and 200 Extra pay deposit. Choose Finish later.',
             'Shop and Extra pay now show Follow Up, while the two transfers remain unreconciled.',
             [{'op':'reconcile','ending':'1260','rows':[['withdrawal',0],['deposit',0]],'button':'Finish later'}],states(later),depends=['cancel']),
        step('done','Resume Statement reconciliation with ending balance 1260. Keep the two previously cleared entries, confirm zero difference and finish with Done.',
             'The two selected entries are reconciled and the account reconciled balance is 1260.',
             [{'op':'reconcile','ending':'1260','button':'Done'}],states(first),depends=['later']),
        step('transfers','Reconcile the remaining outgoing transfer of 50 and incoming transfer of 20, with ending balance 1230. Finish with Done.',
             'Both transfers show reconciled status and Statement has balance 1230.',
             [{'op':'reconcile','ending':'1230','all':True,'button':'Done'}],states({k:'R' for k in base})+
             [row('trx',{'notes':'Outgoing'},account='Statement',to_account='Reserve',amount=50),
              row('trx',{'notes':'Incoming'},account='Reserve',to_account='Statement',amount=20)],depends=['done']),
    ],ledger='reconcile',navigator=['Bank Accounts'],children={'Bank Accounts':['Reserve','Statement'],'Favorites':['Statement']},
       budget={'calls':240,'tokens':3000000,'seconds':2400})]


def date_ranges():
    return [episode('date-range-manager','date-ranges',[
        step('create','Create a checking date range named Review month using range code -1 M (the previous calendar month). Save it and apply it to Everyday Checking.',
             'The account uses Review month, May 1–31, 2026, and shows its five May transactions.',
             [{'op':'date-range','action':'create','name':'Review month','code':'-1 M'},
              {'op':'nav','path':['Bank Accounts','Everyday Checking']},{'op':'account-range','name':'Review month'}]),
        step('edit','Change Review month to Review quarter with range code -1 Q (the previous calendar quarter). Save it and apply the renamed range to Everyday Checking.',
             'The account uses Review quarter, January 1–March 31, 2026, and its transaction list is empty.',
             [{'op':'date-range','action':'edit','old':'Review month','name':'Review quarter','code':'-1 Q'},
              {'op':'nav','path':['Dashboard']},{'op':'nav','path':['Bank Accounts','Everyday Checking']},
              {'op':'account-range','name':'Review quarter'}],depends=['create']),
        step('remove','Delete the custom Review quarter date range, save the manager, then show the manager again.',
             'The saved range list no longer contains Review quarter or Review month, while built-in ranges remain.',
             [{'op':'date-range','action':'delete','old':'Review quarter'},
              {'op':'open','path':['Tools','Date Range Manager…'],'window':'Manage checking date ranges'}],depends=['edit'],modal_end=True),
    ],budget={'calls':240,'seconds':2400,'tokens':3000000})]


def mapped_imports():
    from exchange_inputs import MAPPED_FIELDS
    result=[]
    for fmt in ('XML','CSV'):
        key='import-'+fmt.lower()+'-preset'
        steps=[]
        for batch in (1,2):
            name=f'mapped-{batch}.{fmt.lower()}'
            recipe={'op':'csv-import','format':fmt,'path':'inbox/'+name,'account':'Pocket Cash'}
            if batch==1:
                recipe.update(fields=MAPPED_FIELDS,skip_first=1,save_preset='Bank layout')
                goal=f'Import {inbox(key)}/{name} into Pocket Cash. Map columns in order to Notes, Date, Payee, Withdrawal, Deposit, Category, Number, Tags. Skip the header, use YYYY-MM-DD dates and period decimals. Save the mapping as Bank layout before importing.'
            else:
                recipe.update(preset='Bank layout')
                goal=f'Reopen the {fmt} importer and import {inbox(key)}/{name} into Pocket Cash using the saved Bank layout preset, without rebuilding the mapping.'
            goal+=' Confirm saving and close the importer.'
            checks=[row('trx',{'notes':f'Mapped café {batch}'},account='Pocket Cash',type='Withdrawal',amount=7.125,payee='Cafe Luna',category='Food:Dining out',date='2026-06-10',number=f'M{batch}-1',tags=['home','work']),
                    row('trx',{'notes':f'Mapped salary {batch}'},type='Deposit',amount=250.5,date='2026-06-11',category='Income:Salary',tags=['work']),
                    row('trx',{'notes':f'Mapped zero {batch}'},amount=0,date='2026-06-12',tags=[]),count('trx',{'account':'Pocket Cash'},1+batch*3)]
            steps.append(step('first' if batch==1 else 'reuse',goal,
                              f'Pocket Cash contains the three batch {batch} transactions with their notes, withdrawal/deposit directions, payees and amounts.',
                              [recipe],checks,depends=['first'] if batch==2 else []))
        result.append(episode(key,'import',steps,files_in=[f'exchange/mapped-{i}.{fmt.lower()}' for i in (1,2)],
                               budget={'calls':240,'tokens':3000000,'seconds':2400}))
    return result


def custom_fields():
    M='Custom Field Manager';F='New/Edit Custom Field';T='Edit Transaction'
    return [episode('custom-field-extended','custom-fields',[
        step('definition','Edit Code in the Custom Field Manager: use regular expression ^[A-Z]{2}[0-9]{3,4}$, default AB100 and panel column UDFC02. Save and reopen the field definition.',
             'The saved definition shows Code as String, the requested validation, default AB100 and UDFC02 mapping.',
             [{'op':'open','path':['Tools','Custom Field Manager…'],'window':M},{'op':'manager-menu','window':M,'name':'Edit'},
              {'op':'fill','window':F,'label':'RegEx','value':'^[A-Z]{2}[0-9]{3,4}$'},
              {'op':'choose','window':F,'label':"Panel's column",'value':'UDFC02'},{'op':'close','window':F},
              {'op':'manager-menu','window':M,'name':'Edit'}],
             [row('field',{'description':'Code'},regex='^[A-Z]{2}[0-9]{3,4}$',default='AB100',column='UDFC02')],modal_end=True),
        step('values','On April salary in Everyday Checking, enable custom fields Visit and Labels. Set Visit to 09:25:30 and select Red and Blue for Labels. Keep Code AB100, save and reopen the custom fields.',
             'The saved transaction shows Visit 09:25:30, Labels Red and Blue, and Code AB100.',
             [{'op':'close','window':F,'button':'Cancel'},{'op':'close','window':M,'button':'Close'},{'op':'nav','path':['Bank Accounts','Everyday Checking']},{'op':'row','index':0},{'op':'press','key':'Return'},
              {'op':'custom-fields','times':{'Visit':'09:25:30'},'multiple':{'Labels':['Red','Blue']}},{'op':'close','window':T,'button':'Save'},
              {'op':'row','index':0},{'op':'press','key':'Return'},{'op':'custom-fields'}],
             [row('trx',{'notes':'April salary'},fields={'Code':'AB100','Visit':'09:25:30','Labels':'Blue;Red'})],depends=['definition'],modal_end=True),
        step('reject','Try changing Code on this transaction to invalid value xx and saving. Leave the validation error visible.',
             'The application rejects xx with a custom-field validation message, leaving the transaction editor open.',
             [{'op':'fill','window':T,'label':'Code','value':'xx','commit':True},{'op':'button','window':T,'name':'Save'}],
             [row('trx',{'notes':'April salary'},fields={'Code':'AB100','Visit':'09:25:30','Labels':'Blue;Red'})],depends=['values'],modal_end=True),
        step('bulk','Dismiss the error and cancel the unsaved edit. In Custom Field Manager, bulk replace complete Code values AB100 with CD200.',
             'The bulk content update reports two replacements.',
             [{'op':'alert','button':'OK'},{'op':'close','window':T,'button':'Cancel'},
              {'op':'open','path':['Tools','Custom Field Manager…'],'window':M},{'op':'manager-menu','window':M,'name':'Bulk content update'},
              {'op':'alert','button':'Yes'},{'op':'text-prompt','window':'Update Custom Field Content','value':'AB100','same_title_next':True},
              {'op':'text-prompt','window':'Update Custom Field Content','value':'CD200','same_title_next':True}],
             [row('trx',{'notes':'April salary'},fields={'Code':'CD200','Visit':'09:25:30','Labels':'Blue;Red'}),
              row('trx',{'notes':'April rent'},fields={'Code':'CD200'}),row('trx',{'notes':'April groceries'},fields={'Code':'AB101'})],depends=['reject'],modal_end=True),
        step('delete','Dismiss the replacement result and remove the Code field, confirming removal of its saved values. Leave the manager visible.',
             'Code disappears from the manager; Labels and Visit remain.',
             [{'op':'alert','button':'OK'},{'op':'manager-menu','window':M,'name':'Remove'},{'op':'alert','button':'Yes'}],
             [count('field',{'description':'Code'},0),row('trx',{'notes':'April salary'},fields={'Visit':'09:25:30','Labels':'Blue;Red'}),
              row('trx',{'notes':'April rent'},fields={}),row('trx',{'notes':'April groceries'},fields={})],depends=['bulk']),
    ],ledger='extended-fields',budget={'calls':260,'tokens':3500000,'seconds':2800})]


def backups_retention():
    S='Settings'
    def backup(kind,checks):
        return [dict(kind='backup',pattern=r'ledger\.mmb_'+kind+r'_.*\.bak',check=c,slug=kind+'-'+c['slug'],description='Backup preserves '+c['description'],expect=c['expect']) for group in checks for c in group]
    configure=[{'op':'open','path':['Tools','Settings…'],'window':S},{'op':'settings-tab','name':'Other'},
               {'op':'check','window':S,'name':'Backup database on startup'}, {'op':'check','window':S,'name':'Backup database on exit'},
               {'op':'close','window':S}]
    openledger=[{'op':'press','key':'Control+o'},{'op':'file-dialog','path':'inbox/alternate.mmb'},{'op':'wait','seconds':1},
                {'op':'press','key':'Control+o'},{'op':'file-dialog','path':'inbox/ledger.mmb'},{'op':'wait','seconds':2}]
    return [episode('database-backups','database',[
        step('startup',f'Enable database backups on startup and on exit. Open {inbox("database-backups")}/alternate.mmb, then open {inbox("database-backups")}/ledger.mmb again to create its startup backup. Display the saved backup preferences.',
             'The saved preferences enable both startup and exit backups.',configure+openledger+
             [{'op':'open','path':['Tools','Settings…'],'window':S},{'op':'settings-tab','name':'Other'}],
             backup('start',[row('account',{'name':'Everyday Checking'},balance=2500),count('trx',{},17),
                             row('trx',{'notes':'June split shop'},amount=95.2,payee='Grocer')]),modal_end=True),
        step('exit',f'Change the Everyday Checking account notes to Backup milestone. Open {inbox("database-backups")}/alternate.mmb so the changed ledger closes and its backup is written, then open {inbox("database-backups")}/ledger.mmb again. Leave the account properties visible.',
             'Everyday Checking retains the saved Backup milestone notes after reopening.',
             [{'op':'close','window':S},{'op':'edit-account','account':'Everyday Checking','notes':'Backup milestone'}]+openledger+
             [{'op':'edit-account','account':'Everyday Checking','keep_open':True}],
             backup('update',[row('account',{'name':'Everyday Checking'},notes='Backup milestone',balance=2500),
                              count('trx',{},17),row('trx',{'notes':'June split shop'},amount=95.2)])+
             [row('account',{'name':'Everyday Checking'},notes='Backup milestone')],depends=['startup'],modal_end=True),
    ],files_in=['std/alternate.mmb'],budget={'calls':240,'seconds':2400,'tokens':3000000}),episode('deleted-retention','database',[
        step('configure','Set the retention period for deleted transactions to 10 days in Settings, then save.',
             'The saved database preferences show a retention period of 10 days.',
             [{'op':'open','path':['Tools','Settings…'],'window':S},{'op':'settings-tab','name':'Other'},
              {'op':'fill','window':S,'label':'Days to retain deleted transactions','role':'spin button','value':'10','commit':True},
              {'op':'close','window':S},{'op':'open','path':['Tools','Settings…'],'window':S},{'op':'settings-tab','name':'Other'}],modal_end=True),
        step('clean','After restarting, display Deleted Transactions. Entries were deleted 11, 10 and 9 days before the current fixed date; the 10-day retention rule should now apply.',
             'Only one transaction remains in Deleted Transactions, with selected notes Recent.',
             [{'op':'nav-deleted'},{'op':'row','index':0}],
             [count('trx',{'notes':'Expired'},0),count('trx',{'notes':'Boundary'},0),row('trx',{'notes':'Recent'},deleted=True,amount=9),
              count('trx',{'deleted':False},17),row('trx',{'notes':'April salary'},amount=3200)],
             depends=['configure'],lifecycle='restart'),
    ],ledger='retention')]


def report_parameters():
    from spec_finance import REPORT_NAV,REPORT_CHILDREN
    def values(file,expected):
        return [document('outbox',file,'html-cells',name.lower().replace(' ','-').replace(':',''),
                         'Computed filtered report total for '+name+'.',expect=[value],label=name) for name,value in expected.items()]
    result=[]
    key='report-date-accounts'
    result.append(episode(key,'reports',[
        step('month',f'Open Categories / Summary for the current month (June 2026), limited to Main Checking. Export HTML to {outbox(key)}/month.html.',
             'Categories Summary shows the June 2026 dates and Main Checking, with a total of 1695.00.',
             [{'op':'report','path':['Categories','Summary']},{'op':'report-parameters','period':'Current month','accounts':['Main Checking']},
              {'op':'export-html','path':'outbox/month.html'}],
             values('month.html',{'Electricity':-77,'Rent':-1100,'Groceries':-228,'Salary':3100,'Grand Total:':1695})),
        step('cards',f'Change the report account selection to Credit Card Accounts, keeping the current month. Export to {outbox(key)}/cards.html.',
             'The report now covers credit cards and shows the June dining expense 38.00.',
             [{'op':'report-parameters','group':'Credit Card Accounts'},{'op':'export-html','path':'outbox/cards.html'}],
             values('cards.html',{'Dining out':-38,'Grand Total:':-38}),depends=['month']),
    ],ledger='reports',navigator=REPORT_NAV,children=REPORT_CHILDREN))
    key='report-future-policy'
    result.append(episode(key,'reports',[
        step('include',f'Open Categories / Summary for the current year (2026), limited to Main Checking, with future transactions included. Export to {outbox(key)}/included.html.',
             'The report covers 2026 and includes the future maintenance expense of 500.',
             [{'op':'report','path':['Categories','Summary']},{'op':'report-parameters','period':'Current year','accounts':['Main Checking']},
              {'op':'export-html','path':'outbox/included.html'}],
             values('included.html',{'Maintenance':-500,'Salary':18300,'Rent':-6600})),
        step('preference','From the dashboard, enable Ignore Future Transactions in transaction preferences. Save, then reopen those preferences to show the saved option.',
             'Ignore Future Transactions is enabled in the saved transaction preferences.',
             [{'op':'nav','path':['Dashboard']},{'op':'open','path':['Tools','Settings…'],'window':'Settings'},
              {'op':'settings-tab','name':'Transactions'},{'op':'check','window':'Settings','name':'Ignore Future Transactions'},
              {'op':'close','window':'Settings'}, {'op':'open','path':['Tools','Settings…'],'window':'Settings'},
              {'op':'settings-tab','name':'Transactions'}],modal_end=True),
        step('exclude',f'After this restart, open Categories / Summary for Main Checking and select the date range From current year to week. Export it to {outbox(key)}/excluded.html.',
             'The report uses the requested range through the current week, totals 9950.00 and excludes the July repair expense.',
             [{'op':'report','path':['Categories','Summary']},
              {'op':'report-parameters','period':'From current year to week','more_periods':True,'accounts':['Main Checking']},
              {'op':'export-html','path':'outbox/excluded.html'}],
             [document('outbox','excluded.html','html-cells','total','The filtered category total.',label='Grand Total:',expect=[9950]),
              document('outbox','excluded.html','html-has','no-future-repair','No future repair category is reported.',texts=['Maintenance'],expect=[],nonempty=False)],
              depends=['preference'],lifecycle='restart'),
    ],ledger='reports',navigator=REPORT_NAV,children=REPORT_CHILDREN,budget={'calls':240,'seconds':2400,'tokens':3000000}))
    return result


def budget_options():
    from spec_finance import REPORT_NAV,REPORT_CHILDREN
    result=[]
    for name,options,period in [
        ('override',{'Override yearly budget with monthly budget':True},'2026'),
        ('deduct',{'Subtract monthly budgets from yearly budget in reporting':True},'2026'),
        ('monthly',{},'2026-06'),
        ('financial',{'View Budgets as Financial Years':True,"View Budgets with 'transfer' transactions":True},'2026')]:
        key='report-budget-'+name
        recipe=[{'op':'open','path':['Tools','Settings…'],'window':'Settings'},{'op':'settings-tab','name':'Transactions'}]
        recipe += [{'op':'check','window':'Settings','name':label,'value':value} for label,value in options.items()]
        recipe += [{'op':'close','window':'Settings'}, {'op':'report','path':['Budgets','Budget Performance' if name in ('override','deduct') else 'Budget Category Summary']},
                   {'op':'choose','window':'Money Manager Ex','label':'Budget','value':period}, {'op':'wait','seconds':1},
                   {'op':'export-html'}]
        checks=[document('outbox','report.html','html-number-cells','category-'+label.lower().replace(' ','-'),
                         'Budget estimate, actual and difference for '+label+'.',label=label) for label in (('Groceries','Rent','Salary','Transfer') if name=='financial' else ('Groceries','Rent','Salary'))]
        goal=f'Use the {period} budget. '
        if options:goal+='Enable '+', '.join(options)+'. '
        goal+=f'Open Budgets / {"Budget Performance" if name in ("override","deduct") else "Budget Category Summary"}, select {period}, export HTML to {outbox(key)}/report.html and leave the report visible.'
        result.append(episode(key,'budgets',[step('view',goal,
                          'The requested budget report shows the selected period and recalculated estimates and actuals for the chosen budget settings.',recipe,checks)],
                          ledger='budget-policy' if name=='financial' else 'reports',navigator=REPORT_NAV,children=REPORT_CHILDREN,
                          budget={'calls':300,'tokens':4500000,'seconds':3000} if name=='override' else {'calls':150,'tokens':1800000,'seconds':1600}))
    return result


def budget_frequencies():
    result=[]
    for period in ('2026','2026-06'):
        key='budget-frequencies-'+('annual' if period=='2026' else 'monthly')
        checks=[document('outbox','report.html','html-cells',f'frequency-{i}',
                          'Estimate and actual for '+frequency+'.',label=f'Plan {i}',
                          expect=[-(13 if period=='2026' else 2)*[0,52,26,12,6,4,2,1,365][i],-(i+1)])
                for i,frequency in enumerate(('None','Weekly','Fortnightly','Monthly','Every 2 Months','Quarterly','Half-Yearly','Yearly','Daily'))]
        result.append(episode(key,'budgets',[
            step('report',f'Open Budgets / Budget Category Summary, select budget {period}, export it to {outbox(key)}/report.html and leave it visible.',
                 'The budget summary shows all nine Plan categories, with estimates appropriate to their frequencies and the saved actual expenses.',
                 [{'op':'report','path':['Budgets','Budget Category Summary']},{'op':'choose','window':'Money Manager Ex','label':'Budget','value':period},
                  {'op':'wait','seconds':1},{'op':'export-html'}],checks)
        ],ledger='budget-frequency',navigator=['Bank Accounts'],children={'Bank Accounts':['Budget Cash','Budget Reserve'],'Favorites':['Budget Cash'],'Budget Planner':['2026']}))
    return result


def interchange_roundtrip():
    key='qif-roundtrip'
    return [episode(key,'interchange',[
        step('export',f'Export all accounts to QIF at {outbox(key)}/roundtrip.qif.',
             'The export completes with three transactions from Source.',
             [{'op':'exchange-export','format':'QIF','path':'outbox/roundtrip.qif'}],
             [document('outbox','roundtrip.qif','semantic-qif','complete-export','All source transactions, including tags and splits.'),
              document('outbox','roundtrip.qif','semantic-qif-count','count','The export has three transactions.',expect=3)],modal_end=True),
        step('import',f'Import {outbox(key)}/roundtrip.qif into the empty Target account, using YYYY-MM-DD dates. Confirm and close the importer.',
             'Target contains the bonus, quoted shopping note and split withdrawal with the original amounts.',
             [{'op':'alert','button':'OK'},{'op':'close','window':'Export as QIF file','button':'Cancel'},
              {'op':'qif-import','path':'outbox/roundtrip.qif','account':'Target'}],
             [row('trx',{'account':'Target','number':'RT1'},type='Deposit',amount=123.45,date='2026-06-01',payee='Employer',category='Income:Salary',notes='Café bonus',status='R'),
              row('trx',{'account':'Target','number':'RT2'},type='Withdrawal',amount=20,date='2026-06-02',notes='Shopping, "quoted"',tags=['home','work']),
              row('trx',{'account':'Target','number':'RT3'},type='Withdrawal',amount=30,splits=[{'category':'Food:Groceries','amount':12,'notes':'fruit','tags':[]},
                  {'category':'Homeneeds:Furnishing','amount':18,'notes':'vase','tags':[]}]),count('trx',{'account':'Target'},3)],depends=['export']),
    ],ledger='roundtrip',navigator=['Bank Accounts'],children={'Bank Accounts':['Source','Target']},budget={'calls':320,'tokens':5000000,'seconds':3200})]


def stock_lots():
    import copy
    from spec_finance import REPORT_NAV,REPORT_CHILDREN,stocks
    seed=stocks()[0]['checkpoints'][0]['recipe']
    first=copy.deepcopy(seed)
    second=copy.deepcopy(seed[1:])
    for action in second:
        if action.get('label')=='*Date':action['value']='06/05/2026'
        if action.get('label')=='*Share Number':action['value']='4'
        if action.get('label') in ('*Share Price','Curr. Share Price'):action['value']='30'
        if action.get('label')=='Deductible Comm.':action['value']='1'
        if action['op']=='share-form':action.update(number='CDR-BUY-2',notes='Cedar second lot')
    children=dict(REPORT_CHILDREN,**{'Stock Portfolios':['Broker','Second Broker']})
    return [episode('stock-multiple-lots','stocks',[
        step('first','In Broker create Cedar Works, symbol CDR, purchasing 12.5 shares on 06/01/2026 for 20 per share and commission 2.5, current price 20. Use Employer, Investment:Purchase, number CDR-BUY-1 and notes Cedar initial lot in the linked transaction. Close the editor.',
             'Broker shows the initial Cedar Works lot with 12.5 shares.',first,
             [row('stock',{'symbol':'CDR','date':'2026-06-01'},shares=12.5,commission=2.5),row('trx',{'notes':'Cedar initial lot'},amount=252.5,link='Stock')]),
        step('second','Create a second Cedar Works investment lot with symbol CDR in Broker: 4 shares on 06/05/2026 at 30 per share, commission 1 and current price 30. Use Employer, Investment:Purchase, number CDR-BUY-2 and notes Cedar second lot in its linked transaction. Close the editor.',
             'Broker lists separate Cedar Works lots of 12.5 and 4 shares.',second,
             [count('stock',{'symbol':'CDR'},2),row('stock',{'symbol':'CDR','date':'2026-06-05'},shares=4,commission=1),
              row('trx',{'notes':'Cedar second lot'},amount=121,link='Stock',shares={'number':4,'price':30,'commission':1})],depends=['first']),
        step('move','Move the June 5 Cedar Works lot from Broker to Second Broker. Leave Second Broker visible.',
             'Second Broker contains the four-share Cedar Works lot after the move.',
             [{'op':'button','window':'Money Manager Ex','name':'Move'},{'op':'cell','window':'Moving Transaction from Broker to','name':'Second Broker'},
              {'op':'close','window':'Moving Transaction from Broker to'}, {'op':'nav','path':['Stock Portfolios','Second Broker']}],
             [row('stock',{'symbol':'CDR','date':'2026-06-05'},account='Second Broker',shares=4),
              row('stock',{'symbol':'CDR','date':'2026-06-01'},account='Broker',shares=12.5),
              row('trx',{'notes':'Cedar second lot'},amount=121,shares={'number':4,'price':30,'commission':1})],depends=['second']),
    ],ledger='stock-lots',navigator=REPORT_NAV,children=children,budget={'calls':300,'tokens':4000000,'seconds':3000})]


def investment_cash():
    from spec_finance import REPORT_NAV,REPORT_CHILDREN
    return [episode('investment-cash-ledger','stocks',[
        step('dividend','Record a dividend deposit of 12.75 in Broker on 06/14/2026 from Employer, category Income:Investment Income, notes Investment dividend. Leave Broker’s cash ledger visible.',
             'Broker’s cash balance is 12.75 after the dividend; its stock market value remains 875.',
             [{'op':'nav','path':['Stock Portfolios','Broker']},{'op':'new-transaction','type':'Deposit','account':'Broker','amount':'12.75','date':'06/14/2026',
               'payee':'Employer','category':'Income:Investment Income','notes':'Investment dividend'}],
             [row('trx',{'notes':'Investment dividend'},account='Broker',type='Deposit',amount=12.75,category='Income:Investment Income',date='2026-06-14'),
              row('stock',{'symbol':'ACME'},shares=10),row('stock',{'symbol':'BETA'},shares=25)]),
        step('fee','Record a separate 1.25 withdrawal in Broker on 06/15/2026 to Employer, category Investment:Brokerage Fees, notes Broker service fee. Leave Broker’s cash ledger visible.',
             'Broker’s cash balance is 11.50 after the fee.',
             [{'op':'new-transaction','type':'Withdrawal','account':'Broker','amount':'1.25','date':'06/15/2026','payee':'Employer',
               'category':'Investment:Brokerage Fees','notes':'Broker service fee'}],
             [row('trx',{'notes':'Broker service fee'},account='Broker',type='Withdrawal',amount=1.25,category='Investment:Brokerage Fees')],depends=['dividend']),
    ],ledger='reports',navigator=REPORT_NAV,children=REPORT_CHILDREN)]


def build():
    return accounts()+reconciliation()+date_ranges()+mapped_imports()+custom_fields()+backups_retention()+report_parameters()+budget_options()+budget_frequencies()+interchange_roundtrip()+stock_lots()+investment_cash()
