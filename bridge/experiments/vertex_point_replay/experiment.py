#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/run a native direct-render witness with the shared iMac GPU lease."""
import argparse, datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok, why):
    if not ok: raise ValueError(why)
def cmd(args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120)
    need(r.returncode==0,str(args[0])+' failed: '+r.stderr[-2000:]); return r

def main():
    p=argparse.ArgumentParser(description=__doc__); s=p.add_subparsers(dest='action',required=True)
    for name in ('build','run'):
        q=s.add_parser(name);q.add_argument('--lab',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
        if name=='run':
            q.add_argument('--build',type=Path,required=True);q.add_argument('--mode',choices=('direct','replay'),required=True)
    a=p.parse_args(); lab=a.lab.resolve();out=a.out.resolve();out.relative_to(lab/'results');need(not out.exists() and out.parent.is_dir(),'fresh output required')
    before={k:sha(k) for k in SYSTEM};need(before==SYSTEM,'system differs')
    if a.action=='build':
        out.mkdir(); shutil.copyfile(HERE/'client.mm',out/'client.mm')
        built=cmd(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'client.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
        (out/'compiler.log').write_text(built.stderr);cmd(['codesign','--force','--sign','-',out/'application']);cmd(['codesign','--verify','--strict',out/'application'])
        record={'status':'PREPARED_ONLY','gpu_execution':False,'system':before,'files_sha256':{x.name:sha(x) for x in out.iterdir() if x.is_file()}}
        (out/'build.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':'PREPARED_ONLY'}));return
    build=a.build.resolve();build.relative_to(lab/'results');record=json.loads((build/'build.json').read_text());need(record['status']=='PREPARED_ONLY' and record['system']==before,'build differs')
    for name,h in record['files_sha256'].items():need(sha(build/name)==h,'file differs '+name)
    need(sha(build/'client.mm')==sha(HERE/'client.mm'),'source differs')
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py';need(sha(leasepath)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','lease differs')
    spec=importlib.util.spec_from_file_location('point_replay_witness_reservation',leasepath);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);lease=mod.GPUReservation(lab);child=None;terminal=False
    try:
        out.mkdir();shutil.copyfile(build/'application',out/'application');host=out/'application';host.chmod(0o755);need(sha(host)==record['files_sha256']['application'],'host differs');cmd(['codesign','--verify','--strict',host])
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};lease.spawning(host,sha(host));start=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(host),a.mode],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env);lease.bind_child(child.pid);print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True);code=child.wait()
        table=mod.process_table();need(child.pid not in table and not any(x['command']==str(host) or x['command'].startswith(str(host)+' ') for x in table.values()),'child still visible');terminal=True;lease.finish(code,False,'')
        m={'status':'TERMINAL','mode':a.mode,'exit_code':code,'pid':child.pid,'started_at':start,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'host_sha256':sha(host),'build_sha256':sha(build/'build.json'),'runner_sha256':sha(Path(__file__)),'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'system_before':before,'system_after':{k:sha(k) for k in SYSTEM}}
        (out/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');need(m['system_after']==SYSTEM,'system differs after run');print(json.dumps({'status':'TERMINAL','exit_code':code}),flush=True)
    except BaseException:
        if lease.fd is not None and (child is None or not terminal):lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
        raise
    finally:lease.close()
if __name__=='__main__':main()
