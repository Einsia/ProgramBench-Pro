"""Verifier-side decoding and serializer-neutral projections of CherryTree documents and exports.

Saved documents in every storage format (XML .ctd, SQLite .ctb, a folder of
node files, the 7-Zip protected .ctz/.ctx) are read into one model: the node
tree with node properties, the text of every node with its formatting runs and
anchored widgets, and the bookmarks. Projections drop what the format leaves
free: node ids (node links and bookmarks become node paths), timestamps, how
text is split into runs, attribute order, colour precision and XML layout.

Exports are projected by meaning as well: plain-text exports as text with
normalized line ends and blank-line runs; HTML pages as the node title and a
sequence of formatted text runs, paragraph and list-item boundaries, tables,
code blocks (their text only, not the highlighting colours), images and
embedded files (by decoded content), anchors and link targets; the HTML index
as the nested node list; PDF exports as their words, link targets and page
size. Nothing here reads the application.
"""
from __future__ import annotations

import base64
import collections
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zlib

LATEX_FILENAME = '__ct_special.tex'
WIDGET = '￼'
BOOL_ATTRS = {'readonly', 'nosearch_me', 'nosearch_ch', 'is_bold'}
RUN_ATTRS = ('weight', 'style', 'underline', 'strikethrough', 'foreground', 'background', 'scale', 'family',
             'justification', 'indent', 'link')


class Unreadable(AssertionError):
    """The artifact is missing or cannot be decoded."""


def nfc(text):
    return unicodedata.normalize('NFC', text)


def color(value):
    """#rgb, #rrggbb or #rrrrggggbbbb -> #rrggbb (lower case); '' when unset."""
    value = (value or '').strip().lower()
    if not value:
        return ''
    if not re.fullmatch(r'#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{12})', value):
        return value
    digits = value[1:]
    if len(digits) == 3:
        return '#' + ''.join(c * 2 for c in digits)
    if len(digits) == 12:
        return '#' + digits[0:2] + digits[4:6] + digits[8:10]
    return value


def png_info(data):
    """Decoded RGBA pixels, independent of PNG compression, palette, depth and interlacing."""
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise Unreadable('the image is not PNG')
    import io
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.width * source.height > 40_000_000:
                raise Unreadable('the image dimensions exceed the document limit')
            pixels = source.convert('RGBA')
            return {'width': pixels.width, 'height': pixels.height,
                    'sha256': hashlib.sha256(pixels.tobytes()).hexdigest()}
    except (OSError, ValueError) as exc:
        raise Unreadable('the PNG cannot be decoded') from exc


# -- document readers -> raw model ---------------------------------------------------------------------------------
# raw node: {'id', 'master', 'props': {...}, 'rich': bool, 'runs': [(text, attrs)], 'widgets': [(offset, widget)],
#            'children': [raw nodes]}


def truthy(value):
    return str(value).strip().lower() in ('1', 'true', 'yes')


def element_text(element):
    return element.text or ''


def widget_from_element(element, blob_dir=None):
    """(offset, widget dict) of a codebox, table or encoded_png element."""
    tag = element.tag
    offset = int(element.get('char_offset', '0'))
    justification = element.get('justification') or 'left'
    if tag == 'codebox':
        return offset, {'kind': 'codebox', 'text': element_text(element), 'syntax': element.get('syntax_highlighting', ''),
                        'width': int(element.get('frame_width', '0') or 0),
                        'height': int(element.get('frame_height', '0') or 0),
                        'pixels': truthy(element.get('width_in_pixels', '1')),
                        'brackets': truthy(element.get('highlight_brackets', '0')),
                        'line_numbers': truthy(element.get('show_line_numbers', '0')),
                        'justification': justification}
    if tag == 'table':
        return offset, dict(table_rows(element), justification=justification)
    if tag == 'encoded_png':
        anchor = element.get('anchor')
        if anchor:
            return offset, {'kind': 'anchor', 'name': anchor, 'justification': justification}
        filename = element.get('filename') or ''
        if filename == LATEX_FILENAME:
            return offset, {'kind': 'latex', 'text': element_text(element), 'justification': justification}
        digest = element.get('sha256sum')
        if digest and blob_dir is not None:
            matches = sorted(p for p in Path(blob_dir).iterdir() if p.name.startswith(digest))
            if not matches:
                raise Unreadable(f'blob {digest} of a multiple-files document is missing')
            data = matches[0].read_bytes()
        else:
            try:
                data = base64.b64decode(element_text(element).strip(), validate=False)
            except ValueError:
                raise Unreadable('an embedded image or file is not valid base64') from None
        if filename:
            return offset, {'kind': 'file', 'filename': filename, 'data': data, 'justification': justification}
        return offset, {'kind': 'image', 'data': data, 'link': element.get('link', ''), 'justification': justification}
    raise Unreadable('unknown content element ' + tag)


