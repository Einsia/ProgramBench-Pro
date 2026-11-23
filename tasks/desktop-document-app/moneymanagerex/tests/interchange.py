"""Semantic financial interchange observations, independent of generated IDs."""
import csv
import io
import json
from collections import Counter

import documents


def ordered(values):
    return sorted(values, key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True))


def json_ledger(data):
    value = json.loads(documents.decode(data))
    maps = {}
    for collection in ('ACCOUNTS', 'PAYEES', 'CATEGORIES', 'TAGS'):
        records = value.get(collection, [])
        if not isinstance(records, list):
            raise AssertionError(collection + ' must be an array')
        mapping = {}
        for record in records:
            identifier, name = record.get('ID'), record.get('NAME')
            if identifier is None or not isinstance(name, str) or identifier in mapping:
                raise AssertionError('invalid or duplicate identity in ' + collection)
            mapping[identifier] = name
        maps[collection] = mapping

    def resolve(collection, identifier):
        if identifier in (None, -1, 0):
            return ''
        if identifier not in maps[collection]:
            raise AssertionError('unresolved ' + collection + ' reference')
        return maps[collection][identifier]

    def tags(record):
        return sorted({resolve('TAGS', i) for i in record.get('TAGS', [])})

    transactions = []
    for record in value['transactions']:
        parts = [{'category': resolve('CATEGORIES', r['CATEGORY_ID']), 'amount': float(r['AMOUNT']), 'tags': tags(r)}
                 for r in record.get('DIVISION', [])]
        transactions.append({
            'account': resolve('ACCOUNTS', record.get('ACCOUNTID')),
            'to_account': resolve('ACCOUNTS', record.get('TOACCOUNTID')),
            'payee': resolve('PAYEES', record.get('PAYEEID')),
            'category': resolve('CATEGORIES', record.get('CATEGID')),
            'type': record['TRANSCODE'], 'amount': float(record['TRANSAMOUNT']),
            'to_amount': float(record.get('TOTRANSAMOUNT', 0)), 'status': record.get('STATUS', ''),
            'date': record['TRANSDATE'][:10], 'time': record['TRANSDATE'][11:19],
            'number': record.get('TRANSACTIONNUMBER', ''), 'notes': record.get('NOTES', ''),
            'tags': tags(record), 'splits': ordered(parts),
        })
    accounts = [{'name': r['NAME'], 'balance': float(r['INITIAL_BALANCE']), 'type': r['TYPE'], 'currency': r['CURRENCY_SYMBOL']}
                for r in value.get('ACCOUNTS', [])]
    return {'transactions': ordered(transactions), 'accounts': ordered(accounts)}


def category_tags(value):
    category, _, suffix = value.partition('/')
    return {'category': category, 'tags': sorted({x for x in suffix.replace('|', ':').split(':') if x})}


def qif_transactions(data):
    result = []
    account = ''
    for record in documents.qif_records(data):
        if record.get('!')=='Account':
            account=record.get('N','')
            continue
        if not record.get('!','').startswith('Type:') or 'D' not in record or 'T' not in record:
            continue
        getlist = lambda key: record[key] if isinstance(record.get(key), list) else [record[key]] if key in record else []
        categories, amounts, notes = getlist('S'), getlist('$'), getlist('E')
        if len(categories) != len(amounts):
            raise AssertionError('split categories and amounts differ in length')
        parts = [dict(category_tags(c), amount=documents.to_number(a), notes=notes[i] if i < len(notes) else '')
                 for i,(c,a) in enumerate(zip(categories,amounts))]
        result.append({'account':account,'date': record['D'], 'amount': documents.to_number(record['T']), 'payee': record.get('P',''),
                       'number': record.get('N',''), 'status': record.get('C',''), 'notes': record.get('M',''),
                       **category_tags(record.get('L','')), 'splits': ordered(parts)})
    return ordered(result)


def xml_transactions(data):
    rows = documents.spreadsheet_rows(data)
    if not rows:
        raise AssertionError('XML spreadsheet has no rows')
    header = [str(v) for v in rows[0]]
    if not all(k in header for k in ('Date','Account','Payee','Amount','Notes')):
        raise AssertionError('XML spreadsheet has no transaction header')
    result=[]
    for row in rows[1:]:
        record={k:row[i] if i<len(row) else '' for i,k in enumerate(header) if k!='ID'}
        # The product writes category and subcategory in separate columns.
        if record.get('SubCategory'):
            record['Category']=str(record.get('Category',''))+':'+str(record['SubCategory'])
        record.pop('SubCategory',None)
        if 'Tags' in record:
            record['Tags']=sorted(set(str(record['Tags']).split()))
        result.append(record)
    return ordered(result)


def csv_transactions(data):
    reader=csv.DictReader(io.StringIO(documents.decode(data)))
    if not reader.fieldnames or not all(k in reader.fieldnames for k in ('Date','Account','Amount','Notes')):
        raise AssertionError('CSV has no transaction header')
    return ordered([{k:documents.cell(v or '') for k,v in r.items() if k!='ID'} for r in reader])


def observe(data, check):
    form=check['form']
    if form.startswith('semantic-json'):
        value=json_ledger(data)
        if form=='semantic-json-accounts':
            return value['accounts']
        records=value['transactions']
    elif form.startswith('semantic-qif'):
        records=qif_transactions(data)
    elif form.startswith('semantic-xml'):
        records=xml_transactions(data)
    elif form.startswith('semantic-csv'):
        records=csv_transactions(data)
    else:
        raise ValueError(form)
    if form.endswith('-count'):
        return len(records)
    if check.get('match'):
        records=[r for r in records if all(r.get(k)==v for k,v in check['match'].items())]
        if not records:
            raise AssertionError('no exported transaction matches the business key')
    if check.get('fields'):
        records=[{k:r[k] for k in check['fields']} for r in records]
    return ordered(records)
