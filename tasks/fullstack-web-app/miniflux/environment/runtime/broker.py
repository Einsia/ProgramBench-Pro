#!/usr/bin/env python3
"""Miniflux runtime for a single application instance.

Browser, HTTP and product data operations use the same restricted interface
for the reference and your application.
"""

from __future__ import annotations

import asyncio
import base64
import email.parser
import email.policy
import json
import math
from pathlib import Path
import posixpath
import re
import sys
import time
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import localweb  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, async_playwright  # noqa: E402

PRODUCT = 'Miniflux 2.3.4'
VIEWPORT = {'width': 1280, 'height': 900}
# The baseline accounts every fresh data directory starts with. Their passwords cannot be observed otherwise.
USERS = {'alice': 'Alice-Local-2026!', 'bob': 'Bob-Local-2026!', 'carol': 'Carol-Local-2026!'}
MAX_REQUEST_BYTES = 3_000_000
MAX_RESPONSE_BYTES = 2_000_000
MAX_UPLOAD_BYTES = 1_000_000
MAX_IN_FLIGHT = 8
RPC_TIMEOUT_SEC = 90
HTTP_TIMEOUT_SEC = 60
MAX_SESSIONS = 12
MAX_PENDING_DOWNLOADS = 4
MAX_CONTROLS = 400
MAX_TEXT = 20_000
MAX_VALUE = 4_000
MAX_SCREENSHOT_HEIGHT = 4_000
SETTLE_MS = 250
NAVIGATION_WAIT_SEC = 20
REQUEST_HEADERS = {'accept', 'accept-language', 'authorization', 'if-none-match', 'if-modified-since', 'range',
                   'x-auth-token', 'origin', 'access-control-request-method', 'access-control-request-headers'}
RESPONSE_HEADERS = {'content-type', 'location', 'etag', 'last-modified', 'cache-control', 'www-authenticate',
                    'content-disposition', 'content-length', 'content-range', 'accept-ranges', 'vary',
                    'content-security-policy', 'x-content-type-options', 'access-control-allow-origin',
                    'access-control-allow-methods', 'access-control-allow-headers',
                    'access-control-allow-credentials', 'access-control-max-age', 'x-reader-google-bad-token'}
METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
MODIFIERS = ['Shift', 'Control', 'Alt', 'Meta']
# Product HTTP interfaces reached with op api.
API_PREFIXES = ('/v1/', '/reader/api/0/', '/fever/', '/proxy/', '/feed-icon/')
API_EXACT = ('/fever', '/accounts/ClientLogin', '/healthcheck', '/healthz', '/liveness', '/readiness', '/readyz')
# Front-end implementation files: requested by the pages themselves, never opened, downloaded or fetched with op api.
STATIC = ('/js/', '/stylesheets/', '/icon/')
STATIC_EXACT = ('/favicon.ico', '/robots.txt', '/manifest.json')
DIAGNOSTICS = ('/metrics', '/debug')
# Product HTTP interfaces, static files and diagnostics never open as browser pages.
NOT_PAGES = ('/v1/', '/reader/', '/fever', '/accounts/', '/proxy/', '/feed-icon/', '/healthcheck', '/healthz',
             '/liveness', '/readiness', '/readyz', *STATIC, *DIAGNOSTICS)
# Deployment locations that never reach the caller (error responses, instance-administration pages).
STATIC_PRIVATE = ['/opt/blackbox', '/opt/browsers', '/opt/venv']
# The user setting that would run custom JavaScript in the browser; the black box refuses to set it.
SCRIPT_SETTING = 'custom_js'

# -- machine-readable help (blackbox-v2) ---------------------------------------------------------------
SESSION = {'type': 'string', 'description': 'Browser session name (at most 64 characters); default main. '
                                            'Each session is one page with its own cookies, so separate sessions '
                                            'can be signed in as different users.'}
TARGET = {'type': 'object', 'description': 'Semantic locator: exactly one of ref (from the latest snapshot), role '
                                           '(with optional name), label, placeholder or text; optional nth '
                                           '(zero-based) and exact (default true).'}


def target(required=False, note=''):
    field = dict(TARGET, description=TARGET['description'] + note)
    if required:
        field['required'] = True
    return field


def number(description, required=False):
    field = {'type': 'number', 'description': description}
    if required:
        field['required'] = True
    return field


POINT = 'Without a target: viewport CSS pixels (0-1279, 0-899) as in the screenshot. With a target: CSS pixels ' \
        'relative to the target box, inside it.'
BUTTON = {'type': 'string', 'enum': ['left', 'middle', 'right'], 'description': 'Mouse button; default left.'}
COUNT = {'type': 'integer', 'enum': [1, 2, 3], 'description': 'Number of clicks (2 = double click); default 1.'}
HELD = {'type': 'array', 'items': {'type': 'string', 'enum': MODIFIERS},
        'description': 'Keys held during the action: Shift, Control, Alt, Meta.'}
