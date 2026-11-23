"""Charts and drawing objects are ordinary sheet objects, saved in the workbook."""
from gui import episode,step,key,goto,set_,menu,save,button,choose


def build():
    out=[]
    for id,type_,description in [('scatter','XY','scatter plot of Sales against Index'),
                                 ('column','Column','column chart of the six Sales observations in row order'),
                                 ('line','Line','line chart of the six Sales observations in row order'),
                                 ('pie','Pie','pie chart of the six Sales observations')]:
        source_range='A1:B7' if id=='scatter' else 'B1:B7'
        out.append(episode('chart-'+id,'charts',[
          step('insert','Select '+source_range+' and create a '+description+'. Place it in an empty area to the right of the data. Save as {outbox}/chart.gnumeric.',
               'A '+description+' is visible alongside the source table.',
               [goto(source_range),menu('Insert','Chart...'),choose(type_),button('Insert'),
                {'op':'drag','x':400,'y':250,'to_x':1000,'to_y':650},key('Escape'),save('chart.gnumeric')],
               [{'kind':'objects','file':'chart.gnumeric','sheet':'Data','description':'The saved workbook contains one chart object.','expected':{'objects':['SheetObjectGraph']}}]),
          step('update','Change the first Sales observation in B2 to 30. Save as {outbox}/updated-chart.gnumeric.',
               'The chart changes to reflect the revised first Sales value.',
               [set_(B2=30),save('updated-chart.gnumeric')],depends=['insert'])
        ],inputs=['series.gnumeric'],opened='series.gnumeric'))
    out.append(episode('drawing-objects','objects',[
      step('rectangle','Draw a rectangle in the blank area to the right of the data. Save as {outbox}/rectangle.gnumeric.',
           'A rectangular drawing object is visible beside the table.',
           [button('Rectangle'),{'op':'drag','x':500,'y':280,'to_x':800,'to_y':430},key('Escape'),save('rectangle.gnumeric')]),
      step('ellipse','Draw an ellipse below the rectangle. Save as {outbox}/ellipse.gnumeric.',
           'A new ellipse appears below the existing rectangle.',
           [button('Ellipse'),{'op':'drag','x':500,'y':480,'to_x':800,'to_y':650},key('Escape'),save('ellipse.gnumeric')],depends=['rectangle']),
      step('undo','Undo the ellipse insertion. Save as {outbox}/undo-object.gnumeric.',
           'The ellipse is removed and the rectangle remains.',
           [key('Control+Z'),save('undo-object.gnumeric')],depends=['ellipse']),
      step('arrow','Draw an arrow to the right of the rectangle. Save as {outbox}/arrow.gnumeric.',
           'An arrow object appears beside the retained rectangle.',
           [button('Arrow'),{'op':'drag','x':850,'y':300,'to_x':1100,'to_y':450},key('Escape'),save('arrow.gnumeric')],depends=['rectangle'])
    ],inputs=['series.gnumeric'],opened='series.gnumeric'))
    return out
