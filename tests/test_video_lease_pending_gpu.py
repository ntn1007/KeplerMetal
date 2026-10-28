# SPDX-License-Identifier: MIT
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pending_audit',ROOT/'bridge/experiments/video_lease_pending_gpu/audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
class PendingAuditTests(unittest.TestCase):
 def test_pending_gating_and_negative_controls(self):
  before={'command_status':2,'gate_value':0,'watchdog_state':0,'changed_words':0}
  done={'normal_signal':True,'watchdog_state':1,'gate_value':1,'command_status':4,'dispatch_encoded':True,'errors':0,'guard_errors':0,'written':True}
  audit.check_pending(before,before,done,False)
  for changed in ({'command_status':4},{'gate_value':1},{'watchdog_state':2},{'changed_words':1}):
   with self.assertRaises(ValueError):audit.check_pending(before,{**before,**changed},done,False)
  for changed in ({'normal_signal':False},{'watchdog_state':2},{'command_status':3},{'errors':1},{'guard_errors':1},{'written':False}):
   with self.assertRaises(ValueError):audit.check_pending(before,before,{**done,**changed},False)
  with self.assertRaises(ValueError):audit.check_pending(before,before,done,True)
  audit.check_pending(before,before,{**done,'dispatch_encoded':False},True)
 def test_raw_result_oracle_and_sentinel(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'capture'; v=[audit.SENTINEL]*16+[((i*1664525)&0xffffffff)^audit.SEED for i in range(4096)]+[audit.SENTINEL]*16
   p.write_bytes(struct.pack('<4128I',*v));audit.check_capture(p,False)
   with self.assertRaises(ValueError):audit.check_capture(p,True)
   v[20]^=1;p.write_bytes(struct.pack('<4128I',*v))
   with self.assertRaises(ValueError):audit.check_capture(p,False)
   v=[audit.SENTINEL]*4128;p.write_bytes(struct.pack('<4128I',*v));audit.check_capture(p,True)
   v[0]^=1;p.write_bytes(struct.pack('<4128I',*v))
   with self.assertRaises(ValueError):audit.check_capture(p,True)
if __name__=='__main__':unittest.main()
