"""Additional offline behavior goals and program scenarios."""
import fixtures


def gui_episodes():
    from specification import episode,step,path,tracks,GUI_FILES
    out=[]
    key='gui-local-cover'
    out.append(episode(key,'cover-art',[GUI_FILES[0],'Blue Cover.png','Gold Cover.png'],[
        step('embed',f'Set Northern Lights album artwork to {path(key,"Blue Cover.png","inputs")} and store it as embedded artwork in its audio file.',
             'Northern Lights displays the blue cover with a pale vertical rectangle and gold circle.',
             [{'op':'cover-embed','file':path(key,'Blue Cover.png','inputs')}],
             [{'kind':'embedded-cover','file':GUI_FILES[0],'image':'Blue Cover.png'}]),
        step('export',f'Save the current Northern Lights cover to {path(key,"blue-export.png","outputs")}.',
             'The cover is saved and Northern Lights still displays the blue artwork.',
             [{'op':'cover-save','file':path(key,'blue-export.png','outputs')}],
             [{'kind':'cover-file','file':'blue-export.png','image':'Blue Cover.png'}],['embed'],requires={'visible':['state-1']}),
        step('replace',f'Replace Northern Lights artwork with {path(key,"Gold Cover.png","inputs")}, retaining embedded storage.',
             'Northern Lights displays the gold cover with a red vertical rectangle and blue circle.',
             [{'op':'cover-load','file':path(key,'Gold Cover.png','inputs')}],
             [{'kind':'embedded-cover','file':GUI_FILES[0],'image':'Gold Cover.png'}],['export']),
        step('persist',f'After restart, open the cover manager and save Northern Lights artwork to {path(key,"gold-export.png","outputs")}.',
             'The gold artwork remains available after restart and is saved successfully.',
             [{'op':'cover-save','file':path(key,'gold-export.png','outputs')}],
             [{'kind':'cover-file','file':'gold-export.png','image':'Gold Cover.png'}],['replace'],lifecycle='restart',requires={'visible':['state-1']}),
        step('remove','Delete the embedded cover from Northern Lights.',
             'Northern Lights no longer displays the gold artwork and shows the no-cover placeholder.',
             [{'op':'cover-delete'}],[{'kind':'embedded-cover','file':GUI_FILES[0],'absent':True}],['persist'],requires={'visible':['state-1'],'state-1':['embed/state-1']})
    ],collection=True))
    out[-1]['budget']={'calls':400,'seconds':6000,'tokens':8000000}
    key='gui-loudness-analysis'
    out.append(episode(key,'audio-analysis',['Quiet Study.flac','Loud Study.flac'],[
        step('quiet','Enable local EBU R 128 collection analysis, rescan the collection, and inspect Quiet Study\'s integrated loudness.',
             'Quiet Study shows a numeric integrated loudness result in LUFS.',
             [{'op':'loudness','file':'Quiet Study.flac'}],[{'kind':'loudness','file':'Quiet Study.flac'}]),
        step('loud','Inspect Loud Study\'s integrated loudness after the same analysis.',
             'Loud Study shows a numeric integrated loudness result that is higher than Quiet Study\'s.',
             [{'op':'press','key':'Escape'},{'op':'loudness','file':'Loud Study.flac'}],[{'kind':'loudness','file':'Loud Study.flac'}],['quiet'])
    ],collection=True))
    key='gui-smart-predicates'
    out.append(episode(key,'smart-playlists',GUI_FILES,[
        step('and-limit','Create and open a smart playlist named "Recent Lina" matching Artist contains "Lina" AND Year greater than 2019. Sort by Title ascending and keep only the first matching song.',
             'Recent Lina exists and its generated playlist contains only Aurora.',
             [{'op':'smart-configure','name':'Recent Lina','terms':[{'field':'Artist','value':'Lina'},{'field':'Year','operator':'greater than','value':2019}],'limit':1},
              {'op':'smart-open','name':'Recent Lina'}],[tracks(['Aurora'],True)]),
        step('or','Create and open a smart playlist named "Jazz or New" matching Artist contains "Orion" OR Year greater than 2023, ordered by Title ascending with all matches. Start from an empty current playlist.',
             'Jazz or New generates Blue Harbor and Dancing Stars, in title order.',
             [{'op':'menu','path':['Playlist','Clear playlist']},{'op':'smart-configure','name':'Jazz or New','mode':'OR','terms':[{'field':'Artist','value':'Orion'},{'field':'Year','operator':'greater than','value':2023}]},
              {'op':'smart-open','name':'Jazz or New'}],[tracks(['Blue Harbor','Dancing Stars'],True)],['and-limit']),
        step('no-match','Create and open "No Match" matching Artist contains "Nobody Here". Start from an empty current playlist.',
             'No Match is saved in the smart playlist list and generates no songs.',
             [{'op':'menu','path':['Playlist','Clear playlist']},{'op':'smart-configure','name':'No Match','terms':[{'field':'Artist','value':'Nobody Here'}]},
              {'op':'smart-open','name':'No Match'}],[tracks([],True)],['or'],requires={'visible':['state-1'],'state-1':['and-limit/state-1']})
    ],collection=True))
    key='gui-dynamic-playlist'
    out.append(episode(key,'smart-playlists',GUI_FILES,[
        step('create','Create a smart playlist named "Growing Mix", including all collection songs, sorted by Title ascending, limited initially to two songs, with dynamic mode enabled. Open it.',
             'Growing Mix is active in dynamic mode and begins with Aurora and Blue Harbor.',
             [{'op':'smart-configure','name':'Growing Mix','mode':'ALL','limit':2,'dynamic':True},{'op':'smart-open','name':'Growing Mix'}],
             [tracks(['Aurora','Blue Harbor'],True)]),
        step('advance','Play Aurora, then advance to Blue Harbor. Leave the dynamic playlist visible.',
             'Blue Harbor is current and dynamic mode has added new collection songs beyond the original two.',
             [{'op':'select','title':'Aurora','double':True},{'op':'menu','path':['Music','Next track']},{'op':'wait','seconds':1}],
             [{'kind':'dynamic-added','initial':['Aurora','Blue Harbor'],'allowed':[m['title'] for m in fixtures.GUI.values()]},{'kind':'player','values':{'title':'Blue Harbor','PlaybackStatus':'Playing'}}],['create'])
    ],collection=True))
    key='gui-organize-copy-overwrite'
    out.append(episode(key,'file-organization',list(fixtures.ORGANIZE_FILES),[
        step('copy','Organize the track Shared by Lina Vale into a copy named "Shared.flac" using "%title.%extension" in the collection folder. Keep the original file.',
             'Shared by Lina Vale remains in the collection after a successful copy.',
             [{'op':'organize-copy','artist':'Lina Vale','title':'Shared','pattern':'%title.%extension'}],
             [{'kind':'organized','file':'Shared.flac','source':'Copy A.flac','keep':True}]),
        step('overwrite','Organize the track Shared by Orion Trio into "Shared.flac" using "%title.%extension" in the collection folder, overwriting the existing file and keeping the Orion Trio original.',
             'Shared by Orion Trio remains available after the overwrite operation completes.',
             [{'op':'organize-copy','artist':'Orion Trio','title':'Shared','pattern':'%title.%extension','overwrite':True}],
             [{'kind':'organized','file':'Shared.flac','source':'Copy B.flac','keep':True}],['copy'])
    ],collection=True))
    key='gui-playlist-path-modes'
    files=[['inputs',n] for n in GUI_FILES[:2]]
    out.append(episode(key,'playlist-formats',GUI_FILES[:2],[
        step('relative',f'Select Relative paths in playlist settings, save the setting, then save the current playlist to {path(key,"relative.m3u","outputs")} as M3U.',
             'The playlist saves successfully and retains Aurora and Blue Harbor.',
             [{'op':'setting','page':'Playlist','radio':'Relative'},{'op':'save-playlist','format':'m3u','file':path(key,'relative.m3u','outputs')}],
             [{'kind':'playlist-path-style','name':'relative.m3u','files':files,'style':'relative'}],requires={'visible':['state-1']}),
        step('absolute',f'Select Absolute paths in playlist settings, save the setting, then save the current playlist to {path(key,"absolute.m3u","outputs")} as M3U.',
             'The playlist saves successfully and retains both tracks.',
             [{'op':'setting','page':'Playlist','radio':'Absolute'},{'op':'save-playlist','format':'m3u','file':path(key,'absolute.m3u','outputs')}],
             [{'kind':'playlist-path-style','name':'absolute.m3u','files':files,'style':'absolute'}],['relative'],requires={'visible':['state-1']})
    ],load=True))
    key='gui-save-all-playlists'
    w=episode(key,'playlist-formats',GUI_FILES[:3],[
        step('save-all',f'Save all open playlists as XSPF files in {path(key,"","outputs")}.',
             'All playlists are saved without an error and remain available.',
             [{'op':'save-all','directory':path(key,'','outputs')}],
             [{'kind':'playlist-file','name':name+'.xspf','files':[['inputs',file]]} for name,file in zip(('Zulu Mix','Alpha Mix','Evening 音楽'),GUI_FILES[:3])],
             requires={'visible':['state-1','state-2','state-3']})
    ])
    w['setup'].append({'id':'named-playlists','op':'playlist-library'})
    for cp in w['checkpoints']:cp['depends_on'].append('setup:named-playlists')
    out.append(w)
    return out


