#!/usr/bin/env python3
"""Freeze FP64 source/captures, then recheck raw oracles after extraction.

Host executables, Mesa archives, caches and unrelated process listings are
excluded. Portable verification checks the captured bytes, not a new GPU run.
"""
from pathlib import Path
import hashlib, importlib.util, json, zipfile

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
archive = ROOT / 'KEPLERMETAL_FP64_2026-10-14.zip'
check = ROOT / 'results/fp64-math-portable-verification-20261014'
assert not archive.exists() and not check.exists()
files = set()
for folder in (ROOT / 'results').iterdir():
    if folder.name.startswith(('fp64-math-', 'fp64-normalized-', 'fp64-strict-')):
        if folder.is_dir():
            files.update(p for p in folder.rglob('*') if p.is_file())
        elif folder.is_file():
            files.add(folder)
for name in ['fp64_math_compile.c', 'build_fp64_math.py', 'build_fp64_math_host.py',
             'prepare_fp64_math_cases.py', 'fp64_math_probe.mm', 'run_fp64_math_case.py',
             'run_fp64_math_suite.py', 'verify_fp64_math.py', 'check_fp64_div_model.py',
             'make_fp64_math_report.py', 'package_fp64_math_evidence.py',
             'run_signed_probe.py', 'lab_gpu_reservation.py']:
    files.add(ROOT / 'tools' / name)
files.update(ROOT / 'src' / n for n in ['KeplerProgramImport.h', 'KeplerProgramImport.mm'])
files.update(ROOT / n for n in ['FP64_OPERATIONS_QUALIFIEES_2026-10-14.txt',
                               'WORKFLOW_MISE_A_JOUR_2026-10-14.txt',
                               'WORKFLOW_PISTES_VERIFIEES_2026-10-14.txt',
                               'results/hardware-coverage.json'])
magic = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe',
         b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca', b'\x7fELF'}
selected, excluded = [], []
for p in sorted(files):
    assert p.is_file() and not p.is_symlink()
    assert p.name not in ['coordinator.token', 'config.toml', 'id_rsa', 'id_ed25519']
    assert not p.name.startswith('.env') and 'qwen-private' not in p.parts
    rel = str(p.relative_to(LAB))
    raw = p.read_bytes()
    if '__pycache__' in p.parts or p.suffix in ['.o', '.a', '.dylib'] or raw[:4] in magic or p.name in ['process-table.json', 'packet-delivery.json']:
        excluded.append(rel)
        continue
    selected.append((rel, raw))
entries = [{'path': n, 'bytes': len(raw), 'SHA256': hashlib.sha256(raw).hexdigest()} for n, raw in selected]
manifest = {'files': entries, 'excluded': excluded, 'Git_branch': 'main', 'Git_commit': None,
            'integration_level': 1, 'goal_complete': False, 'system_modified': False,
            'Qwen_job_ids': [], 'scope': 'Source and raw captures; portable checks are not new GPU execution or host binary re-attestation. Original host binaries remain local.'}
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
    for name, raw in selected:
        z.writestr(name, raw)
    z.writestr('PACKET_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for e in entries:
        raw = z.read(e['path'])
        assert len(raw) == e['bytes'] and hashlib.sha256(raw).hexdigest() == e['SHA256']
    check.mkdir()
    z.extractall(check)
spec = importlib.util.spec_from_file_location('fp64_portable', check / 'bridge/tools/verify_fp64_math.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
verified = {}
for name in ['fp64-math-suite-20261014', 'fp64-math-normalized-suite-20261014-03']:
    d = json.loads((check / 'bridge/results' / name / 'summary.json').read_text())
    for r in d['records']:
        relative = Path(r['path']).relative_to(ROOT)
        v = module.verify(check / 'bridge' / relative, portable=True)
        assert v['status'] == r['verification']['status']
        for k in ['numeric_mismatches', 'tag_mismatches', 'correct_double_results']:
            assert v[k] == r['verification'][k]
        verified[name + '/' + r['label']] = {k: x for k, x in v.items() if k not in ['raw_files_SHA256', 'errors']}
(check / 'verification.json').write_text(json.dumps(verified, indent=2) + '\n')
delivery = {'path': str(archive), 'SHA256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'files': len(entries), 'bytes': archive.stat().st_size,
            'all_CRC_SHA_verified': True, 'portable_oracles': len(verified),
            'normalized_oracles_PASS': sum(v['status'].startswith('PASS') for k, v in verified.items() if k.startswith('fp64-math-normalized-suite')),
            'baseline_numeric_FAIL_preserved': sum(v['status'] == 'FAIL' for k, v in verified.items() if k.startswith('fp64-math-suite')),
            'fresh_GPU_execution_by_packager': False, 'goal_complete': False, 'Qwen_job_ids': []}
assert delivery['normalized_oracles_PASS'] == 45 and delivery['baseline_numeric_FAIL_preserved'] == 6
(ROOT / 'results/fp64-math-progress-20261014/packet-delivery.json').write_text(json.dumps(delivery, indent=2) + '\n')
print(json.dumps(delivery, indent=2))
