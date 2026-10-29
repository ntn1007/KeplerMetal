#!/usr/bin/env python3
"""Build and run the bounded empty-render client with a cooperative no-kill lease."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
sys.path.insert(0, str(BRIDGE / 'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value, why):
    if not value: raise ValueError(why)
def timestamp(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def command(args, cwd=None):
    p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True, timeout=120)
    need(p.returncode == 0, 'command failed: ' + str(args[0]) + '\n' + p.stderr[-3000:])
    return p

def build(a):
    out, archive, carrier = a.out.resolve(), a.archive.resolve(), a.carrier.resolve()
    need(not out.exists() and out.parent.is_dir(), 'fresh build path required')
    m = json.loads((archive / 'manifest.json').read_text())
    need(m['status'] == 'PASS' and m['GPU_execution'] is False and sha(archive/'libKeplerMetal.a') == m['static_library_SHA256'], 'archive differs')
    for name, digest in m['source_SHA256'].items(): need(sha(archive/'src'/name) == digest == sha(BRIDGE/'src'/name), 'runtime source differs: '+name)
    need(sha(carrier) == '965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7', 'carrier differs')
    need({p:sha(p) for p in SYSTEM} == SYSTEM, 'installed profile differs')
    out.mkdir()
    shutil.copyfile(HERE/'kepler_client.mm', out/'client.mm')
    shutil.copyfile(HERE.parent/'standalone_icb/bootstrap.mm', out/'bootstrap.mm')
    shutil.copyfile(carrier, out/'carrier.metallib')
    command(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'client.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
    command(['codesign','--force','--sign','-',out/'application'])
    command(['codesign','--verify','--strict',out/'application'])
    app_hash=sha(out/'application')
    command(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-dynamiclib','-I',archive/'src',
             '-DKM_APPROVED_APP_SHA256="'+app_hash+'"',out/'bootstrap.mm',archive/'libKeplerMetal.a','-Wl,-ObjC',
             '-framework','Metal','-framework','Foundation','-o',out/'bootstrap.dylib'])
    command(['codesign','--force','--sign','-',out/'bootstrap.dylib'])
    command(['codesign','--verify','--strict',out/'bootstrap.dylib'])
    files={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'build.json').write_text(json.dumps({'files_SHA256':files,'source_manifest_SHA256':sha(archive/'manifest.json'),
        'archive_SHA256':m['static_library_SHA256'],'system':SYSTEM,'GPU_execution':False},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED','GPU_execution':False,'files_SHA256':files}),flush=True)

def run(a):
    lab, build, out = a.lab.resolve(), a.build.resolve(), a.out.resolve()
    for path in (build, out): path.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(), 'fresh run path required')
    m=json.loads((build/'build.json').read_text())
    for name,digest in m['files_SHA256'].items(): need(sha(build/name)==digest, 'build changed: '+name)
    need(sha(build/'client.mm')==sha(HERE/'kepler_client.mm') and sha(build/'bootstrap.mm')==sha(HERE.parent/'standalone_icb/bootstrap.mm'), 'test source changed')
    need({p:sha(p) for p in SYSTEM} == SYSTEM, 'installed profile differs')
    module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation implementation differs')
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module)
    reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    lease=reservation.GPUReservation(lab);child=None
    try:
        out.mkdir();(out/'outputs').mkdir();binary=out/'application';shutil.copyfile(build/'application',binary);binary.chmod(0o755)
        need(sha(binary)==m['files_SHA256']['application'],'application differs')
        command(['codesign','--verify','--strict',binary]);command(['codesign','--verify','--strict',build/'bootstrap.dylib'])
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_'))}
        if a.mode=='auto':
            env['DYLD_INSERT_LIBRARIES']=str(build/'bootstrap.dylib');env['KM_CARRIER_PATH']=str(build/'carrier.metallib');env['KM_EVENT_PATH']=str(out/'events.json')
        args=[str(build/'carrier.metallib'),a.mode,str(out/'outputs')]
        lease.spawning(binary,sha(binary));registry=lab/'results/signed-native-jobs.json';jobs=json.loads(registry.read_text()) if registry.exists() else []
        started=timestamp()
        with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(binary),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env)
            lease.bind_child(child.pid)
            job={'started_at':started,'pid':child.pid,'original_executable':str(build/'application'),'original_binary_sha256':sha(build/'application'),
                 'signed_executable':str(binary),'signed_binary_sha256':sha(binary),'arguments':args}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid,'mode':a.mode}),flush=True)
            code=child.wait()
        ps=command(['ps','-axo','pid=,command=']).stdout.splitlines()
        state=[line.strip() for line in ps if line.strip().split(None,1)[0]==str(child.pid)]
        job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=timestamp())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,'\n'.join(state))
        after={p:sha(p) for p in SYSTEM}
        result={**job,'mode':a.mode,'GPU_reservation':dict(lease.data),'system_before':SYSTEM,'system_after':after,
                'build_sha256':sha(build/'build.json'),'injected_sha256':sha(build/'bootstrap.dylib') if a.mode=='auto' else None}
        (out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        need(code==0 and not state and after==SYSTEM,'process failed or profile changed')
        for name,digest in m['files_SHA256'].items():need(sha(build/name)==digest,'build changed: '+name)
        report=json.loads((out/'stdout.json').read_text());need(report['status']=='PASS' and report['mode']==a.mode,'client result differs')
        if a.mode=='auto':
            events=json.loads((out/'events.json').read_text())
            executed=[e for e in events if e['operation']=='execute_CPU_render_ICB']
            need(len(executed)==7 and [e['executed_indices'] for e in executed]==[[0],[],[],[0],[],[],[0]],'render trace differs')
        print(json.dumps({'status':'TERMINAL','mode':a.mode,'cases':len(report['cases'])}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally: lease.close()

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(required=True)
    b=subs.add_parser('build')
    for name in ('out','archive','carrier'):b.add_argument('--'+name,type=Path,required=True)
    b.set_defaults(func=build)
    r=subs.add_parser('run')
    for name in ('lab','build','out'):r.add_argument('--'+name,type=Path,required=True)
    r.add_argument('--mode',choices=('direct','auto'),required=True);r.set_defaults(func=run)
    args=p.parse_args();args.func(args)
