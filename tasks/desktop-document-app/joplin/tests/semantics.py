"""Compare generated document structure, without prescribing Markdown spelling."""
import re
import posixpath
from urllib.parse import urlsplit,urlunsplit


def markdown_structure(source):
    from markdown_it import MarkdownIt
    from bs4 import BeautifulSoup, NavigableString
    html = MarkdownIt('commonmark', {'html': True}).enable(['table', 'strikethrough']).render(source)
    soup = BeautifulSoup(html, 'html.parser')
    blocks = {'p', 'div', 'blockquote', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'td', 'th',
              'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'hr', 'dl', 'dt', 'dd'}

    def tree(node, literal=False):
        if isinstance(node, NavigableString):
            text = str(node) if literal else re.sub(r'\s+', ' ', str(node))
            if not literal and not text.strip():
                return ' ' if node.previous_sibling and node.next_sibling and \
                    getattr(node.previous_sibling, 'name', None) not in blocks and \
                    getattr(node.next_sibling, 'name', None) not in blocks else None
            return text
        name = {'b': 'strong', 'i': 'em', 's': 'del', 'strike': 'del'}.get(node.name, node.name)
        attributes = {}
        for key in ('href', 'src', 'alt', 'title', 'start', 'colspan', 'rowspan'):
            if key in node.attrs:
                attributes[key] = node.attrs[key]
                if key in ('href','src'):
                    url=urlsplit(attributes[key])
                    if url.scheme in ('http','https') and any(x in ('.','..') for x in url.path.split('/')):
                        path=posixpath.normpath(url.path)
                        if url.path.endswith('/') and not path.endswith('/'):path+='/'
                        attributes[key]=urlunsplit((url.scheme,url.netloc,path,url.query,url.fragment))
        if name == 'code':
            language = [x for x in node.get('class', []) if x.startswith('language-')]
            if language:
                attributes['language'] = language
        alignment = node.get('align')
        if not alignment:
            match = re.search(r'text-align\s*:\s*(left|center|right)', node.get('style', ''))
            if match:
                alignment = match[1]
        if alignment:
            attributes['align'] = alignment
        children = [value for child in node.children
                    if (value := tree(child, literal or name in ('pre', 'code'))) is not None]
        if name in ('strong','em','del'):
            marks={name}
            if len(children)==1 and isinstance(children[0],list) and children[0][0]=='format':
                marks.update(children[0][1]['marks']);children=children[0][2]
            return ['format',{'marks':sorted(marks)},children]
        return [name, attributes, children]

    return [value for child in soup.children if (value := tree(child)) is not None]
