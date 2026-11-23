"""Resolve visible controls from runtime snapshots, without DOM or filesystem access."""
import time
import re


def normalize(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()


def semantic(control, name):
    """Match a displayed label regardless of which HTML/ARIA attribute carries it."""
    if isinstance(name, (list, tuple)):
        return any(semantic(control, value) for value in name)
    wanted = normalize(name).strip(' :')
    return any(wanted == normalize(control.get(key)).strip(' :') for key in ('label','aria','title','text','placeholder'))


def find(snap, match):
    matches = []
    for control in snap.get('controls', []):
        ok = True
        for name, value in match.items():
            if name in ('nth', 'contains'):
                continue
            if name == 'has_option':
                ok &= any(value in (o.get('label'), o.get('value')) for o in control.get('options', []))
            elif name == 'enabled':
                ok &= (not bool(control.get('disabled'))) == bool(value)
            elif name == 'semantic':
                ok &= semantic(control, value)
            elif name == 'scope':
                ok &= any(normalize(value) in normalize(control.get(key)) for key in ('group', 'context'))
            elif name == 'exclude_scope':
                # The runtime's group is the nearest visible heading/field group. Ancestor context can contain
                # sibling sections, so excluding any occurrence there rejects unrelated, correctly labelled fields.
                group = control.get('group', control.get('context', '').split(' | ')[0])
                ok &= normalize(value) not in normalize(group)
            elif name == 'near':
                ok &= normalize(value) in normalize(control.get('context', '').split(' | ')[0])
            elif name == 'editable':
                ok &= bool(control.get('editable') or control.get('role') in ('textbox','searchbox','spinbutton')) == value
            elif name == 'value_pattern':
                ok &= bool(re.fullmatch(value, str(control.get('value', ''))))
            elif name == 'component':
                ok &= semantic(control, value) or normalize(control.get('context', '').split(' | ')[0]) == normalize(value)
            elif name == 'dimension':
                group, axis = value
                label = normalize(control.get('label') or control.get('aria'))
                nearest = normalize(control.get('context', '').split(' | ')[0])
                aliases = ('width', 'horizontal', 'x offset') if axis == 'width' else ('height', 'vertical', 'y offset')
                explicit = any(semantic(control, group+' '+word) for word in aliases)
                labeled = any(semantic(control, word) for word in aliases) and normalize(group) in nearest
                compact = (label == normalize(group) if axis == 'width' else label == 'x') and normalize(group) in nearest
                ok &= bool(explicit or labeled or compact)
            elif match.get('contains') and isinstance(value, str):
                ok &= value.lower() in str(control.get(name, '')).lower()
            else:
                ok &= control.get(name) == value
        if ok:
            matches.append(control)
    n = match.get('nth', 0)
    if 'nth' not in match and len(matches) > 1:
        if 'scope' in match:
            def distance(c):
                if normalize(match['scope']) in normalize(c.get('group')):
                    return -1
                return next((i for i,s in enumerate(c.get('context','').split(' | ')) if normalize(match['scope']) in normalize(s)),100)
            closest = min(map(distance, matches))
            matches = [c for c in matches if distance(c) == closest]
            if len(matches) == 1:
                return matches[0]
        # A focused editor is unambiguous even when other text fields remain visible.
        focused = [c for c in matches if c.get('focused')]
        if len(focused) == 1:
            return focused[0]
        raise AssertionError('Ambiguous visible controls: ' + str(match))
    return matches[n] if -len(matches) <= n < len(matches) else None


def resolve(ctx, match):
    end = time.monotonic() + 6
    while True:
        control = find(ctx.broker.call({'op': 'snapshot'}), match)
        if control is not None:
            return control
        if time.monotonic() >= end:
            raise AssertionError('Visible control not found: ' + str(match))
        time.sleep(.15)


def act(ctx, step):
    control = resolve(ctx, step['match'])
    op = step.get('action', 'click')
    if op == 'drag-to':
        other = resolve(ctx, step['to'])
        x, y, w, h = control['bounds']
        a, b, c, d = other['bounds']
        return ctx.broker.call({'op': 'drag', 'x': x + step.get('dx', w/2),
                               'y': y + step.get('dy', h/2),
                               'to_x': a + step.get('to_dx', c/2),
                               'to_y': b + step.get('to_dy', d/2), 'steps': 20})
    request = {'op': op, 'target': {'ref': control['ref']}}
    for key in ('value', 'key', 'checked', 'button', 'modifiers', 'click_count'):
        if key in step:
            request[key] = step[key]
    if op == 'pointer':
        _, _, w, h = control['bounds']
        request.update(action='click', x=w * step.get('rx', .5), y=h * step.get('ry', .5))
    result = ctx.broker.call(request)
    if step.get('enter'):
        result = ctx.broker.call({'op': 'press', 'key': 'Enter'})
    return result


def wait_download(ctx, suffix):
    end = time.monotonic() + 12
    while True:
        snap = ctx.broker.call({'op': 'snapshot'})
        if any(d['filename'].lower().endswith(suffix) for d in snap.get('downloads', [])):
            return
        if time.monotonic() >= end:
            raise AssertionError('No product download ending in ' + suffix)
        time.sleep(.2)
