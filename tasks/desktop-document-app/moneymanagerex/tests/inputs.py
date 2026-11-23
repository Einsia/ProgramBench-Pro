"""The documents episodes upload: ledgers and import files, addressed as '<key>/<file name>'."""
import fixtures


def standard(extra=None, **options):
    """The everyday ledger most episodes start from: five accounts, six payees and a dozen transactions per month group."""
    L = fixtures.Ledger(rates={'EUR': 1.10, 'GBP': 1.25, 'JPY': 0.007}, **options)
    L.account('Everyday Checking', 'Checking', 2500.0, favorite=True, number='CHK-001', held='First Bank')
    L.account('Rainy Day Savings', 'Checking', 8000.0)
    L.account('Travel Visa', 'Credit Card', 0.0, limit=5000.0, favorite=True)
    L.account('Pocket Cash', 'Cash', 150.0)
    L.account('Euro Current', 'Checking', 1200.0, currency='EUR')
    L.payee('Landlord', 'Bills:Rent')
    L.payee('Grocer', 'Food:Groceries')
    L.payee('Employer', 'Income:Salary')
    L.payee('City Power', 'Bills:Electricity')
    L.payee('Cafe Luna', 'Food:Dining out')
    L.payee('Book Nook')
    L.tag('work')
    L.tag('home')
    L.tag('trip')
    a = 'Everyday Checking'
    L.trx(a, 'Deposit', 3200.0, '2026-04-01', 'Employer', 'Income:Salary', status='R', notes='April salary')
    L.trx(a, 'Withdrawal', 1150.0, '2026-04-02', 'Landlord', 'Bills:Rent', status='R', number='1001', notes='April rent')
    L.trx(a, 'Withdrawal', 212.4, '2026-04-11', 'Grocer', 'Food:Groceries', status='R', notes='April groceries', tags=('home',))
    L.trx(a, 'Withdrawal', 64.1, '2026-04-20', 'City Power', 'Bills:Electricity', status='R', notes='April power')
    L.trx(a, 'Deposit', 3200.0, '2026-05-01', 'Employer', 'Income:Salary', status='R', notes='May salary')
    L.trx(a, 'Withdrawal', 1150.0, '2026-05-02', 'Landlord', 'Bills:Rent', status='R', number='1002', notes='May rent')
    L.trx(a, 'Withdrawal', 187.75, '2026-05-12', 'Grocer', 'Food:Groceries', status='F', notes='May groceries', tags=('home',))
    L.trx(a, 'Transfer', 300.0, '2026-05-15', to='Rainy Day Savings', category='Transfer', notes='May savings')
    L.trx(a, 'Withdrawal', 41.5, '2026-05-22', 'Cafe Luna', 'Food:Dining out', notes='May dinner', tags=('work', 'trip'))
    L.trx(a, 'Deposit', 3200.0, '2026-06-01', 'Employer', 'Income:Salary', status='R', notes='June salary')
    L.trx(a, 'Withdrawal', 1150.0, '2026-06-02', 'Landlord', 'Bills:Rent', number='1003', notes='June rent')
    L.trx(a, 'Withdrawal', 95.2, '2026-06-08', 'Grocer', splits=(('Food:Groceries', 70.2, 'food'), ('Homeneeds:Furnishing', 25.0, 'lamp')), notes='June split shop')
    v = 'Travel Visa'
    L.trx(v, 'Withdrawal', 320.0, '2026-04-18', 'Book Nook', 'Education:Books', notes='Visa books')
    L.trx(v, 'Withdrawal', 58.0, '2026-05-30', 'Cafe Luna', 'Food:Dining out', notes='Visa lunch', tags=('trip',))
    L.trx(v, 'Deposit', 100.0, '2026-06-03', None, 'Income:Reimbursement/Refunds', notes='Visa refund', status='R')
    L.trx('Euro Current', 'Withdrawal', 80.0, '2026-05-05', 'Cafe Luna', 'Food:Dining out', notes='Euro lunch')
    L.trx('Pocket Cash', 'Withdrawal', 12.5, '2026-06-05', 'Cafe Luna', 'Food:Dining out', notes='Cash coffee')
    if extra:
        extra(L)
    return L.bytes()


