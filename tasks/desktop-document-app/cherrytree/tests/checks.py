"""Independent program checks; never shown to the evaluator.

A check names public state of the candidate and one aspect of it. Everything is
read through the black-box runtime: saved documents and other product files
through list_files and download, the product's command-line export through
export, the desktop clipboard through clipboard_text. Artifacts are observed
once per checkpoint (artifacts.py's serializer-neutral projections); each
aspect assertion compares its own projection with the frozen reference
projection. A missing or unreadable artifact fails every aspect of it.

Check kinds:
- document: a saved document (any storage format, detected from content;
  password for the protected formats). Aspects: format, tree, bookmarks,
  node:<path> (text, formatting runs and objects of one node, with its
  properties), props:<path>, text:<path>.
- file: one product file in the outbox (text, csv or binary content).
- clipboard: the clipboard text.
- export: runs the command-line export of a document; aspects depend on the
  format: files (written file names), index (HTML node list), page:<file>
  (one node page or text file), text (single text file), sections (single
  HTML file), words/links/size (PDF), status (exit and output summary).
"""
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

import artifacts
from artifacts import Unreadable

SETTLE_SECONDS = 20


# -- runtime channels ----------------------------------------------------------------------------------------------


def upload(ctx, name, data, *, area='inbox'):
    return ctx.broker.call({'op': 'upload', 'filename': name, 'base64': base64.b64encode(data).decode(), 'area': area})


def listing(ctx, area='outbox', folder=None):
    request = {'op': 'list_files', 'area': area, **({'folder': folder} if folder else {})}
    try:
        return {f['name']: f['size'] for f in ctx.broker.call(request)['files']}
    except Exception as exc:
        if folder and 'does not exist' in str(exc):
            return {}
        raise


def download(ctx, name, area='outbox'):
    return base64.b64decode(ctx.broker.call({'op': 'download', 'area': area, 'filename': name})['body_base64'])


def settled(ctx, prefix, area='outbox', timeout=SETTLE_SECONDS):
    """Files at prefix (a file name, or a folder name with its files) once their sizes stop changing."""
    deadline = time.monotonic() + timeout
    previous = None
    while True:
        folder = prefix.rsplit('/', 1)[0] if '/' in prefix else None
        files = {n: s for n, s in listing(ctx, area, folder).items() if n == prefix or n.startswith(prefix + '/')}
        if files and files == previous:
            return files
        previous = files
        if time.monotonic() > deadline:
            return files
        time.sleep(.6)


def fetch_tree(ctx, prefix, target, area='outbox'):
    """Download the file or folder prefix of an exchange area into target; returns the local path."""
    files = settled(ctx, prefix, area)
    if not files:
        raise Unreadable(f'{prefix} was not written')
    target = Path(target)
    shutil.rmtree(target, ignore_errors=True)
    if list(files) == [prefix]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(download(ctx, prefix, area))
        return target
    for name in files:
        local = target / name[len(prefix) + 1:]
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(download(ctx, name, area))
    return target


def scratch(ctx, label):
    root = ctx.state['artifacts']
    root.mkdir(parents=True, exist_ok=True)
    ctx.state['serial'] = ctx.state.get('serial', 0) + 1
    return root / f'{ctx.state["serial"]:04d}-{hashlib.sha256(label.encode()).hexdigest()[:10]}'


# -- observations --------------------------------------------------------------------------------------------------


def artifact_key(check):
    return json.dumps({k: v for k, v in check.items() if k not in ('aspect', 'description')}, sort_keys=True)


def observe_document(ctx, check):
    local = fetch_tree(ctx, check['path'], scratch(ctx, check['path']))
    fmt = artifacts.format_of(local)
    if fmt == '7z':
        password = check.get('password')
        if password is None:
            raise Unreadable('a password is required for this document')
        with tempfile.TemporaryDirectory(dir=ctx.state['scratch']) as work:
            inner = artifacts.extract_7z(local, password, work)
            kind = artifacts.format_of(inner)
            raw = artifacts.read_document(inner)
        details = subprocess.run(['7z', 'l', '-slt', f'-p{password}', str(local)], capture_output=True,
                                 text=True, timeout=120)
        encryption = [line.split('=', 1)[1].strip() for line in details.stdout.splitlines()
                      if line.startswith('Encrypted =')]
        fmt = {'storage': {'ctd': 'ctz', 'ctb': 'ctx'}.get(kind, kind),
               'encrypted': details.returncode == 0 and encryption == ['+']}
    else:
        raw = artifacts.read_document(local, check.get('password'))
    projection = artifacts.document_projection(raw)
    return {'format': fmt, **projection}


