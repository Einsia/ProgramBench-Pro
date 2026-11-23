'''Pinned-standard GUI implementation of the reviewed goals, through the black-box runtime (record only).

Recipes drive the standard answer with the same runtime GUI operations that the evaluator and the model use; the
driver captures reference evidence with the evaluator's observation. Controls are found in the runtime's own snapshot
by text, label, placeholder or aria label and operated by ref. These names belong to the pinned standard only; they
are never a candidate requirement.
'''
import base64
import time

import checks

WAIT = 6.0
FIELDS = ('title', 'text', 'label', 'aria', 'placeholder', 'context')
META = ('do', 'value', 'enter', 'key', 'checked', 'button', 'count', 'modifiers', 'nth', 'prefix', 'contains', 'tag',
        'role', 'area', 'readonly', 'exact', 'type', 'current', 'option', 'path', 'seconds', 'file', 'mime', 'field',
        'field_nth', 'link', 'link_nth')


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
            ok = checks.in_area(control, spec.get('area', 'content'))
            for field in FIELDS:
                if field in spec:
                    have = control.get(field) or ''
                    want = spec[field]
                    if spec.get('prefix'):
                        ok = ok and have.startswith(want)
                    elif spec.get('contains'):
                        ok = ok and want.lower() in have.lower()
                    else:
                        ok = ok and have == want
            if 'tag' in spec:
                tags = spec['tag'] if isinstance(spec['tag'], list) else [spec['tag']]
                ok = ok and control.get('tag') in tags
            if 'role' in spec:
                ok = ok and control.get('role') == spec['role']
            if 'readonly' in spec:
                ok = ok and bool(control.get('readonly')) == spec['readonly']
            if ok:
                matches.append(control)
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
            hay = snap['text'] + chr(10) + chr(10).join(b['text'] for b in snap.get('blocks', [])) + chr(10) \
                + chr(10).join((c.get('text') or '') + ' ' + (c.get('value') or '') for c in snap['controls'])
            if text in hay:
                return
            if time.monotonic() > deadline:
                raise AssertionError('text not shown: ' + text)
            time.sleep(0.2)

    def spec(self, step):
        return {k: v for k, v in step.items() if k in FIELDS or k in META}

    def target(self, step):
        return {'ref': self.wait_for(self.spec(step))['ref']}


def execute(ctx, checkpoint):
    ui = UI(ctx)
    ui.snapshot()
    for step in checkpoint['recipe']:
        do = step['do']
        if do == 'open':
            ui.call({'op': 'open', 'path': step['path']})
        elif do == 'click':
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
            if step.get('enter', False):
                ui.call({'op': 'press', 'key': 'Enter'})
        elif do == 'type':
            ui.call({'op': 'type', 'value': step['value']})
        elif do == 'press':
            ui.call({'op': 'press', 'key': step['key']})
        elif do == 'choose':
            # A custom select: click the control that shows the current choice, then the option.
            ui.call({'op': 'click', 'target': {'ref': ui.wait_for({'text': step['current'], 'area': step.get('area', 'content')})['ref']}})
            option = {'text': step['option'], 'area': step.get('area', 'content'), 'nth': step.get('nth', 0)}
            ui.call({'op': 'click', 'target': {'ref': ui.wait_for(option)['ref']}})
        elif do == 'click-after':
            snap = ui.snapshot()
            anchor = checks.pick(checks.fields(snap), step['field'], step.get('field_nth', 0)) if 'field' in step else None
            if anchor is None:
                links = [c for c in snap['controls'] if c.get('tag') == 'a' and checks.in_area(c, 'content')
                         and (c.get('text') or '').startswith(step['link'])]
                if len(links) <= step.get('link_nth', 0):
                    raise AssertionError('no link starting with ' + step['link'])
                anchor = links[step.get('link_nth', 0)]
            button = checks.control_after(snap, anchor, step.get('tag', 'button'), step.get('nth', 0))
            ui.call({'op': 'click', 'target': {'ref': button['ref']}})
        elif do == 'upload':
            data = (ctx.inputs / step['file']).read_bytes()
            ui.call({'op': 'upload', 'filename': step['file'], 'mime_type': step.get('mime', 'application/octet-stream'),
                     'base64': base64.b64encode(data).decode()})
        elif do == 'wait':
            ui.call({'op': 'wait', 'seconds': step.get('seconds', 1)})
        elif do == 'clock':
            ui.call({'op': 'clock', 'seconds': step['seconds']})
        elif do == 'reload':
            ui.call({'op': 'reload'})
        elif do == 'expect':
            ui.require_text(step['text'])
        elif do == 'expect-control':
            ui.wait_for(ui.spec(step))
        elif do == 'download':
            deadline = time.monotonic() + WAIT
            while not ui.snapshot().get('downloads'):
                if time.monotonic() > deadline:
                    raise AssertionError('no download was produced')
                time.sleep(0.3)
        else:
            raise ValueError('unknown recipe step ' + do)
    # Evidence after a settled page.
    ui.call({'op': 'wait', 'seconds': 0.3})
