# SPDX-License-Identifier: MIT
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('compute_audit',ROOT/'bridge/experiments/video_provider_compute/audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ComputeAuditTests(unittest.TestCase):
 def test_failure_not_silently_treated_as_success(self):
  x={'attempted':True,'library':True,'function':True,'pipeline':True,'queue':False,'buffer':False,'written':False,'submitted':False,'completed':False,'errors':0,'guard_errors':0}
  m.check_phase(x,failure=True,skip=False)
  with self.assertRaises(ValueError):m.check_phase(x,failure=False,skip=False)
  x['queue']=True
  with self.assertRaises(ValueError):m.check_phase(x,failure=True,skip=False)
 def test_independent_oracle_rejects_corruption(self):
  seed=0x12345678;values=[m.SENTINEL]*16+[((i*1664525)&0xffffffff)^seed for i in range(4096)]+[m.SENTINEL]*16
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'out';p.write_bytes(struct.pack('<4128I',*values));self.assertEqual(m.check_words(p,seed,False),4096)
   values[50]^=1;p.write_bytes(struct.pack('<4128I',*values))
   with self.assertRaises(ValueError):m.check_words(p,seed,False)
   values[50]^=1;values[0]^=1;p.write_bytes(struct.pack('<4128I',*values))
   with self.assertRaises(ValueError):m.check_words(p,seed,False)
if __name__=='__main__':unittest.main()
