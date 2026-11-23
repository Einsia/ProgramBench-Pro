"""Known transactions distinguish report grouping, filters and journal summary arithmetic."""
from specification import api,step,read
from gui_common import base,product,go,button,fill


def build(add):
    setup=base()+[
      api('second-store','POST','objects/shopping_locations',{'name':'Farm shop'},save='farm'),
      api('grains','POST','objects/product_groups',{'name':'Grains'},save='grains'),
      api('fruit','POST','objects/product_groups',{'name':'Fruit'},save='fruit'),
      product('Rice','rice',product_group_id='{{grains.created_object_id}}'),
      product('Oats','oats',product_group_id='{{grains.created_object_id}}'),
      product('Apples','apples',product_group_id='{{fruit.created_object_id}}'),
      api('buy-rice','POST','stock/products/{{rice.created_object_id}}/add',{'amount':4,'price':2,'shopping_location_id':'{{store.created_object_id}}','purchased_date':'2026-03-05','best_before_date':'2026-06-01'}),
      api('buy-oats','POST','stock/products/{{oats.created_object_id}}/add',{'amount':3,'price':3,'shopping_location_id':'{{farm.created_object_id}}','purchased_date':'2026-03-06','best_before_date':'2026-06-01'}),
      api('buy-apples','POST','stock/products/{{apples.created_object_id}}/add',{'amount':2,'price':4,'shopping_location_id':'{{farm.created_object_id}}','purchased_date':'2026-03-07','best_before_date':'2026-06-01'}),
      api('use-rice','POST','stock/products/{{rice.created_object_id}}/consume',{'amount':1}),
      api('use-oats','POST','stock/products/{{oats.created_object_id}}/consume',{'amount':2}),
    ]
    add('gui-report-grouping','report grouping and journal totals',setup,[
      step('products','Show spending by product for March 2026.',
        'The report visibly separates Rice ($8), Oats ($9) and Apples ($8), totaling $25.',
        [go('/stockreports/spendings')],visible=['Rice','Oats','Apples','$9.00','$8.00']),
      step('stores','Group that spending by store.',
        'The report visibly totals Corner store at $8 and Farm shop at $17.',
        [go('/stockreports/spendings'),button('Store')],visible=['Corner store','Farm shop','$17.00','$8.00']),
      step('groups','Group that spending by product group.',
        'The report visibly totals Grains at $17 and Fruit at $8.',
        [go('/stockreports/spendings'),button('Product group')],visible=['Grains','Fruit','$17.00','$8.00']),
      step('filter','Show only the Grains products in the spending report.',
        'Rice and Oats are visible with combined spending $17; Apples is excluded.',
        [go('/stockreports/spendings'),{'op':'select','target':{'tag':'select'},'value':'Grains'}],visible=['Rice','Oats','$9.00','$8.00']),
      step('date-range','Show spending by product from 2026-03-06 through 2026-03-07.',
        'The report visibly includes Oats ($9) and Apples ($8) and excludes the March 5 Rice purchase.',
        [go('/stockreports/spendings?start_date=2026-03-06&end_date=2026-03-07')],visible=['Oats','Apples','$9.00','$8.00']),
      step('summary','Show the stock journal summary for the recorded purchases and consumption.',
        'The summary visibly distinguishes product purchases from consumption: Rice purchased 4 and consumed 1, Oats purchased 3 and consumed 2, Apples purchased 2.',
        [go('/stockjournal/summary')],visible=['Rice','Oats','Apples','Purchase','Consume']),
      step('summary-filter','Restrict the stock journal summary to Rice.',
        'Only Rice totals remain: purchased 4 Items and consumed 1 Item.',
        [go('/stockjournal/summary'),{'op':'select','target':{'tag':'select','nth':0},'value':'Rice'}],visible=['Rice','4 Items','1 Item']),
    ])
    add('gui-preference-effects','preferences affect ordinary forms',base()+[product(),api('purchase','POST','stock/products/{{product.created_object_id}}/add',{'amount':8,'price':2})],[
      step('purchase-default','Set the default purchase amount to 2.5, then open Purchase and select Rice.',
        'The Purchase amount is visibly prefilled with 2.5 for Rice.',
        [go('/stocksettings'),{'op':'fill','target':{'label':'Default amount for purchase'},'value':'2.5'},{'op':'press','key':'Tab'},
         go('/purchase'),{'op':'choose','target':{'tag':'input','type':'text','nth':0},'value':'Rice'}],
        checks=[read('user/settings/stock_default_purchase_amount',fields=['value'],expected={'value':'2.5'})],visible=['Rice']),
      step('consume-default','Set the default consume amount to 3, then open Consume and select Rice.',
        'The Consume amount is visibly prefilled with 3 for Rice.',
        [go('/stocksettings'),{'op':'fill','target':{'label':'Default amount for consume'},'value':'3'},{'op':'press','key':'Tab'},
         go('/consume'),{'op':'choose','target':{'tag':'input','type':'text','nth':0},'value':'Rice'}],
        checks=[read('user/settings/stock_default_consume_amount',fields=['value'],expected={'value':'3'})],visible=['Rice']),
    ])

    add('gui-product-identifiers','digital product code and plural display',base()+[product(),
        api('barcode','POST','objects/product_barcodes',{'product_id':'{{product.created_object_id}}','barcode':'RICE-2048'})],[
      step('code','Show the Grocycode for Rice.',
        'The Rice product page visibly contains its generated machine-readable Grocycode.',
        [go('/product/{{product.created_object_id}}')],visible=['Grocycode']),
      step('barcode','Select Rice on the Purchase page using barcode RICE-2048.',
        'The Purchase page visibly selects Rice and its stock unit after barcode entry.',
        [go('/purchase'),{'op':'choose','target':{'tag':'input','type':'text','nth':0},'value':'RICE-2048'}],visible=['Rice','Item']),
      step('plural','Use quantity-unit plural form testing to show the form for 2 Items.',
        'The plural test result visibly shows Items for quantity 2.',
        [go('/quantityunitpluraltesting'),{'op':'select','target':{'name':'qu_id'},'value':'Item'},fill('amount','2')],visible=['Result:','Items']),
      step('singular','Change that tested quantity to 1.',
        'The plural test result visibly changes to the singular Item for quantity 1.',
        [fill('amount','1')],visible=['Result:','Item'],depends=['plural']),
    ])
