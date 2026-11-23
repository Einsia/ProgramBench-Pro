"""Broad native-command episodes. Each point represents a distinct observable rule."""
import base64
import itertools
import json
import re
from specification import a,cp,episode,q,captured,st,fs,media_setup
import fixtures


def split(wid,feature,cps,setup=(),size=32):
    return [episode(f'{wid}-{i//size+1:02d}',feature,cps[i:i+size],setup) for i in range(0,len(cps),size)]
def mutation(cmd,name='reply'):return {'remote':cmd,'save':name}
def setting_check(name,**kw):return q('set '+name+'?',project='setting',**kw)
def quote(s):return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'

BOOLS=['auto_expand_albums_follow','auto_expand_albums_search','auto_expand_albums_selcur','auto_hide_playlists_panel','auto_mark_selected_playlist','auto_reshuffle','block_key_paste','confirm_run','continue','continue_album','display_artist_sort_name','follow','ignore_duplicates','mouse','pause_on_output_change','play_library','play_sorted','repeat','repeat_current','replaygain_limit','resume','search_resets_position','show_all_tracks','show_hidden','show_current_bitrate','show_playback_position','show_remaining_time','skip_track_info','smart_artist_sort','sort_albums_by_name','stop_after_queue','time_show_leading_zero','wrap_search']
ENUMS={'aaa_mode':['all','artist','album'],'shuffle':['off','tracks','albums'],'replaygain':['disabled','track','album','track-preferred','album-preferred','smart'],'start_view':['tree','sorted','playlist','queue','browser','filters','settings'],'progress_bar':['disabled','line','shuttle','color','color_shuttle']}
NUMERIC={'buffer_seconds':(1,300,25),'rewind_offset':(-1,9999,11),'scroll_offset':(0,9999,5),'tree_width_percent':(1,100,48),'tree_width_max':(0,9999,65)}
FORMAT_OPTS=['altformat_current','altformat_playlist','altformat_title','altformat_trackwin','format_current','format_heading_album','format_heading_artist','format_heading_playlist','format_playlist','format_playlist_va','format_statusline','format_title','format_trackwin','format_trackwin_album','format_trackwin_va','format_treewin','format_treewin_artist']
COLOR_OPTS=['color_cmdline_bg','color_cmdline_fg','color_error','color_info','color_separator','color_statusline_bg','color_statusline_fg','color_statusline_progress_bg','color_statusline_progress_fg','color_titleline_bg','color_titleline_fg','color_win_bg','color_win_cur','color_win_cur_sel_bg','color_win_cur_sel_fg','color_win_dir','color_win_fg','color_win_inactive_cur_sel_bg','color_win_inactive_cur_sel_fg','color_win_inactive_sel_bg','color_win_inactive_sel_fg','color_win_sel_bg','color_win_sel_fg','color_win_title_bg','color_win_title_fg','color_trackwin_album_bg','color_trackwin_album_fg']
ATTR_OPTS=['color_cmdline_attr','color_cur_sel_attr','color_statusline_attr','color_statusline_progress_attr','color_titleline_attr','color_win_cur_attr','color_win_attr','color_win_cur_sel_attr','color_win_inactive_cur_sel_attr','color_win_inactive_sel_attr','color_win_sel_attr','color_win_title_attr','color_trackwin_album_attr']


def settings():
    out=[];cps=[]
    for name in BOOLS:
        for val in ('true','false'):
            cps.append(cp(name+'-'+val,'Set '+name+' to '+val+'.',['set '+name+'='+val],[a('value','The option reports the requested boolean value.',setting_check(name,guard=val))],prepare=['set '+name+'='+('false' if val=='true' else 'true')]))
        cps.append(cp(name+'-toggle','Toggle '+name+' from false.',['toggle '+name],[a('value','The boolean toggle changes false to true.',setting_check(name,guard='true'))],prepare=['set '+name+'=false']))
    out+=split('booleans','settings',cps)
    cps=[]
    for name,values in ENUMS.items():
        for i,value in enumerate(values):
            cps.append(cp(name+'-'+str(i),'Assign '+value+' to '+name+'.',['set '+name+'='+value],[a('value','The enumerated setting is accepted and returned.',setting_check(name,guard=value))],prepare=['set '+name+'='+values[(i+1)%len(values)]]))
            if name in ('aaa_mode','shuffle','replaygain'):
                cps.append(cp(name+'-cycle-'+str(i),'Cycle '+name+' from '+value+'.',['toggle '+name],[a('value','Cycling reaches the next documented value.',setting_check(name,guard=values[(i+1)%len(values)]))],prepare=['set '+name+'='+value]))
        cps.append(cp(name+'-invalid','Reject an unsupported '+name+' value.',[mutation('set '+name+'=not-a-value')],[a('error','An invalid enumeration is rejected with feedback.',captured('reply','error',guard=True)),a('preserved','The previously accepted enum value is preserved.',setting_check(name,guard=values[-1]))],prepare=['set '+name+'='+values[-1]]))
    out+=split('enums','settings',cps)
    cps=[]
    for name,(lo,hi,middle) in NUMERIC.items():
        for label,value in [('minimum',lo),('maximum',hi),('middle',middle)]:
            cps.append(cp(name+'-'+label,'Set '+name+' at its '+label+'.',['set '+name+'='+str(value)],[a('value','The numeric value is retained.',setting_check(name,guard=str(value)))],prepare=['set '+name+'='+str(middle if value!=middle else lo)]))
        for label,value in [('below',str(lo-1)),('above',str(hi+1)),('text','oops'),('fraction','1.25')]:
            cps.append(cp(name+'-'+label,'Reject '+label+' input for '+name+'.',[mutation('set '+name+'='+value)],[a('preserved','Invalid input preserves the valid value and reports an error.',captured('reply','error',guard=True)),a('value','The prior accepted number remains set.',setting_check(name,guard=str(middle)))],prepare=['set '+name+'='+str(middle)]))
    out+=split('numeric','settings',cps)
    cps=[]
    for name in FORMAT_OPTS:
        cps.append(cp(name,'Configure '+name+' to include title and filename.',['set '+name+'=[%t] %F'],[a('value','This format slot stores the complete format expression.',setting_check(name,guard='[%t] %F'))]))
    for name in COLOR_OPTS:
        cps.append(cp(name,'Set '+name+' to an indexed terminal color.',['set '+name+'=123'],[a('value','This color role accepts a 256-color index.',setting_check(name,guard='123'))]))
    for name in ATTR_OPTS:
        cps.append(cp(name,'Set '+name+' to bold and underline.',['set '+name+'=bold|underline'],[a('value','The attribute role retains both selected attributes.',setting_check(name,nonempty=True))]))
    for name,val in [('format_clipped_text','[...]'),('id3_default_charset','UTF-8'),('icecast_default_charset','UTF-8'),('lib_sort','title -date'),('pl_sort','-duration title'),('pl_env_vars','DATA_DIR,HOME'),('replaygain_preamp','4.5')]:
        cps.append(cp(name,'Change '+name+' and query it.',['set '+name+'='+val],[a('value','The setting stores the specified textual or numeric value.',setting_check(name,nonempty=True))]))
    out+=split('display-settings','settings',cps)
    # Independent defaults are inspected in a new process; never count undefined/empty option values.
    defaults=BOOLS+list(ENUMS)+list(NUMERIC)+COLOR_OPTS+ATTR_OPTS
    out+=split('defaults','settings',[cp(name,'Read the initial '+name+' setting.',[],[a('default','The documented initial value is reported.',setting_check(name,nonempty=True))]) for name in defaults])
    # Query active options after process replacement; a saved text file alone does not prove restoration.
    saved={**{x:'true' for x in ['repeat','repeat_current','play_sorted','follow','show_hidden','sort_albums_by_name','auto_hide_playlists_panel','show_remaining_time']},**{x:'false' for x in ['continue','wrap_search','auto_reshuffle','search_resets_position']},'shuffle':'albums','aaa_mode':'artist','replaygain':'track','scroll_offset':'5','tree_width_percent':'48','tree_width_max':'65','rewind_offset':'11','format_playlist':'%t | %a','format_clipped_text':'...','lib_sort':'title -date','pl_sort':'-duration title'}
    checks=[a(name,'The saved '+name+' option is active after process replacement.',setting_check(name,guard=saved[name])) for name in saved]
    out.append(episode('settings-persistence','persistence',[cp('restart','Save configured settings and restart.',['set '+k+'='+v for k,v in saved.items()]+[{'restart':True}],checks)]))
    return out


