"""GUI episodes: reviewed user goals with acceptance conditions, prepared diagrams, reference recipes and independent
program companions.

Each checkpoint starts in a fresh browser profile on the editor with its diagram imported (prep); the evaluator then
pursues the goal with the editor's own controls. Program companions read the resulting diagram from its JSON export
(or the file, clipboard or page the goal produced) and check only the state the goal changes. Recipes (record only)
drive the pinned standard through the same runtime operations; the control names and positions they use belong to the
standard, never to a candidate. A point that only verifies a refusal or an unchanged state names a positive point of
its episode in `requires`.
"""
SESSION = ('Each checkpoint starts with a fresh editor showing the diagram the goal describes, imported from a '
           'diagram file; tables, columns and other items are named in the goals. Use the editor\'s visible '
           'controls: the side panel, the canvas, menus, the toolbar, dialogs, the pointer and the keyboard. Input '
           'files the goals name are listed under "inputs" and are supplied with the upload operation when a file '
           'chooser is open.')
EQUIVALENTS = ['Any visible route to the same result is valid: side panel form, canvas, menu, toolbar button, '
               'context control, keyboard shortcut or dialog.',
               'Different labels, icons, layouts and dialog designs are valid.']
BYPASSES = ['Do not import a prepared diagram, SQL or DBML file unless the goal asks for that import.',
            'Do not recreate a missing command by other means.']
INITIAL = ('Fresh editor in a fresh browser profile; the checkpoint\'s diagram is imported before the goal starts.')
GUI_BUDGET_FLOORS = {
    'gui-tables': {'calls': 300, 'tokens': 6_000_000},
    'gui-postgresql': {'calls': 180, 'tokens': 2_400_000},
    'gui-dbml': {'calls': 180, 'tokens': 2_800_000},
}


# -- preparation, companions ------------------------------------------------------------------------------------
def fresh(db):
    return {'do': 'fresh', 'db': db}


def load(key):
    return {'do': 'import-json', 'fixture': key}


def start(db, fixture, *extra):
    return [fresh(db), load(fixture), *extra]


def model(part, **extra):
    return {'type': 'model', 'part': part, **extra}


def field_of(table, name, *aspects):
    spec = {'type': 'model', 'part': 'field', 'table': table, 'name': name}
    if aspects:
        spec['aspects'] = list(aspects)
    return spec


def table_of(name, *aspects):
    return {'type': 'model', 'part': 'table', 'name': name, 'aspects': list(aspects)}


def be(name, requirement, check, requires=(), tol=None):
    check = dict(check)
    if tol is not None:
        check['tol'] = tol
    return {'name': name, 'requirement': requirement, 'check': check, 'requires': list(requires)}


def cp(cid, goal, acceptance, prep, recipe, checks=(), requires=()):
    return {'id': cid, 'goal': goal, 'acceptance': acceptance, 'prep': list(prep), 'recipe': list(recipe),
            'checks': list(checks), 'requires': list(requires)}


def episode(key, feature, checkpoints, files=(), hint=''):
    out = []
    for c in checkpoints:
        acceptance = c['acceptance'] if isinstance(c['acceptance'], list) else [c['acceptance']]
        assertions = []
        for n, text in enumerate(acceptance):
            a = {'id': f'{key}/{c["id"]}/visible' + (f'-{n + 1}' if n else ''), 'channel': 'frontend',
                 'method': 'agent', 'requirement': text}
            if c['requires']:
                a['requires'] = [f'{key}/{r}' for r in c['requires']]
            assertions.append(a)
        for b in c['checks']:
            a = {'id': f'{key}/{c["id"]}/{b["name"]}', 'channel': 'backend', 'method': 'program',
                 'requirement': b['requirement'], 'check': b['check']}
            if b['requires']:
                a['requires'] = [f'{key}/{r}' for r in b['requires']]
            assertions.append(a)
        out.append({'id': c['id'], 'goal': c['goal'], 'prep': c['prep'], 'recipe': c['recipe'],
                    'assertions': assertions, 'depends_on': ['setup:editor']})
    n = len(out)
    budget = {'calls': 30 + 30 * n, 'tokens': 400_000 + 500_000 * n, 'seconds': 300 + 600 * n}
    for resource, minimum in GUI_BUDGET_FLOORS.get(key, {}).items():
        budget[resource] = max(budget[resource], minimum)
    return {'id': key, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL,
            'setup': [{'id': 'editor'}], 'inputs': {'files': list(files)},
            'session': SESSION + (' ' + hint if hint else ''),
            'allowed_equivalents': EQUIVALENTS, 'forbidden_bypasses': BYPASSES,
            'budget': budget,
            'checkpoints': out}


# -- recipe helpers (standard only) ------------------------------------------------------------------------------
def click(label, **extra):
    return {'do': 'click', 'label': label, **extra}


def text(value, **extra):
    return {'do': 'click-text', 'text': value, **extra}


def fill(current, value, **extra):
    return {'do': 'fill', 'current': current, 'value': value, **extra}


def fill_ph(placeholder, value, **extra):
    return {'do': 'fill', 'placeholder': placeholder, 'value': value, **extra}


def row(field, **extra):
    return {'do': 'row', 'field': field, **extra}


def option(value, filter=False):
    return {'do': 'option', 'text': value, 'filter': filter}


def pick(value):
    """Choose a type in a type list (typed to filter the long list first)."""
    return option(value, filter=True)


def press(key):
    return {'do': 'press', 'key': key}


def menu(*path, leave=True):
    return {'do': 'menu', 'path': list(path), 'leave': leave}


def wait(seconds=1):
    return {'do': 'wait', 'seconds': seconds}


def open_table(name):
    return text(name)


SHOP = ('mysql', 'gui-shop')
BLOG = ('generic', 'gui-blog')
BLOG_AREAS = ('generic', 'gui-blog-areas')
BLOG_VIEW = ('generic', 'gui-blog-view')
EVENTS = ('postgresql', 'gui-events')


# -- tables -----------------------------------------------------------------------------------------------------
def tables():
    return episode('gui-tables', 'tables', [
        cp('add', 'Add a new table to the diagram and name it "comments".',
           'A table named comments is shown on the canvas and in the list of tables.', start(*BLOG),
           [click('Add table'), {'do': 'fill-prefix', 'prefix': 'table_', 'value': 'comments'}],
           [be('tables', 'The diagram has a new table comments after its tables.', model('tables'))]),
        cp('rename', 'Rename the table "tags" to "labels".',
           'The table formerly named tags is shown as labels on the canvas and in the list.', start(*BLOG),
           [open_table('tags'), fill('tags', 'labels')],
           [be('tables', 'The table tags is renamed to labels.', model('tables'))]),
        cp('delete', 'Delete the table "post_tags".', 'The table post_tags is no longer shown.', start(*BLOG),
           [open_table('post_tags'), {'do': 'row-of', 'anchor': 'Add column', 'unnamed': 0}],
           [be('tables', 'The table post_tags is removed.', model('tables'))]),
        cp('comment', 'Give the table "posts" the comment "articles written by users".',
           'The table posts shows the comment "articles written by users".', start(*BLOG),
           [open_table('posts'), {'do': 'click-title', 'title': 'Add'}, option('Add comment'),
            fill_ph('Comment', 'articles written by users')],
           [be('comment', 'The table posts has the comment.', table_of('posts', 'comment'))]),
        cp('hide', 'Hide the table "tags" from the canvas (it stays in the diagram).',
           'The table tags is no longer drawn on the canvas but is still listed.', start(*BLOG),
           [{'do': 'row-of', 'anchor': 'tags', 'unnamed': 0}],
           [be('hidden', 'The table tags is marked hidden and keeps its columns.',
               table_of('tags', 'flags', 'fields'))]),
        cp('unhide', 'The table "tags" is hidden from the canvas; show it again.', 'The table tags is drawn on the canvas.',
           start(*STATES), [{'do': 'row-of', 'anchor': 'tags', 'unnamed': 0}],
           [be('shown', 'tags is no longer hidden.', table_of('tags', 'flags'), requires=['hide/hidden'])]),
    ])


def moved(name, start, kind='table'):
    return {'type': 'model', 'part': 'moved', 'name': name, 'from': list(start), 'kind': kind}


# Viewport positions of the GUI diagrams' tables (standard layout at zoom 1, pan 0): header centre and row centres.
def at(x, y):
    return {'x': x, 'y': y}


def tables2():
    return episode('gui-tables-2', 'tables', [
        cp('lock', 'Lock the table "users" so that it cannot be moved.',
           'The table users is shown as locked.', start(*BLOG),
           [{'do': 'pointer', 'action': 'move', 'x': 470, 'y': 160}, {'do': 'click-title', 'title': 'Lock table'}],
           [be('locked', 'The table users is locked.', table_of('users', 'flags'))]),
        cp('move', 'Drag the table "tags" down by about 250 pixels.',
           'The table tags is shown lower on the canvas than before.', start(*BLOG),
           [{'do': 'drag', 'x': 1040, 'y': 160, 'to_x': 1040, 'to_y': 410}],
           [be('moved', 'The table tags moved down and not sideways.', moved('tags', (160, -360)))]),
        cp('duplicate', 'Duplicate the table "users" with the table\'s own actions on the canvas.',
           'A copy of the table users, named users_copy, appears on the canvas.', start(*BLOG),
           [{'do': 'pointer', 'action': 'move', 'x': 470, 'y': 160}, {'do': 'click-title', 'title': 'See more'},
            click('Duplicate')],
           [be('tables', 'A copy of users is added.', model('tables')),
            be('copy', 'The copy, named users_copy, has the columns of users.',
               model('table', name='users_copy', aspects=['fields']))]),
        cp('collapse', 'Collapse the unlinked columns of the table "posts" on the canvas.',
           'The table posts shows only its columns that take part in relationships.', start(*BLOG),
           [{'do': 'pointer', 'action': 'move', 'x': 760, 'y': 160},
            {'do': 'click-title', 'title': 'Collapse unlinked columns'}],
           [be('collapsed', 'The table posts is collapsed and keeps its columns.', table_of('posts', 'collapsed',
                                                                                              'field_names'))]),
        cp('search', 'Use the search box of the tables list to find the table "post_tags".',
           'The search result post_tags is offered or the table post_tags is selected and shown.', start(*BLOG),
           [{'do': 'click', 'label': 'Search...'}, {'do': 'type', 'value': 'post_t'}, option('post_tags')],
           [be('unchanged', 'Searching changes nothing in the diagram.', model('tables'),
               requires=['duplicate/tables'])]),
        cp('unlock', 'Unlock the table "users".', 'The table users is no longer shown as locked.', start(*STATES),
           [{'do': 'pointer', 'action': 'move', 'x': 470, 'y': 160}, {'do': 'click-title', 'title': 'Unlock table'}],
           [be('unlocked', 'users is unlocked.', table_of('users', 'flags'), requires=['lock/locked'])]),
        cp('expand', 'The table "posts" shows only its linked columns; show all of its columns again.',
           'The table posts shows its columns id, user_id, title and body.', start(*STATES),
           [{'do': 'pointer', 'action': 'move', 'x': 760, 'y': 160},
            {'do': 'click-title', 'title': 'Expand unlinked columns'}],
           [be('expanded', 'posts is expanded.', table_of('posts', 'collapsed'), requires=['collapse/collapsed'])]),
    ])


def fields1():
    return episode('gui-fields-1', 'columns', [
        cp('add', 'Add a column named "phone" with the type VARCHAR to the table "customers".',
           'The table customers shows a column phone of type VARCHAR.', start(*SHOP),
           [open_table('customers'), click('Add column'), fill('', 'phone'), row('phone', role='combobox'),
            pick('VARCHAR')],
           [be('column', 'customers has a column phone of type VARCHAR.', field_of('customers', 'phone', 'name',
                                                                                    'type'))]),
        cp('type', 'Change the type of the column "placed" of "orders" to DATE.',
           'The column placed of orders is shown with the type DATE.', start(*SHOP),
           [open_table('orders'), row('placed', role='combobox'), pick('DATE')],
           [be('type', 'placed has the type DATE.', field_of('orders', 'placed', 'type'))]),
        cp('not-null', 'Make the column "vip" of "customers" required (NOT NULL).',
           'The column vip of customers is shown as not nullable.', start(*SHOP),
           [open_table('customers'), row('vip', title='Nullable')],
           [be('not-null', 'vip is NOT NULL.', field_of('customers', 'vip', 'notNull'))]),
        cp('primary', 'Add the column "customer_id" of "orders" to the primary key of orders.',
           'The column customer_id of orders is shown as part of the primary key.', start(*SHOP),
           [open_table('orders'), row('customer_id', title='Primary')],
           [be('primary', 'customer_id is a key column.', field_of('orders', 'customer_id', 'primary'))]),
        cp('delete', 'Delete the column "vip" of the table "customers".',
           'The table customers no longer shows the column vip.', start(*SHOP),
           [open_table('customers'), row('vip'), click('Delete')],
           [be('columns', 'customers keeps its other columns in order.', table_of('customers', 'field_names'))]),
    ])


