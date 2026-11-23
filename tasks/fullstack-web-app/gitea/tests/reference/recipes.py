"""Pinned-standard GUI implementation of the reviewed goals, through the black-box runtime (record only).

The recipes drive the standard answer with the same runtime GUI operations that
the evaluator and the model use; BrokerSurface.observe() captures the reference
evidence. Control names, form fields and routes below belong to the pinned
standard only; they are never a candidate requirement. API reads only confirm
that a browser mutation was saved before the evidence is taken.
"""
import re
import time
import urllib.parse

from checks import resolve
from harness import CREDS
from .ui import UI, accessible


def corroborate(c, path, predicate, actor='alice', timeout=10.0, what='browser mutation not saved'):
    """Wait until the product reports the browser mutation through its public API."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        r, p = c.request('GET', path, actor)
        last = (r.status_code, p)
        try:
            if r.status_code == 200 and predicate(p):
                return p
        except (KeyError, TypeError, IndexError):
            pass
        time.sleep(0.2)
    raise AssertionError(what + ': ' + str(last)[:400])


def settle_commits(ui, total, timeout=20.0):
    """The repository page's commit counter is refreshed asynchronously after a commit; wait until it shows the
    branch's known commit total so the evidence does not depend on that timing."""
    deadline = time.monotonic() + timeout
    while True:
        shown = re.search(r'(\d+)\nCommits?\b', ui.snapshot()['text'])
        if not shown or shown.group(1) == str(total):
            return
        assert time.monotonic() < deadline, 'repository commit counter did not settle'
        time.sleep(0.5)
        ui.reload()


def languages(c):
    r, p = c.request('GET', 'repos/alice/workbench/languages', 'alice')
    return p if r.status_code == 200 else None


def settle_languages(c, before, quiet=10.0):
    """Gitea recomputes a repository's language statistics asynchronously, a few seconds after a commit (the
    repository page shows them as a bar). Wait until they differ from their value before the file operation, or
    until they stayed unchanged for `quiet` seconds (an operation on a file that is not counted), so the evidence
    does not depend on that timing."""
    deadline = time.monotonic() + quiet
    while time.monotonic() < deadline:
        if languages(c) != before:
            return
        time.sleep(0.5)


def choose(ui, labels, option):
    """Select an option of a Fomantic dropdown (combobox/menu) or a native select by its visible text."""
    control = ui.find(labels=labels, tags=('select',))
    if control:
        ui.call('select', target={'ref': control['ref']}, value=option)
        return
    raise AssertionError('choice control missing: ' + str(labels))


def radio(ui, name, value):
    """Check the radio of a form field with the given value (radio inputs carry name and value)."""
    snap = ui.snapshot()
    for control in snap['controls']:
        if control.get('type') == 'radio' and control.get('name') == name and control.get('value') == value:
            ui.call('check', target={'ref': control['ref']}, checked=True)
            return
    raise AssertionError('radio choice missing: ' + name + '=' + value)


def review(ui, c, number, event, body):
    route = '/alice/workbench/pulls/' + str(number)
    ui.goto(route + '/files')
    ui.click('Review', 'Review changes', 'Submit review')
    ui.wait(lambda s: any(c['tag'] == 'textarea' and c.get('name') == 'content' and not c.get('offscreen')
                          for c in s['controls']), 'review form did not open')
    ui.fill('content', body)
    ui.click('Approve' if event == 'APPROVED' else 'Request changes')
    corroborate(c, 'repos/alice/workbench/pulls/' + str(number) + '/reviews',
                lambda xs: any(x['state'] == event and x['body'] == body for x in xs), what='review not saved')
    ui.goto(route)
    ui.require(body)


def merge(ui, c, number):
    endpoint = 'repos/alice/workbench/pulls/' + str(number)
    c.pull_ready(endpoint, True)
    route = '/alice/workbench/pulls/' + str(number)
    ui.goto(route)
    # The merge box first offers the default style; its button opens the commit form with a confirmation.
    ui.click('Create merge commit')
    ui.wait(lambda s: sum(1 for x in s['controls'] if any(re.fullmatch(r'Create merge commit', n, re.I)
                                                          for n in accessible(x))) >= 1, 'merge form missing')
    snap = ui.snapshot()
    confirm = [x for x in snap['controls'] if x.get('type') == 'submit' or x['tag'] == 'button'
               if any(re.fullmatch(r'Create merge commit', n, re.I) for n in accessible(x)) and not x.get('disabled')]
    ui.click_ref(confirm[-1])
    corroborate(c, endpoint, lambda p: p['merged'] and p['state'] == 'closed', what='merge not saved')
    # The page reloads itself once the merge request returns; let that finish before opening the page again.
    ui.call('wait', seconds=2)
    ui.goto(route)
    ui.require('Merged')


