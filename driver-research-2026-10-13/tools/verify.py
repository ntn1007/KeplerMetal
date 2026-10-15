#!/usr/bin/env python3
"""Verify local artifacts and that recorded installed components are unchanged."""
from pathlib import Path
import datetime,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
errors=[];files=0;bytes_read=0
for m in (ROOT/'extracted').glob('*-manifest.json'):
    d=json.loads(m.read_text());package=ROOT/d['archive_file']
    if sha(package)!=d['archive_sha256']:errors.append(str(package))
    for e in d['entries']:
        if 'sha256' not in e:continue
        p=ROOT/'extracted'/d['version']/e['path'];files+=1;bytes_read+=e['bytes']
        if not p.is_file() or p.is_symlink() or sha(p)!=e['sha256']:errors.append(str(p))
        if p.exists() and p.stat().st_mode&0o111:errors.append('Unexpected executable mode: '+str(p))
components=json.loads((ROOT/'inventory/components.json').read_text());installed=0
for c in components:
    for key,hashkey in [('info_path','info_sha256'),('executable','sha256')]:
        if key not in c:continue
        p=Path(c[key]);installed+=1
        if sha(p)!=c[hashkey]:errors.append('System component changed: '+str(p))
meta=json.loads((ROOT/'inventory/inventory-manifest.json').read_text())
if sha(Path(meta['root_patch_plist']))!=meta['root_patch_plist_sha256']:errors.append('OCLP root patch plist changed')
compiler_files=json.loads((ROOT/'inventory/compiler-payload-files.json').read_text())
for c in compiler_files:
    if sha(Path(c['path']))!=c['sha256']:errors.append('Compiler payload changed: '+c['path'])
probe=json.loads((ROOT/'inventory/capabilities.json').read_text())['metal'][0]
assert probe['argumentBuffersSupport']==1 and probe['argumentBuffersTierName']=='tier2'
assert probe['readWriteTextureSupport']==1 and probe['readWriteTextureTierName']=='tier1'
for name,n in [('HISTORIQUE_KEPLER',24),('MATRICE_METAL',30)]:
    assert len(json.loads((ROOT/'reports'/(name+'.json')).read_text()))==n
summary={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'extracted_regular_files_verified':files,'extracted_bytes_verified':bytes_read,'archives_verified':len(list((ROOT/'extracted').glob('*-manifest.json'))),'installed_component_file_hashes_unchanged':installed,'compiler_payload_file_hashes_unchanged':len(compiler_files),'root_patch_plist_unchanged':not any('OCLP' in s for s in errors),'errors':errors,'scope':'File integrity and observed system files only, not a new GPU execution/conformance benchmark'}
(ROOT/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));sys.exit(bool(errors))
