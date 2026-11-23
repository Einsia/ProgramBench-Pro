"""Asset, investment, budget and scheduled-transaction user goals."""
from spec_common import row, rows, count, info, step, episode

MAIN='Money Manager Ex'


def assets():
    result=[]
    result.append(episode('asset-depreciation','assets',[
        step('create','Create an asset named Family Car, type Automobile, purchased 06/15/2025 with initial value 20000, depreciating at 10 percent with the default daily compounding period. Add the notes Family hatchback. Decline creation of an associated account.',
             'The assets list shows Family Car as an automobile, with its initial value 20000 and a lower current value.',
             [{'op':'nav','path':['Assets']}, {'op':'button','window':MAIN,'name':'New'},
              {'op':'asset-form','name':'Family Car','type':'Automobile','date':'06/15/2025','value':'20000','change':'Depreciates','rate':'10','notes':'Family hatchback'}],
             [row('asset',{'name':'Family Car'},type='Automobile',date='2025-06-15',value=20000,change='Depreciates',rate=10,notes='Family hatchback',status='Open')]),
        step('edit','Change Family Car to initial value 22000 and depreciation rate 8 percent.',
             'The assets list shows Family Car with initial value 22000 and its recalculated current value.',
             [{'op':'click','x':600,'y':200}, {'op':'button','window':MAIN,'name':'Edit'},
              {'op':'asset-form','window':'Edit Asset','value':'22000','rate':'8'}],
             [row('asset',{'name':'Family Car'},value=22000,rate=8)],depends=['create']),
    ]))
    result.append(episode('asset-create-delete','assets',[
        step('create','Create an asset called Studio Print of type Art, date 06/01/2026, initial value 350, with no change in value. Accept creation of an associated account, then cancel the proposed asset transaction.',
             'The assets list contains Studio Print with initial and current values of 350.',
             [{'op':'nav','path':['Assets']}, {'op':'button','window':MAIN,'name':'New'},
              {'op':'asset-form','name':'Studio Print','type':'Art','date':'06/01/2026','value':'350','account':'Yes'}],
             [row('asset',{'name':'Studio Print'},type='Art',value=350,change='None'),row('account',{'name':'Art'},type='Asset')]),
        step('second','Create a second asset called Collectible Coin of type Other with initial value 90 and no change in value. Decline the associated account.',
             'Collectible Coin appears in the assets list with initial value 90.',
             [{'op':'button','window':MAIN,'name':'New'}, {'op':'asset-form','name':'Collectible Coin','type':'Other','value':'90'}],
             [row('asset',{'name':'Collectible Coin'},value=90,type='Other')]),
        step('delete','Delete the asset Collectible Coin and confirm.',
             'Collectible Coin is removed; the other assets present before deletion remain.',
             [{'op':'click','x':600,'y':226}, {'op':'button','window':MAIN,'name':'Delete'},
              {'op':'alert','button':'Yes'}, {'op':'search','window':MAIN,'value':''}],
             [count('asset',{'name':'Collectible Coin'},0)],depends=['second']),
    ]))
    return result



REPORT_NAV = ['Bank Accounts','Credit Card Accounts','Cash Accounts','Loan Accounts','Term Accounts','Stock Portfolios']
REPORT_CHILDREN = {'Bank Accounts':['Euro Bank','Main Checking','Savings Pot'], 'Credit Card Accounts':['Blue Card'],
                   'Cash Accounts':['Wallet'], 'Loan Accounts':['Home Loan'], 'Term Accounts':['Fixed Term'],
                   'Stock Portfolios':['Broker'], 'Budget Planner':['2026']}


