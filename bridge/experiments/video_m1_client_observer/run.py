#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run public VideoToolbox clients on a reference Mac with local import observation."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'video_bsp_staging'))
from validate_baseline import EXPECTED

SOURCES=('client.mm','observer.c','observer.h')
REFERENCE='d73962c0592ae107d343591bf2d72e013015813e3b2ceff71d37e2c5fee36cd1'
RESERVATION='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248'
OPTS=['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8']
TAGS=('software-plain','software-observed','hardware-plain','hardware-observed')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value: raise ValueError(message)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','fixture','reference','out'): p.add_argument('--'+name,type=Path,required=True)
    for name in ('host','remote-dir'): p.add_argument('--'+name,required=True)
    a=p.parse_args(); lab=a.lab.resolve(); out=a.out.resolve()
    out.relative_to(lab/'results'); need(not out.exists() and out.parent.is_dir(),'fresh output required')
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.host) and
        re.fullmatch(r'/[A-Za-z0-9_./-]+',a.remote_dir) and '..' not in PurePosixPath(a.remote_dir).parts,'invalid host/path')
    need({f.name:sha(f) for f in a.fixture.iterdir() if f.is_file()}==EXPECTED and sha(a.reference)==REFERENCE,'fixture/reference differs')
    sources={n:sha(HERE/n) for n in SOURCES}
    files=[*(HERE/n for n in SOURCES),*(a.fixture/n for n in sorted(EXPECTED))]
    hashes={f.name:sha(f) for f in files}; need(len(hashes)==len(files),'ambiguous transfer names')
    out.mkdir(); ssh=['/usr/bin/ssh','-T',*OPTS,a.host]; prefix='cd '+shlex.quote(a.remote_dir)+' && '
    def run(label,args):
        result=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
        (out/(label+'.stdout')).write_bytes(result.stdout); (out/(label+'.stderr')).write_bytes(result.stderr)
        need(result.returncode==0,label+' failed; inspect retained logs')
        return result.stdout.decode()
    run('mkdir',ssh+['mkdir '+shlex.quote(a.remote_dir)])
    run('transfer',['scp',*OPTS,*files,a.host+':'+a.remote_dir+'/'])
    def check(label):
        rows=run(label,ssh+[prefix+'shasum -a 256 '+' '.join(hashes)]).splitlines()
        need({n:d for d,n in (line.split(None,1) for line in rows)}==hashes,label+' transfer differs')
    check('source-before')
    build=prefix+('xcrun clang -std=c11 -Wall -Wextra -Werror -O1 -dynamiclib observer.c -framework IOKit -o observer.dylib && '
        'xcrun clang++ -std=c++17 -Wall -Wextra -Werror -O1 -fobjc-arc client.mm -framework Foundation '
        '-framework VideoToolbox -framework CoreVideo -framework CoreMedia -framework IOKit -o client && '
        'codesign --force --sign - observer.dylib && codesign --force --sign - client && '
        'codesign --verify --strict observer.dylib && codesign --verify --strict client && '
        'uname -m && sw_vers -productVersion && shasum -a 256 client observer.dylib')
    info=run('build',ssh+[build]).splitlines()
    need(len(info)==4 and info[0]=='arm64','reference architecture differs')
    binaries={n:d for d,n in (line.split(None,1) for line in info[2:])}
    need(set(binaries)=={'client','observer.dylib'} and all(len(d)==64 for d in binaries.values()),'binary identity differs')
    check('source-before-cohort')
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(leasepath)==RESERVATION,'reservation differs')
    spec=importlib.util.spec_from_file_location('m1_vt_reservation',leasepath)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); lease=mod.GPUReservation(lab)
    child=None; finished=False
    try:
        sshpath=Path('/usr/bin/ssh'); lease.spawning(sshpath,sha(sshpath))
        pieces=['trap \'rc=$?; printf "%s\\n" "$rc" >cohort.exit\' EXIT','set -e']
        for tag in TAGS:
            mode=tag.split('-')[0]
            env='env DYLD_INSERT_LIBRARIES=./observer.dylib ' if tag.endswith('observed') else 'env -u DYLD_INSERT_LIBRARIES '
            pieces.append(env+'./client . '+tag+'.nv12 '+mode+' >'+tag+'.json 2>'+tag+'.stderr')
        shell=prefix+'; '.join(pieces)
        started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'cohort.stdout').open('wb') as stdout,(out/'cohort.stderr').open('wb') as stderr:
            child=subprocess.Popen([*ssh,shell],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,))
            lease.bind_child(child.pid); code=child.wait()
        visible=mod.process_table().get(child.pid)
        try:
            marker=run('terminal-marker',ssh+[prefix+'cat cohort.exit']).strip()
            attested=marker.isdigit() and int(marker)==code and code!=255
        except Exception:
            attested=False
        lease.finish(code if attested else None,False,'' if visible is None else 'ssh process still visible')
        finished=True
        (out/'reservation.json').write_text(json.dumps(lease.data,indent=2,sort_keys=True)+'\n')
        need(attested and not visible and code==0,'cohort not successfully terminal')
    finally:
        if not finished: lease.finish(None,False,'cohort outcome not established')
        lease.close()
    remote_files=[a.host+':'+a.remote_dir+'/'+tag+suffix for tag in TAGS for suffix in ('.json','.nv12','.stderr')]
    run('retrieve',['scp',*OPTS,*remote_files,str(out)+'/'])
    check('source-after')
    final=run('binary-after',ssh+[prefix+'codesign --verify --strict client && codesign --verify --strict observer.dylib && shasum -a 256 client observer.dylib']).splitlines()
    need({n:d for d,n in (line.split(None,1) for line in final)}==binaries,'signed binaries changed')
    need({n:sha(HERE/n) for n in SOURCES}==sources and all(sha(f)==hashes[f.name] for f in files) and sha(a.reference)==REFERENCE,'local inputs changed')
    reference=a.reference.read_bytes(); rows=[]
    for tag in TAGS:
        data=json.loads((out/(tag+'.json')).read_text()); pixels=(out/(tag+'.nv12')).read_bytes()
        need(not (out/(tag+'.stderr')).read_bytes() and data['status']=='PASS' and data['frames']==6 and
             data['bytes']==691200 and data['decode_statuses']==[0]*6 and len(pixels)==len(reference),'decode differs')
        observed=tag.endswith('observed'); need(data['observer_loaded']==observed and data['observer_calibrated']==observed,'calibration differs')
        differences=sum(x!=y for x,y in zip(pixels,reference))
        rows.append({'tag':tag,'output_sha256':sha(out/(tag+'.nv12')),'differing_bytes':differences,
            'hardware_property_status':data['hardware_property_status'],'hardware_property':data['hardware_property'],
            'observer_loaded':observed,'observer_calibrated':data['observer_calibrated'],
            'observed_counts':data['observed_counts'],'services':data['services'],
            'detail_events':data['detail_events'],'dropped_events':data['dropped_events']})
    result={'status':'PASS_REFERENCE_COHORT','architecture':info[0],'macos_version':info[1],
        'started_at':started,'source_sha256':sources,'fixture_sha256':EXPECTED,'reference_sha256':REFERENCE,
        'signed_binary_sha256':binaries,'reservation_id':lease.data['reservation_id'],'cohort_exit_code':code,
        'runs':rows,'observer_scope':'instrumented own-process imported functions only',
        'other_processes_observed':False,'kepler_video_execution_proved':False,'system_modified':False,
        'runner_sha256':sha(Path(__file__))}
    (out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'runs':len(rows),'outputs':[(x['tag'],x['differing_bytes'],x['hardware_property']) for x in rows]}))

if __name__=='__main__': main()
