"""Independent validation of the first exported document, before any reimport."""
import csv
import gzip
import io
import struct
import xml.etree.ElementTree as ET
import zipfile


def local(node):return node.tag.rsplit('}',1)[-1]


def validate(raw,kind):
    """Reject a different format regardless of what the candidate's reader claims."""
    assert raw,'exported document is empty'
    if kind in ('native','xml'):
        assert raw.startswith(b'\x1f\x8b')==(kind=='native'),'native compression does not match requested format'
        data=gzip.decompress(raw) if kind=='native' else raw
        root=ET.fromstring(data)
        assert root.tag=='{http://www.gnumeric.org/v10.dtd}Workbook','not a native Gnumeric workbook'
        sheets=[n for n in root.iter() if local(n)=='Sheet']
        assert sheets and any(local(n)=='Cells' and len(n)>0 for n in root.iter()),'native export has no cell table'
        return
    if kind in ('xlsx','xlsx2','ods','ods-strict'):
        assert raw.startswith(b'PK\x03\x04'),'requested office format is not a ZIP package'
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            names=set(package.namelist());assert package.testzip() is None,'office package CRC mismatch'
            if kind.startswith('xlsx'):
                assert {'[Content_Types].xml','_rels/.rels','xl/workbook.xml','xl/styles.xml'}<=names,'not an XLSX package'
                root=ET.fromstring(package.read('xl/workbook.xml'))
                assert local(root)=='workbook' and any(local(n)=='sheet' for n in root.iter()),'XLSX workbook has no sheets'
                worksheets=[n for n in names if n.startswith('xl/worksheets/') and n.endswith('.xml')]
                assert worksheets and any(local(n)=='c' for n in ET.fromstring(package.read(sorted(worksheets)[0])).iter()),'XLSX worksheet has no cells'
                styles=ET.fromstring(package.read('xl/styles.xml'))
                # The fixture carries a real start/left border. The 2006 schema
                # uses left/right; the 2008 schema supports start/end semantics.
                expected='left' if kind=='xlsx' else 'start'
                assert any(local(n)==expected and n.get('style')=='thin' for n in styles.iter()),'XLSX edition lost the requested border semantics'
            else:
                assert {'mimetype','content.xml','META-INF/manifest.xml'}<=names,'not an ODS package'
                assert package.read('mimetype').strip()==b'application/vnd.oasis.opendocument.spreadsheet','wrong office MIME type'
                root=ET.fromstring(package.read('content.xml'))
                assert root.tag=='{urn:oasis:names:tc:opendocument:xmlns:office:1.0}document-content','wrong ODS document root'
                assert any(local(n)=='spreadsheet' for n in root.iter()) and any(local(n)=='table-cell' for n in root.iter()),'ODS spreadsheet content missing'
                manifest=ET.fromstring(package.read('META-INF/manifest.xml'))
                assert local(manifest)=='manifest','ODS manifest missing'
        return
    if kind in ('xls','xls95','xls-dual'):
        assert raw.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),'XLS is not an OLE compound document'
        import xlrd
        from xlrd.compdoc import CompDoc
        document=CompDoc(raw,logfile=io.StringIO())
        required={'xls':['Workbook'],'xls95':['Book'],'xls-dual':['Book','Workbook']}[kind]
        for name in required:
            stream=document.get_named_stream(name)
            assert stream is not None and len(stream)>=8,'requested BIFF stream is absent: '+name
            record,size,version,substream=struct.unpack_from('<HHHH',stream)
            assert record==0x0809 and size>=4 and substream==5,'invalid BIFF workbook header'
            assert version==(0x0600 if name=='Workbook' else 0x0500),'wrong BIFF generation'
        book=xlrd.open_workbook(file_contents=raw)
        assert book.nsheets and book.sheet_by_index(0).nrows>=4,'XLS cell table is empty'
        return
    assert not raw.startswith((b'PK',b'\xd0\xcf',b'\x1f\x8b')),'binary workbook supplied for a text format'
    text=raw.decode('utf-8-sig')
    assert '\x00' not in text,'binary data supplied for a text format'
    lines=text.splitlines()
    if kind=='sylk':
        assert lines and lines[0].startswith('ID;') and lines[-1]=='E','invalid SYLK framing'
        assert any(line.startswith('C;') and ';K' in line for line in lines),'SYLK has no typed cells'
    elif kind=='dif':
        for marker in ('TABLE','VECTORS','TUPLES','DATA','BOT','EOD'):assert marker in lines,'missing DIF structural record '+marker
    elif kind=='csv':
        rows=list(csv.reader(io.StringIO(text),strict=True))
        assert len(rows)>=4 and rows[0][:3]==['Kind','Value','Calculated'],'CSV does not contain the requested table'
    else:raise AssertionError('unknown independent document format '+kind)


