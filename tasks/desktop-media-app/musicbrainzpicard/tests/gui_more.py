"""GUI episodes: sessions, option profiles, cover art, removing files, the setup wizard, configuration backups and
script files."""
from guispec import area_path, step, text_value, episode
from gui_episodes import SESSION_SETTINGS, dump, flac, located, mp3, select, session, vorbis


def sessions():
    key = 'sessions'
    return episode(key, 'sessions', [
        step('save-session', 'Change the Title of the file "Session One" to '+text_value('Edited in session')
             + ' without saving the file; then save the current session to the file '
             + area_path(key, 'outputs', 'work.mbps.gz')+'.',
             'The metadata view of the file shows Title with the original value Session One and the new value Edited '
             'in session (its tags were not saved).',
             [select('Session One'), {'op': 'edit-tag', 'tag': 'Title', 'value': 'Edited in session'},
              {'op': 'menu', 'path': ['File', 'Save Session As…']},
              {'op': 'wait-window', 'title': 'Select a target file'}, {'op': 'dialog', 'path': '{outputs}/work.mbps.gz'},
              select('Edited in session')],
             [{'kind': 'session-file', 'path': 'outputs/work.mbps.gz',
               'description': 'The saved session lists the loaded files with their places and the unsaved title.'}]),
        step('quick-save', 'Change the Album of the file "Session Two" to '+text_value('Quick Album')+' without saving '
             'the file; then save the session again with the application\'s command that saves it to its current '
             'session file (without a file dialog).',
             'The status bar reports that the session was saved to '+area_path(key, 'outputs', 'work.mbps.gz')
             + ', and the metadata view of Session Two shows Album with the original value Session Album and the new '
             'value Quick Album.',
             [select('Session Two'), {'op': 'edit-tag', 'tag': 'Album', 'value': 'Quick Album'},
              {'op': 'menu', 'path': ['File', 'Save Session']}, {'op': 'sleep', 'seconds': 1}, select('Session Two')],
             [{'kind': 'session-file', 'path': 'outputs/work.mbps.gz',
               'description': 'The session file, saved again, lists both unsaved changes.'}],
             depends=['save-session']),
        step('history', 'Open the application\'s activity history.',
             'A window titled Activity History lists the session saves as entries Session saved to "'
             + area_path(key, 'outputs', 'work.mbps.gz')+'".',
             [{'op': 'press', 'key': 'Control+h'}, {'op': 'wait-window', 'title': 'Activity History'},
              {'op': 'sleep', 'seconds': 1}], depends=['save-session']),
        step('new-session', 'Close the activity history window. Start a new, empty session without saving the current '
             'one (the loaded files and the unsaved changes are discarded).',
             'The file list is empty: neither Unclustered Files nor Clusters hold any file.',
             [{'op': 'close-windows'}, {'op': 'menu', 'path': ['File', 'New Session']},
              {'op': 'wait-window', 'title': 'Close Session'},
              {'op': 'button', 'name': "Don't Save"}])],
        documents=[('sess', 's1.flac', flac('Session One', artist='Sess', album='Session Album'), None),
                   ('sess', 's2.mp3', mp3('Session Two', artist='Sess', album='Session Album'), None)],
        profile={'title': 'Sessions', 'settings': SESSION_SETTINGS}, load=['sess'],
        start='two files loaded from '+area_path(key, 'inputs', 'sess')+' (Session One, Session Two)')


