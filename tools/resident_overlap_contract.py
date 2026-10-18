#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Portable, execution-free verifier for the bounded native resident-pair client."""
from pathlib import Path
import hashlib
import json
import struct

POISON=0xa53c6f09

def require(value,message):
    if not value:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def u32(data,offset):return struct.unpack_from('<I',data,offset)[0]
def u64(data,offset):return struct.unpack_from('<Q',data,offset)[0]

def oracle(nonce,role):
    x=nonce^[0x9e3779b9,0x85ebca6b][role]
    for i in range(128):x=((((x<<7)&0xffffffff)|(x>>25))*1664525+1013904223+i)&0xffffffff
    return x

def record_tail(address):
    require(0<address<1<<40 and address%256==0,'aligned bounded descriptor address')
    return struct.pack('<6I',0x200120ad,address>>8,0x200120af,3,0x20012044,0)

def verify_stream(original,candidate,addresses,experimental):
    require(len(addresses)<=2 and len(set(addresses))==len(addresses),'bounded distinct record sequence')
    expected=b''.join(record_tail(a) for a in addresses)
    require(original==expected,'original stream must be exact native record tails')
    require(len(candidate)==len(expected),'complete candidate stream extent')
    if experimental:
        require(len(addresses)==2,'two records required for the intermediate-wait experiment')
        changed=bytearray(expected);struct.pack_into('<I',changed,16,0x20012040);expected=bytes(changed)
        require(u32(candidate,40)==0x20012044 and u32(candidate,44)==0,'terminal wait retained')
    require(candidate==expected,'only the qualified intermediate wait may become NOP')

def verify_witness(row):
    kind,nonce=row['kind'],row['nonce'];s,o=row['sync_words'],row['output_words']
    require(len(s)==len(o)==256,'complete raw buffers')
    active=[] if kind=='none' else [0] if kind=='only-a' else [1] if kind=='only-b' else [0,1]
    count=len(active);require(s[64:67]==[2*count,int(0 in active),int(1 in active)],'GPU sequence and start flags')
    require(all(v==POISON for v in s[:64]+s[67:]),'sync guards')
    tags=[];written=set()
    for role in active:
        offset=[64,128][role];v=o[offset:offset+8];written.update(range(offset,offset+8))
        require(1<=v[0]<v[1]<=2*count,'valid dispatch tags');tags.extend(v[:2])
        require(v[2] in [0,1] and 1<=v[3]<=4096 and (v[2] or v[3]==4096),'bounded peer polling')
        require(1-role in active or v[2]==0,'missing-peer control')
        require(v[4:]==[oracle(nonce,role),nonce,role,128],'independent uint32 arithmetic and invocation marker')
        if kind.startswith('serial-'):
            first=role==(1 if kind.endswith('-ba') else 0)
            require(v[:4]==([1,2,0,4096] if first else [3,4,1,1]),'serial/reverse ordering')
    require(sorted(tags)==list(range(1,2*count+1)),'complete atomic modification order')
    require(all(v==POISON for i,v in enumerate(o) if i not in written),'unused output and omitted-dispatch guards')
    overlap=count==2 and o[64]<o[129] and o[128]<o[65]
    require(row['arithmetic_mismatches']==row['guard_mismatches']==0 and row['interleaved_lifetimes']==overlap and row['active_dispatches']==count,'raw/native result agreement')
    return dict(dispatches=count,arithmetic_results=count,raw_words=512,guard_words=509-8*count,interleaved=overlap)

def verify_build(build):
    build=Path(build);inputs=load(build/'inputs.json')
    for name,digest in inputs['files_SHA256'].items():
        path=(build/name).resolve();path.relative_to(build.resolve());require(sha(path)==digest,'frozen build input '+name)
    core=load(build/'core-manifest.json')
    require(core['status']=='PASS' and core['GPU_execution'] is False and sha(build/'libKeplerMetal.a')==core['static_library_SHA256'],'source-built common archive identity')
    for name,digest in core['source_SHA256'].items():require(sha(build/'core-src'/name)==digest,'frozen runtime source '+name)
    return inputs

