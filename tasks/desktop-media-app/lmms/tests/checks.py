'''Independent program checks for GUI checkpoints.

LMMS has no scripting pipe, so a GUI checkpoint is checked only through what the GUI wrote into the runtime owned
areas (fetched with list_files and download) and through the settings file: a file that exists, exported audio decoded
by the verifier FFmpeg, a saved project file read as XML and the settings of the application. Every check declares what
it reads; the results are never shown to the evaluator agent.
'''
import xml.etree.ElementTree as ET
import zlib

from harness import normalize, number, signal_projection
from semantic import decode_audio


def parse(text, what):
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise AssertionError(what + ' is not XML: ' + str(exc)[:200]) from None


def file_exists(ctx, check):
    path = ctx.fetch(check['path'])
    assert path.stat().st_size != 0, check['path'] + ' is empty'
    return {'file': check['path'], 'written': True}


def file_audio(ctx, check):
    '''Exported audio, decoded by the verifier FFmpeg; the tolerance class and the frame slack are declared per check.'''
    path = ctx.fetch(check['path'])
    audio = decode_audio(path)
    ctx.audit_artifact(path, audio)
    assert audio.frames != 0, check['path'] + ' holds no audio'
    for key, wanted in (check.get('format') or {}).items():
        actual = {'container': audio.container, 'codec': audio.codec}[key]
        assert wanted in actual.split(','), 'exported ' + key + ' ' + actual + ' is not ' + wanted
    if check.get('trim_start'):
        assert audio.frames > check['trim_start'], 'export is shorter than its lead-in'
        audio = audio.slice(check['trim_start'], audio.frames)
    return {'file': check['path'], 'tol': check.get('tol', 'signal'), 'slack': check.get('slack', 0),
            'signal': signal_projection(audio)}


def file_midi(ctx, check):
    from midi_semantics import project
    return {'file': check['path'], **project(ctx.fetch(check['path']).read_bytes())}


def project_xml(data):
    '''The XML of a saved project: a compressed project (big-endian length, then a zlib stream) or plain text.'''
    try:
        return zlib.decompress(data[4:]).decode('utf-8')
    except zlib.error:
        return data.decode('utf-8')


def element(node, tokens, shallow):
    '''A normalized element; a shallow one keeps its own attributes only (the settings of an instrument inside a track
    are not part of the check).'''
    value = normalize(node, tokens)
    return {key: item for key, item in value.items() if key != 'children'} if shallow else value


def project_file(ctx, check):
    '''Elements of a saved project chosen by an xpath, normalized: ids and window geometry are dropped and document
    folders become tokens. The xpath is required so that the version and creator attributes never enter the check.'''
    path = ctx.fetch(check['path'])
    root = parse(project_xml(path.read_bytes()), 'the saved project')
    tokens = {'[' + name + ']': folder for name, folder in ctx.areas().items()}
    found = root.findall(check['xpath'])
    assert found, 'the saved project has no element ' + check['xpath']
    values = [element(node, tokens, check.get('shallow', False)) for node in found]
    if 'fields' in check:
        for node, value in zip(found, values):
            attrs = value['attrs']
            for key in check['fields']:
                child = node.find(key)
                if key not in attrs and child is not None and child.get('value') is not None:
                    attrs[key] = number(child.get('value'))
            assert all(key in attrs for key in check['fields']), 'saved project lacks a required behavior field'
            value['attrs'] = {key: attrs[key] for key in check['fields']}
            for key, (low, high) in check.get('ranges', {}).items():
                observed = value['attrs'].get(key)
                assert isinstance(observed, (int, float)) and low <= observed <= high, key + ' outside required range'
                value['attrs'][key] = {'within': [low, high]}
    return {'file': check['path'], 'xpath': check['xpath'], 'elements': values}


def settings(ctx, check):
    '''Attributes of one section of the settings file; only names without machine specific paths are meant.'''
    root = parse(ctx.settings(), 'the settings file')
    nodes = list(root.iter(check['section']))
    assert nodes, 'the settings have no section ' + check['section']
    return {'section': check['section'], 'values': {name: nodes[0].get(name) for name in check['names']}}


def project_notes(ctx, check):
    '''Track type and musical note data, omitting instrument presets and empty default tracks.'''
    root = parse(project_xml(ctx.fetch(check['path']).read_bytes()), 'the saved project')
    tracks = []
    for track in root.findall('.//track'):
        patterns = []
        for pattern in track.findall('./pattern'):
            notes = [[float(n.get(k, default)) for k, default in
                      [('pos', '0'), ('len', '0'), ('key', '0'), ('vol', '100'), ('pan', '0')]]
                     for n in pattern.findall('./note')]
            if notes:
                patterns.append({'pos': float(pattern.get('pos', '0')), 'notes': sorted(notes)})
        if patterns:
            tracks.append({'type': int(track.get('type', '0')), 'patterns': sorted(patterns, key=lambda p: p['pos'])})
    assert tracks, 'the imported project contains no notes'
    return {'file': check['path'], 'note_tracks': tracks}


OBSERVERS = {'file-exists': file_exists, 'file-audio': file_audio, 'file-midi': file_midi,
             'project-file': project_file, 'project-notes': project_notes, 'settings': settings}


def observe(ctx, episode, checkpoint, check):
    return {'kind': check['kind'], **OBSERVERS[check['kind']](ctx, check)}


import html
import re


def plain_text(markup):
    # The project notes are saved as Qt rich text: the text of the body without its tags.
    body = markup.split('</head>', 1)[-1]
    body = re.sub(r'<br */?>', chr(10), body)
    return html.unescape(re.sub(r'<[^>]*>', '', body)).strip()


def project_text(ctx, check):
    path = ctx.fetch(check['path'])
    root = parse(project_xml(path.read_bytes()), 'the saved project')
    found = root.findall(check['xpath'])
    assert found, 'the saved project has no element ' + check['xpath']
    return {'file': check['path'], 'xpath': check['xpath'], 'text': [plain_text(node.text or '') for node in found]}


OBSERVERS['project-text'] = project_text
