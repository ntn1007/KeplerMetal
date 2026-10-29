#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit serialized public VideoToolbox observations on the pinned iMac."""
import argparse
import datetime
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from experiment import EXPECTED, REFERENCE, SOURCE, SYSTEM

HERE=Path(__file__).resolve().parent
MODES=('software-plain','software-observed','hardware-plain','hardware-observed','metal-plain','metal-observed')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok: raise ValueError(why)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True); p.add_argument('--runs',type=Path,nargs=12,required=True)
    p.add_argument('--m1-audit',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    b=json.loads((a.build/'build.json').read_text())
    need(b['status']=='PREPARED' and not b['gpu_execution'] and b['system']==SYSTEM and
         b['builder_sha256']==sha(HERE/'experiment.py') and b['source_sha256']=={n:sha(v) for n,v in SOURCE.items()} and
         b['build_sha256']=={n:sha(a.build/n) for n in ('client','observer.dylib')} and
         b['fixture']==EXPECTED=={n:sha(a.build/'fixture'/n) for n in EXPECTED} and
         b['reference']==REFERENCE==sha(a.build/'reference.nv12'),'build/fixture differs')
    need({path:sha(path) for path in SYSTEM}==SYSTEM,'current profile differs')
    kernel_files={
        '/System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2':'37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8',
        '/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce':'44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'}
    need({name:sha(name) for name in kernel_files}==kernel_files and platform.machine()=='x86_64','audit-time kernel profile differs')
    gpu=json.loads(subprocess.check_output(['system_profiler','SPDisplaysDataType','-json'],timeout=60))['SPDisplaysDataType']
    need(len(gpu)==1 and gpu[0].get('spdisplays_device-id')=='0x1198' and
         gpu[0].get('spdisplays_vendor')=='sppci_vendor_Nvidia' and gpu[0].get('spdisplays_vram')=='8 GB','audit-time display profile differs')
    os_version=subprocess.check_output(['sw_vers','-productVersion'],text=True,timeout=10).strip()
    os_build=subprocess.check_output(['sw_vers','-buildVersion'],text=True,timeout=10).strip()
    m1=json.loads(a.m1_audit.read_text())
    need(m1['status']=='PASS_TWO_REFERENCE_COHORTS' and m1['frames']==48 and
         m1['reference_sha256']==REFERENCE and m1['differing_bytes']==0 and
         m1['hardware_sessions_report_acceleration']==4,'M1 reference differs')
    reference=(a.build/'reference.nv12').read_bytes(); need(len(reference)==691200,'reference length differs')
    rows=[]; intervals=[]; pids=set(); reservations=set(); counts={n:0 for n in MODES}
    for path in a.runs:
        manifest=json.loads((path/'manifest.json').read_text()); raw=json.loads((path/'stdout.json').read_text())
        reservation=manifest['reservation']; mode=manifest['mode']; need(mode in MODES,'unexpected mode')
        counts[mode]+=1
        need(manifest['status']=='TERMINAL' and manifest['exit_code']==0 and manifest['system_before']==SYSTEM and
            manifest['system_after']==SYSTEM and not manifest['system_modified'] and
            manifest['runner_sha256']==sha(HERE/'experiment.py') and manifest['build_sha256']==sha(a.build/'build.json') and
            manifest['stdout_sha256']==sha(path/'stdout.json') and manifest['stderr_sha256']==sha(path/'stderr.log') and
            not (path/'stderr.log').read_bytes(),'manifest differs')
        need(reservation['state']=='terminal' and reservation['exit_code']==0 and not reservation['SIGKILL_requested'] and
            not reservation['authoritative_ps_status'] and reservation['bootstrap_process_table_checked'] and
            reservation['child_birth_observed'] and reservation['child_PID']==manifest['pid'] and
            reservation['signed_binary_sha256']==manifest['host_sha256']==b['build_sha256']['client'] and
            manifest['observer_sha256']==b['build_sha256']['observer.dylib'],'reservation/identity differs')
        need(manifest['pid'] not in pids and reservation['reservation_id'] not in reservations,'duplicate process/reservation')
        pids.add(manifest['pid']); reservations.add(reservation['reservation_id'])
        for name in ('client','observer.dylib'):
            need(sha(path/name)==b['build_sha256'][name],'copied binary differs')
            sign=subprocess.run(['codesign','--verify','--strict',str(path/name)],capture_output=True,timeout=30)
            need(sign.returncode==0,'signature differs')
        start=datetime.datetime.fromisoformat(manifest['started_at']); end=datetime.datetime.fromisoformat(manifest['completed_at'])
        need(start<end,'process interval differs'); intervals.append((start,end))
        observed=mode.endswith('observed'); hardware=mode.startswith('hardware'); metal=mode.startswith('metal')
        expected_mode='hardware' if hardware else ('metal' if metal else 'software')
        need(raw['mode']==expected_mode and raw['observer_loaded']==observed and raw['unique_nvidia_pci_target'] and
             raw['explicit_gpu_dispatches']==0,'observer or target differs')
        if hardware:
            need(raw['status']=='CREATE_FAILED' and raw['create_status']==-12906 and raw['frames']==raw['bytes']==0 and
                 raw['decode_statuses']==[] and raw['hardware_property'] is None and raw['hardware_property_status'] is None and
                 not (path/'decoded.nv12').exists(),'hardware result differs')
        elif metal:
            need(raw['status']=='METAL_PASS' and raw['create_status']==0 and raw['frames']==raw['bytes']==0 and
                 raw['decode_statuses']==[] and not (path/'decoded.nv12').exists(),'Metal control differs')
        else:
            need(raw['status']=='PASS' and raw['create_status']==0 and raw['frames']==6 and raw['bytes']==len(reference) and
                 raw['decode_statuses']==[0]*6 and raw['hardware_property_status']==-12900 and raw['hardware_property'] is None and
                 (path/'decoded.nv12').read_bytes()==reference,'software result differs')
        if observed:
            x=raw['observation']; need(isinstance(x,dict) and x['return_unchanged'] and x['config_calls']==0 and
                x['config_status']==-1 and x['config_values_match_object']==0 and x['config_failures']==0 and
                x['type_or_profile_failures']==0 and x['registry_query_failures']==0 and x['shared_failures']==0,
                'object observer safety differs')
            names=('create_calls','matching_nonnull','matching_type','shared_calls','shared_matching_argument',
                   'shared_nonnull','shared_type_matches','shared_stored_device_matches')
            expected=0 if mode.startswith('software') else 1
            need(all(x[n]==expected for n in names),'device/shared object observation differs')
        else: need(raw['observation'] is None,'plain observer data differs')
        rows.append({'mode':mode,'manifest_sha256':sha(path/'manifest.json'),'stdout_sha256':sha(path/'stdout.json'),
                     'create_status':raw['create_status'],'frames':raw['frames'],'observation':raw['observation']})
    need(all(counts[x]==2 for x in MODES),'mode count differs')
    intervals.sort(); need(all(intervals[i-1][1]<=intervals[i][0] for i in range(1,len(intervals))),'process overlap')
    record={'status':'PASS_VT_DEVICE_SHARED_OBJECTS','processes':12,'software_processes':4,'metal_control_processes':4,
        'software_frames':24,'software_bytes_compared':24*115200,'hardware_required_processes':4,
        'hardware_create_statuses':[-12906]*4,'hardware_frames':0,'observed_hardware_processes':2,
        'hardware_device_shared_matches':2,'metal_device_shared_matches':2,'software_device_shared_matches':0,
        'system_profile_files':len(SYSTEM),'reference_sha256':REFERENCE,'m1_audit_sha256':sha(a.m1_audit),
        'audit_time_macos_version':os_version,'audit_time_macos_build':os_build,
        'audit_time_pci_device':'10de:1198','audit_time_reported_vram':'8 GB',
        'audit_time_kernel_file_sha256':kernel_files,
        'm1_hardware_sessions_report_acceleration':4,'build_sha256':sha(a.build/'build.json'),
        'source_sha256':{n:sha(v) for n,v in SOURCE.items()},'audit_sha256':sha(Path(__file__)),
        'intervals_nonoverlapping':True,'rows':rows,'observation_process_local_only':True,
        'other_processes_observed':False,'live_kernel_method_dispatch_proved':False,
        'hardware_video_execution_proved':False,'system_modified':False}
    a.out.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':record['status'],'software_frames':record['software_frames'],'hardware_frames':0}))
if __name__=='__main__':main()