GESTURE = {
    'session': SESSION,
    'target': target(note=' Optional; coordinates are then relative to its box.'),
    'x': number('Start x. ' + POINT), 'y': number('Start y. ' + POINT),
    'to_x': number('End x of a drag (same frame as x).'), 'to_y': number('End y of a drag (same frame as y).'),
    'from': {'type': 'object', 'description': 'Alternative drag start {x, y}.'},
    'to': {'type': 'object', 'description': 'Alternative drag end {x, y}.'},
    'via': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}},
            'description': 'Drag only: up to 60 intermediate [x, y] points passed in order before the end.'},
    'steps': {'type': 'integer', 'description': 'Drag only: pointer moves on the final segment, 1-100; default 5.'},
    'button': BUTTON, 'modifiers': HELD,
}
WEB_URL = {'type': 'string', 'required': True,
           'description': 'Absolute http:// URL with a host name, for example http://news.example.com/feed.xml. '
                          'Host names are compared case-insensitively; the query is part of the address (a request '
                          'whose exact query has no resource falls back to the resource without a query).'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, limits and baseline accounts.',
             'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the product process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Restart the product with an empty data directory (its initial three-account state), '
                         'close all browser sessions and return the local web to its example resources with an '
                         'empty request log.'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Restart the product process with the same data directory; browser sessions and their '
                           'cookies stay, and so does the local web, so reload pages afterwards.'},
    'api': {'kind': 'http',
            'summary': 'One HTTP request to the product: the REST API under /v1/, the Fever API under /fever/, '
                       'the Google Reader API (/accounts/ClientLogin and /reader/api/0/), the health checks '
                       '(/healthcheck, /healthz, /liveness, /readiness, /readyz), media proxy addresses under '
                       '/proxy/ and feed icons under /feed-icon/. Redirects are not followed.',
            'fields': {
                'path': {'type': 'string', 'required': True,
                         'description': 'Absolute product path with optional query, for example '
                                        '/v1/entries?status=unread&limit=5; no dot segments.'},
                'method': {'type': 'string', 'enum': METHODS, 'description': 'HTTP method; default GET.'},
                'auth': {'type': ['string', 'array'], 'items': {'type': 'string'},
                         'description': 'HTTP Basic authentication: a baseline username (alice, bob or carol) '
                                        'or [username, password] for any account.'},
                'token': {'type': 'string', 'description': 'API key, sent as the X-Auth-Token header.'},
                'headers': {'type': 'object', 'description': 'Request headers; allowed: ' +
                            ', '.join(sorted(REQUEST_HEADERS)) + '. Use at most one of auth, token and an '
                            'Authorization or X-Auth-Token header.'},
                'json': {'type': ['object', 'array', 'string', 'number', 'boolean'],
                         'description': 'JSON request body (at most one body field).'},
                'body': {'type': 'string', 'description': 'Text request body.'},
                'body_base64': {'type': 'string', 'description': 'Request body bytes, base64 encoded.'},
                'form': {'type': 'object',
                         'description': 'application/x-www-form-urlencoded body: {name: text or list of texts} '
                                        '(a list repeats the field).'},
                'multipart': {'type': 'object',
                              'description': 'multipart/form-data body {fields: {name: text}, files: {name: '
                                             '{filename, base64, mime_type}}}.'},
                'content_type': {'type': 'string', 'description': 'Content-Type of the body; default '
                                                                  'application/json (form: '
                                                                  'application/x-www-form-urlencoded).'},
                'binary': {'type': 'boolean', 'description': 'Also return the response bytes as body_base64.'},
            }},
    'web_put': {'kind': 'files',
                'summary': 'Publish or replace one resource of the local web, the only network the product '
                           'reaches: the product\'s requests for this URL (any method) are answered with it.',
                'fields': {
                    'url': WEB_URL,
                    'status': {'type': 'integer', 'description': 'HTTP status of the answer, 200-599; default 200. '
                                                                 'A redirect needs a Location header.'},
                    'content_type': {'type': 'string',
                                     'description': 'Content-Type of the answer; default from the URL suffix '
                                                    '(.xml, .rss, .atom, .rdf, .json, .html, .opml, images, audio, '
                                                    'video; a path ending in / is HTML) or text/plain.'},
                    'headers': {'type': 'object',
                                'description': 'Further response headers; allowed: ' +
                                               ', '.join(localweb.RESPONSE_HEADERS) + '. With ETag or '
                                               'Last-Modified, conditional GET requests are answered 304.'},
                    'body': {'type': 'string', 'description': 'Text body (UTF-8); at most one of body, '
                                                              'body_base64 and json.'},
                    'body_base64': {'type': 'string',
                                    'description': 'Body bytes, base64 encoded, at most 2000000 bytes.'},
                    'json': {'type': ['object', 'array', 'string', 'number', 'boolean'],
                             'description': 'JSON body (Content-Type application/json unless content_type says '
                                            'otherwise).'},
                    'auth': {'type': 'array', 'items': {'type': 'string'},
                             'description': '[username, password]: requests without these HTTP Basic credentials '
                                            'are answered 401.'},
                }},
    'web_delete': {'kind': 'files',
                   'summary': 'Remove one resource (url) or every resource of a host (host) from the local web; '
                              'their URLs answer 404 again.',
                   'fields': {'url': dict(WEB_URL, required=False),
                              'host': {'type': 'string', 'description': 'Host name whose resources are removed.'}}},
    'web_list': {'kind': 'files', 'fields': {},
                 'summary': 'The resources of the local web: URL, status, content type, size, SHA-256, headers and '
                            'whether they need credentials.'},
    'web_requests': {'kind': 'files',
                     'summary': 'The requests the product sent to the local web, oldest first (the last 1000): '
                                'sequence number, method, URL, host, request headers and body.',
                     'fields': {'host': {'type': 'string', 'description': 'Only requests for this host name.'},
                                'since': {'type': 'integer',
                                          'description': 'Only requests with a higher sequence number; default 0.'},
                                'clear': {'type': 'boolean', 'description': 'Empty the request log after reading.'}}},
    'open': {'kind': 'gui', 'summary': 'Open a product page in a session (the session is created if needed).',
             'fields': {'session': SESSION,
                        'path': {'type': 'string', 'description': 'Absolute page path with optional query or '
                                                                  'fragment, for example /unread; default /.'}}},
    'snapshot': {'kind': 'observe', 'fields': {'session': SESSION},
                 'summary': 'Page URL, title, viewport, scroll position and page size, visible text, controls (ref, '
                            'role, labels, form field name, link target, value, state, bounds [x,y,w,h] in viewport '
                            'pixels), pending downloads and file chooser.'},
    'screenshot': {'kind': 'observe',
                   'fields': {'session': SESSION,
                              'full_page': {'type': 'boolean',
                                            'description': 'Capture the whole page (at most 4000 pixels tall) '
                                                           'instead of the 1280x900 viewport; default false.'}},
                   'summary': 'PNG of the 1280x900 viewport (or of the whole page) as png_base64.'},
    'click': {'kind': 'gui', 'summary': 'Click a control found by a locator.',
              'fields': {'session': SESSION, 'target': target(True), 'button': BUTTON, 'click_count': COUNT,
                         'modifiers': HELD}},
    'fill': {'kind': 'gui', 'summary': 'Replace the value of a form field.',
             'fields': {'session': SESSION, 'target': target(True),
                        'value': {'type': 'string', 'required': True, 'description': 'Replacement text.'}}},
    'type': {'kind': 'gui', 'summary': 'Insert text at the cursor of the target (focused first) or, without a '
                                       'target, of the focused element.',
             'fields': {'session': SESSION, 'target': target(note=' Optional.'),
                        'value': {'type': 'string', 'required': True, 'description': 'Text to insert.'}}},
    'select': {'kind': 'gui', 'summary': 'Choose an option of a native select control by value or label.',
               'fields': {'session': SESSION, 'target': target(True),
                          'value': {'type': 'string', 'required': True, 'description': 'Option value or label.'}}},
    'check': {'kind': 'gui', 'summary': 'Set a checkbox or radio button (also through its visible label).',
              'fields': {'session': SESSION, 'target': target(True),
                         'checked': {'type': 'boolean', 'description': 'Desired state; default true.'}}},
    'press': {'kind': 'gui', 'summary': 'Press a key or chord (Playwright names such as Enter, Escape, Tab, '
                                        'ArrowDown, Shift+Tab, ControlOrMeta+A) on the target, which is focused '
                                        'first, or without a target on the focused element (keyboard shortcuts '
                                        'of the page itself).',
              'fields': {'session': SESSION, 'target': target(note=' Optional.'),
                         'key': {'type': 'string', 'required': True, 'description': 'Key name or chord.'}}},
    'pointer': {'kind': 'gui', 'summary': 'Low-level mouse action: click, down, up, move (hover) or drag at '
                                          'coordinates.',
                'fields': {**GESTURE,
                           'action': {'type': 'string', 'enum': ['click', 'down', 'up', 'move', 'drag'],
                                      'description': 'Pointer action; default click.'},
                           'click_count': COUNT}},
    'drag': {'kind': 'gui', 'summary': 'Press at x,y, pass through via points, release at to_x,to_y '
                                       '(alias of pointer with action drag).',
             'fields': dict(GESTURE)},
    'wheel': {'kind': 'gui', 'summary': 'Turn the mouse wheel over a point (scrolls the list or page under it).',
              'fields': {'session': SESSION, 'target': GESTURE['target'],
                         'x': number('x of the pointer. ' + POINT, True), 'y': number('y of the pointer. ' + POINT, True),
                         'delta_x': number('Horizontal wheel delta, -5000..5000; default 0.'),
                         'delta_y': number('Vertical wheel delta, -5000..5000 (positive scrolls down); default 0.')}},
    'scroll': {'kind': 'gui', 'summary': 'Scroll the page itself by a pixel offset.',
               'fields': {'session': SESSION,
                          'delta_x': number('Horizontal offset, -5000..5000; default 0.'),
                          'delta_y': number('Vertical offset, -5000..5000 (positive scrolls down); default 0.')}},
    'wait': {'kind': 'gui', 'summary': 'Wait up to 3 seconds for asynchronous page changes, then snapshot.',
             'fields': {'session': SESSION, 'seconds': number('Seconds to wait, 0-3; default 0.5.')}},
    'upload': {'kind': 'gui', 'summary': 'Supply one file through a file input (hidden inputs can be addressed by '
                                         'label) or, without a target, answer the pending file chooser.',
               'fields': {'session': SESSION, 'target': target(note=' Optional when a file chooser is pending.'),
                          'filename': {'type': 'string', 'required': True, 'description': 'File name.'},
                          'mime_type': {'type': 'string', 'description': 'MIME type; default '
                                                                         'application/octet-stream.'},
                          'base64': {'type': 'string', 'required': True,
                                     'description': 'File bytes, base64 encoded, at most 1 MB.'}}},
    'download': {'kind': 'files', 'summary': 'Retrieve a pending product download (listed in the snapshot) once, '
                                             'as body_base64 (at most 2 MB).',
                 'fields': {'session': SESSION,
                            'ref': {'type': 'string', 'required': True, 'description': 'Download ref, such as d0.'}}},
    'reload': {'kind': 'gui', 'summary': 'Reload the page.', 'fields': {'session': SESSION}},
    'back': {'kind': 'gui', 'summary': 'Go back in the page history.', 'fields': {'session': SESSION}},
    'close': {'kind': 'lifecycle', 'summary': 'Close a browser session.', 'fields': {'session': SESSION}},
})
BROWSER_OPS = {op for op, spec in OPERATIONS.items() if spec['kind'] in ('gui', 'observe')} | {'download', 'close'}
WEB_OPS = {'web_put', 'web_delete', 'web_list', 'web_requests'}
NOTES = [
    'Static scripts and styles load as assets; page-script reads of their bytes are refused.',
    'Links to javascript: addresses are not activated by pointer, keyboard or drag actions.',
    'Every fresh data directory starts with the three baseline accounts listed under accounts (alice is an '
    'administrator); their passwords cannot be observed otherwise.',
    'The product has no internet. Its outbound HTTP requests go through the local web: an HTTP proxy that the '
    'runtime names in the product\'s HTTP_PROXY, http_proxy, HTTPS_PROXY and https_proxy environment variables '
    '(NO_PROXY and no_proxy list localhost, 127.0.0.1 and ::1). Every host name exists there: a request is '
    'answered with the resource published for its URL (web_put) or with 404, and HTTPS tunnels are refused. '
    'web_requests shows what the product sent, web_list what is published; reset returns the local web to its '
    'example resources (a small site at http://example.org/) and empties the request log. Pages in the browser '
    'load nothing from the local web.',
    'Browser sessions run Chromium with a 1280x900 viewport, locale en-US and time zone UTC.',
    'Every browser action returns a fresh snapshot; refs are valid only for the latest snapshot of that session.',
    'Pages are restricted to the product origin: the product HTTP interfaces (/v1/, /fever/, /accounts/, '
    '/reader/, the health checks, /proxy/ and /feed-icon/), static front-end files and instance diagnostics do not '
    'open as pages, and no external resource loads. Static implementation assets cannot be read as data by page scripts. Native '
    'dialogs (alert, confirm, prompt) are accepted automatically. New windows and tabs are closed.',
    'Paths with dot segments or empty segments are rejected; use the normalized product path.',
    'The custom JavaScript user setting (custom_js) cannot be given a value through the black box: API requests '
    'and form submissions that would set it are refused, because it would run code in the browser.',
    'The File System Access API is not available and native colour or date pickers do not open; set such fields '
    'with fill.',
    'File choosers opened by the page appear in the snapshot as file_chooser; answer them with upload.',
    'Product downloads appear in the snapshot with a ref (at most 4 pending per session); download retrieves each '
    'once. Static front-end files (scripts, style sheets) are not offered as downloads.',
    'Deployment filesystem paths in error responses and instance-administration pages are redacted. Instance '
    'diagnostics and metrics are not exposed.',
    'Browser and API operations share the product state.',
]
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'response_bytes': MAX_RESPONSE_BYTES, 'upload_bytes': MAX_UPLOAD_BYTES,
          'sessions': MAX_SESSIONS, 'pending_downloads_per_session': MAX_PENDING_DOWNLOADS,
          'controls': MAX_CONTROLS, 'text_characters': MAX_TEXT, 'value_characters': MAX_VALUE,
          'in_flight': MAX_IN_FLIGHT, 'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'http_timeout_seconds': HTTP_TIMEOUT_SEC,
          'screenshot_full_page_height': MAX_SCREENSHOT_HEIGHT, 'wheel_and_scroll_delta': [-5000, 5000],
          'drag_via_points': 60, 'drag_steps': [1, 100], 'wait_seconds': 3,
          'web_resources': localweb.MAX_RESOURCES, 'web_resource_bytes': localweb.MAX_RESOURCE_BYTES,
          'web_store_bytes': localweb.MAX_STORE_BYTES, 'web_requests_kept': localweb.MAX_LOG,
          'web_logged_body_bytes': localweb.MAX_LOGGED_BODY}
