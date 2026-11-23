"""GUI episodes: loading, clustering, viewing and editing files, file names, options, scripts and sessions."""
from guispec import area_path, step, text_value, episode

SESSION_SETTINGS = {'session_folder_path': '{outputs}', 'file_save_warning': False,
                    'guess_tracknumber_and_title': False}


def vorbis(kind, title=None, pictures=(), **tags):
    fields = ([['TITLE', title]] if title else [])
    for key, value in tags.items():
        for item in value if isinstance(value, list) else [value]:
            fields.append([key.upper(), item])
    return {'audio': kind, 'tags': {'vorbis': {'fields': fields, 'pictures': [list(p) for p in pictures]}}}


def flac(title=None, **tags):
    return vorbis('flac', title, **tags)


def ogg(title=None, **tags):
    return vorbis('ogg', title, **tags)


ID3_NAMES = {'title': 'TIT2', 'artist': 'TPE1', 'album': 'TALB', 'albumartist': 'TPE2', 'tracknumber': 'TRCK',
             'discnumber': 'TPOS', 'date': 'TDRC', 'genre': 'TCON', 'comment': None}


def mp3(title=None, version=4, **tags):
    frames = [['TIT2', title]] if title else []
    for key, value in tags.items():
        if key == 'comment':
            frames.append(['COMM', 'eng', '', value])
        else:
            frames.append([ID3_NAMES[key], value])
    return {'audio': 'mp3', 'tags': {'id3': {'version': version, 'frames': frames}}}


def m4a(title=None, **tags):
    names = {'artist': '\xa9ART', 'album': '\xa9alb', 'albumartist': 'aART', 'date': '\xa9day'}
    atoms = {'\xa9nam': title} if title else {}
    atoms.update({names[key]: value for key, value in tags.items()})
    return {'audio': 'm4a', 'tags': {'mp4': {'atoms': atoms}}}


def dump(path, description, **extra):
    return {'kind': 'dump', 'path': path, 'description': description, **extra}


def located(title, description):
    return {'kind': 'located', 'title': title, 'description': description}


def session(under, description, tags=False):
    return {'kind': 'session', 'under': under, 'tags': tags, 'description': description}


def select(text, exact=True, modifiers=None):
    value = {'op': 'select', 'text': text, 'exact': exact}
    if modifiers:
        value['modifiers'] = modifiers
    return value


def loading():
    key = 'add-files-and-folders'
    return episode(key, 'loading', [
        step('add-file', 'Add the file '+area_path(key, 'inputs', 'load/a/one.flac')+' with the application\'s '
             'Add Files command.',
             'The file list shows the file titled First Song (artist Loader) under Unclustered Files.',
             [{'op': 'press', 'key': 'Control+o'}, {'op': 'wait-window', 'title': 'Select one or more files'},
              {'op': 'dialog', 'path': '{inputs}/load/a/one.flac'}, {'op': 'sleep', 'seconds': 2},
              select('First Song')],
             [session('load/a', 'The session the application saves on exit lists one.flac as an unclustered '
                      'file, and no other file of the folder.')]),
        step('add-folder', 'Add the folder '+area_path(key, 'inputs', 'load/b')+' with the application\'s Add Folder '
             'command.',
             'The file list shows the files titled Third Song and Fourth Song under Unclustered Files; the text '
             'document of the folder is not listed.',
             [{'op': 'press', 'key': 'Control+e'}, {'op': 'wait-window', 'title': 'Select a directory'},
              {'op': 'dialog', 'path': '{inputs}/load/b'}, {'op': 'sleep', 'seconds': 3},
              select('Third Song')],
             [session('load/b', 'The session the application saves on exit lists the audio files of the folder '
                      'and of its subfolder as unclustered files.')])],
        documents=[('load/a', 'one.flac', flac('First Song', artist='Loader', album='Load Album'),
                    'FLAC file titled First Song'),
                   ('load/a', 'two.mp3', mp3('Second Song', artist='Loader'), 'MP3 file titled Second Song'),
                   ('load/b', 'three.ogg', ogg('Third Song', artist='Loader'), 'Ogg Vorbis file titled Third Song'),
                   ('load/b/sub', 'four.m4a', m4a('Fourth Song', artist='Loader'),
                    'M4A file titled Fourth Song in a subfolder'),
                   ('load/b', 'notes.txt', {'text': 'Not an audio file.\n'}, 'a text document')],
        profile={'title': 'Loading', 'settings': SESSION_SETTINGS},
        start='an empty file list; the settings keep the session the application saves on exit in the output '
              'folder')


