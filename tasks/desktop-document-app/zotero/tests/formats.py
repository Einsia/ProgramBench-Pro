"""Serializer-neutral readings of exported documents and formatted citations.

Each reader turns one document into the data it carries: entries and their
fields, tags and their values, element trees with their text, template
parameters. Whitespace, field order inside an entry, attribute order and the
instance-specific parts of identifiers (the local library URI, generated node
ids) are normalized; values, entry order and the order of repeated fields
(authors) are kept.
"""
import csv
import html
from html.parser import HTMLParser
import io
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

LOCAL = re.compile(r'http://zotero\.org/users/local/[A-Za-z0-9]+/')
NODE_ID = re.compile(r'#item_\d+')


def local(text):
    """The instance's local library URI and generated RDF node ids, normalized."""
    return NODE_ID.sub('#item', LOCAL.sub('http://zotero.org/users/local/{local}/', text))


def spaces(text):
    return ' '.join(str(text).split())


def text_lines(text):
    return [line.rstrip() for line in text.replace('\r\n', '\n').replace('\r', '\n').strip('\n').split('\n')]


# ---------------------------------------------------------------------------------------------- BibTeX family
def _balanced(text, start, opening, closing):
    depth, i = 0, start
    while i < len(text):
        if text[i] == '\\':
            i += 2
            continue
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError('unbalanced BibTeX entry')


def bibtex(text):
    """Entries [{type, key, fields{name: value}}] in document order; @comment and preamble text are kept apart."""
    entries, i = [], 0
    while True:
        at = text.find('@', i)
        if at < 0:
            break
        match = re.match(r'@\s*([A-Za-z]+)\s*([{(])', text[at:])
        if not match:
            i = at + 1
            continue
        kind = match.group(1).lower()
        opening = match.group(2)
        closing = '}' if opening == '{' else ')'
        begin = at + match.end() - 1
        end = _balanced(text, begin, opening, closing)
        body = text[begin + 1:end]
        i = end + 1
        if kind in ('comment', 'preamble', 'string'):
            entries.append({'type': kind, 'body': spaces(body)})
            continue
        key, _, rest = body.partition(',')
        fields, j = {}, 0
        while j < len(rest):
            m = re.match(r'\s*([A-Za-z0-9_:\-.]+)\s*=\s*', rest[j:])
            if not m:
                break
            name = m.group(1).lower()
            j += m.end()
            if j < len(rest) and rest[j] == '{':
                k = _balanced(rest, j, '{', '}')
                value = rest[j + 1:k]
                j = k + 1
            elif j < len(rest) and rest[j] == '"':
                k = j + 1
                while k < len(rest) and rest[k] != '"':
                    k += 2 if rest[k] == '\\' else 1
                value = rest[j + 1:k]
                j = k + 1
            else:
                m2 = re.match(r'[^,]*', rest[j:])
                value = m2.group(0)
                j += m2.end()
            fields[name] = sorted(spaces(v) for v in value.split(',')) if name == 'keywords' else spaces(value)
            m3 = re.match(r'\s*,?', rest[j:])
            j += m3.end()
        entries.append({'type': kind, 'key': key.strip(), 'fields': fields})
    return entries


# ----------------------------------------------------------------------------------------- tagged line formats
def tagged(text, pattern, end=None):
    """Records of a tag-per-line format: [{tag: [values in order]}]; continuation lines join the previous value."""
    records, record, last = [], None, None
    for line in text_lines(text):
        match = re.match(pattern, line)
        if match:
            tag, value = match.group(1), match.group(2).strip()
            if record is None:
                record = {}
            if end and tag == end:
                records.append(record)
                record, last = None, None
                continue
            record.setdefault(tag, []).append(value)
            last = tag
        elif not line.strip():
            if end is None and record:
                records.append(record)
                record, last = None, None
        elif record is not None and last:
            record[last][-1] = (record[last][-1] + ' ' + line.strip()).strip()
    if record:
        records.append(record)
    return records


def ris(text):
    records = tagged(text, r'^([A-Z][A-Z0-9])  -\s?(.*)$', end='ER')
    for record in records:
        if 'KW' in record:
            record['KW'] = sorted(record['KW'])
    return records


def refer(text):
    records = tagged(text, r'^%(\S)\s?(.*)$')
    for record in records:
        if 'K' in record:
            record['K'] = sorted(record['K'])
    return records