EXAMPLES = [{'op': 'api', 'path': '/v1/me', 'auth': 'alice'},
            {'op': 'api', 'path': '/v1/feeds', 'method': 'POST', 'auth': 'alice',
             'json': {'feed_url': 'http://example.org/feed.xml', 'category_id': 1}},
            {'op': 'api', 'path': '/v1/entries?status=unread&direction=desc', 'auth': 'alice'},
            {'op': 'web_put', 'url': 'http://news.example.com/feed.xml', 'content_type': 'application/rss+xml',
             'body': '<?xml version="1.0"?><rss version="2.0"><channel><title>News</title>'
                     '<link>http://news.example.com/</link><item><title>One</title>'
                     '<link>http://news.example.com/1</link></item></channel></rss>'},
            {'op': 'web_requests', 'host': 'news.example.com'},
            {'op': 'open', 'path': '/'},
            {'op': 'fill', 'target': {'label': 'Username'}, 'value': 'alice'},
            {'op': 'fill', 'target': {'label': 'Password'}, 'value': 'Alice-Local-2026!'},
            {'op': 'click', 'target': {'role': 'button', 'name': 'Login'}},
            {'op': 'scroll', 'delta_y': 600},
            {'op': 'screenshot', 'full_page': True}]

# Browser settings shared by the reference and your application.
INIT_SCRIPT = r'''(() => {
  const scriptAddress = value => {
    try { return new URL(value, document.baseURI).protocol === "javascript:"; }
    catch (e) { return false; }
  };
  const preventScriptNavigation = event => {
    if (event.type === "keydown" && !["Enter", " "].includes(event.key)) return;
    const link = event.composedPath().find(node =>
      node instanceof Element && node.matches("a[href], area[href]"));
    if (link && scriptAddress(link.getAttribute("href") || "")) event.preventDefault();
    if (event.type === "drop" && event.dataTransfer) {
      for (const type of ["text/uri-list", "text/plain"]) {
        const value = event.dataTransfer.getData(type);
        if (scriptAddress(value) || value.split(/\r?\n/).some(scriptAddress)) event.preventDefault();
      }
    }
  };
  for (const type of ["click", "auxclick", "keydown", "dragstart", "drop"])
    document.addEventListener(type, preventScriptNavigation, true);
  for (const k of ["showOpenFilePicker", "showSaveFilePicker", "showDirectoryPicker"]) {
    try { delete window[k]; } catch (e) {}
    try { delete Window.prototype[k]; } catch (e) {}
  }
  document.addEventListener("click", e => {
    const t = e.target;
    if (t instanceof HTMLInputElement && ["color", "date", "time", "datetime-local", "month", "week"].includes(t.type))
      e.preventDefault();
  }, true);
})();'''

