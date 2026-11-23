"""Reviewed user goals, acceptance conditions, public setup and program checks of the GUI episodes.

Reference recipes implement these specifications. Goals are authored here and are never produced by translating a
recorded click trace. Setup items are unscored public preparation through the JSON-RPC API with ids (any successful
answer); every checkpoint of a GUI episode needs them. A point that only verifies a refusal or an unavailable view
names, in `requires`, a positive point of the same episode that proves the feature exists.
"""
import base64
import json

from harness import ADMIN, png

ADMIN_PASSWORD = 'admin'
PASSWORD = 'Kanboard-Pass-2026'
USERS = {'bob': ('Bob Builder', 'bob@example.test'), 'carol': ('Carol Viewer', 'carol@example.test')}


def api(name, method, params=None, actor='app', save=None):
    return {'id': name, 'method': method, 'params': params, 'actor': actor, 'save': save}


def user(name, role='app-user'):
    full, email = USERS[name]
    return api('user-' + name, 'createUser', {'username': name, 'password': PASSWORD, 'name': full, 'email': email,
                                              'role': role}, save=name)


def project(name='Website', key='p', identifier=None):
    params = {'name': name, 'owner_id': '{{admin.id}}'}
    if identifier:
        params['identifier'] = identifier
    return [api('project-' + key, 'createProject', params, save=key),
            api('project-' + key + '-admin', 'addProjectUser', ['{{' + key + '}}', '{{admin.id}}', 'project-manager']),
            api('project-' + key + '-columns', 'getColumns', ['{{' + key + '}}'], save=key + '-columns'),
            api('project-' + key + '-lanes', 'getAllSwimlanes', ['{{' + key + '}}'], save=key + '-lanes')]


def task(key, title, project_key='p', **fields):
    return api('task-' + key, 'createTask', {'title': title, 'project_id': '{{' + project_key + '}}', **fields},
               actor=ADMIN, save=key)


def read(method, params, *, fields=(), expected=None, where=None, actor='app', derive=(), description=None,
         refused=None, collection=False, status=None, save=None, feeds=False, present=()):
    """A program check of public state through the API: the projected fields of the answer (or of the one record
    matching where), optionally with derived names (column, swimlane, owner, category, creator, tags, project)."""
    check = {'method': method, 'params': params, 'fields': list(fields), 'expected': expected, 'where': where,
             'actor': actor, 'derive': list(derive), 'collection': collection}
    if refused is not None:
        check['refused'] = refused
    if status is not None:
        check['status'] = status
    if description:
        check['description'] = description
    if save:
        check['save'] = save
    if feeds:
        check['user_feeds'] = True
    if present:
        # Opaque values (generated file names) are observed only as set or not set.
        check['present'] = list(present)
    return check


def text_value(value):
    """Render an exact text input unambiguously for the evaluator."""
    if '\n' not in value:
        return '"' + value + '"'
    ending = ' It ends with a line break.' if value.endswith('\n') else ''
    return ('exactly the lines between the ``` fences (the line breaks are part of the text).' + ending + '\n```\n'
            + value.removesuffix('\n') + '\n```\n')


def step(key, goal, acceptance, recipe, checks=(), depends=(), requires=(), lifecycle=None, prepare=()):
    value = {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': recipe, 'checks': list(checks),
             'depends_on': list(depends), 'requires': list(requires)}
    if lifecycle:
        value['lifecycle'] = lifecycle
    if prepare:
        # Unscored API calls the framework makes right before this checkpoint (other users' actions).
        value['prepare'] = list(prepare)
    return value


def episode(key, feature, setup, steps, actor=ADMIN, inputs=None, files=None, extra_tokens=0):
    setup = [api('admin', 'getUserByName', ['admin'], save='admin')] + setup
    ids = [item['id'] for item in setup]
    for cp in steps:
        cp['assertions'] = [{'id': key + '/' + cp['id'] + '/visible', 'channel': 'frontend', 'method': 'agent',
                             'requirement': cp.pop('acceptance')}]
        for i, check in enumerate(cp.pop('checks')):
            cp['assertions'].append({'id': key + '/' + cp['id'] + f'/state-{i + 1}', 'channel': 'backend',
                                     'method': 'program', 'check': check,
                                     'requirement': check.get('description', 'The independently read public '
                                                              'product state matches the requested checkpoint.')})
        bound = [key + '/' + x for x in cp.pop('requires')]
        if bound:
            cp['assertions'][0]['requires'] = bound
        cp['depends_on'] = ['setup:' + i for i in ids] + cp['depends_on']
    credentials = {}
    if actor == ADMIN:
        credentials = {ADMIN: ADMIN_PASSWORD}
    elif actor:
        credentials = {actor: PASSWORD}
    session = ('Sign in with the supplied account before the first goal; this is unscored preparation.' if actor
               else 'Start unauthenticated. Only sign in when a checkpoint explicitly asks you to.')
    value = {'id': key, 'feature': feature, 'execution': 'gui',
             'initial_state': 'Fresh application process and empty DATA_DIR with the initial administrator; the '
                              'listed public setup is then applied through the JSON-RPC API.',
             'setup': setup, 'inputs': {'account': actor, 'credentials': credentials, **(inputs or {})},
             'actor': actor, 'session': session,
             'allowed_equivalents': ['Different visible labels, page layouts, inline or dialog forms, menus and '
                                     'ordinary navigation routes are valid.',
                                     'Known product page URLs may be entered in the browser; no API browsing.'],
             'forbidden_bypasses': ['Do not use APIs, developer tools, source, private files, or hidden application '
                                    'state to perform GUI goals.', 'Do not manually recreate a missing product '
                                    'command.'],
             'budget': {'calls': min(160, 45 + 25 * len(steps)), 'seconds': min(1800, 480 + 180 * len(steps)),
                        'tokens': min(1_500_000, 350_000 + 180_000 * len(steps) + extra_tokens)},
             'checkpoints': steps}
    for cp in steps:
        if any('csv' in (a.get('check') or {}) for a in cp['assertions']):
            cp['download'] = True
    if files:
        value['files'] = files
    # The manifest is JSON: actor tuples become lists, as the frozen copy reads them back.
    return json.loads(json.dumps(value))


