# SPDX-License-Identifier: MIT
import importlib.util
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_classlist/nested_audit.py'
spec = importlib.util.spec_from_file_location('nested_audit', path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class NestedAuditTests(unittest.TestCase):
    def test_table_contract_rejects_duplicate_and_early_terminator(self):
        data = bytearray(82 * 16)
        for i in range(81):
            struct.pack_into('<IIQ', data, i * 16, i + 1, 4, 0x1000 + i)
        struct.pack_into('<IIQ', data, 62 * 16, 0x800201, 0x30010, 0x12e0d9)
        with patch.object(audit, 'digest', return_value=audit.TABLE):
            audit.check_table(data)
            dup = bytearray(data)
            struct.pack_into('<I', dup, 4 * 16, 0x800201)
            with self.assertRaisesRegex(ValueError, 'unique'):
                audit.check_table(dup)
            early = bytearray(data)
            struct.pack_into('<Q', early, 5 * 16 + 8, 0)
            with self.assertRaisesRegex(ValueError, 'termination'):
                audit.check_table(early)

    def test_local_relocation_requires_text_section_and_exact_site(self):
        data = bytearray(120)
        struct.pack_into('<II', data, 16, 1, 80)
        fields = [11, 80] + [0] * 16 + [112, 1]
        struct.pack_into('<20I', data, 32, *fields)
        struct.pack_into('<II', data, 112, 0x28a758, 0x06000001)
        audit.local_relocation(data, 0x28a758)
        struct.pack_into('<I', data, 116, 0x06000002)
        with self.assertRaisesRegex(ValueError, 'local text relocation'):
            audit.local_relocation(data, 0x28a758)

    def test_wrong_image_and_bundle_refused(self):
        with self.assertRaisesRegex(ValueError, 'image/evidence pin'):
            audit.inspect(b'', b'')

if __name__ == '__main__':
    unittest.main()
