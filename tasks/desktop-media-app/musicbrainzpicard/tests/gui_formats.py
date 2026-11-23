"""Tag formats: reading every supported container and tag layout, and writing tags back.

Each episode ("formats-<family>") loads one file per case, whose tags use one layout of its family (legacy frames,
alternative or lower-case keys, special value forms, pictures). The settings clear existing tags and move saved files
to the output folder under their own file names, so after one save each file holds exactly what the application
read and wrote back; every case is checked on its own file in the output folder (an unsaved file is not there).
Tag writing has its own episodes (gui_writing).
"""
from guispec import area_path, step, episode


def id3(*frames, version=3, v1=False):
    return {'id3': {'version': version, 'frames': [list(f) for f in frames], 'v1': v1}}


def vorbis(*fields, pictures=()):
    return {'vorbis': {'fields': [list(f) for f in fields], 'pictures': [list(p) for p in pictures]}}


def mp4(**atoms):
    return {'mp4': {'atoms': {key.replace('_c_', '\xa9'): value for key, value in atoms.items()}}}


def ape(items):
    return {'ape': {'items': items}}


def asf(attributes):
    return {'asf': {'attributes': attributes}}


MBID = {name: f'{n}{n}{n}{n}{n}{n}{n}{n}-{n}{n}{n}{n}-4{n}{n}{n}-8{n}{n}{n}-{n*12}' for n, name in
        zip('123456789', ('recording', 'track', 'album', 'artist', 'albumartist', 'releasegroup', 'work',
                          'originalalbum', 'originalartist'))}
JPEG, PNG = 'front.jpg', 'back.png'

VORBIS = [
    ('basic-lowercase', 'flac', vorbis(('title', 'Basic title'), ('artist', 'Ärtist'), ('album', 'Älbum'),
                                       ('albumartist', 'Album Ärtist'), ('date', '2004-05-06'), ('tracknumber', '3'),
                                       ('tracktotal', '9'), ('discnumber', '1'), ('disctotal', '2'),
                                       ('genre', 'Rock'), ('genre', 'Pop'))),
    ('totaltracks-precedence', 'flac', vorbis(('TRACKNUMBER', '4'), ('TOTALTRACKS', '12'), ('TRACKTOTAL', '10'),
                                              ('DISCNUMBER', '2'), ('DISCTOTAL', '3'))),
    ('date-sanitized', 'flac', vorbis(('DATE', '2005-00-00'), ('ORIGINALDATE', '1999-07-00'),
                                      ('RELEASEDATE', '2006-02-00'))),
    ('performer-roles', 'flac', vorbis(('PERFORMER', 'Ann Singer (vocals)'), ('PERFORMER', 'Plain Player'),
                                       ('PERFORMER', 'Cat Keys (Live) (piano)'))),
    ('comment-descriptions', 'flac', vorbis(('COMMENT', 'Plain comment'), ('COMMENT', 'Liner text (liner notes)'))),
    ('unsynced-lyrics', 'flac', vorbis(('UNSYNCEDLYRICS', 'Lyric line one'))),
    ('movement-fields', 'flac', vorbis(('MOVEMENTNAME', 'Allegro'), ('MOVEMENT', '1'), ('MOVEMENTTOTAL', '4'),
                                       ('SHOWMOVEMENT', '1'), ('WORK', 'Symphony'))),
    ('musicbrainz-track-ids', 'flac', vorbis(('MUSICBRAINZ_TRACKID', MBID['recording']),
                                             ('MUSICBRAINZ_RELEASETRACKID', MBID['track']),
                                             ('MUSICBRAINZ_ALBUMID', MBID['album']),
                                             ('MUSICBRAINZ_ARTISTID', MBID['artist']))),
    ('ratings', 'flac', vorbis(('RATING:users@musicbrainz.org', '0.8'), ('RATING', '0.2'),
                               ('RATING:someone@example.org', '0.4'))),
    ('musicmagic-fingerprint', 'flac', vorbis(('FINGERPRINT', 'MusicMagic FingerprintABC123=='))),
    ('legacy-coverart', 'ogg', vorbis(('COVERART', '__FRONT_JPEG_BASE64__'))),
    ('flac-pictures', 'flac', vorbis(('ALBUM', 'Pictures'), pictures=((3, 'Front', JPEG), (4, '', PNG)))),
    ('channel-mask', 'flac', vorbis(('WAVEFORMATEXTENSIBLE_CHANNEL_MASK', '0x0004'), ('ARTIST', 'Mask keeper'))),
    ('custom-keys', 'flac', vorbis(('MY_NOTE', 'kept note'), ('another key', 'spaced key'), ('X-Tag', 'dashed'))),
    ('replaygain-r128', 'flac', vorbis(('REPLAYGAIN_TRACK_GAIN', '-6.00 dB'), ('R128_TRACK_GAIN', '-1234'),
                                       ('R128_ALBUM_GAIN', '-567'))),
    ('opus-basic', 'opus', vorbis(('title', 'Opus title'), ('artist', 'Opus artist'), ('R128_TRACK_GAIN', '-256'),
                                  pictures=((3, '', JPEG),))),
    ('speex-basic', 'spx', vorbis(('title', 'Speex title'), ('tracknumber', '2'), ('tracktotal', '5'))),
    ('ogg-flac-basic', 'oggflac', vorbis(('title', 'Ogg FLAC title'), ('genre', 'Jazz'), ('genre', 'Blues'))),
    ('ogg-vorbis-basic', 'ogg', vorbis(('title', 'Vorbis title'), ('albumartist', 'VA'), ('compilation', '1'),
                                       pictures=((3, 'cover', JPEG),))),
    ('slash-numbers', 'flac', vorbis(('TRACKNUMBER', '5/11'), ('DISCNUMBER', '1/3'))),
    ('duplicate-case-keys', 'flac', vorbis(('title', 'Dup keys'), ('Artist', 'First Ärtist'),
                                           ('ARTIST', 'Second Ärtist'))),
    ('lyrics-description', 'flac', vorbis(('TITLE', 'Described lyric'), ('LYRICS', 'Refrain text (refrain)'))),
    ('opus-two-pictures', 'opus', vorbis(('title', 'Opus pictures'),
                                         pictures=((3, 'Front side', JPEG), (4, 'Back side', PNG)))),
]

