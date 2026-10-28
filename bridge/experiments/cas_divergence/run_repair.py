#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run one exact-program CAS repair variant under a no-kill iMac lease."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path


PINS={'shader.metallib':'811e53236f858247d59ae1540efb1a74160c0e566522faadd9fa82ad60de8640',
      'original.sass':'83fedb1873bf54ae9975d3f44bd8e8512a9639903afee18d2decef4fbcdd2eb2',
      'repaired.sass':'d0dfcbe6cbcdbba8df91289d7eb56f122ba48eeeb91d7c6b294ceaf7c291e1e8',
      'trampoline.sass':'518a2b787d35d2e54dd8cc8b213f52e5b5c5faa6135599241bbbd74f433bd213',
      'wrong-original.sass':'acda2d4439c1853ea0438e5c02438625e324f8d549aa9de23a775e69f62509eb'}
SYSTEM={'/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver':'e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645',
        '/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin':'692af9a05d750ac4eedfe3181feed73cb1214b83454f748b3a845b3a3a6aabac',
        '/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist':'eaf1eed0859324c69161f019560ac7818d2b6a3a0d6361bee94ff54f4b962315'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','build','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--mode',choices=('native','replay','trampoline','repaired','negative-pin'),required=True)
    a=p.parse_args();lab=a.lab.resolve();build=a.build.resolve();out=a.out.resolve()
    build.relative_to(lab/'results');out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    for name,digest in PINS.items():need(sha(build/name)==digest,'program or library differs: '+name)
    system_before={path:sha(path) for path in SYSTEM};need(system_before==SYSTEM,'system profile differs')
    build_manifest=build/'build.json'
    if build_manifest.exists():
        build_data=json.loads(build_manifest.read_text())
        for name,digest in build_data['files_SHA256'].items():need(sha(build/name)==digest,'build snapshot differs: '+name)
    module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs')
    source_hashes={n:sha(build/n) for n in ('host','repair_host.mm','import.mm')}
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module)
    reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    lease=reservation.GPUReservation(lab);child=None
    try:
        out.mkdir();(out/'outputs').mkdir();binary=out/'application';library=out/'shader.metallib'
        shutil.copyfile(build/'host',binary);shutil.copyfile(build/'shader.metallib',library);binary.chmod(0o755)
        need(sha(binary)==source_hashes['host'] and sha(library)==PINS['shader.metallib'],'snapshot differs')
        subprocess.run(['codesign','--force','--sign','-',str(binary)],capture_output=True,check=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(binary)],capture_output=True,check=True,timeout=15)
        lease.spawning(binary,sha(binary));registry=lab/'results/signed-native-jobs.json'
        jobs=json.loads(registry.read_text()) if registry.exists() else []
        original='wrong-original.sass' if a.mode=='negative-pin' else 'original.sass'
        replacement={'native':'original.sass','replay':'original.sass','trampoline':'trampoline.sass',
                     'repaired':'repaired.sass','negative-pin':'repaired.sass'}[a.mode]
        argv=[str(library),str(out/'outputs'),a.mode,str(build/original),str(build/replacement)]
        with (out/'report.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(binary),*argv],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,))
            lease.bind_child(child.pid)
            job={'started_at':now(),'pid':child.pid,'original_executable':str(build/'host'),
                 'original_binary_sha256':source_hashes['host'],'signed_executable':str(binary),
                 'signed_binary_sha256':sha(binary),'arguments':argv}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid,'mode':a.mode}),flush=True)
            code=child.wait()
        ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(ps.returncode in (0,1) and not ps.stderr,'cannot confirm process state')
        state=ps.stdout.strip();job.update(exit_code=code,SIGKILL_requested=False,
                                           authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        system_after={path:sha(path) for path in SYSTEM}
        (out/'manifest.json').write_text(json.dumps({**job,'GPU_reservation':dict(lease.data),
           'source_SHA256':source_hashes,'code_SHA256':PINS,'runner_SHA256':sha(__file__),
           'system_before':system_before,'system_after':system_after,
           'build_manifest_SHA256':sha(build_manifest) if build_manifest.exists() else None},indent=2)+'\n')
        need(code==(4 if a.mode=='negative-pin' else 0) and not state,'unexpected process result')
        need(system_after==system_before,'system profile changed during run')
        for name,digest in PINS.items():need(sha(build/name)==digest,'input changed during execution')
        data=json.loads((out/'report.json').read_text())
        if a.mode=='negative-pin':
            need(data['failure_stage']=='pipeline' and not data['GPU_dispatch'] and
                 not data['import']['contract_verified'],'wrong pin not refused')
        else:need(data['device']=='NVIDIA GeForce GTX 880M' and data['GPU_dispatch'] and len(data['runs'])==48,'unexpected GPU report')
        print(json.dumps({'status':'TERMINAL','mode':a.mode,'exit_code':code,'user_GPU_dispatch':data['GPU_dispatch']}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally:lease.close()


if __name__=='__main__':main()