def observe_file(ctx, check):
    files = settled(ctx, check['path'])
    if check['path'] not in files:
        raise Unreadable(f'{check["path"]} was not written')
    data = download(ctx, check['path'])
    if check.get('content') == 'text':
        return {'text': artifacts.text_projection(data)}
    if check.get('content') == 'csv':
        import csv
        import io
        return {'rows': [[artifacts.nfc(c) for c in row] for row in csv.reader(io.StringIO(data.decode('utf-8-sig')))]}
    if check.get('content') == 'png':
        return artifacts.png_info(data)
    if check.get('content') == 'pdf':
        local = scratch(ctx, check['path'])
        local.write_bytes(data)
        return artifacts.pdf_projection(local)
    if check.get('content') == 'ini':
        import configparser
        config = configparser.ConfigParser(interpolation=None)
        config.read_string(data.decode('utf-8'))
        return {key: config.get(*key.split('.', 1)) for key in check['keys']}
    return {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}


def observe_clipboard(ctx, check):
    return {'text': artifacts.nfc(ctx.broker.call({'op': 'clipboard_text'})['text'])}


def observe_export(ctx, check):
    """Run the command-line export into a folder of the outbox and project everything the folder holds afterwards."""
    folder = check['folder']
    request = {'op': 'export', 'document': check['document'], 'format': check['format'],
               'folder': f'{ctx.state["outbox"]}/{folder}', 'seconds': check.get('seconds', 60)}
    for key in ('single_file', 'overwrite', 'password'):
        if key in check:
            request[key] = check[key]
    if check.get('run', True):
        ctx.broker.call(request, timeout=request['seconds'] + 60)
    # Each checkpoint owns only its requested format, even when export options
    # deliberately reuse a directory containing older outputs of other formats.
    suffix = {'txt': '.txt', 'html': '.html', 'pdf': '.pdf'}[check['format']]
    written = sorted(name[len(folder) + 1:] for name in listing(ctx, 'outbox', folder)
                     if name.endswith(suffix) and name[len(folder)+1:] not in check.get('ignore', []))
    observation = {'written': written, 'texts': {}, 'pages': {}, 'indexes': {}, 'singles': {}, 'pdfs': {}}
    if not written:
        return observation
    local = scratch(ctx, folder)
    local.mkdir(parents=True, exist_ok=True)
    for name in written:
        path = local / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(download(ctx, folder + '/' + name))
    if check['format'] == 'html':
        from html_semantics import references
        from urllib.parse import unquote, urlsplit
        resources = set()
        for name in written:
            path = local / name
            for ref in references(path.read_text('utf-8', 'replace')):
                parsed = urlsplit(ref)
                if parsed.scheme or not parsed.path or parsed.path.endswith(('.html', '.htm')):
                    continue
                resource = (path.parent / unquote(parsed.path)).resolve()
                if not resource.is_relative_to(local.resolve()):
                    raise Unreadable('an HTML resource leaves its export folder')
                resources.add(resource.relative_to(local.resolve()).as_posix())
        for name in sorted(resources):
            path = local / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(download(ctx, folder + '/' + name))
    for name in written:
        path = local / name
        if check['format'] == 'txt':
            observation['texts'][name] = artifacts.text_projection(path.read_bytes())
        elif check['format'] == 'pdf':
            observation['pdfs'][name] = artifacts.pdf_projection(path)
        else:
            html = path.read_text('utf-8', 'replace')
            kind = artifacts.html_kind(html)
            if kind == 'index':
                observation['indexes'][name] = artifacts.html_index_projection(html)
            elif kind == 'single':
                observation['singles'][name] = artifacts.html_single_projection(html, path.parent)
            else:
                observation['pages'][name] = artifacts.html_page_projection(html, path.parent)
    return observation


def by_node(found, node_id):
    """The one entry of found whose file name ends with the node id (Parent--Name_<id>.txt / .html)."""
    hits = [value for name, value in found.items() if artifacts.node_id_of(name) == str(node_id)]
    if len(hits) != 1:
        raise AssertionError(f'{len(hits)} export files for node {node_id} instead of one')
    return hits[0]


def only(found, what):
    if len(found) != 1:
        raise AssertionError(f'{len(found)} {what} instead of one')
    return next(iter(found.values()))


