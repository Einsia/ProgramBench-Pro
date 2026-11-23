#!/usr/bin/env python3
"""BentoPDF browser runtime. Product interaction uses visible UI and file exchange only."""
from __future__ import annotations
import asyncio
import base64
import hashlib
import io
from email.message import Message
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime
from browser_scripts import HELPERS, SNAPSHOT_SCRIPT, FIND_SCRIPT, BOX_SCRIPT, DROP_SCRIPT, SETTLE_SCRIPT, FETCH_SCRIPT
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, async_playwright

PRODUCT='BentoPDF 2.8.10 (Simple)'
VIEWPORT={'width':1280,'height':900}
MAX_REQUEST_BYTES=16_000_000
MAX_FILE_BYTES=10_000_000
MAX_DOWNLOAD_BYTES=40_000_000
MAX_PENDING_DOWNLOADS=24
MAX_CONTROLS=400
MAX_TEXT=12000
MAX_VALUE=64000
MAX_IN_FLIGHT=8
RPC_TIMEOUT_SEC=120
ACTION_TIMEOUT_MS=5000
EXPORT_WINDOW_SEC=5
MODIFIERS=['Shift','Control','Alt','Meta']
REF=re.compile(r'(?:f[0-9a-f]{10}:)?(?:e[0-9a-f]{8}(?:x[0-9]{1,3})?|canvas[0-9]{1,3})')
REFUSED_KEYS=({'f12'},{'control','shift','i'},{'control','shift','j'},{'control','shift','c'},
              {'control','shift','k'},{'control','u'},{'meta','alt','i'},{'meta','alt','j'},{'meta','alt','u'})
# Product page paths are public navigation, not product implementation. No arbitrary URL is accepted.
PAGE_NAMES=['add-attachments', 'add-blank-page', 'add-page-labels', 'add-stamps', 'add-watermark', 'adjust-colors', 'alternate-merge', 'background-color', 'bates-numbering', 'bmp-to-pdf', 'bookmark', 'cbz-to-pdf', 'change-permissions', 'combine-single-page', 'compare-pdfs', 'compress-pdf', 'compress-pdf-for-email', 'compress-pdf-to-100kb', 'compress-pdf-to-1mb', 'compress-pdf-to-200kb', 'compress-pdf-to-2mb', 'compress-pdf-to-500kb', 'crop-pdf', 'csv-to-pdf', 'delete-pages', 'deskew-pdf', 'digital-sign-pdf', 'divide-pages', 'duplex-collate', 'edit-attachments', 'edit-metadata', 'edit-pdf', 'edit-pdf-text', 'email-to-pdf', 'epub-to-pdf', 'excel-to-pdf', 'extract-attachments', 'extract-images', 'extract-pages', 'extract-tables', 'fb2-to-pdf', 'fix-page-size', 'flatten-pdf', 'font-to-outline', 'form-creator', 'form-filler', 'header-footer', 'heic-to-pdf', 'image-to-pdf', 'invert-colors', 'jpg-to-pdf', 'json-to-pdf', 'linearize-pdf', 'markdown-to-pdf', 'merge-pdf', 'mobi-to-pdf', 'n-up-pdf', 'ocr-pdf', 'odg-to-pdf', 'odp-to-pdf', 'ods-to-pdf', 'odt-to-pdf', 'organize-pdf', 'overlay-pdf', 'page-dimensions', 'page-numbers', 'pages-to-pdf', 'pdf-booklet', 'pdf-layers', 'pdf-multi-tool', 'pdf-to-bmp', 'pdf-to-cbz', 'pdf-to-csv', 'pdf-to-excel', 'pdf-to-greyscale', 'pdf-to-jpg', 'pdf-to-json', 'pdf-to-markdown', 'pdf-to-pdfa', 'pdf-to-png', 'pdf-to-svg', 'pdf-to-text', 'pdf-to-tiff', 'pdf-to-webp', 'pdf-to-word', 'pdf-to-zip', 'pdf-workflow', 'png-to-pdf', 'posterize-pdf', 'powerpoint-to-pdf', 'prepare-pdf-for-ai', 'protect-pdf', 'psd-to-pdf', 'pub-to-pdf', 'rasterize-pdf', 'remove-annotations', 'remove-blank-pages', 'remove-metadata', 'remove-restrictions', 'repair-pdf', 'reverse-pages', 'rotate-custom', 'rotate-pdf', 'rtf-to-pdf', 'sanitize-pdf', 'scanner-effect', 'sign-pdf', 'split-pdf', 'svg-to-pdf', 'table-of-contents', 'text-color', 'tiff-to-pdf', 'timestamp-pdf', 'txt-to-pdf', 'unlock-pdf', 'validate-signature-pdf', 'view-metadata', 'vsd-to-pdf', 'webp-to-pdf', 'word-to-pdf', 'wpd-to-pdf', 'wps-to-pdf', 'xml-to-pdf', 'xps-to-pdf', 'tools', 'faq', 'about']
PAGE_PATHS={'/','/index.html',*(f'/{name}.html' for name in PAGE_NAMES)}
FRAME_PATHS={'/pdfjs-viewer/viewer.html','/pdfjs-annotation-viewer/web/viewer.html'}
LANGUAGES={'ar','be','da','de','es','fr','id','it','ja','ko','nl','pl','pt','ru','sk','sv','tr','uk','vi','zh','zh-TW'}
NOT_FETCHED=('.map','.ts','.tsx','.jsx','.py','.sh','.toml')
DOWNLOAD_SUFFIXES={'.pdf','.zip','.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff','.svg','.txt','.md','.csv',
                   '.json','.xml','.xlsx','.docx','.cbz','.html','.p12','.pfx','.pem','.crt','.cer'}

