import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_list_witness'
RUNNER_SPEC = importlib.util.spec_from_file_location('list_reserved_cpu', ROOT / 'reserved_cpu.py')
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)
AUDIT_SPEC = importlib.util.spec_from_file_location('list_audit', ROOT / 'audit_gva.py')
audit = importlib.util.module_from_spec(AUDIT_SPEC)
with patch.dict(sys.modules, {'reserved_cpu': runner}):
    AUDIT_SPEC.loader.exec_module(audit)


class ListWitnessParserTest(unittest.TestCase):
    def test_node_requires_all_flags_and_link_status(self):
        line = ('KP_LIST_NODE caller_offset=146279 thread=8 index=0 kind=17039368 '
                'flags=1,0,0,0 next_present=0\n')
        self.assertEqual(audit.list_rows(line), [(146279, 8, 0, 17039368, 1, 0, 0, 0, 0)])
        self.assertEqual(audit.list_rows(line.replace(' next_present=0', '')), [])
        self.assertEqual(audit.list_rows('prefix ' + line), [])

    def test_hit_requires_list_and_output_fields(self):
        line = ('KP_HW_HIT name=list_entry bytes_match=1 thread=8 r14_valid=1 r14=2 '
                'caller_offset=146279 field_valid=0 field=0 list_valid=1 head_present=1 flag=0 selector=2\n')
        self.assertEqual(audit.hits(line), [('list_entry', 1, 8, 1, 2, 146279, 0, 0, 1, 1, 0, 2)])
        self.assertEqual(audit.hits(line.replace(' selector=2', '')), [])


if __name__ == '__main__':
    unittest.main()
