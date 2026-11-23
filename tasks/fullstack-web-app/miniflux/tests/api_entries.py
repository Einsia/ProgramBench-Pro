"""Entries through the REST API: listing with every filter, sort order and page, single entries and their
enclosures, read and starred state (one by one and in bulk), editing, media progress, marking everything as
read, flushing the history, saving without integrations, and importing entries into a feed."""
import calendar
import datetime

import fixtures as fx
from fixtures import rss
from harness import CREDS, Ref, grouped, members, pathref, pick, unordered

DC = ' xmlns:dc="http://purl.org/dc/elements/1.1/"'


def rfc822(stamp):
    return datetime.datetime.fromisoformat(stamp).strftime('%a, %d %b %Y %H:%M:%S GMT')


def unix(stamp):
    return calendar.timegm(datetime.datetime.fromisoformat(stamp).timetuple())


def entry(title, slug, stamp, author=None, tags=(), extra=''):
    parts = [f'<item><title>{title}</title><link>http://entries.test/{slug}</link><guid>{slug}</guid>',
             f'<pubDate>{rfc822(stamp)}</pubDate><description>{title} text.</description>']
    if author:
        parts.append(f'<dc:creator>{author}</dc:creator>')
    parts += [f'<category>{t}</category>' for t in tags]
    parts.append(extra + '</item>\n')
    return ''.join(parts)


ALPHA = rss('Alpha Times', 'http://entries.test/alpha/', [
    entry('Alpha morning', 'alpha/1', '2025-01-01T08:00:00', 'Ann Lee', ['world']),
    entry('Alpha budget', 'alpha/2', '2025-01-02T08:00:00', 'Ben Ode', ['economy']),
    entry('Alpha storm', 'alpha/3', '2025-01-04T08:00:00', 'Ann Lee', ['weather', 'world']),
    entry('Alpha harvest', 'alpha/4', '2025-01-06T08:00:00', 'Cid Roy', ['economy'])], namespaces=DC)
BETA = rss('Beta Weekly', 'http://entries.test/beta/', [
    entry('Beta review', 'beta/1', '2025-01-03T12:00:00', 'Dee Fox'),
    entry('Beta interview', 'beta/2', '2025-01-05T12:00:00', 'Ann Lee'),
    entry('Beta outlook', 'beta/3', '2025-01-07T12:00:00', 'Eve Moss')], namespaces=DC)
GAMMA = rss('Gamma Podcast', 'http://entries.test/gamma/', [
    entry('Gamma episode one', 'gamma/1', '2024-12-20T10:00:00', 'Gil Hart', extra=(
        '<enclosure url="http://media.entries.test/ep1.mp3" length="123456" type="audio/mpeg"/>')),
    entry('Gamma episode two', 'gamma/2', '2024-12-27T10:00:00', 'Gil Hart', extra=(
        '<enclosure url="http://media.entries.test/ep2.mp3" length="654321" type="audio/mpeg"/>'))],
    namespaces=DC)
HIDDEN = rss('Hidden Notes', 'http://entries.test/hidden/', [
    entry('Hidden memo', 'hidden/1', '2025-01-08T09:00:00', 'Hal Ito')], namespaces=DC)
QUIET = rss('Quiet Corner', 'http://entries.test/quiet/', [
    entry('Quiet thought', 'quiet/1', '2025-01-09T09:00:00', 'Ivy Low')], namespaces=DC)
TITLES = members('entries', 'title')


def remember_entries(actor, key):
    def action(c):
        r, payload = c.request('GET', 'entries', actor, params={'limit': 500})
        assert r.status_code == 200, 'entries unavailable'
        c.state[key] = {e['title']: e for e in payload['entries']}
    return action


