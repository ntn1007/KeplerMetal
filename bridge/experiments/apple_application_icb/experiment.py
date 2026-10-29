#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a bounded, local copy of the Apple NSApplicationMain sample and run it."""
import argparse,datetime,hashlib,importlib.util,json,os,plistlib,shutil,subprocess,sys
from pathlib import Path
from adapt import adapt,EXPECTED
from adapt_controller import adapt_controller,CONTROLLER_HASHES
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
MAIN_SHA='3e4e4b192dd637bbff74ca0d0cd4084e962c591aedd64ad6067a1f373b5da9fa'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,why):
    if not x:raise ValueError(why)
def command(args):
    r=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120)
    need(r.returncode==0,str(args[0])+' failed: '+r.stderr[-2500:]);return r.stdout
def tree(root):
    entries=sorted(root.rglob('*'));need(not any(x.is_symlink() for x in entries),'symbolic links forbidden in frozen tree')
    return {str(x.relative_to(root)):sha(x) for x in entries if x.is_file()}
def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='action',required=True)
    b=subs.add_parser('build')
    for n in ('lab','archive','sample','legacy','vertex','manifest','out'):b.add_argument('--'+n,type=Path,required=True)
    r=subs.add_parser('run')
    for n in ('lab','build','out'):r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--mode',choices=('direct','auto','blank'),required=True)
    a=p.parse_args();lab=a.lab.resolve();out=a.out.resolve();out.relative_to(lab/'results');need(not out.exists() and out.parent.is_dir(),'fresh output required')
    if a.action=='build':
        ar=a.archive.resolve();sample=a.sample.resolve();manifest=json.loads((ar/'manifest.json').read_text());need(manifest['status']=='PASS' and not manifest['GPU_execution'] and sha(ar/'libKeplerMetal.a')==manifest['static_library_SHA256'],'archive differs')
        for n,h in manifest['source_SHA256'].items():need(sha(ar/'src'/n)==sha(BRIDGE/'src'/n)==h,'runtime source '+n)
        need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311' and sha(sample/'source/Application/main.m')==MAIN_SHA and {k:sha(k) for k in SYSTEM}==SYSTEM,'sample or system differs')
        assets={'legacy.metallib':(a.legacy,'965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'),'vertex.metallib':(a.vertex,'adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf'),'profiles.json':(a.manifest,'6930ed313d2e1b1e836f189afb2db7c0286f10afb9c867ec3fe9659390e16732')}
        out.mkdir();local=out/'local';local.mkdir();adapt(sample/'source/Renderer',local);adapt_controller(sample/'source/Application',local);shutil.copyfile(HERE/'lab_runtime.mm',local/'lab_runtime.mm')
        controller=local/'AAPLViewController.m';s=controller.read_text();need(s.count('@end')==1,'controller end');s=s.replace('@end','''- (void)viewDidAppear { [super viewDidAppear]; dispatch_async(dispatch_get_main_queue(), ^{ KMRunOnView((MTKView *)self.view); }); }\n@end''');s=s.replace('#import "AAPLRenderer.h"','#import "AAPLRenderer.h"\nextern void KMRunOnView(MTKView *);');controller.write_text(s)
        s=(sample/'source/Application/main.m').read_text();old='return NSApplicationMain(argc, argv);';need(s.count(old)==1 and s.count('#import <Cocoa/Cocoa.h>')==1,'main anchors');s=s.replace('#import <Cocoa/Cocoa.h>','#import <Cocoa/Cocoa.h>\nextern void KMInitialize(int,const char **);');s=s.replace(old,'KMInitialize(argc, argv); const char *appArgs[]={argv[0],NULL}; return NSApplicationMain(1, appArgs);');(local/'main.m').write_text(s)
        for n,(src,h) in assets.items():need(sha(src)==h,'asset '+n);shutil.copyfile(src,out/n)
        base=sample/'derived/Build/Products/Debug/Indirect Command Buffers on CPU.app';need(base.is_dir(),'original xcode-built bundle missing');app=out/'Sample.app';shutil.copytree(base,app,symlinks=True)
        info=app/'Contents/Info.plist';data=plistlib.loads(info.read_bytes());need(data.get('NSMainStoryboardFile')=='Main' and data.get('CFBundleExecutable')=='Indirect Command Buffers on CPU','bundle profile');data['LSUIElement']=True;data['CFBundleIdentifier']='org.keplermetal.local-apple-icb-test';info.write_bytes(plistlib.dumps(data))
        storyboard=app/'Contents/Resources/Base.lproj/Main.storyboardc';need(storyboard.is_dir(),'compiled storyboard missing');shutil.rmtree(storyboard);command(['xcrun','ibtool','--compile',storyboard,sample/'source/Application/macOS/Base.lproj/Main.storyboard'])
        for name in ('AAPLRenderer','AAPLViewController','main'):
            command(['xcrun','clang','-arch','x86_64','-O2','-fobjc-arc','-fmodules','-I',ar/'src','-I',local,'-DTARGET_MACOS=1','-c',local/(name+'.m'),'-o',local/(name+'.o')])
        executable=out/'application';app_executable=app/'Contents/MacOS/Indirect Command Buffers on CPU'
        command(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-fmodules','-fcxx-modules','-I',ar/'src','-I',local,local/'lab_runtime.mm',local/'AAPLRenderer.o',local/'AAPLViewController.o',local/'main.o',ar/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-framework','QuartzCore','-framework','AppKit','-framework','MetalKit','-o',executable])
        command(['codesign','--force','--sign','-',executable]);command(['codesign','--verify','--strict',executable]);shutil.copyfile(executable,app_executable);app_executable.chmod(0o755);need(sha(app_executable)==sha(executable),'executable copy differs');record={'status':'PREPARED_ONLY','archive_sha256':sha(ar/'libKeplerMetal.a'),'archive_manifest_sha256':sha(ar/'manifest.json'),'sample_main_sha256':MAIN_SHA,'apple_source_sha256':EXPECTED,'controller_source_sha256':CONTROLLER_HASHES,'adapt_sha256':sha(HERE/'adapt.py'),'controller_adapt_sha256':sha(HERE/'adapt_controller.py'),'lab_runtime_sha256':sha(HERE/'lab_runtime.mm'),'executable_sha256':sha(executable),'local_files_sha256':tree(local),'bundle_files_sha256':tree(app),'assets_sha256':{n:sha(out/n) for n in assets},'system':SYSTEM,'gpu_execution':False};(out/'build.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':'PREPARED_ONLY','gpu_execution':False}));return
    build=a.build.resolve();build.relative_to(lab/'results');record=json.loads((build/'build.json').read_text());need(record['status']=='PREPARED_ONLY' and record['system']==SYSTEM and {k:sha(k) for k in SYSTEM}==SYSTEM,'build/system differs');need(record['adapt_sha256']==sha(HERE/'adapt.py') and record['controller_adapt_sha256']==sha(HERE/'adapt_controller.py') and record['lab_runtime_sha256']==sha(HERE/'lab_runtime.mm') and tree(build/'local')==record['local_files_sha256'] and tree(build/'Sample.app')==record['bundle_files_sha256'] and all(sha(build/n)==h for n,h in record['assets_sha256'].items()),'build files differ');need(sha(build/'application')==record['executable_sha256'],'signed executable differs');command(['codesign','--verify','--strict',build/'application'])
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py';need(sha(leasepath)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs');spec=importlib.util.spec_from_file_location('application_reservation',leasepath);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);lease=mod.GPUReservation(lab);child=None;terminal=False
    try:
        out.mkdir();(out/'outputs').mkdir();app=out/'Sample.app';shutil.copytree(build/'Sample.app',app,symlinks=True);need(tree(app)==record['bundle_files_sha256'],'bundle copy');host=app/'Contents/MacOS/Indirect Command Buffers on CPU';shutil.copyfile(build/'application',out/'signed-application');command(['codesign','--verify','--strict',out/'signed-application']);need(sha(host)==sha(out/'signed-application')==record['executable_sha256'],'signed host differs');args=[str(build/'legacy.metallib'),str(build/'vertex.metallib'),str(build/'profiles.json'),str(out/'outputs'),a.mode];env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};lease.spawning(host,sha(host));started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(host),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env);lease.bind_child(child.pid);print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True);code=child.wait()
        table=mod.process_table();need(child.pid not in table and not any(x['command']==str(host) or x['command'].startswith(str(host)+' ') for x in table.values()),'child still visible');terminal=True;lease.finish(code,False,'')
        result={'status':'TERMINAL','exit_code':code,'pid':child.pid,'mode':a.mode,'started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'host_sha256':sha(host),'bundle_files_sha256':tree(app),'build_sha256':sha(build/'build.json'),'runner_sha256':sha(Path(__file__)),'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'system_before':SYSTEM,'system_after':{k:sha(k) for k in SYSTEM}}
        (out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');need(code==0 and result['system_after']==SYSTEM,'run failed or system differs');report=json.loads((out/'stdout.json').read_text());need(report['status']=='PASS' and report['mode']==a.mode,'client differs');print(json.dumps({'status':'TERMINAL','cases':len(report['cases'])}),flush=True)
    except BaseException:
        if lease.fd is not None and (child is None or not terminal):lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
        raise
    finally:lease.close()
if __name__=='__main__':main()
