"""Saving options: how the tag, cover image, file naming and loading settings change what saving and loading do.

Every checkpoint prepares its own settings (a profile imported with picard-cli, then a restart) and loads its own
folder; the goal is the plain user action (save, run a script and save, add a folder), and the checks read the files
the action wrote. Every profile names the same settings, so the latest one decides all of them. A small tagger script
("Stamp", which sets Encoded By) gives every save checkpoint a visible result; checkpoints whose settings show no
other result in the main window end on the options page that shows them. The checkpoints are grouped two per
episode.
"""
from guispec import area_path, step, episode

DEFAULTS = {
    'file_save_warning': False, 'guess_tracknumber_and_title': False, 'ignore_file_mbids': True,
    'session_folder_path': '{outputs}',
    'write_id3v23': False, 'id3v2_encoding': 'utf-8', 'id3v23_join_with': '/', 'write_id3v1': True,
    'itunes_compatible_grouping': False, 'remove_id3_from_flac': False, 'remove_ape_from_mp3': False,
    'write_wave_riff_info': True, 'remove_wave_riff_info': False, 'wave_riff_info_encoding': 'windows-1252',
    'aac_save_ape': True, 'remove_ape_from_aac': False, 'ac3_save_ape': True, 'remove_ape_from_ac3': False,
    'disable_date_sanitization_formats': [], 'clear_existing_tags': False, 'enable_tag_saving': True,
    'preserve_timestamps': False, 'fix_missing_seekpoints_flac': False,
    'save_images_to_tags': True, 'embed_only_one_front_image': True, 'save_images_to_files': False,
    'cover_image_filename': 'cover', 'save_images_overwrite': False, 'save_only_one_front_image': False,
    'image_type_as_filename': False, 'remove_images_from_tags': False,
    'rename_files': False, 'move_files': False, 'move_files_to': '{outputs}', 'move_additional_files': False,
    'move_additional_files_pattern': '*.jpg *.png', 'delete_empty_dirs': True, 'ascii_filenames': False,
    'windows_compatibility': True, 'replace_spaces_with_underscores': False, 'replace_dir_separator': '_',
    'ignore_hidden_files': False, 'ignore_regex': '', 'recursively_add_files': True,
}
STAMP = ('Stamp', '$set(encodedby,Stamped)')
STAMP_GOAL = 'Run the tagger script "Stamp" on all loaded files, then save them.'


def stamp_and_save(select):
    return [{'op': 'select', 'text': 'Unclustered Files'}, {'op': 'run-script', 'target': 'Unclustered Files'},
            {'op': 'save'}, {'op': 'select', 'text': select, 'exact': True}]


def stamp_then_page(select, page):
    """Goal and recipe of a save checkpoint that ends on the options page showing its settings."""
    return (STAMP_GOAL[:-1]+f'; then open the options on their {page} page.',
            stamp_and_save(select)+[{'op': 'options', 'page': page}])


def frames(*items, version=4, v1=False):
    return {'id3': {'version': version, 'v1': v1, 'frames': [list(i) for i in items]}}


def vorbis(*fields, pictures=()):
    return {'vorbis': {'fields': [list(f) for f in fields], 'pictures': [list(p) for p in pictures]}}


def ape(**items):
    return {'ape': {'items': {k.replace('_', ' '): v for k, v in items.items()}}}


def doc(folder, name, kind, *specs):
    tags = {}
    for spec in specs:
        tags.update(spec)
    return (folder, name, {'audio': kind, 'tags': tags}, None)


def dump(path, description, **extra):
    return {'kind': 'dump', 'path': path, 'description': description, **extra}


def profile(name, settings, naming=None, tagging=()):
    value = {'title': name, 'settings': {**DEFAULTS, **settings}}
    if naming:
        value['naming'] = {'title': name+' naming', 'script': naming}
    if tagging:
        value['tagging'] = [{'title': title, 'enabled': False, 'script': script} for title, script in tagging]
    return value


