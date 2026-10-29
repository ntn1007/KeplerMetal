#!/usr/bin/env python3
"""Test the audit against temporary altered copies of a retained reference."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    a = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='kepler-m1-inherit-audit-') as directory:
        root = Path(directory)
        for case in ('baseline', 'both_outputs_wrong', 'control_wrong', 'report_wrong'):
            folder = root/case; shutil.copytree(a.input, folder)
            hashes_path = folder/'remote-hashes.json'; hashes = json.loads(hashes_path.read_text())
            if case == 'both_outputs_wrong':
                targets = ['captures/direct-1.bin', 'captures/icb-1.bin']
            elif case == 'control_wrong': targets = ['captures/no-dispatch.bin']
            elif case == 'report_wrong':
                report = json.loads((folder/'stdout.json').read_text()); report['pipeline_order'] = ['a','a','a']
                (folder/'stdout.json').write_text(json.dumps(report)); targets = ['stdout.json']
            else: targets = []
            for name in targets:
                path = folder/name
                if name.endswith('.bin'):
                    data = bytearray(path.read_bytes()); data[0] ^= 1; path.write_bytes(data)
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes_path.write_text(json.dumps(hashes))
            result = subprocess.run([sys.executable, str(HERE/'audit.py'), '--input', str(folder),
                                     '--out', str(root/(case+'.json'))], capture_output=True, text=True, timeout=20)
            expected = {'both_outputs_wrong':'value mismatch', 'control_wrong':'no-dispatch control changed',
                        'report_wrong':'host report differs'}.get(case)
            if case == 'baseline':
                if result.returncode != 0: raise ValueError('baseline failed: '+result.stderr[-500:])
            elif result.returncode == 0 or expected not in result.stderr or (root/(case+'.json')).exists():
                raise ValueError('negative not refused: '+case+' '+result.stderr[-500:])
    print('PASS_AUDIT_MUTATIONS: baseline and three rehashed corruptions; no GPU execution')


if __name__ == '__main__': main()
