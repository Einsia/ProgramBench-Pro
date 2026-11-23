"""Maintainer regressions; run with PYTHONDONTWRITEBYTECODE=1 and external TMPDIR."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import checks
import field_identity as identity
from hooks import Hooks
import suite


HERE = Path(__file__).resolve().parent


def field(value, label=None, placeholder=None, readonly=False):
    control = {'tag': 'input', 'type': 'text', 'value': value}
    if label is not None:
        control['label'] = label
    if placeholder is not None:
        control['placeholder'] = placeholder
    if readonly:
        control['readonly'] = True
    return control


def observe(page, controls, spec):
    snap = {'controls': controls}
    ctx = SimpleNamespace(state={'page': SimpleNamespace(snap=lambda: snap)})
    return checks.observe(ctx, {'page': page}, spec)


def judge(page, spec, actual, expected):
    Hooks().judge(None, {'page': page}, {'check': spec}, actual, expected)


class FieldIdentityTests(unittest.TestCase):
    def test_temperature_placeholder_and_semantic_labels(self):
        values = ['373.15', '100', '211.99', '671.67', '0', '33', '80', '60']
        names = ['Kelvin', 'Celsius', 'Fahrenheit', 'Rankine', 'Delisle', 'Newton', 'Reaumur', 'Romer']
        spec = {'type': 'inputs'}
        actual = observe('/temperature-converter', [field(v, label=n) for n, v in zip(names, values)], spec)
        frozen = {'inputs': [['Please Input', v] for v in values]}
        judge('/temperature-converter', spec, actual, frozen)
        self.assertEqual([p[0] for p in actual['inputs']][:3], names[:3])

    def test_temperature_values_cannot_move_to_another_scale(self):
        expected = {'inputs': [['Please Input', '273.15'], ['Please Input', '0']]}
        for actual in ({'inputs': [['Celsius', '273.15'], ['Kelvin', '0']]},
                       {'inputs': [['Kelvin', '0'], ['Celsius', '273.15']]}):
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                judge('/temperature-converter', {'type': 'inputs'}, actual, expected)

    def test_named_field_layout_can_change_without_moving_values_between_roles(self):
        expected = {'inputs': [['SVG width...', '600'], ['SVG height...', '350']]}
        actual = observe('/svg-placeholder-generator', [field('350', 'Height (in px)'), field('600', 'Width (in px)')],
                         {'type': 'inputs'})
        judge('/svg-placeholder-generator', {'type': 'inputs'}, actual, expected)

    def test_width_and_height_are_not_interchangeable(self):
        with self.assertRaises(AssertionError):
            judge('/svg-placeholder-generator', {'type': 'inputs'},
                  {'inputs': [['Height (in px)', '600'], ['Width (in px)', '350']]},
                  {'inputs': [['SVG width...', '600'], ['SVG height...', '350']]})

    def test_wrong_units_and_unknown_labels_are_rejected(self):
        for label in ('Width (in cm)', 'Height (in inches)', 'Unrelated value'):
            with self.subTest(label=label), self.assertRaises(AssertionError):
                observe('/svg-placeholder-generator', [field('600', label, 'SVG width...')], {'type': 'inputs'})

    def test_semantic_caption_does_not_require_the_original_placeholder(self):
        actual = observe('/svg-placeholder-generator', [field('600', 'Width (in px)', 'Choose a width')],
                         {'type': 'inputs'})
        judge('/svg-placeholder-generator', {'type': 'inputs'}, actual, {'inputs': [['SVG width...', '600']]})

    def test_hash_selection_uses_algorithm_before_visual_position(self):
        spec = {'type': 'outputs', 'start': 1, 'stop': 2, 'labels': True}
        actual = observe('/hash-text', [field('sha1-digest', 'SHA-1', readonly=True),
                                       field('md5-digest', 'MD5', readonly=True)], spec)
        self.assertEqual(actual, {'outputs': [['SHA1', 'sha1-digest']]})
        judge('/hash-text', spec, actual, {'outputs': [['Input text', 'sha1-digest']]})

    def test_hash_values_and_algorithm_labels_cannot_be_swapped(self):
        spec = {'type': 'outputs', 'labels': True}
        expected = {'outputs': [['Input text', 'md5-digest'], ['Input text', 'sha1-digest']]}
        for actual in ({'outputs': [['MD5', 'sha1-digest'], ['SHA1', 'md5-digest']]},
                       {'outputs': [['SHA1', 'md5-digest'], ['MD5', 'sha1-digest']]}):
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                judge('/hash-text', spec, actual, expected)

    def test_single_hash_result_retains_its_algorithm(self):
        with self.assertRaises(AssertionError):
            judge('/hash-text', {'type': 'outputs', 'labels': True, 'start': 2, 'stop': 3},
                  {'outputs': [['SHA1', 'digest']]}, {'outputs': [['Input text', 'digest']]})

    def test_value_only_hash_checks_also_keep_algorithm_identity(self):
        spec = {'type': 'outputs', 'start': 0, 'stop': 1}
        actual = observe('/hash-text', [field('sha1', 'SHA1', readonly=True), field('md5', 'MD5', readonly=True)], spec)
        self.assertEqual(actual, {'outputs': ['md5']})
        with self.assertRaises(AssertionError):
            observe('/hash-text', [field('md5', 'SHA1024', readonly=True)], spec)

    def test_missing_requested_hash_cannot_be_replaced_by_another_algorithm(self):
        spec = {'type': 'outputs', 'start': 0, 'stop': 1}
        with self.assertRaises(AssertionError):
            observe('/hash-text', [field('md5-value', 'SHA1', readonly=True)], spec)
        # A slice may read its requested algorithm even if unrelated results
        # are missing. It must never compress the roles into new positions.
        spec = {'type': 'outputs', 'start': 1, 'stop': 2, 'labels': True}
        actual = observe('/hash-text', [field('sha1-value', 'SHA1', readonly=True)], spec)
        self.assertEqual(actual, {'outputs': [['SHA1', 'sha1-value']]})

    def test_keycode_duplicate_placeholder_is_only_a_positional_fallback(self):
        spec = {'type': 'outputs', 'labels': True}
        expected = {'outputs': [['Key name...', 'a'], ['Keycode...', '65'], ['Code...', 'KeyA'],
                                ['Code...', '0'], ['None', '']]}
        named = {'outputs': [['Key :', 'a'], ['Keycode :', '65'], ['Code :', 'KeyA'],
                             ['Location :', '0'], ['Modifiers :', '']]}
        judge('/keycode-info', spec, named, expected)
        named['outputs'][2][0], named['outputs'][3][0] = 'Location', 'Code'
        with self.assertRaises(AssertionError):
            judge('/keycode-info', spec, named, expected)

    def test_number_and_custom_bases_remain_distinct(self):
        expected = {'inputs': [['Input number', '255'], ['Put your input base here (ex: 10)', '10'],
                               ['Please Input', '42']]}
        actual = {'inputs': [['Input number', '255'], ['Input base', '10'], ['Custom:', '42']]}
        judge('/base-converter', {'type': 'inputs'}, actual, expected)
        actual['inputs'][1][1], actual['inputs'][2][1] = '42', '10'
        with self.assertRaises(AssertionError):
            judge('/base-converter', {'type': 'inputs'}, actual, expected)

    def test_quantity_namespace_and_name_are_distinct(self):
        spec = {'type': 'inputs'}
        expected = {'inputs': [['UUID quantity', '3'], ['Namespace', 'dns'], ['Name', 'example.org']]}
        actual = {'inputs': [['Quantity', '3'], ['Name', 'example.org'], ['Namespace', 'dns']]}
        judge('/uuid-generator', spec, actual, expected)
        actual['inputs'][1][0], actual['inputs'][2][0] = 'Namespace', 'Name'
        with self.assertRaises(AssertionError):
            judge('/uuid-generator', spec, actual, expected)

    def test_duplicate_missing_and_extra_fields_fail(self):
        spec = {'type': 'inputs'}
        expected = {'inputs': [['SVG width...', '600'], ['SVG height...', '350']]}
        for pairs in ([['Width', '600'], ['Width', '350']], [['Width', '600']],
                      [['Width', '600'], ['Height', '350'], ['Font size', '26']]):
            with self.subTest(pairs=pairs), self.assertRaises(AssertionError):
                judge('/svg-placeholder-generator', spec, {'inputs': pairs}, expected)

    def test_conflicting_public_names_fail(self):
        with self.assertRaises(AssertionError):
            observe('/svg-placeholder-generator', [field('600', 'Width', 'SVG height...')], {'type': 'inputs'})

    def test_multi_normalizes_only_declared_field_groups(self):
        spec = {'type': 'multi', 'checks': {'bits': {'type': 'inputs'}, 'text': {'type': 'lines'}}}
        expected = {'bits': {'inputs': [['Please Input', '1024']]}, 'text': {'lines': ['Bits', 'message']}}
        actual = {'bits': {'inputs': [['Bits :', '1024']]}, 'text': {'lines': ['Bits', 'message']}}
        judge('/rsa-key-pair-generator', spec, actual, expected)
        for changed in (('bits', {'inputs': [['Bits', '2048']]}), ('text', {'lines': ['Bits', 'wrong']})):
            wrong = {**actual, changed[0]: changed[1]}
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                judge('/rsa-key-pair-generator', spec, wrong, expected)

    def test_unmapped_page_keeps_strict_label_comparison(self):
        with self.assertRaises(AssertionError):
            judge('/unrelated-tool', {'type': 'inputs'}, {'inputs': [['different', 'same value']]},
                  {'inputs': [['original', 'same value']]})

    def test_truncated_snapshots_do_not_use_positional_fallbacks(self):
        ctx = SimpleNamespace(state={'page': SimpleNamespace(snap=lambda: {'controls': [], 'controls_truncated': True})})
        for kind in ('inputs', 'outputs'):
            with self.subTest(kind=kind), self.assertRaises(AssertionError):
                checks.observe(ctx, {'page': '/temperature-converter'}, {'type': kind})

    def test_all_existing_oracle_objects_still_normalize_without_mutation(self):
        manifest = suite.build()
        oracle = json.loads((HERE / 'data/oracle.json').read_text())['program']
        original = copy.deepcopy(oracle)
        for episode in manifest['episodes']:
            for checkpoint in episode['checkpoints']:
                for assertion in checkpoint['assertions']:
                    if assertion['channel'] == 'backend':
                        expected = oracle[assertion['id']]
                        with self.subTest(assertion=assertion['id']):
                            judge(checkpoint.get('page', '/'), assertion['check'], expected, expected)
        self.assertEqual(oracle, original)

    def test_existing_reference_snapshots_use_declared_semantic_roles(self):
        count = 0
        for path in (HERE / 'data/reference').glob('*/*.json'):
            snap = json.loads(path.read_text())
            for group, select in (('inputs', checks.inputs), ('outputs', checks.outputs)):
                if identity.schema(snap.get('url', '/'), group) is not None:
                    with self.subTest(path=path, group=group):
                        identity.project_controls(select(snap), snap['url'], group)
                    count += 1
        self.assertGreater(count, 20)


if __name__ == '__main__':
    unittest.main()
