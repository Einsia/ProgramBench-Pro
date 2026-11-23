"""Authored chart annotations, axis settings and native image export."""
from gui import episode,step,key,goto,set_,menu,save,button,choose,fill


def edit():return [{'op':'click','x':700,'y':400,'click_count':2}]


def build():
    exports=[{'kind':'chart-export','file':'chart-edited.gnumeric','format':fmt,'title':'Sales outlook',
              'description':'Native graph export creates a nonempty '+fmt.upper()+' document.',
              'expected':{'format':fmt,'nonempty_plot':True}} for fmt in ('svg','png','pdf')]
    return [episode('chart-edit-export','chart-editing',[
      step('create','Create a column chart from B1:B7 and place it to the right of the data. Set its vertical axis maximum to 60 with minimum 0. Save as {outbox}/chart-axis.gnumeric.',
           'The column chart uses a vertical scale extending to the requested maximum.',
           [goto('B1:B7'),menu('Insert','Chart...'),choose('Column'),button('Insert'),{'op':'drag','x':400,'y':250,'to_x':1000,'to_y':650},key('Escape'),*edit(),choose('Y-Axis1'),{'op':'check','name':'Maximum:','checked':False},fill(None,60,index=2),key('Tab'),button('Apply'),save('chart-axis.gnumeric')]),
      step('label','Give the chart the title Sales outlook and add a legend identifying its Sales series. Save as {outbox}/chart-edited.gnumeric.',
           'The chart displays the authored title and a legend naming the plotted series.',
           [*edit(),choose('Chart1'),button('Add'),{'op':'click','target':{'role':'menu item','name':'Title to Chart1'}},fill('Text:','"Sales outlook"'),key('Tab'),button('Apply'),*edit(),choose('Chart1'),button('Add'),{'op':'click','target':{'role':'menu item','name':'Legend to Chart1'}},button('Apply'),save('chart-edited.gnumeric')],exports,depends=['create']),
      step('reopen','The application has restarted. Open {outbox}/chart-edited.gnumeric.',
           'The saved chart retains its title, legend and axis scale after reopening.',
           [{'op':'open','file':'chart-edited.gnumeric','area':'outbox'}],depends=['label'],lifecycle='restart')
    ],inputs=['series.gnumeric'],opened='series.gnumeric')]
