#!/usr/bin/env python3
"""Read selected installed versions and hashes; no binary copying or host IDs."""
from pathlib import Path
import hashlib
import json
import platform
import plistlib
import subprocess

COMPONENTS = ['GeForce.kext', 'GeForceAIRPlugin.bundle', 'GeForceMTLDriver.bundle',
              'GeForceGLDriver.bundle', 'GeForceVADriver.bundle', 'NVDAGK100Hal.kext',
              'NVDAResman.kext', 'NVDAStartup.kext', 'IOAcceleratorFamily2.kext']

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    if platform.system() != 'Darwin':
        raise SystemExit('Requires macOS; reads installed components only.')
    rows = []
    for name in COMPONENTS:
        bundle = Path('/System/Library/Extensions') / name
        info = bundle / 'Contents/Info.plist'
        row = {'component': name, 'present': bundle.exists()}
        if info.is_file():
            metadata = plistlib.loads(info.read_bytes())
            for key in ['CFBundleIdentifier', 'CFBundleVersion', 'CFBundleShortVersionString']:
                row[key] = metadata.get(key)
            executable_name = metadata.get('CFBundleExecutable')
            if isinstance(executable_name, str) and Path(executable_name).name == executable_name:
                executable = bundle / 'Contents/MacOS' / executable_name
                if executable.is_file():
                    row['executable_SHA256'] = digest(executable)
        rows.append(row)
    patch = Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')
    output = {'macOS': subprocess.check_output(['sw_vers'], text=True).strip(),
              'architecture': platform.machine(), 'components': rows,
              'OCLP_patch_plist_present': patch.is_file(),
              'OCLP_patch_plist_SHA256': digest(patch) if patch.is_file() else None,
              'system_modified': False, 'binaries_copied': False}
    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
