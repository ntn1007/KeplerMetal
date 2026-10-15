#!/usr/bin/env python3
"""Compare existing NVIDIA R470 public files; never execute driver code."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'comparison');out.mkdir(exist_ok=False)
bsd=ROOT/'extracted/FreeBSD-470.256.02-public-sources';linux=ROOT/'extracted/470.256.02/kernel';meta=json.loads((bsd/'EXTRACTION.json').read_text());assert sha(ROOT/meta['archive'])==meta['SHA256'];rows=[]
for f in meta['source_files']:
 a=bsd/f['path'];assert sha(a)==f['SHA256']
 for b in linux.rglob(a.name):
  if not b.is_file():continue
  rows.append({'FreeBSD':str(a.relative_to(ROOT)),'Linux':str(b.relative_to(ROOT)),'basename':a.name,'identical':sha(a)==sha(b),'FreeBSD_SHA256':sha(a),'Linux_SHA256':sha(b)})
receipt={'status':'PASS_STATIC_COMPARISON','version':'470.256.02','matched_pairs':len(rows),'byte_identical':sum(r['identical']for r in rows),'pairs':rows,'driver_code_executed':False,'macOS_compatibility_verified':False}
(out/'comparison.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k!='pairs'}))
