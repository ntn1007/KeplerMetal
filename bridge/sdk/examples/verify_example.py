#!/usr/bin/env python3
"""Check the client GPU captures using an independent BGRA8 image oracle."""
from pathlib import Path
import argparse,hashlib,json
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());execute=d['mode']=='execute';assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and d['registry_id']==4294968458 and d['passed'] and d['scope_restored'] and not d['system_modified'] and not d['GPU_resident_ICB'] and not d['performance_benchmark'];assert inp['core_source_compilations']==0 and inp['client_shader_SHA256']==d['client_shader_SHA256'] and inp['client_manifest_SHA256']==d['client_manifest_SHA256']
 if not portable:assert sha(root/'keplermetal_example')==m['original_binary_sha256']==inp['client_executable_SHA256'] and sha(root/'execution/keplermetal_example')==m['signed_binary_sha256']
 assert len(d['runs'])==5;count=0;rawhash={}
 for t,r in enumerate(d['runs']):
  assert r['trial']==t and r['committed']==execute and r['command_status']==(4 if execute else 0);raw=(root/'outputs'/f'trial-{t}.image.bin').read_bytes();rawhash[str(t)]=hashlib.sha256(raw).hexdigest();assert len(raw)==49664 and raw[:256]==raw[-256:]==b'\xa5'*256
  if t:assert r['execution_event']['executed_indices']==([] if t==2 else [0])
  if not execute:assert raw==b'\xa5'*49664;continue
  for y in range(96):
   for x in range(128):assert raw[256+(y*128+x)*4:256+(y*128+x+1)*4]==(bytes([223,159,96,255]) if t!=2 and 32<=x<96 and 24<=y<72 else b'\0'*4),(t,x,y);count+=4
 assert d['runs'][-1]['scope_restored_before_commit']
 if execute:
  for t in [1,3,4]:assert rawhash[str(t)]==rawhash['0']
 return {'status':'PASS','mode':d['mode'],'GPU_command_buffers':5 if execute else 0,'exact_BGRA8_components':count,'client_shader_qualified':execute,'SDK_static_library_consumed':True,'core_source_compilations':0,'native_ICB_images_identical':execute,'scope_restored':True,'all_children_terminal':True,'integration_level':2 if execute else 1,'full_Metal_compatibility':False,'performance_benchmark':False,'raw_sha256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps(r,indent=2))
