"""Categories through the REST API: listing with counters, creation, renaming, hiding, removal, their feeds and
entries, marking as read and refreshing, and isolation between accounts."""
import fixtures as fx
from fixtures import item, rss
from harness import CREDS, Ref, contextual, members, pathref, pick, unordered

TECH = rss('Tech Wire', 'http://cats.test/tech/', [
    item('Compilers explained', 'http://cats.test/tech/compilers', 'tech-1', 'Mon, 03 Mar 2025 08:00:00 GMT',
         'How compilers work.'),
    item('Network basics', 'http://cats.test/tech/network', 'tech-2', 'Tue, 04 Mar 2025 08:00:00 GMT',
         'Packets and routes.'),
    item('Storage engines', 'http://cats.test/tech/storage', 'tech-3', 'Wed, 05 Mar 2025 08:00:00 GMT',
         'Pages and logs.'),
])
SCIENCE = rss('Science Notes', 'http://cats.test/science/', [
    item('Cell biology', 'http://cats.test/science/cells', 'sci-1', 'Thu, 06 Mar 2025 08:00:00 GMT', 'Cells.'),
    item('Plate tectonics', 'http://cats.test/science/plates', 'sci-2', 'Fri, 07 Mar 2025 08:00:00 GMT', 'Plates.'),
])


FIXTURE_TITLES = ('All', 'Tech', 'Science', 'Empty shelf')


def fixture_ids(c):
    return {c.state['category-alice']['id'], c.state['cat-tech']['id'], c.state['cat-science']['id'],
            c.state['cat-empty']['id']}


def titled(*titles):
    """View: the listed members whose title is one of titles, in the product's order (other members belong to
    other points)."""
    def view(payload):
        assert isinstance(payload, list), 'expected the category list'
        return [{'title': x['title'], 'hide_globally': x['hide_globally']} for x in payload if x['title'] in titles]
    return view


@contextual
def fixture_counts(payload, c):
    """Unread counters of the categories with feeds, identified by id (whatever their titles became)."""
    assert isinstance(payload, list), 'expected the category list'
    wanted = (c.state['cat-tech']['id'], c.state['cat-science']['id'])
    return unordered([{'category_id': x['id'], 'total_unread': x['total_unread']} for x in payload if x['id'] in wanted])


@contextual
def fixture_remaining(payload, c):
    """Which of the fixture categories remain, by id."""
    assert isinstance(payload, list), 'expected the category list'
    return unordered([{'category_id': x['id']} for x in payload if x['id'] in fixture_ids(c)])


@contextual
def feeds_by_category(payload, c):
    assert isinstance(payload, list), 'expected the feed list'
    return unordered([{'title': x['title'], 'category_id': x['category']['id']} for x in payload])


def refreshed_hosts(c):
    """Refreshing one category fetches its feeds (in the background)."""
    mark = c.web_mark()
    r, p = c.request('PUT', f"categories/{c.state['cat-science']['id']}/refresh")
    asked = c.settle(lambda: sorted({x['url'] for x in c.web_requests(host='cats.test', since=mark)
                                     if x['url'].endswith('.xml')}))
    return {'status': r.status_code, 'fetched': asked}


