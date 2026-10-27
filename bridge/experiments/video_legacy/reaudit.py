#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the frozen legacy-video cohort; do not execute a native host."""
import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PINS = {
 'audit_video_enumeration':'244c5664498000afe2d6be010cd1cd8a6ff309c6e8c689f3d59024a57af37618',
 'audit_video_factory':'cc3b9259c2b2a994163d8f7fdfbbd40c31af87cebc1df5a85dff83ea8ec10a42',
 'audit_video_legacy':'f11130b4f6206951aecb57a068d5daa1e46cf69f0d1712e533db743a3f218d26',
 'audit_video_local_service':'fc19df8d6658d73ce6952a2989dabe64b093b8ca60c9c7ca19e38e383c97193b',
 'audit_video_local_xpc':'0ba47ad05d386724edf56b283e25df231b29af3159b8df2119b35dd87502ac5c',
 'audit_video_registry':'4eb0d5914ab603e7b494d0f0070dd384771f54a6aa79b01f9b71e088c05e1024',
 'audit_video_routing':'0047130204ec9e69399db5294fcb094aa95b248738207d617a34b3cdab0d0802',
 'audit_video_start':'64772d4ecabd183d3c7eed50940662c6bc688372960d91cd45cb35a90a7633ae',
 'native_video_factory':'9a16a6df79affb20bd5e70dd215aa754d1197f10851ac1d0fa53b11741d2d435',
 'native_video_local_service':'9778a8dca4262bdf8fc120ea9d0729d31ee148bf2caca660d7740b55628318bd',
 'native_video_routing':'acf98802ec94954e81cf57f65067fbb325231beaff27bad4c6c5c18f305c080d',
 'verify_control_flow':'8f7ab8957c0c51c579b27504843b3ee4bc5a1f6501ddbca3bcc125504fa5d532',
 'verify_control_flow_delivery':'61c02feb1e49522bafd2bbe5e95d12b77b5c691b0d20da709718d3dd120dd28b',
 'verify_native_cas_sdk':'247c97e9fdbc0c0ae2098251210b01fbe5129a79be181e2e5772b6a618cf7bbf',
 'verify_native_control_reserve':'6ba93e85fda6d515db3e12c4ff5648fcee29c89c8fa8e0105b309cf85a26ed9c',
}
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def need(ok, why):
 if not ok:raise ValueError(why)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lab',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 lab=a.lab.resolve();tools=lab/'tools';need(not a.out.exists(),'Fresh output required')
 # Validate the local transitive import closure: no undeclared local module is loaded.
 todo=['audit_video_legacy'];seen=set()
 while todo:
  name=todo.pop()
  if name in seen:continue
  source=tools/(name+'.py')
  if not source.is_file():continue
  need(name in PINS and digest(source)==PINS[name],'Unqualified local module: '+name)
  seen.add(name)
  for node in ast.walk(ast.parse(source.read_text())):
   if isinstance(node,ast.ImportFrom) and node.module:todo.append(node.module.split('.')[0])
   elif isinstance(node,ast.Import):todo.extend(x.name.split('.')[0] for x in node.names)
 need(seen==set(PINS),'Import closure changed')
 sys.path.insert(0,str(tools));import audit_video_legacy as v
 old=lab/'results/video-legacy-contract-progress-20261018/legacy-audit-final.json'
 need(digest(old)=='73498e87f5f9872d3a2a5832c2c2dd447e9868cdbb84a4977b405f3f7e217b6b','Historical audit changed')
 historical=json.loads(old.read_text());proof=v.static_proofs(lab)
 rows=sorted((v.probe(lab,*case) for case in v.CASES),key=lambda r:r['started_at'])
 need(rows==historical['cases'],'Frozen case receipts differ from historical audit')
 need(len(rows)==20 and len({x['PID'] for x in rows})==20,'Process identities')
 need(all(x['completed_at']<=y['started_at'] for x,y in zip(rows,rows[1:])),'Overlapping processes')
 ps=subprocess.run(['ps','-p',','.join(str(x['PID']) for x in rows),'-o','pid='],capture_output=True,text=True,check=False)
 need(ps.returncode in (0,1) and not ps.stdout.strip(),'Historical PID is live or ps failed')
 baseline_path=lab/'results/video-local-xpc-progress-20261018/start.json'
 need(digest(baseline_path)=='ce2d2ce2e381f567ad50bd9cf77747adfada6554c9b04b06683bda88ac76243e','Historical system inventory differs')
 baseline=json.loads(baseline_path.read_text())
 changed=[];missing=[]
 for item in baseline['system_before']:
  path=Path(item['path'])
  if not path.is_file():missing.append(str(path))
  elif digest(path)!=item['SHA256']:changed.append(str(path))
 report={'status':'PASS_SCOPED','prior_full_audit_repeated':False,'prior_full_audit_currently':'NOT_RUN_BY_THIS_TOOL',
  'historical_audit_SHA256':digest(old),'current_protected_files_checked':len(baseline['system_before']),
  'current_protected_files_changed':changed,'current_protected_files_missing':missing,
  'native_hosts':len(rows),'terminal_nonoverlapping':True,'software_images':sum(x['software_images'] for x in rows),
  'exact_CPU_pixel_bytes':sum(x['exact_CPU_pixel_bytes'] for x in rows),
  'hardware_refusals':sum(x['mode']=='hardware' for x in rows),'actual_stub_pointer_cases':sum(x['actual_stub_pointer_cases'] for x in rows),
  'static_provenance':proof,'native_execution_during_reaudit':False,'hardware_video_execution_proved':False,
  'limitations':['Historical receipts rechecked using pinned original auditors, not independent hardware execution.',
   'Current protected-file comparison is distinct from the historical observation and excludes unlisted state.',
   'The matching backend is observed after return, not by a breakpoint on its private entry.']}
 a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
