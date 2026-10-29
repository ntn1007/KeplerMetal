import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_property_link_witness'
spec = importlib.util.spec_from_file_location('property_link_reserved_cpu', ROOT / 'reserved_cpu.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
spec = importlib.util.spec_from_file_location('property_link_audit', ROOT / 'audit_gva.py')
audit = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'reserved_cpu': runner}):
    spec.loader.exec_module(audit)


class PropertyLinkParserTest(unittest.TestCase):
    def test_property_result_and_node_comparison_are_required(self):
        line = ('KP_HW_HIT name=property_return bytes_match=1 thread=8 r14_valid=1 r14=0 '
                'caller_offset=117072 field_valid=0 field=0 list_valid=0 head_present=0 flag=0 selector=0 '
                'prop_valid=1 prop_present=0 node_flag_valid=1 node_flag=0 link_valid=0 same_node=0\n')
        self.assertEqual(audit.hits(line), [('property_return', 1, 8, 1, 0, 117072, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0)])
        self.assertEqual(audit.hits(line.replace(' node_flag_valid=1', '')), [])
        self.assertEqual(audit.hits('prefix ' + line), [])

    def test_node_snapshot_needs_all_flags(self):
        line = ('KP_LIST_NODE caller_offset=146279 thread=8 index=0 kind=17039368 '
                'flags=1,0,0,0 next_present=0\n')
        self.assertEqual(audit.list_rows(line), [(146279, 8, 0, 17039368, 1, 0, 0, 0, 0)])
        self.assertEqual(audit.list_rows(line.replace(' next_present=0', '')), [])


if __name__ == '__main__':
    unittest.main()