def clustering():
    key = 'cluster-files'
    coltrane = {'artist': 'John Coltrane', 'albumartist': 'John Coltrane', 'album': 'Blue Train'}
    miles = {'artist': 'Miles Davis', 'albumartist': 'Miles Davis', 'album': 'Kind of Blue'}
    return episode(key, 'clustering', [
        step('cluster', 'Cluster the files listed under Unclustered Files.',
             'The Clusters node holds a cluster Blue Train (John Coltrane) with three files and a cluster Kind of '
             'Blue (Miles Davis) with two files; Untitled Demo remains under Unclustered Files.',
             [select('Unclustered Files', exact=False), {'op': 'press', 'key': 'Control+u'},
              {'op': 'sleep', 'seconds': 2}, select('Clusters', exact=False)]),
        step('edit-cluster', 'Select the cluster Kind of Blue, change its Album to '+text_value('Kind of Blue '
             '(Legacy Edition)')+' and save the files of the cluster; then expand the cluster and select its file So '
             'What.',
             'The cluster is listed as Kind of Blue (Legacy Edition) with its files So What and Freddie Freeloader; '
             'So What is saved (not marked as changed) and its metadata view shows Album Kind of Blue (Legacy '
             'Edition).',
             [select('Kind of Blue', exact=False), {'op': 'edit-tag', 'tag': 'Album',
                                                    'value': 'Kind of Blue (Legacy Edition)'},
              {'op': 'save'}, select('Kind of Blue (Legacy Edition) (2)'), {'op': 'press', 'key': 'Right'},
              {'op': 'sleep', 'seconds': .5}, select('So What')],
             [dump('inputs/clu/b1.flac', 'So What has the album of its edited cluster.'),
              dump('inputs/clu/b2.flac', 'Freddie Freeloader has the album of its edited cluster.')],
             preparation=[{'op': 'command', 'name': 'CLUSTER'}]),
        step('move-file', 'Move the file Lazy Bird from the cluster Blue Train into the cluster Kind of Blue '
             '(Legacy Edition).',
             'Lazy Bird is listed in the cluster Kind of Blue (Legacy Edition), which now has three files; Blue '
             'Train keeps two files.',
             [select('Blue Train', exact=False), {'op': 'press', 'key': 'Right'}, {'op': 'sleep', 'seconds': .5},
              select('Lazy Bird'), {'op': 'press', 'key': 'Control+x'},
              select('Kind of Blue (Legacy Edition)', exact=False), {'op': 'press', 'key': 'Control+v'},
              {'op': 'sleep', 'seconds': 1}, select('Kind of Blue (Legacy Edition)', exact=False),
              {'op': 'press', 'key': 'Right'}, {'op': 'sleep', 'seconds': .5}],
             [session('clu', 'The session the application saves on exit lists every file of the folder in its '
                      'cluster (or unclustered), with Lazy Bird in the cluster Kind of Blue (Legacy Edition).')],
             depends=['edit-cluster'], preparation=[{'op': 'command', 'name': 'CLUSTER'}])],
        documents=[('clu', 'a1.flac', flac('Moment\'s Notice', tracknumber='2', **coltrane), None),
                   ('clu', 'a2.mp3', mp3('Locomotion', tracknumber='3', **coltrane), None),
                   ('clu', 'a3.ogg', ogg('Lazy Bird', tracknumber='4', **coltrane), None),
                   ('clu', 'b1.flac', flac('So What', tracknumber='1', **miles), None),
                   ('clu', 'b2.flac', flac('Freddie Freeloader', tracknumber='2', **miles), None),
                   ('clu', 'c1.flac', flac('Untitled Demo', artist='Nobody'), None)],
        profile={'title': 'Clustering', 'settings': SESSION_SETTINGS}, load=['clu'],
        start='six files loaded from '+area_path(key, 'inputs', 'clu')+': three of the album Blue Train by John '
              'Coltrane (Moment\'s Notice, Locomotion, Lazy Bird), two of the album Kind of Blue by Miles Davis (So '
              'What, Freddie Freeloader) and Untitled Demo without an album')