def fields2():
    return episode('gui-fields-2', 'columns', [
        cp('default', 'Set the default value of the column "price" of "products" to 9.99.',
           'The column price of products has the default value 9.99.', start(*SHOP),
           [open_table('products'), row('price'), fill('0', '9.99')],
           [be('default', 'price defaults to 9.99.', field_of('products', 'price', 'default'))]),
        cp('size', 'Change the size of the column "email" of "customers" to 200.',
           'The column email of customers is shown as VARCHAR(200).', start(*SHOP),
           [open_table('customers'), row('email'), fill('120', '200')],
           [be('size', 'email has the size 200.', field_of('customers', 'email', 'type', 'size'))]),
        cp('unique', 'Make the column "name" of "products" unique.',
           'The column name of products is marked unique.', start(*SHOP),
           [open_table('products'), row('name'), {'do': 'toggle', 'index': 0}],
           [be('unique', 'name is unique.', field_of('products', 'name', 'unique'))]),
        cp('increment', 'Turn off auto increment for the column "id" of "products".',
           'The column id of products is no longer auto-incremented.', start(*SHOP),
           [open_table('products'), row('id'), {'do': 'toggle', 'index': 1}],
           [be('increment', 'id is not auto-incremented.', field_of('products', 'id', 'increment'), requires=['unique/unique'])]),
        cp('check', 'Add the check expression "credit >= 0" to the column "credit" of "customers".',
           'The column credit of customers has the check credit >= 0.', start(*SHOP),
           [open_table('customers'), row('credit'), fill_ph('Check expression', 'credit >= 0')],
           [be('check', 'credit has the check.', field_of('customers', 'credit', 'check'))]),
    ])


def fields3():
    return episode('gui-fields-3', 'columns', [
        cp('comment', 'Give the column "status" of "orders" the comment "where the order is".',
           'The column status of orders has the comment "where the order is".', start(*SHOP),
           [open_table('orders'), row('status'), fill_ph('Comment', 'where the order is')],
           [be('comment', 'status has the comment.', field_of('orders', 'status', 'comment'))]),
        cp('unsigned', 'Make the column "customer_id" of "orders" unsigned.',
           'The column customer_id of orders is marked unsigned.', start(*SHOP),
           [open_table('orders'), row('customer_id'), {'do': 'toggle', 'index': 2}],
           [be('unsigned', 'customer_id is unsigned.', field_of('orders', 'customer_id', 'unsigned'))]),
        cp('enum', 'Add the value "shipped" to the allowed values of the column "status" of "orders".',
           'The values of status are new, paid and shipped.', start(*SHOP),
           [open_table('orders'), row('status'), {'do': 'fill-aria', 'aria': 'input value', 'value': 'shipped',
                                                   'commit': 'Enter'}],
           [be('values', 'status allows new, paid and shipped.', field_of('orders', 'status', 'values'))]),
        cp('reorder', 'Move the column "email" of "customers" so that it comes first, before "id".',
           'The table customers lists email as its first column.', start(*SHOP),
           [open_table('customers'), {'do': 'drag-handle', 'field': 'email', 'to_field': 'id'}],
           [be('order', 'email is the first column of customers.', table_of('customers', 'field_names'))]),
        cp('rename', 'Rename the column "placed" of "orders" to "ordered_at".',
           'The table orders shows a column ordered_at instead of placed.', start(*SHOP),
           [open_table('orders'), fill('placed', 'ordered_at')],
           [be('columns', 'placed is renamed to ordered_at.', table_of('orders', 'field_names'))]),
    ])


# Where the reference keeps the table-level items (indices and unique constraints are easy to miss).
INDEX_HINT = ('In the reference, a table\'s form in the side panel (opened from the Tables list) ends with a button '
              'with a plus sign, tooltip "Add", whose menu adds an index, a unique constraint or a comment; the Indices '
              'and Unique constraints sections of a table fold open when their titles are clicked, and the "..." '
              'button in the row of an index or a constraint opens its details (name, unique check box, Delete). In the '
              'column selector of an index or a constraint, the small cross on a column\'s tag removes that column; '
              'open the selector beside its tags to add one.')


def indexes():
    return episode('gui-indexes', 'indices', [
        cp('add', 'Add an index on the column "email" to the table "customers".',
           'The table customers has an index on email.', start(*SHOP),
           [open_table('customers'), {'do': 'click-title', 'title': 'Add'}, option('Add index'),
            {'do': 'select-in', 'placeholder': 'Select columns', 'option': 'email'}],
           [be('indices', 'customers has one index on email.', table_of('customers', 'indices'))]),
        cp('unique', 'Make the index "orders_status_placed" of "orders" unique.',
           'The index orders_status_placed is shown as unique.', start(*SHOP),
           [open_table('orders'), text('Indices'), {'do': 'row-of', 'anchor': 'status placed', 'unnamed': 0},
            {'do': 'toggle', 'index': 0}],
           [be('indices', 'The index is unique.', table_of('orders', 'indices'))]),
        cp('rename', 'Rename the index "orders_status_placed" to "orders_state_time".',
           'The index of orders is shown as orders_state_time.', start(*SHOP),
           [open_table('orders'), text('Indices'), {'do': 'row-of', 'anchor': 'status placed', 'unnamed': 0},
            fill('orders_status_placed', 'orders_state_time')],
           [be('indices', 'The index is renamed.', table_of('orders', 'indices'))]),
        cp('delete', 'Delete the index "orders_status_placed".', 'The table orders no longer has that index.',
           start(*SHOP),
           [open_table('orders'), text('Indices'), {'do': 'row-of', 'anchor': 'status placed', 'unnamed': 0},
            click('Delete')],
           [be('indices', 'orders has no index.', table_of('orders', 'indices'), requires=['add/indices'])]),
        cp('unique-constraint', 'Add a unique constraint over the columns "name" and "price" of "products".',
           'products has a unique constraint on name and price.', start(*SHOP),
           [open_table('products'), {'do': 'click-title', 'title': 'Add'}, option('Add unique constraint'),
            {'do': 'select-in', 'placeholder': 'Select columns', 'option': 'name'},
            {'do': 'select-in', 'placeholder': 'Select columns', 'option': 'price', 'again': True}],
           [be('uniques', 'products has the unique constraint.', table_of('products', 'uniques'))]),
    ], hint=INDEX_HINT)


def relationships1():
    return episode('gui-relationships-1', 'relationships', [
        cp('create', 'Connect the column "tag_id" of "post_tags" to the column "id" of "tags" (a new relationship).',
           'A relationship line connects post_tags.tag_id with tags.id.', start(*BLOG),
           [{'do': 'drag', 'x': 713, 'y': 541, 'to_x': 1100, 'to_y': 199, 'steps': 20}],
           [be('relationships', 'A relationship from post_tags.tag_id to tags.id exists.', model('relationships'))]),
        cp('cardinality', 'Change the cardinality of the relationship between posts and users to one to one.',
           'The relationship between posts and users is shown as one to one.', start(*BLOG),
           [text('Relationships (1)'), text('fk_posts_user_id_users'), {'do': 'select-value', 'value': 'Many to one', 'option': 'One to one'}],
           [be('cardinality', 'The relationship is one to one.',
               model('relationship', name='fk_posts_user_id_users', aspects=['cardinality']))]),
        cp('on-delete', 'Set the ON DELETE action of the relationship between posts and users to Set null.',
           'The relationship shows Set null as its delete action.', start(*BLOG),
           [text('Relationships (1)'), text('fk_posts_user_id_users'), {'do': 'select-value', 'value': 'Cascade', 'option': 'Set null'}],
           [be('delete', 'ON DELETE is Set null.',
               model('relationship', name='fk_posts_user_id_users', aspects=['delete', 'update']))]),
        cp('on-update', 'Set the ON UPDATE action of the relationship between posts and users to Cascade.',
           'The relationship shows Cascade as its update action.', start(*BLOG),
           [text('Relationships (1)'), text('fk_posts_user_id_users'), {'do': 'select-value', 'value': 'No action', 'option': 'Cascade'}],
           [be('update', 'ON UPDATE is Cascade.',
               model('relationship', name='fk_posts_user_id_users', aspects=['delete', 'update']))]),
        cp('rename', 'Rename the relationship between posts and users to "post_author".',
           'The relationship is listed as post_author.', start(*BLOG),
           [text('Relationships (1)'), text('fk_posts_user_id_users'),
            fill('fk_posts_user_id_users', 'post_author')],
           [be('relationships', 'The relationship is named post_author.', model('relationships'))]),
    ])


def relationships2():
    return episode('gui-relationships-2', 'relationships', [
        cp('swap', 'Swap the direction of the relationship between posts and users.',
           'The relationship now goes from users to posts.', start(*BLOG),
           [text('Relationships (1)'), text('fk_posts_user_id_users'), {'do': 'click-title', 'title': 'Swap'}],
           [be('relationships', 'The relationship starts at users.id and ends at posts.user_id.',
               model('relationships'))]),
        cp('delete', 'Delete the relationship between posts and users.', 'No relationship line is shown any more.',
           start(*BLOG),
           [text('Relationships (1)'), text('fk_posts_user_id_users'), {'do': 'click-title', 'title': 'Delete'}],
           [be('relationships', 'The diagram has no relationship.', model('relationships'), requires=['swap/relationships'])]),
        cp('incompatible', 'Try to connect the column "title" of "posts" (VARCHAR) to the column "id" of "users" '
                           '(INT).', 'The editor refuses: no new relationship appears and it says the columns have '
                                     'different types.', start(*BLOG),
           [{'do': 'drag', 'x': 713, 'y': 273, 'to_x': 500, 'to_y': 199, 'steps': 20}, {'do': 'expect',
                                                                                         'text': 'different types'}],
           [be('unchanged', 'No relationship is added.', model('relationships'), requires=['create-unique/relationship'])]),
        cp('create-unique', 'Connect the column "label" of "tags" to the column "title" of "posts".',
           'A relationship line connects tags.label with posts.title.', start(*BLOG),
           [{'do': 'drag', 'x': 1003, 'y': 236, 'to_x': 740, 'to_y': 273, 'steps': 20}],
           [be('relationship', 'A relationship from tags.label to posts.title exists, one to one because label is '
                               'unique.', model('relationships'))]),
    ])


TOOL = {'table': 816, 'view': 858, 'area': 900, 'note': 942}  # toolbar buttons (standard layout), y 860


def tool(kind):
    return {'do': 'pointer', 'x': TOOL[kind], 'y': 860}


def tab(name):
    """Open a tab of the side panel (scrolling the tab strip as needed)."""
    return {'do': 'tab', 'name': name}


def areas():
    return episode('gui-areas', 'areas', [
        cp('add', 'Add a subject area named "Sales".',
           'A subject area labelled Sales is shown on the canvas.', start(*BLOG),
           [tool('area'), tab('Subject areas'), fill('area_0', 'Sales')],
           [be('areas', 'The diagram has an area Sales.', model('areas'))]),
        cp('rename', 'Rename the subject area "Core" to "Main".', 'The subject area is labelled Main.',
           start(*BLOG_AREAS), [tab('Subject areas'), fill('Core', 'Main')],
           [be('areas', 'The area is renamed.', model('areas'))]),
        cp('delete', 'Delete the subject area "Core".', 'The subject area Core is no longer shown.',
           start(*BLOG_AREAS), [tab('Subject areas'), row('Core', unnamed=-1)],
           [be('areas', 'The area is removed.', model('areas'), requires=['add/areas'])]),
        cp('resize', 'Make the subject area "Core" wider by dragging its right edge about 150 pixels to the right.',
           'The subject area Core is wider than before.', start(*BLOG_AREAS),
           [{'do': 'pointer', 'action': 'move', 'x': 500, 'y': 320},
            {'do': 'drag', 'x': 618, 'y': 358, 'to_x': 768, 'to_y': 358}],
           [be('size', 'The area is wider and keeps its height.', model('area-size', name='Core', size=[230, 260]))]),
        cp('move', 'Move the subject area "Core" down by about 150 pixels.', 'The subject area Core is lower than before.',
           start(*BLOG_AREAS), [{'do': 'drag', 'x': 500, 'y': 320, 'to_x': 500, 'to_y': 470}],
           [be('moved', 'The area moved down.', moved('Core', (-440, -390), kind='area'))]),
        cp('lock', 'Lock the subject area "Core".', 'The subject area Core is shown as locked.', start(*BLOG_AREAS),
           [{'do': 'pointer', 'action': 'move', 'x': 500, 'y': 330}, {'do': 'pointer', 'x': 571, 'y': 121}],
           [be('locked', 'The area is locked.', model('areas', aspects=['name', 'locked']))]),
    ])


