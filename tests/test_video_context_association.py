# SPDX-License-Identifier: MIT
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('association_oracle',ROOT/'bridge/tools/verify_video_context_association.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
def write(p,v):p.write_text(json.dumps(v))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def fixture(p,mode,refused=False):
    for d in ('src','runtime','execution'):(p/d).mkdir()
    (p/'application').write_bytes(b'host');(p/'execution/application').write_bytes(b'signed')
    for n in ('run_sdk_host.py','lab_gpu_reservation.py'):(p/'runtime'/n).write_text(n)
    frozen={'runtime/'+n:sha(p/'runtime'/n) for n in ('run_sdk_host.py','lab_gpu_reservation.py')}
    target=0 if mode=='inventory' else 1 if mode=='wrong-target' else 55
    actual='pair' if mode=='wrong-target' else mode;opened=mode in ('pair','attach');attached=mode=='attach'
    inp={'mode':mode,'registry_id':target,'user_UID':501,'executable_SHA256':sha(p/'application'),'frozen':frozen}
    dev={'class':'nvAccelerator','class_status':0,'registry_status':0,'registry_ID':55,'gpu_ancestor':True,'pci_registry_ID':88,'candidate':opened}
    r={'mode':actual,'pid':123,'uid':501,'euid':501,'matching_status':0,'truncated':False,'target':target,'services':[dev],
       'candidate_count':int(opened),'pci_registry_ID':88 if opened else 0,'metal_enumeration_attempted':opened,
       'metal_candidates':int(opened),'metal_registry_ID':55 if opened else 0,'metal_pci_registry_ID':88 if opened else 0,
       'context_open_attempts':int(opened),'shared_open_attempts':int(opened),'context_returned':opened,'shared_returned':opened,
       'context_close_attempts':int(opened),'shared_close_attempts':int(opened),'handles_distinct':opened,
       'association_attempts':int(attached),'explicit_selector_calls':0,'explicit_GPU_commands':0,'hardware_video_execution_proved':False,
       'status':'INVENTORY_ONLY' if mode=='inventory' else 'TARGET_NOT_QUALIFIED' if mode=='wrong-target' else 'PAIR_OPEN' if mode=='pair' else 'ASSOCIATION_REFUSED' if refused else 'ASSOCIATION_ACCEPTED'}
    if opened:r.update(context_open_status=0,shared_open_status=0,context_close_status=0,shared_close_status=0)
    if attached:r.update(association_status=-536870201 if refused else 0)
    m={'exit_code':0,'SIGKILL_requested':False,'authoritative_ps_status':'','pid':123,'original_binary_sha256':sha(p/'application'),
       'signed_binary_sha256':sha(p/'execution/application'),'launcher_SHA256':frozen['runtime/run_sdk_host.py'],
       'reservation_module_SHA256':frozen['runtime/lab_gpu_reservation.py'],'arguments':[actual,str(target)],
       'GPU_reservation':{'state':'terminal','exit_code':0,'child_PID':123,'known_signed_processes_live':[],'signed_binary_sha256':sha(p/'execution/application')}}
    write(p/'inputs.json',inp);write(p/'results.json',r);write(p/'execution/execution.stdout',r);write(p/'execution/manifest.json',m)
    return r,m

class AssociationTests(unittest.TestCase):
    def test_outcomes(self):
        for mode,refused,outcome in [('inventory',False,'CONTROL_PASS'),('wrong-target',False,'CONTROL_PASS'),('pair',False,'PAIR_OPEN_CLOSED'),('attach',False,'ASSOCIATION_ACCEPTED'),('attach',True,'ASSOCIATION_REFUSED')]:
            with self.subTest(mode=mode,refused=refused),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);fixture(p,mode,refused);self.assertEqual(oracle.verify(p)['outcome'],outcome)
    def test_rejects_invalid_lifetime_and_identity(self):
        for field,value in [('context_close_status',1),('shared_close_attempts',0),('handles_distinct',False),('metal_pci_registry_ID',99),('explicit_selector_calls',1)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);r,_=fixture(p,'attach');r[field]=value;write(p/'results.json',r);write(p/'execution/execution.stdout',r)
                with self.assertRaises(AssertionError):oracle.verify(p)
    def test_unresolved_reservation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);_,m=fixture(p,'attach');m['GPU_reservation']['state']='unresolved';write(p/'execution/manifest.json',m)
            with self.assertRaises(AssertionError):oracle.verify(p)

if __name__=='__main__':unittest.main()
