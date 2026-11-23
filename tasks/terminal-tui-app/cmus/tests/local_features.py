"""Local episodes covering native commands, saved state and interactive editors."""
import base64
import json
from pathlib import Path
from specification import a,cp,episode,q,captured,st,fs,media_setup
from programs import base64file,setting_check,split,quote
import fixtures


def waitlist(count,command='save -l -'):
    return {'wait_list':{'command':command,'count':count}}

def file(name,tags,seconds=10,mtime=1704067200):
    return {'filename':name,'base64':base64.b64encode(fixtures.flac(tags,seconds)).decode(),'mtime':mtime}

def terminal(text):return [{'key':':'},{'type':text},{'key':'Enter'}]
def search(text):return [{'key':'/'},{'type':text},{'key':'Enter'}]
def files_check(names):return dict(source='workspace',request={'action':'list','path':'inbox'},project='workspace-names',guard=sorted(names))

def named_io():
    setups=media_setup()
    setups[0]['files'] += [base64file('duo.m3u','amber.flac\ncobalt.flac\n'),base64file('other.pls','[playlist]\nNumberOfEntries=2\nFile1=echo.flac\nFile2=jade.flac\nVersion=2\n')]
    cps=[
        cp('m3u','Import a named M3U playlist.',['pl-import /workspace/inbox/duo.m3u','view 3','/duo.m3u',waitlist(2,'save -p -')],[a('tracks','The imported M3U has its two entries in file order.',q('save -p -','paths',unordered=False,guard=['amber.flac','cobalt.flac']))]),
        cp('export','Export the selected named playlist.',['pl-export /workspace/outbox/named.m3u'],[a('file','Named playlist export writes the selected sequence.',fs('outbox/named.m3u',paths=True,unordered=False,guard=['amber.flac','cobalt.flac']))],depends=['m3u']),
        cp('pls','Import a named PLS playlist.',['pl-import /workspace/inbox/other.pls','view 3','/other.pls',waitlist(2,'save -p -')],[a('tracks','Named PLS import preserves the intended entries.',q('save -p -','paths',unordered=False,guard=['echo.flac','jade.flac']))]),
        cp('overwrite','Overwrite an existing export with another selected playlist.',terminal('pl-export /workspace/outbox/named.m3u')+[{'key':'y'}],[a('file','Export replaces the old contents rather than appending.',fs('outbox/named.m3u',paths=True,unordered=False,guard=['echo.flac','jade.flac']))],depends=['pls']),
        cp('collision','Import the same basename twice.',['pl-import /workspace/inbox/duo.m3u','save -p'],[a('names','Duplicate import names receive distinct native playlist names.',st('playlists','state-names'))],depends=['m3u']),
        cp('browser-selected','Import the selected browser playlist without a path.',['view 5','cd /workspace/inbox','/other.pls','pl-import','view 3','/other.pls.1',waitlist(2,'save -p -')],[a('tracks','An omitted import path uses the browser selection.',q('save -p -','paths',unordered=False,guard=['echo.flac','jade.flac']))],depends=['pls']),
        cp('delete-all','Delete the populated named playlist collection.',['pl-delete -a'],[a('names','Deleting all named playlists creates the native empty default.',st('playlists','state-names'))],depends=['collision']),
    ]
    return [episode('named-playlist-io','playlists',cps,setups)]


