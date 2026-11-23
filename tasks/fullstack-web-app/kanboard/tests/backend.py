"""Program episodes: the protocol checks, one isolated episode per protocol module.

Each episode runs its module's cases in their declared order against one fresh application instance. The module's
unscored fixture steps become setup items with ids that accept any successful answer; the scored steps of a scenario
depend on the fixtures of that scenario (and on the module's base fixtures), so a failed fixture blocks only its
dependents. A scored step that reads a value an earlier scored step produced, or that checks the effect of an earlier
scored step, declares that step in depends_on. A scored case is never replayed as setup. Points that a server
without the feature passes (an empty list, a refusal, false) are bound to a positive companion point of the same
episode (bindings.py).
"""
import importlib

from harness import Suite
import bindings

MODULES = ['api_jsonrpc', 'api_permissions', 'api_users', 'api_projects', 'api_board', 'api_tasks', 'api_subtasks',
           'api_comments', 'api_links', 'api_files', 'api_tags', 'api_actions', 'api_activity',
           'api_search', 'api_feeds', 'api_persistence']
REQUIREMENT = '; the answer (HTTP status, JSON-RPC result or error code) matches the reference.'
INITIAL_STATE = ('A fresh application with the initial administrator, application API token and webhook token. '
                 "The listed setup items prepare this episode's fixtures through the JSON-RPC API; scored cases are "
                 'never replayed.')


def cases_for(module):
    suite = Suite(module.removeprefix('api_'))
    importlib.import_module(module).build(suite)
    return suite.cases


CASES = {}


def case(case_id):
    """Executable case by id (built on first use)."""
    if not CASES:
        for module in MODULES:
            for c in cases_for(module):
                CASES[c.id] = c
    return CASES[case_id]


def episode(module, cases):
    key = 'protocol-' + module.removeprefix('api_').replace('_', '-')
    positions = {c.id: 'p%04d' % i for i, c in enumerate(cases) if c.channel != 'setup'}
    setup, groups, checkpoints, run = [], [], [], []

    def close(before):
        if run:
            scenarios = sorted({c.scenario for c in run})
            item = {'id': ('fx-%02d-' % len(setup) + '-'.join(scenarios))[:64], 'cases': [c.id for c in run]}
            if before:
                item['before'] = before
            setup.append(item)
            groups.append((item['id'], set(scenarios)))
            run.clear()
    for c in cases:
        if c.channel == 'setup':
            run.append(c)
            continue
        cid = positions[c.id]
        close(cid if checkpoints else None)
        depends = ['setup:' + gid for gid, scenarios in groups
                   if c.scenario in scenarios or 'base' in scenarios or scenarios & set(c.uses)]
        depends += [positions[x] for x in c.after]
        point = {'id': key + '/' + cid + '/response', 'channel': 'backend', 'method': 'program',
                 'requirement': c.description + REQUIREMENT}
        companions = list(dict.fromkeys([*c.requires, *bindings.COMPANIONS.get(c.id, ())]))
        assert all(x in positions for x in companions), 'companion outside the episode: ' + c.id
        if companions:
            point['requires'] = [key + '/' + positions[x] + '/response' for x in companions]
        checkpoints.append({'id': cid, 'case': c.id, 'goal': c.description, 'depends_on': depends,
                            'assertions': [point]})
    assert not run, 'fixture steps after the last scored case of ' + module
    return {'id': key, 'feature': module.removeprefix('api_'), 'execution': 'program', 'initial_state': INITIAL_STATE,
            'setup': setup, 'inputs': {}, 'checkpoints': checkpoints}


def build():
    return [episode(module, cases_for(module)) for module in MODULES]
