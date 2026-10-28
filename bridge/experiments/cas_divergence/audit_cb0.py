#!/usr/bin/env python3
"""Recheck passive conditional-CAS CB0 observations; no command submission."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
from run_repair import SYSTEM

BRIDGE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BRIDGE/'tools'))
from decode_native_commands import decode

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)
def u32(data,offset):return struct.unpack_from('<I',data,offset)[0]
def u64(data,offset):return struct.unpack_from('<Q',data,offset)[0]

def inspect(commands,variant,mode):
    need(len(variant)==128,'variant size differs')
    packets=decode(commands)
    matches=[x for x in packets if x.get('subchannel')==1 and x.get('method')=='0x1b4' and len(x.get('values',[]))==64]
    need(len(matches)==1,'unique QMD upload required')
    qmd=struct.pack('<64I',*matches[0]['values'])
    address=u64(variant,16);size=u64(variant,24);registers=u32(variant,48)
    mask=u32(qmd,0x50)&255;cb0=u32(qmd,0x74)|((u32(qmd,0x78)&255)<<32);cb0bytes=u32(qmd,0x78)>>15
    require_size={'native':1344,'repaired':1408}
    need(mode in require_size and size==require_size[mode] and address and registers==13 and
         mask==7 and cb0bytes==256 and cb0==address+((size+255)&~255) and
         u32(qmd,0x20)==(address&0xffffffff) and u32(qmd,0xb8)>>24==registers,
         'observed QMD/variant relationship differs')
    return {'packets':len(packets),'command_bytes':len(commands),'code_bytes':size,
            'registers':registers,'CB_valid_mask':mask,'CB0_bytes':cb0bytes,
            'CB0_equals_code_end_aligned_256':True,'QMD_program_low32_matches_variant':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',nargs=4,type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();build=a.build.resolve();out=a.out.resolve()
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    built=json.loads((build/'build.json').read_text())
    for name,digest in built['files_SHA256'].items():need(sha(build/name)==digest,'build differs: '+name)
    need(sha(build/'observe.mm')==sha(Path(__file__).with_name('observe_cb0.mm')) and
         sha(build/'import.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
         sha(build/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h') and
         sha(build/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc') and
         sha(build/'ICBTextureNativeMetadata.inc')==sha(BRIDGE/'tools/ICBTextureNativeMetadata.inc'),
         'source differs')
    receipts=[];intervals=[]
    for mode,root in zip(('native','repaired','native','repaired'),a.runs):
        root=root.resolve();m=json.loads((root/'manifest.json').read_text());r=json.loads((root/'report.json').read_text())
        need(m['mode']==mode and m['exit_code']==0 and m['GPU_reservation']['state']=='terminal' and
             not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and
             m['system_before']==m['system_after']==SYSTEM and m['build_sha256']==sha(build/'build.json') and
             m['original_binary_sha256']==sha(build/'host') and m['signed_binary_sha256']==sha(root/'application'),
             'process manifest differs')
        need(subprocess.run(['codesign','--verify','--strict',str(root/'application')],capture_output=True,timeout=15).returncode==0,'signature differs')
        need(r['status']=='PREPARED_NOT_SUBMITTED' and r['mode']==mode and r['device']=='NVIDIA GeForce GTX 880M' and
             r['registry_id']==4294968416 and r['GPU_submissions']==0 and r['command_status']==0 and
             r['GPU_execution_proved'] is False and r['command_SHA256']==sha(root/'commands.bin') and
             r['variant_SHA256']==sha(root/'variant.bin') and r['library_SHA256']==built['files_SHA256']['shader.metallib'],
             'observation report differs')
        if mode=='repaired':
            proof=r['import'];native=proof['native_import'];events=native['events']
            need(proof['gate_accepted'] and proof['constructor_restored'] and native['contract_verified'] and
                 len(events)==1 and events[0]['conditional_auxiliary_section_pinned'] and
                 events[0]['imported_code_identical'],'repaired import proof differs')
        row=inspect((root/'commands.bin').read_bytes(),(root/'variant.bin').read_bytes(),mode)
        row.update({'mode':mode,'command_sha256':r['command_SHA256'],'variant_sha256':r['variant_SHA256'],
                    'signed_host_sha256':m['signed_binary_sha256']});receipts.append(row)
        intervals.append((m['started_at'],m['completed_at']))
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),
                          'observer processes overlap')
    result={'status':'PASS','observations':receipts,'GPU_submissions':0,'CB0_contents_read':False,
            'section_to_CB0_contents_proved':False,'indirect_branch_semantics_proved':False,
            'resident_code_readback':False,'build_sha256':sha(build/'build.json')}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
