"""Frontend goals: user goals the evaluator carries out in the running application with keys and typed text.

Every episode starts the application on a prepared Taskwarrior database (the main fixture unless stated). A goal
gives exact inputs and the visible result to reach; each checkpoint carries one evaluator-judged point and backend
companions (the exported tasks or screen facts), so an inert shell cannot pass. Equivalent keys, prompts and menus
are accepted. The expected values come from the frozen reference; the requirement text describes the behaviour and
must also hold for an equivalent reimplementation.
"""
from spec_core import *
from spec_data import MAIN, TRIO

MAIN_SESSION = SESSION + (' The database holds these pending tasks (ID, description): 1 Pay rent, 2 Write report, '
                          '3 Call plumber, 4 Review PR (started), 5 Buy groceries, 6 Plan trip, 7 Renew passport '
                          '(waiting until June), 8 Read book, 9 Fix bike (depends on 5), 10 Water plants, '
                          '11 Learn piano, 12 Team lunch; plus one completed and one deleted task.')
TRIO_SESSION = SESSION + (' The database holds three pending tasks: 1 Alpha task (project Alpha), 2 Beta task (project '
                          'Beta, tag beta) and 3 Gamma task (priority M).')


def goal(cid, text, steps, checks, accept, depends=(), bound=None):
    return step(cid, text, steps, checks, depends=depends, acceptance=accept,
                requires={'done': [c[0] for c in checks], **(bound or {})})


def wf(key_, feature, tasks, checkpoints, names=(), config=(), session=None):
    session = session or (MAIN_SESSION if tasks is MAIN else TRIO_SESSION if tasks is TRIO else SESSION)
    return gui(key_, feature, fixture(tasks, config), checkpoints, names=names, session=session)


def adds():
    return [
        wf('gui-add-basic', 'add', TRIO, [
            goal('simple', 'Add a task with the description `Call grandma`.', add('Call grandma'),
                 [('task', 'The task exists with that description.', ex(['Call grandma'], 'status', 'project', 'tags'))],
                 'A new task "Call grandma" appears in the task report.'),
            goal('project-tag', 'Add a task `Buy paint` in the project `Home.Garage` with the tag `diy`.',
                 add('Buy paint', 'project:Home.Garage +diy'),
                 [('task', 'The task has the project and the tag.', ex(['Buy paint'], 'project', 'tags'))],
                 'The report lists "Buy paint" with the project Home.Garage and the tag diy.', depends=['simple']),
        ], names=['Call grandma', 'Buy paint']),
        wf('gui-add-dates', 'add', TRIO, [
            goal('tomorrow', 'Add a task `Return books` that is due tomorrow.', add('Return books', 'due:tomorrow'),
                 [('task', 'The task is due tomorrow (2026-05-14).', ex(['Return books'], 'due'))],
                 'The report lists "Return books", and its details show the due date 2026-05-14.'),
            goal('eom', 'Add a task `Send invoice` due at the end of the month (the date expression `eom`).',
                 add('Send invoice', 'due:eom'),
                 [('task', 'The task is due at the end of May 2026.', ex(['Send invoice'], 'due'))],
                 'The report lists "Send invoice", and its details show the due date 2026-05-31.',
                 depends=['tomorrow']),
        ], names=['Return books', 'Send invoice']),
        wf('gui-add-priority', 'add', TRIO, [
            goal('high', 'Add a task `Fix leak` with priority H.', add('Fix leak', 'priority:H'),
                 [('task', 'The task has priority H.', ex(['Fix leak'], 'priority'))],
                 'The report lists "Fix leak" with priority H.'),
            goal('low-tag', 'Add a task `Sort mail` with priority L and the tag `admin`.',
                 add('Sort mail', 'priority:L +admin'),
                 [('task', 'The task has priority L and the tag admin.', ex(['Sort mail'], 'priority', 'tags'))],
                 'The report lists "Sort mail" with priority L and the tag admin.', depends=['high']),
        ], names=['Fix leak', 'Sort mail']),
        wf('gui-add-scheduled', 'add', TRIO, [
            goal('scheduled', 'Add a task `Plan party` scheduled for 2026-06-01.',
                 add('Plan party', 'scheduled:2026-06-01'),
                 [('task', 'The task is scheduled for 2026-06-01.', ex(['Plan party'], 'scheduled'))],
                 'The report lists "Plan party" with a scheduled date (the S column) and its details show '
                 'Scheduled 2026-06-01.'),
        ], names=['Plan party']),
        wf('gui-add-depends', 'add', TRIO, [
            goal('depends', 'Add a task `Deploy app` that depends on task 1 (Alpha task).',
                 add('Deploy app', 'depends:1'),
                 [('task', 'The task depends on Alpha task.', ex(['Deploy app'], 'depends'))],
                 'The report lists "Deploy app" with 1 in its Deps column.'),
        ], names=['Deploy app']),
        wf('gui-add-recur', 'add', TRIO, [
            goal('recur', 'Add a task `Water lawn` that recurs weekly and is due on Friday.',
                 add('Water lawn', 'recur:weekly due:friday'),
                 [('task', 'A weekly recurring task with its first instance is created.',
                   ex(['Water lawn'], 'status', 'recur', 'due'))],
                 'The report lists "Water lawn" with weekly in its Recur column and a value in its Due column.'),
        ], names=['Water lawn']),
        wf('gui-log', 'log', TRIO, [
            goal('log', 'Log an already completed task `Cleaned garage` (use the log prompt, not add).',
                 add('Cleaned garage', opener='l'),
                 [('task', 'The task is recorded as completed.', ex(['Cleaned garage'], 'status'))],
                 'The prompt closes and "Cleaned garage" does not appear among the pending tasks of the report.'),
            goal('show', 'Show the completed tasks in the task list.', [key('R'), typ('completed'), key('Enter')],
                 [('rows', 'The completed tasks are listed: the logged task.', scr('rows'))],
                 'The task list shows the completed tasks, and "Cleaned garage" is among them.', depends=['log']),
        ], names=['Cleaned garage']),
    ]