def restart_effects():
    out=[]
    setup=media_setup(True)
    cps=[cp('library','Restart a nonempty library.',[{'restart':True},waitlist(12)],[a('membership','The running library is populated from its saved files.',q('save -l -','paths',guard=sorted(x[0] for x in fixtures.TRACKS)))]),
         cp('queue','Restore a nonempty queue with resume enabled.',['set resume=true','add -q /workspace/inbox/cobalt.flac','add -q /workspace/inbox/amber.flac',waitlist(2,'save -q -'),{'restart':True},waitlist(2,'save -q -')],[a('queue','Resume restores the active queue contents and order.',q('save -q -','paths',unordered=False,guard=['cobalt.flac','amber.flac']))]),
         cp('resume-disabled','Start without queue restoration when resume is disabled.',['set resume=false',{'restart':True}],[a('queue','Disabling resume does not load the previous queue into playback.',q('save -q -','paths',allow_empty=True,guard=[]))],depends=['queue']),
         cp('volume','Restore unequal channel volumes.',['vol 27 63',{'restart':True}],[a('left','The restored software mixer uses its saved left volume.',q('status','status',field='set.vol_left',guard='27')),a('right','The restored software mixer uses its saved right volume.',q('status','status',field='set.vol_right',guard='63'))]),
         cp('paused','Resume a selected paused track.',['set resume=true',{'play_paused':'/workspace/inbox/amber.flac'},'seek 30',{'restart':True}],[a('track','The running player restores the paused track.',q('status','status',field='file',guard='amber.flac')),a('status','Paused playback remains paused after restart.',q('status','status',field='status',guard='paused')),a('position','The paused resume position is restored.',q('status','status',field='position',number=True,tolerance=1))]),
         cp('named','Restore two different named playlists.',['player-stop','pl-import /workspace/inbox/one.m3u','pl-import /workspace/inbox/two.m3u',{'restart':True},'view 3','/one.m3u',waitlist(2,'save -p -'),{'remote':'save -p -','save':'one'},'/two.m3u',waitlist(2,'save -p -')],[a('one','First playlist contents are restored into the running application.',captured('one','paths',unordered=False,guard=['amber.flac','breeze.flac'])),a('two','Second playlist remains separate with its own order.',q('save -p -','paths',unordered=False,guard=['echo.flac','cobalt.flac']))]),
    ]
    setup[0]['files'] += [base64file('one.m3u','amber.flac\nbreeze.flac\n'),base64file('two.m3u','echo.flac\ncobalt.flac\n')]
    # Named playlist fixtures are ignored during initial audio-directory loading to avoid duplicates.
    setup[1]['steps']=['add -l /workspace/inbox/'+x[0] for x in fixtures.TRACKS]+[waitlist(12)]
    out.append(episode('restart-content','persistence',cps,setup))
    cps=[]
    for view in ('tree','sorted','playlist','queue','browser','filters','settings'):
        cps.append(cp(view,'Use start_view='+view+' on a fresh process.',['set resume=false','set start_view='+view,{'restart':True},'set resume=true',{'quit_saved':True}],[a('view','The running startup view is the configured one.',st('resume','state-line',prefix='view ',guard=view))]))
    out.append(episode('startup-views','persistence',cps))
    setup=media_setup(True)
    cps=[cp('substitute','Save library paths relative to HOME.',['set pl_env_vars=HOME',{'restart':True},waitlist(12),'save -l /workspace/outbox/variables.m3u'],[a('paths','Native export uses its documented variable token for each path.',dict(source='workspace',request={'action':'read','path':'outbox/variables.m3u'},project='variable-paths',variable='HOME',count=12))]),
         cp('reload','Load the variable-based playlist into the active library.',['clear -l','load -l /workspace/outbox/variables.m3u',waitlist(12)],[a('contents','Environment-variable substitution resolves all exported entries.',q('save -L -','paths',guard=sorted(x[0] for x in fixtures.TRACKS)))],depends=['substitute']),
         cp('remove','Return to ordinary paths after disabling variable substitution.',['set pl_env_vars=',{'restart':True},waitlist(12),'save -l /workspace/outbox/absolute.m3u'],[a('paths','Ordinary saved paths no longer contain variable tokens.',dict(source='workspace',request={'action':'read','path':'outbox/absolute.m3u'},project='absolute-paths',count=12))],depends=['reload'])]
    out.append(episode('playlist-environment','persistence',cps,setup))
    return out


def long_setup():
    files=[file(f'page-{i:02d}.flac',{'artist':'Pager','album':'Long','title':f'Track-{i:02d}','tracknumber':str(i+1)},2) for i in range(60)]
    return [{'id':'media','op':'upload','files':files},{'id':'library','op':'drive','steps':['add -l inbox',waitlist(60),'view 2','set lib_sort=filename','set format_playlist=%t']}]

def paging():
    cps=[]
    for name,command,start in [('page-down','win-page-down',0),('page-up','win-page-up',59),('half-down','win-half-page-down',0),('half-up','win-half-page-up',59),('page-top','win-page-top',40),('page-middle','win-page-middle',40),('page-bottom','win-page-bottom',40),('scroll-down','win-scroll-down',40),('scroll-up','win-scroll-up',40)]:
        cps.append(cp(name,'Navigate the long listing with '+command+'.',[{'navigate':{'command':command,'rule':name},'save':'movement'}],[a('movement','The command moves the selection or viewport by its page-relative meaning.',captured('movement','identity',guard=True))],prepare=['view 2','win-top','win-down '+str(start)]))
    cps.append(cp('small-terminal','Use paging after resizing the terminal.',[{'call':{'op':'resize','columns':80,'rows':24}},'win-top',{'navigate':{'command':'win-page-down','rule':'page-down'},'save':'movement'}],[a('movement','Paging uses the new visible page size.',captured('movement','identity',guard=True))]))
    cps.append(cp('current','Select the playing track from a different selection.',['view 2','/Track-20','win-activate','player-pause-playback','win-bottom','win-sel-cur'],[a('selected','Select-current returns to the active library track.',q('echo {}','selected-in',names=['page-20.flac'],guard=True))]))
    for source,dest in [('queue','browser'),('sorted','filters'),('settings','tree')]:
        cps.append(cp('previous-'+source,'Return from '+dest+' to the prior '+source+' view.',['view '+source,'view '+dest,'prev-view','set resume=true',{'quit_saved':True}],[a('view','Previous-view restores the prior active view.',st('resume','state-line',prefix='view ',guard=source))]))
    # A redraw of an already current screen is idempotent; exercise refresh without a duplicate score.
    next(c for c in cps if c['id']=='small-terminal')['steps'].append('refresh')
    return [episode('paging-navigation','navigation',cps,long_setup())]