def filters():
    tests=[]
    strings={'artist':['Aster','Birch','Étoile','*ar*'],'albumartist':['Aster','Various Artists','*Dun*'],'album':['Dawn','Night','*iv*'],'title':['Amber','Echo','*e*','光'],'genre':['Jazz','Rock','*o*'],'comment':['warm piano','*live*','*studio*'],'filename':['*amber.flac','*koto*'],'codec':['flac'],'media':['Vinyl']}
    for field,patterns in strings.items():
        for j,pattern in enumerate(patterns):
            for comp in ('=','!='):
                if field=='codec' and comp=='!=':continue
                tests.append((f'{field}-{j}-'+('eq' if comp=='=' else 'ne'),field+comp+quote(pattern)))
    for field,pivot in [('discnumber',1),('tracknumber',2),('date',2005),('originaldate',2000),('duration',180),('bpm',90)]:
        for name,operator in [('lt','<'),('le','<='),('eq','='),('ne','!='),('ge','>='),('gt','>')]:tests.append((field+'-'+name,field+operator+str(pivot)))
    tests += [('tagged','tag'),('untagged','!tag')]
    for short,value in [('a','Aster'),('A','Various'),('l','Night'),('t','Echo'),('g','Jazz'),('c','live'),('f','koto')]:
        tests += [('short-'+short,'~'+short+' '+value),('short-not-'+short,'!~'+short+' '+value)]
    for short,value in [('D',1),('n',2),('y',2005),('d',180)]:
        for suffix,expression in [('less','<'+str(value)),('more','>'+str(value)),('range',str(value)+'-'+str(value+3)),('exact',str(value))]:tests.append(('short-'+short+'-'+suffix,'~'+short+expression))
    tests += [('and','artist="Aster"&title="Amber"'),('or','genre="Rock"|genre="Folk"'),('not-group','!(genre="Jazz"|genre="Rock")'),('precedence','artist="Aster"|artist="Birch"&duration>150'),('grouped','artist="Aster"|(artist="Birch"&duration>150)'),('nested','((date>=2000&duration<200)|genre="Classical")&tag'),('short-and','~g Rock ~d>100'),('short-or','~a Aster | ~a Cedar'),('short-group','(~a Aster | ~a Birch) !~d<100'),('glob-prefix','title="B*"'),('glob-suffix','title="*a"'),('glob-one-char','title="?mber"'),('glob-uppercase','artist="ASTER"'),('glob-lowercase','artist="aster"')]
    # The media filter is given positive matching fixtures, while all other filters use a varied corpus.
    data=media_setup(True)
    rich=base64.b64encode(fixtures.flac(fixtures.RICH,360)).decode()
    data[0]['files'].append({'filename':'rich.flac','base64':rich})
    data[0]['files'].append({'filename':'wave.wav','base64':base64.b64encode(fixtures.wav()).decode()})
    data[1]['steps'][-1]['wait_list']['count']=14
    cps=[]
    for name,expression in tests:
        cps.append(cp(name,'Filter the library with '+expression+'.',['filter '+expression],[a('membership','The visible library membership follows this filter expression.',q('save -L -','paths',allow_empty=True))],prepare=['filter','live-filter','factivate']))
    out=split('filter-expression','filters',cps,data)
    # Named filters, negation, combinations and replacement use the same user-visible filter manager.
    named=[('single',['fset jazz=genre="Jazz"','factivate jazz']),('negated',['fset jazz=genre="Jazz"','factivate !jazz']),('combine',['fset recent=date>=2000','fset short=duration<200','factivate recent short']),('replace',['fset selected=artist="Aster"','fset selected=artist="Birch"','factivate selected']),('defined-reference',['fset jazz=genre="Jazz"','filter jazz|genre="Folk"'])]
    out+=split('named-filters','filters',[cp(n,'Apply the named filter operation '+n+'.',steps,[a('membership','Named filter activation selects the expected tracks.',q('save -L -','paths',allow_empty=True))],prepare=['filter','live-filter','factivate']) for n,steps in named],media_setup(True))
    live=['Aster','Night','Rock','Echo','Aster Dawn','Birch Night','暖','光','étoile','Jade','live','Various','~g Jazz','~d>200','~a Aster ~d>150']
    out+=split('live-filters','filters',[cp('live-'+str(i),'Apply live filter '+term+'.',['live-filter '+term],[a('membership','The live-filter result is visible in the native filtered export.',dict(source='visible',project='members'))],prepare=['view 2','filter','live-filter','factivate'],requires={'membership':['live-filters-01/live-0/membership']} if i in (2,6,10) else None) for i,term in enumerate(live)],media_setup(True))
    return out


