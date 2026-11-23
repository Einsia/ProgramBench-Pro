"""Backend checks and deterministic driving for calcurse .

A backend assertion carries a `check` dict naming what to observe and the projection to compare. Observations come
only through the runtime's channels: calcurse's own files in the home directory (files inspector), the command-line
channel (calcurse's non-interactive options) and a few layout-independent facts of the terminal screen. Every
artifact is observed once per checkpoint and shared by its aspects. Exceptions in a check fail only that point
; a mismatch raises AssertionError (result_mismatch), any other exception is a program_exception.
"""
from __future__ import annotations

import re
from datetime import datetime
from ical_semantics import project_calendar

from harness import Session

DATA = '~/.local/share/calcurse'
CONF = '~/.config/calcurse'


# -- driving -------------------------------------------------------------------------------------------------
def drive(session: Session, steps):
    """Apply a deterministic list of steps to the product through the runtime's GUI/lifecycle operations."""
    for step in steps or []:
        if 'key' in step:
            session.key(step['key'])
        elif 'keys' in step:
            session.keys(step['keys'])
        elif 'type' in step:
            session.type(step['type'])
        elif 'wait' in step:
            session.wait(step['wait'])
        elif 'cli' in step:
            session.last_cli = (list(step['cli']), session.cli(step['cli']))
        elif 'place' in step:
            session.place(step['place'])
        elif 'reset' in step:
            session.reset()
        elif 'restart' in step:
            session.restart()
        else:
            raise ValueError('unknown recipe step: ' + repr(step))


# -- setup (unscored fixture placement) ----------------------------------------------------------------------
def apply_setup(session: Session, item):
    op = item.get('op', 'place')
    if op == 'place':
        session.place(item['files'])
    elif op == 'drive':
        drive(session, item['steps'])
    else:
        raise ValueError('unknown setup op: ' + op)


# -- observation (one full observation per source, cached per checkpoint) ------------------------------------
def source_key(check):
    kind = check['kind']
    if kind == 'file':
        return ('file', check['path'])
    if kind == 'dir':
        return ('dir', check['path'], check.get('contents', False))
    if kind == 'cli':
        return ('cli', tuple(check['args']), check.get('last', False))
    if kind == 'screen':
        return ('screen',)
    raise ValueError('unknown check kind: ' + kind)


def observe(session: Session, check):
    kind = check['kind']
    if kind == 'file':
        return {'path': check['path'], 'text': session.read(check['path'])}
    if kind == 'dir':
        try:
            listing = session.files('list', check['path'])
        except Exception as exc:
            if 'no such' in str(exc):
                return {'path': check['path'], 'entries': None}
            raise
        entries = [e for e in listing['entries']]
        out = {'path': check['path'], 'entries': {}}
        for e in entries:
            value = e['type']
            if check.get('contents') and e['type'] == 'file':
                value = session.read(e['path'])
            out['entries'][e['name']] = value
        return out
    if kind == 'cli':
        if check.get('last'):
            args, result = session.last_cli
            if args != check['args']:
                raise ValueError('last command does not match the requested observation')
            return result
        return session.cli(check['args'])
    if kind == 'screen':
        return session.screen()
    raise ValueError('unknown check kind: ' + kind)


# -- projection (the asserted slice of a full observation) ---------------------------------------------------
# calcurse prefixes its fatal command-line errors with the source location (for example "args.c: 594: "); the
# message after it is the behaviour.
_SOURCE_PREFIX = re.compile(r'^[\w.-]+\.c: \d+: ', re.M)
_PID = re.compile(r'\b(pid:? =? ?)\d+')


def normalize_output(text):
    text = (text or '').replace('\r\n', '\n')
    text = _SOURCE_PREFIX.sub('', text)
    return _PID.sub(lambda m: m.group(1) + '#', text)


def normalize_diagnostic(text):
    text = normalize_output(text)
    # getopt prefixes its message with argv[0], an implementation detail.
    return re.sub(r"^[^\n]+?: (?=(?:unrecognized option|invalid option|option .*(?:requires an argument|is ambiguous|doesn't allow an argument)))",
                  '', text, flags=re.M)


def conf_values(text):
    values = {}
    for line in (text or '').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        values[key.strip()] = value.strip()
    return values


def key_bindings(text):
    bindings = {}
    for line in (text or '').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = line.split()
        bindings[parts[0]] = parts[1:]
    return bindings


def screen_rows(obs):
    return [line.split('|', 1)[1] if '|' in line else line for line in obs.get('screen', [])]


def recurrence_equivalent_line(line):
    """Canonical default limits for GUI D/W/M/Y recurrence, retaining actual restrictions.

    A yearly explicit day with no month expands across months, so it is not
    collapsed to the default anniversary. Defaults are filled only when neither
    a month-day nor a weekday expansion is present.
    """
    match = re.search(r'\{(\d+)([DWMY])(?P<rest>[^{}]*)\}', line)
    if not match:
        return line
    try:
        origin = datetime.strptime(line.split(' ', 1)[0], '%m/%d/%Y')
    except ValueError:
        return line
    rest, period = match.group('rest'), match[2]
    lists = {k: sorted({int(v) for v in re.findall(r'(?<!\S)' + k + r'(-?\d+)(?!\S)', rest)})
             for k in ('d', 'w', 'm')}
    residue = re.sub(r'(?<!\S)[dwm]-?\d+(?!\S)', '', rest)
    if period == 'W' and not lists['w']:
        lists['w'] = [(origin.weekday() + 1) % 7]
    elif period in ('M', 'Y') and not lists['d'] and not lists['w']:
        lists['d'] = [origin.day]
        if period == 'Y' and not lists['m']:
            lists['m'] = [origin.month]
    if period == 'D' and lists['w'] == list(range(7)):
        lists['w'] = []
    if period in ('D', 'W', 'M') and lists['m'] == list(range(1, 13)):
        lists['m'] = []
    rule = ' '.join((match[1] + period + ' ' + residue).split())
    rule += ''.join(' ' + k + str(v) for k, values in lists.items() for v in values)
    return line[:match.start()] + '{' + rule + '}' + line[match.end():]