SNAPSHOT_SCRIPT = r'''([start, limits]) => {
  for (const name of ["data-blackbox-ref", "data-blackbox-state"])
    document.querySelectorAll("[" + name + "]").forEach(e => e.removeAttribute(name));
  const W = innerWidth, H = innerHeight;
  const shown = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0; };
  // A visually hidden native checkbox or radio is operated through its visible label or container.
  const proxyOf = e => { if (e.tagName !== "INPUT" || !["checkbox", "radio"].includes(e.type) || shown(e)) return null;
    return [...(e.labels || [])].find(shown) || (e.parentElement && shown(e.parentElement) ? e.parentElement : null); };
  const roles = new Set(["button", "link", "checkbox", "radio", "switch", "tab", "menuitem", "menuitemcheckbox",
    "menuitemradio", "option", "combobox", "textbox", "searchbox", "slider", "spinbutton", "treeitem", "listbox",
    "menu", "dialog", "alertdialog"]);
  const selector = 'a,button,input,select,textarea,summary,[role],[contenteditable="true"]';
  const clip = (v, n) => (v || "").trim().slice(0, n);
  const out = [], seen = new Set(); let truncated = false;
  for (const e of document.querySelectorAll(selector)) {
    if (e.tagName === "INPUT" && e.type === "hidden") continue;
    const role = e.getAttribute("role");
    if (role && !roles.has(role) && !["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA", "SUMMARY"].includes(e.tagName)
        && !e.isContentEditable) continue;
    const proxy = proxyOf(e), el = proxy || e;
    if (seen.has(el) || seen.has(e)) continue;
    if (!proxy && !shown(e)) continue;
    if (out.length >= limits.controls) { truncated = true; break; }
    const ref = "e" + (start + out.length);
    el.setAttribute("data-blackbox-ref", ref);
    if (proxy) e.setAttribute("data-blackbox-state", ref);
    seen.add(el); seen.add(e);
    const r = el.getBoundingClientRect();
    const label = e.labels ? [...e.labels].map(x => x.innerText).join(" ") : "";
    const c = {ref, tag: e.tagName.toLowerCase(), role, text: clip(el.innerText, 300)};
    const extra = {aria: clip(e.getAttribute("aria-label"), 300), label: clip(label, 300),
                   title: clip(e.getAttribute("title") || e.getAttribute("data-tooltip-content"), 300),
                   name: clip(e.getAttribute("name"), 200), placeholder: clip(e.getAttribute("placeholder"), 300),
                   type: typeof e.type === "string" && e.tagName !== "BUTTON" && e.tagName !== "SELECT" ? e.type : ""};
    for (const [k, v] of Object.entries(extra)) if (v) c[k] = v;
    if (e.tagName === "BUTTON" && e.type && e.type !== "submit") c.type = e.type;
    if (e.disabled) c.disabled = true;
    if (e.tagName === "A" && e.href) { try { const u = new URL(e.href);
      c.href = u.origin === location.origin ? u.pathname + u.search + u.hash : "[external]"; } catch (x) {} }
    if (["INPUT", "TEXTAREA"].includes(e.tagName)) {
      const v = e.type === "password" ? (e.value ? "[password]" : "") : e.value;
      c.value = v.slice(0, limits.value); if (v.length > limits.value) c.value_truncated = true; }
    if (e.isContentEditable && e.tagName !== "INPUT" && e.tagName !== "TEXTAREA") {
      const v = e.innerText || ""; c.value = v.slice(0, limits.value); if (v.length > limits.value) c.value_truncated = true; }
    if (e.type === "checkbox" || e.type === "radio") c.checked = e.checked;
    else if (["checkbox", "radio", "switch", "menuitemcheckbox", "menuitemradio"].includes(role))
      c.checked = e.getAttribute("aria-checked") === "true";
    if (e.tagName === "SELECT") { c.value = e.value;
      c.options = [...e.options].slice(0, 200).map(o => ({label: o.text.slice(0, 300), value: o.value.slice(0, 300),
        selected: o.selected, disabled: o.disabled}));
      if (e.options.length > 200) c.options_truncated = true; }
    const expanded = e.getAttribute("aria-expanded"); if (expanded !== null) c.expanded = expanded === "true";
    const selected = e.getAttribute("aria-selected"); if (selected !== null) c.selected = selected === "true";
    for (const k of ["min", "max", "maxlength", "accept"]) if (e.hasAttribute(k)) c[k] = e.getAttribute(k);
    if (e.multiple) c.multiple = true;
    if (e.required) c.required = true;
    c.bounds = [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)];
    if (r.bottom <= 0 || r.right <= 0 || r.top >= H || r.left >= W) c.offscreen = true;
    if (proxy) c.proxy = true;
    if (document.activeElement === e) c.focused = true;
    out.push(c);
  }
  const s = (document.body && document.body.innerText) || "";
  const root = document.documentElement;
  return {controls: out, controls_truncated: truncated, viewport: [W, H],
          scroll: [Math.round(scrollX), Math.round(scrollY)],
          page_size: [Math.max(root.scrollWidth, W), Math.max(root.scrollHeight, H)],
          text: s.slice(0, limits.text), text_truncated: s.length > limits.text};
}'''

MASK_SCRIPT = r'''(pattern) => {
  const re = new RegExp(pattern, "g");
  const mask = s => s.replace(re, "[private path]");
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walk.nextNode())) {
    if (node.parentElement.closest("script,style")) continue;
    const masked = mask(node.nodeValue);
    if (masked !== node.nodeValue) node.nodeValue = masked;
  }
  for (const el of document.querySelectorAll("input,textarea")) {
    const masked = mask(el.value);
    if (masked !== el.value) el.value = masked;
  }
}'''

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
lock = asyncio.Lock()
config = None
origin = None
product = None
web = None
web_origin = b''
audit = None
redact = None
private = None
private_bytes = None
browser = None
sessions: dict[str, tuple[object, object]] = {}
ref_serial = 0
download_serial = 0
in_flight = 0


class RequestTooLarge(ValueError):
    pass


def text_value(value, field, *, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value):
        raise ValueError(field + ' must be a string' + (' with a value' if nonempty else ''))
    return value


def redact_value(value):
    if isinstance(value, str):
        return private.sub('[private path]', value)
    if isinstance(value, list):
        return [redact_value(x) for x in value]
    if isinstance(value, dict):
        return {key: redact_value(x) for key, x in value.items()}
    return value


# -- path policy ---------------------------------------------------------------------------------------
def decoded_path(value):
    return urllib.parse.unquote(urllib.parse.urlsplit(value).path, errors='strict')


def under(path, prefixes, exact=()):
    return path in exact or any(path.startswith(p) or path == p.rstrip('/') for p in prefixes)


def instance_diagnostics(path):
    decoded = posixpath.normpath(urllib.parse.unquote(path, errors='strict'))
    return under(decoded, DIAGNOSTICS)


def static_file(path):
    return under(path, STATIC, STATIC_EXACT)


def product_path(value):
    """An absolute product path: no scheme, host, dot or empty segments, backslashes or control characters."""
    if not isinstance(value, str) or not value.startswith('/') or value.startswith('//'):
        raise ValueError('Use an absolute product path, such as /unread; URLs are forbidden.')
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Control characters are forbidden')
    parsed = urllib.parse.urlsplit(value)
    decoded = urllib.parse.unquote(parsed.path, errors='strict')
    if parsed.scheme or parsed.netloc or '\\' in value or '\\' in decoded or '//' in decoded \
            or any(x in ('.', '..') for x in decoded.split('/')):
        raise ValueError('Invalid product path')
    if any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        raise ValueError('Control characters are forbidden')
    if instance_diagnostics(parsed.path):
        raise ValueError('Instance diagnostics and metrics are not exposed by the black box')
    if static_file(decoded):
        raise ValueError('Static front-end files are not exposed by the black box')
    return value


def api_path(value):
    value = product_path(value)
    path = decoded_path(value)
    if not (path.startswith(API_PREFIXES) or path in API_EXACT):
        raise ValueError('HTTP access exposes the REST API (/v1/), the Fever API (/fever/), the Google Reader API '
                         '(/accounts/ClientLogin, /reader/api/0/), the health checks, /proxy/ and /feed-icon/; use '
                         'browser operations for pages')
    return value


def page_path(value):
    value = product_path(value)
    path = decoded_path(value)
    if under(path, NOT_PAGES) or path in ('/v1', '/reader', '/accounts'):
        raise ValueError('Product HTTP interfaces do not open as browser pages; use op api')
    return value


def download_path(value):
    """A product download comes from a page route or a product HTTP interface, never from a static file."""
    value = product_path(value)
    try:
        return page_path(value)
    except ValueError:
        return api_path(value)


# -- the custom JavaScript setting ---------------------------------------------------------------------
def script_field(name):
    return isinstance(name, str) and name.casefold() == SCRIPT_SETTING


def pairs_set_script(pairs):
    return any(script_field(name) and value != '' for name, value in pairs)


def json_sets_script(text):
    """Client settings JSON must be unambiguous; field matching is case-insensitive."""
    try:
        value = runtime.strict_json_loads(text)
    except json.JSONDecodeError as exc:
        # A complete value followed by more input is ambiguous for a streaming decoder.
        # Ordinary syntax errors are left to the product's normal validation response.
        return exc.msg == 'Extra data'
    except ValueError:
        return True
    return isinstance(value, dict) and any(script_field(k) and v not in ('', None) for k, v in value.items())


def multipart_pairs(content_type, body):
    try:
        message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            b'Content-Type: ' + content_type.encode('latin-1', 'replace') + b'\r\n\r\n' + body)
        if not message.is_multipart():
            return []
        pairs = []
        for part in message.iter_parts():
            name = part.get_param('name', header='content-disposition')
            if name is not None:
                pairs.append((str(name), (part.get_payload(decode=True) or b'').decode('utf-8', 'replace')))
        return pairs
    except Exception:
        return []