def build():
    return settings()+filters()+formats()+metadata()+sorting()+playlists()+controls()+bindings()+errors()+extended()+additional()

def rich_setup():
    return [{'id':'media','op':'upload','files':[{'filename':'rich.flac','base64':base64.b64encode(fixtures.flac(fixtures.RICH,360)).decode()}]},
            {'id':'current','op':'drive','steps':[{'play_paused':'/workspace/inbox/rich.flac'}]}]


def formats():
    fields=['artist','albumartist','album','discnumber','totaldiscs','tracknumber','title','genre','comment','date','duration','filename','path','originaldate','bpm','codec','rg_track_gain','rg_track_peak','rg_album_gain','rg_album_peak','arranger','composer','conductor','lyricist','performer','remixer','label','publisher','work','opus','partnumber','part','subtitle','media']
    shorts={'a':'artist','A':'albumartist','l':'album','D':'discnumber','T':'totaldiscs','n':'tracknumber','t':'title','g':'genre','c':'comment','y':'date','d':'duration','f':'path','F':'filename'}
    expressions=[]
    for f in fields:expressions.append(('long-'+f,'%{'+f+'}'))
    for ch,f in shorts.items():expressions.append(('short-'+ch,'%'+ch))
    for f in ('artist','album','title','genre','comment','filename','composer','media'):
        for label,modifier in [('right','30'),('left','-30'),('clip','5')]:expressions.append((f+'-'+label,'%'+modifier+'{'+f+'}'))
    for f in ('discnumber','totaldiscs','tracknumber','date','bpm'):
        for label,modifier in [('right','6'),('left','-6'),('zero','06')]:
            if f=='bpm' and label=='zero':continue
            expressions.append((f+'-'+label,'%'+modifier+'{'+f+'}'))
    expressions += [('literal-percent','100%%'),('literal-question','What%?'),('unicode-literal','曲: %t'),('multiple','%a | %l | %02n | %t | %d'),('gain-precision','%{rg_track_gain} dB'),('duration-leading','%d')]
    cps=[cp(name,'Render the native format expression '+expr+'.',[],[a('render','The format expression renders metadata, formatting or literals correctly.',q('format_print '+quote('['+expr+']'),nonempty=True))]) for name,expr in expressions]
    for c in cps:
        if c['id']=='duration-leading':
            c['steps']=['set time_show_leading_zero=false']
            c['goal']='Render duration without a leading zero.'
            c['checks'][0]['check']['guard']='[6:00]'
    out=split('format-fields','format',cps,rich_setup())
    cond=[]
    for f,val in [('artist','Aurora Ensemble'),('albumartist','Aurora Collective'),('album','Glass Maps'),('title','North Window'),('genre','Chamber'),('media','Vinyl'),('codec','flac')]:
        cond.extend([(f+'-equal',f+'='+quote(val)),(f+'-not',f+'!='+quote(val)),(f+'-glob',f+'='+quote('*'+val.split()[0]+'*'))])
    for f,n in [('discnumber',2),('tracknumber',7),('date',2016),('originaldate',1991),('bpm',123)]:
        for label,op in [('lt','<'),('le','<='),('eq','='),('ge','>='),('gt','>'),('ne','!=')]:
            cond.append((f+'-'+label,[f+op+str(n+offset) for offset in (-1,0,1)]))
    cond += [('same-key','artist=artist'),('different-key','artist=albumartist'),('not-key','artist!=albumartist'),('and','tracknumber=7&date>2000'),('or','tracknumber=0|date>2000'),('group','(tracknumber=0|date>2000)&discnumber=2'),('negate','!(discnumber=2)'),('local','!stream'),('not-compilation','!va')]
    cps=[cp(n,'Render conditional formats using '+str(expr)+'.',[],[a('branch','The expression selects the correct conditional branch.',q('format_print '+' '.join(quote('%{?'+part+'?MATCH?OTHER}') for part in (expr if isinstance(expr,list) else [expr])),nonempty=True))]) for n,expr in cond]
    for option in ('repeat','continue','shuffle','play_library','play_sorted','show_remaining_time'):
        value='tracks' if option=='shuffle' else 'true';opposite='off' if option=='shuffle' else 'false'
        for val in (value,opposite):
            cps.append(cp('setting-'+option+'-'+val,'Render a condition depending on '+option+'.',['set '+option+'='+val],[a('branch','Formatting condition reflects the current option.',q('format_print '+quote('%{?'+option+'?ON?OFF}'),nonempty=True))]))
    cps += [cp('omitted-else','Render a conditional without its else part.',[],[a('render','An omitted else part produces the native conditional result.',q('format_print '+quote('[%{?tracknumber=0?YES}]'),nonempty=True))]),cp('nested','Render a nested condition.',[],[a('render','Nested conditionals resolve the inner expression.',q('format_print '+quote('%{?discnumber=2?%{?tracknumber=7?INNER?OTHER}?OUTER}'),nonempty=True))])]
    out+=split('format-conditions','format',cps,rich_setup())
    return out