def session_startup():
    key = 'session-startup'
    items = [{'file': 'sessin/p1.flac', 'location': {'type': 'cluster', 'cluster_title': 'Saved Cluster',
                                                      'cluster_artist': 'Saved Artist'}},
             {'file': 'sessin/p2.flac'}]
    return episode(key, 'sessions', [
        step('load-session', 'Load the session file '+area_path(key, 'inputs', 'sessin/prepared.mbps.gz')+'.',
             'The file list shows the cluster Saved Cluster holding the file Prepared One, and the file Prepared Two '
             'under Unclustered Files.',
             [{'op': 'menu', 'path': ['File', 'Load Session…']}, {'op': 'wait-window', 'title': 'Select a file'},
              {'op': 'dialog', 'path': '{inputs}/sessin/prepared.mbps.gz'}, {'op': 'sleep', 'seconds': 2},
              select('Saved Cluster', exact=False), {'op': 'press', 'key': 'Right'}, {'op': 'sleep', 'seconds': .5}],
             [session('sessin', 'The session the application saves on exit lists the two files of the loaded '
                      'session in their places.')]),
        step('restore-option', 'In the options\' Sessions page, turn on loading the last saved session on startup and '
             'apply the options; then open the Sessions page again.',
             'The Sessions options page shows "Load last saved session on startup" checked.',
             [{'op': 'options', 'page': 'Sessions'}, {'op': 'set-check', 'name': 'Load last saved session on startup'},
              {'op': 'button', 'name': 'Make It So!'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'options', 'page': 'Sessions'}]),
        step('restored', 'The application was started again. In the session it loaded on startup, expand the cluster '
             'Saved Cluster and select its file Prepared One.',
             'The file list shows the cluster Saved Cluster with its file Prepared One selected, and Prepared Two under '
             'Unclustered Files.',
             [{'op': 'close-windows'}, select('Saved Cluster', exact=False), {'op': 'press', 'key': 'Right'},
              {'op': 'sleep', 'seconds': .5}, select('Prepared One')],
             [session('sessin', 'Started again, the application loads the last session: the session it saves on exit '
                      'lists the two files of that session in their places.')],
             depends=['load-session', 'restore-option'], lifecycle='restart')],
        documents=[('sessin', 'p1.flac', flac('Prepared One', artist='Saved Artist', albumartist='Saved Artist',
                                              album='Saved Cluster'), None),
                   ('sessin', 'p2.flac', flac('Prepared Two', album='Elsewhere'), None),
                   ('sessin', 'prepared.mbps.gz', {'session': {'items': items}},
                    'a saved session listing Prepared One in the cluster Saved Cluster and Prepared Two unclustered')],
        profile={'title': 'Session startup', 'settings': SESSION_SETTINGS},
        start='an empty file list')


def option_profiles():
    key = 'option-profiles'
    shared = {'title': 'Shared Settings', 'settings': {'windows_compatibility': False, 'ascii_filenames': True,
                                                       'replace_spaces_with_underscores': True}}
    return episode(key, 'profiles', [
        step('export', 'Export the option profile "Portable" in share mode to the file '
             + area_path(key, 'outputs', 'portable.toml')+' (Options, Option Profiles page).',
             'The application confirms that the profile was exported to '+area_path(key, 'outputs', 'portable.toml')
             + '.',
             [{'op': 'options', 'page': 'Option Profiles'}, {'op': 'click', 'target': {'role': 'list item',
                                                                                     'name': 'Portable'}},
              {'op': 'button', 'name': 'Export'}, {'op': 'wait-window', 'title': 'Export Profile'},
              {'op': 'button', 'name': 'OK'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'dialog', 'path': '{outputs}/portable.toml'}, {'op': 'wait-window', 'title': 'Export Complete'}],
             [{'kind': 'profile-export', 'path': 'outputs/portable.toml',
               'description': 'The exported profile document holds the profile\'s settings and naming script.'}]),
        step('import', 'Import the option profile file '+area_path(key, 'inputs', 'prof/shared.toml')+' (Options, '
             'Option Profiles page, import from a file) as an enabled profile and apply the options; then open the '
             'Option Profiles page again.',
             'The Option Profiles page lists the profiles Shared Settings and Portable, both enabled.',
             [{'op': 'press', 'key': 'Return'}, {'op': 'options', 'page': 'Option Profiles'},
              {'op': 'button', 'name': 'Import'}, {'op': 'sleep', 'seconds': .5}, {'op': 'press', 'key': 'Down'},
              {'op': 'press', 'key': 'Return'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'dialog', 'path': '{inputs}/prof/shared.toml'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'dismiss'}, {'op': 'button', 'name': 'Make It So!'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'options', 'page': 'Option Profiles'}],
             [{'kind': 'profile-list', 'titles': ['Shared Settings', 'Portable'],
               'description': 'The product\'s profile list names the imported profile.'}]),
        step('new', 'Create a new option profile titled '+text_value('Fresh Start')+' (Options, Option Profiles '
             'page) and apply the options; then open the Option Profiles page again.',
             'The Option Profiles page lists the new profile Fresh Start.',
             [{'op': 'options', 'page': 'Option Profiles'}, {'op': 'button', 'name': 'New'},
              {'op': 'rename-selected', 'value': 'Fresh Start'}, {'op': 'button', 'name': 'Make It So!'},
              {'op': 'sleep', 'seconds': 1}, {'op': 'options', 'page': 'Option Profiles'}],
             [{'kind': 'profile-list', 'titles': ['Fresh Start'],
               'description': 'The product\'s profile list names the new profile.'}])],
        documents=[('prof', 'shared.toml', {'profile': shared}, 'a settings profile titled Shared Settings')],
        profile={'title': 'Portable', 'settings': {**SESSION_SETTINGS, 'rename_files': True, 'move_files': True,
                                                   'move_files_to': '{outputs}/portable'},
                 'naming': {'title': 'Portable naming', 'script': '%artist%/%title%'}},
        start='an empty file list; the option profile "Portable" (renaming and moving files with its own naming '
              'script) is enabled')


