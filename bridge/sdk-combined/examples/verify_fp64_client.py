#!/usr/bin/env python3
"""Reconstruct inputs and exact CPU references; check direct and GPU chains."""
from pathlib import Path
import argparse,hashlib,json,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fp64_cpu_oracle import expected,equivalent,value,bits
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
OPS=['add','mul','fma','div','sqrt'];CHAIN=['div','sqrt','fma','add','mul']
CURATED=[0,0x8000000000000000,1,0x8000000000000001,0x0010000000000000,0x000fffffffffffff,0x7fefffffffffffff,0x7ff0000000000000,0xfff0000000000000,0x7ff8000000000042,0x3ff0000000000000,0x4000000000000000,0x4010000000000000,0xc010000000000000,0x3fe0000000000000,0x3ff0000000000001]
def reconstruct(n,t):
 state=0x880320261014+104729*t;columns=[];mask=(1<<64)-1
 for c in range(3):
  col=[]
  for i in range(n):
   state=(state^(state<<13))&mask;state^=state>>7;state=(state^(state<<17))&mask
   v=(state&0x000fffffffffffff)|((988+(state>>52)%71)<<52)
   if i<16:v=CURATED[(i+c*3+t)%16]
   if c==2 and i>=16:v^=(i&1)<<63
   col.append(v)
  col[16]=[0x3ff0000002000000,0x3feffffffc000000,0xbff0000000000000][c];columns.append(col)
 return columns
