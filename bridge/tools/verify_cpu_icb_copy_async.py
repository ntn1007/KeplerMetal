#!/usr/bin/env python3
"""Independent byte oracle for mixed native pipelines/geometry copy chains on native M1 or GTX."""
from pathlib import Path
import argparse, hashlib, json, struct

# Independent workload specification, not a shader implementation.
RECIPES=[
 [("profile_integer",32,3),("profile_fma",33,3),("profile_shared",64,2),("profile_fma",128,2),("profile_shared",32,5),("profile_integer",128,3)],
 [("profile_fma",128,3),("profile_shared",32,5),("profile_integer",33,3),("profile_shared",64,2),("profile_integer",32,3),("profile_fma",128,2)],
 [("profile_shared",128,5),("profile_integer",33,3),("profile_fma",32,3),("profile_integer",128,2),("profile_fma",64,2),("profile_shared",32,3)]
]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify(root, portable=False):
    root=Path(root)
    read=lambda n:json.loads((root/n).read_text())
    d,m,inp=read('results.json'),read('execution/manifest.json'),read('inputs.json')
    mode=d['mode']; native=d['native_reference']; prep=mode=='prepare_async'
    negative=mode=='no_second_async'; completed=False; split=mode in ['split_async','split_range_async']
    width=2 if mode in ['range_async','split_range_async'] else 1
    slots=width*3; recipe=[32,33,128].index(d['local']);nodes=RECIPES[recipe][:slots];assert d['recipe']==recipe and d['node_specs']==[{'function':f,'local':l,'groups':g} for f,l,g in nodes]
    assert mode in ['chain_async','range_async','split_async','split_range_async','no_second_async','prepare_async']
    assert d['width']==width and d['slots']==slots and d['scope_restored']
    assert d['local'] in [32,33,128] and d['groups']==[3,3,5][recipe] and all(0<l*g<=640 for _,l,g in nodes)
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
        assert r['producer_committed'] and r['producer_status_at_second_copy'] in [2,3]
        assert r['producer_status_before_gate_release'] in [2,3] and r['producer_final_status']==4
        assert r['middle_committed_before_execute']==split and r['consumer_status_before_commit']==0
        assert r['consumer_committed']==(not prep) and r['consumer_final_status']==(0 if prep else 4)
        assert r['consumer_status_before_gate_release']==0 if prep else r['consumer_status_before_gate_release'] in [2,3]
        if split:assert r['middle_status_at_execute'] in [2,3] and r['middle_status_before_gate_release'] in [2,3] and r['middle_final_status']==4
        else:assert r['middle_status_at_execute']==0 and r['middle_final_status']==(0 if prep else 4)
        assert r['gate_initial_value']==0 and r['gate_final_value']==1 and r['gate_release_by_main'] and not r['watchdog_fired']
        assert r['CPU_waits_between_producer_and_consumer_commits']==0 and r['final_completion_wait_calls']==1
        assert r['producer_marker_before_second_copy']==r['producer_marker_before_gate_release']==0
        assert r['producer_marker_final']==r['producer_marker_expected']==0x61a00000+t and r['producer_marker_guards_intact']
        assert all(r[k] for k in ['initial_output_readback_before_producer_commit','ICB_external_reference_released_before_commit','parameter_external_references_released_before_commit','source_parameter_alive_before_commit'])
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
                order=c['predecessor_order'];assert len(order)==(width if j else 0)
                for proof in order:assert proof['kind']=='committed_same_queue_predecessor' and proof['producer_status'] in [2,3] and proof['consumer_status']==0 and proof['same_queue'] and proof['consumer_not_enqueued'] and not proof['CPU_wait_performed']
                for k,pair in enumerate(c['descriptor_pairs']):
                    sf,sl,sg=nodes[k];df,dl,dg=nodes[(j+1)*width+k]
                    assert pair['source']!=pair['destination'] and pair['owners']==j+2
                    assert pair['copied_function']==sf and pair['copied_local']==sl and pair['copied_groups']==sg
                    assert pair['destination_original_function']==df and pair['destination_original_local']==dl and pair['destination_original_groups']==dg
            e=executions[0]
            assert e['location']==width*2 and e['length']==width and e['executed_indices']==list(range(width*2,width*3))
            if negative:assert not e.get('resident_GPU_descriptor',False)
            else:
                assert e['resident_GPU_descriptor']; p=e['evidence']
                order=e['predecessor_order'];assert len(order)==width
                for proof in order:
                    assert proof['kind']==('committed_same_queue_predecessor' if split else 'same_recording_CB') and proof['consumer_status']==0 and proof['same_queue'] and proof['consumer_not_enqueued'] and not proof['CPU_wait_performed']
                    assert proof['producer_status'] in ([2,3] if split else [0])
                assert p['operation']==('resident_QMD_launch' if width==1 else 'resident_QMD_sequence_launch')
                assert p['resident_launches']==width and p['command_bytes']==24*width and p['owners']==slots
                assert p['CPU_QMD_uploads_in_launch']==p['CPU_constant_uploads_in_launch']==p['native_preparation_GPU_dispatches']==0
                assert not p['launch_suppressed'] and len(set(p['descriptor_GPU_addresses']))==width
                owner_rows=p['owner_original_profiles'];assert len(owner_rows)==slots
                assert sorted((e['original_record_function'],e['local_shape'][0],e['groups_shape'][0]) for e in owner_rows)==sorted(nodes)
                for e in owner_rows:
                    shared=e['original_record_function']=='profile_shared'
                    assert e['static_threadgroup_bytes']==(512 if shared else 0) and e['native_register_count']==(8 if shared else 7)
                    assert e['groups_shape'][1:]==e['local_shape'][1:]==[1,1]
                for j,c in enumerate(copies[-1]['descriptor_pairs']):assert c['destination']==p['descriptor_GPU_addresses'][j]
            resets=[e for e in events if e['operation']=='CPU_reset']
            assert len(resets)==(1 if completed else 0)
            if completed:assert resets[0]['location']==0 and resets[0]['length']==width
        assert len(r['files'])==slots*2
        for k in range(slots):
            active=not prep and (width*2<=k<slots if negative else k<width)
            function,local,groups=nodes[k];n=local*groups
            expected=bytearray(b'\xa5'*10368)
            if active:
                for i in range(n):
                    index=(i//local)*local+(i+1)%local if function=='profile_shared' else i
                    first=((seeds[k]*1664525)&0xffffffff)^((index*1013904223)&0xffffffff)
                    if function=='profile_fma':first=struct.unpack('<I',struct.pack('<f',(i&31)*0.5+(seeds[k]&255)))[0]
                    struct.pack_into('<4I',expected,64+i*16,first,i,groups|0x01010000,local)
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
            'mode':mode,'native_reference':native,'width':width,'slots':slots,'recipe':recipe,'node_specs':d['node_specs'],
            'exact_uint32_words':words,'GPU_invocations_counted':invocations,
            'guard_and_untouched_bytes_verified':guards,
            'executed_descriptor_copies':3*width*(1 if prep or negative else 2),
            'executed_resident_launches':3*width if not native and not negative and not prep else 0,
            'owners_max':slots if not native and not negative else None,'CPU_intermediate_completion_waits':0,'producer_marker_zero_before_consumer_commit':True,'gated_pending_observations':3,'watchdog_fired':False,
            'integration_level':0 if native else 2,'full_ICB_contract':False,
            'performance_benchmark':False,'raw_SHA256':hashes}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path)
    a=p.parse_args();v=verify(a.root.resolve(),a.portable)
    if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
