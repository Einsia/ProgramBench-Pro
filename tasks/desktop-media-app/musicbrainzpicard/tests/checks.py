"""Setup, preparation and independent program checks of GUI checkpoints.

Setup items prepare non-target state through public channels only: input documents (upload), settings (a
profile imported with picard-cli, then a restart so that the application uses it) and loaded files (the LOAD
remote command, followed by a WRITE_LOGS marker whose appearance shows that the commands before it completed).
Checks read what the checkpoint's goal produced: saved audio files (tag dumps by the verifier's own reader), the
files and folders of the document folders, documents the application exported, and the session the application
saves when it quits.
"""
import json
import struct
import time

import fixtures
from harness import DATE, UUID, decode_session
from scenario import items as session_items
import tagio

SETTLE_SECONDS = 25


def expand(c, text):
    if isinstance(text, str):
        return text.replace('{inputs}', c.inputs).replace('{outputs}', c.outputs)
    if isinstance(text, list):
        return [expand(c, v) for v in text]
    if isinstance(text, dict):
        return {k: expand(c, v) for k, v in text.items()}
    return text


def document(c, spec):
    """Bytes of one declared input document."""
    if 'audio' in spec:
        return fixtures.audio_file(spec['audio'], spec.get('tags') or {}, seconds=spec.get('seconds', 1.0),
                                   freq=spec.get('freq', 440), channels=spec.get('channels', 1))
    if 'image' in spec:
        return fixtures.image(spec['image'])
    if 'text' in spec:
        return expand(c, spec['text']).encode('utf-8')
    if 'profile' in spec:
        p = expand(c, spec['profile'])
        return fixtures.profile(p['title'], p.get('settings'), p.get('naming'), p.get('tagging', ()),
                                p.get('enable_tagger_scripts'))
    if 'session' in spec:
        items = []
        for item in spec['session']['items']:
            entry = {'file_path': f"{c.inputs}/{item['file']}", 'location': item.get('location', {'type': 'unclustered'})}
            if item.get('tags'):
                entry['metadata'] = {'tags': item['tags']}
            items.append(entry)
        return fixtures.session(items, spec['session'].get('options'))
    raise ValueError('unknown document '+json.dumps(spec)[:200])


def wait_marker(c, marker, seconds=30):
    """The application ran the commands queued before WRITE_LOGS <marker>."""
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if marker in c.tree('outputs'):
            return True
        time.sleep(.5)
    return False


def load(c, paths):
    for path in paths:
        result = c.command('LOAD', f'{c.inputs}/{path}')
        if result.get('exit_code') != 0:
            raise AssertionError('LOAD was not delivered: '+json.dumps(result)[:300])
    c.state['markers'] = c.state.get('markers', 0)+1
    marker = f'.setup-{c.state["markers"]}.log'
    c.command('WRITE_LOGS', f'{c.outputs}/{marker}')
    if not wait_marker(c, marker):
        time.sleep(5)
    time.sleep(1)


def setup(c, episode, item):
    op = item['op']
    if op == 'documents':
        for entry in item['files']:
            c.upload(entry['name'], document(c, entry['spec']), folder=entry.get('folder', ''))
    elif op == 'profile':
        import_profile(c, f'{episode["id"]}.toml', item['profile'])
    elif op == 'load':
        load(c, item['paths'])
    else:
        raise ValueError('unknown setup operation '+op)


def import_profile(c, name, profile):
    path = c.upload(name, document(c, {'profile': profile}), folder='_settings')
    result = c.cli('--yes', 'profiles', 'import', path, '--enable')
    if result.get('exit_code') != 0:
        raise AssertionError('the settings profile was not imported: '+json.dumps(result)[:300])
    c.restart()


def prepare(c, episode, checkpoint):
    for step in checkpoint.get('preparation', []):
        if step['op'] == 'profile':
            # A later imported profile takes precedence; every profile of an episode names the same settings.
            import_profile(c, f'{episode["id"]}-{checkpoint["id"]}.toml', step['profile'])
        elif step['op'] == 'load':
            load(c, step['paths'])
        elif step['op'] == 'command':
            c.command(step['name'], expand(c, step.get('argument', '')))
        else:
            raise ValueError('unknown preparation '+step['op'])


def begin(c, episode, checkpoint):
    c.cache = {}
    # Modification times before the checkpoint's operations (for checks of preserved timestamps).
    listing = c.listing()
    c.state['mtimes'] = {f'{area}/{e["path"]}': e.get('mtime') for area in ('inputs', 'outputs')
                         for e in listing.get(area, []) if e['type'] == 'file'}


def snapshot(c):
    listing = c.listing()
    return {area: [(e['path'], e.get('size')) for e in listing.get(area, [])] for area in ('inputs', 'outputs')}


