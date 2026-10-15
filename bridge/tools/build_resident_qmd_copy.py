#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--public-client',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();(out/'runtime').mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
names=['KeplerCPUICB.h','KeplerCPUICB.mm','KeplerNativeCommands.h','KeplerNativeCommands.mm','KeplerNativeRenderDraws.h','KeplerNativeRenderDraws.mm']
for n in names:shutil.copyfile(ROOT/'src'/n,out/n)
client='cpu_icb_gpu_copy_client.mm' if a.public_client else 'resident_qmd_copy_probe.mm';source=ROOT/('sdk-combined/examples' if a.public_client else 'tools')/client
shutil.copyfile(source,out/client);names.append(client)
for source in [ROOT/'tools/lab_gpu_reservation.py',ROOT/'sdk-combined/runtime/run_sdk_host.py']:shutil.copyfile(source,out/'runtime'/source.name)
library=ROOT/'results/cpu-icb-profiles-native/cpu_icb_profiles.metallib'
if not library.exists():
 candidates=[p for p in (ROOT/'results').glob('*/cpu_icb_profiles.metallib') if sha(p)=='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd'];assert candidates;library=candidates[0]
assert sha(library)=='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd';shutil.copyfile(library,out/'library.metallib')
argv=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/client),*[str(out/n) for n in names if n.endswith('.mm') and n!=client],'-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(argv,capture_output=True,text=True,timeout=60);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr[-3000:]
(out/'inputs.json').write_text(json.dumps({'source_SHA256':{n:sha(out/n) for n in names},'library_SHA256':sha(out/'library.metallib'),'executable_SHA256':sha(out/'application'),'runtime_SHA256':{n:sha(out/'runtime'/n) for n in ['lab_gpu_reservation.py','run_sdk_host.py']},'GPU_execution':False},indent=2)+'\n');print('Build PASS; no GPU execution')
