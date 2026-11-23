"""Program episodes: no evaluator. Each checkpoint starts in a fresh browser profile on the editor with a new diagram
of its database, loads its diagram through the application's import, applies a scripted stimulus and checks what the
application exports or shows. Checkpoints do not depend on each other.
"""
import fixtures as F

INITIAL = ('Fresh browser profile on the editor. Each checkpoint starts again from a fresh profile, chooses the '
           'database of a new diagram and imports its own diagram, so checkpoints do not depend on each other.')


def point(name, requirement, check, requires=(), tol=None):
    check = dict(check)
    if tol is not None:
        check['tol'] = tol
    return {'name': name, 'requirement': requirement, 'check': check, 'requires': list(requires)}


def case(cid, goal, prep, points):
    return {'id': cid, 'goal': goal, 'prep': list(prep), 'points': points}


def episode(key_, feature, cases):
    checkpoints = []
    for c in cases:
        assertions = []
        for p in c.pop('points'):
            a = {'id': f'{key_}/{c["id"]}/{p["name"]}', 'channel': 'backend', 'method': 'program',
                 'requirement': p['requirement'], 'check': p['check']}
            if p['requires']:
                a['requires'] = [f'{key_}/{r}' for r in p['requires']]
            assertions.append(a)
        checkpoints.append({**c, 'assertions': assertions, 'depends_on': ['setup:editor']})
    return {'id': key_, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL,
            'setup': [{'id': 'editor'}], 'inputs': {}, 'checkpoints': checkpoints}


def fresh(db):
    return {'do': 'fresh', 'db': db}


def load(key):
    return {'do': 'import-json', 'fixture': key}


EXPORT_SQL = ['File', 'Export SQL']
DIALECTS = {'mysql': 'MySQL', 'postgresql': 'PostgreSQL', 'sqlite': 'SQLite', 'mariadb': 'MariaDB',
            'transactsql': 'MSSQL', 'oraclesql': 'Oracle'}


def sql(key, export=EXPORT_SQL, column=None):
    spec = {'type': 'sql', 'export': list(export), 'key': key}
    if column is not None:
        spec['column'] = column
    return spec


def order(export=EXPORT_SQL):
    return {'type': 'sql-order', 'export': list(export)}


# Statements of each export and the columns that get their own point (a column whose rendering already has a point
# in the same exporter is checked only through its table's column list). Collected from the reference.
PLAN = {
    'mariadb-library|File>Export SQL': [['table:members', ['id', 'card', 'ip', 'name', 'joined', 'fee']], ['index:members_name', None], ['table:loans', ['id', 'member_id', 'state', 'due']], ['index:loans_member_due', None], ['fk:loans(member_id)->members(id)', None], ['view:late_loans', None]],
    'mssql-crm|File>Export SQL': [['table:accounts', ['id', 'name', 'balance', 'opened', 'active', 'guid', 'note']], ['description:accounts', None], ['description:accounts.note', None], ['index:accounts_name_balance', None], ['table:contacts', ['id', 'account_id', 'email', 'code']], ['index:contacts_email', None], ['fk:contacts(account_id)->accounts(id)', None], ['view:rich_accounts', None]],
    'mysql-catalog|File>Export SQL': [['table:products', ['id', 'sku', 'price', 'tags', 'stock', 'released', 'blurb', 'specs']], ['table:tags', ['product_id', 'label', 'weight']], ['table:reviews', ['id', 'product_id', 'label', 'stars']], ['index:reviews_stars', None], ['fk:tags(product_id)->products(id)', None], ['fk:reviews(product_id,label)->tags(product_id,label)', None], ['view:cheap_products', None], ['view:tagged', None]],
    'mysql-shop|File>Export SQL': [['table:customers', ['email', 'vip', 'credit']], ['index:customers_email_idx', None], ['table:orders', ['id', 'customer_id', 'status', 'placed']], ['index:orders_status_placed', None], ['fk:orders(customer_id)->customers(id)', None]],
    'oracle-hr|File>Export SQL': [['table:departments', ['id', 'name', 'budget', 'created']], ['table:employees', ['dept_id', 'email', 'photo', 'remote']], ['index:employees_dept', None], ['index:employees_email', None], ['fk:employees(dept_id)->departments(id)', None], ['fk:employees(boss_id)->employees(id)', None], ['fk:departments(id)->employees(id)', None], ['view:dept_staff', None]],
    'postgres-events|File>Export SQL': [['enum:mood', None], ['type:address', None], ['comment:type:address', None], ['table:venues', ['id', 'name', 'site', 'opened', 'ref', 'capacity']], ['comment:table:venues', None], ['comment:column:venues.capacity', None], ['table:events', ['id', 'venue_id', 'mood', 'tags', 'price', 'meta', 'place']], ['index:events_venue', None], ['index:events_venue_price', None], ['table:festivals', ['days']], ['fk:events(venue_id)->venues(id)', None], ['view:busy_venues', None], ['comment:view:busy_venues', None], ['view:all_events', None]],
    'sqlite-notes|File>Export SQL': [['table:folders', ['id', 'title', 'color', 'pinned']], ['index:folders_title', None], ['table:pages', ['folder_id', 'body', 'size', 'edited', 'data']], ['index:pages_folder_edited', None], ['table:links', []], ['view:pinned_pages', None]],
    'mariadb-types|File>Export SQL': [['table:hosts', ['id', 'uid', 'v6', 'port', 'seen', 'note', 'mask', 'role']]],
    'mssql-types|File>Export SQL': [['table:samples', ['tiny', 'cash', 'at', 'old', 'clock', 'code', 'memo', 'raw', 'pic', 'doc', 'anything', 'ratio', 'exact', 'wide']]],
    'mysql-types|File>Export SQL': [['table:samples', ['medium', 'flag', 'born', 'ratio', 'stamp', 'at', 'code', 'raw', 'packed', 'short', 'mid', 'long', 'tb', 'mb', 'lb', 'perms', 'shape', 'route', 'zone']]],
    'oracle-types|File>Export SQL': [['table:samples', ['amount', 'ratio', 'legacy', 'code', 'initials', 'text', 'ntext', 'raw', 'file', 'doc', 'day', 'span']]],
    'postgres-types|File>Export SQL': [['table:samples', ['id', 'small', 'big', 'price', 'raw', 'at', 'at_tz', 'span', 'net', 'host', 'mac', 'bits', 'vbits', 'words', 'doc', 'code', 'ratio', 'day', 'ok', 'shape', 'ring']]],
    'generic-store|File>Export SQL>MSSQL': [['type:money', None], ['table:items', ['id', 'code', 'label', 'kind', 'flags', 'price', 'weight', 'active', 'added', 'seen', 'photo', 'extra']], ['index:items_label', None], ['table:stock', ['id', 'item_id', 'count', 'day', 'opens', 'hash', 'blob', 'memo', 'grade', 'score']], ['index:stock_item_day', None], ['table:moves', ['id', 'stock_id', 'note']], ['fk:stock(item_id)->items(id)', None], ['fk:moves(stock_id)->stock(id)', None], ['view:cheap_items', None], ['view:item_moves', None]],
    'generic-typed|File>Export SQL>MSSQL': [['type:money', None], ['type:point2d', None], ['table:wallets', ['owner', 'balance', 'limit']], ['table:transfers', ['wallet_id', 'kind', 'at']], ['fk:transfers(wallet_id)->wallets(id)', None]],
    'generic-store|File>Export SQL>MariaDB': [['table:items', ['id', 'code', 'label', 'kind', 'flags', 'price', 'weight', 'active', 'added', 'seen', 'photo', 'extra']], ['index:items_label', None], ['table:stock', ['id', 'item_id', 'count', 'day', 'opens', 'hash', 'blob', 'memo', 'grade', 'ratio', 'score']], ['index:stock_item_day', None], ['table:moves', ['id', 'stock_id', 'note']], ['fk:stock(item_id)->items(id)', None], ['fk:moves(stock_id)->stock(id)', None], ['view:cheap_items', None], ['view:item_moves', None]],
    'generic-typed|File>Export SQL>MariaDB': [['table:wallets', ['owner', 'balance', 'limit']], ['table:transfers', ['wallet_id', 'kind', 'at']], ['fk:transfers(wallet_id)->wallets(id)', None]],
    'generic-store|File>Export SQL>MySQL': [['table:items', ['id', 'code', 'label', 'kind', 'flags', 'price', 'weight', 'active', 'added', 'seen', 'photo', 'extra']], ['index:items_label', None], ['table:stock', ['id', 'item_id', 'count', 'day', 'opens', 'hash', 'blob', 'memo', 'grade', 'ratio', 'score']], ['index:stock_item_day', None], ['table:moves', ['id', 'stock_id', 'note']], ['fk:stock(item_id)->items(id)', None], ['fk:moves(stock_id)->stock(id)', None], ['view:cheap_items', None], ['view:item_moves', None]],
    'generic-typed|File>Export SQL>MySQL': [['table:wallets', ['owner', 'balance', 'limit']], ['table:transfers', ['wallet_id', 'kind', 'at']], ['fk:transfers(wallet_id)->wallets(id)', None]],
    'generic-store|File>Export SQL>Oracle': [['create:domain:kind_t', None], ['create:domain:flags_t', None], ['table:items', ['id', 'code', 'label', 'kind', 'flags', 'price', 'weight', 'active', 'added', 'seen', 'photo', 'extra']], ['index:items_label', None], ['table:stock', ['id', 'item_id', 'count', 'day', 'hash', 'memo', 'grade', 'ratio', 'score']], ['index:stock_item_day', None], ['table:moves', ['id', 'stock_id', 'note']], ['fk:stock(item_id)->items(id)', None], ['fk:moves(stock_id)->stock(id)', None], ['view:cheap_items', None], ['view:item_moves', None]],
    'generic-typed|File>Export SQL>Oracle': [['table:wallets', ['owner', 'balance', 'limit']], ['create:domain:kind_t', None], ['table:transfers', ['wallet_id', 'kind', 'at']], ['fk:transfers(wallet_id)->wallets(id)', None]],
    'generic-store|File>Export SQL>PostgreSQL': [['type:money', None], ['comment:type:money', None], ['enum:kind_t', None], ['enum:flags_t', None], ['table:items', ['id', 'code', 'label', 'kind', 'flags', 'price', 'weight', 'active', 'added', 'seen', 'photo', 'extra']], ['comment:table:items', None], ['comment:column:items.label', None], ['index:items_label', None], ['table:stock', ['id', 'item_id', 'count', 'day', 'opens', 'hash', 'blob', 'memo', 'grade', 'ratio', 'score']], ['index:stock_item_day', None], ['table:moves', ['id', 'stock_id', 'note']], ['fk:stock(item_id)->items(id)', None], ['fk:moves(stock_id)->stock(id)', None], ['view:cheap_items', None], ['comment:view:cheap_items', None], ['view:item_moves', None]],
    'generic-typed|File>Export SQL>PostgreSQL': [['type:money', None], ['type:point2d', None], ['comment:type:point2d', None], ['table:wallets', ['owner', 'balance', 'limit']], ['enum:kind_t', None], ['table:transfers', ['wallet_id', 'kind', 'at']], ['comment:table:transfers', None], ['fk:transfers(wallet_id)->wallets(id)', None]],
    'generic-store|File>Export SQL>SQLite': [['table:items', ['id', 'code', 'label', 'kind', 'flags', 'price', 'weight', 'active', 'added', 'seen']], ['index:items_label', None], ['table:stock', ['item_id', 'count', 'grade']], ['index:stock_item_day', None], ['table:moves', []], ['view:cheap_items', None], ['view:item_moves', None]],
    'generic-typed|File>Export SQL>SQLite': [['table:wallets', ['owner', 'balance']], ['table:transfers', ['wallet_id', 'kind', 'at']]],
}


