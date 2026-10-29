# SPDX-License-Identifier: MIT
import importlib.util
import struct
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class Error:
    def __init__(self):self.ok=True
    def Success(self):return self.ok


with patch.dict(sys.modules,{'lldb':types.SimpleNamespace(SBError=Error,LLDB_INVALID_ADDRESS=(1<<64)-1)}):
    path=Path(__file__).resolve().parents[1]/'bridge/experiments/video_gva_heap_track/lldb_target.py'
    spec=importlib.util.spec_from_file_location('heap_target_witness',path)
    target=importlib.util.module_from_spec(spec);spec.loader.exec_module(target)


class Process:
    def __init__(self,value=1,unreadable=False):self.value=value;self.unreadable=unreadable;self.writes=0
    def ReadMemory(self,address,size,error):
        if self.unreadable:error.ok=False;return b''
        return struct.pack('<Q',self.value)
    def WriteMemory(self,address,data,error):
        self.writes+=1;self.value=struct.unpack('<Q',data)[0];return len(data)


class HeapTargetTest(unittest.TestCase):
    def test_sentinel_handoff_and_duplicate_refusal(self):
        p=Process();self.assertTrue(target.set_target(p,0x1000,0x1234));self.assertEqual(p.value,0x1234)
        self.assertFalse(target.set_target(p,0x1000,0x5678));self.assertEqual(p.writes,1)
    def test_null_and_unreadable_rejected_without_write(self):
        p=Process();self.assertFalse(target.set_target(p,0x1000,0));self.assertEqual(p.writes,0)
        p=Process(unreadable=True);self.assertFalse(target.set_target(p,0x1000,0x1234));self.assertEqual(p.writes,0)


if __name__=='__main__':unittest.main()
