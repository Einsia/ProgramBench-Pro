"""Independent, deterministic spreadsheet inputs in documented file formats."""
import gzip
import io
import xml.etree.ElementTree as ET

NS = 'http://www.gnumeric.org/v10.dtd'
ET.register_namespace('gnm', NS)


def tag(name):
    return '{'+NS+'}'+name


def sub(parent, name, text=None, **attributes):
    item = ET.SubElement(parent, tag(name), {k:str(v) for k,v in attributes.items()})
    if text is not None:
        item.text = str(text)
    return item


def position(address):
    import re
    m = re.fullmatch(r'([A-Z]+)([1-9][0-9]*)', address.upper())
    assert m, address
    col = 0
    for c in m[1]:
        col = col*26 + ord(c)-64
    return int(m[2])-1, col-1


def native(sheets, *, widths=72, names=None, styles=None):
    """sheets maps sheet names to A1 -> scalar/formula; generated without Gnumeric."""
    root = ET.Element(tag('Workbook'))
    sub(root,'Version',Epoch=1,Major=12,Minor=62,Full='1.12.62')
    sub(root,'Calculation',ManualRecalc=0,EnableIteration=0,MaxIterations=100,IterationTolerance=.001)
    index = sub(root,'SheetNameIndex')
    for name in sheets:
        sub(index,'SheetName',name,**{tag('Cols'):256,tag('Rows'):65536})
    if names:
        defined = sub(root,'Names')
        for name,formula in names.items():
            entry=sub(defined,'Name');sub(entry,'name',name);sub(entry,'value',formula);sub(entry,'position','A1')
    body = sub(root,'Sheets')
    for title, values in sheets.items():
        sheet=sub(body,'Sheet',DisplayFormulas=0,HideZero=0,HideGrid=0,HideColHeader=0,HideRowHeader=0,
                  Visibility='GNM_SHEET_VISIBILITY_VISIBLE')
        sub(sheet,'Name',title)
        coords=[position(a) for a in values]
        sub(sheet,'MaxCol',max([c for r,c in coords]+[0]));sub(sheet,'MaxRow',max([r for r,c in coords]+[0]))
        sub(sheet,'Zoom',1)
        stylelist=sub(sheet,'Styles')
        region=sub(stylelist,'StyleRegion',startCol=0,startRow=0,endCol=255,endRow=65535)
        style=sub(region,'Style',HAlign='GNM_HALIGN_GENERAL',VAlign='GNM_VALIGN_BOTTOM',WrapText=0,
                  ShrinkToFit=0,Rotation=0,Shade=0,Indent=0,Locked=1,Hidden=0,Fore='0:0:0',
                  Back='FFFF:FFFF:FFFF',PatternColor='0:0:0',Format='General')
        sub(style,'Font','Sans',Unit=10,Bold=0,Italic=0,Underline=0,StrikeThrough=0,Script=0)
        for address, attributes in (styles or {}).get(title,{}).items():
            r,c=position(address);region=sub(stylelist,'StyleRegion',startCol=c,startRow=r,endCol=c,endRow=r)
            sub(region,'Style',**attributes)
        sub(sheet,'Cols',DefaultSizePts=widths);sub(sheet,'Rows',DefaultSizePts=18)
        cells=sub(sheet,'Cells')
        for address,value in values.items():
            r,c=position(address)
            if value is None:
                continue
            attrs={'Row':r,'Col':c}
            if isinstance(value,bool):
                attrs['ValueType']=20;value='TRUE' if value else 'FALSE'
            elif isinstance(value,(float,int)):
                attrs['ValueType']=40
            elif not str(value).startswith('='):
                attrs['ValueType']=60
            sub(cells,'Cell',value,**attrs)
        sub(sheet,'SheetLayout',TopLeft='A1')
    sub(root,'UIData',SelectedTab=0)
    return gzip.compress(ET.tostring(root,encoding='utf-8',xml_declaration=True),mtime=0)


def table(rows):
    def letter(c):
        value = ''
        while c:
            c,mod=divmod(c-1,26); value=chr(65+mod)+value
        return value
    return {letter(c+1)+str(r+1):v for r,row in enumerate(rows) for c,v in enumerate(row) if v is not None}


