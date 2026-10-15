#!/usr/bin/env python3
"""Freeze and launch the distinct CPU ICB lifetime consumer in this workspace."""
from pathlib import Path
import argparse, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True)
p.add_argument('--execute', action='store_true')
a = p.parse_args()
out = a.out.resolve()
out.relative_to(ROOT / 'results')
assert not out.exists()
out.mkdir()
commands = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, label):
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=45)
    (out / (label + '.stdout')).write_text(result.stdout)
    (out / (label + '.stderr')).write_text(result.stderr)
    commands.append({'label': label, 'argv': argv, 'exit_code': result.returncode})
    (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    print(label, result.returncode, flush=True)
    assert result.returncode == 0, result.stderr[-4000:]


sources = []
for folder, name in [('src', 'KeplerCPUICB.h'), ('src', 'KeplerCPUICB.mm'),
                     ('src', 'KeplerNativeCommands.h'), ('src', 'KeplerNativeCommands.mm'), ('src','cpu_icb_manifest.metal'), ('src','cpu_icb_manifest.json'),
                     ('tools', 'cpu_icb_manifest_lifetime_probe.mm')]:
    target = out / name
    target.write_bytes((ROOT / folder / name).read_bytes())
    sources.append(target)
library = out / 'cpu_icb_manifest.metallib'
library.write_bytes((ROOT / 'results/native-manifest-pipeline-variable-captured' / library.name).read_bytes())
(out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
(out / 'inputs.json').write_text(json.dumps({'source_hashes': {s.name: sha(s) for s in sources},
    'library_SHA256': sha(library), 'Git_commit': None, 'Qwen_job_ids': [],
    'system_modified': False}, indent=2) + '\n')
exe = out / 'cpu_icb_manifest_lifetime_probe'
run(['clang++', '-O2', '-std=c++17', '-fobjc-arc', '-I', str(out),
     str(out / 'cpu_icb_manifest_lifetime_probe.mm'), str(out / 'KeplerCPUICB.mm'),
     str(out / 'KeplerNativeCommands.mm'), '-framework', 'Metal', '-framework',
     'Foundation', '-o', str(exe)], 'build')
raw = out / 'outputs'
raw.mkdir()
execution = out / 'execution'
run(['python3', str(ROOT / 'tools/run_signed_probe.py'), '--exe', str(exe),
     '--out', str(execution), '--timeout', '30', '--', str(library), str(out/'cpu_icb_manifest.json'), str(raw),
     'execute' if a.execute else 'prepare'], 'observe')
manifest = json.loads((execution / 'manifest.json').read_text())
assert manifest['exit_code'] == 0 and not manifest['SIGKILL_requested'] and not manifest['authoritative_ps_status']
data = json.loads((execution / 'execution.stdout').read_text())
(out / 'results.json').write_text(json.dumps(data, indent=2) + '\n')
assert data['passed'] and data['scope_restored']
print(json.dumps({'mode': data['mode'], 'cases': len(data['cases']), 'all_children_terminal': True}))
