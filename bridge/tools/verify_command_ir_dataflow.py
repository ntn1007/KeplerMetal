#!/usr/bin/env python3
"""Recompute each dependency stage using integer CPU arithmetic and verify guards."""
from pathlib import Path
import argparse,hashlib,json,struct
from verify_local_memory import verify_device_identity
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
MASK=(1<<32)-1
CANARY=0xa5a5a5a5
def verify_native_function_arguments(d,inputs):
 assert d['producer_backend']=='native_msl' and inputs['native_function_arguments']
 assert d['public_argument_encoder'] and d['function_argument_encoder'] and not d['argument_refusal_probe']
 events=d['function_events'];registrations=[e for e in events if e.get('operation')=='register_native_source_IRv2_function']
 assert len(registrations)==1
 e=registrations[0];assert e['library_SHA256']==inputs['assets_SHA256']['native_producer.metallib']
 assert e['function']==d['producer_info']['function'] and not e['instruction_import'] and e['native_pipeline_factories_preserved'] and not e['Apple_ICB_identity'] and not e['GPU_execution']
 schema=e['schema'];assert schema['buffer_index']==0 and schema['binding_count']==4 and schema['encoded_length']==48 and schema['alignment']==8
 assert [(m['type'],m['offset'],m['index'])for m in schema['members']]==[(t,i*8,i)for i,t in enumerate([60,85,60,60,60,60])]
 getters=[e for e in events if e.get('operation')=='function_IRv2_argument_encoder']
 # One initial getter checks the compiled root stride before trial encoders.
 assert len(getters)==(2 if d['mode']=='encoder_reuse'else 5)
 if d['mode']!='encoder_reuse':assert sum(e['reflection_requested']for e in getters)==2
 assert all(e.get('native_reflection_preserved')for e in getters if e['reflection_requested'])
 restores=[e for e in events if e.get('operation')=='restore_IRv2_functions'];assert len(restores)==1 and restores[0]['live_functions_restored']==1
 assert not any(e.get('operation')in ['register_native_IRv2_producer','new_registered_IRv2_pipeline']for e in events)
 for r in d['runs']:
  encoded=[e for e in r['events']if e.get('operation')=='encode_public_IRv2_arguments']
  assert len(encoded)==4 and all(not e['native_Apple_ICB_identity']and e['bytes']==48 for e in encoded)

