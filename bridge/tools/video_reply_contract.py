#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline, hash-bound assessment of a video-buffer reply path.

Never loads a driver or submits GPU/IOKit calls. The two private disassemblies
and REA records are input evidence, not distributed project artifacts.
"""
import argparse, hashlib, json, re, struct
from pathlib import Path
from compare_video_profile import file_bytes, symbols_and_external_relocations
from inspect_video_cache import Cache, inspect, image_map
from video_buffer_user_contract import IMAGE, UUID
from video_method_contract import GE_SHA, get_data_evidence, get_buffer_evidence
from video_reply_bounds import checked_reply

def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def audit(ge,cache,getdata,getbuffer,tail_rea,user_audit):
    b=ge.read_bytes();need(sha(b)==GE_SHA,'GeForce hash differs')
    symbols,relocs=symbols_and_external_relocations(b)
    matches=[s for s in symbols if s['name']=='__ZTV14nvVideoContext' and s['value']==0x90fe8 and s['type']&0x0e==0x0e]
    need(len(matches)==1,'Video vtable identity')
    cell=0x90ff8+0xa78;_,word=file_bytes(b,cell,8)
    need(not relocs.get(cell) and struct.unpack('<Q',word)[0]==0x683b0,'Private response vtable slot')
    name='__ZN15IOAccelContext220getDataBufferPrivateEP16IOAccelResource2P22IOAccelResourcePrivatey'
    need(any(s['name']==name and s['value']==0x683b0 and s['type']&0x0e==0x0e for s in symbols),'Tail symbol')
    _,code=file_bytes(b,0x683b0,6)
    need(sha(code)=='5a96d1fb661d55552184ea24023ae8190bd1523ae1f855a8d671b07143e8b1df' and not any(relocs.get(x) for x in range(0x683b0,0x683b6)),'Tail body differs')
    tail_record=tail_rea.read_bytes();need(sha(tail_record)=='548d3ae35fc55004e621b7906c24bdc64b20398be7de7803aa53f6b996ee9b40','REA tail record differs')
    obj=json.loads(tail_record);r=json.loads(obj['result']['content'][0]['text']);n=r['normalized_result']
    need(r['evidence_id']=='ev_e5a940d04aea0c79af48881f137812f2fcd7dbb6e0bed3d7fb59e1d53b74ad96' and r['subject']['digest']['sha256']==GE_SHA and n['procedure']['address']=='0x683b0' and n['procedure']['body']['total_bytes']==6 and n['assembly']==['0x683b0: PUSH RBP','0x683b1: MOV RBP, RSP','0x683b4: POP RBP','0x683b5: RET'],'REA no-write body')
    outer=get_data_evidence(getdata);inner=get_buffer_evidence(getbuffer)
    parent=json.loads(getdata.read_text())['normalized_result']['assembly'];child=json.loads(getbuffer.read_text())['normalized_result']['assembly']
    anchors=['0x71df: MOV R8, qword ptr [R12]','0x71e3: LEA RAX, [R14 + 0x30]','0x71e7: XOR ECX, ECX','0x71e9: ADD R8, -0x30','0x71ed: CMOVNZ RCX, RAX','0x71fe: CALL qword ptr [RAX + 0xa68]']
    need(all(x in parent for x in anchors) and '0xa8bb: CALL qword ptr [RAX + 0xa78]' in child,'Kernel pointer/length flow')
    c=Cache(cache.resolve());m=image_map(cache.with_name(cache.name+'.map'),IMAGE);img,starts=inspect(c,m[0]['start'],IMAGE);need(img['UUID']==UUID,'Cache image differs')
    rows=[('buffer-function-01',0x7ff80f890b36,236,'35d66134005b9fcfb387423a3ef975bc6cec4b62aeb7c8b82a46e2cfc284cb29','c95c1170940ed933588b5d0c5422306ddb441d541899d8cb371897aef8b89001'),('buffer-function-04',0x7ff80f88ec14,181,'4a2716ebd724b52e4c2cab4e345094eab8a0bbb24a5316ee565478d6732f8059','2b5e82ae8d03ba134d0e6555f26b13206008852c21e476bd121c0bf6ff210251')]
    texts=[]
    for folder,start,length,expected,disasm in rows:
        need(start in starts and sha(c.read(start,length))==expected,'Cache function changed')
        raw=(user_audit/folder/'disassembly.private.txt').read_bytes();need(sha(raw)==disasm,'Private disassembly changed');texts.append(raw.decode())
    a,btext=texts
    for pattern in [r'cmp\s+r13, qword ptr \[rbp - 0x30\]',r'jb\s+0x7ff80f890c08',r'lea\s+rdx, \[r15 \+ 0x30\]|add\s+rdx, 0x30']:
        need(re.search(pattern,a) is not None,'User reply check anchor')
    for pattern in [r'mov\s+rcx, qword ptr \[rbp - 0x38\]',r'call\s+0x7ff80f88ec14']:
        need(re.search(pattern,a) is not None,'User constructor arguments')
    for pattern in [r'mov\s+r15, rdx',r'mov\s+r14, rcx',r'mov\s+rsi, r15',r'mov\s+rdx, r14',r'call\s+0x7ff80f894860']:
        need(re.search(pattern,btext) is not None,'User tail copy')
    accepted=[];rejected=[]
    for nbytes in (0,47,48,49,50):
        try:checked_reply(0,49,nbytes,1,b'x'*49);accepted.append(nbytes)
        except ValueError:rejected.append(nbytes)
    need(accepted==[49] and rejected==[0,47,48,50],'Conservative model controls')
    return {'status':'STATIC_PASS','GeForce_SHA256':GE_SHA,'cache_image_UUID':UUID,'tail_vtable_slot':'0xa78','tail_target':'0x683b0','tail_body_SHA256':sha(code),'tail_REA_evidence_id':r['evidence_id'],'tail_REA_SHA256':sha(tail_record),'kernel_get_data_evidence_id':outer['evidence_id'],'kernel_getDataBuffer_evidence_id':inner['evidence_id'],'static_tail_pointer_rule':'capacity 48 -> null; capacity greater than 48 -> output + 48 with capacity - 48', 'observed_user_reply_check':'rejects output length greater than capacity; no lower-bound check visible in pinned branch','conditional_user_copy_bytes':'device private length, irrespective of a shorter successful reported output','conservative_synthetic_lengths':{'capacity':49,'private_bytes':1,'accepted':accepted,'rejected':rejected},'native_calls':0,'GPU_commands':0,'hardware_video_execution_proved':False,'limits':['On-disk vtable does not establish runtime relocation or selected virtual target.','No live selector 3 or successful output has been observed.','The six-byte function observation does not establish returned tail initialization elsewhere.','A short successful reply is a hypothetical case; no vulnerability or exploit is demonstrated.']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('geforce','cache','getdata','getbuffer','tail-rea','user-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required')
    r=audit(a.geforce,a.cache,a.getdata,a.getbuffer,a.tail_rea,a.user_audit)
    with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(r))
if __name__=='__main__':main()