def changes():
    return [
        wf('gui-modify-project', 'modify', MAIN, [
            goal('project', 'Change the project of `Write report` (task 2) to `Office`.',
                 jump(2) + modify('project:Office'),
                 [('task', 'The project is Office.', ex(['Write report'], 'project'))],
                 'The report shows "Write report" in the project Office.'),
            goal('description', 'Rename the task `Read book` to `Read novel`.',
                 jump(8) + modify('"Read novel"', clear=True),
                 [('task', 'The description is changed.', ex(['Read novel'], 'status', 'annotations'))],
                 'The report lists "Read novel" and no longer "Read book".', depends=['project']),
        ], names=['Read novel']),
        wf('gui-modify-tags', 'modify', MAIN, [
            goal('remove', 'Remove the tag `shop` from `Buy groceries` (task 5), keeping its other tag.',
                 jump(5) + modify('-shop'),
                 [('task', 'Only the tag errand is left.', ex(['Buy groceries'], 'tags'))],
                 'The report shows "Buy groceries" with the tag errand only.'),
            goal('add', 'Add the tags `music` and `weekly` to `Learn piano` (task 11).', jump(11) + modify('+music +weekly'),
                 [('task', 'The task has the three tags.', ex(['Learn piano'], 'tags'))],
                 'The report shows "Learn piano" with the tags hobby, music and weekly.', depends=['remove']),
        ]),
        wf('gui-modify-due', 'modify', MAIN, [
            goal('set', 'Set the due date of `Plan trip` (task 6) to 2026-06-15.', jump(6) + modify('due:2026-06-15'),
                 [('task', 'The task is due on 2026-06-15.', ex(['Plan trip'], 'due'))],
                 'The details of "Plan trip" show the due date 2026-06-15.'),
            goal('clear', 'Remove the due date of `Water plants` (task 10).', jump(10) + modify('due:'),
                 [('task', 'The task has no due date.', ex(['Water plants'], 'due'))],
                 'The report shows "Water plants" without a due date.', depends=['set']),
        ]),
        wf('gui-priority', 'actions', MAIN, [
            goal('h', 'Give `Learn piano` (task 11) priority H.', jump(11) + K('H'),
                 [('task', 'The task has priority H.', ex(['Learn piano'], 'priority'))],
                 'The report shows priority H for "Learn piano".'),
            goal('none', 'Remove the priority of `Pay rent` (task 1).', jump(1) + K('N'),
                 [('task', 'The task has no priority.', ex(['Pay rent'], 'priority'))],
                 'The report shows "Pay rent" without a priority.', depends=['h']),
        ]),
        wf('gui-done-delete', 'actions', MAIN, [
            goal('delete', 'Delete the task `Plan trip`.', jump(6) + K('x'),
                 [('task', 'The task is deleted.', ex(['Plan trip'], 'status'))],
                 '"Plan trip" is no longer listed in the report.'),
            goal('done', 'Mark the task `Write report` as done.', jump(2) + K('d'),
                 [('task', 'The task is completed.', ex(['Write report'], 'status'))],
                 '"Write report" is no longer listed in the report.', depends=['delete']),
        ]),
        wf('gui-start-stop', 'actions', MAIN, [
            goal('start', 'Start working on `Read book` (task 8).', jump(8) + K('s'),
                 [('task', 'The task is started.', ex(['Read book'], 'start'))],
                 '"Read book" is shown as active: its Active column has a value and its details show a start '
                 'time.'),
            goal('stop', 'Stop the active task `Review PR` (task 4).', jump(4) + K('s'),
                 [('task', 'The task is stopped.', ex(['Review PR'], 'start'))],
                 '"Review PR" no longer shows an Active value and its details have no start time.',
                 depends=['start']),
        ]),
        wf('gui-annotate', 'annotate', MAIN, [
            goal('annotate', 'Add the annotation `bring tools` to `Call plumber` (task 3).',
                 jump(3) + [key('A'), typ('bring tools'), key('Enter')],
                 [('task', 'The task has the annotation.', ex(['Call plumber'], 'annotations'))],
                 'The details of "Call plumber" show the annotation "bring tools".'),
        ]),
        wf('gui-quick-tag', 'actions', MAIN, [
            goal('tag', 'Toggle the quick tag (next) on `Team lunch` (task 12).', jump(12) + K('t'),
                 [('task', 'The task has the tag next.', ex(['Team lunch'], 'tags'))],
                 '"Team lunch" shows the tag next and moves to the top of the report.'),
            goal('untag', 'Toggle the quick tag on `Team lunch` again.', K('t'),
                 [('task', 'The tag next is removed.', ex(['Team lunch'], 'tags'))],
                 '"Team lunch" no longer shows the tag next.', depends=['tag']),
        ]),
        wf('gui-duplicate', 'actions', MAIN, [
            goal('duplicate', 'Duplicate the task `Water plants` (task 10).', jump(10) + K('y'),
                 [('task', 'There are two Water plants tasks.', ex(['Water plants'], 'status', 'tags'))],
                 'The report lists "Water plants" twice.'),
        ]),
        wf('gui-undo', 'actions', MAIN, [
            goal('done', 'Mark `Call plumber` (task 3) as done.', jump(3) + K('d'),
                 [('task', 'The task is completed.', ex(['Call plumber'], 'status'))],
                 '"Call plumber" is no longer listed.'),
            goal('undo', 'Undo that last change.', K('u'),
                 [('task', 'The task is pending again.', ex(['Call plumber'], 'status'))],
                 '"Call plumber" is listed again.', depends=['done']),
        ]),
        wf('gui-delete-confirm', 'actions', MAIN, [
            goal('delete', 'Delete the task `Fix bike` (task 9). The application asks for a confirmation; confirm it.',
                 jump(9) + K('x', 'x'),
                 [('task', 'The task is deleted.', ex(['Fix bike'], 'status'))],
                 '"Fix bike" is no longer listed in the report.'),
        ], config=[('uda.taskwarrior-tui.task-report.prompt-on-delete', 'true')]),
    ]


