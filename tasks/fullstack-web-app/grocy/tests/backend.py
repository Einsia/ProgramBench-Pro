"""Independent program episodes; setup dependencies and state dependencies are explicit."""
import importlib
import hashlib
from harness import Suite
MODULES = ['api_entities','api_stock','api_recipes','api_household','api_users','api_extensions','api_persistence','api_advanced','api_coverage','api_credentials']
CASES={}
def cases_for(module):
    s=Suite();importlib.import_module(module).build(s)
    # Foundation records are shared conveniences, not universal prerequisites.
    # Retain only foundation objects referenced by this case or its actual dependencies.
    byid={c.id:c for c in s.cases};producers={c.save:c.id for c in s.cases if c.save}
    foundation=getattr(s,'foundation_ids',set())
    memo={}
    def narrowed(cid,visiting=()):
        if cid in memo:return memo[cid]
        if cid in visiting:raise AssertionError('dependency cycle '+cid)
        case=byid[cid]
        needs=[d for d in case.needs if d not in foundation]
        for key in case.references:
            producer=producers.get(key)
            if producer and producer!=cid and producer not in needs:needs.append(producer)
        expanded=list(needs)
        for dep in needs:
            for parent in narrowed(dep,(*visiting,cid)):
                if parent in foundation and parent not in expanded:expanded.append(parent)
        memo[cid]=tuple(expanded);return memo[cid]
    for c in s.cases:c.needs=narrowed(c.id)
    return s.cases
def case(cid):
    if not CASES:
        for module in MODULES:
            for c in cases_for(module):
                key=module+'/'+c.id
                assert key not in CASES;CASES[key]=c
    return CASES[cid]
def episode(module,cases):
    key='protocol-'+module.removeprefix('api_')
    positions={c.id:'p%04d'%i for i,c in enumerate(cases) if c.channel!='setup'}
    setupids={c.id:'fx-'+hashlib.sha256(c.id.encode()).hexdigest()[:16] for c in cases if c.channel=='setup'}
    def dependency(cid):return 'setup:'+setupids[cid] if cid in setupids else positions[cid]
    setup=[];checkpoints=[];pending=[]
    for c in cases:
        if c.channel=='setup':pending.append(c);continue
        cid=positions[c.id]
        for fx in pending:
            item={'id':setupids[fx.id],'cases':[module+'/'+fx.id]}
            if checkpoints:item['before']=cid
            setup.append(item)
        pending=[]
        point={'id':key+'/'+cid+'/response','channel':'backend','method':'program','requirement':c.description}
        if c.requires:point['requires']=[key+'/'+positions[x]+'/response' for x in c.requires]
        checkpoints.append({'id':cid,'case':module+'/'+c.id,'goal':c.description,'depends_on':[dependency(x) for x in c.needs],
                            'assertions':[point]})
    assert not pending,'unused fixture'
    return {'id':key,'feature':module.removeprefix('api_'),'execution':'program',
            'initial_state':'Fresh Grocy data directory with default admin/admin. Public API fixtures are applied.',
            'setup':setup,'inputs':{},'checkpoints':checkpoints}
def build():return [episode(m,cases_for(m)) for m in MODULES]
