#!/usr/bin/env python3
"""Independent uint32 local-array/live-value oracle, full input and byte guards."""
from pathlib import Path
import argparse,hashlib,json,struct
MASK=(1<<32)-1
def rol5(x):return ((x<<5)|(x>>27))&MASK
def result(name,gid,seed):
 base=gid*129;value=lambda i:(((base+i)*1664525+1013904223)&MASK)^seed
 if name.startswith('pressure'):
  words=int(name[8:]);key=value(128)^seed;checksum=key^gid
  for i in range(words):checksum=(rol5(checksum^value(i))+(key^((i*2891336453)&MASK)))&MASK
  return checksum,key,words,0xcafe0000^gid
 state=value(0)^seed^((gid*747796405)&MASK)
 if name=='local_control':return rol5(state),state,0,0xcafe0000^gid
 words=int(name[5:]);scratch=[(((state+i*2891336453)&MASK)^((i*22695477+0x11998877)&MASK))for i in range(words)]
 for turn in range(17):
  index=(state^(turn*97))&(words-1);other=(index+13)&(words-1);a,b=scratch[index],scratch[other]
  next_=(rol5(a^b)+(state^turn))&MASK;scratch[index]=next_;state=((next_*1664525+1013904223)&MASK)^b
 checksum=state
 for i,v in enumerate(scratch):checksum=(rol5(checksum^v)+i)&MASK
 return checksum,state,words,0xcafe0000^gid
def verify(root):
 root=Path(root);d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text())
 sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 assert d['device']=='NVIDIA GeForce GTX 880M'and d['registry_id']==4294968458 and not d['CPU_expected_answers_uploaded']and not d['system_modified']and not d['performance_benchmark']
 imported=d['mode'].startswith('nak:');mode=d['mode'][4:]if imported else d['mode'];dispatch=not mode.startswith('no_dispatch:');checked=guards=negative=0;files={}
 if imported:
  assert not d['native_reference']and d['program_replaced']and d['caller_inputs_mutated_after_import']
  proof=d['import'];assert proof['contract_verified']and not proof['rejected_import']
  for e in proof['events']:
   if not e.get('code_replaced'):continue
   assert e['imported_code_identical']and e['native_local_metadata_verified']and e.get('native_local_allocation_fields_preserved',e.get('native_allocation_metadata_preserved'))and e['decoded_local_contract_verified']
   assert e['decoded_code_bytes']==d['program_info']['code_bytes']and e['decoded_registers']==d['program_info']['registers']and e['decoded_instruction_count']==d['program_info']['code_bytes']//8-1
   assert e['required_scratch_bytes']==d['program_info']['scratch_bytes']and e['carrier_local_bytes']>=e['required_scratch_bytes']
 extended=d.get('trial_profile')=='extended';counts=[1,31,32,33,64,128,256,512,1024,99,256,2048]if extended else[32,64,256];locals_=[1,31,32,33,64,128,256,512,1024,33,64,1024]if extended else[32,32,64]
 assert len(d['runs'])==len(counts)
 for trial,r in enumerate(d['runs']):
  assert r['trial']==trial and r['threads']==counts[trial]and r['local']==locals_[trial]and r['seed']==0x13579+trial*971
  n,seed=r['threads'],r['seed'];assert r['stride']==129 and n%r['local']==0 and r['groups']*r['local']==n and r['command_status']==4 and r['kernel_dispatches']==int(dispatch)
  input_expected=bytearray(b'\xa5'*r['input_bytes']);expected=bytearray(b'\xa5'*r['output_bytes']);assert len(input_expected)==256+n*129*4 and len(expected)==256+n*16
  for i in range(n*129):struct.pack_into('<I',input_expected,128+4*i,((i*1664525+1013904223)&MASK)^seed)
  if dispatch:
   for gid in range(n):struct.pack_into('<4I',expected,128+gid*16,*result(d['function'],gid,seed))
   checked+=n*4
  else:
   # The exact expected live computation must differ from the untouched canary.
   for gid in range(n):negative+=sum(v!=0xa5a5a5a5 for v in result(d['function'],gid,seed))
  for key,want in [('input_file',input_expected),('output_file',expected)]:
   path=root/'outputs'/r[key];got=path.read_bytes();assert got==want,(d['function'],r['trial'],key,next((i for i,(a,b)in enumerate(zip(got,want))if a!=b),None));files[r[key]]=sha(path)
  guards+=512
 if not dispatch:assert negative>0
 return {'status':'PASS','function':d['function'],'trials':len(d['runs']),'kernel_dispatches':len(d['runs'])if dispatch else 0,'exact_uint32_results':checked,'guard_bytes':guards,'negative_expected_words_absent':negative,'files_SHA256':files,'performance_benchmark':False,'full_objective_complete':False}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args();r=verify(a.directory)
 with(a.directory/'independent-verification.json').open('x')as f:json.dump(r,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in r.items()if k!='files_SHA256'},indent=2))
