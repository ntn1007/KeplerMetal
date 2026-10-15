#!/usr/bin/env python3
"""Freeze decoded reverse conversions and input-only fixtures."""
from pathlib import Path
import argparse,hashlib,json
from fp64_reverse_inputs import OPS,columns,packed
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--compiled',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();compiled=a.compiled.resolve();out=a.out.resolve();compiled.relative_to(ROOT/'results');out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
s=json.loads((compiled/'summary.json').read_text());assert len(s['records'])==36 and not s['GPU_execution'];assert {(r['operation'],r['local']) for r in s['records']}=={(op,local) for op in OPS for local in [32,128,1024]}
carrier=out/'kepler_carrier.metallib';carrier.write_bytes((ROOT/'build/kepler_carrier.metallib').read_bytes());plans=[]
for r in s['records']:
 op,local=r['operation'],r['local'];label=f'{op}-l{local}';assert r['compiled'] and r['known_decode'] and not r['info']['strided_inputs'];decoded=(compiled/(label+'-decode.stdout')).read_text();mode=op[-2:];target=op.split('_')[1];pattern='cvt '+mode+('i ' if target!='f32' else ' ')+('s64' if target=='i64' else target);instructions=[line for line in decoded.splitlines() if pattern in line and 'f64' in line];assert instructions,(op,pattern)
 code=out/(label+'.sass');code.write_bytes((compiled/(label+'.sass')).read_bytes());assert sha(code)==r['code_SHA256'];count={32:33,128:1041,1024:8193}[local];fixtures=[]
 for trial in range(3):
  f={'trial':trial,'count':count,'nonce':0x93d50017^(local*37+trial*101)}
  for name,values in zip(['A','B','C'],columns(op,local,count,trial)):
   path=out/f'{label}-t{trial}-{name}.bin';path.write_bytes(packed(values));f[name]=str(path);f[name+'_SHA256']=sha(path)
  fixtures.append(f)
 plan={'shader_info':r['info'],'code':str(code),'code_SHA256':sha(code),'carrier':str(carrier),'carrier_SHA256':sha(carrier),'fixtures':fixtures,'recipe':'fp64-reverse-v1','conversion_instructions':instructions};path=out/(label+'.plan.json');path.write_text(json.dumps(plan,indent=2)+'\n');plans.append(str(path))
(out/'summary.json').write_text(json.dumps({'plans':plans,'GPU_execution':False,'compiler':s,'recipe_SHA256':sha(ROOT/'tools/fp64_reverse_inputs.py')},indent=2)+'\n');print(json.dumps({'plans':len(plans),'GPU_execution':False}))
