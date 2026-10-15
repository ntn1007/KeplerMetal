#!/usr/bin/env python3
"""Independent LUT arithmetic and byte/guard oracle for registered GPU copies."""
from pathlib import Path
import argparse,hashlib,json,struct

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(root,portable=False):
 root=Path(root);read=lambda n:json.loads((root/n).read_text());d,m,inp=read('results.json'),read('execution/manifest.json'),read('inputs.json')
 native=d['native_reference'];mode=d['mode'];prepare=mode=='prepare';negative=mode=='no_second';completed=mode.endswith('_completed');width=2 if mode.startswith('range')else 1;slots=width*3
 assert mode in ['prepare','chain','range','chain_completed','range_completed','no_second'] and d['width']==width and d['slots']==slots and d['scope_restored']
 assert d['device']==('Apple M1 Max'if native else'NVIDIA GeForce GTX 880M') and d['registry_id'] and (native or d['registry_id']==4294968458)
 assert not any(d[k]for k in ['system_modified','CPU_expected_answers_uploaded','intermediate_descriptor_CPU_readback','performance_benchmark','full_ICB_contract'])
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
 mask=0xffffffff;state=0x17d904e3;table=[]
 for i in range(256):state=(state*1664525+1013904223)&mask;table.append(state^((i*0x9e3779b9)&mask))
 assert read('assets/cpu_icb_literal_lut_values.json')['values']==table
 sizes=[[16,128,256,64,16,256],[128,256,16,256,64,128],[256,16,128,16,256,64]];locals=[32,64,128,256,512,1024];bytes_=8192*16+512
 words=invocations=guards=0;hashes={};assert len(d['runs'])==3
 def load(name):p=root/'outputs'/name;raw=p.read_bytes();hashes[name]=sha(p);return raw
 for t,r in enumerate(d['runs']):
  specs=[]
  for k in range(slots):
   n=[65,2057,4113][t]+k*17;l=locals[k];specs.append({'function':'literal_lut_'+str(sizes[t][k]),'count':n,'local':l,'groups':(n+l-1)//l,'seed':0x4d2713+t*97+k*29,'salt':0x7719+t*53+k*71,'stage':k})
  assert r['trial']==t and r['node_specs']==specs and r['committed']==(not prepare) and r['command_status']==(0 if prepare else 4) and r['before_commit_untouched']
  assert r['source_reset_after_completed_producer']==completed and r['ICB_and_parameter_external_refs_released_before_commit']
  source=bytearray(b'\xa5'*bytes_);values=[]
  for i in range(8192):
   v=((i*11+0x73193211)&mask,(i^0x11998877)+97*t,(i*65537)^0x7719,((i+0x4d2713+t*97)*13)&mask);values.append(v);struct.pack_into('<4I',source,256+i*16,*v)
  assert load(r['input_file'])==source;guards+=512
  counts=[0]*6;assert len(r['outputs'])==slots
  for k,name in enumerate(r['outputs']):
   active=not prepare and (width*2<=k<slots if negative else k<width);expected=bytearray(b'\xa5'*bytes_)
   if active:
    spec=specs[k];n=spec['count'];seed=spec['seed'];salt=spec['salt'];N=sizes[t][k];counts[k]=n
    for i,v in enumerate(values[:n]):
     j=(i*5+seed)&(N-1);a=table[j];b=table[(j^31)&(N-1)];shift=a&31;rot=((v[2]<<shift)|(v[2]>>(32-shift)))&mask
     struct.pack_into('<4I',expected,128+i*16,(v[0]+a)&mask,((v[1]^b)+salt)&mask,rot^seed,(v[3]*3+table[(j+7)&(N-1)])&mask)
    words+=n*4;invocations+=n
   assert load(name)==expected,name;guards+=bytes_-(specs[k]['count']*16 if active else 0)
  counter=bytearray(b'\xa5'*208);struct.pack_into('<6I',counter,128,*counts);assert load(r['counter_file'])==counter;guards+=184
  events=r['copy_events']
  if native:assert not events
  else:
   copies=[e for e in events if e['operation']=='GPU_QMD_copy'];executions=[e for e in events if e['operation']=='executeCommandsInBuffer'];assert len(copies)==(1 if negative else 2) and len(executions)==1
   for j,c in enumerate(copies):
    assert c['source_location']==j*width and c['destination_index']==(j+1)*width and c['length']==width and c['bytes']==256*width and c['whole_range_preflight'] and not c['CPU_shadow_is_execution_source']
    for k,pair in enumerate(c['descriptor_pairs']):assert pair['copied_function']==specs[k]['function'] and pair['copied_groups']==specs[k]['groups'] and pair['copied_local']==specs[k]['local'] and pair['destination_original_function']==specs[(j+1)*width+k]['function'] and pair['owners']==j+2
   e=executions[0];assert e['executed_indices']==list(range(width*2,width*3)) and e['location']==width*2 and e['length']==width
   if negative:assert not e.get('resident_GPU_descriptor',False)
   else:
    assert e['resident_GPU_descriptor'];p=e['evidence'];assert p['command_bytes']==24*width and p['resident_launches']==width and p['owners']==slots and p['CPU_QMD_uploads_in_launch']==p['CPU_constant_uploads_in_launch']==p['native_preparation_GPU_dispatches']==0
    owners=p['owner_original_profiles'];assert len(owners)==slots and len({x['registration_id']for x in owners})==1 and all(x['registration_id']and len(x['manifest_SHA256'])==64 for x in owners)
    assert sorted(x['original_record_function']for x in owners)==sorted(x['function']for x in specs)
    for owner in owners:
     bank=owner['native_literal_bank_0'];N=int(owner['original_record_function'].split('_')[-1]);assert owner['binding_layout_v2'] and owner['constant_buffer_valid_mask']==7 and owner['native_register_count']==14 and owner['static_threadgroup_bytes']==0
     assert bank['bytes']==(256 if N<=64 else 512 if N==128 else 1024) and bank['variant_owner_retained'] and not bank['literal_contents_CPU_read']
 return {'status':'PASS_UNCOMMITTED'if prepare else'PASS_EXPECTED_OLD_DESTINATION'if negative else'PASS','mode':mode,'native_reference':native,'exact_uint32_words':words,'GPU_invocations_counted':invocations,'guard_and_untouched_bytes_verified':guards,'raw_files':len(hashes),'width':width,'slots':slots,'CB0_sizes_qualified':[] if native else [256,512,1024],'binding_count':4,'program_names_hardcoded_in_runtime':False,'integration_level':0 if native else 2,'performance_benchmark':False,'full_ICB_contract':False,'raw_SHA256':hashes}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items()if k!='raw_SHA256'},indent=2))
