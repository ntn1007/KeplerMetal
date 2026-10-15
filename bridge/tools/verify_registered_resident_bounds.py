#!/usr/bin/env python3
"""Independent LUT arithmetic and byte/guard oracle for registered GPU copies."""
from pathlib import Path
import argparse,hashlib,json,struct

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(root,portable=False):
 root=Path(root);read=lambda n:json.loads((root/n).read_text());d,m,inp=read('results.json'),read('execution/manifest.json'),read('inputs.json')
 native=d['native_reference'];mode=d['mode'];prepare=False;negative=False;completed=False;width=2;cold=mode=='prepare_short';slots=width*3
 assert mode in ['prepare_short','copy_short'] and d['width']==width and d['slots']==slots and d['scope_restored']
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
   active=k==(0 if cold else 2);expected=bytearray(b'\xa5'*bytes_)
   if active:
    spec=specs[k];n=spec['count'];seed=spec['seed'];salt=spec['salt'];N=sizes[t][k];counts[k]=n
    for i,v in enumerate(values[:n]):
     j=(i*5+seed)&(N-1);a=table[j];b=table[(j^31)&(N-1)];shift=a&31;rot=((v[2]<<shift)|(v[2]>>(32-shift)))&mask
     struct.pack_into('<4I',expected,128+i*16,(v[0]+a)&mask,((v[1]^b)+salt)&mask,rot^seed,(v[3]*3+table[(j+7)&(N-1)])&mask)
    words+=n*4;invocations+=n
   assert load(name)==expected,name;guards+=bytes_-(specs[k]['count']*16 if active else 0)
  counter=bytearray(b'\xa5'*208);struct.pack_into('<6I',counter,128,*counts);assert load(r['counter_file'])==counter;guards+=184
  assert r['refused'] and r['no_events_before_refusal'] and r['active_index']==(0 if cold else 2) and r['undersized_input_bytes']==16 and 'Resident schema2 buffer range is insufficient' in r['refusal_reason']
  events=r['copy_events'];assert not any(e['operation']=='GPU_QMD_copy'for e in events)
  executions=[e for e in events if e['operation']=='executeCommandsInBuffer'];assert len(executions)==1 and executions[0]['executed_indices']==[r['active_index']] and not executions[0].get('resident_GPU_descriptor',False)
 return {'status':'PASS_EXPECTED_REFUSAL_WITH_VALID_COMMAND_UNCHANGED','mode':mode,'native_reference':native,'exact_uint32_words':words,'GPU_invocations_counted':invocations,'guard_and_untouched_bytes_verified':guards,'raw_files':len(hashes),'width':width,'slots':slots,'CB0_sizes_qualified':[],'binding_count':4,'program_names_hardcoded_in_runtime':False,'integration_level':0 if native else 2,'performance_benchmark':False,'full_ICB_contract':False,'raw_SHA256':hashes}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items()if k!='raw_SHA256'},indent=2))
