'''Expression guard for VisiData, applied in-process by launch.py.

Stock VisiData evaluates typed expressions with eval in its whole namespace: hundreds of modules, interpreter
internals and, through the row context, every attribute of the sheet and of vd. This module replaces every such
path without touching VisiData's files. An expression is parsed to a syntax tree and only a fixed set of node
kinds is accepted. Attribute names must come from an allow-list of value methods and fields, names and attributes
that begin with an underscore are refused, and stores and deletes are refused. Evaluation runs with empty builtins
in a small namespace plus a context that resolves only the sheet's column names. A code object is evaluated only
if this module compiled it. Format-string fields may not walk private attributes either.
'''
import ast
import builtins
import itertools
import json
import math
import random
import string
import sys
import threading
import types
import weakref

REFUSAL = 'This action is disabled in this environment.'
MAX_SOURCE = 4096
MAX_EXPONENT = 1000
DENIED_ATTRIBUTES = frozenset('''format format_map vformat mro gi_frame gi_code gi_yieldfrom cr_frame cr_code
    cr_await ag_frame ag_code ag_await f_back f_builtins f_code f_globals f_locals f_trace tb_frame tb_next
    func_globals func_code'''.split())
# Attribute names usable on values (str, bytes, list, dict, set, numbers, dates); namespace members are added by
# install(). Anything else, including every attribute of sheets, columns and vd, is refused.
BASE_ATTRIBUTES = frozenset('''capitalize casefold center count encode endswith expandtabs find index isalnum
    isalpha isascii isdecimal isdigit isidentifier islower isnumeric isprintable isspace istitle isupper join
    ljust lower lstrip maketrans partition removeprefix removesuffix replace rfind rindex rjust rpartition rsplit
    rstrip split splitlines startswith strip swapcase title translate upper zfill decode hex fromhex append clear
    copy extend insert pop remove reverse sort get items keys setdefault update values popitem fromkeys add
    difference discard intersection isdisjoint issubset issuperset symmetric_difference union conjugate
    bit_length bit_count is_integer as_integer_ratio real imag numerator denominator year month day hour minute
    second microsecond tzinfo fold date time timetuple isoformat strftime weekday isoweekday isocalendar
    astimezone timestamp total_seconds days seconds toordinal now today utcnow fromtimestamp fromisoformat
    fromordinal combine strptime utcoffset tzname min max resolution name'''.split())
ATTRIBUTES = set(BASE_ATTRIBUTES)
ALLOWED = (ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.IfExp, ast.Compare, ast.Call, ast.keyword,
           ast.Constant, ast.Name, ast.Attribute, ast.Subscript, ast.Slice, ast.Starred, ast.Tuple, ast.List,
           ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
           ast.Lambda, ast.arguments, ast.arg, ast.JoinedStr, ast.FormattedValue, ast.Load, ast.Store,
           ast.boolop, ast.operator, ast.unaryop, ast.cmpop)
SAFE_BUILTINS = '''abs all any ascii bin bool bytes chr complex dict divmod enumerate filter float format
    frozenset hex int isinstance len list map max min oct ord range repr reversed round set sorted str sum
    tuple zip'''.split()
VISIDATA_NAMES = '''date datedelta datetime days hours minutes seconds weeks months years vlen floatsi
    floatlocale currency USD filesize'''.split()
RANDOM_NAMES = 'randrange randint choice choices sample uniform gauss lognormvariate'.split()
STRING_NAMES = '''ascii_letters ascii_lowercase ascii_uppercase digits hexdigits punctuation printable
    whitespace'''.split()

STATE = types.SimpleNamespace(visidata=None, vd=None)
TRUSTED = weakref.WeakSet()
IMPORT_ALLOWED = frozenset(('time', '_strptime'))


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    '''datetime strftime and strptime import time and _strptime lazily through the __import__ found in the builtins
    of the calling frame. Only these two loaded modules can be named; expression text cannot reach this function
    because names that begin with an underscore are refused.'''
    if level != 0 or name not in IMPORT_ALLOWED or name not in sys.modules:
        raise ImportError('import is not available in expressions')
    return sys.modules[name]


SAFE_GLOBALS = {'__builtins__': {'__import__': safe_import}}
LOCAL = threading.local()


def refuse():
    STATE.vd.fail(REFUSAL)


def row_attribute(node):
    return isinstance(node.value, ast.Name) and node.value.id == 'row'


def small_constant(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool) and abs(node.value) <= MAX_EXPONENT)


def validate(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED):
            refuse()
        if isinstance(node, (ast.Attribute, ast.Subscript)) and not isinstance(node.ctx, ast.Load):
            refuse()
        if isinstance(node, ast.Attribute):
            if node.attr.startswith('_') or node.attr in DENIED_ATTRIBUTES:
                refuse()
            if node.attr not in ATTRIBUTES and not row_attribute(node):
                refuse()
        elif isinstance(node, ast.Name):
            if node.id.startswith('_'):
                refuse()
        elif isinstance(node, ast.arg):
            if node.arg.startswith('_'):
                refuse()
        elif isinstance(node, ast.keyword):
            if node.arg is not None and node.arg.startswith('_'):
                refuse()
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            nested = isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Pow)
            if nested or not small_constant(node.right):
                refuse()


def source_text(source):
    if not isinstance(source, str) or len(source) > MAX_SOURCE:
        refuse()
    return source.lstrip(' ' + chr(9))


def guarded_compile(source, filename='<expr>', mode='eval', *args, **kwargs):
    if mode != 'eval':
        refuse()
    text = source_text(source)
    try:
        tree = ast.parse(text, '<expr>', 'eval')
    except SyntaxError:
        raise
    except Exception:
        refuse()
    validate(tree)
    code = builtins.compile(tree, '<expr>', 'eval')
    TRUSTED.add(code)
    return code