def program_episodes():
    from backend import episode
    out=[]
    fields=['xesam:title','xesam:artist','xesam:album','xesam:trackNumber','xesam:discNumber','mpris:length']
    for fmt in ('flac','mp3','ogg','aac','wav'):
        files=[f'variant--{fmt}--{v}.{fixtures.FORMATS[fmt][0]}' for v in ('no-title','no-artist','minimal','multi','short')]
        cases=[(v,{'kind':'metadata-variant','file':n},fields,f'Read {fmt} metadata profile {v}') for n,v in zip(files,('no-title','no-artist','minimal','multi','short'))]
        out.append(episode('program-metadata-variants-'+fmt,'media-metadata',cases,files))
    files=list(fixtures.SHORT_FILES)
    cases=[]
    for name in ('natural-end','next-track','stop-after-current','repeat-track','repeat-playlist','remove-current','remove-last'):
        cases.append((name,{'kind':'lifecycle','case':name},['state','title','order'],f'Playback lifecycle: {name} with short distinguishable tracks'))
    out.append(episode('program-playback-lifecycle','playback',cases,files))
    for fmt in ('flac','mp3','ogg','wav'):
        file=f'variant--{fmt}--short.{fixtures.FORMATS[fmt][0]}'
        out.append(episode('program-invalid-'+fmt,'malformed-media',[
            ('valid',{'kind':'valid-media','file':file},['title','duration'],'Load a valid short '+fmt+' track'),
            ('damaged',{'kind':'damaged-media','file':file},['remaining','decoder-error'],'Report failed playback of damaged '+fmt+' content while retaining the valid track')],[file]))
        out[-1]['checkpoints'][-1]['assertions'][0]['requires']=[out[-1]['id']+'/valid/title']
    return out


