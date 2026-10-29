#!/usr/bin/env python3
"""Exercise the state audit against temporary, intentionally altered captures."""
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='kepler-m1-state-audit-') as temp:
        root=Path(temp)
        for case in ('baseline','matching_bad_pair','control_bad','report_bad'):
            folder=root/case;shutil.copytree(a.input,folder);hashfile=folder/'remote-hashes.json';hashes=json.loads(hashfile.read_text())
            if case=='matching_bad_pair': targets=['captures/icb-1.bin','captures/parent-1.bin']
            elif case=='control_bad': targets=['captures/untouched.bin']
            elif case=='report_bad':
                report=json.loads((folder/'stdout.json').read_text());report['parent_rebound_after_icb']=True
                (folder/'stdout.json').write_text(json.dumps(report));targets=['stdout.json']
            else: targets=[]
            for name in targets:
                path=folder/name
                if name.endswith('.bin'):
                    data=bytearray(path.read_bytes());data[0]^=1;path.write_bytes(data)
                hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
            hashfile.write_text(json.dumps(hashes))
            result=subprocess.run([sys.executable,str(HERE/'audit_state.py'),'--input',str(folder),'--out',str(root/(case+'.json'))],capture_output=True,text=True,timeout=20)
            expected={'matching_bad_pair':'capture mismatch','control_bad':'control changed','report_bad':'host report differs'}.get(case)
            if case=='baseline':
                if result.returncode:raise ValueError('baseline failed: '+result.stderr[-500:])
            elif result.returncode==0 or expected not in result.stderr or (root/(case+'.json')).exists():
                raise ValueError('negative not refused: '+case+' '+result.stderr[-500:])
    print('PASS_STATE_AUDIT_MUTATIONS: baseline and three rehashed corruptions; no GPU execution')


if __name__=='__main__': main()
