"""Financial interchange through the product's import/export dialogs."""
from spec_common import episode,step,row,count,document,inbox,outbox
from exchange_inputs import BASIC_FIELDS


def exports():
    result=[]
    for fmt,extension in [('CSV','csv'),('JSON','json'),('QIF','qif')]:
        key='export-'+extension
        points=[]
        for label in ['April salary','April groceries','May savings','May dinner','June split shop','Visa books','Euro lunch']:
            if fmt=='JSON':
                form='semantic-json'; options={'match':{'notes':label}}
            elif fmt=='QIF':
                form='semantic-qif'; options={'match':{'notes':label}}
            else:
                form='semantic-csv'; options={'match':{'Notes':label}}
            points+=document('outbox','ledger.'+extension,form,label.lower().replace(' ','-'),
                             'Complete exported transaction semantics for '+label+'.',**options)
        amount=18 if fmt=='JSON' else 17
        if fmt=='JSON':
            points+=document('outbox','ledger.json','semantic-json-accounts','all-accounts','All exported account names, currencies, types and opening balances.')
        points+=document('outbox','ledger.'+extension,'semantic-'+extension+'-count','transaction-count','The complete exported transaction row count.',
                         expect=18 if fmt=='JSON' else 17 if fmt=='QIF' else 19)
        points+=document('outbox','ledger.'+extension,'semantic-'+extension,'all-transactions','All exported transactions, including their relationships, tags and split parts.')
        result.append(episode(key,'export',[
            step('save',f'Export all accounts with the default date format to {outbox(key)}/ledger.{extension} using {"MMEX CSV" if fmt=="CSV" else fmt} export. Leave the completion message visible.',
                 f'The export completion reports {amount} transactions and the exported accounts.',
                 [{'op':'exchange-export','format':fmt,'path':'outbox/ledger.'+extension}],points,modal_end=True)
        ],ledger='json-export' if fmt=='JSON' else 'std'))
    return result


def csv_imports():
    result=[]
    common=[row('trx',{'notes':'Imported coffee'},account='Pocket Cash',amount=7.25,type='Withdrawal',date='2026-06-10',payee='Cafe Luna',category='Food:Dining out',number='C-1'),
            row('trx',{'notes':'Imported income'},account='Pocket Cash',amount=125.5,type='Deposit',date='2026-06-11',category='Income:Salary'),
            row('trx',{'notes':'Apples, pears and café'},amount=19.95,payee='Marché Nord',category='Food:Groceries',number='C-3'),
            row('payee',{'name':'Marché Nord'},active=1)]
    result.append(episode('import-csv-basic','import',[
        step('import',f'Import {inbox("import-csv-basic")}/bank.csv into Pocket Cash. The columns are Date, Payee, Amount, Category, Number, Notes; skip the header row, use YYYY-MM-DD dates and positive amounts as deposits. Confirm saving and close the importer.',
             'Pocket Cash shows the three imported transactions: a 7.25 withdrawal to Cafe Luna, a 125.50 deposit from Employer and a 19.95 withdrawal to Marché Nord.',
             [{'op':'csv-import','path':'inbox/bank.csv','fields':BASIC_FIELDS,'skip_first':1}],common),
    ],files_in=['exchange/bank.csv'],budget={'calls':150,'seconds':1600,'tokens':1800000}))
    result.append(episode('import-csv-european','import',[
        step('import',f'Import {inbox("import-csv-european")}/euro.csv into Euro Current. Use the semicolon delimiter, DD.MM.YYYY dates, comma decimals, and positive values as withdrawals. Columns are Date, Payee, Amount, Category, Number, Notes. Ignore one row at the start and one at the end; confirm saving and close the importer.',
             'Euro Current lists a withdrawal of 12.34 to Cafe Luna and a deposit of 250.50 from Employer with the imported notes.',
             [{'op':'csv-import','path':'inbox/euro.csv','account':'Euro Current','fields':BASIC_FIELDS,'skip_first':1,'skip_last':1,
               'delimiter':';','decimal':',','date_format':'DD.MM.YYYY','direction':'Positive values are withdrawals'}],
             [row('trx',{'notes':'European purchase'},account='Euro Current',type='Withdrawal',amount=12.34,date='2026-06-17',number='E-1'),
              row('trx',{'notes':'European refund'},type='Deposit',amount=250.5,date='2026-06-18',category='Income:Salary')]),
    ],files_in=['exchange/euro.csv'],budget={'calls':150,'seconds':1600,'tokens':1800000}))
    result.append(episode('import-csv-partial','import',[
        step('import',f'Import {inbox("import-csv-partial")}/partial.csv into Pocket Cash, with columns Date, Payee, Amount, Category, Number, Notes, a header row and YYYY-MM-DD dates. Confirm saving the rows the application accepts, then close the importer.',
             'Pocket Cash lists the imported 8.50 withdrawal to Cafe Luna and the zero-amount Grocer entry; the invalid-date row is absent.',
             [{'op':'csv-import','path':'inbox/partial.csv','fields':BASIC_FIELDS,'skip_first':1}],
             [row('trx',{'notes':'Valid partial import'},amount=8.5,type='Withdrawal',date='2026-06-10'),
              count('trx',{'notes':'Invalid date import'},0),row('trx',{'notes':'Invalid amount import'},amount=0,type='Withdrawal')]),
    ],files_in=['exchange/partial.csv'],budget={'calls':150,'seconds':1600,'tokens':1800000}))
    return result




