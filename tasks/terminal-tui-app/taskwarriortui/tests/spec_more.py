"""More of the same areas on a second fixture: filter rules for scheduled, until, wait, end and entry dates, the
recurrence virtual tags, equality and regular-expression filters, nested expressions; the details of recurring,
completed, deleted and waiting tasks; the Projects and Timesheet views of other data; further modify and undo cases.
"""
from spec_core import *
from spec_data import MAIN, PENDING

FIX2 = [
    T(201, 'Old report', status='completed', entry='20260401T080000Z', end='20260501T090000Z', project='Work.Docs'),
    T(202, 'Late fee', entry='20260402T080000Z', due='20260512T120000Z', tags=['finance']),
    T(203, 'Garden plan', entry='20260403T080000Z', scheduled='20260510T000000Z', project='Home.Garden'),
    T(204, 'Future plan', entry='20260404T080000Z', scheduled='20260610T000000Z', project='Home.Garden.Beds'),
    T(205, 'Contract end', entry='20260405T080000Z', until='20260520T000000Z', due='20260518T000000Z'),
    T(206, 'Paused item', entry='20260406T080000Z', wait='20260520T000000Z', project='Home'),
    T(207, 'Release', entry='20260407T080000Z', project='Work.Code.Release', priority='H', tags=['release', 'urgent']),
    T(208, 'Docs update', entry='20260408T080000Z', project='Work.Docs', priority='M', tags=['docs']),
    T(209, 'Cancelled trip', status='deleted', entry='20260409T080000Z', end='20260509T100000Z', project='Travel'),
    T(210, 'Budget review', entry='20260513T090000Z', tags=['finance']),
    T(211, 'Annotated memo', entry='20260410T080000Z', notes=[('20260411T080000Z', 'first'), ('20260412T080000Z', 'second')]),
    T(212, 'Done early', status='completed', entry='20260411T080000Z', end='20260511T150000Z', project='Home'),
]
FIX2_NAMES = [t['description'] for t in FIX2] + ['Daily standup']
FIX2_SETUP = dict(tasks=FIX2, commands=[('add', 'Daily standup', 'recur:daily', 'due:tomorrow', 'project:Work')])

EXPRESSIONS2 = [
    ('scheduled-before', 'scheduled.before:today', 'rows'), ('scheduled-after', 'scheduled.after:today', 'rows'),
    ('scheduled-day', 'scheduled:2026-05-10', 'rows'), ('until-before', 'until.before:eom', 'rows'),
    ('wait-after', 'wait.after:now', 'rows'), ('end-after', 'end.after:2026-05-05', 'rows'),
    ('end-before', 'end.before:2026-05-05', 'rows'), ('entry-today', 'entry.after:today', 'rows'),
    ('parent', '+PARENT', 'rowset'), ('child', '+CHILD', 'rowset'), ('instance', '+INSTANCE', 'rowset'),
    ('template', '+TEMPLATE', 'rowset'), ('yesterday', '+YESTERDAY', 'rows'), ('quarter', '+QUARTER', 'rowset'),
    ('status-recurring', 'status:recurring', 'rowset'), ('project-subtree', 'project:Work.Code', 'rows'),
    ('project-not-work', 'project.not:Work', 'rowset'), ('project-startswith-dot', 'project.startswith:Home.G', 'rows'),
    ('description-is', 'description.is:Release', 'rows'), ('description-isnt', 'description.isnt:Release', 'rowset'),
    ('tag-and-not', '+docs -urgent', 'rows'), ('tag-both', '+release +urgent', 'rows'),
    ('regex-start', '/^Re/', 'rows'), ('regex-end', '/e$/', 'rowset'), ('regex-alternation', '/fee|plan/', 'rows'),
    ('priority-or', 'priority:H or priority:M', 'rows'), ('priority-is', 'priority.is:M', 'rows'),
    ('urgency-range', 'urgency.over:3 urgency.under:10', 'rowset'), ('due-math', 'due.before:today+6d', 'rowset'),
    ('due-before-today', 'due.before:today', 'rows'),
    ('nested', '( project:Work or project:Home ) and ( +urgent or priority:M )', 'rows'),
    ('uuid-full', 'uuid:' + U(208), 'rows'), ('description-starts', 'description:Annotated', 'rows'),
]


def expressions2_episode():
    cps = [step(cid, f'Filter the report with: {expr}', filt(expr),
                [(order, f'Exactly the tasks matching {expr} are listed.', scr(order))])
           for cid, expr, order in EXPRESSIONS2]
    return program('filter-expressions-2', 'filter', fixture(**FIX2_SETUP), fresh(cps), names=FIX2_NAMES)


def details2_episode():
    cps = [
        step('instance', 'Filter +INSTANCE and select the listed instance.', filt('+INSTANCE'),
             [('details', 'The details of a recurring instance show its recurrence and parent.', scr('details'))]),
        step('completed', 'Filter status:completed and select the last listed task.', filt('status:completed') + K('G'),
             [('details', 'The details of a completed task show its end date.', scr('details'))]),
        step('deleted', 'Filter status:deleted.', filt('status:deleted'),
             [('details', 'The details of a deleted task.', scr('details'))]),
        step('waiting', 'Filter +WAITING.', filt('+WAITING'),
             [('details', 'The details of a waiting task show its wait date.', scr('details'))]),
        step('annotations', 'Filter description:Annotated.', filt('description:Annotated'),
             [('details', 'Both annotations are listed with their dates.', scr('details'))]),
        step('until', 'Filter +UNTIL.', filt('+UNTIL'), [('details', 'The details show the until date.', scr('details'))]),
    ]
    return program('details-2', 'details', fixture(**FIX2_SETUP), fresh(cps), names=FIX2_NAMES)


