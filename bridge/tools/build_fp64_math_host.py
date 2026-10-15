#!/usr/bin/env python3
"""Build one immutable x86_64 capture host for reuse across fresh processes.

No Metal device/context is created here. This is an explicit build, not a
general dependency cache. Each run separately validates and signs its copy.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
out.relative_to(ROOT / 'results')
assert not out.exists()
out.mkdir()
sources = {
    'fp64_math_probe.mm': ROOT / 'tools/fp64_math_probe.mm',
    'KeplerProgramImport.h': ROOT / 'src/KeplerProgramImport.h',
    'KeplerProgramImport.mm': ROOT / 'src/KeplerProgramImport.mm',
}
for name, path in sources.items():
    (out / name).write_bytes(path.read_bytes())
exe = out / 'fp64_math_probe'
argv = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc',
        '-I', str(out), str(out / 'fp64_math_probe.mm'),
        str(out / 'KeplerProgramImport.mm'), '-framework', 'Metal',
        '-framework', 'Foundation', '-o', str(exe)]
r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=50)
(out / 'build.stdout').write_text(r.stdout)
(out / 'build.stderr').write_text(r.stderr)
(out / 'commands.json').write_text(json.dumps([{'argv': argv, 'exit_code': r.returncode}], indent=2) + '\n')
assert r.returncode == 0, r.stderr[-2500:]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
d = {'source_SHA256': {name: sha(out / name) for name in sources},
     'executable_SHA256': sha(exe), 'GPU_execution': False,
     'architecture': 'x86_64', 'builder_SHA256': sha(Path(__file__))}
(out / 'inputs.json').write_text(json.dumps(d, indent=2) + '\n')
print(json.dumps({'out': str(out), 'GPU_execution': False, 'build': 'PASS'}))
