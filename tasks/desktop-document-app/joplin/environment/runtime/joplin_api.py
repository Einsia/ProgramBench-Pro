"""Bounded access to the product's local Data API; no emulated product endpoints."""
import blackbox_runtime as runtime
import base64
import html
import http.client
import io
import json
import re
import secrets
import tarfile
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

TOKEN = 'joplin-local-data-api'
MAX_BODY = 20 * 1024 * 1024
TEXT_TYPES = {'.txt', '.md', '.markdown', '.html', '.htm', '.enex', '.json', '.csv', '.css', '.svg'}


class Refused(ValueError):
    """The request is outside the interface boundary."""


def safe_document(value):
    """Disallow active content and references to files outside the document exchange.

    Joplin's clipping API can import local media and external style sheets. These
    are not needed for local documents; bytes can be supplied as resources or
    data URLs. Inspect escaped representations as well as literal strings.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('id', 'parent_id', 'item_id', 'resource_id', 'file_extension', 'filename') and isinstance(item, str):
                if '/' in item or '\\' in item or item in ('.', '..') or any(ord(c) < 32 for c in item):
                    raise Refused('resource identifiers and file properties must be plain names')
            if key in ('base_url', 'css', 'image_data_url', 'body', 'body_html', 'source_url', 'props'):
                safe_document(item)
            if key == 'stylesheets' and item:
                raise Refused('external style sheets are not available')
    elif isinstance(value, (list, tuple)):
        for item in value:
            safe_document(item)
    elif isinstance(value, str):
        text = value
        for _ in range(4):
            decoded = html.unescape(unquote(text))
            if decoded == text:
                break
            text = decoded
        flat = re.sub(r'[\x00-\x20]', '', text).casefold()
        if re.search(r'(?:file|javascript|vbscript|vscode|shell):', flat):
            raise Refused('local-file and executable URLs are not available')
        if re.search(r'<\s*(?:script|iframe|object|embed)\b|<!ENTITY\b|\bon[a-z]+\s*=', text, re.I):
            raise Refused('active embedded content is not available')
        for match in re.finditer(r'```jsoncanvas[^\n]*\n(.*?)\n```', text, re.I | re.S):
            try:
                canvas = runtime.strict_json_loads(match[1])
            except ValueError:
                continue  # Malformed documents remain product inputs.
            if not isinstance(canvas, dict) or not isinstance(canvas.get('nodes'), list):
                continue
            for node in canvas['nodes']:
                if not isinstance(node, dict):
                    continue
                for key in ('url', 'file'):
                    if key in node and (not isinstance(node[key], str) or
                                        not re.fullmatch(r':/[A-Za-z0-9_-]+', node[key])):
                        raise Refused('whiteboard references must name an internal note or resource')
                if isinstance(node.get('text'), str):
                    safe_document(node['text'])
        # Local markdown images and HTML media can otherwise make the clipper
        # read files or fetch remote content. Joplin :/resource links are safe.
        media = re.findall(r'!\[[^\]]*\]\(\s*([^\s)]+)', text)
        media += re.findall(r'<(?:img|audio|video|source|link)\b[^>]*?\b(?:src|href)\s*=\s*[\x22\x27]?([^\s\x22\x27>]+)', text, re.I)
        if any(not url.startswith(('data:', ':/')) for url in media):
            raise Refused('embedded media must be supplied as data URLs or product resource links')


def check_file(name, content):
    suffix = '.' + name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if suffix in TEXT_TYPES:
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            # Legacy text encodings are still data; inspect their ASCII portion.
            text = content.decode('latin1')
        safe_document(text)
        # RAW/JEX metadata is a public serialized document format. Its path-like
        # identity fields must obey the same boundary as API-created resources.
        marker = re.search(r'\n\nid: ', text)
        if marker:
            metadata = dict(re.findall(r'^([a-z_]+): ?(.*)$', text[marker.start()+2:], re.M))
            safe_document({k:v for k,v in metadata.items() if k in
                           ('id','parent_id','item_id','resource_id','file_extension','filename')})
    if suffix == '.jex':
        try:
            with tarfile.open(fileobj=io.BytesIO(content)) as archive:
                total = 0
                for item in archive:
                    total += item.size
                    if total > MAX_BODY or item.name.startswith('/') or '..' in item.name.split('/'):
                        raise Refused('the import archive exceeds the document boundary')
                    if not item.isfile() and not item.isdir():
                        raise Refused('import archives may contain ordinary documents and folders only')
                    if item.isfile() and item.name.lower().endswith(('.md', '.html', '.txt', '.json')):
                        check_file(item.name, archive.extractfile(item).read())
        except tarfile.TarError:
            pass  # An invalid document remains a valid product input.


SPEC = {'kind': 'http', 'summary': 'Request the local Joplin Data API (Web Clipper service) at PORT. Paths begin '
        'with /ping, /notes, /folders, /tags, /resources, /search, /events, /revisions or /master_keys. The response '
        'contains status, content_type, JSON or text body, and exact body_base64 for binary data. No redirects '
        'are followed. The runtime adds the configured token unless auth is false or token is supplied.',
        'fields': {
            'method': {'type': 'string', 'enum': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'],
                       'description': 'HTTP method, default GET.'},
            'path': {'type': 'string', 'required': True, 'description': 'API path including optional query string.'},
            'query': {'type': 'object', 'description': 'Additional query parameters; scalar values or lists.'},
            'json': {'type': 'object', 'description': 'JSON request object.'},
            'body': {'type': 'string', 'description': 'Raw UTF-8 body, mutually exclusive with json and multipart.'},
            'content_type': {'type': 'string', 'description': 'Raw body content type; default application/json.'},
            'multipart': {'type': 'object', 'description': 'Resource upload: filename (base name), base64 (bytes), '
                          'optional content_type, props (JSON object). Sent as data and props form parts.'},
            'auth': {'type': 'boolean', 'description': 'Attach the local token, default true.'},
            'token': {'type': 'string', 'description': 'Explicit token instead of the configured token.'},
        }}


def request(rt, data):
    raw_path = data['path']
    if len(raw_path) > 16000 or any(ord(c) < 32 for c in raw_path):
        raise ValueError('invalid API path')
    path = urlsplit(raw_path)
    if any(part in ('.', '..') for part in path.path.split('/')):
        raise Refused('API paths cannot contain dot segments')
    if path.scheme or path.netloc or path.fragment or not re.fullmatch(
            r'/(?:ping|notes|folders|tags|resources|search|events|revisions|master_keys)(?:/[A-Za-z0-9_.-]+){0,3}', path.path):
        raise Refused('this path is outside the local Data API interface')
    query = parse_qsl(path.query, keep_blank_values=True)
    for key, value in data.get('query', {}).items():
        for item in value if isinstance(value, list) else [value]:
            if not isinstance(item, (str, int, float, bool)):
                raise ValueError('query values must be scalars')
            query.append((key, str(item).lower() if isinstance(item, bool) else str(item)))
    for key, value in query:
        if key == 'fields' and any(v.strip() and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*|\*',v.strip())
                                   for v in value.split(',')):
            raise Refused('fields accepts comma-separated column names only')
        if key == 'order_by' and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',value):
            raise Refused('order_by accepts a column name only')
    query = [(k, v) for k, v in query if k != 'token']
    if data.get('auth', True):
        query.append(('token', data.get('token', TOKEN)))
    bodies = [k for k in ('json', 'body', 'multipart') if k in data]
    if len(bodies) > 1:
        raise ValueError('supply only one request body')
    headers = {}
    body = None
    if 'json' in data:
        safe_document(data['json'])
        body = json.dumps(data['json'], ensure_ascii=False).encode()
        headers['Content-Type'] = 'application/json'
    elif 'body' in data:
        safe_document(data['body'])
        try:
            safe_document(runtime.strict_json_loads(data['body']))
        except json.JSONDecodeError:
            pass
        body = data['body'].encode()
        headers['Content-Type'] = data.get('content_type', 'application/json')
    elif 'multipart' in data:
        item = data['multipart']
        if set(item) - {'filename', 'base64', 'content_type', 'props'} or not {'filename', 'base64'} <= item.keys():
            raise ValueError('invalid multipart fields')
        from broker import safe_name
        name = safe_name(item['filename'])
        if any(c in name for c in '\x22\r\n'):
            raise ValueError('invalid multipart filename')
        content = base64.b64decode(item['base64'], validate=True)
        if len(content) > MAX_BODY:
            raise ValueError('resource exceeds upload limit')
        check_file(name, content)
        props = item.get('props', {})
        if not isinstance(props, dict):
            raise ValueError('props must be a JSON object')
        safe_document(props)
        properties = json.dumps(props).encode()
        boundary = '----document-' + secrets.token_hex(24)
        while boundary.encode() in content or boundary.encode() in properties:
            boundary = '----document-' + secrets.token_hex(24)
        mime = item.get('content_type', 'application/octet-stream')
        if not isinstance(mime, str) or re.search(r'[\r\n]', mime):
            raise ValueError('invalid content type')
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="props"\r\n\r\n'.encode()
                + properties + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="data"; '
                f'filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
                + content + f'\r\n--{boundary}--\r\n'.encode())
        headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
    if body and len(body) > MAX_BODY + 65536:
        raise ValueError('API body exceeds limit')
    connection = http.client.HTTPConnection('127.0.0.1', rt.config.port, timeout=45)
    try:
        connection.request(data.get('method', 'GET'), path.path + ('?' + urlencode(query) if query else ''), body, headers)
        response = connection.getresponse()
        content = response.read(MAX_BODY + 1)
        if len(content) > MAX_BODY:
            raise ValueError('API response exceeds limit')
        mime = response.getheader('Content-Type', '')
        result = {'status': response.status, 'content_type': mime}
        if (not path.path.endswith('/file') or response.status >= 400) and ('json' in mime or 'text' in mime):
            text = content.decode('utf-8', 'replace')
            if response.status >= 400:
                # The upstream error includes an implementation stack trace.
                try:
                    error = json.loads(text)
                    text = json.dumps({'error': rt.private_text(str(error.get('error', 'Request failed')).split('\n')[0])[0]})
                except (ValueError, AttributeError):
                    text = rt.private_text(text.split('\n')[0])[0]
            try:
                result['body'] = json.loads(text)
            except ValueError:
                result['body'] = text
        else:
            result['body_base64'] = base64.b64encode(content).decode()
        return result
    except (OSError, http.client.HTTPException) as exc:
        raise ValueError('the local Data API did not respond: ' + type(exc).__name__) from None
    finally:
        connection.close()
