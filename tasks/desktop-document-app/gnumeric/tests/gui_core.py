"""Editing, workbook structure, formatting, sorting and view episodes."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill,values,formulas,style


def build():
    w=[]
    def add(id,feature,steps,input='ledger.gnumeric'):
        w.append(episode(id,feature,steps,inputs=[input] if input else [],opened=input))
    add('edit-history','history',[
      step('change','Change C2 to 20, then save as {outbox}/changed.gnumeric.','The Tea row shows 20 units and its revenue updates.',
           [set_(C2=20),save('changed.gnumeric')],[values('changed.gnumeric','Sales',C2=20,E2=70)]),
      step('undo','Use the real Undo command to undo the C2 edit, then save as {outbox}/undone.gnumeric.','The previous Tea units and revenue are restored.',
           [key('Control+Z'),save('undone.gnumeric')],[values('undone.gnumeric','Sales',C2=8,E2=28)],depends=['change']),
      step('redo','Use the real Redo command to reapply the edit, then save as {outbox}/redone.gnumeric.','The Tea row again shows 20 units and the updated revenue.',
           [key('Control+Y'),save('redone.gnumeric')],[values('redone.gnumeric','Sales',C2=20,E2=70)],depends=['undo']),
    ])
    add('clear-cells','editing',[
      step('clear','Clear only the contents of A2:B3. Save as {outbox}/cleared.gnumeric.','The two selected product names and regions are empty; their numeric columns remain.',
           [goto('A2:B3'),menu('Edit','Clear','Contents'),save('cleared.gnumeric')],[values('cleared.gnumeric','Sales',A2=None,B3=None,C2=8,C3=5)]),
      step('restore','Undo the clearing and save as {outbox}/restored.gnumeric.','The cleared names and regions return in their original positions.',
           [key('Control+Z'),save('restored.gnumeric')],[values('restored.gnumeric','Sales',A2='Tea',B3='South')],depends=['clear'])
    ])
    add('fill-formulas','formulas',[
      step('down','Put =C2*D2 in F2 and use Fill Downwards to fill F2:F7. Save as {outbox}/filled.gnumeric.',
           'F2:F7 contain row-by-row calculated revenue results.',
           [set_(F2='=C2*D2'),goto('F2:F7'),menu('Data','Fill','Fill Downwards'),save('filled.gnumeric')],
           [values('filled.gnumeric','Sales',F2=28,F3=30,F7=20),formulas('filled.gnumeric','Sales',F2='=C2*D2',F3='=C3*D3',F7='=C7*D7')]),
      step('absolute','Enter 1.2 in H1 and =E2*$H$1 in G2. Fill G2:G7 downwards and save as {outbox}/absolute.gnumeric.',
           'G2:G7 show revenue scaled using the single value in H1.',
           [set_(H1=1.2,G2='=E2*$H$1'),goto('G2:G7'),menu('Data','Fill','Fill Downwards'),save('absolute.gnumeric')],
           [values('absolute.gnumeric','Sales',G2=33.6,G3=36,G7=24),formulas('absolute.gnumeric','Sales',G3='=E3*$H$1',G7='=E7*$H$1')]),
      step('right','Enter =SUM(C2:C7) in H3 and use Fill to Right across H3:J3. Save as {outbox}/right.gnumeric.',
           'Three adjacent cells show totals calculated from successive source columns.',
           [set_(H3='=SUM(C2:C7)'),goto('H3:J3'),menu('Data','Fill','Fill to Right'),save('right.gnumeric')],
           [values('right.gnumeric','Sales',H3=57,I3=19.5,J3=165.25),formulas('right.gnumeric','Sales',I3='=SUM(D2:D7)',J3='=SUM(E2:E7)')]),
    ])
    add('clipboard-ranges','clipboard',[
      step('copy','Copy A1:B4 and paste a copy starting at G1. Save as {outbox}/copied.gnumeric.',
           'The copied header and first three product/region pairs appear in G1:H4; the source is still present.',
           [goto('A1:B4'),key('Control+C'),goto('G1'),key('Control+V'),save('copied.gnumeric')],
           [values('copied.gnumeric','Sales',A2='Tea',G1='Product',G2='Tea',H4='North')]),
      step('cut','Cut G1:H4 and paste it starting at J1. Show G1:K4 together so both the old and new locations are visible. Save as {outbox}/moved.gnumeric.',
           'The copied block moves to J1:K4 and its former location is cleared.',
           [goto('G1:H4'),key('Control+X'),goto('J1'),key('Control+V'),goto('K4'),goto('G1:K4'),save('moved.gnumeric')],
           [values('moved.gnumeric','Sales',G1=None,H4=None,J1='Product',K4='North')],depends=['copy']),
      step('text','Copy A1:C3 to the clipboard.','The first three rows across columns A through C are selected for copying.',
           [goto('A1:C3'),key('Control+C')],[{'kind':'clipboard','description':'Clipboard contains the selected table as text.',
            'expected':{'text':'Product\tRegion\tUnits\nTea\tNorth\t8\nCoffee\tSouth\t5'}}])
    ])
    add('insert-delete-rows','structure',[
      step('insert','Insert one whole row before row 3. Save as {outbox}/inserted.gnumeric.',
           'A blank row separates Tea and Coffee; the rows below move down.',
           [goto('A3'),menu('Insert','Rows'),save('inserted.gnumeric')],[values('inserted.gnumeric','Sales',A2='Tea',A3=None,A4='Coffee',E9=165.25)]),
      step('delete','Delete whole row 5, which contains Cocoa. Save as {outbox}/deleted.gnumeric.',
           'Cocoa is removed and Juice follows Coffee; the previously inserted blank row remains.',
           [goto('A5'),menu('Edit','Delete','Rows'),save('deleted.gnumeric')],[values('deleted.gnumeric','Sales',A3=None,A4='Coffee',A5='Juice',E8=114.25)],depends=['insert']),
      step('undo','Undo the row deletion. Save as {outbox}/restored.gnumeric.',
           'The Cocoa row is restored between Coffee and Juice.',
           [key('Control+Z'),save('restored.gnumeric')],[values('restored.gnumeric','Sales',A5='Cocoa',E9=165.25)],depends=['delete'])
    ])
    add('insert-delete-columns','structure',[
      step('insert','Insert a whole column before column C. Save as {outbox}/inserted.gnumeric.',
           'A blank column appears between Region and Units, and the numeric columns shift right.',
           [goto('C1'),menu('Insert','Columns'),save('inserted.gnumeric')],[values('inserted.gnumeric','Sales',C1=None,D1='Units',F8=165.25)]),
      step('delete','Delete the whole Region column B. Save as {outbox}/deleted.gnumeric.',
           'The Region column disappears, while the inserted blank column remains before Units.',
           [goto('B1'),menu('Edit','Delete','Columns'),save('deleted.gnumeric')],[values('deleted.gnumeric','Sales',B1=None,C1='Units',E8=165.25)],depends=['insert'])
    ])
    add('text-emphasis','formatting',[
      step('bold','Make A1:E1 bold. Save as {outbox}/bold.gnumeric.','All five header labels are visibly emphasized with bold text.',
           [goto('A1:E1'),button('Bold'),save('bold.gnumeric')],[style('bold.gnumeric','Sales','A1','font:Bold','1'),style('bold.gnumeric','Sales','E1','font:Bold','1')]),
      step('italic','Make A2:A7 italic. Save as {outbox}/italic.gnumeric.','The product names below the header are italic.',
           [goto('A2:A7'),button('Italic'),save('italic.gnumeric')],[style('italic.gnumeric','Sales','A2','font:Italic','1')]),
      step('underline','Underline A8:E8. Save as {outbox}/underlined.gnumeric.','The total-row text and numbers are underlined.',
           [goto('A8:E8'),button('Underline'),save('underlined.gnumeric')],[style('underlined.gnumeric','Sales','A8','font:Underline','1')])
    ])
    add('numeric-toolbar','formatting',[
      step('percentage','Enter 0.125 in G2 and format that cell as a percentage. Save as {outbox}/percent.gnumeric.',
           'G2 displays the fraction using a percent sign.',
           [set_(G2=.125),goto('G2'),button('Percentage'),save('percent.gnumeric')],[values('percent.gnumeric','Sales',G2=.125)]),
      step('precision','Increase the displayed precision of G2 twice. Save as {outbox}/precision.gnumeric.',
           'The percentage in G2 is displayed with two more decimal places.',
           [goto('G2'),button('Increase Precision'),button('Increase Precision'),save('precision.gnumeric')],depends=['percentage']),
      step('thousands','Enter 12345.6 in G4 and apply a thousands-separator format. Save as {outbox}/thousands.gnumeric.',
           'G4 visibly groups the digits with a thousands separator.',
           [set_(G4=12345.6),goto('G4'),button('Thousands Separator'),save('thousands.gnumeric')],[values('thousands.gnumeric','Sales',G4=12345.6)])
    ])
    add('alignment','formatting',[
      step('center','Center the header cells A1:E1 horizontally. Save as {outbox}/centered.gnumeric.',
           'Each header is centered within its own cell.',[goto('A1:E1'),button('Center'),save('centered.gnumeric')],[style('centered.gnumeric','Sales','A1','HAlign','GNM_HALIGN_CENTER')]),
      step('right','Align A2:A7 to the right. Save as {outbox}/right.gnumeric.','The product names are aligned at the right edges of their cells.',
           [goto('A2:A7'),button('Right Align'),save('right.gnumeric')],[style('right.gnumeric','Sales','A2','HAlign','GNM_HALIGN_RIGHT')]),
      step('indent','Increase the indentation of B2:B7 twice. Save as {outbox}/indented.gnumeric.',
           'The region names are indented farther from their cell edges.',
           [goto('B2:B7'),button('Increase Indentation'),button('Increase Indentation'),save('indented.gnumeric')],[style('indented.gnumeric','Sales','B2','Indent','2')])
    ])
    add('merge-cells','formatting',[
      step('merge','Enter Quarterly report in G1 and merge G1:J1. Save as {outbox}/merged.gnumeric.',
           'A single wide cell containing Quarterly report spans columns G through J.',
           [set_(G1='Quarterly report'),goto('G1:J1'),button('Merge'),save('merged.gnumeric')],
           [{'kind':'merged','file':'merged.gnumeric','sheet':'Sales','expected':{'ranges':['G1:J1']},'description':'The saved workbook contains the requested merged range.'}]),
      step('unmerge','Unmerge the wide heading cell. Save as {outbox}/unmerged.gnumeric.',
           'Columns G through J are separate cells again, with the heading kept in G1.',
           [goto('G1:J1'),button('Unmerge'),save('unmerged.gnumeric')],
           [{'kind':'merged','file':'unmerged.gnumeric','sheet':'Sales','expected':{'ranges':[]},'description':'The merged range is removed.'},values('unmerged.gnumeric','Sales',G1='Quarterly report')],depends=['merge'])
    ])
    add('hide-rows-columns','structure',[
      step('rows','Hide rows 3 and 4.','The Coffee and Cocoa rows are hidden, with a gap in the visible row numbers.',
           [goto('A3:A4'),menu('Format','Row','Hide')]),
      step('show-rows','Unhide rows 3 and 4.','Coffee and Cocoa are visible again in their original rows.',
           [goto('A2:A5'),menu('Format','Row','Unhide')],depends=['rows']),
      step('columns','Hide column B.','The Region column is hidden, while Product and Units remain visible.',
           [goto('B1'),menu('Format','Column','Hide')]),
      step('show-columns','Unhide column B.','The Region column is visible again with its original values.',
           [goto('A1:C1'),menu('Format','Column','Unhide')],depends=['columns'])
    ])
    add('sort-rows','sorting',[
      step('ascending','Sort A2:E7 by Product in ascending order, keeping each row together. Save as {outbox}/ascending.gnumeric.',
           'Product rows appear in ascending alphabetical order and their corresponding data travels with them.',
           [goto('A2:E7'),button('Sort Ascending'),save('ascending.gnumeric')],
           [values('ascending.gnumeric','Sales',A2='Cocoa',C2=12,A3='Coffee',A7='Water',C7=15)]),
      step('descending','Sort A2:E7 by Product in descending order. Save as {outbox}/descending.gnumeric.',
           'Product rows appear in descending alphabetical order.',
           [goto('A2:E7'),button('Sort Descending'),save('descending.gnumeric')],
           [values('descending.gnumeric','Sales',A2='Water',A7='Cocoa',C7=12)]),
      step('undo','Undo the descending sort. Save as {outbox}/undone.gnumeric.',
           'The previous ascending order is restored.',[key('Control+Z'),save('undone.gnumeric')],
           [values('undone.gnumeric','Sales',A2='Cocoa',A7='Water')],depends=['descending'])
    ])
    add('sheet-formula-view','view',[
      step('formulas','Turn on display of formulas for the current sheet.',
           'Formula expressions are visible in the Revenue column and total row in place of their calculated values.',
           [menu('Format','Sheet','Display Formulæ')]),
      step('results','Return to displaying calculated values.',
           'The Revenue column and totals display numeric results again.',
           [menu('Format','Sheet','Display Formulæ')],depends=['formulas']),
      step('grid','Hide the sheet gridlines.','The data remains visible while the gridlines between cells disappear.',
           [menu('Format','Sheet','Hide Gridlines')])
    ])
    add('freeze-panes','view',[
      step('freeze','Select B2 and freeze panes, then navigate to A30.',
           'The header row remains visible while the lower pane shows later rows.',
           [goto('B2'),menu('View','Freeze Panes'),goto('A30')]),
      step('unfreeze','Unfreeze the panes and return to A1.',
           'The worksheet returns to a single scrolling area at its top-left data.',
           [menu('View','Unfreeze Panes'),goto('A1')],depends=['freeze'])
    ])
    add('sheet-rename','sheets',[
      step('rename','Rename the current North sheet to Forecast. Save as {outbox}/renamed.gnumeric.',
           'The active sheet tab is named Forecast.',
           [menu('Edit','Sheet','Rename...'),fill(None,'Forecast',index=0),button('OK'),save('renamed.gnumeric')],
           [{'kind':'sheets','file':'renamed.gnumeric','expected':{'names':['Forecast','South','Summary']},'description':'The workbook saves the changed sheet name.'}]),
      step('reference','Switch to Summary.','Summary still shows the combined result from the renamed sheet and South.',
           [choose('Summary')],[values('renamed.gnumeric','Summary',B1=70)],depends=['rename'])
    ],input='multi.gnumeric')
    add('sheet-duplicate','sheets',[
      step('duplicate','Duplicate the North sheet and name the duplicate North copy. Save as {outbox}/duplicated.gnumeric.',
           'A new worksheet containing the North data and formulas appears alongside the original.',
           [menu('Edit','Sheet','Duplicate'),choose('North(2)'),menu('Edit','Sheet','Rename...'),fill(None,'North copy',index=0),button('OK'),save('duplicated.gnumeric')],
           [values('duplicated.gnumeric','North copy',B2=12,B4=30)]),
      step('independent','Change B2 of the duplicated sheet to 100. Save as {outbox}/independent.gnumeric.',
           'The duplicated sheet displays the changed value and recalculated total.',
           [choose('North copy'),set_(B2=100),save('independent.gnumeric')],[values('independent.gnumeric','North copy',B2=100,B4=118)],depends=['duplicate']),
      step('original','Switch back to the original North sheet.','The original North sheet still has 12 in B2 and its original total.',
           [choose('North')],[values('independent.gnumeric','North',B2=12,B4=30)],depends=['independent'])
    ],input='multi.gnumeric')
    return w
