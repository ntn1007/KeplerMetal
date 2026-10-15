#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,struct
LIB='463dabbbb9538a9aef9baa6e421fe3d0d9783d3823acf12177225c3ad1c47494'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def reduction(values,seed):return sum((((v*1664525+1013904223)&0xffffffff)^seed)&255 for v in values)
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());execute=d['mode']=='execute';assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];assert d['registry_id']==4294968458 and not d['system_modified'] and not d['native_command_memory_modified'] and sha(root/'gpu_argument_selector.metallib')==inp['library_SHA256']==d['library_SHA256']==LIB
 if not portable:assert sha(root/'native_gpu_argument_choice_probe')==m['original_binary_sha256'] and sha(root/'execution/native_gpu_argument_choice_probe')==m['signed_binary_sha256']
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current:assert sha(Path(__file__).resolve().parents[1]/('src' if n.endswith('.metal') else 'tools')/n)==h
 assert len(d['runs'])==4;writes=threads=words=0;rawhash={}
 def load(n):p=root/'outputs'/n;rawhash[n]=sha(p);return p.read_bytes()
 for t,r in enumerate(d['runs']):
  assert r['trial']==t and r['committed']==execute and r['command_status']==(4 if execute else 0) and r['producer']==(t!=1) and r['selector']==(t!=3) and not r['CPU_read_of_Private_choice'] and r['same_command_buffer'];names=['values','choice','producer-counter','indices','banks','table','selector-counter'];inputs={n:load(f'trial-{t}.{n}.input.bin') for n in names};expected={n:bytearray(b) for n,b in inputs.items()};values=[17*i+t*3+(t&1 if i==31 else 0) for i in range(32)];assert struct.unpack_from('<32I',inputs['values'],64)==tuple(values);bias=7 if t>=2 else 0;config=load(f'trial-{t}.producer-config.bin');assert struct.unpack_from('<4I',config,256)==(0x9e3779b9,bias,0,0)
  for n,size,offset,span in [('values',256,64,128),('choice',128,64,16),('producer-counter',132,64,4),('indices',128,64,24),('table',1024,256,24),('selector-counter',132,64,4)]:assert len(inputs[n])==size and inputs[n][:offset]==b'\xa5'*offset and inputs[n][offset+span:]==b'\xa5'*(size-offset-span)
  assert struct.unpack_from('<6I',inputs['indices'],64)==(bias,)*6
  assert inputs['banks'][:256]==b'\xa5'*256 and inputs['banks'][280:512]==b'\xa5'*232 and inputs['banks'][536:]==b'\xa5'*488
  assert struct.unpack_from('<4I',inputs['choice'],64)==(0,0,0,0) and struct.unpack_from('<I',inputs['producer-counter'],64)[0]==0 and struct.unpack_from('<I',inputs['selector-counter'],64)[0]==0
  for b in range(2):assert struct.unpack_from('<6I',inputs['banks'],256+b*256)==tuple(0x11223300+b*4096+i for i in range(6))
  total=reduction(values,0x9e3779b9);bank=total&1 if r['producer'] else 0
  if execute and r['producer']:struct.pack_into('<4I',expected['choice'],64,bank,total,0x4b504742,0x9e3779b9);struct.pack_into('<I',expected['producer-counter'],64,32);struct.pack_into('<6I',expected['indices'],64,*range(bias,bias+6));threads+=32
  if execute and r['selector']:expected['table'][256:280]=inputs['banks'][256+bank*256:280+bank*256];struct.pack_into('<I',expected['selector-counter'],64,6);writes+=6
  for n in names:
   after=load(f'trial-{t}.{n}.after.bin');assert after==(expected[n] if execute else b'\xa5'*len(expected[n])),(t,n);words+=len(after)//4 if execute else 0
 return {'status':'PASS','mode':d['mode'],'command_buffers':4 if execute else 0,'exact_UInt32_words':words,'counted_producer_threads':threads,'counted_selector_word_writes':writes,'GPU_computed_choice_and_generated_indices_qualified':execute,'producer_omission_control':execute,'selector_omission_control':execute,'CPU_read_of_Private_choice':False,'system_modified':False,'all_children_terminal':True,'raw_sha256':rawhash,'source_sha256':inp['source_hashes']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ('raw_sha256','source_sha256')},indent=2))
