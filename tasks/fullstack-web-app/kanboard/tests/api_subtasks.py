"""Subtasks and their time tracking through the JSON-RPC API: creation and validation, ordering, updates of each
field (title, assignee, estimates, status, position), the task's time totals, removal, and the per-user timers.

Refused creations are attempted on a task of their own (Subtask checks), so that accepting or refusing one of them
never changes the subtasks the ordinary cases observe."""
from harness import Ref, refused_stored

PASSWORD = 'Subtasks-Pass-2026'
REFUSED = {'', 'Outsider', 'Ghost', 'Bad time', 'Bad status'}


def times(c, r):
    """The task's time totals (sums of its subtasks)."""
    observation = {'http': r.status}
    if r.has_result and isinstance(r.result, dict):
        observation['times'] = {k: r.result.get(k) for k in ('time_estimated', 'time_spent')}
    else:
        observation['result'] = c.norm.clean(r.body.get('result') if isinstance(r.body, dict) else None)
    return observation


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'member', 'createUser', {'username': 'sue', 'password': PASSWORD, 'name': 'Sue Subtask'}, save='sue',
       password=PASSWORD)
    fx('base', 'outsider', 'createUser', {'username': 'sid', 'password': PASSWORD}, save='sid')
    fx('base', 'project', 'createProject', {'name': 'Subtask project'}, save='p')
    fx('base', 'membership', 'addProjectUser', [Ref('p'), Ref('sue'), 'project-member'])
    fx('base', 'task', 'createTask', {'title': 'Parent task', 'project_id': Ref('p')}, save='t')
    fx('base', 'task2', 'createTask', {'title': 'Other parent', 'project_id': Ref('p')}, save='t2')
    fx('base', 'checks-task', 'createTask', {'title': 'Subtask checks', 'project_id': Ref('p')}, save='tc')
    fx('base', 'checks-anchor', 'createSubtask', {'task_id': Ref('tc'), 'title': 'Checks anchor'})

    # -- creation -------------------------------------------------------------------------------------------
    rpc('create', 'create', 'minimal', 'createSubtask', {'task_id': Ref('t'), 'title': 'Write tests'}, save='s1')
    rpc('create', 'create', 'minimal-read', 'getSubtask', [Ref('s1')])
    rpc('create', 'create', 'full', 'createSubtask', {'task_id': Ref('t'), 'title': 'Review code',
                                                      'user_id': Ref('sue'), 'time_estimated': 3,
                                                      'time_spent': 1.5, 'status': 1}, save='s2')
    rpc('create', 'create', 'full-read', 'getSubtask', [Ref('s2')])
    rpc('create', 'create', 'positional', 'createSubtask', [Ref('t'), 'Deploy ✓', Ref('sue'), 2, 0, 2], save='s3')
    rpc('create', 'create', 'all-ordered', 'getAllSubtasks', [Ref('t')],
        after=['rpc.create.create.minimal', 'rpc.create.create.full', 'rpc.create.create.positional'])
    rpc('create', 'create', 'task-totals', 'getTask', [Ref('t')], project=times,
        after=['rpc.create.create.minimal', 'rpc.create.create.full', 'rpc.create.create.positional'])
    rpc('create', 'create', 'other-task-empty', 'getAllSubtasks', [Ref('t2')], requires=['rpc.create.create.all-ordered'])
    rpc('create', 'validation', 'empty-title', 'createSubtask', {'task_id': Ref('tc'), 'title': ''})
    rpc('create', 'validation', 'assignee-not-member', 'createSubtask', {'task_id': Ref('tc'), 'title': 'Outsider',
                                                                        'user_id': Ref('sid')})
    rpc('create', 'validation', 'assignee-missing-user', 'createSubtask', {'task_id': Ref('tc'), 'title': 'Ghost',
                                                                          'user_id': 987654})
    rpc('create', 'validation', 'estimate-not-numeric', 'createSubtask', {'task_id': Ref('tc'), 'title': 'Bad time',
                                                                         'time_estimated': 'long'})
    rpc('create', 'validation', 'status-not-integer', 'createSubtask', {'task_id': Ref('tc'), 'title': 'Bad status',
                                                                       'status': 'done'})
    rpc('create', 'validation', 'missing-task', 'createSubtask', {'task_id': 987654, 'title': 'Orphan'}, actor='app')
    rpc('create', 'validation', 'refusals-not-stored', 'getAllSubtasks', [Ref('tc')],
        project=refused_stored('title', REFUSED, 'Checks anchor'),
        describe='getAllSubtasks of the checks task after the refused creations')
    rpc('create', 'validation', 'missing-subtask', 'getSubtask', [987654], actor='app',
        requires=['rpc.create.create.minimal-read'])

    # -- updates --------------------------------------------------------------------------------------------
    rpc('update', 'update', 'title', 'updateSubtask', {'id': Ref('s1'), 'task_id': Ref('t'), 'title': 'Write more tests'})
    rpc('update', 'update', 'assignee', 'updateSubtask', {'id': Ref('s1'), 'task_id': Ref('t'), 'user_id': Ref('sue')})
    rpc('update', 'update', 'times', 'updateSubtask', {'id': Ref('s1'), 'task_id': Ref('t'), 'time_estimated': 4,
                                                       'time_spent': 2.25})
    rpc('update', 'update', 'status-done', 'updateSubtask', {'id': Ref('s1'), 'task_id': Ref('t'), 'status': 2})
    rpc('update', 'update', 'updated-read', 'getAllSubtasks', [Ref('t')],
        after=['rpc.update.update.title', 'rpc.update.update.assignee', 'rpc.update.update.times',
               'rpc.update.update.status-done', 'rpc.create.create.all-ordered'])
    rpc('update', 'update', 'task-totals', 'getTask', [Ref('t')], project=times, after=['rpc.update.update.times'])
    rpc('update', 'update', 'positional', 'updateSubtask', [Ref('s2'), Ref('t'), 'Review again', 0])
    rpc('update', 'update', 'positional-read', 'getSubtask', [Ref('s2')], after=['rpc.update.update.positional'])
    rpc('update', 'order', 'move-first', 'updateSubtask', {'id': Ref('s3'), 'task_id': Ref('t'), 'position': 1})
    rpc('update', 'order', 'move-first-read', 'getAllSubtasks', [Ref('t')],
        after=['rpc.update.order.move-first', 'rpc.update.update.updated-read', 'rpc.update.update.positional'])
    rpc('update', 'validation', 'wrong-task', 'updateSubtask', {'id': Ref('s1'), 'task_id': Ref('t2'),
                                                               'title': 'Moved?'})
    rpc('update', 'validation', 'assignee-not-member', 'updateSubtask', {'id': Ref('s1'), 'task_id': Ref('t'),
                                                                        'user_id': Ref('sid')})
    rpc('update', 'validation', 'estimate-not-numeric', 'updateSubtask', {'id': Ref('s1'), 'task_id': Ref('t'),
                                                                         'time_estimated': 'x'})
    rpc('update', 'validation', 'missing-subtask', 'updateSubtask', {'id': 987654, 'task_id': Ref('t'),
                                                                    'title': 'Ghost'})
    rpc('update', 'validation', 'unchanged-after-refusals', 'getSubtask', [Ref('s1')],
        after=['rpc.update.update.updated-read'])
    rpc('update', 'validation', 'unassign', 'updateSubtask', {'id': Ref('s1'), 'task_id': Ref('t'), 'user_id': 0},
        after=['rpc.update.update.updated-read'])
    rpc('update', 'validation', 'unassigned-read', 'getSubtask', [Ref('s1')], after=['rpc.update.validation.unassign'])

    # -- removal --------------------------------------------------------------------------------------------
    rpc('remove', 'remove', 'remove', 'removeSubtask', [Ref('s2')], after=['rpc.update.order.move-first-read'])
    rpc('remove', 'remove', 'removed-read', 'getSubtask', [Ref('s2')], actor='app', after=['rpc.remove.remove.remove'],
        requires=['rpc.create.create.minimal-read'])
    rpc('remove', 'remove', 'remaining', 'getAllSubtasks', [Ref('t')],
        after=['rpc.remove.remove.remove', 'rpc.update.validation.unassigned-read'])
    rpc('remove', 'remove', 'task-totals', 'getTask', [Ref('t')], project=times, after=['rpc.remove.remove.remove',
                                                                                       'rpc.update.update.task-totals'])
    rpc('remove', 'remove', 'remove-again', 'removeSubtask', [Ref('s2')], actor='app',
        after=['rpc.remove.remove.remove'])

    # -- timers ---------------------------------------------------------------------------------------------
    fx('timer', 'subtask', 'createSubtask', {'task_id': Ref('t2'), 'title': 'Timed work', 'user_id': Ref('sue')},
       save='st')
    rpc('timer', 'timer', 'no-timer', 'hasSubtaskTimer', [Ref('st'), Ref('sue')], actor='sue')
    rpc('timer', 'timer', 'start', 'setSubtaskStartTime', [Ref('st'), Ref('sue')], actor='sue')
    rpc('timer', 'timer', 'running', 'hasSubtaskTimer', [Ref('st'), Ref('sue')], actor='sue',
        after=['rpc.timer.timer.start'])
    rpc('timer', 'timer', 'running-in-list', 'getAllSubtasks', [Ref('t2')], actor='sue',
        project=lambda c, r: {'http': r.status, 'running': [[x['title'], x['is_timer_started'],
                                                             c.norm.time(x['timer_start_date'])] for x in r.result]},
        after=['rpc.timer.timer.start'])
    rpc('timer', 'timer', 'start-again', 'setSubtaskStartTime', [Ref('st'), Ref('sue')], actor='sue',
        after=['rpc.timer.timer.start'])
    rpc('timer', 'timer', 'other-user-start', 'setSubtaskStartTime', [Ref('st'), 1], actor='sue')
    rpc('timer', 'timer', 'admin-timer', 'hasSubtaskTimer', [Ref('st'), 1], actor='sue')
    rpc('timer', 'timer', 'stop', 'setSubtaskEndTime', [Ref('st'), Ref('sue')], actor='sue',
        after=['rpc.timer.timer.start'])
    rpc('timer', 'timer', 'stopped', 'hasSubtaskTimer', [Ref('st'), Ref('sue')], actor='sue',
        after=['rpc.timer.timer.stop'], requires=['rpc.timer.timer.running'])
    rpc('timer', 'timer', 'stop-without-timer', 'setSubtaskEndTime', [Ref('st'), Ref('sue')], actor='sue',
        after=['rpc.timer.timer.stop'])
    rpc('timer', 'timer', 'application-start', 'setSubtaskStartTime', [Ref('st'), Ref('sue')], actor='app',
        after=['rpc.timer.timer.stop'])
    rpc('timer', 'timer', 'application-running', 'hasSubtaskTimer', [Ref('st'), Ref('sue')], actor='app',
        after=['rpc.timer.timer.application-start'])
    rpc('timer', 'timer', 'application-stop', 'setSubtaskEndTime', [Ref('st'), Ref('sue')], actor='app',
        after=['rpc.timer.timer.application-start'])
    rpc('timer', 'timer', 'missing-subtask', 'hasSubtaskTimer', [987654, Ref('sue')], actor='app')