def reports(extra=None):
    """Two years of activity across several accounts, currencies and categories, a budget, stocks, assets and schedules."""
    L = fixtures.Ledger(rates={'EUR': 1.10, 'GBP': 1.25}, info={'FINANCIAL_YEAR_START_MONTH': '7', 'FINANCIAL_YEAR_START_DAY': '1'})
    L.currency_rate('EUR', '2025-01-01', 1.05)
    L.currency_rate('EUR', '2026-01-01', 1.08)
    L.currency_rate('EUR', '2026-06-01', 1.12)
    L.account('Main Checking', 'Checking', 1500.0, favorite=True, opened='2024-01-01')
    L.account('Savings Pot', 'Checking', 4000.0, opened='2024-01-01')
    L.account('Blue Card', 'Credit Card', 0.0, opened='2024-01-01', limit=3000.0)
    L.account('Wallet', 'Cash', 100.0, opened='2024-01-01')
    L.account('Euro Bank', 'Checking', 600.0, currency='EUR', opened='2024-01-01')
    L.account('Home Loan', 'Loan', -20000.0, opened='2024-01-01')
    L.account('Fixed Term', 'Term', 2500.0, opened='2024-01-01')
    L.account('Broker', 'Investment', 0.0, opened='2024-01-01')
    L.account('Property', 'Asset', 0.0, opened='2024-01-01')
    L.account('Closed Old', 'Checking', 50.0, opened='2024-01-01', status='Closed')
    L.payee('Employer', 'Income:Salary')
    L.payee('Landlord', 'Bills:Rent')
    L.payee('Grocer', 'Food:Groceries')
    L.payee('Cafe', 'Food:Dining out')
    L.payee('Power Co', 'Bills:Electricity')
    L.payee('Garage', 'Automobile:Maintenance')
    L.payee('Pharmacy', 'Healthcare:Prescriptions')
    L.tag('holiday')
    L.tag('family')
    L.tag('work')
    months = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 7)]
    for index, (year, month) in enumerate(months):
        stamp = f'{year}-{month:02d}'
        L.trx('Main Checking', 'Deposit', 3000.0 + 50 * (index % 3), f'{stamp}-01', 'Employer', 'Income:Salary', status='R', notes=f'Salary {stamp}')
        L.trx('Main Checking', 'Withdrawal', 1100.0, f'{stamp}-02', 'Landlord', 'Bills:Rent', status='R', number=str(2000 + index), notes=f'Rent {stamp}')
        L.trx('Main Checking', 'Withdrawal', 200.0 + 7.5 * (index % 5), f'{stamp}-06', 'Grocer', 'Food:Groceries', notes=f'Groceries {stamp}', status='R' if index % 2 else '')
        L.trx('Blue Card', 'Withdrawal', 35.0 + 3 * (index % 4), f'{stamp}-12', 'Cafe', 'Food:Dining out', notes=f'Dinner {stamp}', tags=('family',) if index % 3 == 0 else ())
        L.trx('Main Checking', 'Withdrawal', 60.0 + index, f'{stamp}-15', 'Power Co', 'Bills:Electricity', notes=f'Power {stamp}')
        if index % 4 == 1:
            L.trx('Main Checking', 'Transfer', 250.0, f'{stamp}-20', to='Savings Pot', category='Transfer', notes=f'Saving {stamp}')
        if index % 6 == 2:
            L.trx('Blue Card', 'Withdrawal', 320.0, f'{stamp}-22', 'Garage', 'Automobile:Maintenance', notes=f'Service {stamp}', status='F', tags=('holiday', 'work'))
        if index % 5 == 3:
            L.trx('Euro Bank', 'Withdrawal', 90.0, f'{stamp}-08', 'Pharmacy', 'Healthcare:Prescriptions', notes=f'Pharmacy {stamp}')
        if index % 6 == 5:
            L.trx('Euro Bank', 'Deposit', 400.0, f'{stamp}-25', None, 'Other Income', notes=f'Rent income {stamp}')
        if index % 7 == 0:
            L.trx('Wallet', 'Withdrawal', 25.0, f'{stamp}-10', 'Cafe', splits=(('Food:Dining out', 15.0, 'coffee'), ('Leisure:Magazines', 10.0, 'paper')), notes=f'Cash split {stamp}')
    L.trx('Main Checking', 'Withdrawal', 500.0, '2026-07-05', 'Garage', 'Automobile:Maintenance', notes='Future repair')
    L.trx('Main Checking', 'Withdrawal', 77.0, '2026-06-10', 'Grocer', 'Food:Groceries', status='V', notes='Voided shop')
    L.trx('Main Checking', 'Withdrawal', 13.0, '2026-06-11', 'Grocer', 'Food:Groceries', status='D', notes='Duplicate shop')
    L.trx('Main Checking', 'Withdrawal', 41.0, '2026-06-12', 'Grocer', 'Food:Groceries', notes='Deleted shop', deleted='2026-06-13T10:00:00.000')
    L.budget_year('2026')
    L.budget_year('2026-06')
    L.budget('2026', 'Food:Groceries', 'Monthly', -250.0, 'Weekly shops')
    L.budget('2026', 'Food:Dining out', 'Weekly', -10.0)
    L.budget('2026', 'Bills:Rent', 'Monthly', -1100.0)
    L.budget('2026', 'Bills:Electricity', 'Quarterly', -240.0)
    L.budget('2026', 'Income:Salary', 'Monthly', 3050.0)
    L.budget('2026', 'Automobile:Maintenance', 'Yearly', -700.0)
    L.budget('2026-06', 'Food:Groceries', 'Monthly', -300.0)
    L.budget('2026-06', 'Bills:Rent', 'Monthly', -1100.0)
    L.stock('Broker', 'Acme Corp', 'ACME', 10, 50.0, '2025-03-01', current=62.5, commission=5.0, notes='First lot')
    L.stock('Broker', 'Beta Ltd', 'BETA', 25, 12.0, '2025-09-15', current=10.0, commission=2.5)
    L.stock_price('ACME', '2026-06-01', 60.0)
    L.stock_price('ACME', '2026-06-14', 62.5)
    L.stock_price('BETA', '2026-06-14', 10.0)
    L.asset('Family Car', 'Automobile', 20000.0, '2024-01-01', change='Depreciates', rate=10.0, notes='Hatchback')
    L.asset('Flat', 'Property', 150000.0, '2023-06-01', change='Appreciates', rate=3.0)
    L.asset('Ring', 'Jewellery', 1200.0, '2025-02-14')
    L.sched('Main Checking', 'Withdrawal', 45.0, '2026-06-20', freq=3, payee='Power Co', category='Bills:Electricity', notes='Gas bill')
    L.sched('Main Checking', 'Deposit', 120.0, '2026-07-01', freq=5, payee='Employer', category='Other Income', notes='Quarterly bonus')
    L.sched('Main Checking', 'Transfer', 100.0, '2026-06-25', freq=3, to='Savings Pot', category='Transfer', notes='Monthly saving plan')
    L.sched('Blue Card', 'Withdrawal', 9.99, '2026-06-18', freq=3, payee='Cafe', category='Leisure:Magazines', notes='Subscription', num=3)
    if extra:
        extra(L)
    return L.bytes()


