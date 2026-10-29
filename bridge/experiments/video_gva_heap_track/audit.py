#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit bounded watched-node free observations and CPU controls."""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
HEAP=HERE


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(ok,msg):
    if not ok:raise ValueError(msg)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','build','heap-calibration','region','mapping','metadata','out'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--runs',required=True,nargs=5,type=Path);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    b=read(a.build/'build.json');c=read(a.heap_calibration/'calibration.json');m=read(a.mapping);meta=read(a.metadata)
    need(b['heap_tracking_variant'] and b['base_inputs_sha256']==sha(a.base/'inputs.json') and
         b['heap_calibration_sha256']==sha(a.heap_calibration/'calibration.json') and
         c['status']=='PASS_LLDB_WATCHED_TARGET_CPU_CALIBRATION' and c['match_and_nonmatch_order_tested'] and c['observer_sha256']==sha(a.build/'heap-watch.dylib') and
         sha(HERE/'lldb_tracking.py')==sha(a.build/'lldb_tracking.py') and sha(HERE/'lldb_target.py')==sha(a.build/'lldb_target.py'), 'build provenance differs')
    for n,h in b['frozen'].items():need(sha(a.build/n)==h,'build file differs')
    for n,h in c['sources_sha256'].items():
        s=HEAP.parent/'video_gva_repeat_sessions'/n if n=='repeat_gate.h' else HEAP/n
        need(sha(a.heap_calibration/n)==sha(s)==h,'heap source differs')
    subprocess.run(['codesign','--verify','--strict',str(a.build/'heap-watch.dylib')],capture_output=True,check=True)
    for mode,want in [('match','PASS matched free then unrelated free'),('different','PASS unrelated free then matched free')]:
        path=a.heap_calibration/(mode+'.stdout');log=path.read_text()
        need(c['logs_sha256'][mode]==sha(path) and log.count('KP_HEAP_TARGET_WRITE success=1')==1 and
             want in log and 'exited with status = 0' in log, 'CPU tracking control differs')
    need(sha(a.region)=='f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19' and
         sha(a.mapping)=='2d9c4ed04bcdbdd4049bb7ed88f0a545d3f42b1b478ab320e43fc8feb6a39ffd' and
         m['status']=='STATIC_ONLY' and not m['runtime_target_proved'] and
         meta['image']['UUID']=='ca5414f369373c059ea2d82b35afd4f0' and meta['image_base_VM']==140711945101312 and
         meta['region']['SHA256']==sha(a.region),'static profile differs')
    rows=[x for x in m['rows'] if x['caller_offset']==150964];need(len(rows)==1,'callsite ambiguous');row=rows[0]
    source=a.region.read_bytes();at=150964-148746;need(source[at]==0xe8 and
        150969+struct.unpack_from('<i',source,at+1)[0]==row['stub_VM']-meta['image_base_VM'] and
        '_free' in row['exact_defined_symbols'] and row['verified_GOT_VM']-meta['image_base_VM']==847829912, 'call and slot mapping differs')
    modes=[('cpu','on',0),('wrong','on',-12906),('current','off',-12913),('current','on',-12913),('current','on',-12913)]
    receipts=[]
    for root,(mode,witness,status) in zip(a.runs,modes):
        r=read(root/'manifest.json');report=read(root/'stdout.json');log=(root/'lldb.log').read_text();err=(root/'stderr.log').read_text()
        need(r['status']=='TERMINAL_SCOPED_DEBUGGER' and r['mode']==mode and r['witness']==witness and
             r['target_exit_code']==r['debugger_exit_code']==0 and r['target_and_debugger_absent'] and
             r['reservation']['state']=='terminal' and not r['reservation']['SIGKILL_requested'] and
             not r['reservation']['authoritative_ps_status'] and r['build_sha256']==sha(a.build/'build.json') and
             r['runner_sha256']==sha(HERE/'run_gva.py') and r['host_sha256']==sha(root/'application')==b['frozen']['application'] and
             r['lldb_log_sha256']==sha(root/'lldb.log') and r['stderr_sha256']==sha(root/'stderr.log') and
             r['stdout_sha256']==sha(root/'stdout.json'), 'run provenance differs')
        need(report['status']=='OBSERVATION_COMPLETED' and len(report['additional_public_decodes'])==2 and
             re.findall(r'^KP_REPEAT_(BEGIN|END) request=(\d+)$',err,re.M)==[(x,str(i)) for i in (1,2,3) for x in ('BEGIN','END')], 'request shape differs')
        for i,d in enumerate([report['public_decode'],*report['additional_public_decodes']]):
            need(d is not None and d['decode']['create_status']==status and d['output_frames']==(6 if mode=='cpu' else 0),'decode result differs')
            if mode=='cpu':
                need(d['different_bytes']==0 and d['CPU_reference_bytes_compared']==691200,'CPU result differs')
                folder=root/'outputs' if i==0 else root/'outputs'/('repeat-%d'%(i+1))
                for k in range(6):
                    x=root/'assets/fixtures/H264'/('cpu-frame-%03d.nv12'%k);y=folder/('vt-frame-%03d.nv12'%k)
                    need(x.stat().st_size==115200 and sha(x)==sha(y),'frame differs')
            dep=read(root/'outputs'/('dependency.json' if i==0 else 'dependency-%d.json'%(i+1)))
            met=read((root/'outputs' if i==0 else root/'outputs'/('repeat-%d'%(i+1)))/'metadata.json')
            need(dep['status']=='COMPLETE' and dep['recorders_drained'] and not dep['pending'] and not dep['dropped'] and
                 dep['public_query_controls_valid'] and dep['public_create_called'] and dep['create_status']==status and
                 met['status']=='COMPLETE' and met['recorders_drained'] and not met['pending'] and not met['dropped'] and
                 met['public_retain_control_valid'], 'observer record differs')
        if witness=='on':need(err.count('KP_HEAP_ARMED')==1 and 'KP_HEAP_DISARM_FAILED' not in err,'heap scope differs')
        if mode!='cpu' and witness=='on':need(log.count('KP_HEAP_BINDING matched=1')==1 and 'KP_HEAP_BINDING_ARM_FAIL' not in log,'free slot differs')
        else:need('KP_HEAP_BINDING matched=' not in log,'unexpected free slot observation')
        if mode=='current' and witness=='on':
            hits=re.findall(r'^KP_REQUEST_HIT name=(\w+) thread=\d+ request_window=(\d+)$',log,re.M)
            need(hits==[('property_return','1'),('list_entry','1'),('list_entry','1'),('list_entry','2'),('list_entry','3')], 'request hits differ')
            track=re.findall(r'^KP_HEAP_TRACK_LIST window=(\d+) free_hits=(\d+) zone_hits=(\d+) bound=(\d+) target_ok=(\d+)$',log,re.M)
            need(log.count('KP_HEAP_TRACK_ARM bound=1 target_written=1')==1 and
                 track==[(i,'0','0','1','1') for i in ('1','1','2','3')] and
                 len(re.findall(r'^KP_HW_HIT name=list_entry bytes_match=1 .*link_valid=1 same_node=1$',log,re.M))==4 and
                 'KP_HW_HIT_FAIL' not in log, 'tracking events differ')
        else:need('KP_HEAP_TRACK_ARM ' not in log and 'KP_HEAP_TRACK_LIST ' not in log,'unexpected tracker event')
        receipts.append({'mode':mode,'witness':witness,'status_per_request':[status]*3,'manifest_sha256':sha(root/'manifest.json'),
                         'free_binding_matches_observer_at_arm':mode!='cpu' and witness=='on'})
    need(len({x['manifest_sha256'] for x in receipts})==5,'duplicate run')
    result={'status':'PASS_TWO_SCOPED_NODE_FREE_TRACKS','runs':receipts,'heap_calibration_sha256':sha(a.heap_calibration/'calibration.json'),
            'build_sha256':sha(a.build/'build.json'),'static_region_sha256':sha(a.region),'static_mapping_sha256':sha(a.mapping),
            'auditor_sha256':sha(Path(__file__)),'free_slot_offset':847829912,'linked_callsite_offset':150964,
            'binding_observations':3,'tracking_pointer_armed':True,'matched_free_or_zone_events_before_last_list':0,
            'all_deallocation_paths_covered':False,'allocation_lifetime_proved':False,
            'hardware_video_execution_proved':False,'system_modified':False}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'tracked_runs':2,'matched_events':0,'hardware_images':0}))


if __name__=='__main__':main()
