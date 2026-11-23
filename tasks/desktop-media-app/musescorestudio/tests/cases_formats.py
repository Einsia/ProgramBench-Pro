'''Program cases: file formats and output options of the product command line.

Each scenario converts one fixture with one format or option and observes the parsed output: compressed MusicXML, MEI and SVG for every fixture, repeat unrolling, text-type inference, the test mode, MP3 bitrates, PNG sizes, style files that change the page, the score parts and score media modes and the version options. Observations are the projections of semantic.py; no expected value is written here. What is left out (the product crashes on unrolled repeats in SVG and PDF, and PDF points per fixture all count one A4 page) is explained in COVERAGE.md.
'''
import fixtures

CATALOG = fixtures.catalog()
ROSTER = tuple(sorted(CATALOG))
FORMATS = (('mxl', '.mxl', 'compressed MusicXML'), ('mei', '.mei', 'MEI'), ('svg', '.svg', 'SVG'))
PAGED = ('.svg', '.png')
# 128 kbit/s is the default rate: it repeats the plain MP3 point of cases_export, so only the other rates are scored.
RATES = ('32', '64')
STYLES = {'a5': ('A5 portrait', 5.83, 8.27), 'letter': ('US Letter portrait', 8.5, 11.0),
          'a3': ('A3 portrait', 11.69, 16.54), 'landscape': ('A4 landscape', 11.69, 8.27)}
PNGS = (
    ('r36', 'scale-c.musicxml', ('-r', '36'), 'at 36 dpi'),
    ('r50', 'scale-c.musicxml', ('-r', '50'), 'at 50 dpi'),
    ('r72', 'scale-c.musicxml', ('-r', '72'), 'at 72 dpi'),
    ('r96', 'scale-c.musicxml', ('-r', '96'), 'at 96 dpi'),
    ('r144', 'scale-c.musicxml', ('-r', '144'), 'at 144 dpi'))
# Trimming (-T margin) is observed as the growth of the image over margin 0: the trimmed box itself depends on glyph
# outlines and layout details, while the growth is what the option does.
TRIM_MARGINS = (10, 40)
TRIMS = ('scale-c.musicxml', 'two-parts.musicxml', 'accidentals.musicxml', 'rhythms.musicxml', 'piano-grand.musicxml')
VERSIONS = (('short', '-v', 'The version option -v prints the recorded version line'),
            ('long', '--long-version', 'The long version option --long-version prints the recorded version line with its build'))
TEST_MODE = ('scale-c.musicxml', 'two-parts.musicxml')
PARTS = ('scale-c.musicxml', 'two-parts.musicxml', 'piano-grand.musicxml')
PARTS_PDF = ('scale-c.musicxml', 'two-parts.musicxml')
assert len(ROSTER) == len(CATALOG) and all(name.endswith(('.musicxml', '.mid')) for name in ROSTER)
MEDIA = ('scale-c.musicxml', 'two-parts.musicxml', 'rhythms.musicxml')
# Unrolling changes these fixtures (measured on the standard); segno-coda unrolls to the plain export, so it is not scored.
UNROLLED = ('repeats.musicxml', 'voltas.musicxml')
assert all(name in CATALOG for name in TEST_MODE + PARTS + PARTS_PDF + MEDIA + UNROLLED)
assert all(fixture in CATALOG for _step, fixture, _options, _label in PNGS)


def style_bytes(width, height):
    q = chr(34)
    lines = ['<?xml version=' + q + '1.0' + q + ' encoding=' + q + 'UTF-8' + q + '?>', '<museScore version=' + q + '4.70' + q + '>',
             '  <Style>', '    <pageWidth>%s</pageWidth>' % width, '    <pageHeight>%s</pageHeight>' % height,
             '  </Style>', '</museScore>', '']
    return chr(10).join(lines).encode()


def style(ctx, key):
    name = 'page-' + key + '.mss'
    if name not in ctx.uploaded:
        ctx.document(name, style_bytes(*STYLES[key][1:]))
    return name


def render(ctx, fixture, suffix, options=()):
    source = ctx.fixture(fixture)
    if suffix in PAGED:
        _reply, pages = ctx.produce_pages(source, suffix, *options)
        return [ctx.project('x' + suffix, page) for page in pages]
    _reply, data = ctx.produce(source, suffix, *options)
    return ctx.project('x' + suffix, data)


def rendered(fixture, suffix, options=()):
    def action(ctx):
        return render(ctx, fixture, suffix, options)
    return action


def styled(fixture, suffix, key):
    def action(ctx):
        extra = ('-r', '72') if suffix == '.png' else ()
        return render(ctx, fixture, suffix, extra + ('-S', style(ctx, key)))
    return action