def selection():
    order = ['Buy groceries', 'Review PR', 'Pay rent', 'Call plumber', 'Team lunch', 'Water plants', 'Learn piano',
             'Read book', 'Write report', 'Plan trip', 'Fix bike']

    def mark(*names):
        steps, at = [key('g')], 0
        for index in sorted(order.index(n) for n in names):
            steps += K(*['j'] * (index - at)) + [key('v')]
            at = index
        return steps
    return [
        wf('gui-marks-done', 'selection', MAIN, [
            goal('mark', 'Mark the tasks `Read book` and `Write report` (do not change them yet).',
                 mark('Read book', 'Write report'),
                 [('marked', 'Exactly these two tasks are marked.', scr('marked'))],
                 '"Read book" and "Write report" are shown as marked, and no other task is.'),
            goal('done', 'Complete the two marked tasks together.', K('d'),
                 [('tasks', 'Both tasks are completed.', ex(['Read book', 'Write report'], 'status'))],
                 'Neither "Read book" nor "Write report" is listed any more.', depends=['mark']),
        ]),
        wf('gui-marks-priority', 'selection', MAIN, [
            goal('priority', 'Give both `Pay rent` and `Team lunch` priority L in one action on the two tasks.',
                 mark('Pay rent', 'Team lunch') + K('L'),
                 [('tasks', 'Both tasks have priority L.', ex(['Pay rent', 'Team lunch'], 'priority')),
                  ('marked', 'Both tasks are still marked after the change.', scr('marked'))],
                 'The report shows priority L for "Pay rent" and for "Team lunch".'),
            goal('clear', 'Clear all marks.', K('Escape'),
                 [('marked', 'No task is marked.', scr('marked'))],
                 'No task is shown as marked any more.', depends=['priority']),
        ]),
        wf('gui-mark-all', 'selection', MAIN, [
            goal('all', 'Mark every task of the report.', K('V'),
                 [('marked', 'Every listed task is marked.', scr('marked'))],
                 'Every task of the report is shown as marked.'),
        ]),
        wf('gui-jump', 'navigation', MAIN, [
            goal('jump', 'Select task 10 using the jump-to-ID prompt.', jump(10),
                 [('selected', 'Water plants is selected.', scr('selected'))],
                 '"Water plants" (ID 10) is the selected task.'),
            goal('last', 'Select the last task of the report.', K('G'),
                 [('selected', 'The last task is selected.', scr('selected'))],
                 'The last row of the report ("Fix bike") is the selected task.', depends=['jump']),
        ]),
    ]


