"""Small input documents authored for normal product file exchange."""
import base64


def manual_pdf():
    stream=b'BT /F1 16 Tf 40 740 Td (Mixer instruction manual) Tj 0 -30 Td (Use speed 2 for bread dough.) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    out=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(out));out+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start=len(out);out+=b'xref\n0 6\n0000000000 65535 f \n'
    out+=b''.join(f'{x:010d} 00000 n \n'.encode() for x in offsets[1:])
    out+=b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF\n'
    return out

MANUAL_BASE64=base64.b64encode(manual_pdf()).decode()
