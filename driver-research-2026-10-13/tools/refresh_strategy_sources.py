#!/usr/bin/env python3
"""Snapshot missing official references and local SDK headers, without installing anything."""
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'sources' / 'strategy'
DEST.mkdir(exist_ok=True)
manifest_path = DEST / 'manifest.json'
previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'KeplerMetal-read-only-audit'}), timeout=45) as response:
        return response.read()

def record(path, origin):
    data = path.read_bytes()
    return {'file': str(path.relative_to(ROOT)), 'source': origin,
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

if 'metal_cpp_commit' in previous:
    commit = previous['metal_cpp_commit']
else:
    response = fetch('https://api.github.com/repos/apple/metal-cpp/commits/main')
    (DEST / 'metal-cpp-main-commit.json').write_bytes(response)
    commit = json.loads(response)['sha']
records = []
for name in ['MTL4CommandQueue.hpp', 'MTL4ArgumentTable.hpp', 'MTL4CommandAllocator.hpp']:
    url = f'https://raw.githubusercontent.com/apple/metal-cpp/{commit}/Metal/{name}'
    path = DEST / name
    if not path.exists():
        path.write_bytes(fetch(url))
    records.append(record(path, url))

url = 'https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf'
path = DEST / 'Metal-Shading-Language-Specification.pdf'
if not path.exists():
    path.write_bytes(fetch(url))
if not path.read_bytes().startswith(b'%PDF'):
    raise SystemExit('Official MSL reference was not a PDF')
records.append(record(path, url))

sdk = Path(subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip())
headers = sdk / 'System/Library/Frameworks/Metal.framework/Headers'
availability = []
for name in ['MTLDevice.h', 'MTLArgumentEncoder.h', 'MTLHeap.h', 'MTLFence.h',
             'MTLEvent.h', 'MTLIndirectCommandBuffer.h', 'MTL4CommandAllocator.h',
             'MTL4CommandQueue.h', 'MTL4ArgumentTable.h', 'MTLResidencySet.h']:
    origin = headers / name
    path = DEST / ('sdk-' + name)
    data = origin.read_bytes()
    path.write_bytes(data)
    records.append(record(path, str(origin)))
    availability += [{'file': name, 'line': i + 1, 'text': line.strip()}
                     for i, line in enumerate(data.decode().splitlines())
                     if 'API_AVAILABLE' in line]
(DEST / 'sdk-availability.json').write_text(json.dumps(availability, indent=2) + '\n')
result = {'captured_at': datetime.now(timezone.utc).isoformat(),
          'metal_cpp_commit': commit, 'sdk_path': str(sdk),
          'sdk_version': subprocess.check_output(['xcrun', '--show-sdk-version'], text=True).strip(),
          'files': records,
          'scope': 'References and SDK declarations only; no GPU feature qualification.'}
manifest_path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'metal_cpp_commit': commit, 'sdk_version': result['sdk_version'],
                  'files': len(records), 'manifest': str(manifest_path)}, indent=2))