def filters():
    return [
        wf('gui-filter-project', 'filter', MAIN, [
            goal('work', 'Show only the pending tasks of the project Work (including its subprojects).',
                 filt('project:Work status:pending'),
                 [('rows', 'Only the Work tasks are listed.', scr('rows'))],
                 'The report lists only "Review PR", "Team lunch" and "Write report".'),
            goal('reset', 'Return to the report\'s own filter (status:pending -WAITING limit:page).', K('/', 'Escape'),
                 [('rows', 'All pending tasks are listed again.', scr('rows'))],
                 'The report lists every pending task again.', depends=['work']),
        ]),
        wf('gui-filter-tags', 'filter', MAIN, [
            goal('tags', 'Show only the tasks tagged `bills` or tagged `shop`.', filt('+bills or +shop'),
                 [('rows', 'Pay rent and Buy groceries are listed.', scr('rows'))],
                 'The report lists only "Buy groceries" and "Pay rent".'),
        ]),
        wf('gui-filter-overdue', 'filter', MAIN, [
            goal('overdue', 'Show only the overdue tasks.', filt('+OVERDUE'),
                 [('rows', 'Only the overdue task is listed.', scr('rows'))],
                 'The report lists only "Call plumber".'),
            goal('today', 'Now show only the tasks due today.', filt('+TODAY'),
                 [('rows', 'Only the tasks due today are listed.', scr('rows'))],
                 'The report lists only "Review PR" and "Team lunch".', depends=['overdue']),
        ]),
        wf('gui-filter-word', 'filter', MAIN, [
            goal('word', 'Show only the tasks whose description contains `book`.', filt('book'),
                 [('rows', 'Only Read book is listed.', scr('rows'))],
                 'The report lists only "Read book".'),
        ]),
        wf('gui-filter-completed', 'filter', MAIN, [
            goal('completed', 'Show only the completed tasks by filtering on their status.', filt('status:completed'),
                 [('rows', 'Only the completed task is listed.', scr('rows'))],
                 'The report lists only "Old chore".'),
        ]),
    ]


def reports():
    return [
        wf('gui-report-completed', 'reports', MAIN, [
            goal('completed', 'Switch to the completed report.', [key('R'), typ('completed'), key('Enter')],
                 [('label', 'The completed report is shown.', scr('label')), ('rows', 'It lists Old chore.', scr('rows'))],
                 'The top bar names the completed report and the report lists "Old chore".'),
            goal('next', 'Switch back to the next report.', [key('R'), typ('next'), key('Enter')],
                 [('label', 'The next report is shown.', scr('label'))],
                 'The top bar names the next report and the pending tasks are listed again.', depends=['completed']),
        ]),
        wf('gui-report-waiting', 'reports', MAIN, [
            goal('waiting', 'Switch to the waiting report.', [key('R'), typ('waiting'), key('Enter')],
                 [('label', 'The waiting report is shown.', scr('label')), ('rows', 'It lists Renew passport.', scr('rows'))],
                 'The top bar names the waiting report and it lists "Renew passport".'),
        ]),
        wf('gui-report-oldest', 'reports', MAIN, [
            goal('oldest', 'Switch to the oldest report.', [key('R'), typ('oldest'), key('Enter')],
                 [('rows', 'The tasks are listed oldest first.', scr('rows')), ('label', 'The label.', scr('label'))],
                 'The top bar names the oldest report and "Learn piano" (the oldest pending task) is listed first.'),
        ]),
        wf('gui-report-blocked', 'reports', MAIN, [
            goal('blocked', 'Switch to the blocked report.', [key('R'), typ('blocked'), key('Enter')],
                 [('rows', 'The blocked report lists Fix bike.', scr('rows')), ('label', 'The label.', scr('label'))],
                 'The top bar names the blocked report and it lists only "Fix bike".'),
        ]),
    ]


CONTEXTS = [('context.home.read', 'project:Home'), ('context.home.write', 'project:Home'),
            ('context.work.read', 'project:Work')]


