"""Serializer-neutral normalization of the documents the application produces.

Everything here runs verifier-side on bytes fetched through the runtime
(download, clipboard). Markdown is compared as text with only line endings
normalized; exported HTML is reduced to a semantic tree (tags, text and the
attributes that carry meaning, without styling, classes or editor-only
scaffolding); exported PDF is reduced to page sizes and extractable text;
images to format, size and a coarse pixel signature.
"""
from __future__ import annotations

import html.parser
import io
import re


# -- markdown ------------------------------------------------------------------------------------------------------


def normalize_markdown(data: bytes) -> str:
    """Decode a saved Markdown/text document; only line endings are normalized to LF."""
    text = data.decode('utf-8')
    if text.startswith('﻿'):
        text = text[1:]
    return text.replace('\r\n', '\n').replace('\r', '\n')


def markdown_lines(data: bytes):
    return normalize_markdown(data).split('\n')


# -- HTML ----------------------------------------------------------------------------------------------------------

# Attributes that carry document meaning (as opposed to presentation or editor scaffolding).
MEANINGFUL_ATTRS = {
    'a': ('href', 'title'),
    'img': ('src', 'alt', 'title'),
    'input': ('type', 'checked', 'disabled'),
    'ol': ('start',),
    'th': ('align',),
    'td': ('align',),
    'code': ('class',),            # language-xxx on code blocks
    'col': ('align',),
}
# Block/inline tags kept in the semantic tree. Everything else (span, div wrappers,
# figure chrome, editor tool nodes) is flattened to its text.
KEEP_TAGS = {
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'blockquote', 'pre', 'code', 'ul', 'ol', 'li',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'img', 'strong', 'em', 'del', 'mark',
    'sub', 'sup', 'hr', 'br', 'input', 'b', 'i', 's', 'kbd', 'figure', 'figcaption', 'summary',
    'details', 'dl', 'dt', 'dd',
}
VOID = {'img', 'hr', 'br', 'input', 'col'}
DROP_SUBTREE = {'style', 'script', 'head'}


class _Semantic(html.parser.HTMLParser):
    """Collect a normalized semantic tree: nodes are (tag, attrs, children) or text strings."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = ('#root', {}, [])
        self.stack = [self.root]
        self.dropping = 0

    def _attrs(self, tag, attrs):
        wanted = MEANINGFUL_ATTRS.get(tag, ())
        out = {}
        for key, value in attrs:
            if key in wanted:
                if tag == 'code' and key == 'class':
                    langs = [c for c in (value or '').split() if c.startswith('language-')]
                    if langs:
                        out['class'] = ' '.join(sorted(langs))
                else:
                    out[key] = value if value is not None else ''
        return out

    def handle_starttag(self, tag, attrs):
        if tag in DROP_SUBTREE:
            self.dropping += 1
            return
        if self.dropping:
            return
        if tag not in KEEP_TAGS:
            # Keep children, drop the wrapper: push a transparent marker.
            self.stack.append(('#transparent', {}, self.stack[-1][2]))
            return
        node = (tag, self._attrs(tag, attrs), [])
        self.stack[-1][2].append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if self.dropping or tag in DROP_SUBTREE:
            return
        if tag in KEEP_TAGS:
            self.stack[-1][2].append((tag, self._attrs(tag, attrs), []))

    def handle_endtag(self, tag):
        if tag in DROP_SUBTREE:
            self.dropping = max(0, self.dropping - 1)
            return
        if self.dropping:
            return
        # Pop to the matching open node (transparent wrappers included).
        for i in range(len(self.stack) - 1, 0, -1):
            node = self.stack[i]
            if node[0] == tag or (node[0] == '#transparent' and tag not in VOID and tag not in KEEP_TAGS):
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.dropping:
            return
        if data.strip() == '' and '\n' in data:
            text = ' '
        else:
            text = re.sub(r'\s+', ' ', data)
        if text:
            self.stack[-1][2].append(text)


def _render(node):
    tag, attrs, children = node
    parts = []
    text_run = []

    def flush():
        if text_run:
            joined = ''.join(text_run)
            joined = re.sub(r'\s+', ' ', joined).strip()
            if joined:
                parts.append(joined)
            text_run.clear()

    for child in children:
        if isinstance(child, str):
            text_run.append(child)
        else:
            flush()
            parts.append(_render(child))
    flush()
    if tag in ('#root', '#transparent'):
        return [p for p in parts if p != '']
    rendered = {'t': tag}
    if attrs:
        rendered['a'] = attrs
    body = [p for p in parts if p != '']
    if body:
        rendered['c'] = body
    return rendered


def html_body(data: bytes):
    """A normalized semantic tree of an exported HTML document's body content."""
    text = data.decode('utf-8', 'replace')
    parser = _Semantic()
    parser.feed(text)
    parser.close()
    rendered = _render(parser.root)
    return rendered if isinstance(rendered, list) else [rendered]


def html_text(data: bytes) -> str:
    """Flattened visible text of an exported HTML document (whitespace-normalized)."""
    text = data.decode('utf-8', 'replace')

    class _Text(html.parser.HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.drop = 0

        def handle_starttag(self, tag, attrs):
            if tag in DROP_SUBTREE:
                self.drop += 1

        def handle_endtag(self, tag):
            if tag in DROP_SUBTREE:
                self.drop = max(0, self.drop - 1)

        def handle_data(self, data):
            if not self.drop:
                self.parts.append(data)

    collector = _Text()
    collector.feed(text)
    collector.close()
    return re.sub(r'\s+', ' ', ' '.join(collector.parts)).strip()


# -- PDF -----------------------------------------------------------------------------------------------------------


def pdf_summary(data: bytes):
    """Page count, per-page size (points, rounded) and extractable text of a PDF."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        box = page.mediabox
        try:
            text = page.extract_text() or ''
        except Exception:
            text = ''
        pages.append({'width': round(float(box.width)), 'height': round(float(box.height)),
                      'text': re.sub(r'\s+', ' ', text).strip()})
    return {'pages': pages, 'count': len(pages)}


# -- images --------------------------------------------------------------------------------------------------------


def image_summary(data: bytes):
    from PIL import Image
    image = Image.open(io.BytesIO(data))
    image.load()
    fmt = image.format
    width, height = image.size
    small = image.convert('RGB').resize((8, 8))
    signature = list(small.getdata())
    return {'format': fmt, 'width': width, 'height': height, 'signature': [list(px) for px in signature]}
