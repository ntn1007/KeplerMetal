#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Survey the retained Sierra odc payload without extracting or executing it."""
import argparse
import hashlib
import json
from pathlib import Path
from survey import scan

EXPECTED_SIZE = 5835166720


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if not a.out.parent.is_dir() or a.out.exists(): raise ValueError('fresh output required')
    if a.archive.stat().st_size != EXPECTED_SIZE: raise ValueError('archive size differs')
    with a.archive.open('rb') as stream:
        result = scan(stream, EXPECTED_SIZE)
    result.update(status='PASS_SIERRA_REGULAR_MEMBER_LITERAL_SURVEY', property_name='IOGVACodec',
                  scope='All regular members in retained Sierra payload, three literal encodings; nested compression excluded',
                  source_signature_rechecked=False, dynamically_produced_property_excluded=False,
                  complete_installation_searched=False, vendor_execution=False, GPU_execution=False,
                  system_modified=False, scanner_sha256=sha(Path(__file__).with_name('survey.py')),
                  wrapper_sha256=sha(Path(__file__)))
    with a.out.open('x') as f:
        json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'archive_sha256':result['archive_sha256'],
                      'records':result['records'],'regular_members':result['regular_members'],
                      'matching_members':len(result['matches'])}))


if __name__ == '__main__': main()