def merges():
    def extra(ledger):
        ledger.sched('Everyday Checking', 'Withdrawal', 40, '2026-07-01', freq=3,
                     payee='Book Nook', category='Food:Groceries', notes='Planned purchase', tags=('trip', 'work'))
        ledger.sched('Everyday Checking', 'Withdrawal', 20, '2026-07-02', freq=3,
                     payee='Grocer', notes='Planned split',
                     splits=(('Food:Groceries', 12, 'planned food', ('trip', 'work')),
                             ('Bills:Water', 8, 'planned water')))
        ledger.trx('Everyday Checking', 'Withdrawal', 25, '2026-06-09', 'Grocer', notes='Tagged split',
                   splits=(('Food:Groceries', 20, 'food', ('trip', 'work')), ('Bills:Water', 5, 'water')))
        ledger.budget_year('2026')
        ledger.budget('2026', 'Food:Groceries', 'Monthly', -300)
    return standard(extra)


def legacy():
    ledger = fixtures.Ledger(version=20, info={'STOCKURL': 'http://finance.yahoo.com/echarts?s=%s'})
    ledger.account('Forint Reserve', balance=123456, currency='HUF')
    ledger.account('Dollar Reserve', balance=500)
    ledger.db.execute("UPDATE CURRENCYFORMATS_V1 SET PFX_SYMBOL='Ft', SFX_SYMBOL='' WHERE CURRENCY_SYMBOL='HUF'")
    ledger.payee('Local Shop', 'Food:Groceries')
    ledger.trx('Forint Reserve', 'Withdrawal', 3250, '2026-06-01', 'Local Shop', 'Food:Groceries', notes='Legacy groceries')
    return ledger.bytes()


