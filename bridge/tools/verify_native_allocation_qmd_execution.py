#!/usr/bin/env python3
"""Compare passively captured QMD fields with raw GPU/CPU results after normal commit."""
from pathlib import Path
import argparse,hashlib,json,struct
from analyze_native_allocation_qmd import decode_stream,u32,u64
from verify_native_control_reserve import terminal,load,sha,require,DRIVER
from verify_native_allocation_common import allocation_proof
from verify_control_flow import result as cpu_result

ROOT=Path(__file__).resolve().parents[1]


def verify(root,build,library,reservation_root=None):
    inp=terminal(root,reservation_root or ROOT,build);d=load(root/'results.json');lm=load(library/'manifest.json')
    require(inp==load(build/'inputs.json') and inp['client_will_submit']is True
            and inp['static_library_SHA256']==sha(library/'libKeplerMetal.a')==lm['static_library_SHA256']
            and inp['library_manifest_SHA256']==sha(library/'manifest.json')
            and inp['source_generator_SHA256']==sha(build/'builder.py'),'execution build provenance')
    require(d['status']=='COMPLETED'and d['device']=='NVIDIA GeForce GTX 880M'and d['registry_id']==4294968458
            and d['driver_SHA256']==DRIVER and d['user_GPU_command_buffers']==9
            and d['user_compute_command_buffers']==3 and d['user_blit_command_buffers']==6
            and not d['CPU_expected_answers_uploaded']and not d['packet_replay']
            and not d['native_memory_written_by_probe']and not d['system_modified']and not d['performance_benchmark'],
            'execution scope')
    mode,function=d['mode'].split(':');require(mode in['native','reserved']and function==d['function'],'execution selection')
    depth=int(function[5:]);manifest=load(root/'assets/native-allocation-manifest.json');entry=manifest['certificates'][function]
    certificate=root/'assets'/entry['file'];cert=load(certificate);w=cert['metadata_words']
    require(sha(certificate)==entry['SHA256']==d['certificate_SHA256']
            and sha(root/'assets/control_flow.metallib')==manifest['library_sha256']==d['library_SHA256'],'execution asset pins')
    if mode=='reserved':allocation_proof(d['import'],root/'assets/control_flow.metallib',certificate)
    else:require(d['import']=={},'unexpected native replacement')
    initial=struct.pack('<32I',*d['variant_initial_words_0_128'])
    require(hashlib.sha256(initial).hexdigest()==d['variant_initial_SHA256'],'initial variant')
    frame=(w[12]+15)&~15;control=4096 if mode=='reserved'else w[11];budget=frame*64+((control+511)&~511)+512
    def variant_fields(data):
        require(u64(data,24)==cert['code_bytes']and u32(data,40)==budget and u32(data,44)==cert['code_bytes']//8-1
                and u32(data,48)==w[7]and u32(data,56)==w[14],'execution variant contract')
    variant_fields(initial);rows=[];files={};require(len(d['runs'])==3,'execution trial count')
    for trial,r in enumerate(d['runs']):
        seed=0x13579+trial*971;reserved=trial%3;n=99
        require(r['trial']==trial and r['seed']==seed and r['reserved']==reserved and r['threads']==n
                and r['groups']==3 and r['local']==33 and r['stride']==129 and r['committed']
                and r['kernel_dispatches']==1 and r['command_status']==r['init_status']==r['read_status']==4
                and r['captured_before_commit']and r['stream_unchanged_on_immediate_recheck'],'captured commit/dispatch record')
        fields=struct.pack('<32I',*r['variant_after_words_0_128']);require(hashlib.sha256(fields).hexdigest()==r['variant_after_SHA256'],'post-execution variant')
        variant_fields(fields);command_path=root/'outputs'/r['command_file'];raw=command_path.read_bytes()
        require(len(raw)==r['command_bytes']and sha(command_path)==r['command_SHA256'],'executed stream capture')
        before,after=r['before'],r['after']
        require(before['valid']and after['valid']and before['push']==after['push']
                and after['current']-before['current']==len(raw)and after['current']<=before['end'],'capture interval')
        binding={'groups':3,'local':33,'count':99,'parameters_GPU_address':r['parameters_GPU_address'],'parameters_bytes':512}
        qmd=decode_stream(raw,binding,frame,w[7],control,budget,u64(fields,16))
        expected_input=bytearray(b'\xa5'*(256+n*129*4));expected_parameters=bytearray(b'\xa5'*512)
        for i in range(n*129):struct.pack_into('<I',expected_input,128+4*i,((i*1664525+1013904223)&0xffffffff)^seed)
        struct.pack_into('<4I',expected_parameters,0,seed,n,129,reserved)
        input_path=root/'outputs'/r['input_file'];parameter_path=root/'outputs'/r['parameters_file'];output_path=root/'outputs'/r['output_file'];out=output_path.read_bytes()
        require(r['input_bytes']==len(expected_input)and input_path.read_bytes()==expected_input
                and r['parameters_bytes']==512 and parameter_path.read_bytes()==expected_parameters
                and r['output_bytes']==len(out)==256+n*16 and out[:128]==out[-128:]==b'\xa5'*128,'input/parameters/guards')
        correct=unchanged=other=witnesses=0
        for gid in range(n):
            expected=cpu_result(depth,gid,seed,reserved);actual=struct.unpack_from('<4I',out,128+16*gid)
            for a,e in zip(actual,expected):
                if a==e:correct+=1
                elif a==0xa5a5a5a5:unchanged+=1
                else:other+=1
            witnesses+=int(actual[3]==expected[3])
        numerical='PASS'if correct==n*4 else'UNCHANGED_OUTPUT'if unchanged==n*4 else'NUMERICAL_FAILURE'
        rows.append({'trial':trial,'QMD':qmd,'numerical_status':numerical,'exact_uint32_results':correct,
                     'incorrect_uint32_results':unchanged+other,'unchanged_wrong_words':unchanged,'other_wrong_words':other,
                     'invocation_witnesses':witnesses,'guard_bytes':512,'parameter_bytes_checked':512,
                     'compute_command_buffers':1,'blit_command_buffers':2})
        for p in[command_path,input_path,parameter_path,output_path]:files[p.name]=sha(p)
    return {'observation_status':'VERIFIED','numerical_status':'PASS'if all(r['numerical_status']=='PASS'for r in rows)else'FAIL',
            'mode':mode,'function':function,'native_frame':w[12],'native_control_word11':w[11],
            'requested_control':control,'decoded_allocation_word40':budget,'records':rows,
            'user_GPU_command_buffers':9,'compute_trials':3,'blit_command_buffers':6,
            'exact_uint32_results':sum(r['exact_uint32_results']for r in rows),
            'incorrect_uint32_results':sum(r['incorrect_uint32_results']for r in rows),
            'invocation_witnesses':sum(r['invocation_witnesses']for r in rows),'guard_bytes':1536,'parameter_bytes_checked':1536,
            'captured_then_committed_normally':True,'driver_commit_rewrites_independently_excluded':False,
            'resident_QMD_independently_read_back':False,'files_SHA256':files,
            'static_library_SHA256':inp['static_library_SHA256'],'system_modified':False,'performance_benchmark':False,
            'full_objective_complete':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in['root','build','library','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--reservation-root',type=Path,help='Existing shared laboratory reservation root')
    a=p.parse_args();out=a.out.resolve();reservation=(a.reservation_root or ROOT).resolve();out.relative_to(reservation/'results');proof=verify(a.root.resolve(),a.build.resolve(),a.library.resolve(),reservation)
    with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in proof.items()if k not in['records','files_SHA256']},indent=2))
