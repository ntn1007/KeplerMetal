# SPDX-License-Identifier: MIT
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_classlist/device_audit.py'
spec = importlib.util.spec_from_file_location('device_audit', path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class DeviceAuditTests(unittest.TestCase):
    def test_header_rejects_changed_class_or_alignment(self):
        text = ('#define NV01_DEVICE_0 (0x00000080)\n'
                'typedef struct { NvU32 deviceId; NvHandle hClientShare; '
                'NvHandle hTargetClient; NvHandle hTargetDevice; NvV32 flags; '
                'NvU64 vaSpaceSize NV_ALIGN_BYTES(8); NvU64 vaStartInternal NV_ALIGN_BYTES(8); '
                'NvU64 vaLimitInternal NV_ALIGN_BYTES(8); NvV32 vaMode; } NV0080_ALLOC_PARAMETERS;')
        self.assertIn('deviceId', audit.header_declaration(text))
        for bad in (text.replace('0x00000080', '0x00000081'),
                    text.replace('vaSpaceSize NV_ALIGN_BYTES(8)', 'vaSpaceSize NV_ALIGN_BYTES(4)')):
            with self.assertRaises(ValueError):
                audit.header_declaration(bad)

    def test_unpinned_inputs_refused(self):
        with self.assertRaisesRegex(ValueError, 'input identities'):
            audit.inspect(b'', b'', b'', b'', b'', b'')

if __name__ == '__main__':
    unittest.main()
