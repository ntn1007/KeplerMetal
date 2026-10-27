# SPDX-License-Identifier: MIT
"""Synthetic negative controls for the offline video-context oracle."""
import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('video_oracle',ROOT/'bridge/tools/verify_video_shared_current.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)

def write(p,value):p.write_text(json.dumps(value))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def fixture(p,mode):
    for d in ('src','runtime','execution'):(p/d).mkdir()
    (p/'application').write_bytes(b'synthetic host');(p/'execution/application').write_bytes(b'synthetic signed host')
    for n in ('run_sdk_host.py','lab_gpu_reservation.py'):(p/'runtime'/n).write_text(n)
    frozen={'runtime/'+n:digest(p/'runtime'/n) for n in ('run_sdk_host.py','lab_gpu_reservation.py')}
    target=0 if mode=='inventory' else 1 if mode=='wrong-target' else 55
    realmode='inventory' if mode=='inventory' else 'shared'
    inp={'mode':mode,'registry_id':target,'user_UID':501,'executable_SHA256':digest(p/'application'),'frozen':frozen}
    device={'class':'nvAccelerator','vendor_ID':0x10de,'device_ID':0x1198,'class_status':0,'registry_status':0,'name_status':0,'registry_ID':55,'candidate':mode=='shared'}
    row={'mode':realmode,'pid':123,'uid':501,'euid':501,'matching_status':0,'truncated':False,'user_client_type':6,'special_exclusive_type_used':False,'external_method_calls':0,'GPU_commands_submitted':0,'hardware_video_execution_proved':False,'system_modified':False,'services':[device],'requested_registry_ID':target,'candidate_count':int(mode=='shared'),'status':'OPEN_CLOSED' if mode=='shared' else 'INVENTORY_ONLY' if mode=='inventory' else 'TARGET_NOT_QUALIFIED','open_attempts':int(mode=='shared'),'close_attempts':int(mode=='shared'),'connection_returned':mode=='shared'}
    if mode=='shared':row.update(open_status=0,close_status=0)
    m={'exit_code':0,'SIGKILL_requested':False,'authoritative_ps_status':'','pid':123,'original_binary_sha256':digest(p/'application'),'signed_binary_sha256':digest(p/'execution/application'),'launcher_SHA256':frozen['runtime/run_sdk_host.py'],'reservation_module_SHA256':frozen['runtime/lab_gpu_reservation.py'],'arguments':[realmode,str(target)],'GPU_reservation':{'state':'terminal','exit_code':0,'child_PID':123,'known_signed_processes_live':[],'signed_binary_sha256':digest(p/'execution/application')}}
    write(p/'inputs.json',inp);write(p/'results.json',row);write(p/'execution/execution.stdout',row);write(p/'execution/manifest.json',m)
    return row,m

class VideoSharedOracleTests(unittest.TestCase):
    def test_three_valid_contracts(self):
        for mode in ('inventory','wrong-target','shared'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp);fixture(p,mode);self.assertEqual(oracle.verify(p)['status'],'PASS')
    def test_failed_close_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r,_=fixture(p,'shared');r['close_status']=1;write(p/'results.json',r);write(p/'execution/execution.stdout',r)
            with self.assertRaises(AssertionError):oracle.verify(p)
    def test_wrong_pci_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r,_=fixture(p,'shared');r['services'][0]['device_ID']=0x1180;write(p/'results.json',r);write(p/'execution/execution.stdout',r)
            with self.assertRaises(AssertionError):oracle.verify(p)
    def test_unfinished_reservation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);_,m=fixture(p,'shared');m['GPU_reservation']['state']='running';write(p/'execution/manifest.json',m)
            with self.assertRaises(AssertionError):oracle.verify(p)
    def test_external_method_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r,_=fixture(p,'shared');r['external_method_calls']=1;write(p/'results.json',r);write(p/'execution/execution.stdout',r)
            with self.assertRaises(AssertionError):oracle.verify(p)

    def test_refusal_is_observation_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r,_=fixture(p,'shared')
            r.update(status='OPEN_REFUSED', open_status=-536870201, close_attempts=0, connection_returned=False)
            r.pop('close_status');write(p/'results.json',r);write(p/'execution/execution.stdout',r)
            with self.assertRaises(AssertionError):oracle.verify(p)
            self.assertEqual(oracle.verify(p,allow_refusal=True)['status'],'OBSERVED_REFUSAL')
            r['connection_returned']=True;write(p/'results.json',r);write(p/'execution/execution.stdout',r)
            with self.assertRaises(AssertionError):oracle.verify(p,allow_refusal=True)

if __name__=='__main__':unittest.main()
