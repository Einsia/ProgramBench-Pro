'''Mealie specifics for the kit driver: setup items, reference recipes and program checks.

Everything reaches the candidate through the black-box runtime: program checks and setup use its api operation, restarts
its lifecycle operations, and the reference recipes its browser operations. The comparison normalizes generated
identities, clock fields and secrets (harness.Normalize, harness.AliasGraph).
'''
import base64
import inspect

from evaluation.driver import Hooks as Base
from harness import Context
import backend
import checks
from reference import recipes


class Hooks(Base):
    def start(self, ctx):
        ctx.state['c'] = Context(ctx.broker, ctx.out)

    def inputs(self, ctx):
        # The file of the goal is the one the evaluator may offer to a file chooser (the broker upload takes names from this directory).
        file = ctx.episode.get('inputs', {}).get('file')
        if file:
            (ctx.inputs / file['name']).write_bytes(base64.b64decode(file['base64']) if 'base64' in file else file['text'].encode())

    def setup(self, ctx, item):
        c = ctx.state['c']
        if 'cases' in item:
            # A module's fixture cases: unscored, any success status, only the values later cases need.
            for case_id in item['cases']:
                action = backend.case(case_id).action
                c.current_case = case_id
                if 'relaxed' in inspect.signature(action).parameters:
                    action(c, relaxed=True)
                else:
                    action(c)
        else:
            checks.setup(c, item)

    def prepare(self, ctx, checkpoint):
        if checkpoint.get('open_before'):
            ctx.broker.call({'op':'open','session':'main','path':checks.resolve(checkpoint['open_before'],ctx.state['c'].state)})

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx, ctx.state['c'], checkpoint)

    def check(self, ctx, checkpoint, assertion):
        c = ctx.state['c']
        c.current_case = checkpoint['id']
        if 'check' in assertion:
            return checks.observe(c, assertion['check'])
        observation = backend.case(checkpoint['case']).action(c)
        assert isinstance(observation, dict) and observation, 'program case produced no observation'
        return observation

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        # Generated identities must keep their relationships across the whole episode (typed bijection).
        ctx.state['c'].aliases.compare(actual, expected)

    def close(self, ctx):
        c = ctx.state.get('c')
        if c:
            c.close()
