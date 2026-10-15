#!/usr/bin/env python3
"""Bundle frozen SDK delivery and client raw evidence, excluding host executables."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
archive = ROOT / 'KEPLERMETAL_SDK_APPLICATION_ADAPTEE_2026-10-14.zip'
assert not archive.exists()
files = set()
for name in ['sdk-progress-20261014', 'sdk-delivered-client-prepared-04',
             'sdk-delivered-client-gpu-qualified-04']:
    files.update(p for p in (ROOT / 'results' / name).rglob('*') if p.is_file())
files.update(p for p in (ROOT / 'sdk').rglob('*') if p.is_file())
for name in ['KeplerCPUICB', 'KeplerNativeCommands', 'KeplerNativeRenderDraws']:
    for suffix in ['h', 'mm']:
        files.add(ROOT / 'src' / (name + '.' + suffix))
for name in ['tools/build_keplermetal_sdk.py', 'tools/make_sdk_report.py',
             'tools/package_sdk_evidence.py', 'SDK_APPLICATION_ADAPTEE.txt',
             'results/hardware-coverage.json',
             'results/keplermetal-sdk-build-20261014-04/delivery.json',
             'results/keplermetal-sdk-build-20261014-04/KeplerMetalSDK-x86_64-2026-10-14.tar.gz',
             'results/keplermetal-sdk-client-20261014-04/extraction-verification.json',
             'results/keplermetal-sdk-client-20261014-04/application/commands.json',
             'results/keplermetal-sdk-client-20261014-04/application/inputs.json',
             'results/keplermetal-sdk-client-20261014-01/application/commands.json',
             'results/keplermetal-sdk-client-20261014-01/application/application.stderr',
             'results/keplermetal-sdk-client-20261014-02/application/execution/manifest.json']:
    files.add(ROOT / name)
entries, excluded = [], []
magic = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe',
         b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\x7fELF'}
for path in sorted(files):
    assert path.is_file() and not path.is_symlink()
    rel = str(path.relative_to(LAB))
    if path.name == 'packet-delivery.json' or '__pycache__' in path.parts \
       or path.suffix in ('.o', '.a', '.dylib') or path.read_bytes()[:4] in magic:
        excluded.append(rel)
        continue
    assert path.name not in ('coordinator.token', 'config.toml', 'id_ed25519', 'id_rsa')
    assert not path.name.startswith('.env') and 'qwen-private' not in path.parts
    raw = path.read_bytes()
    entries.append({'path': rel, 'bytes': len(raw),
                    'sha256': hashlib.sha256(raw).hexdigest()})
manifest = {'files': entries, 'excluded_host_executables_and_caches': excluded,
            'scope': 'SDK tar explicitly contains the qualified static library; evidence directories omit host executables. Portable verification does not repeat GPU execution or re-attest omitted executables.',
            'integration_level': 2, 'integration_scope': 'Five bounded adapted-client render scenarios',
            'all_hardware_functions_supported': False, 'system_modified': False,
            'Qwen_job_ids': []}
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as zip:
    for entry in entries:
        raw = (LAB / entry['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        zip.writestr(entry['path'], raw)
    zip.writestr('PACKET_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
with zipfile.ZipFile(archive) as zip:
    assert zip.testzip() is None
    for entry in entries:
        raw = zip.read(entry['path'])
        assert len(raw) == entry['bytes']
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
delivery = {'path': str(archive), 'bytes': archive.stat().st_size,
            'files': len(entries), 'SHA256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'all_SHA256_verified': True, 'Qwen_job_ids': []}
(ROOT / 'results/sdk-progress-20261014/packet-delivery.json').write_text(
    json.dumps(delivery, indent=2) + '\n')
print(json.dumps(delivery, indent=2))
