"""Semantic projections of actual user documents obtained through the runtime."""
import base64
import datetime
import gzip
import io
import math
import re
import time
import warnings
import xml.etree.ElementTree as ET
import zipfile


def upload(ctx,name,data,area='inbox',read_only=False):
    return ctx.broker.call({'op':'upload','filename':name,'area':area,'base64':base64.b64encode(data).decode(),'read_only':read_only})


def download(ctx,name,area='outbox'):
    return base64.b64decode(ctx.broker.call({'op':'download','filename':name,'area':area})['body_base64'],validate=True)


def command(ctx,args,tool='ssconvert'):
    return ctx.broker.call({'op':'cli','tool':tool,'args':args})


def convert(ctx,source,target,options=()):
    reply=command(ctx,[*options,source,target])
    assert reply.get('exit_code')==0 and not reply.get('timed_out'), 'conversion failed: '+str(reply.get('stderr',''))[-600:]
    return reply


def number(value):
    if isinstance(value,(datetime.datetime,datetime.date,datetime.time)):
        return {'type':'datetime','value':value.isoformat()}
    if isinstance(value,datetime.timedelta):return {'type':'duration','value':value.total_seconds()}
    if isinstance(value,bool):return {'type':'boolean','value':value}
    if isinstance(value,(int,float)):
        assert math.isfinite(value),'non-finite spreadsheet result'
        return {'type':'number','value':value}
    if value is None:return {'type':'blank','value':None}
    return {'type':'text','value':str(value)}


def table_token(text):
    """Canonicalize numeric display forms without coercing authored text."""
    normalized=text.replace('−','-')
    if re.fullmatch(r'[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?',normalized):
        return number(float(normalized))
    return number(text)


COMPLEX_RESULTS={'COMPLEX','IMCONJUGATE','IMNEG','IMCOS','IMSIN','IMTAN','IMCOT','IMSEC','IMCSC',
                 'IMCOSH','IMSINH','IMTANH','IMCOTH','IMSECH','IMCSCH','IMEXP','IMLN','IMLOG2','IMLOG10',
                 'IMPOWER','IMSQRT','IMSUM','IMSUB','IMPRODUCT','IMDIV','IMARCCOS','IMARCSIN','IMARCTAN',
                 'IMARCCOT','IMARCSEC','IMARCCSC','IMARCCOSH','IMARCSINH','IMARCTANH','IMARCCOTH',
                 'IMARCSECH','IMARCCSCH','IMFACT','IMGAMMA','IMIGAMMA'}


def mathematical_value(value,formula):
    """Only complex-valued functions receive component-wise numerical comparison."""
    match=re.match(r'=([A-Za-z0-9_.]+)\(',formula)
    if not match or match[1].upper() not in COMPLEX_RESULTS or value['type']=='error':return value
    assert value['type'] in ('text','number'),'complex function did not return a number'
    raw=str(value['value']).strip().replace('−','-')
    numeric=r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
    pattern=rf'[+-]?(?:(?:{numeric})(?:[+-](?:{numeric})?[ij])?|(?:{numeric})?[ij])'
    assert re.fullmatch(pattern,raw),'invalid complex notation'
    try:z=complex(raw.replace('i','j'))
    except ValueError:raise AssertionError('invalid complex notation') from None
    assert math.isfinite(z.real) and math.isfinite(z.imag),'non-finite complex value'
    # A unit has meaning only when an imaginary component is present.
    return {'type':'complex','real':z.real,'imag':z.imag,'unit':raw[-1] if z.imag!=0 else None}


def workbook(data,formulas=False,values_only=False):
    from openpyxl import load_workbook
    assert data.startswith(b'PK'), 'output is not an XLSX document'
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        return load_workbook(io.BytesIO(data),data_only=not formulas,read_only=values_only)


def cell_value(book,sheet,cell):
    assert sheet in book.sheetnames,'missing sheet '+sheet
    c=book[sheet][cell]
    if c.value is None and c.data_type in ('s','str','inlineStr'):return {'type':'text','value':''}
    if c.data_type=='e':return {'type':'error','value':str(c.value)}
    return number(c.value)


