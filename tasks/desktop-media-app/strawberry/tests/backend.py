"""Program episodes over real product MPRIS, CLI and playlist interfaces."""
import time
import fixtures
from harness import value,projection

# Fields have different container representations; each is checked separately.
FORMAT_FIELDS={fmt:list(fixtures.META_FIELDS) for fmt in fixtures.FORMATS}
FORMAT_FIELDS['ogg-flac'].remove('mpris:length')
for field in ('xesam:albumArtist','xesam:discNumber','xesam:composer'):
    FORMAT_FIELDS['tta'].remove(field)


def point(episode,cid,key,description=None,requires=()):
    d={'id':f'{episode}/{cid}/{key.replace(":","-")}','channel':'backend','method':'program',
       'requirement':description or f'The public {key} result matches the recorded product behavior.', 'field':key}
    if requires:d['requires']=list(requires)
    return d


def episode(key,feature,cases,files=()):
    setup=[{'id':'documents','op':'documents','files':list(files)}] if files else []
    checkpoints=[]
    for cid,action,keys,description in cases:
        checkpoints.append({'id':cid,'goal':description,'action':action,'depends_on':['setup:documents'] if files else [],
                            'assertions':[point(key,cid,k,description+' — '+k) for k in keys]})
    if key=='program-player-properties':
        setup.append({'id':'rating-collection','op':'rating-collection','before':'rating-1'})
        for cp in checkpoints:
            if cp['action']['kind']=='rating':
                cp['depends_on'].append('setup:rating-collection')
                if cp['action']['value']<=0 or cp['action']['value']>1:
                    cp['assertions'][0]['requires']=[key+'/rating-1/Rating']
    if key=='program-playlists-interface':
        setup.append({'id':'library','op':'playlist-library'})
        for cp in checkpoints:cp['depends_on'].append('setup:library')
    return {'id':key,'feature':feature,'execution':'program',
            'initial_state':'Fresh profile and private desktop; each case loads its own media through public interfaces.',
            'setup':setup,'inputs':{},'checkpoints':checkpoints}


