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
def verify_memory_ledger(d, required=False):
 """Cross-check requests independently; API counters need not be monotonic.

 Historical records without any ledger remain readable. New builds require the
 complete schema. None (unsupported API) must never be interpreted as zero.
 """
 if 'memory_ledger' not in d:
  assert not required and all('memory_ledger' not in r for r in d['runs'])
  return {'status':'NOT_RECORDED'}
 m=d['memory_ledger'];assert type(m['schema']) is int and m['schema']==1
 assert m['buffer_request_cap_bytes']==8*1024**2 and m['logical_local_cap_bytes']==64*1024**2
 for flag in ['physical_VRAM_measured','scratch_occupancy_measured','maximum_pressure_measured']:assert m[flag] is False
 def counter(value):
  assert value is None or type(value) is int and 0<=value<2**64
  return value
 counter(m['allocated_before_trials']);counter(m['allocated_after_trials'])
 imported=d['mode'].startswith('nak:');mode=d['mode'][4:] if imported else d['mode'];dispatch=not mode.startswith('no_dispatch:')
 name=d['function'];arrays={'local_control':0,'local32':128,'local256':1024,'local1024':4096,'local2048':8192,'local4096':16384,'pressure32':0,'pressure64':0,'pressure96':0};frame=arrays[name]
 carrier=224 if name.startswith('pressure') else frame
 deltas=[];samples=missing=0;private_max=shared_max=array_max=carrier_max=0
 for r in d['runs']:
  row=r['memory_ledger'];n=r['threads'];private=r['input_bytes']+r['output_bytes'];shared=private+16
  expected={'requested_private_bytes':private,'requested_shared_bytes':shared,'source_array_bytes_per_thread':frame,'logical_array_bytes':n*frame if dispatch else 0,
   'imported_carrier_bytes_per_thread':carrier if imported else None,
   'required_scratch_bytes_per_thread':d['program_info']['scratch_bytes'] if imported else None,
   'logical_carrier_bytes':n*carrier if imported and dispatch else (0 if imported else None)}
  for key,value in expected.items():
   assert row[key]==value and (row[key] is None or type(row[key]) is int),key
  assert private<=m['buffer_request_cap_bytes'] and shared<=m['buffer_request_cap_bytes']
  assert row['logical_array_bytes']<=m['logical_local_cap_bytes']
  if imported:
   assert 0<=row['required_scratch_bytes_per_thread']<=carrier and row['logical_carrier_bytes']<=m['logical_local_cap_bytes']
  for key in ['allocated_before_buffers','allocated_after_buffers','allocated_after_completion','allocated_after_release']:
   value=counter(row[key]);samples+=value is not None;missing+=value is None
  before,after=row['allocated_before_buffers'],row['allocated_after_completion']
  if before is not None and after is not None:deltas.append(after-before)
  private_max=max(private_max,private);shared_max=max(shared_max,shared);array_max=max(array_max,row['logical_array_bytes']);carrier_max=max(carrier_max,row['logical_carrier_bytes'] or 0)
 return dict(status='PASS',trials=len(d['runs']),accounting_samples=samples,unsupported_samples=missing,
  requested_private_bytes_max=private_max,requested_shared_bytes_max=shared_max,logical_array_bytes_max=array_max,
  logical_carrier_bytes_max=carrier_max if imported else None,
  API_completion_delta_bytes_min=min(deltas) if deltas else None,API_completion_delta_bytes_max=max(deltas) if deltas else None,
  physical_VRAM_measured=False,scratch_occupancy_measured=False,maximum_pressure_measured=False)

def verify_device_identity(d):
 assert d['device']=='NVIDIA GeForce GTX 880M'
 if 'device_identity' not in d:
  assert d['registry_id']==4294968458  # historical boot; do not rewrite old evidence
  return
 i=d['device_identity']
 assert i['schema']==1 and i['name']==d['device'] and i['registry_id']==d['registry_id']
 assert type(i['registry_id']) is int and i['registry_id']>0 and type(i['PCI_registry_id']) is int and i['PCI_registry_id']>0
 assert i['PCI_vendor_id']==0x10de and i['PCI_device_id']==0x1198

def verify(root, require_memory_ledger=False):
 root=Path(root);d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text())
 sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 verify_device_identity(d)
 if require_memory_ledger:assert 'device_identity' in d
 assert not d['CPU_expected_answers_uploaded']and not d['system_modified']and not d['performance_benchmark']
 imported=d['mode'].startswith('nak:');mode=d['mode'][4:]if imported else d['mode'];dispatch=not mode.startswith('no_dispatch:');checked=guards=negative=0;files={}
 if imported:
  assert not d['native_reference']and d['program_replaced']and d['caller_inputs_mutated_after_import']
  proof=d['import'];assert proof['contract_verified']and not proof['rejected_import']
  assert proof['driver_sha256']==d['driver_SHA256']
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
 ledger=verify_memory_ledger(d,require_memory_ledger)
 report={'status':'PASS','function':d['function'],'trials':len(d['runs']),'kernel_dispatches':len(d['runs'])if dispatch else 0,'exact_uint32_results':checked,'guard_bytes':guards,'negative_expected_words_absent':negative,'files_SHA256':files,'performance_benchmark':False,'full_objective_complete':False}
 if ledger['status']!='NOT_RECORDED':report['memory_ledger']=ledger
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args();r=verify(a.directory)
 with(a.directory/'independent-verification.json').open('x')as f:json.dump(r,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in r.items()if k!='files_SHA256'},indent=2))
