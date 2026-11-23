"""Refreshing feeds: new entries, changed entries (title, content, link, date, tags), entries that left the feed,
read and starred state across refreshes, the ignore-entry-updates setting, feed fields after a refresh, and the
background refresh of one category and of every feed."""
import fixtures as fx
from fixtures import item, rss
from harness import CREDS, Ref, members, pathref, pick

DATE = 'Mon, 06 Jan 2025 {}:00:00 GMT'


def version(n, title='Refresh Daily'):
    items = [item('Stable story', 'http://refresh.test/stable', 'stable', DATE.format('08'), 'Stable body.'),
             item('Read story', 'http://refresh.test/read', 'read', DATE.format('09'), 'Read body.'),
             item('Starred story', 'http://refresh.test/starred', 'starred', DATE.format('10'), 'Starred body.')]
    if n == 1:
        items += [item('Changing story', 'http://refresh.test/changing', 'changing', DATE.format('11'), 'Old body.',
                       '<category>old-tag</category>'),
                  item('Leaving story', 'http://refresh.test/leaving', 'leaving', DATE.format('12'), 'Leaving body.')]
    else:
        items += [item('Changed story (updated)', 'http://refresh.test/changing-moved', 'changing', DATE.format('13'),
                       'New body with more words.', '<category>new-tag</category>'),
                  item('Arriving story', 'http://refresh.test/arriving', 'arriving', DATE.format('14'),
                       'Arriving body.')]
    return rss(title, 'http://refresh.test/', items)


def edited_doc(body):
    """The document of the edited-entry scenario: Stable story with the given body."""
    return rss('Edited Daily', 'http://refresh.test/', [
        item('Stable story', 'http://refresh.test/edited-stable', 'edited-stable', DATE.format('08'), body),
        item('Other story', 'http://refresh.test/edited-other', 'edited-other', DATE.format('09'), 'Other body.')])


def edited_entry(document=None):
    """Refresh the edited-entry feed (optionally with a new document) and read the edited entry back."""
    def action(c):
        if document is not None:
            c.web_put('http://refresh.test/edited.xml', document, fx.RSS_TYPE)
        r, p = c.request('PUT', f"feeds/{c.state['edited']['feed_id']}/refresh")
        rr, entry = c.request('GET', f"entries/{c.state['edited-e']['Stable story']['id']}")
        return {'refresh': r.status_code, 'entry': c.observe(rr, entry, view=pick('title', 'content'))}
    return action


def remember(key, feed_key):
    def action(c):
        c.state[key] = {e['title']: e for e in fx.entries_of(c, feed_key)}
    return action


def refresh(feed_key, document=None, url=None):
    def action(c):
        if document is not None:
            c.web_put(url, document, fx.RSS_TYPE)
        r, p = c.request('PUT', f"feeds/{c.state[feed_key]['feed_id']}/refresh")
        return c.observe(r, p)
    return action


def stored(feed_key, fields=('title', 'url', 'status', 'starred', 'published_at')):
    def action(c):
        r, p = c.request('GET', f"feeds/{c.state[feed_key]['feed_id']}/entries",
                         params={'order': 'published_at', 'direction': 'asc', 'limit': 100})
        return c.observe(r, p, view=members('entries', *fields))
    return action


