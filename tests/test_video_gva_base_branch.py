import importlib.util
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_rtti/base_branch_audit.py'
SPEC = importlib.util.spec_from_file_location('base_branch_audit', PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class BranchTest(unittest.TestCase):
    def test_control_and_mutations(self):
        data = bytearray(176)
        data[28:34] = bytes.fromhex('41833eff7410')
        data[34:44] = bytes.fromhex('498b7e38410fb67640e8')
        struct.pack_into('<i', data, 44, 148746 - (audit.START + 48))
        with patch.object(audit, 'digest', return_value=audit.REGION):
            self.assertEqual(audit.check_branch(data), (117074, 148746))
            for offset in (28, 32, 33, 34, 43, 44):
                changed = bytearray(data)
                changed[offset] ^= 1
                with self.subTest(offset=offset), self.assertRaises(ValueError):
                    audit.check_branch(changed)
            with self.assertRaises(ValueError):
                audit.check_branch(data[:-1])

    def test_hash_pin_refuses_synthetic_region(self):
        with self.assertRaises(ValueError):
            audit.check_branch(bytes(176))


if __name__ == '__main__':
    unittest.main()