def metadata():
    out=[]
    # Each native metadata key is asserted once with a populated rich fixture.
    fields=[x for x in fixtures.RICH if x not in ('disctotal','tracktotal','partnumber','part')]
    checks=[a(k,'Native status exposes the '+k+' metadata.',q('status','status',field='tag.'+k,nonempty=True)) for k in fields]
    checks += [a('duration','The decoded track duration is in seconds.',q('status','status',field='duration',number=True,guard=360.0)),a('file','The current file identifies the loaded track.',q('status','status',field='file',guard='rich.flac')),a('state','The controlled playback state is paused.',q('status','status',field='status',guard='paused'))]
    out.append(episode('metadata-rich','metadata',[cp('status','Inspect the current track metadata.',[],checks)],rich_setup()))
    cps=[]
    for name,fields in [('jade.flac',['artist','album','title','genre','comment','date','originaldate','tracknumber','discnumber']),('koto space.flac',['artist','album','title','comment']),('horizon.flac',['artist','albumartist','compilation'])]:
        cps.append(cp(name.replace('.','-').replace(' ','-'),'Load and pause '+name+'.',[{'play_paused':'/workspace/inbox/'+name}],[a(f,'The tagged '+f+' value is preserved for '+name+'.',q('status','status',field='tag.'+f,nonempty=True)) for f in fields]))
    cps.append(cp('no-tags','Load an untagged file.',[{'play_paused':'/workspace/inbox/untagged.flac'}],[a('duration','An untagged audio file still has its decoded duration.',q('status','status',field='duration',number=True,guard=45.0)),a('title-absent','No title tag is fabricated for the untagged audio.',q('status','missing-tag',field='tag.title',guard=True)),a('filename','The file remains identifiable without metadata.',q('format_print '+quote('%F'),nonempty=True))]))
    out+=split('metadata-variants','metadata',cps,media_setup())
    # Distinct tag encodings and missing-field behavior, independently generated rather than copied from cmus.
    variants=[('empty-title',{'artist':'Aster','title':''}),('unicode-composed',{'artist':'Café','title':'Étude'}),('unicode-decomposed',{'artist':'Cafe\u0301','title':'E\u0301tude'}),('symbols',{'artist':'A&B','title':'<North> "Window"'}),('track-slash',{'artist':'Aster','tracknumber':'12/18','discnumber':'2/4'}),('leading-zero',{'artist':'Aster','tracknumber':'003','discnumber':'01'}),('full-date',{'artist':'Aster','date':'2002-03-04','originaldate':'1990-12-31'}),('compilation-va',{'artist':'Various','album':'Sampler','title':'One'}),('albumartist-override',{'artist':'Soloist','albumartist':'Ensemble','album':'Concert','title':'Movement'})]
    for i,(label,tags) in enumerate(variants):
        file={'filename':label+'.flac','base64':base64.b64encode(fixtures.flac(tags,30)).decode()}
        read=[a('artist','The artist tag remains observable.',q('status','status',field='tag.artist',nonempty=True)),a('formatted','The native formatted tag summary distinguishes this encoding.',q('format_print '+quote('[%a|%A|%t|%n|%D|%y|%{originaldate}]'),nonempty=True))]
        cps2=[cp('read','Read the '+label+' metadata.',['player-play /workspace/inbox/'+file['filename'],'player-pause-playback'],read)]
        out.append(episode('metadata-'+label,'metadata',cps2,[{'id':'media','op':'upload','files':[file]}]))
    return out


def sorting():
    def prepared(load=False):
        setup=media_setup(load)
        for i,f in enumerate(setup[0]['files']):f['mtime']=1704067200+((i*5+7)%12)*60
        return setup
    fields=['artist','albumartist','album','title','tracknumber','discnumber','date','originaldate','duration','genre','comment','filename','filemtime','bpm']
    names=[x[0] for x in fixtures.TRACKS]
    def keymap(key):
        out={}
        for i,(name,tags,duration) in enumerate(fixtures.TRACKS):
            v=name if key=='filename' else duration if key=='duration' else ((i*5+7)%12) if key=='filemtime' else tags.get(key,'')
            if key=='albumartist':v=tags.get('albumartist',tags.get('artist',''))
            out[name]=str(v)
        return out
    cps=[]
    for field in fields:
        for reverse in ('','-'):
            expr=reverse+field
            cps.append(cp(field+('-descending' if reverse else '-ascending'),'Sort the library by '+expr+'.',['set lib_sort='+expr,'view 2',{'order':len(names),'save':'order'}],[a('order','Distinct key groups appear in the requested order; ties are free.',captured('order','ordered',ties=keymap(field)))]))
    for i,expression in enumerate(['artist -duration','genre title','-date -tracknumber','album discnumber tracknumber','albumartist album title','-artist duration','genre -date title','discnumber -tracknumber','originaldate date title','title filename']):
        cps.append(cp('compound-'+str(i),'Use the compound sort '+expression+'.',['set lib_sort='+expression,'view 2',{'order':len(names),'save':'order'}],[a('order','Compound sorting follows the ordered key list.',captured('order','ordered',ties={name:[keymap(k.lstrip('-'))[name] for k in expression.split()] for name in names}))]))
    out=split('library-sort','sorting',cps,prepared(True))
    setup=prepared();setup += [{'id':'playlist','op':'drive','steps':['pl-create Sorting','view 3','win-top','win-toggle','add -p inbox',{'wait_list':{'command':'save -p -','count':12}}]}]
    cps=[]
    for field in fields:
        for rev in ('','-'):
            cps.append(cp(field+('-desc' if rev else '-asc'),'Sort the selected playlist by '+rev+field+'.',['set pl_sort='+rev+field],[a('order','The exported playlist follows this sort, ignoring same-key order.',q('save -p -','paths',unordered=False,ties=keymap(field)))]))
    out+=split('playlist-sort','sorting',cps,setup)
    return out

def base64file(name,text):return {'filename':name,'base64':base64.b64encode(text.encode()).decode()}

