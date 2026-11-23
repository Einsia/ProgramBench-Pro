'''LMMS specifics for the kit driver: setup items, preparation, recipes, product files and checks.

Everything reaches the candidate through the black-box runtime: the product command line through its cli operation,
input documents through upload, files the product wrote through list_files and download, the desktop through observe
and its input operations, and restarts through its lifecycle operations. Rendered and exported audio is decoded by the
verifier's own FFmpeg. LMMS has no scripting pipe, so a GUI checkpoint is checked only through the files the GUI wrote
and the settings file (checks.py).
'''
import os
import struct
import tempfile
from pathlib import Path

from evaluation.broker import BrokerError
from evaluation.driver import Hooks as Base
from harness import SAMPLES, Context, compare
import backend
import checks

# Documented tolerance classes of a rendered signal; a case declares its class in its observation.
# linear: sample playback, a few LSB; signal: synthesized or resampled content, window levels and spectrum within a few
# percent; lossy: encoder delay, padding and quantization allowed. The bounds are calibrated on the standard answer.
BOUNDS = {'linear': {'absolute': 3 / 32768, 'relative': 2e-3},
          'signal': {'absolute': 0.004, 'relative': 0.03},
          'lossy': {'absolute': 0.02, 'relative': 0.1}}
SIGNAL_KEYS = ('tol', 'slack', 'signal')


def document(ctx, name):
    '''Upload the verifier sample that a GUI episode names as an input document.'''
    import document_fixtures
    if name in document_fixtures.DESCRIPTIONS:
        ctx.upload(name, document_fixtures.build(ctx, name))
        return
    for key, spec in SAMPLES.items():
        if spec.filename == name:
            ctx.sample(key)
            return
    if name == 'tone12.mid':
        # Format-0, two deterministic notes (middle C and E), no external
        # soundfont or sample data. The reference imports this into an SF2
        # player track and reports the missing default soundfont separately.
        body = (b'\x00\xff\x51\x03\x07\xa1\x20'
                b'\x00\x90\x3c\x64\x60\x80\x3c\x40'
                b'\x00\x90\x40\x64\x60\x80\x40\x40\x00\xff\x2f\x00')
        data = b'MThd' + struct.pack('>IHHH', 6, 0, 1, 96) + b'MTrk' + struct.pack('>I', len(body)) + body
        ctx.upload(name, data)
        return
    raise ValueError('unknown input document ' + name)


def dismiss_dialogs(ctx, before, attempts=4):
    '''Close the windows a checkpoint left open on purpose (its evidence): Escape while windows that were not there
    when the checkpoint began are still open.'''
    for _ in range(attempts):
        remaining = list(before)
        extra = []
        for title in ctx.window_titles():
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


def leaves_open(checkpoint):
    return any(step.get('leave_open') for step in checkpoint.get('recipe', []))


class Hooks(Base):
    def start(self, ctx):
        scratch = Path(tempfile.mkdtemp(prefix='lmms-', dir=os.environ.get('TMPDIR')))
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
                    document(c, name)
            else:
                raise ValueError('unknown setup operation ' + str(item['op']))
        finally:
            c.flush()

    def prepare(self, ctx, checkpoint):
        c = ctx.state['c']
        if ctx.gui:
            # LMMS has no scripting pipe, so a GUI checkpoint has no scripted preparation.
            c.current_case = checkpoint['id']
            return
        case = ctx.state['cases'][checkpoint['case']]
        c.current_case = case.id
        # A step whose earlier step of the same scenario did not complete is blocked, not failed.
        if case.needs is not None:
            case.needs(c)

    def begin(self, ctx, checkpoint):
        if leaves_open(checkpoint):
            ctx.state['windows_before'] = ctx.state['c'].window_titles()

    def recipe(self, ctx, checkpoint):
        from reference import recipes
        recipes.execute(ctx, checkpoint)

    def collect(self, ctx, checkpoint):
        c = ctx.state['c']
        if ctx.gui and leaves_open(checkpoint):
            dismiss_dialogs(c, ctx.state.get('windows_before', []))
        c.collect()

    def check(self, ctx, checkpoint, assertion):
        c = ctx.state['c']
        if ctx.gui:
            c.current_case = assertion['id']
            return checks.observe(c, ctx.episode, checkpoint, assertion['check'])
        case = ctx.state['cases'][checkpoint['case']]
        c.current_case = case.id
        value = case.action(c)
        c.successful.add(case.id)
        return value

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        if not isinstance(expected, dict) or 'tol' not in expected:
            compare(actual, expected)
            return
        assert isinstance(actual, dict) and actual.get('tol') == expected['tol'], 'the observation has another tolerance class'
        assert 'signal' in actual, 'the observation carries no signal projection'
        slack = expected.get('slack', 0)
        assert actual.get('slack', 0) == slack, 'the observation declares another frame slack'
        rest = lambda value: {key: item for key, item in value.items() if key not in SIGNAL_KEYS}
        compare(rest(actual), rest(expected))
        compare(actual['signal'], expected['signal'], frames=slack, **BOUNDS[expected['tol']])

    def after(self, ctx, checkpoint):
        ctx.state['c'].flush()

    def close(self, ctx):
        c = ctx.state.get('c')
        if c is not None:
            c.close()
