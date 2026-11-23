#!/usr/bin/env python3
"""Navidrome runtime for a single application instance.

Browser, HTTP and product data operations use the same restricted interface
for the reference and your application.
"""

from __future__ import annotations

import asyncio
import base64
from contextlib import ExitStack, contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import posixpath
import re
import stat
import sys
import time
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, async_playwright  # noqa: E402

PRODUCT = 'Navidrome 0.64.2'
VIEWPORT = {'width': 1280, 'height': 900}
# The music library is MUSIC_DIR inside the instance; every response and page shows it as /music.
LIBRARY_ALIAS = '/music'
LIBRARY_MTIME = 1_700_000_000
MAX_LIBRARY_FILE = 2_000_000
MAX_LIBRARY_ENTRIES = 1000
MAX_LIBRARY_PATH = 400
MAX_LIBRARY_SEGMENT = 200
LIBRARY_SUFFIXES = ('.mp3', '.flac', '.ogg', '.oga', '.opus', '.wav', '.m4a', '.aac', '.aiff', '.aif', '.wma', '.ape',
                    '.wv', '.mpc', '.dsf', '.jpg', '.jpeg', '.png', '.webp', '.m3u', '.m3u8', '.nsp', '.lrc', '.txt',
                    '.srt', '.ttml', '.yaml', '.yml')
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
REQUEST_HEADERS = {'accept', 'x-nd-authorization', 'x-nd-client-unique-id', 'range', 'if-none-match',
                   'if-modified-since', 'if-range'}
RESPONSE_HEADERS = {'content-type', 'content-disposition', 'content-range', 'accept-ranges', 'etag', 'last-modified',
                    'location', 'x-total-count', 'x-nd-authorization', 'x-content-duration', 'www-authenticate'}
METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
MODIFIERS = ['Shift', 'Control', 'Alt', 'Meta']
# Product HTTP interfaces are reached with op api, never opened as browser pages.
API_PREFIXES = ('/api/', '/rest/', '/auth/')
# Public share routes reachable with op api: the share, its playlist export, its audio, download and image routes.
# The front-end bundle served below /share/ is not a product answer and stays closed.
SHARE_API = re.compile(r'/share/(?:(?:s|d|img)/[^/]+|[^/]+(?:/m3u)?)')
# Requests of a page that are passed on as they are: static front-end files and media answers.
STATIC_SUFFIXES = ('.js', '.mjs', '.css', '.map', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.woff', '.woff2',
                   '.ttf', '.otf', '.mp3', '.flac', '.ogg', '.oga', '.opus', '.wav', '.m4a', '.aac', '.webmanifest')
