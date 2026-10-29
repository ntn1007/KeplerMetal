#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Launch one pinned Apple Release bundle using its own default library bytes."""
import argparse, datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
sys.path.insert(0, str(BRIDGE / 'experiments/cas_divergence'))
from run_repair import SYSTEM
sys.path.insert(0, str(BRIDGE / 'experiments/apple_application_icb'))
from adapt import EXPECTED
from adapt_controller import CONTROLLER_HASHES

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok, why):
    if not ok: raise ValueError(why)
def cmd(args):
    r = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=120)
    need(r.returncode == 0, str(args[0]) + ': ' + r.stderr[-3000:])
    return r.stdout
def tree(path):
    files = sorted(path.rglob('*'))
    need(not any(p.is_symlink() for p in files), 'bundle contains symlink')
    return {str(p.relative_to(path)): sha(p) for p in files if p.is_file()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    b = sub.add_parser('build')
    for k in ('lab', 'archive', 'sample', 'release', 'build-log', 'carrier', 'shader', 'profiles', 'out'): b.add_argument('--'+k, type=Path, required=True)
    r = sub.add_parser('run')
    for k in ('lab', 'build', 'out'): r.add_argument('--'+k, type=Path, required=True)
    a = parser.parse_args(); lab=a.lab.resolve(); out=a.out.resolve(); out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(), 'fresh output required')
    before = {k:sha(k) for k in SYSTEM}; need(before == SYSTEM, 'system profile differs')
    if a.action == 'build':
        ar=a.archive.resolve(); m=json.loads((ar/'manifest.json').read_text())
        need(m['status']=='PASS' and not m['GPU_execution'] and sha(ar/'libKeplerMetal.a')==m['static_library_SHA256'], 'archive differs')
        for n,h in m['source_SHA256'].items(): need(sha(ar/'src'/n)==sha(BRIDGE/'src'/n)==h, 'runtime source differs: '+n)
        sample=a.sample.resolve(); need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311', 'sample archive differs')
        for n,h in EXPECTED.items(): need(sha(sample/'source/Renderer'/n)==h, 'renderer differs '+n)
        for n,h in CONTROLLER_HASHES.items(): need(sha(sample/'source/Application'/n)==h, 'controller differs '+n)
        log=a.build_log.read_text(errors='replace'); need('** BUILD SUCCEEDED **' in log and 'NS_BLOCK_ASSERTIONS' in log and 'Release' in log, 'Release build evidence differs')
        app=a.release.resolve(); need(app.is_dir(), 'Release bundle missing')
        binary=app/'Contents/MacOS/Indirect Command Buffers on CPU'; default=app/'Contents/Resources/default.metallib'
        need(binary.is_file() and default.is_file(), 'Release bundle contents missing')
        pins={'carrier.metallib':(a.carrier,'965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'), 'shader.metallib':(a.shader,'04d8d8ae6a4485d3be0262e971c365cfff1d5bb04f88f24cdbdfa0ffdee6afa2'), 'profiles.json':(a.profiles,'b5798a3c5129c4cec893c487cbc9211a439deaedd14a1c3a4857114a949e0ace')}
        for src,h in pins.values(): need(sha(src)==h, 'input asset differs')
        need(default.read_bytes()==a.shader.read_bytes(),'shader must equal Release bundle default library byte for byte')
        out.mkdir(); shutil.copytree(app,out/'Sample.app'); shutil.copyfile(binary,out/'application'); (out/'application').chmod(0o755)
        cmd(['codesign','--force','--sign','-',out/'application']); cmd(['codesign','--verify','--strict',out/'application'])
        host=out/'Sample.app/Contents/MacOS/Indirect Command Buffers on CPU'; shutil.copyfile(out/'application',host); host.chmod(0o755)
        for n,(src,_) in pins.items(): shutil.copyfile(src,out/n)
        shutil.copyfile(HERE/'bootstrap.mm',out/'bootstrap.mm')
        apphash=sha(host); defaultsha=sha(default)
        cmd(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-dynamiclib','-I',ar/'src','-DKM_APPROVED_APP_SHA256="'+apphash+'"','-DKM_DEFAULT_LIBRARY_SHA256="'+defaultsha+'"',out/'bootstrap.mm',ar/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-framework','AppKit','-framework','MetalKit','-framework','QuartzCore','-o',out/'bootstrap.dylib'])
        cmd(['codesign','--force','--sign','-',out/'bootstrap.dylib']); cmd(['codesign','--verify','--strict',out/'bootstrap.dylib'])
        record={'status':'PREPARED_ONLY','gpu_execution':False,'system':before,'archive_sha256':sha(ar/'libKeplerMetal.a'),'archive_manifest_sha256':sha(ar/'manifest.json'),'apple_archive_sha256':sha(sample/'AppleSample.zip'),'xcode_original_executable_sha256':sha(binary),'release_default_library_sha256':defaultsha,'xcode_build_log_sha256':sha(a.build_log),'ns_block_assertions_in_build_log':True,'signed_executable_sha256':apphash,'bundle_files_sha256':tree(out/'Sample.app'),'files_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
        (out/'build.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n'); print(json.dumps({'status':'PREPARED_ONLY','gpu_execution':False})); return
    build=a.build.resolve(); build.relative_to(lab/'results'); record=json.loads((build/'build.json').read_text())
    need(record['status']=='PREPARED_ONLY' and record['system']==before and tree(build/'Sample.app')==record['bundle_files_sha256'], 'build/system differs')
    for n,h in record['files_sha256'].items(): need(sha(build/n)==h, 'build file differs '+n)
    need(sha(build/'bootstrap.mm')==sha(HERE/'bootstrap.mm'), 'bootstrap source differs')
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'; need(sha(leasepath)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs')
    spec=importlib.util.spec_from_file_location('apple_original_reservation',leasepath); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); lease=mod.GPUReservation(lab); child=None; terminal=False
    try:
        out.mkdir(); shutil.copytree(build/'Sample.app',out/'Sample.app'); need(tree(out/'Sample.app')==record['bundle_files_sha256'],'bundle copy differs')
        host=out/'Sample.app/Contents/MacOS/Indirect Command Buffers on CPU'; cmd(['codesign','--verify','--strict',build/'application']); cmd(['codesign','--verify','--strict',build/'bootstrap.dylib']); need(sha(host)==record['signed_executable_sha256'],'host differs')
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))}; env.update({'DYLD_INSERT_LIBRARIES':str(build/'bootstrap.dylib'),'KM_CARRIER_PATH':str(build/'carrier.metallib'),'KM_SHADER_PATH':str(build/'shader.metallib'),'KM_MANIFEST_PATH':str(build/'profiles.json'),'KM_REPORT_PATH':str(out/'report.json')})
        lease.spawning(host,sha(host)); started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(host)],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env); lease.bind_child(child.pid); print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True); code=child.wait()
        table=mod.process_table(); need(child.pid not in table and not any(x['command']==str(host) or x['command'].startswith(str(host)+' ') for x in table.values()),'child still visible'); terminal=True; lease.finish(code,False,'')
        result={'status':'TERMINAL','exit_code':code,'pid':child.pid,'started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'build_sha256':sha(build/'build.json'),'runner_sha256':sha(HERE/'experiment.py'),'host_sha256':sha(host),'bootstrap_sha256':sha(build/'bootstrap.dylib'),'stdout_sha256':sha(out/'stdout.log'),'stderr_sha256':sha(out/'stderr.log'),'report_sha256':sha(out/'report.json') if (out/'report.json').is_file() else None,'frames_sha256':{p.name:sha(p) for p in sorted(out.glob('frame-*.bin'))},'system_before':before,'system_after':{k:sha(k) for k in SYSTEM}}
        (out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); need(result['system_after']==before,'system differs');need(code==0 and result['report_sha256'] and len(result['frames_sha256'])==8,'missing captures'); print(json.dumps({'status':'TERMINAL','exit_code':code,'frames':len(result['frames_sha256'])}),flush=True)
    except BaseException:
        if lease.fd is not None and (child is None or not terminal): lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
        raise
    finally: lease.close()
if __name__=='__main__': main()
