"""Tracking, history and task episodes on the visible household management pages."""
from specification import api,read,step
from gui_common import base,go,button,fill


def choose(name):return {'op':'choose','value':name,'target':{'tag':'input','type':'text','nth':0}}
def tracked(value):return {'op':'fill','target':{'tag':'input','type':'text','nth':1},'value':value}


def build(add):
    setup=[api('chore','POST','objects/chores',{'name':'Sweep floor','period_type':'daily','period_interval':1,'start_date':'2026-03-01 09:00:00','assignment_type':'no-assignment'},save='chore')]
    add('gui-chore-tracking','chore tracking',setup,[
      step('track','Record that Sweep floor was performed on 2026-03-10 at 08:30:00, then show its execution journal.',
           'The chore journal visibly contains Sweep floor executed at the requested time.',
           [go('/choretracking'),choose('Sweep floor'),tracked('2026-03-10 08:30:00'),button('OK'),go('/choresjournal')],
           checks=[read('chores/{{chore.created_object_id}}',fields=['tracked_count','last_tracked'],expected={'tracked_count':1,'last_tracked':'2026-03-10 08:30:00'})],visible=['Sweep floor','2026-03-10 08:30:00']),
      step('again','Record a second execution of Sweep floor on 2026-03-11 at 09:00:00. Show its execution journal.',
           'Both executions of Sweep floor are visible with their respective times.',
           [go('/choretracking'),choose('Sweep floor'),tracked('2026-03-11 09:00:00'),button('OK'),go('/choresjournal')],
           checks=[read('chores/{{chore.created_object_id}}',fields=['tracked_count'],expected={'tracked_count':2})],visible=['2026-03-10 08:30:00','2026-03-11 09:00:00'],depends=['track']),
      step('undo','Undo the latest Sweep floor execution and show the chore overview.',
           'The chore overview visibly reflects the remaining execution and its next due time.',
           [go('/choresjournal'),{'op':'click','target':{'title':'Undo chore execution','nth':0}},go('/choresoverview')],
           checks=[read('chores/{{chore.created_object_id}}',fields=['tracked_count','last_tracked'],expected={'tracked_count':1,'last_tracked':'2026-03-10 08:30:00'})],visible=['Sweep floor'],depends=['again']),
      step('reschedule','Reschedule Sweep floor to 2026-03-15 at 10:00:00 and show the chore overview.',
           'Sweep floor visibly has its next due time on 2026-03-15 at 10:00:00.',
           [go('/choresoverview'),{'op':'click','target':{'tag':'button','type':'button'}},button('Reschedule next execution'),
            {'op':'fill','target':{'tag':'input','type':'text','nth':1},'value':'2026-03-15 10:00:00'},button('OK'),go('/choresoverview')],
           checks=[read('objects/chores/{{chore.created_object_id}}',fields=['rescheduled_date'],expected={'rescheduled_date':'2026-03-15 10:00:00'})],visible=['Sweep floor','2026-03-15'],depends=['undo']),
    ])
    setup=[api('battery','POST','objects/batteries',{'name':'Remote AA','charge_interval_days':7,'used_in':'Remote'},save='battery')]
    add('gui-battery-tracking','battery tracking',setup,[
      step('charge','Record a charge of Remote AA at 2026-03-10 08:00:00 and show its charging journal.',
           'The charging journal visibly records Remote AA charged at the requested time.',
           [go('/batterytracking'),choose('Remote AA'),tracked('2026-03-10 08:00:00'),button('OK'),go('/batteriesjournal')],
           checks=[read('batteries/{{battery.created_object_id}}',fields=['charge_cycles_count','last_charged'],expected={'charge_cycles_count':1,'last_charged':'2026-03-10 08:00:00'})],visible=['Remote AA','2026-03-10 08:00:00']),
      step('next-charge','Show the battery overview to inspect when Remote AA should next be charged.',
           'Remote AA visibly has its next estimated charge on 2026-03-17.',
           [go('/batteriesoverview')],checks=[],visible=['Remote AA','2026-03-17'],depends=['charge']),
      step('second-charge','Record another charge of Remote AA at 2026-03-10 08:30:00 and show its journal.',
           'Both charge cycles are visible in the journal.',
           [go('/batterytracking'),choose('Remote AA'),tracked('2026-03-10 08:30:00'),button('OK'),go('/batteriesjournal')],
           checks=[read('batteries/{{battery.created_object_id}}',fields=['charge_cycles_count'],expected={'charge_cycles_count':2})],visible=['2026-03-10 08:30:00','2026-03-10 08:00:00'],depends=['charge']),
      step('undo','Undo the latest charge cycle for Remote AA and show the battery overview.',
           'Remote AA visibly returns to a next estimated charge on 2026-03-17.',
           [go('/batteriesjournal'),{'op':'click','target':{'title':'Undo charge cycle','nth':0}},go('/batteriesoverview')],
           checks=[read('batteries/{{battery.created_object_id}}',fields=['charge_cycles_count','last_charged'],expected={'charge_cycles_count':1,'last_charged':'2026-03-10 08:00:00'})],visible=['Remote AA','2026-03-17'],depends=['second-charge']),
    ])
    setup=[api('category','POST','objects/task_categories',{'name':'Finance'},save='category'),
           api('retained','POST','objects/tasks',{'name':'Keep receipt'},save='retained')]
    add('gui-tasks','task completion and organization',setup,[
      step('create','Create task "Pay bill" with description "Electricity invoice", due 2026-03-12, in category Finance. Save it.',
           'Pay bill is visible with its due date and Finance category.',
           [go('/task/new'),fill('name','Pay bill'),fill('description','Electricity invoice'),
            {'op':'fill','target':{'tag':'input','type':'text','nth':1},'value':'2026-03-12'},
            {'op':'select','target':{'name':'category_id'},'value':'Finance'},button('Save & close'),
            {'op':'save-named','entity':'tasks','name':'Pay bill','save':'task'},go('/tasks')],
           checks=[read('objects/tasks',fields=['name','description','due_date','category_id'],where={'name':'Pay bill'},
             expected={'name':'Pay bill','description':'Electricity invoice','due_date':'2026-03-12','category_id':'{{category.created_object_id}}'},save='task')],visible=['Pay bill','Finance','2026-03-12']),
      step('complete','Mark Pay bill as completed and show completed tasks.',
           'Pay bill is visibly marked completed.',
           [go('/tasks'),{'op':'fill','target':{'placeholder':'Search'},'value':'Pay bill'},
            {'op':'click','target':{'title':'Mark task as completed'}},{'op':'check','target':{'label':'Show done tasks'},'value':True}],
           checks=[read('objects/tasks/{{task.id}}',fields=['done'],expected={'done':1})],visible=['Pay bill'],depends=['create']),
      step('undo','Undo completion of Pay bill so it is an unfinished task again.',
           'Pay bill is visibly an unfinished task again.',
           [{'op':'click','target':{'title':'Undo task'}}],
           checks=[read('objects/tasks/{{task.id}}',fields=['done'],expected={'done':0})],visible=['Pay bill'],depends=['complete']),
      step('edit','Change Pay bill description to "Paid by transfer tomorrow" and save it.',
           'The saved task details show the updated description.',
           [{'op':'edit-named','entity':'tasks','name':'Pay bill','prefix':'/task'},fill('description','Paid by transfer tomorrow'),button('Save'),
            {'op':'edit-named','entity':'tasks','name':'Pay bill','prefix':'/task'}],
           checks=[read('objects/tasks/{{task.id}}',fields=['description'],expected={'description':'Paid by transfer tomorrow'})],depends=['undo']),
      step('delete','Delete Pay bill while retaining Keep receipt.',
           'Pay bill is absent and Keep receipt remains in the task list.',
           [{'op':'delete-named','entity':'tasks','name':'Pay bill','prefix':'/task','list':'/tasks'}],
           checks=[read('objects/tasks',fields=['name'],collection=True,expected=[{'name':'Keep receipt'}])],visible=['Keep receipt'],depends=['edit'],requires=['create/visible']),
    ])
