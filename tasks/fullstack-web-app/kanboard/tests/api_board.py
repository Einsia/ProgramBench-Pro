"""The board of a project: columns, swimlanes, categories and the board view, through the JSON-RPC API.

Column creation, update, ordering and removal (with and without tasks), work-in-progress limits; swimlane creation,
renaming, ordering, disabling, enabling and removal; category creation with colours, renaming and removal (and what
happens to the tasks that use it); and the board structure with tasks in the right cells and their counters.

Edge creations and refused attempts happen in a project of their own (Board checks), so that accepting or refusing
one of them never shifts the positions and lists the ordinary cases observe.
"""
from harness import Ref


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'project', 'createProject', {'name': 'Board project'}, save='p')
    fx('base', 'columns', 'getColumns', [Ref('p')], save='cols')
    fx('base', 'checks', 'createProject', {'name': 'Board checks'}, save='bc')
    fx('base', 'checks-category', 'createCategory', [Ref('bc'), 'Bug'])

    # -- columns --------------------------------------------------------------------------------------------
    rpc('columns', 'columns', 'add', 'addColumn', [Ref('p'), 'Review'], save='c-review')
    rpc('columns', 'columns', 'add-full', 'addColumn', {'project_id': Ref('p'), 'title': 'Deploy', 'task_limit': 3,
                                                        'description': 'Ready to **ship**'}, save='c-deploy')
    rpc('columns', 'columns', 'add-unicode', 'addColumn', [Ref('p'), 'Validé ✓'], save='c-unicode')
    rpc('columns', 'columns', 'listed', 'getColumns', [Ref('p')],
        after=['rpc.columns.columns.add', 'rpc.columns.columns.add-full', 'rpc.columns.columns.add-unicode'])
    rpc('columns', 'columns', 'read', 'getColumn', [Ref('c-deploy')])
    rpc('columns', 'columns', 'read-missing', 'getColumn', [987654], actor='app', requires=['rpc.columns.columns.read'])
    rpc('columns', 'columns', 'add-limit-string', 'addColumn', [Ref('bc'), 'Limit text', 'seven'], save='c-text')
    rpc('columns', 'columns', 'add-limit-string-read', 'getColumn', [Ref('c-text')])
    rpc('columns', 'columns', 'add-empty-title', 'addColumn', [Ref('bc'), ''])
    rpc('columns', 'columns', 'add-missing-project', 'addColumn', [987654, 'Nowhere'], actor='app')
    rpc('columns', 'columns', 'update', 'updateColumn', [Ref('c-review'), 'Code review', 2, 'Two at a time'])
    rpc('columns', 'columns', 'update-read', 'getColumn', [Ref('c-review')], after=['rpc.columns.columns.update'])
    rpc('columns', 'columns', 'update-defaults', 'updateColumn', {'column_id': Ref('c-deploy'), 'title': 'Deploy now'})
    rpc('columns', 'columns', 'update-defaults-read', 'getColumn', [Ref('c-deploy')],
        after=['rpc.columns.columns.update-defaults'])
    rpc('columns', 'columns', 'update-missing', 'updateColumn', [987654, 'Ghost'], actor='app')
    rpc('columns', 'order', 'move-first', 'changeColumnPosition', [Ref('p'), Ref('c-review'), 1])
    rpc('columns', 'order', 'move-first-read', 'getColumns', [Ref('p')], after=['rpc.columns.order.move-first'])
    rpc('columns', 'order', 'move-last', 'changeColumnPosition', [Ref('p'), Ref('cols', 0, 'id'), 7],
        after=['rpc.columns.columns.add', 'rpc.columns.columns.add-full', 'rpc.columns.columns.add-unicode'])
    rpc('columns', 'order', 'move-middle', 'changeColumnPosition', [Ref('p'), Ref('c-unicode'), 3])
    rpc('columns', 'order', 'moved-read', 'getColumns', [Ref('p')],
        after=['rpc.columns.order.move-last', 'rpc.columns.order.move-middle'])
    rpc('columns', 'order', 'position-zero', 'changeColumnPosition', [Ref('p'), Ref('c-review'), 0])
    rpc('columns', 'order', 'position-beyond', 'changeColumnPosition', [Ref('p'), Ref('c-review'), 10])
    rpc('columns', 'order', 'other-project', 'changeColumnPosition', [Ref('p2'), Ref('c-review'), 1],
        prepare=lambda c: c.state.setdefault('p2', c.call('createProject', {'name': 'Board other'})))
    rpc('columns', 'order', 'unchanged-after-refusals', 'getColumns', [Ref('p')],
        after=['rpc.columns.order.moved-read'])
    fx('columns', 'busy-task', 'createTask', {'title': 'Sits in review', 'project_id': Ref('p'),
                                              'column_id': Ref('c-review')}, save='t-review')
    fx('columns', 'closed-task', 'createTask', {'title': 'Closed in deploy', 'project_id': Ref('p'),
                                                'column_id': Ref('c-deploy')}, save='t-deploy')
    fx('columns', 'close', 'closeTask', [Ref('t-deploy')])
    fx('columns', 'scratch', 'addColumn', [Ref('p'), 'Scratch'], save='c-empty')
    rpc('columns', 'remove', 'with-open-task', 'removeColumn', [Ref('c-review')])
    rpc('columns', 'remove', 'with-closed-task', 'removeColumn', [Ref('c-deploy')])
    rpc('columns', 'remove', 'empty-column', 'removeColumn', [Ref('c-empty')])
    rpc('columns', 'remove', 'removed-read', 'getColumn', [Ref('c-empty')], actor='app',
        after=['rpc.columns.remove.empty-column'], requires=['rpc.columns.columns.read'])
    rpc('columns', 'remove', 'remaining', 'getColumns', [Ref('p')],
        after=['rpc.columns.remove.empty-column', 'rpc.columns.order.moved-read'])
    rpc('columns', 'remove', 'remove-missing', 'removeColumn', [987654], actor='app')

    # -- swimlanes ------------------------------------------------------------------------------------------
    fx('swimlanes', 'project', 'createProject', {'name': 'Lanes project'}, save='lp')
    fx('swimlanes', 'default', 'getAllSwimlanes', [Ref('lp')], save='lanes')
    rpc('swimlanes', 'swimlanes', 'add', 'addSwimlane', [Ref('lp'), 'Express'], save='s-express')
    rpc('swimlanes', 'swimlanes', 'add-described', 'addSwimlane', {'project_id': Ref('lp'), 'name': 'Support',
                                                                   'description': 'Customer *issues*'},
        save='s-support')
    rpc('swimlanes', 'swimlanes', 'add-third', 'addSwimlane', [Ref('lp'), 'Research'], save='s-research')
    rpc('swimlanes', 'swimlanes', 'add-duplicate', 'addSwimlane', [Ref('bc'), 'Default swimlane'])
    rpc('swimlanes', 'swimlanes', 'add-missing-project', 'addSwimlane', [987654, 'Nowhere'], actor='app')
    rpc('swimlanes', 'swimlanes', 'listed', 'getAllSwimlanes', [Ref('lp')],
        after=['rpc.swimlanes.swimlanes.add', 'rpc.swimlanes.swimlanes.add-described',
               'rpc.swimlanes.swimlanes.add-third'])
    rpc('swimlanes', 'swimlanes', 'by-id', 'getSwimlaneById', [Ref('s-support')])
    rpc('swimlanes', 'swimlanes', 'get', 'getSwimlane', [Ref('s-support')])
    rpc('swimlanes', 'swimlanes', 'by-name', 'getSwimlaneByName', [Ref('lp'), 'Research'])
    rpc('swimlanes', 'swimlanes', 'by-name-missing', 'getSwimlaneByName', [Ref('lp'), 'research'],
        requires=['rpc.swimlanes.swimlanes.by-name'])
    rpc('swimlanes', 'swimlanes', 'by-id-missing', 'getSwimlaneById', [987654], actor='app',
        requires=['rpc.swimlanes.swimlanes.by-id'])
    rpc('swimlanes', 'swimlanes', 'rename', 'updateSwimlane', [Ref('lp'), Ref('s-express'), 'Fast lane'])
    rpc('swimlanes', 'swimlanes', 'rename-read', 'getSwimlaneById', [Ref('s-express')],
        after=['rpc.swimlanes.swimlanes.rename'])
    rpc('swimlanes', 'swimlanes', 'describe', 'updateSwimlane', {'project_id': Ref('lp'),
                                                                 'swimlane_id': Ref('s-research'),
                                                                 'name': 'Research', 'description': 'Spikes'})
    rpc('swimlanes', 'swimlanes', 'describe-read', 'getSwimlaneByName', [Ref('lp'), 'Research'],
        after=['rpc.swimlanes.swimlanes.describe'])
    rpc('swimlanes', 'swimlanes', 'rename-default', 'updateSwimlane', [Ref('lp'), Ref('lanes', 0, 'id'), 'Main lane'])
    rpc('swimlanes', 'swimlanes', 'rename-empty', 'updateSwimlane', [Ref('lp'), Ref('s-express'), ''])
    rpc('swimlanes', 'swimlanes', 'rename-duplicate', 'updateSwimlane', [Ref('lp'), Ref('s-support'), 'Research'])
    rpc('swimlanes', 'swimlanes', 'rename-other-project', 'updateSwimlane', [987654, Ref('s-support'), 'Moved'],
        actor='app')
    rpc('swimlanes', 'swimlanes', 'unchanged-after-refusals', 'getAllSwimlanes', [Ref('lp')],
        after=['rpc.swimlanes.swimlanes.rename-default', 'rpc.swimlanes.swimlanes.rename',
               'rpc.swimlanes.swimlanes.describe'])
    rpc('swimlanes', 'order', 'move-first', 'changeSwimlanePosition', [Ref('lp'), Ref('s-research'), 1])
    rpc('swimlanes', 'order', 'move-first-read', 'getAllSwimlanes', [Ref('lp')],
        after=['rpc.swimlanes.order.move-first'])
    rpc('swimlanes', 'order', 'position-zero', 'changeSwimlanePosition', [Ref('lp'), Ref('s-research'), 0])
    rpc('swimlanes', 'order', 'position-beyond', 'changeSwimlanePosition', [Ref('lp'), Ref('s-research'), 9])
    rpc('swimlanes', 'status', 'disable', 'disableSwimlane', [Ref('lp'), Ref('s-support')])
    rpc('swimlanes', 'status', 'disabled-all', 'getAllSwimlanes', [Ref('lp')],
        after=['rpc.swimlanes.status.disable', 'rpc.swimlanes.order.move-first'])
    rpc('swimlanes', 'status', 'disabled-active', 'getActiveSwimlanes', [Ref('lp')],
        after=['rpc.swimlanes.status.disable', 'rpc.swimlanes.order.move-first'])
    rpc('swimlanes', 'status', 'enable', 'enableSwimlane', [Ref('lp'), Ref('s-support')],
        after=['rpc.swimlanes.status.disable'])
    rpc('swimlanes', 'status', 'enabled-active', 'getActiveSwimlanes', [Ref('lp')],
        after=['rpc.swimlanes.status.enable'])
    rpc('swimlanes', 'status', 'disable-wrong-project', 'disableSwimlane', [987654, Ref('s-support')], actor='app')
    rpc('swimlanes', 'status', 'disable-missing', 'disableSwimlane', [Ref('lp'), 987654])
    fx('swimlanes', 'task', 'createTask', {'title': 'In express', 'project_id': Ref('lp'),
                                           'swimlane_id': Ref('s-express')}, save='t-express')
    rpc('swimlanes', 'remove', 'with-task', 'removeSwimlane', [Ref('lp'), Ref('s-express')])
    rpc('swimlanes', 'remove', 'empty', 'removeSwimlane', [Ref('lp'), Ref('s-research')])
    rpc('swimlanes', 'remove', 'remaining', 'getAllSwimlanes', [Ref('lp')],
        after=['rpc.swimlanes.remove.empty', 'rpc.swimlanes.status.enable'])
    rpc('swimlanes', 'remove', 'wrong-project', 'removeSwimlane', [987654, Ref('s-support')], actor='app')
    rpc('swimlanes', 'remove', 'missing', 'removeSwimlane', [Ref('lp'), 987654])

    # -- categories -----------------------------------------------------------------------------------------
    fx('categories', 'project', 'createProject', {'name': 'Category project'}, save='cp')
    rpc('categories', 'categories', 'none', 'getAllCategories', [Ref('cp')])
    rpc('categories', 'categories', 'create', 'createCategory', [Ref('cp'), 'Bug'], save='k-bug')
    rpc('categories', 'categories', 'create-colored', 'createCategory', {'project_id': Ref('cp'), 'name': 'Feature',
                                                                         'color_id': 'green'}, save='k-feature')
    rpc('categories', 'categories', 'create-unicode', 'createCategory', [Ref('cp'), 'Amélioration 改进', 'purple'],
        save='k-unicode')
    rpc('categories', 'categories', 'listed-sorted', 'getAllCategories', [Ref('cp')],
        after=['rpc.categories.categories.create', 'rpc.categories.categories.create-colored',
               'rpc.categories.categories.create-unicode'])
    rpc('categories', 'categories', 'read', 'getCategory', [Ref('k-feature')])
    rpc('categories', 'categories', 'read-missing', 'getCategory', [987654], actor='app',
        requires=['rpc.categories.categories.read'])
    rpc('categories', 'validation', 'duplicate-name', 'createCategory', [Ref('bc'), 'Bug'])
    rpc('categories', 'validation', 'empty-name', 'createCategory', [Ref('bc'), ''])
    rpc('categories', 'validation', 'invalid-color', 'createCategory', [Ref('bc'), 'Chore', 'chartreuse'])
    rpc('categories', 'validation', 'name-too-long', 'createCategory', [Ref('bc'), 'n' * 192])
    rpc('categories', 'validation', 'missing-project', 'createCategory', [987654, 'Lost'], actor='app')
    rpc('categories', 'update', 'rename', 'updateCategory', [Ref('k-bug'), 'Defect'])
    rpc('categories', 'update', 'recolor', 'updateCategory', {'id': Ref('k-feature'), 'name': 'Feature',
                                                              'color_id': 'red'})
    rpc('categories', 'update', 'updated-read', 'getAllCategories', [Ref('cp')],
        after=['rpc.categories.update.rename', 'rpc.categories.update.recolor'])
    rpc('categories', 'update', 'rename-duplicate', 'updateCategory', [Ref('k-bug'), 'Feature'])
    rpc('categories', 'update', 'invalid-color', 'updateCategory', [Ref('k-bug'), 'Defect', 'chartreuse'])
    rpc('categories', 'update', 'empty-name', 'updateCategory', [Ref('k-bug'), ''])
    rpc('categories', 'update', 'unchanged-after-refusals', 'getCategory', [Ref('k-bug')],
        after=['rpc.categories.update.rename'])
    fx('categories', 'task', 'createTask', {'title': 'Categorised', 'project_id': Ref('cp'),
                                            'category_id': Ref('k-unicode')}, save='t-cat')
    rpc('categories', 'remove', 'remove-used', 'removeCategory', [Ref('k-unicode')])
    rpc('categories', 'remove', 'task-uncategorised', 'getTask', [Ref('t-cat')],
        after=['rpc.categories.remove.remove-used'])
    rpc('categories', 'remove', 'removed-read', 'getCategory', [Ref('k-unicode')], actor='app',
        after=['rpc.categories.remove.remove-used'], requires=['rpc.categories.categories.read'])
    rpc('categories', 'remove', 'remaining', 'getAllCategories', [Ref('cp')],
        after=['rpc.categories.remove.remove-used', 'rpc.categories.update.updated-read'])
    rpc('categories', 'remove', 'remove-missing', 'removeCategory', [987654], actor='app')

    # -- the board ------------------------------------------------------------------------------------------
    fx('board', 'project', 'createProject', {'name': 'Kanban'}, save='bp')
    fx('board', 'columns', 'getColumns', [Ref('bp')], save='bcols')
    fx('board', 'lanes', 'getAllSwimlanes', [Ref('bp')], save='blanes')
    fx('board', 'lane', 'addSwimlane', [Ref('bp'), 'Urgent'], save='b-urgent')
    fx('board', 'lane-off', 'addSwimlane', [Ref('bp'), 'Parked'], save='b-parked')
    fx('board', 'lane-off-disable', 'disableSwimlane', [Ref('bp'), Ref('b-parked')])
    fx('board', 'limit', 'updateColumn', [Ref('bcols', 1, 'id'), 'Ready', 1])
    fx('board', 'task-1', 'createTask', {'title': 'First in backlog', 'project_id': Ref('bp'), 'score': 3,
                                         'color_id': 'blue'}, save='b1')
    fx('board', 'task-2', 'createTask', {'title': 'Second in backlog', 'project_id': Ref('bp'), 'score': 5},
       save='b2')
    fx('board', 'task-3', 'createTask', {'title': 'Ready one', 'project_id': Ref('bp'),
                                         'column_id': Ref('bcols', 1, 'id')}, save='b3')
    fx('board', 'task-4', 'createTask', {'title': 'Ready two', 'project_id': Ref('bp'),
                                         'column_id': Ref('bcols', 1, 'id'), 'swimlane_id': Ref('b-urgent')},
       save='b4')
    fx('board', 'task-5', 'createTask', {'title': 'Urgent done', 'project_id': Ref('bp'),
                                         'column_id': Ref('bcols', 3, 'id'), 'swimlane_id': Ref('b-urgent')},
       save='b5')
    fx('board', 'task-6', 'createTask', {'title': 'Closed one', 'project_id': Ref('bp')}, save='b6')
    fx('board', 'close-6', 'closeTask', [Ref('b6')])
    fx('board', 'subtask', 'createSubtask', {'task_id': Ref('b1'), 'title': 'Board subtask'})
    fx('board', 'comment', 'createComment', {'task_id': Ref('b1'), 'user_id': 1, 'content': 'Board comment'},
       actor='app')
    rpc('board', 'board', 'structure', 'getBoard', [Ref('bp')])
    rpc('board', 'board', 'empty-project', 'getBoard', [Ref('cp')], after=['rpc.categories.remove.remove-used'])
    rpc('board', 'board', 'missing-project', 'getBoard', [987654], actor='app')
    rpc('board', 'board', 'after-move', 'getBoard', [Ref('bp')],
        prepare=lambda c: c.call('moveTaskPosition', [c.state['bp'], c.state['b2'], c.state['bcols'][2]['id'], 1,
                                                       c.state['blanes'][0]['id']]),
        after=['rpc.board.board.structure'])
    rpc('board', 'board', 'hidden-default-lane', 'getBoard', [Ref('bp')],
        prepare=lambda c: c.call('disableSwimlane', [c.state['bp'], c.state['blanes'][0]['id']]),
        after=['rpc.board.board.after-move'])
