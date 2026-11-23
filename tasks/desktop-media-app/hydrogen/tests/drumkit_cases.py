"""Drumkit tools: validation, extraction, upgrade and installation of verifier-made drumkits.

Every scenario uploads one drumkit archive (.h2drumkit: a gzip tar of a folder with drumkit.xml and samples) and runs
the product's tools on it: `cli check` and `cli legacy-check` (exit status and the verdict line), `cli extract` and
`cli upgrade` into an output folder (exit status, the files written, the drumkit description they hold), and for
kits that install, `cli install` followed by a render of a song that uses the installed kit by name. OSC rows extract,
upgrade and load kits in the running application. Messages compare only the verdict, never a path.
"""
from __future__ import annotations

import io
import re
import tarfile

import fixtures
import songs as S
from harness import MissingDependency, audio_observation
from render_cases import upload_samples

FAMILY = 'drumkit-tools'
SAMPLES = ('kick.wav', 'snare.wav', 'hat.wav', 'tone440.wav')


def sample_bytes(*names):
    return {name: fixtures.sample(name) for name in names}


def kit_instruments(ids=(0, 1, 2), **extra):
    names = (('Kick', 'kick.wav'), ('Snare', 'snare.wav'), ('Hat', 'hat.wav'))
    return [S.Instrument(i, names[i][0], [S.Component([S.Layer(names[i][1])])], volume=1.0 - 0.1 * i,
                         pan=(-0.3, 0.0, 0.3)[i], **extra) for i in ids]


class Kit:
    """One verifier drumkit: its folder name, drumkit.xml text and files."""

    def __init__(self, name, folder, xml, files=None, compression='gz', top=True):
        self.name, self.folder, self.xml = name, folder, xml
        self.files = dict(files if files is not None else sample_bytes('kick.wav', 'snare.wav', 'hat.wav'))
        self.compression, self.top = compression, top

    def archive(self):
        files = dict(self.files)
        if self.xml is not None:
            files['drumkit.xml'] = self.xml
        if self.top:
            return S.archive(self.folder, files, compression=self.compression)
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode='w', format=tarfile.GNU_FORMAT) as tar:
            for name in sorted(files):
                data = files[name].encode() if isinstance(files[name], str) else files[name]
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o644, 1_700_000_000
                tar.addfile(info, io.BytesIO(data))
        import gzip
        return gzip.compress(raw.getvalue(), mtime=0)


