#!/usr/bin/env python3
"""Rebuild local NAK graphics and verify CPU oracles; no driver installation.

Requires the already prepared Mesa/compiler archives, local Rust/Meson tools,
and Envytools decoder. Timing fields are diagnostics, not a graphics benchmark.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shlex
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--out', type=Path, default=root/'results/graphics-reproduction')
args = parser.parse_args()
out = args.out.resolve(); out.relative_to(root/'results'); out.mkdir(parents=True, exist_ok=True)
driver = Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
before = sha(driver)
expected = json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
if before != expected: raise SystemExit('Driver changed: revalidate the program ABI before import.')
commands = []; cases = []
def run(command, label, cwd=root, environment=None):
    env = os.environ.copy()
    for key in ('KEPLER_VERTEX_CODE', 'KEPLER_VERTEX_INFO', 'KEPLER_RENDER_OUTPUT_DIR'):
        env.pop(key, None)
    if environment: env.update(environment)
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    (out/(label+'.stdout')).write_text(result.stdout)
    (out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label, 'command':command, 'cwd':str(cwd),
                     'environment':environment or {}, 'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
    print(label, result.returncode, flush=True)
    if result.returncode:
        print(result.stderr[-2000:]); raise SystemExit(result.returncode)
    return result.stdout

run(['python3',str(root/'tools/prepare_texture_compiler.py')], 'local-compiler-patch')
compilerEnv = {'PATH':str(root/'build/rust-prefix/bin')+':'+str(root/'build/python312-env/bin')+':'+os.environ['PATH'],
               'LIBCLANG_PATH':'/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib',
               'CARGO_HOME':str(root/'build/cargo-home')}
build = root/'build/mesa'
run([str(root/'build/python312-env/bin/ninja'), '-C',str(build),'-j2',
     'src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a'], 'nak-incremental-build', environment=compilerEnv)
entries = json.loads((build/'compile_commands.json').read_text())
entry = next(e for e in entries if e['file'].endswith('/nak_nir.c'))
flags = [a for a in shlex.split(entry['command'])[1:] if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
archives = ['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a',
            'src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a',
            'src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a',
            'src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
for name in ('graphics_fragment_compile','kepler_compute_suite'):
    obj = root/'build'/f'{name}.o'
    run(['clang','-O1']+flags+['-c',str(root/'tools'/f'{name}.c'),'-o',str(obj)],name+'-compile', build)
    run(['clang','-o',str(root/'build'/name),str(obj)]+archives+
        ['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],name+'-link',build)
run(['clang++','-O3','-std=c++17','-fno-objc-arc','-dynamiclib',str(root/'src/KeplerProgramImport.mm'),
     '-framework','Metal','-framework','Foundation','-install_name','@rpath/libKeplerProgramImport.dylib',
     '-o',str(root/'build/libKeplerProgramImport.dylib')], 'import-library-build')
for name in ('render_reference_probe','compute_suite_probe'):
    cmd = ['clang++','-O3','-std=c++17','-fno-objc-arc',str(root/'tools'/f'{name}.mm'),
           '-I'+str(root/'src'),'-L'+str(root/'build'),'-lKeplerProgramImport','-Wl,-rpath,'+str(root/'build'),
           '-framework','Metal','-framework','Foundation']
    if name == 'compute_suite_probe': cmd += ['-framework','Accelerate']
    run(cmd+['-o',str(root/'build'/name)],name+'-build')
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src/graphics_reference.metal'),
     '-o',str(root/'build/graphics_reference.air')], 'graphics-carrier-air')
run(['xcrun','-sdk','macosx','metallib',str(root/'build/graphics_reference.air'),
     '-o',str(root/'build/graphics_reference.metallib')], 'graphics-carrier-metallib')
shaders = {}
for kind in ('constant','read','nearest','linear','vertex','vertex_half'):
    code = out/(kind+'.sass'); infoPath = out/(kind+'-info.json')
    info = json.loads(run([str(root/'build/graphics_fragment_compile'),str(code),str(out/(kind+'.asm')),
                          str(out/(kind+'.sph')),kind],kind+'-shader-compile'))
    infoPath.write_text(json.dumps(info,indent=2)+'\n')
    decoded = run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(code)],kind+'-decode')
    if '[unknown' in decoded: raise SystemExit('Decoder found an unknown instruction or operand.')
    shaders[kind] = (code, infoPath)

def render(label, kind=None, vertex=None, floating=False):
    cmd = [str(root/'build/render_reference_probe'),str(root/'build/graphics_reference.metallib')]
    if kind: cmd += [str(p) for p in shaders[kind]]
    if floating: cmd += ['float']
    env = {'KEPLER_RENDER_OUTPUT_DIR':str(out/(label+'-pixels'))}
    if vertex:
        env.update({'KEPLER_VERTEX_CODE':str(shaders[vertex][0]),'KEPLER_VERTEX_INFO':str(shaders[vertex][1])})
    result = json.loads(run(cmd,label,environment=env))
    assert result['device']=='NVIDIA GeForce GTX 880M' and result['mismatched_channels']==0
    for test in result['tests']:
        assert test['command_status']==4 and test['mismatched_channels']==0
        if kind:
            evidence = test['import']; assert evidence['contract_verified']
            replaced = [e for e in evidence['events'] if e.get('code_replaced')]
            assert len(replaced)==(2 if vertex else 1)
            assert all(e['imported_code_identical'] and e['original_graphics_header_preserved'] for e in replaced)
    path = out/(label+'.json'); path.write_text(json.dumps(result,indent=2)+'\n')
    codes = [shaders[kind][0]] if kind else []
    if vertex: codes.append(shaders[vertex][0])
    cases.append({'label':label,'result':str(path.relative_to(root)),
                  'codes':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in codes]})

for floating in (False, True):
    suffix = 'float' if floating else 'unorm'
    render('native-'+suffix, floating=floating)
    for kind in shaders: render(kind+'-'+suffix, kind, floating=floating)
    for vertex in ('vertex','vertex_half'):
        for fragment in ('constant','read','nearest','linear'):
            render('both-'+vertex+'-'+fragment+'-'+suffix,fragment,vertex,floating)

# Re-linking against the patched compiler must retain the earlier compute results.
smokes = [('fp64',1041,'kepler_carrier'),('atomic32',1025,'kepler_carrier'),
          ('shuffle',1024,'kepler_carrier'),('shared_reduce',64,'kepler_shared_carrier'),
          ('tiled_matmul',4096,'kepler_tiled_carrier')]
for kind,count,carrier in smokes:
    code = out/('compute-'+kind+'.sass'); infoPath = out/('compute-'+kind+'-info.json')
    cmd = [str(root/'build/kepler_compute_suite'),kind,str(code),str(out/('compute-'+kind+'.asm'))]
    if kind=='tiled_matmul': cmd.append('64')
    info = json.loads(run(cmd,'compute-'+kind+'-compile')); infoPath.write_text(json.dumps(info,indent=2)+'\n')
    result = json.loads(run([str(root/'build/compute_suite_probe'),str(root/'build'/f'{carrier}.metallib'),
                           str(code),str(infoPath),str(count),'nocopy','resident'],'compute-'+kind,
                           environment={'VECLIB_MAXIMUM_THREADS':'4'}))
    assert result['device']=='NVIDIA GeForce GTX 880M'
    assert result['mismatches']==0 and result['changed_guards']==0 and result['blas_reference_mismatches']==0
    assert result['import']['contract_verified']
    assert all(e['imported_code_identical'] for e in result['import']['events'])
    path = out/('compute-'+kind+'.json');path.write_text(json.dumps(result,indent=2)+'\n')
    cases.append({'label':'compute-'+kind,'result':str(path.relative_to(root)),
                  'codes':[{'path':str(code.relative_to(root)),'sha256':sha(code)}]})

after = sha(driver); assert before==after
artifacts = [root/'src/KeplerProgramImport.mm',root/'src/KeplerProgramImport.h',
             root/'src/graphics_reference.metal',root/'tools/render_reference_probe.mm',
             root/'tools/graphics_fragment_compile.c',Path(__file__).resolve(),
             root/'src/mesa-26.2.4-macos-texture-import.patch',root/'build/libKeplerProgramImport.dylib',
             root/'build/graphics_fragment_compile',root/'build/render_reference_probe']
manifest = {'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'mesa_version':'26.2.4','mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2',
            'envytools_commit':'f102b82381f3f11cee113d16374c87091db039d9',
            'driver_before_sha256':before,'driver_after_sha256':after,'driver_unchanged':True,
            'cases':cases,'artifacts':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in artifacts],
            'scope':'fixture-qualified local NAK graphics import and compute regression; no graphics performance benchmark or Metal family qualification'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Qualified',len(cases),'cases. Manifest:',out/'manifest.json')
