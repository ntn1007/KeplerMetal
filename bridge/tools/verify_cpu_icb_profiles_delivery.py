#!/usr/bin/env python3
"""Extract only after all archive SHA checks, then verify portable raw oracles."""
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
root=dest/'bridge';cohorts=[('verify_cpu_icb_profiles.py','cpu-icb-profiles-reflection-access-prepared'),('verify_cpu_icb_profiles.py','cpu-icb-profiles-gpu-qualified'),('verify_cpu_icb_profiles_lifetime.py','cpu-icb-profiles-lifetime-private-buffers-prepared'),('verify_cpu_icb_profiles_lifetime.py','cpu-icb-profiles-lifetime-gpu-qualified'),('verify_cpu_icb.py','cpu-icb-registered-legacy-prepared'),('verify_cpu_icb.py','cpu-icb-registered-legacy-gpu-qualified')];checks=[]
for tool,cohort in cohorts:
 argv=['python3',str(root/'tools'/tool),'--input',str(root/'results'/cohort),'--portable'];r=subprocess.run(argv,capture_output=True,text=True,timeout=20);(out/(cohort+'.stdout')).write_text(r.stdout);(out/(cohort+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr;d=json.loads(r.stdout);assert d['status']=='PASS' and d['portable_raw_verification_only'] and not d['host_executable_SHA256_rechecked'];checks.append({'cohort':cohort,'status':'PASS_PORTABLE_RAW','fresh_GPU_execution':False})
result={'archive_SHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_files_verified':len(entries),'CRC_and_all_SHA256_verified':True,'portable_oracles':checks,'fresh_GPU_execution':False,'host_binaries_re_attested':False,'all_hardware_supported':False}
(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