def cover_art():
    key = 'cover-art'
    return episode(key, 'cover-art', [
        step('choose-local', 'Add the image '+area_path(key, 'inputs', 'cover/new-front.png')+' as cover art to the '
             'file "Needs Cover" with the cover art area\'s command for choosing a local file, then save the file.',
             'The cover art area of Needs Cover shows the new picture (green with a yellow box) and the file is '
             'saved (not marked as changed).',
             [select('Needs Cover'), {'op': 'cover-menu', 'keys': ['Down', 'Down', 'Return']},
              {'op': 'wait-window', 'title': 'Select a file or a directory'},
              {'op': 'dialog', 'path': '{inputs}/cover/new-front.png'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'save'}, select('Needs Cover')],
             [dump('inputs/cover/needs.flac', 'The saved file embeds the chosen image as its front cover.')]),
        step('replace-cover', 'For the file "Replace Cover", which already has a front cover, switch the cover art '
             'area to replacing front cover art (instead of appending to it), add the image '
             + area_path(key, 'inputs', 'cover/new-front.png')+' with the cover art area\'s command for choosing a '
             'local file, then save the file.',
             'Replace Cover is saved (not marked as changed) and its cover art area shows only the new picture (green '
             'with a yellow box).',
             [select('Replace Cover'), {'op': 'cover-menu', 'keys': ['Up', 'Up', 'Return']},
              {'op': 'cover-menu', 'keys': ['Down', 'Down', 'Return']},
              {'op': 'wait-window', 'title': 'Select a file or a directory'},
              {'op': 'dialog', 'path': '{inputs}/cover/new-front.png'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'save'}, select('Replace Cover')],
             [dump('inputs/cover/replace.flac', 'The saved file embeds only the chosen image as its front cover.')]),
        step('append-cover', 'For the file "Append Cover", switch the cover art area back to appending front cover art '
             '(instead of replacing it), add the image '+area_path(key, 'inputs', 'cover/new-front.png')+' with the '
             'cover art area\'s command for choosing a local file, then save the file.',
             'Append Cover is saved (not marked as changed) and its cover art area shows both covers: the red and blue '
             'picture it had and, behind or beside it, the green picture.',
             [select('Append Cover'), {'op': 'cover-menu', 'keys': ['Up', 'Return']},
              {'op': 'cover-menu', 'keys': ['Down', 'Down', 'Return']},
              {'op': 'wait-window', 'title': 'Select a file or a directory'},
              {'op': 'dialog', 'path': '{inputs}/cover/new-front.png'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'save'}, select('Append Cover')],
             [dump('inputs/cover/append.flac', 'The saved file embeds its original front cover and the appended '
                   'one.')]),
        step('keep-original', 'Change the Title of the file "Keep Cover" to '+text_value('Kept Cover')+' and give it '
             'the image '+area_path(key, 'inputs', 'cover/new-front.png')+' as cover art (choosing a local file); then '
             'go back to its original cover art with the cover art area\'s command for keeping the original cover '
             'art, and save the file.',
             'Kept Cover is saved (not marked as changed); its metadata view shows Title Kept Cover and its cover art '
             'area shows only its original red and blue picture.',
             [select('Keep Cover'), {'op': 'edit-tag', 'tag': 'Title', 'value': 'Kept Cover'},
              {'op': 'cover-menu', 'keys': ['Down', 'Down', 'Return']},
              {'op': 'wait-window', 'title': 'Select a file or a directory'},
              {'op': 'dialog', 'path': '{inputs}/cover/new-front.png'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'cover-menu', 'keys': ['Down', 'Down', 'Return']}, {'op': 'save'}, select('Kept Cover')],
             [dump('inputs/cover/keep.flac', 'The saved file has the new title and only its original cover.')]),
        step('cover-files', 'In the cover art options, turn on saving cover images as separate files with the file '
             'name '+text_value('folder')+' and apply the options; then save the file "Has Cover" and open the cover '
             'art options again to show the settings.',
             'The cover art options show saving cover images as separate files turned on, with the file name folder.',
             [{'op': 'options', 'page': 'Cover Art'}, {'op': 'set-check', 'name': 'Save cover images as separate files'},
              {'op': 'set-text', 'target': {'role': 'text', 'name': 'Use the following file name for images:'},
               'value': 'folder'},
              {'op': 'button', 'name': 'Make It So!'}, select('Has Cover'), {'op': 'save'},
              {'op': 'options', 'page': 'Cover Art'}],
             [{'kind': 'tree', 'area': 'inputs', 'under': 'cover', 'description': 'The embedded cover of Has Cover is '
               'also saved as an image file named folder next to it.'},
              {'kind': 'image-file', 'path': 'inputs/cover/folder.jpg', 'description': 'The saved image file holds the '
               'embedded cover.'}])],
        documents=[('cover', 'needs.flac', flac('Needs Cover', album='Cover Album'), None),
                   ('cover', 'has.flac', vorbis('flac', 'Has Cover', pictures=[(3, '', 'front.jpg')],
                                               album='Has Album'), None),
                   ('cover', 'replace.flac', vorbis('flac', 'Replace Cover', pictures=[(3, '', 'front.jpg')],
                                                   album='Replace Album'), None),
                   ('cover', 'append.flac', vorbis('flac', 'Append Cover', pictures=[(3, '', 'front.jpg')],
                                                  album='Append Album'), None),
                   ('cover', 'keep.flac', vorbis('flac', 'Keep Cover', pictures=[(3, '', 'front.jpg')],
                                                album='Keep Album'), None),
                   ('cover', 'new-front.png', {'image': 'back.png'}, 'a PNG picture (green with a yellow box)')],
        profile={'title': 'Cover art', 'settings': {**SESSION_SETTINGS, 'embed_only_one_front_image': False}},
        load=['cover'],
        start='five files loaded from '+area_path(key, 'inputs', 'cover')+': Needs Cover (without cover art), Has '
              'Cover, Replace Cover, Append Cover and Keep Cover (each with an embedded front cover, a red and blue '
              'picture); the settings embed every cover image, not only one front image')


