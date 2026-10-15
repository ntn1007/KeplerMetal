#!/usr/bin/env python3
"""Independent raw LUT/rotate oracle for the delivered public-API client."""
from pathlib import Path
import argparse,hashlib,json,struct
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode'];prepare=mode=='prepare';native=mode=='native';assert inp['core_source_compilations']==0
 assert d['registry_id']==4294968458 and d['scope_restored'] and d['caller_data_wiped'] and d['ordinary_native_reference']==native and not d['system_modified'] and not d['performance_benchmark']
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
 M=0xffffffff;table=[];state=0x17d904e3
 for i in range(256):state=(state*1664525+1013904223)&M;table.append(state^((i*0x9e3779b9)&M))
 assert json.loads((root/'assets/cpu_icb_literal_lut_values.json').read_text())['values']==table
 assert len(d['runs'])==7;inv=words=guards=records=0;hashes={}
 def load(n):p=root/'outputs'/n;raw=p.read_bytes();hashes[n]=hashlib.sha256(raw).hexdigest();return raw
 for t,r in enumerate(d['runs']):
  n=[65,4113,16321][t%3];seed=0x4d2713+97*t;salt=0x7719+53*t;active=[0,2,3] if t==2 else [] if t==4 else [0,1,2,3];locals=[1024]*4 if t>=5 else [64,256,128,512]
  assert r['trial']==t and r['count']==n and r['seed']==seed and r['salt']==salt and r['locals']==locals and r['selected_indices']==active and r['committed']==(not prepare) and r['command_status']==(0 if prepare else 4) and r['before_commit_untouched'] and r['scope_restored_before_commit']==(t==6)
  if not native:
   ev=r['execution_event'];assert ev['executed_indices']==active;records+=len(active)
   if active:
    for element,i in zip(ev['evidence']['elements'],active):
     rel=element['relocation'];bank=rel['native_literal_bank_0'];assert bank['bytes']==[256,256,512,1024][i] and bank['variant_owner_retained'] and bank['variant_owner_class']=='NVMTLFunctionVariant' and not bank['literal_contents_CPU_read']
     assert bank['native_code_bytes']==576 and bank['GPU_address']==bank['native_code_GPU_address']+768
     assert rel['function']=='literal_lut_'+str([16,64,128,256][i]) and rel['native_register_count']==14 and rel['local_shape']==[locals[i],1,1] and rel['groups_shape']==[(n+locals[i]-1)//locals[i],1,1]
     assert [(b['index'],b['offset']) for b in rel['bindings']]==[(0,128),(1,256),(2,1024),(3,128)]
  source=bytearray(b'\xa5'*262656);values=[]
  for j in range(n):v=((j*11+0x73193211)&M,(j^0x11998877)+97*t,(j*65537)^salt,((j+seed)*13)&M);values.append(v);struct.pack_into('<4I',source,256+j*16,*v)
  assert load(r['input_file'])==bytes(source);guards+=len(source)-n*16
  for i,file in enumerate(r['outputs']):
   expected=bytearray(b'\xa5'*262656);execute=not prepare and i in active;N=[16,64,128,256][i];fnSeed=seed+29*i;fnSalt=salt+71*i
   for j,v in enumerate(values):
    if execute:
     idx=(j*5+fnSeed)&(N-1);a=table[idx];b=table[(idx^31)&(N-1)];shift=a&31;rot=((v[2]<<shift)|(v[2]>>(32-shift)))&M
     struct.pack_into('<4I',expected,128+j*16,(v[0]+a)&M,((v[1]^b)+fnSalt)&M,rot^fnSeed,(v[3]*3+table[(idx+7)&(N-1)])&M)
    else:expected[128+j*16:128+(j+1)*16]=b'\xc7'*16
   assert load(file)==bytes(expected);guards+=len(expected)-n*16
   if execute:inv+=n;words+=n*4
  counter=bytearray(b'\xa5'*208);struct.pack_into('<4I',counter,128,*[n if not prepare and i in active else 0 for i in range(4)]);assert load(r['counter_file'])==bytes(counter);guards+=192
 return {'status':'PASS','mode':mode,'main_command_buffers':0 if prepare else 7,'exact_uint32_words':words,'GPU_invocations_counted':inv,'guard_bytes_verified':guards,'encoded_records':records,'core_source_compilations':0,'native_CB0_sizes':[256,512,1024],'caller_input_data_wiped':True,'copy_reset_range_empty_precommit_closure_qualified':not prepare,'ordinary_native_reference':native,'integration_level':2,'ordinary_applications_transparent':False,'all_hardware_functions_supported':False,'performance_benchmark':False,'raw_SHA256':hashes}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