def notes():
    return episode('gui-notes', 'notes', [
        cp('add', 'Add a note titled "Reminder" with the content "check the indexes".',
           'A note titled Reminder with the text "check the indexes" is shown on the canvas.', start(*BLOG),
           [tool('note'), tab('Notes'), text('note_0'), fill('note_0', 'Reminder'),
            fill_ph('Content', 'check the indexes')],
           [be('notes', 'The diagram has the note.', model('notes', aspects=['title', 'content']))]),
        cp('content', 'Change the content of the note "Todo" to "add a seasons table and an index".',
           'The note Todo shows the new text.', start(*BLOG_AREAS),
           [tab('Notes'), text('Todo'), fill('add a season table', 'add a seasons table and an index')],
           [be('notes', 'The note has the new content.', model('notes', aspects=['title', 'content']))]),
        cp('rename', 'Rename the note "Todo" to "Plans".', 'The note is titled Plans.', start(*BLOG_AREAS),
           [tab('Notes'), text('Todo'), fill('Todo', 'Plans')],
           [be('notes', 'The note is renamed.', model('notes', aspects=['title', 'content']))]),
        cp('delete', 'Delete the note "Todo".', 'The note Todo is no longer shown.', start(*BLOG_AREAS),
           [tab('Notes'), text('Todo'), {'do': 'nearest', 'field': 'add a season table'}],
           [be('notes', 'The note is removed.', model('notes', aspects=['title']), requires=['add/notes'])]),
        cp('move', 'Move the note "Todo" to the right by about 200 pixels.', 'The note Todo is further right than '
                                                                              'before.', start(*BLOG_AREAS),
           [{'do': 'drag', 'x': 1030, 'y': 497, 'to_x': 1230, 'to_y': 497}],
           [be('moved', 'The note moved right.', moved('Todo', (180, 0), kind='note'))]),
        cp('lock', 'Lock the note "Todo".', 'The note Todo is shown as locked.', start(*BLOG_AREAS),
           [{'do': 'pointer', 'action': 'move', 'x': 1100, 'y': 520}, {'do': 'pointer', 'x': 1139, 'y': 509}],
           [be('locked', 'The note is locked.', model('notes', aspects=['title', 'locked']))]),
    ])


def views():
    return episode('gui-views', 'views', [
        cp('add', 'Add a view named "recent_posts" based on the table "posts".',
           'A view recent_posts based on posts is shown.', start(*BLOG),
           [tool('view'), tab('Views'), {'do': 'fill-prefix', 'prefix': 'view_', 'value': 'recent_posts'},
            {'do': 'select-in', 'placeholder': 'Select a table', 'option': 'posts', 'keep': True}],
           [be('views', 'The diagram has the view with its base table.', model('view', name='recent_posts',
                                                                                aspects=['name', 'base']))]),
        cp('column', 'Add the column "title" of "posts" to the output of the view "post_list", with the alias '
                     '"headline".', 'The view post_list outputs headline.', start(*BLOG_VIEW),
           [tab('Views'), text('post_list'), {'do': 'click-title', 'title': 'Add column'},
            {'do': 'select-in', 'placeholder': 'Column', 'option': 'posts.title', 'keep': True},
            fill_ph('Alias', 'headline', nth=1)],
           [be('columns', 'The view outputs posts.title as headline.',
               model('view', name='post_list', aspects=['columns']))]),
        cp('join', 'Join the table "users" into the view "post_list" (posts.user_id = users.id).',
           'The view post_list joins users.', start(*BLOG_VIEW),
           [tab('Views'), text('post_list'), {'do': 'click-title', 'title': 'Add join'},
            {'do': 'select-in', 'placeholder': 'Select a table', 'option': 'users', 'keep': True}],
           [be('joins', 'The view joins users on posts.user_id = users.id.',
               model('view', name='post_list', aspects=['joins']))]),
        cp('condition', 'Add the condition "posts.user_id = 1" to the view "post_list".',
           'The view post_list has the condition on user_id.', start(*BLOG_VIEW),
           [tab('Views'), text('post_list'), {'do': 'click-title', 'title': 'Add condition'},
            {'do': 'select-in', 'placeholder': 'Column', 'option': 'posts.user_id', 'keep': True},
            fill_ph('Value', '1')],
           [be('conditions', 'The view filters on posts.user_id = 1.',
               model('view', name='post_list', aspects=['conditions']))]),
        cp('materialized', 'Make the view "post_list" materialized and give it the comment "for the front page".',
           'The view post_list is marked materialized and shows the comment.', start(*BLOG_VIEW),
           [tab('Views'), text('post_list'), text('Materialized'), click('Add comment'),
            fill_ph('Comment', 'for the front page')],
           [be('flags', 'The view is materialized with the comment.',
               model('view', name='post_list', aspects=['materialized', 'comment']))]),
    ])


def types():
    return episode('gui-types', 'types', [
        cp('add', 'Add a type named "point2d" with two columns "x" and "y" of type DOUBLE.',
           'A type point2d with the columns x and y is listed.', start(*BLOG),
           [tab('Types'), click('Add type'), {'do': 'fill-prefix', 'prefix': 'type_', 'value': 'point2d'},
            click('Add column'), fill('', 'x'), row('x', role='combobox'), pick('DOUBLE'),
            click('Add column'), fill('', 'y'), row('y', role='combobox'), pick('DOUBLE')],
           [be('types', 'The diagram has the type with its two columns.', model('types'))]),
        cp('field', 'Add a column "country" of type VARCHAR to the type "address".',
           'The type address lists the column country.', start(*EVENTS),
           [tab('Types'), text('address'), click('Add column'), fill('', 'country'), row('country', role='combobox'),
            pick('VARCHAR')],
           [be('types', 'address has the new column.', model('types'))]),
        cp('comment', 'Change the comment of the type "address" to "where to send letters".',
           'The type address shows the new comment.', start(*EVENTS),
           [tab('Types'), text('address'), text('Comment'), fill('postal address', 'where to send letters')],
           [be('types', 'address has the new comment.', model('types'))]),
        cp('delete', 'Delete the type "address".', 'The type address is no longer listed.', start(*EVENTS),
           [tab('Types'), text('address'), click('Delete', nth=-1)],
           [be('types', 'The diagram has no type.', model('types'), requires=['add/types'])]),
        cp('use', 'Change the type of the column "name" of "venues" to the type ADDRESS.',
           'The column name of venues has the type ADDRESS.', start(*EVENTS),
           [open_table('venues'), row('name', role='combobox'), pick('ADDRESS')],
           [be('type', 'name has the type ADDRESS.', field_of('venues', 'name', 'type'))]),
    ])


def enums():
    return episode('gui-enums', 'enums', [
        cp('add', 'Add an enum named "priority" with the values "low" and "high".',
           'An enum priority with the values low and high is listed.', start(*EVENTS),
           [tab('Enums'), click('Add enum'), {'do': 'fill-prefix', 'prefix': 'enum_', 'value': 'priority'},
            {'do': 'fill-aria', 'aria': 'input value', 'value': 'low', 'commit': 'Enter'},
            {'do': 'fill-aria', 'aria': 'input value', 'value': 'high', 'commit': 'Enter'}],
           [be('enums', 'The diagram has the enum with its values.', model('enums'))]),
        cp('value', 'Add the value "angry" to the enum "mood".', 'The enum mood lists happy, sad and angry.',
           start(*EVENTS), [tab('Enums'), text('mood'),
                            {'do': 'fill-aria', 'aria': 'input value', 'value': 'angry', 'commit': 'Enter'}],
           [be('enums', 'mood has the three values.', model('enums'))]),
        cp('rename', 'Rename the enum "mood" to "feeling".', 'The enum is listed as feeling.', start(*EVENTS),
           [tab('Enums'), text('mood'), fill('mood', 'feeling')],
           [be('enums', 'The enum is renamed.', model('enums')),
            be('column', 'The column that used the enum follows the new name.', field_of('events', 'mood', 'type'))]),
        cp('delete', 'Delete the enum "mood".', 'The enum mood is no longer listed.', start(*EVENTS),
           [tab('Enums'), text('mood'), click('Delete', nth=-1)],
           [be('enums', 'The diagram has no enum.', model('enums'), requires=['add/enums'])]),
        cp('use', 'Change the type of the column "price" of "events" to the enum MOOD.',
           'The column price of events has the type MOOD.', start(*EVENTS),
           [open_table('events'), row('price', role='combobox'), pick('MOOD')],
           [be('type', 'price has the type MOOD.', field_of('events', 'price', 'type'))]),
    ])


# -- colours ------------------------------------------------------------------------------------------------------
def colors():
    return episode('gui-colors', 'colors', [
        cp('table', 'Set the colour of the table "users" to #ff9159.',
           'The table users is drawn in an orange colour instead of its former dark teal.', start(*BLOG),
           [open_table('users'), {'do': 'pointer', 'x': 40, 'y': 372}, {'do': 'hex', 'value': '#ff9159'}],
           [be('color', 'users has the colour #ff9159.', table_of('users', 'color'))]),
        cp('note', 'Set the colour of the note "Todo" to #a2d2ff.', 'The note Todo is shown in a light blue colour.',
           start(*BLOG_AREAS),
           [tab('Notes'), text('Todo'), {'do': 'swatch', 'field': 'add a season table', 'dx': 25, 'dy': 16},
            {'do': 'hex', 'value': '#a2d2ff'}],
           [be('color', 'The note has the colour #a2d2ff.', model('notes', aspects=['title', 'color']))]),
        cp('area', 'Set the colour of the subject area "Core" to #7aa95c.',
           'The subject area Core is shown in a green colour.', start(*BLOG_AREAS),
           [tab('Subject areas'), {'do': 'swatch', 'field': 'Core'}, {'do': 'hex', 'value': '#7aa95c'}],
           [be('color', 'The area has the colour #7aa95c.', model('areas', aspects=['name', 'color']))]),
        cp('view', 'Set the colour of the view "post_list" to #ffd166.', 'The view post_list is drawn in a yellow colour.',
           start(*BLOG_VIEW),
           [tab('Views'), text('post_list'), {'do': 'pointer', 'x': 40, 'y': 583}, {'do': 'hex', 'value': '#ffd166'}],
           [be('color', 'The view has the colour #ffd166.', model('view', name='post_list', aspects=['color']))]),
    ])


# -- undo, redo, history ---------------------------------------------------------------------------------------
def history():
    return episode('gui-history', 'history', [
        cp('undo-rename', 'Rename the table "tags" to "labels", then rename it again to "topics", and then undo the last '
                          'rename.', 'The table is shown as labels.', start(*BLOG),
           [open_table('tags'), fill('tags', 'labels'), fill('labels', 'topics'), menu('Edit', 'Undo')],
           [be('tables', 'The table is named labels.', model('tables'))]),
        cp('redo', 'Delete the table "post_tags", undo the deletion, and then redo it.',
           'The table post_tags is not shown any more.', start(*BLOG),
           [open_table('post_tags'), {'do': 'row-of', 'anchor': 'Add column', 'unnamed': 0}, menu('Edit', 'Undo'),
            menu('Edit', 'Redo')],
           [be('tables', 'post_tags is deleted again.', model('tables'))]),
        cp('undo-move', 'Drag the table "tags" down by about 250 pixels, then drag it to the right by about 150 pixels, '
                        'and then undo the last move.',
           'The table tags is lower than at the start but not further to the right.', start(*BLOG),
           [{'do': 'drag', 'x': 1040, 'y': 160, 'to_x': 1040, 'to_y': 410},
            {'do': 'drag', 'x': 1040, 'y': 410, 'to_x': 1190, 'to_y': 410}, menu('Edit', 'Undo')],
           [be('moved', 'tags moved down only.', moved('tags', (160, -360)))]),
        cp('undo-columns', 'Delete the column "title" of the table "posts", then delete its column "body", and then undo '
                           'once.', 'The table posts shows the columns id, user_id and body.', start(*BLOG),
           [open_table('posts'), row('title'), click('Delete'), row('body'), click('Delete'), menu('Edit', 'Undo')],
           [be('columns', 'posts has id, user_id and body.', table_of('posts', 'field_names'))]),
        cp('timeline', 'Rename the table "tags" to "labels", then show the timeline of the changes made in the editor.',
           'A list of the changes made in the editor is shown, including the rename of the table (now labels).',
           start(*BLOG),
           [open_table('tags'), fill('tags', 'labels'), menu('Settings', 'Show timeline')],
           [be('tables', 'The table is renamed.', model('tables'))]),
    ])


