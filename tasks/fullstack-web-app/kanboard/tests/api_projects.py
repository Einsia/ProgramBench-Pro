"""Projects: creation and its validation, lookups, updates, status, public access, removal, personal projects,
project metadata, project files and the activity stream, through the JSON-RPC API."""
from harness import Ref, b64, events, png, refused_stored, saved_ids, subset

PASSWORD = 'Projects-Pass-2026'
# Names of the creations the reference refuses (refusals-not-stored checks that none of them is stored).
REFUSED = {'', 'Dup', 'Dup2', 'Bad id', 'Long id', 'Dup mail', 'Bad mail', 'Bad date', 'Bad priority', 'Ghost owner'}
ORDINARY = ('plain', 'full', 'positional', 'unicode', 'plain2', 'olive-project', 'ownerless', 'given')


def ordinary_projects(c, project):
    return str(project.get('id')) in saved_ids(c, *ORDINARY)


def names_present(names, anchor):
    """Which of these project names a list shows (by name; a map of id to name or a list of records)."""
    def project(c, response):
        result = response.result if response.has_result else None
        if isinstance(result, dict):
            shown = list(result.values())
        elif isinstance(result, list):
            shown = [x.get('name') for x in result if isinstance(x, dict)]
        else:
            return c.observe(response)
        return {'http': response.status, 'anchor-listed': anchor in shown,
                'listed': sorted(n for n in shown if n in names)}
    return project


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'owner', 'createUser', {'username': 'olive', 'password': PASSWORD, 'name': 'Olive Owner'},
       save='olive', password=PASSWORD)
    fx('base', 'admin', 'getUserByName', ['admin'], save='admin')

    # -- creation -------------------------------------------------------------------------------------------
    rpc('create', 'create', 'minimal', 'createProject', {'name': 'Plain project'}, save='plain')
    rpc('create', 'create', 'minimal-read', 'getProjectById', [Ref('plain')])
    rpc('create', 'create', 'minimal-columns', 'getColumns', [Ref('plain')])
    rpc('create', 'create', 'minimal-swimlanes', 'getAllSwimlanes', [Ref('plain')])
    rpc('create', 'create', 'minimal-categories', 'getAllCategories', [Ref('plain')])
    rpc('create', 'create', 'creator-is-manager', 'getProjectUsers', [Ref('plain')])
    rpc('create', 'create', 'creator-role', 'getProjectUserRole', [Ref('plain'), Ref('admin', 'id')])
    rpc('create', 'create', 'full', 'createProject', {
        'name': 'Full project', 'description': 'All the **fields**', 'identifier': 'full7',
        'start_date': '2026-05-01', 'end_date': '2026-07-31', 'priority_default': 2, 'priority_start': 1,
        'priority_end': 5, 'email': 'full@example.test'}, save='full')
    rpc('create', 'create', 'full-read', 'getProjectById', [Ref('full')])
    rpc('create', 'create', 'positional', 'createProject', ['Positional project', 'Made with positions'],
        save='positional')
    rpc('create', 'create', 'positional-read', 'getProjectById', [Ref('positional')])
    rpc('create', 'create', 'unicode', 'createProject', {'name': 'Projet été 项目 🚀', 'description': 'Ünïcödé'},
        save='unicode')
    rpc('create', 'create', 'unicode-read', 'getProjectById', [Ref('unicode')])
    rpc('create', 'create', 'same-name', 'createProject', {'name': 'Plain project'}, save='plain2',
        after=['rpc.create.create.minimal'])
    rpc('create', 'create', 'application-owner', 'createProject', {'name': 'Owned by Olive', 'owner_id': Ref('olive')},
        actor='app', save='olive-project')
    rpc('create', 'create', 'application-owner-read', 'getProjectById', [Ref('olive-project')], actor='app')
    rpc('create', 'create', 'application-owner-members', 'getProjectUsers', [Ref('olive-project')], actor='app')
    rpc('create', 'create', 'application-no-owner', 'createProject', {'name': 'Ownerless'}, actor='app',
        save='ownerless')
    rpc('create', 'create', 'application-no-owner-read', 'getProjectById', [Ref('ownerless')], actor='app')
    rpc('create', 'create', 'user-gives-owner', 'createProject', {'name': 'Given to Olive', 'owner_id': Ref('olive')},
        save='given')
    rpc('create', 'create', 'user-gives-owner-read', 'getProjectById', [Ref('given')], actor='app')
    rpc('create', 'create', 'user-gives-owner-members', 'getProjectUsers', [Ref('given')], actor='app')
    rpc('create', 'create', 'user-gives-owner-creator-access', 'getProjectById', [Ref('given')],
        requires=['rpc.create.create.user-gives-owner-read'])
    rpc('create', 'validation', 'empty-name', 'createProject', {'name': ''})
    rpc('create', 'validation', 'missing-name', 'createProject', {'description': 'No name'})
    rpc('create', 'validation', 'duplicate-identifier', 'createProject', {'name': 'Dup', 'identifier': 'FULL7'},
        after=['rpc.create.create.full'])
    rpc('create', 'validation', 'duplicate-identifier-case', 'createProject', {'name': 'Dup2', 'identifier': 'Full7'},
        after=['rpc.create.create.full'])
    rpc('create', 'validation', 'identifier-not-alphanumeric', 'createProject', {'name': 'Bad id',
                                                                                'identifier': 'has-dash'})
    rpc('create', 'validation', 'identifier-too-long', 'createProject', {'name': 'Long id', 'identifier': 'A' * 51})
    rpc('create', 'validation', 'identifier-max-length', 'createProject', {'name': 'Max id', 'identifier': 'B' * 50},
        save='max-id')
    rpc('create', 'validation', 'duplicate-email', 'createProject', {'name': 'Dup mail', 'email': 'full@example.test'},
        after=['rpc.create.create.full'])
    rpc('create', 'validation', 'invalid-email', 'createProject', {'name': 'Bad mail', 'email': 'nowhere'})
    rpc('create', 'validation', 'start-date-too-long', 'createProject', {'name': 'Bad date',
                                                                        'start_date': '2026-05-01 10:00'})
    rpc('create', 'validation', 'priority-not-integer', 'createProject', {'name': 'Bad priority',
                                                                         'priority_end': 'high'})
    rpc('create', 'validation', 'unknown-owner', 'createProject', {'name': 'Ghost owner', 'owner_id': 987654},
        actor='app')
    rpc('create', 'validation', 'refusals-not-stored', 'getAllProjects',
        project=refused_stored('name', REFUSED, 'Plain project'), after=['rpc.create.create.minimal'],
        describe='getAllProjects as admin after the refused creations (which of them are stored)')

    # -- lookups --------------------------------------------------------------------------------------------
    rpc('lookup', 'lookup', 'by-name', 'getProjectByName', ['Full project'], after=['rpc.create.create.full'])
    rpc('lookup', 'lookup', 'by-name-case', 'getProjectByName', ['full project'], after=['rpc.create.create.full'],
        requires=['rpc.lookup.lookup.by-name'])
    rpc('lookup', 'lookup', 'by-name-duplicate', 'getProjectByName', ['Plain project'],
        after=['rpc.create.create.same-name'])
    rpc('lookup', 'lookup', 'by-name-missing', 'getProjectByName', ['No such project'],
        requires=['rpc.lookup.lookup.by-name'])
    rpc('lookup', 'lookup', 'by-identifier', 'getProjectByIdentifier', ['FULL7'], after=['rpc.create.create.full'])
    rpc('lookup', 'lookup', 'by-identifier-lower', 'getProjectByIdentifier', ['full7'],
        after=['rpc.create.create.full'])
    rpc('lookup', 'lookup', 'by-identifier-missing', 'getProjectByIdentifier', ['NOPE'],
        requires=['rpc.lookup.lookup.by-identifier'])
    rpc('lookup', 'lookup', 'by-identifier-empty', 'getProjectByIdentifier', [''],
        requires=['rpc.lookup.lookup.by-identifier'])
    rpc('lookup', 'lookup', 'by-email', 'getProjectByEmail', ['full@example.test'], after=['rpc.create.create.full'])
    rpc('lookup', 'lookup', 'by-email-missing', 'getProjectByEmail', ['none@example.test'],
        requires=['rpc.lookup.lookup.by-email'])
    rpc('lookup', 'lookup', 'by-id-missing-application', 'getProjectById', [987654], actor='app')
    rpc('lookup', 'lookup', 'by-id-missing-user', 'getProjectById', [987654])
    rpc('lookup', 'lookup', 'all-sorted', 'getAllProjects', actor='app', project=subset(ordinary_projects, 'project'),
        after=['rpc.create.create.minimal', 'rpc.create.create.full', 'rpc.create.create.positional',
               'rpc.create.create.unicode', 'rpc.create.create.same-name', 'rpc.create.create.application-owner',
               'rpc.create.create.application-no-owner', 'rpc.create.create.user-gives-owner'],
        describe='getAllProjects as app (the projects of the ordinary creations)')

    # -- updates --------------------------------------------------------------------------------------------
    fx('update', 'project', 'createProject', {'name': 'Editable', 'identifier': 'EDIT', 'email': 'edit@example.test'},
       save='edit')
    fx('update', 'other', 'createProject', {'name': 'Other', 'identifier': 'OTHER', 'email': 'other@example.test'},
       save='other')
    rpc('update', 'update', 'name-description', 'updateProject', {'project_id': Ref('edit'), 'name': 'Edited',
                                                                  'description': 'New description'})
    rpc('update', 'update', 'name-description-read', 'getProjectById', [Ref('edit')],
        after=['rpc.update.update.name-description'])
    rpc('update', 'update', 'identifier-lower', 'updateProject', {'project_id': Ref('edit'), 'identifier': 'edit2'})
    rpc('update', 'update', 'identifier-read', 'getProjectByIdentifier', ['EDIT2'],
        after=['rpc.update.update.identifier-lower'])
    rpc('update', 'update', 'same-identifier', 'updateProject', {'project_id': Ref('edit'), 'identifier': 'EDIT2'},
        after=['rpc.update.update.identifier-lower'])
    rpc('update', 'update', 'dates', 'updateProject', {'project_id': Ref('edit'), 'start_date': '2026-06-01',
                                                       'end_date': '2026-09-30'})
    rpc('update', 'update', 'dates-other-format', 'updateProject', {'project_id': Ref('other'),
                                                                    'start_date': '05/17/2026'})
    rpc('update', 'update', 'priorities', 'updateProject', {'project_id': Ref('edit'), 'priority_default': 1,
                                                            'priority_start': 0, 'priority_end': 8})
    rpc('update', 'update', 'email', 'updateProject', {'project_id': Ref('edit'), 'email': 'edited@example.test'})
    rpc('update', 'update', 'owner', 'updateProject', {'project_id': Ref('edit'), 'owner_id': Ref('olive')})
    rpc('update', 'update', 'all-read', 'getProjectById', [Ref('edit')],
        after=['rpc.update.update.dates', 'rpc.update.update.priorities', 'rpc.update.update.email',
               'rpc.update.update.owner', 'rpc.update.update.identifier-lower'])
    rpc('update', 'update', 'other-format-read', 'getProjectById', [Ref('other')],
        after=['rpc.update.update.dates-other-format'])
    rpc('update', 'update', 'positional', 'updateProject', [Ref('other'), 'Other renamed'])
    rpc('update', 'update', 'positional-read', 'getProjectByName', ['Other renamed'],
        after=['rpc.update.update.positional'])
    rpc('update', 'update', 'only-id', 'updateProject', [Ref('other')])
    rpc('update', 'validation', 'duplicate-identifier', 'updateProject', {'project_id': Ref('edit'),
                                                                         'identifier': 'OTHER'})
    rpc('update', 'validation', 'duplicate-email', 'updateProject', {'project_id': Ref('edit'),
                                                                    'email': 'other@example.test'})
    rpc('update', 'validation', 'empty-name', 'updateProject', {'project_id': Ref('edit'), 'name': ''})
    rpc('update', 'validation', 'bad-identifier', 'updateProject', {'project_id': Ref('edit'), 'identifier': 'a b'})
    rpc('update', 'validation', 'unknown-owner', 'updateProject', {'project_id': Ref('edit'), 'owner_id': 987654})
    rpc('update', 'validation', 'unchanged', 'getProjectById', [Ref('edit')],
        after=['rpc.update.update.owner', 'rpc.update.update.email', 'rpc.update.update.dates',
               'rpc.update.update.priorities', 'rpc.update.update.identifier-lower'])
    rpc('update', 'validation', 'missing-project', 'updateProject', {'project_id': 987654, 'name': 'Ghost'},
        actor='app')

    # -- status and public access ----------------------------------------------------------------------------
    fx('status', 'project', 'createProject', {'name': 'Status project'}, save='status')
    rpc('status', 'status', 'disable', 'disableProject', [Ref('status')])
    rpc('status', 'status', 'disabled-read', 'getProjectById', [Ref('status')], after=['rpc.status.status.disable'])
    rpc('status', 'status', 'disabled-in-my-projects', 'getMyProjects', after=['rpc.status.status.disable'])
    rpc('status', 'status', 'disable-again', 'disableProject', [Ref('status')], after=['rpc.status.status.disable'])
    rpc('status', 'status', 'enable', 'enableProject', [Ref('status')], after=['rpc.status.status.disable'])
    rpc('status', 'status', 'enabled-read', 'getProjectById', [Ref('status')], after=['rpc.status.status.enable'])
    rpc('status', 'status', 'enable-missing', 'enableProject', [987654], actor='app')
    rpc('status', 'status', 'disable-missing', 'disableProject', [987654], actor='app')
    rpc('status', 'public', 'enable-public', 'enableProjectPublicAccess', [Ref('status')])
    rpc('status', 'public', 'public-read', 'getProjectById', [Ref('status')],
        after=['rpc.status.public.enable-public'])
    rpc('status', 'public', 'disable-public', 'disableProjectPublicAccess', [Ref('status')],
        after=['rpc.status.public.enable-public'])
    rpc('status', 'public', 'private-read', 'getProjectById', [Ref('status')],
        after=['rpc.status.public.disable-public'])
    rpc('status', 'public', 'enable-public-missing', 'enableProjectPublicAccess', [987654], actor='app')

    # -- personal projects ---------------------------------------------------------------------------------
    rpc('personal', 'personal', 'create', 'createMyPrivateProject', ['My notes', 'Only for me'], actor='olive',
        save='mine')
    rpc('personal', 'personal', 'read', 'getProjectById', [Ref('mine')], actor='olive')
    rpc('personal', 'personal', 'owner-role', 'getProjectUserRole', [Ref('mine'), Ref('olive')], actor='olive')
    rpc('personal', 'personal', 'my-projects', 'getMyProjects', actor='olive', after=['rpc.personal.personal.create'])
    rpc('personal', 'personal', 'my-projects-list', 'getMyProjectsList', actor='olive',
        after=['rpc.personal.personal.create'])
    rpc('personal', 'personal', 'admin-not-member', 'getProjectById', [Ref('mine')],
        requires=['rpc.personal.personal.read'])
    rpc('personal', 'personal', 'empty-name', 'createMyPrivateProject', [''], actor='olive')
    rpc('personal', 'personal', 'named-params', 'createMyPrivateProject', {'name': 'Second notes'}, actor='olive',
        save='mine2')
    rpc('personal', 'personal', 'not-in-shared-list', 'getAllProjects', actor='app',
        project=names_present({'My notes', 'Second notes'}, 'Plain project'),
        after=['rpc.personal.personal.named-params'],
        describe='getAllProjects as app after personal projects were created (are they listed)')

    # -- removal --------------------------------------------------------------------------------------------
    fx('remove', 'project', 'createProject', {'name': 'Doomed project'}, save='doomed')
    fx('remove', 'task', 'createTask', {'title': 'Doomed task', 'project_id': Ref('doomed')}, save='doomed-task')
    fx('remove', 'file', 'createProjectFile', [Ref('doomed'), 'doomed.txt', b64('doomed file')], save='doomed-file')
    rpc('remove', 'remove', 'remove', 'removeProject', [Ref('doomed')])
    rpc('remove', 'remove', 'project-gone', 'getProjectById', [Ref('doomed')], actor='app',
        after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'task-gone', 'getTask', [Ref('doomed-task')], actor='app', after=['rpc.remove.remove.remove'])
    rpc('remove', 'remove', 'not-listed', 'getMyProjectsList', project=names_present({'Doomed project'}, 'Plain project'),
        after=['rpc.remove.remove.remove'], describe='getMyProjectsList as admin after the removal (is it listed)')
    rpc('remove', 'remove', 'remove-again', 'removeProject', [Ref('doomed')], actor='app',
        after=['rpc.remove.remove.remove'])

    # -- project metadata ---------------------------------------------------------------------------------
    fx('metadata', 'project', 'createProject', {'name': 'Meta project'}, save='meta')
    rpc('metadata', 'metadata', 'empty', 'getProjectMetadata', [Ref('meta')])
    rpc('metadata', 'metadata', 'save', 'saveProjectMetadata', [Ref('meta'), {'zeta': 'last', 'alpha': 'first',
                                                                              'note': 'Ünïcode ✓'}])
    rpc('metadata', 'metadata', 'all-sorted', 'getProjectMetadata', [Ref('meta')],
        after=['rpc.metadata.metadata.save'])
    rpc('metadata', 'metadata', 'by-name', 'getProjectMetadataByName', [Ref('meta'), 'note'],
        after=['rpc.metadata.metadata.save'])
    rpc('metadata', 'metadata', 'by-name-missing', 'getProjectMetadataByName', [Ref('meta'), 'missing'],
        requires=['rpc.metadata.metadata.by-name'])
    rpc('metadata', 'metadata', 'overwrite', 'saveProjectMetadata', [Ref('meta'), {'alpha': 'changed'}],
        after=['rpc.metadata.metadata.save'])
    rpc('metadata', 'metadata', 'overwrite-read', 'getProjectMetadata', [Ref('meta')],
        after=['rpc.metadata.metadata.overwrite'])
    rpc('metadata', 'metadata', 'numeric-value', 'saveProjectMetadata', [Ref('meta'), {'count': 42}])
    rpc('metadata', 'metadata', 'numeric-value-read', 'getProjectMetadataByName', [Ref('meta'), 'count'],
        after=['rpc.metadata.metadata.numeric-value'])
    rpc('metadata', 'metadata', 'remove', 'removeProjectMetadata', [Ref('meta'), 'zeta'],
        after=['rpc.metadata.metadata.save'])
    rpc('metadata', 'metadata', 'removed-read', 'getProjectMetadata', [Ref('meta')],
        after=['rpc.metadata.metadata.remove', 'rpc.metadata.metadata.overwrite',
               'rpc.metadata.metadata.numeric-value'])
    rpc('metadata', 'metadata', 'remove-missing', 'removeProjectMetadata', [Ref('meta'), 'never-there'])
    rpc('metadata', 'metadata', 'empty-save', 'saveProjectMetadata', [Ref('meta'), {}])
    rpc('metadata', 'metadata', 'list-values', 'saveProjectMetadata', [Ref('meta'), ['first', 'second']])
    rpc('metadata', 'metadata', 'list-values-read', 'getProjectMetadata', [Ref('meta')],
        after=['rpc.metadata.metadata.list-values', 'rpc.metadata.metadata.remove'])

    # -- project files --------------------------------------------------------------------------------------
    fx('files', 'project', 'createProject', {'name': 'File project'}, save='fp')
    fx('files', 'member', 'addProjectUser', [Ref('fp'), Ref('olive'), 'project-member'])
    fx('files', 'stranger', 'createUser', {'username': 'stan', 'password': PASSWORD}, save='stan')
    rpc('files', 'files', 'none', 'getAllProjectFiles', [Ref('fp')])
    rpc('files', 'files', 'create-text', 'createProjectFile', [Ref('fp'), 'notes.txt', b64('Project notes\n')],
        save='f-text')
    rpc('files', 'files', 'create-image', 'createProjectFile', [Ref('fp'), 'pixel.png', b64(png(3, 2))], save='f-png')
    rpc('files', 'files', 'create-unicode-name', 'createProjectFile', [Ref('fp'), 'Résumé été.md', b64('# Été\n')],
        save='f-unicode')
    rpc('files', 'files', 'create-with-creator', 'createProjectFile', [Ref('fp'), 'by-olive.txt', b64('olive'),
                                                                       Ref('olive')], actor='app', save='f-olive')
    rpc('files', 'files', 'create-creator-not-member', 'createProjectFile', [Ref('fp'), 'not-member.txt', b64('x'),
                                                                            Ref('stan')], actor='app',
        requires=['rpc.files.files.create-with-creator'])
    rpc('files', 'files', 'list-sorted', 'getAllProjectFiles', [Ref('fp')],
        after=['rpc.files.files.create-text', 'rpc.files.files.create-image', 'rpc.files.files.create-unicode-name',
               'rpc.files.files.create-with-creator'])
    rpc('files', 'files', 'read-text', 'getProjectFile', [Ref('fp'), Ref('f-text')])
    rpc('files', 'files', 'read-image', 'getProjectFile', [Ref('fp'), Ref('f-png')])
    rpc('files', 'files', 'download-text', 'downloadProjectFile', [Ref('fp'), Ref('f-text')])
    rpc('files', 'files', 'download-image', 'downloadProjectFile', [Ref('fp'), Ref('f-png')])
    rpc('files', 'files', 'download-unicode', 'downloadProjectFile', [Ref('fp'), Ref('f-unicode')])
    rpc('files', 'files', 'read-missing', 'getProjectFile', [Ref('fp'), 987654], requires=['rpc.files.files.read-text'])
    rpc('files', 'files', 'download-missing', 'downloadProjectFile', [Ref('fp'), 987654],
        requires=['rpc.files.files.download-text'])
    rpc('files', 'files', 'empty-content', 'createProjectFile', [Ref('fp'), 'empty.txt', ''])
    rpc('files', 'files', 'remove', 'removeProjectFile', [Ref('fp'), Ref('f-text')],
        after=['rpc.files.files.download-text'])
    rpc('files', 'files', 'removed-read', 'getProjectFile', [Ref('fp'), Ref('f-text')],
        after=['rpc.files.files.remove'], requires=['rpc.files.files.read-text'])
    rpc('files', 'files', 'remove-again', 'removeProjectFile', [Ref('fp'), Ref('f-text')],
        after=['rpc.files.files.remove'])
    rpc('files', 'files', 'after-remove-list', 'getAllProjectFiles', [Ref('fp')], after=['rpc.files.files.remove'])
    rpc('files', 'files', 'remove-all', 'removeAllProjectFiles', [Ref('fp')], after=['rpc.files.files.after-remove-list'])
    rpc('files', 'files', 'after-remove-all', 'getAllProjectFiles', [Ref('fp')], after=['rpc.files.files.remove-all'],
        requires=['rpc.files.files.list-sorted'])
    rpc('files', 'files', 'remove-all-empty', 'removeAllProjectFiles', [Ref('fp')], after=['rpc.files.files.remove-all'])

    # -- activity -------------------------------------------------------------------------------------------
    fx('activity', 'project', 'createProject', {'name': 'Busy project'}, save='busy')
    fx('activity', 'project2', 'createProject', {'name': 'Quiet project'}, save='quiet')
    rpc('activity', 'activity', 'none', 'getProjectActivity', [Ref('busy')], project=events)
    rpc('activity', 'activity', 'task-created', 'createTask', {'title': 'Busy task', 'project_id': Ref('busy')},
        save='busy-task')
    rpc('activity', 'activity', 'task-updated', 'updateTask', {'id': Ref('busy-task'), 'title': 'Busy task edited'})
    rpc('activity', 'activity', 'task-closed', 'closeTask', [Ref('busy-task')], after=['rpc.activity.activity.task-updated'])
    rpc('activity', 'activity', 'comment-created', 'createComment', {'task_id': Ref('busy-task'),
                                                                     'user_id': Ref('admin', 'id'),
                                                                     'content': 'Busy comment'})
    rpc('activity', 'activity', 'other-project-task', 'createTask', {'title': 'Quiet task', 'project_id': Ref('quiet')})
    rpc('activity', 'activity', 'stream', 'getProjectActivity', [Ref('busy')], project=events,
        after=['rpc.activity.activity.task-closed', 'rpc.activity.activity.comment-created'])
    rpc('activity', 'activity', 'both-projects', 'getProjectActivities', [[Ref('busy'), Ref('quiet')]], project=events,
        after=['rpc.activity.activity.stream', 'rpc.activity.activity.other-project-task'])
    rpc('activity', 'activity', 'named-ids', 'getProjectActivities', {'project_ids': [Ref('quiet')]}, project=events,
        after=['rpc.activity.activity.other-project-task'])
    rpc('activity', 'activity', 'my-stream', 'getMyActivityStream', project=events,
        after=['rpc.activity.activity.both-projects'])
