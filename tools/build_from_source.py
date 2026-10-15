#!/usr/bin/env python3
"""Build every runtime object from published text; no GPU dispatch or downloads."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MRC = {'KeplerNativeCAS', 'KeplerProgramImport'}
SOURCES = ['KeplerCPUICB', 'KeplerNativeCommands', 'KeplerNativeRenderDraws',
           'KeplerNativeCAS', 'KeplerFP64', 'KeplerProgramImport']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != 'Darwin':
        parser.error('This source build requires macOS and Xcode; portable checks run on other hosts.')
    out = args.out.resolve()
    try:
        relative = out.relative_to(ROOT / 'build')
        assert relative.parts
    except (ValueError, AssertionError):
        parser.error('--out must be a new directory beneath this checkout/build/')
    out.mkdir(parents=True, exist_ok=False)
    sources = out / 'src'
    sources.mkdir()
    for file in (ROOT / 'bridge/src').iterdir():
        if file.suffix in {'.h', '.mm', '.inc'}:
            shutil.copyfile(file, sources / file.name)
    shutil.copyfile(ROOT / 'examples/link_check.mm', out / 'link_check.mm')
    commands = []

    def run(label, argv):
        argv = [str(x) for x in argv]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        commands.append({'label': label, 'argv': argv, 'exit_code': result.returncode})
        (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        if result.returncode:
            print(result.stderr[-2500:], file=sys.stderr)
            raise SystemExit(f'{label}: FAIL ({result.returncode}); see {out}')
        print(label + ': PASS', flush=True)
        return result.stdout.strip()

    sdk = run('sdk', ['xcrun', '--sdk', 'macosx', '--show-sdk-version'])
    clang = run('clang', ['xcrun', 'clang++', '--version'])
    common = ['xcrun', 'clang++', '-arch', 'x86_64', '-O2', '-std=c++17']
    objects = []
    for name in SOURCES:
        obj = out / (name + '.o')
        run(name, common + ['-fno-objc-arc' if name in MRC else '-fobjc-arc',
                           '-I', sources, '-c', sources / (name + '.mm'), '-o', obj])
        objects.append(obj)
    library = out / 'libKeplerMetal.a'
    run('archive', ['xcrun', 'ar', 'rcs', library] + objects)
    executable = out / 'link_check'
    run('link', common + ['-fobjc-arc', '-I', sources, out / 'link_check.mm',
                         '-Wl,-all_load', library, '-framework', 'Metal', '-framework',
                         'Foundation', '-o', executable])
    run('cpu-link-check', [executable])
    manifest = {'status': 'PASS', 'architecture': 'x86_64', 'SDK': sdk, 'clang': clang,
                'source_SHA256': {p.name: sha(p) for p in sorted(sources.iterdir())},
                'object_SHA256': {p.name: sha(p) for p in objects},
                'static_library_SHA256': sha(library), 'link_check_SHA256': sha(executable),
                'builder_SHA256': sha(Path(__file__)), 'GPU_execution': False,
                'system_modified': False, 'GPU_qualification': 'NOT RUN',
                'historical_qualification_inherited': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'library_SHA256': manifest['static_library_SHA256'], 'GPU_execution': False}))

if __name__ == '__main__':
    main()