ID3_CASES = [
    ('v23-basic', 'mp3', id3(('TIT2', 'Basic title'), ('TPE1', 'Ärtist'), ('TALB', 'Älbum'), ('TPE2', 'Album Ärtist'),
                             ('TRCK', '3/9'), ('TPOS', '1/2'), ('TCON', 'Rock'), ('TCOM', 'Composer C'))),
    ('v23-dates', 'mp3', id3(('TYER', '1999'), ('TDAT', '0512'), ('TORY', '1977'))),
    ('v23-people-list', 'mp3', id3(('IPLS', [['arranger', 'Arr A'], ['engineer', 'Eng E'], ['producer', 'Pro P'],
                                             ['DJ-mix', 'DJ D'], ['mix', 'Mix M'], ['guitar', 'Gui G']]))),
    ('v24-people', 'mp3', id3(('TMCL', [['vocals', 'Voc V'], ['piano', 'Pia P']]),
                              ('TIPL', [['producer', 'Pro P'], ['engineer', 'Eng E']]), version=4)),
    ('legacy-sort-frames', 'mp3', id3(('TXXX', 'ALBUMARTISTSORT', 'Sort, Album'), ('TXXX', 'COMPOSERSORT', 'Sort, C'),
                                      ('TXXX', 'mood', 'Dreamy'), ('TXXX', 'RELEASEDATE', '2001-02-03'))),
    ('musicbrainz-freetext', 'mp3', id3(('TXXX', 'MusicBrainz Album Id', MBID['album']),
                                        ('TXXX', 'MusicBrainz Release Track Id', MBID['track']),
                                        ('TXXX', 'MusicBrainz Album Type', 'album'),
                                        ('TXXX', 'MusicBrainz Album Status', 'official'),
                                        ('UFID', 'http://musicbrainz.org', MBID['recording']))),
    ('replaygain-case', 'mp3', id3(('TXXX', 'replaygain_track_gain', '-6.00 dB'),
                                   ('TXXX', 'REPLAYGAIN_ALBUM_PEAK', '0.990000'))),
    ('comments', 'mp3', id3(('COMM', 'eng', '', 'Plain comment'), ('COMM', 'eng', 'liner', 'Described'),
                            ('COMM', 'deu', '', 'Deutsch'), ('COMM', 'eng', 'iTunNORM', ' 0000044E'))),
    ('lyrics', 'mp3', id3(('USLT', 'eng', '', 'Lyric line'), ('USLT', 'fra', 'refrain', 'Refrain'))),
    ('popularimeter', 'mp3', id3(('POPM', 'users@musicbrainz.org', 196, 3), ('POPM', 'other@example.org', 64, 0))),
    ('flags-and-links', 'mp3', id3(('TCMP', '1'), ('WOAR', 'https://example.org/a'),
                                   ('WCOP', 'https://example.org/l'), ('TBPM', '120'), ('TKEY', 'Am'))),
    ('numeric-genre', 'mp3', id3(('TCON', '(17)'), ('TLAN', 'eng'))),
    ('grouping-movement', 'mp3', id3(('TIT1', 'Group one'), ('GRP1', 'Group two'), ('MVNM', 'Adagio'),
                                     ('MVIN', '2/4'), version=4)),
    ('pictures', 'mp3', id3(('TALB', 'Pictures'), ('APIC', 3, 'Front', JPEG), ('APIC', 4, '', PNG))),
    ('id3v1-only', 'mp3', {'id3': {'version': 3, 'frames': [], 'v1': True, 'only_v1': True,
                                   'v1fields': {'title': 'V1 Title', 'artist': 'V1 Artist', 'album': 'V1 Album',
                                                'year': '1998', 'track': 4, 'genre': 17}}}),
    ('track-forms', 'mp3', id3(('TRCK', '05'), ('TPOS', '2'))),
    ('unknown-frames', 'mp3', id3(('TIT2', 'Has unknown frames'), ('TXXX', 'my_custom', 'custom value'),
                                  ('TSSE', 'LAME'), ('TENC', 'Encoder E'))),
    ('tta-basic', 'tta', id3(('TIT2', 'TTA title'), ('TRCK', '1/2'))),
    ('aiff-basic', 'aiff', id3(('TIT2', 'AIFF title'), ('TPE1', 'AIFF artist'))),
    ('wav-basic', 'wav', id3(('TIT2', 'WAV title'), ('TPE1', 'WAV artist'))),
    ('dsf-basic', 'dsf', id3(('TIT2', 'DSF title'), ('TCON', 'Classical'))),
    ('dff-basic', 'dff', id3(('TIT2', 'DFF title'), ('TCON', 'Classical'))),
    ('mp2-basic', 'mp2', id3(('TIT2', 'MP2 title'), ('TPE1', 'MP2 artist'))),
    ('genre-refinements', 'mp3', id3(('TCON', '(4)(17)Live'),)),
    ('wav-riff-and-id3', 'wav', {'riff': [['INAM', 'Info Title'], ['IART', 'Info Artist'], ['ICMT', 'Info comment']],
                                 **id3(('TIT2', 'ID3 Title'),)}),
    ('mp3-with-ape', 'mp3', {**id3(('TIT2', 'ID3 over APE'), ('TPE1', 'ID3 artist')),
                             **ape({'Title': 'APE title', 'Album': 'APE album'})}),
    ('txxx-multi-values', 'mp3', id3(('TXXX', 'ARTISTS', ['Ann', 'Bob']), ('TXXX', 'CATALOGNUMBER', ['C1', 'C2']),
                                     ('TXXX', 'Acoustid Id', '3f2504e0-4f89-41d3-9a0c-0305e82c3301'))),
    ('v24-dates', 'mp3', id3(('TDRC', '2004-05-06'), ('TDOR', '1999-02'), ('TDRL', '2005'), version=4)),
]

