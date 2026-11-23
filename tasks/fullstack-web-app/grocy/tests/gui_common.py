"""Public fixtures and input descriptions used by browser episodes."""
from specification import api


def base():
    return [api('pantry','POST','objects/locations',{'name':'Pantry'},save='pantry'),
            api('freezer','POST','objects/locations',{'name':'Freezer','is_freezer':1},save='freezer'),
            api('pieces','POST','objects/quantity_units',{'name':'Item','name_plural':'Items'},save='unit'),
            api('store','POST','objects/shopping_locations',{'name':'Corner store'},save='store')]


def product(name='Rice',key='product',**extra):
    return api('product-'+key,'POST','objects/products',{'name':name,'location_id':'{{pantry.created_object_id}}',
               'qu_id_stock':'{{unit.created_object_id}}','qu_id_purchase':'{{unit.created_object_id}}',
               'default_best_before_days':30,**extra},save=key)


def stock(key='product',amount=8,due='2026-04-01',**extra):
    return api('stock-'+key,'POST','stock/products/{{'+key+'.created_object_id}}/add',
               {'amount':amount,'price':2.5,'best_before_date':due,**extra},save='stock-'+key)


def go(path):return {'op':'goto','path':path}
def button(name):return {'op':'button','names':[name]}
def fill(name,value):return {'op':'fill','target':{'name':name},'value':value}
def select(name,value):return {'op':'select','target':{'name':name},'value':value}
def tick(name,value=True):return {'op':'check','target':{'name':name},'value':value}