def delete_package_version(ui, c):
    ui.goto('/alice/-/packages/generic/pbp-generic/2.0.0-rc.1/settings')
    ui.click('Delete package', 'Delete package version', 'Delete Version')
    ui.wait(lambda s: any(any(re.fullmatch(r'Yes|Confirm|Delete', n, re.I) for n in accessible(x))
                          and not x.get('offscreen') for x in s['controls'] if x['tag'] == 'button'),
            'deletion confirmation missing')
    snap = ui.snapshot()
    modal = [x for x in snap['controls'] if x['tag'] == 'button' and not x.get('offscreen')
             and any(re.fullmatch(r'Yes|Confirm', n, re.I) for n in accessible(x))]
    ui.click_ref(modal[-1])
    corroborate(c, 'packages/alice/generic/pbp-generic/1.0.0', lambda p: True)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        r, _ = c.request('GET', 'packages/alice/generic/pbp-generic/2.0.0-rc.1', 'alice')
        if r.status_code == 404:
            break
        time.sleep(0.2)
    else:
        raise AssertionError('browser deletion did not persist')
    ui.goto('/alice/-/packages/generic/pbp-generic/1.0.0')


def execute(ctx, c, checkpoint):
    episode = ctx.episode
    actor = episode.get('actor')
    ui = ctx.state.setdefault('ui', UI(ctx.broker))
    if actor and not ctx.state.get('signed_in'):
        ui.sign_in(actor, CREDS[actor])
        ctx.state['signed_in'] = True
    for raw in checkpoint['recipe']:
        a = resolve(raw, c.state)
        op = a['op']
        if op == 'goto':
            ui.goto(a['path'])
        elif op == 'reload':
            ui.reload()
        elif op == 'click':
            ui.click(*a['names'])
        elif op == 'login-test':
            ui.goto('/user/login')
            ui.fill('user_name', a['username'])
            ui.fill('password', a['password'])
            ui.submit('Sign In')
            ui.goto('/user/settings')
            assert (ui.url.split('?')[0] != '/user/login') == a['valid'], 'sign-in outcome differs: ' + ui.url
        elif op == 'register':
            ui.goto('/user/sign_up')
            for name, value in [('user_name', a['name']), ('email', a['email']), ('password', a['password']),
                                ('retype', a['password'])]:
                ui.fill(name, value)
            ui.submit('Register Account')
            if a['valid']:
                ui.goto('/user/settings')
                assert not ui.url.startswith('/user/login'), 'registration did not sign in'
            else:
                assert any(x in ui.text().lower() for x in ('already', 'taken', 'exist')), 'no duplicate feedback'
        elif op == 'create-repo':
            ui.goto('/repo/create')
            for name, value in [('repo_name', a['name']), ('description', a['description']),
                                ('default_branch', a['default_branch'])]:
                ui.fill(name, value)
            for name, value in [('private', a['private']), ('auto_init', not a['empty']), ('template', a['template'])]:
                ui.check(name, value)
            ui.submit('Create Repository')
            ui.wait(lambda s: s['url'].split('?')[0] == '/alice/' + a['name'], 'repository page not opened')
        elif op == 'create-issue':
            ui.goto('/alice/workbench/issues/new')
            ui.fill('title', a['title'])
            ui.fill('content', a['body'])
            ui.submit('Create Issue')
            ui.wait(lambda s: re.search(r'/issues/\d+$', s['url']), 'issue page not opened')
        elif op == 'comment':
            ui.fill('content', a['body'])
            ui.click('Comment')
            ui.reload()
            ui.require(a['body'])
        elif op == 'title':
            ui.click('Edit')
            field = ui.wait(lambda s: next((x for x in s['controls'] if x['tag'] == 'input' and x.get('value') == a['old']
                                            and not x.get('offscreen')), None), 'title editor did not open')
            ui.call('fill', target={'ref': field['ref']}, value=a['value'])
            ui.click('Save')
            ui.require(a['value'])
            ui.reload()
        elif op == 'label':
            ui.goto('/alice/workbench/labels')
            ui.click('New Label')
            ui.wait(lambda s: any(x.get('name') == 'title' and not x.get('offscreen') for x in s['controls']),
                    'label form did not open')
            ui.fill('title', a['title'])
            ui.fill('description', a['description'])
            ui.fill('color', a['color'])
            ui.submit('Create Label')
            ui.reload()
        elif op == 'milestone':
            ui.goto('/alice/workbench/milestones/new')
            ui.fill('title', a['title'])
            ui.fill('content', a['description'])
            ui.fill('deadline', a['date'])
            ui.submit('Create Milestone')
            ui.reload()
        elif op == 'milestone-edit':
            ui.goto('/alice/workbench/milestones/' + str(c.state['milestone']['id']) + '/edit')
            ui.fill('title', a['title'])
            ui.fill('content', a['description'])
            ui.submit('Save Changes', 'Update Milestone')
        elif op.startswith('file-'):
            route = {'file-create': '_new', 'file-edit': '_edit', 'file-delete': '_delete'}[op]
            path = '/alice/workbench/' + route + '/main' + ('/' + urllib.parse.quote(a['path'], safe='/')
                                                           if op != 'file-create' else '')
            stats = languages(c)
            ui.goto(path)
            if op == 'file-create':
                name = ui.wait(lambda s: next((x for x in s['controls'] if x['tag'] == 'input'
                                               and x.get('placeholder', '').startswith('Name your file')), None),
                               'file name field missing')
                ui.call('fill', target={'ref': name['ref']}, value=a['path'])
            if op != 'file-delete':
                ui.editor(a['content'])
            ui.fill('commit_summary', a['message'])
            ui.submit('Commit Changes', 'Delete File')
            ui.wait(lambda s: '/_new/' not in s['url'] and '/_edit/' not in s['url'] and '/_delete/' not in s['url'],
                    'commit did not complete')
            settle_languages(c, stats)
            ui.reload()
            # The setup repository starts with its initial commit; every file operation adds one.
            ctx.state['commits'] = ctx.state.get('commits', 1) + 1
            settle_commits(ui, ctx.state['commits'])
        elif op == 'release':
            ui.goto('/alice/workbench/releases/new')
            ui.fill('tag_name', a['tag'])
            ui.fill('title', a['title'])
            ui.fill('content', a['body'])
            ui.check('prerelease', a['prerelease'])
            ui.submit('Save Draft' if a['draft'] else 'Publish Release')
            ui.wait(lambda s: not s['url'].endswith('/releases/new'), 'release not saved')
            ui.reload()
        elif op in {'wiki-create', 'wiki-edit'}:
            ui.goto('/alice/workbench/wiki' + ('?action=_new' if op == 'wiki-create' else '/Home?action=_edit'))
            if op == 'wiki-create':
                ui.fill('title', a['title'])
            ui.fill('content', a['content'])
            ui.fill('message', a['message'])
            ui.submit('Save Page')
            ui.wait(lambda s: 'action=' not in s['url'], 'wiki page not saved')
            ui.reload()
        elif op == 'wiki-history':
            snap = ui.snapshot()
            link = next((x for x in snap['controls'] if x['tag'] == 'a' and re.search(r'/wiki/[^/]+\?action=_revision$',
                                                                                     x.get('href', ''))), None)
            assert link, 'wiki revision history link missing'
            ui.click_ref(link)
            ui.require('Create wiki', 'Update wiki')
        elif op == 'organization':
            ui.goto('/org/create')
            ui.fill('org_name', a['name'])
            radio(ui, 'visibility', {'public': '0', 'limited': '1', 'private': '2'}[a['visibility']])
            ui.submit('Create Organization')
            ui.wait(lambda s: s['url'].split('?')[0] in ('/' + a['name'], '/org/' + a['name'] + '/dashboard'),
                    'organization page not opened')
        elif op == 'team':
            ui.goto('/org/web-team-org/teams/new')
            ui.fill('team_name', a['name'])
            ui.fill('description', 'Team responsibilities')
            radio(ui, 'repo_access', 'specific')
            radio(ui, 'permission', 'admin' if a['admin'] else 'read')
            ui.check('can_create_org_repo', False)
            ui.submit('Create Team')
            ui.wait(lambda s: s['url'].startswith('/org/web-team-org/teams/' + a['name']), 'team page not opened')
        elif op in {'profile', 'repo-settings'}:
            ui.goto('/user/settings' if op == 'profile' else '/alice/workbench/settings')
            for field, value in a['fields'].items():
                ui.fill(field, value)
            ui.submit('Update Profile' if op == 'profile' else 'Update Settings')
            ui.reload()
        elif op == 'wiki-branch':
            ui.goto('/alice/pbp-publish/settings')
            ui.fill('default_wiki_branch', 'master')
            field = ui.field('default_wiki_branch')
            # The field belongs to the first settings form; its submit button is the next "Update Settings".
            buttons = [x for x in ui.snap['controls'] if x['tag'] == 'button' and 'Update Settings' in accessible(x)
                       and x['bounds'][1] > field['bounds'][1]]
            assert buttons, 'settings submit missing'
            ui.click_ref(min(buttons, key=lambda x: x['bounds'][1]))
            ui.reload()
            field = ui.field('default_wiki_branch')
            assert field.get('value') == 'master', 'wiki branch not saved'
            # Bring the saved setting into the evidence viewport.
            ui.call('scroll', delta_y=max(0, field['bounds'][1] - 300))
        elif op == 'review':
            review(ui, c, c.state['pull']['number'], a['event'], a['body'])
        elif op == 'merge':
            merge(ui, c, c.state['pull']['number'])
        elif op == 'package-delete':
            delete_package_version(ui, c)
        else:
            raise ValueError('unknown reference operation ' + op)
    for text in checkpoint.get('visible', []):
        ui.require(resolve(text, c.state))
    time.sleep(0.2)
