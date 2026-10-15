#!/usr/bin/env python3
"""Independent byte oracle for bounded copy chains/ranges on native M1 or GTX."""
from pathlib import Path
import argparse, hashlib, json, struct

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify(root, portable=False):
    root=Path(root)
    read=lambda n:json.loads((root/n).read_text())
    d,m,inp=read('results.json'),read('execution/manifest.json'),read('inputs.json')
    mode=d['mode']; native=d['native_reference']; prep=mode=='prepare_chain'
    negative=mode in ['no_chain','no_range']; completed=mode.endswith('_completed')
    width=2 if mode in ['range','range_completed','no_range'] else 1
    slots=width*3; n=d['local']*d['groups']
    assert mode in ['chain','chain_completed','range','range_completed','no_chain','no_range','prepare_chain']
    assert d['width']==width and d['slots']==slots and d['scope_restored']
    assert d['local'] in [32,33,128] and d['groups'] in [3,5] and 0<n<=640
    assert d['device']==('Apple M1 Max' if native else 'NVIDIA GeForce GTX 880M')
    assert d['registry_id'] and (native or d['registry_id']==4294968458)
    assert not any(d[k] for k in ['system_modified','CPU_expected_answers_uploaded','intermediate_descriptor_CPU_readback','full_ICB_contract','performance_benchmark'])
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
    for f,h in inp['source_SHA256'].items():assert sha(root/f)==h
    assert sha(root/'library.metallib')==inp['library_SHA256']
    if not native:assert inp['library_SHA256']=='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd'
    if not portable:
        assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
        assert sha(root/'execution/application')==m['signed_binary_sha256']
    words=invocations=guards=0; hashes={}
    assert len(d['runs'])==3
    for t,r in enumerate(d['runs']):
        seeds=[0x3311+t*97+k*0x4422 for k in range(slots)]
        assert r['trial']==t and r['seeds']==seeds and r['width']==width and r['slots']==slots
        assert r['local']==d['local'] and r['groups']==d['groups']
        assert r['before_commit_untouched'] and r['committed']==(not prep) and r['command_status']==(0 if prep else 4)
        assert r['copy_encoded'] and r['public_copy_selector_used'] and r['copy_executed']==(not prep)
        assert r['second_copy_encoded']==(not negative) and r['second_copy_executed']==(not negative and not prep)
        assert r['producer_completed_before_second_copy']==completed and r['CPU_source_reset_after_producer']==completed
        assert all(r[k] for k in ['ICB_external_reference_released_before_commit','parameter_external_references_released_before_commit','source_parameter_alive_before_commit'])
        events=r['copy_events']
        if native:assert not events
        else:
            copies=[e for e in events if e['operation']=='GPU_QMD_copy']
            executions=[e for e in events if e['operation']=='executeCommandsInBuffer']
            assert len(copies)==(1 if negative else 2) and len(executions)==1
            for j,c in enumerate(copies):
                assert c['source_location']==width*j and c['destination_index']==width*(j+1) and c['length']==width
                assert c['bytes']==256*width and c['encoded_GPU_blits']==width and c['whole_range_preflight']
                assert c['retained_owners']==width*(j+2) and c['CPU_shadow_updated_for_setters'] and not c['CPU_shadow_is_execution_source']
                assert len(c['descriptor_pairs'])==width
                for pair in c['descriptor_pairs']:assert pair['source']!=pair['destination'] and pair['owners']==j+2
            e=executions[0]
            assert e['location']==width*2 and e['length']==width and e['executed_indices']==list(range(width*2,width*3))
            if negative:assert not e.get('resident_GPU_descriptor',False)
            else:
                assert e['resident_GPU_descriptor']; p=e['evidence']
                assert p['operation']==('resident_QMD_launch' if width==1 else 'resident_QMD_sequence_launch')
                assert p['resident_launches']==width and p['command_bytes']==24*width and p['owners']==slots
                assert p['CPU_QMD_uploads_in_launch']==p['CPU_constant_uploads_in_launch']==p['native_preparation_GPU_dispatches']==0
                assert not p['launch_suppressed'] and len(set(p['descriptor_GPU_addresses']))==width
                for j,c in enumerate(copies[-1]['descriptor_pairs']):assert c['destination']==p['descriptor_GPU_addresses'][j]
            resets=[e for e in events if e['operation']=='CPU_reset']
            assert len(resets)==(1 if completed else 0)
            if completed:assert resets[0]['location']==0 and resets[0]['length']==width
        assert len(r['files'])==slots*2
        for k in range(slots):
            active=not prep and (width*2<=k<slots if negative else k<width)
            expected=bytearray(b'\xa5'*10368)
            if active:
                for i in range(n):struct.pack_into('<4I',expected,64+i*16,((seeds[k]*1664525)&0xffffffff)^((i*1013904223)&0xffffffff),i,d['groups']|0x01010000,d['local'])
                words+=n*4; invocations+=n
            path=root/'outputs'/r['files'][k*2]
            assert path.read_bytes()==expected,str(path);hashes[path.name]=sha(path)
            guards+=10368-(n*16 if active else 0)
            counter=bytearray(b'\xa5'*132);struct.pack_into('<I',counter,64,n if active else 0)
            path=root/'outputs'/r['files'][k*2+1]
            assert path.read_bytes()==counter,str(path);hashes[path.name]=sha(path);guards+=128
    if native:assert not d['scope_events']
    else:assert sum(e['operation']=='prepare_resident_compute_commands' for e in d['scope_events'])==3
    return {'status':'PASS_UNCOMMITTED' if prep else 'PASS_EXPECTED_OLD_DESTINATION' if negative else 'PASS',
            'mode':mode,'native_reference':native,'width':width,'slots':slots,
            'exact_uint32_words':words,'GPU_invocations_counted':invocations,
            'guard_and_untouched_bytes_verified':guards,
            'executed_descriptor_copies':0 if prep else 3*width*(1 if negative else 2),
            'executed_resident_launches':3*width if not native and not negative and not prep else 0,
            'owners_max':slots if not native and not negative else None,
            'integration_level':0 if native else 2,'full_ICB_contract':False,
            'performance_benchmark':False,'raw_SHA256':hashes}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path)
    a=p.parse_args();v=verify(a.root.resolve(),a.portable)
    if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
