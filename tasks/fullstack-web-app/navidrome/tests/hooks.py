'''Navidrome specifics for the kit driver: setup items, reference recipes and program checks.

Everything reaches the candidate through the black-box runtime: requests use its api operation, the music library its
library operations, restarts its lifecycle operations and the reference recipes its browser operations. The comparison
normalizes generated identities, wall-clock timestamps and decoder details (normalize.Normalize and AliasGraph).
'''
from evaluation.driver import Hooks as Base
from harness import Context
from reference import recipes
import backend
import checks


class Hooks(Base):
    def start(self, ctx):
        ctx.state['c'] = Context(ctx.broker, ctx.out)

    def setup(self, ctx, item):
        c = ctx.state['c']
        if item.get('bootstrap'):
            c.bootstrap()
            for note in c.notes:
                ctx.note(**note)
        elif 'cases' in item:
            # A module fixture cases: unscored, any success status, only the values later cases need.
            for case_id in item['cases']:
                c.current_case = case_id
                backend.case(case_id).action(c, relaxed=True)
        else:
            checks.setup(c, item)

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
