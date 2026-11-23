"""Interactive user goals. Recipes are used only to record the real upstream program."""
from datetime import datetime, timedelta
from spec_common import *
from fixtures import apt, event, ui, NOTE, AGENDA, ical, vevent, vtodo


def replace(text):
    return S(KS('Control+A', 'Control+K'), answer(text))


def goto(date):
    return S(K('g'), replace(date))


def command(text):
    return S(K(':'), answer(text))


def add_appt(start, end, text):
    return S(K('a'), answer(start), answer(end), answer(text), SAVE)


def add_event(text):
    return S(K('a'), K('Enter'), answer(text), SAVE)


def goal(cid, text, recipe, acceptance, check=None, depends=()):
    checks = [('state', 'The resulting public state reflects this goal.', check)] if check else []
    return step(cid, text, recipe, checks, acceptance=acceptance, depends=depends,
                requires={'done': ['state']} if check else None)


def chain(cps):
    for i in range(1, len(cps)):
        cps[i]['depends_on'].append(cps[i-1]['id'])
    return cps


def setting_steps(index, value=None, presses=1, visible=True):
    enter = S(KS('C','g'), KS(*(['j']*index)) if index else [])
    change = [K('e')]*presses
    if value is not None:
        change += replace(value)
    # Configuration is saved when leaving its menu. Reopen it to show the final value.
    return S(enter, change, KS('q','q'), enter if visible else [])


