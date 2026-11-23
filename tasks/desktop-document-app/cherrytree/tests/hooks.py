"""CherryTree specifics for the episode driver: episode inputs, reference recipes and program checks.

Everything reaches the candidate through the black-box runtime: input
documents (written by fixtures.py in the storage format an episode names) are
uploaded into its inbox, saved documents and other product files come back
through list_files and download, the product's command-line export runs
through export, and the clipboard is read through clipboard_text.
Documents and exports are decoded verifier-side (artifacts.py).
"""
import os
from pathlib import Path
import tempfile

from evaluation.driver import Hooks as Base
import checks
import fixtures
import specification


class Hooks(Base):
    def start(self, ctx):
        scratch = Path(tempfile.mkdtemp(prefix='cherrytree-', dir=os.environ.get('TMPDIR')))
        ctx.state.update(scratch=scratch, fixtures=scratch / 'fixtures', artifacts=ctx.out / 'artifacts', observed={},
                         outbox=specification.outbox(ctx.episode['id']), inbox=specification.inbox(ctx.episode['id']))

    def setup(self, ctx, item):
        """Upload input documents into the inbox (or prepared documents into the outbox)."""
        if item['op'] == 'open':
            ctx.broker.call({'op': 'restart', 'document': item['document']}, timeout=90)
            return
        assert item['op'] == 'upload', 'unknown setup operation ' + item['op']
        folder = ctx.state['fixtures'] / item['id']
        folder.mkdir(parents=True, exist_ok=True)
        for entry in item['files']:
            for name, data in fixtures.input_files(entry, folder):
                checks.upload(ctx, name, data, area=item.get('area', 'inbox'))

    def prepare(self, ctx, checkpoint):
        # A new checkpoint observes its artifacts afresh.
        ctx.state['observed'] = {}

    def begin(self, ctx, checkpoint):
        if ctx.record:
            from reference import recipes
            recipes.begin(ctx, checkpoint)

    def recipe(self, ctx, checkpoint):
        from reference import recipes
        recipes.execute(ctx, checkpoint)

    def collect(self, ctx, checkpoint):
        if ctx.record:
            from reference import recipes
            recipes.collect(ctx, checkpoint)

    def check(self, ctx, checkpoint, assertion):
        """One aspect of an artifact; the artifact is observed once per checkpoint and shared by its aspects."""
        check = assertion['check']
        key = checks.artifact_key(check)
        cache = ctx.state['observed']
        if key not in cache:
            try:
                cache[key] = (checks.observe(ctx, check), None)
            except Exception as exc:
                cache[key] = (None, exc)
        full, error = cache[key]
        if error is not None:
            raise error
        if ctx.record:
            import expectations
            expectations.validate(ctx.episode, checkpoint, check, full)
        return {'aspect': check['aspect'], 'value': checks.project(full, check)}

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        checks.compare(actual, expected)

    def close(self, ctx):
        import shutil
        shutil.rmtree(ctx.state.get('scratch', ''), ignore_errors=True)
