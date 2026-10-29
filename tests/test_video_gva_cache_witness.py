# SPDX-License-Identifier: MIT
"""CPU-only contract tests of the debugger's bounded cached-entry read."""
import contextlib
import importlib.util
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class Error:
    def __init__(self): self.ok = True
    def Success(self): return self.ok


fake_lldb = types.SimpleNamespace(SBError=Error)
path = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_cache_witness/lldb_witness.py'
with patch.dict(sys.modules, {'lldb': fake_lldb}):
    spec = importlib.util.spec_from_file_location('cache_witness', path)
    witness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(witness)


class Register:
    def __init__(self, value, valid=True): self.value, self.valid = value, valid
    def IsValid(self): return self.valid
    def GetValueAsUnsigned(self, default=0): return self.value if self.valid else default


class Process:
    def __init__(self, memory): self.memory = memory
    def ReadMemory(self, address, size, error):
        value = self.memory.get((address, size))
        if value is None: error.ok = False; return b''
        return value


class Thread:
    def __init__(self, process): self.process = process
    def GetProcess(self): return self.process
    def GetThreadID(self): return 42
    def GetFrameAtIndex(self, _): return types.SimpleNamespace(IsValid=lambda: False)


class Frame:
    def __init__(self, process, node): self.thread, self.node = Thread(process), node
    def GetThread(self): return self.thread
    def FindRegister(self, name): return Register(self.node if name == 'rax' else 0)


class Location:
    def GetBreakpoint(self): return types.SimpleNamespace(GetID=lambda: 7)


class CachedReadTest(unittest.TestCase):
    def observe(self, first, flag, missing=False):
        node, pc = 0x2000, 0x3000
        memory = {(pc, 8): b'abcdefgh', (node + 8, 1): bytes([first])}
        if not missing: memory[(node + 0x463, 1)] = bytes([flag])
        witness.EXPECTED = {7: ('after_enumeration', pc, b'abcdefgh')}
        witness.IMAGE_BASE = 0x1000
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            witness.hit(Frame(Process(memory), node), Location(), {})
        return output.getvalue()

    def test_present_and_empty_first_bytes(self):
        self.assertIn('read_ok=1 first_nonzero=1 prior_flag=0', self.observe(65, 0))
        self.assertIn('read_ok=1 first_nonzero=0 prior_flag=1', self.observe(0, 1))

    def test_unreadable_field_not_claimed(self):
        self.assertIn('read_ok=0 first_nonzero=0 prior_flag=0', self.observe(65, 1, True))


if __name__ == '__main__': unittest.main()