# -- clipboard and duplicates ----------------------------------------------------------------------------------
def clip_table(*aspects):
    return {'type': 'clipboard', 'json': 'table', 'aspects': list(aspects)}


def clipboard():
    paste = [{'do': 'pointer', 'x': 800, 'y': 700}, press('Control+v')]
    return episode('gui-clipboard', 'clipboard', [
        cp('copy-paste', 'Copy the table "tags" and paste it into the diagram.',
           'A second table with the columns of tags appears.', start(*BLOG),
           [{'do': 'pointer', 'x': 1100, 'y': 160}, press('Control+c'), press('Control+v')],
           [be('tables', 'The pasted copy is added after the tables.', model('tables')),
            be('copy', 'The copy has the columns of tags.', {'type': 'model', 'part': 'last-table',
                                                              'aspects': ['fields']}),
            be('clipboard', 'The clipboard holds the table tags with its columns.', clip_table('name', 'fields'))]),
        cp('cut', 'Cut the table "tags" out of the diagram.', 'The table tags is no longer shown.', start(*BLOG),
           [{'do': 'pointer', 'x': 1100, 'y': 160}, press('Control+x')],
           [be('tables', 'tags is removed.', model('tables')),
            be('clipboard', 'The clipboard holds tags with its columns.', clip_table('name', 'fields'))]),
        cp('paste-table', 'The clipboard holds a table copied from the editor (a table "archive"); paste it into the '
                          'diagram.', 'A table archive with the columns id and payload appears.',
           start(*BLOG, {'do': 'clipboard', 'file': 'clip-table.json'}), paste,
           [be('table', 'The pasted table archive keeps its columns and comment.',
               model('table', name='archive', aspects=['fields', 'comment']))]),
        cp('paste-note', 'The clipboard holds a note copied from the editor (a note "Pasted"); paste it into the '
                         'diagram.', 'A note Pasted with the text "from the clipboard" appears.',
           start(*BLOG, {'do': 'clipboard', 'file': 'clip-note.json'}), paste,
           [be('notes', 'The pasted note keeps its title and content.', model('notes', aspects=['title', 'content']))]),
        cp('duplicate-note', 'Duplicate the note "Todo".', 'A second note Todo with the same text appears.',
           start(*BLOG_AREAS), [{'do': 'pointer', 'x': 1080, 'y': 500}, press('Control+d')],
           [be('notes', 'The diagram has two notes Todo with the same content.',
               model('notes', aspects=['title', 'content']))]),
        cp('duplicate-area', 'Duplicate the subject area "Core".', 'A second subject area Core appears.',
           start(*BLOG_AREAS), [{'do': 'pointer', 'x': 500, 'y': 330}, press('Control+d')],
           [be('areas', 'The diagram has two areas Core.', model('areas'))]),
    ])


# -- automatic layout, automatic relationships, clearing ---------------------------------------------------------
def arrange():
    return episode('gui-arrange', 'layout', [
        cp('auto-arrange', 'Let the editor arrange the tables automatically.',
           'The tables are spread out so that no table lies on top of another.', start('generic', 'gui-pile'),
           [menu('Edit', 'Auto arrange')],
           [be('spread', 'Every table gets a position of its own.', model('spread'))]),
        cp('auto-connect', 'Let the editor create the relationships that the columns named <table>_id imply, '
                           'automatically.', 'New relationship lines connect the *_id columns to their tables.',
           start('generic', 'autolink'), [menu('Edit', 'Auto-connect foreign keys'), click('Auto-connect foreign keys', nth=-1)],
           [be('relationships', 'The implied relationships are added.', model('relationships'))]),
        cp('clear', 'Clear the whole diagram at once.', 'The canvas and the lists are empty.', start(*BLOG_AREAS),
           [menu('Edit', 'Clear', leave=False), click('Confirm')],
           [be('counts', 'Nothing is left in the diagram.', model('counts'), requires=['snap/snapped'])]),
        cp('snap', 'Turn on snapping to the grid, then drag the table "tags" down by about 100 pixels.',
           'The table tags is lower than before and lines up with the grid.', start(*BLOG),
           [menu('View', 'Snap to grid'), {'do': 'drag', 'x': 1040, 'y': 160, 'to_x': 1040, 'to_y': 262}],
           [be('snapped', 'tags moved down to a position on the 24 pixel grid.', model('snapped', name='tags',
                                                                                        start=[160, -360]))]),
        cp('multi-move', 'Select the tables "users" and "posts" together and drag them down by about 200 pixels in one '
                         'move.', 'Both tables users and posts are lower than before; tags stays in place.',
           start(*BLOG),
           [{'do': 'pointer', 'x': 470, 'y': 160}, {'do': 'pointer', 'x': 760, 'y': 160, 'modifiers': ['Control']},
            {'do': 'drag', 'x': 760, 'y': 160, 'to_x': 760, 'to_y': 360}],
           [be('users', 'users moved down.', moved('users', (-420, -360))),
            be('posts', 'posts moved down.', moved('posts', (-130, -360))),
            be('tags', 'tags did not move.', moved('tags', (160, -360)), requires=['multi-move/users'])]),
    ])


# -- panels and display settings (what the editor shows; checked by the evaluator) -------------------------------------
def panels():
    return episode('gui-panels', 'layout', [
        cp('menubar', 'Hide the menu bar of the editor.', 'The menu bar (File, Edit, View ...) is no longer shown; the '
                                                         'canvas stays.', start(*BLOG), [menu('View', 'Menubar')]),
        cp('sidebar', 'Hide the side panel.', 'The side panel with the tables list is no longer shown; the canvas '
                                              'takes its place.', start(*BLOG), [menu('View', 'Sidebar')]),
        cp('problems', 'Hide the problems panel.', 'The panel listing problems is no longer shown.', start(*BLOG),
           [menu('View', 'Problems')]),
        cp('sidebar-back', 'The side panel is hidden; show it again.', 'The side panel with the tables list is shown.',
           start(*BLOG, {'do': 'menu', 'path': ['View', 'Sidebar']}), [menu('View', 'Sidebar')]),
        cp('dbml', 'Show the diagram as DBML code.', 'DBML code that defines the tables users, posts, tags and post_tags '
                                                     'is shown.', start(*BLOG), [menu('View', 'DBML view')]),
        cp('presentation', 'Switch the editor to presentation mode.',
           'Only the canvas with the diagram is shown, without the menu bar, the side panel and the toolbar.',
           start(*BLOG), [menu('View', 'Presentation mode'), wait(1)]),
    ])


def display1():
    return episode('gui-display-1', 'display', [
        cp('datatypes', 'Hide the data types of the columns on the canvas.',
           'The tables on the canvas show their column names without types such as VARCHAR(60).', start(*BLOG),
           [menu('View', 'Show datatype')]),
        cp('comments', 'Show the comments of the tables on the canvas.',
           'The table customers shows its comment "people who buy" on the canvas.', start(*SHOP),
           [menu('View', 'Show comments')]),
        cp('cardinality', 'Hide the cardinality markers of the relationships.',
           'The relationship line between users and posts no longer shows its 1 and n markers.', start(*BLOG),
           [menu('View', 'Show cardinality')]),
        cp('labels', 'Hide the names of the relationships on the canvas.',
           'The name of the relationship between users and posts is no longer shown beside its line.', start(*BLOG),
           [menu('View', 'Show relationship labels')]),
    ])


def display2():
    return episode('gui-display-2', 'display', [
        cp('grid', 'Hide the grid of the canvas.', 'The canvas background no longer shows the dotted grid.',
           start(*BLOG), [menu('View', 'Show grid')]),
        cp('debug', 'Show the debug coordinates of the canvas.', 'The canvas shows the pan and zoom (scale) values.',
           start(*BLOG), [menu('View', 'Show debug coordinates')]),
        cp('theme', 'Switch the editor to the dark theme.', 'The editor is shown with a dark background.', start(*BLOG),
           [menu('View', 'Theme', 'Dark')]),
        cp('column-details', 'On the canvas, show the details of the column "title" of the table "posts" by pointing '
                             'at it.', 'A pop-up shows the details of posts.title, including its type VARCHAR(120).',
           start(*BLOG), [{'do': 'pointer', 'action': 'move', 'x': 740, 'y': 280},
                          {'do': 'pointer', 'action': 'move', 'x': 745, 'y': 273}, wait(1.5)]),
        cp('details-disabled', 'Disable automatic column-detail pop-ups, then show the display setting.',
           'The Column details display setting is shown as off.', start(*BLOG),
           [menu('View', 'Column details'), menu('View', leave=False)]),
    ])


# -- zoom and pan (read from the debug coordinates the checkpoint shows) ---------------------------------------
def shift(*aspects):
    return {'type': 'transform-change', 'from': [0, 0, 1], 'aspects': list(aspects)}


def zoom():
    debug = {'do': 'menu', 'path': ['View', 'Show debug coordinates']}
    return episode('gui-zoom', 'navigation', [
        cp('in', 'Zoom in on the canvas.', 'The diagram is shown larger than before.', start(*BLOG, debug),
           [menu('View', 'Zoom in')], [be('zoom', 'The scale is above 1.', shift('zoom'))]),
        cp('out', 'Zoom out of the canvas.', 'The diagram is shown smaller than before.', start(*BLOG, debug),
           [menu('View', 'Zoom out')], [be('zoom', 'The scale is below 1.', shift('zoom'))]),
        cp('preset', 'Set the zoom level to 50%.', 'The diagram is shown at half its size and the zoom shows 50%.',
           start(*BLOG, debug), [{'do': 'pointer', 'x': 610, 'y': 860}, option('50 %')],
           [be('scale', 'The scale is 0.5.', {'type': 'transform'}, tol=0.01)]),
        cp('reset', 'Reset the view to its default position and zoom.', 'The diagram is shown at 100% in its initial '
                                                                         'position.',
           start(*BLOG, debug, {'do': 'menu', 'path': ['View', 'Zoom in']},
                 {'do': 'menu', 'path': ['View', 'Zoom in']}), [menu('View', 'Reset view')],
           [be('view', 'Pan 0, 0 and scale 1.', {'type': 'transform'}, tol=0.01)]),
        cp('custom', 'Set the zoom level to exactly 175%.', 'The diagram is shown at 175% and the zoom shows 175%.',
           start(*BLOG, debug), [{'do': 'pointer', 'x': 610, 'y': 860},
                                  {'do': 'fill-placeholder-type', 'placeholder': 'Zoom', 'value': '175', 'commit': 'Enter'}],
           [be('scale', 'The scale is 1.75.', {'type': 'transform'}, tol=0.01)]),
        cp('fit', 'Fit the whole diagram into the window.', 'All four tables are fully visible on the canvas.',
           start(*BLOG, {'do': 'menu', 'path': ['View', 'Sidebar']}, *[{'do': 'menu', 'path': ['View', 'Zoom in']}] * 5),
           [{'do': 'pointer', 'x': 700, 'y': 500}, press('Control+Alt+w')],
           [be('on-screen', 'The four table names are shown on the screen.',
               {'type': 'shown', 'texts': ['users', 'posts', 'tags', 'post_tags'], 'exact': True})]),
        cp('pan', 'Move the view so that the diagram appears about 200 pixels further to the right.',
           'The diagram is shown further to the right than before, at the same size.', start(*BLOG, debug),
           [{'do': 'drag', 'x': 600, 'y': 700, 'to_x': 800, 'to_y': 700, 'button': 'right'}],
           [be('pan', 'The view moved horizontally only, at scale 1.', shift('pan', 'zoom'))]),
    ])


# -- DBML code view --------------------------------------------------------------------------------------------
def dbml_editor():
    def code(word, value):
        """Type in the DBML editor at the end of the line holding the word."""
        return {'do': 'code-line', 'word': word, 'value': value}
    return episode('gui-dbml', 'dbml', [
        cp('add-column', 'In the DBML code of the diagram, add a column "slug" of type varchar to the table "tags".',
           'The table tags shows a new column slug.', start(*BLOG),
           [menu('View', 'DBML view'), code('label', '\nslug varchar'), wait(1.5)],
           [be('column', 'tags has a column slug of type VARCHAR.', field_of('tags', 'slug', 'name', 'type'))]),
        cp('add-table', 'In the DBML code of the diagram, add a table "comments" with a column "id" of type int, '
                        'then show the new table on the canvas.',
           'A table comments with the column id appears on the canvas.', start(*BLOG),
           [menu('View', 'DBML view'), {'do': 'code-end', 'value': '\nTable comments {\nid int'}, wait(1.5),
            menu('View', 'DBML view'), {'do': 'pointer', 'x': 700, 'y': 500}, press('Control+Alt+w'), wait(1)],
           [be('tables', 'The diagram has the new table.', model('tables')),
            be('column', 'comments has the column id of type INT.', field_of('comments', 'id', 'name', 'type'))]),
        cp('rename', 'In the DBML code of the diagram, rename the table "tags" to "labels".',
           'The table formerly named tags is shown as labels.', start(*BLOG),
           [menu('View', 'DBML view'), {'do': 'code-word', 'word': 'tags', 'value': 'labels'}, wait(1.5)],
           [be('tables', 'tags is renamed to labels.', model('tables'))]),
        cp('ref', 'In the DBML code of the diagram, add a reference from post_tags.tag_id to tags.id.',
           'A relationship line connects post_tags.tag_id with tags.id.', start(*BLOG),
           [menu('View', 'DBML view'), {'do': 'code-end', 'value': '\nRef: post_tags.tag_id > tags.id'}, wait(1.5)],
           [be('relationships', 'The relationship is added.', model('relationships'))]),
    ])


