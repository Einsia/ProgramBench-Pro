'''Pinned-standard GUI implementation of the reviewed goals, through the black-box runtime (record only).

The recipes drive the standard answer with the same runtime GUI operations that the evaluator and the model use;
BrokerSurface.observe() captures the reference evidence. Control names, form fields and routes below belong to the
pinned standard only; they are never a candidate requirement. API reads only confirm that a browser mutation was
saved before the evidence is taken.
'''
import time

from checks import resolve
from harness import PASSWORDS
from .ui import UI, accessible

SEARCH = 'Search playlists or type to create new...'
PAGE = {'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}
SHARES = {'_start': 0, '_end': 50, '_sort': 'createdAt', '_order': 'DESC'}
SONGS = {'_start': 0, '_end': 100, '_sort': 'title', '_order': 'ASC'}
DELETE_NAMES = ('confirm', 'yes')
SHARE_NAMES = ('share', 'confirm', 'create', 'ok', 'save')


def corroborate(c, path, predicate, params=None, timeout=10.0, what='browser mutation not saved'):
    '''Wait until the product reports the browser mutation through its native API.'''
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        answer = c.native('GET', path, 'admin', params=params)
        last = (answer['status'], str(answer['body'])[:200])
        try:
            if predicate(answer):
                return answer['body']
        except (KeyError, TypeError, IndexError):
            pass
        time.sleep(0.3)
    raise AssertionError(what + ': ' + str(last))


def listed(c, path, key, value, params=None):
    return corroborate(c, path, lambda r: r['status'] == 200 and any(x.get(key) == value for x in r['body']),
                       params=params)


def identity(rows, key, value):
    return str(next(x['id'] for x in rows if x.get(key) == value))


def starred(c, title, wanted, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        reply = c.reply(c.subsonic('getStarred2'))
        songs = (reply.get('starred2') or {}).get('song') or []
        if any(s.get('title') == title for s in songs) == wanted:
            return
        time.sleep(0.3)
    raise AssertionError('favourite mark of ' + title + ' not ' + ('saved' if wanted else 'removed'))


def starred_album(c, title, wanted, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        reply = c.reply(c.subsonic('getStarred2'))
        albums = (reply.get('starred2') or {}).get('album') or []
        if any(a.get('name') == title for a in albums) == wanted:
            return
        time.sleep(0.3)
    raise AssertionError('favourite mark of the album ' + title + ' not ' + ('saved' if wanted else 'removed'))


STARS = {'album': (11, -7, 24), 'artist': (10, -10, 18)}


def click_star(ui, n):
    # The radio inputs are one pixel large and sit at the corner of the stars, which are drawn by their labels: the star n is
    # a fixed offset from the first radio, and the offset differs between the album page and the artist page.
    dx, dy, step = STARS['artist' if '/artist/' in ui.url else 'album']
    ui.snapshot()
    x, y = ui.find(labels=['1 Star'], types=('radio',))['bounds'][:2]
    ui.call('pointer', action='click', x=x + dx + step * (n - 1), y=y + dy)


def set_rating(ui, stars, was=None):
    ui.snapshot()
    if stars == 0:
        # A rated item has no Empty control: clicking the selected star again clears the rating.
        assert was, 'the current rating is needed to clear it'
        click_star(ui, was)
        return
    control = ui.find(labels=['%d Star%s' % (stars, 's' if stars != 1 else '')], types=('radio',))
    assert control, 'rating control missing for %d stars' % stars
    # A key pressed on the radio selects it (it takes no click or check).
    ui.call('press', target={'ref': control['ref']}, key='Space')


def open_album(ui, title):
    open_card(ui, '/app/#/album/all', title)
    ui.wait(lambda s: '/show' in s['url'], 'album page did not open')


def filter_songs(ui, text):
    if '#/song' not in ui.url:
        ui.goto('/app/#/song')
    ui.fill('title', text)
    ui.call('wait', seconds=1.5)


def checkboxes(ui, dialog):
    found = [x for x in ui.snapshot()['controls'] if x.get('type') == 'checkbox' and not x.get('offscreen')]
    if dialog:
        found = [x for x in found if x['bounds'][0] >= 340 and x['bounds'][1] > 380]
    return sorted(found, key=lambda x: x['bounds'][1])


def song_row(ui, title):
    # With the list filtered to one title, the first checkbox is the select-all of the header and the second the row.
    filter_songs(ui, title)
    rows = checkboxes(ui, False)
    assert len(rows) >= 2, 'no song row listed for ' + title
    return rows[1]


def pick_playlist(ui, playlist):
    ui.wait(lambda s: any(x.get('placeholder') == SEARCH for x in s['controls']), 'playlist dialog did not open')
    ui.call('fill', target={'placeholder': SEARCH}, value=playlist)
    ui.call('wait', seconds=1)
    choice = checkboxes(ui, True)
    assert choice, 'playlist ' + playlist + ' is not offered'
    ui.call('check', target={'ref': choice[0]['ref']}, checked=True)
    ui.click('Add')
    ui.wait(lambda s: not any(x.get('placeholder') == SEARCH for x in s['controls']), 'playlist dialog did not close')


def add_song(ui, title, playlist):
    ui.call('check', target={'ref': song_row(ui, title)['ref']}, checked=True)
    ui.click('Add to Playlist')
    pick_playlist(ui, playlist)


def confirm_dialog(ui, names):
    # An optional confirmation: the lowest matching button of the page is the one of the dialog.
    ui.call('wait', seconds=1)
    options = [x for x in ui.snapshot()['controls'] if x['tag'] == 'button' and not x.get('offscreen')
               and not x.get('disabled') and any(n.strip().lower() in names for n in accessible(x))]
    if options:
        ui.click_ref(max(options, key=lambda x: x['bounds'][1]))


def open_card(ui, route, text):
    ui.goto(route)
    ui.require(text)
    ui.call('click', target={'text': text})


def execute(ctx, c, checkpoint):
    episode = ctx.episode
    actor = episode.get('actor')
    ui = ctx.state.setdefault('ui', UI(ctx.broker))
    if actor and not ctx.state.get('signed_in'):
        ui.sign_in(actor, PASSWORDS[actor])
        ctx.state['signed_in'] = True
    for raw in checkpoint['recipe']:
        a = resolve(raw, c.state)
        op = a['op']
        if op == 'create-admin':
            ui.create_admin(a['username'], a['password'])
        elif op == 'sign-in':
            ui.goto('/app/')
            ui.wait(lambda s: any(x.get('name') == 'username' for x in s['controls']), 'sign-in form missing')
            ui.fill('username', a['username'])
            ui.fill('password', a['password'])
            ui.submit('Sign In')
            ui.call('wait', seconds=2)
            if a['valid']:
                ui.wait(lambda s: '#/login' not in s['url'], 'sign-in did not complete')
        elif op == 'goto':
            ui.goto(a['path'])
        elif op == 'open-album':
            open_card(ui, '/app/#/album/all', a['title'])
        elif op == 'open-artist':
            open_card(ui, '/app/#/artist', a['name'])
        elif op == 'filter-songs':
            filter_songs(ui, a['text'])
        elif op == 'create-playlist':
            ui.goto('/app/#/playlist/create')
            ui.fill('name', a['name'])
            ui.fill('comment', a['comment'])
            if 'public' in a:
                ui.check('public', a['public'], labels=('Public',))
            ui.submit('Save')
            listed(c, 'playlist', 'name', a['name'], PAGE)
            ui.goto('/app/#/playlist')
        elif op == 'add-to-playlist':
            for title in a['titles']:
                add_song(ui, title, a['playlist'])
            pid = identity(listed(c, 'playlist', 'name', a['playlist'], PAGE), 'name', a['playlist'])
            corroborate(c, 'playlist/' + pid + '/tracks', lambda r: r['status'] == 200 and len(r['body']) == len(a['titles']),
                        params={'_start': 0, '_end': 50}, what='songs not added to the playlist')
            ui.goto('/app/#/playlist/' + pid + '/show')
        elif op == 'rename-playlist':
            pid = str(c.state['playlist']['id'])
            ui.goto('/app/#/playlist/' + pid)
            ui.wait(lambda s: any(x.get('name') == 'name' for x in s['controls']), 'playlist form missing')
            ui.fill('name', a['new'])
            ui.submit('Save')
            corroborate(c, 'playlist/' + pid, lambda r: r['status'] == 200 and r['body'].get('name') == a['new'],
                        what='playlist not renamed')
            ui.goto('/app/#/playlist')
        elif op == 'delete-playlist':
            pid = str(c.state['playlist']['id'])
            ui.goto('/app/#/playlist/' + pid)
            ui.click('Delete')
            confirm_dialog(ui, DELETE_NAMES)
            corroborate(c, 'playlist/' + pid, lambda r: r['status'] == 404, what='playlist not deleted')
            ui.goto('/app/#/playlist')
        elif op in ('favourite', 'unfavourite'):
            row = song_row(ui, a['title'])
            y = row['bounds'][1] + row['bounds'][3] // 2
            # The heart of a song row is not in the snapshot until the pointer is over the row: hover, then click it.
            ui.call('pointer', action='move', x=640, y=y)
            ui.call('pointer', action='click', x=1200, y=y)
            starred(c, a['title'], op == 'favourite')
        elif op == 'create-radio':
            ui.goto('/app/#/radio/create')
            ui.fill('name', a['name'])
            ui.fill('streamUrl', a['stream'])
            ui.fill('homePageUrl', a['home'])
            ui.submit('Save')
            listed(c, 'radio', 'name', a['name'], PAGE)
            ui.goto('/app/#/radio')
        elif op == 'edit-radio':
            rid = str(c.state['radio']['id'])
            ui.goto('/app/#/radio/' + rid)
            ui.wait(lambda s: any(x.get('name') == 'name' for x in s['controls']), 'radio form missing')
            ui.fill('name', a['new'])
            ui.submit('Save')
            corroborate(c, 'radio/' + rid, lambda r: r['status'] == 200 and r['body'].get('name') == a['new'],
                        what='radio station not renamed')
            ui.goto('/app/#/radio')
        elif op == 'create-user':
            ui.goto('/app/#/user/create')
            ui.fill('userName', a['username'])
            ui.fill('name', a['name'])
            ui.fill('email', a['email'])
            ui.fill('password', a['password'])
            ui.submit('Save')
            listed(c, 'user', 'userName', a['username'], {**PAGE, '_sort': 'userName'})
            ui.goto('/app/#/user')
        elif op == 'share-album':
            open_card(ui, '/app/#/album/all', a['title'])
            ui.require('Share')
            ui.click('Share')
            if 'description' in a:
                ui.wait(lambda s: any(x.get('name') == 'description' for x in s['controls']), 'share dialog did not open')
                ui.fill('description', a['description'])
                ui.check('downloadable', a.get('downloadable', False))
            confirm_dialog(ui, SHARE_NAMES)
            listed(c, 'share', 'contents', a['title'], SHARES)
            if 'description' in a:
                ui.goto('/app/#/share')
        elif op == 'rate-album':
            open_album(ui, a['title'])
            set_rating(ui, a['stars'], a.get('was'))
            corroborate(c, 'album', lambda r: r['status'] == 200 and any(
                x.get('name') == a['title'] and x.get('rating', 0) == a['stars'] for x in r['body']),
                        params=PAGE, what='album rating not saved')
        elif op in ('favourite-album', 'unfavourite-album'):
            open_album(ui, a['title'])
            ui.click('love', 'unlove')
            starred_album(c, a['title'], op == 'favourite-album')
        elif op == 'set-playlist-public':
            pid = str(c.state['playlist']['id'])
            ui.goto('/app/#/playlist/' + pid)
            ui.wait(lambda s: any(x.get('name') == 'public' for x in s['controls']), 'playlist form missing')
            ui.check('public', a['public'], labels=('Public',))
            ui.submit('Save')
            corroborate(c, 'playlist/' + pid, lambda r: r['status'] == 200 and bool(r['body'].get('public')) == a['public'],
                        what='playlist visibility not saved')
            ui.goto('/app/#/playlist')
        elif op == 'add-album-to-playlist':
            open_album(ui, a['title'])
            ui.click('Add to Playlist', timeout=8.0)
            pick_playlist(ui, a['playlist'])
            pid = identity(listed(c, 'playlist', 'name', a['playlist'], PAGE), 'name', a['playlist'])
            corroborate(c, 'playlist/' + pid + '/tracks', lambda r: r['status'] == 200 and len(r['body']) == a['count'],
                        params={'_start': 0, '_end': 50}, what='album not added to the playlist')
            ui.goto('/app/#/playlist/' + pid + '/show')
        elif op == 'open-playlist':
            pid = identity(listed(c, 'playlist', 'name', a['name'], PAGE), 'name', a['name'])
            ui.goto('/app/#/playlist/' + pid + '/show')
        elif op == 'delete-radio':
            rid = str(c.state['radio']['id'])
            ui.goto('/app/#/radio/' + rid)
            ui.click('Delete')
            confirm_dialog(ui, DELETE_NAMES)
            corroborate(c, 'radio/' + rid, lambda r: r['status'] == 404, what='radio station not deleted')
            ui.goto('/app/#/radio')
        elif op in ('set-user-admin', 'delete-user'):
            uid = identity(listed(c, 'user', 'userName', a['username'], {**PAGE, '_sort': 'userName'}), 'userName', a['username'])
            ui.goto('/app/#/user/' + uid)
            if op == 'delete-user':
                ui.click('Delete')
                confirm_dialog(ui, DELETE_NAMES)
                corroborate(c, 'user/' + uid, lambda r: r['status'] == 404, what='user not deleted')
            else:
                ui.wait(lambda s: any(x.get('name') == 'isAdmin' for x in s['controls']), 'user form missing')
                ui.check('isAdmin', a['admin'], labels=('Is Admin',))
                ui.submit('Save')
                corroborate(c, 'user/' + uid, lambda r: r['status'] == 200 and bool(r['body'].get('isAdmin')) == a['admin'],
                            what='user rights not saved')
            ui.goto('/app/#/user')
        elif op == 'sort-songs':
            ui.call('click', target={'text': a['column']})
            ui.wait(lambda s: 'sort=' + a['column'].lower() in s['url'], 'song list was not sorted')
            ui.call('wait', seconds=1.5)
        elif op == 'open-playlist-edit':
            pid = identity(listed(c, 'playlist', 'name', a['name'], PAGE), 'name', a['name'])
            ui.goto('/app/#/playlist/' + pid)
            ui.wait(lambda s: any(x.get('name') == 'name' for x in s['controls']), 'playlist form missing')
        elif op == 'open-user':
            uid = identity(listed(c, 'user', 'userName', a['username'], {**PAGE, '_sort': 'userName'}), 'userName', a['username'])
            ui.goto('/app/#/user/' + uid)
            ui.wait(lambda s: any(x.get('name') == 'isAdmin' for x in s['controls']), 'user form missing')
        elif op == 'rate-artist':
            open_card(ui, '/app/#/artist', a['name'])
            ui.wait(lambda s: '/show' in s['url'], 'artist page did not open')
            set_rating(ui, a['stars'], a.get('was'))
            corroborate(c, 'artist', lambda r: r['status'] == 200 and any(x.get('name') == a['name'] and x.get('rating', 0) == a['stars'] for x in r['body']), params=PAGE, what='artist rating not saved')
        elif op == 'delete-share':
            ui.goto('/app/#/share')
            ui.wait(lambda s: 'Third Album' in s['text'], 'the share list shows no share')
            rows = checkboxes(ui, False)
            assert len(rows) >= 2, 'no share row listed'
            ui.call('check', target={'ref': rows[1]['ref']}, checked=True)
            ui.click('Delete')
            confirm_dialog(ui, DELETE_NAMES)
            corroborate(c, 'share', lambda r: r['status'] == 200 and len(r['body']) == 0, params=SHARES, what='share not deleted')
            ui.goto('/app/#/share')
        elif op == 'play-album':
            open_album(ui, a['title'])
            ui.click('Play')
            corroborate(c, 'song', lambda r: r['status'] == 200 and all(
                (x.get('playCount') or 0) >= 1 for x in r['body'] if x.get('title') in a['songs']) and
                {x.get('title') for x in r['body']} >= set(a['songs']), params=SONGS, timeout=30.0, what='the album was not played')
            ui.call('wait', seconds=1)
        elif op == 'play-later':
            open_album(ui, a['title'])
            ui.click('Play Later')
            ui.call('wait', seconds=2)
        elif op == 'remove-from-playlist':
            pid = identity(listed(c, 'playlist', 'name', a['playlist'], PAGE), 'name', a['playlist'])
            titles = [x.get('title') for x in c.native('GET', 'playlist/%s/tracks' % pid, params={'_start': 0, '_end': 50})['body']]
            ui.goto('/app/#/playlist/' + pid + '/show')
            ui.require(a['title'])
            ui.call('wait', seconds=1)
            row = checkboxes(ui, False)[titles.index(a['title']) + 1]
            ui.call('check', target={'ref': row['ref']}, checked=True)
            ui.click('Remove')
            confirm_dialog(ui, DELETE_NAMES)
            corroborate(c, 'playlist/' + pid + '/tracks', lambda r: r['status'] == 200 and len(r['body']) == a['count'],
                        params={'_start': 0, '_end': 50}, what='song not removed from the playlist')
            ui.goto('/app/#/playlist/' + pid + '/show')
        elif op == 'library-scan':
            ui.goto('/app/#/library')
            ui.require('Music Library')
            scanned = lambda r: r['status'] == 200 and int(r['headers'].get('x-total-count') or 0) == a['songs']
            ui.click('Quick Scan')
            corroborate(c, 'song', scanned, params=SONGS, timeout=30.0, what='the scan did not find the new song')
            corroborate(c, 'library/1', lambda r: r['status'] == 200 and r['body'].get('totalSongs') == a['songs'], timeout=30.0,
                        what='the library totals were not updated')
            # The page keeps the list it has loaded: reloading shows the new totals.
            ui.reload()
            ui.require(str(a['songs']), timeout=10.0)
        elif op == 'change-password':
            uid = identity(listed(c, 'user', 'userName', a['username'], {**PAGE, '_sort': 'userName'}), 'userName', a['username'])
            ui.goto('/app/#/user/' + uid)
            ui.wait(lambda s: any(x.get('name') == 'changePassword' for x in s['controls']), 'user form missing')
            ui.check('changePassword', True, labels=('Change Password?',))
            ui.fill('password', a['password'])
            ui.submit('Save')
            deadline = time.monotonic() + 10.0
            while c.reply(c.subsonic('ping', a['username'], password=a['password'])).get('status') != 'ok':
                assert time.monotonic() < deadline, 'password not changed'
                time.sleep(0.5)
            ui.goto('/app/#/user')
        elif op == 'sign-out':
            ui.goto('/app/#/album/all')
            ui.click('Settings', timeout=8.0)
            ui.call('wait', seconds=1)
            ui.call('click', target={'text': 'Logout'})
            ui.wait(lambda s: any(x.get('name') == 'username' for x in s['controls']), 'sign-in form missing after logout')
        elif op == 'set-language':
            ui.goto('/app/#/personal')
            ui.require('Language')
            current = next(x for x in ui.snapshot()['controls'] if x['tag'] == 'div' and any(n.startswith('English') for n in accessible(x)))
            ui.click_ref(current)
            ui.call('wait', seconds=1)
            choice = next(x for x in ui.snapshot()['controls'] if any(n.startswith(a['language']) for n in accessible(x)))
            ui.click_ref(choice)
            ui.call('wait', seconds=2)
        elif op == 'rename-player':
            rows = c.native('GET', 'player', params={'_start': 0, '_end': 20})['body']
            name = next(x['name'] for x in rows if x.get('client') == a['client'])
            ui.goto('/app/#/player')
            ui.require(name)
            ui.call('click', target={'text': name})
            ui.wait(lambda s: any(x.get('name') == 'name' for x in s['controls']), 'player form missing')
            ui.fill('name', a['name'])
            ui.submit('Save')
            corroborate(c, 'player', lambda r: r['status'] == 200 and any(x.get('client') == a['client'] and x.get('name') == a['name']
                                                                          for x in r['body']),
                        params={'_start': 0, '_end': 20}, what='player not renamed')
            ui.goto('/app/#/player')
        elif op == 'remove-missing':
            ui.goto('/app/#/missing')
            ui.wait(lambda s: len(checkboxes(ui, False)) >= 2, 'no missing file listed')
            ui.call('check', target={'ref': checkboxes(ui, False)[1]['ref']}, checked=True)
            ui.click('Remove')
            confirm_dialog(ui, DELETE_NAMES + ('remove',))
            corroborate(c, 'missing', lambda r: r['status'] == 200 and len(r['body']) == 0, params={'_start': 0, '_end': 20},
                        what='missing file not removed')
            ui.goto('/app/#/missing')
        elif op == 'rename-self':
            uid = str(c.state['bob']['id'])
            ui.goto('/app/#/user/' + uid)
            ui.wait(lambda s: any(x.get('name') == 'name' for x in s['controls']), 'account form missing')
            ui.fill('name', a['name'])
            ui.submit('Save')
            corroborate(c, 'user/' + uid, lambda r: r['status'] == 200 and r['body'].get('name') == a['name'],
                        what='account name not saved')
            ui.goto('/app/#/album/all')
            ui.goto('/app/#/user/' + uid)
            ui.wait(lambda s: any(x.get('name') == 'name' and x.get('value') == a['name'] for x in s['controls']),
                    'account page does not show the new name')
        elif op == 'create-library':
            ui.goto('/app/#/library/create')
            ui.wait(lambda s: any(x.get('name') == 'path' for x in s['controls']), 'library form missing')
            ui.fill('name', a['name'])
            ui.fill('path', a['path'])
            ui.submit('Save')
            listed(c, 'library', 'name', a['name'], {'_start': 0, '_end': 10})
            ui.goto('/app/#/library')
        else:
            raise ValueError('unknown reference operation ' + op)
    for text in checkpoint.get('visible', []):
        ui.require(resolve(text, c.state))
    time.sleep(0.2)