# ---------------------------------------------------------------------------------------------------- JSON
def csl_json(text):
    items = json.loads(text)
    return json.loads(local(json.dumps(items, ensure_ascii=False)))


def csv_rows(text):
    rows = list(csv.reader(io.StringIO(text.lstrip('\ufeff'))))
    if not rows:
        return []
    header = rows[0]
    return [{name: sorted(v.strip() for v in value.split(';')) if name in ('Manual Tags', 'Automatic Tags') else value
             for name, value in zip(header, row) if value != ''} for row in rows[1:]]


# ------------------------------------------------------------------------------------------------------ XML
def _local_name(tag):
    return tag.split('}', 1)[1] if tag.startswith('{') else tag


def _namespace(tag):
    return tag[1:].split('}', 1)[0] if tag.startswith('{') else ''


def element(node):
    """[namespace-qualified tag, {attribute: value}, text, [children]] with children grouped by tag (stable)."""
    attributes = {('{%s}%s' % (_namespace(k), _local_name(k)) if k.startswith('{') else k): local(v)
                  for k, v in node.attrib.items()}
    children = sorted((element(child) for child in node), key=lambda child: (
        child[0], json.dumps(child, sort_keys=True) if _local_name(child[0]) in ('subject', 'topic', 'tagged') else ''))
    return [node.tag, dict(sorted(attributes.items())), spaces(local(node.text or '')), children]


def xml(text):
    return element(ET.fromstring(text.encode('utf-8') if isinstance(text, str) else text))


# ----------------------------------------------------------------------------------------------------- HTML
class _Tree(HTMLParser):
    VOID = {'br', 'img', 'hr', 'meta', 'link', 'input'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = ['#root', {}, []]
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = [tag, {k: (v or '') for k, v in sorted(attrs)}, []]
        self.stack[-1][2].append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1][2].append(data)


def html_tree(text):
    parser = _Tree()
    parser.feed(text)
    parser.close()
    return parser.root


def inner(node):
    """Inline HTML of a node: text and formatting tags with their attributes, whitespace collapsed."""
    parts = []
    for child in node[2]:
        if isinstance(child, str):
            parts.append(html.escape(child, quote=False))
        else:
            attributes = ''.join(f' {k}="{html.escape(v)}"' for k, v in child[1].items())
            parts.append(f'<{child[0]}{attributes}>{inner(child)}</{child[0]}>')
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()


def find_all(node, predicate):
    found = []
    for child in node[2]:
        if not isinstance(child, str):
            if predicate(child):
                found.append(child)
            found.extend(find_all(child, predicate))
    return found


def has_class(name):
    return lambda node: name in node[1].get('class', '').split()


def bibliography(text):
    """A CSL HTML bibliography: the body's style and each entry's inline HTML (COinS spans left out)."""
    tree = html_tree(text)
    bodies = find_all(tree, has_class('csl-bib-body'))
    if not bodies:
        raise ValueError('no csl-bib-body in the bibliography')
    body = bodies[0]
    entries = [inner(entry) for entry in find_all(body, has_class('csl-entry'))]
    style = ';'.join(sorted(spaces(part).replace(' ', '') for part in body[1].get('style', '').split(';') if part.strip()))
    return {'style': style, 'entries': entries}


def citation(text):
    """A formatted citation: its inline HTML without the outer span."""
    tree = html_tree(text)
    nodes = [child for child in tree[2] if not isinstance(child, str)]
    if len(nodes) == 1 and nodes[0][0] in ('span', 'div') and not nodes[0][1]:
        return inner(nodes[0])
    return inner(tree)


BLOCK_TAGS = r'(?:p|div|li|ul|ol|h[1-6]|blockquote|table|thead|tbody|tr|td|th)'


def note_html(text):
    """A note's content: its inline HTML with the editor's schema wrapper and the white space between block
    elements and at the inner edges of block elements removed."""
    tree = html_tree(text)
    nodes = [child for child in tree[2] if not (isinstance(child, str) and not child.strip())]
    if len(nodes) == 1 and not isinstance(nodes[0], str) and nodes[0][0] == 'div' and 'data-schema-version' in nodes[0][1]:
        tree = nodes[0]
    html = re.sub(r'>\s+<', '><', inner(tree))
    html = re.sub(rf'(<{BLOCK_TAGS}(?:\s[^>]*)?>)\s+', r'\1', html)
    return re.sub(rf'\s+(</{BLOCK_TAGS}>)', r'\1', html)