def table_rows(element):
    rows = [[element_text(cell) for cell in row.findall('cell')] for row in element.findall('row')]
    if rows:
        rows = rows[-1:] + rows[:-1]          # the header row is stored last
    return {'kind': 'table', 'rows': rows, 'light': truthy(element.get('is_light', '0')),
            'default_width': int(element.get('col_max', '60')),
            'column_widths': [int(x) for x in (element.get('col_widths') or '').split(',') if x]}


def node_from_xml(element, blob_dir=None):
    master = int(element.get('master_id', '0') or 0)
    props = {'name': element.get('name', ''), 'syntax': element.get('prog_lang', ''), 'tags': element.get('tags', ''),
             'readonly': truthy(element.get('readonly', '0')), 'bold': truthy(element.get('is_bold', '0')),
             'foreground': color(element.get('foreground', '')), 'icon': int(element.get('custom_icon_id', '0') or 0),
             'nosearch_me': truthy(element.get('nosearch_me', '0')), 'nosearch_ch': truthy(element.get('nosearch_ch', '0'))}
    runs, widgets = [], []
    for child in element:
        if child.tag == 'rich_text':
            runs.append((element_text(child), {k: child.get(k) for k in RUN_ATTRS if child.get(k)}))
        elif child.tag in ('codebox', 'table', 'encoded_png'):
            widgets.append(widget_from_element(child, blob_dir))
    return {'id': int(element.get('unique_id', '0') or 0), 'master': master, 'props': props,
            'rich': props['syntax'] == 'custom-colors', 'runs': runs, 'widgets': widgets, 'children': []}


def read_ctd(path):
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise Unreadable(f'not a CherryTree XML document: {exc}') from None
    if root.tag != 'cherrytree':
        raise Unreadable('the XML root element is not cherrytree')

    def build(element):
        node = node_from_xml(element)
        node['children'] = [build(child) for child in element.findall('node')]
        return node
    bookmarks = root.find('bookmarks')
    marks = [int(x) for x in (bookmarks.get('list', '') if bookmarks is not None else '').split(',') if x.strip()]
    return {'nodes': [build(e) for e in root.findall('node')], 'bookmarks': marks}


