"""Deterministic, independently generated audio and playlist documents."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import wave
from xml.sax.saxutils import escape

FORMATS = {
    'flac': ('flac','flac',[]), 'ogg': ('ogg','libvorbis',['-q:a','4']),
    'opus': ('opus','libopus',['-b:a','64000']), 'mp3': ('mp3','libmp3lame',['-b:a','128000']),
    'aac': ('m4a','aac',['-b:a','128000']), 'alac': ('m4a','alac',[]),
    'wav': ('wav','pcm_s16le',[]), 'aiff': ('aif','pcm_s16be',[]),
    'wavpack': ('wv','wavpack',[]), 'asf': ('wma','wmav2',['-b:a','128000']),
    'speex': ('spx','libspeex',['-ar','32000']), 'ogg-flac': ('oga','flac',['-f','ogg']),
    'tta': ('tta','tta',[]),
}
PROFILES = [
    ('First Light','Mira','Morning','Mira Ensemble','Ambient','A. Writer','Opening movement',1,1,2001,44100,1,3.0),
    ('星の歌','青い鳥','夜の音楽','世界の音','電子音楽','作曲家 林','日本語 中文 한국어',12,2,2024,48000,2,4.25),
    ('Été à Łódź','Björk Åsa','Café déjà vu','Orchestre Noël','Chanson','Zoë García','Crème brûlée',7,3,1999,32000,1,2.5),
    ('Rock & <Roll> "Live"','A/B + C','Side: One?','A & Friends','Rock; Pop','D. E. F.','Quotes "x" & <y>',22,4,2012,44100,2,5.0),
    ('A title '+('long phrase '*18),'An artist '+('ensemble '*12),'Album '+('suite '*15),'Collective '+('players '*9),'Experimental','Composer '+('name '*10),'A comment '+('details '*30),99,12,2030,48000,1,6.5),
    ('  Leading and trailing  ','  Performer  ','  Album spaces  ','  Ensemble  ','  Jazz  ','  Composer  ','  Comment  ',3,1,1987,44100,2,7.25),
    ('Numbers 007','Unit 42','Archive 999','Group 12','Classical','Composer 7','High track and disc numbers',255,99,2099,22050,1,8.0),
    ('Line One\nLine Two','First; Second','Disc One','Various Artists','Jazz / Fusion','One; Two','First line\nSecond line\tTabbed',2,2,1970,48000,2,9.5),
]
GUI = {
    '01 Aurora.flac': dict(title='Aurora',artist='Lina Vale',album='Northern Lights',album_artist='Lina Vale',genre='Ambient',composer='Alex Reed',comment='First session',track='1',disc='1',date='2020'),
    '02 Blue Harbor.flac': dict(title='Blue Harbor',artist='Orion Trio',album='Harbor Sessions',album_artist='Orion Trio',genre='Jazz',composer='Nora West',comment='Live set',track='2',disc='1',date='2022'),
    '03 Cedar Road.flac': dict(title='Cedar Road',artist='Lina Vale',album='Northern Lights',album_artist='Lina Vale',genre='Folk',composer='Alex Reed',comment='Acoustic take',track='3',disc='1',date='2020'),
    '04 Dancing Stars.flac': dict(title='Dancing Stars',artist='Nova Unit',album='Night Sky',album_artist='Nova Unit',genre='Electronic',composer='Eli Stone',comment='Studio mix',track='4',disc='2',date='2024'),
    '05 雨の音.flac': dict(title='雨の音',artist='青い鳥',album='夜の音楽',album_artist='青い鳥',genre='Ambient',composer='林',comment='静かな夜',track='5',disc='1',date='2023'),
}
SORT_FILES={f'sort-{i+1}.flac':dict(meta,track=str(track)) for i,(meta,track) in enumerate(zip(list(GUI.values())[:4],(3,1,4,2)))}
ORGANIZE_FILES={'Copy A.flac':dict(GUI['01 Aurora.flac'],title='Shared'),'Copy B.flac':dict(GUI['02 Blue Harbor.flac'],title='Shared')}
TRANSCODE_SOURCE='Stereo Journey.flac'
SHORT_FILES={'Short Amber.flac':(3.0,330),'Short Blue.flac':(4.0,550),'Short Coral.flac':(5.0,770)}
PLAYLIST_FILES=['First & Last.flac','Middle 空間.flac','Finale.flac']


def varied_pcm(path,gain=1.0,seconds=12):
    import numpy as np
    rate=32000;frames=rate*seconds;t=np.arange(frames)/rate
    samples=np.empty((frames,2),dtype=np.float64)
    for ch in range(2):
        for seg in range(seconds//2):
            sl=slice(seg*rate*2,(seg+1)*rate*2)
            freq=(220,440,660,880,330,550)[seg]+ch*170
            amp=(.10,.22,.14,.28,.18,.12)[seg]*(1 if ch==0 else .7)*gain
            samples[sl,ch]=amp*np.sin(2*np.pi*freq*t[sl])
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes((samples*32767).astype('<i2').tobytes())


def special_audio(path,filename):
    if filename.startswith('variant--'):
        fmt,variant=filename.split('--')[1:];variant=variant.rsplit('.',1)[0]
        tags=dict(GUI['01 Aurora.flac'],title='Variant title',artist='Solo Artist',album='Variant album',track='12/20',disc='3/4',date='1998-07-09')
        if variant=='no-title':tags.pop('title')
        if variant=='no-artist':tags.pop('artist')
        if variant=='minimal':tags={'title':'Minimal tags'}
        encode(path,fmt,tags,32000,1,.35 if variant=='short' else 3.25,2)
        if variant=='multi':
            import mutagen
            media=mutagen.File(path,easy=True)
            if fmt=='wav':
                from mutagen.id3 import TPE1
                media.tags.add(TPE1(encoding=3,text=['First Artist','Second Artist']));media.save()
            else:media['artist']=['First Artist','Second Artist'];media.save()
        return True
    if filename in ORGANIZE_FILES:
        encode(path,'flac',ORGANIZE_FILES[filename],22050,1,8,list(ORGANIZE_FILES).index(filename));return True
    if filename in SORT_FILES:
        encode(path,'flac',SORT_FILES[filename],22050,1,180,list(SORT_FILES).index(filename));return True
    if filename==TRANSCODE_SOURCE or filename in ('Speech Journey.flac','Quiet Study.flac','Loud Study.flac'):
        pcm=path.with_suffix('.wav')
        varied_pcm(pcm,.2 if filename=='Quiet Study.flac' else .9 if filename=='Loud Study.flac' else 1)
        tags={'title':filename.removesuffix('.flac'),'artist':'Signal Ensemble','album':'Channel Studies','genre':'Test','track':'7'}
        cmd=['ffmpeg','-v','error','-y','-i',str(pcm),*(['-ac','1'] if filename=='Speech Journey.flac' else []),'-c:a','flac']
        for k,v in tags.items():cmd+=['-metadata',k+'='+v]
        subprocess.run(cmd+[str(path)],check=True,capture_output=True,timeout=60);pcm.unlink();return True
    if filename in SHORT_FILES or filename in PLAYLIST_FILES:
        seconds,freq=SHORT_FILES.get(filename,(17+5*PLAYLIST_FILES.index(filename),330)) if filename in PLAYLIST_FILES else SHORT_FILES[filename]
        tags=dict(GUI['01 Aurora.flac'],title=filename.removesuffix('.flac'),track='9',disc='2')
        encode(path,'flac',tags,32000,2,seconds,int(freq/37));return True
    return False


META_FIELDS = ['xesam:url','xesam:title','xesam:artist','xesam:album','xesam:albumArtist','mpris:length',
               'xesam:trackNumber','xesam:genre','xesam:discNumber','xesam:comment','xesam:composer']


def name(fmt,index):
    return f'{fmt}-{index+1:02d} 音楽.{FORMATS[fmt][0]}'


def encode(path,fmt,tags,rate,channels,duration,index):
    _,codec,extra=FORMATS[fmt]
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-f','lavfi','-i',
         f'sine=frequency={220+index*37}:sample_rate={rate}:duration={duration}',
         '-ac',str(channels),'-c:a',codec,*extra]
    for key,value in tags.items():cmd+=['-metadata',f'{key}={value}']
    cmd += [str(path)]
    subprocess.run(cmd,check=True,timeout=60,capture_output=True)
    # ID3-tagged WAV and AIFF exercise their real TagLib readers, rather than
    # relying on the narrower RIFF/AIFF metadata FFmpeg happens to write.
    if fmt in ('wav','aiff','mp3','tta'):
        from mutagen.wave import WAVE
        from mutagen.aiff import AIFF
        from mutagen.mp3 import MP3
        from mutagen.trueaudio import TrueAudio
        from mutagen.id3 import TIT2,TPE1,TALB,TPE2,TCON,TCOM,COMM,TRCK,TPOS,TDRC
        a={'wav':WAVE,'aiff':AIFF,'mp3':MP3,'tta':TrueAudio}[fmt](path)
        if a.tags is None:a.add_tags()
        for klass,key in [(TIT2,'title'),(TPE1,'artist'),(TALB,'album'),(TPE2,'album_artist'),(TCON,'genre'),
                          (TCOM,'composer'),(TRCK,'track'),(TPOS,'disc'),(TDRC,'date')]:
            if key in tags:a.tags.add(klass(encoding=3,text=[tags[key]]))
        if 'comment' in tags:a.tags.add(COMM(encoding=3,lang='eng',desc='',text=[tags['comment']]))
        a.save()
    elif fmt=='wavpack':
        from mutagen.wavpack import WavPack
        a=WavPack(path);a['Album Artist']=[tags['album_artist']];a.save()
    elif fmt=='asf':
        from mutagen.asf import ASF
        a=ASF(path);a['Description']=[tags['comment']];a.save()


def store():
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    root=Path(os.environ.get('TMPDIR','/tmp'))/('strawberry-fixtures-'+digest)
    root.mkdir(parents=True,exist_ok=True)
    return root


def audio(filename):
    if filename in ('Blue Cover.png','Gold Cover.png'):return image_file(filename)
    root=store();path=root/filename
    with (root/'generate.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if path.exists():return path
        if special_audio(path,filename):return path
        if filename in GUI:
            index=list(GUI).index(filename)
            encode(path,'flac',GUI[filename],22050,1,180,index)
        else:
            fmt,index=next((f,i) for f in FORMATS for i in range(len(PROFILES)) if name(f,i)==filename)
            row=PROFILES[index]
            tags=dict(zip(['title','artist','album','album_artist','genre','composer','comment','track','disc','date'],map(str,row[:10])))
            encode(path,fmt,tags,*row[10:],index)
    return path


def playlist(kind,paths,variant=0):
    order=[0,1,2] if variant==0 else ([2,0,1] if variant==1 else ([1,1,0] if variant==2 else [0,2]))
    selected=[paths[i] for i in order]
    urls=[Path(p).as_uri() for p in selected]
    if kind in ('m3u','m3u8'):
        ending='\r\n' if variant==1 else '\n'
        rows=['#EXTM3U']
        for i,p in enumerate(selected):rows+=['#EXTINF:180,Track '+str(i+1),urls[i] if variant==2 else p]
        text=ending.join(rows)+ending
        return ('\ufeff'+text if variant==3 else text).encode('utf-8')
    if kind=='pls':
        rows=['[playlist]',f'NumberOfEntries={len(selected)}','Version=2']
        for i,p in enumerate(selected,1):rows += [f'File{i}={p}',f'Title{i}=List title {i}',f'Length{i}=180']
        return ('\n'.join(rows)+'\n').encode()
    if kind=='xspf':
        tracks=''.join('<track><location>'+escape(u)+'</location><title>List title</title><creator>List creator</creator><duration>180000</duration></track>' for u in urls)
        return ('<?xml version="1.0" encoding="UTF-8"?><playlist version="1" xmlns="http://xspf.org/ns/0/"><trackList>'+tracks+'</trackList></playlist>').encode()
    if kind=='asxini':
        return ('[Reference]\n'+''.join(f'Ref{i}={p}\n' for i,p in enumerate(selected,1))).encode()
    if kind=='wpl':
        refs=[Path(p).name if variant==3 else u for p,u in zip(selected,urls)]
        return ('<?wpl version="1.0"?><smil><head><title>Local list</title></head><body><seq>'+''.join('<media src="'+escape(u,{'"':'&quot;'})+'"/>' for u in refs)+'</seq></body></smil>').encode()
    if kind=='asx':
        urls=[Path(p).name for p in selected] if variant==3 else urls
        return ('<ASX version="3.0">'+''.join('<ENTRY><TITLE>List title</TITLE><REF href="'+escape(u,{'"':'&quot;'})+'" /></ENTRY>' for u in urls)+'</ASX>').encode()
    if kind=='cue':
        boundary=[('00:10:00','00:20:00'),('00:01:37','00:03:12'),('00:00:30','00:09:45')][variant%3]
        return ('PERFORMER "Cue Artist"\nTITLE "Cue Album"\nFILE "'+paths[0]+'" WAVE\n'
                '  TRACK 01 AUDIO\n    TITLE "Opening"\n    INDEX 01 00:00:00\n'
                '  TRACK 02 AUDIO\n    TITLE "Middle"\n    INDEX 01 '+boundary[0]+'\n'
                '  TRACK 03 AUDIO\n    TITLE "Finale"\n    INDEX 01 '+boundary[1]+'\n').encode()
    raise ValueError(kind)


def image_file(filename):
    from PIL import Image,ImageDraw
    path=store()/filename
    if not path.exists():
        blue=filename=='Blue Cover.png'
        im=Image.new('RGB',(160,160),(25,65,210) if blue else (245,180,25))
        draw=ImageDraw.Draw(im)
        draw.rectangle((16,16,70,145),fill=(240,240,250) if blue else (150,35,35))
        draw.ellipse((85,20,145,80),fill=(240,190,25) if blue else (20,85,170))
        im.save(path)
    return path
