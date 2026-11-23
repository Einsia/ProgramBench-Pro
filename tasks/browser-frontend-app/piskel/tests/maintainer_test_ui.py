"""Maintainer regressions for visible field groups. Run with unittest and the runtime's Playwright environment."""
import ast
import os
from pathlib import Path
import unittest

import ui


class ScopeMatchingTests(unittest.TestCase):
    def test_shared_ancestor_does_not_exclude_the_active_field(self):
        active = {'ref': 'active', 'label': 'Height', 'editable': True, 'group': 'Resize',
                  'context': 'Height px | Resize Width px Height px Default size Width px Height px'}
        default = dict(active, ref='default', group='Default size', focused=True)
        self.assertIs(ui.find({'controls': [default, active]},
                             {'semantic': 'Height', 'editable': True, 'scope': 'Resize',
                              'exclude_scope': 'Default size'}), active)

    def test_default_scope_prefers_its_own_group_over_ancestor_text(self):
        active = {'ref': 'active', 'label': 'Width', 'editable': True, 'group': 'Resize',
                  'context': 'Width px | Resize Default size Width px Height px'}
        default = dict(active, ref='default', group='Default size')
        self.assertIs(ui.find({'controls': [active, default]},
                             {'semantic': 'Width', 'scope': 'Default size'}), default)

    def test_ambiguous_fields_still_fail(self):
        control = {'label': 'Width', 'editable': True, 'group': 'Resize', 'context': 'Resize Default size'}
        with self.assertRaisesRegex(AssertionError, 'Ambiguous'):
            ui.find({'controls': [dict(control, ref='one'), dict(control, ref='two')]},
                    {'semantic': 'Width', 'scope': 'Resize', 'exclude_scope': 'Default size'})

    def test_legacy_context_is_not_searched_as_a_whole_for_exclusion(self):
        control = {'ref': 'one', 'label': 'Width', 'context': 'Width px | Resize | Resize Default size'}
        self.assertIs(ui.find({'controls': [control]},
                             {'semantic': 'Width', 'scope': 'Resize', 'exclude_scope': 'Default size'}), control)


class RenderedGroupingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(args=['--no-sandbox'])
        self.page = await self.browser.new_page(viewport={'width': 1280, 'height': 900})
        runtime = Path(os.environ.get('PISKEL_RUNTIME_DIR', Path(__file__).resolve().parents[1] / 'environment/runtime'))
        if not runtime.is_dir():
            runtime = Path('/opt/blackbox/runtime')
        module = ast.parse((runtime / 'broker.py').read_text())
        self.helpers = ast.literal_eval(next(n.value for n in module.body if isinstance(n, ast.Assign)
                                            and any(isinstance(t, ast.Name) and t.id == 'HELPERS' for t in n.targets)))

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def snapshot(self, html):
        await self.page.set_content(html)
        return await self.page.evaluate('() => {' + self.helpers + '''
          return {controls: controls(400).out.map(c => {
            const result = {...c}; delete result._el; delete result._field; return result;
          })};
        }''')

    def assert_dimensions(self, snapshot):
        # Values identify the fixture fields only; production matching uses rendered labels and group headings.
        for axis, active_value, default_value in [('Width', '8', '32'), ('Height', '10', '48')]:
            match = {'semantic': axis, 'editable': True, 'scope': 'Resize', 'exclude_scope': 'Default size'}
            self.assertEqual(ui.find(snapshot, match)['value'], active_value)
            default = ui.find(snapshot, {'semantic': axis, 'editable': True, 'scope': 'Default size'})
            self.assertEqual(default['value'], default_value)
            self.assertEqual(default['group'], 'Default size')

    async def test_separate_forms_with_text_block_headings(self):
        # The reference product uses text block captions and two separate forms in one panel.
        snapshot = await self.snapshot('''<div><div>Resize</div><div><form>
          <div><span>Width</span><input value="8"><span>px</span></div>
          <div><span>Height</span><input value="10"><span>px</span></div>
          <input type="submit" value="Resize"></form></div>
          <div>Default size</div><div><form>
          <div><span>Width</span><input value="32"><span>px</span></div>
          <div><span>Height</span><input value="48"><span>px</span></div>
          <input type="submit" value="Set default"></form></div></div>''')
        self.assert_dimensions(snapshot)

    async def test_rows_sharing_one_panel_with_semantic_headings(self):
        # Sibling labelled rows under headings can share one panel.
        snapshot = await self.snapshot('''<aside><h2>Resize</h2>
          <div><label>Width <input value="8"></label>px</div>
          <div><label>Height <input value="10"></label>px</div>
          <input type="submit" value="Resize"><h3>Default size</h3>
          <div><label>Width <input value="32"></label>px</div>
          <div><label>Height <input value="48"></label>px</div>
          <input type="submit" value="Set default"></aside>''')
        self.assert_dimensions(snapshot)

    async def test_explicit_field_groups_and_hidden_headings(self):
        snapshot = await self.snapshot('''<main><h2>Resize and Default size</h2>
          <fieldset><legend>Resize</legend><label>Width <input value="8"></label>
          <label>Height <input value="10"></label></fieldset>
          <h3 id="default-heading">Default size</h3><div role="group" aria-labelledby="default-heading">
          <h3 hidden>Resize</h3><div><label>Width <input value="32"></label></div>
          <div><label>Height <input value="48"></label></div></div></main>''')
        self.assert_dimensions(snapshot)

    async def test_duplicate_groups_remain_ambiguous(self):
        snapshot = await self.snapshot('''<section><h2>Resize</h2><label>Width <input value="8"></label></section>
          <section><h2>Resize</h2><label>Width <input value="12"></label></section>''')
        with self.assertRaisesRegex(AssertionError, 'Ambiguous'):
            ui.find(snapshot, {'semantic': 'Width', 'scope': 'Resize', 'exclude_scope': 'Default size'})


if __name__ == '__main__':
    unittest.main()
