#!/usr/bin/env python3
"""SVG-edit browser runtime for visible controls, public data and file exchange."""
from __future__ import annotations

import asyncio
import base64
import json
import math
from pathlib import Path
import re
import sys
import time
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, async_playwright  # noqa: E402

PRODUCT = 'SVG-edit 7.4.2'
VIEWPORT = {'width': 1280, 'height': 900}
ENTRY_PATHS = ('/', '/index.html')
ENTRY_QUERIES = ('', 'storagePrompt=true', 'storagePrompt=false')
MAX_REQUEST_BYTES = 3_000_000
MAX_FILE_BYTES = 1_000_000
MAX_DOWNLOAD_BYTES = 2_000_000
MAX_SVG_CHARS = 1_000_000
MAX_SOURCE_CHARS = 1_500_000
MAX_IN_FLIGHT = 8
RPC_TIMEOUT_SEC = 90
API_TIMEOUT_SEC = 30
MAX_PENDING_DOWNLOADS = 4
MAX_CONTROLS = 400
MAX_TEXT = 4_000
MAX_VALUE = 4_000
MAX_DRAWING_ITEMS = 60
MAX_DIALOG_TEXT = 4_000
EXPORT_WINDOW_SEC = 5
ACTION_TIMEOUT_MS = 3000
CLICK_PRESS_MS = 50
LOAD_IDLE_SEC = 10
MODIFIERS = ['Shift', 'Control', 'Alt', 'Meta']
REF = re.compile(r'e[0-9a-f]{8}(?:x[0-9]{1,3})?|canvas[0-9]{1,2}')
# Browser developer and source-view chords; the page never needs them.
REFUSED_KEYS = ({'f12'}, {'control', 'shift', 'i'}, {'control', 'shift', 'j'}, {'control', 'shift', 'c'},
                {'control', 'shift', 'k'}, {'control', 'u'}, {'meta', 'alt', 'i'}, {'meta', 'alt', 'j'},
                {'meta', 'alt', 'u'})
NOT_FETCHED = ('.js', '.mjs', '.cjs', '.map', '.css', '.html', '.htm', '.ts')
# SVG-edit imports its default extensions in parallel and inserts each one's toolbar buttons when that import
# completes, so the toolbar order would change from one page load to the next. The page's requests for these
# extension modules are held in the browser and released one at a time in the editor's configured order, each once
# the previous extension's files have loaded; contents are untouched and pages without these files are unaffected.
EXTENSION_ORDER = ('ext-connector', 'ext-eyedropper', 'ext-grid', 'ext-markers', 'ext-panning', 'ext-shapes',
                   'ext-polystar', 'ext-storage', 'ext-opensave', 'ext-layer_view')
EXTENSION_FILE = re.compile(r'/extensions/(ext-[a-z_]+)/(.+)$')
EXTENSION_QUIET = 0.15  # seconds without a file of the previous extension in flight
EXTENSION_LOCALE = 0.03  # seconds after the previous extension's locale module arrived
EXTENSION_LIMIT = 3.0
EXPORT_TYPES = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/bmp': 'bmp', 'image/webp': 'webp',
                'image/gif': 'gif', 'application/pdf': 'pdf', 'image/svg+xml': 'svg'}

# -- machine-readable help (blackbox-v2) ---------------------------------------------------------------
TARGET = {'type': 'object',
          'description': 'Locator, matched against the controls as the snapshot lists them (text also matches '
                         'other visible page text): one of ref (a '
                         'control eXXXXXXXX or a drawing surface canvasN), role (with optional name; the name is the '
                         "control's aria label, label, text or title), label, title (tooltip), text, placeholder, or "
                         'document: true (pointer, drag, wheel and drop only: x/y are document user units of the open '
                         'drawing); optional nth (zero-based among matches) and exact (default true; false = '
                         'case-insensitive substring).'}


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


POINT = ('Without a target: viewport CSS pixels (0-1279, 0-899) as in the screenshot. With a control or canvasN '
         'target: CSS pixels relative to its visible box. With target {"document": true}: document user units.')
BUTTON = {'type': 'string', 'enum': ['left', 'middle', 'right'], 'description': 'Mouse button; default left.'}
COUNT = {'type': 'integer', 'enum': [1, 2, 3], 'description': 'Number of clicks (2 = double click); default 1.'}
HELD = {'type': 'array', 'items': {'type': 'string', 'enum': MODIFIERS},
        'description': 'Keys held during the action: Shift, Control, Alt, Meta.'}
