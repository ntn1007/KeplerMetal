#!/usr/bin/env python3
"""Check raw dependency results and explicit caller/scope ownership observations."""
from pathlib import Path
import argparse,hashlib,json
from verify_command_ir_dataflow import verify as numeric_verify
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(directory):
 root=Path(directory);d=json.loads((root/'results.json').read_text());variant=d['lifetime_variant'];cancelled=variant.startswith('cancel_')
 m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text())
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']and sha(root/'execution/application')==m['signed_binary_sha256']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 assert d['device']=='NVIDIA GeForce GTX 880M'and d['registry_id']==4294968458 and d['scope_restored']and not d['system_modified']and len(d['runs'])==4
 if cancelled:
  assert d['mode']=='basic'and not list((root/'outputs').iterdir());numeric={'status':'NOT_RUN_UNCOMMITTED','raw_files':0,'exact_uint32_results':0,'consumer_invocations':0}
 else:numeric=numeric_verify(root)
 states=[]
 for trial,r in enumerate(d['runs']):
  l=r['lifetime'];assert r['trial']==trial and l['variant']==variant and l['caller_pool_drained_before_commit']and l['caller_bundle_retained']==(variant=='keep')and l['main_status_before_commit']==0
  assert l['abandoned_without_commit']==cancelled and r['committed']==(not cancelled)and r['command_status']==(0 if cancelled else 4)and l['device_restored_after_release']
  if variant not in ['keep','drop']:assert l['device_restored_before_commit']
  leaked=[l[k+'_alive_after_command_release']for k in ['plan','scope','ICB']]
  assert leaked==([True]*3 if variant=='cancel_legacy'else[False]*3),(variant,trial,'application wrapper lifetime',leaked)
  if variant!='cancel_legacy':
   for key in ['record','binding_record','root','private_buffer']:assert not l[key+'_alive_after_command_release'],(variant,trial,key)
  if 'return_ownership_annotated' in inp:
   expected=(not inp['return_ownership_annotated'])or variant=='cancel_legacy';assert l['imported_writer_alive_after_release']==expected,(variant,trial,'imported pipeline ownership')
  states.append({'trial':trial,'caller_pool_drained':True,'device_restored_before_commit':l['device_restored_before_commit'],'application_wrappers_retained_after_release':any(leaked),'root_alive_after_release':l['root_alive_after_command_release'],'native_record_alive_after_release':l['record_alive_after_command_release'],'private_buffer_alive_after_release':l['private_buffer_alive_after_command_release'],'legacy_cycle_observed':variant=='cancel_legacy'})
 return {'status':'PASS','variant':variant,'trials':4,'committed':not cancelled,'numeric':numeric,'states':states,'runtime_SHA256':inp['static_library_SHA256'],'performance_benchmark':False,'full_objective_complete':False,'native_cache_or_full_VRAM_cleanup_qualified':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args();r=verify(a.directory)
 with(a.receipt or a.directory/'lifetime-verification.json').open('x')as f:json.dump(r,f,indent=2);f.write('\n')
 print(json.dumps({**{k:v for k,v in r.items()if k not in ['numeric']},'numeric':{k:v for k,v in r['numeric'].items()if k!='raw_SHA256'}},indent=2))
