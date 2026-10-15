#!/usr/bin/env python3
"""Verify raw pixels/DMA/tessellation arithmetic independently of host counters."""
from pathlib import Path
import argparse,hashlib,json,math,struct
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(directory):
 root=Path(directory);d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text());family=d['family'];policy=d['policy'];cancel=policy=='cancel';host=family.startswith('host_');tess=family in ['tessellation','native_tess'];native=family.startswith('native_')or host
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']and sha(root/'execution/application')==m['signed_binary_sha256']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 assert(root/'KeplerProgramImport.h').read_text().count('NS_RETURNS_RETAINED')==6
 assert d['device']=='NVIDIA GeForce GTX 880M'and d['registry_id']==4294968458 and d['mode']==family+':'+policy and d['native_pipeline_control']==native and len(d['runs'])==4 and not d['system_modified']and not d['performance_benchmark']
 raw={};checked=guards=invocations=0;states=[]
 def load(name):p=root/'outputs'/name;raw[name]=sha(p);return p.read_bytes()
 for trial,r in enumerate(d['runs']):
  assert r['trial']==trial and r['caller_pool_drained_before_commit']and r['caller_bundle_retained']==(policy=='keep')and r['status_before_commit']==0 and r['committed']==(not cancel)and r['command_status']==(0 if cancel else 4)and not r['CPU_expected_answers_uploaded']
  assert r['factory_buffers_observed']==(3 if host else 4 if tess else 2)
  assert not r['pipeline_alive_after_release']and r['factory_buffers_alive_after_release']==0 and not r['target_alive_after_release'],(family,policy,trial,'lifetime',r['pipeline_alive_after_release'],r['factory_buffers_alive_after_release'],r['target_alive_after_release'])
  if not native:
   p=r['import'];assert p['contract_verified'];events=[e for e in p['events']if e.get('code_replaced')];assert len(events)==(2 if family=='graphics'else 1)
   for e in events:assert e['imported_code_identical']and e['original_graphics_header_preserved']
  else:assert not r['import']
  s=r['spec']
  if cancel:assert not r['files'];states.append({'trial':trial,'submitted':False,'all_observed_objects_released':True});continue
  if host:
   n=[257,1025,4096,8191][trial];size=n*16+128;assert s['count']==n and s['requested_buffer_bytes']==size and s['NoCopy']==(family=='host_nocopy')
   requests=[size,size,48];noCopy=family=='host_nocopy';assert s['factory_lengths']==([((x+4095)//4096)*4096 for x in requests]if noCopy else requests)and s['factory_storage_modes']==[0 if noCopy else 1]*3
   a=bytearray(b'\xa5'*size);b=bytearray(a);scales=[.5,-1.5,2,.25];bias=[.125+trial/32,-.25,.5,1]
   for i in range(n):
    for c in range(4):
     x=((i*17+c*3+trial*7)%67-32)/32;struct.pack_into('<f',a,64+i*16+c*4,x);struct.pack_into('<f',b,64+i*16+c*4,x*scales[c]+bias[c])
   assert load(r['files']['input'])==a and load(r['files']['output'])==b,(family,policy,trial,'affine/DMA');checked+=n*8;guards+=256;invocations+=n
  elif tess:
   factor=[0,1,8,64][trial];assert s=={'factor':factor,'capacity':32768};counter=load(r['files']['counter']);assert len(counter)==132 and counter[:64]==b'\xa5'*64 and counter[68:]==b'\xa5'*64;n=struct.unpack_from('<I',counter,64)[0];assert n==[0,3,90,4874][trial],(family,trial,'same-driver reference invocation count',n)
   coords=load(r['files']['coordinates']);values=load(r['files']['values']);assert len(coords)==len(values)==32768*16+128
   for b in [coords,values]:assert b[:64]==b'\xa5'*64 and b[64+n*16:]==b'\xa5'*(len(b)-64-n*16)
   for i in range(n):
    c=struct.unpack_from('<4f',coords,64+i*16);v=struct.unpack_from('<4f',values,64+i*16);assert all(math.isfinite(x)and 0<=x<=1 for x in c)and c[3]==1 and abs(sum(c[:3])-1)<=2e-7
    for k in range(4):
     expected=1 if k==3 else c[k]*c[k]if native else c[k]*c[k]*.5+.125
     assert math.isfinite(v[k])and abs(v[k]-expected)<=1e-7,(family,trial,i,k,v[k],expected)
   checked+=n*8;invocations+=n;guards+=128+2*(len(coords)-n*16)
  else:
   W,H=32+trial*16,24+trial*8;color=[(1+trial)/16,(3+trial)/16,(7+trial)/16,(11+trial)/16];assert s=={'width':W,'height':H,'color':color,'prefix_bytes':256}
   expected=color[:]
   if family in ['vertex','graphics']:expected=[x*.5+(.5 if c==3 else .125)for c,x in enumerate(expected)]
   if family in ['fragment','graphics']:expected=[x*.75+[.0625,.125,.1875,.25][c]for c,x in enumerate(expected)]
   pixels=load(r['files']['pixels']);assert len(pixels)==W*H*16+512 and pixels[:256]==b'\xa5'*256 and pixels[-256:]==b'\xa5'*256
   for i in range(W*H):
    for c,got in enumerate(struct.unpack_from('<4f',pixels,256+i*16)):assert math.isfinite(got)and abs(got-expected[c])<=2e-6,(family,policy,trial,i,c,got,expected[c])
   checked+=W*H*4;guards+=512
  states.append({'trial':trial,'submitted':True,'all_observed_objects_released':True})
 if cancel:assert not list((root/'outputs').iterdir())
 return {'status':'PASS','family':family,'policy':policy,'trials':4,'submitted_trials':0 if cancel else 4,'numeric_components_checked':checked,'guard_bytes':guards,'consumer_invocations_counted_or_expected':invocations,'raw_files':len(raw),'raw_SHA256':raw,'states':states,'full_objective_complete':False,'performance_benchmark':False,'tessellation_topology_oracle':False,'physical_VRAM_cache_cleanup_proven':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args();v=verify(a.directory)
 with(a.receipt or a.directory/'independent-verification.json').open('x')as f:json.dump(v,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in v.items()if k!='raw_SHA256'},indent=2))