def budgets():
    result=[]
    year_points=[]
    for category, period, amount in [('Food:Groceries','Monthly',-250), ('Food:Dining out','Weekly',-10),
                                   ('Bills:Rent','Monthly',-1100),('Bills:Electricity','Quarterly',-240),
                                   ('Income:Salary','Monthly',3050),('Automobile:Maintenance','Yearly',-700)]:
        year_points += row('budget',{'year':'2027','category':category},period=period,amount=amount)
    result.append(episode('budget-periods','budgets',[
        step('copy','Create a 2027 budget based on the existing 2026 budget.',
             'The Budget Editor lists the new year 2027 alongside the existing periods.',
             [{'op':'open','path':['Tools','Budget Planner…'],'window':'Budget Editor'}, {'op':'button','window':'Budget Editor','name':'Add Year'},
              {'op':'fill','window':'Budget Entry Details','label':'Budget Year','role':'spin button','value':'2027','commit':True},
              {'op':'choose','window':'Budget Entry Details','label':'Base Budget On','value':'2026'}, {'op':'close','window':'Budget Entry Details'}],
             [count('budget_year',{'name':'2027'},1),year_points]),
        step('month','Create the monthly budget 2027-02 based on 2026-06.',
             'The Budget Editor lists 2027-02 as a separate monthly budget.',
             [{'op':'button','window':'Budget Editor','name':'Add Month'},
              {'op':'fill','window':'Budget Month Entry','label':'Budget Year','role':'spin button','value':'2027','commit':True},
              {'op':'fill','window':'Budget Month Entry','label':'Budget Month','role':'spin button','value':'2','commit':True},
              {'op':'choose','window':'Budget Month Entry','label':'Base Budget On','value':'2026-06'}, {'op':'close','window':'Budget Month Entry'}],
             [row('budget',{'year':'2027-02','category':'Food:Groceries'},amount=-300,period='Monthly'),row('budget',{'year':'2027-02','category':'Bills:Rent'},amount=-1100)]),
        step('delete','Delete the monthly budget 2027-02, retaining the annual budget 2027.',
             'The Budget Editor no longer lists 2027-02; the other periods present before deletion remain.',
             [{'op':'cell','window':'Budget Editor','name':'2027-02'}, {'op':'button','window':'Budget Editor','name':'Delete'}],
             [count('budget_year',{'name':'2027-02'},0),count('budget',{'year':'2027-02'},0)],depends=['month']),
    ],ledger='reports',navigator=REPORT_NAV,children=REPORT_CHILDREN))
    result.append(episode('budget-edit','budgets',[
        step('expense','Open the 2026 annual budget and change the Food:Groceries budget to an expense of 280 per month, with notes Fresh food. Save the entry.',
             'The annual budget shows Food:Groceries as Monthly with amount -280 and annual estimate -3360.',
             [{'op':'nav','path':['Budget Planner','2026']}, {'op':'click','x':450,'y':732,'count':2},
              {'op':'choose','window':'Budget Year Entry','label':'Type','value':'Expense'},
              {'op':'choose','window':'Budget Year Entry','label':'Frequency','value':'Monthly'},
              {'op':'fill','window':'Budget Year Entry','label':'Amount','value':'280'},
              {'op':'fill-described','window':'Budget Year Entry','text':'notes','value':'Fresh food'},
              {'op':'close','window':'Budget Year Entry'},
              {'op':'button','window':MAIN,'name':'View All Budget Categories'}, {'op':'menu-item','name':'View Planned Budget Categories'}],
             [row('budget',{'year':'2026','category':'Food:Groceries'},amount=-280,period='Monthly',notes='Fresh food')]),
        step('income-view','Show only income budget categories in the annual budget.',
             'The filtered annual budget shows Income:Salary and its positive budget, without the rent and grocery expense entries.',
             [{'op':'button','window':MAIN,'name':'View Planned Budget Categories'}, {'op':'menu-item','name':'View Income Budget Categories'}],
             [info('BUDGET_FILTER','View Income Budget Categories')]),
        step('expense-view','Show only expense budget categories in the annual budget.',
             'The filtered budget shows the expense categories, including rent and groceries, without Income:Salary.',
             [{'op':'button','window':MAIN,'name':'View Income Budget Categories'}, {'op':'menu-item','name':'View Expense Budget Categories'}],
             [info('BUDGET_FILTER','View Expense Budget Categories')]),
    ],ledger='reports',navigator=REPORT_NAV,children=REPORT_CHILDREN))
    return result