def viewing():
    key = 'browse-metadata'
    trio = {'album': 'Trio Album', 'albumartist': 'The Trio'}
    return episode(key, 'views', [
        step('show-tags', 'Select the file Solo Piece to show its tags and cover art.',
             'The metadata view lists Title Solo Piece, Artist Viewer, Album View Album, Date 2011-03-04, Genre with '
             'the two values Jazz and Fusion, and Comment Seen in the view; the cover art area shows the file\'s '
             'embedded front cover picture.',
             [select('Solo Piece')]),
        step('multi-select', 'Select the three files Trio One, Trio Two and Trio Three together.',
             'The metadata view shows Album Trio Album as the common value of the selection and marks Title and '
             'Artist as different across the three files instead of showing one value.',
             [select('Trio One'), select('Trio Two', modifiers=['Control']), select('Trio Three', modifiers=['Control'])]),
        step('filter', 'Use the application\'s item filter to show only the items whose tags contain the text '
             + text_value('Trio')+'.',
             'A filter field holds Trio and the file list shows the three Trio files but no longer Solo Piece.',
             [{'op': 'press', 'key': 'Control+Shift+f'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'type', 'value': 'Trio'}, {'op': 'sleep', 'seconds': 1.5}]),
        step('info', 'Open the Info dialog of the file Solo Piece.',
             'A dialog shows the file\'s information: the file name solo.flac with its folder, the format FLAC, a '
             'length of 1 second, a sample rate of 44100 Hz and 1 channel.',
             [{'op': 'press', 'key': 'Escape'}, {'op': 'press', 'key': 'Control+Shift+f'},
              {'op': 'sleep', 'seconds': .5}, select('Solo Piece'), {'op': 'press', 'key': 'Control+i'},
              {'op': 'sleep', 'seconds': 1.5}]),
        step('artwork', 'Show the artwork of the file Solo Piece in its Info dialog.',
             'The Info dialog shows the file\'s artwork: one existing cover of type Front, the red and blue picture, '
             'with its size 388 B, 64 x 64 pixels and the type image/jpeg.',
             [{'op': 'click', 'target': {'role': 'page tab', 'name': 'Artwork'}}, {'op': 'sleep', 'seconds': 1}]),
        step('custom-column', 'Close the Info dialog. Add a custom column titled '+text_value('Album Caps')+' to the '
             'file list whose expression is '+text_value('$upper(%album%)')+' (Manage custom columns, in the menu of '
             'the file list\'s column headers).',
             'The file list has a column Album Caps that shows VIEW ALBUM for Solo Piece and TRIO ALBUM for the three '
             'Trio files.',
             [{'op': 'close-windows'}, {'op': 'context', 'target': {'role': 'table column header', 'name': 'Title',
                                                                    'nth': 1}, 'keys': ['Up', 'Up', 'Return']},
              {'op': 'wait-window', 'title': 'Manage Custom Columns'}, {'op': 'button', 'name': 'New'},
              {'op': 'set-text', 'target': {'role': 'text', 'name': 'Column Title*'}, 'value': 'Album Caps'},
              {'op': 'set-text', 'target': {'role': 'text', 'name': 'Expression*'}, 'value': '$upper(%album%)'},
              {'op': 'click', 'target': {'role': 'text', 'name': 'Column Title*'}}, {'op': 'button', 'name': 'OK'},
              {'op': 'sleep', 'seconds': 1}]),
        step('columns', 'Show the column Album in the file list (menu of the file list\'s column headers, Album Items) '
             'and sort the file list by its Artist column in ascending order.',
             'The file list has a column Album that shows Trio Album for the three Trio files and View Album for Solo '
             'Piece, and the files are listed by artist: Trio One (Ann Trio), Trio Two (Bob Trio), Trio Three (Cat '
             'Trio), Solo Piece (Viewer).',
             [{'op': 'context', 'target': {'role': 'table column header', 'name': 'Title', 'nth': 1},
               'keys': ['Down', 'Right', 'Down', 'Return', 'Escape', 'Escape']},
              {'op': 'click', 'target': {'role': 'table column header', 'name': 'Artist', 'nth': 1}, 'pause': 1}])],
        documents=[('view', 'solo.flac', vorbis('flac', 'Solo Piece', pictures=[(3, '', 'front.jpg')],
                                               artist='Viewer', album='View Album', date='2011-03-04',
                                               genre=['Jazz', 'Fusion'], comment='Seen in the view'), None),
                   ('view', 'trio1.mp3', mp3('Trio One', artist='Ann Trio', **trio), None),
                   ('view', 'trio2.flac', flac('Trio Two', artist='Bob Trio', **trio), None),
                   ('view', 'trio3.ogg', ogg('Trio Three', artist='Cat Trio', **trio), None)],
        load=['view'],
        start='four files loaded from '+area_path(key, 'inputs', 'view')+': Solo Piece (with an embedded front '
              'cover) and the three files Trio One, Trio Two and Trio Three of the album Trio Album')