def eid(title, key='e'):
    return Ref(key, title, 'id')


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts', 'bob')
    s.fixture('web', 'publish', fx.publish_all([
        ('http://entries.test/alpha.xml', ALPHA, fx.RSS_TYPE), ('http://entries.test/beta.xml', BETA, fx.RSS_TYPE),
        ('http://entries.test/gamma.xml', GAMMA, fx.RSS_TYPE),
        ('http://entries.test/hidden.xml', HIDDEN, fx.RSS_TYPE),
        ('http://entries.test/quiet.xml', QUIET, fx.RSS_TYPE)]))
    s.setup('library', 'daily', 'POST', 'categories', body={'title': 'Daily'}, save='daily')
    s.setup('library', 'weekly', 'POST', 'categories', body={'title': 'Weekly'}, save='weekly')
    s.setup('library', 'quiet', 'POST', 'categories', body={'title': 'Quiet', 'hide_globally': True}, save='quiet')
    fx.subscribe(s, 'library', 'alpha', 'http://entries.test/alpha.xml', 'alpha', category='daily')
    fx.subscribe(s, 'library', 'hidden', 'http://entries.test/hidden.xml', 'hidden', category='daily',
                 hide_globally=True)
    fx.subscribe(s, 'library', 'beta', 'http://entries.test/beta.xml', 'beta', category='weekly')
    fx.subscribe(s, 'library', 'gamma', 'http://entries.test/gamma.xml', 'gamma', category='weekly')
    fx.subscribe(s, 'library', 'quiet-feed', 'http://entries.test/quiet.xml', 'quiet-feed', category='quiet')
    fx.subscribe(s, 'library', 'bob-beta', 'http://entries.test/beta.xml', 'bob-beta', actor='bob')
    s.fixture('library', 'entries', remember_entries('alice', 'e'))
    s.fixture('library', 'bob-entries', remember_entries('bob', 'bob-e'))
    L = ['fx:accounts', 'fx:web', 'fx:library']

    # Listing, ordering and paging.
    default = s.api('entries', 'list', 'default', 'GET', 'entries', needs=L, view=TITLES,
                    description='Without parameters every entry is listed in the default order.')
    s.api('entries', 'list', 'published-desc', 'GET', 'entries', needs=L, view=TITLES,
          params={'order': 'published_at', 'direction': 'desc'}, description='Entries newest first.')
    s.api('entries', 'list', 'title-asc', 'GET', 'entries', needs=L, view=TITLES,
          params={'order': 'title', 'direction': 'asc'}, description='Entries ordered by title.')
    s.api('entries', 'list', 'title-desc', 'GET', 'entries', needs=L, view=TITLES,
          params={'order': 'title', 'direction': 'desc'}, description='Entries ordered by title, descending.')
    s.api('entries', 'list', 'author', 'GET', 'entries', needs=L, view=grouped('author'),
          params={'order': 'author', 'direction': 'asc'}, description='Entries grouped in author order.')
    s.api('entries', 'list', 'category-title', 'GET', 'entries', needs=L, view=grouped('feed.category.title'),
          params={'order': 'category_title', 'direction': 'desc'}, description='Entries in category title order.')
    s.api('entries', 'list', 'category-id', 'GET', 'entries', needs=L, view=by_category_id,
          params={'order': 'category_id', 'direction': 'asc'},
          description='Entries in the order of their categories\' ids (the categories as they were created).')
    s.add('entries', 'list', 'changed-at', changed_order, needs=L,
          description='Entries ordered by their last change, most recent first.')
    s.api('entries', 'list', 'id', 'GET', 'entries', needs=L, view=TITLES, params={'order': 'id', 'direction': 'asc'},
          description='Entries in the order they were stored.')
    s.api('entries', 'list', 'limit', 'GET', 'entries', needs=L, view=TITLES,
          params={'order': 'published_at', 'direction': 'asc', 'limit': 3},
          description='A limit returns the first entries and the total of all.')
    s.api('entries', 'list', 'offset', 'GET', 'entries', needs=L, view=TITLES,
          params={'order': 'published_at', 'direction': 'asc', 'limit': 3, 'offset': 4},
          description='An offset skips entries.')
    s.api('entries', 'list', 'offset-beyond', 'GET', 'entries', needs=L, view=TITLES,
          params={'offset': 50}, requires=[default], description='An offset beyond the last entry returns none.')

    # Filters.
    s.api('entries', 'filter', 'feed', 'GET', 'entries', needs=L, view=TITLES,
          params={'feed_id': Ref('beta', 'feed_id')}, description='Only the entries of one feed.')
    s.api('entries', 'filter', 'category', 'GET', 'entries', needs=L, view=TITLES,
          params={'category_id': Ref('weekly', 'id')}, description='Only the entries of one category.')
    s.api('entries', 'filter', 'after', 'GET', 'entries', needs=L, view=TITLES,
          params={'after': unix('2025-01-04T00:00:00')}, description='Entries published after a time.')
    s.api('entries', 'filter', 'before', 'GET', 'entries', needs=L, view=TITLES,
          params={'before': unix('2025-01-04T00:00:00')}, description='Entries published before a time.')
    s.api('entries', 'filter', 'published-window', 'GET', 'entries', needs=L, view=TITLES,
          params={'published_after': unix('2025-01-02T00:00:00'), 'published_before': unix('2025-01-06T00:00:00')},
          description='Entries published inside a window.')
    s.api('entries', 'filter', 'changed-recently', 'GET', 'entries', needs=L, view=TITLES,
          params={'changed_after': unix('2026-01-01T00:00:00'), 'order': 'published_at'},
          description='Entries changed after a time before the subscription (all of them).')
    s.api('entries', 'filter', 'changed-long-ago', 'GET', 'entries', needs=L, view=TITLES,
          params={'changed_before': unix('2025-06-01T00:00:00')}, requires=[default],
          description='No entry was changed before the subscription.')
    s.api('entries', 'filter', 'tag', 'GET', 'entries', needs=L, view=TITLES, params={'tags': 'economy'},
          description='Entries carrying one tag.')
    s.api('entries', 'filter', 'two-tags', 'GET', 'entries', needs=L, view=TITLES, params={'tags': ['weather', 'world']},
          description='Entries filtered by two tags at once.')
    s.api('entries', 'filter', 'globally-visible', 'GET', 'entries', needs=L, view=TITLES,
          params={'globally_visible': True}, description='Hidden feeds and hidden categories are left out of the '
                                                         'globally visible entries.')
    s.api('entries', 'filter', 'after-entry', 'GET', 'entries', needs=L, view=TITLES,
          params={'after_entry_id': eid('Alpha storm'), 'order': 'id'},
          description='Entries stored after a given entry.')
    s.api('entries', 'filter', 'before-entry', 'GET', 'entries', needs=L, view=TITLES,
          params={'before_entry_id': eid('Alpha storm'), 'order': 'id'},
          description='Entries stored before a given entry.')
    s.api('entries', 'filter', 'search', 'GET', 'entries', needs=L, view=TITLES, params={'search': 'interview'},
          description='A full-text search among the entries.')
    for step, params in [('status', {'status': 'archived'}), ('order', {'order': 'popularity'}),
                         ('direction', {'direction': 'sideways'}), ('feed', {'feed_id': 987654}),
                         ('category', {'category_id': 987654})]:
        s.api('entries', 'filter-invalid', step, 'GET', 'entries', needs=L, params=params, requires=[default],
              description=f'An invalid {step} parameter is refused.')
    s.api('entries', 'list', 'negative-limit', 'GET', 'entries', needs=L, params={'limit': -2, 'order': 'title'},
          view=TITLES, requires=[default], description='How a negative limit is treated.')
    s.api('entries', 'list', 'negative-offset', 'GET', 'entries', needs=L,
          params={'offset': -1, 'limit': 2, 'order': 'title'}, view=TITLES, requires=[default],
          description='How a negative offset is treated.')
    s.api('entries', 'filter-invalid', 'foreign-feed', 'GET', 'entries', actor='bob', needs=L,
          params={'feed_id': Ref('alpha', 'feed_id')}, requires=[default],
          description='Another account\'s feed is not a valid filter.')

    # Single entries.
    shape = s.api('entries', 'read', 'object', 'GET', pathref('entries/{id}', id=eid('Alpha storm')), needs=L,
                  view=entry_with_feed, description='One entry with its feed, category, tags and enclosures.')
    s.api('entries', 'read', 'enclosures', 'GET', pathref('entries/{id}', id=eid('Gamma episode one')), needs=L,
          view=pick('title', 'enclosures'), description='An entry with an audio enclosure.')
    s.api('entries', 'read', 'missing', 'GET', 'entries/987654', requires=[shape],
          description='An unknown entry is not found.')
    s.api('entries', 'read', 'other-account', 'GET', pathref('entries/{id}', id=eid('Beta review', 'bob-e')),
          needs=L, requires=[shape], description='Another account\'s entry is not found.')

    # Entry ids.
    s.api('entries', 'ids', 'all', 'GET', 'entries/ids', needs=L, view=pick('total', 'entry_ids'),
          description='The ids of every entry, newest stored first.')
    ids = s.api('entries', 'ids', 'limit', 'GET', 'entries/ids', needs=L, params={'limit': 2},
                view=pick('total', 'entry_ids'), description='A limited list of entry ids.')
    s.api('entries', 'ids', 'invalid-status', 'GET', 'entries/ids', needs=L, params={'status': 'removed'},
          requires=[ids], description='Only read and unread are valid statuses for the ids.')
    s.api('entries', 'ids', 'invalid-starred', 'GET', 'entries/ids', needs=L, params={'starred': 'maybe'},
          requires=[ids], description='Only true and false are valid for starred.')

    # Read state.
    marked = s.api('state', 'bulk', 'read', 'PUT', 'entries', needs=L,
                   body={'entry_ids': [eid('Alpha morning'), eid('Beta review')], 'status': 'read'},
                   description='Marking several entries as read at once.')
    read_list = s.api('state', 'list', 'read', 'GET', 'entries', needs=L + [marked], view=TITLES,
                      params={'status': 'read'}, description='The read entries.')
    unread_list = s.api('state', 'list', 'unread', 'GET', 'entries', needs=L + [marked], view=TITLES,
                        params={'status': 'unread', 'order': 'published_at', 'direction': 'desc'},
                        description='The unread entries.')
    s.api('state', 'list', 'both', 'GET', 'entries', needs=L + [marked], view=grouped('status'),
          params={'status': ['read', 'unread'], 'order': 'status'}, description='Read and unread entries by status.')
    unread_again = s.api('state', 'bulk', 'unread', 'PUT', 'entries', needs=L,
                         body={'entry_ids': [eid('Alpha morning')], 'status': 'unread'},
                         description='Marking an entry as unread again.')
    after_unread = s.api('state', 'one', 'after-unread', 'GET', pathref('entries/{id}', id=eid('Alpha morning')),
                         needs=L + [unread_again], requires=[marked], view=pick('status'),
                         description='The entry is unread again.')
    s.api('state', 'bulk', 'invalid-status', 'PUT', 'entries', needs=L, requires=[marked],
          body={'entry_ids': [eid('Alpha budget')], 'status': 'archived'},
          description='An invalid status is refused.')
    s.api('state', 'bulk', 'empty-ids', 'PUT', 'entries', needs=L, requires=[marked],
          body={'entry_ids': [], 'status': 'read'}, description='An empty list of entries is refused.')
    s.api('state', 'bulk', 'nothing', 'PUT', 'entries', needs=L, requires=[marked],
          body={'entry_ids': [eid('Alpha budget')]}, description='A change without status or starred is refused.')
    foreign_mark = s.api('state', 'bulk', 'foreign', 'PUT', 'entries', needs=L,
                         body={'entry_ids': [eid('Beta outlook', 'bob-e')], 'status': 'read'},
                         description='Marking another account\'s entry is accepted but changes nothing for that '
                                     'account.')
    foreign_unchanged = s.api('state', 'one', 'foreign-unchanged', 'GET',
                              pathref('entries/{id}', id=eid('Beta outlook', 'bob-e')), actor='bob',
                              needs=L + [foreign_mark], requires=[marked], view=pick('status'),
                              description='The other account\'s entry is still unread.')

    # Starred state.
    starred = s.api('state', 'star', 'bulk', 'PUT', 'entries', needs=L,
                    body={'entry_ids': [eid('Alpha budget')], 'starred': True},
                    description='Starring entries in bulk.')
    toggled = s.api('state', 'star', 'toggle', 'PUT', pathref('entries/{id}/bookmark', id=eid('Alpha storm')), needs=L,
                    description='Toggling the star of one entry.')
    alias = s.api('state', 'star', 'alias', 'PUT', pathref('entries/{id}/star', id=eid('Beta interview')), needs=L,
                  description='The star route toggles the star too.')
    starred_list = s.api('state', 'list', 'starred', 'GET', 'entries', needs=L + [starred, toggled, alias],
                         view=TITLES, params={'starred': True, 'order': 'title'}, description='The starred entries.')
    toggled_again = s.api('state', 'star', 'toggle-again', 'PUT', pathref('entries/{id}/bookmark', id=eid('Alpha storm')),
                          needs=L, description='Toggling the star again.')
    unstarred = s.api('state', 'one', 'unstarred', 'GET', pathref('entries/{id}', id=eid('Alpha storm')),
                      needs=L + [toggled_again], requires=[toggled], view=pick('starred'),
                      description='The entry is no longer starred.')
    s.api('state', 'list', 'not-starred', 'GET', 'entries', needs=L, requires=[starred], view=TITLES,
          params={'starred': False, 'order': 'title'}, description='The entries that are not starred.')
    s.api('state', 'ids', 'starred', 'GET', 'entries/ids', needs=L, requires=[starred], params={'starred': 'true'},
          view=pick('total', 'entry_ids'), description='The ids of the starred entries.')
    s.api('state', 'star', 'foreign', 'PUT', pathref('entries/{id}/bookmark', id=eid('Beta review', 'bob-e')),
          needs=L, requires=[toggled], description='Toggling the star of another account\'s entry.')

    # Editing.
    edited = s.api('edit', 'entry', 'title', 'PUT', pathref('entries/{id}', id=eid('Alpha harvest')), needs=L,
                   body={'title': 'Alpha harvest (corrected)'}, view=pick('title', 'content'),
                   description='Editing the title of an entry.')
    s.api('edit', 'entry', 'content', 'PUT', pathref('entries/{id}', id=eid('Alpha harvest')), needs=L,
          body={'content': '<p>New <b>body</b><script>alert(1)</script> <a href="/relative">link</a></p>'},
          view=pick('title', 'content'), description='Edited content is sanitized like feed content.')
    s.api('edit', 'entry', 'empty-title', 'PUT', pathref('entries/{id}', id=eid('Alpha harvest')), needs=L,
          body={'title': ''}, requires=[edited], description='An entry title cannot be emptied.')
    s.api('edit', 'entry', 'empty-content', 'PUT', pathref('entries/{id}', id=eid('Alpha harvest')), needs=L,
          body={'content': ''}, requires=[edited], description='Entry content cannot be emptied.')
    s.api('edit', 'entry', 'foreign', 'PUT', pathref('entries/{id}', id=eid('Beta review', 'bob-e')), needs=L,
          body={'title': 'Stolen'}, requires=[edited], description='Another account\'s entry cannot be edited.')
    s.api('edit', 'entry', 'read-back', 'GET', pathref('entries/{id}', id=eid('Alpha harvest')), needs=L,
          requires=[edited], view=pick('title', 'content'), description='The edited entry as stored.')

    # Enclosures and media progress.
    enclosure = Ref('e', 'Gamma episode two', 'enclosures', 0, 'id')
    progressed = s.api('media', 'enclosure', 'progress', 'PUT', pathref('enclosures/{id}', id=enclosure), needs=L,
                       body={'media_progression': 42}, description='Saving the playback position of an enclosure.')
    progress_read = s.api('media', 'enclosure', 'read', 'GET', pathref('enclosures/{id}', id=enclosure),
                          needs=L + [progressed], description='An enclosure with its saved playback position.')
    s.api('media', 'enclosure', 'negative', 'PUT', pathref('enclosures/{id}', id=enclosure), needs=L,
          body={'media_progression': -5}, requires=[progressed], description='A negative position is refused.')
    s.api('media', 'enclosure', 'foreign', 'GET', pathref('enclosures/{id}', id=enclosure), actor='bob', needs=L,
          requires=[progressed], description='Another account cannot read the enclosure.')
    s.api('media', 'enclosure', 'missing', 'GET', 'enclosures/987654', requires=[progressed],
          description='An unknown enclosure is not found.')

    # Importing.
    imported = s.api('import', 'entry', 'full', 'POST', pathref('feeds/{id}/entries/import', id=Ref('alpha', 'feed_id')),
                     needs=L, save='imported',
                     body={'url': 'http://entries.test/alpha/imported', 'title': 'Imported story',
                           'content': '<p>Imported <em>content</em><script>x()</script></p>', 'author': 'Importer',
                           'comments_url': 'http://entries.test/alpha/imported#comments',
                           'published_at': unix('2025-01-05T06:00:00'), 'status': 'unread', 'starred': True,
                           'tags': ['imported', 'manual']}, view=pick('id'), hint='entry',
                     description='Importing an entry into a feed creates it.')
    s.api('import', 'entry', 'read-back', 'GET', pathref('entries/{id}', id=Ref('imported', 'id')), needs=L,
          requires=[imported], view=pick('title', 'url', 'comments_url', 'author', 'content', 'published_at', 'status',
                                         'starred', 'tags', 'feed.title'),
          description='The imported entry with every supplied field.')
    s.api('import', 'entry', 'again', 'POST', pathref('feeds/{id}/entries/import', id=Ref('alpha', 'feed_id')),
          needs=L, requires=[imported], body={'url': 'http://entries.test/alpha/imported', 'title': 'Imported twice'},
          view=pick('id'), hint='entry', description='Importing the same URL again returns the existing entry.')
    minimal = s.api('import', 'entry', 'minimal', 'POST', pathref('feeds/{id}/entries/import', id=Ref('alpha', 'feed_id')),
                    needs=L, save='minimal', body={'url': 'http://entries.test/alpha/minimal',
                                                   'published_at': unix('2025-01-05T07:00:00')},
                    view=pick('id'), hint='entry', description='Importing with only a URL.')
    s.api('import', 'entry', 'minimal-read-back', 'GET', pathref('entries/{id}', id=Ref('minimal', 'id')), needs=L,
          requires=[minimal], view=pick('title', 'status', 'starred', 'content', 'tags'),
          description='The defaults of an entry imported with only a URL.')
    s.api('import', 'entry', 'external-id', 'POST', pathref('feeds/{id}/entries/import', id=Ref('alpha', 'feed_id')),
          needs=L, save='external', body={'url': 'http://entries.test/alpha/external-a', 'external_id': 'ext-77',
                                          'title': 'External one', 'published_at': unix('2025-01-05T08:00:00')},
          view=pick('id'), hint='entry', description='Importing an entry identified by an external id.')
    s.api('import', 'entry', 'external-id-again', 'POST',
          pathref('feeds/{id}/entries/import', id=Ref('alpha', 'feed_id')), needs=L, requires=[imported],
          body={'url': 'http://entries.test/alpha/external-b', 'external_id': 'ext-77', 'title': 'External two'},
          view=pick('id'), hint='entry', description='The external id, not the URL, identifies the imported entry.')
    s.api('import', 'entry', 'no-url', 'POST', pathref('feeds/{id}/entries/import', id=Ref('alpha', 'feed_id')),
          needs=L, requires=[imported], body={'title': 'No address'}, description='An imported entry needs a URL.')
    s.api('import', 'entry', 'bad-status', 'POST', pathref('feeds/{id}/entries/import', id=Ref('alpha', 'feed_id')),
          needs=L, requires=[imported], body={'url': 'http://entries.test/alpha/bad', 'status': 'removed'},
          description='An imported entry needs a valid status.')
    s.api('import', 'entry', 'foreign-feed', 'POST', pathref('feeds/{id}/entries/import', id=Ref('alpha', 'feed_id')),
          actor='bob', needs=L, requires=[imported], body={'url': 'http://entries.test/alpha/x'},
          description='Importing into another account\'s feed is refused.')

    # Marking everything as read and flushing the history.
    foreign_all = s.api('read-all', 'user', 'foreign', 'PUT', pathref('users/{id}/mark-all-as-read',
                                                                       id=Ref('alice', 'id')),
                        actor='bob', needs=L, description='An account cannot mark another account\'s entries as read.')
    everything = s.api('read-all', 'user', 'own', 'PUT', pathref('users/{id}/mark-all-as-read', id=Ref('alice', 'id')),
                       needs=L, description='Marking every entry of the account as read.')
    none_unread = s.api('read-all', 'user', 'unread-after', 'GET', 'entries', needs=L + [everything],
                        requires=[unread_list], view=TITLES, params={'status': 'unread'},
                        description='No unread entry remains.')
    s.api('read-all', 'user', 'other-account-unchanged', 'GET', 'entries', actor='bob', needs=L, requires=[everything],
          view=TITLES, params={'status': 'unread', 'order': 'title'},
          description='The other account\'s entries are still unread.')
    flushed = s.api('read-all', 'history', 'flush', 'PUT', 'flush-history', needs=L,
                    description='Flushing the history of read entries is accepted.')
    flush_effect = s.add('read-all', 'history', 'after-flush', after_flush, needs=L + [flushed],
                         description='After flushing, read entries other than starred ones leave the lists.')
    s.api('read-all', 'history', 'flush-delete', 'DELETE', 'flush-history', needs=L, requires=[flush_effect],
          description='The history can also be flushed with DELETE.')

    # Bare confirmations count together with the reads that show their effect.
    s.bind(marked, read_list)
    s.bind(unread_again, after_unread)
    s.bind(foreign_mark, foreign_unchanged)
    for change in (starred, toggled, alias):
        s.bind(change, starred_list)
    s.bind(toggled_again, unstarred)
    s.bind(progressed, progress_read)
    s.bind(everything, none_unread)
    s.bind(foreign_all, everything)
    s.bind(flushed, flush_effect)


