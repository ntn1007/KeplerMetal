#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Source build and serialized signed GPU reception for owned render states."""
from pathlib import Path
import argparse
import py_compile
import shutil
import sys
import subprocess
import json
import hashlib
from public_large_scratch import ROOT,check_library,check_driver_profile,commands,preflight,read,sha,write
MODES=('gpu','native','pipeline_only','pipeline_only_native','resources_only','resources_only_native','forced_0','forced_1','no_producer','no_consumer','release','contracts')
AIR_MODES=('air_gpu','air_native','air_reference','air_no_reset','air_no_reset_native','air_bad_context','air_bad_context_native')
ARGUMENT_MODES=('arguments_gpu','arguments_native','arguments_device','arguments_reflection','arguments_arrays','arguments_reuse','arguments_no_reset','arguments_no_reset_native','arguments_contracts')
DRAW_MODES=('draw_gpu','draw_native','draw_reference','draw_no_dispatch','draw_no_dispatch_native','draw_after_reset','draw_after_reset_native','draw_then_reset','draw_then_reset_native')
INDEXED_MODES=('indexed_gpu','indexed_native','indexed_reference','indexed_no_dispatch','indexed_no_dispatch_native','indexed_foreign','indexed_foreign_native','indexed_wrong_kind','indexed_wrong_kind_native','indexed_last','indexed_last_native','indexed_missing_table','indexed_missing_table_native','indexed_after_reset','indexed_after_reset_native','indexed_then_reset','indexed_then_reset_native','indexed_contracts')


