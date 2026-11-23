"""Pinned-standard GUI implementation of the reviewed functional goals, through the black-box runtime.

Recipes drive only the installed standard answer during record, with the same runtime GUI operations that the evaluator
and the model use. Routes and controls belong to the pinned standard only; they are never a candidate requirement.
"""
import time

from . import ui as desktop

# Navigator geometry of the pinned product at the fixed screen size: one row is 26 pixels high.
NAV_TOP = 119
NAV_ROW = 26
NAV_FIXED_HEAD = ['Dashboard', 'All Transactions', 'Scheduled Transactions', 'Favorites']
NAV_ACCOUNT_SECTIONS = [('Bank Accounts', 'Checking'), ('Credit Card Accounts', 'Credit Card'), ('Cash Accounts', 'Cash'),
                        ('Loan Accounts', 'Loan'), ('Term Accounts', 'Term'), ('Stock Portfolios', 'Investment')]
NAV_FIXED_TAIL = ['Assets', 'Budget Planner', 'Transaction Report', 'Reports', 'General Report Manager', 'Help']
# The accounts of the standard ledger.
NAV_CHILDREN = {'Bank Accounts': ['Euro Current', 'Everyday Checking', 'Rainy Day Savings'], 'Credit Card Accounts': ['Travel Visa'],
                'Cash Accounts': ['Pocket Cash'], 'Favorites': ['Everyday Checking', 'Travel Visa']}
LIST_TOP = 250
LIST_ROW = 23


def begin(ctx, checkpoint):
    """Before the reference-before evidence: a settled desktop."""
    driver = reference(ctx)
    if checkpoint.get('lifecycle') == 'restart':
        driver.expanded={}
        driver.reports_open=False
        driver.ui.wait(3.5)
    driver.ui.park()
    driver.ui.settle()


def execute(ctx, checkpoint):
    reference(ctx).execute(checkpoint)


def reference(ctx):
    if 'reference' not in ctx.state:
        ctx.state['reference'] = Reference(ctx.broker, ctx.episode)
    return ctx.state['reference']


