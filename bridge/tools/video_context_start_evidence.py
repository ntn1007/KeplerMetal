#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify pinned static video-context start and one failure cleanup path."""
import argparse,json,struct
from pathlib import Path
from compare_video_profile import file_bytes,symbols_and_external_relocations
from video_method_contract import IO_SHA,GE_SHA,REA_SHA,sha,symbol_one
from video_resource_ownership import check_evidence

GE_SPEC=('unused','b9373349f6da3ee15b52ae6d6dc1c714af026c2c8a664b839d3bb75fa88eb5d7',
 'ev_f1e1dbf6aab03185949523cc150812efca45770c7c6effdd5916714f20feac26',18,
 ['0x68332: MOV RAX, qword ptr [0x0007b1a0]','0x6833a: JMP qword ptr [RAX + 0x9f0]'])
IO_SPEC=('unused','e21a0c995f17e986903ec783217d72f12ed2d608751192e8e03a4044fed7caa2',
 'ev_1ca8c15c93b3ecd9934ce82631d0ce0fbb0eadecc552db1b426f83fe4c7eb315',76,
 ['0x3a020: LEA RAX, [0x6d760]','0x3a027: CALL qword ptr [RAX + 0x9f0]',
  '0x3a031: JZ 0x0003a05b','0x3a054: INC dword ptr [R14 + 0x230]'])

def target(data,relocs,cell,expected):
    v=struct.unpack('<Q',file_bytes(data,cell,8)[1])[0]
    if relocs.get(cell) or v!=expected:raise ValueError('Static vtable target differs')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('ioaccel','geforce','ge-capture','io-capture','prior-rea','out'):
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():raise ValueError('Fresh output file required')
    io,ge=a.ioaccel.read_bytes(),a.geforce.read_bytes();bundle=a.prior_rea.read_bytes()
    if (sha(io),sha(ge),sha(bundle))!=(IO_SHA,GE_SHA,REA_SHA):raise ValueError('Pinned profile differs')
    isy,ir=symbols_and_external_relocations(io);gsy,gr=symbols_and_external_relocations(ge)
    for sy,name,v in [(gsy,'__ZTV14nvVideoContext',0x90fe8),(gsy,'__ZN14nvVideoContext12contextStartEv',0x6832e),
        (isy,'__ZTV20IOAccelVideoContext2',0x7ac60),(isy,'__ZTV15IOAccelContext2',0x6d760),
        (isy,'__ZN20IOAccelVideoContext212contextStartEv',0x3a016),(isy,'__ZN15IOAccelContext212contextStartEv',0x7a9c)]:
        if symbol_one(sy,name)['value']!=v:raise ValueError('Symbol address differs: '+name)
    target(ge,gr,0x90ff8+0x9e0,0x6832e);target(io,ir,0x7ac60+0x9f0,0x3a016);target(io,ir,0x6d760+0x9f0,0x7a9c)
    rel=gr.get(0x7b1a0,[])
    if len(rel)!=1 or rel[0]['symbol']['name']!='__ZTV20IOAccelVideoContext2' or (rel[0]['external'],rel[0]['length_code'],rel[0]['type'],rel[0]['pc_relative'])!=(1,3,0,0) or file_bytes(ge,0x7b1a0,8)[1]!=b'\0'*8:
        raise ValueError('Parent vtable relocation differs')
    captures=[check_evidence(a.ge_capture,'0x6832e',GE_SPEC,GE_SHA),check_evidence(a.io_capture,'0x3a016',IO_SPEC,IO_SHA)]
    records=json.loads(bundle)['records']
    rows=[r for r in records if isinstance(r.get('normalized_result'),dict) and isinstance(r['normalized_result'].get('procedure'),dict) and r['normalized_result']['procedure'].get('address')=='0x7a9c' and r.get('evidence_id')=='ev_cdf7ab79e67a28410b7f9c96a0efa68db74e71bfcf7f3ca039c465eaea50391f']
    if len(rows)!=1 or rows[0]['subject']['digest']['sha256']!=IO_SHA or '0x7ead: CALL 0x00007eea' not in rows[0]['normalized_result']['assembly']:
        raise ValueError('Base start failure path differs')
    result={'status':'PASS','GeForce_SHA256':GE_SHA,'IOAccelerator_SHA256':IO_SHA,'captures':captures,
       'base_start_evidence_id':rows[0]['evidence_id'],'base_start_bundle_SHA256':REA_SHA,
       'static_chain':['0x6832e','0x3a016','0x7a9c'],'base_failure_call':'0x7eea',
       'runtime_chain_observed':False,'all_failure_paths_qualified':False}
    with a.out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','runtime_chain_observed':False,'all_failure_paths_qualified':False}))

if __name__=='__main__':main()