def collect(c, episode, checkpoint):
    """Let the application finish writing (the document folders stop changing), then read them once."""
    previous, stable_since, deadline = None, None, time.monotonic()+SETTLE_SECONDS
    while time.monotonic() < deadline:
        current = snapshot(c)
        if current == previous:
            if stable_since and time.monotonic()-stable_since >= 2.0:
                break
            stable_since = stable_since or time.monotonic()
        else:
            previous, stable_since = current, None
        time.sleep(.5)
    c.cache = {'listing': c.listing()}


def file_bytes(c, area_path):
    area, _, relative = area_path.partition('/')
    cached = c.cache.setdefault('files', {})
    if area_path not in cached:
        listing = c.cache.get('listing') or c.listing()
        ref = next((e['ref'] for e in listing.get(area, []) if e['type'] == 'file' and e['path'] == relative), None)
        cached[area_path] = c.download(ref) if ref else None
    return cached[area_path]


def tree(c, area, under=''):
    listing = c.cache.get('listing') or c.listing()
    prefix = under.rstrip('/')+'/' if under else ''
    return sorted(e['path'][len(prefix):]+('/' if e['type'] == 'folder' else '')
                  for e in listing.get(area, []) if e['path'].startswith(prefix)
                  and not e['path'].startswith('.setup-') and not e['path'].startswith('_settings'))


TITLE_KEYS = ('TIT2', 'TITLE', '\xa9nam', 'Title')


def title_of(dumped):
    for key, values in dumped.get('fields', {}).items():
        if key in TITLE_KEYS or key.casefold() == 'title':
            return values[0] if values else None
    return None


def located(c, title):
    """Where the file with this title is now: its document folder and relative path."""
    index = c.cache.setdefault('titles', None)
    if index is None:
        listing = c.cache.get('listing') or c.listing()
        index = {}
        for area in ('inputs', 'outputs'):
            for entry in listing.get(area, []):
                name = entry['path'].rsplit('/', 1)[-1]
                if entry['type'] != 'file' or '.' not in name or f'.{name.rsplit(".", 1)[1].lower()}' not in tagio.FAMILY:
                    continue
                try:
                    dumped = tagio.dump_bytes(file_bytes(c, f'{area}/{entry["path"]}'), name)
                except AssertionError:
                    continue
                index.setdefault(title_of(dumped), []).append(f'{area}/{entry["path"]}')
        c.cache['titles'] = index
    return sorted(index.get(title, []))


def normalized(c, value, given=()):
    if isinstance(value, dict):
        return {k: normalized(c, v, given) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(c, v, given) for v in value]
    if isinstance(value, str):
        value = c.normalize(value)
        value = UUID.sub(lambda m: m.group(0) if m.group(0) in given else '<uuid>', value)
        return DATE.sub('<date>', value)
    return value


INI_ESCAPES = {'a': '\a', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t', 'v': '\v', '"': '"', '?': '?',
               "'": "'", '\\': '\\'}


def ini_unescaped(text):
    """One QSettings INI value without its quoting and escapes (\\xHH and \\0 escapes take all following hex or
    octal digits, as the QSettings reader does)."""
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        i += 1
        if ch == '"':
            continue
        if ch != '\\' or i >= len(text):
            out.append(ch)
            continue
        ch = text[i]
        i += 1
        digits, base = ('0123456789abcdefABCDEF', 16) if ch == 'x' else ('01234567', 8) if ch in '01234567' else ('', 0)
        if not base:
            out.append(INI_ESCAPES.get(ch, ch))
            continue
        start = i if ch == 'x' else i-1
        i = start
        while i < len(text) and text[i] in digits:
            i += 1
        out.append(chr(int(text[start:i] or '0', base)))
    return ''.join(out)


def variant_strings(data):
    """The strings of a QSettings @Variant list (QDataStream version 4.0: a QVariantList of strings or a QStringList).
    Any other variant raises ValueError; nothing in a value is ever unpickled."""
    def u32(at):
        return struct.unpack_from('>I', data, at)[0], at+4

    def text(at):
        size, at = u32(at)
        return ('', at) if size == 0xFFFFFFFF else (data[at:at+size].decode('utf-16-be'), at+size)
    kind, at = u32(0)
    if kind not in (9, 11):
        raise ValueError(f'variant type {kind} is not read')
    count, at = u32(at)
    items = []
    for _ in range(count):
        if kind == 9:
            element, at = u32(at)
            if element != 10:
                raise ValueError(f'variant type {element} is not read')
        item, at = text(at)
        items.append(item)
    return items


