#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit six isolated three-request runs and their pinned observer prototypes."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(ok,msg):
    if not ok:raise ValueError(msg)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','build','metadata-qualification','dependency-qualification','out'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--runs',required=True,nargs=6,type=Path);a=p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    base=read(a.base/'inputs.json');b=read(a.build/'build.json');mq=read(a.metadata_qualification/'qualification.json');dq=read(a.dependency_qualification/'qualification.json')
    need(b['repeat_integrated'] and b['base_inputs_sha256']==sha(a.base/'inputs.json') and
         mq['status']=='PASS_CPU_REPEAT_METADATA_PROTOTYPE' and dq['status']=='PASS_REPEAT_DEPENDENCY_CPU_SCOPES','build or qualification differs')
    for n,h in base['frozen'].items():need(sha(a.base/n)==h,'base differs: '+n)
    for n,h in b['frozen'].items():need(sha(a.build/n)==h,'build differs: '+n)
    for n,h in b['sources_sha256'].items():
        need(sha(a.build/n)==sha(HERE/n)==h,'observer source differs: '+n)
        q=mq if n in ('metadata_repeat.mm','video_registry_metadata.h') else dq
        need(q['sources_sha256'][n]==h,'standalone qualification source differs: '+n)
    need(mq['sources_sha256']['repeat_gate.h']==dq['sources_sha256']['repeat_gate.h']==b['sources_sha256']['repeat_gate.h'], 'gate pins differ')
    need(sha(a.base/'libDependency.dylib')==b['dependency_sha256'] and sha(a.base/'libMetadataRepeat.dylib')==b['metadata_sha256'], 'library differs')
    sym=subprocess.run(['nm','-g',str(a.base/'libDependency.dylib')],capture_output=True,text=True,check=True).stdout
    need('KPDependencyTest' not in sym,'test seam in integrated library')
    modes=[('cpu','on',0),('cpu','off',0),('current','off',-12913),('wrong','on',-12906),('current','on',-12913),('current','on',-12913)]
    receipts=[]
    for root,(mode,witness,status) in zip(a.runs,modes):
        m=read(root/'manifest.json');r=read(root/'stdout.json');err=(root/'stderr.log').read_text();log=(root/'lldb.log').read_text()
        need(m['status']=='TERMINAL_SCOPED_DEBUGGER' and m['mode']==mode and m['witness']==witness and
             m['target_exit_code']==m['debugger_exit_code']==0 and m['target_and_debugger_absent'] and
             m['reservation']['state']=='terminal' and not m['reservation']['SIGKILL_requested'] and
             not m['reservation']['authoritative_ps_status'] and m['build_sha256']==sha(a.build/'build.json') and
             m['host_sha256']==sha(root/'application')==b['frozen']['application'] and
             m['lldb_log_sha256']==sha(root/'lldb.log') and m['stdout_sha256']==sha(root/'stdout.json') and
             m['stderr_sha256']==sha(root/'stderr.log'), 'run provenance differs')
        need(r['status']=='OBSERVATION_COMPLETED' and len(r['additional_public_decodes'])==2 and
             m['decoder_status']==status and m['output_frames']==(6 if mode=='cpu' else 0), 'host result differs')
        decodes=[r['public_decode'],*r['additional_public_decodes']]
        for i,v in enumerate(decodes):
            need(v is not None and v['decode']['create_status']==status and v['output_frames']==(6 if mode=='cpu' else 0), 'decode differs')
            if mode=='cpu':
                need(v['CPU_reference_bytes_compared']==691200 and v['different_bytes']==0, 'software comparison differs')
                folder=root/'outputs' if i==0 else root/'outputs'/('repeat-%d'%(i+1))
                for frame in range(6):
                    reference=root/'assets/fixtures/H264'/('cpu-frame-%03d.nv12'%frame)
                    actual=folder/('vt-frame-%03d.nv12'%frame)
                    need(reference.stat().st_size==115200 and sha(reference)==sha(actual), 'frame bytes differ')
        need(re.findall(r'^KP_REPEAT_(BEGIN|END) request=(\d+)$',err,re.M)==[(x,str(i)) for i in (1,2,3) for x in ('BEGIN','END')] and
             'KP_REPEAT_DEPENDENCY_RECORD_FAILED' not in err and 'KP_REPEAT_DEPENDENCY_RELEASE_FAILED' not in err,'request markers differ')
        dependencies=[]; metadata=[]
        for i in range(3):
            dep=read(root/'outputs'/('dependency.json' if i==0 else 'dependency-%d.json'%(i+1)))
            met=read((root/'outputs' if i==0 else root/'outputs'/('repeat-%d'%(i+1)))/'metadata.json')
            need(dep['status']=='COMPLETE' and dep['recorders_drained'] and not dep['pending'] and not dep['dropped'] and
                 dep['public_query_controls_valid'] and dep['public_create_called'] and dep['create_status']==status and
                 dep['hardware_requirement_preserved'] and dep['substitutions']==(1 if mode!='cpu' and i==0 else 0), 'dependency record differs')
            need(met['status']=='COMPLETE' and met['recorders_drained'] and not met['pending'] and not met['dropped'] and
                 met['public_retain_control_valid'], 'metadata record differs')
            dependencies.append({'calls':dep['calls'],'substitutions':dep['substitutions'],'sha256':sha(root/'outputs'/('dependency.json' if i==0 else 'dependency-%d.json'%(i+1)))})
            metadata.append({'calls':met['calls'],'sha256':sha((root/'outputs' if i==0 else root/'outputs'/('repeat-%d'%(i+1)))/'metadata.json')})
        if mode=='current' and witness=='on':
            need(log.count('KP_HW_ARM_PASS mode=gva')==1 and log.count('name=property_return bytes_match=1')==1 and
                 log.count('name=list_entry bytes_match=1')==4 and 'KP_CACHE_CHECK ' not in log and
                 re.search(r'4\.1: .*resolved, hardware, hit count = 0',log), 'cache witness differs')
        if mode=='wrong':need('KP_HW_ARM_FAIL' not in log and 'KP_HW_HIT name=' not in log, 'wrong-board witness differs')
        receipts.append({'manifest_sha256':sha(root/'manifest.json'),'mode':mode,'witness':witness,'session_statuses':[status]*3,
                         'frames_per_request':6 if mode=='cpu' else 0,'dependencies':dependencies,'metadata':metadata})
    need(len({r['manifest_sha256'] for r in receipts})==6,'duplicate receipts')
    result={'status':'PASS_SIX_THREE_REQUEST_RUNS','runs':receipts,'build_sha256':sha(a.build/'build.json'),
            'metadata_qualification_sha256':sha(a.metadata_qualification/'qualification.json'),
            'dependency_qualification_sha256':sha(a.dependency_qualification/'qualification.json'),
            'audit_source_sha256':sha(Path(__file__)),'software_session_count':6,'software_frames':36,
            'software_reference_bytes_matched':4147200,'hardware_required_requests':12,'hardware_images':0,
            'current_witness_runs':2,'property_hits_per_current_witness':1,'list_hits_per_current_witness':4,
            'cache_check_hits_per_current_witness':0,'event_per_request_attribution_proved':False,
            'allocation_lifetime_proved':False,'hardware_video_execution_proved':False,
            'test_seam_absent_from_integrated_library':True,'system_modified':False}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'software_sessions':6,'hardware_requests':12,'hardware_images':0}))


if __name__=='__main__':main()