def interactive_editors():
    setup=[{'id':'files','op':'upload','files':[file('keep.flac',{},2),file('victim.flac',{},2)]}]
    cps=[cp('delete-cancel','Cancel deletion of the selected browser file.',['view 5','cd /workspace/inbox','/victim.flac',{'key':'D'},{'key':'n'}],[a('files','Cancel preserves both exchanged files.',files_check(['keep.flac','victim.flac']))]),
         cp('delete-confirm','Confirm deletion of the selected browser file.',['/victim.flac',{'key':'D'},{'key':'y'}],[a('files','Confirmation removes only the selected file.',files_check(['keep.flac']))],depends=['delete-cancel'])]
    out=[episode('browser-delete','browser',cps,setup)]
    cps=[cp('activate','Activate a selected named filter from its view.',['fset LocalOnly=artist="Aster"','view 6','/LocalOnly','win-toggle','win-activate','view 2'],[a('members','The selected filter changes the running library membership.',q('save -L -','paths',guard=['amber.flac','breeze.flac']))]),
         cp('replace','Edit the same named filter expression.',['fset LocalOnly=artist="Birch"','factivate LocalOnly'],[a('members','Replacing the definition applies the new predicate.',q('save -L -','paths',guard=['cobalt.flac','delta.flac']))],depends=['activate']),
         cp('delete-cancel','Cancel removal of the named filter.',['view 6','/LocalOnly',{'key':'D'},{'key':'n'},'factivate LocalOnly'],[a('members','The canceled deletion leaves the named filter usable.',q('save -L -','paths',guard=['cobalt.flac','delta.flac']))],depends=['replace']),
         cp('delete-confirm','Confirm deletion of the named filter.',['view 6','/LocalOnly',{'key':'D'},{'key':'y'},{'remote':'factivate LocalOnly','save':'reply'}],[a('removed','The deleted filter is no longer available by name.',captured('reply','error',guard=True))],depends=['delete-cancel'])]
    out.append(episode('filter-editor','filters',cps,media_setup(True)))
    cps=[cp('option-edit','Edit a numeric option through Settings.',['view 7','/scroll_offset','win-activate',{'key':'Control+U'},{'type':'set scroll_offset=9'},{'key':'Enter'}],[a('value','Settings activation and command editing change the active value.',setting_check('scroll_offset',guard='9'))]),
         cp('option-toggle','Toggle a selected boolean in Settings.',['set auto_reshuffle=true','view 7','/auto_reshuffle','win-toggle'],[a('value','Toggling the selected Settings row changes its option.',setting_check('auto_reshuffle',guard='false'))]),
         cp('binding-edit','Edit a selected custom binding through Settings.',['bind -f common X echo FirstBinding','view 7','/FirstBinding','win-activate',{'key':'Control+U'},{'type':'bind -f common X echo SecondBinding'},{'key':'Enter'}],[a('binding','Settings editing updates the selected binding command.',q('showbind common X',guard='bind common X echo SecondBinding'))]),
         cp('binding-delete-cancel','Cancel deleting the custom binding.',['view 7','/SecondBinding',{'key':'D'},{'key':'n'}],[a('binding','The canceled deletion preserves its binding.',q('showbind common X',guard='bind common X echo SecondBinding'))],depends=['binding-edit']),
         cp('binding-delete-confirm','Confirm deleting the custom binding.',['view 7','/SecondBinding',{'key':'D'},{'key':'y'}],[a('binding','The confirmed deletion removes the custom binding.',q('showbind common X',guard='No such binding'))],depends=['binding-delete-cancel'])]
    out.append(episode('settings-editor','settings',cps))
    return out


def completion():
    cases=[('command','pl-cre',' CompleteName',st('playlists','state-names'),['save -p']),
           ('option','set scroll_offs','13',setting_check('scroll_offset',guard='13'),[]),
           ('context','bind -f comm','X echo Completion',q('showbind common X',guard='bind common X echo Completion'),[]),
           ('filename','add -l /workspace/inbox/amb','',q('save -l -','paths',guard=['amber.flac']),[waitlist(1)]),
           ('spaced-file','add -q /workspace/inbox/kot','',q('save -q -','paths',guard=['koto space.flac']),[waitlist(1,'save -q -')])]
    cps=[]
    for name,prefix,suffix,check,after in cases:
        steps=[{'key':':'},{'type':prefix},{'key':'Tab'}]+([{'type':suffix}] if suffix else [])+[{'key':'Enter'}]+after
        cps.append(cp(name,'Complete the '+name+' prefix and execute it.',steps,[a('result','Tab completion produces an executable command with the intended target.',check)]))
    cps += [cp('erase-word','Delete the final console word and replace it.',[{'key':':'},{'type':'echo Alpha unwanted'},{'key':'Control+W'},{'type':'Beta'},{'key':'Enter'}],[a('text','Word deletion preserves earlier text and replaces the final word.',dict(source='screen',project='screen-has',texts=['Alpha Beta']))]),
            cp('cursor-edit','Insert into the numeric option value.',[{'key':':'},{'type':'set scroll_offset=3'},{'key':'Left'},{'type':'1'},{'key':'Enter'}],[a('value','Cursor editing inserts before the final character.',setting_check('scroll_offset',guard='13'))]),
            cp('backspace','Erase the last character before executing.',[{'key':':'},{'type':'set scroll_offset=57'},{'key':'Backspace'},{'key':'Enter'}],[a('value','Backspace deletes the preceding character.',setting_check('scroll_offset',guard='5'))])]
    return [episode('console-completion','console',cps,media_setup())]


