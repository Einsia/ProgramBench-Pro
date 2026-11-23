"""The public project feeds (Atom activity feed and iCalendar) reached with the project's public-access token, and
what disabling public access does to them."""
import calendar
import re
import xml.etree.ElementTree as ET

from harness import Ref

ATOM = '{http://www.w3.org/2005/Atom}'


def token(c):
    project = c.call('getProjectById', [c.state['p']])
    assert project.get('is_public') and project.get('token'), 'the project has no public-access token'
    c.state['token'] = project['token']
    return project['token']


TASK_LINK = re.compile(r'/task/(\d+)/?$')


def linked_task(c, url):
    """The task a feed links to; the origin and the rest of the URL's form are the deployment's."""
    match = TASK_LINK.search(url or '')
    return c.norm.identity('task', int(match[1])) if match else ('other' if url else None)


def atom(c, response):
    """The feed: title and, per entry, title, author and the linked task; generated times, the HTML content and the
    form of the link URLs excluded."""
    observation = {'http': response.status, 'type': (response.headers.get('content-type') or '').split(';')[0]}
    if response.status != 200:
        return observation
    root = ET.fromstring(response.content)
    assert root.tag == ATOM + 'feed', 'the answer is not an Atom feed'
    entries = []
    for entry in root.findall(ATOM + 'entry'):
        link = entry.find(ATOM + 'link')
        title = entry.findtext(ATOM + 'title') or ''
        entries.append({'title': re.sub(r'#(\d+)', lambda m: '#' + c.norm.identity('task', int(m[1])), title),
                        'author': entry.findtext(ATOM + 'author/' + ATOM + 'name'),
                        'task': linked_task(c, link.get('href') if link is not None else None)})
    observation['feed'] = {'title': root.findtext(ATOM + 'title'), 'entries': entries}
    return observation


def unfold(text):
    return re.sub(r'\r?\n[ \t]', '', text)


def ics_time(value):
    """A DTSTART/DTEND value as a moment (date-only values are midnight UTC)."""
    value = value.split(':', 1)[1] if ':' in value else value
    digits = re.findall(r'\d+', value)
    joined = ''.join(digits)
    if len(joined) < 8:
        return value
    parts = (int(joined[:4]), int(joined[4:6]), int(joined[6:8]), int(joined[8:10] or 0), int(joined[10:12] or 0),
             int(joined[12:14] or 0))
    return {'@moment': calendar.timegm(parts)}


