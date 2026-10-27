# SPDX-License-Identifier: MIT
import hashlib,importlib.util,json,struct,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
spec=importlib.util.spec_from_file_location('uniform_oracle',ROOT/'bridge/tools/verify_uniform_thread_icb.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v))
def fixture(p,mode='execute'):
    for d in ('runtime','assets','outputs','execution'):(p/d).mkdir()
    for n,b in [('application',b'host'),('execution/application',b'signed'),('runtime_archive.a',b'archive'),('assets/indirect_compute_probe.metallib',b'library'),('runtime/run_sdk_host.py',b'launcher'),('runtime/lab_gpu_reservation.py',b'lease')]:(p/n).write_bytes(b)
    frozen={'runtime/run_sdk_host.py':sha(p/'runtime/run_sdk_host.py'),'runtime/lab_gpu_reservation.py':sha(p/'runtime/lab_gpu_reservation.py')};pin='b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d';form='threads'
    i={'mode':mode,'form':form,'registry_id':55,'frozen':frozen,'executable_SHA256':sha(p/'application'),'runtime_archive_SHA256':sha(p/'runtime_archive.a'),'metallib_SHA256':pin}
    rejects=['out_of_range','GPU_resource_identity','nonuniform_grid','descriptor_inheritance','zero_grid','zero_local','partial_y','partial_z','oversize_grid']
    events=[{'operation':'scope_install','capabilities_spoofed':False}]+[{'operation':'newIndirectCommandBuffer','size':5,'metadata_bytes':2560}]*2+[{'operation':'materialize_CPU_command'}]*4
    ranges=[(0,5,[0,2,4]),(2,1,[2]),(0,5,[0,2,4]),(0,5,[0,4]),(0,5,[0,4]),(0,5,[0,2,4]),(4,1,[4])]
    for loc,length,indices in ranges:events.append({'operation':'executeCommandsInBuffer','location':loc,'length':length,'executed_indices':indices,'evidence':{'raw_packet_copies':len(indices),'native_preparation_GPU_dispatches':0,'command_bytes':len(indices)*464,'system_modified':False}})
    events += [{'operation':'CPU_reset'},{'operation':'CPU_snapshot_copy','GPU_timeline_copy':False},{'operation':'scope_restore','device_class_restored':True}]
    active=[{0,1,2},{1},{0,1,2},{0,2},{0,2},{0,2,3},{2}];sizes=[(1,32),(3,33),(5,128),(3,33)];runs=[]
    for node in range(4):
        (p/f'outputs/before-execute-{node}.output.bin').write_bytes(b'\xa5'*10368)
        (p/f'outputs/before-execute-{node}.counter.bin').write_bytes(b'\xa5'*64+bytes(4)+b'\xa5'*64)
    for trial in range(7):
        outputs=[]
        for node,(groups,local) in enumerate(sizes):
            n=groups*local;seed=0x1234+101*node+37*trial;count=n if node in active[trial] else 0
            values=[]
            for j in range(count):values.extend([((seed*1664525)^(j*1013904223))&0xffffffff,j,groups|0x01010000,local])
            payload=struct.pack('<'+'I'*len(values),*values);data=b'\xa5'*64+payload+b'\xa5'*(10368-64-len(payload))
            (p/f'outputs/trial-{trial}-node-{node}.output.bin').write_bytes(data);(p/f'outputs/trial-{trial}-node-{node}.counter.bin').write_bytes(b'\xa5'*64+struct.pack('<I',count)+b'\xa5'*64)
            outputs.append({'node':node,'actual_invocations':count,'mismatches':0,'guard_mismatches':0})
        runs.append({'trial':trial,'command_status':4,'GPU_user_kernel_execution':True,'selected_buffer':'copy' if trial in (4,6) else 'source','outputs':outputs})
    r={'registry_id':55,'mode':mode,'dispatch_form':form,'ICB_object_created':True,'scope_restored':True,'passed':True,'ICB_contract_complete':False,'system_modified':False,'integration_level':1,'rejections':[{'case':x,'rejected':True} for x in rejects],'events':events,'runs':runs}
    m={'exit_code':0,'SIGKILL_requested':False,'authoritative_ps_status':'','pid':123,'original_binary_sha256':sha(p/'application'),'signed_binary_sha256':sha(p/'execution/application'),'launcher_SHA256':frozen['runtime/run_sdk_host.py'],'reservation_module_SHA256':frozen['runtime/lab_gpu_reservation.py'],'arguments':[str(p/'assets/indirect_compute_probe.metallib'),str(p/'outputs'),mode,form,'55'],'GPU_reservation':{'state':'terminal','exit_code':0,'child_PID':123,'known_signed_processes_live':[],'signed_binary_sha256':sha(p/'execution/application')}}
    put(p/'inputs.json',i);put(p/'results.json',r);put(p/'execution/execution.stdout',r);put(p/'execution/manifest.json',m);return r
class UniformOracleTests(unittest.TestCase):
    def test_raw_results_and_refusals_are_checked(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t).resolve();r=fixture(p)
            with patch.object(oracle,'sha',side_effect=lambda f:'b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d' if Path(f).name=='indirect_compute_probe.metallib' else sha(f)):
                self.assertEqual(oracle.verify(p)['user_GPU_invocations'],4396)
                f=p/'outputs/trial-0-node-0.output.bin';data=bytearray(f.read_bytes());data[70]^=1;f.write_bytes(data)
                with self.assertRaises(AssertionError):oracle.verify(p)
                fixture_path=p/'outputs/trial-0-node-0.output.bin';data[70]^=1;fixture_path.write_bytes(data)
                r['rejections'][0]['rejected']=False;put(p/'results.json',r);put(p/'execution/execution.stdout',r)
                with self.assertRaises(AssertionError):oracle.verify(p)

    def test_cohort_refuses_different_pairs_and_overlap(self):
        import audit_uniform_thread_icb as audit
        expected=[('prepare','groups'),('prepare','threads'),('execute','groups'),('execute','threads'),('execute','groups'),('execute','threads'),('execute','groups'),('execute','threads')];rows={};paths=[]
        for j,(mode,form) in enumerate(expected):
            p=Path('/fake')/str(j);paths.append(p);raw={'buffer':'same'}
            v={'mode':mode,'form':form,'gpu_registry_id':55,'raw_SHA256':raw,'correct_uint32_words':0 if mode=='prepare' else 4,'user_GPU_invocations':0 if mode=='prepare' else 1,'guard_bytes_checked':0 if mode=='prepare' else 64,'negative_api_cases':9}
            i={'build_inputs_SHA256':'build','runtime_archive_SHA256':'archive','metallib_SHA256':'library'};m={'pid':j+1,'started_at':f'2026-10-27T00:00:{j*2:02d}+00:00','completed_at':f'2026-10-27T00:00:{j*2+1:02d}+00:00'}
            rows[str(p)]={'v':v,'i':i,'m':m}
        def read(path):
            path=Path(path);root=str(path.parent.parent) if path.name=='manifest.json' else str(path.parent);row=rows[root]
            return {'verification-execution.json':{'exit_code':0},'verification.stdout':row['v'],'inputs.json':row['i'],'manifest.json':row['m']}[path.name]
        with patch.object(audit,'verify',side_effect=lambda p:rows[str(p)]['v']),patch.object(audit,'read',side_effect=read),patch.object(audit,'sha',return_value='hash'),patch.object(audit.subprocess,'run'):
            self.assertEqual(audit.audit(paths)['audit'],'PASS')
            rows[str(paths[3])]['v']['raw_SHA256']={'buffer':'different'}
            with self.assertRaisesRegex(ValueError,'captures differ'):audit.audit(paths)
            rows[str(paths[3])]['v']['raw_SHA256']={'buffer':'same'};rows[str(paths[1])]['m']['started_at']='2026-10-27T00:00:00+00:00'
            with self.assertRaisesRegex(ValueError,'overlapped'):audit.audit(paths)
if __name__=='__main__':unittest.main()
