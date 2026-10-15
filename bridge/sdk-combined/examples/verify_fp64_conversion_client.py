#!/usr/bin/env python3
"""Recompute conversion bits and dependent addition from independent raw data."""
from pathlib import Path
import argparse, hashlib, json, struct
from fp64_conversion_inputs import OPS, columns, packed, expected_bits, equivalent

sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
value=lambda word:struct.unpack('<d',struct.pack('<Q',word))[0]
bits=lambda number:struct.unpack('<Q',struct.pack('<d',number))[0]

def verify(root,portable=False):
 root=Path(root);read=lambda name:json.loads((root/name).read_text());d=read('results.json');inp=read('inputs.json');m=read('execution/manifest.json');pins=read('assets/fp64_manifest.json');q=d['qualification'];prep=d['mode']=='prepare';negative=d['mode']=='no_producer'
 assert d['mode'] in ['prepare','execute','no_producer'] and d['registry_id']==4294968458 and d['constructor_restored'] and d['device_class_restored'] and d['bad_program_rejected'] and d['caller_program_data_wiped']
 assert not any(d[k] for k in ['system_modified','performance_benchmark','CPU_expected_answers_uploaded','intermediate_CPU_readback'])
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 for name,h in inp['source_hashes'].items():assert sha(root/name)==h
 for name,h in inp['assets_SHA256'].items():assert sha(root/'assets'/name)==h
 if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
 assert inp['core_source_compilations']==0 and len(q['programs'])==len(pins['programs']) and len(pins['programs']) in (24,60) and q['inputs_copied'] and q['constructor_restored'] and q.get('arithmetic_rounding',q['rounding'])=='nearest_even' and not q['registration_is_GPU_qualification']
 operations=['add','mul','fma','div','sqrt',*OPS]+([f'to_{target}_{mode}' for target in ['f32','i64','u64'] for mode in ['rn','rz','rp','rm']] if len(pins['programs'])==60 else [])
 expected_names={f'{op}-l{local}' for op in operations for local in [32,128,1024]}
 pin_by_name={f"{r['operation']}-l{r['local']}":r for r in pins['programs']};assert set(pin_by_name)==expected_names and set(q['available_operations'])==set(operations)
 assert q['carrier_SHA256']==pins['carrier_SHA256']==sha(root/'assets/fp64_carrier.metallib') and {p['program'] for p in q['programs']}==expected_names
 for p in q['programs']:
  row=pin_by_name[p['program']];proof=p['import'];assert p['constructor_restored'] and p['code_SHA256']==row['code_SHA256']==sha(root/'assets'/('fp64_'+p['program']+'.sass'))
  assert proof['contract_verified'] and proof['target_imports']==proof['verified_imports']>0 and not proof['rejected_import']
  for e in proof['events']:assert e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields'] and e['code_input_unchanged_after_constructor'] and e['decoded_code_bytes']==row['info']['code_bytes'] and e['decoded_registers']==row['info']['registers']
 expected_refusals={'wrong_arity_'+op for op in OPS}|{'dense_f32_stride4','unknown_operation'}
 assert {r['case'] for r in d['refusals']}==expected_refusals and all(r['rejected'] and not r['committed'] for r in d['refusals'])
 assert len(d['runs']) in (1,9);checked=converted=chained=tags=guards=dispatches=differences=0;hashes={}
 for t,r in enumerate(d['runs']):
  n=[65,2057,12289][t%3];local=[32,128,1024][t%3];recipe=t%3;assert r['trial']==t and r['recipe_trial']==recipe and r['count']==n and r['local']==local and r['before_commit_untouched'] and r['library_released_before_commit']==(t+1==len(d['runs'])) and r['committed']==(not prep) and r['command_status']==(0 if prep else 4)
  assert len(r['inputs'])==6 and len(r['outputs'])==len(r['events'])==9
  raw_columns=[columns(op,local,n,recipe)[0] for op in OPS];expected=[[expected_bits(op,v) for v in col] for op,col in zip(OPS,raw_columns)]
  for j,name in enumerate(r['inputs']):
   raw=bytearray(b'\xa5'*(256+n*16+128));stride=8 if j<3 else 16
   for i,v in enumerate(raw_columns[j%3]):
    struct.pack_into('<Q',raw,256+i*stride,v)
    if stride==16:struct.pack_into('<Q',raw,256+i*stride+8,0x77aa55cc8899dd00)
   path=root/'outputs'/name;assert path.read_bytes()==bytes(raw);hashes[name]=sha(path);guards+=len(raw)-n*stride
  for k,name in enumerate(r['outputs']):
   path=root/'outputs'/name;raw=path.read_bytes();hashes[name]=sha(path);assert len(raw)==128+n*16+256 and raw[:128]==b'\xa5'*128 and raw[128+n*16:]==b'\xa5'*256,'Guard violation: stop GPU tests';guards+=384
   skipped=negative and k==0;event=r['events'][k]
   if skipped:assert event=={'skipped_producer':True,'encoded_dispatches':0}
   else:
    program=(OPS[k//2] if k<6 else 'add')+f'-l{local}';assert event['program']==program and event['count']==n and event['local']==local and event['encoded_dispatches']==1 and not event['CPU_arithmetic'] and not event['CPU_readback']
    expected_views=[{'offset':256,'stride':8 if k%2==0 else 16,'extent':(n-1)*(8 if k%2==0 else 16)+8}] if k<6 else [{'offset':128,'stride':16,'extent':(n-1)*16+8}]*2
    assert event['inputs']==expected_views and event['output_offset']==128 and event['output_stride']==16
    if not prep:dispatches+=1
   if prep or skipped:assert raw[128:128+n*16]==b'\xc7'*(n*16);continue
   for i in range(n):
    observed,index,stamp=struct.unpack_from('<QII',raw,128+i*16)
    if k<6:wanted=expected[k//2][i]
    else:
     a=0xc7c7c7c7c7c7c7c7 if negative and k==6 else expected[k-6][i];b=expected[k-6][i];wanted=bits(value(a)+value(b))
     if negative and k==6:differences+=not equivalent(wanted,bits(value(b)+value(b)))
    assert equivalent(observed,wanted),(t,k,i,f'{observed:016x}',f'{wanted:016x}')
    assert index==i and stamp==(0x73c50000^(t*101)^(k*31)),(t,k,i,index,stamp)
    checked+=1;tags+=1
    if k<6:converted+=1
    else:chained+=1
 if negative and not prep:assert differences==sum(r['count'] for r in d['runs'])
 return {'status':'PASS_EXPECTED_MISSING_PRODUCER' if negative else 'PASS','mode':d['mode'],'trials':len(d['runs']),'exact_results':checked,'conversion_results':converted,'dependent_add_results':chained,'GPU_invocations_with_correct_tags':tags,'user_dispatches':dispatches,'guard_bytes_verified':guards,'negative_differences_from_full_chain':differences,'programs':len(pins['programs']),'core_source_compilations':0,'constructor_restored':True,'integration_level':2,'performance_benchmark':False,'general_IEEE_conformance':False,'input_unique_shapes':3 if len(d['runs'])==9 else 1,'raw_SHA256':hashes}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
