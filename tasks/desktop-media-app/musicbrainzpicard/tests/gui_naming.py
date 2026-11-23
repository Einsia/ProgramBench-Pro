"""File naming: script functions and path rules, observed in the names the application gives files when saving.

Each probe is one small FLAC file whose title is the probe's id. The episode's naming script (imported as a profile
with renaming and moving to the output folder) contains one branch per probe, `$if($eq(%title%,<id>),<id>_[<expr>])`,
so the file of probe <id> is saved as `<folder>/<id>_[<result>].flac`; the result of every expression is checked on
its own file. Probes cover the script language's text, logic, arithmetic, comparison, multi-value, variable, date and
file-information functions, its escapes, and the rules that make tag values and script output safe file names; the
windows group replaces the characters Windows does not allow in file names with a table of its own.
"""
from guispec import area_path, step, episode

# The tags every probe file starts with; a probe can override or add tags.
BASE = {
    'ARTIST': 'The Beatles', 'ALBUMARTIST': 'Various Artists', 'ALBUM': 'abbey road', 'DATE': '1969-09-26',
    'TRACKNUMBER': '7', 'TOTALTRACKS': '17', 'DISCNUMBER': '1', 'TOTALDISCS': '2', 'GENRE': ['Rock', 'Pop', 'rock'],
    'ARTISTS': ['Paul', 'John'], 'COMMENT': '  spaced   out  text  ', 'MOOD': 'Calm',
    'PERFORMER': ['Ann Singer (lead vocals)', 'Bob Strummer (guitar)', 'Cat Keys (piano)'],
}

TEXT = [
    ('a01', '$upper(%album%)'), ('a02', '$lower(%artist%)'), ('a03', '$left(%artist%,3)'),
    ('a04', '$right(%artist%,4)'), ('a05', '$left(%artist%,x)'), ('a06', '$pad(%tracknumber%,4,0)'),
    ('a07', '$pad(abc,2,x)'), ('a08', '$strip(%comment%)'), ('a09', '$replace(%album%,road,street)'),
    ('a10', '$rreplace(%album%,\\(\\\\w+\\) \\(\\\\w+\\),\\\\2 \\\\1)'), ('a11', '$rreplace(%album%,[,x)'),
    ('a12', '$rsearch(%date%,\\(\\\\d{4}\\))'), ('a13', '$rsearch(%date%,\\(\\\\d+\\)-\\(\\\\d+\\),2)'),
    ('a14', '$rsearch(%date%,\\(?P<m>\\\\d\\\\d\\)-26,m)'), ('a15', '$rsearch(%album%,xyz)'),
    ('a16', '$num(%tracknumber%,3)'), ('a17', '$num(abc,3)'), ('a18', '$num(5,25)'), ('a19', '$trim(%comment%)'),
    ('a20', '$trim(xxhixx,x)'), ('a21', '$title(%album%)'), ('a22', "$title(o'neil AND mcdonald's 2nd)"),
    ('a23', '$len(%album%)'), ('a24', '$firstalphachar(%artist%)'), ('a25', '$firstalphachar(1999,#)'),
    ('a26', '$firstalphachar(,X)'), ('a27', '$initials(%artist%)'), ('a28', '$firstwords(%album%,7)'),
    ('a29', '$firstwords(%album%,5)'), ('a30', '$truncate(%artist%,5)'), ('a31', '$truncate(%artist%,4)'),
    ('a32', '$swapprefix(%artist%)'), ('a33', '$swapprefix(Les Misérables,A,The,Les)'),
    ('a34', '$delprefix(%artist%)'), ('a35', '$delprefix(Anthem,A)'), ('a36', '$reverse(%album%)'),
    ('a37', '$substr(%album%,2,5)'), ('a38', '$substr(%album%,-4,)'), ('a39', '$find(%album%,road)'),
    ('a40', '$find(%album%,zzz)'), ('a41', '$startswith(%album%,abb)'), ('a42', '$endswith(%album%,Road)'),
    ('a43', '$in(%album%,bey)'), ('a44', '$countryname(gb)'), ('a45', '$countryname(XX)'),
    ('a46', '$upper(straße)'), ('a47', '$lower(ÉCOLE)'), ('a48', '$len(naïve café)'), ('a49', '$endswith(%album%,road)'),
]