FILE_FIELDS = {
    'filename': {'type': 'string', 'required': True, 'description': 'File name (base name only).'},
    'mime_type': {'type': 'string', 'description': 'MIME type; default application/octet-stream.'},
    'base64': {'type': 'string', 'required': True, 'description': 'File bytes, base64 encoded, at most 1 MB.'},
}
GESTURE = {
    'target': target(note=' Optional; coordinates are then relative to it.'),
    'x': number('Start x. ' + POINT), 'y': number('Start y. ' + POINT),
    'to_x': number('End x of a drag (same frame as x).'), 'to_y': number('End y of a drag (same frame as y).'),
    'via': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}},
            'description': 'Drag only: up to 60 intermediate [x, y] points (same frame) passed in order.'},
    'steps': {'type': 'integer', 'description': 'Drag only: pointer moves on each segment, 1-100; default 5.'},
    'button': BUTTON, 'modifiers': HELD,
}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, limits and notes.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the product process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Restart the product with an empty data directory and a fresh browser profile (no local '
                         'storage or cookies); the page is left blank until open.'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Restart the product process with the same data directory; the browser page and its '
                           'storage stay, so reload to load the page from the restarted product.'},
    'open': {'kind': 'gui', 'summary': 'Open the editor entry page.',
             'fields': {'path': {'type': 'string',
                                 'description': 'Entry page: / (default) or /index.html, optionally with the query '
                                                'storagePrompt=true or storagePrompt=false.'}}},
    'reload': {'kind': 'gui', 'summary': 'Reload the page (the page may store its state before unloading).',
               'fields': {}},
    'snapshot': {'kind': 'observe', 'fields': {},
                 'summary': 'Page path and title; visible controls (ref, tag, role, text, tooltip title, labels, '
                            'value, state, bounds [x,y,w,h]); drawing surfaces; a summary of the drawn SVG; '
                            'other visible text; pending downloads, file chooser, answered dialogs, refusals.'},
    'screenshot': {'kind': 'observe', 'fields': {}, 'summary': 'PNG of the 1280x900 viewport as png_base64.'},
    'click': {'kind': 'gui', 'summary': 'Click a control (or the centre of a drawing surface) found by a locator.',
              'fields': {'target': target(True), 'button': BUTTON, 'click_count': COUNT, 'modifiers': HELD}},
    'hover': {'kind': 'gui', 'summary': 'Move the pointer over a control.', 'fields': {'target': target(True)}},
    'fill': {'kind': 'gui', 'summary': 'Replace the value of a text field.',
             'fields': {'target': target(True),
                        'value': {'type': 'string', 'required': True, 'description': 'Replacement text.'}}},
    'type': {'kind': 'gui', 'summary': 'Type text key by key into the target (focused first) or, without a target, '
                                       'into the focused element.',
             'fields': {'target': target(note=' Optional.'),
                        'value': {'type': 'string', 'required': True, 'description': 'Text to type.'}}},
    'select': {'kind': 'gui', 'summary': 'Choose an option of a native select control by value or label.',
               'fields': {'target': target(True),
                          'value': {'type': 'string', 'required': True, 'description': 'Option value or label.'}}},
    'check': {'kind': 'gui', 'summary': 'Set a checkbox or radio button.',
              'fields': {'target': target(True), 'checked': {'type': 'boolean', 'description': 'Default true.'}}},
    'press': {'kind': 'gui', 'summary': 'Press a key or chord (Playwright names such as Enter, Escape, Delete, '
                                        'ArrowRight, Shift+O, Control+Z) on the target, which is focused first, or '
                                        'without a target on the focused element (the page body when nothing has '
                                        'focus).',
              'fields': {'target': target(note=' Optional.'),
                         'key': {'type': 'string', 'required': True, 'description': 'Key name or chord.'}}},
    'pointer': {'kind': 'gui', 'summary': 'Low-level mouse action at coordinates: click, down, up, move or drag.',
                'fields': {**GESTURE, 'action': {'type': 'string', 'enum': ['click', 'down', 'up', 'move', 'drag'],
                                                 'description': 'Pointer action; default click.'},
                           'click_count': COUNT}},
    'drag': {'kind': 'gui', 'summary': 'Press at x,y, pass through via points, release at to_x,to_y (alias of '
                                       'pointer with action drag).', 'fields': dict(GESTURE)},
    'wheel': {'kind': 'gui', 'summary': 'Turn the mouse wheel over a point.',
              'fields': {'target': GESTURE['target'], 'x': number('x of the pointer. ' + POINT, True),
                         'y': number('y of the pointer. ' + POINT, True),
                         'delta_x': number('Horizontal wheel delta, -5000..5000; default 0.'),
                         'delta_y': number('Vertical wheel delta, -5000..5000 (positive scrolls down); default 0.'),
                         'modifiers': HELD}},
    'wait': {'kind': 'gui', 'summary': 'Wait up to 3 seconds for asynchronous page changes, then snapshot.',
             'fields': {'seconds': number('Seconds to wait, 0-3; default 0.5.')}},
    'upload': {'kind': 'gui', 'summary': 'Answer the pending file chooser (or fill a file input given as target) '
                                         'with one file.',
               'fields': {'target': target(note=' Optional when a file chooser is pending.'), **FILE_FIELDS}},
    'drop': {'kind': 'gui', 'summary': 'Drop one file at a point, as when dragging it from the desktop onto the '
                                       'page.',
             'fields': {'target': GESTURE['target'], 'x': number('x of the drop. ' + POINT, True),
                        'y': number('y of the drop. ' + POINT, True), **FILE_FIELDS}},
    'dialog': {'kind': 'gui', 'summary': 'Decide the answer to the next native alert, confirm, prompt or leave-page '
                                         'dialog (one shot; without it dialogs are accepted with their default).',
               'fields': {'action': {'type': 'string', 'enum': ['accept', 'dismiss'], 'required': True,
                                     'description': 'accept (OK) or dismiss (Cancel).'},
                          'text': {'type': 'string', 'description': 'Text entered into a prompt before accepting.'}}},
    'download': {'kind': 'files', 'summary': 'Retrieve a pending product download (listed in the snapshot) once, '
                                             'as body_base64 (at most 2 MB).',
                 'fields': {'ref': {'type': 'string', 'required': True, 'description': 'Download ref, such as d1.'}}},
    'api': {'kind': 'http',
            'summary': "Call the editor's JavaScript API on the open page: loadFromString runs "
                       'await window.svgEditor.loadFromString(svg, {noAlert: true}); getSvgString returns '
                       'window.svgEditor.svgCanvas.getSvgString().',
            'fields': {'method': {'type': 'string', 'enum': ['loadFromString', 'getSvgString'], 'required': True,
                                  'description': 'API method.'},
                       'svg': {'type': 'string', 'description': 'loadFromString only: SVG text, at most 1,000,000 '
                                                                'characters.'}}},
})
GUI_ACTIONS = {op for op, spec in OPERATIONS.items() if spec['kind'] == 'gui'}
NOTES = [
    'One browser page (Chromium, 1280x900 viewport, locale en-US, time zone UTC). reset gives a fresh browser '
    'profile; restart keeps the page and its local storage.',
    'Only the editor entry page opens (/ or /index.html, optionally ?storagePrompt=true|false). Other navigations '
    'are refused and reported under blocked; the page stays. New windows and tabs are closed, except that a window '
    'the page opens on its own blob: or data: content (an exported image) is captured as a download.',
    'The page reaches only its own origin: scripts, style sheets, images and fonts load; fetch/XHR may not load '
    'scripts, style sheets, source maps or HTML documents; frames, media, plug-ins, WebSockets and service workers '
    'are blocked; nothing external loads.',
    'Snapshots list controls inside open shadow roots. A control is named by its text, its tooltip (title), its '
    'aria label or its field label; refs are derived from these names and stay valid while the control exists.',
    'Drawing surfaces (visible top-level svg or canvas elements of at least 100x100 pixels) are listed as canvasN. '
    'The drawing summary lists the SVG graphics drawn inside nested svg documents of a surface (or the surface '
    'itself), grouped by container; it is an observation aid and may be empty for other kinds of drawing.',
    'Target {"document": true} maps document user units to the viewport with the screen transform of '
    'window.svgEditor.svgCanvas.getSvgContent().',
    'Every GUI action returns a fresh snapshot after the page has settled.',
    'Native dialogs (alert, confirm, prompt, leave page) are answered at once: by the answer set with dialog '
    '(one shot), otherwise accepted with their default; snapshots report them under dialogs.',
    'File choosers opened by the page appear as file_chooser; answer them with upload. The File System Access API '
    'is not available, so pages use their file-input fallbacks.',
    'Downloads appear in the snapshot with a ref (at most 4 pending); download retrieves each once. Only downloads '
    'of blob: or data: content created by the page are kept.',
    'The api operation calls window.svgEditor on the open page: loadFromString answers {"loaded": true} or '
    '{"loaded": false, "error": ...}; getSvgString answers {"svg": ...}.',
    'Refused keys: developer-tool and view-source chords (F12, Control+Shift+I/J/C/K, Control+U).',
]
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'file_bytes': MAX_FILE_BYTES, 'download_bytes': MAX_DOWNLOAD_BYTES,
          'svg_characters': MAX_SVG_CHARS, 'source_characters': MAX_SOURCE_CHARS,
          'pending_downloads': MAX_PENDING_DOWNLOADS, 'controls': MAX_CONTROLS, 'text_characters': MAX_TEXT,
          'value_characters': MAX_VALUE, 'drawing_items': MAX_DRAWING_ITEMS, 'in_flight': MAX_IN_FLIGHT,
          'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'api_timeout_seconds': API_TIMEOUT_SEC,
          'wheel_delta': [-5000, 5000], 'drag_via_points': 60, 'drag_steps': [1, 100], 'wait_seconds': 3}
EXAMPLES = [{'op': 'open'},
            {'op': 'click', 'target': {'title': 'Square/Rect Tool'}},
            {'op': 'drag', 'target': {'document': True}, 'x': 100, 'y': 100, 'to_x': 260, 'to_y': 180},
            {'op': 'press', 'key': 'Control+Z'},
            {'op': 'api', 'method': 'getSvgString'},
            {'op': 'dialog', 'action': 'accept', 'text': 'Layer 2'},
            {'op': 'screenshot'}]

INIT_SCRIPT = r'''(() => {
  const blockScriptLink = event => {
    const path = event.composedPath ? event.composedPath() : [event.target];
    for (const element of path) {
      if (!element || !element.getAttribute) continue;
      const href = element.getAttribute('href') || element.getAttribute('xlink:href');
      if (!href) continue;
      try {
        if (new URL(href, document.baseURI).protocol === 'javascript:') {
          event.preventDefault();
          event.stopImmediatePropagation();
          return;
        }
      } catch (error) {}
    }
  };
  document.addEventListener('click', blockScriptLink, true);
  document.addEventListener('auxclick', blockScriptLink, true);

  for (const k of ["showOpenFilePicker", "showSaveFilePicker", "showDirectoryPicker"]) {
    try { delete window[k]; } catch (e) {}
    try { delete Window.prototype[k]; } catch (e) {}
  }
  document.addEventListener("click", e => {
    const t = e.composedPath ? e.composedPath()[0] : e.target;
    if (t instanceof HTMLInputElement && ["color", "date", "time", "datetime-local", "month", "week"].includes(t.type))
      e.preventDefault();
  }, true);
})();'''

