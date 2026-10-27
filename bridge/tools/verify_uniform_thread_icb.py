#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check CPU ICB uniform-thread results and raw output without submitting work."""
import hashlib,json,struct,sys
from pathlib import Path

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify(path):
    p=Path(path).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode'];form=i['form']
    assert mode in ('prepare','execute') and form in ('groups','threads') and r==read(p/'execution/execution.stdout')
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live']
    assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256']
    assert sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256']
    assert sha(p/'assets/indirect_compute_probe.metallib')==i['metallib_SHA256']=='b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d'
    assert sha(p/'runtime_archive.a')==i['runtime_archive_SHA256']
    for name,digest in i['frozen'].items():assert sha(p/name)==digest,name
    assert m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py']
    assert m['arguments']==[str(p/'assets/indirect_compute_probe.metallib'),str(p/'outputs'),mode,form,str(i['registry_id'])]
    assert r['registry_id']==i['registry_id'] and r['mode']==mode and r['dispatch_form']==form and r['ICB_object_created'] and r['scope_restored'] and r['passed']
    assert not r['ICB_contract_complete'] and not r['system_modified'] and r['integration_level']==1
    rejections={'out_of_range','GPU_resource_identity','nonuniform_grid','descriptor_inheritance','zero_grid','zero_local','partial_y','partial_z','oversize_grid'}
    assert len(r['rejections'])==len(rejections) and {x['case'] for x in r['rejections']}==rejections and all(x['rejected'] for x in r['rejections'])
    hashes={};guards=words=invocations=0
    for node in range(4):
        out=p/f'outputs/before-execute-{node}.output.bin';counter=p/f'outputs/before-execute-{node}.counter.bin'
        assert out.read_bytes()==b'\xa5'*10368 and counter.read_bytes()==b'\xa5'*64+bytes(4)+b'\xa5'*64
        hashes[out.name]=sha(out);hashes[counter.name]=sha(counter)
    events=r['events'];executions=[e for e in events if e['operation']=='executeCommandsInBuffer'];materialized=[e for e in events if e['operation']=='materialize_CPU_command']
    assert events[0]['operation']=='scope_install' and not events[0]['capabilities_spoofed'] and events[-1]['operation']=='scope_restore' and events[-1]['device_class_restored']
    factories=[e for e in events if e['operation']=='newIndirectCommandBuffer'];assert len(factories)==2 and all(e['size']==5 and e['metadata_bytes']==2560 for e in factories)
    ranges=[(0,5,[0,2,4]),(2,1,[2]),(0,5,[0,2,4]),(0,5,[0,4]),(0,5,[0,4]),(0,5,[0,2,4]),(4,1,[4])]
    if mode=='prepare':
        assert len(r['runs'])==len(executions)==1 and len(materialized)==3 and not r['runs'][0]['main_command_buffer_committed'];ranges=ranges[:1]
    else:
        assert len(r['runs'])==len(executions)==7 and len(materialized)==4
        active=[{0,1,2},{1},{0,1,2},{0,2},{0,2},{0,2,3},{2}];sizes=[(1,32),(3,33),(5,128),(3,33)]
        for trial,run in enumerate(r['runs']):
            assert run['trial']==trial and run['command_status']==4 and run['GPU_user_kernel_execution'] and len(run['outputs'])==4
            assert run['selected_buffer']==('copy' if trial in (4,6) else 'source')
            for node,row in enumerate(run['outputs']):
                groups,local=sizes[node];n=groups*local;seed=0x1234+101*node+37*trial
                out=p/f'outputs/trial-{trial}-node-{node}.output.bin';counter=p/f'outputs/trial-{trial}-node-{node}.counter.bin'
                if node in active[trial]:
                    values=[]
                    for j in range(n):values.extend([((seed*1664525)^(j*1013904223))&0xffffffff,j,groups|0x01010000,local])
                    payload=struct.pack('<'+'I'*len(values),*values);expected=b'\xa5'*64+payload+b'\xa5'*(10368-64-len(payload));count=n;words+=len(values);invocations+=n
                else:expected=b'\xa5'*10368;count=0
                assert out.read_bytes()==expected and counter.read_bytes()==b'\xa5'*64+struct.pack('<I',count)+b'\xa5'*64
                assert row['node']==node and row['actual_invocations']==count and not row['mismatches'] and not row['guard_mismatches']
                hashes[out.name]=sha(out);hashes[counter.name]=sha(counter);guards+=256
        assert len([e for e in events if e['operation']=='CPU_reset'])==1
        copies=[e for e in events if e['operation']=='CPU_snapshot_copy'];assert len(copies)==1 and not copies[0]['GPU_timeline_copy']
    for event,(loc,length,indices) in zip(executions,ranges):
        assert (event['location'],event['length'],event['executed_indices'])==(loc,length,indices)
        e=event['evidence'];assert e['raw_packet_copies']==len(indices) and not e['native_preparation_GPU_dispatches'] and e['command_bytes']==len(indices)*464 and not e['system_modified']
    return {'verification':'PASS','mode':mode,'form':form,'gpu_registry_id':i['registry_id'],'correct_uint32_words':words,'user_GPU_invocations':invocations,'guard_bytes_checked':guards,'negative_api_cases':len(rejections),'scope_restored':True,'GPU_execution_proved':mode=='execute','raw_SHA256':hashes}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
