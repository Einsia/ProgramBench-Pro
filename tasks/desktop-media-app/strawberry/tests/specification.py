"""User-facing goals, functional acceptance and independent state checks."""
import fixtures
from evaluation.contract import files_path

GUI_FILES=list(fixtures.GUI)
TITLES=[v['title'] for v in fixtures.GUI.values()]


def path(wf,name,area='inputs'):
    return files_path(area, name)


def step(cid,goal,acceptance,recipe,checks=(),depends=(),lifecycle=None,requires=None):
    cp={'id':cid,'goal':goal,'acceptance':acceptance,'recipe':recipe,'checks':list(checks),'depends_on':list(depends)}
    if lifecycle:cp['lifecycle']=lifecycle
    if requires:cp['requires']=requires
    return cp


def tracks(names,current=False):return {'kind':'tracks','titles':list(names),'current':current}
def player(**values):return {'kind':'player','values':values}

def episode(key,feature,files,steps,load=False,collection=False):
    setup=[]
    if files:
        audio_files=[n for n in files if not n.endswith('.png')]
        pictures=[n for n in files if n.endswith('.png')]
        if audio_files:setup.append({'id':'documents','op':'documents','files':audio_files,'area':'music' if collection else 'inputs'})
        if pictures:setup.append({'id':'artwork','op':'documents','files':pictures,'area':'inputs'})
    if load:setup.append({'id':'loaded','op':'load','files':files,'area':'music' if collection else 'inputs'})
    if collection:setup.append({'id':'indexed','op':'restart'})
    for cp in steps:
        cp['depends_on']=['setup:'+s['id'] for s in setup]+cp['depends_on']
        cp['assertions']=[{'id':key+'/'+cp['id']+'/visible','channel':'frontend','method':'agent','requirement':cp['acceptance']}]
        for i,check in enumerate(cp['checks']):
            cp['assertions'].append({'id':key+'/'+cp['id']+f'/state-{i+1}','channel':'backend','method':'program',
                                     'requirement':'The independently observed product state or written document satisfies the goal.', 'check':check})
        for suffix,requires in cp.pop('requires',{}).items():
            next(a for a in cp['assertions'] if a['id'].endswith('/'+suffix))['requires']=[key+'/'+(r if '/' in r else cp['id']+'/'+r) for r in requires]
    initial='The named documents have been uploaded'+(' and loaded into the current playlist' if load else '')+('. They are in the configured collection folder; the application has been restarted to index them' if collection else '')+'.'
    return {'id':key,'feature':feature,'execution':'gui','initial_state':'Fresh profile and desktop. '+initial,
            'setup':setup,'inputs':{'documents':{path(key,n,'music' if collection and not n.endswith('.png') else 'inputs'):fixtures.GUI.get(n,fixtures.SORT_FILES.get(n,fixtures.ORGANIZE_FILES.get(n,{'title':n}))) for n in files},
                                  'outputs':'Save requested documents at the absolute paths stated in the goals.'},
            'session':'Operate the visible music application. '+initial,
            'allowed_equivalents':['Menus, keyboard shortcuts, toolbar buttons and context menus are equivalent routes. Layout, wording and widget types may differ.',
                                   'Maximize or resize a dialog, or scroll it, to reach its controls. Enter absolute document paths in file dialogs.'],
            'forbidden_bypasses':['Do not use MPRIS, command-line tools, a terminal, other applications or private files to perform GUI goals.'],
            'budget':{'calls':max(150,70+35*len(steps)),'seconds':max(1500,600+300*len(steps)),
                      'tokens':max(3000000,(70+35*len(steps))*18000)},'checkpoints':steps}


