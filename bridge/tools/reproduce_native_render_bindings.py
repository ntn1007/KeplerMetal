#!/usr/bin/env python3
"""Freeze/build a passive native render capture using an existing pinned library."""
from pathlib import Path
import argparse, hashlib, json, subprocess
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); a = p.parse_args()
out = a.out.resolve(); out.relative_to(ROOT / 'results'); assert not out.exists(); out.mkdir()
commands = []
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def run(argv, label):
    r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=45)
    (out / (label + '.stdout')).write_text(r.stdout); (out / (label + '.stderr')).write_text(r.stderr)
    commands.append({'label': label, 'argv': argv, 'exit_code': r.returncode})
    (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    print(label, r.returncode, flush=True); assert r.returncode == 0, r.stderr[-3000:]
host = out / 'native_render_bindings_capture.mm'; host.write_bytes((ROOT / 'tools' / host.name).read_bytes())
(out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
library = out / 'vertex_io_carrier.metallib'
library.write_bytes((ROOT / 'results/vertex-io-final' / library.name).read_bytes())
assert sha(library) == 'c0e24e5a5534e10f0eca591b5ace2112d76eafde74ed297ce1b3df0d95b5ca43'
(out / 'inputs.json').write_text(json.dumps({'source_hashes': {host.name: sha(host)},
    'library_SHA256': sha(library), 'Git_commit': None, 'Qwen_job_ids': [], 'system_modified': False}, indent=2) + '\n')
exe = out / 'native_render_bindings_capture'
run(['clang++', '-O2', '-std=c++17', '-fobjc-arc', str(host), '-framework', 'Metal', '-framework', 'Foundation', '-o', str(exe)], 'build')
raw = out / 'outputs'; raw.mkdir()
run(['python3', str(ROOT / 'tools/run_signed_probe.py'), '--exe', str(exe), '--out', str(out / 'execution'),
     '--timeout', '20', '--', str(library), str(raw)], 'observe')
m = json.loads((out / 'execution/manifest.json').read_text())
assert m['exit_code'] == 0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
d = json.loads((out / 'execution/execution.stdout').read_text())
assert not d['committed'] and not d['native_memory_modified'] and not d['GPU_user_submissions']
(out / 'capture.json').write_text(json.dumps(d, indent=2) + '\n')
print(json.dumps({'records': len(d['records']),
    'comparable': sum(r['comparable'] for r in d['records']), 'all_children_terminal': True}, indent=2))
