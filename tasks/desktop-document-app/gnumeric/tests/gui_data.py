"""Range transformations and data tools."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill,values,formulas,style


def build():
    w=[]
    def add(id,feature,steps,input='ledger.gnumeric'):
        w.append(episode(id,feature,steps,inputs=[input] if input else [],opened=input))
    add('paste-special','clipboard',[
      step('transpose','Copy A1:C4 and paste it transposed starting at G1. Save as {outbox}/transposed.gnumeric.',
           'The copied table is transposed: product names run across the first row of the new block.',
           [goto('A1:C4'),key('Control+C'),goto('G1'),menu('Edit','Paste Special...'),choose('Transpose'),button('OK'),save('transposed.gnumeric')],
           [values('transposed.gnumeric','Sales',G1='Product',H1='Tea',J1='Cocoa',G3='Units',H3=8,J3=12)]),
      step('values','Copy E2:E7 and paste only its calculated values starting at G6. Save as {outbox}/values.gnumeric.',
           'G6:G11 shows the copied revenue values.',
           [goto('E2:E7'),key('Control+C'),goto('G6'),menu('Edit','Paste Special...'),choose('As Value'),{'op':'choose','name':'None','nth':0},button('OK'),save('values.gnumeric')],
           [values('values.gnumeric','Sales',G6=28,G7=30,G11=20)]),
      step('multiply','Enter 2 in J10, copy J10, and use Paste Special Multiply on C2:C7. Save as {outbox}/multiplied.gnumeric.',
           'Each Units value is multiplied by two and dependent revenue results update.',
           [set_(J10=2),goto('J10'),key('Control+C'),goto('C2:C7'),menu('Edit','Paste Special...'),choose('Multiply'),button('OK'),save('multiplied.gnumeric')],
           [values('multiplied.gnumeric','Sales',C2=16,C7=20,E8=330.5)]),
      step('independent-values','Change C2 to 30 and save as {outbox}/value-paste-independent.gnumeric.',
           'The source revenue recalculates while the pasted value in G6 retains its earlier result.',
           [set_(C2=30),save('value-paste-independent.gnumeric')],
           [values('value-paste-independent.gnumeric','Sales',E2=105,G6=28),
            {'kind':'literal-cells','file':'value-paste-independent.gnumeric','sheet':'Sales','cells':['G6','G7','G11'],'expected':{'literal':True},'description':'Value-only paste contains no dependent formulas.'}],depends=['values','multiply'])
    ])
    add('fill-series','fill',[
      step('linear','Fill G2:G7 with a linear series starting at 3 and increasing by 4. Save as {outbox}/linear.gnumeric.',
           'G2:G7 contains a regular increasing numeric series beginning with 3.',
           [goto('G2:G7'),menu('Data','Fill','Series...'),choose('Column'),choose('Linear'),fill('Start value:',3),fill('Step value:',4),fill('Stop value:',23),button('OK'),save('linear.gnumeric')],
           [values('linear.gnumeric','Sales',G2=3,G3=7,G7=23)]),
      step('growth','Fill H2:H6 with a growth series starting at 2, multiplying by 3 each step. Save as {outbox}/growth.gnumeric.',
           'H2:H6 contains the requested multiplicative series.',
           [goto('H2:H6'),menu('Data','Fill','Series...'),choose('Column'),choose('Growth'),fill('Start value:',2),fill('Step value:',3),fill('Stop value:',162),button('OK'),save('growth.gnumeric')],
           [values('growth.gnumeric','Sales',H2=2,H3=6,H6=162)]),
      step('autofill','Enter 10 in I2 and 15 in I3, select I2:I7, and use Autofill. Save as {outbox}/auto.gnumeric.',
           'The increasing pattern continues through the selected range.',
           [set_(I2=10,I3=15),goto('I2:I7'),menu('Data','Fill','Autofill'),save('auto.gnumeric')],
           [values('auto.gnumeric','Sales',I2=10,I3=15,I7=35)])
    ])
    add('search-text','search',[
      step('find','Search the current sheet for Cocoa. Leave the search results visible.',
           'The search identifies the Cocoa cell as a match.',
           [menu('Edit','Search...'),fill('Search for:','Cocoa'),choose('Current sheet'),button('Find')]),
      step('next','Close the search dialog. Search the current sheet for South and leave its matching cells listed.',
           'The search lists the two South region cells.',
           [button('Close'),menu('Edit','Search...'),fill('Search for:','South'),choose('Current sheet'),button('Find')])
    ])
    add('replace-text','search',[
      step('replace','Replace every occurrence of Blue in the current sheet with Amber, matching case. Save as {outbox}/replaced.gnumeric.',
           'The two Blue team notes become Amber team; the lowercase blue sky note remains.',
           [menu('Edit','Search & Replace...'),fill('Search for','Blue'),fill('Replace by','Amber'),
            {'op':'check','name':'Ignore case','checked':False},{'op':'check','name':'Query','checked':False},choose('Current sheet'),button('OK'),save('replaced.gnumeric')],
           [values('replaced.gnumeric','Text',B2='Amber team',B3='blue sky',B5='Amber team')]),
      step('ignore-case','Replace blue with Silver in the current sheet, ignoring case. Save as {outbox}/insensitive.gnumeric.',
           'The lowercase blue sky note changes to Silver sky.',
           [menu('Edit','Search & Replace...'),fill('Search for','blue'),fill('Replace by','Silver'),
            {'op':'check','name':'Ignore case','checked':True},{'op':'check','name':'Query','checked':False},choose('Current sheet'),button('OK'),save('insensitive.gnumeric')],
           [values('insensitive.gnumeric','Text',B3='Silver sky')],depends=['replace']),
      step('undo','Undo the last replacement operation. Save as {outbox}/undo-replace.gnumeric.',
           'The blue sky note is restored while the earlier Amber team replacements remain.',
           [key('Control+Z'),save('undo-replace.gnumeric')],[values('undo-replace.gnumeric','Text',B2='Amber team',B3='blue sky')],depends=['ignore-case'])
    ],input='text.gnumeric')
    add('column-width','structure',[
      step('width','Set column A to a width of 200 pixels.','The Product column becomes wider and its text remains visible.',
           [goto('A1'),menu('Format','Column','Width...'),fill('Column width in pixels:',200),button('OK')]),
      step('fit','Set A2 to Long product description, then automatically fit column A to its contents.',
           'The full product description is visible within the automatically resized column.',
           [set_(A2='Long product description'),goto('A1'),menu('Format','Column','Auto Fit Width')])
    ])
    add('row-height','structure',[
      step('height','Set row 2 to a height of 48 pixels.','The Tea row is visibly taller than its neighbors.',
           [goto('A2'),menu('Format','Row','Height...'),fill('Row height in pixels:',48),button('OK')]),
      step('fit','Automatically fit row 2 to its contents.','The row height adjusts to fit its text.',
           [goto('A2'),menu('Format','Row','Auto Fit Height')],depends=['height'])
    ])
    add('goal-seek','analysis',[
      step('solve','Use Goal Seek to make E2 equal 70 by changing C2. Keep the result. Save as {outbox}/goal.gnumeric.',
           'The Tea units value changes so its calculated revenue reaches the requested target.',
           [goto('E2'),menu('Tools','Goal Seek...'),fill('Set Cell:','E2'),fill('To Value:',70),fill('By Changing Cell:','C2'),button('Apply'),button('Close'),save('goal.gnumeric')],
           [values('goal.gnumeric','Sales',C2=20,E2=70)]),
      step('edit','Change the Tea price in D2 to 4. Save as {outbox}/after-goal.gnumeric.',
           'The revenue recalculates from the retained units value and the new price.',
           [set_(D2=4),save('after-goal.gnumeric')],[values('after-goal.gnumeric','Sales',C2=20,E2=80)],depends=['solve'])
    ])
    add('import-csv','import',[
      step('open','Open {inbox}/import.csv, completing its text-import dialog if shown. Automatically fit column A so its complete text is visible. Save as {outbox}/imported.gnumeric.',
           'The imported table has three columns; the quoted comma and quote characters remain within their name cells.',
           [{'op':'open','file':'import.csv'},goto('A1'),menu('Format','Column','Auto Fit Width'),save('imported.gnumeric')]),
      step('calculate','Enter =B2*C2 in D2 and =B3*C3 in D3. Save as {outbox}/calculated.gnumeric.',
           'The imported quantities and prices can be used in numeric calculations.',
           [set_(D2='=B2*C2',D3='=B3*C3'),save('calculated.gnumeric')],depends=['open'])
    ],input=None)
    w[-1]['setup']=[{'id':'inputs','op':'upload','files':['import.csv']}]
    for cp in w[-1]['checkpoints']:cp['depends_on'].append('setup:inputs')
    w[-1]['inputs']['documents']={'import.csv':w[-1]['inputs']['input_folder']+'/import.csv'}
    return w
