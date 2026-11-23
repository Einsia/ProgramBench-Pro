"""Reviewed user goals, acceptance conditions, public setup and program checks of the GUI episodes.

Reference recipes (reference/recipes.py) implement these specifications; goals are authored here and are never
produced by translating a recorded click trace. Setup items are unscored public preparation (local web
resources and REST API requests, any success status) that every checkpoint of the episode needs. A point that
only verifies a refusal, an unchanged state or an unavailable view names, in `requires`, a positive point of the
same episode that proves the feature exists. Checks read the public product state through the REST API.
"""
from fixtures import ATOM_TYPE, HTML_TYPE, RSS_TYPE, atom, b64, entry, html_text, item, page, png, rss
from harness import CREDS

BLUE_PNG = b64(png(120, 80, (30, 90, 220)))

FEED_ROUTES = 'Different visible labels, page layouts, menus, inline or dialog editors and ordinary navigation ' \
              'routes are valid.'


# -- setup items -------------------------------------------------------------------------------------------------
def web(name, url, body, content_type=RSS_TYPE, auth=None, status=200):
    spec = {'url': url, 'body': body, 'content_type': content_type, 'status': status}
    if auth:
        spec['auth'] = list(auth)
    return {'id': name, 'web': spec}


def api(name, method, path, body=None, actor='alice', save=None):
    item = {'id': name, 'method': method, 'path': path, 'actor': actor}
    if body is not None:
        item['body'] = body
    if save:
        item['save'] = save
    return item


def categories(actor='alice'):
    """The account's categories (the first one is its default category), saved as cats-<actor>."""
    return api('categories-' + actor, 'GET', 'categories', actor=actor, save='cats-' + actor)


def subscribe(name, url, category='{{cats-alice.0.id}}', actor='alice', **options):
    return api(name, 'POST', 'feeds', {'feed_url': url, 'category_id': category, **options}, actor, save=name)


# -- program checks ------------------------------------------------------------------------------------------------
def read(path, fields=(), expected=None, actor='alice', status=200, where=None, collection=False, items=None,
         contains=None, refused=None, save=None, description=None, at_least=None):
    check = {'request': {'method': 'GET', 'path': path, 'actor': actor, 'status': status}, 'fields': list(fields),
             'expected': expected, 'where': where, 'collection': collection}
    for key, value in (('items', items), ('contains', contains), ('refused', refused), ('save', save),
                       ('description', description), ('at_least', at_least)):
        if value is not None:
            check[key] = value
    return check


def entries(expected, fields=('title', 'status'), actor='alice', query=''):
    """Every entry of the account (any status) projected to fields, compared as a multiset."""
    what = ('The account\'s entries are exactly the listed ones.' if tuple(fields) == ('title',) else
            'The account\'s entries have the requested ' + ' and '.join(fields) + '.')
    return read('entries?limit=200&order=id' + query, fields, expected, actor=actor, items='entries',
                collection=True, description=what)


def feeds(expected, fields=('title', 'feed_url', 'category.title'), actor='alice'):
    return read('feeds', fields, expected, actor=actor, collection=True,
                description='The account\'s subscriptions are exactly the requested ones.')


def feed(url, fields, expected, actor='alice'):
    return read('feeds', fields, expected, actor=actor, where={'feed_url': url},
                description='The subscription ' + url + ' has the requested settings.')


def me(fields, expected, actor='alice'):
    return read('me', fields, expected, actor=actor, description='The saved account settings have the requested '
                                                                 'values.')


# -- episodes ---------------------------------------------------------------------------------------------------------
def step(key, goal, acceptance, recipe, checks=(), visible=(), depends=(), requires=(), lifecycle=None):
    value = {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': recipe, 'checks': list(checks),
             'visible': list(visible), 'depends_on': list(depends), 'requires': list(requires)}
    if lifecycle:
        value['lifecycle'] = lifecycle
    return value


def episode(key, feature, setup, steps, actor='alice', files=None, tokens_per_step=180_000):
    ids = [item['id'] for item in setup]
    for cp in steps:
        cp['assertions'] = [{'id': key + '/' + cp['id'] + '/visible', 'channel': 'frontend', 'method': 'agent',
                             'requirement': cp['acceptance']}]
        for i, check in enumerate(cp['checks']):
            cp['assertions'].append({'id': key + '/' + cp['id'] + f'/state-{i + 1}', 'channel': 'backend',
                                     'method': 'program', 'check': check, 'requirement': check.get(
                                         'description', 'The public product state matches the checkpoint.')})
        bound = [key + '/' + x for x in cp.pop('requires')]
        if bound:
            cp['assertions'][0]['requires'] = bound
        cp['depends_on'] = ['setup:' + i for i in ids] + cp['depends_on']
    accounts = {name: password for name, password in CREDS.items() if name == actor}
    inputs = {'account': actor, 'credentials': accounts}
    if files:
        inputs['files'] = sorted(files)
    session = ('Sign in with the supplied account before the first goal; this is unscored preparation.' if actor
               else 'Start unauthenticated. Only sign in when a goal explicitly asks you to.')
    value = {'id': key, 'feature': feature, 'execution': 'gui',
             'initial_state': 'A fresh application with the three baseline accounts and an empty local web (its '
                              'example site only); the listed setup is then applied through public interfaces.',
             'setup': setup, 'inputs': inputs, 'actor': actor, 'session': session,
             'allowed_equivalents': [FEED_ROUTES, 'Product page URLs may be entered in the browser.'],
             'forbidden_bypasses': ['Do not use APIs, developer tools, page source or hidden application state to '
                                    'perform the goals.', 'Do not recreate a missing product command by other means.'],
             'budget': {'calls': min(160, 45 + 25 * len(steps)), 'seconds': min(1800, 480 + 180 * len(steps)),
                        'tokens': 350_000 + tokens_per_step * len(steps) if tokens_per_step != 180_000 else
                        min(1_500_000, 350_000 + 180_000 * len(steps))},
             'checkpoints': steps}
    if files:
        value['files'] = files
    return value


def news(host, title, names, start=1, extra=lambda n: ''):
    """An RSS feed of host with one item per name, dated on consecutive days (oldest first in document order)."""
    return rss(title, f'http://{host}/', [item(name, f'http://{host}/{i}', f'{host}-{i}',
                                               f'Mon, {i + start:02d} Sep 2025 09:00:00 GMT',
                                               html_text(f'<p>{name} body text.</p>'), extra(i))
                                          for i, name in enumerate(names)])


def site(title, feeds_):
    links = ''.join(f'<link rel="alternate" type="{kind}" title="{name}" href="{href}">\n' for name, kind, href in feeds_)
    return page(title, '<p>Welcome to the site.</p>', head=links)


def opml_document(groups):
    body = ''
    for group, outlines in groups:
        inner = ''.join(f'<outline type="rss" text="{t}" title="{t}" xmlUrl="{u}" htmlUrl="{h}"/>' for t, u, h in outlines)
        body += f'<outline text="{group}" title="{group}">{inner}</outline>' if group else inner
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<opml version="2.0"><head><title>Subscriptions</title></head>'
            f'<body>{body}</body></opml>\n')


def sign_in_steps(user, password):
    return [{'op': 'goto', 'path': '/'}, {'op': 'fill', 'field': 'username', 'value': user},
            {'op': 'fill', 'field': 'password', 'value': password}, {'op': 'click', 'names': ['Login']}]


