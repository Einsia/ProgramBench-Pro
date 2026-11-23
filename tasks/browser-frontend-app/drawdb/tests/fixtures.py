"""Hidden test inputs: diagram files in the application's JSON format, SQL scripts and DBML files.

Diagrams are built here and written as the JSON diagram files the application exports and imports. Ids are
deterministic (t:<table>, <table>.<column>), so recorded observations never depend on generated ids.
"""
import json

BLUE = '#175e7a'


def field(name, type_, size='', default='', check='', primary=False, unique=False, not_null=False, increment=False,
          comment='', **extra):
    out = {'name': name, 'type': type_, 'default': default, 'check': check, 'primary': primary, 'unique': unique,
           'notNull': not_null, 'increment': increment, 'comment': comment}
    if size != '':
        out['size'] = size
    out.update(extra)
    return out


def pk(name='id', type_='INT', increment=True, **extra):
    return field(name, type_, primary=True, unique=True, not_null=True, increment=increment, **extra)


def index(name, fields, unique=False):
    return {'name': name, 'unique': unique, 'fields': list(fields)}


def unique(name, fields):
    return {'name': name, 'fields': list(fields)}


def table(name, fields, x=0, y=0, comment='', indices=(), uniques=(), color=BLUE, **extra):
    out = {'id': 't_' + name, 'name': name, 'x': x, 'y': y, 'locked': False,
           'fields': [dict(f, id=name + '.' + f['name']) for f in fields], 'comment': comment,
           'indices': [dict(i, id=n) for n, i in enumerate(indices)],
           'uniqueConstraints': [dict(u, id=n) for n, u in enumerate(uniques)], 'color': color}
    out.update(extra)
    return out


def rel(start, end, name=None, cardinality='many_to_one', update='No action', delete='No action', pairs=None,
        **extra):
    """A relationship from start 'table.column' (the referencing column) to end 'table.column'."""
    st, sf = start.split('.')
    et, ef = end.split('.')
    pairs = pairs or [(start, end)]
    out = {'name': name or f'fk_{st}_{sf}_{et}', 'startTableId': 't_' + st, 'startFieldId': start,
           'endTableId': 't_' + et, 'endFieldId': end, 'cardinality': cardinality, 'updateConstraint': update,
           'deleteConstraint': delete, 'fields': [{'startFieldId': a, 'endFieldId': b} for a, b in pairs]}
    out.update(extra)
    return out


def note(title, content, x=0, y=0, color='#fcf7ac', height=88, **extra):
    return {'title': title, 'content': content, 'x': x, 'y': y, 'color': color, 'height': height, **extra}


def area(name, x, y, width, height, color='#175e7a', **extra):
    return {'name': name, 'x': x, 'y': y, 'width': width, 'height': height, 'color': color, **extra}


def doc(title, database, tables, relationships=(), notes=(), areas=(), views=(), types=None, enums=None):
    out = {'tables': list(tables),
           'relationships': [dict(r, id=n) for n, r in enumerate(relationships)],
           'notes': [dict(x, id=n) for n, x in enumerate(notes)],
           'subjectAreas': [dict(a, id=n) for n, a in enumerate(areas)],
           'views': list(views), 'database': database, 'title': title}
    if types is not None:
        out['types'] = list(types)
    if enums is not None:
        # Enums carry ids as in the application's own files (it edits an enum by its id).
        out['enums'] = [dict(e, id=e.get('id', f'en_{n}')) for n, e in enumerate(enums)]
    return out


def view(name, base, columns=(), joins=(), conditions=(), comment='', materialized=False, x=0, y=0, color=BLUE):
    """A view on `base`: columns are ('table.column', alias), joins (type, table, 'left.column', right column of the
    joined table), conditions (connector, 'table.column', operator, value)."""
    def ref(name_):
        t, f = name_.split('.')
        return 't_' + t, name_
    cols = []
    for n, (column, alias) in enumerate(columns):
        tid, fid = ref(column)
        cols.append({'id': f'{name}.c{n}', 'tableId': tid, 'fieldId': fid, 'alias': alias})
    js = []
    for n, (kind, other, left, right) in enumerate(joins):
        ltid, lfid = ref(left)
        js.append({'id': f'{name}.j{n}', 'type': kind, 'tableId': 't_' + other,
                   'on': {'leftTableId': ltid, 'leftFieldId': lfid, 'rightFieldId': other + '.' + right}})
    cs = []
    for n, (connector, column, operator, value) in enumerate(conditions):
        tid, fid = ref(column)
        cs.append({'id': f'{name}.w{n}', 'connector': connector, 'tableId': tid, 'fieldId': fid,
                   'operator': operator, 'value': value})
    return {'id': 'v_' + name, 'name': name, 'x': x, 'y': y, 'baseTableId': 't_' + base, 'joins': js,
            'columns': cols, 'conditions': cs, 'comment': comment, 'materialized': materialized, 'color': color}


def enum(name, values):
    return {'name': name, 'values': list(values)}


def ctype(name, fields, comment=''):
    """A composite type: fields are (name, type) or (name, type, values)."""
    return {'id': 'ty_' + name, 'name': name, 'comment': comment,
            'fields': [{'id': f'{name}.{f[0]}', 'name': f[0], 'type': f[1], **({'values': list(f[2])} if len(f) > 2
                                                                               else {})} for f in fields]}


# -- diagrams for the SQL exporters --------------------------------------------------------------------------
def mysql_shop():
    return doc('Shop', 'mysql', [
        table('customers', [pk(type_='INTEGER'),
                            field('email', 'VARCHAR', 120, not_null=True, unique=True, comment='login name'),
                            field('vip', 'BOOLEAN', default='false'),
                            field('credit', 'DECIMAL', '10,2', default='0.00', check='credit >= 0')],
              x=40, y=40, comment='people who buy',
              indices=[index('customers_email_idx', ['email'], unique=True)]),
        table('orders', [pk(type_='INTEGER', unsigned=True), field('customer_id', 'INTEGER', not_null=True),
                         field('status', 'ENUM', default='new', values=['new', 'paid', "it's shipped"]),
                         field('placed', 'DATETIME', default='CURRENT_TIMESTAMP')],
              x=380, y=40, indices=[index('orders_status_placed', ['status', 'placed'])]),
    ], [rel('orders.customer_id', 'customers.id', update='Cascade', delete='Restrict')])


