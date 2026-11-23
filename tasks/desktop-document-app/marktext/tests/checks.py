"""Independent program checks of the documents the application writes or copies.

A check names a public artifact (a saved or exported file, an outbox listing,
or the desktop clipboard) and one aspect of it. Artifacts are read only through
the runtime: list_files and download for the exchange folders, clipboard_text,
clipboard_html and clipboard_image for the clipboard. Each artifact is observed
once per checkpoint with artifacts.py's serializer-neutral normalization; each
aspect assertion compares its projection with the frozen reference projection.
"""
from __future__ import annotations

import base64
import re
import time

import artifacts

SETTLE_SECONDS = 20
AREAS = {'inbox': 'inbox', 'outbox': 'outbox'}


def locate(path):
    folder, _, name = path.partition('/')
    if folder not in AREAS or not name or '/' in name:
        raise ValueError('check paths name a file directly in inbox/ or outbox/: ' + path)
    return AREAS[folder], name


def upload(ctx, name, data, *, area='inbox', read_only=False):
    request = {'op': 'upload', 'filename': name, 'base64': base64.b64encode(data).decode(), 'area': area}
    if read_only:
        request['read_only'] = True
    return ctx.broker.call(request)


def listing(ctx, area):
    return {f['name']: f['size'] for f in ctx.broker.call({'op': 'list_files', 'area': area})['files']
            if not f['read_only']}


def settled(ctx, area, name, timeout=SETTLE_SECONDS):
    """Wait for an output to exist and stop growing."""
    deadline = time.monotonic() + timeout
    previous = None
    while time.monotonic() < deadline:
        size = listing(ctx, area).get(name)
        if size is not None and size == previous:
            return True
        previous = size
        time.sleep(.4)
    return name in listing(ctx, area)


def clipboard_wait(ctx, op, field, timeout=5.0):
    """Read a clipboard flavor, polling until it is non-empty (a just-issued copy may not have landed yet) or the
    timeout elapses. A genuinely empty clipboard (a candidate that did not copy) returns empty after the wait."""
    deadline = time.monotonic() + timeout
    value = ''
    while True:
        try:
            value = ctx.broker.call({'op': op}).get(field, '') or ''
        except Exception:
            value = ''
        if value.strip() or time.monotonic() >= deadline:
            return value
        time.sleep(0.3)


def fetch(ctx, area, name):
    data = base64.b64decode(ctx.broker.call({'op': 'download', 'area': area, 'filename': name})['body_base64'])
    folder = ctx.state['artifacts']
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{len(list(folder.iterdir())) + 1:03d}-{name}'
    target.write_bytes(data)
    return data


def matching(ctx, area, pattern, timeout=SETTLE_SECONDS):
    regex = re.compile(pattern)
    deadline = time.monotonic() + timeout
    previous = None
    while True:
        names = sorted(name for name in listing(ctx, area) if regex.fullmatch(name))
        if names and names == previous:
            break
        previous = names
        if time.monotonic() > deadline:
            break
        time.sleep(.5)
    for name in names:
        settled(ctx, area, name)
    return names


# -- observe one full artifact -------------------------------------------------------------------------------------


def artifact_key(check):
    return repr(sorted((k, repr(v)) for k, v in check.items() if k not in ('aspect', 'description', 'expect')))


def observe(ctx, check):
    kind = check['kind']
    if kind == 'markdown':
        area, name = locate(check['path'])
        if not settled(ctx, area, name):
            raise AssertionError('requested document is missing: ' + name)
        return {'markdown': artifacts.normalize_markdown(fetch(ctx, area, name))}
    if kind == 'html':
        area, name = locate(check['path'])
        if not settled(ctx, area, name):
            raise AssertionError('requested HTML document is missing: ' + name)
        data = fetch(ctx, area, name)
        return {'body': artifacts.html_body(data), 'text': artifacts.html_text(data)}
    if kind == 'pdf':
        area, name = locate(check['path'])
        if not settled(ctx, area, name):
            raise AssertionError('requested PDF is missing: ' + name)
        return artifacts.pdf_summary(fetch(ctx, area, name))
    if kind == 'files':
        time.sleep(check.get('wait', 1.0))
        regex = re.compile(check.get('pattern', '.*'))
        area = AREAS[check['folder']]
        return {'files': sorted(name for name in listing(ctx, area) if regex.fullmatch(name))}
    if kind == 'image-file':
        area, name = locate(check['path'])
        if not settled(ctx, area, name):
            raise AssertionError('requested image is missing: ' + name)
        return artifacts.image_summary(fetch(ctx, area, name))
    if kind == 'clipboard-text':
        text = clipboard_wait(ctx, 'clipboard_text', 'text')
        return {'text': [line.rstrip() for line in text.replace('\r\n', '\n').split('\n')]}
    if kind == 'clipboard-html':
        html = clipboard_wait(ctx, 'clipboard_html', 'html')
        return {'body': artifacts.html_body(html.encode('utf-8')), 'text': artifacts.html_text(html.encode('utf-8'))}
    if kind == 'clipboard-image':
        payload = ctx.broker.call({'op': 'clipboard_image'})
        return artifacts.image_summary(base64.b64decode(payload['png_base64']))
    raise ValueError('unknown program check ' + kind)