def compare(actual,expected):
    if isinstance(expected,dict):
        assert isinstance(actual,dict),'expected an object'
        for k,v in expected.items():
            assert k in actual,'missing field '+k
            compare(actual[k],v)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected),'list length differs'
        for a,e in zip(actual,expected):compare(a,e)
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        assert isinstance(actual,(float,int)) and not isinstance(actual,bool) and math.isfinite(actual),'expected a finite number'
        assert math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-10),f'numeric value differs: {actual} vs {expected}'
    else:
        assert type(actual) is type(expected) and actual==expected,f'value differs: {actual!r} vs {expected!r}'


def xml_workbook(data):
    if data.startswith(b'\x1f\x8b'):data=gzip.decompress(data)
    root=ET.fromstring(data)
    assert root.tag.rsplit('}',1)[-1]=='Workbook','output is not a Gnumeric workbook'
    return root


def local(element):return element.tag.rsplit('}',1)[-1]


def child(node,name):return next((x for x in node if local(x)==name),None)


def native_sheets(data):
    root=xml_workbook(data); sheets=child(root,'Sheets')
    assert sheets is not None,'saved workbook has no sheets'
    return {child(s,'Name').text:s for s in sheets}


def native_cell(sheet,address):
    from fixtures import position
    r,c=position(address)
    cells=child(sheet,'Cells')
    node=next((n for n in cells if n.get('Row')==str(r) and n.get('Col')==str(c)),None) if cells is not None else None
    return node


