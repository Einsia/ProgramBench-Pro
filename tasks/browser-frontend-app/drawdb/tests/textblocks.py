"""Read exported DBML, Mermaid and Markdown as keyed content, independent of presentation whitespace.

Quoted values remain lossless. DBML definitions contain lexical names, values and nested groups; setting groups
are maps (order-independent) while fields and index columns retain order. Mermaid entity definitions and edges
are separated. Markdown sections contain parsed headings, paragraphs, lists, table cells and fenced code.
"""
import html
import re


def lex(text):
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith('//', i):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end + 1
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            if end < 0:
                raise AssertionError('unterminated block comment')
            i = end + 2
        elif c in "'\"`":
            end, value = i + 1, []
            while end < len(text):
                if text.startswith(c * 2, end):
                    value.append(c)
                    end += 2
                elif text[end] == c:
                    break
                elif text[end] == '\\' and end + 1 < len(text):
                    value.append({'n': '\n', 't': '\t', 'r': '\r'}.get(text[end + 1], text[end + 1]))
                    end += 2
                else:
                    value.append(text[end])
                    end += 1
            if end == len(text):
                raise AssertionError('unterminated quoted text')
            out.append(('expression' if c == '`' else 'literal' if c == "'" else 'name', ''.join(value)))
            i = end + 1
        else:
            match = re.match(r'[\w$#-]+', text[i:], re.UNICODE)
            if match:
                out.append(('name', match[0]))
                i += len(match[0])
            else:
                out.append(('punct', c))
                i += 1
    return out


def nested(tokens):
    """Groups preserve semantic order; settings enclosed by [] are unordered key/value entries."""
    out, i = [], 0
    closes = {'(': ')', '[': ']', '{': '}'}
    while i < len(tokens):
        tok = tokens[i]
        if tok[0] == 'punct' and tok[1] in closes:
            opening, closing, depth, j = tok[1], closes[tok[1]], 1, i + 1
            while j < len(tokens) and depth:
                if tokens[j] == ('punct', opening):
                    depth += 1
                elif tokens[j] == ('punct', closing):
                    depth -= 1
                j += 1
            if depth:
                raise AssertionError('unclosed text-export group')
            values = nested(tokens[i + 1:j - 1])
            if opening == '[':
                entries, entry = [], []
                for value in values:
                    if value == ['punct', ',']:
                        entries.append(entry)
                        entry = []
                    else:
                        entry.append(value)
                if entry:
                    entries.append(entry)
                values = sorted(entries, key=repr)
            out.append([opening, values])
            i = j
        else:
            out.append(list(tok))
            i += 1
    return out


def dbml(text):
    tokens = lex(text)
    blocks, order, i = {}, [], 0
    while i < len(tokens):
        start, depth = i, 0
        # Public export definitions all use a top-level body, including named references.
        while i < len(tokens) and tokens[i] != ('punct', '{'):
            i += 1
        if i == len(tokens):
            raise AssertionError('DBML definition has no body')
        i += 1
        depth = 1
        while i < len(tokens) and depth:
            if tokens[i] == ('punct', '{'):
                depth += 1
            elif tokens[i] == ('punct', '}'):
                depth -= 1
            i += 1
        if depth:
            raise AssertionError('DBML definition has no closing brace')
        definition = tokens[start:i]
        kind = definition[0][1].lower()
        definition[0] = ('name', kind)
        name = definition[1][1] if len(definition) > 1 and definition[1][0] == 'name' else ''
        key, n = f'{kind}:{name}', 2
        while key in blocks:
            key = f'{kind}:{name}#{n}'
            n += 1
        blocks[key] = nested(definition)
        order.append(key)
    return {'order': order, 'blocks': blocks}


def mermaid(text):
    blocks, order, relations, body, name = {}, [], [], [], None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('%%'):
            continue
        if name is not None:
            if line == '}':
                blocks['entity:' + name] = nested(lex(' '.join(body)))
                order.append('entity:' + name)
                name, body = None, []
            else:
                body.append(line)
        elif line.endswith('{') and not re.search(r'--|\.\.', line):
            name = line[:-1].strip().strip('"')
        elif line == 'erDiagram':
            blocks['header'] = ['erDiagram']
            order.append('header')
        else:
            # Braces in an ER edge are cardinality symbols, not definition groups.
            relations.append([list(token) for token in lex(line)])
    if name is not None:
        raise AssertionError('unclosed Mermaid entity')
    blocks['relationships'] = sorted(relations, key=repr)
    return {'order': order, 'blocks': blocks}


def inline(text):
    # Emphasis and links affect rendering, not the documented schema values. Inline code remains verbatim.
    chunks = re.split(r'(`[^`]*`)', text.strip())
    result = []
    for chunk in chunks:
        if chunk.startswith('`') and chunk.endswith('`'):
            result.append(chunk[1:-1])
        else:
            chunk = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', chunk)
            chunk = re.sub(r'\*\*([^*]+)\*\*|__([^_]+)__', lambda m: m[1] or m[2], chunk)
            chunk = re.sub(r'<br\s*/?>', '\n', chunk, flags=re.I)
            result.append(' '.join(html.unescape(chunk).split()))
    return ''.join(result)


def table_cells(line):
    # Split unescaped pipes, including tables without outer pipes.
    cells = re.split(r'(?<!\\)\|', line.strip())
    if not cells[0].strip():
        cells.pop(0)
    if cells and not cells[-1].strip():
        cells.pop()
    return [inline(c.replace('\\|', '|')) for c in cells]


def markdown(text):
    blocks, order, stack, key, body = {}, [], [], 'section:', []
    fenced, code = None, []

    def close():
        name, n = key, 2
        while name in blocks:
            name = f'{key}#{n}'
            n += 1
        blocks[name] = list(body)
        order.append(name)

    for raw in text.splitlines():
        line = raw.strip()
        if fenced is not None:
            if line.startswith('```') or line.startswith('~~~'):
                body.append(['code', mermaid('\n'.join(code)) if fenced == 'mermaid' else '\n'.join(code)])
                fenced, code = None, []
            else:
                code.append(raw)
            continue
        fence = re.match(r'(?:```|~~~)(\w*)', line)
        if fence:
            fenced = fence[1]
            continue
        if not line:
            continue
        heading = re.match(r'(#{1,6})\s+(.*?)(?:\s+#+)?$', line)
        if heading:
            if body or key != 'section:':
                close()
            level, title = len(heading[1]), inline(heading[2])
            stack = [item for item in stack if item[0] < level] + [(level, title)]
            key, body = 'section:' + '/'.join(title for _, title in stack), [['heading', title]]
        elif '|' in line:
            cells = table_cells(line)
            if cells and all(re.fullmatch(r':?-{3,}:?', cell.replace(' ', '')) for cell in cells):
                continue
            body.append(['row', cells])
        elif re.match(r'[-*+]\s', line):
            body.append(['item', inline(line[2:])])
        else:
            value = inline(line)
            if body and body[-1][0] == 'paragraph':
                body[-1][1] += ' ' + value
            else:
                body.append(['paragraph', value])
    if fenced is not None:
        raise AssertionError('unclosed Markdown fence')
    close()
    return {'order': order, 'blocks': blocks}


READERS = {'dbml': dbml, 'mermaid': mermaid, 'markdown': markdown}


def read(kind, text):
    return READERS[kind](text)