def read_ctb(path):
    try:
        db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        db.execute('SELECT count(*) FROM node').fetchone()
    except sqlite3.Error as exc:
        raise Unreadable(f'not a CherryTree SQLite document: {exc}') from None
    try:
        rows = {r[0]: r for r in db.execute('SELECT node_id, name, txt, syntax, tags, is_ro, is_richtxt, level FROM node')}
        widgets = collections.defaultdict(list)
        for node_id, offset, just, txt, syntax, width, height, pix, bra, num in db.execute(
                'SELECT node_id, offset, justification, txt, syntax, width, height, is_width_pix, do_highl_bra, '
                'do_show_linenum FROM codebox'):
            widgets[node_id].append((offset, {'kind': 'codebox', 'text': txt or '', 'syntax': syntax or '',
                                              'width': int(width or 0), 'height': int(height or 0), 'pixels': bool(pix),
                                              'brackets': bool(bra), 'line_numbers': bool(num),
                                              'justification': just or 'left'}))
        for node_id, offset, just, txt, col_max in db.execute('SELECT node_id, offset, justification, txt, col_max FROM grid'):
            try:
                table = ET.fromstring((txt or '').strip().encode())
            except ET.ParseError:
                raise Unreadable('a table of the SQLite document is not valid XML') from None
            table.set('col_max', str(col_max or 60))
            widgets[node_id].append((offset, dict(table_rows(table), justification=just or 'left')))
        for node_id, offset, just, anchor, blob, filename, link in db.execute(
                'SELECT node_id, offset, justification, anchor, png, filename, link FROM image'):
            just = just or 'left'
            if anchor:
                item = {'kind': 'anchor', 'name': anchor, 'justification': just}
            elif filename == LATEX_FILENAME:
                item = {'kind': 'latex', 'text': bytes(blob or b'').decode('utf-8', 'replace'), 'justification': just}
            elif filename:
                item = {'kind': 'file', 'filename': filename, 'data': bytes(blob or b''), 'justification': just}
            else:
                item = {'kind': 'image', 'data': bytes(blob or b''), 'link': link or '', 'justification': just}
            widgets[node_id].append((offset, item))
        links = list(db.execute('SELECT node_id, father_id, sequence, master_id FROM children'))
        try:
            marks = [r[0] for r in db.execute('SELECT node_id FROM bookmark ORDER BY sequence')]
        except sqlite3.Error:
            marks = []
    except sqlite3.Error as exc:
        raise Unreadable(f'the SQLite document cannot be read: {exc}') from None
    finally:
        db.close()

    def build(node_id, master):
        row = rows.get(node_id)
        if master and master > 0:
            props = {}
            node = {'id': node_id, 'master': master, 'props': props, 'rich': False, 'runs': [], 'widgets': []}
        else:
            if row is None:
                raise Unreadable(f'node {node_id} is listed in children but missing in node')
            _, name, txt, syntax, tags, is_ro, is_rich, level = row
            is_ro, is_rich, level = int(is_ro or 0), int(is_rich or 0), int(level or 0)
            props = {'name': name or '', 'syntax': syntax or '', 'tags': tags or '', 'readonly': bool(is_ro & 1),
                     'bold': bool(is_rich >> 1 & 1),
                     'foreground': '#%06x' % (is_rich >> 3 & 0xffffff) if is_rich >> 2 & 1 else '',
                     'icon': is_ro >> 1, 'nosearch_me': bool(level & 1), 'nosearch_ch': bool(level >> 1 & 1)}
            runs = []
            if is_rich & 1:
                try:
                    body = ET.fromstring((txt or '<node/>').strip().encode())
                except ET.ParseError:
                    raise Unreadable(f'the rich text of node {node_id} is not valid XML') from None
                for child in body:
                    if child.tag == 'rich_text':
                        runs.append((element_text(child), {k: child.get(k) for k in RUN_ATTRS if child.get(k)}))
            else:
                runs.append((txt or '', {}))
            node = {'id': node_id, 'master': 0, 'props': props, 'rich': bool(is_rich & 1), 'runs': runs,
                    'widgets': sorted(widgets.get(node_id, []), key=lambda w: w[0])}
        node['children'] = [build(child, m) for child, _, _, m in sorted((l for l in links if l[1] == node_id),
                                                                           key=lambda l: l[2])]
        return node
    top = [build(child, m) for child, _, _, m in sorted((l for l in links if l[1] == 0), key=lambda l: l[2])]
    return {'nodes': top, 'bookmarks': marks}


def read_folder(path):
    root = Path(path)
    if not (root / 'subnodes.lst').is_file():
        raise Unreadable('the document folder has no subnodes.lst')

    def ids(folder):
        listing = folder / 'subnodes.lst'
        if not listing.is_file():
            return []
        return [int(x) for x in listing.read_text().split(',') if x.strip()]

    def build(folder):
        try:
            tree = ET.parse(folder / 'node.xml').getroot()
        except (ET.ParseError, OSError) as exc:
            raise Unreadable(f'{folder.name}/node.xml cannot be read: {exc}') from None
        element = tree.find('node')
        if element is None:
            raise Unreadable(f'{folder.name}/node.xml has no node')
        node = node_from_xml(element, blob_dir=folder)
        node['children'] = [build(folder / str(i)) for i in ids(folder)]
        return node
    marks_file = root / 'bookmarks.lst'
    marks = [int(x) for x in marks_file.read_text().split(',') if x.strip()] if marks_file.is_file() else []
    return {'nodes': [build(root / str(i)) for i in ids(root)], 'bookmarks': marks}


