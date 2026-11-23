"""Cell formatting dialogs and authored annotations."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill,values,formulas,style


def build():
    out=[]
    def add(id,steps):out.append(episode(id,'cell-formatting',steps,inputs=['ledger.gnumeric'],opened='ledger.gnumeric'))
    fmt=[menu('Format','Cells','Format...')]
    add('custom-number-format',[
      step('fixed','Format D2:D7 using the custom number format 0.000. Save as {outbox}/fixed.gnumeric.',
           'Every unit price is displayed with three digits after the decimal point.',
           [goto('D2:D7'),*fmt,choose('Custom'),fill('Format code:','0.000'),button('OK'),save('fixed.gnumeric')],
           [style('fixed.gnumeric','Sales','D2','Format','0.000')]),
      step('currency','Format E2:E8 using the custom number format "$"#,##0.00. Save as {outbox}/currency.gnumeric.',
           'Revenue values display a dollar sign and two decimal places.',
           [goto('E2:E8'),*fmt,choose('Custom'),fill('Format code:','"$"#,##0.00'),button('OK'),save('currency.gnumeric')]),
      step('date','Enter =DATE(2024,2,29) in G2 and format it with yyyy-mm-dd. Save as {outbox}/date.gnumeric.',
           'G2 shows the requested leap-day date in year-month-day form.',
           [set_(G2='=DATE(2024,2,29)'),goto('G2'),*fmt,choose('Custom'),fill('Format code:','yyyy-mm-dd'),button('OK'),save('date.gnumeric')],
           [style('date.gnumeric','Sales','G2','Format','yyyy-mm-dd')]),
    ])
    add('wrap-rotation-font',[
      step('wrap','Enter A long product description that wraps across lines in A2, enable Wrap text for A2 and automatically fit row 2. Save as {outbox}/wrapped.gnumeric.',
           'The long description wraps over multiple lines within A2, with sufficient row height to show it.',
           [set_(A2='A long product description that wraps across lines'),goto('A2'),*fmt,choose('Alignment'),
            {'op':'check','name':'Wrap text','checked':True},button('OK'),menu('Format','Row','Auto Fit Height'),save('wrapped.gnumeric')],
           [style('wrapped.gnumeric','Sales','A2','WrapText','1')]),
      step('rotate','Rotate the text in A1:E1 to an angle of 45 degrees and make row 1 tall enough to display it. Save as {outbox}/rotated.gnumeric.',
           'The column header text is visibly diagonal.',
           [goto('A1:E1'),*fmt,choose('Alignment'),fill('Angle:',45),button('OK'),menu('Format','Row','Auto Fit Height'),save('rotated.gnumeric')],
           [style('rotated.gnumeric','Sales','A1','Rotation','45')]),
      step('font','Set A8 to font size 18. Save as {outbox}/font.gnumeric.',
           'The Total label is visibly larger than ordinary cell text.',
           [goto('A8'),*fmt,choose('Font'),fill('Size:',18),button('OK'),save('font.gnumeric')],
           [style('font.gnumeric','Sales','A8','font:Unit','18')]),
    ])
    add('cell-comments',[
      step('comment','Attach the comment Review the North region forecast to cell A2, using Analyst as the author. Save as {outbox}/commented.gnumeric, then show the saved comment.',
           'The saved comment shows the requested text and authored identity.',
           [goto('A2'),menu('Insert','Comment...'),fill('New Author:','Analyst'),fill(None,'Review the North region forecast',index=1),button('OK'),save('commented.gnumeric'),goto('A2'),menu('Insert','Comment...')],
           [{'kind':'comment','file':'commented.gnumeric','sheet':'Sales','cell':'A2','expected':{'author':'Analyst','text':'Review the North region forecast'},'description':'A2 retains the authored comment in the saved workbook.'}]),
      step('edit','Change the A2 comment to Approved for the regional report and its author to Editor. Save as {outbox}/edited-comment.gnumeric, then show the saved comment.',
           'The saved comment displays the replacement text and author.',
           [fill('New Author:','Editor'),fill(None,'Approved for the regional report',index=1),button('OK'),save('edited-comment.gnumeric'),goto('A2'),menu('Insert','Comment...')],
           [{'kind':'comment','file':'edited-comment.gnumeric','sheet':'Sales','cell':'A2','expected':{'author':'Editor','text':'Approved for the regional report'},'description':'Editing a comment replaces its saved text and author.'}],depends=['comment']),
      step('remove','Move the comment Approved for the regional report, authored by Editor, from A2 to B2 while retaining both cell contents. Save as {outbox}/relocated-comment.gnumeric, then show the saved B2 comment.',
           'B2 has the relocated comment with its text and author.',
           [button('Cancel'),goto('B3'),goto('A2'),menu('Edit','Clear','Comments'),goto('B2'),menu('Insert','Comment...'),fill('New Author:','Editor'),fill(None,'Approved for the regional report',index=1),button('OK'),save('relocated-comment.gnumeric'),goto('B2'),menu('Insert','Comment...')],
           [{'kind':'comment','file':'relocated-comment.gnumeric','sheet':'Sales','cell':'A2','expected':{'present':False},'description':'The saved comment is removed from its old cell.'},
            {'kind':'comment','file':'relocated-comment.gnumeric','sheet':'Sales','cell':'B2','expected':{'author':'Editor','text':'Approved for the regional report'},'description':'The relocated comment is saved at B2.'},values('relocated-comment.gnumeric','Sales',A2='Tea',B2='North')],depends=['edit'])
    ])
    add('format-clear',[
      step('style','Make A1:E1 bold and italic, then save as {outbox}/styled.gnumeric.',
           'The headers are visibly bold and italic.',
           [goto('A1:E1'),button('Bold'),button('Italic'),save('styled.gnumeric')],
           [style('styled.gnumeric','Sales','A1','font:Bold','1'),style('styled.gnumeric','Sales','A1','font:Italic','1')]),
      step('clear','Clear formats from A1:E1 while retaining the cell contents. Save as {outbox}/plain.gnumeric.',
           'The headers return to plain cell text, with all five labels preserved.',
           [goto('A1:E1'),menu('Edit','Clear','Formats & Hyperlinks'),save('plain.gnumeric')],
           [values('plain.gnumeric','Sales',A1='Product',E1='Revenue'),style('plain.gnumeric','Sales','A1','font:Bold','0')],depends=['style']),
    ])
    return out
