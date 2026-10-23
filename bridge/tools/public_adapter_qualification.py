#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build public adapter clients and qualify them using local, pinned assets.

No downloads or system changes. Asset SDKs are local-only prerequisites; their
host/library objects are never reused. Each GPU process uses the common lease.
"""
from pathlib import Path
import argparse
import importlib
import json
import shutil
import sys

from public_large_scratch import ROOT, check_library, check_driver_profile, commands, preflight, read, sha, write

CLIENTS = {
    'fp64': 'sdk-combined/examples/fp64_client.mm',
    'forward': 'sdk-combined/examples/fp64_conversion_client.mm',
    'reverse': 'sdk-combined/examples/fp64_reverse_client.mm',
    'icb': 'sdk-combined/examples/client.mm',
    'render': 'tools/cpu_icb_render_probe.mm',
}
ORACLES = {
    'fp64': 'verify_fp64_client', 'forward': 'verify_fp64_conversion_client',
    'reverse': 'verify_fp64_reverse_client', 'icb': 'verify_example',
    'render': 'verify_cpu_icb_render',
}


def build(a):
    out, library, sdk = a.out.resolve(), a.library.resolve(), a.asset_sdk.resolve()
    preflight(out); lm = check_library(library)
    manifest = sdk / 'FILE_MANIFEST.json'
    rows = read(manifest)['files']; pins = {r['path']: r['SHA256'] for r in rows}
    assets = [p for p in (sdk / 'assets').iterdir() if p.is_file()]
    assert assets and len(pins) == len(rows)
    for p in assets: assert sha(p) == pins['assets/' + p.name], p.name
    fp = read(sdk / 'assets/fp64_manifest.json')
    assert len(fp['programs']) == 60
    out.mkdir()
    for name in ['src', 'assets', 'oracles', 'runtime']: (out / name).mkdir()
    for p in assets: shutil.copyfile(p, out / 'assets' / p.name)
    for p in (library / 'src').glob('*.h'): shutil.copyfile(p, out / 'src' / p.name)
    for kind, source in CLIENTS.items(): shutil.copyfile(ROOT / source, out / 'src' / (kind + '.mm'))
    sources = {name + '.py': ROOT / 'sdk-combined/examples' / (name + '.py')
        for name in list(ORACLES.values())[:-1]}
    for name in ['verify_cpu_icb_render', 'decode_native_commands', 'verify_local_memory',
            'fp64_conversion_inputs', 'fp64_reverse_inputs']:
        sources[name + '.py'] = ROOT / 'tools' / (name + '.py')
    sources['fp64_cpu_oracle.py'] = ROOT / 'tools/verify_fp64_math.py'
    for name, p in sources.items(): shutil.copyfile(p, out / 'oracles' / name)
    # The original reverse-conversion client requires three raw input recipes;
    # the SDK asset archive intentionally contains programs, not these inputs.
    sys.path.insert(0,str(out / 'oracles'))
    from fp64_reverse_inputs import columns, packed
    for trial,(local,count) in enumerate([(32,65),(128,2057),(1024,12289)]):
        (out / 'assets' / f'reverse-input-l{local}-t{trial}.bin').write_bytes(
            packed(columns('to_f32_rn',local,count,trial)[0]))
    for name, source in [('lab_gpu_reservation.py', ROOT / 'tools/lab_gpu_reservation.py'),
            ('run_sdk_host.py', ROOT / 'sdk-combined/runtime/run_sdk_host.py')]:
        shutil.copyfile(source, out / 'runtime' / name)
    run_command = commands(out)
    for kind in CLIENTS:
        run_command(kind, ['xcrun', 'clang++', '-arch', 'x86_64', '-O2', '-std=c++17',
            '-fobjc-arc', '-I', out / 'src', out / 'src' / (kind + '.mm'),
            library / 'libKeplerMetal.a', '-Wl,-ObjC', '-framework', 'Metal',
            '-framework', 'Foundation', '-o', out / kind])
    write(out / 'inputs.json', dict(static_library_SHA256=lm['static_library_SHA256'],
        library_manifest_SHA256=sha(library / 'manifest.json'),
        asset_manifest_SHA256=sha(manifest), assets_SHA256={p.name:sha(p) for p in (out / 'assets').iterdir()},
        source_hashes={str(p.relative_to(out)):sha(p) for p in (out / 'src').iterdir()},
        oracle_SHA256={p.name:sha(p) for p in (out / 'oracles').iterdir()},
        runtime_SHA256={p.name:sha(p) for p in (out / 'runtime').iterdir()},
        executable_SHA256={kind:sha(out / kind) for kind in CLIENTS},
        core_source_compilations=0, identity_required=True, builder_SHA256=sha(__file__),
        GPU_execution=False, historical_GPU_qualification_inherited=False))


def run(a):
    build, out, reservation = a.build.resolve(), a.out.resolve(), a.reservation_root.resolve()
    allowed = ['prepare','execute'] + (['register','native'] if a.kind == 'icb' else
        ['no_producer'] if a.kind != 'render' else [])
    assert a.mode in allowed and a.trials in [1,9]
    assert not out.exists() and out.parent.is_dir() and (reservation / 'results').is_dir()
    inputs = read(build / 'inputs.json')
    for key, sub in [('source_hashes',''),('assets_SHA256','assets'),('oracle_SHA256','oracles'),('runtime_SHA256','runtime')]:
        for name, digest in inputs[key].items(): assert sha(build / sub / name) == digest
    executable = build / a.kind
    assert sha(executable) == inputs['executable_SHA256'][a.kind]
    check_driver_profile()
    out.mkdir(); (out / 'outputs').mkdir()
    for folder in ['src','assets','oracles','runtime']: shutil.copytree(build / folder, out / folder)
    shutil.copyfile(executable, out / 'application'); (out / 'application').chmod(0o755)
    actual_inputs = dict(inputs, executable_SHA256=sha(executable), kind=a.kind, mode=a.mode, trials=a.trials,
        source_build_inputs_SHA256=sha(build / 'inputs.json'))
    if a.kind == 'render':
        shutil.copyfile(out / 'assets/render_state_carrier.metallib', out / 'render_state_carrier.metallib')
        actual_inputs['library_SHA256'] = sha(out / 'render_state_carrier.metallib')
        args = [out / 'render_state_carrier.metallib',out / 'outputs',a.mode]
    elif a.kind == 'icb':
        abi = out / 'assets/cpu_icb_native_cas_manifest.json'
        args = [out / 'assets',abi,out / 'outputs',sha(abi),a.mode]
    else: args = [out / 'assets',out / 'outputs',a.mode,a.trials]
    write(out / 'inputs.json',actual_inputs)
    sys.path.insert(0,str(out / 'runtime'))
    from run_sdk_host import run_host
    m = run_host(out / 'application',out / 'execution',list(map(str,args)),reservation)
    result = read(out / 'execution/execution.stdout'); write(out / 'results.json',result)
    sys.path.insert(0,str(out / 'oracles'))
    from verify_local_memory import verify_device_identity
    assert 'device_identity' in result
    verify_device_identity(result)
    oracle = importlib.import_module(ORACLES[a.kind]); proof = oracle.verify(out)
    proof.update(static_library_SHA256=inputs['static_library_SHA256'],
        oracle_SHA256=inputs['oracle_SHA256'][ORACLES[a.kind]+'.py'],
        device_identity=result['device_identity'],public_runner_SHA256=sha(__file__))
    write(out / 'independent-verification.json',proof)
    summary = {k:v for k,v in proof.items() if k not in ['raw_SHA256','raw_files','files_SHA256']}
    summary.update(kind=a.kind,PID=m['pid'])
    print(json.dumps(summary),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('build');q.add_argument('--library',type=Path,required=True)
    q.add_argument('--asset-sdk',type=Path,required=True);q.add_argument('--out',type=Path,required=True);q.set_defaults(fn=build)
    q=sub.add_parser('run');q.add_argument('--build',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
    q.add_argument('--reservation-root',type=Path,required=True);q.add_argument('--kind',choices=list(CLIENTS),required=True)
    q.add_argument('--mode',required=True);q.add_argument('--trials',type=int,choices=[1,9],default=1);q.set_defaults(fn=run)
    a=p.parse_args();a.fn(a)


if __name__=='__main__': main()
