"""Taskwarrior behaviour as the application shows it: urgency and its coefficients (the Urg column and the report
order), dependencies, recurrence, waiting and expiring tasks, configured defaults, user-defined attributes, custom
priority values, date formats, the case sensitivity of searches, and the task data the command line imports and
exports.
"""
from spec_core import *
from spec_data import MAIN, TRIO

# One factor per task (and a plain task for the age term); entry dates differ so the age term differs slightly.
_FACTORS = [
    ('U plain', {}), ('U priority H', {'priority': 'H'}), ('U priority M', {'priority': 'M'}),
    ('U priority L', {'priority': 'L'}), ('U project', {'project': 'Proj'}), ('U one tag', {'tags': ['a']}),
    ('U two tags', {'tags': ['a', 'b']}), ('U three tags', {'tags': ['a', 'b', 'c']}),
    ('U annotated', {'notes': [('20260512T110000Z', 'note')]}), ('U overdue', {'due': '20260506T100000Z'}),
    ('U due today', {'due': '20260513T180000Z'}), ('U due week', {'due': '20260520T100000Z'}),
    ('U due month', {'due': '20260612T100000Z'}), ('U due year', {'due': '20270513T100000Z'}),
    ('U active', {'start': '20260513T090000Z'}), ('U scheduled', {'scheduled': '20260512T000000Z'}),
    ('U waiting', {'wait': '20260601T000000Z'}), ('U next tag', {'tags': ['next']}),
    ('U old', {'entry': '20250101T000000Z'}), ('U blocking', {}), ('U blocked', {'depends': [59]}),
]
# Entry dates one hour apart (the age term breaks every tie between factors of equal weight).
URGENCY = [T(40 + i, name, **dict({'entry': f'20260512T{9 - i // 3:02d}{(i % 3) * 20:02d}00Z'}, **fields))
           for i, (name, fields) in enumerate(_FACTORS)]
URGENCY_NAMES = [t['description'] for t in URGENCY]


def urgency_episode():
    cps = [step('values', 'Observe the urgency of every task.', [],
                [(t['description'].lower().replace(' ', '-')[2:], f'{t["description"]}: its urgency follows its one '
                  'urgency factor.', ex([t['description']], 'urgency')) for t in URGENCY]),
           step('order', 'Show all pending tasks with the filter status:pending.', filt('status:pending'),
                [('rows', 'The tasks are listed by urgency.', scr('rows')),
                 ('cells', 'The Urg column shows each urgency with two decimals.', scr('cells', label='Urg'))])]
    return program('urgency', 'urgency', fixture(URGENCY), cps)


COEFFICIENTS = [
    ('tag-coefficient', 'urgency.user.tag.focus.coefficient', '6.5', T(61, 'C focus', tags=['focus'])),
    ('project-coefficient', 'urgency.user.project.Garden.coefficient', '-2.0', T(62, 'C garden', project='Garden')),
    ('priority-coefficient', 'urgency.uda.priority.H.coefficient', '10', T(63, 'C high', priority='H')),
    ('due-coefficient', 'urgency.due.coefficient', '0', T(64, 'C due', due='20260514T000000Z')),
    ('age-coefficient', 'urgency.age.coefficient', '0', T(65, 'C old', entry='20250101T000000Z')),
    ('active-coefficient', 'urgency.active.coefficient', '1', T(66, 'C active', start='20260513T090000Z')),
    ('tags-coefficient', 'urgency.tags.coefficient', '5', T(67, 'C tagged', tags=['x'])),
    ('annotations-coefficient', 'urgency.annotations.coefficient', '3', T(68, 'C noted',
                                                                          notes=[('20260512T110000Z', 'n')])),
]


def coefficients_episode():
    items = [(cid, {'tasks': [task], 'config': [(name, value)]}, f'Observe the urgency with {name}={value}.', [],
              [('urgency', f'{name}={value} changes the urgency of {task["description"]}.',
                ex([task['description']], 'urgency'))]) for cid, name, value, task in COEFFICIENTS]
    return cases('urgency-coefficients', 'urgency', items)


DEPS = [
    T(70, 'Lay foundation', entry='20260401T080000Z'),
    T(71, 'Build walls', entry='20260402T080000Z', depends=[70]),
    T(72, 'Add roof', entry='20260403T080000Z', depends=[71]),
    T(73, 'Paint house', entry='20260404T080000Z', depends=[71, 72]),
]
DEP_NAMES = [t['description'] for t in DEPS]


