"""Reads a database document into a semantic view: names instead of identifiers, one record per row.

The verifier opens the file with the standard sqlite3 module. Generated identifiers, last-update times and the product's
bookkeeping values are left out of the view; what is compared is what a user entered or the product derived.
A missing table or column raises sqlite3.Error, which fails only the points that need it.
"""
import sqlite3
import json


def number(value):
    if value is None or value == '':
        return 0.0
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return value


def text(value):
    return '' if value is None else str(value)


class View:
    def __init__(self, path):
        self.db = sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True)
        self.db.row_factory = sqlite3.Row
        self.db.text_factory = lambda raw: raw.decode('utf-8', 'replace')
        self.cache = {}

    def close(self):
        self.db.close()

    def rows(self, table, order=None):
        statement = f'SELECT * FROM {table}' + (f' ORDER BY {order}' if order else '')
        return [dict(row) for row in self.db.execute(statement)]

    def table(self, name):
        """One semantic table by name (built on first use)."""
        if name not in self.cache:
            self.cache[name] = getattr(self, 'load_' + name)()
        return self.cache[name]

    # Lookups --------------------------------------------------------------------------------------------------
    def account_names(self):
        if 'account_names' not in self.cache:
            self.cache['account_names'] = {r['ACCOUNTID']: r['ACCOUNTNAME'] for r in self.rows('ACCOUNTLIST_V1')}
        return self.cache['account_names']

    def payee_names(self):
        if 'payee_names' not in self.cache:
            self.cache['payee_names'] = {r['PAYEEID']: r['PAYEENAME'] for r in self.rows('PAYEE_V1')}
        return self.cache['payee_names']

    def category_paths(self):
        if 'category_paths' not in self.cache:
            rows = {r['CATEGID']: r for r in self.rows('CATEGORY_V1')}
            paths = {}

            def path(identifier, depth=0):
                row = rows.get(identifier)
                if row is None or depth > 32:
                    return ''
                parent = row.get('PARENTID')
                above = path(parent, depth + 1) if parent not in (None, -1, identifier) else ''
                return (above + ':' if above else '') + text(row['CATEGNAME'])
            for identifier in rows:
                paths[identifier] = path(identifier)
            self.cache['category_paths'] = paths
        return self.cache['category_paths']

    def currency_symbols(self):
        if 'currency_symbols' not in self.cache:
            self.cache['currency_symbols'] = {r['CURRENCYID']: r['CURRENCY_SYMBOL'] for r in self.rows('CURRENCYFORMATS_V1')}
        return self.cache['currency_symbols']

    def tag_links(self):
        """{(reference type, reference id): sorted tag names}"""
        if 'tag_links' not in self.cache:
            names = {r['TAGID']: r['TAGNAME'] for r in self.rows('TAG_V1')}
            links = {}
            for row in self.rows('TAGLINK_V1'):
                links.setdefault((row['REFTYPE'], row['REFID']), []).append(text(names.get(row['TAGID'], '?')))
            self.cache['tag_links'] = {key: sorted(value, key=str.casefold) for key, value in links.items()}
        return self.cache['tag_links']

    def field_definitions(self):
        if 'field_definitions' not in self.cache:
            self.cache['field_definitions'] = {r['FIELDID']: r for r in self.rows('CUSTOMFIELD_V1')}
        return self.cache['field_definitions']

    def field_values(self, kind):
        """{reference id: {field description: content}} of one reference type"""
        key = 'field_values:' + kind
        if key not in self.cache:
            definitions = self.field_definitions()
            values = {}
            for row in self.rows('CUSTOMFIELDDATA_V1'):
                definition = definitions.get(row['FIELDID'])
                reference = row['REFID']
                actual_kind = 'RecurringTransaction' if reference < 0 else 'Transaction'
                if definition is not None and actual_kind == kind:
                    content=text(row['CONTENT'])
                    if definition['TYPE']=='MultiChoice':
                        content=';'.join(sorted(set(content.split(';')))) if content else ''
                    values.setdefault(abs(reference), {})[text(definition['DESCRIPTION'])] = content
            self.cache[key] = values
        return self.cache[key]

    def attachments(self, kind):
        key = 'attachments:' + kind
        if key not in self.cache:
            values = {}
            for row in self.rows('ATTACHMENT_V1'):
                if row['REFTYPE'] == kind:
                    values.setdefault(row['REFID'], []).append(text(row['DESCRIPTION']))
            self.cache[key] = {k: sorted(v) for k, v in values.items()}
        return self.cache[key]

    # Tables --------------------------------------------------------------------------------------------------
    def load_info(self):
        return [{'name': text(r['INFONAME']), 'value': text(r['INFOVALUE'])} for r in self.rows('INFOTABLE_V1')]

    def load_account(self):
        symbols = self.currency_symbols()
        result = []
        for r in self.rows('ACCOUNTLIST_V1'):
            result.append({'name': text(r['ACCOUNTNAME']), 'type': text(r['ACCOUNTTYPE']), 'number': text(r['ACCOUNTNUM']),
                           'status': text(r['STATUS']), 'notes': text(r['NOTES']), 'held_at': text(r['HELDAT']),
                           'website': text(r['WEBSITE']), 'contact': text(r['CONTACTINFO']), 'access': text(r['ACCESSINFO']),
                           'balance': number(r['INITIALBAL']), 'opened': text(r['INITIALDATE'])[:10],
                           'favorite': text(r['FAVORITEACCT']), 'currency': text(symbols.get(r['CURRENCYID'], '?')),
                           'statement_locked': number(r['STATEMENTLOCKED']), 'statement_date': text(r['STATEMENTDATE'])[:10],
                           'minimum_balance': number(r['MINIMUMBALANCE']), 'credit_limit': number(r['CREDITLIMIT']),
                           'interest': number(r['INTERESTRATE']), 'due_date': text(r['PAYMENTDUEDATE'])[:10],
                           'minimum_payment': number(r['MINIMUMPAYMENT'])})
        return result

    def load_payee(self):
        paths = self.category_paths()
        return [{'name': text(r['PAYEENAME']), 'category': text(paths.get(r['CATEGID'], '')), 'number': text(r['NUMBER']),
                 'website': text(r['WEBSITE']), 'notes': text(r['NOTES']), 'active': number(r['ACTIVE']),
                 'pattern': text(r['PATTERN'])} for r in self.rows('PAYEE_V1')]

    def load_category(self):
        paths = self.category_paths()
        return [{'path': paths[r['CATEGID']], 'name': text(r['CATEGNAME']), 'active': number(r['ACTIVE'])}
                for r in self.rows('CATEGORY_V1')]

    def load_tag(self):
        return [{'name': text(r['TAGNAME']), 'active': number(r['ACTIVE'])} for r in self.rows('TAG_V1')]

    def load_currency(self):
        return [{'symbol': text(r['CURRENCY_SYMBOL']), 'name': text(r['CURRENCYNAME']), 'prefix': text(r['PFX_SYMBOL']),
                 'suffix': text(r['SFX_SYMBOL']), 'decimal': text(r['DECIMAL_POINT']), 'group': text(r['GROUP_SEPARATOR']),
                 'unit': text(r['UNIT_NAME']), 'cent': text(r['CENT_NAME']), 'scale': number(r['SCALE']),
                 'rate': number(r['BASECONVRATE']), 'type': text(r['CURRENCY_TYPE'])} for r in self.rows('CURRENCYFORMATS_V1')]

    def load_currency_history(self):
        symbols = self.currency_symbols()
        return [{'symbol': text(symbols.get(r['CURRENCYID'], '?')), 'date': text(r['CURRDATE'])[:10], 'rate': number(r['CURRVALUE']),
                 'kind': number(r['CURRUPDTYPE'])} for r in self.rows('CURRENCYHISTORY_V1')]

    def _transaction(self, r, tag_kind, field_kind, split_rows, split_tag_kind):
        accounts, payees, paths = self.account_names(), self.payee_names(), self.category_paths()
        links = self.tag_links()
        identifier = r.get('TRANSID', r.get('BDID'))
        splits = []
        for item in split_rows.get(identifier, ()):
            splits.append({'category': text(paths.get(item['CATEGID'], '')), 'amount': number(item['SPLITTRANSAMOUNT']),
                           'notes': text(item['NOTES']),
                           'tags': links.get((split_tag_kind, item['SPLITTRANSID']), [])})
        splits.sort(key=lambda s: (s['category'].casefold(), s['amount'], s['notes']))
        stamp = text(r['TRANSDATE'])
        return {'account': text(accounts.get(r['ACCOUNTID'], '')), 'to_account': text(accounts.get(r['TOACCOUNTID'], '')),
                'payee': text(payees.get(r['PAYEEID'], '')), 'type': text(r['TRANSCODE']), 'amount': number(r['TRANSAMOUNT']),
                'to_amount': number(r['TOTRANSAMOUNT']), 'status': text(r['STATUS']), 'number': text(r['TRANSACTIONNUMBER']),
                'notes': text(r['NOTES']), 'category': text(paths.get(r['CATEGID'], '')), 'date': stamp[:10], 'time': stamp[11:19],
                'color': number(r['COLOR']), 'tags': links.get((tag_kind, identifier), []), 'splits': splits,
                'fields': self.field_values(field_kind).get(identifier, {}), 'attachments': self.attachments(field_kind).get(identifier, []),
                '_id': identifier}

    def load_trx(self):
        splits = {}
        for item in self.rows('SPLITTRANSACTIONS_V1'):
            splits.setdefault(item['TRANSID'], []).append(item)
        result = []
        links = {r['CHECKINGACCOUNTID']: r for r in self.rows('TRANSLINK_V1')}
        shares = {r['CHECKINGACCOUNTID']: r for r in self.rows('SHAREINFO_V1')}
        for r in self.rows('CHECKINGACCOUNT_V1'):
            row = self._transaction(r, 'Transaction', 'Transaction', splits, 'TransactionSplit')
            row['deleted'] = bool(text(r['DELETEDTIME']))
            row['link'] = text(links[r['TRANSID']]['LINKTYPE']) if r['TRANSID'] in links else ''
            info = shares.get(r['TRANSID'])
            row['shares'] = {'number': number(info['SHARENUMBER']), 'price': number(info['SHAREPRICE']),
                             'commission': number(info['SHARECOMMISSION'])} if info else {}
            result.append(row)
        return result

    def load_sched(self):
        splits = {}
        for item in self.rows('BUDGETSPLITTRANSACTIONS_V1'):
            splits.setdefault(item['TRANSID'], []).append(item)
        result = []
        for r in self.rows('BILLSDEPOSITS_V1'):
            row = self._transaction(r, 'RecurringTransaction', 'RecurringTransaction', splits, 'RecurringTransactionSplit')
            row.update(next_date=text(r['NEXTOCCURRENCEDATE'])[:10], repeats=number(r['REPEATS']), occurrences=number(r['NUMOCCURRENCES']))
            result.append(row)
        return result

    def load_budget_year(self):
        return [{'name': text(r['BUDGETYEARNAME'])} for r in self.rows('BUDGETYEAR_V1')]

    def load_budget(self):
        years = {r['BUDGETYEARID']: r['BUDGETYEARNAME'] for r in self.rows('BUDGETYEAR_V1')}
        paths = self.category_paths()
        return [{'year': text(years.get(r['BUDGETYEARID'], '')), 'category': text(paths.get(r['CATEGID'], '')), 'period': text(r['PERIOD']),
                 'amount': number(r['AMOUNT']), 'notes': text(r['NOTES']), 'active': number(r['ACTIVE'])} for r in self.rows('BUDGETTABLE_V1')]

    def load_asset(self):
        symbols = self.currency_symbols()
        return [{'name': text(r['ASSETNAME']), 'type': text(r['ASSETTYPE']), 'status': text(r['ASSETSTATUS']), 'date': text(r['STARTDATE'])[:10],
                 'value': number(r['VALUE']), 'change': text(r['VALUECHANGE']), 'mode': text(r['VALUECHANGEMODE']),
                 'rate': number(r['VALUECHANGERATE']), 'notes': text(r['NOTES']), 'currency': text(symbols.get(r['CURRENCYID'], ''))}
                for r in self.rows('ASSETS_V1')]

    def load_stock(self):
        accounts = self.account_names()
        return [{'name': text(r['STOCKNAME']), 'symbol': text(r['SYMBOL']), 'account': text(accounts.get(r['HELDAT'], '')),
                 'date': text(r['PURCHASEDATE'])[:10], 'shares': number(r['NUMSHARES']), 'price': number(r['PURCHASEPRICE']),
                 'current': number(r['CURRENTPRICE']), 'value': number(r['VALUE']), 'commission': number(r['COMMISSION']),
                 'notes': text(r['NOTES'])} for r in self.rows('STOCK_V1')]

    def load_stock_history(self):
        return [{'symbol': text(r['SYMBOL']), 'date': text(r['DATE'])[:10], 'value': number(r['VALUE']), 'kind': number(r['UPDTYPE'])}
                for r in self.rows('STOCKHISTORY_V1')]

    def load_field(self):
        result = []
        for record in self.rows('CUSTOMFIELD_V1'):
            properties = json.loads(record['PROPERTIES'] or '{}')
            result.append({'description': text(record['DESCRIPTION']), 'kind': text(record['REFTYPE']), 'type': text(record['TYPE']),
                           'tooltip': properties.get('Tooltip', ''), 'default': properties.get('Default', ''),
                           'regex': properties.get('RegEx', ''), 'choices': properties.get('Choice', []),
                           'scale': properties.get('DigitScale', 0), 'column': properties.get('UDFC', ''),
                           'autocomplete': properties.get('Autocomplete', False)})
        return result

    def load_attachment(self):
        return [{'kind': text(r['REFTYPE']), 'description': text(r['DESCRIPTION']), 'file': text(r['FILENAME'])} for r in self.rows('ATTACHMENT_V1')]

    def schema_version(self):
        return self.db.execute('PRAGMA user_version').fetchone()[0]

    def tables(self):
        return sorted(r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))


def matches(row, wanted):
    return all(row.get(key) == value for key, value in wanted.items())