def views2_episode():
    cps = [
        step('projects', 'Open the Projects view.', K(']'),
             [('content', 'The summary lists the nested projects with their counts and completion.', scr('content'))]),
        step('timesheet', 'Open the Timesheet view.', K(']', ']'),
             [('content', 'The timesheet lists the tasks completed and deleted in the recent weeks.', scr('content'))],
             depends=['projects'], lifecycle='restart'),
        step('after', 'Complete Release (filter +release, d), reset the filter and open the Projects view.',
             filt('+release') + K('d', '/', 'Escape', ']'),
             [('content', 'The summary counts the completed task in its projects.', scr('content'))],
             depends=['projects'], lifecycle='restart'),
        step('after-timesheet', 'Open the Timesheet view.', K(']'),
             [('content', 'The timesheet lists the task completed now.', scr('content'))], depends=['after']),
    ]
    return program('views-2', 'views', fixture(**FIX2_SETUP), cps, names=FIX2_NAMES)


MODIFY2 = [
    ('until-clear', '+UNTIL', 'Contract end', 'until:', ('until', 'due')),
    ('wait-clear', '+WAITING', 'Paused item', 'wait:', ('wait', 'status')),
    ('scheduled-clear', 'description:Garden', 'Garden plan', 'scheduled:', ('scheduled',)),
    ('tag-remove', 'description:Release', 'Release', '-urgent', ('tags',)),
    ('project-rename', 'description:Docs', 'Docs update', 'project:Work.Manuals', ('project',)),
    ('priority-change', 'description:Release', 'Release', 'priority:L', ('priority',)),
    ('apostrophe', 'description:Budget', "Budget review", "\"Budget's review\"", ('status',)),
]


def modify2_episode():
    items = []
    for cid, selector, description, text, fields in MODIFY2:
        target = "Budget's review" if cid == 'apostrophe' else description
        goal = (f'Filter {selector}, select the listed task and replace its description in the modify prompt by: {text}'
                if cid == 'apostrophe' else f'Filter {selector}, select the listed task and append in the modify prompt: '
                                            f'{text}')
        items.append((cid, FIX2_SETUP, goal,
                      filt(selector) + (modify(text, clear=True) if cid == 'apostrophe' else modify(text)),
                      [('task', f'{description} gets {text}.', ex([target], *fields))]))
    return cases('modify-2', 'modify', items, names=FIX2_NAMES + ["Budget's review"])


def undo2_episode():
    pairs = [
        ('duplicate', jump(10) + K('y'), ex(['Water plants'], 'status'), 'A copy exists.', 'Undo removes the copy.'),
        ('log', add('Logged then undone', opener='l'), ex(['Logged then undone'], 'status'), 'The task is logged.',
         'Undo removes the logged task.'),
        ('priority-key', jump(11) + K('H'), ex(['Learn piano'], 'priority'), 'The priority is H.',
         'Undo removes the priority again.'),
        ('quick-tag', jump(2) + K('t'), ex(['Write report'], 'tags'), 'The tag next is added.',
         'Undo removes the tag again.'),
        ('marked-done', [key('g'), key('v'), key('j'), key('v'), key('d')], ex(['Buy groceries', 'Review PR'], 'status'),
         'Both marked tasks are completed.', 'One undo reopens both tasks.'),
    ]
    setup, cps = [], []
    for cid, steps, check, did, undone in pairs:
        setup.append(fixture(MAIN, sid='fx-' + cid, before=cid))
        cps.append(step(cid, f'Perform the action ({cid}).', steps, [('task', did, check)]))
        cps.append(step('undo-' + cid, 'Press u.', K('u'), [('task', undone, check)], depends=[cid]))
    return program('undo-2', 'actions', setup, cps, names=['Logged then undone'])


def prompts2_episode():
    on = [('uda.taskwarrior-tui.task-report.prompt-on-done', 'true'),
          ('uda.taskwarrior-tui.task-report.prompt-on-delete', 'true')]
    fx = {'tasks': MAIN, 'config': on}
    items = [
        ('done-marked', fx, 'Mark the first two tasks and press d.', [key('g'), key('v'), key('j'), key('v'), key('d')],
         [('prompt', 'The prompt asks to confirm completing both marked tasks.', scr('prompt'))]),
        ('done-marked-confirm', None, 'Confirm with d.', K('d'),
         [('tasks', 'Both tasks are completed.', ex(['Buy groceries', 'Review PR'], 'status'))], ['done-marked']),
        ('delete-enter', fx, 'Select the last task, press x and confirm with Enter.', K('G', 'x', 'Enter'),
         [('task', 'The task is deleted.', ex(['Fix bike'], 'status'))]),
    ]
    return cases('prompts-2', 'actions', items)


def episodes():
    return [expressions2_episode(), details2_episode(), views2_episode(), modify2_episode(), undo2_episode(),
            prompts2_episode()]