def typed_fields():
    import json
    def extra(ledger):
        for name, kind, properties in [('Units','Integer',{}),('Tax','Decimal',{'DigitScale':3}),
                                       ('Approved','Boolean',{}),('Phase','SingleChoice',{'Choice':['Draft','Final','Review']}),
                                       ('Due','Date',{})]:
            ledger.field('Transaction',name,kind,json.dumps(properties,sort_keys=True))
    return standard(extra)


def json_export():
    """A self-contained export: this upstream release emits only one payee.

    Every destination account also has activity, so its account definition is
    included. All foreign references can then be resolved within the export.
    """
    def extra(ledger):
        ledger.db.execute('UPDATE CHECKINGACCOUNT_V1 SET PAYEEID=? WHERE PAYEEID>0', (ledger.pay['Employer'],))
        ledger.trx('Rainy Day Savings','Deposit',20,'2026-06-10','Employer','Other Income',notes='Savings interest')
    return standard(extra)


def fragmented():
    def extra(ledger):
        for i in range(350):
            ledger.trx('Everyday Checking','Withdrawal',1,'2025-01-01','Grocer','Food:Groceries',notes='Discarded '+str(i)+' '+('x'*8000))
        ledger.db.commit()
        ledger.db.execute("DELETE FROM CHECKINGACCOUNT_V1 WHERE NOTES LIKE 'Discarded %'")
        ledger.db.commit()
        assert ledger.db.execute('PRAGMA freelist_count').fetchone()[0] > 300
    return standard(extra)


def account_actions():
    def extra(ledger):
        ledger.account('Empty Reserve','Checking',0)
        ledger.trx('Rainy Day Savings','Deposit',25,'2026-06-10','Employer','Other Income',notes='Reserve interest')
        ledger.sched('Rainy Day Savings','Withdrawal',5,'2026-07-01',payee='Grocer',category='Food:Groceries',notes='Reserve future',freq=3)
    return standard(extra)


