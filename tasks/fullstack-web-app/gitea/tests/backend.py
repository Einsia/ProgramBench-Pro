"""Program episodes: the retained protocol checks, one isolated episode per protocol module.

Each episode runs its module's cases in their declared order against one fresh
application instance. The module's unscored fixture cases become setup items
with ids that accept any success status; checkpoints that need a fixture declare
it (setup:<id>), so a failed fixture blocks only its dependents. A scored case is
never replayed as setup. Points that a server without the feature passes (an
empty list, a denial, a "gone" read) are bound to a positive companion point of
the same episode (bindings.py). No candidate UI selector runs in a program
episode; the single GUI checkpoint of the wiki episode is operated by the
evaluator.
"""
import importlib
from dataclasses import replace

from harness import CREDS, Suite
import bindings

MODULES = ['api_accounts', 'api_coverage_gaps', 'api_repositories', 'api_permissions', 'api_git', 'git_write',
           'api_issues', 'api_notifications', 'api_organizations', 'api_pulls', 'pull_review_episodes',
           'api_releases_wiki', 'api_packages_lfs', 'protocol_persistence']
REQUIREMENT = '; preserve public content, authorization and resource relationships.'
INITIAL_STATE = ('A fresh application with the public three-account baseline. The listed setup items prepare this '
                 "episode's fixtures through the product's public interfaces; scored cases are never replayed.")


def review_api(case):
    """The review gate's browser steps, expressed through the public API for the protocol episode."""
    def action(c):
        scenario = case.scenario
        key = 'review-gate-' + scenario
        ep = f"repos/alice/pbp-review-gate-{scenario}/pulls/{c.state[key]['number']}"
        stage = case.id.rsplit('.', 1)[1]
        if stage == 'merge-browser':
            c.pull_ready(ep, True)
            r, p = c.request('POST', ep + '/merge', 'bob', body={'Do': 'merge'})
            assert r.status_code == 200
            r, p = c.request('GET', ep, 'alice')
            assert p['merged'] and p['state'] == 'closed'
        else:
            event, body, actor, suffix = {
                'request-changes-browser': ('REQUEST_CHANGES', 'Please address the requested changes', 'carol',
                                            '-rejected'),
                'resolve-with-approval-browser': ('APPROVED', 'Requested changes are addressed', 'carol',
                                                  '-approved-carol'),
                'second-approval-browser': ('APPROVED', 'Second independent approval', 'alice', '-approved-alice'),
            }[stage]
            r, p = c.request('POST', ep + '/reviews', actor, body={'event': event, 'body': body})
            assert r.status_code == 200
            assert p['state'] == event and p['body'] == body
            c.state[key + suffix] = p
        return c.observe(r, p)
    return action


def delete_version(c):
    r, before = c.request('GET', 'packages/alice/generic/pbp-generic/1.0.0/files')
    assert r.status_code == 200
    r, p = c.request('DELETE', 'packages/alice/generic/pbp-generic/2.0.0-rc.1')
    assert r.status_code == 204
    r, after = c.request('GET', 'packages/alice/generic/pbp-generic/1.0.0/files')
    assert r.status_code == 200 and before == after
    return {'deleted': '2.0.0-rc.1', 'other_version_preserved': True}


def cases_for(module):
    """The module's executable cases in order: fixtures (setup), protocol cases and the GUI steps kept as API
    equivalents. Reference-only GUI registrations are not cases of a program episode."""
    suite = Suite()
    importlib.import_module(module).build(suite)
    cases = []
    for case in suite.cases:
        if case.channel == 'ui':
            if module == 'pull_review_episodes':
                case = replace(case, channel='api', action=review_api(case))
            elif case.id == 'ui.package-delete.generic-prerelease.confirm':
                case = replace(case, channel='api', action=delete_version)
            elif module == 'api_releases_wiki' and case.family == 'wiki-settings':
                pass
            else:
                continue
        cases.append(case)
    return cases


CASES = {}


def case(case_id):
    """Executable case by id (built on first use, per module)."""
    if not CASES:
        for module in MODULES:
            for c in cases_for(module):
                CASES[c.id] = c
    return CASES[case_id]


def group_id(run):
    """A contiguous run of one fixture family is one setup item."""
    scenarios = {c.scenario for c in run}
    return 'fx-' + run[0].family.removesuffix('-fixture') + ('-' + run[0].scenario if len(scenarios) == 1 else '')


def serves(module, fixture, scored):
    """Whether a scored case needs a fixture group's state (it is blocked when the group fails)."""
    family = fixture.family.removesuffix('-fixture')
    if module == 'api_permissions':
        if family == 'permission-validation':
            return scored.family == 'permission-validation'
        visibility, grant = fixture.scenario.split('-', 1)
        roles = ['anonymous', 'outsider', 'owner', 'siteadmin'] if grant == 'none' else ['collaborator-' + grant]
        if scored.family == 'permission-revoke':
            return grant != 'none' and scored.scenario == fixture.scenario
        return scored.family.startswith('permission-') and scored.scenario in [visibility + '-' + r for r in roles]
    if module == 'api_coverage_gaps':
        return scored.family == family
    if module == 'api_notifications':
        return scored.scenario == fixture.scenario or scored.scenario.startswith(fixture.scenario + '-')
    if module == 'api_pulls':
        return scored.scenario == fixture.scenario or (
            fixture.scenario == 'closed' and scored.family in ('pull-validation', 'commit-status', 'branch-protection'))
    if module == 'pull_review_episodes':
        return scored.scenario == fixture.scenario
    if module == 'api_packages_lfs':
        return scored.family.startswith('lfs-') and scored.family != 'lfs-validation' \
            and scored.scenario.split('-')[0] == fixture.scenario
    if module == 'api_organizations':
        return scored.family == 'team-unit-access' and fixture.scenario in ('private-repo', scored.scenario)
    # Modules whose fixtures prepare one shared subject: every scored case depends on them.
    return True


