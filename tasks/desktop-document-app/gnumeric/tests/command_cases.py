"""Native conversion options, text search, indexing and workbook comparison."""
import io
import re
import xml.etree.ElementTree as ET
import checks
import fixtures

SEARCH_SHEETS={'Data':{'A1':'Name','B1':'Value','C1':'Formula','A2':'Alpha','A3':'alphabet','A4':'Beta alpha',
                      'A5':'café 東京','A6':'a.b','A7':'A*B','A8':'two words','B2':12,'B3':-7.5,'B4':True,
                      'C2':'=B2*3','C3':'="computed "&A2','C4':'=SQRT(81)'},
               'Other':{'A1':'Alpha again','A2':'lower alpha','B1':37,'C1':'=Data!B2+1'}}
SEARCH_OPTIONS=[([], 'Alpha'),(['--ignore-case'],'alpha'),(['--fixed-strings'],'a.b'),
                (['--fixed-strings'],'A*B'),(['--word-regexp'],'Alpha'),(['--word-regexp','--ignore-case'],'alpha'),
                (['--count'],'Alpha'),(['--count','--ignore-case'],'alpha'),(['--print-locus'],'Alpha'),
                (['--print-type'],'Alpha'),(['--print-locus','--print-type'],'Alpha'),
                (['--with-filename'],'Alpha'),(['--without-filename'],'Alpha'),
                (['--files-with-matches'],'Alpha'),(['--files-without-matches'],'missing'),
                (['--quiet'],'Alpha'),(['--quiet'],'missing'),(['--invert-match'],'Alpha'),
                (['--ignore-case','--invert-match','--count'],'alpha'),
                (['--search-results','--recalc'],'36'),(['--search-results','--recalc'],'computed'),
                (['--fixed-strings'],'café'),([], '^A'),([], 'alpha$'),([], 'A.*a'),
                (['--ignore-case'],'ALPHA'),([], '[0-9]+'),([], 'two\\s+words'),([], '東京'),([], 'missing')]


def point(wid,cid,kind,requirement,**check):
    return {'id':f'{wid}/{cid}/result','channel':'backend','method':'program','requirement':requirement,
            'check':{'kind':kind,**check}}


