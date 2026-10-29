#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and run the bounded state-guard client under the lab reservation."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
from adapt import adapt,EXPECTED
from adapt_controller import adapt_controller,CONTROLLER_HASHES

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def command(args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120)
    need(r.returncode==0,str(args[0])+' failed: '+r.stderr[-1500:]);return r.stdout
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build')
    for n in ('lab','archive','legacy','vertex','manifest','sample','out'):b.add_argument('--'+n,type=Path,required=True)
    r=sub.add_parser('run')
    for n in ('lab','build','out','storyboard-build'):r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--mode',choices=('direct','auto','blank'),required=True)
    a=p.parse_args();lab=a.lab.resolve();out=a.out.resolve();out.relative_to(lab/'results');need(not out.exists() and out.parent.is_dir(),'fresh output required')
    if a.action=='build':
        ar=a.archive.resolve();manifest=json.loads((ar/'manifest.json').read_text());need(manifest['status']=='PASS' and not manifest['GPU_execution'] and sha(ar/'libKeplerMetal.a')==manifest['static_library_SHA256'],'archive differs')
        old_core='e7561f8f60f9fde126db7e7eb6b8913235582924d1f9fb2c0c163dc37cad2367';new_core='8212f9cece201bba4e231e4795c6fb0b380c638992cd75f05ef28af14e627b4e'
        need(sha(BRIDGE/'src'/'KeplerCPUICB.mm')==new_core and manifest['source_SHA256']['KeplerCPUICB.mm'] in (old_core,new_core),'benchmark source revisions differ')
        for name,digest in manifest['source_SHA256'].items():need(sha(ar/'src'/name)==digest and (name=='KeplerCPUICB.mm' or sha(BRIDGE/'src'/name)==digest),'source differs: '+name)
        assets={'legacy.metallib':(a.legacy,'965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'), 'vertex.metallib':(a.vertex,'adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf'), 'profiles.json':(a.manifest,'6930ed313d2e1b1e836f189afb2db7c0286f10afb9c867ec3fe9659390e16732')}
        need({k:sha(k) for k in SYSTEM}==SYSTEM,'system differs');need(sha(a.sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','Apple archive differs');out.mkdir();shutil.copyfile(HERE/'client.mm',out/'client.mm');adapt(a.sample/'source'/'Renderer',out);adapt_controller(a.sample/'source'/'Application',out)
        for name,(src,pin) in assets.items():need(sha(src)==pin,'asset differs: '+name);shutil.copyfile(src,out/name)
        command(['xcrun','clang','-arch','x86_64','-O2','-fobjc-arc','-fmodules','-I',ar/'src','-I',out,'-DTARGET_MACOS=1','-c',out/'AAPLRenderer.m','-o',out/'renderer.o'])
        command(['xcrun','clang','-arch','x86_64','-O2','-fobjc-arc','-fmodules','-I',ar/'src','-I',out,'-DTARGET_MACOS=1','-c',out/'AAPLViewController.m','-o',out/'controller.o'])
        resources=out/'Storyboard.bundle'/'Contents'/'Resources';resources.mkdir(parents=True);(resources.parent/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'org.keplermetal.storyboard-test','CFBundlePackageType':'BNDL','CFBundleVersion':'1'}));command(['xcrun','ibtool','--compile',resources/'Main.storyboardc',a.sample/'source'/'Application'/'macOS'/'Base.lproj'/'Main.storyboard'])
        command(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-fmodules','-fcxx-modules','-I',ar/'src','-I',out,'-DTARGET_MACOS=1',out/'client.mm',out/'renderer.o',out/'controller.o',ar/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-framework','QuartzCore','-framework','AppKit','-framework','MetalKit','-o',out/'application'])
        command(['codesign','--force','--sign','-',out/'application']);command(['codesign','--verify','--strict',out/'application'])
        record={'status':'PREPARED_ONLY','archive_sha256':sha(ar/'libKeplerMetal.a'),'archive_manifest_sha256':sha(ar/'manifest.json'),'adapt_sha256':sha(HERE/'adapt.py'),'controller_adapt_sha256':sha(HERE/'adapt_controller.py'),'controller_source_sha256':CONTROLLER_HASHES,'storyboard_files_sha256':{str(x.relative_to(out)):sha(x) for x in (out/'Storyboard.bundle').rglob('*') if x.is_file()},'apple_source_sha256':EXPECTED,'files_sha256':{x.name:sha(x) for x in out.iterdir() if x.is_file()},'system':SYSTEM,'gpu_execution':False}
        (out/'build.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':'PREPARED_ONLY','gpu_execution':False}));return
    build=a.build.resolve();build.relative_to(lab/'results');record=json.loads((build/'build.json').read_text());need(record['status']=='PREPARED_ONLY' and record['system']==SYSTEM and {k:sha(k) for k in SYSTEM}==SYSTEM,'build/system differs')
    for name,digest in record['files_sha256'].items():need(sha(build/name)==digest,'build differs '+name)
    need(sha(build/'client.mm')==sha(HERE/'client.mm') and record['adapt_sha256']==sha(HERE/'adapt.py') and record['controller_adapt_sha256']==sha(HERE/'adapt_controller.py'),'client or adaptation differs')
    need({str(x.relative_to(build)):sha(x) for x in (build/'Storyboard.bundle').rglob('*') if x.is_file()}==record['storyboard_files_sha256'] and bool(record['storyboard_files_sha256']),'storyboard differs')
    storyboard_build=a.storyboard_build.resolve();storyboard_build.relative_to(lab/'results');storyboard_record=json.loads((storyboard_build/'build.json').read_text());need(storyboard_record['status']=='PREPARED_ONLY' and storyboard_record['controller_source_sha256']==CONTROLLER_HASHES and storyboard_record['controller_adapt_sha256']==sha(HERE/'adapt_controller.py') and bool(storyboard_record['storyboard_files_sha256']) and {str(x.relative_to(storyboard_build)):sha(x) for x in (storyboard_build/'Storyboard.bundle').rglob('*') if x.is_file()}==storyboard_record['storyboard_files_sha256'],'shared storyboard differs')
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py';need(sha(leasepath)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs')
    spec=importlib.util.spec_from_file_location('state_guard_reservation',leasepath);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);lease=mod.GPUReservation(lab);child=None;terminal=False
    try:
        out.mkdir();(out/'outputs').mkdir();shutil.copyfile(build/'application',out/'application');host=out/'application';host.chmod(0o755);need(sha(host)==record['files_sha256']['application'],'host differs');command(['codesign','--verify','--strict',host])
        args=[str(build/'legacy.metallib'),str(build/'vertex.metallib'),str(build/'profiles.json'),str(out/'outputs'),a.mode,str(storyboard_build/'Storyboard.bundle')]
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};lease.spawning(host,sha(host));started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(host),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env);lease.bind_child(child.pid);print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True);code=child.wait()
        table=mod.process_table();need(child.pid not in table and not any(x['command']==str(host) or x['command'].startswith(str(host)+' ') for x in table.values()),'child still visible');terminal=True;lease.finish(code,False,'')
        result={'status':'TERMINAL','exit_code':code,'pid':child.pid,'mode':a.mode,'args':args,'started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'host_sha256':sha(host),'build_sha256':sha(build/'build.json'),'storyboard_build_sha256':sha(storyboard_build/'build.json'),'runner_sha256':sha(Path(__file__)),'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'system_before':SYSTEM,'system_after':{k:sha(k) for k in SYSTEM}}
        (out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');need(code==0 and result['system_after']==SYSTEM,'run failed or system differs');report=json.loads((out/'stdout.json').read_text());need(report['status']=='PASS' and report['mode']==a.mode,'client differs');print(json.dumps({'status':'TERMINAL','cases':len(report['cases'])}),flush=True)
    except BaseException:
        if lease.fd is not None and (child is None or not terminal):lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
        raise
    finally:lease.close()
if __name__=='__main__':main()
