#!/usr/bin/env python3
"""Build an isolated corrected AIR frontend, compile single-CAS kernels offline.
Never alter vendor originals or installed macOS components, and never dispatch GPU work.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, shlex, shutil, subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
OUT = args.out.resolve()
OUT.relative_to(ROOT / 'results')
assert not OUT.exists()
OUT.mkdir()
commands = []
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def run(command, label, cwd=ROOT, acceptable=(0,)):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=55)
    (OUT / (label + '.stdout')).write_text(result.stdout)
    (OUT / (label + '.stderr')).write_text(result.stderr)
    commands.append({'label': label, 'argv': command, 'cwd': str(cwd), 'exit_code': result.returncode})
    (OUT / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    print(label, result.returncode, flush=True)
    if result.returncode not in acceptable:
        raise SystemExit(result.stderr[-4000:] or f'{label} failed: {result.returncode}')
    return result

upstream = ROOT / 'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5'
original = upstream / 'tools/nakc/air_nir.c'
original_sha = sha(original)
fork = OUT / 'source-fork'
fork_source = fork / 'tools/nakc/air_nir.c'
fork_source.parent.mkdir(parents=True)
shutil.copyfile(original, fork_source)
patch = ROOT / 'src/opennvda-air-cas-result.patch'
shutil.copyfile(patch, OUT / patch.name)
run(['patch', '--batch', '--dry-run', '-p1', '-i', str(patch)], 'check-local-patch', fork)
run(['patch', '--batch', '-p1', '-i', str(patch)], 'apply-local-patch', fork)
assert sha(original) == original_sha

build = ROOT / 'build/mesa'
entry = next(row for row in json.loads((build / 'compile_commands.json').read_text())
             if row['file'].endswith('/nak_nir.c'))
flags = [arg for arg in shlex.split(entry['command'])[1:]
         if arg.startswith(('-I', '-D', '-std', '-f', '-W')) and not arg.startswith('-Werror')]
flags += ['-I' + str(upstream / 'drivers/NVMTLDriver/air'), '-I' + str(upstream / 'tools/nakc'),
          '-Werror=implicit-function-declaration']
harness = OUT / 'air_cas_compile.c'
shutil.copyfile(ROOT / 'tools/air_cas_compile.c', harness)
objects = []
for name, source in [('harness', harness), ('air_nir', fork_source)]:
    obj = OUT / (name + '.o')
    run(['clang', '-O1'] + flags + ['-c', str(source), '-o', str(obj)], 'compile-' + name, build)
    objects.append(obj)
objects += [ROOT / ('build/air-' + name + '.o') for name in ['bitstream', 'airir', 'metallib']]
archives = ['src/nouveau/compiler/libnak.a', 'src/nouveau/compiler/libnak_rs.a',
            'src/compiler/nir/libnir.a', 'src/compiler/libcompiler.a',
            'src/nouveau/headers/libnvidia_headers_c.a', 'src/util/libmesa_util.a',
            'src/util/libmesa_util_simd.a', 'src/util/blake3/libblake3.a',
            'src/c11/impl/libmesa_util_c11.a', 'src/compiler/rust/libcompiler_c_helpers.a',
            'src/compiler/rust/libcompiler_bindings.a']
compiler = OUT / 'air_cas_compile'
run(['clang', '-o', str(compiler)] + [str(p) for p in objects] + archives +
    ['-lz', '-lpthread', '-lc++', '-framework', 'CoreFoundation', '-framework', 'Security'],
    'link-offline', build)
records = []
for space in ['device', 'threadgroup']:
    directory = OUT / space
    directory.mkdir()
    init = ('device atomic_uint *a=&global[i];' if space == 'device' else
            'threadgroup atomic_uint shared[1];threadgroup atomic_uint *a=&shared[0];'
            'if(tid==0)atomic_store_explicit(a,initial,memory_order_relaxed);'
            'threadgroup_barrier(mem_flags::mem_threadgroup);')
    flag = 'mem_device' if space == 'device' else 'mem_threadgroup'
    source = ('#include <metal_stdlib>\nusing namespace metal;\n'
              'struct P {uint seed,n,local,groups,variant;};\n'
              'kernel void test(constant P &p [[buffer(0)]],device uint4 *out [[buffer(1)]],'
              'device atomic_uint *global [[buffer(3)]],uint i [[thread_position_in_grid]],'
              'uint tid [[thread_index_in_threadgroup]],uint group [[threadgroup_position_in_grid]]){'
              'uint initial=p.seed+group*0x10001u;uint replacement=p.seed^0x55667788u;' + init +
              'uint compare=initial^(p.variant?1u:0u);'
              'bool success=atomic_compare_exchange_weak_explicit(a,&compare,replacement,'
              'memory_order_relaxed,memory_order_relaxed);'
              'threadgroup_barrier(mem_flags::' + flag + ');'
              'uint final=atomic_load_explicit(a,memory_order_relaxed);'
              'out[i]=uint4(compare,uint(success),final,i);}\n')
    (directory / 'test.metal').write_text(source)
    run(['xcrun', 'metal', '-std=macos-metal2.4', '-fno-fast-math', '-c',
         str(directory / 'test.metal'), '-o', str(directory / 'test.air')], space + '-metal')
    run(['xcrun', 'metallib', str(directory / 'test.air'), '-o', str(directory / 'test.metallib')],
        space + '-metallib')
    execution = OUT / (space + '-offline-execution')
    run(['python3', str(ROOT / 'tools/run_signed_probe.py'), '--exe', str(compiler),
         '--out', str(execution), '--timeout', '20', '--', str(directory / 'test.air'),
         str(directory), 'test', '1', '2'], space + '-offline-launch')
    process = json.loads((execution / 'manifest.json').read_text())
    assert not process['authoritative_ps_status']
    info = json.loads((execution / 'execution.stdout').read_text())
    # Import is only attempted later if all these physical/resource contracts hold.
    assert info['sm'] == 30 and info['local_size'] == [1, 1, 1]
    assert info['buffer_slots'] == 4 and info['push_bytes'] == 56 and info['grid_offset'] == 32
    assert info['constant_bank'] == 2 and not info['scratch_bytes'] and not info['crs_bytes']
    assert info['registers'] <= 63 and info['shared_bytes'] <= 128
    (directory / 'info.json').write_text(json.dumps(info, indent=2) + '\n')
    records.append({'space': space, 'directory': str(directory), 'info': info})
inputs = [harness, fork_source, patch, original, ROOT / 'tools/run_signed_probe.py',
          *objects[2:], *[build / path for path in archives]]
manifest = {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'records': records, 'original_source_unchanged': sha(original) == original_sha,
            'input_hashes': {str(path): sha(path) for path in inputs},
            'compiler_sha256': sha(compiler), 'gpu_dispatch': False,
            'scope': 'Offline AIR→NIR→SM30 compilation; local source patch, not a native-driver repair.'}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'out': str(OUT), 'compiled': len(records), 'gpu_dispatch': False}, indent=2))