class Reference:
    def __init__(self, broker, episode):
        self.ui = desktop.UI(broker)
        self.episode = episode
        self.expanded = {}
        self.sections = episode.get('navigator') or ['Bank Accounts', 'Credit Card Accounts', 'Cash Accounts']
        self.children = dict(NAV_CHILDREN, **(episode.get('navigator_children') or {}))
        folders = episode['inputs']
        self.folders = {'inbox': folders['input_folder'], 'outbox': folders['output_folder']}

    def path(self, relative):
        folder, _, rest = relative.partition('/')
        return self.folders[folder] + '/' + rest

    def execute(self, checkpoint):
        self.run(checkpoint['recipe'])
        if not checkpoint.get('modal_end'):
            self.ui.park()
        self.ui.settle()

    def run(self, recipe):
        for step in recipe:
            getattr(self, 'op_' + step['op'].replace('-', '_'))(step)

    # -- generic ------------------------------------------------------------------------------------------------
    def op_menu(self, step):
        self.ui.menu(*step['path'])
        self.ui.wait(step.get('wait', .4))

    def op_account_type(self, step):
        self.ui.menu('Accounts', 'Change Account Type…')
        self.op_cell({'window':'Change Account Type','name':step['name']})
        self.op_button({'window':'Change Account Type','name':'OK'})
        self.op_cell({'window':'Change Account Type','name':step['type']})
        self.op_close({'window':'Change Account Type'})

    def op_account_delete(self, step):
        self.ui.menu('Accounts','Delete Account…')
        self.op_cell({'window':'Accounts','name':step['name']})
        self.op_close({'window':'Accounts'})
        self.op_alert({'button':'Yes' if step.get('confirm',True) else 'No'})
        self.ui.click(100,NAV_TOP)
        self.ui.wait(.5)

    def op_reconcile(self, step):
        self.op_button_described({'window':'Money Manager Ex','text':'Reconcile'})
        window = self.ui.wait_window("Reconcile account 'Statement'")
        window.fill('Statement ending balance',step['ending'],commit=True)
        if step.get('all'):
            window.button('All (un)cleared')
        for side,index in step.get('rows',[]):
            root = next(n for n in self.ui.tree()['nodes'] if n['name']==window.title and n['role'] in desktop.DIALOG_ROLES)
            x,y,_,_ = root['bounds']
            self.ui.click(x+(34 if side=='withdrawal' else 413),y+141+23*index)
        window.close(step['button'])
        self.ui.wait(.5)

    def op_date_range(self, step):
        self.ui.menu('Tools','Date Range Manager…')
        manager = self.ui.wait_window('Manage checking date ranges')
        table=manager.find('table')
        self.ui.click(table['bounds'][0]+60,table['bounds'][1]+30)
        self.ui.press('Home')
        if step['action']!='create':
            self.op_cell({'window':manager.title,'name':step['old']})
        manager.button({'create':'New','edit':'Edit','delete':'Delete'}[step['action']])
        if step['action']=='delete':
            self.op_alert({'button':'Yes'})
        else:
            window=self.ui.wait_window('New date range' if step['action']=='create' else 'Edit date range')
            window.fill('Name',step['name'])
            window.fill('Range code',step['code'],commit=True)
            window.close('Save')
        manager.close('Save')
        self.ui.wait(.5)

    def op_account_range(self, step):
        window=self.ui.wait_window('Money Manager Ex')
        buttons=[n for n in window.nodes() if n['role']=='push button' and n['bounds'][1]==160 and n['bounds'][0]<470]
        self.ui.call({'op':'click','target':buttons[0]['ref']})
        self.ui.click_menu_item(step['name'])
        self.ui.wait(.6)

    def op_menu_item(self, step):
        self.ui.click_menu_item(step['name'])
        self.ui.wait(step.get('wait', .4))

    def op_drag(self, step):
        self.ui.call({key: value for key, value in step.items() if key != 'wait'})
        self.ui.wait(step.get('wait', .4))

    def op_scroll(self, step):
        self.ui.call({key: value for key, value in step.items() if key != 'wait'})
        self.ui.wait(step.get('wait', .4))

    def op_press(self, step):
        self.ui.press(step['key'])
        self.ui.wait(step.get('wait', .3))

    def op_wait(self, step):
        self.ui.wait(step['seconds'])

    def op_click(self, step):
        self.ui.click(step['x'], step['y'], button=step.get('button'), count=step.get('count'), modifiers=step.get('modifiers'))
        self.ui.wait(step.get('wait', .3))

    def op_alert(self, step):
        """Answer a message box with a named button."""
        window = self.ui.wait_alert(step.get('timeout', 10.0))
        window.button(step.get('button', 'OK'))
        self.ui.wait(.4)

    def op_button(self, step):
        window = self.ui.wait_window(step['window'])
        window.button(step['name'], step.get('nth', 0))
        self.ui.wait(step.get('wait', .4))

    def op_file_dialog(self, step):
        self.ui.file_dialog(self.path(step['path']))
        self.ui.wait(step.get('wait', .5))

    # -- dialogs in general -------------------------------------------------------------------------------------
    def op_open(self, step):
        """A menu path that opens a window."""
        self.ui.menu(*step['path'])
        self.ui.wait_window(step['window'])

    def op_fill(self, step):
        window = self.ui.wait_window(step['window'])
        if step.get('role'):
            node = window.field(step['label'], roles=(step['role'],), below=step.get('below', False))
            self.ui.call({'op': 'fill', 'target': node['ref'], 'value': str(step['value'])})
            if step.get('commit'):
                self.ui.press('Tab')
        else:
            window.fill(step['label'], step['value'], below=step.get('below', False), commit=step.get('commit', False))
        self.ui.wait(.1)
        if step.get('entry'):
            self.ui.press('Tab')
            self.ui.wait(.2)

    def op_fill_described(self, step):
        """The text field whose tooltip contains a word."""
        window = self.ui.wait_window(step['window'])
        nodes = [n for n in window.nodes() if n['role'] in ('text', 'spin button') and step['text'].casefold() in (n.get('description') or '').casefold()]
        self.ui.call({'op': 'fill', 'target': nodes[step.get('nth', 0)]['ref'], 'value': step['value']})
        self.ui.wait(.1)
        if step.get('commit'):
            self.ui.press('Tab')
            self.ui.wait(.2)

    def op_fill_text(self, step):
        """The nth editable text field of a window."""
        window = self.ui.wait_window(step['window'])
        nodes = [n for n in window.nodes() if n['role'] == 'text' and 'editable' in n.get('states', ()) and 'disabled' not in n.get('states', ())]
        self.ui.call({'op': 'fill', 'target': nodes[step.get('nth', 0)]['ref'], 'value': step['value']})
        self.ui.wait(.1)
        if step.get('commit'):
            self.ui.press('Tab')
            self.ui.wait(.2)

    def op_time(self, step):
        import re
        window = self.ui.wait_window(step['window'])
        node = next(n for n in window.nodes() if n['role'] == 'text' and
                    re.fullmatch(r'\d\d:\d\d:\d\d', n.get('text', '')))
        x, y, _, height = node['bounds']
        for offset, value in zip((8, 32, 57), step['value'].split(':')):
            self.ui.click(x + offset, y + height // 2)
            self.ui.type(value)
            self.ui.wait(.15)
        self.ui.press('Tab')
        self.ui.wait(.3)

    def op_choose(self, step):
        window = self.ui.wait_window(step['window'])
        if 'label' in step:
            window.choose(step['label'], step['value'], below=step.get('below', False))
        else:
            combos = [n for n in window.nodes() if n['role'] == 'combo box' and 'disabled' not in n.get('states', ())]
            window.pick(combos[step.get('nth', 0)], step['value'])

    def op_check(self, step):
        window = self.ui.wait_window(step['window'])
        if 'label' in step:
            node = window.field(step['label'], roles=('check box',))
            self.ui.call({'op': 'check', 'target': node['ref'], 'checked': step.get('value', True)})
        else:
            window.check(step['name'], step.get('value', True), step.get('nth', 0))
        self.ui.wait(.2)

    def op_radio(self, step):
        window = self.ui.wait_window(step['window'])
        window.radio(step['name'])
        self.ui.wait(.2)

    def op_tab(self, step):
        self.ui.wait_window(step['window']).tab(step['name'])

    def op_cell(self, step):
        """Click a table cell of a window by its text."""
        window = self.ui.wait_window(step['window'])
        node = window.find('table cell', step['name'], step.get('nth', 0))
        request = {'op': 'click', 'target': node['ref']}
        if step.get('count'):
            request['click_count'] = step['count']
        if step.get('mouse'):
            request['button'] = step['mouse']
        self.ui.call(request)
        self.ui.wait(step.get('wait', .3))

    def op_search(self, step):
        window = self.ui.wait_window(step['window'])
        node = window.find('text', 'Search')
        self.ui.call({'op': 'fill', 'target': node['ref'], 'value': step['value']})
        self.ui.wait(.5)

    def op_category_row(self, step):
        window = self.ui.wait_window('Category Manager')
        path = step.get('path', '')
        self.op_search({'window': 'Category Manager', 'value': path})
        pane = window.find('scroll pane')
        x, y, _, _ = pane['bounds']
        depth = path.count(':') + 1 if path else 0
        if path:
            self.ui.click(x + 70, y + 13)
            self.ui.wait(.15)
        self.ui.click(x + 70, y + 13 + 23 * depth)
        self.ui.wait(.3)
        if step.get('menu'):
            self.ui.context_menu(x + 70, y + 13 + 23 * depth, *step['menu'])
            self.ui.wait(.4)

    def op_toggle(self, step):
        window = self.ui.wait_window(step['window'])
        node = window.find(None, step['name'])
        checked = 'checked' in node.get('states', ())
        if 'value' not in step or checked != step['value']:
            window.toggle(step['name'])
        self.ui.wait(.3)

    def op_merge(self, step):
        kind = step['kind']
        self.ui.menu('Tools', 'Merge', kind + '…')
        window = self.ui.wait_window('Merge ' + kind)
        for label, key in (('Source', 'source'), ('Target', 'target')):
            window.fill(label, step[key], below=True, commit=True)
            self.ui.wait(.3)
        if step.get('delete', True):
            node = next(n for n in window.nodes() if n['role'] == 'check box')
            self.ui.call({'op': 'check', 'target': node['ref'], 'checked': True})
        window.button('Merge')
        self.ui.wait_alert().button('OK')
        self.ui.wait(.5)
        window.close('Close')
        self.ui.wait_alert().button('OK')
        self.ui.wait(.5)

    def op_asset_form(self, step):
        window = self.ui.wait_window(step.get('window', 'New Asset'))
        for key, label in (('name', 'Name'), ('date', 'Date'), ('value', 'Initial Value')):
            if key in step:
                window.fill(label, step[key], commit=True)
                self.ui.wait(.2)
        for key, label in (('type', 'Asset Type'), ('change', 'Change in Value')):
            if key in step:
                window.choose(label, step[key])
        if 'rate' in step:
            self.ui.wait(.5)
            window.fill('% Rate', step['rate'], commit=True)
        if 'notes' in step:
            self.notes_field(window, step['notes'])
        window.button('OK')
        if step.get('window', 'New Asset') == 'New Asset':
            self.ui.wait_alert().button(step.get('account', 'No'))
            if step.get('account') == 'Yes':
                self.ui.wait_window('Add Asset Transaction').close('Cancel')
        self.ui.wait_gone(window.title)
        self.ui.wait(.5)

    def op_share_form(self, step):
        window = self.ui.wait_window('Add Share Transaction')
        if step.get('type'):
            window.choose('Type', step['type'])
        for key, label in (('shares', 'Share Number'), ('price', 'Share Price'), ('commission', 'Deductible Comm.'),
                           ('date', 'Date'), ('number', 'Number')):
            if key in step:
                window.fill(label, step[key], commit=True)
        if step.get('payee'):
            window.button('Select Payee')
            payees = self.ui.wait_window('Payee Manager')
            payees.fill('Search', step['payee'])
            self.ui.wait(.4)
            x, y = self.list_row(payees, 0)
            self.ui.click(x, y, count=2)
            self.ui.wait(.3)
        if step.get('category'):
            self.entry(window, 'Category', step['category'])
        if step.get('notes'):
            node = next(n for n in window.nodes() if n['role'] == 'text' and
                        'Specify any text notes' in n.get('description', ''))
            self.ui.call({'op': 'fill', 'target': node['ref'], 'value': step['notes']})
        window.close('OK')
        self.ui.wait(.5)

    def op_exchange_export(self, step):
        kind = step['format']
        title = {'CSV': 'CSV', 'JSON': 'JSON', 'QIF': 'QIF'}[kind]
        self.ui.menu('File', 'Export as', ('MMEX CSV' if kind == 'CSV' else kind) + ' File…')
        window = self.ui.wait_window('Export as ' + title + ' file')
        if step.get('categories'):
            window.check('Categories', True)
        for key, label in (('from', 'From Date'), ('to', 'To Date')):
            if key in step:
                window.check(label, True)
                window.fill(label, step[key], commit=True)
        window.button('Browse…')
        self.ui.file_dialog(self.path(step['path']))
        window.button('OK')
        self.ui.wait_alert()

    def op_xml_export(self, step):
        self.ui.menu('File', 'Export as', 'XML File…')
        window = self.ui.wait_window('Export as XML file')
        window.button('Browse…')
        self.ui.file_dialog(self.path(step['path']))
        window.choose('Account', step['account'])
        window.button('MMEX format')
        window.check('Export column titles', True)
        window.button('Export')
        self.ui.wait_alert()

    def op_qif_import(self, step):
        self.ui.menu('File', 'Import from', 'QIF File…')
        window = self.ui.wait_window('Import from QIF file')
        window.button('Browse…')
        self.ui.file_dialog(self.path(step['path']))
        self.ui.wait(.7)
        window.check('Account', True)
        window.choose('Account', step.get('account', 'Pocket Cash'))
        if step.get('duplicates'):
            window.check('Duplicates', True)
        window.button('OK')
        self.ui.wait_alert(timeout=30).button('Yes')
        self.ui.wait(.5)
        if self.ui.has_alert():
            self.ui.wait_alert().button('OK')
        if any('Import from QIF file' in title for title in self.ui.window_titles()):
            window.close('Close')
        self.ui.wait(.5)
        self.op_scroll({'op': 'scroll', 'x': 850, 'y': 888, 'delta_x': -3000})
        self.op_scroll({'op': 'scroll', 'x': 850, 'y': 888, 'delta_x': 400})

    def op_settings_tab(self, step):
        names = ['General', 'View', 'Dashboard', 'Transactions', 'Attachments', 'Network', 'Other']
        root = next(n for n in self.ui.tree()['nodes'] if n['name'] == 'Settings' and n['role'] in desktop.DIALOG_ROLES)
        x, y, _, _ = root['bounds']
        self.ui.click(x + 57, y + 87 + 67 * names.index(step['name']))
        self.ui.wait(.4)

    def op_manager_menu(self, step):
        window = self.ui.wait_window(step['window'])
        table = window.find('table')
        x, y, width, _ = table['bounds']
        self.ui.context_menu(x + width // 2, y + 36 + 23 * step.get('index', 0), step['name'])
        self.ui.wait(.4)

    def op_custom_fields(self, step):
        window = self.ui.wait_window(step.get('window', 'Edit Transaction'))
        if not any(n['role'] == 'panel' and n['name'] == 'Custom fields' for n in window.nodes()):
            self.op_button_described({'window': window.title, 'text': 'Show/Hide custom'})
        for name, value in step.get('values', {}).items():
            window.check(name, True)
            window.fill(name, value, commit=True)
        for name, value in step.get('choices', {}).items():
            window.check(name, True)
            window.choose(name, value)
        for name, value in step.get('booleans', {}).items():
            window.check(name, True)
            window.radio('True' if value else 'False')
        for name,value in step.get('times',{}).items():
            window.check(name,True)
            self.op_time({'window':window.title,'value':value})
        for name,values in step.get('multiple',{}).items():
            window.check(name,True)
            button=window.field(name,roles=('push button',))
            self.ui.call({'op':'click','target':button['ref']})
            chooser=self.ui.wait_window('Multi Choice')
            for value in values:
                cell=chooser.find('table cell',value)
                self.ui.click(cell['bounds'][0]-14,cell['bounds'][1]+10)
            chooser.close()

    def op_ofx_import(self, step):
        self.ui.menu('File', 'Import from', 'OFX File…')
        window = self.ui.wait_window('Import OFX file')
        window.button('Browse…')
        self.ui.file_dialog(self.path(step['path']))
        self.ui.wait(.4)
        self.ui.press('alt+i')
        for payee in ('Cafe Luna', 'Employer'):
            confirmation = self.ui.wait_window('Payee Confirmation Required')
            confirmation.choose('Select Existing Payee', payee, below=True)
            confirmation.button('OK')
            self.ui.wait(.6)
        self.ui.wait_window('OFX Import Summary', timeout=30)

    def op_csv_import(self, step):
        self.ui.menu('File', 'Import from', step.get('format', 'CSV') + ' File…')
        window = self.ui.wait_window('Import from ' + step.get('format', 'CSV') + ' file')
        window.button('Browse…')
        self.ui.file_dialog(self.path(step['path']))
        window.choose('Account', step.get('account', 'Pocket Cash'))
        if step.get('preset'):
            window.choose('Preset',step['preset'])
        if step.get('delimiter'):
            window.fill('CSV Delimiter', step['delimiter'], commit=True)
        if step.get('date_format'):
            window.choose('Date Format', step['date_format'])
        if step.get('decimal'):
            window.choose('Decimal Char', step['decimal'])
        if step.get('direction'):
            window.choose('Amount', step['direction'])
        for name in step.get('fields',[]):
            table = window.find('table')
            x,y,width,_ = table['bounds']
            self.ui.click(x+60,y+15)
            self.ui.press('Home')
            for _ in range(45):
                candidates=[n for n in window.nodes() if n['role']=='table cell' and n['name']==name and x<=n['bounds'][0]<x+width]
                if candidates:
                    break
                self.ui.press('Down')
            else:
                raise desktop.UIError('import mapping field not found: '+name)
            self.ui.call({'op':'click','target':candidates[0]['ref']})
            window.button('Add')
            self.ui.wait(.15)
        for key, label in (('skip_first', 'From start'), ('skip_last', 'From end')):
            if step.get(key):
                node = window.field(label, roles=('spin button',))
                self.ui.call({'op': 'fill', 'target': node['ref'], 'value': str(step[key])})
                self.ui.press('Tab')
        if step.get('save_preset'):
            self.op_button_described({'window':window.title,'text':'Save current settings as a Preset'})
            self.op_text_prompt({'window':'Save Preset','value':step['save_preset']})
        window.button('Import')
        self.ui.wait_alert(timeout=30).button(step.get('confirm', 'OK'))
        self.ui.wait(.4)
        window.close('Close')
        self.ui.wait(.5)
        self.op_scroll({'op': 'scroll', 'x': 850, 'y': 888, 'delta_x': -3000})
        self.op_scroll({'op': 'scroll', 'x': 850, 'y': 888, 'delta_x': 400})

    def list_row(self, window, index):
        """Screen position of a row of the drawn list of a dialog: below the header of its first scroll pane."""
        pane = window.find('scroll pane')
        x, y, w, _ = pane['bounds']
        return x + w // 3, y + 25 + 11 + 23 * index

    def op_list_row(self, step):
        window = self.ui.wait_window(step['window'])
        x, y = self.list_row(window, step.get('index', 0))
        self.ui.click(x, y, count=step.get('count'))
        self.ui.wait(.3)

    def op_list_menu(self, step):
        """A command of the context menu of a drawn list in a dialog."""
        window = self.ui.wait_window(step['window'])
        x, y = self.list_row(window, step.get('index', 0))
        self.ui.click(x, y)
        self.ui.wait(.2)
        self.ui.context_menu(x, y, *step['path'])
        self.ui.wait(.4)

    def op_close(self, step):
        """Press a button that ends a window and wait until it is gone."""
        window = self.ui.wait_window(step['window'])
        if step['window'] == 'Settings' and step.get('button', 'OK') == 'OK':
            window.button('OK')
            self.ui.wait(.5)
            if self.ui.has_alert():
                self.ui.wait_alert().button('OK')
            self.ui.wait_gone('Settings')
            return
        window.close(step.get('button', 'OK'))
        self.ui.wait(step.get('wait', .5))

    def op_text_prompt(self, step):
        """Answer a dialog that asks for one line of text."""
        window = self.ui.wait_window(step['window'])
        nodes = [n for n in window.nodes() if n['role'] in ('text', 'password text') and 'editable' in n.get('states', ())]
        self.ui.call({'op': 'fill', 'target': nodes[0]['ref'], 'value': step['value']})
        self.ui.wait(.1)
        if step.get('same_title_next'):
            window.button(step.get('button','OK'))
        else:
            window.close(step.get('button', 'OK'))
        self.ui.wait(.4)

    def op_button_described(self, step):
        """Click a button by a word of its tooltip."""
        window = self.ui.wait_window(step['window'])
        nodes = [n for n in window.nodes() if n['role'] in ('push button', 'toggle button') and step['text'].casefold() in (n.get('description') or '').casefold()]
        self.ui.call({'op': 'click', 'target': nodes[step.get('nth', 0)]['ref']})
        self.ui.wait(step.get('wait', .5))

    # -- navigator ------------------------------------------------------------------------------------------------
    def nav_rows(self):
        rows = []
        for name in NAV_FIXED_HEAD + self.sections + NAV_FIXED_TAIL:
            rows.append(name)
            if self.expanded.get(name):
                rows.extend(name + '/' + child for child in self.children.get(name, ()))
        return rows

    def nav_y(self, name):
        return NAV_TOP + NAV_ROW * self.nav_rows().index(name)

    def op_nav(self, step):
        """Select a navigator row, expanding its section first: path ['Bank Accounts', 'Everyday Checking']."""
        path = step['path']
        if len(path) == 2 and not self.expanded.get(path[0]):
            self.ui.click(11, self.nav_y(path[0]))
            self.expanded[path[0]] = True
            self.ui.wait(.3)
        self.ui.click(100, self.nav_y('/'.join(path)))
        self.ui.wait(step.get('wait', 1.0))

    def op_report(self, step):
        """Open one built-in report from a fresh navigator, using normal tree keys."""
        roots = ['Cash Flow', 'Categories', 'Forecast Report', 'Income vs. Expenses',
                 'My Usage', 'Payees', 'Summary of Accounts', 'Budgets', 'Stocks Report']
        children = {'Cash Flow': ['Daily', 'Monthly', 'Transactions'],
                    'Categories': ['Monthly', 'Summary', 'Where the Money Goes', 'Where the Money Comes From'],
                    'Income vs. Expenses': ['Monthly'], 'Summary of Accounts': ['Monthly', 'Yearly'],
                    'Budgets': ['Budget Performance', 'Budget Category Summary'], 'Stocks Report': ['Summary']}
        path = step['path']
        self.ui.click(100, self.nav_y('Reports'))
        self.ui.press('Left')
        self.ui.click(100,self.nav_y('Reports'))
        self.ui.press('Right')
        for _ in range(roots.index(path[0]) + 1):
            self.ui.press('Down')
        if len(path) > 1:
            self.ui.press('Left')
            self.ui.click(100,self.nav_y('Reports')+(roots.index(path[0])+1)*NAV_ROW)
            self.ui.press('Right')
            for _ in range(children[path[0]].index(path[1]) + 1):
                self.ui.press('Down')
        self.ui.wait(1.5)

    def op_report_parameters(self, step):
        window=self.ui.wait_window('Money Manager Ex')
        if step.get('period'):
            button=next(n for n in window.nodes() if n['role']=='push button' and n['bounds'][1]==93)
            self.ui.call({'op':'click','target':button['ref']})
            if step.get('more_periods'):
                self.ui.call({'op':'click','target':{'role':'menu','name':'More date ranges…'}})
                self.ui.press('Right')
                self.ui.wait(.3)
            self.ui.click_menu_item(step['period'])
        if step.get('accounts') and window.field('Accounts',roles=('combo box',))['name'] != 'Specific Accounts…':
            window.choose('Accounts','Specific Accounts…')
            chooser=self.ui.wait_window(step.get('dialog','Categories Summary'))
            for name in step['accounts']:
                cell=chooser.find('table cell',name)
                self.ui.click(cell['bounds'][0]-14,cell['bounds'][1]+10)
            chooser.close()
        if step.get('group'):
            window.choose('Accounts',step['group'])
        for i,value in enumerate(step.get('dates',[])):
            nodes=[n for n in window.nodes() if n['role']=='text' and 'editable' in n.get('states',[])]
            self.ui.call({'op':'fill','target':nodes[i]['ref'],'value':value})
            self.ui.press('Tab')
            self.ui.wait(.3)
        self.ui.wait(.7)

    def op_export_html(self, step):
        self.ui.menu('File', 'Export as', 'HTML File…')
        self.ui.file_dialog(self.path(step.get('path', 'outbox/report.html')))
        self.ui.wait(.5)

    def op_row(self, step):
        """Click a row of the transaction list by its position from the top."""
        self.ui.click(600, LIST_TOP + LIST_ROW * step['index'], count=step.get('count'), modifiers=step.get('modifiers'))
        self.ui.wait(step.get('wait', .4))

    # -- accounts -------------------------------------------------------------------------------------------------
    def op_new_account(self, step):
        if not step.get('wizard_open'):
            self.ui.menu('Accounts', 'New Account…')
        wizard = self.ui.wait_window('Add Account Wizard')
        wizard.button('Next >')
        self.ui.wait(.4)
        if step.get('type', 'Checking') != 'Checking':
            combo = wizard.find('combo box')
            wizard.pick(combo, step['type'])
        wizard.button('Next >')
        self.ui.wait(.4)
        wizard.fill('Name of the Account', step['name'], below=True)
        wizard.button('Finish')
        self.ui.wait(1.0)

    def op_new_database(self, step):
        self.ui.call({'op': 'click', 'target': {'role': 'push button', 'name': 'New Database'}})
        self.ui.file_dialog(self.path(step['path']))
        wizard = self.ui.wait_window('New Database Wizard')
        wizard.button('Next >')
        self.ui.wait(.3)
        wizard.button('Set Currency')
        self.choose_currency(step.get('currency', 'USD'))
        wizard.fill('User Name', step.get('user', 'River Household'))
        wizard.button('Finish')
        self.ui.wait_window('Add Account Wizard')

    def op_save_encrypted(self, step):
        self.ui.menu('File', 'Save Database As…')
        window = self.ui.wait_window('Save database file as')
        selector = next(n for n in window.nodes() if n['role'] == 'combo box' and
                        'Select which types' in n.get('description', ''))
        window.pick(selector, 'Encrypted MMEX Database (*.emb)')
        self.ui.file_dialog(self.path(step['path']))
        self.op_text_prompt({'window': 'MMEX: Encrypted Database', 'value': step['password']})
        self.ui.wait(1)

    def edit_account_fields(self, window, step):
        for label, key in (('Account Name:', 'name'), ('Initial Balance:', 'balance'), ('Opening Date:', 'opened')):
            if key in step:
                window.fill(label, step[key], commit=True)
        if 'status' in step:
            window.choose('Account Status:', step['status'])
        if 'favorite' in step:
            window.check('Favorite Account', step['favorite'])
        if 'currency' in step:
            window.button(window.field('Currency:', roles=('push button',))['name'])
            self.choose_currency(step['currency'])
        if 'notes' in step:
            window.tab('Notes')
            nodes = [n for n in window.nodes() if n['role'] == 'text' and 'notes' in (n.get('description') or '').casefold()]
            self.ui.call({'op': 'fill', 'target': nodes[0]['ref'], 'value': step['notes']})
        tabs = {'Other': (('number', 'Account Number:'), ('card_number', 'Card Number:'), ('held_at', 'Held At:'), ('website', 'Website:'),
                          ('contact', 'Contact:'), ('access', 'Access Info:')),
                'Statement': (('statement_date', 'Reconciled Date:'), ('minimum_balance', 'Minimum Bal:')),
                'Credit': (('credit_limit', 'Credit Limit:'), ('interest', 'Interest Rate:'), ('due_date', 'Payment Due Date:'),
                           ('minimum_payment', 'Minimum Payment:'))}
        for tab, fields in tabs.items():
            if any(key in step for key, _ in fields) or (tab == 'Statement' and 'locked' in step):
                window.tab(tab)
                if tab == 'Statement' and 'locked' in step:
                    window.check('Locked', step['locked'])
                for key, label in fields:
                    if key in step:
                        window.fill(label, step[key], commit=True)

    def choose_currency(self, symbol):
        dialog = self.ui.wait_window('Currency Manager')
        dialog.fill('Search', symbol)
        self.ui.wait(.5)
        cell = dialog.find('table cell', symbol)
        self.ui.call({'op': 'click', 'target': cell['ref']})
        self.ui.wait(.3)
        dialog.button('Select')
        self.ui.wait(.5)

    def op_account_dialog(self, step):
        """Fill the Edit Account dialog that is open and confirm it."""
        window = self.ui.wait_window('Edit Account')
        self.edit_account_fields(window, step)
        if step.get('tab'):
            window.tab(step['tab'])
        if step.get('keep_open'):
            return
        window.close('OK')
        self.ui.wait(1.0)

    def op_edit_account(self, step):
        self.ui.menu('Accounts', 'Edit Account…')
        chooser = self.ui.wait_window('Accounts')
        cell = chooser.find(None, step['account'])
        self.ui.call({'op': 'click', 'target': cell['ref']})
        self.ui.wait(.2)
        chooser.button('OK')
        self.op_account_dialog(step)

    def op_nav_deleted(self, step):
        """The deleted transactions row sits above the help row while deleted transactions exist."""
        rows = self.nav_rows()
        rows.insert(rows.index('Help'), 'Deleted Transactions')
        self.ui.click(100, NAV_TOP + NAV_ROW * rows.index('Deleted Transactions'))
        self.ui.wait(1.0)

    # -- transactions ---------------------------------------------------------------------------------------------
    def entry(self, window, label, value):
        """A text field with an auto-completion list: the first Tab closes the list."""
        node = window.field(label)
        self.ui.call({'op': 'fill', 'target': node['ref'], 'value': value})
        self.ui.wait(.2)
        self.ui.press('Tab')
        self.ui.wait(.2)

    def date_field(self, window, label, value):
        node = window.field(label)
        self.ui.call({'op': 'fill', 'target': node['ref'], 'value': value})
        self.ui.wait(.1)
        self.ui.press('Tab')
        self.ui.wait(.2)

    def notes_field(self, window, value):
        nodes = [n for n in window.nodes() if n['role'] == 'text' and 'notes' in (n.get('description') or '').casefold()]
        self.ui.call({'op': 'fill', 'target': nodes[0]['ref'], 'value': value})
        self.ui.wait(.1)

    def tags_field(self, window, names):
        label = window.find('label', 'Tags')
        x, y, _, h = label['bounds']
        arrow = window.field('Tags', roles=('push button',))
        self.ui.click(arrow['bounds'][0] - 120, y + h // 2)
        self.ui.wait(.2)
        self.ui.press('Control+a')
        self.ui.press('BackSpace')
        for name in names:
            self.ui.type(name + ' ')
            self.ui.wait(.2)
        self.ui.press('Tab')
        self.ui.wait(.2)

    def fill_transaction(self, window, step):
        kind = step.get('type')
        if kind:
            window.pick(window.field('Type', roles=('combo box',)), kind)
        if 'date' in step:
            self.date_field(window, 'Date', step['date'])
        if 'amount' in step:
            window.fill('Amount', step['amount'])
            self.ui.press('Tab')
            self.ui.wait(.2)
        if 'account' in step:
            self.entry(window, 'From' if kind == 'Transfer' else 'Account', step['account'])
        if 'to_account' in step:
            self.entry(window, 'To', step['to_account'])
        if step.get('advanced'):
            window.check('Advanced', True)
            self.ui.wait(.3)
            first = window.field('Amount')
            amounts = [n for n in window.nodes() if n['role'] == 'text' and n['bounds'][1] == first['bounds'][1]]
            self.ui.call({'op': 'fill', 'target': max(amounts, key=lambda n: n['bounds'][0])['ref'], 'value': step['advanced']})
            self.ui.press('Tab')
            self.ui.wait(.2)
        if 'payee' in step:
            self.entry(window, 'From' if kind == 'Deposit' else 'Payee', step['payee'])
        if 'category' in step:
            self.entry(window, 'Category', step['category'])
        if 'tags' in step:
            self.tags_field(window, step['tags'])
        if 'status' in step:
            window.choose('Status', step['status'])
        if 'number' in step:
            window.fill('Number', step['number'])
        if 'notes' in step:
            self.notes_field(window, step['notes'])

    def finish_transaction(self, window, step, button):
        window.button(button)
        self.ui.wait(.5)
        for answer in step.get('confirm', ()):
            self.ui.wait_alert().button(answer)
            self.ui.wait(.4)
        self.ui.wait_gone(window.title)
        self.ui.wait(.6)

    def transaction_dialog(self):
        for title in ('New Transaction', 'Edit Transaction', 'Duplicate Transaction', 'Enter Transaction'):
            if any(title in name for name in self.ui.window_titles()):
                return self.ui.wait_window(title)
        return self.ui.wait_window('Transaction')

    def op_new_transaction(self, step):
        self.ui.press('F9')
        window = self.ui.wait_window('New Transaction')
        self.fill_transaction(window, step)
        if step.get('button', 'Save'):
            self.finish_transaction(window, step, step.get('button', 'Save'))

    def op_transaction_form(self, step):
        """Fill the transaction dialog that is open."""
        window = self.transaction_dialog()
        self.fill_transaction(window, step)
        if step.get('button'):
            self.finish_transaction(window, step, step['button'])

    def op_edit_row(self, step):
        self.op_row({'index': step['index']})
        self.ui.press('Return')
        window = self.ui.wait_window('Edit Transaction')
        self.fill_transaction(window, step)
        self.finish_transaction(window, step, step.get('button', 'Save'))

    def op_row_menu(self, step):
        """A command of the context menu of a list row."""
        self.ui.context_menu(step.get('x', 600), LIST_TOP + LIST_ROW * step['index'], *step['path'])
        self.ui.wait(step.get('wait', .6))

    def op_splits(self, step):
        """Fill the split dialog of the open transaction dialog: rows of [category, amount, tags, notes]."""
        window = self.transaction_dialog()
        button = window.field('Category', roles=('push button',))
        self.ui.call({'op': 'click', 'target': button['ref']})
        dialog = self.ui.wait_window('Split Transaction')
        for index, item in enumerate(step['rows']):
            nodes = [n for n in dialog.nodes() if n['role'] == 'text' and 'disabled' not in n.get('states', ())]
            if index * 2 + 1 >= len(nodes):
                dialog.button('Add Split')
                self.ui.wait(.3)
                nodes = [n for n in dialog.nodes() if n['role'] == 'text' and 'disabled' not in n.get('states', ())]
            self.ui.call({'op': 'fill', 'target': nodes[index * 2]['ref'], 'value': item[0]})
            self.ui.wait(.2)
            self.ui.press('Tab')
            self.ui.wait(.2)
            nodes = [n for n in dialog.nodes() if n['role'] == 'text' and 'disabled' not in n.get('states', ())]
            self.ui.call({'op': 'fill', 'target': nodes[index * 2 + 1]['ref'], 'value': item[1]})
            self.ui.press('Tab')
            self.ui.wait(.2)
        dialog.close('OK')
        self.ui.wait(.4)


    # -- payees -------------------------------------------------------------------------------------------------
    def op_payee_pattern(self, step):
        """The first cell of the match pattern grid of the payee dialog."""
        window = self.ui.wait_window('Edit Payee')
        label = window.find('label', 'Match Patterns\non Import')
        panel = [n for n in window.nodes() if n['role'] == 'panel' and 'match this payee' in (n.get('description') or '')][0]
        x, y, w, h = panel['bounds']
        self.ui.click(x + w // 2, y + h // 2, count=2)
        self.ui.wait(.3)
        self.ui.type(step['value'])
        self.ui.press('Return')
        self.ui.wait(.3)

    # -- bulk edit ------------------------------------------------------------------------------------------------
    def op_bulk_edit(self, step):
        window = self.ui.wait_window('Multi Transactions Update')
        if 'payee' in step:
            window.check('Payee', True)
            self.ui.wait(.2)
            node = window.field('Payee')
            self.ui.call({'op': 'fill', 'target': node['ref'], 'value': step['payee']})
            self.ui.press('Tab')
            self.ui.wait(.2)
        if 'append_notes' in step:
            window.check('Notes', True)
            self.ui.wait(.2)
            window.check('Append', True, nth=self.append_index(window))
            nodes = [n for n in window.nodes() if n['role'] == 'text' and 'editable' in n.get('states', ()) and 'disabled' not in n.get('states', ())]
            self.ui.call({'op': 'fill', 'target': nodes[-1]['ref'], 'value': step['append_notes']})
        window.close('OK')
        self.ui.wait(.8)

    @staticmethod
    def append_index(window):
        return len([n for n in window.nodes() if n['role'] == 'check box' and n['name'] == 'Append']) - 1
