"""Decode public image exports and inspect their rendered text, without depending on diagram layout or PDF objects."""
import io
import re
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageOps


def raster_svg(data):
    # Parsing rejects truncated markup. A browser renderer handles drawDB's SVG foreignObject labels as well
    # as equivalent SVG text/path implementations. No document code or external resource is allowed to run.
    try:
        root = ET.fromstring(data)
        assert root.tag.rsplit('}', 1)[-1] == 'svg'
    except (ET.ParseError, AssertionError):
        raise AssertionError('the SVG export is not a complete SVG document') from None
    from playwright.sync_api import sync_playwright
    markup = data.decode('utf-8')
    markup = re.sub(r'<\?xml[^>]*\?>', '', markup)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        try:
            page = browser.new_page(viewport={'width': 1600, 'height': 1200}, java_script_enabled=False)
            page.route('**/*', lambda route: route.abort())
            page.set_content('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
                             'img-src data:; style-src \'unsafe-inline\'; font-src data:">' +
                             '<style>html,body{margin:0;background:white}svg{max-width:4000px;max-height:4000px}</style>' +
                             markup, wait_until='load')
            data = page.locator('svg').first.screenshot(timeout=15000, animations='disabled')
        finally:
            browser.close()
    return Image.open(io.BytesIO(data)).convert('RGB')


def decoded(data):
    if data.startswith(b'%PDF'):
        import pymupdf
        try:
            with pymupdf.open(stream=data, filetype='pdf') as doc:
                if not 1 <= len(doc) <= 32 or doc.is_encrypted:
                    raise AssertionError('the PDF has no readable pages')
                images = []
                for page in doc:
                    scale = min(3.0, 3000 / max(page.rect.width, page.rect.height))
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                    images.append(Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB'))
                return 'pdf', images
        except Exception as exc:
            raise AssertionError('the PDF export cannot be decoded: ' + str(exc)[:100]) from None
    if b'<svg' in data[:4096]:
        return 'svg', [raster_svg(data)]
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ('PNG', 'JPEG') or image.width * image.height > 40_000_000:
                raise AssertionError('unsupported or oversized raster image')
            image.load()
            return image.format.lower(), [image.convert('RGB')]
    except Exception as exc:
        raise AssertionError('the image export cannot be decoded: ' + str(exc)[:100]) from None


def text_of(image):
    if min(image.size) < 8:
        return ''
    # Render at a readable resolution. Text matching ignores antialiasing, colour and positions.
    scale = min(3, max(1, 2200 / max(image.size)))
    size = tuple(max(1, round(x * scale)) for x in image.size)
    image = image.resize(size, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format='PNG')
    chunks = []
    for mode in (11, 6):
        try:
            result = subprocess.run(['tesseract', 'stdin', 'stdout', '-l', 'eng', '--psm', str(mode)],
                                    input=output.getvalue(), capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            raise AssertionError('exported image text could not be read within the decoding limit') from None
        if result.returncode:
            raise AssertionError('exported image text could not be decoded')
        chunks.append(result.stdout.decode('utf-8', 'replace'))
    return '\n'.join(chunks)


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def inspect(data, required, absent=()):
    if not required:
        raise ValueError('image checks must name diagram content to observe')
    fmt, images = decoded(data)
    content = '\n'.join(text_of(image) for image in images)
    words = normalized(content)
    if not all(normalized(value) in words for value in required):
        raise AssertionError('the rendered export does not show the required diagram text: ' + repr(content[:1600]))
    if any(normalized(value) in words for value in absent):
        raise AssertionError('the rendered export shows content that should be hidden')
    return {'format': fmt, 'content': {value: normalized(value) in words for value in required},
            'absent': {value: normalized(value) not in words for value in absent}}