def project(full, check):
    kind = check['kind']
    if kind == 'file':
        text = full.get('text')
        if check.get('nonempty') and not (text and text.strip()):
            raise AssertionError('the operation did not create the required nonempty data file')
        if check.get('required_line') and check['required_line'] not in (text or '').splitlines():
            raise AssertionError('the saved item does not satisfy the requested state')
        out = {'path': check['path'], 'exists': text is not None}
        mode = check.get('mode', 'lines')
        if text is None or mode == 'exists':
            return out
        if mode == 'lines':
            out['lines'] = sorted(line for line in text.replace('\r\n', '\n').split('\n') if line.strip())
        elif mode == 'recurrence-equivalent':
            out['lines'] = sorted(recurrence_equivalent_line(line) for line in text.replace('\r\n', '\n').split('\n')
                                  if line.strip())
        elif mode == 'ical':
            out['components'] = ical_projection(text, check)
        elif mode == 'ordered':
            out['lines'] = [line for line in text.replace('\r\n', '\n').split('\n') if line.strip()]
        elif mode == 'text':
            out['text'] = text.replace('\r\n', '\n')
        elif mode == 'pcal':
            out['lines'] = [line.rstrip() for line in text.splitlines() if line.strip() and not line.startswith('#')]
            if not out['lines']:
                raise AssertionError('empty pcal export')
        elif mode == 'conf':
            values = conf_values(text)
            out['values'] = {key: values.get(key) for key in check['keys']}
        elif mode == 'keys':
            bindings = key_bindings(text)
            out['bindings'] = {action: sorted(bindings[action]) if action in bindings else None for action in check['actions']}
        elif mode == 'contains':
            out['contains'] = {needle: needle in text for needle in check['needles']}
        else:
            raise ValueError('unknown file mode: ' + mode)
        return out
    if kind == 'dir':
        entries = full.get('entries')
        if entries is None:
            if check.get('nonempty'):
                raise AssertionError('the imported item did not create its required note directory')
            return {'path': check['path'], 'exists': False}
        names = {k: v for k, v in entries.items() if not (check.get('visible') and k.startswith('.'))}
        if check.get('nonempty') and not names:
            raise AssertionError('the imported item did not create its required note')
        if check.get('contents'):
            return {'path': check['path'], 'exists': True, 'entries': names}
        return {'path': check['path'], 'exists': True, 'names': sorted(names)}
    if kind == 'cli':
        part = check.get('part', 'stdout')
        if check.get('success') and (full.get('exit_code') != 0 or full.get('timed_out')):
            raise AssertionError('command did not succeed: ' + normalize_output(full.get('stderr'))[:800])
        if check.get('failure') and (not full.get('exit_code') or full.get('timed_out')):
            raise AssertionError('invalid command was not rejected promptly')
        out = {'args': list(check['args']), 'exit_code': full.get('exit_code')}
        if part in ('stdout', 'all'):
            out['stdout'] = normalize_output(full.get('stdout'))
        if part in ('stderr', 'all'):
            out['stderr'] = normalize_output(full.get('stderr'))
        if part == 'lines':
            out['lines'] = sorted(l for l in normalize_output(full.get('stdout')).split('\n') if l.strip())
        if part == 'error':
            out['diagnostic'] = normalize_diagnostic(full.get('stderr') or full.get('stdout')).strip()
            if not out['diagnostic']:
                raise AssertionError('a rejected command must explain the problem')
        if part == 'ical':
            out['components'] = ical_projection(full.get('stdout', ''), check)
        if full.get('timed_out'):
            out['timed_out'] = True
        return out
    if kind == 'screen':
        rows = screen_rows(full)
        fact = check['fact']
        if fact == 'contains':
            text = '\n'.join(rows)
            found = {needle: needle in text for needle in check['needles']}
            if not all(found.values()):
                raise AssertionError('required visible content is missing: ' + repr([n for n,v in found.items() if not v]))
            return {'fact': fact, 'contains': found}
        if fact == 'process':
            return {'fact': fact, 'process': full.get('process')}
        if fact == 'presence':
            text = '\n'.join(rows)
            present = {needle: needle in text for needle in check.get('present', [])}
            absent = {needle: needle not in text for needle in check.get('absent', [])}
            if not all(present.values()) or not all(absent.values()):
                raise AssertionError('the requested visible state was not reached')
            return {'fact': fact, 'present': present, 'absent': absent}
        raise ValueError('unknown screen fact: ' + fact)
    raise ValueError('unknown check kind: ' + kind)


def ical_projection(text, check):
    return project_calendar(text, check)


def compare(actual, expected):
    if actual != expected:
        raise AssertionError('observation differs from the reference: ' + _first_diff(actual, expected))


def _first_diff(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                return f'{key}: {a.get(key)!r} != {b.get(key)!r}'[:1500]
    return f'{a!r} != {b!r}'[:1500]
