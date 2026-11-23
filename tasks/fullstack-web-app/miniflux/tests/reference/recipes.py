"""Pinned-standard GUI implementation of the reviewed goals, through the black-box runtime (record only).

The recipes drive the standard answer with the same runtime GUI operations that the evaluator and the model
use; BrokerSurface.observe() captures the reference evidence. Control names, form fields and routes below
belong to the pinned standard only; they are never a candidate requirement. API reads only confirm that a
browser mutation was saved before the evidence is taken.
"""
import base64
import re
import time

from checks import resolve
from harness import CREDS
from .ui import UI, accessible, action_pattern


def corroborate(c, path, predicate, actor='alice', timeout=10.0, what='browser mutation not saved'):
    """Wait until the product reports the browser mutation through its public API."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        r, p = c.request('GET', path, actor)
        last = (r.status_code, p)
        try:
            if r.status_code == 200 and predicate(p):
                return p
        except (KeyError, TypeError, IndexError):
            pass
        time.sleep(0.2)
    raise AssertionError(what + ': ' + str(last)[:400])


def step(ui, c, ctx, a):
    op = a['op']
    if op == 'goto':
        ui.goto(a['path'])
    elif op == 'reload':
        ui.reload()
    elif op == 'click':
        ui.click(*a['names'])
    elif op == 'link':
        ui.link(a['href'])
    elif op == 'expand':
        # Open a collapsed <details> section by its summary; a section already open (its probe text is visible,
        # for example an enabled integration) stays open.
        snap = ui.snapshot()
        if a.get('probe') and a['probe'] in snap['text']:
            return
        summary = next((x for x in snap['controls'] if x['tag'] == 'summary' and x.get('text') == a['text']), None)
        assert summary, 'section missing: ' + a['text']
        if not summary.get('expanded', False):
            ui.click_ref(summary)
            if a.get('probe'):
                ui.require(a['probe'])
    elif op == 'fill':
        ui.fill(a['field'], a['value'])
    elif op == 'check':
        ui.check(a['field'], a.get('value', True))
    elif op == 'select':
        ui.select(a['field'], a['value'])
    elif op == 'press':
        if a.get('field'):
            ui.call('press', target={'ref': ui.field(a['field'])['ref']}, key=a['key'])
        else:
            ui.call('press', key=a['key'])
    elif op == 'upload':
        data = (ctx.inputs / a['file']).read_bytes()
        ui.call('upload', target={'ref': ui.field(a['field'])['ref']}, filename=a['file'],
                mime_type=a.get('mime_type', 'application/octet-stream'), base64=base64.b64encode(data).decode())
    elif op == 'require':
        ui.require(*a['texts'])
    elif op == 'require-absent':
        # After the page had time to react, none of the texts is visible.
        ui.call('wait', seconds=a.get('seconds', 1))
        text = ui.snapshot()['text']
        present = [x for x in a['texts'] if x in text]
        assert not present, 'unexpected visible text: ' + repr(present)
    elif op == 'wait-url':
        ui.wait(lambda s: s['url'].split('?')[0] == a['path'], 'page not reached: ' + a['path'])
    elif op == 'sleep':
        ui.call('wait', seconds=a['seconds'])
    elif op == 'corroborate':
        expected = a['expect']
        corroborate(c, a['path'], lambda p: all(_lookup(p, k) == v for k, v in expected.items()),
                    actor=a.get('actor', 'alice'))
    elif op == 'choose':
        # A radio button or checkbox known by its label.
        snap = ui.snapshot()
        control = next((x for x in snap['controls'] if x['tag'] == 'input' and x.get('type') in ('radio', 'checkbox')
                        and (x.get('label') or '').strip() == a['label']), None)
        assert control, 'choice missing: ' + a['label']
        ui.call('check', target={'ref': control['ref']}, checked=a.get('value', True))
    elif op == 'click-nth':
        # The nth (page order) of several buttons with the same name.
        patterns = [action_pattern(n) for n in a['names']]
        snap = ui.snapshot()
        matches = [x for x in snap['controls'] if (x['tag'] == 'button' or x.get('type') in ('submit', 'button'))
                   and not x.get('disabled') and any(p.search(n) for p in patterns for n in accessible(x))]
        assert len(matches) > a['nth'], 'action missing: ' + str(a['names'])
        ui.click_ref(matches[a['nth']])
    elif op == 'require-download':
        ui.wait(lambda s: any(d.get('filename', '').endswith(a['suffix']) for d in s.get('downloads') or []),
                'download missing: ' + a['suffix'])
    elif op == 'row':
        # An action of one listed item (entry, feed, category or user): the first matching control after the
        # item's anchor link in page order.
        ui.click_ref(row_control(ui, a))
    elif op == 'open-feed-edit':
        # The settings page of the feed subscribed from a URL (its id is the product's own).
        feeds = corroborate(c, 'feeds', lambda p: any(f['feed_url'] == a['feed_url'] for f in p))
        ui.goto('/feed/%d/edit' % next(f['id'] for f in feeds if f['feed_url'] == a['feed_url']))
    elif op == 'sign-in':
        ui.sign_in(a['user'], a['password'])
    elif op == 'sign-out':
        ui.click('Logout')
        ui.wait(lambda s: s['url'].split('?')[0] == '/', 'sign-out did not complete')
    else:
        raise AssertionError('unknown recipe step ' + op)


def label(control):
    """A link's own label: its first text line without an unread counter."""
    text = (control.get('text') or '').split('\n')[0].strip()
    return re.sub(r'\s*\(\d+\)$', '', text)


def row_control(ui, a, timeout=5.0):
    deadline = time.monotonic() + timeout
    patterns = [action_pattern(n) for n in a['names']]
    while True:
        snap = ui.snapshot()
        controls = snap['controls']
        anchors = [i for i, x in enumerate(controls) if x['tag'] == 'a' and (
            (a.get('anchor') and label(x) == a['anchor']) or (a.get('href') and x.get('href') == a['href']))]
        if anchors:
            for x in controls[anchors[0] + 1:]:
                if not x.get('disabled') and any(p.search(n) for p in patterns for n in accessible(x)):
                    return x
        if time.monotonic() > deadline:
            raise AssertionError('item action missing: ' + str(a))
        time.sleep(0.2)


def _lookup(value, path):
    for part in path.split('.'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def execute(ctx, c, checkpoint):
    episode = ctx.episode
    actor = episode.get('actor')
    ui = ctx.state.setdefault('ui', UI(ctx.broker))
    if actor and not ctx.state.get('signed_in'):
        ui.sign_in(actor, CREDS[actor])
        ctx.state['signed_in'] = True
    for raw in checkpoint['recipe']:
        step(ui, c, ctx, resolve(raw, c.state))
    # The reference after-evidence must visibly show what the acceptance condition describes.
    for text in checkpoint.get('visible', []):
        ui.require(resolve(text, c.state))
    time.sleep(0.2)