def mysql_catalog():
    return doc('Catalog', 'mysql', [
        table('products', [pk(type_='BIGINT', unsigned=True),
                           field('sku', 'CHAR', 8, not_null=True, default="AB'CD"),
                           field('price', 'FLOAT', '7,2', unsigned=True, default='9.5'),
                           field('tags', 'SET', values=['new', 'sale']),
                           field('stock', 'MEDIUMINT', unsigned=True, default='0', check='stock >= 0'),
                           field('released', 'YEAR', default='2024'),
                           field('blurb', 'TEXT', 500, comment="shown on the product's page"),
                           field('specs', 'JSON')],
              x=40, y=300),
        table('tags', [field('product_id', 'BIGINT', primary=True, not_null=True),
                       field('label', 'VARCHAR', 32, primary=True, not_null=True),
                       field('weight', 'TINYINT', unsigned=True, default='1')],
              x=420, y=300, comment="a product's labels",
              uniques=[unique('tags_label_weight', ['label', 'weight'])]),
        table('reviews', [pk(type_='INTEGER'), field('product_id', 'BIGINT'), field('label', 'VARCHAR', 32),
                          field('stars', 'TINYINT', not_null=True, check='stars BETWEEN 1 AND 5')],
              x=760, y=300, indices=[index('reviews_stars', ['stars'])]),
    ], [rel('tags.product_id', 'products.id', update='Set null', delete='Set default'),
        rel('reviews.product_id', 'tags.product_id', name='fk_reviews_tag', update='No action', delete='Cascade',
            pairs=[('reviews.product_id', 'tags.product_id'), ('reviews.label', 'tags.label')])],
        views=[view('cheap_products', 'products', [('products.sku', 'code'), ('products.price', '')],
                    conditions=[('', 'products.price', '<', '10'), ('AND', 'products.sku', 'LIKE', 'A%')],
                    comment='under ten'),
               view('tagged', 'products', [('products.sku', ''), ('tags.label', 'tag')],
                    joins=[('LEFT', 'tags', 'products.id', 'product_id')], materialized=True)])


def mariadb_library():
    return doc('Library', 'mariadb', [
        table('members', [pk(type_='INTEGER', unsigned=True), field('card', 'UUID', not_null=True, unique=True),
                          field('ip', 'INET4'), field('name', 'VARCHAR', 60, not_null=True, comment='full name'),
                          field('joined', 'DATE', default='CURRENT_DATE'),
                          field('fee', 'DECIMAL', '6,2', unsigned=True, default='12.50')],
              x=40, y=40, comment='card holders', indices=[index('members_name', ['name'])]),
        table('loans', [pk(type_='BIGINT'), field('member_id', 'INTEGER', unsigned=True, not_null=True),
                        field('state', 'ENUM', default='open', values=['open', 'late', 'closed']),
                        field('due', 'DATETIME', check="due > '2020-01-01'")],
              x=400, y=40, indices=[index('loans_member_due', ['member_id', 'due'], unique=True)],
              uniques=[unique('loans_member_state', ['member_id', 'state'])]),
    ], [rel('loans.member_id', 'members.id', update='Restrict', delete='Set null')],
        views=[view('late_loans', 'loans', [('loans.id', 'loan'), ('members.name', '')],
                    joins=[('INNER', 'members', 'loans.member_id', 'id')],
                    conditions=[('', 'loans.state', '=', 'late')], comment='overdue')])


def postgres_events():
    return doc('Events', 'postgresql', [
        table('venues', [pk(type_='INTEGER'), field('name', 'VARCHAR', 80, not_null=True, unique=True),
                         field('site', 'POINT'), field('opened', 'TIMESTAMPTZ', default='now()'),
                         field('ref', 'UUID', default='gen_random_uuid()'),
                         field('capacity', 'INTEGER', default='100', check='capacity > 0',
                               comment="seats, it's approximate")],
              x=40, y=40, comment='where things happen'),
        table('events', [pk(type_='BIGINT'), field('venue_id', 'INTEGER', not_null=True),
                         field('mood', 'MOOD', default='happy'), field('tags', 'TEXT', isArray=True),
                         field('price', 'NUMERIC', '8,2', default='0'), field('meta', 'JSONB'),
                         field('place', 'ADDRESS')],
              x=400, y=40, indices=[index('events_venue', ['venue_id']),
                                    index('events_venue_price', ['venue_id', 'price'], unique=True)],
              uniques=[unique('events_venue_mood', ['venue_id', 'mood'])]),
        table('festivals', [field('days', 'SMALLINT', not_null=True, default='1')], x=760, y=40,
              inherits=['events']),
    ], [rel('events.venue_id', 'venues.id', update='Cascade', delete='Set null')],
        views=[view('busy_venues', 'venues', [('venues.name', ''), ('events.price', 'cost')],
                    joins=[('FULL', 'events', 'venues.id', 'venue_id')],
                    conditions=[('', 'events.meta', 'IS NOT NULL', ''), ('OR', 'venues.capacity', '>=', '500')],
                    materialized=True, comment="the venue's busy days"),
               view('all_events', 'events')],
        types=[ctype('address', [('street', 'VARCHAR'), ('zip', 'INTEGER')], comment='postal address')],
        enums=[enum('mood', ['happy', 'sad', "it's ok"])])


def sqlite_notes():
    return doc('Notes', 'sqlite', [
        table('folders', [pk(type_='INTEGER'), field('title', 'VARCHAR', 100, not_null=True, comment='shown name'),
                          field('color', 'TEXT', default='#ffffff'), field('pinned', 'BOOLEAN', default='0')],
              x=40, y=40, comment='groups of notes', indices=[index('folders_title', ['title'], unique=True)]),
        table('pages', [pk(type_='INTEGER'), field('folder_id', 'INTEGER', not_null=True),
                        field('body', 'TEXT', 2000), field('size', 'REAL', check='size >= 0'),
                        field('edited', 'DATETIME', default='CURRENT_TIMESTAMP'), field('data', 'BLOB')],
              x=400, y=40, indices=[index('pages_folder_edited', ['folder_id', 'edited'])],
              uniques=[unique('pages_folder_body', ['folder_id', 'body'])]),
        table('links', [field('from_id', 'INTEGER', primary=True, not_null=True),
                        field('to_id', 'INTEGER', primary=True, not_null=True)], x=760, y=40),
    ], [rel('pages.folder_id', 'folders.id', update='No action', delete='Cascade'),
        rel('links.from_id', 'pages.id', update='Restrict', delete='Set null'),
        rel('links.to_id', 'pages.id', name='fk_links_target', update='Set default', delete='Restrict')],
        views=[view('pinned_pages', 'pages', [('pages.id', ''), ('folders.title', 'folder')],
                    joins=[('INNER', 'folders', 'pages.folder_id', 'id')],
                    conditions=[('', 'folders.pinned', '=', '1')], comment='quick access')])


def mssql_crm():
    return doc('CRM', 'transactsql', [
        table('accounts', [pk(type_='INTEGER'), field('name', 'NVARCHAR', 100, not_null=True, unique=True),
                           field('balance', 'MONEY', default='0', check='balance >= 0'),
                           field('opened', 'DATETIME2', '3', default='GETDATE()'),
                           field('active', 'BIT', default='1'), field('guid', 'UNIQUEIDENTIFIER'),
                           field('note', 'TEXT', comment="owner's remark\nsecond line")],
              x=40, y=40, comment="the company's clients",
              indices=[index('accounts_name_balance', ['name', 'balance'])]),
        table('contacts', [pk(type_='BIGINT'), field('account_id', 'INTEGER', not_null=True),
                           field('email', 'VARCHAR', 200, default="it's@example.org"),
                           field('code', 'CHAR', 4)],
              x=420, y=40, indices=[index('contacts_email', ['email'], unique=True)],
              uniques=[unique('contacts_account_code', ['account_id', 'code'])]),
    ], [rel('contacts.account_id', 'accounts.id', update='Cascade', delete='No action')],
        views=[view('rich_accounts', 'accounts', [('accounts.name', 'client'), ('accounts.balance', '')],
                    conditions=[('', 'accounts.balance', '>', '1000')], comment='top clients')])