def build(a):
    out,library=a.out.resolve(),a.library.resolve();preflight(out);m=check_library(library);out.mkdir()
    air=bool(getattr(a,'air_reset_build',None))
    argument_encoders=bool(getattr(a,'render_argument_encoders',False));assert not argument_encoders or air
    typed_draw=bool(getattr(a,'typed_render_draw',False));assert not typed_draw or(air and argument_encoders)
    typed_indexed=bool(getattr(a,'typed_indexed_render',False));assert not typed_indexed or(air and argument_encoders and not typed_draw and not a.source_commands)
    assert air==bool(getattr(a,'air_reset_inspections',None)),'Both AIR source build and inspections are required'
    for name in ['src','assets','runtime','oracles','library-src']:(out/name).mkdir()
    shutil.copyfile(library/'manifest.json',out/'runtime-manifest.json')
    for name in m['source_SHA256']:shutil.copyfile(library/'src'/name,out/'library-src'/name)
    for name in ['KeplerCPUICB.h','KeplerGPUIdentity.h','KeplerRenderCommandRecords.h','KeplerRenderStateRecords.h','KeplerIndirectRenderRangePins.h',
        'render_state_carrier.metal','combined_render_resources.metal','cpu_icb_combined_profiles.json','indirect_render_test.metal','render_state_catalogue.metal','render_state_catalogue_test.metal']:
        shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['render_state_catalogue_client.mm','public_render_state_catalogue.py']:shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    if a.source_commands:
        for name in ['KeplerNativeRenderCommands.h','render_source_commands_test.metal']:
            shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    if air:
        for name in ['AIRCertifiedResetPipeline.h','AIRCertifiedResetPipeline.mm','NativeCommandBoundaryCapture.inc','OwnedKeplerComputeCode.inc','AIRRenderResetIntegration.inc','AIRRenderResetEncode.inc']:
            shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    if argument_encoders:
        for name in ['RenderRecordArgumentsSetup.inc','RenderRecordArgumentsEncode.inc','RenderRecordArgumentsContracts.inc']:shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    if typed_draw:shutil.copyfile(ROOT/'tools/AIRRenderDrawIntegration.inc',out/'src/AIRRenderDrawIntegration.inc')
    if typed_indexed:shutil.copyfile(ROOT/'tools/AIRIndexedRenderIntegration.inc',out/'src/AIRIndexedRenderIntegration.inc')
    for name in ['verify_render_state_catalogue.py','verify_indirect_render_ranges.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name);py_compile.compile(str(out/'oracles'/name),doraise=True)
    if air:
        for name in ['verify_air_reset_render.py','verify_air_render_reset.py']:shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    if argument_encoders:shutil.copyfile(ROOT/'tools/verify_render_record_arguments.py',out/'oracles/verify_render_record_arguments.py')
    if typed_draw:shutil.copyfile(ROOT/'tools/verify_typed_render_draw.py',out/'oracles/verify_typed_render_draw.py')
    if typed_indexed:shutil.copyfile(ROOT/'tools/verify_indexed_render.py',out/'oracles/verify_indexed_render.py')
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    run=commands(out)
    for source,name,modules in [('render_state_carrier','render_state_carrier',True),('combined_render_resources','combined_render_resources',True),
        ('indirect_render_test','test',False),('render_state_catalogue','state',False),('render_state_catalogue_test','producer',False)]:
        if name=='producer'and a.source_commands:source='render_source_commands_test'
        flags=[]if modules else['-fmodules=none']
        if name in ['state','producer']:flags+=['-I',out/'src']
        run(name+'-metal',['xcrun','metal','-std=macos-metal2.4',*flags,'-c',out/'src'/(source+'.metal'),'-o',out/(name+'.air')])
        run(name+'-metallib',['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')])
    for name,digest in [('render_state_carrier','965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'),('combined_render_resources','3f07a5bb05487244b82001dff6edeed23ace2bd10a32824be1cb727f29f17775')]:
        assert sha(out/'assets'/(name+'.metallib'))==digest
    assert sha(out/'assets/state.metallib')in(out/'src/KeplerIndirectRenderRangePins.h').read_text()
    shutil.copyfile(out/'src/cpu_icb_combined_profiles.json',out/'assets/combined.json')
    extras=[]
    if air:
        ab=a.air_reset_build.resolve();am=read(ab/'inputs.json');assert am['profile']==('typed-indexed-render-air28-v1'if typed_indexed else'typed-render-draw-dataflow-air28-v1'if typed_draw else'reset-dataflow-air28-v1')
        for name,digest in am['frozen'].items():assert sha(ab/name)==digest,name
        if typed_indexed:from verify_air_indexed_inspection import verify as verify_inspection
        elif typed_draw:from verify_air_render_draw import verify as verify_inspection
        else:from verify_air_reset_dataflow import verify as verify_inspection
        for variant in ['lowered','reference']:
            p=a.air_reset_inspections.resolve()/('inspect-'+variant);assert verify_inspection(p)['mode']=='inspect'
            cert=read(p/'certificate.json');assert cert['library_SHA256']==sha(ab/'assets'/(variant+'.metallib'))
            assert cert['inspection_inputs_SHA256']==sha(p/'inputs.json')and cert['inspection_results_SHA256']==sha(p/'results.json')and cert['no_native_call']is True
            shutil.copyfile(ab/'assets'/(variant+'.metallib'),out/'assets'/('reset-'+variant+'.metallib'))
            shutil.copyfile(p/'certificate.json',out/'assets'/('reset-'+variant+'.certificate.json'))
        run('reset-MRC',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',out/'src','-c',out/'src/AIRCertifiedResetPipeline.mm','-o',out/'AIRCertifiedResetPipeline.o'])
        extras=['-DKP_AIR_RENDER_RESET=1',out/'AIRCertifiedResetPipeline.o']
        if argument_encoders:extras+=['-DKP_RENDER_ARGUMENT_ENCODERS=1']
        if typed_draw:extras+=['-DKP_TYPED_RENDER_DRAW=1']
        if typed_indexed:extras+=['-DKP_TYPED_INDEXED_RENDER=1']
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src',out/'src/render_state_catalogue_client.mm',*extras,library/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(source_SHA256={str(p.relative_to(out)):sha(p)for p in(out/'src').iterdir()},
        runtime_sources_SHA256=m['source_SHA256'],runtime_SHA256={p.name:sha(p)for p in(out/'runtime').iterdir()},oracle_SHA256={p.name:sha(p)for p in(out/'oracles').iterdir()},
        assets_SHA256={p.name:sha(p)for p in(out/'assets').iterdir()},executable_SHA256=sha(out/'application'),
        static_library_SHA256=m['static_library_SHA256'],library_manifest_SHA256=sha(library/'manifest.json'),source_commands=a.source_commands,air_reset=air,render_argument_encoders=argument_encoders,typed_render_draw=typed_draw,typed_indexed_render=typed_indexed,GPU_execution=False))


