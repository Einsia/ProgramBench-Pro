"""Validation, filters, outlines, conditional styles, named ranges and solver."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill,values


def combo(label,value):return {'op':'combo','label':label,'value':value}
def check(name,value=True):return {'op':'check','name':name,'checked':value}


def build():
    out=[]
    def add(id,feature,steps):
        out.append(episode(id,feature,steps,inputs=['ledger.gnumeric'],opened='ledger.gnumeric'))
    add('validation','validation',[
      step('configure','For C2:C7 allow only whole numbers between 1 and 20 inclusive, ignoring blank cells, with a Stop error alert. Confirm the rule and enter 15 in C2. Save as {outbox}/validated.gnumeric.',
           'The valid units value 15 is accepted and the Tea revenue updates.',
           [goto('C2:C7'),menu('Data','Validate...'),combo('Allow:','Whole numbers'),fill('Min:',1),fill('Max:',20),combo('Action:','Stop            (never allow invalid input)'),check('Ignore blank cells'),button('OK'),set_(C2=15),save('validated.gnumeric')],
           [values('validated.gnumeric','Sales',C2=15,E2=52.5)]),
      step('reject','Try to change C2 to 25 and leave the validation response visible.',
           'The application rejects the out-of-range value and offers to re-edit or discard it.',[set_(C2=25)],depends=['configure']),
      step('recover','Discard the invalid edit, then change C2 to 10 and save as {outbox}/recovered.gnumeric.',
           'C2 accepts 10 and its revenue recalculates.',[button('Discard'),set_(C2=10),save('recovered.gnumeric')],
           [values('recovered.gnumeric','Sales',C2=10,E2=35)],depends=['reject'])
    ])
    add('auto-filter','filtering',[
      step('north','Add an Auto Filter to A1:E7 and filter the Region column to North only.',
           'Only Tea and Cocoa remain visible under the table headers; the total row outside the filter remains.',
           [goto('A1:E7'),menu('Data','Filter','Add Auto Filter'),{'op':'click','x':280,'y':224},choose('North'),key('Return')]),
      step('all','Clear the Region filter by selecting all values.',
           'All six product rows are visible again.',[{'op':'click','x':280,'y':224},choose('(All)'),key('Return')],depends=['north'])
    ])
    add('group-outline','outlining',[
      step('group','Group rows 2 through 4 and collapse that group.',
           'The three grouped product rows are hidden and an outline control offers to expand them.',
           [goto('A2:A4'),menu('Data','Group and Outline','Group...'),choose('Rows'),button('OK'),menu('Data','Group and Outline','Hide Detail'),choose('Rows'),button('OK')]),
      step('expand','Expand the grouped rows again.',
           'Tea, Coffee and Cocoa are visible again with the outline grouping retained.',
           [goto('A2:A4'),menu('Data','Group and Outline','Show Detail'),choose('Rows'),button('OK')],depends=['group'])
    ])
    add('conditional-format','conditional-formatting',[
      step('rule','For C2:C7 create a conditional format that displays values greater than 10 in font size 18, then close the editor. Save as {outbox}/conditional.gnumeric.',
           'The units values 12 and 15 are visibly larger, while values at or below 10 retain their ordinary size.',
           [goto('C2:C7'),menu('Format','Cells','Conditional Formatting...'),combo('Condition:','Cell value is > x.'),fill('x:',10),check('Font'),button('Edit Style'),choose('Font'),fill('Size:',18),button('OK'),button('⇐ Add'),button('Close'),save('conditional.gnumeric')]),
      step('update','Change C2 to 18 and C4 to 5. Save as {outbox}/condition-updated.gnumeric.',
           'C2 enlarges and C4 returns to ordinary size as their values cross the rule threshold.',
           [set_(C2=18,C4=5),save('condition-updated.gnumeric')],[values('condition-updated.gnumeric','Sales',C2=18,C4=5)],depends=['rule'])
    ])
    add('defined-names','names',[
      step('define','Name the range C2:C7 UnitsRange, then enter =SUM(UnitsRange) in G1. Save as {outbox}/named.gnumeric.',
           'G1 displays the sum calculated through the new named range.',[goto('C2:C7'),goto('UnitsRange'),set_(G1='=SUM(UnitsRange)'),save('named.gnumeric')],
           [values('named.gnumeric','Sales',G1=57)]),
      step('change','Change C2 to 20 and save as {outbox}/named-update.gnumeric.',
           'The formula using UnitsRange updates after a value inside the named range changes.',[set_(C2=20),save('named-update.gnumeric')],
           [values('named-update.gnumeric','Sales',G1=69)],depends=['define'])
    ])
    add('solver','optimization',[
      step('optimize','Use Solver to maximize E2 by changing C2, with a linear model, nonnegative variables and the constraint E2 <= 70. Keep the optimal result and save as {outbox}/solved.gnumeric.',
           'The Tea revenue reaches the allowed maximum and its units value changes accordingly.',
           [goto('E2'),menu('Tools','Solver...'),fill('Set Target Cell:','$E$2'),fill('By Changing Cells:','$C$2'),key('Tab'),choose('Max'),choose('Model'),choose('Linear Model (LP/MILP)'),check('Assume Non-Negative'),choose('Constraints'),fill('Left Hand Side:','$E$2'),fill('Right Hand Side:',70),key('Tab'),button('Add'),button('Solve'),{'op':'wait','seconds':1},button('Close'),save('solved.gnumeric')],
           [values('solved.gnumeric','Sales',C2=20,E2=70)]),
      step('formula','Change D2 to 5 and save as {outbox}/after-solver.gnumeric.',
           'The retained units value remains and the revenue formula updates to the new price.',[set_(D2=5),save('after-solver.gnumeric')],
           [values('after-solver.gnumeric','Sales',C2=20,E2=100)],depends=['optimize'])
    ])
    return out
