#!/usr/bin/env python3
"""Record bounded SDK lifetime evidence without changing the full objective."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/command-ir-lifetime-progress-20261015';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();r=json.loads((OUT/'qualification-receipt.json').read_text());assert r['status']=='PASS'and not r['objective_complete']
paths=[ROOT/'results/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/evidence-summaries/hardware-coverage.json'];raw=[p.read_bytes()for p in paths];assert len(set(raw))==1;d=json.loads(raw[0]);assert not d['complete']and len(d['coverage'])==31
imports=next(x for x in d['coverage']if x['category']=='Application-local native program import');imports['tested_scope']+=' SDK return-ownership correction:6documented+1 C factories now NS_RETURNS_RETAINED; bodies MRC unchanged. Same-object CPU fixture6retained vs6destroyed, real compute-pipeline GTX A/B8trials/16output files identical with old pipeline retained and annotated pipeline released. Annotated MRC object is byte-identical after rebuild. Real graphics/tessellation/NoCopy ARC destruction, native caches and fullVRAM remain unqualified.'
ir=next(x for x in d['coverage']if x['category']=='Public MSL compute-command frontend and portable GPU command IR');ir['status']='GPU_IR_v2_native_bindings_and_bounded_caller_lifetimes_qualified_L2';ir['tested_scope']+=' Caller lifetime:abandoned CB->callback->plan->CB cycle reproduced and removed by retaining immutable producer resource list instead of plan. Final annotated/rebuilt callers43cohorts/169trials (36lifetime,64dataflow,69XYZ/v1/v2/shared);32fixed lifetime cases plus4legacy-retention witnesses,8uncommitted mainCBs not assigned numeric execution. Observed scope/plan/ICB/native records/root/private buffer/imported writer deallocated in fixed cases after owner/pool release. Same current-source M1 reference12trials/156files identical. Static runtime d881 unchanged; prior129core cohorts not reexecuted or transferred as new-caller qualification. New probes/system checks recorded. No gain or transparent integration claim.'
for row in [imports,ir]:
 for e in ['COMMANDES_GPU_DUREE_VIE_2026-10-15.txt','results/command-ir-lifetime-progress-20261015/qualification-receipt.json','results/command-ir-lifetime-progress-20261015/real-return-ownership-pair.json','results/command-ir-lifetime-return-contract-recheck-20261015/receipt.json']:
  if e not in row['evidence']:row['evidence'].append(e)
text=json.dumps(d,ensure_ascii=False,indent=2)+'\n';changes=[]
for i,p in enumerate(paths):
 before=OUT/'before'/f'hardware-coverage-{i}.json'
 with before.open('xb')as f:f.write(raw[i])
 old=sha(p);p.write_text(text);changes.append({'path':str(p),'before_SHA256':old,'after_SHA256':sha(p)})
with(OUT/'coverage-update.json').open('x')as f:json.dump({'status':'PASS','complete':False,'categories':31,'changes':changes},f,indent=2);f.write('\n')
print('coverage31categories /3copies /complete=false PASS')
