"""Payees, categories, tags and currencies: their managers, merging and the rules that protect used entries."""
from spec_common import row, count, names, rows, step, episode, HINTS

P = 'Payee Manager'
C = 'Category Manager'
G = 'Tag Manager'
U = 'Currency Manager'


def payees():
    result = []
    # ---------------------------------------------------------------- payees
    k = 'payee-add-edit'
    result.append(episode(k, 'payees', [
        step('add', 'In the Payee Manager add a new payee named "Garden Centre" with the category Homeneeds:Furnishing, the reference "GC-1", the website '
                    '"https://garden.example", the notes "Plants and tools" and the match pattern "GARDEN*".',
             'The payee list shows Garden Centre with the category Homeneeds:Furnishing.',
             [{'op': 'open', 'path': ['Tools', 'Payee Manager…'], 'window': P},
              {'op': 'list-menu', 'window': P, 'index': 0, 'path': ['Add']},
              {'op': 'fill', 'window': 'Edit Payee', 'label': 'Payee', 'value': 'Garden Centre'},
              {'op': 'fill', 'window': 'Edit Payee', 'label': 'Last Used Category', 'value': 'Homeneeds:Furnishing', 'entry': True},
              {'op': 'fill', 'window': 'Edit Payee', 'label': 'Reference', 'value': 'GC-1'},
              {'op': 'fill', 'window': 'Edit Payee', 'label': 'Website', 'value': 'https://garden.example'},
              {'op': 'fill-described', 'window': 'Edit Payee', 'text': 'notes', 'value': 'Plants and tools'},
              {'op': 'payee-pattern', 'value': 'GARDEN*'},
              {'op': 'close', 'window': 'Edit Payee'},
              {'op': 'search', 'window': P, 'value': 'Garden'}],
             [row('payee', {'name': 'Garden Centre'}, category='Homeneeds:Furnishing', number='GC-1', website='https://garden.example', notes='Plants and tools', active=1.0)]),
        step('edit', 'Edit the payee Book Nook: rename it to "Book Corner" and give it the category Education:Books.',
             'The payee list shows Book Corner with the category Education:Books and no longer lists Book Nook.',
             [{'op': 'search', 'window': P, 'value': 'Book'},
              {'op': 'list-menu', 'window': P, 'index': 0, 'path': ['Edit']},
              {'op': 'fill', 'window': 'Edit Payee', 'label': 'Payee', 'value': 'Book Corner'},
              {'op': 'fill', 'window': 'Edit Payee', 'label': 'Last Used Category', 'value': 'Education:Books', 'entry': True},
              {'op': 'close', 'window': 'Edit Payee'}],
             [row('payee', {'name': 'Book Corner'}, category='Education:Books'), row('trx', {'notes': 'Visa books'}, payee='Book Corner')]),
    ]))
    return result


