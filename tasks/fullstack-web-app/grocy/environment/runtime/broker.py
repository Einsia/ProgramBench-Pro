#!/usr/bin/env python3
"""Grocy runtime: browser actions, public product interfaces and instance lifecycle."""
from __future__ import annotations

import asyncio
import base64
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
from web_policy import NAVIGATION_GUARD, restrict_script_request  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, async_playwright  # noqa: E402

PRODUCT = 'Grocy 4.7.1'
CLOCK = '2026-03-10T09:00:00Z'
VIEWPORT = {'width': 1280, 'height': 900}
# The baseline accounts every fresh data directory starts with. Their passwords cannot be observed otherwise.
USERS = {'admin': 'admin'}
MAX_REQUEST_BYTES = 3_000_000
MAX_RESPONSE_BYTES = 2_000_000
MAX_UPLOAD_BYTES = 1_000_000
MAX_IN_FLIGHT = 8
RPC_TIMEOUT_SEC = 90
HTTP_TIMEOUT_SEC = 30
MAX_SESSIONS = 12
MAX_PENDING_DOWNLOADS = 4
MAX_CONTROLS = 400
MAX_TEXT = 20_000
MAX_VALUE = 4_000
MAX_SCREENSHOT_HEIGHT = 4_000
SETTLE_MS = 250
NAVIGATION_WAIT_SEC = 20
REQUEST_HEADERS = {'accept', 'authorization', 'content-type', 'if-match', 'if-none-match', 'if-modified-since',
                   'if-unmodified-since', 'range', 'content-range', 'grocy-api-key', 'cookie'}
RESPONSE_HEADERS = {'content-type', 'location', 'link', 'etag', 'www-authenticate', 'retry-after', 'allow', 'dav',
                    'cache-control', 'x-pagination-total-pages', 'x-pagination-result-count', 'x-ratelimit-limit',
                    'x-ratelimit-remaining', 'x-ratelimit-reset', 'range', 'content-range', 'content-length',
                    'last-modified', 'accept-ranges', 'content-disposition'}
METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
MODIFIERS = ['Shift', 'Control', 'Alt', 'Meta']
API_PREFIXES = ('/api/',)
API_EXACT = ()
DIAGNOSTICS = ('/debug', '/metrics')
NOT_PAGES = ('/api', '/css/', '/img/', '/js/', '/packages/', '/viewjs/', '/uisounds/', '/data/',
             '/manifest', '/favicon', '/robots.txt', '/config', '/localization/', '/migrations/',
             '/services/', '/controllers/', '/middleware/', '/plugins/', '/vendor/')
