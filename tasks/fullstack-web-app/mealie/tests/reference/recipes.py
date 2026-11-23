'''Deterministic GUI recipes for the pinned reference, using only the public runtime.

The selectors and page routes below implement the independently authored goals. They are never candidate UI requirements.
'''
import time

import checks
from checks import resolve
from .ui import UI


def execute(ctx, c, checkpoint):
    actor = ctx.episode.get('actor')
    ui = ctx.state.setdefault('ui', UI(ctx.broker))
    if actor and not ctx.state.get('signed_in'):
        ui.sign_in(actor, c.creds[actor])
        ctx.state['signed_in'] = True
    for raw in checkpoint['recipe']:
        a = resolve(raw, c.state)
        op = a.pop('op')
        if op == 'signin':
            ui.sign_in(a['user'],a['password'])
        elif op == 'share-delete':
            row=ui.wait(lambda s: next((x for x in s['controls'] if x.get('text','').startswith('Expires At')),None),'share row missing')
            x,y,w,h=row['bounds']
            buttons=[v for v in ui.snap['controls'] if v['tag']=='button' and not v.get('text') and not v.get('aria')
                     and y <= v['bounds'][1] <= y+h and x <= v['bounds'][0] <= x+w]
            assert buttons, 'share link delete action unavailable'
            ui.call('click',target={'ref':buttons[0]['ref']})
        elif op == 'goto':
            ui.goto(a['path'])
        elif op == 'reload':
            ui.reload()
        elif op == 'fill':
            ui.fill(a.pop('value'), **a)
        elif op == 'click':
            ui.click(**a)
        elif op == 'button':
            ui.click_button(a.pop('name'), **a)
        elif op == 'press':
            ui.press(a.pop('key'), **a)
        elif op == 'tick':
            ui.tick(a.pop('value'), **a)
        elif op == 'choice':
            value = a.pop('value')
            ui.click(**a)
            ui.click(role='option', text=value)
        elif op == 'autocomplete':
            escape = a.pop('escape',True)
            value = a.pop('value')
            ui.fill(value, **a)
            ui.click(role='option', text=value)
            if escape:
                ui.press('Escape')
        elif op == 'recipe-menu':
            ui.goto('/g/home/r/' + a['slug'])
            ui.click(tag='button', expanded=False, region=[1000, 170, 1280, 450])
            ui.click(role='listitem', text=a['name'])
        elif op == 'list-delete':
            ui.goto('/shopping-lists?disableRedirect=true')
            row = ui.control(tag='a', text=a['name'])
            x,y,w,h = row['bounds']
            buttons = [c for c in ui.snap['controls'] if c['tag']=='button' and not c.get('text')
                       and x <= c['bounds'][0] < x+w and y <= c['bounds'][1] < y+h]
            assert len(buttons)==2, 'shopping list row actions missing'
            ui.call('click', target={'ref':buttons[-1]['ref']})
        elif op == 'table-action':
            # Search isolates the desired visible row. The table exposes the two icon actions in that row.
            ui.fill(a['name'], label='Search', tag='input')
            ui.wait(lambda s: a['name'] in s['text'], 'table row missing')
            time.sleep(0.8)
            buttons = [x for x in ui.snapshot()['controls'] if x.get('tag') == 'button'
                       and not x.get('text') and not x.get('aria') and not x.get('disabled')
                       and x['bounds'][0] > 1000 and 610 <= x['bounds'][1] <= 730]
            assert len(buttons) >= 2, 'row actions missing: ' + str(buttons)
            ui.call('click', target={'ref': buttons[0 if a['action'] == 'edit' else -1]['ref']})
        elif op == 'top':
            ui.call('scroll', delta_y=-5000)
        elif op == 'scroll':
            ui.call('scroll', **a)
        elif op == 'upload':
            ui.call('upload', **a)
        elif op == 'wait':
            ui.call('wait', seconds=a.get('seconds', 1))
        elif op == 'require':
            ui.require(*a['texts'])
        else:
            raise ValueError('unknown reference operation ' + op)
    # Confirm only the requested public outcomes before freezing after-evidence.
    for check in checkpoint.get('checks', []):
        if 'download' in check:
            continue
        end = time.monotonic() + 12
        while True:
            try:
                checks.observe(c, check)
                break
            except AssertionError:
                if time.monotonic() >= end:
                    raise
                time.sleep(0.3)
    for text in checkpoint.get('visible', []):
        ui.require(resolve(text, c.state))
