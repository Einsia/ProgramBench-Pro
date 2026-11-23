"""Project activity through the JSON-RPC API: the event that each kind of change records (its name, its title with
the names it mentions, its author and task), read as the newest events of the project's activity stream right after
the change. Changes are made by a signed-in user (the administrator); changes made with the application token record
no activity. Events of one change share a timestamp, so they are compared without order, like the whole stream."""
from harness import Ref, b64, events

PASSWORD = 'Activity-Pass-2026'


def newest(count):
    """The newest count events of the stream (no order among them)."""
    def project(c, response):
        observation = events(c, response)
        if isinstance(observation.get('result'), list):
            observation['result'] = {'@unordered': observation['result'][:count]}
        return observation
    return project


def unordered(c, response):
    observation = events(c, response)
    if isinstance(observation.get('result'), list):
        observation['result'] = {'@unordered': observation['result']}
    return observation


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'user', 'createUser', {'username': 'ana', 'password': PASSWORD, 'name': 'Ana Activity'}, save='ana',
       password=PASSWORD)
    fx('base', 'admin', 'getUserByName', ['admin'], save='admin')
    fx('base', 'project', 'createProject', {'name': 'Event project'}, actor='app', save='p')
    fx('base', 'target', 'createProject', {'name': 'Event target'}, actor='app', save='p2')
    fx('base', 'admin-member', 'addProjectUser', [Ref('p'), Ref('admin', 'id'), 'project-manager'], actor='app')
    fx('base', 'admin-target', 'addProjectUser', [Ref('p2'), Ref('admin', 'id'), 'project-manager'], actor='app')
    fx('base', 'member', 'addProjectUser', [Ref('p'), Ref('ana'), 'project-member'], actor='app')
    fx('base', 'columns', 'getColumns', [Ref('p')], actor='app', save='cols')
    fx('base', 'lane', 'addSwimlane', [Ref('p'), 'Second lane'], actor='app', save='lane')
    fx('base', 'lanes', 'getActiveSwimlanes', [Ref('p')], actor='app', save='lanes')
    # Made with the application token: no activity yet.
    fx('base', 'first', 'createTask', {'title': 'Backlog first', 'project_id': Ref('p')}, actor='app', save='t0')
    fx('base', 'second', 'createTask', {'title': 'Backlog second', 'project_id': Ref('p')}, actor='app', save='t8')
    fx('base', 'linked', 'createTask', {'title': 'Linked task', 'project_id': Ref('p')}, actor='app', save='t9')

    rpc('events', 'events', 'empty', 'getProjectActivity', [Ref('p')], project=events,
        describe='getProjectActivity before any change by a user (only application-token changes so far)')
    changes = []

    def change(step, method, params, count=1, save=None, actor=None, stream=None):
        extra = {} if actor is None else {'actor': actor}
        cid = rpc('events', 'events', step, method, params, save=save, **extra)
        rpc('events', 'events', step + '-event', 'getProjectActivity', [Ref(stream or 'p')], project=newest(count),
            after=[cid], describe=f'getProjectActivity after {method} ({step}), newest {count}')
        changes.append(cid)
        return cid

    change('create', 'createTask', {'title': 'Event task', 'project_id': Ref('p')}, save='t1')
    change('rename', 'updateTask', {'id': Ref('t1'), 'title': 'Event task renamed'})
    change('assign', 'updateTask', {'id': Ref('t1'), 'owner_id': Ref('ana')}, count=2)
    change('move-column', 'moveTaskPosition', {'project_id': Ref('p'), 'task_id': Ref('t1'),
                                               'column_id': Ref('cols', 1, 'id'), 'position': 1,
                                               'swimlane_id': Ref('lanes', 0, 'id')})
    change('move-position', 'moveTaskPosition', {'project_id': Ref('p'), 'task_id': Ref('t8'),
                                                 'column_id': Ref('cols', 0, 'id'), 'position': 1,
                                                 'swimlane_id': Ref('lanes', 0, 'id')})
    change('move-swimlane', 'moveTaskPosition', {'project_id': Ref('p'), 'task_id': Ref('t1'),
                                                 'column_id': Ref('cols', 1, 'id'), 'position': 1,
                                                 'swimlane_id': Ref('lane')})
    change('close', 'closeTask', [Ref('t1')])
    change('open', 'openTask', [Ref('t1')])
    change('subtask-create', 'createSubtask', {'task_id': Ref('t1'), 'title': 'Event subtask'}, save='st')
    change('subtask-update', 'updateSubtask', {'id': Ref('st'), 'task_id': Ref('t1'), 'status': 1})
    change('subtask-remove', 'removeSubtask', [Ref('st')])
    change('comment-create', 'createComment', {'task_id': Ref('t1'), 'user_id': Ref('admin', 'id'),
                                               'content': 'Event comment'}, save='cm')
    change('comment-update', 'updateComment', {'id': Ref('cm'), 'content': 'Event comment edited'})
    change('comment-remove', 'removeComment', [Ref('cm')])
    change('file-create', 'createTaskFile', [Ref('p'), Ref('t1'), 'event.txt', b64('event file')])
    # A link is recorded for both of its tasks.
    change('link-create', 'createTaskLink', [Ref('t1'), Ref('t9'), 1], count=2, save='tl')
    change('link-remove', 'removeTaskLink', [Ref('tl')])
    change('color', 'updateTask', {'id': Ref('t1'), 'color_id': 'red'})
    change('application-token', 'updateTask', {'id': Ref('t0'), 'title': 'Backlog first renamed'}, actor='app')
    change('as-member', 'updateTask', {'id': Ref('t0'), 'title': 'Renamed by Ana'}, actor='ana')
    rpc('events', 'events', 'stream', 'getProjectActivity', [Ref('p')], project=unordered, after=list(changes),
        describe='getProjectActivity: the whole stream after the changes')
    rpc('events', 'events', 'member-stream', 'getMyActivityStream', actor='ana', project=unordered,
        after=list(changes), describe='getMyActivityStream as ana after the changes')
    change('move-project', 'moveTaskToProject', [Ref('t1'), Ref('p2')], stream='p2')
