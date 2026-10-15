#!/usr/bin/env python3
"""Extract our immutable packet once and rerun portable raw oracles, not GPUs."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, subprocess, sys, zipfile

p = argparse.ArgumentParser()
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
archive, out = a.archive.resolve(), a.out.resolve()
assert not out.exists()
out.mkdir()
extracted = out / 'extracted'
extracted.mkdir()
with zipfile.ZipFile(archive) as packet:
    assert packet.testzip() is None
    manifest = json.loads(packet.read('PACKET_MANIFEST.json'))
    assert len(packet.namelist()) == len(manifest['files']) + 1
    assert set(packet.namelist()) == {f['path'] for f in manifest['files']} | {'PACKET_MANIFEST.json'}
    for entry in manifest['files']:
        member = PurePosixPath(entry['path'])
        assert not member.is_absolute() and '..' not in member.parts
        raw = packet.read(entry['path'])
        assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
        path = extracted / entry['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
bridge = extracted / 'bridge'
checks = []
groups = [('verify_cpu_icb.py', ['cpu-icb-prepared-retained', 'cpu-icb-gpu-qualified',
           'cpu-icb-weak-prepared', 'cpu-icb-weak-gpu-qualified']),
          ('verify_cpu_icb_lifetime.py', ['cpu-icb-lifetime-prepared',
           'cpu-icb-lifetime-readback-prepared', 'cpu-icb-lifetime-readback-gpu-qualified'])]
for script, cohorts in groups:
    for cohort in cohorts:
        args = [sys.executable, str(bridge / 'tools' / script), '--input',
                str(bridge / 'results' / cohort), '--portable']
        r = subprocess.run(args, capture_output=True, text=True, timeout=30)
        (out / (cohort + '.stdout')).write_text(r.stdout)
        (out / (cohort + '.stderr')).write_text(r.stderr)
        assert r.returncode == 0, (cohort, r.stderr[-2000:])
        checks.append({'cohort': cohort, 'portable_raw_oracle': 'PASS', 'new_GPU_execution': False})
r = subprocess.run([sys.executable, str(bridge / 'tools/verify_native_replay.py'),
                    '--input', str(bridge / 'results/native-nop-record-qualified')],
                   capture_output=True, text=True, timeout=30)
(out / 'native-nop-record.stdout').write_text(r.stdout)
(out / 'native-nop-record.stderr').write_text(r.stderr)
assert r.returncode == 0, r.stderr[-2000:]
history = json.loads((bridge / 'results/cpu-icb-progress/verification-history.json').read_text())
assert [row['exit_code'] for row in history] == [-6, -11, 0, 0, 0, 0, 0, 17, 0, 0]
result = {'status': 'PASS', 'archive': str(archive),
    'archive_SHA256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'CRC_and_SHA256_content_files': len(manifest['files']),
    'CPU_ICB_portable_oracle_cohorts': len(checks), 'NOP_materialization_oracle': 'PASS',
    'preserved_failed_children': 3, 'host_executables_re_attested': False,
    'new_GPU_execution': False, 'system_modified': False, 'checks': checks}
(out / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
