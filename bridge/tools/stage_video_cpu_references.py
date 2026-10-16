#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage independent NV12 references while reusing exact immutable probe code.

The executable retains its dependency on the original frozen observer library.
This stages new assets; it neither rebuilds code nor reuses execution results.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-build', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--reference-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source_build.resolve(), args.out.resolve()
    out.relative_to(ROOT / 'results')
    reference = args.reference.read_bytes()
    assert hashlib.sha256(reference).hexdigest() == args.reference_sha256
    assert len(reference) == 320 * 240 * 3 // 2 * 6
    inputs = json.loads((source / 'inputs.json').read_text())
    assert sha(source / 'application') == inputs['executable_SHA256']
    assert sha(source / 'libVideoVAObserver.dylib') == inputs['observer_library_SHA256']
    for name, h in inputs['source_hashes'].items():
        assert sha(source / name) == h
    for name, h in inputs['assets_SHA256'].items():
        assert sha(source / 'assets' / name) == h
    for name, h in inputs['runtime_SHA256'].items():
        assert sha(source / 'runtime' / name) == h
    fixture = json.loads((source / 'assets/fixture/fixture.json').read_text())
    assert len(fixture['frames']) == 6
    assert not any((source / 'assets/fixture').glob('cpu-frame-*.nv12'))
    out.mkdir(exist_ok=False)
    for folder in ['assets', 'runtime']:
        shutil.copytree(source / folder, out / folder)
    for name in [*inputs['source_hashes'], 'application', 'libVideoVAObserver.dylib', 'vda.o', 'vt.o']:
        shutil.copyfile(source / name, out / name)
    (out / 'application').chmod(0o755)
    shutil.copyfile(source / 'commands.json', out / 'original-build-commands.json')
    shutil.copyfile(Path(__file__), out / 'asset-stager.py')
    frame_bytes = 320 * 240 * 3 // 2
    for i in range(6):
        (out / 'assets/fixture' / f'cpu-frame-{i:03d}.nv12').write_bytes(reference[i*frame_bytes:(i+1)*frame_bytes])
    derivation = {'kind': 'ASSET_ONLY_DERIVATION', 'source_build': str(source),
                  'source_build_inputs_SHA256': sha(source / 'inputs.json'),
                  'original_library_dependency': str(source / 'libVideoVAObserver.dylib'),
                  'reference_SHA256': args.reference_sha256, 'reference_bytes': len(reference),
                  'executable_rebuilt': False, 'execution_results_reused': False,
                  'original_compressed_fixtures_preserved': True, 'GPU_execution': False}
    (out / 'derivation.json').write_text(json.dumps(derivation, indent=2) + '\n')
    inputs['source_hashes']['asset-stager.py'] = sha(out / 'asset-stager.py')
    inputs['assets_SHA256'] = {str(p.relative_to(out / 'assets')): sha(p)
                              for p in (out / 'assets').rglob('*') if p.is_file()}
    inputs['immutable_executable_reused'] = True
    inputs['source_build_inputs_SHA256'] = derivation['source_build_inputs_SHA256']
    inputs['derivation_SHA256'] = sha(out / 'derivation.json')
    inputs['fixture_files'] = len(list((out / 'assets/fixture').iterdir()))
    (out / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    print(json.dumps({'status': 'STAGED', 'executable_rebuilt': False,
                      'reference_bytes': len(reference), 'GPU_work': 0}))


if __name__ == '__main__':
    main()
