"""picard-cli: option profiles (list, import, export) and the CLI's own help and version output.

Every scenario starts from a fresh instance, uploads its profile documents and runs picard-cli. A scenario scores
the import (exit status and the messages the CLI prints) and, separately, the stored result as the CLI itself
reports it: the profile list and a backup export of each listed profile. Messages are compared line by line after
replacing document-folder prefixes, generated UUIDs and the export date, without Python traceback blocks (the runtime
gives the CLI an empty standard input, so a yes/no prompt ends the run); exports are compared as parsed TOML.
"""
import re

import fixtures
from harness import DATE, UUID, MissingDependency

FAMILY = 'profiles-cli'
LOG_LINE = re.compile(r'^[DIWE]: \d\d:\d\d:\d\d')
LISTED = re.compile(r'^\s+(.*) \[(enabled|disabled)\] \(id: ([0-9a-f-]{36})\)\s*$')


def without_tracebacks(lines):
    """Lines without Python traceback blocks: a block's frames name the implementation's own files and lines, so
    only the exit status and the CLI's own messages are compared (a crash at a prompt still shows as exit status 1
    after the prompt)."""
    out, skipping = [], False
    for line in lines:
        if line.startswith('Traceback (most recent call last):'):
            skipping = True
            continue
        if skipping:
            if (not line.strip() or line.startswith((' ', '\t'))
                    or line.startswith(('During handling of the above exception', 'The above exception was'))):
                continue
            skipping = False  # the exception line ends the block
            continue
        out.append(line)
    return out


class Normalizer:
    """Document paths, the export date and UUIDs the scenario did not give itself are replaced by stable names."""

    def __init__(self, ctx, given=()):
        self.ctx, self.given = ctx, set(given)

    def text(self, value):
        value = self.ctx.normalize(value)
        value = UUID.sub(lambda m: m.group(0) if m.group(0) in self.given else '<uuid>', value)
        return DATE.sub('<date>', value)

    def lines(self, text):
        kept = [line for line in without_tracebacks(str(text or '').splitlines())
                if line.strip() and not LOG_LINE.match(line) and not line.startswith('qt.')]
        return [self.text(line.rstrip()) for line in kept]

    def value(self, value):
        if isinstance(value, dict):
            return {k: self.value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.value(v) for v in value]
        if isinstance(value, str):
            return self.text(value)
        return value


def outcome(ctx, result, given=()):
    if 'error' in result and 'exit_code' not in result:
        raise AssertionError('picard-cli could not be run: '+str(result['error'])[:300])
    norm = Normalizer(ctx, given)
    return {'exit_code': result.get('exit_code'), 'stdout': norm.lines(result.get('stdout')),
            'stderr': norm.lines(result.get('stderr'))}


def parse_toml(text):
    import tomli
    try:
        return tomli.loads(text)
    except Exception as exc:
        raise AssertionError(f'the export is not valid TOML: {exc}') from None


def stored(ctx, given=()):
    """The profiles picard-cli lists, each with its backup export (parsed)."""
    norm = Normalizer(ctx, given)
    listing = ctx.cli('profiles', 'list')
    rows = []
    for line in str(listing.get('stdout') or '').splitlines():
        match = LISTED.match(line)
        if match:
            title, state, identifier = match.groups()
            exported = ctx.cli('profiles', 'export', identifier, '--mode', 'backup')
            document = parse_toml(exported.get('stdout') or '') if exported.get('exit_code') == 0 else None
            rows.append({'title': title, 'state': state, 'export': norm.value(document)})
    return {'list': norm.lines(listing.get('stdout')), 'profiles': rows}


def add(suite, key, description, documents, steps, given=(), state=True):
    """documents: {name: bytes or callable(ctx)}; steps: list of picard-cli argument lists ({inputs}, {outputs})."""
    def prepare(ctx):
        ctx.reset()
        for name, data in documents.items():
            ctx.upload(name, data(ctx) if callable(data) else data, folder=key)
        ctx.state['scenario'] = key
        return {'prepared': key}

    def needs(ctx):
        if ctx.state.get('scenario') != key:
            raise MissingDependency('the preparation of scenario '+key+' did not complete')

    def run(ctx):
        observed = []
        for args in steps:
            expanded = [a.format(inputs=f'{ctx.inputs}/{key}', outputs=ctx.outputs) for a in args]
            observed.append(outcome(ctx, ctx.cli(*expanded), given))
        ctx.state['ran'] = key
        return {'steps': observed}
    suite.add(FAMILY, key, 'prepare', prepare, channel='setup', description='Fresh instance and documents for '+key)
    first = suite.add(FAMILY, key, 'messages', run, description=description+' (exit status and messages)',
                      needs=needs)
    if state:
        def result(ctx):
            if ctx.state.get('ran') != key:
                raise MissingDependency('the picard-cli step of '+key+' did not run')
            return stored(ctx, given)
        suite.add(FAMILY, key, 'stored', result, description=description+' (stored profiles as listed and '
                  'exported)', needs=needs)
    return first