def stocks():
    result=[]
    stock='New Stock Investment'
    edit='Edit Stock Investment'
    result.append(episode('stock-purchase-sale','stocks',[
        step('buy','In the Broker portfolio create Cedar Works (symbol CDR), initially purchasing 12.5 shares on 06/01/2026 at 20 per share with commission 2.5 and current price 20. In the proposed share transaction use payee Employer, category Investment:Purchase, number CDR-BUY-1 and notes Cedar initial lot. Confirm the transaction and close the investment editor.',
             'The Broker portfolio shows Cedar Works with 12.5 shares and purchase cost including commission of 252.50.',
             [{'op':'nav','path':['Stock Portfolios','Broker']}, {'op':'click','x':700,'y':700}, {'op':'button','window':MAIN,'name':'New'},
              {'op':'fill','window':stock,'label':'Company Name','value':'Cedar Works'}, {'op':'fill','window':stock,'label':'Stock Symbol','value':'CDR'},
              {'op':'fill','window':stock,'label':'*Date','value':'06/01/2026','commit':True},
              {'op':'fill','window':stock,'label':'*Share Number','value':'12.5','commit':True},
              {'op':'fill','window':stock,'label':'*Share Price','value':'20','commit':True},
              {'op':'fill','window':stock,'label':'Deductible Comm.','value':'2.5','commit':True},
              {'op':'fill','window':stock,'label':'Curr. Share Price','value':'20','commit':True}, {'op':'button','window':stock,'name':'Save'},
              {'op':'share-form','payee':'Employer','category':'Investment:Purchase','number':'CDR-BUY-1','notes':'Cedar initial lot'},
              {'op':'close','window':edit,'button':'Close'}],
             [row('stock',{'symbol':'CDR'},name='Cedar Works',account='Broker',shares=12.5,price=20.2,value=252.5,current=20,commission=2.5),
              row('trx',{'notes':'Cedar initial lot'},type='Withdrawal',amount=252.5,category='Investment:Purchase',number='CDR-BUY-1',link='Stock',
                  shares={'number':12.5,'price':20,'commission':2.5})]),
        step('price','Change the current share price of Cedar Works to 24.5, save and close the investment editor.',
             'The portfolio displays Cedar Works with an unrealized gain of 53.75 over its purchase cost.',
             [{'op':'button','window':MAIN,'name':'Edit'}, {'op':'fill','window':edit,'label':'Curr. Share Price','value':'24.5','commit':True},
              {'op':'button','window':edit,'name':'Save'}, {'op':'close','window':edit,'button':'Close'}],
             [row('stock',{'symbol':'CDR'},current=24.5),row('stock_history',{'symbol':'CDR','date':'2026-06-15'},value=24.5)],depends=['buy']),
        step('sell','For Cedar Works use Adjust Trade to sell 3.5 shares on 06/10/2026 for 25 per share with commission 1, so that the net deposit is 86.50. Check that net amount before saving; if the form retains a previous calculation, re-enter the price or commission to refresh it. Use Employer as payee, Investment:Sale as category, CDR-SELL-1 as number and Cedar partial sale as notes.',
             'The portfolio shows Cedar Works with 9 shares remaining after the sale.',
             [{'op':'button','window':MAIN,'name':'Adjust Trade'},
              {'op':'share-form','type':'Sell','shares':'3.5','price':'25','commission':'1','date':'06/10/2026','payee':'Employer',
               'category':'Investment:Sale','number':'CDR-SELL-1','notes':'Cedar partial sale'}],
             [row('stock',{'symbol':'CDR'},shares=9),row('trx',{'notes':'Cedar partial sale'},type='Deposit',amount=86.5,category='Investment:Sale',number='CDR-SELL-1',link='Stock')],depends=['price']),
        step('close-position','Sell the remaining 9 Cedar Works shares on 06/12/2026 for 24 per share with commission 1. Verify the net deposit is 215.00, refreshing the price or commission if needed. Use Employer, Investment:Sale, number CDR-SELL-2 and notes Cedar final sale.',
             'Cedar Works has no shares remaining after the final sale.',
             [{'op':'button','window':MAIN,'name':'Adjust Trade'},
              {'op':'share-form','type':'Sell','shares':'9','price':'24','commission':'1','date':'06/12/2026','payee':'Employer',
               'category':'Investment:Sale','number':'CDR-SELL-2','notes':'Cedar final sale'}],
             [row('stock',{'symbol':'CDR'},shares=0,value=0),row('trx',{'notes':'Cedar final sale'},type='Deposit',amount=215,
               category='Investment:Sale',shares={'number':-9,'price':24,'commission':1})],depends=['sell']),
    ],ledger='reports',navigator=REPORT_NAV,children=REPORT_CHILDREN,budget={'calls':320,'seconds':3600,'tokens':4000000}))
    result.append(episode('stock-history','stocks',[
        step('history','Edit Acme Corp in the Broker portfolio. Add the historical share price 63.25 for 06/10/2026, leaving the price history visible.',
             'The history shows June 10, 2026 at 63.25 alongside the existing price entries.',
             [{'op':'nav','path':['Stock Portfolios','Broker']}, {'op':'click','x':600,'y':220}, {'op':'button','window':MAIN,'name':'Edit'},
              {'op':'button','window':edit,'name':'Add'}, {'op':'fill','window':edit,'label':'Price Date','value':'06/10/2026','commit':True},
              {'op':'fill','window':edit,'label':'Price','value':'63.25','commit':True}, {'op':'button','window':edit,'name':'Add'}],
             [row('stock_history',{'symbol':'ACME','date':'2026-06-10'},value=63.25)],modal_end=True),
        step('update','Update the historical Acme Corp price for 06/10/2026 to 64.125.',
             'The price history shows the revised price 64.125 for June 10.',
             [{'op':'fill','window':edit,'label':'Price','value':'64.125','commit':True}, {'op':'button','window':edit,'name':'Add'}],
             [row('stock_history',{'symbol':'ACME','date':'2026-06-10'},value=64.125)],depends=['history'],modal_end=True),
    ],ledger='reports',navigator=REPORT_NAV,children=REPORT_CHILDREN))
    return result