def label(key):
    kind, _, rest = key.partition(':')
    return (kind + '-' + rest).replace(':', '-').replace('->', '-to-').replace('(', '.').replace(')', '').replace(',', '+')


def statement_points(plan, export, script):
    """Points for one export: each statement, each listed column, and the statement order."""
    out = []
    for key, columns in plan:
        kind, _, name = key.partition(':')
        if kind == 'table':
            out.append(point(name, f"In the {script}, the CREATE TABLE statement for {name} has the reference's "
                                   'header, column order, table constraints and table options.', sql(key, export)))
            for column in columns:
                out.append(point(f'{name}.{column}', f"In the {script}, column {name}.{column} has the reference's "
                                                     'type and column clauses.', sql(key, export, column)))
            continue
        what = {'index': 'creates the index', 'fk': 'adds the foreign key', 'view': 'creates the view',
                'enum': 'creates the enum type', 'type': 'creates the type', 'comment': 'sets the comment on',
                'description': 'adds the description of', 'create': 'creates'}[kind]
        out.append(point(label(key), f'The {script} {what} {name} as the reference does.', sql(key, export)))
    if len(plan) > 1:
        out.append(point('order', f"The statements of the {script} come in the reference's order.", order(export)))
    return out


OWN = [('mysql', [('shop', 'mysql-shop', 'Shop'), ('catalog', 'mysql-catalog', 'Catalog'),
                  ('types', 'mysql-types', 'Kinds')]),
       ('mariadb', [('library', 'mariadb-library', 'Library'), ('types', 'mariadb-types', 'Kinds')]),
       ('postgresql', [('events', 'postgres-events', 'Events'), ('types', 'postgres-types', 'Kinds')]),
       ('sqlite', [('notes', 'sqlite-notes', 'Notes')]),
       ('transactsql', [('crm', 'mssql-crm', 'CRM'), ('types', 'mssql-types', 'Kinds')]),
       ('oraclesql', [('hr', 'oracle-hr', 'HR'), ('types', 'oracle-types', 'Kinds')])]
GENERIC = [('store', 'generic-store', 'Store'), ('typed', 'generic-typed', 'Typed')]


def sql_exports():
    flows = []
    for db, cases in OWN:
        flows.append(episode('sql-export-' + DIALECTS[db].lower(), 'sql-export', [
            case(cid, f'Export the {DIALECTS[db]} diagram "{title}" as SQL (File, Export SQL).',
                 [fresh(db), load(fixture)],
                 statement_points(PLAN[f'{fixture}|File>Export SQL'], EXPORT_SQL, f'{DIALECTS[db]} script'))
            for cid, fixture, title in cases]))
    for db, dialect in DIALECTS.items():
        export = EXPORT_SQL + [dialect]
        flows.append(episode('sql-convert-' + dialect.lower(), 'sql-convert', [
            case(cid, f'Export the generic diagram "{title}" as {dialect} SQL (File, Export SQL, {dialect}).',
                 [fresh('generic'), load(fixture)],
                 statement_points(PLAN[f'{fixture}|' + '>'.join(export)], export,
                                  f'{dialect} script of the generic diagram'))
            for cid, fixture, title in GENERIC]))
    for flow in flows:
        own = flow['id'].startswith('sql-export-')
        suffix = flow['id'].split('sql-export-' if own else 'sql-convert-', 1)[1]
        db = next(db for db, label in DIALECTS.items() if label.lower() == suffix)
        fixture_db = db if own else 'generic'
        export = EXPORT_SQL if own else EXPORT_SQL + [DIALECTS[db]]
        diagram = F.coverage_types(fixture_db)
        columns = [field['name'] for field in diagram['tables'][0]['fields']]
        extra = episode(flow['id'], flow['feature'], [case('additional-types',
                         'Export the additional column types supported by the editor.',
                         [fresh(fixture_db), load('coverage-' + fixture_db)],
                         statement_points([['table:type_choices', columns]], export, DIALECTS[db] + ' script'))])
        flow['checkpoints'].extend(extra['checkpoints'])
    return flows


