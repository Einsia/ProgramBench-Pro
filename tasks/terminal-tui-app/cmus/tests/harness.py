"""Only the runtime's public channels are used by setup, drivers and observations."""
import re
import time

class Session:
    def __init__(self,broker):self.broker=broker;self.saved={}
    def call(self,op,**fields):return self.broker.call({'op':op,**fields})
    def remote(self,command):
        value=self.call('remote',command=command)
        if not isinstance(value.get('stdout'),str):raise AssertionError('native control output is missing')
        return value['stdout']
    def key(self,k):return self.call('key',key=k)
    def keys(self,ks):return self.call('keys',keys=list(ks))
    def type(self,s):return self.call('type',text=s)
    def console(self,s):self.key('Escape');self.key(':');self.type(s);return self.key('Enter')
    def upload(self,f):return self.call('upload',**f)
    def wait_list(self,command='save -l -',count=None,expected=None,timeout=15):
        """Wait for a known business postcondition, never a briefly stable partial import."""
        if count is None and expected is None:raise ValueError('wait_list needs an exact count or membership')
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            try:names=paths(self.remote(command))
            except AssertionError:
                time.sleep(.1);continue
            if (count is None or len(names)==count) and (expected is None or sorted(names)==sorted(expected)):
                self.remote('echo ""')
                return names
            time.sleep(.1)
        raise AssertionError('native playlist did not reach the expected complete contents')
    def quit_saved(self):
        self.remote('quit')
        return self.wait_stopped()
    def wait_stopped(self):
        end=time.monotonic()+5
        while time.monotonic()<end:
            if not self.call('status').get('running'):return
            time.sleep(.05)
        raise AssertionError('application did not finish saving and quitting')
    def wait_status(self,expected,timeout=10):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            status=parse_status(self.remote('status'))
            if all(status.get(k) in v if isinstance(v,list) else status.get(k)==v for k,v in expected.items()):return status
            time.sleep(.05)
        raise AssertionError('playback did not reach the expected state')
    def wait_positive(self,command,timeout=3):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            value=self.remote(command).strip()
            try:
                if float(value)>0:return True
            except ValueError:raise AssertionError('the format response is not a number')
            time.sleep(.05)
        raise AssertionError('the expected positive format value did not appear')
    def sort_keys(self,field,count):
        bitrates={}
        if field=='bitrate':
            filename=None
            for line in self.remote('save -e -l -').splitlines():
                if line.startswith('file '):filename=line[5:].rsplit('/',1)[-1]
                elif line.startswith('bitrate ') and filename:bitrates[filename]=float(line.split()[1])
        self.remote('win-top');keys=[]
        for _ in range(count):
            path=self.remote('echo {}').strip()
            if not path.startswith('/workspace/'):raise AssertionError('sorted selection has no file')
            if field=='bitrate':
                if path.rsplit('/',1)[-1] not in bitrates:raise AssertionError('extended export has no bitrate')
                keys.append(bitrates[path.rsplit('/',1)[-1]]);self.remote('win-down');continue
            self.play_paused(path)
            value=self.remote('format_print "%{'+field+'}"').strip()
            if field in ('bitrate','rg_track_gain','rg_track_peak','rg_album_gain','rg_album_peak'):
                try:value=float(value) if value else None
                except ValueError:raise AssertionError('numeric sort key is invalid')
            keys.append(value)
            self.remote('win-down')
        return keys
    def navigate(self,command,rule):
        def window():
            text='\n'.join(self.call('screen')['screen'])
            return sorted(set(int(x) for x in re.findall(r'Track-(\d{2})',text)))
        def selected():
            value=self.remote('echo {}')
            m=re.search(r'page-(\d{2})\.flac',value)
            if not m:raise AssertionError('the selected page track is missing')
            return int(m[1])
        before=window();start=selected()
        self.remote(command);after=window();end=selected()
        if not before or not after:raise AssertionError('the visible track window is empty')
        page=len(before)
        if rule in ('page-down','page-up','half-down','half-up'):
            distance=((page-1)//2 if rule.startswith('half') else page-1)
            distance=min(distance,59-before[-1] if rule.endswith('down') else before[0])
            target=max(0,min(59,start+(distance if rule.endswith('down') else -distance)))
            return end!=start and abs(end-target)<=3
        if rule=='page-top':return end!=start and before[0]<=end<=before[0]+2
        if rule=='page-bottom':return end!=start and before[-1]-2<=end<=before[-1]
        if rule=='page-middle':return end!=start and abs(end-(before[0]+before[-1])//2)<=2
        if rule=='scroll-down':return after[0]==before[0]+1 and end==start
        if rule=='scroll-up':return after[0]==before[0]-1 and end==start
        raise ValueError('unknown page movement rule')
    def boundary(self,expected=None,loop=False,timeout=8):
        self.remote('player-play')
        self.wait_status({'status':'playing'})
        initial=parse_status(self.remote('status'));progress=False;deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            st=parse_status(self.remote('status'))
            if loop:
                pos=int(st.get('position','-1'))
                if pos>=2:progress=True
                if progress and 0<=pos<=1 and st.get('status')=='playing' and st.get('file')==initial.get('file'):
                    self.remote('player-pause-playback');return {'looped':True}
            elif all(st.get(k)==v for k,v in expected.items()):
                if st.get('status')=='playing':self.remote('player-pause-playback')
                return {k:st.get(k) for k in expected}
            time.sleep(.05)
        raise AssertionError('track-end playback transition did not reach its expected result')
    def random_order(self,command,count=12):
        self.remote('view 4' if command=='rand' else 'view 2')
        if command=='rand':
            before=paths(self.remote('save -q -'))
            for _ in range(3):
                self.remote('rand');after=paths(self.remote('save -q -'))
                if sorted(before)!=sorted(after) or len(after)!=count:raise AssertionError('randomization lost or duplicated tracks')
                if after!=before:return True
            return False
        def traversal():
            self.remote('win-top');self.remote('win-activate');self.remote('player-pause-playback')
            seq=[]
            for _ in range(count):
                st=parse_status(self.remote('status'));name=st.get('file','').rsplit('/',1)[-1]
                if not name:raise AssertionError('shuffle playback has no current file')
                seq.append(name);self.remote('player-next');self.remote('player-pause-playback')
            return seq
        first=traversal();self.remote('reshuffle');second=traversal()
        return len(set(first))==count and sorted(first)==sorted(second) and first!=second
    def order(self,count):
        self.remote('win-top');out=[]
        for _ in range(count):
            s=self.remote('echo {}').strip()
            if not s or '/' not in s:raise AssertionError('selection did not identify a track')
            out.append(s.rsplit('/',1)[-1]);self.remote('win-down')
        return out
    def visible(self):
        self.remote('win-top');out=[]
        for _ in range(512):
            name=self.remote('echo {}').strip()
            if not name:break
            if not name.startswith(('/workspace/','inbox/','cue://')):raise AssertionError('native selection query returned an error or invalid path')
            name=name.rsplit('/',1)[-1]
            if out and name==out[-1]:break
            out.append(name);self.remote('win-down')
        return out
    def play_paused(self,path):
        self.remote('player-play '+path)
        end=time.monotonic()+5
        while time.monotonic()<end:
            status=parse_status(self.remote('status'))
            if status.get('status')=='playing' and 'file' in status:break
            time.sleep(.03)
        else:raise AssertionError('track did not begin playing')
        self.remote('player-pause-playback')
        for _ in range(30):
            if parse_status(self.remote('status')).get('status')=='paused':return
            time.sleep(.03)
        raise AssertionError('track did not pause')


def paths(text):
    lines=[s.strip() for s in text.splitlines() if s.strip() and not s.startswith('#')]
    if any(not (s.startswith('/') or s.startswith('inbox/') or '\x1f' in s) for s in lines):raise AssertionError('native playlist output contains an error or invalid entry')
    return [s.rsplit('/',1)[-1] for s in lines]


def parse_status(text):
    out={}
    for line in text.splitlines():
        if line.startswith(('tag ','set ')):
            a,b,c=(line.split(' ',2)+[''])[:3];out[a+'.'+b]=c
        elif ' ' in line:
            k,v=line.split(' ',1);out[k]=v
    return out


def setting(text):
    m=re.search(r"setting:\s*'(.*?)'\s*$",text,re.S)
    if not m or '=' not in m[1]:raise AssertionError('setting query did not return a setting value')
    return m[1].split('=',1)[1]