def ical(c, response):
    """The calendar: its name and, per event, summary, start, end, linked task, attendee and organizer names."""
    observation = {'http': response.status, 'type': (response.headers.get('content-type') or '').split(';')[0]}
    if response.status != 200:
        return observation
    text = unfold(response.text)
    assert 'BEGIN:VCALENDAR' in text, 'the answer is not an iCalendar document'
    name = re.search(r'^X-WR-CALNAME:(.*)$', text, re.M)
    events = []
    for block in re.findall(r'BEGIN:VEVENT\r?\n(.*?)END:VEVENT', text, re.S):
        fields = {}
        for line in block.splitlines():
            key, _, value = line.partition(':')
            fields.setdefault(key.split(';')[0], (key, value))
        def value(name):
            return fields[name][1] if name in fields else None

        def param(name, attribute):
            if name not in fields:
                return None
            match = re.search(attribute + r'=("[^"]*"|[^;:]*)', fields[name][0])
            return match[1].strip('"') if match else None
        summary = value('SUMMARY') or ''
        events.append({
            'summary': re.sub(r'#(\d+)', lambda m: '#' + c.norm.identity('task', int(m[1])), summary),
            'start': ics_time(fields['DTSTART'][0] + ':' + fields['DTSTART'][1]) if 'DTSTART' in fields else None,
            'end': ics_time(fields['DTEND'][0] + ':' + fields['DTEND'][1]) if 'DTEND' in fields else None,
            'task': linked_task(c, value('URL')),
            'attendee': param('ATTENDEE', 'CN'), 'organizer': param('ORGANIZER', 'CN')})
    observation['calendar'] = {'name': name[1].strip() if name else None, 'events': {'@unordered': events}}
    return observation


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'user', 'createUser', {'username': 'fay', 'password': 'Feeds-Pass-2026', 'name': 'Fay Feeds'},
       save='fay')
    fx('base', 'project', 'createProject', {'name': 'Feed project'}, save='p')
    fx('base', 'member', 'addProjectUser', [Ref('p'), Ref('fay'), 'project-member'])
    fx('base', 'task-due', 'createTask', {'title': 'Due with time', 'project_id': Ref('p'),
                                          'date_due': '2026-04-21 15:30', 'owner_id': Ref('fay')}, save='t1')
    fx('base', 'task-midnight', 'createTask', {'title': 'Due at midnight', 'project_id': Ref('p'),
                                               'date_due': '2026-04-22 00:00'}, save='t2')
    fx('base', 'task-span', 'createTask', {'title': 'Spans days', 'project_id': Ref('p'),
                                           'date_started': '2026-04-10 08:00', 'date_due': '2026-04-25 17:00'},
       save='t3')
    fx('base', 'task-far', 'createTask', {'title': 'Far future', 'project_id': Ref('p'),
                                          'date_due': '2027-06-01 12:00'})
    fx('base', 'task-past', 'createTask', {'title': 'Long past', 'project_id': Ref('p'),
                                           'date_due': '2026-01-10 12:00'})
    fx('base', 'task-recent', 'createTask', {'title': 'Recently due', 'project_id': Ref('p'),
                                             'date_due': '2026-03-01 09:00'})
    fx('base', 'task-closed', 'createTask', {'title': 'Closed but due', 'project_id': Ref('p'),
                                             'date_due': '2026-04-23 12:00'}, save='t5')
    fx('base', 'close', 'closeTask', [Ref('t5')])
    fx('base', 'task-none', 'createTask', {'title': 'No dates', 'project_id': Ref('p')})
    fx('base', 'comment', 'createComment', {'task_id': Ref('t1'), 'user_id': 1, 'content': 'Feed comment'},
       actor='app')

    def get(path_of, view):
        def action(c):
            response = c.http('GET', path_of(c))
            assert response.status < 500, f'candidate HTTP server error {response.status}'
            return view(c, response)
        return action

    suite.add('feeds', 'feeds', 'atom-before-public', get(lambda c: '/feed/project/0123456789abcdef0123', atom),
              description='GET /feed/project/<unknown token>', requires=['rpc.feeds.feeds.atom'])
    rpc('feeds', 'feeds', 'enable-public', 'enableProjectPublicAccess', [Ref('p')])
    suite.add('feeds', 'feeds', 'atom', get(lambda c: '/feed/project/' + token(c), atom),
              description='GET /feed/project/<token>',
              after=['rpc.feeds.feeds.enable-public'])
    suite.add('feeds', 'feeds', 'ical', get(lambda c: '/ical/project/' + token(c), ical),
              description='GET /ical/project/<token>', after=['rpc.feeds.feeds.enable-public'])
    suite.add('feeds', 'feeds', 'atom-wrong-token', get(lambda c: '/feed/project/' + 'f' * 60, atom),
              description='GET /feed/project/<wrong token>', requires=['rpc.feeds.feeds.atom'])
    suite.add('feeds', 'feeds', 'ical-wrong-token', get(lambda c: '/ical/project/' + 'f' * 60, ical),
              description='GET /ical/project/<wrong token>', requires=['rpc.feeds.feeds.ical'])
    suite.add('feeds', 'feeds', 'user-feed-unknown', get(lambda c: '/feed/user/' + 'e' * 60, atom),
              description='GET /feed/user/<unknown token>', requires=['rpc.feeds.feeds.atom'])
    suite.add('feeds', 'feeds', 'user-ical-unknown', get(lambda c: '/ical/user/' + 'e' * 60, ical),
              description='GET /ical/user/<unknown token>', requires=['rpc.feeds.feeds.ical'])
    rpc('feeds', 'changes', 'more-activity', 'updateTask', {'id': Ref('t2'), 'title': 'Due at midnight (moved)',
                                                            'date_due': '2026-04-24 00:00'},
        after=['rpc.feeds.feeds.atom'])
    suite.add('feeds', 'changes', 'atom-after-update', get(lambda c: '/feed/project/' + c.state['token'], atom),
              description='GET /feed/project/<token> after an update', after=['rpc.feeds.changes.more-activity'])
    suite.add('feeds', 'changes', 'ical-after-update', get(lambda c: '/ical/project/' + c.state['token'], ical),
              description='GET /ical/project/<token> after an update', after=['rpc.feeds.changes.more-activity'])
    rpc('feeds', 'changes', 'disable-public', 'disableProjectPublicAccess', [Ref('p')],
        after=['rpc.feeds.changes.atom-after-update', 'rpc.feeds.changes.ical-after-update'])
    suite.add('feeds', 'changes', 'atom-old-token', get(lambda c: '/feed/project/' + c.state['token'], atom),
              description='GET /feed/project/<former token>', after=['rpc.feeds.changes.disable-public'],
              requires=['rpc.feeds.feeds.atom'])
    suite.add('feeds', 'changes', 'ical-old-token', get(lambda c: '/ical/project/' + c.state['token'], ical),
              description='GET /ical/project/<former token>', after=['rpc.feeds.changes.disable-public'],
              requires=['rpc.feeds.feeds.ical'])
    rpc('feeds', 'changes', 're-enable', 'enableProjectPublicAccess', [Ref('p')],
        after=['rpc.feeds.changes.disable-public'])
    suite.add('feeds', 'changes', 'new-token-differs', lambda c: {
        'changed': c.call('getProjectById', [c.state['p']])['token'] != c.state['token']},
        description='enableProjectPublicAccess draws a new token', after=['rpc.feeds.changes.re-enable'])