def model(part, **extra):
    return {'type': 'model', 'part': part, **extra}


def sql_file(name, dialect=None, overwrite=False):
    step = {'do': 'import-sql', 'file': name}
    if dialect:
        step['dialect'] = dialect
    if overwrite:
        step['overwrite'] = True
    return step


# Scripts per importer: the tables they define, with the tables whose indices/unique constraints and comment get
# their own point, and whether relationships, enums and types are defined.
IMPORT_CASES = [
    ('mysql', 'library.sql', ['authors', 'books', 'reviews'], ['authors', 'books'], ['authors'], True, False),
    ('postgresql', 'shop-pg.sql', ['customers', 'orders', 'lines'], ['customers', 'orders'], ['customers'], True,
     True),
    ('sqlite', 'todo.sql', ['lists', 'items', 'tags'], ['items'], [], True, False),
    ('transactsql', 'helpdesk.sql', ['agents', 'tickets'], ['agents', 'tickets'], [], False, False),
    ('oraclesql', 'school.sql', ['teachers', 'courses', 'seats'], ['teachers'], [], True, False),
    ('mariadb', 'shops-maria.sql', ['shops', 'staff'], ['shops', 'staff'], ['shops'], True, False),
]


def sql_imports():
    flows = []
    for db, name, tables, keyed, commented, rels, typed in IMPORT_CASES:
        dialect = DIALECTS[db]
        own = [point('tables', f'Importing {name} creates its tables in script order.', model('tables'))]
        for table in tables:
            own.append(point(table + '.columns', f'The imported table {table} has the reference\'s columns: names, '
                                                 'types, sizes, keys, NOT NULL, UNIQUE, auto increment, defaults, '
                                                 'checks, comments and enum values.',
                             model('table', name=table, aspects=['fields'])))
        for table in keyed:
            own.append(point(table + '.keys', f'The imported table {table} has the reference\'s indices and unique '
                                              'constraints.', model('table', name=table, aspects=['indices', 'uniques'])))
        for table in commented:
            own.append(point(table + '.comment', f'The imported table {table} keeps its comment.',
                             model('table', name=table, aspects=['comment'])))
        if rels:
            own.append(point('relationships', 'The foreign keys become relationships with the reference\'s names, '
                                              'columns, cardinality and actions.', model('relationships')))
        if typed:
            own.append(point('enums', 'The enum type of the script becomes an enum of the diagram.', model('enums')))
            own.append(point('types', 'The composite type of the script becomes a type of the diagram.',
                             model('types')))
        generic = [point(table + '.types', f'Imported into a generic diagram, the columns of {table} get the '
                                           'reference\'s generic types and sizes.',
                         model('table', name=table, aspects=['types'])) for table in tables]
        flows.append(episode('sql-import-' + dialect.lower(), 'sql-import', [
            case('own', f'Import the {dialect} script {name} into a new {dialect} diagram (File, Import from SQL, '
                        'upload the file).', [fresh(db), sql_file(name)], own),
            case('generic', f'Import the {dialect} script {name} into a new generic diagram (File, Import from SQL, '
                            f'{dialect}, upload the file).', [fresh('generic'), sql_file(name, dialect)], generic),
        ]))
    flows.append(episode('sql-import-options', 'sql-import', [
        case('append', 'The MySQL diagram "Shop" is open. Import library.sql without overwriting.',
             [fresh('mysql'), load('mysql-shop'), sql_file('library.sql')], [
                 point('tables', 'The imported tables are added after the diagram\'s own tables.', model('tables')),
                 point('relationships', 'The diagram keeps its relationship and gains the imported ones.',
                       model('relationships'))]),
        case('overwrite', 'The MySQL diagram "Shop" is open. Import library.sql and choose to overwrite the existing '
                          'diagram.', [fresh('mysql'), load('mysql-shop'), sql_file('library.sql', overwrite=True)], [
                 point('tables', 'Only the imported tables remain.', model('tables')),
                 point('relationships', 'Only the imported relationships remain.', model('relationships'))]),
        case('refused', 'The MySQL diagram "Shop" is open. Try to import broken.sql, a script with a syntax error.',
             [fresh('mysql'), load('mysql-shop'), sql_file('broken.sql')], [
                 point('unchanged', 'The script is refused and the diagram keeps its tables.', model('tables'),
                       requires=['append/tables'])]),
    ]))
    return flows


TEXT_PLAN = {
    'generic-store|dbml': ['enum:kind_box_bag_t', 'enum:flags_hot_cold_t', 'table:items', 'table:stock', 'table:moves',
                           'ref:fk_stock_item_id_items', 'ref:fk_moves_stock_id_stock'],
    'generic-typed|dbml': ['enum:kind_in_out_t', 'table:wallets', 'table:transfers',
                           'ref:fk_transfers_wallet_id_wallets'],
    'mysql-catalog|dbml': ['enum:tags_new_sale_t', 'table:products', 'table:tags', 'table:reviews',
                           'ref:fk_tags_product_id_products', 'ref:fk_reviews_tag'],
    'postgres-events|dbml': ['enum:mood', 'table:venues', 'table:events', 'table:festivals',
                             'ref:fk_events_venue_id_venues'],
    'generic-store|mermaid': ['entity:items', 'entity:stock', 'entity:moves', 'relationships'],
    'postgres-events|mermaid': ['entity:venues', 'entity:events', 'entity:festivals', 'relationships'],
    'generic-store|markdown': ['Summary', 'Database type', 'Table structure/items', 'Table structure/items/Enums/kind',
                               'Table structure/items/Indexes', 'Table structure/stock', 'Table structure/stock/Indexes',
                               'Table structure/stock/Unique constraints', 'Table structure/moves', 'Relationships',
                               'Types', 'Views/cheap_items', 'Views/item_moves', 'Database Diagram'],
    'generic-typed|markdown': ['Summary', 'Table structure/wallets', 'Table structure/transfers',
                               'Table structure/transfers/Enums/kind', 'Relationships', 'Types', 'Database Diagram'],
    'mysql-catalog|markdown': ['Summary', 'Database type', 'Table structure/products', 'Table structure/tags',
                               'Table structure/tags/Unique constraints', 'Table structure/reviews',
                               'Table structure/reviews/Indexes', 'Relationships', 'Views/cheap_products',
                               'Views/tagged (materialized)', 'Database Diagram'],
    'postgres-events|markdown': ['Summary', 'Database type', 'Table structure/venues', 'Table structure/events',
                                 'Table structure/events/Indexes', 'Table structure/events/Unique constraints',
                                 'Table structure/festivals', 'Relationships', 'Types',
                                 'Views/busy_venues (materialized)', 'Views/all_events', 'Database Diagram'],
}
TEXT_FIXTURES = {'generic-store': ('generic', 'Store'), 'generic-typed': ('generic', 'Typed'),
                 'mysql-catalog': ('mysql', 'Catalog'), 'postgres-events': ('postgresql', 'Events')}
