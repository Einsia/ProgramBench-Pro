"""SVG-edit specifics for the shared driver: setup, per-checkpoint preparation, reference recipes, program checks.

Everything reaches the candidate through the black-box runtime: the editor page is
opened with the runtime's open operation, documents are prepared with its api
operation (window.svgEditor.loadFromString), scripted stimuli are its keyboard and
pointer operations (keys, and pointer input in document coordinates), and reads
use the api operation (getSvgString) or product downloads.
"""
import math
from pathlib import Path
import time

from evaluation.driver import Hooks as Base
import checks
import fixtures
from reference import recipes

INPUTS = Path(__file__).resolve().parent / 'fixtures'
# The first-visit storage question: its confirm control is any control named OK (any element or role, any letter
# case) with a control named Cancel beside it; the question counts as answered once that OK control is gone.
CONSENT_PAIR = 200   # pixels between the centres of the question's OK and Cancel controls
CONSENT_WAIT = 6.0   # seconds the question may take to close after it is answered


def open_editor(ctx, fresh=True):
    """Open the entry page in a fresh browser profile (nothing stored by an earlier checkpoint: drawing,
    preferences, storage choice) and answer the first-visit storage question with its OK control when it is shown."""
    if fresh:
        status = ctx.broker.call({'op': 'reset'})
        if not status.get('ready'):
            raise RuntimeError('the application did not come back after a reset: ' + str(status.get('detail')))
    snap = ctx.broker.call({'op': 'open'})
    answers = consent_controls(snap)
    if not answers:
        return snap
    for ok in answers:
        if answered(ctx, ctx.broker.call({'op': 'click', 'target': {'ref': ok['ref']}}), ok):
            return snap
    # No OK closed it: one Enter on the focused control, then fail loudly instead of running against a blocked page.
    if answered(ctx, ctx.broker.call({'op': 'press', 'key': 'Enter'}), answers[0]):
        return snap
    raise RuntimeError(f'the first-visit storage question stayed open {CONSENT_WAIT:.0f} s after it was answered '
                       'with OK')


def consent_controls(snap):
    """The OK controls of the storage question shown in a snapshot, nearest to the middle of the page first: controls
    named OK that have a control named Cancel beside them (an OK elsewhere on the page is not the question's)."""
    controls = [c for c in snap.get('controls', []) if c.get('bounds')]
    cancels = [centre(c) for c in controls if named(c, 'cancel')]
    width, height = snap.get('viewport') or (1280, 900)
    oks = [c for c in controls if named(c, 'ok') and any(math.dist(centre(c), p) <= CONSENT_PAIR for p in cancels)]
    return sorted(oks, key=lambda c: math.dist(centre(c), (width / 2, height / 2)))


def answered(ctx, snap, ok):
    """Whether the OK control that was used is gone, watching the page for up to CONSENT_WAIT seconds."""
    deadline = time.monotonic() + CONSENT_WAIT
    while any(named(c, 'ok') and c.get('bounds') and math.dist(centre(c), centre(ok)) <= 3
              for c in snap.get('controls', [])):
        if time.monotonic() >= deadline:
            return False
        snap = ctx.broker.call({'op': 'wait', 'seconds': 0.5})
    return True


def named(control, word):
    """Whether the control's accessible name (aria label, label, text or tooltip) is the word, in any letter case."""
    return any((control.get(key) or '').strip().lower() == word for key in ('aria', 'label', 'text', 'title'))


def centre(control):
    x, y, w, h = control['bounds']
    return x + w / 2, y + h / 2


def layer_titles(svg):
    try:
        return [layer['title'] for layer in svgmodel_layers(svg)]
    except AssertionError:
        return None


def svgmodel_layers(svg):
    import svgmodel
    doc = svgmodel.Doc(svg)
    return [{'title': next((svgmodel.text_content(c) for c in layer if svgmodel.name(c) == 'title'), None)}
            for layer in doc.layers()]


def run_steps(ctx, steps, fixture=None):
    for step in steps:
        if step['op'] == 'open-editor':
            open_editor(ctx)
        elif step['op'] == 'reload-drawing':
            # Reopen the page so that the editor restores its stored drawing (SVG-edit refreshes its layers list
            # only then); if the drawing did not survive the reload, load it again through the API.
            ctx.broker.call({'op': 'open'})
            current = ctx.broker.call({'op': 'api', 'method': 'getSvgString'}).get('svg', '')
            if fixture is not None and layer_titles(current) != layer_titles(fixture):
                answer = ctx.broker.call({'op': 'api', 'method': 'loadFromString', 'svg': fixture})
                if not answer.get('loaded'):
                    raise RuntimeError('the fixture drawing did not load after the reload')
        else:
            ctx.broker.call(dict(step))


def fresh_without_consent(ctx):
    """A fresh profile whose first-visit storage prompt is left open for the goal."""
    status = ctx.broker.call({'op': 'reset'})
    if not status.get('ready'):
        raise RuntimeError('the application did not come back after a reset: ' + str(status.get('detail')))
    ctx.broker.call({'op': 'open'})


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
        steps = list(checkpoint.get('steps', []))
        if steps and steps[0]['op'] == 'no-consent':
            fresh_without_consent(ctx)
            steps = steps[1:]
            if checkpoint.get('fixture_svg') not in (None, fixtures.EMPTY):
                raise ValueError('a checkpoint without consent starts from the empty drawing')
            run_steps(ctx, steps)
            ctx.state['reader'].reset()
            return
        if checkpoint.get('reopen', True):
            open_editor(ctx)
        if checkpoint.get('fixture_svg') is not None:
            answer = ctx.broker.call({'op': 'api', 'method': 'loadFromString', 'svg': checkpoint['fixture_svg']})
            if not answer.get('loaded'):
                raise RuntimeError('the fixture drawing did not load: ' + str(answer.get('error'))[:200])
        run_steps(ctx, steps, checkpoint.get('fixture_svg'))
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
        checks.compare(actual, expected, assertion['check'].get('tol', 0.05))
