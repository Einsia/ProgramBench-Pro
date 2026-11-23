"""drawDB specifics for the shared driver: checkpoint preparation, reference recipes, program checks.

Everything reaches the candidate through the black-box runtime: each checkpoint starts in a fresh browser profile
on the editor with a new diagram of its database, loads its diagram through the application's own import (a
diagram file, a SQL script or a DBML file chosen in the import dialog), applies its stimulus with GUI operations
(menus, dialog buttons, fields, keyboard shortcuts, the clipboard), and checks the files the application exports,
the clipboard or the visible page (ui, checks).
"""
import json

from evaluation.driver import Hooks as Base
import checks
import fixtures
from reference import recipes
from ui import UI, HarnessError



def run_steps(ctx, steps):
    ui = ctx.state['ui']
    for step in steps:
        do = step['do']
        if do == 'fresh':
            ui.fresh(step.get('db', 'generic'), step.get('path', '/editor'))
        elif do == 'import-json':
            ui.import_json('diagram.json', fixtures.diagram(step['fixture']))
        elif do == 'stage-json':
            data = json.dumps(fixtures.diagram(step['fixture']), indent=2).encode() if 'fixture' in step \
                else fixtures.text_file(step['file']).encode()
            ui.stage_json(step.get('file', 'diagram.json'), data)
        elif do == 'import-sql':
            ui.import_sql(step['file'], fixtures.text_file(step['file']), step.get('dialect'), step.get('overwrite', False))
        elif do == 'import-dbml':
            ui.import_dbml(step['file'], fixtures.text_file(step['file']))
        elif do == 'import-ddb':
            ui.menu('File', 'Import from', 'JSON')
            ui.supply(step['file'], fixtures.input_bytes(step['file']), 'application/octet-stream')
            ui.submit('Import')
        elif do == 'custom-type-add':
            ui.menu('Settings', 'Configure custom types')
            ui.click('Add custom type')
            ui.dialog_fill(step['name'], 'Save', placeholder='VARCHAR')
        elif do == 'choose-value':
            ui.choose_value(step['current'], step['value'])
        elif do == 'fill-value':
            fields = [c for c in ui.snap().get('controls', []) if c.get('tag') in ('input', 'textarea')
                      and c.get('value') == step['current']]
            if len(fields) != 1:
                raise HarnessError('the form has no unique field with value ' + step['current'])
            ui.fill(fields[0], step['value'])
            ui.press('Tab')
        elif do == 'new-diagram':
            ui.menu('File', 'New')
            if ui.find('Blank'):
                ui.click('Blank')
                ui.confirm('Create')
            ui.choose_database(step['db'])
        elif do == 'saved-fixtures':
            entries = [('Atlas', 'mysql', 'gui-shop'), ('Birch', 'postgresql', 'gui-events'),
                       ('Cedar', 'mysql', 'gui-shop')]
            for n, (name, database, fixture) in enumerate(entries):
                if n:
                    ui.menu('File', 'New')
                    ui.click('Blank')
                    ui.confirm('Create')
                    ui.choose_database(database)
                data = fixtures.diagram(fixture)
                data['title'] = name
                if name == 'Cedar':
                    data['tables'] = data['tables'][:1]
                    data['relationships'] = []
                ui.import_json(name + '.json', data)
                ui.press('Control+s')
                ui.wait(1)
            ui.menu('File', 'Open')
        elif do == 'menu':
            ui.menu(*step['path'], leave=step.get('leave', True))
        elif do == 'click':
            ui.click(step['label'], **({'startswith': True} if step.get('startswith') else {}))
        elif do == 'confirm':
            ui.confirm(step['label'])
        elif do == 'press':
            ui.press(step['key'])
        elif do == 'escape':
            ui.escape(step.get('times', 2))
        elif do == 'away':
            ui.away()
        elif do == 'open':
            ui.call({'op': 'open', 'path': step['path']})
        elif do == 'reset-open':
            status = ui.call({'op': 'reset'})
            if not status.get('ready'):
                raise HarnessError('the application did not come back after a reset')
            ui.call({'op': 'open', 'path': '/editor'})
        elif do == 'reload':
            ui.call({'op': 'reload'})
        elif do == 'restart':
            status = ui.call({'op': 'restart'})
            if not status.get('ready'):
                raise HarnessError('the application did not come back after a restart')
            ui.call({'op': 'reload'})
        elif do == 'wait':
            ui.wait(step.get('seconds', 0.5))
        elif do == 'clipboard':
            text = fixtures.text_file(step['file']) if 'file' in step else step['text']
            ui.call({'op': 'clipboard', 'action': 'write', 'text': text})
        elif do == 'table':
            ui.open_table(step['name'])
        elif do == 'fill':
            ui.fill_field(step)
        elif do == 'dialog-fill':
            ui.menu(*step['menu'])
            ui.dialog_fill(step['value'], step['button'])
        elif do == 'choose':
            ui.choose(step['menu'], step['item'], step['button'])
        elif do == 'confirm-menu':
            ui.menu_confirm(*step['menu'])
        elif do == 'select':
            ui.open_table(step['name'])
        else:
            raise ValueError('unknown step ' + do)


class Hooks(Base):
    def start(self, ctx):
        ctx.state['ui'] = UI(ctx.broker)

    def inputs(self, ctx):
        for name in ctx.episode.get('inputs', {}).get('files', []):
            (ctx.inputs / name).write_bytes(fixtures.input_bytes(name))

    def setup(self, ctx, item):
        if item['id'] == 'editor':
            return
        raise ValueError('unknown setup item ' + item['id'])

    def prepare(self, ctx, checkpoint):
        ctx.state['exports'] = {}
        run_steps(ctx, checkpoint.get('prep', []))

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx, checkpoint)

    def collect(self, ctx, checkpoint):
        ctx.state['exports'] = {}

    def check(self, ctx, checkpoint, assertion):
        observation = checks.observe(ctx, checkpoint, assertion['check'])
        assert isinstance(observation, dict) and observation, 'the check produced no observation'
        return observation

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        checks.compare(actual, expected, assertion['check'].get('tol'))
