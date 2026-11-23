"""Program episodes using ordinary spreadsheet documents and native CLI operations."""
from collections import defaultdict
import re
import checks
import fixtures
import formulas


def family(case):
    f=case['family'].removeprefix('functions-')
    if f in ('math','numeric-boundaries','rounding','arithmetic','flt','numtheory'):return 'math'
    if f in ('stat','aggregates','order-statistics','regression','statistical-tests','distributions'):return 'statistics'
    if f in ('r','r-distributions','random'):return 'distributions'
    if f in ('date','dates','hebrew-date','christian-date'):return 'dates'
    if f in ('financial','financial-basis','derivatives','erlang'):return 'finance'
    if f in ('string','text'):return 'text'
    if f in ('eng','engineering','complex'):return 'engineering'
    if f in ('lookup','lookup-arrays','database','tsa'):return 'references'
    if f in ('info','logical','logical-types','error-classification'):return 'logical'
    return f


def build():
    grouped=defaultdict(list)
    for case in formulas.cases():grouped[family(case)].append(case)
    out=[]
    for group,cases in sorted(grouped.items()):
        wid='program-formulas-'+group
        cps=[];setup=[]
        for offset in range(0,len(cases),32):
            block=cases[offset:offset+32];cid=f'batch-{offset//32+1:02d}'
            setup.append({'id':cid,'before':cid,'op':'formula-input','cases':block})
            points=[]
            for row,case in enumerate(block,1):
                points.append({'id':f'{wid}/{cid}/formula-{offset+row:04d}','channel':'backend','method':'program',
                               'requirement':case['meaning'], 'check':{'kind':'formula','cell':f'B{row}','case':case}})
            cps.append({'id':cid,'goal':'Recalculate the independent formula examples in the supplied workbook.',
                        'depends_on':['setup:'+cid],'assertions':points})
        out.append({'id':wid,'feature':group,'execution':'program','initial_state':'Fresh offline spreadsheet process and exchange folders.',
                    'setup':setup,'inputs':{},'checkpoints':cps})
    import format_cases
    import command_cases
    import portable_cases
    return out+format_cases.build()+command_cases.build()+portable_cases.build()


def setup(ctx,item):
    if item['op']=='portable-input':
        import portable_cases
        return portable_cases.setup(ctx,item)
    if item['op']=='formula-input':
        values={}
        for i,case in enumerate(item['cases'],1):
            values[f'A{i}']=case['meaning']
            values[f'B{i}']=case['formula']
        source=fixtures.native({'Results':values,'Data':fixtures.FORMULA_DATA,'Database':fixtures.DATABASE})
        checks.upload(ctx,item['id']+'.gnumeric',source)
        return
    if item['op']=='command-inputs':
        import command_cases
        return command_cases.setup(ctx,item)
    import format_cases
    return format_cases.setup(ctx,item)


def evaluate(ctx,checkpoint,assertion):
    check=assertion['check'];cid=checkpoint['id']
    if check['kind']!='formula':
        if check['kind'] in ('legacy','document-export'):
            import portable_cases
            return portable_cases.evaluate(ctx,checkpoint,assertion)
        if ctx.episode['id'].startswith(('program-native-tools','program-convert-options','program-excel-function-names')):
            import command_cases
            return command_cases.evaluate(ctx,checkpoint,assertion)
        import format_cases
        return format_cases.evaluate(ctx,checkpoint,assertion)
    key=('formula-output',cid)
    if key not in ctx.state:
        try:
            checks.convert(ctx,'inbox/'+cid+'.gnumeric','outbox/'+cid+'.xlsx',['--recalc'])
            ctx.state[key]=(checks.workbook(checks.download(ctx,cid+'.xlsx')),None)
        except Exception as error:
            ctx.state[key]=(None,error)
    book,error=ctx.state[key]
    if error is not None:raise error
    value=checks.cell_value(book,'Results',check['cell'])
    if ctx.record:
        case=check['case']
        if case.get('error'):
            assert value['type']=='error','invalid input unexpectedly produced a result: '+case['formula']
            assert value['value']!='#NAME?','invalid test function: '+case['formula']
        else:
            assert value['type'] not in ('error','blank'),'reference example produced no valid result: '+case['formula']+' '+str(value)
    return checks.mathematical_value(value,check['case']['formula'])
