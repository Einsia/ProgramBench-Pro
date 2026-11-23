"""Automatic actions through the JSON-RPC API: the catalogue of actions and events, creation and its validation,
listing and removal, and the effect of each action when its event happens (task creation and updates, moves between
columns and swimlanes, assignment, closing, links) or when the daily background job runs (the cron job URL).

One point per action covers the event and its effect: the request that makes the event happen is part of the effect
observation, not a point of its own. Refused creations are attempted in a project of their own (Action checks)."""
import time

from harness import RESULTS, WEBHOOK_TOKEN, Ref, refs, resolve

PASSWORD = 'Actions-Pass-2026'
A = '\\Kanboard\\Action\\'


def task_view(c, r):
    """The task fields automatic actions change."""
    observation = {'http': r.status}
    if r.has_result and isinstance(r.result, dict):
        task = r.result
        observation['task'] = c.norm.clean({k: task.get(k) for k in (
            'title', 'project_id', 'column_id', 'swimlane_id', 'owner_id', 'color_id', 'category_id', 'priority',
            'is_active', 'date_due', 'date_started', 'position')}, 'task')
    else:
        observation['result'] = c.norm.clean(r.body.get('result') if isinstance(r.body, dict) else None)
    return observation


def summary(c, project):
    tasks = c.call('getAllTasks', [project, 1]) + c.call('getAllTasks', [project, 0])
    return {'@unordered': [c.norm.clean({k: t.get(k) for k in (
        'title', 'column_id', 'swimlane_id', 'owner_id', 'color_id', 'category_id', 'is_active', 'date_due')}, 'task')
        for t in tasks]}


# The refused creations (action, event) of the validation cases, and the checks project's own valid action.
REFUSED = {('TaskTeleport', 'task.create'), ('TaskAssignColorColumn', 'task.close'),
           ('TaskAssignColorColumn', 'task.move.column'), ('TaskCloseColumn', 'task.move.column'),
           ('TaskAssignSpecificUser', 'task.move.column')}
ANCHOR = ('TaskAssignColorColumn', 'task.create')


