"""Authorization of the user API: application roles and project roles, procedure by procedure.

Every project-scoped procedure is called at the boundary of its access level: the lowest project role that may use it
and the highest role that may not (a project viewer for reads; viewer and member for member-level changes; member and
manager for manager-level changes), plus representatives of other ways to hold or lack a role (membership through a
group, an administrator or application manager who is not a project member). Application-level procedures are called
as application user, manager and administrator. A refusal counts only together with the allowed call of the same
procedure. Observations record whether the request was performed (error code or the kind of answer), not its content;
the content of each procedure is checked by its own module.
"""
from harness import ADMIN, Ref, b64

PASSWORD = 'Role-Pass-2026'
ROLES = {'viewer': 'project-viewer', 'member': 'project-member', 'manager': 'project-manager'}


def build(suite):
    fx = suite.fixture
    # -- accounts, group and the project with one member of each role ----------------------------------------
    for name in ('viewer', 'member', 'manager', 'outsider', 'grouped', 'appmgr'):
        role = 'app-manager' if name == 'appmgr' else 'app-user'
        fx('base', 'user-' + name, 'createUser', {'username': name, 'password': PASSWORD, 'name': name.title(),
                                                  'role': role}, actor=ADMIN, save='u-' + name, password=PASSWORD)
    fx('base', 'admin-id', 'getUserByName', ['admin'], save='u-admin')
    fx('base', 'group', 'createGroup', ['Crew'], save='crew')
    fx('base', 'group-member', 'addGroupMember', [Ref('crew'), Ref('u-grouped')])
    for key, name, identifier in (('p', 'Perm Project', 'PERM'), ('p2', 'Perm Second', 'PERMTWO')):
        fx('base', key, 'createProject', {'name': name, 'identifier': identifier,
                                          'email': identifier.lower() + '@example.test'}, actor='app', save=key)
        for role in ROLES:
            fx('base', f'{key}-{role}', 'addProjectUser', [Ref(key), Ref('u-' + role), ROLES[role]], actor='app')
        fx('base', key + '-crew', 'addProjectGroup', [Ref(key), Ref('crew'), 'project-member'], actor='app')
    fx('base', 'columns', 'getColumns', [Ref('p')], actor='app', save='cols')
    fx('base', 'swimlanes', 'getActiveSwimlanes', [Ref('p')], actor='app', save='lanes')
    fx('base', 'lane', 'addSwimlane', [Ref('p'), 'Perm lane'], actor='app', save='lane')
    fx('base', 'category', 'createCategory', {'project_id': Ref('p'), 'name': 'Perm category'}, actor='app',
       save='cat')
    # Created by a signed-in project manager, so that the project has activity to read.
    fx('base', 'task', 'createTask', {'title': 'Perm task', 'project_id': Ref('p'), 'reference': 'PERM-1',
                                      'date_due': '2026-04-01 10:00'}, actor='manager', save='t')
    fx('base', 'task2', 'createTask', {'title': 'Perm second task', 'project_id': Ref('p')}, actor='app', save='t2')
    fx('base', 'subtask', 'createSubtask', {'task_id': Ref('t'), 'title': 'Perm subtask'}, actor='app', save='st')
    fx('base', 'comment', 'createComment', {'task_id': Ref('t'), 'user_id': Ref('u-admin', 'id'),
                                            'content': 'Perm comment'}, actor='app', save='cm')
    fx('base', 'link', 'createTaskLink', [Ref('t'), Ref('t2'), 1], actor='app', save='tl')
    fx('base', 'external', 'createExternalTaskLink', {'task_id': Ref('t'), 'url': 'https://example.org/perm',
                                                      'dependency': 'related'}, actor='app', save='el')
    fx('base', 'task-file', 'createTaskFile', [Ref('p'), Ref('t'), 'perm.txt', b64('permission file')],
       actor='app', save='tf')
    fx('base', 'project-file', 'createProjectFile', [Ref('p'), 'perm-plan.txt', b64('permission plan')],
       actor='app', save='pf')
    fx('base', 'task-meta', 'saveTaskMetadata', [Ref('t'), {'k': 'task value'}], actor='app')
    fx('base', 'project-meta', 'saveProjectMetadata', [Ref('p'), {'k': 'project value'}], actor='app')
    fx('base', 'tag', 'createTag', [Ref('p'), 'perm-tag'], actor='app', save='tag')
    fx('base', 'task-tags', 'setTaskTags', [Ref('p'), Ref('t'), ['perm-tag']], actor='app')
    fx('base', 'action', 'createAction', {'project_id': Ref('p'), 'event_name': 'task.move.column',
                                          'action_name': '\\Kanboard\\Action\\TaskCloseColumn',
                                          'params': {'column_id': Ref('cols', 3, 'id')}}, actor='app', save='act')

    def call(family, step, method, params, actor, requires=()):
        return suite.rpc(family, 'base', step, method, params, actor, project=lambda c, r: c.outcome(r),
                         requires=requires)

    # -- reads: project viewer allowed, a user without a project role refused ----------------------------------
    reads = [
        ('getProjectById', [Ref('p')]), ('getProjectByName', ['Perm Project']),
        ('getProjectByIdentifier', ['PERM']), ('getProjectByEmail', ['perm@example.test']),
        ('getProjectActivity', [Ref('p')]), ('getProjectActivities', [[Ref('p')]]),
        ('getColumns', [Ref('p')]), ('getColumn', [Ref('cols', 0, 'id')]),
        ('getAllSwimlanes', [Ref('p')]), ('getActiveSwimlanes', [Ref('p')]),
        ('getSwimlaneById', [Ref('lane')]), ('getSwimlaneByName', [Ref('p'), 'Perm lane']),
        ('getSwimlane', [Ref('lane')]), ('getAllCategories', [Ref('p')]), ('getCategory', [Ref('cat')]),
        ('getBoard', [Ref('p')]), ('getAllTasks', [Ref('p'), 1]), ('getTask', [Ref('t')]),
        ('getTaskByReference', [Ref('p'), 'PERM-1']), ('searchTasks', [Ref('p'), 'status:open']),
        ('getOverdueTasksByProject', [Ref('p')]), ('getAllComments', [Ref('t')]), ('getComment', [Ref('cm')]),
        ('getAllSubtasks', [Ref('t')]), ('getSubtask', [Ref('st')]),
        ('hasSubtaskTimer', [Ref('st'), Ref('u-viewer')]), ('getSubtaskTimeSpent', [Ref('st'), Ref('u-viewer')]),
        ('getAllTaskLinks', [Ref('t')]), ('getTaskLinkById', [Ref('tl')]),
        ('getAllExternalTaskLinks', [Ref('t')]), ('getExternalTaskLinkById', [Ref('t'), Ref('el')]),
        ('getAllTaskFiles', [Ref('t')]), ('getTaskFile', [Ref('tf')]), ('downloadTaskFile', [Ref('tf')]),
        ('getAllProjectFiles', [Ref('p')]), ('getProjectFile', [Ref('p'), Ref('pf')]),
        ('downloadProjectFile', [Ref('p'), Ref('pf')]), ('getTaskMetadata', [Ref('t')]),
        ('getTaskMetadataByName', [Ref('t'), 'k']), ('getProjectMetadata', [Ref('p')]),
        ('getProjectMetadataByName', [Ref('p'), 'k']), ('getTaskTags', [Ref('t')]),
        ('getTagsByProject', [Ref('p')]), ('getProjectUsers', [Ref('p')]), ('getAssignableUsers', [Ref('p')]),
        ('getProjectUserRole', [Ref('p'), Ref('u-member')]),
    ]
    for method, params in reads:
        allowed = call('read', method + '-viewer', method, params, 'viewer')
        call('read', method + '-outsider', method, params, 'outsider', requires=[allowed])
    # Other ways to hold or lack a role, on representative reads.
    for method, params in (('getProjectById', [Ref('p')]), ('getBoard', [Ref('p')]), ('getTask', [Ref('t')]),
                           ('getAllComments', [Ref('t')]), ('getProjectUsers', [Ref('p')])):
        allowed = call('read', method + '-group-member', method, params, 'grouped')
        call('read', method + '-admin-not-member', method, params, ADMIN, requires=[allowed])
        call('read', method + '-app-manager-not-member', method, params, 'appmgr', requires=[allowed])
        call('read', method + '-application-token', method, params, 'app')
    for method, params in (('getAllTasks', [Ref('p'), 1]), ('getColumns', [Ref('p')])):
        call('read', method + '-anonymous', method, params, None)

    # -- member-level changes: viewer refused, member allowed (each on its own subject) -------------------------
    def member_level(method, refused, allowed):
        ok = call('member', method + '-member', method, allowed, 'member')
        call('member', method + '-viewer', method, refused, 'viewer', requires=[ok])
        return ok

    for key, title in (('t-close', 'Close me'), ('t-remove', 'Remove me'), ('t-files', 'Files task'),
                       ('t-move', 'Move me'), ('t-update', 'Update me')):
        fx('base', key, 'createTask', {'title': title, 'project_id': Ref('p')}, actor='app', save=key)
    # Users change only their own comments: the member's own comments are the subjects of the allowed changes.
    fx('base', 'cm-member', 'createComment', {'task_id': Ref('t'), 'user_id': Ref('u-member'),
                                              'content': 'Member comment'}, actor='app', save='cm-member')
    fx('base', 'cm-remove', 'createComment', {'task_id': Ref('t'), 'user_id': Ref('u-member'),
                                              'content': 'Comment to remove'}, actor='app', save='cm-remove')
    fx('base', 'pf-remove', 'createProjectFile', [Ref('p'), 'remove-plan.txt', b64('remove plan')], actor='app',
       save='pf-remove')
    fx('base', 'st-remove', 'createSubtask', {'task_id': Ref('t'), 'title': 'Subtask to remove'}, actor='app',
       save='st-remove')
    fx('base', 'tl-remove', 'createTaskLink', [Ref('t'), Ref('t2'), 2], actor='app', save='tl-remove')
    fx('base', 'el-remove', 'createExternalTaskLink', {'task_id': Ref('t'), 'url': 'https://example.org/remove',
                                                       'dependency': 'related'}, actor='app', save='el-remove')
    fx('base', 'tf-remove', 'createTaskFile', [Ref('p'), Ref('t-files'), 'remove.txt', b64('remove')],
       actor='app', save='tf-remove')
    fx('base', 'tf-keep', 'createTaskFile', [Ref('p'), Ref('t-files'), 'keep.txt', b64('keep')], actor='app',
       save='tf-keep')
    fx('base', 'tag-remove', 'createTag', [Ref('p'), 'tag-to-remove'], actor='app', save='tag-remove')
    member_level('createTask', {'title': 'Viewer task', 'project_id': Ref('p')},
                 {'title': 'Member task', 'project_id': Ref('p')})
    member_level('updateTask', {'id': Ref('t-update'), 'title': 'Viewer title'},
                 {'id': Ref('t-update'), 'title': 'Member title'})
    member_level('closeTask', [Ref('t')], [Ref('t-close')])
    member_level('openTask', [Ref('t-close')], [Ref('t-close')])
    member_level('moveTaskPosition', [Ref('p'), Ref('t-move'), Ref('cols', 1, 'id'), 1, Ref('lanes', 0, 'id')],
                 [Ref('p'), Ref('t-move'), Ref('cols', 2, 'id'), 1, Ref('lanes', 0, 'id')])
    member_level('duplicateTaskToProject', [Ref('t'), Ref('p')], [Ref('t'), Ref('p')])
    member_level('moveTaskToProject', [Ref('t-move'), Ref('p2')], [Ref('t-move'), Ref('p2')])
    member_level('removeTask', [Ref('t')], [Ref('t-remove')])
    member_level('createComment', {'task_id': Ref('t'), 'user_id': Ref('u-viewer'), 'content': 'By viewer'},
                 {'task_id': Ref('t'), 'user_id': Ref('u-member'), 'content': 'By member'})
    member_level('updateComment', {'id': Ref('cm'), 'content': 'Viewer edit'},
                 {'id': Ref('cm-member'), 'content': 'Member edit'})
    member_level('removeComment', [Ref('cm')], [Ref('cm-remove')])
    member_level('createSubtask', {'task_id': Ref('t'), 'title': 'Viewer subtask'},
                 {'task_id': Ref('t'), 'title': 'Member subtask'})
    member_level('updateSubtask', {'id': Ref('st'), 'task_id': Ref('t'), 'title': 'Viewer edit'},
                 {'id': Ref('st'), 'task_id': Ref('t'), 'title': 'Member edit'})
    member_level('removeSubtask', [Ref('st')], [Ref('st-remove')])
    member_level('setSubtaskStartTime', [Ref('st'), Ref('u-viewer')], [Ref('st'), Ref('u-member')])
    member_level('setSubtaskEndTime', [Ref('st'), Ref('u-viewer')], [Ref('st'), Ref('u-member')])
    member_level('createTaskLink', [Ref('t'), Ref('t2'), 4], [Ref('t'), Ref('t2'), 6])
    member_level('updateTaskLink', [Ref('tl'), Ref('t'), Ref('t2'), 10], [Ref('tl'), Ref('t'), Ref('t2'), 8])
    member_level('removeTaskLink', [Ref('tl')], [Ref('tl-remove')])
    member_level('createExternalTaskLink',
                 {'task_id': Ref('t'), 'url': 'https://example.org/viewer', 'dependency': 'related'},
                 {'task_id': Ref('t'), 'url': 'https://example.org/member', 'dependency': 'related'})
    member_level('updateExternalTaskLink', {'task_id': Ref('t'), 'link_id': Ref('el'), 'title': 'Viewer'},
                 {'task_id': Ref('t'), 'link_id': Ref('el'), 'title': 'Member'})
    member_level('removeExternalTaskLink', [Ref('t'), Ref('el')], [Ref('t'), Ref('el-remove')])
    member_level('createTaskFile', [Ref('p'), Ref('t'), 'viewer.txt', b64('viewer')],
                 [Ref('p'), Ref('t'), 'member.txt', b64('member')])
    member_level('removeTaskFile', [Ref('tf')], [Ref('tf-remove')])
    member_level('removeAllTaskFiles', [Ref('t')], [Ref('t-files')])
    member_level('createProjectFile', [Ref('p'), 'viewer.txt', b64('viewer')], [Ref('p'), 'member.txt',
                                                                                 b64('member')])
    member_level('removeProjectFile', [Ref('p'), Ref('pf')], [Ref('p'), Ref('pf-remove')])
    member_level('setTaskTags', [Ref('p'), Ref('t'), ['viewer-tag']], [Ref('p'), Ref('t'), ['member-tag']])
    member_level('createTag', [Ref('p'), 'viewer-made'], [Ref('p'), 'member-made'])
    member_level('updateTag', [Ref('tag'), 'viewer-renamed'], [Ref('tag'), 'member-renamed'])
    member_level('removeTag', [Ref('tag')], [Ref('tag-remove')])
    member_level('saveTaskMetadata', [Ref('t'), {'viewer': 'x'}], [Ref('t'), {'member': 'y'}])
    member_level('removeTaskMetadata', [Ref('t'), 'k'], [Ref('t'), 'k'])
    # A group membership grants the group's project role.
    grouped = call('member', 'createTask-group-member', 'createTask', {'title': 'Group task', 'project_id': Ref('p')},
                   'grouped')
    call('member', 'createTask-outsider', 'createTask', {'title': 'Outsider task', 'project_id': Ref('p')},
         'outsider', requires=[grouped])
    call('member', 'createTask-admin-not-member', 'createTask', {'title': 'Admin task', 'project_id': Ref('p')},
         ADMIN, requires=[grouped])
    call('member', 'createComment-group-member', 'createComment',
         {'task_id': Ref('t'), 'user_id': Ref('u-grouped'), 'content': 'By group member'}, 'grouped')

    # -- manager-level changes: member refused, manager allowed --------------------------------------------------
    def manager_level(method, refused, allowed):
        ok = call('manager', method + '-manager', method, allowed, 'manager')
        call('manager', method + '-member', method, refused, 'member', requires=[ok])
        return ok

    fx('base', 'cat-remove', 'createCategory', {'project_id': Ref('p'), 'name': 'Category to remove'},
       actor='app', save='cat-remove')
    fx('base', 'col-remove', 'addColumn', [Ref('p'), 'Column to remove'], actor='app', save='col-remove')
    fx('base', 'lane-remove', 'addSwimlane', [Ref('p'), 'Lane to remove'], actor='app', save='lane-remove')
    fx('base', 'act-remove', 'createAction', {'project_id': Ref('p'), 'event_name': 'task.move.column',
                                              'action_name': '\\Kanboard\\Action\\TaskCloseColumn',
                                              'params': {'column_id': Ref('cols', 2, 'id')}}, actor='app',
       save='act-remove')
    fx('base', 'group2', 'createGroup', ['Second crew'], save='crew2')
    fx('base', 'p-meta2', 'saveProjectMetadata', [Ref('p'), {'gone': 'soon'}], actor='app')
    fx('base', 'p3', 'createProject', {'name': 'Perm Third'}, actor='app', save='p3')
    fx('base', 'p3-manager', 'addProjectUser', [Ref('p3'), Ref('u-manager'), 'project-manager'], actor='app')
    fx('base', 'p3-member', 'addProjectUser', [Ref('p3'), Ref('u-member'), 'project-member'], actor='app')
    manager_level('getActions', [Ref('p')], [Ref('p')])
    manager_level('createAction', {'project_id': Ref('p'), 'event_name': 'task.move.column',
                                   'action_name': '\\Kanboard\\Action\\TaskCloseColumn',
                                   'params': {'column_id': Ref('cols', 1, 'id')}},
                  {'project_id': Ref('p'), 'event_name': 'task.move.column',
                   'action_name': '\\Kanboard\\Action\\TaskCloseColumn', 'params': {'column_id': Ref('cols', 0, 'id')}})
    manager_level('removeAction', [Ref('act')], [Ref('act-remove')])
    manager_level('createCategory', {'project_id': Ref('p'), 'name': 'Member category'},
                  {'project_id': Ref('p'), 'name': 'Manager category'})
    manager_level('updateCategory', {'id': Ref('cat'), 'name': 'Member rename'},
                  {'id': Ref('cat'), 'name': 'Manager rename'})
    manager_level('removeCategory', [Ref('cat')], [Ref('cat-remove')])
    manager_level('addColumn', [Ref('p'), 'Member column'], [Ref('p'), 'Manager column'])
    manager_level('updateColumn', [Ref('cols', 0, 'id'), 'Member backlog'], [Ref('cols', 0, 'id'), 'Manager backlog'])
    manager_level('changeColumnPosition', [Ref('p'), Ref('cols', 0, 'id'), 2], [Ref('p'), Ref('cols', 0, 'id'), 2])
    manager_level('removeColumn', [Ref('cols', 1, 'id')], [Ref('col-remove')])
    manager_level('addSwimlane', [Ref('p'), 'Member lane'], [Ref('p'), 'Manager lane'])
    manager_level('updateSwimlane', [Ref('p'), Ref('lane'), 'Member lane name'],
                  [Ref('p'), Ref('lane'), 'Manager lane name'])
    manager_level('disableSwimlane', [Ref('p'), Ref('lane')], [Ref('p'), Ref('lane')])
    manager_level('enableSwimlane', [Ref('p'), Ref('lane')], [Ref('p'), Ref('lane')])
    manager_level('changeSwimlanePosition', [Ref('p'), Ref('lane'), 1], [Ref('p'), Ref('lane'), 1])
    manager_level('removeSwimlane', [Ref('p'), Ref('lane')], [Ref('p'), Ref('lane-remove')])
    manager_level('addProjectUser', [Ref('p'), Ref('u-outsider'), 'project-viewer'],
                  [Ref('p'), Ref('u-appmgr'), 'project-viewer'])
    manager_level('changeProjectUserRole', [Ref('p'), Ref('u-viewer'), 'project-member'],
                  [Ref('p'), Ref('u-appmgr'), 'project-member'])
    manager_level('removeProjectUser', [Ref('p'), Ref('u-viewer')], [Ref('p'), Ref('u-appmgr')])
    manager_level('addProjectGroup', [Ref('p'), Ref('crew2'), 'project-viewer'],
                  [Ref('p'), Ref('crew2'), 'project-viewer'])
    manager_level('changeProjectGroupRole', [Ref('p'), Ref('crew2'), 'project-member'],
                  [Ref('p'), Ref('crew2'), 'project-member'])
    manager_level('removeProjectGroup', [Ref('p'), Ref('crew2')], [Ref('p'), Ref('crew2')])
    manager_level('saveProjectMetadata', [Ref('p'), {'member': 'x'}], [Ref('p'), {'manager': 'y'}])
    manager_level('removeProjectMetadata', [Ref('p'), 'k'], [Ref('p'), 'gone'])
    manager_level('updateProject', {'project_id': Ref('p2'), 'description': 'By member'},
                  {'project_id': Ref('p2'), 'description': 'By manager'})
    manager_level('enableProjectPublicAccess', [Ref('p2')], [Ref('p2')])
    manager_level('disableProjectPublicAccess', [Ref('p2')], [Ref('p2')])
    manager_level('disableProject', [Ref('p2')], [Ref('p2')])
    manager_level('enableProject', [Ref('p2')], [Ref('p2')])
    manager_level('removeProject', [Ref('p3')], [Ref('p3')])
    # Removing every project file is a member-level change; the viewer is refused first.
    refused = call('member', 'removeAllProjectFiles-viewer', 'removeAllProjectFiles', [Ref('p')], 'viewer',
                   requires=['rpc.member.base.removeAllProjectFiles-member'])
    call('member', 'removeAllProjectFiles-member', 'removeAllProjectFiles', [Ref('p')], 'member')

    # -- application roles -----------------------------------------------------------------------------------
    fx('base', 'victim', 'createUser', {'username': 'victim', 'password': PASSWORD}, save='u-victim')
    fx('base', 'victim2', 'createUser', {'username': 'victim2', 'password': PASSWORD}, save='u-victim2')
    fx('base', 'link-label', 'createLink', ['acl relates', 'acl related by'], save='acl-link')
    fx('base', 'group3', 'createGroup', ['Third crew'], save='crew3')
    admin_only = [
        ('getUser', [Ref('u-member')]), ('getUserByName', ['member']), ('getAllUsers', None),
        ('isActiveUser', [Ref('u-member')]), ('createUser', {'username': 'made-by', 'password': PASSWORD}),
        ('updateUser', {'id': Ref('u-victim'), 'name': 'Renamed'}), ('disableUser', [Ref('u-victim')]),
        ('enableUser', [Ref('u-victim')]), ('removeUser', [Ref('u-victim2')]), ('createLdapUser', ['ldap-person']),
        ('getAllGroups', None), ('getGroup', [Ref('crew')]), ('createGroup', ['Made group']),
        ('updateGroup', [Ref('crew3'), 'Renamed crew']), ('removeGroup', [Ref('crew3')]),
        ('getGroupMembers', [Ref('crew')]), ('getMemberGroups', [Ref('u-grouped')]),
        ('isGroupMember', [Ref('crew'), Ref('u-grouped')]), ('addGroupMember', [Ref('crew'), Ref('u-outsider')]),
        ('removeGroupMember', [Ref('crew'), Ref('u-outsider')]),
        ('getAllLinks', None), ('getLinkById', [1]), ('getLinkByLabel', ['blocks']), ('getOppositeLinkId', [2]),
        ('createLink', ['acl made', 'acl made by']), ('updateLink', [Ref('acl-link'), 0, 'acl renamed']),
        ('removeLink', [Ref('acl-link')]), ('getAllProjects', None), ('getOverdueTasks', None),
    ]
    for method, params in admin_only:
        ok = suite.qualify(f'rpc.application.base.{method}-admin')
        for role in ('outsider', 'appmgr'):
            call('application', f'{method}-{role}', method, params, role, requires=[ok])
        assert call('application', method + '-admin', method, params, ADMIN) == ok
    manager_ok = call('application', 'createProject-app-manager', 'createProject', {'name': 'Manager made'},
                      'appmgr')
    call('application', 'createProject-app-user', 'createProject', {'name': 'User made'}, 'outsider',
         requires=[manager_ok])
    # Application-level procedures that every user may call (a user with project memberships, so that the answers
    # have content).
    for method, params in (('getAllTags', None), ('getMe', None), ('getMyProjects', None),
                           ('getMyProjectsList', None), ('createMyPrivateProject', ['Mine']), ('getVersion', None),
                           ('getColorList', None), ('getAvailableActions', None)):
        call('application', method + '-app-user', method, params, 'member')
