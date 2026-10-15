#!/usr/bin/env python3
"""Compile only Mesa's shader compiler archives in the isolated workspace."""
from pathlib import Path
import subprocess
import os
import json

root = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env['PATH'] = str(root/'build/rust-prefix/bin') + ':' + str(root/'build/python312-env/bin') + ':' + env['PATH']
env['LIBCLANG_PATH'] = '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib'
env['CARGO_HOME'] = str(root/'build/cargo-home')
configure = [str(root/'build/python312-env/bin/meson'), 'setup', str(root/'build/mesa'),
             str(root/'vendor/mesa-26.2.4'), '--buildtype=release',
             '--prefix='+str(root/'build/mesa-prefix'),
             '-Dgallium-drivers=[]', '-Dvulkan-drivers=nouveau', '-Dplatforms=[]',
             '-Dglx=disabled', '-Degl=disabled', '-Dgbm=disabled',
             '-Dgles1=disabled', '-Dgles2=disabled', '-Dopengl=false',
             '-Dllvm=disabled', '-Dxmlconfig=disabled', '-Dvideo-codecs=[]',
             '-Dbuild-tests=false', '-Dvalgrind=disabled', '-Dlibunwind=disabled']
archives = ['src/nouveau/compiler/libnak.a', 'src/nouveau/compiler/libnak_rs.a',
            'src/compiler/nir/libnir.a', 'src/compiler/libcompiler.a',
            'src/nouveau/headers/libnvidia_headers_c.a',
            'src/util/libmesa_util.a', 'src/util/libmesa_util_simd.a',
            'src/util/blake3/libblake3.a', 'src/c11/impl/libmesa_util_c11.a',
            'src/compiler/rust/libcompiler_c_helpers.a',
            'src/compiler/rust/libcompiler_bindings.a']
commands = [configure, [str(root/'build/python312-env/bin/ninja'), '-C', str(root/'build/mesa'), '-j2'] + archives]
status = []
for label, command in zip(('configure', 'build'), commands):
    with (root/('logs/offline-'+label+'.log')).open('w') as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=log)
    status.append({'stage': label, 'command': command, 'exit_code': result.returncode})
    (root/'results/offline-compiler-build.json').write_text(json.dumps({
        'scope': 'compiler archives only; no driver installed or native GPU submission',
        'commands': status, 'environment': {k:env[k] for k in ('PATH','CARGO_HOME','LIBCLANG_PATH')},
    }, indent=2)+'\n')
    print(label, 'exit', result.returncode, flush=True)
    if result.returncode:
        print((root/('logs/offline-'+label+'.log')).read_text()[-5000:])
        raise SystemExit(result.returncode)
