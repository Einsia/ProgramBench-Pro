"""Documented date shorthands and keyboard arithmetic, checked through saved tasks."""
from specification import read,step
from gui_common import go,button,fill

TARGET={'tag':'input','type':'text','nth':1}
def due(value):return {'op':'fill','target':TARGET,'value':value}

SHORTHANDS=[
 ('mmdd','0315','2026-03-15'),('roll-year','0102','2027-01-02'),
 ('compact','20260417','2026-04-17'),('month-end','202602e','2026-02-28'),
 ('leap-month','202402+','2024-02-29'),('relative-month','+1m','2026-04-10'),
 ('relative-days','-2d','2026-03-08'),('relative-year','+1y','2027-03-10'),
 ('never','x','2999-12-31')]
ARROWS=[
 ('day-forward','2026-01-31','ArrowDown','2026-02-01'),('day-back','2026-03-01','ArrowUp','2026-02-28'),
 ('week-forward','2026-12-28','ArrowRight','2027-01-04'),('week-back','2026-01-03','ArrowLeft','2025-12-27'),
 ('month-forward','2026-01-31','Shift+ArrowDown','2026-02-28'),('month-back','2024-03-31','Shift+ArrowUp','2024-02-29'),
 ('year-forward','2024-02-29','Shift+ArrowRight','2025-02-28'),('year-back','2025-03-01','Shift+ArrowLeft','2024-03-01')]

def build(add):
    for group,rows in [('short-form',SHORTHANDS[:5]),('relative',SHORTHANDS[5:]),('keyboard-days',ARROWS[:4]),('keyboard-months',ARROWS[4:])]:
        cps=[]
        for row in rows:
            key,entered,*rest=row;expected=rest[-1];name='Date '+key
            if len(row)==3:
                goal='Create task "'+name+'" using `'+entered+'` as its due-date input, then save it.'
                operations=[due(entered)]
            else:
                chord=rest[0]
                goal='Create task "'+name+'". Set due date to '+entered+', apply '+chord+' in the due-date field, then save it.'
                operations=[due(entered),{'op':'press','target':TARGET,'key':chord}]
            acceptance=('The task visibly has no due deadline.' if key=='never' else 'The saved task visibly shows due date '+expected+'.')
            cps.append(step(key,goal,acceptance,[go('/task/new'),fill('name',name),*operations,button('Save & close'),go('/tasks')],
                checks=[read('objects/tasks',fields=['name','due_date'],where={'name':name},expected={'name':name,'due_date':expected})],
                visible=[name,'Never' if key=='never' else expected]))
        add('gui-dates-'+group,'date input '+group,[],cps)