# -- import dialogs --------------------------------------------------------------------------------------------
def imports():
    def upload(name):
        return {'do': 'upload', 'file': name}
    return episode('gui-import', 'import', [
        cp('json', 'Import the diagram file gui-library.json into the editor.',
           'The editor shows the tables books, members and loans of the imported diagram.', start(*BLOG),
           [menu('File', 'Import from', 'JSON'), upload('gui-library.json'), {'do': 'confirm', 'label': 'Import'}],
           [be('tables', 'The imported diagram replaces the tables.', model('tables')),
            be('title', 'The editor takes the title of the imported diagram.', model('title'))]),
        cp('dbml', 'Import the DBML file inventory.dbml into the editor.',
           'The tables warehouses and items of inventory.dbml are shown, connected by a relationship.',
           [fresh('generic')], [menu('File', 'Import from', 'DBML'), upload('inventory.dbml'),
                                {'do': 'confirm', 'label': 'Import'}],
           [be('tables', 'The tables of inventory.dbml are imported.', model('tables')),
            be('items', 'items has the columns of the file.', table_of('items', 'field_names')),
            be('relationships', 'The reference becomes a relationship.', model('relationships'))]),
        cp('sql', 'Import the MySQL script clinic.sql into this MySQL diagram.',
           'The tables doctors and visits are shown, connected by a relationship.', [fresh('mysql')],
           [menu('File', 'Import from SQL'), {'do': 'upload-tab'}, upload('clinic.sql'),
            {'do': 'confirm', 'label': 'Import'}],
           [be('tables', 'The tables of clinic.sql are imported.', model('tables')),
            be('visits', 'visits has the columns of the script.', table_of('visits', 'field_names')),
            be('relationships', 'The foreign key becomes a relationship.', model('relationships'))]),
        cp('sql-generic', 'Import the PostgreSQL script tickets.sql into this generic diagram.',
           'The tables queues and tickets are shown.', [fresh('generic')],
           [menu('File', 'Import from SQL', 'PostgreSQL'), {'do': 'upload-tab'}, upload('tickets.sql'),
            {'do': 'confirm', 'label': 'Import'}],
           [be('tables', 'The tables of tickets.sql are imported.', model('tables')),
            be('tickets', 'tickets has the columns of the script.', table_of('tickets', 'field_names'))]),
        cp('sql-keep', 'Import the MySQL script clinic.sql, keeping the tables already in the diagram.',
           'The tables customers, orders and products are shown together with doctors and visits.', start(*SHOP),
           [menu('File', 'Import from SQL'), {'do': 'upload-tab'}, upload('clinic.sql'),
            {'do': 'confirm', 'label': 'Import'}],
           [be('tables', 'The imported tables are added after the existing ones.', model('tables'))]),
        cp('sql-replace', 'Import the MySQL script clinic.sql, replacing the current diagram.',
           'Only the tables doctors and visits are shown.', start(*SHOP),
           [menu('File', 'Import from SQL'), {'do': 'upload-tab'}, upload('clinic.sql'),
            {'do': 'tick', 'label': 'Overwrite existing diagram'}, {'do': 'confirm', 'label': 'Import'}],
           [be('tables', 'The diagram holds only the imported tables.', model('tables'))]),
        cp('broken', 'Try to import the SQL script unfinished.sql into this MySQL diagram.',
           'The editor reports that the script cannot be read and imports nothing.', start(*SHOP),
           [menu('File', 'Import from SQL'), {'do': 'upload-tab'}, upload('unfinished.sql'), click('Import'),
            wait(1)],
           [be('unchanged', 'The diagram keeps its tables.', model('tables'), requires=['sql/tables'])]),
        cp('dbml-broken', 'Try to import the DBML file unclosed.dbml.',
           'The editor reports that the file cannot be read and imports nothing.', [fresh('generic')],
           [menu('File', 'Import from', 'DBML'), upload('unclosed.dbml'), wait(1)],
           [be('unchanged', 'Nothing is imported.', model('counts'), requires=['dbml/tables'])]),
        cp('json-mismatch', 'Try to import the diagram file gui-shop.json (a MySQL diagram) into this generic diagram.',
           'The editor refuses because the databases of the two diagrams do not match.', start(*BLOG),
           [menu('File', 'Import from', 'JSON'), upload('gui-shop.json'), wait(1)],
           [be('unchanged', 'The diagram keeps its tables.', model('tables'), requires=['json/tables'])]),
        cp('sql-sqlite', 'Import the SQLite script pantry.sql into this generic diagram.',
           'The tables shelves and jars are shown, connected by a relationship.', [fresh('generic')],
           [menu('File', 'Import from SQL', 'SQLite'), {'do': 'upload-tab'}, upload('pantry.sql'),
            {'do': 'confirm', 'label': 'Import'}],
           [be('tables', 'The tables of pantry.sql are imported.', model('tables')),
            be('jars', 'jars has the columns of the script.', table_of('jars', 'field_names')),
            be('relationships', 'The foreign key becomes a relationship.', model('relationships'))]),
        cp('cancel-json', 'Cancel the pending diagram import and return to the existing Shop diagram.',
           'The Shop diagram is usable again with customers, orders and products; the replacement was not imported.',
           start(*SHOP, {'do': 'stage-json', 'fixture': 'mysql-catalog'}), [click('Cancel')],
           [be('kept', 'Cancelling the prepared replacement keeps the original tables and fields.',
               model('all-fields'), requires=['json/tables'])]),
    ], files=['gui-library.json', 'inventory.dbml', 'clinic.sql', 'tickets.sql', 'unfinished.sql', 'unclosed.dbml',
              'gui-shop.json', 'pantry.sql'])


# -- export dialogs: SQL ---------------------------------------------------------------------------------------
def dl_sql(key, column=None):
    spec = {'type': 'sql', 'export': ['download', '.sql'], 'key': key}
    if column:
        spec['column'] = column
    return spec


def export_sql():
    def export(*path):
        return [menu('File', 'Export SQL', *path), click('Export'), {'do': 'download', 'suffix': '.sql'}]
    out = [cp('own', 'Export the diagram as an SQL file.', 'An SQL script that creates the tables customers, orders and '
                                                          'products is downloaded.', start(*SHOP), export(),
              [be('orders', 'The script creates orders as the reference does.', dl_sql('table:orders')),
               be('fk', 'The script adds the foreign key of orders.', dl_sql('fk:orders(customer_id)->customers(id)'))])]
    out.append(cp('own-postgresql', 'Export this PostgreSQL diagram as an SQL file.',
                  'An SQL script that creates the enum, the type and the tables is downloaded.', start(*EVENTS),
                  export(),
                  [be('enum', 'The script creates the enum mood as the reference does.', dl_sql('enum:mood')),
                   be('type', 'The script creates the type address as the reference does.', dl_sql('type:address')),
                   be('events', 'The script creates events as the reference does.', dl_sql('table:events')),
                   be('mood', 'The script declares events.mood with the enum type as the reference does.',
                      dl_sql('table:events', 'mood'))]))
    for key, entry in (('postgresql', 'PostgreSQL'), ('sqlite', 'SQLite'), ('mssql', 'MSSQL'), ('oracle', 'Oracle'),
                       ('mariadb', 'MariaDB'), ('mysql', 'MySQL')):
        points = [be('posts', f'The {entry} script creates posts as the reference does.', dl_sql('table:posts')),
                  be('title', f'The {entry} script declares posts.title (VARCHAR(120)) as the reference does.',
                     dl_sql('table:posts', 'title'))]
        if key != 'sqlite':
            points.append(be('fk', f'The {entry} script adds the foreign key of posts.',
                             dl_sql('fk:posts(user_id)->users(id)')))
        out.append(cp(key, f'Export this generic diagram as an SQL file for {entry}.',
                      f'An SQL script for {entry} that creates the tables users, posts, tags and post_tags is '
                      'downloaded.', start(*BLOG), export(entry), points))
    return episode('gui-export-sql', 'sql-export', out)


# -- export dialogs: other files ---------------------------------------------------------------------------------
def export_files():
    return episode('gui-export', 'exports', [
        cp('json', 'Export the diagram as a JSON file.', 'A JSON file of the diagram is downloaded.', start(*BLOG),
           [menu('File', 'Export as', 'JSON'), click('Export'), {'do': 'download', 'suffix': '.json'}],
           [be('tables', 'The file holds the tables with their columns.', {'type': 'file-model', 'suffix': '.json',
                                                                            'part': 'tables'}),
            be('relationships', 'The file holds the relationship.', {'type': 'file-model', 'suffix': '.json',
                                                                      'part': 'relationships'})]),
        cp('dbml', 'Export the diagram as a DBML file.', 'A DBML file of the diagram is downloaded.', start(*BLOG),
           [menu('File', 'Export as', 'DBML'), click('Export'), {'do': 'download', 'suffix': '.dbml'}],
           [be('posts', 'The file defines the table posts as the reference does.',
               {'type': 'blocks', 'format': 'dbml', 'export': ['download', '.dbml'], 'key': 'table:posts'})]),
        cp('mermaid', 'Export the diagram as a Mermaid diagram file.', 'A Mermaid file of the diagram is downloaded.',
           start(*BLOG), [menu('File', 'Export as', 'Mermaid'), click('Export'), {'do': 'download', 'suffix': '.md'}],
           [be('posts', 'The file declares the entity posts as the reference does.',
               {'type': 'blocks', 'format': 'mermaid', 'export': ['download', '.md'], 'key': 'entity:posts'})]),
        cp('markdown', 'Export the documentation of the diagram as a Markdown file.',
           'A Markdown document describing the tables is downloaded.', start(*BLOG),
           [menu('File', 'Export as', 'Markdown'), click('Export'), {'do': 'download', 'suffix': '.md'}],
           [be('posts', 'The document describes the table posts as the reference does.',
               {'type': 'blocks', 'format': 'markdown', 'export': ['download', '.md'], 'key': 'section:Blog documentation/Table structure/posts'})]),
        cp('saved', 'Export all diagrams saved in this browser as one archive file.',
           'An archive file with the saved diagrams is downloaded.', start(*BLOG),
           [menu('Settings', 'Export saved data'), {'do': 'download', 'suffix': '.zip'}],
           [be('archive', 'The archive holds the saved diagram Blog with its tables.',
               {'type': 'archive', 'export': ['download', '.zip']})]),
    ])


def export_images():
    def image(fmt, entry, suffix, **extra):
        return {'type': 'image', 'export': ['download', suffix], 'texts': ['Products', 'Categories', 'description'],
                'absent': ['Secrets'], **extra}
    return episode('gui-images', 'images', [
        cp('png', 'Export the diagram as a PNG image.', 'A PNG picture of the diagram is downloaded.', start('generic', 'image-catalog'),
           [menu('File', 'Export as', 'PNG'), click('Export'), {'do': 'download', 'suffix': '.png'}],
           [be('png', 'A PNG image with the drawing is saved.', image('png', 'PNG', '.png'))]),
        cp('jpeg', 'Export the diagram as a JPEG image.', 'A JPEG picture of the diagram is downloaded.', start('generic', 'image-catalog'),
           [menu('File', 'Export as', 'JPEG'), click('Export'), {'do': 'download', 'suffix': '.jpeg'}],
           [be('jpeg', 'A JPEG image with the drawing is saved.', image('jpeg', 'JPEG', '.jpeg'))]),
        cp('svg', 'Export the diagram as an SVG image.', 'An SVG picture of the diagram is downloaded.', start('generic', 'image-catalog'),
           [menu('File', 'Export as', 'SVG'), click('Export'), {'do': 'download', 'suffix': '.svg'}],
           [be('svg', 'An SVG image naming the tables is saved.', image('svg', 'SVG', '.svg',
                                                                        texts=['Products', 'Categories', 'description']))]),
        cp('pdf', 'Export the diagram as a PDF document.', 'A PDF of the diagram is downloaded.', start('generic', 'image-catalog'),
           [menu('File', 'Export as', 'PDF'), {'do': 'download', 'suffix': '.pdf'}],
           [be('pdf', 'A one-page PDF with the picture is saved.', image('pdf', 'PDF', '.pdf', facts='pages'))]),
    ])