MP4_CASES = [
    ('basic-atoms', 'm4a', mp4(_c_nam='Basic title', _c_ART='Ärtist', _c_alb='Älbum', aART='Album Ärtist',
                               _c_day='2004-05-06', trkn=[[3, 9]], disk=[[1, 2]], _c_gen=['Rock', 'Pop'],
                               _c_wrt='Composer C')),
    ('comment-lyrics', 'm4a', mp4(_c_cmt='A comment', _c_lyr='Lyric line', _c_too='Encoder E', cprt='© Holder')),
    ('musicbrainz-freeform', 'm4a', mp4(**{'----:com.apple.iTunes:MusicBrainz Track Id': MBID['recording'],
                                           '----:com.apple.iTunes:MusicBrainz Album Id': MBID['album'],
                                           '----:com.apple.iTunes:MusicBrainz Release Track Id': MBID['track'],
                                           '----:com.apple.iTunes:ARTISTS': ['A1', 'A2']})),
    ('freeform-case', 'm4a', mp4(**{'----:com.apple.iTunes:replaygain_track_gain': '-6.00 dB',
                                    '----:com.apple.iTunes:REPLAYGAIN_ALBUM_PEAK': '0.990000',
                                    '----:com.apple.iTunes:releasedate': '2001-02-03'})),
    ('flags-numbers', 'm4a', mp4(cpil=True, pgap=True, pcst=True, tmpo=[120], _c_mvi=[2], _c_mvc=[4], shwm=[1])),
    ('sort-and-show', 'm4a', mp4(soal='Sort album', soaa='Sort album artist', soar='Sort artist', sonm='Sort title',
                                 soco='Sort composer', sosn='Sort show', tvsh='Show name', purl='https://example.org/f')),
    ('cover-art', 'm4a', mp4(_c_alb='Pictures', covr=[JPEG, PNG])),
    ('unknown-freeform', 'm4a', mp4(**{'----:com.apple.iTunes:MY_NOTE': 'kept note',
                                       '----:org.example:OTHER': 'other mean', 'desc': 'description atom'})),
    ('work-grouping', 'm4a', mp4(_c_grp='Group', _c_wrk='Work W', _c_mvn='Movement M', _c_dir='Director D',
                                 **{'----:com.apple.iTunes:initialkey': 'Am'})),
    ('track-without-total', 'm4a', mp4(trkn=[[5, 0]], disk=[[2, 0]])),
    ('alac-basic', 'alac', mp4(_c_nam='ALAC title', _c_ART='ALAC artist')),
    ('unknown-atoms', 'm4a', mp4(_c_nam='Unknown atoms', purd='2020-01-01 10:00:00', _c_too='Old encoder')),
    ('freeform-multi', 'm4a', mp4(**{'----:com.apple.iTunes:MOOD': ['Calm', 'Dark'],
                                     '----:com.apple.iTunes:LANGUAGE': 'eng'})),
]

