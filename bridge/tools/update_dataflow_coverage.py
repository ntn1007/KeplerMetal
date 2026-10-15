#!/usr/bin/env python3
"""Add the qualified dataflow scope without claiming full hardware/API coverage."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'results/command-ir-dataflow-progress-20261015';read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read(out/'qualification-receipt.json');assert r['status']=='PASS'and not r['objective_complete'];paths=[ROOT/'results/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/evidence-summaries/hardware-coverage.json']
before=[p.read_bytes()for p in paths];assert len(set(before))==1
d=json.loads(before[0]);assert not d['complete'];row=next(c for c in d['coverage']if c['category']=='Public MSL compute-command frontend and portable GPU command IR');assert len(d['coverage'])==31
row['status']='GPU_IR_v2_XYZ_native32B_bindings_and_three_stage_dataflow_qualified_L2'
row['tested_scope']+=' Dataflow extension: constants reflected at slot2/3, inactive reflected input, exact same-buffer/same-offset sharing across catalogue entries. Full32B native resource bindings captured by suppressed-launch preparations and selected/copied on GPU; no arbitrary handles. Three archived-native seed/gather/finish kernels,64trials,5035008uint32 exact,1258752counted invocations,81473504guardbytes. Missing-stage/producer/consumer,copy/reset,split-CB,6invalid-record cases and8API refusals. Native M1 same-source reference12trials/156files identical. Matched8B descriptor controls8additionaltrials isolate opaque-read-binding effect while preserving VA and counters. Current d8815830 library:132XYZ/60v1/60v2three/24combined plus11API refusals+6positiveXYZ;129legacy cohorts/185steps/129offlineoracles;60primer+9policy checks. Previous pointer-only numerical failures preserved; no gain claimed.'
row['remaining_requirements']='Partial/nonuniform workgroups; other reflected constant/buffer layouts; stage-in/strides/textures/samplers in GPU IR; cross-context copies; sustained/concurrent lifetime and dependency stress; complete ICB contract; ordinary-application transparent integration and benchmark. Preserve separate native-driver,video,display,power and full-VRAM objective.'
for e in ['COMMANDES_GPU_FLUX_NATIFS_2026-10-15.txt','results/command-ir-dataflow-progress-20261015/qualification-receipt.json','results/command-ir-dataflow-progress-20261015/preserved-failures.json','results/command-ir-dataflow-descriptor-controls-20261015/receipt.json','results/command-ir-dataflow-M1-return-20261015/receipt.json']:
 if e not in row['evidence']:row['evidence'].append(e)
after=json.dumps(d,ensure_ascii=False,indent=2)+'\n';history=[]
for i,p in enumerate(paths):
 saved=out/'before'/f'hardware-coverage-{i}.json'
 with saved.open('xb')as f:f.write(before[i])
 old=sha(p);p.write_text(after);history.append({'path':str(p),'before_SHA256':old,'after_SHA256':sha(p)})
(out/'coverage-update.json').write_text(json.dumps({'status':'PASS','complete':False,'categories':31,'copies':history},indent=2)+'\n');print('coverage3copies /31categories /complete=false PASS')
