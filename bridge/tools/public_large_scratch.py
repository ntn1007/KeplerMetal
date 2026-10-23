#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce bounded local-memory tests from public text and local dependencies.

Builds do not submit GPU work. The run phase requires an explicit common host
reservation. No driver, SDK, compiled program or private fixture is downloaded.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAGIC = 0x4e414b00
DRIVER = Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver')
DRIVER_SHA256 = '2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054'
ARCHIVES = ['src/nouveau/compiler/libnak.a', 'src/nouveau/compiler/libnak_rs.a',
    'src/compiler/nir/libnir.a', 'src/compiler/libcompiler.a',
    'src/nouveau/headers/libnvidia_headers_c.a', 'src/util/libmesa_util.a',
    'src/util/libmesa_util_simd.a', 'src/util/blake3/libblake3.a',
    'src/c11/impl/libmesa_util_c11.a', 'src/compiler/rust/libcompiler_c_helpers.a',
    'src/compiler/rust/libcompiler_bindings.a']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check_driver_profile():
    """Reject before signing, reserving or starting a Metal process. No repinning."""
    actual = sha(DRIVER)
    if actual != DRIVER_SHA256:
        raise RuntimeError(f'Installed GeForceMTLDriver profile changed: expected {DRIVER_SHA256}, got {actual}; GPU execution NOT RUN; qualify a new profile separately')
    return actual


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def check_library(folder):
    m = read(folder / 'manifest.json')
    expected = {'KeplerCPUICB.o', 'KeplerNativeCommands.o', 'KeplerNativeRenderDraws.o',
        'KeplerNativeCAS.o', 'KeplerFP64.o', 'KeplerProgramImport.o', 'KeplerCommandIRProducerFactory.o'}
    assert m['status'] == 'PASS' and m['architecture'] == 'x86_64' and m['SDK'] == '26.2'
    assert set(m['object_SHA256']) == expected, 'Qualify the complete public seven-object archive'
    assert {name[:-2] + '.mm' for name in expected} <= set(m['source_SHA256'])
    assert sha(folder / 'libKeplerMetal.a') == m['static_library_SHA256']
    for name, digest in m['source_SHA256'].items():
        assert sha(folder / 'src' / name) == digest == sha(ROOT / 'src' / name)
    for name, digest in m['object_SHA256'].items(): assert sha(folder / name) == digest
    assert sha(folder / 'src/KeplerNativeCAS.mm') == sha(ROOT / 'src/KeplerNativeCAS.mm')
    return m


def commands(out):
    history = []
    def run(label, argv, cwd=None, additions=None):
        argv = list(map(str, argv)); env = os.environ.copy(); env.pop('NAK_DEBUG', None)
        env.update(additions or {})
        r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
        (out / (label + '.stdout')).write_text(r.stdout); (out / (label + '.stderr')).write_text(r.stderr)
        history.append(dict(label=label, argv=argv, cwd=str(cwd) if cwd else None,
            environment=additions or {}, exit_code=r.returncode))
        (out / 'commands.json').write_text(json.dumps(history, indent=2) + '\n')
        if r.returncode: raise RuntimeError(f'{label} failed ({r.returncode}); inspect saved stderr')
        print(label, 'PASS', flush=True)
        return r.stdout
    return run


def preflight(out):
    assert platform.system() == 'Darwin' and platform.machine() == 'x86_64'
    assert subprocess.check_output(['xcrun', '--show-sdk-version'], text=True).strip() == '26.2'
    assert out.parent.is_dir() and not out.exists(), 'Use a new directory beneath an existing parent'
    assert shutil.disk_usage(out.parent).free >= 512 * 1024**2


