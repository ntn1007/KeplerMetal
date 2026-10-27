# SPDX-License-Identifier: MIT
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from launch_certified_cas import prepare

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class LaunchPreflight(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.assets=self.root/'assets';self.assets.mkdir()
  self.exe=self.root/'client';self.exe.write_bytes(b'client');self.boot=self.root/'bootstrap';self.boot.write_bytes(b'bootstrap')
  (self.assets/'library').write_bytes(b'library');rows=[]
  for n in range(5):
   p=self.assets/f'cert{n}';p.write_bytes(f'cert{n}'.encode());rows.append({'function':f'f{n}','certificate':p.name,'certificate_SHA256':sha(p)})
  (self.assets/'client-manifest.json').write_text(json.dumps({'library':'library','library_SHA256':sha(self.assets/'library'),'profiles':rows}))
  self.policy=self.root/'policy';self.policy.write_text(json.dumps({'version':1,'allowed_clients':[sha(self.exe)]}));self.calls=[]
 def tearDown(self):self.tmp.cleanup()
 def check(self):return prepare(self.exe,self.boot,sha(self.boot),self.assets,self.policy,sha(self.policy),signature_check=lambda p:self.calls.append(p.name))
 def test_valid(self):
  r=self.check();self.assertEqual(r['executable_SHA256'],sha(self.exe));self.assertEqual(self.calls,['client','bootstrap'])
 def test_unlisted_and_duplicate(self):
  for values in [['0'*64],[sha(self.exe),sha(self.exe)]]:
   self.policy.write_text(json.dumps({'version':1,'allowed_clients':values}))
   with self.assertRaises(ValueError):self.check()
 def test_malformed_and_tamper(self):
  self.policy.write_text('[]')
  with self.assertRaises(ValueError):self.check()
  self.policy.write_text(json.dumps({'version':1,'allowed_clients':[sha(self.exe)]}));(self.assets/'cert1').write_bytes(b'changed')
  with self.assertRaises(ValueError):self.check()
 def test_asset_escape(self):
  manifest=self.assets/'client-manifest.json';d=json.loads(manifest.read_text());d['profiles'][0]['certificate']='../client';manifest.write_text(json.dumps(d))
  with self.assertRaises(ValueError):self.check()
  d['profiles'][0]['certificate']='link';manifest.write_text(json.dumps(d));(self.assets/'link').symlink_to(self.exe)
  with self.assertRaises(ValueError):self.check()
 def test_mismatched_policy_digest_and_signature(self):
  with self.assertRaises(ValueError):prepare(self.exe,self.boot,sha(self.boot),self.assets,self.policy,'0'*64,signature_check=lambda p:None)
  def refuse(p):raise ValueError('signature failure')
  with self.assertRaises(ValueError):prepare(self.exe,self.boot,sha(self.boot),self.assets,self.policy,sha(self.policy),signature_check=refuse)

class LaunchLifecycle(unittest.TestCase):
 def test_local_terminal_receipt_and_private_logs(self):
  from unittest.mock import patch
  import launch_certified_cas as module
  class FakeLease:
   last=None
   def __init__(self,root):self.fd=123;self.data={};FakeLease.last=self
   def spawning(self,path,digest):self.data.update(state='spawning',signed_executable=path,signed_binary_sha256=digest)
   def bind_child(self,pid):self.data.update(state='running',child_PID=pid)
   def finish(self,code,killed,status):self.data.update(state='terminal' if code is not None and not killed and not status else 'unresolved',exit_code=code,authoritative_ps_status=status)
   def close(self):self.closed=True
  class FakeChild:
   pid=1234
   def wait(self):return 0
  class FakePS:stdout=''
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'results').mkdir();exe=root/'app';exe.write_bytes(b'app');boot=root/'boot';boot.write_bytes(b'boot');pol=root/'policy';pol.write_bytes(b'policy')
   prepared={'executable':str(exe),'executable_SHA256':sha(exe),'bootstrap':str(boot),'bootstrap_SHA256':sha(boot),'policy':str(pol),'policy_SHA256':sha(pol),'assets':str(root),'inputs':{str(exe):sha(exe),str(boot):sha(boot),str(pol):sha(pol)}}
   receipt=root/'receipt'
   with patch.object(module,'check_profile',return_value={'test':True}),patch.object(module,'GPUReservation',FakeLease),patch.object(module.subprocess,'Popen',return_value=FakeChild()) as spawn,patch.object(module.subprocess,'run',return_value=FakePS()):
    result=module.launch(prepared,'optin',['private-argument'],root,receipt)
   self.assertEqual(result['status'],'TERMINAL');self.assertTrue(FakeLease.last.closed);self.assertEqual(result['GPU_reservation']['child_PID'],1234)
   self.assertEqual(spawn.call_args.kwargs['env']['DYLD_INSERT_LIBRARIES'],str(boot));self.assertNotIn('private-argument',(receipt/'manifest.json').read_text());self.assertEqual((receipt/'execution.stdout').stat().st_mode & 0o777,0o600)
 def test_spawn_failure_leaves_terminal_reservation(self):
  from unittest.mock import patch
  import launch_certified_cas as module
  class FakeLease:
   last=None
   def __init__(self,root):self.fd=123;self.data={};FakeLease.last=self
   def spawning(self,path,digest):self.data['state']='spawning'
   def finish(self,code,killed,status):self.data.update(state='terminal' if code is not None and not killed and not status else 'unresolved',exit_code=code)
   def close(self):self.closed=True
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'results').mkdir();exe=root/'app';exe.write_bytes(b'app');boot=root/'boot';boot.write_bytes(b'boot');pol=root/'policy';pol.write_bytes(b'policy')
   prepared={'executable':str(exe),'executable_SHA256':sha(exe),'bootstrap':str(boot),'bootstrap_SHA256':sha(boot),'policy':str(pol),'policy_SHA256':sha(pol),'assets':str(root),'inputs':{str(exe):sha(exe)}}
   with patch.object(module,'check_profile',return_value={}),patch.object(module,'GPUReservation',FakeLease),patch.object(module.subprocess,'Popen',side_effect=OSError('spawn failed')):
    with self.assertRaises(OSError):module.launch(prepared,'native',[],root,root/'receipt')
   self.assertEqual(FakeLease.last.data['state'],'terminal');self.assertTrue(FakeLease.last.closed)

 def test_interrupted_wait_stays_unresolved_without_kill(self):
  from unittest.mock import patch
  import launch_certified_cas as module
  class FakeLease:
   last=None
   def __init__(self,root):self.fd=123;self.data={};FakeLease.last=self
   def spawning(self,path,digest):self.data['state']='spawning'
   def bind_child(self,pid):self.data['state']='running'
   def finish(self,code,killed,status):self.data.update(state='terminal' if code is not None and not killed and not status else 'unresolved',kill_requested=killed)
   def close(self):self.closed=True
  class FakeChild:
   pid=1234
   def wait(self):raise KeyboardInterrupt()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'results').mkdir();exe=root/'app';exe.write_bytes(b'app');boot=root/'boot';boot.write_bytes(b'boot');pol=root/'policy';pol.write_bytes(b'policy')
   prepared={'executable':str(exe),'executable_SHA256':sha(exe),'bootstrap':str(boot),'bootstrap_SHA256':sha(boot),'policy':str(pol),'policy_SHA256':sha(pol),'assets':str(root),'inputs':{str(exe):sha(exe)}}
   with patch.object(module,'check_profile',return_value={}),patch.object(module,'GPUReservation',FakeLease),patch.object(module.subprocess,'Popen',return_value=FakeChild()):
    with self.assertRaises(KeyboardInterrupt):module.launch(prepared,'native',[],root,root/'receipt')
   self.assertEqual(FakeLease.last.data['state'],'unresolved');self.assertFalse(FakeLease.last.data['kill_requested']);self.assertTrue(FakeLease.last.closed)

if __name__=='__main__':unittest.main()
