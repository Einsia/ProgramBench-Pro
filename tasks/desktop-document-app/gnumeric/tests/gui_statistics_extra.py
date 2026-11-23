"""Additional statistical report generators with attributed numeric outputs."""
from gui import episode,step,goto,set_,menu,save,button,choose,fill,values


def ck(name,value=True):return {'op':'check','name':name,'checked':value}


def build():
    out=[]
    one=['Statistics','One Sample Tests'];two=['Statistics','Two Sample Tests']
    reports=[
      ('one-mean',one+['Claims About a Mean...'],'one-sample mean test',{},[choose('Test'),fill('Predicted Mean:',20)],'Use a predicted mean of 20.','normality.gnumeric','B1:C13'),
      ('sign',one+['Claims About a Median','Sign Test...'],'sign test',{},[choose('Test'),fill('Predicted Median:',20)],'Use a predicted median of 20.','normality.gnumeric','B1:C13'),
      ('wilcoxon',one+['Claims About a Median','Wilcoxon Signed Rank Test...'],'one-sample Wilcoxon signed-rank test for each column separately',{},[choose('Test'),fill('Predicted Median:',20)],'Test each column against a predicted population median of 20.','normality.gnumeric','B1:C13'),
      ('paired',two+['Claims About Two Means','Paired Samples...'],'paired t test',{'Variable 1 range:':'B1:B7','Variable 2 range:':'C1:C7'},[choose('Test'),fill('Hypothesized mean difference:',2)],'Use a hypothesized mean difference of 2.','series.gnumeric','B1:C7'),
      ('unpaired-equal',two+['Claims About Two Means','Unpaired Samples, Equal Variances...'],'unpaired equal-variance t test',{'Variable 1 range:':'B1:B7','Variable 2 range:':'C1:C7'},[],'','series.gnumeric','B1:C7'),
      ('unpaired-unequal',two+['Claims About Two Means','Unpaired Samples, Unequal Variances...'],'unpaired unequal-variance t test',{'Variable 1 range:':'B1:B7','Variable 2 range:':'C1:C7'},[],'','series.gnumeric','B1:C7'),
      ('variance',two+['Claims About Two Variances'],'variance-ratio F test',{'Variable 1 range:':'B1:B7','Variable 2 range:':'C1:C7'},[],'','series.gnumeric','B1:C7'),
      ('pca',['Statistics','Dependent Observations','Principal Components Analysis...'],'principal components analysis',{},[],'','series.gnumeric','B1:C7'),
    ]
    for id,path,description,fields,options,detail,file,range_ in reports:
        check={'kind':'analysis-region','analysis':id,'file':id+'.gnumeric','sheet':'Data','range':'E1:U40',
               'description':'The saved report associates each statistic with its sample, metric or component.'}
        out.append(episode('analysis-'+id,'statistical-generators',[
          step('report','Run the '+description+' on Sales and Cost in Data!'+range_+', with first-row labels and columns as groups. '+detail+
               'Keep other defaults, put formula output at E1 and save as {outbox}/'+id+'.gnumeric.',
               'The generated '+description+' is visible beside its input samples.',
               [{'op':'analysis','path':path,'range':range_,'fields':fields,'options':options,'output':'E1'},save(id+'.gnumeric')],[check]),
          step('update','Change B2 from 12 to 30. Save as {outbox}/'+id+'-updated.gnumeric.',
               'The edited Sales sample and recalculated report remain visible.',[set_(B2=30),save(id+'-updated.gnumeric')],
               [{**check,'file':id+'-updated.gnumeric','description':'The report recalculates its attributed statistics after a sample changes.'}],depends=['report'])
        ],inputs=[file],opened=file))
    for id,path,title,range_,file,fields,opts in [
        ('anova-two',['Statistics','Multiple Sample Tests','ANOVA','Two Factor...'],'two-factor ANOVA without replication','A1:C7','series.gnumeric',{},[]),
        ('chi-squared',['Statistics','Multiple Sample Tests','Contingency Table','Test of Independence...'],'contingency-table independence test','A1:C4','contingency.gnumeric',{'Contingency Table:':'A1:C4'},[])]:
        check={'kind':'analysis-region','analysis':id,'file':id+'.gnumeric','sheet':'Data','range':'E1:U40','description':'The report preserves metric and factor associations.'}
        out.append(episode('analysis-'+id,'statistical-generators',[
          step('report','Generate the '+title+' for Data!'+range_+' with labels. Keep the default options, place formulas at E1 and save as {outbox}/'+id+'.gnumeric.',
               'The generated '+title+' is visible with its input table.',
               [{'op':'analysis','path':path,'range':range_,'fields':fields,'options':opts,'output':'E1'},save(id+'.gnumeric')],[check]),
          step('update','Change B2 from 12 to 30 and save as {outbox}/'+id+'-updated.gnumeric.',
               'The generated test results update after the observation changes.',[set_(B2=30),save(id+'-updated.gnumeric')],
               [{**check,'file':id+'-updated.gnumeric'}],depends=['report'])
        ],inputs=[file],opened=file))
    out.append(episode('histogram-cutoffs','histogram',[
      step('bins','Generate a Histogram for Sales in B1:B7 with labels. Use three calculated cutoffs from 15 to 30 and the default bin endpoint convention, without a chart. Put output at E1 and save as {outbox}/histogram.gnumeric.',
           'The generated histogram output shows the requested finite cutoff boundaries and outer intervals.',
           [{'op':'analysis','path':['Statistics','Descriptive Statistics','Frequency Tables','Histogram...'],'range':'B1:B7','output':'E1',
             'options':[choose('Cutoffs'),fill('Number of cutoffs:',3),fill('Minimum cutoff:',15),fill('Maximum cutoff:',30),choose('Graphs & Options'),choose('No chart')]},save('histogram.gnumeric')],
           [{'kind':'analysis-region','analysis':'histogram-bins','file':'histogram.gnumeric','sheet':'Data','range':'E1:U20',
             'expected':{'intervals':[['-infinity',15],[15,22.5],[22.5,30],[30,'infinity']]},'description':'The four displayed bin intervals preserve their ordered boundaries.'}])
    ],inputs=['series.gnumeric'],opened='series.gnumeric'))
    out.append(episode('periodic-sampling','sampling',[
      step('sample','Take one periodic sample from Sales in B1:B7, with labels, period 2, offset 0 and sample-size field 3. Place formulas at E1 and save as {outbox}/sample.gnumeric.',
           'The output lists every second Sales observation in source order.',
           [{'op':'analysis','path':['Statistics','Sampling...'],'range':'B1:B7','options':[choose('Options'),fill('Period:',2),fill('Size of sample:',3),fill('Offset:',0)],'output':'E1'},save('sample.gnumeric')],
           [values('sample.gnumeric','Data',E1='Sales',E2=19,E3=26,E4=35)]),
      step('update','Change B3 to 22 and save as {outbox}/sample-updated.gnumeric.',
           'The sampled occurrence of the changed source observation updates.',[set_(B3=22),save('sample-updated.gnumeric')],
           [values('sample-updated.gnumeric','Data',E2=22,E3=26,E4=35)],depends=['sample'])
    ],inputs=['series.gnumeric'],opened='series.gnumeric'))
    out.append(episode('frequency-table','frequency-tables',[
      step('count','Generate a Frequency Table for Region in B1:B7, with labels and the predetermined categories G2:G5. Use exact comparisons and put formulas at A11. Save as {outbox}/frequency.gnumeric.',
           'The generated table attributes a count to each displayed region category.',
           [{'op':'analysis','path':['Statistics','Descriptive Statistics','Frequency Tables','Frequency Tables...'],'range':'B1:B7','options':[choose('Categories'),fill('Category range:','G2:G5')],'output':'A11'},save('frequency.gnumeric')],
           [{'kind':'analysis-region','analysis':'frequency','file':'frequency.gnumeric','sheet':'Sales','range':'A11:F25','description':'Frequency counts remain associated with their categories.'}]),
      step('change','Change B2 from North to South and save as {outbox}/frequency-updated.gnumeric.',
           'The North and South frequencies change to reflect the revised category.',[set_(B2='South'),save('frequency-updated.gnumeric')],
           [{'kind':'analysis-region','analysis':'frequency','file':'frequency-updated.gnumeric','sheet':'Sales','range':'A11:F25','description':'Category counts update after the source record changes.'}],depends=['count'])
    ],inputs=['frequency-input.gnumeric'],opened='frequency-input.gnumeric'))
    out.append(episode('kaplan-meier','survival-analysis',[
      step('estimate','Generate Kaplan-Meier estimates from times B2:B7 without censorship. Disable the graph; retain standard errors and the other default options. Place the output at E1 and save as {outbox}/survival.gnumeric.',
           'The generated survival table associates times with the population at risk and survival estimates.',
           [goto('B2:B7'),menu('Statistics','Dependent Observations','Kaplan-Meier Estimates...'),fill('Time column:','B2:B7'),ck('Permit censorship',False),choose('Options'),ck('Show graph',False),choose('Output'),choose('Output range:'),fill(None,'E1',index=0),button('OK'),save('survival.gnumeric')],
           [{'kind':'analysis-region','analysis':'kaplan','file':'survival.gnumeric','sheet':'Data','range':'E1:U30','description':'Survival values retain their time axis and metric associations.'}]),
      step('change','Change B2 from 12 to 18 and save as {outbox}/survival-updated.gnumeric.',
           'The survival table updates its times and associated risk estimates.',[set_(B2=18),save('survival-updated.gnumeric')],
           [{'kind':'analysis-region','analysis':'kaplan','file':'survival-updated.gnumeric','sheet':'Data','range':'E1:U30','description':'Time-indexed survival estimates recalculate after an observation changes.'}],depends=['estimate'])
    ],inputs=['series.gnumeric'],opened='series.gnumeric'))
    return out
