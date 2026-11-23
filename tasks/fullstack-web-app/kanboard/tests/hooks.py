"""Kanboard specifics for the shared driver: setup items, reference recipes and program checks.

Everything reaches the candidate through the black-box runtime: program checks and setup use its api operation
(the JSON-RPC API, the feeds and the cron job URL), restarts its lifecycle operations, and the reference recipes its
browser operations. The comparison normalizes generated identities, clock timestamps and opaque generated strings
(harness.Normalize/AliasGraph).
"""
from evaluation.driver import Hooks as Base
from harness import Context
import backend
import checks
from reference import recipes


class Hooks(Base):
    def start(self, ctx):
        ctx.state['c'] = Context(ctx.broker)

    def inputs(self, ctx):
        checks.inputs(ctx, ctx.episode)

    def setup(self, ctx, item):
        c = ctx.state['c']
        if 'cases' in item:
            # A module's fixture steps: unscored, any successful answer, only the values later steps need.
            for case_id in item['cases']:
                c.current_case = case_id
                backend.case(case_id).action(c)
        else:
            checks.setup(c, item)

    def prepare(self, ctx, checkpoint):
        checks.prepare(ctx.state['c'], checkpoint)

    def begin(self, ctx, checkpoint):
        checks.begin(ctx, ctx.state['c'], checkpoint)

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx, ctx.state['c'], checkpoint)

    def collect(self, ctx, checkpoint):
        checks.collect(ctx, ctx.state['c'], checkpoint)

    def check(self, ctx, checkpoint, assertion):
        c = ctx.state['c']
        c.current_case = checkpoint['id']
        if 'check' in assertion:
            return checks.observe(ctx, c, checkpoint, assertion['check'])
        observation = backend.case(checkpoint['case']).action(c)
        assert isinstance(observation, dict) and observation, 'program case produced no observation'
        return observation

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        # Generated identities must keep their relationships across the whole episode (typed bijection).
        ctx.state['c'].aliases.compare(actual, expected)
