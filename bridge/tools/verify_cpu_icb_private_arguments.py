#!/usr/bin/env python3
"""Independent raw FIFO, Private table, numeric and lifetime qualification."""
from pathlib import Path
import argparse, base64, hashlib, json, math, struct
from decode_native_commands import decode
LIB='16fb242714c00ac7390a923fc4953ea3b94ae7623431d79c18e354beb616c77f'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());execute=d['mode']=='execute'
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
 if not portable:assert sha(root/'cpu_icb_private_arguments_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_private_arguments_probe')==m['signed_binary_sha256']
 assert sha(root/'private_fragment_resources.metallib')==inp['library_SHA256']==d['library_SHA256']==LIB and sha(root/'cpu_icb_private_argument_profiles.json')==inp['manifest_SHA256']==d['manifest_SHA256']
 assert d['registry_id']==4294968458 and d['passed'] and d['scope_restored'] and d['integration_level']==1 and d['native_command_memory_modified'] and not any(d[k] for k in ('system_modified','installed_driver_modified','general_GPU_handle_generation','performance_benchmark','GPU_resident_ICB','full_ICB_contract'))
 # Native command memory IS modified by the scoped record transport; a probe's
 # declaration must distinguish this from changing native code or the driver.
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current:assert sha(Path(__file__).resolve().parents[1]/('src' if n.startswith('Kepler') or n.endswith(('.json','.metal')) else 'tools')/n)==h
 assert len(d['runs'])==8 and {x['case'] for x in d['rejections']}=={'Private_CPU_encoding','Private_source_table','pending_other_command_buffer'} and all(x['rejected'] for x in d['rejections'])
 channels=invocations=records=0;maximum=0;rawhash={}
 def load(n):p=root/'outputs'/n;rawhash[n]=sha(p);return p.read_bytes()
 def pixel(tex,params,x,y,bank):
  p=params[bank];src=tex[bank]
  if bank:
   x1=min(x+1,63);y1=min(y+1,47);v=[src[(y*64+x)*4+k]*.75*.875+src[(y*64+x1)*4+k]*.25*.875+src[(y1*64+x)*4+k]*.75*.125+src[(y1*64+x1)*4+k]*.25*.125 for k in range(4)]
  else:v=[src[(y*64+x)*4+k] for k in range(4)]
  return [v[k]*p[k]+p[k+4] for k in range(4)]
 for t,r in enumerate(d['runs']):
  produced=t in (2,3,5,6,7);bank=1 if t in (1,3,5,6,7) else 0;draw=t!=5;ordinary=t in (0,3,7)
  assert r['trial']==t and r['committed']==execute and r['command_status']==(4 if execute else 0) and r['GPU_producer']==produced and r['consumer_drawn']==draw
  assert r['bound_storage_mode']==(0 if t==0 else 2) and not r['CPU_access_to_Private_contents'] and not r['CPU_read_between_producer_consumer'] and r['same_command_buffer_producer_consumer']==(t!=6 or not execute)
  assert r['producer_status']==(4 if execute else 0) and r['copied_and_source_reset']==(t in (3,7)) and r['source_mutated_after_snapshot']==(t in (3,7)) and r['ordinary_native_draw_after_ICB']==ordinary
  banks=load(f'trial-{t}.banks.bin');assert len(banks)==1024
  for start,end in [(0,256),(280,512),(536,1024)]:assert banks[start:end]==b'\xa5'*(end-start)
  if t in (3,7):mutated=bytearray(banks);mutated[512]^=1;assert load(f'trial-{t}.banks-mutated.bin')==mutated
  e=r['execution_event'];assert e['executed_indices']==([0] if draw else [])
  rows=e['evidence'].get('sequence_records',[]);assert len(rows)==(1 if draw else 0)
  for j,row in enumerate(rows):
   raw=load(f'trial-{t}.record-{j}.commands.bin');prefix=load(f'trial-{t}.record-{j}.prefix.bin');assert raw==struct.pack('<6I',0xa0050e0c,4,3,1,0,0)==base64.b64decode(row['commands_base64']) and base64.b64decode(row['primer_draw_base64'])==struct.pack('<6I',0xa0050e0c,4,1,1,0,0) and row['native_primer_draw_removed']
   assert prefix==base64.b64decode(row['prefix_base64']) and hashlib.sha256(prefix).hexdigest()==row['prefix_SHA256'];ps=decode(prefix) if prefix else []
   if ps and ps[0]['method']=='0xe04':
    for k,p in enumerate(ps[:16]):assert p['method']==hex(0xe04+k*16) and p['values']==[64<<16,48<<16]
    assert len(ps)>=16;ps=ps[16:]
   assert not ps or len(ps)==1 and ps[0]['method']=='0x3ab0' and ps[0]['values']==[0]
   assert row['record']['library_SHA256']==LIB and row['record']['name']=='linear' and row['record']['fragment_buffers']==1 and e['caller_pipeline_restored'] and e['caller_fragment_slots_restored']==1;records+=1
  private=e['evidence'].get('Private_fragment_tables',[]);assert len(private)==(1 if draw and t else 0)
  for p in private:assert p['storage_mode']==2 and not p['CPU_access_to_Private_contents'] and p['client_must_not_write_result'] and p['source_tables']==(2 if produced else 1) and p['same_command_buffer']==(t!=6 or not execute) and p['payload_SHA256']==hashlib.sha256(banks[256+bank*256:280+bank*256]).hexdigest()
  tex=[];params=[]
  for k in range(2):
   raw=load(f'trial-{t}.texture-{k}.bin');expected=bytearray()
   for y in range(48):
    for x in range(64):expected+=struct.pack('<4f',((x*3+y*5+k*7)&63)/64,((x*7+y*11+k*3)&63)/64,(((x^y)+k*5)&31)/32,1)
   assert raw==expected;tex.append(struct.unpack('<12288f',raw));p=load(f'trial-{t}.params-{k}.input.bin');assert p[:256]==b'\xa5'*256 and p[288:]==b'\xa5'*224;values=struct.unpack_from('<8f',p,256);assert values==((1,1,1,1,0,0,0,0) if k==0 else (.5,1.5,2,1,.125,.25,.5,0));params.append(values)
   assert load(f'trial-{t}.params-{k}.after.bin')==(p if execute else b'\xa5'*512)
  before=load(f'trial-{t}.image-before.bin');image=load(f'trial-{t}.image.bin');assert before==b'\xa5'*49664 and image[:256]==before[:256] and image[-256:]==before[-256:];ab=load(f'trial-{t}.private-arguments.bin');counter=load(f'trial-{t}.counter.bin')
  if not execute:assert image==before and ab==b'\xa5'*1024 and counter==b'\xa5'*512;continue
  expected=bytearray(b'\xa5'*1024);expected[256:280]=banks[256+bank*256:280+bank*256]
  if produced:expected[512:536]=banks[512:536]
  assert ab==expected and counter[:256]==b'\xa5'*256 and counter[260:]==b'\xa5'*252 and struct.unpack_from('<I',counter,256)[0]==(6 if produced else 0);invocations+=6 if produced else 0
  actual=struct.unpack_from('<12288f',image,256)
  for y in range(48):
   for x in range(64):
    expected=pixel(tex,params,x,y,0) if ordinary and x<16 else pixel(tex,params,x,y,bank) if draw else (0,0,0,0)
    for k in range(4):a=actual[(y*64+x)*4+k];error=abs(a-expected[k]);maximum=max(maximum,error);assert math.isfinite(a) and error<=2e-6,(t,x,y,k,a,expected[k]);channels+=1
 assert d['runs'][-1]['resource_leases_before_commit']
 return {'status':'PASS','mode':d['mode'],'main_command_buffers':9 if execute else 0,'render_command_buffers':8 if execute else 0,'copied_draw_records':records,'correct_float32_channels':channels,'maximum_error':maximum,'counted_GPU_word_writes':invocations,'Private_argument_tables_in_CPU_ICB_qualified':execute,'GPU_selection_of_native_encoded_tables_in_CPU_ICB_qualified':execute,'completed_producer_reuse':execute,'pending_other_producer_refused':True,'source_snapshot_mutation_control':True,'scope_restored':True,'all_children_terminal':True,'integration_level':1,'GPU_resident_ICB':False,'full_ICB_contract':False,'performance_benchmark':False,'source_sha256':inp['source_hashes'],'raw_sha256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ('source_sha256','raw_sha256')},indent=2))