def sets_script(content_type, body, query=''):
    """Whether a request would give the custom JavaScript setting a value, under every reading of its body."""
    if pairs_set_script(urllib.parse.parse_qsl(query, keep_blank_values=True)):
        return True
    if not body:
        return False
    text = body.decode('utf-8', 'replace')
    if json_sets_script(text) or pairs_set_script(urllib.parse.parse_qsl(text, keep_blank_values=True)):
        return True
    kind = (content_type or '').split(';')[0].strip().lower()
    return kind.startswith('multipart/') and pairs_set_script(multipart_pairs(content_type, body))


# -- request validation --------------------------------------------------------------------------------
def validate_target(value):
    if not isinstance(value, dict):
        raise ValueError('target must be a semantic locator object')
    keys = {'ref', 'role', 'label', 'placeholder', 'text'} & value.keys()
    if len(keys) != 1 or value.keys() - (keys | {'name', 'nth', 'exact'}):
        raise ValueError('target needs exactly one of ref, role, label, placeholder or text (plus name, nth, exact); '
                         'arbitrary selectors are forbidden')
    key = next(iter(keys))
    text_value(value[key], 'target.' + key, nonempty=True)
    if key == 'ref' and not re.fullmatch(r'e[0-9]+', value[key]):
        raise ValueError('Invalid control reference')
    # Playwright inserts roles into its internal selector syntax without escaping.
    if key == 'role' and not re.fullmatch(r'[a-z][a-z0-9]*', value[key]):
        raise ValueError('role must be an ARIA role name')
    if 'name' in value:
        if key != 'role':
            raise ValueError('name is only supported with role')
        text_value(value['name'], 'target.name')
    if 'nth' in value and (type(value['nth']) is not int or value['nth'] < 0):
        raise ValueError('nth must be a non-negative integer')
    if 'exact' in value and type(value['exact']) is not bool:
        raise ValueError('exact must be boolean')


def finite(value, field, low=-100, high=5000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(field + ' must be a finite number')
    if not low <= value <= high:
        raise ValueError(f'{field} must lie between {low} and {high}')
    return float(value)


def point(value, field):
    if not isinstance(value, dict) or set(value) != {'x', 'y'}:
        raise ValueError(field + ' must be an object {x, y}')
    return finite(value['x'], field + '.x'), finite(value['y'], field + '.y')


def gesture_points(data, drag):
    """(start, via points, end) in the request's coordinate frame."""
    if drag:
        if 'from' in data or 'to' in data:
            if not {'from', 'to'} <= data.keys() or {'x', 'y', 'to_x', 'to_y'} & data.keys():
                raise ValueError('Use either from/to objects or x, y, to_x, to_y')
            start, end = point(data['from'], 'from'), point(data['to'], 'to')
        else:
            start = finite(data.get('x'), 'x'), finite(data.get('y'), 'y')
            end = finite(data.get('to_x'), 'to_x'), finite(data.get('to_y'), 'to_y')
        via = data.get('via', [])
        if not isinstance(via, list) or len(via) > 60:
            raise ValueError('via lists at most 60 [x, y] points')
        middle = []
        for item in via:
            if not isinstance(item, list) or len(item) != 2:
                raise ValueError('each via point is [x, y]')
            middle.append((finite(item[0], 'via x'), finite(item[1], 'via y')))
        steps = data.get('steps', 5)
        if type(steps) is not int or not 1 <= steps <= 100:
            raise ValueError('steps must be between 1 and 100')
        return start, middle, end
    for key in ('to_x', 'to_y', 'from', 'to', 'via', 'steps'):
        if key in data:
            raise ValueError(key + ' is only used by drags')
    return (finite(data.get('x'), 'x'), finite(data.get('y'), 'y')), [], None


def header_value(value, field):
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(field + ' must be a string without control characters')
    return value


def form_pairs(form):
    if not isinstance(form, dict):
        raise ValueError('form must be an object of texts or lists of texts')
    pairs = []
    for name, value in form.items():
        values = value if isinstance(value, list) else [value]
        if not all(isinstance(x, str) for x in values):
            raise ValueError('form values are texts or lists of texts')
        pairs.extend((name, x) for x in values)
    return pairs


def request_body(data):
    """(content type, body bytes) of an api request as the product will receive it."""
    if 'json' in data:
        return data.get('content_type', 'application/json'), json.dumps(data['json']).encode()
    if 'body' in data:
        return data.get('content_type', 'application/json'), data['body'].encode()
    if 'body_base64' in data:
        return data.get('content_type', 'application/json'), base64.b64decode(data['body_base64'], validate=True)
    if 'form' in data:
        return (data.get('content_type', 'application/x-www-form-urlencoded'),
                urllib.parse.urlencode(form_pairs(data['form'])).encode())
    return data.get('content_type', 'application/json'), b''


def validate_api(data):
    path = api_path(data['path'])
    auth = data.get('auth')
    if isinstance(auth, str):
        if auth not in USERS:
            raise ValueError('Use [username, password] for an account other than alice, bob or carol')
    elif auth is not None and (len(auth) != 2 or not all(isinstance(x, str) for x in auth)):
        raise ValueError('auth must be a baseline username or [username, password]')
    if 'token' in data:
        header_value(text_value(data['token'], 'token', nonempty=True), 'token')
    lowered = set()
    for key, value in data.get('headers', {}).items():
        if key.lower() not in REQUEST_HEADERS:
            raise ValueError('Unsupported request header: ' + str(key))
        header_value(value, 'header ' + key)
        if key.lower() in lowered:
            raise ValueError('Duplicate request header')
        lowered.add(key.lower())
    if sum((auth is not None, 'token' in data, bool({'authorization', 'x-auth-token'} & lowered))) > 1:
        raise ValueError('Use only one of auth, token, or an Authorization or X-Auth-Token header')
    if len({'json', 'body', 'body_base64', 'multipart', 'form'} & data.keys()) > 1:
        raise ValueError('Use only one request body format')
    header_value(data.get('content_type', 'application/json'), 'content_type')
    pairs = []
    if 'multipart' in data:
        parts = data['multipart']
        if parts.keys() - {'fields', 'files'}:
            raise ValueError('multipart contains only fields and files')
        fields, files = parts.get('fields', {}), parts.get('files', {})
        if not isinstance(fields, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in fields.items()):
            raise ValueError('multipart fields must be a mapping of strings')
        if not isinstance(files, dict):
            raise ValueError('multipart files must be an object')
        for key, value in files.items():
            if not isinstance(value, dict) or value.keys() - {'filename', 'base64', 'mime_type'}:
                raise ValueError('Each multipart file is {filename, base64, mime_type}')
            text_value(value.get('filename'), 'filename', nonempty=True)
            text_value(value.get('mime_type', 'application/octet-stream'), 'mime_type', nonempty=True)
            base64.b64decode(text_value(value.get('base64'), 'base64'), validate=True)
        pairs = list(fields.items()) + [(k, 'file') for k in files]
    kind, body = request_body(data)
    if pairs_set_script(pairs) or sets_script(kind, body, urllib.parse.urlsplit(path).query):
        raise ValueError('The custom JavaScript setting (custom_js) cannot be given a value through the black box')


def validate_request(data):
    op = runtime.validate(OPERATIONS, data)
    if op in BROWSER_OPS:
        session = text_value(data.get('session', 'main'), 'session', nonempty=True)
        if len(session) > 64 or any(ord(c) < 32 for c in session):
            raise ValueError('Invalid session')
    if 'target' in data:
        validate_target(data['target'])
    if op == 'open':
        page_path(data.get('path', '/'))
    if op in {'fill', 'type', 'select'}:
        text_value(data.get('value'), 'value')
    if op == 'press':
        text_value(data.get('key'), 'key', nonempty=True)
    if op in {'pointer', 'drag'}:
        gesture_points(data, op == 'drag' or data.get('action') == 'drag')
    if op == 'wheel':
        finite(data.get('x'), 'x'), finite(data.get('y'), 'y')
    if op in {'wheel', 'scroll'}:
        finite(data.get('delta_x', 0), 'delta_x', -5000, 5000), finite(data.get('delta_y', 0), 'delta_y', -5000, 5000)
    if op == 'wait':
        finite(data.get('seconds', 0.5), 'seconds', 0, 3)
    if op == 'upload':
        text_value(data.get('filename'), 'filename', nonempty=True)
        text_value(data.get('mime_type', 'application/octet-stream'), 'mime_type', nonempty=True)
        if len(base64.b64decode(text_value(data.get('base64'), 'base64'), validate=True)) > MAX_UPLOAD_BYTES:
            raise ValueError('Upload exceeds 1MB')
    if op == 'download' and not re.fullmatch(r'd[0-9]+', data['ref']):
        raise ValueError('download needs a reference from the current snapshot')
    if op == 'api':
        validate_api(data)
    return op


async def read_request(request):
    length = request.headers.get('content-length')
    if length is not None and int(length) > MAX_REQUEST_BYTES:
        raise RequestTooLarge('Request exceeds 3MB')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
            raise RequestTooLarge('Request exceeds 3MB')
        body.extend(chunk)
    return bytes(body)


async def read_response(response):
    content = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=65536):
        content.extend(chunk[:MAX_RESPONSE_BYTES + 1 - len(content)])
        if len(content) > MAX_RESPONSE_BYTES:
            return bytes(content[:MAX_RESPONSE_BYTES]), True
    return bytes(content), False


