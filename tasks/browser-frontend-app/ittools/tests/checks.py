'''Observations of tool pages through the black-box runtime, and their comparison with the frozen reference.

Every read goes through the runtime: the snapshot of the page (the controls of the whole page with their values
and states, preformatted blocks and the other text), the clipboard operation and product downloads. Observations
are projections of what a user sees: result fields by position and label, switches and check boxes by state,
result text by line. Values that differ on every run (random tokens, identifiers, keys) are observed by shape only.
'''
import base64
import io
import json
import math
import re
import sys

sys.path.insert(0, '/opt/verifier-lib')

import pages
import field_identity

COPYRIGHT = '©'
PRESSABLE = ('button', 'link', 'menuitem', 'tab', 'option', 'switch', 'checkbox', 'radio')
MENU_WIDTH = 240  # stimuli only: controls whose left edge lies inside the menu column belong to the menu
NEUTRAL = (1279, 899)  # the bottom right corner of the 1280x900 viewport, where no control sits
UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
LOWER = UPPER.lower()
DIGITS = '0123456789'


class Page:
    '''The snapshot of the page for the current checkpoint: read once, dropped by reset after every action.'''

    def __init__(self, broker):
        self.broker = broker
        self.cache = None

    def reset(self):
        self.cache = None

    def snap(self, reading=False):
        if self.cache is None or (reading and 'reading' not in self.cache):
            # The pointer is moved to the corner of the viewport first, so that a tooltip left by the last pointer
            # position (Copy to clipboard, Copied!) is not read as page text.
            self.broker.call({'op': 'pointer', 'action': 'move', 'x': NEUTRAL[0], 'y': NEUTRAL[1]})
            snap = self.broker.call({'op': 'snapshot', 'reading': True} if reading else {'op': 'snapshot'})
            snap['complete'] = not (snap.get('controls_truncated') or snap.get('text_truncated'))
            self.cache = snap
        return self.cache


# -- reading the snapshot ------------------------------------------------------------------------------
def name_of(control):
    return control.get('label') or control.get('placeholder') or ''


def fields(snap):
    return [c for c in snap['controls'] if c.get('tag') in ('input', 'textarea') and c.get('type') not in ('file', 'hidden')]


def outputs(snap):
    return [c for c in fields(snap) if c.get('readonly')]


def inputs(snap):
    return [c for c in fields(snap) if not c.get('readonly')]


def toggles(snap):
    return [c for c in snap['controls'] if c.get('role') in ('switch', 'checkbox')]


def pick(items, name, nth=0):
    found = [c for c in items if name in (c.get('label'), c.get('placeholder'))]
    if len(found) <= nth:
        raise AssertionError('no field named %r (number %d) on the page' % (name, nth))
    return found[nth]


def control_after(snap, control, tag='button', nth=0):
    '''The nth control with the tag that follows the control in page order (a copy button follows its field).'''
    controls = snap['controls']
    rest = [c for c in controls[controls.index(control) + 1:] if c.get('tag') == tag]
    if len(rest) <= nth:
        raise AssertionError('no %s follows the control' % tag)
    return rest[nth]


def in_area(control, area):
    if area == 'any':
        return True
    return (control['bounds'][0] < MENU_WIDTH) == (area == 'menu')


def tool_area(snap, reading=False):
    '''The tool area of the page as (text, control) pairs (control is the listed control the text belongs to, or
    None): from the title of the page (its first line outside controls equal to the page title in any interface
    language) up to a copyright line or the end of the page. Returns (pairs before, pairs of the area, pairs after).'''
    if reading:
        refs = {c['ref']: c for c in snap['controls']}
        pairs = [(text, refs.get(ref) if ref else None) for text, ref in snap.get('reading', [])]
    else:
        pairs = [(line, None) for line in snap.get('text', '').split(chr(10)) if line]
    path = (snap.get('url') or '/').split('?')[0]
    titles = pages.TITLES.get(path, ())
    starts = [i for i, (text, control) in enumerate(pairs) if control is None and text in titles]
    if not starts:
        raise AssertionError('the page %s shows no title line of its tool' % path)
    start = starts[0]
    stops = [i for i in range(start + 1, len(pairs)) if COPYRIGHT in pairs[i][0]]
    stop = stops[0] if stops else len(pairs)
    return pairs[:start], pairs[start:stop], pairs[stop:]


def body_lines(snap, reading=None):
    '''The text lines of the tool area: the page text of the tool itself (title, description, labels, results).
    reading 'values' adds the text of value controls (copyable values), 'all' the text of every control.'''
    area = tool_area(snap, bool(reading))[1]
    if reading == 'values':
        area = [(text, c) for text, c in area if c is None or not pressable(c)]
    return [text for text, _ in area]


def pressable(control):
    return control.get('tag') in ('button', 'a') or control.get('role') in PRESSABLE


