"""Changing tasks from the report: modify (m), annotate (A), done (d), delete (x), start/stop (s), quick tag (t), the
priority keys (H M L N), duplicate (y) and undo (u), on the selected task and on several marked tasks.

The main fixture's IDs: 1 Pay rent, 2 Write report, 3 Call plumber, 4 Review PR (active), 5 Buy groceries,
6 Plan trip, 7 Renew passport (waiting), 8 Read book, 9 Fix bike (depends on 5), 10 Water plants, 11 Learn piano,
12 Team lunch. A checkpoint selects its task with the jump prompt (:ID) and changes only that task; checkpoints start
from their own fresh fixture, so they are independent unless they declare a dependency on the one before.
"""
from spec_core import *
from spec_data import MAIN, PENDING

ALL = ('status', 'project', 'tags', 'priority', 'due', 'scheduled', 'wait', 'until', 'depends', 'start', 'end')
# The next report's order of the main fixture (by urgency).
ORDER = ['Buy groceries', 'Review PR', 'Pay rent', 'Call plumber', 'Team lunch', 'Water plants', 'Learn piano',
         'Read book', 'Write report', 'Plan trip', 'Fix bike']


def mark(*descriptions):
    """Mark the named tasks with v, moving through the report with g and j (by report position)."""
    steps, at = [key('g')], 0
    for index in sorted(ORDER.index(d) for d in descriptions):
        steps += K(*['j'] * (index - at)) + [key('v')]
        at = index
    return steps

MODIFY = [
    # (cid, task id, description, appended text, fields)
    ('project', 2, 'Write report', 'project:Office', ('project',)),
    ('project-clear', 1, 'Pay rent', 'project:', ('project',)),
    ('tag-add', 8, 'Read book', '+leisure', ('tags',)),
    ('tag-remove', 5, 'Buy groceries', '-shop', ('tags',)),
    ('tags-swap', 3, 'Call plumber', '-phone +urgent +home', ('tags',)),
    ('priority', 6, 'Plan trip', 'priority:H', ('priority',)),
    ('priority-clear', 4, 'Review PR', 'priority:', ('priority',)),
    ('due', 11, 'Learn piano', 'due:eow', ('due',)),
    ('due-clear', 10, 'Water plants', 'due:', ('due',)),
    ('wait', 12, 'Team lunch', 'wait:tomorrow', ('wait', 'status')),
    ('scheduled', 9, 'Fix bike', 'scheduled:2026-05-20', ('scheduled',)),
    ('depends-clear', 9, 'Fix bike', 'depends:', ('depends',)),
]
MODIFY_MORE = [
    ('depends', 2, 'Write report', 'depends:3', ('depends',)),
    ('until', 6, 'Plan trip', 'until:2026-09-01', ('until',)),
    ('several', 8, 'Read book', 'project:Leisure +novel priority:L due:2026-06-30', ('project', 'tags', 'priority', 'due')),
]
FX = {'tasks': MAIN}


def modify_episode():
    items = [('prompt', FX, 'Select task 2 and open the modify prompt.', jump(2) + K('m'),
              [('prompt', 'The modify prompt names the task and is prefilled with its quoted description.',
                scr('prompt'))]),
             ('escape', None, 'Press Escape.', K('Escape'),
              [('title', 'The modify prompt closes without a change.', scr('title')),
               ('task', 'The task is unchanged.', ex(['Write report'], *ALL))], ['prompt'])]
    for cid, tid, description, text, fields in MODIFY:
        items.append((cid, FX, f'Select task {tid} ({description}) and append "{text}" in the modify prompt.',
                      jump(tid) + modify(text),
                      [('task', f'{description} gets {text}; nothing else changes.', ex([description], *ALL))]))
    return bind(cases('modify', 'modify', items), {'escape/task': ['project/task']})