def editing():
    key = 'edit-tags'
    return episode(key, 'editing', [
        step('title', 'Change the Title of the file "Original Title" to '+text_value('Grüße aus Köln')+' and save '
             'the file.',
             'The file is saved (not marked as changed) and its metadata view shows Title Grüße aus Köln.',
             [select('Original Title'), {'op': 'edit-tag', 'tag': 'Title', 'value': 'Grüße aus Köln'},
              {'op': 'save'}, select('Grüße aus Köln')],
             [dump('inputs/edit/title.flac', 'The saved file has the new title and its other tags unchanged.')]),
        step('add-tag', 'Add a new tag Mood with the value '+text_value('Calm')+' to the file "Add Target" and save '
             'the file.',
             'The file is saved and its metadata view lists the tag Mood with the value Calm.',
             [select('Add Target'), {'op': 'add-tag', 'tag': 'mood', 'value': 'Calm'}, {'op': 'save'},
              select('Add Target')],
             [dump('inputs/edit/add.flac', 'The saved file has the new Mood tag and its other tags unchanged.')]),
        step('remove-tag', 'Remove the Comment tag of the file "Remove Target" and save the file.',
             'The file is saved and its metadata view no longer lists a Comment; Mood Gloomy is still there.',
             [select('Remove Target'), {'op': 'remove-tag', 'tag': 'Comment'}, {'op': 'save'},
              select('Remove Target')],
             [dump('inputs/edit/remove.flac', 'The saved file has no comment and its other tags unchanged.')]),
        step('multi-value', 'Add Blues as a second value to the Genre tag of the file "Multi Target" (Rock stays '
             'its first value; the tag then has two values) and save the file.',
             'The file is saved and its metadata view shows Genre with the two values Rock and Blues.',
             [select('Multi Target'), {'op': 'add-value', 'tag': 'Genre', 'value': 'Blues'}, {'op': 'save'},
              select('Multi Target')],
             [dump('inputs/edit/multi.flac', 'The saved file has the genres Rock and Blues as two values.')]),
        step('mp3', 'Change the Artist of the MP3 file "Mp3 Target" to '+text_value('Neuer Künstler')+' and its '
             'Track Number to 2, then save the file.',
             'The file is saved and its metadata view shows Artist Neuer Künstler and Track Number 2.',
             [select('Mp3 Target'), {'op': 'edit-tag', 'tag': 'Artist', 'value': 'Neuer Künstler'},
              {'op': 'edit-tag', 'tag': 'Track Number', 'value': '2'}, {'op': 'save'}, select('Mp3 Target')],
             [dump('inputs/edit/id3.mp3', 'The saved MP3 file has the new artist and track number (keeping its '
                   'total of tracks) and its other tags unchanged.')]),
        step('pending', 'Change the Album of the file "Pending Target" to '+text_value('After Edit')+' without '
             'saving the file.',
             'The metadata view of Pending Target shows Album with the original value Before Edit and the new value '
             'After Edit.',
             [select('Pending Target'), {'op': 'edit-tag', 'tag': 'Album', 'value': 'After Edit'}],
             [session('edit/pending.flac', 'The session the application saves on exit keeps the unsaved new album '
                      'of the file.', tags=True)])],
        documents=[('edit', 'title.flac', flac('Original Title', artist='Edit Artist', album='Edit Album',
                                               comment='Old comment', genre='Pop', date='2001'), None),
                   ('edit', 'add.flac', flac('Add Target', artist='Edit Artist'), None),
                   ('edit', 'remove.flac', flac('Remove Target', comment='Old comment', mood='Gloomy'), None),
                   ('edit', 'multi.flac', flac('Multi Target', genre='Rock'), None),
                   ('edit', 'id3.mp3', mp3('Mp3 Target', version=3, artist='Old Artist', tracknumber='1/9',
                                           album='Edit Album'), None),
                   ('edit', 'pending.flac', flac('Pending Target', album='Before Edit'), None)],
        profile={'title': 'Editing', 'settings': SESSION_SETTINGS}, load=['edit'],
        start='six files loaded from '+area_path(key, 'inputs', 'edit')+', titled Original Title, Add Target, '
              'Remove Target, Multi Target, Mp3 Target and Pending Target')


