#!/usr/bin/env python3
"""Rebuild and verify this SM30/macOS experiment in the isolated workspace.

Requires the pinned compiler-only Mesa build produced by build_offline_compiler.py.
Does not install a driver, edit a system file, or change OCLP.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shlex
import struct
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--out', type=Path, default=root/'results/nak-reproduction')
args = parser.parse_args()
out = args.out.resolve()
out.relative_to(root/'results')
out.mkdir(parents=True, exist_ok=True)
stages = []
driver = Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver')
expected_driver = json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
driver_before = hashlib.sha256(driver.read_bytes()).hexdigest()
if driver_before != expected_driver:
    raise SystemExit('Installed driver changed: revalidate the observed ABI before executing this experiment.')

def run(command, name, cwd=root, expected=0):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        stages.append({'name':name,'command':command,'cwd':str(cwd),'timeout_seconds':60})
        (out/'commands.json').write_text(json.dumps(stages,indent=2)+'\n')
        raise SystemExit(f'{name}: timeout; inspect the process before retrying')
    (out/(name+'.stdout')).write_text(result.stdout)
    (out/(name+'.stderr')).write_text(result.stderr)
    stages.append({'name':name,'command':command,'cwd':str(cwd),
                   'exit_code':result.returncode,'expected_exit_code':expected})
    (out/'commands.json').write_text(json.dumps(stages,indent=2)+'\n')
    print(name,result.returncode,flush=True)
    if result.returncode != expected:
        print(result.stderr[-3000:])
        raise SystemExit(f'{name}: unexpected exit code')
    return result.stdout

for stem in ('add_buffers','kepler_carrier','kepler_branch_carrier'):
    run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',
         str(root/'src'/f'{stem}.metal'),'-o',str(root/'build'/f'{stem}.air')],stem+'-air')
    run(['xcrun','-sdk','macosx','metallib',str(root/'build'/f'{stem}.air'),
         '-o',str(root/'build'/f'{stem}.metallib')],stem+'-metallib')

run([sys.executable,str(root/'tools/build_air_compiler.py'),'--constant-buffer-index','2'],
    'air-to-sm30-build')

build = root/'build/mesa'
entries = json.loads((build/'compile_commands.json').read_text())
entry = next(e for e in entries if e['file'].endswith('/nak_nir.c'))
flags = [a for a in shlex.split(entry['command'])[1:]
         if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
obj = root/'build/kepler_driver_marker.o'
run(['clang','-O1']+flags+['-c',str(root/'tools/kepler_driver_marker.c'),'-o',str(obj)],
    'marker-compile',build)
archives = ['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a',
            'src/compiler/nir/libnir.a','src/compiler/libcompiler.a',
            'src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a',
            'src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a',
            'src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a',
            'src/compiler/rust/libcompiler_bindings.a']
run(['clang','-o',str(root/'build/kepler_driver_marker'),str(obj)]+archives+
    ['-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],
    'marker-link',build)
for stem,option in [('driver-marker',None),('driver-straight-marker','straight'),('nir-straight-add','add')]:
    cmd=[str(root/'build/kepler_driver_marker'),str(root/'build'/f'{stem}.sass'),str(out/f'{stem}.asm')]
    if option:cmd.append(option)
    run(cmd,stem+'-compile')
for tool in ('compiler_output_trace','nak_macos_probe'):
    run(['clang++','-g','-O3','-std=c++17','-fno-objc-arc',str(root/'tools'/f'{tool}.mm'),
         '-framework','Metal','-framework','Foundation','-o',str(root/'build'/tool)],tool+'-build')

# Observe an unmodified branching shader to verify the two launch values.
capture=out/'branch-carrier-capture'
run([str(root/'build/compiler_output_trace'),str(root/'build/kepler_branch_carrier.metallib'),
     str(capture)],'branch-carrier-capture')
blob=(capture/'program-0.compiler-output.bin').read_bytes()
offset=8;launch_words=None
while True:
    next_section,kind,size=struct.unpack_from('<QII',blob,offset)
    if kind==0x10004:
        launch_words=list(struct.unpack_from('<'+'I'*(size//4),blob,offset+16))
    if not next_section:break
    offset+=next_section
if launch_words is None or (launch_words[9],launch_words[11]) != (576,576):
    raise SystemExit('The observed branch-launch metadata changed; do not apply guessed values.')

cases=[]
def probe(name,code,mode,count,warmups=None,trials=None,expected=0):
    dest=out/name;dest.mkdir(exist_ok=True)
    command=[str(root/'build/nak_macos_probe'),str(root/'build/kepler_carrier.metallib'),
             str(root/'build'/code),str(dest),mode,str(count)]
    if warmups is not None:command += [str(warmups),str(trials)]
    text=run(command,name,expected=expected)
    result=json.loads(text)
    (dest/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    (dest/'status.json').write_text(json.dumps(stages[-1],indent=2)+'\n')
    if expected==10 and (result.get('mismatches')!=count or result.get('changed_guard_elements')!=0 or result.get('first_value')!=-123456):
        raise SystemExit(f'{name}: the negative control no longer matches the observed missing-output failure')
    if result.get('gpu_dispatch') and expected==0:
        if result.get('mismatches',result.get('mismatches_including_warmups')) != 0:
            raise SystemExit(f'{name}: numerical mismatch')
        if result.get('changed_guard_elements',result.get('changed_guard_elements_including_warmups')) != 0:
            raise SystemExit(f'{name}: guard changed')
    code_path=root/'build'/code
    if result.get('import_contract_verified'):
        # Prove that the container handed to the driver contains exactly this code.
        imported=(dest/'imported.compiler-output.bin').read_bytes();offset=8
        while True:
            following,kind,size=struct.unpack_from('<QII',imported,offset)
            if kind==0x10005:
                if imported[offset+16:offset+16+size] != code_path.read_bytes():
                    raise SystemExit(f'{name}: imported code differs')
                break
            if not following:raise SystemExit(f'{name}: no native code section')
            offset+=following
    cases.append({'name':name,'code':str(code_path.relative_to(root)),
                  'code_sha256':hashlib.sha256(code_path.read_bytes()).hexdigest(),
                  'result':str((dest/'result.json').relative_to(root)),
                  'expected_exit_code':expected,'actual_exit_code':stages[-1]['exit_code']})

probe('native-control','driver-marker.sass','control',1)
probe('nak-marker-missing-launch-fields','driver-marker.sass','marker',1,expected=10)
probe('nak-marker-correct-launch-fields','driver-marker.sass','stack_marker',1)
probe('nak-straight-marker','driver-straight-marker.sass','straight_marker',1)
for count in (1,17,31,32,33,1041,65536,1048576):
    probe(f'air-correct-{count}','add_buffers-air-cb2.sass','stack_execute',count)
for count in (65536,1048576):
    probe(f'air-benchmark-{count}','add_buffers-air-cb2.sass','stack_execute',count,3,9)

driver_after=hashlib.sha256(driver.read_bytes()).hexdigest()
manifest={'driver_before_sha256':driver_before,'driver_after_sha256':driver_after,
          'installed_driver_binary_unchanged':driver_before==driver_after,
          'observed_branch_launch_words_9_11':[launch_words[9],launch_words[11]],
          'cases':cases,'scope':'controlled own-process import through existing driver; no system installation'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if driver_before != driver_after:raise SystemExit('Installed driver changed during the test; inspect externally.')
run([sys.executable,str(root/'tools/make_nak_report.py'),'--input',str(out)],'report')
print('Results:',out)
