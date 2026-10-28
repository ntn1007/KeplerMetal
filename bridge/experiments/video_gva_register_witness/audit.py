#!/usr/bin/env python3
"""Recheck frozen register witnesses, negative controls and software frames."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM as CAS_SYSTEM
SYSTEM=dict(CAS_SYSTEM)
SYSTEM['/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce']='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(ok,reason):
    if not ok:raise ValueError(reason)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True,timeout=15).returncode==0,'signature differs')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('base','build','calibration','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=9,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==9,'fresh output or runs differ')
    base,build,cal=(x.resolve() for x in (a.base,a.build,a.calibration))
    old=read(base/'inputs.json');b=read(build/'build.json');c=read(cal/'calibration.json')
    need(b['status']=='PREPARED' and b['GPU_execution'] is False and b['system']==SYSTEM and
         b['base_inputs_sha256']==sha(base/'inputs.json') and b['registry_id']==old['new_registry_ID'],'build profile differs')
    for name,digest in old['frozen'].items():need(sha(base/name)==digest,'base differs: '+name)
    for name,digest in b['frozen'].items():need(sha(build/name)==digest,'build differs: '+name)
    for name in ('witness.h','tail.S','gva_observer.mm'):need(sha(build/name)==sha(HERE/name),'observer source differs')
    need(c['status']=='PASS' and not c['GPU_execution'] and not c['vendor_execution'] and
         c['scalar']['scalar_flag_cases']==256 and c['scalar']['real_nothrow_allocation_bytes']==1536 and
         c['interposition']['cross_image_interposition'] and c['interposition']['selector']==9 and
         c['interposition']['matching_calls']==1 and c['interposition']['other_call_excluded'],'calibration differs')
    for name,digest in c['sources_sha256'].items():need(sha(cal/name)==sha(HERE/name)==digest,'calibration source differs: '+name)
    for name,digest in c['files_sha256'].items():need(sha(cal/name)==digest,'calibration file differs: '+name)
    need(sha(cal/'tail.S')==sha(build/'tail.S'),'calibration and GPU witness differ')
    for name in ('calibrate','observer.dylib','synthetic.dylib','interpose-calibrate'):sign(cal/name)
    sign(build/'gva-register-observer.dylib');sign(base/'libObserver.dylib')
    pattern=(('cpu','on'),('wrong','on'),('current','on'),('current','off'),('current','on'),
             ('wrong','on'),('cpu','off'),('current','on'),('current','off'))
    statusline='KM_GVA_REGISTER profile=1 allocator=1 images=1 removed=0 calls=1 dropped=0 pending=0'
    eventline='KM_GVA_REGISTER_EVENT index=0 ready=1 selector=2 allocation_size=1536 caller_match=1'
    stack='KM_STACK count=6 offsets=152101,149133,117072,232932,115492,264163'
    intervals=[];receipts=[];cpu_hashes=[];positive=0;negative=0
    for root,(mode,witness) in zip(a.runs,pattern):
        root=root.resolve();m=read(root/'manifest.json');report=read(root/'stdout.json')
        choices={'assets/owned-choice.json','assets/dependency-choice.json','assets/factory-policy-choice.json'}
        for name,digest in old['frozen'].items():
            if name.startswith('assets/') and name not in choices:need(sha(root/name)==digest,'run asset differs: '+name)
        need(read(root/'assets/owned-choice.json')=={'route':'owned'} and
             read(root/'assets/dependency-choice.json')=={'mode':'native' if mode=='cpu' else 'present-key'} and
             read(root/'assets/factory-policy-choice.json')=={'mode':'observe' if mode=='cpu' else 'wrong-board' if mode=='wrong' else 'current-board'},'run choices differ')
        need(m['mode']==mode and m.get('witness','on')==witness and m['exit_code']==0 and not m['SIGKILL_requested'] and
             not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal' and m['GPU_reservation']['child_PID']==m['pid'] and
             m['system_before']==m['system_after']==SYSTEM and m['build_sha256']==sha(build/'build.json') and
             m['base_inputs_sha256']==sha(base/'inputs.json') and m['base_observer_sha256']==sha(base/'libObserver.dylib') and
             m['observer_sha256']==(sha(build/'gva-register-observer.dylib') if witness=='on' else None) and
             m['original_binary_sha256']==m['signed_binary_sha256']==sha(base/'application')==sha(root/'application'),'process provenance differs')
        sign(root/'application');need(report['status']=='OBSERVATION_COMPLETED' and report['codec']=='H264' and not report['hardware_video_execution_proved'],'host outcome differs')
        decode=report['public_decode'];result=decode['decode']['create_status'];frames=decode['output_frames']
        need(result==(0 if mode=='cpu' else -12906 if mode=='wrong' else -12913) and frames==(6 if mode=='cpu' else 0),'decoder status differs')
        dep=read(root/'outputs/dependency.json');factory=read(root/'outputs/factory-resolver.json')
        need(dep['status']=='COMPLETE' and dep['profile']['GPU_registry_ID']==b['registry_id'] and dep['recorders_drained'] and not dep['dropped'] and not dep['pending'] and
             factory['status']=='COMPLETE' and factory['recorders_drained'] and not factory['dropped'],'existing observers differ')
        lines=(root/'stderr.log').read_text().splitlines()
        summaries=[s for s in lines if s.startswith('KM_GVA_REGISTER ')]
        events=[s for s in lines if s.startswith('KM_GVA_REGISTER_EVENT ')]
        if witness=='off':need(not summaries and not events,'disabled witness recorded')
        elif mode=='current':
            need(summaries==[statusline] and events==[eventline] and lines.count(stack)==1,'actual selector witness differs');positive+=1
        elif mode=='wrong':
            need(summaries==['KM_GVA_REGISTER profile=1 allocator=1 images=1 removed=0 calls=0 dropped=0 pending=0'] and not events,'wrong-board control differs');negative+=1
        else:need(summaries==['KM_GVA_REGISTER profile=0 allocator=1 images=0 removed=0 calls=0 dropped=0 pending=0'] and not events,'software control differs')
        if mode=='current':need(dep['substitutions']==1 and factory['policy_substitutions']==3 and decode['decode']['specification']['RequireHardwareAcceleratedVideoDecoder'] is True,'counterfactual scope differs')
        if mode=='cpu':
            need(decode['different_bytes']==0 and decode['CPU_reference_bytes_compared']==691200,'software summary differs')
            hashes=[]
            for i in range(6):
                actual=root/'outputs'/('vt-frame-%03d.nv12'%i);reference=root/'assets/fixtures/H264'/('cpu-frame-%03d.nv12'%i)
                data=actual.read_bytes();need(len(data)==115200 and data==reference.read_bytes(),'software image differs');hashes.append(sha(actual))
            cpu_hashes.append(hashes)
        intervals.append((m['started_at'],m['completed_at']))
        receipts.append({'mode':mode,'witness':witness,'create_status':result,'images':frames,
                         'selector':2 if mode=='current' and witness=='on' else None})
    need(positive==3 and negative==2 and len(cpu_hashes)==2 and cpu_hashes[0]==cpu_hashes[1],'cohort comparison differs')
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)),'hosts overlap')
    result={'status':'PASS_BOUNDED_REGISTER_OBSERVATION','hosts':9,'observed_selector':2,'observed_allocation_bytes':1536,
            'current_board_observations':positive,'wrong_board_controls':negative,'current_without_witness_controls':2,
            'software_controls':2,'software_images':12,'software_reference_bytes':1382400,'hardware_images':0,
            'current_hardware_create_status':-12913,'wrong_board_hardware_create_status':-12906,
            'live_region_sha256':'cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c',
            'observer_sha256':sha(build/'gva-register-observer.dylib'),'calibration_sha256':sha(cal/'calibration.json'),
            'base_inputs_sha256':sha(base/'inputs.json'),'tail_sha256':sha(build/'tail.S'),'receipts':receipts,
            'hardware_video_execution_proved':False,'codec_meaning_of_selector_proved':False,
            'counterfactual_property_and_policy_used':True,'all_allocator_calls_observed':False,'system_modified':False}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