def entry_with_feed(payload):
    """An entry with the fields of its embedded feed that belong to the entry (the feed's own settings and
    schedule are the feed endpoints' business)."""
    assert isinstance(payload, dict) and isinstance(payload.get('feed'), dict), 'expected an entry with its feed'
    feed = payload['feed']
    out = {k: v for k, v in payload.items() if k != 'feed'}
    out['feed'] = {k: feed.get(k) for k in ('id', 'user_id', 'title', 'feed_url', 'site_url')}
    category = feed.get('category') or {}
    out['feed']['category'] = {k: category.get(k) for k in ('id', 'user_id', 'title')}
    return out


def by_category_id(payload):
    """Groups of entries per category, in the order of the categories (named by title); members as multisets."""
    assert isinstance(payload, dict) and isinstance(payload.get('entries'), list), 'expected an entries collection'
    groups = []
    for entry in payload['entries']:
        category = entry['feed']['category']
        if groups and groups[-1][0] == category['id']:
            groups[-1][2].append(entry['title'])
        else:
            groups.append((category['id'], category['title'], [entry['title']]))
    return {'total': payload.get('total'),
            'groups': [{'category': title, 'members': unordered(sorted(names))} for _, title, names in groups]}


def changed_order(c):
    """Entries ordered by their last change: two entries changed one after the other come first (their status is
    set and reset, so it is unchanged); the others, changed together when they were stored, form one group."""
    first, second = (c.state['e'][t]['id'] for t in ('Beta review', 'Alpha budget'))
    for entry_id in (first, second):
        for status in ('read', 'unread'):
            r, _ = c.request('PUT', 'entries', body={'entry_ids': [entry_id], 'status': status})
            assert r.status_code == 204, 'status change failed'
    r, p = c.request('GET', 'entries', params={'order': 'changed_at', 'direction': 'desc', 'limit': 100})
    if r.status_code != 200:
        return c.observe(r, p)
    titles = [e['title'] for e in p['entries']]
    return {'status': r.status_code, 'latest': titles[:2], 'others': unordered(sorted(titles[2:]))}


def after_flush(c):
    """The flush runs in the background: read the read entries until they stop changing."""
    def read():
        r, p = c.request('GET', 'entries', params={'status': 'read', 'order': 'title'})
        return r.status_code, (sorted(e['title'] for e in p['entries']) if r.status_code == 200 else p)
    status, titles = c.settle(read, quiet=2.0, limit=20.0)
    return {'status': status, 'read_titles': titles}
