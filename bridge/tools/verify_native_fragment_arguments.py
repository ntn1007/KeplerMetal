#!/usr/bin/env python3
"""Independent native-only fragment argument-buffer baseline image oracle."""
from pathlib import Path
import argparse,hashlib,json,math,struct
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 d=json.loads((root/'capture.json').read_text());inp=json.loads((root/'inputs.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];assert d['committed'] and d['GPU_user_submissions']==3 and not d['native_memory_modified'] and not d['system_modified']
 assert sha(root/'fragment_resources.metallib')==inp['library_SHA256']==d['library_SHA256']=='45c98ce0a295f0cde1a2396c90e60f6a4e2154f2cccf2f30191e65b124c48bbf'
 if not portable:assert sha(root/'native_fragment_arguments_capture')==m['original_binary_sha256'] and sha(root/'execution/native_fragment_arguments_capture')==m['signed_binary_sha256']
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current:assert sha(Path(__file__).resolve().parents[1]/('src' if n.endswith('.metal') else 'tools')/n)==h
 maximum=0;channels=0;rawhash={}
 for row in d['rows']:
  name=row['name'];p=root/'outputs'/(name+'.image.bin');raw=p.read_bytes();rawhash[p.name]=sha(p);p=root/'outputs'/(name+'.texture-input.bin');src=struct.unpack('<12288f',p.read_bytes());rawhash[p.name]=sha(p);assert raw[:256]==b'\xa5'*256 and raw[-256:]==b'\xa5'*256;actual=struct.unpack_from('<12288f',raw,256);assert row['command_status']==4 and row['encoded_length']==24 and row['encoded_alignment']==8 and row['vertex_argument_count']==0
  for y in range(48):
   for x in range(64):
    for k in range(4):
     if name=='fs_arg_linear':
      x1=min(x+1,63);y1=min(y+1,47);expected=src[(y*64+x)*4+k]*.75*.875+src[(y*64+x1)*4+k]*.25*.875+src[(y1*64+x)*4+k]*.75*.125+src[(y1*64+x1)*4+k]*.25*.125
     else:expected=src[(y*64+x)*4+k]
     v=actual[(y*64+x)*4+k];error=abs(v-expected);maximum=max(maximum,error);assert math.isfinite(v) and error<=2e-6;channels+=1
 return {'status':'PASS','correct_float32_channels':channels,'maximum_error':maximum,'library_SHA256':d['library_SHA256'],'GPU_command_buffers':3,'fresh_GPU_execution':False,'archived_GPU_execution_checked':True,'host_executables_re_attested':not portable,'system_modified':False,'raw_sha256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k!='raw_sha256'},indent=2))