def oracle_hr():
    return doc('HR', 'oraclesql', [
        table('departments', [pk(type_='INTEGER'), field('name', 'VARCHAR2', 50, not_null=True, unique=True),
                              field('budget', 'NUMBER', '12,2', default='0', check='budget >= 0'),
                              field('created', 'TIMESTAMP', default='SYSTIMESTAMP')],
              x=40, y=40, comment='company units'),
        table('employees', [pk(type_='INTEGER'), field('dept_id', 'INTEGER'), field('boss_id', 'INTEGER'),
                            field('email', 'NVARCHAR2', 80, default="hr@example.org", comment='work address'),
                            field('photo', 'BLOB'), field('remote', 'BOOLEAN', default='FALSE')],
              x=400, y=40, indices=[index('employees_dept', ['dept_id']),
                                    index('employees_email', ['email'], unique=True)],
              uniques=[unique('employees_dept_email', ['dept_id', 'email'])]),
    ], [rel('employees.dept_id', 'departments.id', update='Cascade', delete='Cascade'),
        rel('employees.boss_id', 'employees.id', name='fk_employees_boss', update='No action', delete='Set null'),
        rel('departments.id', 'employees.id', name='fk_departments_head', update='Restrict', delete='Restrict',
            cardinality='one_to_one')],
        views=[view('dept_staff', 'employees', [('employees.email', ''), ('departments.name', 'dept')],
                    joins=[('RIGHT', 'departments', 'employees.dept_id', 'id')], materialized=True,
                    comment='staff by unit')])


# -- one table per dialect with the remaining column types of its type list -----------------------------------------
def mysql_types():
    return doc('Kinds', 'mysql', [
        table('samples', [pk(type_='INTEGER'), field('tiny', 'TINYINT', default='1', unsigned=True),
                          field('medium', 'MEDIUMINT'), field('flag', 'BIT', 1), field('born', 'YEAR'),
                          field('ratio', 'DOUBLE'), field('stamp', 'TIMESTAMP', default='CURRENT_TIMESTAMP'),
                          field('at', 'TIME'), field('code', 'CHAR', 3, default='abc'), field('raw', 'BINARY', 16),
                          field('packed', 'VARBINARY', 64), field('short', 'TINYTEXT'), field('mid', 'MEDIUMTEXT'),
                          field('long', 'LONGTEXT'), field('tb', 'TINYBLOB'), field('mb', 'MEDIUMBLOB'),
                          field('lb', 'LONGBLOB'), field('perms', 'SET', values=['read', 'write']),
                          field('shape', 'GEOMETRY'), field('route', 'LINESTRING'), field('zone', 'POLYGON')],
              x=40, y=40),
    ])


def mariadb_types():
    return doc('Kinds', 'mariadb', [
        table('hosts', [pk(type_='INTEGER'), field('uid', 'UUID', not_null=True), field('v4', 'INET4'),
                        field('v6', 'INET6'), field('port', 'SMALLINT', default='80', unsigned=True),
                        field('seen', 'DATETIME', default='CURRENT_TIMESTAMP'), field('note', 'TINYTEXT'),
                        field('mask', 'BIT', 8), field('role', 'SET', values=['web', 'db'])],
              x=40, y=40),
    ])


def postgres_types():
    return doc('Kinds', 'postgresql', [
        table('samples', [field('id', 'SERIAL', primary=True, not_null=True, unique=True),
                          field('small', 'SMALLSERIAL'), field('big', 'BIGSERIAL'), field('price', 'MONEY'),
                          field('raw', 'BYTEA'), field('at', 'TIME'), field('at_tz', 'TIMETZ'),
                          field('span', 'INTERVAL'), field('net', 'CIDR'), field('host', 'INET'),
                          field('mac', 'MACADDR'), field('bits', 'BIT', 8), field('vbits', 'VARBIT', 16),
                          field('words', 'TSVECTOR'), field('doc', 'XML'), field('code', 'CHAR', 2, default='xx'),
                          field('ratio', 'DOUBLE PRECISION', default='1.5'), field('day', 'DATE', default='CURRENT_DATE'),
                          field('ok', 'BOOLEAN', default='true'), field('shape', 'POLYGON'), field('ring', 'CIRCLE')],
              x=40, y=40),
    ])


def mssql_types():
    return doc('Kinds', 'transactsql', [
        table('samples', [pk(type_='INTEGER'), field('tiny', 'TINYINT', default='0'), field('cash', 'SMALLMONEY'),
                          field('at', 'DATETIMEOFFSET'), field('old', 'SMALLDATETIME'), field('clock', 'TIME'),
                          field('code', 'NCHAR', 10), field('memo', 'NTEXT'), field('raw', 'VARBINARY', 64),
                          field('pic', 'IMAGE'), field('doc', 'XML'), field('anything', 'SQL_VARIANT'),
                          field('ratio', 'REAL'), field('exact', 'DECIMAL', '9,3', default='0.5'),
                          field('wide', 'FLOAT')],
              x=40, y=40),
    ])


def oracle_types():
    return doc('Kinds', 'oraclesql', [
        table('samples', [pk(type_='INTEGER'), field('amount', 'NUMBER', 5), field('ratio', 'FLOAT'),
                          field('legacy', 'LONG'), field('code', 'NCHAR', 3), field('initials', 'CHAR', 2),
                          field('text', 'CLOB'), field('ntext', 'NCLOB'), field('raw', 'RAW', 16),
                          field('file', 'BFILE'), field('doc', 'JSON'), field('day', 'DATE', default='SYSDATE'),
                          field('span', 'INTERVAL')],
              x=40, y=40),
    ])


def generic_store():
    return doc('Store', 'generic', [
        table('items', [pk(), field('code', 'UUID', not_null=True, unique=True),
                        field('label', 'VARCHAR', 40, not_null=True, comment='display name'),
                        field('kind', 'ENUM', default='box', values=['box', 'bag']),
                        field('flags', 'SET', values=['hot', 'cold']), field('price', 'DECIMAL', '8,3', default='1.5'),
                        field('weight', 'DOUBLE'), field('active', 'BOOLEAN', default='true'),
                        field('added', 'TIMESTAMP', default='CURRENT_TIMESTAMP'), field('seen', 'DATETIME'),
                        field('photo', 'BLOB'), field('extra', 'JSON')],
              x=40, y=40, comment='things for sale', indices=[index('items_label', ['label'])]),
        table('stock', [pk('id', 'SMALLINT'), field('item_id', 'INT', not_null=True),
                        field('count', 'BIGINT', default='0', check='count >= 0'), field('day', 'DATE'),
                        field('opens', 'TIME'), field('hash', 'BINARY', 16), field('blob', 'VARBINARY', 64),
                        field('memo', 'TEXT', 400), field('grade', 'CHAR', 2, default="A'"),
                        field('ratio', 'FLOAT', '5,2'), field('score', 'REAL')],
              x=420, y=40, indices=[index('stock_item_day', ['item_id', 'day'], unique=True)],
              uniques=[unique('stock_item_grade', ['item_id', 'grade'])]),
        table('moves', [pk('id', 'BIGINT'), field('stock_id', 'SMALLINT', not_null=True),
                        field('qty', 'INT', not_null=True), field('note', 'VARCHAR', 100)], x=800, y=40),
    ], [rel('stock.item_id', 'items.id', update='Cascade', delete='Restrict'),
        rel('moves.stock_id', 'stock.id', update='Set null', delete='Cascade')],
        views=[view('cheap_items', 'items', [('items.label', 'name'), ('items.price', '')],
                    conditions=[('', 'items.price', '<=', '2'), ('AND', 'items.kind', 'IN', "('box', 'bag')")],
                    comment='bargains'),
               view('item_moves', 'moves', [('moves.qty', ''), ('items.label', '')],
                    joins=[('INNER', 'stock', 'moves.stock_id', 'id'), ('LEFT', 'items', 'stock.item_id', 'id')])],
        types=[ctype('money', [('amount', 'DECIMAL'), ('currency', 'CHAR')], comment='an amount with currency')])


