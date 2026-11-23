"""The local web of the Miniflux black-box runtime.

The product has no network. Its outbound HTTP requests go to this forward proxy (the runtime
gives the product HTTP_PROXY, http_proxy, HTTPS_PROXY and https_proxy naming it). Every host
name resolves here: a request is answered with the resource published for its URL (op web_put)
or with 404, and every request the product made is recorded (op web_requests). HTTPS tunnels
(CONNECT) are refused. The proxy opens no connection of its own, so nothing behind it, the
runtime or the product itself included, is reachable through it.
"""
import base64
import email.utils
import hashlib
import http.server
import json
import re
import threading
import urllib.parse
from collections import deque

MAX_RESOURCES = 1000
MAX_RESOURCE_BYTES = 2_000_000
MAX_STORE_BYTES = 64_000_000
MAX_LOG = 1000
MAX_LOGGED_BODY = 256_000
MAX_REQUEST_BODY = 4_000_000
# Response headers a published resource may carry (Content-Type and Content-Length come from the resource).
RESPONSE_HEADERS = ('etag', 'last-modified', 'cache-control', 'expires', 'location', 'retry-after', 'content-encoding',
                    'content-language', 'content-disposition', 'link', 'set-cookie', 'x-robots-tag', 'date',
                    'access-control-allow-origin')
HOP = {'connection', 'proxy-connection', 'keep-alive', 'te', 'trailer', 'transfer-encoding', 'upgrade',
       'proxy-authorization', 'proxy-authenticate'}
HOST = re.compile(r'(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*')
TYPES = {'.xml': 'application/xml', '.rss': 'application/rss+xml', '.atom': 'application/atom+xml',
         '.rdf': 'application/rdf+xml', '.json': 'application/json', '.html': 'text/html; charset=utf-8',
         '.htm': 'text/html; charset=utf-8', '.opml': 'text/x-opml', '.txt': 'text/plain; charset=utf-8',
         '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
         '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.webp': 'image/webp', '.mp3': 'audio/mpeg',
         '.ogg': 'audio/ogg', '.m4a': 'audio/mp4', '.mp4': 'video/mp4', '.webm': 'video/webm', '.pdf': 'application/pdf'}

# A 16x16 PNG favicon (one color) for the example site.
FAVICON = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAFklEQVR42mPQyNtHEmIY1TCqYfhqAAAriFQQ28RynAAAAABJRU5ErkJggg==')
EXAMPLE_RSS = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example News</title>
    <link>http://example.org/</link>
    <description>Example articles served by the local web</description>
    <item>
      <title>Hello from the local web</title>
      <link>http://example.org/articles/hello.html</link>
      <guid>http://example.org/articles/hello.html</guid>
      <pubDate>Mon, 06 Jan 2025 09:30:00 GMT</pubDate>
      <author>editor@example.org (Example Editor)</author>
      <description>&lt;p&gt;This article is served by the &lt;em&gt;local web&lt;/em&gt; of the black box.&lt;/p&gt;</description>
    </item>
    <item>
      <title>Second article</title>
      <link>http://example.org/articles/second.html</link>
      <guid>http://example.org/articles/second.html</guid>
      <pubDate>Tue, 07 Jan 2025 14:00:00 GMT</pubDate>
      <description>A plain second article.</description>
    </item>
  </channel>
</rss>
'''
EXAMPLE_ATOM = '''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Notes</title>
  <link href="http://example.org/notes/"/>
  <link rel="self" href="http://example.org/atom.xml"/>
  <id>urn:example:notes</id>
  <updated>2025-02-03T10:00:00Z</updated>
  <entry>
    <title>A note in Atom</title>
    <link href="http://example.org/notes/1"/>
    <id>urn:example:notes:1</id>
    <updated>2025-02-03T10:00:00Z</updated>
    <author><name>Note Writer</name></author>
    <content type="html">&lt;p&gt;Atom content with a &lt;a href="http://example.org/"&gt;link&lt;/a&gt;.&lt;/p&gt;</content>
  </entry>
