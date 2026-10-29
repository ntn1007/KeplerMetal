#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline audit; no native launches or GPU operations."""
import argparse,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import sha,write

def need(x,m):
 if not x:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',nargs=6,type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output');b=read(a.build/'build.json');need(all(sha(a.build/n)==h for n,h in b['files'].items()) and sha(HERE/'host.mm')==b['files']['host.mm'] and sha(HERE/'experiment.py')==b['files']['runner.py'],'build/source differs');need(subprocess.run(['codesign','--verify','--strict',str(a.build/'libObserver.dylib')],capture_output=True).returncode==0,'library signature')
 modes=['inventory','control','baseline','large','baseline','large'];ids=[];times=[];rows=[];target=None
 for path,mode in zip(a.runs,modes):
  e=read(path/'execution.json');v=read(path/'verification.json');r=read(path/'stdout.json');lease=e['reservation'];need(e['mode']==v['mode']==r['mode']==mode and e['exit_code']==0 and v['status']=='PASS' and e['profile_unchanged'] and lease['state']=='terminal' and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'] and lease['child_PID']==e['pid']==r['pid'],'terminal/mode differs')
  need(sha(path/'application')==e['host_sha256']==b['files']['application'] and sha(path/'stdout.json')==e['stdout_sha256'] and sha(path/'stderr.log')==e['stderr_sha256'] and e['build_sha256']==sha(a.build/'build.json') and subprocess.run(['codesign','--verify','--strict',str(path/'application')],capture_output=True).returncode==0,'provenance')
  need(not r['matching_status'] and not r['truncated'] and not r['dropped'] and not r['observer_inflight_final'] and not r['explicit_GPU_commands'] and not r['hardware_video_execution_proved'] and not r['raw_payload_exported'] and r['uid']==r['euid']==b['uid']!=0,'host constraints')
  devices=[x for x in r['services'] if x['class']=='nvAccelerator' and x['gpu_ancestor'] and x['class_status']==x['registry_status']==0];need(len(devices)==1,'device ambiguity')
  if mode=='inventory':target=devices[0]['registry_ID'];need(v['registry_id']==target and not r['candidate_count'] and not r['events'],'inventory')
  else:
   need(r['target']==target and r['candidate_count']==1 and devices[0]['candidate'] and r['pci_registry_ID']==devices[0]['pci_registry_ID'],'device identity')
   events=r['events']
   if mode=='control':need(v['interposition_calibrated'] and r['control_open_status']==r['control_close_status']==0 and all(any(z['kind']==k and z['port']==0 and z['status']!=0 for z in events) for k in ('method','struct')),'hook calibration')
   else:
    need(r['status']=='WARM_COMPARISON_RECORDED' and r['metal_candidates']==1 and r['metal_pci_registry_ID']==r['pci_registry_ID'] and r['warm_created'] and r['cpu_bytes_correct'] and r['warm_weak_cleared'],'Metal control')
    matches=[z for z in events if z['phase']==4 and z['kind']=='method' and z['type_or_selector']==0 and z['status']==0 and z['input_struct_bytes']==168 and z['output_struct_bytes']==89 and z['caller_symbol']=='IOAccelResourceCreate' and z['caller_offset']==0x2072]
    if mode=='baseline':need(not r['target_created'] and not matches and not r['selected_reply_fields_captured_in_memory'],'baseline event')
    else:
     q=r['reply_identity'];c=q['comparison'];need(r['target_created'] and r['target_length']==4194304 and r['target_weak_cleared'] and len(matches)==1 and q['status']=='PINNED' and q['resource_fields_read'] and not q['getter_called'] and c['captured_qualified_reply_count']==c['matching_pairs']==1 and c['wrong_value_matches']==0 and not c['raw_addresses_exported'] and r['selected_reply_fields_captured_in_memory'],'comparison')
  ids.append(lease['reservation_id']);times.append((e['started_at'],e['completed_at']));rows.append({'mode':mode,'host_sha256':e['host_sha256'],'stdout_sha256':e['stdout_sha256'],'reservation_id':ids[-1],'terminal':True})
 need(len(set(ids))==6 and all(times[i][1]<=times[i+1][0] for i in range(5)),'overlap')
 result={'status':'PASS_LIVE_METAL_REPLY_FIELDS','hosts':6,'matching_real_buffer_creations':2,'baseline_controls':2,'identity_controls':2,'resource_bytes_cpu_checked':8388608,'captured_fields_compared_inside_process':True,'raw_addresses_exported':False,'independent_raw_field_recomparison':False,'explicit_gpu_commands':False,'hardware_video_execution_proved':False,'generic_metal_buffer_is_video_buffer':False,'system_modified':False,'source_sha256':b['files']['host.mm'],'runner_sha256':b['files']['runner.py'],'library_sha256':b['files']['libObserver.dylib'],'application_sha256':b['files']['application'],'audit_sha256':sha(Path(__file__)),'rows':rows};write(a.out,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
