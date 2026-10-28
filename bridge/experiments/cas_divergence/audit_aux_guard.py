#!/usr/bin/env python3
"""Audit a constructor-level auxiliary mismatch and accepted GPU imports."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from run_repair import PINS,SYSTEM


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('build','negative-build','negative-run','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--positive-runs',nargs=2,type=Path,required=True);a=p.parse_args()
    build=a.build.resolve();bad=a.negative_build.resolve();run=a.negative_run.resolve();out=a.out.resolve()
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    original=(build/'src/KeplerConditionalAux.h').read_bytes();modified=(bad/'src/KeplerConditionalAux.h').read_bytes()
    needle=b'0x6b,0x67,0x31,0xdc';replace=b'0x6a,0x67,0x31,0xdc'
    need(original.count(needle)==1 and modified==original.replace(needle,replace),'test pin mutation differs')
    native_source=Path(__file__).resolve().parents[2]/'src/KeplerNativeCAS.mm'
    header_source=native_source.with_name('KeplerConditionalAux.h')
    need(sha(build/'import.mm')==sha(native_source) and sha(build/'src/KeplerConditionalAux.h')==sha(header_source) and
         sha(bad/'import.mm')==sha(native_source),'compiled source differs')
    m=json.loads((run/'manifest.json').read_text());r=json.loads((run/'report.json').read_text())
    nb=json.loads((bad/'negative-build.json').read_text());sdk=json.loads((bad/'sdk-build.json').read_text())
    need(nb['mode']=='wrong-expected-aux-digest' and nb['original_header_SHA256']==sha(header_source) and
         nb['test_header_SHA256']==sha(bad/'src/KeplerConditionalAux.h') and
         nb['test_host_SHA256']==sdk['host_SHA256']==sha(bad/'host-sdk') and
         nb['native_input_modified'] is False and nb['GPU_dispatch'] is False,'negative build differs')
    need(m['test_mode']=='negative-aux' and m['exit_code']==4 and m['GPU_reservation']['state']=='terminal' and
         not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and
         m['system_before']==m['system_after']==SYSTEM and m['SDK_build_SHA256']==sha(bad/'sdk-build.json') and
         m['original_binary_sha256']==sdk['host_SHA256'] and m['signed_binary_sha256']==sha(run/'application') and
         sha(run/'shader.metallib')==PINS['shader.metallib'],'negative manifest differs')
    need(subprocess.run(['codesign','--verify','--strict',str(run/'application')],capture_output=True,timeout=15).returncode==0,
         'negative signature differs')
    proof=r['import'];native=proof['native_import'];events=native['events']
    need(r['mode']=='repaired' and not r['GPU_dispatch'] and r['failure_stage']=='pipeline' and
         proof['gate_accepted'] and proof['constructor_restored'] and native['rejected_import'] and
         not native['contract_verified'] and len(events)==1 and
         events[0]['conditional_auxiliary_section_pinned'] is False and
         events[0]['code_replaced'] is False and not any((run/'outputs').iterdir()),'negative evidence differs')
    positives=[]
    for directory in a.positive_runs:
        report=json.loads((directory/'report.json').read_text());manifest=json.loads((directory/'manifest.json').read_text())
        proof=report['import'];native=proof['native_import'];events=native['events']
        need(manifest['test_mode']=='repaired' and manifest['exit_code']==0 and
             manifest['GPU_reservation']['state']=='terminal' and not manifest['authoritative_ps_status'] and
             manifest['system_before']==manifest['system_after']==SYSTEM and report['GPU_dispatch'] and
             proof['gate_accepted'] and proof['constructor_restored'] and native['contract_verified'] and
             len(events)==1 and events[0]['conditional_auxiliary_section_pinned'] is True and
             events[0]['code_replaced'] is True,'accepted aux evidence differs')
        positives.append({'signed_executable_sha256':sha(directory/'application'),
                          'report_sha256':sha(directory/'report.json'), 'live_aux_matched':True})
    result={'status':'PASS','positive_imports':positives,'negative':{'test':'wrong expected auxiliary digest',
            'actual_native_input_mutated':False,'live_aux_mismatch_rejected':True,'code_replaced':False,
            'GPU_dispatch':False,'constructor_restored':True},
            'gate_source_sha256':sha(header_source),'native_import_source_sha256':sha(native_source),
            'bank_c0_binding_proved':False,'resident_GPU_instruction_readback':False}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))


if __name__=='__main__':main()
