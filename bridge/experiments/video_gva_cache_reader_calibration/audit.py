#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify cache-reader calibration and bind it to the prior video witness."""
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WITNESS = HERE.parent / 'video_gva_cache_witness'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, msg):
    if not ok: raise ValueError(msg)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('calibration', 'video-build', 'out'): p.add_argument('--'+arg, required=True, type=Path)
    a = p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    cal = json.loads((a.calibration/'calibration.json').read_text())
    build = json.loads((a.video_build/'build.json').read_text())
    sources = {'host.cpp': HERE/'host.cpp', 'invoke.S': HERE/'invoke.S', 'lldb_calibrate.py': HERE/'lldb_calibrate.py',
               'lldb_witness.py': WITNESS/'lldb_witness.py', 'marker.S': WITNESS/'marker.S', 'cpu_dylib.cpp': WITNESS/'cpu_dylib.cpp'}
    need(cal['status']=='PASS_FOUR_CPU_CACHE_READS' and cal['wrong_base_refused'] and
         cal['resolved_hardware_breakpoint_hits']==4 and not cal['gpu_execution'] and not cal['vendor_execution'], 'calibration differs')
    for name, source in sources.items():
        need(sha(source)==sha(a.calibration/name)==cal['sources_sha256'][name], 'source mismatch '+name)
    need(cal['witness_sha256']==build['frozen']['lldb_witness.py']==sha(a.video_build/'lldb_witness.py'), 'video witness differs')
    need(cal['host_sha256']==sha(a.calibration/'host') and cal['library_sha256']==sha(a.calibration/'marker.dylib') and
         cal['lldb_log_sha256']==sha(a.calibration/'lldb.stdout') and
         cal['wrong_base_log_sha256']==sha(a.calibration/'lldb-wrong-base.stdout'), 'calibration artifacts differ')
    log = (a.calibration/'lldb.stdout').read_text(); neg=(a.calibration/'lldb-wrong-base.stdout').read_text()
    rows = re.findall(r'^KP_CACHE_CHECK thread=(\d+) bytes_match=(\d+) read_ok=(\d+) first_nonzero=(\d+) prior_flag=(\d+)$', log, re.M)
    need([r[1:] for r in rows] == [('1','1','1','0'),('1','1','0','1'),('1','1','1','1'),('1','0','0','0')] and
         len({r[0] for r in rows})==1 and re.search(r'2\.1: .*resolved, hardware, hit count = 4', log) and
         'CACHE_CPU_FINISHED' in log and 'exited with status = 0' in log, 'positive log differs')
    need('KP_CACHE_CAL_FAIL base' in neg and 'KP_CACHE_CAL_ARMED' not in neg and 'KP_CACHE_CHECK ' not in neg and
         'CACHE_CPU_FINISHED' in neg and 'exited with status = 0' in neg, 'negative log differs')
    result = {'status':'PASS_CALIBRATION_BOUND_TO_PRIOR_VIDEO_WITNESS', 'cases':4, 'wrong_base_refused':True,
              'callback_source_sha256':cal['witness_sha256'], 'calibration_sha256':sha(a.calibration/'calibration.json'),
              'video_build_sha256':sha(a.video_build/'build.json'), 'auditor_sha256':sha(Path(__file__)),
              'callback_exercised_at_CPU_hardware_breakpoint':True, 'video_cached_path_hit_proved':False,
              'node_lifetime_proved':False, 'hardware_video_execution_proved':False, 'system_modified':False}
    with a.out.open('x') as f: json.dump(result,f,indent=2,sort_keys=True); f.write('\n')
    print(json.dumps({'status':result['status'], 'cases':4, 'hardware_video_execution_proved':False}))


if __name__ == '__main__': main()
