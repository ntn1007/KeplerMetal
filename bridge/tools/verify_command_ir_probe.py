#!/usr/bin/env python3
"""Independent byte-level CPU oracle for GPU-produced portable commands."""
from pathlib import Path
import argparse,json,struct
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();root=a.directory.resolve();d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text())
assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
assert d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id']==4294968458
assert d['performance_benchmark'] is False and d['GPU_command_execution'] is False
assert len(d['runs'])==36
if d['mode']!='carrier':
 proof=d['import'];assert proof['contract_verified'] and not proof['rejected_import']
 assert proof['target_imports']==proof['verified_imports'] and proof['target_imports']>0
 for e in proof['events']:
  if e.get('code_replaced'):assert e['imported_code_identical'] and e['code_input_unchanged_after_constructor'] and e['decoded_code_bytes']==d['compiled_info']['code_bytes'] and e['decoded_registers']==d['compiled_info']['registers']
bad=guards=checked=0
for run in d['runs']:
 assert run['command']['status']==4 and not run['command']['error']
 raw=(root/'outputs'/run['output_file']).read_bytes();assert len(raw)==1152
 expected=bytearray(b'\xa5'*1152)
 if d['mode']=='carrier':
  for i in range(32):struct.pack_into('<4I',expected,64+i*16,32^0x7a11beef,0,0xdeadbeef,i)
 elif d['mode']=='producer':
  valid=(run['context_magic']==0x4b504343 and run['context_version']==1 and run['capacity']<=8 and run['record_bytes']==128)
  if valid:
   for i in range(run['capacity']):
    semantic=d.get('semantic','basic')
    if semantic=='copy' and i>1:continue
    at=64+i*128;expected[at:at+128]=b'\0'*128
    if semantic=='copy' and i==0:struct.pack_into('<I',expected,at,0x4b504952);continue
    flags=2|4;error=0;token=run['pipeline_token'];pipeline=0
    if token>>32==0x4b504950 and (token&0xffffffff)<run['pipeline_count']<=8:pipeline=token;flags|=1
    else:flags|=0x80000000;error=1
    for slot,address in enumerate(run['resource_addresses']):
     if slot<run['max_bindings']:struct.pack_into('<Q',expected,at+48+slot*8,address);flags|=16<<slot
     else:flags|=0x80000000;error=2
    struct.pack_into('<IIQ',expected,at,0x4b504952,flags,pipeline)
    struct.pack_into('<3I',expected,at+16,1,1,1);struct.pack_into('<3I',expected,at+32,32,1,1)
    struct.pack_into('<II',expected,at+72,48640,error)
    if semantic!='basic':
     flags|=128
     if semantic!='clear':flags|=8
     struct.pack_into('<I',expected,at+4,flags)
     struct.pack_into('<6I',expected,at+80,3,2,1,17,4,2)
    if semantic=='threads':struct.pack_into('<4I',expected,at+16,97,2,1,1)
 for i,(actual,wanted)in enumerate(zip(raw,expected)):
  if i<64 or i>=1088:guards+=actual!=wanted
  else:bad+=actual!=wanted
 checked+=len(raw)//4
assert bad==guards==0,(bad,guards)
receipt={'status':'PASS','mode':d['mode'],'semantic':d.get('semantic','basic'),'runs':len(d['runs']),'checked_uint32_words':checked,'mismatch_bytes':bad,'guard_mismatch_bytes':guards,'GPU_command_execution':False,'scope':'Portable IR records, not execution of the commands described in them'}
(root/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
