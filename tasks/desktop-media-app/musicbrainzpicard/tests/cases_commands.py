"""Remote commands of the running application (start.sh -e) and file loading, observed through the session the
product saves on exit (which files are loaded, where, and in which cluster)."""
import re

import fixtures
from harness import FILE_SECONDS
from scenario import expand, flac, items, m4a, mp3, needs, ogg, prepare, run_commands

FAMILY = 'remote-commands'


def loaded(ctx, session):
    return {'items': items(ctx, session)}


def add(suite, key, description, files, commands, settings=None, project=loaded, requires=(), quits_itself=False):
    suite.add(FAMILY, key, 'prepare', prepare(key, settings, files), channel='setup',
              description='Fresh instance, settings profile and documents for '+key)
    return suite.add(FAMILY, key, 'result', run_commands(key, commands, project, quits_itself),
                     description=description, needs=needs(key), requires=requires)


def add_action(suite, key, description, files, action, settings=None, requires=()):
    """A scenario whose scored step is its own action (not the session written on exit)."""
    suite.add(FAMILY, key, 'prepare', prepare(key, settings, files), channel='setup',
              description='Fresh instance, settings profile and documents for '+key)
    return suite.add(FAMILY, key, 'result', action, description=description, needs=needs(key), requires=requires)


def command_list(ctx):
    """The command names that "start.sh -e help" lists (one command per line, optionally bulleted)."""
    result = ctx.command('help')
    names = re.findall(r'(?m)^\s*(?:[-*\u2022]\s+)?([A-Z][A-Z0-9_]{2,})\b', str(result.get('stdout') or ''))
    return {'exit_code': result.get('exit_code'), 'commands': sorted(set(names))}


def written_log(key, commands, name):
    """The remote commands, then the log document WRITE_LOGS wrote into the output folder: whether it was written
    and whether it mentions the scenario's input folder (the argument of the LOAD that ran before)."""
    def action(ctx):
        for command, argument in commands:
            ctx.command(command, expand(ctx, key, argument))
        data = ctx.fetch('outputs', name, wait=FILE_SECONDS)
        if data is None:
            raise AssertionError(f'no log document {name} was written')
        return {'written': True, 'mentions_loaded_folder': f'{ctx.inputs}/{key}' in data.decode('utf-8', 'replace')}
    return action


def command_file(*lines):
    """A remote-command document; {base} is the scenario's input folder."""
    return lambda ctx, key: ('\n'.join(expand(ctx, key, line) for line in lines)+'\n').encode('utf-8')


