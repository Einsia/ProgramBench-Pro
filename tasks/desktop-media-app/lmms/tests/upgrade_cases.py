'''Project file coverage of the product command line: upgrade, dump and the project container.

Every point uploads a generated project document and runs cli upgrade or cli dump on it. The reply carries the project
XML (body) or the file the action wrote. A point returns the normalized projection of that XML (window geometry and ids
removed, numbers rounded, notes sorted) or, for a rejected input, only what a user can see: the exit status, whether the
output is blank and whether a message was printed. The exit status of dump and upgrade is 0 even for unreadable input,
so rejections are observed through the body, the written file and the message. A rejection counts only together with the
point that shows the same action accepting a valid project.
'''
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
import zlib

import projectxml as px
from harness import project_projection

NL = chr(10)
# One version below and one at or above each upgrade step: 0.4.0-20080409 (positions times three), 0.4.0-rc2 (sample
# names, bass shape), 1.1.0 (sends), 1.1.91 (arpeggio direction, sample path) and 1.2.0-rc3 (steps, sync modes).
VERSIONS = ('0.4.0-20080408', '0.4.0-20080409', '0.4.0', '1.0.99', '1.1.0', '1.1.91', '1.2.0-rc3', '1.2.1', '1.3.0')
OLD_FORMATS = (('arpeggio', '2', '0', '0.5'), ('arpeggio-off', '0', '1', '0.25'), ('arpeggio-3', '3', '0', '1.0'))
DUMP_OK = 'backend.project-file.dump-compressed.result'
UPGRADE_OK = 'backend.project-file.upgrade-to-compressed.result'


def composite(version):
    '''One project that every upgrade step of the 0.4.0 to 1.2.0 era changes something in, saved by the given version.'''
    project = px.Project(bpm=140)
    project.add(px.instrument_track('Lead', 'tripleoscillator', notes=[(0, 48, 57), (48, 48, 60)]))
    project.add(px.instrument_track('Sampler', 'audiofileprocessor', params={'src': '/samples/bassloopes/x.ogg'}))
    project.add(px.instrument_track('Drums', 'audiofileprocessor', params={'src': 'drumsynth/misc kick.ogg'}))
    project.add(px.instrument_track('Bass', 'lb302', params={'shape': 3}))
    project.add(px.beat_track(name='Beat/Baseline 0', tracks=[px.instrument_track('Kicker', 'kicker', steps=[0, 4, 8, 12])]))
    project.channel(1, 'A', sends=())
    project.channel(2, 'B', sends=())
    root = ET.fromstring(project.xml())
    root.set('creatorversion', version)
    for holder in root.iter('bbtrack'):
        for item in holder.iter('pattern'):
            item.set('steps', '4')
    lead = root.find('song/trackcontainer/track/instrumenttrack')
    ET.SubElement(lead, 'arpeggiator', {'arpdir': '3', 'syncmode': '2', 'arptime_numerator': '4', 'arptime_syncmode': '0'})
    return px.HEADER + ET.tostring(root, encoding='unicode') + NL


def old_format(arpdir, chorddisabled, volume):
    '''A project in the format of LMMS 0.2.1: head values as child elements, channel tracks, arpeggio and chords in one.'''
    root = ET.Element('lmms-project', {'version': '1.0', 'creator': 'LMMS', 'creatorversion': '0.2.1-20070401', 'type': 'song'})
    head = ET.SubElement(root, 'head')
    ET.SubElement(head, 'bpm', {'value': '120'})
    ET.SubElement(head, 'mastervol', {'value': '80'})
    ET.SubElement(head, 'masterpitch', {'value': '3'})
    song = ET.SubElement(root, 'song')
    container = ET.SubElement(song, 'trackcontainer', {'type': 'song'})
    track = ET.SubElement(container, 'track', {'type': '0', 'name': 'Old'})
    channel = ET.SubElement(track, 'channeltrack', {'vol': '100'})
    ET.SubElement(channel, 'arpandchords', {'arpdir': arpdir, 'chorddisabled': chorddisabled, 'arpdisabled': '0'})
    other = ET.SubElement(container, 'track', {'type': '2', 'name': 'S'})
    ET.SubElement(other, 'sampletrack', {'vol': volume})
    return px.HEADER + ET.tostring(root, encoding='unicode') + NL


def source(ctx, scenario, content):
    suffix = '.mmpz' if isinstance(content, bytes) else '.mmp'
    return ctx.project('src-' + scenario + suffix, content)


def body_projection(reply):
    assert reply['body'] and reply['body'].strip(), 'the action wrote no project XML'
    return project_projection(reply['body'])


