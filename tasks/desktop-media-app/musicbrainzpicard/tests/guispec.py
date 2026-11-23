"""Building blocks of the GUI episode specifications (goals, acceptance, setup, checks)."""
import json
from evaluation.contract import files_path

EQUIVALENTS = ['Menus, toolbar buttons, keyboard shortcuts, context menus and dialogs are equivalent routes to a '
               'product command.',
               'Selecting files or folders in another way (the folder node, Control+A, Shift+click) is equivalent; '
               'layout, wording and widget types may differ from any reference.',
               'File dialogs take absolute paths: type the given path in the dialog\'s file-name field and confirm '
               'with Return or the dialog\'s Open/Save/Choose button.']
BYPASSES = ['Do not use terminals, remote commands, other applications or private files to perform a goal.',
            'Do not recreate a missing product command by other means, for example by editing files outside the '
            'application.']


def area_path(episode, area, relative):
    return files_path(area, relative)


def text_value(value):
    """Render an exact text input unambiguously for the evaluator."""
    if '\n' not in value:
        return '"'+value+'"'
    return 'exactly the lines between the ``` fences.\n```\n'+value+'\n```\n'


def budget(checkpoints):
    calls = min(180, 50+30*checkpoints)
    return {'calls': calls, 'seconds': min(3000, 600+300*checkpoints), 'tokens': min(2_500_000, 15_000*calls)}


def step(key, goal, acceptance, recipe, checks=(), depends=(), requires=None, lifecycle=None, preparation=()):
    """requires maps an assertion of this checkpoint ('visible' or 'state-N') to the points it counts together
    with ('state-N' of this checkpoint or '<checkpoint>/<point>')."""
    value = {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': list(recipe), 'checks': list(checks),
             'preparation': list(preparation), 'depends_on': list(depends), 'requires': dict(requires or {})}
    if lifecycle:
        value['lifecycle'] = lifecycle
    return value


def episode(key, feature, steps, *, documents=(), profile=None, load=(), start='an empty file list',
             described=None):
    """documents: (folder, name, spec, description or None); profile: settings imported before the first
    checkpoint; load: input-relative paths loaded before the first checkpoint."""
    items = []
    if documents:
        items.append({'id': 'documents', 'op': 'documents',
                      'files': [{'folder': folder, 'name': name, 'spec': spec} for folder, name, spec, _ in documents]})
    if profile:
        items.append({'id': 'profile', 'op': 'profile', 'profile': profile})
    if load:
        items.append({'id': 'load', 'op': 'load', 'paths': list(load)})
    checkpoints = []
    for cp in steps:
        cp = dict(cp)
        companions = cp.pop('requires')
        cp['depends_on'] = ['setup:'+item['id'] for item in items]+cp['depends_on']
        cp['assertions'] = [{'id': f'{key}/{cp["id"]}/visible', 'channel': 'frontend', 'method': 'agent',
                             'requirement': cp.pop('acceptance')}]
        for index, check in enumerate(cp.pop('checks')):
            cp['assertions'].append({'id': f'{key}/{cp["id"]}/state-{index+1}', 'channel': 'backend',
                                     'method': 'program',
                                     'requirement': check.get('description', 'The independently read product '
                                                              'output matches the requested checkpoint.'),
                                     'check': {k: v for k, v in check.items() if k != 'description'}})
        for assertion in cp['assertions']:
            point = assertion['id'].rsplit('/', 1)[1]
            if point in companions:
                assertion['requires'] = [f'{key}/'+(r if '/' in r else f'{cp["id"]}/{r}') for r in companions[point]]
        checkpoints.append(cp)
    listed = {area_path(key, 'inputs', f'{folder}/{name}' if folder else name): description
              for folder, name, _spec, description in documents if description}
    prepared = 'Before the first checkpoint the framework prepared: '+start+'.'
    inputs = {'documents': listed, 'folders': {'inputs': area_path(key, 'inputs', ''),
                                                'outputs': area_path(key, 'outputs', '')}}
    if described:
        inputs['notes'] = described
    value = {'id': key, 'feature': feature, 'execution': 'gui',
             'initial_state': 'Fresh application process, private desktop session and empty DATA_DIR. '+prepared,
             'setup': items, 'inputs': inputs,
             'session': 'Operate the visible desktop application only. '+prepared,
             'allowed_equivalents': EQUIVALENTS, 'forbidden_bypasses': BYPASSES,
             'budget': budget(len(steps)), 'checkpoints': checkpoints}
    return json.loads(json.dumps(value, ensure_ascii=False))
