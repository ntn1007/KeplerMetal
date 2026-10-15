#!/usr/bin/env python3
"""Record exact tool versions and hashes without altering machine settings."""
from pathlib import Path
import subprocess
import json
import hashlib
import datetime
import argparse

root = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--hash-only',action='store_true',help='Refresh artifact hashes without launching native tool version probes')
args=parser.parse_args()
commands = {
    'macos':['sw_vers'], 'cpu':['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'],
    'machine':['/usr/sbin/sysctl','-n','hw.model'], 'clang':['clang','--version'],
    'xcode':['xcodebuild','-version'], 'metal':['xcrun','metal','--version'],
    'sdk':['xcrun','--show-sdk-version'],
    'rustc':[str(root/'build/rust-prefix/bin/rustc'),'--version'],
    'cargo':[str(root/'build/rust-prefix/bin/cargo'),'--version'],
    'bindgen':[str(root/'build/rust-prefix/bin/bindgen'),'--version'],
    'cbindgen':[str(root/'build/rust-prefix/bin/cbindgen'),'--version'],
    'python':[str(root/'build/python312-env/bin/python3'),'--version'],
    'meson':[str(root/'build/python312-env/bin/meson'),'--version'],
    'ninja':[str(root/'build/python312-env/bin/ninja'),'--version'],
    'cmake':['cmake','--version'], 'bison':['bison','--version'],
    'bridge_links':['otool','-L',str(root/'build/libIOKitKeplerBridge.dylib')],
}
previousPath=root/'results/provenance.json'
previous=json.loads(previousPath.read_text()) if previousPath.exists() else {}
tools = previous.get('tools',{}) if args.hash_only else {}
for name, command in ([] if args.hash_only else commands.items()):
    result = subprocess.run(command,capture_output=True,text=True)
    tools[name] = {'command':command,'exit_code':result.returncode,
                   'output':(result.stdout+result.stderr).strip()}
files = list((root/'src').glob('*')) + list((root/'tools').glob('*.*'))
files += [root/'tools/envydis-build/CMakeLists.txt']
files += [root/'build'/name for name in ('libIOKitKeplerBridge.dylib','libTraceIOKit.dylib',
          'metal_submission_probe','native_transport_probe','air_parse_probe','kepler_air_compile','add_buffers_reference',
          'add_buffers.air','add_buffers.metallib','add_buffers-air.sass','add_buffers-metallib.sass')]
files += [root/'build/envydis-only/envydis/envydis']
files += list((root/'build').glob('*.sass')) + list((root/'build').glob('*.air')) + list((root/'build').glob('*.metallib'))
files += [root/'build'/name for name in ('compiler_output_trace','driver_inventory','kepler_driver_marker','nak_macos_probe')]
files += [root/'build'/name for name in ('libKeplerProgramImport.dylib','nak_memory_bench','compute_suite_probe','kepler_compute_suite')]
files += [root/'build'/name for name in ('kepler_clock_compile','clock_probe','graphics_fragment_compile','render_reference_probe','render_state_probe','program_container_test')]
files += list((root/'build').glob('*.sph'))
files += [root/'build'/name for name in ('vertex_io_compile','vertex_io_probe')]
files += [root/'build'/name for name in ('resource_compile','resource_probe')]
files += [root/'build'/name for name in ('tessellation_compile','tessellation_probe')]
files += [root/'build'/name for name in ('tessellation_capture_compile','tessellation_capture_probe')]
files += [root/'build'/name for name in ('video_engine_probe','video_loader_probe')]
files += [root/'build/vda_engine_probe']
files = list(dict.fromkeys(files))
hashes = [{'path':str(file.relative_to(root)),'bytes':file.stat().st_size,
           'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
          for file in files if file.is_file()]
(root/'results/provenance.json').write_text(json.dumps({
    'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'tools':tools,'files':hashes,
    'tool_versions_refreshed':not args.hash_only,
    'tool_versions_observed_at':previous.get('tool_versions_observed_at',previous.get('collected_at')) if args.hash_only else datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope':'isolated user-space tools; no system installation; no new driver qualification',
},indent=2)+'\n')
if args.hash_only:print('Retained',len(tools),'previous tool observations; refreshed',len(hashes),'file hashes only.')
else:print('Recorded',len(tools),'tool/environment checks and',len(hashes),'file hashes.')

