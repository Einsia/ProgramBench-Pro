"""Input documents of the episodes, built by the verifier from literal specifications without invoking the product.

Ledger writes a database document (.mmb) directly: the schema below is the product's database version 21, the categories
are the defaults of a new database, the currencies a subset of its table. Identifiers are small numbers and every value is
literal, so a ledger is byte-identical on every build. The text formats (CSV, QIF, OFX, XML) are written by their own
builders further down.
"""
import os
import sqlite3
import tempfile

DB_VERSION = 21

SCHEMA = (
    'CREATE TABLE ACCOUNTLIST_V1(ACCOUNTID integer primary key, ACCOUNTNAME TEXT COLLATE NOCASE NOT NULL UNIQUE, ACCOUNTTYPE TEXT NOT NULL /* Cash, Checking, Term, Investment, Credit Card, Loan, Asset, Shares */, ACCOUNTNUM TEXT, STATUS TEXT NOT NULL /* Open, Closed */, NOTES TEXT, HELDAT TEXT, WEBSITE TEXT, CONTACTINFO TEXT, ACCESSINFO TEXT, INITIALBAL numeric, INITIALDATE TEXT, FAVORITEACCT TEXT NOT NULL, CURRENCYID integer NOT NULL, STATEMENTLOCKED integer, STATEMENTDATE TEXT, MINIMUMBALANCE numeric, CREDITLIMIT numeric, INTERESTRATE numeric, PAYMENTDUEDATE text, MINIMUMPAYMENT numeric)',
    'CREATE TABLE ASSETS_V1(ASSETID integer primary key, STARTDATE TEXT NOT NULL, ASSETNAME TEXT COLLATE NOCASE NOT NULL, ASSETSTATUS TEXT /* Open, Closed */, CURRENCYID integer, VALUECHANGEMODE TEXT /* Percentage, Linear */, VALUE numeric, VALUECHANGE TEXT /* None, Appreciates, Depreciates */, NOTES TEXT, VALUECHANGERATE numeric, ASSETTYPE TEXT /* Property, Automobile, Household Object, Art, Jewellery, Cash, Other */)',
    'CREATE TABLE ATTACHMENT_V1 (ATTACHMENTID INTEGER NOT NULL PRIMARY KEY, REFTYPE TEXT NOT NULL /* Transaction, Stock, Asset, Bank Account, Repeating Transaction, Payee */, REFID INTEGER NOT NULL, DESCRIPTION TEXT COLLATE NOCASE, FILENAME TEXT NOT NULL COLLATE NOCASE)',
    'CREATE TABLE BILLSDEPOSITS_V1(BDID integer primary key, ACCOUNTID integer NOT NULL, TOACCOUNTID integer, PAYEEID integer NOT NULL, TRANSCODE TEXT NOT NULL /* Withdrawal, Deposit, Transfer */, TRANSAMOUNT numeric NOT NULL, STATUS TEXT /* None, Reconciled, Void, Follow up, Duplicate */, TRANSACTIONNUMBER TEXT, NOTES TEXT, CATEGID integer, TRANSDATE TEXT, FOLLOWUPID integer, TOTRANSAMOUNT numeric, REPEATS integer, NEXTOCCURRENCEDATE TEXT, NUMOCCURRENCES integer, COLOR integer DEFAULT -1)',
    'CREATE TABLE BUDGETSPLITTRANSACTIONS_V1(SPLITTRANSID integer primary key, TRANSID integer NOT NULL, CATEGID integer, SPLITTRANSAMOUNT numeric, NOTES TEXT)',
    'CREATE TABLE BUDGETTABLE_V1(BUDGETENTRYID integer primary key, BUDGETYEARID integer, CATEGID integer, PERIOD TEXT NOT NULL /* None, Weekly, Bi-Weekly, Monthly, Monthly, Bi-Monthly, Quarterly, Half-Yearly, Yearly, Daily*/, AMOUNT numeric NOT NULL, NOTES TEXT, ACTIVE integer)',
    'CREATE TABLE BUDGETYEAR_V1(BUDGETYEARID integer primary key, BUDGETYEARNAME TEXT NOT NULL UNIQUE)',
    'CREATE TABLE CATEGORY_V1( CATEGID INTEGER PRIMARY KEY,  CATEGNAME TEXT NOT NULL COLLATE NOCASE,  ACTIVE INTEGER,  PARENTID INTEGER,  UNIQUE(CATEGNAME, PARENTID))',
    'CREATE TABLE CHECKINGACCOUNT_V1(TRANSID integer primary key, ACCOUNTID integer NOT NULL, TOACCOUNTID integer, PAYEEID integer NOT NULL, TRANSCODE TEXT NOT NULL /* Withdrawal, Deposit, Transfer */, TRANSAMOUNT numeric NOT NULL, STATUS TEXT /* None, Reconciled, Void, Follow up, Duplicate */, TRANSACTIONNUMBER TEXT, NOTES TEXT, CATEGID integer, TRANSDATE TEXT, LASTUPDATEDTIME TEXT, DELETEDTIME TEXT, FOLLOWUPID integer, TOTRANSAMOUNT numeric, COLOR integer DEFAULT -1)',
    'CREATE TABLE CURRENCYFORMATS_V1(CURRENCYID integer primary key, CURRENCYNAME TEXT COLLATE NOCASE NOT NULL UNIQUE, PFX_SYMBOL TEXT, SFX_SYMBOL TEXT, DECIMAL_POINT TEXT, GROUP_SEPARATOR TEXT, UNIT_NAME TEXT COLLATE NOCASE, CENT_NAME TEXT COLLATE NOCASE, SCALE integer, BASECONVRATE numeric, CURRENCY_SYMBOL TEXT COLLATE NOCASE NOT NULL UNIQUE, CURRENCY_TYPE TEXT NOT NULL /* Fiat, Crypto */)',
    'CREATE TABLE CURRENCYHISTORY_V1(CURRHISTID INTEGER PRIMARY KEY, CURRENCYID INTEGER NOT NULL, CURRDATE TEXT NOT NULL, CURRVALUE NUMERIC NOT NULL, CURRUPDTYPE INTEGER, UNIQUE(CURRENCYID, CURRDATE))',
    'CREATE TABLE CUSTOMFIELDDATA_V1 (FIELDATADID INTEGER NOT NULL PRIMARY KEY, FIELDID INTEGER NOT NULL, REFID INTEGER NOT NULL, CONTENT TEXT, UNIQUE(FIELDID, REFID))',
    'CREATE TABLE CUSTOMFIELD_V1 (FIELDID INTEGER NOT NULL PRIMARY KEY, REFTYPE TEXT NOT NULL /* Transaction, Stock, Asset, Bank Account, Repeating Transaction, Payee */, DESCRIPTION TEXT COLLATE NOCASE, TYPE TEXT NOT NULL /* String, Integer, Decimal, Boolean, Date, Time, SingleChoice, MultiChoice */, PROPERTIES TEXT NOT NULL)',
    'CREATE TABLE INFOTABLE_V1(INFOID integer not null primary key, INFONAME TEXT COLLATE NOCASE NOT NULL UNIQUE, INFOVALUE TEXT NOT NULL)',
    "CREATE TABLE PAYEE_V1(PAYEEID integer primary key, PAYEENAME TEXT COLLATE NOCASE NOT NULL UNIQUE, CATEGID integer, NUMBER TEXT, WEBSITE TEXT, NOTES TEXT, ACTIVE integer, PATTERN TEXT DEFAULT '')",
    'CREATE TABLE REPORT_V1(REPORTID integer not null primary key, REPORTNAME TEXT COLLATE NOCASE NOT NULL UNIQUE, GROUPNAME TEXT COLLATE NOCASE, ACTIVE integer, SQLCONTENT TEXT, LUACONTENT TEXT, TEMPLATECONTENT TEXT, DESCRIPTION TEXT)',
    'CREATE TABLE SHAREINFO_V1 (SHAREINFOID integer NOT NULL primary key, CHECKINGACCOUNTID integer NOT NULL, SHARENUMBER numeric, SHAREPRICE numeric, SHARECOMMISSION numeric, SHARELOT TEXT)',
    'CREATE TABLE SPLITTRANSACTIONS_V1(SPLITTRANSID integer primary key, TRANSID integer NOT NULL, CATEGID integer, SPLITTRANSAMOUNT numeric, NOTES TEXT)',
    'CREATE TABLE STOCKHISTORY_V1(HISTID integer primary key, SYMBOL TEXT NOT NULL, DATE TEXT NOT NULL, VALUE numeric NOT NULL, UPDTYPE integer, UNIQUE(SYMBOL, DATE))',
    'CREATE TABLE STOCK_V1(STOCKID integer primary key, HELDAT integer, PURCHASEDATE TEXT NOT NULL, STOCKNAME TEXT COLLATE NOCASE NOT NULL, SYMBOL TEXT, NUMSHARES numeric, PURCHASEPRICE numeric NOT NULL, NOTES TEXT, CURRENTPRICE numeric NOT NULL, VALUE numeric, COMMISSION numeric)',
    'CREATE TABLE TAGLINK_V1(TAGLINKID INTEGER PRIMARY KEY, REFTYPE TEXT NOT NULL, REFID INTEGER NOT NULL, TAGID INTEGER NOT NULL, FOREIGN KEY (TAGID) REFERENCES TAG_V1 (TAGID), UNIQUE(REFTYPE, REFID, TAGID))',
    'CREATE TABLE TAG_V1(TAGID INTEGER PRIMARY KEY, TAGNAME TEXT COLLATE NOCASE NOT NULL UNIQUE, ACTIVE INTEGER)',
    'CREATE TABLE TRANSLINK_V1 (TRANSLINKID  integer NOT NULL primary key, CHECKINGACCOUNTID integer NOT NULL, LINKTYPE TEXT NOT NULL /* Asset, Stock */, LINKRECORDID integer NOT NULL)',
    'CREATE INDEX IDX_ACCOUNTLIST_ACCOUNTTYPE ON ACCOUNTLIST_V1(ACCOUNTTYPE)',
    'CREATE INDEX IDX_ASSETS_ASSETTYPE ON ASSETS_V1(ASSETTYPE)',
    'CREATE INDEX IDX_ATTACHMENT_REF ON ATTACHMENT_V1 (REFTYPE, REFID)',
    'CREATE INDEX IDX_BILLSDEPOSITS_ACCOUNT ON BILLSDEPOSITS_V1 (ACCOUNTID, TOACCOUNTID)',
    'CREATE INDEX IDX_BUDGETSPLITTRANSACTIONS_TRANSID ON BUDGETSPLITTRANSACTIONS_V1(TRANSID)',
    'CREATE INDEX IDX_BUDGETTABLE_BUDGETYEARID ON BUDGETTABLE_V1(BUDGETYEARID)',
    'CREATE INDEX IDX_BUDGETYEAR_BUDGETYEARNAME ON BUDGETYEAR_V1(BUDGETYEARNAME)',
    'CREATE INDEX IDX_CATEGORY_CATEGNAME ON CATEGORY_V1(CATEGNAME)',
    'CREATE INDEX IDX_CATEGORY_CATEGNAME_PARENTID ON CATEGORY_V1(CATEGNAME, PARENTID)',
    'CREATE INDEX IDX_CHECKINGACCOUNT ON TRANSLINK_V1 (CHECKINGACCOUNTID)',
    'CREATE INDEX IDX_CHECKINGACCOUNT_ACCOUNT ON CHECKINGACCOUNT_V1 (ACCOUNTID, TOACCOUNTID)',
    'CREATE INDEX IDX_CHECKINGACCOUNT_TRANSDATE ON CHECKINGACCOUNT_V1 (TRANSDATE)',
    'CREATE INDEX IDX_CURRENCYFORMATS_SYMBOL ON CURRENCYFORMATS_V1(CURRENCY_SYMBOL)',
    'CREATE INDEX IDX_CURRENCYHISTORY_CURRENCYID_CURRDATE ON CURRENCYHISTORY_V1(CURRENCYID, CURRDATE)',
    'CREATE INDEX IDX_CUSTOMFIELDDATA_REF ON CUSTOMFIELDDATA_V1 (FIELDID, REFID)',
    'CREATE INDEX IDX_CUSTOMFIELD_REF ON CUSTOMFIELD_V1 (REFTYPE)',
    'CREATE INDEX IDX_INFOTABLE_INFONAME ON INFOTABLE_V1(INFONAME)',
    'CREATE INDEX IDX_LINKRECORD ON TRANSLINK_V1 (LINKTYPE, LINKRECORDID)',
    'CREATE INDEX IDX_PAYEE_INFONAME ON PAYEE_V1(PAYEENAME)',
    'CREATE INDEX IDX_SHAREINFO ON SHAREINFO_V1 (CHECKINGACCOUNTID)',
    'CREATE INDEX IDX_SPLITTRANSACTIONS_TRANSID ON SPLITTRANSACTIONS_V1(TRANSID)',
    'CREATE INDEX IDX_STOCKHISTORY_SYMBOL ON STOCKHISTORY_V1(SYMBOL)',
    'CREATE INDEX IDX_STOCK_HELDAT ON STOCK_V1(HELDAT)',
    'CREATE INDEX IDX_TAGLINK ON TAGLINK_V1 (REFTYPE, REFID, TAGID)',
    'CREATE INDEX IDX_TAGNAME ON TAG_V1 (TAGNAME)',
    'CREATE INDEX INDEX_REPORT_NAME ON REPORT_V1(REPORTNAME)',
)