def other_formats():
    result=[]
    key='export-xml'
    points=[]
    for note in ('April salary','April rent','April power','May savings','June split shop'):
        points+=document('outbox','ledger.xml','semantic-xml',note.lower().replace(' ','-'),
                         'Exported XML business values for '+note+'.',match={'Notes':note})
    points+=document('outbox','ledger.xml','semantic-xml-count','transaction-rows','All XML transaction/split rows are present.',expect=13)
    points+=document('outbox','ledger.xml','semantic-xml','complete-transactions','Complete XML transaction values, ignoring row and split order.')
    result.append(episode(key,'export',[
        step('save',f'Export Everyday Checking as XML to {outbox(key)}/ledger.xml, using MMEX fields and including column titles. Leave the completion message visible.',
             'The XML export reports 13 exported transaction rows.',
             [{'op':'xml-export','path':'outbox/ledger.xml','account':'Everyday Checking'}],points,modal_end=True)
    ]))
    key='import-qif'
    result.append(episode(key,'import',[
        step('import',f'Import {inbox(key)}/bank.qif into Pocket Cash using YYYY-MM-DD dates. Confirm the import and close the importer.',
             'Pocket Cash contains QIF dinner, QIF bonus and QIF split shop, with their amounts and payees.',
             [{'op':'qif-import','path':'inbox/bank.qif'}],
             [row('trx',{'notes':'QIF dinner'},account='Pocket Cash',amount=32.75,type='Withdrawal',payee='Cafe Luna',category='Food:Dining out',number='Q-1'),
              row('trx',{'notes':'QIF bonus'},amount=450.25,type='Deposit',date='2026-06-11',status='R'),
              row('trx',{'notes':'QIF split shop'},amount=60.5,splits=[{'category':'Food:Groceries','amount':40.25,'notes':'fruit','tags':[]},
                  {'category':'Homeneeds:Furnishing','amount':20.25,'notes':'vase','tags':[]}])]),
        step('duplicates',f'Import {inbox(key)}/bank.qif into Pocket Cash again, enabling duplicate detection by transaction number and leaving its action as Skip. Confirm and close the importer.',
             'Pocket Cash still shows one copy of each of the three imported QIF transactions.',
             [{'op':'qif-import','path':'inbox/bank.qif','duplicates':True}],
             [count('trx',{'notes':'QIF dinner'},1),count('trx',{'notes':'QIF bonus'},1),count('trx',{'notes':'QIF split shop'},1)],depends=['import']),
    ],files_in=['exchange/bank.qif']))
    return result



def ofx():
    key='import-ofx'
    return [episode(key,'import',[
        step('import',f'Import {inbox(key)}/bank.ofx into Everyday Checking. For the coffee transaction choose the existing payee Cafe Luna and its dining category; for the bonus choose Employer and its salary category. Complete the import and leave its summary visible.',
             'The OFX import summary shows two successfully imported transactions, assigned to Cafe Luna and Employer.',
             [{'op':'ofx-import','path':'inbox/bank.ofx'}],
             [row('trx',{'notes':'OFX coffee'},amount=28.75,type='Withdrawal',account='Everyday Checking',payee='Cafe Luna',category='Food:Dining out'),
              row('trx',{'notes':'OFX bonus'},amount=250.5,type='Deposit',payee='Employer',category='Income:Salary')],modal_end=True),
    ],files_in=['exchange/bank.ofx'],budget={'calls':150,'seconds':1600,'tokens':1800000})]


def build():
    return exports()+csv_imports()+other_formats()+ofx()
