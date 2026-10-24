#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build source-lowered NVIDIA producers; qualify records and native execution."""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import sys
from public_large_scratch import ROOT,check_library,check_driver_profile,commands,preflight,read,sha,write

FLOW_MODES=['basic','barrier','copy','no_seed','no_gather','no_finish','split',
    'no_producer','no_consumer','bad_parameters','bad_counter','bad_pipeline',
    'bad_buffer3_flag','bad_groups','bad_reserved','refusals']
FUNCTION_FLOW_MODES=FLOW_MODES+['encoder_reuse']
STABLE_FLOW_MODES=FUNCTION_FLOW_MODES+['duplicate_templates']


def msl_abi(text):
    """Keep the canonical ABI; replace only its incompatible system typedef include."""
    anchor='#include <stdint.h>'
    assert text.count(anchor)==1
    for contract in ['#define KP_COMMAND_IR_VERSION2 2u','#define KP_COMMAND_RECORD_BYTES 128u',
                     '#define KP_COMMAND_MAX_RECORDS 8u','#define KP_COMMAND_V2_MAX_BINDINGS 4u']:
        assert contract in text, 'Qualify a changed command ABI separately'
    return text.replace(anchor,'typedef unsigned int uint32_t;\ntypedef unsigned long uint64_t;')


def lower_readonly_members(text,profile):
    """Only registered argument-buffer pointer members; never global keywords.

    The native constant-space pointer-to-integer path loses the high word after
    pointer arithmetic in our record probe. The registered inputs are immutable
    GPU buffers; read-only device pointers preserve their address representation.
    Calls, kernel constants, ordinary constant variables and SDK code stay intact.
    """
    seen=set()
    pattern=r'(?m)^(\s*)constant\s+(\w+)\s*\*\s*(\w+)\s*\[\[id\((\d+)\)\]\];'
    def replace(m):
        indent,type_,name,index=m.groups()
        assert name in profile and profile[name]==(type_,int(index)) and name not in seen
        seen.add(name)
        return f'{indent}device const {type_} *{name} [[id({index})]];'
    result=re.sub(pattern,replace,text)
    assert seen==set(profile),'Readonly member schema changed; qualify it separately'
    return result


def compile_refusals(out):
    folder=out/'compile-refusals';folder.mkdir();rows=[]
    for name,argument,call in [
        ('constant_binding','constant uint *p [[buffer(1)]]','c.set_kernel_buffer(p,0u);'),
        ('strided_binding','device uint *p [[buffer(1)]]','c.set_kernel_buffer(p,4ul,0u);')]:
        source=folder/(name+'.metal')
        source.write_text('#include <metal_stdlib>\n#include <metal_command_buffer>\nusing namespace metal;\nstruct Args {command_buffer commands [[id(0)]];};\nkernel void unsupported(device Args &a [[buffer(0)]],'+argument+') {compute_command c(a.commands,0);'+call+'}\n')
        argv=['xcrun','metal','-std=macos-metal2.3','-I',str(out/'include'),'-c',str(source),'-o',str(folder/(name+'.air'))]
        r=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        (folder/(name+'.stdout')).write_text(r.stdout);(folder/(name+'.stderr')).write_text(r.stderr)
        rows.append(dict(case=name,argv=argv,exit_code=r.returncode,expected_deleted_overload=True))
        assert r.returncode!=0 and 'deleted' in r.stderr,(name,r.stderr)
    write(folder/'commands.json',rows)
    return dict(cases=2,expected_refusals=2,commands_SHA256=sha(folder/'commands.json'))


