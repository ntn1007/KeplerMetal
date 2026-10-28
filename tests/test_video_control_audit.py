# SPDX-License-Identifier: MIT
import importlib.util
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_classlist/control_audit.py'
spec = importlib.util.spec_from_file_location('control_audit', path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class ControlAuditTests(unittest.TestCase):
    def test_wrong_vendor_and_evidence_inputs_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'vendor input identity'):
            audit.inspect(b'', b'', b'', b'')
        with patch.object(audit, 'NVDA', audit.sha(b'nvda')), \
             patch.object(audit, 'CUDA', audit.sha(b'cuda')):
            with self.assertRaisesRegex(ValueError, 'REA evidence identity'):
                audit.inspect(b'nvda', b'cuda', b'', b'')

    def test_relative_control_edge_requires_opcode_and_exact_target(self):
        source, target = 0x100, 0x200
        code = b'\xe8' + struct.pack('<i', target - source - 5)
        with patch.object(audit, 'file_bytes', return_value=(0, code)):
            audit.direct(b'', source, target)
            with self.assertRaises(ValueError):
                audit.direct(b'', source, target + 1)
            with self.assertRaises(ValueError):
                audit.direct(b'', source, target, 0xe9)

if __name__ == '__main__':
    unittest.main()