# -- product lifecycle ---------------------------------------------------------------------------------
async def start_product(fresh):
    started = await asyncio.to_thread(product.start, fresh)
    if started:
        await asyncio.to_thread(runtime.wait_http, product)
    return product.status()


async def close_sessions():
    for context, _page in list(sessions.values()):
        try:
            await context.close()
        except Exception:
            pass
    sessions.clear()


# -- browser sessions ----------------------------------------------------------------------------------
def same_origin(url):
    host = urllib.parse.urlsplit(origin)
    return (url.scheme, url.hostname, url.port) == (host.scheme, host.hostname, host.port)


def product_url(value):
    url = urllib.parse.urlsplit(value)
    if not same_origin(url):
        raise ValueError('Browser navigation outside the product is forbidden')
    return urllib.parse.urlunsplit(('', '', url.path, url.query, url.fragment))


REFUSED_SCRIPT = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Refused by the black box</title>'
                  '</head><body><p>The custom JavaScript setting cannot be given a value through the black box.</p>'
                  '</body></html>')


def page_resource_allowed(path, resource_type):
    """Static implementation files load as assets, never as data read by page scripts."""
    path = urllib.parse.unquote(path, errors='strict')
    return not (static_file(path)) or resource_type in {'script', 'stylesheet', 'image', 'font', 'media', 'manifest', 'texttrack'}


async def new_session(name):
    if len(sessions) >= MAX_SESSIONS:
        raise ValueError('Close an existing browser session before opening another')
    context = await browser.new_context(locale='en-US', timezone_id='UTC', viewport=VIEWPORT,
                                        service_workers='block', accept_downloads=True)

    async def restrict(route):
        request = route.request
        url = urllib.parse.urlsplit(request.url)
        if same_origin(url):
            if not page_resource_allowed(url.path, route.request.resource_type):
                await route.abort()
                return
            if instance_diagnostics(url.path):
                await route.abort()
                return
            if request.is_navigation_request():
                try:
                    page_path(urllib.parse.urlunsplit(('', '', url.path, url.query, url.fragment)))
                except ValueError as exc:
                    # An empty 204 answer cancels the navigation and keeps the current document. A navigation that
                    # starts a download has no frame yet; it is reported like one of the main frame.
                    try:
                        main = request.frame == page.main_frame
                    except PlaywrightError:
                        main = True
                    if main:
                        page._blackbox_blocked = {'path': url.path, 'reason': str(exc)}
                    await route.fulfill(status=204, body='')
                    return
            if sets_script(request.headers.get('content-type', ''), request.post_data_buffer or b'', url.query):
                await route.fulfill(status=403, content_type='text/html; charset=utf-8', body=REFUSED_SCRIPT)
                return
            await route.continue_()
        elif url.scheme in {'data', 'blob'} and not request.is_navigation_request():
            await route.continue_()
        else:
            await route.abort()

    await context.route('**/*', restrict)
    # HTTP routing does not cover WebSocket handshakes; the product offers no public WebSocket feature.
    try:
        await context.route_web_socket('**/*', lambda ws: ws.close())
    except AttributeError:
        pass
    await context.add_init_script(INIT_SCRIPT)
    page = await context.new_page()
    page._blackbox_downloads = {}
    page._blackbox_refs = set()
    page._blackbox_chooser = None
    page._blackbox_status = 200
    page._blackbox_blocked = None

    def document_response(response):
        if response.request.is_navigation_request() and response.frame == page.main_frame:
            page._blackbox_status = response.status

    async def remember_download(download):
        global download_serial
        try:
            # A download of a product URL is held to the page and interface policy, so static front-end files never
            # arrive this way; data the page builds itself (blob) stays.
            relative = ('[page data]' if download.url.startswith('blob:')
                        else download_path(product_url(download.url)))
            if len(page._blackbox_downloads) >= MAX_PENDING_DOWNLOADS:
                raise ValueError('Too many pending downloads')
        except ValueError:
            await download.cancel()
            return
        ref = 'd' + str(download_serial)
        download_serial += 1
        page._blackbox_downloads[ref] = (download, {'ref': ref, 'url': relative,
                                                    'filename': Path(download.suggested_filename).name[:700]})

    page.on('response', document_response)
    page.on('download', remember_download)
    page.on('filechooser', lambda chooser: setattr(page, '_blackbox_chooser', chooser))
    page.on('dialog', lambda dialog: asyncio.ensure_future(dialog.accept()))
    page.set_default_timeout(8000)
    page.set_default_navigation_timeout(30000)
    context.on('page', lambda extra: asyncio.ensure_future(extra.close()) if extra != page else None)
    sessions[name] = (context, page)
    return page


def landing_path(url):
    """The page policy as it applies to a document the browser has landed on."""
    return page_path(product_url(url))


async def enforce_landing(page):
    """Hold every landed document to the page policy. A navigation may be redirected, and the browser follows
    a redirect itself, so the route handler sees only the first request; the document that the navigation
    ends on is the one the caller would read. A document outside the policy is replaced by a blank one and
    reported as a blocked navigation, so no page content, pixels or downloads come from it."""
    blocked = None
    for frame in list(page.frames):
        try:
            url = frame.url
            if url in ('', 'about:blank'):
                continue
            try:
                landing_path(url)
            except ValueError as exc:
                blocked = blocked or {'path': urllib.parse.urlsplit(url).path[:200], 'reason': str(exc)}
                await frame.goto('about:blank')
        except PlaywrightError:
            continue
    if blocked is not None:
        page._blackbox_blocked = blocked
    return blocked is None


async def mask_deployment(page):
    """Instance administration and error pages may show deployment paths; mask them before text and pixels."""
    path = urllib.parse.urlsplit(page.url).path
    if path == '/about' or page._blackbox_status >= 400:
        try:
            await page.evaluate(MASK_SCRIPT, private.pattern)
        except PlaywrightError:
            pass


async def settled(page):
    try:
        await page.wait_for_load_state('domcontentloaded', timeout=10000)
    except PlaywrightTimeout:
        pass


async def read_document(page):
    for attempt in range(6):
        await settled(page)
        try:
            await mask_deployment(page)
            return await page.evaluate(SNAPSHOT_SCRIPT, [ref_serial, {'controls': MAX_CONTROLS, 'text': MAX_TEXT,
                                                                      'value': MAX_VALUE}])
        except PlaywrightError as exc:
            # A navigation replaced the document while it was being read; read the new one.
            if attempt == 5 or not any(x in str(exc) for x in ('Execution context was destroyed', 'navigation',
                                                                 'Cannot find context', 'Frame was detached')):
                raise
            await page.wait_for_timeout(200)


async def snapshot(page):
    global ref_serial
    await enforce_landing(page)
    data = await read_document(page)
    if not await enforce_landing(page):
        # The document moved outside the policy while it was read; that document is not the one reported.
        data = await read_document(page)
    ref_serial += len(data['controls'])
    page._blackbox_refs = {control['ref'] for control in data['controls']}
    result = {'url': product_url(page.url) if page.url != 'about:blank' else 'about:blank',
              'title': await page.title(), 'viewport': data['viewport'], 'scroll': data['scroll'],
              'page_size': data['page_size'], 'text': data['text'], 'text_truncated': data['text_truncated'],
              'controls': data['controls'], 'controls_truncated': data['controls_truncated'],
              'downloads': [meta for _, meta in page._blackbox_downloads.values()]}
    if page._blackbox_chooser is not None:
        result['file_chooser'] = {'multiple': page._blackbox_chooser.is_multiple()}
    if page._blackbox_blocked:
        result['blocked_navigation'], page._blackbox_blocked = page._blackbox_blocked, None
    return result


