#!/usr/bin/env python3
"""Check copied records against a separate Mach-read command stream capture."""
from pathlib import Path
import argparse,base64,hashlib,json,struct
from decode_native_commands import decode
def verify(root):
 d=json.loads((root/'results.json').read_text());assert d['ICB'];m=json.loads((root/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];count=stencil=0;proofs=[]
 for t,r in enumerate(d['runs']):
  for j,a in enumerate(r['actions']):
   raw=(root/'outputs'/a['raw_file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==a['raw_SHA256'];ps=decode(raw) if raw else [];draws=[p for p in ps if p['method']=='0x3830'];assert [p['values'] for p in draws]==([] if t==13 else [[4,3,1,0,0]])
   for row in a['execution_event']['evidence'].get('sequence_records',[]):
    commands=base64.b64decode(row['commands_base64']);prefix=base64.b64decode(row['prefix_base64']);assert commands==struct.pack('<6I',0xa0050e0c,4,3,1,0,0);assert prefix+commands in raw,'engine record differs from independently captured real encoder stream';assert hashlib.sha256(prefix).hexdigest()==row['prefix_SHA256'] and row['native_state_prefix_preserved_bytes']==len(prefix) and row['primer_bytes']==len(prefix)+24
    refs=[p for p in (decode(prefix) if prefix else []) if p['method'] in ('0x1394','0xf54')]
    if refs:assert [p['method'] for p in refs]==['0x1394','0xf54'] and all(p['values']==[7] for p in refs);stencil+=1
    count+=1;proofs.append({'trial':t,'action':j,'record_in_independent_stream':True,'raw_SHA256':a['raw_SHA256'],'prefix_bytes':len(prefix)})
 assert count==20 and stencil==3;return {'status':'PASS','records_in_independently_read_native_stream':count,'native_stencil_reference_prefixes_preserved':stencil,'scope':'CPU verification of archived independent Mach captures; does not rerun GPU','proofs':proofs}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve())
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k!='proofs'},indent=2))