def selection_cache():
    cps=[]
    for cmd,label,expected in [('win-add-q','append',['amber.flac','cobalt.flac']),('win-add-Q','prepend',['cobalt.flac','amber.flac'])]:
        for nomove in (False,True):
            cps.append(cp(label+('-stay' if nomove else '-advance'),'Copy the selected track with '+cmd+(' -n' if nomove else '')+'.',[cmd+(' -n' if nomove else ''),waitlist(2,'save -q -')],[a('queue','Append and prepend produce different ordered queues.',q('save -q -','paths',unordered=False,guard=expected)),a('selection','The -n flag controls whether selection advances.',q('echo {}','selected-in',names=['cobalt.flac' if nomove else 'delta.flac'],guard=True))],prepare=['view 2','set lib_sort=filename','unmark','/Cobalt','clear -q','add -q /workspace/inbox/amber.flac',waitlist(1,'save -q -')]))
    cps.append(cp('marked','Append a marked subset of library tracks.',['mark artist="Aster"','win-add-q -n',waitlist(2,'save -q -')],[a('subset','The marked set is copied rather than just its cursor track.',q('save -q -','paths',unordered=False,guard=['amber.flac','breeze.flac']))],prepare=['view 2','set lib_sort=filename','unmark','clear -q']))
    cps.append(cp('artist-group','Append all tracks of a selected library artist.',['view 1','//Aster','win-add-q -n',waitlist(2,'save -q -')],[a('group','Artist-level copying includes all tracks in the selected group.',q('save -q -','paths',guard=['amber.flac','breeze.flac']))],prepare=['clear -q','view 2','unmark']))
    out=[episode('selection-queue-copy','selection',cps,media_setup(True))]
    newa=file('amber.flac',{'artist':'Changed','title':'New Amber'},33,1800000000)
    newb=file('breeze.flac',{'artist':'Changed','title':'New Breeze'},44,1800000001)
    same=file('amber.flac',{'artist':'Hidden change','title':'Same Timestamp'},55,1704067200)
    cps=[cp('unchanged-mtime','Do not reload unchanged modification times.',[{'upload':same},'update-cache',{'wait':.2},{'play_paused':'/workspace/inbox/amber.flac'}],[a('cached','The old cache remains when file mtime is unchanged.',q('status','status',field='tag.title',guard='Amber'))]),
         cp('force-selected','Force refresh only the selected cache entry.',[{'upload':newa},{'upload':newb},'view 2','/Amber','win-update-cache -f',{'wait':.2},{'play_paused':'/workspace/inbox/amber.flac'}],[a('title','Selected cache update reads new metadata.',q('status','status',field='tag.title',guard='New Amber'))]),
         cp('other-cached','The other changed track remains cached until updated.',[{'play_paused':'/workspace/inbox/breeze.flac'}],[a('title','A selected-only update leaves the unselected cached entry alone.',q('status','status',field='tag.title',guard='Breeze'))],depends=['force-selected']),
         cp('update-view','Update changed files in the library view.',['view 2','win-update',{'wait':.2},{'play_paused':'/workspace/inbox/breeze.flac'}],[a('title','Window update reloads a file with changed mtime.',q('status','status',field='tag.title',guard='New Breeze'))],depends=['other-cached']),
         cp('removed-file','Remove a vanished track during library update.',['player-stop','view 5','cd /workspace/inbox','/breeze.flac',{'key':'D'},{'key':'y'},'view 2','win-update',waitlist(11)],[a('membership','A missing audio file is removed from the running library.',q('save -l -','paths',guard=sorted(x[0] for x in fixtures.TRACKS if x[0]!='breeze.flac')))],depends=['update-view'])]
    out.append(episode('selective-cache','metadata',cps,media_setup(True)))
    return out


def build():return named_io()+restart_effects()+paging()+interactive_editors()+completion()+selection_cache()+playback_endings()+extra_formats_sort()+native_information()+other_commands()+decoder_output()

def short_setup():
    files=[file('first.flac',{'artist':'Aster','album':'One','title':'First','tracknumber':'1'},4),file('second.flac',{'artist':'Aster','album':'One','title':'Second','tracknumber':'2'},4),file('third.flac',{'artist':'Birch','album':'Two','title':'Third','tracknumber':'1'},4)]
    return [{'id':'media','op':'upload','files':files},{'id':'library','op':'drive','steps':['add -l inbox',waitlist(3)]}]