def more():
    result = []
    result.append(episode('payee-visibility', 'payees', [
        step('hide', 'Hide the payee Cafe Luna, then show hidden payees in the manager so its hidden state can be seen.',
             'Cafe Luna is listed as a hidden payee.',
             [{'op':'open','path':['Tools','Payee Manager…'],'window':P}, {'op':'search','window':P,'value':'Cafe'},
              {'op':'list-menu','window':P,'path':['Hide Selected']}, {'op':'toggle','window':P,'name':'Show hidden','value':True}],
             [row('payee',{'name':'Cafe Luna'},active=0)]),
        step('show', 'Make Cafe Luna visible again in the payee manager.',
             'Cafe Luna is listed without the hidden indication.',
             [{'op':'list-menu','window':P,'path':['Show Selected']}],
             [row('payee',{'name':'Cafe Luna'},active=1)], depends=['hide']),
        step('used', 'Try to remove Cafe Luna and leave the resulting explanation visible.',
             'The application explains that the payee is in use and cannot be removed.',
             [{'op':'list-menu','window':P,'path':['Remove']}], modal_end=True,
             points=[count('payee',{'name':'Cafe Luna'},1)], requires={'visible':['show/payee-cafe-luna-active']}),
    ]))
    result.append(episode('payee-remove-unused', 'payees', [
        step('add', 'Add an unused payee named Temporary Vendor in the Payee Manager.',
             'The payee list contains Temporary Vendor.',
             [{'op':'open','path':['Tools','Payee Manager…'],'window':P}, {'op':'list-menu','window':P,'path':['Add']},
              {'op':'fill','window':'Edit Payee','label':'Payee','value':'Temporary Vendor'}, {'op':'close','window':'Edit Payee'},
              {'op':'search','window':P,'value':'Temporary'}], [row('payee',{'name':'Temporary Vendor'},active=1)]),
        step('remove', 'Remove Temporary Vendor from the payee manager, then clear its search to display the remaining payees.',
             'The list displays the original payees, including Book Nook and Cafe Luna, without Temporary Vendor.',
             [{'op':'list-menu','window':P,'path':['Remove']}, {'op':'search','window':P,'value':''}],
             [count('payee',{'name':'Temporary Vendor'},0)], depends=['add']),
    ]))
    result.append(episode('tag-manage', 'tags', [
        step('add', 'Add the tag household in the Tag Manager.', 'The tag list includes household.',
             [{'op':'open','path':['Tools','Tag Manager…'],'window':G}, {'op':'button','window':G,'name':'Add'},
              {'op':'text-prompt','window':'Add Tag','value':'household'}], [row('tag',{'name':'household'},active=1)]),
        step('rename', 'Rename the tag home to domestic.', 'The tag list shows domestic in place of home.',
             [{'op':'cell','window':G,'name':'home'}, {'op':'button','window':G,'name':'Edit'},
              {'op':'text-prompt','window':'Edit Tag','value':'domestic'}],
             [row('tag',{'name':'domestic'},active=1),row('trx',{'notes':'April groceries'},tags=['domestic']),row('trx',{'notes':'May groceries'},tags=['domestic'])]),
        step('delete', 'Delete the unused tag household.', 'The tag household is removed; the other tags present before deletion remain.',
             [{'op':'cell','window':G,'name':'household'}, {'op':'button','window':G,'name':'Delete'}],
             [count('tag',{'name':'household'},0)], depends=['add']),
        step('used', 'Select the tag work and inspect whether it can be deleted. Leave it selected.',
             'The tag work remains listed and deletion is unavailable for this used tag.',
             [{'op':'cell','window':G,'name':'work'}, {'op':'button','window':G,'name':'Delete'}],
             [count('tag',{'name':'work'},1)], modal_end=True, requires={'visible':['rename/tag-domestic-active']}),
    ]))
    result.append(episode('category-hierarchy', 'categories', [
        step('root', 'Add a top-level category named Hobbies in the Category Manager.', 'The category tree contains Hobbies at the top level.',
             [{'op':'open','path':['Tools','Category Manager…'],'window':C}, {'op':'category-row'}, {'op':'button','window':C,'name':'New'},
              {'op':'text-prompt','window':'Add Category','value':'Hobbies'}, {'op':'search','window':C,'value':'Hobbies'}],
             [row('category',{'path':'Hobbies'},active=1)]),
        step('child', 'Add the subcategory Music under Hobbies.', 'Music appears within Hobbies in the category tree.',
             [{'op':'category-row','path':'Hobbies'}, {'op':'button','window':C,'name':'New'},
              {'op':'text-prompt','window':'Add Category','value':'Music'}, {'op':'search','window':C,'value':'Hobbies'}],
             [row('category',{'path':'Hobbies:Music'},active=1)],depends=['root']),
        step('rename', 'Rename Hobbies:Music to Instruments.', 'The category tree shows Hobbies with the child Instruments.',
             [{'op':'category-row','path':'Hobbies:Music'}, {'op':'button','window':C,'name':'Edit'},
              {'op':'text-prompt','window':'Edit Category','value':'Instruments'}, {'op':'search','window':C,'value':'Hobbies'}],
             [row('category',{'path':'Hobbies:Instruments'},active=1)],depends=['child']),
        step('delete', 'Delete Hobbies:Instruments and show Hobbies again.', 'Hobbies remains as a category with no child Instruments.',
             [{'op':'category-row','path':'Hobbies:Instruments'}, {'op':'button','window':C,'name':'Delete'}, {'op':'search','window':C,'value':'Hobbies'}],
             [count('category',{'path':'Hobbies:Instruments'},0)],depends=['rename']),
    ]))
    result.append(episode('category-hide-used', 'categories', [
        step('hide', 'Hide Education:Books, turn off showing hidden categories, then display the Education category group.',
             'Education shows its remaining subcategories such as Tuition and Others, without Books.',
             [{'op':'open','path':['Tools','Category Manager…'],'window':C}, {'op':'category-row','path':'Education:Books','menu':['Hide Selected Category']},
              {'op':'toggle','window':C,'name':'Show All','value':False}, {'op':'search','window':C,'value':'Education'}],
             [row('category',{'path':'Education:Books'},active=0)]),
        step('show', 'Make Education:Books visible again, then display Education with hidden categories excluded.', 'Education again includes Books among its visible subcategories.',
             [{'op':'toggle','window':C,'name':'Show All','value':True}, {'op':'category-row','path':'Education:Books','menu':['Show Selected Category']},
              {'op':'toggle','window':C,'name':'Show All','value':False}, {'op':'search','window':C,'value':'Education'}],
             [row('category',{'path':'Education:Books'},active=1)],depends=['hide']),
        step('used', 'Select Education:Books in the Category Manager and inspect whether it can be deleted. Leave it selected.',
             'Education:Books remains listed and the delete operation is unavailable for this used category.',
             [{'op':'category-row','path':'Education:Books'}, {'op':'button','window':C,'name':'Delete'}],
             [count('category',{'path':'Education:Books'},1)],modal_end=True,requires={'visible':['show/category-education-books-active']}),
    ]))
    for kind, source, target, points in [
        ('Payees','Book Nook','Grocer',[
            row('trx',{'notes':'Visa books'},payee='Grocer'), row('sched',{'notes':'Planned purchase'},payee='Grocer'), count('payee',{'name':'Book Nook'},0)]),
        ('Categories','Food:Groceries','Food:Dining out',[
            row('trx',{'notes':'April groceries'},category='Food:Dining out'), row('trx',{'notes':'May groceries'},category='Food:Dining out'),
            row('sched',{'notes':'Planned purchase'},category='Food:Dining out'), row('payee',{'name':'Grocer'},category='Food:Dining out'),
            count('budget',{'year':'2026'},0), count('category',{'path':'Food:Groceries'},0),
            rows('trx',['splits'],{'notes':'Tagged split'}), rows('sched',['splits'],{'notes':'Planned split'})]),
        ('Tags','work','home',[
            row('trx',{'notes':'May dinner'},tags=['home','trip']), row('sched',{'notes':'Planned purchase'},tags=['home','trip']),
            rows('trx',['splits'],{'notes':'Tagged split'}), rows('sched',['splits'],{'notes':'Planned split'}),count('tag',{'name':'work'},0)]),
    ]:
        key='merge-'+kind.lower()
        manager={'Payees':P,'Categories':C,'Tags':G}[kind]
        after=[{'op':'open','path':['Tools',manager+'…'],'window':manager}]
        after += [{'op':'search','window':manager,'value':target}]
        result.append(episode(key,'merges',[
            step('merge',f'Merge {source} into {target} using the {kind.lower()} merge operation, deleting the source after merging. Then display {target} in its manager.',
                 f'The manager lists {target}, and the merged source {source} has been removed.',
                 [{'op':'merge','kind':kind,'source':source,'target':target}]+after, points)
        ],ledger='merges'))
    return result