def build():
    out=[]
    key='gui-open-playback'
    out.append(episode(key,'playback',GUI_FILES[:2],[
        step('open',f'Open {path(key,GUI_FILES[0])} and start playing it.',
             'Aurora is present and is the current playing track.',[{'op':'open','file':path(key,GUI_FILES[0])}],
             [tracks(['Aurora']),player(PlaybackStatus='Playing',title='Aurora')]),
        step('pause','Pause playback.','Aurora remains current and playback is paused.',[{'op':'menu','path':['Music','Pause']}],
             [player(PlaybackStatus='Paused',title='Aurora')],['open']),
        step('append',f'Add {path(key,GUI_FILES[1])} to the existing playlist.',
             'The playlist contains Aurora and Blue Harbor.',[{'op':'add-file','file':path(key,GUI_FILES[1])}],
             [tracks(['Aurora','Blue Harbor'])],['pause']),
        step('play-second','Play Blue Harbor from this playlist.','Blue Harbor is the current playing track.',
             [{'op':'select','title':'Blue Harbor','double':True}], [player(PlaybackStatus='Playing',title='Blue Harbor')],['append']),
        step('stop','Stop playback.','Playback is stopped; both tracks remain available in the playlist.',
             [{'op':'menu','path':['Music','Stop']}],[player(PlaybackStatus='Stopped'),tracks(['Aurora','Blue Harbor'])],['play-second']),
    ]))
    key='gui-playlist-history'
    out.append(episode(key,'editing',GUI_FILES[:3],[
        step('remove','Remove Blue Harbor from the playlist.','Aurora and Cedar Road remain; Blue Harbor has been removed.',
             [{'op':'select','title':'Blue Harbor'},{'op':'press','key':'Delete'}],[tracks(['Aurora','Cedar Road'])]),
        step('undo','Undo the removal.','The three original tracks are present again.',[{'op':'undo'}],
             [tracks(TITLES[:3])],['remove']),
        step('redo','Redo the removal.','Blue Harbor is removed again while the other two tracks remain.',[{'op':'redo'}],
             [tracks(['Aurora','Cedar Road'])],['undo']),
        step('clear','Clear this playlist.','The playlist is empty and shows zero tracks.',[{'op':'menu','path':['Playlist','Clear playlist']}],
             [tracks([])],['redo']),
        step('undo-clear','Use undo to restore the original three-track playlist.','Aurora, Blue Harbor and Cedar Road are restored.',[{'op':'undo'}],
             [tracks(TITLES[:3])],['clear'])
    ],load=True))
    key='gui-remove-duplicates'
    out.append(episode(key,'playlist-management',[GUI_FILES[0],GUI_FILES[1],GUI_FILES[0],GUI_FILES[2]],[
        step('deduplicate','Remove duplicate tracks from the playlist.','Aurora, Blue Harbor and Cedar Road each appear once.',
             [{'op':'menu','path':['Playlist','Remove duplicates from playlist']}],[tracks(TITLES[:3])])
    ],load=True))
    key='gui-playlist-search'
    out.append(episode(key,'search',GUI_FILES[:4],[
        step('title','Filter the playlist for "Blue".','Blue Harbor is the matching visible track.',[{'op':'playlist-filter','value':'Blue'}]),
        step('artist','Replace the playlist filter with "Lina".','Aurora and Cedar Road are the matching visible tracks.',[{'op':'playlist-filter','value':'Lina'}],depends=['title']),
        step('restore','Clear the playlist filter.','All four original tracks are visible again.',[{'op':'playlist-filter','value':''}],
             [tracks(TITLES[:4])],['artist'])
    ],load=True))
    key='gui-playlist-sort'
    out.append(episode(key,'sorting',[list(fixtures.SORT_FILES)[i] for i in (2,0,3,1)],[
        step('title-up','Sort the playlist by title in ascending order.','The tracks appear as Aurora, Blue Harbor, Cedar Road, Dancing Stars.',
             [{'op':'sort','column':'Title','descending':False}],[tracks(TITLES[:4])]),
        step('title-down','Sort the playlist by title in descending order.','The tracks appear as Dancing Stars, Cedar Road, Blue Harbor, Aurora.',
             [{'op':'sort','column':'Title','descending':True}],[tracks(list(reversed(TITLES[:4])))],['title-up']),
        step('track','Sort the playlist by track number in ascending order.','Blue Harbor, Dancing Stars, Aurora and Cedar Road appear in that order, with track numbers 1, 2, 3, 4.',
             [{'op':'sort','column':'Track','descending':False}],[tracks(['Blue Harbor','Dancing Stars','Aurora','Cedar Road'])],['title-down'])
    ],load=True))
    key='gui-playlist-tabs'
    out.append(episode(key,'playlist-management',GUI_FILES[:2],[
        step('new','Create a new, empty playlist.','A second, empty playlist is current; the original playlist is still available.',
             [{'op':'press','key':'Control+n'}],[{'kind':'playlists','count':2}]),
        step('rename','Rename the new playlist to "Evening Mix".','The current playlist is named Evening Mix.',
             [{'op':'rename-playlist','name':'Evening Mix'}],[{'kind':'playlists','names':['Playlist 1','Evening Mix']}],['new']),
        step('add',f'Add {path(key,GUI_FILES[1])} to Evening Mix.', 'Evening Mix contains Blue Harbor.',
             [{'op':'add-file','file':path(key,GUI_FILES[1])}],[tracks(['Blue Harbor'],True)],['rename']),
        step('return','Switch to the original Playlist 1.','Playlist 1 is current and still contains Aurora and Blue Harbor.',
             [{'op':'tab','name':'Playlist 1'}],[tracks(TITLES[:2],True)],['add']),
        step('persist','After the application restart, switch to Evening Mix.','Evening Mix is still named correctly and contains Blue Harbor.',
             [{'op':'tab','name':'Evening Mix'}],[tracks(['Blue Harbor'],True)],['return'],lifecycle='restart')
    ],load=True))
    for fmt in ('m3u','pls','xspf'):
        key='gui-playlist-export-'+fmt;dest=path(key,'Evening.'+fmt,'outputs')
        out.append(episode(key,'playlist-formats',GUI_FILES[:3],[
            step('save',f'Save the current playlist as {dest}, using the {fmt.upper()} playlist format.',
                 'The playlist has been saved successfully and its three tracks remain available.',
                 [{'op':'save-playlist','file':dest,'format':fmt}],[{'kind':'playlist-file','name':'Evening.'+fmt,'files':[['inputs',n] for n in GUI_FILES[:3]]}],
                 requires={'visible':['state-1']}),
            step('clear','Clear the current playlist.','The playlist is empty.',[{'op':'menu','path':['Playlist','Clear playlist']}],
                 [tracks([])],['save']),
            step('reload',f'Load the saved playlist {dest}.','Aurora, Blue Harbor and Cedar Road are restored in their saved order.',
                 [{'op':'load-playlist','file':dest}],[tracks(TITLES[:3],True)],['clear'])
        ],load=True))
    key='gui-tag-editing'
    out.append(episode(key,'tag-editing',GUI_FILES[:2],[
        step('identity','Change Aurora\'s title to "Aurora Revisited" and artist to "Mira North", and save the changes.',
             'The playlist identifies the track as Aurora Revisited by Mira North.',
             [{'op':'tags','title':'Aurora','fields':{'Title':'Aurora Revisited','Artist':'Mira North'}}],
             [{'kind':'tags','file':GUI_FILES[0],'values':{'title':'Aurora Revisited','artist':'Mira North'}}]),
        step('details','Set that track\'s album to "Winter Sketches", genre to "Classical", year to 2025, track number to 8 and disc number to 2. Save the changes.',
             'The saved tag editor shows Winter Sketches, Classical, year 2025, track 8 and disc 2.',
             [{'op':'tags','title':'Aurora Revisited','fields':{'Album':'Winter Sketches','Genre':'Classical','Year':'2025','Track':'8','Disc':'2'},'reopen':True}],
             [{'kind':'tags','file':GUI_FILES[0],'values':{'album':'Winter Sketches','genre':'Classical','date':'2025','tracknumber':'8','discnumber':'2'}}],['identity']),
        step('comment','Set that track\'s composer to "Émile Chen" and comment to "Recorded in winter". Save the changes.',
             'The saved tag editor shows composer Émile Chen and comment Recorded in winter.',
             [{'op':'tags','title':'Aurora Revisited','fields':{'Composer':'Émile Chen','Comment':'Recorded in winter'},'reopen':True}],
             [{'kind':'tags','file':GUI_FILES[0],'values':{'composer':'Émile Chen','comment':'Recorded in winter'}}],['details']),
        step('cancel','Change its title to "Discarded Title", then discard the change. Reopen its tags to inspect the saved title.',
             'The saved title is still Aurora Revisited.',[{'op':'tags','title':'Aurora Revisited','fields':{'Title':'Discarded Title'},'discard':True,'reopen':True}],
             [{'kind':'tags','file':GUI_FILES[0],'values':{'title':'Aurora Revisited'}}],['comment']),
        step('lyrics','Save the lyrics "Under the northern sky" on that track, and reopen its lyrics to inspect them.',
             'The saved lyrics read Under the northern sky.',[{'op':'lyrics','title':'Aurora Revisited','value':'Under the northern sky'}],
             [{'kind':'tags','file':GUI_FILES[0],'values':{'lyrics':'Under the northern sky'}}],['cancel'])
    ],load=True))
    out.extend(extra())
    from additions import gui_episodes,smart_edit_episode
    out.extend(gui_episodes())
    out.append(smart_edit_episode())
    return out


