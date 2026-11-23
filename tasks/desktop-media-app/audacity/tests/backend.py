"""Program checks grouped into isolated bounded episodes.

Each program episode gets a fresh runtime instance and runs a contiguous slice
of the case modules, starting at a scenario boundary. Every scenario prepares
its own state through public scripting and uploaded input documents; those
preparation rows are positional setup items that run right before the
scenario's first checkpoint, and the scenario's checkpoints declare them, so a
failed preparation blocks only its own scenario. A scored row whose
earlier step in the same scenario did not complete is blocked by its
preparation check instead of failing in cascade. No scored row is
replayed as setup. Each scored row is one backend assertion compared with the
frozen standard observation.
"""
import importlib
from harness import Suite

MODULES = ('backend_cases', 'import_export_cases', 'persistence_cases')
LIMIT = 120
# Scenarios that restart the application or open a fresh instance are slow;
# smaller slices keep each episode's wall time short.
LIMITS = {'import-export': 30, 'persistence': 40}
FEATURES = (
    ('history', ('history-multilevel',)),
    ('editing', ('edit-', 'empty-edit')),
    ('effects', ('effect-', 'mix-stereo-to-mono')),
    ('mixing', ('gain-pan', 'mute-solo', 'envelope', 'mix-render', 'track-align')),
    ('tracks', ('tracks',)),
    ('labels', ('labels',)),
    ('selection', ('selection',)),
    ('project', ('project-rate', 'project-name')),
    ('analysis', ('analysis-',)),
    ('import-export', ('import-fixture', 'export-fixture')),
    ('generation', ('generator',)),
    ('malformed-input', ('negative-import',)),
    ('persistence', ('project-', 'preference-restart')),
)


def feature(family):
    for base in (family, family.removesuffix('-fixture')):
        for name, prefixes in FEATURES:
            if any(base == p or base.startswith(p) for p in prefixes):
                return name
    raise ValueError('unclassified program family '+family)


def cases_for(module):
    suite = Suite()
    importlib.import_module(module).build(suite)
    return suite.cases


def scenario_key(case):
    return feature(case.family), case.scenario


def slices(cases):
    """Consecutive same-feature scenarios, cut at scenario boundaries after LIMIT scored rows; an attached
    scenario stays with the one before it."""
    begin, scored, current = 0, 0, None
    for index, case in enumerate(cases):
        boundary = index == 0 or scenario_key(case) != scenario_key(cases[index-1])
        name = feature(case.family)
        if boundary and index and not case.attached and (name != current or scored >= LIMITS.get(current, LIMIT)):
            yield current, begin, index
            begin, scored = index, 0
        current = name
        scored += case.channel != 'setup'
    yield current, begin, len(cases)


def build():
    episodes, parts = [], {}
    for module in MODULES:
        cases = cases_for(module)
        for name, begin, end in slices(cases):
            parts[name] = parts.get(name, 0)+1
            key = f'program-{name}-{parts[name]:02d}'
            setup, checkpoints, latest, pending = [], [], {}, []
            assertion_of = {}
            for index in range(begin, end):
                case = cases[index]
                if case.channel == 'setup':
                    item = {'id': f's{index:04d}', 'case': index, 'description': case.description}
                    setup.append(item)
                    pending.append(item)
                    latest[scenario_key(case)] = item['id']
                    continue
                cid = f'p{index:04d}'
                for item in pending:
                    item['before'] = cid
                pending = []
                depends = [f'setup:{latest[scenario_key(case)]}'] if scenario_key(case) in latest else []
                assertion = {'id': key+'/'+cid+'/result', 'channel': 'backend', 'method': 'program',
                             'requirement': case.description+'; the independently observed product state, '
                             'scripting reply or decoded artifact matches the recorded standard within the '
                             'documented tolerances.'}
                assertion_of[case.id] = assertion['id']
                if case.requires:
                    missing = [r for r in case.requires if r not in assertion_of]
                    assert not missing, f'companion of {case.id} is not an earlier point of {key}: {missing}'
                    assertion['requires'] = [assertion_of[r] for r in case.requires]
                checkpoint = {'id': cid, 'goal': case.description, 'case': index, 'depends_on': depends,
                              'assertions': [assertion]}
                if case.needs is not None:
                    checkpoint['prepare'] = 'Blocked unless the earlier steps of this scenario completed.'
                checkpoints.append(checkpoint)
            assert not pending, f'{key} ends with setup rows that precede no checkpoint'
            episodes.append({'id': key, 'feature': name, 'execution': 'program',
                'initial_state': 'Fresh application process, desktop session and empty DATA_DIR. Each scenario '
                                 'prepares its own state through public scripting commands and uploaded input '
                                 'documents (setup items right before its first checkpoint).',
                'program': {'module': module, 'begin': begin, 'end': end},
                'setup': setup, 'inputs': {}, 'checkpoints': checkpoints})
    return episodes