def playlists():
    out=[];names=[x[0] for x in fixtures.TRACKS];three=['amber.flac','cobalt.flac','echo.flac']
    forms={
        'plain':'\n'.join('/workspace/inbox/'+x for x in three)+'\n',
        'm3u':'#EXTM3U\n#EXTINF:181,Aster - Amber\n'+''.join('/workspace/inbox/'+x+'\n' for x in three),
        'relative':'../inbox/amber.flac\n../inbox/cobalt.flac\n../inbox/echo.flac\n',
        'crlf':'#EXTM3U\r\n'+''.join('/workspace/inbox/'+x+'\r\n' for x in three),
        'pls':'[playlist]\nNumberOfEntries=3\n'+''.join('File%d=/workspace/inbox/%s\nTitle%d=Label %d\nLength%d=-1\n'%(i+1,x,i+1,i+1,i+1) for i,x in enumerate(three))+'Version=2\n',
        'duplicates':'/workspace/inbox/amber.flac\n/workspace/inbox/amber.flac\n/workspace/inbox/echo.flac\n',
        'comments':'# comment\n\n/workspace/inbox/cobalt.flac\n# ignored\n/workspace/inbox/amber.flac\n',
        'unicode':'/workspace/inbox/jade.flac\n/workspace/inbox/koto space.flac\n',
        'missing':'/workspace/inbox/no-such.flac\n/workspace/inbox/echo.flac\n',
    }
    cps=[]
    for label,text in forms.items():
        ext='.pls' if label=='pls' else '.m3u'
        file=base64file(label+ext,text)
        # File contents use the actual directory available through the public upload alias.
        for target,flag,dump in [('library','-l','save -l -'),('queue','-q','save -q -'),('playlist','-p','save -p -')]:
            expected_count=1 if label=='missing' else 2 if label in ('comments','unicode') or (label=='duplicates' and target=='library') else 3
            steps=['clear '+flag,{'upload':file},'add '+flag+' /workspace/inbox/'+file['filename'],{'wait_list':{'command':dump,'count':expected_count}}]
            prep=['view 3','win-top','win-toggle'] if target=='playlist' else []
            cps.append(cp(label+'-'+target,'Import '+label+' playlist into '+target+'.',steps,[a('entries','The playlist format resolves entries, duplicates and filenames as cmus does.',q(dump,'paths',unordered=target=='library'))],prepare=prep))
    # A playlist collection exists for playlist-target imports; each checkpoint prepares independently.
    setup=media_setup();setup.append({'id':'lists','op':'drive','steps':['pl-create Imports','view 3','win-top','win-toggle']})
    out+=split('playlist-import','playlists',cps,setup)
    # Selection and marked playlist are different native concepts; tests make the distinction observable.
    cps=[
      cp('create','Create two named playlists.',['pl-create Alpha','pl-create Beta','view 3','save -p'],[a('names','Both named playlists appear in the saved playlist directory.',st('playlists','state-names'))]),
      cp('mark-alpha','Mark Alpha, then add tracks to it.',['win-top','win-down','win-toggle','add -p /workspace/inbox/amber.flac','add -p /workspace/inbox/cobalt.flac',{'wait_list':{'command':'save -p -','count':2}}],[a('entries','The selected named playlist contains the added tracks.',q('save -p -','paths',unordered=False))],depends=['create']),
      cp('rename','Rename the selected playlist.',['pl-rename Amber favorites','save -p'],[a('names','The renamed playlist replaces its prior name.',st('playlists','state-names'))],depends=['mark-alpha']),
      cp('restart','Restart with named playlists intact.',[{'restart':True}],[a('names','Named playlist files persist.',st('playlists','state-names'))],depends=['rename']),
      cp('delete','Delete one named playlist.',['pl-delete Beta'],[a('names','Deleting a playlist preserves the other playlists.',st('playlists','state-names'))],depends=['restart']),
    ]
    out.append(episode('playlist-management','playlists',cps,media_setup()))
    cps=[]
    for target,flag,dump in [('library','-l','save -l -'),('queue','-q','save -q -')]:
        for label,n in [('single',1),('several',3)]:
            file='export-'+target+'-'+label+'.m3u'
            steps=['clear '+flag]+['add '+flag+' /workspace/inbox/'+x for x in three[:n]]+[{'wait_list':{'command':dump,'count':n}},'save '+flag+' /workspace/outbox/'+file]
            cps.append(cp(target+'-'+label,'Save '+target+' to a public output file.',steps,[a('file','The written playlist contains the intended media paths.',fs('/workspace/outbox/'+file,paths=True,unordered=target=='library'))]))
            if target=='library':
                cps.append(cp(target+'-'+label+'-reload','Reload the exported library playlist.',['clear -l','load -l /workspace/outbox/'+file,{'wait_list':{'count':n}}],[a('entries','Loading the exported file restores its library membership.',q('save -l -','paths'))],depends=[target+'-'+label]))
    out+=split('playlist-roundtrip','playlists',cps,media_setup())
    # Marking, moving and copying all use visible selections, then inspect native exports.
    edit_setup=media_setup();edit_setup.append({'id':'lists','op':'drive','steps':['pl-create Editing','view 3','win-top','win-toggle']})
    edits=[('remove-selected',['win-top','win-down','win-remove']),('move-down',['win-top','win-mv-after']),('move-up',['win-bottom','win-mv-before']),('remove-marked',['win-top','win-toggle','win-down','win-toggle','win-remove']),('invert-marks',['mark artist="Aster"','invert','win-remove']),('unmark',['mark artist="Aster"','unmark','win-top','win-remove']),('move-marked-after',['mark artist="Aster"','win-bottom','win-mv-after']),('move-marked-before',['mark artist="Aster"','win-bottom','win-mv-before'])]
    for target,flag,dump in [('queue','-q','save -q -'),('playlist','-p','save -p -')]:
        for label,ops in edits:
            prep=['set pl_sort=','view '+('4' if target=='queue' else '3'),'clear '+flag]+['add '+flag+' /workspace/inbox/'+n for n in names[:6]]+[{'wait_list':{'command':dump,'count':6}},'unmark']+(['win-next'] if target=='playlist' else [])
            out.append(episode('edit-'+target+'-'+label,'editing',[cp('edit','Perform '+label+' in the '+target+'.',ops,[a('sequence','The remaining sequence records the requested edit.',q(dump,'paths',unordered=False))],prepare=prep)],edit_setup))
    # Copy filters select real subsets, not blank/default state.
    for target,flag,dump in [('library','-l','save -l -'),('playlist','-p','save -p -')]:
        for expr,label in [('artist="Aster"','artist'),('genre="Rock"','genre'),('duration>200','duration'),('!tag','untagged')]:
            prep=['view 4','clear -q']+['add -q /workspace/inbox/'+n for n in names]+[{'wait_list':{'command':'save -q -','count':12}},'unmark','mark '+expr]
            # Copying from queue to queue creates additional items, which is a distinct append behavior.
            cmd={'library':'win-add-l -n','playlist':'win-add-p -n','queue':'win-add-q -n'}[target]
            out.append(episode('copy-marked-'+target+'-'+label,'selection',[cp('copy','Copy the marked '+label+' subset into '+target+'.',[cmd],[a('entries','The destination contains the tracks selected by the mark expression.',q(dump,'paths',unordered=target=='library'))],prepare=prep)],edit_setup))
    return out