def merged(names):
    '''Consecutive repeats merged (a text shown twice in a row, such as a label and its tooltip, counts once).'''
    out = []
    for name in names:
        if not out or out[-1] != name:
            out.append(name)
    return out


# -- shape of values that differ on every run ------------------------------------------------------------
def char_classes(text):
    found = set()
    for ch in text:
        if ch in UPPER:
            found.add('upper')
        elif ch in LOWER:
            found.add('lower')
        elif ch in DIGITS:
            found.add('digit')
        elif ch == chr(10):
            found.add('newline')
        elif ch == ' ':
            found.add('space')
        else:
            found.add('symbol')
    return sorted(found)


def shape(text, spec):
    out = {} if spec.get('only_patterns') else {'length': len(text), 'classes': char_classes(text)}
    for name, pattern in sorted(spec.get('patterns', {}).items()):
        out[name] = re.fullmatch(pattern, text) is not None
    if 'line_pattern' in spec or spec.get('lines'):
        lines = text.split(chr(10))
        out['lines'] = len(lines)
        if not spec.get('only_patterns'):
            out['unique'] = len(set(lines)) == len(lines)
        if 'line_pattern' in spec:
            out['all_lines_match'] = all(re.fullmatch(spec['line_pattern'], line) is not None for line in lines)
    return out


def source_text(ctx, spec):
    where = spec['from']
    if where == 'clipboard':
        return clipboard(ctx)
    snap = ctx.state['page'].snap()
    if where == 'field':
        return pick(fields(snap), spec['name'], spec.get('nth', 0)).get('value', '')
    if where == 'output':
        items = [c.get('value', '') for c in outputs(snap)]
    elif where == 'input':
        items = [c.get('value', '') for c in inputs(snap)]
    elif where == 'block':
        items = [b['text'] for b in snap.get('blocks', [])]
    else:
        raise ValueError('unknown source ' + where)
    index = spec.get('index', 0)
    if not -len(items) <= index < len(items):
        raise AssertionError('the page has no %s number %d' % (where, index))
    return items[index]


def clipboard(ctx):
    return ctx.broker.call({'op': 'clipboard'}).get('text', '')


# -- observation dispatcher ----------------------------------------------------------------------------
def observe(ctx, cp, spec):
    kind = spec['type']
    if kind == 'multi':
        return {name: observe(ctx, cp, sub) for name, sub in spec['checks'].items()}
    if kind == 'clipboard':
        return {'text': clipboard(ctx)}
    if kind == 'download':
        return observe_download(ctx, spec)
    if kind == 'shape':
        return shape(source_text(ctx, spec), spec)
    if kind == 'changed':
        # A value that differs on every run: whether it changed from the one remembered before the last steps.
        before = ctx.state.get('memo', {}).get(spec['name'])
        if before is None:
            raise AssertionError('no value was remembered as %r' % spec['name'])
        return {'changed': source_text(ctx, spec['source']) != before}
    snap = ctx.state['page'].snap()
    if kind == 'page':
        return {'url': snap.get('url'), 'title': snap.get('title')}
    if kind == 'outputs':
        if snap.get('controls_truncated'):
            raise AssertionError('the page lists more controls than the interface reports')
        # Resolve the whole group before selecting a result. A different visual
        # order is valid, but a digest or scale must keep its semantic identity.
        items = field_identity.project_controls(outputs(snap), cp.get('page', '/'), 'outputs')
        roles = field_identity.schema(cp.get('page', '/'), 'outputs')
        if roles is not None and items:
            selected = roles[spec.get('start', 0):spec.get('stop')]
            by_name = dict(items)
            if any(role.name not in by_name for role in selected):
                raise AssertionError('the page is missing a requested result field')
            items = [[role.name, by_name[role.name]] for role in selected]
        else:
            items = items[spec.get('start', 0):spec.get('stop')]
        if not items and not spec.get('allow_empty'):
            raise AssertionError('the page shows no result fields')
        if spec.get('labels'):
            return {'outputs': items}
        return {'outputs': [value for name, value in items]}
    if kind == 'inputs':
        if snap.get('controls_truncated') and field_identity.schema(cp.get('page', '/'), 'inputs') is not None:
            raise AssertionError('the page lists more controls than the interface reports')
        return {'inputs': field_identity.project_controls(inputs(snap), cp.get('page', '/'), 'inputs')}
    if kind == 'fields':
        out = {}
        for entry in spec['names']:
            name, nth = (entry, 0) if isinstance(entry, str) else entry
            out[name if nth == 0 else '%s[%d]' % (name, nth)] = pick(fields(snap), name, nth).get('value', '')
        return out
    if kind == 'blocks':
        blocks = [b['text'] for b in snap.get('blocks', [])]
        if not blocks and not spec.get('allow_empty'):
            raise AssertionError('the page shows no preformatted result')
        return {'blocks': blocks}
    if kind in ('menu', 'cards'):
        # Tool and category names in page order (consecutive repeats merged): those outside the tool area are the
        # menu, those inside the home page area are its tool cards.
        snap = ctx.state['page'].snap(reading=True)
        if snap.get('reading_truncated'):
            raise AssertionError('the page text is longer than the interface reports')
        before, area, after = tool_area(snap, True)
        chosen = before + after if kind == 'menu' else area
        return {'names': merged([text for text, _ in chosen if text in pages.MENU_NAMES])}
    if kind == 'lines':
        reading = spec.get('reading')
        if reading:
            snap = ctx.state['page'].snap(reading=True)
        if snap.get('reading_truncated' if reading else 'text_truncated') and not spec.get('partial'):
            raise AssertionError('the page text is longer than the interface reports')
        lines = body_lines(snap, reading)[spec.get('skip', 0):]
        if 'start' in spec:
            if spec['start'] not in lines:
                raise AssertionError('the page shows no line %r' % spec['start'])
            lines = lines[lines.index(spec['start']) + 1:]
        if 'stop' in spec and spec['stop'] in lines:
            lines = lines[:lines.index(spec['stop'])]
        if 'count' in spec:
            lines = lines[:spec['count']]
        return {'lines': lines}
    if kind == 'toggles':
        return {'toggles': [[c.get('role'), c.get('text') or '', bool(c.get('checked'))] for c in toggles(snap)]}
    if kind == 'controls':
        items = [c for c in snap['controls'] if in_area(c, spec.get('area', 'any'))]
        for key in ('tag', 'role'):
            if key in spec:
                items = [c for c in items if c.get(key) == spec[key]]
        if 'prefix' in spec:
            items = [c for c in items if (c.get('text') or '').startswith(spec['prefix'])]
        if 'text' in spec:
            items = [c for c in items if (c.get('text') or '') == spec['text']]
        texts = [c.get('text') or '' for c in items]
        return {'count': len(texts)} if spec.get('count_only') else {'count': len(texts), 'texts': texts}
    raise ValueError('unknown check type ' + kind)