def dependencies_episode():
    cps = [
        step('initial', 'Observe the report of the dependency chain.', [],
             [('rows', 'Blocking tasks rank above the tasks they block.', scr('rows')),
              ('deps', 'The Deps column lists the IDs each task depends on.', scr('cells', label='Deps'))]),
        step('blocked-details', 'Select task 4 (Paint house).', jump(4),
             [('details', 'The details list the tasks that block it and the BLOCKED virtual tag.', scr('details'))],
             lifecycle='restart'),
        step('blocking-details', 'Select task 2 (Build walls).', jump(2),
             [('details', 'The details list the tasks it blocks and the tasks blocking it.', scr('details'))],
             lifecycle='restart'),
        step('blocked-filter', 'Filter with +BLOCKED.', filt('+BLOCKED'),
             [('rows', 'The blocked tasks are listed.', scr('rows'))], lifecycle='restart'),
        step('done-root', 'Select task 1 and complete it.', jump(1) + K('d'),
             [('rows', 'Build walls is no longer blocked and moves up.', scr('rows')),
              ('deps', 'The remaining dependencies are shown with the new IDs.', scr('cells', label='Deps'))],
             depends=['initial'], lifecycle='restart'),
        step('add-dependency', 'Add the task "Move in" depending on tasks 1 and 3.', add('Move in', 'depends:1,3'),
             [('task', 'The new task depends on Build walls and Paint house.', ex(['Move in'], 'depends'))],
             depends=['done-root']),
        step('circular', 'Select task 1 (Build walls) and make it depend on task 2 (Add roof).',
             jump(1) + modify('depends:2'),
             [('task', 'Taskwarrior refuses a circular dependency: Build walls keeps no dependency on Add roof.',
               ex(['Build walls'], 'depends')),
              ('error', 'An error popup appears.', scr('error'))], depends=['done-root'], lifecycle='restart'),
    ]
    wf = program('dependencies', 'taskwarrior', fixture(DEPS), cps, names=['Move in'])
    return bind(wf, {'circular/task': ['circular/error']})


# A weekly recurring template and its pending instance, imported with fixed UUIDs.
TEMPLATE = T(95, 'Weekly sync', status='recurring', entry='20260509T070000Z', project='Work', due='20260515T000000Z',
             recur='weekly', mask='-', rtype='periodic')
INSTANCE = T(96, 'Weekly sync', entry='20260509T070500Z', project='Work', due='20260515T000000Z', recur='weekly',
             parent=U(95), imask=0, rtype='periodic')


def recurrence_episode():
    rec = {'tasks': TRIO + [TEMPLATE, INSTANCE]}
    items = [
        ('add', {'tasks': []}, 'Add "Water ferns" recurring weekly, due Friday.',
         add('Water ferns', 'recur:weekly due:friday'),
         [('tasks', 'A recurring template and its first pending instance exist.',
           ex(['Water ferns'], 'status', 'recur', 'due', 'parent', 'mask', 'imask')),
          ('rows', 'The pending instance is listed in the next report.', scr('rows'))]),
        ('recurring-report', None, 'Switch to the recurring report.', [key('R'), typ('recurring'), key('Enter')],
         [('rows', 'The recurring report lists the template and the instance.', scr('rows'))], ['add']),
        ('until', {'tasks': []}, 'Add "Short course" recurring daily from tomorrow until the day after.',
         add('Short course', 'recur:daily due:tomorrow until:2026-05-15'),
         [('tasks', 'The recurrence ends at the until date.', ex(['Short course'], 'status', 'until', 'recur'))]),
        ('done-instance', rec, 'Select the instance of Weekly sync (the first task) and complete it.', K('g', 'd'),
         [('tasks', 'The instance is completed and the template records it in its mask.',
           ex(['Weekly sync'], 'status', 'mask', 'imask', 'end')),
          ('rows', 'The completed instance leaves the report.', scr('rows'))]),
        ('delete-instance', rec, 'Select the instance of Weekly sync (the first task) and delete it.', K('g', 'x'),
         [('tasks', 'The instance is deleted and the template records it in its mask.',
           ex(['Weekly sync'], 'status', 'mask', 'imask', 'end'))]),
    ]
    return bind(cases('recurrence', 'taskwarrior', items, names=['Water ferns', 'Short course', 'Weekly sync']),
                {'done-instance/rows': ['done-instance/tasks']})


