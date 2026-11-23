'''Public setup and independent program checks for GUI checkpoints.

MuseScore Studio has no scripting channel, so a GUI checkpoint is checked through what its goal makes the application write: a saved project, an exported score or the window titles. Files are retrieved with list_files and download through the runtime and read with the projections of semantic.py; results are never shown to the evaluator agent.
'''
import io
import xml.etree.ElementTree as ET
import zipfile

import semantic


def setup(ctx, operations):
    for op in operations:
        raise ValueError('unknown setup operation ' + str(op.get('op')))


def score_root(data):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise AssertionError('the saved project is not a zip archive') from None
    with archive:
        members = [name for name in archive.namelist() if name.endswith('.mscx') and '/' not in name]
        assert len(members) == 1, 'a project holds exactly one score document'
        try:
            return ET.fromstring(archive.read(members[0]))
        except ET.ParseError:
            raise AssertionError('the score document is not well-formed XML') from None


def staff_notes(root):
    '''Per measure of the first staff: the chords as duration:pitches and the rests as rest:duration.'''
    staff = root.find('Score/Staff')
    assert staff is not None, 'the score has no staff'
    rows = []
    for measure in staff.findall('Measure'):
        cells = []
        for voice in measure.findall('voice'):
            for item in voice:
                if item.tag == 'Chord':
                    dots = int(item.findtext('dots') or 0)
                    pitches = sorted(int(note.findtext('pitch')) for note in item.findall('Note'))
                    cells.append('%s%s:%s' % (item.findtext('durationType') or '?', '.' * dots, ','.join(str(p) for p in pitches)))
                elif item.tag == 'Rest':
                    cells.append('rest:%s' % (item.findtext('durationType') or '?'))
        rows.append(cells)
    return rows


def words(node):
    return semantic.words_of(''.join(node.itertext())) if node is not None else ''


def mark(node):
    '''One notation mark of a staff as [kind, value]; None for nodes that are not marks.'''
    tag = node.tag
    if tag == 'Clef':
        return ['Clef', node.findtext('concertClefType') or '']
    if tag == 'KeySig':
        return ['KeySig', int(node.findtext('concertKey') or 0)]
    if tag == 'TimeSig':
        return ['TimeSig', '%s/%s' % (node.findtext('sigN'), node.findtext('sigD'))]
    if tag in ('Dynamic', 'Articulation', 'Accidental', 'Marker', 'Fermata', 'Breath'):
        return [tag, node.findtext('subtype') or '']
    if tag == 'BarLine':
        return ['BarLine', node.findtext('subtype') or 'normal']
    if tag in ('Tempo', 'StaffText', 'SystemText', 'Lyrics', 'Harmony', 'Jump', 'Expression', 'RehearsalMark'):
        return [tag, words(node.find('text'))]
    if tag == 'Tuplet':
        return ['Tuplet', '%s/%s' % (node.findtext('actualNotes'), node.findtext('normalNotes'))]
    if tag == 'Spanner' and node.find(node.get('type', '')) is not None:
        return ['Spanner', node.get('type')]
    return None


def staff_marks(root, kinds):
    '''The marks of the given kinds in document order over every staff; repeat barlines are Measure attributes.'''
    out = []
    for staff in root.findall('Score/Staff'):
        for measure in staff.findall('Measure'):
            if 'Repeat' in kinds:
                if measure.find('startRepeat') is not None:
                    out.append(['Repeat', 'start'])
                if measure.find('endRepeat') is not None:
                    out.append(['Repeat', 'end'])
            for node in measure.iter():
                item = mark(node)
                if item is not None and item[0] in kinds:
                    out.append(item)
    return out


def score_style(data):
    '''The style values a project stores (score_style.mss beside the score document).'''
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        with archive:
            names = [name for name in archive.namelist() if name.endswith('.mss') and '/' not in name]
            raw = archive.read(names[0]) if names else b''
    except zipfile.BadZipFile:
        raise AssertionError('the saved project is not a zip archive') from None
    if not raw:
        return {}
    try:
        style = ET.fromstring(raw).find('Style')
    except ET.ParseError:
        raise AssertionError('the style document is not well-formed XML') from None
    return {child.tag: semantic.words_of(child.text) for child in style} if style is not None else {}


def score_file(ctx, check):
    '''A project the goal saved: notes, signatures, tempos, marks of named kinds, style values, parts and metadata tags,
    each only when the check asks for it.'''
    data = ctx.fetch(check['path'])
    root = score_root(data)
    fields = check.get('fields', ['notes'])
    result = {}
    if 'notes' in fields:
        result['notes'] = staff_notes(root)
    if 'keys' in fields:
        result['keys'] = [int(node.findtext('concertKey') or 0) for node in root.iter('KeySig')]
    if 'times' in fields:
        result['times'] = [[int(node.findtext('sigN')), int(node.findtext('sigD'))] for node in root.iter('TimeSig')]
    if 'tempos' in fields:
        result['tempos'] = [[round(float(node.findtext('tempo')), 3),
                             semantic.words_of(''.join(node.find('text').itertext())) if node.find('text') is not None else '']
                            for node in root.iter('Tempo')]
    if 'marks' in fields:
        result['marks'] = staff_marks(root, check.get('marks', []))
    if 'style' in fields:
        style = score_style(data)
        result['style'] = {name: style.get(name, '') for name in check.get('style', [])}
    if 'parts' in fields:
        result['parts'] = [semantic.words_of(part.findtext('trackName')) for part in root.findall('Score/Part')]
    if 'tags' in fields:
        found = {tag.get('name'): semantic.words_of(tag.text) for tag in root.iter('metaTag')}
        result['tags'] = {name: found.get(name, '') for name in check.get('tags', [])}
    for key, value in check.get('expect', {}).items():
        assert result[key] == value, '%s is %r, expected %r' % (key, result[key], value)
    return result


def file_project(ctx, check):
    '''A score the goal exported: the projection of its format.'''
    name = check['path'].rsplit('/', 1)[-1]
    return {'project': ctx.project(name, ctx.fetch(check['path']))}


def file_exists(ctx, check):
    assert len(ctx.fetch(check['path'])) > 0, check['path'] + ' is empty'
    return {'written': True}


def window_title(ctx, check):
    titles = sorted(title for title in ctx.window_titles() if title)
    assert titles == sorted(check['titles']), 'the window titles are %r' % titles
    return {'titles': titles}


OBSERVERS = {'score-file': score_file, 'file-project': file_project, 'file-exists': file_exists,
             'window-title': window_title}


def observe(ctx, episode, checkpoint, check):
    return {'kind': check['kind'], **OBSERVERS[check['kind']](ctx, check)}