MEDIA_ROUTES = ('/rest/stream', '/rest/download', '/rest/getCoverArt', '/rest/getAvatar', '/share/s/', '/share/d/', '/share/img/')
# Server-sent event streams never end; the runtime does not carry them.
STREAMS = ('/api/events',)
DIAGNOSTICS = ('/debug',)
# A public share page: one path segment after /share/ (the share image route has more segments).
SHARE_PAGE = re.compile(r'/share/[A-Za-z0-9_-]+')
# Deployment locations that never reach the caller (error responses, configuration responses).
STATIC_PRIVATE = ['/opt/blackbox', '/opt/browsers', '/opt/venv']

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
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, limits and the library path.',
             'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the product process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Restart the product with an empty data directory and an empty music library (the first-run '
                         'state, without accounts) and close all browser sessions.'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Restart the product process with the same data directory and music library; browser '
                           'sessions and their cookies stay, so reload pages afterwards. The product looks at the '
                           'library again while it starts.'},
    'api': {'kind': 'http',
            'summary': 'One HTTP request to the product: the OpenSubsonic API under /rest/, the native API under '
                       '/api/, authentication under /auth/ and public share addresses under /share/. Redirects are '
                       'not followed.',
            'fields': {
                'path': {'type': 'string', 'required': True,
                         'description': 'Absolute product path with optional query, for example '
                                        '/rest/ping?u=name&p=password&v=1.16.1&c=client&f=json; no dot segments.'},
                'method': {'type': 'string', 'enum': METHODS, 'description': 'HTTP method; default GET.'},
                'headers': {'type': 'object', 'description': 'Request headers; allowed: ' +
                            ', '.join(sorted(REQUEST_HEADERS)) + '.'},
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
    'library_put': {'kind': 'files',
                    'summary': 'Write one file (audio, cover image, playlist or lyrics file) into the music library, '
                               'replacing a file of the same path; the product sees it at its next scan.',
                    'fields': {
                        'path': {'type': 'string', 'required': True,
                                 'description': 'Relative path inside the library (a leading /music/ is accepted), '
                                                'for example Artist/Album/01 Track.mp3; at most eight folders; '
                                                'suffixes: ' + ' '.join(LIBRARY_SUFFIXES) +
                                                ', plus the file name .ndignore.'},
                        'base64': {'type': 'string', 'required': True,
                                   'description': 'File bytes, base64 encoded, at most 2000000 bytes.'},
                        'mtime': {'type': 'integer',
                                  'description': 'Modification time in seconds since the epoch; default 1700000000.'}}},
    'library_list': {'kind': 'files', 'fields': {},
                     'summary': 'List the files of the music library with size and SHA-256 (at most 1000).'},
    'library_delete': {'kind': 'files',
                       'summary': 'Delete one file of the music library; folders left empty are removed.',
                       'fields': {'path': {'type': 'string', 'required': True,
                                           'description': 'Relative path inside the library.'}}},
    'library_move': {'kind': 'files',
                     'summary': 'Move or rename one file of the music library, keeping its modification time.',
                     'fields': {'from': {'type': 'string', 'required': True,
                                         'description': 'Relative path of the existing file.'},
                                'to': {'type': 'string', 'required': True,
                                       'description': 'Relative path of the new name; it must not exist.'}}},
    'open': {'kind': 'gui', 'summary': 'Open a product page in a session (the session is created if needed).',
             'fields': {'session': SESSION,
                        'path': {'type': 'string', 'description': 'Absolute page path with optional query or '
                                                                  'fragment, for example /app/#/album/all; default /.'}}},
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
    'Static scripts and styles load as assets; page-script reads of their bytes are refused.',
    'Links to javascript: addresses are not activated by pointer, keyboard or drag actions.',
    'The first-run state has no accounts: the sign-in page offers to create the administrator, which is also '
    'POST /auth/createAdmin; every other account is created by an administrator.',
    'Browser sessions run Chromium with a 1280x900 viewport, locale en-US and time zone UTC.',
    'Every browser action returns a fresh snapshot; refs are valid only for the latest snapshot of that session.',
    'Pages are restricted to the product origin: only the web application at /app/ (with its # routes) and public '
    'share pages (/share/<id>) open as pages. The product HTTP interfaces, static assets and instance diagnostics '
    'do not open as pages, and no external resource loads. Static implementation assets cannot be read as data by page scripts. '
    'Native dialogs (alert, confirm, prompt) are accepted automatically. New windows and tabs are closed.',
    'Paths with dot segments are rejected; use the normalized product path.',
    'The File System Access API is not available and native colour or date pickers do not open; set such fields '
    'with fill.',
    'File choosers opened by the page appear in the snapshot as file_chooser; answer them with upload.',
    'Product downloads appear in the snapshot with a ref (at most 4 pending per session); download retrieves each '
    'once.',
    'The music library is a folder owned by the runtime and always appears as /music in responses, pages and '
    'downloads; library folders registered through /api/library must lie inside /music. library_put, library_list, '
    'library_delete and library_move manage its files; the product finds changes when it scans (a scan started in '
    'the application or with /rest/startScan, and while it starts).',
    'Server-sent event streams (/api/events) are not carried, so pages do not update themselves from them; reload '
    'or reopen a page to see changes made elsewhere.',
    'Deployment filesystem paths in responses and pages are redacted. Instance diagnostics are not exposed.',
    'Browser, API and library operations share the product state.',
]
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'response_bytes': MAX_RESPONSE_BYTES, 'upload_bytes': MAX_UPLOAD_BYTES,
          'library_file_bytes': MAX_LIBRARY_FILE, 'library_files_listed': MAX_LIBRARY_ENTRIES,
          'sessions': MAX_SESSIONS, 'pending_downloads_per_session': MAX_PENDING_DOWNLOADS,
          'controls': MAX_CONTROLS, 'text_characters': MAX_TEXT, 'value_characters': MAX_VALUE,
          'in_flight': MAX_IN_FLIGHT, 'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'http_timeout_seconds': HTTP_TIMEOUT_SEC,
          'screenshot_full_page_height': MAX_SCREENSHOT_HEIGHT, 'wheel_and_scroll_delta': [-5000, 5000],
          'drag_via_points': 60, 'drag_steps': [1, 100], 'wait_seconds': 3}
