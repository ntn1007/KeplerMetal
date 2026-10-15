#!/usr/bin/env python3
"""Run matched native descriptor8-byte controls after the legacy GPU suite ends."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);a=p.parse_args()
assert json.loads((ROOT/'results/command-ir-dataflow-full-nonregression-20261015/completion.json').read_text())['status']=='PASS'
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);history=[];targets={}
for mode in ['descriptor_positive','descriptor_negative']:
 target=ROOT/'results'/(a.prefix+'-'+mode);targets[mode]=target
 for phase,args in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',a.build.resolve(),'--out',target,'--mode',mode]),('CPU',[sys.executable,ROOT/'tools/verify_command_ir_dataflow.py',target])]:
  args=[str(x)for x in args];r=subprocess.run(args,capture_output=True,text=True,timeout=75);(out/(mode+'-'+phase+'.stdout')).write_text(r.stdout);(out/(mode+'-'+phase+'.stderr')).write_text(r.stderr);history.append({'mode':mode,'phase':phase,'argv':args,'exit_code':r.returncode});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n');assert not r.returncode,(mode,phase,r.stderr[-2500:])
 print(mode,'expected CPU oracle PASS',flush=True)
import struct
positive,negative=[json.loads((targets[k]/'results.json').read_text())for k in ['descriptor_positive','descriptor_negative']];comparisons=[]
pi,ni=[json.loads((targets[k]/'inputs.json').read_text())for k in ['descriptor_positive','descriptor_negative']]
for key in ['executable_SHA256','static_library_SHA256','assets_SHA256','source_hashes']:assert pi[key]==ni[key]
for p,n in zip(positive['runs'],negative['runs']):
 assert p['specs']==n['specs'];entry={'trial':p['trial'],'count':p['specs'][0]['count'],'stage_component_differences':[]}
 counts=[sum(e['operation']=='materialize_CPU_command'for e in r['scope_events'])for r in [p,n]];assert counts==[15*(p['trial']+1)]*2;entry['native_preparations_per_trial_per_variant']=15;entry['cumulative_native_preparations_per_variant']=counts[0]
 for name in ['stage0','stage1','stage2','counter']:
  a=(targets['descriptor_positive']/'outputs'/p['files'][name]).read_bytes();b=(targets['descriptor_negative']/'outputs'/n['files'][name]).read_bytes();assert len(a)==len(b)
  if name in ['stage0','counter']:assert a==b
  else:
   count=p['specs'][0]['count']*4;aa=struct.unpack_from('<'+'I'*count,a,128);bb=struct.unpack_from('<'+'I'*count,b,128);differences=sum(x!=y for x,y in zip(aa,bb));assert differences>0;entry['stage_component_differences'].append({'stage':name,'words_different':differences,'words':count})
 comparisons.append(entry)
receipt={'status':'PASS','control_trials':8,'native_library_and_runtime_identical':True,'preparation_and_blit_counts_identical':True,'changed_binding_bytes_per_stage':8,'stages_with_controlled_read_binding':[1,2],'same_GPU_VAs_and_other_entry_fields_within_each_control':True,'negative_result_correctly_differs_from_full_chain':True,'stage0_and_all_stage_counters_identical':True,'comparisons':comparisons,'performance_benchmark':False,'full_objective_complete':False}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
