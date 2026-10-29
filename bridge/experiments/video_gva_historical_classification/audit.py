#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare a pinned High Sierra classifier with the recorded current path."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'video_gva_renderer_filter'))
from audit import REGION_SHA, classify
OLD_SHA='54dc80c41bab45492d1eb601fb1d242b513107645d068bf24edee155b965681f'
FAT_SHA='fd3bb85c44252b11431cee998fb35906ed51ab0a8d5ea6afa5fd79c636a46948'
REA_SHA='6ad2ada34fa269ea9c41dabd86c7b5926cb48f4b210f6a8a1eb46f9af69b14eb'
IDS=('ev_247b9e60588040bc9a1d23ca7dc8ff8f96c7143b01a604d49f9704992436a124',
     'ev_931bf92d58c7106a382a89793c44f1a449547dd15df2b697589287a5b3134103')
WINDOWS={(0x23c3e,0x23c56):'739b16741402a12e3f23bc5aa3a929d8402a022cfbc8c085b7b4b408bb60b193',
 (0x24070,0x2408e):'e025a73b8ac4c23e682a46d1a7dedfcae9c91759b6fa29ef870094c03dd81ac3',
 (0x240ea,0x2410d):'1f47391b577b985ef1df9ae8b56a060454e5e862c4be5f5dd9fdec57d36f32bd',
 (0x2415a,0x24174):'aa96c8d86609a7325757eef95092e39c952a62dd203599d934c39fca8360e7d4',
 (0x24218,0x2423f):'ef9e914e28e0de153211534737059eb26d369f42302a465ef62afee1c47027ae'}
def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(Path(p).read_bytes())
def need(ok,msg):
    if not ok:raise ValueError(msg)
def fat_x86(data):
    need(len(data)>=8 and data[:4]==b'\xca\xfe\xba\xbe','FAT32 header')
    count=struct.unpack_from('>I',data,4)[0];need(0<count<=16 and len(data)>=8+20*count,'FAT32 table')
    matches=[]
    for i in range(count):
        cpu,subtype,offset,size,align=struct.unpack_from('>IIIII',data,8+20*i)
        need(offset<=len(data) and size<=len(data)-offset,'FAT32 slice bounds')
        if cpu==0x01000007:matches.append(data[offset:offset+size])
    need(len(matches)==1,'unique x86_64 slice required');return matches[0]
def macho_profile(data):
    need(len(data)>=32 and data[:4]==b'\xcf\xfa\xed\xfe','Mach-O x86_64 header')
    cpu,_,_,count,size=struct.unpack_from('<IIIII',data,4)
    need(cpu==0x01000007 and count<=1024 and 32+size<=len(data),'Mach-O commands')
    pos=32;uuids=[];text=[]
    for _ in range(count):
        need(pos+8<=32+size,'command header bounds');cmd,sz=struct.unpack_from('<II',data,pos)
        need(sz>=8 and pos+sz<=32+size,'command bounds')
        if cmd==0x1b:
            need(sz==24,'UUID size');uuids.append(data[pos+8:pos+24].hex())
        if cmd==0x19 and sz>=72:
            name=data[pos+8:pos+24].split(b'\0',1)[0];vm,vmsize,fileoff,filesize=struct.unpack_from('<QQQQ',data,pos+24)
            if name==b'__TEXT':text.append((vm,vmsize,fileoff,filesize))
        pos+=sz
    need(pos==32+size and uuids==['78a7c6684a3934c99309f3c418487d6f'] and len(text)==1,'Mach-O identity')
    vm,_,off,length=text[0];need(vm==off==0 and length>0xcf692,'text mapping');return uuids[0]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('universal','legacy','rea','current-region','current-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output')
    legacy=a.legacy.read_bytes();fat=a.universal.read_bytes()
    need(digest(legacy)==OLD_SHA and digest(fat)==FAT_SHA and fat_x86(fat)==legacy,'legacy slice provenance')
    uuid=macho_profile(legacy)
    for (start,end),expected in WINDOWS.items():need(digest(legacy[start:end])==expected,'legacy instruction window')
    need(legacy[0xcf686:0xcf692]==b'NVIDIA, VP4\0','legacy VP4 label')
    need(sha(a.rea)==REA_SHA,'retained REA bundle differs');records=json.loads(a.rea.read_text())['records']
    selected=[]
    for evidence in IDS:
        rows=[r for r in records if r.get('evidence_id')==evidence]
        need(len(rows)==1 and rows[0]['subject']['digest']['sha256']==OLD_SHA,'REA evidence identity');selected.append(rows[0])
    names=selected[0]['normalized_result']['referenced_strings']
    need(any(x.get('source_address')=='0x23c4a' and x.get('address')=='0xcf686' and x.get('value')=='NVIDIA, VP4' for x in names),'legacy label evidence')
    assembly=selected[1]['normalized_result']['assembly']
    for fragment in ('0x24163: CMP R10D, 0x1040008','0x2416a: JNZ 0x000241d1','0x2416c: INC R9D','0x2416f: MOV R15, RBX'):
        need(fragment in assembly,'legacy classifier evidence')
    current=json.loads(a.current_audit.read_text());need(sha(a.current_region)==REGION_SHA and current['status']=='PASS_BOUNDED_CLASSIFICATION_WITNESS' and current['source_region_sha256']==REGION_SHA and current['observed_field']=='0x01040008' and current['synthetic_runs']==2 and not current['hardware_video_execution_proved'] and classify(0x1040008)=='excluded','current evidence')
    receipt={'status':'PASS_PINNED_HISTORICAL_COMPARISON','legacy_universal_sha256':FAT_SHA,'legacy_x86_64_sha256':OLD_SHA,'legacy_uuid':uuid,'legacy_rea_bundle_sha256':REA_SHA,'legacy_evidence_ids':IDS,'legacy_instruction_windows_sha256':{f'{a:x}:{b:x}':h for (a,b),h in WINDOWS.items()},'legacy_label':'NVIDIA, VP4','legacy_field_offset':'0x408','legacy_classifier_compares':'0x01040008','current_region_sha256':REGION_SHA,'current_witness_audit_sha256':sha(a.current_audit),'current_observed_field':'0x01040008','current_static_classification':'excluded','legacy_runtime_tested':False,'legacy_compatibility_proved':False,'hardware_video_execution_proved':False,'system_modified':False}
    with a.out.open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':receipt['status'],'legacy_label':receipt['legacy_label'],'current_classification':'excluded','hardware_video_execution_proved':False}))
if __name__=='__main__':main()
