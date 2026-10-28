# SPDX-License-Identifier: MIT
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'));spec=importlib.util.spec_from_file_location('property_branch',ROOT/'bridge/experiments/video_gva_property_observer/branch_audit.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class BranchTests(unittest.TestCase):
 def setUp(self):
  self.start=150800;self.data=bytearray(80)
  for off,value in [(150807,b'\xe8'),(150812,b'\x48\x85\xc0'),(150815,b'\x74\x29'),(150821,b'\xc6\x86\x63\x04\x00\x00\x01'),(150845,b'\xe8')]:self.data[off-self.start:off-self.start+len(value)]=value
 def test_branch_target(self):self.assertEqual(mod.branch(self.data,self.start)['null_branch_target'],150858)
 def test_corrupt_instruction_and_target_refused(self):
  for off in (150812,150815,150816,150821,150845):
   data=self.data.copy();data[off-self.start]^=1
   with self.subTest(offset=off),self.assertRaises(ValueError):mod.branch(data,self.start)
if __name__=='__main__':unittest.main()