def field(kind,description,required=False,**extra):
    return {'type':kind,'description':description,**({'required':True} if required else {}),**extra}
TARGET=field('object','Visible locator: exactly one of ref, role (optional name), label, title, text, placeholder; optional nth (zero-based) and exact (default true). Frame controls carry frame-prefixed refs. No CSS or code selectors.')
def target(required=False):return dict(TARGET,**({'required':True} if required else {}))
def number(description,required=False):return field('number',description,required)
BUTTON=field('string','Mouse button; default left.',enum=['left','middle','right'])
COUNT=field('integer','Click count; default 1.',enum=[1,2,3])
HELD=field('array','Held modifier keys.',items={'type':'string','enum':MODIFIERS})
FILE_FIELDS={'filename':field('string','File basename only; no paths or control characters.',True),
             'mime_type':field('string','File MIME type; default application/octet-stream.'),
             'base64':field('string','File bytes encoded as base64; at most 10 MB.',True)}
GESTURE={'target':target(),'x':number('Start x in viewport pixels, or relative to target.'),
         'y':number('Start y in viewport pixels, or relative to target.'),'to_x':number('Drag end x.'),'to_y':number('Drag end y.'),
         'via':field('array','Up to 60 intermediate [x,y] drag points.',items={'type':'array','items':{'type':'number'}}),
         'steps':field('integer','Pointer moves per segment, 1-100, default 5.'),'button':BUTTON,'modifiers':HELD}