EXAMPLES = [{'op': 'api', 'path': '/auth/createAdmin', 'method': 'POST',
             'json': {'username': 'admin', 'password': 'a-password'}},
            {'op': 'api', 'path': '/rest/ping?u=admin&p=a-password&v=1.16.1&c=client&f=json'},
            {'op': 'library_put', 'path': 'Artist/Album/01 Track.mp3', 'base64': '<base64 bytes>'},
            {'op': 'library_list'},
            {'op': 'open', 'path': '/app/'},
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
audit = None
redact = None
private = None
private_bytes = None
browser = None
music_root = None
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
    # An absolute product path: no scheme, host, dot segments, backslashes or control characters.
    if not isinstance(value, str) or not value.startswith('/') or value.startswith('//'):
        raise ValueError('Use an absolute product path, such as /app/; URLs are forbidden.')
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Control characters are forbidden')
    parsed = urllib.parse.urlsplit(value)
    decoded = urllib.parse.unquote(parsed.path, errors='strict')
    segments = decoded.split('/')
    backslash = chr(92)
    odd = (parsed.scheme or parsed.netloc or backslash in value or backslash in decoded or '//' in decoded
           or any(x in ('.', '..') for x in segments))
    if odd:
        raise ValueError('Invalid product path')
    if any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        raise ValueError('Control characters are forbidden')
    if instance_diagnostics(parsed.path):
        raise ValueError('Instance diagnostics and runtime profiles are not exposed by the black box')
    return value


def api_path(value):
    value = product_path(value)
    path = urllib.parse.unquote(urllib.parse.urlsplit(value).path, errors='strict')
    if path.rstrip('/') in STREAMS:
        raise ValueError('Server-sent event streams are not carried by the black box')
    if not (path.startswith(API_PREFIXES) or SHARE_API.fullmatch(path)):
        raise ValueError('HTTP access exposes the OpenSubsonic API (/rest/), the native API (/api/), '
                         'authentication (/auth/) and share addresses (/share/); use browser operations for pages')
    return value


def page_path(value):
    value = product_path(value)
    path = urllib.parse.unquote(urllib.parse.urlsplit(value).path, errors='strict')
    if path in ('/', '/app', '/app/') or (SHARE_PAGE.fullmatch(path) and path != '/share/img'):
        return value
    raise ValueError('Only the web application at /app/ and public share pages (/share/<id>) open as browser '
                     'pages; use op api for the HTTP interfaces')


def scrubbed(kind):
    # Text answers can carry deployment paths; binary answers (audio, images) are passed on untouched.
    kind = (kind or '').split(';')[0].strip().lower()
    return not kind or kind.startswith(('application/json', 'application/xml', 'text/')) or 'mpegurl' in kind


def alias_text(content):
    # The library folder appears as /music; every other private location is masked.
    if music_root:
        content = content.replace(music_root.encode(), LIBRARY_ALIAS.encode())
    return private_bytes.sub(b'[private path]', content)


def download_bytes(meta, content):
    # Exported playlists list library files; they carry the same /music names as every other answer.
    if meta['filename'].casefold().endswith(('.m3u', '.m3u8')):
        return alias_text(content)
    return content


def real_library_path(value):
    # A library folder named with /music, as the product sees it.
    parts = value.split('/')[1:]
    if any(part in ('.', '..') or chr(92) in part or any(ord(c) < 32 for c in part) for part in parts):
        raise ValueError('Library paths must lie inside ' + LIBRARY_ALIAS)
    return music_root + value[len(LIBRARY_ALIAS):]


def library_fields(pairs):
    """Keep original fields while rejecting case-insensitive JSON field collisions."""
    result, names = {}, set()
    for key, value in pairs:
        name = key.casefold()
        if name in names:
            raise ValueError('Library settings must not contain duplicate or ambiguous fields')
        names.add(name)
        result[key] = value
    return result


def library_body(body):
    # Go matches JSON fields case-insensitively; every spelling uses the same path policy.
    if not isinstance(body, dict):
        return body
    body = library_fields(body.items())
    key = next((key for key in body if key.casefold() == 'path'), None)
    if key is not None:
        value = body.pop(key)
        if not isinstance(value, str) or not (value == LIBRARY_ALIAS or value.startswith(LIBRARY_ALIAS + '/')):
            raise ValueError('Library paths must lie inside ' + LIBRARY_ALIAS)
        body['path'] = real_library_path(value)
    return body


async def fulfill_aliased(route, response):
    # The answer as the page receives it: in text answers the library folder is /music and other paths are masked.
    body = await response.body()
    if scrubbed(response.headers.get('content-type')):
        body = alias_text(body)
    skipped = ('content-encoding', 'content-length', 'transfer-encoding')
    headers = {k: v for k, v in response.headers.items() if k.lower() not in skipped}
    await route.fulfill(status=response.status, headers=headers, body=body)


async def serve_native(route, path):
    # Native API requests made by pages: library folders keep their /music names and paths in answers are masked.
    request = route.request
    options = {}
    if path.startswith('/api/library') and request.method in ('POST', 'PUT', 'PATCH'):
        try:
            options['post_data'] = json.dumps(library_body(runtime.strict_json_loads(request.post_data or 'null')))
        except ValueError as exc:
            await route.fulfill(status=422, content_type='application/json',
                                body=json.dumps({'errors': {'path': str(exc)}}))
            return
    await fulfill_aliased(route, await route.fetch(**options))


async def serve_page_request(route, navigation):
    # Documents and the other requests of a page (not its static files or media): the library folder is shown as
    # /music in their text. A redirected document is left to the browser, which follows it itself.
    response = await route.fetch(max_redirects=0)
    if navigation and 300 <= response.status < 400:
        await route.continue_()
        return
    await fulfill_aliased(route, response)


def passes_through(path):
    # Static front-end files and media are served as they are.
    return path.lower().endswith(STATIC_SUFFIXES) or path.startswith(MEDIA_ROUTES)


def alias_snapshot(data):
    # The library folder appears as /music in what a snapshot reports, whatever the page drew.
    def alias(value):
        return value.replace(music_root, LIBRARY_ALIAS) if isinstance(value, str) and music_root else value
    data['text'] = alias(data.get('text'))
    for control in data.get('controls', []):
        for key, value in list(control.items()):
            control[key] = alias(value)
    return data


# -- the music library ---------------------------------------------------------------------------------
def library_target(value, field='path'):
    # A relative path inside the library: no dot segments, backslashes or control characters.
    if isinstance(value, str) and value.startswith(LIBRARY_ALIAS + '/'):
        value = value[len(LIBRARY_ALIAS) + 1:]
    if not isinstance(value, str) or not value or value.startswith('/'):
        raise ValueError(field + ' must be a relative path inside the library')
    if len(value) > MAX_LIBRARY_PATH or any(ord(c) < 32 or ord(c) == 127 for c in value) or chr(92) in value:
        raise ValueError(field + ' is too long or contains control characters or backslashes')
    segments = value.split('/')
    if len(segments) > 9 or any(not s or s in ('.', '..') or len(s) > MAX_LIBRARY_SEGMENT for s in segments):
        raise ValueError(field + ' has an empty, dot or overlong segment or more than eight folders')
    name = segments[-1].casefold()
    if not (name.endswith(LIBRARY_SUFFIXES) or name == '.ndignore'):
        raise ValueError(field + ' must end with one of: ' + ' '.join(LIBRARY_SUFFIXES) + ' (or be .ndignore)')
    return segments


@contextmanager
def library_parent(segments, create=False):
    """Hold the real library root and every parent directory until the operation ends."""
    with ExitStack() as stack:
        current = stack.enter_context(runtime.open_directory(music_root))
        for name in segments[:-1]:
            try:
                child = runtime.open_relative(current, name, directory=True)
                current = stack.enter_context(child)
            except FileNotFoundError:
                if not create:
                    raise ValueError('no such library file') from None
                account = product.account()
                current = stack.enter_context(runtime.owned_directory(
                    current, name, uid=account.pw_uid, gid=account.pw_gid, mode=0o700))
        yield current, segments[-1]


def library_regular(fd):
    """Validate an opened ordinary file before reading it or changing metadata."""
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('library entries must be regular files without additional links')
    return info


def prune_library(segments):
    """Remove only empty parents, anchored at the library root for every removal."""
    for length in range(len(segments) - 1, 0, -1):
        try:
            with library_parent(segments[:length]) as (parent, name):
                os.rmdir(name, dir_fd=parent)
        except OSError:
            return


def library_op(op, data):
    if op == 'library_list':
        entries = []

        def walk(parent, prefix):
            children = runtime.list_directory(parent)
            for name, info in children:
                if not stat.S_ISREG(info.st_mode):
                    continue
                if len(entries) >= MAX_LIBRARY_ENTRIES:
                    return True
                with runtime.open_relative(parent, name) as fd:
                    payload = runtime.read_bounded(fd, limit=MAX_LIBRARY_FILE)
                entries.append({'path': '/'.join((*prefix, name)), 'size': len(payload),
                                'sha256': hashlib.sha256(payload).hexdigest()})
            for name, info in children:
                if not stat.S_ISDIR(info.st_mode):
                    continue
                with runtime.open_relative(parent, name, directory=True) as child:
                    if walk(child, (*prefix, name)):
                        return True
            return False

        with runtime.open_directory(music_root) as root:
            truncated = walk(root, ())
        return {'files': entries, 'truncated': truncated}
    if op == 'library_put':
        segments = library_target(data['path'])
        payload = base64.b64decode(data['base64'], validate=True)
        if len(payload) > MAX_LIBRARY_FILE:
            raise ValueError('File exceeds ' + str(MAX_LIBRARY_FILE) + ' bytes')
        mtime = data.get('mtime', LIBRARY_MTIME)
        if not 0 <= mtime <= 4_102_444_800:
            raise ValueError('mtime must lie between 0 and 4102444800')
        account = product.account()
        with library_parent(segments, create=True) as (parent, name):
            try:
                with runtime.open_relative(parent, name) as fd:
                    library_regular(fd)
            except FileNotFoundError:
                pass
            runtime.atomic_write(parent, name, payload, uid=account.pw_uid, gid=account.pw_gid, mode=0o600)
            with runtime.open_relative(parent, name) as fd:
                library_regular(fd)
                ns = int(mtime * 1_000_000_000)
                runtime.set_metadata(fd, ns=(ns, ns))
        return {'path': '/'.join(segments), 'size': len(payload)}
    if op == 'library_delete':
        segments = library_target(data['path'])
        with library_parent(segments) as (parent, name):
            with runtime.open_relative(parent, name) as fd:
                library_regular(fd)
            runtime.unlink_entry(parent, name)
        prune_library(segments)
        return {'deleted': '/'.join(segments)}
    source_parts = library_target(data['from'], 'from')
    target_parts = library_target(data['to'], 'to')
    with library_parent(source_parts) as (source_parent, source_name):
        with runtime.open_relative(source_parent, source_name) as fd:
            library_regular(fd)
        with library_parent(target_parts, create=True) as (target_parent, target_name):
            try:
                os.stat(target_name, dir_fd=target_parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('the destination exists')
            os.rename(source_name, target_name, src_dir_fd=source_parent, dst_dir_fd=target_parent)
    prune_library(source_parts)
    return {'moved': '/'.join(target_parts)}


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
    api_path(data['path'])
    lowered = set()
    for key, value in data.get('headers', {}).items():
        if key.lower() not in REQUEST_HEADERS:
            raise ValueError('Unsupported request header: ' + str(key))
        header_value(value, 'header ' + key)
        if key.lower() in lowered:
            raise ValueError('Duplicate request header')
        lowered.add(key.lower())
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
            text_value(value.get('filename'), 'filename', nonempty=True)
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
        text_value(data.get('filename'), 'filename', nonempty=True)
        text_value(data.get('mime_type', 'application/octet-stream'), 'mime_type', nonempty=True)
        if len(base64.b64decode(text_value(data.get('base64'), 'base64'), validate=True)) > MAX_UPLOAD_BYTES:
            raise ValueError('Upload exceeds 1MB')
    if op == 'download' and not re.fullmatch(r'd[0-9]+', data['ref']):
        raise ValueError('download needs a reference from the current snapshot')
    if op == 'api':
        validate_api(data)
    if op in ('library_put', 'library_delete'):
        library_target(data['path'])
    if op == 'library_move':
        library_target(data['from'], 'from')
        library_target(data['to'], 'to')
    if op == 'library_put':
        payload = base64.b64decode(text_value(data.get('base64'), 'base64'), validate=True)
        if len(payload) > MAX_LIBRARY_FILE:
            raise ValueError('File exceeds ' + str(MAX_LIBRARY_FILE) + ' bytes')
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


def page_resource_allowed(path, resource_type):
    """Static implementation files load as assets, never as data read by page scripts."""
    path = urllib.parse.unquote(path, errors='strict')
    return not (path.lower().endswith(('.js', '.mjs', '.cjs', '.css', '.map', '.wasm'))) or resource_type in {'script', 'stylesheet', 'image', 'font', 'media', 'manifest', 'texttrack'}


async def new_session(name):
    if len(sessions) >= MAX_SESSIONS:
        raise ValueError('Close an existing browser session before opening another')
    context = await browser.new_context(locale='en-US', timezone_id='UTC', viewport=VIEWPORT,
                                        service_workers='block', accept_downloads=True)

    async def restrict(route):
        request = route.request
        url = urllib.parse.urlsplit(request.url)
        if not same_origin(url):
            if url.scheme in {'data', 'blob'} and not request.is_navigation_request():
                await route.continue_()
            else:
                await route.abort()
            return
        if not page_resource_allowed(url.path, request.resource_type):
            await route.abort()
            return
        if instance_diagnostics(url.path):
            await route.abort()
            return
        if request.is_navigation_request():
            try:
                page_path(urllib.parse.urlunsplit(('', '', url.path, url.query, url.fragment)))
            except ValueError as exc:
                # An empty 204 answer cancels the navigation and keeps the current document.
                if request.frame == page.main_frame:
                    page._blackbox_blocked = {'path': url.path, 'reason': str(exc)}
                await route.fulfill(status=204, body='')
                return
            await serve_page_request(route, True)
            return
        path = urllib.parse.unquote(url.path)
        if path.rstrip('/') in STREAMS:
            # A 204 answer ends an event stream for good; the page simply receives no events.
            await route.fulfill(status=204, body='')
        elif path.startswith('/api/'):
            await serve_native(route, path)
        elif passes_through(path):
            await route.continue_()
        else:
            await serve_page_request(route, False)

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
            relative = ('[page data]' if download.url.startswith('blob:')
                        else product_path(product_url(download.url)))
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
    # Error pages may show deployment paths; mask them before text and pixels.
    if page._blackbox_status >= 400:
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
    data = alias_snapshot(data)
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


async def api_dispatch(data):
    path = api_path(data['path'])
    method = data.get('method', 'GET')
    decoded = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
    headers = {'content-type': data.get('content_type', 'application/json')}
    for key, value in data.get('headers', {}).items():
        headers[key.lower()] = value
    library_write = decoded.startswith('/api/library') and method in ('POST', 'PUT', 'PATCH')
    if library_write and 'json' not in data:
        raise ValueError('Library folders are registered with a json body')
    kwargs = {}
    if 'json' in data:
        kwargs['json'] = library_body(data['json']) if library_write else data['json']
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
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=HTTP_TIMEOUT_SEC) as client:
        async with client.stream(method, origin + path, headers=headers, **kwargs) as response:
            content, truncated = await read_response(response)
            status = response.status_code
            kind = response.headers.get('content-type', '')
            response_headers = {k.lower(): v.replace(origin, '') for k, v in response.headers.items()
                                if k.lower() in RESPONSE_HEADERS}
    if scrubbed(kind):
        content = alias_text(content)
    try:
        body = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = content.decode('utf-8', errors='replace')
    return {'status': status, 'headers': response_headers, 'body': body,
            'body_base64': base64.b64encode(content).decode() if data.get('binary') else None, 'truncated': truncated}


async def dispatch(data):
    op = validate_request(data)
    if op == 'help':
        return runtime.help_document(PRODUCT, 'browser', OPERATIONS, limits=LIMITS, notes=NOTES, examples=EXAMPLES,
                                     library=LIBRARY_ALIAS)
    if op == 'status':
        return product.status()
    if op == 'reset':
        await close_sessions()
        return await start_product(True)
    if op == 'restart':
        return await start_product(False)
    if op == 'api':
        return await api_dispatch(data)
    if op.startswith('library_'):
        return await asyncio.to_thread(library_op, op, data)
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
            return {**meta, 'size': path.stat().st_size,
                    'body_base64': base64.b64encode(download_bytes(meta, content[:MAX_RESPONSE_BYTES])).decode(),
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
    global config, origin, product, audit, redact, private, private_bytes, browser, music_root
    config = runtime.options().parse_args(argv)
    origin = f'http://127.0.0.1:{config.port}'
    music_root = str(Path(config.state) / 'music')
    work = Path(config.work)
    work.mkdir(parents=True, exist_ok=True)
    product = runtime.Product(config, log=runtime.BoundedLog(config.log_dir),
                              directories={**runtime.layout(config.state), 'MUSIC_DIR': Path(config.state) / 'music'})
    audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
    roots = (config.solution, config.state, config.work, config.log_dir,
             product.account().pw_dir, *product.directories.values(), Path(__file__).resolve().parent)
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
