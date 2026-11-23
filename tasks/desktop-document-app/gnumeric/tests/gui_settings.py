"""Document properties, preferences, printing configuration and lifecycle."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill,values,formulas


def build():
    out=[]
    def add(id,feature,steps,input='ledger.gnumeric'):
        out.append(episode(id,feature,steps,inputs=[input] if input else [],opened=input))
    properties={'kind':'metadata','file':'properties.gnumeric','fields':['title','subject','initial-creator','description'],
                'expected':{'fields':{'title':'Regional sales','subject':'Quarterly planning','initial-creator':'Zoë Chen','description':'Reviewed for publication'}},
                'description':'The saved workbook retains the four authored description properties.'}
    add('document-properties','metadata',[
      step('set','Set the document Title to Regional sales, Subject to Quarterly planning, Author to Zoë Chen and Comments to Reviewed for publication. Save as {outbox}/properties.gnumeric. Reopen the description properties and leave them visible.',
           'The description properties display all four authored values.',
           [menu('File','Document Properties...'),choose('Description'),fill('Title:','Regional sales'),fill('Subject:','Quarterly planning'),
            fill('Author:','Zoë Chen'),fill('Comments:','Reviewed for publication'),button('Close'),save('properties.gnumeric'),
            menu('File','Document Properties...'),choose('Description')],[properties]),
      step('persist','The application has restarted. Open {outbox}/properties.gnumeric and show its description properties.',
           'The authored title, subject, author and comments remain after reopening.',
           [{'op':'open','file':'properties.gnumeric','area':'outbox'},menu('File','Document Properties...'),choose('Description')],depends=['set'],lifecycle='restart')
    ])
    add('default-preferences','preferences',[
      step('set','In Preferences set the default number of sheets to 3 and the default zoom factor to 1.25. Close Preferences and create a new workbook.',
           'The new workbook contains three sheets and uses the increased default zoom.',
           [menu('Edit','Preferences...'),choose('Windows'),fill('Default Number of Sheets',3),fill('Default Zoom Factor',1.25),button('Close'),key('Control+N')]),
      step('quit','Quit the application normally so that the changed preferences are saved.',
           'The application exits after using the requested default settings.',[key('Control+Q')],[{'kind':'lifecycle','expected':{'running':False},'description':'The application process exits normally before its preferences are reopened.'}],depends=['set']),
      step('persist','The application has restarted. Inspect its new workbook, then open the Windows preferences and leave them visible.',
           ['The new workbook still has three sheets.','Preferences retain the requested sheet count and zoom factor.'],
           [menu('Edit','Preferences...'),choose('Windows')],depends=['quit'],lifecycle='restart')
    ],input=None)
    add('manual-recalculation','calculation',[
      step('manual','Set workbook recalculation to Manual. Close properties, enter =RAND() in G2 and save as {outbox}/manual.gnumeric. Leave G2 selected.',
           'G2 displays a numeric random sample between zero and one.',
           [menu('File','Document Properties...'),choose('Calculation'),choose('Manual'),button('Close'),set_(G2='=RAND()'),save('manual.gnumeric'),goto('G2')],
           [{'kind':'calculation-setting','file':'manual.gnumeric','attribute':'ManualRecalc','expected':{'value':'1'},'description':'The saved workbook is configured for manual recalculation.'},formulas('manual.gnumeric','Sales',G2='=RAND()')]),
      step('calculate','Use the Recalculate command and leave G2 visible.',
           'G2 displays a newly calculated random sample, different from its previous value.',[menu('Edit','Recalculate'),goto('G2')],depends=['manual']),
      step('automatic','Switch workbook recalculation back to Automatic, then change C2 to 10.',
           'The Revenue formula updates immediately when the input changes.',
           [menu('File','Document Properties...'),choose('Calculation'),choose('Automatic'),button('Close'),set_(C2=10)],depends=['calculate'])
    ])
    add('page-setup','printing',[
      step('landscape','Set the current sheet to landscape orientation and enable horizontal centering on the printed page. Confirm and save as {outbox}/landscape.gnumeric. Reopen Page Setup.',
           'Page Setup shows landscape orientation and horizontal centering enabled.',
           [menu('File','Page Setup...'),choose('Landscape'),{'op':'check','name':'Horizontally','checked':True},button('OK'),save('landscape.gnumeric'),menu('File','Page Setup...')]),
      step('grid','In Page Setup enable printing grid lines and row/column headings on the Sheet tab. Confirm, save as {outbox}/print-grid.gnumeric, then reopen Page Setup on its Sheet tab.',
           'The print settings show grid lines and row/column headings enabled.',
           [choose('Sheet'),{'op':'check','name':'Grid lines','checked':True},{'op':'check','name':'Row and column headings','checked':True},button('OK'),save('print-grid.gnumeric'),menu('File','Page Setup...'),choose('Sheet')],depends=['landscape'])
    ])
    add('input-error-recovery','input-errors',[
      step('bad','Try to open {inbox}/invalid.gnumeric. If an import-format dialog appears, cancel it. Leave any file-error message visible.',
           'The application reports that the selected file cannot be opened as the requested workbook.',
           [{'op':'open','file':'invalid.gnumeric'}]),
      step('recover','Dismiss the error, then open {inbox}/ledger.gnumeric.',
           'The valid Sales workbook opens and shows its data and calculated revenues.',
           [button('Close'),{'op':'open','file':'ledger.gnumeric'}])
    ],input=None)
    out[-1]['setup']=[{'id':'inputs','op':'upload','files':['invalid.gnumeric','ledger.gnumeric']}]
    for cp in out[-1]['checkpoints']:cp['depends_on'].append('setup:inputs')
    out[-1]['inputs']['documents']={n:out[-1]['inputs']['input_folder']+'/'+n for n in ('invalid.gnumeric','ledger.gnumeric')}
    return out
