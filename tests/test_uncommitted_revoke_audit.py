# SPDX-License-Identifier: MIT
import importlib.util,struct,tempfile,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('revoke_audit',root/'bridge/experiments/uncommitted_revoke/audit.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class RevokeAuditTests(unittest.TestCase):
 def base(self):
  return {'mode':'revoked','device_candidates':1,'registry_id':4294968416,'native_class':'NVMTLCommandBuffer','initial_status':0,'initial_untouched':True,'completed':True,'late_revoke_refused':True,'written':True,'errors':0,'guard_errors':0,'system_modified':False,'guard_installed':True,'commit_blocked':True,'enqueue_blocked':True,'second_commit_blocked':True,'stale_final_status':0,'dispatches':1}
 def test_rejects_missed_revocation_or_unexpected_submission(self):
  x=self.base();a.classify(x,'revoked')
  for name,value in [('guard_installed',False),('commit_blocked',False),('enqueue_blocked',False),('second_commit_blocked',False),('stale_final_status',4),('late_revoke_refused',False),('initial_untouched',False),('errors',1),('dispatches',0)]:
   with self.assertRaises(ValueError):a.classify({**x,name:value},'revoked')
 def test_capture_rejects_stale_execution_and_guard_corruption(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x';v=[a.SENTINEL]*16+[a.VALUES['revoked']^i for i in range(4096)]+[a.SENTINEL]*16;p.write_bytes(struct.pack('<4128I',*v));a.capture(p,'revoked')
   v[32]=a.VALUES['native']^16;p.write_bytes(struct.pack('<4128I',*v))
   with self.assertRaises(ValueError):a.capture(p,'revoked')
   v=[a.SENTINEL]*4128;p.write_bytes(struct.pack('<4128I',*v));a.capture(p,'revoked-negative')
   v[0]^=1;p.write_bytes(struct.pack('<4128I',*v))
   with self.assertRaises(ValueError):a.capture(p,'revoked-negative')
if __name__=='__main__':unittest.main()
