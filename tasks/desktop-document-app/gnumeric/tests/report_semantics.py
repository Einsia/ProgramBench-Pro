"""Associate statistics with their series, metric, matrix axes or observation index."""
import re


ALIASES={'average':'mean','arithmetic mean':'mean','minimum':'min','maximum':'max','n':'count','observations':'count',
         'std dev':'standard deviation','std deviation':'standard deviation','std error':'standard error',
         'sample variance':'variance','p value':'pvalue','p-value':'pvalue','significance of f':'pvalue',
         'r squared':'r2','r^2':'r2','adjusted r squared':'adjusted r2','adjusted r^2':'adjusted r2',
         't-statistics':'t statistic','t-statistic':'t statistic','coefficients':'coefficient'}


def label(value):
    text=' '.join(str(value).casefold().replace('_',' ').replace(':','').split())
    return ALIASES.get(text,text)


def project(sheet,region,kind):
    import checks
    cells={(c.row,c.column):c for row in sheet[region] for c in row if c.value is not None and c.value!=''}
    assert cells,'analysis report is empty'
    result={}
    def text(r,c):
        n=cells.get((r,c));return label(n.value) if n and n.data_type!='e' and isinstance(n.value,str) else None
    def item(r,c):
        n=cells.get((r,c))
        if n is None:return None
        return {'type':'error','value':n.value} if n.data_type=='e' else checks.number(n.value)
    def put(key,r,c):
        value=item(r,c)
        if value is not None:
            assert key not in result,'ambiguous duplicate report key '+key
            result[key]=value
    def find(name):return [(r,c) for r,c in cells if text(r,c)==label(name)]
    def first(name):
        positions=sorted(find(name));assert positions,'missing report label '+name
        return positions[0]
    def table(anchor,section):
        hr,hc=first(anchor)
        headers={c:text(hr,c) for r,c in cells if r==hr and c>hc and text(r,c)}
        assert headers,'report columns missing for '+anchor
        for r in range(hr+1,max(x[0] for x in cells)+1):
            rowname=text(r,hc)
            if rowname is None:
                if not any((r,c) in cells for c in headers):break
                continue
            if not any(item(r,c) and item(r,c)['type'] in ('number','error') for c in headers):break
            for c,name in headers.items():put(section+'/'+rowname+'/'+name,r,c)
    if kind in ('descriptive','normality','correlation','covariance','one-mean','sign','wilcoxon','paired','variance','unpaired-equal','unpaired-unequal','known-variance','mann-whitney','two-sign','two-wilcoxon'):
        hr,hc=first('Sales');columns={name:c for (r,c) in cells if r==hr and (name:=text(r,c)) in ('sales','cost')}
        assert 'sales' in columns,'sample column header missing'
        if kind in ('descriptive','normality','correlation','covariance'):assert 'cost' in columns,'second sample column missing'
        labelcols=[c for r,c in cells if c<min(columns.values()) and text(r,c)]
        assert labelcols,'metric or matrix row labels missing'
        lc=max(labelcols)
        for r in range(hr+1,max(x[0] for x in cells)+1):
            metric=text(r,lc)
            if not metric:continue
            for series,c in columns.items():
                key=('/'.join(sorted([metric,series])) if kind in ('correlation','covariance') else series+'/'+metric)
                value=item(r,c)
                if value is None:continue
                if key in result:
                    checks.compare(result[key],value)
                else:result[key]=value
    elif kind=='rank-percentile':
        for hr,pc in sorted(find('Point')):
            series=text(hr,pc+1);assert series in ('sales','cost'),'rank table lacks a sample label'
            columns={pc+1:'value'}
            for c in (pc+2,pc+3):
                if text(hr,c):columns[c]=text(hr,c)
            for r in range(hr+1,max(x[0] for x in cells)+1):
                point=item(r,pc)
                if not point or point['type']!='number':break
                for c,metric in columns.items():put(series+'/point-'+str(int(point['value']))+'/'+metric,r,c)
    elif kind in ('moving-average','smoothing','fourier','sampling'):
        for series in ('Sales','Cost'):
            positions=find(series)
            if not positions:continue
            hr,c=positions[0];start=hr+1;component='value'
            if kind=='fourier':
                component=text(start,c) or 'real';start+=1
            sequence=0
            for r in range(start,max(x[0] for x in cells)+1):
                value=item(r,c)
                if value is None:break
                sequence+=1;put(label(series)+'/'+component+'/'+str(sequence),r,c)
        if kind=='smoothing':
            hr,c=first('Exponential Smoothing');put('parameter/alpha',hr+1,c)
    elif kind in ('frequency','kaplan'):
        header='Category' if kind=='frequency' else 'Time';hr,hc=first(header)
        headers={c:text(hr,c) for r,c in cells if r==hr and c>hc and text(r,c)}
        for r in range(hr+1,max(x[0] for x in cells)+1):
            value=item(r,hc)
            if value is None:break
            axis=str(value['value'])
            for c,metric in headers.items():put(axis+'/'+metric,r,c)
    elif kind=='pca':
        hr,hc=first('Covariances');series={name:c for r,c in cells if r==hr and (name:=text(r,c)) in ('sales','cost')}
        assert len(series)==2,'PCA variables are missing'
        for metric in ('Count','Mean','Variance'):
            r,c=first(metric)
            for name,col in series.items():put('sample/'+name+'/'+label(metric),r,col)
        er,ec=first('Eigenvalues');vr,vc=first('Eigenvectors')
        ordered=sorted(((item(er,c)['value'],c) for c in series.values()),reverse=True)
        for i,(eigenvalue,col) in enumerate(ordered,1):
            result['component/'+str(i)+'/eigenvalue']=checks.number(eigenvalue)
            vector=[item(vr+j,col)['value'] for j in range(2)]
            # An eigenvector and its negative describe the same component.
            for x,name in enumerate(series):
                for y,other in enumerate(series):result[f'component/{i}/projector/{name}/{other}']=checks.number(vector[x]*vector[y])
    elif kind=='chi-squared':
        for metric in ('Test Statistic','Degrees of Freedom','p-Value','Critical Value'):
            r,c=first(metric);put(label(metric),r,c+1)
    elif kind=='histogram-bins':
        _,left=first('Histogram');pairs=[]
        for r in sorted({r for r,c in cells}):
            a,b=item(r,left),item(r,left+1)
            if a and b and a['type']==b['type']=='number':
                def bound(v):return '-infinity' if v < -1e100 else 'infinity' if v>1e100 else v
                pairs.append([bound(a['value']),bound(b['value'])])
        assert len(pairs)>=3,'histogram bin intervals missing'
        return {'intervals':pairs}
    elif kind=='anova-two':
        hr,hc=first('Summary');headers={c:text(hr,c) for r,c in cells if r==hr and c>hc and text(r,c)}
        end,_=first('Source of Variation')
        for r in range(hr+1,end):
            axis=item(r,hc)
            if axis is None:continue
            for c,metric in headers.items():
                value=item(r,c)
                if value and value['type']=='number':put('summary/'+str(axis['value']).casefold()+'/'+metric,r,c)
        table('Source of Variation','anova')
    elif kind=='anova':
        table('Groups','summary');table('Source of Variation','anova')
    elif kind=='regression':
        r,c=first('Regression Statistics')
        for rr in range(r+1,r+10):
            metric=text(rr,c);value=item(rr,c+1)
            if metric and value and value['type']=='number':put('fit/sales/'+metric,rr,c+1)
            else:break
        hr,hc=first('df');lc=hc-1
        headers={col:text(hr,col) for row,col in cells if row==hr and text(row,col)}
        for rr in range(hr+1,hr+4):
            rowname=text(rr,lc);assert rowname,'ANOVA source label missing'
            for col,name in headers.items():put('anova/'+rowname+'/'+name,rr,col)
        hr,hc=first('coefficient');lc=hc-1
        headers={col:text(hr,col) for row,col in cells if row==hr and text(row,col)}
        for offset,name in ((4,'lower confidence bound'),(5,'upper confidence bound')):
            if (hr,hc+offset) in cells:headers[hc+offset]=name
        for rr in range(hr+1,hr+3):
            term=text(rr,lc);assert term,'coefficient term label missing'
            for col,name in headers.items():put('coefficient/'+term+'/'+name,rr,col)
        hr,hc=first('Constant');headers={col:text(hr,col) for row,col in cells if row==hr and text(row,col)}
        for rr in range(hr+1,max(x[0] for x in cells)+1):
            if (rr,hc) not in cells:break
            for col,name in headers.items():put('observation/'+str(rr-hr)+'/'+name,rr,col)
    else:raise AssertionError('unknown report semantics '+kind)
    assert sum(v['type']=='number' for v in result.values())>=3,'report contains too few attributed numeric results'
    return {'statistics':result}