def locator(page, value):
    validate_target(value)
    if 'ref' in value:
        if value['ref'] not in page._blackbox_refs:
            raise ValueError('Stale or unknown control reference; use the latest snapshot')
        result = page.locator('[data-blackbox-ref="' + value['ref'] + '"]')
    elif 'role' in value:
        result = page.get_by_role(value['role'], name=value.get('name'), exact=value.get('exact', True))
    elif 'label' in value:
        result = page.get_by_label(value['label'], exact=value.get('exact', True))
    elif 'placeholder' in value:
        result = page.get_by_placeholder(value['placeholder'], exact=value.get('exact', True))
    else:
        result = page.get_by_text(value['text'], exact=value.get('exact', True))
    return result.nth(int(value.get('nth', 0)))


async def position(page, data, x, y):
    """Viewport coordinates of a point given in the request's frame."""
    if 'target' in data:
        box = await locator(page, data['target']).bounding_box()
        if not box:
            raise ValueError('Target is not visible')
        if not (0 <= x <= box['width'] and 0 <= y <= box['height']):
            raise ValueError('Coordinates must lie inside the target box')
        return box['x'] + x, box['y'] + y
    if not (0 <= x < VIEWPORT['width'] and 0 <= y < VIEWPORT['height']):
        raise ValueError('Viewport coordinates must lie inside the 1280x900 viewport')
    return x, y


async def pointer_action(page, data):
    action = 'drag' if data['op'] == 'drag' else data.get('action', 'click')
    button = data.get('button', 'left')
    (sx, sy), via, end = gesture_points(data, action == 'drag')
    modifiers = data.get('modifiers', [])
    for key in modifiers:
        await page.keyboard.down(key)
    try:
        x, y = await position(page, data, sx, sy)
        if action == 'click':
            await page.mouse.click(x, y, button=button, click_count=data.get('click_count', 1))
        elif action == 'down':
            await page.mouse.move(x, y)
            await page.mouse.down(button=button)
        elif action == 'up':
            await page.mouse.move(x, y)
            await page.mouse.up(button=button)
        elif action == 'move':
            await page.mouse.move(x, y, steps=4)
        else:
            points = [await position(page, data, px, py) for px, py in via]
            tx, ty = await position(page, data, *end)
            await page.mouse.move(x, y)
            await page.mouse.down(button=button)
            for px, py in points:
                await page.mouse.move(px, py, steps=4)
            await page.mouse.move(tx, ty, steps=int(data.get('steps', 5)))
            await page.mouse.up(button=button)
    finally:
        for key in reversed(modifiers):
            await page.keyboard.up(key)


async def acting(page, action):
    """Run one input action, then wait until a navigation it started has loaded its new document (a navigation
    answered by a download, a refusal or no content leaves the current document in place)."""
    state = {'started': False, 'final': None, 'committed': False, 'failed': False}

    def main_navigation(request):
        return request.is_navigation_request() and request.frame == page.main_frame

    def on_request(request):
        if main_navigation(request):
            state['started'] = True

    def on_response(response):
        if main_navigation(response.request) and not 300 <= response.status < 400:
            state['final'] = time.monotonic()

    def on_navigated(frame):
        if frame == page.main_frame:
            state['committed'] = True

    def on_failed(request):
        if main_navigation(request):
            state['failed'] = True

    listeners = (('request', on_request), ('response', on_response), ('framenavigated', on_navigated),
                 ('requestfailed', on_failed))
    for event, handler in listeners:
        page.on(event, handler)
    try:
        await action()
        await page.wait_for_timeout(SETTLE_MS)
        if state['started']:
            deadline = time.monotonic() + NAVIGATION_WAIT_SEC
            while time.monotonic() < deadline and not (state['committed'] or state['failed']):
                if state['final'] is not None and time.monotonic() - state['final'] > 2:
                    break
                await asyncio.sleep(0.05)
            await settled(page)
    finally:
        for event, handler in listeners:
            page.remove_listener(event, handler)


CODE_SUFFIXES = ('.js', '.mjs', '.cjs', '.css', '.map', '.wasm', '.ts', '.jsx', '.tsx')
CODE_PREFIXES = (b'//# sourceMappingURL', b'//@license', b'{"version":3,', b'"use strict"', b"'use strict'",
                 b'import ', b'import{', b'export ', b'export{', b'self.', b'(function(', b'(()=>', b'!function(',
                 b'var ', b'const ', b'let ', b'function ', b'/*!', b'@charset', b':root{', b':root {', b'define(')


def code_like(filename, content):
    """Front-end code (scripts, style sheets, source maps) is never handed over as a download, whatever its route."""
    head = content[:4096].lstrip(b'\xef\xbb\xbf \t\r\n')
    return Path(filename).suffix.lower() in CODE_SUFFIXES or head.startswith(CODE_PREFIXES) \
        or b'sourceMappingURL=' in content[-2048:]


def scrubbed(content):
    """The local web's loopback address is a detail of this runtime instance; answers show it as [local web]."""
    return content.replace(web_origin, b'[local web]') if web_origin else content


async def api_dispatch(data):
    path = api_path(data['path'])
    method = data.get('method', 'GET')
    auth = data.get('auth')
    if isinstance(auth, str):
        auth = (auth, USERS[auth])
    elif auth is not None:
        auth = tuple(auth)
    kind, body = request_body(data)
    headers = {'content-type': kind, 'accept-encoding': 'identity'}
    for key, value in data.get('headers', {}).items():
        headers[key.lower()] = value
    if data.get('token'):
        headers['x-auth-token'] = data['token']
    kwargs = {'content': body} if body else {}
    if 'multipart' in data:
        headers.pop('content-type', None)
        parts = data['multipart']
        kwargs = {'data': parts.get('fields', {}),
                  'files': {k: (Path(v['filename']).name, base64.b64decode(v['base64'], validate=True),
                                v.get('mime_type', 'application/octet-stream'))
                            for k, v in parts.get('files', {}).items()}}
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=HTTP_TIMEOUT_SEC) as client:
        async with client.stream(method, origin + path, auth=auth, headers=headers, **kwargs) as response:
            content, truncated = await read_response(response)
            status = response.status_code
            response_headers = {k.lower(): scrubbed(v.encode('latin-1', 'replace')).decode('latin-1').replace(origin, '')
                                for k, v in response.headers.items() if k.lower() in RESPONSE_HEADERS}
    content = scrubbed(content)
    try:
        answer = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        answer = content.decode('utf-8', errors='replace')
    if status >= 400:
        answer = redact_value(answer)
        content = private_bytes.sub(b'[private path]', content)
    return {'status': status, 'headers': response_headers, 'body': answer,
            'body_base64': base64.b64encode(content).decode() if data.get('binary') else None, 'truncated': truncated}


def web_dispatch(op, data):
    if op == 'web_put':
        return web.put(data)
    if op == 'web_delete':
        return web.delete(data)
    if op == 'web_list':
        return web.listing()
    return web.requests(data)


