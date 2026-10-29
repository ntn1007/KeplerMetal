#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit one pinned AppleGVA free callsite and five three-session runs."""
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(ok,msg):
    if not ok:raise ValueError(msg)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','build','calibration','reserved-control','region','mapping','out'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--runs',required=True,nargs=5,type=Path);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    b=read(a.build/'build.json');c=read(a.calibration/'calibration.json');r=read(a.reserved_control/'manifest.json')
    region=a.region.read_bytes();mapping=read(a.mapping)
    need(sha(a.region)=='f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19' and
         sha(a.mapping)=='2d9c4ed04bcdbdd4049bb7ed88f0a545d3f42b1b478ab320e43fc8feb6a39ffd' and
         region[150961-148746:150969-148746]==bytes.fromhex('4c89f7e8b3120a00') and
         mapping['status']=='STATIC_ONLY' and not mapping['runtime_target_proved'], 'static free call differs')
    matches=[x for x in mapping['rows'] if x['caller_offset']==150964]
    need(len(matches)==1 and '_free' in matches[0]['exact_defined_symbols'], 'free call mapping differs')
    need(b['request_window_variant'] and b['base_inputs_sha256']==sha(a.base/'inputs.json') and
         b['calibration_sha256']==sha(a.calibration/'calibration.json') and b['reserved_control_sha256']==sha(a.reserved_control/'manifest.json') and
         c['status']=='PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION' and c['request_windows_1_2_3_calibrated'] and c['active_arm_calibrated'] and c['free_candidate_match_and_mismatch_calibrated'] and
         c['windows_log_sha256']==sha(a.calibration/'windows.stdout') and c['active_arm_log_sha256']==sha(a.calibration/'armactive.stdout') and
         r['status']=='PASS_RESERVED_DEBUGGER_CPU' and r['reservation']['state']=='terminal' and r['debugger_and_target_absent_from_process_table'] and
         r['calibration_sha256']==sha(a.calibration/'calibration.json') and r['log_sha256']==sha(a.reserved_control/'lldb.log'), 'prerequisites differ')
    for n,h in c['source_sha256'].items():need(sha(HERE/n)==sha(a.calibration/n)==h,'calibration source differs')
    for n,h in b['frozen'].items():need(sha(a.build/n)==h,'build differs')
    for n in ('marker.S','gva_marker.cpp','lldb_witness.py','lldb_guard.py'):need(sha(HERE/n)==sha(a.build/n),'witness source differs')
    need(re.search(r'^KP_NODE_FREE_CANDIDATE thread=[0-9]+ request_window=1 compared=1 matches=1$',(a.calibration/'positive.stdout').read_text(),re.M) and
         re.search(r'^KP_NODE_FREE_CANDIDATE thread=[0-9]+ request_window=1 compared=1 matches=0$',(a.calibration/'different.stdout').read_text(),re.M) and
         c['positive_log_sha256']==sha(a.calibration/'positive.stdout') and c['different_log_sha256']==sha(a.calibration/'different.stdout'), 'node comparison calibration differs')
    windows=re.findall(r'^KP_REQUEST_HIT name=(property_return|list_entry|after_enumeration) thread=[0-9]+ request_window=([0-3])$',(a.calibration/'windows.stdout').read_text(),re.M)
    need(windows==[(n,str(i)) for i in (1,2,3) for n in ('property_return','list_entry','after_enumeration')], 'calibration markers differ')
    modes=[('cpu','on',0),('wrong','on',-12906),('current','off',-12913),('current','on',-12913),('current','on',-12913)]
    summaries=[]
    for root,(mode,witness,status) in zip(a.runs,modes):
        m=read(root/'manifest.json');report=read(root/'stdout.json');err=(root/'stderr.log').read_text();log=(root/'lldb.log').read_text()
        need(m['status']=='TERMINAL_SCOPED_DEBUGGER' and m['mode']==mode and m['witness']==witness and
             m['target_exit_code']==m['debugger_exit_code']==0 and m['target_and_debugger_absent'] and
             m['reservation']['state']=='terminal' and not m['reservation']['SIGKILL_requested'] and
             not m['reservation']['authoritative_ps_status'] and m['build_sha256']==sha(a.build/'build.json') and
             m['host_sha256']==sha(root/'application')==b['frozen']['application'] and
             m['lldb_log_sha256']==sha(root/'lldb.log') and m['stderr_sha256']==sha(root/'stderr.log') and
             m['stdout_sha256']==sha(root/'stdout.json'), 'run provenance differs')
        need(report['status']=='OBSERVATION_COMPLETED' and len(report['additional_public_decodes'])==2 and
             re.findall(r'^KP_REPEAT_(BEGIN|END) request=(\d+)$',err,re.M)==[(x,str(i)) for i in (1,2,3) for x in ('BEGIN','END')], 'request shape differs')
        decodes=[report['public_decode'],*report['additional_public_decodes']]
        for i,d in enumerate(decodes):
            need(d is not None and d['decode']['create_status']==status and d['output_frames']==(6 if mode=='cpu' else 0),'decode result differs')
            if mode=='cpu':
                need(d['different_bytes']==0 and d['CPU_reference_bytes_compared']==691200,'CPU comparison differs')
                folder=root/'outputs' if i==0 else root/'outputs'/('repeat-%d'%(i+1))
                for k in range(6):
                    source=root/'assets/fixtures/H264'/('cpu-frame-%03d.nv12'%k);actual=folder/('vt-frame-%03d.nv12'%k)
                    need(source.stat().st_size==115200 and sha(source)==sha(actual),'frame differs')
            dep=read(root/'outputs'/('dependency.json' if i==0 else 'dependency-%d.json'%(i+1)))
            met=read((root/'outputs' if i==0 else root/'outputs'/('repeat-%d'%(i+1)))/'metadata.json')
            need(dep['status']=='COMPLETE' and dep['recorders_drained'] and not dep['pending'] and not dep['dropped'] and
                 dep['public_query_controls_valid'] and dep['public_create_called'] and dep['create_status']==status and
                 met['status']=='COMPLETE' and met['recorders_drained'] and not met['pending'] and not met['dropped'] and
                 met['public_retain_control_valid'], 'observer record differs')
        hits=re.findall(r'^KP_REQUEST_HIT name=(\w+) thread=(\d+) request_window=(\d+)$',log,re.M)
        if mode=='current' and witness=='on':
            expected=[('property_return','1'),('list_entry','1'),('list_entry','1'),('list_entry','2'),('list_entry','3')]
            need([(name,window) for name,thread,window in hits]==expected and 'KP_REQUEST_ARM window=1' in log and
                 'KP_HW_ARM_FAIL' not in log and 'KP_HW_HIT_FAIL' not in log and 'KP_NODE_FREE_CANDIDATE ' not in log and
                 re.search(r'4\.1: .*resolved, hardware, hit count = 0',log), 'current witness differs')
        if mode=='wrong':need('KP_HW_ARM_PASS mode=gva' in log and not hits,'wrong-board control differs')
        if witness=='off':need(not hits and 'KP_HW_ARM_PASS' not in log,'no-witness control differs')
        summaries.append({'mode':mode,'witness':witness,'statuses':[status]*3,'manifest_sha256':sha(root/'manifest.json'),
                          'request_windows':[(n,int(i)) for n,t,i in hits]})
    need(len({x['manifest_sha256'] for x in summaries})==5,'duplicate runs')
    result={'status':'PASS_TWO_BOUNDED_NODE_FREE_WITNESSES','runs':summaries,'build_sha256':sha(a.build/'build.json'),
            'calibration_sha256':sha(a.calibration/'calibration.json'),'reserved_control_sha256':sha(a.reserved_control/'manifest.json'),
            'audit_source_sha256':sha(Path(__file__)),'current_witnesses':2,'property_windows':[1],
            'list_windows':[1,1,2,3],'node_free_callsite_hits':0,'other_free_paths_excluded':False,'software_reference_bytes_matched':2073600,
            'hardware_video_execution_proved':False,'request_window_proves_async_causality':False,
            'allocation_lifetime_proved':False,'system_modified':False}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'node_free_callsite_hits':0,'hardware_images':0}))


if __name__=='__main__':main()