def multi_editing():
    key = 'edit-several-files'
    return episode(key, 'editing', [
        step('edit-all', 'Select the three files Song M1, Song M2 and Song M3 and change their Album to '
             + text_value('Right Album')+' in one edit; then save the three files and select the three of them '
             'again.',
             'The three files are saved (none is marked as changed) and, with the three selected, the metadata view '
             'shows Album Right Album as their common value.',
             [select('Song M1'), select('Song M2', modifiers=['Control']), select('Song M3', modifiers=['Control']),
              {'op': 'edit-tag', 'tag': 'Album', 'value': 'Right Album'}, {'op': 'save'}, select('Song M1'),
              select('Song M2', modifiers=['Control']), select('Song M3', modifiers=['Control'])],
             [dump('inputs/multi/m1.flac', 'Song M1 has the new album.'),
              dump('inputs/multi/m2.mp3', 'Song M2 has the new album.'),
              dump('inputs/multi/m3.ogg', 'Song M3 has the new album.')]),
        step('copy-paste', 'Copy the Artist value of the file "Source Song" and paste it as the Artist of the file '
             '"Target Song" with the metadata view\'s copy and paste; then save "Target Song".',
             'Target Song is saved and shows Artist Copied Ärtist.',
             [select('Source Song'), {'op': 'copy-tag', 'tag': 'Artist'}, select('Target Song'),
              {'op': 'paste-tag', 'tag': 'Artist'}, {'op': 'save'}, select('Target Song')],
             [dump('inputs/multi/dst.flac', 'Target Song has the copied artist and its other tags unchanged.')]),
        step('revert', 'Change the Title of the file "Song M4" to '+text_value('Temporary')+'; then restore its '
             'original title with the metadata view\'s command for the original value (do not type the old title).',
             'The metadata view of the file shows Title Song M4 again without a pending change, and the file is '
             'not marked as changed.',
             [select('Song M4'), {'op': 'edit-tag', 'tag': 'Title', 'value': 'Temporary'},
              {'op': 'use-original', 'tag': 'Title'}, select('Song M4')])],
        documents=[('multi', 'm1.flac', flac('Song M1', artist='Multi A', album='Wrong Album'), None),
                   ('multi', 'm2.mp3', mp3('Song M2', artist='Multi B', album='Wrong Album'), None),
                   ('multi', 'm3.ogg', ogg('Song M3', artist='Multi C', album='Wrong Album'), None),
                   ('multi', 'm4.flac', flac('Song M4', artist='Multi D', album='Wrong Album'), None),
                   ('multi', 'src.flac', flac('Source Song', artist='Copied Ärtist'), None),
                   ('multi', 'dst.flac', flac('Target Song', artist='Placeholder', album='Paste Album'), None)],
        profile={'title': 'Editing', 'settings': SESSION_SETTINGS}, load=['multi'],
        start='six files loaded from '+area_path(key, 'inputs', 'multi')+': Song M1 to Song M4 (album Wrong Album), '
              'Source Song (artist Copied Ärtist) and Target Song (artist Placeholder)')


def tags_from_file_names():
    key = 'tags-from-file-names'
    first = ['01 - First Track.flac', '02 - Second_Track.mp3', '10 - Encore_Piece.ogg']
    return episode(key, 'tags-from-file-names', [
        step('folders', 'Select the three files of the folder '+area_path(key, 'inputs', 'tff')+' (in its subfolders '
             'Artist One/Album One and Artist Two/Live Set) and set their tags from their file names with the format '
             + text_value('%artist%/%album%/%tracknumber% - %title%')+', replacing underscores with spaces; then '
             'save the three files.',
             'The three files are saved; for example the file 02 - Second_Track.mp3 now shows Title Second Track, '
             'Artist Artist One, Album Album One and Track Number 2.',
             [select('01 - First Track.flac'), select('02 - Second_Track.mp3', modifiers=['Control']),
              select('10 - Encore_Piece.ogg', modifiers=['Control']),
              {'op': 'tags-from-names', 'format': '%artist%/%album%/%tracknumber% - %title%', 'underscores': True},
              {'op': 'save'}, select('Second Track')],
             [dump('inputs/tff/Artist One/Album One/'+first[0], 'Tags parsed from the path of '+first[0]+'.'),
              dump('inputs/tff/Artist One/Album One/'+first[1], 'Tags parsed from the path of '+first[1]+'.'),
              dump('inputs/tff/Artist Two/Live Set/'+first[2], 'Tags parsed from the path of '+first[2]+'.')]),
        step('pattern', 'Select the two files of the folder '+area_path(key, 'inputs', 'tff2')+' and set their tags '
             'from their file names with the format '+text_value('%date%_%title%_-_%tracknumber%')+', replacing '
             'underscores with spaces; then save the two files.',
             'The two files are saved; the file 1999-07-04_Night_Show_-_05.flac now shows Title Night Show, Date '
             '1999-07-04 and Track Number 5.',
             [select('1999-07-04_Night_Show_-_05.flac'), select('2003_Morning_Song_-_11.flac', modifiers=['Control']),
              {'op': 'tags-from-names', 'format': '%date%_%title%_-_%tracknumber%', 'underscores': True},
              {'op': 'save'}, select('Night Show')],
             [dump('inputs/tff2/1999-07-04_Night_Show_-_05.flac', 'Date, title and track number parsed from the '
                   'file name.'),
              dump('inputs/tff2/2003_Morning_Song_-_11.flac', 'Year, title and track number parsed from the file '
                   'name.')])],
        documents=[('tff/Artist One/Album One', first[0], {'audio': 'flac', 'tags': {}}, None),
                   ('tff/Artist One/Album One', first[1], {'audio': 'mp3', 'tags': {}}, None),
                   ('tff/Artist Two/Live Set', first[2], {'audio': 'ogg', 'tags': {}}, None),
                   ('tff2', '1999-07-04_Night_Show_-_05.flac', {'audio': 'flac', 'tags': {}}, None),
                   ('tff2', '2003_Morning_Song_-_11.flac', {'audio': 'flac', 'tags': {}}, None)],
        profile={'title': 'Parsing', 'settings': SESSION_SETTINGS}, load=['tff', 'tff2'],
        start='five files without tags loaded from '+area_path(key, 'inputs', 'tff')+' and '
              + area_path(key, 'inputs', 'tff2')+' (the file list shows their file names)')


