"""Independent semantic checks for ordinary playlists, images and audio documents."""
import configparser
import hashlib
import json
import math
import posixpath
from pathlib import Path
import re
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET


def playlist_entries(path):
    text=Path(path).read_text(encoding='utf-8-sig')
    ext=Path(path).suffix.casefold()
    if ext in ('.m3u','.m3u8'):
        return [s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('#')]
    if ext=='.pls':
        parser=configparser.ConfigParser(interpolation=None,strict=False)
        parser.read_string(text)
        section=next((s for s in parser.sections() if s.casefold()=='playlist'),None)
        assert section is not None,'PLS playlist section missing'
        numbered={int(k[4:]):v.strip() for k,v in parser[section].items() if re.fullmatch(r'file\d+',k,re.I)}
        assert numbered,'PLS has no file entries'
        return [numbered[i] for i in sorted(numbered)]
    tree=ET.fromstring(text)
    if ext=='.xspf':return [e.text.strip() for e in tree.iter() if e.tag.rsplit('}',1)[-1]=='location' and e.text]
    if ext=='.wpl':return [e.attrib['src'] for e in tree.iter() if e.tag.casefold()=='media' and 'src' in e.attrib]
    if ext=='.asx':return [v for e in tree.iter() if e.tag.casefold()=='ref' for k,v in e.attrib.items() if k.casefold()=='href']
    raise AssertionError('unsupported playlist format')


def document_path(reference,playlist_path):
    assert isinstance(reference,str) and reference.strip(),'empty playlist entry'
    uri=urllib.parse.urlsplit(reference.strip())
    assert uri.scheme.casefold() in ('','file'),'playlist target must be a local document'
    assert not uri.netloc or uri.netloc.casefold()=='localhost','remote file target'
    assert not uri.query and not uri.fragment,'unexpected URI query or fragment'
    raw=urllib.parse.unquote(uri.path)
    assert raw and '\x00' not in raw,'invalid playlist target'
    return posixpath.normpath(raw if raw.startswith('/') else posixpath.join(posixpath.dirname(playlist_path),raw))


def playlist_identity(c,name,expected_files,area='outputs'):
    path=c.take(name,area=area)
    public=posixpath.join(c.areas[area],name)
    targets=[document_path(u,public) for u in playlist_entries(path)]
    expected=[posixpath.join(c.areas[a],n) for a,n in expected_files]
    assert targets==expected,'exported playlist points to different documents or order'
    available={row['path'] for a in c.areas for row in c.call(op='list_files',area=a)['files']}
    assert all(t in available for t in targets),'exported playlist target does not exist'
    # Display titles and optional EXTINF metadata are not an export-format contract.
    return {'documents':[{'area':a,'file':n} for a,n in expected_files]}


def audio_info(path):
    proc=subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(path)],capture_output=True,text=True,timeout=45)
    assert proc.returncode==0,'media output is not readable'
    streams=json.loads(proc.stdout).get('streams',[])
    stream=next((s for s in streams if s.get('codec_type')=='audio'),None)
    assert stream is not None,'media output contains no audio stream'
    return stream


def decode_audio(path,rate=32000):
    import numpy as np
    stream=audio_info(path);channels=int(stream['channels'])
    assert 1<=channels<=8,'invalid audio channel count'
    proc=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-ar',str(rate),'-f','f32le','-'],capture_output=True,timeout=60)
    assert proc.returncode==0 and proc.stdout,'audio output did not decode'
    samples=np.frombuffer(proc.stdout,dtype='<f4')
    assert len(samples)%channels==0 and np.isfinite(samples).all(),'invalid audio samples'
    return samples.reshape(-1,channels),stream


