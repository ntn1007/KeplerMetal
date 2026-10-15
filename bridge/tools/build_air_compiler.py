#!/usr/bin/env python3
"""Build and run the small AIR/SM30 harness with pinned upstream components."""
from pathlib import Path
import os
import json
import shlex
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--objects-only', action='store_true')
parser.add_argument('--constant-buffer-index',type=int,default=0,choices=range(8))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
build = root/'build/mesa'
upstream = root/'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5'
air = upstream/'drivers/NVMTLDriver/air'
compiler = upstream/'tools/nakc'
entries = json.loads((build/'compile_commands.json').read_text())
entry = next(e for e in entries if e['file'].endswith('/nak_nir.c'))
flags = [a for a in shlex.split(entry['command'])[1:]
         if a.startswith(('-I', '-D', '-std', '-f', '-W')) and not a.startswith('-Werror')]
flags += ['-I'+str(air), '-I'+str(compiler), '-Werror=implicit-function-declaration']
sources = [root/'tools/kepler_air_compile.c', compiler/'air_nir.c',
           air/'bitstream.c', air/'airir.c', air/'metallib.c']
objects = []
status = []
def run(command, label, output=None):
    with (root/('logs/'+label+'.log')).open('w') as log:
        if output:
            with output.open('w') as out:
                result = subprocess.run(command, cwd=build, stdout=out, stderr=log)
        else:
            result = subprocess.run(command, cwd=build, stdout=log, stderr=log)
    status.append({'stage':label, 'command':command, 'exit_code':result.returncode})
    (root/'results/air-sm30-build.json').write_text(json.dumps(status, indent=2)+'\n')
    print(label, 'exit', result.returncode, flush=True)
    if result.returncode:
        print((root/('logs/'+label+'.log')).read_text()[-5000:])
        raise SystemExit(result.returncode)

for source in sources:
    obj = root/('build/air-'+source.stem+'.o')
    run(['clang','-O1']+flags+['-c',str(source),'-o',str(obj)], 'compile-'+source.stem)
    objects.append(str(obj))
if args.objects_only:
    raise SystemExit(0)
archives = ['src/nouveau/compiler/libnak.a', 'src/nouveau/compiler/libnak_rs.a',
            'src/compiler/nir/libnir.a', 'src/compiler/libcompiler.a',
            'src/nouveau/headers/libnvidia_headers_c.a',
            'src/util/libmesa_util.a', 'src/util/libmesa_util_simd.a',
            'src/util/blake3/libblake3.a', 'src/c11/impl/libmesa_util_c11.a',
            'src/compiler/rust/libcompiler_c_helpers.a',
            'src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(root/'build/kepler_air_compile')]+objects+archives+
    ['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'], 'link-air-sm30')
for extension in ('air', 'metallib'):
    suffix='' if args.constant_buffer_index==0 else '-cb'+str(args.constant_buffer_index)
    run([str(root/'build/kepler_air_compile'), str(root/('build/add_buffers.'+extension)),
         str(root/('build/add_buffers-'+extension+suffix+'.sass')),
         str(root/('results/add_buffers-'+extension+suffix+'.asm')),str(args.constant_buffer_index)],
        'run-air-sm30-'+extension+suffix, root/('results/air-sm30-'+extension+suffix+'.json'))
