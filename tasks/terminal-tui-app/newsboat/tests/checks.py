"""Backend checks and deterministic driving for Newsboat.

A backend assertion carries a `check` dict naming what to observe and the projection to compare. Observations
come only through the runtime's channels: the home-directory inspector (the urls file, saved articles, dumped
configurations, the podcast queue, the history files, exported files), the SQLite cache tables, the command line,
and facts parsed from the terminal screen (harness.Screen). Every source is observed once per checkpoint and
shared by its aspects. Exceptions in a check fail only that point; a mismatch raises AssertionError
(result_mismatch), any other exception is a program_exception.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from harness import Screen, Session


# -- driving -------------------------------------------------------------------------------------------------
def drive(session: Session, steps):
    """Apply a deterministic list of steps through the runtime's GUI and lifecycle operations."""
    for step in steps or []:
        if 'reset' in step:
            session.call({'op': 'reset'})
        elif 'resize' in step:
            session.call({'op': 'resize', **step['resize']})
        elif 'key' in step:
            session.key(step['key'])
        elif 'keys' in step:
            session.keys(step['keys'])
        elif 'type' in step:
            session.type(step['type'])
        elif 'cmd' in step:
            session.key(':')
            session.type(step['cmd'])
            session.key('Enter')
        elif 'prompt' in step:
            if step['prompt']:
                session.type(step['prompt'])
            session.key('Enter')
        elif 'wait' in step:
            session.wait(step['wait'])
        elif 'place' in step:
            session.place(step['place'])
        elif 'update_inputs' in step:
            session.call({'op':'update_inputs','files':step['update_inputs']})
        elif 'http_source' in step:
            session.call({'op':'http_source','routes':step['http_source']})
        elif 'restart' in step:
            result=session.restart(step['restart'] if isinstance(step['restart'], list) else None)
            if not result.get('ready'):
                raise AssertionError('the application did not become ready after restart: '+str(result.get('detail')))
        elif 'cli' in step:
            result=session.cli(step['cli'])
            if result.get('exit_code') != 0 and not step.get('allow_error'):
                raise AssertionError('preparation command failed: '+str(result.get('stderr',''))[:500])
        elif 'expect' in step:
            check = step['expect']
            project(observe(session, check), check)
        else:
            raise ValueError('unknown recipe step: ' + repr(step))


def apply_setup(session: Session, item):
    op = item.get('op', 'place')
    if op == 'place':
        result = session.place(item['files'])
        if not result.get('ready'):
            raise AssertionError('the application is not ready after placing the setup files: '
                                 + str(result.get('detail')))
    elif op == 'drive':
        drive(session, item['steps'])
    else:
        raise ValueError('unknown setup op: ' + op)


# -- observation ---------------------------------------------------------------------------------------------
def source_key(check):
    kind = check['kind']
    if kind == 'screen':
        return ('screen',)
    if kind == 'cache':
        return ('cache', check['table'])
    if kind == 'file':
        return ('file', check['path'])
    if kind == 'dir':
        return ('dir', check['path'])
    if kind == 'cli':
        return ('cli', tuple(check['args']))
    if kind == 'http_requests':return ('http_requests',)
    raise ValueError('unknown check kind: ' + kind)


def observe(session: Session, check):
    kind = check['kind']
    if kind == 'screen':
        return session.screen()
    if kind == 'cache':
        return session.cache(check['table'])
    if kind == 'file':
        try:
            return session.home('read', check['path'])
        except Exception as exc:  # an absent file is an observation, not an error
            if 'no such' in str(exc):
                return None
            raise
    if kind == 'dir':
        return session.home('list', check['path'])
    if kind == 'cli':
        return session.cli(check['args'])
    if kind == 'http_requests':return session.call({'op':'http_requests'})
    raise ValueError('unknown check kind: ' + kind)


# -- projection ----------------------------------------------------------------------------------------------
def _lines(text, *, strip=True, drop_blank=True):
    out = []
    for line in (text or '').splitlines():
        line = line.rstrip() if strip else line
        if drop_blank and not line.strip():
            continue
        out.append(line)
    return out


def _opml(text):
    """Subscription outline tree in document order, without descriptive document-title wording.
    Raises AssertionError when the text is not OPML (a candidate defect)."""
    try:
        root = ET.fromstring(text.encode('utf-8') if isinstance(text, str) else text)
    except ET.ParseError as exc:
        raise AssertionError(f'not an XML document: {exc}') from None
    if root.tag != 'opml':
        raise AssertionError('the document element is not <opml>')
    body = root.find('body')
    outlines = []

    def walk(node, depth):
        for child in node:
            if child.tag == 'outline':
                attrs = {k:v for k,v in child.attrib.items() if k in ('type','text','title','xmlUrl','htmlUrl','category')}
                if 'category' in attrs:
                    attrs['category'] = ','.join(sorted(x.strip() for x in attrs['category'].split(',')))
                outlines.append([depth, sorted([k,v] for k,v in attrs.items())])
                walk(child, depth + 1)
    if body is not None:
        walk(body, 0)
    return {'version': root.get('version'), 'outlines': outlines}


