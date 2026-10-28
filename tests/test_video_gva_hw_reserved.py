import importlib.util
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_hw_witness/reserved_cpu.py'
SPEC = importlib.util.spec_from_file_location('reserved_cpu', PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
AUDIT_SPEC = importlib.util.spec_from_file_location('hw_audit', PATH.with_name('audit_gva.py'))
audit = importlib.util.module_from_spec(AUDIT_SPEC)
with patch.dict(sys.modules, {'reserved_cpu': runner}):
    AUDIT_SPEC.loader.exec_module(audit)


class TerminalReceiptTest(unittest.TestCase):
    def test_one_zero_exit(self):
        self.assertEqual(runner.terminal_pid('other\nKP_PROCESS_EXITED pid=42 code=0\n'), 42)

    def test_missing_ambiguous_or_failed_is_refused(self):
        for value in ('', 'KP_PROCESS_EXITED pid=0 code=0\n',
                      'KP_PROCESS_EXITED pid=42 code=1\n',
                      'KP_PROCESS_EXITED pid=42 code=0\nKP_PROCESS_EXITED pid=42 code=0\n',
                      'prefix KP_PROCESS_EXITED pid=42 code=0\n'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runner.terminal_pid(value)

    def test_hit_requires_complete_machine_and_stack_fields(self):
        line = 'KP_HW_HIT name=after_base bytes_match=1 thread=8 r14_valid=1 r14=2 caller_offset=115492\n'
        self.assertEqual(audit.hits(line), [('after_base', 1, 8, 1, 2, 115492)])
        self.assertEqual(audit.hits(line.replace(' caller_offset=115492', '')), [])
        self.assertEqual(audit.hits('prefix ' + line), [])


class GuardTest(unittest.TestCase):
    def test_stopped_target_is_waited_until_exit(self):
        fake_lldb = types.SimpleNamespace(eStateExited=9)
        path = PATH.with_name('lldb_guard.py')
        spec = importlib.util.spec_from_file_location('test_lldb_guard', path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'lldb': fake_lldb}):
            spec.loader.exec_module(module)
        class Process:
            def __init__(self): self.states = iter((5, 5, 9))
            def IsValid(self): return True
            def GetProcessID(self): return 73
            def GetState(self): return next(self.states)
            def GetExitStatus(self): return 0
        process = Process()
        target = types.SimpleNamespace(GetProcess=lambda: process)
        debugger = types.SimpleNamespace(GetSelectedTarget=lambda: target)
        output = io.StringIO()
        with patch.object(module.time, 'sleep') as sleep, redirect_stdout(output):
            module.await_terminal(debugger)
        sleep.assert_called_once_with(5)
        self.assertIn('KP_GUARD_UNRESOLVED pid=73', output.getvalue())
        self.assertIn('KP_PROCESS_EXITED pid=73 code=0', output.getvalue())


if __name__ == '__main__':
    unittest.main()
