#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit compiler observations; no shader or command is executed on a GPU."""
from pathlib import Path
import argparse
import hashlib
import re
from public_large_scratch import read,sha,write
from verify_native_command_boundary import verify

OPERATIONS={
    'compute_reset':'air.reset_compute_command','render_reset':'air.reset_render_command',
    'compute_copy':'air.copy_compute_command','render_copy':'air.copy_render_command',
    'render_draw':'air.draw_primitives_render_command','render_vertex':'air.set_vertex_buffer_render_command.p1i8'}


def audit(root,build,observation):
    root,build,observation=(Path(p).resolve()for p in(root,build,observation))
    m=read(build/'inputs.json');assert m['capture_native_code']is True and m['post_constructor_code']is True
    assert len(m['frontends'])==16 and all(r['exit_code']==0 for r in m['frontends'].values())
    rows=[];intervals=[];raw_hashes=set();witness_hashes={};typed=[];common=set()
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_native_command_boundary import verify;print(json.dumps(verify(sys.argv[2])))'
    for case in m['frontends']:
        path=root/case;proof=verify(path);receipt=read(path/'execution/manifest.json');inputs=read(path/'inputs.json')
        assert inputs==dict(m,case=case,driver_SHA256=inputs['driver_SHA256'],source_build_inputs_SHA256=sha(build/'inputs.json'))
        saved=read(path/'independent-verification.json')
        assert saved==dict(proof,PID=receipt['pid'])
        checked=read(path/'verification-execution.json');assert checked['exit_code']==0 and checked['isolated_interpreter']is True
        assert checked['argv'][1:]==['-I','-c',code,str(path/'oracles'),str(path)]
        assert checked['code_SHA256']==hashlib.sha256(code.encode()).hexdigest()
        assert read(path/'verification.stdout')==proof and not(path/'verification.stderr').read_text()
        for program in proof['native_constructor_programs']:assert program['post_constructor_CPU_copy_identical']is True
        rows.append(dict(proof,PID=receipt['pid']));intervals.append((receipt['started_at'],receipt['completed_at']))
        ir=(path/'assets'/(case+'.ll')).read_text()
        if case.startswith('typed_'):
            assert proof['classification']=='command_argument_metadata_refused'
            actual=read(path/'results.json')
            assert actual['error_domain']=='CompilerError'and actual['error_code']==2
            assert actual['encoder_created']is True and actual['encoder_length']==0
            assert '!"air.command_buffer"'in ir and '!"air.indirect_buffer"'in ir
            typed.append(case)
        else:
            assert proof['pipeline_created']is True and '!"air.indirect_buffer"'not in ir and '!"air.command_buffer"'not in ir
        if case.startswith('raw_'):
            key=case[4:].removesuffix('_witness');symbol=OPERATIONS[key]
            calls=[line for line in ir.splitlines()if re.search(r'\bcall\b.*@'+re.escape(symbol)+r'\(',line)]
            assert len(calls)==1,(case,calls)
            program=proof['native_constructor_programs'][0]
            if case.endswith('_witness'):witness_hashes[key]=program['code_SHA256']
            else:raw_hashes.add(program['code_SHA256'])
            assert program['code_bytes']==(128 if case.endswith('_witness')else 64)
        if (observation/case/'inputs.json').is_file():
            common.add(case)
            prior=verify(observation/case)
            for field in ['classification','pipeline_created','pipeline_error','library_SHA256']:assert prior[field]==proof[field]
    assert {'pointer_control','typed_compute_reset','typed_render_reset',*('raw_'+key for key in OPERATIONS)}<=common
    assert len(typed)==2 and len(raw_hashes)==1 and len(witness_hashes)==6
    shared={digest for key,digest in witness_hashes.items()if key!='render_vertex'}
    assert len(shared)==1 and witness_hashes['render_vertex']not in shared
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    control=verify(root/'witness_control')['native_constructor_programs'][0]
    assert control['code_bytes']==192 and control['code_SHA256']not in witness_hashes.values()
    return dict(status='PASS_CONSTRUCTION_OBSERVATIONS',signed_terminal_nonoverlapping_processes=len(rows),
        typed_command_metadata_refusals=len(typed),native_pipelines_created=14,post_constructor_CPU_code_comparisons=14,
        raw_command_operations=len(OPERATIONS),noninterposed_observation_pairs=len(common),raw_main_code_bytes=64,witness_main_code_bytes=128,
        witness_control_code_bytes=192,identical_raw_main_code_SHA256=next(iter(raw_hashes)),
        five_command_witness_code_SHA256=next(iter(shared)),
        vertex_command_witness_code_SHA256=witness_hashes['render_vertex'],
        witness_control_code_SHA256=control['code_SHA256'],
        raw_native_ABI_or_late_linking_qualified=False,GPU_dispatches=0,GPU_execution_proved=False,
        performance_benchmark=False,full_objective_complete=False,cases=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    for name in ['build','observation','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=audit(a.root,a.build,a.observation);write(a.out,r);print({k:v for k,v in r.items()if k!='cases'})
