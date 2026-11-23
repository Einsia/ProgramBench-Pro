"""API credential lifecycle, file attachments and saved state across restarts."""
from specification import api,read,step
from fixtures import MANUAL_BASE64
from gui_common import base,product,stock,go,button,fill
from gui_stock import choose_product,amount


def build(add):
    add('gui-api-keys','API key management',[],[
      step('create','Create an API key with description "Tablet".',
           'The API key list visibly contains a generated key described as Tablet.',
           [go('/manageapikeys'),button('Add'),fill('description','Tablet'),button('OK')],checks=[],visible=['Tablet']),
      step('another','Create a second API key with description "Kitchen".',
           'Two distinct API keys are visibly listed with descriptions Tablet and Kitchen.',
           [button('Add'),fill('description','Kitchen'),button('OK')],checks=[],visible=['Tablet','Kitchen'],depends=['create']),
      step('revoke','Delete the Tablet API key while keeping Kitchen.',
           'Tablet is absent from the key list and Kitchen remains.',
           [{'op':'fill','target':{'placeholder':'Search'},'value':'Tablet'},{'op':'click','target':{'title':'Delete this item'}},button('Yes'),
            {'op':'fill','target':{'placeholder':'Search'},'value':''}],checks=[],visible=['Kitchen'],depends=['another'],requires=['create/visible']),
    ])
    setup=[api('equipment','POST','objects/equipment',{'name':'Mixer'},save='equipment')]
    add('gui-equipment-file','equipment manual attachment',setup,[
      step('attach','Attach the supplied manual.pdf as the instruction manual for Mixer and save it.',
           'Mixer visibly has the attached instruction manual available.',
           [go('/equipment/{{equipment.created_object_id}}'),{'op':'upload','name':'manual.pdf','base64':MANUAL_BASE64},button('Save'),go('/equipment/{{equipment.created_object_id}}')],
           checks=[{'manual':True,'equipment':'{{equipment.created_object_id}}'}],visible=['manual.pdf']),
      step('notes','Set Mixer notes to "Unplug before cleaning." and save it.',
           'Mixer visibly shows the saved note Unplug before cleaning.',
           [go('/equipment/{{equipment.created_object_id}}'),{'op':'form','fields':[{'action':'editor','target':{'role':'textbox'},'value':'Unplug before cleaning.'}]},button('Save'),go('/equipment'),button('NOTES')],
           checks=[],visible=['Unplug before cleaning.'],depends=['attach']),
    ],inputs={'file':{'name':'manual.pdf','base64':MANUAL_BASE64}})
    setup=base()+[product(),stock(amount=8)]
    add('gui-persistence','saved inventory after restart',setup,[
      step('change','Consume 2 Items of Rice and show the remaining stock.',
           'Rice visibly has 6 Items remaining.',
           [go('/consume'),choose_product(),amount(2),button('OK'),go('/stockoverview')],
           checks=[read('stock/products/{{product.created_object_id}}',fields=['stock_amount'],expected={'stock_amount':6})],visible=['Rice','6 Items']),
      step('retained','The application has been restarted with its saved data. Show the stock overview for Rice.',
           'Rice still visibly has the saved quantity of 6 Items.',
           [go('/stockoverview')],checks=[read('stock/products/{{product.created_object_id}}',fields=['stock_amount'],expected={'stock_amount':6})],visible=['Rice','6 Items'],depends=['change'],lifecycle='restart'),
    ])
