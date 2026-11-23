'''Backend checks and deterministic driving for lazygit .

A backend assertion carries a `check` dict naming what to observe and the projection to compare. Observations come
only through the runtime channels: the git channel (the repository is the observable state of a git client), the
workspace inspector, lazygit's own state file, the clipboard channel, the command-line channel and
layout-independent semantic facts parsed from the terminal screen (harness.Screen). Every artifact is observed once
per checkpoint and shared by its aspects. Exceptions in a check fail only that point ; a mismatch raises
AssertionError (result_mismatch), any other exception is a program_exception.

Projections compare behaviour, never bookkeeping: commit hashes are replaced by labels derived from the commit
subjects, dates are not compared, remote paths are normalised, and the clock-dependent recency column of the side
panels is dropped.
'''
from __future__ import annotations

import re
import time

from harness import Screen, Session

HEX = re.compile('(?<![0-9a-f])[0-9a-f]{7,40}(?![0-9a-f])')
TAB, NL, US = chr(9), chr(10), chr(31)
REPO_PARTS = ('head', 'branches', 'log', 'status', 'stash', 'tags', 'reflog', 'remotes', 'worktrees')
DEFAULT_PARTS = ('head', 'branches', 'log', 'status')


# -- driving ---------------------------------------------------------------------------------------------------
def drive(session: Session, steps):
    '''Apply a deterministic list of steps to the product through the runtime's GUI and lifecycle operations.'''
    for step in steps or []:
        if 'key' in step:
            session.key(step['key'])
        elif 'keys' in step:
            session.keys(step['keys'])
        elif 'type' in step:
            session.type(step['type'])
        elif 'wait' in step:
            session.wait(step['wait'])
        elif 'await_git' in step:
            # A quiet terminal can precede the completion of an asynchronous repository update. Poll only the
            # public read channel, with a bounded deadline; the ordinary assertions still decide success.
            condition = step['await_git']
            deadline = time.monotonic() + condition.get('seconds', 10)
            while True:
                result = session.git(condition['argv'])
                if result['exit_code'] == 0 and result['stdout'] == condition['stdout']:
                    break
                if time.monotonic() >= deadline:
                    break
                session.wait(0.1)
        elif 'setup' in step:
            session.setup(step['setup'])
        elif 'reset' in step:
            session.reset()
        elif 'restart' in step:
            session.restart()
        elif 'resize' in step:
            columns, rows = step['resize']
            session.call({'op': 'resize', 'columns': columns, 'rows': rows})
        else:
            raise ValueError('unknown recipe step: ' + repr(step))


# -- setup (unscored fixture preparation) ----------------------------------------------------------------------
def apply_setup(session: Session, item):
    op = item.get('op', 'steps')
    if op == 'steps':
        session.setup(item['steps'])
    elif op == 'drive':
        drive(session, item['steps'])
    else:
        raise ValueError('unknown setup op: ' + op)


# -- observation (one full observation per source, cached per checkpoint) --------------------------------------
def source_key(check):
    kind = check['kind']
    if kind == 'repo':
        return ('repo', check.get('repo'), check.get('remote'), tuple(check.get('parts') or DEFAULT_PARTS),
                check.get('rev'), bool(check.get('all')))
    if kind == 'git':
        return ('git', tuple(check['argv']), check.get('repo'), check.get('remote'))
    if kind == 'tree':
        return ('tree', check.get('path', '/workspace'), check.get('action', 'tree'))
    if kind in ('state', 'clipboard', 'screen'):
        return (kind,)
    if kind == 'cli':
        return ('cli', check['option'])
    raise ValueError('unknown check kind: ' + kind)