LEDGER = [
    ['Product','Region','Units','Price','Revenue'],
    ['Tea','North',8,3.5,'=C2*D2'],
    ['Coffee','South',5,6,'=C3*D3'],
    ['Cocoa','North',12,4.25,'=C4*D4'],
    ['Juice','East',7,2.5,'=C5*D5'],
    ['Water','South',15,1.25,'=C6*D6'],
    ['Milk','East',10,2,'=C7*D7'],
    ['Total',None,'=SUM(C2:C7)',None,'=SUM(E2:E7)'],
]
SERIES = [['Index','Sales','Cost'],[1,12,4],[2,19,7],[3,15,6],[4,26,8],[5,23,9],[6,35,10]]
FORMULA_DATA = {
    'A1':1,'A2':2,'A3':4,'A4':8,'A5':16,'A6':-3,'A7':0,
    'B1':2,'B2':5,'B3':9,'B4':17,'B5':33,'B6':-4,'B7':3,
    'C1':'apple','C2':'banana','C3':'apricot','C4':'berry','C5':'apple',
    'D1':True,'D2':False,'D3':'text','D4':7,'D5':None,
    'E1':10,'F1':20,'G1':30,'E2':'ten','F2':'twenty','G2':'thirty',
}
DATABASE = table([['Tree','Height','Age','Yield'],['Apple',18,20,14],['Pear',12,12,10],
                  ['Cherry',13,14,9],['Apple',14,15,10],['Pear',9,8,8],['Apple',8,9,6]])
DATABASE.update({'F1':'Tree','F2':'Apple','G1':'Height','G2':'>10','I1':'Tree','I2':'Pear'})


def named(name):
    if name=='badge.png':
        from PIL import Image,ImageDraw
        image=Image.new('RGB',(160,80),'#2a6fb5');ImageDraw.Draw(image).rectangle((80,0,159,79),fill='#efb233')
        buffer=io.BytesIO();image.save(buffer,format='PNG');return buffer.getvalue()
    if name=='frequency-input.gnumeric':return native({'Sales':{**table(LEDGER),'G1':'Categories','G2':'North','G3':'South','G4':'East','G5':'West'}},widths=86)
    if name=='consolidate-input.gnumeric':return native({'Areas':{'A1':2,'B1':4,'A2':6,'B2':8,'D1':3,'E1':5,'D2':7,'E2':9}},widths=75)
    if name=='split-input.gnumeric':return native({'Text':{'A1':'Raw','A2':'"Tea;North";8;3.5','A3':'Coffee;;6','A4':'Cocoa;12;4.25'}},widths=140)
    if name=='model-table.gnumeric':return native({'Model':{'A1':2,'B1':3,'C1':'=A1*B1+5','F1':'=C1','E2':1,'E3':2,'E4':4,'J1':'=C1','K1':2,'L1':5,'J2':1,'J3':3}},widths=65)
    if name=='merge-template.gnumeric':return native({'Template':{'A1':'Invoice','A2':'Customer','B2':'name','D1':'Names','D2':'Tea','D3':'Coffee','D4':'Cocoa'}},widths=86)
    if name=='filter-input.gnumeric':return native({'Sales':{**table(LEDGER),'G1':'Region','H1':'Units','G2':'North','H2':'>8','J1':'Region','J2':'North','J3':'East'}},widths=86)
    if name=='ledger.gnumeric':return native({'Sales':table(LEDGER)},widths=86)
    if name=='series.gnumeric':return native({'Data':table(SERIES)},widths=82)
    if name=='fourier-series.gnumeric':return native({'Data':table(SERIES+[[7,18,5],[8,29,11]])},widths=82)
    if name=='contingency.gnumeric':return native({'Data':table([['Group','Yes','No'],['A',12,4],['B',19,7],['C',15,6]])},widths=82)
    if name=='normality.gnumeric':return native({'Data':table(SERIES+[[7,18,5],[8,29,11],[9,21,6],[10,32,8],[11,24,7],[12,16,5]])},widths=82)
    if name=='multi.gnumeric':return native({'North':{'A1':'North','B2':12,'B3':18,'B4':'=SUM(B2:B3)'},
                                            'South':{'A1':'South','B2':25,'B3':15,'B4':'=SUM(B2:B3)'},
                                            'Summary':{'A1':'Combined','B1':'=North!B4+South!B4'}},widths=90)
    if name=='text.gnumeric':return native({'Text':table([['Name','Note'],['Alice','Blue team'],['Bob','blue sky'],['Carla','Green team'],['Dora','Blue team']])},widths=120)
    if name=='blank.gnumeric':return native({'Sheet1':{}},widths=72)
    if name=='import.csv':return 'Name,Quantity,Price\n"Café, North",4,2.5\n"Tea ""Green""",7,3.25\n'.encode()
    if name=='import.tsv':return 'Name\tQuantity\tPrice\nTea\t4\t2.5\nCoffee\t7\t3.25\n'.encode()
    if name=='invalid.gnumeric':return b'<?xml version="1.0"?><gnm:Workbook xmlns:gnm="http://www.gnumeric.org/v10.dtd"><gnm:Sheets><broken' 
    if name=='empty.gnumeric':return b''
    raise ValueError('unknown fixture '+name)
