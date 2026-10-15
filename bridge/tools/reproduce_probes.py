#!/usr/bin/env python3
"""Repeat the bounded local probes. Never install or change system components."""
from pathlib import Path
import os
import subprocess
import json

root = Path(__file__).resolve().parents[1]
(root/'build').mkdir(exist_ok=True)
(root/'logs').mkdir(exist_ok=True)
(root/'results').mkdir(exist_ok=True)
commands = []
def run(command, label, output=None, env=None):
    with (root/('logs/reproduce-'+label+'.log')).open('w') as log:
        if output:
            with output.open('w') as out:
                result = subprocess.run(command, stdout=out, stderr=log, env=env)
        else:
            result = subprocess.run(command, stdout=log, stderr=log, env=env)
    commands.append({'stage':label,'command':command,'exit_code':result.returncode})
    (root/'results/reproduce-probes.json').write_text(json.dumps(commands,indent=2)+'\n')
    print(label, result.returncode, flush=True)
    if result.returncode:
        print((root/('logs/reproduce-'+label+'.log')).read_text()[-3000:])
        raise SystemExit(result.returncode)

run(['clang','-dynamiclib','-Wall','-Wextra','-Werror',str(root/'src/trace_iokit.c'),
     '-framework','IOKit','-framework','CoreFoundation','-o',str(root/'build/libTraceIOKit.dylib')], 'tracer-build')
run(['clang++','-std=c++17','-fobjc-arc',str(root/'src/metal_submission_probe.mm'),
     '-framework','Metal','-framework','Foundation','-o',str(root/'build/metal_submission_probe')], 'metal-probe-build')
env = os.environ.copy()
env['DYLD_INSERT_LIBRARIES'] = str(root/'build/libTraceIOKit.dylib')
env['KEPLER_TRACE_FILE'] = str(root/'results/iokit-trace.jsonl')
run([str(root/'build/metal_submission_probe')], 'metal-probe', root/'results/submission-probe.json', env)
run(['clang++','-std=c++17','-dynamiclib','-Wall','-Wextra','-Werror',
     str(root/'src/IOKitKeplerBridge.cpp'),'-framework','IOKit','-framework','CoreFoundation',
     '-install_name','@rpath/libIOKitKeplerBridge.dylib','-o',str(root/'build/libIOKitKeplerBridge.dylib')], 'native-bridge-build')
run(['clang++','-std=c++17',str(root/'tools/native_transport_probe.cpp'),'-I'+str(root/'src'),
     '-L'+str(root/'build'),'-lIOKitKeplerBridge','-Wl,-rpath,'+str(root/'build'),
     '-o',str(root/'build/native_transport_probe')], 'native-probe-build')
run([str(root/'build/native_transport_probe')], 'native-probe', root/'results/native-transport.json')
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src/add_buffers.metal'),
     '-o',str(root/'build/add_buffers.air')], 'air-build')
run(['xcrun','-sdk','macosx','metallib',str(root/'build/add_buffers.air'),
     '-o',str(root/'build/add_buffers.metallib')], 'metallib-build')
upstream = root/'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/drivers/NVMTLDriver/air'
run(['clang','-std=c11','-O1','-I'+str(upstream),str(root/'tools/air_parse_probe.c')]+
    [str(upstream/name) for name in ('bitstream.c','airir.c','metallib.c')]+
    ['-o',str(root/'build/air_parse_probe')], 'air-reader-build')
for extension in ('air','metallib'):
    run([str(root/'build/air_parse_probe'),str(root/('build/add_buffers.'+extension))],
        'air-reader-'+extension,root/('results/air-reader-'+extension+'.json'))
run(['clang++','-std=c++17','-fobjc-arc',str(root/'tools/add_buffers_reference.mm'),
     '-framework','Metal','-framework','Foundation','-o',str(root/'build/add_buffers_reference')],
    'addition-reference-build')
run([str(root/'build/add_buffers_reference'),str(root/'build/add_buffers.metallib')],
    'addition-reference',root/'results/add-reference.json')
run(['python3',str(root/'tools/analyze_trace.py')], 'trace-analysis')