LOGIC = [
    ('b01', '$if(%album%,yes,no)'), ('b02', '$if(%nosuchtag%,yes,no)'), ('b03', '$if2(%nosuchtag%,%album%,x)'),
    ('b04', '$if2(,,)'), ('b05', '$noop(ignored)visible'), ('b06', '$add(%tracknumber%,3,10)'),
    ('b07', '$sub(10,%tracknumber%)'), ('b08', '$mul(3,4,5)'), ('b09', '$div(17,5)'), ('b10', '$div(5,0)'),
    ('b11', '$mod(17,5)'), ('b12', '$add(a,1)'), ('b13', '$sub(-3,4)'), ('b14', '$or(,,x)'), ('b15', '$and(a,,b)'),
    ('b16', '$not(%nosuchtag%)'), ('b17', '$eq(%tracknumber%,7)'), ('b18', '$ne(a,a)'), ('b19', '$lt(9,10)'),
    ('b20', '$lt(9,10,text)'), ('b21', '$lte(abc,ABD,nocase)'), ('b22', '$gt(2.5,10)'), ('b23', '$gte(b,a)'),
    ('b24', '$gt(10,9,int)'), ('b25', '$lt(x,1,int)'), ('b26', '$eq_any(%tracknumber%,3,7,9)'),
    ('b27', '$ne_all(%tracknumber%,3,9)'), ('b28', '$eq_all(a,a,a)'), ('b29', '$ne_any(a,a,b)'),
    ('b30', '$min(auto,10,9,100)'), ('b31', '$max(text,10,9,100)'), ('b32', '$min(nocase,b,A,c)'),
    ('b33', '$max(int,%genre%,1)'), ('b34', '$max(float,1.5,2.25)'), ('b35', '$len()'),
    ('b36', '$div(-7,2)'), ('b37', '$mod(-7,3)'), ('b38', '$gt(1e3,999)'), ('b39', '$eq(1,01)'),
    ('b40', '$eq_any(x)'), ('b41', '$and(a,b)'), ('b42', '$ne(a,b)'),
]

MULTI = [
    ('c01', '%genre%'), ('c02', '$lenmulti(%genre%)'), ('c03', '$getmulti(%genre%,1)'),
    ('c04', '$getmulti(%genre%,-1)'), ('c05', '$getmulti(%genre%,9)'), ('c06', '$inmulti(%genre%,Pop)'),
    ('c07', '$inmulti(%genre%,Po)'), ('c08', '$in(%genre%,Po)'), ('c09', '$join(%genre%,+)'),
    ('c10', '$slice(%genre%,1)'), ('c11', '$slice(%genre%,0,-1)'), ('c12', '$sortmulti(%genre%)'),
    ('c13', '$reversemulti(%genre%)'), ('c14', '$unique(%genre%)'), ('c15', '$unique(%genre%,1)'),
    ('c16', '$map(%genre%,$upper(%_loop_value%))'), ('c17', '$map(%genre%,%_loop_count%)'),
    ('c18', '$foreach(%genre%,$set(_acc,%_acc%<%_loop_value%>))%_acc%'),
    ('c19', '$set(_i,0)$while($lt(%_i%,4),$set(_i,$add(%_i%,1)))%_i%'),
    ('c20', '$while(1,$set(_n,%_loop_count%))%_n%'), ('c21', '$replacemulti(%genre%,rock,metal)'),
    ('c22', '$setmulti(_m,a; b; c)$lenmulti(%_m%)'), ('c23', '$setmulti(_m,a|b,|)$getmulti(%_m%,1)'),
    ('c24', '$set(_x,abc)$get(_x)'), ('c25', '$set(_x,abc)$unset(_x)<%_x%>'), ('c26', '$copy(_g,genre)$lenmulti(%_g%)'),
    ('c27', '$set(_a,x)$copymerge(_a,genre)%_a%'), ('c28', '$setmulti(_a,Rock; z)$copymerge(_a,genre)%_a%'),
    ('c29', '$setmulti(_a,Rock)$copymerge(_a,genre,1)%_a%'), ('c30', '$is_multi(%genre%)'),
    ('c31', '$is_multi(%album%)'), ('c32', '$setmulti(_c,one; ; two)$cleanmulti(_c)$lenmulti(%_c%)'),
    ('c33', '$performer(vocals)'), ('c34', '$performer(/^guitars?\\$/i)'), ('c35', '$performer()'),
    ('c36', '$performer(,+)'), ('c37', '$join(%artists%, & )'), ('c38', '$lenmulti(a; b; c)'),
    ('c39', '$getmulti(x; y; z,2)'), ('c40', '$set(_s,%genre%)$lenmulti(%_s%)'),
    ('c41', '$unset(performer:*)$performer()'), ('c42', '$delete(mood)<%mood%>'),
]