def contexts():
    return [
        wf('gui-context-home', 'context', MAIN, [
            goal('home', 'Activate the context `home`.', [key('c'), typ('home'), key('Enter')],
                 [('label', 'The home context is active.', scr('label')),
                  ('setting', 'The context is stored.', cli('_get', 'rc.context'))],
                 'The top bar shows [home] and only "Pay rent" and "Call plumber" are listed.'),
            goal('add', 'Add a task `Clean gutters` while the context is active.', add('Clean gutters'),
                 [('task', 'The context gives the task the project Home.', ex(['Clean gutters'], 'project'))],
                 '"Clean gutters" is listed in the home context with the project Home.', depends=['home']),
        ], names=['Clean gutters'], config=CONTEXTS),
        wf('gui-context-none', 'context', MAIN, [
            goal('work', 'Activate the context `work`.', [key('c'), typ('work'), key('Enter')],
                 [('label', 'The work context is active.', scr('label'))],
                 'The top bar shows [work] and only the Work tasks are listed.'),
            goal('none', 'Deactivate the context again (choose none).', [key('c'), typ('none'), key('Enter')],
                 [('label', 'No context is active.', scr('label')),
                  ('setting', 'The context setting is cleared.', cli('_get', 'rc.context'))],
                 'The top bar shows [none] and all pending tasks are listed.', depends=['work']),
        ], config=CONTEXTS),
    ]


def views():
    return [
        wf('gui-projects', 'views', MAIN, [
            goal('projects', 'Show the Projects view.', K(']'),
                 [('view', 'The Projects view is active.', scr('view'))],
                 'The project summary is shown, listing Home, Music, Travel and Work with their remaining tasks.'),
            goal('back', 'Return to the task report.', K('['),
                 [('view', 'The Tasks view is active.', scr('view'))],
                 'The task report is shown again.', depends=['projects']),
        ]),
        wf('gui-calendar', 'views', MAIN, [
            goal('calendar', 'Show the Calendar view.', K(']', ']', ']'),
                 [('view', 'The Calendar view is active.', scr('view'))],
                 'The calendar of 2026 is shown.'),
            goal('year', 'Show the calendar of the year 2028.', K('j', 'j'),
                 [('year', 'The calendar shows 2028.', scr('content', first=1))],
                 'The calendar shows the months of 2028.', depends=['calendar']),
        ]),
        wf('gui-timesheet', 'views', MAIN, [
            goal('timesheet', 'Show the Timesheet view.', K(']', ']'),
                 [('view', 'The Timesheet view is active.', scr('view'))],
                 'The timesheet lists "Old chore" as completed and "Review PR" as started this week.'),
        ]),
        wf('gui-help', 'help', MAIN, [
            goal('help', 'Open the key binding help.', K('?'),
                 [('help', 'The help popup is open.', scr('boxes'))],
                 'A help popup listing the key bindings is shown.'),
            goal('close', 'Close the help.', K('Escape'),
                 [('boxes', 'No popup is open.', scr('boxes'))],
                 'The help is closed and the task report is visible again.', depends=['help']),
        ]),
    ]


def details():
    return [
        wf('gui-details-pane', 'details', MAIN, [
            goal('hide', 'Hide the task details pane.', K('z'),
                 [('layout', 'The details pane is hidden.', scr('layout'))],
                 'Only the task report is shown, without the details of the selected task.'),
            goal('right', 'Show the task details again, placed to the right of the report.', K('z', '\\'),
                 [('layout', 'The details are to the right.', scr('layout'))],
                 'The details of the selected task are shown to the right of the report.', depends=['hide']),
        ]),
        wf('gui-details-task', 'details', MAIN, [
            goal('blocked', 'Show the details of `Fix bike` (task 9).', jump(9),
                 [('details', 'The details are those of Fix bike.', scr('detail', key='Description'))],
                 'The details pane shows "Fix bike", blocked by task 5 "Buy groceries".'),
        ]),
    ]