def extra():
    out=[]
    key='gui-repeat-shuffle'
    out.append(episode(key,'playback-modes',GUI_FILES[:3],[
        step('repeat-track','Enable repeating the current track.','Repeat mode indicates that the current track repeats.',
             [{'op':'menu','path':['Playlist','Repeat mode','Repeat track']},{'op':'show-repeat-mode'}],[player(LoopStatus='Track')]),
        step('repeat-list','Enable repeating the whole playlist.','Repeat mode indicates that the playlist repeats.',
             [{'op':'press','key':'Escape'},{'op':'press','key':'Escape'},{'op':'menu','path':['Playlist','Repeat mode','Repeat playlist']},{'op':'show-repeat-mode'}],[player(LoopStatus='Playlist')],['repeat-track']),
        step('repeat-off','Turn repeating off.','Repeating is off.',[{'op':'press','key':'Escape'},{'op':'press','key':'Escape'},{'op':'menu','path':['Playlist','Repeat mode','Don\'t repeat']}],
             [player(LoopStatus='None')],['repeat-list']),
        step('shuffle-on','Enable shuffling all tracks.','Shuffle is enabled for all tracks.',
             [{'op':'menu','path':['Playlist','Shuffle mode','Shuffle all']}],[player(Shuffle=True)]),
        step('shuffle-off','Turn shuffle off.','Shuffle is off.',[{'op':'menu','path':['Playlist','Shuffle mode','Don\'t shuffle']}],
             [player(Shuffle=False)],['shuffle-on'])
    ],load=True))
    key='gui-volume'
    out.append(episode(key,'volume',GUI_FILES[:1],[
        step('half','Set the playback volume to 50%.','The displayed volume is 50%.',[{'op':'volume','percent':50}],
             [player(Volume=.5)]),
        step('mute','Mute the player.','The player indicates muted audio.',[{'op':'menu','path':['Music','Mute']}],
             [],['half']),
        step('restore','Unmute the player.','The volume returns to 50%.',[{'op':'menu','path':['Music','Mute']}],
             [],['mute'])
    ],load=True))
    key='gui-equalizer'
    out.append(episode(key,'equalizer',[],[
        step('rock','Enable the equalizer and select the Rock preset. Leave it open for inspection.',
             'The equalizer is enabled, Rock is selected, and its band controls show a non-flat curve.',
             [{'op':'equalizer','preset':'Rock','enabled':True}]),
        step('zero','Select the Zero equalizer preset.','Zero is selected and all equalizer bands are at zero.',
             [{'op':'equalizer','preset':'Zero','enabled':True}],depends=['rock']),
        step('balance','Enable the stereo balancer and move it to the leftmost position.',
             'The stereo balancer is enabled and set fully left.',[{'op':'balance','left':True}],depends=['zero']),
        step('persist','After the application restart, open the equalizer to inspect the saved settings.',
             'The equalizer remains enabled with Zero selected, and the stereo balancer remains enabled and fully left.',
             [{'op':'menu','path':['Tools','Equalizer']}],depends=['balance'],lifecycle='restart'),
        step('disabled','Disable both the equalizer and the stereo balancer.',
             'Both processing options are disabled, with their controls inactive.',
             [{'op':'check','target':{'role':'check box','name':'Enable equalizer'},'checked':False},
              {'op':'check','target':{'role':'check box','name':'Enable stereo balancer'},'checked':False}],depends=['persist'])
    ]))
    key='gui-settings'
    out.append(episode(key,'settings',[],[
        step('volume-step','In settings, change the volume increment to 10 and save. Reopen settings to inspect the value.',
             'The saved volume increment is 10.',[{'op':'setting','page':'Behavior','spin':'Volume Increment','value':'10','reopen':True}]),
        step('cancel','Change the volume increment to 25, then cancel. Reopen settings to inspect the saved value.',
             'The volume increment remains 10.',[{'op':'setting','page':'Behavior','spin':'Volume Increment','value':'25','cancel':True,'reopen':True}],depends=['volume-step']),
        step('restart','After the application restart, open the behavior settings to inspect the volume increment.',
             'The volume increment remains 10 after restart.',[{'op':'setting','page':'Behavior'}],depends=['cancel'],lifecycle='restart'),
        step('relative','Set saved playlist paths to Relative and save. Reopen the playlist settings to inspect it.',
             'Relative paths are selected for saving playlists.',[{'op':'setting','page':'Playlist','radio':'Relative','reopen':True}],depends=['restart']),
        step('replaygain','Enable normalization using Replay Gain metadata and save. Reopen backend settings to inspect it.',
             'Replay Gain metadata is selected as the audio normalization method.',
             [{'op':'setting','page':'Backend','radio':'Use Replay Gain metadata if it is available','reopen':True}],depends=['relative'])
    ]))
    key='gui-collection'
    out.append(episode(key,'collection',GUI_FILES,[
        step('browse','Show the collection grouped by artist, expand Lina Vale, and expand Northern Lights to see its tracks.',
             'The collection shows Lina Vale / Northern Lights containing Aurora and Cedar Road.',
             [{'op':'collection-browse'}]),
        step('filter','Filter the collection for "Orion".',
             'The matching collection shows Orion Trio and Harbor Sessions with Blue Harbor.',
             [{'op':'collection-filter','value':'Orion','expand':['Orion Trio','Harbor Sessions']}],depends=['browse']),
        step('add','Add the matching Blue Harbor track from the collection to the playlist.',
             'Blue Harbor is present in the playlist.',[{'op':'collection-add','title':'Blue Harbor'}],
             [tracks(['Blue Harbor'],True)],['filter']),
        step('unicode','Clear the collection filter and find the artist 青い鳥, album 夜の音楽 and track 雨の音.',
             'The collection visibly contains 青い鳥 / 夜の音楽 / 雨の音.',
             [{'op':'collection-filter','value':'青い鳥','expand':['青い鳥','夜の音楽']}],depends=['add'])
    ],collection=True))
    key='gui-smart-playlist'
    out.append(episode(key,'smart-playlists',GUI_FILES,[
        step('create','Create a smart playlist named "Lina Selection" matching Artist contains "Lina", sorted by Title ascending, containing all matching songs.',
             'The saved smart playlist Lina Selection is available in the smart playlist list.',
             [{'op':'smart-create','name':'Lina Selection','field':'Artist','value':'Lina'}]),
        step('use','Open the Lina Selection smart playlist.',
             'The generated playlist contains Aurora and Cedar Road in title order.',
             [{'op':'smart-open','name':'Lina Selection'}],[tracks(['Aurora','Cedar Road'],True)],['create']),
        step('persist','After the application restart, clear the current playlist, then open the saved Lina Selection smart playlist.',
             'Lina Selection remains available and generates Aurora and Cedar Road.',
             [{'op':'menu','path':['Playlist','Clear playlist']},{'op':'smart-open','name':'Lina Selection'}],[tracks(['Aurora','Cedar Road'],True)],['use'],lifecycle='restart')
    ],collection=True))
    key='gui-queue'
    out.append(episode(key,'queue',GUI_FILES[:3],[
        step('enqueue','Queue Cedar Road and then Aurora, and show the queue.',
             'The queue contains Cedar Road followed by Aurora.',[{'op':'queue','titles':['Cedar Road','Aurora']}]),
        step('dequeue','Remove Cedar Road from the queue, leaving Aurora queued.',
             'Aurora is the only queued track.',[{'op':'queue','titles':['Cedar Road']}],depends=['enqueue'])
    ],load=True))
    for fmt,label,extension in [('wav','Wav (.wav)','wav'),('mp3','MP3 (.mp3)','mp3'),('opus','Ogg Opus (.opus)','opus'),('flac','FLAC (.flac)','flac'),('alac','ALAC (.m4a)','m4a'),('aac','M4A AAC (.mp4)','mp4'),('vorbis','Ogg Vorbis (.ogg)','ogg'),('speex','Ogg Speex (.spx)','spx'),('wavpack','WavPack (.wv)','wv'),('asf','Windows Media audio (.wma)','wma'),('ogg-flac','Ogg FLAC (.ogg)','ogg')]:
        key='gui-transcode-'+fmt
        source='Speech Journey.flac' if fmt=='speex' else fixtures.TRANSCODE_SOURCE
        out.append(episode(key,'transcoding',[source],[
            step('convert',f'Transcode {path(key,source)} to {label}, placing the converted file in {path(key,"", "outputs")}.',
                 'The transcoder reports successful completion for the requested track with no failed conversions.',
                 [{'op':'transcode','file':path(key,source),'format':label,'destination':path(key,'','outputs')}],
                 [{'kind':'audio','name':source.removesuffix('.flac')+'.'+extension,'source':source,'codec':fmt}],requires={'visible':['state-1']})
        ]))
    key='gui-cover-manager'
    out.append(episode(key,'cover-art',GUI_FILES,[
        step('browse','Open the cover manager and show the albums in the collection.',
             'The cover manager lists the collection albums, including Northern Lights, Harbor Sessions and Night Sky.',
             [{'op':'menu','path':['Tools','Cover Manager']},{'op':'maximize'}]),
        step('filter','Filter the cover manager for "Northern".',
             'Northern Lights is the matching visible album.',[{'op':'cover-filter','value':'Northern'}],depends=['browse'])
    ],collection=True))
    key='gui-organize-files'
    out.append(episode(key,'file-organization',GUI_FILES[:1],[
        step('organize','Organize Aurora within the collection folder using the naming pattern "%artist/%album/%track - %title.%extension", keeping spaces and removing the original file after copying.',
             'The operation completes and the visible collection still contains Aurora under Lina Vale and Northern Lights.',
             [{'op':'organize','title':'Aurora','pattern':'%artist/%album/%track - %title.%extension'}],
             [{'kind':'organized','file':'Lina Vale/Northern Lights/01 - Aurora.flac'}]),
        step('restart','After the application restart, find Aurora in the collection and add it to the playlist.',
             'Aurora can still be found and added from the organized collection.',
             [{'op':'collection-filter','value':'Aurora','expand':['Lina Vale','Northern Lights']},{'op':'collection-add','title':'Aurora'}],
             [tracks(['Aurora'],True)],['organize'],lifecycle='restart')
    ],collection=True))
    return out