TEXT_EXPORTS = {'dbml': ('DBML', 'DBML file'), 'mermaid': ('Mermaid', 'Mermaid diagram'),
                'markdown': ('Markdown', 'Markdown documentation')}


def block(fmt, key, export):
    return {'type': 'blocks', 'format': fmt, 'key': key, 'export': list(export)}


def text_exports():
    flows = []
    for fmt, (entry, what) in TEXT_EXPORTS.items():
        export = ['File', 'Export as', entry]
        cases = []
        for fixture, (db, title) in TEXT_FIXTURES.items():
            keys = TEXT_PLAN.get(f'{fixture}|{fmt}')
            if not keys:
                continue
            points = []
            for key in keys:
                name = key.replace('/', '.').replace(' ', '-').replace('(', '').replace(')', '').replace(':', '-')
                full = f'section:{title} documentation/{key}' if fmt == 'markdown' else key
                points.append(point(name, f'The {what} of "{title}" has the reference\'s {key} block.',
                                    block(fmt, full, export)))
            if fmt != 'mermaid':
                points.append(point('order', f'The blocks of the {what} come in the reference\'s order.',
                                    {'type': 'blocks-order', 'format': fmt, 'export': export}))
            cases.append(case(fixture.split('-', 1)[1], f'Export the diagram "{title}" as {entry} (File, Export as, '
                                                        f'{entry}).', [fresh(db), load(fixture)], points))
        flows.append(episode(fmt + '-export', fmt + '-export', cases))
    return flows


def dbml_imports():
    blog = 'Import blog.dbml (File, Import from, DBML) into a new {} diagram.'
    generic = [point('tables', 'The DBML tables become tables in file order.', model('tables'))]
    for table in ('users', 'posts', 'tags'):
        generic.append(point(table + '.columns', f'The columns of {table} carry the DBML types, sizes, settings, '
                                                 'defaults and notes.', model('table', name=table, aspects=['fields'])))
    generic += [
        point('posts.indexes', 'The named DBML indexes of posts become indices.',
              model('table', name='posts', aspects=['indices', 'uniques'])),
        point('users.note', 'The table note and header colour of users are kept.',
              model('table', name='users', aspects=['comment', 'color'])),
        point('relationships', 'Inline and standalone refs become relationships with their names, cardinality and '
                               'actions.', model('relationships')),
    ]
    return [episode('dbml-import', 'dbml-import', [
        case('generic', blog.format('generic'), [fresh('generic'), {'do': 'import-dbml', 'file': 'blog.dbml'}],
             generic),
        case('postgresql', blog.format('PostgreSQL'), [fresh('postgresql'), {'do': 'import-dbml', 'file': 'blog.dbml'}],
             [point('enums', 'In a PostgreSQL diagram the DBML enum becomes an enum.', model('enums'))]),
        case('refused', 'The generic diagram "Store" is open. Try to import broken.dbml, a file with a syntax error.',
             [fresh('generic'), load('generic-store'), {'do': 'import-dbml', 'file': 'broken.dbml'}],
             [point('unchanged', 'The file is refused and the diagram keeps its tables.', model('tables'),
                    requires=['generic/tables'])]),
    ])]


MSG = {
    'error': 'The file contains an error.',
    'missing': 'The file is missing necessary properties for a diagram.',
    'mismatch': "The imported diagram and the open diagram don't use matching databases.",
    'ready': 'Everything looks good. You can now import.',
    'overwrite': 'The current diagram is not empty. Importing a new diagram will overwrite the current changes.',
    'no-table': 'Relationship fk_to_ghost_table references a table that does not exist.',
    'no-column': 'Relationship fk_to_ghost_column references a column that does not exist.',
}


def shown(*texts, reveal=()):
    return {'type': 'shown', 'texts': list(texts), 'reveal': list(reveal)}


def json_files():
    board = [fresh('generic'), load('generic-board')]
    flows = [episode('json-roundtrip', 'json', [
        case('board', 'Import the generic diagram file "Board" and export it again as JSON.', board, [
            point('tables', 'The tables are kept in order.', model('tables')),
            point('teams', 'A locked table keeps its columns, colour, position and lock.',
                  model('table', name='teams', aspects=['fields', 'color', 'position', 'flags'])),
            point('members', 'A hidden table keeps its columns, comment, colour, position and hidden state.',
                  model('table', name='members', aspects=['fields', 'comment', 'color', 'position', 'flags'])),
            point('relationships', 'The relationships are kept.', model('relationships')),
            point('notes', 'The notes keep their titles, contents, colours and positions.',
                  model('notes', aspects=['title', 'content', 'color', 'position'])),
            point('areas', 'The subject areas keep their names, colours, positions and sizes.',
                  model('areas', aspects=['name', 'color', 'position', 'size'])),
            point('views', 'The view keeps its base table, columns, join, condition and comment.', model('views')),
            point('types', 'The custom type of the generic diagram is kept.', model('types')),
            point('title', 'The diagram title is the imported one.', model('title')),
        ]),
        case('postgresql', 'Import the PostgreSQL diagram file "Events" and export it again as JSON.',
             [fresh('postgresql'), load('postgres-events')], [
                 point('enums', 'The enum is kept.', model('enums')),
                 point('types', 'The composite type is kept.', model('types')),
                 point('festivals', 'The inherited table keeps its parent.',
                       model('table', name='festivals', aspects=['fields', 'inherits'])),
                 point('events', 'Array, enum and custom-type columns are kept.',
                       model('table', name='events', aspects=['fields'])),
             ]),
    ])]
    keys = []
    for db, fixture, title in (('mysql', 'mysql-shop', 'Shop'), ('postgresql', 'postgres-events', 'Events'),
                               ('generic', 'generic-store', 'Store'), ('sqlite', 'sqlite-notes', 'Notes')):
        required = {'database': 'text', 'title': 'text', **{key: 'list' for key in
                    ('notes', 'relationships', 'subjectAreas', 'tables', 'views')}}
        if db in ('generic', 'postgresql'):
            required['types'] = 'list'
        if db == 'postgresql':
            required['enums'] = 'list'
        keys.append(case(db, f'Export the {db} diagram "{title}" as JSON.', [fresh(db), load(fixture)], [
            point('keys', f'The {db} diagram contains the required typed data properties; extra metadata is allowed.',
                  {'type': 'json-keys', 'required': required}),
            point('database', 'The diagram file names the database of the diagram.', model('database'))]))
    flows.append(episode('json-properties', 'json', keys))
    shop = [fresh('mysql'), load('mysql-shop')]
    flows.append(episode('json-import-checks', 'json', [
        case('ready', 'In a new MySQL diagram, choose the diagram file "Shop" in the JSON import dialog.',
             [fresh('mysql'), {'do': 'stage-json', 'fixture': 'mysql-shop'}], [
                 point('message', 'The dialog says the file is ready to import.', shown(MSG['ready'], MSG['overwrite']))]),
        case('overwrite', 'With the MySQL diagram "Shop" open, choose the MySQL diagram file "Catalog" in the JSON '
                          'import dialog.',
             shop + [{'do': 'stage-json', 'fixture': 'mysql-catalog'}], [
                 point('warning', 'The dialog warns that importing overwrites the current diagram.',
                       shown(MSG['overwrite'], MSG['ready']))]),
        case('replaced', 'With the diagram "Shop" open, import the MySQL diagram file "Catalog".',
             shop + [load('mysql-catalog')], [
                 point('tables', 'The imported diagram replaces the open one.', model('tables')),
                 point('title', 'The diagram takes the imported title.', model('title'))]),
        case('not-json', 'With the diagram "Shop" open, choose a file that is not valid JSON in the JSON import dialog.',
             shop + [{'do': 'stage-json', 'file': 'not-json.json'}], [
                 point('message', 'The dialog reports an error in the file.', shown(MSG['error']),
                       requires=['ready/message']),
                 point('unchanged', 'Nothing is imported.', model('tables'), requires=['replaced/tables'])]),
        case('missing', 'With the diagram "Shop" open, choose a JSON file without tables in the JSON import dialog.',
             shop + [{'do': 'stage-json', 'file': 'no-tables.json'}], [
                 point('message', 'The dialog reports missing diagram properties.', shown(MSG['missing']),
                       requires=['ready/message']),
                 point('unchanged', 'Nothing is imported.', model('tables'), requires=['replaced/tables'])]),
        case('mismatch', 'With the MySQL diagram "Shop" open, choose a PostgreSQL diagram file in the JSON import '
                         'dialog.', shop + [{'do': 'stage-json', 'fixture': 'mismatched'}], [
                 point('message', 'The dialog reports that the databases do not match.', shown(MSG['mismatch']),
                       requires=['ready/message']),
                 point('unchanged', 'Nothing is imported.', model('title'), requires=['replaced/title'])]),
        case('no-table', 'In a new MySQL diagram, choose a diagram file whose relationship points to a missing table.',
             [fresh('mysql'), {'do': 'stage-json', 'fixture': 'dangling-table'}], [
                 point('message', 'The dialog names the relationship that references a missing table.',
                       shown(MSG['no-table']), requires=['ready/message'])]),
        case('no-column', 'In a new MySQL diagram, choose a diagram file whose relationship points to a missing '
                          'column.', [fresh('mysql'), {'do': 'stage-json', 'fixture': 'dangling-column'}], [
                 point('message', 'The dialog names the relationship that references a missing column.',
                       shown(MSG['no-column']), requires=['ready/message'])]),
    ]))
    return flows