# Wiki pages exist only after their creation: their later points depend on it (the first creation also shows
# whether the wiki interface works at all, with or without the reference's wiki-branch setting).
def wiki_dependency(cases, scored):
    if not scored.family.startswith('wiki') or scored.family == 'wiki-settings':
        return None
    scenario = 'home' if scored.family == 'wiki-pagination' else scored.scenario
    if scored.family == 'wiki' and scored.id.endswith('.create'):
        return None
    return 'api.wiki.' + scenario + '.create'


def parts(module, cases):
    """(episode id, case indices). Releases and the wiki share no state and become separate episodes."""
    key = 'protocol-' + module.removeprefix('api_')
    if module != 'api_releases_wiki':
        return [(key, list(range(len(cases))))]
    fixtures = [i for i, c in enumerate(cases) if c.channel == 'setup']
    wiki = [i for i, c in enumerate(cases) if c.family.startswith('wiki')]
    releases = [i for i, c in enumerate(cases) if c.channel != 'setup' and i not in wiki]
    return [('protocol-releases', fixtures + releases), ('protocol-wiki', fixtures + wiki)]


# Unscored reads of the baseline accounts that some cases refer to (user ids in repository search filters).
BASELINE = {'api_repositories': ['alice', 'bob', 'carol']}


def uses_baseline(case):
    return case.family == 'repository-search' and case.scenario.rsplit('-', 1)[-1] in ('owner', 'starred')


def episode(module, key, cases, selection):
    positions = {cases[i].id: 'p%04d' % i for i in selection}
    setup, groups, checkpoints, run = [], [], [], []
    if module in BASELINE:
        setup.append({'id': 'fx-baseline-users', 'users': BASELINE[module]})

    def close(before):
        if run:
            item = {'id': group_id(run), 'cases': [c.id for c in run]}
            if before:
                item['before'] = before
            assert item['id'] not in {x['id'] for x in setup}, 'duplicate setup id ' + item['id']
            setup.append(item)
            groups.append((item['id'], run[0]))
            run.clear()
    for i in selection:
        c = cases[i]
        if c.channel == 'setup':
            if run and run[-1].family != c.family:
                close(None if not checkpoints else 'p%04d' % i)
            run.append(c)
            continue
        close('p%04d' % i if checkpoints else None)
        cid = positions[c.id]
        depends = ['setup:' + gid for gid, fixture in groups if serves(module, fixture, c)]
        if module in BASELINE and uses_baseline(c):
            depends.insert(0, 'setup:fx-baseline-users')
        prior = wiki_dependency(cases, c)
        if prior and prior in positions:
            depends.append(positions[prior])
        if c.channel == 'ui':
            cp = {'id': cid, 'case': c.id,
                  'goal': 'Set the Wiki default branch for alice/pbp-publish to master through '
                          '/alice/pbp-publish/settings, save and reload.',
                  'depends_on': depends, 'recipe': [{'op': 'wiki-branch'}], 'visible': [],
                  'assertions': [{'id': key + '/' + cid + '/visible', 'channel': 'frontend', 'method': 'agent',
                                  'requirement': 'The visible Wiki branch setting is master after reloading.'}]}
        else:
            point = {'id': key + '/' + cid + '/response', 'channel': 'backend', 'method': 'program',
                     'requirement': c.description + REQUIREMENT}
            companions = bindings.COMPANIONS.get(c.id, ())
            assert all(x in positions for x in companions), 'companion outside the episode: ' + c.id
            required = [positions[x] for x in companions]
            if required:
                point['requires'] = [key + '/' + x + '/response' for x in required]
            cp = {'id': cid, 'case': c.id, 'goal': c.description, 'depends_on': depends, 'assertions': [point]}
        checkpoints.append(cp)
    gui = any(c.channel == 'ui' for c in (cases[i] for i in selection))
    value = {'id': key, 'feature': module.removeprefix('api_') if key != 'protocol-wiki' else 'wiki',
             'execution': 'mixed' if gui else 'program', 'initial_state': INITIAL_STATE, 'setup': setup,
             'inputs': {}, 'checkpoints': checkpoints}
    if key == 'protocol-releases':
        value['feature'] = 'releases'
    if gui:
        value.update(inputs={'account': 'alice', 'credentials': {'alice': CREDS['alice']}},
                     session='Sign in with the supplied account before the goal; this is unscored preparation.',
                     allowed_equivalents=['Equivalent visible settings controls and routes.'],
                     forbidden_bypasses=['Change the setting through visible controls; do not use APIs or create '
                                         'branches instead.'],
                     budget={'calls': 70, 'seconds': 900, 'tokens': 650000}, actor='alice')
    return value


def build():
    episodes = []
    for module in MODULES:
        cases = cases_for(module)
        for key, selection in parts(module, cases):
            episodes.append(episode(module, key, cases, selection))
    return episodes