def extract_7z(path, password, work):
    # Stream the single document into a verifier-chosen name. Archive paths and
    # symbolic links never create files or select read targets on the verifier.
    listing = subprocess.run(['7z', 'l', '-slt', f'-p{password}', str(path)], capture_output=True,
                             text=True, timeout=120)
    entries = listing.stdout.partition('----------')[2]
    paths = re.findall(r'^Path = (.*)$', entries, re.M)
    if listing.returncode != 0 or len(paths) != 1 or 'Folder = +' in entries or 'Symbolic Link =' in entries:
        raise Unreadable('the protected document must contain one regular document')
    sizes = re.findall(r'^Size = (\d+)$', entries, re.M)
    if len(sizes) != 1 or int(sizes[0]) > 50 * 1024 * 1024:
        raise Unreadable('the protected document exceeds the size limit')
    target = Path(work) / 'document'
    with target.open('wb') as output:
        done = subprocess.run(['7z', 'x', '-so', '-bd', f'-p{password}', str(path)], stdout=output,
                              stderr=subprocess.PIPE, timeout=120)
    if done.returncode != 0 or target.stat().st_size > 50 * 1024 * 1024:
        raise Unreadable('the protected document cannot be opened with the expected password')
    return target


def read_document(path, password=None):
    """The raw model of a saved document; the format is detected from its content (folder, SQLite, 7-Zip, XML)."""
    path = Path(path)
    if path.is_dir():
        return read_folder(path)
    if not path.is_file():
        raise Unreadable('the document does not exist')
    head = path.read_bytes()[:16]
    if head.startswith(b'SQLite format 3'):
        return read_ctb(path)
    if head.startswith(b"7z\xbc\xaf'\x1c"):
        if password is None:
            raise Unreadable('the document is password protected')
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as work:
            return read_document(extract_7z(path, password, work))
    return read_ctd(path)


def format_of(path):
    """Storage format of a saved document by content: ctd, ctb, folder or 7z."""
    path = Path(path)
    if path.is_dir():
        return 'folder'
    head = path.read_bytes()[:16]
    if head.startswith(b'SQLite format 3'):
        return 'ctb'
    if head.startswith(b"7z\xbc\xaf'\x1c"):
        return '7z'
    return 'ctd'


# -- document projection -------------------------------------------------------------------------------------------


def paths_of(nodes):
    """Node id -> readable node path ("Parent/Child"; a repeated sibling name gets #2, #3, ...)."""
    result = {}

    def visit(siblings, prefix):
        seen = collections.Counter()
        for node in siblings:
            name = nfc(effective(node, siblings_cache)['props'].get('name', ''))
            seen[name] += 1
            label = name if seen[name] == 1 else f'{name}#{seen[name]}'
            path = prefix + label
            result.setdefault(node['id'], path)
            visit(node['children'], path + '/')
    siblings_cache.clear()
    siblings_cache.update(index(nodes))
    visit(nodes, '')
    return result


siblings_cache = {}


def index(nodes):
    found = {}
    for node in nodes:
        found[node['id']] = node
        found.update(index(node['children']))
    return found


def effective(node, by_id):
    """A shared node shows the name, properties and content of its master node."""
    if node.get('master'):
        master = by_id.get(node['master'])
        if master is not None and not master.get('master'):
            return master
    return node


def link_target(value, paths):
    """A link attribute in a serializer-neutral form: web URL, file or folder path, or node path with anchor."""
    kind, _, rest = (value or '').partition(' ')
    if kind == 'webs':
        return 'web ' + rest
    if kind in ('file', 'fold'):
        try:
            target = base64.b64decode(rest).decode('utf-8')
        except ValueError:
            target = rest
        return ('file ' if kind == 'file' else 'folder ') + target
    if kind == 'node':
        node_id, _, anchor = rest.partition(' ')
        try:
            path = paths.get(int(node_id), '?missing')
        except ValueError:
            path = '?missing'
        return 'node ' + path + (('#' + anchor) if anchor else '')
    return value