def programs(a):
    out, mesa = a.out.resolve(), a.mesa_build.resolve()
    preflight(out)
    archive_hashes = {n:sha(mesa / n) for n in ARCHIVES}
    entry = next(x for x in read(mesa / 'compile_commands.json') if x['file'].endswith('/nak_nir.c'))
    flags = [x for x in shlex.split(entry['command'])[1:] if x.startswith(('-I', '-D', '-std', '-f', '-W')) and not x.startswith('-Werror')]
    source = ROOT / 'tools/local_memory_large_scratch_compile.c'
    text = source.read_text()
    if a.witness:
        assert text.count('0xcafe0000u') == 1
        text = text.replace('0xcafe0000u', '0x4e414b00u')
    out.mkdir(); (out / source.name).write_text(text)
    shutil.copyfile(ROOT / 'src/KeplerResourceABI.h', out / 'KeplerResourceABI.h')
    run = commands(out)
    run('compile', ['xcrun', 'clang', '-O1', *flags, '-I', out, '-c', out / source.name, '-o', out / 'compiler.o'], mesa)
    run('link', ['xcrun', 'clang', '-o', out / 'compiler', out / 'compiler.o', *ARCHIVES, '-lz', '-lpthread', '-lc++', '-framework', 'CoreFoundation', '-framework', 'Security'], mesa)
    modes = ['local2048', 'local4096'] if a.witness else ['local_control', 'local32', 'local256', 'local1024', 'pressure32', 'pressure64', 'pressure96', 'local2048', 'local4096', 'pressure32_forced_spill']
    records = []
    for name in modes:
        forced = name.endswith('_forced_spill'); semantic = name.removesuffix('_forced_spill')
        info = json.loads(run(name, [out / 'compiler', semantic, out / (name + '.sass'), out / (name + '.asm')], mesa, {'NAK_DEBUG':'spill'} if forced else None))
        assert info['sm'] == 30 and not info['crs_bytes'] and 24 <= info['registers'] <= 63
        assert info['code_bytes'] == (out / (name + '.sass')).stat().st_size <= 65536
        if a.witness: info['execution_witness_magic'] = MAGIC
        write(out / (name + '.json'), info)
        records.append(dict(name=name, info=info, code_SHA256=sha(out / (name + '.sass'))))
    write(out / 'manifest.json', dict(status='BUILT_NOT_GPU_QUALIFIED', programs=records,
        source_SHA256=sha(out / source.name), resource_ABI_SHA256=sha(out / 'KeplerResourceABI.h'),
        archives_SHA256=archive_hashes, compiler_SHA256=sha(out / 'compiler'),
        execution_witness_magic=MAGIC if a.witness else None, builder_SHA256=sha(__file__), GPU_execution=False))


def build(a):
    out, lib, source_programs = a.out.resolve(), a.library.resolve(), a.programs.resolve()
    preflight(out); lm = check_library(lib); pm = read(source_programs / 'manifest.json')
    source = ROOT / 'src' / ('kepler_local_memory.metal' if a.carrier == 'legacy' else 'kepler_large_scratch.metal')
    expected = ('bb052086f1a0f8ce1a2cad8da00c74926ac47abe0d0b95d3b1f66cf24f4d3d5d'
        if a.carrier == 'legacy' else '62a49cf2ea3a3e4daec94cb7cf6c35abb2828101b74c47a8ea6d16d042137424')
    for row in pm['programs']:
        assert sha(source_programs / (row['name'] + '.sass')) == row['code_SHA256']
    out.mkdir(); (out / 'assets').mkdir(); (out / 'runtime').mkdir()
    shutil.copyfile(source, out / source.name)
    run = commands(out)
    run('metal', ['xcrun', 'metal', '-std=macos-metal2.3', '-c', out / source.name, '-o', out / 'local_memory.air'])
    run('metallib', ['xcrun', 'metallib', out / 'local_memory.air', '-o', out / 'assets/local_memory.metallib'])
    assert sha(out / 'assets/local_memory.metallib') == expected, 'A different carrier needs separate qualification; do not repin to bypass this check'
    for row in pm['programs']:
        for suffix in ['.sass', '.json']:
            shutil.copyfile(source_programs / (row['name'] + suffix), out / 'assets' / (row['name'] + suffix))
    names = ['native_large_scratch_probe.mm', 'native_large_scratch_import_contract.mm']
    for name in names: shutil.copyfile(ROOT / 'tools' / name, out / name)
    shutil.copyfile(lib / 'src/KeplerProgramImport.h', out / 'KeplerProgramImport.h')
    for name, src in [('application', names[0]), ('contracts', names[1])]:
        run(name, ['xcrun', 'clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fobjc-arc', '-DKP_LOCAL_IMPORT=1', '-DKP_LOCAL_EXTENDED=' + str(int(a.extended)), '-I', out, out / src, lib / 'libKeplerMetal.a', '-Wl,-ObjC', '-framework', 'Metal', '-framework', 'Foundation', '-o', out / name])
    for name, origin in [('lab_gpu_reservation.py', ROOT / 'tools/lab_gpu_reservation.py'), ('run_sdk_host.py', ROOT / 'sdk-combined/runtime/run_sdk_host.py')]:
        shutil.copyfile(origin, out / 'runtime' / name)
    write(out / 'inputs.json', dict(source_hashes={n:sha(out / n) for n in [*names, 'KeplerProgramImport.h', source.name]},
        assets_SHA256={p.name:sha(p) for p in (out / 'assets').iterdir()},
        runtime_SHA256={p.name:sha(p) for p in (out / 'runtime').iterdir()},
        static_library_SHA256=lm['static_library_SHA256'], library_manifest_SHA256=sha(lib / 'manifest.json'),
        programs_manifest_SHA256=sha(source_programs / 'manifest.json'), executable_SHA256=sha(out / 'application'),
        contract_executable_SHA256=sha(out / 'contracts'), extended_profile=a.extended, carrier=a.carrier,
        execution_witness_magic=pm.get('execution_witness_magic'), memory_ledger_schema=1,
        oracle_SHA256=sha(ROOT / 'tools/verify_local_memory.py'), builder_SHA256=sha(__file__), GPU_execution=False))


