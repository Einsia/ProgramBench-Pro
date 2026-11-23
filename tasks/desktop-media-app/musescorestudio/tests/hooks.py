'''MuseScore Studio specifics for the episode driver: setup items, preparation, recipes, product files and program checks.

Everything reaches the candidate through the black-box runtime: the product command line through its convert
operation, input documents through upload, files the product wrote through list_files and download, the desktop
through windows, observe and the input operations, and restarts through the lifecycle operations.
'''
import os
from pathlib import Path
import tempfile
import time

from evaluation.broker import BrokerError
from evaluation.driver import Hooks as Base
from harness import Context, compare
import backend


def window_titles(ctx):
    return sorted(str(w.get('title', '')) for w in ctx.broker.call({'op': 'windows'}).get('windows', []))


def dismiss_dialogs(ctx, before, attempts=4):
    '''Close the windows a checkpoint left open on purpose (its evidence) before the program checks: Escape while
    windows that were not there when the checkpoint began are still open.'''
    for _ in range(attempts):
        remaining = list(before)
        extra = []
        for title in window_titles(ctx):
            if title in remaining:
                remaining.remove(title)
            else:
                extra.append(title)
        if not extra:
            return
        try:
            ctx.broker.call({'op': 'press', 'key': 'Escape'})
        except BrokerError:
            return
        time.sleep(1.0)


class Hooks(Base):
    def start(self, ctx):
        scratch = Path(tempfile.mkdtemp(prefix='musescorestudio-', dir=os.environ.get('TMPDIR')))
        ctx.state['c'] = Context(ctx.broker, ctx.out, scratch)
        if not ctx.gui:
            ctx.state['cases'] = backend.cases_for(ctx.episode['program']['module'])

    def setup(self, ctx, item):
        c = ctx.state['c']
        c.current_case = 'setup:' + item['id']
        try:
            if not ctx.gui:
                ctx.state['cases'][item['case']].action(c)
            elif item['op'] == 'documents':
                for name in item['files']:
                    c.fixture(name)
            else:
                raise ValueError('unknown setup operation ' + str(item['op']))
        finally:
            c.flush()

    def prepare(self, ctx, checkpoint):
        c = ctx.state['c']
        c.current_case = checkpoint['id']
        if ctx.gui:
            import checks
            checks.setup(c, checkpoint.get('preparation', []))
            return
        case = ctx.state['cases'][checkpoint['case']]
        c.current_case = case.id
        # A step whose earlier step of the same scenario did not complete is blocked, not failed.
        if case.needs is not None:
            case.needs(c)

    def begin(self, ctx, checkpoint):
        if any(step.get('leave_open') for step in checkpoint.get('recipe', [])):
            ctx.state['windows_before'] = window_titles(ctx)

    def recipe(self, ctx, checkpoint):
        from reference import recipes
        recipes.execute(ctx, checkpoint)

    def collect(self, ctx, checkpoint):
        if any(step.get('leave_open') for step in checkpoint.get('recipe', [])):
            dismiss_dialogs(ctx, ctx.state.get('windows_before', []))
        ctx.state['c'].collect()

    def check(self, ctx, checkpoint, assertion):
        c = ctx.state['c']
        if ctx.gui:
            import checks
            c.current_case = assertion['id']
            return checks.observe(c, ctx.episode, checkpoint, assertion['check'])
        case = ctx.state['cases'][checkpoint['case']]
        c.current_case = case.id
        value = case.action(c)
        c.successful.add(case.id)
        return value

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        compare(actual, expected)

    def after(self, ctx, checkpoint):
        ctx.state['c'].flush()

    def close(self, ctx):
        c = ctx.state.get('c')
        if c is not None:
            c.close()
