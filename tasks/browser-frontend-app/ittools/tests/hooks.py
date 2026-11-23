'''ittools specifics for the shared driver: setup, per-checkpoint preparation, reference recipes, program checks.

Everything reaches the candidate through the black-box runtime: pages are opened with its open operation, inputs are
filled and buttons pressed with its GUI operations, the page clock is moved with its clock operation, and reads use
its snapshot, clipboard and download operations. Program checkpoints put their stimulus in `steps`, which run as
preparation; GUI checkpoints use `steps` only to reach the state the goal starts from.
'''
import base64
from pathlib import Path

from evaluation.driver import Hooks as Base
import checks
import field_identity
from reference import recipes

INPUTS = Path(__file__).resolve().parent / 'fixtures'


def open_page(ctx, path, fresh=True):
    '''Open a page in a fresh browser profile (nothing stored by an earlier checkpoint: inputs, favourites, theme,
    language, collapsed menu categories).'''
    if fresh:
        status = ctx.broker.call({'op': 'reset'})
        if not status.get('ready'):
            raise RuntimeError('the application did not come back after a reset: ' + str(status.get('detail')))
    return ctx.broker.call({'op': 'open', 'path': path})


def anchor(snap, step):
    '''The control a pseudo step is anchored to: a named field, or a link of the content area by its leading text.'''
    if 'field' in step:
        return checks.pick(checks.fields(snap), step['field'], step.get('field_nth', 0))
    if 'link' in step:
        links = [c for c in snap['controls'] if c.get('tag') == 'a' and checks.in_area(c, 'content')
                 and (c.get('text') or '').startswith(step['link'])]
        index = step.get('link_nth', 0)
        if len(links) <= index:
            raise AssertionError('no link starting with %r' % step['link'])
        return links[index]
    raise ValueError('a pseudo step needs field or link')


