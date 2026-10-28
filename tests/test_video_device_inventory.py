# SPDX-License-Identifier: MIT
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_classlist/device_inventory.py'
spec = importlib.util.spec_from_file_location('device_inventory', path)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)

def target():
    return {'vendor-id': bytes.fromhex('de100000'), 'device-id': bytes.fromhex('98110000'),
            'rm_board_number': b'\0' * 4, 'IORegistryEntryID': 7, 'IORegistryEntryName': 'GFX0'}

class DeviceInventoryTests(unittest.TestCase):
    def test_nested_unique_match_and_zero_value(self):
        out = inventory.inspect_tree([{'children': [target()]}])
        self.assertEqual(out['board_value_u32_le'], 0)
        self.assertEqual(out['private_RM_calls'], 0)

    def test_ambiguous_or_missing_gpu_is_refused(self):
        for tree in ([], [target(), target()]):
            with self.assertRaises(ValueError):
                inventory.inspect_tree(tree)

    def test_property_type_length_and_identity_are_required(self):
        for key, value in [('rm_board_number', b''), ('rm_board_number', 0),
                           ('IORegistryEntryID', True), ('IORegistryEntryID', 0)]:
            row = target(); row[key] = value
            with self.assertRaises(ValueError):
                inventory.inspect_tree([row])

if __name__ == '__main__':
    unittest.main()