def playback_endings():
    out=[]
    defaults=['player-stop','clear -q','filter','live-filter','set shuffle=off','set aaa_mode=all','set repeat=false','set repeat_current=false','set continue=true','set continue_album=true','set play_library=true','set play_sorted=true','set lib_sort=filename','set stop_after_queue=false','view 2']
    def start(title):return ['/'+title,'win-activate','player-pause-playback']
    cases=[('continue-on',[],'First',{'file':'/workspace/inbox/second.flac','status':'playing'}),
           ('continue-off',['set continue=false'],'First',{'file':'/workspace/inbox/second.flac','status':'stopped'}),
           ('repeat-off',[],'Third',{'status':'stopped','file':None}),
           ('repeat-on',['set repeat=true'],'Third',{'file':'/workspace/inbox/first.flac','status':'playing'}),
           ('album-stop',['set continue_album=false'],'Second',{'file':'/workspace/inbox/third.flac','status':'stopped'}),
           ('album-continue',[],'Second',{'file':'/workspace/inbox/third.flac','status':'playing'}),
           ('artist-scope',['set aaa_mode=artist'],'Second',{'status':'stopped','file':None}),
           ('album-scope',['set aaa_mode=album'],'Second',{'status':'stopped','file':None}),
           ('sorted-order',['set lib_sort=-filename'],'Second',{'file':'/workspace/inbox/first.flac','status':'playing'}),
           ('tree-order',['set lib_sort=-filename','set play_sorted=false'],'Second',{'file':'/workspace/inbox/third.flac','status':'playing'})]
    for name,options,title,expected in cases:
        out.append(episode('end-'+name,'playback',[cp('transition','Reach the end of '+title+' under '+name+'.',[{'boundary':{'expected':expected},'save':'transition'}],[a('transition','The track-end event follows the selected playback mode.',captured('transition','identity',guard=expected))],prepare=defaults+options+start(title))],short_setup()))
    out.append(episode('end-repeat-current','playback',[cp('loop','Repeat the current track at its end.',[{'boundary':{'loop':True},'save':'transition'}],[a('loop','The current file loops through its end instead of merely staying paused.',captured('transition','identity',guard={'looped':True}))],prepare=defaults+['set repeat_current=true']+start('First'))],short_setup()))
    for enabled in ('true','false'):
        expected={'status':'stopped'} if enabled=='true' else {'file':'/workspace/inbox/third.flac','status':'playing'}
        prep=defaults+['set stop_after_queue='+enabled]+start('Second')+['add -q /workspace/inbox/first.flac',waitlist(1,'save -q -'),'player-next','player-pause-playback']
        out.append(episode('end-queue-'+enabled,'playback',[cp('transition','Reach the end of the last queued track.',[{'boundary':{'expected':expected},'save':'transition'}],[a('transition','The empty-queue policy chooses stop or library continuation.',captured('transition','identity',guard=expected))],prepare=prep)],short_setup()))
    setup=short_setup();setup[1]['steps']+=['add -p /workspace/inbox/third.flac','add -p /workspace/inbox/first.flac',waitlist(2,'save -p -')]
    out.append(episode('end-playlist-source','playback',[cp('transition','Continue within the selected playlist at track end.',[{'boundary':{'expected':{'file':'/workspace/inbox/first.flac','status':'playing'}},'save':'transition'}],[a('next','Playlist source follows playlist order rather than library order.',captured('transition','identity',guard={'file':'/workspace/inbox/first.flac','status':'playing'}))],prepare=defaults+['view 3','win-next','win-top','win-activate','player-pause-playback','set play_library=false'])],setup))
    setup=media_setup(True)
    cps=[cp('queue-rand','Randomize a nonempty queue.',[{'random_order':{'command':'rand'},'save':'randomized'}],[a('permutation','Randomizing changes order while preserving every queue item.',captured('randomized','identity',guard=True))],prepare=['add -q inbox',waitlist(12,'save -q -')]),
         cp('reshuffle','Rebuild the shuffled playback order.',[{'random_order':{'command':'reshuffle'},'save':'randomized'}],[a('permutation','Reshuffle changes a complete shuffled traversal without losing tracks.',captured('randomized','identity',guard=True))],prepare=['clear -q','set aaa_mode=all','set repeat=true','set continue=true','set auto_reshuffle=false','set shuffle=tracks','set play_library=true'])]
    out.append(episode('random-order-effects','playback',cps,setup))
    return out