def build(suite):
    three = [('', 'one.flac', flac('One')), ('', 'two.mp3', mp3('Two')), ('', 'three.ogg', ogg('Three'))]
    nested = [('a', 'top.flac', flac('Top')), ('a/b', 'middle.mp3', mp3('Middle')),
              ('a/b/c', 'deep.m4a', m4a('Deep')), ('a/b/c', 'deep2.ogg', ogg('Deep two'))]
    load_one = add(suite, 'load-single-file', 'LOAD with one file path loads exactly that file', three,
                   [('LOAD', '{base}/two.mp3')])
    add(suite, 'load-folder-recursive', 'LOAD with a folder loads the supported files of all its subfolders',
        nested, [('LOAD', '{base}/a')])
    add(suite, 'load-folder-flat', 'LOAD with a folder and "Include sub-folders when adding files" off loads only '
        'the folder\'s own files', nested, [('LOAD', '{base}/a/b')], settings={'recursively_add_files': False})
    add(suite, 'load-skips-documents', 'LOAD with a folder skips files that are not supported audio (text, '
        'image, profile)', [('', 'song.flac', flac('Song')), ('', 'notes.txt', b'liner notes\n'),
                            ('', 'cover.jpg', lambda ctx, key: fixtures.image('front.jpg')), ('', 'list.m3u', b'song.flac\n')],
        [('LOAD', '{base}')])
    hidden = [('', 'visible.flac', flac('Visible')), ('', '.hidden.mp3', mp3('Hidden')),
              ('.secret', 'inside.ogg', ogg('Inside'))]
    add(suite, 'load-hidden-included', 'By default LOAD includes hidden files and hidden folders', hidden,
        [('LOAD', '{base}')])
    add(suite, 'load-hidden-ignored', 'With "Ignore hidden files" LOAD skips hidden files and hidden folders',
        hidden, [('LOAD', '{base}')], settings={'ignore_hidden_files': True})
    regex = [('Live', 'concert.flac', flac('Concert')), ('Studio', 'demo take.flac', flac('Demo take')),
             ('Studio', 'final.mp3', mp3('Final')), ('Studio', 'DEMO-2.ogg', ogg('Demo two'))]
    add(suite, 'load-ignore-regex', 'LOAD skips files whose path matches the "Ignore file paths" regular '
        'expression', regex, [('LOAD', '{base}')], settings={'ignore_regex': '(?i)demo'})
    add(suite, 'load-ignore-regex-folder', 'The ignore expression is matched against the whole path, so a folder '
        'name excludes its files', regex, [('LOAD', '{base}')], settings={'ignore_regex': '/Live/'})
    add(suite, 'load-ignore-regex-invalid', 'An invalid ignore expression ignores nothing', regex,
        [('LOAD', '{base}')], settings={'ignore_regex': '[unclosed'})
    add(suite, 'load-twice', 'Loading the same file twice keeps one entry', three,
        [('LOAD', '{base}/one.flac'), ('LOAD', '{base}/one.flac'), ('LOAD', '{base}')])
    add(suite, 'load-file-url', 'LOAD accepts a file:// URL', three, [('LOAD', 'file://{base}/three.ogg')])
    add(suite, 'load-missing-then-present', 'LOAD of a missing file lists it as a file that failed to load, and '
        'later commands still run',
        three, [('LOAD', '{base}/missing.flac'), ('LOAD', '{base}/one.flac')])
    add(suite, 'command-names-case', 'Command names are case-insensitive', three,
        [('load', '{base}/one.flac'), ('Load', '{base}/two.mp3')])
    add(suite, 'unknown-command-ignored', 'An unknown command is ignored and the following commands still run',
        three, [('FROBNICATE', '{base}/one.flac'), ('LOAD', '{base}/three.ogg')])
    odd = [('', 'good.flac', flac('Good')), ('', 'UPPER.FLAC', flac('Upper case suffix')),
           ('', 'damaged.mp3', b'\x00garbage'*500), ('', 'mp3-named.ogg', mp3('Wrong suffix'))]
    add(suite, 'load-odd-files', 'Suffixes are matched without case; a damaged file stays listed; a file whose '
        'content does not match its suffix is dropped', odd, [('LOAD', '{base}')])
    unicode = [('Café Ünïcödé', 'Ünïcödé 曲.flac', flac('Unicode')), ('Café Ünïcödé', 'plain.mp3', mp3('Plain'))]
    add(suite, 'load-unicode-paths', 'Files with non-ASCII folder and file names load', unicode,
        [('LOAD', '{base}/Café Ünïcödé')])
    remove_one = add(suite, 'remove-one', 'REMOVE with the absolute path of a loaded file removes only that file',
                     three, [('LOAD', '{base}'), ('REMOVE', '{base}/two.mp3')])
    add(suite, 'remove-not-loaded', 'REMOVE of a path that is not loaded changes nothing', three,
        [('LOAD', '{base}/one.flac'), ('LOAD', '{base}/three.ogg'), ('REMOVE', '{base}/two.mp3')],
        requires=(remove_one,))
    add(suite, 'remove-all-then-load', 'REMOVE_ALL removes every file; a later LOAD works again', three,
        [('LOAD', '{base}'), ('REMOVE_ALL', ''), ('LOAD', '{base}/two.mp3')])
    album = [('', f'{n}.flac', flac(f'Track {n}', album='Shared Album', artist='Band')) for n in ('a1', 'a2')]
    singles = [('', 'loose.mp3', mp3('Loose', album='Lonely')), ('', 'other.ogg', ogg('Other'))]
    add(suite, 'remove-unclustered', 'After CLUSTER, REMOVE_UNCLUSTERED removes only the files left outside '
        'clusters', album+singles, [('LOAD', '{base}'), ('CLUSTER', ''), ('REMOVE_UNCLUSTERED', '')])
    add(suite, 'remove-saved-without-albums', 'REMOVE_SAVED only concerns album files and leaves unclustered files',
        three, [('LOAD', '{base}'), ('REMOVE_SAVED', '')], requires=(load_one,))
    add(suite, 'cluster-new-files', 'With "Automatically cluster all new files" loading clusters the files',
        album+singles, [('LOAD', '{base}')], settings={'cluster_new_files': True})
    lines = command_file('# load two files', '', '  LOAD "{base}/folder one/x.flac"', 'load {base}/y.mp3',
                         '# done')
    spaced = [('folder one', 'x.flac', flac('X')), ('', 'y.mp3', mp3('Y')), ('', 'z.ogg', ogg('Z'))]
    add(suite, 'from-file-basic', 'FROM_FILE runs the commands of a file: comments and blank lines are skipped, '
        'quoted paths keep spaces, names are case-insensitive', spaced+[('', 'commands.txt', lines)],
        [('FROM_FILE', '{base}/commands.txt')], project=loaded)
    add(suite, 'from-file-arguments', 'A command line with several arguments runs the command once per argument',
        spaced+[('', 'multi.txt', command_file('LOAD {base}/y.mp3 {base}/z.ogg'))],
        [('FROM_FILE', '{base}/multi.txt')])
    add(suite, 'from-file-nested', 'FROM_FILE inside a command file runs the other file\'s commands', spaced+[
        ('', 'outer.txt', command_file('LOAD {base}/z.ogg', 'FROM_FILE {base}/inner.txt')),
        ('', 'inner.txt', command_file('LOAD {base}/y.mp3'))], [('FROM_FILE', '{base}/outer.txt')])
    add(suite, 'from-file-circular', 'A command file that includes itself runs its other commands once', spaced+[
        ('', 'loop.txt', command_file('LOAD {base}/y.mp3', 'FROM_FILE {base}/loop.txt'))],
        [('FROM_FILE', '{base}/loop.txt')])
    add(suite, 'from-file-quit-stops', 'QUIT in a command file makes the application quit (saving its session) '
        'before the commands after it run', spaced+[
            ('', 'stop.txt', command_file('LOAD {base}/y.mp3', 'QUIT', 'LOAD {base}/z.ogg'))],
        [('FROM_FILE', '{base}/stop.txt')], project=loaded, quits_itself=True)
    add(suite, 'from-file-cluster', 'A command file can load and cluster', album+singles+[
        ('', 'cluster.txt', command_file('LOAD {base}', 'CLUSTER'))], [('FROM_FILE', '{base}/cluster.txt')])
    add_action(suite, 'remote-help', '"start.sh -e help" lists the remote commands', [], command_list)
    logs = add_action(suite, 'write-logs', 'WRITE_LOGS writes the log, which records the commands that ran',
                      three, written_log('write-logs', [('LOAD', '{base}'), ('WRITE_LOGS', '{outputs}/write-logs.log')],
                                         'write-logs.log'))
    add_action(suite, 'clear-logs', 'After CLEAR_LOGS the written log no longer holds the earlier messages', three,
               written_log('clear-logs', [('LOAD', '{base}'), ('CLEAR_LOGS', ''),
                                          ('WRITE_LOGS', '{outputs}/clear-logs.log')], 'clear-logs.log'),
               requires=(logs,))
    add(suite, 'session-options', 'The saved session records the profile\'s Rename files, Move files and Save tags '
        'settings', three, [('LOAD', '{base}/one.flac')],
        settings={'rename_files': True, 'move_files': True, 'enable_tag_saving': False},
        project=lambda ctx, session: {'options': (session or {}).get('options'), 'items': items(ctx, session)})
    return suite