# -- product files -------------------------------------------------------------------------------------
def take_download(ctx):
    '''The newest pending product download (retrieved once, kept for the checkpoint).'''
    files = ctx.state.setdefault('files', {})
    if 'download' not in files:
        snap = ctx.broker.call({'op': 'snapshot'})
        pending = snap.get('downloads', [])
        if not pending:
            raise AssertionError('no download was produced')
        item = ctx.broker.call({'op': 'download', 'ref': pending[-1]['ref']})
        files['download'] = (item['filename'], base64.b64decode(item['body_base64']))
    return files['download']


def image_facts(data):
    from PIL import Image
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise AssertionError('the downloaded file is not a readable image: ' + type(exc).__name__) from None
    colours = image.convert('RGBA').getcolors(maxcolors=64)
    return {'format': image.format, 'size': list(image.size),
            'palette': None if colours is None else sorted('#%02x%02x%02x%02x' % c[1] for c in colours)}


def observe_download(ctx, spec):
    name, data = take_download(ctx)
    parts = spec.get('parts', ('name', 'text'))
    out = {}
    if 'name' in parts:
        out['name'] = name
    if 'text' in parts:
        out['text'] = data.decode('utf-8', errors='replace')
    if 'bytes' in parts:
        out['bytes'] = len(data)
    if 'sha256' in parts:
        import hashlib
        out['sha256'] = hashlib.sha256(data).hexdigest()
    if 'image' in parts:
        out.update(image_facts(data))
    return out


# -- comparison ----------------------------------------------------------------------------------------
def show(value):
    return json.dumps(value, ensure_ascii=False)[:160]


def compare(actual, expected, tol=0.0, path='observation'):
    '''Structural equality with numeric tolerance; AssertionError names the first difference.'''
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if actual != expected:
            raise AssertionError('%s: expected %s, got %s' % (path, show(expected), show(actual)))
        return
    if isinstance(expected, (int, float)):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual) \
                or abs(actual - expected) > tol:
            raise AssertionError('%s: expected %s (tolerance %s), got %s' % (path, expected, tol, show(actual)))
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise AssertionError('%s: expected %d items, got %s' % (
                path, len(expected), len(actual) if isinstance(actual, list) else show(actual)))
        for i, (a, e) in enumerate(zip(actual, expected)):
            compare(a, e, tol, '%s[%d]' % (path, i))
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise AssertionError('%s: expected an object' % path)
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        if missing or extra:
            raise AssertionError('%s: keys differ (missing %s, unexpected %s)' % (path, missing[:5], extra[:5]))
        for key in expected:
            compare(actual[key], expected[key], tol, '%s.%s' % (path, key))
        return
    raise AssertionError('%s: unsupported value' % path)