ASF_CASES = [
    ('basic', 'wma', asf({'Title': 'Basic title', 'Author': 'Ärtist', 'WM/AlbumTitle': 'Älbum',
                          'WM/AlbumArtist': 'Album Ärtist', 'WM/Year': '2004', 'WM/TrackNumber': '3',
                          'WM/PartOfSet': '1/2', 'WM/Genre': ['Rock', 'Pop'], 'WM/Composer': 'Composer C'})),
    ('musicbrainz', 'wma', asf({'MusicBrainz/Track Id': MBID['recording'], 'MusicBrainz/Album Id': MBID['album'],
                                'MusicBrainz/Release Track Id': MBID['track'], 'MusicBrainz/Album Type': 'album'})),
    ('people-sort', 'wma', asf({'WM/Writer': 'Lyricist L', 'WM/Conductor': 'Conductor C', 'WM/ModifiedBy': 'Remixer R',
                                'WM/AlbumSortOrder': 'Sort album', 'WM/ArtistSortOrder': 'Sort artist'})),
    ('rating-compilation', 'wma', asf({'WM/SharedUserRating': [75], 'WM/IsCompilation': [True]})),
    ('pictures', 'wma', asf({'WM/AlbumTitle': 'Pictures', 'WM/Picture': [[3, '', JPEG], [4, '', PNG]]})),
    ('unknown-attributes', 'wma', asf({'Title': 'Has unknown', 'WM/MyOwnTag': 'dropped?', 'Description': 'Comment D'})),
    ('original-dates', 'wma', asf({'WM/OriginalReleaseTime': '1977-08-09', 'WM/OriginalReleaseYear': '1977',
                                   'WM/OriginalAlbumTitle': 'Orig album'})),
    ('replaygain-case', 'wma', asf({'replaygain_track_gain': '-6.00 dB', 'REPLAYGAIN_ALBUM_PEAK': '0.990000'})),
    ('dword-numbers', 'wma', asf({'Title': 'Dword numbers', 'WM/TrackNumber': [5], 'WM/BeatsPerMinute': [120]})),
    ('picture-description', 'wma', asf({'Title': 'Band picture', 'WM/Picture': [[8, 'Band photo', PNG]]})),
]

