# SPDX-License-Identifier: MIT
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fields_reaudit', ROOT/'bridge/experiments/video_provider_fields_reaudit/audit.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def valid_gate():
    observation = {key: True for key in ('ready', 'caller_pinned', 'caller_path_matches', 'caller_UUID_matches',
                   'config_header_20_read', 'display_array_region_readable', 'selected_index_in_mask',
                   'selected_index_in_range', 'selected_display_value_nonzero', 'region_is_not_allocation_size_proof')}
    observation.update(caller_offset=0x24d16, config_first_word=0, display_mask=15, display_array_required_count=4)
    return {'status': 'COMPLETE', 'calibration_pass': True, 'drained': True, 'dropped': 0, 'sierra_loaded': False,
            'sierra_export_called': False, 'gate_return': 14, 'gate_calls': 1, 'argument_observation': observation,
            'events': [{'name': 'AVD_CreateAVDAccelerator', 'found': True, 'identity_pin': True, 'result_replaced': True}]}


class EvidenceTests(unittest.TestCase):
    def test_positive_and_changed_fields(self):
        original = valid_gate()
        m.check_capture(original, 'enabled')
        for key, value in [('display_mask', 1), ('display_array_required_count', 1),
                           ('selected_display_value_nonzero', False), ('caller_pinned', False), ('caller_offset', 0)]:
            changed = copy.deepcopy(original)
            changed['argument_observation'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.check_capture(changed, 'enabled')
        changed = copy.deepcopy(original)
        changed['sierra_export_called'] = True
        with self.assertRaises(ValueError):
            m.check_capture(changed, 'enabled')

    def test_negative_route_cannot_silently_observe(self):
        gate = valid_gate()
        gate['gate_calls'] = 0
        gate['argument_observation']['ready'] = False
        m.check_capture(gate, 'wrong-name')
        gate['gate_calls'] = 1
        with self.assertRaises(ValueError):
            m.check_capture(gate, 'wrong-name')


if __name__ == '__main__':
    unittest.main()
