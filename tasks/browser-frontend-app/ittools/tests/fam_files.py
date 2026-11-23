'''Program episodes: base64 file converter, QR code and WiFi QR code generators, SVG placeholder generator, RSA key pair generator.'''
import base64
import struct
import zlib

from pbuild import NL, bind, blocks, box, case, changed, choose, click, clip, controls, fields, fill, lines, multi, outs, point, remember, shape, switch, upload, wait, episode

DEFAULT = 'Open the page without typing.'
INPUTS = {'type': 'inputs'}
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412) + ' ' + chr(10003)
QUOTE = chr(34)
BS = chr(92)
FILES = {'files': ['memo.txt', 'sheet.pdf', 'tile.png']}


def download(*parts):
    return {'type': 'download', 'parts': list(parts)}


def b64(data):
    return base64.b64encode(data).decode()


def b64s(text):
    return b64(text.encode())


def png(width, height, rgb):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)

    raw = b''.join(bytes([0]) + bytes(rgb) * width for _ in range(height))
    head = bytes([137]) + b'PNG' + bytes([13, 10, 26, 10])
    return head + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


# -- Base64 file converter ------------------------------------------------------------------------------
B64_PAGE = '/base64-file-converter'
FILE_NAME, EXTENSION = 'File Name', 'Extension'
DROP = 'Drag and drop a file here, or click to select a file or Browse files'
PASTE = 'Put your base64 file string here...'
B64_FORM = multi(inputs=INPUTS, text=lines(skip=2))
SAVED = download('name', 'text')
SAVED_BIN = download('name', 'bytes', 'sha256')
SAVED_IMG = download('name', 'bytes', 'sha256', 'image')


