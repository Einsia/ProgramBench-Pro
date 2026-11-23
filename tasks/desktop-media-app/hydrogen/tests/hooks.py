"""Hydrogen specifics for the kit driver: setup items, preparation, recipes, product files and program checks.

Everything reaches the candidate through the black-box runtime: OSC through its osc operation, the command line
through cli, input documents through upload, files the product wrote through list_files and download, the settings
file through settings, the desktop through observe and its input operations, and restarts through its lifecycle
operations. Rendered audio is decoded by the verifier's own FFmpeg.
"""
import os
from pathlib import Path
import tempfile

from evaluation.broker import BrokerError
from evaluation.driver import Hooks as Base
from harness import Context, compare
import backend
import checks


class Hooks(Base):
    def start(self, ctx):
        scratch = Path(tempfile.mkdtemp(prefix='hydrogen-', dir=os.environ.get('TMPDIR')))
        ctx.state['c'] = Context(ctx.broker, ctx.out, scratch)
        if not ctx.gui:
            ctx.state['cases'] = backend.cases_for(ctx.episode['program']['module'])

    def setup(self, ctx, item):
        c = ctx.state['c']
        c.current_case = 'setup:' + item['id']
        try:
            if not ctx.gui:
                ctx.state['cases'][item['case']].action(c)
            else:
                checks.setup(c, ctx.episode, item)
        finally:
            c.flush()

    def prepare(self, ctx, checkpoint):
        c = ctx.state['c']
        c.current_case = checkpoint['id']
        if ctx.gui:
            checks.prepare(c, ctx.episode, checkpoint)
            return
        case = ctx.state['cases'][checkpoint['case']]
        c.current_case = case.id
        # The shared driver gates explicit manifest dependencies on completed assertion results.

    def begin(self, ctx, checkpoint):
        ctx.state['windows_before'] = ctx.state['c'].window_titles()

    def recipe(self, ctx, checkpoint):
        from reference import recipes
        recipes.execute(ctx, checkpoint)

    def collect(self, ctx, checkpoint):
        checks.collect(ctx.state['c'], ctx.episode, checkpoint, ctx.state.get('windows_before', []))

    def check(self, ctx, checkpoint, assertion):
        c = ctx.state['c']
        if ctx.gui:
            c.current_case = assertion['id']
            return checks.observe(c, ctx.episode, checkpoint, assertion['check'])
        case = ctx.state['cases'][checkpoint['case']]
        c.current_case = case.id
        return case.action(c)

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        compare(actual, expected)

    def after(self, ctx, checkpoint):
        ctx.state['c'].flush()

    def close(self, ctx):
        c = ctx.state.get('c')
        if c is not None:
            c.close()