def kits():
    valid = S.drumkit_xml('Verifier Kit', kit_instruments(), author='verifier', info='Three synthetic voices',
                          license='CC BY-SA')
    multi = S.drumkit_xml('Layered Kit', [S.Instrument(0, 'Tone', [S.Component(
        [S.Layer('layer220.wav', 0.0, 0.5, 0.8, -1.0), S.Layer('layer550.wav', 0.5, 1.0, 1.2, 0.0)], id=0),
        S.Component([S.Layer('kick.wav')], id=1, gain=0.6)])], components=((0, 'Close', 1.0), (1, 'Room', 0.5)))
    return [
        Kit('valid', 'Verifier Kit', valid),
        Kit('no-namespace', 'Plain Kit', S.drumkit_xml('Plain Kit', kit_instruments(), namespace=False)),
        Kit('legacy', 'Old Kit', S.drumkit_xml('Old Kit', kit_instruments(), legacy=True, namespace=False)),
        Kit('layered', 'Layered Kit', multi, files=sample_bytes('layer220.wav', 'layer550.wav', 'kick.wav')),
        Kit('unicode', 'Kït Ω', S.drumkit_xml('Kït Ω', kit_instruments(), info='ñ & <i>'), compression='gz'),
        Kit('licensed', 'Licensed Kit', S.drumkit_xml('Licensed Kit', kit_instruments(), license='CC0',
                                                      image='cover.png', image_license='CC BY'),
            files={**sample_bytes('kick.wav', 'snare.wav', 'hat.wav'), 'cover.png': b'\x89PNG\r\n\x1a\n' + bytes(64)}),
        Kit('missing-sample', 'Gap Kit', S.drumkit_xml('Gap Kit', kit_instruments()),
            files=sample_bytes('kick.wav', 'hat.wav')),
        Kit('uncompressed', 'Tar Kit', S.drumkit_xml('Tar Kit', kit_instruments()), compression=None),
        Kit('bzip2', 'Bz Kit', S.drumkit_xml('Bz Kit', kit_instruments()), compression='bz2'),
        Kit('no-folder', 'Flat Kit', S.drumkit_xml('Flat Kit', kit_instruments()), top=False),
        Kit('broken-xml', 'Broken Kit', '<?xml version="1.0"?>\n<drumkit_info><name>Broken Kit</name>\n'),
        Kit('wrong-root', 'Root Kit', '<?xml version="1.0"?>\n<song><name>Root Kit</name></song>\n'),
        Kit('bad-values', 'Odd Kit', S.drumkit_xml('Odd Kit', kit_instruments()).replace(
            '<volume>1</volume>', '<volume>loud</volume>', 1).replace('<pan>-0.3</pan>', '<pan>x</pan>', 1)),
        Kit('unknown-element', 'Extra Kit', S.drumkit_xml('Extra Kit', kit_instruments()).replace(
            '<author>verifier</author>', '<author>verifier</author>\n <color>red</color>', 1)),
        Kit('no-name', 'Nameless Kit', re.sub(r'<name>Nameless Kit</name>\n', '',
                                              S.drumkit_xml('Nameless Kit', kit_instruments()), count=1)),
        Kit('no-drumkit-xml', 'Empty Kit', None),
        Kit('settings', 'Settings Kit', S.drumkit_xml('Settings Kit', [
            S.Instrument(0, 'Kick', [S.Component([S.Layer('kick.wav', gain=0.9)])], volume=0.6, pan=-0.4, gain=1.3,
                         attack=500, decay=1000, sustain=0.7, release=2000, filter_active=True, filter_cutoff=0.6,
                         mute_group=1, midi_note=40),
            S.Instrument(1, 'Snare', [S.Component([S.Layer('snare.wav', pitch=-2.0)])], volume=0.9, pan=0.3,
                         stop_note=True, midi_channel=9, midi_note=38),
            S.Instrument(2, 'Hat', [S.Component([S.Layer('hat.wav', min=0.0, max=0.5),
                                                 S.Layer('hat.wav', min=0.5, max=1.0, gain=1.5)])],
                         hihat=1, lower_cc=20, higher_cc=90, selection='ROUND_ROBIN')], author='Verifier Ltd.',
                                                      info='Instruments with their own settings')),
        Kit('two-components', 'Room Kit', S.drumkit_xml('Room Kit', [S.Instrument(0, 'Snare', [
            S.Component([S.Layer('snare.wav')], id=0), S.Component([S.Layer('hat.wav', gain=0.5)], id=1, gain=0.8)])],
            components=((0, 'Close', 1.0), (1, 'Room', 0.6))), files=sample_bytes('snare.wav', 'hat.wav')),
        Kit('subfolder', 'Folder Kit', S.drumkit_xml('Folder Kit', [
            S.Instrument(i, name, [S.Component([S.Layer('samples/' + sample)])])
            for i, (name, sample) in enumerate((('Kick', 'kick.wav'), ('Snare', 'snare.wav'), ('Hat', 'hat.wav')))]),
            files={'samples/' + name: data for name, data in sample_bytes('kick.wav', 'snare.wav', 'hat.wav').items()}),
        Kit('quoted-name', "Tom's & Co Kit", S.drumkit_xml("Tom's & Co Kit", kit_instruments(), author='Tom & Co')),
        Kit('gpl', 'GPL Kit', S.drumkit_xml('GPL Kit', kit_instruments(), license='GPL',
                                            info='Line one\nLine two')),
        Kit('xz', 'Xz Kit', S.drumkit_xml('Xz Kit', kit_instruments()), compression='xz'),
        Kit('many', 'Big Kit', S.drumkit_xml('Big Kit', [
            S.Instrument(i, f'Voice {i + 1}', [S.Component([S.Layer(('kick.wav', 'snare.wav', 'hat.wav')[i % 3])])],
                         volume=round(1.0 - 0.05 * i, 2)) for i in range(10)])),
    ]


