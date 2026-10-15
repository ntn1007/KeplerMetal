#!/usr/bin/env python3
"""Recheck the zero/one-CTA resident-QMD boundary without GPU execution."""
from pathlib import Path
import argparse,json,struct
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();root=a.directory.resolve();d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text());grid=inp['QMD_grid_override'];assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status'];assert grid in [-1,0,1]
if grid==-1:
 from verify_gpu_command_bindings import verify
 result=verify(root);result={k:v for k,v in result.items()if k not in ['raw_SHA256','selected_commands']}
else:
 mask=0xffffffff;words=invocations=guards=0
 for t,r in enumerate(d['runs']):
  assert r['command_status']==4 and r['QMD_grid_override']==grid
  bank,total,tag,nonce=struct.unpack_from('<4I',(root/'outputs'/r['choice_file']).read_bytes(),64);assert tag==0x4b504743 and bank==total%3
  resource=total//34%3;spec=r['node_specs'][bank];local=spec['local'];seed=spec['seed'];sw=spec['static_bytes']//4;dw=spec['dynamic_bytes']//4
  for k,(name,cn)in enumerate(zip(r['outputs'],r['counter_files'])):
   out=bytearray(b'\xa5'*(8192*16+512));counter=bytearray(b'\xa5'*208);co=128 if k<d['slots']else 128+4*(k-d['slots']);n=local if grid==1 and k==d['slots']+resource else 0;struct.pack_into('<I',counter,co,n)
   for i in range(n):
    fixed=lambda j:(seed*1664525^j*2246822519^0x73193211)&mask;dynamic=lambda j:(seed*22695477^j*2891336453^0x11998877)&mask
    v=(sum(dynamic(j)for j in range(i,dw,local))&mask,sum(fixed(j)for j in range(i,sw,local))&mask,i,fixed((i+1)%sw)^dynamic((i*3+7)%dw));struct.pack_into('<4I',out,128+32*resource+i*16,*v)
   assert (root/'outputs'/name).read_bytes()==out and (root/'outputs'/cn).read_bytes()==counter
   invocations+=n;words+=n*4;guards+=len(out)-n*16+len(counter)-4
  for name in r['QMD_files']:
   raw=(root/'outputs'/name).read_bytes();assert len(raw)==256 and struct.unpack_from('<I',raw,48)==(grid,) and struct.unpack_from('<I',raw,52)==(0x10001,) and struct.unpack_from('<I',raw,184)[0]>>24==12
 result={'status':'PASS','runs':3,'grid':grid,'exact_uint32_words':words,'GPU_consumer_invocations':invocations,'unchanged_and_guard_bytes':guards,'GPU_execution_by_verifier':False}
(root/'reverification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
