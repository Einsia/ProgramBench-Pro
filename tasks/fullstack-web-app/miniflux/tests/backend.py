"""Program episodes: one isolated episode per protocol module.

Each episode runs its module's cases in their declared order against one fresh application instance.
The module's unscored fixture cases become setup items (any success status); a checkpoint declares the
fixture groups and earlier cases it needs, so a failed fixture or a failed earlier case blocks only its
dependents. A scored case is never replayed as setup. Points that a server without the feature passes
(an empty list, a refusal, an unchanged state) are bound (requires) to positive points of the same
episode. A module may open with browser checkpoints that the evaluator operates (mixed episodes):
settings that only the web interface offers, followed by the program checks that use them.
"""
import importlib

from harness import CREDS, Suite

MODULES = ['api_users', 'api_categories', 'api_feeds', 'api_fetch', 'api_entries', 'api_search', 'api_opml',
           'api_discovery', 'api_refresh', 'api_media', 'api_icons', 'parse_rss', 'parse_atom', 'parse_json', 'parse_rdf',
           'content_sanitize', 'content_rewrite', 'content_urls', 'content_filters', 'content_scraper',
           'api_fever', 'api_greader', 'api_integrations', 'api_persistence']
REQUIREMENT = '; preserve the public content, status codes, errors and relationships of the response.'
INITIAL_STATE = ('A fresh application with the three baseline accounts and an empty local web (its example site '
                 'only). The listed setup items publish this episode\'s resources in the local web and prepare '
                 'fixtures through the product\'s public interfaces; scored cases are never replayed.')


def module_cases(module):
    suite = Suite(prefix=module + ':')
    importlib.import_module(module).build(suite)
    return suite.cases


CASES = {}


def case(case_id):
    """Executable case by id (built on first use)."""
    if not CASES:
        for module in available():
            for c in module_cases(module):
                CASES[c.id] = c
    return CASES[case_id]


def available():
    return list(MODULES)


def episode_id(module):
    return 'protocol-' + module.removeprefix('api_').replace('_', '-')


def episode(module, cases):
    key = episode_id(module)
    setup, checkpoints = [], []
    position = {}
    groups = {}  # fixture group -> setup ids created so far
    run = []

    def close(before):
        if not run:
            return
        group = run[0].family
        count = len(groups.get(group, []))
        item = {'id': 'fx-' + group + ('' if not count else '-' + str(count + 1)), 'cases': [c.id for c in run]}
        if before:
            item['before'] = before
        setup.append(item)
        groups.setdefault(group, []).append(item['id'])
        run.clear()

    # Checkpoint ids first, so that companions may name points defined later in the module.
    scored = [c for c in cases if c.channel not in ('check', 'setup')]
    position.update({c.id: 'p%04d' % i for i, c in enumerate(scored)})
    gui = 0
    for c in cases:
        if c.channel == 'check':
            continue
        if c.channel == 'setup':
            if run and run[-1].family != c.family:
                close('p%04d' % len(checkpoints) if checkpoints else None)
            run.append(c)
            continue
        cid = 'p%04d' % len(checkpoints)
        close(cid if checkpoints else None)
        depends = []
        for need in c.needs:
            if need.startswith('fx:'):
                depends += ['setup:' + x for x in groups.get(need[3:], [])]
            else:
                assert int(position[need][1:]) < len(checkpoints), f'{c.id} needs a later case: {need}'
                depends.append(position[need])
        required = [bound(cases, key, position, x) for x in c.requires]
        if c.channel == 'ui':
            gui += 1
            assertions = [{'id': key + '/' + cid + '/visible', 'channel': 'frontend', 'method': 'agent',
                           'requirement': c.gui['acceptance']}]
            for i, check in enumerate(c.gui['checks']):
                assertions.append({'id': key + '/' + cid + f'/state-{i + 1}', 'channel': 'backend',
                                   'method': 'program', 'check': check,
                                   'requirement': case(check).description + REQUIREMENT})
            if required:
                assertions[0]['requires'] = required
            cp = {'id': cid, 'case': c.id, 'goal': c.gui['goal'], 'depends_on': depends,
                  'recipe': c.gui['recipe'], 'assertions': assertions}
        else:
            point = {'id': key + '/' + cid + '/response', 'channel': 'backend', 'method': 'program',
                     'requirement': c.description + REQUIREMENT}
            if required:
                point['requires'] = required
            cp = {'id': cid, 'case': c.id, 'goal': c.description, 'depends_on': depends, 'assertions': [point]}
        assert position[c.id] == cid
        checkpoints.append(cp)
    close(None)
    value = {'id': key, 'feature': module.split('_', 1)[1] if module.startswith(('api_', 'parse_', 'content_'))
             else module, 'execution': 'mixed' if gui else 'program', 'initial_state': INITIAL_STATE,
             'setup': setup, 'inputs': {}, 'checkpoints': checkpoints}
    if module.startswith('parse_'):
        value['feature'] = 'feed-parsing'
    elif module.startswith('content_'):
        value['feature'] = 'content-processing'
    if gui:
        value.update(inputs={'account': 'alice', 'credentials': {'alice': CREDS['alice']}},
                     session='Sign in with the supplied account before the goal; this is unscored preparation.',
                     allowed_equivalents=['Equivalent visible settings controls and routes.'],
                     forbidden_bypasses=['Change settings through visible controls; do not use APIs instead.'],
                     budget=getattr(importlib.import_module(module), 'BUDGET', None) or
                     {'calls': min(160, 45 + 25 * gui), 'seconds': min(1800, 480 + 180 * gui),
                      'tokens': min(1_500_000, 350_000 + 180_000 * gui)}, actor='alice')
    return value


def bound(cases, key, position, case_id):
    """The point a companion binding names: a program case's response, or the first state check of a browser
    checkpoint (its state, not its display), or its visible point when it has no state check."""
    target = next(c for c in cases if c.id == case_id)
    if target.channel == 'ui':
        return key + '/' + position[case_id] + ('/state-1' if target.gui['checks'] else '/visible')
    return key + '/' + position[case_id] + '/response'


def build():
    return [episode(module, module_cases(module)) for module in available()]