# Kits that install and are then used by name: by a song naming the kit and its instruments (Kick, Snare and Hat, or
# the Tone of the layered kit), or for the others by exporting a verifier song with the kit loaded instead (-k).
# (The unicode kit's folder name depends on the host locale; the quoted-name kit installs under a folder without its
# apostrophe, so its name finds no kit; the GPL kit differs from the valid kit only in its description.)
INSTALLABLE = ('valid', 'legacy', 'layered', 'no-namespace', 'settings', 'two-components', 'subfolder', 'xz', 'many')
EXTRA = ('settings', 'two-components', 'subfolder', 'quoted-name', 'gpl', 'xz', 'many')
STANDARD = ('valid', 'legacy', 'no-namespace', 'xz')


def after(step):
    return (step,)


# The command line writes its verdict to standard output and its log to standard error; the runtime replies with
# both streams in one text, where a log line may land in the middle of the verdict line.
COLOR = re.compile(r'\x1b\[[0-9;]*m')
LOG_LINE = re.compile(r'\((?:E|W|I|D|L)\) \[[^\]\n]*\][^\n]*\n?')


def without_log(output):
    return LOG_LINE.sub('', COLOR.sub('', output))


def verdict(output):
    match = re.search(r'Provided (legacy )?drumkit \[[^\n]*?\] is (valid|INVALID!)', without_log(output))
    return match.group(2).rstrip('!').casefold() if match else None


def target_files(reply, target):
    prefix = 'outputs/' + target + '/'
    return sorted(d['path'][len(prefix):] for d in reply.get('downloads', []) if d.get('path', '').startswith(prefix))


def tar_members(data):
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as tar:
            members = {m.name: (tar.extractfile(m).read() if m.isreg() else None) for m in tar.getmembers()}
    except (tarfile.TarError, OSError, EOFError):
        raise AssertionError('the drumkit file is not a readable tar archive') from None
    return members


def kit_projection(ctx, data):
    return S.drumkit_projection(data, ctx.places())


def check_step(kit, action):
    def run(ctx):
        reply = ctx.cli(action, drumkit=kit.name + '.h2drumkit')
        own = {'exit_code': reply['exit_code'], 'verdict': verdict(reply['output'])}
        invalid = kit.name in ('no-folder', 'broken-xml', 'wrong-root', 'no-name', 'no-drumkit-xml') or \
            (kit.name == 'legacy' and action == 'check')
        other = ctx.cli(action, drumkit='control-valid.h2drumkit' if invalid else 'control-invalid.h2drumkit')
        contrast = {'exit_code': other['exit_code'], 'verdict': verdict(other['output'])}
        assert own['verdict'] is not None and contrast['verdict'] is not None, 'the CLI returned no validation verdict'
        return {'document': own, 'contrast': contrast}
    return run


def extract_step(kit):
    def run(ctx):
        target = 'x-' + kit.name
        reply = ctx.cli('extract', drumkit=kit.name + '.h2drumkit', target=target)
        files = target_files(reply, target)
        out = {'exit_code': reply['exit_code'], 'files': files}
        xml = [f for f in files if f.endswith('drumkit.xml')]
        if xml and kit.xml is not None:
            # Extraction copies the archive members: the description must arrive byte for byte.
            data = ctx.take(f'outputs/{target}/{xml[0]}', reply.get('downloads'))
            out['description_intact'] = data == kit.xml.encode('utf-8')
        return out
    return run


