"""Built-in reports and their ordinary HTML exports."""
from spec_common import episode, step, document, outbox
from spec_finance import REPORT_NAV, REPORT_CHILDREN

REPORTS = [
    ('cashflow-daily', ['Cash Flow','Daily'], 'cash-flow projection by day'),
    ('cashflow-monthly', ['Cash Flow','Monthly'], 'cash-flow projection by month'),
    ('cashflow-transactions', ['Cash Flow','Transactions'], 'cash-flow projection including scheduled transactions'),
    ('categories-monthly', ['Categories','Monthly'], 'monthly category income and expenses'),
    ('categories-summary', ['Categories','Summary'], 'income and expenses grouped by category'),
    ('spending', ['Categories','Where the Money Goes'], 'expense categories and their relative contributions'),
    ('income', ['Categories','Where the Money Comes From'], 'income categories and their relative contributions'),
    ('forecast', ['Forecast Report'], 'forecast of deposits and withdrawals over time'),
    ('income-expenses', ['Income vs. Expenses'], 'income compared with expenses'),
    ('income-expenses-monthly', ['Income vs. Expenses','Monthly'], 'income compared with expenses by month'),
    ('payees', ['Payees'], 'income and expenses grouped by payee'),
    ('accounts-monthly', ['Summary of Accounts','Monthly'], 'account balances summarized by month'),
    ('accounts-yearly', ['Summary of Accounts','Yearly'], 'account balances summarized by year'),
    ('budget-performance', ['Budgets','Budget Performance'], 'budget performance against actual transactions'),
    ('budget-summary', ['Budgets','Budget Category Summary'], 'budget amounts and actual spending by category'),
    ('stocks', ['Stocks Report'], 'stock investment performance over time'),
    ('stocks-summary', ['Stocks Report','Summary'], 'stock holdings and their valuations'),
]


def build():
    result=[]
    row_labels = {
        'cashflow-daily': ['2026-06-18','2026-06-20','2026-06-25','2026-07-01'],
        'cashflow-monthly': ['2026-06-01','2026-07-01','2026-10-01','2027-06-01'],
        'cashflow-transactions': ['2026-06-18','2026-06-20','2026-07-01','2026-07-05'],
        'categories-monthly': ['Bills:Electricity','Bills:Rent','Food:Groceries','Income:Salary'],
        'categories-summary': ['Electricity','Rent','Groceries','Salary'],
        'spending': ['Rent','Groceries','Electricity'], 'income': ['Salary','Grand Total:'],
        'income-expenses': ['Income:','Expenses:','Difference:'],
        'income-expenses-monthly': ['2025 January','2025 June','2026 January','2026 June'],
        'payees': ['Employer','Landlord','Grocer','Power Co'],
        'accounts-monthly': ['2024 January','2025 June','2026 January','2026 June'],
        'accounts-yearly': ['2024','2025','2026'],
        'budget-performance': ['Rent','Groceries','Salary'],
        'budget-summary': ['Rent','Groceries','Electricity'],
        'stocks-summary': ['Acme Corp','Beta Ltd'],
    }
    for name,path,description in REPORTS:
        key='report-'+name
        checks=[]
        recipe=[{'op':'report','path':path}]
        goal=f'Open the built-in report {" / ".join(path)} using the existing report settings.'
        if name == 'stocks':
            goal = 'Open the stock performance report, select Acme Corp and display its price history.'
            recipe += [{'op':'choose','window':'Money Manager Ex','label':'Stock name','value':'Beta Ltd'},
                       {'op':'choose','window':'Money Manager Ex','label':'Stock name','value':'Acme Corp'},
                       {'op':'wait','seconds':1}]
        if name in row_labels:
            goal += f' Export the current report as HTML to {outbox(key)}/report.html and leave the report visible.'
            recipe += [{'op':'export-html'}]
            for index,label in enumerate(row_labels[name]):
                checks += document('outbox','report.html','html-cells',f'computed-row-{index+1}',
                                   'Computed report values for '+label+'.',label=label)
        result.append(episode(key,'reports',[
            step('view',goal,
                 f'The report displays {description} for the supplied ledger, with populated results consistent with the reference.',
                 recipe,checks)
        ],ledger='reports',navigator=REPORT_NAV,children=REPORT_CHILDREN,
           budget={'calls':200,'seconds':1800,'tokens':2500000} if name=='spending' else None))
    return result