def run(code, context):
    if code not in TRUSTED:
        refuse()
    return builtins.eval(code, SAFE_GLOBALS, context)


def guarded_eval(source, globals=None, locals=None):
    code = source if isinstance(source, types.CodeType) else guarded_compile(source)
    return run(code, {})


# -- contexts: only column names, row, col and curcol are resolvable ----------------------------------------------
class SafeColumn:
    __slots__ = ('name',)

    def __init__(self, column):
        self.name = getattr(column, 'name', '')


class SafeSheet:
    __slots__ = ('name',)

    def __init__(self, sheet):
        self.name = getattr(sheet, 'name', '')


def find_column(sheet, current, name):
    names = getattr(sheet, 'availColnames', None)
    if not isinstance(name, str) or not names or name not in names:
        return None
    index = names.index(name)
    columns = sheet.availCols
    column = columns[index]
    if column is current:
        rest = names[index + 1:]
        if name not in rest:
            return None
        column = columns[index + 1 + rest.index(name)]
    return column


def column_value(column, row):
    active = LOCAL.__dict__.setdefault('active', set())
    key = (id(column), id(row))
    if key in active:
        raise STATE.visidata.RecursiveExprException()
    active.add(key)
    try:
        return column.getTypedValue(row)
    finally:
        active.discard(key)


class SafeRow:
    __slots__ = ('_sheet', '_row', '_col')

    def __init__(self, sheet, row, col):
        self._sheet, self._row, self._col = sheet, row, col

    def __getitem__(self, name):
        column = find_column(self._sheet, self._col, name)
        if column is None:
            raise KeyError(name)
        return column_value(column, self._row)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        column = find_column(self._sheet, self._col, name)
        if column is None:
            raise AttributeError(name)
        return column_value(column, self._row)


class Context:
    def __init__(self, sheet, row=None, col=None, curcol=None):
        self.sheet, self.row, self.col, self.curcol = sheet, row, col, curcol

    def __getitem__(self, name):
        if self.row is not None:
            column = find_column(self.sheet, self.col, name)
            if column is not None:
                return column_value(column, self.row)
            if name == 'row':
                return SafeRow(self.sheet, self.row, self.col)
        if name == 'col' and self.col is not None:
            return SafeColumn(self.col)
        if name == 'curcol' and self.curcol is not None:
            return SafeColumn(self.curcol)
        raise KeyError(name)


class ColorContext:
    def __init__(self, sheet, col, row, value):
        self.sheet, self.col, self.row, self.value = sheet, col, row, value

    def __getitem__(self, name):
        if name in ('v', 'value'):
            return self.value
        if name in ('r', 'row') and self.row is not None:
            return SafeRow(self.sheet, self.row, self.col)
        if name in ('c', 'col') and self.col is not None:
            return SafeColumn(self.col)
        if name in ('s', 'sheet'):
            return SafeSheet(self.sheet)
        if self.row is not None:
            column = find_column(self.sheet, None, name)
            if column is not None:
                return column_value(column, self.row)
        raise KeyError(name)


def evalExpr(sheet, expr, row=None, col=None, **kwargs):
    code = expr if isinstance(expr, types.CodeType) else guarded_compile(expr)
    return run(code, Context(sheet, row, col, kwargs.get('curcol')))


def make_color_func(expr):
    code = guarded_compile(expr)

    def func(s, c, r, v):
        typed = v.typedval if hasattr(v, 'typedval') else v
        try:
            return run(code, ColorContext(s, c, r, typed))
        except Exception as exc:
            STATE.vd.debug('condfmt %s: %s: %s' % (expr, type(exc).__name__, exc))
            return False
    return func


def build_namespace(visidata):
    names = {name: getattr(builtins, name) for name in SAFE_BUILTINS}
    maths = {name: getattr(math, name) for name in dir(math) if not name.startswith('_')}
    randoms = {name: getattr(random, name) for name in RANDOM_NAMES}
    strings = {name: getattr(string, name) for name in STRING_NAMES}
    tools = {name: getattr(itertools, name) for name in dir(itertools) if not name.startswith('_')}
    for group in (maths, randoms, strings):
        names.update(group)
    for name in VISIDATA_NAMES:
        if hasattr(visidata, name):
            names[name] = getattr(visidata, name)
    names.update(math=types.SimpleNamespace(**maths), random=types.SimpleNamespace(**randoms),
                 string=types.SimpleNamespace(**strings), itertools=types.SimpleNamespace(**tools),
                 json=types.SimpleNamespace(loads=json.loads, dumps=json.dumps))
    for group in (maths, randoms, strings, tools):
        ATTRIBUTES.update(group)
    ATTRIBUTES.update(('loads', 'dumps'))
    return names


def install(visidata):
    STATE.visidata = visidata
    STATE.vd = visidata.vd
    SAFE_GLOBALS.update(build_namespace(visidata))
    visidata.eval = guarded_eval
    pending, seen = [visidata.BaseSheet], set()
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        if 'evalExpr' in cls.__dict__:
            cls.evalExpr = evalExpr
        pending.extend(cls.__subclasses__())
    sys.modules['visidata.expr'].compile = guarded_compile
    sys.modules['visidata.features.condfmt']._make_color_func = make_color_func
    formatter = visidata.MissingAttrFormatter
    inherited = formatter.get_field

    def get_field(self, field_name, args, kwargs):
        parts = field_name.replace('[', '.').replace(']', '.').split('.')
        if any(part.startswith('_') or part in DENIED_ATTRIBUTES for part in parts):
            return '', field_name
        return inherited(self, field_name, args, kwargs)
    formatter.get_field = get_field