SYSTEM_PRIVATE = ['/opt/blackbox', '/opt/browsers', '/opt/venv', '/usr/local/lib', '/usr/lib', '/var/www']
LOGIN_REUSE_SEC = 420
logins = {}  # (username, password) -> (session token, monotonic time of the sign-in)

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
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, limits and baseline accounts.',
             'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the product process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Restart the product with an empty data directory (its initial admin/admin state) and '
                         'close all browser sessions.'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Restart the product process with the same data directory; browser sessions and their '
                           'cookies stay, so reload pages afterwards.'},
    'api': {'kind': 'http',
            'summary': 'One HTTP request to the REST API under /api/. OpenAPI: /api/openapi/specification. '
                       'Calendar export: /api/calendar/ical. Redirects are not followed.',
            'fields': {
                'path': {'type': 'string', 'required': True,
                         'description': 'Absolute product path with optional query, for example '
                                        '/api/objects/products?limit=10; no dot segments.'},
                'method': {'type': 'string', 'enum': METHODS, 'description': 'HTTP method; default GET.'},
                'auth': {'type': ['string', 'array'], 'items': {'type': 'string'},
                         'description': 'A baseline username (admin) or [username, password]. The runtime signs in '
                                        'through the normal /login form (a form POST with the fields username and '
                                        'password) and sends the session cookie that sign-in sets with the request: '
                                        'Grocy names it grocy_session_access_token, and when a successful sign-in sets '
                                        'no cookie of that name, every cookie it set is sent. A refused sign-in is '
                                        'returned as the answer.'},
                'fresh_auth': {'type':'boolean','description':'With auth, create a new login session instead of reusing its cached cookie.'},
                'token': {'type': 'string', 'description': 'API key, sent as the GROCY-API-KEY header.'},
                'headers': {'type': 'object', 'description': 'Request headers; allowed: ' +
                            ', '.join(sorted(REQUEST_HEADERS)) + '. Use at most one of auth, token and an '
                            'GROCY-API-KEY or Cookie header.'},
                'json': {'type': ['object', 'array', 'string', 'number', 'boolean'],
                         'description': 'JSON request body (at most one body field).'},
                'body': {'type': 'string', 'description': 'Text request body.'},
                'body_base64': {'type': 'string', 'description': 'Request body bytes, base64 encoded.'},
                'multipart': {'type': 'object',
                              'description': 'multipart/form-data body {fields: {name: text}, files: {name: '
                                             '{filename, base64, mime_type}}}.'},
                'content_type': {'type': 'string', 'description': 'Content-Type of the body; default '
                                                                  'application/json.'},
                'binary': {'type': 'boolean', 'description': 'Also return the response bytes as body_base64.'},
            }},
    'open': {'kind': 'gui', 'summary': 'Open a product page in a session (the session is created if needed).',
             'fields': {'session': SESSION,
                        'path': {'type': 'string', 'description': 'Absolute page path with optional query or '
                                                                  'fragment, for example /stockoverview; default /.'}}},
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
                                       'target, of the focused element. Code editors take their text this way.',
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
                                        'first, or without a target on the focused element.',
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
    'wheel': {'kind': 'gui', 'summary': 'Turn the mouse wheel over a point (scrolls the list, editor or page '
                                        'under it).',
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
NOTES = [
    'A fresh data directory has the upstream default administrator account admin/admin.',
    'The product clock starts at 2026-03-10 09:00:00 UTC on each process start and then advances normally. '
    'Browser date/time begins at the same instant; locale en-US, timezone UTC, viewport 1280x900.',
    'Browser and API operations share product state. Browser sessions have separate cookies; API auth signs in '
    'separately. API paths, methods, request bodies and query parameters are described by /api/openapi/specification.',
    'Every browser action returns a snapshot. Refs are derived from control content and valid for the latest snapshot.',
    'Only same-origin product pages may open. APIs and static resources cannot open as documents, including in '
    'frames or after redirects. External resources are blocked. Native dialogs are accepted; new tabs are closed.',
    'Paths with dot segments, encoded path separators or control characters are rejected.',
    'File choosers appear as file_chooser in snapshots. Supply their bytes with upload; only basenames are accepted.',
    'File downloads are limited to product data: text, JSON, CSV, iCalendar, PDF and common raster images. '
    'Scripts, styles, archives and source maps are not available as downloads.',
    'File API names use standard base64 encoding of the basename as documented by the product. '
    'Downloads and file API transfers are limited to the data file types listed above.',
    'Rich text uses type; clear it with ControlOrMeta+A and Backspace. Native date/color fields can be filled.',
    'Deployment filesystem paths and implementation stack traces in error responses are redacted.',
]
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'response_bytes': MAX_RESPONSE_BYTES, 'upload_bytes': MAX_UPLOAD_BYTES,
          'sessions': MAX_SESSIONS, 'pending_downloads_per_session': MAX_PENDING_DOWNLOADS,
          'controls': MAX_CONTROLS, 'text_characters': MAX_TEXT, 'value_characters': MAX_VALUE,
          'in_flight': MAX_IN_FLIGHT, 'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'http_timeout_seconds': HTTP_TIMEOUT_SEC,
          'screenshot_full_page_height': MAX_SCREENSHOT_HEIGHT, 'wheel_and_scroll_delta': [-5000, 5000],
          'drag_via_points': 60, 'drag_steps': [1, 100], 'wait_seconds': 3}