def build(a):
    assert not a.stable_identities or a.function_arguments,'Stable contexts require the native function binding route'
    out,library,assets=a.out.resolve(),a.library.resolve(),a.assets.resolve()
    preflight(out);lm=check_library(library);pins=read(ROOT/'tools/native_msl_fixture_pins.json')['assets']
    if not a.nak_baseline:
        native_assets={'consumer.metallib','consumer.json','gpu_command_selector.metallib',
            'gpu_command_geometry.metallib','gpu_command_bindings.metallib','materializer.metallib'}
        pins={name:digest for name,digest in pins.items()if name in native_assets}
    for name,digest in pins.items():assert Path(name).name==name and sha(assets/name)==digest,name
    out.mkdir()
    for folder in ['src','lowered','include','assets','runtime','oracles']:(out/folder).mkdir()
    shutil.copyfile(Path(__file__),out/'src/public_native_msl_commands.py')
    for name in pins:shutil.copyfile(assets/name,out/'assets'/name)
    for name in ['KeplerCPUICB.h','KeplerGPUIdentity.h','KeplerProgramImport.h','KeplerCommandIR.h',
                 'KeplerNativeMSLCommands.h','gpu_command_frontend_dataflow.metal',
                 'command_ir_field_probe.metal','native_command_records_probe.metal']:
        shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['command_ir_dataflow_client.mm','native_command_records_probe.mm']:
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    if a.function_arguments:
        shutil.copyfile(ROOT/'src/native_source_function_contracts.metal',out/'src/native_source_function_contracts.metal')
        shutil.copyfile(ROOT/'tools/native_source_function_contracts.mm',out/'src/native_source_function_contracts.mm')
    if a.stable_identities:
        shutil.copyfile(ROOT/'src/stable_pipeline_record_probe.metal',out/'src/stable_pipeline_record_probe.metal')
        shutil.copyfile(ROOT/'tools/stable_pipeline_record_probe.mm',out/'src/stable_pipeline_record_probe.mm')
    (out/'include/KeplerCommandIR.h').write_text(msl_abi((out/'src/KeplerCommandIR.h').read_text()))
    shutil.copyfile(out/'src/KeplerNativeMSLCommands.h',out/'include/metal_command_buffer')
    for source,profile in [('gpu_command_frontend_dataflow',{'parameters':('uint',4)}),
                           ('native_command_records_probe',{'constants':('uint',3)})]:
        (out/'lowered'/(source+'.metal')).write_text(lower_readonly_members((out/'src'/(source+'.metal')).read_text(),profile))
    for name in ['verify_command_ir_dataflow.py','verify_native_msl_records.py','verify_native_function_contracts.py','verify_stable_pipeline_records.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    run=commands(out)
    for name,source in [('native_producer','gpu_command_frontend_dataflow'),('records','native_command_records_probe'),('field','command_ir_field_probe')]:
        flags=['-I',out/'include'] if name!='field' else []
        source_folder='src'if name=='field'else'lowered'
        run(name+'-metal',['xcrun','metal','-std=macos-metal2.3',*flags,'-c',out/source_folder/(source+'.metal'),'-o',out/(name+'.air')])
        run(name+'-metallib',['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')])
    if a.stable_identities:
        run('stable-records-metal',['xcrun','metal','-std=macos-metal2.3','-I',out/'include','-c',out/'src/stable_pipeline_record_probe.metal','-o',out/'stable_records.air'])
        run('stable-records-metallib',['xcrun','metallib',out/'stable_records.air','-o',out/'assets/stable_records.metallib'])
    if a.function_arguments:
        for name,source in [('opaque_producer','gpu_command_frontend_dataflow'),('function_contracts','native_source_function_contracts')]:
            run(name+'-metal',['xcrun','metal','-std=macos-metal2.3','-c',out/'src'/(source+'.metal'),'-o',out/(name+'.air')])
            run(name+'-metallib',['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')])
        if a.nak_baseline:
            assert sha(out/'assets/opaque_producer.metallib')=='a9367d4492cd100adfcde990efe0b043e4b070536a3615be5b9b2f63bfb473db'
            shutil.copyfile(out/'assets/opaque_producer.metallib',out/'assets/producer.metallib')
    kinds=['dataflow','nak','records']if a.nak_baseline else['dataflow','records']
    if a.function_arguments:kinds.append('contracts')
    if a.function_arguments and a.nak_baseline:kinds.append('nak_function')
    if a.stable_identities:kinds.append('stable_records')
    for kind in kinds:
        source={'records':'native_command_records_probe.mm','stable_records':'stable_pipeline_record_probe.mm','contracts':'native_source_function_contracts.mm'}.get(kind,'command_ir_dataflow_client.mm')
        flags=[] if kind in ['records','stable_records','contracts'] else ['-DKP_DATAFLOW_NATIVE=0','-DKP_NATIVE_MSL_COMMANDS='+str(int(kind=='dataflow'))]
        if kind in ['dataflow','nak_function'] and a.function_arguments:
            flags+=['-DKP_PUBLIC_ARGUMENT_ENCODER=1','-DKP_FUNCTION_ARGUMENT_ENCODER=1']
        if kind=='dataflow' and a.stable_identities:flags+=['-DKP_STABLE_PIPELINE_IDENTITIES=1']
        link=[] if kind=='records' else [library/'libKeplerMetal.a','-Wl,-ObjC']
        run(kind,['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',*flags,
            '-I',out/'src',out/'src'/source,*link,'-framework','Metal','-framework','Foundation','-o',out/kind])
    refusals=compile_refusals(out)
    write(out/'inputs.json',dict(source_hashes={str(p.relative_to(out)):sha(p)for folder in ['src','lowered','include']for p in (out/folder).iterdir()},
        assets_SHA256={p.name:sha(p)for p in (out/'assets').iterdir()},runtime_SHA256={p.name:sha(p)for p in (out/'runtime').iterdir()},
        oracle_SHA256={p.name:sha(p)for p in (out/'oracles').iterdir()},executables={k:sha(out/k)for k in kinds},
        static_library_SHA256=lm['static_library_SHA256'],library_manifest_SHA256=sha(library/'manifest.json'),
        existing_fixture_pins_SHA256=sha(ROOT/'tools/native_msl_fixture_pins.json'),builder_SHA256=sha(__file__),
        shader_call_sites_modified=False,readonly_argument_pointer_members_lowered=True,NAK_baseline_built=a.nak_baseline,
        native_function_arguments=a.function_arguments,
        native_stable_pipeline_identities=a.stable_identities,
        compile_refusals=refusals,SDK_modified=False,GPU_execution=False))


