"""Sheet lifecycle, workbook-local navigation and authored image objects."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill,values


def build():
    out=[episode('sheet-management','sheet-management',[
      step('order','Move South before North using sheet management. Save as {outbox}/reordered.gnumeric.',
           'South appears before North while the Summary sheet remains.',
           [menu('Edit','Sheet','Manage Sheets...'),choose('South'),button('Up'),button('Close'),save('reordered.gnumeric')],
           [{'kind':'sheets','file':'reordered.gnumeric','expected':{'names':['South','North','Summary']},'description':'The saved sheet order changes as requested.'}]),
      step('delete','Remove South and save as {outbox}/removed.gnumeric. Show Summary.',
           'South is removed, and Summary reports that its former cross-sheet reference is unavailable.',
           [choose('South'),menu('Edit','Sheet','Remove'),save('removed.gnumeric'),choose('Summary')],
           [{'kind':'sheets','file':'removed.gnumeric','expected':{'names':['North','Summary']},'description':'The removed sheet is absent from the saved workbook.'}],depends=['order']),
      step('restore','Undo removing South, then save as {outbox}/restored.gnumeric. Show Summary.',
           'South and the combined total are restored.',
           [key('Control+Z'),save('restored.gnumeric'),choose('Summary')],
           [values('restored.gnumeric','Summary',B1=70)],depends=['delete']),
      step('hide','Hide South without deleting it, then save as {outbox}/hidden.gnumeric.',
           'South disappears from the visible sheet tabs while Summary still calculates its combined total.',
           [{'op':'sheet-visibility','sheet':'South','visible':False},save('hidden.gnumeric')],
           [{'kind':'sheet-attribute','file':'hidden.gnumeric','sheet':'South','attribute':'Visibility','expected':{'value':'GNM_SHEET_VISIBILITY_HIDDEN'},'description':'South is saved as hidden, with its contents retained.'},values('hidden.gnumeric','Summary',B1=70)],depends=['restore']),
      step('show','Make South visible again and save as {outbox}/shown.gnumeric.',
           'South returns to the visible sheet tabs.',[{'op':'sheet-visibility','sheet':'South','visible':True},save('shown.gnumeric')],
           [{'kind':'sheet-attribute','file':'shown.gnumeric','sheet':'South','attribute':'Visibility','expected':{'value':'GNM_SHEET_VISIBILITY_VISIBLE'},'description':'South is visible again in the saved workbook.'}],depends=['hide'])
    ],inputs=['multi.gnumeric'],opened='multi.gnumeric')]
    out.append(episode('internal-hyperlink','internal-navigation',[
      step('link','Enter Jump to total in North!D1, attach an Internal Link to Summary!B1, and follow it. Save as {outbox}/linked.gnumeric.',
           'Following the link activates Summary and selects its combined total.',
           [set_(D1='Jump to total'),goto('D1'),menu('Insert','Hyperlink...'),{'op':'combo','label':'Type:','value':'Internal Link'},fill('Target Range:','Summary!B1'),button('OK'),goto('A1'),{'op':'click','x':480,'y':224},save('linked.gnumeric')],
           [values('linked.gnumeric','Summary',B1=70)]),
      step('reopen','The application has restarted. Open {outbox}/linked.gnumeric, switch to North and follow Jump to total again.',
           'The saved link still navigates to the Summary total.',
           [{'op':'open','file':'linked.gnumeric','area':'outbox'},choose('North'),goto('A1'),{'op':'click','x':480,'y':224}],depends=['link'],lifecycle='restart')
    ],inputs=['multi.gnumeric'],opened='multi.gnumeric'))
    out.append(episode('image-object','image-objects',[
      step('insert','Insert {inbox}/badge.png into an empty area to the right of the table, at approximately twice its original width and height. Save as {outbox}/with-image.gnumeric.',
           'The blue-and-gold image appears alongside the worksheet data.',
           [menu('Insert','Image...'),key('Control+L'),{'op':'type','value':'{inbox}/badge.png'},key('Return'),{'op':'drag','x':500,'y':300,'to_x':820,'to_y':460},key('Escape'),save('with-image.gnumeric')],
           [{'kind':'objects','file':'with-image.gnumeric','sheet':'Data','expected':{'objects':['SheetObjectImage']},'description':'The saved workbook contains an embedded image object.'}]),
      step('reopen','The application has restarted. Open {outbox}/with-image.gnumeric.',
           'The image remains visible beside the data after reopening.',
           [{'op':'open','file':'with-image.gnumeric','area':'outbox'}],depends=['insert'],lifecycle='restart')
    ],inputs=['series.gnumeric','badge.png'],opened='series.gnumeric'))
    # Recipe paths use the same public exchange folders as goals.
    for w in out:
        for cp in w['checkpoints']:
            for action in cp['recipe']:
                if action.get('op')=='type':action['value']=action['value'].replace('{inbox}',w['inputs']['input_folder'])
    return out