def currencies():
    result=[]
    result.append(episode('currency-format','currencies',[
        step('format','Edit Euro (EUR): use the currency symbol EUR as a suffix, a comma decimal character, a dot grouping character, scale 2 and conversion to base rate 1.125. Save, then show the saved currency format again.',
             'The saved format displays EUR as the suffix, comma decimals, dot grouping and the base rate 1.125.',
             [{'op':'open','path':['Tools','Currency Manager…'],'window':U}, {'op':'search','window':U,'value':'EUR'},
              {'op':'cell','window':U,'name':'EUR','count':2}, {'op':'fill','window':U,'label':'Currency Symbol','value':'EUR'},
              {'op':'radio','window':U,'name':'Suffix'}, {'op':'choose','window':U,'label':'Decimal Char','value':'Comma'},
              {'op':'choose','window':U,'label':'Grouping Char','value':'Dot (.)'}, {'op':'fill','window':U,'label':'Scale','value':'2'},
              {'op':'fill','window':U,'label':'Conversion to Base Rate','value':'1.125'}, {'op':'close','window':U},
              {'op':'cell','window':U,'name':'EUR','count':2}],
             [row('currency',{'symbol':'EUR'},suffix='EUR',prefix='',decimal=',',group='.',scale=100,rate=1.125)], modal_end=True),
    ]))
    result.append(episode('currency-history','currencies',[
        step('add','Add an exchange rate for EUR dated 06/01/2026 with value 1.12 in the Currency Manager.',
             'The Euro history lists June 1, 2026 with rate 1.12.',
             [{'op':'open','path':['Tools','Currency Manager…'],'window':U}, {'op':'search','window':U,'value':'EUR'}, {'op':'cell','window':U,'name':'EUR'},
              {'op':'fill','window':U,'label':'Date','value':'06/01/2026','commit':True}, {'op':'fill','window':U,'label':'Value','value':'1.12'},
              {'op':'button','window':U,'name':'Add/Update'}], [row('currency_history',{'symbol':'EUR','date':'2026-06-01'},rate=1.12)]),
        step('update','Update that EUR rate for 06/01/2026 to 1.15.',
             'The history lists June 1, 2026 with the updated rate 1.15.',
             [{'op':'fill','window':U,'label':'Value','value':'1.15'}, {'op':'button','window':U,'name':'Add/Update'}],
             [row('currency_history',{'symbol':'EUR','date':'2026-06-01'},rate=1.15)],depends=['add']),
        step('second','Add a second EUR rate dated 06/10/2026 with value 1.18.',
             'Both EUR history rows are visible, for June 1 and June 10, with their distinct rates.',
             [{'op':'fill','window':U,'label':'Date','value':'06/10/2026','commit':True}, {'op':'fill','window':U,'label':'Value','value':'1.18'},
              {'op':'button','window':U,'name':'Add/Update'}], [row('currency_history',{'symbol':'EUR','date':'2026-06-10'},rate=1.18)],depends=['update']),
    ]))
    return result


def build():
    return payees() + more() + currencies()
