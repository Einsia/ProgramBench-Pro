"""Deterministic small documents generated locally; no upstream content."""
import io, json, struct, zlib, zipfile
from xml.sax.saxutils import escape

SERIES = ['Atlas', 'Beacon', 'Café 漫画', 'Delta', 'Evergreen', 'Folio']
COLORS = [(210,45,55),(25,110,210),(25,165,95),(165,70,200),(230,150,30),(35,160,170)]


def png(index=0,page=1,width=360,height=480):
    color=COLORS[index%len(COLORS)]
    rows=[]
    for y in range(height):
        row=bytearray()
        for x in range(width):
            c=color
            if x<12 or x>=width-12 or y<12 or y>=height-12:c=(24,30,40)
            if 30<y<70 and 30<x<min(width-30,30+page*50):c=(245,245,220)
            if height//3<y<height*2//3 and width//3<x<width*2//3:c=tuple(max(0,v-50) for v in color)
            row.extend(c)
        rows.append(b'\0'+row)
    def chunk(t,b):return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b'')


def archive(entries):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries:
            i=zipfile.ZipInfo(name,(2024,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16
            z.writestr(i,data)
    return b.getvalue()


def cbz(series=0,number=1,pages=4,metadata=True):
    entries=[(f'{p:03}.png',png(series,p)) for p in range(1,pages+1)]
    if metadata:
        values={'Series':SERIES[series],'Title':f'{SERIES[series]} chapter {number}','Number':str(number),'Count':'3',
                'Summary':f'Adventure {number} in {SERIES[series]}. Café Ω.', 'Year':str(2020+series),'Month':str(number),'Day':'15',
                'Writer':['Ada Rivers','Boris Stone','Chloé 林'][series%3], 'Penciller':'Dana Ink',
                'Publisher':['North Press','South Press'][series%2], 'Genre':['Adventure','Fantasy','History'][series%3],
                'Tags':f'volume-{number}, '+['bright','dark'][series%2], 'LanguageISO':['en','fr','ja'][series%3],
                'AgeRating':['Everyone','Teen','Mature 17+'][series%3], 'Web':'https://example.test/comic/'+str(series),
                'Manga':'YesAndRightToLeft' if series==2 else 'No','SeriesGroup':'Shared World' if series<2 else 'Other Worlds',
                'StoryArc':'Opening arc' if number==1 else 'Later arc','StoryArcNumber':str(series*3+number)}
        xml='<ComicInfo>'+''.join('<'+k+'>'+escape(v)+'</'+k+'>' for k,v in values.items())+'</ComicInfo>'
        entries.append(('ComicInfo.xml',xml.encode()))
    return archive(entries)


def epub():
    opf='''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">urn:uuid:00000000-0000-4000-8000-000000000123</dc:identifier><dc:title>Harbor Journal</dc:title><dc:creator>Elena Writer</dc:creator><dc:language>en</dc:language><dc:publisher>Harbor Press</dc:publisher><dc:description>A journal across three harbors.</dc:description><dc:date>2023-04-05</dc:date><meta property="dcterms:modified">2024-01-01T00:00:00Z</meta></metadata>
<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="cover" href="cover.png" media-type="image/png" properties="cover-image"/>'''+''.join(f'<item id="c{i}" href="chapter{i}.xhtml" media-type="application/xhtml+xml"/>' for i in range(1,4))+'''</manifest><spine>'''+''.join(f'<itemref idref="c{i}"/>' for i in range(1,4))+'</spine></package>'
    entries=[('mimetype',b'application/epub+zip'),('META-INF/container.xml',b'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'),('OEBPS/content.opf',opf.encode()),('OEBPS/cover.png',png(3))]
    entries.append(('OEBPS/nav.xhtml',('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body><nav epub:type="toc"><h1>Contents</h1><ol>'+''.join(f'<li><a href="chapter{i}.xhtml">Harbor {i}</a></li>' for i in range(1,4))+'</ol></nav></body></html>').encode()))
    for i in range(1,4):
        text=f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Harbor {i}</title></head><body><h1>Harbor {i}</h1><p>Chapter {i}: The sailors arrive in the quiet harbor. The morning light crosses the blue water.</p>'+''.join(f'<p>Journal entry {n}: Reading connects these distant places with stories and memories.</p>' for n in range(24))+'</body></html>'
        entries.append((f'OEBPS/chapter{i}.xhtml',text.encode()))
    return archive(entries)


def pdf():
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>']
    for i in range(2):
        stream=(f'0.{i+2} 0.4 0.7 rg 20 20 320 440 re f 1 0.85 0.1 rg 45 65 110 95 re f 0.8 0.1 0.15 rg 190 200 105 110 re f 0 0 0 RG 8 w 30 30 300 420 re S 0 0 0 rg BT /F1 22 Tf 40 400 Td (Vector page {i+1}) Tj ET').encode()
        objects += [f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 360 480] /Resources << /Font << /F1 7 0 R >> >> /Contents {4+i*2} 0 R >>'.encode(),b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    b=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,o in enumerate(objects,1):offsets.append(len(b));b.extend(f'{i} 0 obj\n'.encode()+o+b'\nendobj\n')
    start=len(b);b.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for off in offsets[1:]:b.extend(f'{off:010} 00000 n \n'.encode())
    b.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode());return bytes(b)


def rar():
    """Small RAR 4 archive using the stored method; entries are our own generated assets."""
    def header(kind,flags,body):
        core=struct.pack('<BHH',kind,flags,7+len(body))+body
        return struct.pack('<H',zlib.crc32(core)&0xffff)+core
    output=bytearray(b'Rar!\x1a\x07\x00'+header(0x73,0,b'\0'*6))
    with zipfile.ZipFile(io.BytesIO(cbz(4,1))) as z:
        for name in z.namelist():
            data=z.read(name);name=name.encode()
            body=struct.pack('<IIBIIBBHI',len(data),len(data),3,zlib.crc32(data)&0xffffffff,0x58210000,20,0x30,len(name),0o100644)+name
            output+=header(0x74,0x8000,body)+data
    output+=header(0x7b,0,b'')
    return bytes(output)
