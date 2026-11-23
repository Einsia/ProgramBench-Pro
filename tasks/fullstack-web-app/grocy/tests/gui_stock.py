"""Stock mutations and public inventory views operated through ordinary visible controls."""
from specification import api,read,step
from gui_common import base,product,stock,go,button,fill,select,tick
from gui_master import field


def choose_product(name='Rice'):
    return {'op':'choose','value':name,'target':{'tag':'input','type':'text','nth':0}}


def amount(value):return fill('display_amount',str(value))


def detail(expected):
    return read('stock/products/{{product.created_object_id}}',fields=list(expected),expected=expected)


def build(add):
    setup=base()+[product()]
    add('gui-stock-purchase','stock purchase',setup,[
      step('purchase','Purchase 4 Items of Rice for a unit price of 2.50, due 2026-04-01, into Pantry. Show the saved stock.',
           'Rice is visibly in stock with amount 4 Items and due date 2026-04-01.',
           [go('/purchase'),choose_product(),amount(4),{'op':'fill','target':{'tag':'input','type':'text','nth':1},'value':'2026-04-01'},
            fill('price','2.50'),button('OK'),go('/stockoverview')],
           checks=[detail({'stock_amount':4,'next_due_date':'2026-04-01','last_price':2.5})],visible=['Rice','4 Items','2026-04-01']),
      step('second-purchase','Purchase another 2 Items of Rice for a unit price of 3.00, due 2026-05-01. Show the individual stock entries.',
           'The stock entries visibly distinguish the first purchase of 4 Items and the later purchase of 2 Items with their due dates.',
           [go('/purchase'),choose_product(),amount(2),{'op':'fill','target':{'tag':'input','type':'text','nth':1},'value':'2026-05-01'},
            fill('price','3.00'),button('OK'),go('/stockentries')],
           checks=[detail({'stock_amount':6}),read('stock/products/{{product.created_object_id}}/entries',fields=['amount','price','best_before_date'],collection=True,expected=[{'amount':4,'price':2.5,'best_before_date':'2026-04-01'},{'amount':2,'price':3,'best_before_date':'2026-05-01'}])],visible=['Rice','2026-04-01','2026-05-01'],depends=['purchase']),
      step('journal','Show the stock journal for Rice so its two purchases can be inspected.',
           'The journal visibly shows both Rice purchase bookings and their amounts.',
           [go('/stockjournal')],checks=[read('objects/stock_log',fields=['amount','transaction_type'],collection=True,
              expected=[{'amount':4,'transaction_type':'purchase'},{'amount':2,'transaction_type':'purchase'}])],visible=['Rice','Purchase'],depends=['second-purchase']),
    ])
    setup=base()+[product(),stock()]
    add('gui-stock-consume','stock consumption and opening',setup,[
      step('open','Mark 2 Items of Rice as opened, then show its inventory state.',
           'Rice visibly has 2 opened Items while its total stock remains 8 Items.',
           [go('/consume'),choose_product(),amount(2),button('Mark as opened'),go('/stockoverview')],
           checks=[detail({'stock_amount':8,'stock_amount_opened':2})],visible=['Rice'],),
      step('consume','Consume 1 Item of Rice, then show the remaining stock.',
           'The remaining Rice stock is visibly 7 Items.',
           [go('/consume'),choose_product(),amount(1),button('OK'),go('/stockoverview')],
           checks=[detail({'stock_amount':7,'stock_amount_opened':1})],visible=['Rice','7 Items'],depends=['open']),
      step('spoil','Record 1 Item of Rice as consumed because it spoiled. Show this booking in the stock journal.',
           'The journal visibly identifies the Rice consumption as spoiled.',
           [go('/consume'),choose_product(),amount(1),tick('spoiled'),button('OK'),go('/stockjournal')],
           checks=[read('objects/stock_log',fields=['amount','spoiled'],where={'spoiled':1},expected={'amount':-1,'spoiled':1})],visible=['Rice','Spoiled'],depends=['consume']),
      step('undo','Undo the most recent Rice consumption booking, restoring that Item to stock. Show the stock overview.',
           'Rice stock is visibly restored to 7 Items.',
           [go('/stockjournal'),{'op':'click','target':{'title':'Undo transaction','nth':0}},go('/stockoverview')],
           checks=[detail({'stock_amount':7})],visible=['Rice','7 Items'],depends=['spoil']),
    ])
    add('gui-stock-transfer','stock transfer',setup,[
      step('transfer','Transfer 3 Items of Rice from Pantry to Freezer. Show the stock entries.',
           'Rice stock is visibly split between Pantry and Freezer, including 3 Items in Freezer.',
           [go('/transfer'),choose_product(),select('location_id_from','Pantry'),amount(3),select('location_id_to','Freezer'),button('OK'),go('/stockentries')],
           checks=[read('stock/products/{{product.created_object_id}}/locations',fields=['location_id','amount'],collection=True,
             expected=[{'location_id':'{{pantry.created_object_id}}','amount':5},{'location_id':'{{freezer.created_object_id}}','amount':3}])],visible=['Rice','Pantry','Freezer']),
      step('location-view','Show only Rice stock held in Freezer.',
           'The stock entries visibly show only Rice in Freezer, totaling 3 Items, with no Pantry entries.',
           [go('/stockentries'),{'op':'select','target':{'tag':'select','nth':0},'value':'Freezer'}],
           checks=[],visible=['Rice','3 Items','Freezer'],depends=['transfer']),
      step('return','Transfer 1 Item of Rice back from Freezer to Pantry. Show the stock entries.',
           'The stock entries visibly show 2 Items in Freezer and 6 Items in Pantry.',
           [go('/transfer'),choose_product(),select('location_id_from','Freezer'),amount(1),select('location_id_to','Pantry'),button('OK'),go('/stockentries')],
           checks=[read('stock/products/{{product.created_object_id}}/locations',fields=['location_id','amount'],collection=True,
             expected=[{'location_id':'{{pantry.created_object_id}}','amount':6},{'location_id':'{{freezer.created_object_id}}','amount':2}])],visible=['Rice','Pantry','Freezer'],depends=['transfer']),
    ])
    add('gui-stock-inventory','stock inventory correction',setup,[
      step('increase','Set the counted stock of Rice to 10 Items; use due date 2026-05-01 and unit price 3.00 for the added stock. Show the stock overview.',
           'The inventory visibly contains 10 Items of Rice.',
           [go('/inventory'),choose_product(),amount(10),{'op':'fill','target':{'tag':'input','type':'text','nth':1},'value':'2026-05-01'},fill('price','3'),button('OK'),go('/stockoverview')],
           checks=[detail({'stock_amount':10})],visible=['Rice','10 Items']),
      step('decrease','Correct the counted stock of Rice down to 5 Items and show the stock overview.',
           'The inventory visibly contains 5 Items of Rice.',
           [go('/inventory'),choose_product(),amount(5),button('OK'),go('/stockoverview')],
           checks=[detail({'stock_amount':5})],visible=['Rice','5 Items'],depends=['increase']),
      step('report','Show the stock journal so the inventory corrections for Rice can be inspected.',
           'The journal visibly distinguishes the two inventory corrections and their amounts.',
           [go('/stockjournal')],checks=[read('objects/stock_log',fields=['amount','transaction_type'],params={'query[]':'transaction_type=inventory-correction'},collection=True,
             expected=[{'amount':2,'transaction_type':'inventory-correction'},{'amount':-5,'transaction_type':'inventory-correction'}])],visible=['Rice','Inventory correction'],depends=['decrease']),
    ])
    add('gui-product','product master data',base(),[
      step('create','Create product "Oats" using Pantry and Item for stock and purchase units, minimum stock 3, and default due days 14. Save it.',
           'Oats is visible as a saved product with its stock unit and default location.',
           [go('/product/new'),{'op':'form','fields':[field('name','Oats'),field('location_id','Pantry','select'),
             field('qu_id_purchase','Item','select'),field('qu_id_stock','Item','select'),field('min_stock_amount','3'),field('default_best_before_days','14')]},
            button('Save & return to products'),{'op':'save-named','entity':'products','name':'Oats','save':'created'},go('/products')],
           checks=[read('objects/products',fields=['name','location_id','qu_id_stock','min_stock_amount','default_best_before_days'],where={'name':'Oats'},
              expected={'name':'Oats','location_id':'{{pantry.created_object_id}}','qu_id_stock':'{{unit.created_object_id}}','min_stock_amount':3,'default_best_before_days':14},save='created')],visible=['Oats']),
      step('edit','Change Oats to minimum stock 5 and default due days 30. Save and show its saved product details.',
           'The saved Oats details visibly show minimum stock 5 and default due days 30.',
           [{'op':'edit-named','entity':'products','name':'Oats','prefix':'/product'},fill('min_stock_amount','5'),fill('default_best_before_days','30'),
            button('Save & return to products'),{'op':'edit-named','entity':'products','name':'Oats','prefix':'/product'}],
           checks=[read('objects/products',fields=['min_stock_amount','default_best_before_days'],where={'name':'Oats'},expected={'min_stock_amount':5,'default_best_before_days':30})],depends=['create']),
      step('below-minimum','Show the stock overview for Oats so its replenishment need can be inspected.',
           'Oats is visibly below its minimum stock amount.',
           [go('/stockoverview')],checks=[],visible=['Oats'],depends=['edit']),
    ])
