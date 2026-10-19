#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Relink the published CAS coexistence client against a public archive.

Assets must be generated locally by the earlier CAS/allocation workflows. This
tool never downloads or publishes their compiled libraries or certificates.
"""
from pathlib import Path
import argparse
import shutil
import sys

from public_large_scratch import ROOT, check_library, preflight, commands, read, write, sha


def build(a):
    out, library, asset_build = a.out.resolve(), a.library.resolve(), a.asset_build.resolve()
    preflight(out); lm = check_library(library); source_inputs = read(asset_build / 'inputs.json')
    client = ROOT / 'tools/public_large_scratch_cas_probe.mm'
    large = a.large_build.resolve(); large_inputs = read(large / 'inputs.json')
    assert large_inputs['static_library_SHA256'] == lm['static_library_SHA256']
    for name, digest in source_inputs['assets'].items(): assert sha(asset_build / 'assets' / name) == digest
    out.mkdir(); shutil.copyfile(client, out / 'cas_client.mm')
    names = ['KeplerNativeCAS.h', 'KeplerProgramImport.h', 'KeplerNativeAllocation.h']
    for name in names:
        assert sha(library / 'src' / name) == sha(ROOT / 'src' / name)
        shutil.copyfile(ROOT / 'src' / name, out / name)
    shutil.copyfile(ROOT / 'tools/NativeAllocationExecution.inc', out / 'NativeAllocationExecution.inc')
    shutil.copytree(asset_build / 'assets', out / 'assets'); (out / 'runtime').mkdir()
    for name in ['local_memory.metallib', 'local2048.sass', 'local2048.json', 'local4096.sass', 'local4096.json']:
        assert sha(large / 'assets' / name) == large_inputs['assets_SHA256'][name]
        shutil.copyfile(large / 'assets' / name, out / 'assets' / ('large-' + name))
    for name, origin in [('lab_gpu_reservation.py', ROOT / 'tools/lab_gpu_reservation.py'), ('run_sdk_host.py', ROOT / 'sdk-combined/runtime/run_sdk_host.py')]:
        shutil.copyfile(origin, out / 'runtime' / name)
    run = commands(out)
    run('client', ['xcrun', 'clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fobjc-arc', '-I', out, out / 'cas_client.mm', library / 'libKeplerMetal.a', '-Wl,-ObjC', '-framework', 'Metal', '-framework', 'Foundation', '-o', out / 'cas_example'])
    write(out / 'inputs.json', dict(module_static_library_SHA256=lm['static_library_SHA256'],
        library_manifest_SHA256=sha(library / 'manifest.json'), source_asset_inputs_SHA256=sha(asset_build / 'inputs.json'),
        large_build_inputs_SHA256=sha(large / 'inputs.json'),
        source_hashes={n:sha(out / n) for n in ['cas_client.mm', 'NativeAllocationExecution.inc', *names]},
        assets={p.name:sha(p) for p in (out / 'assets').iterdir()},
        runtime_SHA256={p.name:sha(p) for p in (out / 'runtime').iterdir()},
        executable_SHA256=sha(out / 'cas_example'), builder_SHA256=sha(__file__), GPU_execution=False))


def run(a):
    build, out, reservation = a.build.resolve(), a.out.resolve(), a.reservation_root.resolve()
    assert not out.exists() and out.parent.is_dir() and (reservation / 'results').is_dir()
    inputs = read(build / 'inputs.json')
    for key, sub in [('source_hashes', ''), ('assets', 'assets'), ('runtime_SHA256', 'runtime')]:
        for name, digest in inputs[key].items(): assert sha(build / sub / name) == digest
    assert sha(build / 'cas_example') == inputs['executable_SHA256']
    out.mkdir(); (out / 'outputs').mkdir()
    for name in inputs['source_hashes']: shutil.copyfile(build / name, out / name)
    shutil.copyfile(build / 'cas_example', out / 'cas_example'); (out / 'cas_example').chmod(0o755)
    for name in ['assets', 'runtime']: shutil.copytree(build / name, out / name)
    write(out / 'inputs.json', inputs)
    sys.path.insert(0, str(out / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'cas_example', out / 'execution', [str(out / 'assets'), str(out / 'assets/client-manifest.json'), str(out / 'outputs'), a.mode], reservation)
    d = read(out / 'execution/execution.stdout'); write(out / 'results.json', d)
    from verify_native_cas_sdk import verify as verify_cas
    from verify_native_allocation_common import allocation_proof, native_record
    cas = verify_cas(out)
    assert d['large_inputs_wiped_before_commit'] and len(d['large_local_imports']) == 2
    for item, frame in zip(d['large_local_imports'], [8192, 16384]):
        proof = item['import']
        assert proof['contract_verified'] and proof['constructor_restored']
        events = [e for e in proof['events'] if e.get('code_replaced')]
        assert events and all(e['decoded_local_contract_verified'] and e['native_local_allocation_fields_preserved'] and e['imported_code_identical'] and e['code_input_unchanged_after_constructor'] and e['decoded_local_allocation_word'] == frame * 64 + 1536 for e in events)
    assert d['local_memory_import']['contract_verified'] and d['descriptor_transport_import']['contract_verified']
    allocation = allocation_proof(d['native_allocation_import'], out / 'assets/allocation-prelude.metallib', out / 'assets/allocation-prelude.certificate.json')
    if a.mode == 'execute':
        assert [r['function'] for r in d['large_local_postludes']] == ['local2048', 'local4096']
        post = [native_record(out, r) for r in [d['local_postlude'], d['native_allocation_postlude'], *d['large_local_postludes']]]
    else:
        assert d['local_postlude'] == d['native_allocation_postlude'] == {} and not d['large_local_postludes']
        post = []
    proof = dict(status='PASS', mode=a.mode, PID=manifest['pid'], CAS={k:v for k,v in cas.items() if k != 'records'},
        native_allocation=allocation, postludes=post, compute_command_buffers=cas['user_GPU_command_buffers'] + len(post),
        exact_uint32_results=cas.get('correct_uint32_words', 0) + sum(r['exact_uint32_results'] for r in post),
        guard_bytes=cas.get('guard_bytes_verified', 0) + sum(r['guard_bytes'] for r in post),
        static_library_SHA256=inputs['module_static_library_SHA256'], performance_benchmark=False, installed_driver_changed=False)
    write(out / 'independent-verification.json', proof)
    print(__import__('json').dumps({k:v for k,v in proof.items() if k not in ['postludes', 'native_allocation']}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='action', required=True)
    q = sub.add_parser('build'); q.add_argument('--library', type=Path, required=True); q.add_argument('--asset-build', type=Path, required=True); q.add_argument('--large-build', type=Path, required=True); q.add_argument('--out', type=Path, required=True); q.set_defaults(fn=build)
    q = sub.add_parser('run'); q.add_argument('--build', type=Path, required=True); q.add_argument('--out', type=Path, required=True); q.add_argument('--reservation-root', type=Path, required=True); q.add_argument('--mode', choices=['negative', 'execute'], required=True); q.set_defaults(fn=run)
    a = p.parse_args(); a.fn(a)


if __name__ == '__main__': main()
