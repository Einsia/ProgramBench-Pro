'''Builders for the GUI episodes of ittools: goals with acceptance, reference recipes and program companions.'''

SESSION = ('Each checkpoint starts with a fresh browser profile showing the page the goal describes. Use the visible '
           'controls of the page, the menu, the search box, the keyboard and the pointer. The goal says which page to '
           'work on; the menu and the header lead to every other tool.')
EQUIVALENTS = ['Any visible route to the same result is valid: a button, the menu, a card, the command palette or a keyboard shortcut.',
               'Different labels, icons, layouts and animations are valid.']
BYPASSES = ['Do not read or change the data the page stores in the browser.',
            'Do not reach a result by typing another address when the goal asks for a control of the page.']
INITIAL = 'Fresh browser profile with the product running; each checkpoint opens its own page and is independent of the other checkpoints.'


def be(name, requirement, check, requires=()):
    return {'name': name, 'requirement': requirement, 'check': check, 'requires': list(requires)}


def cp(cid, goal, acceptance, recipe, checks=(), page='/', steps=(), requires=()):
    return {'id': cid, 'goal': goal, 'acceptance': acceptance, 'page': page, 'steps': list(steps),
            'recipe': list(recipe), 'checks': list(checks), 'requires': list(requires)}


def episode(key, feature, checkpoints):
    out = []
    for c in checkpoints:
        first = {'id': '%s/%s/visible' % (key, c['id']), 'channel': 'frontend', 'method': 'agent', 'requirement': c['acceptance']}
        if c['requires']:
            first['requires'] = ['%s/%s' % (key, r) for r in c['requires']]
        assertions = [first]
        for b in c['checks']:
            a = {'id': '%s/%s/%s' % (key, c['id'], b['name']), 'channel': 'backend', 'method': 'program',
                 'requirement': b['requirement'], 'check': dict(b['check'])}
            if b['requires']:
                a['requires'] = ['%s/%s' % (key, r) for r in b['requires']]
            assertions.append(a)
        out.append({'id': c['id'], 'goal': c['goal'], 'page': c['page'], 'steps': c['steps'], 'recipe': c['recipe'],
                    'assertions': assertions, 'depends_on': ['setup:site']})
    n = len(out)
    return {'id': key, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL, 'setup': [{'id': 'site'}],
            'inputs': {}, 'session': SESSION, 'allowed_equivalents': EQUIVALENTS, 'forbidden_bypasses': BYPASSES,
            'budget': {'calls': 30 + 30 * n, 'tokens': 400000 + 500000 * n, 'seconds': 300 + 240 * n}, 'checkpoints': out}