def removing():
    key = 'remove-files'
    return episode(key, 'removing', [
        step('remove', 'Remove the file "Remove Me" from the file list (the file itself stays in its folder).',
             'Remove Me is no longer listed; Keep Me and Trash Me still are.',
             [select('Remove Me'), {'op': 'button', 'name': 'Remove'}, select('Keep Me')],
             [session('rm', 'The session the application saves on exit no longer lists the removed file.')]),
        step('trash', 'Move the file "Trash Me" to the trash with the application\'s Move to trash command.',
             'Trash Me is no longer listed; Keep Me and Remove Me still are.',
             [select('Trash Me'), {'op': 'press', 'key': 'Shift+Delete'},
              {'op': 'wait-window', 'title': 'Move files to trash'}, {'op': 'button', 'name': 'Yes'},
              select('Keep Me')],
             [{'kind': 'tree', 'area': 'inputs', 'under': 'rm', 'description': 'The trashed file is gone from its '
               'folder; the other files remain.'}],
             preparation=[{'op': 'load', 'paths': ['rm']}])],
        documents=[('rm', 'keep.flac', flac('Keep Me'), None), ('rm', 'remove.flac', flac('Remove Me'), None),
                   ('rm', 'trash.flac', flac('Trash Me'), None)],
        profile={'title': 'Removing', 'settings': SESSION_SETTINGS}, load=['rm'],
        start='three files loaded from '+area_path(key, 'inputs', 'rm')+' (Keep Me, Remove Me, Trash Me); before the '
              'second checkpoint the framework loads the folder again')


