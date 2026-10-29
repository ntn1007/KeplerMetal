#!/usr/bin/env python3
"""Independently verify frozen source, process evidence, and raw GPU images."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=4,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    build=a.build.resolve();archive=a.archive.resolve();m=json.loads((build/'build.json').read_text());am=json.loads((archive/'manifest.json').read_text())
    need(m['GPU_execution'] is False and m['system']==SYSTEM and sha(archive/'manifest.json')==m['source_manifest_SHA256'] and
         sha(archive/'libKeplerMetal.a')==m['archive_SHA256']==am['static_library_SHA256'],'archive evidence differs')
    for name,digest in am['source_SHA256'].items():need(sha(archive/'src'/name)==digest==sha(BRIDGE/'src'/name),'source differs: '+name)
    for name,digest in m['files_SHA256'].items():need(sha(build/name)==digest,'build differs: '+name)
    need(sha(build/'client.mm')==sha(HERE/'kepler_client.mm') and sha(build/'bootstrap.mm')==sha(HERE.parent/'standalone_icb/bootstrap.mm') and
         sha(build/'carrier.metallib')=='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7','test profile differs')
    need(subprocess.run(['codesign','--verify','--strict',str(build/'bootstrap.dylib')],capture_output=True,timeout=15).returncode==0,'bootstrap signature differs')
    names=('normal','one','two','indexed_normal','indexed_one','indexed_two','normal_after_reset')
    receipts=[];intervals=[];images=[]
    for root,mode in zip(a.runs,('direct','auto','direct','auto')):
        root=root.resolve();manifest=json.loads((root/'manifest.json').read_text());report=json.loads((root/'stdout.json').read_text())
        need(manifest['mode']==mode and manifest['exit_code']==0 and not manifest['SIGKILL_requested'] and not manifest['authoritative_ps_status'] and
             manifest['GPU_reservation']['state']=='terminal' and manifest['GPU_reservation']['child_PID']==manifest['pid'] and
             manifest['system_before']==manifest['system_after']==SYSTEM and manifest['build_sha256']==sha(build/'build.json') and
             manifest['original_binary_sha256']==sha(build/'application')==manifest['signed_binary_sha256']==sha(root/'application') and
             manifest['injected_sha256']==(sha(build/'bootstrap.dylib') if mode=='auto' else None),'process evidence differs')
        need(manifest['arguments']==[str(build/'carrier.metallib'),mode,str(root/'outputs')] and
             subprocess.run(['codesign','--verify','--strict',str(root/'application')],capture_output=True,timeout=15).returncode==0,'arguments or signature differ')
        need(report['status']=='PASS' and report['mode']==mode and report['rejections']==(7 if mode=='auto' else 0) and report['device']=='NVIDIA GeForce GTX 880M' and report['registry_id']!=0 and
             [r['case'] for r in report['cases']]==list(names) and all(r['completed'] and r['checked_channels']==12288 and r['guard_bytes']==512 for r in report['cases']),'client report differs')
        if mode=='auto':
            need(report['device_class'].startswith('KPICBDevice_'),'adapted device missing')
            trace=(root/'stderr.log').read_text()
            need(all(x in trace for x in ('KM_BOOT enabled','KM_BOOT queue matched','KM_BOOT library snapshot approved','KM_BOOT pipeline matched')),'bootstrap trace differs')
            events=json.loads((root/'events.json').read_text())
            execs=[e for e in events if e['operation']=='execute_CPU_render_ICB']
            need(len(execs)==7 and [e['executed_indices'] for e in execs]==[[0],[],[],[0],[],[],[0]],'ICB event sequence differs')
        else:need(report['device_class']=='NVMTLDevice' and not (root/'events.json').exists(),'native control differs')
        hashes=[]
        for name in names:
            path=root/'outputs'/(name+'.bin');raw=path.read_bytes()
            need(len(raw)==49664 and raw[:256]==raw[-256:]==b'\xa5'*256,'image guard differs')
            values=struct.unpack('<12288f',raw[256:-256]);empty=name.endswith('one') or name.endswith('two');color=(.75,.125,.25,1.)
            need(all(value==(0.0 if empty else color[i%4]) for i,value in enumerate(values)),'independent pixel oracle differs: '+name)
            hashes.append(sha(path))
        images.append(hashes);intervals.append((manifest['started_at'],manifest['completed_at']))
        receipts.append({'mode':mode,'image_sha256':dict(zip(names,hashes)),'checked_channels':7*12288,'guard_bytes':7*512})
    need(images[0]==images[1]==images[2]==images[3],'direct and adapted captures differ')
    intervals.sort();need(all(x<=y for x,y in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)),'processes overlap')
    report={'status':'PASS','processes':4,'cases_per_process':7,'checked_float_channels':4*7*12288,'guard_bytes':4*7*512,'negative_api_refusals':14,
            'direct_and_adapted_images_identical':True,'runtime_archive_sha256':m['archive_SHA256'],'receipts':receipts,
            'system_driver_modified':False,'transparent_application_support':False,'general_metal_conformance':False,'performance_benchmark':False}
    with a.out.open('x') as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(report))

if __name__=='__main__':main()
