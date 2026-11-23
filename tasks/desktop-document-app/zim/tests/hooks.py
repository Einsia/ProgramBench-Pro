'''Zim specifics for the kit driver: setup items, per-checkpoint preparation, reference recipes and program checks.

Everything reaches the candidate through the black-box runtime: notebooks and inputs through upload, pages and exports through
list_files and download, the product command line through cli, the desktop through observe and its input operations, and
restarts through its lifecycle operations. Nothing in this module is shown to the evaluator agent or the candidate.
'''
import os
from pathlib import Path
import tempfile

from evaluation.driver import Hooks as Base
from harness import Context, compare
import backend


class Hooks(Base):
    def start(self, ctx):
        scratch = Path(tempfile.mkdtemp(prefix='zim-', dir=os.environ.get('TMPDIR')))
        ctx.state['c'] = Context(ctx.broker, ctx.out, scratch)
        if not ctx.gui:
            ctx.state['cases'] = backend.cases_for(ctx.episode['program']['module'])

    def setup(self, ctx, item):
        c = ctx.state['c']
        c.current_case = 'setup:' + item['id']
        try:
            if not ctx.gui:
                ctx.state['cases'][item['case']].action(c)
            elif item['op'] == 'notebook':
                import fixtures
                for name, data in fixtures.notebook(item['key']).items():
                    c.upload('notebook', name, data)
                c.restart()
            elif item['op'] == 'inputs':
                import fixtures
                for name, data in fixtures.inputs(*item['files']).items():
                    c.upload('inbox', name, data)
            else:
                raise ValueError('unknown setup operation ' + str(item['op']))
        finally:
            c.flush()

    def prepare(self, ctx, checkpoint):
        c = ctx.state['c']
        c.current_case = checkpoint['id']
        if ctx.gui:
            return
        case = ctx.state['cases'][checkpoint['case']]
        c.current_case = case.id
        # A step whose earlier step of the same scenario did not complete is blocked, not failed.
        if case.needs is not None:
            case.needs(c)

    def begin(self, ctx, checkpoint):
        if ctx.record:
            from reference import recipes
            recipes.begin(ctx, checkpoint)

    def recipe(self, ctx, checkpoint):
        from reference import recipes
        recipes.execute(ctx, checkpoint)

    def check(self, ctx, checkpoint, assertion):
        c = ctx.state['c']
        if ctx.gui:
            import gui_checks
            c.current_case = assertion['id']
            return gui_checks.observe(c, ctx.episode, checkpoint, assertion['check'])
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