</feed>
'''
EXAMPLE_JSON = json.dumps({
    'version': 'https://jsonfeed.org/version/1.1', 'title': 'Example Journal',
    'home_page_url': 'http://example.org/journal/', 'feed_url': 'http://example.org/feed.json',
    'items': [{'id': 'journal-1', 'url': 'http://example.org/journal/1', 'title': 'A JSON Feed item',
               'content_html': '<p>JSON Feed content.</p>', 'date_published': '2025-03-04T08:00:00Z',
               'tags': ['example']}]}, indent=2)
EXAMPLE_HOME = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Example site</title>
  <link rel="alternate" type="application/rss+xml" title="Example News" href="/feed.xml">
  <link rel="alternate" type="application/atom+xml" title="Example Notes" href="/atom.xml">
  <link rel="icon" type="image/png" href="/favicon.png">
</head>
<body><h1>Example site</h1><p>A small site of the local web.</p></body>
</html>
'''
EXAMPLE_ARTICLE = '''<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Hello from the local web</title></head>
<body>
  <nav><a href="/">Home</a></nav>
  <article>
    <h1>Hello from the local web</h1>
    <p>The full text of the first example article. It has more paragraphs than its feed summary.</p>
    <p>Pages of the local web can be fetched by the product like any other web page.</p>
  </article>
  <footer>Example footer</footer>
</body>
</html>
'''
EXAMPLES = [
    ('http://example.org/', 'text/html; charset=utf-8', EXAMPLE_HOME.encode()),
    ('http://example.org/feed.xml', 'application/rss+xml', EXAMPLE_RSS.encode()),
    ('http://example.org/atom.xml', 'application/atom+xml', EXAMPLE_ATOM.encode()),
    ('http://example.org/feed.json', 'application/feed+json', EXAMPLE_JSON.encode()),
    ('http://example.org/favicon.png', 'image/png', FAVICON),
    ('http://example.org/articles/hello.html', 'text/html; charset=utf-8', EXAMPLE_ARTICLE.encode()),
]


def canonical(url):
    """(key, display URL) of an absolute http URL; raises ValueError for anything else."""
    if not isinstance(url, str) or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ValueError('url must be an absolute http URL without spaces or control characters')
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() != 'http' or not parts.hostname:
        raise ValueError('url must be an absolute http:// URL with a host name (the local web has no HTTPS)')
    if parts.username is not None or parts.password is not None:
        raise ValueError('url must not carry credentials; use auth')
    host = parts.hostname.lower()
    if not HOST.fullmatch(host) or host == 'localhost' or host.endswith('.localhost') \
            or re.fullmatch(r'[0-9.]+', host):
        raise ValueError('the local web serves host names, not localhost or IP addresses')
    try:
        port = parts.port
    except ValueError:
        raise ValueError('invalid port') from None
    authority = host if port in (None, 80) else f'{host}:{port}'
    path = parts.path or '/'
    key = authority + path + ('?' + parts.query if parts.query else '')
    return key, 'http://' + key


def default_type(path):
    lower = path.lower()
    if lower.endswith('/'):
        return 'text/html; charset=utf-8'
    for suffix, kind in TYPES.items():
        if lower.endswith(suffix):
            return kind
    return 'text/plain; charset=utf-8'


class Resource:
    def __init__(self, url, status, content_type, headers, body, auth):
        self.url, self.status, self.content_type = url, status, content_type
        self.headers, self.body, self.auth = headers, body, auth

    def describe(self):
        return {'url': self.url, 'status': self.status, 'content_type': self.content_type, 'size': len(self.body),
                'sha256': hashlib.sha256(self.body).hexdigest(), 'headers': dict(self.headers),
                'auth': self.auth is not None}


def logged_body(data):
    shown = data[:MAX_LOGGED_BODY]
    entry = {'size': len(data)}
    try:
        entry['body'] = shown.decode('utf-8')
    except UnicodeDecodeError:
        entry['body_base64'] = base64.b64encode(shown).decode()
    if len(data) > MAX_LOGGED_BODY:
        entry['body_truncated'] = True
    return entry


