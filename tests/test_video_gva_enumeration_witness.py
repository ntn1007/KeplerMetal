import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_enumeration_witness'
RUNNER_SPEC = importlib.util.spec_from_file_location('enumeration_reserved_cpu', ROOT / 'reserved_cpu.py')
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)
AUDIT_SPEC = importlib.util.spec_from_file_location('enumeration_audit', ROOT / 'audit_gva.py')
audit = importlib.util.module_from_spec(AUDIT_SPEC)
with patch.dict(sys.modules, {'reserved_cpu': runner}):
    AUDIT_SPEC.loader.exec_module(audit)


class WitnessParserTest(unittest.TestCase):
    def test_complete_event_includes_field_and_caller(self):
        line = ('KP_HW_HIT name=after_enumeration bytes_match=1 thread=8 '
                'r14_valid=1 r14=2 caller_offset=264163 field_valid=1 field=0\n')
        self.assertEqual(audit.hits(line), [('after_enumeration', 1, 8, 1, 2, 264163, 1, 0)])
        self.assertEqual(audit.hits(line.replace(' field_valid=1 field=0', '')), [])
        self.assertEqual(audit.hits('prefix ' + line), [])

    def test_terminal_receipt_must_be_unique_and_successful(self):
        self.assertEqual(runner.terminal_pid('KP_PROCESS_EXITED pid=45 code=0\n'), 45)
        for text in ('', 'KP_PROCESS_EXITED pid=45 code=1\n',
                     'KP_PROCESS_EXITED pid=45 code=0\nKP_PROCESS_EXITED pid=46 code=0\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                runner.terminal_pid(text)


if __name__ == '__main__':
    unittest.main()