OPERATIONS=runtime.check_operations({
 'help':{'kind':'info','summary':'Operations, public boundaries and limits.','fields':{}},
 'status':{'kind':'lifecycle','summary':'Product readiness and process state.','fields':{}},
 'reset':{'kind':'lifecycle','summary':'Restart with fresh application data and a fresh browser profile.','fields':{}},
 'restart':{'kind':'lifecycle','summary':'Restart with existing data, keeping browser storage and current page.','fields':{}},
 'open':{'kind':'gui','summary':'Open a product page by its same-origin path.','fields':{'path':field('string','Product page path; default /. Optional language prefix and fragment; no query.')}},
 'reload':{'kind':'gui','summary':'Reload the current product page, preserving browser storage.','fields':{}},
 'snapshot':{'kind':'observe','summary':'Visible page and allowed frames: text, controls, canvas bounds, downloads, pending file chooser.','fields':{}},
 'screenshot':{'kind':'observe','summary':'PNG screenshot of the 1280 by 900 viewport.','fields':{}},
 'click':{'kind':'gui','summary':'Click a visible control.','fields':{'target':target(True),'button':BUTTON,'click_count':COUNT,'modifiers':HELD}},
 'hover':{'kind':'gui','summary':'Hover a visible control.','fields':{'target':target(True)}},
 'fill':{'kind':'gui','summary':'Replace a field value (also native color, date and range inputs).','fields':{'target':target(True),'value':field('string','Replacement value.',True)}},
 'type':{'kind':'gui','summary':'Type text into the focused element or a target.','fields':{'target':target(),'value':field('string','Text to type.',True)}},
 'select':{'kind':'gui','summary':'Select a native option by value or displayed label.','fields':{'target':target(True),'value':field('string','Option value or label.',True)}},
 'check':{'kind':'gui','summary':'Set checkbox or radio state.','fields':{'target':target(True),'checked':field('boolean','Checked state; default true.')}},
 'press':{'kind':'gui','summary':'Press a key or chord on the focused element or target.','fields':{'target':target(),'key':field('string','Playwright key name, for example Enter, Escape, Control+Z.',True)}},
 'pointer':{'kind':'gui','summary':'Pointer action in viewport pixels or relative to target.','fields':{**GESTURE,'action':field('string','Pointer action; default click.',enum=['click','down','up','move','drag']),'click_count':COUNT}},
 'drag':{'kind':'gui','summary':'Drag from x,y to to_x,to_y through optional via points.','fields':dict(GESTURE)},
 'wheel':{'kind':'gui','summary':'Scroll at viewport coordinates or a point in a target.','fields':{'target':target(),'x':number('Pointer x.',True),'y':number('Pointer y.',True),'delta_x':number('Horizontal delta, -5000..5000.'),'delta_y':number('Vertical delta, -5000..5000; positive scrolls down.'),'modifiers':HELD}},
 'wait':{'kind':'gui','summary':'Wait up to 3 seconds for asynchronous processing.','fields':{'seconds':number('Seconds, 0..3; default 0.5.')}},
 'upload':{'kind':'gui','summary':'Supply one file to the pending file chooser, or to a visible file input target.','fields':{'target':target(),'stage':field('boolean','For a pending multiple-file chooser: stage this file without closing it; a later upload with stage false submits all staged files together. At most 12 files / 32 MB total.'),**FILE_FIELDS}},
 'reuse_download':{'kind':'gui','summary':'Supply an existing product download to the pending file chooser, for opening the exported document again.','fields':{'ref':field('string','Download ref from the current snapshot.',True)}},
 'drop':{'kind':'gui','summary':'Drop one file at a point on the page.','fields':{'target':target(),'x':number('Drop x.',True),'y':number('Drop y.',True),**FILE_FIELDS}},
 'dialog':{'kind':'gui','summary':'Set a one-shot response to the next native dialog.','fields':{'action':field('string','Answer.',True,enum=['accept','dismiss']),'text':field('string','Prompt text when accepting.')}},
 'download':{'kind':'files','summary':'Retrieve one pending product download as body_base64.','fields':{'ref':field('string','A download ref from the current snapshot.',True)}},
 'clipboard':{'kind':'observe','summary':'Read text copied by the page through the browser clipboard.','fields':{}},
})
NOTES=[
 'One Chromium page, 1280x900, en-US, UTC. All tool pages shown by the application can be navigated. Only bundled PDF viewer frames are allowed. Their controls have frame-prefixed refs; bounds are viewport coordinates.',
 'A page requesting browser printing creates a PDF download using Chromium print-to-PDF, its print stylesheet and default Letter paper unless CSS specifies a page size.',
 'All actions return a fresh snapshot. Use wheel to scroll long pages and sidebars. Native dialogs accept defaults unless dialog supplies a one-shot answer. New windows are closed; page-created exports may become downloads.',
 'Uploads are bounded in-memory files, never server filesystem paths. File pickers accept bytes through upload. Use Add More controls to add further files. The File System Access API is unavailable.',
 'reuse_download supplies an earlier generated file to a pending chooser without consuming it, so exported documents can be reopened or passed into another product tool.',
 'For a native chooser accepting multiple files, upload with stage true holds a file; the final upload (stage false) submits the group together. Staged files are submitted together when staging ends.',
 'Downloads are PDF, document, image, text, structured-data, certificate or ZIP files generated by the page or delivered as a same-origin HTTP attachment. HTTP exports must have an allowed MIME type, file suffix and content; redirects stay on the application origin. Executable/code downloads and archives containing executable/code entries are refused. Downloads are retrieved once and reset clears them.',
 'The browser reaches only the application origin. No page source, arbitrary script evaluation, raw HTTP, cookies, storage, filesystem or network-log interface is available. Static code and data resources cannot be opened as documents.',
 'Code-provider configuration pages and PDF scripting are unavailable. Developer/source-view key chords are refused. Worker and WASM resources needed by the installed application load from its own origin.',
 'Incidental generated UUIDs in observations and download names are shown as [generated]; the file bytes themselves are unchanged.',
 'new Date() uses 2026-01-15T12:00:00Z; Date.now() advances from that epoch for elapsed-time checks. Math.random is seeded per document. reset clears browser storage; restart preserves it.',
]
LIMITS={'request_bytes':MAX_REQUEST_BYTES,'file_bytes':MAX_FILE_BYTES,'download_bytes':MAX_DOWNLOAD_BYTES,'pending_downloads':MAX_PENDING_DOWNLOADS,'controls':MAX_CONTROLS,'text_characters':MAX_TEXT,'value_characters':MAX_VALUE,'rpc_timeout_seconds':RPC_TIMEOUT_SEC,'in_flight':MAX_IN_FLIGHT,'wait_seconds':3}
EXAMPLES=[{'op':'open'},{'op':'open','path':'/rotate-pdf.html'},{'op':'snapshot'},{'op':'click','target':{'text':'Click to select a file or drag and drop'}},{'op':'screenshot'}]
INIT_SCRIPT=r'''(()=>{
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

 const RealDate=Date; const instant=Date.parse('2026-01-15T12:00:00Z'); const startTick=performance.now();
 class FixedDate extends RealDate {constructor(...a){super(...(a.length?a:[instant]));}static now(){return instant+Math.floor(performance.now()-startTick);}}
 window.Date=FixedDate;let seed=17531;Math.random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
 for(const k of ['showOpenFilePicker','showSaveFilePicker','showDirectoryPicker']){try{delete window[k];delete Window.prototype[k];}catch(e){}}
 document.addEventListener('click',e=>{const t=e.composedPath?e.composedPath()[0]:e.target;if(t instanceof HTMLInputElement&&['color','date','time','datetime-local','month','week'].includes(t.type))e.preventDefault();},true);
 window.print=()=>window.__blackboxPrint();
 // PDF.js documents honor these normal viewer preferences; no document scripts are run.
 try{const p=JSON.parse(localStorage.getItem('pdfjs.preferences')||'{}');p.enableScripting=false;localStorage.setItem('pdfjs.preferences',JSON.stringify(p));}catch(e){}
})();'''
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
lock=asyncio.Lock();config=origin=product=audit=redact=private=browser=None
state={};in_flight=0
class RequestTooLarge(ValueError):pass

LOAD_IDLE_SEC=5
CLICK_PRESS_MS=50

def text_value(value, field, *, nonempty=False, limit=None):
    if not isinstance(value, str) or (nonempty and not value):
        raise ValueError(field + ' must be a string' + (' with a value' if nonempty else ''))
    if limit is not None and len(value) > limit:
        raise ValueError(f'{field} exceeds {limit} characters')
    return value

