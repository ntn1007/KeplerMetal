#!/usr/bin/env python3
"""Check the immutable archive, then rerun its CPU oracles without host binaries."""
from pathlib import Path
import argparse,hashlib,json,subprocess,zipfile
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();archive=a.archive.resolve();out=a.out.resolve();assert not out.exists();out.mkdir();dest=out/'extracted';dest.mkdir()
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None;m=json.loads(z.read('PACKET_MANIFEST.json'));entries=m['files'];assert len({e['path'] for e in entries})==len(entries) and len(z.namelist())==len(entries)+1
    for e in entries:
        name=e['path'];target=dest/name;target.resolve().relative_to(dest);assert not Path(name).is_absolute();raw=z.read(name);assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
    assert not m['all_hardware_functions_supported'] and not m['ICB_contract_complete'] and not m['system_modified']
    for e in entries:
        target=dest/e['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(e['path']))
root=dest/'bridge';cohorts=[('verify_cpu_icb_depth_gpu', 'depth-gpu-combined-icb-prepared'), ('verify_cpu_icb_depth_gpu', 'depth-gpu-combined-icb-gpu-qualified'), ('verify_cpu_icb_depth_gpu', 'depth-gpu-combined-native-prepared'), ('verify_cpu_icb_depth_gpu', 'depth-gpu-combined-native-gpu-qualified')];checks=[]
for tool,cohort in cohorts:
    # Invoke the pure verifier so old CLI helpers do not rewrite archive data.
    code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);m=__import__(sys.argv[2]);r=m.verify(Path(sys.argv[3]),False,True);print(json.dumps({k:v for k,v in r.items() if k not in ("raw_SHA256","raw_sha256","source_sha256")}))'
    argv=['python3','-c',code,str(root/'tools'),tool,str(root/'results'/cohort)];r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/(cohort+'.stdout')).write_text(r.stdout);(out/(cohort+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr;d=json.loads(r.stdout);assert d['status']=='PASS';checks.append({'cohort':cohort,'status':'PASS_PORTABLE_RAW','fresh_GPU_execution':False,'host_executables_re_attested':False})
argv=['python3',str(root/'tools/verify_depth_gpu_equivalence.py'),str(root/'results/depth-gpu-combined-icb-gpu-qualified'),str(root/'results/depth-gpu-combined-native-gpu-qualified')];r=subprocess.run(argv,capture_output=True,text=True,timeout=45);assert r.returncode==0,r.stderr;d=json.loads(r.stdout);assert d['status']=='PASS';(out/'equivalence.stdout').write_text(r.stdout);checks.append({'cohort':'native-ICB-equivalence-and-physical-records','status':'PASS_PORTABLE_EQUIVALENCE','fresh_GPU_execution':False,'host_executables_re_attested':False})
result={'archive_SHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_files_verified':len(entries),'CRC_and_all_SHA256_verified':True,'portable_oracles':checks,'fresh_GPU_execution':False,'host_binaries_re_attested':False,'all_hardware_supported':False}
(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
