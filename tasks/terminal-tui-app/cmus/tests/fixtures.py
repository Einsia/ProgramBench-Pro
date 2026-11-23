"""Deterministic FLAC test media with independently authored metadata and optional sample levels."""
import base64
import hashlib
import struct


def crc(data,bits,poly):
    v=0
    for b in data:
        v^=b<<(bits-8)
        for _ in range(8):v=((v<<1)^poly) if v&(1<<(bits-1)) else (v<<1)
        v&=(1<<bits)-1
    return v


def flac(tags,seconds=180,rate=8000,pattern=(0,)):
    count=seconds*rate
    pcm=b''.join(struct.pack('<h',pattern[i%len(pattern)])*min(4096,count-start) for i,start in enumerate(range(0,count,4096)))
    si=struct.pack('>HH',4096,4096)+bytes(6)+((rate<<44)|(15<<36)|count).to_bytes(8,'big')+hashlib.md5(pcm).digest()
    comments=[(k.upper()+'='+str(v)).encode() for k,v in tags.items()]
    vc=struct.pack('<I',10)+b'Fixture v1'+struct.pack('<I',len(comments))+b''.join(struct.pack('<I',len(x))+x for x in comments)
    out=b'fLaC'+b'\x00'+len(si).to_bytes(3,'big')+si+b'\x84'+len(vc).to_bytes(3,'big')+vc
    for i,start in enumerate(range(0,count,4096)):
        size=min(4096,count-start)
        h=b'\xff\xf8\x74\x08'+chr(i).encode()+struct.pack('>H',size-1)
        frame=h+bytes([crc(h,8,0x07)])+b'\x00'+struct.pack('>h',pattern[i%len(pattern)])
        out+=frame+struct.pack('>H',crc(frame,16,0x8005))
    return out

TRACKS=[
 ('amber.flac',{'artist':'Aster','albumartist':'Aster','album':'Dawn','title':'Amber','genre':'Jazz','date':'1998','originaldate':'1995','discnumber':'1','tracknumber':'2','comment':'warm piano','bpm':'90'},181),
 ('breeze.flac',{'artist':'Aster','albumartist':'Aster','album':'Dawn','title':'Breeze','genre':'Jazz','date':'1998','originaldate':'1995','discnumber':'1','tracknumber':'1','comment':'quiet morning','bpm':'75'},120),
 ('cobalt.flac',{'artist':'Birch','albumartist':'Birch','album':'Night','title':'Cobalt','genre':'Rock','date':'2005','originaldate':'2000','discnumber':'2','tracknumber':'3','comment':'electric live','bpm':'140'},240),
 ('delta.flac',{'artist':'Birch','albumartist':'Birch','album':'Night','title':'Delta','genre':'Rock','date':'2005','originaldate':'2000','discnumber':'1','tracknumber':'1','comment':'electric studio','bpm':'110'},60),
 ('echo.flac',{'artist':'Cedar','albumartist':'Cedar','album':'River','title':'Echo','genre':'Folk','date':'2021','originaldate':'2010','discnumber':'1','tracknumber':'4','comment':'acoustic guitar','bpm':'100'},299),
 ('fable.flac',{'artist':'Cedar','albumartist':'Cedar','album':'River','title':'Fable','genre':'Folk','date':'2021','originaldate':'2010','discnumber':'2','tracknumber':'1','comment':'acoustic live','bpm':'60'},90),
 ('garden.flac',{'artist':'The Dunes','albumartist':'The Dunes','album':'Sand','title':'Garden','genre':'Ambient','date':'2014','discnumber':'1','tracknumber':'1','bpm':'50','artistsort':'Dunes'},321),
 ('horizon.flac',{'artist':'Elm','albumartist':'Various Artists','album':'Gathering','title':'Horizon','genre':'Pop','date':'2019','discnumber':'1','tracknumber':'2','compilation':'1'},200),
 ('island.flac',{'artist':'Fern','albumartist':'Various Artists','album':'Gathering','title':'Island','genre':'Pop','date':'2019','discnumber':'1','tracknumber':'1','compilation':'1'},199),
 ('jade.flac',{'artist':'Étoile','albumartist':'Étoile','album':'Éclat','title':'Jade été','genre':'Classical','date':'1980','originaldate':'1900','discnumber':'3','tracknumber':'12','comment':'été calme'},180),
 ('koto space.flac',{'artist':'空','albumartist':'空','album':'星','title':'光','genre':'World','date':'2023','discnumber':'1','tracknumber':'7','comment':'日本語'},121),
 ('untagged.flac',{},45),
]
# One rich track exercises every public metadata key without depending on a reference implementation.
RICH={'artist':'Aurora Ensemble','albumartist':'Aurora Collective','album':'Glass Maps','title':'North Window','genre':'Chamber','comment':'Recorded in the blue room','date':'2016-02-14','originaldate':'1991-10-12','discnumber':'2/3','disctotal':'3','tracknumber':'7/12','tracktotal':'12','bpm':'123','composer':'Mira Vale','conductor':'Niko Reed','performer':'Elena Fox','arranger':'Sana Hill','lyricist':'Oren Lake','remixer':'Tess Moon','label':'Small Room','publisher':'Open Scores','work':'Glass Suite','opus':'Op. 42','partnumber':'3','part':'Adagio','subtitle':'Second light','media':'Vinyl','replaygain_track_gain':'-4.00 dB','replaygain_track_peak':'0.8','replaygain_album_gain':'-6.00 dB','replaygain_album_peak':'0.9'}


def fixture_files():
    return [{'filename':name,'base64':base64.b64encode(flac(tags,duration)).decode(),'mtime':1704067200+i*60} for i,(name,tags,duration) in enumerate(TRACKS)]


def wav(seconds=1,rate=8000,channels=1,bits=16):
    data=bytes(int(seconds*rate)*channels*(bits//8))
    return b'RIFF'+struct.pack('<I',36+len(data))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,channels,rate,rate*channels*bits//8,channels*bits//8,bits)+b'data'+struct.pack('<I',len(data))+data
