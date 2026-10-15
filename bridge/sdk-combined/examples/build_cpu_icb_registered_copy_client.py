#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
SDK=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);(out/'runtime').mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
argv=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(SDK/'include'),str(SDK/'examples/cpu_icb_registered_copy_client.mm'),'-L',str(SDK/'lib'),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(out/'application')]
r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr[-2000:]
for source in [SDK/'examples/cpu_icb_registered_copy_client.mm',SDK/'include/KeplerCPUICB.h']:shutil.copyfile(source,out/source.name)
(out/'assets').mkdir()
for n in ['literal_lut.metallib','cpu_icb_literal_lut_manifest.json','cpu_icb_literal_lut_values.json']:shutil.copyfile(SDK/'assets'/n,out/'assets'/n)
for source in [SDK/'runtime/lab_gpu_reservation.py',SDK/'runtime/run_sdk_host.py']:shutil.copyfile(source,out/'runtime'/source.name)
(out/'inputs.json').write_text(json.dumps({'source_hashes':{n:sha(out/n) for n in ['cpu_icb_registered_copy_client.mm','KeplerCPUICB.h']},'assets_SHA256':{p.name:sha(p) for p in (out/'assets').iterdir()},'executable_SHA256':sha(out/'application'),'runtime_SHA256':{n:sha(out/'runtime'/n) for n in ['lab_gpu_reservation.py','run_sdk_host.py']},'static_library_SHA256':sha(SDK/'lib/libKeplerMetal.a'),'core_source_compilations':0,'GPU_execution':False},indent=2)+'\n');print(json.dumps({'build':'PASS','core_source_compilations':0}))
