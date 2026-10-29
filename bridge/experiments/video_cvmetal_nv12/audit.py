#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare all captured CVPixelBuffer planes to independent CPU patterns."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(x,why):
    if not x:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=8,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==8,'fresh output and distinct runs')
    build=a.build.resolve();b=load(build/'build.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM,'build')
    for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build file '+n)
    for n in ('client.mm','kernels.metal'):need(sha(build/n)==sha(HERE/n),'source differs')
    sign(build/'application');luma=bytes(16+(x*3+y*5+7)%220 for y in range(96) for x in range(128));chroma=bytes(v for y in range(48) for x in range(64) for v in (16+(x*7+y*11+3)%225,16+(x*5+y*13+9)%225));sentinel_y=bytes([0x55])*len(luma);sentinel_uv=bytes([0x55])*len(chroma)
    images={};rows=[];intervals=[];padding=0;dispatches=0
    for path,mode in zip(a.runs,('gpu','y-only','uv-only','none')*2):
        path=path.resolve();m=load(path/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(path/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');sign(path/'application')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
        need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(path/'stdout.json') and m['stderr_sha256']==sha(path/'stderr.log'),'logs/system')
        d=load(path/'stdout.json');y=mode in ('gpu','y-only');uv=mode in ('gpu','uv-only');n=int(y)+int(uv)
        need(d['status']=='PASS' and d['mode']==mode and d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id'] and d['surface_id'] and d['same_surface'] and d['surface_planes']==[0,1] and len(d['row_bytes'])==2 and all(v>=128 for v in d['row_bytes']) and d['samples']==18432 and d['dispatches']==n and d['command_buffer_status']==(4 if n else 0) and not d['video_decode_executed'],'client')
        need(len(d['storage_modes'])==len(d['synchronized'])==2 and d['synchronized']==[bool(y and d['storage_modes'][0]==1),bool(uv and d['storage_modes'][1]==1)],'synchronization')
        need(d['padding_checked']==(d['row_bytes'][0]-128)*96+(d['row_bytes'][1]-128)*48,'padding count');raw=(path/'outputs/nv12.bin').read_bytes();expected=(luma if y else sentinel_y)+(chroma if uv else sentinel_uv);need(raw==expected,'CPU plane mismatch');digest=sha(path/'outputs/nv12.bin');images.setdefault(mode,[]).append(digest);padding+=d['padding_checked'];dispatches+=n;intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(path/'manifest.json'),'capture_sha256':digest,'row_bytes':d['row_bytes'],'storage_modes':d['storage_modes'],'synchronized':d['synchronized']})
    need(all(len(v)==2 and v[0]==v[1] for v in images.values()) and len({v[0] for v in images.values()})==4,'repeat/control mismatch');intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(7)),'process overlap')
    result={'status':'PASS_CVMETAL_NV12','build_sha256':sha(build/'build.json'),'kernel_source_sha256':sha(HERE/'kernels.metal'),'kernel_library_sha256':b['files_sha256']['kernels.metallib'],'processes':8,'modes':['gpu','y-only','uv-only','none'],'luma_bytes_per_image':len(luma),'chroma_bytes_per_image':len(chroma),'cpu_checked_bytes':8*(len(luma)+len(chroma)),'completed_gpu_dispatches':dispatches,'padding_bytes_checked':padding,'same_iosurface_and_planes_observed':True,'video_hardware_decode_proved':False,'video_hardware_encode_proved':False,'physical_transfer_count_measured':False,'performance_benchmark':False,'system_files_unchanged':True,'runs':rows}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'cpu_checked_bytes':result['cpu_checked_bytes'],'dispatches':dispatches,'padding_bytes_checked':padding}))
if __name__=='__main__':main()
