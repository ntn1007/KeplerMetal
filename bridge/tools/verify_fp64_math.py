#!/usr/bin/env python3
"""Strict binary64 CPU oracle; exact finite bits/signs, quiet NaN classification.

FMA finite results use exact rational arithmetic with a single binary64 rounding.
No CPU-computed answer is uploaded to the GPU.
"""
from pathlib import Path
from fractions import Fraction
import argparse,hashlib,json,math,struct
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bits(x):return struct.unpack('<Q',struct.pack('<d',x))[0]
def value(x):return struct.unpack('<d',struct.pack('<Q',x))[0]
def sign(x):return bool(bits(x)>>63)
def expected(op,a,b,c):
 if op=='add':return a+b
 if op=='mul':return a*b
 if op=='div':
  if math.isnan(a) or math.isnan(b):return math.nan
  if b==0:return math.nan if a==0 else math.copysign(math.inf,-1 if sign(a)^sign(b) else 1)
  return a/b
 if op=='sqrt':
  try:return math.sqrt(a)
  except ValueError:return math.nan
 if any(math.isnan(v) for v in [a,b,c]):return math.nan
 if (a==0 and math.isinf(b)) or (b==0 and math.isinf(a)):return math.nan
 if math.isinf(a) or math.isinf(b):
  p=math.copysign(math.inf,-1 if sign(a)^sign(b) else 1)
  return math.nan if math.isinf(c) and sign(c)!=sign(p) else p
 if math.isinf(c):return c
 exact=Fraction.from_float(a)*Fraction.from_float(b)+Fraction.from_float(c)
 if exact==0:return -0.0 if (a==0 or b==0) and sign(a)^sign(b) and c==0 and sign(c) else 0.0
 try:return float(exact)
 except OverflowError:return math.copysign(math.inf,1 if exact>0 else -1)
def equivalent(observed,reference):
 if math.isnan(reference):return math.isnan(value(observed)) and bool(observed&(1<<51))
 return observed==bits(reference)
def verify(root,portable=False):
 plan=json.loads((root/'plan.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode'];prepare=mode=='prepare';native=mode=='native';info=plan['shader_info']
 assert d['registry_id']==4294968458 and d['constructor_restored'] and not d['system_modified'] and not d['performance_benchmark'] and not d['CPU_computed_expected_outputs']
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 inp=json.loads((root/'inputs.json').read_text())
 for n,h in inp['source_SHA256'].items():assert sha(root/n)==h
 assert sha(root/'program.sass')==plan['code_SHA256'] and sha(root/'carrier.metallib')==plan['carrier_SHA256']
 if not portable:assert sha(root/'fp64_math_probe')==m['original_binary_sha256'] and sha(root/'execution/fp64_math_probe')==m['signed_binary_sha256']
 assert d['operation']==info['operation'] and d['local']==info['local'] and len(d['runs'])==len(plan['fixtures'])==3
 if not native:
  p=d['import'];assert p['contract_verified'] and p['target_imports']==p['verified_imports'] and p['verified_imports']>0 and not p['rejected_import']
  for e in p['events']:assert e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields'] and e['decoded_code_bytes']==info['code_bytes'] and e['decoded_registers']==info['registers'] and e['code_input_unchanged_after_constructor']
 mismatches=tags=guards=correct=tagged=0;errors=[];hashes={}
 for f,r in zip(plan['fixtures'],d['runs']):
  n=f['count'];nonce=f['nonce'];assert r['trial']==f['trial'] and r['count']==n and r['nonce']==nonce and r['committed']==(not prepare) and r['command_status']==(0 if prepare else 4) and r['upload_status']==r['readback_status']==4
  inputs=[]
  for name in ['A','B','C']:
   raw=(root/'outputs'/r['files'][name]).read_bytes();source=(root/f"trial-{f['trial']}-{name}.input.bin").read_bytes();assert sha(root/f"trial-{f['trial']}-{name}.input.bin")==f[name+'_SHA256']
   assert raw==b'\xa5'*64+source+b'\xa5'*64;inputs.append(struct.unpack('<'+'d'*n,source));guards+=128;hashes[r['files'][name]]=hashlib.sha256(raw).hexdigest()
  raw=(root/'outputs'/r['files']['output']).read_bytes();assert len(raw)==(n+64)*16+128
  badGuards=sum(b!=0xa5 for b in raw[:64]+raw[64+n*16:]);guards+=1152
  assert badGuards==0,'Memory guard violation: stop further GPU launches'
  hashes[r['files']['output']]=hashlib.sha256(raw).hexdigest()
  if prepare:assert raw==b'\xa5'*len(raw);continue
  for i in range(n):
   ob,index,stamp=struct.unpack_from('<QII',raw,64+i*16);reference=expected(info['operation'],inputs[0][i],inputs[1][i],inputs[2][i]);good=equivalent(ob,reference);tag=index==i and stamp==nonce
   correct+=good;tagged+=tag;mismatches+=not good;tags+=not tag
   if not good and len(errors)<32:errors.append({'trial':f['trial'],'index':i,'input_bits':[f'{bits(v[i]):016x}' for v in inputs],'observed_bits':f'{ob:016x}','expected_bits':f'{bits(reference):016x}','expected_NaN':math.isnan(reference)})
 total=sum(f['count'] for f in plan['fixtures']);status='PASS' if prepare or (mismatches==0 and tags==0) else 'FAIL'
 if native:assert mismatches>0 and tags>0;status='PASS_EXPECTED_DIFFERENCE'
 return {'status':status,'mode':mode,'operation':info['operation'],'local':info['local'],'main_command_buffers':0 if prepare else 3,'double_results_checked':0 if prepare else total,'correct_double_results':correct,'numeric_mismatches':mismatches,'tag_mismatches':tags,'GPU_invocations_with_correct_tags':tagged,'guard_bytes_verified':guards,'raw_files_SHA256':hashes,'errors':errors,'NaN_policy':'Quiet NaN required, payload/sign not standardized','finite_and_signed_zero_policy':'Exact IEEE binary64 bits; no ULP tolerance','constructor_restored':True,'integration_level':1,'performance_benchmark':False,'general_IEEE_conformance':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k not in ['raw_files_SHA256','errors']},indent=2))
 raise SystemExit(0 if v['status'].startswith('PASS') else 1)
