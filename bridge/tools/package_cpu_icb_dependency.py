#!/usr/bin/env python3
"""Freeze dependency qualification evidence and verify seven portable oracles.

This does not execute GPU code. Host executables and credentials are excluded.
"""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
ARCHIVE = ROOT / 'KEPLERMETAL_ICB_DEPENDANCES_CB0_BARRIERES_2026-10-14.zip'
CHECK = ROOT / 'results/icb-dependency-portable-verification'
assert not ARCHIVE.exists() and not CHECK.exists()
files = set()
for folder in sorted((ROOT / 'results').glob('icb-dependency-*')):
    files.update(p for p in folder.rglob('*') if p.is_file())
for name in (
    'ICB_DEPENDANCES_CB0_BARRIERES.txt', 'RAPPORT_PRELIMINAIRE_2026-10-14.txt',
    'results/hardware-coverage.json', 'SDK_COMBINE_APPLICATION_ADAPTEE.txt',
    'results/combined-sdk-progress/qualification-receipt.json',
    'tools/reproduce_cpu_icb_dependency.py', 'tools/cpu_icb_dependency_probe.mm',
    'tools/verify_cpu_icb_dependency.py', 'tools/verify_cpu_icb_native_cas.py',
    'tools/verify_cpu_icb_mixed.py', 'tools/decode_native_commands.py',
    'tools/run_signed_probe.py', 'tools/package_cpu_icb_dependency.py',
    'src/cpu_icb_dependency.metal', 'src/cpu_icb_dependency_manifest.json',
):
    files.add(ROOT / name)
for stem in ('KeplerCPUICB', 'KeplerNativeCommands', 'KeplerNativeRenderDraws',
             'KeplerNativeCAS', 'KeplerProgramImport'):
    files.update((ROOT / 'src' / (stem + ext)) for ext in ('.h', '.mm'))
files.add(ROOT / 'src/KeplerNativeCASAdapter.inc')
cohorts = {
    'dependency': ['icb-dependency-prepared-cb0', 'icb-dependency-gpu-qualified',
                   'icb-dependency-native-reference'],
    'cas': ['icb-dependency-cas-regression-prepared',
            'icb-dependency-cas-regression-gpu-qualified'],
    'mixed': ['icb-dependency-mixed-regression-prepared',
              'icb-dependency-mixed-regression-gpu-qualified'],
}
for group in cohorts.values():
    for name in group:
        inputs = json.loads((ROOT / 'results' / name / 'inputs.json').read_text())
        for filename in inputs['source_hashes']:
            candidates = [ROOT / 'src' / filename, ROOT / 'tools' / filename]
            source = next(p for p in candidates if p.is_file())
            files.add(source)
files.add(ROOT / 'vendor/mesa-26.2.4/src/nouveau/headers/nvidia/classes/cla0c0.h')

magic = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe',
         b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\x7fELF'}
selected, excluded = [], []
for path in sorted(files):
    assert path.is_file() and not path.is_symlink(), str(path)
    relative = str(path.relative_to(LAB))
    assert path.name not in ('coordinator.token', 'config.toml', 'id_rsa',
                             'id_ed25519')
    assert not path.name.startswith('.env') and 'qwen-private' not in path.parts
    raw = path.read_bytes()
    if (path.name == 'packet-delivery.json' or '__pycache__' in path.parts
            or path.suffix in ('.o', '.a', '.dylib') or raw[:4] in magic):
        excluded.append(relative)
        continue
    selected.append((relative, raw))
entries = [{'path': name, 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in selected]
manifest = {
    'files': entries, 'excluded_host_binaries_and_caches': excluded,
    'integration_level': 1, 'full_ICB_contract': False,
    'concurrent_dispatch_qualified': False, 'all_hardware_functions_supported': False,
    'system_modified': False, 'Qwen_job_ids': [],
    'scope': 'Incremental CB0/dependency evidence; portable checks do not '
             'repeat GPU execution or re-attest omitted executables.'
}
with zipfile.ZipFile(ARCHIVE, 'x', zipfile.ZIP_DEFLATED) as archive:
    for name, raw in selected:
        archive.writestr(name, raw)
    archive.writestr('PACKET_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
with zipfile.ZipFile(ARCHIVE) as archive:
    assert archive.testzip() is None
    for entry in entries:
        raw = archive.read(entry['path'])
        assert len(raw) == entry['bytes']
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    CHECK.mkdir()
    archive.extractall(CHECK)

sys.path.insert(0, str(CHECK / 'bridge/tools'))
from verify_cpu_icb_dependency import verify as verify_dependency
from verify_cpu_icb_native_cas import verify as verify_cas
from verify_cpu_icb_mixed import verify as verify_mixed
oracles = {}
for kind, group in cohorts.items():
    verify = {'dependency': verify_dependency, 'cas': verify_cas,
              'mixed': verify_mixed}[kind]
    for name in group:
        result = verify(CHECK / 'bridge/results' / name, current=True, portable=True)
        assert result['status'] == 'PASS'
        oracles[name] = {k: v for k, v in result.items() if k != 'raw_SHA256'}
delivery = {
    'path': str(ARCHIVE), 'bytes': ARCHIVE.stat().st_size, 'files': len(entries),
    'SHA256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
    'all_CRC_SHA_verified': True, 'portable_oracles': len(oracles),
    'fresh_GPU_execution': False, 'Qwen_job_ids': [],
}
(CHECK / 'verification.json').write_text(json.dumps(oracles, indent=2) + '\n')
(ROOT / 'results/icb-dependency-progress/packet-delivery.json').write_text(
    json.dumps(delivery, indent=2) + '\n')
print(json.dumps(delivery, indent=2))