def build():
    episodes = []

    def add(*a, **kw):
        episodes.append(episode(*a, **kw))

    # -- authentication ---------------------------------------------------------------------------------------
    add('login-valid', 'authentication', [], [
        step('signed-in', f'Sign in with the username "bob" and the password "{CREDS["bob"]}".',
             'Bob is signed in: an authenticated page of his reader (for example the unread entries) is shown instead '
             'of the sign-in form.',
             sign_in_steps('bob', CREDS['bob']) + [{'op': 'wait-url', 'path': '/unread'}], visible=['Unread'])],
        actor=None)
    add('login-invalid', 'authentication', [], [
        step('refused', 'Try to sign in with the username "bob" and the password "Wrong-Password-2026!".',
             'The sign-in is refused with a visible error message about the credentials and the sign-in form is '
             'still offered; no page of the reader is shown.',
             sign_in_steps('bob', 'Wrong-Password-2026!'),
             [read('me', ['username'], {'username': 'bob'}, actor='bob',
                   refused={'path': 'me', 'actor': ['bob', 'Wrong-Password-2026!'], 'status': 401},
                   description='The account signs in with its real password through the public interface and the '
                               'wrong password is refused.')],
             visible=['Invalid username or password'], requires=['refused/state-1'])], actor=None)
    add('logout', 'authentication', [], [
        step('reader', 'Open the list of your feeds.', 'The feeds page of the signed-in reader is shown.',
             [{'op': 'goto', 'path': '/feeds'}], visible=['Feeds']),
        step('signed-out', 'Log out.', 'The session ends and the sign-in form is shown.',
             [{'op': 'sign-out'}], visible=['Login'], depends=['reader']),
        step('protected', 'Open the page /unread.',
             'Without a session the unread entries are not shown; the sign-in form is offered instead.',
             [{'op': 'goto', 'path': '/unread'}], visible=['Login'], depends=['signed-out'],
             requires=['signed-out/visible'])])

    # -- subscriptions ----------------------------------------------------------------------------------------
    gazette = news('gazette.test', 'Morning Gazette', ['Gazette 1', 'Gazette 2', 'Gazette 3'])
    add('subscribe-feed', 'subscriptions', [web('feed', 'http://gazette.test/feed.xml', gazette)], [
        step('subscribed', 'Subscribe to the feed http://gazette.test/feed.xml.',
             'The subscription "Morning Gazette" is created and shown with its entries.',
             [{'op': 'goto', 'path': '/subscribe'}, {'op': 'fill', 'field': 'url', 'value': 'http://gazette.test/feed.xml'},
              {'op': 'click', 'names': ['Find a feed']}, {'op': 'require', 'texts': ['Gazette 1']}],
             [feeds([{'title': 'Morning Gazette', 'feed_url': 'http://gazette.test/feed.xml', 'category.title': 'All'}]),
              entries([{'title': f'Gazette {n}'} for n in (1, 2, 3)], fields=('title',))],
             visible=['Morning Gazette']),
        step('listed', 'Open the list of all your feeds.',
             'The list of feeds contains Morning Gazette with its web site.',
             [{'op': 'goto', 'path': '/feeds'}], visible=['Morning Gazette'], depends=['subscribed'])])
    site_feeds = [('Corner RSS', 'application/rss+xml', '/rss.xml'), ('Corner Atom', 'application/atom+xml', '/atom.xml')]
    corner_atom = atom('Corner Atom feed', 'http://corner.test/', [
        entry('Corner Atom entry', 'http://corner.test/a1', 'urn:corner:a1', '2025-09-03T09:00:00Z',
              content='<p>Atom body.</p>')], feed_id='urn:corner')
    add('subscribe-discovery', 'subscriptions', [
        web('site', 'http://corner.test/', site('Corner site', site_feeds), HTML_TYPE),
        web('rss', 'http://corner.test/rss.xml', news('corner.test', 'Corner RSS feed', ['Corner RSS entry'])),
        web('atom', 'http://corner.test/atom.xml', corner_atom, ATOM_TYPE)], [
        step('chosen', 'Subscribe to the website http://corner.test/; it offers several feeds — subscribe to its Atom '
                       'feed ("Corner Atom").',
             'The Atom feed of the site (Corner Atom feed) is subscribed; the RSS feed is not.',
             [{'op': 'goto', 'path': '/subscribe'}, {'op': 'fill', 'field': 'url', 'value': 'http://corner.test/'},
              {'op': 'click', 'names': ['Find a feed']}, {'op': 'choose', 'label': 'Corner Atom'},
              {'op': 'click', 'names': ['Subscribe']}, {'op': 'require', 'texts': ['Corner Atom entry']}],
             [feeds([{'title': 'Corner Atom feed', 'feed_url': 'http://corner.test/atom.xml', 'category.title': 'All'}])],
             visible=['Corner Atom feed'])])
    tech = news('techdesk.test', 'Tech Desk', ['Tech one', 'Tech two'])
    add('subscribe-options', 'subscriptions', [
        web('feed', 'http://techdesk.test/feed.xml', tech), api('category', 'POST', 'categories', {'title': 'Technology'})], [
        step('configured', 'Subscribe to http://techdesk.test/feed.xml in the category "Technology", with the user '
                           'agent "GUI Agent/1.0" and with fetching the original content of entries enabled.',
             'The feed Tech Desk is subscribed in the category Technology; its settings show the user agent GUI '
             'Agent/1.0 and that original content is fetched.',
             [{'op': 'goto', 'path': '/subscribe'}, {'op': 'fill', 'field': 'url', 'value': 'http://techdesk.test/feed.xml'},
              {'op': 'select', 'field': 'category_id', 'value': 'Technology'},
              {'op': 'expand', 'text': 'Advanced Options'}, {'op': 'check', 'field': 'crawler'},
              {'op': 'fill', 'field': 'user_agent', 'value': 'GUI Agent/1.0'}, {'op': 'click', 'names': ['Find a feed']},
              {'op': 'require', 'texts': ['Tech one']},
              {'op': 'open-feed-edit', 'feed_url': 'http://techdesk.test/feed.xml'}],
             [feed('http://techdesk.test/feed.xml', ['title', 'category.title', 'user_agent', 'crawler'],
                   {'title': 'Tech Desk', 'category.title': 'Technology', 'user_agent': 'GUI Agent/1.0', 'crawler': True})],
             visible=['Tech Desk'])])
    add('subscription-errors', 'subscriptions', [web('feed', 'http://gazette.test/feed.xml', gazette)], [
        step('missing', 'Subscribe to http://gazette.test/missing.xml.',
             'No subscription is created and a visible error explains that the feed could not be found or fetched.',
             [{'op': 'goto', 'path': '/subscribe'}, {'op': 'fill', 'field': 'url', 'value': 'http://gazette.test/missing.xml'},
              {'op': 'click', 'names': ['Find a feed']}],
             [feeds([])], visible=['not found'], requires=['valid/state-1']),
        step('valid', 'Subscribe to http://gazette.test/feed.xml.', 'The subscription Morning Gazette is created.',
             [{'op': 'goto', 'path': '/subscribe'}, {'op': 'fill', 'field': 'url', 'value': 'http://gazette.test/feed.xml'},
              {'op': 'click', 'names': ['Find a feed']}, {'op': 'require', 'texts': ['Gazette 1']}],
             [feeds([{'title': 'Morning Gazette', 'feed_url': 'http://gazette.test/feed.xml', 'category.title': 'All'}])],
             visible=['Morning Gazette']),
        step('duplicate', 'Subscribe to http://gazette.test/feed.xml again.',
             'The product refuses a second subscription with a visible message; the feed stays subscribed once.',
             [{'op': 'goto', 'path': '/subscribe'}, {'op': 'fill', 'field': 'url', 'value': 'http://gazette.test/feed.xml'},
              {'op': 'click', 'names': ['Find a feed']}],
             [feeds([{'title': 'Morning Gazette', 'feed_url': 'http://gazette.test/feed.xml', 'category.title': 'All'}])],
             visible=['already exists'], depends=['valid'], requires=['valid/state-1'])])
    private = news('vault.test', 'Members Only', ['Members entry'])
    add('subscribe-credentials', 'subscriptions', [
        web('feed', 'http://vault.test/feed.xml', private, auth=('reader', 'Vault-Pass-2026'))], [
        step('authenticated', 'Subscribe to http://vault.test/feed.xml, which needs the username "reader" and the '
                              'password "Vault-Pass-2026".',
             'The protected feed Members Only is subscribed and its entry "Members entry" is listed.',
             [{'op': 'goto', 'path': '/subscribe'}, {'op': 'fill', 'field': 'url', 'value': 'http://vault.test/feed.xml'},
              {'op': 'expand', 'text': 'Advanced Options'}, {'op': 'fill', 'field': 'feed_username', 'value': 'reader'},
              {'op': 'fill', 'field': 'feed_password', 'value': 'Vault-Pass-2026'},
              {'op': 'click', 'names': ['Find a feed']}, {'op': 'require', 'texts': ['Members entry']}],
             [feed('http://vault.test/feed.xml', ['title', 'username'], {'title': 'Members Only', 'username': 'reader'}),
              entries([{'title': 'Members entry'}], fields=('title',))], visible=['Members Only'])])

    # -- reading ---------------------------------------------------------------------------------------------------
    reading = news('reading.test', 'Reading Room', ['Reading 1', 'Reading 2', 'Reading 3'])
    base = [web('feed', 'http://reading.test/feed.xml', reading), categories(),
            subscribe('subscription', 'http://reading.test/feed.xml')]
    add('read-entry', 'reading', base, [
        step('opened', 'Open the entry "Reading 2" to read it.',
             'The entry Reading 2 is displayed with its content ("Reading 2 body text."), its feed Reading Room and a '
             'link to the original article.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'click', 'names': ['Reading 2']},
              {'op': 'require', 'texts': ['Reading 2 body text.']}],
             [read('entries?limit=50', ['status'], {'status': 'read'}, items='entries', where={'title': 'Reading 2'},
                   description='Reading an entry marks it as read (the default reading behavior).')],
             visible=['Reading 2 body text.', 'Reading Room']),
        step('unread', 'Mark the entry Reading 2 as unread.', 'The entry Reading 2 is shown as unread again.',
             [{'op': 'click', 'names': ['Mark as unread']}, {'op': 'require', 'texts': ['Mark as read']}],
             [read('entries?limit=50', ['status'], {'status': 'unread'}, items='entries', where={'title': 'Reading 2'},
                   description='The entry Reading 2 is unread again.')], depends=['opened']),
        step('starred', 'Star the entry Reading 2.', 'The entry Reading 2 is visibly starred.',
             [{'op': 'click', 'names': ['Star']}, {'op': 'require', 'texts': ['Unstar']}],
             [entries([{'title': 'Reading 1', 'starred': False}, {'title': 'Reading 2', 'starred': True},
                       {'title': 'Reading 3', 'starred': False}], fields=('title', 'starred'))], depends=['opened']),
        step('starred-list', 'Open the list of your starred entries.',
             'The starred list contains Reading 2 and neither Reading 1 nor Reading 3.',
             [{'op': 'goto', 'path': '/starred'}], visible=['Reading 2'], depends=['starred']),
        step('unstarred', 'Remove the star from Reading 2.', 'Reading 2 is no longer starred.',
             [{'op': 'row', 'anchor': 'Reading 2', 'names': ['Unstar']}, {'op': 'sleep', 'seconds': 1}],
             [entries([{'title': 'Reading 1', 'starred': False}, {'title': 'Reading 2', 'starred': False},
                       {'title': 'Reading 3', 'starred': False}], fields=('title', 'starred'))],
             depends=['starred'])])
    listing = news('listing.test', 'List Feed', ['List 1', 'List 2', 'List 3', 'List 4'])
    add('list-actions', 'reading', [web('feed', 'http://listing.test/feed.xml', listing), categories(),
                                     subscribe('subscription', 'http://listing.test/feed.xml')], [
        step('toggle-read', 'In the list of unread entries, mark "List 3" as read without opening it.',
             'List 3 is marked as read; the other entries stay unread.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'row', 'anchor': 'List 3', 'names': ['Mark as read']},
              {'op': 'sleep', 'seconds': 1}],
             [entries([{'title': 'List 1', 'status': 'unread'}, {'title': 'List 2', 'status': 'unread'},
                       {'title': 'List 3', 'status': 'read'}, {'title': 'List 4', 'status': 'unread'}])]),
        step('toggle-star', 'In the list of unread entries, star "List 1" without opening it.',
             'List 1 is shown as starred.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'row', 'anchor': 'List 1', 'names': ['Star']},
              {'op': 'sleep', 'seconds': 1}],
             [entries([{'title': f'List {n}', 'starred': n == 1} for n in range(1, 5)], fields=('title', 'starred'))]),
        step('all-read', 'Mark all unread entries as read.', 'No unread entries remain.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'click', 'names': ['Mark all as read']},
              {'op': 'click', 'names': ['yes']}, {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/unread'}],
             [entries([{'title': f'List {n}', 'status': 'read'} for n in range(1, 5)])]),
        step('history', 'Open the history of read entries.', 'The history lists the four read entries List 1 to List 4.',
             [{'op': 'goto', 'path': '/history'}], visible=['List 1', 'List 4'], depends=['all-read']),
        step('flushed', 'Clear (flush) the history.',
             'The read entries disappear from the history, except the starred List 1 which remains listed.',
             [{'op': 'goto', 'path': '/history'}, {'op': 'click', 'names': ['Flush history']},
              {'op': 'click', 'names': ['yes']}, {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/history'}],
             [read('entries?status=read&limit=50', ['title', 'starred'], [{'title': 'List 1', 'starred': True}],
                   items='entries', collection=True,
                   description='Flushing the history removes the read entries that are not starred.')],
             visible=['List 1'], depends=['all-read'])])
    add('feed-mark-read', 'reading', [
        web('alpha', 'http://alpha.test/feed.xml', news('alpha.test', 'Alpha Feed', ['Alpha one', 'Alpha two'])),
        web('beta', 'http://beta.test/feed.xml', news('beta.test', 'Beta Feed', ['Beta one', 'Beta two'])),
        categories(), subscribe('alpha-feed', 'http://alpha.test/feed.xml'),
        subscribe('beta-feed', 'http://beta.test/feed.xml')], [
        step('feed-read', 'Mark all entries of the feed "Alpha Feed" as read.',
             'The entries of Alpha Feed are read while those of Beta Feed stay unread.',
             [{'op': 'goto', 'path': '/feeds'}, {'op': 'row', 'anchor': 'Alpha Feed', 'names': ['Mark all as read']},
              {'op': 'click', 'names': ['yes']}, {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/feeds'}],
             [entries([{'title': 'Alpha one', 'status': 'read'}, {'title': 'Alpha two', 'status': 'read'},
                       {'title': 'Beta one', 'status': 'unread'}, {'title': 'Beta two', 'status': 'unread'}])]),
        step('all-entries', 'Open all entries of the feed Alpha Feed, including the read ones.',
             'Alpha one and Alpha two are both listed (as read entries).',
             [{'op': 'goto', 'path': '/feed/{{alpha-feed.feed_id}}/entries/all'}],
             visible=['Alpha one', 'Alpha two'], depends=['feed-read'])])
    article = page('Full story', '<article><h1>Full story</h1><p>The complete article text lives on the website.</p>'
                                 '<p>It has a second paragraph.</p></article><footer>Site footer</footer>')
    summary = rss('Summaries', 'http://summary.test/', [
        item('Summary only', 'http://summary.test/story.html', 'summary-1', 'Mon, 01 Sep 2025 09:00:00 GMT',
             'Just a teaser.')])
    add('fetch-original', 'reading', [
        web('feed', 'http://summary.test/feed.xml', summary), web('article', 'http://summary.test/story.html', article,
                                                                   HTML_TYPE),
        categories(), subscribe('subscription', 'http://summary.test/feed.xml')], [
        step('fetched', 'Open the entry "Summary only" and replace its teaser with the original article content '
                        'fetched from the website.',
             'The entry now shows the full article text ("The complete article text lives on the website.") instead '
             'of the teaser.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'click', 'names': ['Summary only']},
              {'op': 'click', 'names': ['Download']}, {'op': 'require', 'texts': ['The complete article text']}],
             [read('entries?limit=50', [], {'content contains \'The complete article text lives on the website.\'': True},
                   items='entries', where={'title': 'Summary only'},
                   contains={'content': 'The complete article text lives on the website.'},
                   description='The entry content was replaced by the original article.')],
             visible=['The complete article text lives on the website.'])])
    shared = news('shared.test', 'Shared Feed', ['Shared story', 'Private story'])
    add('share-entry', 'sharing', [web('feed', 'http://shared.test/feed.xml', shared), categories(),
                                    subscribe('subscription', 'http://shared.test/feed.xml')], [
        step('shared', 'Share the entry "Shared story" publicly.',
             'A public link for Shared story exists; its public page shows the entry title and content.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'click', 'names': ['Shared story']},
              {'op': 'click', 'names': ['Share']}, {'op': 'require', 'texts': ['Shared story body text.']}],
             [read('entries?limit=50', ['share_code'], items='entries', where={'title': 'Shared story'},
                   description='The entry has a public share code.')],
             visible=['Shared story body text.']),
        step('shares', 'Open the list of your shared entries.',
             'The list of shared entries contains Shared story and not Private story.',
             [{'op': 'goto', 'path': '/shares'}], visible=['Shared story'], depends=['shared']),
        step('unshared', 'Stop sharing the entry Shared story.', 'Shared story is no longer shared publicly.',
             [{'op': 'goto', 'path': '/shares'}, {'op': 'row', 'anchor': 'Shared story', 'names': ['Unshare']},
              {'op': 'click', 'names': ['yes']}, {'op': 'sleep', 'seconds': 1}],
             [read('entries?limit=50', ['share_code'], {'share_code': ''}, items='entries',
                   where={'title': 'Shared story'}, description='The entry no longer has a share code.')],
             depends=['shared'], requires=['shared/state-1'])])
    found = rss('Lab Notes', 'http://lab.test/', [
        item('Quantum computing basics', 'http://lab.test/1', 'lab-1', 'Mon, 01 Sep 2025 09:00:00 GMT',
             'Qubits and gates explained.'),
        item('Garden notes', 'http://lab.test/2', 'lab-2', 'Tue, 02 Sep 2025 09:00:00 GMT', 'Tomatoes and basil.'),
        item('A leap forward', 'http://lab.test/3', 'lab-3', 'Wed, 03 Sep 2025 09:00:00 GMT',
             'A quantum leap in battery research.')])
    add('search', 'search', [web('feed', 'http://lab.test/feed.xml', found), categories(),
                             subscribe('subscription', 'http://lab.test/feed.xml'),
                             {'id': 'read', 'mark': {'title': 'A leap forward', 'status': 'read'}}], [
        step('results', 'Search your entries for the word "quantum".',
             'The results list "Quantum computing basics" and "A leap forward" (whose text mentions quantum), read or '
             'not, and not "Garden notes".',
             [{'op': 'goto', 'path': '/search'}, {'op': 'fill', 'field': 'q', 'value': 'quantum'},
              {'op': 'click', 'names': ['Search']}, {'op': 'require', 'texts': ['A leap forward']}],
             visible=['Quantum computing basics', 'A leap forward']),
        step('unread-only', 'Search for "quantum" among unread entries only.',
             'Only "Quantum computing basics" is listed; "A leap forward" is excluded because it is already read.',
             [{'op': 'goto', 'path': '/search'}, {'op': 'fill', 'field': 'q', 'value': 'quantum'},
              {'op': 'check', 'field': 'unread'}, {'op': 'click', 'names': ['Search']},
              {'op': 'require', 'texts': ['Quantum computing basics']}],
             visible=['Quantum computing basics'], depends=['results'])])
    tagged = rss('Science Weekly', 'http://weekly.test/', [
        item('Podcast episode', 'http://weekly.test/1', 'weekly-1', 'Mon, 01 Sep 2025 09:00:00 GMT', 'Listen now.',
             '<category>science</category><enclosure url="http://media.weekly.test/episode.mp3" length="4096" '
             'type="audio/mpeg"/>'),
        item('Lab news', 'http://weekly.test/2', 'weekly-2', 'Tue, 02 Sep 2025 09:00:00 GMT', 'News from the lab.',
             '<category>science</category>'),
        item('Other news', 'http://weekly.test/3', 'weekly-3', 'Wed, 03 Sep 2025 09:00:00 GMT', 'Something else.',
             '<category>culture</category>')])
    add('tags-attachments', 'reading', [web('feed', 'http://weekly.test/feed.xml', tagged), categories(),
                                        subscribe('subscription', 'http://weekly.test/feed.xml')], [
        step('attachment', 'Open the entry "Podcast episode" and look at its attachment.',
             'The entry shows its audio attachment (episode.mp3) with a player or a download link.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'click', 'names': ['Podcast episode']},
              {'op': 'expand', 'text': 'Attachments (1)'}], visible=['Attachments']),
        step('tag', 'Open the list of entries tagged "science".',
             'Podcast episode and Lab news are listed; Other news (tagged culture) is not.',
             [{'op': 'click', 'names': ['science']}, {'op': 'require', 'texts': ['Lab news']}],
             visible=['Podcast episode', 'Lab news'], depends=['attachment'])])
    pictures = rss('Picture Desk', 'http://pictures.test/', [
        item('Blue square', 'http://pictures.test/1', 'pictures-1', 'Mon, 01 Sep 2025 09:00:00 GMT',
             html_text('<p>A picture follows.</p><p><img src="http://pics.test/blue.png" alt="Blue square picture" '
                       'width="120" height="80"></p><p>End of the picture story.</p>'))])
    add('entry-pictures', 'reading', [web('feed', 'http://pictures.test/feed.xml', pictures),
                                      {'id': 'picture', 'web': {'url': 'http://pics.test/blue.png',
                                                                'body_base64': BLUE_PNG, 'content_type': 'image/png'}},
                                      categories(), subscribe('subscription', 'http://pictures.test/feed.xml')], [
        step('shown', 'Open the entry "Blue square" and look at its picture.',
             'The entry shows its picture: a blue rectangle between "A picture follows." and "End of the picture '
             'story.".',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'click', 'names': ['Blue square']},
              {'op': 'require', 'texts': ['End of the picture story.']}, {'op': 'sleep', 'seconds': 1}],
             [{'web': {'fetched': ['http://pics.test/blue.png'], 'at_least': {'http://pics.test/blue.png': 1}},
               'expected': {'http://pics.test/blue.png': True},
               'description': 'The product fetched the picture for the browser (pages load nothing from the local '
                              'web themselves).'}],
             visible=['End of the picture story.'])])
    paged = news('pages.test', 'Paged Feed', [f'Page item {n}' for n in range(1, 6)])
    add('pagination', 'reading', [web('feed', 'http://pages.test/feed.xml', paged), categories(),
                                  subscribe('subscription', 'http://pages.test/feed.xml'),
                                  api('me', 'GET', 'me', save='me'),
                                  api('per-page', 'PUT', 'users/{{me.id}}', {'entries_per_page': 2})], [
        step('second-page', 'Go to the second page of your unread entries (two entries are shown per page, oldest '
                            'first).',
             'The second page lists Page item 3 and Page item 4.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'click', 'names': ['Next']},
              {'op': 'require', 'texts': ['Page item 3']}], visible=['Page item 3', 'Page item 4']),
        step('page-read', 'Mark only the entries of this page as read.',
             'Page item 3 and Page item 4 are marked as read; the other three entries stay in the unread list.',
             [{'op': 'click', 'names': ['Mark this page as read']}, {'op': 'click', 'names': ['yes']},
              {'op': 'sleep', 'seconds': 1}],
             [entries([{'title': f'Page item {n}', 'status': 'read' if n in (3, 4) else 'unread'}
                       for n in range(1, 6)])], depends=['second-page'])])

    # -- feeds -----------------------------------------------------------------------------------------------------
    editable = news('editable.test', 'Editable Feed', ['Editable one'])
    add('edit-feed', 'feed-settings', [web('feed', 'http://editable.test/feed.xml', editable), categories(),
                                       subscribe('subscription', 'http://editable.test/feed.xml'),
                                       api('archive', 'POST', 'categories', {'title': 'Archive'})], [
        step('renamed', 'Rename the feed "Editable Feed" to "Renamed Feed" and move it to the category "Archive".',
             'The feed is now called Renamed Feed and belongs to the category Archive.',
             [{'op': 'goto', 'path': '/feed/{{subscription.feed_id}}/edit'},
              {'op': 'fill', 'field': 'title', 'value': 'Renamed Feed'},
              {'op': 'select', 'field': 'category_id', 'value': 'Archive'}, {'op': 'click', 'names': ['Update']},
              {'op': 'require', 'texts': ['Renamed Feed']}],
             [feed('http://editable.test/feed.xml', ['title', 'category.title'],
                   {'title': 'Renamed Feed', 'category.title': 'Archive'})], visible=['Renamed Feed']),
        step('rules', 'In the settings of the feed Renamed Feed, set the scraper rules to "article", the content '
                      'rewrite rules to "add_dynamic_image" and the regex-based blocking filter to "(?i)sponsored".',
             'The feed settings show the three rules.',
             [{'op': 'goto', 'path': '/feed/{{subscription.feed_id}}/edit'},
              {'op': 'fill', 'field': 'scraper_rules', 'value': 'article'},
              {'op': 'fill', 'field': 'rewrite_rules', 'value': 'add_dynamic_image'},
              {'op': 'fill', 'field': 'blocklist_rules', 'value': '(?i)sponsored'}, {'op': 'click', 'names': ['Update']},
              {'op': 'goto', 'path': '/feed/{{subscription.feed_id}}/edit'}],
             [feed('http://editable.test/feed.xml', ['scraper_rules', 'rewrite_rules', 'blocklist_rules'],
                   {'scraper_rules': 'article', 'rewrite_rules': 'add_dynamic_image', 'blocklist_rules': '(?i)sponsored'})],
             depends=['renamed']),
        step('paused', 'Stop the automatic refreshing of the feed Renamed Feed and hide its entries from the global '
                       'unread list.',
             'The feed settings show that it is not refreshed and that its entries are hidden from the global unread '
             'list.',
             [{'op': 'goto', 'path': '/feed/{{subscription.feed_id}}/edit'}, {'op': 'check', 'field': 'disabled'},
              {'op': 'check', 'field': 'hide_globally'}, {'op': 'click', 'names': ['Update']},
              {'op': 'goto', 'path': '/feed/{{subscription.feed_id}}/edit'}],
             [feed('http://editable.test/feed.xml', ['disabled', 'hide_globally'],
                   {'disabled': True, 'hide_globally': True})], depends=['renamed'])])
    growing = news('growing.test', 'Growing Feed', ['Growing 1', 'Growing 2'])
    grown = news('growing.test', 'Growing Feed', ['Growing 1', 'Growing 2', 'Growing 3'])
    add('refresh-feed', 'feed-settings', [web('feed', 'http://growing.test/feed.xml', growing), categories(),
                                          subscribe('subscription', 'http://growing.test/feed.xml'),
                                          web('feed-update', 'http://growing.test/feed.xml', grown)], [
        step('refreshed', 'Refresh the feed "Growing Feed" now.',
             'The new entry Growing 3 appears among the entries of Growing Feed.',
             [{'op': 'goto', 'path': '/feeds'}, {'op': 'row', 'anchor': 'Growing Feed', 'names': ['Refresh']},
              {'op': 'goto', 'path': '/feed/{{subscription.feed_id}}/entries'}, {'op': 'require', 'texts': ['Growing 3']}],
             [entries([{'title': f'Growing {n}'} for n in (1, 2, 3)], fields=('title',))], visible=['Growing 3'])])
    add('remove-feed', 'feed-settings', [
        web('one', 'http://keeper.test/feed.xml', news('keeper.test', 'Keeper Feed', ['Keeper entry'])),
        web('two', 'http://disposable.test/feed.xml', news('disposable.test', 'Disposable Feed', ['Disposable entry'])),
        categories(), subscribe('keeper', 'http://keeper.test/feed.xml'),
        subscribe('disposable', 'http://disposable.test/feed.xml')], [
        step('removed', 'Unsubscribe from (remove) the feed "Disposable Feed".',
             'Disposable Feed is no longer among the feeds; Keeper Feed remains.',
             [{'op': 'goto', 'path': '/feeds'}, {'op': 'row', 'anchor': 'Disposable Feed', 'names': ['Remove']},
              {'op': 'click', 'names': ['yes']}, {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/feeds'}],
             [feeds([{'title': 'Keeper Feed', 'feed_url': 'http://keeper.test/feed.xml', 'category.title': 'All'}]),
              entries([{'title': 'Keeper entry'}], fields=('title',))], visible=['Keeper Feed'])])
    add('feed-errors', 'feed-settings', [
        web('feed', 'http://fragile.test/feed.xml', news('fragile.test', 'Fragile Feed', ['Fragile entry'])),
        categories(), subscribe('subscription', 'http://fragile.test/feed.xml'),
        web('broken', 'http://fragile.test/feed.xml', 'this is not a feed any more', 'text/plain')], [
        step('failed', 'Refresh the feed "Fragile Feed" now and look at the result.',
             'The refresh fails and the product visibly reports a problem with the feed (an error message about the '
             'unreadable feed).',
             [{'op': 'goto', 'path': '/feeds'}, {'op': 'row', 'anchor': 'Fragile Feed', 'names': ['Refresh']},
              {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/feeds'}],
             [read('feeds', [], {'parsing_error_count >= 1': True}, where={'feed_url': 'http://fragile.test/feed.xml'},
                   at_least={'parsing_error_count': 1}, description='The feed has recorded a refresh error.')],
             visible=['Unable to detect feed format'])])

    # -- categories --------------------------------------------------------------------------------------------------
    add('categories', 'categories', [], [
        step('created', 'Create the category "Science".', 'The category Science is listed among the categories.',
             [{'op': 'goto', 'path': '/category/create'}, {'op': 'fill', 'field': 'title', 'value': 'Science'},
              {'op': 'click', 'names': ['Save']}, {'op': 'goto', 'path': '/categories'}],
             [read('categories', ['title'], [{'title': 'All'}, {'title': 'Science'}], collection=True,
                   description='The account has its default category and Science.')], visible=['Science']),
        step('duplicate', 'Try to create a second category named "Science".',
             'The product refuses the duplicate with a visible message; there is still one Science category.',
             [{'op': 'goto', 'path': '/category/create'}, {'op': 'fill', 'field': 'title', 'value': 'Science'},
              {'op': 'click', 'names': ['Save']}],
             [read('categories', ['title'], [{'title': 'All'}, {'title': 'Science'}], collection=True,
                   description='No second Science category exists.')],
             visible=['already exists'], depends=['created'], requires=['created/state-1']),
        step('renamed', 'Rename the category "Science" to "Natural Science" and hide its entries from the global '
                        'unread list.',
             'The category is called Natural Science and is set to hide its entries from the global unread list.',
             [{'op': 'goto', 'path': '/categories'}, {'op': 'row', 'anchor': 'Science', 'names': ['Edit']},
              {'op': 'fill', 'field': 'title', 'value': 'Natural Science'}, {'op': 'check', 'field': 'hide_globally'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/categories'}],
             [read('categories', ['title', 'hide_globally'], {'title': 'Natural Science', 'hide_globally': True},
                   where={'title': 'Natural Science'}, description='The renamed category hides its entries globally.')],
             visible=['Natural Science'], depends=['created']),
        step('removed', 'Delete the category "Natural Science".', 'Natural Science is no longer listed.',
             [{'op': 'goto', 'path': '/categories'}, {'op': 'row', 'anchor': 'Natural Science', 'names': ['Remove']},
              {'op': 'click', 'names': ['yes']}, {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/categories'}],
             [read('categories', ['title'], [{'title': 'All'}], collection=True,
                   description='Only the default category remains.')], depends=['renamed'],
             requires=['created/state-1'])])
    add('category-entries', 'categories', [
        web('work', 'http://work.test/feed.xml', news('work.test', 'Work Feed', ['Work task', 'Work memo'])),
        web('leisure', 'http://leisure.test/feed.xml', news('leisure.test', 'Leisure Feed', ['Leisure trip'])),
        api('work-category', 'POST', 'categories', {'title': 'Work'}, save='work-category'),
        api('leisure-category', 'POST', 'categories', {'title': 'Leisure'}, save='leisure-category'),
        subscribe('work-feed', 'http://work.test/feed.xml', '{{work-category.id}}'),
        subscribe('leisure-feed', 'http://leisure.test/feed.xml', '{{leisure-category.id}}'),
        {'id': 'star-memo', 'mark': {'title': 'Work memo', 'starred': True}}], [
        step('listed', 'Open the entries of the category "Work".',
             'Work task and Work memo are listed; Leisure trip is not.',
             [{'op': 'goto', 'path': '/categories'}, {'op': 'link', 'href': '/category/{{work-category.id}}/entries'},
              {'op': 'require', 'texts': ['Work memo']}], visible=['Work task', 'Work memo']),
        step('feeds', 'Open the list of feeds of the category "Work".',
             'Work Feed is listed; Leisure Feed is not.',
             [{'op': 'goto', 'path': '/category/{{work-category.id}}/feeds'}], visible=['Work Feed']),
        step('starred', 'Open only the starred entries of the category "Work".',
             'Work memo (the starred one) is listed; Work task is not.',
             [{'op': 'goto', 'path': '/category/{{work-category.id}}/entries'},
              {'op': 'click', 'names': ['Show only starred entries']}, {'op': 'require', 'texts': ['Work memo']}],
             visible=['Work memo']),
        step('category-read', 'Mark all entries of the category "Work" as read.',
             'The Work entries are read; Leisure trip stays unread.',
             [{'op': 'goto', 'path': '/categories'}, {'op': 'row', 'anchor': 'Work', 'names': ['Mark all as read']},
              {'op': 'click', 'names': ['yes']}, {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/categories'}],
             [entries([{'title': 'Work task', 'status': 'read'}, {'title': 'Work memo', 'status': 'read'},
                       {'title': 'Leisure trip', 'status': 'unread'}])]),
        step('counts', 'Open the list of categories and look at their unread counts.',
             'Work shows no unread entries and Leisure shows one unread entry.',
             [{'op': 'goto', 'path': '/categories'}], visible=['Leisure'], depends=['category-read'])])

    # -- settings ------------------------------------------------------------------------------------------------------
    add('settings-appearance', 'settings', [], [
        step('theme', 'Change the theme to "Dark - Sans Serif" and show 10 entries per page.',
             'The interface uses a dark theme; the settings show "Dark - Sans Serif" selected and 10 entries per page.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'select', 'field': 'theme', 'value': 'dark_sans_serif'},
              {'op': 'fill', 'field': 'entries_per_page', 'value': '10'}, {'op': 'click', 'names': ['Update']},
              {'op': 'goto', 'path': '/settings'}],
             [me(['theme', 'entries_per_page'], {'theme': 'dark_sans_serif', 'entries_per_page': 10})]),
        step('sorting', 'Sort entries with the most recent first.', 'The settings show recent entries first.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'select', 'field': 'entry_direction', 'value': 'desc'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/settings'}],
             [me(['entry_sorting_direction'], {'entry_sorting_direction': 'desc'})]),
        step('timezone', 'Set your timezone to "Europe/Paris".', 'The settings show the timezone Europe/Paris.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'select', 'field': 'timezone', 'value': 'Europe/Paris'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/settings'}],
             [me(['timezone'], {'timezone': 'Europe/Paris'})]),
        step('stylesheet', 'Add the custom CSS "body { letter-spacing: 0.5px; }" to your settings.',
             'The settings show the custom CSS.',
             [{'op': 'goto', 'path': '/settings'},
              {'op': 'fill', 'field': 'custom_css', 'value': 'body { letter-spacing: 0.5px; }'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/settings'}],
             [me(['stylesheet'], {'stylesheet': 'body { letter-spacing: 0.5px; }'})]),
        step('language', 'Change the interface language to French ("Français").',
             'The interface is displayed in French.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'select', 'field': 'language', 'value': 'fr_FR'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/settings'}],
             [me(['language'], {'language': 'fr_FR'})], visible=['Paramètres'])],
        # The settings page is large (every observation is long): budget calibrated on the standard answer.
        tokens_per_step=360_000)
    add('settings-password', 'settings', [], [
        step('mismatch', 'Change your password to "Carol-New-2026!" but type "Carol-Other-2026!" as the confirmation.',
             'The change is refused with a visible message about the confirmation; the password is unchanged.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'fill', 'field': 'password', 'value': 'Carol-New-2026!'},
              {'op': 'fill', 'field': 'confirmation', 'value': 'Carol-Other-2026!'},
              {'op': 'click', 'names': ['Update']}],
             [read('me', ['username'], {'username': 'carol'}, actor='carol',
                   refused={'path': 'me', 'actor': ['carol', 'Carol-New-2026!'], 'status': 401},
                   description='The old password still works and the new one does not.')],
             visible=['Passwords are not the same'], requires=['changed/state-1']),
        step('changed', 'Change your password to "Carol-New-2026!" (with the same confirmation), then log out and sign '
                        'in again as "carol" with the new password.',
             'Signing in with the new password works: the reader is shown to carol again.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'fill', 'field': 'password', 'value': 'Carol-New-2026!'},
              {'op': 'fill', 'field': 'confirmation', 'value': 'Carol-New-2026!'}, {'op': 'click', 'names': ['Update']},
              {'op': 'require', 'texts': ['Preferences saved']}, {'op': 'sign-out'}]
             + sign_in_steps('carol', 'Carol-New-2026!') + [{'op': 'wait-url', 'path': '/unread'}],
             [read('me', ['username'], {'username': 'carol'}, actor=['carol', 'Carol-New-2026!'],
                   refused={'path': 'me', 'actor': 'carol', 'status': 401},
                   description='The new password works and the old one is refused.')], visible=['Unread'])],
        actor='carol')
    manual = news('manual.test', 'Manual Feed', ['Manual 1', 'Manual 2'])
    add('settings-reading', 'settings', [web('feed', 'http://manual.test/feed.xml', manual), categories(),
                                         subscribe('subscription', 'http://manual.test/feed.xml')], [
        step('configured', 'Configure reading so that entries are marked as read only manually, the estimated '
                           'reading time is not shown, and the reading speed for other languages is 300 words per '
                           'minute.',
             'The settings show manual marking, no reading time and a reading speed of 300.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'choose', 'label': 'Mark entries as read manually'},
              {'op': 'check', 'field': 'show_reading_time', 'value': False},
              {'op': 'fill', 'field': 'default_reading_speed', 'value': '300'}, {'op': 'click', 'names': ['Update']},
              {'op': 'goto', 'path': '/settings'}],
             [me(['mark_read_on_view', 'show_reading_time', 'default_reading_speed'],
                 {'mark_read_on_view': False, 'show_reading_time': False, 'default_reading_speed': 300})]),
        step('opened', 'Open the entry "Manual 1" to read it.',
             'The entry Manual 1 is displayed and still offered to be marked as read (it stays unread).',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'click', 'names': ['Manual 1']},
              {'op': 'require', 'texts': ['Manual 1 body text.']}],
             [entries([{'title': 'Manual 1', 'status': 'unread'}, {'title': 'Manual 2', 'status': 'unread'}])],
             visible=['Manual 1 body text.'], depends=['configured'], requires=['configured/state-1'])])
    filtered = rss('Filtered News', 'http://filtered.test/', [
        item('Regular article', 'http://filtered.test/1', 'filtered-1', 'Mon, 01 Sep 2025 09:00:00 GMT', 'Fine.'),
        item('Sponsored: buy now', 'http://filtered.test/2', 'filtered-2', 'Tue, 02 Sep 2025 09:00:00 GMT', 'Ad.'),
        item('Another article', 'http://filtered.test/3', 'filtered-3', 'Wed, 03 Sep 2025 09:00:00 GMT', 'Fine too.')])
    add('settings-filters', 'settings', [web('feed', 'http://filtered.test/feed.xml', filtered)], [
        step('rule', 'Add the global entry blocking rule "EntryTitle=(?i)sponsored" to your settings.',
             'The settings show the entry blocking rule.',
             [{'op': 'goto', 'path': '/settings'},
              {'op': 'fill', 'field': 'block_filter_entry_rules', 'value': 'EntryTitle=(?i)sponsored'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/settings'}],
             [me(['block_filter_entry_rules'], {'block_filter_entry_rules': 'EntryTitle=(?i)sponsored'})]),
        step('applied', 'Subscribe to http://filtered.test/feed.xml.',
             'Filtered News is subscribed with Regular article and Another article; the sponsored entry is not '
             'listed.',
             [{'op': 'goto', 'path': '/subscribe'}, {'op': 'fill', 'field': 'url', 'value': 'http://filtered.test/feed.xml'},
              {'op': 'click', 'names': ['Find a feed']}, {'op': 'require', 'texts': ['Another article']}],
             [entries([{'title': 'Regular article'}, {'title': 'Another article'}], fields=('title',))],
             visible=['Regular article'], depends=['rule'])])
    add('settings-home', 'settings', [], [
        step('home', 'Make the categories page your default home page.',
             'The settings show the categories page as the default home page.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'select', 'field': 'default_home_page', 'value': 'categories'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/settings'}],
             [me(['default_home_page'], {'default_home_page': 'categories'}, actor='bob')]),
        step('relogin', f'Log out, then sign in again as "bob" with the password "{CREDS["bob"]}".',
             'After signing in, the categories page is shown first.',
             [{'op': 'sign-out'}] + sign_in_steps('bob', CREDS['bob']) + [{'op': 'wait-url', 'path': '/categories'}],
             visible=['Categories'], depends=['home'])], actor='bob')
    add('settings-validation', 'settings', [], [
        step('refused', 'Change your username to "alice".',
             'The change is refused with a visible message that the name is already taken.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'fill', 'field': 'username', 'value': 'alice'},
              {'op': 'click', 'names': ['Update']}],
             [me(['username'], {'username': 'carol'}, actor='carol')], visible=['already exists'],
             requires=['accepted/state-1']),
        step('accepted', 'Change your username to "caroline".', 'The settings are saved with the username caroline.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'fill', 'field': 'username', 'value': 'caroline'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/settings'}],
             [read('me', ['username'], {'username': 'caroline'}, actor=['caroline', CREDS['carol']],
                   refused={'path': 'me', 'actor': 'carol', 'status': 401},
                   description='The account signs in as caroline and no longer as carol.')])], actor='carol')

    # Settings whose effect shows elsewhere.
    effects = news('effects.test', 'Effects Feed', ['Effect 1', 'Effect 2', 'Effect 3'])
    podcast = rss('Pod Feed', 'http://pod.test/', [
        item('Episode one', 'http://pod.test/1', 'pod-1', 'Mon, 01 Sep 2025 09:00:00 GMT', 'Show notes.',
             '<enclosure url="http://media.pod.test/one.mp3" length="2048" type="audio/mpeg"/>')])
    add('settings-effects', 'settings', [web('feed', 'http://effects.test/feed.xml', effects),
                                         web('podcast', 'http://pod.test/feed.xml', podcast), categories(),
                                         subscribe('effects-feed', 'http://effects.test/feed.xml'),
                                         subscribe('pod-feed', 'http://pod.test/feed.xml')], [
        step('recent-first', 'Make the most recent entries come first, then open your unread entries.',
             'The unread entries are listed newest first: Effect 3, then Effect 2, then Effect 1.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'select', 'field': 'entry_direction', 'value': 'desc'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/unread'}],
             [me(['entry_sorting_direction'], {'entry_sorting_direction': 'desc'})], visible=['Effect 3']),
        step('shortcuts-off', 'Turn off the keyboard shortcuts in your settings, then press "?" on the unread entries '
                              'page.',
             'No keyboard shortcuts help appears.',
             [{'op': 'goto', 'path': '/settings'}, {'op': 'check', 'field': 'keyboard_shortcuts', 'value': False},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/unread'}, {'op': 'press', 'key': '?'},
              {'op': 'require-absent', 'texts': ['Keyboard Shortcuts']}],
             [me(['keyboard_shortcuts'], {'keyboard_shortcuts': False})], requires=['shortcuts-off/state-1']),
        step('no-player', 'In the settings of the feed "Pod Feed", turn off the media player, then open its entry '
                          '"Episode one".',
             'The entry lists its audio attachment without an audio player.',
             [{'op': 'goto', 'path': '/feed/{{pod-feed.feed_id}}/edit'}, {'op': 'check', 'field': 'no_media_player'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/feed/{{pod-feed.feed_id}}/entries'},
              {'op': 'click', 'names': ['Episode one']}, {'op': 'require', 'texts': ['Show notes.']},
              {'op': 'require-absent', 'texts': ['Seek:']}],
             [feed('http://pod.test/feed.xml', ['no_media_player'], {'no_media_player': True})],
             visible=['Attachments'])])
    add('refresh-all', 'feed-settings', [
        web('on-v1', 'http://on.test/feed.xml', news('on.test', 'Enabled Feed', ['On one'])),
        web('off-v1', 'http://off.test/feed.xml', news('off.test', 'Disabled Feed', ['Off one'])),
        categories(), subscribe('on-feed', 'http://on.test/feed.xml'),
        subscribe('off-feed', 'http://off.test/feed.xml', disabled=True),
        web('on-v2', 'http://on.test/feed.xml', news('on.test', 'Enabled Feed', ['On one', 'On two'])),
        web('off-v2', 'http://off.test/feed.xml', news('off.test', 'Disabled Feed', ['Off one', 'Off two']))], [
        step('refreshed', 'From the list of feeds, refresh all feeds in the background, then open your unread '
                          'entries.',
             'The new entry "On two" of Enabled Feed is among the unread entries; "Off two" of the disabled feed is not.',
             [{'op': 'goto', 'path': '/feeds'}, {'op': 'click', 'names': ['Refresh all feeds in the background']},
              {'op': 'sleep', 'seconds': 3}, {'op': 'goto', 'path': '/unread'}, {'op': 'require', 'texts': ['On two']}],
             [{'web': {'fetched': ['http://on.test/feed.xml', 'http://off.test/feed.xml'], 'again': True,
                       'at_least': {'http://on.test/feed.xml': 2}},
               'expected': {'http://on.test/feed.xml': {'fetched': True, 'again': True},
                            'http://off.test/feed.xml': {'fetched': True, 'again': False}},
               'description': 'Refreshing all feeds fetched the enabled feed again and not the disabled one.'},
              {**entries([{'title': 'On one'}, {'title': 'On two'}, {'title': 'Off one'}], fields=('title',)),
               'settle': 2}],
             visible=['On two'])])
    add('about', 'about', [], [
        step('version', 'Open the About page of the application.',
             'The About page shows the application version 2.3.4.',
             [{'op': 'goto', 'path': '/about'}], visible=['2.3.4'])])

    # -- API keys, users, sessions -------------------------------------------------------------------------------------
    add('api-keys', 'api-keys', [], [
        step('created', 'Create an API key labelled "GUI client".',
             'The key GUI client is listed with its token.',
             [{'op': 'goto', 'path': '/keys/create'}, {'op': 'fill', 'field': 'description', 'value': 'GUI client'},
              {'op': 'click', 'names': ['Save']}, {'op': 'require', 'texts': ['GUI client']}],
             [read('api-keys', ['description'], [{'description': 'GUI client'}], collection=True,
                   description='The account has the API key GUI client.')], visible=['GUI client']),
        step('deleted', 'Delete the API key "GUI client".', 'The key GUI client is no longer listed.',
             [{'op': 'goto', 'path': '/keys'}, {'op': 'click', 'names': ['Remove']}, {'op': 'click', 'names': ['yes']},
              {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/keys'}],
             [read('api-keys', ['description'], [], collection=True, description='The account has no API key left.')],
             depends=['created'], requires=['created/state-1'])])
    add('users-admin', 'users', [], [
        step('created', 'Create the user "dave" with the password "Dave-Local-2026!"; dave is not an administrator.',
             'The user dave is listed among the users, without administrator rights.',
             [{'op': 'goto', 'path': '/user/create'}, {'op': 'fill', 'field': 'username', 'value': 'dave'},
              {'op': 'fill', 'field': 'password', 'value': 'Dave-Local-2026!'},
              {'op': 'fill', 'field': 'confirmation', 'value': 'Dave-Local-2026!'}, {'op': 'click', 'names': ['Save']},
              {'op': 'goto', 'path': '/users'}],
             [read('users', ['username', 'is_admin'], {'username': 'dave', 'is_admin': False}, where={'username': 'dave'},
                   save='dave', description='The account dave exists without administrator rights.'),
              read('me', ['username'], {'username': 'dave'}, actor=['dave', 'Dave-Local-2026!'],
                   description='dave signs in with the chosen password.')], visible=['dave']),
        step('duplicate', 'Try to create another user named "bob".',
             'The product refuses it with a visible message that the user already exists.',
             [{'op': 'goto', 'path': '/user/create'}, {'op': 'fill', 'field': 'username', 'value': 'bob'},
              {'op': 'fill', 'field': 'password', 'value': 'Another-Bob-2026!'},
              {'op': 'fill', 'field': 'confirmation', 'value': 'Another-Bob-2026!'}, {'op': 'click', 'names': ['Save']}],
             [read('users', ['username'], [{'username': n} for n in ('alice', 'bob', 'carol', 'dave')], collection=True,
                   description='No second bob account exists.')],
             visible=['already exists'], requires=['created/state-1']),
        step('promoted', 'Give dave administrator rights.', 'dave is shown as an administrator.',
             [{'op': 'goto', 'path': '/users/{{dave.id}}/edit'}, {'op': 'check', 'field': 'is_admin'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/users'}],
             [read('users', ['username', 'is_admin'], {'username': 'dave', 'is_admin': True}, where={'username': 'dave'},
                   description='dave has administrator rights.')], depends=['created']),
        step('renamed', 'Rename the user dave to "david".', 'The user list shows david instead of dave.',
             [{'op': 'goto', 'path': '/users/{{dave.id}}/edit'}, {'op': 'fill', 'field': 'username', 'value': 'david'},
              {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/users'}],
             [read('users', ['username'], [{'username': n} for n in ('alice', 'bob', 'carol', 'david')], collection=True,
                   description='The account is now called david.')], visible=['david'], depends=['created']),
        step('removed', 'Delete the user david.', 'david is no longer listed among the users.',
             [{'op': 'goto', 'path': '/users'}, {'op': 'row', 'href': '/users/{{dave.id}}/edit', 'names': ['Remove']},
              {'op': 'click', 'names': ['yes']}, {'op': 'sleep', 'seconds': 1}, {'op': 'goto', 'path': '/users'}],
             [read('users', ['username'], [{'username': n} for n in ('alice', 'bob', 'carol')], collection=True,
                   description='Only the baseline accounts remain.')], depends=['renamed'])])
    add('users-denied', 'users', [], [
        step('denied', 'Open the user administration page /users.',
             'Bob, who is not an administrator, cannot see or manage the user list (the page is refused).',
             [{'op': 'goto', 'path': '/users'}, {'op': 'require', 'texts': ['Forbidden']}],
             [read('me', ['username', 'is_admin'], {'username': 'bob', 'is_admin': False}, actor='bob',
                   refused={'path': 'users', 'actor': 'bob', 'status': 403},
                   description='bob is not an administrator and the user list is refused to him.')],
             requires=['settings/visible']),
        step('settings', 'Open your own settings.', 'The settings page of bob is shown (its username field holds bob).',
             [{'op': 'goto', 'path': '/settings'}], visible=['Settings'])], actor='bob')
    add('sessions', 'sessions', [], [
        step('listed', 'Open the list of your active sessions.',
             'The current browser session is listed with its browser (user agent) and marked as the current one.',
             [{'op': 'goto', 'path': '/sessions'}], visible=['Current Session'])])

    # -- OPML ----------------------------------------------------------------------------------------------------------
    upload = opml_document([('Imported', [('Uploaded One', 'http://upload-one.test/feed.xml', 'http://upload-one.test/'),
                                          ('Uploaded Two', 'http://upload-two.test/feed.xml', 'http://upload-two.test/')])])
    add('opml-file', 'opml', [], [
        step('imported', 'Import the subscriptions of the OPML file subscriptions.opml.',
             'The feeds Uploaded One and Uploaded Two are subscribed in the category Imported.',
             [{'op': 'goto', 'path': '/import'}, {'op': 'upload', 'field': 'file', 'file': 'subscriptions.opml',
                                                  'mime_type': 'text/x-opml'},
              {'op': 'click-nth', 'names': ['Import'], 'nth': 0}, {'op': 'goto', 'path': '/feeds'}],
             [feeds([{'title': 'Uploaded One', 'feed_url': 'http://upload-one.test/feed.xml', 'category.title': 'Imported'},
                     {'title': 'Uploaded Two', 'feed_url': 'http://upload-two.test/feed.xml', 'category.title': 'Imported'}])],
             visible=['Uploaded One', 'Uploaded Two'])], files={'subscriptions.opml': upload})
    remote = opml_document([(None, [('Remote One', 'http://remote-one.test/feed.xml', 'http://remote-one.test/')]),
                            ('Remote Group', [('Remote Two', 'http://remote-two.test/feed.xml', 'http://remote-two.test/')])])
    add('opml-url', 'opml', [web('list', 'http://lists.test/subscriptions.opml', remote, 'text/x-opml')], [
        step('imported', 'Import the subscriptions listed in the OPML document at http://lists.test/subscriptions.opml.',
             'Remote One is subscribed in the default category and Remote Two in the category Remote Group.',
             [{'op': 'goto', 'path': '/import'}, {'op': 'fill', 'field': 'url',
                                                  'value': 'http://lists.test/subscriptions.opml'},
              {'op': 'click-nth', 'names': ['Import'], 'nth': 1}, {'op': 'goto', 'path': '/feeds'}],
             [feeds([{'title': 'Remote One', 'feed_url': 'http://remote-one.test/feed.xml', 'category.title': 'All'},
                     {'title': 'Remote Two', 'feed_url': 'http://remote-two.test/feed.xml', 'category.title': 'Remote Group'}])],
             visible=['Remote One', 'Remote Two'])])
    add('opml-export', 'opml', [web('feed', 'http://gazette.test/feed.xml', gazette), categories(),
                                subscribe('subscription', 'http://gazette.test/feed.xml')], [
        step('exported', 'Export your subscriptions as an OPML file.',
             'An OPML file with the subscriptions is produced as a download.',
             [{'op': 'goto', 'path': '/feeds'}, {'op': 'click', 'names': ['Export']},
              {'op': 'require-download', 'suffix': '.opml'}])])

    # -- keyboard and persistence ------------------------------------------------------------------------------------
    keys = news('keys.test', 'Keyboard Feed', ['Key 1', 'Key 2', 'Key 3'])
    add('keyboard', 'keyboard-shortcuts', [web('feed', 'http://keys.test/feed.xml', keys), categories(),
                                           subscribe('subscription', 'http://keys.test/feed.xml')], [
        step('help', 'On the unread entries page, open the keyboard shortcuts help with the "?" key.',
             'A help listing the keyboard shortcuts (navigation and actions) is shown.',
             [{'op': 'goto', 'path': '/unread'}, {'op': 'press', 'key': '?'},
              {'op': 'require', 'texts': ['Keyboard Shortcuts']}], visible=['Keyboard Shortcuts']),
        step('toggle', 'Close the help and, using keyboard shortcuts only, select the first entry of the unread list '
                       '(Key 1) and toggle it to read.',
             'Key 1 is marked as read; Key 2 and Key 3 stay unread.',
             [{'op': 'press', 'key': 'Escape'}, {'op': 'press', 'key': 'j'}, {'op': 'press', 'key': 'm'},
              {'op': 'sleep', 'seconds': 1}],
             [entries([{'title': 'Key 1', 'status': 'read'}, {'title': 'Key 2', 'status': 'unread'},
                       {'title': 'Key 3', 'status': 'unread'}])], depends=['help'])])
    add('restart-visible-state', 'persistence', [], [
        step('before', 'Create the category "Durable".', 'The category Durable is listed.',
             [{'op': 'goto', 'path': '/category/create'}, {'op': 'fill', 'field': 'title', 'value': 'Durable'},
              {'op': 'click', 'names': ['Save']}, {'op': 'goto', 'path': '/categories'}],
             [read('categories', ['title'], [{'title': 'All'}, {'title': 'Durable'}], collection=True,
                   description='The category Durable exists.')], visible=['Durable']),
        step('after', 'The application was restarted with the same data. Open the list of categories.',
             'The category Durable is still listed after the restart.',
             [{'op': 'goto', 'path': '/categories'}],
             [read('categories', ['title'], [{'title': 'All'}, {'title': 'Durable'}], collection=True,
                   description='The category Durable survived the restart.')], visible=['Durable'],
             depends=['before'], lifecycle='restart')])
    return episodes