def base64_file_converter():
    def convert(cid, goal, value, requirement, seen=SAVED, before=()):
        steps = list(before) + [fill(value, placeholder=PASTE), click('Download file')]
        return case(cid, goal, B64_PAGE, steps, [point('file', requirement, multi(file=seen, inputs=INPUTS))])

    def uploaded(cid, goal, name, mime, requirement, after=(), seen=None):
        steps = [click(DROP), upload(name, mime), wait(0.8)] + list(after)
        return case(cid, goal, B64_PAGE, steps, [point('base64', requirement, seen or multi(out=outs(allow_empty=True)))])

    shown = 'The file is saved under the name and extension the page works out.'
    rows = [
        ('plain-text', 'Paste the base64 of hello world and press Download file.', b64s('hello world'), shown, SAVED),
        ('data-text', 'Paste a text/plain data address.', 'data:text/plain;base64,' + b64s('hello'), shown, SAVED),
        ('data-json', 'Paste an application/json data address.', 'data:application/json;base64,' + b64s('{' + QUOTE + 'a' + QUOTE + ':1}'), shown, SAVED),
        ('data-csv', 'Paste a text/csv data address.', 'data:text/csv;base64,' + b64s('a,b' + NL + '1,2'), shown, SAVED),
        ('data-html', 'Paste a text/html data address.', 'data:text/html;base64,' + b64s('<p>hi</p>'), shown, SAVED),
        ('data-unknown', 'Paste a data address with a made-up type.', 'data:application/x-nothing;base64,' + b64s('x'), shown, SAVED),
        ('png', 'Paste a PNG image as a data address.', 'data:image/png;base64,' + b64(png(4, 3, (255, 128, 0))), shown, SAVED_IMG),
        ('pdf', 'Paste the start of a PDF file as a data address.', 'data:application/pdf;base64,' + b64s('%PDF-1.4' + NL + '%%EOF'), shown, SAVED_BIN),
        ('gif', 'Paste a GIF header as a data address.', 'data:image/gif;base64,' + b64(b'GIF89a' + bytes(10)), shown, SAVED_BIN),
        ('jpeg', 'Paste a JPEG header as a data address.', 'data:image/jpeg;base64,' + b64(bytes([255, 216, 255, 224]) + b'JFIF' + bytes(8)), shown, SAVED_BIN),
        ('unicode', 'Paste the base64 of a text with non-Latin characters.', b64s(UNI), shown, SAVED),
        ('long', 'Paste the base64 of 5000 letters.', b64s('x' * 5000), shown, SAVED_BIN),
        ('all-bytes', 'Paste the base64 of every byte value from 0 to 255.', b64(bytes(range(256))), shown, SAVED_BIN),
        ('spaces', 'Paste a base64 text with spaces around it.', ' ' + b64s('hello') + ' ', shown, SAVED),
    ]
    cases = [case('default', DEFAULT, B64_PAGE, [], [point('form', 'The page opens with the default file name and nothing to convert.', B64_FORM)])]
    cases += [convert(*row) for row in rows]
    for cid, goal, value in (('sig-png', 'Paste the bare base64 of a PNG image.', b64(png(4, 3, (255, 128, 0)))),
                             ('sig-pdf', 'Paste the bare base64 of the start of a PDF file.', b64s('%PDF-1.4' + NL + '%%EOF')),
                             ('sig-gif', 'Paste the bare base64 of a GIF header.', b64(b'GIF89a' + bytes(10)))):
        cases.append(case(cid, goal, B64_PAGE, [fill(value, placeholder=PASTE)],
                          [point('extension', 'The extension is filled in from the file type the base64 text starts with.', multi(inputs=INPUTS))]))

    named = [
        ('custom-name', 'Type the file name report and the extension csv.', 'report', 'csv'),
        ('name-has-extension', 'Type the file name report.csv and the extension csv.', 'report.csv', 'csv'),
        ('other-extension', 'Type the file name report.txt and the extension csv.', 'report.txt', 'csv'),
        ('dot-extension', 'Type the extension .md with a leading dot.', 'file', '.md'),
        ('name-only', 'Type the file name notes and leave the extension empty.', 'notes', ''),
        ('empty-name', 'Clear the file name and type the extension txt.', '', 'txt'),
        ('long-name', 'Type a file name of 100 letters and the extension txt.', 'n' * 100, 'txt'),
        ('name-with-space', 'Type the file name my report and the extension txt.', 'my report', 'txt'),
    ]
    for cid, goal, name, ext in named:
        cases.append(convert(cid, goal + ' Paste a text and press Download file.', b64s('a,b' + NL + '1,2'), 'The file name and the extension follow what was typed.', SAVED,
                             [fill(name, label=FILE_NAME), fill(ext, label=EXTENSION)]))
    for cid, goal, value in (('invalid', 'Paste text that is not base64.', '!!! not base64 !!!'), ('bad-length', 'Paste a base64 text cut to five characters.', 'aGVsb'), ('url-safe', 'Paste a base64 text written with url safe characters.', 'aGVsbG8_'),
                             ('data-bad', 'Paste a data address with invalid base64.', 'data:text/plain;base64,@@@@')):
        cases.append(case(cid, goal, B64_PAGE, [fill(value, placeholder=PASTE)],
                          [point('message', 'A text that is not base64 is flagged with a message.', B64_FORM, ['plain-text/file'])]))
    cases += [
        uploaded('upload-text', 'Choose the text file memo.txt.', 'memo.txt', 'text/plain', 'A chosen file is shown as a base64 data address.'),
        uploaded('upload-png', 'Choose the image file tile.png.', 'tile.png', 'image/png', 'A chosen image is shown as a base64 data address.'),
        uploaded('upload-pdf', 'Choose the document sheet.pdf.', 'sheet.pdf', 'application/pdf', 'A chosen document is shown as a base64 data address.'),
        uploaded('upload-no-type', 'Choose memo.txt with no known type.', 'memo.txt', 'application/octet-stream', 'A file with no known type is shown with a generic type.'),
        uploaded('upload-copy', 'Choose memo.txt and press Copy.', 'memo.txt', 'text/plain', 'Copy puts the base64 text on the clipboard.', [click('Copy')],
                 multi(out=outs(allow_empty=True), copied=clip())),
    ]
    wf = episode('base64-file-converter', 'converter', cases)
    wf['inputs'] = dict(FILES)
    return wf


