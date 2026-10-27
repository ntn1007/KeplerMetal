# SPDX-License-Identifier: MIT
import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('metal_shared_oracle',ROOT/'bridge/tools/verify_video_shared_metal.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
def write(p,v):p.write_text(json.dumps(v))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def fixture(p,mode,refused=True):
    for d in ('src','runtime','execution'):(p/d).mkdir()
    (p/'application').write_bytes(b'host');(p/'execution/application').write_bytes(b'signed host')
    for n in ('run_sdk_host.py','lab_gpu_reservation.py'):(p/'runtime'/n).write_text(n)
    frozen={'runtime/'+n:sha(p/'runtime'/n) for n in ('run_sdk_host.py','lab_gpu_reservation.py')}
    target=0 if mode=='inventory' else 1 if mode=='wrong-target' else 55
    actual='direct' if mode=='wrong-target' else mode
    opened=mode not in ('inventory','wrong-target');metal=mode in ('device','queue');queue=mode=='queue'
    inp={'mode':mode,'registry_id':target,'user_UID':501,'executable_SHA256':sha(p/'application'),'frozen':frozen}
    gpu={'class':'nvAccelerator','class_status':0,'registry_status':0,'registry_ID':55,'gpu_ancestor':True,'pci_registry_ID':88,'candidate':opened}
    r={'mode':actual,'pid':123,'uid':501,'euid':501,'matching_status':0,'truncated':False,'target':target,'services':[gpu],
       'candidate_count':int(opened),'pci_registry_ID':88 if opened else 0,'metal_enumeration_attempted':metal,'metal_candidates':int(metal),
       'metal_registry_ID':77 if metal else 0,'metal_pci_registry_ID':88 if metal else 0,'queue_attempted':queue,'queue_created':queue,'open_attempts':int(opened),
       'connection_returned':opened and not refused,'close_attempts':int(opened and not refused),'explicit_IOConnect_calls':0,
       'explicit_GPU_commands':0,'hardware_video_execution_proved':False,
       'status':('OPEN_REFUSED' if refused else 'OPEN_CLOSED') if opened else ('INVENTORY_ONLY' if mode=='inventory' else 'TARGET_NOT_QUALIFIED')}
    if opened:r.update(open_status=-536870201 if refused else 0)
    if opened and not refused:r.update(close_status=0)
    m={'exit_code':0,'SIGKILL_requested':False,'authoritative_ps_status':'','pid':123,'original_binary_sha256':sha(p/'application'),
       'signed_binary_sha256':sha(p/'execution/application'),'launcher_SHA256':frozen['runtime/run_sdk_host.py'],
       'reservation_module_SHA256':frozen['runtime/lab_gpu_reservation.py'],'arguments':[actual,str(target)],
       'GPU_reservation':{'state':'terminal','exit_code':0,'child_PID':123,'known_signed_processes_live':[],'signed_binary_sha256':sha(p/'execution/application')}}
    write(p/'inputs.json',inp);write(p/'results.json',r);write(p/'execution/execution.stdout',r);write(p/'execution/manifest.json',m)
    return r,m

class MetalSharedTests(unittest.TestCase):
    def test_controls_refusal_and_success(self):
        for mode in ('inventory','wrong-target','direct','device','queue'):
            for refused in (True,False):
                with self.subTest(mode=mode,refused=refused),tempfile.TemporaryDirectory() as tmp:
                    p=Path(tmp);fixture(p,mode,refused);o=oracle.verify(p)
                    self.assertEqual(o['outcome'],'CONTROL_PASS' if mode in ('inventory','wrong-target') else 'OPEN_REFUSED' if refused else 'OPEN_CLOSED')
    def test_mismatched_pci_queue_and_command_are_rejected(self):
        for key,value in (('pci_registry_ID',99),('metal_pci_registry_ID',99),('queue_created',False),('explicit_GPU_commands',1)):
            with self.subTest(key=key),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);r,_=fixture(p,'queue');r[key]=value;write(p/'results.json',r);write(p/'execution/execution.stdout',r)
                with self.assertRaises(AssertionError):oracle.verify(p)
    def test_unterminated_reservation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);_,m=fixture(p,'device');m['GPU_reservation']['state']='unresolved';write(p/'execution/manifest.json',m)
            with self.assertRaises(AssertionError):oracle.verify(p)

if __name__=='__main__':unittest.main()
