#!/usr/bin/env python3
"""Incremental source/raw-evidence package, including preserved failed probes."""
from pathlib import Path
import argparse, hashlib, json, zipfile

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
parser = argparse.ArgumentParser()
parser.add_argument('--name', default='KEPLERMETAL_CPU_ICB_2026-10-13-v2.zip')
args = parser.parse_args()
assert Path(args.name).name == args.name and args.name.endswith('.zip')
archive = ROOT / args.name
assert not archive.exists()
cohorts = ['cpu-icb-prepared', 'cpu-icb-prepared-runtime', 'cpu-icb-prepared-retained',
    'cpu-icb-gpu-qualified', 'cpu-icb-weak-prepared', 'cpu-icb-weak-gpu-qualified',
    'cpu-icb-lifetime-prepared', 'cpu-icb-lifetime-gpu-qualified',
    'cpu-icb-lifetime-readback-prepared', 'cpu-icb-lifetime-readback-gpu-qualified',
    'cpu-icb-progress', 'native-nop-record-qualified', 'native-cpu-record-layout',
    'native-cpu-record-storage', 'native-cpu-record-data', 'cpu-icb-documents']
files = set()
for cohort in cohorts:
    files.update(p for p in (ROOT / 'results' / cohort).rglob('*') if p.is_file() and not p.is_symlink())
for name in ['CPU_ICB_NATIF.txt', 'results/hardware-coverage.json',
    'src/KeplerCPUICB.h', 'src/KeplerCPUICB.mm', 'src/KeplerNativeCommands.h',
    'src/KeplerNativeCommands.mm', 'src/indirect_compute_probe.metal',
    'tools/cpu_icb_probe.mm', 'tools/cpu_icb_lifetime_probe.mm',
    'tools/reproduce_cpu_icb.py', 'tools/reproduce_cpu_icb_lifetime.py',
    'tools/verify_cpu_icb.py', 'tools/verify_cpu_icb_lifetime.py',
    'tools/native_cpu_record_probe.mm', 'tools/reproduce_native_cpu_record.py',
    'tools/reproduce_nop_native_record.py', 'tools/verify_native_replay.py',
    'tools/decode_native_commands.py',
    'tools/make_cpu_icb_report.py', 'tools/package_cpu_icb.py',
    'tools/verify_cpu_icb_delivery.py', 'tools/run_signed_probe.py']:
    files.add(ROOT / name)
research = LAB / 'driver-research-2026-10-13'
for name in ['reports/STRATEGIE_KEPLERMETAL.txt', 'reports/STRATEGIE_PREUVES.json',
    'reports/STRATEGIE_LIVRAISON.json', 'reports/MODERNISATION_NVIDIA_ACTUALISEE.json',
    'reports/MODERNISATION_NVIDIA_ACTUALISEE.csv', 'reports/METAL_CAPACITES_ACTUALISEES.json',
    'reports/METAL_CAPACITES_ACTUALISEES.csv', 'reports/EXPERIMENTATIONS_PRIORISEES.json',
    'tools/make_strategy_report.py']:
    files.add(research / name)
native_magic = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe',
                b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\x7fELF'}
selected, excluded = [], []
for path in sorted(files):
    assert path.is_file() and not path.is_symlink(), path
    rel = str(path.relative_to(LAB))
    with path.open('rb') as stream:
        magic = stream.read(4)
    if '__pycache__' in path.parts or path.suffix in ('.o', '.a', '.dylib') or magic in native_magic or path.name == 'packet-delivery.json':
        excluded.append(rel)
        continue
    if path.name.startswith('.env') or path.name in ('config.toml', 'id_rsa', 'id_ed25519') or 'coordinator.token' in path.name:
        raise ValueError('credential/config candidate refused')
    selected.append(path)
entries = [{'path': str(p.relative_to(LAB)), 'bytes': p.stat().st_size,
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in selected]
manifest = {'files': entries, 'excluded_host_binaries_and_caches': excluded,
    'ICB_contract_complete': False, 'CPU_compute_selector_subset_qualified': True,
    'GPU_generated_ICB': False, 'integration_level': 1, 'Qwen_job_ids': [],
    'system_modified': False, 'all_hardware_functions_supported': False,
    'scope': 'Incremental lab sources/raw GPU oracles and preserved failures. Not an installable '
             'driver. GPU execution requires pinned iMac/workspace; portable verification does '
             'not re-attest omitted host executables or repeat physical GPU execution.'}
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
    for path, entry in zip(selected, entries):
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        output.writestr(entry['path'], raw)
    output.writestr('PACKET_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
with zipfile.ZipFile(archive) as output:
    assert output.testzip() is None and len(output.namelist()) == len(entries) + 1
    for entry in entries:
        raw = output.read(entry['path'])
        assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
delivery = {'path': str(archive), 'bytes': archive.stat().st_size,
    'content_files': len(entries), 'ZIP_entries': len(entries) + 1,
    'SHA256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'CRC_and_all_SHA256_verified': True, 'Qwen_job_ids': []}
(ROOT / 'results/cpu-icb-progress/packet-delivery.json').write_text(json.dumps(delivery, indent=2) + '\n')
print(json.dumps(delivery, indent=2))
