"""Transactions: entering, editing, deleting and restoring, splits, status keys, bulk operations, validation."""
from spec_common import row, count, names, rows, step, episode, document, files

EVERYDAY = ['Bank Accounts', 'Everyday Checking']


def build():
    result = []
    k = 'trx-withdrawal'
    t = {'notes': 'Course book'}
    result.append(episode(k, 'transactions', [
        step('enter', 'Open the account Everyday Checking and enter a new withdrawal: date 06/14/2026, amount 45.60, payee Book Nook, category Education:Books, '
                      'number INV-7, status Follow Up, notes "Course book".',
             'The account view of Everyday Checking lists a new withdrawal of 45.60 to Book Nook in the category Education:Books, flagged for follow up.',
             [{'op': 'nav', 'path': EVERYDAY},
              {'op': 'new-transaction', 'date': '06/14/2026', 'amount': '45.60', 'payee': 'Book Nook', 'category': 'Education:Books', 'number': 'INV-7',
               'status': 'Follow Up', 'notes': 'Course book'}],
             [row('trx', t, account='Everyday Checking', type='Withdrawal', amount=45.6, date='2026-06-14', payee='Book Nook', category='Education:Books',
                  number='INV-7', status='F', to_account='')]),
        step('default-category', 'Enter another new withdrawal in Everyday Checking: amount 18.25, payee Cafe Luna, notes "Espresso"; keep the date and the category that '
                                 'the dialog offers after the payee is chosen.',
             'The account view lists a new withdrawal of 18.25 to Cafe Luna with the category Food:Dining out.',
             [{'op': 'new-transaction', 'amount': '18.25', 'payee': 'Cafe Luna', 'notes': 'Espresso'}],
             [row('trx', {'notes': 'Espresso'}, category='Food:Dining out', date='2026-06-15', amount=18.25, status='')]),
    ]))

    k = 'trx-deposit'
    result.append(episode(k, 'transactions', [
        step('enter', 'In the account Travel Visa enter a new deposit: date 06/10/2026, amount 75.5, from the payee Employer, category Income:Reimbursement/Refunds, '
                      'status Reconciled, notes "Expense claim".',
             'The account view of Travel Visa lists a new reconciled deposit of 75.50 from Employer.',
             [{'op': 'nav', 'path': ['Credit Card Accounts', 'Travel Visa']},
              {'op': 'new-transaction', 'type': 'Deposit', 'date': '06/10/2026', 'amount': '75.5', 'payee': 'Employer', 'category': 'Income:Reimbursement/Refunds',
               'status': 'Reconciled', 'notes': 'Expense claim'},
              {'op': 'scroll', 'x': 850, 'y': 888, 'delta_x': 400}],
             [row('trx', {'notes': 'Expense claim'}, account='Travel Visa', type='Deposit', amount=75.5, date='2026-06-10', payee='Employer',
                  category='Income:Reimbursement/Refunds', status='R')]),
    ]))

    k = 'trx-transfer'
    result.append(episode(k, 'transactions', [
        step('same-currency', 'Enter a new transfer of 250 from Everyday Checking to Rainy Day Savings dated 06/12/2026, category Transfer, notes "Monthly saving".',
             'The account view shows the transfer of 250.00 to Rainy Day Savings.',
             [{'op': 'nav', 'path': EVERYDAY},
              {'op': 'new-transaction', 'type': 'Transfer', 'date': '06/12/2026', 'amount': '250', 'to_account': 'Rainy Day Savings', 'category': 'Transfer', 'notes': 'Monthly saving'}],
             [row('trx', {'notes': 'Monthly saving'}, type='Transfer', account='Everyday Checking', to_account='Rainy Day Savings', amount=250.0, to_amount=250.0,
                  date='2026-06-12', payee='', category='Transfer')]),
        step('other-currency', 'Enter a new transfer from Everyday Checking to Euro Current dated 06/13/2026, category Transfer, notes "Euro top-up": 110 leave Everyday Checking '
                               'and 100 arrive in Euro Current (use the advanced amount option for the second amount).',
             'The account view shows the transfer of 110.00 to Euro Current.',
             [{'op': 'new-transaction', 'type': 'Transfer', 'date': '06/13/2026', 'amount': '110', 'to_account': 'Euro Current', 'advanced': '100', 'category': 'Transfer', 'notes': 'Euro top-up'}],
             [row('trx', {'notes': 'Euro top-up'}, type='Transfer', to_account='Euro Current', amount=110.0, to_amount=100.0, date='2026-06-13')]),
    ]))

    k = 'trx-edit-delete'
    result.append(episode(k, 'transactions', [
        step('edit', 'In Everyday Checking edit the transaction with the notes "May dinner": change the amount to 44.75, the payee to Grocer, the category to Food:Groceries and the notes to "May dinner fixed".',
             'The list shows the edited transaction with 44.75 and the payee Grocer.',
             [{'op': 'nav', 'path': EVERYDAY}, {'op': 'edit-row', 'index': 8, 'amount': '44.75', 'payee': 'Grocer', 'category': 'Food:Groceries', 'notes': 'May dinner fixed'}],
             [row('trx', {'notes': 'May dinner fixed'}, amount=44.75, payee='Grocer', category='Food:Groceries', date='2026-05-22', tags=['trip', 'work'])]),
        step('delete', 'Delete the transaction with the notes "April power" from Everyday Checking and confirm.',
             'The transaction April power (64.10) is no longer listed in the account view.',
             [{'op': 'row', 'index': 3}, {'op': 'press', 'key': 'Delete'}, {'op': 'alert', 'button': 'Yes'}],
             [row('trx', {'notes': 'April power'}, deleted=True)]),
        step('trash', 'Restore the deleted transaction with the notes "April power", then show it in Everyday Checking.',
             'Everyday Checking again lists the City Power withdrawal of 64.10.',
             [{'op': 'nav-deleted'}, {'op': 'row', 'index': 0}, {'op': 'press', 'key': 'r'}, {'op': 'alert', 'button': 'Yes'},
              {'op': 'nav', 'path': EVERYDAY}],
             [row('trx', {'notes': 'April power'}, deleted=False, amount=64.1, account='Everyday Checking')], depends=['delete']),
    ], navigator=['Bank Accounts', 'Credit Card Accounts', 'Cash Accounts']))

    k = 'trx-split'
    result.append(episode(k, 'transactions', [
        step('enter', 'In Everyday Checking enter a new withdrawal dated 06/11/2026 to the payee Grocer with the notes "Weekly shop", split into two categories: 60 for Food:Groceries and 15.5 for Homeneeds:Clothing.',
             'The list shows a new withdrawal of 75.50 to Grocer whose category column shows split categories.',
             [{'op': 'nav', 'path': EVERYDAY},
              {'op': 'new-transaction', 'date': '06/11/2026', 'payee': 'Grocer', 'notes': 'Weekly shop', 'button': None},
              {'op': 'splits', 'rows': [['Food:Groceries', '60'], ['Homeneeds:Clothing', '15.5']]},
              {'op': 'transaction-form', 'button': 'Save'}],
             [row('trx', {'notes': 'Weekly shop'}, amount=75.5, category='',
                  splits=[{'category': 'Food:Groceries', 'amount': 60.0, 'notes': '', 'tags': []}, {'category': 'Homeneeds:Clothing', 'amount': 15.5, 'notes': '', 'tags': []}])]),
    ]))

    k = 'trx-split-details'
    result.append(episode(k, 'transactions', [
        step('tags', 'Edit the transaction with the notes "June split shop" in Everyday Checking: open its split categories, change the amount of the Food:Groceries part to 80.2 and add a third part of 9.8 for Bills:Water. Save the transaction.',
             'The list shows the transaction with the new total of 115.00.',
             [{'op': 'nav', 'path': EVERYDAY}, {'op': 'row', 'index': 11}, {'op': 'press', 'key': 'Return'},
              {'op': 'splits', 'rows': [['Food:Groceries', '80.2'], ['Homeneeds:Furnishing', '25'], ['Bills:Water', '9.8']]},
              {'op': 'transaction-form', 'button': 'Save'}],
             [row('trx', {'notes': 'June split shop'}, amount=115.0,
                  splits=[{'category': 'Bills:Water', 'amount': 9.8, 'notes': '', 'tags': []}, {'category': 'Food:Groceries', 'amount': 80.2, 'notes': 'food', 'tags': []},
                          {'category': 'Homeneeds:Furnishing', 'amount': 25.0, 'notes': 'lamp', 'tags': []}])]),
        step('view', 'Show the split categories of that transaction with the command for viewing them in the list\'s context menu and leave the window with the parts open.',
             'A window lists the three parts of the split transaction with their categories and amounts: Food:Groceries 80.20, Homeneeds:Furnishing 25.00 and Bills:Water 9.80.',
             [{'op': 'row-menu', 'index': 11, 'path': ['View Split Categories'], 'wait': 1.0}], modal_end=True, depends=['tags']),
    ]))

    k = 'trx-tags'
    result.append(episode(k, 'transactions', [
        step('existing', 'In Everyday Checking enter a new withdrawal of 33 to the payee Cafe Luna with the notes "Team lunch" and the two tags work and trip.',
             'The list shows the new transaction with the tags trip and work in its tags column.',
             [{'op': 'nav', 'path': EVERYDAY}, {'op': 'new-transaction', 'amount': '33', 'payee': 'Cafe Luna', 'notes': 'Team lunch', 'tags': ['work', 'trip']}],
             [row('trx', {'notes': 'Team lunch'}, tags=['trip', 'work'], amount=33.0)]),
        step('manager', 'In the Tag Manager add a new tag named "bonus", then give the transaction with the notes "June salary" this tag by editing the transaction.',
             'The list shows the tag bonus in the tags column of the June salary transaction.',
             [{'op': 'open', 'path': ['Tools', 'Tag Manager…'], 'window': 'Tag Manager'}, {'op': 'button', 'window': 'Tag Manager', 'name': 'Add'},
              {'op': 'text-prompt', 'window': 'Add Tag', 'value': 'bonus'}, {'op': 'close', 'window': 'Tag Manager', 'button': 'OK'},
              {'op': 'edit-row', 'index': 9, 'tags': ['bonus']}],
             [row('tag', {'name': 'bonus'}, active=1.0), row('trx', {'notes': 'June salary'}, tags=['bonus'])]),
    ]))

    k = 'trx-status-keys'
    result.append(episode(k, 'transactions', [
        step('keys', 'In Everyday Checking mark transactions with the status keys of the list: the transaction "June rent" as reconciled, "May dinner" as void, and "June split shop" as flagged for follow up.',
             'The status column shows R for June rent, V for May dinner and F for June split shop.',
             [{'op': 'nav', 'path': EVERYDAY}, {'op': 'row', 'index': 10}, {'op': 'press', 'key': 'r'}, {'op': 'row', 'index': 8}, {'op': 'press', 'key': 'v'},
              {'op': 'row', 'index': 11}, {'op': 'press', 'key': 'f'}],
             [row('trx', {'notes': 'June rent'}, status='R'), row('trx', {'notes': 'May dinner'}, status='V'), row('trx', {'notes': 'June split shop'}, status='F')]),
        step('unmark', 'Set the transaction "June rent" back to unreconciled and mark "May groceries" as duplicate, with the same keys.',
             'The status column is empty for June rent and shows D for May groceries.',
             [{'op': 'row', 'index': 10}, {'op': 'press', 'key': 'u'}, {'op': 'row', 'index': 6}, {'op': 'press', 'key': 'd'}],
             [row('trx', {'notes': 'June rent'}, status=''), row('trx', {'notes': 'May groceries'}, status='D')], depends=['keys']),
        step('bulk', 'Select the three April transactions "April rent", "April groceries" and "April power" together and mark all of them as flagged for follow up with the list\'s context menu.',
             'The status column shows F for the three selected April transactions.',
             [{'op': 'row', 'index': 1}, {'op': 'row', 'index': 3, 'modifiers': ['Shift']}, {'op': 'row-menu', 'index': 3, 'path': ['Mark as', 'Follow Up']}],
             [row('trx', {'notes': 'April rent'}, status='F'), row('trx', {'notes': 'April groceries'}, status='F'), row('trx', {'notes': 'April power'}, status='F'),
              row('trx', {'notes': 'April salary'}, status='R')]),
    ]))

    k = 'trx-duplicate-paste'
    result.append(episode(k, 'transactions', [
        step('duplicate', 'In Everyday Checking duplicate the transaction "April power": in the dialog that opens set the date to 06/09/2026 and the notes to "June power", and save.',
             'The list shows a new transaction June power of 64.10 to City Power, and April power is still there.',
             [{'op': 'nav', 'path': EVERYDAY}, {'op': 'row', 'index': 3}, {'op': 'button', 'window': 'Money Manager Ex', 'name': 'Duplicate'},
              {'op': 'transaction-form', 'date': '06/09/2026', 'notes': 'June power', 'button': 'Save'}],
             [row('trx', {'notes': 'June power'}, amount=64.1, payee='City Power', category='Bills:Electricity', date='2026-06-09', status='', type='Withdrawal'),
              row('trx', {'notes': 'April power'}, date='2026-04-20')]),
        step('paste', 'Copy the transaction "May rent" with Ctrl+C in the list, open the account Pocket Cash and paste it there with Ctrl+V.',
             'The account view of Pocket Cash lists a pasted transaction of 1150.00 to Landlord.',
             [{'op': 'row', 'index': 5}, {'op': 'press', 'key': 'Control+c'}, {'op': 'nav', 'path': ['Cash Accounts', 'Pocket Cash']}, {'op': 'click', 'x': 600, 'y': 600}, {'op': 'press', 'key': 'Control+v'}],
             [row('trx', {'notes': 'May rent', 'account': 'Pocket Cash'}, amount=1150.0, payee='Landlord', category='Bills:Rent', number='1002', type='Withdrawal', status='', date='2026-06-15'),
              count('trx', {'notes': 'May rent', 'account': 'Everyday Checking'}, 1)]),
    ]))

    k = 'trx-move'
    result.append(episode(k, 'transactions', [
        step('move', 'In Everyday Checking move the transaction "May dinner" to the account Travel Visa with the Move command of the list\'s context menu.',
             'Everyday Checking no longer lists May dinner.',
             [{'op': 'nav', 'path': EVERYDAY}, {'op': 'row-menu', 'index': 8, 'path': ['Move Transaction…']}, {'op': 'alert', 'button': 'Yes'},
              {'op': 'cell', 'window': 'Moving transaction', 'name': 'Travel Visa'}, {'op': 'close', 'window': 'Moving transaction'}],
             [row('trx', {'notes': 'May dinner'}, account='Travel Visa', amount=41.5, payee='Cafe Luna', tags=['trip', 'work'])]),
        step('view', 'Open the account Travel Visa.', 'The account view of Travel Visa now lists the transaction May dinner of 41.50 to Cafe Luna.',
             [{'op': 'nav', 'path': ['Credit Card Accounts', 'Travel Visa']}], depends=['move']),
    ]))

    k = 'trx-bulk-edit'
    result.append(episode(k, 'transactions', [
        step('edit', 'In Everyday Checking select the three transactions "April rent", "April groceries" and "April power" and edit them together: set the payee of all three to City Power and append the text "checked" to their notes (the option that keeps the existing notes).',
             'The three April rows show the payee City Power.',
             [{'op': 'nav', 'path': EVERYDAY}, {'op': 'row', 'index': 1}, {'op': 'row', 'index': 3, 'modifiers': ['Shift']}, {'op': 'button', 'window': 'Money Manager Ex', 'name': 'Edit'},
              {'op': 'bulk-edit', 'payee': 'City Power', 'append_notes': 'checked'}],
             [row('trx', {'notes': 'April rent\nchecked'}, payee='City Power', amount=1150.0, category='Bills:Rent'), row('trx', {'notes': 'April groceries\nchecked'}, payee='City Power', amount=212.4),
              row('trx', {'notes': 'April power\nchecked'}, payee='City Power', amount=64.1), row('trx', {'notes': 'April salary'}, payee='Employer')]),
    ]))

    k = 'trx-new-names'
    result.append(episode(k, 'transactions', [
        step('payee', 'In Everyday Checking enter a new withdrawal of 19.99 with the notes "New shop visit", typing the new payee name "Corner Shop" that does not exist yet, and the category Food:Groceries.',
             'The list shows the transaction with the new payee Corner Shop.',
             [{'op': 'nav', 'path': EVERYDAY}, {'op': 'new-transaction', 'amount': '19.99', 'payee': 'Corner Shop', 'category': 'Food:Groceries', 'notes': 'New shop visit', 'confirm': ['Yes']}],
             [row('trx', {'notes': 'New shop visit'}, payee='Corner Shop', category='Food:Groceries'), row('payee', {'name': 'Corner Shop'}, active=1.0)]),
        step('calculator', 'Enter a new withdrawal to the payee Grocer with the notes "Calculated amount", typing the expression 12+3*2 in the amount field and moving on, so that the field shows the result.',
             'The list shows the new transaction with the amount 18.00.',
             [{'op': 'new-transaction', 'amount': '12+3*2', 'payee': 'Grocer', 'notes': 'Calculated amount'}],
             [row('trx', {'notes': 'Calculated amount'}, amount=18.0, category='Food:Groceries')]),
        step('save-new', 'With one use of the new transaction dialog enter two withdrawals in Everyday Checking: first 5 to Cafe Luna with the notes "Coffee one" using the button that saves and starts the next transaction, then 6 to Cafe Luna with the notes "Coffee two", and save.',
             'The list shows both new Cafe Luna withdrawals, for 5.00 and 6.00.',
             [{'op': 'new-transaction', 'amount': '5', 'payee': 'Cafe Luna', 'notes': 'Coffee one', 'button': None}, {'op': 'button', 'window': 'New Transaction', 'name': 'Save and New', 'wait': 1.0},
              {'op': 'transaction-form', 'amount': '6', 'payee': 'Cafe Luna', 'notes': 'Coffee two', 'button': 'Save'}],
             [row('trx', {'notes': 'Coffee one'}, amount=5.0, payee='Cafe Luna'), row('trx', {'notes': 'Coffee two'}, amount=6.0, payee='Cafe Luna')]),
    ]))
    return result
