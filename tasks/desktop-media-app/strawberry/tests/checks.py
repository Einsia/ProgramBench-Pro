"""Independent checks of the state directly requested by GUI goals."""
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
from harness import compare,value


def observe(c,spec):
    kind=spec['kind']
    if kind=='tracks':
        if spec.get('current'):
            current=c.get('ActivePlaylist','Playlists')
            assert current[0] and current[1][0],'no current playlist'
            c.method('ActivatePlaylist',current[1][0],interface='Playlists')
            c.call(op='wait',seconds=1)
            if c.get('PlaybackStatus')=='Playing':c.method('Pause')
        actual=[m.get('xesam:title') for m in c.tracks()]
        compare(actual,spec['titles']);return actual
    if kind=='dynamic-added':
        actual=[m.get('xesam:title') for m in c.tracks()]
        assert set(spec['initial'])<=set(actual)<=set(spec['allowed']),'dynamic membership differs'
        assert len(actual)==len(set(actual))>len(spec['initial']),'dynamic mode did not append new unique songs'
        return {'added_matching_songs':True,'unique':True}
    if kind=='track-set':
        actual=[m.get('xesam:title') for m in c.tracks()]
        assert sorted(actual)==sorted(spec['titles']),'generated collection membership differs'
        return sorted(actual)
    if kind=='player':
        data=c.mpris('Player','get_all');actual={}
        for k in spec['values']:actual[k]=data.get('Metadata',{}).get('xesam:title') if k=='title' else data.get(k)
        compare(actual,spec['values']);return actual
    if kind=='playlist-path-style':
        import media_semantics
        result=media_semantics.playlist_identity(c,spec['name'],spec['files'])
        entries=media_semantics.playlist_entries(c.take(spec['name']))
        relative=all(not urllib.parse.urlsplit(e).scheme and not e.startswith('/') for e in entries)
        absolute=all(e.startswith('/') or urllib.parse.urlsplit(e).scheme=='file' for e in entries)
        assert relative if spec['style']=='relative' else absolute,'playlist path style differs'
        return {'style':spec['style'],**result}
    if kind=='smart-names':
        names=[n['name'] for n in c.call(op='observe',tree=True).get('nodes',[]) if n['role']=='list item']
        if 'absent' in spec:assert spec['absent'] not in names
        return {'removed':spec['absent']}
    if kind=='playlists':
        count=c.get('PlaylistCount','Playlists')
        rows=c.method('GetPlaylists',0,100,'UserDefined',False,interface='Playlists')
        assert isinstance(rows,list) and len(rows)==count
        if 'count' in spec:assert count==spec['count']
        if 'names' in spec:assert sorted(r[1] for r in rows)==sorted(spec['names'])
        return {'count':count,'names':sorted(r[1] for r in rows)}
    if kind=='tags':
        import mutagen
        f=c.take(spec['file'],area=spec.get('area','inputs'))
        audio=mutagen.File(f,easy=True)
        assert audio is not None and audio.tags,'written audio has no readable tags'
        actual={k:list(audio.tags.get('description',audio.tags.get(k,[])) if k=='comment' else audio.tags.get(k,[])) for k in spec['values']}
        expected={k:[v] for k,v in spec['values'].items()}
        compare(actual,expected);return actual
    if kind=='playlist-file':
        import media_semantics
        return media_semantics.playlist_identity(c,spec['name'],spec['files'])
    raise ValueError(kind)


_base_observe=observe

def observe(c,spec):
    import media_semantics
    if spec['kind'] in ('embedded-cover','cover-file'):return media_semantics.cover_result(c,spec)
    if spec['kind']=='loudness':
        import fixtures
        source=fixtures.audio(spec['file'])
        result=subprocess.run(['ffmpeg','-hide_banner','-i',str(source),'-filter_complex','ebur128=peak=true','-f','null','-'],capture_output=True,text=True,timeout=60)
        expected=float(re.findall(r'I:\s*(-?\d+(?:\.\d+)?) LUFS',result.stderr)[-1])
        o=c.call(op='observe',tree=True);labels=[n for n in o['nodes'] if n['role']=='label']
        values=[float(m.group(1)) for n in labels for m in [re.search(r'(-?\d+(?:\.\d+)?)\s*LUFS',n.get('name',''))] if m]
        assert values,'no visible integrated loudness result'
        assert any(abs(v-expected)<1 for v in values),f'loudness differs from signal: {values}, expected {expected}'
        return {'loudness_lufs':round(values[0],1)}
    if spec['kind']=='organized':return media_semantics.verify_organized(c,spec)
    if spec['kind']!='audio':return _base_observe(c,spec)
    import fixtures
    output=c.take(spec['name'],seconds=60)
    return media_semantics.verify_audio(output,fixtures.audio(spec['source']),spec['codec'])
