'''Pinned-standard GUI implementation of the reviewed functional goals, through the black-box runtime (record only).

Recipes drive only the installed standard answer during record, with the same runtime GUI operations that the evaluator and the
model use; the evidence is captured by the evaluator observation function. The helpers of ui.py locate controls by their visible
accessible names. Their routes belong to the pinned standard only and are never a candidate requirement.
'''
import json
import time
from types import SimpleNamespace

from . import ui

BUTTONS = {1: 'left', 2: 'middle', 3: 'right'}
# A point of the index pane below its entries: resting the pointer there keeps tooltips and hover highlights out of the evidence.
PARK = (100, 800)


class BrokerUI:
    '''The desktop interface that ui.py expects, on top of the runtime GUI operations.'''

    def __init__(self, broker):
        self.broker = broker

    def call(self, request):
        return self.broker.call(request)

    def observe(self):
        observation = self.call({'op': 'observe', 'tree': True})
        nodes = []
        for node in observation['nodes']:
            item = dict(node)
            x, y, w, h = item.pop('bounds')
            item['bounds'] = {'x': x, 'y': y, 'width': w, 'height': h}
            if 'visible' in item:
                vx, vy, vw, vh = item.pop('visible')
                item['visible_bounds'] = {'x': vx, 'y': vy, 'width': vw, 'height': vh}
            states = set(item.get('states', ())) | {'showing', 'visible'}
            if 'disabled' not in states:
                states |= {'enabled', 'sensitive'}
            item['states'] = sorted(states)
            nodes.append(item)
        width, height = observation['screen']
        return {'nodes': nodes, 'viewport': {'width': width, 'height': height}}

    def click(self, target=None, *, x=None, y=None, button=1, count=1):
        request = {'op': 'click', **({'target': target} if target is not None else {'x': x, 'y': y})}
        if button != 1:
            request['button'] = BUTTONS[button]
        if count != 1:
            request['click_count'] = count
        return self.call(request)

    def fill(self, target, value):
        return self.call({'op': 'fill', 'target': target, 'value': str(value)})

    def press(self, key):
        return self.call({'op': 'press', 'key': key})

    def type(self, value, target=None):
        return self.call({'op': 'type', 'value': str(value), **({'target': target} if target is not None else {})})

    def check(self, target, value=True):
        return self.call({'op': 'check', 'target': target, 'checked': bool(value)})

    def hover(self, target=None, *, x=None, y=None, seconds=.7):
        request = {'op': 'move', 'seconds': min(3.0, float(seconds))}
        request.update({'target': target} if target is not None else {'x': x, 'y': y})
        return self.call(request)

    def wait(self, seconds=.2):
        return self.call({'op': 'wait', 'seconds': min(5.0, float(seconds))})

    def windows(self):
        return self.call({'op': 'windows'})['windows']

    def focus_window(self, window):
        return self.call({'op': 'focus_window', 'window': window})


def reference(ctx):
    if 'reference' not in ctx.state:
        ctx.state['reference'] = Reference(ctx)
    return ctx.state['reference']


def begin(ctx, checkpoint):
    '''Before the reference-before evidence: the episode preparation, or a settled restart.'''
    driver = reference(ctx)
    if checkpoint['id'] == ctx.episode['checkpoints'][0]['id']:
        driver.prepare()
    elif checkpoint.get('lifecycle') == 'restart':
        driver.relaunched()


def execute(ctx, checkpoint):
    reference(ctx).execute(checkpoint)