def run(a):
    b,out=a.build.resolve(),a.out.resolve();m=read(b/'inputs.json');assert not out.exists()and out.parent.is_dir()
    assert(a.mode in DRAW_MODES)==m.get('typed_render_draw',False),'Draw mode and frozen host must agree'
    assert(a.mode in INDEXED_MODES)==m.get('typed_indexed_render',False),'Indexed mode and frozen host must agree'
    assert(a.mode in ARGUMENT_MODES+DRAW_MODES+INDEXED_MODES)==m.get('render_argument_encoders',False),'Argument mode and frozen host must agree'
    assert(a.mode in AIR_MODES+ARGUMENT_MODES+DRAW_MODES+INDEXED_MODES)==m.get('air_reset',False),'Mode and frozen host must agree'
    for key,folder in [('source_SHA256',''),('runtime_sources_SHA256','library-src'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles'),('assets_SHA256','assets')]:
        for name,digest in m[key].items():assert sha(b/folder/name)==digest,name
    assert sha(b/'runtime-manifest.json')==m['library_manifest_SHA256']and sha(b/'application')==m['executable_SHA256']
    driver=check_driver_profile();out.mkdir();(out/'outputs').mkdir()
    for name in ['src','assets','runtime','oracles','library-src']:shutil.copytree(b/name,out/name)
    shutil.copyfile(b/'runtime-manifest.json',out/'runtime-manifest.json');shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755)
    write(out/'inputs.json',dict(m,mode=a.mode,driver_SHA256=driver,source_build_inputs_SHA256=sha(b/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    receipt=run_host(out/'application',out/'execution',list(map(str,[out/'assets',out/'outputs',a.mode])),a.reservation_root.resolve())
    write(out/'results.json',read(out/'execution/execution.stdout'))
    # A fresh isolated interpreter cannot reuse an oracle module imported by
    # this mutable launcher. Every oracle/helper resolves inside the frozen copy.
    module='verify_indexed_render'if m.get('typed_indexed_render',False)else'verify_typed_render_draw'if m.get('typed_render_draw',False)else'verify_render_record_arguments'if m.get('render_argument_encoders',False)else'verify_air_reset_render'if m.get('air_reset',False)else'verify_render_state_catalogue'
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))'
    argv=[sys.executable,'-I','-c',code,str(out/'oracles'),str(out)]
    verified=subprocess.run(argv,capture_output=True,text=True)
    (out/'verification.stdout').write_text(verified.stdout);(out/'verification.stderr').write_text(verified.stderr)
    write(out/'verification-execution.json',dict(argv=argv,exit_code=verified.returncode,isolated_interpreter=True,code_SHA256=hashlib.sha256(code.encode()).hexdigest()))
    if verified.returncode:raise RuntimeError('Frozen oracle failed; see '+str(out/'verification.stderr'))
    proof=json.loads(verified.stdout);write(out/'independent-verification.json',dict(proof,PID=receipt['pid'],static_library_SHA256=m['static_library_SHA256']))
    print({k:v for k,v in proof.items()if k!='files_SHA256'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--library',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.add_argument('--source-commands',action='store_true');b.add_argument('--air-reset-build',type=Path);b.add_argument('--air-reset-inspections',type=Path);b.add_argument('--render-argument-encoders',action='store_true');b.add_argument('--typed-render-draw',action='store_true');b.add_argument('--typed-indexed-render',action='store_true');b.set_defaults(func=build)
    r=s.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--mode',choices=MODES+AIR_MODES+ARGUMENT_MODES+DRAW_MODES+INDEXED_MODES,required=True);r.add_argument('--reservation-root',type=Path,required=True);r.set_defaults(func=run)
    a=p.parse_args();a.func(a)
