"""Small financial interchange documents, authored independently of the product."""
import csv
import io


def csv_bytes(rows, delimiter=','):
    stream=io.StringIO(newline='')
    writer=csv.writer(stream,delimiter=delimiter,lineterminator='\n')
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


BASIC_FIELDS=['Date','Payee','Amount','Category','Number','Notes']
CSV_CASES={
    'bank.csv':(BASIC_FIELDS,[
        ['2026-06-10','Cafe Luna','-7.25','Food:Dining out','C-1','Imported coffee'],
        ['2026-06-11','Employer','125.5','Income:Salary','C-2','Imported income'],
        ['2026-06-12','Marché Nord','-19.95','Food:Groceries','C-3','Apples, pears and café'],
    ],','),
    'euro.csv':(BASIC_FIELDS,[
        ['17.06.2026','Cafe Luna','12,34','Food:Dining out','E-1','European purchase'],
        ['18.06.2026','Employer','-250,50','Income:Salary','E-2','European refund'],
        ['Footer','not a transaction','','','',''],
    ],';'),
    'partial.csv':(BASIC_FIELDS,[
        ['2026-06-10','Cafe Luna','-8.5','Food:Dining out','P-1','Valid partial import'],
        ['bad-date','Cafe Luna','-12','Food:Dining out','P-2','Invalid date import'],
        ['2026-06-12','Grocer','not-money','Food:Groceries','P-3','Invalid amount import'],
    ],','),
}


def document(name):
    if name == 'receipt.txt':
        return b'Groceries receipt\nTotal: 212.40\n'
    if name in CSV_CASES:
        header,rows,delimiter=CSV_CASES[name]
        return csv_bytes([header]+rows,delimiter)
    if name=='bank.qif':
        return b'''!Type:Bank
D2026-06-10
T-32.75
PCafe Luna
LFood:Dining out
NQ-1
MQIF dinner
^
D2026-06-11
T450.25
PEmployer
LIncome:Salary
NQ-2
MQIF bonus
CR
^
D2026-06-12
T-60.50
PGrocer
NQ-3
MQIF split shop
SFood:Groceries
$-40.25
Efruit
SHomeneeds:Furnishing
$-20.25
Evase
^
'''
    raise KeyError(name)

OFX = b'''OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20260615120000<LANGUAGE>ENG</SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS><STMTRS><CURDEF>USD
<BANKACCTFROM><BANKID>1001<ACCTID>CHK-001<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20260601000000<DTEND>20260615000000
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260610120000<TRNAMT>-28.75<FITID>OFX-COFFEE-1<NAME>Cafe Luna<MEMO>OFX coffee</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260611120000<TRNAMT>250.50<FITID>OFX-SALARY-2<NAME>Employer<MEMO>OFX bonus</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>1000.00<DTASOF>20260615120000</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>'''

_doc = document

def document(name):
    return OFX if name=='bank.ofx' else _doc(name)

# The product's OFX importer accepts XML-style closed leaf elements.
import re as _re
OFX = _re.sub(rb'<(CODE|SEVERITY|DTSERVER|LANGUAGE|TRNUID|CURDEF|BANKID|ACCTID|ACCTTYPE|DTSTART|DTEND|TRNTYPE|DTPOSTED|TRNAMT|FITID|NAME|MEMO|BALAMT|DTASOF)>([^<]*)',
              lambda m: b'<' + m[1] + b'>' + m[2].strip() + b'</' + m[1] + b'>', OFX)

OFX = OFX[OFX.index(b"<OFX>"):].replace(b"><", b">\n<")
OFX = _re.sub(rb'</(?:CODE|SEVERITY|DTSERVER|LANGUAGE|TRNUID|CURDEF|BANKID|ACCTID|ACCTTYPE|DTSTART|DTEND|TRNTYPE|DTPOSTED|TRNAMT|FITID|NAME|MEMO|BALAMT|DTASOF)>', b'', OFX)


MAPPED_FIELDS=['Notes','Date','Payee','Withdrawal','Deposit','Category','Number','Tags']

def mapped_rows(batch):
    return [
        [f'Mapped café {batch}','2026-06-10','Cafe Luna','7.125','','Food:Dining out',f'M{batch}-1','home work'],
        [f'Mapped salary {batch}','2026-06-11','Employer','','250.50','Income:Salary',f'M{batch}-2','work'],
        [f'Mapped zero {batch}','2026-06-12','Grocer','0','','Food:Groceries',f'M{batch}-3',''],
    ]

_previous_document=document

def document(name):
    if name.startswith('mapped-'):
        batch=name.split('-')[1].split('.')[0]
        rows=[MAPPED_FIELDS]+mapped_rows(batch)
        if name.endswith('.csv'):
            return csv_bytes(rows)
        from xml.sax.saxutils import escape
        content=''.join('<Row>'+''.join('<Cell><Data ss:Type="String">'+escape(str(c))+'</Data></Cell>' for c in r)+'</Row>' for r in rows)
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
                '<Worksheet ss:Name="Activity"><Table>'+content+'</Table></Worksheet>'
                '<Worksheet ss:Name="Ignored"><Table><Row><Cell><Data ss:Type="String">Not transactions</Data></Cell></Row></Table></Worksheet>'
                '</Workbook>').encode('utf-8')
    return _previous_document(name)
