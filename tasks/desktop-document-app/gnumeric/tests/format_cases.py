"""Public file-format round trips, exporter options and native command-line tools."""
import io
import json
import re
import zipfile
from collections import defaultdict
import checks
import fixtures

FORMAT_TARGETS=[
 ('native','Gnumeric_XmlIO:sax','gnumeric',True),('xml','Gnumeric_XmlIO:sax:0','xml',True),
 ('xlsx','Gnumeric_Excel:xlsx','xlsx',True),('xlsx2','Gnumeric_Excel:xlsx2','xlsx',True),
 ('ods','Gnumeric_OpenCalc:odf','ods',True),('ods-strict','Gnumeric_OpenCalc:openoffice','ods',True),
 ('xls','Gnumeric_Excel:excel_biff8','xls',True),('xls95','Gnumeric_Excel:excel_biff7','xls',True),
 ('xls-dual','Gnumeric_Excel:excel_dsf','xls',True),('sylk','Gnumeric_sylk:sylk','slk',False),
 ('dif','Gnumeric_dif:dif','dif',False),('csv','Gnumeric_stf:stf_csv','csv',False),
 ('html','Gnumeric_html:html40','html',False),('xhtml','Gnumeric_html:xhtml','html',False),
]
DATA={
 'A1':'Kind','B1':'Value','C1':'Calculated',
 'A2':'Integer','B2':37,'C2':'=B2*3',
 'A3':'Negative','B3':-12.5,'C3':'=ABS(B3)',
 'A4':'Fraction','B4':0.125,'C4':'=B4*100',
 'A5':'Unicode','B5':'café 東京 Δ',
 'A6':'Comma','B6':'one,two',
 'A7':'Quote','B7':'She said "yes"',
 'A8':'Newline','B8':'line one\nline two',
 'A9':'Leading space','B9':'  padded  ',
 'A10':'Leading zeros','B10':'00123',
 'A11':'Boolean','B11':True,
 'A12':'Ampersand','B12':'A&B <C>',
 'A13':'Scientific','B13':1.25e8,
 'A14':'Small number','B14':0.0003125,
 'A15':'Literal equals','B15':'=SUM(1,2)',
}
VALUE_CELLS=['B2','B3','B4','B5','B6','B7','B8','B9','B10','B11','B12','B13','B14','B15','C2','C3','C4']
STYLE_CHECKS=[('A1','bold'),('B1','italic'),('C1','underline'),('A2','font_size'),('A3','font_color'),
              ('A4','fill'),('A5','horizontal'),('A6','vertical'),('B8','wrap'),('B9','indent'),
              ('B4','number_format'),('B13','number_format'),('B14','number_format'),('A7','border'),
              ('A8','rotation'),('B2','locked')]