def ini_list(raw):
    """A string-list setting of a QSettings INI file as a list: comma-separated items or an @Variant list."""
    if raw is None:
        return None
    raw = raw.strip()
    if raw in ('', '@Invalid()'):
        return []
    if raw.strip('"').startswith('@Variant('):
        try:
            return variant_strings(ini_unescaped(raw.strip('"')[9:-1]).encode('latin-1'))
        except (ValueError, IndexError, UnicodeError, struct.error):
            return raw
    items, current, quoted, i = [], [], False, 0
    while i < len(raw):
        ch = raw[i]
        if ch == '\\' and i+1 < len(raw):
            current.append(raw[i:i+2])
            i += 2
            continue
        if ch == '"':
            quoted = not quoted
        if ch == ',' and not quoted:
            items.append(''.join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    items.append(''.join(current))
    return [ini_unescaped(item.strip()) for item in items]


def observe(c, episode, checkpoint, assertion):
    check = assertion['check']
    kind = check['kind']
    if kind == 'dump':
        path = check.get('path')
        for candidate in check.get('paths', ()):
            if file_bytes(c, candidate) is not None:
                path = candidate
                break
        if path is None and 'title' in check:
            places = located(c, check['title'])
            if len(places) != 1:
                raise AssertionError(f'{len(places)} saved files are titled {check["title"]!r}')
            path = places[0]
        if path is None:
            raise AssertionError('none of the expected files exists: '+', '.join(check.get('paths', ())))
        data = file_bytes(c, path)
        if data is None:
            raise AssertionError(f'{path} does not exist')
        result = tagio.dump_bytes(data, path.rsplit('/', 1)[-1], encodings=check.get('encodings', False),
                                  seektable=check.get('seektable', False))
        for key in check.get('drop', ()):
            result.pop(key, None)
        return result
    if kind == 'mtime-kept':
        listing = c.cache.get('listing') or c.listing()
        area, _, relative = check['path'].partition('/')
        now = next((e.get('mtime') for e in listing.get(area, []) if e['type'] == 'file' and e['path'] == relative),
                   None)
        before = c.state.get('mtimes', {}).get(check['path'])
        if now is None or before is None:
            raise AssertionError(f'{check["path"]} is missing before or after the checkpoint')
        return {'modification_time_kept': abs(now-before) < 0.01}
    if kind == 'image-file':
        data = file_bytes(c, check['path'])
        if data is None:
            raise AssertionError(f'{check["path"]} does not exist')
        return tagio.picture_summary(data)
    if kind == 'located':
        places = located(c, check['title'])
        if not places:
            raise AssertionError(f'no saved file is titled {check["title"]!r}')
        return {'paths': places}
    if kind == 'tree':
        return {'paths': tree(c, check['area'], check.get('under', ''))}
    if kind == 'exists':
        return {'exists': file_bytes(c, check['path']) is not None}
    if kind == 'profile-export':
        data = file_bytes(c, check['path'])
        if data is None:
            raise AssertionError(f'{check["path"]} does not exist')
        import tomli
        try:
            value = tomli.loads(data.decode('utf-8'))
        except Exception as exc:
            raise AssertionError(f'the exported profile is not TOML: {exc}') from None
        return {'profile': normalized(c, value)}
    if kind == 'profile-list':
        listing = c.cli('profiles', 'list')
        if listing.get('exit_code') != 0:
            raise AssertionError('picard-cli profiles list failed: '+json.dumps(listing)[:300])
        lines = [normalized(c, line.strip()) for line in str(listing.get('stdout', '')).splitlines()]
        return {'profiles': sorted(line for line in lines if any(title in line for title in check['titles']))}
    if kind == 'ini':
        data = file_bytes(c, check['path'])
        if data is None:
            raise AssertionError(f'{check["path"]} does not exist')
        import configparser
        parser = configparser.RawConfigParser(strict=False, interpolation=None)
        parser.optionxform = str
        try:
            parser.read_string(data.decode('utf-8'))
        except Exception as exc:
            raise AssertionError(f'the file is not an INI document: {type(exc).__name__}') from None
        section = parser[check['section']] if parser.has_section(check['section']) else {}
        if check.get('lists'):
            return {key: normalized(c, ini_list(section.get(key))) for key in check['keys']}
        return {key: normalized(c, section.get(key)) for key in check['keys']}
    if kind == 'script-package':
        data = file_bytes(c, check['path'])
        if data is None:
            raise AssertionError(f'{check["path"]} does not exist')
        import yaml
        try:
            value = yaml.safe_load(data.decode('utf-8'))
        except Exception as exc:
            raise AssertionError(f'the script package is not YAML: {type(exc).__name__}') from None
        if not isinstance(value, dict):
            raise AssertionError('the script package is not a mapping')
        fields = ('title', 'script', 'script_language_version', 'description', 'author', 'license', 'version')
        return {key: value.get(key) for key in fields if key in value}
    if kind == 'session-file':
        data = file_bytes(c, check['path'])
        if data is None:
            raise AssertionError(f'{check["path"]} does not exist')
        session = decode_session(data)
        return {'options': (session or {}).get('options'), 'items': session_items(c, session, tags=True)}
    if kind == 'session':
        session = c.quit_session()
        rows = session_items(c, session, tags=check.get('tags', False))
        if 'under' in check:
            prefix = '<inputs>/'+check['under']
            rows = [r for r in rows if r['path'] == prefix or r['path'].startswith(prefix.rstrip('/')+'/')]
        return {'items': rows}
    raise ValueError('unknown check '+kind)
