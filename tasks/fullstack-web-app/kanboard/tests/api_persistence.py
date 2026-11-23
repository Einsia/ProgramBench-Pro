"""Persistence: everything written through the API is still there after the application restarts with the same
data directory, and the user-specific procedures (getMe and the My... procedures) answer for each signed-in user."""
from harness import Ref, b64

PASSWORD = 'Persist-Pass-2026'


def restart_then(c):
    c.restart()


def build(suite):
    rpc, fx = suite.rpc, suite.fixture

    # -- the user-specific procedures ---------------------------------------------------------------------------
    fx('me', 'user', 'createUser', {'username': 'maya', 'password': PASSWORD, 'name': 'Maya Me',
                                    'email': 'maya@example.test'}, save='maya', password=PASSWORD)
    fx('me', 'manager', 'createUser', {'username': 'mark', 'password': PASSWORD, 'role': 'app-manager'}, save='mark',
       password=PASSWORD)
    fx('me', 'project', 'createProject', {'name': 'My project'}, save='mp')
    fx('me', 'project2', 'createProject', {'name': 'Not my project'}, save='np')
    fx('me', 'member', 'addProjectUser', [Ref('mp'), Ref('maya'), 'project-member'])
    fx('me', 'assigned', 'createTask', {'title': 'For Maya', 'project_id': Ref('mp'), 'owner_id': Ref('maya'),
                                        'date_due': '2026-04-12 12:00'}, save='mt1')
    fx('me', 'assigned2', 'createTask', {'title': 'Also for Maya', 'project_id': Ref('mp'), 'owner_id': Ref('maya'),
                                         'date_due': '2026-05-12 12:00'}, save='mt2')
    fx('me', 'subtask', 'createSubtask', {'task_id': Ref('mt2'), 'title': 'Maya subtask', 'user_id': Ref('maya')})
    fx('me', 'unassigned', 'createTask', {'title': 'Nobody', 'project_id': Ref('mp')})
    fx('me', 'elsewhere', 'createTask', {'title': 'Elsewhere', 'project_id': Ref('np')})
    rpc('me', 'me', 'get-me', 'getMe', actor='maya')
    rpc('me', 'me', 'get-me-manager', 'getMe', actor='mark')
    rpc('me', 'me', 'dashboard', 'getMyDashboard', actor='maya')
    rpc('me', 'me', 'dashboard-admin', 'getMyDashboard')
    rpc('me', 'me', 'projects', 'getMyProjects', actor='maya')
    rpc('me', 'me', 'projects-list', 'getMyProjectsList', actor='maya')
    rpc('me', 'me', 'projects-list-manager', 'getMyProjectsList', actor='mark')
    rpc('me', 'me', 'overdue', 'getMyOverdueTasks', actor='maya')
    rpc('me', 'me', 'activity', 'getMyActivityStream', actor='maya',
        project=lambda c, r: {'http': r.status, 'events': [[e['event_name'], c.norm.ident('task', e['task_id'])]
                                                           for e in r.result]})
    rpc('me', 'me', 'private-project', 'createMyPrivateProject', ['Maya private'], actor='maya', save='maya-private')
    rpc('me', 'me', 'private-listed', 'getMyProjectsList', actor='maya', after=['rpc.me.me.private-project'])
    rpc('me', 'me', 'private-hidden-from-admin', 'getAllProjects', actor='app',
        project=lambda c, r: {'http': r.status, 'names': sorted(p['name'] for p in r.result)},
        after=['rpc.me.me.private-project'])
    # The application token has no user session: the same procedures are refused for it.
    for step, method, params, positive in (
            ('dashboard-as-application', 'getMyDashboard', None, 'dashboard'),
            ('projects-as-application', 'getMyProjects', None, 'projects'),
            ('projects-list-as-application', 'getMyProjectsList', None, 'projects-list'),
            ('activity-as-application', 'getMyActivityStream', None, 'activity'),
            ('overdue-as-application', 'getMyOverdueTasks', None, 'overdue'),
            ('private-project-as-application', 'createMyPrivateProject', ['Private by app'], 'private-project')):
        rpc('me', 'me', step, method, params, actor='app', requires=['rpc.me.me.' + positive])

    # -- data written before a restart ------------------------------------------------------------------------
    fx('persist', 'user', 'createUser', {'username': 'pete', 'password': PASSWORD, 'name': 'Pete Persist'},
       save='pete', password=PASSWORD)
    fx('persist', 'group', 'createGroup', ['Persisted group'], save='pg')
    fx('persist', 'group-member', 'addGroupMember', [Ref('pg'), Ref('pete')])
    fx('persist', 'project', 'createProject', {'name': 'Durable project', 'identifier': 'DURABLE',
                                               'description': 'Survives restarts'}, save='pp')
    fx('persist', 'columns', 'getColumns', [Ref('pp')], save='pcols')
    fx('persist', 'member', 'addProjectUser', [Ref('pp'), Ref('pete'), 'project-manager'])
    fx('persist', 'group-role', 'addProjectGroup', [Ref('pp'), Ref('pg'), 'project-viewer'])
    fx('persist', 'column', 'addColumn', [Ref('pp'), 'Durable column', 4, 'Persisted column'], save='pcol')
    fx('persist', 'lane', 'addSwimlane', [Ref('pp'), 'Durable lane'], save='plane')
    fx('persist', 'category', 'createCategory', [Ref('pp'), 'Durable category', 'cyan'], save='pcat')
    fx('persist', 'task', 'createTask', {
        'title': 'Durable task', 'project_id': Ref('pp'), 'description': 'Persisted *markdown*', 'color_id': 'lime',
        'owner_id': Ref('pete'), 'category_id': Ref('pcat'), 'swimlane_id': Ref('plane'), 'column_id': Ref('pcol'),
        'date_due': '2026-05-20 10:00', 'score': 21, 'priority': 1, 'reference': 'DUR-1', 'tags': ['durable']},
       save='pt')
    fx('persist', 'task2', 'createTask', {'title': 'Durable closed task', 'project_id': Ref('pp')}, save='pt2')
    fx('persist', 'close', 'closeTask', [Ref('pt2')])
    fx('persist', 'subtask', 'createSubtask', {'task_id': Ref('pt'), 'title': 'Durable subtask', 'user_id': Ref('pete'),
                                               'time_estimated': 2, 'status': 1}, save='pst')
    fx('persist', 'comment', 'createComment', {'task_id': Ref('pt'), 'user_id': Ref('pete'),
                                               'content': 'Durable comment'}, actor='app', save='pcm')
    fx('persist', 'link', 'createTaskLink', [Ref('pt'), Ref('pt2'), 7], save='ptl')
    fx('persist', 'external', 'createExternalTaskLink', [Ref('pt'), 'https://example.org/durable', 'related'],
       save='pel')
    fx('persist', 'file', 'createTaskFile', [Ref('pp'), Ref('pt'), 'durable.txt', b64('durable bytes\n')], save='pf')
    fx('persist', 'project-file', 'createProjectFile', [Ref('pp'), 'durable-plan.txt', b64('durable plan\n')],
       save='ppf')
    fx('persist', 'task-meta', 'saveTaskMetadata', [Ref('pt'), {'kept': 'yes'}])
    fx('persist', 'project-meta', 'saveProjectMetadata', [Ref('pp'), {'kept': 'also'}])
    fx('persist', 'action', 'createAction', {'project_id': Ref('pp'), 'event_name': 'task.move.column',
                                             'action_name': '\\Kanboard\\Action\\TaskCloseColumn',
                                             'params': {'column_id': Ref('pcols', 3, 'id')}}, save='pa')
    fx('persist', 'link-label', 'createLink', ['persists with', 'is persisted with'], save='plink')
    fx('persist', 'public', 'enableProjectPublicAccess', [Ref('pp')])
    fx('persist', 'disabled-user', 'createUser', {'username': 'dora', 'password': PASSWORD}, save='dora')
    fx('persist', 'disable', 'disableUser', [Ref('dora')])

    def after_restart(step, method, params=None, actor='admin', **kwargs):
        if step == 'project':
            rpc('persist', 'restart', step, method, params, actor, prepare=restart_then, **kwargs)
        else:
            rpc('persist', 'restart', step, method, params, actor, after=['rpc.persist.restart.project'], **kwargs)
    after_restart('project', 'getProjectById', [Ref('pp')])
    after_restart('users', 'getProjectUsers', [Ref('pp')])
    after_restart('user-role', 'getProjectUserRole', [Ref('pp'), Ref('pete')])
    after_restart('columns', 'getColumns', [Ref('pp')])
    after_restart('swimlanes', 'getAllSwimlanes', [Ref('pp')])
    after_restart('categories', 'getAllCategories', [Ref('pp')])
    after_restart('task', 'getTask', [Ref('pt')])
    after_restart('closed-tasks', 'getAllTasks', [Ref('pp'), 0])
    after_restart('task-tags', 'getTaskTags', [Ref('pt')])
    after_restart('subtasks', 'getAllSubtasks', [Ref('pt')])
    after_restart('comments', 'getAllComments', [Ref('pt')])
    after_restart('task-links', 'getAllTaskLinks', [Ref('pt')])
    after_restart('external-links', 'getAllExternalTaskLinks', [Ref('pt')])
    after_restart('task-files', 'getAllTaskFiles', [Ref('pt')])
    after_restart('task-file-bytes', 'downloadTaskFile', [Ref('pf')])
    after_restart('project-files', 'getAllProjectFiles', [Ref('pp')])
    after_restart('task-metadata', 'getTaskMetadata', [Ref('pt')])
    after_restart('project-metadata', 'getProjectMetadata', [Ref('pp')])
    after_restart('actions', 'getActions', [Ref('pp')])
    after_restart('link-labels', 'getLinkById', [Ref('plink')])
    after_restart('group-members', 'getGroupMembers', [Ref('pg')])
    after_restart('user', 'getUser', [Ref('pete')])
    after_restart('password', 'getMe', actor='pete')
    after_restart('disabled-user', 'isActiveUser', [Ref('dora')])
    after_restart('application-token', 'getVersion', actor='app')
    after_restart('board', 'getBoard', [Ref('pp')])
    rpc('persist', 'restart', 'write-after-restart', 'createTask', {'title': 'Written after restart',
                                                                    'project_id': Ref('pp')}, save='pt3',
        after=['rpc.persist.restart.project'])
    rpc('persist', 'restart', 'second-restart', 'getTask', [Ref('pt3')], prepare=restart_then,
        after=['rpc.persist.restart.write-after-restart'])
    rpc('persist', 'restart', 'action-still-runs', 'moveTaskPosition', [Ref('pp'), Ref('pt3'), Ref('pcols', 3, 'id'), 1,
                                                                        Ref('plane')],
        after=['rpc.persist.restart.second-restart'])
    rpc('persist', 'restart', 'action-effect', 'getTask', [Ref('pt3')], after=['rpc.persist.restart.action-still-runs'],
        project=lambda c, r: {'http': r.status, 'is_active': r.result.get('is_active') if r.has_result and
                              isinstance(r.result, dict) else None})
