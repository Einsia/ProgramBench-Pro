"""Money Manager Ex specifics for the kit driver: episode inputs, reference recipes and program checks.

Everything reaches the candidate through the black-box runtime: database documents and import files are uploaded into its
inbox before the first goal, the database is opened with the runtime's restart operation, saved databases and exports come
back through list_files and download, and clipboard contents through clipboard_text. Documents are decoded and measured
verifier-side (ledger.py, documents.py).
"""
import base64
import time

from evaluation.driver import Hooks as Base
import checks
import inputs


class Hooks(Base):
    def start(self, ctx):
        ctx.state['observed'] = {}

    def setup(self, ctx, item):
        """Upload the episode's documents; a database named by the item is opened by a restart."""
        assert item['op'] == 'documents', 'unknown setup operation ' + item['op']
        for name in item.get('files', ()):
            data = inputs.document(name)
            ctx.broker.call({'op': 'upload', 'filename': name.rpartition('/')[2], 'area': item.get('area', 'inbox'),
                             'base64': base64.b64encode(data).decode()})
        if item.get('open'):
            status = ctx.broker.call({'op': 'restart', 'database': item['open']})
            if not status.get('ready'):
                raise AssertionError('the application did not start with the database: ' + str(status.get('detail')))
            # The product executes due scheduled transactions a few seconds after opening a database.
            time.sleep(item.get('wait', 4.0))

    def begin(self, ctx, checkpoint):
        if ctx.record:
            from reference import recipes
            recipes.begin(ctx, checkpoint)

    def recipe(self, ctx, checkpoint):
        from reference import recipes
        recipes.execute(ctx, checkpoint)

    def prepare(self, ctx, checkpoint):
        checks.prepare(ctx, checkpoint)
        if not ctx.gui:
            checks.program_prepare(ctx, checkpoint)

    def collect(self, ctx, checkpoint):
        ctx.state['observed'] = {}

    def check(self, ctx, checkpoint, assertion):
        value = checks.observe(ctx, assertion['check'])
        if ctx.record:
            checks.expect(value, assertion['check'])
        return value

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        checks.compare(actual, expected, assertion['check'])

    def after(self, ctx, checkpoint):
        checks.release(ctx)

    def close(self, ctx):
        checks.release(ctx)
