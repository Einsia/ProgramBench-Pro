"""Accounts: the wizard, every field of the account dialog, editing, closing, changing the type, deleting."""
from spec_common import row, count, names, rows, step, episode


def build():
    result = []
    k = 'account-new-checking'
    result.append(episode(k, 'accounts', [
        step('wizard', 'Create a new account of the type Checking named "Holiday Fund". In the account dialog that follows set the initial '
                       'balance to 1250.75 and the opening date to 03/15/2026, mark it as a favorite account, and confirm the dialog.',
             'The new account Holiday Fund appears on the dashboard among the bank accounts, with a balance of $1250.75.',
             [{'op': 'new-account', 'name': 'Holiday Fund'},
              {'op': 'account-dialog', 'balance': '1250.75', 'opened': '03/15/2026', 'favorite': True}],
             [row('account', {'name': 'Holiday Fund'}, type='Checking', balance=1250.75, opened='2026-03-15', favorite='TRUE', status='Open', currency='USD')]),
        step('notes', 'Save the notes "Summer trip money" in the account Holiday Fund, then show its saved notes again.',
             'The reopened account information shows the saved notes Summer trip money.',
             [{'op': 'edit-account', 'account': 'Holiday Fund', 'notes': 'Summer trip money'},
              {'op': 'edit-account', 'account': 'Holiday Fund', 'tab': 'Notes', 'keep_open': True}],
             [row('account', {'name': 'Holiday Fund'}, notes='Summer trip money')], depends=['wizard'], modal_end=True),
    ]))

    k = 'account-new-types'
    result.append(episode(k, 'accounts', [
        step('credit-card', 'Create a new account of the type Credit Card named "Store Card" and confirm the account dialog with its defaults.',
             'Store Card appears on the dashboard in the section of credit card accounts.',
             [{'op': 'new-account', 'name': 'Store Card', 'type': 'Credit Card'}, {'op': 'account-dialog'}],
             [row('account', {'name': 'Store Card'}, type='Credit Card', balance=0.0, status='Open', favorite='TRUE')]),
        step('term', 'Create a new account of the type Term named "Fixed Deposit", with the initial balance 4000 and the opening date 01/10/2026.',
             'A section of term accounts appears on the dashboard and lists Fixed Deposit with $4000.00.',
             [{'op': 'new-account', 'name': 'Fixed Deposit', 'type': 'Term'}, {'op': 'account-dialog', 'balance': '4000', 'opened': '01/10/2026'}],
             [row('account', {'name': 'Fixed Deposit'}, type='Term', balance=4000.0, opened='2026-01-10')]),
        step('investment', 'Create a new account of the type Investment named "Index Broker" and confirm the account dialog with its defaults.',
             'A section of stock portfolios appears on the dashboard and lists Index Broker.',
             [{'op': 'new-account', 'name': 'Index Broker', 'type': 'Investment'}, {'op': 'account-dialog'}],
             [row('account', {'name': 'Index Broker'}, type='Investment', status='Open')]),
        step('loan', 'Create a new account of the type Loan named "Car Loan", with the initial balance -9000.',
             'A section of loan accounts appears on the dashboard and lists Car Loan with a negative balance of 9000.',
             [{'op': 'new-account', 'name': 'Car Loan', 'type': 'Loan'}, {'op': 'account-dialog', 'balance': '-9000'}],
             [row('account', {'name': 'Car Loan'}, type='Loan', balance=-9000.0)]),
    ]))

    k = 'account-all-fields'
    a = {'name': 'Rainy Day Savings'}
    result.append(episode(k, 'accounts', [
        step('other', 'Edit the account Rainy Day Savings. On its Other page set the account number to "SAV-7788", held at to "Union Credit", the '
                      'website to "https://union.example/savings", the contact to "Ann 555-0199" and the access info to "branch 12". Save, then show these saved details again.',
             'The reopened account information shows SAV-7788, Union Credit, the website and Ann 555-0199; access information is populated.',
             [{'op': 'edit-account', 'account': 'Rainy Day Savings', 'number': 'SAV-7788', 'held_at': 'Union Credit', 'website': 'https://union.example/savings',
               'contact': 'Ann 555-0199', 'access': 'branch 12'},
              {'op': 'edit-account', 'account': 'Rainy Day Savings', 'tab': 'Other', 'keep_open': True}],
             [row('account', a, number='SAV-7788', held_at='Union Credit', website='https://union.example/savings', contact='Ann 555-0199', access='branch 12')], modal_end=True),
        step('statement', 'Edit the account Rainy Day Savings again. On its Statement page turn the lock on, set the reconciled date to 05/31/2026 and the '
                          'minimum balance to 500. Save, then show these saved statement settings again.',
             'The reopened statement settings show the lock enabled, a reconciled date of May 31, 2026 and a minimum balance of 500.',
             [{'op': 'close', 'window': 'Edit Account'},
              {'op': 'edit-account', 'account': 'Rainy Day Savings', 'locked': True, 'statement_date': '05/31/2026', 'minimum_balance': '500'},
              {'op': 'edit-account', 'account': 'Rainy Day Savings', 'tab': 'Statement', 'keep_open': True}],
             [row('account', a, statement_locked=1.0, statement_date='2026-05-31', minimum_balance=500.0)],
             modal_end=True),
        step('credit', 'Edit the account Travel Visa. On its Credit page set the credit limit to 7500, the interest rate to 19.9, the payment due date to '
                       '07/20/2026 and the minimum payment to 35. Save, then show these saved credit settings again.',
             'The reopened credit settings show the credit limit 7500, interest rate 19.9, payment date July 20, 2026 and minimum payment 35.',
             [{'op': 'close', 'window': 'Edit Account'},
              {'op': 'edit-account', 'account': 'Travel Visa', 'credit_limit': '7500', 'interest': '19.9', 'due_date': '07/20/2026', 'minimum_payment': '35'},
              {'op': 'edit-account', 'account': 'Travel Visa', 'tab': 'Credit', 'keep_open': True}],
             [row('account', {'name': 'Travel Visa'}, credit_limit=7500.0, interest=19.9, due_date='2026-07-20', minimum_payment=35.0)],
             modal_end=True),
    ],budget={'calls':160,'seconds':1500,'tokens':1800000}))
    return result