def verify_audio(actual_path,source_path,codec=None):
    """Inspect every half-second window of each channel, including the final window.

    Sine frequencies and segment envelopes differ in the two channels. Windows
    avoid only 100 ms at each segment edge to allow normal codec priming. The
    source fixture includes content changes throughout its complete duration.
    """
    import numpy as np
    rate=32000
    source,_=decode_audio(source_path,rate);actual,stream=decode_audio(actual_path,rate)
    assert actual.shape[1]==source.shape[1],'transcoding lost or added channels'
    assert abs(len(source)-len(actual))/rate<.16,'transcoded duration differs'
    if codec is not None:
        allowed={'wav':{'pcm_s16le'},'mp3':{'mp3'},'opus':{'opus'},'flac':{'flac'},'ogg-flac':{'flac'},
                 'alac':{'alac'},'aac':{'aac'},'vorbis':{'vorbis'},'speex':{'speex'},'wavpack':{'wavpack'},'asf':{'wmav2'}}[codec]
        assert stream['codec_name'] in allowed,'wrong output codec'
    # Align global codec delay from complete multichannel cross-correlation.
    n=min(len(source),len(actual));size=1<<(2*n-1).bit_length()
    corr=np.zeros(size)
    for ch in range(source.shape[1]):
        corr+=np.fft.irfft(np.fft.rfft(actual[:n,ch],size)*np.conj(np.fft.rfft(source[:n,ch],size)),size)
    maxlag=int(.12*rate);lags=np.arange(-maxlag,maxlag+1)
    lag=int(lags[np.argmax(corr[lags%size])])
    if lag>0:actual=actual[lag:]
    elif lag<0:source=source[-lag:]
    n=min(len(source),len(actual));window=rate//2
    # Full signal envelope: no unexamined long middle or tail region.
    starts=list(range(0,max(1,n-window+1),window))
    if starts[-1]!=n-window:starts.append(max(0,n-window))
    for ch in range(source.shape[1]):
        for start in starts:
            a=source[start:start+window,ch];b=actual[start:start+window,ch]
            ar=float(np.sqrt(np.mean(a*a)));br=float(np.sqrt(np.mean(b*b)))
            assert abs(ar-br)<=max(.008,.18*ar),f'channel {ch+1} signal level differs near {start/rate:.1f}s'
            # Segment boundary windows may contain two frequencies; use an inset
            # for spectral identity, leaving at most normal priming slack.
            pad=int(.1*rate);a=a[pad:-pad];b=b[pad:-pad]
            fa=int(np.argmax(np.abs(np.fft.rfft(a))));fb=int(np.argmax(np.abs(np.fft.rfft(b))))
            assert abs(fa-fb)<=2,f'channel {ch+1} signal frequency differs near {start/rate:.1f}s'
    return {'codec':stream['codec_name'],'channels':actual.shape[1],'seconds':float(stream.get('duration',len(actual)/rate)),'signal':'all-channel windows matched'}


def verify_organized(c,spec):
    import fixtures
    rows=c.call(op='list_files',area='music')['files'];names=[r['filename'] for r in rows]
    expected=spec['file'];original=spec.get('source','01 Aurora.flac')
    assert expected in names,'organized document missing'
    assert (original in names)==spec.get('keep',False),'original-file retention differs'
    target=c.take(expected,area='music')
    # File organization moves/copies documents without decoding or rewriting tags.
    assert target.read_bytes()==fixtures.audio(original).read_bytes(),'organized file contents differ from original'
    return {'organized':expected,'preserved_content':True,'original_retained':spec.get('keep',False)}


def image_matches(payload,source):
    from PIL import Image
    import io
    import numpy as np
    im=Image.open(io.BytesIO(payload)).convert('RGB').resize((64,64))
    ref=Image.open(source).convert('RGB').resize((64,64))
    error=float(np.mean(np.abs(np.asarray(im,dtype=float)-np.asarray(ref,dtype=float))))
    assert error<10,'cover artwork differs from input image'
    return True


def cover_result(c,spec):
    import fixtures
    if spec['kind']=='cover-file':payload=c.take(spec['file']).read_bytes()
    else:
        from mutagen.flac import FLAC
        audio=FLAC(c.take(spec['file'],area='music'))
        if spec.get('absent'):
            assert not audio.pictures,'embedded cover was not removed'
            return {'embedded':False}
        assert audio.pictures,'embedded cover missing'
        payload=audio.pictures[0].data
    image_matches(payload,fixtures.image_file(spec['image']))
    return {'image':spec['image'],'matching_pixels':True}