def modify_more_episode():
    items = []
    for cid, tid, description, text, fields in MODIFY_MORE:
        items.append((cid, FX, f'Select task {tid} ({description}) and append "{text}" in the modify prompt.',
                      jump(tid) + modify(text),
                      [('task', f'{description} gets {text}.', ex([description], *ALL))]))
    items += [
        ('description', FX, 'Select task 11, clear the modify prompt and type "Learn guitar" (with the quotes).',
         jump(11) + modify('"Learn guitar"', clear=True),
         [('task', 'The description changes; project and tags stay.', ex(['Learn guitar'], *ALL)),
          ('old', 'No task keeps the old description.', ex(['Learn piano'], 'status'))]),
        ('words', FX, 'Select task 10, clear the modify prompt and type: Water all plants',
         jump(10) + modify('Water all plants', clear=True),
         [('task', 'Plain words replace the description.', ex(['Water all plants'], *ALL))]),
        ('append-word', FX, 'Select task 12 and append the word "today" after the prefilled description.',
         jump(12) + modify('today'),
         [('task', 'An extra word outside the quotes is appended to the description.',
           ex(['Team lunch today'], 'status', 'project', 'tags'))]),
        ('substitute', FX, 'Select task 2, clear the modify prompt and type /report/summary/',
         jump(2) + modify('/report/summary/', clear=True),
         [('task', 'The substitution replaces "report" in the description.', ex(['Write summary'], 'status'))]),
        ('follow', FX, 'Select task 3 (Call plumber) and give it priority:H.', jump(3) + modify('priority:H'),
         [('selected', 'The selection follows the modified task to its new place.', scr('selected')),
          ('rows', 'The report is re-sorted by the new urgency.', scr('rows'))]),
        ('error', FX, 'Select task 1 and append due:zzz.', jump(1) + modify('due:zzz'),
         [('error', 'An error popup says the modification failed.', scr('error')),
          ('task', 'The task is unchanged.', ex(['Pay rent'], *ALL))]),
    ]
    wf = cases('modify-more', 'modify', items, names=['Learn guitar', 'Water all plants', 'Team lunch today',
                                                     'Write summary'])
    return bind(wf, {'error': ['several/task'], 'follow/selected': ['follow/rows'],
                     'description/old': ['description/task']})


def modify_marked_episode():
    marks = mark('Read book', 'Write report')
    items = [
        ('marked', FX, 'Mark Read book and Write report, open the modify prompt and type +batch.',
         marks + K('m') + [typ('+batch'), key('Enter')],
         [('tasks', 'Both marked tasks get the tag; no other task changes.', ex(PENDING, 'tags', 'status')),
          ('marked', 'The tasks stay marked.', scr('marked'))]),
        ('marked-project', FX, 'Mark Read book and Write report and modify them with project:Shared.',
         marks + K('m') + [typ('project:Shared'), key('Enter')],
         [('tasks', 'Both marked tasks move to the project.', ex(['Write report', 'Read book'], 'project'))]),
        ('marked-annotate', FX, 'Mark Read book and Write report and annotate them with "checked".',
         marks + K('A') + [typ('checked'), key('Enter')],
         [('tasks', 'Both marked tasks get the annotation.', ex(['Write report', 'Read book'], 'annotations'))]),
        ('marked-undo', FX, 'Mark Read book and Write report, modify them with project:Shared and press u.',
         marks + K('m') + [typ('project:Shared'), key('Enter'), key('u')],
         [('tasks', 'One undo reverts the modification of both marked tasks.',
           ex(['Write report', 'Read book'], 'project'))]),
        ('annotate-undo', FX, 'Mark Read book and Write report, annotate them with "checked" and press u.',
         marks + K('A') + [typ('checked'), key('Enter'), key('u')],
         [('tasks', 'One undo removes the annotation from both marked tasks.',
           ex(['Write report', 'Read book'], 'annotations'))]),
    ]
    return bind(cases('modify-marked', 'modify', items), {'marked-undo': ['marked-project/tasks'],
                                                          'annotate-undo': ['marked-annotate/tasks']})