def refused_actions(c, r):
    """Which refused creations the checks project lists, and whether it lists its own action."""
    rows = None
    if r.has_result and isinstance(r.result, list):
        rows = [(str(a.get('action_name', '')).rsplit('\\', 1)[-1], a.get('event_name')) for a in r.result
                if isinstance(a, dict)]
    return {'http': r.status, 'anchor-listed': rows is not None and ANCHOR in rows,
            'refused-stored': sorted('|'.join(x) for x in rows or [] if x in REFUSED)}


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'user', 'createUser', {'username': 'ana', 'password': PASSWORD, 'name': 'Ana Actor'}, save='ana',
       password=PASSWORD)
    fx('base', 'user2', 'createUser', {'username': 'ben', 'password': PASSWORD, 'name': 'Ben Bystander'}, save='ben',
       password=PASSWORD)
    fx('base', 'admin', 'getUserByName', ['admin'], save='admin')

    # -- catalogue ------------------------------------------------------------------------------------------
    rpc('catalogue', 'catalogue', 'actions', 'getAvailableActions')
    rpc('catalogue', 'catalogue', 'events', 'getAvailableActionEvents')
    for name in ('TaskClose', 'TaskCloseColumn', 'TaskAssignColorColumn', 'TaskDuplicateAnotherProject',
                 'TaskMoveColumnAssigned', 'TaskAssignColorOnDueDate', 'TaskAssignCategoryLink', 'CommentCreation'):
        rpc('catalogue', 'compatible', name, 'getCompatibleActionEvents', [A + name])
    rpc('catalogue', 'compatible', 'unknown-action', 'getCompatibleActionEvents', [A + 'TaskTeleport'])

    # -- creation, validation, listing, removal -----------------------------------------------------------------
    fx('manage', 'project', 'createProject', {'name': 'Action catalogue project'}, save='mp')
    fx('manage', 'columns', 'getColumns', [Ref('mp')], save='mcols')
    fx('manage', 'other', 'createProject', {'name': 'Foreign project'}, save='fp')
    fx('manage', 'other-columns', 'getColumns', [Ref('fp')], save='fcols')
    fx('manage', 'checks', 'createProject', {'name': 'Action checks'}, save='vp')
    fx('manage', 'checks-columns', 'getColumns', [Ref('vp')], save='vcols')
    fx('manage', 'checks-anchor', 'createAction', [Ref('vp'), 'task.create', A + 'TaskAssignColorColumn',
                                                   {'column_id': Ref('vcols', 0, 'id'), 'color_id': 'green'}])
    rpc('manage', 'create', 'close-in-column', 'createAction', {
        'project_id': Ref('mp'), 'event_name': 'task.move.column', 'action_name': A + 'TaskCloseColumn',
        'params': {'column_id': Ref('mcols', 3, 'id')}}, save='a1')
    rpc('manage', 'create', 'color-on-create', 'createAction', [
        Ref('mp'), 'task.create', A + 'TaskAssignColorColumn', {'column_id': Ref('mcols', 0, 'id'),
                                                                'color_id': 'red'}], save='a2')
    rpc('manage', 'create', 'listed', 'getActions', [Ref('mp')],
        after=['rpc.manage.create.close-in-column', 'rpc.manage.create.color-on-create'])
    rpc('manage', 'validation', 'unknown-action', 'createAction', [
        Ref('vp'), 'task.create', A + 'TaskTeleport', {'column_id': Ref('vcols', 0, 'id')}])
    rpc('manage', 'validation', 'incompatible-event', 'createAction', [
        Ref('vp'), 'task.close', A + 'TaskAssignColorColumn', {'column_id': Ref('vcols', 0, 'id'), 'color_id': 'red'}])
    rpc('manage', 'validation', 'missing-parameter', 'createAction', [
        Ref('vp'), 'task.move.column', A + 'TaskAssignColorColumn', {'column_id': Ref('vcols', 0, 'id')}])
    rpc('manage', 'validation', 'extra-parameter', 'createAction', [
        Ref('vp'), 'task.move.column', A + 'TaskCloseColumn', {'column_id': Ref('vcols', 0, 'id'), 'color_id': 'red'}])
    rpc('manage', 'validation', 'empty-parameters', 'createAction', [Ref('vp'), 'task.create', A + 'TaskAssignCurrentUser',
                                                                     {}])
    rpc('manage', 'validation', 'foreign-column', 'createAction', [
        Ref('vp'), 'task.move.column', A + 'TaskCloseColumn', {'column_id': Ref('fcols', 0, 'id')}])
    rpc('manage', 'validation', 'foreign-column-application', 'createAction', [
        Ref('vp'), 'task.move.column', A + 'TaskCloseColumn', {'column_id': Ref('fcols', 0, 'id')}], actor='app')
    rpc('manage', 'validation', 'non-numeric-column', 'createAction', [
        Ref('vp'), 'task.move.column', A + 'TaskCloseColumn', {'column_id': 'last'}])
    rpc('manage', 'validation', 'unassignable-user', 'createAction', [
        Ref('vp'), 'task.move.column', A + 'TaskAssignSpecificUser', {'column_id': Ref('vcols', 1, 'id'),
                                                                      'user_id': Ref('ben')}])
    rpc('manage', 'validation', 'not-stored', 'getActions', [Ref('vp')], project=refused_actions,
        describe='getActions of the checks project after the refused creations')
    rpc('manage', 'remove', 'remove', 'removeAction', [Ref('a1')], after=['rpc.manage.create.listed'])
    rpc('manage', 'remove', 'remaining', 'getActions', [Ref('mp')], after=['rpc.manage.remove.remove'])
    rpc('manage', 'remove', 'again', 'removeAction', [Ref('a1')], actor='app', after=['rpc.manage.remove.remove'])

    # -- effects ----------------------------------------------------------------------------------------------
    def scenario(key, action, event, params, *, trigger, trigger_params=None, trigger_actor='admin', check='task',
                 setup=(), title=None, task_extra=None, prepare_trigger=None, negative=None):
        """One action: its project and task fixtures, the scored creation and the scored effect (one observation of
        the request that makes the event happen and of the state read afterwards); negative (method, params) is a
        second trigger that must not fire the action."""
        fx(key, 'project', 'createProject', {'name': 'Action ' + key}, save=key + '-p')
        fx(key, 'columns', 'getColumns', [Ref(key + '-p')], save=key + '-c')
        fx(key, 'lanes', 'getAllSwimlanes', [Ref(key + '-p')], save=key + '-s')
        fx(key, 'member', 'addProjectUser', [Ref(key + '-p'), Ref('ana'), 'project-member'])
        for i, (method, fparams, save) in enumerate(setup):
            fx(key, f'setup-{i}', method, fparams, save=save)
        if title:
            fx(key, 'task', 'createTask', {'title': title, 'project_id': Ref(key + '-p'), **(task_extra or {})},
               save=key + '-t')
        created = rpc(key, 'action', 'create', 'createAction', [Ref(key + '-p'), event, A + action, params])
        read = ('getTask', [Ref(key + '-t')], task_view) if check == 'task' else check

        def effect(c):
            # The event happens (the request is part of this observation), then the effect is read.
            if prepare_trigger:
                prepare_trigger(c)
            if trigger == 'cron':
                response = c.http('GET', '/cronjob?token=' + WEBHOOK_TOKEN)
                fired = {'http': response.status, 'body': response.text.strip()[:100]}
            else:
                response = c.rpc(trigger, resolve(trigger_params, c), resolve(trigger_actor, c))
                fired = c.outcome(response)
                if trigger == 'createTask' and response.has_result and response.result not in (False, None):
                    c.state[key + '-t'] = response.result
                    c.norm.register(key + '-t', response.result, 'task')
            response = c.rpc(read[0], resolve(read[1], c))
            seen = read[2](c, response) if read[2] else c.observe(response, RESULTS.get(read[0], {}).get('kind'))
            return {'event': fired, 'effect': seen}
        what = 'the cron job URL' if trigger == 'cron' else trigger
        fired = suite.add(key, 'action', 'effect', effect, after=[created],
                          reads=refs(trigger_params) | (refs(read[1]) - {key + '-t'}),
                          description=f'{read[0]} after {what} with the action {action} ({key})')
        if negative:
            rpc(key, 'action', 'no-effect', negative[0], negative[1], negative[2] if len(negative) > 2 else 'admin',
                after=[fired], project=lambda c, r: {'trigger': c.outcome(r), 'tasks': summary(c, c.state[key + '-p'])})

    scenario('close-column', 'TaskCloseColumn', 'task.move.column', {'column_id': Ref('close-column-c', 3, 'id')},
             title='Finish me', trigger='moveTaskPosition',
             trigger_params=[Ref('close-column-p'), Ref('close-column-t'), Ref('close-column-c', 3, 'id'), 1,
                             Ref('close-column-s', 0, 'id')],
             negative=('createTask', {'title': 'Stays open', 'project_id': Ref('close-column-p'),
                                      'column_id': Ref('close-column-c', 2, 'id')}))
    scenario('color-column', 'TaskAssignColorColumn', 'task.move.column',
             {'column_id': Ref('color-column-c', 1, 'id'), 'color_id': 'green'}, title='Paint me',
             trigger='moveTaskPosition',
             trigger_params=[Ref('color-column-p'), Ref('color-column-t'), Ref('color-column-c', 1, 'id'), 1,
                             Ref('color-column-s', 0, 'id')])
    scenario('color-create', 'TaskAssignColorColumn', 'task.create',
             {'column_id': Ref('color-create-c', 2, 'id'), 'color_id': 'purple'},
             trigger='createTask', trigger_params={'title': 'Born purple', 'project_id': Ref('color-create-p'),
                                                   'column_id': Ref('color-create-c', 2, 'id')},
             negative=('createTask', {'title': 'Born yellow', 'project_id': Ref('color-create-p')}))
    scenario('assign-me', 'TaskAssignCurrentUser', 'task.create', {}, trigger='createTask', trigger_actor='ana',
             trigger_params={'title': 'Mine now', 'project_id': Ref('assign-me-p')},
             negative=('createTask', {'title': 'Made by the application', 'project_id': Ref('assign-me-p')}, 'app'))
    scenario('assign-specific', 'TaskAssignSpecificUser', 'task.move.column',
             {'column_id': Ref('assign-specific-c', 2, 'id'), 'user_id': Ref('ana')}, title='Hand over',
             trigger='moveTaskPosition',
             trigger_params=[Ref('assign-specific-p'), Ref('assign-specific-t'), Ref('assign-specific-c', 2, 'id'), 1,
                             Ref('assign-specific-s', 0, 'id')])
    scenario('assign-creator', 'TaskAssignCreator', 'task.move.column', {'column_id': Ref('assign-creator-c', 1, 'id')},
             title='Back to its creator', task_extra={'creator_id': Ref('ana')}, trigger='moveTaskPosition',
             trigger_params=[Ref('assign-creator-p'), Ref('assign-creator-t'), Ref('assign-creator-c', 1, 'id'), 1,
                             Ref('assign-creator-s', 0, 'id')])
    scenario('assign-mover', 'TaskAssignCurrentUserColumn', 'task.move.column',
             {'column_id': Ref('assign-mover-c', 2, 'id')}, title='Whoever moves it', trigger='moveTaskPosition',
             trigger_actor='ana',
             trigger_params=[Ref('assign-mover-p'), Ref('assign-mover-t'), Ref('assign-mover-c', 2, 'id'), 1,
                             Ref('assign-mover-s', 0, 'id')])
    scenario('assign-if-none', 'TaskAssignCurrentUserColumnIfNoUserAlreadySet', 'task.move.column',
             {'column_id': Ref('assign-if-none-c', 2, 'id')}, title='Already owned',
             task_extra={'owner_id': Ref('ana')}, trigger='moveTaskPosition',
             trigger_params=[Ref('assign-if-none-p'), Ref('assign-if-none-t'), Ref('assign-if-none-c', 2, 'id'), 1,
                             Ref('assign-if-none-s', 0, 'id')])
    scenario('assign-in-column', 'TaskAssignToUserOnCreationInColumn', 'task.create',
             {'column_id': Ref('assign-in-column-c', 1, 'id')}, trigger='createTask', trigger_actor='ana',
             trigger_params={'title': 'Created in ready', 'project_id': Ref('assign-in-column-p'),
                             'column_id': Ref('assign-in-column-c', 1, 'id')},
             negative=('createTask', {'title': 'Created in backlog', 'project_id': Ref('assign-in-column-p')}))
    scenario('move-assigned', 'TaskMoveColumnAssigned', 'task.assignee_change',
             {'src_column_id': Ref('move-assigned-c', 0, 'id'), 'dest_column_id': Ref('move-assigned-c', 2, 'id')},
             title='Assign and move', trigger='updateTask',
             trigger_params={'id': Ref('move-assigned-t'), 'owner_id': Ref('ana')})
    scenario('move-unassigned', 'TaskMoveColumnUnAssigned', 'task.assignee_change',
             {'src_column_id': Ref('move-unassigned-c', 1, 'id'), 'dest_column_id': Ref('move-unassigned-c', 0, 'id')},
             title='Unassign and move back', task_extra={'owner_id': Ref('ana'),
                                                         'column_id': Ref('move-unassigned-c', 1, 'id')},
             trigger='updateTask', trigger_params={'id': Ref('move-unassigned-t'), 'owner_id': 0})
    scenario('move-closed', 'TaskMoveColumnClosed', 'task.close', {'dest_column_id': Ref('move-closed-c', 3, 'id')},
             title='Close and move', trigger='closeTask', trigger_params=[Ref('move-closed-t')])
    scenario('move-category', 'TaskMoveColumnCategoryChange', 'task.update',
             {'dest_column_id': Ref('move-category-c', 2, 'id'), 'category_id': Ref('move-category-k')},
             setup=[('createCategory', [Ref('move-category-p'), 'Escalated'], 'move-category-k')],
             title='Categorise and move', trigger='updateTask',
             trigger_params={'id': Ref('move-category-t'), 'category_id': Ref('move-category-k')})
    scenario('lane-category', 'TaskMoveSwimlaneCategoryChange', 'task.update',
             {'dest_swimlane_id': Ref('lane-category-l'), 'category_id': Ref('lane-category-k')},
             setup=[('createCategory', [Ref('lane-category-p'), 'Support'], 'lane-category-k'),
                    ('addSwimlane', [Ref('lane-category-p'), 'Support lane'], 'lane-category-l')],
             title='Categorise and change lane', trigger='updateTask',
             trigger_params={'id': Ref('lane-category-t'), 'category_id': Ref('lane-category-k')})
    scenario('lane-assigned', 'TaskMoveSwimlaneAssigned', 'task.assignee_change',
             {'user_id': Ref('ana'), 'dest_swimlane_id': Ref('lane-assigned-l')},
             setup=[('addSwimlane', [Ref('lane-assigned-p'), 'Ana lane'], 'lane-assigned-l')],
             title='Assign and change lane', trigger='updateTask',
             trigger_params={'id': Ref('lane-assigned-t'), 'owner_id': Ref('ana')})
    scenario('color-category', 'TaskAssignColorCategory', 'task.create_update',
             {'color_id': 'orange', 'category_id': Ref('color-category-k')},
             setup=[('createCategory', [Ref('color-category-p'), 'Hot'], 'color-category-k')],
             trigger='createTask', trigger_params={'title': 'Hot task', 'project_id': Ref('color-category-p'),
                                                   'category_id': Ref('color-category-k')})
    scenario('category-color', 'TaskAssignCategoryColor', 'task.create_update',
             {'color_id': 'red', 'category_id': Ref('category-color-k')},
             setup=[('createCategory', [Ref('category-color-p'), 'Alarm'], 'category-color-k')],
             title='Turns red', trigger='updateTask', trigger_params={'id': Ref('category-color-t'), 'color_id': 'red'})
    scenario('color-priority', 'TaskAssignColorPriority', 'task.create_update', {'color_id': 'pink', 'priority': 3},
             trigger='createTask', trigger_params={'title': 'Top priority', 'project_id': Ref('color-priority-p'),
                                                   'priority': 3},
             negative=('createTask', {'title': 'Low priority', 'project_id': Ref('color-priority-p'), 'priority': 1}))
    scenario('color-user', 'TaskAssignColorUser', 'task.assignee_change', {'color_id': 'teal', 'user_id': Ref('ana')},
             title='Ana colour', trigger='updateTask', trigger_params={'id': Ref('color-user-t'),
                                                                     'owner_id': Ref('ana')})
    scenario('color-lane', 'TaskAssignColorSwimlane', 'task.move.swimlane',
             {'swimlane_id': Ref('color-lane-l'), 'color_id': 'brown'},
             setup=[('addSwimlane', [Ref('color-lane-p'), 'Brown lane'], 'color-lane-l')],
             title='Change lane', trigger='moveTaskPosition',
             trigger_params=[Ref('color-lane-p'), Ref('color-lane-t'), Ref('color-lane-c', 0, 'id'), 1,
                             Ref('color-lane-l')])
    scenario('priority-lane', 'TaskAssignPrioritySwimlane', 'task.move.swimlane',
             {'swimlane_id': Ref('priority-lane-l'), 'priority': 2},
             setup=[('addSwimlane', [Ref('priority-lane-p'), 'Fast lane'], 'priority-lane-l')],
             title='Speed up', trigger='moveTaskPosition',
             trigger_params=[Ref('priority-lane-p'), Ref('priority-lane-t'), Ref('priority-lane-c', 0, 'id'), 1,
                             Ref('priority-lane-l')])
    scenario('user-lane', 'TaskAssignUserSwimlaneChange', 'task.move.swimlane',
             {'swimlane_id': Ref('user-lane-l'), 'user_id': Ref('ana')},
             setup=[('addSwimlane', [Ref('user-lane-p'), 'Ana handles'], 'user-lane-l')],
             title='Give to Ana', trigger='moveTaskPosition',
             trigger_params=[Ref('user-lane-p'), Ref('user-lane-t'), Ref('user-lane-c', 0, 'id'), 1,
                             Ref('user-lane-l')])
    scenario('category-lane', 'TaskAssignCategorySwimlaneChange', 'task.create',
             {'swimlane_id': Ref('category-lane-l'), 'category_id': Ref('category-lane-k')},
             setup=[('addSwimlane', [Ref('category-lane-p'), 'Bugs lane'], 'category-lane-l'),
                    ('createCategory', [Ref('category-lane-p'), 'Bug'], 'category-lane-k')],
             trigger='createTask', trigger_params={'title': 'Created in bugs lane', 'project_id': Ref('category-lane-p'),
                                                   'swimlane_id': Ref('category-lane-l')})
    scenario('due-on-create', 'TaskAssignDueDateOnCreation', 'task.create', {'duration': 5},
             trigger='createTask', trigger_params={'title': 'Due in five days', 'project_id': Ref('due-on-create-p')})
    scenario('due-on-move', 'TaskAssignDueDateOnMoveColumn', 'task.move.column',
             {'duration': 2, 'column_id': Ref('due-on-move-c', 0, 'id')}, title='Due after leaving backlog',
             trigger='moveTaskPosition',
             trigger_params=[Ref('due-on-move-p'), Ref('due-on-move-t'), Ref('due-on-move-c', 1, 'id'), 1,
                             Ref('due-on-move-s', 0, 'id')])
    scenario('start-on-move', 'TaskUpdateStartDate', 'task.move.column', {'column_id': Ref('start-on-move-c', 2, 'id')},
             title='Started when in progress', trigger='moveTaskPosition',
             trigger_params=[Ref('start-on-move-p'), Ref('start-on-move-t'), Ref('start-on-move-c', 2, 'id'), 1,
                             Ref('start-on-move-s', 0, 'id')])
    scenario('start-on-leave', 'TaskUpdateStartDateOnMoveColumn', 'task.move.column',
             {'column_id': Ref('start-on-leave-c', 0, 'id')}, title='Started when leaving backlog',
             trigger='moveTaskPosition',
             trigger_params=[Ref('start-on-leave-p'), Ref('start-on-leave-t'), Ref('start-on-leave-c', 3, 'id'), 1,
                             Ref('start-on-leave-s', 0, 'id')])
    scenario('comment-on-move', 'CommentCreationMoveTaskColumn', 'task.move.column',
             {'column_id': Ref('comment-on-move-c', 1, 'id')}, title='Leave a trace', trigger='moveTaskPosition',
             trigger_params=[Ref('comment-on-move-p'), Ref('comment-on-move-t'), Ref('comment-on-move-c', 1, 'id'), 1,
                             Ref('comment-on-move-s', 0, 'id')],
             check=('getAllComments', [Ref('comment-on-move-t')], None))
    scenario('subtask-on-move', 'SubtaskTimerMoveTaskColumn', 'task.move.column',
             {'column_id': Ref('subtask-on-move-c', 2, 'id'), 'subtask': 'Working on it'}, title='Start the clock',
             trigger='moveTaskPosition',
             trigger_params=[Ref('subtask-on-move-p'), Ref('subtask-on-move-t'), Ref('subtask-on-move-c', 2, 'id'), 1,
                             Ref('subtask-on-move-s', 0, 'id')],
             check=('getAllSubtasks', [Ref('subtask-on-move-t')],
                    lambda c, r: {'http': r.status, 'subtasks': [[s['title'], s['status'], s['username'],
                                                                  s['is_timer_started']] for s in r.result]}))
    scenario('duplicate-project', 'TaskDuplicateAnotherProject', 'task.close',
             {'column_id': Ref('duplicate-project-c', 0, 'id'), 'project_id': Ref('duplicate-project-d')},
             setup=[('createProject', {'name': 'Duplicate destination'}, 'duplicate-project-d')],
             title='Copy me on close', trigger='closeTask', trigger_params=[Ref('duplicate-project-t')],
             check=('getAllTasks', [Ref('duplicate-project-d'), 1],
                    lambda c, r: {'http': r.status, 'tasks': summary(c, c.state['duplicate-project-d'])}))
    scenario('move-project', 'TaskMoveAnotherProject', 'task.move.column',
             {'column_id': Ref('move-project-c', 3, 'id'), 'project_id': Ref('move-project-d')},
             setup=[('createProject', {'name': 'Move destination'}, 'move-project-d')],
             title='Send me away', trigger='moveTaskPosition',
             trigger_params=[Ref('move-project-p'), Ref('move-project-t'), Ref('move-project-c', 3, 'id'), 1,
                             Ref('move-project-s', 0, 'id')])
    scenario('color-link', 'TaskAssignColorLink', 'task_internal_link.create_update', {'color_id': 'grey', 'link_id': 2},
             setup=[('createTask', {'title': 'Blocked one', 'project_id': Ref('color-link-p')}, 'color-link-o')],
             title='Blocker', trigger='createTaskLink', trigger_params=[Ref('color-link-t'), Ref('color-link-o'), 2])
    scenario('category-link', 'TaskAssignCategoryLink', 'task_internal_link.create_update',
             {'category_id': Ref('category-link-k'), 'link_id': 4},
             setup=[('createCategory', [Ref('category-link-p'), 'Duplicate'], 'category-link-k'),
                    ('createTask', {'title': 'Original one', 'project_id': Ref('category-link-p')}, 'category-link-o')],
             title='Copycat', trigger='createTaskLink', trigger_params=[Ref('category-link-t'), Ref('category-link-o'), 4])

    # -- the daily background job --------------------------------------------------------------------------
    def wait_a_second(c):
        time.sleep(1.2)
    scenario('cron-color-due', 'TaskAssignColorOnDueDate', 'task.cronjob.daily', {'color_id': 'red'},
             setup=[('createTask', {'title': 'Due tomorrow', 'project_id': Ref('cron-color-due-p'),
                                    'date_due': '2026-04-15 12:00'}, None)],
             title='Overdue', task_extra={'date_due': '2026-04-10 12:00'}, trigger='cron', check=('getAllTasks', [Ref('cron-color-due-p'), 1],
                                          lambda c, r: {'http': r.status, 'tasks': summary(c, c.state['cron-color-due-p'])}))
    scenario('cron-color-start', 'TaskAssignColorOnStartDate', 'task.cronjob.daily', {'color_id': 'amber'},
             setup=[('createTask', {'title': 'Starts later', 'project_id': Ref('cron-color-start-p'),
                                    'date_started': '2026-05-01 09:00'}, None)],
             title='Started', task_extra={'date_started': '2026-04-10 09:00'}, trigger='cron', check=('getAllTasks', [Ref('cron-color-start-p'), 1],
                                          lambda c, r: {'http': r.status,
                                                        'tasks': summary(c, c.state['cron-color-start-p'])}))
    scenario('cron-move-due', 'TaskMoveColumnOnDueDate', 'task.cronjob.daily',
             {'duration': 3, 'src_column_id': Ref('cron-move-due-c', 0, 'id'),
              'dest_column_id': Ref('cron-move-due-c', 2, 'id')},
             setup=[('createTask', {'title': 'Due in a month', 'project_id': Ref('cron-move-due-p'),
                                    'date_due': '2026-05-14 12:00'}, None)],
             title='Due in two days', task_extra={'date_due': '2026-04-16 12:00'}, trigger='cron', check=('getAllTasks', [Ref('cron-move-due-p'), 1],
                                          lambda c, r: {'http': r.status, 'tasks': summary(c, c.state['cron-move-due-p'])}))
    scenario('cron-move-start', 'TaskMoveColumnOnStartDate', 'task.cronjob.daily',
             {'src_column_id': Ref('cron-move-start-c', 0, 'id'), 'dest_column_id': Ref('cron-move-start-c', 2, 'id')},
             title='Should have started', task_extra={'date_started': '2026-04-13 09:00'}, trigger='cron', check=('getAllTasks', [Ref('cron-move-start-p'), 1],
                                          lambda c, r: {'http': r.status,
                                                        'tasks': summary(c, c.state['cron-move-start-p'])}))
    scenario('cron-close-idle', 'TaskCloseNoActivity', 'task.cronjob.daily', {'duration': 0},
             title='Idle task', trigger='cron', prepare_trigger=wait_a_second,
             check=('getAllTasks', [Ref('cron-close-idle-p'), 1],
                    lambda c, r: {'http': r.status, 'tasks': summary(c, c.state['cron-close-idle-p'])}))
    scenario('cron-keep-active', 'TaskCloseNoActivity', 'task.cronjob.daily', {'duration': 2},
             title='Recently active', trigger='cron',
             check=('getAllTasks', [Ref('cron-keep-active-p'), 1],
                    lambda c, r: {'http': r.status, 'tasks': summary(c, c.state['cron-keep-active-p'])}))
    scenario('cron-close-column', 'TaskCloseNoActivityColumn', 'task.cronjob.daily',
             {'duration': 0, 'column_id': Ref('cron-close-column-c', 1, 'id')},
             setup=[('createTask', {'title': 'Idle in backlog', 'project_id': Ref('cron-close-column-p')}, None)],
             title='Idle in ready', task_extra={'column_id': Ref('cron-close-column-c', 1, 'id')},
             trigger='cron', prepare_trigger=wait_a_second,
             check=('getAllTasks', [Ref('cron-close-column-p'), 1],
                    lambda c, r: {'http': r.status, 'tasks': summary(c, c.state['cron-close-column-p'])}))
    scenario('cron-move-idle', 'TaskMoveColumnNotMovedPeriod', 'task.cronjob.daily',
             {'duration': 0, 'src_column_id': Ref('cron-move-idle-c', 0, 'id'),
              'dest_column_id': Ref('cron-move-idle-c', 3, 'id')},
             title='Stuck in backlog', trigger='cron', prepare_trigger=wait_a_second,
             check=('getAllTasks', [Ref('cron-move-idle-p'), 1],
                    lambda c, r: {'http': r.status, 'tasks': summary(c, c.state['cron-move-idle-p'])}))

    def cron_answer(token):
        def action(c):
            response = c.http('GET', '/cronjob?token=' + token)
            return {'http': response.status} if token != WEBHOOK_TOKEN else {'http': response.status,
                                                                            'body': response.text.strip()[:100]}
        return action
    suite.add('cron', 'url', 'right-token', cron_answer(WEBHOOK_TOKEN), description='GET /cronjob with the webhook token')
    suite.add('cron', 'url', 'wrong-token', cron_answer('not-the-token'), description='GET /cronjob with a wrong token',
              requires=['rpc.cron.url.right-token'])
