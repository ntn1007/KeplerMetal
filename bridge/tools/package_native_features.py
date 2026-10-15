#!/usr/bin/env python3
from pathlib import Path
import datetime,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];files=[]
names=['native-features-initial','native-features-arguments-final','native-features-arguments-expanded','native-features-simd-final','native-features-cas-final','native-features-cas-capture-final','native-features-sources','native-features-report']
for name in names:files.extend(p for p in (ROOT/'results'/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['packet-files.json','delivery.json'])
for name in ['native_features_probe.mm','reproduce_native_features.py','verify_native_features.py','summarize_native_features.py','capture_native_cas.py','run_signed_probe.py','package_native_features.py']:files.append(ROOT/'tools'/name)
files.append(ROOT/'src/KeplerSIMD.metalh');rows=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(set(files))]
manifest={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_root':str(ROOT),'files':rows,'scope':'Raw captures, known failures, own-process probes and application-local SIMD helper. Numerical/hash verification is not a remote hardware attestation.'};mp=ROOT/'results/native-features-report/packet-files.json';mp.write_text(json.dumps(manifest,indent=2)+'\n');files.append(mp)
archive=ROOT/'KEPLERMETAL_FONCTIONS_NATIVES_2026-10-13.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(files)):z.write(p,str(p.relative_to(ROOT)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for row in rows:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
d={'path':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(set(files)),'CRC_and_sha256_passed':True};(ROOT/'results/native-features-report/delivery.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2))