def audit_capture(build,run):
    build,run=Path(build),Path(run);inputs=verify_build(build);d=load(run/'results.json');m=load(run/'execution/manifest.json')
    require(d==load(run/'execution/execution.stdout') and load(run/'inputs.json')==inputs,'complete stdout and identical input manifest')
    require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'native host terminal')
    require(m['original_binary_sha256']==inputs['files_SHA256']['application'] and sha(run/'execution/application')==m['signed_binary_sha256'],'original and signed executable identities')
    q=m['GPU_reservation'];require(q['state']=='terminal' and q['lock_inherited_by_child'] and q['bootstrap_process_table_checked'] and not q['known_signed_processes_live'],'common inherited host lease')
    require(d['status']=='PASS' and d['pid']==m['pid'] and d['uid']==d['euid']>0 and d['device']=='NVIDIA GeForce GTX 880M' and d['scope_restored'],'unprivileged native GPU result and scope restoration')
    require(not any(d[k] for k in ['native_shader_code_changed','common_runtime_modified','system_modified','performance_benchmark']),'bounded laboratory scope')
    require(d['library_SHA256']==inputs['files_SHA256']['probe.metallib'] and d['manifest_SHA256']==inputs['files_SHA256']['manifest.json'],'exact registered shader inputs')
    materialized=[e for e in d['scope_events'] if e['operation']=='materialize_CPU_command'];require(len(materialized)==2,'two prepared native records')
    ranges=[];addresses=[];backing=[]
    for role,row in enumerate(d['resident_backing']):
        prefix=run/'captures'/('record-'+str(role));data={name:Path(str(prefix)+'.'+name+'.bin').read_bytes() for name in ['QMD','constants','original','relocated']}
        qmd,c,original,relocated=[data[n] for n in ['QMD','constants','original','relocated']]
        require([len(qmd),len(c),len(original),len(relocated)]==[256,65536,464,464],'full state and record captures')
        for name,payload in data.items():require(hashlib.sha256(payload).hexdigest()==row[name+'_SHA256'],'state/capture digest')
        require(row['constants_SHA256']==materialized[role]['snapshot_SHA256'] and qmd==relocated[184:440],'actual GPU state equals validated native snapshot/relocation')
        changes=[o for o in range(0,464,4) if original[o:o+4]!=relocated[o:o+4]]
        require(changes==row['changed_command_words'] and set(changes)<=set([12,16,168,172,308,312,444]),'only state-address relocations')
        cb,descriptor=row['constants_GPU_address'],row['QMD_GPU_address'];ranges.extend([(cb,cb+65536),(descriptor,descriptor+4096)]);addresses.append(descriptor)
        e=row['relocation'];literal=e['native_literal_bank_0'];literal_address=(u32(qmd,0x78)&255)<<32|u32(qmd,0x74)
        require(e['native_register_count']==17 and e['constant_buffer_valid_mask']==7 and (u32(qmd,0xb8)>>24)==17 and (u32(qmd,0x50)&255)==7,'native kernel metadata')
        require(literal['variant_owner_retained'] and literal['bytes']==256 and literal['native_code_bytes']==2304 and literal_address==literal['GPU_address']==literal['native_code_GPU_address']+2304,'native code/literal ownership')
        require(((u32(qmd,0x80)&255)<<32|u32(qmd,0x7c))==cb and u32(qmd,0x80)>>15==65536,'dedicated constant state in GPU QMD')
        for b in e['bindings']:require(u64(c,b['index']*32+8)==b['GPU_address']+b['offset']==b['native_table_address'],'actual GPU binding table')
        require(relocated[440:464]==record_tail(descriptor),'native resident template')
        backing.append({k:row[k] for k in ['role','QMD_SHA256','constants_SHA256']})
    require(len(backing)==2 and all(b<=c or d<=a for i,(a,b) in enumerate(ranges) for c,d in ranges[i+1:]),'four disjoint state allocations')
    require(verify_witness(d['preparation_untouched_witness'])['dispatches']==0,'preparation left all user witnesses untouched')
    mode=d['mode'];trials=int(m['arguments'][-1]);require(1<=trials<=8 and mode in ['prepare','serial','overlap'],'bounded protocol')
    expected=[] if mode=='prepare' else [(kind,i) for kind in ['none','only-a','only-b','serial-ab','serial-ba'] for i in range(1 if mode=='overlap' else trials)]
    if mode=='overlap':expected.extend((kind,i) for kind in ['overlap-ab','overlap-ba'] for i in range(trials))
    require([(r['kind'],r['trial']) for r in d['runs']]==expected,'all requested controls and experimental orders')
    totals=dict(dispatches=0,arithmetic_results=0,raw_words=0,guard_words=0,interleaved=0,parameter_bytes=0)
    for i,row in enumerate(d['runs']):
        kind=row['kind'];experimental=kind.startswith('overlap-');result=verify_witness(row)
        require(row['nonce']==(310031+104729*i)&0xffffffff and row['command_status']==4,'fresh nonce and complete command buffer')
        roles=[] if kind=='none' else [0] if kind=='only-a' else [1] if kind=='only-b' else [1,0] if kind.endswith('-ba') else [0,1]
        file=run/'captures'/('trial-'+str(i)+'.commands.bin');stream=file.read_bytes();original=Path(str(file)+'.original').read_bytes() if experimental else stream
        verify_stream(original,stream,[addresses[r] for r in roles],experimental)
        require(sha(file)==row['stream_SHA256'] and len(stream)==row['stream_bytes'],'actual candidate stream digest')
        if roles:
            e=row['resident_evidence'];c=row['cursor_evidence'];require(e['stream_SHA256']==hashlib.sha256(original).hexdigest() and e['CPU_QMD_uploads_in_launch']==e['CPU_constant_uploads_in_launch']==e['native_preparation_GPU_dispatches']==0,'prepared-state execution')
            require(c['validated_native_stream_start']+len(stream)==c['after_current']<c['after_end'],'validated native stream boundary')
        if experimental:
            patch=row['experimental_patch'];require(patch['changed_word_offset']==16 and patch['original_header']==0x20012044 and patch['candidate_header']==0x20012040 and patch['terminal_WAIT_FOR_IDLE_retained'] and not patch['native_shader_changed'] and not patch['QMD_or_constant_state_changed'],'only qualified wait changed')
            require(patch['original_stream_SHA256']==hashlib.sha256(original).hexdigest() and patch['candidate_stream_SHA256']==row['stream_SHA256'],'before/after stream identities')
        require(row['native_encoder_dispatch_type']==0,'native getter not spoofed')
        params=bytearray(b'\xa5'*1024);struct.pack_into('<4I',params,256,4096,row['nonce'],128,0)
        for role in range(2):require((run/'captures'/('trial-'+str(i)+'.params-'+str(role)+'.bin')).read_bytes()==params,'all raw parameter bytes and padding')
        for k,v in result.items():totals[k]+=v
        totals['parameter_bytes']+=2048
    require(totals['dispatches']==d['user_compute_dispatches'] and d['experimental_wait_removals']==(2*trials if mode=='overlap' else 0),'dispatch and changed-wait counts')
    if mode=='overlap':
        require(totals['interleaved']==2*trials,'every bounded candidate pair interleaved')
        require(len(d['resident_state_rechecks'])==6,'complete state rechecks before both orders and afterward')
        for entry in d['resident_state_rechecks']:
            for name in ['QMD','constants']:
                file=run/'captures'/(entry['label']+'-'+str(entry['role'])+'.'+name+'.bin')
                require(sha(file)==entry[name+'_SHA256']==backing[entry['role']][name+'_SHA256'],'GPU state stable across completed kernels')
    return dict(status='PASS',mode=mode,trials=len(d['runs']),totals=totals,
        input_manifest_SHA256=sha(build/'inputs.json'),execution_manifest_SHA256=sha(run/'execution/manifest.json'),
        results_SHA256=sha(run/'results.json'),prototype_level=1,performance_benchmark=False,
        simultaneous_instruction_execution_proved=False,full_Metal_API_implementation=False)
