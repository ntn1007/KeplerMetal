# SPDX-License-Identifier: MIT
import importlib.util
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_cached_codec/audit.py'
spec = importlib.util.spec_from_file_location('gva_cached_codec', PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class OfflineContractTest(unittest.TestCase):
    def fixture(self):
        data = bytearray(2669)
        branches = [(0x541, 1, 1, 0x55e), (0x54d, 1, 1, 0x556),
                    (0x55c, 1, 1, 0x546), (0x65c, 1, 1, 0x692),
                    (0x669, 1, 1, 0x656), (0x676, 4, 2, 0x763),
                    (0x680, 4, 2, 0x763), (0x68d, 4, 1, 0x8af),
                    (0x815, 1, 1, 0x840)]
        for at, size, pos, target in branches:
            struct.pack_into({1: '<b', 4: '<i'}[size], data, at + pos, target - at - pos - size)
        mapping = json.dumps({'status': 'STATIC_ONLY', 'runtime_target_proved': False,
                              'rows': [{'caller_offset': n, 'exact_defined_symbols': [s]} for n, s in
                                       [(150807, '_IORegistryEntryCreateCFProperty'),
                                        (150845, '_CFStringGetCString'), (150853, '_CFRelease')]]}).encode()
        windows = {name: (lo, hi, audit.digest(data[lo:hi])) for name, (lo, hi, _) in audit.WINDOWS.items()}
        return bytes(data), mapping, windows

    def test_relative_target_signed_short_and_long(self):
        data, _, _ = self.fixture()
        self.assertEqual(audit.relative_target(data, 0x55c, 1, 1), 0x546)
        self.assertEqual(audit.relative_target(data, 0x676, 4, 2), 0x763)

    def test_synthetic_pins_pass_without_claiming_runtime(self):
        data, mapping, windows = self.fixture()
        with patch.object(audit, 'REGION', audit.digest(data)), patch.object(audit, 'MAPPING', audit.digest(mapping)), patch.object(audit, 'WINDOWS', windows):
            result = audit.inspect(data, mapping)
        self.assertEqual(result['branch_targets_verified'], 9)
        self.assertFalse(result['runtime_reactivation_observed'])
        self.assertFalse(result['hardware_video_execution_proved'])

    def test_changed_branch_refused_even_if_hashes_recomputed(self):
        data, mapping, windows = self.fixture()
        changed = bytearray(data)
        changed[0x682] ^= 1
        windows = {name: (lo, hi, audit.digest(changed[lo:hi])) for name, (lo, hi, _) in windows.items()}
        with patch.object(audit, 'REGION', audit.digest(changed)), patch.object(audit, 'MAPPING', audit.digest(mapping)), patch.object(audit, 'WINDOWS', windows):
            with self.assertRaisesRegex(ValueError, 'branch target mismatch'):
                audit.inspect(bytes(changed), mapping)

    def test_unpinned_region_rejected(self):
        data, mapping, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, 'region pin mismatch'):
            audit.inspect(data, mapping)

    def test_wrong_mapping_refused(self):
        data, mapping, windows = self.fixture()
        with patch.object(audit, 'REGION', audit.digest(data)), patch.object(audit, 'WINDOWS', windows):
            with self.assertRaisesRegex(ValueError, 'mapping pin mismatch'):
                audit.inspect(data, mapping)


if __name__ == '__main__':
    unittest.main()
