#!/usr/bin/env python3
"""Verify deep-control progress while retaining the failing native96 qualification."""
from pathlib import Path
import argparse,hashlib,json,struct
from verify_control_flow import verify as numeric,result
from verify_native_cas_sdk import verify as cas_numeric
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())

def terminal(root):
    m=load(root/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
    inp=load(root/'inputs.json');assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
    for n,h in inp['source_hashes'].items():assert sha(root/n)==h
    for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
    return inp

def failure(root,entry):
    terminal(root);d=load(root/'results.json');assert d['depth']==96 and d['native_reference']and not d['program_replaced']and not d['CPU_expected_answers_uploaded']
    assert len(d['runs'])==12;count=guards=0
    for row in d['runs']:
        n=row['threads'];seed=row['seed'];expected_in=bytearray(b'\xa5'*(256+n*129*4));expected_out=bytearray(b'\xa5'*(256+n*16))
        for i in range(n*129):struct.pack_into('<I',expected_in,128+4*i,((i*1664525+1013904223)&0xffffffff)^seed)
        for gid in range(n):
            if entry:struct.pack_into('<4I',expected_out,128+16*gid,0xface0000^gid,0x13572468,96,0xbabe0000^gid)
            got=struct.unpack_from('<4I',expected_out,128+16*gid);assert got!=result(96,gid,seed,row['reserved']);count+=1
        assert (root/'outputs'/row['input_file']).read_bytes()==expected_in
        assert (root/'outputs'/row['output_file']).read_bytes()==expected_out
        assert row['command_status']==4 and row['kernel_dispatches']==1;guards+=512
    return {'status':'FAIL','trials':12,'kernel_invocations_without_final_result':count,'entry_witnesses':count if entry else 0,'guard_bytes':guards,'process_terminal':True}

def observations(folder):
    assert load(folder/'status.json')['status']=='PASS';d=load(folder/'observations.json');rows=[]
    for item in d['records']:
        root=folder/item['function'];m=load(root/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']
        capture=root/'capture';payload=next(capture.glob('program-*.compiler-output.bin'));assert sha(payload)==item['compiler_output_SHA256']
        b=payload.read_bytes();version,total=struct.unpack_from('<2I',b);assert version in[7,8,9]and total==len(b);offset=8;words=None;code=None
        for _ in range(32):
            next_,kind,size=struct.unpack_from('<QII',b,offset);assert offset+16+size<=len(b)
            if kind==0x10004:assert words is None and size==232;words=list(struct.unpack_from('<58I',b,offset+16))
            if kind==0x10005:assert code is None;code=b[offset+16:offset+16+size]
            if not next_:break
            assert next_>=16+size;offset+=next_
        assert words==item['metadata_words']and code==(capture/'native.sass').read_bytes()and sha(capture/'native.sass')==item['code_SHA256']
        listing=capture/'native.envydis.txt';assert sha(listing)==item['listing_SHA256']
        variant=next(capture.glob('program-*.variant.bin'));assert sha(variant)==item['variant_SHA256'];v=list(struct.unpack_from('<32I',variant.read_bytes()));assert v==item['variant_words_0_128']
        assert words[9]==64*words[12]+words[11]and words[12]==words[13]
        assert v[10]==((words[12]+15)&~15)*64+((words[11]+511)&~511)+512
        assert v[12]==words[7]and v[14]==words[14]
        rows.append({'function':item['function'],'source_depth':item['source_depth'],'GPR':words[7],
                     'metadata_word9':words[9],'metadata_word11':words[11],'native_frame':words[12],
                     'native_spill':words[14],'decoded_allocation_word40':v[10],
                     'code_bytes':len(code),'code_SHA256':item['code_SHA256'],'control_instructions':len(item['control_instruction_lines'])})
    return rows

def verify():
    p=ROOT/'results/control-flow-progress-20261015';native=ROOT/'results/control-flow-native-build-20261015-02';programs=ROOT/'results/control-flow-programs-build-20261015-02'
    pm=load(programs/'manifest.json');assert pm['status']=='PASS'and pm['external_CRS_offline_only']and not pm['GPU_execution']and len(pm['programs'])==8
    assert sha(native/'control_flow.metal')==pm['MSL_SHA256']and sha(native/'control_flow.air')==pm['AIR_SHA256']
    for n,h in pm['source_SHA256'].items():assert sha(programs/n)==h
    for n,h in pm['archives_SHA256'].items():assert sha(ROOT/'build/mesa'/n)==h
    for row in pm['programs']:
        name=row['name'];assert sha(programs/name/'program.sass')==row['code_SHA256']and load(programs/name/'info.json')==row['info']
        assert '[unknown'not in(programs/('decode-'+name+'.stdout')).read_text()
    lib=ROOT/'results/control-flow-runtime-library-build-20261015';lm=load(lib/'manifest.json');pin=sha(lib/'libKeplerMetal.a');assert pin==lm['static_library_SHA256']
    for n,h in lm['source_SHA256'].items():
        assert sha(lib/n)==h;current=ROOT/n
        if not current.exists():
            assert n=='src/KeplerFP64Programs.inc';current=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-02/KeplerMetalSDK/src/KeplerFP64Programs.inc'
        assert sha(current)==h
    native_rows=observations(ROOT/'results/control-flow-native-observations-20261015-02');entry_rows=observations(ROOT/'results/control-flow-entry-observations-20261015')
    assert len(native_rows)==8 and len(entry_rows)==2
    q=ROOT/'results/control-flow-qualification-20261015';assert load(q/'status.json')=={'status':'FAIL','mode':'depth96','phase':'CPU','retry':False}
    native_cases=[]
    for row in load(q/'history.json'):
        if row['phase']!='CPU':assert row['exit_code']==0;continue
        if row['mode']=='depth96':assert row['exit_code']!=0;continue
        assert row['exit_code']==0;root=Path(row['result']);assert terminal(root)['static_library_SHA256']==pin
        native_cases.append(numeric(root))
    assert len(native_cases)==7
    failed=failure(ROOT/'results/control-flow-extended-20261015-depth96',False)
    instrumented=failure(ROOT/'results/control-flow-entry-depth96-20261015',True)
    entry_control=numeric(ROOT/'results/control-flow-entry-depth0-20261015')
    selected=ROOT/'results/control-flow-preserving-qualification-20261015';ss=load(selected/'status.json');assert ss['status']=='PASS'and not ss['full_standard_matrix']
    imports=[];roots={}
    for row in load(selected/'history.json'):
        assert row['exit_code']==0
        if row['phase']!='CPU':continue
        root=Path(row['result']);assert terminal(root)['static_library_SHA256']==pin
        d=load(root/'results.json');r=numeric(root);imports.append(r);roots[row['mode']]=root
        if d['program_replaced']:
            profile=d['profile'];assert profile==load(root/'assets'/(d['function']+'.json'))
            assert profile['code_SHA256']==sha(programs/d['function']/'program.sass')
    assert len(imports)==9 and sum(r['trials']for r in imports if r['kernel_dispatches'])==60 and sum(r['trials']for r in imports if not r['kernel_dispatches'])==48
    matched=0
    for depth in[0,4,8,16,24]:
        candidate=roots['nak:depth'+str(depth)];reference=ROOT/'results'/('control-flow-extended-20261015-depth'+str(depth))
        for f in(reference/'outputs').iterdir():assert f.read_bytes()==(candidate/'outputs'/f.name).read_bytes();matched+=1
    cas=[]
    for mode in ['execute','negative']:
        root=ROOT/'results'/('control-flow-CAS-'+mode+'-20261015');d=load(root/'results.json');assert d['control_flow_prelude']and d['descriptor_transport_prelude']and d['control_flow_import']['contract_verified']
        assert load(root/'inputs.json')['module_static_library_SHA256']==pin;cas.append(cas_numeric(root))
    start=load(p/'start.json')
    for row in start['system_before']:assert sha(row['path'])==row['SHA256']
    assert len(start['system_before'])==83 and sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==start['OCLP_SHA256']
    passing=native_cases+imports
    return {'status':'PARTIAL','evidence_verification':'PASS','standard_matrix':'FAIL native depth96',
            'runtime_library_SHA256':pin,'MSL_SHA256':pm['MSL_SHA256'],'programs_manifest_SHA256':sha(programs/'manifest.json'),
            'native_observations':native_rows,'entry_observations':entry_rows,'native_pass_trials':84,'native_failure':failed,'entry_only_native96':instrumented,'instrumented_depth0':{k:v for k,v in entry_control.items()if k!='files_SHA256'},
            'import_pass_trials':60,'negative_control_trials':48,'exact_uint32_results':sum(r['exact_uint32_results']for r in passing),
            'kernel_invocation_witnesses':sum(r['kernel_invocation_witnesses']for r in passing),
            'guard_bytes_passing_matrix':sum(r['guard_bytes']for r in passing),'native_AIR_files_matched':matched,
            'qualified_compiler_CRS_bytes':[1024,1536,2048],'qualified_NAK_scratch_bytes':[0,100,296],
            'native_failures_are_not_expected_successes':True,'NAK_depth40_execution':'NOT RUN; native96 carrier lacks a valid final result',
            'NAK_depth64_96':'Offline only; no fitting qualified carrier; depth96 code also exceeds current import limit',
            'CAS_operations_after_control_and_descriptor':cas[0]['correct_CAS_operations'],'CAS_rejection_controls':8,
            'system_files_unchanged':83,'OCLP_unchanged':True,'performance_benchmark':False,'M1_reference':'NOT RUN','Qwen_job_ids':[],
            'full_objective_complete':False,'next':'Reduce native96 failure: distinguish control depth, spill frame and code size; retain entry witness and independent native controls'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=verify();out=a.out.resolve();out.relative_to(ROOT/'results')
    with out.open('x')as f:json.dump(d,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in d.items()if k not in['native_observations','entry_observations','instrumented_depth0']},indent=2))
