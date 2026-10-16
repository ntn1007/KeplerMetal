#!/usr/bin/env python3
"""Freeze one bounded native reservation experiment; keep the qualified API intact."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = 'ecff9c4f83d25283cf35a31ac77f53bcc9d1032a77b21209aba07ce3c5795991'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['out', 'native-build', 'observations']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--reserve', type=int, choices=[2048, 2560, 3072, 3584, 4096], required=True)
    a = p.parse_args(); out = a.out.resolve(); out.relative_to(ROOT / 'results')
    native, obs = a.native_build.resolve(), a.observations.resolve()
    ni = json.loads((native / 'inputs.json').read_text()); od = json.loads((obs / 'observations.json').read_text())
    assert od['native_build_inputs_SHA256'] == sha(native / 'inputs.json')
    assert sha(ROOT / 'tools/NativeControlReserveExperiment.mm') == EXPERIMENT
    for name, digest in ni['assets_SHA256'].items():
        assert sha(native / 'assets' / name) == digest
    out.mkdir(exist_ok=False)
    shutil.copytree(native / 'assets', out / 'assets'); shutil.copytree(native / 'runtime', out / 'runtime')
    certificates = {}
    for row in od['records']:
        assert sha(obs / row['function'] / 'capture/native.sass') == row['code_SHA256']
        certificates[row['function']] = {'metadata_words': row['metadata_words'], 'code_SHA256': row['code_SHA256']}
    config = {'variant': ni.get('variant', 'nested'), 'entry_witness': ni.get('entry_witness', False),
              'depths': [r['source_depth'] for r in od['records']], 'certificates': certificates,
              'control_reserve': a.reserve}
    (out / 'assets/control_flow_config.json').write_text(json.dumps(config, indent=2) + '\n')
    sources = ['control_flow_probe.mm', 'NativeControlReserveExperiment.mm']
    for name in sources: shutil.copyfile(ROOT / 'tools' / name, out / name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    commands = []
    for label, argv in [
        ('module', ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc', '-c', out / sources[1], '-o', out / 'reserve.o']),
        ('host', ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fobjc-arc', '-DKP_NATIVE_RESERVE_EXPERIMENT=1',
                  out / sources[0], out / 'reserve.o', '-framework', 'Foundation', '-framework', 'Metal', '-o', out / 'application'])]:
        argv = list(map(str, argv)); r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        (out / (label + '.stdout')).write_text(r.stdout); (out / (label + '.stderr')).write_text(r.stderr)
        commands.append({'label': label, 'argv': argv, 'exit_code': r.returncode})
        (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        assert r.returncode == 0, r.stderr[-3000:]
    inputs = {'source_hashes': {n: sha(out / n) for n in sources},
              'assets_SHA256': {f.name: sha(f) for f in (out / 'assets').iterdir()},
              'runtime_SHA256': {f.name: sha(f) for f in (out / 'runtime').iterdir()},
              'executable_SHA256': sha(out / 'application'), 'module_object_SHA256': sha(out / 'reserve.o'),
              'native_build_inputs_SHA256': sha(native / 'inputs.json'), 'observations_SHA256': sha(obs / 'observations.json'),
              'source_generator_SHA256': sha(out / 'builder.py'), 'reserve_mode': str(a.reserve),
              'GPU_execution': False, 'scope': 'Standalone pinned experiment; native GPU code and common runtime unchanged'}
    (out / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'reserve': a.reserve, 'experiment_SHA256': EXPERIMENT}))


if __name__ == '__main__': main()
