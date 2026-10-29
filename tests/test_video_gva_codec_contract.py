import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_codec_contract/audit.py'
SPEC = importlib.util.spec_from_file_location('codec_contract_audit', PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class CodecContractTest(unittest.TestCase):
    def test_recursive_key_scan_handles_nested_personalities_and_arrays(self):
        sample = {'IOKitPersonalities': {'A': {'other': [{'IOGVACodec': 'synthetic'}]},
                                        'B': {'unrelated': 1}}}
        self.assertEqual(audit.key_paths(sample, 'IOGVACodec'),
                         [('IOKitPersonalities', 'A', 'other', '0', 'IOGVACodec')])
        self.assertEqual(audit.key_paths({'unrelated': 'IOGVACodec'}, 'IOGVACodec'), [])

    def test_unpinned_code_is_refused(self):
        with self.assertRaises(ValueError):
            audit.static_contract(bytes(2669))


if __name__ == '__main__':
    unittest.main()