# -- QR code generator ----------------------------------------------------------------------------------
QR_PAGE = '/qrcode-generator'
QR_TEXT = 'Text:'
GET_QR = 'Download qr-code'
QR_FILE = download('name', 'sha256', 'image')


def qr_code_generator():
    def make(cid, goal, steps, requirement):
        full = list(steps) + [wait(1.0), click(GET_QR)]
        return case(cid, goal, QR_PAGE, full, [point('png', requirement, multi(file=QR_FILE, input=fields(QR_TEXT)))])

    def text(value):
        return [fill(value, label=QR_TEXT)]

    same = 'Each text gives its own QR code image.'
    level = 'https://example.org/level'
    cases = [make('default', DEFAULT, [], 'The page opens with the QR code of the example address.')]
    for cid, goal, value in (
        ('short', 'Type a.', 'a'), ('words', 'Type hello world.', 'hello world'),
        ('address', 'Type a web address with a query.', 'https://example.org/path?a=1&b=2#top'),
        ('digits', 'Type ten digits.', '0123456789'), ('capitals', 'Type HELLO WORLD.', 'HELLO WORLD'),
        ('unicode', 'Type non-Latin text.', UNI), ('lines', 'Type two lines.', 'one' + NL + 'two'),
        ('long', 'Type 300 letters.', 'abcdefghij' * 30), ('very-long', 'Type 1200 letters.', 'abcdefghij' * 120),
    ):
        cases.append(make(cid, goal, text(value), same))
    cases.append(make('spaces', 'Type hello world with spaces around it.', text('  hello world  '), 'Spaces around the text are ignored.'))
    for name, option in (('low', 'low'), ('quartile', 'quartile'), ('high', 'high')):
        cases.append(make('level-' + name, 'Choose the error resistance %s and type an address.' % option, [choose('medium', option)] + text(level), 'The error resistance changes the image.'))
    cases.append(make('level-medium', 'Type an address with the default error resistance.', text(level), 'The default error resistance is medium.'))
    cases.append(make('level-low-long', 'Choose the error resistance low and type 2000 letters.', [choose('medium', 'low')] + text('abcdefghij' * 200), 'A long text fits at the lowest error resistance.'))
    cases.append(make('level-high-long', 'Choose the error resistance high and type 500 letters.', [choose('medium', 'high')] + text('abcdefghij' * 50), 'A long text fits at the highest error resistance.'))
    cases.append(make('too-long', 'Choose the error resistance high and type 2000 letters.', [choose('medium', 'high')] + text('abcdefghij' * 200), 'A text too long for the code leaves the earlier image in place.'))
    cases.append(make('cleared', 'Clear the text.', text(''), 'Clearing the text leaves the earlier image in place.'))
    return episode('qr-code-generator', 'generator', bind(cases, {'too-long': 'short/png', 'cleared': 'short/png'}))


# -- WiFi QR code generator -----------------------------------------------------------------------------
WIFI_PAGE = '/wifi-qrcode-generator'
SSID, PASSWORD, ENC = 'SSID:', 'Password:', 'WPA/WPA2'
SELECT = 'Select an option'
WIFI_FILE = multi(file=QR_FILE, inputs=INPUTS)
WIFI_NONE = multi(inputs=INPUTS, button=controls(area='any', prefix='Download', count_only=True), text=lines(skip=2))