def observe_repo(session, check):
    repo, remote = check.get('repo'), check.get('remote')
    parts = list(check.get('parts') or DEFAULT_PARTS)
    unknown = [p for p in parts if p not in REPO_PARTS]
    if unknown:
        raise ValueError('unknown repository part: ' + ', '.join(unknown))

    def run(*argv):
        result = session.git(list(argv), repo=repo, remote=remote)
        return result['stdout'] if result['exit_code'] == 0 else ''
    out = {}
    for part in parts:
        if part == 'head':
            name = run('branch', '--show-current').strip()
            out['head'] = [name, '' if name else run('log', '-1', '--format=%s').strip()]
        elif part == 'branches':
            out['branches'] = run('for-each-ref', '--format=%(refname:short)%09%(contents:subject)%09%(upstream:short)%09%(upstream:track)', 'refs/heads')
        elif part == 'log':
            revs = ['--all'] if check.get('all') else [check.get('rev', 'HEAD')]
            out['log'] = run('log', '--format=%H%x1f%P%x1f%an%x1f%s', *revs)
        elif part == 'status':
            out['status'] = run('status', '--porcelain', '-uall')
        elif part == 'stash':
            out['stash'] = run('stash', 'list', '--format=%gs')
        elif part == 'tags':
            out['tags'] = run('for-each-ref', '--format=%(refname:short)%09%(objecttype)%09%(contents:subject)', 'refs/tags')
        elif part == 'reflog':
            out['reflog'] = run('reflog', 'show', '--format=%gs', check.get('rev', 'HEAD'))
        elif part == 'remotes':
            out['remotes'] = run('remote', '-v')
        elif part == 'worktrees':
            out['worktrees'] = run('worktree', 'list', '--porcelain')
    return out


def observe(session: Session, check):
    kind = check['kind']
    if kind == 'repo':
        return observe_repo(session, check)
    if kind == 'git':
        result = session.git(check['argv'], repo=check.get('repo'), remote=check.get('remote'))
        return {'exit_code': result['exit_code'], 'stdout': result['stdout']}
    if kind == 'tree':
        return session.workspace(check.get('action', 'tree'), check.get('path', '/workspace'))
    if kind == 'state':
        return session.state()
    if kind == 'clipboard':
        return session.clipboard()
    if kind == 'cli':
        return session.cli(check['option'])
    if kind == 'screen':
        return session.screen()
    raise ValueError('unknown check kind: ' + kind)


# -- projection (the asserted slice of a full observation) -----------------------------------------------------
def scrub(text):
    '''Object names and the private remote location never take part in a comparison.'''
    return HEX.sub('<sha>', text).replace('[data]/remotes/', '@remotes/')


def lines_of(text, ordered=False):
    rows = [scrub(line) for line in text.splitlines() if line.strip()]
    return rows if ordered else sorted(rows)


def labels(pairs):
    '''Commit labels from the subjects: the newest commit of a subject keeps it, older ones get #2, #3.'''
    seen, out = {}, {}
    for sha, subject in pairs:
        count = seen.get(subject, 0) + 1
        seen[subject] = count
        out[sha] = subject if count == 1 else '%s#%d' % (subject, count)
    return out


def project_log(text, with_author):
    commits = [line.split(US) for line in text.splitlines() if line]
    names = labels([(c[0], c[3]) for c in commits])
    rows = []
    for c in commits:
        row = {'subject': c[3], 'parents': [names.get(p, '<unlisted>') for p in c[1].split()]}
        if with_author:
            row['author'] = c[2]
        rows.append(row)
    return rows


def project_repo(full, check):
    out = {}
    for part in check.get('parts') or DEFAULT_PARTS:
        text = full[part]
        if part == 'head':
            out['head'] = text
        elif part == 'branches':
            out['branches'] = sorted(line.split(TAB) for line in text.splitlines() if line)
        elif part == 'log':
            out['log'] = project_log(text, check.get('author'))
        elif part == 'status':
            out['status'] = lines_of(text)
        elif part == 'stash':
            out['stash'] = lines_of(text, ordered=True)
        elif part == 'tags':
            out['tags'] = sorted(line.split(TAB) for line in text.splitlines() if line)
        elif part == 'reflog':
            out['reflog'] = lines_of(text, ordered=True)
        elif part == 'remotes':
            out['remotes'] = lines_of(text)
        elif part == 'worktrees':
            out['worktrees'] = sorted(scrub(line) for line in text.splitlines() if line.startswith(('worktree ', 'branch ', 'detached', 'bare')))
    return out


def norm_item(number, item):
    '''One panel line without the clock-dependent column, hashes and author initials.'''
    text = item.rstrip()
    if number == 2:
        return text
    text = ' '.join(text.split())
    if number == 3:
        current = text.startswith('*')
        return ('* ' if current else '') + text.lstrip('*~ ').strip()
    if number == 4:
        stripped = re.sub('^[0-9a-f]{7,40} [^ ]+ [^ ] ', '', text)
        return stripped if stripped != text else re.sub('^[0-9a-f]{7,40} ', '', text)
    if number == 5:
        return re.sub('^[~ ]+', '', text)
    return text


