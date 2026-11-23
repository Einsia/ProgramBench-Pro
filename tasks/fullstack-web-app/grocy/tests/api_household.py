"""Chore schedules, execution history, batteries, tasks and calendar exports."""
from harness import Ref,pathref,resolve,subset,unordered
from common import foundation,fx,product,objpath,readback
from api_stock import route,entries,LOG_FIELDS

CHORE_FIELDS=['last_tracked','tracked_count','next_estimated_execution_time','average_execution_frequency_hours']
CHORE_LOG=['chore_id','tracked_time','done_by_user_id','undone','skipped','scheduled_execution_time']
BATTERY_FIELDS=['last_charged','charge_cycles_count','next_estimated_charge_time']


def build(s):
    f=foundation(s)
    variants=[('manual',{'period_type':'manually'}),('hourly',{'period_type':'hourly','period_interval':3}),
      ('daily',{'period_type':'daily'}),('two-days',{'period_type':'daily','period_interval':2}),
      ('weekly',{'period_type':'weekly','period_config':'monday,wednesday,friday'}),
      ('fortnightly',{'period_type':'weekly','period_config':'tuesday','period_interval':2}),
      ('monthly',{'period_type':'monthly','period_days':15}),('month-end',{'period_type':'monthly','period_days':31}),
      ('yearly',{'period_type':'yearly'}),('adaptive',{'period_type':'adaptive'}),
      ('date-only',{'period_type':'daily','track_date_only':1}),('rollover',{'period_type':'daily','rollover':1}),
      ('rescheduled',{'period_type':'daily','rescheduled_date':'2026-03-16 10:00:00'})]
    for name,extra in variants:
        s.needs=list(f['needs'])
        cf,ch=fx(s,name,'chores',{'name':'Chore '+name,'start_date':'2026-03-01 09:00:00','period_days':1,
                                'period_interval':1,'assignment_type':'no-assignment',**extra},'chore-'+name)
        s.needs=f['needs']+[cf];detail=pathref('chores/{id}',id=ch)
        s.api('chores',name,'schedule','GET',detail,fields=CHORE_FIELDS,hint='chores')
        a=s.api('chores',name,'execute-first','POST',pathref('chores/{id}/execute',id=ch),body={'tracked_time':'2026-03-03 08:30:00'},
                save='first-'+name,fields=CHORE_LOG,hint='chores_log',after=readback(detail,CHORE_FIELDS,{'tracked_count':1},hint='chores'))
        b=s.api('chores',name,'execute-second','POST',pathref('chores/{id}/execute',id=ch),body={'tracked_time':'2026-03-06 10:00:00','done_by':f['admin']},
                save='second-'+name,fields=CHORE_LOG,hint='chores_log',needs=[a],after=readback(detail,CHORE_FIELDS,{'tracked_count':2},hint='chores'))
        s.api('chores',name,'journal','GET','objects/chores_log',params={'query[]':pathref('chore_id={id}',id=ch)},
              fields=CHORE_LOG,hint='chores_log',needs=[b])
        undone=s.api('chores',name,'undo-latest','POST',pathref('chores/executions/{id}/undo',id=Ref('second-'+name,'id')),
                     body={},status=204,needs=[b],after=readback(detail,CHORE_FIELDS,{'tracked_count':1},hint='chores'))
        s.api('chores',name,'undo-again','POST',pathref('chores/executions/{id}/undo',id=Ref('second-'+name,'id')),body={},status=400,needs=[undone],requires=[b])
        skip=s.api('chores',name,'skip','POST',pathref('chores/{id}/execute',id=ch),body={'tracked_time':'2026-03-08 09:00:00','skipped':True},
                   status=400 if name=='manual' else 200,fields=None if name=='manual' else CHORE_LOG,hint='chores_log',needs=[undone],
                   after=readback(detail,CHORE_FIELDS,{'tracked_count':1},hint='chores'))
        s.api('chores',name,'unknown-user','POST',pathref('chores/{id}/execute',id=ch),body={'tracked_time':'2026-03-09 09:00:00','done_by':999999},status=400,requires=[a])
    # Chore execution can consume stock, with observable quantity changes.
    s.needs=list(f['needs'])
    pf,p=fx(s,'uses-product','products',product(f,'Cleaning liquid'),'cleaning-p')
    cf,ch=fx(s,'uses-product','chores',{'name':'Clean sink','period_type':'manually','consume_product_on_execution':1,
                                    'product_id':p,'product_amount':.5,'assignment_type':'no-assignment'},'cleaning-chore')
    s.needs=f['needs']+[pf,cf]
    a=s.api('chores','stock','purchase','POST',route(p,'/add'),body={'amount':4,'price':2},fields=LOG_FIELDS,hint='stock_log')
    a=s.api('chores','stock','execute','POST',pathref('chores/{id}/execute',id=ch),body={'tracked_time':'2026-03-10 08:00:00'},fields=CHORE_LOG,hint='chores_log',needs=[a],after=entries(p,3.5))
    # Merge preserves both histories and removes the old chore.
    mf,other=fx(s,'merge','chores',{'name':'Clean basin','period_type':'manually','assignment_type':'no-assignment'},'merge-chore')
    b=s.api('chores','merge','execute-other','POST',pathref('chores/{id}/execute',id=other),body={'tracked_time':'2026-03-08 07:00:00'},fields=CHORE_LOG,hint='chores_log',needs=[mf])
    merged=s.api('chores','merge','merge','POST',pathref('chores/{a}/merge/{b}',a=ch,b=other),body={},status=204,needs=[a,b],
                 after=readback(pathref('chores/{id}',id=ch),CHORE_FIELDS,{'tracked_count':2},hint='chores'))
    s.api('chores','merge','old-gone','GET',objpath('chores',other),status=404,needs=[merged],requires=[b])
    s.api('chores','merge','same-refused','POST',pathref('chores/{id}/merge/{id}',id=ch),body={},status=400,needs=[merged],requires=[a])
    # Recharge schedules cover unscheduled, overdue, future and leap-day arithmetic.
    for name,interval,first,second in [
      ('unscheduled',0,'2026-03-01 12:00:00','2026-03-05 13:30:00'),
      ('daily',1,'2026-03-08 12:00:00','2026-03-09 13:30:00'),
      ('fortnight',14,'2026-02-28 12:00:00','2026-03-05 13:30:00'),
      ('long-life',365,'2025-03-01 12:00:00','2026-03-05 13:30:00'),
      ('leap-day',2,'2024-02-28 12:00:00','2024-02-29 13:30:00')]:
        s.needs=list(f['needs']);bf,bt=fx(s,name,'batteries',{'name':'Battery '+name,'charge_interval_days':interval,'used_in':'Remote'},'battery-'+name)
        s.needs=f['needs']+[bf];detail=pathref('batteries/{id}',id=bt)
        s.api('batteries',name,'initial','GET',detail,fields=BATTERY_FIELDS,hint='batteries')
        a=s.api('batteries',name,'charge-first','POST',pathref('batteries/{id}/charge',id=bt),body={'tracked_time':first},save='battery-first-'+name,
                hint='battery_charge_cycles',after=readback(detail,BATTERY_FIELDS,{'charge_cycles_count':1},hint='batteries'))
        b=s.api('batteries',name,'charge-second','POST',pathref('batteries/{id}/charge',id=bt),body={'tracked_time':second},save='battery-second-'+name,
                hint='battery_charge_cycles',needs=[a],after=readback(detail,BATTERY_FIELDS,{'charge_cycles_count':2},hint='batteries'))
        s.api('batteries',name,'history','GET','objects/battery_charge_cycles',params={'query[]':pathref('battery_id={id}',id=bt)},
              fields=['battery_id','tracked_time','undone'],hint='battery_charge_cycles',needs=[b])
        undo=s.api('batteries',name,'undo-last','POST',pathref('batteries/charge-cycles/{id}/undo',id=Ref('battery-second-'+name,'id')),
                   body={},status=204,needs=[b],after=readback(detail,BATTERY_FIELDS,{'charge_cycles_count':1,'last_charged':first},hint='batteries'))
        s.api('batteries',name,'repeat-undo','POST',pathref('batteries/charge-cycles/{id}/undo',id=Ref('battery-second-'+name,'id')),
              body={},status=400,needs=[undo],requires=[b])
        inactive=s.api('batteries',name,'deactivate','PUT',objpath('batteries',bt),body={'active':0},status=204,needs=[undo])
        s.api('batteries',name,'inactive-details','GET',detail,fields=BATTERY_FIELDS,hint='batteries',needs=[inactive])
    # Task completion uses explicit instants; undo restores the incomplete state.
    for name,extra in [('undated',{}),('overdue',{'due_date':'2026-03-01 09:00:00'}),('today',{'due_date':'2026-03-10 13:00:00'}),
                       ('future',{'due_date':'2026-04-01 14:00:00'}),('assigned',{'assigned_to_user_id':f['admin'],'category_id':f['cat']})]:
        s.needs=list(f['needs']);tf,t=fx(s,name,'tasks',{'name':'Task '+name,'description':'Household reminder',**extra},'task-'+name)
        s.needs=f['needs']+[tf];path=objpath('tasks',t)
        a=s.api('tasks',name,'complete','POST',pathref('tasks/{id}/complete',id=t),body={'done_time':'2026-03-10 08:45:00'},status=204,
                after=readback(path,['name','done','done_timestamp','due_date','category_id','assigned_to_user_id'],{'done':1,'done_timestamp':'2026-03-10 08:45:00'},hint='tasks'))
        s.api('tasks',name,'current-filter','GET','tasks',params={'query[]':pathref('id={id}',id=t)},hint='tasks',needs=[a])
        b=s.api('tasks',name,'undo','POST',pathref('tasks/{id}/undo',id=t),body={},status=204,needs=[a],after=readback(path,['done','done_timestamp'],{'done':0,'done_timestamp':None}))
        c=s.api('tasks',name,'complete-again','POST',pathref('tasks/{id}/complete',id=t),body={'done_time':'2026-03-11 09:15:00'},status=204,needs=[b],after=readback(path,['done','done_timestamp'],{'done':1,'done_timestamp':'2026-03-11 09:15:00'}))
        s.api('tasks',name,'change-due','PUT',path,body={'due_date':'2026-04-15 15:00:00'},status=204,needs=[c],after=readback(path,['done','due_date'],{'done':1,'due_date':'2026-04-15 15:00:00'}))
    s.needs=[]
    for entity,op in [('chores','execute'),('batteries','charge'),('tasks','complete'),('tasks','undo')]:
        s.api('household','missing',entity+'-'+op,'POST',entity+'/999999/'+op,body={},status=400)
    s.api('household','overview','chores','GET','chores',hint='chores')
    s.api('household','overview','batteries','GET','batteries',hint='batteries')
    s.api('household','overview','tasks','GET','tasks',hint='tasks')