def first_values(raw,kind):
    """A direct cell reader for first outputs with portable cached scalar values."""
    import checks
    from openpyxl.utils import get_column_letter
    if kind in ('xlsx','xlsx2'):
        book=checks.workbook(raw,values_only=True);sheet=book.worksheets[0]
        return {c.coordinate:checks.cell_value(book,sheet.title,c.coordinate) for row in sheet for c in row if c.value is not None}
    if kind in ('xls','xls95','xls-dual'):
        import xlrd
        book=xlrd.open_workbook(file_contents=raw);sheet=book.sheet_by_index(0);result={}
        for r in range(sheet.nrows):
            for c in range(sheet.ncols):
                cell=sheet.cell(r,c)
                if cell.ctype in (xlrd.XL_CELL_EMPTY,xlrd.XL_CELL_BLANK):continue
                value=bool(cell.value) if cell.ctype==xlrd.XL_CELL_BOOLEAN else cell.value
                if cell.ctype==xlrd.XL_CELL_ERROR:result[get_column_letter(c+1)+str(r+1)]={'type':'error','value':xlrd.error_text_from_code[cell.value]}
                else:result[get_column_letter(c+1)+str(r+1)]=checks.number(value)
        return result
    if kind in ('ods','ods-strict'):
        ns={'table':'urn:oasis:names:tc:opendocument:xmlns:table:1.0','office':'urn:oasis:names:tc:opendocument:xmlns:office:1.0','text':'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
        with zipfile.ZipFile(io.BytesIO(raw)) as z:root=ET.fromstring(z.read('content.xml'))
        sheet=root.find('.//table:table',ns);assert sheet is not None
        result={};row=1
        def paragraph(node):
            text=node.text or ''
            for part in node:
                name=local(part)
                if name=='s':text+=' '*int(part.get('{'+ns['text']+'}c','1'))
                elif name=='tab':text+='\t'
                elif name=='line-break':text+='\n'
                else:text+=paragraph(part)
                text+=part.tail or ''
            return text
        for tr in sheet.findall('table:table-row',ns):
            repeat=int(tr.get('{'+ns['table']+'}number-rows-repeated','1'));col=1
            for cell in tr:
                copies=int(cell.get('{'+ns['table']+'}number-columns-repeated','1'));typ=cell.get('{'+ns['office']+'}value-type')
                if typ:
                    if typ in ('float','percentage','currency'):value=checks.number(float(cell.get('{'+ns['office']+'}value')))
                    elif typ=='boolean':value=checks.number(cell.get('{'+ns['office']+'}boolean-value')=='true')
                    else:value=checks.number('\n'.join(paragraph(n) for n in cell.findall('text:p',ns)))
                    for rr in range(row,min(row+repeat,100)):
                        for cc in range(col,min(col+copies,100)):result[get_column_letter(cc)+str(rr)]=value
                col+=copies
            row+=repeat
            if row>100:break
        return result
    return None


def formula_cells(raw,kind):
    """Identify actual formula records in the first worksheet, independent of ssconvert."""
    from openpyxl.utils import get_column_letter
    result=set()
    if kind in ('native','xml'):
        root=ET.fromstring(gzip.decompress(raw) if kind=='native' else raw)
        sheet=next(n for n in root.iter() if local(n)=='Sheet')
        for cell in sheet.iter():
            if local(cell)=='Cell' and ((cell.text or '').startswith('=') or cell.get('ExprID')):
                result.add(get_column_letter(int(cell.get('Col'))+1)+str(int(cell.get('Row'))+1))
    elif kind in ('xlsx','xlsx2'):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        result={c.get('r') for c in root.iter() if local(c)=='c' and any(local(n)=='f' for n in c)}
    elif kind in ('ods','ods-strict'):
        table='urn:oasis:names:tc:opendocument:xmlns:table:1.0'
        with zipfile.ZipFile(io.BytesIO(raw)) as z:root=ET.fromstring(z.read('content.xml'))
        sheet=next(n for n in root.iter() if n.tag=='{'+table+'}table');row=1
        for tr in sheet.findall('{'+table+'}table-row'):
            col=1
            for cell in tr:
                if cell.get('{'+table+'}formula'):result.add(get_column_letter(col)+str(row))
                col+=int(cell.get('{'+table+'}number-columns-repeated','1'))
            row+=int(tr.get('{'+table+'}number-rows-repeated','1'))
    elif kind in ('xls','xls95','xls-dual'):
        from xlrd.compdoc import CompDoc
        doc=CompDoc(raw,logfile=io.StringIO());stream=doc.get_named_stream('Book' if kind=='xls95' else 'Workbook')
        offset=0;start=None
        while offset+4<=len(stream):
            code,size=struct.unpack_from('<HH',stream,offset)
            if code==0x0085:
                start=struct.unpack_from('<I',stream,offset+4)[0];break
            offset+=4+size
        assert start is not None,'BIFF worksheet offset is missing'
        offset=start
        while offset+4<=len(stream):
            code,size=struct.unpack_from('<HH',stream,offset)
            if code==0x000A:break
            if code==0x0006 and size>=6:
                row,col=struct.unpack_from('<HH',stream,offset+4);result.add(get_column_letter(col+1)+str(row+1))
            offset+=4+size
    else:raise AssertionError('format has no formula reader '+kind)
    return result
