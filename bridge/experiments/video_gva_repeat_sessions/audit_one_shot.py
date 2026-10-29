#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit one failed CPU repetition and the pre-existing one-shot guard."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok, why):
    if not ok: raise ValueError(why)


def static_guard(data):
    need(hashlib.sha256(data).hexdigest() == 'f5a4845045975c9deba0aca80c42d5a2216c64b72f37d234d3935b6a97f45db4', 'source pin differs')
    text=data.decode()
    need(text.count('NSDictionary *pins=begun.exchange(true)?nil:prepare(@(argv[1]));bool calibrated=false;')==1 and
         text.count('OSStatus status=(pins&&calibrated&&(!apply||modified))?VTDecompressionSessionCreate(')==1 and
         text.count('allocator,format,forwarded,attributes,callback,session):(OSStatus)-50;')==1,
         'guard sequence differs')
    return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('base','build','run','reconciliation','out'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    base=json.loads((a.base/'inputs.json').read_text());build=json.loads((a.build/'build.json').read_text())
    source=a.base/'video_dependency.mm';need(sha(source)==base['frozen']['video_dependency.mm'] and static_guard(source.read_bytes()),'source provenance differs')
    need(build['repeat_variant'] and build['base_inputs_sha256']==sha(a.base/'inputs.json') and
         sha(a.run/'application')==build['frozen']['application'],'variant differs')
    variant=a.build/'registry-repeated.mm'
    need(sha(variant)==build['variant_source_sha256'] and 'if(!extra)return 10;[additional addObject:extra];' in variant.read_text(), 'repeat source differs')
    for index in range(6):
        ref=a.run/'assets/fixtures/H264'/('cpu-frame-%03d.nv12' % index)
        got=a.run/'outputs'/('vt-frame-%03d.nv12' % index)
        need(ref.stat().st_size == 115200 and sha(ref)==sha(got), 'first CPU frame differs')
    log=(a.run/'lldb.log').read_text();err=(a.run/'stderr.log').read_text()
    rec=json.loads(a.reconciliation.read_text());e=rec['evidence'];old=rec['preserved_prior_state']
    need(e['status']=='CPU_SESSION_TERMINAL_RECONCILED' and e['target_exit_code']==10 and
         e['target_debugger_and_owner_absent'] and not e['prior_kill_requested'] and
         e['lldb_log_sha256']==sha(a.run/'lldb.log') and e['stderr_sha256']==sha(a.run/'stderr.log') and
         e['host_sha256']==sha(a.run/'application') and old['state']=='unresolved','reconciliation differs')
    need(re.search(r'^KP_PROCESS_EXITED pid=\d+ code=10$',log,re.M) and
         any(x.startswith('(lldb) settings set target.run-args ') and x.endswith(' "cpu"') for x in log.splitlines()) and
         re.findall(r'^KP_REPEAT_(BEGIN|END) request=(\d+)$',err,re.M)==[('BEGIN','1'),('END','1'),('BEGIN','2'),('END','2')],
         'failed run differs')
    result={'status':'PASS_RETAINED_CPU_FAILURE_AND_ONE_SHOT_AUDIT',
            'source_sha256':sha(source),'base_inputs_sha256':sha(a.base/'inputs.json'),
            'build_sha256':sha(a.build/'build.json'),'failed_log_sha256':sha(a.run/'lldb.log'),
            'reconciliation_sha256':sha(a.reconciliation),'audit_source_sha256':sha(Path(__file__)),
            'first_request_returned':True,'first_request_cpu_reference_bytes_matched':691200,'second_helper_returned_nil':True,'third_request_started':False,
            'one_shot_guard_statically_confirmed':True,'guard_proved_cause_of_helper_nil':False,
            'second_session_creation_proved':False,'hardware_video_execution_proved':False,
            'new_gpu_video_request':False,'system_modified':False}
    with a.out.open('x') as f: json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'second_helper_nil_cause_proved':False}))


if __name__=='__main__': main()