def run_attrs(attrs, paths):
    result = {}
    for key, value in attrs.items():
        if not value:
            continue
        if key in ('foreground', 'background'):
            value = color(value)
        elif key == 'link':
            value = link_target(value, paths)
        elif key == 'justification' and value == 'left':
            continue
        elif key == 'indent' and value == '0':
            continue
        result[key] = value
    return result


def widget_projection(widget, paths):
    w = dict(widget)
    data = w.pop('data', None)
    if w['kind'] == 'image':
        w.update(png_info(data or b''))
        w['link'] = link_target(w['link'], paths) if w['link'] else ''
    elif w['kind'] == 'file':
        w['sha256'] = hashlib.sha256(data or b'').hexdigest()
        w['size'] = len(data or b'')
        w['filename'] = nfc(w['filename'])
    elif w['kind'] == 'table':
        w['rows'] = [[nfc(c) for c in row] for row in w['rows']]
    elif w['kind'] in ('codebox', 'latex'):
        w['text'] = nfc(w['text'].replace('\r\n', '\n'))
    if w.get('justification') == 'left':
        w.pop('justification')
    return w


def content(node, paths):
    """Text (one placeholder character per widget), merged formatting runs and widgets of one node."""
    chars = []
    for text, attrs in node['runs']:
        normal = run_attrs(attrs, paths)
        for ch in nfc(text.replace('\r\n', '\n')):
            # Formatting of a line end is not visible; paragraph properties are kept on the visible characters.
            chars.append((ch, () if ch == '\n' else tuple(sorted(normal.items()))))
    widgets = []
    for offset, widget in sorted(node['widgets'], key=lambda w: w[0]):
        position = max(0, min(offset, len(chars)))
        chars.insert(position, (WIDGET, ()))
        widgets.append(dict(widget_projection(widget, paths), at=position))
    # Re-number widget positions after all insertions (offsets are positions in the final text).
    positions = [i for i, (ch, _) in enumerate(chars) if ch == WIDGET]
    for widget, position in zip(widgets, positions):
        widget['at'] = position
    runs = []
    for ch, attrs in chars:
        if runs and runs[-1][1] == attrs:
            runs[-1][0] += ch
        else:
            runs.append([ch, attrs])
    text = ''.join(ch for ch, _ in chars)
    position, spans = 0, []
    for value, attributes in runs:
        if attributes:
            spans.append({'start': position, 'end': position + len(value), 'attributes': dict(attributes)})
        position += len(value)
    return {'text': text, 'runs': [[t, dict(a)] for t, a in runs if a], 'spans': spans, 'widgets': widgets}


def node_projection(node, by_id, paths):
    shown = effective(node, by_id)
    props = dict(shown['props'])
    props['name'] = nfc(props.get('name', ''))
    props['tags'] = nfc(props.get('tags', ''))
    result = {'props': props, 'children': [paths.get(c['id'], '') for c in node['children']]}
    if node.get('master'):
        result['shared_with'] = paths.get(node['master'], '?missing')
    if shown['rich']:
        result.update(content(shown, paths))
    else:
        result['text'] = nfc(''.join(t for t, _ in shown['runs']).replace('\r\n', '\n'))
    return result


def document_projection(raw):
    """{'tree': nested [name, [children]], 'nodes': {path: node projection}, 'bookmarks': [paths]}."""
    by_id = index(raw['nodes'])
    paths = paths_of(raw['nodes'])

    def tree(nodes):
        return [[nfc(effective(n, by_id)['props'].get('name', '')), tree(n['children'])] for n in nodes]
    nodes = {}

    def visit(siblings):
        for node in siblings:
            nodes[paths[node['id']]] = node_projection(node, by_id, paths)
            visit(node['children'])
    visit(raw['nodes'])
    return {'tree': tree(raw['nodes']), 'nodes': nodes,
            'bookmarks': [paths.get(b, '?missing') for b in raw['bookmarks']]}


