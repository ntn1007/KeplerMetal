#!/usr/bin/env python3
"""Independent uint32 nested-loop oracle, complete input/output and guard checks."""
from pathlib import Path
import argparse,hashlib,json,struct
MASK=(1<<32)-1
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rol5(x):return ((x<<5)|(x>>27))&MASK
def result(depth,gid,seed,reserved,serial=False,pressure=False):
    value=lambda i:((((gid*129+i)*1664525+1013904223)&MASK)^seed)
    if pressure:
        words=depth*8;key=value(128)^seed;checksum=key^gid
        for i in range(words):checksum=(rol5(checksum^value(i%128))+(key^((i*2891336453)&MASK)))&MASK
        return checksum,key,words,0xcafe0000^gid
    initial=(value(0)+seed+gid*747796405)&MASK
    def layer(level,state):
        visits=0;limit=1+((value(level+1)^seed^reserved)&1)
        for turn in range(limit):
            state=(rol5(state^value(level+1))+level*2891336453+turn)&MASK
            if turn==0 and level+1<depth:
                state,child=layer(level+1,state);visits+=child
            state=(((state*1664525+1013904223)&MASK)^(level*97+turn+reserved))&MASK
            visits+=1
        return state,visits
    if serial:
        state,visits=initial,0
        for level in range(depth):
            for turn in range(1+((value(level+1)^seed^reserved)&1)):
                state=(rol5(state^value(level+1))+level*2891336453+turn)&MASK
                state=(((state*1664525+1013904223)&MASK)^(level*97+turn+reserved))&MASK;visits+=1
    else:state,visits=layer(0,initial)if depth else(initial,0)
    assert depth<=visits<=2*depth
    return rol5(state)^seed,state,visits,0xcafe0000^gid
def verify(root,apple_reference=False):
    root=Path(root);d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text())
    assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
    assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
    for n,h in inp['source_hashes'].items():assert sha(root/n)==h
    for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
    if apple_reference:
        assert d.get('reference_target')=='Apple M1 Max'and d['device']=='Apple M1 Max'
        assert inp['architecture']=='arm64'and inp['reference_target']=='Apple M1 Max'
        assert not d['program_replaced']
    else:assert d['device']=='NVIDIA GeForce GTX 880M'and d['registry_id']==4294968458
    imported=d['mode'].startswith('nak:')
    assert d['native_reference']==(not imported) and d['program_replaced']==imported
    if imported:
        profile=d['profile'];info=profile['program_info'];carrier=profile['carrier'];w=carrier['metadata_words'];v=carrier['variant_words_0_128']
        assert info['semantic']==d['function'] and info['sm']==30 and info['source_language']=='MSL/AIR'
        assert info['scratch_bytes']<=w[12] and info['registers']<=w[7] and info['crs_bytes']<=((w[11]+511)&~511)
        assert w[9]==64*w[12]+w[11] and w[12]==w[13] and not w[35]
        assert sha(root/'assets'/(d['function']+'.sass'))==profile['code_SHA256']
        assert sha(root/'assets'/(carrier['function']+'-native.sass'))==carrier['code_SHA256']
        proof=d['import'];assert proof['contract_verified'] and not proof['rejected_import'] and d['caller_inputs_mutated_after_import']
        events=[e for e in proof['events']if e.get('code_replaced')];assert events
        for e in events:
            assert e['imported_code_identical'] and e['native_metadata_preserved_except_instruction_count'] and e['code_input_unchanged_after_constructor']
            assert e['decoded_code_bytes']==info['code_bytes'] and e['decoded_registers']==w[7] and e['decoded_instruction_count']==info['code_bytes']//8-1
            assert e['decoded_allocation_word_40']==v[10] and e['decoded_spill_bytes_56']==v[14] and e['launch_words_9_11']==[w[9],w[11]]
    assert not d['CPU_expected_answers_uploaded']and not d['system_modified']and not d['performance_benchmark']
    depth=d['depth'];assert isinstance(depth,int)and 0<=depth<=120 and d['function']=='depth'+str(depth)
    variant=d.get('variant','nested');assert variant in ['nested','reload_bounds','serial','pressure']
    if (root/'assets/control_flow_config.json').exists():assert json.loads((root/'assets/control_flow_config.json').read_text())['variant']==variant
    mode=d['mode'][4:]if imported else d['mode'];dispatch=not mode.startswith('no_dispatch:');counts=[1,31,32,33,64,128,256,512,1024,99,256,2048];locals_=[1,31,32,33,64,128,256,512,1024,33,64,1024]
    assert len(d['runs'])==12;checked=guards=missing=visits=0;files={}
    for trial,row in enumerate(d['runs']):
        n=counts[trial];seed=0x13579+trial*971;reserved=trial%3
        assert row['trial']==trial and row['threads']==n and row['seed']==seed and row['reserved']==reserved and row['stride']==129
        if apple_reference:
            requested=row.get('requested_local',row['local']);assert requested==locals_[trial]
            assert row['local']==(requested if requested<=d['max_threads']else 1)
        else:assert row['local']==locals_[trial]
        assert n%row['local']==0 and row['groups']*row['local']==n and row['command_status']==4 and row['kernel_dispatches']==int(dispatch)
        assert row['input_bytes']==256+n*129*4 and row['output_bytes']==256+n*16
        want_input=bytearray(b'\xa5'*row['input_bytes']);want_output=bytearray(b'\xa5'*row['output_bytes'])
        for i in range(n*129):struct.pack_into('<I',want_input,128+4*i,((i*1664525+1013904223)&MASK)^seed)
        for gid in range(n):
            values=result(depth,gid,seed,reserved,variant=='serial',variant=='pressure')
            if dispatch:struct.pack_into('<4I',want_output,128+16*gid,*values);visits+=values[2]
            else:missing+=sum(x!=0xa5a5a5a5 for x in values)
        if dispatch:checked+=4*n
        for key,want in [('input_file',want_input),('output_file',want_output)]:
            file=root/'outputs'/row[key];got=file.read_bytes();assert got==want,(depth,trial,key);files[row[key]]=sha(file)
        guards+=512
    return {'status':'PASS','depth':depth,'variant':variant,'mode':d['mode'],'trials':12,'kernel_dispatches':12 if dispatch else 0,'exact_uint32_results':checked,
            'kernel_invocation_witnesses':checked//4,'loop_body_visits':visits,'guard_bytes':guards,'negative_expected_words_absent':missing,
            'files_SHA256':files,'native_only':not imported,'performance_benchmark':False,'full_objective_complete':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--apple-reference',action='store_true');a=p.parse_args();d=verify(a.directory,a.apple_reference)
    with(a.directory/'independent-verification.json').open('x')as f:json.dump(d,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in d.items()if k!='files_SHA256'},indent=2))