def run(a):
    build, out, reservation = a.build.resolve(), a.out.resolve(), a.reservation_root.resolve()
    assert not out.exists() and out.parent.is_dir()
    assert (reservation / 'results').is_dir(), 'Use the existing common reservation root for this physical GPU'
    assert shutil.disk_usage(reservation).free >= 128 * 1024**2 and shutil.disk_usage(out.parent).free >= 128 * 1024**2
    inputs = read(build / 'inputs.json')
    assert inputs.get('execution_witness_magic') in [None, MAGIC]
    for key, sub in [('source_hashes', ''), ('assets_SHA256', 'assets'), ('runtime_SHA256', 'runtime')]:
        for name, digest in inputs[key].items(): assert sha(build / sub / name) == digest
    executable = 'contracts' if a.contracts else 'application'
    digest = inputs['contract_executable_SHA256' if a.contracts else 'executable_SHA256']
    assert sha(build / executable) == digest
    if inputs.get('memory_ledger_schema') == 1:
        assert sha(ROOT / 'tools/verify_local_memory.py') == inputs['oracle_SHA256'], 'Oracle changed after build; freeze a new build'
    if a.contracts: assert a.mode in ['construct', 'negative'] and not inputs.get('execution_witness_magic')
    check_driver_profile()
    out.mkdir(); (out / 'outputs').mkdir()
    for name in inputs['source_hashes']: shutil.copyfile(build / name, out / name)
    shutil.copyfile(build / executable, out / 'application'); (out / 'application').chmod(0o755)
    shutil.copytree(build / 'assets', out / 'assets'); shutil.copytree(build / 'runtime', out / 'runtime')
    actual_inputs = dict(inputs, executable_SHA256=digest, source_build_inputs_SHA256=sha(build / 'inputs.json'))
    write(out / 'inputs.json', actual_inputs)
    sys.path.insert(0, str(out / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution', [str(out / 'assets'), str(out / 'outputs'), a.mode], reservation)
    result = read(out / 'execution/execution.stdout'); write(out / 'results.json', result)
    if a.contracts:
        assert result['status'] == 'PASS' and result['constructor_restored'] and result['GPU_command_buffers'] == result['GPU_dispatches'] == 0
        assert all(r['PASS'] and r['constructor_restored'] for r in result['runs'])
        proof = dict(status='PASS', contract_cases=len(result['runs']),
            expected_rejections=sum(r['expected_rejection'] for r in result['runs']),
            pipelines_created=sum(r['pipeline_created'] for r in result['runs']), kernel_dispatches=0)
    else:
        import verify_local_memory as oracle
        original = oracle.result
        try:
            if inputs.get('execution_witness_magic'):
                def tagged(name, gid, seed):
                    x, y, z, unused = original(name, gid, seed)
                    return x, y, z, MAGIC ^ gid
                oracle.result = tagged
            proof = oracle.verify(out, require_memory_ledger=inputs.get('memory_ledger_schema') == 1)
        finally:
            oracle.result = original
        if inputs.get('execution_witness_magic'): proof['execution_witness_magic'] = MAGIC
    proof['oracle_SHA256'] = sha(ROOT / 'tools/verify_local_memory.py')
    proof['public_runner_SHA256'] = sha(__file__)
    write(out / 'independent-verification.json', proof)
    print(json.dumps(dict(mode=a.mode, PID=manifest['pid'], **{k:v for k,v in proof.items() if k != 'files_SHA256'})), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    q = sub.add_parser('programs'); q.add_argument('--mesa-build', type=Path, required=True); q.add_argument('--witness', action='store_true')
    q.add_argument('--out', type=Path, required=True); q.set_defaults(fn=programs)
    q = sub.add_parser('build'); q.add_argument('--library', type=Path, required=True); q.add_argument('--programs', type=Path, required=True)
    q.add_argument('--carrier', choices=['large', 'legacy'], default='large'); q.add_argument('--extended', action='store_true')
    q.add_argument('--out', type=Path, required=True); q.set_defaults(fn=build)
    q = sub.add_parser('run'); q.add_argument('--build', type=Path, required=True); q.add_argument('--out', type=Path, required=True)
    q.add_argument('--reservation-root', type=Path, required=True); q.add_argument('--mode', required=True); q.add_argument('--contracts', action='store_true'); q.set_defaults(fn=run)
    a = p.parse_args(); a.fn(a)


if __name__ == '__main__': main()