def build():
    out=[]
    wid='program-native-tools';cps=[]
    for i,(flags,pattern) in enumerate(SEARCH_OPTIONS):
        cid=f'search-{i+1:02d}'
        a=point(wid,cid,'search','Search workbook cells with '+repr(pattern)+' and '+repr(flags),flags=flags,pattern=pattern)
        if pattern=='missing':a['requires']=[wid+'/search-01/result']
        cps.append({'id':cid,'goal':a['requirement'],'depends_on':['setup:inputs'],'assertions':[a]})
    for i,formula in enumerate(['=1+2','=UPPER("alpha")','=IF(TRUE,"red","blue")']):
        cid=f'index-{i+1:02d}'
        cps.append({'id':cid,'goal':'Index the text content of a spreadsheet.', 'depends_on':['setup:inputs'],
          'assertions':[point(wid,cid,'index','Index text, Unicode and formula-derived text.',formula=formula)]})
    for i,(cell,value) in enumerate([('B2',99),('A2','Revised'),('C2','=B2*5'),('D5','Added cell'),('A5','élève 北京'),('B4',False)]):
        cid=f'diff-{i+1:02d}'
        cps.append({'id':cid,'goal':'Compare two workbooks with a specific content change.', 'depends_on':['setup:inputs'],
          'assertions':[point(wid,cid,'diff','The native comparison identifies '+cell+' changing to '+str(value),cell=cell,value=value)]})
    for id,flags,patterns in [('pattern-file',[],['Alpha','東京']),('patterns-insensitive',['--ignore-case'],['alpha','café']),
                              ('patterns-fixed',['--fixed-strings'],['a.b','A*B']),('patterns-count',['--count'],['Alpha','two words'])]:
        cps.append({'id':id,'goal':'Search with patterns read from a document file.','depends_on':['setup:inputs'],
                    'assertions':[point(wid,id,'pattern-file','Pattern-file search honors its match options.',flags=flags,patterns=patterns)]})
    for id,kind in [('diff-file','diff-file'),('diff-highlight','diff-highlight'),('diff-style','diff-style')]:
        cps.append({'id':id,'goal':'Compare changed content or styling using native output options.','depends_on':['setup:inputs'],
                    'assertions':[point(wid,id,kind,'The comparison exports the requested change representation.')]})
    out.append({'id':wid,'feature':'native-tools','execution':'program','initial_state':'Fresh application and exchange folders.',
                'setup':[{'id':'inputs','op':'command-inputs'}],'inputs':{},'checkpoints':cps})
    wid='program-convert-options';cps=[]
    assignments=[('A1=99','A1'),('B2=-7.25','B2'),('C3=hello world','C3'),('D4==SUM(A1:A3)','D4'),
                 ('E5==IF(TRUE,42,0)','E5'),('F6=TRUE','F6'),('G7=éclair 東京','G7')]
    for i,(assignment,cell) in enumerate(assignments):
        cid=f'set-{i+1:02d}'
        cps.append({'id':cid,'goal':'Apply a native cell assignment before exporting.', 'depends_on':['setup:inputs'],
          'assertions':[point(wid,cid,'set','ssconvert --set '+assignment,assignment=assignment,cell=cell)]})
    for id,kind,args in [('per-sheet','per-sheet',[]),('merge','merge',[]),
                         ('explicit-import','explicit-import',['--import-type','Gnumeric_XmlIO:sax']),
                         ('missing-file','conversion-error',['inbox/absent.gnumeric','outbox/missing.xlsx']),
                         ('invalid-exporter','conversion-error',['--export-type','invalid_exporter','inbox/search.gnumeric','outbox/invalid.xlsx']),
                         ('invalid-importer','conversion-error',['--import-type','invalid_importer','inbox/search.gnumeric','outbox/invalid-import.xlsx']),
                         ('invalid-option','conversion-error',['--export-type','Gnumeric_stf:stf_assistant','--export-options','not-a-setting=yes','inbox/search.gnumeric','outbox/invalid.csv']),
                         ('bad-file','conversion-error',['--import-type','Gnumeric_XmlIO:sax','inbox/bad.gnumeric','outbox/bad.xlsx'])]:
        a=point(wid,id,kind,'Native conversion behavior: '+id,args=args)
        if kind=='conversion-error':a['requires']=[wid+'/set-01/result']
        cps.append({'id':id,'goal':a['requirement'],'depends_on':['setup:inputs'],'assertions':[a]})
    out.append({'id':wid,'feature':'conversion-options','execution':'program','initial_state':'Fresh application and exchange folders.',
                'setup':[{'id':'inputs','op':'command-inputs'}],'inputs':{},'checkpoints':cps})
    wid='program-excel-function-names';cps=[]
    aliases=['PERCENTILE.INC(Data!A1:A5,0.25)','PERCENTILE.EXC(Data!A1:A5,0.25)',
             'QUARTILE.INC(Data!A1:A5,1)','QUARTILE.EXC(Data!A1:A5,1)',
             'RANK.EQ(4,{1;4;4;9;12},0)','RANK.AVG(4,{1;4;4;9;12},0)',
             'PERCENTRANK.INC(Data!A1:A5,6,4)','PERCENTRANK.EXC(Data!A1:A5,6,4)',
             'COVARIANCE.P(Data!B1:B5,Data!A1:A5)','COVARIANCE.S(Data!B1:B5,Data!A1:A5)',
             'NORM.DIST(2,1,3,FALSE)','NORM.DIST(2,1,3,TRUE)','LOGNORM.DIST(2,0.5,1,FALSE)',
             'LOGNORM.DIST(2,0.5,1,TRUE)','GAMMA.DIST(2,3,4,FALSE)','GAMMA.DIST(2,3,4,TRUE)',
             'BINOM.DIST(3,8,0.4,FALSE)','BINOM.DIST(3,8,0.4,TRUE)',
             'POISSON.DIST(3,2,FALSE)','POISSON.DIST(3,2,TRUE)','STDEV.S(Data!A1:A5)',
             'STDEV.P(Data!A1:A5)','VAR.S(Data!A1:A5)','VAR.P(Data!A1:A5)',
             'CHISQ.DIST(3,4,TRUE)','CHISQ.DIST.RT(3,4)','T.DIST(1.5,8,TRUE)',
             'F.DIST(2,4,8,TRUE)','F.DIST.RT(2,4,8)','BETA.DIST(0.3,2,4,TRUE)',
             'EXPON.DIST(1.5,2,TRUE)','WEIBULL.DIST(2,3,4,TRUE)']
    for i,expr in enumerate(aliases):
        cid=f'alias-{i+1:02d}'
        cps.append({'id':cid,'goal':'Import and calculate a documented Excel function spelling.',
                    'assertions':[point(wid,cid,'excel-alias','XLSX formula '+expr,formula='='+expr)]})
    out.append({'id':wid,'feature':'excel-compatibility','execution':'program','initial_state':'Fresh application and exchange folders.',
                'setup':[],'inputs':{},'checkpoints':cps})
    return out