def generic_typed():
    return doc('Typed', 'generic', [
        table('wallets', [pk(), field('owner', 'VARCHAR', 60, not_null=True),
                          field('balance', 'MONEY', not_null=True), field('limit', 'MONEY')],
              x=40, y=40),
        table('transfers', [pk('id', 'BIGINT'), field('wallet_id', 'INT'), field('kind', 'ENUM', values=['in', 'out']),
                            field('at', 'DATETIME', default='NOW()')],
              x=400, y=40, comment="a wallet's movements"),
    ], [rel('transfers.wallet_id', 'wallets.id', update='No action', delete='Set default', cardinality='one_to_one')],
        types=[ctype('money', [('amount', 'DECIMAL'), ('currency', 'CHAR')], comment=''),
               ctype('point2d', [('x', 'DOUBLE'), ('y', 'DOUBLE')], comment='a position')])


def generic_board():
    return doc('Board', 'generic', [
        table('teams', [pk(), field('name', 'VARCHAR', 50, not_null=True)], x=60, y=80, color='#7d4dc4',
              locked=True),
        table('members', [pk(), field('team_id', 'INT'), field('nick', 'CHAR', 12, unique=True)], x=360, y=80,
              color='#d4282b', hidden=True, comment='players'),
        table('scores', [pk('id', 'BIGINT'), field('member_id', 'INT', not_null=True),
                         field('points', 'SMALLINT', default='0')], x=660, y=80),
    ], [rel('members.team_id', 'teams.id', delete='Cascade'),
        rel('scores.member_id', 'members.id', update='Restrict', cardinality='one_to_one')],
        notes=[note('Todo', 'add a seasons table', x=60, y=400, color='#a2d9f2', height=96),
               note('Rule', "scores can't be negative", x=320, y=420)],
        areas=[area('League', 40, 40, 560, 300, color='#dbd800'), area('Stats', 640, 40, 300, 260)],
        views=[view('rankings', 'scores', [('members.nick', 'player'), ('scores.points', '')],
                    joins=[('INNER', 'members', 'scores.member_id', 'id')],
                    conditions=[('', 'scores.points', '>', '0')], comment='who leads')],
        types=[ctype('rgb', [('r', 'SMALLINT'), ('g', 'SMALLINT'), ('b', 'SMALLINT')], comment='a colour')])


def mismatched():
    d = mysql_shop()
    d['database'] = 'postgresql'
    d['title'] = 'Elsewhere'
    return d


def dangling(field_only):
    d = mysql_shop()
    d['title'] = 'Dangling'
    r = d['relationships'][0]
    if field_only:
        r['endFieldId'] = 'customers.ghost'
        r['fields'] = [{'startFieldId': 'orders.customer_id', 'endFieldId': 'customers.ghost'}]
        r['name'] = 'fk_to_ghost_column'
    else:
        r['endTableId'] = 't_ghosts'
        r['name'] = 'fk_to_ghost_table'
    return d


# -- diagrams with problems (one to three each, so that the problems list shows them all) ---------------------------
def raw_view(name, base, columns=(), joins=(), x=0, y=0):
    return {'id': 'v_' + name + str(x), 'name': name, 'x': x, 'y': y, 'baseTableId': base, 'joins': list(joins),
            'columns': list(columns), 'conditions': [], 'comment': '', 'materialized': False, 'color': BLUE}


def issues(n):
    g, pg = 'generic', 'postgresql'
    ok = [pk(), field('label', 'VARCHAR', 20)]
    if n == 1:
        return doc('Problems 1', g, [table('', ok), table('dup', ok, x=300), dict(table('dup', ok, x=600), id='t_dup2')])
    if n == 2:
        return doc('Problems 2', g, [table('blank_cols', [pk(), field('', 'INT'), field('x', '')])])
    if n == 3:
        return doc('Problems 3', g, [
            table('feelings', [pk(), field('mood', 'ENUM', values=[])]),
            table('stock', [pk(), field('qty', 'INT', default='abc'), field('count', 'INT', default='12'),
                            field('note', 'VARCHAR', 20, not_null=True, default='NULL'),
                            field('memo', 'VARCHAR', 20, default='null')], x=300)])
    if n == 4:
        return doc('Problems 4', g, [
            table('twins', [pk(), field('x', 'INT'), dict(field('x', 'TEXT'), name='x')]),
            table('stock', [pk(), field('a', 'INT'), field('b', 'INT')], x=300,
                  indices=[index('i1', ['a']), index('i1', ['b']), index('', ['a', 'b'])])])
    if n == 5:
        return doc('Problems 5', g, [
            table('idx_empty', [pk(), field('a', 'INT')], indices=[index('idx_none', [])]),
            table('nokey', [field('a', 'INT'), field('b', 'INT')], x=300),
            table('uq_empty', [pk(), field('a', 'INT')], x=600, uniques=[unique('uq_none', [])])])
    if n == 6:
        a = table('a', [pk(), field('b_id', 'INT')])
        b = table('b', [pk(), field('a_id', 'INT')], x=300)
        tree = table('tree', [pk(), field('parent_id', 'INT')], x=600)
        return doc('Problems 6', g, [a, b, tree], [
            rel('a.b_id', 'b.id', name='fk_same'), rel('b.a_id', 'a.id', name='fk_same'),
            rel('tree.parent_id', 'tree.id', name='fk_tree_parent')])
    if n == 7:
        return doc('Problems 7', pg, [table('t', [pk('id', 'INTEGER')])], types=[
            ctype('', [('v', 'INTEGER')]), ctype('pair', [('a', 'INTEGER')]),
            dict(ctype('pair', [('b', 'TEXT')]), id='ty_pair2'), ctype('hollow', [])], enums=[])
    if n == 8:
        return doc('Problems 8', pg, [table('t', [pk('id', 'INTEGER')])], types=[
            ctype('loose', [('', 'INTEGER'), ('w', ''), ('kind', 'ENUM', [])])], enums=[])
    if n == 9:
        return doc('Problems 9', pg, [table('t', [pk('id', 'INTEGER')])],
                   types=[ctype('twin', [('v', 'INTEGER'), ('v', 'TEXT')])],
                   enums=[enum('', ['a']), enum('empty', [])])
    if n == 10:
        return doc('Problems 10', pg, [
            table('base', [pk('id', 'INTEGER'), field('name', 'TEXT')]),
            table('kid', [pk('id', 'INTEGER'), field('toy', 'TEXT')], x=300, inherits=['base'])],
            types=[], enums=[enum('state', ['on', 'off']), enum('state', ['up', 'down'])])
    if n == 11:
        return doc('Problems 11', g, [table('orders', ok)], views=[
            raw_view('', 't_orders'), raw_view('v', 't_orders', x=200), raw_view('v', 't_orders', x=400),
            raw_view('orders', 't_orders', x=600)])
    if n == 12:
        items = table('items', ok)
        return doc('Problems 12', g, [table('orders', [pk(), field('item_id', 'INT')]), dict(items, x=300)], views=[
            raw_view('nobase', None),
            raw_view('j1', 't_orders', joins=[{'id': 'j1', 'type': 'INNER', 'tableId': None, 'on': None}], x=200),
            raw_view('j2', 't_orders', joins=[{'id': 'j2', 'type': 'LEFT', 'tableId': 't_items', 'on': None}], x=400)])
    if n == 13:
        orders = table('orders', [pk(), field('item_id', 'INT')])
        items = table('items', [pk(), field('box_id', 'INT')], x=300)
        boxes = table('boxes', [pk()], x=600)
        return doc('Problems 13', g, [orders, items, boxes], views=[
            raw_view('j3', 't_orders', joins=[
                {'id': 'a', 'type': 'INNER', 'tableId': 't_items',
                 'on': {'leftTableId': 't_boxes', 'leftFieldId': 'boxes.id', 'rightFieldId': 'items.box_id'}},
                {'id': 'b', 'type': 'INNER', 'tableId': 't_boxes',
                 'on': {'leftTableId': 't_orders', 'leftFieldId': 'orders.item_id', 'rightFieldId': 'boxes.id'}}]),
            raw_view('cols', 't_orders', columns=[{'id': 'c0', 'tableId': 't_orders', 'fieldId': None, 'alias': ''}],
                     x=200),
            raw_view('dupcols', 't_orders', columns=[
                {'id': 'c1', 'tableId': 't_orders', 'fieldId': 'orders.id', 'alias': ''},
                {'id': 'c2', 'tableId': 't_items', 'fieldId': 'items.id', 'alias': ''}],
                joins=[{'id': 'c3', 'type': 'INNER', 'tableId': 't_items',
                        'on': {'leftTableId': 't_orders', 'leftFieldId': 'orders.item_id', 'rightFieldId': 'items.id'}}],
                x=400)])
    if n == 0:
        return doc('No problems', g, [table('clean', ok), table('tidy', [pk(), field('clean_id', 'INT')], x=300)],
                   [rel('tidy.clean_id', 'clean.id')])
    raise KeyError(n)