def build():
    out=[]
    for fmt in fixtures.FORMATS:
        key='program-metadata-'+fmt;files=[fixtures.name(fmt,i) for i in range(len(fixtures.PROFILES))]
        cases=[(f'profile-{i+1}',{'kind':'metadata','file':file},FORMAT_FIELDS[fmt],
                f'Load {fmt} profile {i+1} and read its independently encoded metadata and duration') for i,file in enumerate(files)]
        out.append(episode(key,'media-metadata',cases,files))
    gui=list(fixtures.GUI)
    for kind in ('m3u','m3u8','pls','xspf','asxini','cue','asx','wpl'):
        cases=[]
        for variant in range(3 if kind=='cue' else 4):
            cases.append((f'variant-{variant+1}',{'kind':'playlist','format':kind,'variant':variant,'files':fixtures.PLAYLIST_FILES if kind in ('asx','wpl') else gui[:3]},
                          ['count','order','title','artist','album','duration','track','disc'],
                          f'Load {kind} playlist variant {variant+1}; observe order, duplicates and decoded metadata'))
        out.append(episode('program-playlist-'+kind,'playlist-formats',cases,fixtures.PLAYLIST_FILES if kind in ('asx','wpl') else gui[:3]))
    cases=[]
    for i,v in enumerate((0,.01,.33,.5,.99,1,-.2,1.2,.345)):
        cases.append((f'volume-{i+1}',{'kind':'set-property','name':'Volume','value':v},['Volume'],f'Set MPRIS Volume to {v} and read its bounded value'))
    for i,v in enumerate(('Track','Playlist','None','invalid','track','')):
        cases.append((f'loop-{i+1}',{'kind':'set-property','name':'LoopStatus','value':v},['LoopStatus'],f'Set loop mode to {v!r} from a known previous mode'))
    for i,v in enumerate((True,False)):
        cases.append((f'shuffle-{i+1}',{'kind':'set-property','name':'Shuffle','value':v},['Shuffle'],f'Set shuffle to {v}'))
    for i,v in enumerate((.25,.6,1,0,2,-1)):
        cases.append((f'rating-{i+1}',{'kind':'rating','value':v},['Rating'],f'Rate the current track {v} through MPRIS'))
    out.append(episode('program-player-properties','playback',cases,gui[:3]))
    cases=[]
    for method,chain in [('Play',['Play']),('Pause',['Play','Pause']),('PlayPause-playing',['Play','PlayPause']),
                         ('PlayPause-paused',['Play','Pause','PlayPause']),('Stop',['Play','Stop']),
                         ('Next',['Play','Next']),('Previous',['Play','Next','Previous'])]:
        cases.append((method.lower(),{'kind':'transport','chain':chain},['PlaybackStatus','title','CanPlay','CanPause','CanSeek','CanGoNext','CanGoPrevious'],f'Execute {chain} on three tracks'))
    for pos in (0,1,7,37,179,-1,181):
        cases.append((f'position-{str(pos).replace("-","minus")}',{'kind':'position','position':pos},['position','title','PlaybackStatus'],f'Set current position to {pos} seconds while paused'))
    for pos in (-50,-3,0,4,25):
        cases.append((f'seek-{str(pos).replace("-","minus")}',{'kind':'seek','offset':pos},['position','title','PlaybackStatus'],f'Seek by {pos} seconds from a fixed paused position'))
    cases += [('wrong-track-position',{'kind':'position','position':15,'wrong':True},['position'], 'A stale track ID cannot seek the current track'),
              ('rate-zero',{'kind':'rate','value':0},['Rate','PlaybackStatus'],'Rate zero pauses playback'),
              ('rate-other',{'kind':'rate','value':2},['Rate','PlaybackStatus'],'Unsupported rate preserves the fixed playback speed')]
    out.append(episode('program-transport','playback',cases,gui[:3]))
    cases=[]
    for option in ('--play','--pause','--play-pause','--stop','--next','--previous','--restart-or-previous'):
        cases.append((option[2:],{'kind':'cli-transport','option':option},['PlaybackStatus','title'],f'Forward {option} to the running application'))
    for i,v in enumerate((-1,0,1,33,75,100,101)):
        cases.append((f'volume-{i}',{'kind':'cli-volume','value':v},['Volume'],f'Command line --volume {v}'))
    for option in ('--volume-up','--volume-down'):
        cases.append((option[2:],{'kind':'cli-volume-step','option':option},['Volume'],f'Command line {option} changes volume'))
    for option in ('--volume-increase-by','--volume-decrease-by'):
        for v in (0,7,37,100,-9):
            cases.append((option[2:]+'-'+str(v).replace('-','minus'),{'kind':'cli-volume-by','option':option,'value':v},['Volume'],f'Command line {option} {v} from 43 percent'))
    for i in (1,2,3,0,9):
        cases.append((f'play-track-{i}',{'kind':'cli-track','index':i},['title','PlaybackStatus'],f'Command line --play-track {i}'))
    for option in ('--seek-to','--seek-by'):
        for v in (-2,0,5,50):
            cases.append((option[2:]+'-'+str(v).replace('-','minus'),{'kind':'cli-seek','option':option,'value':v},['position'],f'Command line {option} {v}'))
    out.append(episode('program-command-line','command-line',cases,gui[:3]))
    cases=[]
    for place in ('begin','middle','end','unknown'):
        for current in (False,True):
            cases.append((f'add-{place}-{current}',{'kind':'track-add','place':place,'current':current},['order','current','status'],f'Insert a track {place}, SetAsCurrent={current}'))
    for i in (0,1,2,9):
        cases.append((f'remove-{i}',{'kind':'track-remove','index':i},['order'],f'Remove track index {i}, with an absent-ID case'))
    for i in (0,1,2,9):
        cases.append((f'goto-{i}',{'kind':'track-goto','index':i},['order','current'],f'Go to track {i} without replacing the list'))
    cases.append(('metadata-request-order',{'kind':'metadata-order'},['title','invalid'],'Request metadata in a different order, with duplicates and an invalid ID'))
    cases.append(('append',{'kind':'append'},['order'],'Append two tracks without replacing the existing playlist'))
    cases.append(('open-uri',{'kind':'open-uri'},['order','current'],'OpenUri adds and starts a local track'))
    out.append(episode('program-track-list','playlist-management',cases,gui[:4]))
    cases=[]
    for name,v in [('Volume',.37),('LoopStatus','Track'),('Shuffle',True)]:
        cases.append(('persist-'+name.lower(),{'kind':'persist-property','name':name,'value':v},[name],f'{name} survives a restart with the same data directory'))
    cases.append(('playlist-restart',{'kind':'persist-list'},['order','title'],'Playlist tracks and metadata survive a restart'))
    cases.append(('reset-profile',{'kind':'reset'},['tracks','Volume','Shuffle','LoopStatus'],'Reset restores a fresh profile and empty playlist'))
    out.append(episode('program-persistence','persistence',cases,gui[:3]))
    cases=[]
    for order in ('UserDefined','Alphabetical'):
        for reverse in (False,True):
            for index,limit in ((0,10),(1,2),(2,1),(3,10),(4,2)):
                cases.append((f'{order}-{reverse}-{index}-{limit}',{'kind':'playlist-query','order':order,'reverse':reverse,'index':index,'limit':limit},
                              ['names'],f'Enumerate named playlists ordered {order}, reverse={reverse}, offset {index}, limit {limit}'))
    cases.append(('play-named',{'kind':'playlist-named'},['title','status'],'Play Alpha Mix by its name through the command line'))
    cases.append(('activate',{'kind':'playlist-activate'},['title','status'],'Activate a named playlist through MPRIS'))
    out.append(episode('program-playlists-interface','playlist-management',cases,gui[:3]))
    from additions import program_episodes
    out.extend(program_episodes())
    return out