def finite(value, field, low=-100.0, high=5000.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(field + ' must be a finite number')
    if not low <= value <= high:
        raise ValueError(f'{field} must lie between {low:g} and {high:g}')
    return float(value)

def gesture_points(data, drag):
    low, high = -100.0, 5000.0
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

async def read_request(request):
    length = request.headers.get('content-length')
    if length is not None and int(length) > MAX_REQUEST_BYTES:
        raise RequestTooLarge('Request exceeds 16 MB')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
            raise RequestTooLarge('Request exceeds 16 MB')
        body.extend(chunk)
    return bytes(body)

async def start_product(fresh):
    started = await asyncio.to_thread(product.start, fresh)
    if started:
        await asyncio.to_thread(runtime.wait_http, product)
    return product.status()

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

async def current_page():
    page = state.get('page')
    if page is None or page.is_closed():
        page = await new_page()
    return page

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

def private_roots(*paths):
    """Deployment roots as whole path prefixes, with what follows them."""
    roots = sorted({str(Path(p)) for p in paths if p and str(p) != '/'}, key=len, reverse=True)
    return r'(?<![\w.~/-])(?:' + '|'.join(re.escape(r) for r in roots) + r''')(?![\w.~-])(?:/[^\s"'<>]*)?'''

def validate_target(value):
    if not isinstance(value,dict):raise ValueError('target must be a locator object')
    keys={'ref','role','label','title','text','placeholder'}&value.keys()
    if len(keys)!=1 or value.keys()-(keys|{'name','nth','exact'}):raise ValueError('Use one visible locator and optional name/nth/exact; no arbitrary selectors')
    key=next(iter(keys));text_value(value[key],'target.'+key,nonempty=True,limit=400)
    if key=='ref' and not REF.fullmatch(value[key]):raise ValueError('Use a ref from the latest snapshot')
    if key=='role' and not re.fullmatch('[a-z][a-z0-9]*',value[key]):raise ValueError('Invalid ARIA role')
    if 'name' in value:
        if key!='role':raise ValueError('name applies only to role')
        text_value(value['name'],'name',limit=400)
    if 'nth' in value and (type(value['nth']) is not int or not 0<=value['nth']<=1000):raise ValueError('nth must be 0..1000')
    if 'exact' in value and type(value['exact']) is not bool:raise ValueError('exact must be boolean')

def file_bytes(data):
    name=text_value(data.get('filename'),'filename',nonempty=True,limit=200)
    if name in ('.','..') or any(c in name for c in '/\\\x00') or any(ord(c)<32 or ord(c)==127 for c in name):raise ValueError('filename must be a basename without control characters')
    text_value(data.get('mime_type','application/octet-stream'),'mime_type',nonempty=True,limit=100)
    try:content=base64.b64decode(text_value(data.get('base64'),'base64'),validate=True)
    except ValueError:raise ValueError('Invalid base64') from None
    if len(content)>MAX_FILE_BYTES:raise ValueError('File exceeds 10 MB')
    return content

def public_path(path):
    try:path=urllib.parse.unquote(path,errors='strict')
    except (ValueError,UnicodeDecodeError):return None
    if any(ord(c)<32 or ord(c)==127 or c=='\\' for c in path) or path.startswith('//'):return None
    parts=path.split('/')
    if any(p in ('.','..') for p in parts):return None
    if len(parts)>2 and parts[1] in LANGUAGES:path='/'+('/'.join(parts[2:]) or 'index.html')
    return path

def entry_path(value):
    text_value(value,'path',nonempty=True,limit=500)
    u=urllib.parse.urlsplit(value)
    if u.scheme or u.netloc or u.query or not value.startswith('/') or public_path(u.path) not in PAGE_PATHS:
        raise ValueError('Only product page paths listed by the application may be opened')
    return value

def same_origin(u):
    host=urllib.parse.urlsplit(origin)
    return (u.scheme,u.hostname,u.port)==(host.scheme,host.hostname,host.port)

def page_path(url):
    u=urllib.parse.urlsplit(url)
    return u.path+('#'+u.fragment if u.fragment else '')

def allowed_navigation(u,frame=False):
    if not same_origin(u):return False
    path=public_path(u.path)
    if frame and path in FRAME_PATHS:
        query=urllib.parse.parse_qs(u.query)
        return set(query)<={'file'} and all(v.startswith('blob:'+origin+'/') for v in query.get('file',[]))
    return not u.query and path in PAGE_PATHS

def on_product(page):
    return allowed_navigation(urllib.parse.urlsplit(page.url))

def sanitize_text(text):
    text=str(text).replace(origin,'[application]') if origin else str(text)
    text=re.sub(r'(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])','[generated]',text,flags=re.I)
    if redact is not None:text=redact(private.sub('[private path]',text))
    return re.sub(r'blob:\[application\]/[^\s"<>]+','[document]',text)

def clean(value):
    if isinstance(value,str):return sanitize_text(value)
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    return value

async def guard_documents(page):
    bad=[]
    for frame in page.frames:
        if frame.url=='about:blank':continue
        if not allowed_navigation(urllib.parse.urlsplit(frame.url),frame!=page.main_frame):bad.append(frame)
    if bad:
        state['blocked']={'kind':'navigation','path':'[document outside the permitted product pages]'}
        await page.goto('about:blank')
        return False
    return page.url!='about:blank'

def frame_ref(frame):
    if frame==state['page'].main_frame:return ''
    # The product's public viewer path identifies its frame independently of process/port/blob identifiers.
    return 'f'+hashlib.sha256(page_path(frame.url).encode()).hexdigest()[:10]

async def visible_frames(page):
    result=[(page.main_frame,'',0,0)]
    for frame in page.frames:
        if frame==page.main_frame or not allowed_navigation(urllib.parse.urlsplit(frame.url),True):continue
        try:
            box=await (await frame.frame_element()).bounding_box()
            if box and box['x']<1280 and box['y']<900 and box['x']+box['width']>0 and box['y']+box['height']>0:
                result.append((frame,frame_ref(frame),box['x'],box['y']))
        except PlaywrightError:pass
    return result

async def snapshot(page):
    await guard_documents(page)
    data={'url':page_path(page.url) if on_product(page) else 'about:blank','title':'','viewport':[1280,900],
          'controls':[],'canvases':[],'text':'','controls_truncated':False,'text_truncated':False}
    if on_product(page):
        texts=[]
        for frame,ref,dx,dy in await visible_frames(page):
            try:part=await frame.evaluate(SNAPSHOT_SCRIPT,[{'controls':MAX_CONTROLS,'text':MAX_TEXT}])
            except PlaywrightError:continue
            if not ref:data['title']=part['title']
            texts.append(part['text'])
            for kind in ('controls','canvases'):
                for c in part[kind]:
                    x,y,w,h=c['bounds'];x+=dx;y+=dy
                    left,top,right,bottom=max(0,x),max(0,y),min(1280,x+w),min(900,y+h)
                    if right-left<1 or bottom-top<1:continue
                    c['bounds']=[round(v) for v in [left,top,right-left,bottom-top]]
                    if ref:c['ref']=ref+':'+c['ref'];c['frame']=ref
                    data[kind].append(c)
            data['controls_truncated']|=part['controls_truncated']
            data['text_truncated']|=part['text_truncated']
        data['text']='\n'.join(texts)[:MAX_TEXT]
        data['controls']=data['controls'][:MAX_CONTROLS]
    data['downloads']=[meta for _,meta in state.get('downloads',{}).values()]
    if state.get('chooser') is not None:data['file_chooser']={'multiple':state['chooser'].is_multiple(),'staged_files':[x['name'] for x in state.get('staged',[])]}
    if state.get('dialogs'):data['dialogs'],state['dialogs']=state['dialogs'],[]
    if state.get('blocked'):data['blocked'],state['blocked']=state['blocked'],None
    return clean(data)

def acceptable_download(filename,content):
    suffix=Path(filename).suffix.lower()
    if suffix not in DOWNLOAD_SUFFIXES or len(content)>MAX_DOWNLOAD_BYTES or not content:return False
    if suffix in {'.zip','.cbz','.xlsx','.docx'}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                entries=z.infolist()
                if len(entries)>10000 or sum(i.file_size for i in entries)>200_000_000:return False
                for i in entries:
                    name=i.filename.replace('\\','/')
                    if name.startswith('/') or '..' in name.split('/') or '\x00' in name:return False
                    if Path(name).suffix.lower() in {'.js','.mjs','.cjs','.map','.wasm','.so','.dll','.exe','.py','.sh','.bat','.whl','.tgz'}:return False
        except (ValueError,zipfile.BadZipFile):return False
    if suffix=='.pdf' and b'%PDF-' not in content[:1024]:return False
    return True

def add_download(filename,content,mime=None):
    filename=sanitize_text(Path(filename).name[:200]) or 'download'
    if not acceptable_download(filename,content):
        state['blocked']={'kind':'download','path':'[unsupported format or size]'};return
    ref='d'+hashlib.sha256(filename.encode()).hexdigest()[:12]
    if ref not in state['downloads'] and len(state['downloads'])>=MAX_PENDING_DOWNLOADS:
        state['blocked']={'kind':'download','path':'[too many pending downloads]'};return
    meta={'ref':ref,'filename':filename,'size':len(content)}
    if mime:meta['type']=mime
    state['downloads'][ref]=(content,meta)

HTTP_EXPORT_TYPES={'application/pdf','application/zip','application/x-zip-compressed','application/octet-stream',
 'image/png','image/jpeg','image/webp','image/bmp','image/tiff','image/svg+xml','text/plain','text/csv','text/markdown',
 'application/json','application/xml','text/xml','text/html','application/vnd.openxmlformats-officedocument.wordprocessingml.document',
 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/x-pkcs12','application/pkcs12',
 'application/pkix-cert','application/x-x509-ca-cert','application/x-pem-file'}

def export_headers(url,headers):
    parsed=urllib.parse.urlsplit(url)
    if not same_origin(parsed) or public_path(parsed.path) is None:return None
    message=Message();message['Content-Disposition']=headers.get('content-disposition','')
    if message.get_content_disposition()!='attachment':return None
    name=message.get_filename() or Path(parsed.path).name
    mime=headers.get('content-type','').split(';',1)[0].strip().lower()
    if mime not in HTTP_EXPORT_TYPES or Path(name).suffix.lower() not in DOWNLOAD_SUFFIXES:return None
    if any(c in name for c in '/\\\x00') or any(ord(c)<32 for c in name):return None
    try:
        if int(headers.get('content-length','0'))>MAX_DOWNLOAD_BYTES:return None
    except ValueError:return None
    return {'filename':name,'mime':mime}

async def new_page():
    await close_page()
    context=await browser.new_context(locale='en-US',timezone_id='UTC',viewport=VIEWPORT,service_workers='block',
                                      accept_downloads=True,permissions=['clipboard-read','clipboard-write'])
    state.update(context=context,downloads={},http_exports={},staged=[],chooser=None,dialog=None,dialogs=[],blocked=None,tasks=set())
    async def restrict(route):
        req=route.request;u=urllib.parse.urlsplit(req.url)
        if req.is_navigation_request():
            try:main=req.frame==state.get('page').main_frame
            except (PlaywrightError,AttributeError):main=False
            if allowed_navigation(u,not main):await route.continue_();return
            if same_origin(u) and public_path(u.path) is not None:
                # An ordinary same-origin HTTP attachment is a file export, never a navigable document.
                # Inspect responses without following a redirect to an unapproved origin or exposing a body.
                response=None
                try:
                    export_url=req.url
                    for _ in range(6):
                        response=await route.fetch(url=export_url,max_redirects=0,timeout=30000)
                        if response.status not in (301,302,303,307,308):break
                        location=response.headers.get('location','');next_url=urllib.parse.urljoin(export_url,location)
                        if not same_origin(urllib.parse.urlsplit(next_url)):break
                        export_url=next_url
                    meta=export_headers(export_url,response.headers) if response else None
                    if meta and response.ok:
                        data=await response.body()
                        if acceptable_download(meta['filename'],data):
                            state['http_exports'][req.url]=meta
                            await route.fulfill(response=response,body=data)
                            return
                except PlaywrightError:pass
            state['blocked']={'kind':'navigation','path':'[navigation outside product pages]'}
            if main:await route.fulfill(status=204,body='')
            else:await route.abort()
            return
        if u.scheme in {'data','blob'}:await route.continue_();return
        if not same_origin(u):await route.abort();return
        path=public_path(u.path)
        if path is None or path.endswith(NOT_FETCHED) or 'sandbox' in path.lower() or path.endswith('/package.json'):
            await route.abort();return
        kind=req.resource_type
        if kind in {'script','stylesheet','image','font','fetch','xhr','other'}:
            # PDF and OCR workers fetch local resources as part of normal processing. Only the static serving
            # policy decides which resources exist; no RPC exposes their bodies as observations.
            if kind in {'fetch','xhr'} and path.endswith(('.html','.htm')):await route.abort();return
            await route.continue_()
        else:await route.abort()
    await context.route('**/*',restrict)
    await context.route_web_socket('**/*',lambda ws:ws.close())
    async def print_document(source):
        page=state.get('page')
        if page is None or source.get('page')!=page or not await guard_documents(page):return
        content=await page.pdf(print_background=True,prefer_css_page_size=True,format='Letter')
        add_download('document.pdf',content,'application/pdf')
    await context.expose_binding('__blackboxPrint',print_document)
    await context.add_init_script(INIT_SCRIPT)
    page=await context.new_page();state['page']=page
    def response_export(response):
        meta=export_headers(response.url,response.headers)
        if meta:state['http_exports'][response.url]=meta
    context.on('response',response_export)
    def track(coro):
        task=asyncio.ensure_future(coro);state['tasks'].add(task)
        task.add_done_callback(lambda t:state.get('tasks',set()).discard(t))
    async def answer(dialog):
        plan=state.get('dialog');state['dialog']=None
        entry={'type':dialog.type,'message':dialog.message[:500]}
        try:
            if plan and plan['action']=='dismiss':await dialog.dismiss();entry['answer']='dismissed'
            elif dialog.type=='prompt':
                txt=(plan or {}).get('text',dialog.default_value)
                if txt is None:txt=dialog.default_value
                await dialog.accept(txt);entry.update(answer='accepted',text=txt[:500])
            else:await dialog.accept();entry['answer']='accepted'
        except PlaywrightError:pass
        state['dialogs']=(state.get('dialogs',[])+[entry])[-8:]
    async def download(d):
        if not await guard_documents(page) or not (d.url.startswith(('blob:','data:')) or d.url in state.get('http_exports',{})):
            await d.cancel();state['blocked']={'kind':'download','path':'[not an approved product export]'};return
        try:
            path=await d.path()
            if path:
                with open(path,'rb') as f:content=f.read(MAX_DOWNLOAD_BYTES+1)
                add_download(d.suggested_filename,content)
        except PlaywrightError:pass
        finally:
            try:await d.delete()
            except PlaywrightError:pass
    async def extra_window(extra):
        try:
            deadline=time.monotonic()+EXPORT_WINDOW_SEC
            while extra.url=='about:blank' and time.monotonic()<deadline and not extra.is_closed():await asyncio.sleep(.05)
            if await guard_documents(page) and extra.url.startswith(('blob:','data:')):
                fetched=await page.evaluate(FETCH_SCRIPT,[extra.url,MAX_DOWNLOAD_BYTES])
                if fetched and fetched.get('base64'):
                    mime=fetched.get('type','').split(';')[0]
                    ext={'application/pdf':'.pdf','image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp','image/svg+xml':'.svg'}.get(mime)
                    if ext:add_download('export'+ext,base64.b64decode(fetched['base64']),mime)
        except PlaywrightError:pass
        finally:
            try:await extra.close()
            except PlaywrightError:pass
    page.on('dialog',lambda d:track(answer(d)))
    page.on('download',lambda d:track(download(d)))
    page.on('filechooser',lambda c:state.__setitem__('chooser',c))
    context.on('page',lambda extra:track(extra_window(extra)) if extra!=state.get('page') else None)
    page.set_default_timeout(ACTION_TIMEOUT_MS);page.set_default_navigation_timeout(30000)
    return page

async def resolve(page,value,want='element'):
    validate_target(value);spec=dict(value);frames=[]
    if ':' in spec.get('ref',''):
        prefix,spec['ref']=spec['ref'].split(':',1)
        frames=[f for f in page.frames if frame_ref(f)==prefix]
    else:frames=[page.main_frame]
    for frame in frames:
        h=await frame.evaluate_handle(FIND_SCRIPT,[spec,want]);el=h.as_element()
        if el is not None:return el
    raise ValueError('No visible control matches; use the latest snapshot')

async def to_viewport(page,data,points):
    if data.get('target'):
        element=await resolve(page,data['target']);box=await element.bounding_box()
        if not box:raise ValueError('Target is not visible')
        for x,y in points:
            if not (0<=x<=box['width'] and 0<=y<=box['height']):raise ValueError('Point must lie inside target')
        points=[(box['x']+x,box['y']+y) for x,y in points]
    if any(not(0<=x<1280 and 0<=y<900) for x,y in points):raise ValueError('Point must lie inside viewport')
    return points

def validate_request(data):
    op=runtime.validate(OPERATIONS,data)
    if 'target' in data:validate_target(data['target'])
    if op=='open':entry_path(data.get('path','/'))
    if op in {'fill','type','select'}:text_value(data['value'],'value',limit=MAX_VALUE)
    if op=='press':check_key(data['key'])
    if op in {'pointer','drag'}:gesture_points(data,op=='drag' or data.get('action')=='drag')
    if op in {'wheel','drop'}:finite(data['x'],'x');finite(data['y'],'y')
    if op=='wheel':finite(data.get('delta_x',0),'delta_x',-5000,5000);finite(data.get('delta_y',0),'delta_y',-5000,5000)
    if op=='wait':finite(data.get('seconds',.5),'seconds',0,3)
    if op in {'upload','drop'}:file_bytes(data)
    if op=='upload' and data.get('stage') and 'target' in data:raise ValueError('Staging requires a pending multiple-file chooser')
    if op=='dialog' and 'text' in data:text_value(data['text'],'text',limit=4000)
    if op in {'download','reuse_download'} and not re.fullmatch(r'd[0-9a-f]{12}',data['ref']):raise ValueError('Use a download ref from the snapshot')
    return op

async def element_action(page,op,data):
    element=await resolve(page,data['target'],'field' if op in {'fill','select','check','upload','type'} else 'element')
    if op=='click':await acting(page,lambda:element.click(button=data.get('button','left'),click_count=data.get('click_count',1),modifiers=data.get('modifiers') or None))
    elif op=='hover':await acting(page,lambda:element.hover())
    elif op=='fill':
        if await element.get_attribute('type')=='range':
            async def slide():
                await element.evaluate('(e,v)=>{e.value=v;e.dispatchEvent(new Event("input",{bubbles:true}));e.dispatchEvent(new Event("change",{bubbles:true}));}',data['value'])
            await acting(page,slide)
        else:await acting(page,lambda:element.fill(data['value']))
    elif op=='type':
        async def typing():await element.focus();await page.keyboard.type(data['value'])
        await acting(page,typing)
    elif op=='select':
        async def choose():
            values=await element.evaluate('(e)=>[...e.options].map(o=>o.value)')
            await element.select_option(value=data['value']) if data['value'] in values else await element.select_option(label=data['value'])
        await acting(page,choose)
    elif op=='check':await acting(page,lambda:element.set_checked(data.get('checked',True)))
    elif op=='press':await acting(page,lambda:element.press(data['key']))
    elif op=='upload':await acting(page,lambda:element.set_input_files({'name':data['filename'],'mimeType':data.get('mime_type','application/octet-stream'),'buffer':file_bytes(data)}))

async def dispatch(data):
    op=validate_request(data)
    if op=='help':return runtime.help_document(PRODUCT,'browser',OPERATIONS,limits=LIMITS,notes=NOTES,examples=EXAMPLES)
    if op=='status':return product.status()
    if op=='reset':await new_page();return await start_product(True)
    if op=='restart':return await start_product(False)
    page=await current_page()
    if op=='open':
        state['chooser']=None;state['staged']=[];await page.goto(origin+entry_path(data.get('path','/')),wait_until='domcontentloaded');await loaded(page);return await snapshot(page)
    await guard_documents(page)
    if op=='download':
        if data['ref'] not in state['downloads']:raise ValueError('Unknown download ref')
        content,meta=state['downloads'].pop(data['ref']);return {**meta,'body_base64':base64.b64encode(content).decode(),'truncated':False}
    if op=='snapshot':await settled(page);return await snapshot(page)
    if op=='screenshot':
        await settled(page);await guard_documents(page)
        return {'png_base64':base64.b64encode(await page.screenshot(full_page=False,animations='disabled',timeout=30000)).decode(),'width':1280,'height':900}
    if op=='dialog':state['dialog']={k:data[k] for k in ('action','text') if k in data};return await snapshot(page)
    if not on_product(page):raise ValueError('Open a product page first')
    if op=='clipboard':return {'text':sanitize_text((await page.evaluate('()=>navigator.clipboard.readText()'))[:MAX_VALUE])}
    if op=='reload':state['chooser']=None;state['staged']=[];await page.reload(wait_until='domcontentloaded');await loaded(page)
    elif op in {'pointer','drag'}:await acting(page,lambda:pointer_action(page,data))
    elif op=='wheel':
        async def wheel():
            (x,y),=await to_viewport(page,data,[(float(data['x']),float(data['y']))])
            for key in data.get('modifiers',[]):await page.keyboard.down(key)
            try:await page.mouse.move(x,y);await page.mouse.wheel(float(data.get('delta_x',0)),float(data.get('delta_y',0)))
            finally:
                for key in reversed(data.get('modifiers',[])):await page.keyboard.up(key)
        await acting(page,wheel)
    elif op=='drop':
        async def drop():
            (x,y),=await to_viewport(page,data,[(float(data['x']),float(data['y']))])
            r=await page.evaluate(DROP_SCRIPT,[x,y,data['filename'],data.get('mime_type','application/octet-stream'),data['base64']])
            if 'error' in r:raise ValueError(r['error'])
        await acting(page,drop)
    elif op=='wait':await page.wait_for_timeout(1000*data.get('seconds',.5));await settled(page)
    elif op=='reuse_download':
        chooser=state.get('chooser')
        if chooser is None:raise ValueError('Open a file chooser first')
        if data['ref'] not in state['downloads']:raise ValueError('Unknown download ref')
        content,meta=state['downloads'][data['ref']]
        state['chooser']=None;state['staged']=[]
        import mimetypes
        await acting(page,lambda:chooser.set_files({'name':meta['filename'],'mimeType':mimetypes.guess_type(meta['filename'])[0] or 'application/octet-stream','buffer':content}))
    elif op=='upload' and 'target' not in data:
        chooser=state.get('chooser')
        if chooser is None:raise ValueError('Open a file chooser with the application first')
        payload={'name':data['filename'],'mimeType':data.get('mime_type','application/octet-stream'),'buffer':file_bytes(data)}
        staged=state.setdefault('staged',[])
        if data.get('stage') and not chooser.is_multiple():raise ValueError('This file chooser accepts only one file')
        if len(staged)>=12 or sum(len(x['buffer']) for x in staged)+len(payload['buffer'])>32_000_000:raise ValueError('Staged file limit exceeded')
        if data.get('stage'):
            staged.append(payload)
        else:
            payloads=[*staged,payload];state['staged']=[];state['chooser']=None
            await acting(page,lambda:chooser.set_files(payloads if chooser.is_multiple() else payload))
    elif op in {'type','press'} and 'target' not in data:
        await acting(page,lambda:page.keyboard.type(data['value']) if op=='type' else page.keyboard.press(data['key']))
    else:
        try:await element_action(page,op,data)
        except PlaywrightTimeout:raise ValueError('Control did not accept the action: it may be disabled, covered or not editable') from None
    return await snapshot(page)

@app.post('/rpc')
async def rpc(request:Request):
    global in_flight
    if in_flight>=MAX_IN_FLIGHT:return JSONResponse({'error':'Busy','detail':'Too many pending requests'},429)
    in_flight+=1;started=time.monotonic();data=None
    try:
        async with asyncio.timeout(RPC_TIMEOUT_SEC):
            data=runtime.strict_json_loads(await read_request(request))
            async with lock:result=await dispatch(data)
        code=200
    except RequestTooLarge as e:result,code={'error':'RequestTooLarge','detail':str(e)},413
    except TimeoutError:result,code={'error':'TimeoutError','detail':'Black-box request deadline exceeded'},408
    except runtime.RuntimeCleanupError as e:
        result,code={'error':'RuntimeCleanupError','detail':sanitize_text(redact(private.sub('[private path]',str(e))))[:600]},500
    except Exception as e:
        result,code={'error':type(e).__name__,'detail':sanitize_text(redact(private.sub('[private path]',str(e).split('Call log:')[0])))[:600]},400
    finally:in_flight-=1
    audit.record(data.get('op','help') if isinstance(data,dict) else None,code,time.monotonic()-started)
    return JSONResponse(result,code)

async def main(argv=None):
    global config,origin,product,audit,redact,private,browser
    config=runtime.options(socket_mode='0600').parse_args(argv);origin=f'http://127.0.0.1:{config.port}'
    work=Path(config.work);work.mkdir(parents=True,exist_ok=True);work.chmod(0o700)
    product=runtime.Product(config,log=runtime.BoundedLog(config.log_dir))
    Path(config.log_dir).chmod(0o700)
    Path(config.socket).parent.mkdir(parents=True,exist_ok=True)
    Path(config.socket).parent.chmod(0o700)
    audit=runtime.Audit(Path(config.log_dir)/'rpc-audit.jsonl')
    roots=(config.solution,config.state,config.work,config.log_dir,Path(__file__).resolve().parent,
           Path(config.socket).parent,Path.home(),product.account().pw_dir)
    redact=runtime.redactor(*roots);private=re.compile(private_roots(*roots))
    runtime.exit_on_sigterm()
    async with async_playwright() as p:
        # Eager baseline WASM compilation avoids stalls observed with the browser's
        # concurrent tier-up/lazy compilation. Apply the same engine settings to every target.
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--js-flags=--no-wasm-tier-up --no-wasm-lazy-compilation --wasm-num-compilation-tasks=1'],downloads_path=str(work/'downloads'))
        try:
            await new_page();await start_product(True)
            sock=runtime.listen(config.socket,config.socket_mode)
            server=uvicorn.Server(uvicorn.Config(app,access_log=False,log_level='warning'))
            runtime.exit_on_sigterm();await server.serve(sockets=[sock])
        finally:await close_page();await asyncio.to_thread(product.stop);await browser.close()
if __name__=='__main__':asyncio.run(main())
