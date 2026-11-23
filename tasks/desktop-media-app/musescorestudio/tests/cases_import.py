'''Program cases: generated score fixtures imported by the product and read back in every output form.

Each scenario imports one fixture into a project document, then reads that project through the product command
line: MusicXML export, MIDI export, score document (mscx), project archive (mscz), metadata and element listing,
plus one direct conversion (see DIRECT). Observations are the projections of semantic.py, never raw
bytes.
'''
from harness import MissingDependency
import fixtures

CATALOG = fixtures.catalog()
XML = sorted(name for name in CATALOG if name.endswith('.musicxml'))
MID = sorted(name for name in CATALOG if name.endswith('.mid'))
FORMS = (
    ('xml', '.musicxml', 'MusicXML'),
    ('mid', '.mid', 'MIDI'),
    ('mscx', '.mscx', 'score document (mscx)'),
    ('mscz', '.mscz', 'project archive (mscz)'),
)
LISTINGS = (
    ('meta', '--score-meta', 'metadata listing (--score-meta)'),
    ('elements', '--score-elements', 'element listing (--score-elements)'),
)
# Converting a fixture directly gives the same observation as reading it back through the project archive, except for
# the MIDI of two-track (measured on the pinned standard), so only that point is scored.
DIRECT = (('two-track', '.mid', 'MIDI'),)


def prepare(fixture, scenario):
    def action(ctx):
        ctx.new_scenario(scenario)
        ctx.project_of(fixture)
        ctx.state['backend'] = {'scenario': scenario, 'fixture': fixture}
        return {'imported': True}
    return action


def needs(scenario):
    def check(ctx):
        state = ctx.state.get('backend')
        if not state or state.get('scenario') != scenario:
            raise MissingDependency('successful import is missing for ' + scenario)
    return check


def export_action(kind, suffix):
    def action(ctx):
        source = ctx.project_of(ctx.state['backend']['fixture'])
        if kind == 'mscx':
            _reply, data = ctx.produce_mscx(source)
        else:
            _reply, data = ctx.produce(source, suffix)
        return ctx.project('x' + suffix, data)
    return action


def direct_action(suffix):
    def action(ctx):
        source = ctx.fixture(ctx.state['backend']['fixture'])
        _reply, data = ctx.produce(source, suffix)
        return ctx.project('x' + suffix, data)
    return action


def listing_action(kind, option):
    def action(ctx):
        source = ctx.project_of(ctx.state['backend']['fixture'])
        return ctx.stdout_projection(kind, ctx.convert(source, option))
    return action


def build(suite):
    for fixture in XML + MID:
        stem = fixture.rsplit('.', 1)[0]
        family = 'musicxml' if fixture.endswith('.musicxml') else 'midi'
        source = 'MusicXML' if family == 'musicxml' else 'MIDI'
        suite.add(family + '-fixture', stem, 'import', prepare(fixture, stem), channel='setup',
                  description='Import the ' + source + ' fixture ' + stem + ' into a project document')
        for kind, suffix, label in FORMS:
            suite.add(family, stem, kind, export_action(kind, suffix), needs=needs(stem),
                      description='The ' + source + ' fixture ' + stem + ' imported and exported as ' + label
                      + ' has the recorded content')
        for kind, option, label in LISTINGS:
            suite.add(family, stem, kind, listing_action(kind, option), needs=needs(stem),
                      description='The imported ' + source + ' fixture ' + stem + ' reports the recorded ' + label)
        for name, suffix, label in DIRECT:
            if name == stem:
                suite.add(family, stem, 'direct-' + suffix[1:], direct_action(suffix), needs=needs(stem),
                          description='The ' + source + ' fixture ' + stem + ' converted directly to ' + label
                          + ' has the recorded content')