class LocalWeb:
    def __init__(self):
        self.lock = threading.Lock()
        self.resources = {}
        self.log = deque(maxlen=MAX_LOG)
        self.serial = 0
        self.server = None
        self.load_examples()

    # -- resources ------------------------------------------------------------------------------------------
    def load_examples(self):
        for url, kind, body in EXAMPLES:
            key, shown = canonical(url)
            self.resources[key] = Resource(shown, 200, kind, {}, body, None)

    def reset(self):
        """The initial local web: only the example resources, an empty request log."""
        with self.lock:
            self.resources.clear()
            self.log.clear()
            self.load_examples()

    def put(self, data):
        key, shown = canonical(data['url'])
        status = data.get('status', 200)
        if type(status) is not int or not 200 <= status <= 599:
            raise ValueError('status must be an HTTP status between 200 and 599')
        bodies = [k for k in ('body', 'body_base64', 'json') if k in data]
        if len(bodies) > 1:
            raise ValueError('Use only one of body, body_base64 and json')
        if 'body_base64' in data:
            body = base64.b64decode(data['body_base64'], validate=True)
        elif 'json' in data:
            body = json.dumps(data['json'], ensure_ascii=False).encode()
        else:
            body = data.get('body', '').encode()
        if len(body) > MAX_RESOURCE_BYTES:
            raise ValueError(f'A resource holds at most {MAX_RESOURCE_BYTES} bytes')
        kind = data.get('content_type') or ('application/json' if 'json' in data else
                                            default_type(urllib.parse.urlsplit(shown).path))
        if any(ord(c) < 32 or ord(c) == 127 for c in kind):
            raise ValueError('content_type must not contain control characters')
        headers = {}
        for name, value in (data.get('headers') or {}).items():
            lower = str(name).lower()
            if lower not in RESPONSE_HEADERS:
                raise ValueError('Unsupported response header: ' + str(name) + '; allowed: ' + ', '.join(RESPONSE_HEADERS))
            if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError('header values are strings without control characters')
            headers[lower] = value
        if 300 <= status < 400 and status != 304 and 'location' not in headers:
            raise ValueError('a redirect needs a Location header')
        auth = data.get('auth')
        if auth is not None:
            if not isinstance(auth, list) or len(auth) != 2 or not all(isinstance(x, str) and x for x in auth) \
                    or ':' in auth[0]:
                raise ValueError('auth is [username, password] (non-empty, no colon in the username)')
            auth = tuple(auth)
        with self.lock:
            if key not in self.resources and len(self.resources) >= MAX_RESOURCES:
                raise ValueError(f'The local web holds at most {MAX_RESOURCES} resources; delete some first')
            used = sum(len(r.body) for k, r in self.resources.items() if k != key)
            if used + len(body) > MAX_STORE_BYTES:
                raise ValueError(f'The local web holds at most {MAX_STORE_BYTES} bytes')
            self.resources[key] = Resource(shown, status, kind, headers, body, auth)
            return self.resources[key].describe()

    def delete(self, data):
        if ('url' in data) == ('host' in data):
            raise ValueError('web_delete needs exactly one of url and host')
        with self.lock:
            if 'url' in data:
                key, shown = canonical(data['url'])
                removed = [shown] if self.resources.pop(key, None) else []
            else:
                host = str(data['host']).lower()
                keys = [k for k in self.resources if k.split('/', 1)[0].split(':')[0] == host]
                removed = [self.resources.pop(k).url for k in keys]
        return {'removed': removed}

    def listing(self):
        with self.lock:
            return {'resources': [r.describe() for r in sorted(self.resources.values(), key=lambda r: r.url)]}

    def requests(self, data):
        since = data.get('since', 0)
        if type(since) is not int or since < 0:
            raise ValueError('since must be a non-negative integer')
        host = data.get('host')
        with self.lock:
            rows = [dict(x) for x in self.log if x['seq'] > since
                    and (host is None or x['host'] == str(host).lower())]
            last = self.serial
            if data.get('clear'):
                self.log.clear()
        return {'requests': rows, 'last': last}

    # -- proxy ------------------------------------------------------------------------------------------------
    def record(self, method, url, host, headers, body):
        with self.lock:
            self.serial += 1
            entry = {'seq': self.serial, 'method': method, 'url': url, 'host': host,
                     'headers': {k.lower(): v for k, v in headers.items() if k.lower() not in HOP},
                     **logged_body(body)}
            self.log.append(entry)

    def lookup(self, key):
        with self.lock:
            found = self.resources.get(key)
            if found is None and '?' in key:
                found = self.resources.get(key.split('?', 1)[0])
            return found

    def start(self):
        web = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            server_version = 'local-web'
            sys_version = ''

            def log_message(self, *args):
                pass

            def body(self):
                if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
                    data = bytearray()
                    while True:
                        size = int(self.rfile.readline().split(b';')[0].strip() or b'0', 16)
                        if size == 0:
                            while self.rfile.readline() not in (b'\r\n', b'\n', b''):
                                pass
                            return bytes(data)
                        if len(data) + size > MAX_REQUEST_BODY:
                            raise ValueError('request body too large')
                        data.extend(self.rfile.read(size))
                        self.rfile.readline()
                length = int(self.headers.get('Content-Length') or 0)
                if length > MAX_REQUEST_BODY:
                    raise ValueError('request body too large')
                return self.rfile.read(length) if length else b''

            def reply(self, status, kind, payload, extra=()):
                self.send_response(status)
                for name, value in extra:
                    self.send_header(name, value)
                if kind:
                    self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(payload)))
                self.send_header('Connection', 'close')
                self.end_headers()
                if self.command != 'HEAD' and status not in (204, 304):
                    self.wfile.write(payload)
                self.close_connection = True

            def do_CONNECT(self):
                web.record('CONNECT', self.path, self.path.rsplit(':', 1)[0].lower(), dict(self.headers), b'')
                self.reply(403, 'text/plain; charset=utf-8', b'HTTPS tunnels are not available in the local web\n')

            def handle_any(self):
                try:
                    data = self.body()
                except (ValueError, OSError):
                    self.reply(413, 'text/plain; charset=utf-8', b'request body too large\n')
                    return
                target = self.path
                if target.startswith('/'):
                    target = 'http://' + (self.headers.get('Host') or 'unknown.invalid') + target
                try:
                    key, shown = canonical(target)
                    host = key.split('/', 1)[0].split(':')[0]
                except ValueError:
                    web.record(self.command, target[:2000], '', dict(self.headers), data)
                    self.reply(404, 'text/plain; charset=utf-8', b'Not found in the local web\n')
                    return
                web.record(self.command, shown, host, dict(self.headers), data)
                resource = web.lookup(key)
                if resource is None:
                    self.reply(404, 'text/plain; charset=utf-8', b'Not found in the local web\n')
                    return
                if resource.auth is not None:
                    expected = 'Basic ' + base64.b64encode(':'.join(resource.auth).encode()).decode()
                    if self.headers.get('Authorization', '') != expected:
                        self.reply(401, 'text/plain; charset=utf-8', b'Authentication required\n',
                                   [('WWW-Authenticate', 'Basic realm="local web"')])
                        return
                headers = list(resource.headers.items())
                if self.command in ('GET', 'HEAD') and resource.status == 200:
                    etag, modified = resource.headers.get('etag'), resource.headers.get('last-modified')
                    match = self.headers.get('If-None-Match')
                    since = self.headers.get('If-Modified-Since')
                    unchanged = False
                    if etag and match:
                        unchanged = any(x.strip() in ('*', etag, 'W/' + etag) or x.strip().removeprefix('W/') == etag
                                        for x in match.split(','))
                    elif modified and since:
                        try:
                            unchanged = email.utils.parsedate_to_datetime(modified) <= \
                                email.utils.parsedate_to_datetime(since)
                        except (TypeError, ValueError):
                            unchanged = False
                    if unchanged:
                        self.reply(304, None, b'', headers)
                        return
                self.reply(resource.status, resource.content_type, resource.body, headers)

            do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = handle_any

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.server.server_address[1]

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