def setup_wizard():
    key = 'setup-wizard'
    return episode(key, 'setup-wizard', [
        step('wizard', 'Open the setup wizard; on its file organization page turn on renaming files and moving them '
             'into the folder '+area_path(key, 'outputs', 'organized')+'; finish the wizard (keep the other pages as '
             'they are) and then save all loaded files.',
             'The wizard is closed and the metadata view of Wizard Song shows a File Path in '
             + area_path(key, 'outputs', 'organized/Wiz/Wizardry')+'.',
             [{'op': 'menu', 'path': ['Help', 'Show Setup Wizard…']}, {'op': 'wait-window', 'title': 'Picard Setup'},
              {'op': 'button', 'name': 'Next >'},
              {'op': 'set-check', 'name': 'Rename files based on tags (e.g. "Artist - Title.mp3")'},
              {'op': 'set-check', 'name': 'Move files to a folder structure based on tags'},
              {'op': 'fill', 'target': {'role': 'text', 'text': 'Music'}, 'value': '{outputs}/organized'},
              {'op': 'button', 'name': 'Next >'}, {'op': 'button', 'name': 'Next >'},
              {'op': 'button', 'name': 'Next >'}, {'op': 'button', 'name': 'Finish'},
              select('Unclustered Files', exact=False), {'op': 'save'}, select('Wizard Song')],
             [located('Wizard Song', 'The file saved under the name and folder the wizard\'s settings give it.')])],
        documents=[('wiz', 'w1.flac', flac('Wizard Song', artist='Wiz', albumartist='Wiz', album='Wizardry',
                                           tracknumber='1'), None)],
        profile={'title': 'Wizard', 'settings': SESSION_SETTINGS}, load=['wiz'],
        start='the file Wizard Song loaded from '+area_path(key, 'inputs', 'wiz')+'; files are neither renamed nor '
              'moved when saving')


def backup(path):
    """Recipe: options, Maintenance page, save a configuration backup to path, confirm the message."""
    return [{'op': 'options', 'page': 'Maintenance'}, {'op': 'button', 'name': 'Save backup…'},
            {'op': 'wait-window', 'title': 'Backup Configuration File'}, {'op': 'dialog', 'path': path},
            {'op': 'wait-window', 'title': 'Backup Configuration File'}, {'op': 'button', 'name': 'OK'}]