def reconcile():
    L = fixtures.Ledger()
    L.account('Statement','Checking',1000,favorite=True)
    L.account('Reserve','Checking',300)
    L.trx('Statement','Deposit',100,'2026-06-01','Employer','Income:Salary',status='R',notes='Already reconciled')
    L.trx('Statement','Withdrawal',40,'2026-06-02','Grocer','Food:Groceries',notes='Shop')
    L.trx('Statement','Deposit',200,'2026-06-03','Employer','Income:Salary',notes='Extra pay')
    L.trx('Statement','Transfer',50,'2026-06-04',to='Reserve',category='Transfer',notes='Outgoing')
    L.trx('Reserve','Transfer',20,'2026-06-05',to='Statement',category='Transfer',notes='Incoming')
    return L.bytes()


def retention():
    def extra(L):
        for label,deleted in [('Expired','2026-06-04T12:00:00'),('Boundary','2026-06-05T12:00:00'),('Recent','2026-06-06T12:00:00')]:
            L.trx('Everyday Checking','Withdrawal',9,'2026-06-01','Grocer','Food:Groceries',notes=label,deleted=deleted)
    return standard(extra)


def extended_fields():
    import json
    def extra(L):
        L.field('Transaction','Code','String',json.dumps({'RegEx':'^[A-Z]{2}[0-9]{3}$','Default':'AB100','UDFC':'UDFC01'}))
        L.field('Transaction','Labels','MultiChoice',json.dumps({'Choice':['Red','Blue','Green']}))
        L.field('Transaction','Visit','Time')
        for ref,value in ((1,'AB100'),(2,'AB100'),(3,'AB101')):
            L.field_value('Code',ref,value)
    return standard(extra)


def budget_frequency():
    L=fixtures.Ledger(categories=False)
    L.account('Budget Cash','Checking',1000,favorite=True);L.account('Budget Reserve','Checking',100)
    L.budget_year('2026');L.budget_year('2026-06')
    for i,period in enumerate(('None','Weekly','Fortnightly','Monthly','Every 2 Months','Quarterly','Half-Yearly','Yearly','Daily')):
        name=f'Plan {i}'
        L.budget('2026',name,period,-12)
        L.budget('2026-06',name,period,-12)
        L.trx('Budget Cash','Withdrawal',i+1,'2026-06-02','Planner',name,notes='Actual '+period)
    return L.bytes()


def roundtrip():
    L=fixtures.Ledger();L.account('Source','Checking',0);L.account('Target','Checking',0)
    L.trx('Source','Deposit',123.45,'2026-06-01','Employer','Income:Salary',notes='Café bonus',number='RT1',status='R')
    L.trx('Source','Withdrawal',20,'2026-06-02','Grocer','Food:Groceries',notes='Shopping, \"quoted\"',number='RT2',tags=('home','work'))
    L.trx('Source','Withdrawal',30,'2026-06-03','Grocer',notes='Split roundtrip',number='RT3',splits=(('Food:Groceries',12,'fruit'),('Homeneeds:Furnishing',18,'vase')))
    return L.bytes()


def stock_lots():
    return reports(lambda L:L.account('Second Broker','Investment',0))


def budget_policy():
    def extra(L):
        L.budget('2026','Transfer','Yearly',-1200)
        L.trx('Main Checking','Transfer',125,'2026-07-08',to='Savings Pot',category='Transfer',notes='Fiscal allocation')
    return reports(extra)


LEDGERS = {'budget-policy':budget_policy,'stock-lots':stock_lots,'budget-frequency':budget_frequency,'roundtrip':roundtrip,'extended-fields':extended_fields,'account-actions':account_actions,'reconcile':reconcile,'retention':retention,'std': standard, 'reports': reports, 'merges': merges, 'legacy': legacy, 'typed-fields': typed_fields, 'json-export': json_export, 'fragmented': fragmented}


def document(logical):
    key, _, name = logical.rpartition('/')
    if key == 'exchange':
        import exchange_inputs
        return exchange_inputs.document(name)
    if key.startswith('auto-'):
        import schedule_cases
        return schedule_cases.document(key[5:])
    if key in LEDGERS:
        return LEDGERS[key]()
    raise KeyError('unknown document ' + logical)