def wifi_qr_code_generator():
    def made(cid, goal, steps, requirement):
        return case(cid, goal, WIFI_PAGE, list(steps) + [wait(1.0), click(GET_QR)], [point('png', requirement, WIFI_FILE)])

    def absent(cid, goal, steps, requirement):
        return case(cid, goal, WIFI_PAGE, list(steps) + [wait(1.0)], [point('page', requirement, WIFI_NONE)])

    def home(password='hunter2'):
        return [fill('HomeNet', label=SSID), fill(password, label=PASSWORD)]

    def eap(method=None, phase2=None, identity=None, anonymous=False):
        steps = [choose(ENC, 'WPA2-EAP'), fill('HomeNet', label=SSID), fill('hunter2', label=PASSWORD)]
        if method:
            steps.append(choose(SELECT, method, search=method))
            if phase2:
                steps.append(choose(SELECT, phase2, search=phase2))
        if identity:
            steps.append(fill(identity, label='Identity:'))
        if anonymous:
            steps.append(box(1))
        return steps

    cases = [
        absent('default', DEFAULT, [], 'The page opens with no QR code and no download button.'),
        made('wpa', 'Type the SSID HomeNet and the password hunter2.', home(), 'A WPA network gives a QR code that can be saved.'),
        made('wpa-other', 'Type another SSID and password.', [fill('Guest-5G', label=SSID), fill('correct horse battery staple', label=PASSWORD)], 'Another network gives another QR code.'),
        made('wpa-hidden', 'Type the SSID and password and tick Hidden SSID.', home() + [box(0)], 'A hidden network gives another QR code.'),
        made('wpa-special', 'Type an SSID and password with semicolons, commas, colons, a quote and a backslash.',
             [fill('a;b,c:d' + QUOTE + 'e' + BS + 'f', label=SSID), fill('p;w,d:' + QUOTE + BS, label=PASSWORD)], 'Special characters are escaped inside the QR code.'),
        made('wpa-unicode', 'Type an SSID with non-Latin characters.', home() [:0] + [fill(UNI, label=SSID), fill('hunter2', label=PASSWORD)], 'Non-Latin characters are encoded in the QR code.'),
        made('wpa-long', 'Type a password of 60 letters.', home('p' * 60), 'A long password gives a bigger QR code.'),
        absent('wpa-no-password', 'Type only the SSID.', [fill('HomeNet', label=SSID)], 'A WPA network with no password gives no QR code.'),
        absent('no-ssid', 'Type only the password.', [fill('hunter2', label=PASSWORD)], 'A password with no SSID gives no QR code.'),
        made('nopass', 'Choose No password and type the SSID.', [choose(ENC, 'No password'), fill('OpenNet', label=SSID)], 'An open network gives a QR code without a password.'),
        made('nopass-hidden', 'Choose No password, type the SSID and tick Hidden SSID.', [choose(ENC, 'No password'), fill('OpenNet', label=SSID), box(0)], 'The hidden flag does not change an open network code.'),
        made('wep', 'Choose WEP and type the SSID and password.', [choose(ENC, 'WEP')] + home(), 'A WEP network gives its own QR code.'),
        made('wep-hidden', 'Choose WEP, type the SSID and password and tick Hidden SSID.', [choose(ENC, 'WEP')] + home() + [box(0)], 'A hidden WEP network gives its own QR code.'),
        made('eap-md5', 'Choose WPA2-EAP, the method MD5 and an identity.', eap('MD5', None, 'user@example.org'), 'An EAP network with a method gives a QR code.'),
        made('eap-tls', 'Choose WPA2-EAP, the method TLS and an identity.', eap('TLS', None, 'user@example.org'), 'The EAP method changes the QR code.'),
        made('eap-phase2', 'Choose WPA2-EAP, the method PEAP, the phase 2 method MSCHAPV2 and an identity.', eap('PEAP', 'MSCHAPV2', 'user@example.org'), 'The phase 2 method changes the QR code.'),
        made('eap-phase2-none', 'Choose WPA2-EAP, the method PEAP, the phase 2 method None and an identity.', eap('PEAP', 'None', 'user@example.org'), 'The phase 2 method None changes the QR code.'),
        made('eap-anonymous', 'Choose WPA2-EAP, the method TTLS and tick Anonymous.', eap('TTLS', None, 'user@example.org', True), 'Anonymous replaces the identity in the QR code.'),
        made('eap-hidden', 'Choose WPA2-EAP, the method TLS, an identity and tick Hidden SSID.', eap('TLS', None, 'user@example.org') + [box(0)], 'A hidden EAP network gives its own QR code.'),
        absent('eap-no-method', 'Choose WPA2-EAP and type the SSID and password but no method.', eap(), 'An EAP network with no method gives no QR code.'),
    ]
    return episode('wifi-qr-code-generator', 'generator', bind(cases, {'wpa-no-password': 'wpa/png', 'no-ssid': 'wpa/png', 'eap-no-method': 'wpa/png'}))