def extra_formats_sort():
    out=[]
    tagged=[('z-low.flac',{'artist':'Sort','title':'Low','media':'Vinyl','replaygain_track_gain':'-9.0 dB','replaygain_track_peak':'0.2','replaygain_album_gain':'-4.0 dB','replaygain_album_peak':'0.4'},60),('a-high.flac',{'artist':'Sort','title':'High','media':'CD','replaygain_track_gain':'3.0 dB','replaygain_track_peak':'0.9','replaygain_album_gain':'-1.0 dB','replaygain_album_peak':'1.1'},30),('m-mid.flac',{'artist':'Sort','title':'Mid','media':'Digital','replaygain_track_gain':'-2.0 dB','replaygain_track_peak':'0.5','replaygain_album_gain':'2.0 dB','replaygain_album_peak':'0.7'},120)]
    files=[file(n,t,d) for n,t,d in tagged]
    # Distinct encoded formats create conflicting bitrate/codec/profile keys.
    codecs=json.loads((Path(__file__).parent/'codecs.json').read_text())
    files += [{'filename':n,'base64':b} for n,b in codecs.items()]
    setup=[{'id':'media','op':'upload','files':files},{'id':'library','op':'drive','steps':['add -l inbox',waitlist(len(files))]}]
    cps=[]
    for name in ['bitrate','codec','codec_profile','media','rg_track_gain','rg_track_peak','rg_album_gain','rg_album_peak']:
        for reverse in ('','-'):
            cps.append(cp(name+('-desc' if reverse else '-asc'),'Sort by '+reverse+name+'.',['view 2','set lib_sort='+reverse+name,{'sort_keys':{'field':name,'count':len(files)},'save':'sort'}],[a('ordered','The sorted traversal has monotonic key groups; equal-key order is free.',captured('sort','sort-key-order',reverse=bool(reverse),field=name))]))
    out.append(episode('sort-media-properties','sorting',cps,setup))
    # Native multiple-argument format_print plus display-only layout grammar.
    setup=[{'id':'media','op':'upload','files':[file('format.flac',{'artist':'Format Artist','album':'Format Album','title':'Window Song','tracknumber':'7'},65),file('count.flac',{'artist':'Counter','title':'Count Me'},4),file('clipping.flac',{'artist':'A very long artist name that cannot fit beside the song in a forty column terminal','title':'Window Song'},65)]},{'id':'current','op':'drive','steps':[{'play_paused':'/workspace/inbox/format.flac'}]}]
    cps=[cp('multiple','Print several independent format arguments.',[],[a('lines','Each format argument produces a separate complete line.',q('format_print "[%a]" "[%t]" "[%02n]"',guard='[Format Artist]\n[Window Song]\n[07]'))]),
         cp('empty','Render an absent metadata field inside literals.',[],[a('field','Missing optional metadata leaves its surrounding text intact.',q('format_print "before[%{composer}]after"',guard='before[]after'))]),
         cp('play-count','Observe an incremented play counter after a track loops.',
            ['add -l /workspace/inbox/count.flac',waitlist(1),'view 2','win-top','set repeat_current=true','win-activate','player-pause-playback',{'boundary':{'loop':True}},'set repeat_current=false'],
            [a('count','A completed playback increments the native %X counter.',q('format_print "%X"',guard='1'))]),
         cp('play-count-sort','Sort tracks by their actual completed-play count.',
            ['add -l /workspace/inbox/format.flac',waitlist(2),'set lib_sort=play_count','view 2',{'order':2,'save':'ascending'},'set lib_sort=-play_count',{'order':2,'save':'descending'}],
            [a('ascending','Unplayed track precedes the completed track.',captured('ascending','identity',guard=['format.flac','count.flac'])),a('descending','Descending play counts reverse the two tracks.',captured('descending','identity',guard=['count.flac','format.flac']))],depends=['play-count']),
         cp('align-right','Render a right-aligned trailing duration.',
            ['player-stop','clear -l','add -l /workspace/inbox/format.flac',waitlist(1),'set format_playlist=%t%= %d','view 2'],
            [a('content','Right alignment puts the duration after the title while preserving both fields.',dict(source='screen',project='format-alignment',left='Window Song',right='01:05',guard=True))]),
         cp('priority','Render text with a clipping priority boundary.',
            ['clear -l','add -l /workspace/inbox/clipping.flac',waitlist(1),'set format_playlist=%a%! | %t%= %d',{'call':{'op':'resize','columns':40,'rows':20}}],
            [a('title','A priority boundary preserves the title when the artist must be clipped.',dict(source='screen',project='clipped-priority',title='Window Song',artist='A very long artist name that cannot fit beside the song in a forty column terminal',guard=True))]),
         cp('percent-width','Render a percentage-width field.',
            ['clear -l','add -l /workspace/inbox/format.flac',waitlist(1),'set format_playlist=[%50%a]',{'call':{'op':'resize','columns':100,'rows':30}}],
            [a('width','The field width is half of the available terminal width.',dict(source='screen',project='percentage-field',guard=True))]),
    ]
    out.append(episode('format-extra-grammar','format',cps,setup))
    return out