# -- diagrams: rename, save as, open, new, delete ---------------------------------------------------------------
def saved(*names):
    return {'type': 'saved', 'names': list(names)}


def diagrams():
    copy = {'do': 'dialog-fill', 'menu': ['File', 'Save as'], 'value': 'Shop copy', 'button': 'Save as'}
    return episode('gui-diagrams', 'diagrams', [
        cp('rename', 'Rename the diagram to "Shop v2".', 'The editor shows the diagram title Shop v2.', start(*SHOP),
           [{'do': 'dialog-fill', 'menu': ['File', 'Rename'], 'value': 'Shop v2', 'button': 'Rename'}],
           [be('title', 'The diagram is titled Shop v2.', model('title'))]),
        cp('save-as', 'Save the diagram as a new diagram named "Shop archive", then show the list of saved diagrams.',
           'The list of saved diagrams shows Shop archive beside Shop.', start(*SHOP),
           [{'do': 'dialog-fill', 'menu': ['File', 'Save as'], 'value': 'Shop archive', 'button': 'Save as'},
            wait(1), menu('File', 'Open'), wait(1)],
           [be('saved', 'Shop archive is saved beside Shop.', saved('Shop', 'Shop archive'))]),
        cp('open', 'Open the saved diagram "Shop copy".', 'The editor shows the diagram Shop copy with its three tables.',
           start(*SHOP, copy, {'do': 'confirm-menu', 'menu': ['Edit', 'Clear']}, wait(2)),
           [{'do': 'choose', 'menu': ['File', 'Open'], 'item': 'Shop copy', 'button': 'Open'}],
           [be('title', 'The open diagram is Shop copy.', model('title')),
            be('tables', 'It has the tables saved in the copy.', model('tables'))]),
        cp('new', 'Start a new, empty diagram for PostgreSQL.', 'An empty PostgreSQL diagram is shown.', start(*SHOP),
           [menu('File', 'New'), text('Blank'), click('Create'), text('PostgreSQL'), click('Confirm')],
           [be('database', 'The new diagram is for PostgreSQL.', model('database')),
            be('empty', 'It is empty.', model('counts'), requires=['new/database'])]),
        cp('delete', 'Delete the current diagram "Shop copy", then show the list of saved diagrams.',
           'The diagram Shop copy is deleted: the editor no longer shows it and it is gone from the saved diagrams.',
           start(*SHOP, copy,
                                                                                         {'do': 'choose', 'menu': ['File', 'Open'], 'item': 'Shop copy', 'button': 'Open'}),
           [menu('File', 'Delete diagram', leave=False), click('Confirm'), wait(3), menu('File', 'Open'), wait(1)],
           [be('saved', 'Shop copy is gone and Shop stays.', saved('Shop', 'Shop copy'))]),
        cp('cancel-delete', 'Cancel the pending deletion, then show the saved diagrams.',
           'Shop remains in the list of saved diagrams.',
           start(*SHOP, press('Control+s'), wait(1), menu('File', 'Delete diagram', leave=False)),
           [click('Cancel'), menu('File', 'Open')],
           [be('saved', 'The saved Shop diagram survives cancellation.', saved('Shop'), requires=['delete/saved'])]),
    ])


# -- templates -------------------------------------------------------------------------------------------------
def templates():
    return episode('gui-templates', 'templates', [
        cp('new', 'Create a new diagram from the template "Library schema".',
           'A diagram with the tables of the library template is shown.', start(*SHOP),
           [menu('File', 'New'), text('Library schema'), click('Create')],
           [be('tables', 'The diagram has the tables of the template.', model('tables')),
            be('title', 'The diagram takes the title of the template.', model('title'))]),
        cp('page', 'On the templates page, open the template "Bank schema" in the editor.',
           'The editor shows a diagram with the tables of the bank template.',
           start(*BLOG, {'do': 'open', 'path': '/templates'}),
           [{'do': 'nth-unnamed', 'index': 4}, wait(2)],
           [be('tables', 'The diagram has the tables of the template.', model('tables'))]),
        cp('save', 'Save the current diagram as a template, then show the list of your own templates.',
           'The list of your own templates shows the template Shop.', start(*SHOP),
           [menu('File', 'Save as template'), wait(1), {'do': 'open', 'path': '/templates'},
            text('Your templates'), wait(1)],
           [be('listed', 'The templates page lists Shop under the user\'s own templates.',
               {'type': 'shown', 'open': '/templates', 'reveal': ['Your templates'], 'texts': ['Shop'],
                'exact': True})]),
        cp('use', 'Create a new diagram from your own template "Shop".', 'A diagram with the tables of Shop is shown.',
           start(*SHOP, {'do': 'menu', 'path': ['File', 'Save as template']},
                 {'do': 'dialog-fill', 'menu': ['File', 'Rename'], 'value': 'Other', 'button': 'Rename'},
                 {'do': 'confirm-menu', 'menu': ['Edit', 'Clear']}),
           [menu('File', 'New'), text('Shop'), click('Create')],
           [be('tables', 'The new diagram has the tables of the template.', model('tables')),
            be('title', 'It takes the template\'s title.', model('title'))]),
        cp('page-own', 'On the templates page, open your own template "Shop" in the editor.',
           'The editor shows a diagram with the tables customers, orders and products.',
           start(*SHOP, {'do': 'menu', 'path': ['File', 'Save as template']},
                 {'do': 'dialog-fill', 'menu': ['File', 'Rename'], 'value': 'Other', 'button': 'Rename'},
                 {'do': 'select', 'name': 'products'}, {'do': 'press', 'key': 'Delete'}, wait(2),
                 {'do': 'open', 'path': '/templates'}),
           [text('Your templates'), {'do': 'nth-unnamed', 'index': 0}, wait(2)],
           [be('tables', 'The diagram has the tables of the template.', model('tables')),
            be('title', 'It takes the template\'s title.', model('title'))]),
        cp('delete', 'On the templates page, delete your own template "Shop".',
           'The template Shop is no longer listed among your templates.',
           start(*SHOP, {'do': 'menu', 'path': ['File', 'Save as template']}, {'do': 'open', 'path': '/templates'}),
           [text('Your templates'), click('Delete'), wait(1)],
           [be('gone', 'The templates page no longer lists Shop under the user\'s own templates.',
               {'type': 'shown', 'open': '/templates', 'reveal': ['Your templates'], 'texts': ['Shop'], 'exact': True},
               requires=['save/listed'])]),
    ])


# -- settings --------------------------------------------------------------------------------------------------
def settings():
    return episode('gui-settings', 'settings', [
        cp('language', 'Switch the interface language of the editor to German (Deutsch).',
           'The menus and labels of the editor are shown in German.', start(*BLOG),
           [menu('Settings', 'Language'), text('Deutsch'), click('Confirm')]),
        cp('autosave', 'Turn off autosave.', 'The autosave setting is shown as off.', start(*BLOG),
           [menu('Settings', 'Autosave'), menu('Settings', leave=False)]),
        cp('custom-type', 'In the editor\'s settings for custom data types, add the type "MONEY" for MySQL; then use '
                          'it as the type of the column "price" of "products".',
           'The column price of products has the type MONEY.', start(*SHOP),
           [menu('Settings', 'Configure custom types'), click('Add custom type'), {'do': 'fill-new', 'value': 'MONEY'},
            click('Save'), open_table('products'), row('price', role='combobox'), pick('MONEY')],
           [be('type', 'price has the type MONEY.', field_of('products', 'price', 'type'))]),
        cp('flush', 'Delete everything the editor has stored in this browser.',
           'The editor starts over without saved diagrams and asks for the database of a new diagram.', start(*BLOG),
           [menu('Settings', 'Flush storage', leave=False), click('Confirm'), wait(2)],
           [be('fresh', 'The editor asks for the database of a new diagram.', {'type': 'shown',
                                                                                'texts': ['Choose a database']})]),
    ])


# -- pages -----------------------------------------------------------------------------------------------------
def page(pattern):
    return {'type': 'page', 'path': pattern}


def pages():
    return episode('gui-pages', 'pages', [
        cp('landing', 'From the home page, go to the editor.', 'The editor is shown.',
           [fresh('generic'), {'do': 'open', 'path': '/'}], [{'do': 'click', 'label': 'Try it for yourself'}],
           [be('editor', 'The editor page is open.', page('/editor(/.*)?'))]),
        cp('landing-templates', 'From the home page, open the templates page.', 'The page listing the templates is '
                                                                                'shown.',
           [fresh('generic'), {'do': 'open', 'path': '/'}], [{'do': 'click', 'label': 'Templates'}],
           [be('templates', 'The templates page is open.', page('/templates'))]),
        cp('not-found', 'Open the address /no-such-page of the application.',
           'A page says that what was looked for could not be found and points to the documentation, e-mail and '
           'Discord for help.', [fresh('generic')], [{'do': 'open', 'path': '/no-such-page'}]),
        cp('exit', 'Leave the editor with its exit command.', 'The home page of the application is shown.',
           start(*BLOG), [menu('File', 'Exit'), wait(1)],
           [be('home', 'The home page is open.', page('/'))]),
        cp('bug-report', 'Open the page for reporting a bug from the editor.', 'A form for reporting a bug is shown.',
           start(*BLOG), [menu('Help', 'Report a bug')],
           [be('page', 'The bug report page is open.', page('/bug-report'))]),
    ])


# -- PostgreSQL specifics, more column properties ----------------------------------------------------------------
def postgres():
    return episode('gui-postgresql', 'columns', [
        cp('array', 'Make the column "price" of "events" an array.', 'The column price of events is marked as an array.',
           start(*EVENTS), [open_table('events'), row('price'), {'do': 'toggle', 'index': 1}],
           [be('array', 'price is an array.', field_of('events', 'price', 'isArray'))]),
        cp('inherits', 'Make the table "events" inherit from the table "venues".',
           'The table events is shown as inheriting from venues.', start(*EVENTS),
           [open_table('events'), {'do': 'select-in', 'placeholder': 'Inherits', 'option': 'venues'}],
           [be('inherits', 'events inherits from venues.', table_of('events', 'inherits'))]),
        cp('jsonb', 'Change the type of the column "price" of "events" to JSONB.',
           'The column price of events has the type JSONB.', start(*EVENTS),
           [open_table('events'), row('price', role='combobox'), pick('JSONB')],
           [be('type', 'price has the type JSONB.', field_of('events', 'price', 'type'))]),
    ])


def fields4():
    return episode('gui-fields-4', 'columns', [
        cp('precision', 'Set the precision of the column "price" of "products" to 12,4.',
           'The column price of products is shown as DECIMAL(12,4).', start(*SHOP),
           [open_table('products'), row('price'), fill('8,2', '12,4')],
           [be('size', 'price has the precision 12,4.', field_of('products', 'price', 'type', 'size'))]),
        cp('enum', 'Change the type of the column "vip" of "customers" to ENUM with the values "yes" and "no".',
           'The column vip of customers is an ENUM of yes and no.', start(*SHOP),
           [open_table('customers'), row('vip', role='combobox'), pick('ENUM'), row('vip'),
            {'do': 'fill-aria', 'aria': 'input value', 'value': 'yes', 'commit': 'Enter'},
            {'do': 'fill-aria', 'aria': 'input value', 'value': 'no', 'commit': 'Enter'}],
           [be('values', 'vip is an ENUM of yes and no.', field_of('customers', 'vip', 'type', 'values'))]),
        cp('new-column', 'Add a column "sku" of type VARCHAR(40) that is NOT NULL and unique to the table "products".',
           'The table products shows a column sku of type VARCHAR(40).', start(*SHOP),
           [open_table('products'), click('Add column'), fill('', 'sku'), row('sku', role='combobox'), pick('VARCHAR'),
            row('sku', title='Nullable'), row('sku'), fill_ph('Size', '40'), {'do': 'toggle', 'index': 0}],
           [be('column', 'products has the column sku with these properties.',
               field_of('products', 'sku', 'name', 'type', 'size', 'notNull', 'unique'))]),
        cp('default-now', 'Set the default value of the column "placed" of "orders" to CURRENT_TIMESTAMP.',
           'The column placed of orders has the default value CURRENT_TIMESTAMP.', start(*SHOP),
           [open_table('orders'), row('placed'), fill_ph('Default', 'CURRENT_TIMESTAMP')],
           [be('default', 'placed defaults to CURRENT_TIMESTAMP.', field_of('orders', 'placed', 'default'))]),
    ])


