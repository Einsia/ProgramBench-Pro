"""Third-party integrations, configured in the integration settings (browser checkpoints) and observed as the
requests the product sends to the local web: the webhook on saved entries and on new entries of a refresh,
bookmark services on saved entries (Linkding, Wallabag with its token exchange), notifications of new entries
(Apprise, Slack), and the save action of the REST API with and without an enabled integration."""
import json
import re
import urllib.parse

import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS, canonical_html, norm_text, unordered

DATE = 'Mon, {:02d} Mar 2025 08:30:00 GMT'
SIGNATURE = re.compile(r'^[0-9a-f]{64}$')
HOOK = 'http://hooks.test/receive'
LINKDING = ('http://links.test', 'ld-key-2026', 'miniflux, news')
WALLABAG = ('http://wallabag.test', 'wb-client', 'wb-secret', 'wb-user', 'wb-pass-2026', 'reading')
APPRISE = ('http://apprise.test', 'json://notify.test/inbox')
SLACK = 'http://slack.test/services/hook'
# Seven browser checkpoints on the large integration settings and feed pages: the evaluator budget is calibrated
# on the standard answer (its usage stays under 40%).
BUDGET = {'calls': 250, 'seconds': 1740, 'tokens': 3_500_000}
FEED_HOOK = 'http://feedhook.test/receive'
FEED_APPRISE = 'json://feed-notify.test/inbox'


def hook_item(n):
    extra = f'<author>writer{n}@hooknews.test (Hook Writer {n})</author><category>topic-{n}</category>'
    if n == 1:
        extra += ('<comments>http://hooknews.test/1#comments</comments>'
                  '<enclosure url="http://media.hooknews.test/one.mp3" length="1234" type="audio/mpeg"/>')
    return item(f'Hook {n}', f'http://hooknews.test/{n}', f'hook-{n}', DATE.format(n),
                fx.html_text(f'<p>Hook body <b>{n}</b></p>'), extra)


def hook_feed(count):
    return rss('Hook News', 'http://hooknews.test/', [hook_item(n) for n in range(count, 0, -1)])


SITE = page('Hook site', '<p>site</p>')
OTHER = rss('Bob Hooks', 'http://bobhooks.test/', [
    item('Bob item', 'http://bobhooks.test/1', 'bob-1', DATE.format(20), 'Bob body')])


def remember(c):
    for actor in ('alice', 'bob'):
        r, p = c.request('GET', 'entries', actor, params={'limit': 100})
        c.state.setdefault('by-title', {}).update({e['title']: e for e in p['entries']})
    r, feeds = c.request('GET', 'feeds')
    c.state['hook-feed'] = next(f for f in feeds if f['title'] == 'Hook News')


def entry_id(c, title):
    return c.state['by-title'][title]['id']


# -- observations of delivered requests ---------------------------------------------------------------------
def deliveries(c, host, mark, count=1, seconds=15):
    """Requests the product sent to one local-web host since mark: waits for `count`, then for stragglers."""
    read = lambda: [x for x in c.web_requests(host=host, since=mark) if x['method'] != 'CONNECT']
    c.wait(read, lambda xs: len(xs) >= count, seconds=seconds, what='deliveries to ' + host)
    return c.settle(read, quiet=1.5, limit=10)


def body_of(x):
    if 'body' in x:
        return x['body']
    return '<binary>' if x.get('body_base64') else ''


def json_body(x):
    try:
        return json.loads(body_of(x))
    except (TypeError, ValueError):
        return {'not-json': norm_text(body_of(x))[:200]}


def webhook_feed(c, f):
    n = c.norm
    out = n.clean({k: v for k, v in f.items() if k != 'category'}, 'feed')
    if isinstance(f.get('category'), dict):
        out['category'] = {'id': n.identity('category', f['category'].get('id')), 'title': f['category'].get('title')}
    return out


def webhook_entry(c, e):
    out = c.norm.clean({k: v for k, v in e.items() if k != 'feed'}, 'entry')
    if isinstance(e.get('feed'), dict):
        out['feed'] = webhook_feed(c, e['feed'])
    return out


