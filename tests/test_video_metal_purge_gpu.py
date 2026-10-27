# SPDX-License-Identifier: MIT
import array,hashlib,importlib.util,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge/tools'))
spec=importlib.util.spec_from_file_location('purge_gpu_oracle',ROOT/'bridge/tools/verify_video_metal_purge_gpu.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v))
def fixture(p,mode):
    for d in ('src','runtime','assets','outputs','execution'):(p/d).mkdir()
    (p/'application').write_bytes(b'host');(p/'execution/application').write_bytes(b'signed');(p/'assets/resource_sync.metallib').write_bytes(b'library')
    for n in ('run_sdk_host.py','lab_gpu_reservation.py'):(p/'runtime'/n).write_text(n)
    frozen={'runtime/'+n:sha(p/'runtime'/n) for n in ('run_sdk_host.py','lab_gpu_reservation.py')}
    n=1024*1024;seed=0xfeed1234;mask=0xffffffff;neg=mode=='negative';term=(seed*747796405)&mask
    target=array.array('I',(j^0x5a39d117 if neg else ((j*1664525)&mask)^seed for j in range(n)))
    output=array.array('I',(0xa5a5a5a5 if neg else (((j^0x5a39d117)+((j*1013904223)&mask))&mask)^term for j in range(n)))
    (p/'outputs/target.bin').write_bytes(target.tobytes());(p/'outputs/output.bin').write_bytes(b'\xa5'*64+output.tobytes()+b'\xa5'*64)
    i={'mode':mode,'registry_id':55,'user_UID':501,'executable_SHA256':sha(p/'application'),'metallib_SHA256':sha(p/'assets/resource_sync.metallib'),'frozen':frozen}
    r={'mode':mode,'pid':123,'uid':501,'euid':501,'gpu_registry_id':55,'pci_registry_id':88,'elements':n,'seed':seed,'guard_bytes_each':64,'target_length':n*4,'output_length':n*4+128,'threadgroup_size':32,'pipeline_read_max_threads':1024,'pipeline_write_max_threads':1024,'state_initial':2,'state_restored':2,'previous_empty':2 if mode=='purge' else 0,'state_empty':4 if mode=='purge' else 0,'previous_restore':4 if mode=='purge' else 0,'command_submitted':not neg,'command_status':0 if neg else 4}
    m={'exit_code':0,'SIGKILL_requested':False,'authoritative_ps_status':'','pid':123,'original_binary_sha256':sha(p/'application'),'signed_binary_sha256':sha(p/'execution/application'),'launcher_SHA256':frozen['runtime/run_sdk_host.py'],'reservation_module_SHA256':frozen['runtime/lab_gpu_reservation.py'],'arguments':[mode,'55',str(p/'assets/resource_sync.metallib'),str(p/'outputs')], 'GPU_reservation':{'state':'terminal','exit_code':0,'child_PID':123,'known_signed_processes_live':[],'signed_binary_sha256':sha(p/'execution/application')}}
    put(p/'inputs.json',i);put(p/'results.json',r);put(p/'execution/execution.stdout',r);put(p/'execution/manifest.json',m);return r
class PurgeGPUOracleTests(unittest.TestCase):
    def test_gpu_read_write_and_corrupted_data_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t).resolve();fixture(p,'purge');self.assertEqual(oracle.verify(p)['outcome'],'GPU_READ_WRITE_PASS')
            with (p/'outputs/target.bin').open('r+b') as f:f.seek(4*12345);f.write(b'\0\0\0\0')
            with self.assertRaises(AssertionError):oracle.verify(p)
    def test_negative_has_no_gpu_and_guard_corruption_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t).resolve();fixture(p,'negative');result=oracle.verify(p);self.assertEqual(result['outcome'],'NEGATIVE_CONTROL_PASS');self.assertGreater(result['negative_gpu_read_mismatches'],0)
            with (p/'outputs/output.bin').open('r+b') as f:f.seek(0);f.write(b'\0')
            with self.assertRaises(AssertionError):oracle.verify(p)

    def test_cohort_rejects_different_captures_and_overlap(self):
        import audit_video_metal_purge_gpu as audit
        modes=['negative','native','purge','native','purge','native','purge'];rows={};paths=[]
        for j,mode in enumerate(modes):
            p=Path('/fake')/str(j);paths.append(p)
            v={'mode':mode,'outcome':'NEGATIVE_CONTROL_PASS' if not j else 'GPU_READ_WRITE_PASS','gpu_registry_id':55,'pci_registry_id':88,'target_SHA256':'neg' if not j else 'target','output_SHA256':'neg' if not j else 'output','cpu_words_compared':2,'guard_bytes_compared':128,'negative_gpu_read_mismatches':1 if not j else 0,'negative_gpu_write_mismatches':1 if not j else 0}
            i={'build_inputs_SHA256':'build','metallib_SHA256':'library'};m={'pid':j+1,'started_at':f'2026-10-27T00:00:{j*2:02d}+00:00','completed_at':f'2026-10-27T00:00:{j*2+1:02d}+00:00'}
            rows[str(p)]={'v':v,'i':i,'m':m}
        def read(path):
            path=Path(path);root=str(path.parent.parent) if path.name=='manifest.json' else str(path.parent);row=rows[root]
            return {'verification-execution.json':{'exit_code':0},'verification.stdout':row['v'],'inputs.json':row['i'],'results.json':{},'manifest.json':row['m']}[path.name]
        with patch.object(audit,'verify',side_effect=lambda p:rows[str(p)]['v']),patch.object(audit,'read',side_effect=read),patch.object(audit,'sha',return_value='hash'),patch.object(audit.subprocess,'run'):
            self.assertEqual(audit.audit(paths)['audit'],'PASS')
            rows[str(paths[-1])]['v']['target_SHA256']='wrong'
            with self.assertRaisesRegex(ValueError,'captures disagree'):audit.audit(paths)
            rows[str(paths[-1])]['v']['target_SHA256']='target';rows[str(paths[1])]['m']['started_at']='2026-10-27T00:00:00+00:00'
            with self.assertRaisesRegex(ValueError,'overlapped'):audit.audit(paths)
if __name__=='__main__':unittest.main()