class Reference:
    def __init__(self, ctx):
        self.episode = ctx.episode
        self.rpc = BrokerUI(ctx.broker)
        self.ctx = SimpleNamespace(ui=self.rpc)
        self.harness = ctx.state['c']

    def path(self, area, name=''):
        '''Absolute path of a file or folder in an exchange folder of this episode runtime.'''
        return self.harness.path(area, name)

    def park(self):
        self.rpc.hover(x=PARK[0], y=PARK[1], seconds=.1)

    def settle(self, timeout=10.0, quiet=1.5):
        '''Wait until the observation stops changing before evidence is captured. While a window is active, a state
        without any focused control counts as not settled yet; activating that window once (an ordinary user action)
        gives focus back.'''
        deadline = time.monotonic() + timeout
        last, since, nudged = None, time.monotonic(), False
        while time.monotonic() < deadline:
            observation = self.rpc.call({'op': 'observe'})
            key = json.dumps(observation, sort_keys=True)
            now = time.monotonic()
            if key != last:
                last, since = key, now
            else:
                active = next((w for w in observation.get('windows', ()) if w.get('active')), None)
                waiting_for_focus = observation.get('focused') is None and active is not None
                if now - since >= quiet and not waiting_for_focus:
                    return
                if waiting_for_focus and now - since >= quiet and not nudged:
                    nudged = True
                    self.rpc.call({'op': 'focus_window', 'window': active['ref']})
                    last = None
                    continue
                if now - since >= 4.0:
                    return
            time.sleep(.25)

    def prepare(self):
        self.run(self.episode.get('prepare', []))
        ui.wait_idle(self.ctx, timeout=30)
        self.park()
        self.settle()

    def execute(self, checkpoint):
        self.run(checkpoint['recipe'])
        if not checkpoint.get('modal_end'):
            ui.wait_idle(self.ctx)
            self.park()
        self.settle()

    def relaunched(self):
        ui.wait_idle(self.ctx, timeout=30)
        self.park()
        self.settle()

    def run(self, recipe):
        for step in recipe:
            getattr(self, 'op_' + step['op'].replace('-', '_'))(step)

    def toggle(self, label, value=True, dialog=False):
        items = ui.nodes(self.ctx)
        scope = ui.dialog_scope(items) if dialog else items
        node = ui.find(scope, (label,), roles={'check box', 'toggle button', 'radio button'})
        if node is None:
            raise AssertionError('visible option ' + repr(label) + ' was not found')
        self.rpc.check({'ref': node['ref']}, value)

    # -- keyboard and menus ------------------------------------------------
    def op_menu(self, step):
        ui.wait_idle(self.ctx)
        ui.menu(self.ctx, *step['path'])

    def op_key(self, step):
        ui.key(self.ctx, step['key'], step.get('pause', .3))

    def op_type(self, step):
        if not step.get('dialog'):
            ui.wait_idle(self.ctx)
        ui.type_text(self.ctx, step['text'], step.get('pause', .3))

    def op_park(self, step):
        # Move the pointer to an empty part of the editor so that tooltips and hover highlights stay out of the evidence.
        self.rpc.hover(x=step.get('x', PARK[0]), y=step.get('y', PARK[1]), seconds=step.get('seconds', .7))
        time.sleep(.5)

    def op_wait(self, step):
        time.sleep(step.get('seconds', .5))

    def op_save(self, step):
        ui.wait_idle(self.ctx)
        ui.key(self.ctx, 'Control+S', .8)
        ui.wait_idle(self.ctx)

    # -- dialogs ------------------------------------------------------------
    def op_dialog(self, step):
        '''Answer the visible dialog with one of the named buttons.'''
        ui.accept(self.ctx, *step['buttons'])
        time.sleep(.3)

    def op_dialog_close(self, step):
        # Press a dialog button until the dialog is gone: a visible completion list may take the first click.
        for _ in range(3):
            ui.accept(self.ctx, *step["buttons"])
            time.sleep(.8)
            if not ui.dialogs(ui.nodes(self.ctx)):
                return
        raise AssertionError("the dialog did not close after repeated clicks on " + repr(step["buttons"]))

    def op_fill(self, step):
        ui.fill(self.ctx, step['label'], step['value'])

    def op_click(self, step):
        '''Click a visible control by its name or text (in the newest dialog unless dialog is false).'''
        ui.click(self.ctx, step['label'], roles=set(step.get('roles', ())), dialog=step.get('dialog', True))
        time.sleep(.4)

    def op_enable_plugin(self, step):
        '''Edit, Preferences, Plugins tab: tick the plugin row of the given name (its Enabled cell is left of the name cell), then OK.'''
        ui.wait_idle(self.ctx)
        ui.menu(self.ctx, 'Edit', 'Preferences')
        ui.wait_for(self.ctx, ui.dialogs, message='the preferences dialog did not appear')
        ui.click(self.ctx, 'Plugins', roles={'page tab'}, dialog=True)
        time.sleep(.6)
        for _ in range(15):
            scope = ui.dialog_scope(ui.nodes(self.ctx))
            cells = [n for n in scope if n.get('role') == 'table cell']
            for i, node in enumerate(cells[1:], 1):
                if ui.norm(node.get('name')) == ui.norm(step['name']):
                    self.rpc.click({'ref': cells[i - 1]['ref']})
                    time.sleep(.6)
                    ui.accept(self.ctx, 'OK')
                    ui.wait_idle(self.ctx, timeout=20)
                    return
            table = next((n for n in scope if n.get('role') == 'table'), None)
            if table is None:
                break
            box = table['bounds']
            self.rpc.call({'op': 'scroll', 'x': box['x'] + box['width'] // 2, 'y': box['y'] + box['height'] // 2, 'delta_y': 300})
            time.sleep(.4)
        raise AssertionError('plugin ' + repr(step['name']) + ' was not found on the Plugins tab')

    def op_fill_field(self, step):
        '''Replace the text of the n-th editable entry of the newest dialog (an entry without a caption).'''
        index = step.get('index', 0)

        def locate(items):
            fields = [n for n in ui.dialog_scope(items) if n.get('role') in ui.FIELD_ROLES and 'editable' in n.get('states', ())]
            return fields[index] if len(fields) > index else None
        node = ui.wait_for(self.ctx, locate, message='the dialog has no editable field ' + str(index))
        self.rpc.fill({'ref': node['ref']}, step['value'])

    def op_check(self, step):
        self.toggle(step['label'], step.get('value', True), dialog=step.get('dialog', True))

    def op_files_dialog(self, step):
        ui.files_dialog(self.ctx, self.path(step['area'], step['name']), *step.get('buttons', ()))
        ui.wait_idle(self.ctx)

    # -- pages ------------------------------------------------------------------
    def op_new_page(self, step):
        ui.wait_idle(self.ctx)
        ui.key(self.ctx, 'Control+Shift+N' if step.get('sub') else 'Control+N', .5)
        ui.wait_for(self.ctx, ui.dialogs, message='the new page dialog did not appear')
        ui.fill(self.ctx, 'Page Name', step['name'])
        ui.accept(self.ctx, 'OK')
        ui.wait_idle(self.ctx)

    def op_jump(self, step):
        ui.wait_idle(self.ctx)
        ui.key(self.ctx, 'Control+J', .5)
        ui.wait_for(self.ctx, ui.dialogs, message='the jump dialog did not appear')
        ui.fill(self.ctx, 'Jump to Page', step['name'])
        ui.accept(self.ctx, 'Jump')
        ui.wait_idle(self.ctx)

    # -- search -----------------------------------------------------------------
    def op_find(self, step):
        ui.wait_idle(self.ctx)
        ui.key(self.ctx, 'Control+F', .5)
        ui.type_text(self.ctx, step['text'], .4)
        for label, value in step.get('options', {}).items():
            self.toggle(label, value)
        for _ in range(step.get('next', 0)):
            ui.key(self.ctx, 'Control+G', .3)

    def op_replace(self, step):
        ui.wait_idle(self.ctx)
        ui.key(self.ctx, 'Control+H', .6)
        ui.wait_for(self.ctx, ui.dialogs, message='the replace dialog did not appear')
        ui.fill(self.ctx, 'Find what', step['find'])
        ui.fill(self.ctx, 'Replace with', step['with'])
        for label, value in step.get('options', {}).items():
            self.toggle(label, value, dialog=True)
        for _ in range(step.get('next', 0)):
            ui.click(self.ctx, 'Next', roles=ui.BUTTON_ROLES, dialog=True)
            time.sleep(.3)
        ui.click(self.ctx, 'Replace All' if step.get('all') else 'Replace', roles=ui.BUTTON_ROLES, dialog=True)
        time.sleep(.5)
        if not step.get('leave_open'):
            ui.key(self.ctx, 'Escape', .5)

    # -- export -----------------------------------------------------------------
    def op_export(self, step):
        '''File > Export with the default HTML format and template, each page to its own file in an outbox folder.
        Other formats, templates and the single file mode need their own probes before a recipe uses them.'''
        if step.get('format', 'HTML') != 'HTML' or step.get('template', 'Default') != 'Default' or step.get('single'):
            raise NotImplementedError('the export recipe covers the HTML Default template with separate files only')
        ui.wait_idle(self.ctx)
        ui.menu(self.ctx, 'File', 'Export')
        ui.wait_for(self.ctx, ui.dialogs, message='the export dialog did not appear')
        if step.get('page'):
            self.toggle('Single page', dialog=True)
            ui.fill(self.ctx, 'Page', step['page'])
            self.toggle('Include subpages', step.get('subpages', True), dialog=True)
        ui.accept(self.ctx, 'Forward')
        time.sleep(.6)
        ui.accept(self.ctx, 'Forward')
        time.sleep(.6)
        ui.fill(self.ctx, 'Output folder', self.path('outbox', step['folder']))
        ui.accept(self.ctx, 'OK')
        if step.get('leave_open'):
            # The confirmation message stays on screen: wait for its window instead of for an idle editor.
            deadline = time.monotonic() + 30
            while len(self.rpc.windows()) < 3:
                if time.monotonic() > deadline:
                    raise AssertionError('the export did not report that it completed')
                time.sleep(.3)
            return
        ui.wait_idle(self.ctx, timeout=30)
