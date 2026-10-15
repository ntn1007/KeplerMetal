#!/usr/bin/env python3
"""Prepare pinned build dependencies locally, including paths with spaces."""
from pathlib import Path
import argparse
import os
import sys
import json
import shutil
import subprocess
import tarfile
import hashlib

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--python', default=sys.executable)
args = parser.parse_args()
prefix = root/'build/rust-prefix'
venv = root/'build/python312-env'
env = os.environ.copy()
env['PATH'] = str(prefix/'bin')+':'+str(venv/'bin')+':'+env['PATH']
env['CARGO_HOME'] = str(root/'build/cargo-home')
env['CARGO_BUILD_JOBS'] = '2'
env['LIBCLANG_PATH'] = '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib'
status = []
def run(command, label):
    with (root/('logs/setup-'+label+'.log')).open('w') as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=log)
    status.append({'stage':label,'command':command,'exit_code':result.returncode})
    (root/'results/setup-tools.json').write_text(json.dumps(status,indent=2)+'\n')
    if result.returncode: raise SystemExit(result.returncode)
    print(label, 'OK', flush=True)

run([args.python,'-c','import sys; assert sys.version_info >= (3,10); print(sys.version)'], 'python-version')
if not (venv/'bin/python3').exists():
    run([args.python,'-m','venv',str(venv)], 'python-venv')
run([str(venv/'bin/python3'),'-m','pip','install','--disable-pip-version-check',
     '-r',str(root/'tools/python-requirements.txt')], 'python-packages')
prefix.mkdir(parents=True,exist_ok=True)
ready = all((prefix/'bin'/name).exists() for name in ('rustc','cargo'))
if ready:
    ready = all('1.99.0' in subprocess.check_output([str(prefix/'bin'/name),'--version'],text=True)
                for name in ('rustc','cargo'))
ready = ready and any((prefix/'lib/rustlib/x86_64-apple-darwin/lib').glob('libstd-*.rlib'))
for item in json.loads((root/'results/rust-toolchain-downloads.json').read_text()):
    archive = root/'vendor'/Path(item['url']).name
    if not archive.exists():
        run(['curl','-fL','--retry','2',item['url'],'-o',str(archive)], 'download-'+item['component'])
    if hashlib.sha256(archive.read_bytes()).hexdigest() != item['sha256']:
        raise RuntimeError('Rust archive checksum differs: '+str(archive))
    # Never overwrite an already usable toolchain, including during a build.
    if ready: continue
    extracted = root/'vendor'/archive.name.removesuffix('.tar.xz')
    if not extracted.exists():
        with tarfile.open(archive,'r:xz') as tar:
            members = tar.getmembers()
            for member in members:
                if Path(member.name).is_absolute() or '..' in Path(member.name).parts:
                    raise RuntimeError('Unsafe archive member')
                if member.issym():
                    target = (root/'vendor'/member.name).parent / member.linkname
                    if not target.resolve().is_relative_to((root/'vendor').resolve()):
                        raise RuntimeError('Unsafe archive symlink')
                if member.islnk() and (Path(member.linkname).is_absolute() or '..' in Path(member.linkname).parts):
                    raise RuntimeError('Unsafe archive hardlink')
            tar.extractall(root/'vendor')
    # Official component manifests describe files relative to this prefix.
    # Copy the component payload; install.sh's argument parser loses spaces.
    for component in (extracted/'components').read_text().splitlines():
        for source in (extracted/component).iterdir():
            if source.name == 'manifest.in': continue
            target = prefix/source.name
            if source.is_dir():
                shutil.copytree(source,target,dirs_exist_ok=True,symlinks=True)
            else:
                shutil.copy2(source,target,follow_symlinks=False)
run([str(prefix/'bin/rustc'),'--version'], 'rustc-version')
run([str(prefix/'bin/cargo'),'--version'], 'cargo-version')
for package, version, executable in [('bindgen-cli','0.73.2','bindgen'),('cbindgen','0.29.2','cbindgen')]:
    binary = prefix/'bin'/executable
    actual = subprocess.run([str(binary),'--version'],capture_output=True,text=True) if binary.exists() else None
    if actual is None or actual.returncode or version not in actual.stdout:
        run([str(prefix/'bin/cargo'),'install',package,'--version',version,'--locked',
             '--root',str(prefix)], 'cargo-'+package)
    run([str(binary),'--version'], executable+'-version')