def setup(ctx,item):
    ctx.state['search-path']=checks.upload(ctx,'search.gnumeric',fixtures.native(SEARCH_SHEETS))['path']
    checks.upload(ctx,'another.gnumeric',fixtures.native({'Third':{'A1':'Merged third sheet','B2':41}}))
    checks.upload(ctx,'bad.gnumeric',b'This is not a spreadsheet\x00\x01')


def canonical_xml(value):
    root=ET.fromstring(value)
    def one(n):
        return {'tag':n.tag.rsplit('}',1)[-1],'attributes':dict(sorted(n.attrib.items())),
                'text':(n.text or '').strip(),'children':[one(c) for c in n]}
    return one(root)


def evaluate(ctx,cp,a):
    c=a['check'];kind=c['kind'];id=cp['id']
    if kind=='pattern-file':
        checks.upload(ctx,'patterns.txt',('\n'.join(c['patterns'])+'\n').encode())
        r=checks.command(ctx,[*c['flags'],'--pattern-file','inbox/patterns.txt','inbox/search.gnumeric'],tool='ssgrep')
        assert r['exit_code'] in (0,1),'pattern-file search failed'
        assert r['stdout'],'pattern-file search returned no matches'
        return {'lines':sorted(r['stdout'].replace(ctx.state['search-path'],'search.gnumeric').splitlines())}
    if kind in ('diff-file','diff-highlight','diff-style'):
        changed={s:dict(v) for s,v in SEARCH_SHEETS.items()};changed['Data']['B2']=99
        styles={'Data':{'A2':{'Rotation':45,'WrapText':1}}} if kind=='diff-style' else None
        checks.upload(ctx,id+'.gnumeric',fixtures.native(changed,styles=styles))
        output=id+('.gnumeric' if kind=='diff-highlight' else '.xml')
        flag='--highlight' if kind=='diff-highlight' else '--xml'
        r=checks.command(ctx,[flag,'--output','outbox/'+output,'inbox/search.gnumeric','inbox/'+id+'.gnumeric'],tool='ssdiff')
        assert r['exit_code'] in (0,1,2),'comparison output failed'
        raw=checks.download(ctx,output)
        if kind=='diff-highlight':
            sheets=checks.native_sheets(raw);sheet=sheets['Data']
            regions=checks.child(sheet,'Styles');marked=[]
            for region in regions:
                style=checks.child(region,'Style')
                if style is not None and style.get('Back') not in (None,'FFFF:FFFF:FFFF'):
                    marked.append([region.get(k) for k in ('startCol','startRow','endCol','endRow')])
            assert marked,'highlight comparison marked no cells'
            return {'marked_ranges':sorted(marked)}
        root=ET.fromstring(raw)
        nodes=[n for n in root.iter() if n.tag.rsplit('}',1)[-1] in ('Cell','StyleRegion')]
        for node in nodes:
            for child in list(node):
                if child.get('New')==child.get('Old'):node.remove(child)
        assert nodes,'comparison did not report a change'
        return {'changes':[canonical_xml(ET.tostring(n)) for n in nodes]}
    if kind=='search':
        r=checks.command(ctx,[*c['flags'],c['pattern'],'inbox/search.gnumeric'],tool='ssgrep')
        assert r['exit_code'] in (0,1),'search failed: '+r['stderr']
        text=r['stdout'].replace(ctx.state['search-path'],'search.gnumeric')
        return {'exit_code':r['exit_code'],'lines':sorted(text.splitlines())}
    if kind=='index':
        checks.upload(ctx,id+'.gnumeric',fixtures.native({'Text':{'A1':'Index input '+id,'A2':'café 東京','B1':c['formula']}}))
        r=checks.command(ctx,['--index','inbox/'+id+'.gnumeric'],tool='ssindex')
        assert r['exit_code']==0 and r['stdout'],'indexer failed'
        root=ET.fromstring(r['stdout'])
        terms=sorted((n.text or '') for n in root.iter() if n.tag.rsplit('}',1)[-1]=='data')
        assert any('Index input' in t for t in terms),'index did not include the input text'
        return {'terms':[t for t in terms if t not in ('Print_Area','Sheet_Title')]}
    if kind=='diff':
        changed={s:dict(v) for s,v in SEARCH_SHEETS.items()};changed['Data'][c['cell']]=c['value']
        checks.upload(ctx,id+'.gnumeric',fixtures.native(changed))
        r=checks.command(ctx,['--xml','inbox/search.gnumeric','inbox/'+id+'.gnumeric'],tool='ssdiff')
        assert r['exit_code'] in (0,1,2) and r['stdout'],'comparison failed: '+r['stderr']
        root=ET.fromstring(r['stdout']); changes=[]
        for sheet in root.iter():
            if sheet.tag.rsplit('}',1)[-1]!='Sheet':continue
            for cell in sheet.iter():
                if cell.tag.rsplit('}',1)[-1]!='Cell':continue
                fields={k:cell.get(k) for k in ('Row','Col','Old','New') if cell.get(k) is not None}
                for field in ('Old','New'):
                    if field not in fields:continue
                    typ=cell.get(field+'ValueType')
                    if typ=='40':fields[field]=float(fields[field])
                    elif typ=='20':fields[field]=fields[field].casefold()=='true'
                    elif fields[field].startswith('='):fields[field]=re.sub(r'\s+','',fields[field]).casefold()
                changes.append({'sheet':sheet.get('Name'),**fields})
        if ctx.record:assert changes,'comparison did not identify the changed cell'
        return {'changes':sorted(changes,key=lambda d:(d['sheet'],int(d['Row']),int(d['Col'])))}
    if kind=='set':
        output=id+'.xlsx'
        checks.convert(ctx,'inbox/search.gnumeric','outbox/'+output,['--recalc','--set',c['assignment']])
        book=checks.workbook(checks.download(ctx,output))
        v=checks.cell_value(book,'Data',c['cell'])
        if ctx.record:assert v['type'] not in ('blank','error'),'assignment was not applied'
        return v
    if kind=='conversion-error':
        r=checks.command(ctx,c['args'])
        if ctx.record:assert r['exit_code']!=0 and r['stderr'],'invalid conversion unexpectedly succeeded'
        return {'failed':r['exit_code']!=0,'diagnostic':bool(r['stderr'].strip())}
    if kind=='explicit-import':
        checks.convert(ctx,'inbox/search.gnumeric','outbox/explicit.xlsx',c['args'])
        return checks.cell_value(checks.workbook(checks.download(ctx,'explicit.xlsx')),'Data','A2')
    if kind=='per-sheet':
        checks.convert(ctx,'inbox/search.gnumeric','outbox/split-%n.csv',['--export-type','Gnumeric_stf:stf_csv','--export-file-per-sheet'])
        files=[f['name'] for f in ctx.broker.call({'op':'list_files','area':'outbox'})['files'] if f['name'].startswith('split-')]
        assert len(files)==2,'per-sheet export did not produce two files'
        return {'documents':sorted(checks.download(ctx,n).decode('utf-8').splitlines() for n in files)}
    if kind=='merge':
        r=checks.command(ctx,['--merge-to','outbox/merged.xlsx','inbox/search.gnumeric','inbox/another.gnumeric'])
        assert r['exit_code']==0,'merge failed: '+r['stderr']
        book=checks.workbook(checks.download(ctx,'merged.xlsx'))
        return {'names':book.sheetnames,'third':checks.cell_value(book,book.sheetnames[-1],'B2')}
    if kind=='excel-alias':
        from openpyxl import Workbook
        book=Workbook();sheet=book.active;sheet.title='Results';sheet['A1']='=_xlfn.'+c['formula'].lstrip('=')
        data=book.create_sheet('Data')
        for k,v in fixtures.FORMULA_DATA.items():data[k]=v
        stream=io.BytesIO();book.save(stream)
        checks.upload(ctx,id+'.xlsx',stream.getvalue())
        checks.convert(ctx,'inbox/'+id+'.xlsx','outbox/'+id+'.xlsx',['--recalc'])
        v=checks.cell_value(checks.workbook(checks.download(ctx,id+'.xlsx')),'Results','A1')
        if ctx.record:assert v['type'] not in ('error','blank'),'Excel function name was not recognized: '+c['formula']
        return v
    raise ValueError(kind)