# -- problems --------------------------------------------------------------------------------------------------
def problems():
    return episode('gui-problems', 'problems', [
        cp('show', 'Show the list of problems the editor finds in this diagram.',
           'A list of problems is shown and reports that the table posts has the column title twice.',
           start('generic', 'gui-dupes'), [click('Problems', startswith=True)]),
        cp('fix', 'The table "posts" has two columns named "title"; rename the second one to "subtitle".',
           'The editor reports no problems any more.', start('generic', 'gui-dupes'),
           [open_table('posts'), fill('title', 'subtitle', nth=1)],
           [be('columns', 'posts has the columns title and subtitle.', table_of('posts', 'field_names'))]),
        cp('no-key', 'The editor reports that the table "tags" has no primary key; make its column "id" the primary key.',
           'The editor no longer reports a problem for tags.', start('generic', 'gui-nokey'),
           [open_table('tags'), row('id', title='Primary')],
           [be('primary', 'tags.id is the primary key.', field_of('tags', 'id', 'primary'))]),
        cp('enum-values', 'The editor reports that the enum "state" has no values; give it the values "on" and "off".',
           'The enum state lists on and off and the editor no longer reports it.', start('postgresql', 'gui-empty-enum'),
           [tab('Enums'), text('state'),
            {'do': 'fill-aria', 'aria': 'input value', 'nth': -1, 'value': 'on', 'commit': 'Enter'},
            {'do': 'fill-aria', 'aria': 'input value', 'nth': -1, 'value': 'off', 'commit': 'Enter'}],
           [be('enums', 'state has the values on and off.', model('enums'))]),
        cp('strict', 'Turn off strict mode, then look at the problems panel.',
           'The problems panel no longer lists the duplicate column of posts; it says that strict mode is off.',
           start('generic', 'gui-dupes'), [menu('View', 'Strict mode'), click('Problems', startswith=True)]),
    ])


# -- more views ----------------------------------------------------------------------------------------------
def views2():
    return episode('gui-views-2', 'views', [
        cp('rename', 'Rename the view "post_list" to "front_page".', 'The view is shown as front_page.',
           start(*BLOG_VIEW), [tab('Views'), text('post_list'), fill('post_list', 'front_page')],
           [be('views', 'The view is renamed.', model('views'))]),
        cp('delete', 'Delete the view "post_list".', 'The view post_list is no longer shown.', start(*BLOG_VIEW),
           [tab('Views'), text('post_list'), {'do': 'row-of', 'anchor': 'Add comment', 'unnamed': 0}],
           [be('views', 'The diagram has no view.', model('views'), requires=['rename/views'])]),
        cp('base', 'Change the base table of the view "post_list" to "users".', 'The view post_list is based on users.',
           start(*BLOG_VIEW), [tab('Views'), text('post_list'), {'do': 'select-value', 'value': 'posts',
                                                                  'option': 'users'}],
           [be('base', 'The view is based on users.', model('view', name='post_list', aspects=['base']))]),
        cp('join-type', 'Change the join of the view "author_posts" to a LEFT JOIN.',
           'The view author_posts shows a left join of users.', start('generic', 'gui-blog-view2'),
           [tab('Views'), text('author_posts'), {'do': 'select-value', 'value': 'INNER', 'option': 'LEFT'}],
           [be('joins', 'The join is a left join.', model('view', name='author_posts', aspects=['joins']))]),
        cp('remove-column', 'Remove the output column "title" from the view "author_posts".',
           'The view author_posts no longer outputs title.', start('generic', 'gui-blog-view2'),
           [tab('Views'), text('author_posts'), {'do': 'row-of', 'anchor': 'posts.title', 'unnamed': 0}],
           [be('columns', 'The view outputs only the other columns.',
               model('view', name='author_posts', aspects=['columns']))]),
    ])


# -- more relationships, indices, types, table states, locks ---------------------------------------------------------
STAFF = ('generic', 'gui-staff')
LINES = ('generic', 'gui-lines')


def relationships3():
    rel_open = [text('Relationships (1)'), text('fk_posts_user_id_users')]
    return episode('gui-relationships-3', 'relationships', [
        cp('label', 'Change the label shown on the many side of the relationship between posts and users to "*".',
           'The relationship line shows * instead of n at its many end.', start(*BLOG),
           rel_open + [fill_ph('Label', '*')],
           [be('label', 'The many side is labelled *.', model('relationship', name='fk_posts_user_id_users',
                                                              aspects=['label']))]),
        cp('color', 'Set the colour of the relationship between posts and users to #e63946.',
           'The relationship line between posts and users is drawn in red.', start(*BLOG),
           rel_open + [{'do': 'swatch-left', 'anchor': 'Swap'}, {'do': 'hex', 'value': '#e63946'}],
           [be('color', 'The relationship has the colour #e63946.', model('relationship', name='fk_posts_user_id_users',
                                                                         aspects=['color']))]),
        cp('composite', 'Extend the relationship from shipments to order_lines to a composite key: add the pair '
                        'shipments.line_no to order_lines.line_no.',
           'The relationship connects both shipments.order_id and shipments.line_no with order_lines.',
           start(*LINES),
           [text('Relationships (1)'), text('shipment_line'), text('Composite key'), click('Add column'),
            {'do': 'select-value', 'value': 'id', 'option': 'line_no'},
            {'do': 'select-value', 'value': 'order_id', 'nth': -1, 'option': 'line_no'}],
           [be('pairs', 'The relationship pairs order_id with order_id and line_no with line_no.',
               model('relationship', name='shipment_line', aspects=['pairs']))]),
        cp('self', 'Connect the column "manager_id" of "staff" to the column "id" of the same table.',
           'A relationship line leads from staff.manager_id back to staff.id.', start(*STAFF),
           [{'do': 'drag', 'x': 423, 'y': 273, 'to_x': 520, 'to_y': 199, 'steps': 20}],
           [be('relationships', 'The relationship from staff.manager_id to staff.id exists.', model('relationships'))]),
        cp('between', 'Connect the column "lead_id" of "teams" to the column "id" of "staff".',
           'A relationship line connects teams.lead_id with staff.id.', start(*STAFF),
           [{'do': 'drag', 'x': 783, 'y': 273, 'to_x': 520, 'to_y': 199, 'steps': 20}],
           [be('relationships', 'The relationship from teams.lead_id to staff.id exists.', model('relationships'))]),
    ])


SHOP_UC = ('mysql', 'gui-shop-uc')


def indexes2():
    index_open = [open_table('orders'), text('Indices'), {'do': 'row-of', 'anchor': 'status placed', 'unnamed': 0}]
    uc_open = [open_table('products'), text('Unique constraints'), {'do': 'row-of', 'anchor': 'name price',
                                                                     'unnamed': 0}]
    return episode('gui-indexes-2', 'indices', [
        cp('columns', 'Append the column "customer_id" to the index "orders_status_placed" of "orders", '
           'keeping its existing columns first: the final column order must be status, placed, customer_id.',
           'The index orders_status_placed lists status, placed and customer_id in that order.', start(*SHOP),
           [open_table('orders'), text('Indices'), {'do': 'select-value', 'value': 'status placed',
                                                     'option': 'customer_id', 'at_end': True}],
           [be('indices', 'The index covers status, placed and customer_id in that order.',
               table_of('orders', 'indices'))]),
        cp('second', 'Add a second index to the table "orders", on the column "placed".',
           'The table orders has two indices; the new one covers placed.', start(*SHOP),
           [open_table('orders'), {'do': 'click-title', 'title': 'Add'}, option('Add index'),
            {'do': 'select-in', 'placeholder': 'Select columns', 'option': 'placed'}],
           [be('indices', 'orders keeps its index and gains one on placed.', table_of('orders', 'indices'))]),
        cp('uc-rename', 'Rename the unique constraint "products_name_price" of "products" to "products_unique_offer".',
           'The unique constraint is shown as products_unique_offer.', start(*SHOP_UC),
           uc_open + [fill('products_name_price', 'products_unique_offer')],
           [be('uniques', 'The constraint is renamed.', table_of('products', 'uniques'))]),
        cp('uc-columns', 'Remove the column "price" from the unique constraint "products_name_price".',
           'The unique constraint products_name_price covers only name.', start(*SHOP_UC),
           [open_table('products'), text('Unique constraints'), {'do': 'tag-close', 'tag': 'price'}],
           [be('uniques', 'The constraint covers name only.', table_of('products', 'uniques'))]),
        cp('uc-delete', 'Delete the unique constraint "products_name_price".',
           'The table products no longer has a unique constraint.', start(*SHOP_UC),
           uc_open + [click('Delete')],
           [be('uniques', 'products has no unique constraint.', table_of('products', 'uniques'), requires=['uc-rename/uniques'])]),
    ], hint=INDEX_HINT)


def types2():
    return episode('gui-types-2', 'types', [
        cp('rename', 'Rename the type "address" to "location".', 'The type is listed as location.', start(*EVENTS),
           [tab('Types'), text('address'), fill('address', 'location')],
           [be('types', 'The type is renamed.', model('types'))]),
        cp('field-type', 'Change the type of the column "zip" of the type "address" to VARCHAR.',
           'The column zip of the type address has the type VARCHAR.', start(*EVENTS),
           [tab('Types'), text('address'), row('zip', role='combobox'), pick('VARCHAR')],
           [be('types', 'zip is a VARCHAR.', model('types'))]),
        cp('field-delete', 'Delete the column "zip" of the type "address".', 'The type address lists only street.',
           start(*EVENTS), [tab('Types'), text('address'), row('zip'), click('Delete')],
           [be('types', 'address keeps street only.', model('types'))]),
        cp('enum-value-delete', 'Remove the value "sad" from the enum "mood".', 'The enum mood lists only happy.',
           start(*EVENTS), [tab('Enums'), text('mood'), {'do': 'tag-close', 'tag': 'sad'}],
           [be('enums', 'mood has only happy.', model('enums'))]),
        cp('enum-batch', 'Add the values "calm", "tired" and "busy" to the enum "mood".',
           'The enum mood lists happy, sad, calm, tired and busy.', start(*EVENTS),
           [tab('Enums'), text('mood'), {'do': 'fill-aria', 'aria': 'input value', 'value': 'calm', 'commit': 'Enter'},
            {'do': 'fill-aria', 'aria': 'input value', 'value': 'tired', 'commit': 'Enter'},
            {'do': 'fill-aria', 'aria': 'input value', 'value': 'busy', 'commit': 'Enter'}],
           [be('enums', 'mood has the five values in order.', model('enums'))]),
    ])


STATES = ('generic', 'gui-blog-states')


def tables4():
    return episode('gui-tables-3', 'tables', [
        cp('create', 'Create a table "comments" with the columns "id" (INT, primary key), "post_id" (INT, not null) '
                     'and "body" (TEXT).', 'A table comments with the columns id, post_id and body is shown.',
           start(*BLOG),
           [click('Add table'), {'do': 'fill-prefix', 'prefix': 'table_', 'value': 'comments'}, click('Add column'),
            fill('', 'post_id'), row('post_id', role='combobox'), pick('INT'), row('post_id', title='Nullable'),
            click('Add column'), fill('', 'body'), row('body', role='combobox'), pick('TEXT')],
           [be('columns', 'comments has the three columns with their types.',
               {'type': 'model', 'part': 'table', 'name': 'comments', 'aspects': ['typenames']}),
            be('id', 'id is the primary key.', field_of('comments', 'id', 'primary')),
            be('post_id', 'post_id is required and not a key.', field_of('comments', 'post_id', 'notNull', 'primary'))]),
        cp('width', 'Make the table "posts" wider by dragging its right edge about 100 pixels to the right.',
           'The table posts is drawn wider than before.', start(*BLOG),
           [{'do': 'pointer', 'action': 'move', 'x': 800, 'y': 230},
            {'do': 'drag', 'x': 917, 'y': 230, 'to_x': 1017, 'to_y': 230}],
           [be('width', 'posts is wider than the default width.', model('table-width', name='posts', width=220))]),
        cp('locked', 'The table "users" is locked. Try to drag it down by about 200 pixels, then drag the table '
                     '"posts" down by about 200 pixels.',
           'The locked table users stays where it was, while the table posts moves down.', start(*STATES),
           [{'do': 'drag', 'x': 470, 'y': 160, 'to_x': 470, 'to_y': 360},
            {'do': 'drag', 'x': 760, 'y': 160, 'to_x': 760, 'to_y': 360}],
           [be('unmoved', 'users did not move.', moved('users', (-420, -360)), requires=['locked/moved']),
            be('moved', 'posts moved down.', moved('posts', (-130, -360)))]),
    ])