def annotate_episode():
    items = [
        ('prompt', FX, 'Select task 6 and open the annotate prompt.', jump(6) + K('A'),
         [('prompt', 'The annotate prompt names the task and opens with a pair of quotes.', scr('prompt'))]),
        ('annotate', None, 'Type "book hotel" and press Enter.', [typ('book hotel'), key('Enter')],
         [('task', 'Plan trip gets the annotation.', ex(['Plan trip'], 'annotations', 'status'))], ['prompt']),
        ('second', FX, 'Select task 8 (it already has an annotation) and annotate it with "Chapter 4".',
         jump(8) + [key('A'), typ('Chapter 4'), key('Enter')],
         [('task', 'The new annotation follows the existing one.', ex(['Read book'], 'annotations'))]),
        ('outside', FX, 'Select task 2 and annotate it, typing the words after the quotes: "" needs data',
         jump(2) + [key('A'), key('End'), typ(' needs data'), key('Enter')],
         [('task', 'Words outside the quotes form the annotation.', ex(['Write report'], 'annotations'))]),
        ('empty', FX, 'Select task 3 and confirm the annotate prompt with only its empty quotes.',
         jump(3) + K('A', 'Enter'),
         [('error', 'An error popup appears.', scr('error')),
          ('task', 'No annotation is added.', ex(['Call plumber'], 'annotations'))]),
        ('escape', FX, 'Select task 12, open the annotate prompt, type "x" and press Escape.',
         jump(12) + [key('A'), typ('x'), key('Escape')],
         [('task', 'Escape adds nothing.', ex(['Team lunch'], 'annotations'))]),
    ]
    return bind(cases('annotate', 'annotate', items), {'empty': ['annotate/task'], 'escape': ['annotate/task']})


ACTIONS = [
    # (cid, task id, description, keys, requirement, fields)
    ('start', 8, 'Read book', ['s'], 'The task is started now.', ('start', 'status')),
    ('stop', 4, 'Review PR', ['s'], 'The active task is stopped.', ('start', 'status')),
    ('quick-tag', 3, 'Call plumber', ['t'], 'The task gets the tag next.', ('tags',)),
    ('quick-untag', 1, 'Pay rent', ['t', 't'], 'Pressing t twice adds and removes the tag next.', ('tags',)),
    ('priority-h', 11, 'Learn piano', ['H'], 'The task gets priority H.', ('priority',)),
    ('priority-m', 1, 'Pay rent', ['M'], 'The priority changes to M.', ('priority',)),
    ('priority-l', 12, 'Team lunch', ['L'], 'The task gets priority L.', ('priority',)),
    ('priority-n', 4, 'Review PR', ['N'], 'N removes the priority.', ('priority',)),
]


def actions_episode():
    items = []
    for cid, tid, description, keys, requirement, fields in ACTIONS:
        items.append((cid, FX, f'Select task {tid} ({description}) and press {" ".join(keys)}.', jump(tid) + K(*keys),
                      [('task', requirement, ex([description], *fields))]))
    items.append(('duplicate', FX, 'Select task 12 (Team lunch) and press y.', jump(12) + K('y'),
                  [('task', 'A second Team lunch task with the same attributes and a new entry date exists.',
                    ex(['Team lunch'], 'status', 'project', 'tags', 'due', 'priority', 'entry')),
                   ('selected', 'The original task stays selected.', scr('selected'))]))
    items.append(('start-selection', FX, 'Select task 6 (Plan trip) and press s.', jump(6) + K('s'),
                  [('selected', 'The started task stays selected after the report is re-sorted.', scr('selected')),
                   ('rows', 'The report is re-sorted by the new urgency.', scr('rows'))]))
    return bind(cases('actions', 'actions', items), {'quick-untag': ['quick-tag/task'],
                                                     'duplicate/selected': ['duplicate/task'],
                                                     'start-selection/selected': ['start-selection/rows']})


def finish_episode():
    items = [
        ('done', {'tasks': MAIN}, 'Select task 2 (Write report) and press d.', jump(2) + K('d'),
         [('task', 'The task is completed now.', ex(['Write report'], 'status', 'end')),
          ('ids', 'The remaining pending tasks are renumbered.', ex(PENDING, 'id'))]),
        ('delete', {'tasks': MAIN}, 'Select task 6 (Plan trip) and press x.', jump(6) + K('x'),
         [('task', 'The task is deleted now.', ex(['Plan trip'], 'status', 'end')),
          ('rows', 'The deleted task leaves the report.', scr('rows'))]),
        ('done-selection', {'tasks': MAIN}, 'Select task 10 (Water plants) and press d.', jump(10) + K('d'),
         [('selected', 'The selection stays at the same row, on the next task.', scr('selected')),
          ('rows', 'The completed task leaves the report.', scr('rows'))]),
        ('done-last', {'tasks': MAIN}, 'Select the last task of the report (Fix bike) and press d.', K('G', 'd'),
         [('selected', 'The selection moves up to the new last task.', scr('selected')),
          ('task', 'Fix bike is completed.', ex(['Fix bike'], 'status'))]),
        ('done-blocker', {'tasks': MAIN}, 'Select task 5 (Buy groceries, which Fix bike depends on) and press d.',
         jump(5) + K('d'),
         [('task', 'Buy groceries is completed.', ex(['Buy groceries'], 'status')),
          ('rows', 'Fix bike is no longer blocked and moves up in the report.', scr('rows'))]),
        ('delete-active', {'tasks': MAIN}, 'Select task 4 (the active Review PR) and press x.', jump(4) + K('x'),
         [('task', 'The active task is deleted.', ex(['Review PR'], 'status', 'end'))]),
        ('empty', {'tasks': []}, 'Press d, x, s, t, H and y in an empty database.', K('d', 'x', 's', 't', 'H', 'y'),
         [('tasks', 'Nothing happens.', summary()), ('running', 'The application keeps running.', scr('running'))]),
    ]
    wf = cases('finish', 'actions', items)
    for cp in wf['checkpoints']:
        if cp['id'] == 'empty':
            for a in cp['assertions']:
                a['requires'] = ['finish/done/task']
    return wf


