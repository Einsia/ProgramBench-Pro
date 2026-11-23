"""Tag writing: the tags of the plan written to every tag format.

Each episode loads tagless files named after write cases ("t-title", "p-track-and-total", "s-date-year-only", ...)
and has one tagger script in its settings, "Write plan", with one branch per file name that sets exactly the tags of
that case. Running the script on all files and saving them writes each case to its own file, so a file's saved tags
are exactly what the application writes for that case in the episode's format and options. ID3v2.4, MP4 and ASF map
almost every tag in a way of their own and receive the whole plan. Most Vorbis cases follow one rule (the internal
tag name, upper-cased, as the field name), most APEv2 cases another (the internal name as the key) and most ID3v2.3
cases write the ID3v2.4 frames; these episodes receive the cases that depart from their rule and a few
representatives of it. The container episode writes one combined case to one file of every other container,
through the same script mechanism.
"""
from guispec import area_path, step, episode
import tagsets

SCRIPT = 'Write plan'
BASE = {'file_save_warning': False, 'guess_tracknumber_and_title': False, 'ignore_file_mbids': True}

# family key -> (file kind, suffix, label, extra settings, tags of the input files)
FAMILIES = {
    'vorbis': ('flac', 'flac', 'FLAC (Vorbis comments)', {}, {}),
    'id3v24': ('mp3', 'mp3', 'MP3 with ID3v2.4 (the default ID3 settings)', {}, {}),
    'id3v23': ('mp3', 'mp3', 'MP3 with ID3v2.3 (UTF-16 text, multiple values joined with "/")',
               {'write_id3v23': True, 'id3v2_encoding': 'utf-16', 'id3v23_join_with': '/'}, {}),
    'mp4': ('m4a', 'm4a', 'MP4 (M4A atoms)', {}, {}),
    # WMA files without any attribute carry no file information in the product, so every input has one attribute
    # the product does not map (kept unchanged when saving).
    'asf': ('wma', 'wma', 'WMA (ASF attributes; each file also has the unmapped attribute WM/ToolName)', {},
            {'asf': {'attributes': {'WM/ToolName': 'fixture'}}}),
    'apev2': ('wv', 'wv', 'WavPack (APEv2)', {}, {}),
}
# Representatives of a family's general rule, and the cases that depart from it (whole plan when not listed).
REPRESENTATIVES = ('t-title', 't-artists', 't-genre', 't-comment', 't-lyrics', 't-musicbrainz-albumid',
                   't-replaygain-track-gain', 't-my-custom-tag', 's-title-with-slash')
DEPARTURES = {
    'vorbis': ('t-totaltracks', 't-totaldiscs', 't-performer-vocals', 't-movement', 't-movementnumber',
               't-musicbrainz-recordingid', 't-musicbrainz-trackid', 't-r128-track-gain', 't-r128-album-gain',
               'p-track-and-total', 'p-disc-and-total', 'p-movement-number-and-total', 's-comment-with-description',
               's-comment-with-language', 's-lyrics-with-language', 's-performer-empty-role', 's-performer-two-roles'),
    'id3v23': ('t-artists', 't-albumartists', 't-date', 't-originaldate', 't-releasedate', 't-genre', 't-arranger',
               't-engineer', 't-producer', 't-mixer', 't-djmixer', 't-performer-vocals', 't-releasetype', 't-mood',
               't-musicbrainz-artistid', 's-date-year-only', 's-date-year-month', 's-performer-empty-role',
               's-performer-two-roles'),
    'apev2': ('t-albumartist', 't-tracknumber', 't-totaltracks', 't-discnumber', 't-totaldiscs', 't-date',
              't-remixer', 't-performer-vocals', 't-releasetype', 't-releasestatus', 't-website', 't-movement',
              't-movementnumber', 't-gapless', 't-podcast', 't-podcasturl', 't-show', 't-showsort',
              't-originalartist', 't-musicbrainz-recordingid', 't-musicbrainz-trackid', 't-r128-track-gain',
              't-r128-album-gain', 'p-track-and-total', 'p-disc-and-total', 'p-movement-number-and-total',
              's-date-year-only', 's-date-year-month', 's-comment-with-description', 's-comment-with-language',
              's-lyrics-with-language', 's-performer-empty-role', 's-performer-two-roles', 's-website-two'),
}
# The file each episode ends on and what its metadata view shows after saving (each format shows its own result).
EXAMPLES = {
    'vorbis': ('s-performer-two-roles', 'Performer [guitar] Guitarist G and Performer [piano] Pianist P; Pianist Q'),
    'id3v24': ('s-comment-with-language', 'Comment [deu] Deutscher Kommentar'),
    'id3v23': ('t-genre', 'Genre Rock/Jazz Fusion'),
    'mp4': ('t-gapless', 'Gapless Playback 1'),
    'asf': ('p-track-and-total', 'Track Number 7 and no Total Tracks'),
    'apev2': ('p-disc-and-total', 'Disc Number 3 and Total Discs 5'),
}
# Cases a format does not write at all: the saved file equals its input. They count only together with the
# family's first case (the writer works at all).
UNWRITTEN = {
    'vorbis': {'t-r128-track-gain', 't-r128-album-gain'},
    'mp4': {'t-totaltracks', 't-totaldiscs', 't-performer-vocals', 't-r128-track-gain', 't-r128-album-gain',
            's-comment-with-description', 's-comment-with-language', 's-performer-two-roles'},
    'apev2': {'t-totaltracks', 't-totaldiscs', 't-gapless', 't-podcast', 't-podcasturl', 't-show', 't-showsort',
              't-r128-track-gain', 't-r128-album-gain'},
    'asf': {'p-movement-number-and-total', 's-comment-with-description', 's-comment-with-language',
            's-performer-empty-role', 's-performer-two-roles', 't-arranger', 't-gapless', 't-license', 't-movement',
            't-movementnumber', 't-movementtotal', 't-my-custom-tag', 't-performer-vocals', 't-podcast',
            't-podcasturl', 't-r128-album-gain', 't-r128-track-gain', 't-releasedate', 't-show', 't-showmovement',
            't-showsort', 't-totaldiscs', 't-totaltracks', 't-writer'},
}
# The combined case written to one file of each further container.
CONTAINERS = (('ogg', 'ogg'), ('opus', 'opus'), ('spx', 'spx'), ('oggflac', 'oga'), ('alac', 'm4a'),
              ('tta', 'tta'), ('aiff', 'aiff'), ('wav', 'wav'), ('dsf', 'dsf'), ('dff', 'dff'), ('mp2', 'mp2'),
              ('ape', 'ape'), ('mpc', 'mpc'), ('ofr', 'ofr'), ('tak', 'tak'), ('aac', 'aac'), ('ac3', 'ac3'))


