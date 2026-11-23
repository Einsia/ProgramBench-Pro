"""Program checks grouped into isolated bounded episodes.

Each program episode gets a fresh runtime instance and runs a contiguous slice of a case module, starting at a
scenario boundary. Every scenario prepares its own state (fresh instance, settings profile, uploaded documents);
those preparation rows are setup items that run right before the scenario's first checkpoint, and the scenario's
checkpoints declare them, so a failed preparation blocks only its own scenario. A scored row whose earlier step in
the same scenario did not complete is blocked instead of failing in cascade. No scored row is replayed as setup.
Each scored row is one backend assertion compared with the frozen standard observation.
"""
import importlib
from harness import Suite

MODULES = ('cases_commands', 'cases_cluster', 'cases_profiles')
FEATURES = {'remote-commands': 'remote-commands', 'clustering': 'clustering', 'profiles-cli': 'profiles',
            'cli': 'profiles'}
# Scored rows per program episode (scenarios are never split).
LIMIT = 40


def cases_for(module):
    suite = Suite()
    importlib.import_module(module).build(suite)
    return suite.cases


def slices(cases):
    """Consecutive scenarios of one feature, cut at scenario boundaries after LIMIT scored rows."""
    if not cases:
        return
    begin, scored = 0, 0
    for index, case in enumerate(cases):
        boundary = index == 0 or case.scenario != cases[index-1].scenario
        if boundary and index and (FEATURES[case.family] != FEATURES[cases[begin].family] or scored >= LIMIT):
            yield FEATURES[cases[begin].family], begin, index
            begin, scored = index, 0
        scored += case.channel != 'setup'
    yield FEATURES[cases[begin].family], begin, len(cases)


def build():
    episodes, parts = [], {}
    for module in MODULES:
        cases = cases_for(module)
        for name, begin, end in slices(cases):
            parts[name] = parts.get(name, 0)+1
            key = f'program-{name}-{parts[name]:02d}'
            setup, checkpoints, latest, pending, assertion_of = [], [], {}, [], {}
            for index in range(begin, end):
                case = cases[index]
                if case.channel == 'setup':
                    item = {'id': f's{index:04d}', 'case': index, 'description': case.description}
                    setup.append(item)
                    pending.append(item)
                    latest[case.scenario] = item['id']
                    continue
                cid = f'p{index:04d}'
                for item in pending:
                    item['before'] = cid
                pending = []
                depends = [f'setup:{latest[case.scenario]}'] if case.scenario in latest else []
                assertion = {'id': key+'/'+cid+'/result', 'channel': 'backend', 'method': 'program',
                             'requirement': case.description+'; the observed product output matches the recorded '
                             'standard.'}
                assertion_of[case.id] = assertion['id']
                if case.requires:
                    missing = [r for r in case.requires if r not in assertion_of]
                    assert not missing, f'companion of {case.id} is not an earlier point of {key}: {missing}'
                    assertion['requires'] = [assertion_of[r] for r in case.requires]
                checkpoints.append({'id': cid, 'goal': case.description, 'case': index, 'depends_on': depends,
                                    'assertions': [assertion]})
            assert not pending, f'{key} ends with setup rows that precede no checkpoint'
            episodes.append({'id': key, 'feature': name, 'execution': 'program',
                              'initial_state': 'Fresh application process, desktop session and empty DATA_DIR. Each '
                                               'scenario prepares its own state: a fresh instance, a settings '
                                               'profile imported with picard-cli, and uploaded documents (setup '
                                               'items right before its first checkpoint).',
                              'program': {'module': module, 'begin': begin, 'end': end},
                              'setup': setup, 'inputs': {}, 'checkpoints': checkpoints})
    return episodes