# Problems each diagram has, as the problems list words them (point name, message).
ISSUES = {
    1: [('no-name', 'Declared a table with no name'), ('duplicate-table', "Duplicate table by the name 'dup'")],
    2: [('empty-column-name', "Empty column `name` in table 'blank_cols'"),
        ('empty-column-type', "Empty column `type` in table 'blank_cols'")],
    3: [('enum-no-values', "'mood' column of table 'feelings' is of type `ENUM` but no values have been specified"),
        ('default-type', "Default value for column 'qty' in table 'stock' does not match its type"),
        ('not-null-default-null', "'note' column of table 'stock' is NOT NULL but has default NULL")],
    4: [('duplicate-column', "Duplicate table columns by name 'x' in table 'twins'"),
        ('duplicate-index', "Duplicate index by name 'i1' in table 'stock'"),
        ('index-no-name', "Declared an index with no name in table 'stock'")],
    5: [('index-no-columns', "Index in table 'idx_empty' indexes no columns"),
        ('no-primary-key', "Table 'nokey' has no primary key"),
        ('unique-no-columns', "Index in table 'uq_empty' indexes no columns")],
    6: [('duplicate-reference', "Duplicate reference by the name 'fk_same'"),
        ('circular', "Circular dependency involving table 'a'")],
    7: [('type-no-name', 'Declared a type with no name'), ('duplicate-type', "Duplicate types by the name 'pair'"),
        ('type-no-columns', "Declared an empty type 'hollow' with no columns")],
    8: [('type-column-no-name', "Empty column `name` in type 'loose'"),
        ('type-column-no-type', "Empty column `type` in type 'loose'"),
        ('type-enum-no-values', "'kind' column of type 'loose' is of type `ENUM` but no values have been specified")],
    9: [('duplicate-type-column', "Duplicate type columns by name 'v' in type 'twin'"),
        ('enum-no-name', 'Found enum with no name'), ('enum-empty', "Found enum 'empty' with no values")],
    10: [('inherited-column', "Column 'id' in table 'kid' with inherited definition will be merged"),
         ('duplicate-enum', "Duplicate enums with the name 'state'")],
    11: [('view-no-name', 'View with no name'), ('duplicate-view', "Duplicate views with the name 'v'"),
         ('view-table-name', "View 'orders' has the same name as a table")],
    12: [('view-no-base', "View 'nobase' has no base table"), ('join-no-table', "Join with no table in view 'j1'"),
         ('join-no-condition', "Join on 'items' in view 'j2' has no condition")],
    13: [('join-order', "Join on 'items' in view 'j3' references a table joined after it"),
         ('view-empty-column', "Empty output column in view 'cols'"),
         ('view-duplicate-column', "Duplicate output column 'id' in view 'dupcols'")],
}
# Near misses that must not be reported, bound to a reported problem of the same diagram.
NOT_ISSUES = {
    3: ('valid-defaults', 'default-type', ["Default value for column 'count' in table 'stock' does not match its type",
                                           "'memo' column of table 'stock' is NOT NULL but has default NULL"]),
    6: ('self-reference', 'circular', ["Circular dependency involving table 'tree'"]),
    1: ('keys-present', 'no-name', ["Table 'dup' has no primary key"]),
}
PROBLEMS = ['Problems']


def problems():
    cases = []
    for n, found in ISSUES.items():
        db = 'postgresql' if 7 <= n <= 10 else 'generic'
        points = [point(name, f'The problems list reports: {text}', shown(text, reveal=PROBLEMS))
                  for name, text in found]
        if n in NOT_ISSUES:
            name, companion, texts = NOT_ISSUES[n]
            points.append(point(name, 'The problems list does not report: ' + ' / '.join(texts),
                                shown(*texts, reveal=PROBLEMS), requires=[f'diagram-{n}/{companion}']))
        cases.append(case(f'diagram-{n}', f'Import the {db} diagram "Problems {n}" and open the problems list.',
                          [fresh(db), load(f'issues-{n}')], points))
    cases.append(case('clean', 'Import the generic diagram "No problems" and open the problems list.',
                      [fresh('generic'), load('issues-0')], [
                          point('none', 'The problems list says that no problems were detected.',
                                shown('No problems were detected.', reveal=PROBLEMS))]))
    cases.append(case('strict-off', 'Import the generic diagram "Problems 1", press Control+Shift+M (the strict mode '
                                    'toggle of the View menu) and open the problems list.',
                      [fresh('generic'), load('issues-1'), {'do': 'press', 'key': 'Control+Shift+M'}], [
                          point('hidden', 'With strict mode switched off the list says that no problems will be '
                                          'displayed, and the problems are not listed.',
                                shown('Strict mode is off so no problems will be displayed.',
                                      'Declared a table with no name', reveal=PROBLEMS))]))
    return [episode('problems', 'problems', cases)]


def press(key):
    return {'do': 'press', 'key': key}


def select(name):
    return {'do': 'select', 'name': name}