def _rows_of(table, columns, where):
    if not table.get('exists'):
        raise AssertionError('the application cache table is missing')
    names = table['columns']
    missing = [c for c in columns + list(where) if c not in names]
    if missing:
        raise AssertionError('the cache table has no column ' + ', '.join(missing))
    index = {c: names.index(c) for c in names}
    rows = []
    for row in table['rows']:
        if all(row[index[c]] == v for c, v in where.items()):
            rows.append(['' if row[index[c]] is None and c=='flags' else row[index[c]] for c in columns])
    return sorted(rows, key=lambda r: [str(v) for v in r])


def project(full, check):
    value = _project(full, check)
    if check.get('nonempty') and not any(value.values()):
        raise AssertionError('the required observation is empty')
    if 'expected' in check and value != check['expected']:
        raise AssertionError('the authored behavioral invariant failed: ' + _first_diff(value, check['expected']))
    return value


def _project(full, check):
    kind = check['kind']
    if kind=='http_requests':
        rows=full['requests']
        if 'path' in check:rows=[r for r in rows if r['path']==check['path']]
        if check.get('headers'):
            rows=[dict(r,headers={k:r['headers'].get(k) for k in check['headers']}) for r in rows]
        return {'requests':[{k:r.get(k) for k in check.get('fields',['path','method','status'])} for r in rows]}
    if kind == 'screen':
        screen = full if isinstance(full, Screen) else Screen(full)
        fact = check['fact']
        if fact != 'exited':
            if screen.process != 'running':
                if not (check.get('after_exit') and screen.process=='exited with status 0'):
                    raise AssertionError('the application is not running for this screen observation')
            elif not any(row.strip() for row in screen.all_text()):
                raise AssertionError('the application has not drawn a usable screen')
        if check.get('view'):
            screen.require_view(check['view'])
        if fact == 'title':
            return {'title': screen.title()}
        if fact == 'title-parts':
            title=screen.title()
            found=[];offset=0
            for part in check['parts']:
                position=title.find(part,offset)
                if position<0:break
                found.append(part);offset=position+len(part)
            return {'parts':found}
        if fact == 'message':
            return {'message': screen.message()}
        if fact == 'hints':
            return {'hints': screen.hints()}
        if fact == 'body':
            return {'body': screen.body()}
        if fact == 'lines':
            rows = screen.body()
            return {'lines': rows[check.get('start', 0):check.get('stop')]}
        if fact == 'labels':
            if not screen.body() or not screen.labels(check['labels']):
                screen.require_view(check.get('view','list'))
            values = screen.labels(check['labels'])
            for tied in check.get('ties', []):
                indices = [i for i,v in enumerate(values) if v in tied]
                if indices and indices == list(range(indices[0], indices[-1]+1)):
                    values[indices[0]:indices[-1]+1] = sorted(values[i] for i in indices)
            return {'labels': sorted(values) if check.get('unordered') else values}
        if fact == 'focus':
            return {'focus': screen.focus(check['labels'])}
        if fact == 'counts':
            return {'counts': screen.counts(check['labels'])}
        if fact == 'tag-counts':
            result = {}
            for row in screen.body():
                label = screen.label_of(row, check['labels'])
                if label is None:
                    continue
                values = []
                for term in ('feeds', 'articles'):
                    found = re.search(r'\b'+term+r'\s*[:=]?\s*(\d+)\b',row,re.I)
                    reverse = re.search(r'\b(\d+)\s*'+term+r'\b',row,re.I)
                    values.append(int((found or reverse).group(1)) if (found or reverse) else None)
                if None not in values:
                    result[label] = values
            return {'counts': result}
        if fact == 'row-token':
            return {'visible': any(check['label'] in row and re.search(r'(?<!\w)'+re.escape(check['token'])+r'(?!\w)',row)
                                   for row in screen.body())}
        if fact == 'styled':
            return {'styled': screen.styled(check['pattern'])}
        if fact == 'exited':
            return {'exited': screen.exited()}
        if fact == 'contains':
            text = '\n'.join(screen.all_text())
            return {'contains': [needle for needle in check['needles'] if needle in text]}
        if fact == 'matches':
            return {'matches': re.findall(check['pattern'], '\n'.join(screen.all_text()))}
        if fact == 'style-flags':
            styles = [set(s.get('style',[])) for s in screen.styles if re.search(check['pattern'], s.get('text',''))]
            return {'attributes': [a for a in check['attributes'] if any(a in s for s in styles)]}
        if fact == 'bars':
            return {'title_visible': any('Newsboat' in row for row in screen.all_text()),
                    'hints_visible': any('q:Quit' in row for row in screen.all_text()),
                    'top_is_title': 'Newsboat' in screen.title(), 'top_is_hints': 'q:Quit' in screen.title()}
        if fact == 'help-actions':
            rows=[line.strip() for line in screen.body() if line.strip() and not line.strip().endswith(':')]
            matches=[line for line in rows if check['query'].lower() in line.lower()]
            if not matches or len(matches)!=len(rows):
                raise AssertionError('the help list is not filtered to the requested actions')
            return {'actions': sorted(set(re.findall(r'\b(?:reload(?:-[a-z]+)*)\b','\n'.join(matches))))}
        if fact == 'right-aligned':
            result={}
            for row in screen.body():
                label=screen.label_of(row,check['labels'])
                if label is not None:
                    result[label]=[row.startswith(check['left']),row.endswith(check['right']),
                                   len(row.rstrip())==screen.width]
            return {'aligned':result}
        if fact == 'line-widths':
            return {'widths':[len(line.rstrip()) for line in screen.body() if line.strip() and line.strip()!='~']}
        raise ValueError('unknown screen fact: ' + fact)
    if kind == 'cache':
        return {'rows': _rows_of(full, list(check['columns']), dict(check.get('where') or {}))}
    if kind == 'file':
        if full is None:
            if check.get('absent'):
                return {'exists': False}
            raise AssertionError('the expected application output file is missing')
        text = full.get('text', '')
        mode = check.get('mode', 'lines')
        if mode == 'contains':
            return {'contains': [n for n in check['needles'] if n in text]}
        if mode == 'config':
            import shlex
            rows = [shlex.split(ln, comments=True) for ln in text.splitlines()]
            rows = [row[1:] for row in rows if row and row[0] == check['name']]
            if not rows:
                raise AssertionError('setting absent from configuration export: ' + check['name'])
            if any(len(row)!=1 for row in rows):
                raise AssertionError('configuration setting must have exactly one value: '+check['name'])
            if check.get('value_type') == 'bool':
                allowed = {'yes': True, 'true': True, 'no': False, 'false': False}
                converted = []
                for row in rows:
                    values = []
                    for value in row:
                        if value.lower() not in allowed:
                            raise AssertionError('invalid Boolean value in configuration export: ' + value)
                        values.append(allowed[value.lower()])
                    converted.append(values)
                rows = converted
            if check.get('value_type') == 'int':
                rows = [[int(v) for v in row] for row in rows]
            return {'values': rows}
        if mode == 'urls':
            import shlex
            rows = [shlex.split(ln, comments=True) for ln in text.splitlines()]
            return {'urls': sorted([row[0], sorted(row[1:])] for row in rows if row)}
        if mode == 'words':
            return {'words': text.split()}
        if mode == 'body-layout':
            parts = re.split(r'\n[ \t]*\n', text, maxsplit=1)
            body = parts[1] if len(parts)>1 else ''
            if not body.strip():
                raise AssertionError('the exported article has no body')
            return {'body': [line.rstrip() for line in body.rstrip().splitlines()]}
        if mode == 'body-widths':
            parts=re.split(r'\n[ \t]*\n',text,maxsplit=1)
            if len(parts)!=2 or not parts[1].strip():raise AssertionError('missing article body')
            return {'widths':[len(line.rstrip()) for line in parts[1].splitlines() if line.strip()]}
        if mode == 'text':
            return {'exists': True, 'text': text}
        if mode == 'lines':
            return {'exists': True, 'lines': _lines(text)}
        if mode == 'sorted':
            return {'exists': True, 'lines': sorted(_lines(text))}
        if mode == 'grep':
            rx = re.compile(check['pattern'])
            return {'exists': True, 'lines': [ln for ln in _lines(text) if rx.search(ln)]}
        if mode == 'opml':
            return {'exists': True, 'opml': _opml(text)}
        raise ValueError('unknown file mode: ' + mode)
    if kind == 'dir':
        names = [e['name'] for e in full.get('entries', []) if check.get('hidden') or not e['name'].startswith('.')]
        return {'names': sorted(names)}
    if kind == 'cli':
        if full.get('output_limited') or full.get('timed_out'):
            raise AssertionError('the candidate command exceeded its output or time limit')
        part = check.get('part', 'stdout')
        if part == 'exit':
            return {'exit_code': full.get('exit_code')}
        if part == 'stdout':
            return {'stdout': _lines(full.get('stdout'))}
        if part == 'stderr':
            return {'stderr': _lines(full.get('stderr'))}
        if part == 'output':
            return {'output': _lines((full.get('stdout') or '') + '\n' + (full.get('stderr') or ''))}
        if part == 'grep':
            rx = re.compile(check['pattern'])
            text = (full.get('stdout') or '') + '\n' + (full.get('stderr') or '')
            return {'grep': [ln for ln in _lines(text) if rx.search(ln)]}
        if part == 'opml':
            return {'opml': _opml(full.get('stdout') or '')}
        if part == 'contains':
            text = (full.get('stdout') or '') + '\n' + (full.get('stderr') or '')
            return {'contains': [n for n in check['needles'] if n in text]}
        raise ValueError('unknown cli part: ' + part)
    raise ValueError('unknown check kind: ' + kind)


def compare(actual, expected):
    if actual != expected:
        raise AssertionError('observation differs from the reference: ' + _first_diff(actual, expected))


def _first_diff(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                return f'{key}: {a.get(key)!r} != {b.get(key)!r}'[:1500]
    return f'{a!r} != {b!r}'[:1500]
