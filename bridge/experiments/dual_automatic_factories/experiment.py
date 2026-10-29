#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze and serialize a mixed compute/render ICB cohort on one queue."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_library,check_driver_profile,preflight,sha,write

COMPUTE='7478ba6e51f7bb4c466e60e4b07cf7af15c8abe04d04f3211cb2f1f2c6525911'
RENDER='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
MANIFEST='225c1f1bf5aeb78ad89aa7444597e126926e033c57a16a80d32f269c2f9fa1be'
def build(a):
    library=a.library.resolve();out=a.out.resolve();preflight(out);metadata=check_library(library)
    for f,h in [(a.compute,COMPUTE),(a.render,RENDER),(BRIDGE/'src/cpu_icb_gpu_indices.json',MANIFEST)]:
        if sha(f)!=h:raise ValueError('input profile differs')
    out.mkdir();shutil.copyfile(HERE/'host.mm',out/'cpu_icb_mixed_probe.mm')
    for f,n in [(a.compute,'cpu_icb_gpu_indices.metallib'),(a.render,'render_state_carrier.metallib'),(BRIDGE/'src/cpu_icb_gpu_indices.json','cpu_icb_gpu_indices.json')]:shutil.copyfile(f,out/n)
    (out/'oracles').mkdir();(out/'runtime').mkdir()
    shutil.copyfile(BRIDGE/'tools/decode_native_commands.py',out/'oracles/decode_native_commands.py')
    original=(BRIDGE/'tools/verify_cpu_icb_mixed.py').read_text()
    old="d['registry_id']==4294968458"
    replacement="d['registry_id']==d['device_identity']['registry_id'] and d['device_identity']['PCI_vendor_id']==0x10de and d['device_identity']['PCI_device_id']==0x1198 and d['device_identity']['name']=='NVIDIA GeForce GTX 880M'"
    if original.count(old)!=1:raise ValueError('verifier profile differs')
    (out/'oracles/verify_cpu_icb_mixed.py').write_text(original.replace(old,replacement))
    shutil.copyfile(BRIDGE/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(BRIDGE/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    cmd=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(library/'src'),str(out/'cpu_icb_mixed_probe.mm'),str(library/'libKeplerMetal.a'),'-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'cpu_icb_mixed_probe')]
    x=subprocess.run(cmd,capture_output=True,timeout=120);(out/'build.stdout').write_bytes(x.stdout);(out/'build.stderr').write_bytes(x.stderr)
    if x.returncode:raise RuntimeError('compile failed; inspect build.stderr')
    frozen={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ('inputs.json','build.stdout','build.stderr')}
    write(out/'inputs.json',{'source_hashes':{'cpu_icb_mixed_probe.mm':sha(out/'cpu_icb_mixed_probe.mm')},'compute_library_SHA256':COMPUTE,'render_library_SHA256':RENDER,'manifest_SHA256':MANIFEST,'static_library_SHA256':metadata['static_library_SHA256'],'frozen':frozen,'system_modified':False})
    print(json.dumps({'status':'BUILD_PASS','gpu_execution':False,'host_sha256':sha(out/'cpu_icb_mixed_probe')}))
def run(a):
    out=a.out.resolve();build=a.build.resolve();data=json.loads((build/'inputs.json').read_text());preflight(out)
    for n,h in data['frozen'].items():
        if sha(build/n)!=h:raise ValueError('frozen input differs: '+n)
    check_driver_profile();out.mkdir();(out/'outputs').mkdir()
    for n in ('cpu_icb_mixed_probe.mm','cpu_icb_mixed_probe','cpu_icb_gpu_indices.metallib','render_state_carrier.metallib','cpu_icb_gpu_indices.json'):
        shutil.copyfile(build/n,out/n)
    shutil.copytree(build/'oracles',out/'oracles');shutil.copytree(build/'runtime',out/'runtime')
    write(out/'inputs.json',data)
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    m=run_host(out/'cpu_icb_mixed_probe',out/'execution',[str(out/'cpu_icb_gpu_indices.metallib'),str(out/'cpu_icb_gpu_indices.json'),str(out/'render_state_carrier.metallib'),str(out/'outputs'),a.mode],a.lab.resolve())
    if sha(out/'cpu_icb_mixed_probe')!=m['original_binary_sha256'] or sha(out/'execution/application')!=m['signed_binary_sha256']:raise ValueError('executable mismatch')
    result=json.loads((out/'execution/execution.stdout').read_text());write(out/'results.json',result)
    if result['automatic_order']!=a.mode or result['automatic_factories']!=(a.mode!='execute') or not result['queue_restored']:raise ValueError('automatic mode/restore differs')
    events=result['events'];count=lambda name:sum(x.get('operation')==name for x in events)
    if a.mode!='execute' and (count('automatic_compute_factories_enabled')!=1 or count('automatic_render_factories_enabled')!=1 or count('automatic_compute_encoder')<9 or count('automatic_render_encoder')<9):raise ValueError('automatic factory events missing')
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_cpu_icb_mixed import verify;print(json.dumps(verify(__import__("pathlib").Path(sys.argv[2]),portable=True)))'
    x=subprocess.run([sys.executable,'-I','-c',code,str(out/'oracles'),str(out)],capture_output=True,text=True)
    (out/'verify.stdout').write_text(x.stdout);(out/'verify.stderr').write_text(x.stderr)
    if x.returncode:raise RuntimeError('Independent oracle failed; inspect verify.stderr')
    proof=json.loads(x.stdout);write(out/'independent-verification.json',dict(proof,automatic_mode=a.mode,automatic_compute_events=count('automatic_compute_encoder'),automatic_render_events=count('automatic_render_encoder'),signed_host_verified=True,driver_sha256=check_driver_profile()))
    print(json.dumps({'status':'PASS','mode':a.mode,'compute_events':count('automatic_compute_encoder'),'render_events':count('automatic_render_encoder'),'gpu_channels':proof['correct_float32_channels']}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(required=True);b=sub.add_parser('build')
    for n in ('library','compute','render','out'):b.add_argument('--'+n,type=Path,required=True)
    b.set_defaults(func=build);r=sub.add_parser('run')
    for n in ('build','lab','out'):r.add_argument('--'+n,type=Path,required=True)
    r.add_argument('--mode',choices=('execute','auto-compute-first','auto-render-first'),required=True);r.set_defaults(func=run)
    a=p.parse_args();a.func(a)