def upgrade_step(kit):
    def run(ctx):
        target = 'u-' + kit.name
        reply = ctx.cli('upgrade', drumkit=kit.name + '.h2drumkit', target=target)
        files = target_files(reply, target)
        out = {'exit_code': reply['exit_code'], 'files': files}
        archives = [f for f in files if f.endswith('.h2drumkit')]
        if archives:
            members = tar_members(ctx.take(f'outputs/{target}/{archives[0]}', reply.get('downloads')))
            out['members'] = sorted(name for name in members if members[name] is not None)
            xml = [name for name in members if name.endswith('drumkit.xml') and members[name] is not None]
            if xml:
                out['drumkit'] = kit_projection(ctx, members[xml[0]])
        return out
    return run


def installed_render(kit, instrument_names=None):
    """Install the kit, then play it by name: a song that names the kit and its instruments plays the kit's samples
    (instrument_names), or a verifier song is exported with the kit loaded in its place (-k)."""
    def run(ctx):
        installed = ctx.cli('install', drumkit=kit.name + '.h2drumkit')['exit_code']
        stem = ctx.unique('kit-render', '')
        if instrument_names:
            layers = {'Kick': 'kick.wav', 'Snare': 'snare.wav', 'Hat': 'hat.wav', 'Tone': 'layer220.wav'}
            instruments = [S.Instrument(i, name, [S.Component([S.Layer(layers[name])])], drumkit=kit.folder,
                                        drumkit_lookup=0) for i, name in enumerate(instrument_names)]
            song = S.Song(instruments, [S.Pattern('P', [S.Note(48 * i, i) for i in range(len(instruments))])])
            ctx.upload(stem + '.h2song', song.xml())
            reply = ctx.cli('export', song=stem + '.h2song', output=stem + '.wav')
        else:
            ctx.upload('click.wav', fixtures.sample('click.wav'))
            beats = S.Song([S.Instrument(i, f'Slot {i}', [S.Component([S.Layer(ctx.inputs('click.wav'))])])
                            for i in range(10)],
                           [S.Pattern('P', [S.Note(16 * i, i, velocity=0.5 + 0.05 * i) for i in range(10)])])
            ctx.upload(stem + '.h2song', beats.xml())
            reply = ctx.cli('export', song=stem + '.h2song', output=stem + '.wav', kit=kit.folder)
        info, frames = ctx.decode(ctx.take('outputs/' + stem + '.wav', reply.get('downloads')), stem + '.wav')
        return {'install_exit_code': installed, 'render': audio_observation(info, frames, {'onsets': 0.02,
                                                                                          'window': 2048})}
    return run


def build(suite):
    for kit in kits():
        scenario = 'kit-' + kit.name

        def prepare(ctx, kit=kit):
            ctx.fresh()
            ctx.upload(kit.name + '.h2drumkit', kit.archive())
            controls = kits()
            ctx.upload('control-valid.h2drumkit', controls[0].archive())
            ctx.upload('control-invalid.h2drumkit', next(k for k in controls if k.name == 'no-name').archive())
        suite.setup(FAMILY, scenario, prepare, f'Fresh instance with the drumkit document {kit.name}.h2drumkit')
        if kit.name not in EXTRA:
            # (The verdict of the further kits repeats the verdict of the kits above.)
            for action in ('check', 'legacy-check'):
                suite.add(FAMILY, scenario, action, check_step(kit, action),
                          description=f'Run `{action}` on the {kit.name} drumkit and a contrasting named/nameless '
                                      'control; read both exit statuses and verdicts')
        if kit.name != 'unicode':
            # (Extracting a folder name outside ASCII depends on the locales of the host, not on the product.)
            suite.add(FAMILY, scenario, 'extract', extract_step(kit),
                      description=f'Extract the {kit.name} drumkit into an output folder; read the files written')
        suite.add(FAMILY, scenario, 'upgrade', upgrade_step(kit),
                  description=f'Upgrade the {kit.name} drumkit into an output folder; read the archive it writes')
        if kit.name in INSTALLABLE:
            if kit.name == 'layered' or kit.name in STANDARD:
                names = ['Tone'] if kit.name == 'layered' else ['Kick', 'Snare', 'Hat']
                suite.add(FAMILY, scenario, 'install-render', installed_render(kit, names),
                          description=f'Install the {kit.name} drumkit and render a song that names the installed kit '
                                      'and its instruments instead of sample paths')
            else:
                suite.add(FAMILY, scenario, 'install-render', installed_render(kit),
                          description=f'Install the {kit.name} drumkit and export a ten-instrument verifier song with '
                                      'the installed kit loaded in place of its own instruments (-k)')
    osc(suite)


