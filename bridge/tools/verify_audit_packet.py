#!/usr/bin/env python3
"""Portable integrity and raw arithmetic checks; does not attest a remote GPU."""
from pathlib import Path
import hashlib,json,struct
root=Path(__file__).resolve().parent
manifest=json.loads((root/'packet-manifest.json').read_text())
for a in manifest['files']:
 p=root/a['path'];assert p.stat().st_size==a['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256'],a['path']
MASK=0xffffffff;words_checked=0;atomic_threads=0
suite=json.loads((root/'results/shared-units-audited/manifest.json').read_text());assert len(suite['cases'])==288
for c in suite['cases']:
 d=json.loads((root/c['result']).read_text());b=(root/c['dump']).read_bytes();assert b[:64]==b[-64:]==bytes([0xa5])*64
 v=struct.unpack('<'+'I'*((len(b)-128)//4),b[64:-64]);kind=d['kind'];groups=d['groups'];local=d['local'];active=d['active'];seed=(0xfffffff0 if d['variant'] else 0xf00d5000);assert seed==d['seed'];control=0xabad1dea if d['mode']=='control' else 0
 if kind=='capacity':
  n=d['shared_bytes']//4;assert len(v)==groups*n*2
  for g in range(groups):
   for phase in range(2):
    for i in range(n):
     x=(i*(7 if phase else 5)+(13 if phase else 7))%n
     assert v[g*n*2+phase*n+i]==((x*0x9e3779b9)&MASK)^(seed^(g*0x100001))^(0x6a09e667 if phase else 0)^control
  words_checked+=len(v)
 else:
  assert len(v)==groups*(local+1)
  for g in range(groups):
   initial=(seed+g*0x100001)&MASK;ret=list(v[g*(local+1):g*(local+1)+active]);final=v[g*(local+1)+local]
   assert v[g*(local+1)+active:g*(local+1)+local]==(0xa5a5a5a5,)*(local-active)
   if kind=='add':
    step=2 if control else 1;assert final==(initial+active*step)&MASK;assert sorted(ret)==sorted((initial+i*step)&MASK for i in range(active))
   elif kind=='exchange':assert sorted(ret+[final])==sorted([initial]+[(0x12345678^i)^control for i in range(active)])
   else:
    assert kind=='cas';replacement=0x12345678^control;assert final==(initial if d['variant'] else replacement);assert sorted(ret)==sorted([initial]*active if d['variant'] else [initial]+[replacement]*(active-1))
  atomic_threads+=groups*active
bench=json.loads((root/'results/shared-benchmark-final/manifest.json').read_text());measured_groups=0;raw_benchmark_words=0
def expected_sum(kind,seed,local,groups):return sum((((7*0x9e3779b9)&MASK)^(seed^(g*0x100001)))if kind=='capacity'else(seed+g*0x100001+local)&MASK for g in range(groups))&MASK
for c in bench['cases']:
 d=json.loads((root/c['result']).read_text());kind=c['kind'];groups=c['groups'];local=c['local'];batch=c['batch'];assert len(d['samples'])==18
 for s in d['samples']:
  seed=(0xfffffc00+(s['round']+3)*0x9e3779b9)&MASK;assert seed==s['seed'];assert s['GPU_completed_groups']==groups*batch;assert s['GPU_result_checksum']==(expected_sum(kind,seed,local,groups)*batch)&MASK;measured_groups+=groups*batch
 seed=(0xfffffc00+12*0x9e3779b9)&MASK
 for path in ('metal','nak'):
  prefix=str((root/c['result']).with_suffix(''))+'-'+path;b=Path(prefix+'.output.bin').read_bytes();p=Path(prefix+'.progress.bin').read_bytes();assert b[:64]==b[-64:]==p[:64]==p[-64:]==bytes([0xa5])*64
  assert struct.unpack_from('<2I',p,64)==(groups*batch,(expected_sum(kind,seed,local,groups)*batch)&MASK);v=struct.unpack('<'+'I'*((len(b)-128)//4),b[64:-64]);raw_benchmark_words+=len(v)
  for g in range(groups):
   if kind=='capacity':
    n=12288
    for phase in range(2):
     for i in range(n):
      x=(i*(7 if phase else 5)+(13 if phase else 7))%n;assert v[g*n*2+phase*n+i]==((x*0x9e3779b9)&MASK)^(seed^(g*0x100001))^(0x6a09e667 if phase else 0)
   else:
    initial=(seed+g*0x100001)&MASK;assert sorted(v[g*(local+1):g*(local+1)+local])==sorted((initial+i)&MASK for i in range(local));assert v[g*(local+1)+local]==(initial+local)&MASK
print(json.dumps({'integrity_files':len(manifest['files']),'shared_cases':288,'capacity_words_all_three_modes':words_checked,'atomic_threads_all_three_modes':atomic_threads,'measured_GPU_group_counter_values_verified':measured_groups,'benchmark_raw_words_verified':raw_benchmark_words,'offline_arithmetic_passed':True,'remote_hardware_execution_attested':False},indent=2))