def webhook_payload(c, payload):
    if not isinstance(payload, dict):
        return payload
    out = {k: v for k, v in payload.items() if k not in ('feed', 'entry', 'entries')}
    if isinstance(payload.get('feed'), dict):
        out['feed'] = webhook_feed(c, payload['feed'])
    if isinstance(payload.get('entry'), dict):
        out['entry'] = webhook_entry(c, payload['entry'])
    if isinstance(payload.get('entries'), list):
        out['entries'] = unordered([webhook_entry(c, e) if isinstance(e, dict) else e for e in payload['entries']])
    return out


def webhook_request(c, x, full=True):
    signature = x['headers'].get('x-miniflux-signature')
    out = {'method': x['method'], 'url': norm_text(x['url']), 'content-type': x['headers'].get('content-type'),
           'event': x['headers'].get('x-miniflux-event-type'),
           'signature': '[signature]' if signature and SIGNATURE.match(signature) else signature}
    payload = json_body(x)
    if full:
        out['body'] = webhook_payload(c, payload)
    else:
        entry = payload.get('entry') if isinstance(payload, dict) else None
        out['body'] = {'event_type': payload.get('event_type') if isinstance(payload, dict) else None,
                       'entry_title': entry.get('title') if isinstance(entry, dict) else None}
    return out


def plain_request(c, x, headers=('content-type', 'authorization', 'accept'), form=False):
    out = {'method': x['method'], 'url': norm_text(x['url'])}
    for name in headers:
        out[name] = x['headers'].get(name)
    if form:
        out['form'] = {k: v for k, v in sorted(urllib.parse.parse_qs(body_of(x), keep_blank_values=True).items())}
    else:
        payload = json_body(x)
        if isinstance(payload, dict) and isinstance(payload.get('content'), str):
            payload = {**payload, 'content': canonical_html(payload['content'])}
        out['json'] = payload
    return out


# -- actions ---------------------------------------------------------------------------------------------------
def save(title, host, view, count=1, actor='alice'):
    """Save an entry through the REST API and observe what reached one service of the local web."""
    def action(c):
        mark = c.web_mark()
        r, p = c.request('POST', f'entries/{entry_id(c, title)}/save', actor)
        if r.status_code >= 400:
            return c.observe(r, p)
        sent = deliveries(c, host, mark, count)
        return {'status': r.status_code, 'requests': [view(c, x) for x in sent]}
    return action


def refresh_with(count, host, view, new=1):
    """Publish the feed with `count` items, refresh it and observe what reached one service of the local web.

    The case brings its own starting point: the document without the `new` last items is refreshed first (not
    observed), so exactly those items are new whatever earlier cases did, and its deliveries settle before the
    observation starts."""
    def action(c):
        feed = c.state['hook-feed']['id']
        before = c.web_mark()
        c.web_put('http://hooknews.test/feed.xml', hook_feed(count - new), fx.RSS_TYPE)
        c.request('PUT', f'feeds/{feed}/refresh')
        c.settle(lambda: len([x for x in c.web_requests(since=before) if x['host'] != 'hooknews.test']),
                 quiet=1.5, limit=15)
        c.web_put('http://hooknews.test/feed.xml', hook_feed(count), fx.RSS_TYPE)
        mark = c.web_mark()
        r, p = c.request('PUT', f'feeds/{feed}/refresh')
        if r.status_code >= 400:
            return c.observe(r, p)
        sent = deliveries(c, host, mark, 1)
        return {'status': r.status_code, 'requests': [view(c, x) for x in sent]}
    return action


def quiet_refresh(c):
    """A refresh without new entries notifies nobody."""
    mark = c.web_mark()
    r, p = c.request('PUT', f"feeds/{c.state['hook-feed']['id']}/refresh")
    sent = c.settle(lambda: [x['host'] for x in c.web_requests(since=mark)
                             if x['host'] in ('hooks.test', 'apprise.test', 'slack.test')], quiet=3.0, limit=10)
    return {'status': r.status_code, 'notified': sorted(set(sent))}