def run_program(c,a):
    from harness import value,projection
    import time
    kind=a['kind']
    if kind=='metadata-variant':
        return c.load([c.document(a['file'])],1,verify_identity=False)[0]
    if kind in ('valid-media','damaged-media'):
        file=c.document(a['file']);md=c.load([file],1)[0]
        if kind=='valid-media':return {'title':value(md,'xesam:title'),'duration':value(md,'mpris:length')}
        bad='damaged.'+a['file'].rsplit('.',1)[-1]
        p=c.upload(bad,b'This document is not audio.\n')
        c.cli('--append',p);c.call(op='wait',seconds=1)
        # Any visible import-error notice is dismissed through the same UI channel.
        for _ in range(2):
            if any(n['role'] in ('dialog','alert') for n in c.call(op='observe')['nodes']):c.call(op='press',key='Escape')
        tracks=c.tracks();assert value(tracks[0],'xesam:title')==value(md,'xesam:title'),'valid track was displaced'
        invalid=next((t for t in tracks if value(t,'xesam:url')==bad),None)
        assert invalid is not None,'damaged playlist entry was not created'
        c.method('GoTo',invalid['mpris:trackid'],interface='TrackList')
        def reported():
            view=c.call(op='observe')
            return any(n['role'] in ('dialog','alert') and 'error' in n.get('name','').casefold() for n in view['nodes'])
        c.wait(reported,seconds=15,message='decoder failure not reported in the public interface')
        assert c.get('PlaybackStatus')=='Stopped','damaged input falsely reported playing'
        c.call(op='press',key='Escape')
        return {'remaining':value(tracks[0],'xesam:title'),'decoder-error':True}
    if kind=='lifecycle':
        names=list(fixtures.SHORT_FILES);case=a['case']
        chosen=names[:1] if case=='natural-end' else names[:2]
        c.load([c.document(n) for n in chosen],len(chosen));c.set('Shuffle',False);c.set('LoopStatus','None')
        idx=1 if case in ('repeat-playlist','remove-last') else 0
        ids=c.get('Tracks','TrackList');c.method('GoTo',ids[idx],interface='TrackList')
        c.wait(lambda:c.get('PlaybackStatus')=='Playing' and c.get('Position')>200000)
        if case=='stop-after-current':c.cli('--stop-after-current')
        if case=='repeat-track':c.set('LoopStatus','Track')
        if case=='repeat-playlist':c.set('LoopStatus','Playlist')
        if case.startswith('remove-'):
            c.method('RemoveTrack',ids[idx],interface='TrackList');time.sleep(.3)
        else:
            near_end=int((fixtures.SHORT_FILES[chosen[idx]][0]-1)*1e6)
            c.method('SetPosition',c.get('Metadata')['mpris:trackid'],near_end)
            if case=='repeat-track':c.wait(lambda:c.get('Position')>=near_end-.2e6,seconds=3)
            if case in ('natural-end','stop-after-current'):c.wait(lambda:c.get('PlaybackStatus')=='Stopped',seconds=10)
            elif case=='next-track':c.wait(lambda:c.get('Metadata').get('xesam:title')=='Short Blue',seconds=10)
            elif case=='repeat-playlist':c.wait(lambda:c.get('Metadata').get('xesam:title')=='Short Amber',seconds=10)
            else:
                c.wait(lambda:c.get('Position')<1000000,seconds=10)
        state=c.get('PlaybackStatus');title=c.get('Metadata').get('xesam:title')
        if state=='Playing':c.method('Pause')
        return {'state':state,'title':title,'order':[value(m,'xesam:url') for m in c.tracks()]}
    raise ValueError(kind)

def smart_edit_episode():
    from specification import episode,step,path,tracks,GUI_FILES
    key='gui-smart-playlist-edit-delete'
    return episode(key,'smart-playlists',GUI_FILES,[
        step('create','Create the Lina Selection smart playlist matching Artist contains Lina.', 'Lina Selection is in the smart playlist list.',[{'op':'smart-create','name':'Lina Selection','field':'Artist','value':'Lina'}]),
        step('edit','Edit Lina Selection to match Artist contains Orion instead.', 'The edited smart playlist produces Blue Harbor.',[{'op':'smart-edit','field':'Artist','value':'Orion'},{'op':'smart-open','name':'Lina Selection'}],[tracks(['Blue Harbor'],True)],['create']),
        step('delete','Delete Lina Selection.', 'Lina Selection is no longer in the smart playlist list.',[{'op':'smart-delete'}],[{'kind':'smart-names','absent':'Lina Selection'}],['edit'])
    ],collection=True)
