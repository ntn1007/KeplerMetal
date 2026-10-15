#!/usr/bin/env python3
"""CPU color/depth/stencil oracle, independent of the GPU image/readbacks."""
from pathlib import Path
import argparse,base64,hashlib,json,math,struct
from decode_native_commands import decode
LIB='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());execute=d['mode'].endswith('execute');icb=d['ICB'];assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and d['passed'] and d['scope_restored'] and d['registry_id']==4294968458 and not d['system_modified'] and not d['GPU_resident_ICB'] and not d['performance_benchmark'];assert sha(root/'render_state_carrier.metallib')==inp['library_SHA256']==d['library_SHA256']==LIB and sha(root/'cpu_icb_depth_stencil_profiles.json')==inp['manifest_SHA256']==d['manifest_SHA256']
 if not portable:assert sha(root/'depth_stencil_icb_probe')==m['original_binary_sha256'] and sha(root/'execution/depth_stencil_icb_probe')==m['signed_binary_sha256']
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current:assert sha(Path(__file__).resolve().parents[1]/('src' if n.startswith('Kepler') or n.endswith(('.json','.metal')) else 'tools')/n)==h
 assert len(d['runs'])==15;channels=depths=stencils=records=0;maximum=0;rawhash={}
 def load(n):p=root/'outputs'/n;rawhash[n]=sha(p);return p.read_bytes()
 for t,r in enumerate(d['runs']):
  combined=t in (11,12,14);assert r['trial']==t and r['committed']==execute and r['command_status']==(4 if execute else 0) and r['combined_depth_stencil']==combined and not r['CPU_access_to_Private_contents']
  expected_names=['near'] if t<8 or t==13 else ['near','far'] if t in (8,10) else ['far','near'] if t==9 else ['write','read'];assert [a['name'] for a in r['actions']]==expected_names
  for j,a in enumerate(r['actions']):
   raw=load(a['raw_file']);assert len(raw)==a['raw_bytes'] and hashlib.sha256(raw).hexdigest()==a['raw_SHA256'];packets=decode(raw) if raw else []
   if icb:
    e=a['execution_event'];rows=e['evidence'].get('sequence_records',[]);assert len(rows)==(0 if t==13 else 1)
    for row in rows:assert base64.b64decode(row['commands_base64'])==struct.pack('<6I',0xa0050e0c,4,3,1,0,0) and base64.b64decode(row['primer_draw_base64'])==struct.pack('<6I',0xa0050e0c,4,1,1,0,0) and row['native_primer_draw_removed'] and row['record']['name']==a['name'];records+=1
   else:assert packets and packets[-1]['method']=='0x3830' and packets[-1]['values']==[4,1 if t==13 else 3,1,0,0]
  image=load(f'trial-{t}.image.bin');z=load(f'trial-{t}.depth.bin');s=load(f'trial-{t}.stencil.bin') if combined else None;assert len(image)==49664 and len(z)==12800 and image[:256]==b'\xa5'*256 and image[-256:]==b'\xa5'*256 and z[:256]==b'\xa5'*256 and z[-256:]==b'\xa5'*256
  if s is not None:assert len(s)==12800 and s[:256]==b'\xa5'*256 and s[-256:]==b'\xa5'*256
  if not execute:assert image==b'\xa5'*49664 and z==b'\xa5'*12800 and (s is None or s==b'\xa5'*12800);continue
  pixels=struct.unpack_from('<12288f',image,256);actualz=struct.unpack_from('<3072f',z,256)
  for y in range(48):
   if s is not None:assert s[256+y*256+64:256+(y+1)*256]==b'\xa5'*192
   for x in range(64):
    covered=96*(x+.5)<64*(y+.5+48)
    color=(.75,.125,.25,1) if t in (2,3,6,7,8,9) or combined and (not covered if t==12 else covered) else (.25,.875,.5,1) if t==10 else (0,0,0,0);depth=1. if combined else .75 if t==10 else .25
    for k in range(4):a=pixels[(y*64+x)*4+k];error=abs(a-color[k]);maximum=max(maximum,error);assert math.isfinite(a) and error<=2e-6,(t,x,y,k,a,color[k]);channels+=1
    assert actualz[y*64+x]==depth,(t,x,y,actualz[y*64+x],depth);depths+=1
    if s is not None:assert s[256+y*256+x]==(7 if covered else 0),(t,x,y,s[256+y*256+x]);stencils+=1
 assert d['runs'][-1]['classes_restored_before_commit']
 if icb:assert d['rejections']==[{'case':'pipeline_attachment_mismatch','rejected':True}]
 else:assert d['rejections']==[]
 return {'status':'PASS','mode':d['mode'],'command_buffers':15 if execute else 0,'correct_float32_channels':channels,'exact_depth_values':depths,'exact_stencil_values':stencils,'maximum_error':maximum,'copied_ICB_draw_records':records,'depth_stencil_ICB_qualified':icb and execute,'native_depth_stencil_reference_qualified':not icb and execute,'scope_restored':True,'all_children_terminal':True,'GPU_resident_ICB':False,'performance_benchmark':False,'source_sha256':inp['source_hashes'],'raw_sha256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ('source_sha256','raw_sha256')},indent=2))
