#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit software VT decode and native GPU NV12 transformation against FFmpeg."""
import argparse,base64,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sha_bytes(p):return hashlib.sha256(p).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(x,why):
    if not x:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--reference-evidence',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=8,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==8,'fresh output and distinct runs')
    build=a.build.resolve();b=load(build/'build.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM,'build')
    for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build file '+n)
    for n in ('client.mm','kernels.metal'):need(sha(build/n)==sha(HERE/n),'source differs')
    need({x.name:sha(x) for x in (build/'fixture').iterdir() if x.is_file()}==b['fixture_sha256'],'fixture')
    sign(build/'application');f=load(build/'fixture/fixture.json');need(f['NAL_length_bytes']==4 and len(f['frames'])==6 and len(f['H264_parameter_sets_base64'])==2,'fixture contract')
    start=b'\0\0\0\1';annex=b''.join(start+base64.b64decode(x,validate=True) for x in f['H264_parameter_sets_base64'])
    for row in f['frames']:
        name=row['file'];need(name==Path(name).name,'fixture path');data=(build/'fixture'/name).read_bytes();need(len(data)==row['bytes'],'sample length');i=0
        while i<len(data):
            need(i+4<=len(data),'NAL prefix');n=int.from_bytes(data[i:i+4],'big');i+=4;need(n>0 and i+n<=len(data),'NAL bounds');annex+=start+data[i:i+n];i+=n
    annex_sha='12858642f02b0e1d98ddf409dd729a879b6a7a5d3434c860882532ca4f6b40af';reference_sha='d73962c0592ae107d343591bf2d72e013015813e3b2ceff71d37e2c5fee36cd1';ffmpeg_sha='c8173e9755795978bce8e104f8d7044fabe7d6d84044aba37d3648c6f4e4e1a8'
    reference=a.reference_evidence.resolve();started=load(reference/'run-start.json');terminal=load(reference/'run-terminal.json');ref=(build/'reference.nv12').read_bytes()
    need(sha_bytes(annex)==annex_sha==sha(reference/'fixture-annexb.h264') and (reference/'fixture-annexb.h264').read_bytes()==annex and len(ref)==691200 and sha_bytes(ref)==reference_sha==sha(reference/'decoded.nv12'),'reference inputs')
    need(started['architecture']=='arm64' and started['hardware_acceleration']=='none' and started['binary_SHA256']==terminal['binary_SHA256_after']==ffmpeg_sha and started['input_SHA256']==terminal['input_SHA256_after']==annex_sha and terminal['output_SHA256']==reference_sha and terminal['output_bytes']==len(ref) and terminal['exit_code']==0 and not terminal['SIGKILL_requested'] and not terminal['authoritative_ps_status'] and terminal['pid']==started['pid'] and terminal['stderr_SHA256']==sha(reference/'stderr.txt') and terminal['stdout_SHA256']==sha(reference/'stdout.txt'),'archived independent FFmpeg receipt')
    rows=[];images={};intervals=[];dispatches=0;propertyStatuses=set();sentinel=bytes([0x55])*115200
    for path,mode in zip(a.runs,('gpu','y-only','uv-only','none')*2):
        path=path.resolve();m=load(path/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(path/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process provenance');sign(path/'application')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(path/'stdout.json') and m['stderr_sha256']==sha(path/'stderr.log'),'logs/system')
        d=load(path/'stdout.json');y=mode in ('gpu','y-only');uv=mode in ('gpu','uv-only');n=int(y)+int(uv)
        need(d['status']=='PASS' and d['mode']==mode and d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id'] and d['decoder_hardware_disabled'] and d['decode_statuses']==[0]*6 and d['decode_finish_status']==d['decode_wait_status']==0 and d['gpu_dispatches']==6*n and len(d['frames'])==6 and not d['hardware_video_execution_proved'],'client')
        propertyStatuses.add(d['hardware_property_status']);frameHashes=[]
        for i,item in enumerate(d['frames']):
            need(item['frame']==i and item['source_iosurface'] and item['dest_iosurface'] and item['distinct_surfaces'] and item['texture_planes_checked']==4 and item['source_unchanged'] and item['source_bytes']==item['dest_bytes']==115200 and item['command_buffer_status']==(4 if n else 0),'frame')
            need(len(item['source_storage'])==len(item['dest_storage'])==len(item['dest_synchronized'])==2 and item['dest_synchronized']==[bool(y and item['dest_storage'][0]==1),bool(uv and item['dest_storage'][1]==1)],'managed synchronization')
            expectedSource=ref[115200*i:115200*(i+1)];source=(path/'outputs'/f'source-{i}.nv12').read_bytes();dest=(path/'outputs'/f'dest-{i}.nv12').read_bytes();need(source==expectedSource,'source differs from independent FFmpeg')
            expectedDest=(bytes(255-v for v in expectedSource[:76800]) if y else sentinel[:76800])+(expectedSource[76800:] if uv else sentinel[76800:]);need(dest==expectedDest,'GPU destination differs from CPU oracle');frameHashes.append(sha_bytes(dest))
        images.setdefault(mode,[]).append(frameHashes);dispatches+=6*n;intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(path/'manifest.json'),'dest_sha256':frameHashes})
    need(all(len(v)==2 and v[0]==v[1] for v in images.values()),'repeat mismatch');intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(7)),'process overlap')
    out={'status':'PASS_SOFTWARE_VT_METAL_NV12','build_sha256':sha(build/'build.json'),'fixture_sha256':b['fixture_sha256'],'annexb_sha256':annex_sha,'reference_nv12_sha256':reference_sha,'reference_ffmpeg_sha256':ffmpeg_sha,'reference_ffmpeg_architecture':'arm64','reference_acceleration':'none','reference_receipt_sha256':sha(reference/'run-terminal.json'),'reference_reexecuted_this_cohort':False,'processes':8,'frames':48,'source_and_destination_bytes_checked':11059200,'completed_gpu_dispatches':dispatches,'decoder_hardware_disabled':True,'decoder_hardware_property_statuses':sorted(propertyStatuses),'distinct_surface_identity_checked':True,'hardware_video_decode_proved':False,'hardware_video_encode_proved':False,'physical_transfer_count_measured':False,'performance_benchmark':False,'system_files_unchanged':True,'runs':rows}
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':out['status'],'bytes_checked':out['source_and_destination_bytes_checked'],'gpu_dispatches':dispatches,'decoder_hardware_property_statuses':sorted(propertyStatuses)}))
if __name__=='__main__':main()
