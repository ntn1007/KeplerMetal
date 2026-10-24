#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute owned-code binding/readback observations and missing-copy controls."""
from pathlib import Path
import argparse
import hashlib
from public_large_scratch import read,sha,write
from public_native_command_binding import CASES
from verify_native_command_binding import verify
from verify_native_command_boundary import verify as verify_reference


def relative_call(word,pc):
    """One direct SM30 CALL encoding; not a general instruction decoder.

    Field/opcode reference: envytools gf100.c at f102b82381f3f11cee113d16374c87091db039d9.
    """
    assert type(word)is int and 0<=word<1<<64 and type(pc)is int and pc>=0 and pc%8==0
    if word&0xf800000000004007!=0x5000000000000007:return None
    value=(word>>26)&0xffffff
    displacement=value-(1<<24)if value&(1<<23)else value
    return dict(PC=pc,displacement=displacement,target=pc+8+displacement,kind='PC_relative_CALL')


def audit(root,build,reference):
    root,build,reference=(Path(p).resolve()for p in(root,build,reference))
    m=read(build/'inputs.json');rows=[];intervals=[];cases=set();matches=misses=guard_bytes=code_bytes=0
    changed=identity_changed=encoded=blits=copy_blits=0;reference_programs={};resident_entry_calls=0
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_native_command_binding import verify;print(json.dumps(verify(sys.argv[2])))'
    plans=[('no-copy','readback_no_copy',('pointer_control','raw_render_reset','raw_render_reset_witness','raw_render_vertex_witness')),
           ('inspect','inspect',CASES),('encode','encode',CASES),('readback-0','readback',CASES),('readback-1','readback',CASES)]
    for group,mode,names in plans:
        for name in names:
            p=root/group/name;proof=verify(p);receipt=read(p/'execution/manifest.json');inputs=read(p/'inputs.json')
            assert inputs==dict(m,case=name,mode=mode,driver_SHA256=inputs['driver_SHA256'],source_build_inputs_SHA256=sha(build/'inputs.json'))
            assert read(p/'independent-verification.json')==dict(proof,PID=receipt['pid'])
            checked=read(p/'verification-execution.json');assert checked['exit_code']==0 and checked['isolated_interpreter']is True
            assert checked['argv'][1:]==['-I','-c',code,str(p/'oracles'),str(p)]and checked['code_SHA256']==hashlib.sha256(code.encode()).hexdigest()
            assert read(p/'verification.stdout')==proof and not(p/'verification.stderr').read_text()
            d=read(p/'results.json');assert proof['code_buffer_storage_modes']==[2]*proof['CPU_code_stages']
            if name not in reference_programs:reference_programs[name]=verify_reference(reference/name)['native_constructor_programs'][0]['code_SHA256']
            assert proof['constructor_code_SHA256']==reference_programs[name]
            old=read(reference/name/'inputs.json')
            assert old['frozen']['assets/'+name+'.metallib']==inputs['frozen']['assets/'+name+'.metallib']
            assert old['driver_SHA256']==inputs['driver_SHA256']
            changed+=proof['CPU_code_changed_after_construction'];encoded+=proof['encoded_uncommitted_dispatches'];blits+=proof['committed_blit_CBs']
            identities={(s['code_GPU_address'],s['code_buffer_GPU_address'],s['code_buffer_offset'],s['code_buffer_length'])for s in d['CPU_snapshots']}
            identity_changed+=len(identities)>1
            if mode=='readback':
                matches+=sum(proof['resident_readbacks_match_CPU']);misses+=2-sum(proof['resident_readbacks_match_CPU']);copy_blits+=2
                code_bytes+=sum(row['code_bytes']for row in d['readbacks'])
                for row in d['readbacks']:
                    data=(p/'outputs'/row['file']).read_bytes()[64:-64]
                    import struct
                    call=relative_call(struct.unpack_from('<Q',data,8)[0],8)
                    if name.startswith('raw_'):
                        assert call==dict(PC=8,displacement=-16,target=0,kind='PC_relative_CALL')
                        resident_entry_calls+=1
                    else:assert call is None
            if mode.startswith('readback'):guard_bytes+=128*len(d['readbacks'])
            rows.append(dict(group=group,PID=receipt['pid'],**{k:v for k,v in proof.items()if k!='files_SHA256'}))
            intervals.append((receipt['started_at'],receipt['completed_at']));cases.add(name)
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    assert cases==set(CASES)
    for name in CASES:
        for stage in ['before-binding','after-encoding']:
            a=(root/'readback-0'/name/'outputs'/(stage+'.resident-readback.bin')).read_bytes()
            b=(root/'readback-1'/name/'outputs'/(stage+'.resident-readback.bin')).read_bytes()
            assert a==b,(name,stage)
    return dict(status='PASS_BINDING_OBSERVATIONS',signed_terminal_nonoverlapping_processes=len(rows),
        shader_cases=len(cases),encoded_uncommitted_compute_CBs=encoded,submitted_compute_dispatches=0,
        committed_blit_CBs=blits,blit_CBs_with_copy=copy_blits,blit_CBs_without_copy=blits-copy_blits,
        resident_CPU_matches=matches,resident_CPU_mismatches=misses,code_bytes_compared=code_bytes,
        readback_guard_bytes=guard_bytes,CPU_code_changes=changed,code_buffer_identity_changes=identity_changed,
        post_bind_QMDs_checked=encoded,repeat_readback_file_pairs=28,private_code_buffers=True,
        resident_PC_relative_calls_to_program_entry=resident_entry_calls,
        native_ICB_execution_qualified=False,commit_time_rewriting_excluded=False,
        performance_benchmark=False,full_objective_complete=False,cases=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path)
    for name in ['build','reference','out']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=audit(a.root,a.build,a.reference);write(a.out,r);print({k:v for k,v in r.items()if k!='cases'})
