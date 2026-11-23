'''Reviewed user goals, acceptance conditions, public setup and program checks of the GUI episodes.

Reference recipes implement these specifications. Goals are authored here and are never produced by translating a
recorded click trace. Setup items are unscored public preparation with ids (any success status). A point that only
verifies a rejection or an unavailable view names, in `requires`, a positive point of the same episode that proves the
feature exists. Read-only views carry no program check: a read of the product API is not the state of a view.
'''
from harness import PASSWORDS

BOOTSTRAP = {'id': 'fx-bootstrap', 'bootstrap': True}
PAGE = {'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}
DAVE = 'Dave-Local-2026!'
CAROL_NEW = 'Carol-New-2026!'
SHARES = {'_start': 0, '_end': 50, '_sort': 'createdAt', '_order': 'DESC'}


def find(key, path, **where):
    '''Unscored setup: look up the one object with these values and keep it for later setup items and checks.'''
    return {'id': 'fx-find-' + key, 'api': 'native', 'path': path, 'params': {'_start': 0, '_end': 100}, 'where': where, 'save': key}


def make(key, path, body, actor='admin', save=None):
    return {'id': 'fx-' + key, 'api': 'native', 'method': 'POST', 'path': path, 'body': body, 'actor': actor,
            **({'save': save} if save else {})}


def call(key, op, actor='admin', **query):
    return {'id': 'fx-' + key, 'api': 'subsonic', 'op': op, 'actor': actor, 'query': query}


def read(path, fields=(), expected=None, actor='admin', status=200, where=None, params=None, save=None,
         collection=False):
    return {'api': 'native', 'method': 'GET', 'path': path, 'actor': actor, 'params': params, 'status': status,
            'save': save, 'fields': list(fields), 'expected': expected, 'where': where, 'collection': collection}


def sub(op, extract=None, fields=(), expected=None, actor='admin', password=None, query=None, collection=False):
    return {'api': 'subsonic', 'op': op, 'extract': extract, 'actor': actor, 'password': password,
            'query': query or {}, 'status': 200, 'fields': list(fields), 'expected': expected, 'where': None,
            'collection': collection, 'save': None}


def login(user, password):
    return {'api': 'login', 'user': user, 'password': password, 'status': 200, 'fields': ['username', 'isAdmin'],
            'expected': {'username': user, 'isAdmin': user == 'admin'}, 'where': None, 'collection': False,
            'save': None}


def tracks(titles):
    return read('playlist/{{playlist.id}}/tracks', ['title'], [{'title': t} for t in titles],
                params={'_start': 0, '_end': 50}, collection=True)


def step(key, goal, acceptance, recipe, checks=(), visible=(), depends=(), action_required=True, requires=()):
    return {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': recipe, 'checks': list(checks),
            'visible': list(visible), 'depends_on': list(depends), 'action_required': action_required,
            'requires': list(requires)}


def episode(key, feature, steps, setup=(), actor='admin', bootstrap=True, seconds=None):
    items = ([dict(BOOTSTRAP)] if bootstrap else []) + list(setup)
    order = [cp['id'] for cp in steps]
    for cp in steps:
        # A setup item that runs before a later checkpoint is a prerequisite of that checkpoint and the ones after it.
        ids = [item['id'] for item in items if order.index(item.get('before', order[0])) <= order.index(cp['id'])]
        cp['assertions'] = [{'id': key + '/' + cp['id'] + '/visible', 'channel': 'frontend', 'method': 'agent',
                             'requirement': cp['acceptance']}]
        for i, check in enumerate(cp['checks']):
            cp['assertions'].append({'id': key + '/' + cp['id'] + '/state-%d' % (i + 1), 'channel': 'backend',
                                     'method': 'program', 'check': check,
                                     'requirement': check.get('description', 'The independently read public product '
                                                                             'state matches the requested checkpoint.')})
        # requires: 'checkpoint/visible' or 'checkpoint/state-N' of this episode.
        bound = [key + '/' + x for x in cp.pop('requires')]
        if bound:
            cp['assertions'][0]['requires'] = bound
        cp['depends_on'] = ['setup:' + i for i in ids] + cp['depends_on']
    accounts = {actor: PASSWORDS[actor]} if actor else {}
    session = ('Sign in with the supplied account before authenticated goals; this is unscored preparation.' if actor
               else 'Start unauthenticated. Only sign in or create an account when the checkpoint explicitly asks you to.')
    return {'id': key, 'feature': feature, 'execution': 'gui',
            'initial_state': 'Fresh application process and empty DATA_DIR in its first-run state; the listed public '
                             'setup then creates the administrator, two ordinary accounts and the scanned music library.'
                             if bootstrap else 'Fresh application process and empty DATA_DIR in its first-run state: no '
                                               'accounts and an empty music library.',
            'setup': items, 'inputs': {'account': actor, 'credentials': accounts}, 'actor': actor, 'session': session,
            'allowed_equivalents': ['Different visible labels, page layouts, inline or dialog editors and ordinary '
                                    'navigation routes are valid.',
                                    'Known application addresses (# routes below /app/) may be entered in the browser; '
                                    'no API browsing.'],
            'forbidden_bypasses': ['Do not use APIs, developer tools, source, private files, or hidden application state '
                                   'to perform GUI goals.', 'Do not manually recreate a missing product command.'],
            # seconds: a few episodes give the evaluator long pages to read and get a larger time budget.
            'budget': {'calls': min(160, 45 + 25 * len(steps)), 'seconds': seconds or min(1800, 480 + 180 * len(steps)),
                       'tokens': min(1_500_000, 350_000 + 180_000 * len(steps))},
            'checkpoints': steps}


def build():
    episodes = []

    def add(*args, **kwargs):
        episodes.append(episode(*args, **kwargs))

    add('first-run-admin', 'first-run', [
        step('created', "Open the application at /app/. It has no accounts yet. Create the administrator account with the "
                        "username 'admin' and the password 'Admin-Local-2026!', repeating the password in the confirmation field.",
             'The administrator is created and signed in: the application shows its album list, empty with a message that '
             'there are no albums yet, instead of the account creation or sign-in form.',
             [{'op': 'create-admin', 'username': 'admin', 'password': PASSWORDS['admin']}],
             [login('admin', PASSWORDS['admin'])], visible=['No Albums yet'])], actor=None, bootstrap=False)

    # Sign-in: two refused attempts, then the account signs in. The refusals count only together with the sign-in.
    add('sign-in', 'authentication', [
        step('wrong-password', "Open the application at /app/ and sign in with the username 'bob' and the password "
                               "'Wrong-Password-2026!'.",
             'The sign-in is refused: the sign-in form is still shown and no album browsing view is shown.',
             [{'op': 'sign-in', 'username': 'bob', 'password': 'Wrong-Password-2026!', 'valid': False}],
             visible=['Password'], requires=['signed-in/visible']),
        step('unknown-user', "Sign in with the username 'nobody' and the password 'Whatever-2026!'.",
             'The sign-in is refused: the sign-in form is still shown and no album browsing view is shown.',
             [{'op': 'sign-in', 'username': 'nobody', 'password': 'Whatever-2026!', 'valid': False}],
             visible=['Password'], requires=['signed-in/visible']),
        step('signed-in', "Sign in with the username 'bob' and the password '%s'." % PASSWORDS['bob'],
             'Bob is signed in: the album browsing views are shown instead of the sign-in form.',
             [{'op': 'sign-in', 'username': 'bob', 'password': PASSWORDS['bob'], 'valid': True}], visible=['Albums'])],
        actor=None)

    add('browse-albums', 'browsing', [
        step('grid', 'Open the list of all albums (Albums, then All in the navigation).',
             'Seven albums are listed, each with its album artist: [Unknown Album] ([Unknown Artist]), Café Ω '
             '(Ünïcode Ärtist), First Album (Alpha Artist), First Album (Delta Duo), Mixtape (Various Artists), Second '
             'Album (Beta Band) and Third Album (Gamma Trio).',
             [{'op': 'goto', 'path': '/app/#/album/all'}], visible=['Café Ω', 'Mixtape', 'Third Album'],
             action_required=False),
        step('detail', "Open the album 'Second Album' by Beta Band from the album list.",
             'The album page of Second Album by Beta Band lists its three songs: Intro, Drift and Reprise.',
             [{'op': 'open-album', 'title': 'Second Album', 'artist': 'Beta Band'}], visible=['Intro', 'Drift', 'Reprise'])],
        seconds=1500)

    add('song-search', 'search', [
        step('filter', "Open the list of songs (Songs in the navigation) and filter it by the text 'Single' with the "
                       "list's search field.",
             'Exactly the three songs whose titles contain Single are listed: Single A, Single B and Single C; the other '
             'songs are not shown.',
             [{'op': 'goto', 'path': '/app/#/song'}, {'op': 'filter-songs', 'text': 'Single'}],
             visible=['Single A', 'Single B', 'Single C']),
        step('none', "Replace the filter text with 'zzz'.",
             'No songs are listed: the list shows no rows or a no-results message, and Single A, Single B and Single C '
             'are gone.',
             [{'op': 'filter-songs', 'text': 'zzz'}], depends=['filter'], requires=['filter/visible'])], seconds=1200)

    add('playlist-lifecycle', 'playlists', [
        step('created', "Create a playlist named 'Evening Mix' with the comment 'Songs for the evening' (Playlists, then "
                        "create) and save it.",
             'The playlist Evening Mix is created and listed among the playlists.',
             [{'op': 'create-playlist', 'name': 'Evening Mix', 'comment': 'Songs for the evening'}],
             [read('playlist', ['name', 'comment'], {'name': 'Evening Mix', 'comment': 'Songs for the evening'},
                   where={'name': 'Evening Mix'}, params=PAGE, save='playlist')], visible=['Evening Mix']),
        step('add-songs', "In the list of songs select the songs 'Opening' and 'Echo' and add them to the existing playlist "
                          "'Evening Mix' with the add to playlist action.",
             'The songs Opening and Echo are in the playlist: the playlist Evening Mix lists exactly those two songs.',
             [{'op': 'add-to-playlist', 'titles': ['Opening', 'Echo'], 'playlist': 'Evening Mix'}],
             [tracks(['Opening', 'Echo'])], visible=['Opening', 'Echo'], depends=['created']),
        step('renamed', "Change the name of the playlist 'Evening Mix' to 'Late Night' (edit it from the playlist list or its "
                        "page) and save.",
             'The playlist is now named Late Night and still contains Opening and Echo.',
             [{'op': 'rename-playlist', 'old': 'Evening Mix', 'new': 'Late Night'}],
             [read('playlist/{{playlist.id}}', ['name', 'comment'],
                   {'name': 'Late Night', 'comment': 'Songs for the evening'}), tracks(['Opening', 'Echo'])],
             visible=['Late Night'], depends=['created', 'add-songs']),
        step('deleted', "Delete the playlist 'Late Night' from the playlist list.",
             'The playlist is gone: the playlist list no longer shows Late Night.',
             [{'op': 'delete-playlist', 'name': 'Late Night'}],
             [read('playlist/{{playlist.id}}', status=404)], depends=['renamed'], requires=['created/state-1'])], seconds=2400)

    add('favourites', 'annotations', [
        step('star', "In the list of songs mark the song 'Echo' as a favourite with its heart control.",
             'Echo is shown as a favourite (a filled heart) in the song list.',
             [{'op': 'favourite', 'title': 'Echo'}],
             [sub('getStarred2', 'starred2.song', ['title'], [{'title': 'Echo'}], collection=True)]),
        step('unstar', "Remove the favourite mark from the song 'Echo'.",
             'Echo is no longer shown as a favourite: its heart is empty.',
             [{'op': 'unfavourite', 'title': 'Echo'}],
             [sub('getStarred2', 'starred2.song', ['title'], [], collection=True)], depends=['star'],
             requires=['star/state-1'])])

    add('radio-stations', 'radios', [
        step('none-yet', 'Open the list of radio stations (Radios in the navigation).',
             'No radio station is listed: the page says that there are no radios yet.',
             [{'op': 'goto', 'path': '/app/#/radio'}], visible=['No Radios yet'], action_required=False,
             requires=['created/state-1']),
        step('created', "Create an internet radio station named 'Night Radio' with the stream address "
                        "http://stream.example.test/night.mp3 and the home page address http://example.test/night (Radios, "
                        "then create) and save it.",
             'Night Radio is created and listed among the radio stations.',
             [{'op': 'create-radio', 'name': 'Night Radio', 'stream': 'http://stream.example.test/night.mp3',
               'home': 'http://example.test/night'}],
             [read('radio', ['name', 'streamUrl', 'homePageUrl'],
                   {'name': 'Night Radio', 'streamUrl': 'http://stream.example.test/night.mp3',
                    'homePageUrl': 'http://example.test/night'}, where={'name': 'Night Radio'}, params=PAGE,
                   save='radio')], visible=['Night Radio']),
        step('edited', "Change the name of the radio station 'Night Radio' to 'Dawn Radio' and save.",
             'The station is now named Dawn Radio in the radio list.',
             [{'op': 'edit-radio', 'old': 'Night Radio', 'new': 'Dawn Radio'}],
             [read('radio/{{radio.id}}', ['name', 'streamUrl'],
                   {'name': 'Dawn Radio', 'streamUrl': 'http://stream.example.test/night.mp3'})],
             visible=['Dawn Radio'], depends=['created']),
        step('deleted', "Delete the radio station 'Dawn Radio' (open the station and use its delete action) and confirm.",
             'The station is gone: the radio list no longer shows Dawn Radio.',
             [{'op': 'delete-radio'}],
             [read('radio/{{radio.id}}', status=404)], depends=['edited'], requires=['created/state-1'])])

    add('user-accounts', 'users', [
        step('created', "As the administrator create a user with the username 'dave', the name 'Dave', the email "
                        "'dave@example.test' and the password '%s', not an administrator (Users, then create), and save." % DAVE,
             'The user dave is created and listed among the users.',
             [{'op': 'create-user', 'username': 'dave', 'name': 'Dave', 'email': 'dave@example.test', 'password': DAVE}],
             [read('user', ['userName', 'name', 'email', 'isAdmin'],
                   {'userName': 'dave', 'name': 'Dave', 'email': 'dave@example.test', 'isAdmin': False},
                   where={'userName': 'dave'}, params={**PAGE, '_sort': 'userName'}),
              sub('ping', actor='dave', password=DAVE)], visible=['dave'])])

    # The one browser share: made with a description and downloads allowed, then seen in the list of shares.
    add('album-share', 'sharing', [
        step('none-yet', 'Open the list of shares (Shares in the navigation).',
             'No share is listed: the page says that there are no shares yet.',
             [{'op': 'goto', 'path': '/app/#/share'}], visible=['No Shares yet'], action_required=False,
             requires=['created/state-1']),
        step('created', "Share the album 'Third Album' by Gamma Trio: open the album, use its share action, enter the "
                        "description 'For friends', allow downloads and confirm. Then open the list of shares.",
             'The list of shares shows a share of Third Album with the description For friends.',
             [{'op': 'share-album', 'title': 'Third Album', 'artist': 'Gamma Trio', 'description': 'For friends',
               'downloadable': True}],
             [read('share', ['resourceType', 'contents', 'description', 'downloadable'],
                   {'resourceType': 'album', 'contents': 'Third Album', 'description': 'For friends', 'downloadable': True},
                   where={'contents': 'Third Album'}, params=SHARES)], visible=['Third Album', 'For friends'])])

    add('restart-persistence', 'persistence', [
        {**step('after', "The framework has restarted the application using the same data directory. Open the list of "
                         "playlists.",
                'The playlist Durable list made before the restart is still listed.',
                [{'op': 'goto', 'path': '/app/#/playlist'}],
                [read('playlist', ['name', 'comment'], {'name': 'Durable list', 'comment': 'Survives restart'},
                      where={'name': 'Durable list'}, params=PAGE)], visible=['Durable list'], action_required=False),
         'lifecycle': 'restart'}],
        setup=[make('durable', 'playlist', {'name': 'Durable list', 'comment': 'Survives restart', 'public': False})])

    add('library-views', 'browsing', [
        step('artists', 'Open the list of artists (Artists in the navigation).',
             'Seven album artists are listed: [Unknown Artist], Alpha Artist, Beta Band, Delta Duo, Gamma Trio, Various '
             'Artists and Ünïcode Ärtist.',
             [{'op': 'goto', 'path': '/app/#/artist'}],
             visible=['Alpha Artist', 'Beta Band', 'Delta Duo', 'Gamma Trio', 'Various Artists'], action_required=False),
        step('songs', 'Open the list of songs (Songs in the navigation).',
             'The fifteen songs of the library are listed with their titles, among them Opening, Middle, Closing and Echo.',
             [{'op': 'goto', 'path': '/app/#/song'}], visible=['Opening', 'Middle', 'Closing', 'Echo'],
             action_required=False),
        step('imported-playlist', "Open the playlist 'Favourites' from the list of playlists.",
             'The playlist Favourites shows two songs, Opening and Intro, and tells that it was imported from the file '
             'Favourites.m3u.',
             [{'op': 'open-playlist', 'name': 'Favourites'}], visible=['Favourites.m3u', 'Opening', 'Intro'])])

    add('admin-pages', 'administration', [
        step('libraries', 'Open the library administration page (the account menu, then Libraries).',
             'One library is listed: Music Library at the path /music with 15 songs and 7 albums.',
             [{'op': 'goto', 'path': '/app/#/library'}], visible=['Music Library', '/music'], action_required=False),
        step('users', 'Open the list of users (the account menu, then Users).',
             'The users admin, bob and carol are listed.',
             [{'op': 'goto', 'path': '/app/#/user'}], visible=['admin', 'bob', 'carol'], action_required=False),
        step('settings', 'Open the personal settings page (the account menu, then Personal).',
             'The personal settings page shows the options Theme, Language, Default View and ReplayGain Mode.',
             [{'op': 'goto', 'path': '/app/#/personal'}],
             visible=['Theme', 'Language', 'Default View', 'ReplayGain Mode'], action_required=False)])

    # An ordinary account edits its own account, and does not reach the administration pages.
    add('own-account', 'permissions', [
        step('renamed', "Open your own account (the account menu, then User) and change your name to 'Bobby Tables', then save.",
             'The account is saved: opened again, the account of bob shows the name Bobby Tables.',
             [{'op': 'rename-self', 'username': 'bob', 'name': 'Bobby Tables'}],
             [read('user/{{bob.id}}', ['userName', 'name'], {'userName': 'bob', 'name': 'Bobby Tables'}, actor='bob')],
             visible=['Bobby Tables']),
        step('users', 'Open the list of users at the address /app/#/user.',
             'The account of an ordinary user cannot list users: no other account (admin, carol) is listed; the page shows '
             'no results or an access-denied message.',
             [{'op': 'goto', 'path': '/app/#/user'}], visible=['No results found'], action_required=False,
             requires=['renamed/state-1']),
        step('libraries', 'Open the library administration page at the address /app/#/library.',
             'No library administration is offered: no library list and no scan controls are shown; the page reports that '
             'it was not found or that access is denied.',
             [{'op': 'goto', 'path': '/app/#/library'}], visible=['Not Found'], action_required=False,
             requires=['renamed/state-1'])], actor='bob', setup=[find('bob', 'user', userName='bob')])

    add('album-rating', 'annotations', [
        step('none-rated', 'Open the list of top rated albums (Albums, then Top Rated in the navigation).',
             'No album is listed: nothing has been rated yet, so the list is empty and shows a no-results message.',
             [{'op': 'goto', 'path': '/app/#/album/topRated'}], visible=['No results found'], action_required=False,
             requires=['top-rated/visible']),
        step('rate', "Open the album 'Second Album' by Beta Band and give it a rating of 4 stars.",
             'The album page of Second Album shows a rating of 4 stars.',
             [{'op': 'rate-album', 'title': 'Second Album', 'artist': 'Beta Band', 'stars': 4}],
             [read('album', ['name', 'rating'], {'name': 'Second Album', 'rating': 4}, where={'name': 'Second Album'},
                   params=PAGE)], visible=['Second Album']),
        step('top-rated', 'Open the list of top rated albums (Albums, then Top Rated in the navigation).',
             'Second Album by Beta Band is listed, and no other album is.',
             [{'op': 'goto', 'path': '/app/#/album/topRated'}], visible=['Second Album'], depends=['rate'],
             action_required=False),
        step('clear', "Remove the rating of the album 'Second Album' again so that it has no stars.",
             'The album page of Second Album shows no rating.',
             [{'op': 'rate-album', 'title': 'Second Album', 'artist': 'Beta Band', 'stars': 0, 'was': 4}],
             [sub('getAlbumList2', 'albumList2.album', ['name'], [], query={'type': 'highest', 'size': 10}, collection=True)],
             visible=['Second Album'], depends=['rate'], requires=['rate/state-1'])])

    add('album-favourite', 'annotations', [
        step('none-loved', 'Open the list of favourite albums (Albums, then Favourites in the navigation).',
             'No album is listed: nothing is a favourite yet, so the list is empty and shows a no-results message.',
             [{'op': 'goto', 'path': '/app/#/album/starred'}], visible=['No results found'], action_required=False,
             requires=['listed/visible']),
        step('star', "Open the album 'Second Album' by Beta Band and mark it as a favourite with its heart control.",
             'The album page of Second Album shows the album as a favourite (a filled heart).',
             [{'op': 'favourite-album', 'title': 'Second Album', 'artist': 'Beta Band'}],
             [sub('getStarred2', 'starred2.album', ['name'], [{'name': 'Second Album'}], collection=True)],
             visible=['Second Album']),
        step('listed', 'Open the list of favourite albums (Albums, then Favourites in the navigation).',
             'Second Album by Beta Band is listed, and no other album is.',
             [{'op': 'goto', 'path': '/app/#/album/starred'}], visible=['Second Album'], depends=['star'],
             action_required=False),
        step('unstar', "Remove the favourite mark from the album 'Second Album'.",
             'The album page of Second Album shows the album without the favourite mark (an empty heart).',
             [{'op': 'unfavourite-album', 'title': 'Second Album', 'artist': 'Beta Band'}],
             [sub('getStarred2', 'starred2.album', ['name'], [], collection=True)], visible=['Second Album'],
             depends=['star'], requires=['star/state-1'])])

    add('playlist-public', 'playlists', [
        step('public', "Make the playlist 'Shared Mix' public: open it for editing, tick Public and save.",
             'The playlist Shared Mix is public: it is marked as public in the playlist list.',
             [{'op': 'set-playlist-public', 'public': True}],
             [read('playlist/{{playlist.id}}', ['name', 'public'], {'name': 'Shared Mix', 'public': True}),
              sub('getPlaylists', 'playlists.playlist', ['name'], [{'name': 'Shared Mix'}], actor='bob', collection=True)],
             visible=['Shared Mix']),
        step('private', "Make the playlist 'Shared Mix' private again: open it for editing, clear Public and save.",
             'The playlist Shared Mix is private again: it is no longer marked as public in the playlist list.',
             [{'op': 'set-playlist-public', 'public': False}],
             [read('playlist/{{playlist.id}}', ['name', 'public'], {'name': 'Shared Mix', 'public': False}),
              sub('getPlaylists', 'playlists.playlist', ['name'], [], actor='bob', collection=True)],
             visible=['Shared Mix'], depends=['public'], requires=['public/state-2'])],
        setup=[make('shared-mix', 'playlist', {'name': 'Shared Mix', 'comment': 'For everyone', 'public': False}, save='playlist')])

    add('album-to-playlist', 'playlists', [
        step('added', "Open the album 'Second Album' by Beta Band and add the whole album to the existing playlist 'Album Mix' "
                      "with the add to playlist action of the album page.",
             'The three songs of Second Album are in the playlist: the playlist Album Mix lists Intro, Drift and Reprise.',
             [{'op': 'add-album-to-playlist', 'title': 'Second Album', 'artist': 'Beta Band', 'playlist': 'Album Mix', 'count': 3}],
             [tracks(['Intro', 'Drift', 'Reprise'])], visible=['Intro', 'Drift', 'Reprise'])],
        setup=[make('album-mix', 'playlist', {'name': 'Album Mix', 'comment': 'Whole album', 'public': False}, save='playlist')])

    add('user-rights', 'users', [
        step('promoted', "Make the user 'dave' an administrator: open the user for editing, tick Is Admin and save.",
             'The user dave is now an administrator.',
             [{'op': 'set-user-admin', 'username': 'dave', 'admin': True}],
             [read('user/{{dave.id}}', ['userName', 'isAdmin'], {'userName': 'dave', 'isAdmin': True})], visible=['dave']),
        step('deleted', "Delete the user 'dave' (open the user and use its delete action) and confirm.",
             'The user dave is gone: the list of users no longer shows dave.',
             [{'op': 'delete-user', 'username': 'dave'}],
             [read('user/{{dave.id}}', status=404)], depends=['promoted'], requires=['promoted/state-1'])],
        setup=[make('dave', 'user', {'userName': 'dave', 'name': 'Dave', 'email': 'dave@example.test', 'password': DAVE,
                                    'isAdmin': False}, save='dave')])

    add('artist-pages', 'browsing', [
        step('list', 'Open the list of artists (Artists in the navigation).',
             'The list shows the album artists with their album and song counts, among them Alpha Artist (1 album, 3 songs) and Gamma Trio (1 album, 2 songs).',
             [{'op': 'goto', 'path': '/app/#/artist'}], visible=['Alpha Artist', 'Gamma Trio', 'Album Count', 'Song Count'],
             action_required=False),
        step('detail', "Open the artist 'Gamma Trio' from the list of artists.",
             'The page of Gamma Trio is shown with its album Third Album (1999).',
             [{'op': 'open-artist', 'name': 'Gamma Trio'}], visible=['Third Album', '1999'], depends=['list'])])

    add('song-sorting', 'browsing', [
        step('by-title', 'Open the list of songs (Songs in the navigation) and sort it by the Title column with the column header so that titles run from Z to A.',
             'The songs are sorted by title in descending order: Single C is listed before Single B, and Single B before Single A.',
             [{'op': 'goto', 'path': '/app/#/song'}, {'op': 'sort-songs', 'column': 'Title'}],
             visible=['Single C', 'Single B', 'Single A'])])

    share_setup = [find('third', 'album', name='Third Album'), call('share', 'createShare', id='{{third.id}}')]
    add('share-pages', 'sharing', [
        step('listed', 'Open the list of shares (Shares in the navigation).',
             'The list shows one share: the album Third Album shared by admin.',
             [{'op': 'goto', 'path': '/app/#/share'}], visible=['Third Album', 'Shared By'], action_required=False),
        step('public-page', 'Open the public page of the share: its address is /share/ followed by the share id shown in the list of shares.',
             'The public share page lists the songs of the share, Blue Hour and Late Train, without the sign-in form.',
             [{'op': 'goto', 'path': '/share/{{share.id}}'}], visible=['Blue Hour', 'Late Train'], action_required=False)],
        setup=share_setup + [find('share', 'share')])

    add('imported-playlist-page', 'playlists', [
        step('edit-page', "Open the playlist 'Favourites' for editing (the edit action in the playlist list).",
             'The edit form of Favourites is shown and tells that the playlist is imported automatically from the file /music/Playlists/Favourites.m3u.',
             [{'op': 'open-playlist-edit', 'name': 'Favourites'}], visible=['Auto-import', '/music/Playlists/Favourites.m3u'])])

    add('user-edit-page', 'users', [
        step('edit-page', "Open the user 'carol' for editing (Users in the account menu, then the user).",
             'The edit form of carol is shown with the options Is Admin and Libraries and the scrobble filter field.',
             [{'op': 'open-user', 'username': 'carol'}], visible=['Is Admin', 'Libraries', 'Scrobble filter'])])

    add('play-history', 'annotations', [
        step('none-recent', 'Open the list of recently played albums (Albums, then Recently Played in the navigation).',
             'No album is listed: nothing has been played yet, so the list is empty and shows a no-results message.',
             [{'op': 'goto', 'path': '/app/#/album/recentlyPlayed'}], visible=['No results found'], action_required=False,
             requires=['recent/visible']),
        step('recent', 'Open the list of recently played albums (Albums, then Recently Played in the navigation).',
             'First Album by Alpha Artist is listed as recently played, and no other album is.',
             [{'op': 'goto', 'path': '/app/#/album/recentlyPlayed'}], visible=['First Album', 'Alpha Artist'], action_required=False),
        step('most-played', 'Open the list of most played albums (Albums, then Most Played in the navigation).',
             'First Album by Alpha Artist is listed as most played, and no other album is.',
             [{'op': 'goto', 'path': '/app/#/album/mostPlayed'}], visible=['First Album', 'Alpha Artist'], action_required=False)],
        setup=[find('opening', 'song', title='Opening'),
               {**call('play-opening', 'scrobble', id='{{opening.id}}'), 'before': 'recent'}])

    add('radio-list', 'radios', [
        step('listed', 'Open the list of radio stations (Radios in the navigation).',
             'The list shows the station Probe FM with its home page address http://home.example.test/p.',
             [{'op': 'goto', 'path': '/app/#/radio'}], visible=['Probe FM', 'http://home.example.test/p'], action_required=False)],
        setup=[make('radio', 'radio', {'name': 'Probe FM', 'streamUrl': 'http://stream.example.test/p', 'homePageUrl': 'http://home.example.test/p'})])

    add('artist-rating', 'annotations', [
        step('rate', 'Open the artist Gamma Trio and give the artist a rating of 3 stars.',
             'The artist page of Gamma Trio shows a rating of 3 stars.',
             [{'op': 'rate-artist', 'name': 'Gamma Trio', 'stars': 3}],
             [read('artist', ['name', 'rating'], {'name': 'Gamma Trio', 'rating': 3}, where={'name': 'Gamma Trio'}, params=PAGE, save='gamma')],
             visible=['Gamma Trio']),
        step('clear', 'Remove the rating of the artist Gamma Trio again so that it has no stars.',
             'The artist page of Gamma Trio shows no rating.',
             [{'op': 'rate-artist', 'name': 'Gamma Trio', 'stars': 0, 'was': 3}],
             [read('artist/{{gamma.id}}', ['name', 'rating?'], {'name': 'Gamma Trio', 'rating': None})],
             visible=['Gamma Trio'], depends=['rate'], requires=['rate/state-1'])])

    add('album-details', 'browsing', [
        step('open', 'Open the album Third Album by Gamma Trio from the list of all albums.',
             'The album page of Third Album by Gamma Trio shows the year 1999, the genres Jazz and Blues and its two songs, Blue Hour and Late Train.',
             [{'op': 'open-album', 'title': 'Third Album', 'artist': 'Gamma Trio'}],
             visible=['1999', 'Blue Hour', 'Late Train', 'Jazz', 'Blues'])])

    add('song-filters', 'search', [
        step('unicode', "Open the list of songs (Songs in the navigation) and filter it by the text 'Naïve' with the list's search field.",
             'Exactly one song is listed: Naïve Ω; the other songs are not shown.',
             [{'op': 'goto', 'path': '/app/#/song'}, {'op': 'filter-songs', 'text': 'Naïve'}], visible=['Naïve Ω']),
        step('case', "Replace the filter text with 'train' (lower case).",
             'Exactly one song is listed: Late Train; the filter does not depend on letter case.',
             [{'op': 'filter-songs', 'text': 'train'}], visible=['Late Train'], depends=['unicode']),
        step('blue', "Replace the filter text with 'blue'.",
             'Exactly one song is listed: Blue Hour; Late Train is no longer shown.',
             [{'op': 'filter-songs', 'text': 'blue'}], visible=['Blue Hour'], depends=['case'])])

    add('share-delete', 'sharing', [
        step('deleted', "Open the list of shares (Shares in the navigation), select the share of Third Album and delete it, confirming if asked.",
             'The share is gone: the list of shares no longer shows Third Album.',
             [{'op': 'delete-share'}],
             [read('share', ['resourceType'], [], params={'_start': 0, '_end': 50}, collection=True)])],
        setup=share_setup)

    add('album-pages', 'browsing', [
        step('compilation', 'Open the album Mixtape by Various Artists from the list of all albums (Albums, then All in the navigation).',
             'The album page of Mixtape shows its three songs: Single A, Single B and Single C.',
             [{'op': 'open-album', 'title': 'Mixtape', 'artist': 'Various Artists'}], visible=['Single A', 'Single B', 'Single C']),
        step('unicode', 'Open the album Café Ω by Ünïcode Ärtist from the list of all albums.',
             'The album page of Café Ω shows its song Naïve Ω.',
             [{'op': 'open-album', 'title': 'Café Ω', 'artist': 'Ünïcode Ärtist'}], visible=['Naïve Ω']),
        step('discs', 'Open the album Second Album by Beta Band from the list of all albums.',
             'The album page of Second Album groups its songs by disc: it shows the headings Disc 1 and Disc 2.',
             [{'op': 'open-album', 'title': 'Second Album', 'artist': 'Beta Band'}], visible=['Disc 1', 'Disc 2'])])

    add('artist-albums', 'browsing', [
        step('beta', 'Open the artist Beta Band from the list of artists (Artists in the navigation).',
             'The page of Beta Band is shown with its album Second Album (2010).',
             [{'op': 'open-artist', 'name': 'Beta Band'}], visible=['Second Album', '2010']),
        step('unicode', 'Open the artist Ünïcode Ärtist from the list of artists.',
             'The page of Ünïcode Ärtist is shown with its album Café Ω (2015).',
             [{'op': 'open-artist', 'name': 'Ünïcode Ärtist'}], visible=['Café Ω', '2015']),
        step('compilation', 'Open the artist Various Artists from the list of artists.',
             'The page of Various Artists is shown with its album Mixtape (2020).',
             [{'op': 'open-artist', 'name': 'Various Artists'}], visible=['Mixtape', '2020'])])

    # Lists of an ordinary account: favourites, ratings, plays and playlists are its own; radio stations are shared.
    add('ordinary-account-scope', 'permissions', [
        step('favourites', 'Open the list of favourite albums (Albums, then Favourites in the navigation).',
             'Only Mixtape is listed: the favourite of the administrator (Second Album) is not.',
             [{'op': 'goto', 'path': '/app/#/album/starred'}], visible=['Mixtape'], action_required=False),
        step('top-rated', 'Open the list of top rated albums (Albums, then Top Rated in the navigation).',
             'Only Mixtape is listed: the rating of the administrator (Third Album) does not count for this account.',
             [{'op': 'goto', 'path': '/app/#/album/topRated'}], visible=['Mixtape'], action_required=False),
        step('recent', 'Open the list of recently played albums (Albums, then Recently Played in the navigation).',
             'Only First Album by Delta Duo is listed: what the administrator played (First Album by Alpha Artist) is not.',
             [{'op': 'goto', 'path': '/app/#/album/recentlyPlayed'}], visible=['Delta Duo'], action_required=False),
        step('playlists', 'Open the list of playlists (Playlists in the navigation).',
             'Only the playlist Bob Mix is listed: the private playlist of the administrator (Admin Private) is not.',
             [{'op': 'goto', 'path': '/app/#/playlist'}], visible=['Bob Mix'], action_required=False),
        step('radios', 'Open the list of radio stations (Radios in the navigation).',
             'The station Shared FM made by the administrator is listed: radio stations are shared by all accounts.',
             [{'op': 'goto', 'path': '/app/#/radio'}], visible=['Shared FM'], action_required=False)],
        actor='bob',
        setup=[find('second', 'album', name='Second Album'), find('third', 'album', name='Third Album'),
               find('mixtape', 'album', name='Mixtape'), find('opening', 'song', title='Opening'), find('echo', 'song', title='Echo'),
               call('admin-loves', 'star', albumId='{{second.id}}'), call('bob-loves', 'star', 'bob', albumId='{{mixtape.id}}'),
               call('admin-rates', 'setRating', id='{{third.id}}', rating=5),
               call('bob-rates', 'setRating', 'bob', id='{{mixtape.id}}', rating=4),
               call('admin-plays', 'scrobble', id='{{opening.id}}'), call('bob-plays', 'scrobble', 'bob', id='{{echo.id}}'),
               make('admin-playlist', 'playlist', {'name': 'Admin Private', 'comment': '', 'public': False}),
               make('bob-playlist', 'playlist', {'name': 'Bob Mix', 'comment': '', 'public': False}, actor='bob'),
               make('shared-radio', 'radio', {'name': 'Shared FM', 'streamUrl': 'http://stream.example.test/shared'})])

    # The web player: an album played from its page, another one added to the end of the queue.
    add('web-player', 'playback', [
        step('play-album', "Open the album 'Second Album' by Beta Band and play it with its play action.",
             'The player has played the album: its play queue lists the three songs of Second Album, Intro, Drift and Reprise.',
             [{'op': 'play-album', 'title': 'Second Album', 'artist': 'Beta Band', 'songs': ['Intro', 'Drift', 'Reprise']}],
             [read('song', ['title', 'playCount'], [{'title': 'Drift', 'playCount': 1}, {'title': 'Intro', 'playCount': 1},
                                                   {'title': 'Reprise', 'playCount': 1}],
                   params={'_start': 0, '_end': 50, '_sort': 'title', '_order': 'ASC', 'album_id': '{{second.id}}'},
                   collection=True) | {'wait': 20}],
             visible=['Intro', 'Drift', 'Reprise']),
        step('play-later', "Open the album 'Third Album' by Gamma Trio and add it to the end of the play queue with its play later action.",
             'The play queue now lists five songs: Intro, Drift and Reprise, then Blue Hour and Late Train.',
             [{'op': 'play-later', 'title': 'Third Album', 'artist': 'Gamma Trio'}], visible=['Blue Hour', 'Late Train'],
             depends=['play-album'])], setup=[find('second', 'album', name='Second Album')])

    add('playlist-tracks', 'playlists', [
        step('removed', "Open the playlist 'Road Trip' and remove the song 'Echo' from it.",
             'The playlist Road Trip now lists two songs, Opening and Intro; Echo is no longer in it.',
             [{'op': 'remove-from-playlist', 'playlist': 'Road Trip', 'title': 'Echo', 'count': 2}],
             [tracks(['Opening', 'Intro'])], visible=['Opening', 'Intro'])],
        setup=[make('road-trip', 'playlist', {'name': 'Road Trip', 'comment': '', 'public': False}, save='playlist'),
               find('opening', 'song', title='Opening'), find('echo', 'song', title='Echo'), find('intro', 'song', title='Intro'),
               make('road-trip-songs', 'playlist/{{playlist.id}}/tracks', {'ids': ['{{opening.id}}', '{{echo.id}}', '{{intro.id}}']})])

    add('library-scan', 'libraries', [
        step('quick-scan', 'A new song file has been put into the music folder. Start a quick scan of the library from the '
                           'library administration page (the account menu, then Libraries).',
             'The scan has found the new song: the library Music Library now counts 16 songs and 8 albums (the page may need '
             'to be reloaded to show the new totals).',
             [{'op': 'library-scan', 'songs': 16}],
             [read('song', ['title', 'album'], [{'title': 'Prelude', 'album': 'Fifth Album'}],
                   params={'_start': 0, '_end': 5, '_sort': 'title', '_order': 'ASC', 'title': 'Prelude'}, collection=True)
              | {'wait': 20}],
             visible=['16'])],
        setup=[{'id': 'fx-new-file', 'library_put': 'Epsilon Ensemble/Fifth Album/01 Prelude.mp3'}])

    add('change-password', 'users', [
        step('changed', "Open the user 'carol' for editing (Users in the account menu, then the user), tick Change Password, "
                        "enter the new password '%s' and save." % CAROL_NEW,
             'The edit form is saved and the application shows the list of users again, with carol in it.',
             [{'op': 'change-password', 'username': 'carol', 'password': CAROL_NEW}],
             [{**sub('ping', actor='carol', password=CAROL_NEW), 'description': 'carol answers to the new password'}],
             visible=['carol'], requires=['changed/state-1']),
        step('signed-in', "Sign out (the account menu, then Logout) and sign in with the username 'carol' and the new password "
                          "'%s'." % CAROL_NEW,
             'Carol is signed in with the new password: the album browsing views are shown instead of the sign-in form.',
             [{'op': 'sign-out'}, {'op': 'sign-in', 'username': 'carol', 'password': CAROL_NEW, 'valid': True}],
             visible=['Albums'], depends=['changed'], requires=['changed/state-1'])])

    add('personal-language', 'preferences', [
        step('german', 'Change the language of the interface to Deutsch in the personal settings (the account menu, then '
                       'Personal).',
             'The interface is shown in German: the navigation reads Alben and Interpreten instead of Albums and Artists.',
             [{'op': 'set-language', 'language': 'Deutsch'}], visible=['Alben', 'Interpreten'])])

    add('players-page', 'administration', [
        step('renamed', "Open the list of players (the account menu, then Players), open the player whose client is "
                        "'pbp-check' and change its name to 'Living Room', then save.",
             'The list of players shows the player Living Room.',
             [{'op': 'rename-player', 'client': 'pbp-check', 'name': 'Living Room'}],
             [read('player', ['client', 'name'], {'client': 'pbp-check', 'name': 'Living Room'},
                   params={'_start': 0, '_end': 20}, where={'client': 'pbp-check'})],
             visible=['Living Room'])])

    add('missing-files', 'libraries', [
        step('listed', 'A song file has been deleted from the music folder and the library has been scanned. Open the '
                       'missing files page (the account menu, then Missing Files).',
             'The page lists the missing file Untagged/loose track.mp3 of the library Music Library.',
             [{'op': 'goto', 'path': '/app/#/missing'}], visible=['Untagged/loose track.mp3'], action_required=False),
        step('removed', 'Remove the missing file from the list.',
             'The missing file is gone: the page states that there are no missing files.',
             [{'op': 'remove-missing'}],
             [read('missing', ['path'], [], params={'_start': 0, '_end': 20}, collection=True)],
             visible=['No Missing Files'], depends=['listed'])],
        setup=[{'id': 'fx-drop-file', 'library_delete': 'Untagged/loose track.mp3', 'scan': 'quick'}])

    add('library-create', 'libraries', [
        step('created', "Create a second library named 'Unicode Only' for the folder /music/Unicode (the account menu, then "
                        "Libraries, then create) and save it.",
             'The list of libraries shows the new library Unicode Only with the path /music/Unicode next to Music Library.',
             [{'op': 'create-library', 'name': 'Unicode Only', 'path': '/music/Unicode'}],
             [read('library', ['name', 'path'], {'name': 'Unicode Only', 'path': '/music/Unicode'}, where={'name': 'Unicode Only'},
                   params={'_start': 0, '_end': 10})], visible=['Unicode Only', '/music/Unicode'])])

    add('smart-playlist', 'playlists', [
        step('opened', "A rule playlist file has been put into the music folder and the library has been scanned. Open the "
                       "playlist 'Rock Songs' from the list of playlists.",
             'The playlist Rock Songs lists the three Rock songs of the library: Closing, Middle and Opening.',
             [{'op': 'open-playlist', 'name': 'Rock Songs'}], visible=['Closing', 'Middle', 'Opening'])],
        setup=[{'id': 'fx-rule-file', 'library_put': 'Playlists/Smart/Rock.nsp', 'scan': 'full',
                'text': '{"name": "Rock Songs", "all": [{"is": {"genre": "Rock"}}], "sort": "title"}'}])

    return episodes
