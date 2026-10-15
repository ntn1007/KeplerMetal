#!/usr/bin/env python3
"""Independent image/opaque-copy/count/guard oracle, including prepare gate."""
from pathlib import Path
import argparse, hashlib, json, math, struct
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());execute=d['mode']=='execute'
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
 if not portable:assert sha(root/'native_private_arguments_probe')==m['original_binary_sha256'] and sha(root/'execution/native_private_arguments_probe')==m['signed_binary_sha256']
 assert sha(root/'private_fragment_resources.metallib')==inp['library_SHA256']==d['library_SHA256'] and d['registry_id']==4294968458 and not any(d[k] for k in ('system_modified','native_command_memory_modified','installed_driver_modified','general_GPU_handle_generation','performance_benchmark'))
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current:assert sha(Path(__file__).resolve().parents[1]/('src' if n.endswith('.metal') else 'tools')/n)==h
 assert len(d['runs'])==7
 channels=invocations=0;maximum=0;rawhash={}
 def load(n):p=root/'outputs'/n;rawhash[n]=sha(p);return p.read_bytes()
 for t,r in enumerate(d['runs']):
  produced=t in (2,3,5,6);bank=1 if t in (1,3,5,6) else 0;draw=t!=5
  assert r['trial']==t and r['committed']==execute and r['command_status']==(4 if execute else 0) and r['GPU_producer']==produced and r['consumer_drawn']==draw
  assert r['bound_storage_mode']==(0 if t==0 else 2) and (r['bound_contents_pointer_exposed'] or t!=0) and not r['CPU_access_to_Private_contents'] and r['argument_length']==24 and r['argument_alignment']==256 and r['same_command_buffer_producer_consumer'] and not r['CPU_read_between_producer_consumer']
  banks=load(f'trial-{t}.banks.bin');assert len(banks)==1024
  for start,end in [(0,256),(280,512),(536,1024)]:assert banks[start:end]==b'\xa5'*(end-start)
  tex=[];params=[]
  for k in range(2):
   raw=load(f'trial-{t}.texture-{k}.bin');expected=bytearray()
   for y in range(48):
    for x in range(64):expected+=struct.pack('<4f',((x*3+y*5+k*7)&63)/64,((x*7+y*11+k*3)&63)/64,(((x^y)+k*5)&31)/32,1)
   assert raw==expected;tex.append(struct.unpack('<12288f',raw));p=load(f'trial-{t}.params-{k}.input.bin');assert p[:256]==b'\xa5'*256 and p[288:]==b'\xa5'*224;values=struct.unpack_from('<8f',p,256);assert values==((1,1,1,1,0,0,0,0) if k==0 else (.5,1.5,2,1,.125,.25,.5,0));params.append(values)
   after=load(f'trial-{t}.params-{k}.after.bin');assert after==(p if execute else b'\xa5'*512)
  config=load(f'trial-{t}.configuration.bin');assert config[:256]==b'\xa5'*256 and config[272:]==b'\xa5'*240 and struct.unpack_from('<4I',config,256)==(1 if t in (3,5,6) else 0,6,0x12345678,0x87654321)
  before=load(f'trial-{t}.image-before.bin');image=load(f'trial-{t}.image.bin');assert before==b'\xa5'*49664 and image[:256]==before[:256] and image[-256:]==before[-256:]
  ab=load(f'trial-{t}.private-arguments.bin');counter=load(f'trial-{t}.counter.bin')
  if not execute:assert image==before and ab==b'\xa5'*1024 and counter==b'\xa5'*132;continue
  expected=bytearray(banks);expected[256:280]=banks[256+bank*256:280+bank*256];assert ab==expected
  assert counter[:64]==b'\xa5'*64 and counter[68:]==b'\xa5'*64 and struct.unpack_from('<I',counter,64)[0]==(6 if produced else 0);invocations+=6 if produced else 0
  actual=struct.unpack_from('<12288f',image,256);src=tex[bank];p=params[bank]
  for y in range(48):
   for x in range(64):
    for k in range(4):
     if not draw:v=0
     else:
      if bank:
       x1=min(x+1,63);y1=min(y+1,47);sample=src[(y*64+x)*4+k]*.75*.875+src[(y*64+x1)*4+k]*.25*.875+src[(y1*64+x)*4+k]*.75*.125+src[(y1*64+x1)*4+k]*.25*.125
      else:sample=src[(y*64+x)*4+k]
      v=sample*p[k]+p[k+4]
     a=actual[(y*64+x)*4+k];e=abs(a-v);maximum=max(maximum,e);assert math.isfinite(a) and e<=2e-6,(t,x,y,k,a,v);channels+=1
 assert d['runs'][-1]['resource_leases_before_commit']
 return {'status':'PASS','mode':d['mode'],'main_command_buffers':7 if execute else 0,'correct_float32_channels':channels,'maximum_error':maximum,'tolerance':2e-6,'counted_GPU_word_writes':invocations,'Private_argument_table_native_qualified':execute,'GPU_selection_of_native_encoded_tables_qualified':execute,'general_GPU_handle_generation':False,'producer_omission_control':execute,'consumer_omission_control':execute,'CPU_read_between_producer_consumer':False,'system_modified':False,'all_children_terminal':True,'source_sha256':inp['source_hashes'],'raw_sha256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ('source_sha256','raw_sha256')},indent=2))