def schedules():
    window='New Scheduled Transaction'
    match={'notes':'Summer utility plan'}
    return [episode('scheduled-manual','scheduled',[
        step('create','Create a manual monthly scheduled withdrawal in Everyday Checking: due and paid dates 06/20/2026, three payments left, payee City Power, category Bills:Electricity, amount 48.75, notes Summer utility plan. Leave both automatic execution options off.',
             'Scheduled Transactions lists the monthly City Power withdrawal of 48.75 due June 20.',
             [{'op':'nav','path':['Scheduled Transactions']}, {'op':'button','window':MAIN,'name':'New'},
              {'op':'fill','window':window,'label':'Date Due','value':'06/20/2026','commit':True},
              {'op':'fill','window':window,'label':'Date Paid','value':'06/20/2026','commit':True},
              {'op':'choose','window':window,'label':'Repeats','value':'Monthly','below':True},
              {'op':'fill','window':window,'label':'Payments Left','value':'3'},
              {'op':'fill','window':window,'label':'Account','value':'Everyday Checking','entry':True},
              {'op':'fill','window':window,'label':'Payee','value':'City Power','entry':True},
              {'op':'fill','window':window,'label':'Category','value':'Bills:Electricity','entry':True},
              {'op':'fill','window':window,'label':'Amount','value':'48.75','commit':True},
              {'op':'fill-described','window':window,'text':'Specify any text notes','value':'Summer utility plan'}, {'op':'close','window':window}],
             [row('sched',match,account='Everyday Checking',type='Withdrawal',payee='City Power',category='Bills:Electricity',amount=48.75,
                  date='2026-06-20',next_date='2026-06-20',repeats=3,occurrences=3)]),
        step('skip','Skip the next occurrence of Summer utility plan.',
             'The schedule advances to July 20.',
             [{'op':'click','x':600,'y':150}, {'op':'button','window':MAIN,'name':'Skip'}],
             [row('sched',match,date='2026-07-20',next_date='2026-07-20',occurrences=2),count('trx',match,0)],depends=['create']),
        step('enter','Enter the next occurrence of Summer utility plan, accepting the proposed transaction details.',
             'The schedule advances to August 20.',
             [{'op':'button','window':MAIN,'name':'Enter'}, {'op':'close','window':'Enter Scheduled Transaction'}],
             [row('sched',match,date='2026-08-20',next_date='2026-08-20',occurrences=1),
              row('trx',match,account='Everyday Checking',date='2026-07-20',amount=48.75,payee='City Power',category='Bills:Electricity')],depends=['skip']),
        step('delete','Delete the remaining Summer utility plan schedule and confirm, then open Everyday Checking to view the occurrence already entered.',
             'Everyday Checking still lists the posted City Power transaction for 48.75.',
             [{'op':'button','window':MAIN,'name':'Delete'}, {'op':'alert','button':'Yes'}, {'op':'nav','path':['Bank Accounts','Everyday Checking']}],
             [count('sched',match,0)],depends=['enter']),
    ])]


def build():
    return assets() + budgets() + stocks() + schedules()
