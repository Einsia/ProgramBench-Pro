"""Pinned-standard GUI implementation of the reviewed goals, through the black-box runtime (record only).

Recipes drive the standard answer with the same runtime GUI operations that the
evaluator and the model use; the driver captures reference evidence with the
evaluator's observation. Controls are found in the runtime's own snapshot by
tooltip, text, label or panel context and operated by ref. These names belong
to the pinned standard only; they are never a candidate requirement.
"""
import base64
import time

WAIT = 6.0
FIELDS = ('title', 'text', 'label', 'context', 'aria', 'placeholder')
META = ('do', 'value', 'enter', 'key', 'checked', 'button', 'count', 'modifiers', 'nth', 'prefix', 'contains', 'tag',
        'has_option', 'options', 'dx', 'dy', 'x', 'y', 'exact', 'type')


class UI:
    def __init__(self, ctx):
        self.ctx = ctx
        self.broker = ctx.broker
        self.snap = None

    def call(self, request):
        answer = self.broker.call(request)
        if isinstance(answer, dict) and 'controls' in answer:
            self.snap = answer
        return answer

    def snapshot(self):
        return self.call({'op': 'snapshot'})

    def find(self, spec, snap=None):
        snap = snap or self.snap or self.snapshot()
        matches = []
        for control in snap['controls']:
            ok = True
            for field in FIELDS:
                if field in spec:
                    have = control.get(field) or ''
                    want = spec[field]
                    if spec.get('prefix'):
                        ok &= have.startswith(want)
                    elif spec.get('contains'):
                        ok &= want.lower() in have.lower()
                    else:
                        ok &= have == want
            if 'tag' in spec:
                tags = spec['tag'] if isinstance(spec['tag'], list) else [spec['tag']]
                ok &= control.get('tag') in tags
            if 'has_option' in spec:
                ok &= any(spec['has_option'] in (o.get('value'), o.get('label')) for o in control.get('options', []))
            if spec.get('options'):
                ok &= bool(control.get('options'))
            if spec.get('unnamed'):
                ok &= not any(control.get(k) for k in ('title', 'text', 'label', 'context', 'aria', 'placeholder')) \
                    and control.get('type') == 'text'
            if spec.get('enabled'):
                ok &= not control.get('disabled')
            if ok:
                matches.append(control)
        if 'below' in spec:
            matches = [c for c in matches if c['bounds'][1] > spec['below']]
        if 'right_of' in spec:
            matches = [c for c in matches if c['bounds'][0] > spec['right_of']]
        index = spec.get('nth', 0)
        return matches[index] if len(matches) > index else None

    def wait_for(self, spec, timeout=WAIT, what=None):
        deadline = time.monotonic() + timeout
        while True:
            control = self.find(spec, self.snapshot())
            if control:
                return control
            if time.monotonic() > deadline:
                raise AssertionError('control not found: ' + (what or str(spec)))
            time.sleep(0.2)

    def require_text(self, text, timeout=WAIT):
        deadline = time.monotonic() + timeout
        while True:
            snap = self.snapshot()
            hay = snap['text'] + '\n' + '\n'.join(c.get('text', '') for c in snap['controls'])
            if text in hay:
                return
            if time.monotonic() > deadline:
                raise AssertionError('text not shown: ' + text)
            time.sleep(0.2)

    def control(self, step):
        spec = {k: v for k, v in step.items() if k in FIELDS or k in ('tag', 'has_option', 'options', 'prefix',
                                                                        'contains', 'nth', 'unnamed')}
        return self.wait_for(spec)

    def target(self, step):
        spec = {k: v for k, v in step.items() if k in FIELDS or k in ('tag', 'has_option', 'options', 'prefix',
                                                                        'contains', 'nth', 'unnamed')}
        if set(spec) == {'text'} and not self.find(spec, self.snapshot()):
            # Plain page text that is not a listed control: the runtime's text locator finds it on screen.
            return {'text': spec['text']}
        return {'ref': self.control(step)['ref']}


def document(step, *keys):
    return {k: step[k] for k in keys if k in step}


