"""Declarative episodes authored from the public cmus manual and discriminating media fixtures."""
import fixtures


def q(command,project='text',**kw):return dict(source='query',command=command,project=project,**kw)
def captured(name,project='text',**kw):return dict(source='captured',name=name,project=project,**kw)
def st(file,project,**kw):return dict(source='state',request={'file':file},project=project,**kw)
def fs(path,**kw):return dict(source='workspace',request={'action':'read','path':path},project='file-text',**kw)
def a(suffix,requirement,check):return dict(suffix=suffix,requirement=requirement,check=check)
def cp(id,goal,steps,checks,prepare=(),depends=(),front=None,requires=None):
    return dict(id=id,goal=goal,steps=list(steps),prepare=list(prepare),checks=checks,depends_on=list(depends),front=front,requires=requires)


def episode(id,feature,cps,setup=(),gui=False):
    seen=[]
    for c in cps:
        # Within one independently prepared family, failed prerequisites do not block later cases.
        # Empty negative observations are accompanied by a positive point in that family when available.
        if c.get('requires') is None and c.get('checks') and seen:
            for check in c['checks']:
                if check['check'].get('allow_empty') and not c.get('front'):
                    c['requires']={check['suffix']:[seen[0]]}
        for check in c.get('checks',[]):
            if not check['check'].get('allow_empty'):seen.append(id+'/'+c['id']+'/'+check['suffix'])
        c['depends_on']=['setup:'+x['id'] for x in setup]+c['depends_on']
        assertions=[]
        if c['front']:
            assertions.append(dict(id=id+'/'+c['id']+'/visible',channel='frontend',method='agent',requirement=c['front']))
        for b in c.pop('checks'):
            assertions.append(dict(id=id+'/'+c['id']+'/'+b['suffix'],channel='backend',method='program',requirement=b['requirement'],check=b['check']))
        if c['requires']:
            for suffix,deps in c['requires'].items():
                row=next(x for x in assertions if x['id']==id+'/'+c['id']+'/'+suffix)
                row['requires']=[id+'/'+c['id']+'/'+x if '/' not in x else x for x in deps]
        c['assertions']=assertions;c.pop('front');c.pop('requires')
    w=dict(id=id,feature=feature,execution='gui' if gui else 'program',initial_state='Fresh cmus with the explicitly listed media and preparation.',setup=list(setup),inputs={},checkpoints=cps)
    if gui:w.update(session='Operate cmus through its visible terminal and : command line. Each checkpoint states the desired final result. Any equivalent keyboard or command route is accepted.',allowed_equivalents=['Equivalent visible keys and cmus console commands. Layout and color choices are free.'],forbidden_bypasses=['Do not use an external shell or manipulate files outside the cmus interface.'],budget={'calls':120,'tokens':800000,'seconds':1200})
    if id=='gui-filter-edit':w['budget']={'calls':120,'tokens':1200000,'seconds':1200}
    if id=='gui-marked-edit-1':w['budget']={'calls':200,'tokens':2000000,'seconds':2400}
    return w


def media_setup(load=False):
    s=[{'id':'media','op':'upload','files':fixtures.fixture_files()}]
    if load:s.append({'id':'library','op':'drive','steps':['add -l inbox',{'wait_list':{'count':len(fixtures.TRACKS)}}]})
    return s

def build():
    from programs import build as programs
    from gui import build as gui
    from local_features import build as local_features, gui_episodes
    return programs()+gui()+local_features()+gui_episodes()