def osc(suite):
    valid = kits()[0]

    def prepare(ctx):
        ctx.fresh()
        upload_samples(ctx)
        ctx.upload('valid.h2drumkit', valid.archive())
        ctx.upload('kit-target.h2song', S.Song(
            [S.Instrument(0, 'Empty', [])], [S.Pattern('Empty', [])], name='Empty').xml())
        ctx.open_song('kit-target.h2song')
        ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)
    suite.setup(FAMILY, 'osc', prepare,
                'Fresh instance with the valid drumkit uploaded and an empty one-instrument song opened')

    def extract(ctx):
        replies = ctx.osc('/Hydrogen/EXTRACT_DRUMKIT', 'valid.h2drumkit', 'osc-extract', wait=1.5)
        files = sorted(r['path'][len('outputs/osc-extract/'):] for r in ctx.pending()
                       if r.get('path', '').startswith('outputs/osc-extract/'))
        return {'files': files}
    extracted = suite.add(FAMILY, 'osc', 'extract', extract,
                          description='Send /Hydrogen/EXTRACT_DRUMKIT with a target folder; read the files written')

    def upgrade(ctx):
        ctx.osc('/Hydrogen/UPGRADE_DRUMKIT', 'valid.h2drumkit', 'osc-upgrade', wait=2.0)
        files = sorted(r['path'][len('outputs/osc-upgrade/'):] for r in ctx.pending()
                       if r.get('path', '').startswith('outputs/osc-upgrade/'))
        return {'files': files}
    suite.add(FAMILY, 'osc', 'upgrade', upgrade,
              description='Send /Hydrogen/UPGRADE_DRUMKIT with a target folder; read the files written')

    view = lambda p: {'drumkit': p['song']['drumkit'], 'instruments': [[i['name'], i['drumkit']] for i in p['instruments']]}

    def load_path(ctx):
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', ctx.areas()['outputs'] + '/osc-extract/Verifier Kit', wait=2.0)
        return view(ctx.song())
    loaded = suite.add(FAMILY, 'osc', 'load-folder', load_path, needs=after(extracted),
                       description='Send /Hydrogen/LOAD_DRUMKIT with the extracted kit folder; read the instruments')

    def install_and_load(ctx):
        ctx.osc('/Hydrogen/EXTRACT_DRUMKIT', 'valid.h2drumkit', wait=1.5)
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', 'TR808EmulationKit', wait=2.0)
        # Replace the song before loading a smaller kit: the native OSC thread
        # otherwise shrinks the same instrument list that the GUI timer reads.
        ctx.open_song('kit-target.h2song')
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', 'Verifier Kit', wait=2.0)
        return view(ctx.song())
    suite.add(FAMILY, 'osc', 'install-load-name', install_and_load,
              description='Send /Hydrogen/EXTRACT_DRUMKIT without a target (installs), load the factory TR808 kit, '
                          'open an empty one-instrument song, then load the installed kit by name')

    def unknown(ctx):
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', 'TR808EmulationKit', wait=2.0)
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', 'No Such Kit', wait=1.0)
        return view(ctx.song())
    suite.add(FAMILY, 'osc', 'load-unknown', unknown, requires=(loaded,),
              description='Load the factory TR808 kit, then send /Hydrogen/LOAD_DRUMKIT with an unknown kit name')
