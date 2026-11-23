"""Tasks through the JSON-RPC API: creation with every field and its validation, date formats, reads, updates of
each field, tags, closing and reopening, ordering inside a cell, moving between columns, swimlanes and projects,
duplication, removal, overdue lists and recurring tasks.

Refused creations and edge cases are attempted in a project of their own (Task checks): whether a candidate accepts
or refuses one of them never changes the tasks, positions and lists the other cases observe."""
from harness import Ref

PASSWORD = 'Tasks-Pass-2026'
# Titles of the creations the reference refuses (their attempts happen in the Task checks project).
REFUSED = {'Due timestamp', 'Bad due', 'Text due', 'Backwards', 'Outsider owned', 'Outsider made', 'Bad color', '',
           'Bad score', 'Huge score', 'Lane zero', 'Lane negative', 'Long reference', 'Bad time'}


def refused_not_stored(c, r):
    """Which refused creations the checks project lists, and whether it lists its own anchor task."""
    titles = [t.get('title') for t in r.result if isinstance(t, dict)] \
        if r.has_result and isinstance(r.result, list) else None
    return {'http': r.status, 'anchor-listed': titles is not None and 'Checks anchor' in titles,
            'refused-stored': sorted(t for t in titles or [] if t in REFUSED)}


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'member', 'createUser', {'username': 'mona', 'password': PASSWORD, 'name': 'Mona Member'},
       save='mona', password=PASSWORD)
    fx('base', 'outsider', 'createUser', {'username': 'otto', 'password': PASSWORD, 'name': 'Otto Outside'},
       save='otto')
    fx('base', 'project', 'createProject', {'name': 'Task project', 'identifier': 'TASKS'}, save='p')
    fx('base', 'membership', 'addProjectUser', [Ref('p'), Ref('mona'), 'project-member'])
    fx('base', 'columns', 'getColumns', [Ref('p')], save='cols')
    fx('base', 'lanes', 'getAllSwimlanes', [Ref('p')], save='lanes')
    fx('base', 'lane', 'addSwimlane', [Ref('p'), 'Hotfix'], save='hotfix')
    fx('base', 'category', 'createCategory', [Ref('p'), 'Feature', 'blue'], save='feature')
    fx('base', 'other-project', 'createProject', {'name': 'Second task project'}, save='p2')
    fx('base', 'other-category', 'createCategory', [Ref('p2'), 'Feature'], save='feature2')
    fx('base', 'other-lane', 'addSwimlane', [Ref('p2'), 'Hotfix'], save='hotfix2')
    fx('base', 'other-columns', 'getColumns', [Ref('p2')], save='cols2')
    fx('base', 'checks-project', 'createProject', {'name': 'Task checks'}, save='vp')
    fx('base', 'checks-member', 'addProjectUser', [Ref('vp'), Ref('mona'), 'project-member'])
    fx('base', 'checks-anchor', 'createTask', {'title': 'Checks anchor', 'project_id': Ref('vp')})

    # -- creation -------------------------------------------------------------------------------------------
    rpc('create', 'create', 'minimal', 'createTask', {'title': 'Minimal task', 'project_id': Ref('p')}, save='t-min')
    rpc('create', 'create', 'minimal-read', 'getTask', [Ref('t-min')])
    rpc('create', 'create', 'full', 'createTask', {
        'title': 'Full task', 'project_id': Ref('p'), 'color_id': 'green', 'column_id': Ref('cols', 1, 'id'),
        'owner_id': Ref('mona'), 'creator_id': Ref('mona'), 'date_due': '2026-04-20 14:30',
        'description': 'Some **markdown**\n\n- item', 'category_id': Ref('feature'), 'score': 8,
        'swimlane_id': Ref('hotfix'), 'priority': 2, 'reference': 'TICKET-42', 'tags': ['api', 'urgent'],
        'date_started': '2026-04-15 09:00', 'time_estimated': 4.5, 'time_spent': 1.25}, save='t-full')
    rpc('create', 'create', 'full-read', 'getTask', [Ref('t-full')])
    rpc('create', 'create', 'full-tags', 'getTaskTags', [Ref('t-full')])
    rpc('create', 'create', 'positional', 'createTask', ['Positional task', Ref('p'), 'red', Ref('cols', 2, 'id')],
        save='t-pos')
    rpc('create', 'create', 'positional-read', 'getTask', [Ref('t-pos')])
    rpc('create', 'create', 'unicode', 'createTask', {'title': 'Tâche 任务 ✓', 'project_id': Ref('p'),
                                                      'description': 'Ünïcödé'}, save='t-uni')
    rpc('create', 'create', 'unicode-read', 'getTask', [Ref('t-uni')])
    rpc('create', 'create', 'second-in-cell', 'createTask', {'title': 'Second minimal', 'project_id': Ref('p')},
        save='t-min2', after=['rpc.create.create.minimal'])
    rpc('create', 'create', 'second-in-cell-read', 'getTask', [Ref('t-min2')])
    rpc('create', 'create', 'application-creator', 'createTask', {'title': 'Made by the application',
                                                                  'project_id': Ref('p')}, actor='app',
        save='t-app')
    rpc('create', 'create', 'application-creator-read', 'getTask', [Ref('t-app')])
    rpc('create', 'create', 'member-creator', 'createTask', {'title': 'Made by Mona', 'project_id': Ref('p')},
        actor='mona', save='t-mona')
    rpc('create', 'create', 'member-creator-read', 'getTask', [Ref('t-mona')])
    rpc('create', 'dates', 'due-date-only', 'createTask', {'title': 'Due date only', 'project_id': Ref('p'),
                                                           'date_due': '2026-05-01'}, save='t-d1')
    rpc('create', 'dates', 'due-user-format', 'createTask', {'title': 'Due user format', 'project_id': Ref('p'),
                                                             'date_due': '05/02/2026'}, save='t-d2')
    rpc('create', 'dates', 'due-underscore', 'createTask', {'title': 'Due underscore', 'project_id': Ref('p'),
                                                            'date_due': '2026_05_03'}, save='t-d3')
    rpc('create', 'dates', 'due-timestamp', 'createTask', {'title': 'Due timestamp', 'project_id': Ref('vp'),
                                                           'date_due': '1778000000'}, save='t-d4')
    rpc('create', 'dates', 'due-dates-read', 'getAllTasks', [Ref('p'), 1],
        project=lambda c, r: {'http': r.status, 'due': {'@map': {t['title']: c.norm.moment(t['date_due'])
                                                                 for t in r.result if t['title'].startswith('Due')}}},
        after=['rpc.create.dates.due-date-only', 'rpc.create.dates.due-user-format',
               'rpc.create.dates.due-underscore'])
    rpc('create', 'dates', 'due-invalid', 'createTask', {'title': 'Bad due', 'project_id': Ref('vp'),
                                                         'date_due': '2026-13-45'})
    rpc('create', 'dates', 'due-text', 'createTask', {'title': 'Text due', 'project_id': Ref('vp'),
                                                      'date_due': 'next week'})
    rpc('create', 'dates', 'start-after-due', 'createTask', {'title': 'Backwards', 'project_id': Ref('vp'),
                                                             'date_due': '2026-04-20', 'date_started': '2026-04-25'})
    rpc('create', 'dates', 'start-equals-due', 'createTask', {'title': 'Same day', 'project_id': Ref('vp'),
                                                              'date_due': '2026-04-20 10:00',
                                                              'date_started': '2026-04-20 10:00'}, save='t-same')
    rpc('create', 'validation', 'owner-not-member', 'createTask', {'title': 'Outsider owned', 'project_id': Ref('vp'),
                                                                   'owner_id': Ref('otto')})
    rpc('create', 'validation', 'creator-not-member', 'createTask', {'title': 'Outsider made', 'project_id': Ref('vp'),
                                                                     'creator_id': Ref('otto')})
    rpc('create', 'validation', 'invalid-color', 'createTask', {'title': 'Bad color', 'project_id': Ref('vp'),
                                                                'color_id': 'magenta'})
    rpc('create', 'validation', 'empty-title', 'createTask', {'title': '', 'project_id': Ref('vp')})
    rpc('create', 'validation', 'score-not-integer', 'createTask', {'title': 'Bad score', 'project_id': Ref('vp'),
                                                                    'score': 'big'})
    rpc('create', 'validation', 'score-out-of-range', 'createTask', {'title': 'Huge score', 'project_id': Ref('vp'),
                                                                     'score': 3000000000})
    rpc('create', 'validation', 'negative-score', 'createTask', {'title': 'Negative score', 'project_id': Ref('vp'),
                                                                 'score': -3}, save='t-neg')
    rpc('create', 'validation', 'swimlane-zero', 'createTask', {'title': 'Lane zero', 'project_id': Ref('vp'),
                                                                'swimlane_id': 0}, save='t-lane0')
    rpc('create', 'validation', 'swimlane-negative', 'createTask', {'title': 'Lane negative', 'project_id': Ref('vp'),
                                                                    'swimlane_id': -2})
    rpc('create', 'validation', 'reference-too-long', 'createTask', {'title': 'Long reference',
                                                                     'project_id': Ref('vp'), 'reference': 'r' * 192})
    rpc('create', 'validation', 'time-not-numeric', 'createTask', {'title': 'Bad time', 'project_id': Ref('vp'),
                                                                   'time_estimated': 'soon'})
    rpc('create', 'validation', 'missing-project', 'createTask', {'title': 'Nowhere', 'project_id': 987654},
        actor='app')
    rpc('create', 'validation', 'refusals-not-stored', 'getAllTasks', [Ref('vp'), 1], project=refused_not_stored,
        describe='getAllTasks of the checks project after the refused creations')

    # -- reads ----------------------------------------------------------------------------------------------
    rpc('read', 'read', 'by-reference', 'getTaskByReference', [Ref('p'), 'TICKET-42'], after=['rpc.create.create.full'])
    rpc('read', 'read', 'by-reference-missing', 'getTaskByReference', [Ref('p'), 'TICKET-404'],
        requires=['rpc.read.read.by-reference'])
    rpc('read', 'read', 'by-reference-other-project', 'getTaskByReference', [Ref('p2'), 'TICKET-42'],
        requires=['rpc.read.read.by-reference'])
    rpc('read', 'read', 'missing-application', 'getTask', [987654], actor='app')
    rpc('read', 'read', 'missing-user', 'getTask', [987654])
    rpc('read', 'read', 'all-open', 'getAllTasks', [Ref('p')],
        after=['rpc.create.create.minimal', 'rpc.create.create.full', 'rpc.create.create.positional',
               'rpc.create.create.unicode', 'rpc.create.create.second-in-cell', 'rpc.create.create.application-creator',
               'rpc.create.create.member-creator', 'rpc.create.dates.due-date-only', 'rpc.create.dates.due-user-format',
               'rpc.create.dates.due-underscore'])
    rpc('read', 'read', 'all-closed-none', 'getAllTasks', [Ref('p'), 0])

    # -- updates --------------------------------------------------------------------------------------------
    fx('update', 'task', 'createTask', {'title': 'Editable task', 'project_id': Ref('p'), 'tags': ['old'],
                                        'date_due': '2026-04-30', 'owner_id': Ref('mona'), 'score': 1},
       save='t-edit')
    rpc('update', 'update', 'title-description', 'updateTask', {'id': Ref('t-edit'), 'title': 'Edited task',
                                                                'description': 'Edited description'})
    rpc('update', 'update', 'title-description-read', 'getTask', [Ref('t-edit')],
        after=['rpc.update.update.title-description'])
    rpc('update', 'update', 'color-score-priority', 'updateTask', {'id': Ref('t-edit'), 'color_id': 'purple',
                                                                   'score': 13, 'priority': 3})
    rpc('update', 'update', 'dates', 'updateTask', {'id': Ref('t-edit'), 'date_due': '2026-06-15 16:45',
                                                    'date_started': '2026-06-01'})
    rpc('update', 'update', 'reference-times', 'updateTask', {'id': Ref('t-edit'), 'reference': 'REF-EDIT',
                                                              'time_estimated': 6, 'time_spent': 2.5})
    rpc('update', 'update', 'category', 'updateTask', {'id': Ref('t-edit'), 'category_id': Ref('feature')})
    rpc('update', 'update', 'fields-read', 'getTask', [Ref('t-edit')],
        after=['rpc.update.update.color-score-priority', 'rpc.update.update.dates',
               'rpc.update.update.reference-times', 'rpc.update.update.category',
               'rpc.update.update.title-description'])
    rpc('update', 'update', 'tags', 'updateTask', {'id': Ref('t-edit'), 'tags': ['new', 'shiny']})
    rpc('update', 'update', 'tags-read', 'getTaskTags', [Ref('t-edit')], after=['rpc.update.update.tags'])
    rpc('update', 'update', 'tags-project', 'getTagsByProject', [Ref('p')], after=['rpc.update.update.tags'])
    rpc('update', 'update', 'clear-tags', 'updateTask', {'id': Ref('t-edit'), 'tags': []},
        after=['rpc.update.update.tags'])
    rpc('update', 'update', 'clear-tags-read', 'getTaskTags', [Ref('t-edit')], after=['rpc.update.update.clear-tags'],
        requires=['rpc.update.update.tags-read'])
    rpc('update', 'update', 'unassign', 'updateTask', {'id': Ref('t-edit'), 'owner_id': 0})
    rpc('update', 'update', 'clear-due', 'updateTask', {'id': Ref('t-edit'), 'date_due': ''})
    rpc('update', 'update', 'cleared-read', 'getTask', [Ref('t-edit')],
        after=['rpc.update.update.unassign', 'rpc.update.update.clear-due', 'rpc.update.update.fields-read'])
    rpc('update', 'update', 'assign-member', 'updateTask', {'id': Ref('t-edit'), 'owner_id': Ref('mona')},
        after=['rpc.update.update.unassign'])
    rpc('update', 'update', 'positional', 'updateTask', [Ref('t-edit'), 'Positional edit', 'orange'])
    rpc('update', 'update', 'positional-read', 'getTask', [Ref('t-edit')],
        after=['rpc.update.update.positional', 'rpc.update.update.assign-member', 'rpc.update.update.cleared-read'])
    rpc('update', 'validation', 'owner-not-member', 'updateTask', {'id': Ref('t-edit'), 'owner_id': Ref('otto')})
    rpc('update', 'validation', 'invalid-color', 'updateTask', {'id': Ref('t-edit'), 'color_id': 'neon'})
    rpc('update', 'validation', 'bad-due-date', 'updateTask', {'id': Ref('t-edit'), 'date_due': '2026/99/99'})
    rpc('update', 'validation', 'start-after-due', 'updateTask', {'id': Ref('t-edit'), 'date_due': '2026-05-01',
                                                                  'date_started': '2026-06-01'})
    rpc('update', 'validation', 'score-not-integer', 'updateTask', {'id': Ref('t-edit'), 'score': 'x'})
    rpc('update', 'validation', 'unchanged-after-refusals', 'getTask', [Ref('t-edit')],
        after=['rpc.update.update.positional-read'])
    rpc('update', 'validation', 'missing-task', 'updateTask', {'id': 987654, 'title': 'Ghost'}, actor='app')
    rpc('update', 'validation', 'only-id', 'updateTask', {'id': Ref('t-edit')})

    # -- status ---------------------------------------------------------------------------------------------
    fx('status', 'task', 'createTask', {'title': 'Closable task', 'project_id': Ref('p')}, save='t-close')
    fx('status', 'subtask', 'createSubtask', {'task_id': Ref('t-close'), 'title': 'Open subtask'}, save='st-close')
    rpc('status', 'status', 'close', 'closeTask', [Ref('t-close')])
    rpc('status', 'status', 'closed-read', 'getTask', [Ref('t-close')], after=['rpc.status.status.close'])
    rpc('status', 'status', 'subtask-closed', 'getSubtask', [Ref('st-close')], after=['rpc.status.status.close'])
    rpc('status', 'status', 'closed-list', 'getAllTasks', [Ref('p'), 0], after=['rpc.status.status.close'])
    rpc('status', 'status', 'close-again', 'closeTask', [Ref('t-close')], after=['rpc.status.status.close'])
    rpc('status', 'status', 'open', 'openTask', [Ref('t-close')], after=['rpc.status.status.close'])
    rpc('status', 'status', 'opened-read', 'getTask', [Ref('t-close')], after=['rpc.status.status.open'])
    rpc('status', 'status', 'open-again', 'openTask', [Ref('t-close')], after=['rpc.status.status.open'])
    rpc('status', 'status', 'close-missing', 'closeTask', [987654], actor='app')
    rpc('status', 'status', 'open-missing', 'openTask', [987654], actor='app')

    # -- positions inside a cell and moves -------------------------------------------------------------------
    fx('move', 'project', 'createProject', {'name': 'Move project'}, save='mp')
    fx('move', 'columns', 'getColumns', [Ref('mp')], save='mcols')
    fx('move', 'lanes', 'getAllSwimlanes', [Ref('mp')], save='mlanes')
    fx('move', 'lane', 'addSwimlane', [Ref('mp'), 'Side lane'], save='mside')
    for n in range(1, 5):
        fx('move', f'task-{n}', 'createTask', {'title': f'Card {n}', 'project_id': Ref('mp')}, save=f'm{n}')

    def cell(c, r):
        tasks = c.call('getAllTasks', [c.state['mp'], 1])
        return {'http': r.status, 'result': r.body.get('result') if isinstance(r.body, dict) else None,
                'cells': sorted([t['title'], c.norm.ident('column', t['column_id']),
                                 c.norm.ident('swimlane', t['swimlane_id']), t['position']] for t in tasks)}

    def card(key):
        """A refused or no-op move: its answer and the cell of the card it targeted."""
        def project(c, r):
            task = c.call('getTask', [c.state[key]])
            return {'http': r.status, 'result': r.body.get('result') if isinstance(r.body, dict) else None,
                    'card': [task['title'], c.norm.ident('column', task['column_id']),
                             c.norm.ident('swimlane', task['swimlane_id']), task['position']]}
        return project
    rpc('move', 'position', 'to-top', 'moveTaskPosition', [Ref('mp'), Ref('m4'), Ref('mcols', 0, 'id'), 1,
                                                           Ref('mlanes', 0, 'id')], project=cell)
    rpc('move', 'position', 'to-middle', 'moveTaskPosition', [Ref('mp'), Ref('m1'), Ref('mcols', 0, 'id'), 3,
                                                              Ref('mlanes', 0, 'id')], project=cell,
        after=['rpc.move.position.to-top'])
    rpc('move', 'position', 'beyond-end', 'moveTaskPosition', [Ref('mp'), Ref('m4'), Ref('mcols', 0, 'id'), 50,
                                                                Ref('mlanes', 0, 'id')], project=cell,
        after=['rpc.move.position.to-middle'])
    rpc('move', 'position', 'other-column', 'moveTaskPosition', [Ref('mp'), Ref('m2'), Ref('mcols', 2, 'id'), 1,
                                                                 Ref('mlanes', 0, 'id')], project=cell,
        after=['rpc.move.position.beyond-end'])
    rpc('move', 'position', 'other-column-read', 'getTask', [Ref('m2')], after=['rpc.move.position.other-column'])
    rpc('move', 'position', 'other-swimlane', 'moveTaskPosition', [Ref('mp'), Ref('m3'), Ref('mcols', 2, 'id'), 1,
                                                                   Ref('mside')], project=cell,
        after=['rpc.move.position.other-column'])
    rpc('move', 'position', 'swimlane-zero-keeps', 'moveTaskPosition', [Ref('mp'), Ref('m3'), Ref('mcols', 3, 'id'),
                                                                        1, 0], project=cell,
        after=['rpc.move.position.other-swimlane'])
    rpc('move', 'position', 'position-zero', 'moveTaskPosition', [Ref('mp'), Ref('m1'), Ref('mcols', 0, 'id'), 0,
                                                                  Ref('mlanes', 0, 'id')], project=card('m1'),
        after=['rpc.move.position.swimlane-zero-keeps'])
    rpc('move', 'position', 'wrong-project', 'moveTaskPosition', [Ref('p'), Ref('m4'), Ref('mcols', 1, 'id'), 1,
                                                                  Ref('mlanes', 0, 'id')], project=card('m4'),
        after=['rpc.move.position.swimlane-zero-keeps'])
    rpc('move', 'position', 'same-place', 'moveTaskPosition', [Ref('mp'), Ref('m2'), Ref('mcols', 2, 'id'), 1,
                                                               Ref('mlanes', 0, 'id')], project=card('m2'),
        after=['rpc.move.position.swimlane-zero-keeps'])
    fx('move', 'closed', 'createTask', {'title': 'Closed card', 'project_id': Ref('mp')}, save='m-closed')
    fx('move', 'close', 'closeTask', [Ref('m-closed')])
    rpc('move', 'position', 'closed-task', 'moveTaskPosition', [Ref('mp'), Ref('m-closed'), Ref('mcols', 3, 'id'), 1,
                                                                Ref('mlanes', 0, 'id')])
    rpc('move', 'position', 'closed-task-read', 'getTask', [Ref('m-closed')], after=['rpc.move.position.closed-task'])

    # -- moving and duplicating to another project -----------------------------------------------------------
    fx('project', 'traveller', 'createTask', {
        'title': 'Traveller', 'project_id': Ref('p'), 'column_id': Ref('cols', 2, 'id'), 'swimlane_id': Ref('hotfix'),
        'category_id': Ref('feature'), 'owner_id': Ref('mona'), 'tags': ['travel'], 'description': 'Goes away',
        'score': 5, 'priority': 1, 'date_due': '2026-05-05', 'reference': 'TRAVEL-1', 'time_estimated': 3},
       save='t-travel')
    fx('project', 'traveller-subtask', 'createSubtask', {'task_id': Ref('t-travel'), 'title': 'Packed bag',
                                                         'user_id': Ref('mona')})
    fx('project', 'traveller-link', 'createExternalTaskLink', {'task_id': Ref('t-travel'),
                                                               'url': 'https://example.org/map',
                                                               'dependency': 'related'})
    fx('project', 'copy-source', 'createTask', {
        'title': 'Original', 'project_id': Ref('p'), 'column_id': Ref('cols', 1, 'id'), 'swimlane_id': Ref('hotfix'),
        'category_id': Ref('feature'), 'owner_id': Ref('mona'), 'tags': ['copy'], 'description': 'Copied',
        'score': 2, 'date_due': '2026-05-06', 'reference': 'COPY-1', 'time_estimated': 2, 'color_id': 'teal'},
       save='t-orig')
    fx('project', 'copy-subtask', 'createSubtask', {'task_id': Ref('t-orig'), 'title': 'Copied subtask',
                                                    'user_id': Ref('mona'), 'time_estimated': 1})
    rpc('project', 'move', 'to-other-project', 'moveTaskToProject', [Ref('t-travel'), Ref('p2')])
    rpc('project', 'move', 'moved-read', 'getTask', [Ref('t-travel')], after=['rpc.project.move.to-other-project'])
    rpc('project', 'move', 'moved-tags', 'getTaskTags', [Ref('t-travel')], after=['rpc.project.move.to-other-project'])
    rpc('project', 'move', 'moved-subtasks', 'getAllSubtasks', [Ref('t-travel')],
        after=['rpc.project.move.to-other-project'])
    rpc('project', 'move', 'back-with-targets', 'moveTaskToProject', {
        'task_id': Ref('t-travel'), 'project_id': Ref('p'), 'swimlane_id': Ref('lanes', 0, 'id'),
        'column_id': Ref('cols', 3, 'id'), 'category_id': 0, 'owner_id': 0},
        after=['rpc.project.move.moved-read'])
    rpc('project', 'move', 'back-read', 'getTask', [Ref('t-travel')], after=['rpc.project.move.back-with-targets'])
    rpc('project', 'duplicate', 'same-project', 'duplicateTaskToProject', [Ref('t-orig'), Ref('p')], save='t-copy1')
    rpc('project', 'duplicate', 'same-project-read', 'getTask', [Ref('t-copy1')])
    rpc('project', 'duplicate', 'same-project-subtasks', 'getAllSubtasks', [Ref('t-copy1')])
    rpc('project', 'duplicate', 'same-project-links', 'getAllTaskLinks', [Ref('t-copy1')])
    rpc('project', 'duplicate', 'other-project', 'duplicateTaskToProject', [Ref('t-orig'), Ref('p2')], save='t-copy2')
    rpc('project', 'duplicate', 'other-project-read', 'getTask', [Ref('t-copy2')])
    rpc('project', 'duplicate', 'other-project-tags', 'getTaskTags', [Ref('t-copy2')])
    rpc('project', 'duplicate', 'with-targets', 'duplicateTaskToProject', {
        'task_id': Ref('t-orig'), 'project_id': Ref('p2'), 'column_id': Ref('cols2', 2, 'id'), 'owner_id': 0},
        save='t-copy3')
    rpc('project', 'duplicate', 'with-targets-read', 'getTask', [Ref('t-copy3')])
    rpc('project', 'duplicate', 'source-unchanged', 'getTask', [Ref('t-orig')],
        after=['rpc.project.duplicate.with-targets', 'rpc.project.duplicate.other-project',
               'rpc.project.duplicate.same-project'])

    # -- removal --------------------------------------------------------------------------------------------
    fx('remove', 'task', 'createTask', {'title': 'Doomed task', 'project_id': Ref('p')}, save='t-doomed')
    fx('remove', 'comment', 'createComment', {'task_id': Ref('t-doomed'), 'user_id': 1, 'content': 'Doomed comment'},
       actor='app', save='c-doomed')
    rpc('remove', 'remove', 'remove', 'removeTask', [Ref('t-doomed')])
    rpc('remove', 'remove', 'removed-read', 'getTask', [Ref('t-doomed')], actor='app', after=['rpc.remove.remove.remove'],
        requires=['rpc.create.create.minimal-read'])
    rpc('remove', 'remove', 'comment-removed', 'getComment', [Ref('c-doomed')], actor='app',
        after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'remove-again', 'removeTask', [Ref('t-doomed')], actor='app',
        after=['rpc.remove.remove.remove'])

    # -- overdue --------------------------------------------------------------------------------------------
    fx('overdue', 'project', 'createProject', {'name': 'Late project'}, save='lp')
    fx('overdue', 'member', 'addProjectUser', [Ref('lp'), Ref('mona'), 'project-member'])
    fx('overdue', 'late-1', 'createTask', {'title': 'Late by days', 'project_id': Ref('lp'),
                                           'date_due': '2026-04-01', 'owner_id': Ref('mona')})
    fx('overdue', 'late-2', 'createTask', {'title': 'Late by hours', 'project_id': Ref('lp'),
                                           'date_due': '2026-04-14 06:00'})
    fx('overdue', 'future', 'createTask', {'title': 'Due later', 'project_id': Ref('lp'), 'date_due': '2026-04-30'})
    fx('overdue', 'no-due', 'createTask', {'title': 'Never due', 'project_id': Ref('lp')})
    fx('overdue', 'late-closed', 'createTask', {'title': 'Late but closed', 'project_id': Ref('lp'),
                                                'date_due': '2026-03-01'}, save='late-closed')
    fx('overdue', 'close', 'closeTask', [Ref('late-closed')])

    def overdue(c, r):
        observation = {'http': r.status}
        if r.has_result:
            observation['tasks'] = {'@unordered': c.norm.clean(r.result, 'task')}
        else:
            observation['error'] = (r.error or {}).get('code')
        return observation
    rpc('overdue', 'overdue', 'by-project', 'getOverdueTasksByProject', [Ref('lp')], project=overdue)
    def overdue_outside_checks(c, r):
        observation = overdue(c, r)
        if r.has_result and isinstance(r.result, list):
            kept = [t for t in r.result if str(t.get('project_id')) != str(c.state['vp'])]
            observation['tasks'] = {'@unordered': c.norm.clean(kept, 'task')}
        return observation
    rpc('overdue', 'overdue', 'all', 'getOverdueTasks', project=overdue_outside_checks,
        describe='getOverdueTasks as admin (the tasks outside the checks project)')
    rpc('overdue', 'overdue', 'mine', 'getMyOverdueTasks', actor='mona', project=overdue)
    rpc('overdue', 'overdue', 'empty-project', 'getOverdueTasksByProject', [Ref('mp')], project=overdue,
        requires=['rpc.overdue.overdue.by-project'])

    # -- recurring tasks ------------------------------------------------------------------------------------
    fx('recurrence', 'project', 'createProject', {'name': 'Recurring project'}, save='rp')
    fx('recurrence', 'columns', 'getColumns', [Ref('rp')], save='rcols')
    fx('recurrence', 'lanes', 'getAllSwimlanes', [Ref('rp')], save='rlanes')
    rpc('recurrence', 'recurrence', 'on-close', 'createTask', {
        'title': 'Weekly report', 'project_id': Ref('rp'), 'date_due': '2026-04-17 09:00', 'recurrence_status': 1,
        'recurrence_trigger': 2, 'recurrence_factor': 7, 'recurrence_timeframe': 0, 'recurrence_basedate': 0,
        'column_id': Ref('rcols', 1, 'id'), 'tags': ['weekly']}, save='r1')
    rpc('recurrence', 'recurrence', 'on-close-read', 'getTask', [Ref('r1')])
    rpc('recurrence', 'recurrence', 'close-it', 'closeTask', [Ref('r1')])

    def series(c, r):
        tasks = c.call('getAllTasks', [c.state['rp'], 1]) + c.call('getAllTasks', [c.state['rp'], 0])
        return {'http': r.status, 'tasks': {'@unordered': c.norm.clean(sorted(tasks, key=lambda t: t['id']), 'task')}}
    rpc('recurrence', 'recurrence', 'after-close', 'getTask', [Ref('r1')], project=series,
        after=['rpc.recurrence.recurrence.close-it'])
    rpc('recurrence', 'recurrence', 'monthly-last-column', 'createTask', {
        'title': 'Monthly invoice', 'project_id': Ref('rp'), 'date_due': '2026-01-31', 'recurrence_status': 1,
        'recurrence_trigger': 1, 'recurrence_factor': 1, 'recurrence_timeframe': 1, 'recurrence_basedate': 0},
        save='r2')
    rpc('recurrence', 'recurrence', 'move-to-last', 'moveTaskPosition', [Ref('rp'), Ref('r2'), Ref('rcols', 3, 'id'),
                                                                         1, Ref('rlanes', 0, 'id')])
    rpc('recurrence', 'recurrence', 'after-last-column', 'getTask', [Ref('r2')], project=series,
        after=['rpc.recurrence.recurrence.move-to-last', 'rpc.recurrence.recurrence.after-close'])
    rpc('recurrence', 'recurrence', 'yearly-first-column', 'createTask', {
        'title': 'Yearly audit', 'project_id': Ref('rp'), 'date_due': '2026-02-28', 'recurrence_status': 1,
        'recurrence_trigger': 0, 'recurrence_factor': -1, 'recurrence_timeframe': 2, 'recurrence_basedate': 0},
        save='r3')
    rpc('recurrence', 'recurrence', 'move-from-first', 'moveTaskPosition', [Ref('rp'), Ref('r3'),
                                                                            Ref('rcols', 2, 'id'), 1,
                                                                            Ref('rlanes', 0, 'id')])
    rpc('recurrence', 'recurrence', 'after-first-column', 'getTask', [Ref('r3')], project=series,
        after=['rpc.recurrence.recurrence.move-from-first', 'rpc.recurrence.recurrence.after-last-column'])
    rpc('recurrence', 'recurrence', 'not-recurring', 'createTask', {'title': 'One off', 'project_id': Ref('rp'),
                                                                    'date_due': '2026-04-20'}, save='r4')
    rpc('recurrence', 'recurrence', 'close-not-recurring', 'closeTask', [Ref('r4')])
    rpc('recurrence', 'recurrence', 'after-not-recurring', 'getTask', [Ref('r4')], project=series,
        after=['rpc.recurrence.recurrence.close-not-recurring', 'rpc.recurrence.recurrence.after-first-column'])
    rpc('recurrence', 'recurrence', 'update-to-recurring', 'updateTask', {
        'id': Ref('r4'), 'recurrence_status': 1, 'recurrence_trigger': 2, 'recurrence_factor': 2,
        'recurrence_timeframe': 0, 'recurrence_basedate': 0}, after=['rpc.recurrence.recurrence.close-not-recurring'])
    rpc('recurrence', 'recurrence', 'reopen-and-close', 'closeTask', [Ref('r4')],
        prepare=lambda c: c.call('openTask', [c.state['r4']]), after=['rpc.recurrence.recurrence.update-to-recurring'])
    rpc('recurrence', 'recurrence', 'after-update', 'getTask', [Ref('r4')], project=series,
        after=['rpc.recurrence.recurrence.reopen-and-close'])