# Shared page-side helpers: composed tree, visibility, clipping, controls (snapshot and ref resolution use the same
# enumeration, so a ref always names the same control).
HELPERS = r'''
  const W = innerWidth, H = innerHeight;
  const css = e => getComputedStyle(e);
  const up = n => n.assignedSlot || n.parentElement || (n.parentNode && n.parentNode.host) || null;
  const shown = e => { const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && e.checkVisibility({opacityProperty: true, visibilityProperty: true}); };
  const inSvg = e => { for (let p = up(e); p; p = up(p)) if (p instanceof SVGSVGElement) return true; return false; };
  const top = p => !p || p === document.body || p === document.documentElement;
  const visibleRect = e => {
    const r = e.getBoundingClientRect();
    let x0 = Math.max(r.left, 0), y0 = Math.max(r.top, 0), x1 = Math.min(r.right, W), y1 = Math.min(r.bottom, H);
    for (let cur = e; ;) {
      const position = css(cur).position;
      if (position === "fixed") break;
      let cb = up(cur);
      if (position === "absolute")
        while (!top(cb) && css(cb).position === "static" && css(cb).transform === "none") cb = up(cb);
      if (top(cb)) break;
      const s = css(cb);
      if (s.overflowX !== "visible" || s.overflowY !== "visible") {
        const q = cb.getBoundingClientRect();
        if (s.overflowX !== "visible") { x0 = Math.max(x0, q.left); x1 = Math.min(x1, q.right); }
        if (s.overflowY !== "visible") { y0 = Math.max(y0, q.top); y1 = Math.min(y1, q.bottom); }
      }
      cur = cb;
    }
    return x1 - x0 >= 1 && y1 - y0 >= 1 ? [x0, y0, x1 - x0, y1 - y0] : null;
  };
  const clip = (v, n) => (v || "").replace(/\s+/g, " ").trim().slice(0, n);
  const tip = e => clip(e.getAttribute && e.getAttribute("title"), 200);
  const hidden = n => { if (n.nodeType !== 1) return false; const s = css(n);
    return s.display === "none" || s.visibility === "hidden"; };
  // Rendered text of a composed subtree (shadow roots and slots followed, form fields and svg excluded).
  const ctext = (root, n) => {
    let out = "";
    const visit = node => {
      if (out.length > n) return;
      if (node.nodeType === 3) { out += node.nodeValue + " "; return; }
      if (node.nodeType === 11) { for (const c of node.childNodes) visit(c); return; }
      if (node.nodeType !== 1) return;
      if (node instanceof SVGElement || ["SCRIPT", "STYLE", "TEMPLATE", "INPUT", "SELECT", "TEXTAREA"].includes(node.tagName)) return;
      if (hidden(node)) return;
      if (node.tagName === "SLOT") { for (const a of node.assignedNodes({flatten: true})) visit(a); return; }
      if (node.shadowRoot) { for (const c of node.shadowRoot.childNodes) visit(c); return; }
      for (const c of node.childNodes) visit(c);
    };
    visit(root);
    return clip(out, n);
  };
  const ROLES = new Set(["button", "link", "checkbox", "radio", "switch", "tab", "menuitem", "menuitemcheckbox",
    "menuitemradio", "option", "combobox", "textbox", "searchbox", "slider", "spinbutton", "treeitem", "listbox"]);
  const NATIVE = new Set(["A", "BUTTON", "INPUT", "SELECT", "TEXTAREA", "SUMMARY"]);
  const FIELDS = new Set(["INPUT", "SELECT", "TEXTAREA"]);
  const elements = () => {
    const out = [];
    const walk = root => { for (const c of root.children) { out.push(c); if (c.shadowRoot) walk(c.shadowRoot); walk(c); } };
    walk(document);
    return out;
  };
  const native = e => NATIVE.has(e.tagName) || (e.isContentEditable && !(up(e) && up(e).isContentEditable)) ||
    ROLES.has(e.getAttribute("role") || "");
  const eligible = e => {
    if (e instanceof SVGElement) return false;
    if (e.tagName === "INPUT" && e.type === "hidden") return false;
    if (native(e)) return true;
    if (clip(e.getAttribute("title"), 1)) return true;
    const p = up(e);
    return css(e).cursor === "pointer" && !(p && p.nodeType === 1 && css(p).cursor === "pointer");
  };
  const inside = (a, b, slack) => a.left >= b.left - slack && a.top >= b.top - slack && a.right <= b.right + slack &&
    a.bottom <= b.bottom + slack;
  const hash = s => { let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h.toString(16).padStart(8, "0"); };
  const caption = (e, scope) => {
    // The nearest text before the field inside its container (after it for check boxes and radios).
    const toggle = e.type === "checkbox" || e.type === "radio";
    const text = n => n.nodeType === 3 ? n.nodeValue : (n.nodeType === 1 && !hidden(n) && !FIELDS.has(n.tagName) &&
      !(n.querySelector && n.querySelector("input,select,textarea,button")) ? ctext(n, 80) : "");
    const walk = (start, back) => {
      for (let n = start; n; n = back ? n.previousSibling : n.nextSibling) {
        if (n.nodeType === 1 && (FIELDS.has(n.tagName) || n.tagName === "BUTTON" || n.tagName === "BR" ||
            (n.querySelector && n.querySelector("input,select,textarea,button")))) return "";
        const t = clip(text(n), 80); if (t) return t;
      }
      return ""; };
    let c = toggle ? walk(e.nextSibling, false) || walk(e.previousSibling, true) : walk(e.previousSibling, true);
    // Then the text before the field's enclosing elements (shadow hosts included), up to three levels.
    for (let p = up(e), i = 0; !c && p && p !== scope && p.nodeType === 1 && i < 3; p = up(p), i++)
      c = toggle ? walk(p.nextSibling, false) : walk(p.previousSibling, true);
    return c;
  };
  // Controls: elements merged into groups (an element wrapping exactly one eligible control is one control; a tooltip-
  // only container around several controls gives them its tooltip as context).
  const controls = limit => {
    const all = elements();
    const cands = all.filter(e => { try { return eligible(e) && shown(e) && !inSvg(e); } catch (x) { return false; } });
    const set = new Set(cands), parent = new Map(), kids = new Map();
    for (const e of cands) {
      let p = up(e); while (p && !set.has(p)) p = up(p);
      parent.set(e, p || null);
      if (p) { if (!kids.has(p)) kids.set(p, []); kids.get(p).push(e); }
    }
    const into = new Map();  // member -> group root
    const contextOf = new Map();
    const dropped = new Set();
    for (const e of cands) {
      const k = kids.get(e) || [];
      if (k.length === 1 && !kids.has(k[0]) && inside(k[0].getBoundingClientRect(), e.getBoundingClientRect(), 4)) {
        into.set(k[0], e);
      } else if (k.length >= 1 && !native(e) && css(e).cursor !== "pointer") {
        // A titled container around several controls is not a control itself; its tooltip names their context.
        dropped.add(e);
        if (tip(e)) for (const c of k) contextOf.set(c, tip(e).slice(0, 160));
      }
    }
    const root = e => { let r = e; while (into.has(r)) r = into.get(r); return r; };
    const groups = new Map();
    for (const e of cands) {
      if (dropped.has(e)) continue;
      const r = root(e); if (dropped.has(r)) continue;
      if (!groups.has(r)) groups.set(r, []); groups.get(r).push(e);
    }
    const out = [], counts = {};
    for (const [el, members] of groups) {
      if (out.length >= limit) return {out, truncated: true};
      const v = visibleRect(el); if (!v) continue;
      const field = members.find(m => FIELDS.has(m.tagName)) || null;
      const titled = [...members].reverse().find(m => tip(m));
      const c = {tag: el.tagName.toLowerCase()};
      const role = members.map(m => m.getAttribute("role")).find(Boolean); if (role) c.role = role;
      const button = members.find(m => m.tagName === "INPUT" && ["button", "submit", "reset"].includes(m.type));
      const text = button ? clip(button.value, 200) : ctext(el, 200); if (text) c.text = text;
      if (titled) c.title = tip(titled);
      const aria = members.map(m => m.getAttribute("aria-label")).find(Boolean); if (aria) c.aria = clip(aria, 200);
      if (field) {
        const labels = field.labels ? [...field.labels].map(l => ctext(l, 120)).filter(Boolean).join(" ") : "";
        const label = labels || caption(field, el.parentElement); if (label) c.label = clip(label, 120);
        if (field.tagName === "INPUT") c.type = field.type;
        if (field.name) c.name = clip(field.name, 80);
        if (field.placeholder) c.placeholder = clip(field.placeholder, 120);
        if (field.tagName === "SELECT") {
          c.value = field.value;
          c.options = [...field.options].slice(0, 60).map(o => ({label: clip(o.text, 60), value: clip(o.value, 60),
            selected: o.selected}));
        } else if (field.type === "checkbox" || field.type === "radio") { c.checked = field.checked; c.value = field.value; }
        else if (field.type === "file") c.file = true;
        else if (["button", "submit", "reset"].includes(field.type)) { delete c.value; }
        else if (field.type !== "password") { const raw = String(field.value || ""); c.value = raw.slice(0, 4000);
          if (raw.length > 4000) c.value_truncated = true; }
      } else if (el.isContentEditable) { c.value = (el.innerText || "").slice(0, 4000); }
      const ctx = members.map(m => contextOf.get(m)).find(Boolean);
      if (ctx) c.context = ctx;
      else if (!c.title && !c.aria && !c.label) {
        for (let p = up(el), i = 0; p && i < 5; p = up(p), i++) {
          const t = p.nodeType === 1 ? tip(p).slice(0, 160) : ""; if (t) { c.context = t; break; } }
      }
      if (members.some(m => m.disabled || m.hasAttribute("disabled") || m.getAttribute("aria-disabled") === "true")) c.disabled = true;
      if (members.some(m => m.hasAttribute("pressed") || m.getAttribute("aria-pressed") === "true")) c.pressed = true;
      const expanded = members.map(m => m.getAttribute("aria-expanded")).find(x => x !== null && x !== undefined);
      if (expanded) c.expanded = expanded === "true";
      const selected = members.map(m => m.getAttribute("aria-selected")).find(x => x !== null && x !== undefined);
      if (selected) c.selected = selected === "true";
      c.bounds = v.map(Math.round);
      const key = hash(JSON.stringify([c.tag, c.role, c.text, c.title, c.aria, c.label, c.context, c.type, c.name]));
      counts[key] = (counts[key] || 0) + 1;
      c.ref = "e" + key + (counts[key] > 1 ? "x" + counts[key] : "");
      c._el = el; c._field = field;
      out.push(c);
    }
    return {out, truncated: false};
  };
  // Drawing surfaces: visible top-level svg or canvas elements of at least 100x100 visible pixels.
  const surfaces = () => {
    const out = [];
    for (const e of elements()) {
      if (!(e instanceof SVGSVGElement || e instanceof HTMLCanvasElement)) continue;
      if (e instanceof SVGSVGElement && inSvg(e)) continue;
      if (!shown(e)) continue;
      const v = visibleRect(e);
      if (v && v[2] >= 100 && v[3] >= 100) out.push({el: e, v});
    }
    return out;
  };
'''