# -- SVG placeholder generator --------------------------------------------------------------------------
SVG_PAGE = '/svg-placeholder-generator'
WIDTH, HEIGHT, FONT, CUSTOM = 'SVG width...', 'SVG height...', 'Font size...', 'Custom text'
SVG_SEEN = multi(inputs=INPUTS, svg=blocks())
SVG_FILE = multi(file=download('name', 'text'))


def svg_placeholder_generator():
    def one(cid, goal, steps, requirement, seen=SVG_SEEN):
        return case(cid, goal, SVG_PAGE, steps, [point('svg', requirement, seen)])

    def size(w, h):
        return [fill(str(w), placeholder=WIDTH), fill(str(h), placeholder=HEIGHT)]

    shown = 'The SVG element and its base64 form follow the settings.'
    cases = [one('default', DEFAULT, [], 'The page opens with a 600 by 350 placeholder.')]
    for cid, goal, steps in (
        ('square', 'Set the size to 100 by 100.', size(100, 100)),
        ('tiny', 'Set the size to 1 by 1.', size(1, 1)),
        ('large', 'Set the size to 4000 by 3000.', size(4000, 3000)),
        ('wide', 'Set the size to 1200 by 100.', size(1200, 100)),
        ('font-small', 'Set the font size to 8.', [fill('8', placeholder=FONT)]),
        ('font-large', 'Set the font size to 120.', [fill('120', placeholder=FONT)]),
        ('text', 'Type the custom text Hello.', [fill('Hello', label=CUSTOM)]),
        ('text-unicode', 'Type a custom text with non-Latin characters.', [fill(UNI, label=CUSTOM)]),
        ('text-markup', 'Type a custom text with angle brackets.', [fill('<b>bold</b>', label=CUSTOM)]),
        ('text-ampersand', 'Type a custom text with an ampersand and quotes.', [fill('Tom & Jerry ' + QUOTE + 'show' + QUOTE, label=CUSTOM)]),
        ('text-spaces', 'Type a custom text of three spaces.', [fill('   ', label=CUSTOM)]),
        ('text-long', 'Type a custom text of 200 letters.', [fill('w' * 200, label=CUSTOM)]),
        ('text-and-size', 'Set 300 by 200 and the text Banner.', size(300, 200) + [fill('Banner', label=CUSTOM)]),
        ('text-cleared', 'Type a custom text and clear it again.', [fill('Hello', label=CUSTOM), fill('', label=CUSTOM)]),
        ('exact-off', 'Turn off Use exact size.', [switch(0)]),
        ('exact-off-size', 'Set 320 by 240 and turn off Use exact size.', size(320, 240) + [switch(0)]),
        ('exact-toggled', 'Turn Use exact size off and on again.', [switch(0), switch(0)]),
        ('all', 'Set 500 by 500, font size 30, the text Square and turn off Use exact size.', size(500, 500) + [fill('30', placeholder=FONT), fill('Square', label=CUSTOM), switch(0)]),
        ('decimal', 'Type 10.5 as the width.', [fill('10.5', placeholder=WIDTH)]),
        ('zero', 'Type 0 as the width.', [fill('0', placeholder=WIDTH)]),
        ('negative', 'Type -5 as the height.', [fill('-5', placeholder=HEIGHT)]),
        ('empty-width', 'Clear the width.', [fill('', placeholder=WIDTH)]),
        ('huge', 'Type 99999 as both the width and the height.', size(99999, 99999)),
    ):
        cases.append(one(cid, goal, steps, shown))
    cases += [
        one('copy-svg', 'Type the text Hello and press Copy svg.', [fill('Hello', label=CUSTOM), click('Copy svg')], 'Copy svg puts the SVG element on the clipboard.', multi(copied=clip())),
        one('copy-base64', 'Type the text Hello and press Copy base64.', [fill('Hello', label=CUSTOM), click('Copy base64')], 'Copy base64 puts the data address on the clipboard.', multi(copied=clip())),
        one('download', 'Press Download svg.', [click('Download svg')], 'The SVG is saved as a file.', SVG_FILE),
        one('download-custom', 'Set 200 by 100, the text Card and press Download svg.', size(200, 100) + [fill('Card', label=CUSTOM), click('Download svg')], 'The saved file follows the settings.', SVG_FILE),
        one('download-inexact', 'Turn off Use exact size and press Download svg.', [switch(0), click('Download svg')], 'The saved file has no fixed size.', SVG_FILE),
    ]
    return episode('svg-placeholder-generator', 'generator', bind(cases, {'text-cleared': 'text/svg', 'zero': 'square/svg', 'negative': 'square/svg', 'exact-toggled': 'exact-off/svg'}))


