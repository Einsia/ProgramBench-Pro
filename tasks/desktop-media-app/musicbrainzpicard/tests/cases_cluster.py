"""Clustering (CLUSTER): which loaded files are grouped together, and the title and artist a cluster gets.

Each scenario loads files whose album, album artist and artist tags (or folder names) differ in one respect,
clusters them, quits and reads the saved session. Two points per scenario: the grouping (which files share a
cluster, which stay unclustered) and the cluster names (title and artist). Every case has a strict majority, so
the result does not depend on the order in which files finished loading.
"""
from scenario import flac, items, m4a, mp3, needs, ogg, prepare, run_commands

FAMILY = 'clustering'
MAKERS = {'flac': flac, 'mp3': mp3, 'ogg': ogg, 'm4a': m4a}


def grouping(ctx, session):
    """Files that share a cluster, as sets of paths; unclustered files separately."""
    groups, loose = {}, []
    for row in items(ctx, session):
        if row['location'] == 'cluster':
            groups.setdefault(tuple(row['cluster']), []).append(row['path'])
        else:
            loose.append(row['path'])
    return {'groups': sorted(sorted(paths) for paths in groups.values()), 'unclustered': sorted(loose)}


def names(ctx, session):
    """The title and artist of the cluster each clustered file is in."""
    return {'clusters': {row['path']: row['cluster'] for row in items(ctx, session) if row['location'] == 'cluster'}}


def add(suite, key, description, files, settings=None, commands=None):
    documents = []
    for index, (folder, kind, title, tags) in enumerate(files):
        documents.append((folder, f'{index+1:02d}-{kind}.{ "m4a" if kind == "m4a" else kind}', MAKERS[kind](title, **tags)))
    suite.add(FAMILY, key, 'prepare', prepare(key, settings, documents), channel='setup',
              description='Fresh instance, settings profile and documents for '+key)
    steps = commands or [('LOAD', '{base}'), ('CLUSTER', '')]
    observed = {}

    def first(ctx):
        session = run_commands(key, steps, lambda c, s: s)(ctx)
        observed[key] = session
        return grouping(ctx, session)

    def second(ctx):
        if key not in observed:
            from harness import MissingDependency
            raise MissingDependency('the clustering step of '+key+' did not complete')
        return names(ctx, observed[key])
    suite.add(FAMILY, key, 'grouping', first, description=description+' (grouping)', needs=needs(key))
    suite.add(FAMILY, key, 'names', second, description=description+' (cluster title and artist)',
              needs=needs(key))


def album(name, artist=None, albumartist=None, **more):
    tags = {'album': name}
    if artist:
        tags['artist'] = artist
    if albumartist:
        tags['albumartist'] = albumartist
    tags.update(more)
    return tags


