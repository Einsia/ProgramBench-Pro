'''Builders for the program episodes of ittools: stimuli (raw runtime requests and the pseudo steps of hooks.py) and the observation specs of checks.py.'''

NL = chr(10)
INITIAL = ('Fresh browser profile (reset) with the product running; each checkpoint opens its own page, applies its steps and is independent of the other checkpoints.')


# -- stimuli -------------------------------------------------------------------------------------------
def fill(value, label=None, placeholder=None, nth=0):
    target = {'label': label} if label is not None else {'placeholder': placeholder}
    if nth:
        target['nth'] = nth
    return {'op': 'fill', 'target': target, 'value': value}


def typed(value):
    return {'op': 'type', 'value': value}


def press(key):
    return {'op': 'press', 'key': key}


def click(text, nth=0):
    target = {'text': text}
    if nth:
        target['nth'] = nth
    return {'op': 'click', 'target': target}


def switch(index):
    return {'op': 'click', 'target': {'role': 'switch', 'nth': index}}


def box(index):
    return {'op': 'click', 'target': {'role': 'checkbox', 'nth': index}}


def choose(current, option, search=None, nth=0, current_nth=0):
    step = {'op': 'choose', 'current': current, 'option': option}
    if search is not None:
        step['search'] = search
    if nth:
        step['nth'] = nth
    if current_nth:
        step['current_nth'] = current_nth
    return step


def copy_after(field, field_nth=0, nth=0):
    '''The button that follows the named field (a copy button follows its result field).'''
    step = {'op': 'click-after', 'field': field}
    if field_nth:
        step['field_nth'] = field_nth
    if nth:
        step['nth'] = nth
    return step


def clock(seconds):
    return {'op': 'clock', 'seconds': seconds}


def wait(seconds=0.5):
    return {'op': 'wait', 'seconds': seconds}


def reload():
    return {'op': 'reload'}


def toolbar(index, size=16):
    '''The button at a place in a row of unnamed buttons (an editor toolbar).'''
    return {'op': 'toolbar', 'index': index, 'size': size}


def last_button():
    '''The unnamed button lowest on the page (the copy button of the result block).'''
    return {'op': 'click-last'}


def monaco(side, text):
    '''Replace the text of one side of a monaco editor pair (0 left, 1 right); an empty text clears it.'''
    return {'op': 'monaco-set', 'side': side, 'text': text}


def select_editor(starts='Hey!'):
    '''Click the rich text editor whose text starts so and select all of its text.'''
    return {'op': 'edit-select-all', 'starts': starts}


def upload(name, mime='application/octet-stream'):
    return {'op': 'upload-file', 'file': name, 'mime': mime}


# -- observation specs (see checks.observe) -----------------------------------------------------------
def out(index):
    return {'type': 'outputs', 'start': index, 'stop': index + 1}


def outs(start=None, stop=None, labels=False, allow_empty=False):
    spec = {'type': 'outputs'}
    if start is not None:
        spec['start'] = start
    if stop is not None:
        spec['stop'] = stop
    if labels:
        spec['labels'] = True
    if allow_empty:
        spec['allow_empty'] = True
    return spec


def fields(*names):
    return {'type': 'fields', 'names': list(names)}


def blocks(allow_empty=False):
    spec = {'type': 'blocks'}
    if allow_empty:
        spec['allow_empty'] = True
    return spec


def lines(start=None, stop=None, skip=0, partial=False, reading=None, count=None):
    '''Text lines of the tool area; reading 'values' adds the text of value controls, 'all' that of every control;
    count keeps only that many lines (after start), leaving out transient messages that follow a result.'''
    spec = {'type': 'lines'}
    if reading is not None:
        assert reading in ('values', 'all')
        spec['reading'] = reading
    if start is not None:
        spec['start'] = start
    if stop is not None:
        spec['stop'] = stop
    if skip:
        spec['skip'] = skip
    if partial:
        spec['partial'] = True
    if count is not None:
        spec['count'] = count
    return spec


def clip():
    return {'type': 'clipboard'}


def toggles():
    return {'type': 'toggles'}


def address():
    return {'type': 'page'}


def source(where, **kw):
    '''Where a value is read: output, input or block (by index), field (by name) or clipboard.'''
    spec = {'from': where}
    spec.update(kw)
    return spec


def carry(src, **target):
    '''Type the value read from src into the field named by target (label or placeholder, optional nth).'''
    return {'op': 'carry', 'source': src, 'target': target}


def remember(src, name='before'):
    return {'op': 'remember', 'source': src, 'as': name}


def changed(src, name='before'):
    '''Whether the value read from src differs from the one remembered under name.'''
    return {'type': 'changed', 'source': src, 'name': name}


def menu():
    '''Tool and category names outside the tool area (the menu), in order.'''
    return {'type': 'menu'}


def cards():
    '''Tool names inside the tool area of the home page (its tool cards), in order.'''
    return {'type': 'cards'}


def controls(**kw):
    spec = {'type': 'controls'}
    spec.update(kw)
    return spec


def multi(**named):
    return {'type': 'multi', 'checks': named}


def shape(source, **kw):
    spec = {'type': 'shape', 'from': source}
    spec.update(kw)
    return spec


# -- assembly -------------------------------------------------------------------------------------------
def point(name, requirement, check, requires=(), tol=None):
    check = dict(check)
    if tol is not None:
        check['tol'] = tol
    return {'name': name, 'requirement': requirement, 'check': check, 'requires': list(requires)}


def case(cid, goal, page, steps, points):
    return {'id': cid, 'goal': goal, 'page': page, 'steps': list(steps), 'points': list(points)}


def bind(cases, mapping):
    '''Bind the points of the named cases to a positive point of the same episode (case/point): a refusal, an empty
    result or an unchanged or restored state that a page ignoring the input would also show only counts with it.'''
    named = {c['id']: c for c in cases}
    for cid, required in mapping.items():
        for p in named[cid]['points']:
            p['requires'] = sorted(set(p['requires']) | {required})
    return cases


def episode(key, feature, cases):
    checkpoints = []
    for c in cases:
        assertions = []
        for p in c['points']:
            a = {'id': '%s/%s/%s' % (key, c['id'], p['name']), 'channel': 'backend', 'method': 'program',
                 'requirement': p['requirement'], 'check': p['check']}
            if p['requires']:
                a['requires'] = ['%s/%s' % (key, r) for r in p['requires']]
            assertions.append(a)
        checkpoints.append({'id': c['id'], 'goal': c['goal'], 'page': c['page'], 'steps': c['steps'],
                            'assertions': assertions, 'depends_on': ['setup:site']})
    return {'id': key, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL,
            'setup': [{'id': 'site'}], 'inputs': {}, 'checkpoints': checkpoints}
