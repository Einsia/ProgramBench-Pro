"""Manifest constructors and public-interface recipes."""
import json
import re

import fixtures as F


# The evaluator forecasts later checkpoints from recent round-trip latency.
# These episodes need additional time headroom when a model request retries.
GUI_TIME_BUDGETS = {name:10800 for name in (
    'gui-navigation-3','gui-reading-2','gui-search-1',
    'gui-sorting-1','gui-sorting-3','gui-sorting-4')}

def slug(text):
    return re.sub('[^a-z0-9]+', '-', text.lower()).strip('-')


def quote(text):
    return json.dumps(text, ensure_ascii=False)


def K(key):
    return {'key': key}


def C(command):
    return {'cmd': command}


def P(text):
    return {'prompt': text}


def S(*parts):
    return [step for part in parts for step in (part if isinstance(part, list) else [part])]


def select(n):
    return [K('Home')] + [K('Down')] * n


def feed(n=0):
    return select(n) + [K('Enter')]


def article(n=0):
    return select(n) + [K('Enter')]


def scr(fact, **kw):
    return dict(kind='screen', fact=fact, **kw)


def labels(names=F.ALL_TITLES, **kw):
    return scr('labels', labels=list(names), **kw)


def focus(names=F.ALL_TITLES):
    return scr('focus', labels=list(names), nonempty=True)


def contains(*needles):
    return scr('contains', needles=list(needles), expected={'contains': list(needles)})


def cache(columns, where=None, table='rss_item', **kw):
    return dict(kind='cache', table=table, columns=columns.split() if isinstance(columns, str) else columns,
                where=where or {}, **kw)


def file(path, mode='lines', **kw):
    return dict(kind='file', path=path, mode=mode, **kw)


def cli(args, part='stdout', **kw):
    return dict(kind='cli', args=args, part=part, **kw)


def point(name, check, requirement=None):
    return (name, requirement or name.replace('-', ' ').capitalize() + '.', check)


def cp(name, goal, steps, checks=(), acceptance=None, depends=()):
    return dict(id=name, goal=goal, steps=steps, checks=list(checks), acceptance=acceptance,
                depends_on=list(depends))


def episode(name, feature, checkpoints, *, files=None, load=True, before=(), gui=False, setup=(), session=''):
    if files is None:
        files = F.library()
    prep = [{'id': 'fixtures', 'op': 'place', 'files': files}]
    if load:
        prep.append({'id': 'loaded', 'op': 'drive', 'steps': [{'cli': ['-x', 'reload']}]})
    if before:
        prep.append({'id': 'positioned', 'op': 'drive', 'steps': list(before)})
    prep.extend(setup)
    dependencies = ['setup:' + p['id'] for p in prep if not p.get('before')]
    for c in checkpoints:
        c['depends_on'] = dependencies + c['depends_on']
        c['assertions'] = [dict(id=f'{name}/{c["id"]}/{suffix}', channel='backend', method='program',
                                requirement=requirement, check=check) for suffix, requirement, check in c.pop('checks')]
        for a in c['assertions']:
            if a['check'].get('fact')=='message':
                companions=[x['id'] for x in c['assertions'] if x is not a and
                            (x['check']['kind']=='cache' or x['check'].get('fact') in ('exited','focus','labels'))]
                if companions:a['requires']=companions
        acceptance = c.pop('acceptance')
        if acceptance:
            texts = [acceptance] if isinstance(acceptance, str) else acceptance
            c['assertions'] += [dict(id=f'{name}/{c["id"]}/visible-{i+1}', channel='frontend', method='agent',
                                    requirement=text) for i, text in enumerate(texts)]
    w = dict(id=name, feature=feature, execution='gui' if gui else 'program',
             initial_state='A fresh Newsboat home with local subscriptions and the supplied fixture files.',
             inputs={}, setup=prep, checkpoints=checkpoints)
    if gui:
        w.update(session=('The local subscriptions have been loaded. Use the terminal to reach each goal. '
                          'The current dialog has help on ?. Colon opens the command line; the runtime help '
                          'lists its command names. Paths beginning ~/ name the application home. ' + session),
                 allowed_equivalents=['Any terminal operation or application command that achieves the stated '
                                      'result is equivalent. Selection must be visibly identifiable.'],
                 forbidden_bypasses=['Do not use external programs or modify files outside the application.'],
                 budget={'calls': 180, 'tokens': 1800000, 'seconds': GUI_TIME_BUDGETS.get(name,1800)})
    return w


def scenarios(name, feature, cases, *, gui=False, chunk=5):
    """Independent scenarios share an episode/conversation, never a preceding case's mutable state."""
    result=[]
    for offset in range(0,len(cases),chunk):
        cps,setup=[],[]
        for case in cases[offset:offset+chunk]:
            c,files,before=case
            prep='prepare-'+c['id']
            c['depends_on'].append('setup:'+prep)
            setup.append(dict(id=prep,before=c['id'],op='drive',steps=S({'reset':True},
                         {'place':files or F.library()}, {'cli':['-x','reload']},before)))
            cps.append(c)
        result.append(episode(name+'-'+str(offset//chunk+1),feature,cps,load=False,setup=setup,gui=gui,
                               session='Each goal starts from its own freshly prepared state shown in its before observation.'))
    return result
