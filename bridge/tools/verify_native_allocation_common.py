#!/usr/bin/env python3
"""Independent raw-result checks for common native-allocation interoperability."""
from pathlib import Path
import argparse,json,struct
from verify_native_control_reserve import terminal,load,sha,require,DRIVER
from verify_control_flow import result as native_result
from verify_local_memory import result as local_result
from verify_native_cas_sdk import verify as cas_suite
from public_large_scratch import DRIVER_PROFILES
from verify_local_memory import verify_device_identity

ROOT=Path(__file__).resolve().parents[1]


def native_record(root,row):
    require(row['kind']in['native','local']and row['threads']==row['local']==33
            and row['groups']==1 and row['seed']==0x13579 and row['stride']==129
            and row['reserved']==2 and row['command_status']==4
            and row['kernel_dispatches']==1,'native/local record shape')
    n=row['threads'];seed=row['seed'];inp=bytearray(b'\xa5'*(256+n*129*4))
    out=bytearray(b'\xa5'*(256+n*16))
    for i in range(n*129):struct.pack_into('<I',inp,128+4*i,((i*1664525+1013904223)&0xffffffff)^seed)
    for gid in range(n):
        values=(native_result(row['depth'],gid,seed,row['reserved'])if row['kind']=='native'
                else local_result(row['function'],gid,seed))
        struct.pack_into('<4I',out,128+16*gid,*values)
    require(row['input_bytes']==len(inp)and row['output_bytes']==len(out),'record byte count')
    require((root/'outputs'/row['input_file']).read_bytes()==inp,'record complete input/guards')
    require((root/'outputs'/row['output_file']).read_bytes()==out,'record complete output/guards')
    return {'status':'PASS','kind':row['kind'],'exact_uint32_results':n*4,'invocation_witnesses':n,
            'guard_bytes':512,'kernel_dispatches':1}