def editing():
    return [
        wf('gui-history', 'history', TRIO, [
            goal('first', 'Add a task `Daily standup` with the tag `meeting`.', add('Daily standup', '+meeting'),
                 [('task', 'The task is added.', ex(['Daily standup'], 'status', 'tags'))],
                 '"Daily standup" with the tag meeting is listed.'),
            goal('again', 'Add the same task a second time by recalling it from the add prompt\'s history.',
                 K('a', 'Up', 'Enter'),
                 [('task', 'There are two Daily standup tasks.', ex(['Daily standup'], 'status', 'tags'))],
                 '"Daily standup" is listed twice.', depends=['first']),
        ], names=['Daily standup']),
        wf('gui-completion', 'completion', MAIN, [
            goal('complete', 'Add a task `Pick tomatoes` with the tag `garden`: type +gar after the description and '
                             'complete the tag with Tab.',
                 [key('a'), typ('Pick tomatoes'), key('End'), typ(' +gar'), key('Tab'), key('Enter')],
                 [('task', 'The task has the tag garden.', ex(['Pick tomatoes'], 'tags'))],
                 '"Pick tomatoes" is listed with the tag garden.'),
        ], names=['Pick tomatoes']),
        wf('gui-edit-line', 'editing', TRIO, [
            goal('edit', 'Open the add prompt and type `Pay the bill`; then, before confirming, change the text to '
                         '`Pay the gas bill` by moving the cursor and inserting `gas `.',
                 [key('a'), typ('Pay the bill'), key('Alt+b'), typ('gas '), key('Enter')],
                 [('task', 'The edited description is added.', ex(['Pay the gas bill'], 'status'))],
                 '"Pay the gas bill" is listed in the report.'),
        ], names=['Pay the gas bill']),
    ]


