'''Program episodes: one isolated episode per API module.

Each episode runs its module's cases in their declared order against one fresh application instance. A module's
unscored fixture cases become setup items with ids that accept any success status; checkpoints that need a fixture
declare it (setup:<id>), so a failed fixture blocks only its dependents. A scored case is never replayed as setup.
Protocol assertions compare normalized public responses. Optional companion bindings are declared in bindings.py.
No browser operation runs in a program episode.
'''
import importlib
import re

from harness import Suite
import bindings
from dependencies import DEPENDENCIES

# Modules in execution order; each one builds the cases of one episode.
MODULES = ['api_organizers', 'api_ingredients', 'api_recipes', 'api_mealplans', 'api_shopping', 'api_cookbooks', 'api_accounts', 'api_social', 'api_files', 'api_extras', 'api_access', 'api_persistence', 'api_configuration', 'api_interchange', 'api_scope', 'api_roundtrip', 'api_discovery', 'api_identity']
REQUIREMENT = '; preserve resource relationships, permissions and numeric error codes.'
INITIAL_STATE = ('A fresh application with only the initial administrator account (admin) in the default group Home '
                 'and household Family. The listed setup items prepare this episode fixtures through the public '
                 'interfaces; scored cases are never replayed.')


def cases_for(module):
    '''The executable cases of a module in order: fixtures (setup items) and scored protocol cases.'''
    suite = Suite()
    importlib.import_module(module).build(suite)
    return suite.cases


CASES = {}


def case(case_id):
    '''Executable case by id (built on first use, for every module).'''
    if not CASES:
        for module in MODULES:
            for c in cases_for(module):
                assert c.id not in CASES, 'case id used by two modules: ' + c.id
                CASES[c.id] = c
    return CASES[case_id]


def episode(module, key, cases):
    positions={c.id:'p%04d'%i for i,c in enumerate(cases)}
    setup_ids={c.id:'fx-%04d'%i for i,c in enumerate(cases) if c.channel=='setup'}
    index={c.id:i for i,c in enumerate(cases)}
    for c in cases:
        assert c.id in DEPENDENCIES, 'undeclared dependencies: '+c.id
        assert all(d in index and index[d]<index[c.id] for d in DEPENDENCIES[c.id]), 'invalid prerequisite: '+c.id
    def expanded(cid):
        result=set()
        for dep in DEPENDENCIES[cid]:
            if dep in setup_ids:
                result.add('setup:'+setup_ids[dep])
                result.update(expanded(dep))
            else:
                result.add(key+'/'+positions[dep]+'/response')
        return sorted(result)
    setup=[];checkpoints=[];pending=[]
    for c in cases:
        if c.channel=='setup':
            pending.append(c)
            continue
        cid=positions[c.id]
        for fixture in pending:
            item={'id':setup_ids[fixture.id],'cases':[fixture.id]}
            if checkpoints:item['before']=cid
            setup.append(item)
        pending=[]
        point={'id':key+'/'+cid+'/response','channel':'backend','method':'program',
               'requirement':c.description+REQUIREMENT}
        companions=bindings.COMPANIONS.get(c.id,())
        if companions:point['requires']=[key+'/'+positions[x]+'/response' for x in companions]
        checkpoints.append({'id':cid,'case':c.id,'goal':c.description,'depends_on':expanded(c.id),
                            'assertions':[point]})
    assert not pending,'unused fixture tail in '+module
    return {'id':key,'feature':module.removeprefix('api_'),'execution':'program',
            'initial_state':INITIAL_STATE,'setup':setup,'inputs':{},'checkpoints':checkpoints}


def build():
    return [episode(module, 'protocol-' + module.removeprefix('api_'), cases_for(module)) for module in MODULES]
