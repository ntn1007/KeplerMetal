#!/usr/bin/env python3
"""Require a stale CB1 group count to change exactly the grid witness words."""
from pathlib import Path
import argparse,hashlib,json,struct
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('control',type=Path);p.add_argument('--positive',type=Path,required=True);a=p.parse_args()
d=json.loads((a.control/'results.json').read_text());positive=json.loads((a.positive/'results.json').read_text());m=json.loads((a.control/'execution/manifest.json').read_text());inp=json.loads((a.control/'inputs.json').read_text())
assert d['mode']==positive['mode']=='basic' and d['consumer_profile']=='manifest'
assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
assert inp['test_only_stale_group_witness']
for n,h in inp['source_hashes'].items():assert sha(a.control/n)==h
for n,h in inp['assets_SHA256'].items():assert sha(a.control/'assets'/n)==h
assert sha(a.control/'application')==inp['executable_SHA256']==m['original_binary_sha256']
differences=invocations=0;rows=[]
for t,(r,ref)in enumerate(zip(d['runs'],positive['runs'])):
 assert r['trial']==t and r['command_status']==4 and r['node_specs']==ref['node_specs']
 spec=r['node_specs'][(t+1)%3];groups=1+0xa5a5a5a5%spec['groups'];n=groups*spec['local'];target=4+(t+2)%3
 for k,(name,cn)in enumerate(zip(r['outputs'],r['counter_files'])):
  expected=bytearray((a.positive/'outputs'/name).read_bytes());actual=(a.control/'outputs'/name).read_bytes()
  assert (a.control/'outputs'/cn).read_bytes()==(a.positive/'outputs'/cn).read_bytes()
  if k==target:
   oo=128+32*(k-4)
   for i in range(n):
    assert struct.unpack_from('<I',expected,oo+i*16+8)[0]==groups|(1<<16)|(1<<24)
    struct.pack_into('<I',expected,oo+i*16+8,spec['groups']|(1<<16)|(1<<24))
   differences+=n;invocations+=n
  assert actual==expected,(t,k)
 rows.append({'trial':t,'actual_dispatch_groups':groups,'shader_visible_groups':spec['groups'],'invocations':n})
receipt={'status':'PASS_EXPECTED_GRID_WITNESS_MISMATCH','changed_uint32_words':differences,'unchanged_invocation_count':invocations,'all_other_output_counter_guard_bytes_identical':True,'runs':rows,'performance_benchmark':False}
with(a.control/'independent-control-verification.json').open('x')as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(receipt,indent=2))