def background(path, hosts):
    """Start a background refresh and wait until the requested hosts stop changing."""
    def action(c):
        mark = c.web_mark()
        r, p = c.request('PUT', path(c))
        asked = c.settle(lambda: sorted({x['url'] for x in c.web_requests(since=mark) if x['host'] in hosts}))
        return {'refresh': c.observe(r, p), 'fetched': asked}
    return action


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    urls = {name: f'http://refresh.test/{name}.xml' for name in ('main', 'frozen', 'renamed')}
    s.fixture('web', 'publish', fx.publish_all(
        [(u, version(1), fx.RSS_TYPE) for u in urls.values()] +
        [('http://cat-a.refresh.test/feed.xml', version(1, 'Category A'), fx.RSS_TYPE),
         ('http://cat-b.refresh.test/feed.xml', version(1, 'Category B'), fx.RSS_TYPE),
         ('http://all.refresh.test/one.xml', version(1, 'All one'), fx.RSS_TYPE),
         ('http://all.refresh.test/two.xml', version(1, 'All two'), fx.RSS_TYPE),
         ('http://refresh.test/edited.xml', edited_doc('Stable body.'), fx.RSS_TYPE)]))
    fx.subscribe(s, 'library', 'main', urls['main'], 'main')
    fx.subscribe(s, 'library', 'frozen', urls['frozen'], 'frozen', ignore_entry_updates=True)
    fx.subscribe(s, 'library', 'renamed', urls['renamed'], 'renamed')
    s.setup('library', 'rename', 'PUT', pathref('feeds/{id}', id=Ref('renamed', 'feed_id')),
            body={'title': 'My own title'})
    s.fixture('library', 'entries', remember('main-e', 'main'))
    s.setup('library', 'mark-read', 'PUT', 'entries', body={'entry_ids': [Ref('main-e', 'Read story', 'id')],
                                                            'status': 'read'})
    s.setup('library', 'star', 'PUT', pathref('entries/{id}/bookmark', id=Ref('main-e', 'Starred story', 'id')))
    s.setup('categories', 'a', 'POST', 'categories', body={'title': 'Refresh A'}, save='cat-a')
    s.setup('categories', 'b', 'POST', 'categories', body={'title': 'Refresh B'}, save='cat-b')
    fx.subscribe(s, 'categories', 'feed-a', 'http://cat-a.refresh.test/feed.xml', 'feed-a', category='cat-a')
    fx.subscribe(s, 'categories', 'feed-b', 'http://cat-b.refresh.test/feed.xml', 'feed-b', category='cat-b')
    L = ['fx:accounts', 'fx:web', 'fx:library']

    done = s.add('refresh', 'main', 'refresh', refresh('main', version(2), urls['main']), needs=L,
                 description='Refreshing a feed whose document changed.')
    main_entries = s.add('refresh', 'main', 'entries', stored('main'), needs=L + [done],
          description='After the refresh: new entries are unread, read and starred states are kept, and entries '
                      'that left the feed stay.')
    s.add('refresh', 'main', 'changed-entry', stored('main', ('title', 'url', 'content', 'tags', 'published_at')),
          needs=L + [done], requires=[done], description='An entry whose title, link, content, date and tags changed.')
    s.api('refresh', 'main', 'feed', 'GET', pathref('feeds/{id}', id=Ref('main', 'feed_id')), needs=L + [done],
          requires=[done], view=pick('title', 'site_url', 'parsing_error_count'),
          description='The feed after the refresh.')
    frozen = s.add('refresh', 'frozen', 'refresh', refresh('frozen', version(2), urls['frozen']), needs=L,
                   description='Refreshing a feed that ignores entry updates.')
    frozen_entries = s.add('refresh', 'frozen', 'entries', stored('frozen', ('title', 'url', 'content', 'status')),
                           needs=L + [frozen], requires=[done],
                           description='With entry updates ignored, existing entries keep their title and content.')
    renamed = s.add('refresh', 'renamed', 'refresh', refresh('renamed', version(2, 'Renamed upstream'),
                                                             urls['renamed']),
                    needs=L, description='Refreshing a feed the user renamed while its document changed title.')
    renamed_feed = s.api('refresh', 'renamed', 'feed', 'GET', pathref('feeds/{id}', id=Ref('renamed', 'feed_id')),
                         needs=L + [renamed], requires=[done], view=pick('title'),
                         description='Which title the renamed feed keeps.')
    s.add('refresh', 'main', 'unchanged-again', refresh('main'), needs=L, requires=[done],
          description='Refreshing again without changes.')
    s.add('refresh', 'main', 'entries-again', stored('main', ('title',)), needs=L + [done], requires=[done],
          description='A refresh without changes adds nothing.')

    C = L + ['fx:categories']
    s.add('refresh', 'category', 'background',
          background(lambda c: f"categories/{c.state['cat-a']['id']}/refresh", {'cat-a.refresh.test', 'cat-b.refresh.test'}),
          needs=C, description='Refreshing one category fetches only its feeds, in the background.')
    fx.subscribe(s, 'all', 'one', 'http://all.refresh.test/one.xml', 'all-one')
    fx.subscribe(s, 'all', 'two', 'http://all.refresh.test/two.xml', 'all-two')
    s.add('refresh', 'all', 'background', background(lambda c: 'feeds/refresh', {'all.refresh.test'}),
          needs=L + ['fx:categories', 'fx:all'], description='Refreshing all feeds fetches the feeds that are due.')

    # An entry the user edited, then refreshed unchanged and changed upstream.
    fx.subscribe(s, 'edited', 'feed', 'http://refresh.test/edited.xml', 'edited')
    s.fixture('edited', 'entries', remember('edited-e', 'edited'))
    E = L + ['fx:edited']
    edit = s.api('refresh', 'edited', 'edit', 'PUT',
                 pathref('entries/{id}', id=Ref('edited-e', 'Stable story', 'id')), needs=E,
                 body={'title': 'My edited title'}, view=pick('title'), description='Editing the title of an entry.')
    s.add('refresh', 'edited', 'unchanged', edited_entry(), needs=E + [edit],
          description='Whether a refresh of an unchanged document keeps the user\'s edit.')
    s.add('refresh', 'edited', 'changed-upstream', edited_entry(edited_doc('Stable body, revised upstream.')),
          needs=E + [edit], description='Whether a refresh with changed entry content replaces the user\'s edit.')

    # Bare confirmations of a refresh count together with the reads that show their effect.
    s.bind(done, main_entries)
    s.bind(frozen, frozen_entries)
    s.bind(renamed, renamed_feed)