def gui_episodes():
    from gui import frontend,visual,console
    out=[]
    setup=media_setup();setup[0]['files'].append(base64file('duo.m3u','amber.flac\ncobalt.flac\n'))
    out.append(episode('gui-native-import','playlists',[frontend('import','Import /workspace/inbox/duo.m3u as a named playlist and display its tracks.',console('pl-import /workspace/inbox/duo.m3u')+[{'key':'3'},{'key':'G'}],q('save -p -','paths',guard=['amber.flac','cobalt.flac']),'The imported named playlist displays Amber and Cobalt.')],setup,gui=True))
    cps=[visual('page','Move the long sorted listing down by one page.',[{'key':'PageDown'}],'The listing advances by a page and later numbered tracks are visible.',prepare=['win-top']),frontend('last','Select Track-59 at the end of the library.',[{'key':'G'}],q('echo {}','selected-in',names=['page-59.flac'],guard=True),'Track-59 is visibly selected at the end of the list.'),visual('half','Move upward by half a page.',[{'key':'Control+U'}],'The selection and listing move upward by approximately half of the visible page.',depends=['last'])]
    out.append(episode('gui-paging','navigation',cps,long_setup(),gui=True))
    setup=[{'id':'media','op':'upload','files':[file('keep.flac',{'title':'Keep'},2),file('victim.flac',{'title':'Victim'},2)]},{'id':'browser','op':'drive','steps':['view 5','cd /workspace/inbox']}]
    out.append(episode('gui-browser-delete','browser',[frontend('delete','Delete victim.flac from the browser, confirming the deletion.',search('victim.flac')+[{'key':'D'},{'key':'y'}],files_check(['keep.flac']),'victim.flac disappears from the browser while keep.flac remains.')],setup,gui=True))
    setup=media_setup(True);setup.append({'id':'filter','op':'drive','steps':['fset LocalOnly=genre="Jazz"','view 6']})
    cps=[frontend('edit','Change LocalOnly to match genre Rock.',console('fset LocalOnly=genre="Rock"'),dict(source='screen',project='screen-has',texts=['LocalOnly','genre="Rock"']),'LocalOnly displays a Rock genre condition.'),frontend('apply','Activate LocalOnly and show the resulting library.',console('factivate LocalOnly')+[{'key':'2'}],q('save -L -','paths',guard=['cobalt.flac','delta.flac']),'The library contains only Cobalt and Delta under the active filter.',depends=['edit'])]
    out.append(episode('gui-filter-edit','filters',cps,setup,gui=True))
    cps=[frontend('number','Set scroll_offset to 9 and show its value in Settings.',[{'key':'7'}]+search('scroll_offset')+[{'key':'Enter'},{'key':'Control+U'},{'type':'set scroll_offset=9'},{'key':'Enter'}],setting_check('scroll_offset',guard='9'),'The Settings view shows scroll_offset with value 9.'),frontend('toggle','Turn auto_reshuffle off in Settings.',search('auto_reshuffle')+[{'key':'Space'}],setting_check('auto_reshuffle',guard='false'),'The Settings row shows auto_reshuffle disabled.',prepare=['set auto_reshuffle=true'])]
    out.append(episode('gui-settings-edit','settings',cps,gui=True))
    return out

def native_information():
    out=[episode('native-information','console',[
        cp('help','Request the native user-help message.',[],[a('manuals','The help command points to the product user manuals.',q('help',guard='To get started with cmus, read cmus-tutorial(7) and cmus(1) man pages'))]),
        cp('version','Request the in-application version.',[],[a('version','The version command returns the selected release.',q('version',guard='v2.13.0'))]),
    ])]
    files=[file('early.flac',{'artist':'Year Artist','album':'Range','title':'Early','date':'2001','tracknumber':'1'},60),file('late.flac',{'artist':'Year Artist','album':'Range','title':'Late','date':'2003','tracknumber':'2'},90)]
    setup=[{'id':'media','op':'upload','files':files},{'id':'library','op':'drive','steps':['add -l inbox',waitlist(2),'view 1']}]
    out.append(episode('album-format-aggregates','format',[
        cp('header','Display album aggregate fields.',['set format_heading_album=Album:%l Total:%{albumduration} Years:%y-%{maxdate}','//Year Artist'],[a('duration','Album duration aggregates its two decoded tracks.',dict(source='screen',project='screen-has',texts=['Total:02:30'])),a('range','The album date range uses both endpoint years.',dict(source='screen',project='screen-has',texts=['Years:2001-2003']))]),
        cp('seconds','Print paused position and duration in seconds.',[{'play_paused':'/workspace/inbox/late.flac'},'seek 30'],[a('values','The seconds-only fields expose numerical position and duration.',q('format_print "%{position_sec}|%{duration_sec}"',guard='30|90'))]),
    ],setup))
    codecs=json.loads((Path(__file__).parent/'codecs.json').read_text())
    setup=[{'id':'media','op':'upload','files':[{'filename':'sample.mp3','base64':codecs['sample.mp3']}]}]
    out.append(episode('format-current-bitrate','format',[cp('bitrate','Display a nonzero current compressed-audio bitrate.',
        ['set show_current_bitrate=true','player-play /workspace/inbox/sample.mp3',{'wait_positive':{'command':'format_print "%{bitrate}"'},'save':'bitrate'},'player-pause-playback'],
        [a('bitrate','Current MPEG playback reports a positive bitrate in kilobits per second.',captured('bitrate','identity',guard=True)),a('profile','The native codec profile identifies constant-bitrate encoding.',q('format_print "%{codec_profile}"',guard='CBR'))])],setup))
    return out

