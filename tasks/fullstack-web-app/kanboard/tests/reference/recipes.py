"""Pinned-standard GUI implementation of the reviewed goals, through the black-box runtime (record only).

The recipes drive the standard answer with the same runtime GUI operations that the evaluator and the model use;
BrokerSurface.observe() captures the reference evidence. Control names, form fields and routes below belong to the
pinned standard only; they are never a candidate requirement. API reads only confirm that a browser mutation was saved
before the evidence is taken.
"""
import base64
from pathlib import Path
import time

from checks import fill
from specification import ADMIN_PASSWORD, PASSWORD
from .ui import UI, accessible, exact


def corroborate(c, method, params, predicate, what='browser mutation not saved', timeout=10.0):
    """Wait until the product reports the browser mutation through its public API."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        response = c.rpc(method, params, 'app')
        last = response.body
        try:
            if response.has_result and predicate(response.result):
                return response.result
        except (KeyError, TypeError, IndexError):
            pass
        time.sleep(0.25)
    raise AssertionError(what + ': ' + str(last)[:400])


def card(ui, title):
    """The board card link of a task title."""
    return ui.control(title, tags=('a',))


def drag_card(ui, title, column_title, lane=0):
    """Drag a board card into a column (the column header gives the target x; the first lane's cell the y)."""
    snap = ui.snapshot()
    source = card(ui, title)
    header = next(c for c in snap['controls'] if c['tag'] == 'a' and exact(column_title).search(c.get('text') or ''))
    sx, sy = source['bounds'][0] + 10, source['bounds'][1] + source['bounds'][3] // 2
    tx = header['bounds'][0] + 40
    ty = max(source['bounds'][1] + 20, header['bounds'][1] + 70)
    ui.call('drag', x=sx, y=sy, via=[[sx + 5, sy + 5], [(sx + tx) / 2, ty]], to_x=tx, to_y=ty, steps=10)
    ui.call('wait', seconds=1.5)


def upload(ui, ctx, name, target_label=None):
    data = (Path(ctx.inputs) / name).read_bytes()
    mime = 'image/png' if name.endswith('.png') else 'text/plain'
    request = {'filename': name, 'base64': base64.b64encode(data).decode(), 'mime_type': mime}
    snap = ui.snapshot()
    if snap.get('file_chooser'):
        ui.call('upload', **request)
        return
    control = next(c for c in reversed(snap['controls']) if c['tag'] == 'input' and c.get('type') == 'file')
    ui.call('upload', target={'ref': control['ref']}, **request)


def execute(ctx, c, checkpoint):
    episode = ctx.episode
    actor = episode.get('actor')
    ui = ctx.state.setdefault('ui', UI(ctx.broker))
    if actor and not ctx.state.get('signed_in'):
        ui.sign_in(actor, ADMIN_PASSWORD if actor == 'admin' else PASSWORD)
        ctx.state['signed_in'] = True
    for raw in checkpoint['recipe']:
        a = fill(raw, c.state)
        op = a['op']
        if op == 'goto':
            ui.goto(a['path'])
        elif op == 'reload':
            ui.reload()
        elif op == 'sign-in':
            ui.sign_in(a['user'], a['password'])
        elif op == 'sign-in-fail':
            ui.goto('/login')
            ui.fill('username', a['user'])
            ui.fill('password', a['password'])
            ui.click('Sign in', tags=('button',))
            ui.require('Bad username or password')
        elif op == 'sign-out-menu':
            ui.goto('/dashboard')
            avatar = next(x for x in ui.snapshot()['controls'] if x['tag'] == 'a' and x['bounds'][0] > 1200
                          and x['bounds'][1] < 30 and (x.get('text') or '').strip())
            ui.click_ref(avatar)
            ui.click('Logout', tags=('a',))
            ui.wait(lambda s: s['url'].startswith('/login'), 'sign-out did not complete')
        elif op == 'click':
            ui.click(*a['names'], tags=tuple(a['tags']) if a.get('tags') else None, last=a.get('last', False))
            ui.call('wait', seconds=a.get('wait', 0.8))
        elif op == 'link':
            ui.click_ref(ui.link(a['href']))
            ui.call('wait', seconds=a.get('wait', 0.8))
        elif op == 'fill':
            ui.fill(a['field'], a['value'])
        elif op == 'select':
            ui.select(a['field'], a['value'])
        elif op == 'check':
            ui.check(a['field'], a.get('value', True))
        elif op == 'save':
            ui.save(*(a.get('names') or ()))
        elif op == 'wait-text':
            ui.require(*a['texts'])
        elif op == 'wait':
            ui.call('wait', seconds=a.get('seconds', 1))
        elif op == 'drag':
            drag_card(ui, a['task'], a['column'])
        elif op == 'upload':
            upload(ui, ctx, a['file'])
        elif op == 'corroborate':
            corroborate(c, a['method'], a.get('params'), lambda result, a=a: eval_expect(result, a['expect']))
        elif op == 'new-task':
            adders = [x for x in ui.snapshot()['controls'] if x['tag'] == 'a' and x.get('title') == 'Add a new task']
            ui.click_ref(sorted(adders, key=lambda x: (x['bounds'][1], x['bounds'][0]))[a['column']])
            ui.field('title')
        elif op == 'select-label':
            control = ui.wait(lambda s: next((x for x in reversed(s['controls']) if x['tag'] == 'select'
                                              and exact(a['label']).search(x.get('label') or x.get('aria') or '')),
                                             None), 'select missing: ' + a['label'])
            ui.call('select', target={'ref': control['ref']}, value=a['value'])
        elif op == 'select-nth':
            matches = [x for x in ui.snapshot()['controls'] if x['tag'] == 'select' and x.get('name') == a['field']]
            ui.call('select', target={'ref': matches[a.get('nth', 0)]['ref']}, value=a['value'])
        elif op == 'autocomplete':
            if a.get('placeholder'):
                control = next(x for x in ui.snapshot()['controls'] if x.get('placeholder') == a['placeholder'])
            else:
                control = ui.field(a['field'])
            ui.call('fill', target={'ref': control['ref']}, value=a['value'])
            ui.call('wait', seconds=1.5)
            ui.call('press', key='ArrowDown')
            ui.call('press', key='Enter')
            ui.call('wait', seconds=0.5)
        elif op == 'tag':
            box = next(x for x in reversed(ui.snapshot()['controls']) if x.get('role') == 'searchbox')
            ui.call('click', target={'ref': box['ref']})
            ui.call('type', value=a['value'])
            ui.call('wait', seconds=0.8)
            ui.call('press', key='Enter')
            ui.call('wait', seconds=0.5)
        elif op == 'public-board':
            ui.goto(ui.link(r'^/public/board/')['href'])
        elif op == 'filter':
            # The filter box may hold a query already: select it all and type the new one over it.
            control = ui.field('search')
            ui.call('click', target={'ref': control['ref']})
            ui.call('press', key='ControlOrMeta+A')
            ui.call('press', key='Backspace')
            ui.call('type', value=a['value'])
            ui.call('press', key='Enter')
            ui.call('wait', seconds=1)
            ui.wait(lambda s: any(x.get('name') == 'search' and x.get('value') == a['value'] for x in s['controls']),
                    'the filter box does not hold the query ' + a['value'])
        elif op == 'wait-absent':
            ui.absent(*a['texts'])
        elif op == 'menu':
            menus = dropdowns(ui)
            ui.click_ref(menus[a['index']])
            ui.call('wait', seconds=0.5)
            ui.click(a['item'], tags=('a',), last=True)
            ui.call('wait', seconds=1)
        elif op == 'subtask-status':
            for _ in range(a['clicks']):
                ui.click(a['title'], tags=('a',))
                ui.call('wait', seconds=1.2)
        elif op == 'comment':
            ui.click('Add a comment', tags=('a',))
            ui.call('wait', seconds=1)
            ui.fill('comment', a['value'])
            ui.save()
        elif op == 'comment-edit':
            ui.click_ref(dropdowns(ui)[-1])
            ui.click('Edit', tags=('a',), last=True)
            ui.call('wait', seconds=1)
            ui.fill('comment', a['value'])
            ui.save()
        elif op == 'comment-remove':
            ui.click_ref(dropdowns(ui)[-1])
            ui.click('Remove', tags=('a',), last=True)
            ui.call('wait', seconds=1)
            ui.click('Yes', tags=('button',))
            ui.call('wait', seconds=1)
        elif op == 'attach':
            ui.call('wait', seconds=1)
            chooser = next((x for x in reversed(ui.snapshot()['controls'])
                            if any(exact(n).search(t) for n in ('choose files', 'Browse') for t in accessible(x))), None)
            if chooser:
                ui.click_ref(chooser)
            upload(ui, ctx, a['file'])
            ui.call('wait', seconds=1)
            ui.click('Upload files', tags=('button',))
            ui.call('wait', seconds=2)
        elif op == 'attach-input':
            upload(ui, ctx, a['file'])
        elif op == 'attachment-remove':
            ui.click(a['name'], tags=('a',))
            ui.call('wait', seconds=0.5)
            ui.click_ref(ui.link(r'/file/\d+/confirm'))
            ui.call('wait', seconds=1)
            ui.click('Yes', tags=('button',))
            ui.call('wait', seconds=1)
        elif op == 'column-edit' or op == 'column-remove':
            columns = c.call('getColumns', [c.state['p']], 'app')
            index = [x['title'] for x in columns].index(a['column'])
            ui.goto('/project/%s/columns' % c.state['p'])
            ui.click_ref(dropdowns(ui)[index])
            ui.click('Edit' if op == 'column-edit' else 'Remove', tags=('a',), last=True)
            ui.call('wait', seconds=1)
            if op == 'column-remove':
                ui.click('Yes', tags=('button',))
                ui.call('wait', seconds=1)
        elif op in ('swimlane-disable', 'swimlane-menu'):
            lanes = c.call('getActiveSwimlanes', [c.state['p']], 'app')
            index = [x['name'] for x in lanes].index(a['name'])
            ui.goto('/project/%s/swimlanes' % c.state['p'])
            ui.click_ref(dropdowns(ui)[index])
            ui.click('Disable' if op == 'swimlane-disable' else a['item'], tags=('a',), last=True)
            ui.call('wait', seconds=1)
        elif op == 'role-change':
            control = next(x for x in ui.snapshot()['controls'] if x['tag'] == 'select' and x.get('aria') == 'Role'
                           and not x.get('name') and x['bounds'][1] > 200)
            ui.call('select', target={'ref': control['ref']}, value=a['value'])
            ui.call('wait', seconds=1.5)
        elif op == 'press':
            ui.call('press', key=a['key'])
            ui.call('wait', seconds=0.3)
        elif op == 'user-disable':
            ui.click('#%s' % a['id'], tags=('a',))
            ui.click('Disable', tags=('a',), last=True)
            ui.call('wait', seconds=1)
            ui.click('Yes', tags=('button',))
            ui.call('wait', seconds=1)
        elif op == 'group-member':
            ui.goto('/groups')
            groups = c.call('getAllGroups', None, 'app')
            group = next(x for x in groups if x['name'] == a['group'])
            ui.click('#%s' % group['id'], tags=('a',))
            ui.click('Add group member', tags=('a',), last=True)
            ui.call('wait', seconds=1)
            chooser = [x for x in ui.snapshot()['controls'] if x['tag'] == 'input' and x.get('type') == 'text'
                       and x.get('placeholder') not in ('Display another project', 'Search')][-1]
            ui.call('click', target={'ref': chooser['ref']})
            ui.call('type', value=a['user'])
            ui.call('press', key='Enter')
            ui.save()
        elif op == 'check-value':
            control = next(x for x in ui.snapshot()['controls'] if x.get('name') == a['field']
                           and str(x.get('value')) == str(a['value']))
            ui.call('check', target={'ref': control['ref']}, checked=True)
        elif op == 'user-action':
            ui.click('#%s' % a['id'], tags=('a',))
            ui.click(a['item'], tags=('a',), last=True)
            ui.call('wait', seconds=1)
            ui.click('Yes', tags=('button',))
            ui.call('wait', seconds=1)
        elif op == 'check-label':
            control = ui.wait(lambda s: next((x for x in s['controls'] if x.get('type') in ('checkbox', 'radio')
                                              and exact(a['label']).search(x.get('label') or '')), None),
                              'choice missing: ' + a['label'])
            ui.call('check', target={'ref': control['ref']}, checked=True)
        elif op == 'column-menu':
            ui.click(a['column'], tags=('a',))
            ui.call('wait', seconds=0.5)
            ui.click(a['item'], tags=('a',), last=True)
            ui.call('wait', seconds=1)
        elif op == 'template':
            ui.click('Predefined task description', 'Template for the task description', tags=('a',), last=True)
            ui.call('wait', seconds=0.5)
            ui.click(a['name'], tags=('a',), last=True)
            ui.call('wait', seconds=0.5)
        elif op == 'custom-filter':
            ui.click('Custom filters', tags=('a',))
            ui.call('wait', seconds=0.5)
            ui.click(a['name'], tags=('a',), last=True)
            ui.call('wait', seconds=1)
        else:
            raise ValueError('unknown recipe operation ' + op)


def dropdowns(ui):
    """The icon-only dropdown triggers of the page body, in document order."""
    return [x for x in ui.snapshot()['controls'] if x['tag'] == 'a' and not (x.get('text') or '').strip()
            and not x.get('title') and not x.get('aria') and 26 <= x['bounds'][2] <= 32 and x['bounds'][1] > 80]


def eval_expect(result, expect):
    """A small predicate language for corroborate: {'path': value} pairs, or {'where': {...}} on a list."""
    if 'started' in expect:
        return bool((result or {}).get('date_started'))
    if 'equals' in expect:
        return result == expect['equals']
    if 'null' in expect:
        return result is None
    if 'where' in expect:
        return any(all(x.get(k) == v for k, v in expect['where'].items()) for x in result or [])
    if 'absent' in expect:
        return not any(all(x.get(k) == v for k, v in expect['absent'].items()) for x in result or [])
    return all((result or {}).get(k) == v for k, v in expect.items())


__all__ = ['execute', 'accessible']