def read_gui(ctx,check):
    """Only the requested property is compared; exporter bookkeeping is ignored."""
    kind=check['kind']
    if kind=='lifecycle':
        return {'running':ctx.broker.call({'op':'status'})['running']}
    if kind=='clipboard':
        return {'text':ctx.broker.call({'op':'clipboard_text'})['text'].replace('\r\n','\n').rstrip('\n')}
    filename=check['file']
    key=('gui-file',filename,ctx.state.get('checkpoint'))
    if key not in ctx.state:
        deadline=time.monotonic()+15
        while True:
            names={f['name'] for f in ctx.broker.call({'op':'list_files','area':'outbox'})['files']}
            if filename in names:break
            assert time.monotonic()<deadline,'requested output is missing: '+filename
            time.sleep(.25)
        ctx.state[key]=download(ctx,filename)
    data=ctx.state[key]
    if kind=='chart-export':
        fmt=check['format'];prefix='graph-'+fmt+'-'
        result=command(ctx,['--export-graphs','outbox/'+filename,'outbox/'+prefix+'%n.'+fmt])
        assert result['exit_code']==0,'native graph export failed'
        names=[f['name'] for f in ctx.broker.call({'op':'list_files','area':'outbox'})['files'] if f['name'].startswith(prefix) and f['name'].endswith('.'+fmt)]
        assert len(names)==1,'graph export did not produce one chart document'
        raw=download(ctx,names[0])
        if fmt=='svg':
            root=ET.fromstring(raw);assert local(root)=='svg','graph export is not SVG'
            assert sum(local(n) in ('path','rect','circle','polygon','polyline','use','text') for n in root.iter())>=6,'SVG has no chart drawing'
        elif fmt=='png':
            from PIL import Image
            image=Image.open(io.BytesIO(raw));assert image.format=='PNG' and min(image.size)>=80,'graph PNG is invalid'
            assert len(image.convert('RGB').resize((64,64)).getcolors(4096) or [])>=3,'graph PNG is blank'
        else:
            import fitz
            pdf=fitz.open(stream=raw,filetype='pdf');assert len(pdf)==1,'chart PDF page count differs'
            assert check['title'] in pdf[0].get_text(),'chart PDF lost its authored title'
        return {'format':fmt,'nonempty_plot':True}
    if kind=='calculation-setting':
        node=child(xml_workbook(data),'Calculation')
        assert node is not None,'saved calculation settings are missing'
        return {'value':node.get(check['attribute'])}
    if kind=='metadata':
        root=xml_workbook(data)
        meta=next((n for n in root.iter() if local(n)=='meta'),None)
        assert meta is not None,'saved metadata is missing'
        fields={local(n):n.text or '' for n in meta}
        return {'fields':{name:fields.get(name) for name in check['fields']}}
    if kind in ('values','analysis-region','generated-sheets'):
        # The candidate's own converter produces the portable values projection.
        target='values-'+filename.rsplit('.',1)[0]+'.xlsx'
        projection=key+('values',)
        if projection not in ctx.state:
            convert(ctx,'outbox/'+filename,'outbox/'+target,['--recalc'])
            ctx.state[projection]=workbook(download(ctx,target),values_only=True)
        book=ctx.state[projection]
        if kind=='generated-sheets':
            return {'rows':sorted([[book[name][address].value for address in check['cells']] for name in book.sheetnames if name not in check.get('exclude',[])],key=repr)}
        if kind=='analysis-region':
            import report_semantics
            assert check['sheet'] in book.sheetnames,'analysis sheet is missing'
            output={}
            for row in book[check['sheet']][check['range']]:
                for cell in row:
                    if cell.value is not None:output[cell.coordinate]=cell_value(book,check['sheet'],cell.coordinate)
            assert sum(v['type']=='number' for v in output.values())>=check.get('min_numbers',3),'analysis report has too few numeric results'
            if check.get('no_errors'):
                assert all(v['type']!='error' for v in output.values()),'analysis report contains spreadsheet errors'
            return report_semantics.project(book[check['sheet']],check['range'],check['analysis'])
        return {'cells':{address:cell_value(book,check['sheet'],address) for address in check['cells']}}
    sheets=native_sheets(data)
    if kind=='sheets':return {'names':list(sheets)}
    assert check['sheet'] in sheets,'missing sheet '+check['sheet']
    sheet=sheets[check['sheet']]
    if kind=='literal-cells':
        nodes=[native_cell(sheet,address) for address in check['cells']]
        return {'literal':all(n is not None and n.get('ValueType') is not None and not n.get('ExprID') for n in nodes)}
    if kind=='comment':
        objects=child(sheet,'Objects')
        comment=next((n for n in objects or () if local(n)=='CellComment' and n.get('ObjectBound')==check['cell']),None)
        if comment is None:return {'present':False}
        return {'present':True,'author':comment.get('Author',''),'text':comment.get('Text','')}
    if kind=='formulas':
        values={}
        for a in check['cells']:
            n=native_cell(sheet,a)
            assert n is not None,'missing formula cell '+a
            expression=n.text or ''
            # Shared native expressions are resolved by their defining cell, with
            # relative references translated to this cell.
            if not expression and n.get('ExprID'):
                cells=child(sheet,'Cells')
                first=next((x for x in cells if x.get('ExprID')==n.get('ExprID') and (x.text or '').startswith('=')),None)
                assert first is not None,'missing shared expression definition'
                from openpyxl.formula.translate import Translator
                from openpyxl.utils import get_column_letter
                origin=get_column_letter(int(first.get('Col'))+1)+str(int(first.get('Row'))+1)
                expression=Translator(first.text,origin=origin).translate_formula(a)
            assert expression.startswith('='),'saved cell is not a formula: '+a
            values[a]=re.sub(r'\s+','',expression).casefold()
        return {'formulas':values}
    if kind=='sheet-attribute':return {'value':sheet.get(check['attribute'],check.get('default'))}
    if kind=='style':
        from fixtures import position
        r,c=position(check['cell']); merged={}; font={}
        for region in child(sheet,'Styles') or ():
            if int(region.get('startRow'))<=r<=int(region.get('endRow')) and int(region.get('startCol'))<=c<=int(region.get('endCol')):
                style=child(region,'Style')
                if style is not None:
                    merged.update(style.attrib)
                    f=child(style,'Font')
                    if f is not None:font.update(f.attrib);font['name']=f.text
        if check['property'].startswith('font:'):value=font.get(check['property'][5:])
        else:value=merged.get(check['property'])
        assert value is not None,'style property is absent'
        return {'value':value}
    if kind=='merged':
        ranges=child(sheet,'MergedRegions')
        return {'ranges':sorted(n.text for n in ranges or ())}
    if kind=='objects':
        objects=child(sheet,'Objects')
        return {'objects':sorted(local(n) for n in objects or ())}
    raise ValueError('unknown GUI artifact check '+kind)
