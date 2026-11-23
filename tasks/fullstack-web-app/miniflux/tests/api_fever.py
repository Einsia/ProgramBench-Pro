"""The Fever API, after the account enables it in the integration settings (the browser checkpoint): the API key
check, groups, feeds and their group relations, favicons, items with since_id, max_id and with_ids, the unread
and saved item lists, and marking items, feeds and groups."""
import hashlib

import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS, unordered

USER, PASSWORD = 'alice-fever', 'Fever-Pass-2026'
KEY = hashlib.md5(f'{USER}:{PASSWORD}'.encode()).hexdigest()
DATE = 'Mon, {:02d} Jan 2025 10:00:00 GMT'
ICON = fx.png(16, 16, (200, 150, 0))
NEWS = rss('Fever News', 'http://fever.test/news/', [
    item(f'News {n}', f'http://fever.test/news/{n}', f'news-{n}', DATE.format(n), fx.html_text(f'<p>News body {n}</p>'),
         f'<author>news{n}@fever.test (Reporter {n})</author>') for n in range(1, 5)])
BLOG = rss('Fever Blog', 'http://fever.test/blog/', [
    item(f'Blog {n}', f'http://fever.test/blog/{n}', f'blog-{n}', DATE.format(n + 10), f'Blog body {n}')
    for n in range(1, 4)])
SITE = page('Fever site', '<p>site</p>', head='<link rel="icon" type="image/png" href="/icon.png">\n')


def fever(query, form=None, key=KEY):
    """POST /fever/?<query> with the API key, normalized: ids are aliases, id lists multisets, refresh times clocks."""
    def action(c):
        body = {'api_key': key} if key is not None else {}
        body.update(form or {})
        r, p = c.request('POST', '/fever/' + ('?' + query if query else ''), None, form=body)
        if r.status_code >= 400 or not isinstance(p, dict):
            return {'status': r.status_code, 'body': p if isinstance(p, str) else None}
        return {'status': r.status_code, 'body': normalize(c, p)}
    return action


def normalize(c, p):
    n = c.norm
    out = {}
    for key, value in p.items():
        if key in ('last_refreshed_on_time',):
            out[key] = '[time]' if value else value
        elif key == 'groups':
            out[key] = unordered([{'id': n.identity('category', g['id']), 'title': g['title']} for g in value or []])
        elif key == 'feeds':
            out[key] = unordered([{'id': n.identity('feed', f['id']), 'favicon_id': n.identity('icon', f['favicon_id']),
                                   'title': f['title'], 'url': f['url'], 'site_url': f['site_url'],
                                   'is_spark': f['is_spark'], 'last_updated_on_time': '[time]' if f['last_updated_on_time']
                                   else f['last_updated_on_time']} for f in value or []])
        elif key == 'feeds_groups':
            out[key] = unordered([{'group_id': n.identity('category', g['group_id']),
                                   'feed_ids': unordered([n.identity('feed', int(x)) for x in g['feed_ids'].split(',') if x])}
                                  for g in value or []])
        elif key == 'favicons':
            out[key] = unordered([{'id': n.identity('icon', f['id']), 'data': f['data']} for f in value or []])
        elif key == 'items':
            out[key] = unordered([{'id': n.identity('entry', i['id']), 'feed_id': n.identity('feed', i['feed_id']),
                                   **{k: i[k] for k in ('title', 'author', 'url', 'is_saved', 'is_read',
                                                        'created_on_time')},
                                   'html': n.clean({'content': i['html']})['content']} for i in value or []])
        elif key in ('unread_item_ids', 'saved_item_ids'):
            out[key] = unordered([n.identity('entry', int(x)) for x in value.split(',') if x])
        else:
            out[key] = value
    return out


def ids(c, title_prefix):
    r, p = c.request('GET', 'entries', params={'limit': 100})
    return sorted(e['id'] for e in p['entries'] if e['title'].startswith(title_prefix))


def remember(c):
    r, p = c.request('GET', 'entries', params={'limit': 100})
    c.state['by-title'] = {e['title']: e for e in p['entries']}
    r, feeds = c.request('GET', 'feeds')
    c.state['feeds'] = {f['title']: f for f in feeds}
    r, cats = c.request('GET', 'categories')
    c.state['cats'] = {x['title']: x for x in cats}


