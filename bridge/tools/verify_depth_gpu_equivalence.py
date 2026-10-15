#!/usr/bin/env python3
"""Cross-check archived native/ICB outputs and separately captured draw bytes."""
from pathlib import Path
import argparse,base64,hashlib,json,struct
from verify_cpu_icb_combined import packet
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(icb,native):
 a=json.loads((icb/'results.json').read_text());b=json.loads((native/'results.json').read_text());assert a['ICB'] and not b['ICB'] and a['mode'].endswith('execute') and b['mode'].endswith('execute');matches=[];writers=indices=0
 for t,r in enumerate(a['runs']):
  for n in ['image','depth','stencil']:
   name=f'trial-{t}.{n}.bin';p=icb/'outputs'/name;q=native/'outputs'/name;assert p.read_bytes()==q.read_bytes(),name;matches.append({'file':name,'SHA256':sha(p)})
  row=r['writer_event']['evidence']['sequence_records'][0];raw=(icb/'outputs'/f'trial-{t}.writer.commands.bin').read_bytes();prefix=(icb/'outputs'/f'trial-{t}.writer.prefix.bin').read_bytes();assert raw==struct.pack('<6I',0xa0050e0c,4,3,1,0,0)==base64.b64decode(row['commands_base64']) and prefix==base64.b64decode(row['prefix_base64']) and hashlib.sha256(prefix).hexdigest()==row['prefix_SHA256'];writers+=1
  for j,row in enumerate(r['execution_event'].get('evidence',{}).get('sequence_records',[])):
   raw=(icb/'outputs'/f'trial-{t}.record-{j}.commands.bin').read_bytes();prefix=(icb/'outputs'/f'trial-{t}.record-{j}.prefix.bin').read_bytes();assert raw==packet(row['record'],6)==base64.b64decode(row['commands_base64']) and prefix==base64.b64decode(row['prefix_base64']);indices+=1
 assert len(matches)==27 and writers==9 and indices==8;return {'status':'PASS','native_ICB_files_byte_identical':27,'separately_recaptured_stencil_writer_records':9,'separately_recaptured_indexed_records':8,'fresh_GPU_execution':False,'matches':matches}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('icb',type=Path);p.add_argument('native',type=Path);p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.icb.resolve(),a.native.resolve())
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k!='matches'},indent=2))
