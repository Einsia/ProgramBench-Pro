"""Guard configuration save goals, persisted companions and the published specification."""
import json
from pathlib import Path
import unittest

import suite


class ConfigurationGoalsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = suite.build()
        cls.frozen = json.loads((Path(__file__).resolve().parent / 'data/manifest.json').read_text())

    def test_general_options_require_exit_save_and_reopen(self):
        episodes = [w for w in self.current['episodes'] if w['id'].startswith('gui-config-')]
        self.assertEqual(len(episodes), 14)
        for episode in episodes:
            with self.subTest(episode=episode['id']):
                cp = episode['checkpoints'][0]
                for phrase in ('Leave general options', 'exit the configuration menu', 'return to the organizer',
                               'save the setting', 'Reopen general options'):
                    self.assertIn(phrase, cp['goal'])
                frontend = next(a for a in cp['assertions'] if a['channel'] == 'frontend')
                self.assertIn('saved by returning to the organizer', frontend['requirement'])
                self.assertIn('reopened', frontend['requirement'])
                companion = next(a for a in cp['assertions'] if a['channel'] == 'backend')
                self.assertEqual(companion['check']['kind'], 'file')
                self.assertEqual(companion['check']['mode'], 'conf')
                self.assertEqual(frontend['requires'], [companion['id']])

    def test_binding_edits_require_exit_save_and_reopen(self):
        episode = next(w for w in self.current['episodes'] if w['id'] == 'gui-key-configuration')
        for cp in episode['checkpoints']:
            if cp['id'] not in ('add-alias', 'remove-alias'):
                continue
            with self.subTest(checkpoint=cp['id']):
                for phrase in ('Leave the key editor', 'exit the configuration menu', 'return to the organizer',
                               'save the key configuration', 'Reopen the key editor'):
                    self.assertIn(phrase, cp['goal'])
                frontend = next(a for a in cp['assertions'] if a['channel'] == 'frontend')
                self.assertIn('saved by returning to the organizer', frontend['requirement'])
                self.assertIn('reopened key editor', frontend['requirement'])
                companion = next(a for a in cp['assertions'] if a['channel'] == 'backend')
                self.assertEqual(companion['check']['mode'], 'keys')
                self.assertEqual(frontend['requires'], [companion['id']])

    def test_published_manifest_matches_executable_specification(self):
        # Includes goals, reference steps, persisted-file checks and companion dependencies.
        self.assertEqual(self.current, self.frozen)


if __name__ == '__main__':
    unittest.main()