APE_CASES = [
    ('basic', 'wv', ape({'Title': 'Basic title', 'Artist': 'Ärtist', 'Album': 'Älbum', 'Album Artist': 'Album Ärtist',
                         'Year': '2004-05-06', 'Track': '3/9', 'Disc': '1/2', 'Genre': ['Rock', 'Pop']})),
    ('year-sanitized', 'wv', ape({'Year': '2005-00-00'})),
    ('performer-comment', 'wv', ape({'Performer': ['Ann Singer (vocals)', 'Plain Player'],
                                     'Comment': ['Plain', 'Liner (liner notes)']})),
    ('translated-keys', 'wv', ape({'MixArtist': 'Remixer R', 'Weblink': 'https://example.org/w',
                                   'DiscSubtitle': 'Disc sub', 'CatalogNumber': 'CAT-1', 'Original Artist': 'Orig'})),
    ('musicbrainz', 'wv', ape({'musicbrainz_trackid': MBID['recording'], 'musicbrainz_releasetrackid': MBID['track'],
                               'MUSICBRAINZ_ALBUMSTATUS': 'official', 'MUSICBRAINZ_ALBUMTYPE': 'album'})),
    ('cover-art', 'wv', ape({'Album': 'Pictures', 'Cover Art (Front)': ['binary', 'front.jpg', JPEG],
                             'Cover Art (Back)': ['binary', 'back.png', PNG]})),
    ('key-case', 'wv', ape({'TITLE': 'Upper key', 'artist': 'lower key', 'My Note': 'custom'})),
    ('ape-basic', 'ape', ape({'Title': 'APE title', 'Artist': 'APE artist'})),
    ('mpc-basic', 'mpc', ape({'Title': 'MPC title', 'Track': '2'})),
    ('ofr-basic', 'ofr', ape({'Title': 'OFR title', 'Genre': 'Jazz'})),
    ('tak-basic', 'tak', ape({'Title': 'TAK title', 'Album': 'TAK album'})),
    ('aac-basic', 'aac', ape({'Title': 'AAC title', 'Artist': 'AAC artist'})),
    ('ac3-basic', 'ac3', ape({'Title': 'AC3 title', 'Artist': 'AC3 artist'})),
    ('multi-values', 'wv', ape({'Artist': ['Ann', 'Bob'], 'Genre': ['Jazz', 'Blues']})),
    ('lowercase-cover', 'wv', ape({'Title': 'Lower cover', 'cover art (front)': ['binary', 'front.jpg', JPEG]})),
    ('replaygain-case', 'wv', ape({'REPLAYGAIN_TRACK_GAIN': '-6.00 dB', 'replaygain_album_peak': '0.990000',
                                   'MP3GAIN_MINMAX': '100,200'})),
]

FAMILIES = (('vorbis', 'Vorbis comments (FLAC, Ogg)', VORBIS, 'basic-lowercase.flac'),
            ('id3', 'ID3 (MP3, TTA, AIFF, WAVE, DSF, DSDIFF)', ID3_CASES, 'v23-basic.mp3'),
            ('mp4', 'MP4 atoms (M4A)', MP4_CASES, 'basic-atoms.m4a'),
            ('asf', 'ASF attributes (WMA)', ASF_CASES, 'basic.wma'),
            ('ape', 'APEv2 (WavPack, Monkey\'s Audio, Musepack, OptimFROG, TAK, AAC, AC-3)', APE_CASES,
             'basic.wv'))
# The file each save checkpoint ends on (a layout the application converts) and what its metadata view shows.
SAVED = {
    'vorbis': ('totaltracks-precedence', 'Track Number 4, Total Tracks 12, Disc Number 2 and Total Discs 3'),
    'id3': ('v23-people-list', 'Arranger Arr A, Engineer Eng E, Producer Pro P, DJ-Mixer DJ D, Mixer Mix M and '
            'Performer [guitar] Gui G'),
    'mp4': ('flags-numbers', 'Compilation (iTunes) 1, Gapless Playback 1, Podcast 1, BPM 120, Movement Number 2, '
            'Movement Count 4 and Show Work & Movement 1'),
    'asf': ('people-sort', 'Lyricist Lyricist L, Conductor Conductor C, Remixer Remixer R, Album Sort Order Sort '
            'album and Artist Sort Order Sort artist'),
    'ape': ('translated-keys', 'Remixer Remixer R, Artist Website https://example.org/w, Disc Subtitle Disc sub, '
            'Catalog Number CAT-1 and Original Artist Orig'),
}
SUFFIX = {'flac': 'flac', 'ogg': 'ogg', 'opus': 'opus', 'spx': 'spx', 'oggflac': 'oga', 'mp3': 'mp3', 'mp2': 'mp2',
          'tta': 'tta', 'aiff': 'aiff', 'wav': 'wav', 'dsf': 'dsf', 'dff': 'dff', 'm4a': 'm4a', 'alac': 'm4a',
          'wma': 'wma', 'wv': 'wv', 'ape': 'ape', 'mpc': 'mpc', 'ofr': 'ofr', 'tak': 'tak', 'aac': 'aac', 'ac3': 'ac3'}
