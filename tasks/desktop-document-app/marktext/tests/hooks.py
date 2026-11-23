"""MarkText specifics for the episode driver: episode inputs, reference recipes and program checks.

Everything reaches the candidate through the black-box runtime: episode inputs
are uploaded into the inbox before the first goal, documents are opened with the
runtime's `open`, program episodes drive the application and read back the
documents it writes, and GUI episodes are operated by the evaluator. Saved and
exported documents come back through list_files and download, and clipboard
contents through clipboard_text, clipboard_html and clipboard_image; everything
is normalized verifier-side (artifacts.py).
"""
from evaluation.driver import Hooks as Base
import checks
import drive
import fixtures
from reference import recipes


class Hooks(Base):
    def start(self, ctx):
        ctx.state['artifacts'] = ctx.out / 'artifacts'
        ctx.state['observed'] = {}
        ctx.state['opened'] = False

    def setup(self, ctx, item):
        assert item['op'] == 'upload', 'unknown setup operation ' + item['op']
        for entry in item['files']:
            data = fixtures.content(entry)
            name = entry['name'] if isinstance(entry, dict) else entry
            checks.upload(ctx, name, data, area=item.get('area', 'inbox'), read_only=item.get('read_only', False))

    def prepare(self, ctx, checkpoint):
        if not ctx.state['opened']:
            ctx.state['opened'] = True
            opened = ctx.episode.get('opened_paths') or []
            if opened:
                ctx.broker.call({'op': 'open', 'paths': opened}, timeout=90)
                drive.settle(ctx, 3.0)
        if checkpoint.get('drive'):
            drive.run(ctx, checkpoint['drive'])

    def begin(self, ctx, checkpoint):
        if ctx.record:
            recipes.begin(ctx, checkpoint)

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx, checkpoint)

    def check(self, ctx, checkpoint, assertion):
        check = assertion['check']
        key = (checkpoint['id'], checks.artifact_key(check))
        cache = ctx.state['observed']
        if key not in cache:
            try:
                full = checks.observe(ctx, check)
                if ctx.record:
                    checks.expect(full, check)
                cache[key] = (full, None)
            except Exception as exc:
                cache[key] = (None, exc)
        full, error = cache[key]
        if error is not None:
            raise error
        return checks.project(full, check)

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        checks.compare(actual, expected)
