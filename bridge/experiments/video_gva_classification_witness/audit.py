#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit calibrated, scoped AppleGVA classification witnesses."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'video_gva_renderer_filter'))
from audit import REGION_SHA, WINDOWS, classify
sys.path.insert(0,str(HERE.parent/'video_gva_property_link_witness'))
from reserved_cpu import terminal_pid

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def need(v,m):
    if not v:raise ValueError(m)
def signature(path):need(subprocess.run(['codesign','--verify','--strict',str(path)],capture_output=True).returncode==0,'signature: '+str(path))
def hits(log):
    pattern=r'^KP_CLASS_HIT name=(classify|skip|after_enumeration) bytes_match=(\d+) thread=(\d+) caller_offset=(\d+) kind_valid=(\d+) kind=(\d+) flags_valid=(\d+) flags=(\d+),(\d+),(\d+),(\d+) same_prior=(\d+) field_valid=(\d+) field=(\d+)$'
    return [(name,*(int(x) for x in values)) for name,*values in re.findall(pattern,log,re.M)]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','build','calibration','reserved-control','region','prior-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=6,required=True,help='cpu, off, synthetic1, synthetic2, wrong, no-witness')
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==6,'fresh output and distinct runs required')
    base=load(a.base/'inputs.json');build=load(a.build/'build.json');cal=load(a.calibration/'calibration.json');control=load(a.reserved_control/'manifest.json')
    prior=load(a.prior_audit);region=a.region.read_bytes()
    need(sha(a.region)==REGION_SHA and len(region)==1136 and prior['status']=='PASS_STATIC_FILTER_AND_RECORDED_SNAPSHOTS' and prior['source_region_sha256']==REGION_SHA,'static capture or prior audit differs')
    for (start,end),wanted in WINDOWS.items():need(hashlib.sha256(region[start:end]).hexdigest()==wanted,'static instruction window differs')
    need(classify(17039368)=='excluded','classifier differs')
    need(build['status']=='PREPARED_ONLY' and build['base_inputs_sha256']==sha(a.base/'inputs.json') and build['calibration_sha256']==sha(a.calibration/'calibration.json') and build['reserved_control_sha256']==sha(a.reserved_control/'manifest.json'),'build provenance')
    for name,digest in base['frozen'].items():need(sha(a.base/name)==digest,'base: '+name)
    for name,digest in build['frozen'].items():need(sha(a.build/name)==digest,'build: '+name)
    for name,digest in cal['source_sha256'].items():need(sha(a.calibration/name)==sha(HERE/name)==digest,'calibration source: '+name)
    for name in ('marker.S','gva_marker.cpp','lldb_witness.py','lldb_guard.py'):need(sha(a.build/name)==sha(HERE/name),'build source: '+name)
    need(cal['status']=='PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION' and cal['excluded_skip_same_node'] and cal['accepted_skip_absent'] and cal['bad_base_refused'] and cal['output_field']==7 and not cal['GPU_execution'],'calibration status')
    for name,digest in cal['logs'].items():need(sha(a.calibration/(name+'.stdout'))==digest,'calibration log: '+name)
    need(sha(a.calibration/'host')==cal['host_sha256'] and sha(a.calibration/'marker.dylib')==cal['library_sha256'],'calibration binaries')
    need(control['status']=='PASS_RESERVED_DEBUGGER_CPU' and control['reservation']['state']=='terminal' and control['debugger_and_target_absent_from_process_table'] and control['log_sha256']==sha(a.reserved_control/'lldb.log') and control['guard_sha256']==sha(HERE/'lldb_guard.py') and control['calibration_sha256']==sha(a.calibration/'calibration.json'),'reserved control')
    for path in (a.calibration/'host',a.calibration/'marker.dylib',a.build/'marker.dylib',a.base/'libObserver.dylib'):signature(path)
    expected=[('cpu','on','off',0,6),('current','on','off',-12913,0),('current','on','synthetic',-12913,0),('current','on','synthetic',-12913,0),('wrong','on','off',-12906,0),('current','off','off',-12913,0)]
    rows=[]
    for root,(mode,witness,probe,status,frames) in zip(a.runs,expected):
        m=load(root/'manifest.json');report=load(root/'stdout.json');log=(root/'lldb.log').read_text();err=(root/'stderr.log').read_text();reservation=m['reservation']
        need((m['mode'],m['witness'],m['probe'],m['decoder_status'],m['output_frames'])==(mode,witness,probe,status,frames),'run mode or result')
        need(m['status']=='TERMINAL_SCOPED_DEBUGGER' and m['target_exit_code']==m['debugger_exit_code']==0 and m['target_and_debugger_absent'] and terminal_pid(log)==m['target_pid'],'terminal outcome')
        need(reservation['state']=='terminal' and reservation['child_PID']==m['debugger_pid'] and reservation['exit_code']==0 and not reservation['SIGKILL_requested'] and not reservation['authoritative_ps_status'],'reservation')
        need(m['build_sha256']==sha(a.build/'build.json') and m['runner_sha256']==sha(HERE/'run_gva.py') and m['host_sha256']==sha(root/'application')==build['frozen']['application'],'run provenance');signature(root/'application')
        for name,field in [('stdout.json','stdout_sha256'),('stderr.log','stderr_sha256'),('lldb.log','lldb_log_sha256')]:need(sha(root/name)==m[field],'run log: '+name)
        need(report['status']=='OBSERVATION_COMPLETED' and report['codec']=='H264' and not report['hardware_video_execution_proved'] and not m['hardware_video_execution_proved'] and not m['system_modified'],'report status')
        dec=report['public_decode'];need(dec['output_frames']==frames and dec['decode']['create_status']==status,'decode')
        changes={'assets/owned-choice.json','assets/dependency-choice.json','assets/factory-policy-choice.json'}
        for name,digest in base['frozen'].items():
            if name.startswith('assets/') and name not in changes:need(sha(root/name)==digest,'asset: '+name)
        need(load(root/'assets/owned-choice.json')=={'route':'owned'} and load(root/'assets/dependency-choice.json')=={'mode':'native' if mode=='cpu' else 'present-key'} and load(root/'assets/factory-policy-choice.json')=={'mode':'observe' if mode=='cpu' else 'wrong-board' if mode=='wrong' else 'current-board'},'choices')
        found=hits(log);need(not any(x in log for x in ('KP_GUARD_NO_PROCESS','KP_GUARD_UNRESOLVED','KP_HW_ARM_FAIL','KP_HW_HIT_FAIL')),'debugger failure')
        if mode=='cpu':
            need(not found and dec['different_bytes']==0 and dec['missing_CPU_references']==0 and dec['CPU_reference_bytes_compared']==691200,'CPU decode');
            for i in range(6):
                image=root/'outputs'/f'vt-frame-{i:03}.nv12';reference=root/'assets/fixtures/H264'/f'cpu-frame-{i:03}.nv12'
                need(image.stat().st_size==115200 and sha(image)==sha(reference),'CPU frame')
        elif mode=='current' and witness=='on':
            synthetic=probe=='synthetic';need(err.count('KM_CODEC_PROBE original_null=1 injected=%d profile=1'%synthetic)==1 and log.count('KP_HW_ARM_PASS mode=gva')==1,'property mode or marker')
            want=['classify','skip','classify','skip','after_enumeration'] if synthetic else ['skip','skip','after_enumeration']
            need([x[0] for x in found]==want and len({x[2] for x in found})==1 and all(x[1]==1 for x in found),'witness sequence')
            for hit in found[:-1]:
                name,_,_,caller,valid,kind,flagsvalid,f0,f1,f2,f3,same,_,_=hit
                need(caller in (147562,146279) and valid==flagsvalid==1 and kind==17039368 and (f0,f1,f2,f3)==(1,0,0,int(synthetic)) and same==int(synthetic and name=='skip'),'node fields')
            need([x[3] for x in found[:-1]]==([147562,147562,146279,146279] if synthetic else [147562,146279]),'caller sequence')
            need(found[-1][3]==264163 and found[-1][-2:]==(1,0),'enumeration output')
        else:
            need(not found and ('KP_HW_ARM_PASS mode=gva' in log)==(mode=='wrong' and witness=='on'),'unexpected control witness')
        rows.append({'mode':mode,'witness':witness,'probe':probe,'decoder_status':status,'output_frames':frames,'witness_hits':len(found),'manifest_sha256':sha(root/'manifest.json'),'lldb_log_sha256':sha(root/'lldb.log')})
    receipt={'status':'PASS_BOUNDED_CLASSIFICATION_WITNESS','prior_static_audit_sha256':sha(a.prior_audit),'source_region_sha256':sha(a.region),'calibration_sha256':sha(a.calibration/'calibration.json'),'reserved_control_sha256':sha(a.reserved_control/'manifest.json'),'build_sha256':sha(a.build/'build.json'),'runs':rows,'synthetic_runs':2,'classification_then_same_pointer_skip_per_run':2,'observed_field':'0x01040008','hardware_decoder_status':-12913,'hardware_frames':0,'node_allocation_lifetime_proved':False,'individual_machine_branches_stepped':False,'full_failure_cause_identified':False,'hardware_video_execution_proved':False,'system_modified':False}
    with a.out.open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':receipt['status'],'synthetic_runs':2,'hardware_video_execution_proved':False}))
if __name__=='__main__':main()