def execute(ctx, checkpoint):
    ui = UI(ctx)
    ui.snapshot()
    for step in checkpoint['recipe']:
        do = step['do']
        if do == 'click':
            request = {'op': 'click', 'target': ui.target(step)}
            if 'button' in step:
                request['button'] = step['button']
            if 'count' in step:
                request['click_count'] = step['count']
            if 'modifiers' in step:
                request['modifiers'] = step['modifiers']
            ui.call(request)
        elif do == 'fill':
            ui.call({'op': 'fill', 'target': ui.target(step), 'value': step['value']})
            if step.get('enter', True):
                ui.call({'op': 'press', 'key': 'Enter'})
        elif do == 'select':
            ui.call({'op': 'select', 'target': ui.target(step), 'value': step['value']})
        elif do == 'check':
            ui.call({'op': 'check', 'target': ui.target(step), 'checked': step.get('checked', True)})
        elif do == 'type':
            ui.call({'op': 'type', 'value': step['value']})
        elif do == 'press':
            ui.call({'op': 'press', 'key': step['key']})
        elif do in ('pointer', 'drag'):
            request = {'op': do, 'target': {'document': True},
                       **document(step, 'x', 'y', 'to_x', 'to_y', 'via', 'steps', 'button', 'modifiers', 'action',
                                  'click_count')}
            if step.get('viewport'):
                request.pop('target')
            ui.call(request)
        elif do == 'menu':
            ui.call({'op': 'click', 'target': ui.target({'text': 'SVG-Edit', 'tag': 'button'})})
            ui.call({'op': 'click', 'target': ui.target({'text': step['item'], 'tag': 'se-menu-item'})})
        elif do == 'dialog':
            request = {'op': 'dialog', 'action': step.get('action', 'accept')}
            if 'value' in step:
                request['text'] = step['value']
            ui.call(request)
        elif do == 'upload':
            data = (ctx.inputs / step['file']).read_bytes()
            ui.call({'op': 'upload', 'filename': step['file'], 'mime_type': step.get('mime', 'image/svg+xml'),
                     'base64': base64.b64encode(data).decode()})
        elif do == 'wait':
            ui.call({'op': 'wait', 'seconds': step.get('seconds', 1)})
        elif do == 'pointer-on':
            # A point inside a control (for example one swatch of a palette strip).
            request = {'op': 'pointer', 'target': ui.target(step), 'x': step['x'], 'y': step['y']}
            if 'modifiers' in step:
                request['modifiers'] = step['modifiers']
            ui.call(request)
        elif do == 'pointer-near':
            # A point beside a listed control (for example an unnamed toggle cell left of a layer name).
            control = ui.control(step)
            x, y, w, h = control['bounds']
            ui.call({'op': 'pointer', 'x': x + step.get('dx', 0), 'y': y + h / 2 + step.get('dy', 0)})
        elif do == 'click-nth':
            matches = [c for c in ui.snapshot()['controls'] if c.get('title') == step['title']]
            if len(matches) <= step['nth']:
                raise AssertionError('no control number %d titled %s' % (step['nth'], step['title']))
            ui.call({'op': 'click', 'target': {'ref': matches[step['nth']]['ref']}})
        elif do == 'maybe-click':
            control = ui.find({'text': step['text']}, ui.snapshot())
            if control:
                ui.call({'op': 'click', 'target': {'ref': control['ref']}})
        elif do == 'expect-dialog':
            if not any(d.get('type') == step['type'] for d in (ui.snap or {}).get('dialogs', [])):
                raise AssertionError('no native %s was answered' % step['type'])
        elif do == 'background':
            # The editor-background colour field of the preferences dialog (a colour picker): open it and set hex.
            ui.call({'op': 'click', 'target': ui.target({'title': 'Change background color/opacity'})})
            ui.call({'op': 'fill', 'target': ui.target({'label': '#:'}), 'value': step['value']})
            ui.call({'op': 'click', 'target': ui.target({'title': 'Commit To This Color Selection'})})
        elif do == 'expect':
            ui.require_text(step['text'])
        elif do == 'expect-control':
            ui.wait_for({k: v for k, v in step.items() if k != 'do'})
        elif do == 'download':
            deadline = time.monotonic() + WAIT
            while not any(d['filename'].endswith(step['suffix']) for d in ui.snapshot().get('downloads', [])):
                if time.monotonic() > deadline:
                    raise AssertionError('no download ' + step['suffix'])
                time.sleep(0.3)
        elif do == 'reload':
            ui.call({'op': 'reload'})
        else:
            raise ValueError('unknown recipe step ' + do)
    # Evidence after a settled page.
    ui.call({'op': 'wait', 'seconds': 0.3})