def other_commands():
    setup=media_setup(True)
    cps=[cp('write-alias','Save the library using the w command alias.',['w -l /workspace/outbox/alias.m3u'],[a('file','The native save alias writes the complete library.',fs('outbox/alias.m3u',paths=True,guard=sorted(x[0] for x in fixtures.TRACKS)))]),
         cp('push-binding','Prefill the console using a push key binding.',['bind -f common X push set repeat=',{'key':'X'},{'type':'true'},{'key':'Enter'}],[a('value','The pushed command is completed and executed.',setting_check('repeat',guard='true'))],prepare=['set repeat=false']),
         cp('quit-cancel','Cancel an interactive quit request.',terminal('quit -i')+[{'key':'n'}],[a('running','Canceling quit leaves the native command interface usable.',q('version',guard='v2.13.0'))]),
         cp('quit-confirm','Confirm interactive quitting after changing a setting.',['set repeat=true']+terminal('quit -i')+[{'key':'y'},{'wait_stopped':True}],[a('saved','Confirming quit saves the configured state.',st('autosave','state-line',prefix='set repeat=',guard='true'))]),
         cp('wq','Save and quit using wq.',['set repeat=false','wq',{'wait_stopped':True}],[a('saved','The wq alias saves its changed configuration.',st('autosave','state-line',prefix='set repeat=',guard='false'))]),
    ]
    out=[episode('native-command-aliases','console',cps,setup)]
    setup=media_setup()
    cps=[cp('enter','Activate a browser directory.',['view 5','cd /workspace','/inbox','win-activate'],[a('directory','Activation enters the selected directory.',q('pwd',guard='/workspace/inbox'))]),
         cp('up','Navigate to the browser parent.',['browser-up'],[a('directory','Browser-up returns to the parent of inbox.',q('pwd',guard='/workspace'))],depends=['enter']),
         cp('refresh-files','Refresh the browser after adding a new media file.',['view 5','cd /workspace/inbox',{'upload':file('new-file.flac',{'title':'New File'},2)},'win-update'],[a('visible','Browser update reveals the newly added audio file.',dict(source='screen',project='screen-has',texts=['new-file.flac']))]),
    ]
    out.append(episode('browser-navigation-update','browser',cps,setup))
    return out

def decoder_output():
    setup=[{'id':'media','op':'upload','files':[file('decoder.flac',{'artist':'Codec','title':'Decode'},2),file('fallback.flac',{'artist':'Fallback','title':'Fallback'},2)]}]
    cps=[cp('enabled','Decode a file with the ordinary input plugin.', ['add -l /workspace/inbox/decoder.flac',waitlist(1)],[a('file','The enabled decoder loads a real audio file.',q('save -l -','paths',guard=['decoder.flac']))]),
         cp('disabled','Disable both decoders for this file type.',['clear -l']+terminal('set input.flac.priority=0')+[{'key':'y'},'set input.ffmpeg.priority=0','add -l /workspace/inbox/fallback.flac',waitlist(0)], [a('file','Disabled decoders cannot import the audio file.',q('save -l -','paths',allow_empty=True,guard=[]))],depends=['enabled'],requires={'file':['decoder-priority/enabled/file']}),
         cp('fallback','Use the fallback decoder with the native FLAC plugin still disabled.',['set input.ffmpeg.priority=30','add -l /workspace/inbox/fallback.flac',waitlist(1)],[a('file','A remaining decoder can load the same input file.',q('save -l -','paths',guard=['fallback.flac']))],depends=['disabled']),
    ]
    out=[episode('decoder-priority','decoding',cps,setup)]
    cps=[cp('render','Render a complete track through the file output driver.',
        ['set output_plugin=ao','set dsp.ao.driver=wav','set dsp.ao.wav_dir=/workspace/outbox','set dsp.ao.wav_counter=7','set softvol=false','set continue=false','player-play /workspace/inbox/decoder.flac',{'wait_status':{'expected':{'status':'stopped'},'timeout':8}}],
        [a('audio','The file output contains the decoded complete PCM stream.',dict(source='workspace',request={'action':'read','path':'outbox/07.wav'},project='pcm-output',guard={'channels':2,'rate':8000,'width':2,'frames':16000,'samples_match':True})),a('counter','The output counter advances after a completed file.',setting_check('dsp.ao.wav_counter',nonempty=True))])]
    signal_file={'filename':'decoder.flac','base64':base64.b64encode(fixtures.flac({'artist':'Codec','title':'Decode'},2,pattern=(1000,-500,2000,-1500))).decode()}
    out.append(episode('audio-file-output','playback',cps,[{'id':'media','op':'upload','files':[signal_file]}]))
    return out
