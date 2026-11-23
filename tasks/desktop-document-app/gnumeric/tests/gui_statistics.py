"""Native analysis dialogs and their ordinary worksheet reports."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill

ANALYSES=[
 ('descriptive',['Statistics','Descriptive Statistics','Descriptive Statistics...'],'descriptive statistics',{},[],True),
 ('correlation',['Statistics','Descriptive Statistics','Correlation...'],'correlation matrix',{},[],True),
 ('covariance',['Statistics','Descriptive Statistics','Covariance...'],'covariance matrix',{},[],True),
 ('rank-percentile',['Statistics','Descriptive Statistics','Ranks And Percentiles...'],'rank and percentile tables',{},[],True),
 ('regression',['Statistics','Dependent Observations','Regression...'],'linear regression report',{'Y variable:':'B1:B7','X variables:':'C1:C7'},[],True),
 ('moving-average',['Statistics','Dependent Observations','Forecast','Moving Average...'],'moving average report',{},[],True),
 ('smoothing',['Statistics','Dependent Observations','Forecast','Exponential Smoothing...'],'exponential smoothing report',{},[],True),
 ('anova',['Statistics','Multiple Sample Tests','ANOVA','One Factor...'],'one-factor analysis of variance report',{},[],True),
 ('normality',['Statistics','One Sample Tests','Normality Tests...'],'normality test report',{},[choose('Test'),{'op':'check','name':'Create Normal Probability Plot','checked':False}],True),
 ('fourier',['Statistics','Dependent Observations','Fourier Analysis...'],'Fourier real-component report',{},[],True),
]


def build():
    result=[]
    for id,path,description,fields,options,labels in ANALYSES:
        input_range={'normality':'B1:C13','moving-average':'B1:B7','fourier':'B1:B9'}.get(id,'B1:C7')
        filename={'normality':'normality.gnumeric','fourier':'fourier-series.gnumeric'}.get(id,'series.gnumeric')
        samples='the single Sales series' if id in ('moving-average','fourier') else 'Sales and Cost'
        generate={'op':'analysis','path':path,'range':input_range,'output':'E1','fields':fields,'options':options,'labels':labels}
        check={'kind':'analysis-region','analysis':id,'file':id+'.gnumeric','sheet':'Data','range':'E1:Q32',
               'description':'The analysis writes a nonempty, numeric report in the requested output area.'}
        if id=='normality':check.update(min_numbers=8,no_errors=True)
        result.append(episode('analysis-'+id,'statistics',[
          step('report','Use the '+description+' tool on '+samples+' (Data!'+input_range+', with labels in the first row, grouped by columns). '
               +('Use Sales as Y and Cost as X. ' if id=='regression' else '')+
               ('Disable the normal probability plot and keep the other default options. Place the output at Data!E1, as formulas. ' if id=='normality' else
                'Keep the default analysis options and place the output at Data!E1, as formulas. ')+
               'Save as {outbox}/'+id+'.gnumeric.',
               'The generated '+description+' is visible in the worksheet beginning at E1.',
               [generate,save(id+'.gnumeric')],[check]),
          step('update','Change the first Sales observation in B2 from 12 to 30. Save as {outbox}/'+id+'-updated.gnumeric.',
               'The Sales input changes and the generated report remains visible with recalculated results.',
               [set_(B2=30),save(id+'-updated.gnumeric')],
               [{**check,'file':id+'-updated.gnumeric','description':'The analysis output recalculates after the source data is edited.'}],depends=['report'])
        ],inputs=[filename],opened=filename))
    return result