CATEGORIES = (
    (1, 'Bills', 1, -1),
    (2, 'Telephone', 1, 1),
    (3, 'Electricity', 1, 1),
    (4, 'Gas', 1, 1),
    (5, 'Internet', 1, 1),
    (6, 'Rent', 1, 1),
    (7, 'Cable TV', 1, 1),
    (8, 'Water', 1, 1),
    (9, 'Food', 1, -1),
    (10, 'Groceries', 1, 9),
    (11, 'Dining out', 1, 9),
    (12, 'Leisure', 1, -1),
    (13, 'Movies', 1, 12),
    (14, 'Video Rental', 1, 12),
    (15, 'Magazines', 1, 12),
    (16, 'Automobile', 1, -1),
    (17, 'Maintenance', 1, 16),
    (18, 'Gas', 1, 16),
    (19, 'Parking', 1, 16),
    (20, 'Registration', 1, 16),
    (21, 'Education', 1, -1),
    (22, 'Books', 1, 21),
    (23, 'Tuition', 1, 21),
    (24, 'Others', 1, 21),
    (25, 'Homeneeds', 1, -1),
    (26, 'Clothing', 1, 25),
    (27, 'Furnishing', 1, 25),
    (28, 'Others', 1, 25),
    (29, 'Healthcare', 1, -1),
    (30, 'Health', 1, 29),
    (31, 'Dental', 1, 29),
    (32, 'Eyecare', 1, 29),
    (33, 'Physician', 1, 29),
    (34, 'Prescriptions', 1, 29),
    (35, 'Insurance', 1, -1),
    (36, 'Auto', 1, 35),
    (37, 'Life', 1, 35),
    (38, 'Home', 1, 35),
    (39, 'Health', 1, 35),
    (40, 'Vacation', 1, -1),
    (41, 'Travel', 1, 40),
    (42, 'Lodging', 1, 40),
    (43, 'Sightseeing', 1, 40),
    (44, 'Taxes', 1, -1),
    (45, 'Income Tax', 1, 44),
    (46, 'House Tax', 1, 44),
    (47, 'Water Tax', 1, 44),
    (48, 'Others', 1, 44),
    (49, 'Miscellaneous', 1, -1),
    (50, 'Gifts', 1, -1),
    (51, 'Income', 1, -1),
    (52, 'Salary', 1, 51),
    (53, 'Reimbursement/Refunds', 1, 51),
    (54, 'Investment Income', 1, 51),
    (55, 'Other Income', 1, -1),
    (56, 'Other Expenses', 1, -1),
    (57, 'Transfer', 1, -1),
    (58, 'Investment', 1, -1),
    (59, 'Purchase', 1, 58),
    (60, 'Sale', 1, 58),
    (61, 'Dividend', 1, 58),
    (62, 'Capital Gains', 1, 58),
    (63, 'Brokerage Fees', 1, 58),
    (64, 'Interest', 1, 58),
    (65, 'Taxes', 1, 58),
    (66, 'Split', 1, 58),
    (67, 'Merger', 1, 58),
)
CURRENCIES = {
    'USD': (1, 'US dollar', '$', '', '.', ',', 'Dollar', 'Cent', 100, 1, 'USD', 'Fiat'),
    'EUR': (2, 'Euro', '€', '', '.', ' ', '', '', 100, 1, 'EUR', 'Fiat'),
    'GBP': (3, 'British pound', '£', '', '.', ' ', 'Pound', 'Pence', 100, 1, 'GBP', 'Fiat'),
    'AUD': (14, 'Australian dollar', '$', '', '.', ',', '', '', 100, 1, 'AUD', 'Fiat'),
    'CAD': (34, 'Canadian dollar', '$', '', '.', ' ', '', '', 100, 1, 'CAD', 'Fiat'),
    'CNY': (38, 'Chinese yuan', '¥', '', '.', ' ', '', '', 100, 1, 'CNY', 'Fiat'),
    'HUF': (64, 'Hungarian forint', '', 'Ft', '.', ' ', '', '', 1, 1, 'HUF', 'Fiat'),
    'INR': (66, 'Indian rupee', '₹', '', '.', ' ', '', '', 100, 1, 'INR', 'Fiat'),
    'JPY': (73, 'Japanese yen', '¥', '', '.', ' ', '', '', 1, 1, 'JPY', 'Fiat'),
    'SEK': (133, 'Swedish krona', 'kr', '', '.', ' ', '', '', 100, 1, 'SEK', 'Fiat'),
    'CHF': (134, 'Swiss franc', 'Fr.', '', '.', ' ', '', '', 100, 1, 'CHF', 'Fiat'),
}