def config_backup():
    key = 'config-backup'
    result = episode(key, 'maintenance', [
        step('backup', 'In the options, turn on "Rename files when saving" (File Naming page) and apply the options; '
             'then open the options again and, on the Maintenance page, save a configuration backup to the file '
             + area_path(key, 'outputs', 'picard-backup.ini')+'.',
             'The application confirms that the configuration was backed up to '
             + area_path(key, 'outputs', 'picard-backup.ini')+'.',
             [{'op': 'options', 'page': 'File Naming'}, {'op': 'set-check', 'name': 'Rename files when saving'},
              {'op': 'button', 'name': 'Make It So!'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'options', 'page': 'Maintenance'}, {'op': 'button', 'name': 'Save backup…'},
              {'op': 'wait-window', 'title': 'Backup Configuration File'},
              {'op': 'dialog', 'path': '{outputs}/picard-backup.ini'},
              {'op': 'wait-window', 'title': 'Backup Configuration File'}],
             [{'kind': 'ini', 'path': 'outputs/picard-backup.ini', 'section': 'setting',
               'keys': ['rename_files'],
               'description': 'The backup holds the configuration with renaming turned on.'}]),
        step('preserve-tag', 'Close the options dialog. Add the tag Mood of the file "Config Song" to the Preserve Tags '
             'list with the metadata '
             'view\'s context menu; then save a configuration backup to the file '
             + area_path(key, 'outputs', 'preserve.ini')+' (options, Maintenance page) and open the Tags page of the '
             'options.',
             'The Tags options page lists mood among the tags to preserve from being cleared or overwritten.',
             [{'op': 'close-windows'}, select('Config Song'), {'op': 'tag-menu', 'tag': 'Mood', 'keys': ['Down', 'Down',
                                                                                                       'Return']},
              *backup('{outputs}/preserve.ini'), {'op': 'options', 'page': 'Tags'}],
             [{'kind': 'ini', 'path': 'outputs/preserve.ini', 'section': 'setting', 'keys': ['preserved_tags'], 'lists': True,
               'description': 'The backup holds the list of preserved tags with mood.'}]),
        step('top-tags', 'In the options\' Top Tags page, add the tag genre, move it to the top of the list and apply '
             'the options; then save a configuration backup to the file '+area_path(key, 'outputs', 'top.ini')
             + ' (options, Maintenance page) and select the file Config Song.',
             'The metadata view of Config Song lists Genre (Ambient) as its first row, above Title.',
             [{'op': 'close-windows'}, {'op': 'options', 'page': 'Top Tags'}, {'op': 'button', 'name': 'Add new tag'},
              {'op': 'type', 'value': 'genre'}, {'op': 'press', 'key': 'Return'},
              *[{'op': 'button', 'name': 'Move tag up', 'pause': .3}]*6, {'op': 'button', 'name': 'Make It So!'},
              {'op': 'sleep', 'seconds': 1}, *backup('{outputs}/top.ini'), {'op': 'close-windows'},
              select('Config Song')],
             [{'kind': 'ini', 'path': 'outputs/top.ini', 'section': 'setting', 'keys': ['metadatabox_top_tags'], 'lists': True,
               'description': 'The backup holds the top tags with genre first.'}])],
        documents=[('cfg', 'c1.flac', flac('Config Song', artist='Cfg', genre='Ambient', mood='Serene'), None)],
        profile={'title': 'Backup', 'settings': SESSION_SETTINGS}, load=['cfg'],
        start='the file Config Song loaded from '+area_path(key, 'inputs', 'cfg'))
    result['budget'].update(calls=250, tokens=5_000_000)
    return result


def script_files():
    key = 'script-files'
    tagger = ('title: Imported tagger\nscript_language_version: \'1.0\'\nscript: $set(mood,imported mood)\n')
    return episode(key, 'scripts', [
        step('export-naming', 'With the file naming script editor, export the file naming script "Shared naming" '
             'as a script package to '+area_path(key, 'outputs', 'shared-naming.ptsp')+'.',
             'The application confirms that the script was exported to '
             + area_path(key, 'outputs', 'shared-naming.ptsp')+'.',
             [{'op': 'press', 'key': 'Control+Shift+s'}, {'op': 'wait-window', 'title': 'File naming script editor'},
              {'op': 'click', 'target': {'role': 'menu item', 'name': 'File', 'nth': 1}}, {'op': 'sleep', 'seconds': .5},
              {'op': 'click', 'target': {'role': 'menu item', 'name': 'Export a script file'}},
              {'op': 'wait-window', 'title': 'Export Script File'}, {'op': 'dialog', 'path': '{outputs}/shared-naming.ptsp'},
              {'op': 'wait-window', 'title': 'Export Script'}],
             [{'kind': 'script-package', 'path': 'outputs/shared-naming.ptsp',
               'description': 'The exported package holds the naming script\'s title and text.'}]),
        step('export-tagger', 'On the options\' Scripting page, export the tagger script "Shared tagger" as a script '
             'package to '+area_path(key, 'outputs', 'shared-tagger.ptsp')+'.',
             'The application confirms that the script was exported to '
             + area_path(key, 'outputs', 'shared-tagger.ptsp')+'.',
             [{'op': 'close-windows'}, {'op': 'options', 'page': 'Scripting'},
              {'op': 'click', 'target': {'role': 'list item', 'name': 'Shared tagger'}},
              {'op': 'button', 'name': 'Export'}, {'op': 'wait-window', 'title': 'Export Script File'},
              {'op': 'dialog', 'path': '{outputs}/shared-tagger.ptsp'}, {'op': 'wait-window', 'title': 'Export Script'}],
             [{'kind': 'script-package', 'path': 'outputs/shared-tagger.ptsp',
               'description': 'The exported package holds the tagger script\'s title and text.'}]),
        step('import-tagger', 'On the options\' Scripting page, import the tagger script package '
             + area_path(key, 'inputs', 'scripts/imported-tagger.ptsp')+' and apply the options; then run the '
             'imported script on all loaded files and save them; then select the file Script One.',
             'The files are saved and the metadata view of Script One shows Mood imported mood.',
             [{'op': 'close-windows'}, {'op': 'options', 'page': 'Scripting'}, {'op': 'button', 'name': 'Import'},
              {'op': 'wait-window', 'title': 'Import Script File'},
              {'op': 'dialog', 'path': '{inputs}/scripts/imported-tagger.ptsp'}, {'op': 'sleep', 'seconds': 1},
              {'op': 'button', 'name': 'Make It So!'}, select('Unclustered Files', exact=False),
              {'op': 'run-script', 'target': 'Unclustered Files', 'entry': 2}, {'op': 'save'}, select('Script One')],
             [dump('inputs/scripts-in/x1.flac', 'The imported script set the mood of the FLAC file.'),
              dump('inputs/scripts-in/x2.mp3', 'The imported script set the mood of the MP3 file.')])],
        documents=[('scripts', 'imported-tagger.ptsp', {'text': tagger}, 'a tagger script package (YAML)'),
                   ('scripts-in', 'x1.flac', flac('Script One', album='Script Album'), None),
                   ('scripts-in', 'x2.mp3', mp3('Script Two', album='Script Album'), None)],
        profile={'title': 'Scripts', 'settings': SESSION_SETTINGS,
                 'naming': {'title': 'Shared naming', 'script': '%album%/$num(%tracknumber%,2) %title%'},
                 'tagging': [{'title': 'Shared tagger', 'enabled': False, 'script': '$set(comment,shared tagger ran)'}],
                 'enable_tagger_scripts': True},
        load=['scripts-in'],
        start='two files loaded from '+area_path(key, 'inputs', 'scripts-in')+' (Script One, Script Two); the '
              'settings hold the file naming script "Shared naming" and, with tagger scripts enabled, the (inactive) '
              'tagger script "Shared tagger"')