def more():
    order = ['Buy groceries', 'Review PR', 'Pay rent', 'Call plumber', 'Team lunch', 'Water plants', 'Learn piano',
             'Read book', 'Write report', 'Plan trip', 'Fix bike']

    def mark(*names):
        steps, at = [key('g')], 0
        for index in sorted(order.index(n) for n in names):
            steps += K(*['j'] * (index - at)) + [key('v')]
            at = index
        return steps
    return [
        wf('gui-add-subproject', 'add', TRIO, [
            goal('add', 'Add a task `Mow lawn` in the project `Home.Garden`, due on Saturday.',
                 add('Mow lawn', 'project:Home.Garden due:saturday'),
                 [('task', 'The task has the project and the due date.', ex(['Mow lawn'], 'project', 'due'))],
                 'The report lists "Mow lawn" in the project Home.Garden, and its details show the due date '
                 '2026-05-16.'),
        ], names=['Mow lawn']),
        wf('gui-add-annotate', 'annotate', TRIO, [
            goal('add', 'Add a task `Book dentist`.', add('Book dentist'),
                 [('task', 'The task exists.', ex(['Book dentist'], 'status'))], '"Book dentist" is listed.'),
            goal('note', 'Annotate `Book dentist` with `ask about cleaning`.', [key('A'), typ('ask about cleaning'),
                                                                               key('Enter')],
                 [('task', 'The annotation is stored.', ex(['Book dentist'], 'annotations'))],
                 'The details of "Book dentist" show the annotation "ask about cleaning".', depends=['add']),
        ], names=['Book dentist']),
        wf('gui-add-until', 'add', TRIO, [
            goal('until', 'Add a task `Trial offer` that expires at the end of the year (an until date of `eoy`).',
                 add('Trial offer', 'until:eoy'),
                 [('task', 'The task has the until date.', ex(['Trial offer'], 'until'))],
                 'The report lists "Trial offer" and its details show Until 2026-12-31 23:59:59.'),
        ], names=['Trial offer']),
        wf('gui-add-tags', 'add', TRIO, [
            goal('tags', 'Add a task `Pack boxes` with the three tags `move`, `heavy` and `fragile`.',
                 add('Pack boxes', '+move +heavy +fragile'),
                 [('task', 'The task has the three tags.', ex(['Pack boxes'], 'tags'))],
                 'The report lists "Pack boxes" with the tags fragile, heavy and move.'),
        ], names=['Pack boxes']),
        wf('gui-add-error', 'add', TRIO, [
            goal('error', 'Try to add a task `Bad due` with the due date `zzz`, and leave the message that appears on '
                          'screen.', add('Bad due', 'due:zzz'),
                 [('error', 'An error popup names the invalid date.', scr('error', mentions=['zzz'])),
                  ('task', 'Nothing is added.', ex(['Bad due'], 'status'))],
                 'An error message says that zzz is not a valid date, and no task "Bad due" is listed.',
                 bound={'task': ['error']}),
            goal('fix', 'Dismiss the message and add `Bad due` again, this time due tomorrow.',
                 K('Escape', 'a', 'Escape') + add('Bad due', 'due:tomorrow'),
                 [('task', 'The task is added, due tomorrow.', ex(['Bad due'], 'due'))],
                 'The report lists "Bad due", and its details show the due date 2026-05-14.', depends=['error']),
        ], names=['Bad due']),
        wf('gui-modify-depends', 'modify', MAIN, [
            goal('depends', 'Make `Write report` (task 2) depend on `Call plumber` (task 3).',
                 jump(2) + modify('depends:3'),
                 [('task', 'Write report depends on Call plumber.', ex(['Write report'], 'depends'))],
                 '"Write report" shows 3 in its Deps column.'),
        ]),
        wf('gui-modify-wait', 'modify', MAIN, [
            goal('wait', 'Hide `Plan trip` (task 6) from the report until 2026-06-01 by giving it a wait date.',
                 jump(6) + modify('wait:2026-06-01'),
                 [('task', 'The wait date is set.', ex(['Plan trip'], 'wait'))],
                 '"Plan trip" is no longer listed in the next report.'),
        ]),
        wf('gui-modify-marked', 'modify', MAIN, [
            goal('project', 'Move both `Plan trip` and `Read book` to the project `Leisure` with one modification.',
                 mark('Plan trip', 'Read book') + K('m') + [typ('project:Leisure'), key('Enter')],
                 [('tasks', 'Both tasks are in Leisure.', ex(['Plan trip', 'Read book'], 'project'))],
                 'The report shows "Plan trip" and "Read book" in the project Leisure.'),
        ]),
        wf('gui-undo-modify', 'actions', MAIN, [
            goal('modify', 'Change the project of `Pay rent` (task 1) to `Flat`.', jump(1) + modify('project:Flat'),
                 [('task', 'The project is Flat.', ex(['Pay rent'], 'project'))],
                 '"Pay rent" shows the project Flat.'),
            goal('undo', 'Undo that change.', K('u'),
                 [('task', 'The project is Home again.', ex(['Pay rent'], 'project'))],
                 '"Pay rent" shows the project Home again.', depends=['modify']),
        ]),
        wf('gui-marks-delete', 'selection', MAIN, [
            goal('delete', 'Delete both `Team lunch` and `Water plants` in one action.',
                 mark('Team lunch', 'Water plants') + K('x'),
                 [('tasks', 'Both tasks are deleted.', ex(['Team lunch', 'Water plants'], 'status'))],
                 'Neither "Team lunch" nor "Water plants" is listed any more.'),
        ]),
        wf('gui-marks-start', 'selection', MAIN, [
            goal('start', 'Start both `Learn piano` and `Write report` in one action.',
                 mark('Learn piano', 'Write report') + K('s'),
                 [('tasks', 'Both tasks are started.', ex(['Learn piano', 'Write report'], 'start'))],
                 '"Learn piano" and "Write report" both show a value in the Active column.'),
        ]),
        wf('gui-marks-annotate', 'selection', MAIN, [
            goal('annotate', 'Annotate both `Call plumber` and `Fix bike` with `check tools` in one action.',
                 mark('Call plumber', 'Fix bike') + K('A') + [typ('check tools'), key('Enter')],
                 [('tasks', 'Both tasks have the annotation.', ex(['Call plumber', 'Fix bike'], 'annotations'))],
                 'The details of the selected task show the annotation "check tools".'),
        ]),
        wf('gui-done-project', 'selection', MAIN, [
            goal('done', 'Complete every pending task of the project Home (including its subprojects) at once.',
                 filt('project:Home status:pending') + K('V', 'd'),
                 [('tasks', 'Exactly the Home tasks are completed.', summary())],
                 'No pending task of the project Home is listed any more.'),
        ]),
        wf('gui-done-confirm', 'actions', MAIN, [
            goal('done', 'Complete the task `Team lunch` (task 12). The application asks for a confirmation; confirm '
                         'it.', jump(12) + K('d', 'd'),
                 [('task', 'The task is completed.', ex(['Team lunch'], 'status'))],
                 '"Team lunch" is no longer listed.'),
        ], config=[('uda.taskwarrior-tui.task-report.prompt-on-done', 'true')]),
        wf('gui-jump-error', 'navigation', MAIN, [
            goal('jump', 'Try to jump to task 42 (there is no such task) and leave the message on screen.', jump(42),
                 [('error', 'An error popup names the missing task.', scr('error', mentions=['42']))],
                 'An error message says that task 42 cannot be located.'),
        ]),
        wf('gui-filter-priority', 'filter', MAIN, [
            goal('priority', 'Show only the tasks with priority L.', filt('priority:L'),
                 [('rows', 'The priority L tasks are listed.', scr('rows'))],
                 'The report lists only "Buy groceries" and "Water plants".'),
        ]),
        wf('gui-filter-week', 'filter', MAIN, [
            goal('week', 'Show only the pending tasks due by the end of this week (Sunday 2026-05-17).',
                 filt('status:pending due.by:eow'),
                 [('rows', 'The tasks due this week are listed.', scr('rows'))],
                 'The report lists only "Buy groceries", "Review PR", "Pay rent", "Call plumber" and "Team lunch".'),
        ]),
        wf('gui-filter-untagged', 'filter', MAIN, [
            goal('untagged', 'Show only the pending tasks that have no tags.', filt('status:pending -TAGGED'),
                 [('rows', 'The untagged pending tasks are listed.', scr('rows'))],
                 'The report lists only "Read book", "Write report", "Plan trip" and "Fix bike".'),
        ]),
        wf('gui-filter-noproject', 'filter', MAIN, [
            goal('noproject', 'Show only the pending tasks that have no project.', filt('status:pending project:'),
                 [('rows', 'The pending tasks without a project are listed.', scr('rows'))],
                 'The report lists only "Buy groceries", "Water plants", "Read book" and "Fix bike".'),
        ]),
        wf('gui-filter-history', 'history', MAIN, [
            goal('garden', 'Show only the tasks tagged `garden`.', filt('+garden'),
                 [('rows', 'Water plants is listed.', scr('rows'))], 'The report lists only "Water plants".'),
            goal('reset', 'Return to the report\'s own filter (status:pending -WAITING limit:page).', K('/', 'Escape'),
                 [('rows', 'All pending tasks are listed.', scr('rows'))], 'Every pending task is listed again.',
                 depends=['garden']),
            goal('recall', 'Apply the garden filter again by recalling it from the filter prompt\'s history.',
                 [key('/'), key('Control+u'), key('Up'), key('Enter')],
                 [('rows', 'Water plants is listed again.', scr('rows'))], 'The report lists only "Water plants" '
                                                                           'again.', depends=['reset']),
        ]),
        wf('gui-report-all', 'reports', MAIN, [
            goal('all', 'Switch to the all report.', [key('R'), typ('all'), key('Enter')],
                 [('label', 'The all report is shown.', scr('label')), ('rows', 'It lists every task.', scr('rows'))],
                 'The top bar names the all report, which lists the completed and deleted tasks as well.'),
        ]),
        wf('gui-report-ready', 'reports', MAIN, [
            goal('ready', 'Switch to the ready report.', [key('R'), typ('ready'), key('Enter')],
                 [('label', 'The ready report is shown.', scr('label')), ('rows', 'Its tasks.', scr('rows'))],
                 'The top bar names the ready report; "Plan trip" (scheduled later) and "Fix bike" (blocked) are not '
                 'listed.'),
        ]),
        wf('gui-report-overdue', 'reports', MAIN, [
            goal('overdue', 'Switch to the overdue report.', [key('R'), typ('overdue'), key('Enter')],
                 [('label', 'The overdue report is shown.', scr('label')), ('rows', 'Its tasks.', scr('rows'))],
                 'The top bar names the overdue report, which lists only "Call plumber".'),
        ]),
        wf('gui-report-newest', 'reports', MAIN, [
            goal('newest', 'Switch to the newest report.', [key('R'), typ('newest'), key('Enter')],
                 [('label', 'The newest report is shown.', scr('label')), ('rows', 'Its tasks.', scr('rows'))],
                 'The top bar names the newest report; "Review PR" (the newest task) is listed first.'),
        ]),
        wf('gui-calendar-decade', 'views', MAIN, [
            goal('decade', 'Show the calendar of the year 2036.', K(']', ']', ']', 'J'),
                 [('year', 'The calendar shows 2036.', scr('content', first=1))],
                 'The calendar shows the months of 2036.'),
        ]),
        wf('gui-help-scroll', 'help', MAIN, [
            goal('scroll', 'Open the key binding help and scroll it until the binding of the undo key is visible.',
                 K('?') + K(*['j'] * 20),
                 [('help', 'The help popup is open.', scr('boxes'))],
                 'The help popup shows the line for u: task undo.'),
        ]),
        wf('gui-completion-project', 'completion', MAIN, [
            goal('project', 'Add a task `Prune hedge` in the project `Home.Repairs`: after the description type '
                            'project:Ho, then press Tab to open the completion list and apply Home.Repairs from it.',
                 [key('a'), typ('Prune hedge'), key('End'), typ(' project:Ho'), key('Tab'), key('Tab'), key('Enter'),
                  key('Enter')],
                 [('task', 'The task is in Home.Repairs.', ex(['Prune hedge'], 'project'))],
                 '"Prune hedge" is listed in the project Home.Repairs.'),
        ], names=['Prune hedge']),
        wf('gui-edit-word', 'editing', TRIO, [
            goal('word', 'Open the add prompt and type `Clean the big garage`; then, before confirming, delete the word '
                         '`big` and the space after it.',
                 [key('a'), typ('Clean the big garage'), key('Alt+b'), key('Control+w'), key('Enter')],
                 [('task', 'The edited description is added.', ex(['Clean the garage'], 'status'))],
                 '"Clean the garage" is listed in the report.'),
        ], names=['Clean the garage']),
    ]


def episodes():
    return (adds() + changes() + selection() + filters() + reports() + contexts() + views() + details() + editing() +
            more())
