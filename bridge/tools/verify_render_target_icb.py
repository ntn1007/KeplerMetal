#!/usr/bin/env python3
from pathlib import Path
import argparse,base64,hashlib,json,struct
from decode_native_commands import decode
LIB='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());execute=d['mode'].endswith('execute');icb=d['ICB'];assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and d['passed'] and d['scope_restored'] and d['registry_id']==4294968458 and not d['system_modified'] and not d['GPU_resident_ICB'] and not d['performance_benchmark'];assert sha(root/'render_state_carrier.metallib')==inp['library_SHA256']==d['library_SHA256']==LIB
 if not portable:assert sha(root/'render_target_icb_probe')==m['original_binary_sha256'] and sha(root/'execution/render_target_icb_probe')==m['signed_binary_sha256']
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current:assert sha(Path(__file__).resolve().parents[1]/('src' if n.startswith('Kepler') or n.endswith('.json') else 'tools')/n)==h
 assert len(d['runs'])==12;pixels=components=records=0;rawhash={}
 def load(n):p=root/'outputs'/n;rawhash[n]=sha(p);return p.read_bytes()
 for t,r in enumerate(d['runs']):
  w,h=[(64,48),(96,64),(128,96)][t//4];fmt=[70,80,115,125][t%4];bpp=8 if fmt==115 else 16 if fmt==125 else 4;row=((w*bpp+255)//256)*256;assert (r['width'],r['height'],r['color_format'],r['bytes_per_pixel'],r['bytes_per_row'])==(w,h,fmt,bpp,row) and r['trial']==t and r['committed']==execute and r['command_status']==(4 if execute else 0)
  if icb:
   e=r['execution_event'];rs=e['evidence']['sequence_records'];assert e['executed_indices']==[0] and len(rs)==1 and e['caller_pipeline_restored'];a=rs[0];raw=load(f'trial-{t}.commands.bin');prefix=load(f'trial-{t}.prefix.bin');assert raw==struct.pack('<6I',0xa0050e0c,4,3,1,0,0)==base64.b64decode(a['commands_base64']) and base64.b64decode(a['primer_draw_base64'])==struct.pack('<6I',0xa0050e0c,4,1,1,0,0) and a['native_primer_draw_removed'] and prefix==base64.b64decode(a['prefix_base64']) and hashlib.sha256(prefix).hexdigest()==a['prefix_SHA256'];ps=decode(prefix) if prefix else [];assert len(ps)==16
   for j,p in enumerate(ps):assert p['method']==hex(0xe04+j*16) and p['values']==[(w//4)|((w//4+w//2)<<16),(h//4)|((h//4+h//2)<<16)]
   records+=1
  image=load(f'trial-{t}.image.bin');assert len(image)==row*h+512 and image[:256]==image[-256:]==b'\xa5'*256
  if not execute:assert image==b'\xa5'*len(image);continue
  color=bytes([191,32,64,255]) if fmt==70 else bytes([64,32,191,255]) if fmt==80 else struct.pack('<4e',.75,.125,.25,1) if fmt==115 else struct.pack('<4f',.75,.125,.25,1);black=b'\0'*bpp
  for y in range(h):
   assert image[256+y*row+w*bpp:256+(y+1)*row]==b'\xa5'*(row-w*bpp)
   for x in range(w):assert image[256+y*row+x*bpp:256+y*row+(x+1)*bpp]==(color if w//4<=x<w//4+w//2 and h//4<=y<h//4+h//2 else black),(t,x,y);pixels+=1;components+=4
 assert d['runs'][-1]['classes_restored_before_commit']
 if icb:assert {r['case'] for r in d['rejections']}=={'format_mismatch','extent_mismatch'} and all(r['rejected'] for r in d['rejections'])
 else:assert not d['rejections']
 return {'status':'PASS','mode':d['mode'],'command_buffers':12 if execute else 0,'exact_pixels':pixels,'exact_color_components':components,'copied_records':records,'formats':[70,80,115,125],'sizes':[[64,48],[96,64],[128,96]],'render_targets_ICB_qualified':execute and icb,'native_render_targets_qualified':execute and not icb,'scope_restored':True,'all_children_terminal':True,'GPU_resident_ICB':False,'performance_benchmark':False,'source_sha256':inp['source_hashes'],'raw_sha256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ('source_sha256','raw_sha256')},indent=2))
