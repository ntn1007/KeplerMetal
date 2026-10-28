#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the retained nonprivileged NVIDIA port open/close cohort."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

SOURCE = 'c4cd20b346da1d318adc1018a789bea2caa7c57150572ba582d08608146d2c00'
BINARY = '86cf4e09ffbbd05192c02c89f5e9b53dea741ab46b2791a15f42a987a3c6075c'
RUNNER = '30812a05c96c48dc2d6ae51aaf20f0557963acfea8931cdbe8b802a23dadbbd8'
RESERVATION = 'ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248'
SIGNED = 'd057e6574e142cd7116da6a8af03186274560d06f3f0255a838c3641cd7871e7'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok, text):
    if not ok: raise ValueError(text)

def native_return(directory):
    with tempfile.TemporaryDirectory(prefix='ioret-', dir=directory) as temp:
        p, exe = Path(temp) / 'return.c', Path(temp) / 'return'
        p.write_text('#include <IOKit/IOReturn.h>\n#include <stdio.h>\n'
                     'int main(void){printf("%08x\\n",(unsigned)kIOReturnUnsupported);return 0;}\n')
        subprocess.run(['xcrun', 'clang', '-arch', 'x86_64', str(p), '-o', str(exe)],
                       check=True, capture_output=True, timeout=30)
        r = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=10)
        need(r.stdout == 'e00002c7\n', 'SDK constant')
    return '0xe00002c7'

def inspect(source, runner, build, runs, no_lease, directory):
    need(sha(source) == sha(build / 'open_probe.mm') == SOURCE and
         sha(build / 'open-probe') == BINARY and sha(runner) == RUNNER, 'frozen inputs')
    built = json.loads((build / 'build.json').read_text())
    need(built['source_sha256'] == SOURCE and built['binary_sha256'] == BINARY and
         built['compile_exit'] == 0 and not built['program_executed'], 'build evidence')
    cases = [('open', '1', 'PROFILE_REFUSED'), ('wrong-code-hash', '4294968425', 'PROFILE_REFUSED'),
             ('open', '4294968425', 'OPEN_REFUSED_NO_CONNECTION'),
             ('open', '4294968425', 'OPEN_REFUSED_NO_CONNECTION')]
    need(len(runs) == len(cases), 'expected ordered cohort')
    hosts = []
    for folder, (mode, rid, expected) in zip(runs, cases):
        m = json.loads((folder / 'manifest.json').read_text())
        data = (folder / 'execution.stdout').read_bytes(); result = json.loads(data)
        exe = folder / 'application'; lease = m['GPU_reservation']
        need(not (folder / 'execution.stderr').read_bytes() and m['arguments'] == [mode, rid] and
             m['original_binary_sha256'] == BINARY and m['signed_binary_sha256'] == sha(exe) == SIGNED and
             Path(m['signed_executable']).resolve() == exe.resolve(), 'signed process identity')
        subprocess.run(['codesign', '--verify', '--strict', str(exe)], check=True,
                       capture_output=True, timeout=15)
        need(m['runner_SHA256'] == RUNNER and m['reservation_module_SHA256'] == RESERVATION and
             m['exit_code'] == 0 and not m['SIGKILL_requested'] and not m['kill_requested'] and
             not m['authoritative_ps_status'] and lease['state'] == 'terminal' and
             lease['lock_inherited_by_child'] and lease['bootstrap_process_table_checked'] and
             not lease['known_signed_processes_live'], 'terminal reserved process')
        need(result['status'] == expected and result['mode'] == mode and result['pid'] == m['pid'] and
             result['uid'] == result['euid'] == 501 and result['lease_inherited'] and
             result['files_checked'] == 5 and result['RM_calls'] == result['GPU_dispatches'] == 0,
             'bounded result')
        if expected == 'OPEN_REFUSED_NO_CONNECTION':
            need(result['open_attempts'] == 1 and result['open_status'] == -536870201 and
                 not result['connection_returned'] and result['close_attempts'] == 0 and
                 result['matching_NVDA_services'] == 4 and result['selected_NVDA_services'] == 1 and
                 result['parent_name'] == 'NVDA,Display-A' and result['registry_id'] == int(rid) and
                 result['resident_regions_checked'] == 3 and not result['truncated'], 'open refusal')
        else:
            need(result['open_attempts'] == result['close_attempts'] == 0, 'no-open control')
            if mode == 'wrong-code-hash':
                need(not result['registry_enumerated'] and result['resident_regions_checked'] == 0,
                     'wrong code hash')
            else:
                need(result['registry_enumerated'] and result['selected_NVDA_services'] == 0, 'wrong id')
        hosts.append({'mode': mode, 'status': expected, 'pid': m['pid'],
                      'started_at': m['started_at'], 'completed_at': m['completed_at'],
                      'stdout_sha256': hashlib.sha256(data).hexdigest(),
                      'manifest_sha256': sha(folder / 'manifest.json')})
    need(all(a['completed_at'] < b['started_at'] for a,b in zip(hosts,hosts[1:])), 'ordered hosts')
    no = json.loads((no_lease / 'manifest.json').read_text())
    raw = (no_lease / 'execution.stdout').read_bytes(); result = json.loads(raw)
    need(no['status'] == 'PASS_EXPECTED_LEASE_REFUSAL' and no['binary_sha256'] == SIGNED and
         no['stdout_sha256'] == hashlib.sha256(raw).hexdigest() and no['exit_code'] == 0 and
         no['process_absent'] and result['pid'] == no['pid'] and result['status'] == 'LEASE_REQUIRED' and
         result['open_attempts'] == result['RM_calls'] == result['GPU_dispatches'] == 0,
         'missing lease refusal')
    return {'status': 'PASS_BOUNDED_OPEN_OBSERVATION', 'source_sha256': SOURCE,
            'binary_sha256': BINARY, 'signed_sha256': SIGNED, 'runner_sha256': RUNNER,
            'hosts': hosts, 'missing_lease_pid': no['pid'], 'uid': 501,
            'open_attempts': 2, 'connections_returned': 0, 'RM_calls': 0, 'GPU_dispatches': 0,
            'open_status_hex': native_return(directory),
            'scope': 'Two current-profile refusals only; unsupported return does not identify the cause or establish current administrator behavior.'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('source', 'runner', 'build', 'no-lease', 'out'): p.add_argument('--'+arg, type=Path, required=True)
    p.add_argument('--runs', nargs=4, type=Path, required=True)
    a = p.parse_args(); need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output')
    result = inspect(a.source, a.runner, a.build, a.runs, a.no_lease, a.out.parent)
    with a.out.open('x') as f: json.dump(result, f, indent=2, sort_keys=True); f.write('\n')
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__': main()
