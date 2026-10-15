#!/usr/bin/env python3
"""Freeze and recheck exact artifact bytes; do not execute extracted binaries."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'
PROGRESS=RESULTS/'resident-dynamic-progress-20261014/final-qualification-03'
ARCHIVE=ROOT/'KEPLERMETAL_ICB_DYNAMIQUE_2026-10-14.zip'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert not ARCHIVE.exists()
    receipt=json.loads((PROGRESS/'qualification-receipt.json').read_text());assert receipt['status']=='PASS'
    selected=set()
    def add(p):
        p=Path(p);p.relative_to(ROOT)
        if p.is_dir():
            for f in p.rglob('*'):
                if f.is_file()and not f.is_symlink()and f.suffix not in ['.o','.pyc']and'__pycache__'not in f.parts:selected.add(f)
        elif p.is_file()and not p.is_symlink():selected.add(p)
        else:raise FileNotFoundError(p)
    for p in RESULTS.glob('resident-dynamic-*'):add(p)
    comparisons=json.loads((PROGRESS/'nonregression-raw-comparison.json').read_text())
    for row in comparisons['files']:add(ROOT/row['previous'])
    # This old probe is the source-identical reference for both manifest modes.
    for suffix in ['prepared','gpu-qualified']:
        add(RESULTS/('cpu-icb-grid3d-dynamic-regression-'+suffix)/'cpu_icb_manifest_probe.mm')
    for n in ['KeplerCPUICB.h','KeplerCPUICB.mm','KeplerNativeCommands.h','KeplerNativeCommands.mm','cpu_icb_manifest.metal','cpu_icb_dynamic_resident_manifest.json']:add(ROOT/'src'/n)
    for n in ['build_combined_keplermetal_sdk.py','run_registered_resident_copy.py','run_dynamic_resident_copy.py',
              'verify_dynamic_resident_copy.py','verify_dynamic_resident_bounds.py','run_m1_dynamic_copy_reference.py',
              'collect_m1_gpu_copy_reference.py','lab_gpu_reservation.py','build_resident_dynamic_clients.py',
              'run_sdk_legacy_icb_probe.py','verify_sdk_legacy_icb_probe.py','run_resident_dynamic_nonregression.py',
              'verify_cpu_icb_manifest.py','verify_cpu_icb_grid3d.py','decode_native_commands.py',
              'finalize_resident_dynamic_qualification.py','package_resident_dynamic_evidence.py']:add(ROOT/'tools'/n)
    add(ROOT/'ICB_MEMOIRE_DYNAMIQUE_M1_GTX_2026-10-14.txt')
    add(ROOT/'results/hardware-coverage.json')
    add(ROOT/'sdk-combined/README.md')
    entries=[{'path':'bridge/'+str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(selected)]
    manifest={'files':entries,'Git':receipt['Git'],'job_ids':[],'objective_complete':False,'system_modified':False,
              'performance_benchmark':False,'scope':'L2 dynamic shared argument0 in registered resident compute copies'}
    with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False)as z:
        for p in sorted(selected):z.write(p,'bridge/'+str(p.relative_to(ROOT)))
        z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    out=RESULTS/'resident-dynamic-packet-check-20261014';out.mkdir(exist_ok=False)
    with zipfile.ZipFile(ARCHIVE)as z:
        assert len(z.namelist())==len(entries)+1 and len(set(z.namelist()))==len(z.namelist())
        for n in z.namelist():assert not n.startswith('/')and'..'not in Path(n).parts
        for e in entries:
            raw=z.read(e['path']);assert len(raw)==e['bytes']and hashlib.sha256(raw).hexdigest()==e['SHA256']
        z.extractall(out)
    frozen=out/'bridge';sdk=frozen/'results/resident-dynamic-sdk-build-20261014-04/KeplerMetalSDK'
    sdk_manifest=json.loads((sdk/'FILE_MANIFEST.json').read_text())
    for e in sdk_manifest['files']:assert sha(sdk/e['path'])==e['SHA256']and(sdk/e['path']).stat().st_size==e['bytes']
    sys.path[:0]=[str(frozen/'tools'),str(sdk/'examples')]
    loaded={}
    def oracle(name,base):
        if(name,str(base))not in loaded:
            spec=importlib.util.spec_from_file_location(name,base/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);loaded[name,str(base)]=m.verify
        return loaded[name,str(base)]
    names={'async':'verify_cpu_icb_copy_async','mixed':'verify_cpu_icb_copy_mixed','graph':'verify_cpu_icb_copy_graph',
           'baseline':'verify_cpu_icb_gpu_copy','refusal':'verify_cpu_icb_copy_refusals','registered':'verify_registered_resident_copy',
           'registered_bounds':'verify_registered_resident_bounds','reverse':'verify_fp64_reverse_client','arithmetic':'verify_fp64_client',
           'cas':'verify_example','literal':'verify_literal_client'}
    source_checks=json.loads((PROGRESS/'independent-rechecks.json').read_text())['checks'];checks=[]
    for c in source_checks:
        p=frozen/c['path'];legacy=False
        if p.name.startswith('resident-dynamic-bounds-'):name,base='verify_dynamic_resident_bounds',sdk/'examples'
        elif p.name.startswith('resident-dynamic-regression-'):
            variant=p.name[len('resident-dynamic-regression-'):].split('-')[0]
            if variant in ['manifest','grid3d']:name,base,legacy='verify_cpu_icb_'+variant,frozen/'tools',True
            else:name,base=names[variant],sdk/'examples'
        else:name,base='verify_dynamic_resident_copy',sdk/'examples'
        v=oracle(name,base)(p,portable=True)
        assert v['status']==c['verification']['status']and v.get('raw_SHA256')==c['verification'].get('raw_SHA256')
        if legacy:
            m=json.loads((p/'execution/manifest.json').read_text())
            assert sha(p/('cpu_icb_'+variant+'_probe'))==m['original_binary_sha256']
            assert sha(p/'execution/application')==m['signed_binary_sha256']
        checks.append({'path':c['path'],'status':v['status']})
    assert len(checks)==106
    for row in comparisons['files']:
        a,b=frozen/row['current'],frozen/row['previous'];assert a.read_bytes()==b.read_bytes()and sha(a)==row['SHA256']
    assert len(comparisons['files'])==2296
    verification={'status':'PASS','manifest_files_verified':len(entries),'SDK_files_including_manifest':len(sdk_manifest['files'])+1,
                  'portable_oracles':checks,'portable_oracle_count':106,'nonregression_raw_files_identical':2296,
                  'GPU_runs_started':0,'extracted_binaries_executed':False,'archive_SHA256':sha(ARCHIVE)}
    (out/'portable-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    delivery={'status':'PASS','path':str(ARCHIVE),'SHA256':sha(ARCHIVE),'bytes':ARCHIVE.stat().st_size,
              'files_including_manifest':len(entries)+1,'portable_oracles':106,'system_modified':False,'objective_complete':False}
    with(PROGRESS/'packet-delivery.json').open('x')as f:json.dump(delivery,f,indent=2);f.write('\n')
    print(json.dumps(delivery,indent=2))


if __name__=='__main__':main()
