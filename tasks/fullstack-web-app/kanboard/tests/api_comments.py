"""Comments through the JSON-RPC API: creation with references and visibility levels, who may comment as whom,
ordering, visibility filtering by application role, edits and removal by the author only.

Refused creations, edits and removals act on a task of their own (Comment checks) with its own comments, so that
accepting or refusing one of them never changes the comments the ordinary cases observe."""
from harness import Ref

PASSWORD = 'Comments-Pass-2026'


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'admin', 'getUserByName', ['admin'], save='admin')
    fx('base', 'user', 'createUser', {'username': 'cora', 'password': PASSWORD, 'name': 'Cora Commenter'},
       save='cora', password=PASSWORD)
    fx('base', 'manager', 'createUser', {'username': 'mick', 'password': PASSWORD, 'name': 'Mick Manager',
                                         'role': 'app-manager'}, save='mick', password=PASSWORD)
    fx('base', 'project', 'createProject', {'name': 'Comment project'}, save='p')
    fx('base', 'member-user', 'addProjectUser', [Ref('p'), Ref('cora'), 'project-member'])
    fx('base', 'member-manager', 'addProjectUser', [Ref('p'), Ref('mick'), 'project-member'])
    fx('base', 'task', 'createTask', {'title': 'Discussed task', 'project_id': Ref('p')}, save='t')
    fx('base', 'task2', 'createTask', {'title': 'Quiet task', 'project_id': Ref('p')}, save='t2')
    fx('base', 'checks-task', 'createTask', {'title': 'Comment checks', 'project_id': Ref('p')}, save='tc')
    fx('base', 'checks-admin-note', 'createComment', {'task_id': Ref('tc'), 'user_id': Ref('admin', 'id'),
                                                      'content': 'Admin note'}, actor='app', save='cc-admin')
    fx('base', 'checks-cora-note', 'createComment', {'task_id': Ref('tc'), 'user_id': Ref('cora'),
                                                     'content': 'Cora note'}, actor='app', save='cc-cora')

    # -- creation -------------------------------------------------------------------------------------------
    rpc('create', 'create', 'own', 'createComment', {'task_id': Ref('t'), 'user_id': Ref('admin', 'id'),
                                                     'content': 'First comment'}, save='c1')
    rpc('create', 'create', 'own-read', 'getComment', [Ref('c1')])
    rpc('create', 'create', 'with-reference', 'createComment', {'task_id': Ref('t'), 'user_id': Ref('cora'),
                                                                'content': 'From the tracker',
                                                                'reference': 'TRACKER-9'}, actor='cora', save='c2')
    rpc('create', 'create', 'with-reference-read', 'getComment', [Ref('c2')], actor='cora')
    rpc('create', 'create', 'markdown', 'createComment', [Ref('t'), Ref('cora'), '**Bold** and `code`\n\n> quoted'],
        actor='cora', save='c3')
    rpc('create', 'create', 'for-someone-else', 'createComment', {'task_id': Ref('tc'), 'user_id': Ref('admin', 'id'),
                                                                  'content': 'Pretending'}, actor='cora')
    rpc('create', 'create', 'application-any-author', 'createComment', {'task_id': Ref('t'), 'user_id': Ref('cora'),
                                                                        'content': 'Imported comment'},
        actor='app', save='c4')
    rpc('create', 'create', 'application-no-author', 'createComment', {'task_id': Ref('t'), 'user_id': 0,
                                                                       'content': 'System note'}, actor='app',
        save='c5')
    rpc('create', 'create', 'empty-content', 'createComment', {'task_id': Ref('tc'), 'user_id': Ref('admin', 'id'),
                                                               'content': ''})
    rpc('create', 'create', 'missing-task', 'createComment', {'task_id': 987654, 'user_id': 1, 'content': 'Lost'},
        actor='app')
    rpc('create', 'create', 'all-in-order', 'getAllComments', [Ref('t')],
        after=['rpc.create.create.own', 'rpc.create.create.with-reference', 'rpc.create.create.markdown',
               'rpc.create.create.application-any-author', 'rpc.create.create.application-no-author'])
    rpc('create', 'create', 'none-on-other-task', 'getAllComments', [Ref('t2')],
        requires=['rpc.create.create.all-in-order'])
    rpc('create', 'create', 'missing-comment', 'getComment', [987654], actor='app',
        requires=['rpc.create.create.own-read'])

    # -- visibility -----------------------------------------------------------------------------------------
    rpc('visibility', 'create', 'admin-only', 'createComment', {'task_id': Ref('t2'), 'user_id': Ref('admin', 'id'),
                                                                'content': 'Administrators only',
                                                                'visibility': 'app-admin'}, save='v-admin')
    rpc('visibility', 'create', 'managers', 'createComment', {'task_id': Ref('t2'), 'user_id': Ref('mick'),
                                                              'content': 'Managers and up',
                                                              'visibility': 'app-manager'}, actor='mick',
        save='v-manager')
    rpc('visibility', 'create', 'everyone', 'createComment', {'task_id': Ref('t2'), 'user_id': Ref('cora'),
                                                              'content': 'Everyone', 'visibility': 'app-user'},
        actor='cora', save='v-user')
    rpc('visibility', 'create', 'user-raises', 'createComment', {'task_id': Ref('tc'), 'user_id': Ref('cora'),
                                                                 'content': 'Secret', 'visibility': 'app-manager'},
        actor='cora')
    rpc('visibility', 'create', 'manager-raises', 'createComment', {'task_id': Ref('tc'), 'user_id': Ref('mick'),
                                                                    'content': 'Top secret',
                                                                    'visibility': 'app-admin'}, actor='mick')
    rpc('visibility', 'create', 'invalid-level', 'createComment', {'task_id': Ref('tc'), 'user_id': 0,
                                                                   'content': 'Odd level', 'visibility': 'everyone'},
        actor='app')
    after = ['rpc.visibility.create.admin-only', 'rpc.visibility.create.managers', 'rpc.visibility.create.everyone']
    rpc('visibility', 'read', 'as-admin', 'getAllComments', [Ref('t2')], after=after)
    rpc('visibility', 'read', 'as-manager', 'getAllComments', [Ref('t2')], actor='mick', after=after)
    rpc('visibility', 'read', 'as-user', 'getAllComments', [Ref('t2')], actor='cora', after=after)
    rpc('visibility', 'read', 'as-application', 'getAllComments', [Ref('t2')], actor='app', after=after)
    rpc('visibility', 'read', 'single-hidden-from-user', 'getComment', [Ref('v-admin')], actor='cora',
        after=['rpc.visibility.create.admin-only'])

    # -- edits and removal ----------------------------------------------------------------------------------
    rpc('edit', 'edit', 'own', 'updateComment', {'id': Ref('c2'), 'content': 'From the tracker (edited)'},
        actor='cora')
    rpc('edit', 'edit', 'own-read', 'getComment', [Ref('c2')], actor='cora', after=['rpc.edit.edit.own'])
    rpc('edit', 'edit', 'positional', 'updateComment', [Ref('c1'), 'First comment, revised'])
    rpc('edit', 'edit', 'positional-read', 'getComment', [Ref('c1')], after=['rpc.edit.edit.positional'])
    rpc('edit', 'edit', 'others-comment', 'updateComment', {'id': Ref('cc-admin'), 'content': 'Hijacked'}, actor='cora')
    rpc('edit', 'edit', 'admin-edits-others', 'updateComment', {'id': Ref('cc-cora'), 'content': 'Admin edit'})
    rpc('edit', 'edit', 'application-edits-any', 'updateComment', {'id': Ref('c3'), 'content': 'Application edit'},
        actor='app')
    rpc('edit', 'edit', 'empty-content', 'updateComment', {'id': Ref('cc-cora'), 'content': ''}, actor='cora')
    rpc('edit', 'edit', 'missing-comment', 'updateComment', {'id': 987654, 'content': 'Ghost'}, actor='app')
    rpc('edit', 'edit', 'after-edits', 'getAllComments', [Ref('t')],
        after=['rpc.edit.edit.own', 'rpc.edit.edit.positional', 'rpc.edit.edit.application-edits-any',
               'rpc.create.create.all-in-order'])
    rpc('remove', 'remove', 'others-comment', 'removeComment', [Ref('cc-admin')], actor='cora')
    rpc('remove', 'remove', 'own', 'removeComment', [Ref('c3')], actor='cora')
    rpc('remove', 'remove', 'application-any', 'removeComment', [Ref('c4')], actor='app')
    rpc('remove', 'remove', 'own-admin', 'removeComment', [Ref('c1')])
    rpc('remove', 'remove', 'remaining', 'getAllComments', [Ref('t')],
        after=['rpc.remove.remove.own', 'rpc.remove.remove.application-any', 'rpc.remove.remove.own-admin',
               'rpc.edit.edit.after-edits'])
    rpc('remove', 'remove', 'checks-after-refusals', 'getAllComments', [Ref('tc')],
        describe='getAllComments of the checks task after the refused creations, edits and removal')
    rpc('remove', 'remove', 'removed-read', 'getComment', [Ref('c3')], actor='app', after=['rpc.remove.remove.own'],
        requires=['rpc.create.create.own-read'])
    rpc('remove', 'remove', 'again', 'removeComment', [Ref('c3')], actor='app', after=['rpc.remove.remove.own'])