SNAPSHOT_SCRIPT = r'''([limits]) => {''' + HELPERS + r'''
  const result = controls(limits.controls);
  const listed = new Set(result.out.map(c => c._el));
  const controlsOut = result.out.map(c => { const o = {...c}; delete o._el; delete o._field; return o; });
  const round = b => b.map(v => Math.round(v));
  // Drawing summary: SVG graphics inside the nested svg documents of each surface (or the surface itself).
  const GRAPHIC = new Set(["rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "image", "use",
    "foreignObject"]);
  const DEFS = new Set(["defs", "symbol", "marker", "clipPath", "mask", "pattern", "linearGradient", "radialGradient",
    "filter", "title", "desc", "metadata", "style", "script"]);
  const KEYS = {rect: ["x", "y", "width", "height", "rx", "ry"], circle: ["cx", "cy", "r"], ellipse: ["cx", "cy", "rx", "ry"],
    line: ["x1", "y1", "x2", "y2"], polyline: ["points"], polygon: ["points"], path: ["d"],
    text: ["x", "y", "font-family", "font-size", "font-weight", "font-style", "text-anchor", "text-decoration"],
    image: ["x", "y", "width", "height", "href", "xlink:href"], use: ["x", "y", "href", "xlink:href"],
    foreignObject: ["x", "y", "width", "height"]};
  const PAINT = ["fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "stroke-dasharray",
    "stroke-linejoin", "stroke-linecap", "transform", "filter", "marker-start", "marker-mid", "marker-end", "class"];
  const label = e => { let s = e.tagName; if (e.id) s += "#" + e.id;
    const cls = e.getAttribute("class"); if (cls) s += "." + clip(cls, 40).replace(/ /g, ".");
    const t = [...e.children].find(c => c.tagName === "title"); if (t && clip(t.textContent, 1)) s += ' "' + clip(t.textContent, 40) + '"';
    return s; };
  const canvases = [], drawing = [];
  let items = 0;
  surfaces().forEach(({el, v}, n) => {
    canvases.push({ref: "canvas" + n, tag: el.tagName.toLowerCase(), bounds: round(v)});
    if (!(el instanceof SVGSVGElement)) return;
    const docs = [...el.querySelectorAll("svg")].filter(s => s.parentElement && !s.parentElement.closest("defs,symbol,pattern,marker,mask,clipPath"));
    const roots = docs.length ? docs : [el];
    for (const root of roots) {
      const groups = new Map();
      const visit = (node, chain) => {
        for (const c of node.children) {
          const tag = c.tagName;
          if (DEFS.has(tag) || tag === "svg") continue;
          if (tag === "g" || tag === "a" || tag === "switch") {
            const next = chain.concat([label(c)]);
            if (c.getAttribute("display") === "none" || css(c).display === "none" || css(c).visibility === "hidden") {
              const key = next.join(" > "); if (!groups.has(key)) groups.set(key, {container: key, hidden: true, items: []});
              continue; }
            visit(c, next); continue;
          }
          if (!GRAPHIC.has(tag)) continue;
          let box; try { box = c.getBoundingClientRect(); } catch (x) { continue; }
          if (!(box.width > 0 || box.height > 0) || !c.checkVisibility({visibilityProperty: true, opacityProperty: false})) continue;
          if (items >= limits.drawing) { drawing.truncated = true; continue; }
          const key = chain.join(" > ");
          if (!groups.has(key)) groups.set(key, {container: key, items: []});
          const item = {kind: tag}; if (c.id) item.id = clip(c.id, 60);
          for (const k of (KEYS[tag] || []).concat(PAINT)) { const val = c.getAttribute(k); if (val !== null && val !== "") item[k] = clip(val, 80); }
          if (tag === "text") item.text = clip(c.textContent, 80);
          item.bounds = round([box.x, box.y, box.width, box.height]);
          groups.get(key).items.push(item); items++;
        }
      };
      visit(root, [label(root)]);
      for (const g of groups.values()) drawing.push(Object.assign({canvas: "canvas" + n}, g));
    }
  });
  // Other visible text (outside listed controls and drawing surfaces).
  const lines = [];
  let size = 0;
  const textVisit = node => {
    if (size > limits.text) return;
    if (node.nodeType === 3) { const t = clip(node.nodeValue, 300); if (t && lines[lines.length - 1] !== t) { lines.push(t); size += t.length + 1; } return; }
    if (node.nodeType === 11) { for (const c of node.childNodes) textVisit(c); return; }
    if (node.nodeType !== 1) return;
    if (node instanceof SVGElement || listed.has(node) || ["SCRIPT", "STYLE", "TEMPLATE", "INPUT", "SELECT", "TEXTAREA", "OPTION"].includes(node.tagName)) return;
    if (hidden(node)) return;
    if (node.tagName === "SLOT") { for (const a of node.assignedNodes({flatten: true})) textVisit(a); return; }
    if (node.shadowRoot) { for (const c of node.shadowRoot.childNodes) textVisit(c); return; }
    const r = node.getBoundingClientRect();
    if (r.width === 0 && r.height === 0 && css(node).display !== "contents") return;
    if (r.bottom <= 0 || r.right <= 0 || r.top >= H || r.left >= W) return;
    for (const c of node.childNodes) textVisit(c);
  };
  if (document.body) textVisit(document.body);
  const text = lines.join("\n");
  return {title: document.title, viewport: [W, H], controls: controlsOut, controls_truncated: result.truncated,
          canvases, drawing, drawing_truncated: !!drawing.truncated, text: text.slice(0, limits.text),
          text_truncated: text.length > limits.text};
}'''

FIND_SCRIPT = r'''([spec, want]) => {''' + HELPERS + r'''
  if (spec.ref && spec.ref.startsWith("canvas")) { const s = surfaces()[Number(spec.ref.slice(6))]; return s ? s.el : null; }
  const list = controls(100000).out;
  let found;
  if (spec.ref) found = list.filter(c => c.ref === spec.ref);
  else {
    const exact = spec.exact !== false;
    const norm = v => (v || "").replace(/\s+/g, " ").trim();
    const same = (have, want) => exact ? norm(have) === norm(want) : norm(have).toLowerCase().includes(norm(want).toLowerCase());
    const implicit = c => c.role || ({a: "link", button: "button", select: "combobox", textarea: "textbox", summary: "button"}[c.tag]) ||
      (c.type === "checkbox" ? "checkbox" : c.type === "radio" ? "radio" : c.tag === "input" || c.type ? "textbox" : "button");
    const name = c => c.aria || c.label || c.text || c.title || "";
    if ("role" in spec) found = list.filter(c => implicit(c) === spec.role && (spec.name === undefined || same(name(c), spec.name)));
    else if ("label" in spec) found = list.filter(c => same(c.label, spec.label) || same(c.aria, spec.label));
    else if ("title" in spec) found = list.filter(c => same(c.title, spec.title));
    else if ("placeholder" in spec) found = list.filter(c => same(c.placeholder, spec.placeholder));
    else found = list.filter(c => same(c.text, spec.text));
  }
  const c = found[spec.nth || 0];
  if (!c && "text" in spec && !spec.ref) {
    // Fallback: the innermost visible element (outside drawings) whose rendered text matches, as on screen.
    const exact = spec.exact !== false;
    const norm = v => (v || "").replace(/\s+/g, " ").trim();
    const hits = elements().filter(e => { try { if (e instanceof SVGElement || inSvg(e) || !shown(e)) return false;
      const t = norm(ctext(e, 300)); return exact ? t === norm(spec.text) : t.toLowerCase().includes(norm(spec.text).toLowerCase());
    } catch (x) { return false; } });
    const within = (o, e) => { for (let p = up(o); p; p = up(p)) if (p === e) return true; return false; };
    const innermost = hits.filter(e => !hits.some(o => o !== e && within(o, e)));
    return innermost[spec.nth || 0] || null;
  }
  if (!c) return null;
  return want === "field" && c._field ? c._field : c._el;
}'''

