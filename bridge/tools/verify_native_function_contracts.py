#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit source-lowered function registration and native-factory controls."""
from pathlib import Path
import hashlib,json
from verify_local_memory import verify_device_identity
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
CASES=['refuse_'+s for s in ['empty','hash','index','missing','old_opaque','wrong_token',
    'wrong_context_type','wrong_context_size','wrong_context_access','missing_context',
    'missing_slot','extra_slot']]+['immutable_registration','adapted_getter_native_reflection','reverse_ABI_refused','legacy_getters_coexist']+[
    'native_factory_'+str(i) for i in range(6)]+['inactive_encoder_refused','native_getters_restored','inactive_registration_refused']

def verify(root):
    root=Path(root);d=json.loads((root/'results.json').read_text());inp=json.loads((root/'inputs.json').read_text());m=json.loads((root/'execution/manifest.json').read_text())
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
    assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
    assert sha(root/'execution/application')==m['signed_binary_sha256']
    for key,folder in [('source_hashes',''),('assets_SHA256','assets'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles')]:
        for name,digest in inp[key].items():assert sha(root/folder/name)==digest
    verify_device_identity(d)
    assert d['status']=='PASS' and d['scope_restored'] and not d['system_modified'] and not d['instruction_import']
    assert d['GPU_command_buffers']==d['GPU_dispatches']==0
    assert [c['case']for c in d['cases']]==CASES and all(c['PASS']for c in d['cases'])
    assert len(d['factories'])==6
    for i,f in enumerate(d['factories']):
        assert f['variant']==i and f['PASS'] and f['class']=='NVMTLComputePipelineState' and not f['error']
        assert f['native_reflection']==(i not in [0,3])
    events=d['events'];registrations=[e for e in events if e.get('operation')=='register_native_source_IRv2_function']
    assert len(registrations)==1 and registrations[0]['library_SHA256']==inp['assets_SHA256']['native_producer.metallib']
    assert not any(e.get('operation')in ['register_native_IRv2_producer','new_registered_IRv2_pipeline']for e in events)
    assert len([e for e in events if e.get('operation')=='restore_IRv2_functions' and e['live_functions_restored']==2])==1
    return dict(status='PASS',contract_cases=len(CASES),expected_refusals=15,native_pipeline_factory_variants=6,GPU_dispatches=0,full_objective_complete=False)