EXAMPLES = [{'op': 'api', 'path': '/api/openapi/specification', 'auth': 'admin'},
            {'op': 'api', 'path': '/api/objects/products', 'auth': 'admin'},
            {'op': 'api', 'path': '/api/objects/locations', 'method': 'POST', 'auth': 'admin',
             'json': {'name': 'Pantry'}},
            {'op': 'open', 'path': '/login'}, {'op': 'screenshot'}, {'op': 'restart'}]

# Browser behavior shared by the reference and your application.
INIT_SCRIPT = r'''(() => {
  // The offline container reports no network, which makes the product's service worker replace every page with an
  // offline notice; every application page receives the same online status.
  try { Object.defineProperty(Navigator.prototype, 'onLine', {get: () => true, configurable: true}); } catch (e) {}
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
  const out = [], seen = new Set(), signatures = new Map(); let truncated = false;
  for (const e of document.querySelectorAll(selector)) {
    if (e.tagName === "INPUT" && e.type === "hidden") continue;
    const role = e.getAttribute("role");
    if (role && !roles.has(role) && !["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA", "SUMMARY"].includes(e.tagName)
        && !e.isContentEditable) continue;
    const proxy = proxyOf(e), el = proxy || e;
    if (seen.has(el) || seen.has(e)) continue;
    if (!proxy && !shown(e)) continue;
    if (out.length >= limits.controls) { truncated = true; break; }
    const signature = JSON.stringify([start, e.tagName, role, e.getAttribute("name"), e.getAttribute("aria-label"),
      e.getAttribute("id"), e.getAttribute("href"), clip(el.innerText, 300), e.type || ""]);
    const occurrence = signatures.get(signature) || 0; signatures.set(signature, occurrence + 1);
    let hash = 2166136261; for (const ch of signature + ":" + occurrence) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619);
    const ref = "e" + (hash >>> 0);
    el.setAttribute("data-blackbox-ref", ref);
    if (proxy) e.setAttribute("data-blackbox-state", ref);
    seen.add(el); seen.add(e);
    const r = el.getBoundingClientRect();
    const label = e.labels ? [...e.labels].map(x => x.innerText).join(" ") : "";
    const c = {ref, tag: e.tagName.toLowerCase(), role, text: clip(el.innerText, 300)};
    const extra = {aria: clip(e.getAttribute("aria-label"), 300), label: clip(label, 300),
                   title: clip(e.getAttribute("title") || e.getAttribute("data-original-title") || e.getAttribute("data-tooltip-content"), 300),
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


def instance_diagnostics(path):
    decoded = posixpath.normpath(urllib.parse.unquote(path, errors='strict'))
    return any(decoded == root or decoded.startswith(root + '/') for root in DIAGNOSTICS)


def product_path(value):
    """An absolute product path: no scheme, host, dot segments, backslashes or control characters."""
    if not isinstance(value, str) or not value.startswith('/') or value.startswith('//'):
        raise ValueError('Use an absolute product path, such as /stockoverview; URLs are forbidden.')
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Control characters are forbidden')
    parsed = urllib.parse.urlsplit(value)
    decoded = urllib.parse.unquote(parsed.path, errors='strict')
    segments = decoded.split('/')
    if parsed.scheme or parsed.netloc or '\\' in value or '\\' in decoded or decoded.startswith('//') \
            or any(x in ('.', '..') for x in segments):
        raise ValueError('Invalid product path')
    if any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        raise ValueError('Control characters are forbidden')
    if re.search(r'%[0-9a-fA-F]{2}', decoded):
        raise ValueError('Nested percent encoding is forbidden in paths')
    if instance_diagnostics(parsed.path):
        raise ValueError('Instance diagnostics and runtime profiles are not exposed by the black box')
    return value


FILE_SUFFIXES = {'.txt', '.json', '.csv', '.ics', '.ical', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}


def filename(value):
    if not isinstance(value, str) or not value or len(value.encode()) > 240 or value in ('.', '..') \
            or any(ord(c) < 32 or ord(c) == 127 for c in value) or '/' in value or '\\' in value:
        raise ValueError('File name must be a basename of at most 240 bytes without control characters')
    if Path(value).suffix.lower() not in FILE_SUFFIXES:
        raise ValueError('File type is not offered by the data-file exchange')
    return value


def api_path(value):
    value = product_path(value)
    path = urllib.parse.unquote(urllib.parse.urlsplit(value).path, errors='strict')
    if not path.startswith(API_PREFIXES):
        raise ValueError('HTTP access exposes /api/; use browser operations for product pages')
    if path.startswith('/api/files/'):
        parts = path.split('/')
        if len(parts) != 5:
            raise ValueError('File API paths require a group and encoded basename')
        for name in parts[4].split('_'):
            try:
                filename(base64.b64decode(name, validate=True).decode('utf-8'))
            except (ValueError, UnicodeError) as exc:
                raise ValueError('Invalid encoded data-file name') from exc
    return value


def page_path(value):
    value = product_path(value)
    path = urllib.parse.unquote(urllib.parse.urlsplit(value).path, errors='strict').lower()
    if path.startswith(NOT_PAGES) or re.search(r'\.(?:js|mjs|cjs|css|map|json|php|html?|wasm|txt|xml|zip|gz|svg|png|jpe?g|woff2?|ttf)$', path):
        raise ValueError('APIs and static resources cannot open as browser documents; use api for product interfaces')
    return value


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


def validate_api(data):
    path = api_path(data['path'])
    method = data.get('method', 'GET')
    auth = data.get('auth')
    if isinstance(auth, str):
        if auth not in USERS:
            raise ValueError('Use [username, password] for an account other than admin')
    elif auth is not None and (len(auth) != 2 or not all(isinstance(x, str) for x in auth)):
        raise ValueError('auth must be a baseline username or [username, password]')
    if data.get('fresh_auth') and auth is None:
        raise ValueError('fresh_auth requires auth')
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
    if sum((auth is not None, 'token' in data, 'grocy-api-key' in lowered, 'cookie' in lowered, 'authorization' in lowered)) > 1:
        raise ValueError('Use one authentication method: auth, token, GROCY-API-KEY, Cookie, or Authorization')
    if len({'json', 'body', 'body_base64', 'multipart'} & data.keys()) > 1:
        raise ValueError('Use only one request body format')
    if 'body_base64' in data:
        base64.b64decode(data['body_base64'], validate=True)
    header_value(data.get('content_type', 'application/json'), 'content_type')
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
            filename(value.get('filename'))
            text_value(value.get('mime_type', 'application/octet-stream'), 'mime_type', nonempty=True)
            base64.b64decode(text_value(value.get('base64'), 'base64'), validate=True)


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
        filename(data.get('filename'))
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
    if fresh:
        logins.clear()
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


async def new_session(name):
    if len(sessions) >= MAX_SESSIONS:
        raise ValueError('Close an existing browser session before opening another')
    context = await browser.new_context(locale='en-US', timezone_id='UTC', viewport=VIEWPORT,
                                        service_workers='block', accept_downloads=True)

    async def restrict(route):
        url = urllib.parse.urlsplit(route.request.url)
        if same_origin(url):
            if instance_diagnostics(url.path):
                await route.abort()
                return
            if route.request.is_navigation_request():
                try:
                    page_path(urllib.parse.urlunsplit(('', '', url.path, url.query, url.fragment)))
                except ValueError as exc:
                    # Data attachments may trigger a browser download. If they instead
                    # become documents, enforce_landing still blocks their content.
                    if url.path.startswith('/api/files/') or url.path == '/api/calendar/ical':
                        try:
                            api_path(urllib.parse.urlunsplit(('', '', url.path, url.query, '')))
                            await route.continue_()
                            return
                        except ValueError:
                            pass
                    # An empty 204 answer cancels the navigation and keeps the current document. A navigation that
                    # starts a download has no frame yet; it is reported like one of the main frame.
                    try:
                        main = route.request.frame == page.main_frame
                    except PlaywrightError:
                        main = True
                    if main:
                        page._blackbox_blocked = {'path': url.path, 'reason': str(exc)}
                    await route.fulfill(status=204, body='')
                    return
            if await restrict_script_request(route, origin, api_path, page_path):
                return
            await route.continue_()
        elif url.scheme in {'data', 'blob'} and not route.request.is_navigation_request():
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
    await context.add_init_script(NAVIGATION_GUARD)
    from datetime import datetime
    await context.clock.install(time=datetime.fromisoformat(CLOCK.replace('Z', '+00:00')))
    page = await context.new_page()
    page._blackbox_downloads = {}
    page._blackbox_refs = set()
    page._blackbox_chooser = None
    page._blackbox_status = 200
    page._blackbox_frame_status = {}
    page._blackbox_blocked = None

    def document_response(response):
        if response.request.is_navigation_request():
            page._blackbox_frame_status[response.url] = response.status
            if response.frame == page.main_frame:
                page._blackbox_status = response.status

    async def remember_download(download):
        try:
            await enforce_landing(page)
            filename(download.suggested_filename)
            # A download of a product URL is held to the interface policy of op api, so static assets, the service
            # worker and application documents never arrive this way; data the page builds itself (blob) stays.
            relative = ('[page data]' if download.url.startswith('blob:')
                        else api_path(product_path(product_url(download.url))))
            if len(page._blackbox_downloads) >= MAX_PENDING_DOWNLOADS:
                raise ValueError('Too many pending downloads')
        except ValueError:
            await download.cancel()
            return
        import hashlib
        ref = 'd' + str(int(hashlib.sha256((relative + download.suggested_filename).encode()).hexdigest()[:12], 16))
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


CODE_SUFFIXES = ('.js', '.mjs', '.cjs', '.css', '.map', '.wasm', '.ts', '.vue', '.jsx', '.tsx')
CODE_PREFIXES = (b'//# sourceMappingURL', b'{"version":3,', b'"use strict"', b"'use strict'", b'import ', b'import{',
                 b'export ', b'export{', b'self.', b'if(!self.', b'try{self', b'(function(', b'(()=>', b'!function(',
                 b'var ', b'const ', b'let ', b'function ', b'/*!', b'@charset', b':root{', b'define(')


def code_like(filename, content):
    """Front-end code (scripts, style sheets, source maps) is never handed over as a download, whatever its route."""
    head = content[:4096].lstrip(b'\xef\xbb\xbf \t\r\n')
    return Path(filename).suffix.lower() in CODE_SUFFIXES or head.startswith(CODE_PREFIXES) \
        or b'sourceMappingURL=' in content[-2048:]


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
    for frame in page.frames:
        status = (page._blackbox_status if frame == page.main_frame else
                  page._blackbox_frame_status.get(frame.url, 200))
        if status >= 400:
            try:
                await frame.evaluate(MASK_SCRIPT, private.pattern)
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
            limits = {'controls': MAX_CONTROLS, 'text': MAX_TEXT, 'value': MAX_VALUE}
            data = await page.evaluate(SNAPSHOT_SCRIPT, ['main', limits])
            for frame in page.frames:
                if frame == page.main_frame or frame.url in ('', 'about:blank'):
                    continue
                landing_path(frame.url)
                element = await frame.frame_element()
                box = await element.bounding_box()
                if not box or not await element.is_visible():
                    continue
                part = await frame.evaluate(SNAPSHOT_SCRIPT, [product_url(frame.url), limits])
                data['text'] += '\n' + part['text']
                for control in part['controls']:
                    control['bounds'][0] += round(box['x'])
                    control['bounds'][1] += round(box['y'])
                    data['controls'].append(control)
            data['text_truncated'] = data['text_truncated'] or len(data['text']) > MAX_TEXT
            data['text'] = data['text'][:MAX_TEXT]
            data['controls_truncated'] = data['controls_truncated'] or len(data['controls']) > MAX_CONTROLS
            data['controls'] = data['controls'][:MAX_CONTROLS]
            return data
        except PlaywrightError as exc:
            # A navigation replaced the document while it was being read; read the new one.
            transient = ('detached' in str(exc).lower() or any(x in str(exc) for x in
                         ('Execution context was destroyed', 'navigation', 'Cannot find context')))
            if attempt == 5 or not transient:
                raise
            await page.wait_for_timeout(200)


async def snapshot(page):
    global ref_serial
    await enforce_landing(page)
    data = await read_document(page)
    if not await enforce_landing(page):
        # The document moved outside the policy while it was read; that document is not the one reported.
        data = await read_document(page)
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


async def locator(page, value):
    validate_target(value)
    if 'ref' in value and value['ref'] not in page._blackbox_refs:
        raise ValueError('Stale or unknown control reference; use the latest snapshot')
    candidates = []
    for frame in page.frames:
        if frame.url not in ('', 'about:blank'):
            landing_path(frame.url)
        if 'ref' in value:
            result = frame.locator('[data-blackbox-ref="' + value['ref'] + '"]')
        elif 'role' in value:
            result = frame.get_by_role(value['role'], name=value.get('name'), exact=value.get('exact', True))
        elif 'label' in value:
            result = frame.get_by_label(value['label'], exact=value.get('exact', True))
        elif 'placeholder' in value:
            result = frame.get_by_placeholder(value['placeholder'], exact=value.get('exact', True))
        else:
            result = frame.get_by_text(value['text'], exact=value.get('exact', True))
        for index in range(await result.count()):
            item = result.nth(index)
            if await item.is_visible() or 'label' in value:
                candidates.append(item)
    index = int(value.get('nth', 0))
    if index >= len(candidates):
        raise ValueError('No matching visible control; use a current snapshot')
    return candidates[index]


async def position(page, data, x, y):
    """Viewport coordinates of a point given in the request's frame."""
    if 'target' in data:
        box = await (await locator(page, data['target'])).bounding_box()
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


async def fetch(client, method, path, headers, kwargs, auth=None):
    async with client.stream(method, origin + path, auth=auth, headers=headers, **kwargs) as response:
        content, truncated = await read_response(response)
        reply = {k.lower(): v.replace(origin, '') for k, v in response.headers.items() if k.lower() in RESPONSE_HEADERS}
        return response.status_code, reply, content, truncated


# Sign in through the product's ordinary form and keep its session cookie as a Cookie header value. Grocy's cookie
# is grocy_session_access_token; an implementation that names its session cookie differently gets every cookie its
# successful sign-in set (a sign-in that redirects back to /login counts as refused).
async def session_token(client, credentials, fresh=False):
    held = logins.get(credentials)
    if held and not fresh and time.monotonic() - held[1] < LOGIN_REUSE_SEC:
        return held[0], None
    logins.pop(credentials, None)
    response = await client.post(origin + '/login', data={'username': credentials[0], 'password': credentials[1]})
    location = response.headers.get('location', '').replace(origin, '')
    token = response.cookies.get('grocy_session_access_token')
    if token:
        cookie = 'grocy_session_access_token=' + token
    elif response.cookies and not urllib.parse.urlsplit(location).path.startswith('/login'):
        cookie = '; '.join(f'{name}={value}' for name, value in response.cookies.items())
    else:
        content = await response.aread()
        return None, (response.status_code, {'location': location}, content, False)
    logins[credentials] = (cookie, time.monotonic())
    return cookie, None


async def api_dispatch(data):
    path = api_path(data['path'])
    method = data.get('method', 'GET')
    auth = data.get('auth')
    if isinstance(auth, str):
        auth = (auth, USERS[auth])
    elif auth is not None:
        auth = tuple(auth)
    headers = {'content-type': data.get('content_type', 'application/json')}
    for key, value in data.get('headers', {}).items():
        headers[key.lower()] = value
    if data.get('token'):
        headers['grocy-api-key'] = data['token']
    kwargs = {}
    if 'json' in data:
        kwargs['json'] = data['json']
    elif 'body' in data:
        kwargs['content'] = data['body'].encode()
    elif 'body_base64' in data:
        kwargs['content'] = base64.b64decode(data['body_base64'], validate=True)
    elif 'multipart' in data:
        headers.pop('content-type', None)
        parts = data['multipart']
        kwargs = {'data': parts.get('fields', {}),
                  'files': {k: (Path(v['filename']).name, base64.b64decode(v['base64'], validate=True),
                                v.get('mime_type', 'application/octet-stream'))
                            for k, v in parts.get('files', {}).items()}}
    # API auth uses the normal login session, while token sends an API key.
    signed = auth is not None
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=HTTP_TIMEOUT_SEC) as client:
        answer = None
        if signed:
            token, answer = await session_token(client, auth, fresh=data.get('fresh_auth',False))
            if token:
                headers['cookie'] = token
        if answer is None:
            answer = await fetch(client, method, path, headers, kwargs, None if signed else auth)
            if signed and answer[0] == 401:
                token, refused = await session_token(client, auth, fresh=True)
                if token:
                    headers['cookie'] = token
                    answer = await fetch(client, method, path, headers, kwargs)
                else:
                    answer = refused
    status, reply, content, truncated = answer
    try:
        body = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = content.decode('utf-8', errors='replace')
    if status >= 400:
        body = redact_value(body)
        if isinstance(body, dict):
            body = {k: v for k, v in body.items() if k not in {'trace', 'stacktrace', 'file', 'line'}}
            content = json.dumps(body, ensure_ascii=False).encode()
        else:
            content = private_bytes.sub(b'[private path]', content)
    return {'status': status, 'headers': reply, 'body': body,
            'body_base64': base64.b64encode(content).decode() if data.get('binary') else None, 'truncated': truncated}


async def dispatch(data):
    op = validate_request(data)
    if op == 'help':
        return runtime.help_document(PRODUCT, 'browser', OPERATIONS, limits=LIMITS, notes=NOTES, examples=EXAMPLES,
                                     accounts=[{'username': user, 'password': password,
                                                'administrator': True}
                                               for user, password in USERS.items()])
    if op == 'status':
        return product.status()
    if op == 'reset':
        await close_sessions()
        return await start_product(True)
    if op == 'restart':
        return await start_product(False)
    if op == 'api':
        return await api_dispatch(data)
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
                raise ValueError('Script, style sheet and source map downloads are not offered')
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
        loc = await locator(page, data['target'])
        if op == 'click':
            await acting(page, lambda: loc.click(button=data.get('button', 'left'),
                                                 click_count=data.get('click_count', 1),
                                                 modifiers=data.get('modifiers') or None))
        elif op == 'fill':
            async def fill_and_notify():
                await loc.fill(data['value'])
                # Notify ordinary keyboard-based form listeners after replacement.
                await loc.press('End')
            await acting(page, fill_and_notify)
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
                for frame in page.frames:
                    proxied = await frame.evaluate(
                        'ref => { const e = document.querySelector(\'[data-blackbox-state="\' + ref + \'"]\'); '
                        'return e ? e.checked : null; }', data['target']['ref'])
                    if proxied is not None:
                        break
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
    roots = sorted({str(Path(p)) for p in [*SYSTEM_PRIVATE, *paths] if p and str(p) != '/'}, key=len, reverse=True)
    return r'(?<![\w.~/-])(?:' + '|'.join(re.escape(r) for r in roots) + r''')(?![\w.~-])(?:/[^\s"'<>]*)?'''


async def main(argv=None):
    global config, origin, product, audit, redact, private, private_bytes, browser
    config = runtime.options().parse_args(argv)
    origin = f'http://127.0.0.1:{config.port}'
    work = Path(config.work)
    work.mkdir(parents=True, exist_ok=True)
    product = runtime.Product(config, log=runtime.BoundedLog(config.log_dir), env={
        'LD_PRELOAD': '/usr/local/lib/faketime/libfaketime.so.1',
        'FAKETIME': '@2026-03-10 09:00:00', 'FAKETIME_DONT_FAKE_MONOTONIC': '1', 'TZ': 'UTC'})
    audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
    roots = (config.solution, config.state, config.work, config.log_dir, Path(__file__).resolve().parent)
    redact = runtime.redactor(*roots)
    private = re.compile(private_roots(*roots))
    private_bytes = re.compile(private.pattern.encode())
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


if __name__ == '__main__':
    asyncio.run(main())