def input_book():
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment,Border,Side,Protection
    from openpyxl.workbook.defined_name import DefinedName
    b=Workbook();s=b.active;s.title='Data'
    for a,v in DATA.items():s[a]=v
    s['B15'].data_type='s'
    s['A1'].font=Font(bold=True);s['B1'].font=Font(italic=True);s['C1'].font=Font(underline='single')
    s['A2'].font=Font(size=18);s['A3'].font=Font(color='FFAA1122');s['A4'].fill=PatternFill('solid',fgColor='FFFFCC33')
    s['A5'].alignment=Alignment(horizontal='center');s['A6'].alignment=Alignment(vertical='top')
    s['B8'].alignment=Alignment(wrap_text=True);s['B9'].alignment=Alignment(indent=2)
    s['B4'].number_format='0.00%';s['B13'].number_format='0.00E+00';s['B14'].number_format='0.0000000'
    s['A7'].border=Border(bottom=Side(style='thin',color='FF223344'),left=Side(style='thin',color='FF223344'))
    s['A8'].alignment=Alignment(textRotation=45);s['B2'].protection=Protection(locked=False)
    s.column_dimensions['A'].width=21;s.column_dimensions['B'].width=25;s.row_dimensions[8].height=36
    s.merge_cells('E1:G1');s['E1']='Merged title';s.freeze_panes='C2'
    other=b.create_sheet('Données');other['A1']='Second sheet';other['B2']=19;other['C2']='=Data!B2+B2'
    b.defined_names.add(DefinedName('NamedNumber',attr_text="'Data'!$B$2"))
    s['E3']='=NamedNumber*2'
    import datetime
    b.properties.created=b.properties.modified=datetime.datetime(2024,1,1)
    buffer=io.BytesIO();b.save(buffer)
    canonical=io.BytesIO()
    with zipfile.ZipFile(buffer) as src, zipfile.ZipFile(canonical,'w',zipfile.ZIP_DEFLATED) as dst:
        for n in sorted(src.namelist()):
            info=zipfile.ZipInfo(n,date_time=(2024,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            dst.writestr(info,src.read(n))
    return canonical.getvalue()


def describe_style(cell,aspect):
    def color(c):
        if c is None:return None
        if c.type=='rgb':return str(c.rgb)[-6:].upper()
        return {'type':c.type,'value':str(c.index)}
    if aspect=='bold':return bool(cell.font.bold)
    if aspect=='italic':return bool(cell.font.italic)
    if aspect=='underline':return cell.font.underline or None
    if aspect=='font_size':return float(cell.font.sz or 0)
    if aspect=='font_color':return color(cell.font.color)
    if aspect=='fill':return [cell.fill.patternType,color(cell.fill.fgColor)]
    if aspect=='horizontal':return cell.alignment.horizontal or 'general'
    if aspect=='vertical':return cell.alignment.vertical or 'bottom'
    if aspect=='wrap':return bool(cell.alignment.wrap_text)
    if aspect=='indent':return int(cell.alignment.indent or 0)
    if aspect=='rotation':return int(cell.alignment.textRotation or 0)
    if aspect=='number_format':return cell.number_format
    if aspect=='border':return [cell.border.bottom.style,color(cell.border.bottom.color)]
    if aspect=='locked':return bool(cell.protection.locked)
    raise ValueError(aspect)


def build():
    out=[]
    wid='program-format-roundtrips';cps=[]
    for short,exporter,ext,rich in FORMAT_TARGETS:
        points=[]
        for address in VALUE_CELLS:
            points.append({'id':f'{wid}/{short}/value-{address.lower()}','channel':'backend','method':'program',
              'requirement':f'{short} conversion preserves its observable handling of {DATA.get("A"+re.sub("[A-Z]", "", address),address)}.',
              'check':{'kind':'roundtrip-value','format':short,'cell':address}})
        if rich:
            points.append({'id':f'{wid}/{short}/formula-records','channel':'backend','method':'program',
                           'requirement':'The first '+short+' document contains actual formulas in C2:C4.',
                           'check':{'kind':'roundtrip-formulas','format':short}})
            for sheet,cell,value in [('Data','C2',15),('Data','C3',9),('Data','C4',20),('Data','E3',10),('Données','C2',24)]:
                points.append({'id':f'{wid}/{short}/updated-{sheet.casefold()}-{cell.casefold()}','channel':'backend','method':'program',
                               'requirement':'Changing source values after '+short+' export recalculates '+sheet+'!'+cell+'.',
                               'check':{'kind':'roundtrip-updated','format':short,'sheet':sheet,'cell':cell,'expected':checks.number(value)}})
            for address,aspect in STYLE_CHECKS:
                points.append({'id':f'{wid}/{short}/style-{address.lower()}-{aspect}','channel':'backend','method':'program',
                  'requirement':f'{short} round trip preserves {address} {aspect}.',
                  'check':{'kind':'roundtrip-style','format':short,'cell':address,'aspect':aspect}})
            for aspect in ('sheet-names','second-sheet-value','cross-sheet-formula','merged-cells','column-width','row-height','named-formula'):
                points.append({'id':f'{wid}/{short}/{aspect}','channel':'backend','method':'program',
                  'requirement':f'{short} round trip retains {aspect}.','check':{'kind':'roundtrip-structure','format':short,'aspect':aspect}})
        cps.append({'id':short,'goal':f'Convert the supplied workbook to {short} and reopen that real exported document.',
                    'depends_on':['setup:input'],'assertions':points})
    out.append({'id':wid,'feature':'file-formats','execution':'program','initial_state':'Fresh application and exchange files.',
                'setup':[{'id':'input','op':'format-input'}],'inputs':{},'checkpoints':cps})
    wid='program-text-export';cps=[]
    opts=[('raw','format=raw'),('preserve','format=preserve'),
          ('semicolon','separator=;'),('tab','separator=\t'),('pipe','separator=|'),
          ('quote-always','quoting-mode=always'),('quote-never','quoting-mode=never'),
          ('crlf','eol=windows'),('cr','eol=mac'),('formulas','formulas=true'),
          ('latin1','charset=ISO-8859-1'),('sheet-selection','sheet=Données')]
    for id,option in opts:
        cps.append({'id':id,'goal':'Export with '+option,'depends_on':['setup:input'],
          'assertions':[{'id':f'{wid}/{id}/text','channel':'backend','method':'program','requirement':'Native text export option '+option,
                         'check':{'kind':'text-export','option':option}}]})
    out.append({'id':wid,'feature':'text-formats','execution':'program','initial_state':'Fresh application and exchange files.',
                'setup':[{'id':'input','op':'format-input'}],'inputs':{},'checkpoints':cps})
    return out


def setup(ctx,item):
    checks.upload(ctx,'format-input.xlsx',input_book())


def output(ctx,short):
    key=('roundtrip',short)
    if key not in ctx.state:
        try:
            _,exporter,ext,rich=next(x for x in FORMAT_TARGETS if x[0]==short)
            filename='converted-'+short+'.'+ext;final='reopened-'+short+'.xlsx'
            checks.convert(ctx,'inbox/format-input.xlsx','outbox/'+filename,['--recalc','--export-type',exporter])
            import document_formats
            first=checks.download(ctx,filename)
            document_formats.validate(first,short)
            ctx.state[('first-document',short)]=(filename,first)
            ctx.state[('first-values',short)]=document_formats.first_values(first,short)
            checks.convert(ctx,'outbox/'+filename,'outbox/'+final,['--recalc'])
            raw=checks.download(ctx,final)
            data=checks.workbook(raw);formula=checks.workbook(raw,formulas=True)
            assert len(data.sheetnames)>=1 and data.worksheets[0]['B2'].value is not None,'round trip produced an empty workbook'
            ctx.state[key]=((data,formula),None)
        except Exception as e:ctx.state[key]=(None,e)
    books,error=ctx.state[key]
    if error is not None:raise error
    return books


def evaluate(ctx,cp,assertion):
    c=assertion['check'];kind=c['kind']
    if kind=='text-export':
        filename='text-'+cp['id']+'.csv'
        checks.convert(ctx,'inbox/format-input.xlsx','outbox/'+filename,
                       ['--recalc','--export-type','Gnumeric_stf:stf_assistant','--export-options',c['option']])
        raw=checks.download(ctx,filename)
        assert raw,'text export is empty'
        # Byte representation is itself the behavior for delimiter, quoting,
        # encoding and line-ending options; no timestamps enter this fixture.
        return {'bytes':list(raw)}
    if c['format'] in ('html','xhtml'):
        short=c['format'];cache=('html-output',short)
        if cache not in ctx.state:
            from lxml import html
            _,exporter,ext,rich=next(x for x in FORMAT_TARGETS if x[0]==short)
            filename='converted-'+short+'.html'
            checks.convert(ctx,'inbox/format-input.xlsx','outbox/'+filename,['--recalc','--export-type',exporter])
            root=html.fromstring(checks.download(ctx,filename))
            tables=root.xpath('//table')
            assert tables,'export has no table'
            grid={}
            for row,tr in enumerate(tables[0].xpath('./tr | ./tbody/tr'),1):
                col=1
                for td in tr.xpath('./td | ./th'):
                    for br in td.xpath('.//br'):
                        br.tail='\n'+(br.tail or '').lstrip('\n')
                    text=''.join(td.itertext()).replace('−','-').strip()
                    from openpyxl.utils import get_column_letter
                    grid[get_column_letter(col)+str(row)]=text
                    col+=int(td.get('colspan','1'))
            assert grid.get('B2')=='37','HTML export did not retain the input table'
            ctx.state[cache]=grid
        assert c['cell'] in ctx.state[cache],'HTML export is missing a cell'
        return {'text':ctx.state[cache][c['cell']]}
    data,formula=output(ctx,c['format']);sheet=data.worksheets[0]
    if kind=='roundtrip-formulas':
        import document_formats
        cells=document_formats.formula_cells(ctx.state[('first-document',c['format'])][1],c['format'])
        assert {'C2','C3','C4'}<=cells,'first exported document replaced formulas with scalar results'
        return {'formula_cells':['C2','C3','C4']}
    if kind=='roundtrip-updated':
        key=('updated-first',c['format'])
        if key not in ctx.state:
            first,_=ctx.state[('first-document',c['format'])];target='updated-'+c['format']+'.xlsx'
            checks.convert(ctx,'outbox/'+first,'outbox/'+target,['--set','B2=5','--set','B3=-9','--set','B4=0.2','--recalc'])
            ctx.state[key]=checks.workbook(checks.download(ctx,target),values_only=True)
        value=checks.cell_value(ctx.state[key],c['sheet'],c['cell'])
        if ctx.record:checks.compare(value,c['expected'])
        return value
    if kind=='roundtrip-value':
        direct=ctx.state.get(('first-values',c['format']))
        if direct is not None:
            assert c['cell'] in direct,'first exported document is missing the requested cell'
            return direct[c['cell']]
        return checks.cell_value(data,sheet.title,c['cell'])
    if kind=='roundtrip-style':return {'value':describe_style(sheet[c['cell']],c['aspect'])}
    aspect=c['aspect']
    if aspect=='sheet-names':return {'names':data.sheetnames}
    if aspect=='second-sheet-value':return checks.cell_value(data,data.sheetnames[1],'B2')
    if aspect=='cross-sheet-formula':return checks.cell_value(data,data.sheetnames[1],'C2')
    if aspect=='named-formula':return checks.cell_value(data,data.sheetnames[0],'E3')
    if aspect=='merged-cells':return {'ranges':sorted(str(r) for r in sheet.merged_cells.ranges)}
    if aspect=='column-width':return {'width':round(sheet.column_dimensions['B'].width,1)}
    if aspect=='row-height':return {'height':round(sheet.row_dimensions[8].height or 0,1)}
    raise ValueError(aspect)