def expect(full, check):
    """Record-only guard: the reference actually produced a usable artifact for this check."""
    wanted = check.get('expect') or {}
    if check['kind'] == 'markdown':
        text = full['markdown']
        if wanted.get('nonempty', True) and not text.strip():
            raise AssertionError('reference saved an empty Markdown document')
        for needle in wanted.get('contains', ()):
            if needle not in text:
                raise AssertionError(f'reference output is missing expected text {needle!r}: {text!r}')
        for needle in wanted.get('absent', ()):
            if needle in text:
                raise AssertionError(f'reference output unexpectedly contains {needle!r}: {text!r}')
        if 'equals' in wanted and text != wanted['equals']:
            raise AssertionError(f'reference output {text!r} differs from the specification {wanted["equals"]!r}')
    if check['kind'] == 'html':
        for needle in wanted.get('contains', ()):
            if needle not in full['text']:
                raise AssertionError(f'reference HTML is missing expected text {needle!r}')
    if check['kind'] == 'clipboard-text':
        if wanted.get('nonempty', True) and not any(line.strip() for line in full['text']):
            raise AssertionError('reference copied empty clipboard text')
        for needle in wanted.get('contains', ()):
            if not any(needle in line for line in full['text']):
                raise AssertionError(f'reference clipboard text is missing {needle!r}')
    if check['kind'] == 'clipboard-html':
        if wanted.get('nonempty', True) and not full['text'].strip():
            raise AssertionError('reference copied empty clipboard HTML')
        for needle in wanted.get('contains', ()):
            if needle not in full['text']:
                raise AssertionError(f'reference clipboard HTML is missing {needle!r}')
    if check['kind'] == 'files' and 'files' in wanted:
        if full['files'] != wanted['files']:
            raise AssertionError(f'reference files {full["files"]} differ from {wanted["files"]}')
    if check['kind'] == 'pdf' and 'count' in wanted:
        if full['count'] != wanted['count']:
            raise AssertionError(f'reference PDF has {full["count"]} pages, expected {wanted["count"]}')


# -- project one aspect --------------------------------------------------------------------------------------------


def project(full, check):
    aspect, kind = check['aspect'], check['kind']
    if kind == 'markdown' and aspect == 'content':
        return {'aspect': aspect, 'markdown': full['markdown']}
    if kind in ('html', 'clipboard-html'):
        if aspect == 'body':
            return {'aspect': aspect, 'body': full['body']}
        if aspect == 'text':
            return {'aspect': aspect, 'text': full['text']}
    if kind == 'pdf':
        if aspect == 'geometry':
            return {'aspect': aspect, 'pages': [{'width': p['width'], 'height': p['height']} for p in full['pages']]}
        if aspect == 'text':
            return {'aspect': aspect, 'pages': [p['text'] for p in full['pages']]}
        if aspect == 'count':
            return {'aspect': aspect, 'count': full['count']}
    if kind in ('files',) and aspect == 'files':
        return {'aspect': aspect, 'files': full['files']}
    if kind in ('image-file', 'clipboard-image'):
        if aspect == 'format':
            return {'aspect': aspect, 'format': full['format']}
        if aspect == 'resolution':
            return {'aspect': aspect, 'width': full['width'], 'height': full['height']}
        if aspect == 'pixels':
            return {'aspect': aspect, 'signature': full['signature']}
    if kind == 'clipboard-text' and aspect == 'text':
        return {'aspect': aspect, 'text': full['text']}
    raise ValueError(f'aspect {aspect} is not defined for {kind} checks')


# -- compare -------------------------------------------------------------------------------------------------------


def _pixels_close(a, b, tol=16):
    if len(a) != len(b):
        return False
    return all(abs(ca - cb) <= tol for pa, pb in zip(a, b) for ca, cb in zip(pa, pb))


def compare(actual, expected):
    aspect = expected.get('aspect')
    if not isinstance(actual, dict) or actual.get('aspect') != aspect:
        raise AssertionError('observed aspect differs')
    if aspect == 'pixels':
        if not _pixels_close(actual.get('signature', []), expected['signature']):
            raise AssertionError('image pixels differ beyond tolerance')
        return
    if actual != expected:
        raise AssertionError(f'observation differs from the reference: {actual!r} != {expected!r}')
