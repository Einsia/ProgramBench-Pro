"""Pinned-standard GUI implementation of the reviewed goals, through the black-box runtime (record only).

Recipes drive the standard answer with the same runtime GUI operations that the evaluator and the model use; the
driver captures reference evidence with the evaluator's observation. Controls are found in the runtime's own
snapshot by their names, placeholders, values and positions in the reference's layout (for example the buttons in
the row of a column in the side panel). These names and positions belong to the pinned standard only; they are never
a candidate requirement.
"""
import re
import time

import fixtures
from ui import HarnessError, norm

WAIT = 6.0
PANEL = 374  # width of the standard's side panel; canvas controls start to its right


class Recipe:
    def __init__(self, ctx):
        self.ctx = ctx
        self.ui = ctx.state['ui']

    def snap(self):
        return self.ui.snap()

    def controls(self, snap=None):
        return (snap or self.snap()).get('controls', [])

    def field_input(self, name, snap=None, nth=0):
        """The side panel input that holds a column (or other item) name; for an empty name, the last empty name
        field (a row just added)."""
        found = [c for c in self.controls(snap) if c.get('tag') in ('input', 'textarea') and c.get('value') == name]
        if name == '':
            found = [c for c in found if norm(c.get('placeholder')) == 'name'][-1:]
        if len(found) <= nth:
            raise HarnessError(f'no field holds "{name}"')
        return found[nth]

    def in_row(self, anchor, snap=None, **want):
        """Controls on the same row as anchor (vertical centres within 8 px), left to right; a row of the side
        panel keeps to the panel."""
        ax, ay, aw, ah = anchor['bounds']
        centre = ay + ah / 2
        row = [c for c in self.controls(snap) if abs(c['bounds'][1] + c['bounds'][3] / 2 - centre) <= 8
               and c['ref'] != anchor['ref'] and (ax >= PANEL or c['bounds'][0] < PANEL)]
        for key, value in want.items():
            row = [c for c in row if c.get(key) == value]
        return sorted(row, key=lambda c: c['bounds'][0])

    def click_ref(self, control):
        return self.ui.call({'op': 'click', 'target': {'ref': control['ref']}})

    def option(self, text, timeout=WAIT, filter_first=False):
        """Click an entry of an open dropdown list (option or menu item) by its text; with filter_first the text is
        typed first, for long lists that only show the entries matching what is typed."""
        if filter_first:
            self.ui.call({'op': 'type', 'value': text})
        deadline = time.monotonic() + timeout
        while True:
            snap = self.snap()
            found = [c for c in self.controls(snap) if norm(c.get('text')) == norm(text)
                     and c.get('role') in ('option', 'listbox', 'menuitem', 'menuitemcheckbox', 'treeitem')]
            if found:
                return self.click_ref(found[-1])
            if time.monotonic() > deadline:
                try:
                    return self.ui.call({'op': 'click', 'target': {'text': text}})
                except Exception:
                    raise HarnessError(f'no option "{text}"') from None
            time.sleep(0.25)

    def step(self, step):
        ui = self.ui
        do = step['do']
        if do == 'click':
            if 'nth' in step:
                found = ui.matches(step['label'])
                self.click_ref(found[step['nth']])
            else:
                ui.click(step['label'], **({'startswith': True} if step.get('startswith') else {}))
        elif do == 'tab':
            # A tab of the side panel, scrolling its tab strip to the right as needed.
            for _ in range(8):
                tabs = [c for c in self.controls() if c.get('role') == 'tab'
                        and norm(c.get('text')).startswith(norm(step['name']))]
                if tabs:
                    self.click_ref(tabs[0])
                    break
                arrows = [c for c in self.controls() if c.get('tag') == 'button' and not c.get('text')
                          and not c.get('title') and 80 <= c['bounds'][1] <= 100 and c['bounds'][0] > 300]
                if not arrows:
                    raise HarnessError('no tab ' + step['name'])
                self.click_ref(arrows[0])
            else:
                raise HarnessError('no tab ' + step['name'])
        elif do == 'fill-placeholder-type':
            target = [c for c in self.controls() if norm(c.get('placeholder')) == norm(step['placeholder'])][
                step.get('nth', 0)]
            ui.call({'op': 'click', 'target': {'ref': target['ref']}})
            ui.call({'op': 'type', 'value': step['value']})
            if step.get('commit'):
                ui.press(step['commit'])
        elif do == 'click-text':
            request = {'op': 'click', 'target': {'text': step['text'], **({'nth': step['nth']} if 'nth' in step else {})}}
            for key in ('click_count', 'button'):
                if key in step:
                    request[key] = step[key]
            ui.call(request)
        elif do == 'click-title':
            found = [c for c in self.controls() if c.get('title') == step['title']]
            self.click_ref(found[step.get('nth', 0)])
        elif do == 'menu':
            ui.menu(*step['path'], leave=step.get('leave', True))
        elif do == 'press':
            ui.press(step['key'])
        elif do == 'type':
            ui.call({'op': 'type', 'value': step['value']})
        elif do == 'fill':
            target = self.field_input(step['current'], nth=step.get('nth', 0)) if 'current' in step else None
            if target is None:
                fields = [c for c in self.controls() if c.get('tag') in ('input', 'textarea')
                          and norm(c.get('placeholder')) == norm(step['placeholder'])]
                target = fields[step.get('nth', 0)]
            ui.fill(target, step['value'])
            if step.get('commit', 'Tab'):
                ui.call({'op': 'press', 'target': {'ref': target['ref']}, 'key': step.get('commit', 'Tab')})
        elif do == 'row':
            # A button in the row of the field holding `field`: by title, by text, or the n-th unnamed one.
            anchor = self.field_input(step['field'], nth=step.get('nth', 0))
            row = self.in_row(anchor)
            if 'title' in step:
                target = [c for c in row if c.get('title') == step['title']][0]
            elif 'text' in step:
                target = [c for c in row if c.get('text') == step['text']][0]
            elif 'role' in step:
                target = [c for c in row if c.get('role') == step['role']][0]
            else:
                target = [c for c in row if c.get('tag') == 'button' and not c.get('text') and not c.get('title')][
                    step.get('unnamed', 0)]
            self.click_ref(target)
        elif do == 'fill-prefix':
            # The name field of an item whose generated name starts with prefix (opening it in the list first).
            fields = [c for c in self.controls() if c.get('tag') == 'input' and str(c.get('value', '')).startswith(
                step['prefix'])]
            if not fields:
                entry = [c for c in self.controls() if str(c.get('text', '')).startswith(step['prefix'])]
                self.click_ref(entry[0])
                fields = [c for c in self.controls() if c.get('tag') == 'input' and str(c.get('value', '')).startswith(
                    step['prefix'])]
            ui.fill(fields[0], step['value'])
            ui.call({'op': 'press', 'target': {'ref': fields[0]['ref']}, 'key': 'Tab'})
        elif do == 'row-of':
            # A button in the row of the control named anchor: the n-th unnamed one, or the one titled so.
            anchor = [c for c in self.controls() if norm(c.get('text')) == norm(step['anchor'])][step.get('nth', 0)]
            row = self.in_row(anchor)
            if 'title' in step:
                target = [c for c in row if c.get('title') == step['title']][0]
            else:
                target = [c for c in row if c.get('tag') == 'button' and not c.get('text') and not c.get('title')][
                    step.get('unnamed', 0)]
            self.click_ref(target)
        elif do == 'fill-aria':
            target = [c for c in self.controls() if c.get('aria') == step['aria']][step.get('nth', 0)]
            ui.call({'op': 'click', 'target': {'ref': target['ref']}})
            ui.call({'op': 'type', 'value': step['value']})
            if step.get('commit'):
                ui.press(step['commit'])
        elif do == 'drag-handle':
            # Drag the sortable handle in front of a column's name field onto another column's row.
            source = self.field_input(step['field'])
            dest = self.field_input(step['to_field'])
            sx, sy, sw, sh = source['bounds']
            dx, dy, dw, dh = dest['bounds']
            ui.call({'op': 'drag', 'x': sx - 17, 'y': sy + sh / 2, 'to_x': sx - 17, 'to_y': dy + dh / 2 - 6,
                     'via': [[sx - 17, sy + sh / 2 - 6]], 'steps': 15})
        elif do == 'select-in':
            # A select found by its placeholder text (or, again, the last one), then the option.
            boxes = [c for c in self.controls() if c.get('role') == 'combobox' and (
                norm(c.get('text')) == norm(step['placeholder']) or step.get('again'))]
            box = boxes[-1] if step.get('again') else boxes[0]
            self.click_ref(box)
            self.option(step['option'])
            if not step.get('keep'):
                ui.escape(1)
        elif do == 'select-value':
            # A select found by the value it shows, then the new option.
            boxes = [c for c in self.controls() if c.get('role') == 'combobox' and norm(c.get('text')) == norm(
                step['value'])]
            box = boxes[step.get('nth', 0)]
            if step.get('at_end'):
                # A multi-value select: open it beside its values (a click on a value's tag would remove it).
                x, y, w, h = box['bounds']
                ui.call({'op': 'pointer', 'x': x + w - 12, 'y': y + h / 2})
            else:
                self.click_ref(box)
            self.option(step['option'])
        elif do == 'toggle':
            # The n-th check box (an unnamed small box) of the open details popover, top to bottom.
            boxes = [c for c in self.controls() if c.get('tag') == 'span' and not c.get('text')
                     and c['bounds'][2] <= 20 and c['bounds'][3] <= 24]
            boxes.sort(key=lambda c: (c['bounds'][1], c['bounds'][0]))
            self.click_ref(boxes[step['index']])
        elif do == 'nearest':
            # The unnamed button closest to the field holding `field` (for example a delete button beside it).
            anchor = self.field_input(step['field'])
            ax, ay, aw, ah = anchor['bounds']
            buttons = [c for c in self.controls() if c.get('tag') == 'button' and not c.get('text')
                       and not c.get('title')]
            target = min(buttons, key=lambda c: (c['bounds'][0] + c['bounds'][2] / 2 - ax - aw / 2) ** 2
                         + (c['bounds'][1] + c['bounds'][3] / 2 - ay - ah / 2) ** 2)
            self.click_ref(target)
        elif do == 'option':
            self.option(step['text'], filter_first=step.get('filter', False))
        elif do == 'check':
            found = [c for c in self.controls() if norm(c.get('label')) == norm(step['label'])
                     or norm(c.get('text')) == norm(step['label'])]
            target = [c for c in found if c.get('checked') is not None] or found
            ui.call({'op': 'check', 'target': {'ref': target[0]['ref']}, 'checked': step.get('checked', True)})
        elif do == 'drag':
            request = {'op': 'drag', 'x': step['x'], 'y': step['y'], 'to_x': step['to_x'], 'to_y': step['to_y'],
                       'steps': step.get('steps', 12)}
            for key in ('via', 'button', 'modifiers'):
                if key in step:
                    request[key] = step[key]
            ui.call(request)
        elif do == 'pointer':
            request = {'op': 'pointer', 'x': step['x'], 'y': step['y']}
            for key in ('action', 'click_count', 'button', 'modifiers'):
                if key in step:
                    request[key] = step[key]
            ui.call(request)
        elif do == 'wheel':
            ui.call({'op': 'wheel', 'x': step['x'], 'y': step['y'], 'delta_y': step.get('delta_y', 0),
                     'delta_x': step.get('delta_x', 0)})
        elif do == 'hover':
            ui.call({'op': 'hover', 'target': {'text': step['text']}})
        elif do == 'upload':
            data = fixtures.input_bytes(step['file'])
            mime = {'json': 'application/json', 'sql': 'application/sql'}.get(step['file'].rsplit('.', 1)[-1],
                                                                              'application/octet-stream')
            ui.supply(step['file'], data, step.get('mime', mime))
        elif do == 'confirm':
            ui.confirm(step['label'])
        elif do == 'wait':
            ui.wait(step.get('seconds', 1))
        elif do == 'open':
            ui.call({'op': 'open', 'path': step['path']})
        elif do == 'reload':
            ui.call({'op': 'reload'})
        elif do == 'away':
            ui.away()
        elif do == 'escape':
            ui.escape(step.get('times', 1))
        elif do == 'expect':
            deadline = time.monotonic() + WAIT
            while not ui.contains(step['text'], self.snap()):
                if time.monotonic() > deadline:
                    raise HarnessError('text not shown: ' + step['text'])
                time.sleep(0.3)
        elif do == 'download':
            deadline = time.monotonic() + WAIT
            while not any(d['filename'].endswith(step['suffix']) for d in self.snap().get('downloads', [])):
                if time.monotonic() > deadline:
                    raise HarnessError('no download ' + step['suffix'])
                time.sleep(0.3)
        elif do == 'swatch':
            # The colour swatch right of an item's name field (a plain box, not a control), then its picker opens.
            anchor = self.field_input(step['field'])
            x, y, w, h = anchor['bounds']
            ui.call({'op': 'pointer', 'x': x + w + step.get('dx', 24), 'y': y + step.get('dy', h / 2)})
        elif do == 'swatch-left':
            # The colour swatch at the left end of the row of the control named anchor.
            anchor = [c for c in self.controls() if step['anchor'] in (c.get('title'), c.get('text'))][0]
            x, y, w, h = anchor['bounds']
            ui.call({'op': 'pointer', 'x': step.get('x', 40), 'y': y + h / 2})
        elif do == 'hex':
            # The hexadecimal value field of the open colour picker.
            fields = [c for c in self.controls() if c.get('tag') == 'input'
                      and re.fullmatch(r'#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})', str(c.get('value', '')))]
            value = step['value'] if fields[-1]['value'].startswith('#') else step['value'].lstrip('#')
            ui.fill(fields[-1], value)
            ui.call({'op': 'press', 'target': {'ref': fields[-1]['ref']}, 'key': 'Enter'})
        elif do == 'focus-aria':
            target = [c for c in self.controls() if c.get('aria') == step['aria']][step.get('nth', 0)]
            self.click_ref(target)
        elif do == 'tag-close':
            # The close mark at the right end of a closable tag (a value of a multi-value field).
            tag = [c for c in self.controls() if norm(c.get('aria')) == norm('Closable Tag: ' + step['tag'])][0]
            x, y, w, h = tag['bounds']
            ui.call({'op': 'pointer', 'x': x + w - 9, 'y': y + h / 2})
        elif do == 'code-line':
            # In the code editor: the end of the line that shows the word, then the typed text.
            ui.call({'op': 'click', 'target': {'text': step['word']}})
            ui.press('End')
            ui.call({'op': 'type', 'value': step['value']})
        elif do == 'code-end':
            ui.call({'op': 'click', 'target': {'text': step.get('line', 'Table')}})
            ui.press('Control+End')
            ui.call({'op': 'type', 'value': step['value']})
        elif do == 'code-word':
            # Select a word of the code by double-clicking it, then type its replacement.
            ui.call({'op': 'click', 'target': {'text': step['word'], **({'nth': step['nth']} if 'nth' in step else {})},
                     'click_count': 2})
            ui.call({'op': 'type', 'value': step['value']})
        elif do == 'upload-tab':
            ui.choose_upload_tab()
        elif do == 'tick':
            ui.tick(step['label'], step.get('checked', True))
        elif do == 'fill-new':
            # The newest empty text field (a row just added to a dialog).
            fields = [c for c in self.controls() if c.get('tag') == 'input' and c.get('type', 'text') == 'text'
                      and not c.get('value')]
            ui.fill(fields[step.get('nth', 0)], step['value'])
        elif do == 'nth-unnamed':
            # The n-th unnamed button of the page in reading order (for example the fork button of a template card).
            buttons = [c for c in self.controls() if c.get('tag') == 'button' and not c.get('text')
                       and not c.get('title') and not c.get('aria')]
            buttons.sort(key=lambda c: (c['bounds'][1], c['bounds'][0]))
            self.click_ref(buttons[step['index']])
        elif do == 'choose':
            ui.choose(step['menu'], step['item'], step['button'])
        elif do == 'dialog-fill':
            if step.get('menu'):
                ui.menu(*step['menu'])
            ui.dialog_fill(step['value'], step['button'])
        elif do == 'reload':
            ui.call({'op': 'reload'})
        elif do == 'modal-row-delete':
            anchor = self.field_input(step['field'])
            x, y, width, height = anchor['bounds']
            buttons = [c for c in self.controls() if c.get('tag') == 'button'
                       and c['bounds'][0] > x + width and abs(c['bounds'][1] + c['bounds'][3] / 2 - y - height / 2) < 12]
            self.click_ref(max(buttons, key=lambda c: c['bounds'][0]))
        elif do == 'screenshot':
            ui.call({'op': 'screenshot'})
        else:
            raise ValueError('unknown recipe step ' + do)


def execute(ctx, checkpoint):
    recipe = Recipe(ctx)
    recipe.snap()
    for step in checkpoint['recipe']:
        recipe.step(step)
    # Evidence after a settled page.
    ctx.state['ui'].wait(0.5)

