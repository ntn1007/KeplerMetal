#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit pinned legacy caller context and shared-client association without running a host."""
import argparse, hashlib, json, subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD_SHA = 'd18fcab0e8f100ad1800e4eeecbdf7c44e7509ca51e7b6dbc588d51a5d6a63b6'
GPU_ID = 4294968416
CASES = [('inspect','inspect','passive',False,False),('context','hardware','enabled',True,False),
         ('attach-1','hardware','enabled',True,True),('wrong','hardware','wrong-name',False,False),
         ('attach-2','hardware','enabled',True,True),('cpu','cpu','passive',False,False)]

def need(condition, why):
    if not condition: raise ValueError(why)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())

def check_gate(g, route, probe, attach):
    need(g['status'] == 'COMPLETE' and g['calibration_pass'] and g['service_calibration_pass'] and g['drained'] and g['dropped'] == 0, 'gate/calibration')
    need(not g['sierra_loaded'] and not g['sierra_export_called'] and g['gate_return'] == 14, 'provider unexpectedly used')
    need(g['context_probe_enabled'] is probe and g['explicit_video_external_methods']==0 and g['explicit_gpu_dispatches_by_gate']==0, 'probe setting')
    if probe:
        need(g['context_open_attempts']==1 and g['context_open_status']==0 and g['context_close_attempts']==1 and g['context_close_status']==0, 'context open/close')
    else:
        need(g['context_open_attempts']==0 and g['context_close_attempts']==0 and g['context_open_status']==-2147483648 and g['context_close_status']==-2147483648, 'unexpected context operation')
    need(g['association_probe_enabled'] is attach, 'association setting')
    if probe:need(g['metal_registry_matches'] is True,'Metal identity')
    if attach:
        need(g['shared_open_attempts']==1 and g['shared_open_status']==0 and g['shared_close_attempts']==1 and g['shared_close_status']==0 and g['connections_distinct'] is True and g['association_attempts']==1 and g['association_status']==0,'association result')
    else:
        need(g['shared_open_attempts']==0 and g['shared_close_attempts']==0 and g['association_attempts']==0 and g['shared_open_status']==-2147483648 and g['shared_close_status']==-2147483648 and g['association_status']==-2147483648,'unexpected shared operation')
    o = g['argument_observation']
    if route == 'enabled':
        need(g['gate_calls'] == 1 and o['ready'] and o['caller_offset'] == 0x24d16, 'gate/caller')
        for name in ('caller_pinned','caller_path_matches','caller_UUID_matches','config_header_20_read',
                     'display_array_region_readable','selected_index_in_mask','selected_index_in_range',
                     'selected_display_value_nonzero','selected_port_send_right','selected_service_class_ok',
                     'selected_service_registry_ok','region_is_not_allocation_size_proof'):
            need(o[name] is True, 'observation: ' + name)
        need((o['config_first_word'],o['display_mask'],o['display_array_required_count']) == (0,15,4), 'header')
        need(o['selected_service_class'] == 'nvAccelerator' and o['selected_service_registry_ID'] == GPU_ID, 'service identity')
        events = [e for e in g['events'] if e['name'] == 'AVD_CreateAVDAccelerator']
        need(len(events) == 1 and events[0]['identity_pin'] and events[0]['result_replaced'], 'lookup')
    else:
        need(g['gate_calls'] == 0 and not o['ready'], 'unexpected gate')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--hosts',type=Path,nargs=6,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    b=a.build.resolve();need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.hosts))==6,'fresh output/distinct hosts')
    need(sha(b/'inputs.json')==BUILD_SHA,'build identity');i=read(b/'inputs.json')
    for name,h in i['frozen'].items():need(sha(b/name)==h,'frozen '+name)
    for name in ('coordinator.py','video_provider_fields_observer.mm','video_provider_gate_main.mm','video_provider_lookup_client.mm'):
        need(sha(HERE/name)==i['frozen']['src/'+name],'source '+name)
    need(i['GPU_registry_ID']==GPU_ID and not i['build_executes_provider'],'profile')
    imports=subprocess.run(['nm','-u',str(b/'libLookupObserver.dylib')],capture_output=True,text=True,check=True).stdout
    need('_IOServiceOpen' in imports and '_IOServiceClose' in imports and '_IOConnectAddClient' in imports and '_MTLCreateSystemDefaultDevice' in imports and '_IOConnectCall' not in imports,'gate imports')
    rows=[]; intervals=[];pids=set()
    for d,(label,mode,route,probe,attach) in zip(a.hosts,CASES):
        d=d.resolve();inp=read(d/'inputs.json');m=read(d/'execution/manifest.json');lease=m['GPU_reservation'];g=read(d/'provider-gate.json');x=read(d/'result.json')
        need(inp['build_manifest_SHA256']==BUILD_SHA and inp['mode']==mode and inp['route']==route and inp['probe'] is probe and inp['attach'] is attach,'case inputs')
        for name,h in inp['assets_SHA256'].items():need(sha(d/'assets'/name)==h,'asset '+name)
        need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and not lease['known_signed_processes_live'],'lease')
        need(m['pid'] not in pids,'reused pid');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
        need(sha(d/'application')==m['original_binary_sha256']==i['frozen']['application'] and sha(d/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'application')
        subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],capture_output=True,check=True)
        need(g==read(d/'outputs/provider-gate.json') and x==read(d/'execution/execution.stdout'),'output mismatch');check_gate(g,route,probe,attach)
        if mode=='hardware':
            v=x['public_decode'];need(v['decode']['specification']['RequireHardwareAcceleratedVideoDecoder'] is True and v['decode']['create_status']==-12913 and v['output_frames']==0,'hardware result')
        if mode=='cpu':
            v=x['public_decode'];need(v['decode']['create_status']==0 and v['output_frames']==6 and v['different_bytes']==0,'CPU result')
            for k in range(6):
                actual=(d/'outputs'/f'vt-frame-{k:03d}.nv12').read_bytes();expected=(d/'assets/fixtures/H264'/f'cpu-frame-{k:03d}.nv12').read_bytes();need(actual==expected and len(actual)==460800,'CPU bytes')
        rows.append({'case':label,'mode':mode,'route':route,'probe':probe,'attach':attach,'gate_calls':g['gate_calls'],'gate_SHA256':sha(d/'provider-gate.json')})
    intervals.sort();need(all(a<=b for a,b in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'overlapping hosts')
    out={'status':'PASS','terminal_nonoverlapping_processes':6,'selected_service_observations':3,'context_open_close_successes':3,'shared_client_association_successes':2,'selected_service_class':'nvAccelerator','selected_registry_ID':GPU_ID,'hardware_failures':4,'hardware_images':0,'software_images':6,'software_CPU_reference_bytes':2764800,'build_manifest_SHA256':BUILD_SHA,'cases':rows,'hardware_video_execution_proved':False,'sierra_provider_executed_by_gate':False,'scope':'Own-process legacy AppleGVA counterfactual; public context/shared-client association, no video selector or decode.'}
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