def waiting_episode():
    fx = {'tasks': MAIN}
    items = [
        ('hide', fx, 'Select task 2 (Write report) and give it wait:tomorrow.', jump(2) + modify('wait:tomorrow'),
         [('rows', 'The waiting task leaves the next report.', scr('rows')),
          ('task', 'It keeps its pending status with a wait date.', ex(['Write report'], 'status', 'wait'))]),
        ('waiting-report', None, 'Switch to the waiting report.', [key('R'), typ('waiting'), key('Enter')],
         [('rows', 'The waiting report lists the waiting tasks.', scr('rows'))], ['hide']),
        ('unwait', None, 'Switch back to the next report, filter +WAITING, select Write report and clear its wait.',
         [key('R'), typ('next'), key('Enter')] + filt('+WAITING') + [key('G')] + modify('wait:'),
         [('task', 'Clearing the wait date makes the task pending and listed again.',
           ex(['Write report'], 'status', 'wait'))], ['waiting-report']),
        ('past-wait', fx, 'Add "Already visible" with wait:yesterday.', add('Already visible', 'wait:yesterday'),
         [('rows', 'A wait date in the past does not hide the task.', scr('rows'))]),
        ('expired', fx, 'Add "Expired thing" with until:yesterday.', add('Expired thing', 'until:yesterday'),
         [('task', 'A task past its until date expires: it is deleted at once.',
           ex(['Expired thing'], 'status', 'end'))]),
    ]
    return cases('waiting', 'taskwarrior', items, names=['Already visible', 'Expired thing'])


def config_cases():
    items = [
        ('default-project', {'tasks': [], 'config': [('default.project', 'Inbox')]}, 'Add "Defaulted" without a project.',
         add('Defaulted'), [('task', 'default.project gives it the project Inbox.', ex(['Defaulted'], 'project'))]),
        ('default-due', {'tasks': [], 'config': [('default.due', 'eow')]}, 'Add "Due by default" without a due date.',
         add('Due by default'), [('task', 'default.due gives it the end of the week.', ex(['Due by default'], 'due'))]),
        ('default-overridden', {'tasks': [], 'config': [('default.project', 'Inbox')]},
         'Add "Own project" with project:Mine.', add('Own project', 'project:Mine'),
         [('task', 'An explicit project wins over default.project.', ex(['Own project'], 'project'))]),
        ('uda-numeric', {'tasks': [], 'config': [('uda.estimate.type', 'numeric'), ('uda.estimate.label', 'Est')]},
         'Add "Estimated" with estimate:3.', add('Estimated', 'estimate:3'),
         [('task', 'The user-defined numeric attribute is stored.', ex(['Estimated'], 'estimate'))]),
        ('uda-values', {'tasks': [], 'config': [('uda.size.type', 'string'), ('uda.size.values', 'S,M,L')]},
         'Add "Sized" with size:M.', add('Sized', 'size:M'),
         [('task', 'The user-defined attribute with listed values is stored.', ex(['Sized'], 'size'))]),
        ('uda-rejected', {'tasks': [], 'config': [('uda.size.type', 'string'), ('uda.size.values', 'S,M,L')]},
         'Add "Too big" with size:XL.', add('Too big', 'size:XL'),
         [('error', 'A value outside the listed values is rejected.', scr('error', mentions=['XL'])),
          ('task', 'Nothing is added.', ex(['Too big'], 'status'))]),
        ('uda-column', {'tasks': [T(80, 'Big job', estimate=8), T(81, 'Small job', estimate=1)],
                        'config': [('uda.estimate.type', 'numeric'), ('uda.estimate.label', 'Est'),
                                   ('report.next.columns', 'id,estimate,description,urgency'),
                                   ('report.next.labels', 'ID,Est,Description,Urg')]},
         'Observe the next report configured with an estimate column.', [],
         [('headers', 'The report shows the configured columns.', scr('headers')),
          ('cells', 'The Est column shows each task\'s estimate.', scr('cells', label='Est'))]),
        ('uda-filter', {'tasks': [T(80, 'Big job', estimate=8), T(81, 'Small job', estimate=1)],
                        'config': [('uda.estimate.type', 'numeric')]},
         'Filter with estimate.over:4.', filt('estimate.over:4'),
         [('rows', 'User-defined attributes can be filtered.', scr('rows'))]),
        ('priority-values', {'tasks': [], 'config': [('uda.priority.values', 'A,B,C,')]},
         'Add "Custom prio" with priority:B.', add('Custom prio', 'priority:B'),
         [('task', 'The configured priority value is accepted.', ex(['Custom prio'], 'priority'))]),
        ('priority-values-old', {'tasks': [], 'config': [('uda.priority.values', 'A,B,C,')]},
         'Add "Old prio" with priority:H.', add('Old prio', 'priority:H'),
         [('error', 'H is no longer a priority value.', scr('error', mentions=['H'])),
          ('task', 'Nothing is added.', ex(['Old prio'], 'status'))]),
        ('dateformat', {'tasks': [], 'config': [('dateformat', 'D/M/Y')]}, 'Add "Euro date" due 20/06/2026.',
         add('Euro date', 'due:20/06/2026'),
         [('task', 'dates are read in the configured format.', ex(['Euro date'], 'due'))]),
        ('search-case', {'tasks': MAIN, 'config': [('search.case.sensitive', 'no')]}, 'Filter with Bike.',
         filt('Bike'), [('rows', 'With case-insensitive search, Bike finds Fix bike.', scr('rows'))]),
        ('due-window', {'tasks': MAIN, 'config': [('due', '1')]}, 'Filter with +DUE.', filt('+DUE'),
         [('rows', 'With due=1 only tasks due within a day count as DUE.', scr('rows'))]),
    ]
    wf = cases('taskwarrior-config', 'taskwarrior', items,
               names=['Defaulted', 'Due by default', 'Own project', 'Estimated', 'Sized', 'Too big', 'Custom prio',
                      'Old prio', 'Euro date'])
    bind = {'uda-rejected': 'taskwarrior-config/uda-values/task',
            'priority-values-old': 'taskwarrior-config/priority-values/task'}
    for cp in wf['checkpoints']:
        if cp['id'] in bind:
            for a in cp['assertions']:
                a['requires'] = [bind[cp['id']]]
    return wf