def renaming():
    key = 'rename-and-move'
    band = {'albumartist': 'Band', 'artist': 'Band'}
    titles = ['Intro', 'AC/DC Cover', 'Guest Song', 'Encore', 'Lonely Track']
    checks = lambda what: [located(t, f'{t}: saved under the name {what}.') for t in titles]
    return episode(key, 'file-naming', [
        step('enable', 'In the options, turn on renaming files and moving them into the folder '
             + area_path(key, 'outputs', 'library')+' when saving (keep the default file naming script); then save '
             'all loaded files.',
             'The files are saved: none is marked as changed, and the metadata view of Intro shows a File Path in '
             + area_path(key, 'outputs', 'library')+'.',
             [{'op': 'options', 'page': 'File Naming'}, {'op': 'set-check', 'name': 'Move files when saving'},
              {'op': 'set-text', 'target': {'role': 'text', 'name': 'Destination directory:'},
               'value': '{outputs}/library'},
              {'op': 'set-check', 'name': 'Rename files when saving'}, {'op': 'button', 'name': 'Make It So!'},
              select('Unclustered Files', exact=False), {'op': 'save'}, select('Intro')],
             checks('that the default script gives it')+[
                 {'kind': 'tree', 'area': 'inputs', 'description': 'The input folder the files left is removed once '
                  'it is empty (the default for empty folders).'}],
             requires={'state-6': ['state-1']}),
        step('preset', 'Make "Preset 2: [album artist]/[album]/[track #]. [title]" the active file naming script and '
             'save all loaded files again.',
             'The files are saved again: the metadata view of Intro shows its File Path in '
             + area_path(key, 'outputs', 'library/Band/Debut')+' with the name 1. Intro.flac.',
             [{'op': 'menu', 'path': ['Options', 'File naming scripts',
                                      'Preset 2: [album artist]/[album]/[track #]. [title]']},
              select('Unclustered Files', exact=False), {'op': 'save'}, select('Intro')],
             checks('that preset 2 gives it'), depends=['enable']),
        step('compat', 'In the file naming compatibility options, turn on replacing spaces with underscores; then '
             'save all loaded files again.',
             'The files are saved again: the metadata view of Intro shows the file name 1._Intro.flac.',
             [{'op': 'options', 'page': 'Compatibility'}, {'op': 'set-check', 'name': 'Replace spaces with underscores'},
              {'op': 'button', 'name': 'Make It So!'}, select('Unclustered Files', exact=False), {'op': 'save'},
              select('Intro')],
             checks('that preset 2 gives it with spaces replaced by underscores'), depends=['preset'])],
        documents=[('org', 'o1.flac', flac('Intro', album='Debut', tracknumber='1', totaltracks='10', date='2001',
                                           **band), None),
                   ('org', 'o2.mp3', mp3('AC/DC Cover', album='Debut', tracknumber='2/10', **band), None),
                   ('org', 'o3.ogg', ogg('Guest Song', albumartist='Various Artists', artist='Guest Star',
                                         album='Hits', tracknumber='5'), None),
                   ('org', 'o4.flac', flac('Encore', albumartist='Band', artist='Band', album='Live',
                                           discnumber='2', totaldiscs='2', tracknumber='3'), None),
                   ('org', 'o5.m4a', m4a('Lonely Track', artist='Solo Act'), None)],
        profile={'title': 'Renaming', 'settings': SESSION_SETTINGS}, load=['org'],
        start='five files loaded from '+area_path(key, 'inputs', 'org')+' (Intro, AC/DC Cover, Guest Song, Encore '
              'and Lonely Track); files are neither renamed nor moved when saving')


