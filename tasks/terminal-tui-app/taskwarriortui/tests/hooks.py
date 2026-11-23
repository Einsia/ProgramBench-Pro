"""taskwarrior-tui specifics for the shared driver.

Program episodes: `prepare` drives the checkpoint's deterministic key sequence through the runtime; `check` reads the
resulting state (the tasks through the application's command line, semantic screen facts) and `judge` compares it
with the frozen reference. GUI episodes: `recipe` drives the pinned standard for record; the evaluator drives the
candidate for compare; backend companion checks read the resulting state the same way. Everything goes through
ctx.broker; nothing touches product internals.
"""
from evaluation.driver import Hooks as Base

import checks
from harness import Session
from reference import recipes


class Hooks(Base):
    def start(self, ctx):
        ctx.state['session'] = Session(ctx.broker)
        ctx.state['observed'] = {}

    def setup(self, ctx, item):
        checks.apply_setup(ctx.state['session'], item)

    def prepare(self, ctx, checkpoint):
        # Per-checkpoint observation cache (one observation per source, shared by that checkpoint's aspects).
        ctx.state['observed'] = {}
        if not ctx.gui:
            checks.drive(ctx.state['session'], checkpoint.get('steps', []))

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx, checkpoint)

    def check(self, ctx, checkpoint, assertion):
        session = ctx.state['session']
        check = assertion['check']
        key = (checkpoint['id'], checks.source_key(check))
        cache = ctx.state['observed']
        if key not in cache:
            try:
                cache[key] = (checks.observe(session, check), None)
            except Exception as exc:  # observed once; the error is raised for every aspect that shares it
                cache[key] = (None, exc)
        full, error = cache[key]
        if error is not None:
            raise error
        return checks.project(full, check)

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        checks.compare(actual, expected)
