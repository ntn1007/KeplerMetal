#!/usr/bin/env python3
from pathlib import Path
import json,shutil
r=Path(__file__).resolve().parents[1];p=r/'results/gpu-generated-bindings-progress-20261014'
q=json.loads((p/'final-qualification/qualification-receipt.json').read_text());assert q['status']=='PASS'and not q['objective_complete']
paths=[r/'results/hardware-coverage.json',r.parent/'driver-research-2026-10-13/inventory/hardware-coverage.json',r.parent/'driver-research-2026-10-13/inventory/evidence-summaries/hardware-coverage.json']
backup=p/'coverage-before';backup.mkdir(exist_ok=False)
for i,f in enumerate(paths):
 shutil.copyfile(f,backup/(str(i)+'-hardware-coverage.json'));d=json.loads(f.read_text());assert not d['complete']and len(d['coverage'])==30
 for e in d['coverage']:
  if e['category']=='CPU-recorded compute ICB selectors and bounded resource lifetime':
   e['GPU_resource_binding_qualification']={**q,'evidence':'bridge/results/gpu-generated-bindings-progress-20261014/final-qualification/qualification-receipt.json'}
   e['tested_scope']+='; GPU selects independent approved output/counter catalogue and rewrites dedicated CB1, retaining/declaration of6extra resources and propagation through GPU copies, with native M1 set_kernel_buffer reference'
   e['full_category_qualified']=False
  elif e['category']=='Native ICB factory/runtime boundary':
   e['application_local_GPU_resource_bindings']='Qualified L2 catalogue extension, installed NVMTLDevice unchanged'
 f.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
print('Three coverage copies updated;30categories;complete=false')