def clipboard2():
    paste = [{'do': 'pointer', 'x': 800, 'y': 700}, press('Control+v')]
    return episode('gui-clipboard-2', 'clipboard', [
        cp('cut-note', 'Cut the note "Todo" out of the diagram.', 'The note Todo is no longer shown.',
           start(*BLOG_AREAS), [{'do': 'pointer', 'x': 1080, 'y': 500}, press('Control+x')],
           [be('notes', 'The note is removed.', model('notes', aspects=['title']), requires=['copy-view/views']),
            be('clipboard', 'The clipboard holds the note with its title and text.',
               {'type': 'clipboard', 'json': 'note', 'keys': ['title', 'content']})]),
        cp('copy-view', 'Copy the view "post_list" and paste it into the diagram.',
           'A second view post_list appears.', start(*BLOG_VIEW),
           [{'do': 'pointer', 'x': 1100, 'y': 520}, press('Control+c'), press('Control+v')],
           [be('views', 'The diagram has two views with the columns of post_list.', model('views'))]),
        cp('duplicate-view', 'Duplicate the view "post_list".', 'A second view post_list appears.', start(*BLOG_VIEW),
           [{'do': 'pointer', 'x': 1100, 'y': 520}, press('Control+d')],
           [be('views', 'The diagram has two views post_list.', model('views'))]),
        cp('paste-area', 'The clipboard holds a subject area copied from the editor (an area "Pasted area"); paste '
                         'it into the diagram.', 'A subject area Pasted area appears.',
           start(*BLOG, {'do': 'clipboard', 'file': 'clip-area.json'}), paste,
           [be('areas', 'The pasted area keeps its name and colour.', model('areas', aspects=['name', 'color']))]),
    ])


def sql_tools():
    return episode('gui-sql-tools', 'sql-export', [
        cp('copy-sql', 'Copy the SQL script of this MySQL diagram to the clipboard, then paste it into the editor of '
                       'the SQL import dialog (without importing it), showing the CREATE TABLE customers statement.',
           'The SQL import dialog shows the pasted script of the diagram, with the CREATE TABLE statement of customers.',
           start(*SHOP),
           [menu('File', 'Export SQL'), wait(1), {'do': 'pointer', 'x': 945, 'y': 572}, wait(1), {'do': 'escape'},
            menu('File', 'Import from SQL'), wait(1), {'do': 'pointer', 'x': 600, 'y': 400}, press('Control+v'),
            press('Control+Home'), wait(1)],
           [be('customers', 'The copied script creates customers as the reference does.',
               {'type': 'clipboard', 'sql': 'table:customers'})]),
        cp('paste-sql', 'The clipboard holds a MySQL script; import it into this MySQL diagram by pasting it into '
                        'the SQL import dialog.', 'The tables doctors and visits are shown.',
           [fresh('mysql'), {'do': 'clipboard', 'file': 'clinic.sql'}],
           [menu('File', 'Import from SQL'), wait(1), {'do': 'pointer', 'x': 600, 'y': 400}, press('Control+v'), wait(1),
            {'do': 'confirm', 'label': 'Import'}],
           [be('tables', 'The pasted script is imported.', model('tables'))]),
    ])


VIEW3 = ('generic', 'gui-blog-view3')


def views3():
    view_open = [tab('Views'), text('author_posts')]
    return episode('gui-views-3', 'views', [
        cp('operator', 'Change the condition of the view "author_posts" from posts.id > 10 to posts.id >= 10.',
           'The view author_posts filters on posts.id >= 10.', start(*VIEW3),
           view_open + [{'do': 'select-value', 'value': '>', 'option': '>='}],
           [be('conditions', 'The condition uses >=.', model('view', name='author_posts', aspects=['conditions']))]),
        cp('or', 'Add a second condition to the view "author_posts": OR users.name = admin.',
           'The view author_posts has the conditions posts.id > 10 OR users.name = admin.', start(*VIEW3),
           view_open + [{'do': 'click-title', 'title': 'Add condition'},
                        {'do': 'select-in', 'placeholder': 'Column', 'option': 'users.name', 'keep': True},
                        {'do': 'select-value', 'value': 'AND', 'option': 'OR'},
                        {'do': 'wheel', 'x': 180, 'y': 600, 'delta_y': 300}, fill_ph('Value', 'admin', nth=1)],
           [be('conditions', 'The view has both conditions joined by OR.',
               model('view', name='author_posts', aspects=['conditions']))]),
        cp('alias', 'Change the alias of the output column users.name of the view "author_posts" to "writer".',
           'The view author_posts outputs writer.', start(*VIEW3), view_open + [fill('author', 'writer')],
           [be('columns', 'users.name is output as writer.', model('view', name='author_posts', aspects=['columns']))]),
        cp('remove-condition', 'Remove the condition of the view "author_posts".',
           'The view author_posts no longer has a condition.', start(*VIEW3),
           view_open + [{'do': 'row-of', 'anchor': 'posts.id', 'nth': 2, 'unnamed': 0}],
           [be('conditions', 'The view has no condition.', model('view', name='author_posts', aspects=['conditions']),
               requires=['operator/conditions'])]),
        cp('hide-view', 'Hide the view author_posts from the canvas while keeping it in the diagram.',
           'author_posts is still in the Views list and is no longer drawn on the canvas.', start(*VIEW3),
           [tab('Views'), {'do': 'row-of', 'anchor': 'author_posts', 'unnamed': 0}],
           [be('hidden', 'The existing view is marked hidden.', model('view', name='author_posts', aspects=['flags']))]),
        cp('move-view', 'Move the view author_posts down by about 150 pixels.',
           'The view is lower on the canvas than before.', start(*VIEW3),
           [{'do': 'drag', 'x': 1100, 'y': 520, 'to_x': 1100, 'to_y': 670}],
           [be('moved', 'The unlocked view moves down.',
               model('moved', kind='view', name='author_posts', **{'from': [200, 0]}))]),
        cp('lock-view', 'Lock the view author_posts, then try to drag it down by about 150 pixels.',
           'The view is shown as locked and stays at its original position.', start(*VIEW3),
           [{'do': 'pointer', 'action': 'move', 'x': 1100, 'y': 520}, {'do': 'click-title', 'title': 'Lock'},
            {'do': 'drag', 'x': 1100, 'y': 520, 'to_x': 1100, 'to_y': 670},
            {'do': 'pointer', 'action': 'move', 'x': 1100, 'y': 520}],
           [be('locked', 'The existing view is marked locked.', model('view', name='author_posts', aspects=['flags'])),
            be('unmoved', 'The locked view did not move.',
               model('moved', kind='view', name='author_posts', **{'from': [200, 0]}), requires=['move-view/moved'])]),
    ])


def custom_type_lifecycle():
    setup = start(*SHOP, {'do': 'custom-type-add', 'name': 'MONEY'}, {'do': 'table', 'name': 'products'},
                  {'do': 'choose-value', 'current': 'DECIMAL', 'value': 'MONEY'})
    config = menu('Settings', 'Configure custom types')
    return episode('gui-custom-types', 'settings', [
        cp('rename', 'Rename the MySQL custom data type MONEY to CREDIT and save the setting; show the price '
                     'column of products that already uses the type.',
           'The products.price column now shows CREDIT.', setup,
           [config, fill('MONEY', 'CREDIT'), click('Save'), open_table('products')],
           [be('type', 'Renaming the type updates columns that used MONEY.', field_of('products', 'price', 'type'))]),
        cp('delete', 'Delete the MySQL custom data type MONEY and save the setting; show products.price afterward.',
           'The products.price column uses the fallback type after MONEY is deleted.', setup,
           [config, {'do': 'modal-row-delete', 'field': 'MONEY'}, click('Save'), open_table('products')],
           [be('type', 'Deleting the type gives its existing columns the reference fallback.',
               field_of('products', 'price', 'type'))]),
        cp('color', 'Change the colour of the MySQL custom type MONEY to #ff0000, save, reload the page, '
                    'and show the saved custom type setting.',
           'The saved MONEY type is shown with a red colour swatch after reloading.', setup,
           [config, {'do': 'swatch', 'field': 'MONEY'}, {'do': 'hex', 'value': '#ff0000'},
            text('Name'), click('Save'), {'do': 'reload'}, wait(1), config]),
        cp('cancel-rename', 'An unsaved rename of MONEY to CREDIT is pending in custom-type settings. Close '
                            'without saving, then reopen the settings to show the stored type.',
           'The stored custom type is still MONEY, with no CREDIT type saved.', setup +
           [config, {'do': 'fill-value', 'current': 'MONEY', 'value': 'CREDIT'}],
           [click('Close'), config],
           [be('type', 'The unsaved rename leaves products.price as MONEY.', field_of('products', 'price', 'type'),
               requires=['rename/type'])]),
        cp('scope', 'Move the custom type MONEY from MySQL to PostgreSQL, save it, then reopen custom-type '
                    'settings and filter them to PostgreSQL.',
           'The PostgreSQL type list contains MONEY with PostgreSQL as its database.', setup,
           [config, {'do': 'select-value', 'value': 'MySQL', 'option': 'PostgreSQL'}, click('Save'), config,
            {'do': 'select-value', 'value': 'Database: All', 'option': 'PostgreSQL'}],
           [be('type', 'Removing MONEY from the MySQL scope updates its existing column to the fallback.',
               field_of('products', 'price', 'type'))]),
        cp('scope-filter', 'Show only PostgreSQL custom types in the settings; MONEY was created for MySQL.',
           'The custom-type settings show PostgreSQL selected and no MONEY custom type.', setup,
           [config, {'do': 'select-value', 'value': 'Database: All', 'option': 'PostgreSQL'}],
           [be('stored', 'The MySQL column keeps its custom type while the list is filtered.',
               field_of('products', 'price', 'type'), requires=['scope/type'])], requires=['scope/visible']),
    ])


def saved_diagram_tools():
    setup = [fresh('mysql'), {'do': 'saved-fixtures'}]
    names = ['Atlas', 'Birch', 'Cedar']
    def listed(ordered=False):
        return {'type': 'visible-list', 'names': names, 'ordered': ordered}
    return episode('gui-saved-tools', 'diagrams', [
        cp('search', 'Search the saved diagrams for "AT".', 'The saved list shows Atlas and hides Birch and Cedar.',
           setup, [fill_ph('Search...', 'AT')],
           [be('list', 'The search matches Atlas regardless of letter case.', listed())]),
        cp('database', 'Filter the saved diagram list to PostgreSQL.', 'Only Birch remains in the saved list.', setup,
           [{'do': 'select-value', 'value': 'All databases', 'option': 'PostgreSQL'}],
           [be('list', 'The database filter retains only Birch.', listed())]),
        cp('combined', 'Filter the saved diagrams to MySQL and search for "ar".',
           'Only Cedar is listed after applying both filters.', setup,
           [{'do': 'select-value', 'value': 'All databases', 'option': 'MySQL'}, fill_ph('Search...', 'ar')],
           [be('list', 'Name and database filters are combined.', listed())]),
        cp('clear', 'Clear the active search filter to show all saved diagrams again.',
           'Atlas, Birch and Cedar are all listed.', setup +
           [{'do': 'fill', 'placeholder': 'Search', 'value': 'Atlas'}],
           [click('Clear')],
           [be('list', 'Clearing filters restores all saved diagrams.', listed(), requires=['search/list'])]),
        cp('name-ascending', 'Sort the saved diagrams by name, ascending.',
           'The saved list is ordered Atlas, Birch, Cedar.', setup, [click('Name')],
           [be('order', 'Diagram names are in ascending order.', listed(True))]),
        cp('name-descending', 'Sort the saved diagrams by name, descending.',
           'The saved list is ordered Cedar, Birch, Atlas.', setup + [{'do': 'click', 'label': 'Name'}], [click('Name')],
           [be('order', 'Diagram names are in descending order.', listed(True))]),
        cp('size', 'Sort the saved diagrams by size, largest first.',
           'The list shows the larger saved diagrams before the smaller ones.', setup, [click('Size')],
           [be('order', 'The files are listed in descending size order.', listed(True))]),
    ])


def build():
    return [tables(), tables2(), fields1(), fields2(), fields3(), fields4(), indexes(), relationships1(),
            relationships2(), areas(), notes(), views(), views2(), types(), enums(), postgres(), colors(), history(),
            clipboard(), arrange(), panels(), display1(), display2(), zoom(), dbml_editor(), imports(), export_sql(),
            export_files(), export_images(), diagrams(), templates(), settings(), pages(), problems(),
            relationships3(), indexes2(), types2(), tables4(), clipboard2(), sql_tools(), views3(), custom_type_lifecycle(), saved_diagram_tools()]
