#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify a bounded video context/shared-client association witness offline."""
from pathlib import Path
import hashlib,json,sys

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(path):
    p=Path(path).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode']
    assert mode in ('inventory','wrong-target','pair','attach','owner-map-close')
    assert r==read(p/'execution/execution.stdout') and m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live']
    assert r['pid']==m['pid'] and r['uid']==r['euid']==i['user_UID']!=0
    assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256']
    assert sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in i['frozen'].items():assert sha(p/name)==digest,name
    assert m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py']
    expected='pair' if mode=='wrong-target' else mode
    assert m['arguments']==[expected,str(i['registry_id'])] and r['mode']==expected and r['target']==i['registry_id']
    assert r['creator_parser_calibrated']
    assert not r['matching_status'] and not r['truncated'] and not r['explicit_selector_calls'] and not r['explicit_GPU_commands'] and not r['hardware_video_execution_proved']
    devs=[v for v in r['services'] if v['class']=='nvAccelerator' and v['gpu_ancestor'] and not v['class_status'] and not v['registry_status']]
    assert len(devs)==1 and devs[0]['pci_registry_ID']
    if mode in ('inventory','wrong-target'):
        assert not r['candidate_count'] and not r['metal_enumeration_attempted'] and not r['context_open_attempts'] and not r['shared_open_attempts'] and not r['association_attempts']
        assert not r.get('map1_attempts',0) and not r.get('map2_attempts',0)
        assert not r['context_returned'] and not r['shared_returned'] and not r['context_close_attempts'] and not r['shared_close_attempts']
        assert r['status']==('INVENTORY_ONLY' if mode=='inventory' else 'TARGET_NOT_QUALIFIED')
        if mode=='wrong-target':assert i['registry_id']==1
        outcome='CONTROL_PASS'
    else:
        assert r['candidate_count']==1 and devs[0]['candidate'] and i['registry_id']==devs[0]['registry_ID']
        assert r['pci_registry_ID']==devs[0]['pci_registry_ID']==r['metal_pci_registry_ID']
        assert r['metal_enumeration_attempted'] and r['metal_candidates']==1 and r['metal_registry_ID']
        assert r['context_open_attempts']==r['shared_open_attempts']==1 and r['context_open_status']==r['shared_open_status']==0
        assert r['context_returned'] and r['shared_returned'] and r['handles_distinct']
        assert r['context_close_attempts']==r['shared_close_attempts']==1 and r['context_close_status']==r['shared_close_status']==0
        if mode=='pair':
            assert r['status']=='PAIR_OPEN' and not r['association_attempts'];outcome='PAIR_OPEN_CLOSED'
        else:
            assert r['association_attempts']==1
            if r['association_status']!=0:assert r['status']=='ASSOCIATION_REFUSED';outcome='ASSOCIATION_REFUSED'
            elif mode=='attach':assert r['status']=='ASSOCIATION_ACCEPTED';outcome='ASSOCIATION_ACCEPTED'
            else:
                assert r['owner_qualified'] and r['owner_registry_ID'] and not r['mapping_contents_read_or_written'] and not r['explicit_unmap_calls'] and r['map2_attempts']==1
                owner=r['owner_registry_ID']
                for phase in ('before','after_open','after_associate','after_context_close','after_shared_close'):
                    snap=r['registry_'+phase];assert snap['status']==0 and not snap['truncated'] and snap['iterator_valid'] and 1<=snap['attempts']<=3
                    assert all(e['id_status']==0 and e['class_status']==0 and e['id'] and e['class']=='nvVideoContext' and all(isinstance(e[k],bool) for k in ('creator_present','creator_is_string','creator_matches_self_pid')) for e in snap['contexts'])
                    own=[e for e in snap['contexts'] if e['id']==owner and e['creator_matches_self_pid']]
                    if phase in ('after_open','after_associate'):assert len(own)==1
                    else:assert all(e['id']!=owner for e in snap['contexts'])
                assert r['mapping_ranges_disjoint']
                assert r['status'] in ('OWNER_MAP_COVERAGE_RECORDED','MAP_REFUSED_OR_INVALID')
                if r['map2_returned']:
                    assert r['map2_status']==0 and r['map2_bytes']==4096
                    assert r['map1_attempts']==1
                else:assert r['status']=='MAP_REFUSED_OR_INVALID' and not r.get('map1_attempts',0)
                for typ in (1,2):
                    if r.get('map%d_returned'%typ):
                        assert r['map%d_status'%typ]==0 and r['map%d_bytes'%typ]==4096
                        for phase in ('before_close','after_context_close','after_shared_close'):
                            assert r['type%d_%s'%(typ,phase)] in (0,1), 'vm query error'
                        assert r['type%d_before_close'%typ]==1
                outcome='COVERAGE_RECORDED' if r['status']=='OWNER_MAP_COVERAGE_RECORDED' else 'MAP_REFUSED_OR_INVALID'
    return {'verification':'PASS','outcome':outcome,'mode':mode,'gpu_registry_id':devs[0]['registry_ID'],
            'pci_registry_ID':devs[0]['pci_registry_ID'],'metal_registry_ID':r['metal_registry_ID'],
            'association_status_hex':hex(r['association_status'] & 0xffffffff) if r['association_attempts'] else None,
            'explicit_selector_calls':0,'explicit_GPU_commands':0,'driver_internal_activity_traced':False,
            'hardware_video_execution_proved':False,'mapping_object_cleanup_proved':False}

if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