def everyone(c):
    """Saving with several services enabled delivers the entry to each bookmark service and the webhook."""
    mark = c.web_mark()
    r, p = c.request('POST', f"entries/{entry_id(c, 'Hook 2')}/save")
    hosts = ('hooks.test', 'links.test', 'wallabag.test', 'apprise.test', 'slack.test')
    seen = c.wait(lambda: {x['host'] for x in c.web_requests(since=mark) if x['host'] in hosts},
                  lambda got: {'hooks.test', 'links.test', 'wallabag.test'} <= got, seconds=15)
    seen = c.settle(lambda: sorted({x['host'] for x in c.web_requests(since=mark) if x['host'] in hosts}),
                    quiet=2.0, limit=10)
    return {'status': r.status_code, 'services': seen}


def feed_hook(c):
    """With a feed's own webhook URL, its new entries go there and not to the account's webhook."""
    out = refresh_with(8, 'feedhook.test', webhook_request)(c)
    # The account webhook got nothing for the observed refresh (its requests after the new document).
    newest = [x for x in c.web_requests(host='hooks.test') if x['method'] == 'POST'
              and 'Hook 8' in (x.get('body') or '')]
    out['account_webhook'] = len(newest)
    return out


def wallabag_view(c, x):
    if x['url'].endswith('/oauth/v2/token'):
        return plain_request(c, x, ('content-type', 'accept'), form=True)
    return plain_request(c, x, ('content-type', 'authorization', 'accept'))


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    fx.default_category(s, 'accounts', 'bob')
    s.fixture('web', 'publish', fx.publish_all([
        ('http://hooknews.test/feed.xml', hook_feed(2), fx.RSS_TYPE), ('http://hooknews.test/', SITE, fx.HTML_TYPE),
        ('http://bobhooks.test/feed.xml', OTHER, fx.RSS_TYPE),
        (HOOK, '{"ok": true}', 'application/json'),
        (LINKDING[0] + '/api/bookmarks/', '{"id": 1}', 'application/json', 201),
        (WALLABAG[0] + '/oauth/v2/token', '{"access_token": "wallabag-access-2026", "token_type": "bearer", '
                                          '"expires_in": 3600}', 'application/json'),
        (WALLABAG[0] + '/api/entries.json', '{"id": 7}', 'application/json'),
        (APPRISE[0] + '/notify', '{"ok": true}', 'application/json'),
        (SLACK, 'ok', 'text/plain'), (FEED_HOOK, '{"ok": true}', 'application/json')]))
    s.setup('library', 'category', 'POST', 'categories', body={'title': 'Hook shelf'}, save='shelf')
    fx.subscribe(s, 'library', 'hooks', 'http://hooknews.test/feed.xml', 'hooks', category='shelf')
    fx.subscribe(s, 'library', 'bob-hooks', 'http://bobhooks.test/feed.xml', 'bob-hooks', actor='bob')
    s.fixture('library', 'remember', remember)
    L = ['fx:accounts', 'fx:web', 'fx:library']

    no_integration = s.api('integrations', 'status', 'none', 'GET', 'integrations/status', needs=L,
                           description='Before any integration is enabled the account reports none.')
    s.api('integrations', 'save', 'without-integration', 'POST',
          lambda c: f"entries/{entry_id(c, 'Hook 1')}/save", needs=L, requires=[no_integration],
          description='Saving an entry needs an enabled integration.')

    hooked = s.check('webhook', 'enable', 'delivery', save('Hook 1', 'hooks.test', lambda c, x: webhook_request(
        c, x, full=False)), description='A saved entry is delivered to the webhook URL as a signed save event.')
    webhook = s.gui('integration', 'enable-webhook',
                    f'Open the integration settings, activate the webhook with the URL "{HOOK}", and save.',
                    f'The integration settings show the webhook activated with the URL {HOOK} and a secret.',
                    [{'op': 'goto', 'path': '/integrations'}, {'op': 'expand', 'text': 'Webhook', 'probe': 'Default Webhook URL'},
                     {'op': 'check', 'field': 'webhook_enabled'}, {'op': 'fill', 'field': 'webhook_url', 'value': HOOK},
                     {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/integrations'}],
                    checks=[hooked], needs=L)
    W = L + [webhook]
    enabled_status = s.api('integrations', 'status', 'enabled', 'GET', 'integrations/status', needs=W,
                           requires=[webhook], description='With the webhook enabled the account reports integrations.')
    s.api('integrations', 'status', 'other-account', 'GET', 'integrations/status', actor='bob', needs=W,
          requires=[webhook], description='Another account still reports none.')
    s.api('integrations', 'save', 'other-account', 'POST', lambda c: f"entries/{entry_id(c, 'Bob item')}/save",
          actor='bob', needs=W, requires=[webhook], description='Another account cannot save without its own.')
    s.api('integrations', 'save', 'missing-entry', 'POST', 'entries/987654321/save', needs=W, requires=[webhook],
          description='Saving an entry that does not exist.')
    s.api('integrations', 'save', 'foreign-entry', 'POST', lambda c: f"entries/{entry_id(c, 'Bob item')}/save",
          needs=W, requires=[webhook], description='Saving another account\'s entry.')
    s.add('webhook', 'save', 'payload', save('Hook 2', 'hooks.test', webhook_request), needs=W,
          description='The save event carries the entry with its feed and category.')
    s.add('webhook', 'save', 'enclosure', save('Hook 1', 'hooks.test', webhook_request), needs=W,
          description='The save event of an entry with comments link, enclosure and tags.')
    pushed = s.add('webhook', 'refresh', 'new-entries', refresh_with(3, 'hooks.test', webhook_request), needs=W,
                   description='A refresh that finds a new entry sends a new-entries event with the feed.')
    s.add('webhook', 'refresh', 'nothing-new', quiet_refresh, needs=W, requires=[pushed],
          description='A refresh without new entries sends nothing.')
    s.add('webhook', 'refresh', 'two-new', refresh_with(5, 'hooks.test', webhook_request, new=2), needs=W,
          description='Several new entries of one refresh travel in one event.')

    linked = s.check('linkding', 'enable', 'bookmark', save('Hook 1', 'links.test', plain_request),
                     description='A saved entry becomes a Linkding bookmark with the API key, tags and unread flag.')
    linkding = s.gui('integration', 'enable-linkding',
                     f'Open the integration settings and activate Linkding with the API endpoint "{LINKDING[0]}", the '
                     f'API key "{LINKDING[1]}" and the tags "{LINKDING[2]}"; bookmarks should be marked as unread. '
                     'Save.',
                     f'The integration settings show Linkding activated with {LINKDING[0]}, the API key, the tags '
                     f'"{LINKDING[2]}" and bookmarks marked as unread.',
                     [{'op': 'goto', 'path': '/integrations'}, {'op': 'expand', 'text': 'Linkding', 'probe': 'Linkding API Endpoint'},
                      {'op': 'check', 'field': 'linkding_enabled'},
                      {'op': 'fill', 'field': 'linkding_url', 'value': LINKDING[0]},
                      {'op': 'fill', 'field': 'linkding_api_key', 'value': LINKDING[1]},
                      {'op': 'fill', 'field': 'linkding_tags', 'value': LINKDING[2]},
                      {'op': 'check', 'field': 'linkding_mark_as_unread'},
                      {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/integrations'}],
                     checks=[linked], needs=L)

    walled = s.check('wallabag', 'enable', 'entry', save('Hook 2', 'wallabag.test', wallabag_view, count=2),
                     description='A saved entry goes to Wallabag after a password-grant token exchange.')
    wallabag = s.gui('integration', 'enable-wallabag',
                     f'Open the integration settings and activate Wallabag with the API endpoint "{WALLABAG[0]}", the '
                     f'client ID "{WALLABAG[1]}", the client secret "{WALLABAG[2]}", the username "{WALLABAG[3]}", '
                     f'the password "{WALLABAG[4]}" and the tags "{WALLABAG[5]}". Save.',
                     f'The integration settings show Wallabag activated with {WALLABAG[0]}, the client ID '
                     f'{WALLABAG[1]}, the username {WALLABAG[3]} and the tags {WALLABAG[5]}.',
                     [{'op': 'goto', 'path': '/integrations'}, {'op': 'expand', 'text': 'Wallabag', 'probe': 'Wallabag Base URL'},
                      {'op': 'check', 'field': 'wallabag_enabled'},
                      {'op': 'fill', 'field': 'wallabag_url', 'value': WALLABAG[0]},
                      {'op': 'fill', 'field': 'wallabag_client_id', 'value': WALLABAG[1]},
                      {'op': 'fill', 'field': 'wallabag_client_secret', 'value': WALLABAG[2]},
                      {'op': 'fill', 'field': 'wallabag_username', 'value': WALLABAG[3]},
                      {'op': 'fill', 'field': 'wallabag_password', 'value': WALLABAG[4]},
                      {'op': 'fill', 'field': 'wallabag_tags', 'value': WALLABAG[5]},
                      {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/integrations'}],
                     checks=[walled], needs=L)
    s.add('integrations', 'save', 'every-service', everyone, needs=W + [linkding, wallabag],
          description='With several services enabled a save reaches each of them.')

    notified = s.check('apprise', 'enable', 'notification', refresh_with(6, 'apprise.test', plain_request),
                       description='A new entry of a refresh is announced to the Apprise server.')
    apprise = s.gui('integration', 'enable-apprise',
          f'Open the integration settings and activate Apprise with the Apprise API URL "{APPRISE[0]}" and the '
          f'service URL "{APPRISE[1]}". Save.',
          f'The integration settings show Apprise activated with {APPRISE[0]} and the service URL {APPRISE[1]}.',
          [{'op': 'goto', 'path': '/integrations'}, {'op': 'expand', 'text': 'Apprise', 'probe': 'Apprise API URL'},
           {'op': 'check', 'field': 'apprise_enabled'}, {'op': 'fill', 'field': 'apprise_url', 'value': APPRISE[0]},
           {'op': 'fill', 'field': 'apprise_services_url', 'value': APPRISE[1]},
           {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/integrations'}],
          checks=[notified], needs=L)

    slacked = s.check('slack', 'enable', 'message', refresh_with(7, 'slack.test', plain_request),
                      description='A new entry of a refresh is posted to the Slack webhook as an attachment.')
    s.gui('integration', 'enable-slack',
          f'Open the integration settings and activate Slack with the webhook link "{SLACK}". Save.',
          f'The integration settings show Slack activated with the webhook link {SLACK}.',
          [{'op': 'goto', 'path': '/integrations'}, {'op': 'expand', 'text': 'Slack', 'probe': 'Slack Webhook link'},
           {'op': 'check', 'field': 'slack_enabled'}, {'op': 'fill', 'field': 'slack_webhook_link', 'value': SLACK},
           {'op': 'click', 'names': ['Update']}, {'op': 'goto', 'path': '/integrations'}],
          checks=[slacked], needs=L)

    own_hook = s.check('webhook', 'feed', 'own-url', feed_hook,
                       description='New entries of the feed go to its own webhook URL instead of the account\'s.')
    s.gui('feed', 'webhook-url',
          f'In the settings of the feed "Hook News", set its own webhook URL to "{FEED_HOOK}" and save.',
          f'The settings of Hook News show the webhook URL {FEED_HOOK}.',
          [{'op': 'goto', 'path': '/feed/{{hooks.feed_id}}/edit'},
           {'op': 'expand', 'text': 'Webhook', 'probe': 'Override webhook url'},
           {'op': 'fill', 'field': 'webhook_url', 'value': FEED_HOOK}, {'op': 'click', 'names': ['Update']},
           {'op': 'goto', 'path': '/feed/{{hooks.feed_id}}/edit'}],
          checks=[own_hook], needs=W)

    own_apprise = s.check('apprise', 'feed', 'own-services', refresh_with(9, 'apprise.test', plain_request),
                          description='New entries of the feed are announced to its own Apprise service URLs.')
    s.gui('feed', 'apprise-services',
          f'In the settings of the feed "Hook News", set its own Apprise service URL to "{FEED_APPRISE}" and save.',
          f'The settings of Hook News show the Apprise service URL {FEED_APPRISE}.',
          [{'op': 'goto', 'path': '/feed/{{hooks.feed_id}}/edit'},
           {'op': 'expand', 'text': 'Apprise', 'probe': 'Comma separated list of Apprise service URLs'},
           {'op': 'fill', 'field': 'apprise_service_urls', 'value': FEED_APPRISE}, {'op': 'click', 'names': ['Update']},
           {'op': 'goto', 'path': '/feed/{{hooks.feed_id}}/edit'}],
          checks=[own_apprise], needs=L + [apprise])

    # The status without integrations counts only with the status that reports them.
    s.bind(no_integration, enabled_status)
