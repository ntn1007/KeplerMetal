#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the native producer matrix, record bytes and prior NAK controls."""
from pathlib import Path
import argparse
import json
from public_large_scratch import read,sha
from public_native_msl_commands import FLOW_MODES,FUNCTION_FLOW_MODES,msl_abi,lower_readonly_members
import verify_native_msl_records
import verify_command_ir_dataflow
import verify_native_function_contracts


def audit(root,*,function_arguments=False):
    root=Path(root);expected={f'native-{m}':('dataflow',m)for m in (FUNCTION_FLOW_MODES if function_arguments else FLOW_MODES)}
    expected.update({f'nak-{m}':('nak',m)for m in ['basic','barrier','copy']})
    expected.update({'records-execute-0':('records','execute'),'records-execute-1':('records','execute'),
                     'records-no_dispatch':('records','no_dispatch')})
    if function_arguments:
        expected.update({f'contracts-{i}':('contracts','inspect')for i in range(2)})
        expected.update({f'nak-function-{m}':('nak_function',m)for m in ['basic','barrier','copy']})
    assert {p.name for p in root.iterdir()if p.is_dir()}==set(expected)
    results=[];intervals=[];libraries=set()
    for label,(kind,mode)in expected.items():
        path=root/label;inp=read(path/'inputs.json');m=read(path/'execution/manifest.json');d=read(path/'results.json')
        assert inp['kind']==kind and inp['mode']==mode
        if kind=='dataflow':assert bool(inp.get('native_function_arguments'))==function_arguments
        assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
        assert sha(path/'application')==inp['executable_SHA256']==m['original_binary_sha256']
        assert sha(path/'execution/application')==m['signed_binary_sha256']
        for key,folder in [('source_hashes',''),('assets_SHA256','assets'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
            for name,digest in inp[key].items():assert sha(path/folder/name)==digest
        assert (path/'include/KeplerCommandIR.h').read_text()==msl_abi((path/'src/KeplerCommandIR.h').read_text())
        for source,profile in [('gpu_command_frontend_dataflow',{'parameters':('uint',4)}),('native_command_records_probe',{'constants':('uint',3)})]:
            assert (path/'lowered'/(source+'.metal')).read_text()==lower_readonly_members((path/'src'/(source+'.metal')).read_text(),profile)
        proof=(verify_native_function_contracts.verify(path)if kind=='contracts'else verify_native_msl_records.verify(path)if kind=='records'else verify_command_ir_dataflow.verify(path))
        saved=read(path/'independent-verification.json')
        for key,value in proof.items():assert saved[key]==value,(label,key)
        if kind not in ['records','contracts']:assert d['producer_backend']==('native_msl'if kind=='dataflow'else'NAK')
        if kind=='nak_function':
            assert d['function_argument_encoder'] and d['public_argument_encoder']
            events=d['function_events'];registered=[e for e in events if e.get('operation')=='register_native_IRv2_function']
            assert len(registered)==1 and registered[0]['library_SHA256']=='a9367d4492cd100adfcde990efe0b043e4b070536a3615be5b9b2f63bfb473db'
            assert [(m['type'],m['offset'],m['index'])for m in registered[0]['schema']['members']]==[(t,i*8,i)for i,t in enumerate([80,79,60,60,60,60])]
            assert not any(e.get('operation')=='register_native_source_IRv2_function'for e in events)
            getters=[e for e in events if e.get('operation')=='function_IRv2_argument_encoder']
            assert len(getters)==4 and sum(e['reflection_requested']for e in getters)==2
            assert len([e for e in events if e.get('operation')=='restore_IRv2_functions'and e['live_functions_restored']==1])==1
            assert all(len([e for e in r['events']if e.get('operation')=='encode_public_IRv2_arguments'])==4 for r in d['runs'])
        libraries.add(inp['static_library_SHA256']);intervals.append((m['started_at'],m['completed_at']))
        results.append(dict(case=label,kind=kind,**{k:v for k,v in proof.items()if k!='raw_SHA256'}))
    assert len(libraries)==1;intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    pairs=0;legacy_pairs=0
    for mode in ['basic','barrier','copy']:
        for trial in range(4):
            for field in ['stage0','stage1','stage2','counter']:
                name=f'trial-{trial}-{field}.bin'
                assert (root/f'native-{mode}/outputs'/name).read_bytes()==(root/f'nak-{mode}/outputs'/name).read_bytes();pairs+=1
                if function_arguments:
                    assert (root/f'native-{mode}/outputs'/name).read_bytes()==(root/f'nak-function-{mode}/outputs'/name).read_bytes();legacy_pairs+=1
    native=[r for r in results if r['kind']=='dataflow'];nak=[r for r in results if r['kind']=='nak'];record=[r for r in results if r['kind']=='records']
    report=dict(status='PASS',signed_terminal_nonoverlapping_processes=len(results),static_library_SHA256=next(iter(libraries)),
        native_dataflow_processes=len(native),native_exact_consumer_uint32=sum(r['exact_uint32_results']for r in native),
        native_consumer_invocations=sum(r['consumer_invocations']for r in native),
        native_dataflow_guard_bytes=sum(r['guard_bytes']for r in native),API_refusals=sum(r['API_refusals']for r in native),
        NAK_baseline_processes=len(nak),NAK_baseline_consumer_uint32=sum(r['exact_uint32_results']for r in nak),
        native_NAK_identical_stage_counter_files=pairs,record_test_processes=len(record),
        record_test_dispatches=sum(r['user_dispatches']for r in record),record_test_cases=sum(r['cases']for r in record),
        record_data_bytes=sum(r['record_data_bytes']for r in record),record_guard_bytes=sum(r['guard_bytes']for r in record),
        native_producer_instruction_import=False,Apple_native_ICB_layout=False,core_runtime_modified=function_arguments,
        performance_benchmark=False,full_objective_complete=False,cases=results)
    if function_arguments:
        contracts=[r for r in results if r['kind']=='contracts'];legacy=[r for r in results if r['kind']=='nak_function']
        report.update(native_function_arguments=True,contract_processes=len(contracts),
            contract_cases=sum(r['contract_cases']for r in contracts),
            contract_expected_refusals=sum(r['expected_refusals']for r in contracts),
            native_pipeline_factory_variants_per_process=6,legacy_function_processes=len(legacy),
            legacy_function_exact_consumer_uint32=sum(r['exact_uint32_results']for r in legacy),
            native_legacy_function_identical_stage_counter_files=legacy_pairs)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--out',type=Path);p.add_argument('--function-arguments',action='store_true');a=p.parse_args();r=audit(a.root,function_arguments=a.function_arguments)
    if a.out:
        with a.out.open('x')as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in r.items()if k!='cases'},indent=2))