def undo_episode():
    pairs = [
        ('done', jump(2) + K('d'), ex(['Write report'], 'status', 'end'), 'The task is completed.',
         'Undo reopens the completed task.'),
        ('delete', jump(6) + K('x'), ex(['Plan trip'], 'status', 'end'), 'The task is deleted.',
         'Undo restores the deleted task.'),
        ('modify', jump(1) + modify('project:Elsewhere'), ex(['Pay rent'], 'project'), 'The project changes.',
         'Undo restores the project.'),
        ('add', add('Short lived'), ex(['Short lived'], 'status'), 'The task is added.',
         'Undo removes the added task.'),
        ('annotate', jump(8) + [key('A'), typ('to undo'), key('Enter')], ex(['Read book'], 'annotations'),
         'The annotation is added.', 'Undo removes the annotation.'),
        ('start', jump(3) + K('s'), ex(['Call plumber'], 'start'), 'The task is started.', 'Undo stops it again.'),
    ]
    setup, cps = [], []
    for cid, steps, check, did, undone in pairs:
        setup.append(fixture(MAIN, sid='fx-' + cid, before=cid))
        cps.append(step(cid, f'Perform the action ({cid}).', steps, [('task', did, check)]))
        cps.append(step('undo-' + cid, 'Press u.', K('u'), [('task', undone, check)], depends=[cid]))
    setup.append(fixture(MAIN, sid='fx-twice', before='twice'))
    cps.append(step('twice', 'Complete task 2 and then task 1.', jump(2) + K('d') + jump(1) + K('d'),
                    [('tasks', 'Both tasks are completed.', ex(['Write report', 'Pay rent'], 'status'))]))
    cps.append(step('undo-twice', 'Press u twice.', K('u', 'u'),
                    [('tasks', 'Undo twice reopens both tasks.', ex(['Write report', 'Pay rent'], 'status')),
                     ('selected', 'The task reopened last is selected.', scr('selected'))], depends=['twice']))
    setup.append(fixture([], sid='fx-nothing', before='nothing'))
    cps.append(step('nothing', 'Press u in an empty database.', K('u'),
                    [('tasks', 'Nothing changes.', summary()), ('running', 'The application keeps running.',
                                                                scr('running'))]))
    wf = program('undo', 'actions', setup, cps, names=['Short lived'])
    for cp in wf['checkpoints']:
        if cp['id'] == 'nothing':
            for a in cp['assertions']:
                a['requires'] = ['undo/undo-done/task']
    return wf


