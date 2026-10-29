#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and launch two signed Apple sample builds with one scoped policy bootstrap."""
import argparse, datetime, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/apple_original_bootstrap'))
from experiment import SYSTEM, EXPECTED, CONTROLLER_HASHES, sha, need, cmd, tree

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build')
    for n in ('lab','archive','sample','app-a','app-b','log-a','log-b','carrier','profiles','out'): b.add_argument('--'+n,type=Path,required=True)
    r=sub.add_parser('run')
    for n in ('lab','build','out'): r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--client',choices=('a','b'),required=True);r.add_argument('--policy',choices=('a','ab'),required=True)
    r.add_argument('--case',choices=('normal','denied-client','wrong-policy-hash'),default='normal')
    a=p.parse_args(); lab=a.lab.resolve();out=a.out.resolve();out.relative_to(lab/'results');need(not out.exists() and out.parent.is_dir(),'fresh output required');before={k:sha(k) for k in SYSTEM};need(before==SYSTEM,'system profile differs')
    if a.action=='build':
        ar=a.archive.resolve();m=json.loads((ar/'manifest.json').read_text());need(m['status']=='PASS' and not m['GPU_execution'] and sha(ar/'libKeplerMetal.a')==m['static_library_SHA256'],'archive differs')
        for n,h in m['source_SHA256'].items():need(sha(ar/'src'/n)==sha(BRIDGE/'src'/n)==h,'runtime source differs '+n)
        sample=a.sample.resolve();need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','Apple archive differs')
        for n,h in EXPECTED.items():need(sha(sample/'source/Renderer'/n)==h,'renderer differs '+n)
        for n,h in CONTROLLER_HASHES.items():need(sha(sample/'source/Application'/n)==h,'controller differs '+n)
        for log in (a.log_a,a.log_b):
            text=log.read_text(errors='replace');need('** BUILD SUCCEEDED **' in text and 'NS_BLOCK_ASSERTIONS' in text and 'Release' in text,'build log differs')
        need('-O1' in a.log_b.read_text(errors='replace'),'second build optimization is not evidenced')
        paths=[a.app_a.resolve(),a.app_b.resolve()];binary='Contents/MacOS/Indirect Command Buffers on CPU';default='Contents/Resources/default.metallib';want='04d8d8ae6a4485d3be0262e971c365cfff1d5bb04f88f24cdbdfa0ffdee6afa2'
        need(all((x/binary).is_file() and sha(x/default)==want for x in paths) and (paths[0]/default).read_bytes()==(paths[1]/default).read_bytes(),'bundle/library differs')
        need(sha(paths[0]/binary)!=sha(paths[1]/binary),'compiled executables identical')
        need(sha(a.carrier)=='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7' and sha(a.profiles)=='b5798a3c5129c4cec893c487cbc9211a439deaedd14a1c3a4857114a949e0ace','carrier or profile differs')
        out.mkdir(); apps={};
        for tag,source in zip(('a','b'),paths):
            bundle=out/('Sample-'+tag+'.app');shutil.copytree(source,bundle);sign_dir=out/('sign-'+tag);sign_dir.mkdir();host=sign_dir/'Indirect Command Buffers on CPU';shutil.copyfile(source/binary,host);host.chmod(0o755);cmd(['codesign','--force','--sign','-',host]);cmd(['codesign','--verify','--strict',host]);shutil.copyfile(host,bundle/binary);(bundle/binary).chmod(0o755)
            apps[tag]={'unsigned_sha256':sha(source/binary),'signed_sha256':sha(host),'bundle_sha256':tree(bundle)}
        need(apps['a']['signed_sha256']!=apps['b']['signed_sha256'],'signed executables identical')
        for n,src in (('carrier.metallib',a.carrier),('shader.metallib',paths[0]/default),('profiles.json',a.profiles)):shutil.copyfile(src,out/n)
        for n in ('bootstrap.mm','Policy.h','policy_tests.mm'):shutil.copyfile(HERE/n,out/n)
        for policy,clients in (('a',[apps['a']['signed_sha256']]),('ab',[apps['a']['signed_sha256'],apps['b']['signed_sha256']])):
            (out/('policy-'+policy+'.json')).write_text(json.dumps({'version':1,'allowed_clients':clients},sort_keys=True,indent=2)+'\n')
        cmd(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',ar/'src','-I',out,'-dynamiclib',out/'bootstrap.mm',ar/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-framework','AppKit','-framework','MetalKit','-framework','QuartzCore','-o',out/'bootstrap.dylib']);cmd(['codesign','--force','--sign','-',out/'bootstrap.dylib']);cmd(['codesign','--verify','--strict',out/'bootstrap.dylib'])
        cmd(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out,out/'policy_tests.mm','-framework','Foundation','-o',out/'policy_tests']);cmd(['codesign','--force','--sign','-',out/'policy_tests']);cmd(['codesign','--verify','--strict',out/'policy_tests']);test=cmd([out/'policy_tests']);(out/'policy-tests.json').write_text(test);need(json.loads(test)['status']=='PASS','policy tests failed')
        record={'status':'PREPARED_ONLY','gpu_execution':False,'system':before,'archive_sha256':m['static_library_SHA256'],'archive_manifest_sha256':sha(ar/'manifest.json'),'apple_archive_sha256':sha(sample/'AppleSample.zip'),'logs_sha256':{'a':sha(a.log_a),'b':sha(a.log_b)},'apps':apps,'files_sha256':{x.name:sha(x) for x in out.iterdir() if x.is_file()}}
        (out/'build.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':'PREPARED_ONLY','policy_tests':json.loads(test)}));return
    build=a.build.resolve();build.relative_to(lab/'results');record=json.loads((build/'build.json').read_text());need(record['status']=='PREPARED_ONLY' and record['system']==before,'build/system differs')
    for n,h in record['files_sha256'].items():need(sha(build/n)==h,'build file differs '+n)
    for n in ('bootstrap.mm','Policy.h','policy_tests.mm'):need(sha(build/n)==sha(HERE/n),'source differs '+n)
    for tag in ('a','b'):need(tree(build/('Sample-'+tag+'.app'))==record['apps'][tag]['bundle_sha256'],'bundle differs '+tag)
    selected=build/('policy-'+a.policy+'.json');policy=json.loads(selected.read_text());listed=record['apps'][a.client]['signed_sha256'] in policy['allowed_clients']
    need((a.case=='normal' and listed) or (a.case=='denied-client' and a.client=='b' and a.policy=='a' and not listed) or (a.case=='wrong-policy-hash' and listed),'client/policy case differs')
    expected_policy='0'*64 if a.case=='wrong-policy-hash' else sha(selected)
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py';need(sha(leasepath)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs');spec=importlib.util.spec_from_file_location('release_policy_reservation',leasepath);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);lease=mod.GPUReservation(lab);child=None;terminal=False
    try:
        out.mkdir();shutil.copytree(build/('Sample-'+a.client+'.app'),out/'Sample.app');need(tree(out/'Sample.app')==record['apps'][a.client]['bundle_sha256'],'bundle copy differs');host=out/'Sample.app/Contents/MacOS/Indirect Command Buffers on CPU';need(sha(host)==record['apps'][a.client]['signed_sha256'],'host differs');cmd(['codesign','--verify','--strict',build/('sign-'+a.client)/'Indirect Command Buffers on CPU']);cmd(['codesign','--verify','--strict',build/'bootstrap.dylib'])
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};env.update({'DYLD_INSERT_LIBRARIES':str(build/'bootstrap.dylib'),'KM_CARRIER_PATH':str(build/'carrier.metallib'),'KM_SHADER_PATH':str(build/'shader.metallib'),'KM_MANIFEST_PATH':str(build/'profiles.json'),'KM_REPORT_PATH':str(out/'report.json'),'KM_POLICY_PATH':str(selected),'KM_POLICY_SHA256':expected_policy})
        lease.spawning(host,sha(host));started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'stdout.log').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(host)],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env);lease.bind_child(child.pid);print(json.dumps({'status':'STARTED','pid':child.pid,'client':a.client,'policy':a.policy}),flush=True);code=child.wait()
        table=mod.process_table();need(child.pid not in table and not any(x['command']==str(host) or x['command'].startswith(str(host)+' ') for x in table.values()),'child still visible');terminal=True;lease.finish(code,False,'')
        result={'status':'TERMINAL','exit_code':code,'pid':child.pid,'client':a.client,'policy':a.policy,'case':a.case,'started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'build_sha256':sha(build/'build.json'),'runner_sha256':sha(HERE/'experiment.py'),'host_sha256':sha(host),'policy_sha256':sha(selected),'expected_policy_sha256':expected_policy,'bootstrap_sha256':sha(build/'bootstrap.dylib'),'stdout_sha256':sha(out/'stdout.log'),'stderr_sha256':sha(out/'stderr.log'),'report_sha256':sha(out/'report.json') if (out/'report.json').is_file() else None,'frame_sha256':sha(out/'frame.bin') if (out/'frame.bin').is_file() else None,'system_before':before,'system_after':{k:sha(k) for k in SYSTEM}}
        (out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');need(result['system_after']==before,'system differs')
        if a.case=='normal':need(code==0 and result['report_sha256'] and result['frame_sha256'],'application failed')
        else:need(code==3 and not result['report_sha256'] and not result['frame_sha256'] and 'KM_APP policy refused before device discovery' in (out/'stderr.log').read_text() and 'KM_APP scoped adaptation enabled' not in (out/'stderr.log').read_text(),'policy refusal differs')
        print(json.dumps({'status':'TERMINAL','exit_code':code,'client':a.client,'policy':a.policy,'case':a.case}),flush=True)
    except BaseException:
        if lease.fd is not None and (child is None or not terminal):lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
        raise
    finally:lease.close()
if __name__=='__main__':main()
