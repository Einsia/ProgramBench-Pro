"""Tag values written through sessions: one value plan per tag, chosen so that every value is distinct and some
contain characters outside ASCII.

WRITE is the full plan of single tags (each written alone to its own file, so a file's saved tags are exactly what
the product writes for that one tag); PAIRS are the tags that format writers combine (number and total) and
SPECIALS the variants whose value or name has a special form (dates, descriptions, empty roles, lists).
"""

WRITE = {
    'title': ['Tītle of the Song'],
    'artist': ['Ärtist One'],
    'album': ['Älbum Name'],
    'albumartist': ['Älbum Artist'],
    'artists': ['Ärtist One', 'Guest Twø'],
    'albumartists': ['Älbum Artist', 'Co Ärtist'],
    'artistsort': ['One, Ärtist'],
    'albumartistsort': ['Artist, Älbum'],
    'albumsort': ['Name, Älbum'],
    'titlesort': ['Song, Tītle of the'],
    'composersort': ['Compöser, The'],
    'tracknumber': ['7'],
    'totaltracks': ['13'],
    'discnumber': ['3'],
    'totaldiscs': ['5'],
    'discsubtitle': ['Disc Sübtitle'],
    'subtitle': ['Track Sübtitle'],
    'date': ['1987-06-05'],
    'originaldate': ['1977-08-09'],
    'originalyear': ['1976'],
    'releasedate': ['1988-01-02'],
    'genre': ['Rock', 'Jazz Fusion'],
    'composer': ['Compöser'],
    'lyricist': ['Lyricist Ł'],
    'writer': ['Wrïter W'],
    'conductor': ['Cönductor C'],
    'remixer': ['Remixer Ř'],
    'arranger': ['Arranger Ä'],
    'engineer': ['Engineer Ë'],
    'producer': ['Prödücer P'],
    'mixer': ['Mïxer M'],
    'djmixer': ['DJ Mïxer'],
    'performer:vocals': ['Vocalist Ṽ'],
    'comment': ['A plain cömment'],
    'lyrics': ['First line of lyrics\nSecond line of lyrics'],
    'media': ['Digital Media'],
    'releasetype': ['album', 'live'],
    'releasestatus': ['official'],
    'releasecountry': ['GB'],
    'script': ['Latn'],
    'language': ['eng'],
    'label': ['Label Łabel'],
    'catalognumber': ['CAT-0042'],
    'barcode': ['0123456789012'],
    'isrc': ['GBAAA8700001'],
    'asin': ['B000ASIN01'],
    'copyright': ['© 1987 Hölder'],
    'license': ['https://creativecommons.org/licenses/by/4.0/'],
    'website': ['https://example.org/artist'],
    'encodedby': ['Encöder Person'],
    'encodersettings': ['LAME -V0'],
    'bpm': ['128'],
    'key': ['Am'],
    'mood': ['Cälm'],
    'grouping': ['Gröup G'],
    'work': ['Wörk Title'],
    'movement': ['Mövement Name'],
    'movementnumber': ['2'],
    'movementtotal': ['4'],
    'showmovement': ['1'],
    'compilation': ['1'],
    'gapless': ['1'],
    'podcast': ['1'],
    'podcasturl': ['https://example.org/feed.xml'],
    'show': ['Shöw Name'],
    'showsort': ['Name, Shöw'],
    'originalalbum': ['Original Älbum'],
    'originalartist': ['Original Ärtist'],
    'originalfilename': ['original-file.wav'],
    'acoustid_id': ['3f2504e0-4f89-41d3-9a0c-0305e82c3301'],
    'acoustid_fingerprint': ['AQAAEyMYSWUSa0kqKclzSQ'],
    'musicip_puid': ['de2b3c50-0d6c-49e6-a3a1-4ed4bdc5c0e8'],
    'musicbrainz_recordingid': ['11111111-1111-4111-8111-111111111111'],
    'musicbrainz_trackid': ['22222222-2222-4222-8222-222222222222'],
    'musicbrainz_albumid': ['33333333-3333-4333-8333-333333333333'],
    'musicbrainz_artistid': ['44444444-4444-4444-8444-444444444444', '44444444-4444-4444-8444-444444444445'],
    'musicbrainz_albumartistid': ['55555555-5555-4555-8555-555555555555'],
    'musicbrainz_releasegroupid': ['66666666-6666-4666-8666-666666666666'],
    'musicbrainz_workid': ['77777777-7777-4777-8777-777777777777'],
    'musicbrainz_discid': ['xb9fF4OBvcJE0E_0gq7Ry6v0bv4-'],
    'musicbrainz_originalalbumid': ['88888888-8888-4888-8888-888888888888'],
    'musicbrainz_originalartistid': ['99999999-9999-4999-8999-999999999999'],
    'replaygain_track_gain': ['-6.50 dB'],
    'replaygain_track_peak': ['0.987654'],
    'replaygain_album_gain': ['-7.25 dB'],
    'replaygain_album_peak': ['0.999000'],
    'replaygain_track_range': ['5.12 dB'],
    'replaygain_album_range': ['6.34 dB'],
    'replaygain_reference_loudness': ['-18.00 LUFS'],
    'r128_track_gain': ['-1234'],
    'r128_album_gain': ['-567'],
    'my_custom_tag': ['Custöm value'],
}

PAIRS = {
    'track-and-total': {'tracknumber': ['7'], 'totaltracks': ['13']},
    'disc-and-total': {'discnumber': ['3'], 'totaldiscs': ['5']},
    'movement-number-and-total': {'movementnumber': ['2'], 'movementtotal': ['4']},
}

SPECIALS = {
    'date-year-only': {'date': ['1999']},
    'date-year-month': {'date': ['1999-04']},
    'comment-with-description': {'comment:liner notes': ['Described cömment']},
    'comment-with-language': {'comment:deu:': ['Deutscher Kommentar']},
    'lyrics-with-language': {'lyrics:fra:': ['Paroles en français']},
    'performer-empty-role': {'performer:': ['Plain Performer']},
    'performer-two-roles': {'performer:guitar': ['Guitarist G'], 'performer:piano': ['Pianist P', 'Pianist Q']},
    'website-two': {'website': ['https://example.org/one', 'https://example.org/two']},
    'title-with-slash': {'title': ['Before/After: Part 1']},
}

# Container-specific subsets for formats whose family mapping is already covered in full by another format.
CONTAINER = ('title', 'artist', 'albumartist', 'genre', 'tracknumber', 'date', 'comment', 'lyrics',
             'performer:vocals', 'musicbrainz_albumid', 'my_custom_tag')


def plans(names=None, pairs=True, specials=True):
    """{case name: tags} for files written one plan each."""
    found = {}
    for name in names or WRITE:
        found['t-'+name.replace(':', '-').replace('_', '-')] = {name: WRITE[name]}
    if pairs:
        for name, tags in PAIRS.items():
            found['p-'+name] = tags
    if specials:
        for name, tags in SPECIALS.items():
            found['s-'+name] = tags
    return found
