"""Tagger scripts: what running a script does to the tags a file saves.

Each probe is one small FLAC file whose title is the probe's id and whose other tags are the same for every probe.
The episode's settings hold one tagger script, "Probes", with one branch per probe, `$if($eq(%title%,<id>),<body>)`;
running it on all files and saving them shows the effect of every body on its own file: setting, unsetting and
deleting tags, multi-value handling, copying and merging, hidden variables, tag names with descriptions, and
script functions applied to tag values.
"""
from guispec import area_path, step, episode

BASE = {'ARTIST': 'The Beatles', 'ALBUM': 'abbey road', 'DATE': '1969-09-26', 'TRACKNUMBER': '7',
        'TOTALTRACKS': '17', 'GENRE': ['Rock', 'Pop', 'rock'], 'COMMENT': 'Old comment', 'MOOD': 'Calm',
        'COMPOSER': 'Lennon', 'PERFORMER': ['Ann Singer (lead vocals)', 'Bob Strummer (guitar)']}

PROBES = [
    ('s01', '$set(album,$upper(%album%))'),
    ('s02', '$set(comment,from %_filename% %_extension%)'),
    ('s03', '$setmulti(genre,Jazz; Blues; Soul)'),
    ('s04', '$set(genre,Jazz; Blues)'),
    ('s05', '$unset(comment)$set(subtitle,after unset)'),
    ('s06', '$delete(comment)$set(subtitle,after delete)'),
    ('s07', '$set(_hidden,secret)$set(mood,%_hidden%)'),
    ('s08', '$copy(lyricist,composer)'),
    ('s09', '$copymerge(genre,mood)'),
    ('s10', '$setmulti(genre,$unique(%genre%))'),
    ('s11', '$set(tracknumber,$num(%tracknumber%,3))'),
    ('s12', '$set(date,$year(%date%))'),
    ('s13', '$set(artist,$swapprefix(%artist%))'),
    ('s14', '$set(performer:piano,Cat Keys)'),
    ('s15', '$unset(performer:*)$set(subtitle,performers unset)'),
    ('s16', '$delete(performer:lead vocals)$set(subtitle,one performer deleted)'),
    ('s17', '$set(lyrics,Line one\\nLine two)'),
    ('s18', '$set(totaltracks,$add(%totaltracks%,1))'),
    ('s19', '$set(mood,)$set(subtitle,mood set empty)'),
    ('s20', '$set(MixedCase,value of mixed case)'),
    ('s21', '$set(comment:liner,Liner text)'),
    ('s22', '$set(~internal,x)$set(subtitle,tilde variable)'),
    ('s23', '$setmulti(artists,%artist%; Guest)'),
    ('s24', '$set(albumartist,$if2(%albumartist%,%artist%))'),
    ('s25', '$set(title,$title(%album%))'),
    ('s26', '$set(mood,$getmulti(%genre%,1))'),
    ('s27', '$set(work,$rreplace(%album%,\\(\\\\w+\\) \\(\\\\w+\\),\\\\2 \\\\1))'),
    ('s28', '$noop($set(mood,never))$set(subtitle,after noop)'),
    ('s29', '$if($gt(%tracknumber%,5),$set(mood,big),$set(mood,small))'),
    ('s30', '$foreach(%genre%,$set(grouping,%grouping%+%_loop_value%))'),
    ('s31', '$set(date,$dateformat(%date%,\\%Y.\\%m.\\%d))'),
    ('s32', '$set(comment,$truncate(%comment%,3))'),
    ('s33', '$copy(_tmp,genre)$unset(genre)$setmulti(genre,$reversemulti(%_tmp%))'),
    ('s34', '$delete(mood)$set(mood,Reborn)'),
    ('s35', '$set(website,https://example.org/a\\, b)'),
    ('s36', '$set(bpm,$div($mul(120,3),2))'),
    ('s37', '$setmulti(genre,Rock; ; Jazz)$cleanmulti(genre)'),
    ('s38', '$set(artist,$upper(%artist%))$set(artist,$lower(%artist%))'),
    ('s39', '$set(isrc,$replace(GB-AAA-87-00001,-,))'),
    ('s40', '$set(subtitle,<$len(%_nothing%)>)'),
    ('s41', '$setmulti(performer:,Plain One; Plain Two)'),
    ('s42', '$unset(comment:*)$set(subtitle,comments unset)'),
]
SCRIPT = 'Probes'


def fields(ident):
    out = [['TITLE', ident]]
    for key, value in BASE.items():
        for item in value if isinstance(value, list) else [value]:
            out.append([key, item])
    return out


def build():
    key = 'tagger-script-effects'
    folder = 'ts-probes'
    script = ''.join(f'$if($eq(%title%,{ident}),{body})' for ident, body in PROBES)
    documents = [(folder, f'{ident}.flac', {'audio': 'flac', 'tags': {'vorbis': {'fields': fields(ident)}}}, None)
                 for ident, _ in PROBES]
    checks = [{'kind': 'dump', 'path': f'inputs/{folder}/{ident}.flac',
               'description': f'Probe {ident}: the file saved after the script ran {body!r} on it.'}
              for ident, body in PROBES]
    profile = {'title': 'Tagger script probes', 'settings': {
        'file_save_warning': False, 'guess_tracknumber_and_title': False, 'ignore_file_mbids': True},
        'tagging': [{'title': SCRIPT, 'enabled': False, 'script': script}]}
    return [episode(key, 'tagger-scripts', [
        step('apply', f'Run the tagger script "{SCRIPT}" on all loaded files (for example on the Unclustered Files '
             'node), then save all loaded files.',
             'The script ran and the files were saved: no file is marked as changed; for example the file that was '
             'titled s25 is now titled Abbey Road, and selecting the file titled s01 shows Album ABBEY ROAD.',
             [{'op': 'select', 'text': 'Unclustered Files'}, {'op': 'run-script', 'target': 'Unclustered Files'},
              {'op': 'save'}, {'op': 'select', 'text': 's01', 'exact': True}], checks)],
        documents=documents, profile=profile, load=[folder],
        start=f'{len(PROBES)} FLAC files loaded from {area_path(key, "inputs", folder)}, titled s01 to '
              f's{len(PROBES):02d} and otherwise with the same tags (artist The Beatles, album abbey road, genres '
              'Rock, Pop and rock, a comment, a mood, a composer and two performers); the settings contain the '
              f'tagger script "{SCRIPT}", which changes each file\'s tags depending on its title')]
