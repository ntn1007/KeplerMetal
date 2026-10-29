#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a bounded, process-local AppleGVA codec-string counterfactual."""
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--original-base', type=Path, required=True)
    p.add_argument('--runs', type=Path, nargs=6, required=True,
                   help='CPU, wrong-key, wrong-id, off, synthetic 1, synthetic 2')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    check(not a.out.exists() and a.out.parent.is_dir(), 'fresh audit output required')
    base = load(a.base/'inputs.json')
    original = load(a.original_base/'inputs.json')
    build = load(a.build/'build.json')
    check(base.get('codec_probe_variant') is True and base['original_inputs_sha256'] == sha(a.original_base/'inputs.json'), 'base provenance')
    check(base['builder_sha256'] == sha(HERE/'build.py') and base['predicate_sha256'] == sha(HERE/'predicate.h'), 'probe source provenance')
    for name, digest in original['frozen'].items():
        check(sha(a.original_base/name) == digest, 'original input: '+name)
    for name, digest in base['frozen'].items():
        check(sha(a.base/name) == digest, 'base input: '+name)
    for name, digest in build['frozen'].items():
        check(sha(a.build/name) == digest, 'build input: '+name)
    check(build['base_inputs_sha256'] == sha(a.base/'inputs.json') and build['status'] == 'PREPARED_ONLY', 'build provenance')
    root = a.base.parent
    check((root/'predicate-run.stdout').read_text().strip() == 'PASS one synthetic property predicate and nine refusals', 'predicate test')
    check((root/'cfstring-run.stdout').read_text().strip() == 'PASS CFString type ownership conversion and original preservation', 'CFString test')
    check(sha(root/'predicate_test.cpp') == sha(HERE/'predicate_test.cpp') and sha(root/'cfstring_test.cpp') == sha(HERE/'cfstring_test.cpp'), 'control sources')
    expected = [('cpu','off',0,6), ('current','wrong-key',-12913,0),
                ('current','wrong-id',-12913,0), ('current','off',-12913,0),
                ('current','synthetic',-12913,0), ('current','synthetic',-12913,0)]
    results = []
    for run, (mode, probe, status, frames) in zip(a.runs, expected):
        m = load(run/'manifest.json'); report = load(run/'stdout.json'); reservation = m['reservation']
        check((m['mode'],m['probe'],m['witness'],m['decoder_status'],m['output_frames']) == (mode,probe,'on',status,frames), f'{run.name}: mode or result')
        check(m['status']=='TERMINAL_SCOPED_DEBUGGER' and m['debugger_exit_code']==0 and m['target_exit_code']==0 and m['target_and_debugger_absent'] is True, f'{run.name}: process outcome')
        check(reservation['state']=='terminal' and reservation['child_PID']==m['debugger_pid'] and reservation['exit_code']==0 and reservation['authoritative_ps_status']=='' and not reservation['SIGKILL_requested'], f'{run.name}: reservation')
        check(m['build_sha256']==sha(a.build/'build.json') and m['runner_sha256']==sha(HERE/'run_gva.py') and m['host_sha256']==sha(run/'application')==build['frozen']['application'], f'{run.name}: provenance')
        for name, field in [('stdout.json','stdout_sha256'),('stderr.log','stderr_sha256'),('lldb.log','lldb_log_sha256')]:
            check(sha(run/name)==m[field], f'{run.name}: {name} digest')
        check(not m['hardware_video_execution_proved'] and not m['system_modified'] and report['status']=='OBSERVATION_COMPLETED' and report['codec']=='H264', f'{run.name}: report')
        dec=report['public_decode']; check(dec['decode']['create_status']==status and dec['output_frames']==frames and not dec['hardware_video_execution_proved'], f'{run.name}: decoder')
        if mode=='cpu':
            check(dec['different_bytes']==0 and dec['missing_CPU_references']==0 and dec['CPU_reference_bytes_compared']==691200, 'CPU comparison counters')
            for i in range(6):
                frame=run/'outputs'/f'vt-frame-{i:03}.nv12'; ref=a.base/'assets/fixtures/H264'/f'cpu-frame-{i:03}.nv12'
                check(frame.stat().st_size==115200 and sha(frame)==sha(ref), f'CPU frame {i}')
        else:
            injected=int(probe=='synthetic'); err=(run/'stderr.log').read_text(); log=(run/'lldb.log').read_text()
            check(err.count(f'KM_CODEC_PROBE original_null=1 injected={injected} profile=1')==1, f'{run.name}: injection')
            property_lines=[x for x in err.splitlines() if 'KM_PROPERTY offset=150812 ' in x]
            check(len(property_lines)==1 and f'present={injected} type={injected}' in property_lines[0] and 'class=nvAccelerator key=IOGVACodec options=0' in property_lines[0] and ('text=KeplerMetalProbe' in property_lines[0] if injected else 'text=NONE' in property_lines[0]), f'{run.name}: property')
            prop=[x for x in log.splitlines() if 'KP_HW_HIT name=property_return ' in x]
            nodes=[x for x in log.splitlines() if 'KP_LIST_NODE ' in x]
            links=[x for x in log.splitlines() if 'KP_HW_HIT name=list_entry ' in x]
            after=[x for x in log.splitlines() if 'KP_HW_HIT name=after_enumeration ' in x]
            check(len(prop)==1 and 'bytes_match=1' in prop[0] and f'prop_valid=1 prop_present={injected} node_flag_valid=1 node_flag=0' in prop[0], f'{run.name}: property breakpoint')
            check(len(nodes)==2 and all(f'flags=1,0,0,{injected} next_present=0' in x for x in nodes), f'{run.name}: node flags')
            check(len(links)==2 and all('bytes_match=1' in x and 'link_valid=1 same_node=1' in x for x in links), f'{run.name}: link')
            check(len(after)==1 and 'bytes_match=1' in after[0] and 'field_valid=1 field=0' in after[0], f'{run.name}: enumeration')
            threads=[re.search(r'\bthread=(\d+)',x).group(1) for x in prop+nodes+links+after]
            check(len(set(threads))==1, f'{run.name}: threads')
            check(not any(x in log for x in ('KP_GUARD_NO_PROCESS','KP_GUARD_UNRESOLVED','KP_HW_ARM_FAIL','KP_HW_HIT_FAIL')), f'{run.name}: debugger errors')
        results.append({'mode':mode,'probe':probe,'decoder_status':status,'output_frames':frames,
                        'property_injected':probe=='synthetic', 'manifest_sha256':sha(run/'manifest.json'),
                        'stdout_sha256':m['stdout_sha256'],'stderr_sha256':m['stderr_sha256'],'lldb_log_sha256':m['lldb_log_sha256']})
    receipt={'status':'PASS_BOUNDED_AUDIT','base_inputs_sha256':sha(a.base/'inputs.json'),
             'build_sha256':sha(a.build/'build.json'),'runner_sha256':sha(HERE/'run_gva.py'),
             'predicate_controls':'PASS','cfstring_control':'PASS','runs':results,
             'synthetic_value_is_nvidia_configuration':False,'hardware_video_execution_proved':False,
             'full_cause_identified':False,'limitations':'Scoped process and pinned build only; arbitrary string; allocator identity and causal branch not proved.'}
    a.out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':receipt['status'],'runs':len(results),'hardware_video_execution_proved':False}))


if __name__=='__main__':
    main()