SHOWN = {
    'vorbis': 'Title "Basic title", Artist "Ärtist", Album "Älbum", Album Artist "Album Ärtist", Date 2004-05-06, '
              'Track Number 3, Total Tracks 9, Disc Number 1, Total Discs 2 and Genre with the two values Rock and Pop',
    'id3': 'Title "Basic title", Artist "Ärtist", Album "Älbum", Album Artist "Album Ärtist", Track Number 3, '
           'Total Tracks 9, Disc Number 1, Total Discs 2, Genre Rock and Composer "Composer C"',
    'mp4': 'Title "Basic title", Artist "Ärtist", Album "Älbum", Album Artist "Album Ärtist", Date 2004-05-06, '
           'Track Number 3, Total Tracks 9, Disc Number 1, Total Discs 2, Genre with the values Rock and Pop and '
           'Composer "Composer C"',
    'asf': 'Title "Basic title", Artist "Ärtist", Album "Älbum", Album Artist "Album Ärtist", Date 2004, '
           'Track Number 3, Disc Number 1, Total Discs 2, Genre with the values Rock and Pop and Composer "Composer C"',
    'ape': 'Title "Basic title", Artist "Ärtist", Album "Älbum", Album Artist "Album Ärtist", Date 2004-05-06, '
           'Track Number 3, Total Tracks 9, Disc Number 1, Total Discs 2 and Genre with the values Rock and Pop',
}


def read_episode(family, label, cases, shown_file):
    key = f'formats-{family}'
    folder = f'read-{family}'
    documents = [(folder, f'{name}.{SUFFIX[kind]}', {'audio': kind, 'tags': tags}, None) for name, kind, tags in cases]
    profile = {'title': 'Rewrite', 'settings': {
        'clear_existing_tags': True, 'rename_files': True, 'move_files': True,
        'move_files_to': '{outputs}/'+folder, 'file_save_warning': False, 'guess_tracknumber_and_title': False,
        'ignore_file_mbids': True},
        'naming': {'title': 'By extension', 'script': '%_extension%/%_filename%'}}
    checks = []
    for name, kind, _tags in cases:
        suffix = SUFFIX[kind]
        checks.append({'kind': 'dump', 'path': f'outputs/{folder}/{suffix}/{name}.{suffix}',
                       'description': f'{name}.{suffix}: saved and moved to the output folder with existing tags '
                                      f'cleared, the file holds exactly the tags the application read from its '
                                      f'{label} layout and wrote back.'})
    saved, saved_tags = SAVED[family]
    saved_file = next(f'{name}.{SUFFIX[kind]}' for name, kind, _tags in cases if name == saved)
    return episode(key, 'tag-formats', [
        step('show', f'Select the file whose title is "Basic title" (the file {shown_file} in the folder '
             f'{area_path(key, "inputs", folder)}) to show its tags.',
             f'The metadata view lists the tags read from {shown_file}: {SHOWN[family]}.',
             [{'op': 'select', 'text': 'Basic title', 'exact': True}]),
        step('save', f'Save all loaded files; then select the file {saved_file}.',
             f'The files are saved and moved: no file is marked as changed or failed, and the metadata view of '
             f'{saved_file} shows {saved_tags}, with its File Path in '
             f'{area_path(key, "outputs", folder+"/"+saved_file.rsplit(".", 1)[1])}.',
             [{'op': 'select', 'text': 'Unclustered Files'}, {'op': 'save'}, {'op': 'find-file', 'name': saved}],
             checks)],
        documents=documents, profile=profile, load=[folder],
        start=f'{len(cases)} files in {label} layouts loaded from {area_path(key, "inputs", folder)}; the settings '
              f'clear existing tags when saving and move saved files to {area_path(key, "outputs", folder)} '
              'into a folder per file type, keeping their file names')


def build():
    return [read_episode(*family) for family in FAMILIES]
