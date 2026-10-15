#!/usr/bin/env python3
"""Append completed, bounded evidence without declaring the hardware complete."""
from pathlib import Path
import json,shutil

r=Path(__file__).resolve().parents[1]
base=r/'results/gpu-generated-geometry-progress-20261014'
geometry=json.loads((base/'final-qualification/qualification-receipt.json').read_text())
selection=json.loads((r/'results/gpu-generated-selection-progress-20261014/final-qualification/qualification-receipt.json').read_text())
assert geometry['status']==selection['status']=='PASS' and not geometry['objective_complete']
paths=[r/'results/hardware-coverage.json',r.parent/'driver-research-2026-10-13/inventory/hardware-coverage.json',r.parent/'driver-research-2026-10-13/inventory/evidence-summaries/hardware-coverage.json']
backup=base/'coverage-before';backup.mkdir(exist_ok=False)
for i,p in enumerate(paths):
    shutil.copyfile(p,backup/(str(i)+'-hardware-coverage.json'))
    d=json.loads(p.read_text());assert not d['complete'] and len(d['coverage'])==30
    for e in d['coverage']:
        if e['category']=='CPU-recorded compute ICB selectors and bounded resource lifetime':
            e['GPU_command_selection_qualification']={**selection,'evidence':'bridge/results/gpu-generated-selection-progress-20261014/final-qualification/qualification-receipt.json'}
            e['GPU_grid_prefix_qualification']={**geometry,'evidence':'bridge/results/gpu-generated-geometry-progress-20261014/final-qualification/qualification-receipt.json'}
            e['tested_scope']+='; GPU selects sealed candidate and computes bounded X-grid prefix from Private input, with native M1 reference and independent raw-output/counter/guard verification'
            e['remaining_requirements']='Other registered compute/render ABI layouts, general GPU shader/command construction and MSL frontend, broader dimensions and state changes, inherited states, concurrent/pressure/lifecycle qualification, new-library performance measurements and transparent ordinary-application integration'
            e['full_category_qualified']=False
        elif e['category']=='Grid geometry and control flow':
            e['GPU_grid_prefix_evidence']='bridge/results/gpu-generated-geometry-progress-20261014/final-qualification/qualification-receipt.json'
            e['tested_scope']+='; certified native shared kernels: GPU-computed bounded1D prefix, local size/resources/static+dynamic allocations preserved'
        elif e['category']=='Native ICB factory/runtime boundary':
            e['application_local_GPU_grid_prefix']='Qualified L2 separate adapter; installed NVMTLDevice factory/runtime unchanged'
    p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
print('Updated three coverage copies;30categories;full objective remains incomplete')
