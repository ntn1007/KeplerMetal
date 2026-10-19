#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Serialize one public-archive suite and stop before the next case on failure."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--reservation-root', type=Path, required=True)
    p.add_argument('--suite', choices=['baseline', 'extended', 'legacy', 'witness'], required=True)
    a = p.parse_args(); build = a.build.resolve(); out = a.out.resolve()
    inputs = json.loads((build / 'inputs.json').read_text())
    assert inputs['extended_profile'] == (a.suite in ['extended', 'legacy'])
    assert inputs['carrier'] == ('legacy' if a.suite == 'legacy' else 'large')
    assert inputs['execution_witness_magic'] == (0x4e414b00 if a.suite == 'witness' else None)
    modes = (['nak:local_control', 'nak:local32', 'nak:local256', 'nak:local1024', 'nak:pressure32', 'nak:pressure64', 'nak:pressure96', 'nak:pressure32_forced_spill', 'nak:no_dispatch:local1024', 'nak:no_dispatch:pressure96']
        if a.suite == 'legacy' else ['nak:local2048', 'nak:no_dispatch:local2048', 'nak:local4096', 'nak:no_dispatch:local4096'])
    assert not out.exists() and out.parent.is_dir()
    out.mkdir(); history = []; tool = Path(__file__).with_name('public_large_scratch.py')
    sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    for mode in modes:
        case = out / mode.replace(':', '-')
        cmd = list(map(str, [sys.executable, '-B', tool, 'run', '--build', build, '--out', case,
            '--reservation-root', a.reservation_root.resolve(), '--mode', mode]))
        r = subprocess.run(cmd, capture_output=True, text=True)
        (out / (case.name + '.stdout')).write_text(r.stdout); (out / (case.name + '.stderr')).write_text(r.stderr)
        if r.returncode:
            (out / 'failure.json').write_text(json.dumps(dict(mode=mode, argv=cmd, exit_code=r.returncode, retries=0), indent=2) + '\n')
            print(r.stdout[-2000:], r.stderr[-2000:], flush=True)
            raise SystemExit(r.returncode)
        proof = json.loads((case / 'independent-verification.json').read_text())
        m = json.loads((case / 'execution/manifest.json').read_text())
        assert proof['status'] == 'PASS'
        row = dict(mode=mode, argv=cmd, PID=m['pid'], started=m['started_at'], completed=m['completed_at'],
            **{k:proof[k] for k in ['kernel_dispatches', 'exact_uint32_results', 'guard_bytes', 'negative_expected_words_absent']},
            manifest_SHA256=sha(case / 'execution/manifest.json'), verification_SHA256=sha(case / 'independent-verification.json'))
        history.append(row); (out / 'history.json').write_text(json.dumps(history, indent=2) + '\n')
        print(json.dumps({k:v for k,v in row.items() if k != 'argv'}), flush=True)
    assert all(a['completed'] < b['started'] for a,b in zip(history, history[1:]))
    summary = dict(status='PASS', suite=a.suite, cases=len(history), static_library_SHA256=inputs['static_library_SHA256'],
        **{k:sum(r[k] for r in history) for k in ['kernel_dispatches', 'exact_uint32_results', 'guard_bytes', 'negative_expected_words_absent']},
        public_runner_SHA256=sha(tool), qualifier_SHA256=sha(__file__), performance_benchmark=False,
        installed_driver_changed=False, full_objective_complete=False)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n'); print(json.dumps(summary), flush=True)


if __name__ == '__main__': main()
