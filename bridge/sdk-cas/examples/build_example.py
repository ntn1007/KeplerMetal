#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess
SDK=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
argv=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(SDK/'include'),str(SDK/'examples/client.mm'),'-L',str(SDK/'lib'),'-lKeplerNativeCAS','-framework','Metal','-framework','Foundation','-o',str(out/'cas_example')]
r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr
(out/'inputs.json').write_text(json.dumps({'module_static_library_SHA256':sha(SDK/'lib/libKeplerNativeCAS.a'),'public_header_SHA256':sha(SDK/'include/KeplerNativeCAS.h'),'client_source_SHA256':sha(SDK/'examples/client.mm'),'executable_SHA256':sha(out/'cas_example'),'core_source_compilations':0,'assets':{x.name:sha(x) for x in (SDK/'assets').iterdir() if x.is_file()}},indent=2)+'\n');print('Client built against delivered static module; core source compilations: 0')
