"""The task search language through searchTasks: every documented attribute, operators, relative dates, multiple
values, quoting and combinations. Results are compared as sets of task titles (the language defines no order)."""
from harness import Ref

PASSWORD = 'Search-Pass-2026'
TASKS = [
    # title, extra fields
    ('Alpha login bug', {'color_id': 'red', 'owner': 'sam', 'category': 'bug', 'date_due': '2026-04-13 10:00',
                         'score': 8, 'priority': 2, 'reference': 'TICKET-1234', 'tags': ['urgent', 'backend'],
                         'description': 'The needle is in this description'}),
    ('Beta payment form', {'color_id': 'blue', 'owner': 'lee', 'category': 'feature', 'date_due': '2026-04-14 18:00',
                           'score': 3, 'priority': 1, 'reference': 'TICKET-77', 'tags': ['frontend'],
                           'column': 2}),
    ('Gamma report export', {'color_id': 'deep_orange', 'owner': 'admin', 'date_due': '2026-04-15 09:00', 'score': 5,
                             'priority': 0, 'reference': 'SUPPORT-9', 'swimlane': 'lane', 'column': 1}),
    ('Delta dashboard widgets', {'color_id': 'blue', 'date_due': '2026-04-20 12:00', 'score': 1, 'tags': ['frontend'],
                                 'date_started': '2026-04-10 09:00', 'column': 3}),
    ('Epsilon cleanup', {'category': 'bug', 'date_started': '2026-04-16 09:00', 'creator': 'sam'}),
    ('Zeta archived item', {'owner': 'sam', 'date_due': '2026-04-01 12:00', 'closed': True}),
    ('Eta beta testing', {'color_id': 'green', 'owner': 'lee', 'description': 'Contains the word alpha only here'}),
]