def screen_fact(screen, check):
    fact = check['fact']
    if fact == 'panel':
        number, field = check['number'], check.get('field', 'items')
        panel = screen.panel(number)
        if panel is None:
            return {'fact': fact, 'number': number, 'value': None}
        if field == 'items':
            value = [norm_item(number, i) for i in panel['items']]
        elif field == 'selected':
            index = panel['selected']
            value = norm_item(number, panel['items'][index]) if index is not None else None
        elif field == 'position':
            value = panel['position']
        else:
            raise ValueError('unknown panel field: ' + repr(field))
        return {'fact': fact, 'number': number, 'field': field, 'value': value}
    if fact == 'focus':
        return {'fact': fact, 'focus': screen.focus()}
    if fact == 'visible-panels':
        return {'fact': fact, 'panels': sorted(screen.views)}
    if fact == 'popup':
        return {'fact': fact, 'titles': [b['title'] for b in screen.popups], 'text': scrub(screen.popup_text())}
    if fact == 'main':
        text = scrub(screen.main_text())
        limit = check.get('lines')
        return {'fact': fact, 'title': screen.main_title(), 'text': NL.join(text.splitlines()[:limit]) if limit else text}
    if fact == 'commit-subject':
        # The commit header in the main view carries the complete subject independently of list column widths.
        match = re.search(r'\n\s*\n {4}(\S[^\n]*)', screen.main_text())
        return {'fact': fact, 'subject': match.group(1).strip() if match else None}
    if fact == 'diff-hunks':
        return {'fact': fact, 'hunks': re.findall(r'@@[^\n]*?@@', screen.main_text())}
    if fact == 'diff-changes':
        return {'fact': fact, 'lines': [line.rstrip() for line in screen.main_lines()
                                      if line.startswith(('+', '-')) and not line.startswith(('+++', '---'))]}
    if fact == 'diff-summary':
        return {'fact': fact, 'summary': next((line.strip() for line in screen.main_lines()
                                               if re.search(r'\d+ files? changed', line)), None)}
    if fact == 'hints':
        return {'fact': fact, 'hints': screen.hints()}
    if fact == 'banner':
        return {'fact': fact, 'banner': screen.banner()}
    raise ValueError('unknown screen fact: ' + fact)


def project(full, check):
    kind = check['kind']
    if kind == 'repo':
        return project_repo(full, check)
    if kind == 'git':
        return {'exit_code': full['exit_code'], 'stdout': scrub(full['stdout'])}
    if kind == 'tree':
        fields = set(check.get('fields', ['size', 'sha256', 'target']))
        recursive = check.get('action', 'tree') == 'tree'
        key = 'path' if recursive else 'name'
        entries = []
        for e in full['entries']:
            row = {'name': e.get(key), 'type': e['type']}
            for field in ('size', 'sha256', 'mode'):
                if field in fields and (field == 'mode' or e['type'] == 'file'):
                    row[field] = e.get(field)
            if 'target' in fields and e['type'] == 'symlink':
                row['target'] = e.get('target')
            entries.append(row)
        if check.get('names_only'):
            return {'path': full.get('path'), 'names': [e['name'] for e in entries]}
        return {'path': full.get('path'), 'entries': entries}
    if kind == 'state':
        if check.get('field') == 'hidecommandlog':
            match = re.search(r'^hidecommandlog: (true|false)$', full.get('text', ''), re.MULTILINE)
            return {'field': 'hidecommandlog', 'value': match.group(1) == 'true' if match else None}
        return {'exists': full.get('exists'), 'recent': [line.strip(' -') for line in full.get('text', '').splitlines() if line.startswith('    - ')]}
    if kind == 'clipboard':
        out = {'text': scrub(full['text']) if check.get('scrub') and full.get('text') else full.get('text')}
        if check.get('count', True):
            out['copies'] = full.get('copies')
        return out
    if kind == 'cli':
        out = full.get('stdout', '')
        if check['option'] == '--version':
            fields = dict(part.split('=', 1) for part in out.strip().split(', ') if '=' in part)
            return {'option': check['option'], 'version': fields.get('version')}
        return {'option': check['option'], 'exit_code': full.get('exit_code'), 'stdout': out}
    if kind == 'screen':
        return screen_fact(full if isinstance(full, Screen) else Screen(full), check)
    raise ValueError('unknown check kind: ' + kind)


def compare(actual, expected):
    if actual != expected:
        raise AssertionError('observation differs from the reference: ' + _first_diff(actual, expected))


def _first_diff(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                return f'{key}: {a.get(key)!r} != {b.get(key)!r}'
    return f'{a!r} != {b!r}'
