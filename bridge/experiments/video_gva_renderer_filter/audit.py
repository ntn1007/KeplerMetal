#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit one pinned static renderer-class filter against recorded node snapshots."""
import argparse
import hashlib
import json
import re
from pathlib import Path

REGION_SHA = '4c07b6daa5d9e4449c3f77192951ffa230915193befe87cbbf443e25226fa564'
WINDOWS = {(0xf0,0x119):'dfefbd9fbd5af3a5eea70d52094dcb9362c6ff1c521422caf3aa3f4f962abfe2',
           (0x119,0x165):'d613bc956c1e65fb859cb772e480d8cc3077c9c22ad8efa23be07595342e2a32',
           (0x168,0x193):'4fb0fab8b42fbe1bd26bbb335aa55dc817fdbf0d3d1c1f04804f5d2ae6e4e110'}


def digest(data): return hashlib.sha256(data).hexdigest()
def need(ok, message):
    if not ok: raise ValueError(message)
def read(path): return json.loads(Path(path).read_text())


def classify(value):
    """Model 32-bit unsigned arithmetic in the inspected flag-zero path."""
    if not isinstance(value,int) or not 0 <= value <= 0xffffffff:
        raise ValueError('a 32-bit unsigned renderer field is required')
    first=(value-0x1080001)&0xffffffff
    if first<=31 and (0x8000808b >> first)&1: return 'first'
    second=(value-0x1020000)&0xffffffff
    if second<=4 and (0x15 >> second)&1: return 'second'
    if value==0x1080080: return 'first'
    return 'excluded'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--region',type=Path,required=True)
    p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--prior-audit',type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=3,required=True,help='off, synthetic 1, synthetic 2')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==3,'fresh output and distinct runs required')
    region=a.region.read_bytes(); meta=read(a.metadata); previous=read(a.prior_audit)
    need(len(region)==1136 and digest(region)==REGION_SHA and meta['region']['SHA256']==REGION_SHA and meta['region']['target_image_offset']==146348 and meta['image']['UUID']=='ca5414f369373c059ea2d82b35afd4f0', 'capture profile differs')
    for (start,end),expected in WINDOWS.items():need(digest(region[start:end])==expected, 'instruction window differs')
    need(previous['status']=='PASS_BOUNDED_AUDIT' and not previous['hardware_video_execution_proved'] and len(previous['runs'])==6,'prior audit differs')
    checks=[]
    for run, prior in zip(a.runs,previous['runs'][3:]):
        manifest=read(run/'manifest.json'); log=(run/'lldb.log').read_text(); expected=prior['probe']; injected=int(expected=='synthetic')
        need(expected in ('off','synthetic') and manifest['mode']=='current' and manifest['probe']==expected and manifest['status']=='TERMINAL_SCOPED_DEBUGGER' and manifest['decoder_status']==-12913 and manifest['output_frames']==0, f'{run.name}: unexpected case')
        need(digest((run/'manifest.json').read_bytes())==prior['manifest_sha256'] and digest((run/'lldb.log').read_bytes())==manifest['lldb_log_sha256']==prior['lldb_log_sha256'], f'{run.name}: evidence hash differs')
        need(manifest['reservation']['state']=='terminal' and manifest['target_and_debugger_absent'] and not manifest['hardware_video_execution_proved'], f'{run.name}: terminal state')
        rows=re.findall(r'^KP_LIST_NODE caller_offset=(\d+) thread=(\d+) index=(\d+) kind=(\d+) flags=(\d+),(\d+),(\d+),(\d+) next_present=(\d+)$',log,re.M)
        need(len(rows)==2,'list snapshot count differs')
        rows=[tuple(map(int,row)) for row in rows]
        need([row[0] for row in rows]==[147562,146279] and len({row[1] for row in rows})==1 and all(row[2:]==(0,17039368,1,0,0,injected,0) for row in rows),f'{run.name}: snapshots differ')
        links=[line for line in log.splitlines() if 'KP_HW_HIT name=list_entry ' in line]
        need(len(links)==2 and all('bytes_match=1' in line and 'flag=0 selector=2' in line and 'link_valid=1 same_node=1' in line for line in links),f'{run.name}: selection breakpoint differs')
        output=[line for line in log.splitlines() if 'KP_HW_HIT name=after_enumeration ' in line]
        need(len(output)==1 and 'field_valid=1 field=0' in output[0],f'{run.name}: output differs')
        need(classify(rows[1][3])=='excluded','unexpected classification')
        checks.append({'probe':expected,'renderer_field':hex(rows[1][3]),'selection_flag':0,'observed_node_flags':[1,0,0,injected],'modeled_category':'excluded','enumeration_output':0,'manifest_sha256':prior['manifest_sha256']})
    need([c['probe'] for c in checks]==['off','synthetic','synthetic'],'run order differs')
    receipt={'status':'PASS_STATIC_FILTER_AND_RECORDED_SNAPSHOTS','source_region_sha256':REGION_SHA,
             'windows_sha256':{f'{a:x}:{b:x}':v for (a,b),v in WINDOWS.items()},
             'prior_audit_sha256':digest(a.prior_audit.read_bytes()),'runs':checks,
             'static_classifier':{'first_mask_base':'0x01080001','first_mask':'0x8000808b','first_mask_width':32,'first_extra':'0x01080080','second_mask_base':'0x01020000','second_mask':'0x15','second_mask_width':5},
             'rea_wrapper_sha256':'2b0f302644be362039a7e4bb353b20ba1a25ed98230ff0e92d4c8b1d59e8f605',
             'rea_analysis_evidence':'ev_85c3930ac61c44d71934e0ce8ef511410b4c33d4e99bd4dea11c7cfdd347d8d1',
             'actual_branch_traced':False,'node_stable_after_resume_proved':False,'full_cause_identified':False,'hardware_video_execution_proved':False,
             'scope':'Static pinned selection path and three earlier debugger snapshots; no new vendor or GPU execution.'}
    with a.out.open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':receipt['status'],'renderer_field':'0x01040008','category':'excluded','hardware_video_execution_proved':False}))


if __name__=='__main__':main()
