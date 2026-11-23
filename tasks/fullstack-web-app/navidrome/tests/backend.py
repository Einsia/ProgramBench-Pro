'''Program episodes: one isolated episode per protocol module.

Each episode runs its module cases in their declared order against one fresh application instance. The common
setup item creates the administrator and two ordinary accounts and scans the fixture library; the unscored fixture
cases of a module become further setup items with ids, so a failed fixture blocks only the checkpoints that follow
it. A scored case is never replayed as setup. A point that a server without the feature passes (an empty list, a
denial) is bound to a positive companion point of the same episode (COMPANIONS of the module); a case that needs
the state made by an earlier scored case names it in DEPENDS.
'''
import importlib

from harness import Suite

MODULES = ['api_browse', 'api_users', 'api_playlists', 'api_social', 'api_library', 'api_scan', 'api_tags', 'api_persist', 'api_more', 'api_perms', 'api_format', 'api_native', 'api_sorts', 'api_smart', 'api_lyrics', 'api_libraries', 'api_shares', 'api_artwork', 'api_media']
REQUIREMENT = '; preserve public content, authorization and resource relationships.'
INITIAL_STATE = ('A fresh application in its first-run state. The listed setup items create the administrator, two '
                 'ordinary accounts and the scanned music library through the product public interfaces; scored cases '
                 'are never replayed.')
BOOTSTRAP = {'id': 'fx-bootstrap', 'bootstrap': True}
CASES = {}


def load(module):
    return importlib.import_module(module)


def cases_for(module):
    suite = Suite()
    load(module).build(suite)
    return suite.cases


def case(case_id):
    if not CASES:
        for module in MODULES:
            for c in cases_for(module):
                CASES[c.id] = c
    return CASES[case_id]


def name_of(module):
    return module.removeprefix('api_').replace('_', '-')


def episode(module):
    mod = load(module)
    cases = cases_for(module)
    companions = getattr(mod, 'COMPANIONS', {})
    needs = getattr(mod, 'DEPENDS', {})
    key = 'protocol-' + name_of(module)
    scored = [c for c in cases if c.channel != 'setup']
    positions = {c.id: 'p%04d' % i for i, c in enumerate(scored)}
    setup, checkpoints, groups, run = [dict(BOOTSTRAP)], [], [], []

    def close(before):
        if not run:
            return
        item = {'id': 'fx-%s-%d' % (name_of(module), len(groups) + 1), 'cases': [c.id for c in run]}
        if before:
            item['before'] = before
        setup.append(item)
        groups.append(item['id'])
        run.clear()

    for c in cases:
        if c.channel == 'setup':
            run.append(c)
            continue
        close(positions[c.id] if checkpoints else None)
        cid = positions[c.id]
        depends = ['setup:' + g for g in ['fx-bootstrap'] + groups]
        for earlier in needs.get(c.id, ()):
            assert earlier in positions and positions[earlier] < cid, 'a dependency must be an earlier case: ' + c.id
            depends.append(positions[earlier])
        point = {'id': key + '/' + cid + '/response', 'channel': 'backend', 'method': 'program',
                 'requirement': c.description + REQUIREMENT}
        required = [key + '/' + positions[x] + '/response' for x in companions.get(c.id, ())]
        assert all(x in positions for x in companions.get(c.id, ())), 'companion outside the episode: ' + c.id
        if required:
            point['requires'] = required
        checkpoints.append({'id': cid, 'case': c.id, 'goal': c.description, 'depends_on': depends, 'assertions': [point]})
    assert not run, 'fixture cases need a scored case after them'
    return {'id': key, 'feature': name_of(module), 'execution': 'program', 'initial_state': INITIAL_STATE,
            'setup': setup, 'inputs': {}, 'checkpoints': checkpoints}


def build():
    return [episode(module) for module in MODULES]
