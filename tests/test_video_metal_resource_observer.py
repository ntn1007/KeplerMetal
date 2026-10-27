# SPDX-License-Identifier: MIT
import hashlib,importlib.util,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
spec=importlib.util.spec_from_file_location('metal_resource_observer',ROOT/'bridge/tools/verify_video_metal_resource_observer.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v))
def fixture(p,mode):
    for d in ('src','runtime','execution'):(p/d).mkdir()
    (p/'application').write_bytes(b'host');(p/'execution/application').write_bytes(b'signed');(p/'libResourceObserver.dylib').write_bytes(b'observer')
    for n in ('run_sdk_host.py','lab_gpu_reservation.py'):(p/'runtime'/n).write_text(n)
    frozen={'runtime/'+n:sha(p/'runtime'/n) for n in ('run_sdk_host.py','lab_gpu_reservation.py')}
    target=0 if mode=='inventory' else 1 if mode=='wrong-target' else 55;actual='control' if mode=='wrong-target' else mode;active=mode in ('control','buffer')
    inp={'mode':mode,'registry_id':target,'user_UID':501,'executable_SHA256':sha(p/'application'),'frozen':frozen,'observer_library':'/test/observer.dylib','observer_SHA256':sha(p/'libResourceObserver.dylib')}
    d={'class':'nvAccelerator','class_status':0,'registry_status':0,'registry_ID':55,'gpu_ancestor':True,'pci_registry_ID':88,'candidate':active}
    r={'mode':actual,'pid':123,'uid':501,'euid':501,'matching_status':0,'truncated':False,'target':target,'services':[d],
       'candidate_count':int(active),'pci_registry_ID':88 if active else 0,'dropped':0,'observer_inflight_final':0,
       'scalar_values_recorded':False,'payload_bytes_recorded':False,'explicit_GPU_commands':0,'hardware_video_execution_proved':False,'events':[],
       'status':'INVENTORY_ONLY' if mode=='inventory' else 'TARGET_NOT_QUALIFIED' if mode=='wrong-target' else 'CONTROL_RECORDED' if mode=='control' else 'BUFFER_RELEASED'}
    if mode=='control':
        r.update(null_method_status=-1,null_struct_status=-1,control_open_status=0,control_close_status=0,control_connection=True)
        r['events']=[{'kind':'method','port':0,'status':0xffffffff,'type_or_selector':0,'service_registry_ID':0},{'kind':'struct','port':0,'status':0xffffffff,'type_or_selector':0,'service_registry_ID':0},{'kind':'open','port':17,'status':0,'type_or_selector':3,'service_registry_ID':55},{'kind':'close','port':17,'status':0,'type_or_selector':0,'service_registry_ID':0}]
    if mode=='buffer':r.update(metal_candidates=1,metal_registry_ID=55,metal_pci_registry_ID=88,buffer_created=True,cpu_bytes_correct=True)
    m={'exit_code':0,'SIGKILL_requested':False,'authoritative_ps_status':'','pid':123,'original_binary_sha256':sha(p/'application'),
       'signed_binary_sha256':sha(p/'execution/application'),'launcher_SHA256':frozen['runtime/run_sdk_host.py'],
       'reservation_module_SHA256':frozen['runtime/lab_gpu_reservation.py'],'arguments':[actual,str(target)],'dependency_listing':'/test/observer.dylib',
       'GPU_reservation':{'state':'terminal','exit_code':0,'child_PID':123,'known_signed_processes_live':[],'signed_binary_sha256':sha(p/'execution/application')}}
    put(p/'inputs.json',inp);put(p/'results.json',r);put(p/'execution/execution.stdout',r);put(p/'execution/manifest.json',m);return r
class ObserverTests(unittest.TestCase):
    def test_known_modes(self):
        for mode in ('inventory','wrong-target','control','buffer'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as t:
                p=Path(t);fixture(p,mode);self.assertEqual(mod.verify(p)['verification'],'PASS')
    def test_missing_method_control_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);r=fixture(p,'control');r['events']=[e for e in r['events'] if e['kind']!='struct'];put(p/'results.json',r);put(p/'execution/execution.stdout',r)
            with self.assertRaises(AssertionError):mod.verify(p)
    def test_false_buffer_and_dropped_events_rejected(self):
        for key,value in [('cpu_bytes_correct',False),('dropped',1),('metal_pci_registry_ID',99)]:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as t:
                p=Path(t);r=fixture(p,'buffer');r[key]=value;put(p/'results.json',r);put(p/'execution/execution.stdout',r)
                with self.assertRaises(AssertionError):mod.verify(p)

    def test_audit_refuses_missing_create_and_overlapping_runs(self):
        import audit_video_metal_resource_observer as audit
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); paths=[]
            for n,mode in enumerate(('control','buffer','buffer')):
                p=root/str(n);p.mkdir();r=fixture(p,mode);i=json.loads((p/'inputs.json').read_text());m=json.loads((p/'execution/manifest.json').read_text())
                i['build_inputs_SHA256']='common';m['pid']=r['pid']=123+n;m['GPU_reservation']['child_PID']=123+n
                m['started_at']=f'2026-10-27T00:00:0{n*2}+00:00';m['completed_at']=f'2026-10-27T00:00:0{n*2+1}+00:00'
                if mode=='buffer':
                    r['events']=[{'kind':'open','port':17,'status':0,'type_or_selector':6,'service_registry_ID':55},
                                 {'kind':'method','port':17,'status':0,'type_or_selector':0,'service_registry_ID':0,'input_scalar_count':0,'input_struct_bytes':168,'caller_image':'/IOAccelerator','caller_symbol':'IOAccelResourceCreate','phase':2}]
                put(p/'inputs.json',i);put(p/'results.json',r);put(p/'execution/execution.stdout',r);put(p/'execution/manifest.json',m);put(p/'verification-execution.json',{'exit_code':0});paths.append(p)
            with patch.object(audit.subprocess,'run'):
                self.assertEqual(audit.audit(paths)['audit'],'PASS')
                r=json.loads((paths[1]/'results.json').read_text());r['events'].pop();put(paths[1]/'results.json',r);put(paths[1]/'execution/execution.stdout',r)
                with self.assertRaisesRegex(ValueError,'No matching resource create'): audit.audit(paths)
                m=json.loads((paths[1]/'execution/manifest.json').read_text());m['started_at']='2026-10-27T00:00:00+00:00';put(paths[1]/'execution/manifest.json',m)
                with self.assertRaisesRegex(ValueError,'overlapped'): audit.audit(paths)
if __name__=='__main__':unittest.main()