# -- export projections --------------------------------------------------------------------------------------------


def text_projection(data):
    """Plain text with LF line ends, trailing spaces removed, runs of blank lines kept as one blank line."""
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise Unreadable('the text export is not UTF-8') from None
    lines = [line.rstrip() for line in nfc(text.lstrip('﻿')).replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    out = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    while out and not out[-1]:
        out.pop()
    return '\n'.join(out)


def node_page_name(name):
    """A node page reference without the trailing node id of the page name (Parent--Child_12.html#a ->
    Parent--Child.html#a); a single-file export's in-page reference (#Child_12.html) the same way."""
    page, hash_, fragment = name.lstrip('#').partition('#')
    return re.sub(r'_\d+(\.html)$', r'\1', page) + hash_ + fragment


STYLE_TAGS = {'strong': ('weight', 'heavy'), 'b': ('weight', 'heavy'), 'em': ('style', 'italic'), 'i': ('style', 'italic'),
              'code': ('family', 'monospace'), 'small': ('scale', 'small'), 'sup': ('scale', 'sup'),
              'sub': ('scale', 'sub'), 'u': ('underline', 'single'), 's': ('strikethrough', 'true'),
              'strike': ('strikethrough', 'true'), 'del': ('strikethrough', 'true')}
for level in range(1, 7):
    STYLE_TAGS[f'h{level}'] = ('scale', f'h{level}')
BLOCKS = {'p', 'div', 'br', 'ul', 'ol', 'li', 'table', 'tr', 'pre', 'hr', 'blockquote'}


def css(style):
    result = {}
    for declaration in (style or '').split(';'):
        key, _, value = declaration.partition(':')
        key, value = key.strip().lower(), value.strip().lower()
        if not key or not value:
            continue
        if key == 'color':
            result['foreground'] = color(value)
        elif key == 'background-color':
            result['background'] = color(value)
        elif key == 'text-decoration':
            if 'underline' in value:
                result['underline'] = 'single'
            if 'line-through' in value:
                result['strikethrough'] = 'true'
        elif key == 'font-weight' and value in ('bold', '700', '800', '900'):
            result['weight'] = 'heavy'
        elif key == 'font-style' and value == 'italic':
            result['style'] = 'italic'
        elif key == 'font-family' and 'mono' in value:
            result['family'] = 'monospace'
        elif key == 'text-align':
            result['justification'] = value
        elif key in ('indent', 'margin-left', 'padding-left'):
            result['indent:' + key] = value
    return result


def html_kind(html):
    from html_semantics import kind
    return kind(html)


def html_page_projection(html, folder):
    from html_semantics import page
    return page(html, folder)


def html_single_projection(html, folder):
    from html_semantics import single
    return single(html, folder)


def html_index_projection(html):
    from html_semantics import index
    return index(html)


def node_id_of(name):
    match = re.search(r'_(\d+)\.(txt|html)$', name)
    return match.group(1) if match else None


def pdf_projection(path):
    """Words (as a multiset), link targets and page size of a PDF export."""
    done = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(path), '-'], capture_output=True, timeout=120)
    if done.returncode != 0:
        raise Unreadable('the PDF export cannot be read')
    # Page numbers ("2/5") depend on the page layout and are left out.
    words = sorted(w for w in nfc(done.stdout.decode('utf-8', 'replace')).split() if not re.fullmatch(r'\d+/\d+', w))
    info = subprocess.run(['pdfinfo', '-url', str(path)], capture_output=True, text=True, timeout=60)
    urls = sorted(line.split(None, 2)[2].strip() for line in info.stdout.splitlines()[1:] if len(line.split(None, 2)) == 3)
    meta = subprocess.run(['pdfinfo', str(path)], capture_output=True, text=True, timeout=60).stdout
    size = re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', meta)
    return {'words': words, 'links': urls,
            'page_size': [round(float(size.group(1))), round(float(size.group(2)))] if size else None}