def edit_actions():
    shop = [fresh('mysql'), load('mysql-shop')]
    paste = [{'do': 'away'}, press('Control+v')]
    return [episode('edit-actions', 'editing', [
        case('duplicate', 'The MySQL diagram "Shop" is open. Select the table customers and press Control+D.',
             shop + [select('customers'), press('Control+d')], [
                 point('tables', 'A copy of customers is added after the existing tables.', model('tables')),
                 point('copy', 'The copy has the same columns and lies 20 units right of and below the original.',
                       model('table', name='customers', nth=1, aspects=['fields', 'position']))]),
        case('delete', 'Select the table customers and press Delete.', shop + [select('customers'), press('Delete')], [
            point('tables', 'The table is removed.', model('tables')),
            point('relationships', 'The relationship to the removed table is removed with it.',
                  model('relationships'), requires=['undo/relationships'])]),
        case('undo', 'Delete the table customers, then press Control+Z.',
             shop + [select('customers'), press('Delete'), press('Control+z')], [
                 point('tables', 'Undo restores the table.', model('tables')),
                 point('relationships', 'Undo restores its relationship.', model('relationships'))]),
        case('redo', 'Delete the table customers, undo with Control+Z, then redo with Control+Y.',
             shop + [select('customers'), press('Delete'), press('Control+z'), press('Control+y')], [
                 point('tables', 'Redo removes the table again.', model('tables'))]),
        case('cut', 'Select the table orders and press Control+X.', shop + [select('orders'), press('Control+x')], [
            point('clipboard', 'The clipboard holds the table orders as JSON.',
                  {'type': 'clipboard', 'json': 'table', 'aspects': ['name', 'fields', 'indices']}),
            point('tables', 'The table is removed.', model('tables'))]),
        case('copy', 'Select the table customers and press Control+C.', shop + [select('customers'), press('Control+c')],
             [point('clipboard', 'The clipboard holds the table customers as JSON, with its comment and indices.',
                    {'type': 'clipboard', 'json': 'table', 'aspects': ['name', 'fields', 'indices', 'comment']}),
              point('unchanged', 'Copying leaves the diagram unchanged.', model('tables'),
                    requires=['copy/clipboard'])]),
        case('paste-table', 'Put the JSON of a table on the clipboard and press Control+V in the editor.',
             shop + [{'do': 'clipboard', 'file': 'clip-table.json'}] + paste, [
                 point('tables', 'The pasted table is added.', model('tables')),
                 point('table', 'The pasted table keeps its columns, comment and colour and lies 20 units right of and '
                                'below the copied position.',
                       model('last-table', aspects=['name', 'fields', 'comment', 'color', 'position']))]),
        case('paste-note', 'Put the JSON of a note on the clipboard and press Control+V.',
             shop + [{'do': 'clipboard', 'file': 'clip-note.json'}] + paste, [
                 point('notes', 'The pasted note is added with its title, content, colour and shifted position.',
                       model('notes', aspects=['title', 'content', 'color', 'position']))]),
        case('paste-area', 'Put the JSON of a subject area on the clipboard and press Control+V.',
             shop + [{'do': 'clipboard', 'file': 'clip-area.json'}] + paste, [
                 point('areas', 'The pasted area is added with its name, colour, size and shifted position.',
                       model('areas', aspects=['name', 'color', 'size', 'position']))]),
        case('paste-text', 'Put plain text on the clipboard and press Control+V.',
             shop + [{'do': 'clipboard', 'text': 'customers, orders'}] + paste, [
                 point('unchanged', 'Text that is not an element is not pasted.', model('counts'),
                       requires=['paste-table/tables'])]),
        case('clear', 'The generic diagram "Board" is open. Choose Clear in the Edit menu and confirm.',
             [fresh('generic'), load('generic-board'), {'do': 'confirm-menu', 'menu': ['Edit', 'Clear']}], [
                 point('empty', 'Tables, relationships, notes, areas, views and types are all removed.',
                       model('counts'), requires=['duplicate/tables'])]),
        case('add-mysql', 'The MySQL diagram "Shop" is open. Press Add table in the tables list.',
             shop + [{'do': 'click', 'label': 'Add table'}], [
                 point('count', 'One table is added.', model('counts')),
                 point('columns', 'The new table of a MySQL diagram has one auto-incremented unsigned INTEGER key '
                                  'column id.', model('last-table', aspects=['fields']))]),
        case('add-generic', 'The generic diagram "Store" is open. Press Add table in the tables list.',
             [fresh('generic'), load('generic-store'), {'do': 'click', 'label': 'Add table'}], [
                 point('columns', 'The new table of a generic diagram has an INT key column id.',
                       model('last-table', aspects=['fields']))]),
        case('undo-menu', 'Press Add table, then choose Undo in the Edit menu.',
             shop + [{'do': 'click', 'label': 'Add table'}, {'do': 'menu', 'path': ['Edit', 'Undo']}], [
                 point('tables', 'Undo removes the added table.', model('tables'))]),
    ])]


def autolinks():
    def rel_point(name, requirement):
        return point(name.replace('fk_', '').replace('_', '-'), requirement, model('relationship', name=name))
    return [episode('auto-connect', 'editing', [
        case('autolink', 'The generic diagram "Autolink" is open. Choose Auto-connect foreign keys in the Edit menu '
                         'and confirm.',
             [fresh('generic'), load('autolink'), {'do': 'menu', 'path': ['Edit', 'Auto-connect foreign keys']},
              {'do': 'confirm', 'label': 'Auto-connect foreign keys'}], [
                 rel_point('fk_posts_user_id_users', 'A column named after the singular table name and its key '
                                                     '(user_id) is connected to users.id.'),
                 rel_point('fk_parcels_boxes_id_boxes', 'A column named after the plural table name and its key '
                                                        '(boxes_id) is connected to boxes.id.'),
                 rel_point('fk_parcels_boxid_boxes', 'A column named after the singular table name and its key '
                                                     'without underscore (boxid) is connected.'),
                 rel_point('fk_posts_category_id_categories', 'A unique column category_id is connected to '
                                                              'categories.id one to one.'),
                 rel_point('fk_cities_code_countries', 'A column with the name of a key that is not id (code) is '
                                                       'connected to that key.'),
                 rel_point('fk_cities_country_code_countries', 'country_code is connected to countries.code.'),
                 point('all', 'Exactly the reference\'s relationships exist: the already connected likes.user_id gets '
                              'no second relationship and cities.posts none.', model('relationships'),
                       requires=['autolink/posts-user-id-users']),
             ]),
    ])]