def autolink():
    """Foreign-key-like columns for the automatic connection: plural and singular table names, a primary key that is
    not id, a unique column, and a column that is already connected."""
    return doc('Autolink', 'generic', [
        table('users', [pk(), field('name', 'VARCHAR', 40)]),
        table('posts', [pk(), field('user_id', 'INT'), field('category_id', 'INT', unique=True)], x=300),
        table('categories', [pk(), field('title', 'VARCHAR', 40)], x=600),
        table('boxes', [pk()], y=300),
        table('parcels', [pk(), field('boxid', 'INT'), field('boxes_id', 'INT')], x=300, y=300),
        table('countries', [field('code', 'CHAR', 2, primary=True, not_null=True)], x=600, y=300),
        table('cities', [pk(), field('country_code', 'CHAR', 2), field('code', 'CHAR', 2), field('posts', 'INT')],
              y=600),
        table('likes', [pk(), field('user_id', 'INT'), field('post_id', 'INT')], x=300, y=600),
    ], [rel('likes.user_id', 'users.id', name='fk_likes_user_existing')])



def display():
    return doc('Display', 'generic', [
        table('people', [pk(), field('nickname', 'VARCHAR', 30, comment='what friends say')], x=-380, y=-180),
        table('tasks', [pk(), field('owner_id', 'INT', not_null=True), field('due', 'DATE')], x=60, y=-180),
    ], [rel('tasks.owner_id', 'people.id')])



# -- diagrams for the GUI goals (tables placed where the editor shows them without scrolling) -------------------------
def gui_shop():
    return doc('Shop', 'mysql', [
        table('customers', [pk(type_='INTEGER'), field('email', 'VARCHAR', 120, not_null=True, unique=True),
                            field('vip', 'BOOLEAN', default='false'), field('credit', 'DECIMAL', '10,2')],
              x=-420, y=-360, comment='people who buy'),
        table('orders', [pk(type_='INTEGER'), field('customer_id', 'INTEGER', not_null=True),
                         field('status', 'ENUM', default='new', values=['new', 'paid']),
                         field('placed', 'DATETIME')],
              x=-130, y=-360, indices=[index('orders_status_placed', ['status', 'placed'])]),
        table('products', [pk(type_='INTEGER'), field('name', 'VARCHAR', 80, not_null=True),
                           field('price', 'DECIMAL', '8,2', default='0')], x=160, y=-360),
    ], [rel('orders.customer_id', 'customers.id', update='Cascade', delete='Restrict')])


def gui_blog():
    return doc('Blog', 'generic', [
        table('users', [pk(), field('name', 'VARCHAR', 60, not_null=True)], x=-420, y=-360),
        table('posts', [pk(), field('user_id', 'INT', not_null=True), field('title', 'VARCHAR', 120),
                        field('body', 'TEXT', 2000)], x=-130, y=-360),
        table('tags', [pk(), field('label', 'VARCHAR', 30, unique=True)], x=160, y=-360),
        table('post_tags', [field('post_id', 'INT', primary=True, not_null=True),
                            field('tag_id', 'INT', primary=True, not_null=True)], x=-130, y=-60),
    ], [rel('posts.user_id', 'users.id', delete='Cascade')])


def gui_events():
    return doc('Events', 'postgresql', [
        table('venues', [pk(type_='INTEGER'), field('name', 'VARCHAR', 80, not_null=True)], x=-420, y=-360),
        table('events', [pk(type_='BIGINT'), field('venue_id', 'INTEGER'), field('mood', 'MOOD'),
                         field('price', 'NUMERIC', '8,2')], x=-130, y=-360),
    ], [rel('events.venue_id', 'venues.id')],
        types=[ctype('address', [('street', 'VARCHAR'), ('zip', 'INTEGER')], comment='postal address')],
        enums=[enum('mood', ['happy', 'sad'])])



def gui_blog_areas():
    d = gui_blog()
    d['subjectAreas'] = [dict(area('Core', -440, -390, 230, 260, color='#7d4dc4'), id=0)]
    d['notes'] = [dict(note('Todo', 'add a season table', x=180, y=0, color='#fcf7ac', height=96), id=0)]
    return d


def gui_blog_view():
    d = gui_blog()
    d['views'] = [view('post_list', 'posts', [('posts.id', '')], x=200, y=0)]
    return d


def gui_blog_view2():
    d = gui_blog()
    d['views'] = [view('author_posts', 'posts', [('posts.id', ''), ('posts.title', ''), ('users.name', 'author')],
                       joins=[('INNER', 'users', 'posts.user_id', 'id')], x=200, y=0)]
    return d


