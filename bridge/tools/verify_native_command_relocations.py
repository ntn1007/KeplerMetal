#!/usr/bin/env python3
"""Validate native packet framing, QMD geometry, offset changes and restoration."""
from pathlib import Path
import argparse,hashlib,json,struct
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve();capture=json.loads((root/'capture.json').read_text());decoded=json.loads((root/'decoded-packets.json').read_text());rows=[]
assert not capture['GPU_dispatch'] and not capture['committed'] and not capture['ICB_created']
for record,pack in zip(capture['records'],decoded['records']):
 raw=Path(record['file']).read_bytes();assert len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==record['SHA256'];assert record['range_comparable'] and record['saved']
 assert sum(p['bytes'] for p in pack['packets'])==len(raw)
 qmd=[]
 for upload in pack['uploads']:
  if upload['data_bytes']!=256:continue
  data=Path(upload['payload_file']).read_bytes();get=lambda o:struct.unpack_from('<I',data,o)[0]
  qmd.append({'destination':upload['destination_GPU_address'],'program':get(0x20),'grid':[get(0x30)&0x7fffffff,get(0x34)&65535,get(0x34)>>16],
              'local':[get(0x48)>>16,get(0x4c)&65535,get(0x4c)>>16],'GPR':(get(0xb8)>>24)&63})
 changed=record['step']==1;local=33 if changed else 32
 if record['mode']=='direct':assert len(qmd)==1 and qmd[0]['grid']==[5 if changed else 3,1,1] and qmd[0]['local']==[local,1,1]
 else:
  assert len(qmd)==2 and qmd[0]['local']==qmd[0]['grid']==[1,1,1] and qmd[1]['local']==[local,1,1] and qmd[1]['grid']==[0,0,0]
  address=capture['args_GPU_address']+(128 if changed else 64);words=struct.unpack('<'+str(len(raw)//4)+'I',raw);pairs=[i*4 for i in range(len(words)-1) if (words[i],words[i+1])==((address&0xffffffff),address>>32)]
  assert pairs==[476],pairs
 rows.append({'mode':record['mode'],'step':record['step'],'bytes':len(raw),'SHA256':record['SHA256'],'descriptors':qmd,'changed_offset_verified':record['mode']=='indirect' and changed})
for mode in ['direct','indirect']:
 selected=[r for r in rows if r['mode']==mode];assert selected[0]['SHA256']==selected[2]['SHA256']!=selected[1]['SHA256']
process=json.loads((root/'execution/manifest.json').read_text());assert not process['SIGKILL_requested'] and not process['authoritative_ps_status']
summary={'status':'PASS','captures':len(rows),'restoration_byte_exact':True,'argument_pointer_relocation_verified':True,
 'native_context_writes':False,'GPU_dispatch':False,'ICB_replay_verified':False,'records':rows,
 'scope':'Own-process public encoding only; resource offset/local dimensions alter emitted templates, restoration gives identical bytes. ABI/residency/lifetime for replay remains unqualified.'}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
