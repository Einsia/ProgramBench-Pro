"""Building blocks of the episode specifications: goals, acceptance conditions, program points and setup."""
import re

from evaluation.contract import files_path
LEDGER = 'ledger.mmb'

HINTS = ('The window is drawn by a desktop toolkit: dialogs and menus appear in the accessibility snapshot, while the navigator tree on '
         'the left, the toolbar, the transaction lists and the dashboard and report pages may be visible only in the screenshot; read them '
         'there and click them by screen position. A navigator section opens with the small triangle at its left end or by double click; '
         'the row itself opens its view. Fields with a suggestion list (account, payee, category) show the list over the field below; press '
         'Tab once to close the list before clicking elsewhere. Dates are typed in the form the date field shows (MM/DD/YYYY). A dialog takes '
         'its values when it is confirmed. When a goal names an output file, enter exactly that full path as the file name. The database is '
         'saved automatically, so judge the visible result as a user would at a glance; do not reopen files or undo '
         'actions to compare (the state at the start of each goal is kept as evidence for the judgement).')


def inbox(key):
    """The runtime's inbox of one episode (its exchange folders sit beside the product's instance directory)."""
    return files_path('inbox', instance=False)


def outbox(key):
    return files_path('outbox', instance=False)


def slug(value):
    text = re.sub(r'[^A-Za-z0-9]+', '-', str(value)).strip('-').lower()
    return text[:32] or 'x'


def _label(match):
    return '-'.join(slug(value) for value in (match or {}).values()) or 'all'


TABLE_TITLES = {'account': 'Account', 'payee': 'Payee', 'category': 'Category', 'tag': 'Tag', 'currency': 'Currency', 'trx': 'Transaction',
                'sched': 'Scheduled transaction', 'budget': 'Budget entry', 'budget_year': 'Budget', 'asset': 'Asset', 'stock': 'Stock',
                'stock_history': 'Stock price', 'currency_history': 'Currency rate', 'field': 'Custom field', 'attachment': 'Attachment'}


def row(table, match, file=None, area=None, **fields):
    """One program point per field of the one row a match selects; the value given is the expected value at record."""
    result = []
    for field, value in fields.items():
        check = {'kind': 'row', 'table': table, 'match': dict(match), 'field': field, 'expect': value,
                 'slug': f'{table}-{_label(match)}-{field}',
                 'description': f'{TABLE_TITLES.get(table, table)} {_describe(match)}: the {field} is saved as {_value(value)}.'}
        result.append(_located(check, file, area))
    return result


def _describe(match):
    return ', '.join(f'{key} {value!r}' for key, value in (match or {}).items())


def _value(value):
    text = repr(value)
    return text if len(text) < 80 else text[:77] + '...'


def _located(check, file, area):
    if file:
        check['file'] = file
    if area:
        check['area'] = area
    return check


def count(table, match, value, slug_text=None, file=None, area=None):
    return [_located({'kind': 'count', 'table': table, 'match': dict(match), 'expect': value,
                      'slug': slug_text or f'{table}-{_label(match)}-count',
                      'description': f'{TABLE_TITLES.get(table, table)} rows matching {_describe(match) or "anything"}: {value}.'}, file, area)]


def names(table, field, match=None, expect=None, slug_text=None, file=None, area=None):
    check = {'kind': 'names', 'table': table, 'field': field, 'match': dict(match or {}), 'slug': slug_text or f'{table}-{field}-list',
             'description': f'The {field} values of the {TABLE_TITLES.get(table, table)} rows {_describe(match) or ""}.', 'nonempty': True}
    if expect is not None:
        check['expect'] = expect
    return [_located(check, file, area)]


def rows(table, fields, match=None, sort=None, slug_text=None, file=None, area=None, expect=None):
    check = {'kind': 'rows', 'table': table, 'fields': list(fields), 'match': dict(match or {}), 'slug': slug_text or f'{table}-{_label(match)}-rows',
             'description': f'The {TABLE_TITLES.get(table, table)} rows {_describe(match)}: {", ".join(fields)}.', 'nonempty': True}
    if sort:
        check['sort'] = list(sort)
    if expect is not None:
        check['expect'] = expect
    return [_located(check, file, area)]


def info(name, value=None, file=None, area=None):
    check = {'kind': 'info', 'name': name, 'slug': f'setting-{slug(name)}', 'description': f'The database setting {name} is saved as expected.'}
    if value is not None:
        check['expect'] = value
    return [_located(check, file, area)]


def document(area, file, form, slug_text, description, expect=None, **options):
    check = {'kind': 'document', 'area': area, 'file': file, 'form': form, 'slug': slug_text, 'description': description, 'nonempty': True, **options}
    if expect is not None:
        check['expect'] = expect
    return [check]


def files(area, pattern, expect, slug_text, description):
    return [{'kind': 'files', 'area': area, 'pattern': pattern, 'expect': expect, 'slug': slug_text, 'description': description}]


