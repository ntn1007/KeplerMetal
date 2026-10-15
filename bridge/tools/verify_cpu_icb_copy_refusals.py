#!/usr/bin/env python3
"""Refusal transaction oracle: execute the untouched target after discarding errors."""
from pathlib import Path
import argparse, hashlib, json, struct

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(root,portable=False):
    root=Path(root);read=lambda n:json.loads((root/n).read_text())
    d,m,inp=read('results.json'),read('execution/manifest.json'),read('inputs.json')
    mode=d['mode'];reasons={'second_unprepared':'prepared registered native profiles',
                           'pending_source':'prior source/destination copy',
                           'overlap':'nonoverlapping occupied ranges',
                           'unretained_CB':'retained uncommitted CB'}
    assert mode in reasons and d['adapter_policy_refusals'] and not d['native_reference']
    assert d['scope_restored'] and d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id']==4294968458
    assert d['recipe']==0 and d['slots']==6 and d['width']==2
    assert not any(d[k] for k in ['system_modified','CPU_expected_answers_uploaded','intermediate_descriptor_CPU_readback','full_ICB_contract','performance_benchmark'])
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
    for n,h in inp['source_SHA256'].items():assert sha(root/n)==h
    assert sha(root/'library.metallib')==inp['library_SHA256']=='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd'
    if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
    assert len(d['runs'])==3;hashes={};words=guards=0
    for t,r in enumerate(d['runs']):
        seeds=[0x3311+t*97+k*0x4422 for k in range(6)]
        assert r['trial']==t and r['seeds']==seeds and r['command_status']==4 and r['executed_index']==2
        assert all(r[k] for k in ['rejected','no_partial_copy_event','discarded_uncommitted','before_commit_untouched','ICB_external_reference_released_before_commit','parameter_external_references_released_before_commit','source_parameter_alive_before_commit'])
        assert reasons[mode] in r['refusal'] and len(r['files'])==12
        events=r['copy_events'];copies=[e for e in events if e['operation']=='GPU_QMD_copy'];executions=[e for e in events if e['operation']=='executeCommandsInBuffer']
        assert len(copies)==(1 if mode=='pending_source' else 0) and len(executions)==1
        if copies:
            c=copies[0];assert c['source_location']==0 and c['destination_index']==1 and c['length']==1
        e=executions[0];assert e['location']==2 and e['length']==1 and e['executed_indices']==[2] and not e.get('resident_GPU_descriptor',False)
        for k in range(6):
            expected=bytearray(b'\xa5'*10368)
            if k==2:
                for i in range(128):
                    neighbor=(i//64)*64+(i+1)%64
                    struct.pack_into('<4I',expected,64+i*16,((seeds[k]*1664525)&0xffffffff)^((neighbor*1013904223)&0xffffffff),i,2|0x01010000,64)
                words+=128*4
            f=root/'outputs'/r['files'][k*2];assert f.read_bytes()==expected,str(f);hashes[f.name]=sha(f);guards+=10368-(2048 if k==2 else 0)
            count=bytearray(b'\xa5'*132);struct.pack_into('<I',count,64,128 if k==2 else 0)
            f=root/'outputs'/r['files'][k*2+1];assert f.read_bytes()==count,str(f);hashes[f.name]=sha(f);guards+=128
    return {'status':'PASS_EXPECTED_REFUSAL_WITH_UNTOUCHED_TARGET','mode':mode,'refusals':3,
            'exact_uint32_words':words,'GPU_invocations_counted':384,
            'guard_and_untouched_bytes_verified':guards,'failed_CBs_committed':0,
            'pending_first_copy_executed':False,'integration_level':2,
            'performance_benchmark':False,'full_ICB_contract':False,'raw_SHA256':hashes}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path)
    a=p.parse_args();v=verify(a.root.resolve(),a.portable)
    if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps({k:x for k,x in v.items()if k!='raw_SHA256'},indent=2))