def controls():
    out=[];cps=[]
    for value in ['0','100','37','250','-250','+10%','-10%','33%','150%','-150%','25 80','+5% -10%','-3 +8','0 100','100 0']:
        cps.append(cp('volume-'+str(len(cps)),'Apply volume '+value+'.',['vol '+value],[a('left','The left channel follows absolute, relative and clamped volume rules.',q('status','status',field='set.vol_left')),a('right','The right channel independently follows the second volume argument.',q('status','status',field='set.vol_right'))],prepare=['set softvol=true','vol 40 60']))
    cps += [cp('mute','Mute a known software volume.',['mute'],[a('left','Mute silences the left channel.',q('status','status',field='set.vol_left',guard='0')),a('right','Mute silences the right channel.',q('status','status',field='set.vol_right',guard='0'))],prepare=['set softvol=true','vol 35 65']),cp('unmute','Restore volume after muting.',['mute','mute'],[a('left','Unmute restores the left channel.',q('status','status',field='set.vol_left',guard='35')),a('right','Unmute restores the right channel.',q('status','status',field='set.vol_right',guard='65'))],prepare=['vol 35 65'])]
    out+=split('volume','playback',cps)
    cps=[]
    for label,commands,expected in [('play',['player-play'],'playing'),('pause',['player-play','player-pause-playback'],'paused'),('toggle-pause',['player-pause'],'playing'),('toggle-again',['player-pause','player-pause'],'paused'),('stop',['player-stop'],'stopped')]:
        cps.append(cp(label,'Put the player into '+expected+' state.',commands,[a('state','The player reports the requested state.',q('status','status',field='status',guard=expected))],prepare=[{'play_paused':'/workspace/inbox/amber.flac'}]))
    for i,seek in enumerate(['0','10','1m','00:30','0:01:15','+5','-5','+0:20','-0:10','+1m','-1m','9999']):
        cps.append(cp('seek-'+str(i),'Seek using '+seek+'.',['seek 60','seek '+seek],[a('position','Seeking follows absolute and relative time syntax with one-second tolerance.',q('status','status',field='position',number=True,tolerance=1))],prepare=[{'play_paused':'/workspace/inbox/amber.flac'}]))
    for label,ops,expected in [('next',['player-next'],'amber.flac'),('previous',['player-next','player-prev'],'breeze.flac'),('rewind-to-start',['seek 30','player-prev'],'breeze.flac'),('next-album',['player-next-album'],'delta.flac'),('previous-album',['player-next-album','player-prev-album'],'breeze.flac')]:
        cps.append(cp(label,'Apply '+label+' to a populated library.',ops+['player-pause-playback'],[a('file','The playback traversal picks the correct file or rewinds the current one.',q('status','status',field='file',guard=expected))],prepare=['set shuffle=off','set rewind_offset=5','set continue=true','set play_library=true','view 2','/Breeze','win-activate','player-pause-playback']))
    cps += [cp('queue-priority','Play the queued track before the library.',['clear -q','add -q /workspace/inbox/echo.flac','player-next','player-pause-playback'],[a('file','The next track is taken from the queue.',q('status','status',field='file',guard='echo.flac')),a('queue','The played queue item is consumed.',q('save -q -','paths',allow_empty=True))],prepare=[{'play_paused':'/workspace/inbox/amber.flac'}]),cp('prepend-priority','Prepend a track ahead of another queue item.',['clear -q','add -q /workspace/inbox/echo.flac','add -Q /workspace/inbox/cobalt.flac','player-next','player-pause-playback'],[a('file','The prepended track plays first.',q('status','status',field='file',guard='cobalt.flac')),a('queue','The previously appended track remains queued.',q('save -q -','paths',guard=['echo.flac']))],prepare=[{'play_paused':'/workspace/inbox/amber.flac'}])]
    out+=split('player-controls','playback',cps,media_setup(True))
    # Search and navigation assert the actual selected file through native echo expansion.
    cps=[]
    for label,ops in [('top',['win-top']),('bottom',['win-bottom']),('down',['win-top','win-down 3']),('up',['win-bottom','win-up 3']),('clamp-up',['win-top','win-up 999']),('clamp-down',['win-top','win-down 999'])]:
        cps.append(cp(label,'Move the selection with '+label+'.',ops,[a('selected','The selected track is identified by cmus echo expansion.',q('echo {}',nonempty=True))],prepare=['view 2','filter','live-filter','set lib_sort=filename']))
    for label,search in [('artist','/Birch'),('title','/Echo'),('unicode','/光'),('restricted','//Amber'),('backward','?Jade'),('multiword','/Aster Dawn')]:
        cps.append(cp('search-'+label,'Search using '+search+'.',[search],[a('selected','Search selects a matching track.',q('echo {}',nonempty=True))],prepare=['view 2','win-top','set search_resets_position=true']))
    for start,operator,expected in [('1','left-view','settings'),('7','right-view','tree'),('3','left-view','sorted'),('3','right-view','queue'),('1','left-view -n','tree'),('7','right-view -n','settings')]:
        cid='view-'+start+'-'+operator.replace(' ','-')
        cps.append(cp(cid,'Navigate views using '+operator+'.',[operator,{'quit_saved':True}],
            [a('view','The native resume file records the resulting view.',st('resume','state-line',prefix='view ',guard=expected))],
            prepare=['set resume=true','view '+start]))
    out+=split('navigation-search','navigation',cps,media_setup(True))
    return out


