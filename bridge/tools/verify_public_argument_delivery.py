#!/usr/bin/env python3
"""Verify the final typed-binding candidate, negative cases and native M1 data."""
from pathlib import Path
import argparse,hashlib,json
from verify_command_ir_dataflow import verify as numeric
from verify_command_ir_lifetime import verify as lifetime
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
library=ROOT/'results/argument-binding-runtime-library-build-20261015-06';lm=json.loads((library/'manifest.json').read_text());pin=sha(library/'libKeplerMetal.a');assert pin==lm['static_library_SHA256']=='edd584b05b94ca536ab65a1976440a52e521a15657e0b02f843be1a422d7b176'
for n,h in lm['source_SHA256'].items():assert sha(library/n)==h
rows=[]
def cohort(path,public=True,life=False):
 root=Path(path);inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());assert inp['static_library_SHA256']==pin and sha(root/'execution/application')==m['signed_binary_sha256']
 v=lifetime(root)if life else numeric(root)
 if not life:
  assert d['public_argument_encoder']==public and not d['argument_refusal_probe']
  if public:
   for r in d['runs']:
    events=[e for e in r['events']if e.get('operation')=='encode_public_IRv2_arguments'];assert len(events)==4 and[(e['candidate'],e['resource'],e['offset'],e['bytes'])for e in events]==[(0,0,0,48),(1,1,48,48),(2,2,96,48),(0,0,0,48)]and all(not e['native_Apple_ICB_identity']for e in events)
    assert any(e.get('operation')=='new_public_IRv2_argument_encoder'for e in r['scope_events'])
 rows.append({'directory':str(root),'kind':'lifetime'if life else'typed'if public else'legacy','results_SHA256':sha(root/'results.json'),'verification':v});return d
suite=ROOT/'results/public-argument-final-dataflow-suite-20261015';h=json.loads((suite/'history.json').read_text());modes=[r for r in h if r['phase']=='CPU'];assert len(modes)==16 and all(r['exit_code']==0 for r in h)
typed={}
for r in modes:root=ROOT/'results'/Path(r['result']).name;typed[r['mode']]=(root,cohort(root))
cohort(ROOT/'results/public-argument-final-reuse-20261015')
legacy_root=ROOT/'results/public-argument-final-legacy-basic-20261015';legacy=cohort(legacy_root,False)
basic_root,basic=typed['basic'];one=json.loads((basic_root/'inputs.json').read_text());two=json.loads((legacy_root/'inputs.json').read_text())
for key in ['source_hashes','assets_SHA256','runtime_SHA256','static_library_SHA256']:assert one[key]==two[key]
common_names=['input','stage0','stage1','stage2','dummySrc','counter','dummyCounter']+['dummy'+str(i)for i in range(6)]
ab=[]
for trial in range(4):
 for name in common_names:
  x=basic_root/'outputs'/basic['runs'][trial]['files'][name];y=legacy_root/'outputs'/legacy['runs'][trial]['files'][name];assert x.read_bytes()==y.read_bytes();ab.append({'trial':trial,'name':name,'SHA256':sha(x)})
life_suite=ROOT/'results/public-argument-final-lifetime-suite-20261015';h=json.loads((life_suite/'history.json').read_text());cohorts=[r for r in h if r['phase']=='CPU'];assert len(cohorts)==9 and all(r['exit_code']==0 for r in h)
for r in cohorts:cohort(ROOT/'results'/Path(r['directory']).name,False,True)
root=ROOT/'results/public-argument-final-refusals-20261015';d=json.loads((root/'results.json').read_text());inp=json.loads((root/'inputs.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());assert inp['static_library_SHA256']==pin and d['argument_refusal_probe']and d['public_argument_encoder']and len(d['runs'])==4 and d['scope_restored']and not list((root/'outputs').iterdir())
assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'and sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']and sha(root/'execution/application')==m['signed_binary_sha256']
for n,h in inp['source_hashes'].items():assert sha(root/n)==h
rejections=[r for x in d['runs']for r in x['argument_refusals']];assert len(rejections)==84 and all(r['PASS']and r['parameters_unchanged']and r['plan_released']and r['encoder_released']and not r['user_kernel_submitted']and r['reason']for r in rejections)
assert len({r['case']for r in rejections})==21
ref=ROOT/'results/public-argument-M1-final-return-20261015/Reference';rm=json.loads((ref/'REFERENCE_RETURN.json').read_text())
for e in rm['files']:assert sha(ref/e['path'])==e['SHA256']
assert sha(ref/'command_ir_dataflow_client.mm')==one['source_hashes']['command_ir_dataflow_client.mm']
native=[];cross=[]
for mode in ['no_producer','barrier','no_consumer']:
 root=ref/'results'/mode;d=json.loads((root/'results.json').read_text());v=numeric(root);assert d['public_argument_encoder']and not d['argument_refusal_probe'];native.append({'mode':mode,'verification':v})
 candidate,local=typed[mode]
 for i in range(4):
  for name in common_names:
   x=root/'outputs'/d['runs'][i]['files'][name];y=candidate/'outputs'/local['runs'][i]['files'][name];assert x.read_bytes()==y.read_bytes();cross.append({'mode':mode,'trial':i,'name':name,'SHA256':sha(x)})
v={'status':'PASS','candidate_library_SHA256':pin,'typed_dataflow_cohorts':16,'typed_dataflow_scenarios':64,'encoder_reuse_scenarios':4,'legacy_comparison_scenarios':4,'lifetime_scenarios':36,'rejection_cases':21,'rejection_scenarios':84,'total_final_candidate_scenarios':192,'M1_scenarios':12,'same_reception_source_SHA256':one['source_hashes']['command_ir_dataflow_client.mm'],'A_B_semantic_files_identical':len(ab),'M1_semantic_files_identical':len(cross),'native_Apple_ICB_resource_identity':False,'three_pointer_layout_GPU_qualified':False,'integration_level':2,'performance_benchmark':False,'full_objective_complete':False,'rows':rows,'rejections':rejections,'legacy_comparison':ab,'M1':native,'M1_comparison':cross}
with a.out.open('x')as f:json.dump(v,f,indent=2);f.write('\n')
print(json.dumps({k:x for k,x in v.items()if k not in ['rows','rejections','legacy_comparison','M1','M1_comparison']},indent=2))