def gui_blog_view3():
    d = gui_blog()
    d['views'] = [view('author_posts', 'posts', [('posts.id', ''), ('posts.title', ''), ('users.name', 'author')],
                       joins=[('INNER', 'users', 'posts.user_id', 'id')],
                       conditions=[('', 'posts.id', '>', '10')], x=200, y=0)]
    return d


def gui_nokey():
    """One problem: a table without a primary key."""
    d = gui_blog()
    d['tables'][2]['fields'][0] = dict(field('id', 'INT', not_null=True), id='tags.id')
    return d


def gui_empty_enum():
    """One problem: an enum without values."""
    d = gui_events()
    d['enums'] = [dict(enum('mood', ['happy', 'sad']), id='en_0'), dict(enum('state', []), id='en_1')]
    return d


def gui_pile():
    """Four tables stacked on one spot, for the automatic arrangement."""
    return doc('Pile', 'generic', [
        table('authors', [pk(), field('name', 'VARCHAR', 80)], x=0, y=0),
        table('books', [pk(), field('author_id', 'INT'), field('title', 'VARCHAR', 120)], x=0, y=0),
        table('shelves', [pk(), field('label', 'VARCHAR', 20)], x=0, y=0),
        table('loans', [pk(), field('book_id', 'INT'), field('due', 'DATE')], x=0, y=0),
    ], [rel('books.author_id', 'authors.id'), rel('loans.book_id', 'books.id')])


def gui_library():
    """A generic diagram file offered to the GUI import goal."""
    return doc('Library', 'generic', [
        table('books', [pk(), field('title', 'VARCHAR', 200, not_null=True), field('year', 'SMALLINT')],
              x=-420, y=-360),
        table('members', [pk(), field('name', 'VARCHAR', 80)], x=-130, y=-360),
        table('loans', [pk(), field('book_id', 'INT'), field('member_id', 'INT'), field('due', 'DATE')],
              x=160, y=-360),
    ], [rel('loans.book_id', 'books.id'), rel('loans.member_id', 'members.id')])


def gui_staff():
    return doc('Staff', 'generic', [
        table('staff', [pk(), field('name', 'VARCHAR', 80), field('manager_id', 'INT')], x=-420, y=-360),
        table('teams', [pk(), field('name', 'VARCHAR', 40), field('lead_id', 'INT')], x=-60, y=-360),
    ])


def gui_lines():
    """A relationship over the first column of a two-column key, for the composite key goal."""
    return doc('Lines', 'generic', [
        table('order_lines', [field('order_id', 'INT', primary=True, not_null=True),
                              field('line_no', 'INT', primary=True, not_null=True), field('qty', 'INT')],
              x=-420, y=-360),
        table('shipments', [pk(), field('order_id', 'INT', not_null=True), field('line_no', 'INT', not_null=True),
                            field('sent', 'DATE')], x=-60, y=-360),
    ], [rel('shipments.order_id', 'order_lines.order_id', name='shipment_line')])


def gui_shop_uc():
    d = gui_shop()
    d['tables'][2]['uniqueConstraints'] = [dict(unique('products_name_price', ['name', 'price']), id=0)]
    return d


def gui_blog_states():
    """users locked, posts collapsed, tags hidden."""
    d = gui_blog()
    d['tables'][0]['locked'] = True
    d['tables'][1]['collapsed'] = True
    d['tables'][2]['hidden'] = True
    return d


def gui_dupes():
    """A diagram with one problem: a table with two columns of the same name."""
    d = gui_blog()
    d['tables'][1]['fields'].append(dict(field('title', 'VARCHAR', 80), id='posts.title2'))
    return d


CLIPBOARD = {
    'table': {'id': 'clip', 'name': 'archive', 'x': -150, 'y': 30, 'comment': 'old rows', 'color': '#4d4dff',
              'indices': [], 'fields': [
                  {'id': 'a1', 'name': 'id', 'type': 'BIGINT', 'default': '', 'check': '', 'primary': True,
                   'unique': True, 'notNull': True, 'increment': True, 'comment': ''},
                  {'id': 'a2', 'name': 'payload', 'type': 'TEXT', 'default': '', 'check': '', 'primary': False,
                   'unique': False, 'notNull': False, 'increment': False, 'comment': 'raw data'}]},
    'note': {'id': 7, 'x': -180, 'y': 20, 'title': 'Pasted', 'content': 'from the clipboard', 'color': '#ffdfba',
             'height': 90},
    'area': {'id': 9, 'name': 'Pasted area', 'x': -350, 'y': -150, 'width': 300, 'height': 160, 'color': '#c7f2a4'},
}


DIAGRAMS = {
    'mysql-shop': mysql_shop, 'mysql-catalog': mysql_catalog, 'mariadb-library': mariadb_library,
    'postgres-events': postgres_events, 'sqlite-notes': sqlite_notes, 'mssql-crm': mssql_crm, 'oracle-hr': oracle_hr,
    'mysql-types': mysql_types, 'mariadb-types': mariadb_types, 'postgres-types': postgres_types, 'mssql-types': mssql_types,
    'oracle-types': oracle_types,
    'generic-store': generic_store, 'generic-typed': generic_typed, 'generic-board': generic_board,
    'mismatched': mismatched, 'dangling-table': lambda: dangling(False), 'dangling-column': lambda: dangling(True),
    **{f'issues-{n}': (lambda n=n: issues(n)) for n in range(14)}, 'autolink': autolink, 'display': display,
    'gui-shop': gui_shop, 'gui-blog': gui_blog, 'gui-events': gui_events, 'gui-blog-areas': gui_blog_areas,
    'gui-blog-view': gui_blog_view, 'gui-blog-view2': gui_blog_view2, 'gui-pile': gui_pile, 'gui-dupes': gui_dupes,
    'gui-library': gui_library, 'gui-staff': gui_staff, 'gui-lines': gui_lines, 'gui-shop-uc': gui_shop_uc,
    'gui-blog-states': gui_blog_states, 'gui-blog-view3': gui_blog_view3, 'gui-nokey': gui_nokey,
    'gui-empty-enum': gui_empty_enum,
}

# Each untested type in the pinned version's public type list gets a distinct column rendering.
ADDITIONAL_TYPES = {'mysql': ['BLOB', 'DATE', 'GEOMETRYCOLLECTION', 'MULTILINESTRING', 'MULTIPOINT', 'MULTIPOLYGON', 'NUMERIC', 'POINT', 'SMALLINT'], 'mariadb': ['BINARY', 'BLOB', 'BOOLEAN', 'CHAR', 'DOUBLE', 'FLOAT', 'GEOMETRY', 'GEOMETRYCOLLECTION', 'JSON', 'LINESTRING', 'LONGBLOB', 'LONGTEXT', 'MEDIUMBLOB', 'MEDIUMINT', 'MEDIUMTEXT', 'MULTILINESTRING', 'MULTIPOINT', 'MULTIPOLYGON', 'NUMERIC', 'POINT', 'POLYGON', 'TEXT', 'TIME', 'TIMESTAMP', 'TINYBLOB', 'TINYINT', 'VARBINARY', 'YEAR'], 'postgresql': ['BOX', 'DECIMAL', 'HALFVEC', 'JSON', 'LINE', 'LSEG', 'MACADDR8', 'PATH', 'REAL', 'SPARSEVEC', 'TIMESTAMP', 'TSQUERY', 'VECTOR'], 'sqlite': ['DATE', 'NUMERIC', 'TIME', 'TIMESTAMP'], 'transactsql': ['BINARY', 'CURSOR', 'DATE', 'DATETIME', 'DOUBLE', 'JSON', 'NUMERIC', 'SMALLINT', 'TIMESTAMP'], 'oraclesql': ['VECTOR'], 'generic': ['CLOB', 'NCLOB', 'NUMBER', 'NUMERIC', 'VARCHAR2']}


