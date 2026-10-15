#!/usr/bin/env python3
"""Create reproducible raw IEEE binary64 inputs, including fused-only examples."""
from pathlib import Path
import argparse,hashlib,json,struct
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--compiled',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();compiled=a.compiled.resolve();compiled.relative_to(ROOT/'results');out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bits(x):return struct.unpack('<Q',struct.pack('<d',x))[0]
P=0x7ff0000000000000;N=P|1<<63;QN=0x7ff8000000000042;MN=0x0010000000000000;MX=0x7fefffffffffffff
triples=[(bits(1+2**-27),bits(1-2**-27),bits(-1.0)),(0, bits(1.),0),(1<<63,bits(1.),1<<63),(MN,bits(.5),0),(1,bits(1.),0),(0xfffffffffffff,bits(1.),0),(MX,bits(2.),bits(-1.)),(bits(-2.),bits(3.),bits(.5)),(P,bits(1.),0),(N,bits(1.),0),(P,0,0),(P,N,0),(QN,bits(1.),0),(bits(1.),QN,0),(bits(1.),0,0),(bits(-1.),0,0),(0,0,0),(bits(4.),bits(2.),bits(-2.)),(bits(2.),bits(3.),bits(.25)),(bits(1.),bits(3.),bits(.25)),(bits(1+2**-52),bits(1+2**-52),bits(-1.)),(bits(2**-500),bits(2**500),bits(-1.)),(bits(2**500),bits(2**-500),bits(-1.)),(bits(2**-1022),bits(2**-52),0),(0x8000000000000001,bits(1.),0),(bits(-4.),bits(-2.),bits(0.)),(bits(.5),bits(.25),bits(-.125)),(bits(3.),bits(7.),bits(-21.)),(bits(1e300),bits(1e-300),bits(-1.)),(bits(1e-300),bits(1e300),bits(-1.)),(bits(0.),P,bits(1.)),(bits(-0.),P,bits(-1.))]
datasets={}
for local,count in [(32,33),(128,1041),(1024,8193)]:
 fixtures=[]
 for trial in range(3):
  state=0x880520261014+97*local+104729*trial;columns=[[],[],[]]
  for i in range(count):
   if i<len(triples):values=triples[(i+trial*7)%len(triples)]
   else:
    values=[]
    for _ in range(3):
     state=(state*6364136223846793005+1442695040888963407)&0xffffffffffffffff
     exponent=1+((state>>52)%2046);values.append((state&(1<<63|((1<<52)-1)))|(exponent<<52))
   for k,v in enumerate(values):columns[k].append(v)
  f={'trial':trial,'count':count,'nonce':0xa7310017^(local*37+trial*101)}
  for name,values in zip(['A','B','C'],columns):
   path=out/f'l{local}-t{trial}-{name}.bin';path.write_bytes(struct.pack('<'+'Q'*count,*values));f[name]=str(path);f[name+'_SHA256']=sha(path)
  fixtures.append(f)
 datasets[local]=fixtures
carrier=out/'kepler_carrier.metallib';carrier.write_bytes((ROOT/'build/kepler_carrier.metallib').read_bytes())
plans=[]
for r in json.loads((compiled/'summary.json').read_text())['records']:
 assert r['compiled'] and r['known_decode'];name=f"{r['operation']}-l{r['local']}";code=out/(name+'.sass');code.write_bytes((compiled/(name+'.sass')).read_bytes());assert sha(code)==r['code_SHA256']
 plan={'shader_info':r['info'],'code':str(code),'code_SHA256':sha(code),'carrier':str(carrier),'carrier_SHA256':sha(carrier),'fixtures':datasets[r['local']]};path=out/(name+'.plan.json');path.write_text(json.dumps(plan,indent=2)+'\n');plans.append(str(path))
(out/'summary.json').write_text(json.dumps({'plans':plans,'input_recipe':'32 IEEE edge/fused cases, rotating across three trials; finite random sign/mantissa/exponent 1..2046','GPU_execution':False},indent=2)+'\n');print(json.dumps({'plans':len(plans),'GPU_execution':False}))
