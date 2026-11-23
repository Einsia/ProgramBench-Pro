"""Visible creation, editing and deletion of master-data families."""
from specification import api,read,step


def field(name,value,action='fill'):
    return {'target':{'name':name},'value':value,'action':action}


def build(add):
    configs=[
      ('locations','location','/locations','location',{},[field('is_freezer',True,'check')],{'is_freezer':1},'Save'),
      ('quantity_units','quantityunit','/quantityunits','quantity unit',{},[field('name_plural','Atlas portions')],{'name_plural':'Atlas portions'},'Save & return to quantity units'),
      ('shopping_locations','shoppinglocation','/shoppinglocations','store',{},[],{},'Save'),
      ('product_groups','productgroup','/productgroups','product group',{},[],{},'Save'),
      ('task_categories','taskcategory','/taskcategories','task category',{},[],{},'Save'),
      ('meal_plan_sections','mealplansection','/mealplansections','meal plan section',{},[field('sort_number','3'),field('time_info','18:30')],{'sort_number':3,'time_info':'18:30'},'Save'),
      ('equipment','equipment','/equipment','equipment item',{},[],{},'Save'),
      ('batteries','battery','/batteries','battery',{},[field('used_in','Remote'),field('charge_interval_days','7')],{'used_in':'Remote','charge_interval_days':7},'Save'),
      ('chores','chore','/chores','chore',{'period_type':'manually'},[field('period_type','Manually','select'),field('assignment_type','No assignment','select')],{'period_type':'manually'},'Save'),
      ('userentities','userentity','/userentities','custom entity',{'caption':'Atlas reserve'},[field('caption','Atlas library')],{'caption':'Atlas library'},'Save'),
    ]
    for entity,singular,listpage,label,keepopts,extra,values,save in configs:
        name='AtlasLibrary' if entity=='userentities' else 'Atlas '+label
        renamed=name+' revised' if entity!='userentities' else 'AtlasLibraryRevised'
        keep='AtlasReserve' if entity=='userentities' else 'Atlas reserve'
        setup=[api('retained','POST','objects/'+entity,{'name':keep,**keepopts},save='keep')]
        details=[]
        if entity=='locations':details.append('mark it as a freezer')
        if entity=='quantity_units':details.append('use plural name "Atlas portions"')
        if entity=='meal_plan_sections':details.append('set sort number 3 and time 18:30')
        if entity=='batteries':details.append('set used in "Remote" and charge interval 7 days')
        if entity=='chores':details.append('use a manual schedule and no assignment')
        if entity=='userentities':details.append('use caption "Atlas library"')
        goal='Create a '+label+' named "'+name+'"'+('; '+', and '.join(details) if details else '')+'. Save it.'
        cp1=step('create',goal,'The saved '+label+' is visible with its requested name.',
                 [{'op':'goto','path':'/'+singular+'/new'},{'op':'form','fields':[field('name',name),*extra]},
                  {'op':'button','names':[save]},{'op':'save-named','entity':entity,'name':name,'save':'created'},
                  {'op':'goto','path':listpage}],
                 checks=[read('objects/'+entity,fields=['name',*values],where={'name':name},expected={'name':name,**values},save='created')],visible=[name])
        cp2=step('rename','Rename "'+name+'" to "'+renamed+'" and save it.',
                 'The saved '+label+' is visible with its new name.',
                 [{'op':'edit-named','entity':entity,'name':name,'prefix':'/'+singular},
                  {'op':'form','fields':[field('name',renamed)]},{'op':'button','names':[save]},
                  {'op':'save-named','entity':entity,'name':renamed,'save':'created'},{'op':'goto','path':listpage}],
                 checks=[read('objects/'+entity,fields=['name',*values],where={'name':renamed},expected={'name':renamed,**values},save='created')],
                 visible=[renamed],depends=['create'])
        if entity=='userentities':
            renamed=name
            values={'caption':'Atlas library revised'}
            cp2=step('rename','Change the caption of the custom entity "AtlasLibrary" to "Atlas library revised" and save.',
                     'The custom entity shows its updated caption.',
                     [{'op':'edit-named','entity':entity,'name':name,'prefix':'/'+singular},
                      {'op':'form','fields':[field('caption','Atlas library revised')]},{'op':'button','names':[save]},
                      {'op':'goto','path':listpage}],
                     checks=[read('objects/'+entity,fields=['name','caption'],where={'name':name},expected={'name':name,**values})],
                     visible=['Atlas library revised'],depends=['create'])
        cp3=step('delete','Delete "'+renamed+'" while retaining "'+keep+'".',
                 'The deleted item is absent from the collection, which still shows the retained item.',
                 [{'op':'delete-named','entity':entity,'name':renamed,'prefix':'/'+singular,'list':listpage}],
                 checks=[read('objects/'+entity,fields=['name'],params={'query[]':'name~Atlas'},collection=True,expected=[{'name':keep}])],
                 visible=[keep],depends=['rename'],requires=['create/visible'])
        add('gui-master-'+entity,label,setup,[cp1,cp2,cp3])
