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
    mode=d['mode']; native=d['native_reference']; prepare=mode=='prepare'; negative=mode=='no_second'
    width=2 if mode.startswith('range') else 1; slots=width*3
    assert mode in ['prepare','chain','range','chain_completed','range_completed','no_second']
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
            active=not prepare and (k>=2*width if negative else k<width)
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
        if native:
            assert not r['copy_events'] and not r['preparation_events']
            continue
        materialized=[e for e in r['preparation_events'] if e['operation']=='materialize_CPU_command'][-slots:]
        assert len(materialized)==slots
        for spec,e in zip(specs,materialized):
            assert e['user_kernel_invocations']==0 and e['dynamic_threadgroup_length']==spec['dynamic_bytes']
            assert e['command_bytes']==(496 if spec['dynamic_bytes'] else 464)
            p=e['relocation']; assert p['QMD_total_shared_bytes']==spec['dynamic_bytes'] and p['binding_layout_v2']
            assert p['parameters_offset']==1024 and p['constant_buffer_valid_mask']==6
        copies=[e for e in r['copy_events'] if e['operation']=='GPU_QMD_copy']
        executions=[e for e in r['copy_events'] if e['operation']=='executeCommandsInBuffer']
        assert len(copies)==(1 if negative else 2) and len(executions)==1
        for j,c in enumerate(copies):
            assert c['source_location']==j*width and c['destination_index']==(j+1)*width
            assert c['length']==width and c['bytes']==width*256 and c['whole_range_preflight']
            assert not c['CPU_shadow_is_execution_source']
            for k,pair in enumerate(c['descriptor_pairs']):
                assert pair['copied_function']==specs[k]['function']
                assert pair['copied_groups']==specs[k]['groups'] and pair['copied_local']==specs[k]['local']
                assert pair['copied_dynamic_threadgroup_bytes']==specs[k]['dynamic_bytes']
                assert pair['destination_original_dynamic_threadgroup_bytes']==specs[(j+1)*width+k]['dynamic_bytes']
        e=executions[0]; assert e['executed_indices']==list(range(2*width,3*width))
        if negative:
            assert not e.get('resident_GPU_descriptor',False)
        else:
            assert e['resident_GPU_descriptor']; p=e['evidence']
            assert p['command_bytes']==24*width and p['resident_launches']==width and p['owners']==slots
            assert p['CPU_QMD_uploads_in_launch']==p['CPU_constant_uploads_in_launch']==p['native_preparation_GPU_dispatches']==0
            owners=p['owner_original_profiles']; assert len(owners)==slots
            assert len({x['registration_id'] for x in owners})==1 and all(x['registration_id'] for x in owners)
            wanted=sorted((s['function'],s['local'],s['groups'],s['dynamic_bytes']) for s in specs)
            actual=sorted((x['original_record_function'],x['local_shape'][0],x['groups_shape'][0],x['dynamic_threadgroup_bytes'])for x in owners)
            assert actual==wanted
            for o in owners:
                dy=o['dynamic_threadgroup_bytes']
                assert o['QMD_total_shared_bytes']==dy and o['static_threadgroup_bytes']==0
                assert o['dynamic_base_word_validated']==bool(dy)
                assert o['native_register_count']==(8 if dy else 7)
                assert o['constant_buffer_valid_mask']==6 and o['binding_layout_v2'] and not o['native_literal_bank_0']
    return {'status':'PASS_UNCOMMITTED'if prepare else'PASS_EXPECTED_OLD_DESTINATION'if negative else'PASS',
            'mode':mode,'native_reference':native,'exact_uint32_words':words,'GPU_invocations_counted':invocations,
            'guard_and_untouched_bytes_verified':guards,'raw_files':len(hashes),'raw_SHA256':hashes,
            'executed_configurations':qualified,'GTX_native_QMD_qualified':not native,
            'integration_level':0 if native else 2,'performance_benchmark':False,'full_ICB_contract':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path)
    a=p.parse_args();v=verify(a.root.resolve(),a.portable)
    if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps({k:x for k,x in v.items()if k not in ['raw_SHA256','executed_configurations']},indent=2))