def import_args(name, *flags, yes=True):
    return [*(['--yes'] if yes else []), 'profiles', 'import', '{inputs}/'+name, *flags]


PROFILE = fixtures.profile


def build(suite):
    add(suite, 'list-empty', 'Listing profiles of a fresh configuration', {}, [['profiles', 'list']], state=False)
    add(suite, 'import-minimal', 'Importing a profile with only a title creates a disabled profile', {
        'p.toml': PROFILE('Minimal')}, [import_args('p.toml')])
    add(suite, 'import-enabled', 'Importing with --enable creates an enabled profile', {
        'p.toml': PROFILE('Enabled one', {'rename_files': True})}, [import_args('p.toml', '--enable')])
    add(suite, 'import-settings-types', 'Boolean, integer, text and list settings are stored and exported in key '
        'order', {'p.toml': PROFILE('Typed', {
            'write_id3v23': True, 'id3v23_join_with': '; ', 'session_autosave_interval_min': 15,
            'preserved_tags': ['comment', 'lyrics'], 'ignore_regex': '\\.bak$', 'max_genres': 7,
            'va_name': 'Divers', 'windows_compatibility': False})}, [import_args('p.toml')])
    add(suite, 'import-unknown-settings', 'Unrecognised setting names are skipped with a warning', {
        'p.toml': PROFILE('Unknown keys', {'rename_files': True, 'no_such_option': 1, 'another_typo': 'x'})},
        [import_args('p.toml')])
    add(suite, 'import-non-profile-settings', 'Settings that are not part of profiles are skipped with a warning', {
        'p.toml': PROFILE('Not in profiles', {'ui_language': 'de', 'fpcalc_threads': 3, 'clear_existing_tags': True})},
        [import_args('p.toml')])
    add(suite, 'import-out-of-range', 'Out-of-range numbers are corrected to the nearest bound with a warning', {
        'p.toml': PROFILE('Bounds', {'session_autosave_interval_min': 5000, 'server_port': 0, 'max_genres': 101,
                                     'cover_image_quality': -5, 'query_limit': 50})}, [import_args('p.toml')])
    add(suite, 'import-invalid-toml', 'A document that is not TOML is refused', {
        'p.toml': b'[profile\ntitle = "Broken"\n'}, [import_args('p.toml')])
    add(suite, 'import-missing-profile-section', 'A document without a [profile] section is refused', {
        'p.toml': b'[settings]\nrename_files = true\n'}, [import_args('p.toml')])
    add(suite, 'import-missing-title', 'A [profile] section without a title is refused', {
        'p.toml': b'[profile]\nformat_version = 1\n'}, [import_args('p.toml')])
    add(suite, 'import-future-format', 'A newer profile format version is refused', {
        'p.toml': PROFILE('Future', extra_profile={'format_version': 2}).replace(b'format_version = 1\n', b'')},
        [import_args('p.toml')])
    add(suite, 'import-format-version-text', 'A format version that is not an integer is refused', {
        'p.toml': b'[profile]\ntitle = "Text version"\nformat_version = "1"\n'}, [import_args('p.toml')])
    add(suite, 'import-settings-not-table', 'A [settings] value that is not a table is refused', {
        'p.toml': b'settings = 3\n[profile]\ntitle = "Flat"\n'}, [import_args('p.toml')])
    add(suite, 'import-missing-file', 'Importing a document that does not exist fails', {},
        [import_args('absent.toml')], state=False)
    add(suite, 'import-duplicate-title', 'A second profile with the same title gets a numbered title', {
        'a.toml': PROFILE('Twin', {'rename_files': True}), 'b.toml': PROFILE('Twin', {'move_files': True}),
        'c.toml': PROFILE('Twin', {'delete_empty_dirs': False})},
        [import_args('a.toml'), import_args('b.toml'), import_args('c.toml')])
    given = '0f6c2b8e-61b3-4c39-9d8e-5f7f0c1d2a3b'
    add(suite, 'import-keeps-given-id', 'A profile id given in the document is kept; importing it again creates a '
        'new id', {'p.toml': PROFILE('With id', {'rename_files': True}, extra_profile={'id': given})},
        [import_args('p.toml'), import_args('p.toml')], given=(given,))
    add(suite, 'import-naming-script', 'A custom file naming script is registered and exported with the profile', {
        'p.toml': PROFILE('Naming', {'rename_files': True}, naming={
            'title': 'Album folders', 'script': '$if2(%albumartist%,%artist%)/%album%/$num(%tracknumber%,2) %title%',
            'author': 'Tester', 'description': 'Folders per album', 'version': '1.2'})}, [import_args('p.toml')])
    add(suite, 'import-naming-preset', 'A naming section that names a preset selects the preset without copying it',
        {'p.toml': PROFILE('Preset naming', naming={'id': 'Preset 2', 'title': 'Preset 2', 'preset': True,
                                                    'script': '%title%'})}, [import_args('p.toml')])
    add(suite, 'import-naming-incomplete', 'A naming section without a script is skipped with a warning', {
        'p.toml': PROFILE('Half naming', {'rename_files': True}, naming={'title': 'No script'})},
        [import_args('p.toml')])
    scripts = [{'title': 'Upper titles', 'script': '$set(title,$upper(%title%))'},
               {'title': 'Comment', 'script': '$set(comment,checked)', 'enabled': False}]
    add(suite, 'import-tagger-explicit', 'Tagger scripts with an explicit enable switch are imported as given', {
        'p.toml': PROFILE('Scripts on', tagging=scripts, enable_tagger_scripts=True)}, [import_args('p.toml')])
    add(suite, 'import-tagger-explicit-off', 'An explicit disabled switch keeps tagger scripting off', {
        'p.toml': PROFILE('Scripts off', tagging=scripts, enable_tagger_scripts=False)}, [import_args('p.toml')])
    add(suite, 'import-tagger-yes', 'Shared tagger scripts are enabled when --yes confirms', {
        'p.toml': PROFILE('Shared scripts', tagging=scripts)}, [import_args('p.toml')])
    add(suite, 'import-tagger-no-enable', 'With --no-enable-tagger-scripts shared scripts are imported but tagger '
        'scripting stays off', {'p.toml': PROFILE('Shared kept off', tagging=scripts)},
        [import_args('p.toml', '--no-enable-tagger-scripts')])
    add(suite, 'import-tagger-prompt', 'Without --yes the enable question is answered no when there is no input', {
        'p.toml': PROFILE('Shared prompt', tagging=scripts)}, [import_args('p.toml', yes=False)])
    add(suite, 'import-tagger-duplicates', 'Duplicate tagger scripts (same title and text) are imported once with a '
        'warning; entries without title or text are skipped', {'p.toml': PROFILE('Dupes', tagging=[
            {'title': 'One', 'script': '$set(genre,Rock)'}, {'title': 'One', 'script': '$set(genre,Rock)'},
            {'title': 'One', 'script': '$set(genre,Pop)'}, {'title': '', 'script': '$noop()'},
            {'title': 'Empty', 'script': ''}], enable_tagger_scripts=True)}, [import_args('p.toml')])
    add(suite, 'import-upgrade-old-names', 'Settings of an older Picard version are upgraded on import', {
        'p.toml': PROFILE('From 2.x', {'dont_write_tags': True, 'windows_compatible_filenames': False,
                                       'max_tags': 7, 'toolbar_multiselect': True,
                                       'selected_file_naming_script_id': 'Preset 3'},
                          extra_profile={'picard_version': '2.13.3'})}, [import_args('p.toml')])
    add(suite, 'import-upgrade-genres', 'Old genre options are renamed and folksonomy tags enable genres', {
        'p.toml': PROFILE('Old genres', {'folksonomy_tags': True, 'min_tag_usage': 40, 'join_tags': ' / ',
                                         'only_my_tags': True}, extra_profile={'picard_version': '2.0.4'})},
        [import_args('p.toml')])
    add(suite, 'import-upgrade-release-types', 'Old release type scores become preferred and discouraged types', {
        'p.toml': PROFILE('Old scores', raw_settings=[
            'release_type_scores = [["Album", 0.9], ["Live", 0.7], ["Single", 0.5], ["Compilation", 0.1], '
            '["Other", 0.0]]'], extra_profile={'picard_version': '2.13.0'})}, [import_args('p.toml')])
    add(suite, 'import-upgrade-standardize', 'An old standardize-artists switch becomes the artist names option', {
        'p.toml': PROFILE('Old standardize', {'standardize_artists': True, 'standardize_instruments': True,
                                              'artist_locales': ['fr', 'en']},
                          extra_profile={'picard_version': '2.12.0'})}, [import_args('p.toml')])
    add(suite, 'import-current-version-no-upgrade', 'Settings of the current version are not upgraded', {
        'p.toml': PROFILE('Current', {'dont_write_tags': True, 'enable_tag_saving': True},
                          extra_profile={'picard_version': '3.0.3.final0'})}, [import_args('p.toml')])
    add(suite, 'import-replace', 'Importing with --replace replaces the settings of an existing profile', {
        'a.toml': PROFILE('Base', {'rename_files': True, 'move_files': True}),
        'b.toml': PROFILE('Replacement', {'ascii_filenames': True})},
        [import_args('a.toml', '--enable'), import_args('b.toml', '--replace', 'Base')])
    add(suite, 'import-replace-missing', 'Replacing a profile that does not exist fails', {
        'a.toml': PROFILE('Lonely', {'rename_files': True})},
        [import_args('a.toml', '--replace', 'Nothing like it')])
    add(suite, 'import-replace-ambiguous', 'A partial name matching several profiles is refused', {
        'a.toml': PROFILE('Studio A'), 'b.toml': PROFILE('Studio B'), 'c.toml': PROFILE('Other')},
        [import_args('a.toml'), import_args('b.toml'), import_args('c.toml', '--replace', 'Studio')])
    add(suite, 'import-replace-prompt', 'Without --yes a replacement asks first and is cancelled without input', {
        'a.toml': PROFILE('Keep me', {'rename_files': True}), 'b.toml': PROFILE('Would replace', {'move_files': True})},
        [import_args('a.toml'), import_args('b.toml', '--replace', 'Keep me', yes=False)])
    add(suite, 'list-several', 'The list shows every profile, newest first, with its state and totals', {
        'a.toml': PROFILE('First'), 'b.toml': PROFILE('Second'), 'c.toml': PROFILE('Third')},
        [import_args('a.toml', '--enable'), import_args('b.toml'), import_args('c.toml', '--enable'),
         ['profiles', 'list']])
    share = PROFILE('Shareable', {'move_files_to': '{outputs}', 'rename_files': True, 'listenbrainz_token': 'secret',
                                  'proxy_username': 'me'}, tagging=scripts, enable_tagger_scripts=True)
    add(suite, 'export-share', 'A share export leaves out personal settings, disabled scripts and the id', {
        'p.toml': lambda ctx: share.replace(b'{outputs}', ctx.outputs.encode())},
        [import_args('p.toml'), ['profiles', 'export', 'Shareable']])
    add(suite, 'export-to-file', 'Exporting to a file writes the TOML there and reports it', {
        'p.toml': PROFILE('To file', {'rename_files': True, 'file_save_warning': False})},
        [import_args('p.toml'), ['profiles', 'export', 'To file', '-o', '{outputs}/exported.toml', '--mode', 'backup'],
         ['--yes', 'profiles', 'export', 'To file', '-o', '{outputs}/exported.toml'],
         ['profiles', 'export', 'To file', '-o', '{outputs}/exported.toml']])
    add(suite, 'export-partial-match', 'Export finds a profile by part of its title or the start of its id; no '
        'match and several matches are errors', {
            'a.toml': PROFILE('Classical night'), 'b.toml': PROFILE('Classical day'), 'c.toml': PROFILE('Jazz')},
        [import_args('a.toml'), import_args('b.toml'), import_args('c.toml'), ['profiles', 'export', 'jaz'],
         ['profiles', 'export', 'classical'], ['profiles', 'export', 'Opera']], state=False)
    add(suite, 'cli-help', 'picard-cli without a command prints its help; profiles without a verb prints the '
        'profiles help', {}, [[], ['profiles']], state=False)
    add(suite, 'cli-version', 'picard-cli --version prints the product version', {}, [['--version']], state=False)
    add(suite, 'cli-unknown-option', 'An unknown picard-cli option is an error', {},
        [['profiles', 'list', '--bogus']], state=False)
    return suite
