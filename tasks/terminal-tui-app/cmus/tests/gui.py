"""Visible user goals; recipes are only used to record the upstream reference."""
from specification import a,cp,episode,q,st,media_setup
from programs import setting_check
import fixtures

def console(text):return [{'key':':'},{'type':text},{'key':'Enter'}]
def frontend(id,goal,steps,check,acceptance,prepare=(),depends=()):
    return cp(id,goal,steps,[a('result','The native product output confirms the requested result.',check)],prepare=prepare,depends=depends,front=acceptance,requires={'visible':['result']})
def visual(id,goal,steps,acceptance,prepare=(),depends=()):
    return cp(id,goal,steps,[],prepare=prepare,depends=depends,front=acceptance)

def build():
    out=[]
    base=media_setup(True)
    # A populated library gives every navigation goal a visible difference.
    for view,title in [('1','Library'),('2','Library'),('3','Playlist'),('4','Play Queue'),('5','Browser'),('6','Filters'),('7','Settings')]:
        view_goal={'1':'Show the library grouped by artist and album.','2':'Show the library as a sorted track list.'}.get(view,'Show the '+title+' view.')
        view_accept={'1':'The library displays its artist and album groups with a track pane.','2':'The library displays a single sorted list of tracks.'}.get(view,'The '+title+' view is visible with its relevant content.')
        cps=[visual('view',view_goal,[{'key':view}],view_accept,prepare=['view '+('5' if view!='5' else '2')])]
        if view=='1':
            cps += [visual('expand','Expand the Aster artist in the library tree.',[{'key':'/'},{'type':'Aster'},{'key':'Enter'}],'The Aster artist is expanded and its Dawn album is visible.',prepare=['view 1']),frontend('tracks','Focus the track pane for the Aster album.',[{'key':'Tab'}],q('echo {}','selected-in',names=['breeze.flac','amber.flac'],guard=True),'The track pane for the selected album has an identifiable selection.',depends=['expand'])]
        if view=='2':
            cps += [frontend('last','Select the last track in the sorted library.',[{'key':'G'}],q('echo {}',nonempty=True),'The final track in the sorted library is visibly selected.',prepare=['view 2']),frontend('first','Select the first track in the sorted library.',[{'key':'g'}],q('echo {}',nonempty=True),'The first track in the sorted library is visibly selected.',prepare=['view 2'])]
        out.append(episode('gui-view-'+view,'navigation',cps,base,gui=True))
    # Search results are exact goals rather than prescribed routes.
    for i,(name,term) in enumerate([('Amber','Amber'),('Echo','Echo'),('Cobalt','Cobalt'),('Jade été','Jade'),('光','光'),('Breeze','Breeze'),('Garden','Garden'),('Fable','Fable')]):
        cps=[frontend('find','Find and select the track '+name+'.',[{'key':'/'},{'type':term},{'key':'Enter'}],q('echo {}',nonempty=True),'The track '+name+' is visibly selected.',prepare=['view 2','win-bottom' if i%2 else 'win-top'])]
        if term=='Amber':
            cps += [frontend('artist','Find and select Echo by Cedar.',[{'key':'/'},{'type':'Cedar'},{'key':'Enter'}],q('echo {}',nonempty=True),'Echo by Cedar is selected.'),frontend('next','Select the next Cedar search match.',[{'key':'n'}],q('echo {}',nonempty=True),'The next Cedar track is selected.',depends=['artist']),frontend('previous','Return to the previous Cedar match.',[{'key':'N'}],q('echo {}',nonempty=True),'The earlier Cedar match is selected.',depends=['next'])]
        out.append(episode('gui-search-'+str(i),'search',cps,base,gui=True))
    # Sorts expose a visibly changed order using strongly different sort keys.
    for i,(label,expression) in enumerate([('title','title'),('artist descending','-artist'),('duration','duration'),('duration descending','-duration'),('year','date'),('year descending','-date'),('album','album'),('genre then title','genre title')]):
        # The native selected file after a jump gives a layout-independent companion for the final order.
        steps=console('set lib_sort='+expression)+[{'key':'g'}]
        sort_fields=expression.split()
        ties={}
        for name,tags,duration in fixtures.TRACKS:
            values=[str(duration) if f.lstrip('-')=='duration' else tags.get(f.lstrip('-'),'') for f in sort_fields]
            ties[name]='|'.join(values)
        cps=[frontend('sort','Sort the library by '+label+'.',steps,dict(source='visible',project='ordered',ties=ties,nonempty=True),'The sorted library displays tracks in '+label+' order.',prepare=['view 2','set lib_sort=filename'])]
        out.append(episode('gui-sort-'+str(i),'sorting',cps,base,gui=True))
    # Add/remove/filter are tested through a populated before view with an observable after view.
    for i,(label,expr,visible) in enumerate([('Jazz','genre="Jazz"',['Amber','Breeze']),('Rock','genre="Rock"',['Cobalt','Delta']),('Folk','genre="Folk"',['Echo','Fable']),('long tracks','duration>200',['Cobalt','Echo','Garden']),('Aster','artist="Aster"',['Amber','Breeze']),('recent tracks','date>=2020',['Echo','Fable','光'])]):
        cps=[frontend('filter','Filter the library to '+({'long tracks':'tracks longer than 200 seconds','recent tracks':'tracks dated 2020 or later'}.get(label,label))+'.',console('filter '+expr),q('save -L -','paths',nonempty=True),'Only '+({'long tracks':'tracks longer than 200 seconds','recent tracks':'tracks dated 2020 or later'}.get(label,'the '+label+' tracks'))+' remain in the library listing.',prepare=['view 2']),frontend('restore','Clear the temporary library filter.',console('filter'),q('save -L -','paths',nonempty=True),'The full library is visible again.',depends=['filter'])]
        out.append(episode('gui-filter-'+str(i),'filters',cps,base,gui=True))
    for i,term in enumerate(['Aster','Night','Jade','光']):
        out.append(episode('gui-live-'+str(i),'filters',[frontend('live','Use a live filter for '+term+'.',console('live-filter '+term),dict(source='visible',project='members',nonempty=True),'The library displays only tracks matching '+term+'.',prepare=['view 2'])],base,gui=True))
    # Queue copies, ordering and removal.
    for i,(source,title) in enumerate([('amber.flac','Amber'),('cobalt.flac','Cobalt'),('jade.flac','Jade été'),('koto space.flac','光')]):
        cps=[frontend('append','Add '+title+' to the play queue and show it.',console('add -q /workspace/inbox/'+source)+[{'key':'4'}],q('save -q -','paths',nonempty=True),'The play queue contains '+title+'.'),frontend('prepend','Place Echo before the existing queued track.',console('add -Q /workspace/inbox/echo.flac'),q('save -q -','paths',unordered=False,nonempty=True),'Echo is listed before the previously queued track.',depends=['append']),frontend('remove','Remove Echo from the queue, preserving the other track.',[{'key':'g'},{'key':'D'}],q('save -q -','paths',unordered=False,nonempty=True),'Echo is removed while '+title+' remains queued.',depends=['prepend'])]
        out.append(episode('gui-queue-'+str(i),'queue',cps,base,gui=True))
    # Named playlist goals use selected versus marked playlist semantics explicitly.
    for i,name in enumerate(['Favorites','Evening','旅行']):
        cps=[frontend('create','Create a playlist named '+name+' and display it.',console('pl-create '+name)+[{'key':'3'},{'key':'G'}],dict(source='screen',project='screen-has',texts=[name]),'A named playlist '+name+' is visible.'),frontend('add','Mark '+name+' as the destination and add Amber and Echo to it.',[{'key':'Space'}]+console('add -p /workspace/inbox/amber.flac')+console('add -p /workspace/inbox/echo.flac'),q('save -p -','paths',nonempty=True),'The '+name+' playlist displays Amber and Echo.',depends=['create']),frontend('rename','Rename the playlist to '+name+' Mix.',console('pl-rename '+name+' Mix'),dict(source='screen',project='screen-has',texts=[name+' Mix']),'The playlist is visibly named '+name+' Mix.',depends=['add'])]
        out.append(episode('gui-playlist-'+str(i),'playlists',cps,base,gui=True))
    # Playback: paused evidence avoids depending on the wall clock during evaluator operations.
    for i,(file,title) in enumerate([('amber.flac','Amber'),('cobalt.flac','Cobalt'),('jade.flac','Jade été'),('koto space.flac','光')]):
        cps=[frontend('play','Play '+title+' then pause it.',console('player-play /workspace/inbox/'+file)+[{'key':'c'}],q('status','status',field='status',guard='paused'),'The current track is '+title+' and playback is paused.',prepare=['view 2']),frontend('seek','Seek the paused track to one minute.',console('seek 1m'),q('status','status',field='position',number=True,tolerance=1),'The paused playback position shows one minute.',depends=['play']),frontend('stop','Stop playback.',[{'key':'v'}],q('status','status',field='status',guard='stopped'),'The player displays a stopped state.',depends=['seek'])]
        out.append(episode('gui-play-'+str(i),'playback',cps,base,gui=True))
    # Visible mode toggles have status indicators, unlike purely internal options.
    for i,(option,label,key,start) in enumerate([('repeat','repeat','r','false'),('follow','follow','f','false'),('continue','continuous playback','C','false'),('play_sorted','sorted library playback','o','false'),('play_library','library playback','M','false'),('repeat_current','repeat current track','Control+R','false'),('shuffle','track shuffle','s','off'),('aaa_mode','artist scope','m','all')]):
        cps=[frontend('enable','Enable '+label+'.',[{'key':key}],setting_check(option,nonempty=True),'The player status visibly indicates '+label+'.',prepare=['set '+option+'='+start]),frontend('cycle',{'shuffle':'Switch shuffle to albums.','aaa_mode':'Switch playback scope to the current album.','play_library':'Switch playback source to the playlist.'}.get(option,'Disable '+label+'.'),[{'key':key}],setting_check(option,nonempty=True),{'shuffle':'The status indicates album shuffle.','aaa_mode':'The status indicates album scope.','play_library':'The status indicates playlist playback.'}.get(option,'The status indicates that '+label+' is disabled.'),depends=['enable'])]
        out.append(episode('gui-mode-'+str(i),'settings',cps,base,gui=True))
    # Volume has explicit left/right values and mute restores them.
    cps=[frontend('channels','Set left volume to 35% and right to 65%.',console('vol 35 65'),q('status','status',field='set.vol_left',guard='35'),'The status shows distinct left and right volumes of 35% and 65%.'),frontend('louder','Increase both channel volumes by ten percentage points.',[{'key':'+'}],q('status','status',field='set.vol_left',guard='45'),'The volume indicator increases to 45% left and 75% right.',depends=['channels']),frontend('mute','Mute the player.',console('mute'),q('status','status',field='set.vol_left',guard='0'),'The player volume is visibly muted.',depends=['louder']),frontend('unmute','Restore the volume after muting.',console('mute'),q('status','status',field='set.vol_left',guard='45'),'The previously set channel volumes return.',depends=['mute'])]
    out.append(episode('gui-volume','playback',cps,base,gui=True))
    # Browser navigation and adding directory entries are visible filesystem use cases.
    cps=[frontend('enter','Open the inbox directory in the browser.',[{'key':'5'}]+console('cd /workspace/inbox'),dict(source='screen',project='screen-has',texts=['inbox','amber.flac']),'The browser displays the inbox audio files.'),frontend('hidden','Show hidden browser entries.',[{'key':'i'}],setting_check('show_hidden',guard='true'),'The hidden .hidden.flac audio file becomes visible.',depends=['enter']),frontend('parent','Navigate back to the workspace directory.',[{'key':'Backspace'}],q('pwd',nonempty=True),'The browser shows the workspace with inbox and outbox directories.',depends=['hidden'])]
    hidden=media_setup();hidden[0]['files'].append(dict(hidden[0]['files'][0],filename='.hidden.flac'))
    out.append(episode('gui-browser','browser',cps,hidden,gui=True))
    # User-facing console and format customization.
    cps=[frontend('message','Display the message Ready to listen.',console('echo Ready to listen'),dict(source='screen',project='screen-has',texts=['Ready to listen']),'Ready to listen appears on the message line.'),frontend('format','Set the playlist display format to the exact text `%t -- %a`.',console('set format_playlist=%t -- %a'),setting_check('format_playlist',guard='%t -- %a'),'Ordinary tagged tracks controlled by format_playlist display title followed by artist; compilation rows use their separate format.',prepare=['view 2']),frontend('duration','Hide elapsed playback position from the status display.',console('set show_playback_position=false'),setting_check('show_playback_position',guard='false'),'The elapsed position is hidden from the player status.',prepare=[{'play_paused':'/workspace/inbox/amber.flac'}]),frontend('remaining','Show remaining playback time for the paused track.',console('set show_playback_position=true')+console('set show_remaining_time=true'),setting_check('show_remaining_time',guard='true'),'The paused track status displays remaining time.',depends=['duration'])]
    out.append(episode('gui-console-display','display',cps,base,gui=True))
    # Library membership changes show an actual before/after result.
    cps=[frontend('add','Add Amber to the library and display it.',console('add -l /workspace/inbox/amber.flac')+[{'key':'2'}],q('save -l -','paths',guard=['amber.flac']),'The library contains Amber.'),frontend('directory','Add the inbox directory to the library.',console('add -l /workspace/inbox'),q('save -l -','paths',nonempty=True),'The library now includes the inbox collection, including the other artists.',depends=['add']),frontend('remove','Remove Amber from the library while keeping the other tracks.',[{'key':'/'},{'type':'Amber'},{'key':'Enter'},{'key':'D'}],q('save -l -','paths',nonempty=True),'Amber is removed from the populated library while the other tracks remain.',depends=['directory'])]
    out.append(episode('gui-library-edit','library',cps,media_setup(),gui=True))
    cps=[frontend('define','Define a filter named JazzOnly for Jazz music and show it in the filter view.',console('fset JazzOnly=genre="Jazz"')+[{'key':'6'}],dict(source='screen',project='screen-has',texts=['JazzOnly']),'The JazzOnly filter appears with its genre condition.'),frontend('activate','Activate JazzOnly and show its library result.',console('factivate JazzOnly')+[{'key':'2'}],q('save -L -','paths',guard=['amber.flac','breeze.flac']),'Only Amber and Breeze remain visible through JazzOnly.',depends=['define']),frontend('negate','Apply the inverse of JazzOnly.',console('factivate !JazzOnly'),q('save -L -','paths',nonempty=True),'The library displays the tracks outside the Jazz genre.',depends=['activate'])]
    out.append(episode('gui-named-filter','filters',cps,base,gui=True))
    cps=[frontend('define','Bind common key X to toggle repeat and display the binding.',console('bind -f common X toggle repeat')+console('showbind common X'),q('showbind common X',nonempty=True),'The command display identifies X as the repeat toggle.'),frontend('invoke','Use X to enable repeat.',[{'key':'X'}],setting_check('repeat',guard='true'),'The player visibly enables repeat through the configured binding.',prepare=['set repeat=false'],depends=['define']),frontend('replace','Change X to toggle shuffle, and use it to enable track shuffle.',console('bind -f common X toggle shuffle')+[{'key':'X'}],setting_check('shuffle',guard='tracks'),'The rebound key enables track shuffle.',prepare=['set shuffle=off'],depends=['invoke'])]
    out.append(episode('gui-custom-binding','bindings',cps,base,gui=True))
    # Editing a subset of queued tracks exposes mark, move, remove and copy behavior.
    for i,label in enumerate(['Aster tracks','Rock tracks','Folk tracks']):
        expr=['artist="Aster"','genre="Rock"','genre="Folk"'][i]
        setup=media_setup()
        setup.append({'id':'queue','op':'drive','steps':['add -q inbox',{'wait_list':{'command':'save -q -','count':12}},'view 4']})
        cps=[visual('mark','Mark the '+label+' in the queue.',console('mark '+expr),'The '+label+' are visibly marked in the queue.'),frontend('copy','Copy the marked queue tracks to the library and show the library.',[{'key':'a'},{'key':'2'}],q('save -l -','paths',nonempty=True),'The library shows the tracks copied from the marked queue subset.',depends=['mark']),frontend('remove','Return to the queue and remove its marked tracks.',[{'key':'4'},{'key':'D'}],q('save -q -','paths',nonempty=True),'The marked subset is removed from the queue and the other tracks remain.',depends=['copy'])]
        out.append(episode('gui-marked-edit-'+str(i),'selection',cps,setup,gui=True))
    return out