def persistence():
    shop = [fresh('mysql'), load('mysql-shop')]
    copy = {'do': 'dialog-fill', 'menu': ['File', 'Save as'], 'value': 'Duplicate store', 'button': 'Save as'}
    rename_orders = [{'do': 'table', 'name': 'orders'}, {'do': 'fill', 'placeholder': 'Name', 'value': 'purchases'}]
    return [episode('persistence', 'persistence', [
        case('reload', 'Import the MySQL diagram "Shop", then reload the page.', shop + [{'do': 'reload'}], [
            point('tables', 'After the reload the editor shows the saved diagram.', model('tables')),
            point('title', 'The saved diagram keeps its title.', model('title')),
            point('address', 'The editor address names the saved diagram (/editor/diagrams/<id>).',
                  {'type': 'page', 'path': '/editor/diagrams/[^/]+'})]),
        case('restart', 'Import "Shop", restart the application and reload the page.', shop + [{'do': 'restart'}], [
            point('tables', 'The diagram survives a restart of the application.', model('tables'))]),
        case('reset', 'Import "Shop", then start again with a fresh browser profile and open the editor.',
             shop + [{'do': 'reset-open'}], [
                 point('fresh', 'A fresh profile has no saved diagram: the editor asks for the database of a new '
                                'diagram.', shown('Choose a database'), requires=['reload/tables'])]),
        case('rename', 'Rename the diagram "Shop" to "Shop renamed" (File, Rename) and reload the page.',
             shop + [{'do': 'dialog-fill', 'menu': ['File', 'Rename'], 'value': 'Shop renamed', 'button': 'Rename'},
                     {'do': 'reload'}], [
                 point('title', 'The new title is saved.', model('title'))]),
        case('save-as', 'Save the diagram "Shop" as a copy named "Duplicate store" (File, Save as).', shop + [copy], [
            point('current', 'The original diagram stays open.', model('title'), requires=['open-copy/title'])]),
        case('open-copy', 'Save "Shop" as "Duplicate store", then open the copy from the list of diagrams.',
             shop + [copy, {'do': 'choose', 'menu': ['File', 'Open'], 'item': 'Duplicate store', 'button': 'Open'}],
             [point('title', 'The opened diagram is the copy.', model('title')),
              point('tables', 'The copy has the tables of the original.', model('tables'))]),
        case('open-original', 'Save "Shop" as "Duplicate store", open the copy, then open "Shop" again.',
             shop + [copy, {'do': 'choose', 'menu': ['File', 'Open'], 'item': 'Duplicate store', 'button': 'Open'},
                     {'do': 'choose', 'menu': ['File', 'Open'], 'item': 'Shop', 'button': 'Open'}], [
                 point('title', 'The original diagram opens again.', model('title'))]),
        case('recent', 'Save "Shop" as "Duplicate store", then open the copy from File, Open Recent.',
             shop + [copy, {'do': 'menu', 'path': ['File', 'Open Recent', 'Duplicate store']}], [
                 point('title', 'Open Recent lists the copy and opens it.', model('title'))]),
        case('delete', 'Delete the diagram "Shop" (File, Delete diagram) and confirm.',
             shop + [{'do': 'confirm-menu', 'menu': ['File', 'Delete diagram']}], [
                 point('empty', 'The editor is left with an empty diagram.', model('counts'), requires=['reload/tables']),
                 point('title', 'The empty diagram is untitled.', model('title')),
                 point('address', 'The editor shows the blank template (/editor/templates/blank).',
                       {'type': 'page', 'path': '/editor/templates/blank'})]),
        case('flush', 'Import "Shop", then choose Flush storage in the Settings menu and confirm.',
             shop + [{'do': 'confirm-menu', 'menu': ['Settings', 'Flush storage']}, {'do': 'wait', 'seconds': 2}], [
                 point('fresh', 'All saved data is removed: the editor asks for the database of a new diagram.',
                       shown('Choose a database'), requires=['reload/tables'])]),
        case('autosave-on', 'Import "Shop", rename the table orders to purchases in the side panel and reload the page.',
             shop + rename_orders + [{'do': 'wait', 'seconds': 2}, {'do': 'reload'}], [
                 point('tables', 'With autosave on (the default) the rename is saved.', model('tables'))]),
        case('autosave-save', 'Import "Shop", switch Autosave off (Settings), rename orders to purchases, press '
                              'Control+S and reload the page.',
             shop + [{'do': 'menu', 'path': ['Settings', 'Autosave']}] + rename_orders +
             [{'do': 'escape'}, {'do': 'press', 'key': 'Control+s'}, {'do': 'wait', 'seconds': 2}, {'do': 'reload'}], [
                 point('tables', 'Saving by hand keeps the rename.', model('tables'))]),
        case('autosave-off', 'Import "Shop", switch Autosave off (Settings), rename orders to purchases and reload the '
                             'page without saving.',
             shop + [{'do': 'menu', 'path': ['Settings', 'Autosave']}] + rename_orders +
             [{'do': 'wait', 'seconds': 2}, {'do': 'reload'}], [
                 point('tables', 'Without autosave the unsaved rename is lost.', model('tables'),
                       requires=['autosave-save/tables'])]),
        case('saved-data', 'Save "Shop" as "Duplicate store", then choose Export saved data in the Settings menu.',
             shop + [copy], [
                 point('archive', 'A zip archive holds every saved diagram as diagrams/<name>.json with its tables.',
                       {'type': 'archive', 'export': ['Settings', 'Export saved data']})]),
    ])]


TEMPLATES = [('blog', 'Blog database schema'), ('hr', 'Human resources schema'), ('shop', 'E-commerce schema'),
             ('library', 'Library schema'), ('bank', 'Bank schema'), ('university', 'University schema')]


def templates():
    cases = []
    for key, title in TEMPLATES:
        cases.append(case(key, f'Create a new diagram from the template "{title}" (File, New).',
                          [fresh('generic'), {'do': 'choose', 'menu': ['File', 'New'], 'item': title,
                                              'button': 'Create'}], [
                              point('tables', f'The new diagram has the tables of "{title}".', model('tables')),
                              point('relationships', f'The new diagram has the relationships of "{title}".',
                                    model('relationships'))]))
    cases.append(case('title', 'Create a new diagram from the template "Library schema".',
                      [fresh('generic'), {'do': 'choose', 'menu': ['File', 'New'], 'item': 'Library schema',
                                          'button': 'Create'}], [
                          point('title', 'The new diagram takes the template\'s title.', model('title')),
                          point('database', 'Diagrams from the default templates are generic.', model('database'))]))
    cases.append(case('blank', 'With "Shop" open, create a new diagram from the blank template.',
                      [fresh('mysql'), load('mysql-shop'), {'do': 'choose', 'menu': ['File', 'New'], 'item': 'Blank',
                                                           'button': 'Create'}], [
                          point('database', 'A blank diagram starts by asking for its database.',
                                shown('Choose a database'), requires=['blog/tables'])]))
    cases.append(case('custom', 'Save "Shop" as a template (File, Save as template), rename the diagram to "Other" '
                                'and open File, New.',
                      [fresh('mysql'), load('mysql-shop'), {'do': 'menu', 'path': ['File', 'Save as template']},
                       {'do': 'dialog-fill', 'menu': ['File', 'Rename'], 'value': 'Other', 'button': 'Rename'},
                       {'do': 'menu', 'path': ['File', 'New']}, {'do': 'wait', 'seconds': 1}], [
                          point('listed', 'The new template is offered beside the default templates.',
                                shown('Shop', 'Blog database schema'))]))
    cases.append(case('custom-use', 'Save "Shop" as a template, then create a new diagram from it.',
                      [fresh('mysql'), load('mysql-shop'), {'do': 'menu', 'path': ['File', 'Save as template']},
                       {'do': 'dialog-fill', 'menu': ['File', 'Rename'], 'value': 'Other', 'button': 'Rename'},
                       {'do': 'choose', 'menu': ['File', 'New'], 'item': 'Shop', 'button': 'Create'}], [
                          point('tables', 'The diagram created from the saved template has its tables.',
                                model('tables')),
                          point('database', 'It keeps the template\'s database.', model('database'))]))
    cases.append(case('page', 'Open the templates page /templates.', [fresh('generic'), {'do': 'open', 'path': '/templates'}],
                      [point('default', 'The page shows the six default templates.',
                             shown(*[title for _, title in TEMPLATES]))]))
    return [episode('templates', 'templates', cases)]