def build():
    episodes = []

    def add(*a, **kw):
        episodes.append(episode(*a, **kw))

    # -- authentication ---------------------------------------------------------------------------------------
    add('login-valid', 'authentication', [], [
        step('session', f'Use the sign-in page /login. Sign in with username "admin" and password '
                        f'"{ADMIN_PASSWORD}".',
             'The sign-in succeeds: a signed-in page (the dashboard) is shown and identifies the account admin.',
             [{'op': 'sign-in', 'user': ADMIN, 'password': ADMIN_PASSWORD}]),
        step('last-logins', 'Open the list of your last logins in your profile.',
             'The list shows your sign-in of today through the sign-in form (authentication method Database).',
             [{'op': 'goto', 'path': '/user/show/{{admin.id}}/last-logins'}, {'op': 'wait-text', 'texts': ['Database']}],
             depends=['session']),
        step('persistent', 'Open the list of your persistent connections in your profile.',
             'The list shows the persistent connection of this browser with its creation and expiration dates.',
             [{'op': 'goto', 'path': '/user/show/{{admin.id}}/sessions'}, {'op': 'wait-text', 'texts': ['06/13/2026']}],
             depends=['session'])], actor=None)
    add('login-invalid', 'authentication', [], [
        step('session', 'Use the sign-in page /login. Sign in with username "admin" and password '
                        '"Wrong-Password-1".',
             'The sign-in is refused: the sign-in form is shown again with an error about the credentials, and no '
             'signed-in page is shown.',
             [{'op': 'sign-in-fail', 'user': ADMIN, 'password': 'Wrong-Password-1'}], requires=['retry/visible']),
        step('retry', f'Now sign in with username "admin" and the right password "{ADMIN_PASSWORD}".',
             'The sign-in succeeds: the dashboard of the account admin is shown.',
             [{'op': 'sign-in', 'user': ADMIN, 'password': ADMIN_PASSWORD}])], actor=None)
    add('logout', 'authentication', [], [
        step('signed-in', 'Open your dashboard.',
             'The dashboard of the signed-in account admin is shown.',
             [{'op': 'goto', 'path': '/dashboard'}, {'op': 'wait-text', 'texts': ['Dashboard for admin']}]),
        step('signed-out', 'Sign out through the account menu at the top right of any page, then open /dashboard.',
             'After signing out, opening the dashboard shows the sign-in form instead of the dashboard.',
             [{'op': 'sign-out-menu'}, {'op': 'goto', 'path': '/dashboard'}], depends=['signed-in'],
             requires=['signed-in/visible'])])

    # -- projects ---------------------------------------------------------------------------------------------
    add('project-create', 'projects', [], [
        step('created', 'Create a new team project named "Website Redesign" with the identifier "WEB" from the '
                        'dashboard\'s New project link.',
             'The new project opens (its board or overview) and is titled Website Redesign, with the default columns '
             'Backlog, Ready, Work in progress and Done.',
             [{'op': 'goto', 'path': '/project/create'}, {'op': 'fill', 'field': 'name', 'value': 'Website Redesign'},
              {'op': 'fill', 'field': 'identifier', 'value': 'WEB'}, {'op': 'save'},
              {'op': 'wait-text', 'texts': ['Website Redesign']}],
             [read('getProjectByName', ['Website Redesign'], fields=['name', 'identifier', 'is_private', 'is_active'],
                   expected={'name': 'Website Redesign', 'identifier': 'WEB', 'is_private': 0, 'is_active': 1},
                   save='created'),
              read('getColumns', ['{{created.id}}'], fields=['title', 'position'], collection=True,
                   expected=[{'title': 'Backlog', 'position': 1}, {'title': 'Ready', 'position': 2},
                             {'title': 'Work in progress', 'position': 3}, {'title': 'Done', 'position': 4}])]),
        step('edited', 'In the settings of Website Redesign, edit the project: set the description to "Public site '
                       'overhaul" and the email to "web@example.test", then save.',
             'The project settings show the saved description Public site overhaul and the email '
             'web@example.test.',
             [{'op': 'goto', 'path': '/project/{{created.id}}/edit'},
              {'op': 'fill', 'field': 'description', 'value': 'Public site overhaul'},
              {'op': 'fill', 'field': 'email', 'value': 'web@example.test'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getProjectByName', 'params': ['Website Redesign'],
               'expect': {'email': 'web@example.test'}}, {'op': 'goto', 'path': '/project/{{created.id}}/edit'}],
             [read('getProjectByName', ['Website Redesign'], fields=['description', 'email'],
                   expected={'description': 'Public site overhaul', 'email': 'web@example.test'})],
             depends=['created'])])
    add('project-personal', 'projects', [], [
        step('created', 'Create a new personal project named "Private Notes" from the dashboard\'s New personal '
                        'project link.',
             'The new project Private Notes opens; it is a personal project.',
             [{'op': 'goto', 'path': '/project/create/personal'},
              {'op': 'fill', 'field': 'name', 'value': 'Private Notes'}, {'op': 'save'},
              {'op': 'wait-text', 'texts': ['Private Notes']}],
             [read('getProjectByName', ['Private Notes'], fields=['name', 'is_private'],
                   expected={'name': 'Private Notes', 'is_private': 1})])])
    add('project-close-reopen', 'projects', project('Seasonal Campaign'), [
        step('closed', 'Close the project Seasonal Campaign from its settings (Close this project) and confirm.',
             'The project is shown as closed (inactive), for example in the project list or its summary.',
             [{'op': 'goto', 'path': '/project/{{p}}'}, {'op': 'click', 'names': ['Close this project']},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']}, {'op': 'goto', 'path': '/projects'},
              {'op': 'wait-text', 'texts': ['Seasonal Campaign']}],
             [read('getProjectById', ['{{p}}'], fields=['is_active'], expected={'is_active': 0})]),
        step('reopened', 'Reopen the project Seasonal Campaign from its settings and confirm.',
             'The project is shown as open (active) again.',
             [{'op': 'goto', 'path': '/project/{{p}}'}, {'op': 'click', 'names': ['Open this project']},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']}, {'op': 'goto', 'path': '/project/{{p}}'}],
             [read('getProjectById', ['{{p}}'], fields=['is_active'], expected={'is_active': 1})],
             depends=['closed'])])
    add('project-public', 'projects', project('Open Roadmap') + [task('t1', 'Publish roadmap')], [
        step('enabled', 'Enable public access for the project Open Roadmap in its settings (Public access).',
             'The public access settings show that the project is public and offer its public board link and feed '
             'links.',
             [{'op': 'goto', 'path': '/project/{{p}}/share'}, {'op': 'click', 'names': ['Enable public access']},
              {'op': 'wait-text', 'texts': ['Disable public access']}],
             [read('getProjectById', ['{{p}}'], fields=['is_public'], expected={'is_public': 1})]),
        step('public-board', 'Open the public board link shown in those settings.',
             'A read-only public board of Open Roadmap is shown, with the task Publish roadmap in Backlog.',
             [{'op': 'public-board'}], depends=['enabled']),
        step('public-task', 'On the public board, open the task Publish roadmap.',
             'A read-only page of the task Publish roadmap is shown (its column Backlog, no editing actions) with a way '
             'back to the public board.',
             [{'op': 'click', 'names': ['Publish roadmap'], 'tags': ['a']},
              {'op': 'wait-text', 'texts': ['Back to the board']}], depends=['public-board']),
        step('disabled', 'Go back to the project settings and disable public access.',
             'The public access settings show that the project is no longer public.',
             [{'op': 'goto', 'path': '/project/{{p}}/share'}, {'op': 'click', 'names': ['Disable public access']},
              {'op': 'wait-text', 'texts': ['Enable public access']}],
             [read('getProjectById', ['{{p}}'], fields=['is_public', 'token'], expected={'is_public': 0, 'token': ''})],
             depends=['enabled'])])
    add('project-remove', 'projects', project('Obsolete Project') + project('Keep Project', 'k'), [
        step('removed', 'Remove the project Obsolete Project from its settings and confirm the removal.',
             'Obsolete Project no longer appears in the project list; Keep Project is still listed.',
             [{'op': 'goto', 'path': '/project/{{p}}'}, {'op': 'click', 'names': ['Remove']},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']}, {'op': 'goto', 'path': '/projects'},
              {'op': 'wait-text', 'texts': ['Keep Project']}],
             [read('getProjectByName', ['Keep Project'], fields=['name'], expected={'name': 'Keep Project'},
                   refused={'method': 'getProjectByName', 'params': ['Obsolete Project'], 'actor': 'app'},
                   description='Keep Project still exists and Obsolete Project is gone.')])])
    add('project-duplicate', 'projects', project('Template Board') + [
            api('col', 'addColumn', ['{{p}}', 'Review']),
            api('cat', 'createCategory', ['{{p}}', 'Design', 'blue']),
            task('t1', 'Template task')], [
        step('duplicated', 'Duplicate the project Template Board from its settings (Duplicate), keeping the default '
                           'options, and open the new copy.',
             'A new project named after Template Board (marked as a clone or copy) exists and its board shows the same '
             'columns, including Review.',
             [{'op': 'goto', 'path': '/project/{{p}}/duplicate'}, {'op': 'save', 'names': ['Duplicate']},
              {'op': 'wait-text', 'texts': ['Review']}],
             [read('getAllProjects', None, fields=['name'], collection=True,
                   description='The project list contains the original and its copy.'),
              read('getAllCategories', ['{{p}}'], fields=['name'], collection=True, expected=[{'name': 'Design'}])])])

    # -- tasks on the board -------------------------------------------------------------------------------------
    add('task-create', 'tasks', project('Website') + [user('bob'),
            api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member'])], [
        step('created', 'On the board of the project Website, add a new task in the Ready column with the title '
                        '"Write release notes", the description ' + text_value('Summarize **all** changes\n\n- API\n'
                                                                              '- UI') + 'colour Green, assignee bob, '
                        'priority 2 and complexity 5.',
             'The board shows the task Write release notes in the Ready column with its details (assignee bob).',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'new-task', 'column': 1},
              {'op': 'fill', 'field': 'title', 'value': 'Write release notes'},
              {'op': 'fill', 'field': 'description', 'value': 'Summarize **all** changes\n\n- API\n- UI'},
              {'op': 'select', 'field': 'color_id', 'value': 'Green'}, {'op': 'select', 'field': 'owner_id',
                                                                        'value': 'Bob Builder'},
              {'op': 'select', 'field': 'priority', 'value': '2'}, {'op': 'fill', 'field': 'score', 'value': '5'},
              {'op': 'save'}, {'op': 'wait-text', 'texts': ['Write release notes']}],
             [read('getAllTasks', ['{{p}}', 1], where={'title': 'Write release notes'},
                   fields=['title', 'description', 'color_id', 'priority', 'score'], derive=['column', 'owner'],
                   expected={'title': 'Write release notes', 'description': 'Summarize **all** changes\n\n- API\n- UI',
                             'color_id': 'green', 'priority': 2, 'score': 5, 'column': 'Ready', 'owner': 'bob'})]),
        step('viewed', 'Open the task Write release notes.',
             'The task page shows the title, the assignee bob, the column Ready, and the description rendered as '
             'formatted text (bold "all" and a two-item list) rather than raw Markdown.',
             [{'op': 'click', 'names': ['Write release notes'], 'tags': ['a']}, {'op': 'wait-text', 'texts': ['UI']}],
             depends=['created'])])
    add('task-edit', 'tasks', project('Website') + [user('bob'),
            api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member']),
            api('cat', 'createCategory', ['{{p}}', 'Bug', 'red']),
            task('t1', 'Fix login form', description='Initial description')], [
        step('edited', 'Edit the task Fix login form (project Website): change its title to "Fix login form '
                       'validation", set the category Bug, assignee bob, due date 2026-04-30, reference "BUG-17" and '
                       'add the tag "frontend". Save.',
             'The task shows the new title, the category Bug, the assignee bob, the due date April 30 2026, the '
             'reference BUG-17 and the tag frontend.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Edit the task']},
              {'op': 'fill', 'field': 'title', 'value': 'Fix login form validation'},
              {'op': 'select', 'field': 'category_id', 'value': 'Bug'},
              {'op': 'select', 'field': 'owner_id', 'value': 'Bob Builder'},
              {'op': 'fill', 'field': 'date_due', 'value': '04/30/2026'},
              {'op': 'fill', 'field': 'reference', 'value': 'BUG-17'}, {'op': 'tag', 'value': 'frontend'},
              {'op': 'save'}, {'op': 'wait-text', 'texts': ['Fix login form validation']}],
             [read('getTask', ['{{t1}}'], fields=['title', 'reference', 'description', 'date_due'],
                   derive=['category', 'owner', 'tags'],
                   expected={'title': 'Fix login form validation', 'reference': 'BUG-17',
                             'description': 'Initial description', 'date_due': '2026-04-30', 'category': 'Bug',
                             'owner': 'bob', 'tags': ['frontend']})])])
    add('task-move', 'tasks', project('Website') + [task('t1', 'Design mockups'), task('t2', 'Stay in backlog')], [
        step('moved', 'On the board of the project Website, move the task Design mockups from Backlog to the Work in '
                      'progress column (for example by dragging its card).',
             'The board shows Design mockups in the Work in progress column; Stay in backlog remains in Backlog.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'drag', 'task': 'Design mockups',
                                                       'column': 'Work in progress'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'],
               'expect': {'column_id': '{{p-columns.2.id}}'}}, {'op': 'reload'}],
             [read('getTask', ['{{t1}}'], derive=['column'], expected={'column': 'Work in progress'}),
              read('getTask', ['{{t2}}'], derive=['column'], expected={'column': 'Backlog'})]),
        step('done', 'Move the same task on to the Done column.',
             'The board shows Design mockups in the Done column.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'drag', 'task': 'Design mockups', 'column': 'Done'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'],
               'expect': {'column_id': '{{p-columns.3.id}}'}}, {'op': 'reload'}],
             [read('getTask', ['{{t1}}'], fields=['is_active'], derive=['column'],
                   expected={'column': 'Done', 'is_active': 1})], depends=['moved']),
        step('transitions', 'Open the task Design mockups and show its transitions (the history of its column moves).',
             'The transitions list the move from Backlog to Work in progress and the move from Work in progress to '
             'Done, both executed by admin.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Transitions'], 'tags': ['a']},
              {'op': 'wait-text', 'texts': ['Destination column']}], depends=['done'])])
    add('bulk-move', 'tasks', project('Website') + [user('bob'),
            api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member']),
            task('t1', 'Alpha item'), task('t2', 'Beta item'), task('t3', 'Gamma item')], [
        step('moved', 'In the list view of the project Website, select the tasks Alpha item and Beta item and move both '
                      'at once to the column Done.',
             'The list (or the board) shows Alpha item and Beta item in Done; Gamma item stays in Backlog.',
             [{'op': 'goto', 'path': '/list/{{p}}'}, {'op': 'check-value', 'field': 'tasks[]', 'value': '{{t1}}'},
              {'op': 'check-value', 'field': 'tasks[]', 'value': '{{t2}}'},
              {'op': 'click', 'names': ['Apply action'], 'tags': ['a']},
              {'op': 'click', 'names': ['Move selected tasks to another column or swimlane'], 'tags': ['a']},
              {'op': 'select', 'field': 'column_id', 'value': 'Done'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t2}}'],
               'expect': {'column_id': '{{p-columns.3.id}}'}}, {'op': 'goto', 'path': '/list/{{p}}'}],
             [read('getAllTasks', ['{{p}}', 1], fields=['title'], derive=['column'], collection=True,
                   expected=[{'title': 'Alpha item', 'column': 'Done'}, {'title': 'Beta item', 'column': 'Done'},
                             {'title': 'Gamma item', 'column': 'Backlog'}])]),
        step('bulk-edit', 'In the list view, select the tasks Beta item and Gamma item and edit both at once: colour '
                          'Green and assignee bob.',
             'The list shows Beta item and Gamma item in green and assigned to bob; Alpha item is unchanged.',
             [{'op': 'goto', 'path': '/list/{{p}}'}, {'op': 'check-value', 'field': 'tasks[]', 'value': '{{t2}}'},
              {'op': 'check-value', 'field': 'tasks[]', 'value': '{{t3}}'},
              {'op': 'click', 'names': ['Apply action'], 'tags': ['a']},
              {'op': 'click', 'names': ['Edit tasks in bulk'], 'tags': ['a']},
              {'op': 'check', 'field': 'change_color', 'value': True},
              {'op': 'select', 'field': 'color_id', 'value': 'Green'},
              {'op': 'check', 'field': 'change_assignee', 'value': True},
              {'op': 'select', 'field': 'owner_id', 'value': 'Bob Builder'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t3}}'], 'expect': {'owner_id': '{{bob}}'}},
              {'op': 'goto', 'path': '/list/{{p}}'}],
             [read('getAllTasks', ['{{p}}', 1], fields=['title', 'color_id'], derive=['owner'], collection=True,
                   expected=[{'title': 'Alpha item', 'color_id': 'yellow', 'owner': None},
                             {'title': 'Beta item', 'color_id': 'green', 'owner': 'bob'},
                             {'title': 'Gamma item', 'color_id': 'green', 'owner': 'bob'}])], depends=['moved'])])
    add('task-position', 'tasks', project('Website') + [task('t1', 'Reorder me'), task('t2', 'Neighbour')], [
        step('moved', 'Open the task Reorder me (project Website) and use its Move position action to place it in the '
                      'column Ready.',
             'The task is shown in the Ready column.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Move position']},
              {'op': 'select-label', 'label': 'Column', 'value': 'Ready'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'],
               'expect': {'column_id': '{{p-columns.1.id}}'}}, {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], derive=['column'], expected={'column': 'Ready'})])])
    add('task-close-reopen', 'tasks', project('Website') + [task('t1', 'Ship version 2')], [
        step('closed', 'Close the task Ship version 2 (project Website) and confirm.',
             'The task is shown as closed.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Close this task']},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'], 'expect': {'is_active': 0}},
              {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], fields=['is_active'], expected={'is_active': 0})]),
        step('board', 'Open the board of the project Website.',
             'The closed task Ship version 2 is not shown on the board.',
             [{'op': 'goto', 'path': '/board/{{p}}'}], depends=['closed'], requires=['closed/state-1']),
        step('reopened', 'Reopen the task Ship version 2 and confirm.',
             'The task is shown as open again.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Open this task']},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'], 'expect': {'is_active': 1}},
              {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], fields=['is_active'], expected={'is_active': 1})], depends=['closed'])])
    add('task-remove', 'tasks', project('Website') + [task('t1', 'Delete me'), task('t2', 'Keep me')], [
        step('removed', 'Remove the task Delete me (project Website) and confirm.',
             'The board no longer shows Delete me; Keep me is still on the board.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Remove']},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'], 'expect': {'null': True}},
              {'op': 'goto', 'path': '/board/{{p}}'}],
             [read('getTask', ['{{t2}}'], fields=['title'], expected={'title': 'Keep me'},
                   refused={'method': 'getTask', 'params': ['{{t1}}'], 'actor': 'app'},
                   description='Keep me still exists and Delete me is gone.')])])
    add('task-duplicate-move', 'tasks', project('Website') + project('Mobile App', 'm') + [
            task('t1', 'Shared component'), task('t2', 'Transfer me')], [
        step('duplicated', 'Duplicate the task Shared component within the project Website.',
             'A duplicate of Shared component exists in Website (its title marks it as a duplicate).',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Duplicate']},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']},
              {'op': 'wait-text', 'texts': ['[DUPLICATE] Shared component']}],
             [read('getAllTasks', ['{{p}}', 1], fields=['title'], collection=True,
                   expected=[{'title': '[DUPLICATE] Shared component'}, {'title': 'Shared component'},
                             {'title': 'Transfer me'}])]),
        step('moved', 'Move the task Transfer me to the project Mobile App.',
             'Transfer me now belongs to Mobile App (its page or the Mobile App board shows it).',
             [{'op': 'goto', 'path': '/task/{{t2}}'}, {'op': 'click', 'names': ['Move to project']},
              {'op': 'wait', 'seconds': 1}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t2}}'], 'expect': {'project_id': '{{m}}'}},
              {'op': 'goto', 'path': '/task/{{t2}}'}],
             [read('getTask', ['{{t2}}'], fields=['title'], derive=['project', 'column'],
                   expected={'title': 'Transfer me', 'project': 'Mobile App', 'column': 'Backlog'})])])
    add('subtasks', 'subtasks', project('Website') + [user('bob'),
            api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member']),
            task('t1', 'Prepare launch')], [
        step('added', 'On the task Prepare launch (project Website), add two sub-tasks: "Write announcement" assigned '
                      'to bob, and "Update screenshots".',
             'Both sub-tasks are listed on the task, Write announcement with the assignee bob.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Add a sub-task']},
              {'op': 'fill', 'field': 'title', 'value': 'Write announcement'},
              {'op': 'select', 'field': 'user_id', 'value': 'Bob Builder'}, {'op': 'save'},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Add a sub-task']},
              {'op': 'fill', 'field': 'title', 'value': 'Update screenshots'}, {'op': 'save'},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'wait-text', 'texts': ['Update screenshots']}],
             [read('getTask', ['{{t1}}'], derive=['subtasks'],
                   expected={'subtasks': [['Write announcement', 0, 'bob'], ['Update screenshots', 0, None]]})]),
        step('progress', 'Change the status of the sub-task Write announcement to done.',
             'The sub-task Write announcement is shown as done; Update screenshots is still to do.',
             [{'op': 'subtask-status', 'title': 'Write announcement', 'clicks': 2},
              {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], derive=['subtasks'],
                   expected={'subtasks': [['Write announcement', 2, 'bob'], ['Update screenshots', 0, None]]})],
             depends=['added'])])
    add('subtask-convert', 'subtasks', project('Website') + [task('t1', 'Plan sprint'),
            api('subtask-s1', 'createSubtask', {'task_id': '{{t1}}', 'title': 'Book meeting room'}, save='s1')], [
        step('converted', 'On the task Plan sprint (project Website), convert its sub-task Book meeting room into a task '
                          'of its own.',
             'Book meeting room is now a task on the board of Website.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'menu', 'index': 0, 'item': 'Convert to task'},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']},
              {'op': 'corroborate', 'method': 'getAllSubtasks', 'params': ['{{t1}}'], 'expect': {'equals': []}},
              {'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'wait-text', 'texts': ['Book meeting room']}],
             [read('getAllTasks', ['{{p}}', 1], fields=['title'], derive=['column'], collection=True,
                   expected=[{'title': 'Book meeting room', 'column': 'Backlog'},
                             {'title': 'Plan sprint', 'column': 'Backlog'}]),
              read('getTask', ['{{t1}}'], fields=['title'], derive=['subtasks'],
                   expected={'title': 'Plan sprint', 'subtasks': []})])])
    notes = [api(key, 'createComment', {'task_id': '{{t2}}', 'user_id': '{{admin.id}}', 'content': text})
             for key, text in (('older-note', 'Older note'), ('newer-note', 'Newer note'))]
    add('comments', 'comments', project('Website') + [task('t1', 'Review pull request'), task('t2', 'Plan release')]
        + notes, [
        step('added', 'On the task Review pull request (project Website), add the comment "Looks good, **ship it**".',
             'The comment is listed on the task with its author admin, with "ship it" rendered in bold.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'comment', 'value': 'Looks good, **ship it**'},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'wait-text', 'texts': ['ship it']}],
             [read('getTask', ['{{t1}}'], derive=['comments'],
                   expected={'comments': [['Looks good, **ship it**', 'admin']]})]),
        step('edited', 'Edit that comment so that it reads "Looks good after the fixes".',
             'The task shows the comment with the new text only.',
             [{'op': 'comment-edit', 'value': 'Looks good after the fixes'}, {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], derive=['comments'],
                   expected={'comments': [['Looks good after the fixes', 'admin']]})], depends=['added']),
        step('removed', 'Remove that comment and confirm.',
             'The task no longer lists any comment.',
             [{'op': 'comment-remove'}, {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], derive=['comments'], expected={'comments': []})], depends=['added']),
        step('sorted', 'Open the task Plan release, which has two comments, and change the order of its comments so '
                       'that the newest comment is shown first.',
             'The task Plan release lists its comments newest first: "Newer note" above "Older note".',
             [{'op': 'goto', 'path': '/task/{{t2}}'}, {'op': 'click', 'names': ['Change sorting'], 'tags': ['a']},
              {'op': 'goto', 'path': '/task/{{t2}}'}, {'op': 'wait-text', 'texts': ['Newer note', 'Older note']}])])
    add('task-links', 'links', project('Website') + [task('t1', 'Backend API'), task('t2', 'Frontend screens')], [
        step('internal', 'On the task Backend API (project Website), add an internal link: Backend API blocks the task '
                         'Frontend screens.',
             'Backend API lists Frontend screens under internal links with the relation blocks.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Add internal link']},
              {'op': 'select', 'field': 'link_id', 'value': 'blocks'},
              {'op': 'autocomplete', 'field': 'title', 'value': 'Frontend'}, {'op': 'save'},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'wait-text', 'texts': ['Frontend screens']}],
             [read('getTask', ['{{t1}}'], derive=['links'], expected={'links': [['blocks', 'Frontend screens']]}),
              read('getTask', ['{{t2}}'], derive=['links'], expected={'links': [['is blocked by', 'Backend API']]})]),
        step('opposite', 'Open the task Frontend screens.',
             'Frontend screens lists Backend API under internal links with the opposite relation is blocked by.',
             [{'op': 'goto', 'path': '/task/{{t2}}'}, {'op': 'wait-text', 'texts': ['Backend API']}],
             depends=['internal']),
        step('external', 'On the task Backend API, add an external web link to "https://example.org/api-spec" (link '
                         'type Web Link) and give it the title "API specification".',
             'Backend API lists the external link API specification pointing to https://example.org/api-spec.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Add external link']},
              {'op': 'fill', 'field': 'text', 'value': 'https://example.org/api-spec'},
              {'op': 'select', 'field': 'type', 'value': 'Web Link'}, {'op': 'save'},
              {'op': 'fill', 'field': 'title', 'value': 'API specification'}, {'op': 'save'},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'wait-text', 'texts': ['API specification']}],
             [read('getTask', ['{{t1}}'], derive=['external'],
                   expected={'external': [['API specification', 'https://example.org/api-spec', 'related']]})])])
    add('attachments', 'files', project('Website') + [task('t1', 'Collect feedback')], [
        step('uploaded', 'Attach the input file feedback.txt to the task Collect feedback (project Website).',
             'The task lists the attachment feedback.txt.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Attach a document']},
              {'op': 'attach', 'file': 'feedback.txt'}, {'op': 'goto', 'path': '/task/{{t1}}'},
              {'op': 'wait-text', 'texts': ['feedback.txt']}],
             [read('getTask', ['{{t1}}'], derive=['files'], expected={'files': [['feedback.txt', 38]]})]),
        step('removed', 'Remove that attachment and confirm.',
             'The task no longer lists feedback.txt.',
             [{'op': 'attachment-remove', 'name': 'feedback.txt'}, {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], derive=['files'], expected={'files': []})], depends=['uploaded'])],
        files={'feedback.txt': 'Customers want a darker theme option.\n'})
    add('recurrence', 'tasks', project('Website') + [task('t1', 'Weekly backup check', date_due='2026-04-20 09:00')], [
        step('configured', 'On the task Weekly backup check (project Website), edit the recurrence: generate a '
                           'recurrent task when the task is closed, with a new due date 7 days after the existing due '
                           'date. Save.',
             'The recurrence settings of the task show it as recurrent when closed, 7 days, based on the existing due '
             'date.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Edit recurrence']},
              {'op': 'select', 'field': 'recurrence_status', 'value': 'Yes'},
              {'op': 'select', 'field': 'recurrence_trigger', 'value': 'When task is closed'},
              {'op': 'fill', 'field': 'recurrence_factor', 'value': '7'},
              {'op': 'select', 'field': 'recurrence_timeframe', 'value': 'Day(s)'},
              {'op': 'select', 'field': 'recurrence_basedate', 'value': 'Existing due date'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'], 'expect': {'recurrence_status': 1}},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Edit recurrence']},
              {'op': 'wait', 'seconds': 1}],
             [read('getTask', ['{{t1}}'], fields=['recurrence_status', 'recurrence_trigger', 'recurrence_factor',
                                                 'recurrence_timeframe', 'recurrence_basedate'],
                   expected={'recurrence_status': 1, 'recurrence_trigger': 2, 'recurrence_factor': 7,
                             'recurrence_timeframe': 0, 'recurrence_basedate': 0})]),
        step('closed', 'Close the task Weekly backup check and confirm, then open the board of the project.',
             'The board shows a new open task Weekly backup check (the next occurrence).',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Close this task']},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']},
              {'op': 'corroborate', 'method': 'getAllTasks', 'params': ['{{p}}', 1],
               'expect': {'where': {'title': 'Weekly backup check'}}}, {'op': 'goto', 'path': '/board/{{p}}'}],
             [read('getAllTasks', ['{{p}}', 1], where={'title': 'Weekly backup check'},
                   fields=['date_due', 'recurrence_status'], derive=['column'],
                   expected={'date_due': '2026-04-27', 'recurrence_status': 1, 'column': 'Backlog'})],
             depends=['configured'])])

    # -- board configuration ----------------------------------------------------------------------------------
    add('columns', 'board', project('Website') + [task('t1', 'Existing task')], [
        step('added', 'In the settings of the project Website (Columns), add a new column titled "QA" with a task '
                      'limit of 2 and the description "Quality checks".',
             'The column list shows QA after Done with the task limit 2.',
             [{'op': 'goto', 'path': '/project/{{p}}/columns'}, {'op': 'click', 'names': ['Add a new column']},
              {'op': 'fill', 'field': 'title', 'value': 'QA'}, {'op': 'fill', 'field': 'task_limit', 'value': '2'},
              {'op': 'fill', 'field': 'description', 'value': 'Quality checks'}, {'op': 'save'},
              {'op': 'goto', 'path': '/project/{{p}}/columns'}, {'op': 'wait-text', 'texts': ['QA']}],
             [read('getColumns', ['{{p}}'], fields=['title', 'task_limit', 'description', 'position'],
                   collection=True,
                   expected=[{'title': 'Backlog', 'task_limit': 0, 'description': '', 'position': 1},
                             {'title': 'Done', 'task_limit': 0, 'description': '', 'position': 4},
                             {'title': 'QA', 'task_limit': 2, 'description': 'Quality checks', 'position': 5},
                             {'title': 'Ready', 'task_limit': 0, 'description': '', 'position': 2},
                             {'title': 'Work in progress', 'task_limit': 0, 'description': '', 'position': 3}])]),
        step('renamed', 'Edit the column Ready: rename it to "Selected".',
             'The column list shows Selected instead of Ready.',
             [{'op': 'column-edit', 'column': 'Ready'}, {'op': 'fill', 'field': 'title', 'value': 'Selected'},
              {'op': 'save'}, {'op': 'goto', 'path': '/project/{{p}}/columns'}, {'op': 'wait-text', 'texts': ['Selected']}],
             [read('getColumns', ['{{p}}'], fields=['title'], collection=True,
                   expected=[{'title': 'Backlog'}, {'title': 'Done'}, {'title': 'QA'}, {'title': 'Selected'},
                             {'title': 'Work in progress'}])], depends=['added']),
        step('dashboard-hidden', 'Edit the column Done so that its tasks are hidden on the dashboard.',
             'The column settings of Done show that its tasks are hidden on the dashboard.',
             [{'op': 'column-edit', 'column': 'Done'}, {'op': 'check', 'field': 'hide_in_dashboard', 'value': True},
              {'op': 'save'}, {'op': 'corroborate', 'method': 'getColumns', 'params': ['{{p}}'],
                               'expect': {'where': {'title': 'Done', 'hide_in_dashboard': 1}}},
              {'op': 'column-edit', 'column': 'Done'}],
             [read('getColumns', ['{{p}}'], where={'title': 'Done'}, fields=['title', 'hide_in_dashboard', 'task_limit'],
                   expected={'title': 'Done', 'hide_in_dashboard': 1, 'task_limit': 0})], depends=['added']),
        step('removed', 'Remove the empty column QA and confirm.',
             'QA is no longer listed among the columns.',
             [{'op': 'column-remove', 'column': 'QA'}, {'op': 'goto', 'path': '/project/{{p}}/columns'}],
             [read('getColumns', ['{{p}}'], fields=['title'], collection=True,
                   expected=[{'title': 'Backlog'}, {'title': 'Done'}, {'title': 'Selected'},
                             {'title': 'Work in progress'}])], depends=['added'])])
    add('swimlanes', 'board', project('Website') + [task('t1', 'Urgent fix')], [
        step('added', 'In the settings of the project Website (Swimlanes), add a swimlane named "Expedite" with the '
                      'description "Same-day work".',
             'The swimlane list shows Expedite as active, and the board shows an Expedite swimlane.',
             [{'op': 'goto', 'path': '/project/{{p}}/swimlanes'}, {'op': 'click', 'names': ['Add a new swimlane']},
              {'op': 'fill', 'field': 'name', 'value': 'Expedite'},
              {'op': 'fill', 'field': 'description', 'value': 'Same-day work'}, {'op': 'save'},
              {'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'wait-text', 'texts': ['Expedite']}],
             [read('getAllSwimlanes', ['{{p}}'], fields=['name', 'description', 'is_active', 'position'],
                   collection=True,
                   expected=[{'name': 'Default swimlane', 'description': '', 'is_active': 1, 'position': 1},
                             {'name': 'Expedite', 'description': 'Same-day work', 'is_active': 1, 'position': 2}])]),
        step('moved-task', 'On the board, move the task Urgent fix into the Expedite swimlane (same column) using the '
                           'task\'s Move position action or by dragging it.',
             'The board shows Urgent fix in the Expedite swimlane.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Move position']},
              {'op': 'select-label', 'label': 'Swimlane', 'value': 'Expedite'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'], 'expect': {'position': 1}},
              {'op': 'goto', 'path': '/board/{{p}}'}],
             [read('getTask', ['{{t1}}'], derive=['swimlane', 'column'],
                   expected={'swimlane': 'Expedite', 'column': 'Backlog'})], depends=['added']),
        step('task-limit', 'Edit the swimlane Expedite: give it a task limit of 3.',
             'The swimlane settings show the task limit 3 for Expedite.',
             [{'op': 'swimlane-menu', 'name': 'Expedite', 'item': 'Edit'},
              {'op': 'fill', 'field': 'task_limit', 'value': '3'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getAllSwimlanes', 'params': ['{{p}}'],
               'expect': {'where': {'name': 'Expedite', 'task_limit': 3}}},
              {'op': 'goto', 'path': '/project/{{p}}/swimlanes'}],
             [read('getAllSwimlanes', ['{{p}}'], where={'name': 'Expedite'}, fields=['name', 'task_limit'],
                   expected={'name': 'Expedite', 'task_limit': 3})], depends=['added']),
        step('disabled', 'Disable the swimlane Expedite in the swimlane settings.',
             'The swimlane settings list Expedite among the inactive swimlanes.',
             [{'op': 'swimlane-disable', 'name': 'Expedite'}, {'op': 'goto', 'path': '/project/{{p}}/swimlanes'}],
             [read('getAllSwimlanes', ['{{p}}'], fields=['name', 'is_active'], collection=True,
                   expected=[{'name': 'Default swimlane', 'is_active': 1}, {'name': 'Expedite', 'is_active': 0}])],
             depends=['added'])])
    add('categories', 'board', project('Website') + [task('t1', 'Broken link')], [
        step('added', 'In the settings of the project Website (Categories), add a category named "Defect" with the '
                      'colour Red.',
             'The category list shows Defect.',
             [{'op': 'goto', 'path': '/project/{{p}}/categories'}, {'op': 'click', 'names': ['Add a new category']},
              {'op': 'fill', 'field': 'name', 'value': 'Defect'}, {'op': 'select', 'field': 'color_id', 'value': 'Red'},
              {'op': 'save'}, {'op': 'goto', 'path': '/project/{{p}}/categories'},
              {'op': 'wait-text', 'texts': ['Defect']}],
             [read('getAllCategories', ['{{p}}'], fields=['name', 'color_id'], collection=True,
                   expected=[{'name': 'Defect', 'color_id': 'red'}])]),
        step('assigned', 'Edit the task Broken link and give it the category Defect.',
             'The task Broken link shows the category Defect (on its page or its board card).',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Edit the task']},
              {'op': 'select', 'field': 'category_id', 'value': 'Defect'}, {'op': 'save'},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'wait-text', 'texts': ['Defect']}],
             [read('getTask', ['{{t1}}'], derive=['category'], expected={'category': 'Defect'})],
             depends=['added'])])
    add('project-tags', 'tags', project('Website'), [
        step('added', 'In the settings of the project Website (Tags), add the tags "backend" with the colour Blue and '
                      '"design" without a colour.',
             'The project tag list shows backend and design.',
             [{'op': 'goto', 'path': '/project/{{p}}/tags'}, {'op': 'click', 'names': ['Add new tag']},
              {'op': 'fill', 'field': 'name', 'value': 'backend'}, {'op': 'select', 'field': 'color_id', 'value': 'Blue'},
              {'op': 'save'}, {'op': 'goto', 'path': '/project/{{p}}/tags'}, {'op': 'click', 'names': ['Add new tag']},
              {'op': 'fill', 'field': 'name', 'value': 'design'}, {'op': 'save'},
              {'op': 'goto', 'path': '/project/{{p}}/tags'}, {'op': 'wait-text', 'texts': ['design']}],
             [read('getTagsByProject', ['{{p}}'], fields=['name', 'color_id'], collection=True,
                   expected=[{'name': 'backend', 'color_id': 'blue'}, {'name': 'design', 'color_id': ''}])])])
    add('automatic-action', 'actions', project('Website') + [task('t1', 'Finish documentation')], [
        step('added', 'In the settings of the project Website (Automatic actions), add an automatic action that closes '
                      'a task when it is moved to the column Done (action "Close a task in a specific column", event '
                      '"Move a task to another column", column Done).',
             'The automatic action list shows the new action with its event and the column Done.',
             [{'op': 'goto', 'path': '/project/{{p}}/actions'}, {'op': 'click', 'names': ['Add a new action']},
              {'op': 'select', 'field': 'action_name', 'value': 'Close a task in a specific column'},
              {'op': 'save', 'names': ['Next step']},
              {'op': 'select', 'field': 'event_name', 'value': 'Move a task to another column'},
              {'op': 'save', 'names': ['Next step']},
              {'op': 'select', 'field': 'params[column_id]', 'value': 'Done'}, {'op': 'save'},
              {'op': 'goto', 'path': '/project/{{p}}/actions'}, {'op': 'wait-text', 'texts': ['Done']}],
             [read('getActions', ['{{p}}'], fields=['action_name', 'event_name'], collection=True,
                   expected=[{'action_name': '\\Kanboard\\Action\\TaskCloseColumn',
                              'event_name': 'task.move.column'}])]),
        step('triggered', 'Move the task Finish documentation to the column Done (on the board or with Move position).',
             'Finish documentation is closed automatically: its page shows it closed (in the column Done).',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Move position']},
              {'op': 'select-label', 'label': 'Column', 'value': 'Done'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'], 'expect': {'is_active': 0}},
              {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], fields=['is_active'], derive=['column'],
                   expected={'is_active': 0, 'column': 'Done'})], depends=['added'])])
    add('project-permissions', 'permissions', project('Website') + [user('bob')], [
        step('added', 'In the settings of the project Website (Permissions), allow the user bob as a Project Member.',
             'The permissions page lists bob with the role Project Member.',
             [{'op': 'goto', 'path': '/project/{{p}}/permissions'},
              {'op': 'autocomplete', 'placeholder': 'Enter user name...', 'value': 'bob'},
              {'op': 'select-nth', 'field': 'role', 'nth': 0, 'value': 'Project Member'},
              {'op': 'click', 'names': ['Add'], 'tags': ['button']},
              {'op': 'corroborate', 'method': 'getProjectUserRole', 'params': ['{{p}}', '{{bob}}'],
               'expect': {'equals': 'project-member'}}, {'op': 'goto', 'path': '/project/{{p}}/permissions'}],
             [read('getProjectUserRole', ['{{p}}', '{{bob}}'], expected='project-member')]),
        step('changed', 'Change the role of bob in this project to Project Manager.',
             'The permissions page lists bob with the role Project Manager.',
             [{'op': 'role-change', 'user': 'bob', 'value': 'Project Manager'},
              {'op': 'corroborate', 'method': 'getProjectUserRole', 'params': ['{{p}}', '{{bob}}'],
               'expect': {'equals': 'project-manager'}}, {'op': 'goto', 'path': '/project/{{p}}/permissions'}],
             [read('getProjectUserRole', ['{{p}}', '{{bob}}'], expected='project-manager')], depends=['added'])])
    add('viewer-readonly', 'permissions', project('Website') + [user('carol'), task('t1', 'Read-only task'),
            api('carol-viewer', 'addProjectUser', ['{{p}}', '{{carol}}', 'project-viewer'])], [
        step('board', 'Open the board of the project Website.',
             'The board shows the task Read-only task to carol, but offers no control to add a task.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'wait-text', 'texts': ['Read-only task']}]),
        step('settings', 'Try to open the edit page of the project Website by entering its path /project/1/edit.',
             'The project settings are not available to carol: an access denied page (or no editable project form) is '
             'shown.',
             [{'op': 'goto', 'path': '/project/{{p}}/edit'}], requires=['board/visible'])], actor='carol')

    # -- users and groups ---------------------------------------------------------------------------------------
    add('user-create', 'users', [], [
        step('created', 'In User management, create a new user with the username "dana", the name "Dana Designer", '
                        'the email "dana@example.test", the password "Dana-Pass-2026" (confirmed) and the role Manager.',
             'The user list shows dana (Dana Designer) with the role Manager.',
             [{'op': 'goto', 'path': '/users'}, {'op': 'click', 'names': ['New user']},
              {'op': 'fill', 'field': 'username', 'value': 'dana'}, {'op': 'fill', 'field': 'name', 'value': 'Dana Designer'},
              {'op': 'fill', 'field': 'email', 'value': 'dana@example.test'},
              {'op': 'fill', 'field': 'password', 'value': 'Dana-Pass-2026'},
              {'op': 'fill', 'field': 'confirmation', 'value': 'Dana-Pass-2026'},
              {'op': 'select', 'field': 'role', 'value': 'Manager'}, {'op': 'save'},
              {'op': 'goto', 'path': '/users'}, {'op': 'wait-text', 'texts': ['Dana Designer']}],
             [read('getUserByName', ['dana'], fields=['username', 'name', 'email', 'role', 'is_active'],
                   expected={'username': 'dana', 'name': 'Dana Designer', 'email': 'dana@example.test',
                             'role': 'app-manager', 'is_active': 1}),
              read('getVersion', None, actor=('secret', 'dana', 'Dana-Pass-2026'),
                   description='The new account authenticates with the password set in the form.')]),
        step('duplicate', 'Try to create another user with the same username "dana" (password "Other-Pass-2026", '
                          'confirmed).',
             'The user is not created: the form is shown again with an error that the username is already taken.',
             [{'op': 'goto', 'path': '/users'}, {'op': 'click', 'names': ['New user']},
              {'op': 'fill', 'field': 'username', 'value': 'dana'},
              {'op': 'fill', 'field': 'password', 'value': 'Other-Pass-2026'},
              {'op': 'fill', 'field': 'confirmation', 'value': 'Other-Pass-2026'}, {'op': 'save'},
              {'op': 'wait-text', 'texts': ['already']}],
             [read('getAllUsers', None, fields=['username'], collection=True,
                   expected=[{'username': 'admin'}, {'username': 'dana'}])], depends=['created'])],
        extra_tokens=180_000)
    add('user-edit-disable', 'users', [user('bob')], [
        step('edited', 'In User management, edit the user bob: change the name to "Robert Builder" and the email to '
                       '"robert@example.test".',
             'The user list or bob\'s profile shows the name Robert Builder and the new email.',
             [{'op': 'goto', 'path': '/user/{{bob}}/edit'}, {'op': 'fill', 'field': 'name', 'value': 'Robert Builder'},
              {'op': 'fill', 'field': 'email', 'value': 'robert@example.test'}, {'op': 'save'},
              {'op': 'goto', 'path': '/users'}, {'op': 'wait-text', 'texts': ['Robert Builder']}],
             [read('getUserByName', ['bob'], fields=['name', 'email'],
                   expected={'name': 'Robert Builder', 'email': 'robert@example.test'})]),
        step('disabled', 'Disable the user bob.',
             'The user list shows bob as disabled (inactive).',
             [{'op': 'goto', 'path': '/users'}, {'op': 'user-disable', 'id': '{{bob}}'},
              {'op': 'corroborate', 'method': 'isActiveUser', 'params': ['{{bob}}'], 'expect': {'equals': False}},
              {'op': 'goto', 'path': '/users'}],
             [read('getUserByName', ['bob'], fields=['is_active'], expected={'is_active': 0},
                   refused={'method': 'getMe', 'params': None, 'actor': ('secret', 'bob', PASSWORD)},
                   description='bob is inactive and can no longer authenticate.')], depends=['edited'])])
    add('user-remove', 'users', [user('bob'), user('carol')], [
        step('removed', 'In User management, remove the user carol and confirm.',
             'The user list no longer shows carol; admin and bob are still listed.',
             [{'op': 'goto', 'path': '/users'}, {'op': 'user-action', 'id': '{{carol}}', 'item': 'Remove'},
              {'op': 'corroborate', 'method': 'getUserByName', 'params': ['carol'], 'expect': {'null': True}},
              {'op': 'goto', 'path': '/users'}],
             [read('getAllUsers', None, fields=['username', 'name'], collection=True,
                   expected=[{'username': 'admin', 'name': None}, {'username': 'bob', 'name': 'Bob Builder'}])])])
    add('user-import', 'users', [user('bob')], [
        step('imported', 'In User management, import users from the input file users.csv with the default options.',
             'The user list shows the imported users erin (Erin Editor) and frank (Frank Field); bob is listed once.',
             [{'op': 'goto', 'path': '/users'}, {'op': 'click', 'names': ['Import'], 'tags': ['a']},
              {'op': 'attach-input', 'file': 'users.csv'}, {'op': 'save', 'names': ['Import']},
              {'op': 'goto', 'path': '/users'}, {'op': 'wait-text', 'texts': ['Erin Editor', 'Frank Field']}],
             [read('getAllUsers', None, fields=['username', 'name', 'email', 'role'], collection=True,
                   expected=[{'username': 'admin', 'name': None, 'email': None, 'role': 'app-admin'},
                             {'username': 'bob', 'name': 'Bob Builder', 'email': 'bob@example.test',
                              'role': 'app-user'},
                             {'username': 'erin', 'name': 'Erin Editor', 'email': 'erin@example.test',
                              'role': 'app-manager'},
                             {'username': 'frank', 'name': 'Frank Field', 'email': None, 'role': 'app-user'}]),
              read('getMe', None, actor=('secret', 'erin', 'Erin-Pass-2026'), fields=['username', 'role'],
                   expected={'username': 'erin', 'role': 'app-manager'},
                   description='An imported account signs in with the password from the file.')])],
        files={'users.csv': 'Username,Password,Email,Full Name,Administrator,Manager,Remote User\n'
                            'Erin,Erin-Pass-2026,erin@example.test,Erin Editor,0,1,0\n'
                            'frank,Frank-Pass-2026,,Frank Field,no,no,no\n'
                            'bob,Other-Pass-2026,other@example.test,Another Bob,0,0,0\n'})
    add('groups', 'groups', [user('bob'), user('carol')], [
        step('created', 'In User management, open the groups and create a group named "Designers".',
             'The group list shows Designers.',
             [{'op': 'goto', 'path': '/groups'}, {'op': 'click', 'names': ['New group']},
              {'op': 'fill', 'field': 'name', 'value': 'Designers'}, {'op': 'save'},
              {'op': 'goto', 'path': '/groups'}, {'op': 'wait-text', 'texts': ['Designers']}],
             [read('getAllGroups', None, fields=['name'], collection=True, expected=[{'name': 'Designers'}])]),
        step('members', 'Add the users bob and carol to the group Designers.',
             'The members page of Designers lists bob and carol.',
             [{'op': 'group-member', 'group': 'Designers', 'user': 'Bob Builder'},
              {'op': 'group-member', 'group': 'Designers', 'user': 'Carol Viewer'}],
             [read('getAllGroups', None, where={'name': 'Designers'}, fields=['name', 'nb_users'],
                   expected={'name': 'Designers', 'nb_users': 2})], depends=['created'])])
    add('my-profile', 'profile', [user('bob')], [
        step('edited', 'Open your own profile (My profile in the account menu) and edit it: set the name to "Bob '
                       'Brick" and the email to "brick@example.test".',
             'Your profile shows the name Bob Brick and the email brick@example.test.',
             [{'op': 'goto', 'path': '/user/{{bob}}/edit'}, {'op': 'fill', 'field': 'name', 'value': 'Bob Brick'},
              {'op': 'fill', 'field': 'email', 'value': 'brick@example.test'}, {'op': 'save'},
              {'op': 'goto', 'path': '/user/show/{{bob}}'}, {'op': 'wait-text', 'texts': ['Bob Brick']}],
             [read('getUserByName', ['bob'], fields=['name', 'email'],
                   expected={'name': 'Bob Brick', 'email': 'brick@example.test'})]),
        step('password', f'Change your password from "{PASSWORD}" to "Bob-New-Pass-2026".',
             'The password change is confirmed (a success message or the profile is shown again without errors).',
             [{'op': 'goto', 'path': '/user/{{bob}}/password'},
              {'op': 'fill', 'field': 'current_password', 'value': PASSWORD},
              {'op': 'fill', 'field': 'password', 'value': 'Bob-New-Pass-2026'},
              {'op': 'fill', 'field': 'confirmation', 'value': 'Bob-New-Pass-2026'}, {'op': 'save'}],
             [read('getVersion', None, actor=('secret', 'bob', 'Bob-New-Pass-2026'),
                   refused={'method': 'getVersion', 'params': None, 'actor': ('secret', 'bob', PASSWORD)},
                   description='The new password authenticates and the old one no longer does.')],
             depends=['edited']),
        step('token', 'In your profile, open the API section and generate a personal API access token.',
             'A new personal access token is displayed in your profile.',
             [{'op': 'goto', 'path': '/user/show/{{bob}}'}, {'op': 'click', 'names': ['API']},
              {'op': 'click', 'names': ['Generate a new token']}, {'op': 'wait', 'seconds': 1}],
             [{'method': 'getMe', 'params': None, 'actor': ('secret', 'bob', 'Bob-New-Pass-2026'), 'fields': [],
               'derive': [], 'expected': None, 'where': None, 'collection': False, 'token_auth': True,
               'description': 'The generated personal token authenticates the account through the API.'}],
             depends=['password'])], actor='bob')

    # -- views, search and the dashboard ------------------------------------------------------------------------
    views = project('Website') + [user('bob'), api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member']),
                                  task('t1', 'Alpha homepage', owner_id='{{bob}}', color_id='blue'),
                                  task('t2', 'Beta checkout', color_id='red', date_due='2026-04-10 12:00'),
                                  task('t3', 'Gamma newsletter', owner_id='{{bob}}', column_id='{{p-columns.2.id}}'),
                                  task('t4', 'Delta archive'), api('close-t4', 'closeTask', ['{{t4}}'], actor=ADMIN)]
    add('board-filter', 'search', views, [
        step('assignee', 'On the board of the project Website, filter the tasks with the query "assignee:bob" in the '
                         'filter box.',
             'The board shows only Alpha homepage and Gamma newsletter (the tasks assigned to bob).',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'filter', 'value': 'assignee:bob'},
              {'op': 'wait-text', 'texts': ['Gamma newsletter']}, {'op': 'wait-absent', 'texts': ['Beta checkout']}]),
        step('color', 'Replace the filter with "color:red".',
             'The board shows only Beta checkout.',
             [{'op': 'filter', 'value': 'color:red'}, {'op': 'wait-text', 'texts': ['Beta checkout']},
              {'op': 'wait-absent', 'texts': ['Alpha homepage', 'Gamma newsletter']}]),
        step('closed', 'Open the list view of the project and filter it with "status:closed".',
             'The list shows only the closed task Delta archive.',
             [{'op': 'goto', 'path': '/list/{{p}}'}, {'op': 'filter', 'value': 'status:closed'},
              {'op': 'wait-text', 'texts': ['Delta archive']}, {'op': 'wait-absent', 'texts': ['Beta checkout']}])])
    add('global-search', 'search', views + project('Mobile App', 'm') + [task('t5', 'Alpha mobile', project_key='m')], [
        step('search', 'Use the search on the dashboard to search all projects for "Alpha".',
             'The results list Alpha homepage (Website) and Alpha mobile (Mobile App), and no other task.',
             [{'op': 'goto', 'path': '/dashboard'}, {'op': 'filter', 'value': 'Alpha'},
              {'op': 'wait-text', 'texts': ['Alpha mobile']}, {'op': 'wait-absent', 'texts': ['Beta checkout']}]),
        step('activity', 'Switch to the search of the activity stream and search it for title:"Delta archive".',
             'The results list the events of the task Delta archive (its creation and its closing by admin) and no '
             'event of another task.',
             [{'op': 'goto', 'path': '/search'}, {'op': 'click', 'names': ['Activity stream search'], 'tags': ['a']},
              {'op': 'filter', 'value': 'title:"Delta archive"'}, {'op': 'wait-text', 'texts': ['Delta archive']},
              {'op': 'wait-absent', 'texts': ['Alpha homepage']}])])
    add('dashboard', 'dashboard', views, [
        step('tasks', 'Open your dashboard and look at the tasks assigned to you (My tasks).',
             'The dashboard lists Alpha homepage and Gamma newsletter as bob\'s tasks.',
             [{'op': 'goto', 'path': '/dashboard/{{bob}}/tasks'}, {'op': 'wait-text', 'texts': ['Gamma newsletter']}]),
        step('projects', 'Open the list of your projects (My projects) on the dashboard.',
             'The dashboard lists the project Website.',
             [{'op': 'goto', 'path': '/dashboard/{{bob}}/projects'}, {'op': 'wait-text', 'texts': ['Website']}])],
        actor='bob')
    add('activity', 'activity', views, [
        step('stream', 'Open the activity stream of the project Website.',
             'The activity stream lists the creation of the tasks (for example Alpha homepage and Delta archive) and '
             'the closing of Delta archive.',
             [{'op': 'goto', 'path': '/project/{{p}}/activity'}, {'op': 'wait-text', 'texts': ['Delta archive']}])])
    add('overview', 'projects', views + [api('describe', 'updateProject', {'project_id': '{{p}}',
                                                                           'description': 'Company website project'})], [
        step('overview', 'Open the overview page of the project Website.',
             'The overview shows the project description Company website project and the tasks per column (for '
             'example Gamma newsletter in Work in progress).',
             [{'op': 'goto', 'path': '/project/{{p}}/overview'}, {'op': 'wait-text', 'texts': ['Company website project']}])])

    # -- export and import --------------------------------------------------------------------------------------
    add('export-tasks', 'export', views + [
            api('subtask-1', 'createSubtask', {'task_id': '{{t1}}', 'title': 'Write copy', 'user_id': '{{bob}}',
                                               'time_estimated': 2}),
            api('subtask-2', 'createSubtask', {'task_id': '{{t3}}', 'title': 'Pick images', 'status': 1}),
            api('move-t1', 'moveTaskPosition', ['{{p}}', '{{t1}}', '{{p-columns.1.id}}', 1, '{{p-lanes.0.id}}'],
                actor=ADMIN)], [
        step('csv', 'Export the tasks of the project Website as CSV for the period from 04/01/2026 to 04/30/2026 '
                    '(Export in the project menu, Tasks).',
             'The export starts a file download of the CSV export.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'click', 'names': ['Configure this project'], 'tags': ['a']},
              {'op': 'click', 'names': ['Exports'], 'tags': ['a']},
              {'op': 'fill', 'field': 'from', 'value': '04/01/2026'},
              {'op': 'fill', 'field': 'to', 'value': '04/30/2026'}, {'op': 'press', 'key': 'Escape'},
              {'op': 'save', 'names': ['Export']},
              {'op': 'wait', 'seconds': 2}],
             [{'csv': ['Task Id', 'Title', 'Status', 'Column', 'Assignee Username', 'Color'],
               'description': 'The downloaded CSV contains every task of the project with its title, status, column, '
                              'assignee and colour.'}]),
        step('subtasks-csv', 'Export the sub-tasks of the project Website as CSV for the same period (Exports, '
                             'Subtasks).',
             'The export starts a file download of the sub-task CSV export.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'click', 'names': ['Configure this project'], 'tags': ['a']},
              {'op': 'click', 'names': ['Exports'], 'tags': ['a']}, {'op': 'click', 'names': ['Subtasks'], 'tags': ['a']},
              {'op': 'wait', 'seconds': 1}, {'op': 'fill', 'field': 'from', 'value': '04/01/2026'},
              {'op': 'fill', 'field': 'to', 'value': '04/30/2026'}, {'op': 'press', 'key': 'Escape'},
              {'op': 'save', 'names': ['Export']}, {'op': 'wait', 'seconds': 2}],
             [{'csv': ['Title', 'Status', 'Assignee', 'Time estimated', 'Task Id', 'Task Title'],
               'description': 'The downloaded CSV lists every sub-task with its status, assignee, estimate and task.'}]),
        step('transitions-csv', 'Export the task transitions of the project Website as CSV for the same period '
                                '(Exports, Task transitions).',
             'The export starts a file download of the task transition CSV export.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'click', 'names': ['Configure this project'], 'tags': ['a']},
              {'op': 'click', 'names': ['Exports'], 'tags': ['a']},
              {'op': 'click', 'names': ['Task transitions'], 'tags': ['a']},
              {'op': 'wait', 'seconds': 1}, {'op': 'fill', 'field': 'from', 'value': '04/01/2026'},
              {'op': 'fill', 'field': 'to', 'value': '04/30/2026'}, {'op': 'press', 'key': 'Escape'},
              {'op': 'save', 'names': ['Export']}, {'op': 'wait', 'seconds': 2}],
             [{'csv': ['Task Title', 'Source column', 'Destination column', 'Executer'],
               'description': 'The downloaded CSV lists the move of Alpha homepage from Backlog to Ready by admin.'}]),
        step('summary-csv', 'Export the daily project summary of Website as CSV for the same period (Exports, Daily '
                            'project summary).',
             'The export starts a file download of the daily summary CSV export.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'click', 'names': ['Configure this project'], 'tags': ['a']},
              {'op': 'click', 'names': ['Exports'], 'tags': ['a']},
              {'op': 'click', 'names': ['Daily project summary'], 'tags': ['a']},
              {'op': 'wait', 'seconds': 1}, {'op': 'fill', 'field': 'from', 'value': '04/01/2026'},
              {'op': 'fill', 'field': 'to', 'value': '04/30/2026'}, {'op': 'press', 'key': 'Escape'},
              {'op': 'save', 'names': ['Export']}, {'op': 'wait', 'seconds': 2}],
             [{'csv': ['Date', 'Backlog', 'Ready', 'Work in progress', 'Done'],
               'description': 'The downloaded CSV lists the number of tasks per column for each day.'}])])
    add('import-tasks', 'import', project('Website') + [user('bob'),
            api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member'])], [
        step('imported', 'Import tasks into the project Website from the input file tasks.csv (Import in the project '
                         'menu), with the default options.',
             'The board of Website shows the imported tasks Import first and Import second.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'click', 'names': ['Configure this project'], 'tags': ['a']},
              {'op': 'click', 'names': ['Import tasks'], 'tags': ['a']}, {'op': 'attach-input', 'file': 'tasks.csv'},
              {'op': 'save', 'names': ['Import']}, {'op': 'goto', 'path': '/board/{{p}}'},
              {'op': 'wait-text', 'texts': ['Import second']}],
             [read('getAllTasks', ['{{p}}', 1], fields=['title', 'description', 'color_id'],
                   derive=['owner', 'column'], collection=True,
                   expected=[{'title': 'Import first', 'description': 'First imported task', 'color_id': 'green',
                              'owner': 'bob', 'column': 'Backlog'},
                             {'title': 'Import second', 'description': 'Second imported task', 'color_id': 'red',
                              'owner': None, 'column': 'Ready'}])])],
        files={'tasks.csv': 'Reference,Title,Description,Assignee Username,Creator Username,Color Name,Column Name,'
                            'Category Name,Swimlane Name,Complexity,Time Estimated,Time Spent,Start Date,Due Date,'
                            'Priority,Status,Tags,External Link\n'
                            'IMP-1,Import first,First imported task,bob,admin,Green,Backlog,,,3,,,,,,open,,\n'
                            'IMP-2,Import second,Second imported task,,admin,Red,Ready,,,,,,,,,open,,\n'})

    # -- application settings -----------------------------------------------------------------------------------
    add('link-labels', 'settings', [], [
        step('added', 'In Settings, open the link labels and add a link label "depends on" with the opposite label '
                      '"is a dependency of".',
             'The link label list shows depends on and is a dependency of.',
             [{'op': 'goto', 'path': '/settings/links/labels'}, {'op': 'click', 'names': ['Add link label']},
              {'op': 'fill', 'field': 'label', 'value': 'depends on'},
              {'op': 'fill', 'field': 'opposite_label', 'value': 'is a dependency of'}, {'op': 'save'},
              {'op': 'goto', 'path': '/settings/links/labels'}, {'op': 'wait-text', 'texts': ['is a dependency of']}],
             [read('getLinkByLabel', ['depends on'], fields=['label'], expected={'label': 'depends on'}),
              read('getLinkByLabel', ['is a dependency of'], fields=['label'],
                   expected={'label': 'is a dependency of'})])])
    add('default-columns', 'settings', [user('bob')], [
        step('configured', 'In Settings, open the project settings and set the default columns for new projects to '
                           '"Todo, Doing, Review, Shipped". Save.',
             'The settings show the default columns Todo, Doing, Review, Shipped.',
             [{'op': 'goto', 'path': '/settings/project'},
              {'op': 'fill', 'field': 'board_columns', 'value': 'Todo, Doing, Review, Shipped'}, {'op': 'save'},
              {'op': 'goto', 'path': '/settings/project'}]),
        step('categories', 'In the same settings, set the default categories for new projects to "Bug, Feature". '
                           'Save.',
             'The settings show the default categories Bug, Feature.',
             [{'op': 'goto', 'path': '/settings/project'},
              {'op': 'fill', 'field': 'project_categories', 'value': 'Bug, Feature'}, {'op': 'save'},
              {'op': 'goto', 'path': '/settings/project'}], depends=['configured']),
        step('new-project', 'Create a new project named "Fresh Start" and open its board.',
             'The board of Fresh Start has the columns Todo, Doing, Review and Shipped.',
             [{'op': 'goto', 'path': '/project/create'}, {'op': 'fill', 'field': 'name', 'value': 'Fresh Start'},
              {'op': 'save'}, {'op': 'wait-text', 'texts': ['Shipped']}],
             [read('getProjectByName', ['Fresh Start'], fields=['name'], expected={'name': 'Fresh Start'},
                   save='fresh'),
              read('getColumns', ['{{fresh.id}}'], fields=['title', 'position'], collection=True,
                   expected=[{'title': 'Doing', 'position': 2}, {'title': 'Review', 'position': 3},
                             {'title': 'Shipped', 'position': 4}, {'title': 'Todo', 'position': 1}]),
              read('getAllCategories', ['{{fresh.id}}'], fields=['name'], collection=True,
                   expected=[{'name': 'Bug'}, {'name': 'Feature'}],
                   description='The new project has the default categories.')],
             depends=['configured', 'categories']),
        step('personal-off', 'In the project settings, disable personal projects. Save, then open your dashboard.',
             'The dashboard no longer offers to create a personal project (the link to create a team project is still '
             'there).',
             [{'op': 'goto', 'path': '/settings/project'},
              {'op': 'check', 'field': 'disable_private_project', 'value': True}, {'op': 'save'},
              {'op': 'goto', 'path': '/dashboard'}, {'op': 'wait-text', 'texts': ['New project']}],
             [read('getMe', None, fields=['username'], actor=('secret', 'bob', PASSWORD), expected={'username': 'bob'},
                   refused={'method': 'createMyPrivateProject', 'params': ['Not allowed'],
                            'actor': ('secret', 'bob', PASSWORD)},
                   description='A user can no longer create a personal project through the API.')])])

    # -- more board and task operations ---------------------------------------------------------------------------
    add('bulk-create', 'tasks', project('Website'), [
        step('created', 'On the board of the project Website, create tasks in bulk in the Backlog column (from the '
                        'column\'s menu) with the three titles ' + text_value('Translate menu\nTranslate footer\n'
                                                                              'Translate emails\n') +
                        'one task per line, colour Blue.',
             'The Backlog column shows the three new tasks Translate menu, Translate footer and Translate emails.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'column-menu', 'column': 'Backlog',
                                                       'item': 'Create tasks in bulk'},
              {'op': 'fill', 'field': 'tasks', 'value': 'Translate menu\nTranslate footer\nTranslate emails'},
              {'op': 'select', 'field': 'color_id', 'value': 'Blue'}, {'op': 'save'},
              {'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'wait-text', 'texts': ['Translate emails']}],
             [read('getAllTasks', ['{{p}}', 1], fields=['title', 'color_id'], derive=['column'], collection=True,
                   expected=[{'title': 'Translate menu', 'color_id': 'blue', 'column': 'Backlog'},
                             {'title': 'Translate footer', 'color_id': 'blue', 'column': 'Backlog'},
                             {'title': 'Translate emails', 'color_id': 'blue', 'column': 'Backlog'}])])])
    add('close-column', 'tasks', project('Website') + [task('t1', 'Ready one', column_id='{{p-columns.1.id}}'),
                                                      task('t2', 'Ready two', column_id='{{p-columns.1.id}}'),
                                                      task('t3', 'Still in backlog')], [
        step('closed', 'On the board of the project Website, close all tasks of the Ready column at once (from the '
                       'column\'s menu) and confirm.',
             'The Ready column is empty; Still in backlog remains on the board.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'column-menu', 'column': 'Ready',
                                                       'item': 'Close all tasks in this column and this swimlane'},
              {'op': 'click', 'names': ['Yes'], 'tags': ['button']},
              {'op': 'corroborate', 'method': 'getAllTasks', 'params': ['{{p}}', 1],
               'expect': {'absent': {'title': 'Ready one'}}}, {'op': 'goto', 'path': '/board/{{p}}'}],
             [read('getAllTasks', ['{{p}}', 0], fields=['title'], collection=True,
                   expected=[{'title': 'Ready one'}, {'title': 'Ready two'}]),
              read('getAllTasks', ['{{p}}', 1], fields=['title'], collection=True,
                   expected=[{'title': 'Still in backlog'}])])])
    add('assign-start', 'tasks', project('Website') + [task('t1', 'Pick me up')], [
        step('assigned', 'Open the task Pick me up (project Website) and assign it to yourself with its Assign to me '
                         'link.',
             'The task shows admin as its assignee.',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Assign to me'], 'tags': ['a']},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'], 'expect': {'owner_id': '{{admin.id}}'}},
              {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], derive=['owner'], expected={'owner': 'admin'})]),
        step('started', 'Start the task now with its Start now link.',
             'The task shows a start date of today (04/14/2026).',
             [{'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'click', 'names': ['Start now'], 'tags': ['a']},
              {'op': 'corroborate', 'method': 'getTask', 'params': ['{{t1}}'], 'expect': {'started': True}},
              {'op': 'goto', 'path': '/task/{{t1}}'}],
             [read('getTask', ['{{t1}}'], fields=['date_started'], expected={'date_started': '2026-04-14'})],
             depends=['assigned'])])
    add('predefined-content', 'tasks', project('Website'), [
        step('template', 'In the settings of the project Website (Predefined contents), add a predefined task '
                         'description titled "Bug report" with the text ' + text_value('Steps to reproduce:\n1.\n2.\n')
                         + 'Save it.',
             'The predefined contents list the task description Bug report.',
             [{'op': 'goto', 'path': '/project/{{p}}/predefined-contents'},
              {'op': 'click', 'names': ['Add predefined task description'], 'tags': ['a']},
              {'op': 'fill', 'field': 'title', 'value': 'Bug report'},
              {'op': 'fill', 'field': 'description', 'value': 'Steps to reproduce:\n1.\n2.\n'}, {'op': 'save'},
              {'op': 'goto', 'path': '/project/{{p}}/predefined-contents'}, {'op': 'wait-text', 'texts': ['Bug report']}]),
        step('used', 'Create a task titled "Crash on save" in the Backlog of Website and fill its description from the '
                     'predefined description Bug report.',
             'The task Crash on save exists and its description is the Bug report text (Steps to reproduce).',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'new-task', 'column': 0},
              {'op': 'fill', 'field': 'title', 'value': 'Crash on save'}, {'op': 'template', 'name': 'Bug report'},
              {'op': 'save'}, {'op': 'corroborate', 'method': 'getAllTasks', 'params': ['{{p}}', 1],
                               'expect': {'where': {'title': 'Crash on save'}}},
              {'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'click', 'names': ['Crash on save'], 'tags': ['a']},
              {'op': 'wait-text', 'texts': ['Steps to reproduce']}],
             [read('getAllTasks', ['{{p}}', 1], where={'title': 'Crash on save'}, fields=['title', 'description'],
                   expected={'title': 'Crash on save', 'description': 'Steps to reproduce:\n1.\n2.\n'})],
             depends=['template'])])
    add('custom-filter', 'search', views, [
        step('created', 'In the project Website, add a custom filter named "Red work" with the filter "color:red" '
                        '(Add custom filters in the project menu).',
             'The project\'s custom filters list Red work with its filter color:red.',
             [{'op': 'goto', 'path': '/project/{{p}}/customer-filters'},
              {'op': 'click', 'names': ['Add custom filters'], 'tags': ['a']},
              {'op': 'fill', 'field': 'name', 'value': 'Red work'}, {'op': 'fill', 'field': 'filter', 'value': 'color:red'},
              {'op': 'save'}, {'op': 'goto', 'path': '/project/{{p}}/customer-filters'},
              {'op': 'wait-text', 'texts': ['Red work']}]),
        step('applied', 'Open the board of Website and apply the saved custom filter Red work.',
             'The board is filtered with color:red and shows only Beta checkout.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'custom-filter', 'name': 'Red work'},
              {'op': 'wait-text', 'texts': ['Beta checkout']}], depends=['created'])])
    add('analytics', 'analytics', views, [
        step('distribution', 'Open the analytics of the project Website and look at the task distribution.',
             'The task distribution shows the open tasks per column: Backlog 2 (66.67%), Work in progress 1 (33.33%), '
             'Ready 0 and Done 0.',
             [{'op': 'goto', 'path': '/analytics/tasks/{{p}}'}, {'op': 'wait-text', 'texts': ['66.67%']}]),
        step('repartition', 'In the same analytics, look at the user repartition.',
             'The user repartition shows the open tasks per assignee: Bob Builder 2 (66.67%) and the unassigned '
             'tasks 1 (33.33%).',
             [{'op': 'goto', 'path': '/analytics/users/{{p}}'}, {'op': 'wait-text', 'texts': ['Bob Builder', '66.67%']}])])
    add('global-tags', 'tags', [], [
        step('added', 'In Settings, open the global tags management and add a global tag named "company" with the '
                      'colour Purple.',
             'The global tag list shows company.',
             [{'op': 'goto', 'path': '/settings/tags'}, {'op': 'click', 'names': ['Add new tag'], 'tags': ['a']},
              {'op': 'fill', 'field': 'name', 'value': 'company'}, {'op': 'select', 'field': 'color_id', 'value': 'Purple'},
              {'op': 'save'}, {'op': 'goto', 'path': '/settings/tags'}, {'op': 'wait-text', 'texts': ['company']}],
             [read('getAllTags', None, fields=['name', 'project_id', 'color_id'], collection=True,
                   expected=[{'name': 'company', 'project_id': 0, 'color_id': 'purple'}])])])
    add('user-language', 'profile', [user('bob')], [
        step('french', 'Edit your own profile and change the language to Français. Save.',
             'The interface is now shown in French (for example the profile or dashboard labels are French).',
             [{'op': 'goto', 'path': '/user/{{bob}}/edit'}, {'op': 'select', 'field': 'language', 'value': 'Français'},
              {'op': 'save'}, {'op': 'goto', 'path': '/dashboard'}],
             [read('getUser', ['{{bob}}'], fields=['language'], expected={'language': 'fr_FR'})])], actor='bob')

    # -- roles, notifications and preferences ---------------------------------------------------------------------
    add('custom-roles', 'permissions', project('Website') + [user('bob'), task('t1', 'Draft copy')], [
        step('created', 'In the settings of the project Website (Custom roles), add a custom role named "Reviewer".',
             'The custom role list of Website shows Reviewer.',
             [{'op': 'goto', 'path': '/project/{{p}}/custom-roles'},
              {'op': 'click', 'names': ['Add a new custom role'], 'tags': ['a']},
              {'op': 'fill', 'field': 'role', 'value': 'Reviewer'}, {'op': 'save'},
              {'op': 'goto', 'path': '/project/{{p}}/custom-roles'}, {'op': 'wait-text', 'texts': ['Reviewer']}]),
        step('assigned', 'In the permissions of Website, allow the user bob with the role Reviewer.',
             'The permissions page lists bob with the role Reviewer.',
             [{'op': 'goto', 'path': '/project/{{p}}/permissions'},
              {'op': 'autocomplete', 'placeholder': 'Enter user name...', 'value': 'bob'},
              {'op': 'select-nth', 'field': 'role', 'nth': 0, 'value': 'Reviewer'},
              {'op': 'click', 'names': ['Add'], 'tags': ['button']},
              {'op': 'corroborate', 'method': 'getProjectUserRole', 'params': ['{{p}}', '{{bob}}'],
               'expect': {'equals': 'Reviewer'}}, {'op': 'goto', 'path': '/project/{{p}}/permissions'}],
             [read('getProjectUserRole', ['{{p}}', '{{bob}}'], expected='Reviewer')], depends=['created']),
        step('restricted', 'Add a project restriction to the custom role Reviewer: task creation is not permitted.',
             'The custom roles page lists the restriction "task creation is not permitted" for Reviewer.',
             [{'op': 'goto', 'path': '/project/{{p}}/custom-roles'},
              {'op': 'click', 'names': ['Restrictions for the role "Reviewer"'], 'tags': ['a']},
              {'op': 'click', 'names': ['Add a new project restriction'], 'tags': ['a'], 'last': True},
              {'op': 'select', 'field': 'rule', 'value': 'Task creation is not permitted'}, {'op': 'save'},
              {'op': 'goto', 'path': '/project/{{p}}/custom-roles'},
              {'op': 'wait-text', 'texts': ['Task creation is not permitted']}], depends=['created']),
        step('column-exception', 'Add a column restriction to the custom role Reviewer: task creation is permitted '
                                 'for the column Ready.',
             'The restrictions of Reviewer list the column restriction "task creation is permitted" for the column '
             'Ready, next to the project restriction "task creation is not permitted".',
             [{'op': 'goto', 'path': '/project/{{p}}/custom-roles'},
              {'op': 'click', 'names': ['Restrictions for the role "Reviewer"'], 'tags': ['a']},
              {'op': 'click', 'names': ['Add a new column restriction'], 'tags': ['a'], 'last': True},
              {'op': 'select', 'field': 'rule', 'value': 'Task creation is permitted for this column'},
              {'op': 'select', 'field': 'column_id', 'value': 'Ready'}, {'op': 'save'},
              {'op': 'goto', 'path': '/project/{{p}}/custom-roles'},
              {'op': 'wait-text', 'texts': ['Task creation is permitted for this column']}], depends=['restricted']),
        step('restricted-view', f'Sign out, then sign in as bob with the password "{PASSWORD}" and open the board '
                                f'of the project Website.',
             'bob sees the board of Website with the task Draft copy; a control to add a task is offered in the '
             'column Ready only, not in the other columns (the role Reviewer may create tasks only in Ready).',
             [{'op': 'sign-out-menu'}, {'op': 'sign-in', 'user': 'bob', 'password': PASSWORD},
              {'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'wait-text', 'texts': ['Draft copy']}],
             depends=['assigned', 'restricted', 'column-exception']),
        step('column-create', 'As bob, add a task named "Proofread" in the column Ready of Website.',
             'The board of Website shows the task Proofread in the column Ready.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'new-task', 'column': 0},
              {'op': 'fill', 'field': 'title', 'value': 'Proofread'}, {'op': 'save'},
              {'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'wait-text', 'texts': ['Proofread']}],
             [read('getAllTasks', ['{{p}}', 1], where={'title': 'Proofread'}, fields=['title'],
                   derive=['column', 'creator'], expected={'title': 'Proofread', 'column': 'Ready', 'creator': 'bob'})],
             depends=['restricted-view'])])
    add('notifications', 'notifications', project('Website') + [user('bob'),
            api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member'])], [
        step('enabled', 'In your profile, open the notification settings: enable web notifications for all tasks of '
                        'the project Website and save.',
             'The notification settings show web notifications enabled for Website.',
             [{'op': 'goto', 'path': '/user/{{bob}}/notifications'},
              {'op': 'check', 'field': 'notification_types[web]', 'value': True},
              {'op': 'check-label', 'label': 'All tasks'}, {'op': 'check-label', 'label': 'Website'},
              {'op': 'save'}, {'op': 'goto', 'path': '/user/{{bob}}/notifications'}],
             [read('getUser', ['{{bob}}'], fields=['notifications_enabled', 'notifications_filter'],
                   expected={'notifications_enabled': 1, 'notifications_filter': 1})]),
        step('received', 'The administrator has meanwhile assigned a new task to you. Open your web notifications.',
             'The web notifications list a notification about the new task Review the copy.',
             [{'op': 'goto', 'path': '/dashboard'}, {'op': 'click', 'names': ['Unread notifications', 'My notifications'], 'tags': ['a']},
              {'op': 'wait-text', 'texts': ['Review the copy']}], depends=['enabled'],
             prepare=[api('assigned-task', 'createTask', {'title': 'Review the copy', 'project_id': '{{p}}',
                                                          'owner_id': '{{bob}}'}, actor=ADMIN, save='rt')]),
        step('mention', 'The administrator has meanwhile mentioned you in a comment on that task. Open your web '
                        'notifications again.',
             'The web notifications now also report that you were mentioned in a comment on that task.',
             [{'op': 'goto', 'path': '/dashboard'},
              {'op': 'click', 'names': ['Unread notifications', 'My notifications'], 'tags': ['a']},
              {'op': 'wait-text', 'texts': ['mentioned']}], depends=['received'],
             prepare=[api('mention', 'createComment', {'task_id': '{{rt}}', 'user_id': '{{admin.id}}',
                                                       'content': '@bob please check the copy'}, actor=ADMIN)])],
        actor='bob')
    add('date-format', 'settings', project('Website') + [task('t1', 'Dated task', date_due='2026-05-20 10:00')], [
        step('configured', 'In Settings, open the application settings and change the date format to the ISO format '
                           '(year-month-day). Save, then open the task Dated task of the project Website.',
             'The task page shows its due date in the ISO format, 2026-05-20.',
             [{'op': 'goto', 'path': '/settings/application'},
              {'op': 'select', 'field': 'application_date_format', 'value': 'Y-m-d'}, {'op': 'save'},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'wait-text', 'texts': ['2026-05-20']}]),
        step('timezone', 'Edit your own profile and set your time zone to America/New_York. Save, then open the task '
                         'Dated task again.',
             'The task page shows its due date in New York time: 2026-05-20 06:00.',
             [{'op': 'goto', 'path': '/user/{{admin.id}}/edit'},
              {'op': 'select', 'field': 'timezone', 'value': 'America/New_York'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getUser', 'params': ['{{admin.id}}'],
               'expect': {'timezone': 'America/New_York'}},
              {'op': 'goto', 'path': '/task/{{t1}}'}, {'op': 'wait-text', 'texts': ['2026-05-20 06:00']}],
             [read('getUser', ['{{admin.id}}'], fields=['timezone'], expected={'timezone': 'America/New_York'})],
             depends=['configured'])])
    add('user-public-access', 'profile', project('Website') + [user('bob'),
            api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member']),
            task('t1', 'Bob deadline', owner_id='{{bob}}', date_due='2026-04-20 15:00')], [
        step('enabled', 'In your profile, open Public access and enable it.',
             'The page shows that public access is enabled and offers the personal RSS and iCalendar feed links.',
             [{'op': 'goto', 'path': '/user/{{bob}}/share'}, {'op': 'click', 'names': ['Enable public access']},
              {'op': 'wait-text', 'texts': ['Disable public access']}],
             [read('getMe', None, actor=('secret', 'bob', PASSWORD), feeds=True,
                   description='The personal activity feed and calendar of bob, reached with the public-access '
                               'token, list the activity of the projects of bob and the task with a due date '
                               'assigned to bob.')])],
        actor='bob')
    add('api-token', 'settings', [], [
        step('reset', 'In Settings, open the API settings and reset the API token.',
             'The API settings show a new token, different from the one shown before.',
             [{'op': 'goto', 'path': '/settings/api'}, {'op': 'click', 'names': ['Reset token'], 'tags': ['a']},
              {'op': 'wait', 'seconds': 1}, {'op': 'goto', 'path': '/settings/api'}],
             [read('getVersion', None, actor=ADMIN, refused={'method': 'getVersion', 'params': None, 'actor': 'app'},
                   description='The previous application token no longer authenticates; user credentials still do.')])])
    add('project-import', 'projects', project('Website') + project('Archive', 'a') + [
            task('a1', 'Archived plan', project_key='a', column_id='{{a-columns.1.id}}'),
            task('a2', 'Archived report', project_key='a'),
            api('archive-action', 'createAction', {'project_id': '{{a}}', 'event_name': 'task.move.column',
                                                   'action_name': '\\Kanboard\\Action\\TaskCloseColumn',
                                                   'params': {'column_id': '{{a-columns.3.id}}'}})], [
        step('tasks', 'In the settings of the project Website, import the tasks of the project Archive (Import tasks '
                      'from another project).',
             'The board of Website shows the tasks Archived plan and Archived report.',
             [{'op': 'goto', 'path': '/project/{{p}}/import/tasks'},
              {'op': 'select', 'field': 'src_project_id', 'value': 'Archive'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getAllTasks', 'params': ['{{p}}', 1],
               'expect': {'where': {'title': 'Archived report'}}}, {'op': 'goto', 'path': '/board/{{p}}'}],
             [read('getAllTasks', ['{{p}}', 1], fields=['title'], derive=['column'], collection=True,
                   description='Website has copies of the open tasks of Archive.')]),
        step('actions', 'In the automatic actions of Website, import the automatic actions of the project Archive.',
             'The automatic actions of Website list the action that closes a task moved to the column Done.',
             [{'op': 'goto', 'path': '/project/{{p}}/actions'},
              {'op': 'click', 'names': ['Import from another project'], 'tags': ['a']},
              {'op': 'select', 'field': 'src_project_id', 'value': 'Archive'}, {'op': 'save'},
              {'op': 'corroborate', 'method': 'getActions', 'params': ['{{p}}'],
               'expect': {'where': {'event_name': 'task.move.column'}}}, {'op': 'goto', 'path': '/project/{{p}}/actions'}],
             [read('getActions', ['{{p}}'], fields=['action_name', 'event_name'], collection=True,
                   expected=[{'action_name': '\\Kanboard\\Action\\TaskCloseColumn', 'event_name': 'task.move.column'}],
                   description='Website has a copy of the automatic action of Archive.')])])
    add('board-display', 'board', project('Website') + [user('bob'),
            api('bob-member', 'addProjectUser', ['{{p}}', '{{bob}}', 'project-member']),
            task('t1', 'Alpha homepage', owner_id='{{bob}}', date_due='2026-04-30 12:00'),
            task('t2', 'Beta checkout', color_id='red')], [
        step('collapsed', 'On the board of the project Website, switch the task cards to the collapsed display (Collapse '
                          'tasks in the project menu).',
             'The cards are shown in their collapsed form: each card shows only its number, the title (Alpha '
             'homepage with its assignee) and no further details such as the due date.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'click', 'names': ['Configure this project'], 'tags': ['a']},
              {'op': 'click', 'names': ['Collapse tasks'], 'tags': ['a']}, {'op': 'wait', 'seconds': 1.5},
              {'op': 'wait-text', 'texts': ['BB - Alpha homepage']}]),
        step('hidden-column', 'Hide the column Done of the board (from the column\'s menu), then reload the board.',
             'After the reload the column Done is still hidden (its tasks and its full header are not shown, only a '
             'way to show it again), while Backlog, Ready and Work in progress are shown normally.',
             [{'op': 'goto', 'path': '/board/{{p}}'}, {'op': 'column-menu', 'column': 'Done', 'item': 'Hide this column'},
              {'op': 'wait', 'seconds': 1}, {'op': 'reload'}, {'op': 'wait-text', 'texts': ['Done']}])])
    add('avatar', 'profile', [user('bob')], [
        step('uploaded', 'In your profile, open Avatar and upload the input file avatar.png as your avatar image.',
             'The avatar page shows the uploaded picture (a plain blue square) instead of the initials, and offers to '
             'remove the image.',
             [{'op': 'goto', 'path': '/user/{{bob}}/avatar'}, {'op': 'attach-input', 'file': 'avatar.png'},
              {'op': 'save', 'names': ['Upload my avatar image']}, {'op': 'goto', 'path': '/user/{{bob}}/avatar'},
              {'op': 'wait-text', 'texts': ['Remove my image']}],
             [read('getMe', None, actor=('secret', 'bob', PASSWORD), present=['avatar_path'],
                   expected={'avatar_path': True}, description='The account has an avatar image.')])],
        actor='bob', files={'avatar.png': {'base64': base64.b64encode(png(48, 48, (40, 90, 200))).decode()}})
    return episodes