def titles(c, r):
    observation = {'http': r.status}
    if r.has_result and isinstance(r.result, list):
        observation['titles'] = {'@unordered': [t.get('title') for t in r.result if isinstance(t, dict)]}
    else:
        observation['result'] = c.norm.clean(r.body.get('result') if isinstance(r.body, dict) else None)
        if r.error:
            observation['error'] = r.error.get('code')
    return observation


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'sam', 'createUser', {'username': 'sam', 'password': PASSWORD, 'name': 'Sam Search'}, save='sam',
       password=PASSWORD)
    fx('base', 'lee', 'createUser', {'username': 'lee', 'password': PASSWORD, 'name': 'Lee Finder'}, save='lee',
       password=PASSWORD)
    fx('base', 'admin', 'getUserByName', ['admin'], save='admin')
    fx('base', 'project', 'createProject', {'name': 'Search project'}, save='p')
    fx('base', 'other-project', 'createProject', {'name': 'Elsewhere'}, save='p2')
    fx('base', 'other-task', 'createTask', {'title': 'Alpha elsewhere', 'project_id': Ref('p2')})
    for user in ('sam', 'lee'):
        fx('base', 'member-' + user, 'addProjectUser', [Ref('p'), Ref(user), 'project-member'])
    fx('base', 'columns', 'getColumns', [Ref('p')], save='cols')
    fx('base', 'lane', 'addSwimlane', [Ref('p'), 'Version 42'], save='lane')
    fx('base', 'bug', 'createCategory', [Ref('p'), 'Bug'], save='bug')
    fx('base', 'feature', 'createCategory', [Ref('p'), 'Feature Request'], save='feature')
    for i, (title, extra) in enumerate(TASKS):
        values = {'title': title, 'project_id': Ref('p')}
        for key in ('color_id', 'date_due', 'score', 'priority', 'reference', 'tags', 'description', 'date_started'):
            if key in extra:
                values[key] = extra[key]
        if 'owner' in extra:
            values['owner_id'] = Ref(extra['owner'], 'id') if extra['owner'] == 'admin' else Ref(extra['owner'])
        if 'category' in extra:
            values['category_id'] = Ref(extra['category'])
        if 'column' in extra:
            values['column_id'] = Ref('cols', extra['column'], 'id')
        if 'swimlane' in extra:
            values['swimlane_id'] = Ref(extra['swimlane'])
        actor = extra.get('creator', 'admin')
        fx('base', f'task-{i}', 'createTask', values, actor=actor, save=f't{i}')
        if extra.get('closed'):
            fx('base', f'close-{i}', 'closeTask', [Ref(f't{i}')])
    fx('base', 'subtask', 'createSubtask', {'task_id': Ref('t3'), 'title': 'Lee checks widgets', 'user_id': Ref('lee')})
    fx('base', 'subtask2', 'createSubtask', {'task_id': Ref('t2'), 'title': 'Sam exports', 'user_id': Ref('sam')})
    fx('base', 'link', 'createTaskLink', [Ref('t0'), Ref('t1'), 2])
    fx('base', 'link2', 'createTaskLink', [Ref('t2'), Ref('t4'), 1])
    fx('base', 'comment', 'createComment', {'task_id': Ref('t4'), 'user_id': Ref('admin', 'id'),
                                            'content': 'Remember the secret word'})

    def q(step, query, actor='admin'):
        rpc('search', 'query', step, 'searchTasks', [Ref('p'), query], actor, project=titles)

    q('everything-open', 'status:open')
    q('closed', 'status:closed')
    q('all-statuses', 'status:all')
    q('title-word', 'alpha')
    q('title-words', 'beta form')
    q('quoted-title', '"report export"')
    q('title-attribute', 'title:cleanup')
    q('unknown-word', 'nonexistent')
    q('empty-query', '')
    q('assignee-username', 'assignee:sam')
    q('assignee-full-name', 'assignee:"Lee Finder"')
    q('assignee-several', 'assignee:sam assignee:lee')
    q('assignee-nobody', 'assignee:nobody')
    q('assignee-me-admin', 'assignee:me')
    q('assignee-me-lee', 'assignee:me', actor='lee')
    q('creator-me-sam', 'creator:me', actor='sam')
    q('creator-username', 'creator:sam')
    q('subtask-assignee', 'subtask:assignee:lee')
    q('subtask-assignee-name', 'subtask:assignee:"Sam Search"')
    q('color-id', 'color:blue')
    q('color-name', 'color:"Deep Orange"')
    q('color-several', 'color:red color:green')
    q('due-today', 'due:today')
    q('due-tomorrow', 'due:tomorrow')
    q('due-yesterday', 'due:yesterday')
    q('due-exact', 'due:2026-04-20')
    q('due-after', 'due:>2026-04-15')
    q('due-before', 'due:<2026-04-15')
    q('due-from', 'due:>=2026-04-15')
    q('due-until', 'due:<=2026-04-14')
    q('due-relative', 'due:<"+3 days"')
    q('due-none', 'due:none')
    q('started-past', 'started:<=2026-04-14')
    q('started-future', 'started:>2026-04-14')
    q('created-today', 'created:today')
    q('created-before', 'created:<2026-01-01')
    q('created-range', 'createdRange:"2026-04-14..2026-04-15"')
    q('created-range-later', 'createdRange:"2026-05-01..2026-05-31"')
    q('updated-today', 'updated:today')
    q('modified-range', 'modifiedRange:"2026-04-14..2026-04-15"')
    q('updated-range', 'updatedRange:"2026-04-01..2026-04-30" status:closed')
    q('completed-today', 'completed:today')
    q('completed-range', 'completedRange:"2026-04-14..2026-04-15"')
    q('moved-range', 'movedRange:"2026-04-14..2026-04-15"')
    q('moved-range-combined', 'movedRange:"2026-04-14..2026-04-15" color:blue')
    q('description', 'description:needle')
    q('description-short', 'desc:"word alpha"')
    q('reference-exact', 'reference:TICKET-1234')
    q('reference-wildcard', 'ref:TICKET-*')
    q('reference-none', 'reference:none')
    q('category-name', 'category:"Feature Request"')
    q('category-several', 'category:Bug category:"Feature Request"')
    q('category-none', 'category:none')
    q('category-id', lambda c: 'category:' + str(c.state['bug']))
    q('project-name', 'project:"Search project"')
    q('project-other-name', 'project:Elsewhere')
    q('project-id', lambda c: 'project:' + str(c.state['p']))
    q('column-name', 'column:"Work in progress"')
    q('column-several', 'column:Backlog column:ready')
    q('swimlane', 'swimlane:"Version 42"')
    q('swimlane-default', 'swimlane:"Default swimlane"')
    q('link-blocks', 'link:blocks')
    q('link-blocked-by', 'link:"is blocked by"')
    q('link-several', 'link:blocks link:"relates to"')
    q('comment', 'comment:"secret word"')
    q('tag', 'tag:urgent')
    q('tag-several', 'tag:urgent tag:frontend')
    q('tag-quoted', 'tag:"frontend"')
    q('score-at-least', 'score:>=5')
    q('complexity-exact', 'complexity:8')
    q('score-below', 'score:<3')
    q('priority', 'priority:2')
    q('priority-range', 'priority:>0')
    q('task-id', lambda c: '#' + str(c.state['t2']))
    q('task-number', lambda c: str(c.state['t3']))
    q('combined-assignee-color', 'assignee:lee color:blue')
    q('combined-status-assignee', 'status:closed assignee:sam')
    q('combined-tag-due', 'tag:frontend due:>2026-04-15')
    q('combined-category-title', 'category:bug cleanup')
    rpc('search', 'scope', 'other-project', 'searchTasks', [Ref('p2'), 'alpha'], project=titles)
    rpc('search', 'scope', 'application', 'searchTasks', [Ref('p'), 'alpha'], actor='app', project=titles)
    rpc('search', 'scope', 'missing-project', 'searchTasks', [987654, 'alpha'], project=titles)