class Ledger:
    """One database document under construction."""

    def __init__(self, base='USD', currencies=('USD', 'EUR', 'GBP', 'JPY', 'CAD', 'CHF', 'INR', 'SEK', 'HUF'), user='Pat Example',
                 rates=None, info=None, version=DB_VERSION, categories=True):
        self.folder = tempfile.TemporaryDirectory(prefix='ledger-')
        self.path = os.path.join(self.folder.name, 'ledger.mmb')
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA page_size=4096')
        for statement in SCHEMA:
            self.db.execute(statement)
        self.db.execute(f'PRAGMA user_version={version}')
        self.next_id = {}
        self.cur = {}
        for symbol in currencies:
            row = list(CURRENCIES[symbol])
            if rates and symbol in rates:
                row[9] = rates[symbol]
            self.db.execute('INSERT INTO CURRENCYFORMATS_V1(CURRENCYID,CURRENCYNAME,PFX_SYMBOL,SFX_SYMBOL,DECIMAL_POINT,'
                            'GROUP_SEPARATOR,UNIT_NAME,CENT_NAME,SCALE,BASECONVRATE,CURRENCY_SYMBOL,CURRENCY_TYPE) '
                            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', row)
            self.cur[symbol] = row[0]
        self.base = base
        values = {'DATAVERSION': '3', 'MMEXVERSION': '1.9.4', 'CREATEDATE': '2025-01-01', 'DATEFORMAT': '%Y-%m-%d',
                  'BASECURRENCYID': str(self.cur[base]), 'USERNAME': user}
        values.update(info or {})
        for name, value in values.items():
            self.db.execute('INSERT INTO INFOTABLE_V1(INFONAME, INFOVALUE) VALUES (?, ?)', (name, value))
        self.cat = {}
        if categories:
            names = {row[0]: row for row in CATEGORIES}
            for row in CATEGORIES:
                self.db.execute('INSERT INTO CATEGORY_V1(CATEGID,CATEGNAME,ACTIVE,PARENTID) VALUES (?,?,?,?)', row)
                self.cat[(names[row[3]][1] + ':' if row[3] > 0 else '') + row[1]] = row[0]
            self.next_id['CATEGORY_V1'] = 1000
        self.acc = {}
        self.pay = {}
        self.tags = {}
        self.fld = {}
        self.years = {}
        self.stocks = {}
        self.assets = {}

    def new_id(self, table, start=1):
        value = self.next_id.get(table, start)
        self.next_id[table] = value + 1
        return value

    def info(self, name, value):
        self.db.execute('INSERT OR REPLACE INTO INFOTABLE_V1(INFOID, INFONAME, INFOVALUE) VALUES '
                        '((SELECT INFOID FROM INFOTABLE_V1 WHERE INFONAME=?), ?, ?)', (name, name, value))

    def category(self, path, active=1):
        """A category path such as Food:Groceries; missing levels are created."""
        if path in (None, ''):
            return -1
        if path in self.cat:
            return self.cat[path]
        parent, _, name = path.rpartition(':')
        parent_id = self.category(parent) if parent else -1
        new = self.new_id('CATEGORY_V1', 1000)
        self.db.execute('INSERT INTO CATEGORY_V1(CATEGID,CATEGNAME,ACTIVE,PARENTID) VALUES (?,?,?,?)', (new, name, active, parent_id))
        self.cat[path] = new
        return new

    def account(self, name, kind='Checking', balance=0.0, opened='2025-01-01', currency=None, favorite=False, status='Open',
                number='', notes='', held='', website='', contact='', access='', locked=0, statement='', minimum=0.0, limit=0.0,
                interest=0.0, due='', payment=0.0):
        new = self.new_id('ACCOUNTLIST_V1')
        self.db.execute('INSERT INTO ACCOUNTLIST_V1(ACCOUNTID,ACCOUNTNAME,ACCOUNTTYPE,ACCOUNTNUM,STATUS,NOTES,HELDAT,WEBSITE,'
                        'CONTACTINFO,ACCESSINFO,INITIALBAL,INITIALDATE,FAVORITEACCT,CURRENCYID,STATEMENTLOCKED,STATEMENTDATE,'
                        'MINIMUMBALANCE,CREDITLIMIT,INTERESTRATE,PAYMENTDUEDATE,MINIMUMPAYMENT) '
                        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (new, name, kind, number, status, notes, held, website, contact, access, balance, opened,
                         'TRUE' if favorite else 'FALSE', self.cur[currency or self.base], locked, statement, minimum, limit,
                         interest, due, payment))
        self.acc[name] = new
        return new

    def payee(self, name, category=None, number='', website='', notes='', active=1, pattern=''):
        new = self.new_id('PAYEE_V1')
        self.db.execute('INSERT INTO PAYEE_V1(PAYEEID,PAYEENAME,CATEGID,NUMBER,WEBSITE,NOTES,ACTIVE,PATTERN) VALUES (?,?,?,?,?,?,?,?)',
                        (new, name, self.category(category), number, website, notes, active, pattern))
        self.pay[name] = new
        return new

    def tag(self, name, active=1):
        if name not in self.tags:
            new = self.new_id('TAG_V1')
            self.db.execute('INSERT INTO TAG_V1(TAGID,TAGNAME,ACTIVE) VALUES (?,?,?)', (new, name, active))
            self.tags[name] = new
        return self.tags[name]

    def link_tags(self, kind, ref, names):
        for name in names:
            self.db.execute('INSERT INTO TAGLINK_V1(REFTYPE,REFID,TAGID) VALUES (?,?,?)', (kind, ref, self.tag(name)))

    def field(self, kind, description, field_type='String', properties='{}'):
        new = self.new_id('CUSTOMFIELD_V1')
        self.db.execute('INSERT INTO CUSTOMFIELD_V1(FIELDID,REFTYPE,DESCRIPTION,TYPE,PROPERTIES) VALUES (?,?,?,?,?)',
                        (new, kind, description, field_type, properties))
        self.fld[description] = new
        return new

    def field_value(self, description, ref, content):
        self.db.execute('INSERT INTO CUSTOMFIELDDATA_V1(FIELDID,REFID,CONTENT) VALUES (?,?,?)', (self.fld[description], ref, content))

    def _payee_id(self, payee):
        if payee in (None, ''):
            return -1
        return self.pay[payee] if payee in self.pay else self.payee(payee)

    def trx(self, account, code, amount, date, payee=None, category=None, status='', number='', notes='', to=None, to_amount=None,
            color=-1, deleted='', tags=(), splits=(), fields=None, time='00:00:00', updated='2026-01-01T00:00:00.000'):
        new = self.new_id('CHECKINGACCOUNT_V1')
        self.db.execute('INSERT INTO CHECKINGACCOUNT_V1(TRANSID,ACCOUNTID,TOACCOUNTID,PAYEEID,TRANSCODE,TRANSAMOUNT,STATUS,'
                        'TRANSACTIONNUMBER,NOTES,CATEGID,TRANSDATE,LASTUPDATEDTIME,DELETEDTIME,FOLLOWUPID,TOTRANSAMOUNT,COLOR) '
                        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (new, self.acc[account], self.acc[to] if to else -1, self._payee_id(payee), code, amount, status, number, notes,
                         self.category(category), f'{date}T{time}', updated, deleted, -1,
                         amount if to_amount is None and to else (to_amount or 0.0), color))
        self.link_tags('Transaction', new, tags)
        for item in splits:
            split = self.new_id('SPLITTRANSACTIONS_V1')
            self.db.execute('INSERT INTO SPLITTRANSACTIONS_V1(SPLITTRANSID,TRANSID,CATEGID,SPLITTRANSAMOUNT,NOTES) VALUES (?,?,?,?,?)',
                            (split, new, self.category(item[0]), item[1], item[2] if len(item) > 2 else ''))
            if len(item) > 3:
                self.link_tags('TransactionSplit', split, item[3])
        for name, content in (fields or {}).items():
            self.field_value(name, new, content)
        return new

    def sched(self, account, code, amount, date, freq=0, mode=0, num=-1, payee=None, category=None, status='', number='', notes='',
              to=None, to_amount=None, color=-1, due=None, tags=(), splits=(), fields=None, time='00:00:00'):
        new = self.new_id('BILLSDEPOSITS_V1')
        self.db.execute('INSERT INTO BILLSDEPOSITS_V1(BDID,ACCOUNTID,TOACCOUNTID,PAYEEID,TRANSCODE,TRANSAMOUNT,STATUS,TRANSACTIONNUMBER,'
                        'NOTES,CATEGID,TRANSDATE,FOLLOWUPID,TOTRANSAMOUNT,REPEATS,NEXTOCCURRENCEDATE,NUMOCCURRENCES,COLOR) '
                        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (new, self.acc[account], self.acc[to] if to else -1, self._payee_id(payee), code, amount, status, number, notes,
                         self.category(category), f'{date}T{time}', -1, amount if to_amount is None and to else (to_amount or 0.0),
                         mode * 100 + freq, due or date, num, color))
        self.link_tags('RecurringTransaction', new, tags)
        for item in splits:
            split = self.new_id('BUDGETSPLITTRANSACTIONS_V1')
            self.db.execute('INSERT INTO BUDGETSPLITTRANSACTIONS_V1(SPLITTRANSID,TRANSID,CATEGID,SPLITTRANSAMOUNT,NOTES) VALUES (?,?,?,?,?)',
                            (split, new, self.category(item[0]), item[1], item[2] if len(item) > 2 else ''))
            if len(item) > 3:
                self.link_tags('RecurringTransactionSplit', split, item[3])
        for name, content in (fields or {}).items():
            self.field_value(name, new, content)
        return new

    def budget_year(self, name):
        new = self.new_id('BUDGETYEAR_V1')
        self.db.execute('INSERT INTO BUDGETYEAR_V1(BUDGETYEARID,BUDGETYEARNAME) VALUES (?,?)', (new, name))
        self.years[name] = new
        return new

    def budget(self, year, category, period, amount, notes='', active=1):
        new = self.new_id('BUDGETTABLE_V1')
        self.db.execute('INSERT INTO BUDGETTABLE_V1(BUDGETENTRYID,BUDGETYEARID,CATEGID,PERIOD,AMOUNT,NOTES,ACTIVE) VALUES (?,?,?,?,?,?,?)',
                        (new, self.years[year], self.category(category), period, amount, notes, active))
        return new

    def asset(self, name, kind='Property', value=0.0, date='2025-01-01', status='Open', change='None', rate=0.0, mode='Percentage',
              notes='', currency=-1):
        new = self.new_id('ASSETS_V1')
        self.db.execute('INSERT INTO ASSETS_V1(ASSETID,STARTDATE,ASSETNAME,ASSETSTATUS,CURRENCYID,VALUECHANGEMODE,VALUE,VALUECHANGE,NOTES,'
                        'VALUECHANGERATE,ASSETTYPE) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (new, date, name, status, currency, mode, value, change, notes, rate, kind))
        self.assets[name] = new
        return new

    def stock(self, account, name, symbol, shares, price, date='2025-01-01', current=None, commission=0.0, notes=''):
        new = self.new_id('STOCK_V1')
        current = price if current is None else current
        self.db.execute('INSERT INTO STOCK_V1(STOCKID,HELDAT,PURCHASEDATE,STOCKNAME,SYMBOL,NUMSHARES,PURCHASEPRICE,NOTES,CURRENTPRICE,VALUE,'
                        'COMMISSION) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (new, self.acc[account], date, name, symbol, shares, price, notes, current, shares * current, commission))
        self.stocks[name] = new
        return new

    def stock_price(self, symbol, date, value, kind=1):
        self.db.execute('INSERT INTO STOCKHISTORY_V1(SYMBOL,DATE,VALUE,UPDTYPE) VALUES (?,?,?,?)', (symbol, date, value, kind))

    def currency_rate(self, symbol, date, value, kind=1):
        self.db.execute('INSERT INTO CURRENCYHISTORY_V1(CURRENCYID,CURRDATE,CURRVALUE,CURRUPDTYPE) VALUES (?,?,?,?)',
                        (self.cur[symbol], date, value, kind))

    def bytes(self):
        self.db.commit()
        self.db.close()
        with open(self.path, 'rb') as stream:
            content = stream.read()
        self.folder.cleanup()
        return content