VARIABLES = [
    ('v01', '$year(%date%)'), ('v02', '$month(%date%)'), ('v03', '$day(26.09.1969,dmy)'),
    ('v04', '$dateformat(%date%,\\%d.\\%m.\\%Y)'), ('v05', '$dateformat(1969-13-01)'),
    ('v06', '$dateformat(09-26-1969,\\%Y \\%b,mdy)'), ('v07', '$year(1969)'), ('v08', '$month(1969)'),
    ('v09', '%_extension%'), ('v10', '%_filename%'), ('v11', '%_length%'), ('v12', '%_sample_rate%'),
    ('v13', '%_channels%'), ('v14', '%_bits_per_sample%'), ('v15', '%_bitrate%'), ('v16', '%_format%'),
    ('v17', '$matchedtracks()'), ('v18', '<$is_complete()>'), ('v19', '$is_audio()'), ('v20', '<$is_video()>'),
    ('v21', '$len($datetime(\\%Y))'), ('v22', '$right(%_dirname%,12)'), ('v23', '$get(ALBUM)'), ('v24', '%tracknumber%_%totaltracks%'),
    ('v25', '%discnumber% of %totaldiscs%'), ('v26', '$get_original(album)'), ('v27', '<$get_new(album)>'),
    ('v28', '%_totalalbumtracks%<%_multiartist%>'), ('v29', '%albumartist%'), ('v30', '%_filesize%'),
    ('v31', '$get(album)'),
]

SYNTAX = [
    ('d01', '\\$literal'), ('d02', '100\\%'), ('d03', 'a\\,b'), ('d04', '\\(x\\)'), ('d05', '%album%/%artist%'),
    ('d06', '%subtitle%', {'SUBTITLE': 'AC/DC live'}), ('d07', 'a:b*c?d"e<f>g|h'),
    ('d08', '%subtitle%', {'SUBTITLE': 'Part 2: Why?'}), ('d09', '/.hidden/%album%'),
    ('d10', 'ends with dot./x'), ('d11', 'CON/x'), ('d12', 'x'*300), ('d13', '%subtitle%', {'SUBTITLE': 'tab\there'}),
    ('d14', 'a//b'), ('d15', ' lead and trail /x'), ('d16', '%subtitle%', {'SUBTITLE': '  padded  '}),
    ('d17', '$if($eq(1,1),$if($eq(2,2),deep,),)'), ('d18', '%genre%'), ('d19', '$num(%tracknumber%,2). %album%'),
    ('d20', '%subtitle%', {'SUBTITLE': 'dots... here'}), ('d21', '%subtitle%', {'SUBTITLE': 'ünïcödé ✓'}),
    ('d22', '%subtitle%', {'SUBTITLE': 'back\\slash'}), ('d23', '%nosuchtag%'), ('d24', '%_nosuchvar%'),
]

WINDOWS = [
    ('w01', 'a:b'), ('w02', 'why?'), ('w03', 'star*'), ('w04', '<angle>'), ('w05', 'pipe|line'),
    ('w06', 'say "hi"'), ('w07', '%subtitle%', {'SUBTITLE': 'Part 2: Why?'}),
    ('w08', '%subtitle%', {'SUBTITLE': 'Mixed <*> "|"'}), ('w09', '$upper(%album%): live?'),
    ('w10', 'back\\\\slash'),
]
# Windows compatibility with a replacement table of its own (characters it does not list keep the default "_").
WIN_REPLACEMENTS = {':': ' -', '?': '', '*': '+', '<': '[', '>': ']', '|': '!'}

GROUPS = (('text', TEXT), ('logic', LOGIC), ('multi', MULTI), ('variables', VARIABLES), ('syntax', SYNTAX),
          ('windows', WINDOWS))
