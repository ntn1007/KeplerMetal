#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/run no-dispatch extent controls under GPU reservation."""
import argparse, datetime, importlib.util, json, os, shutil, subprocess
from pathlib import Path
from experiment import HERE, BRIDGE, SYSTEM, sha, need, command as cmd

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build')
    for n in ('lab','archive','app-build','old-shader','old-manifest','out'): b.add_argument('--'+n,type=Path,required=True)
    r=sub.add_parser('run')
    for n in ('lab','build','out'): r.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(); lab=a.lab.resolve(); out=a.out.resolve(); out.relative_to(lab/'results'); need(not out.exists() and out.parent.is_dir(),'fresh output required'); before={k:sha(k) for k in SYSTEM}; need(before==SYSTEM,'system differs')
    if a.action=='build':
        ar=a.archive.resolve(); m=json.loads((ar/'manifest.json').read_text()); app=a.app_build.resolve(); bm=json.loads((app/'build.json').read_text())
        need(m['status']=='PASS' and not m['GPU_execution'] and sha(ar/'libKeplerMetal.a')==m['static_library_SHA256']==bm['archive_sha256'],'archive differs')
        for n,h in m['source_SHA256'].items(): need(sha(ar/'src'/n)==sha(BRIDGE/'src'/n)==h,'source differs '+n)
        need(sha(a.old_shader)=='adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf','old shader differs')
        need(sha(a.old_manifest)=='6930ed313d2e1b1e836f189afb2db7c0286f10afb9c867ec3fe9659390e16732','old manifest differs')
        for n in ('carrier.metallib','shader.metallib','profiles.json'): need(sha(app/n)==bm['files_sha256'][n],'app asset differs')
        out.mkdir(); shutil.copyfile(HERE/'contracts.mm',out/'contracts.mm'); shutil.copyfile(a.old_shader,out/'old.metallib');shutil.copyfile(a.old_manifest,out/'old-profiles.json')
        for n in ('carrier.metallib','shader.metallib','profiles.json'): shutil.copyfile(app/n,out/n)
        cmd(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',ar/'src',out/'contracts.mm',ar/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'contracts'])
        cmd(['codesign','--force','--sign','-',out/'contracts']); cmd(['codesign','--verify','--strict',out/'contracts'])
        record={'status':'PREPARED_ONLY','gpu_execution':False,'system':before,'archive_sha256':m['static_library_SHA256'],'app_build_sha256':sha(app/'build.json'),'files_sha256':{x.name:sha(x) for x in out.iterdir() if x.is_file()}}; (out/'build.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':'PREPARED_ONLY'}));return
    build=a.build.resolve(); build.relative_to(lab/'results'); record=json.loads((build/'build.json').read_text()); need(record['status']=='PREPARED_ONLY' and record['system']==before,'build/system differs')
    for n,h in record['files_sha256'].items(): need(sha(build/n)==h,'artifact differs '+n)
    need(sha(build/'contracts.mm')==sha(HERE/'contracts.mm'),'source differs');cmd(['codesign','--verify','--strict',build/'contracts'])
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py';need(sha(leasepath)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs');spec=importlib.util.spec_from_file_location('release_contract_reservation',leasepath);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);lease=mod.GPUReservation(lab);child=None;terminal=False
    try:
        out.mkdir();shutil.copyfile(build/'contracts',out/'contracts');host=out/'contracts';host.chmod(0o755);need(sha(host)==record['files_sha256']['contracts'],'host differs');cmd(['codesign','--verify','--strict',host]);args=[str(build/n) for n in ('carrier.metallib','shader.metallib','profiles.json','old.metallib','old-profiles.json')]
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};lease.spawning(host,sha(host));started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(host),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env);lease.bind_child(child.pid);print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True);code=child.wait()
        table=mod.process_table();need(child.pid not in table and not any(x['command']==str(host) or x['command'].startswith(str(host)+' ') for x in table.values()),'child still visible');terminal=True;lease.finish(code,False,'')
        result={'status':'TERMINAL','exit_code':code,'pid':child.pid,'started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),'build_sha256':sha(build/'build.json'),'runner_sha256':sha(HERE/'contracts.py'),'host_sha256':sha(host),'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'system_before':before,'system_after':{k:sha(k) for k in SYSTEM}};(out/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');need(code==0 and result['system_after']==before,'process/system failed');report=json.loads((out/'stdout.json').read_text());need(report['status']=='PASS' and report['command_buffers_committed']==0,'contract failed');print(json.dumps({'status':'TERMINAL','cases':len(report['cases'])}),flush=True)
    except BaseException:
        if lease.fd is not None and (child is None or not terminal):lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
        raise
    finally:lease.close()
if __name__=='__main__':main()