def coverage_types(database):
    columns = []
    for name in ADDITIONAL_TYPES[database]:
        size = '9,3' if name in ('NUMERIC', 'NUMBER', 'DECIMAL') else 32 if name in ('CHAR', 'VARCHAR2', 'BINARY', 'VARBINARY') else 3 if name in ('VECTOR', 'HALFVEC', 'SPARSEVEC') and database == 'postgresql' else ''
        columns.append(field('kind_' + name.lower(), name, size))
    if database == 'postgresql':
        columns += [field('dense_default', 'VECTOR', 3, default='[1,2,3]'),
                    field('half_array', 'HALFVEC', 4, isArray=True),
                    field('sparse_default', 'SPARSEVEC', 5, default='{1:2,4:3}/5')]
    return doc('Additional types', database, [table('type_choices', columns, x=-200, y=-300)])


DIAGRAMS.update({'coverage-' + db: (lambda db=db: coverage_types(db)) for db in ADDITIONAL_TYPES})

def image_ledger():
    return doc('Ledger', 'generic', [
        table('Accounts', [pk(), field('balance', 'DECIMAL', '9,2')], x=-360, y=-220, width=360),
        table('Entries', [pk(), field('account_id', 'INT'), field('amount', 'DECIMAL', '9,2')], x=100, y=-120, width=360),
    ], [rel('Entries.account_id', 'Accounts.id')])


def image_catalog():
    return doc('Catalog image', 'generic', [
        table('Products', [pk(), field('category_id', 'INT'), field('description', 'VARCHAR', 40)], x=-360, y=-220, width=360),
        table('Categories', [pk(), field('title', 'VARCHAR', 40)], x=100, y=-120, width=360),
        table('Secrets', [pk(), field('password', 'TEXT')], x=60, y=100, hidden=True),
    ], [rel('Products.category_id', 'Categories.id')])


DIAGRAMS.update({'image-ledger': image_ledger, 'image-catalog': image_catalog})

def quoted_names():
    return doc('Case and Unicode — café', 'mysql', [
        table('Order Rows', [field('select', 'INT'),
                             field('DisplayName', 'VARCHAR', 40, default='two  spaces'),
                             field('备注', 'VARCHAR', 40, default='café 数据', comment='first line\nsecond line')],
              x=-200, y=-250, width=360),
    ])


DIAGRAMS['quoted-names'] = quoted_names

# -- SQL scripts for the importers ---------------------------------------------------------------------------
# Written in the syntax each importer accepts (every statement form below is one the reference reads).
MYSQL_LIBRARY = """CREATE TABLE `authors` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL COMMENT 'pen name',
  `email` VARCHAR(255) UNIQUE,
  `born` DATE DEFAULT NULL,
  `rating` DECIMAL(3,1) DEFAULT 5.0,
  `status` ENUM('active','retired') DEFAULT 'active',
  `created` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `bio` TEXT,
  PRIMARY KEY (`id`)
) COMMENT='writers';

CREATE TABLE `books` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `author_id` INT NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `pages` SMALLINT CHECK (pages > 0),
  `isbn` CHAR(13),
  `price` FLOAT(6,2) DEFAULT 9.99,
  CONSTRAINT `books_isbn` UNIQUE (`isbn`),
  FOREIGN KEY (`author_id`) REFERENCES `authors`(`id`) ON DELETE CASCADE ON UPDATE RESTRICT
);

CREATE INDEX `books_title` ON `books` (`title`);
CREATE UNIQUE INDEX `authors_name_email` ON `authors` (`name`, `email`);

CREATE TABLE `reviews` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `book_id` INT UNIQUE,
  `stars` TINYINT DEFAULT 3,
  `body` MEDIUMTEXT,
  `posted` DATETIME DEFAULT NOW(),
  PRIMARY KEY (`id`)
);

ALTER TABLE `reviews` ADD FOREIGN KEY (`book_id`) REFERENCES `books`(`id`) ON DELETE SET NULL;
"""

POSTGRES_SHOP = """CREATE TYPE mood AS ENUM ('happy', 'sad');

CREATE TYPE money_t AS (
  amount NUMERIC(10,2),
  currency CHAR(3)
);

CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  email VARCHAR(120) NOT NULL UNIQUE,
  active BOOLEAN DEFAULT TRUE,
  joined TIMESTAMPTZ DEFAULT now(),
  feeling mood DEFAULT 'happy',
  note TEXT
);

CREATE TABLE orders (
  id BIGINT GENERATED BY DEFAULT AS IDENTITY,
  customer_id INTEGER NOT NULL,
  total NUMERIC(12,2) DEFAULT 0,
  meta JSONB,
  ref UUID DEFAULT gen_random_uuid(),
  PRIMARY KEY (id),
  CONSTRAINT orders_ref UNIQUE (ref),
  CONSTRAINT orders_customer FOREIGN KEY (customer_id) REFERENCES customers (id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX orders_total_idx ON orders (total);
CREATE UNIQUE INDEX customers_email_joined ON customers (email, joined);

COMMENT ON TABLE customers IS 'buyers';
COMMENT ON COLUMN orders.total IS 'sum of the lines';

CREATE TABLE lines (
  order_id BIGINT,
  pos SMALLINT,
  qty INTEGER DEFAULT 1,
  PRIMARY KEY (order_id, pos)
);

ALTER TABLE lines ADD CONSTRAINT lines_order FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE;
"""

SQLITE_TODO = """CREATE TABLE lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  color VARCHAR(7) DEFAULT '#ffffff',
  archived BOOLEAN DEFAULT 0
);

CREATE TABLE items (
  id INTEGER PRIMARY KEY,
  list_id INTEGER NOT NULL,
  text TEXT NOT NULL,
  done BOOLEAN NOT NULL DEFAULT 0,
  due DATETIME,
  weight REAL CHECK (weight >= 0),
  UNIQUE (list_id, text),
  FOREIGN KEY (list_id) REFERENCES lists (id) ON DELETE CASCADE ON UPDATE NO ACTION
);

CREATE TABLE tags (
  item_id INTEGER REFERENCES items (id) ON DELETE SET NULL,
  label TEXT,
  PRIMARY KEY (item_id, label)
);
"""

MSSQL_HELPDESK = """CREATE TABLE [agents] (
  [id] INT IDENTITY(1,1) NOT NULL,
  [name] NVARCHAR(80) NOT NULL,
  [email] VARCHAR(120) UNIQUE,
  [salary] MONEY DEFAULT 0,
  [hired] DATETIME2 DEFAULT GETDATE(),
  [active] BIT DEFAULT 1,
  PRIMARY KEY ([id])
);

CREATE TABLE [tickets] (
  [id] BIGINT IDENTITY(1,1) PRIMARY KEY,
  [agent_id] INT,
  [subject] NVARCHAR(200) NOT NULL,
  [body] NVARCHAR(MAX),
  [priority] TINYINT DEFAULT 2 CHECK ([priority] >= 1),
  [opened] DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT [tickets_subject] UNIQUE ([subject])
);

CREATE INDEX [tickets_opened] ON [tickets] ([opened]);
CREATE UNIQUE INDEX [agents_name_email] ON [agents] ([name], [email]);
"""