def project_export(full, aspect):
    part, _, arg = aspect.partition(':')
    if part in ('files', 'written'):
        return full['written']
    if part == 'node-text':
        return by_node(full['texts'], arg)
    if part == 'file-text':
        if arg not in full['texts']:
            raise AssertionError(f'the export did not write {arg}')
        return full['texts'][arg]
    if part == 'single-text':
        return only(full['texts'], 'text files')
    if part == 'node-page':
        return by_node(full['pages'], arg)
    if part == 'index':
        return only(full['indexes'], 'HTML indexes')
    if part == 'section':
        sections = only(full['singles'], 'single HTML files')['sections']
        if arg not in sections:
            raise AssertionError(f'the single HTML file has no section for node {arg}')
        return sections[arg]
    if part == 'section-order':
        return only(full['singles'], 'single HTML files')['order']
    if part in ('pdf-words', 'pdf-links', 'pdf-size'):
        pdf = only(full['pdfs'], 'PDF files')
        return pdf[{'pdf-words': 'words', 'pdf-links': 'links', 'pdf-size': 'page_size'}[part]]
    raise ValueError('unknown export aspect ' + aspect)


OBSERVERS = {'document': observe_document, 'file': observe_file, 'clipboard': observe_clipboard,
             'export': observe_export}


def observe(ctx, check):
    return OBSERVERS[check['kind']](ctx, check)


# -- projections ---------------------------------------------------------------------------------------------------


def project(full, check):
    aspect = check['aspect']
    kind = check['kind']
    if kind == 'document':
        if aspect == 'imported':
            original = {'Inbox', 'Projects', 'Archive', 'Script'}
            imported = {p: n for p, n in full['nodes'].items() if p.split('/')[0] not in original}
            if not imported:
                raise AssertionError('the import added no nodes')
            return imported
        if aspect in ('format', 'tree', 'bookmarks'):
            return full[aspect]
        part, _, path = aspect.partition(':')
        node = full['nodes'].get(path)
        if node is None:
            raise AssertionError(f'the document has no node {path}')
        if part == 'node':
            return node
        if part == 'props':
            return node['props']
        if part == 'text':
            return node['text']
        if part == 'content':
            result = {k: node.get(k) for k in ('text', 'runs', 'spans', 'widgets')}
            if check.get('ignore_plain_blank_lines'):
                # These plain-text clipboard goals require line order, not empty
                # paragraphs introduced at the paste boundary. Formatting and
                # objects remain checked independently and are not discarded.
                result['text'] = re.sub(r'\n{2,}', '\n', result['text']).strip('\n')
            if check.get('ignore_trailing_widget_newlines'):
                # A table appended to the note is a block on screen regardless
                # of whether the editor puts the terminal LF before or after it.
                match = re.search(r'\n*\ufffc\n*\Z', result['text'])
                if match and result['widgets'] and result['widgets'][-1]['at'] >= match.start():
                    result['text'] = result['text'][:match.start()] + '\ufffc'
                    result['widgets'] = [dict(w) for w in result['widgets']]
                    result['widgets'][-1]['at'] = match.start()
            if check.get('ignore_terminal_newlines'):
                result['text'] = result['text'].rstrip('\n')
            return result
        raise ValueError('unknown document aspect ' + aspect)
    if kind == 'export':
        return project_export(full, aspect)
    if kind == 'clipboard' and aspect == 'text' and check.get('ignore_terminal_newlines'):
        return full['text'].rstrip('\n')
    if aspect == 'all':
        return full
    return full[aspect]


def compare(actual, expected):
    if actual != expected:
        raise AssertionError('observation differs from the reference: ' + summary(actual, expected))


def summary(actual, expected):
    """A short description of the first difference, for the result reason."""
    def walk(a, e, path):
        if type(a) is not type(e):
            return f'{path}: {type(a).__name__} instead of {type(e).__name__}'
        if isinstance(e, dict):
            for key in sorted(set(a) | set(e), key=str):
                if key not in a:
                    return f'{path}.{key} missing'
                if key not in e:
                    return f'{path}.{key} unexpected'
                found = walk(a[key], e[key], f'{path}.{key}')
                if found:
                    return found
            return None
        if isinstance(e, list):
            if len(a) != len(e):
                return f'{path}: {len(a)} items instead of {len(e)}'
            for i, (x, y) in enumerate(zip(a, e)):
                found = walk(x, y, f'{path}[{i}]')
                if found:
                    return found
            return None
        if a != e:
            return f'{path}: {json.dumps(a, ensure_ascii=False)[:160]} instead of {json.dumps(e, ensure_ascii=False)[:160]}'
        return None
    return (walk(actual, expected, '$') or 'differs')[:400]
