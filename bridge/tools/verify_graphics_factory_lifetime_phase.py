#!/usr/bin/env python3
"""Recompute the entire archived matrix, keeping the Managed failure visible."""
from pathlib import Path
import argparse,collections,json,struct
from verify_graphics_factory_lifetime import verify
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
hist=[]
for name in ['graphics-factory-lifetime-suite-20261015','graphics-factory-lifetime-remainder-20261015']:hist+=json.loads((ROOT/'results'/name/'history.json').read_text())
entries={r['case']:Path(r['directory'])for r in hist if r['phase']in ['CPU','reuse_existing_terminal_cohort']};assert len(entries)==22
rows=[]
for case,original in entries.items():
 # Archives may live at a new absolute path. Use only the recorded basename.
 root=ROOT/'results'/original.name
 try:result=verify(root);rows.append({'case':case,'status':'PASS','directory':str(root),'verification':result})
 except AssertionError as e:
  assert case=='host_managed:cancel';rows.append({'case':case,'status':'FAIL','directory':str(root),'reason':str(e),'infrastructure_failure':False})
assert sum(r['status']=='PASS'for r in rows)==21
comparisons=[]
for policy in ['drop','keep']:
 x=ROOT/'results'/entries['tessellation:'+policy].name;y=ROOT/'results'/entries['native_tess:drop'].name
 dx=json.loads((x/'results.json').read_text());dy=json.loads((y/'results.json').read_text())
 for i in range(4):
  n=struct.unpack_from('<I',(x/'outputs'/dx['runs'][i]['files']['counter']).read_bytes(),64)[0]
  first=(x/'outputs'/dx['runs'][i]['files']['coordinates']).read_bytes();second=(y/'outputs'/dy['runs'][i]['files']['coordinates']).read_bytes()
  equal=collections.Counter(first[64+k*16:80+k*16]for k in range(n))==collections.Counter(second[64+k*16:80+k*16]for k in range(n));assert equal
  comparisons.append({'imported_policy':policy,'trial':i,'coordinates':n,'native_imported_coordinate_multiset_bit_exact':equal})
v={'status':'PARTIAL','cohorts':22,'scenarios':88,'PASS_cohorts':21,'FAIL_cohorts':1,'full_objective_complete':False,'performance_benchmark':False,'rows':rows,'native_tess_coordinate_comparisons':comparisons,'numeric_components_checked':sum(r.get('verification',{}).get('numeric_components_checked',0)for r in rows),'guard_bytes':sum(r.get('verification',{}).get('guard_bytes',0)for r in rows),'raw_files':sum(r.get('verification',{}).get('raw_files',0)for r in rows)}
with a.out.open('x')as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in v.items()if k not in ['rows','native_tess_coordinate_comparisons']}))