def entry_id(title):
    return lambda c: str(c.state['by-title'][title]['id'])


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    s.fixture('web', 'publish', fx.publish_all([
        ('http://fever.test/news.xml', NEWS, fx.RSS_TYPE), ('http://fever.test/blog.xml', BLOG, fx.RSS_TYPE),
        ('http://fever.test/news/', SITE, fx.HTML_TYPE), ('http://fever.test/icon.png', ICON, 'image/png')]))
    s.setup('library', 'category', 'POST', 'categories', body={'title': 'Fever shelf'}, save='shelf')
    fx.subscribe(s, 'library', 'news', 'http://fever.test/news.xml', 'news', category='shelf')
    fx.subscribe(s, 'library', 'blog', 'http://fever.test/blog.xml', 'blog')
    s.fixture('library', 'remember', remember)
    s.setup('library', 'read', 'PUT', 'entries', body={'entry_ids': [lambda c: c.state['by-title']['News 1']['id']],
                                                       'status': 'read'})
    s.setup('library', 'star', 'PUT', 'entries', body={'entry_ids': [lambda c: c.state['by-title']['Blog 2']['id']],
                                                       'starred': True})
    L = ['fx:accounts', 'fx:web', 'fx:library']
    s.fixture('bob', 'subscribe', bob_subscription)

    auth = s.check('fever', 'auth', 'key', fever(''),
                   description='The Fever API accepts the MD5 of "username:password" as API key.')
    enabled = s.gui('integration', 'enable-fever',
                    f'Open the integration settings, activate the Fever API with the Fever username "{USER}" and '
                    f'the password "{PASSWORD}", and save.',
                    f'The integration settings show the Fever API activated with the username {USER}.',
                    [{'op': 'goto', 'path': '/integrations'}, {'op': 'expand', 'text': 'Fever', 'probe': 'Fever Username'},
                     {'op': 'check', 'field': 'fever_enabled'}, {'op': 'fill', 'field': 'fever_username', 'value': USER},
                     {'op': 'fill', 'field': 'fever_password', 'value': PASSWORD}, {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/integrations'}],
                    checks=[auth], needs=L)
    F = L + [enabled]
    wrong_key = s.add('fever', 'auth', 'wrong-key', fever('', key='0' * 32), needs=F, requires=[enabled],
          description='A wrong API key is not authenticated.')
    s.add('fever', 'auth', 'no-key', fever('', key=None), needs=F, requires=[enabled],
          description='A request without API key is not authenticated.')
    s.add('fever', 'auth', 'plain-password', fever('', key=PASSWORD), needs=F, requires=[enabled],
          description='The password itself is not the API key.')
    s.add('fever', 'read', 'groups', fever('api&groups'), needs=F,
          description='Groups are the account\'s categories, with their feeds.')
    s.add('fever', 'read', 'feeds', fever('api&feeds'), needs=F, description='Feeds with favicons and groups.')
    s.add('fever', 'read', 'favicons', fever('api&favicons'), needs=F, description='Favicons as data URLs.')
    items = s.add('fever', 'read', 'items', fever('api&items'), needs=F,
          description='Items with their feed, author, HTML, URL, read and saved state and creation time.')
    s.add('fever', 'read', 'since-id', since_id(), needs=F,
          description='Items after a given item id.')
    s.add('fever', 'read', 'max-id', max_id(), needs=F, description='Items before a given item id.')
    s.add('fever', 'read', 'with-ids', with_ids(), needs=F, description='Items with the given ids.')
    s.add('fever', 'read', 'unread', fever('api&unread_item_ids'), needs=F, description='The unread item ids.')
    s.add('fever', 'read', 'saved', fever('api&saved_item_ids'), needs=F, description='The saved item ids.')
    s.add('fever', 'read', 'links', fever('api&links'), needs=F, requires=[items], description='Hot links (none).')
    read = s.add('fever', 'write', 'item-read', mark('item', 'read', 'News 2'), needs=F,
                 description='Marking an item as read.')
    read_check = s.add('fever', 'write', 'item-read-check', fever('api&unread_item_ids'), needs=F + [read],
                       description='The read item left the unread ids.')
    unread = s.add('fever', 'write', 'item-unread', mark('item', 'unread', 'News 1'), needs=F,
                   description='Marking an item as unread.')
    saved = s.add('fever', 'write', 'item-saved', mark('item', 'saved', 'News 3'), needs=F,
                  description='Saving (starring) an item.')
    unsaved = s.add('fever', 'write', 'item-unsaved', mark('item', 'unsaved', 'Blog 2'), needs=F,
                    description='Unsaving an item.')
    saved_check = s.add('fever', 'write', 'saved-check', fever('api&saved_item_ids'), needs=F + [saved, unsaved],
                        description='The saved ids after saving and unsaving.')
    state_check = s.add('fever', 'write', 'state-check', state_view, needs=F + [read, unread, saved, unsaved],
                        description='The read and starred state of the entries after the item changes.')
    feed_read = s.add('fever', 'write', 'feed-read', mark_feed(), needs=F,
                      description='Marking a feed read before a time.')
    group_read = s.add('fever', 'write', 'group-read', mark_group(), needs=F,
                       description='Marking a group read before a time.')
    final_unread = s.add('fever', 'write', 'final-unread', fever('api&unread_item_ids'),
                         needs=F + [feed_read, group_read],
                         description='The unread ids after marking a feed and a group read.')
    s.add('fever', 'auth', 'other-account', other_account, needs=F, requires=[enabled],
          description='Another account\'s credentials are not this account\'s API key.')
    s.add('fever', 'auth', 'key-in-query', key_in_query, needs=F, requires=[wrong_key],
          description='The API key may be sent in the query.')
    s.add('fever', 'write', 'unknown-item', mark_unknown, needs=F, requires=[read],
          description='Marking an item that does not exist changes nothing.')
    foreign = s.add('fever', 'write', 'foreign-feed', foreign_feed, needs=F + ['fx:bob'], requires=[feed_read],
                    description='Marking another account\'s feed as read changes nothing there.')
    s.add('fever', 'write', 'all-read', mark_group_zero, needs=F, requires=[feed_read],
          description='Marking group 0 as read marks every item read.')

    # Bare acknowledgements count together with the reads that show their effect.
    s.bind(read, read_check)
    s.bind(unread, state_check)
    s.bind(saved, saved_check)
    s.bind(unsaved, saved_check)
    s.bind(feed_read, final_unread)
    s.bind(group_read, final_unread)


def since_id():
    def action(c):
        return fever('api&items&since_id=' + entry_id('News 2')(c))(c)
    return action


def max_id():
    def action(c):
        return fever('api&items&max_id=' + entry_id('Blog 2')(c))(c)
    return action


def with_ids():
    def action(c):
        wanted = ','.join(entry_id(t)(c) for t in ('News 3', 'Blog 1'))
        return fever('api&items&with_ids=' + wanted)(c)
    return action


def mark(kind, state, title):
    def action(c):
        return fever('api', {'mark': kind, 'as': state, 'id': entry_id(title)(c)})(c)
    return action


def mark_feed():
    def action(c):
        feed = c.state['feeds']['Fever News']['id']
        return fever('api', {'mark': 'feed', 'as': 'read', 'id': str(feed), 'before': '1735862400'})(c)
    return action


def mark_group():
    def action(c):
        group = c.state['cats']['All']['id']
        return fever('api', {'mark': 'group', 'as': 'read', 'id': str(group), 'before': '1736683200'})(c)
    return action


def state_view(c):
    r, p = c.request('GET', 'entries', params={'limit': 100, 'order': 'title'})
    return {'status': r.status_code, 'entries': [{k: e[k] for k in ('title', 'status', 'starred')}
                                                 for e in p['entries']]}


def other_account(c):
    key = hashlib.md5(b'bob:' + CREDS['bob'].encode()).hexdigest()
    return fever('', key=key)(c)


def key_in_query(c):
    r, p = c.request('POST', '/fever/?api&api_key=' + KEY, None, form={})
    return {'status': r.status_code, 'body': normalize(c, p) if isinstance(p, dict) else p}


def mark_unknown(c):
    out = fever('api', {'mark': 'item', 'as': 'read', 'id': '987654321'})(c)
    out['unread'] = fever('api&unread_item_ids')(c)['body']
    return out


def bob_subscription(c):
    c.web_put('http://fever.test/bob.xml', rss('Bob Fever', 'http://fever.test/bob/', [
        item('Bob item', 'http://fever.test/bob/1', 'bob-1', DATE.format(5), 'Bob body')]), fx.RSS_TYPE)
    r, cats = c.request('GET', 'categories', 'bob')
    r, p = c.request('POST', 'feeds', 'bob', body={'feed_url': 'http://fever.test/bob.xml', 'category_id': cats[0]['id']})
    assert r.status_code == 201, 'bob subscription failed'
    c.state['bob-feed'] = p['feed_id']


def foreign_feed(c):
    out = fever('api', {'mark': 'feed', 'as': 'read', 'id': str(c.state['bob-feed']), 'before': '1900000000'})(c)
    r, p = c.request('GET', 'entries', 'bob', params={'limit': 10})
    out['bob_entries'] = [{k: e[k] for k in ('title', 'status')} for e in p['entries']]
    return out


def mark_group_zero(c):
    out = fever('api', {'mark': 'group', 'as': 'read', 'id': '0', 'before': '1'})(c)
    out['unread'] = fever('api&unread_item_ids')(c)['body']
    return out
