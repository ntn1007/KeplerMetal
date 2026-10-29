# SPDX-License-Identifier: MIT
import importlib.util
import struct
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class Error:
    def __init__(self): self.ok=True
    def Success(self): return self.ok


with patch.dict(sys.modules,{'lldb':types.SimpleNamespace(SBError=Error),'lldb_witness':types.SimpleNamespace()}):
    path=Path(__file__).resolve().parents[1]/'bridge/experiments/video_gva_heap_binding/lldb_binding.py'
    spec=importlib.util.spec_from_file_location('heap_binding_witness',path)
    binding=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding)


class Process:
    def __init__(self,value):self.value=value
    def ReadMemory(self,address,size,error):
        if self.value is None:error.ok=False;return b''
        return struct.pack('<Q',self.value)


class BindingTest(unittest.TestCase):
    def test_match_mismatch_and_unreadable(self):
        self.assertTrue(binding.inspect(Process(123),0x1000,123))
        self.assertFalse(binding.inspect(Process(124),0x1000,123))
        self.assertIsNone(binding.inspect(Process(None),0x1000,123))


if __name__=='__main__':unittest.main()
