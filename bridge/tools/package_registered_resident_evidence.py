#!/usr/bin/env python3
"""Freeze and independently recheck this milestone without executing binaries."""
from pathlib import Path
import hashlib
import importlib.util
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'
PROGRESS = RESULTS / 'registered-resident-progress-20261014/final-qualification'
ARCHIVE = ROOT / 'KEPLERMETAL_ICB_REGISTRATION_NATIVE_2026-10-14.zip'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert not ARCHIVE.exists()
    receipt = json.loads((PROGRESS / 'qualification-receipt.json').read_text())
    assert receipt['status'] == 'PASS'
    selected = set()

    def add(p):
        p = Path(p)
        p.relative_to(ROOT)
        if p.is_dir():
            for f in p.rglob('*'):
                if f.is_file() and not f.is_symlink() and f.suffix not in ['.o', '.pyc'] and '__pycache__' not in f.parts:
                    selected.add(f)
        elif p.is_file() and not p.is_symlink():
            selected.add(p)
        else:
            raise FileNotFoundError(p)

    for p in RESULTS.glob('registered-resident-*'):
        add(p)
    comparisons = json.loads((PROGRESS / 'nonregression-raw-comparison.json').read_text())
    for row in comparisons['files']:
        add(ROOT / row['previous'])
    for n in ['KeplerCPUICB.h', 'KeplerCPUICB.mm', 'KeplerNativeCommands.h', 'KeplerNativeCommands.mm']:
        add(ROOT / 'src' / n)
    for n in ['build_combined_keplermetal_sdk.py', 'run_registered_resident_copy.py',
              'verify_registered_resident_copy.py', 'verify_registered_resident_bounds.py',
              'run_m1_registered_copy_reference.py', 'collect_m1_gpu_copy_reference.py',
              'lab_gpu_reservation.py', 'finalize_registered_resident_qualification.py',
              'package_registered_resident_evidence.py']:
        add(ROOT / 'tools' / n)
    add(ROOT / 'ICB_REGISTRATION_NATIVE_CB0_M1_GTX_2026-10-14.txt')
    add(ROOT / 'results/hardware-coverage.json')
    entries = [{'path': 'bridge/' + str(p.relative_to(ROOT)), 'bytes': p.stat().st_size,
                'SHA256': sha(p)} for p in sorted(selected)]
    manifest = {'files': entries, 'Git': receipt['Git'], 'job_ids': [],
                'objective_complete': False, 'system_modified': False,
                'performance_benchmark': False, 'scope': 'Bounded L2 registered native resident ICB'}
    with zipfile.ZipFile(ARCHIVE, 'x', zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as z:
        for p in sorted(selected):
            z.write(p, 'bridge/' + str(p.relative_to(ROOT)))
        z.writestr('PACKET_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    out = RESULTS / 'registered-resident-packet-check-20261014'
    out.mkdir(exist_ok=False)
    with zipfile.ZipFile(ARCHIVE) as z:
        assert len(z.namelist()) == len(entries) + 1 and len(set(z.namelist())) == len(z.namelist())
        for n in z.namelist():
            assert not n.startswith('/') and '..' not in Path(n).parts
        for e in entries:
            raw = z.read(e['path'])
            assert len(raw) == e['bytes'] and hashlib.sha256(raw).hexdigest() == e['SHA256']
        z.extractall(out)

    frozen = out / 'bridge'
    sdk = frozen / 'results/registered-resident-sdk-build-20261014-02/KeplerMetalSDK'
    sd = json.loads((sdk / 'FILE_MANIFEST.json').read_text())
    for e in sd['files']:
        assert sha(sdk / e['path']) == e['SHA256'] and (sdk / e['path']).stat().st_size == e['bytes']
    modules = {}

    def oracle(name, base):
        key = (name, str(base))
        if key not in modules:
            spec = importlib.util.spec_from_file_location(name, base / (name + '.py'))
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            modules[key] = m.verify
        return modules[key]

    checks = json.loads((PROGRESS / 'independent-rechecks.json').read_text())['checks']
    passed = []
    variant_verifiers = {'async': 'verify_cpu_icb_copy_async', 'mixed': 'verify_cpu_icb_copy_mixed',
                         'graph': 'verify_cpu_icb_copy_graph', 'baseline': 'verify_cpu_icb_gpu_copy',
                         'refusal': 'verify_cpu_icb_copy_refusals', 'reverse': 'verify_fp64_reverse_client',
                         'arithmetic': 'verify_fp64_client', 'cas': 'verify_example', 'literal': 'verify_literal_client'}
    for c in checks:
        p = frozen / c['path']
        if 'registered-resident-bounds-' in p.name:
            name, base = 'verify_registered_resident_bounds', frozen / 'tools'
        elif 'registered-resident-regression-' in p.name:
            variant = p.name[len('registered-resident-regression-'):].split('-')[0]
            name, base = variant_verifiers[variant], sdk / 'examples'
        else:
            name, base = 'verify_registered_resident_copy', frozen / 'tools'
        v = oracle(name, base)(p, portable=True)
        assert v['status'] == c['verification']['status']
        assert v.get('raw_SHA256') == c['verification'].get('raw_SHA256')
        passed.append({'path': c['path'], 'status': v['status']})
    assert len(passed) == 91
    for row in comparisons['files']:
        a, b = frozen / row['current'], frozen / row['previous']
        assert a.read_bytes() == b.read_bytes() and sha(a) == row['SHA256']
    assert len(comparisons['files']) == 1764
    verification = {'status': 'PASS', 'manifest_files_verified': len(entries),
                    'SDK_files_verified_including_manifest': len(sd['files']) + 1,
                    'portable_oracles': passed, 'portable_oracle_count': len(passed),
                    'nonregression_raw_files_compared': 1764, 'GPU_runs_started': 0,
                    'extracted_binaries_executed': False, 'archive_SHA256': sha(ARCHIVE)}
    (out / 'portable-verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    delivery = {'status': 'PASS', 'path': str(ARCHIVE), 'SHA256': sha(ARCHIVE),
                'bytes': ARCHIVE.stat().st_size, 'files_including_manifest': len(entries) + 1,
                'portable_oracles': 91, 'system_modified': False, 'objective_complete': False}
    with (PROGRESS / 'packet-delivery.json').open('x') as f:
        json.dump(delivery, f, indent=2)
        f.write('\n')
    print(json.dumps(delivery, indent=2))


if __name__ == '__main__':
    main()
