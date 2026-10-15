#!/usr/bin/env python3
"""Independent integer/shared-sum oracle; no binary or GPU execution."""
from pathlib import Path
import argparse
import hashlib
import json
import struct


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify(root, portable=False):
    root=Path(root)
    read=lambda n:json.loads((root/n).read_text())
    d, m, inp=read('results.json'), read('execution/manifest.json'), read('inputs.json')
    mode=d['mode']; native=d['native_reference']; prepare=False; negative=False; cold=mode in ['prepare_bound','prepare_private'];owner=mode in ['owner_bound','execute_owner_bound']; assert not native
    width=2; slots=6
    assert mode in ['prepare_bound','prepare_private','copy_bound','owner_bound','execute_owner_bound']
    assert d['width']==width and d['slots']==slots and d['scope_restored']
    assert d['device']==('Apple M1 Max' if native else 'NVIDIA GeForce GTX 880M')
    assert native or d['registry_id']==4294968458
    assert not any(d[k] for k in ['system_modified','CPU_expected_answers_uploaded','intermediate_descriptor_CPU_readback','performance_benchmark','full_ICB_contract'])
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert m['GPU_reservation']['state']=='terminal'
    for n,h in inp['source_hashes'].items():assert sha(root/n)==h
    for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
    if not portable:
        assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
        assert sha(root/'execution/application')==m['signed_binary_sha256']
    locals_=[[32,33,128,256,512,1024],[512,1024,32,33,128,256],[128,256,512,1024,32,33]]
    shared=[[49152,0,4096,0,0,1024],[0,49152,0,1024,32768,0],[1024,4096,0,0,32768,49152]]
    for row in shared:row[1]=4096;row[3]=1024;row[5]=49152
    mask=0xffffffff; buffer_bytes=8192*16+512; words=invocations=guards=0; hashes={}; qualified=[]
    assert len(d['runs'])==3
    for t,r in enumerate(d['runs']):
        specs=[]
        for k in range(slots):
            local=locals_[t][k]; groups=3 if local<=33 else 5 if local==128 else 2 if local==256 else 1
            specs.append({'function':'manifest_dynamic' if shared[t][k] else 'manifest_mix',
                          'local':local,'groups':groups,'count':local*groups,
                          'seed':0x765431+t*97+k*101,'dynamic_bytes':shared[t][k]})
        assert r['trial']==t and r['node_specs']==specs
        assert r['committed']==(not prepare) and r['command_status']==(0 if prepare else 4)
        assert r['before_commit_untouched'] and r['ICB_and_parameter_external_refs_released_before_commit']
        assert r['source_reset_after_completed_producer']==mode.endswith('_completed')
        assert len(r['outputs'])==len(r['counter_files'])==slots
        for k,(name,cn) in enumerate(zip(r['outputs'],r['counter_files'])):
            active=k==(0 if cold or owner else 2)
            expected=bytearray(b'\xa5'*buffer_bytes); counter=bytearray(b'\xa5'*208)
            spec=specs[k]; n=spec['count']; seed=spec['seed']; local=spec['local']
            struct.pack_into('<I',counter,128,n if active else 0)
            if active:
                for i in range(n):
                    if spec['dynamic_bytes']:
                        group,lane=divmod(i,local); total=0
                        for j in range(lane,spec['dynamic_bytes']//4,local):
                            total+=(seed*1664525 ^ group*1013904223 ^ j*2246822519)&mask
                        value=total&mask
                    else:
                        x=(seed*1664525 ^ i*1013904223)&mask
                        value=((x<<13)|(x>>19))&mask
                    struct.pack_into('<4I',expected,128+i*16,value,i,spec['groups']|(1<<16)|(1<<24),local)
                words+=n*4; invocations+=n
                qualified.append({'local':local,'dynamic_bytes':spec['dynamic_bytes'],'function':spec['function']})
            for filename,data in [(name,expected),(cn,counter)]:
                f=root/'outputs'/filename; assert f.read_bytes()==data,filename; hashes[filename]=sha(f)
            guards+=buffer_bytes-(n*16 if active else 0)+204
        assert r['refused'] and r['events_unchanged_at_refusal'] and not r['bad_command_buffer_committed']
        assert r['private_parameter_rejected']==(mode=='prepare_private') and r['first_copy_completed']==owner
        assert r['original_source_reset']==owner and r['probe_index']==(5 if cold else 1 if owner else 3)
        assert r['selected_index']==(0 if cold else 1 if owner else 2) and r['active_output_index']==(0 if cold or owner else 2)
        wanted='Resident retained dynamic shared parameter differs from its allocation' if owner else 'Resident dynamic shared state is outside its registration' if mode=='prepare_private' else 'Resident dynamic shared parameter differs from its allocation'
        assert r['refusal_reason']==wanted
        materialized=[e for e in r['preparation_events'] if e['operation']=='materialize_CPU_command'][-slots:]
        # scope.events is cumulative: each earlier cold trial materialized its
        # valid witness after the refusal. The refusal itself adds no events.
        assert len(materialized)==(t if cold else slots)
        for spec,e in zip(specs,[] if cold else materialized):
            assert e['user_kernel_invocations']==0 and e['dynamic_threadgroup_length']==spec['dynamic_bytes']
            assert e['command_bytes']==(496 if spec['dynamic_bytes'] else 464)
        assert not any(e['operation']=='GPU_QMD_copy'for e in r['copy_events'])
        executions=[e for e in r['copy_events'] if e['operation']=='executeCommandsInBuffer'];assert len(executions)==1
        e=executions[0];assert e['executed_indices']==[r['selected_index']]
        if owner:
            c=r['first_copy_evidence']; assert c['operation']=='GPU_QMD_copy' and c['length']==1 and c['bytes']==256
            assert c['descriptor_pairs'][0]['copied_function']==specs[0]['function']
            assert c['descriptor_pairs'][0]['copied_dynamic_threadgroup_bytes']==specs[0]['dynamic_bytes']
            assert e['resident_GPU_descriptor'];p=e['evidence']
            assert p['command_bytes']==24 and p['owners']==2 and p['CPU_QMD_uploads_in_launch']==p['CPU_constant_uploads_in_launch']==0
            owners=p['owner_original_profiles'];assert len(owners)==2
            assert sorted((x['original_record_function'],x['dynamic_threadgroup_bytes'],x['local_shape'][0])for x in owners)==sorted((x['function'],x['dynamic_bytes'],x['local'])for x in specs[:2])
        else:
            assert not e.get('resident_GPU_descriptor',False) and not r['first_copy_evidence']
    return {'status':'PASS_EXPECTED_REFUSAL_WITH_VALID_WITNESS',
            'mode':mode,'native_reference':native,'exact_uint32_words':words,'GPU_invocations_counted':invocations,
            'guard_and_untouched_bytes_verified':guards,'raw_files':len(hashes),'raw_SHA256':hashes,
            'executed_configurations':qualified,'GTX_native_QMD_qualified':not native,
            'integration_level':0 if native else 2,'performance_benchmark':False,'full_ICB_contract':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path)
    a=p.parse_args();v=verify(a.root.resolve(),a.portable)
    if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps({k:x for k,x in v.items()if k not in ['raw_SHA256','executed_configurations']},indent=2))
