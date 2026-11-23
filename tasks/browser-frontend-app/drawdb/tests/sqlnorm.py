"""Structural comparison of SQL exports, with dialect-aware identifiers and lossless string literals.

Whitespace between tokens and optional identifier delimiters do not change a definition. String content is
preserved exactly, numeric literals use their decimal value, and column/constraint structure retains order
where SQL makes that order meaningful. This reads the export forms supported by the reference's six dialects.
"""
import re
from decimal import Decimal

WORD = re.compile(r'(?:[^\W\d]|[@#$])[\w@#$]*', re.UNICODE)
NUMBER = re.compile(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')
PUNCT2 = ('<>', '>=', '<=', '!=', '::', '||')
# Words that begin a column clause in a column definition.
CLAUSES = {'NOT', 'NULL', 'UNIQUE', 'PRIMARY', 'AUTO_INCREMENT', 'AUTOINCREMENT', 'IDENTITY', 'GENERATED', 'DEFAULT',
           'CHECK', 'COMMENT', 'UNSIGNED', 'ZEROFILL', 'ARRAY', 'COLLATE', 'CHARACTER', 'REFERENCES', 'CONSTRAINT'}
TABLE_CONSTRAINTS = {'PRIMARY', 'CONSTRAINT', 'FOREIGN', 'UNIQUE', 'CHECK', 'KEY', 'INDEX'}


class Token(tuple):
    """(kind, value): kind is word, ident, string, number, comment or punct."""

    def __new__(cls, pair, raw=None):
        result = super().__new__(cls, pair)
        result.raw = pair[1] if raw is None else raw
        return result

    @property
    def kind(self):
        return self[0]

    @property
    def value(self):
        return self[1]


def squeeze(value):
    return ' '.join(value.split())


KEYWORDS = set("""CREATE OR REPLACE ALTER UNIQUE MATERIALIZED TEMPORARY TEMP TABLE INDEX VIEW TYPE DOMAIN
IF NOT EXISTS FOREIGN KEY REFERENCES COMMENT ON COLUMN DATABASE SCHEMA IS EXEC EXECUTE ADD CONSTRAINT PRIMARY CHECK DEFAULT NULL
AUTO_INCREMENT AUTOINCREMENT IDENTITY GENERATED ALWAYS BY AS STORED VIRTUAL UNSIGNED ZEROFILL ARRAY COLLATE
CHARACTER SET SELECT FROM WHERE JOIN INNER LEFT RIGHT FULL OUTER CROSS AND OR IN LIKE BETWEEN TRUE FALSE
ASC DESC CASCADE RESTRICT NO ACTION DELETE UPDATE INHERITS WITH WITHOUT TIME ZONE USING N MAX MIN
CURRENT_TIMESTAMP CURRENT_DATE CURRENT_TIME NOW SYSDATE YEAR MONTH DAY SECOND TO INTERVAL
INT INTEGER TINYINT SMALLINT MEDIUMINT BIGINT INT2 INT4 INT8 SERIAL SMALLSERIAL BIGSERIAL SERIAL2 SERIAL4 SERIAL8
NUMERIC DECIMAL DEC NUMBER REAL FLOAT DOUBLE PRECISION BINARY_FLOAT BINARY_DOUBLE MONEY SMALLMONEY
BIT BOOLEAN BOOL CHAR CHARACTER NCHAR VARCHAR NVARCHAR VARCHAR2 NVARCHAR2 TEXT NTEXT TINYTEXT MEDIUMTEXT LONGTEXT
BYTEA BINARY VARBINARY BLOB TINYBLOB MEDIUMBLOB LONGBLOB CLOB NCLOB RAW LONG BFILE IMAGE
DATE TIME TIMESTAMP TIMESTAMPTZ DATETIME DATETIME2 DATETIMEOFFSET SMALLDATETIME YEAR JSON JSONB XML UUID
UNIQUEIDENTIFIER ENUM SET INET CIDR MACADDR MACADDR8 POINT LINE LSEG BOX PATH POLYGON CIRCLE GEOMETRY GEOGRAPHY
LINESTRING MULTIPOINT MULTILINESTRING MULTIPOLYGON GEOMETRYCOLLECTION TSVECTOR TSQUERY OID SQL_VARIANT HIERARCHYID
ROWVERSION VECTOR HALFVEC SPARSEVEC ROWNUM FETCH ONLY LIMIT OFFSET NULLS FIRST LAST END CASE WHEN THEN ELSE
""".split()) | CLAUSES | TABLE_CONSTRAINTS


def identifier(value, dialect, quoted=False):
    dialect = {'postgres': 'postgresql', 'oracle': 'oraclesql', 'mssql': 'transactsql'}.get(dialect, dialect)
    if dialect in ('sqlite', 'transactsql'):
        return value.casefold()
    if not quoted and dialect == 'postgresql':
        return value.lower()
    if not quoted and dialect == 'oraclesql':
        return value.upper()
    return value


def tokenize(text, dialect='mysql'):
    text = re.sub(r'(?im)^[ \t]*GO[ \t]*(?:--[^\n]*)?$', ';', text)
    tokens, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith('--', i) or text.startswith('/*', i):
            block = text.startswith('/*', i)
            j = text.find('*/' if block else '\n', i + 2)
            j = n if j < 0 else j
            tokens.append(Token(('comment', text[i + 2:j].strip())))
            i = j + (2 if block else 0)
        elif c in "'\"`[":
            closing = ']' if c == '[' else c
            if c == '[' and text.startswith('[]', i):
                tokens.append(Token(('punct', '[]')))
                i += 2
                continue
            j, out = i + 1, []
            while j < n:
                if text.startswith(closing * 2, j):
                    out.append(closing)
                    j += 2
                elif text[j] == closing:
                    break
                elif text[j] == '\\' and c == "'" and dialect in ('mysql', 'mariadb') and j + 1 < n:
                    escapes = {'n': '\n', 'r': '\r', 't': '\t', '0': '\0', 'b': '\b'}
                    out.append(escapes.get(text[j + 1], text[j + 1]))
                    j += 2
                else:
                    out.append(text[j])
                    j += 1
            if j == n:
                raise AssertionError('unterminated SQL quoted value')
            value = ''.join(out)
            tokens.append(Token(('string', value) if c == "'" else
                                ('ident', identifier(value, dialect, quoted=True))))
            i = j + 1
        elif NUMBER.match(text, i):
            m = NUMBER.match(text, i)
            value = Decimal(m.group(0))
            _, digits, exponent = value.as_tuple()
            digits = list(digits)
            while len(digits) > 1 and digits[-1] == 0:
                digits.pop()
                exponent += 1
            number = ''.join(map(str, digits)) + (f'E{exponent}' if exponent else '') if value else '0'
            tokens.append(Token(('number', number)))
            i = m.end()
        elif WORD.match(text, i):
            m = WORD.match(text, i)
            raw = m.group(0)
            upper = raw.upper()
            # MSSQL named procedure arguments and built-in grammar/type words are case-insensitive.
            kind = 'word' if upper in KEYWORDS or raw.startswith('@') else 'ident'
            tokens.append(Token((kind, upper if kind == 'word' else identifier(raw, dialect)), raw))
            i = m.end()
        else:
            two = text[i:i + 2]
            tokens.append(Token(('punct', two if two in PUNCT2 else c)))
            i += 2 if two in PUNCT2 else 1
    return identifier_positions(tokens, dialect)


def identifier_positions(tokens, dialect):
    """Resolve names in declaration/reference positions, including names that also spell type words."""
    def mark(i):
        if i < len(tokens) and tokens[i].kind == 'word':
            tokens[i] = Token(('ident', identifier(tokens[i].raw, dialect)), tokens[i].raw)

    def name(i):
        mark(i)
        while i + 2 < len(tokens) and tokens[i + 1] == ('punct', '.'):
            i += 2
            mark(i)
        return i + 1

    def first_in_list(i):
        if i >= len(tokens) or tokens[i] != ('punct', '('):
            return
        end, depth, first = group(tokens, i), 0, True
        for k in range(i + 1, end - 1):
            if first and depth == 0 and tokens[k].kind != 'comment':
                mark(k)
                first = False
            if tokens[k] == ('punct', '('):
                depth += 1
            elif tokens[k] == ('punct', ')'):
                depth -= 1
            elif tokens[k] == ('punct', ',') and depth == 0:
                first = True

    # A table body differs from a list of referenced names: its column types and constraints are grammar.
    for i in range(len(tokens)):
        if tokens[i] == ('word', 'CREATE'):
            k = i + 1
            while k < len(tokens) and tokens[k].value in ('OR', 'REPLACE', 'ALTER', 'UNIQUE', 'MATERIALIZED', 'TEMP', 'TEMPORARY'):
                k += 1
            if k == len(tokens):
                continue
            what = tokens[k].value
            k += 1
            while k < len(tokens) and tokens[k].value in ('IF', 'NOT', 'EXISTS'):
                k += 1
            end_name = name(k)
            if what == 'TABLE' and end_name < len(tokens) and tokens[end_name] == ('punct', '('):
                end, depth, first = group(tokens, end_name), 0, True
                for j in range(end_name + 1, end - 1):
                    tok = tokens[j]
                    if first and depth == 0 and tok.kind != 'comment':
                        if not (tok.kind == 'word' and tok.value in TABLE_CONSTRAINTS):
                            mark(j)
                        first = False
                    if tok == ('punct', '('):
                        depth += 1
                    elif tok == ('punct', ')'):
                        depth -= 1
                    elif tok == ('punct', ',') and depth == 0:
                        first = True
        elif tokens[i] == ('word', 'ALTER') and i + 1 < len(tokens) and tokens[i + 1] == ('word', 'TABLE'):
            name(i + 2)
        elif tokens[i] == ('word', 'COMMENT') and i + 3 < len(tokens) and tokens[i + 1] == ('word', 'ON'):
            name(i + (4 if tokens[i + 2] == ('word', 'MATERIALIZED') else 3))
        elif tokens[i] == ('word', 'REFERENCES'):
            first_in_list(name(i + 1))
        elif tokens[i] == ('word', 'CONSTRAINT'):
            name(i + 1)
        elif tokens[i] == ('word', 'KEY') or tokens[i] == ('word', 'UNIQUE'):
            first_in_list(i + 1)
        elif tokens[i] == ('word', 'ON'):
            # CREATE INDEX ... ON table(columns); COMMENT ON <kind> is handled by key().
            if i + 1 < len(tokens) and tokens[i + 1].kind == 'ident':
                first_in_list(name(i + 1))
        if tokens[i] == ('punct', '.'):
            if i:
                mark(i - 1)
            mark(i + 1)
    return tokens


def split(tokens):
    statements, current = [], []
    for tok in tokens:
        if tok == ('punct', ';'):
            if [t for t in current if t.kind != 'comment']:
                statements.append(current)
                current = []
            continue
        current.append(tok)
    if [t for t in current if t.kind != 'comment']:
        statements.append(current)
    elif current and statements:
        statements[-1].extend(current)
    return statements


def name_of(tok):
    return tok.value if tok.kind in ('ident', 'word', 'string') else str(tok.value)


def words(tokens):
    return [t.value if t.kind == 'word' else None for t in tokens]


def group(tokens, start):
    """End index (exclusive) of the parenthesised group that starts at tokens[start] == '('."""
    depth = 0
    for i in range(start, len(tokens)):
        if tokens[i] == ('punct', '('):
            depth += 1
        elif tokens[i] == ('punct', ')'):
            depth -= 1
            if depth == 0:
                return i + 1
    return len(tokens)


def names_in(tokens, start):
    """Identifiers of a parenthesised list at tokens[start] and the index after it."""
    end = group(tokens, start)
    return [name_of(t) for t in tokens[start + 1:end - 1] if t.kind in ('ident', 'word')], end


def key(statement):
    body = [t for t in statement if t.kind != 'comment']
    w = words(body)
    if not body:
        return 'empty'
    if w[0] == 'CREATE':
        i = 1
        while i < len(w) and w[i] in ('OR', 'REPLACE', 'ALTER', 'UNIQUE', 'MATERIALIZED', 'TEMPORARY', 'TEMP'):
            i += 1
        what = w[i] if i < len(w) else None
        i += 1
        while i < len(w) and w[i] in ('IF', 'NOT', 'EXISTS'):
            i += 1
        name = name_of(body[i]) if i < len(body) else ''
        if what == 'TABLE':
            return 'table:' + name
        if what == 'INDEX':
            return 'index:' + name
        if what == 'VIEW':
            return 'view:' + name
        if what == 'TYPE':
            return ('enum:' if 'ENUM' in w[i:i + 4] else 'type:') + name
        return 'create:' + str(what) + ':' + name
    if w[0] == 'ALTER' and len(w) > 2 and w[1] == 'TABLE':
        table = name_of(body[2])
        if 'FOREIGN' in w:
            f = w.index('FOREIGN')
            start = f + 2
            cols, after = names_in(body, start) if start < len(body) and body[start] == ('punct', '(') else ([], start)
            if 'REFERENCES' in w[after:]:
                r = after + w[after:].index('REFERENCES')
                ref = name_of(body[r + 1])
                refcols, _ = names_in(body, r + 2) if r + 2 < len(body) and body[r + 2] == ('punct', '(') else ([], 0)
                return f'fk:{table}({",".join(cols)})->{ref}({",".join(refcols)})'
        return 'alter:' + table
    if w[0] == 'COMMENT' and len(w) > 2 and w[1] == 'ON':
        target = w[2] if w[2] != 'MATERIALIZED' else 'VIEW'
        j = 3 if w[2] != 'MATERIALIZED' else 4
        path = []
        while j < len(body) and body[j].kind in ('ident', 'word') and w[j] != 'IS':
            path.append(name_of(body[j]))
            j += 1
            if j < len(body) and body[j] == ('punct', '.'):
                j += 1
        return f'comment:{target.lower()}:' + '.'.join(path)
    if w[0] in ('EXEC', 'EXECUTE'):
        level1 = level2 = None
        for i, tok in enumerate(body):
            if tok.kind == 'word' and tok.value in ('@LEVEL1NAME', '@LEVEL2NAME'):
                value = next((b for b in body[i + 1:i + 4] if b.kind == 'string'), None)
                if value is not None:
                    if tok.value == '@LEVEL1NAME':
                        level1 = value.value
                    else:
                        level2 = value.value
        return 'description:' + str(level1) + ('.' + level2 if level2 else '')
    return 'other:' + ' '.join(str(x) for x in w[:3])


def show(tokens):
    """A compact text form of tokens, for observations."""
    out = []
    for t in tokens:
        if t.kind == 'string':
            out.append("'" + t.value.replace("'", "''") + "'")
        elif t.kind == 'ident':
            out.append('<' + t.value + '>')
        elif t.kind == 'comment':
            out.append('/*' + t.value + '*/')
        else:
            out.append(t.value)
    return ' '.join(out)


def clauses(tokens):
    """Column clauses of a column definition after its type, as a sorted list of texts."""
    out, i, n = [], 0, len(tokens)
    while i < n:
        t = tokens[i]
        w = t.value if t.kind == 'word' else None
        j = i + 1
        if w == 'NOT':
            j = i + 2
        elif w == 'PRIMARY':
            j = i + 2
        elif w == 'GENERATED':
            while j < n and not (tokens[j].kind == 'word' and tokens[j].value == 'IDENTITY'):
                j += 1
            j += 1
        elif w in ('DEFAULT', 'COMMENT', 'COLLATE'):
            if j < n and tokens[j] == ('punct', '('):
                j = group(tokens, j)
            else:
                if j < n and tokens[j] in (('punct', '-'), ('punct', '+')):
                    j += 1
                j += 1
                if j < n and tokens[j] == ('punct', '('):
                    j = group(tokens, j)
                while j + 1 < n and tokens[j] == ('punct', '::'):
                    j += 2
        elif w == 'CHARACTER':
            j = i + 3
        elif w == 'CHECK':
            if j < n and tokens[j] == ('punct', '('):
                j = group(tokens, j)
        elif w in ('REFERENCES', 'CONSTRAINT'):
            while j < n and not (tokens[j].kind == 'word' and tokens[j].value in CLAUSES - {'NULL'}
                                 and tokens[j].value not in ('NOT',)):
                if tokens[j] == ('punct', '('):
                    j = group(tokens, j)
                else:
                    j += 1
        else:
            while j < n and not (tokens[j].kind == 'word' and tokens[j].value in CLAUSES):
                if tokens[j] == ('punct', '('):
                    j = group(tokens, j)
                else:
                    j += 1
        out.append(show(tokens[i:j]))
        i = j
    return sorted(out)


def column(tokens):
    comments = [t.value for t in tokens if t.kind == 'comment']
    body = [t for t in tokens if t.kind != 'comment']
    if not body:
        return {'comments': comments}
    name = name_of(body[0])
    i = 1
    while i < len(body) and not (body[i].kind == 'word' and body[i].value in CLAUSES):
        i = group(body, i) if body[i] == ('punct', '(') else i + 1
    return {'name': name, 'type': show(body[1:i]), 'clauses': clauses(body[i:]), 'comments': comments}


def elements(tokens):
    """The comma-separated elements of a parenthesised definition list (without the parentheses)."""
    out, current, depth = [], [], 0
    for t in tokens:
        if t == ('punct', '('):
            depth += 1
        elif t == ('punct', ')'):
            depth -= 1
        if t == ('punct', ',') and depth == 0:
            out.append(current)
            current = []
        else:
            current.append(t)
    if current:
        out.append(current)
    return out


def table(statement):
    lead = []
    i = 0
    while i < len(statement) and statement[i].kind == 'comment':
        lead.append(statement[i].value)
        i += 1
    rest = statement[i:]
    open_at = next((k for k, t in enumerate(rest) if t == ('punct', '(')), None)
    if open_at is None:
        return {'head': show(rest)}
    end = group(rest, open_at)
    columns, constraints = [], []
    for element in elements(rest[open_at + 1:end - 1]):
        body = [t for t in element if t.kind != 'comment']
        if body and body[0].kind == 'word' and body[0].value in TABLE_CONSTRAINTS:
            constraints.append(show(element))
        else:
            columns.append(column(element))
    return {'comments': lead, 'head': show(rest[:open_at]), 'columns': columns, 'constraints': sorted(constraints),
            'tail': show(rest[end:])}


def statements(text, dialect="mysql"):
    """[(key, statement tokens)] in script order."""
    return [(key(s).casefold(), s) for s in split(tokenize(text, dialect))]


def canonical(statement):
    k = key(statement).casefold()
    if k.startswith('table:'):
        return {'key': k, **table(statement)}
    return {'key': k, 'tokens': show(statement)}


def read(text, dialect="mysql"):
    """{'order': [keys], 'statements': {key: canonical form}} (later duplicates get #2, #3 ... suffixes)."""
    order, found = [], {}
    for k, s in statements(text, dialect):
        name = k
        n = 2
        while name in found:
            name = f'{k}#{n}'
            n += 1
        order.append(name)
        found[name] = canonical(s)
    return {'order': order, 'statements': found}