def verify(directory):
 root=Path(directory);d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode'];native=d['native_reference'];copy=mode=='copy';duplicate=mode=='duplicate_templates';source_count=6 if duplicate else 3;rows=4 if copy else 3;slots=source_count+rows;stable=False
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert d['scope_restored']and not d['CPU_expected_answers_uploaded']and not d['IR_CPU_read_before_execution']and not d['performance_benchmark']and not d['system_modified']and len(d['runs'])==4
 if native:assert d['device']=='Apple M1 Max'
 else:
  inp=json.loads((root/'inputs.json').read_text());assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
  for n,h in inp['source_hashes'].items():assert sha(root/n)==h
  for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
  verify_device_identity(d)
  assert d['producer_info']['command_ir_version']==2
  if d.get('producer_backend')=='native_msl':
   info=d['producer_info'];assert d['producer_import']=={} and not info['instruction_import'] and not info['Apple_ICB_layout']
   assert info['producer_backend']=='native_msl' and info['root_bytes']==48 and info['thread_width']==32 and info['pipeline_class']=='NVMTLComputePipelineState'
   assert info['library_SHA256']==sha(root/'assets/native_producer.metallib')
   if inp.get('native_function_arguments'):verify_native_function_arguments(d,inp)
   stable=bool(inp.get('native_stable_pipeline_identities'))
   if stable:
    ids=d['producer_info']['stable_pipeline_IDs'];assert len(ids)==len(set(ids))==3 and all(x>>32==0x4b505350 and x&0xffffffff for x in ids)
    assert d['producer_info']['context_version']==3
  else:
   assert d['producer_import']['contract_verified']and not d['producer_import']['rejected_import']
   for e in d['producer_import']['events']:
    if e.get('code_replaced'):assert e['imported_code_identical']and e['decoded_code_bytes']==d['producer_info']['code_bytes']and e['decoded_registers']==d['producer_info']['registers']
 assert d['API_refusals']==(8 if mode=='refusals'else 0)
 sizes=[256,1024,4096,32768];locals_=[[32,128,1024],[33,256,512],[128,33,1024],[1024,256,33]];files={};comparisons=invocations=guardbytes=0;duplicate_GPU_choices=0
 def load(name):
  p=root/'outputs'/name;files[name]=sha(p);return p.read_bytes()
 for trial,r in enumerate(d['runs']):
  source_order=[(trial+i)%3 for i in range(source_count)]if stable else[0,1,2]
  n=sizes[trial];specs=[{'stage':s,'count':n,'seed':0x13579+trial*97+s*101,'salt':0x7654321+trial*31+s*137,'local':locals_[trial][s],'groups':(n+locals_[trial][s]-1)//locals_[trial][s]}for s in range(3)]
  length=max(s['groups']*s['local']for s in specs)*16+512
  source_locals=[(64 if specs[stage]['local']==32 else 32)if duplicate and ((trial+stage)&1)==i//3 else specs[stage]['local']for i,stage in enumerate(source_order)]
  candidate_for_stage=[next(i for i,stage in enumerate(source_order)if stage==s and source_locals[i]==specs[s]['local'])for s in range(3)]
  if duplicate:
   assert stable
   last_for_stage=[max(i for i,stage in enumerate(source_order)if stage==s)for s in range(3)]
   events=[e for e in r['events']if e.get('operation')=='encode_public_IRv2_arguments']
   assert len(events)==4
   for e,stage in zip(events,[0,1,2,0]):assert e['root_template_index']==last_for_stage[stage] and e['execution_template_resolved_on_GPU'] and 'candidate'not in e
   duplicate_GPU_choices+=sum(a!=b for a,b in zip(last_for_stage,candidate_for_stage))
  assert r['trial']==trial and r['specs']==specs and r['buffer_bytes']==length and r['rows']==rows and r['command_status']==4 and r['intermediate_CPU_waits']==0
  assert r['producer_present']==(mode!='no_producer')and r['consumer_present']==(mode!='no_consumer')
  outputs=[];counts=[0,0,0]
  for stage in range(3):
   enabled=mode not in ['no_producer','no_consumer']and mode!=['no_seed','no_gather','no_finish'][stage]and not(stage==0 and mode.startswith('bad_'))
   values=[(CANARY,)*4 for _ in range(n)];seed=specs[stage]['seed'];salt=specs[stage]['salt']
   if enabled:
    for i in range(n):
     if stage==0:v=(i+seed,((i*1664525+1013904223)&MASK)^seed,(i^seed)+salt,(i*17)^salt)
     elif stage==1:
      a,b,c,e=(CANARY,)*4 if mode=='descriptor_negative'else outputs[0][(i*5+seed)&(n-1)];v=(c+salt,a^seed,e+i,b*3)
     else:
      a,b,c,e=(CANARY,)*4 if mode=='descriptor_negative'else outputs[1][n-1-i];v=(b+e,c^salt,a+i,e+seed)
     values[i]=tuple(x&MASK for x in v)
    counts[stage]=n;comparisons+=n*4;invocations+=n
   outputs.append(values)
  expected={k:bytearray(b'\xa5'*length)for k in ['input','dummySrc',*[f'dummy{k}'for k in range(slots)],'stage0','stage1','stage2']}
  for stage,values in enumerate(outputs):
   for i,v in enumerate(values):struct.pack_into('<4I',expected[f'stage{stage}'],128+i*16,*v)
  for k,c in [('counter',counts),('dummyCounter',[0,0,0])]:
   expected[k]=bytearray(b'\xa5'*256);struct.pack_into('<3I',expected[k],128,*c)
  for name,data in expected.items():
   got=load(r['files'][name]);assert got==data,(mode,trial,name,next((i for i,(a,b)in enumerate(zip(got,data))if a!=b),None));guardbytes+=len(data)-(n*16 if name.startswith('stage')else 12 if name in ['counter','dummyCounter']else 0)
  raw=load(r['files']['records']);assert len(raw)==1216
  if stable:
   assert r['queried_pipeline_IDs']==ids
   roots=struct.unpack('<18Q',load(r['root_file']));assert len(roots)==18
   for stage in range(3):
    offset=stage*6
    assert roots[offset]==r['GPU_addresses']['producerContext'] and roots[offset+1]==ids[stage]
    assert roots[offset+2]==r['GPU_addresses'][f'stage{stage}']+128
    assert roots[offset+3]==r['GPU_addresses'][f'stage{stage-1}'if stage else'input']+128
    assert 0<roots[offset+4]<1<<40 and roots[offset+5]==r['GPU_addresses']['counter']+128
   assert len({roots[s*6+4]for s in range(3)})==3
   context=struct.pack('<4IQ2I',0x4b505343,3,rows,4,r['GPU_addresses']['records']+128,128,source_count)
   for stage,local in zip(source_order,source_locals):context+=struct.pack('<QQ10I',ids[stage],roots[stage*6+4],(n+local-1)//local,1,1,local,1,1,0,2,0,0)
   context+=bytes((8-source_count)*56)
   assert load(r['files']['producerContext'])==context
  if native:assert raw==b'\xa5'*1216
  else:
   assert raw[:128]==b'\xa5'*128 and raw[128+rows*128:]==b'\xa5'*(1216-128-rows*128)
   witness=bytearray(b'\xa5'*(128+rows*64));witness[64:64+rows*64]=bytes(rows*64);recordwords={}
   nativeTemplates=load(r['files']['nativeTemplates'])if'nativeTemplates'in r['files']else None
   nativeBindings=load(r['files']['nativeBindings'])if'nativeBindings'in r['files']else None
   if nativeBindings is not None:
    assert len(nativeTemplates)==source_count*65536 and len(nativeBindings)==source_count*3*128
    for candidate in range(source_count):
     for resource in range(3):
      names=[f'stage{resource}',f'stage{resource-1}'if resource else'input',None,'counter']
      for slot in [0,1,3]:
       if source_order[candidate]==0 and slot==1:continue
       at=(candidate*3+resource)*128+slot*32
       assert struct.unpack_from('<Q',nativeBindings,at+8)[0]==r['GPU_addresses'][names[slot]]+128
       assert struct.unpack_from('<I',nativeBindings,at+16)[0]==128
   for row in range(rows):
    stage=0 if row==3 else row;part=raw[128+row*128:256+row*128];empty=(copy and row==0)or mode==['no_seed','no_gather','no_finish'][stage]
    resource=0;bank=0;groups=[0,1,1];local=[source_locals[0],1,1]
    if mode=='no_producer':assert part==b'\xa5'*128;status=2
    elif empty:assert part==struct.pack('<I',0x4b504952)+bytes(124);status=0
    else:
     w=list(struct.unpack('<32I',part));want=[0]*32;want[:12]=[0x4b504952,379 if mode=='barrier'else 371,candidate_for_stage[stage],0x4b504950,specs[stage]['groups'],1,1,0,specs[stage]['local'],1,1,0]
     mutated=mode.startswith('bad_')and row==0
     changes={'bad_parameters':(16,1),'bad_counter':(26,1),'bad_pipeline':(2,8),'bad_buffer3_flag':(1,115),'bad_groups':(4,0),'bad_reserved':(28,1)}
     pointerwords=[12,13,14,15,16,17,26,27]
     change,value=changes[mode]if mutated else(-1,0)
     for i in pointerwords:want[i]=w[i]
     if mutated:want[change]=value
     assert w==want,(mode,trial,row,'record structure')
     for i in [12,14,16,26]:
      if i!=change:assert 0<(w[i]|w[i+1]<<32)<1<<40
     recordwords[row]=w
     status=2 if mutated else 1
     if status==1:bank=candidate_for_stage[stage];resource=stage;groups=[specs[stage]['groups'],1,1];local=[specs[stage]['local'],1,1]
    struct.pack_into('<16I',witness,64+row*64,*groups,bank,*local,resource,status,0x4b504952,3,2,0,0,0,0x4b50524d)
    if nativeTemplates is not None:
     expectedCB=bytearray(nativeTemplates[bank*65536:(bank+1)*65536])
     for off,v in [(0x700,groups),(0x720,[a*b for a,b in zip(groups,local)]),(0x740,groups)]:struct.pack_into('<3I',expectedCB,off,*v)
     if status==1 and nativeBindings is not None:
      for slot in [0,1,3]:
       start=(bank*3+resource)*128+slot*32;expectedCB[slot*32:(slot+1)*32]=nativeBindings[start:start+32]
     elif status==1:
      # Historical pointer-only attempt is retained for diagnosing the failure.
      for slot,start in [(0,12),(1,14),(3,26)]:struct.pack_into('<2I',expectedCB,slot*32+8,*recordwords[row][start:start+2])
     if mode=='descriptor_negative'and row in [1,2]:
      old=nativeTemplates[bank*65536+32:bank*65536+40];assert old!=expectedCB[32:40];expectedCB[32:40]=old
     assert load(r['files'][f'CB1-{row}'])==expectedCB,(mode,trial,row,'full native CB1')
   assert load(r['files']['witness'])==witness,(mode,trial,'witness')
   seedrow=3 if copy else 0
   if seedrow in recordwords and 1 in recordwords:
    a,b=recordwords[seedrow],recordwords[1]
    assert a[12:14]==b[14:16]and(mode=='bad_counter'or a[26:28]==b[26:28])and a[16:18]!=b[16:18]
   if 1 in recordwords and 2 in recordwords:
    a,b=recordwords[1],recordwords[2];assert a[12:14]==b[14:16]and a[26:28]==b[26:28]and a[16:18]!=b[16:18]
 report={'status':'PASS','mode':mode,'native_reference':native,'trials':4,'exact_uint32_results':comparisons,'consumer_invocations':invocations,'guard_bytes':guardbytes,'API_refusals':d['API_refusals'],'raw_files':len(files),'raw_SHA256':files,'performance_benchmark':False,'full_objective_complete':False}
 if d.get('producer_backend')=='native_msl':report.update(producer_backend='native_msl',producer_instruction_import=False)
 if d.get('producer_backend')=='native_msl' and inp.get('native_function_arguments'):report.update(native_function_arguments=True,function_getters_restored=True)
 if stable:report.update(stable_pipeline_identities=True,immutable_contexts_checked=4,template_permutations_checked=4)
 if duplicate:assert duplicate_GPU_choices==6;report.update(duplicate_templates=True,duplicate_GPU_choices_different_from_root_representative=duplicate_GPU_choices)
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args();r=verify(a.directory)
 with(a.receipt or a.directory/'independent-verification.json').open('x')as f:json.dump(r,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in r.items()if k!='raw_SHA256'},indent=2))