def build(suite):
    add(suite, 'same-album', 'Files with the same album and album artist form one cluster', [
        ('', 'flac', 'A1', album('Night Drive', albumartist='Lumen')),
        ('', 'mp3', 'A2', album('Night Drive', albumartist='Lumen')),
        ('', 'ogg', 'A3', album('Night Drive', albumartist='Lumen'))])
    add(suite, 'album-spelling', 'Album names that differ only in case, spaces and punctuation are one cluster, '
        'titled with the most frequent spelling', [
            ('', 'flac', 'B1', album('Abbey Road', albumartist='Quartet')),
            ('', 'mp3', 'B2', album('abbey road', albumartist='Quartet')),
            ('', 'ogg', 'B3', album('Abbey-Road!', albumartist='Quartet')),
            ('', 'flac', 'B4', album('abbey road', albumartist='Quartet')),
            ('', 'mp3', 'B5', album('abbey road', albumartist='Quartet'))])
    add(suite, 'two-albums', 'Different albums form separate clusters', [
        ('', 'flac', 'C1', album('First Light', albumartist='Dawn')),
        ('', 'mp3', 'C2', album('First Light', albumartist='Dawn')),
        ('', 'ogg', 'C3', album('Last Light', albumartist='Dusk')),
        ('', 'flac', 'C4', album('Last Light', albumartist='Dusk'))])
    add(suite, 'single-file-album', 'An album with a single file is not clustered', [
        ('', 'flac', 'D1', album('Pair', albumartist='Duo')),
        ('', 'mp3', 'D2', album('Pair', albumartist='Duo')),
        ('', 'ogg', 'D3', album('Solo', albumartist='One'))])
    add(suite, 'album-artist-preferred', 'The album artist names the cluster rather than the track artists', [
        ('', 'flac', 'E1', album('Split', artist='Guest One', albumartist='Host')),
        ('', 'mp3', 'E2', album('Split', artist='Guest Two', albumartist='Host')),
        ('', 'ogg', 'E3', album('Split', artist='Guest Two', albumartist='Host'))])
    add(suite, 'artist-fallback', 'Without album artists, the most frequent track artist names the cluster', [
        ('', 'flac', 'F1', album('Covers', artist='Singer A')),
        ('', 'mp3', 'F2', album('Covers', artist='Singer B')),
        ('', 'ogg', 'F3', album('Covers', artist='Singer B'))])
    add(suite, 'no-artist', 'A cluster without any artist is attributed to Various Artists', [
        ('', 'flac', 'G1', album('Nameless')), ('', 'mp3', 'G2', album('Nameless'))])
    add(suite, 'custom-various-name', 'The "Various Artists" name setting names clusters without artists', [
        ('', 'flac', 'H1', album('Sampler')), ('', 'ogg', 'H2', album('Sampler'))], settings={'va_name': 'V.A.'})
    add(suite, 'artist-spelling', 'Artist names that differ in case count together; the most frequent exact '
        'spelling of that group names the cluster', [
            ('', 'flac', 'I1', album('Echoes', albumartist='the band')),
            ('', 'mp3', 'I2', album('Echoes', albumartist='The Band')),
            ('', 'ogg', 'I3', album('Echoes', albumartist='The Band')),
            ('', 'flac', 'I4', album('Echoes', albumartist='Other Group'))])
    add(suite, 'folder-album', 'Files without an album tag are grouped by folder: the folder names the album and '
        'its parent folder the artist', [
            ('Painter/Colours', 'flac', 'J1', {}), ('Painter/Colours', 'mp3', 'J2', {}),
            ('Painter/Shapes', 'ogg', 'J3', {}), ('Painter/Shapes', 'flac', 'J4', {})])
    add(suite, 'folder-artist-dash-album', 'A folder named "Artist - Album" gives both names', [
        ('Misc/Choir - Hymns', 'flac', 'K1', {}), ('Misc/Choir - Hymns', 'mp3', 'K2', {}),
        ('Misc/Choir - Hymns', 'ogg', 'K3', {})])
    add(suite, 'folder-disc-subfolders', 'Disc subfolders (CD 1, Disc 2) are skipped when the folder names the '
        'album', [
            ('Pianist/Nocturnes/CD 1', 'flac', 'L1', {}), ('Pianist/Nocturnes/CD 1', 'mp3', 'L2', {}),
            ('Pianist/Nocturnes/Disc 2', 'ogg', 'L3', {}), ('Pianist/Nocturnes/Disc 2', 'flac', 'L4', {})])
    add(suite, 'folder-keeps-tag-artist', 'With an artist tag but no album tag, the folder names the album and the '
        'tag names the artist', [
            ('Somebody/Rarities', 'flac', 'M1', {'artist': 'Real Artist'}),
            ('Somebody/Rarities', 'mp3', 'M2', {'artist': 'Real Artist'})])
    add(suite, 'punctuation-only-albums', 'Album names made only of punctuation are compared without spaces', [
        ('', 'flac', 'N1', album('! ! !', albumartist='Shout')), ('', 'mp3', 'N2', album('!!!', albumartist='Shout')),
        ('', 'ogg', 'N3', album('! ! !', albumartist='Shout')),
        ('', 'ogg', 'N4', album('? ? ?', albumartist='Ask')), ('', 'flac', 'N5', album('???', albumartist='Ask')),
        ('', 'mp3', 'N6', album('???', albumartist='Ask'))])
    add(suite, 'accented-albums', 'Accented letters are part of the album name: Café and Cafe are different', [
        ('', 'flac', 'O1', album('Café', albumartist='Barista')), ('', 'mp3', 'O2', album('café', albumartist='Barista')),
        ('', 'ogg', 'O3', album('café', albumartist='Barista')),
        ('', 'ogg', 'O4', album('Cafe', albumartist='Barista')), ('', 'flac', 'O5', album('CAFE', albumartist='Barista')),
        ('', 'mp3', 'O6', album('Cafe', albumartist='Barista'))])
    add(suite, 'cjk-albums', 'Albums with CJK names cluster by exact name', [
        ('', 'flac', 'P1', album('夜の街', albumartist='東京バンド')), ('', 'mp3', 'P2', album('夜の街', albumartist='東京バンド')),
        ('', 'ogg', 'P3', album('朝の街', albumartist='東京バンド')), ('', 'flac', 'P4', album('朝の街', albumartist='東京バンド'))])
    add(suite, 'compilation-majority', 'One album with different album artists clusters once under the most '
        'frequent album artist', [
            ('', 'flac', 'Q1', album('Mixtape', albumartist='DJ One')),
            ('', 'mp3', 'Q2', album('Mixtape', albumartist='DJ Two')),
            ('', 'ogg', 'Q3', album('Mixtape', albumartist='DJ Two')),
            ('', 'm4a', 'Q4', album('Mixtape', albumartist='DJ Two'))])
    add(suite, 'cluster-twice', 'Clustering again keeps the clusters and adds nothing twice', [
        ('', 'flac', 'R1', album('Repeat', albumartist='Loop')), ('', 'mp3', 'R2', album('Repeat', albumartist='Loop'))],
        commands=[('LOAD', '{base}'), ('CLUSTER', ''), ('CLUSTER', '')])
    add(suite, 'cluster-joins-existing', 'Clustering again after more files are loaded keeps the existing cluster; a '
        'single later file of the same album does not join it and stays unclustered', [
        ('first', 'flac', 'S1', album('Grow', albumartist='Seed')), ('first', 'mp3', 'S2', album('Grow', albumartist='Seed')),
        ('later', 'ogg', 'S3', album('Grow', albumartist='Seed')), ('later', 'flac', 'S4', album('Other', albumartist='Weed'))],
        commands=[('LOAD', '{base}/first'), ('CLUSTER', ''), ('LOAD', '{base}/later'), ('CLUSTER', '')])
    add(suite, 'whitespace-album', 'An album tag of only spaces does not form a cluster', [
        ('', 'flac', 'T1', album('   ', albumartist='Blank')), ('', 'mp3', 'T2', album('   ', albumartist='Blank')),
        ('', 'ogg', 'T3', album('Real', albumartist='Blank')), ('', 'flac', 'T4', album('Real', albumartist='Blank'))])
    add(suite, 'large-majority', 'A larger album with three spellings takes the most frequent one', [
        ('', 'flac', 'U1', album('Grand Tour', albumartist='Traveller')),
        ('', 'mp3', 'U2', album('GRAND TOUR', albumartist='Traveller')),
        ('', 'ogg', 'U3', album('Grand Tour', albumartist='Traveller')),
        ('', 'm4a', 'U4', album('Grand  Tour', albumartist='Traveller')),
        ('', 'flac', 'U5', album('Grand Tour', albumartist='Traveller')),
        ('', 'mp3', 'U6', album('GRAND TOUR', albumartist='Traveller'))])
    return suite