BOX_SCRIPT = r'''(e) => {''' + HELPERS + r'''
  if (!e || !shown(e)) return null;
  const v = visibleRect(e);
  return v ? {x: v[0], y: v[1], width: v[2], height: v[3]} : null;
}'''

DOCUMENT_SCRIPT = r'''(points) => {
  const editor = window.svgEditor;
  const canvas = editor && editor.svgCanvas;
  const content = canvas && typeof canvas.getSvgContent === "function" ? canvas.getSvgContent() : null;
  if (!content || typeof content.getScreenCTM !== "function")
    return {error: "the page does not provide window.svgEditor.svgCanvas.getSvgContent() with a screen transform"};
  const m = content.getScreenCTM();
  if (!m) return {error: "the drawing element has no screen transform"};
  return {points: points.map(([x, y]) => { const p = new DOMPoint(x, y).matrixTransform(m); return [p.x, p.y]; })};
}'''

DROP_SCRIPT = r'''([x, y, name, type, data]) => {
  let el = document.elementFromPoint(x, y);
  while (el && el.shadowRoot) { const inner = el.shadowRoot.elementFromPoint(x, y); if (!inner || inner === el) break; el = inner; }
  if (!el) return {error: "nothing at the drop point"};
  const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
  const transfer = new DataTransfer();
  transfer.items.add(new File([bytes], name, {type}));
  const fire = kind => el.dispatchEvent(new DragEvent(kind, {bubbles: true, cancelable: true, composed: true,
    clientX: x, clientY: y, dataTransfer: transfer}));
  fire("dragenter"); fire("dragover"); fire("drop");
  return {dropped: true};
}'''

API_LOAD = r'''async ([svg, limit]) => {
  const editor = window.svgEditor;
  if (!editor || typeof editor.loadFromString !== "function")
    return {error: "the page does not provide window.svgEditor.loadFromString"};
  try { await editor.loadFromString(svg, {noAlert: true}); return {loaded: true}; }
  catch (x) { return {loaded: false, error: String((x && x.message) || x).slice(0, limit)}; }
}'''

API_SOURCE = r'''(limit) => {
  const editor = window.svgEditor;
  const canvas = editor && editor.svgCanvas;
  if (!canvas || typeof canvas.getSvgString !== "function")
    return {error: "the page does not provide window.svgEditor.svgCanvas.getSvgString"};
  const s = canvas.getSvgString();
  if (typeof s !== "string") return {error: "getSvgString did not return a string"};
  return {svg: s.slice(0, limit), truncated: s.length > limit};
}'''

# Wait until the page is quiet: no DOM mutation (including inside shadow roots) for `quiet` ms and no finite running
# animation, bounded by `limit` ms; then two animation frames.
SETTLE_SCRIPT = r'''([quiet, limit]) => new Promise(resolve => {
  const start = performance.now(); let last = start;
  const observer = new MutationObserver(() => { last = performance.now(); });
  const watch = root => { observer.observe(root, {subtree: true, childList: true, attributes: true, characterData: true});
    for (const e of root.querySelectorAll("*")) if (e.shadowRoot) watch(e.shadowRoot); };
  try { watch(document); } catch (x) {}
  const busy = () => { try { return document.getAnimations().some(a => a.playState === "running" &&
    a.effect && a.effect.getComputedTiming().iterations !== Infinity); } catch (x) { return false; } };
  const tick = () => {
    const now = performance.now();
    if ((now - last >= quiet && !busy()) || now - start >= limit) {
      observer.disconnect(); requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))); return; }
    setTimeout(tick, 40);
  };
  setTimeout(tick, 40);
})'''

FETCH_SCRIPT = r'''async ([url, limit]) => {
  const response = await fetch(url);
  const blob = await response.blob();
  if (blob.size > limit) return {error: "too large", size: blob.size};
  const buffer = new Uint8Array(await blob.arrayBuffer());
  let binary = ""; for (let i = 0; i < buffer.length; i += 32768) binary += String.fromCharCode.apply(null, buffer.subarray(i, i + 32768));
  return {type: blob.type, size: blob.size, base64: btoa(binary)};
}'''

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
lock = asyncio.Lock()
config = None
origin = None
product = None
audit = None
redact = None
private = None
browser = None
state: dict = {}
in_flight = 0


class RequestTooLarge(ValueError):
    pass


# -- validation ----------------------------------------------------------------------------------------
def text_value(value, field, *, nonempty=False, limit=None):
    if not isinstance(value, str) or (nonempty and not value):
        raise ValueError(field + ' must be a string' + (' with a value' if nonempty else ''))
    if limit is not None and len(value) > limit:
        raise ValueError(f'{field} exceeds {limit} characters')
    return value


def entry_path(value):
    """The editor entry page, optionally with the storage prompt query the product itself uses."""
    if not isinstance(value, str) or not value.startswith('/') or value.startswith('//') or len(value) > 200:
        raise ValueError('Use the editor entry page / (or /index.html); URLs are not opened')
    if any(ord(c) < 32 or ord(c) == 127 or c == '\\' for c in value):
        raise ValueError('Invalid entry path')
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path not in ENTRY_PATHS \
            or parsed.query not in ENTRY_QUERIES:
        raise ValueError('Only the editor entry page opens: / or /index.html, optionally with ?storagePrompt=true '
                         'or ?storagePrompt=false')
    return value


def validate_target(value, *, document=False):
    if not isinstance(value, dict):
        raise ValueError('target must be a locator object')
    keys = {'ref', 'role', 'label', 'title', 'text', 'placeholder', 'document'} & value.keys()
    if len(keys) != 1 or value.keys() - (keys | {'name', 'nth', 'exact'}):
        raise ValueError('target needs exactly one of ref, role, label, title, text, placeholder or document (plus '
                         'name, nth, exact); arbitrary selectors are forbidden')
    key = next(iter(keys))
    if key == 'document':
        if value['document'] is not True or len(value) != 1:
            raise ValueError('target {"document": true} takes no other field')
        if not document:
            raise ValueError('target {"document": true} applies to pointer, drag, wheel and drop only')
        return
    text_value(value[key], 'target.' + key, nonempty=True, limit=300)
    if key == 'ref' and not REF.fullmatch(value[key]):
        raise ValueError('Invalid reference; use a ref from the latest snapshot')
    if key == 'role' and not re.fullmatch(r'[a-z][a-z0-9]*', value[key]):
        raise ValueError('role must be an ARIA role name')
    if 'name' in value:
        if key != 'role':
            raise ValueError('name is only supported with role')
        text_value(value['name'], 'target.name', limit=300)
    if 'nth' in value and (type(value['nth']) is not int or not 0 <= value['nth'] <= 1000):
        raise ValueError('nth must be an integer between 0 and 1000')
    if 'exact' in value and type(value['exact']) is not bool:
        raise ValueError('exact must be boolean')