def bindings():
    cps=[]
    cases=[('common','x','player-play'),('common','c','player-pause'),('common','v','player-stop'),('common','b','player-next'),('common','z','player-prev'),('common','B','player-next-album'),('common','Z','player-prev-album'),('common','r','toggle repeat'),('common','s','toggle shuffle'),('common','m','toggle aaa_mode'),('common','C','toggle continue'),('common','M','toggle play_library'),('common','o','toggle play_sorted'),('common','f','toggle follow'),('common','t','toggle show_remaining_time'),('common','1','view tree'),('common','2','view sorted'),('common','3','view playlist'),('common','4','view queue'),('common','5','view browser'),('common','6','view filters'),('common','7','view settings'),('common','j','win-down'),('common','k','win-up'),('common','g','win-top'),('common','G','win-bottom'),('common','enter','win-activate'),('common','space','win-toggle'),('common','D','win-remove'),('common','a','win-add-l'),('common','y','win-add-p'),('common','e','win-add-q'),('common','E','win-add-Q'),('common','p','win-mv-after'),('common','P','win-mv-before'),('common','/','search-start'),('common','?','search-b-start'),('common','n','search-next'),('common','N','search-prev'),('common','F','push filter '),('common','L','push live-filter '),('browser','space','win-activate'),('browser','backspace','browser-up'),('browser','i','toggle show_hidden'),('browser','u','win-update')]
    for i,(context,key,command) in enumerate(cases):
        cps.append(cp('default-'+str(i),'Inspect the '+context+' '+key+' binding.',[],[a('binding','The key maps to its documented action.',q('showbind '+context+' '+key,nonempty=True))]))
    out=split('keybindings','bindings',cps)
    cps=[]
    for context in ('common','library','playlist','queue','browser','filters'):
        name=context+'-custom'
        cps.append(cp(name,'Create a context-specific binding.',['bind -f '+context+' X echo custom-'+context],[a('binding','The context-specific command is stored.',q('showbind '+context+' X',nonempty=True))]))
        cps.append(cp(context+'-overwrite','Replace an existing binding.',['bind -f '+context+' X echo replacement'],[a('binding','Force binding replaces the previous command.',q('showbind '+context+' X',nonempty=True))],prepare=['bind -f '+context+' X echo original']))
        cps.append(cp(context+'-remove','Remove an existing binding.',['bind -f '+context+' X echo original','unbind '+context+' X'],[a('removed','Unbinding reports that no command remains.',q('showbind '+context+' X',nonempty=True))]))
    cps.append(cp('invoke','Invoke a custom key binding.',[{'key':'X'}],[a('visible','The custom command changes the repeat setting.',setting_check('repeat',guard='true'))],prepare=['bind -f common X set repeat=true','set repeat=false']))
    cps.append(cp('persist','Save and restore a custom key binding.',['bind -f common X echo persisted',{'restart':True}],[a('binding','The binding survives restart.',q('showbind common X',nonempty=True))]))
    out+=split('binding-edit','bindings',cps)
    return out


def errors():
    commands=['set missing_option=1','set repeat=maybe','toggle scroll_offset','set tree_width_percent=101','set buffer_seconds=0','view unknown','view 0','view 8','add','clear extra','clear -z','load','load -p inbox/amber.flac','save -z -','set','toggle','showbind','showbind common definitely_unknown','bind invalid x echo nope','unbind invalid x','seek nonsense','seek 1:xx','vol nonsense','pl-create','pl-rename','pl-delete no-such-playlist','pl-export','fset bad','filter title>5','filter unknown="x"','mark unknown="x"','factivate missing-filter','add -l /workspace/inbox/missing.flac','cd /workspace/no-such-folder','not-a-command','player-play a b c','win-down abc','win-up -2','unbind common','bind common']
    cps=[cp('error-'+str(i),'Reject the invalid command '+cmd+'.',[mutation(cmd)],[a('feedback','This invalid command produces nonempty native error feedback.',captured('reply','error',guard=True))]) for i,cmd in enumerate(commands)]
    return split('command-errors','errors',cps,media_setup(True))

def extended():
    from pathlib import Path
    out=[];cps=[]
    codecs=json.loads((Path(__file__).parent/'codecs.json').read_text())
    data=[{'id':'media','op':'upload','files':[{'filename':n,'base64':b} for n,b in codecs.items()]}]
    for name in codecs:
        cps.append(cp(name.replace('.','-'),'Decode and play the '+name+' audio format.',[{'play_paused':'/workspace/inbox/'+name}],[a('file','The format is decoded as a playable audio file.',q('status','status',field='file',guard=name)),a('duration','The decoded file has the expected approximate duration.',q('status','status',field='duration',number=True,tolerance=1)),a('codec','The format printer exposes a nonempty codec identifier.',q('format_print "%{codec}"',nonempty=True))]))
    out+=split('audio-formats','decoding',cps,data)
    cps=[];data=[{'id':'media','op':'upload','files':[]}]
    for rate,channels,bits in [(8000,1,16),(16000,2,16),(44100,1,16),(48000,2,16),(8000,1,8),(16000,2,24)]:
        name=f'pcm-{rate}-{channels}-{bits}.wav';data[0]['files'].append({'filename':name,'base64':base64.b64encode(fixtures.wav(2,rate,channels,bits)).decode()})
        cps.append(cp(name[:-4],'Decode the '+name+' PCM file.',[{'play_paused':'/workspace/inbox/'+name}],[a('file','PCM sample-rate, channel and bit-depth variations are playable.',q('status','status',field='file',guard=name)),a('duration','PCM frame counts give a two-second duration.',q('status','status',field='duration',number=True,guard=2.0))]))
    out+=split('pcm-formats','decoding',cps,data)
    # CLI is a normal invocation of start.sh with an upstream terminating option.
    out.append(episode('command-line','cli',[
        cp('version','Print the application version.',[],[a('version','The native version flag identifies cmus 2.13.0.',dict(source='cli',option='--version',project='cli-line',match='cmus v2.13.0',nonempty=True))]),
        cp('help','Print usage.',[],[a('help','Usage exposes the documented entry points.',dict(source='cli',option='--help',project='cli-has',texts=['--listen','--plugins','--version']))]),
        cp('plugins','List installed codecs and output methods.',[],[a('plugins','The installed decoding/output plugin list is observable.',dict(source='cli',option='--plugins',project='cli-has',texts=['Input Plugins','flac','wav','Output Plugins','pulse']))])]))
    # Native cache updates are observable by replacing media then asking cmus to re-read it.
    change={'filename':'amber.flac','base64':base64.b64encode(fixtures.flac({'artist':'New Artist','album':'New Album','title':'Retagged'},111)).decode(),'mtime':1800000000}
    out.append(episode('metadata-cache','metadata',[
        cp('update','Reload changed metadata through update-cache.',[{'upload':change},'update-cache -f',{'wait':.3},{'play_paused':'/workspace/inbox/amber.flac'}],[a('title','The reloaded track exposes its new title.',q('status','status',field='tag.title',guard='Retagged')),a('artist','The artist is updated from the changed audio tags.',q('status','status',field='tag.artist',guard='New Artist')),a('duration','The reloaded audio duration changes too.',q('status','status',field='duration',number=True,guard=111.0))])],media_setup(True)))
    # Deliberately distinguish duplicate filenames and duplicate tag identities.
    duplicate=dict(fixtures.TRACKS[0][1]);extra={'filename':'duplicate.flac','base64':base64.b64encode(fixtures.flac(duplicate,181)).decode()}
    for setting in ('true','false'):
        setup=media_setup();setup[0]['files'].append(extra)
        out.append(episode('duplicates-'+setting,'library',[cp('add','Add tag-identical files with ignore_duplicates='+setting+'.',['set ignore_duplicates='+setting,'add -l /workspace/inbox/amber.flac','add -l /workspace/inbox/duplicate.flac',{'wait_list':{'count':1 if setting=='true' else 2}}],[a('membership','Duplicate tag policy controls whether both distinct files are included.',q('save -l -','paths',nonempty=True))])],setup))
    # Addition filters have a distinct effect from temporary view filters: excluded tracks never enter the library.
    for label,expr in [('jazz','genre="Jazz"'),('long','duration>200'),('tagged','tag')]:
        out.append(episode('add-filter-'+label,'library',[cp('add','Add inbox with a library-add filter.',['set lib_add_filter='+expr,'add -l inbox',{'wait_list':{'count':{'jazz':2,'long':3,'tagged':11}[label]}}],[a('membership','The permanent library contains only tracks accepted at addition.',q('save -l -','paths',nonempty=True))])],media_setup()))
    # Source reads cmus command files within the exchange directory, still subject to OS restrictions.
    setup=media_setup();setup[0]['files'].append(base64file('settings.txt','set repeat=true\nset shuffle=albums\nfset FromFile=genre="Jazz"\nfactivate FromFile\n'))
    out.append(episode('source-config','configuration',[cp('source','Read commands from an exchanged cmus configuration file.',['add -l inbox',{'wait_list':{'count':12}},'source /workspace/inbox/settings.txt'],[a('repeat','The command file changes the repeat setting.',setting_check('repeat',guard='true')),a('shuffle','The command file changes shuffle mode.',setting_check('shuffle',guard='albums')),a('filter','The command file defines and activates a working filter.',q('save -L -','paths',guard=['amber.flac','breeze.flac']))])],setup))
    return out