ROUNDTRIP = T(90, 'Round trip', entry='20260301T081500Z', project='Data.Sub', tags=['one', 'two'], priority='M',
              due='20260601T120000Z', scheduled='20260520T000000Z', until='20261231T000000Z',
              wait='20260515T000000Z', notes=[('20260302T090000Z', 'first note'), ('20260303T090000Z', 'second note')])
ROUND_GROUPS = [
    ('values', 'status, project, priority and UUID', ('status', 'project', 'priority', 'uuid')),
    ('lists', 'tags and annotations', ('tags', 'annotations')),
    ('dates', 'entry, due, scheduled, until and wait dates', ('entry', 'due', 'scheduled', 'until', 'wait')),
]


def data_episode():
    done = T(91, 'Finished import', status='completed', entry='20260201T000000Z', end='20260210T000000Z')
    gone = T(92, 'Removed import', status='deleted', entry='20260202T000000Z', end='20260211T000000Z')
    started = T(93, 'Started import', entry='20260203T000000Z', start='20260512T080000Z')
    cps = [step('round-trip', 'Observe the imported task.', [],
                [(cid, f'task export keeps the imported {text}.', ex(['Round trip'], *fields))
                 for cid, text, fields in ROUND_GROUPS])]
    cps += [
        step('completed', 'Observe the imported completed task.', [],
             [('task', 'Status and end date are kept.', ex(['Finished import'], 'status', 'end', 'entry', 'id'))]),
        step('deleted', 'Observe the imported deleted task.', [],
             [('task', 'Status and end date are kept.', ex(['Removed import'], 'status', 'end', 'id'))]),
        step('started', 'Observe the imported active task.', [],
             [('task', 'The start date is kept.', ex(['Started import'], 'start', 'id'))]),
        step('ids', 'Observe the IDs.', [], [('ids', 'Pending tasks are numbered in import order; others have 0.',
                                              ex(['Round trip', 'Finished import', 'Removed import', 'Started import'],
                                                 'id'))]),
        step('modified', 'Filter description:Round (the imported task waits until 2026-05-15, so the next report '
                         'hides it), select it and give it priority H with the H key.',
             filt('description:Round') + jump(1) + K('H'),
             [('task', 'The change is exported with the other fields intact.',
               ex(['Round trip'], 'priority', 'project', 'tags', 'due', 'wait', 'annotations'))]),
        step('reimport', 'Import the task again with a changed description from the command line.',
             [cmd('rc.confirmation=off', 'import', stdin='[{"uuid":"' + U(90) + '","description":"Round trip updated",'
                                                          '"status":"pending","entry":"20260301T081500Z"}]')],
             [('tasks', 'Importing an existing UUID replaces the task.', summary())]),
    ]
    return program('data', 'data', fixture([ROUNDTRIP, done, gone, started]), cps,
                   names=['Round trip updated'])


def episodes():
    return [urgency_episode(), coefficients_episode(), dependencies_episode(), recurrence_episode(),
            waiting_episode(), config_cases(), data_episode()]