def trim_action(fixture):
    def action(ctx):
        sizes = {}
        for margin in (0,) + TRIM_MARGINS:
            pages = render(ctx, fixture, '.png', ('-r', '72', '-T', str(margin)))
            assert len(pages) == 1, 'a trimmed export of a one-page score writes one image'
            sizes[margin] = (pages[0]['width'], pages[0]['height'])
        base = sizes[0]
        return {'growth': {str(m): [sizes[m][0] - base[0], sizes[m][1] - base[1]] for m in TRIM_MARGINS}}
    return action


def bitrate_action(rate):
    def action(ctx):
        _reply, data = ctx.produce(ctx.fixture('scale-c.musicxml'), '.mp3', '-b', rate)
        return ctx.audio('x.mp3', data)
    return action


def printed(option, kind, fixture=None):
    '''The standard output of one run of an option, through the projection of its kind.'''
    def action(ctx):
        arguments = (ctx.fixture(fixture), option) if fixture else (option,)
        return ctx.stdout_projection(kind, ctx.convert(*arguments))
    return action


def build(suite):
    for step, suffix, label in FORMATS:
        for fixture in ROSTER:
            stem, _dot, kind = fixture.rpartition('.')
            source = 'MusicXML' if kind == 'musicxml' else 'MIDI'
            suite.add('format-' + step, stem, 'export', rendered(fixture, suffix),
                      description='The ' + source + ' fixture ' + stem + ' exported as ' + label + ' has the recorded content')
    for fixture in UNROLLED:
        stem = fixture.rpartition('.')[0]
        for suffix, label in (('.musicxml', 'MusicXML'), ('.mid', 'MIDI')):
            suite.add('format-unroll', stem, suffix[1:], rendered(fixture, suffix, ('--unroll-repeats',)),
                      description='The fixture ' + stem + ' exported as ' + label + ' with its repeats unrolled has the recorded content')
    suite.add('format-text', 'dynamics-tempo', 'infer', rendered('dynamics-tempo.musicxml', '.mscz', ('--musicxml-infer-text-type',)),
              description='The fixture dynamics-tempo imported with text type inference has the recorded score document')
    for rate in RATES:
        suite.add('format-bitrate', 'scale-c', 'b' + rate, bitrate_action(rate),
                  description='The fixture scale-c rendered as MP3 at ' + rate + ' kbps sounds as recorded')
    for step, fixture, options, label in PNGS:
        suite.add('format-png', step, 'size', rendered(fixture, '.png', options),
                  description='The fixture ' + fixture.rpartition('.')[0] + ' exported as PNG ' + label + ' has the recorded image size')
    for fixture in TRIMS:
        stem = fixture.rpartition('.')[0]
        suite.add('format-png', stem + '-trim', 'growth', trim_action(fixture),
                  description='The fixture ' + stem + ' exported as PNG at 72 dpi and trimmed grows over margin 0 by the recorded pixels for margins '
                  + ' and '.join(str(m) for m in TRIM_MARGINS))
    for key, (label, _width, _height) in STYLES.items():
        for suffix, name in (('.pdf', 'PDF'), ('.svg', 'SVG')):
            suite.add('format-style', 'scale-c-' + key, suffix[1:], styled('scale-c.musicxml', suffix, key),
                      description='The fixture scale-c exported as ' + name + ' with a style file that sets the page to ' + label + ' has the recorded page')
        if key in ('a5', 'landscape'):
            suite.add('format-style', 'scale-c-' + key, 'png', styled('scale-c.musicxml', '.png', key),
                      description='The fixture scale-c exported as PNG with a style file that sets the page to ' + label + ' has the recorded image size')
    for step, option, description in VERSIONS:
        suite.add('format-version', 'product', step, printed(option, 'version'), description=description)
    for fixture in TEST_MODE:
        stem = fixture.rpartition('.')[0]
        suite.add('format-testmode', stem, 'mscz', rendered(fixture, '.mscz', ('-t',)),
                  description='The fixture ' + stem + ' converted to a project in test mode has the recorded score document')
    for fixture in PARTS:
        stem = fixture.rpartition('.')[0]
        suite.add('format-parts', stem, 'score-parts', printed('--score-parts', 'parts', fixture),
                  description='The fixture ' + stem + ' printed by the score parts mode lists its parts with the recorded score document of each part')
    for fixture in PARTS_PDF:
        stem = fixture.rpartition('.')[0]
        suite.add('format-partspdf', stem, 'score-parts-pdf', printed('--score-parts-pdf', 'partspdf', fixture),
                  description='The fixture ' + stem + ' printed by the score parts PDF mode lists its parts with the recorded page structure of each part PDF and of the score PDFs')
    for fixture in MEDIA:
        stem = fixture.rpartition('.')[0]
        suite.add('format-media', stem, 'score-media', printed('--score-media', 'media', fixture),
                  description='The fixture ' + stem + ' printed by the score media mode carries the recorded media counts and position documents')
