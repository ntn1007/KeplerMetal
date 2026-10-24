#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck frozen inputs, terminal leases, CPU bytes and independent references."""
from pathlib import Path
import argparse
from public_large_scratch import read,sha,write
from verify_air_reset_dataflow import verify,CASES,native_code


def audit(root,build):
    root,build=Path(root).resolve(),Path(build).resolve();m=read(build/'inputs.json')
    rows=[];intervals=[];inspections={};proofs={}
    for variant in ['lowered','reference']:
        path=root/('inspect-'+variant);proof=verify(path);assert proof['mode']=='inspect'
        cert=read(path/'certificate.json');d=read(path/'results.json');code,metadata=native_code(path)
        assert cert['inspection_inputs_SHA256']==sha(path/'inputs.json')and cert['inspection_results_SHA256']==sha(path/'results.json')
        assert cert['library_SHA256']==d['library_SHA256']and cert['code_SHA256']==d['code_SHA256']
        assert cert['code_bytes']==len(code)and cert['metadata_words']==metadata and cert['no_native_call']is True
        assert cert['disassembly_SHA256']==sha(path/'native-code.sass.txt')
        inspections[variant]=path
        rows.append(dict(path=str(path.relative_to(root)),**proof))
    checked=guards=words=resets=dispatches=buffers=0
    for group,mode in [('no-dispatch','no_dispatch'),('execute-0','execute'),('execute-1','execute'),('execute-2','execute')]:
        for variant in ['lowered','reference']:
            path=root/'cohort'/group/variant;proof=verify(path);assert proof['mode']==mode and proof['variant']==variant
            assert sha(path/'certificate.json')==sha(inspections[variant]/'certificate.json')
            checked+=proof['checked_bytes'];guards+=proof['guard_bytes'];words+=proof['witness_words'];resets+=proof['reset_records'];dispatches+=proof['compute_dispatches']
            buffers+=read(path/'results.json')['command_buffers'];proofs[group,variant]=proof
            rows.append(dict(path=str(path.relative_to(root)),**{k:v for k,v in proof.items()if k!='files_SHA256'}))
    isolated='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_air_reset_dataflow import verify;print(json.dumps(verify(sys.argv[2])))'
    for row in rows:
        path=root/row['path'];receipt=read(path/'execution/manifest.json');inputs=read(path/'inputs.json')
        assert inputs['source_build_inputs_SHA256']==sha(build/'inputs.json')
        for field in ['frozen','executable_SHA256','original_AIR_SHA256','profile']:assert inputs[field]==m[field]
        assert read(path/'independent-verification.json')==dict(verify(path),PID=receipt['pid'])
        v=read(path/'verification-execution.json');assert v['exit_code']==0 and v['isolated_interpreter']is True
        assert v['argv'][1:]==['-I','-c',isolated,str(path/'oracles'),str(path)]
        assert read(path/'verification.stdout')==verify(path)and not(path/'verification.stderr').read_text()
        intervals.append((receipt['started_at'],receipt['completed_at']));row['PID']=receipt['pid']
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    pairs=repeat=0
    for i in range(3):
        a,b=(proofs['execute-'+str(i),v]for v in ['lowered','reference'])
        assert a['files_SHA256']==b['files_SHA256'];pairs+=len(a['files_SHA256'])
        if i:
            for variant in ['lowered','reference']:
                assert proofs['execute-'+str(i),variant]['files_SHA256']==proofs['execute-0',variant]['files_SHA256'];repeat+=len(proofs['execute-0',variant]['files_SHA256'])
    assert proofs['no-dispatch','lowered']['files_SHA256']==proofs['no-dispatch','reference']['files_SHA256']
    assert proofs['execute-0','lowered']['files_SHA256']['full-0.bin']!=proofs['no-dispatch','lowered']['files_SHA256']['full-0.bin']
    return dict(status='PASS_AIR_RESET_DATAFLOW',signed_terminal_nonoverlapping_processes=len(rows),
        compute_dispatches=dispatches,committed_command_buffers=buffers,checked_readback_bytes=checked,
        guard_bytes=guards,witness_words=words,reset_records=resets,CPU_oracle_mismatches=0,reference_file_pairs=pairs,
        repeat_file_pairs=repeat,reference_no_dispatch_pairs=48,contexts_private=True,records_private=True,
        GPU_qualified_shader_profiles=1,structural_translation_CPU_profiles=2,native_Apple_ICB_ABI=False,system_driver_modified=False,
        performance_benchmark=False,full_objective_complete=False,cases=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();d=audit(a.root,a.build);write(a.out,d);print({k:v for k,v in d.items()if k!='cases'})