def build():
    out=[]
    for name, entries in [
        ('clock-times', [('09:00','10:30','Planning'),('14:15','15:00','Review'),('18:05','','Check-in'),('23:30','00:15','Night watch')]),
        ('durations', [('08:00','+45','Breakfast'),('11:00','+01:30','Workshop'),('16:00','+2h15m','Lab session'),('20:00','+1d2h','Long trip')]),
    ]:
        cps=[]
        for i,(start,end,label) in enumerate(entries):
            wording=('no duration' if not end else ('duration '+end[1:] if end.startswith('+') else 'ending at '+end))
            cps.append(goal('add-'+str(i+1),f'Add and save an appointment today starting at {start}, {wording}, named "{label}".',
                            add_appt(start,end,label),
                            (f'The appointment list shows {label} continuing into the following day.'
                             if end == '+1d2h' or (end and not end.startswith('+') and end < start)
                             else f'The appointment list shows {label} with the requested time span.'),apts()))
        out.append(gui('gui-add-'+name,'appointments',ui(),chain(cps)))

    cps=[]
    for i,label in enumerate(['Company holiday','Réunion 東京','Punctuation: A & B / C']):
        cps.append(goal('event-'+str(i+1),'Add and save an all-day event today named "'+label+'".',add_event(label),
                        'The selected day shows the all-day event '+label+'.',apts()))
    out.append(gui('gui-add-events','events',ui(),chain(cps)))

    out.append(gui('gui-edit-appointment','appointments',ui(apts=[apt(text='Draft')]),chain([
        goal('description','Rename Draft to "Team planning" and save.',S(KS('e','3'),replace('Team planning'),SAVE),
             'The appointment is named Team planning.',apts()),
        goal('end','Extend Team planning to end at 12:15 today and save.',S(KS('e','2'),replace('12:15'),SAVE),
             'Team planning now runs from 10:00 to 12:15.',apts()),
        goal('start','Change its start to 09:30, keeping the end at 12:15, and save.',S(KS('e','1'),replace('09:30'),SAVE),
             'Team planning now starts at 09:30 and ends at 12:15.',apts()),
        goal('move','Move it to start at 14:00 today while preserving its 2-hour 45-minute duration; save.',
             S(KS('e','4'),replace('14:00'),SAVE),'Team planning runs from 14:00 to 16:45.',apts()),
    ])))
    out.append(gui('gui-event-edit-copy','events',ui(apts=[event(text='Draft holiday')]),chain([
        goal('rename','Rename Draft holiday to "Spring holiday" and save.',S(K('e'),replace('Spring holiday'),SAVE),
             'The all-day event is named Spring holiday.',apts()),
        goal('copy','Copy Spring holiday to March 20, 2026, retain the original, and save.',
             S(K('c'),goto('03/20/2026'),K('p'),SAVE),'March 20 shows Spring holiday.',apts()),
        goal('rename-copy','Rename the March 20 copy to "Spring break" and save.',S(K('e'),replace('Spring break'),SAVE),
             'March 20 shows Spring break.',apts()),
        goal('original','Display the original event on March 18, 2026.',goto(TODAY),
             'March 18 still shows Spring holiday.',scr('contains',needles=['Spring holiday'])),
    ])))
    out.append(gui('gui-copy-appointment','appointments',ui(apts=[apt(minutes=90,text='Consultation')]),chain([
        goal('copy','Copy Consultation to March 19, 2026, retain the original and save.',
             S(K('c'),goto('03/19/2026'),K('p'),SAVE),'March 19 shows Consultation from 10:00 to 11:30.',apts()),
        goal('shift-copy','Move the copied appointment to 15:00 while preserving its duration, then save.',
             S(KS('e','4'),replace('15:00'),SAVE),'March 19 shows Consultation from 15:00 to 16:30.',apts()),
        goal('original','Display the original appointment on March 18.',goto(TODAY),
             'March 18 shows Consultation from 10:00 to 11:30.',scr('contains',needles=['Consultation','10:00','11:30'])),
    ])))

    for period,next_date,last_date in [('d','03/19/2026','03/20/2026'),('w','03/25/2026','04/01/2026'),
                                       ('m','04/18/2026','05/18/2026'),('y','03/18/2027','03/18/2028')]:
        word={'d':'daily','w':'weekly','m':'monthly','y':'yearly'}[period]
        label=word.title()+' reminder'
        recurrence_state = apts('recurrence-equivalent')
        out.append(gui('gui-repeat-'+word,'recurrence',ui(apts=[apt(text=label)]),chain([
            goal('repeat',f'Make {label} repeat {word}, every one period, for exactly three occurrences; save.',
                 S(KS('r','s',period),K('Enter'),answer('#3'),SAVE),
                 f'{label} is shown as a repeating appointment.',recurrence_state),
            goal('next',f'Display the next occurrence of {label}, on {next_date}.',command('next'),
                 f'The selected date is {next_date} and its list shows {label}.',scr('contains',needles=[label])),
            goal('exception',f'Delete only the occurrence on {next_date}, save, then display the remaining occurrence on {last_date}.',
                 S(KS('d','s'),SAVE,goto(last_date)),f'The remaining occurrence of {label} is visible on {last_date}.',recurrence_state),
        ])))

    for name,period,weekdays,months,monthdays,start_date,next_date in [
        ('workdays','d','Mon Tue Wed Thu Fri','','','2026-03-18','03/19/2026'),
        ('first-last-monday','m','1Mon -1Mon','','','2026-03-02','03/30/2026'),
        ('month-end','m','','','-1','2026-03-31','04/30/2026'),
    ]:
        out.append(gui('gui-advanced-'+name,'recurrence',ui(apts=[event(start_date,text='Schedule')]),chain([
            goal('rule',f'Make Schedule on {start_date} repeat with base period {period.upper()}, interval 1, no end date, '
                 f'weekdays "{weekdays}", months "{months}", and month days "{monthdays}" (blank means unrestricted); save.',
                 S(goto(datetime.strptime(start_date,'%Y-%m-%d').strftime('%m/%d/%Y')),
                   KS('r','a',period),K('Enter'),K('Enter'),answer(weekdays),answer(months),answer(monthdays),SAVE),
                 'Schedule is now a repeating all-day event.',apts()),
            goal('view','Display Schedule on '+next_date+'.',goto(next_date),
                 'The requested occurrence of Schedule is visible.',scr('contains',needles=['Schedule'])),
        ])))

    # Todos are edited with the same normal interface; completion, priority and ordering are user-visible.
    for name,items in [('priorities',[(1,'Urgent bill'),(5,'Weekly shopping'),(9,'Someday project'),(0,'Unranked thought')]),
                       ('text',[(3,'Réviser le budget'),(4,'東京の予約'),(2,'Milk, bread; eggs')])]:
        cps=[]
        for i,(priority,label) in enumerate(items):
            cps.append(goal('task-'+str(i+1),f'Add and save a todo "{label}" with priority {priority}.',
                            S(K('a'),answer(label),K(str(priority)),SAVE),
                            (f'The todo list shows {label} at priority {priority}.' if priority else f'The todo list shows {label} as an unranked task.'),todos()))
        out.append(gui('gui-todo-'+name,'todos',ui(panel='todo'),chain(cps)))
    out.append(gui('gui-todo-edit','todos',ui(todo=['[5] Draft task'],panel='todo'),chain([
        goal('rename','Rename Draft task to "Submit report" and save.',S(K('e'),replace('Submit report'),SAVE),
             'The todo is named Submit report.',todos()),
        goal('raise','Change Submit report to priority 3 and save.',S(KS('-','-'),SAVE),
             'Submit report is visible with priority 3.',dict(todos(),required_line='[3] Submit report')),
        goal('lower','Change Submit report to priority 4 and save.',S(K('+'),SAVE),
             'Submit report is visible with priority 4.',dict(todos(),required_line='[4] Submit report')),
        goal('complete','Complete Submit report, save, and switch to showing completed tasks.',
             S(K('!'),SAVE,setting_steps(3,visible=False)),
             'Submit report is visible as completed.',dict(todos(),required_line='[-4] Submit report')),
        goal('reopen','Reopen Submit report and save.',S(K('!'),SAVE),
             'Submit report is visible as an unfinished priority-4 task.',dict(todos(),required_line='[4] Submit report')),
    ])))

    out.append(gui('gui-delete-and-restore','events',ui(apts=[event(text='Keep me'),event(text='Remove me')]),chain([
        goal('remove','Delete Remove me, retain Keep me, and save.',S(K('j'),KS('d','s'),SAVE),
             'Keep me remains visible as the retained all-day event.',apts()),
        goal('restore','Paste the deleted event into March 19, 2026 and save.',S(goto('03/19/2026'),K('p'),SAVE),
             'March 19 shows the restored Remove me event.',apts()),
    ])))
    out.append(gui('gui-notify-flag','notifications',ui(apts=[apt(text='Reminder')]),chain([
        goal('flag','Mark Reminder as important for notification and save.',S(K('!'),SAVE),
             'Reminder is visibly marked as important.',apts()),
        goal('copy-flag','Copy the marked Reminder to tomorrow and save.',S(K('c'),goto('03/19/2026'),K('p'),SAVE),
             'Tomorrow shows the copied Reminder with its importance mark.',apts()),
    ])))

    # Every navigation target contains a distinct event, making the chosen day observable without fixed columns.
    nav_groups = [
        ('nearby',[('t','2026-03-19'),('T','2026-03-18'),('w','2026-03-25'),('W','2026-03-18')]),
        ('months',[('m','2026-04-18'),('M','2026-03-18'),('y','2027-03-18'),('Y','2026-03-18')]),
        ('week-edges',[('0','2026-03-16'),('$','2026-03-22'),('Control+G','2026-03-18')]),
    ]
    for name,targets in nav_groups:
        dates=sorted(set(date for _,date in targets))
        cps=[]
        for i,(key,date) in enumerate(targets):
            label='Visit '+date
            cps.append(goal('date-'+str(i+1),'Select '+date+' and display its event.',[K(key)],
                            label+' is visible for the selected day.',scr('contains',needles=[label])))
        out.append(gui('gui-navigation-'+name,'navigation',ui(apts=[event(d,'Visit '+d) for d in dates],panel='calendar'),chain(cps)))
    dates=['2028-02-29','2026-12-31','2027-01-01','2026-03-18']
    out.append(gui('gui-navigation-goto','navigation',ui(apts=[event(d,'Date '+d) for d in dates]),chain([
        goal('goto-'+str(i+1),'Go to '+d+' and display its event.',goto(datetime.strptime(d,'%Y-%m-%d').strftime('%m/%d/%Y')),
             'Date '+d+' is visible for the selected day.',scr('contains',needles=['Date '+d]))
        for i,d in enumerate(dates)])))

    # Configuration goals use visible values and saved settings, rather than exact geometry or colours.
    options=[(0,'appearance.compactpanels','yes',None),(2,'appearance.calendarview','weekly',None),
             (3,'appearance.todoview','show-completed',None),(4,'general.multipledays','yes',None),
             (9,'appearance.emptyday','No appointments','No appointments'),
             (10,'general.autosave','no',None),(11,'general.autogc','yes',None),
             (12,'general.periodicsave','15','15'),(14,'general.confirmquit','no',None),
             (15,'general.confirmdelete','no',None),(16,'general.firstdayofweek','sunday',None),
             (17,'format.outputdate','%Y-%m-%d','%Y-%m-%d'),
             (20,'format.dayheading','%A %Y-%m-%d','%A %Y-%m-%d'),
             (21,'format.appointmenttime','%I:%M %p','%I:%M %p')]
    for index,key,value,input_value in options:
        out.append(gui('gui-config-'+slug(key),'configuration',ui(apts=[apt(text='Example')],todo=['[-3] Closed']),[
            goal('set','Set '+key+' to "'+value+'". Leave general options, then exit the configuration menu '
                 'to return to the organizer and save the setting. Reopen general options and leave its current value visible.',
                 setting_steps(index,input_value,presses=6 if key == 'general.firstdayofweek' else 1),
                 'The setting has been saved by returning to the organizer, and general options has been reopened '
                 'to show the requested value for '+key+'.',conf(key))]))

    # Notes remain product data even though external note editing is unavailable.
    out.append(gui('gui-note-copy-remove','notes',ui(apts=[apt(text='With note',note=NOTE)],notes=[NOTE]),chain([
        goal('copy','Copy With note, including its note, to March 19 and save.',S(K('c'),goto('03/19/2026'),K('p'),SAVE),
             'March 19 shows With note with a note indicator.',apts()),
        goal('detach','Remove only the note from the March 19 copy, retain the appointment and save.',S(KS('d','n'),SAVE),
             'The March 19 appointment remains visible without an attached note.',apts()),
        goal('original','Display the original appointment on March 18.',goto(TODAY),
             'The original With note appointment still shows an attached note.',scr('contains',needles=['With note'])),
    ])))

    # Import/export use ordinary product prompts. No non-GUI evaluator bypass is available.
    imported=ical(vevent('DTSTART:20260318T143000\nDTEND:20260318T153000\nSUMMARY:Imported review')+'\n'+
                  vtodo('SUMMARY:Imported task\nPRIORITY:2'))
    out.append(gui('gui-import','icalendar',ui(files={'exchange.ics':imported}),[
        goal('import','Import the file exchange.ics from the home directory, dismiss its result message, and save.',
             S(K('i'),answer('exchange.ics'),K('Enter'),SAVE),
             'The calendar shows Imported review from 14:30 to 15:30 and the todo list shows Imported task.',apts()),
    ]))

    # Persistence combines visible results with a framework restart of the saved data.
    out.append(gui('gui-persistence','persistence',ui(),[
        goal('create','Create and save an all-day event today named "Persistent event".',add_event('Persistent event'),
             'Persistent event is shown for today.',apts()),
        step('reopen','The application has already been restarted for you before this checkpoint. Display today\'s Persistent event.',[],
             [('state','The saved event survives a fresh application process.',apts())],
             acceptance='Persistent event is visible after the restart.',depends=['create'],lifecycle='restart',requires={'done':['state']}),
    ]))
    out.append(gui('gui-recur-edit','recurrence',ui(apts=[apt(text='Weekly draft',rule='1W')]),chain([
        goal('rename','Rename the repeating Weekly draft series to "Team sync" and save.',
             S(KS('e','3'),replace('Team sync'),SAVE),'The repeating appointment is named Team sync.',apts()),
        goal('length','Make every Team sync occurrence end at 11:45 and save.',S(KS('e','2'),replace('11:45'),SAVE),
             'Team sync is shown from 10:00 to 11:45.',apts()),
        goal('next','Display its next weekly occurrence on March 25.',command('next'),
             'March 25 shows Team sync from 10:00 to 11:45.',scr('contains',needles=['Team sync','11:45'])),
    ])))
    out.append(gui('gui-remove-series','recurrence',ui(apts=[event(text='Recurring',rule='1D'),event(text='Retained')]),chain([
        goal('delete-all','Delete the entire Recurring series, retain Retained and save.',S(KS('d','a'),SAVE),
             'Retained is the remaining all-day event for today.',apts()),
        goal('new','Add and save a replacement all-day event today named "New plan".',add_event('New plan'),
             'Today shows New plan and Retained.',apts()),
    ])))
    out.append(gui('gui-todo-delete','todos',ui(todo=['[1] Discard','[3] Keep'],panel='todo'),chain([
        goal('delete','Delete the Discard todo, retain Keep, and save.',S(KS('d','y'),SAVE),
             'Keep remains in the todo list.',todos()),
        goal('new','Add and save a new priority-2 todo named "Replacement".',S(K('a'),answer('Replacement'),K('2'),SAVE),
             'Replacement and Keep are both visible.',todos()),
    ])))
    out.append(gui('gui-calendar-views','navigation',ui(apts=[apt(text='Visible meeting')],panel='calendar'),chain([
        goal('weekly','Switch the calendar to its weekly view.',[K('Control+N')],
             'The calendar shows the days of the current week with appointment time slots.'),
        goal('monthly','Return to the monthly calendar view.',[K('Control+P')],
             'The calendar shows the March 2026 month grid.'),
    ])))
    for fmt,date,label in [(2,'20/03/2026','European date'),(4,'2026-03-20','ISO date')]:
        out.append(gui('gui-input-format-'+str(fmt),'configuration',ui(conf={'format.inputdate':str(fmt)},
                           apts=[event('2026-03-20',label)]),chain([
            goal('date','Using the configured date format, select March 20, 2026.',goto(date),
                 label+' is visible for March 20.',scr('contains',needles=[label])),
            goal('add','Add and save an all-day event on that date named "Date format test".',add_event('Date format test'),
                 'March 20 shows Date format test.',apts()),
        ])))
    long_text='Detailed plan: review the quarterly budget with the regional team, then confirm the launch checklist and delivery date.'
    out.append(gui('gui-view-detail','display',ui(apts=[apt(text=long_text)]),[
        goal('detail','Display the complete description of the Detailed plan appointment.',[K('v')],
             'The full description is visible, including the launch checklist and delivery date.')]))
    return out