def step(key, goal, acceptance, recipe, points=(), *, depends=(), lifecycle=None, modal_end=False, requires=None):
    """One checkpoint. requires binds a frontend assertion (suffix such as 'visible') to companion points of this
    checkpoint (their slugs) or of the same episode ('checkpoint/slug')."""
    flat = [check for item in points for check in (item if isinstance(item, list) else [item])]
    checkpoint = {'id': key, 'goal': goal, 'acceptance': [acceptance] if isinstance(acceptance, str) else list(acceptance),
                  'recipe': list(recipe), 'checks': flat, 'depends_on': list(depends)}
    if lifecycle:
        checkpoint['lifecycle'] = lifecycle
    if modal_end:
        checkpoint['modal_end'] = True
    if requires:
        checkpoint['requires'] = {suffix: list(items) for suffix, items in requires.items()}
    return checkpoint


def budget_for(n, *, scale=1.0):
    return {'calls': int(min(200, 55 + 30 * n) * scale), 'seconds': int(min(2400, 540 + 240 * n) * scale),
            'tokens': int(min(2_000_000, 500_000 + 300_000 * n) * scale)}


def episode(key, feature, steps, *, ledger='std', files_in=(), files_out=(), session=None, setup=(), notes='', navigator=None, children=None,
             opened=True, budget=None):
    """A GUI episode: the ledger and the input documents are uploaded before the first goal and the ledger is open."""
    uploads = ([f'{ledger}/{LEDGER}'] if ledger else []) + list(files_in)
    items = []
    if uploads:
        item = {'id': 'documents', 'op': 'documents', 'files': uploads}
        if ledger and opened:
            item['open'] = LEDGER
        items.append(item)
    items += list(setup)
    for checkpoint in steps:
        checkpoint['depends_on'] = ['setup:' + item['id'] for item in items] + list(checkpoint['depends_on'])
        checkpoint['assertions'] = []
        for index, text in enumerate(checkpoint['acceptance']):
            suffix = 'visible' if len(checkpoint['acceptance']) == 1 else f'visible-{index + 1}'
            checkpoint['assertions'].append({'id': f'{key}/{checkpoint["id"]}/{suffix}', 'channel': 'frontend', 'method': 'agent', 'requirement': text})
        used = {}
        for check in checkpoint['checks']:
            name = check.pop('slug')
            used[name] = used.get(name, 0) + 1
            suffix = name if used[name] == 1 else f'{name}-{used[name]}'
            checkpoint['assertions'].append({'id': f'{key}/{checkpoint["id"]}/{suffix}', 'channel': 'backend', 'method': 'program',
                                             'requirement': check['description'], 'check': check})
    ids = {a['id'] for checkpoint in steps for a in checkpoint['assertions']}
    for checkpoint in steps:
        for suffix, points in checkpoint.pop('requires', {}).items():
            point = next(a for a in checkpoint['assertions'] if a['id'] == f'{key}/{checkpoint["id"]}/{suffix}')
            point['requires'] = [f'{key}/{checkpoint["id"]}/{p}' if '/' not in p else f'{key}/{p}' for p in points]
            assert all(r in ids for r in point['requires']), point['requires']
    documents = {name.rpartition('/')[2]: {'path': f'{inbox(key)}/{name.rpartition("/")[2]}'} for name in files_in}
    if session is None:
        start = f'The application has just started and shows the database {inbox(key)}/{LEDGER}.' if ledger and opened else \
            'The application has just started without an open database, in a fresh data directory.'
        session = start + ' Work on the goals in order. ' + HINTS
    value = {'id': key, 'feature': feature, 'execution': 'gui',
             'initial_state': 'Fresh application process with an empty DATA_DIR and a private desktop session; the listed documents are in the '
                              'inbox before the first goal.' + (' ' + notes if notes else ''),
             'setup': items,
             'inputs': {'input_folder': inbox(key), 'output_folder': outbox(key), 'documents': documents},
             'session': session,
             'allowed_equivalents': ['Menus, toolbar buttons, context menus, keyboard shortcuts, navigator rows and links that reach the same product '
                                     'command are equivalent.',
                                     'Typing a full path into a file dialog is equivalent to browsing to it.'],
             'forbidden_bypasses': ['Do not use terminals, other applications, private files or hidden state.',
                                    'Do not recreate a missing product command by other means.'],
             'budget': budget or budget_for(len(steps)),
             'checkpoints': steps}
    if navigator:
        value['navigator'] = list(navigator)
    if children:
        value['navigator_children'] = dict(children)
    return value


def program(key, feature, steps, *, setup=(), notes=''):
    """A program episode: no evaluator; setup prepares the state and every point is a deterministic observation."""
    items = list(setup)
    for checkpoint in steps:
        checkpoint['depends_on'] = ['setup:' + item['id'] for item in items] + list(checkpoint.get('depends_on', ()))
        checkpoint['assertions'] = []
        used = {}
        for check in checkpoint.pop('checks'):
            name = check.pop('slug')
            used[name] = used.get(name, 0) + 1
            suffix = name if used[name] == 1 else f'{name}-{used[name]}'
            checkpoint['assertions'].append({'id': f'{key}/{checkpoint["id"]}/{suffix}', 'channel': 'backend', 'method': 'program',
                                             'requirement': check['description'], 'check': check})
    return {'id': key, 'feature': feature, 'execution': 'program',
            'initial_state': 'Fresh application process with an empty DATA_DIR; the listed documents are in the inbox.' + (' ' + notes if notes else ''),
            'setup': items, 'inputs': {'input_folder': inbox(key), 'output_folder': outbox(key), 'documents': {}}, 'checkpoints': steps}