async def dispatch(data):
    op = validate_request(data)
    if op == 'help':
        return runtime.help_document(PRODUCT, 'browser', OPERATIONS, limits=LIMITS, notes=NOTES, examples=EXAMPLES,
                                     accounts=[{'username': user, 'password': password, 'administrator': user == 'alice'}
                                               for user, password in USERS.items()])
    if op == 'status':
        return product.status()
    if op == 'reset':
        await close_sessions()
        web.reset()
        return await start_product(True)
    if op == 'restart':
        return await start_product(False)
    if op == 'api':
        return await api_dispatch(data)
    if op in WEB_OPS:
        return web_dispatch(op, data)
    name = data.get('session', 'main')
    if op == 'close':
        if name not in sessions:
            raise ValueError('Unknown browser session')
        context, _page = sessions.pop(name)
        await context.close()
        return {'closed': name}
    page = sessions[name][1] if name in sessions else await new_session(name)
    # A rejected navigation may leave Chromium's error document; a new validated open recovers.
    if op != 'open':
        await enforce_landing(page)
    if op == 'open':
        page._blackbox_chooser = None
        await page.goto(origin + page_path(data.get('path', '/')), wait_until='domcontentloaded')
        await page.wait_for_timeout(150)
    elif op == 'snapshot':
        pass
    elif op == 'screenshot':
        await settled(page)
        await enforce_landing(page)
        await mask_deployment(page)
        if data.get('full_page'):
            height = await page.evaluate('() => document.documentElement.scrollHeight')
            png = await page.screenshot(full_page=True, clip={'x': 0, 'y': 0, 'width': VIEWPORT['width'],
                                                              'height': min(max(height, 1), MAX_SCREENSHOT_HEIGHT)})
            return {'png_base64': base64.b64encode(png).decode(), 'width': VIEWPORT['width'],
                    'height': min(height, MAX_SCREENSHOT_HEIGHT), 'screenshot_truncated': height > MAX_SCREENSHOT_HEIGHT}
        png = await page.screenshot(full_page=False)
        return {'png_base64': base64.b64encode(png).decode(), 'width': VIEWPORT['width'],
                'height': VIEWPORT['height'], 'screenshot_truncated': False}
    elif op == 'download':
        pending = page._blackbox_downloads
        if data['ref'] not in pending:
            raise ValueError('Unknown download reference; use the current snapshot')
        download, meta = pending.pop(data['ref'])
        try:
            if await download.failure():
                raise ValueError('Product download failed')
            path = Path(await download.path())
            with path.open('rb') as stream:
                content = stream.read(MAX_RESPONSE_BYTES + 1)
            if code_like(meta['filename'], content):
                raise ValueError('Script and style sheet downloads are not offered')
            return {**meta, 'size': path.stat().st_size,
                    'body_base64': base64.b64encode(content[:MAX_RESPONSE_BYTES]).decode(),
                    'truncated': len(content) > MAX_RESPONSE_BYTES}
        finally:
            await download.cancel()
            await download.delete()
    elif op == 'back':
        page._blackbox_chooser = None
        await page.go_back(wait_until='domcontentloaded')
    elif op == 'reload':
        page._blackbox_chooser = None
        await page.reload(wait_until='domcontentloaded')
    elif op in {'pointer', 'drag'}:
        await acting(page, lambda: pointer_action(page, data))
    elif op == 'wheel':
        async def wheel():
            x, y = await position(page, data, finite(data['x'], 'x'), finite(data['y'], 'y'))
            await page.mouse.move(x, y)
            await page.mouse.wheel(float(data.get('delta_x', 0)), float(data.get('delta_y', 0)))
        await acting(page, wheel)
    elif op == 'scroll':
        await page.evaluate('([x, y]) => window.scrollBy(x, y)', [float(data.get('delta_x', 0)),
                                                                  float(data.get('delta_y', 0))])
        await page.wait_for_timeout(SETTLE_MS)
    elif op == 'wait':
        await page.wait_for_timeout(int(1000 * float(data.get('seconds', 0.5))))
    elif op == 'upload' and 'target' not in data:
        chooser, page._blackbox_chooser = page._blackbox_chooser, None
        if chooser is None:
            raise ValueError('No file chooser is pending; give the file input as target or open the chooser first')
        await acting(page, lambda: chooser.set_files({'name': Path(data['filename']).name,
                                                      'buffer': base64.b64decode(data['base64']),
                                                      'mimeType': data.get('mime_type', 'application/octet-stream')}))
    elif op in {'type', 'press'} and 'target' not in data:
        if op == 'type':
            await acting(page, lambda: page.keyboard.insert_text(data['value']))
        else:
            await acting(page, lambda: page.keyboard.press(data['key']))
    else:
        loc = locator(page, data['target'])
        if op == 'click':
            await acting(page, lambda: loc.click(button=data.get('button', 'left'),
                                                 click_count=data.get('click_count', 1),
                                                 modifiers=data.get('modifiers') or None))
        elif op == 'fill':
            await acting(page, lambda: loc.fill(data['value']))
        elif op == 'type':
            async def insert():
                await loc.focus()
                await page.keyboard.insert_text(data['value'])
            await acting(page, insert)
        elif op == 'select':
            await acting(page, lambda: loc.select_option(data['value']))
        elif op == 'check':
            wanted = data.get('checked', True)
            proxied = None
            if 'ref' in data['target']:
                proxied = await page.evaluate(
                    'ref => { const e = document.querySelector(\'[data-blackbox-state="\' + ref + \'"]\'); '
                    'return e ? e.checked : null; }', data['target']['ref'])
            if proxied is None:
                await acting(page, lambda: loc.set_checked(wanted))
            elif proxied != wanted:
                await acting(page, lambda: loc.click())
        elif op == 'press':
            await acting(page, lambda: loc.press(data['key']))
        elif op == 'upload':
            await acting(page, lambda: loc.set_input_files({'name': Path(data['filename']).name,
                                                            'mimeType': data.get('mime_type',
                                                                                 'application/octet-stream'),
                                                            'buffer': base64.b64decode(data['base64'])}))
    return await snapshot(page)


@app.post('/rpc')
async def rpc(request: Request):
    global in_flight
    if in_flight >= MAX_IN_FLIGHT:
        return JSONResponse({'error': 'Busy', 'detail': 'Too many pending requests; retry later'}, 429)
    in_flight += 1
    started = time.monotonic()
    data = None
    try:
        async with asyncio.timeout(RPC_TIMEOUT_SEC):
            data = runtime.strict_json_loads(await read_request(request))
            async with lock:
                result = await dispatch(data)
        code = 200
    except RequestTooLarge as error:
        result, code = {'error': 'RequestTooLarge', 'detail': str(error)}, 413
    except TimeoutError:
        result, code = {'error': 'TimeoutError', 'detail': 'Black-box request deadline exceeded'}, 408
    except Exception as error:
        # Never return private filesystem paths or stack traces.
        result, code = {'error': type(error).__name__, 'detail': redact(redact_value(str(error).split('Call log:')[0]))[:600]}, 400
    finally:
        in_flight -= 1
    audit.record(data.get('op', 'help') if isinstance(data, dict) else None, code, time.monotonic() - started)
    return JSONResponse(result, code)


def private_roots(*paths):
    """Deployment roots as whole path prefixes (not inside another path or word), with what follows them."""
    roots = sorted({str(Path(p)) for p in [*STATIC_PRIVATE, *paths] if p and str(p) != '/'}, key=len, reverse=True)
    return r'(?<![\w.~/-])(?:' + '|'.join(re.escape(r) for r in roots) + r''')(?![\w.~-])(?:/[^\s"'<>]*)?'''


async def main(argv=None):
    global config, origin, product, web, web_origin, audit, redact, private, private_bytes, browser
    config = runtime.options().parse_args(argv)
    origin = f'http://127.0.0.1:{config.port}'
    work = Path(config.work)
    work.mkdir(parents=True, exist_ok=True)
    web = localweb.LocalWeb()
    proxy = f'http://127.0.0.1:{web.start()}'
    web_origin = proxy.removeprefix('http://').encode()
    product = runtime.Product(config, log=runtime.BoundedLog(config.log_dir),
                              env={'HTTP_PROXY': proxy, 'http_proxy': proxy, 'HTTPS_PROXY': proxy,
                                   'https_proxy': proxy, 'NO_PROXY': 'localhost,127.0.0.1,::1',
                                   'no_proxy': 'localhost,127.0.0.1,::1'})
    audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
    roots = (config.solution, config.state, config.work, config.log_dir,
             product.account().pw_dir, *product.directories.values(), Path(__file__).resolve().parent)
    redact = runtime.redactor(*roots)
    private = re.compile(private_roots(*roots))
    private_bytes = re.compile(private.pattern.encode())
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=['--no-sandbox'],
                                                       downloads_path=str(work / 'downloads'))
            # A product that fails to start is reported by status; the runtime keeps serving.
            await start_product(True)
            sock = runtime.listen(config.socket, config.socket_mode)
            server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level='warning'))
            runtime.exit_on_sigterm()
            try:
                await server.serve(sockets=[sock])
            finally:
                await close_sessions()
                await asyncio.to_thread(product.stop)
    finally:
        web.stop()


if __name__ == '__main__':
    asyncio.run(main())