ORACLE_SCHOOL = """CREATE TABLE teachers (
  id NUMBER(10) GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  name VARCHAR2(100) NOT NULL,
  email VARCHAR2(200) UNIQUE,
  hired DATE,
  CONSTRAINT teachers_email_name UNIQUE (email, name)
);

CREATE TABLE courses (
  id NUMBER(10) NOT NULL PRIMARY KEY,
  teacher_id NUMBER(10),
  title VARCHAR2(150) NOT NULL,
  credits NUMBER(4,1) DEFAULT 3,
  syllabus CLOB,
  CONSTRAINT courses_teacher_fk FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE
);

CREATE TABLE seats (
  course_id NUMBER(10),
  code CHAR(4) NOT NULL UNIQUE,
  CONSTRAINT seats_course FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE SET NULL
);
"""

MARIADB_SHOPS = """CREATE TABLE `shops` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code` CHAR(36) NOT NULL,
  `name` VARCHAR(60) NOT NULL DEFAULT 'new shop',
  `rating` DOUBLE DEFAULT 0,
  `opened` YEAR,
  PRIMARY KEY (`id`),
  UNIQUE KEY `shops_code` (`code`)
) COMMENT='stores';

CREATE TABLE `staff` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `shop_id` INT UNSIGNED NOT NULL,
  `role` ENUM('clerk','manager') NOT NULL DEFAULT 'clerk',
  `hired` DATE,
  `badge` BIT(8),
  FOREIGN KEY (`shop_id`) REFERENCES `shops` (`id`) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX `staff_role` ON `staff` (`role`, `hired`);
"""

DBML_BLOG = """Project blog {
  database_type: 'PostgreSQL'
  Note: 'A small blog'
}

enum post_state {
  draft
  published [note: 'visible to readers']
  archived
}

Table users [headercolor: #3498db] {
  id integer [pk, increment]
  name varchar(80) [not null, note: 'display name']
  email varchar(255) [unique, not null]
  born date
  created_at timestamp [default: `now()`]
  score decimal(5,2) [default: 0]
  Note: 'people who write'
}

Table posts {
  id bigint [pk, increment]
  author_id integer [not null, ref: > users.id]
  title varchar(200) [not null, default: 'untitled']
  state post_state [default: 'draft']
  body text

  indexes {
    (author_id, title) [unique, name: 'posts_author_title']
    title [name: 'posts_title']
  }
}

Table tags {
  post_id bigint
  label varchar(30)

  indexes {
    (post_id, label) [pk]
  }
}

Ref tags_post: tags.post_id > posts.id [delete: cascade, update: no action]
Ref: users.id - tags.label
"""

DBML_BROKEN = """Table things {
  id integer [pk
  name varchar
}
"""

# Scripts the importers refuse: not SQL a parser of the dialect accepts.
BROKEN_SQL = "CREATE TABLE broken (\n  id INT,\n  name VARCHAR(20)\n  CONSTRAINT\n"

# Inputs of the GUI import goals (their own files, so that the program import checks are not repeated).
DBML_INVENTORY = """Table warehouses {
  id integer [pk, increment]
  city varchar(60) [not null]
}

Table items {
  id integer [pk, increment]
  warehouse_id integer [not null]
  sku varchar(20) [unique]
  qty integer [default: 0]
}

Ref: items.warehouse_id > warehouses.id
"""

MYSQL_CLINIC = """CREATE TABLE `doctors` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(80) NOT NULL,
  `room` SMALLINT,
  PRIMARY KEY (`id`)
);

CREATE TABLE `visits` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `doctor_id` INT NOT NULL,
  `patient` VARCHAR(80) NOT NULL,
  `at` DATETIME,
  FOREIGN KEY (`doctor_id`) REFERENCES `doctors`(`id`)
);
"""

POSTGRES_TICKETS = """CREATE TABLE queues (
  id SERIAL PRIMARY KEY,
  title VARCHAR(40) NOT NULL
);

CREATE TABLE tickets (
  id BIGSERIAL PRIMARY KEY,
  queue_id INTEGER NOT NULL,
  subject TEXT,
  opened TIMESTAMP DEFAULT now(),
  FOREIGN KEY (queue_id) REFERENCES queues (id)
);
"""

SQLITE_PANTRY = """CREATE TABLE shelves (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL
);

CREATE TABLE jars (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shelf_id INTEGER NOT NULL,
  content TEXT,
  filled DATE,
  FOREIGN KEY (shelf_id) REFERENCES shelves (id)
);
"""

TEXTS = {
    **{f'clip-{k}.json': json.dumps(v) for k, v in CLIPBOARD.items()},
    'library.sql': MYSQL_LIBRARY, 'shop-pg.sql': POSTGRES_SHOP, 'todo.sql': SQLITE_TODO,
    'helpdesk.sql': MSSQL_HELPDESK, 'school.sql': ORACLE_SCHOOL, 'shops-maria.sql': MARIADB_SHOPS,
    'broken.sql': BROKEN_SQL, 'blog.dbml': DBML_BLOG, 'broken.dbml': DBML_BROKEN,
    'inventory.dbml': DBML_INVENTORY, 'clinic.sql': MYSQL_CLINIC, 'tickets.sql': POSTGRES_TICKETS,
    'unfinished.sql': 'CREATE TABLE notes (\n  id INT,\n  body TEXT\n',
    'unclosed.dbml': 'Table shelves {\n  id integer [pk\n  label varchar\n',
    'pantry.sql': SQLITE_PANTRY,
    'quoted-names.sql': "CREATE TABLE `Order Rows` (`select` INT, `DisplayName` VARCHAR(40) DEFAULT 'two  spaces', `备注` VARCHAR(40) DEFAULT 'café 数据');",
    'legacy.ddb': json.dumps(dict(generic_board(), author='A local author', project='Offline schema', title='Legacy board')),
    'legacy-default.ddb': json.dumps({k: v for k, v in dict(generic_board(), title='Legacy generic').items() if k != 'database'}),
    'legacy-invalid.ddb': json.dumps({'tables': 'invalid', 'relationships': [], 'notes': [], 'subjectAreas': []}),
    'legacy-missing.ddb': json.dumps({'title': 'Incomplete legacy file'}),
    'legacy-mismatch.ddb': json.dumps(mysql_shop()),
    'not-json.json': '{"tables": [ {"name": "a",\n',
    'no-tables.json': json.dumps({'title': 'Hollow', 'database': 'mysql', 'relationships': [], 'notes': []}, indent=2),
}


def diagram(key):
    return DIAGRAMS[key]()


def text_file(name):
    return TEXTS[name]


def input_bytes(name):
    """An input file offered to the evaluator of a GUI episode."""
    stem = name.rsplit('.', 1)[0]
    if name.endswith('.json') and stem in DIAGRAMS:
        return json.dumps(diagram(stem), indent=2).encode()
    return TEXTS[name].encode()
