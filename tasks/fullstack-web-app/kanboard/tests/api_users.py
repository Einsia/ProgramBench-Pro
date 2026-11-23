"""Users, groups and group membership (administrator procedures of the JSON-RPC API).

Creation with every optional field, the validation rules (required username, unique username, password length,
e-mail syntax, application roles, username length), reads by id and by name, the sorted collection, updates of each
field and their validation, disabling and enabling (a disabled account cannot use the API), removal and what it
unassigns, LDAP account creation without a directory, and groups with their members.
"""
from harness import Ref, saved_ids, subset

PASSWORD = 'Users-Pass-2026'
# Shared lists show the accounts and groups of the ordinary steps only; refused attempts and boundary cases may or may
# not add records there, which those cases check on their own.
ORDINARY_USERS = ('admin', 'mia', 'noah', 'olga', 'pia', 'zoe')
ORDINARY_GROUPS = ('designers', 'backend', 'analysts')


def ordinary_users(c, user):
    return str(user.get('id')) in saved_ids(c, *ORDINARY_USERS)


def ordinary_groups(c, group):
    return str(group.get('id')) in saved_ids(c, *ORDINARY_GROUPS)


def build(suite):
    rpc, fx = suite.rpc, suite.fixture

    # -- creation -------------------------------------------------------------------------------------------
    rpc('create', 'users', 'minimal', 'createUser', {'username': 'mia', 'password': PASSWORD}, save='mia')
    rpc('create', 'users', 'minimal-read', 'getUser', [Ref('mia')])
    rpc('create', 'users', 'full', 'createUser', {'username': 'noah', 'password': PASSWORD, 'name': 'Noah Field',
                                                  'email': 'noah@example.test', 'role': 'app-manager'}, save='noah')
    rpc('create', 'users', 'full-read', 'getUser', [Ref('noah')])
    rpc('create', 'users', 'admin-role', 'createUser', {'username': 'olga', 'password': PASSWORD, 'name': 'Olga',
                                                        'role': 'app-admin'}, save='olga')
    rpc('create', 'users', 'admin-role-read', 'getUserByName', ['olga'])
    rpc('create', 'users', 'positional', 'createUser', ['pia', PASSWORD, 'Pia Positional', 'pia@example.test'],
        save='pia')
    rpc('create', 'users', 'positional-read', 'getUser', [Ref('pia')])
    rpc('create', 'users', 'unicode-name', 'createUser', {'username': 'zoë', 'password': PASSWORD,
                                                          'name': 'Zoë Ünïcode 李'}, save='zoe')
    rpc('create', 'users', 'unicode-name-read', 'getUserByName', ['zoë'])
    rpc('create', 'users', 'trimmed-username', 'createUser', {'username': '  quinn  ', 'password': PASSWORD},
        save='quinn')
    rpc('create', 'users', 'trimmed-username-read', 'getUser', [Ref('quinn')])
    rpc('create', 'users', 'trimmed-username-lookup', 'getUserByName', ['quinn'], after=[
        'rpc.create.users.trimmed-username'])
    rpc('create', 'users', 'duplicate-email-allowed', 'createUser', {'username': 'noah2', 'password': PASSWORD,
                                                                     'email': 'noah@example.test'}, save='noah2')
    rpc('create', 'users', 'max-username', 'createUser', {'username': 'u' * 191, 'password': PASSWORD},
        save='long-user')
    rpc('create', 'users', 'six-character-password', 'createUser', {'username': 'six', 'password': 'abcdef'},
        save='six')
    # Refused creations: every rule on its own.
    fx('create', 'existing', 'createUser', {'username': 'taken', 'password': PASSWORD}, save='taken')
    rpc('create', 'validation', 'duplicate-username', 'createUser', {'username': 'taken', 'password': PASSWORD})
    rpc('create', 'validation', 'duplicate-admin', 'createUser', {'username': 'admin', 'password': PASSWORD})
    rpc('create', 'validation', 'short-password', 'createUser', {'username': 'shorty', 'password': 'abcde'})
    rpc('create', 'validation', 'empty-password', 'createUser', {'username': 'nopass', 'password': ''})
    rpc('create', 'validation', 'empty-username', 'createUser', {'username': '', 'password': PASSWORD})
    rpc('create', 'validation', 'too-long-username', 'createUser', {'username': 'u' * 192, 'password': PASSWORD})
    rpc('create', 'validation', 'invalid-email', 'createUser', {'username': 'mailer', 'password': PASSWORD,
                                                                'email': 'not-an-email'})
    rpc('create', 'validation', 'invalid-role', 'createUser', {'username': 'roler', 'password': PASSWORD,
                                                               'role': 'project-manager'})
    rpc('create', 'validation', 'unknown-role', 'createUser', {'username': 'roler2', 'password': PASSWORD,
                                                               'role': 'superuser'})
    rpc('create', 'validation', 'missing-password', 'createUser', {'username': 'nopw'})
    rpc('create', 'validation', 'refused-not-stored', 'getUserByName', ['shorty'])

    # -- authentication of created accounts ----------------------------------------------------------------
    def password_of(name):
        def register(c):
            c.passwords[name] = PASSWORD
        return register
    rpc('auth', 'accounts', 'new-user-signs-in', 'getMe', None, 'mia', prepare=password_of('mia'),
        after=['rpc.create.users.minimal'])
    rpc('auth', 'accounts', 'new-user-wrong-password', 'getMe', None, ('wrong', 'mia'),
        after=['rpc.create.users.minimal'], requires=['rpc.auth.accounts.new-user-signs-in'])
    rpc('auth', 'accounts', 'six-character-password-signs-in', 'getVersion', None, ('secret', 'six', 'abcdef'),
        after=['rpc.create.users.six-character-password'])
    rpc('auth', 'accounts', 'trimmed-username-signs-in', 'getVersion', None, ('secret', 'quinn', PASSWORD),
        after=['rpc.create.users.trimmed-username'])

    # -- reads ----------------------------------------------------------------------------------------------
    fx('read', 'admin', 'getUserByName', ['admin'], save='admin')
    rpc('read', 'users', 'all-sorted', 'getAllUsers', project=subset(ordinary_users, 'user'),
        after=['rpc.create.users.minimal', 'rpc.create.users.full', 'rpc.create.users.admin-role',
               'rpc.create.users.positional', 'rpc.create.users.unicode-name'],
        describe='getAllUsers as admin (the accounts of the ordinary creations)')
    rpc('read', 'users', 'by-id-admin', 'getUser', [Ref('admin', 'id')])
    rpc('read', 'users', 'by-name-admin', 'getUserByName', ['admin'])
    rpc('read', 'users', 'by-name-case', 'getUserByName', ['MIA'], after=['rpc.create.users.minimal'])
    rpc('read', 'users', 'by-name-missing', 'getUserByName', ['nobody-here'],
        requires=['rpc.read.users.by-name-admin'])
    rpc('read', 'users', 'by-id-missing', 'getUser', [987654], requires=['rpc.read.users.by-id-admin'])
    rpc('read', 'users', 'active-missing', 'isActiveUser', [987654])

    # -- updates --------------------------------------------------------------------------------------------
    fx('update', 'subject', 'createUser', {'username': 'rita', 'password': PASSWORD, 'name': 'Rita',
                                           'email': 'rita@example.test'}, save='rita', password=PASSWORD)
    fx('update', 'other', 'createUser', {'username': 'sam', 'password': PASSWORD}, save='sam')
    rpc('update', 'update', 'name', 'updateUser', {'id': Ref('rita'), 'name': 'Rita Renamed'})
    rpc('update', 'update', 'name-read', 'getUser', [Ref('rita')], after=['rpc.update.update.name'])
    rpc('update', 'update', 'email', 'updateUser', {'id': Ref('rita'), 'email': 'rita.new@example.test'})
    rpc('update', 'update', 'role', 'updateUser', {'id': Ref('rita'), 'role': 'app-manager'})
    rpc('update', 'update', 'email-role-read', 'getUser', [Ref('rita')],
        after=['rpc.update.update.email', 'rpc.update.update.role'])
    rpc('update', 'update', 'username', 'updateUser', {'id': Ref('rita'), 'username': 'rita2'})
    rpc('update', 'update', 'username-old-name', 'getUserByName', ['rita'], after=['rpc.update.update.username'])
    rpc('update', 'update', 'username-new-name', 'getUserByName', ['rita2'], after=['rpc.update.update.username'])
    rpc('update', 'update', 'renamed-signs-in', 'getVersion', None, ('secret', 'rita2', PASSWORD),
        after=['rpc.update.update.username'])
    rpc('update', 'update', 'positional', 'updateUser', [Ref('rita'), None, 'Rita Positional'])
    rpc('update', 'update', 'positional-read', 'getUser', [Ref('rita')], after=['rpc.update.update.positional'])
    rpc('update', 'update', 'clear-name', 'updateUser', {'id': Ref('rita'), 'name': ''})
    rpc('update', 'update', 'clear-name-read', 'getUser', [Ref('rita')], after=['rpc.update.update.clear-name'])
    rpc('update', 'validation', 'duplicate-username', 'updateUser', {'id': Ref('rita'), 'username': 'sam'})
    rpc('update', 'validation', 'invalid-email', 'updateUser', {'id': Ref('rita'), 'email': 'broken@'})
    rpc('update', 'validation', 'invalid-role', 'updateUser', {'id': Ref('rita'), 'role': 'project-viewer'})
    rpc('update', 'validation', 'too-long-username', 'updateUser', {'id': Ref('rita'), 'username': 'r' * 192})
    rpc('update', 'validation', 'unchanged-after-refusals', 'getUser', [Ref('rita')],
        after=['rpc.update.update.clear-name'])
    rpc('update', 'validation', 'missing-user', 'updateUser', {'id': 987654, 'name': 'Ghost'})
    rpc('update', 'validation', 'only-id', 'updateUser', {'id': Ref('sam')})

    # -- enable, disable, remove -----------------------------------------------------------------------------
    fx('status', 'subject', 'createUser', {'username': 'tess', 'password': PASSWORD}, save='tess',
       password=PASSWORD)
    rpc('status', 'status', 'active-initially', 'isActiveUser', [Ref('tess')])
    rpc('status', 'status', 'disable', 'disableUser', [Ref('tess')])
    rpc('status', 'status', 'inactive', 'isActiveUser', [Ref('tess')], after=['rpc.status.status.disable'])
    rpc('status', 'status', 'disabled-read', 'getUser', [Ref('tess')], after=['rpc.status.status.disable'])
    rpc('status', 'status', 'disabled-cannot-sign-in', 'getMe', None, 'tess', after=['rpc.status.status.disable'],
        requires=['rpc.status.status.enabled-signs-in'])
    rpc('status', 'status', 'disable-again', 'disableUser', [Ref('tess')], after=['rpc.status.status.disable'])
    rpc('status', 'status', 'enable', 'enableUser', [Ref('tess')], after=['rpc.status.status.disable'])
    rpc('status', 'status', 'active-again', 'isActiveUser', [Ref('tess')], after=['rpc.status.status.enable'])
    rpc('status', 'status', 'enabled-signs-in', 'getMe', None, 'tess', after=['rpc.status.status.enable'])
    rpc('status', 'status', 'disable-missing', 'disableUser', [987654])
    rpc('status', 'status', 'enable-missing', 'enableUser', [987654])

    fx('remove', 'subject', 'createUser', {'username': 'uma', 'password': PASSWORD, 'name': 'Uma'}, save='uma',
       password=PASSWORD)
    fx('remove', 'project', 'createProject', {'name': 'Removal project'}, save='rm-project')
    fx('remove', 'member', 'addProjectUser', [Ref('rm-project'), Ref('uma'), 'project-member'])
    fx('remove', 'task', 'createTask', {'title': 'Assigned to Uma', 'project_id': Ref('rm-project'),
                                        'owner_id': Ref('uma')}, save='rm-task')
    fx('remove', 'subtask', 'createSubtask', {'task_id': Ref('rm-task'), 'title': 'Uma subtask',
                                              'user_id': Ref('uma')}, save='rm-subtask')
    fx('remove', 'comment', 'createComment', {'task_id': Ref('rm-task'), 'user_id': Ref('uma'),
                                              'content': 'Uma wrote this'}, actor='app', save='rm-comment')
    fx('remove', 'private', 'createMyPrivateProject', ['Uma private'], actor='uma', save='uma-private')
    rpc('remove', 'remove', 'remove', 'removeUser', [Ref('uma')])
    rpc('remove', 'remove', 'gone-by-id', 'getUser', [Ref('uma')], after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'gone-by-name', 'getUserByName', ['uma'], after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'cannot-sign-in', 'getVersion', None, ('secret', 'uma', PASSWORD),
        after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'task-unassigned', 'getTask', [Ref('rm-task')], after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'subtask-unassigned', 'getSubtask', [Ref('rm-subtask')], after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'comment-kept', 'getComment', [Ref('rm-comment')], after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'private-project-removed', 'getProjectById', [Ref('uma-private')], 'app',
        after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'project-members', 'getProjectUsers', [Ref('rm-project')],
        after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'remove-again', 'removeUser', [Ref('uma')], after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'remove-missing', 'removeUser', [987654])

    # -- LDAP account without a directory ---------------------------------------------------------------------
    rpc('ldap', 'ldap', 'create-without-directory', 'createLdapUser', ['directory-user'])
    rpc('ldap', 'ldap', 'not-created', 'getUserByName', ['directory-user'],
        after=['rpc.ldap.ldap.create-without-directory'])

    # -- groups ---------------------------------------------------------------------------------------------
    rpc('groups', 'groups', 'create', 'createGroup', ['Designers'], save='designers')
    rpc('groups', 'groups', 'create-external', 'createGroup', ['Backend', 'ext-backend-7'], save='backend')
    rpc('groups', 'groups', 'create-named', 'createGroup', {'name': 'Analysts', 'external_id': ''}, save='analysts')
    rpc('groups', 'groups', 'read', 'getGroup', [Ref('backend')])
    rpc('groups', 'groups', 'read-missing', 'getGroup', [987654], requires=['rpc.groups.groups.read'])
    fx('groups', 'existing', 'createGroup', ['Taken group'], save='taken-group')
    rpc('groups', 'groups', 'duplicate-name', 'createGroup', ['Taken group'])
    rpc('groups', 'groups', 'empty-name', 'createGroup', [''])
    rpc('groups', 'groups', 'all-sorted', 'getAllGroups', project=subset(ordinary_groups, 'group'),
        after=['rpc.groups.groups.create', 'rpc.groups.groups.create-external', 'rpc.groups.groups.create-named'],
        describe='getAllGroups as admin (the groups of the ordinary creations)')
    rpc('groups', 'groups', 'rename', 'updateGroup', [Ref('designers'), 'Product designers'])
    rpc('groups', 'groups', 'rename-read', 'getGroup', [Ref('designers')], after=['rpc.groups.groups.rename'])
    rpc('groups', 'groups', 'external-id', 'updateGroup', {'group_id': Ref('analysts'), 'external_id': 'ext-a'})
    rpc('groups', 'groups', 'external-id-read', 'getGroup', [Ref('analysts')], after=['rpc.groups.groups.external-id'])
    rpc('groups', 'groups', 'rename-to-existing', 'updateGroup', [Ref('taken-group'), 'Backend'])
    rpc('groups', 'groups', 'rename-missing', 'updateGroup', [987654, 'Ghosts'])

    fx('members', 'people', 'createUser', {'username': 'vera', 'password': PASSWORD, 'name': 'Vera'}, save='vera')
    fx('members', 'people2', 'createUser', {'username': 'walt', 'password': PASSWORD, 'name': 'Walt'}, save='walt')
    rpc('members', 'members', 'add', 'addGroupMember', [Ref('backend'), Ref('vera')])
    rpc('members', 'members', 'add-second', 'addGroupMember', [Ref('backend'), Ref('walt')])
    rpc('members', 'members', 'add-other-group', 'addGroupMember', [Ref('designers'), Ref('vera')])
    rpc('members', 'members', 'add-again', 'addGroupMember', [Ref('backend'), Ref('vera')],
        after=['rpc.members.members.add'])
    rpc('members', 'members', 'is-member', 'isGroupMember', [Ref('backend'), Ref('vera')],
        after=['rpc.members.members.add'])
    rpc('members', 'members', 'is-not-member', 'isGroupMember', [Ref('analysts'), Ref('vera')],
        requires=['rpc.members.members.is-member'])
    rpc('members', 'members', 'members-sorted', 'getGroupMembers', [Ref('backend')],
        after=['rpc.members.members.add', 'rpc.members.members.add-second'])
    rpc('members', 'members', 'groups-of-user', 'getMemberGroups', [Ref('vera')],
        after=['rpc.members.members.add', 'rpc.members.members.add-other-group'])
    rpc('members', 'members', 'group-counts', 'getAllGroups', project=subset(ordinary_groups, 'group'),
        after=['rpc.members.members.add', 'rpc.members.members.add-second', 'rpc.members.members.add-other-group'],
        describe='getAllGroups as admin after the members were added (the groups of the ordinary creations)')
    rpc('members', 'members', 'empty-group', 'getGroupMembers', [Ref('analysts')],
        requires=['rpc.members.members.members-sorted'])
    rpc('members', 'members', 'remove', 'removeGroupMember', [Ref('backend'), Ref('walt')],
        after=['rpc.members.members.add-second'])
    rpc('members', 'members', 'removed', 'isGroupMember', [Ref('backend'), Ref('walt')],
        after=['rpc.members.members.remove'], requires=['rpc.members.members.is-member'])
    rpc('members', 'members', 'remove-non-member', 'removeGroupMember', [Ref('analysts'), Ref('walt')])
    rpc('members', 'members', 'add-missing-user', 'addGroupMember', [Ref('backend'), 987654])
    rpc('members', 'members', 'missing-group-members', 'getGroupMembers', [987654])
    rpc('members', 'members', 'remove-group', 'removeGroup', [Ref('designers')], after=['rpc.members.members.add-other-group'])
    rpc('members', 'members', 'removed-group-gone', 'getGroup', [Ref('designers')],
        after=['rpc.members.members.remove-group'], requires=['rpc.groups.groups.read'])
    rpc('members', 'members', 'removed-group-memberships', 'getMemberGroups', [Ref('vera')],
        after=['rpc.members.members.remove-group'])
    rpc('members', 'members', 'remove-group-again', 'removeGroup', [Ref('designers')],
        after=['rpc.members.members.remove-group'])
    fx('members', 'leaver', 'createUser', {'username': 'xena', 'password': PASSWORD}, save='xena')
    fx('members', 'leaver-member', 'addGroupMember', [Ref('backend'), Ref('xena')])
    rpc('members', 'members', 'removed-user-leaves-groups', 'removeUser', [Ref('xena')])
    rpc('members', 'members', 'removed-user-members', 'getGroupMembers', [Ref('backend')],
        after=['rpc.members.members.removed-user-leaves-groups', 'rpc.members.members.remove'])