# -- RSA key pair generator -----------------------------------------------------------------------------
RSA_PAGE = '/rsa-key-pair-generator'
BITS = 'Please Input'
BASE = '[A-Za-z0-9+/]'
EOL = '(?:' + chr(13) + '?' + chr(10) + ')'


def pem(kind):
    return '-----BEGIN ' + kind + '-----' + EOL + '(?:' + BASE + '{1,64}={0,2}' + EOL + ')+-----END ' + kind + '-----' + BS + 's*'


RSA_PUBLIC = {'from': 'block', 'index': 0}


def rsa_key_pair_generator():
    keys = multi(bits=INPUTS, public=shape('block', index=0, patterns={'pem': pem('PUBLIC KEY')}),
                 private=shape('block', index=1, patterns={'pem': pem('RSA PRIVATE KEY')}, only_patterns=True))

    def made(cid, goal, steps, requirement, pause):
        return case(cid, goal, RSA_PAGE, list(steps) + [wait(pause)], [point('keys', requirement, keys)])

    cases = [
        made('default', DEFAULT, [], 'The page opens with a 2048 bit key pair in PEM form.', 15),
        made('bits-1024', 'Set the bits to 1024.', [fill('1024', placeholder=BITS)], 'A 1024 bit pair is shorter than the default.', 8),
        made('bits-512', 'Set the bits to 512.', [fill('512', placeholder=BITS)], 'A 512 bit pair is shorter still.', 5),
        made('bits-768', 'Set the bits to 768.', [fill('768', placeholder=BITS)], 'A 768 bit pair sits between the 512 and the 1024 bit sizes.', 6),
        case('refresh', 'Set the bits to 1024 and press Refresh key-pair.', RSA_PAGE,
             [fill('1024', placeholder=BITS), wait(8), remember(RSA_PUBLIC), click('Refresh key-pair'), wait(8)],
             [point('keys', 'Refresh makes a new pair of the same size.', multi(keys=keys, changed=changed(RSA_PUBLIC)))]),
    ]
    for cid, goal, value in (('bits-255', 'Set the bits to 255.', '255'), ('bits-300', 'Set the bits to 300.', '300'), ('bits-100', 'Set the bits to 100.', '100'), ('bits-empty', 'Clear the bits.', '')):
        cases.append(case(cid, goal, RSA_PAGE, [fill(value, placeholder=BITS), wait(3)],
                          [point('message', 'A number of bits that is out of range or not a multiple of eight is flagged with a message.', multi(bits=INPUTS, text=lines(skip=2)))]))
    return episode('rsa-key-pair-generator', 'generator', bind(cases, {'bits-255': 'bits-1024/keys', 'bits-300': 'bits-1024/keys', 'bits-100': 'bits-1024/keys', 'bits-empty': 'bits-1024/keys'}))


def build():
    return [base64_file_converter(), qr_code_generator(), wifi_qr_code_generator(), svg_placeholder_generator(), rsa_key_pair_generator()]