def html_text(text):
    """The visible text of an HTML fragment or document: one entry per block, white space collapsed."""
    tree = html_tree(text)
    blocks, current = [], []
    BLOCK = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'tr', 'br', 'title'}

    def walk(node):
        for child in node[2]:
            if isinstance(child, str):
                current.append(child)
            elif child[0] in ('script', 'style', 'head'):
                continue
            else:
                if child[0] in BLOCK:
                    flush()
                walk(child)
                if child[0] in BLOCK:
                    flush()

    def flush():
        line = spaces(''.join(current))
        current.clear()
        if line:
            blocks.append(line)
    walk(tree)
    flush()
    return blocks


def coins(text):
    """COinS spans: the ContextObject keys and values of each span, in document order."""
    tree = html_tree(text)
    result = []
    for span in find_all(tree, has_class('Z3988')):
        query = urllib.parse.parse_qs(span[1].get('title', ''), keep_blank_values=True)
        result.append({k: v for k, v in sorted(query.items())})
    return result


def bookmarks(text):
    """Netscape bookmark file: (title, link) of every bookmark, folder names, in document order."""
    tree = html_tree(text)
    links = [[spaces(inner(a)), a[1].get('href', '')] for a in find_all(tree, lambda n: n[0] == 'a')]
    folders = [spaces(inner(h)) for h in find_all(tree, lambda n: n[0] == 'h3')]
    return {'links': links, 'folders': folders}


def wikipedia(text):
    """Citation templates: [{template, parameters{name: value}}] in document order."""
    result = []
    for match in re.finditer(r'\{\{(.*?)\}\}', text, flags=re.S):
        parts = [part.strip() for part in match.group(1).split('|')]
        parameters = {}
        for part in parts[1:]:
            name, _, value = part.partition('=')
            parameters[name.strip()] = spaces(value)
        result.append({'template': parts[0], 'parameters': parameters})
    return result


def rtf_text(text):
    """The visible text of an RTF document (control words removed, \\par as line breaks, \\'xx and \\u decoded)."""
    out, i, depth, skip = [], 0, 0, []
    destination = False

    def put(value):
        if not destination:
            out.append(value)

    while i < len(text):
        char = text[i]
        if char == '{':
            depth += 1
            skip.append(destination)
            i += 1
            continue
        if char == '}':
            depth -= 1
            destination = skip.pop() if skip else False
            i += 1
            continue
        if char == '\\':
            match = re.match(r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)", text[i:], re.S)
            if match is None:
                break
            if match.group(1):
                word, arg = match.group(1), match.group(2)
                if word in ('par', 'line'):
                    put('\n')
                elif word == 'tab':
                    put('\t')
                elif word == 'u' and arg is not None:
                    put(chr(int(arg) % 65536))
                    i += match.end()
                    if i < len(text) and text[i] == '?':
                        i += 1
                    continue
                elif word in ('fonttbl', 'colortbl', 'stylesheet', 'info', 'pict', 'generator'):
                    destination = True
            elif match.group(3):
                put(bytes.fromhex(match.group(3)).decode('cp1252'))
            elif match.group(4) == '*':
                destination = True
            elif match.group(4) in '\\{}':
                put(match.group(4))
            elif match.group(4) in '\r\n':
                put('\n')
            elif match.group(4) == '~':
                put(' ')
            elif match.group(4) == '_':
                put('-')
            i += match.end()
            continue
        if not destination and char not in '\r\n':
            out.append(char)
        i += 1
    return [spaces(line) for line in ''.join(out).split('\n') if spaces(line)]


READERS = {'bibtex': bibtex, 'biblatex': bibtex, 'ris': ris, 'refer': refer, 'csljson': csl_json, 'csv': csv_rows,
           'mods': xml, 'tei': xml, 'rdf_zotero': xml, 'rdf_bibliontology': xml, 'rdf_dc': xml, 'coins': coins,
           'bookmarks': bookmarks, 'wikipedia': wikipedia, 'bib': bibliography, 'citation': citation, 'rtf': rtf_text,
           'xml': xml, 'text': text_lines, 'html-text': html_text, 'note': note_html}


def read(kind, text):
    return READERS[kind](text)