def ready_player(c,playing=False,index=0,area='inputs'):
    files=list(fixtures.GUI)[:3]
    c.load([c.document(n,area) for n in files],3)
    c.set('Shuffle',False);c.set('LoopStatus','None')
    c.method('GoTo',c.get('Tracks','TrackList')[index],interface='TrackList')
    c.wait(lambda:c.get('PlaybackStatus')=='Playing' and c.get('Position')>200000)
    if not playing:
        c.method('Pause');c.wait(lambda:c.get('PlaybackStatus')=='Paused')
    return c.tracks()


def state(c):
    p=c.mpris('Player','get_all')
    assert isinstance(p,dict) and 'PlaybackStatus' in p,'missing Player state'
    p['title']=p.get('Metadata',{}).get('xesam:title')
    p['position']={'position_seconds':p.get('Position',-10000000)/1e6}
    return p


def run(c,a):
    kind=a['kind']
    if kind in ('playlist-query','playlist-activate','playlist-named'):
        rows=c.method('GetPlaylists',0,100,'UserDefined',False,interface='Playlists')
        if kind=='playlist-query':
            result=c.method('GetPlaylists',a['index'],a['limit'],a['order'],a['reverse'],interface='Playlists')
            return {'names':[r[1] for r in result]}
        if kind=='playlist-named':
            c.cli('--play-playlist','Alpha Mix');c.wait(lambda:c.get('Metadata').get('xesam:title')=='Blue Harbor')
            return {'title':c.get('Metadata').get('xesam:title'),'status':c.get('PlaybackStatus')}
        chosen=next(r for r in rows if r[1]=='Alpha Mix')
        c.method('ActivatePlaylist',chosen[0],interface='Playlists');time.sleep(1)
        return {'title':c.get('Metadata').get('xesam:title'),'status':c.get('PlaybackStatus')}
    if kind=='metadata':
        return c.load([c.document(a['file'])],1,verify_identity=False)[0]
    if kind=='playlist':
        paths=[c.document(n) for n in a.get('files',list(fixtures.GUI)[:3])]
        payload=fixtures.playlist(a['format'],paths,a['variant'])
        p=c.upload(f"sample-{a['variant']}.{a['format']}",payload)
        expected=[paths[0]]*3 if a['format']=='cue' else [paths[i] for i in ([0,1,2] if a['variant']==0 else [2,0,1] if a['variant']==1 else [1,1,0] if a['variant']==2 else [0,2])]
        expected=[__import__('pathlib').Path(n).name for n in expected]
        c.load([p],len(expected))
        def imported():
            result=c.tracks()
            return result if [value(m,'xesam:url') for m in result]==expected else None
        md=c.wait(imported)
        return {'count':len(md),'order':[value(m,'xesam:url') for m in md],
                **{short:[value(m,key) if key in m else {'absent':True} for m in md] for short,key in
                   [('title','xesam:title'),('artist','xesam:artist'),('album','xesam:album'),
                    ('duration','mpris:length'),('track','xesam:trackNumber'),('disc','xesam:discNumber')]}}
    if kind=='set-property':
        if a['name']=='LoopStatus':c.set('LoopStatus','Playlist')
        elif a['name']=='Shuffle':c.set('Shuffle',not a['value'])
        c.set(a['name'],a['value']);return {a['name']:c.get(a['name'])}
    if kind=='rating':
        ready_player(c,area='music')
        expected=max(0,min(1,a['value']))
        prior=.8 if expected!=.8 else .2
        c.set('Rating',prior);c.wait(lambda:abs(c.get('Rating')-prior)<.001)
        c.set('Rating',a['value']);c.wait(lambda:abs(c.get('Rating')-expected)<.001)
        return {'Rating':c.get('Rating')}
    if kind=='transport':
        ready_player(c)
        for m in a['chain']:c.method(m);time.sleep(.15)
        time.sleep(.25);return state(c)
    if kind in ('position','seek','rate','cli-seek'):
        ready_player(c,playing=kind=='rate')
        track=c.get('Metadata')['mpris:trackid']
        c.method('SetPosition',track,10_000_000)
        if kind=='position':c.method('SetPosition','/invalid' if a.get('wrong') else track,a['position']*1000000)
        elif kind=='seek':c.method('Seek',a['offset']*1000000)
        elif kind=='rate':c.set('Rate',a['value'])
        else:c.cli(a['option'],str(a['value']))
        time.sleep(.3);return state(c)
    if kind=='cli-transport':
        ready_player(c,playing=a['option']!='--play',index=1)
        c.cli(a['option']);time.sleep(.3);return state(c)
    if kind=='cli-volume':c.cli('--volume',str(a['value']));return {'Volume':c.get('Volume')}
    if kind=='cli-volume-step':c.set('Volume',.5);c.cli(a['option']);return {'Volume':c.get('Volume')}
    if kind=='cli-volume-by':
        c.set('Volume',.43);c.cli(a['option'],str(a['value']));return {'Volume':c.get('Volume')}
    if kind=='cli-track':
        ready_player(c);c.cli('--play-track',str(a['index']));time.sleep(.3);return state(c)
    if kind.startswith('track-') or kind in ('metadata-order','append','open-uri'):
        md=ready_player(c);ids=[m['mpris:trackid'] for m in md]
        if kind=='track-add':
            after={'begin':'/','middle':ids[0],'end':ids[-1],'unknown':'/invalid'}[a['place']]
            c.method('AddTrack',c.document(list(fixtures.GUI)[3]),after,a['current'],interface='TrackList')
            c.wait(lambda:len(c.tracks())==4)
        elif kind=='track-remove':
            c.method('RemoveTrack',ids[a['index']] if a['index']<len(ids) else '/invalid',interface='TrackList')
        elif kind=='track-goto':c.method('GoTo',ids[a['index']] if a['index']<len(ids) else '/invalid',interface='TrackList')
        elif kind=='metadata-order':
            result=c.method('GetTracksMetadata',[ids[2],ids[0],ids[2],'/invalid'],interface='TrackList')
            return {'title':[r.get('xesam:title') for r in result[:3]],'invalid':result[3]=={}}
        elif kind=='append':c.cli('--append',c.document(list(fixtures.GUI)[1]),c.document(list(fixtures.GUI)[0]));c.wait(lambda:len(c.tracks())==5)
        elif kind=='open-uri':c.method('OpenUri',c.document(list(fixtures.GUI)[3]));c.wait(lambda:len(c.tracks())==4)
        time.sleep(.3)
        return {'order':[value(m,'xesam:url') for m in c.tracks()],
                'current':c.get('Metadata').get('xesam:title'),'status':c.get('PlaybackStatus')}
    if kind.startswith('persist-'):
        ready_player(c)
        if kind=='persist-property':c.set(a['name'],a['value'])
        c.call(op='restart');time.sleep(.3)
        if kind=='persist-property':return {a['name']:c.get(a['name'])}
        md=c.wait(c.tracks);return {'order':[value(m,'xesam:url') for m in md],'title':[value(m,'xesam:title') for m in md]}
    if kind=='reset':
        ready_player(c);c.set('Volume',.23);c.set('Shuffle',True);c.set('LoopStatus','Track')
        c.call(op='reset');c.uploaded.clear()
        return {'tracks':c.tracks(),**{k:c.get(k) for k in ('Volume','Shuffle','LoopStatus')}}
    from additions import run_program
    return run_program(c,a)
