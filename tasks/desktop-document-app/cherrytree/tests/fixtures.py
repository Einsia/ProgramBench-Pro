"""Deterministic CherryTree input documents, written by the verifier before an episode uses them.

A document is a tree of nodes; a rich-text node holds a sequence of text runs
(text plus formatting attributes) and anchored widgets (code boxes, tables,
images, anchors, embedded files, LaTeX equations); plain-text and code nodes
hold text only. The same document can be written in each of CherryTree's
storage formats from the format descriptions alone: XML (.ctd), SQLite (.ctb),
a folder of node files (multiple files), and the password-protected 7-Zip
variants (.ctz holding a .ctd, .ctx holding a .ctb). Nothing here reads the
application.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
from xml.sax.saxutils import escape, quoteattr

PASSWORD = 'cherry-7z'
TIME = 1704067200          # 2024-01-01 00:00:00 UTC, every timestamp of an input document
FORMATS = ('ctd', 'ctb', 'folder', 'ctz', 'ctx')
EXTENSION = {'ctd': '.ctd', 'ctb': '.ctb', 'folder': '', 'ctz': '.ctz', 'ctx': '.ctx'}
LATEX_FILENAME = '__ct_special.tex'
# Attributes of a text run, in CherryTree's own names and value spellings.
RUN_ATTRIBUTES = ('weight', 'style', 'underline', 'strikethrough', 'foreground', 'background', 'scale', 'family',
                  'justification', 'indent', 'link')


@dataclasses.dataclass
class Widget:
    kind: str                  # codebox, table, image, anchor, file, latex
    props: dict
    justification: str = 'left'


@dataclasses.dataclass
class Node:
    id: int
    name: str
    content: list = dataclasses.field(default_factory=list)   # rich: (text, attrs) tuples and Widgets; else [text]
    children: list = dataclasses.field(default_factory=list)
    syntax: str = 'custom-colors'                              # custom-colors = rich text, plain-text, or a language
    tags: str = ''
    readonly: bool = False
    bold: bool = False
    foreground: str = ''
    icon: int = 0
    nosearch_me: bool = False
    nosearch_ch: bool = False
    master: int = 0            # a shared node: the id of the node whose content it shows

    @property
    def rich(self):
        return self.syntax == 'custom-colors'


@dataclasses.dataclass
class Document:
    nodes: list
    bookmarks: tuple = ()


def run(text, **attrs):
    return (text, {k: str(v) for k, v in attrs.items()})


def png(width, height, color, *, mark=None):
    """A small deterministic RGB PNG: a solid color with an optional 8x8 square of another color at the top left."""
    import struct
    import zlib
    rows = b''
    for y in range(height):
        rows += b'\x00' + b''.join(bytes(mark if mark and x < 8 and y < 8 else color) for x in range(width))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


# -- serialization -------------------------------------------------------------------------------------------------


def walk(nodes, parent=None, level=0):
    for sequence, node in enumerate(nodes, 1):
        yield node, parent, level, sequence
        yield from walk(node.children, node, level + 1)


def pieces(node):
    """Rich runs and widgets with the character offset of each widget (every widget takes one character)."""
    offset, runs, widgets = 0, [], []
    for item in node.content:
        if isinstance(item, Widget):
            widgets.append((offset, item))
            offset += 1
        else:
            runs.append(item)
            offset += len(item[0])
    return runs, widgets


def plain_text(node):
    return ''.join(item if isinstance(item, str) else item[0] for item in node.content)


def run_xml(text, attrs):
    attributes = ''.join(f' {key}={quoteattr(attrs[key])}' for key in RUN_ATTRIBUTES if attrs.get(key))
    return f'<rich_text{attributes}>{escape(text)}</rich_text>'


def table_xml(props, offset=None, justification='left'):
    rows = props['rows']
    attributes = ''
    if offset is not None:
        attributes = f' char_offset="{offset}" justification="{justification}"'
        attributes += f' col_min="{props.get("col_min", 60)}" col_max="{props.get("col_max", 60)}"'
    widths = props.get('col_widths') or ','.join(['0'] * len(rows[0]))
    attributes += f' col_widths="{widths}"'
    if props.get('light'):
        attributes += ' is_light="1"'
    # The header row is stored last.
    body = ''.join('<row>' + ''.join(f'<cell>{escape(c)}</cell>' for c in row) + '</row>' for row in rows[1:] + rows[:1])
    return f'<table{attributes}>{body}</table>'


def codebox_xml(props, offset, justification):
    return (f'<codebox char_offset="{offset}" justification="{justification}" frame_width="{props.get("width", 500)}" '
            f'frame_height="{props.get("height", 100)}" width_in_pixels="{int(props.get("pixels", True))}" '
            f'syntax_highlighting="{props.get("syntax", "plain-text")}" highlight_brackets="{int(props.get("brackets", True))}" '
            f'show_line_numbers="{int(props.get("line_numbers", False))}">{escape(props["text"])}</codebox>')


def image_xml(widget, offset, blobs=None):
    """encoded_png element; blobs collects multifile blobs (sha256 name -> bytes) instead of inline base64."""
    p, j = widget.props, widget.justification
    head = f'<encoded_png char_offset="{offset}" justification="{j}"'
    if widget.kind == 'anchor':
        return head + f' anchor={quoteattr(p["name"])}/>'
    if widget.kind == 'latex':
        return head + f' filename="{LATEX_FILENAME}">{escape(p["text"])}</encoded_png>'
    data = p['data'] if widget.kind == 'file' else p['png']
    if widget.kind == 'file':
        head += f' filename={quoteattr(p["filename"])} time="{p.get("time", TIME)}"'
    elif p.get('link'):
        head += f' link={quoteattr(p["link"])}'
    if blobs is not None:
        digest = hashlib.sha256(data).hexdigest()
        suffix = Path(p['filename']).suffix if widget.kind == 'file' else '.png'
        blobs[digest + suffix] = data
        return head + f' sha256sum="{digest}"/>'
    return head + f'>{base64.b64encode(data).decode()}</encoded_png>'


def widget_xml(widget, offset, blobs=None):
    if widget.kind == 'codebox':
        return codebox_xml(widget.props, offset, widget.justification)
    if widget.kind == 'table':
        return table_xml(widget.props, offset, widget.justification)
    return image_xml(widget, offset, blobs)


def node_attributes(node):
    if node.master:
        return f'unique_id="{node.id}" master_id="{node.master}"'
    return (f'unique_id="{node.id}" master_id="0" name={quoteattr(node.name)} prog_lang="{node.syntax}" '
            f'tags={quoteattr(node.tags)} readonly="{int(node.readonly)}" nosearch_me="{int(node.nosearch_me)}" '
            f'nosearch_ch="{int(node.nosearch_ch)}" custom_icon_id="{node.icon}" is_bold="{int(node.bold)}" '
            f'foreground="{node.foreground}" ts_creation="{TIME}" ts_lastsave="{TIME}"')


def node_body(node, blobs=None):
    """The content elements of one node: rich_text runs, then the widgets with their offsets."""
    if node.master:
        return ''
    if not node.rich:
        return run_xml(plain_text(node), {})
    runs, widgets = pieces(node)
    return ''.join(run_xml(t, a) for t, a in runs) + ''.join(widget_xml(w, o, blobs) for o, w in widgets)


def write_ctd(document, path):
    def element(node, depth):
        pad = '  ' * depth
        children = ''.join(element(child, depth + 1) for child in node.children)
        if node.master:
            return f'{pad}<node {node_attributes(node)}/>\n'
        return f'{pad}<node {node_attributes(node)}>{node_body(node)}\n{children}{pad}</node>\n'
    text = '<?xml version="1.0" encoding="UTF-8"?>\n<cherrytree>\n'
    text += f'  <bookmarks list="{",".join(str(b) for b in document.bookmarks)}"/>\n'
    text += ''.join(element(node, 1) for node in document.nodes) + '</cherrytree>\n'
    Path(path).write_text(text, encoding='utf-8')


SCHEMA = '''CREATE TABLE node (node_id INTEGER UNIQUE,name TEXT,txt TEXT,syntax TEXT,tags TEXT,is_ro INTEGER,is_richtxt INTEGER,has_codebox INTEGER,has_table INTEGER,has_image INTEGER,level INTEGER,ts_creation INTEGER,ts_lastsave INTEGER);
CREATE TABLE codebox (node_id INTEGER,offset INTEGER,justification TEXT,txt TEXT,syntax TEXT,width INTEGER,height INTEGER,is_width_pix INTEGER,do_highl_bra INTEGER,do_show_linenum INTEGER);
CREATE TABLE grid (node_id INTEGER,offset INTEGER,justification TEXT,txt TEXT,col_min INTEGER,col_max INTEGER);
CREATE TABLE image (node_id INTEGER,offset INTEGER,justification TEXT,anchor TEXT,png BLOB,filename TEXT,link TEXT,time INTEGER);
CREATE TABLE children (node_id INTEGER UNIQUE,father_id INTEGER,sequence INTEGER, master_id INTEGER);
CREATE TABLE bookmark (node_id INTEGER UNIQUE,sequence INTEGER);'''


def write_ctb(document, path):
    path = Path(path)
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for node, parent, level, sequence in walk(document.nodes):
        db.execute('INSERT INTO children VALUES (?,?,?,?)', (node.id, parent.id if parent else 0, sequence, node.master))
        if node.master:
            continue
        runs, widgets = pieces(node) if node.rich else ([], [])
        if node.rich:
            txt = '<?xml version="1.0" encoding="UTF-8"?>\n<node>' + ''.join(run_xml(t, a) for t, a in runs) + '</node>'
        else:
            txt = plain_text(node)
        kinds = {w.kind for _, w in widgets}
        is_ro = int(node.readonly) | (node.icon << 1)
        is_richtxt = int(node.rich) | (0x02 if node.bold else 0)
        if node.foreground:
            is_richtxt |= 0x04 | (int(node.foreground[1:], 16) << 3)
        search = int(node.nosearch_me) | (int(node.nosearch_ch) << 1)
        db.execute('INSERT INTO node VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (node.id, node.name, txt, node.syntax, node.tags, is_ro, is_richtxt, int('codebox' in kinds),
                    int('table' in kinds), int(bool(kinds - {'codebox', 'table'})), search, TIME, TIME))
        for offset, w in widgets:
            p = w.props
            if w.kind == 'codebox':
                db.execute('INSERT INTO codebox VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (node.id, offset, w.justification, p['text'], p.get('syntax', 'plain-text'), p.get('width', 500),
                            p.get('height', 100), int(p.get('pixels', True)), int(p.get('brackets', True)),
                            int(p.get('line_numbers', False))))
            elif w.kind == 'table':
                db.execute('INSERT INTO grid VALUES (?,?,?,?,?,?)',
                           (node.id, offset, w.justification, '<?xml version="1.0" encoding="UTF-8"?>\n' + table_xml(p) + '\n',
                            p.get('col_min', 60), p.get('col_max', 60)))
            else:
                anchor = p['name'] if w.kind == 'anchor' else ''
                blob = {'image': p.get('png'), 'file': p.get('data'), 'latex': p.get('text', '').encode()}.get(w.kind)
                filename = p['filename'] if w.kind == 'file' else LATEX_FILENAME if w.kind == 'latex' else ''
                link = p.get('link', '') if w.kind == 'image' else ''
                db.execute('INSERT INTO image VALUES (?,?,?,?,?,?,?,?)',
                           (node.id, offset, w.justification, anchor, blob, filename, link,
                            p.get('time', TIME) if w.kind == 'file' else 0))
    for sequence, bookmark in enumerate(document.bookmarks, 1):
        db.execute('INSERT INTO bookmark VALUES (?,?)', (bookmark, sequence))
    db.commit()
    db.close()


def write_folder(document, path):
    root = Path(path)
    root.mkdir(parents=True)

    def write(nodes, folder):
        (folder / 'subnodes.lst').write_text(','.join(str(n.id) for n in nodes))
        for node in nodes:
            target = folder / str(node.id)
            target.mkdir()
            blobs = {}
            if node.master:
                body = f'  <node {node_attributes(node)}/>\n'
            else:
                body = f'  <node {node_attributes(node)}>{node_body(node, blobs)}\n  </node>\n'
            (target / 'node.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<cherrytree>\n' + body +
                                             '</cherrytree>\n', encoding='utf-8')
            for name, data in blobs.items():
                (target / name).write_bytes(data)
            if node.children:
                write(node.children, target)
    write(document.nodes, root)
    (root / 'bookmarks.lst').write_text(','.join(str(b) for b in document.bookmarks))


def write_7z(inner, path, password=PASSWORD):
    """A password-protected 7-Zip archive holding one document file (as CherryTree's encrypted formats)."""
    path = Path(path)
    path.unlink(missing_ok=True)
    os.utime(inner, (TIME, TIME))
    subprocess.run(['7z', 'a', '-t7z', '-bd', '-y', f'-p{password}', str(path.resolve()), inner.name], cwd=inner.parent,
                   check=True, capture_output=True)


def write(document, folder, stem, fmt, password=PASSWORD):
    """Write document as folder/stem<extension> in one storage format; returns the path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (stem + EXTENSION[fmt])
    if fmt == 'ctd':
        write_ctd(document, target)
    elif fmt == 'ctb':
        write_ctb(document, target)
    elif fmt == 'folder':
        write_folder(document, target)
    else:
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as work:
            inner = Path(work) / (stem + ('.ctd' if fmt == 'ctz' else '.ctb'))
            (write_ctd if fmt == 'ctz' else write_ctb)(document, inner)
            write_7z(inner, target, password)
    return target


def files_of(path):
    """(relative name, bytes) of a written document file or folder, for upload."""
    path = Path(path)
    if path.is_file():
        return [(path.name, path.read_bytes())]
    return [(f'{path.name}/{p.relative_to(path)}', p.read_bytes()) for p in sorted(path.rglob('*')) if p.is_file()]


# -- the corpus ----------------------------------------------------------------------------------------------------

def b64(path):
    return base64.b64encode(path.encode()).decode()


def rich(id, name, *content, children=(), **props):
    return Node(id, name, [run(c) if isinstance(c, str) else c for c in content], list(children), **props)


def plain(id, name, text, syntax='plain-text', children=(), **props):
    return Node(id, name, [text], list(children), syntax=syntax, **props)


def formatting():
    """One formatting feature per node."""
    para = '\n'
    nodes = [
        rich(11, 'Bold', 'Plain start, ', run('strong words', weight='heavy'), ' and plain end.'),
        rich(12, 'Italic', 'Before ', run('slanted phrase', style='italic'), ' after.'),
        rich(13, 'Underline', run('underlined line', underline='single'), para, 'next line'),
        rich(14, 'Strikethrough', 'keep ', run('removed', strikethrough='true'), ' keep'),
        rich(15, 'Heading 1', run('Chapter title', scale='h1'), para, 'Body under the chapter.'),
        rich(16, 'Heading 2', run('Section title', scale='h2'), para, 'Body under the section.'),
        rich(17, 'Heading 3', run('Subsection title', scale='h3'), para, 'Body under the subsection.'),
        rich(18, 'Heading 4 to 6', run('Level four', scale='h4'), para, run('Level five', scale='h5'), para,
             run('Level six', scale='h6'), para),
        rich(19, 'Small', 'normal ', run('fine print', scale='small')),
        rich(20, 'Superscript', 'E = mc', run('2', scale='sup'), ' and x', run('n+1', scale='sup')),
        rich(21, 'Subscript', 'H', run('2', scale='sub'), 'O and CO', run('2', scale='sub')),
        rich(22, 'Monospace', 'Run ', run('make install', family='monospace'), ' as root.'),
        rich(23, 'Foreground', 'A ', run('red', foreground='#ffff00000000'), ' and a ', run('blue', foreground='#00000000ffff'),
             ' word.'),
        rich(24, 'Background', 'A ', run('highlighted', background='#ffffffff0000'), ' word.'),
        rich(25, 'Combined', run('bold italic red', weight='heavy', style='italic', foreground='#cccc00000000'), ' then ',
             run('underlined mono', underline='single', family='monospace')),
        rich(26, 'Centered', run('Centered paragraph', justification='center'), para, 'Left paragraph'),
        rich(27, 'Right aligned', run('Right paragraph', justification='right'), para, 'Left paragraph'),
        rich(28, 'Filled', run('Filled paragraph with several words to justify', justification='fill')),
        rich(29, 'Indented', 'Level zero', para, run('Level one', indent='1'), para, run('Level two', indent='2'), para),
        rich(30, 'Heading with styles', run('Bold ', scale='h2', weight='heavy'), run('italic heading', scale='h2', style='italic')),
        rich(31, 'Markup characters', 'Tags <b>not bold</b> & "quotes" \'single\' > end'),
        rich(32, 'Whitespace', 'two  spaces\tand a tab', para, para, '   leading spaces', para, 'trailing   '),
        rich(33, 'Empty node'),
        rich(34, 'Strike and underline', run('both lines', strikethrough='true', underline='single'), ' none'),
    ]
    return Document(nodes)


def lists():
    nodes = [
        rich(41, 'Bulleted', 'Shopping:\n• apples\n• pears\n    ◇ green pears\n• plums\n'),
        rich(42, 'Numbered', 'Steps:\n1. open\n2. edit\n3. save\n'),
        rich(43, 'To-do', 'Tasks:\n☐ write\n☑ review\n☒ dropped\n'),
        rich(44, 'Mixed lists', '1. first\n• bullet inside\n2. second\n☐ check\n'),
        rich(45, 'Horizontal rule', 'above\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\nbelow'),
        rich(46, 'Special characters', 'Arrows → ← ↔, math ≤ ≥ ≠ ± ∞, currency € £ ¥, marks © ® ™'),
    ]
    return Document(nodes)


def structure():
    """Hierarchy, sibling order and node names (including characters that file names cannot hold)."""
    deep = rich(66, 'Level 6', 'deepest')
    for level, id in ((5, 65), (4, 64), (3, 63), (2, 62)):
        deep = rich(id, f'Level {level}', f'level {level} text', children=[deep])
    nodes = [
        rich(61, 'Level 1', 'top of the chain', children=[deep]),
        rich(70, 'Siblings', 'parent of three', children=[rich(73, 'Zulu', 'z'), rich(71, 'Alpha', 'a'), rich(72, 'Mike', 'm')]),
        rich(80, 'Name characters', 'names with characters file systems reject', children=[
            rich(81, 'slash/back\\slash', 'slashes'),
            rich(82, 'star*question?colon:', 'wildcards'),
            rich(83, 'angle <left> pipe | quote "', 'brackets'),
            rich(84, '  padded name  ', 'padding'),
            rich(85, 'two words here', 'spaces'),
            rich(86, 'Ünïcødé 名前 имя', 'unicode'),
            rich(87, 'Same name', 'first of two'),
            rich(88, 'Same name', 'second of two'),
            rich(89, 'L' + 'o' * 170 + 'ng', 'a very long name'),
        ]),
        rich(1000, 'Large id', 'id one thousand'),
        rich(5, 'Small id', 'id five'),
    ]
    return Document(nodes)


def codeboxes():
    py = 'def greet(name):\n    return f"hello {name}"\n\nprint(greet("tree"))'
    nodes = [
        rich(101, 'Python box', 'Code:\n', Widget('codebox', {'text': py, 'syntax': 'python3'}), '\nend'),
        rich(102, 'C box', Widget('codebox', {'text': 'int main(void)\n{\n    return 0;\n}', 'syntax': 'c', 'line_numbers': True})),
        rich(103, 'Shell box', 'Run:\n', Widget('codebox', {'text': 'for f in *.txt; do\n  echo "$f"\ndone', 'syntax': 'sh',
                                                              'width': 80, 'pixels': False, 'height': 60})),
        rich(104, 'Plain box', Widget('codebox', {'text': 'no highlighting <here> & there', 'syntax': 'plain-text'}),
             ' after the box'),
        rich(105, 'Two boxes', 'first:\n', Widget('codebox', {'text': 'SELECT 1;', 'syntax': 'sql'}), '\nsecond:\n',
             Widget('codebox', {'text': '{"a": [1, 2]}', 'syntax': 'json'}), '\n'),
        rich(106, 'Centered box', Widget('codebox', {'text': 'x = 1', 'syntax': 'python3'}, 'center'), '\ncaption'),
        rich(107, 'Empty box', 'before\n', Widget('codebox', {'text': '', 'syntax': 'plain-text'}), '\nafter'),
    ]
    return Document(nodes)


def tables():
    nodes = [
        rich(121, 'Simple table', 'Prices:\n', Widget('table', {'rows': [['Item', 'Price'], ['Tea', '3'], ['Cake', '5']]}),
             '\nend of table'),
        rich(122, 'Wide table', Widget('table', {'rows': [['A', 'B', 'C', 'D', 'E'], ['1', '2', '3', '4', '5'],
                                                         ['6', '7', '8', '9', '10']]})),
        rich(123, 'Header only', Widget('table', {'rows': [['Only', 'Header']]})),
        rich(124, 'Empty cells', Widget('table', {'rows': [['Key', 'Value'], ['', 'no key'], ['no value', '']]})),
        rich(125, 'Markup cells', Widget('table', {'rows': [['Code', 'Meaning'], ['<b>', 'tag & "quote"'], ['a|b', 'pipe']]})),
        rich(126, 'Unicode cells', Widget('table', {'rows': [['语言', 'Слово'], ['中文', 'русский'], ['日本語', 'ελληνικά']]})),
        rich(127, 'Light table', Widget('table', {'rows': [['Light', 'Table'], ['x', 'y']], 'light': True})),
        rich(128, 'Multiline cell', Widget('table', {'rows': [['Name', 'Address'], ['Ann', 'Line one\nLine two']]})),
        rich(129, 'Two tables', Widget('table', {'rows': [['T1'], ['a']]}), ' and ', Widget('table', {'rows': [['T2'], ['b']]})),
    ]
    return Document(nodes)


def media():
    """Images, anchors, embedded files and LaTeX equations."""
    nodes = [
        rich(141, 'Image', 'A picture:\n', Widget('image', {'png': png(40, 24, (200, 30, 30), mark=(255, 255, 255))}),
             '\ncaption below'),
        rich(142, 'Linked image', Widget('image', {'png': png(16, 16, (20, 120, 220)), 'link': 'webs https://example.org/pic'}),
             ' click it'),
        rich(143, 'Two images', Widget('image', {'png': png(10, 30, (0, 160, 0))}), ' and ',
             Widget('image', {'png': png(30, 10, (90, 90, 90), mark=(255, 200, 0))}, 'center')),
        rich(144, 'Anchor', 'Top text\n', Widget('anchor', {'name': 'target-spot'}), 'Text after the anchor'),
        rich(145, 'Embedded text file', 'Attachment: ', Widget('file', {'filename': 'notes.txt', 'data': b'line one\nline two\n'})),
        rich(146, 'Embedded image file', Widget('file', {'filename': 'chart.png', 'data': png(20, 20, (10, 10, 120))}), ' attached'),
        rich(147, 'Unicode file name', Widget('file', {'filename': 'отчёт 2024.csv', 'data': 'a,b\n1,2\n'.encode()})),
        rich(148, 'LaTeX', 'Formula:\n', Widget('latex', {'text': '\\documentclass{article}\n\\pagestyle{empty}\n'
                                                          '\\begin{document}\n$e^{i\\pi}+1=0$\n\\end{document}'}), '\ndone'),
    ]
    return Document(nodes)


def links():
    nodes = [
        rich(161, 'Web links', 'Visit ', run('the example site', link='webs https://example.com/path?q=1&r=2'), ' or ',
             run('a mail page', link='webs http://example.net/mail')),
        rich(162, 'Node link', 'See ', run('the target node', link='node 166'), ' for details.'),
        rich(163, 'Anchor link', 'Jump to ', run('the spot', link='node 166 spot'), '.'),
        rich(164, 'File link', 'Open ', run('the readme', link='file ' + b64('/srv/docs/readme.txt')), '.'),
        rich(165, 'Folder link', 'Browse ', run('the docs folder', link='fold ' + b64('/srv/docs')), '.'),
        rich(166, 'Link target', 'Target text\n', Widget('anchor', {'name': 'spot'}), 'anchored part'),
        rich(167, 'Styled link', run('bold link', link='webs https://example.com/b', weight='heavy'), ' plain'),
        rich(168, 'Link in heading', run('Heading link', scale='h2', link='node 161')),
    ]
    return Document(nodes)


def node_types():
    nodes = [
        plain(181, 'Plain text node', 'Plain text keeps <tags> & **marks**\n  indentation\n'),
        plain(182, 'Python node', 'import os\n\nfor key in sorted(os.environ):\n    print(key)\n', syntax='python3'),
        plain(183, 'C node', '#include <stdio.h>\nint main(void) { puts("hi"); return 0; }\n', syntax='c'),
        plain(184, 'Shell node', 'echo "$HOME" | wc -c\n', syntax='sh'),
        plain(185, 'XML node', '<?xml version="1.0"?>\n<root attr="1"/>\n', syntax='xml'),
        rich(186, 'Read-only node', 'cannot be edited', readonly=True),
        rich(187, 'Bold red node', 'node with a bold red name', bold=True, foreground='#cc0000'),
        rich(188, 'Tagged node', 'node with tags', tags='alpha beta'),
        rich(189, 'Icon node', 'node with a custom icon', icon=12),
        rich(190, 'Hidden from search', 'excluded', nosearch_me=True, nosearch_ch=True,
             children=[rich(191, 'Child of hidden', 'child text')]),
        rich(192, 'Shared master', 'Shared text visible in two places', children=[rich(193, 'Shared child', 'child')]),
        Node(194, '', master=192),
    ]
    return Document(nodes, bookmarks=(186, 181))


def unicode_text():
    nodes = [
        rich(201, 'Русский', 'Съешь же ещё этих мягких французских булок.'),
        rich(202, '中文', '我能吞下玻璃而不伤身体。'),
        rich(203, 'العربية', 'أستطيع أكل الزجاج و هذا لا يؤلمني.'),
        rich(204, 'עברית', 'אני יכול לאכול זכוכית וזה לא מזיק לי.'),
        rich(205, 'Emoji', 'Weather ☀ ☂ ❄ and faces ☺ ☻'),
        rich(206, 'Ελληνικά', 'Μπορώ να φάω σπασμένα γυαλιά χωρίς να πάθω τίποτα.'),
        rich(207, 'Mixed scripts', 'English, Русский, 中文 and ελληνικά in one line'),
    ]
    return Document(nodes)


def kitchen():
    """A little of everything, for the storage format and option matrices."""
    return Document([
        rich(1, 'Overview', run('Project notes', scale='h1'), '\nSome ', run('bold', weight='heavy'), ' and ',
             run('italic', style='italic'), ' text with a ', run('link', link='node 4'), '.\n', children=[
                 rich(2, 'Tasks', '☐ draft\n☑ review\n', Widget('table', {'rows': [['Task', 'Owner'], ['draft', 'Ann']]})),
                 plain(3, 'Script', 'echo ready\n', syntax='sh'),
             ]),
        rich(4, 'Media', 'Image: ', Widget('image', {'png': png(12, 12, (250, 120, 0))}), '\nFile: ',
             Widget('file', {'filename': 'k.txt', 'data': b'kitchen\n'}), '\nCode:\n',
             Widget('codebox', {'text': 'print(1)', 'syntax': 'python3'}), '\n'),
        rich(5, 'Ünïcødé', 'Привет, 世界'),
    ], bookmarks=(4,))


CORPUS = {'formatting': formatting, 'lists': lists, 'structure': structure, 'codeboxes': codeboxes, 'tables': tables,
          'media': media, 'links': links, 'node-types': node_types, 'unicode': unicode_text, 'kitchen': kitchen}


def document(name):
    return CORPUS[name]()


def version_one():
    return Document([rich(1, 'One', 'version one text')])


def version_two():
    return Document([rich(1, 'One', 'second edition words'), rich(2, 'Two', 'more nodes now')])


def empty_tree():
    return Document([])


def notebook():
    """The everyday document of the GUI episodes: short distinct node names and lines."""
    return Document([
        rich(1, 'Inbox', 'Meeting notes\nCall the plumber tomorrow.\nBuy milk and eggs.\nRenew the library card.\n'),
        rich(2, 'Projects', 'Ideas for the year.\n', children=[
            rich(3, 'Garden', 'Plant tomatoes in May.\nWater twice a week.\n'),
            rich(4, 'Kitchen', 'Paint the cabinets.\n'),
        ]),
        rich(5, 'Archive', 'Old receipts and letters.\n'),
        plain(6, 'Script', 'echo hello\n', syntax='sh'),
    ])


def search_notebook():
    d=notebook()
    d.nodes[0]=rich(1, 'Inbox', 'Meeting notes\nCall the plumber tomorrow.\nBuy milk and eggs.\nBuy milk\tand\teggs.\nBuy milk   and eggs.\nKeep milk and eggplant.\n')
    return d


def pattern_png(width=160, height=100):
    import struct,zlib
    colors=((240,40,20),(20,180,40),(30,70,230),(250,210,20))
    raw=b''.join(b'\x00'+b''.join(bytes(colors[(y>=height//2)*2+(x>=width//2)]) for x in range(width)) for y in range(height))
    def chunk(k,v):return struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


def advanced():
    image=Widget('image',{'png':pattern_png()})
    table=Widget('table',{'rows':[['Item','Count','Note'],['Zebra','2','z'],['Apple','5',''],['Mango','3','sweet']]})
    code=Widget('codebox',{'text':'old value\nsecond line','syntax':'plain-text','width':500,'height':100})
    return Document([
        rich(1,'Image',image),
        rich(2,'Attachment',Widget('file',{'filename':'plan.txt','data':b'Monday: outline\nTuesday: review\n'})),
        rich(3,'Table',table),rich(4,'Code',code),
        rich(5,'Rich',run('Bold title',weight='heavy'),'\nBody ',run('link',link='webs https://example.com'),'\n',image,'\n',code,'\n',table,'\n'),
        rich(6,'Destination','Destination start.\n'),
        rich(7,'Headings',run('Chapter',scale='h1'),'\nChapter body\n',run('Section',scale='h2'),'\nSection body\n',run('Detail',scale='h3'),'\nDetail body\n'),
        plain(8,'Cleanup','alpha   \n\tbeta\tgamma  \n'),
        rich(9,'Format','Source phrase\nTarget phrase\nLatest phrase\n'),
        rich(10,'Repeated','same phrase / same phrase / same phrase\n'),
    ])


def search_tree():
    return Document([
        rich(1,'Alpha','cat catapult CAT\n',tags='urgent',children=[rich(2,'Child','cat child\n')]),
        rich(3,'Excluded','cat secret\n',nosearch_me=True,children=[rich(4,'Nested','cat nested\n')]),
        rich(5,'Other','dog cat\n',tags='urgent'),
    ])


EXTRA = {'advanced': advanced, 'search-tree': search_tree, 'search-notebook': search_notebook, 'version-one': version_one, 'version-two': version_two, 'empty-tree': empty_tree, 'notebook': notebook}
# Files that are not valid documents of the format their name claims.
RAW = {
    'truncated-xml': b'<?xml version="1.0" encoding="UTF-8"?>\n<cherrytree>\n  <node unique_id="1" name="cut',
    'not-xml': b'This is a plain sentence, not a document.\n',
    'empty-file': b'',
    'bad-sqlite': b'SQLite format 3\x00' + bytes(84),
}


def document_of(name):
    return (CORPUS.get(name) or EXTRA[name])()


def input_files(entry, folder):
    """(relative name, bytes) of one input entry: {'document', 'format', 'as'?, 'password'?} or {'raw', 'as'}."""
    if 'import' in entry:
        import imports
        return imports.files(entry['import'])
    if 'text' in entry:
        return [(entry['as'], entry['text'].encode('utf-8'))]
    if 'image' in entry:
        return [(entry['as'], png(160, 100, (240, 100, 40), mark=(20, 60, 220)))]
    if 'raw' in entry:
        return [(entry['as'], RAW[entry['raw']])]
    if 'copy' in entry:
        source = write(document_of(entry['copy']), folder, 'copy-source', 'ctd')
        return [(entry['as'], source.read_bytes())]
    stem = entry.get('as', entry['document'])
    path = write(document_of(entry['document']), folder, stem, entry['format'], entry.get('password', PASSWORD))
    return files_of(path)