# Settings of a group besides renaming and moving.
GROUP_SETTINGS = {'windows': {'windows_compatibility': True, 'win_compat_replacements': WIN_REPLACEMENTS}}
GROUP_NOTES = {'windows': 'Windows compatibility is on with the replacements ' + ', '.join(
    f'{k} by "{v}"' for k, v in WIN_REPLACEMENTS.items()) + ' (other characters Windows does not allow become "_")'}
# Probes whose name part is empty count only together with a probe of the same function that gives a result, so an
# engine that answers unknown functions with an empty string does not score them.
# The probe each group's frontend acceptance shows, with the file name its expression gives.
SHOWN = {'text': ('a01', 'a01_[ABBEY ROAD].flac'), 'logic': ('b06', 'b06_[20].flac'),
         'multi': ('c09', 'c09_[Rock+Pop+rock].flac'), 'variables': ('v04', 'v04_[26.09.1969].flac'),
         'syntax': ('d02', 'd02_[100%].flac'), 'windows': ('w01', 'w01_[a -b].flac')}
COMPANIONS = {
    'a05': 'a03', 'a15': 'a12', 'a40': 'a39', 'a42': 'a49', 'a45': 'a44',
    'b04': 'b03', 'b10': 'b09', 'b12': 'b06', 'b15': 'b41', 'b18': 'b42', 'b20': 'b19', 'b22': 'b24', 'b25': 'b19',
    'b33': 'b31', 'b39': 'b17', 'b40': 'b26',
    'c05': 'c03', 'c07': 'c06', 'c31': 'c30', 'c41': 'c33',
    'v05': 'v04', 'v08': 'v02', 'v23': 'v31',
    'd23': 'd06', 'd24': 'd06',
}


def probes(entries):
    found = []
    for entry in entries:
        ident, expression = entry[0], entry[1]
        extra = entry[2] if len(entry) > 2 else {}
        found.append((ident, expression, extra))
    return found


def naming_script(entries):
    return ''.join(f'$if($eq(%title%,{ident}),{ident}_[{expression}])' for ident, expression, _ in entries)


def fields(ident, extra):
    tags = dict(BASE, **extra)
    out = [['TITLE', ident]]
    for key, value in tags.items():
        for item in value if isinstance(value, list) else [value]:
            out.append([key, item])
    return out


def build():
    episodes = []
    for group, entries in GROUPS:
        key = f'naming-functions-{group}'
        folder = f'nf-{group}'
        entries = probes(entries)
        documents = [(folder, f'{ident}.flac', {'audio': 'flac', 'tags': {'vorbis': {'fields': fields(ident, extra)}}},
                      None) for ident, _, extra in entries]
        profile = {'title': 'Naming probes', 'settings': {
            'rename_files': True, 'move_files': True, 'move_files_to': '{outputs}/'+folder, 'file_save_warning': False,
            'guess_tracknumber_and_title': False, **GROUP_SETTINGS.get(group, {})},
            'naming': {'title': f'Probes ({group})', 'script': naming_script(entries)}}
        checks = [{'kind': 'located', 'title': ident, 'description': f'The file of probe {ident} is saved with the '
                   f'name the naming script gives it for {expression!r}.'} for ident, expression, _ in entries]
        index = {ident: n+1 for n, (ident, _, _) in enumerate(entries)}
        requires = {f'state-{index[a]}': [f'state-{index[b]}'] for a, b in COMPANIONS.items() if a in index}
        shown, name = SHOWN[group]
        episodes.append(episode(key, 'naming-scripts', [
            step('save', 'Select all loaded files and save them; then select the file titled "'+shown+'" to show its '
                 'tags.',
                 f'The files are saved and none is marked as changed any more; the metadata view of the file titled '
                 f'"{shown}" shows its File Path {area_path(key, "outputs", folder+"/"+name)} (the name its naming-script '
                 f'expression gives).',
                 [{'op': 'select', 'text': 'Unclustered Files'}, {'op': 'save'},
                  {'op': 'select', 'text': shown, 'exact': True}], checks, requires=requires)],
            documents=documents, profile=profile, load=[folder],
            start=f'{len(entries)} files (titles {entries[0][0]} to {entries[-1][0]}) loaded from '
                  f'{area_path(key, "inputs", folder)}; the settings rename and move files to '
                  f'{area_path(key, "outputs", folder)} with a naming script that names each file after an '
                  'expression' + (f'; {GROUP_NOTES[group]}' if group in GROUP_NOTES else '')))
    return episodes