def first_entry(feed_key, save):
    def action(c):
        c.state[save] = fx.entries_of(c, feed_key)[0]
    return action


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    fx.default_category(s, 'accounts', 'bob')
    s.fixture('web', 'publish', fx.publish_all([('http://cats.test/tech.xml', TECH, fx.RSS_TYPE),
                                                 ('http://cats.test/science.xml', SCIENCE, fx.RSS_TYPE)]))
    s.setup('library', 'tech', 'POST', 'categories', body={'title': 'Tech'}, save='cat-tech')
    s.setup('library', 'science', 'POST', 'categories', body={'title': 'Science'}, save='cat-science')
    s.setup('library', 'empty', 'POST', 'categories', body={'title': 'Empty shelf'}, save='cat-empty')
    fx.subscribe(s, 'library', 'tech-feed', 'http://cats.test/tech.xml', 'feed-tech', category='cat-tech')
    fx.subscribe(s, 'library', 'science-feed', 'http://cats.test/science.xml', 'feed-science',
                 category='cat-science')
    s.fixture('library', 'entries', first_entry('feed-tech', 'tech-first'))
    L = ['fx:accounts', 'fx:web', 'fx:library']
    tech = pathref('categories/{id}', id=Ref('cat-tech', 'id'))
    science = pathref('categories/{id}', id=Ref('cat-science', 'id'))

    listed = s.api('categories', 'list', 'titles', 'GET', 'categories', needs=L, view=pick('title', 'hide_globally'),
                   description='The account\'s categories, sorted as the product sorts them.')
    s.api('categories', 'list', 'counts', 'GET', 'categories', params={'counts': True}, needs=L,
          view=pick('title', 'feed_count', 'total_unread'),
          description='With counts=true every category carries its number of feeds and unread entries.')
    s.api('categories', 'list', 'other-account', 'GET', 'categories', actor='bob', needs=L,
          view=pick('title'), requires=[listed], description='Another account sees only its own categories.')
    sorting = s.api('categories', 'sorting', 'alphabetical', 'PUT', pathref('users/{id}', id=Ref('alice', 'id')),
                    body={'categories_sorting_order': 'alphabetical'}, needs=L, view=pick('categories_sorting_order'),
                    description='The account sorts categories alphabetically.')
    s.api('categories', 'sorting', 'alphabetical-list', 'GET', 'categories', params={'counts': True}, needs=L,
          requires=[sorting], view=titled(*FIXTURE_TITLES),
          description='With alphabetical sorting the counted list is ordered by title, not by unread entries.')
    s.setup('sorting-restore', 'unread-count', 'PUT', pathref('users/{id}', id=Ref('alice', 'id')),
            body={'categories_sorting_order': 'unread_count'})

    created = s.api('categories', 'create', 'plain', 'POST', 'categories', body={'title': 'Reading list'},
                    description='Creating a category returns it.')
    hidden = s.api('categories', 'create', 'hidden', 'POST', 'categories', body={'title': 'Muted', 'hide_globally': True},
          view=pick('title', 'hide_globally'), description='A category can be created hidden from the global lists.')
    unicode_title = s.api('categories', 'create', 'unicode', 'POST', 'categories', body={'title': 'Ciência 科学'},
                          view=pick('title'),
          description='Category titles keep non-ASCII text.')
    s.api('categories', 'create', 'padded', 'POST', 'categories', body={'title': '  Padded title  '},
          view=pick('title'), description='Whether surrounding spaces of a title are kept.')
    s.api('categories', 'create', 'duplicate', 'POST', 'categories', body={'title': 'Tech'}, needs=L,
          requires=[created], description='A title already used by the account is refused.')
    s.api('categories', 'create', 'duplicate-case', 'POST', 'categories', body={'title': 'TECH'}, needs=L,
          requires=[created], view=pick('title'), description='Whether titles differing only in case are distinct.')
    s.api('categories', 'create', 'empty', 'POST', 'categories', body={'title': ''}, requires=[created],
          description='The title is mandatory.')
    s.api('categories', 'create', 'blank', 'POST', 'categories', body={'title': '   '}, requires=[created],
          description='Whether a title of spaces only is accepted.')
    s.api('categories', 'create', 'anonymous', 'POST', 'categories', actor=None, body={'title': 'Nope'},
          requires=[created], description='Creating a category needs credentials.')
    s.api('categories', 'create', 'same-title-other-account', 'POST', 'categories', actor='bob',
          body={'title': 'Tech'}, needs=L, requires=[created], view=pick('title'),
          description='Another account may use a title that this account already uses.')
    s.api('categories', 'list', 'after-create', 'GET', 'categories', needs=L + [created, hidden, unicode_title],
          view=titled(*FIXTURE_TITLES, 'Reading list', 'Muted', 'Ciência 科学'),
          description='The category list after the creations, sorted by title.')

    renamed = s.api('categories', 'update', 'rename', 'PUT', tech, body={'title': 'Technology'}, needs=L,
                    view=pick('id', 'title', 'hide_globally'), hint='category',
                    description='Renaming a category returns it.')
    s.api('categories', 'update', 'hide', 'PUT', tech, body={'hide_globally': True}, needs=L,
          view=pick('title', 'hide_globally'), description='A category can be hidden from the global lists.')
    s.api('categories', 'update', 'unhide', 'PUT', tech, body={'hide_globally': False}, needs=L,
          view=pick('title', 'hide_globally'), description='A hidden category can be shown again.')
    s.api('categories', 'update', 'duplicate', 'PUT', science, body={'title': 'Technology'}, needs=L,
          requires=[renamed], description='Renaming to a title the account already uses is refused.')
    s.api('categories', 'update', 'empty', 'PUT', science, body={'title': ''}, needs=L, requires=[renamed],
          description='A category cannot get an empty title.')
    s.api('categories', 'update', 'missing', 'PUT', 'categories/987654', body={'title': 'Ghost'},
          requires=[renamed], description='Updating an unknown category is not found.')
    s.api('categories', 'update', 'other-account', 'PUT', tech, actor='bob', body={'title': 'Stolen'}, needs=L,
          requires=[renamed], description='Another account cannot update the category.')

    feeds = s.api('categories', 'feeds', 'list', 'GET', pathref('categories/{id}/feeds', id=Ref('cat-tech', 'id')),
                  needs=L, view=pick('title', 'feed_url', 'category.title'),
                  description='The feeds of one category.')
    s.api('categories', 'feeds', 'other-account', 'GET', pathref('categories/{id}/feeds', id=Ref('cat-tech', 'id')),
          actor='bob', needs=L, requires=[feeds], view=pick('title'),
          description='Another account cannot list the feeds of the category.')
    entries = s.api('categories', 'entries', 'list', 'GET',
                    pathref('categories/{id}/entries', id=Ref('cat-tech', 'id')),
                    params={'order': 'published_at', 'direction': 'asc'}, needs=L,
                    view=members('entries', 'title', 'status', 'feed.title'),
                    description='The entries of one category, oldest first.')
    s.api('categories', 'entries', 'filtered', 'GET', pathref('categories/{id}/entries', id=Ref('cat-tech', 'id')),
          params={'order': 'published_at', 'direction': 'desc', 'limit': 2}, needs=L,
          view=members('entries', 'title'), description='Category entries newest first, limited to two.')
    s.api('categories', 'entries', 'one', 'GET',
          pathref('categories/{c}/entries/{e}', c=Ref('cat-tech', 'id'), e=Ref('tech-first', 'id')), needs=L,
          view=pick('title', 'url', 'feed.title'), description='One entry read through its category.')
    s.api('categories', 'entries', 'wrong-category', 'GET',
          pathref('categories/{c}/entries/{e}', c=Ref('cat-science', 'id'), e=Ref('tech-first', 'id')), needs=L,
          requires=[entries], description='An entry is not found through another category.')
    marked = s.api('categories', 'read', 'mark', 'PUT',
                   pathref('categories/{id}/mark-all-as-read', id=Ref('cat-tech', 'id')), needs=L,
                   description='Marking every entry of a category as read.')
    counts_after = s.api('categories', 'read', 'counts-after', 'GET', 'categories', params={'counts': True},
                         needs=L + [marked], view=fixture_counts,
                         description='The unread counters after marking one category as read.')
    s.api('categories', 'read', 'other-account', 'PUT',
          pathref('categories/{id}/mark-all-as-read', id=Ref('cat-science', 'id')), actor='bob', needs=L,
          requires=[marked], description='Another account cannot mark the category as read.')
    refreshed = s.add('categories', 'refresh', 'one', refreshed_hosts, needs=L,
                      description='Refreshing one category fetches its feeds.')
    s.api('categories', 'refresh', 'missing', 'PUT', 'categories/987654/refresh', requires=[refreshed],
          description='Refreshing an unknown category.')

    removed = s.api('categories', 'delete', 'empty', 'DELETE',
                    pathref('categories/{id}', id=Ref('cat-empty', 'id')), needs=L,
                    description='Removing a category without feeds.')
    with_feeds = s.api('categories', 'delete', 'with-feeds', 'DELETE', science, needs=L,
                       description='Removing a category that still has feeds.')
    feeds_after = s.api('categories', 'delete', 'feeds-after', 'GET', 'feeds', needs=L + [with_feeds],
                        view=feeds_by_category, description='The feeds left after removing a category that had feeds.')
    s.api('categories', 'delete', 'missing', 'DELETE', 'categories/987654', requires=[removed],
          description='Removing an unknown category is not found.')
    s.api('categories', 'delete', 'other-account', 'DELETE', tech, actor='bob', needs=L, requires=[removed],
          description='Another account cannot remove the category.')
    final = s.api('categories', 'list', 'final', 'GET', 'categories', needs=L + [removed, with_feeds],
                  view=fixture_remaining, description='Which of the fixture categories remain.')

    # Bare confirmations count together with the reads that show their effect.
    s.bind(marked, counts_after)
    s.bind(removed, final)
    s.bind(with_feeds, feeds_after)