def interface():
    key = 'interface'
    return episode(key, 'interface', [
        step('quick-rename', 'Turn on renaming files through the quick settings of the Options menu (not the Options '
             'dialog), then save the file Interface Song.',
             'The file is saved and renamed: the metadata view of Interface Song shows a File Path ending in '
             '01 Interface Song.flac.',
             [{'op': 'quick-setting', 'index': 2}, select('Interface Song'), {'op': 'save'}, select('Interface Song')],
             [located('Interface Song', 'The file saved under the name the default naming script gives it.')]),
        step('toolbar-labels', 'In the User Interface options, turn off the text labels under the toolbar icons and '
             'apply the options.',
             'The main toolbar shows its buttons as icons without text labels.',
             [{'op': 'options', 'page': 'User Interface'},
              {'op': 'set-check', 'name': 'Show text labels under icons', 'value': False},
              {'op': 'button', 'name': 'Make It So!'}, {'op': 'sleep', 'seconds': 1}]),
        step('log', 'Open the application\'s error/debug log.',
             'A log window is open and lists the application\'s log messages, among them messages about loading '
             'the folder '+area_path(key, 'inputs', 'ui')+'.',
             [{'op': 'press', 'key': 'Control+g'}, {'op': 'wait-window', 'title': 'Log View'}]),
        step('hide-panes', 'Close the log window, then hide the metadata view and the cover art view of the main '
             'window.',
             'The main window shows the file and album lists but neither the metadata view nor the cover art area.',
             [{'op': 'close-windows'}, {'op': 'menu', 'path': ['View', 'Metadata']},
              {'op': 'menu', 'path': ['View', 'Cover Art']}, {'op': 'sleep', 'seconds': .5}])],
        documents=[('ui', 'u1.flac', flac('Interface Song', artist='UI', albumartist='UI', album='UI Album',
                                          tracknumber='1'), None)],
        profile={'title': 'Interface', 'settings': SESSION_SETTINGS}, load=['ui'],
        start='the file Interface Song loaded from '+area_path(key, 'inputs', 'ui')+'; files are neither renamed '
              'nor moved when saving')


def build():
    return [sessions(), session_startup(), option_profiles(), cover_art(), removing(), setup_wizard(), config_backup(), script_files(),
            interface()]