def display():
    shown_texts = ['VARCHAR(30)', 'fk_tasks_owner_id_people', 'what friends say', 'pan x']
    base = [fresh('generic'), load('display')]
    view = lambda item: {'do': 'menu', 'path': ['View', item]}
    return [episode('display', 'view', [
        case('defaults', 'Import the generic diagram "Display".', base, [
            point('shown', 'Column types and relationship names are shown on the canvas; column comments and the '
                           'debug coordinates are not.', shown(*shown_texts))]),
        case('datatypes', 'Switch off Show datatype in the View menu.', base + [view('Show datatype')], [
            point('shown', 'Column types are no longer shown on the canvas.', shown(*shown_texts),
                  requires=['defaults/shown'])]),
        case('labels', 'Switch off Show relationship labels in the View menu.',
             base + [view('Show relationship labels')], [
                 point('shown', 'Relationship names are no longer shown.', shown('fk_tasks_owner_id_people'),
                       requires=['defaults/shown'])]),
        case('comments', 'Switch on Show comments in the View menu.', base + [view('Show comments')], [
            point('shown', 'Column comments are shown under their columns.', shown(*shown_texts))]),
        case('debug', 'Switch on Show debug coordinates in the View menu.', base + [view('Show debug coordinates')], [
            point('shown', 'The debug coordinates panel is shown.', shown(*shown_texts)),
            point('transform', 'It shows pan 0, 0 and scale 1.', {'type': 'transform'})]),
        case('menubar', 'Switch off Menubar in the View menu.', base + [view('Menubar')], [
            point('hidden', 'The menu bar is hidden.', dict(shown('File', 'Edit'), exact=True),
                  requires=['defaults/shown'])]),
        case('sidebar', 'Switch off Sidebar in the View menu.', base + [view('Sidebar')], [
            point('hidden', 'The side panel is hidden.', shown('Add table'), requires=['defaults/shown'])]),
        case('problems', 'Switch off Problems in the View menu.', base + [view('Problems')], [
            point('hidden', 'The problems list is hidden.', shown('Problems', reveal=()), requires=['defaults/shown'])]),
        case('kept', 'Switch off Show datatype and reload the page.', base + [view('Show datatype'), {'do': 'reload'}],
             [point('shown', 'The setting is kept after the reload.', shown(*shown_texts), requires=['defaults/shown'])]),
        case('language', 'Choose the language Deutsch (Settings, Language) and reload the page.',
             base + [{'do': 'choose', 'menu': ['Settings', 'Language'], 'item': 'Deutsch', 'button': 'Confirm'},
                     {'do': 'reload'}], [
                 point('menus', 'The menus are shown in German, also after the reload.',
                       dict(shown('Datei', 'Bearbeiten', 'Ansicht', 'File'), exact=True))]),
    ])]


def view_transform():
    base = [fresh('generic'), load('display'), {'do': 'menu', 'path': ['View', 'Show debug coordinates']},
            {'do': 'away'}]
    t = {'type': 'transform'}
    return [episode('view-transform', 'view', [
        case('zoom-in', 'With the debug coordinates shown, press Control+ArrowUp.', base + [press('Control+ArrowUp')], [
            point('scale', 'The scale grows by a factor of 1.2.', t),
            point('label', 'The zoom field shows 120%.', shown('120', '100'))]),
        case('zoom-out', 'Press Control+ArrowDown twice.', base + [press('Control+ArrowDown'), press('Control+ArrowDown')],
             [point('scale', 'Each press divides the scale by 1.2.', t)]),
        case('pan', 'Press ArrowRight twice and ArrowDown once.',
             base + [press('ArrowRight'), press('ArrowRight'), press('ArrowDown')], [
                 point('pan', 'Each arrow key moves the view by 60 units.', t)]),
        case('pan-zoomed', 'Zoom in once, then press ArrowLeft.', base + [press('Control+ArrowUp'), press('ArrowLeft')],
             [point('pan', 'Panning by keyboard moves 60 screen units, scaled by the zoom.', t)]),
        case('reset', 'Zoom in and pan, then press Enter.',
             base + [press('Control+ArrowUp'), press('ArrowRight'), press('Enter')], [
                 point('reset', 'Enter resets the view to pan 0, 0 and scale 1.', t, requires=['zoom-in/scale'])]),
        case('menu-zoom', 'Choose Zoom in in the View menu twice.',
             base + [{'do': 'menu', 'path': ['View', 'Zoom in']}, {'do': 'menu', 'path': ['View', 'Zoom in']}], [
                 point('scale', 'Each Zoom in multiplies the scale by 1.2.', t)]),
    ])]


def images():
    store = [fresh('generic'), load('image-ledger')]
    export = lambda kind: ['File', 'Export as', kind]
    return [episode('images', 'images', [
        case('png', 'Export the diagram "Ledger" as a PNG image.', store, [
            point('image', 'A PNG image of the diagram is produced.', {'type': 'image', 'export': export('PNG'), 'texts': ['Accounts', 'Entries', 'balance']})]),
        case('jpeg', 'Export the diagram "Ledger" as a JPEG image.', store, [
            point('image', 'A JPEG image of the diagram is produced.', {'type': 'image', 'export': export('JPEG'), 'texts': ['Accounts', 'Entries', 'balance']})]),
        case('svg', 'Export the diagram "Ledger" as an SVG image.', store, [
            point('image', 'An SVG image of the diagram is produced that contains the visible table names.',
                  {'type': 'image', 'export': export('SVG'), 'texts': ['Accounts', 'Entries', 'balance']})]),
        case('pdf', 'Export the diagram "Ledger" as PDF.', store, [
            point('document', 'A one-page PDF with the picture of the diagram is produced.',
                  {'type': 'image', 'export': export('PDF'), 'texts': ['Accounts', 'Entries', 'balance']})]),
        case('copy', 'Press Control+Alt+C (Copy as image).', store + [press('Control+Alt+c'), {'do': 'wait', 'seconds': 2}],
             [point('clipboard', 'The clipboard holds a PNG picture of the diagram.',
                    {'type': 'clipboard', 'image': True, 'texts': ['Accounts', 'Entries', 'balance']})]),
    ])]


def ddb_imports():
    valid = [fresh('generic'), {'do': 'import-ddb', 'file': 'legacy.ddb'}]
    return [episode('ddb-import', 'json-import', [
        case('valid', 'Import the legacy DDB diagram.', valid, [
            point('tables', 'The legacy file creates its tables.', model('tables')),
            point('fields', 'The imported legacy columns keep their definitions.', model('all-fields')),
            point('relationships', 'The legacy relationship connects its columns.', model('relationships')),
            point('title', 'The title in the legacy file is restored.', model('title'))]),
        case('default-database', 'Import a legacy file with no database property into a generic diagram.',
             [fresh('generic'), {'do': 'import-ddb', 'file': 'legacy-default.ddb'}], [
                 point('database', 'The legacy file defaults to the generic database.', model('database')),
                 point('tables', 'The default-database legacy file imports its tables.', model('tables'))]),
        *[case(cid, 'Try to import a refused legacy file into a populated generic diagram.',
               [fresh('generic'), load('generic-store'), {'do': 'import-ddb', 'file': name}], [
                   point('kept', 'The populated diagram is kept after the refused file.', model('all-fields'),
                         requires=['valid/fields'])])
          for cid, name in [('invalid', 'legacy-invalid.ddb'), ('missing', 'legacy-missing.ddb'),
                            ('mismatch', 'legacy-mismatch.ddb')]],
    ])]


def text_boundaries():
    return [episode('text-boundaries', 'formats', [
        case('json', 'Import and export a diagram with quoted names, Unicode and significant whitespace.',
             [fresh('mysql'), load('quoted-names')], [
                 point('title', 'The Unicode diagram title survives the round trip.', model('title')),
                 point('names', 'Spaces and letter case in table names survive.', model('tables')),
                 point('fields', 'Unicode column names, exact default strings and multiline comments survive.',
                       model('all-fields'))]),
        case('sql', 'Import SQL with quoted identifiers, a reserved word column and Unicode string literals.',
             [fresh('mysql'), sql_file('quoted-names.sql')], [
                 point('names', 'The quoted table name is imported without losing its space.', model('tables')),
                 point('fields', 'The quoted column names and significant string whitespace are imported.',
                       model('all-fields'))]),
    ])]


def build():
    return (sql_exports() + sql_imports() + text_exports() + dbml_imports() + json_files() + problems()
            + ddb_imports() + text_boundaries() + edit_actions() + autolinks() + persistence() + templates() + display() + view_transform() + images())