IMPORTED_NAMING = ("title: Upper album\nscript_language_version: '1.0'\n"
                   "script: '$upper(%album%)/%title% - $year(%date%)'\n")


def naming_editor():
    key = 'naming-script-editor'
    script = '$year(%date%)/%album%/$num(%tracknumber%,2) %title%'
    titles = ['First Light', 'Second Wind', 'Third Eye']
    return episode(key, 'naming-scripts', [
        step('new-script', 'In the file naming script editor, add a new script titled '+text_value('Year first')
             + ' whose text is exactly '+text_value(script)+', make it the active file naming script, then save all '
             'loaded files.',
             'The files are saved with names from the new script: the metadata view of First Light shows its File '
             'Path in '+area_path(key, 'outputs', 'nse/1999/Dawn')+' with the name 01 First Light.flac.',
             [{'op': 'press', 'key': 'Control+Shift+s'}, {'op': 'wait-window', 'title': 'File naming script editor'},
              {'op': 'click', 'target': {'role': 'menu item', 'name': 'Script', 'nth': 0}}, {'op': 'sleep', 'seconds': .5},
              {'op': 'click', 'target': {'role': 'menu item', 'name': 'Add a new script'}}, {'op': 'sleep', 'seconds': .5},
              {'op': 'click', 'target': {'role': 'menu item', 'name': 'Empty / blank script'}},
              {'op': 'sleep', 'seconds': 1}, {'op': 'naming-editor', 'title': 'Year first', 'script': script},
              {'op': 'button', 'name': 'Make It So!'}, {'op': 'wait-window', 'title': 'Activate script?'},
              {'op': 'button', 'name': 'Yes'}, {'op': 'sleep', 'seconds': 1},
              select('Unclustered Files', exact=False), {'op': 'save'}, select('First Light')],
             [located(t, f'{t}: saved under the name the new script gives it.') for t in titles]),
        step('import-script', 'In the file naming script editor, import the naming script package '
             + area_path(key, 'inputs', 'nse-scripts/upper-album.ptsp')+', make the imported script the active file '
             'naming script, then save all loaded files.',
             'The files are saved with names from the imported script: the metadata view of First Light shows its File '
             'Path in '+area_path(key, 'outputs', 'nse/DAWN')+' with the name First Light - 1999.flac.',
             [{'op': 'close-windows'}, {'op': 'press', 'key': 'Control+Shift+s'},
              {'op': 'wait-window', 'title': 'File naming script editor'},
              {'op': 'click', 'target': {'role': 'menu item', 'name': 'File', 'nth': 1}}, {'op': 'sleep', 'seconds': .5},
              {'op': 'click', 'target': {'role': 'menu item', 'name': 'Import a script file'}},
              {'op': 'wait-window', 'title': 'Import Script File'},
              {'op': 'dialog', 'path': '{inputs}/nse-scripts/upper-album.ptsp'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'button', 'name': 'Make It So!'}, {'op': 'wait-window', 'title': 'Activate script?'},
              {'op': 'button', 'name': 'Yes'}, {'op': 'sleep', 'seconds': 1},
              select('Unclustered Files', exact=False), {'op': 'save'}, select('First Light')],
             [located(t, f'{t}: saved under the name the imported script gives it.') for t in titles])],
        documents=[('nse-scripts', 'upper-album.ptsp', {'text': IMPORTED_NAMING},
                    'a file naming script package (YAML) titled Upper album'),
                   ('nse-in', 'n1.flac', flac('First Light', album='Dawn', date='1999-01-01', tracknumber='1'), None),
                   ('nse-in', 'n2.flac', flac('Second Wind', album='Dawn', date='1999-01-01', tracknumber='2'), None),
                   ('nse-in', 'n3.mp3', mp3('Third Eye', album='Dusk', date='2004-06-07', tracknumber='7'), None)],
        profile={'title': 'Naming editor', 'settings': {**SESSION_SETTINGS, 'rename_files': True, 'move_files': True,
                                                        'move_files_to': '{outputs}/nse'}},
        load=['nse-in'],
        start='three files loaded from '+area_path(key, 'inputs', 'nse-in')+' (First Light, Second Wind, Third Eye); '
              'the settings rename and move files to '+area_path(key, 'outputs', 'nse')+' with the default file '
              'naming script')


