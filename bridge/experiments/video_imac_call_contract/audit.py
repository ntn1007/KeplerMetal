#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit serialized public VideoToolbox observations on the pinned iMac."""
import argparse
import datetime
import hashlib
import json
import platform
import re
import struct
import sys
import subprocess
from pathlib import Path
from experiment import EXPECTED, REFERENCE, SOURCE, SYSTEM

HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from inspect_video_cache import Cache, image_map, inspect, stub_symbol
MODES=('software-plain','software-observed','hardware-plain','hardware-observed')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok: raise ValueError(why)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True); p.add_argument('--runs',type=Path,nargs=8,required=True)
    p.add_argument('--m1-audit',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cache',type=Path,required=True); p.add_argument('--device-capture',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True); p.add_argument('--calibration',type=Path,required=True)
    a=p.parse_args(); need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    need(not a.work.exists() and a.work.parent.is_dir(),'fresh private work directory required')
    image='/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator'
    cache=Cache(a.cache.resolve()); maps=image_map(a.cache.with_name(a.cache.name+'.map'),image)
    img,starts=inspect(cache,maps[0]['start'],image)
    expected='392ef70adb9a4175266bb9b29611428f4cb00ab1a8a518ce59e950ffa915294a'
    metadata=json.loads((a.device_capture/'metadata.json').read_text()); region=metadata['region']
    binary=(a.device_capture/'function-region.private.bin').read_bytes()
    start=0x7ff80f88df60; site=0x7ff80f88dffd; fallthrough=site+5; overwritten=0x7ff80f88e009
    need(img['UUID']=='198a776afe0335ee8e537b9f14caabaa' and metadata['status']=='PASS' and
         metadata['image']['UUID']==img['UUID'] and region['start_VM']==start and start in starts and
         region['bytes']==len(binary)==685 and region['SHA256']==expected and sha(a.device_capture/'function-region.private.bin')==expected and
         cache.read(start,len(binary))==binary,'device constructor capture differs')
    pos=site-start; need(binary[pos]==0xe8,'constructor call instruction differs')
    target=site+5+struct.unpack_from('<i',binary,pos+1)[0]
    binding=stub_symbol(cache,img,target)
    need(target==0x7ff80f89476a and binding and binding.get('static_symbol')=='_IOConnectCallStructMethod',
         'constructor import differs')
    a.work.mkdir(); obj=a.work/'device.private.o'
    command=['python3',str(BRIDGE/'tools/video_region_analysis_object.py'),'--metadata',str(a.device_capture/'metadata.json'),'--out',str(obj)]
    build=subprocess.run(command,capture_output=True,timeout=60); need(build.returncode==0,'private analysis object failed')
    dis=subprocess.run(['xcrun','llvm-objdump','-d','--x86-asm-syntax=intel',str(obj)],capture_output=True,text=True,timeout=60)
    need(dis.returncode==0,'private disassembly failed'); (a.work/'disassembly.private.txt').write_text(dis.stdout)
    need(re.search(r'7ff80f88e002:\s+(?:[0-9a-f]{2}\s+)+mov\s+r15d, dword ptr \[rbp - 0x284\]',dis.stdout) and
         re.search(r'7ff80f88e009:\s+(?:[0-9a-f]{2}\s+)+mov\s+rax, qword ptr \[rip',dis.stdout),
         'post-call instructions differ')
    b=json.loads((a.build/'build.json').read_text())
    need(b['status']=='PREPARED' and not b['gpu_execution'] and b['system']==SYSTEM and
         b['builder_sha256']==sha(HERE/'experiment.py') and b['source_sha256']=={n:sha(v) for n,v in SOURCE.items()} and
         b['build_sha256']=={n:sha(a.build/n) for n in ('client','observer.dylib')} and
         b['fixture']==EXPECTED=={n:sha(a.build/'fixture'/n) for n in EXPECTED} and
         b['reference']==REFERENCE==sha(a.build/'reference.nv12'),'build/fixture differs')
    cal=json.loads((a.calibration/'validation.json').read_text())
    calraw=json.loads((a.calibration/'test.stdout').read_text())
    need(cal['status']=='PASS_NULL_PORT_CALIBRATION' and cal['cases']==3 and cal['null_port_only'] and
         not cal['gpu_connection_opened'] and cal['build_sha256']==sha(a.build/'build.json') and
         cal['observer_sha256']==b['build_sha256']['observer.dylib']==sha(a.calibration/'observer.dylib') and
         cal['host_sha256']==sha(a.calibration/'calibration') and cal['calibration_source_sha256']==sha(HERE/'calibration.c') and
         cal['runner_sha256']==sha(HERE/'calibrate.py') and calraw['status']=='PASS' and calraw['cases']==3 and
         calraw['null_port_only'] and calraw['returned_statuses']==cal['returned_statuses'] and
         not (a.calibration/'test.stderr').read_bytes(),'calibration differs')
    for name in ('calibration','observer.dylib'):
        sign=subprocess.run(['codesign','--verify','--strict',str(a.calibration/name)],capture_output=True,timeout=30)
        need(sign.returncode==0,'calibration signature differs')
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
        observed=mode.endswith('observed'); hardware=mode.startswith('hardware')
        need(raw['mode']==('hardware' if hardware else 'software') and raw['observer_loaded']==observed and
             raw['observer_calibrated']==observed and raw['dropped_events']==0,'observer differs')
        if hardware:
            need(raw['status']=='CREATE_FAILED' and raw['create_status']==-12906 and raw['frames']==raw['bytes']==0 and
                 raw['decode_statuses']==[] and raw['hardware_property'] is None and raw['hardware_property_status'] is None and
                 not (path/'decoded.nv12').exists(),'hardware result differs')
        else:
            need(raw['status']=='PASS' and raw['create_status']==0 and raw['frames']==6 and raw['bytes']==len(reference) and
                 raw['decode_statuses']==[0]*6 and raw['hardware_property_status']==-12900 and raw['hardware_property'] is None and
                 (path/'decoded.nv12').read_bytes()==reference,'software result differs')
        services=raw['services']; events=raw['detail_events']
        if observed:
            need(len(events)==sum(raw['observed_counts'][1:]) and all(e['service'] is None or 0<=e['service']<len(services) for e in events),
                 'event identities differ')
            if hardware:
                need(raw['observed_counts']==[3,3,6,0] and [(s['class'],s['type']) for s in services]==
                     [('IOSurfaceRoot',0),('nvAccelerator',5),('nvAccelerator',6)],'hardware service observations differ')
                typed=[(e['kind'],e['selector'],services[e['service']]['type']) for e in events if e['service'] is not None and
                       services[e['service']]['class']=='nvAccelerator']
                need(typed==[(2,9,5),(2,2,5),(2,0,5),(2,7,5),(2,9,6),(2,10,6)],'NVIDIA call observation differs')
                scoped=[e for e in events if e['service'] is not None and services[e['service']]['class']=='nvAccelerator']
                expected_calls=[(9,1,16,None,None,0x1002,'IOAccelDeviceCreateWithAPIProperty'),
                  (2,0,0,600,600,0x1074,'IOAccelDeviceCreateWithAPIProperty'),
                  (0,0,0,64,64,0x113f,'IOAccelDeviceCreateWithAPIProperty'),
                  (7,0,0,24,24,0x11aa,'IOAccelDeviceCreateWithAPIProperty'),
                  (9,0,0,16,16,0x14dd,'IOAccelSharedCreate'),
                  (10,0,0,24,24,0x1f42,'IOAccelSharedSetupDirtyRing')]
                got=[(e['selector'],e['status'],e['input_struct'],e['struct_capacity'],e['struct_returned'],
                      e['caller_offset'],e['caller_symbol']) for e in scoped]
                need(got==expected_calls and all(e['caller_image']=='IOAccelerator' and e['input_scalars']==0 and
                     e['scalar_capacity'] is None and e['scalar_returned'] is None for e in scoped),'call contract differs')
                need([e['ticket'] for e in scoped]==sorted(e['ticket'] for e in scoped),'entry order differs')
            else:
                need(raw['observed_counts']==[1,22,0,0] and [(s['class'],s['type']) for s in services]==[('IOSurfaceRoot',0)],
                     'software service observations differ')
        else: need(raw['observed_counts']==[0,0,0,0] and not services and not events,'plain observer data differs')
        rows.append({'mode':mode,'manifest_sha256':sha(path/'manifest.json'),'stdout_sha256':sha(path/'stdout.json'),
                     'create_status':raw['create_status'],'frames':raw['frames'],'observed_counts':raw['observed_counts'],
                     'services':services,'detail_events':events})
    need(all(counts[x]==2 for x in MODES),'mode count differs')
    intervals.sort(); need(all(intervals[i-1][1]<=intervals[i][0] for i in range(1,len(intervals))),'process overlap')
    record={'status':'PASS_IMAC_VT_CALL_CONTRACT','processes':8,'software_processes':4,
        'software_frames':24,'software_bytes_compared':24*115200,'hardware_required_processes':4,
        'hardware_create_statuses':[-12906]*4,'hardware_frames':0,'observed_hardware_processes':2,
        'system_profile_files':len(SYSTEM),'reference_sha256':REFERENCE,'m1_audit_sha256':sha(a.m1_audit),
        'audit_time_macos_version':os_version,'audit_time_macos_build':os_build,
        'audit_time_pci_device':'10de:1198','audit_time_reported_vram':'8 GB',
        'audit_time_kernel_file_sha256':kernel_files,
        'ioaccelerator_image_uuid':img['UUID'],'device_function_sha256':expected,
        'device_callsite_image_offset':'0xffd','return_address_image_offset':'0x1002',
        'post_call_eax_overwritten_before_test_static':True,'loaded_device_code_hash_observed':False,
        'm1_hardware_sessions_report_acceleration':4,'build_sha256':sha(a.build/'build.json'),
        'calibration_receipt_sha256':sha(a.calibration/'validation.json'),'calibration_cases':3,
        'source_sha256':{n:sha(v) for n,v in SOURCE.items()},'audit_sha256':sha(Path(__file__)),
        'intervals_nonoverlapping':True,'rows':rows,'observation_process_local_only':True,
        'other_processes_observed':False,'live_kernel_method_dispatch_proved':False,
        'hardware_video_execution_proved':False,'system_modified':False}
    a.out.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':record['status'],'software_frames':record['software_frames'],'hardware_frames':0}))
if __name__=='__main__':main()
