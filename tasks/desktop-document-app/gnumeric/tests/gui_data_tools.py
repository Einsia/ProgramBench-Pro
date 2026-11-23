"""Offline data-generation, transformation and scenario tools."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill,values,formulas


def ck(name,value=True):return {'op':'check','name':name,'checked':value}
def output(cell):return [choose('Output'),choose('Output range:'),fill(None,cell,index=0),button('OK')]


def build():
    out=[]
    def add(id,feature,steps,file):out.append(episode(id,feature,steps,inputs=[file],opened=file))
    add('consolidate','consolidation',[
      step('sum','Consolidate Areas!A1:B2 and Areas!D1:E2 by position, using SUM, into A5. Save as {outbox}/consolidated.gnumeric.',
           'The output combines the matching positions of both source regions.',
           [{'op':'consolidate','ranges':['A1:B2','Areas!D1:E2'],'output':'A5'},save('consolidated.gnumeric')],
           [values('consolidated.gnumeric','Areas',A5=5,B5=9,A6=13,B6=17)]),
      step('mean','Consolidate the same two source regions using AVERAGE into D5. Save as {outbox}/averaged.gnumeric.',
           'The second consolidation shows the mean for each corresponding source position.',
           [{'op':'consolidate','ranges':['A1:B2','Areas!D1:E2'],'function':'AVERAGE','output':'D5'},save('averaged.gnumeric')],
           [values('averaged.gnumeric','Areas',D5=2.5,E5=4.5,D6=6.5,E6=8.5)],depends=['sum'])
    ],'consolidate-input.gnumeric')
    add('text-to-columns','text-to-columns',[
      step('split','Split A2:A4 into columns using semicolon separators and double-quote text indicators. Keep empty fields separate. Save as {outbox}/split.gnumeric.',
           'The parsed table places quoted semicolons within product names and preserves the empty quantity field.',
           [goto('A2:A4'),menu('Data','Text to Columns...'),button('Forward'),ck('Semicolon (;)'),ck('See two separators as one',False),button('Finish'),save('split.gnumeric')],
           [values('split.gnumeric','Text',B2='Tea;North',C2=8,D2=3.5,B3='Coffee',C3=None,D3=6,B4='Cocoa',C4=12,D4=4.25)]),
      step('calculate','Calculate quantity times price in E2 and E4 from the newly split numeric columns. Save as {outbox}/split-calculated.gnumeric.',
           'The parsed numeric fields support arithmetic results beside the table.',
           [set_(E2='=C2*D2',E4='=C4*D4'),save('split-calculated.gnumeric')],
           [values('split-calculated.gnumeric','Text',E2=28,E4=51)],depends=['split'])
    ],'split-input.gnumeric')
    add('data-table','data-table',[
      step('column','Build a one-variable Data Table in E1:F4 with A1 as the column input cell. The result formula is already in F1. Save as {outbox}/column-table.gnumeric.',
           'The result column evaluates the model for each input listed in E2:E4.',
           [goto('E1:F4'),menu('Data','Table...'),fill('Column Input:','A1'),button('OK'),save('column-table.gnumeric')],
           [values('column-table.gnumeric','Model',F2=8,F3=11,F4=17,A1=2,B1=3)]),
      step('two-inputs','Build a two-variable Data Table in J1:L3 using B1 as the row input and A1 as the column input. Save as {outbox}/two-inputs.gnumeric.',
           'The four result cells evaluate the combinations of row and column input values.',
           [goto('J1:L3'),menu('Data','Table...'),fill('Row Input:','B1'),fill('Column Input:','A1'),button('OK'),save('two-inputs.gnumeric'),goto('L3')],
           [values('two-inputs.gnumeric','Model',K2=7,L2=10,K3=11,L3=20)],depends=['column'])
    ],'model-table.gnumeric')
    add('tabulate-dependency','tabulate-dependency',[
      step('generate','Tabulate C1 while varying A1 from 1 to 5 in steps of 2, in Coordinate mode. Rename the generated sheet Dependency and show it. Save as {outbox}/dependency.gnumeric.',
           'The generated sheet lists each input alongside its model result.',
           [menu('Data','Fill','Tabulate Dependency...'),fill(None,'A1',index=3),fill(None,1,index=12),fill(None,5,index=9),fill(None,2,index=6),fill(None,'C1',index=0),choose('Coordinate'),button('OK'),choose('Tabulation'),menu('Edit','Sheet','Rename...'),fill(None,'Dependency',index=0),button('OK'),save('dependency.gnumeric')],
           [values('dependency.gnumeric','Dependency',A1=1,B1=8,A2=3,B2=14,A3=5,B3=20),values('dependency.gnumeric','Model',A1=2,C1=11)])
    ],'model-table.gnumeric')
    add('fill-merge','fill-merge',[
      step('generate','Use Fill Merge on template A1:B2, mapping the names in D2:D4 into template cell B2. Show the generated template for Tea and save as {outbox}/merged-templates.gnumeric.',
           'Separate generated worksheets contain the invoice template populated with the source names.',
           [goto('A1:B2'),menu('Data','Fill','Merge...'),fill(None,'D2:D4',index=1),fill(None,'B2',index=0),key('Tab'),button('Add'),button('Merge'),choose('Sheet1'),save('merged-templates.gnumeric')],
           [{'kind':'generated-sheets','file':'merged-templates.gnumeric','exclude':['Template'],'cells':['A1','A2','B2'],
             'expected':{'rows':[['Invoice','Customer','Cocoa'],['Invoice','Customer','Coffee'],['Invoice','Customer','Tea']]},'description':'Every data row creates its own populated template.'}]),
      step('undo','Undo the Fill Merge operation and save as {outbox}/unmerged-templates.gnumeric.',
           'The original template and source names remain after the generated sheets are removed.',
           [key('Control+Z'),save('unmerged-templates.gnumeric')],
           [{'kind':'sheets','file':'unmerged-templates.gnumeric','expected':{'names':['Template']},'description':'Undo removes the generated sheets while retaining the template.'},values('unmerged-templates.gnumeric','Template',B2='name',D2='Tea',D4='Cocoa')],depends=['generate'])
    ],'merge-template.gnumeric')
    add('advanced-filter','advanced-filter',[
      step('and','Advanced-filter A1:E7 using the AND criteria in G1:H2. Put the output at A11, preserving the source. Save as {outbox}/and-filter.gnumeric.',
           'The extracted rows satisfy both the region and units conditions.',
           [goto('A1:E7'),menu('Data','Filter','Advanced Filter...'),fill('Criteria range:','G1:H2'),*output('A11'),save('and-filter.gnumeric')],
           [values('and-filter.gnumeric','Sales',A15='Cocoa',B15='North',C15=12,E15=51,A16=None,A2='Tea')]),
      step('or','Use Advanced Filter on A1:E7 with the OR criteria in J1:J3, writing the result at A21. Save as {outbox}/or-filter.gnumeric and show the extracted rows.',
           'The extracted table includes the North and East region records.',
           [goto('A1:E7'),menu('Data','Filter','Advanced Filter...'),fill('Criteria range:','J1:J3'),*output('A21'),save('or-filter.gnumeric'),goto('A25:E28')],
           [values('or-filter.gnumeric','Sales',A25='Tea',A26='Cocoa',A27='Juice',A28='Milk',A29=None)],depends=['and'])
    ],'filter-input.gnumeric')
    add('scenarios','scenarios',[
      step('capture','Save the current C2:D2 inputs as a scenario named Baseline. Change C2 to 20 and D2 to 5, then save those inputs as a scenario named Growth. Show Baseline and save as {outbox}/baseline.gnumeric.',
           'Showing Baseline restores the original Tea inputs and recalculates revenue.',
           [goto('C2:D2'),menu('Tools','Scenarios','Add...'),fill('Scenario name:','Baseline'),fill('Changing cells:','C2:D2'),button('OK'),set_(C2=20,D2=5),goto('C2:D2'),menu('Tools','Scenarios','Add...'),fill('Scenario name:','Growth'),fill('Changing cells:','C2:D2'),button('OK'),menu('Tools','Scenarios','View...'),choose('Baseline'),button('Show'),button('OK'),save('baseline.gnumeric')],
           [values('baseline.gnumeric','Sales',C2=8,D2=3.5,E2=28)]),
      step('growth','Show the saved Growth scenario and save as {outbox}/growth-scenario.gnumeric.',
           'The Growth inputs and their calculated revenue are restored.',
           [menu('Tools','Scenarios','View...'),choose('Growth'),button('Show'),button('OK'),save('growth-scenario.gnumeric')],
           [values('growth-scenario.gnumeric','Sales',C2=20,D2=5,E2=100)],depends=['capture']),
      step('reopen','The application has restarted. Open {outbox}/growth-scenario.gnumeric and show its Baseline scenario.',
           'The saved scenario remains available after reopening and restores its inputs.',
           [{'op':'open','file':'growth-scenario.gnumeric','area':'outbox'},menu('Tools','Scenarios','View...'),choose('Baseline'),button('Show'),button('OK')],depends=['growth'],lifecycle='restart')
    ],'ledger.gnumeric')
    run_sim=[menu('Tools','Simulation...'),fill('Input variables:','A1'),fill('Output variables:','B1'),choose('Options'),
             fill('Iterations:',10),fill('First round #:',1),fill('Last round #:',1),key('Tab'),
             choose('Output'),choose('Output range:'),fill(None,'D1',index=0),button('OK'),choose('Summary'),{'op':'simulation-summary'}]
    out.append(episode('risk-simulation','simulation',[
      step('constant','Enter 7 in A1 and =2*A1+1 in B1, then save as {outbox}/simulation-source.gnumeric. Run Risk Simulation with A1 as the input variable and B1 as the output variable, 10 iterations, first and last rounds both 1, worksheet output at D1. Show the complete Summary, enlarging the dialog if necessary.',
           'The simulation summary reports the requested iteration count and constant input/output minima, averages and maxima.',
           [set_(A1=7,B1='=2*A1+1'),save('simulation-source.gnumeric'),*run_sim]),
      step('change','Close the simulation dialog, change A1 to 11, then run the same 10-iteration simulation for round 1 again and show its Summary.',
           'The simulation summary changes the input and dependent output statistics consistently.',
           [button('Close'),set_(A1=11),*run_sim],depends=['constant'])
    ]))
    return out