def run_steps(ctx, steps):
    for step in steps:
        op = step['op']
        if op == 'click-after':
            # The button that follows a named field (a copy button) or a card link (a favourite button).
            snap = ctx.broker.call({'op': 'snapshot'})
            button = checks.control_after(snap, anchor(snap, step), step.get('tag', 'button'), step.get('nth', 0))
            ctx.broker.call({'op': 'click', 'target': {'ref': button['ref']}})
        elif op == 'choose':
            # A custom select: open the control that shows the current choice, optionally search, pick the option.
            snap = ctx.broker.call({'op': 'snapshot'})
            area = step.get('area', 'content')
            shown = [c for c in snap['controls'] if checks.in_area(c, area) and (c.get('text') or '') == step['current']]
            if len(shown) <= step.get('current_nth', 0):
                raise AssertionError('no select showing %r' % step['current'])
            before = {c['ref'] for c in snap['controls']}
            snap = ctx.broker.call({'op': 'click', 'target': {'ref': shown[step.get('current_nth', 0)]['ref']}})
            if 'search' in step:
                snap = ctx.broker.call({'op': 'type', 'value': step['search']})
            options = [c for c in snap['controls'] if c['ref'] not in before and (c.get('text') or '') == step['option']]
            if len(options) <= step.get('nth', 0):
                options = [c for c in snap['controls'] if (c.get('text') or '') == step['option']]
            if len(options) <= step.get('nth', 0):
                raise AssertionError('the list offers no option %r' % step['option'])
            ctx.broker.call({'op': 'click', 'target': {'ref': options[step.get('nth', 0)]['ref']}})
        elif op == 'monaco-set':
            # A monaco editor takes its text through a hidden one-pixel textarea: fill gives it the focus, then select all and type.
            snap = ctx.broker.call({'op': 'snapshot'})
            areas = sorted([c for c in snap['controls'] if c.get('tag') == 'textarea' and c['bounds'][2] <= 2], key=lambda c: c['bounds'][0])
            if len(areas) <= step['side']:
                raise AssertionError('the page has no editor number %d' % step['side'])
            ctx.broker.call({'op': 'fill', 'target': {'ref': areas[step['side']]['ref']}, 'value': 'x'})
            ctx.broker.call({'op': 'press', 'key': 'Control+a'})
            if step['text']:
                # Line by line: Escape closes a word suggestion first, so Enter starts a new line instead of accepting it.
                for n, row in enumerate(step['text'].split('\n')):
                    if n:
                        ctx.broker.call({'op': 'press', 'key': 'Escape'})
                        ctx.broker.call({'op': 'press', 'key': 'Enter'})
                    if row:
                        ctx.broker.call({'op': 'type', 'value': row})
            else:
                ctx.broker.call({'op': 'press', 'key': 'Delete'})
        elif op == 'edit-select-all':
            # A rich text editor: click it and select all of its text.
            snap = ctx.broker.call({'op': 'snapshot'})
            editors = [c for c in snap['controls'] if (c.get('text') or '').startswith(step['starts']) and checks.in_area(c, 'content')]
            if not editors:
                raise AssertionError('no editor whose text starts with %r' % step['starts'])
            ctx.broker.call({'op': 'click', 'target': {'ref': editors[0]['ref']}})
            ctx.broker.call({'op': 'press', 'key': 'Control+a'})
        elif op == 'toolbar':
            # A row of unnamed buttons of the given size (an editor toolbar): the button at the given place.
            snap = ctx.broker.call({'op': 'snapshot'})
            rows = {}
            for c in snap['controls']:
                if c.get('tag') == 'button' and not (c.get('text') or '') and checks.in_area(c, 'content') and c['bounds'][1] > 150:
                    rows.setdefault(c['bounds'][1], []).append(c)
            bars = [sorted(r, key=lambda c: c['bounds'][0]) for r in rows.values() if len(r) == step.get('size', 16)]
            if not bars:
                raise AssertionError('the page has no toolbar of %d buttons' % step.get('size', 16))
            ctx.broker.call({'op': 'click', 'target': {'ref': bars[0][step['index']]['ref']}})
        elif op == 'click-last':
            # The unnamed button lowest on the page (the copy button of the result block).
            snap = ctx.broker.call({'op': 'snapshot'})
            blanks = [c for c in snap['controls'] if c.get('tag') == 'button' and not (c.get('text') or '') and checks.in_area(c, 'content')]
            if not blanks:
                raise AssertionError('the page has no unnamed button')
            blanks.sort(key=lambda c: (c['bounds'][1], c['bounds'][0]))
            ctx.broker.call({'op': 'click', 'target': {'ref': blanks[-1]['ref']}})
        elif op == 'wait':
            # The runtime wait takes at most 3 seconds: a longer pause is made of several waits.
            left = float(step.get('seconds', 1))
            while left > 0:
                ctx.broker.call({'op': 'wait', 'seconds': min(3.0, left)})
                left -= 3.0
        elif op == 'carry':
            # Type a value the page shows (a result field, block or the clipboard) into another field.
            ctx.state['page'].reset()
            value = checks.source_text(ctx, step['source'])
            ctx.state['page'].reset()
            ctx.broker.call({'op': 'fill', 'target': step['target'], 'value': value})
        elif op == 'remember':
            # Keep a value the page shows, to compare it with the value after the next steps.
            ctx.state['page'].reset()
            ctx.state['memo'][step['as']] = checks.source_text(ctx, step['source'])
            ctx.state['page'].reset()
        elif op == 'upload-file':
            data = (ctx.inputs / step['file']).read_bytes()
            ctx.broker.call({'op': 'upload', 'filename': step['file'],
                             'mime_type': step.get('mime', 'application/octet-stream'),
                             'base64': base64.b64encode(data).decode()})
        else:
            ctx.broker.call(dict(step))


class Hooks(Base):
    def start(self, ctx):
        ctx.state['page'] = checks.Page(ctx.broker)

    def inputs(self, ctx):
        for name in ctx.episode.get('inputs', {}).get('files', []):
            (ctx.inputs / name).write_bytes((INPUTS / name).read_bytes())

    def setup(self, ctx, item):
        if item['id'] == 'site':
            status = ctx.status()
            if not status.get('ready'):
                raise RuntimeError('the application is not ready: ' + str(status.get('detail')))
        else:
            raise ValueError('unknown setup item ' + item['id'])

    def prepare(self, ctx, checkpoint):
        ctx.state['page'].reset()
        ctx.state['files'] = {}
        ctx.state['memo'] = {}
        if checkpoint.get('reopen', True):
            open_page(ctx, checkpoint.get('page', '/'))
        run_steps(ctx, checkpoint.get('steps', []))
        ctx.state['page'].reset()

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx, checkpoint)

    def collect(self, ctx, checkpoint):
        ctx.state['page'].reset()

    def check(self, ctx, checkpoint, assertion):
        ctx.state['page'].reset()
        observation = checks.observe(ctx, checkpoint, assertion['check'])
        assert isinstance(observation, dict) and observation, 'the check produced no observation'
        return observation

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        spec = assertion['check']
        page = checkpoint.get('page', '/')
        checks.compare(field_identity.normalize(actual, page, spec), field_identity.normalize(expected, page, spec),
                       spec.get('tol', 0.0))