def marked_actions_episode():
    pairs = [('done', 'd', 'Both marked tasks are completed.', ('status', 'end')),
             ('delete', 'x', 'Both marked tasks are deleted.', ('status', 'end')),
             ('start', 's', 'Both marked tasks are started.', ('start',)),
             ('quick-tag', 't', 'Both marked tasks get the tag next.', ('tags',)),
             ('priority', 'H', 'Both marked tasks get priority H.', ('priority',)),
             ('duplicate', 'y', 'Both marked tasks are duplicated.', ('status', 'project'))]
    items = [(cid, {'tasks': MAIN}, f'Mark Read book and Write report and press {k}.',
              mark('Read book', 'Write report') + K(k),
              [('tasks', requirement, ex(PENDING, *fields))]) for cid, k, requirement, fields in pairs]
    items.append(('mixed-start', {'tasks': MAIN}, 'Mark Review PR (active) and Read book and press s.',
                  mark('Review PR', 'Read book') + K('s'),
                  [('tasks', 's toggles each marked task: the active one stops, the other starts.',
                    ex(['Review PR', 'Read book'], 'start'))]))
    items.append(('three', {'tasks': MAIN}, 'Mark Pay rent, Team lunch and Plan trip and press L.',
                  mark('Pay rent', 'Team lunch', 'Plan trip') + K('L'),
                  [('tasks', 'All three marked tasks get priority L.', ex(PENDING, 'priority'))]))
    items.append(('all-done', {'tasks': MAIN}, 'Filter project:Home, mark all listed tasks with V and press d.',
                  filt('project:Home') + K('V', 'd'),
                  [('tasks', 'Exactly the tasks of project Home and its subprojects are completed.', summary())]))
    return cases('marked-actions', 'actions', items)


def prompts_episode():
    on = [('uda.taskwarrior-tui.task-report.prompt-on-done', 'true'),
          ('uda.taskwarrior-tui.task-report.prompt-on-delete', 'true'),
          ('uda.taskwarrior-tui.task-report.prompt-on-undo', 'true')]
    fx = {'tasks': MAIN, 'config': on}
    items = [
        ('delete-prompt', fx, 'Select task 6 and press x.', jump(6) + K('x'),
         [('prompt', 'A prompt asks to confirm deleting task 6.', scr('prompt')),
          ('task', 'Nothing is deleted yet.', ex(['Plan trip'], 'status'))]),
        ('delete-escape', None, 'Press Escape.', K('Escape'),
         [('task', 'Escape aborts: the task stays pending.', ex(['Plan trip'], 'status')),
          ('title', 'The filter line is shown again.', scr('title'))], ['delete-prompt']),
        ('delete-confirm', fx, 'Select task 6, press x and confirm with x.', jump(6) + K('x', 'x'),
         [('task', 'The task is deleted.', ex(['Plan trip'], 'status'))]),
        ('undo-prompt', fx, 'Delete task 6 (x, x) and press u.', jump(6) + K('x', 'x', 'u'),
         [('prompt', 'A prompt asks to confirm running task undo.', scr('prompt')),
          ('task', 'Nothing is undone yet.', ex(['Plan trip'], 'status'))], ['delete-confirm']),
        ('undo-abort', None, 'Press q.', K('q'),
         [('task', 'q aborts the undo.', ex(['Plan trip'], 'status')),
          ('running', 'The application keeps running.', scr('running'))], ['undo-prompt']),
        ('undo-confirm', None, 'Press u and confirm with Enter.', K('u', 'Enter'),
         [('task', 'The deletion is undone.', ex(['Plan trip'], 'status'))], ['undo-abort']),
        ('done-prompt', fx, 'Select task 2 and press d.', jump(2) + K('d'),
         [('prompt', 'A prompt asks to confirm completing task 2.', scr('prompt')),
          ('task', 'Nothing is completed yet.', ex(['Write report'], 'status'))]),
        ('done-confirm', None, 'Confirm with d.', K('d'),
         [('task', 'The task is completed.', ex(['Write report'], 'status'))], ['done-prompt']),
        ('done-abort', fx, 'Select task 1, press d and then q.', jump(1) + K('d', 'q'),
         [('task', 'q aborts: the task stays pending.', ex(['Pay rent'], 'status')),
          ('title', 'The filter line is shown again.', scr('title')),
          ('running', 'The application keeps running.', scr('running'))]),
        ('done-enter', fx, 'Select task 1, press d and then Enter.', jump(1) + K('d', 'Enter'),
         [('task', 'Enter confirms too.', ex(['Pay rent'], 'status'))]),
    ]
    return bind(cases('prompts', 'actions', items),
                {'done-abort': ['done-confirm/task'], 'delete-escape': ['delete-confirm/task'],
                 'undo-abort': ['undo-confirm/task'], 'done-prompt/task': ['done-prompt/prompt'],
                 'delete-prompt/task': ['delete-prompt/prompt'], 'undo-prompt/task': ['undo-prompt/prompt']})


def episodes():
    return [modify_episode(), modify_more_episode(), modify_marked_episode(), annotate_episode(),
            actions_episode(), finish_episode(), undo_episode(), marked_actions_episode(), prompts_episode()]
