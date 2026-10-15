#!/usr/bin/env python3
"""Raw CPU oracle for the same portable Metal client on either host."""
from pathlib import Path
import argparse,hashlib,json,struct
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,portable=False):
 root=Path(root);d=json.loads((root/'results.json').read_text());inp=json.loads((root/'inputs.json').read_text());m=json.loads((root/'execution/manifest.json').read_text())
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal' and not d['system_modified']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 assert m['reservation_module_SHA256']==inp['runtime_SHA256']['lab_gpu_reservation.py'] and m['launcher_SHA256']==inp['runtime_SHA256']['run_sdk_host.py']
 if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
 cap=d['capabilities'];assert cap['registry_id'] and cap['name'];status=d.get('status','CAPABILITIES_ONLY')
 if status in ['NATIVE_ICB_FACTORY_EXCEPTION','NATIVE_ICB_FACTORY_NIL','CAPABILITIES_ONLY','ADAPTER_NOT_LINKED']:
  assert d.get('GPU_dispatches',0)==0 and not d.get('runs')
  return {'status':'OBSERVED_UNAVAILABLE' if status.startswith('NATIVE_ICB') else 'PASS_CAPABILITIES','observation':status,'capabilities':cap,'user_dispatches':0,'performance_benchmark':False}
 assert status=='EXECUTED' and d['scope_restored'] and d['caller_data_wiped'] and not d['performance_benchmark']
 prep=d['mode']=='prepare';nativeICB=d['mode']=='native_icb';adapter=d['mode'] in ['prepare','execute']
 assert d['native_ICB']==nativeICB and d['native_ICB_copy_on_GPU']==nativeICB and d['adapter_CPU_snapshot_copy']==adapter and d['ordinary_native_reference']==(d['mode']=='native')
 assert len(d['runs'])==7;M=0xffffffff;state=0x17d904e3;table=[]
 for i in range(256):state=(state*1664525+1013904223)&M;table.append(state^((i*0x9e3779b9)&M))
 assert json.loads((root/'assets/cpu_icb_literal_lut_values.json').read_text())['values']==table
 words=invocations=guards=records=0;hashes={}
 def load(name):raw=(root/'outputs'/name).read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest();return raw
 for t,r in enumerate(d['runs']):
  n=[65,4113,16321][t%3];seed=0x4d2713+97*t;salt=0x7719+53*t;active=[0,2,3] if t==2 else [] if t==4 else [0,1,2,3];locals=[1024]*4 if t>=5 else [64,256,128,512]
  assert r['trial']==t and r['count']==n and r['seed']==seed and r['salt']==salt and r['locals']==locals and r['selected_indices']==active and r['before_commit_untouched']
  assert r['committed']==(not prep) and r['command_status']==(0 if prep else 4) and r['scope_restored_before_commit']==(t==6)
  if adapter:assert r['execution_event']['executed_indices']==active
  else:assert not r['execution_event']
  records+=len(active);source=bytearray(b'\xa5'*262656);values=[]
  for j in range(n):v=((j*11+0x73193211)&M,(j^0x11998877)+97*t,(j*65537)^salt,((j+seed)*13)&M);values.append(v);struct.pack_into('<4I',source,256+j*16,*v)
  assert load(r['input_file'])==bytes(source);guards+=len(source)-n*16
  for i,file in enumerate(r['outputs']):
   want=bytearray(b'\xa5'*262656);executed=not prep and i in active;N=[16,64,128,256][i];fnSeed=seed+29*i;fnSalt=salt+71*i
   for j,v in enumerate(values):
    if executed:
     k=(j*5+fnSeed)&(N-1);a=table[k];b=table[(k^31)&(N-1)];s=a&31;rot=((v[2]<<s)|(v[2]>>(32-s)))&M
     struct.pack_into('<4I',want,128+j*16,(v[0]+a)&M,((v[1]^b)+fnSalt)&M,rot^fnSeed,(v[3]*3+table[(k+7)&(N-1)])&M)
    else:want[128+j*16:128+(j+1)*16]=b'\xc7'*16
   assert load(file)==bytes(want),file;guards+=len(want)-n*16
   if executed:words+=n*4;invocations+=n
  counter=bytearray(b'\xa5'*208);struct.pack_into('<4I',counter,128,*[n if not prep and i in active else 0 for i in range(4)]);assert load(r['counter_file'])==bytes(counter);guards+=192
 return {'status':'PASS','mode':d['mode'],'capabilities':cap,'main_command_buffers':0 if prep else 7,'encoded_records':records,'exact_uint32_words':words,'GPU_invocations_counted':invocations,'guard_bytes_verified':guards,'native_ICB':nativeICB,'copy_mechanism':'GPU-timeline native copy' if nativeICB else 'CPU snapshot helper' if adapter else 'direct reference, no ICB copy','core_source_compilations':0,'performance_benchmark':False,'raw_SHA256':hashes}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