def tagger_script_options():
    key = 'tagger-script-options'
    script = '$set(album,$upper(%album%))'
    return episode(key, 'tagger-scripts', [
        step('add-and-run', 'In the options\' Scripting page, enable tagger scripts and add a new script titled '
             + text_value('Upper album')+' whose text is exactly '+text_value(script)+'; then run this script on all '
             'loaded files and save them.',
             'The files are saved and show their albums in upper case, for example Quiet Album becomes QUIET ALBUM.',
             [{'op': 'options', 'page': 'Scripting'}, {'op': 'set-check', 'name': 'Enable Tagger Script(s)'},
              {'op': 'tagger-script', 'title': 'Upper album', 'script': script},
              {'op': 'button', 'name': 'Make It So!'}, {'op': 'sleep', 'seconds': 1},
              select('Unclustered Files', exact=False), {'op': 'run-script', 'target': 'Unclustered Files'},
              {'op': 'save'}, select('Quiet One')],
             [dump('inputs/tso/t1.flac', 'The album of the FLAC file in upper case.'),
              dump('inputs/tso/t2.mp3', 'The album of the MP3 file in upper case.'),
              dump('inputs/tso/t3.ogg', 'The album of the Ogg file in upper case.')])],
        documents=[('tso', 't1.flac', flac('Quiet One', album='Quiet Album'), None),
                   ('tso', 't2.mp3', mp3('Loud Two', album='Loud Älbum'), None),
                   ('tso', 't3.ogg', ogg('Soft Three', album='soft album'), None)],
        profile={'title': 'Scripts', 'settings': SESSION_SETTINGS}, load=['tso'],
        start='three files loaded from '+area_path(key, 'inputs', 'tso')+' (Quiet One, Loud Two, Soft Three); there '
              'are no tagger scripts')


def id3_options():
    key = 'id3-options'
    return episode(key, 'tag-options', [
        step('v23', 'In the ID3 options, choose ID3v2.3 with UTF-16 text encoding and turn off including ID3v1 tags, '
             'apply the options and save all loaded files; finally open the ID3 options again to show the settings.',
             'The ID3 options show version 2.3, the UTF-16 text encoding and ID3v1 tags turned off.',
             [{'op': 'options', 'page': 'ID3'}, {'op': 'set-check', 'name': '2.3', 'role': 'radio button'},
              {'op': 'set-check', 'name': 'UTF-16', 'role': 'radio button'},
              {'op': 'set-check', 'name': 'Also include ID3v1 tags in the files', 'value': False},
              {'op': 'button', 'name': 'Make It So!'}, select('Unclustered Files', exact=False), {'op': 'save'},
              {'op': 'options', 'page': 'ID3'}],
             [dump('inputs/id3o/'+name, f'{name} saved as ID3v2.3 with UTF-16 text and without an ID3v1 tag.',
                   encodings=True) for name in ('dates.mp3', 'people.mp3', 'multi.mp3')])],
        documents=[('id3o', 'dates.mp3', {'audio': 'mp3', 'tags': {'id3': {'version': 4, 'v1': True, 'frames': [
                        ['TIT2', 'Dätes'], ['TDRC', '2004-05-06'], ['TDOR', '1999-02-03'], ['TDRL', '2005']]}}}, None),
                   ('id3o', 'people.mp3', {'audio': 'mp3', 'tags': {'id3': {'version': 4, 'v1': True, 'frames': [
                        ['TIT2', 'Peöple'], ['TMCL', [['piano', 'Pia P'], ['vocals', 'Voc V']]],
                        ['TIPL', [['producer', 'Pro P']]], ['TMOO', 'Mood M']]}}}, None),
                   ('id3o', 'multi.mp3', {'audio': 'mp3', 'tags': {'id3': {'version': 4, 'v1': True, 'frames': [
                        ['TIT2', 'Mülti'], ['TPE1', ['Art One', 'Art Two']], ['TCON', ['Rock', 'Pop']],
                        ['TSOP', 'One, Art']]}}}, None)],
        profile={'title': 'ID3', 'settings': SESSION_SETTINGS}, load=['id3o'],
        start='three MP3 files with ID3v2.4 and ID3v1 tags loaded from '+area_path(key, 'inputs', 'id3o')
              + ' (Dätes, Peöple, Mülti); the ID3 options are at their defaults (ID3v2.4, UTF-8, ID3v1 included)')


def build():
    return [loading(), clustering(), viewing(), editing(), multi_editing(), tags_from_file_names(), renaming(),
            naming_editor(), tagger_script_options(), id3_options()]
