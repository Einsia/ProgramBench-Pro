'''Libraries and scans: administration of the native library collection, scan permissions, scan targets and missing files.

The library that holds the music cannot be removed or moved (the product answers both with a server error, which is not
checked); renaming it is allowed. State that changes is chained with need(); denial and empty-result points are bound to
a positive point of the same episode.'''
from api_browse import LIBRARY

ROWS = {'_start': 0, '_end': 20}
FIELDS = ['name', 'path']
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def rollups(c, relaxed=False):
    '''The folder and file totals of the library and the folder count of the scan status: counting rules of their own
    (which folders and files count), checked once here and left out of every other observation.'''
    assert not relaxed, 'library checks are scored cases'
    library = c.native('GET', 'library/1')
    assert library['status'] == 200 and isinstance(library['body'], dict), 'library 1: HTTP %s' % library['status']
    return {'folders': library['body'].get('totalFolders'), 'files': library['body'].get('totalFiles'),
            'scanFolders': c.scan_state().get('folderCount')}


def full_scan(c, relaxed=False):
    '''A full scan requested by the administrator: the request is accepted and, once the scan has finished, the scan
    status reports the songs of the library.'''
    assert not relaxed, 'library checks are scored cases'
    reply = c.reply(c.subsonic('startScan', fullScan='true'))
    accepted = reply.get('status')
    c.settle(first=False, quiet=2.0, timeout=30.0)
    state = c.scan_state()
    return {'accepted': accepted, 'scanning': state.get('scanning'), 'count': state.get('count'), 'type': state.get('scanType')}


def build(s):
    nat, sub = s.nat, s.sub

    # -- reading the collection ------------------------------------------------------------------------------------
    listed = nat('library', 'list', 'admin', 'GET', 'library', params=ROWS, status=200, fields=LIBRARY)
    read = nat('library', 'read', 'first', 'GET', 'library/1', status=200, fields=LIBRARY)
    s.add('library', 'totals', 'folders-and-files', rollups, description='library folder and file totals and the scan folder count')
    scanned = s.add('library', 'startScan', 'full-by-admin', full_scan, description='subsonic startScan of a full scan by the administrator, then the scan status')
    COMPANIONS[nat('library', 'list', 'anonymous', 'GET', 'library', anonymous=True, params=ROWS, status=401)] = [listed]
    COMPANIONS[nat('library', 'list', 'ordinary-user', 'GET', 'library', 'bob', params=ROWS)] = [listed]
    COMPANIONS[nat('library', 'read', 'unknown-id', 'GET', 'library/9', status=404)] = [read]
    COMPANIONS[nat('library', 'missing', 'list', 'GET', 'missing', params=ROWS, status=200)] = [listed]

    # -- creating a library is checked on its input ----------------------------------------------------------------
    COMPANIONS[nat('library', 'create', 'missing-folder', 'POST', 'library', body={'name': 'Sub', 'path': '/music/NoSuchFolder'}, status=400)] = [listed]
    COMPANIONS[nat('library', 'create', 'without-name', 'POST', 'library', body={'path': '/music/Unicode'}, status=400)] = [listed]
    COMPANIONS[nat('library', 'create', 'duplicate-path', 'POST', 'library', body={'name': 'Dup', 'path': '/music'}, status=400)] = [listed]
    COMPANIONS[nat('library', 'create', 'by-bob', 'POST', 'library', 'bob', body={'name': 'Sub', 'path': '/music/Unicode'}, status=403)] = [listed]
    COMPANIONS[nat('library', 'update', 'by-bob', 'PUT', 'library/1', 'bob', body={'name': 'Hijack', 'path': '/music'}, status=403)] = [read]
    COMPANIONS[nat('library', 'update', 'anonymous', 'PUT', 'library/1', anonymous=True, body={'name': 'Hijack', 'path': '/music'}, status=401)] = [read]

    # -- renaming the library ---------------------------------------------------------------------------------------
    renamed = nat('library', 'update', 'rename', 'PUT', 'library/1', body={'name': 'Renamed', 'path': '/music'}, status=200, fields=FIELDS)
    COMPANIONS[renamed] = [need(nat('library', 'read', 'after-rename', 'GET', 'library/1', status=200, fields=LIBRARY), renamed)]
    need(nat('library', 'list', 'after-rename', 'GET', 'library', params=ROWS, status=200, fields=LIBRARY), renamed)
    need(sub('library', 'getMusicFolders', 'after-rename', 'getMusicFolders'), renamed)
    restored = need(nat('library', 'update', 'rename-back', 'PUT', 'library/1', body={'name': 'Music Library', 'path': '/music'}, status=200, fields=FIELDS), renamed)
    COMPANIONS[restored] = [need(sub('library', 'getMusicFolders', 'after-rename-back', 'getMusicFolders'), restored)]

    # -- scans ---------------------------------------------------------------------------------------------------------
    COMPANIONS[sub('library', 'startScan', 'by-bob', 'startScan', 'bob', expect=50)] = [scanned]
    COMPANIONS[sub('library', 'startScan', 'target-bad-format', 'startScan', target='bad', expect=0)] = [scanned]
    COMPANIONS[sub('library', 'startScan', 'target-unknown-library', 'startScan', target='9:', expect=70)] = [scanned]
    COMPANIONS[sub('library', 'getScanStatus', 'by-anonymous', 'getScanStatus', auth=False, expect=10)] = [scanned]
