#!/usr/bin/env python3
"""Independent guard, integer sum and terminal identity checks for controls."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify(root,portable=False):
    root=Path(root);read=lambda n:json.loads((root/n).read_text())
    d,m,inp=read('results.json'),read('execution/manifest.json'),read('inputs.json')
    assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
    for n,h in inp['source_hashes'].items():assert sha(root/n)==h
    for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
    if not portable:
        assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
        assert sha(root/'execution/application')==m['signed_binary_sha256']
    assert d['scope_restored']and not d['system_modified']
    hashes={}
    if d['status']=='PASS_EXPECTED_OLD_ZERO_BASE_REJECTION':
        assert d['reason']=='Dynamic threadgroup pointer prelude differs'and d['user_outputs_and_counters_untouched']
        assert inp['static_library_SHA256']=='af692ec2833c3138ce3d4f639b9c6b3ffad58f8368ab1aee7ff93a8b814391d4'
        assert len(d['raw_files'])==6
        for n in d['raw_files']:
            f=root/'outputs'/n;raw=f.read_bytes();expected=b'\xa5'*(8192*16+512)if n.startswith('slot')else b'\xa5'*128+bytes(4)+b'\xa5'*76;assert raw==expected;hashes[n]=sha(f)
        return {'status':d['status'],'exact_uint32_words':0,'raw_SHA256':hashes,'old_library_refusal_observed':True,'performance_benchmark':False}
    assert d['status']=='PASS_REJECTIONS_AND_VALID_REPLAY'and d['original_constructor_accepted']and d['main_command_status']==4 and not d['mutated_commands_ever_submitted']
    expected_reasons={'base_zero':'Dynamic threadgroup pointer prelude differs','base_minus16':'Dynamic threadgroup pointer prelude differs','snapshot_base_zero':'Captured dynamic threadgroup base word differs from native prelude','shared_total_plus16':'Native QMD static shared memory differs from reflected profile'}
    assert len(d['controls'])==4
    for c in d['controls']:
        assert c['reason']==expected_reasons[c['case']]and c['refused']and c['CPU_validator_only']and not c['mutated_bytes_ever_encoded']
    wanted=bytearray(b'\xa5'*(8192*16+512));mask=0xffffffff;seed=0x765431
    for i in range(96):
        group,lane=divmod(i,32)
        fixed=lambda j:(seed*1664525 ^ group*1013904223 ^ j*2246822519 ^ 0x73193211)&mask
        dynamic=lambda j:(seed*22695477 ^ group*747796405 ^ j*2891336453 ^ 0x11998877)&mask
        a=sum(dynamic(j)for j in range(lane,12160,32))&mask;b=sum(fixed(j)for j in range(lane,128,32))&mask
        witness=fixed((lane+1)%128)^dynamic((lane*3+7)%12160)
        struct.pack_into('<4I',wanted,128+i*16,a,b,i,witness)
    assert(root/'outputs/output.bin').read_bytes()==wanted
    assert(root/'outputs/counter.bin').read_bytes()==b'\xa5'*128+struct.pack('<I',96)+b'\xa5'*76
    for n in ['output.bin','counter.bin']:hashes[n]=sha(root/'outputs'/n)
    executions=[e for e in d['events']if e['operation']=='executeCommandsInBuffer'];assert len(executions)==1 and not executions[0].get('resident_GPU_descriptor',False)
    proof=executions[0]['evidence'];assert proof['command_bytes']==496 and proof['raw_packet_copies']==1
    o=proof['elements'][0]['relocation']
    assert o['dynamic_threadgroup_base_word']==o['static_threadgroup_bytes']==512 and o['QMD_total_shared_bytes']==49152
    return {'status':d['status'],'exact_uint32_words':384,'raw_SHA256':hashes,'constructor_rejection_controls':4,'GPU_invocations_counted':96,'mutated_bytes_sent_to_GPU':False,'valid_witness_path':'full496byte_native_packet_replay','performance_benchmark':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path);p.add_argument('--portable',action='store_true');a=p.parse_args();v=verify(a.root,a.portable)
    if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps({k:x for k,x in v.items()if k!='raw_SHA256'},indent=2))