def describe(data):
    '''What a written project file is: plain XML, a compressed project (length and zlib stream) or unreadable.'''
    if data[:5] == b'<?xml':
        return {'container': 'xml', 'project': project_projection(data.decode('utf-8'))}
    try:
        text = zlib.decompress(data[4:])
    except zlib.error:
        return {'container': 'unreadable', 'size': len(data)}
    declared = struct.unpack('>I', data[:4])[0]
    return {'container': 'compressed', 'length_matches': declared == len(text),
            'project': project_projection(text.decode('utf-8'))}


def rejected(reply):
    return {'exit_code': reply['exit_code'], 'blank': not (reply['body'] or '').strip(),
            'reported': bool(reply['output'].strip())}


def upgrade_point(suite, scenario, content, output, description, requires=()):
    def action(ctx):
        reply = ctx.cli('upgrade', source(ctx, scenario, content), output=output)
        return {'exit_code': reply['exit_code'],
                'files': {name: describe(data) for name, data in sorted(reply['files'].items())}}
    suite.add('project-file', scenario, 'result', action, description=description, requires=requires)


def build(suite):
    for version in VERSIONS:
        tag = version.replace('.', '-')

        def action(ctx, version=version, tag=tag):
            reply = ctx.cli('upgrade', source(ctx, 'v-' + tag, composite(version)))
            return {'version': version, 'exit_code': reply['exit_code'], 'project': body_projection(reply)}
        suite.add('upgrade', 'version-' + tag, 'result', action,
                  description=f'Upgrade a project saved by LMMS {version} to the current format')
    for label, arpdir, disabled, volume in OLD_FORMATS:
        def old_action(ctx, label=label, arpdir=arpdir, disabled=disabled, volume=volume):
            reply = ctx.cli('upgrade', source(ctx, 'old-' + label, old_format(arpdir, disabled, volume)))
            return {'exit_code': reply['exit_code'], 'project': body_projection(reply)}
        suite.add('upgrade', 'format-0-2-1-' + label, 'result', old_action,
                  description=f'Upgrade a project in the format of LMMS 0.2.1 ({label}) to the current format')

    def dump_compressed(ctx):
        reply = ctx.cli('dump', source(ctx, 'dump-compressed', px.mmpz(composite('1.2.2'))))
        return {'exit_code': reply['exit_code'], 'project': body_projection(reply)}
    suite.add('project-file', 'dump-compressed', 'result', dump_compressed, description='Dump a compressed project to XML')

    def dump_old(ctx):
        reply = ctx.cli('dump', source(ctx, 'dump-old-version', px.mmpz(composite('0.4.0'))))
        return {'exit_code': reply['exit_code'], 'project': body_projection(reply)}
    suite.add('project-file', 'dump-old-version', 'result', dump_old,
              description='Dump a compressed project of an old version: the XML is shown as saved, not upgraded')
    def dump_unreadable(ctx):
        inputs = (('plain-xml', source(ctx, 'dump-plain-xml', composite('1.2.2'))),
                  ('corrupt', source(ctx, 'dump-corrupt', bytes([0, 0, 0, 16]) + b'notzlibdata')),
                  ('empty', source(ctx, 'dump-empty', b'')),
                  ('missing', ctx.path('inputs', 'src-dump-missing.mmpz')))
        return {name: rejected(ctx.cli('dump', target)) for name, target in inputs}
    suite.add('project-file', 'dump-unreadable', 'result', dump_unreadable,
              description='Dump a plain XML project, a damaged file, an empty file and a missing file: none yields XML',
              requires=(DUMP_OK,))
    upgrade_point(suite, 'upgrade-to-compressed', px.mmpz(composite('1.2.0')), 'out-upgrade-to-compressed.mmpz',
                  'Upgrade a compressed project into a compressed project file')
    upgrade_point(suite, 'upgrade-to-xml', composite('1.2.0'), 'out-upgrade-to-xml.mmp',
                  'Upgrade a plain XML project into a plain XML project file')
    upgrade_point(suite, 'upgrade-compressed-to-xml', px.mmpz(composite('1.2.0')), 'out-upgrade-compressed-to-xml.mmp',
                  'Upgrade a compressed project into a plain XML project file')
    upgrade_point(suite, 'upgrade-xml-to-compressed', composite('1.2.0'), 'out-upgrade-xml-to-compressed.mmpz',
                  'Upgrade a plain XML project into a compressed project file')
    upgrade_point(suite, 'upgrade-corrupt-to-compressed', bytes([0, 0, 0, 16]) + b'notzlibdata',
                  'out-upgrade-corrupt-to-compressed.mmpz', 'Upgrade a damaged project file into a project file',
                  requires=(UPGRADE_OK,))