def escape(text):
    out = text.replace('\\', '\\\\')
    for ch in '$%(),':
        out = out.replace(ch, '\\'+ch)
    return out.replace('\n', '\\n')


def assignments(tags):
    parts = []
    for name, values in tags.items():
        if len(values) == 1:
            parts.append(f'$set({name},{escape(values[0])})')
        else:
            parts.append(f'$setmulti({name},{"; ".join(escape(v) for v in values)})')
    return ''.join(parts)


def plan_script(cases):
    return ''.join(f'$if($eq(%_filename%,{name}),{assignments(tags)})' for name, tags in cases.items())


def matrix(key, folder, files, script, settings, prepared, example, shown, description, inputs=None, unwritten=(),
           final=None):
    """example: the file (case name) the goal ends on, found by its name in the file list, or final: a goal ending
    and the recipe step that selects a file by its title."""
    documents = [(folder, f'{name}.{suffix}', {'audio': kind, 'tags': inputs or {}}, None)
                 for name, kind, suffix in files]
    names = [name for name, _kind, _suffix in files]
    requires = {f'state-{names.index(name)+1}': ['state-1'] for name in unwritten}
    checks = [{'kind': 'dump', 'path': f'inputs/{folder}/{name}.{suffix}',
               'description': f'{name}.{suffix}: the tags the application saved in {description(kind)} for '
                              f'this case.'} for name, kind, suffix in files]
    profile = {'title': 'Tag writing', 'settings': {**BASE, **settings},
               'tagging': [{'title': SCRIPT, 'enabled': False, 'script': script}]}
    if final is None:
        name = next(f'{n}.{suffix}' for n, _kind, suffix in files if n == example)
        final = (f'the file {name} (scroll the file list to reach it)', f'the metadata view of {name}',
                 {'op': 'find-file', 'name': example})
    return episode(key, 'tag-writing', [
        step('apply', f'Run the tagger script "{SCRIPT}" on all loaded files (for example on the Unclustered Files '
             f'node), then save all loaded files; then select {final[0]}.',
             f'The script ran and the files were saved: no file is marked as changed, and {final[1]} shows {shown}.',
             [{'op': 'select', 'text': 'Unclustered Files'}, {'op': 'run-script', 'target': 'Unclustered Files'},
              {'op': 'save'}, final[2]], checks, requires=requires)],
        documents=documents, profile=profile, load=[folder],
        start=f'{len(files)} files without tags loaded from {area_path(key, "inputs", folder)}; {prepared}')


def build():
    episodes = []
    plan = tagsets.plans()
    for family, (kind, suffix, label, settings, inputs) in FAMILIES.items():
        kept = set(DEPARTURES[family]) | set(REPRESENTATIVES) if family in DEPARTURES else set(plan)
        cases = {name: tags for name, tags in plan.items() if name in kept}
        files = [(name, kind, suffix) for name in cases]
        example, shown = EXAMPLES[family]
        episodes.append(matrix(
            f'tag-writing-{family}', f'write-{family}', files, plan_script(cases), settings,
            f'the files are {label}, each named after the case of tags it receives; the settings contain the tagger '
            f'script "{SCRIPT}", which sets, depending on the file name, the tags of that file\'s case', example, shown,
            lambda _kind, label=label: label, inputs, UNWRITTEN.get(family, ())))
    combined = {name: tagsets.WRITE[name] for name in tagsets.CONTAINER}
    files = [('c-'+kind, kind, suffix) for kind, suffix in CONTAINERS]
    episodes.append(matrix(
        'tag-writing-containers', 'write-containers', files, assignments(combined), {},
        'one file of each further container (Ogg Vorbis, Opus, Speex, Ogg FLAC, ALAC, TrueAudio, AIFF, WAVE, DSF, '
        'DSDIFF, MP2, Monkey\'s Audio, Musepack, OptimFROG, TAK, AAC, AC-3); the settings contain the tagger script '
        f'"{SCRIPT}", which sets the same tags on every file', None,
        f'Title {tagsets.WRITE["title"][0]} and Artist {tagsets.WRITE["artist"][0]}',
        lambda kind: f'its container ({kind})',
        final=('any one of the files', 'the metadata view of that file',
               {'op': 'select', 'text': tagsets.WRITE['title'][0], 'exact': True})))
    return episodes
