"""The Google Reader API, after the account enables it in the integration settings (the browser checkpoint):
ClientLogin and tokens, user information, subscriptions and tags, stream item ids with their filters and
paging, item contents, tagging items read and starred, marking streams read, subscribing, renaming, moving and
unsubscribing feeds, renaming and removing labels."""
import re

import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS, norm_text, unordered

USER, PASSWORD = 'alice-reader', 'Reader-Pass-2026'
DATE = 'Mon, {:02d} Feb 2025 09:00:00 GMT'
ICON = fx.png(16, 16, (0, 120, 200))
WORLD = rss('Reader World', 'http://greader.test/world/', [
    item(f'World {n}', f'http://greader.test/world/{n}', f'world-{n}', DATE.format(n),
         fx.html_text(f'<p>World story {n}</p>'), f'<author>w{n}@greader.test (Writer {n})</author>'
         + ('<enclosure url="http://media.greader.test/w1.mp3" length="5" type="audio/mpeg"/>' if n == 1 else ''))
    for n in range(1, 5)])
TECH = rss('Reader Tech', 'http://greader.test/tech/', [
    item(f'Tech {n}', f'http://greader.test/tech/{n}', f'tech-{n}', DATE.format(n + 10), f'Tech story {n}')
    for n in range(1, 4)])
EXTRA = rss('Reader Extra', 'http://greader.test/extra/', [
    item('Extra 1', 'http://greader.test/extra/1', 'extra-1', DATE.format(20), 'Extra story')])
QUICK = rss('Reader Quick', 'http://greader.test/quick/', [
    item('Quick 1', 'http://greader.test/quick/1', 'quick-1', DATE.format(21), 'Quick story')])
SITE = page('Reader site', '<p>site</p>', head='<link rel="icon" type="image/png" href="/icon.png">\n')
LINKED = page('Linked site', '<p>A site with a feed link.</p>',
              head='<link rel="alternate" type="application/rss+xml" title="Linked" href="/linked.xml">\n')
LINKED_FEED = rss('Reader Linked', 'http://greader.test/site/', [
    item('Linked 1', 'http://greader.test/site/1', 'linked-1', DATE.format(22), 'Linked story')])
LONG_ID = re.compile(r'tag:google\.com,2005:reader/item/([0-9a-f]{16})')
FEED_ID = re.compile(r'^feed/(\d+)$')
USER_ID = re.compile(r'user/(\d+)/')
ICON_ID = re.compile(r'/feed-icon/([0-9a-f]+)')


def normalize(c, value, key=''):
    """Google Reader answers with opaque ids in strings: item ids (hexadecimal and decimal), feed and user ids
    and icon hashes become episode aliases; crawl and change times become clocks; tokens are secrets."""
    n = c.norm
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in ('crawlTimeMsec', 'updated') and v:
                out[k] = '[time]'
            elif k == 'id' and key == 'itemRefs' and isinstance(v, str) and v.isdigit():
                out[k] = n.identity('entry', int(v))
            elif k in ('userId', 'userProfileId') and isinstance(v, str) and v.isdigit():
                out[k] = n.identity('user', int(v))
            elif k in ('items', 'subscriptions', 'tags') and isinstance(v, list):
                out[k] = unordered([normalize(c, x, k) for x in v])
            elif k == 'content' and isinstance(v, str):
                out[k] = n.clean({'content': v})['content']
            else:
                out[k] = normalize(c, v, k)
        return out
    if isinstance(value, list):
        return [normalize(c, x, key) for x in value]
    if isinstance(value, str):
        for token in c.state.get('greader-tokens', ()):
            value = value.replace(token, '[token]')
        value = LONG_ID.sub(lambda m: 'item/' + n.identity('entry', int(m[1], 16)), value)
        value = FEED_ID.sub(lambda m: 'feed/' + n.identity('feed', int(m[1])), value)
        value = USER_ID.sub(lambda m: 'user/' + n.identity('user', int(m[1])) + '/', value)
        value = ICON_ID.sub(lambda m: '/feed-icon/' + n.identity('icon-hash', m[1]), value)
        return norm_text(value)
    return value


