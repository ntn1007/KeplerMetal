#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently check per-descriptor native profiles for the dual-copy witness."""
import importlib.util,json,sys
from pathlib import Path

def need(ok,why):
 if not ok:raise ValueError(why)
def check(root):
 root=Path(root).resolve();path=root/'src/verify_partial_gpu_dual_copy.py';spec=importlib.util.spec_from_file_location('frozen_dual_oracle',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);base=mod.verify(root)
 r=json.loads((root/'results.json').read_text());proof=r['execution_event']['evidence'];profiles=proof['owner_original_profiles'];by_address={x['descriptor_GPU_address']:x for x in profiles};need(len(by_address)==len(profiles)==proof['owners'],'Owner identity differs')
 barrier=4 if r['scenario']==3 else 2;expected=['partial_builtin_barrier']*barrier+['partial_buffer_stencil']
 def check_record(address,name):
  p=by_address.get(address);need(p is not None and p['original_record_function']==name,'Pipeline identity differs')
  need(p['native_register_count']==(22 if name=='partial_builtin_barrier' else 11) and p['static_threadgroup_bytes']==(512 if name=='partial_builtin_barrier' else 0) and p['QMD_total_shared_bytes']==(512 if name=='partial_builtin_barrier' else 0),'Native profile differs')
  need(p['manifest_SHA256']=='c7dcdc81adba7f7ba6cf8175ecc179a086a9bd150b44d71ca1a39ad18846ef9a','Native registration differs')
 addresses=proof['descriptor_GPU_addresses'];need(len(addresses)==len(expected),'Execution descriptor count differs')
 for address,name in zip(addresses,expected):check_record(address,name)
 if r['mode']!='native':
  pairs=r['copy_event']['descriptor_pairs'];need(len(pairs)==len(expected),'Copied pair count differs')
  for pair,name in zip(pairs,expected):check_record(pair['source'],name);check_record(pair['destination'],name)
 need(r['pipeline_mismatch_refused'],'Different pipelines in a pair accepted')
 return dict(base,dual_pipeline_profiles_checked=True)
if __name__=='__main__':print(json.dumps(check(sys.argv[1]),sort_keys=True))
