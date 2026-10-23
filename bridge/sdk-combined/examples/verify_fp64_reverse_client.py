#!/usr/bin/env python3
"""Raw typed conversion and GPU roundtrip oracle; all finite bits are exact."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from verify_local_memory import verify_device_identity
import argparse,hashlib,json,struct
from fp64_reverse_inputs import OPS,columns,packed,expected_bits,equivalent_for
from fp64_conversion_inputs import expected_bits as promote,equivalent as equivalent64
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def verify(root,portable=False):
 root=Path(root);read=lambda n:json.loads((root/n).read_text());d=read('results.json');inp=read('inputs.json');m=read('execution/manifest.json');pins=read('assets/fp64_manifest.json');q=d['qualification'];prep=d['mode']=='prepare';negative=d['mode']=='no_producer'
 if 'device_identity' in d:verify_device_identity(d)
 assert d['mode'] in ['prepare','execute','no_producer'] and ('device_identity' in d or d['registry_id']==4294968458) and d['constructor_restored'] and d['device_class_restored'] and d['bad_program_rejected'] and d['caller_program_data_wiped']
 assert not any(d[k] for k in ['system_modified','performance_benchmark','CPU_expected_answers_uploaded','intermediate_CPU_readback'])
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 for name,h in inp['source_hashes'].items():assert sha(root/name)==h
 for name,h in inp['assets_SHA256'].items():assert sha(root/'assets'/name)==h
 if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
 operations=['add','mul','fma','div','sqrt','from_i64','from_u64','from_f32',*OPS];expected_names={f'{op}-l{local}' for op in operations for local in [32,128,1024]}
 assert inp['core_source_compilations']==0 and len(q['programs'])==len(pins['programs'])==60 and q['inputs_copied'] and q['constructor_restored'] and q['rounding']=='per_operation' and q['arithmetic_rounding']=='nearest_even' and not q['registration_is_GPU_qualification']
 pin_by_name={f"{r['operation']}-l{r['local']}":r for r in pins['programs']};assert set(pin_by_name)==expected_names and set(q['available_operations'])==set(operations)
 assert q['carrier_SHA256']==pins['carrier_SHA256']==sha(root/'assets/fp64_carrier.metallib') and {p['program'] for p in q['programs']}==expected_names
 for p in q['programs']:
  row=pin_by_name[p['program']];proof=p['import'];assert p['constructor_restored'] and p['code_SHA256']==row['code_SHA256']==sha(root/'assets'/('fp64_'+p['program']+'.sass'))
  assert proof['contract_verified'] and proof['target_imports']==proof['verified_imports']>0 and not proof['rejected_import']
  for e in proof['events']:assert e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields'] and e['code_input_unchanged_after_constructor'] and e['decoded_code_bytes']==row['info']['code_bytes'] and e['decoded_registers']==row['info']['registers']
 for op in OPS:
  c=q['output_contracts'][op];assert c['rounding']==op[-2:] and c['output_format']==('binary32_low32_zero_high' if op.startswith('to_f32_') else 'int64_twos_complement' if op.startswith('to_i64_') else 'uint64') and c['integer_out_of_range']==('not_applicable' if op.startswith('to_f32_') else 'saturate; NaN→0')
 assert {r['case'] for r in d['refusals']}=={'wrong_arity_0','wrong_arity_1','wrong_arity_2','misaligned_typed_output'} and all(r['rejected'] and not r['committed'] for r in d['refusals'])
 assert len(d['runs']) in [1,9];checked=direct=roundtrips=tags=guards=dispatches=differences=0;hashes={};mode_differences={}
 for t,r in enumerate(d['runs']):
  n=[65,2057,12289][t%3];local=[32,128,1024][t%3];assert r['trial']==t and r['recipe_trial']==t%3 and r['count']==n and r['local']==local and r['before_commit_untouched'] and r['library_released_before_commit']==(t+1==len(d['runs'])) and r['committed']==(not prep) and r['command_status']==(0 if prep else 4)
  values=columns('to_f32_rn',local,n,t%3)[0];assert (root/'assets'/f'reverse-input-l{local}-t{t%3}.bin').read_bytes()==packed(values);expected=[[expected_bits(op,v) for v in values] for op in OPS]
  assert len(r['inputs'])==2 and len(r['outputs'])==len(r['events'])==36
  for wide,name in enumerate(r['inputs']):
   raw=bytearray(b'\xa5'*(256+n*16+128));stride=16 if wide else 8
   for i,v in enumerate(values):
    struct.pack_into('<Q',raw,256+i*stride,v)
    if wide:struct.pack_into('<Q',raw,256+i*stride+8,0x77aa55cc8899dd00)
   path=root/'outputs'/name;assert path.read_bytes()==bytes(raw);hashes[name]=sha(path);guards+=len(raw)-n*stride
  for k,name in enumerate(r['outputs']):
   path=root/'outputs'/name;raw=path.read_bytes();hashes[name]=sha(path);assert len(raw)==128+n*16+256 and raw[:128]==b'\xa5'*128 and raw[128+n*16:]==b'\xa5'*256,'Guard violation: stop GPU tests';guards+=384
   skipped=negative and k==0;event=r['events'][k]
   if skipped:assert event=={'skipped_producer':True,'encoded_dispatches':0}
   else:
    op=OPS[k//2] if k<24 else ['from_f32','from_i64','from_u64'][(k-24)//4];program=op+f'-l{local}'
    assert event['program']==program and event['count']==n and event['local']==local and event['encoded_dispatches']==1 and not event['CPU_arithmetic'] and not event['CPU_readback']
    stride=(16 if k%2 else 8) if k<24 else 16;offset=256 if k<24 else 128;assert event['inputs']==[{'offset':offset,'stride':stride,'extent':(n-1)*stride+8}] and event['output_offset']==128 and event['output_stride']==16
    if not prep:dispatches+=1
   if prep or skipped:assert raw[128:128+n*16]==b'\xc7'*(n*16);continue
   for i in range(n):
    observed,index,stamp=struct.unpack_from('<QII',raw,128+i*16)
    if k<24:wanted=expected[k//2][i];good=equivalent_for(OPS[k//2],observed,wanted);direct+=1
    else:
     reverse=k-24;source=0xc7c7c7c7c7c7c7c7 if negative and reverse==0 else expected[reverse][i];back=['from_f32','from_i64','from_u64'][reverse//4];wanted=promote(back,source);good=equivalent64(observed,wanted);roundtrips+=1
     if negative and reverse==0:differences+=not equivalent64(wanted,promote(back,expected[reverse][i]))
    assert good,(t,k,i,f'{observed:016x}',f'{wanted:016x}');assert index==i and stamp==(0x85d10000^(t*101)^(k*31));checked+=1;tags+=1
  if not prep and not negative:
   for target in ['f32','i64','u64']:
    base=['f32','i64','u64'].index(target)*4
    for other in [1,2,3]:
     key=target+'_rn_vs_'+['rn','rz','rp','rm'][other];mode_differences[key]=mode_differences.get(key,0)+sum(not equivalent_for(OPS[base],expected[base][i],expected[base+other][i]) for i in range(n))
 if negative and not prep:assert differences>0
 if not prep and not negative:assert all(v>0 for v in mode_differences.values()),mode_differences
 return {'status':'PASS_EXPECTED_MISSING_PRODUCER' if negative else 'PASS','mode':d['mode'],'trials':len(d['runs']),'exact_results':checked,'reverse_results':direct,'GPU_roundtrip_results':roundtrips,'GPU_invocations_with_correct_tags':tags,'user_dispatches':dispatches,'guard_bytes_verified':guards,'negative_differences_from_full_chain':differences,'rounding_mode_differences':mode_differences,'programs':60,'core_source_compilations':0,'constructor_restored':True,'integration_level':2,'performance_benchmark':False,'general_IEEE_conformance':False,'raw_SHA256':hashes}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