def remember_token(c, payload):
    """The token a ClientLogin answer hands out (text lines or JSON); later answers mention it as [token]."""
    if isinstance(payload, dict):
        token = payload.get('Auth')
    else:
        lines = dict(line.split('=', 1) for line in str(payload).strip().splitlines() if '=' in line)
        token = lines.get('Auth')
    if isinstance(token, str) and token:
        known = c.state.setdefault('greader-tokens', [])
        if token not in known:
            known.append(token)
        c.state['greader-token'] = token
    return token


def login(c):
    r, p = c.request('POST', '/accounts/ClientLogin', None, form={'Email': USER, 'Passwd': PASSWORD})
    token = remember_token(c, p) if r.status_code == 200 else None
    assert token, f'ClientLogin failed: {r.status_code}'
    return token


def reader(method, path, params=None, form=None, token=True):
    """One Google Reader request authenticated with the ClientLogin token (header for GET, T field for POST)."""
    def action(c):
        tok = c.state.get('greader-token') or login(c)
        headers = {}
        body = dict(form or {})
        if token is True:
            if method == 'GET':
                headers['Authorization'] = 'GoogleLogin auth=' + tok
            else:
                body['T'] = tok
        elif token:
            headers['Authorization'] = 'GoogleLogin auth=' + token
        query = {k: (v(c) if callable(v) else v) for k, v in (params or {}).items()}
        body = {k: (v(c) if callable(v) else v) for k, v in body.items()}
        r, p = c.request(method, '/reader/api/0/' + path, None, params=query or None, headers=headers or None,
                         form=body if method == 'POST' else None)
        out = {'status': r.status_code}
        if r.headers.get('x-reader-google-bad-token'):
            out['bad_token'] = r.headers.get('x-reader-google-bad-token')
        out['body'] = normalize(c, p) if isinstance(p, (dict, list)) else normalize(c, p.strip())
        return out
    return action


def entry_ids(c, *titles):
    r, p = c.request('GET', 'entries', params={'limit': 100})
    by_title = {e['title']: e['id'] for e in p['entries']}
    return [str(by_title[t]) for t in titles]


def ids_of(*titles, long=False, fmt=None):
    def value(c):
        found = entry_ids(c, *titles)
        if long:
            fmt_ = 'tag:google.com,2005:reader/item/%016x'
        else:
            fmt_ = fmt
        return [fmt_ % int(x) for x in found] if fmt_ else found
    return value


def feed_stream(title):
    def value(c):
        r, feeds = c.request('GET', 'feeds')
        return 'feed/' + str(next(f['id'] for f in feeds if f['title'] == title))
    return value


def state(c):
    r, p = c.request('GET', 'entries', params={'limit': 100, 'order': 'title'})
    return {'status': r.status_code, 'entries': [{k: e[k] for k in ('title', 'status', 'starred')} for e in p['entries']]}


def subscriptions(c):
    r, feeds = c.request('GET', 'feeds')
    return {'status': r.status_code, 'feeds': unordered([{'title': f['title'], 'feed_url': f['feed_url'],
                                                          'category': f['category']['title']} for f in feeds])}


def categories(c):
    r, cats = c.request('GET', 'categories')
    return {'status': r.status_code, 'categories': unordered(sorted(x['title'] for x in cats))}


