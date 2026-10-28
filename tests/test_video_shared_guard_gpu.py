# SPDX-License-Identifier: MIT
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shared_guard_audit',ROOT/'bridge/experiments/video_shared_guard_gpu/audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SharedGuardAuditTests(unittest.TestCase):
 def test_gpu_and_negative_capture_and_corruption(self):
  expected=[m.SENTINEL]*16+[((i*1664525)&0xffffffff)^m.SEED for i in range(4096)]+[m.SENTINEL]*16
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'capture';p.write_bytes(struct.pack('<4128I',*expected));m.check_capture(p,False)
   with self.assertRaises(ValueError):m.check_capture(p,True)
   expected[16+17]^=1;p.write_bytes(struct.pack('<4128I',*expected))
   with self.assertRaises(ValueError):m.check_capture(p,False)
   expected=[m.SENTINEL]*4128;p.write_bytes(struct.pack('<4128I',*expected));m.check_capture(p,True)
   expected[0]^=1;p.write_bytes(struct.pack('<4128I',*expected))
   with self.assertRaises(ValueError):m.check_capture(p,True)
if __name__=='__main__':unittest.main()
