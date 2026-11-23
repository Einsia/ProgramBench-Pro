"""Shared building blocks of the program scenarios: a fresh instance with its own settings profile, uploaded
documents, remote commands, and the session the application saves when it quits.

Every scenario starts from a fresh instance (runtime reset), imports its settings as a profile with the product's
picard-cli (the session folder is the output folder, so the session the product saves on exit can be read), restarts
the application so the settings apply, and uploads its documents into a folder of its own. The scored step then
drives the product and reads what it wrote.
"""
import fixtures
from harness import MissingDependency, SESSION_NAME


def lazy(kind, tags):
    """A fixture made only when it is uploaded (the manifest is built without generating audio)."""
    return lambda ctx, key: fixtures.audio_file(kind, tags)


def flac(title, **tags):
    fields = [('TITLE', title)]+[(key.upper(), value) for key, value in tags.items()]
    return lazy('flac', {'vorbis': {'fields': fields}})


def mp3(title, **tags):
    frames = [('TIT2', title)]
    names = {'artist': 'TPE1', 'album': 'TALB', 'albumartist': 'TPE2', 'tracknumber': 'TRCK', 'date': 'TDRC'}
    for key, value in tags.items():
        frames.append((names[key], value))
    return lazy('mp3', {'id3': {'version': 4, 'frames': frames}})


def ogg(title, **tags):
    fields = [('TITLE', title)]+[(key.upper(), value) for key, value in tags.items()]
    return lazy('ogg', {'vorbis': {'fields': fields}})


def m4a(title, **tags):
    names = {'artist': '\xa9ART', 'album': '\xa9alb', 'albumartist': 'aART'}
    atoms = {'\xa9nam': title, **{names[key]: value for key, value in tags.items()}}
    return lazy('m4a', {'mp4': {'atoms': atoms}})


def prepare(key, settings=None, files=(), profile_title='Scenario settings'):
    """Setup action: fresh instance, settings profile, restart, documents under inputs/<key>/."""
    def action(ctx):
        ctx.reset()
        values = {'session_folder_path': ctx.outputs, 'file_save_warning': False, **(settings or {})}
        document = ctx.upload(f'{key}.toml', fixtures.profile(profile_title, values), folder='_profiles')
        result = ctx.cli('--yes', 'profiles', 'import', document, '--enable')
        if result.get('exit_code') != 0:
            raise AssertionError('the settings profile was not imported: '+str(result)[:300])
        ctx.restart()
        for folder, name, data in files:
            if callable(data):
                data = data(ctx, key)
            ctx.upload(name, data, folder='/'.join(part for part in (key, folder) if part))
        ctx.state['scenario'] = key
        return {'prepared': key}
    return action


def needs(key):
    def check(ctx):
        if ctx.state.get('scenario') != key:
            raise MissingDependency('the preparation of scenario '+key+' did not complete')
    return check


def expand(ctx, key, text):
    return text.format(inputs=ctx.inputs, outputs=ctx.outputs, base=f'{ctx.inputs}/{key}')


def items(ctx, session, *, tags=False):
    """Loaded files as the saved session lists them: document path, location and cluster (sorted by path; the
    product's list order is the order files finished loading)."""
    rows = []
    for item in (session or {}).get('items') or []:
        if not isinstance(item, dict):
            raise AssertionError('a session item is not a mapping')
        location = item.get('location') or {}
        row = {'path': ctx.normalize(str(item.get('file_path'))), 'location': location.get('type')}
        if location.get('type') == 'cluster':
            row['cluster'] = [location.get('cluster_title'), location.get('cluster_artist')]
        if tags:
            row['tags'] = ((item.get('metadata') or {}).get('tags')) or {}
        rows.append(row)
    return sorted(rows, key=lambda r: r['path'])


def run_commands(key, commands, project, quits_itself=False):
    """Scored action: the remote commands, then QUIT (unless the commands quit the application themselves) and the
    session the product saved."""
    def action(ctx):
        previous_session = ctx.fetch('outputs', SESSION_NAME) if quits_itself else None
        for name, argument in commands:
            ctx.command(name, expand(ctx, key, argument))
        session = ctx.quit_session(quits_itself=quits_itself, previous_session=previous_session)
        return project(ctx, session)
    return action
