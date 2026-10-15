#!/usr/bin/env python3
"""Package reports, provenance and static comparisons, excluding large binaries."""
from pathlib import Path
import datetime,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
files=[]
for dirname in ['reports','inventory','sources','comparison','tools']:
    files.extend(p for p in (ROOT/dirname).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files += [ROOT/'COMMANDES.txt',ROOT/'verification.json',ROOT/'archives/manifest.json']
files += list((ROOT/'archives').glob('*.sha256sum'))
files += list((ROOT/'extracted').glob('*-manifest.json'))
rows=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(set(files))]
manifest={'packaged_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':rows,'excluded':'The five .run archives, extracted driver files and executable probes remain in the workspace. Their hashes/download commands are included. Prior raw GPU fixtures remain in ../bridge; summaries explicitly marked historical.','purpose':'Two independent research reports, inventory and reproducible static investigation; no installed driver change.'}
mp=ROOT/'delivery-files.json';mp.write_text(json.dumps(manifest,indent=2)+'\n');files.append(mp)
archive=ROOT/'KEPLERMETAL_INVENTAIRE_2026-10-13.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(files)):z.write(p,str(p.relative_to(ROOT)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for row in rows:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
delivery={'path':str(archive.resolve()),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(set(files)),'zip_crc_and_sha_verified':True}
(ROOT/'delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
