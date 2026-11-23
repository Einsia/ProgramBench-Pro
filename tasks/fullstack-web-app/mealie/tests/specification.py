'''Reviewed user goals, acceptance conditions, public setup and program checks of the GUI episodes.

Reference recipes implement these specifications. Goals are authored here and are never produced by translating a recorded
click trace. Setup items are unscored public preparation with ids (any success status); every checkpoint of a GUI
episode needs them. A point that only verifies a rejection or an unavailable view names, in requires, a positive point
of the same episode that proves the feature exists. The episodes live in the gui_* modules next to this file; each
defines build(add).
'''
import importlib

from harness import ADMIN

CREDS = {ADMIN["username"]: ADMIN["password"]}

MODULES = ['gui_recipes', 'gui_data', 'gui_planning', 'gui_settings', 'gui_misc', 'gui_extended']
DEFAULT_CHECK = 'The independently read public product state matches the requested checkpoint.'


def q(value):
    '''An exact text input, quoted for the evaluator.'''
    return chr(34) + value + chr(34)


def api(name, method, path, body=None, actor='admin', save=None, settle=0):
    item = {'id': name, 'method': method, 'path': path, 'actor': actor, 'body': body, 'save': save}
    if settle:
        item['settle'] = settle
    return item


def recipe(name='Tomato Soup', slug='tomato-soup', extra=None):
    steps = [api('recipe-' + slug, 'POST', 'recipes', {'name': name})]
    if extra:
        steps.append(api('body-' + slug, 'PATCH', 'recipes/' + slug, extra))
    return steps


def read(path, fields=(), expected=None, actor='admin', status=200, where=None, save=None, collection=False, params=None,
         description=None, refused=None, at=None):
    check = {'request': {'method': 'GET', 'path': path, 'actor': actor, 'body': None, 'status': status, 'save': save, 'params': params},
             'fields': list(fields), 'expected': expected, 'where': where, 'collection': collection}
    if at:
        check['at'] = at
    if description:
        check['description'] = description
    if refused:
        check['refused'] = refused
    return check


def denied(path, actor, status, method='GET', body=None):
    '''A request the product has to refuse; it counts only inside the read it accompanies.'''
    return {'method': method, 'path': path, 'actor': actor, 'body': body, 'status': status, 'save': None}


def step(key, goal, acceptance, recipe, checks=(), visible=(), depends=(), action_required=True, requires=(), lifecycle=None, open_before=None):
    cp = {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': recipe, 'checks': list(checks), 'visible': list(visible),
          'depends_on': list(depends), 'action_required': action_required, 'requires': list(requires)}
    if open_before:
        cp['open_before'] = open_before
    if lifecycle:
        cp['lifecycle'] = lifecycle
    return cp


def episode(key, feature, setup, steps, actor='admin', inputs=None, budget=None):
    ids = [item['id'] for item in setup]
    for cp in steps:
        cp['assertions'] = [{'id': key + '/' + cp['id'] + '/visible', 'channel': 'frontend', 'method': 'agent', 'requirement': cp['acceptance']}]
        for i, check in enumerate(cp['checks']):
            cp['assertions'].append({'id': key + '/' + cp['id'] + '/state-%d' % (i + 1), 'channel': 'backend', 'method': 'program',
                                     'requirement': check.get('description', DEFAULT_CHECK), 'check': check})
        # requires: checkpoint/visible or checkpoint/state-N of this episode.
        bound = [key + '/' + x for x in cp.pop('requires')]
        if bound:
            cp['assertions'][0]['requires'] = bound
        cp['depends_on'] = ['setup:' + i for i in ids] + cp['depends_on']
    accounts = {name: password for name, password in CREDS.items() if name == actor}
    for item in setup:
        body = item.get('body') or {}
        if isinstance(body,dict) and body.get('username') == actor and body.get('password'):
            accounts[actor] = body['password']
    session = ('Sign in with the supplied account before authenticated goals; this is unscored preparation.' if actor
               else 'Start unauthenticated. Only sign in when the checkpoint explicitly asks you to.')
    return {'id': key, 'feature': feature, 'execution': 'gui',
            'initial_state': 'Fresh application process and DATA_DIR with the initial administrator admin (changeme@example.com / MyPassword), group Home and household Family; listed public setup is then applied.',
            'setup': setup, 'inputs': {'account': actor, 'credentials': accounts, **(inputs or {})}, 'actor': actor, 'session': session,
            'allowed_equivalents': ['Different visible labels, page layouts, dialogs and ordinary navigation routes are valid.',
                                    'Known product page URLs may be entered in the browser; no API browsing.'],
            'forbidden_bypasses': ['Do not use APIs, developer tools, source, private files, or hidden application state to perform GUI goals.',
                                   'Do not manually recreate a missing product command.'],
            'budget': {'calls': min(400, 120 + 60 * len(steps)), 'seconds': 600 + 240 * len(steps),
                       'tokens': 600_000 + 250_000 * len(steps), **(budget or {})},
            'checkpoints': steps}


def build():
    episodes = []

    def add(*a, **kw):
        episodes.append(episode(*a, **kw))
    for name in MODULES:
        importlib.import_module(name).build(add)
    return episodes