def prepared(folder, settings, naming=None, tagging=(STAMP,)):
    return [{'op': 'profile', 'profile': profile('Options '+folder, settings, naming, tagging)},
            {'op': 'load', 'paths': [folder]}]


def parts(key):
    """All input documents and all checkpoints, with document paths of the episode `key`."""
    documents = [
        doc('fo1', 'latin.mp3', 'mp3', frames(['TIT2', 'Café Crème'], ['TPE1', 'Łódź Artist'], ['TALB', 'Album À'],
                                               ['COMM', 'eng', '', 'Ünicode comment'], ['TIT1', 'Grouping G'],
                                               ['TXXX', 'WORK', 'Work W'], v1=True)),
        doc('fo1', 'flac-with-id3.flac', 'flac', frames(['TIT2', 'Old ID3 title']),
            vorbis(['TITLE', 'Flac With ID3'], ['ALBUM', 'Cleanup'])),
        doc('fo1', 'mp3-with-ape.mp3', 'mp3', frames(['TIT2', 'Mp3 With APE']), ape(Title='APE title', Artist='APE')),
        doc('fo1', 'wave.wav', 'wav', {'riff': [['INAM', 'Old Info Title'], ['ICMT', 'Old info comment'],
                                                 ['ISFT', 'Old Software']]},
            frames(['TIT2', 'Wave Tïtle'], ['TPE1', 'Wåve Artist'])),
        doc('fo1', 'noape.aac', 'aac', ape(Title='AAC title', Artist='AAC artist')),
        doc('fo1', 'keep.ac3', 'ac3', ape(Title='AC3 title', Artist='AC3 artist')),
        doc('fo1', 'date-kept.flac', 'flac', vorbis(['TITLE', 'Date Kept'], ['DATE', '2005-00-00'])),
        doc('fo1', 'date-cleaned.wv', 'wv', ape(Title='Date Cleaned', Year='2005-00-00')),
        ('fo1', 'seek-kept.flac', {'audio': 'flac', 'tags': {'vorbis': {'fields': [['TITLE', 'Seek Kept']],
                                                                       'empty_seektable': True}}}, None),
        doc('fo2', 'multi.mp3', 'mp3', frames(['TIT2', 'Mülti'], ['TPE1', ['Art One', 'Art Two']],
                                               ['TCON', ['Rock', 'Pop']], ['TCOM', ['Comp A', 'Comp B']],
                                               ['TDRC', '2004-05-06'], ['TDOR', '1999'])),
        doc('fo2', 'wave2.wav', 'wav', {'riff': [['INAM', 'Info Title Kept'], ['IART', 'Info Artist Kept']]},
            frames(['TIT2', 'Wave Two'])),
        doc('fo2', 'aac2.aac', 'aac', ape(Title='AAC two', Artist='AAC artist')),
        doc('fo2', 'ac32.ac3', 'ac3', ape(Title='AC3 two', Artist='AC3 artist')),
        doc('fo3', 't1.flac', 'flac', vorbis(['TITLE', 'Keep Tags One'], ['ALBUM', 'Original Album'])),
        doc('fo3', 't2.mp3', 'mp3', frames(['TIT2', 'Keep Tags Two'], ['TALB', 'Original Album'])),
        doc('fo4', 'c1.flac', 'flac', vorbis(['TITLE', 'Clear One'], ['MOOD', 'Moody'], ['ALBUM', 'Before'],
                                             ['MY_NOTE', 'note'])),
        doc('fo4', 'c2.mp3', 'mp3', frames(['TIT2', 'Clear Two'], ['TMOO', 'Moody'], ['TALB', 'Before'],
                                           ['TXXX', 'MY_NOTE', 'note'])),
        doc('fo5/album', 'i1.flac', 'flac', vorbis(['TITLE', 'Pictures One'], ['ALBUM', 'Pictures'],
                                                   pictures=[(3, 'Front', 'front.jpg'), (4, '', 'back.png')])),
        doc('fo6', 'i2.flac', 'flac', vorbis(['TITLE', 'Pictures Two'], pictures=[(4, '', 'back.png'),
                                                                                  (3, 'Front', 'front.jpg')])),
        doc('fo6', 'i3.mp3', 'mp3', frames(['TIT2', 'Pictures Three'], ['APIC', 4, '', 'back.png'],
                                           ['APIC', 3, 'Front', 'front.jpg'])),
        doc('fo7/src', 'p1.flac', 'flac', vorbis(['TITLE', 'Ünïcode: Name?'])),
        doc('fo7/src', 'p2.flac', 'flac', vorbis(['TITLE', 'AC/DC Song'])),
        ('fo7/src', 'cover.jpg', {'image': 'front.jpg'}, None),
        ('fo7/src', 'notes.txt', {'text': 'liner notes\n'}, None),
        ('fo7/src', 'keep.log', {'text': 'stays here\n'}, None),
        doc('fo8', '07. Guessed Title.flac', 'flac', {}),
        doc('fo8', '08 - Dash Title.flac', 'flac', {}),
        doc('fo8', 'Some Artist - 03 - Other Title.mp3', 'mp3', {}),
        doc('fo8', '12.ogg', 'ogg', {}),
        ('fo10', 'ts.flac', {'audio': 'flac', 'tags': {'vorbis': {'fields': [['TITLE', 'Time Kept']],
                                                                  'empty_seektable': True}}}, None),
        doc('fo10', 'ts.mp3', 'mp3', frames(['TIT2', 'Time Kept Too'])),
        doc('fo9', 'visible.flac', 'flac', vorbis(['TITLE', 'Visible'])),
        doc('fo9', '.hidden.flac', 'flac', vorbis(['TITLE', 'Hidden'])),
        doc('fo9/skip', 'skipped.flac', 'flac', vorbis(['TITLE', 'Skipped'])),
        doc('fo9/deeper', 'deeper.flac', 'flac', vorbis(['TITLE', 'Deeper'])),
    ]
    inputs = lambda path: area_path(key, 'inputs', path)
    outputs = lambda path: area_path(key, 'outputs', path)
    steps = [
        step('formats-1', stamp_then_page('Café Crème', 'ID3')[0],
             'The ID3 options page shows ID3v2 version 2.4 and the ISO-8859-1 text encoding selected, Save iTunes '
             'compatible grouping and work checked and Also include ID3v1 tags unchecked.',
             stamp_then_page('Café Crème', 'ID3')[1],
             [dump('inputs/fo1/latin.mp3', 'ID3v2.4 with ISO-8859-1 text (UTF-16 where a value needs it), iTunes '
                   'compatible grouping and work, and no ID3v1 tag.', encodings=True),
              dump('inputs/fo1/flac-with-id3.flac', 'The FLAC file without its ID3 tag.'),
              dump('inputs/fo1/mp3-with-ape.mp3', 'The MP3 file without its APEv2 tag.', encodings=True),
              dump('inputs/fo1/wave.wav', 'The WAVE file with new RIFF INFO tags in UTF-8, the old INFO removed.'),
              dump('inputs/fo1/noape.aac', 'The AAC file without APEv2 tags.'),
              dump('inputs/fo1/keep.ac3', 'The AC-3 file with its APEv2 tags written again.'),
              dump('inputs/fo1/date-kept.flac', 'The Vorbis date is not sanitized.'),
              dump('inputs/fo1/date-cleaned.wv', 'The APEv2 date is sanitized.'),
              dump('inputs/fo1/seek-kept.flac', 'The empty FLAC seek table is kept.', seektable=True),
              {'kind': 'mtime-kept', 'path': 'inputs/fo1/latin.mp3', 'description': 'Saving changed the file\'s '
               'modification time.'}],
             preparation=prepared('fo1', {
                 'id3v2_encoding': 'iso-8859-1', 'write_id3v1': False, 'itunes_compatible_grouping': True,
                 'remove_id3_from_flac': True, 'remove_ape_from_mp3': True, 'remove_wave_riff_info': True,
                 'wave_riff_info_encoding': 'utf-8', 'aac_save_ape': False, 'remove_ape_from_aac': True,
                 'disable_date_sanitization_formats': ['vorbis']})),
        step('formats-2', stamp_then_page('Mülti', 'AC3')[0],
             'The AC3 options page shows Do not save tags selected and Remove APEv2 tags from AC3 files checked.',
             stamp_then_page('Mülti', 'AC3')[1],
             [dump('inputs/fo2/multi.mp3', 'ID3v2.3 with UTF-16 text and multiple values joined with "; ".',
                   encodings=True),
              dump('inputs/fo2/wave2.wav', 'The WAVE file keeps its RIFF INFO and gets ID3v2.3.'),
              dump('inputs/fo2/aac2.aac', 'The AAC file with its APEv2 tags written again.'),
              dump('inputs/fo2/ac32.ac3', 'The AC-3 file without APEv2 tags.')],
             preparation=prepared('fo2', {
                 'write_id3v23': True, 'id3v2_encoding': 'utf-16', 'id3v23_join_with': '; ',
                 'write_wave_riff_info': False, 'ac3_save_ape': False, 'remove_ape_from_ac3': True})),
        step('no-tag-saving', 'Run the tagger script "Mark" on all loaded files, then save them; then select the file '
             'Keep Tags One.',
             'The files are saved and moved: the metadata view of Keep Tags One shows a File Path in '
             + outputs('renamed/Marked Album')+'.',
             [{'op': 'select', 'text': 'Unclustered Files'}, {'op': 'run-script', 'target': 'Unclustered Files'},
              {'op': 'save'}, {'op': 'select', 'text': 'Keep Tags One', 'exact': True}],
             [{'kind': 'located', 'title': 'Keep Tags One', 'description': 'Moved by the naming script using the '
               'scripted album.'},
              {'kind': 'located', 'title': 'Keep Tags Two', 'description': 'Moved by the naming script using the '
               'scripted album.'},
              {'kind': 'dump', 'title': 'Keep Tags One', 'description': 'The moved file keeps its original tags.'},
              {'kind': 'dump', 'title': 'Keep Tags Two', 'description': 'The moved file keeps its original tags.'}],
             requires={'state-3': ['state-1'], 'state-4': ['state-2']},
             preparation=prepared('fo3', {'enable_tag_saving': False, 'rename_files': True, 'move_files': True,
                                          'move_files_to': '{outputs}/renamed'},
                                  naming='%album%/%title%', tagging=[('Mark', '$set(album,Marked Album)')])),
        step('clear-tags', 'Run the tagger script "Trim" on all loaded files, then save them; then select the file '
             'Clear One.',
             'The files are saved and none is marked as changed; the metadata view of Clear One shows Album Cleared.',
             [{'op': 'select', 'text': 'Unclustered Files'}, {'op': 'run-script', 'target': 'Unclustered Files'},
              {'op': 'save'}, {'op': 'select', 'text': 'Clear One', 'exact': True}],
             [dump('inputs/fo4/c1.flac', 'Only the tags of the new metadata remain in the FLAC file.'),
              dump('inputs/fo4/c2.mp3', 'Only the tags of the new metadata remain in the MP3 file.')],
             preparation=prepared('fo4', {'clear_existing_tags': True},
                                  tagging=[('Trim', '$unset(mood)$set(album,Cleared)')])),
        step('cover-files', stamp_then_page('Pictures One', 'Cover Art')[0],
             'The Cover Art options page shows Embed cover images into tags unchecked, and Save cover images as '
             'separate files, Use the primary image type as the file name and Remove cover images from tags checked.',
             stamp_then_page('Pictures One', 'Cover Art')[1],
             [{'kind': 'tree', 'area': 'inputs', 'under': 'fo5', 'description': 'The embedded images are saved as '
               'image files named after their type next to the audio file.'},
              {'kind': 'image-file', 'path': 'inputs/fo5/album/cover.jpg', 'description': 'The front cover file holds '
               'the embedded front image.'},
              {'kind': 'image-file', 'path': 'inputs/fo5/album/back.png', 'description': 'The back cover file holds '
               'the embedded back image.'},
              dump('inputs/fo5/album/i1.flac', 'The images are removed from the tags.')],
             preparation=prepared('fo5', {'save_images_to_files': True, 'image_type_as_filename': True,
                                          'save_images_to_tags': False, 'remove_images_from_tags': True,
                                          'embed_only_one_front_image': False})),
        step('cover-front-only', stamp_then_page('Pictures Two', 'Cover Art')[0],
             'The Cover Art options page shows Embed cover images into tags and Embed only a single front image '
             'checked, and Save cover images as separate files unchecked.',
             stamp_then_page('Pictures Two', 'Cover Art')[1],
             [dump('inputs/fo6/i2.flac', 'Only the front image stays embedded in the FLAC file.'),
              dump('inputs/fo6/i3.mp3', 'Only the front image stays embedded in the MP3 file.')],
             preparation=prepared('fo6', {'embed_only_one_front_image': True})),
        step('paths', STAMP_GOAL[:-1]+'; then select the file AC/DC Song.', 'The script ran and the files were saved and '
             'moved: the metadata view of AC/DC Song '
             'shows Encoded By Stamped and a File Path in '+outputs('paths')+'.', stamp_and_save('AC/DC Song'),
             [{'kind': 'located', 'title': 'Ünïcode: Name?', 'description': 'File name with non-ASCII characters '
               'replaced and without Windows compatibility.'},
              {'kind': 'located', 'title': 'AC/DC Song', 'description': 'File name with the directory separator of '
               'the title replaced.'},
              {'kind': 'tree', 'area': 'outputs', 'under': 'paths', 'description': 'The audio files and the '
               'additional files matching the patterns are in the destination folder.'},
              {'kind': 'tree', 'area': 'inputs', 'under': 'fo7', 'description': 'Only the file that matches no '
               'additional-file pattern is left in the source folder.'}],
             preparation=prepared('fo7', {'rename_files': True, 'move_files': True, 'move_files_to': '{outputs}/paths',
                                          'windows_compatibility': False, 'ascii_filenames': True,
                                          'replace_dir_separator': '-', 'move_additional_files': True,
                                          'move_additional_files_pattern': '*.jpg *.txt'},
                                  naming='%title%')),
        step('timestamps', stamp_then_page('Time Kept', 'Tags')[0],
             'The Tags options page shows Preserve timestamps of tagged files and Fix missing seekpoints for FLAC files '
             'checked.',
             stamp_then_page('Time Kept', 'Tags')[1],
             [dump('inputs/fo10/ts.flac', 'The empty FLAC seek table is removed.', seektable=True),
              {'kind': 'mtime-kept', 'path': 'inputs/fo10/ts.flac', 'description': 'The saved FLAC file keeps its '
               'modification time.'},
              dump('inputs/fo10/ts.mp3', 'The saved MP3 file.'),
              {'kind': 'mtime-kept', 'path': 'inputs/fo10/ts.mp3', 'description': 'The saved MP3 file keeps its '
               'modification time.'}],
             requires={'state-2': ['state-1'], 'state-4': ['state-3']},
             preparation=prepared('fo10', {'preserve_timestamps': True, 'fix_missing_seekpoints_flac': True})),
        step('guess', STAMP_GOAL[:-1]+'; then select the file 07. Guessed Title.flac.', 'The script ran and the files '
             'were saved: the file 07. Guessed Title.flac shows '
             'Title Guessed Title, Track Number 7 and Encoded By Stamped, and it is not marked as changed.',
             stamp_and_save('Guessed Title'),
             [dump('inputs/fo8/07. Guessed Title.flac', 'Title and track number guessed from the file name.'),
              dump('inputs/fo8/08 - Dash Title.flac', 'Title and track number guessed from a file name with a '
                   'dash after the number.'),
              dump('inputs/fo8/Some Artist - 03 - Other Title.mp3', 'Tags guessed from the file name.'),
              dump('inputs/fo8/12.ogg', 'Tags guessed from a file name that is only a number.')],
             preparation=prepared('fo8', {'guess_tracknumber_and_title': True})),
        step('add-filtered', 'Add the folder '+inputs('fo9')+' with the application\'s Add Folder command.',
             'The file list shows Visible and Deeper, but not Hidden or Skipped.',
             [{'op': 'press', 'key': 'Control+e'}, {'op': 'wait-window', 'title': 'Select a directory'},
              {'op': 'dialog', 'path': '{inputs}/fo9'}, {'op': 'sleep', 'seconds': 3},
              {'op': 'select', 'text': 'Visible', 'exact': True}],
             [{'kind': 'session', 'under': 'fo9', 'description': 'The session the application saves on exit lists '
               'only the files that the loading settings do not exclude.'}],
             preparation=[{'op': 'profile', 'profile': profile('Options fo9', {'ignore_hidden_files': True,
                                                                               'ignore_regex': '/skip/'})}]),
    ]
    return documents, steps