def additional():
    out=[];allowed=[x[0] for x in fixtures.TRACKS]
    cps=[cp('tracks','Queue three random tracks from the library.',['clear -q','tqueue 3'],[a('selection','Exactly three chosen tracks belong to the library.',q('save -q -','random-selection',count=3,allowed=allowed))]),cp('default-track','Queue the default single random track.',['clear -q','tqueue'],[a('selection','The default random track count is one.',q('save -q -','random-selection',count=1,allowed=allowed))]),cp('album','Queue one random album from a single-album filtered library.',['filter artist="Aster"','clear -q','lqueue 1'],[a('album','The random album includes its two tracks in album order.',q('save -q -','paths',unordered=False,guard=['breeze.flac','amber.flac']))]),cp('default-album','Queue the default single album from another filtered artist.',['filter artist="Birch"','clear -q','lqueue'],[a('album','The default album count is one complete album.',q('save -q -','paths',unordered=False,guard=['delta.flac','cobalt.flac']))])]
    out.append(episode('random-queue','queue',cps,media_setup(True)))
    out.append(episode('extended-export','playlists',[cp('save','Export library metadata to an extended text playlist.',['save -e -l /workspace/outbox/metadata.txt'],[a('records','Extended export preserves file identities and durations.',dict(source='workspace',request={'action':'read','path':'outbox/metadata.txt'},project='extended-records',fields=['file','duration'])),a('tags','Extended export includes the tracks title, artist and album metadata.',dict(source='workspace',request={'action':'read','path':'outbox/metadata.txt'},project='extended-records',fields=['file','title','artist','album']))])],media_setup(True)))
    cue='FILE "amber.flac" WAVE\n  TRACK 01 AUDIO\n    TITLE "Cue Alpha"\n    PERFORMER "Cue Artist"\n    INDEX 01 00:00:00\n  TRACK 02 AUDIO\n    TITLE "Cue Beta"\n    PERFORMER "Cue Artist"\n    INDEX 01 01:00:00\n'
    setup=media_setup();setup[0]['files'].append(base64file('album.cue',cue))
    cps=[cp('add','Add a two-track cue sheet.',['add -l /workspace/inbox/album.cue',{'wait':.2}],[a('tracks','The library expands the cue sheet into two track URLs.',q('save -l -',nonempty=True))]),cp('first','Play the first cue subtrack.',['view 2','win-top','win-activate','player-pause-playback'],[a('title','Cue title metadata labels the first subtrack.',q('status','status',field='tag.title',guard='Cue Alpha')),a('duration','The first cue region ends at its following index.',q('status','status',field='duration',number=True,guard=60.0))],depends=['add']),cp('second','Play the second cue subtrack.',['win-down','win-activate','player-pause-playback'],[a('title','The second cue title is exposed.',q('status','status',field='tag.title',guard='Cue Beta')),a('duration','The final cue region uses the remaining duration.',q('status','status',field='duration',number=True,guard=121.0))],depends=['first'])]
    out.append(episode('cue-sheet','decoding',cps,setup))
    themes=['amazon','cyan','default','dracula','gray-88','green-mono-88','green','gruvbox-alt','gruvbox-warm','gruvbox','jellybeans','night','solarized-dark','solarized-light','spotify','xterm-white','zenburn']
    cps=[]
    for theme in themes:
        cps.append(cp(theme,'Select the '+theme+' built-in color scheme.',['colorscheme '+theme],[a('title','The scheme supplies its window title foreground.',setting_check('color_win_title_fg',nonempty=True)),a('selection','The scheme supplies its selected-entry background.',setting_check('color_win_sel_bg',nonempty=True))]))
    out+=split('themes','display',cps)
    # The alias command and history work through actual terminal input.
    cps=[cp('abbreviation','Use an unambiguous command abbreviation.',['to repeat'],[a('value','An unambiguous abbreviated command is recognized.',setting_check('repeat',guard='true'))],prepare=['set repeat=false']),cp('history','Repeat the most recent console command with Up and Enter.',[{'console':'toggle repeat'},{'key':':'},{'key':'Up'},{'key':'Enter'}],[a('value','Console history restores and executes the previous command.',setting_check('repeat',guard='false'))],prepare=['set repeat=false']),cp('line-delete','Edit the console line before submitting it.',[{'key':':'},{'type':'set repeat=false'},{'key':'Control+U'},{'type':'set repeat=true'},{'key':'Enter'}],[a('value','Console line deletion replaces the pending input.',setting_check('repeat',guard='true'))],prepare=['set repeat=false']),cp('cancel','Cancel a pending command without applying it.',[{'key':':'},{'type':'set repeat=false'},{'key':'Escape'}],[a('value','Canceling preserves the prior active value.',setting_check('repeat',guard='true'))],prepare=['set repeat=true'])]
    out.append(episode('console-editing','console',cps))
    return out