def cas_record(root,row):
    require(row['kind']=='CAS'and row['candidate']and row['layout']=='standard'
            and row['local']==33 and row['groups']==3 and row['variant']==row['iteration']==0
            and row['seed']==0x2468 and row['committed']and row['command_status']==4,'CAS record shape')
    n=99;raw=(root/'outputs'/row['file']).read_bytes()
    require(len(raw)==n*16+128 and raw[:64]==raw[-64:]==b'\xa5'*64,'CAS guards')
    winners=[0,0,0]
    for gid in range(n):
        old,success,final,index=struct.unpack_from('<4I',raw,64+16*gid)
        require(success in[0,1],'CAS success flag');winners[gid//33]+=success
        initial=(0x2468+(gid//33)*0x10001)&0xffffffff;replacement=0x2468^0x55667788
        require((old,success,final,index)==(initial if success else replacement,success,replacement,gid),
                'CAS complete result')
    require(winners==[1,1,1],'CAS group contention winners')
    return {'status':'PASS','correct_CAS_operations':n,'exact_uint32_results':4*n,'guard_bytes':128,
            'kernel_dispatches':1}


def allocation_proof(proof,library,certificate):
    c=load(certificate);w=c['metadata_words']
    if 'actual_driver_sha256' in proof:
        require(proof['actual_driver_sha256'] in DRIVER_PROFILES,'actual driver profile')
        identity=proof['device_identity']
        verify_device_identity(dict(device=identity['name'],registry_id=identity['registry_id'],device_identity=identity))
    for flag in ['gate_accepted','constructor_entered','contract_verified','constructor_restored',
                 'immutable_library_data','inputs_snapshotted','shares_import_mutex','thread_local_scope']:
        require(proof[flag]is True,'allocation proof: '+flag)
    require(not proof['native_program_replaced']and not proof['system_modified']
            and proof['calls']==len(proof['events'])==1 and proof['function']==c['function']
            and proof['library_SHA256']==sha(library)==c['library_sha256']
            and proof['certificate_SHA256']==sha(certificate)and c['driver_sha256']==DRIVER,'allocation pins')
    e=proof['events'][0]
    for flag in ['certificate_matches','metadata_match','code_match','parsed','only_metadata_words9_11_changed',
                 'native_code_identical','native_code_identical_after_constructor',
                 'payload_unchanged_after_constructor','decoded_contract_verified']:
        require(e[flag]is True,'allocation event: '+flag)
    actual=e['actual_metadata_words'];require(len(actual)==58 and all(actual[i]==w[i]for i in range(58)if i not in[2,4]),'allocation metadata pin')
    require(e['actual_code_SHA256']==e['post_constructor_code_SHA256']==c['native_code_sha256']
            and e['code_bytes']==c['code_bytes']and e['old_control']==w[11]
            and e['new_control']==e['requested_reserve']==4096 and e['native_frame']==w[12]
            and e['native_GPR']==w[7]and e['decoded_spill_bytes56']==w[14]
            and e['decoded_allocation_word40']==e['expected_allocation_word40']
            ==((w[12]+15)&~15)*64+4096+512,'allocation decoded/code identity')
    return {'status':'PASS','function':c['function'],'code_SHA256':c['native_code_sha256'],
            'native_code_bytes':c['code_bytes'],'native_frame':w[12],
            'unrelated_passthrough_calls':proof['unrelated_constructor_passthrough_calls']}


def verify_concurrency(root,build):
    inp=terminal(root,ROOT,build);d=load(root/'results.json');assets=root/'assets'
    require(load(build/'inputs.json')==inp,'concurrency build inputs')
    require(d['status']=='PASS'and d['mode']=='concurrent'and d['registry_id']==4294968458
            and d['device']=='NVIDIA GeForce GTX 880M'and d['constructor_restored']
            and d['hook_seen_at_gate']and d['legacy_blocked_during_gate']and not d['gate_timeout']
            and d['errors']==['','','']and not d['CPU_expected_answers_uploaded']
            and not d['system_modified']and not d['performance_benchmark'],'concurrency control')
    manifest=load(assets/'native-allocation-manifest.json');entry=manifest['certificates']['depth96']
    require(sha(assets/entry['file'])==entry['SHA256'],'concurrency certificate manifest')
    proof=allocation_proof(d['allocation'],assets/'control_flow.metallib',assets/entry['file'])
    require(proof['unrelated_passthrough_calls']>=1,'unrelated native constructor overlap not observed')
    p=d['CAS'];require(p['gate_accepted']and p['constructor_restored']and p['immutable_library_data']
        and p['native_import']['contract_verified']and p['native_import']['constructor_restored'],
        'protected CAS restoration')
    for e in p['native_import']['events']:
        require(e['expected_original_code_identical']and e['native_metadata_identical_to_certificate']
                and e['imported_code_identical']and e['code_input_unchanged_after_constructor'],
                'CAS constructor code/pin evidence')
    require(len(d['runs'])==3 and [r['kind']for r in d['runs']]==['native','CAS','native'],'concurrency compute coverage')
    require([d['runs'][i]['depth']for i in[0,2]]==[96,0],'native depth coverage')
    records=[native_record(root,d['runs'][0]),cas_record(root,d['runs'][1]),native_record(root,d['runs'][2])]
    return {'status':'PASS','scope':'Controlled simultaneous API creation; serial GPU computation afterward',
            'allocation_proof':proof,'legacy_waited_for_common_mutex':True,'unrelated_constructor_passthrough_observed':True,
            'native_and_CAS_kernels':records,'exact_uint32_results':sum(r['exact_uint32_results']for r in records),
            'guard_bytes':sum(r['guard_bytes']for r in records),'GPU_command_buffers':3,
            'static_library_SHA256':inp['static_library_SHA256'],'performance_benchmark':False}


def verify_coexist(root,build):
    m=load(root/'execution/manifest.json');inp=load(root/'inputs.json');d=load(root/'results.json')
    require(m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']
            and m['GPU_reservation']['state']=='terminal','coexist process')
    require(load(build/'inputs.json')==inp and load(root/'execution/execution.stdout')==d
            and m['launcher_sha256']==sha(ROOT/'tools/run_signed_probe.py')
            and m['reservation_module_SHA256']==sha(ROOT/'tools/lab_gpu_reservation.py')
            and m['GPU_reservation']['lock_inherited_by_child']
            and m['GPU_reservation']['bootstrap_process_table_checked']
            and not m['GPU_reservation']['known_signed_processes_live'],
            'coexist runner/result provenance')
    signed=Path(m['signed_executable']).resolve();signed.relative_to(root.resolve()/'execution')
    require(sha(build/'cas_example')==inp['executable_SHA256']==m['original_binary_sha256']
            and sha(signed)==m['signed_binary_sha256'],'coexist executable')
    require(sha(build/'cas_client.mm')==inp['client_source_SHA256']
            and sha(build/'KeplerNativeCAS.h')==inp['public_header_SHA256']
            and sha(build/'KeplerProgramImport.h')==inp['local_header_SHA256']
            and sha(build/'KeplerNativeAllocation.h')==inp['allocation_header_SHA256']
            and sha(build/'NativeAllocationExecution.inc')==inp['allocation_execution_helper_SHA256'],'coexist sources')
    for name,h in inp['assets'].items():require(sha(build/'assets'/name)==h,'coexist asset: '+name)
    require(d['native_allocation_prelude']and d['local_memory_prelude']and d['descriptor_transport_prelude']
            and d['allocation_inputs_wiped_before_commit']and d['local_memory_import']['contract_verified']
            and d['descriptor_transport_import']['contract_verified'],'coexist prelude')
    proof=allocation_proof(d['native_allocation_import'],build/'assets/allocation-prelude.metallib',
                           build/'assets/allocation-prelude.certificate.json')
    cas=cas_suite(root);post=[]
    if d['mode']=='execute':
        require(d['native_allocation_postlude']['depth']==96 and d['local_postlude']['function']=='local32',
                'coexist postlude coverage')
        post=[native_record(root,d['local_postlude']),native_record(root,d['native_allocation_postlude'])]
    else:require(d['native_allocation_postlude']==d['local_postlude']=={},'negative mode unexpectedly dispatched')
    return {'status':'PASS','mode':d['mode'],'allocation':proof,'CAS':{k:v for k,v in cas.items()if k!='records'},
            'postludes':post,'total_user_GPU_command_buffers':cas['user_GPU_command_buffers']+len(post),
            'static_library_SHA256':inp['module_static_library_SHA256'],'performance_benchmark':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--kind',choices=['concurrency','coexist'],required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results')
    result=(verify_concurrency if a.kind=='concurrency'else verify_coexist)(a.root.resolve(),a.build.resolve())
    with out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