def finite(value, field, low=-100.0, high=5000.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(field + ' must be a finite number')
    if not low <= value <= high:
        raise ValueError(f'{field} must lie between {low:g} and {high:g}')
    return float(value)


def coordinate_range(data):
    return (-100_000.0, 100_000.0) if data.get('target', {}).get('document') else (-100.0, 5000.0)


def gesture_points(data, drag):
    low, high = coordinate_range(data)
    start = finite(data.get('x'), 'x', low, high), finite(data.get('y'), 'y', low, high)
    if not drag:
        for key in ('to_x', 'to_y', 'via', 'steps'):
            if key in data:
                raise ValueError(key + ' is only used by drags')
        return start, [], None
    end = finite(data.get('to_x'), 'to_x', low, high), finite(data.get('to_y'), 'to_y', low, high)
    via = data.get('via', [])
    if not isinstance(via, list) or len(via) > 60:
        raise ValueError('via lists at most 60 [x, y] points')
    middle = []
    for item in via:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError('each via point is [x, y]')
        middle.append((finite(item[0], 'via x', low, high), finite(item[1], 'via y', low, high)))
    steps = data.get('steps', 5)
    if type(steps) is not int or not 1 <= steps <= 100:
        raise ValueError('steps must be between 1 and 100')
    return start, middle, end


def check_key(key):
    text_value(key, 'key', nonempty=True, limit=60)
    parts = {p.strip().lower() for p in key.split('+') if p.strip()}
    parts = {'control' if p in ('ctrl', 'controlormeta') else p for p in parts}
    if any(chord <= parts and len(chord) == len(parts) for chord in REFUSED_KEYS):
        raise ValueError('Developer-tool and view-source keys are not available')


def file_bytes(data):
    name = text_value(data.get('filename'), 'filename', nonempty=True, limit=200)
    if '/' in name or '\\' in name or '\x00' in name or name in ('.', '..'):
        raise ValueError('filename must be a base name')
    text_value(data.get('mime_type', 'application/octet-stream'), 'mime_type', nonempty=True, limit=100)
    try:
        content = base64.b64decode(text_value(data.get('base64'), 'base64'), validate=True)
    except ValueError:
        raise ValueError('base64 is not valid base64') from None
    if len(content) > MAX_FILE_BYTES:
        raise ValueError('The file exceeds 1 MB')
    return content


def validate_request(data):
    op = runtime.validate(OPERATIONS, data)
    if 'target' in data:
        validate_target(data['target'], document=op in {'pointer', 'drag', 'wheel', 'drop'})
    if op == 'open':
        entry_path(data.get('path', '/'))
    if op in {'fill', 'type', 'select'}:
        text_value(data.get('value'), 'value', limit=MAX_VALUE * 4)
    if op == 'press':
        check_key(data.get('key'))
    if op in {'pointer', 'drag'}:
        gesture_points(data, op == 'drag' or data.get('action') == 'drag')
    if op in {'wheel', 'drop'}:
        low, high = coordinate_range(data)
        finite(data.get('x'), 'x', low, high), finite(data.get('y'), 'y', low, high)
    if op == 'wheel':
        finite(data.get('delta_x', 0), 'delta_x', -5000, 5000), finite(data.get('delta_y', 0), 'delta_y', -5000, 5000)
    if op == 'wait':
        finite(data.get('seconds', 0.5), 'seconds', 0, 3)
    if op in {'upload', 'drop'}:
        file_bytes(data)
    if op == 'dialog' and 'text' in data:
        text_value(data['text'], 'text', limit=MAX_DIALOG_TEXT)
    if op == 'download' and not re.fullmatch(r'd[0-9]{1,6}', data['ref']):
        raise ValueError('download needs a ref from the current snapshot, such as d1')
    if op == 'api':
        if data['method'] == 'loadFromString':
            text_value(data.get('svg'), 'svg', limit=MAX_SVG_CHARS)
        elif 'svg' in data:
            raise ValueError('svg is only used by loadFromString')
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


# -- product lifecycle ---------------------------------------------------------------------------------
async def start_product(fresh):
    started = await asyncio.to_thread(product.start, fresh)
    if started:
        await asyncio.to_thread(runtime.wait_http, product)
    return product.status()


# -- browser page --------------------------------------------------------------------------------------
def same_origin(url):
    host = urllib.parse.urlsplit(origin)
    return (url.scheme, url.hostname, url.port) == (host.scheme, host.hostname, host.port)


def page_path(url):
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(('', '', parsed.path, parsed.query, ''))


def allowed_navigation(url):
    return (same_origin(url) and url.path in ENTRY_PATHS and url.query in ENTRY_QUERIES
            and not url.username and not url.password)


async def close_page():
    context = state.get('context')
    for task in list(state.get('tasks', ())):
        task.cancel()
    state.clear()
    if context is not None:
        try:
            await context.close()
        except Exception:
            pass


def extension_file(url):
    match = EXTENSION_FILE.search(urllib.parse.urlsplit(url).path)
    return match.groups() if match and match.group(1) in EXTENSION_ORDER else None


def extension_event(request, kind):
    """Bookkeeping of the page's extension files: in flight, last arrival, locale arrival."""
    found = extension_file(request.url)
    sequence = state.get('extensions')
    if found is None or sequence is None:
        return
    name, rest = found
    flight = sequence['flight']
    if kind == 'start':
        flight[name] = flight.get(name, 0) + 1
        return
    flight[name] = max(0, flight.get(name, 0) - 1)
    sequence['arrived'][name] = time.monotonic()
    if kind == 'finished' and rest.startswith('locale/'):
        sequence['locale'][name] = time.monotonic()


async def extension_turn(name):
    """Hold an extension module request until the previous extension in the configured order has loaded."""
    sequence = state.get('extensions')
    if sequence is None or name == EXTENSION_ORDER[0]:
        return
    previous = EXTENSION_ORDER[EXTENSION_ORDER.index(name) - 1]
    load, deadline = sequence['load'], time.monotonic() + EXTENSION_LIMIT
    while sequence['load'] == load and time.monotonic() < deadline:
        now = time.monotonic()
        arrived, locale = sequence['arrived'].get(previous), sequence['locale'].get(previous)
        if arrived is not None and not sequence['flight'].get(previous) and (
                (locale is not None and now - locale >= EXTENSION_LOCALE) or now - arrived >= EXTENSION_QUIET):
            return
        await asyncio.sleep(0.01)


async def new_page():
    """A fresh browser profile with one page."""
    await close_page()
    context = await browser.new_context(locale='en-US', timezone_id='UTC', viewport=VIEWPORT,
                                        service_workers='block', accept_downloads=True)
    state.update(context=context, downloads={}, download_serial=0, chooser=None, dialog=None, dialogs=[],
                 blocked=None, tasks=set(), extensions={'load': 0, 'flight': {}, 'arrived': {}, 'locale': {}})

    def main_frame(request):
        try:
            return state.get('page') is not None and request.frame == state['page'].main_frame
        except PlaywrightError:
            return False

    async def restrict(route):
        request = route.request
        url = urllib.parse.urlsplit(request.url)
        if url.scheme in ('data', 'blob'):
            if request.is_navigation_request() and main_frame(request):
                state['blocked'] = {'kind': 'navigation', 'path': '[export content is not an application page]'}
                await route.fulfill(status=204, body='')
            else:
                await route.continue_()
            return
        if not same_origin(url):
            if request.is_navigation_request() and main_frame(request):
                # Refused like any other navigation: an empty 204 answer keeps the current document.
                state['blocked'] = {'kind': 'navigation', 'path': ('[other origin] ' + page_path(request.url))[:200]}
                await route.fulfill(status=204, body='')
            else:
                await route.abort()
            return
        if request.is_navigation_request():
            if main_frame(request):
                if allowed_navigation(url):
                    sequence = state['extensions']
                    sequence['load'] += 1
                    for key in ('flight', 'arrived', 'locale'):
                        sequence[key].clear()
                    await route.continue_()
                    return
                # An empty 204 answer cancels the navigation and keeps the current document.
                state['blocked'] = {'kind': 'navigation', 'path': page_path(request.url)[:200]}
                await route.fulfill(status=204, body='')
                return
            await route.abort()
            return
        kind = request.resource_type
        if kind in ('script', 'stylesheet', 'image', 'font'):
            found = extension_file(request.url) if kind == 'script' else None
            if found and found[1] == found[0] + '.js':
                await extension_turn(found[0])
            await route.continue_()
        elif kind in ('fetch', 'xhr'):
            path = urllib.parse.unquote(url.path).lower()
            if path.endswith(NOT_FETCHED) or path.rsplit('/', 1)[-1] == 'package.json':
                await route.abort()
            else:
                await route.continue_()
        else:
            await route.abort()

    await context.route('**/*', restrict)
    context.on('request', lambda request: extension_event(request, 'start'))
    context.on('requestfinished', lambda request: extension_event(request, 'finished'))
    context.on('requestfailed', lambda request: extension_event(request, 'failed'))
    try:
        await context.route_web_socket('**/*', lambda ws: ws.close())
    except AttributeError:
        pass
    await context.add_init_script(INIT_SCRIPT)
    page = await context.new_page()
    state['page'] = page

    def track(coroutine):
        task = asyncio.ensure_future(coroutine)
        state['tasks'].add(task)
        task.add_done_callback(lambda t: state.get('tasks', set()).discard(t))

    async def answer(dialog):
        plan, state['dialog'] = state.get('dialog'), None
        entry = {'type': dialog.type, 'message': dialog.message[:300]}
        try:
            if plan and plan['action'] == 'dismiss':
                entry['answer'] = 'dismissed'
                await dialog.dismiss()
            else:
                text = plan.get('text') if plan else None
                entry['answer'] = 'accepted'
                if dialog.type == 'prompt':
                    entry['text'] = (text if text is not None else dialog.default_value)[:300]
                    await dialog.accept(text if text is not None else dialog.default_value)
                else:
                    await dialog.accept()
        except PlaywrightError:
            pass
        state['dialogs'] = (state.get('dialogs', []) + [entry])[-8:]

    async def remember_download(download):
        url = download.url
        if not await permitted_document(page):
            await download.cancel()
            return
        if not url.startswith(('blob:', 'data:')) or len(state['downloads']) >= MAX_PENDING_DOWNLOADS:
            state['blocked'] = {'kind': 'download', 'path': '[not created by the page]' if not url.startswith(
                ('blob:', 'data:')) else '[too many pending downloads]'}
            await download.cancel()
            return
        try:
            path = await download.path()
            content = Path(path).read_bytes()[:MAX_DOWNLOAD_BYTES + 1] if path else b''
        except PlaywrightError:
            return
        finally:
            try:
                await download.delete()
            except PlaywrightError:
                pass
        if await permitted_document(page):
            add_download(Path(download.suggested_filename).name[:200] or 'download', content, None)

    async def capture_window(extra):
        """A window the page opens on its own blob:/data: content (an export) becomes a download; others close."""
        try:
            deadline = time.monotonic() + EXPORT_WINDOW_SEC
            while time.monotonic() < deadline and not extra.url.startswith(('blob:', 'data:')) and not extra.is_closed():
                await asyncio.sleep(0.05)
            url = extra.url
            if (url.startswith(('blob:', 'data:')) and len(state['downloads']) < MAX_PENDING_DOWNLOADS
                    and await permitted_document(page)):
                fetched = None
                try:
                    fetched = await page.evaluate(FETCH_SCRIPT, [url, MAX_DOWNLOAD_BYTES])
                except PlaywrightError:
                    pass
                if fetched and 'base64' in fetched:
                    mime = (fetched.get('type') or '').split(';')[0].strip().lower()
                    if mime in EXPORT_TYPES and await permitted_document(page):
                        add_download('export.' + EXPORT_TYPES[mime], base64.b64decode(fetched['base64']), mime)
                    else:
                        state['blocked'] = {'kind': 'window', 'path': '[unsupported export content]'}
                else:
                    state['blocked'] = {'kind': 'window', 'path': '[unreadable page content]'}
            else:
                state['blocked'] = {'kind': 'window', 'path': '[new window closed]'}
        finally:
            try:
                await extra.close()
            except PlaywrightError:
                pass

    page.on('dialog', lambda dialog: track(answer(dialog)))
    page.on('download', lambda download: track(remember_download(download)))
    page.on('filechooser', lambda chooser: state.__setitem__('chooser', chooser))
    context.on('page', lambda extra: track(capture_window(extra)) if extra != state.get('page') else None)
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    page.set_default_navigation_timeout(30000)
    return page


def add_download(filename, content, mime):
    state['download_serial'] += 1
    ref = 'd' + str(state['download_serial'])
    meta = {'ref': ref, 'filename': filename, 'size': len(content[:MAX_DOWNLOAD_BYTES + 1])}
    if mime:
        meta['type'] = mime
    state['downloads'][ref] = (content, meta)


async def current_page():
    page = state.get('page')
    if page is None or page.is_closed():
        page = await new_page()
    return page


def on_product(page):
    url = urllib.parse.urlsplit(page.url)
    return url.scheme in ('http', 'https') and allowed_navigation(url)


async def permitted_document(page):
    """Validate the document actually displayed before observing it or reading an export."""
    if page.url == 'about:blank' and len(page.frames) == 1:
        return False
    permitted = on_product(page) and all(
        frame == page.main_frame or frame.url in ('', 'about:blank') for frame in page.frames)
    if permitted:
        try:
            permitted = await page.evaluate('() => document.contentType') == 'text/html'
        except PlaywrightError:
            permitted = False
    if permitted:
        return True
    state['blocked'] = {'kind': 'document', 'path': '[document outside the permitted editor page]'}
    state.get('downloads', {}).clear()
    state['chooser'] = None
    try:
        await page.goto('about:blank', wait_until='domcontentloaded')
    except PlaywrightError:
        pass
    return False


async def settled(page, quiet=150, limit=3000):
    """The page has finished reacting: pending downloads and export windows processed, DOM quiet."""
    tasks = [t for t in state.get('tasks', ()) if not t.done()]
    if tasks:
        await asyncio.wait(tasks, timeout=EXPORT_WINDOW_SEC + 2)
    if not on_product(page):
        return
    try:
        await page.evaluate(SETTLE_SCRIPT, [quiet, limit])
    except PlaywrightError:
        pass
    tasks = [t for t in state.get('tasks', ()) if not t.done()]
    if tasks:
        await asyncio.wait(tasks, timeout=EXPORT_WINDOW_SEC + 2)


async def loaded(page):
    """After opening or reloading: load event, network quiet, then DOM quiet."""
    try:
        await page.wait_for_load_state('load', timeout=LOAD_IDLE_SEC * 1000)
        await page.wait_for_load_state('networkidle', timeout=LOAD_IDLE_SEC * 1000)
    except PlaywrightTimeout:
        pass
    await settled(page, quiet=300, limit=5000)


async def snapshot(page):
    if not await permitted_document(page):
        data = {'title': '', 'viewport': [VIEWPORT['width'], VIEWPORT['height']], 'controls': [],
                'controls_truncated': False, 'canvases': [], 'drawing': [], 'drawing_truncated': False,
                'text': '', 'text_truncated': False}
        url = 'about:blank' if page.url == 'about:blank' else '[no product page]'
    else:
        for attempt in range(6):
            try:
                data = await page.evaluate(SNAPSHOT_SCRIPT, [{'controls': MAX_CONTROLS, 'text': MAX_TEXT,
                                                              'drawing': MAX_DRAWING_ITEMS}])
                break
            except PlaywrightError as exc:
                if attempt == 5 or not any(x in str(exc) for x in ('Execution context was destroyed', 'navigation',
                                                                     'Cannot find context', 'Frame was detached')):
                    raise
                await page.wait_for_timeout(200)
        if not await permitted_document(page):
            return await snapshot(page)
        url = page_path(page.url)
    result = {'url': url, **data,
              'downloads': [meta for _, meta in state.get('downloads', {}).values()]}
    if state.get('chooser') is not None:
        result['file_chooser'] = {'multiple': state['chooser'].is_multiple()}
    if state.get('dialogs'):
        result['dialogs'], state['dialogs'] = state['dialogs'], []
    if state.get('blocked'):
        result['blocked'], state['blocked'] = state['blocked'], None
    return result


async def resolve(page, value, want='element'):
    """An element handle for a locator; locators match the controls exactly as the snapshot lists them."""
    validate_target(value)
    handle = await page.evaluate_handle(FIND_SCRIPT, [value, want])
    element = handle.as_element()
    if element is None:
        raise ValueError('No listed control matches the locator' if 'ref' not in value or not value['ref'].startswith('e')
                         else 'Unknown or stale ref; take a new snapshot')
    return element


async def to_viewport(page, data, points):
    """Viewport coordinates of points given in the request's frame."""
    tgt = data.get('target')
    if tgt is None:
        out = points
    elif tgt.get('document'):
        mapped = await page.evaluate(DOCUMENT_SCRIPT, [list(p) for p in points])
        if 'error' in mapped:
            raise ValueError(mapped['error'])
        out = [tuple(p) for p in mapped['points']]
    else:
        element = await resolve(page, tgt)
        box = await page.evaluate(BOX_SCRIPT, element)
        if not box:
            raise ValueError('Target is not visible')
        for x, y in points:
            if not (0 <= x <= box['width'] and 0 <= y <= box['height']):
                raise ValueError('Coordinates must lie inside the target box ({:.0f}x{:.0f})'.format(box['width'],
                                                                                                   box['height']))
        out = [(box['x'] + x, box['y'] + y) for x, y in points]
    for x, y in out:
        if not (0 <= x < VIEWPORT['width'] and 0 <= y < VIEWPORT['height']):
            raise ValueError('The point lies outside the 1280x900 viewport')
    return out


async def pointer_action(page, data):
    action = 'drag' if data['op'] == 'drag' else data.get('action', 'click')
    button = data.get('button', 'left')
    start, via, end = gesture_points(data, action == 'drag')
    points = await to_viewport(page, data, [start, *via] + ([end] if end else []))
    modifiers = data.get('modifiers', [])
    for key in modifiers:
        await page.keyboard.down(key)
    try:
        x, y = points[0]
        if action == 'click':
            # A human-like press: some editors react to the press before the release.
            await page.mouse.click(x, y, button=button, click_count=data.get('click_count', 1), delay=CLICK_PRESS_MS)
        elif action == 'down':
            await page.mouse.move(x, y)
            await page.mouse.down(button=button)
        elif action == 'up':
            await page.mouse.move(x, y)
            await page.mouse.up(button=button)
        elif action == 'move':
            await page.mouse.move(x, y, steps=4)
        else:
            steps = int(data.get('steps', 5))
            await page.mouse.move(x, y)
            await page.mouse.down(button=button)
            for px, py in points[1:]:
                await page.mouse.move(px, py, steps=steps)
            await page.mouse.up(button=button)
    finally:
        for key in reversed(modifiers):
            await page.keyboard.up(key)


async def acting(page, action):
    """Run one input action; if it started a main-frame navigation, wait for the new document; then settle."""
    navigation = {'started': False}

    def on_request(request):
        if request.is_navigation_request() and request.frame == page.main_frame:
            navigation['started'] = True

    page.on('request', on_request)
    try:
        await action()
        await page.wait_for_timeout(120)
        if navigation['started']:
            await loaded(page)
        else:
            await settled(page)
    finally:
        page.remove_listener('request', on_request)


async def api_call(page, data):
    if not await permitted_document(page):
        raise ValueError('Open the editor first')
    script, argument = (API_LOAD, [data['svg'], 300]) if data['method'] == 'loadFromString' \
        else (API_SOURCE, MAX_SOURCE_CHARS)
    try:
        result = await asyncio.wait_for(page.evaluate(script, argument), API_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        raise ValueError('The editor did not answer the API call in time') from None
    if not isinstance(result, dict):
        raise ValueError('The editor answered with an unexpected value')
    if not await permitted_document(page):
        raise ValueError('The editor document changed during the API call')
    if 'error' in result and 'loaded' not in result:
        raise ValueError(result['error'])
    if data['method'] == 'loadFromString':
        await settled(page, quiet=200, limit=3000)
    return result


async def dispatch(data):
    op = validate_request(data)
    if op == 'help':
        return runtime.help_document(PRODUCT, 'browser', OPERATIONS, limits=LIMITS, notes=NOTES, examples=EXAMPLES)
    if op == 'status':
        return product.status()
    if op == 'reset':
        await new_page()
        return await start_product(True)
    if op == 'restart':
        return await start_product(False)
    page = await current_page()
    if op == 'download':
        if not await permitted_document(page):
            raise ValueError('Open the permitted editor page first')
        pending = state['downloads']
        if data['ref'] not in pending:
            raise ValueError('Unknown download ref; use the current snapshot')
        content, meta = pending.pop(data['ref'])
        return {**meta, 'body_base64': base64.b64encode(content[:MAX_DOWNLOAD_BYTES]).decode(),
                'truncated': len(content) > MAX_DOWNLOAD_BYTES}
    if op == 'api':
        return await api_call(page, data)
    if op == 'snapshot':
        await settled(page)
        return await snapshot(page)
    if op == 'screenshot':
        await settled(page)
        await permitted_document(page)
        png = await page.screenshot(full_page=False)
        if not await permitted_document(page):
            png = await page.screenshot(full_page=False)
        return {'png_base64': base64.b64encode(png).decode(), 'width': VIEWPORT['width'],
                'height': VIEWPORT['height']}
    if op == 'dialog':
        state['dialog'] = {'action': data['action'], 'text': data.get('text')}
        return await snapshot(page)
    if op == 'open':
        state['chooser'] = None
        await page.goto(origin + entry_path(data.get('path', '/')), wait_until='domcontentloaded')
        await loaded(page)
        return await snapshot(page)
    if not await permitted_document(page):
        raise ValueError('Open the editor first')
    if op == 'reload':
        state['chooser'] = None
        await page.reload(wait_until='domcontentloaded')
        await loaded(page)
    elif op in {'pointer', 'drag'}:
        await acting(page, lambda: pointer_action(page, data))
    elif op == 'wheel':
        async def wheel():
            (x, y), = await to_viewport(page, data, [(float(data['x']), float(data['y']))])
            for key in data.get('modifiers', []):
                await page.keyboard.down(key)
            try:
                await page.mouse.move(x, y)
                await page.mouse.wheel(float(data.get('delta_x', 0)), float(data.get('delta_y', 0)))
            finally:
                for key in reversed(data.get('modifiers', [])):
                    await page.keyboard.up(key)
        await acting(page, wheel)
    elif op == 'drop':
        async def drop():
            (x, y), = await to_viewport(page, data, [(float(data['x']), float(data['y']))])
            done = await page.evaluate(DROP_SCRIPT, [x, y, data['filename'],
                                                     data.get('mime_type', 'application/octet-stream'),
                                                     data['base64']])
            if 'error' in done:
                raise ValueError(done['error'])
        await acting(page, drop)
    elif op == 'wait':
        await page.wait_for_timeout(int(1000 * float(data.get('seconds', 0.5))))
        await settled(page)
    elif op == 'upload' and 'target' not in data:
        chooser, state['chooser'] = state.get('chooser'), None
        if chooser is None:
            raise ValueError('No file chooser is pending; open it with the page, or give a file input as target')
        payload = {'name': data['filename'], 'mimeType': data.get('mime_type', 'application/octet-stream'),
                   'buffer': base64.b64decode(data['base64'])}
        await acting(page, lambda: chooser.set_files(payload))
    elif op in {'type', 'press'} and 'target' not in data:
        if op == 'type':
            await acting(page, lambda: page.keyboard.type(data['value']))
        else:
            await acting(page, lambda: page.keyboard.press(data['key']))
    else:
        try:
            await element_action(page, op, data)
        except PlaywrightTimeout:
            raise ValueError('The control did not accept the action within 3 s: it may be covered by a dialog or '
                             'overlay, disabled, or not editable') from None
    return await snapshot(page)


async def element_action(page, op, data):
    """An input action on one located control."""
    field_ops = {'fill', 'select', 'check', 'upload', 'type'}
    element = await resolve(page, data['target'], 'field' if data['op'] in field_ops else 'element')
    if op == 'click':
        await acting(page, lambda: element.click(button=data.get('button', 'left'),
                                                 click_count=data.get('click_count', 1),
                                                 modifiers=data.get('modifiers') or None))
    elif op == 'hover':
        await acting(page, lambda: element.hover())
    elif op == 'fill':
        await acting(page, lambda: element.fill(data['value']))
    elif op == 'type':
        async def typing():
            await element.focus()
            await page.keyboard.type(data['value'])
        await acting(page, typing)
    elif op == 'select':
        await acting(page, lambda: element.select_option(data['value']))
    elif op == 'check':
        await acting(page, lambda: element.set_checked(data.get('checked', True)))
    elif op == 'press':
        await acting(page, lambda: element.press(data['key']))
    elif op == 'upload':
        payload = {'name': data['filename'], 'mimeType': data.get('mime_type', 'application/octet-stream'),
                   'buffer': base64.b64decode(data['base64'])}
        await acting(page, lambda: element.set_input_files(payload))


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
        result, code = {'error': type(error).__name__,
                        'detail': redact(private.sub('[private path]', str(error).split('Call log:')[0]))[:600]}, 400
    finally:
        in_flight -= 1
    audit.record(data.get('op', 'help') if isinstance(data, dict) else None, code, time.monotonic() - started)
    return JSONResponse(result, code)


def private_roots(*paths):
    """Deployment roots as whole path prefixes, with what follows them."""
    roots = sorted({str(Path(p)) for p in paths if p and str(p) != '/'}, key=len, reverse=True)
    return r'(?<![\w.~/-])(?:' + '|'.join(re.escape(r) for r in roots) + r''')(?![\w.~-])(?:/[^\s"'<>]*)?'''


async def main(argv=None):
    global config, origin, product, audit, redact, private, browser
    config = runtime.options().parse_args(argv)
    origin = f'http://127.0.0.1:{config.port}'
    work = Path(config.work)
    work.mkdir(parents=True, exist_ok=True)
    product = runtime.Product(config, log=runtime.BoundedLog(config.log_dir))
    audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
    roots = (config.solution, config.state, config.work, config.log_dir, Path(__file__).resolve().parent,
             Path(config.socket).parent, Path.home(), product.account().pw_dir)
    redact = runtime.redactor(*roots)
    private = re.compile(private_roots(*roots))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=['--no-sandbox'],
                                                   downloads_path=str(work / 'downloads'))
        await new_page()
        # A product that fails to start is reported by status; the runtime keeps serving.
        await start_product(True)
        sock = runtime.listen(config.socket, config.socket_mode)
        server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level='warning'))
        runtime.exit_on_sigterm()
        try:
            await server.serve(sockets=[sock])
        finally:
            await close_page()
            await asyncio.to_thread(product.stop)


if __name__ == '__main__':
    asyncio.run(main())
