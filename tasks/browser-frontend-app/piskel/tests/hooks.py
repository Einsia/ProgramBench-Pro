"""Piskel specifics for the episode driver: setup, per-checkpoint preparation, reference recipes, program checks.

Everything reaches the candidate through the black-box runtime: the editor page is opened with the runtime's
open operation, sprites are prepared with its api operation (loadPiskel), scripted stimuli are its keyboard,
pointer (in sprite pixel coordinates), click, fill and drop operations, and reads use the api operation
(getPiskel), the snapshot, or product downloads.
"""
from pathlib import Path
import base64
import time

from evaluation.driver import Hooks as Base
import checks
import ui
from reference import recipes

INPUTS = Path(__file__).resolve().parent / 'fixtures'
PRIMARY = {'title': 'Primary - left mouse button', 'exact': False}
SECONDARY = {'title': 'Secondary - right mouse button', 'exact': False}
NEUTRAL = (150, 600)   # a point of the page left of the drawing area that no control covers


def open_editor(ctx, fresh=True):
    """A fresh browser profile (nothing stored by an earlier checkpoint), then the entry page."""
    if fresh:
        status = ctx.broker.call({'op': 'reset'})
        if not status.get('ready'):
            raise RuntimeError('the application did not come back after a reset: ' + str(status.get('detail')))
    return ctx.broker.call({'op': 'open'})


def load(ctx, text):
    answer = ctx.broker.call({'op': 'api', 'method': 'loadPiskel', 'piskel': text})
    if not answer.get('loaded'):
        raise RuntimeError('the fixture sprite did not load: ' + str(answer.get('error'))[:200])


def set_color(ctx, which, value):
    """Open the primary or secondary colour chooser, type the hex value, confirm it with Enter and close the
    chooser by clicking beside it."""
    snap = ctx.broker.call({'op': 'click', 'target': dict(PRIMARY if which == 'primary' else SECONDARY)})
    fields = [c for c in snap.get('controls', []) if c.get('editable')
              and str(c.get('value') or '').startswith(('#', 'rgb'))]
    if len(fields) != 1:
        raise RuntimeError('the colour chooser did not open a colour field')
    ctx.broker.call({'op': 'fill', 'target': {'ref': fields[0]['ref']}, 'value': value})
    ctx.broker.call({'op': 'press', 'key': 'Enter'})
    ctx.broker.call({'op': 'pointer', 'action': 'click', 'x': NEUTRAL[0], 'y': NEUTRAL[1]})


def run_steps(ctx, steps):
    for step in steps:
        op = step['op']
        if op == 'open-editor':
            open_editor(ctx)
        elif op == 'color':
            set_color(ctx, step.get('which', 'primary'), step['value'])
        elif op == 'load':
            load(ctx, step['piskel'])
        elif op == 'ui':
            ui.act(ctx, step)
        elif op == 'wait-text-gone':
            end = time.monotonic() + 10
            while True:
                snapshot = ctx.broker.call({'op': 'snapshot'})
                if step['text'].lower() not in snapshot.get('text', '').lower():
                    break
                if time.monotonic() >= end:
                    raise AssertionError('The page is still showing: ' + step['text'])
                ctx.broker.call({'op': 'wait', 'seconds': .2})
        elif op == 'wait-control':
            ui.resolve(ctx, step['match'])
        elif op == 'wait-download':
            ui.wait_download(ctx, step['suffix'])
        elif op == 'roundtrip':
            text = ctx.broker.call({'op': 'api', 'method': 'getPiskel'}).get('piskel')
            assert isinstance(text, str), 'getPiskel returned no document'
            load(ctx, text)
        elif op == 'load-result':
            ctx.state['load_result'] = ctx.broker.call({'op': 'api', 'method': 'loadPiskel',
                                                      'piskel': step['piskel']})
        elif op == 'reload-download':
            _, data = checks.take_download(ctx, ('.piskel',))
            load(ctx, data.decode('utf-8'))
        elif op == 'input':
            data = (INPUTS / step['filename']).read_bytes()
            request = {k: v for k, v in step.items() if k not in ('op', 'action')}
            request.update(op=step.get('action', 'upload'), base64=base64.b64encode(data).decode())
            ctx.broker.call(request)
        elif op == 'inputs':
            files = []
            for name in step['filenames']:
                data = (INPUTS / name).read_bytes()
                files.append({'filename':name,'mime_type':'image/png','base64':base64.b64encode(data).decode()})
            request = {k:v for k,v in step.items() if k not in ('op','filenames','action')}
            request.update(op=step.get('action','upload'),files=files)
            ctx.broker.call(request)
        else:
            ctx.broker.call(dict(step))


class Hooks(Base):
    def start(self, ctx):
        ctx.state['reader'] = checks.Reader(ctx.broker)

    def inputs(self, ctx):
        for name in ctx.episode.get('inputs', {}).get('files', []):
            (ctx.inputs / name).write_bytes((INPUTS / name).read_bytes())

    def setup(self, ctx, item):
        if item['id'] == 'editor':
            open_editor(ctx, fresh=False)
        else:
            raise ValueError('unknown setup item ' + item['id'])

    def prepare(self, ctx, checkpoint):
        ctx.state['reader'].reset()
        ctx.state['files'] = {}
        if checkpoint.get('reopen', True):
            open_editor(ctx)
        if checkpoint.get('fixture') is not None:
            load(ctx, checkpoint['fixture'])
        run_steps(ctx, checkpoint.get('steps', []))
        ctx.state['reader'].reset()

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx, checkpoint)

    def collect(self, ctx, checkpoint):
        ctx.state['reader'].reset()

    def check(self, ctx, checkpoint, assertion):
        observation = checks.observe(ctx, checkpoint, assertion['check'])
        assert isinstance(observation, dict) and observation, 'the check produced no observation'
        return observation

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        spec = assertion['check']
        if 'freehand_radius' in spec:
            checks.compare_stroke(actual, expected, spec['freehand_radius'], spec.get('mirror_axis'))
        else:
            checks.compare(actual, expected, spec.get('tol', 0.001))