def client_login(form, output=None):
    def action(c):
        body = dict(form)
        if output:
            body['output'] = output
        r, p = c.request('POST', '/accounts/ClientLogin', None, form=body)
        if r.status_code == 200:
            remember_token(c, p)
        return {'status': r.status_code, 'body': normalize(c, p) if isinstance(p, (dict, list)) else
                normalize(c, p.strip())}
    return action


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    s.fixture('web', 'publish', fx.publish_all([
        ('http://greader.test/world.xml', WORLD, fx.RSS_TYPE), ('http://greader.test/tech.xml', TECH, fx.RSS_TYPE),
        ('http://greader.test/extra.xml', EXTRA, fx.RSS_TYPE), ('http://greader.test/quick.xml', QUICK, fx.RSS_TYPE),
        ('http://greader.test/world/', SITE, fx.HTML_TYPE), ('http://greader.test/icon.png', ICON, 'image/png'),
        ('http://greader.test/site/', LINKED, fx.HTML_TYPE), ('http://greader.test/linked.xml', LINKED_FEED, fx.RSS_TYPE)]))
    s.setup('library', 'category', 'POST', 'categories', body={'title': 'Reader Shelf'}, save='shelf')
    fx.subscribe(s, 'library', 'world', 'http://greader.test/world.xml', 'world', category='shelf')
    fx.subscribe(s, 'library', 'tech', 'http://greader.test/tech.xml', 'tech')
    s.fixture('library', 'states', lambda c: (
        c.request('PUT', 'entries', body={'entry_ids': [int(x) for x in entry_ids(c, 'World 1', 'Tech 1')],
                                          'status': 'read'}),
        c.request('PUT', 'entries', body={'entry_ids': [int(x) for x in entry_ids(c, 'World 2')], 'starred': True})))
    L = ['fx:accounts', 'fx:web', 'fx:library']

    logged = s.check('greader', 'login', 'text', client_login({'Email': USER, 'Passwd': PASSWORD}),
                     description='ClientLogin answers SID, LSID and Auth lines with the token.')
    enabled = s.gui('integration', 'enable-google-reader',
                    f'Open the integration settings, activate the Google Reader API with the username "{USER}" and '
                    f'the password "{PASSWORD}", and save.',
                    f'The integration settings show the Google Reader API activated with the username {USER}.',
                    [{'op': 'goto', 'path': '/integrations'}, {'op': 'expand', 'text': 'Google Reader', 'probe': 'Google Reader Username'},
                     {'op': 'check', 'field': 'googlereader_enabled'},
                     {'op': 'fill', 'field': 'googlereader_username', 'value': USER},
                     {'op': 'fill', 'field': 'googlereader_password', 'value': PASSWORD},
                     {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/integrations'}],
                    checks=[logged], needs=L)
    G = L + [enabled]
    s.add('greader', 'login', 'json', client_login({'Email': USER, 'Passwd': PASSWORD}, 'json'), needs=G,
          description='ClientLogin with JSON output.')
    s.add('greader', 'login', 'wrong-password', client_login({'Email': USER, 'Passwd': 'nope'}), needs=G,
          requires=[enabled], description='ClientLogin refuses a wrong password.')
    s.add('greader', 'login', 'account-password', client_login({'Email': 'alice', 'Passwd': CREDS['alice']}),
          needs=G, requires=[enabled], description='The account\'s own credentials are not the Google Reader login.')
    s.add('greader', 'login', 'missing', client_login({'Email': USER}), needs=G, requires=[enabled],
          description='ClientLogin needs both fields.')
    s.add('greader', 'token', 'header', reader('GET', 'token'), needs=G, description='The token endpoint.')
    s.add('greader', 'token', 'bad', reader('GET', 'user-info', token='alice-reader/' + '0' * 64), needs=G,
          requires=[enabled], description='A wrong token is refused and flagged.')
    s.add('greader', 'token', 'none', reader('GET', 'user-info', token=False), needs=G, requires=[enabled],
          description='A request without token is refused.')
    s.add('greader', 'info', 'user', reader('GET', 'user-info', {'output': 'json'}), needs=G,
          description='User information.')
    s.add('greader', 'info', 'subscriptions', reader('GET', 'subscription/list', {'output': 'json'}), needs=G,
          description='Subscriptions with categories, URLs and icons.')
    s.add('greader', 'info', 'tags', reader('GET', 'tag/list', {'output': 'json'}), needs=G,
          description='Tags: the starred state and the labels.')
    reading = s.add('greader', 'stream', 'reading-list', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/reading-list', 'output': 'json'}), needs=G,
        description='Item ids of the reading list, newest first.')
    s.add('greader', 'stream', 'oldest-first', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/reading-list', 'r': 'o', 'output': 'json'}), needs=G,
        description='Item ids oldest first.')
    s.add('greader', 'stream', 'count', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/reading-list', 'n': '3', 'output': 'json'}), needs=G,
        description='A limited number of item ids with a continuation.')
    s.add('greader', 'stream', 'continuation', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/reading-list', 'n': '3', 'c': '3', 'output': 'json'}), needs=G,
        description='The next page of item ids.')
    s.add('greader', 'stream', 'exclude-read', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/reading-list', 'xt': 'user/-/state/com.google/read', 'output': 'json'}),
        needs=G, description='Read items excluded.')
    s.add('greader', 'stream', 'starred', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/starred', 'output': 'json'}), needs=G, description='Starred item ids.')
    s.add('greader', 'stream', 'read', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/read', 'output': 'json'}), needs=G, description='Read item ids.')
    s.add('greader', 'stream', 'feed', reader('GET', 'stream/items/ids', {
        's': feed_stream('Reader Tech'), 'output': 'json'}), needs=G, description='Item ids of one feed.')
    s.add('greader', 'stream', 'time-window', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/reading-list', 'ot': '1738486800', 'nt': '1739350800', 'output': 'json'}),
        needs=G, description='Item ids published inside a time window.')
    s.add('greader', 'stream', 'no-json', reader('GET', 'stream/items/ids', {
        's': 'user/-/state/com.google/reading-list'}), needs=G, requires=[reading],
        description='Stream ids need JSON output.')
    contents = s.add('greader', 'contents', 'short-ids', reader('POST', 'stream/items/contents', form={
        'i': ids_of('World 1', 'Tech 2'), 'output': 'json'}), needs=G,
        description='Item contents requested by decimal ids.')
    s.add('greader', 'contents', 'long-ids', reader('POST', 'stream/items/contents', form={
        'i': ids_of('World 3', long=True), 'output': 'json'}), needs=G,
        description='Item contents requested by long item ids.')
    s.add('greader', 'contents', 'no-ids', reader('POST', 'stream/items/contents', form={'output': 'json'}), needs=G,
          requires=[contents], description='Item contents without ids.')
    marked = s.add('greader', 'edit', 'read', reader('POST', 'edit-tag', form={
        'i': ids_of('World 3', 'Tech 3'), 'a': 'user/-/state/com.google/read'}), needs=G,
        description='Tagging items as read.')
    unread_tag = s.add('greader', 'edit', 'unread', reader('POST', 'edit-tag', form={
        'i': ids_of('World 1'), 'r': 'user/-/state/com.google/read'}), needs=G,
        description='Removing the read tag.')
    star = s.add('greader', 'edit', 'star', reader('POST', 'edit-tag', form={
        'i': ids_of('Tech 1', long=True), 'a': 'user/-/state/com.google/starred'}), needs=G,
        description='Starring an item.')
    unstar = s.add('greader', 'edit', 'unstar', reader('POST', 'edit-tag', form={
        'i': ids_of('World 2'), 'r': 'user/-/state/com.google/starred'}), needs=G, description='Unstarring an item.')
    s.add('greader', 'edit', 'conflict', reader('POST', 'edit-tag', form={
        'i': ids_of('World 4'), 'a': 'user/-/state/com.google/read', 'r': 'user/-/state/com.google/read'}),
        needs=G, requires=[marked], description='Adding and removing the same tag is refused.')
    edit_state = s.add('greader', 'edit', 'state', state, needs=G + [marked, unread_tag, star, unstar],
                       description='The entries after the tag changes.')
    feed_read = s.add('greader', 'mark', 'feed', reader('POST', 'mark-all-as-read', form={
        's': feed_stream('Reader Tech'), 'ts': '1739800000000000'}), needs=G,
        description='Marking one feed\'s stream read up to a time.')
    label_read = s.add('greader', 'mark', 'label', reader('POST', 'mark-all-as-read', form={
        's': 'user/-/label/Reader Shelf', 'ts': '1738659600000000'}), needs=G,
        description='Marking a label read up to a time.')
    mark_state = s.add('greader', 'mark', 'state', state, needs=G + [feed_read, label_read],
                       description='The entries after marking streams read.')
    quick = s.add('greader', 'subscription', 'quickadd', reader('POST', 'subscription/quickadd', form={
        'quickadd': 'http://greader.test/quick.xml'}), needs=G, description='Quick-adding a subscription.')
    subscribed = s.add('greader', 'subscription', 'subscribe', reader('POST', 'subscription/edit', form={
        'ac': 'subscribe', 's': 'feed/http://greader.test/extra.xml', 't': 'Extra by Reader',
        'a': 'user/-/label/New Label'}), needs=G, description='Subscribing with a title into a new label.')
    after_subscribe = s.add('greader', 'subscription', 'after-subscribe', subscriptions, needs=G + [quick, subscribed],
                            description='The subscriptions after quick-adding and subscribing.')
    feed_renamed = s.add('greader', 'subscription', 'rename', reader('POST', 'subscription/edit', form={
        'ac': 'edit', 's': feed_stream('Reader Tech'), 't': 'Tech Renamed'}), needs=G,
        description='Renaming a subscription.')
    moved = s.add('greader', 'subscription', 'move', reader('POST', 'subscription/edit', form={
        'ac': 'edit', 's': feed_stream('Reader World'), 'a': 'user/-/label/Moved Label'}), needs=G,
        description='Moving a subscription to another label.')
    unsubscribed = s.add('greader', 'subscription', 'unsubscribe', reader('POST', 'subscription/edit', form={
        'ac': 'unsubscribe', 's': feed_stream('Reader Quick')}), needs=G, description='Unsubscribing.')
    after_edits = s.add('greader', 'subscription', 'after-edits', subscriptions,
                        needs=G + [quick, subscribed, feed_renamed, moved, unsubscribed],
                        description='The subscriptions after renaming, moving and unsubscribing.')
    renamed = s.add('greader', 'tag', 'rename', reader('POST', 'rename-tag', form={
        's': 'user/-/label/New Label', 'dest': 'user/-/label/Renamed Label'}), needs=G,
        description='Renaming a label.')
    disabled = s.add('greader', 'tag', 'disable', reader('POST', 'disable-tag', form={'s': 'user/-/label/Moved Label'}),
                     needs=G, description='Removing a label.')
    tag_categories = s.add('greader', 'tag', 'categories', categories, needs=G + [renamed, disabled],
                           description='The categories after renaming and removing labels.')
    tag_feeds = s.add('greader', 'tag', 'feeds-after', subscriptions, needs=G + [renamed, disabled],
                      description='Where the feeds of a removed label went.')
    s.add('greader', 'fallback', 'unknown', reader('GET', 'unread-count', {'output': 'json'}), needs=G,
          requires=[reading], description='An endpoint the product does not implement.')
    s.add('greader', 'ids', 'short-hex', reader('POST', 'stream/items/contents', form={
        'i': ids_of('World 4', fmt='tag:google.com,2005:reader/item/%x'), 'output': 'json'}), needs=G,
        description='Item contents requested by a long item id without zero padding.')
    s.add('greader', 'ids', 'bare-hex', reader('POST', 'stream/items/contents', form={
        'i': ids_of('Tech 2', fmt='%016x'), 'output': 'json'}), needs=G,
        description='Item contents requested by a bare 16-digit hexadecimal id.')
    s.add('greader', 'ids', 'feed-exclude-read', reader('GET', 'stream/items/ids', {
        's': feed_stream('Reader World'), 'xt': 'user/-/state/com.google/read', 'output': 'json'}), needs=G,
        description='Unread item ids of one feed.')
    kept = s.add('greader', 'ids', 'user-prefix', reader('POST', 'edit-tag', form={
        'i': ids_of('Extra 1'), 'a': lambda c: f"user/{c.state['alice']['id']}/state/com.google/read"}), needs=G,
        description='Tags may name the user explicitly instead of "-".')
    kept_unread = s.add('greader', 'ids', 'kept-unread', reader('POST', 'edit-tag', form={
        'i': ids_of('World 2'), 'a': 'user/-/state/com.google/kept-unread'}), needs=G,
        description='The kept-unread tag marks items unread.')
    state_after = s.add('greader', 'ids', 'state-after', state, needs=G + [kept, kept_unread],
                        description='The entries after the explicit-user and kept-unread tags.')
    s.add('greader', 'errors', 'edit-to-feed', reader('POST', 'subscription/edit', form={
        'ac': 'edit', 's': feed_stream('Reader World'), 'a': feed_stream('Tech Renamed')}), needs=G,
        requires=[reading], description='A subscription can only be moved to a label.')
    s.add('greader', 'errors', 'edit-unknown-feed', reader('POST', 'subscription/edit', form={
        'ac': 'edit', 's': 'feed/987654321', 't': 'Nothing'}), needs=G, requires=[reading],
        description='Renaming a subscription that does not exist.')
    s.add('greader', 'errors', 'unknown-action', reader('POST', 'subscription/edit', form={
        'ac': 'frobnicate', 's': feed_stream('Reader World')}), needs=G, requires=[reading],
        description='An unknown subscription action.')
    s.add('greader', 'errors', 'rename-to-existing', reader('POST', 'rename-tag', form={
        's': 'user/-/label/Renamed Label', 'dest': 'user/-/label/Reader Shelf'}), needs=G, requires=[renamed],
        description='Renaming a label to the title of another label.')
    s.add('greader', 'errors', 'rename-unknown', reader('POST', 'rename-tag', form={
        's': 'user/-/label/No Such Label', 'dest': 'user/-/label/Anything'}), needs=G, requires=[renamed],
        description='Renaming a label that does not exist.')
    s.add('greader', 'errors', 'disable-not-label', reader('POST', 'disable-tag', form={
        's': 'user/-/state/com.google/starred'}), needs=G, requires=[renamed],
        description='Only labels can be removed.')
    s.add('greader', 'errors', 'quickadd-invalid', reader('POST', 'subscription/quickadd', form={
        'quickadd': 'not a url'}), needs=G, requires=[quick], description='Quick-adding something that is no URL.')
    s.add('greader', 'subscription', 'quickadd-site', reader('POST', 'subscription/quickadd', form={
        'quickadd': 'http://greader.test/site/'}), needs=G,
        description='Quick-adding a web site subscribes to the feed it links.')
    marked_all = s.add('greader', 'mark', 'reading-list', reader('POST', 'mark-all-as-read', form={
        's': 'user/-/state/com.google/reading-list', 'ts': '1739000000'}), needs=G,
        description='Marking the reading list read up to a time given in seconds.')
    reading_state = s.add('greader', 'mark', 'reading-list-state', state, needs=G + [marked_all],
                          description='The entries after marking the reading list read.')

    # Bare "OK" acknowledgements count together with the reads that show their effect.
    for change in (marked, unread_tag, star, unstar):
        s.bind(change, edit_state)
    for change in (feed_read, label_read):
        s.bind(change, mark_state)
    s.bind(subscribed, after_subscribe)
    for change in (feed_renamed, moved, unsubscribed):
        s.bind(change, after_edits)
    s.bind(renamed, tag_categories)
    s.bind(disabled, tag_feeds)
    for change in (kept, kept_unread):
        s.bind(change, state_after)
    s.bind(marked_all, reading_state)