def run(a):
    b,out=a.build.resolve(),a.out.resolve();assert not out.exists() and out.parent.is_dir()
    assert a.mode in (['inspect']if a.kind=='contracts'else ['execute','no_dispatch']if a.kind in ['records','stable_records']else STABLE_FLOW_MODES)
    inputs=read(b/'inputs.json');assert a.kind in inputs['executables'],'Requested backend was not built'
    if a.mode=='encoder_reuse':assert a.kind=='dataflow' and inputs.get('native_function_arguments')
    if a.mode=='duplicate_templates':assert a.kind=='dataflow' and inputs.get('native_stable_pipeline_identities')
    for key,folder in [('source_hashes',''),('assets_SHA256','assets'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
        for name,digest in inputs[key].items():assert sha(b/folder/name)==digest,name
    assert sha(b/a.kind)==inputs['executables'][a.kind];driver=check_driver_profile()
    out.mkdir();(out/'outputs').mkdir()
    for folder in ['src','lowered','include','assets','runtime','oracles']:shutil.copytree(b/folder,out/folder)
    shutil.copyfile(b/a.kind,out/'application');(out/'application').chmod(0o755)
    write(out/'inputs.json',dict(inputs,executable_SHA256=sha(out/'application'),kind=a.kind,mode=a.mode,
        driver_SHA256=driver,source_build_inputs_SHA256=sha(b/'inputs.json'),public_runner_SHA256=sha(__file__)))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    argv=[out/'assets']if a.kind=='contracts'else [out/'assets'/(a.kind+'.metallib'),a.mode,out/'outputs']if a.kind in ['records','stable_records']else[out/'assets',out/'outputs',a.mode]
    m=run_host(out/'application',out/'execution',list(map(str,argv)),a.reservation_root.resolve())
    result=read(out/'execution/execution.stdout');write(out/'results.json',result)
    assert a.kind in ['records','stable_records','contracts'] or result['producer_backend']==('native_msl'if a.kind=='dataflow'else'NAK')
    sys.path.insert(0,str(out/'oracles'))
    if a.kind=='contracts':import verify_native_function_contracts as oracle
    elif a.kind=='stable_records':import verify_stable_pipeline_records as oracle
    elif a.kind=='records':import verify_native_msl_records as oracle
    else:import verify_command_ir_dataflow as oracle
    proof=oracle.verify(out);proof.update(kind=a.kind,PID=m['pid'],static_library_SHA256=inputs['static_library_SHA256'])
    write(out/'independent-verification.json',proof)
    print(json.dumps({k:v for k,v in proof.items()if k!='raw_SHA256'}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('build')
    for name in ['library','assets','out']:q.add_argument('--'+name,type=Path,required=True)
    q.add_argument('--nak-baseline',action='store_true',help='Also require the archived SM30 fixtures and build the comparison client')
    q.add_argument('--function-arguments',action='store_true',help='Bind native producers through registered public function argument encoders')
    q.add_argument('--stable-identities',action='store_true',help='Use stable scope-owned pipeline IDs and permuted native template catalogues')
    q.set_defaults(fn=build);q=s.add_parser('run')
    for name in ['build','out','reservation-root']:q.add_argument('--'+name,type=Path,required=True)
    q.add_argument('--kind',choices=['dataflow','nak','records','stable_records','contracts','nak_function'],required=True);q.add_argument('--mode',required=True);q.set_defaults(fn=run)
    a=p.parse_args();a.fn(a)


if __name__=='__main__':main()
