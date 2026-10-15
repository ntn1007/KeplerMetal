#!/usr/bin/env python3
"""Check native M1 manifest consumers against integer CPU results, offline."""
from pathlib import Path
import argparse,hashlib,json,struct
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(root):
 root=Path(root);manifest=json.loads((root/'FILE_MANIFEST.json').read_text())
 for f in manifest['files']:assert sha(root/f['path'])==f['SHA256']
 mask=0xffffffff;words=invocations=files=0;rows=[]
 for mode in ['basic','barrier','clear','copy','reset','no_producer','split']:
  p=root/'results'/mode;d=json.loads((p/'results.json').read_text());m=json.loads((p/'execution/manifest.json').read_text())
  assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
  assert d['native_reference']and d['device']=='Apple M1 Max'and len(d['runs'])==3
  for t,r in enumerate(d['runs']):
   assert r['trial']==t and r['command_status']==4 and r['intermediate_CPU_completion_waits']==0
   bank=(t+1)%3;resource=(t+2)%3;spec=r['node_specs'][bank];groups=1+0xa5a5a5a5%spec['groups'];live=mode not in ['reset','no_producer'];slots=3+(2 if mode=='copy'else 1)
   for k,(outn,cn)in enumerate(zip(r['outputs'],r['counter_files'])):
    n=groups*spec['local']if live and k==slots+resource else 0;expected=bytearray(b'\xa5'*(8192*16+512));counter=bytearray(b'\xa5'*208);oo=128 if k<slots else 128+32*(k-slots);co=128 if k<slots else 128+4*(k-slots);struct.pack_into('<I',counter,co,n)
    for i in range(n):
     seed=spec['seed'];local=spec['local'];group,lane=divmod(i,local);dw=spec['dynamic_bytes']//4
     if spec['function']=='manifest_mix':
      x=(seed*1664525 ^ i*1013904223)&mask;v=(((x<<13)|(x>>19))&mask,i,groups|(1<<16)|(1<<24),local)
     else:
      assert spec['function']=='manifest_dynamic';v=(sum((seed*1664525 ^ group*1013904223 ^ j*2246822519)&mask for j in range(lane,dw,local))&mask,i,groups|(1<<16)|(1<<24),local)
     struct.pack_into('<4I',expected,oo+i*16,*v)
    assert(p/'outputs'/outn).read_bytes()==expected,(mode,t,k,'out')
    assert(p/'outputs'/cn).read_bytes()==counter,(mode,t,k,'counter')
    words+=n*4;invocations+=n;files+=2
  rows.append({'mode':mode,'PID':m['pid'],'runs':3})
 return {'status':'PASS','trials':21,'exact_uint32_words':words,'consumer_invocations':invocations,'raw_output_counter_files':files,'source_manifest_SHA256':sha(root/'FILE_MANIFEST.json'),'runs':rows,'performance_benchmark':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('reference',type=Path);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();d=verify(a.reference)
 with a.receipt.open('x')as f:json.dump(d,f,indent=2);f.write('\n')
 print(json.dumps(d,indent=2))