def verify(root,portable=False):
 root=Path(root);d=json.loads((root/'results.json').read_text());inp=json.loads((root/'inputs.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());prep=d['mode']=='prepare';negative=d['mode']=='no_producer'
 assert d['mode'] in ['prepare','execute','no_producer'] and d['registry_id']==4294968458
 assert d['bad_program_rejected'] and d['caller_program_data_wiped'] and d['constructor_restored'] and d['device_class_restored']
 assert not any(d[k] for k in ['CPU_expected_answers_uploaded','intermediate_CPU_readback','system_modified','performance_benchmark'])
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 assert inp['core_source_compilations']==0
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 if not portable:assert sha(root/'application')==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
 q=d['qualification'];pins=json.loads((root/'assets/fp64_manifest.json').read_text())
 assert q['inputs_copied'] and q['constructor_restored'] and not q['registration_is_GPU_qualification'] and q['input_strides']==[8,16] and q['output_stride']==16 and q.get('arithmetic_rounding',q['rounding'])=='nearest_even'
 if 'output_contracts' in q:assert all(q['output_contracts'][op]['rounding']=='rn' for op in ['add','mul','fma','div','sqrt'])
 assert len(q['programs'])==len(pins['programs']) and len(pins['programs']) in (15,24,60) and q['carrier_SHA256']==pins['carrier_SHA256']==sha(root/'assets/fp64_carrier.metallib')
 pin_by_name={f"{p['operation']}-l{p['local']}":p for p in pins['programs']}
 for p in q['programs']:
  pin=pin_by_name[p['program']];proof=p['import'];assert p['constructor_restored'] and p['code_SHA256']==pin['code_SHA256']==sha(root/'assets'/('fp64_'+p['program']+'.sass'))
  assert proof['contract_verified'] and not proof['rejected_import'] and proof['target_imports']==proof['verified_imports'] and proof['verified_imports']>0
  assert pin['info']['strided_inputs'] and p['gprs']==pin['info']['registers'] and p['code_bytes']==pin['info']['code_bytes']
  for e in proof['events']:assert e['imported_code_identical'] and e['code_input_unchanged_after_constructor'] and e['metadata_bytes_preserved_except_import_fields'] and e['decoded_code_bytes']==p['code_bytes'] and e['decoded_registers']==p['gprs']
 assert {r['case'] for r in d['refusals']}=={'stride24','misaligned_output','overlapping_input_output','missing_operand','unsupported_local','short_output','over_count_limit'} and len(d['refusals'])==7 and all(r['rejected'] and not r['committed'] for r in d['refusals'])
 specs=[(op,mask) for op in OPS for mask in range(1<< (1 if op=='sqrt' else 3 if op=='fma' else 2))];assert len(specs)==22
 correct=tagged=guard=negative_differences=dispatches=0;raw_hashes={};per_operation={op:0 for op in OPS}
 assert len(d['runs']) in [1,9]
 for t,r in enumerate(d['runs']):
  n=[65,2057,12289][t%3];local=[32,128,1024][t%3]
  assert r['trial']==t and r['count']==n and r['local']==local and r['input_offset']==256 and r['output_offset']==128 and r['before_commit_untouched']
  assert r['library_released_before_commit']==(t==len(d['runs'])-1) and r['committed']==(not prep) and r['command_status']==(0 if prep else 4)
  assert len(r['inputs'])==6 and len(r['outputs'])==27 and len(r['direct_events'])==22 and len(r['chain_events'])==5
  cols=reconstruct(n,t);values=[[value(v) for v in c] for c in cols]
  for j,file in enumerate(r['inputs']):
   raw=(root/'outputs'/file).read_bytes();assert len(raw)==256+n*16+128
   body=b''.join(struct.pack('<Q',v) for v in cols[j]) if j<3 else b''.join(struct.pack('<QQ',v,0x77aa55cc8899dd00) for v in cols[j-3])
   assert raw==b'\xa5'*256+body+b'\xa5'*(len(raw)-256-len(body));guard+=len(raw)-len(body);raw_hashes[file]=hashlib.sha256(raw).hexdigest()
  refs={op:[expected(op,a,b,c) for a,b,c in zip(*values)] for op in OPS}
  full=[];control=[]
  for i,(a,b,c) in enumerate(zip(*values)):
   x=expected('div',a,b,c);y=expected('sqrt',x,b,c);z=expected('fma',y,b,c);u=expected('add',z,a,c);v=expected('mul',u,y,c);full.append([x,y,z,u,v])
   if negative:
    x=value(0xc7c7c7c7c7c7c7c7);y=expected('sqrt',x,b,c);z=expected('fma',y,b,c);u=expected('add',z,a,c);v=expected('mul',u,y,c);control.append([x,y,z,u,v])
  for k,file in enumerate(r['outputs']):
   raw=(root/'outputs'/file).read_bytes();assert len(raw)==128+n*16+256 and raw[:128]==b'\xa5'*128 and raw[-256:]==b'\xa5'*256;guard+=384;raw_hashes[file]=hashlib.sha256(raw).hexdigest()
   if k<22:
    op,mask=specs[k];ev=r['direct_events'][k];stamp=0x62a30000^(t*101)^(k*31);assert ev['program']==f'{op}-l{local}' and ev['stride_mask']==mask and ev['output_offset']==128 and ev['count']==n and ev['stamp']==stamp and ev['encoded_dispatches']==1
    assert [v['stride'] for v in ev['inputs']]==[16 if mask&(1<<i) else 8 for i in range(len(ev['inputs']))] and all(v['offset']==256 for v in ev['inputs'])
    references=refs[op]
   else:
    step=k-22;op=CHAIN[step];ev=r['chain_events'][step];stamp=0x62a30000^(t*101)^0x55221^(step*257)
    if negative and step==0:
     assert ev['skipped_producer'] and ev['encoded_dispatches']==0 and raw[128:128+n*16]==b'\xc7'*(n*16);continue
    assert ev['program']==f'{op}-l{local}' and ev['stride_mask']==[0,1,1,1,3][step] and ev['stamp']==stamp and ev['count']==n and ev['encoded_dispatches']==1
    assert [v['offset'] for v in ev['inputs']]==[[256,256],[128],[128,256,256],[128,256],[128,128]][step]
    references=[v[step] for v in control if negative] if negative else [v[step] for v in full]
   dispatches+=not prep
   if prep:assert raw[128:128+n*16]==b'\xc7'*(n*16);continue
   for i in range(n):
    ob,index,stamp0=struct.unpack_from('<QII',raw,128+i*16)
    assert index==i and stamp0==stamp,'Execution marker mismatch; stop further GPU launches'
    if not equivalent(ob,references[i]):raise AssertionError({'trial':t,'file':file,'row':i,'observed':f'{ob:016x}','expected':f'{bits(references[i]):016x}'})
    correct+=1;tagged+=1;per_operation[op]+=1
    if negative and k>=22:negative_differences+=not equivalent(ob,full[i][k-22])
 assert not negative or negative_differences>0
 return {'status':'PASS_EXPECTED_DIFFERENCE' if negative else 'PASS','mode':d['mode'],'trials':len(d['runs']),'exact_results_for_executed_programs':correct,'GPU_invocations_with_correct_tags':tagged,'exact_results_per_operation':per_operation,'negative_differences_from_full_chain':negative_differences,'guard_bytes_verified':guard,'user_dispatches':dispatches,'main_command_buffers':0 if prep else len(d['runs']),'all_22_input_stride_combinations':not prep,'GPU_only_chain':not prep and not negative,'library_released_before_last_commit':True,'refused_encoding_cases':7,'bad_program_rejected':True,'constructor_restored':True,'core_source_compilations':0,'integration_level':2,'performance_benchmark':False,'exhaustive_IEEE_conformance':False,'raw_SHA256':raw_hashes}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