FOLDERS = {'formats-1': 'fo1', 'formats-2': 'fo2', 'no-tag-saving': 'fo3', 'clear-tags': 'fo4', 'cover-files': 'fo5',
           'cover-front-only': 'fo6', 'paths': 'fo7', 'timestamps': 'fo10', 'guess': 'fo8', 'add-filtered': 'fo9'}
SETTINGS = {
    'formats-1': 'writes ID3v2.4 with ISO-8859-1 text, iTunes compatible grouping and no ID3v1, removes ID3 tags from '
                 'FLAC and APEv2 tags from MP3, replaces RIFF INFO in UTF-8, does not save APEv2 tags to AAC (removing '
                 'them) and does not sanitize Vorbis dates',
    'formats-2': 'writes ID3v2.3 with UTF-16 text joined with "; ", writes no RIFF INFO and removes APEv2 tags from AC-3',
    'no-tag-saving': 'renames and moves files with the naming script %album%/%title% without writing tags',
    'clear-tags': 'clears existing tags',
    'cover-files': 'saves cover images as image files named after their type instead of embedding them, and '
                   'removes embedded images from the tags',
    'cover-front-only': 'embeds only one front image',
    'paths': 'renames and moves files with the naming script %title%, replacing non-ASCII characters and directory '
             'separators ("-"), without Windows compatibility, and moves *.jpg and *.txt files along',
    'timestamps': 'preserves the files\' modification times and removes empty FLAC seek tables',
    'guess': 'guesses track numbers and titles from file names',
    'add-filtered': 'ignores hidden files and paths matching /skip/',
}
GROUPS = (('saving-options-tags', ('formats-1', 'formats-2')),
          ('saving-options-writing', ('no-tag-saving', 'clear-tags')),
          ('saving-options-cover', ('cover-files', 'cover-front-only')),
          ('saving-options-files', ('paths', 'timestamps')),
          ('saving-options-loading', ('guess', 'add-filtered')))


def build():
    episodes = []
    for key, ids in GROUPS:
        documents, steps = parts(key)
        folders = {FOLDERS[i] for i in ids}
        chosen = [s for s in steps if s['id'] in ids]
        if 'add-filtered' in ids:
            start = ('an empty file list; before each checkpoint the framework imports that checkpoint\'s settings and '
                     'restarts the application, and before the first checkpoint it also loads that checkpoint\'s folder')
        else:
            start = ('an empty file list; before each checkpoint the framework imports that checkpoint\'s settings, '
                     'restarts the application and loads that checkpoint\'s folder')
        episodes.append(episode(
            key, 'saving-options', chosen, documents=[d for d in documents if d[0].split('/')[0] in folders],
            start=start, described='Settings per checkpoint: '+'; '.join(f'{i} {SETTINGS[i]}' for i in ids)+'.'))
    return episodes
