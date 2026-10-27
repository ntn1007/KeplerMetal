#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and test a single, pinned, opt-in standalone Metal client.

This is an experimental process-local integration test, not a general Metal
implementation. All hardware hosts are serialized via the laboratory lease.
"""
from pathlib import Path
import argparse, json, os, shutil, subprocess, sys

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
sys.path.insert(0, str(BRIDGE / 'tools'))
from public_large_scratch import check_library, check_driver_profile, commands, preflight, read, sha, write

CARRIER_SHA = '965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
MODES = ('direct', 'auto', 'auto-native', 'wrong-library', 'wrong-client')

def build(args):
    out, lib = args.out.resolve(), args.library.resolve()
    preflight(out)
    assert sha(HERE/'client.mm') == '0a6cc2f28b3b23f2518746417b635ba07334fd09abc938fc9a8629470480943d', 'Client source changed; qualify a new profile'
    assert sha(BRIDGE/'tools/ordinary_metal_client.mm') == '8f0bf04d18b3e91113788ad08d2fe97ecf1f5d50cc5746fb8ddf9ff684810042', 'Metal client changed; qualify a new profile'
    manifest = check_library(lib)
    out.mkdir()
    for folder in ('src', 'assets', 'runtime', 'library-src'):
        (out / folder).mkdir()
    for name in manifest['source_SHA256']:
        shutil.copyfile(lib / 'src' / name, out / 'library-src' / name)
    for name in ('client.mm', 'bootstrap.mm', 'verify.py'):
        shutil.copyfile(HERE / name, out / 'src' / name)
    shutil.copyfile(HERE / 'run_host.py', out / 'runtime/run_host.py')
    shutil.copyfile(BRIDGE / 'tools/lab_gpu_reservation.py', out / 'runtime/lab_gpu_reservation.py')
    shutil.copyfile(BRIDGE / 'tools/ordinary_metal_client.mm', out / 'src/ordinary_metal_client.mm')
    carrier = (BRIDGE / 'src/render_state_carrier.metal').read_text()
    (out / 'src/carrier.metal').write_text(carrier)
    assert carrier.count('return float4(.75,.125,.25,1);') == 1
    (out / 'src/wrong_carrier.metal').write_text(carrier.replace('return float4(.75,.125,.25,1);', 'return float4(.5,.125,.25,1);', 1))
    run = commands(out)
    for name in ('carrier', 'wrong_carrier'):
        run(name + '-metal', ['xcrun','metal','-std=macos-metal2.4','-c',out / ('src/' + name + '.metal'),'-o',out / (name + '.air')])
        run(name + '-metallib', ['xcrun','metallib',out / (name + '.air'),'-o',out / ('assets/' + name + '.metallib')])
    assert sha(out / 'assets/carrier.metallib') == CARRIER_SHA
    assert sha(out / 'assets/wrong_carrier.metallib') != CARRIER_SHA
    run('client', ['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'src/client.mm',out/'src/ordinary_metal_client.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
    run('client-symbols', ['nm','-u',out/'application'])
    imports = (out/'client-symbols.stdout').read_text()
    assert 'Kepler' not in imports and 'KPCPU' not in imports
    run('client-sign', ['codesign','--force','--sign','-',out/'application'])
    run('client-sign-check', ['codesign','--verify','--strict',out/'application'])
    app_sha = sha(out/'application')
    # Negative identity control: one byte of the test executable's own diagnostic.
    original = (out/'application').read_bytes()
    assert original.count(b'no device\n') == 1
    variant = out/'assets/wrong-application'
    variant.write_bytes(original.replace(b'no device\n',b'No device\n',1)); variant.chmod(0o755)
    run('wrong-client-sign', ['codesign','--force','--sign','-',variant])
    assert sha(variant) != app_sha
    run('bootstrap', ['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-dynamiclib','-I',out/'library-src',f'-DKM_APPROVED_APP_SHA256="{app_sha}"',out/'src/bootstrap.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'assets/bootstrap.dylib'])
    run('bootstrap-sign', ['codesign','--force','--sign','-',out/'assets/bootstrap.dylib'])
    run('bootstrap-sign-check', ['codesign','--verify','--strict',out/'assets/bootstrap.dylib'])
    frozen = {str(p.relative_to(out)):sha(p) for folder in ('src','assets','runtime','library-src') for p in (out/folder).iterdir() if p.is_file()}
    write(out/'inputs.json', {'frozen':frozen,'executable_SHA256':app_sha,'static_library_SHA256':manifest['static_library_SHA256'],'GPU_execution':False,'client_imports_project_symbols':False})

def run(args):
    build, out = args.build.resolve(), args.out.resolve()
    manifest = read(build/'inputs.json')
    assert not out.exists() and out.parent.is_dir()
    for name, digest in manifest['frozen'].items():
        assert sha(build/name) == digest, name
    assert sha(build/'application') == manifest['executable_SHA256']
    driver = check_driver_profile()
    out.mkdir()
    for folder in ('src','assets','runtime','library-src'):
        shutil.copytree(build/folder, out/folder)
    shutil.copyfile(build/('assets/wrong-application' if args.mode == 'wrong-client' else 'application'), out/'application')
    (out/'application').chmod(0o755)
    (out/'outputs').mkdir()
    write(out/'inputs.json', dict(manifest,mode=args.mode,driver_SHA256=driver,build_inputs_SHA256=sha(build/'inputs.json'),run_executable_SHA256=sha(out/'application')))
    env = {k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','KM_'))}
    if args.mode in ('auto','wrong-library','wrong-client'):
        env['DYLD_INSERT_LIBRARIES'] = str(out/'assets/bootstrap.dylib')
        env['KM_CARRIER_PATH'] = str(out/'assets/carrier.metallib')
        env['KM_EVENT_PATH'] = str(out/'events.json')
    client_mode = 'direct' if args.mode == 'direct' else 'auto'
    library = 'wrong_carrier.metallib' if args.mode == 'wrong-library' else 'carrier.metallib'
    expected_exit = 3 if args.mode == 'wrong-client' else 7 if args.mode in ('auto-native','wrong-library') else 0
    sys.path.insert(0,str(out/'runtime'))
    from run_host import run_host
    result = run_host(out/'application', out/'execution', [str(out/'assets'/library),str(out/'outputs'),client_mode], args.reservation_root.resolve(), child_env=env, expected_exit=expected_exit)
    check = subprocess.run([sys.executable,'-I',str(out/'src/verify.py'),str(out)],capture_output=True,text=True)
    (out/'verification.stdout').write_text(check.stdout)
    (out/'verification.stderr').write_text(check.stderr)
    write(out/'verification-execution.json',{'exit_code':check.returncode,'isolated_interpreter':True})
    if check.returncode:
        raise RuntimeError('Independent oracle failed; inspect ' + str(out/'verification.stderr'))
    print(check.stdout.strip(), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True)
    b = sub.add_parser('build')
    for name in ('library','out'):
        b.add_argument('--'+name,type=Path,required=True)
    b.set_defaults(func=build)
    r = sub.add_parser('run')
    for name in ('build','out','reservation-root'):
        r.add_argument('--'+name,type=Path,required=True)
    r.add_argument('--mode',choices=MODES,required=True)
    r.set_defaults(func=run)
    a = parser.parse_args()
    a.func(a)
