#!/usr/bin/env python3
"""Decode only structurally pinned native QMDv00_06 streams, offline.

Uncommitted capture proves prepared command bytes, not GPU submission,
resident instructions, consumed memory or dynamic hardware stack depth.
"""
from pathlib import Path
import argparse,hashlib,json,struct
from verify_native_control_reserve import terminal,load,sha,require,DRIVER
from verify_native_allocation_common import allocation_proof

ROOT=Path(__file__).resolve().parents[1]
PROFILE=[(0x180,1,4),(0x1b0,4,17),(0x1b4,3,32),(0x180,1,4),(0x1b0,4,17),(0x1b4,3,64),(0x2b4,1,1),(0x2bc,1,1),(0x110,1,1)]


def u32(data,at):return struct.unpack_from('<I',data,at)[0]
def u64(data,at):return struct.unpack_from('<Q',data,at)[0]


def packets(data):
    require(len(data)==464,'unknown stream length');offset=0;result=[]
    while offset<len(data):
        header=u32(data,offset);begin=offset;offset+=4
        mode=header>>29;count=(header>>16)&0x1fff;channel=(header>>13)&7;method=(header&0x1fff)*4
        require(channel==1 and mode in[1,3,4]and count,'push header')
        size=0 if mode==4 else count*4;require(offset+size<=len(data),'push payload')
        result.append({'offset':begin,'data':offset,'method':method,'mode':mode,'count':count});offset+=size
    require([(r['method'],r['mode'],r['count'])for r in result]==PROFILE,'unknown native packet sequence')
    return result


def decode_stream(raw,binding,frame,registers,control,budget,code_address):
    """Validate the captured stream before interpreting hardware field offsets."""
    p=packets(raw);q=raw[p[5]['data']:p[5]['data']+256]
    qmd_target=(u32(raw,p[3]['data']+8)<<32)|u32(raw,p[3]['data']+12)
    cb_target=(u32(raw,p[0]['data']+8)<<32)|u32(raw,p[0]['data']+12)
    cb1=u32(q,0x7c)|((u32(q,0x80)&255)<<32);cb2=u32(q,0x84)|((u32(q,0x88)&255)<<32)
    require(u32(raw,p[0]['data'])==128 and u32(raw,p[0]['data']+4)==1
            and u32(raw,p[3]['data'])==256 and u32(raw,p[3]['data']+4)==1
            and cb_target==cb1+0x6f0 and qmd_target==u32(raw,p[6]['data'])<<8
            and u32(raw,p[7]['data'])==3 and u32(raw,p[8]['data'])==0,'native QMD/constant upload and launch headers')
    values={'version':u32(q,0x48)&15,'major_version':(u32(q,0x48)>>4)&15,
            'groups':[u32(q,0x30),u32(q,0x34)&65535,u32(q,0x34)>>16],
            'local':[u32(q,0x48)>>16,u32(q,0x4c)&65535,u32(q,0x4c)>>16],
            'shared_bytes':u32(q,0x44)&0x3ffff,'constant_buffer_valid_mask':u32(q,0x50)&255,
            'local_low_bytes':u32(q,0xb4)&0xffffff,'local_high_bytes':u32(q,0xb8)&0xffffff,
            'register_count':u32(q,0xb8)>>24,'CRS_bytes':u32(q,0xbc)&0xffffff}
    require(values['version']==6 and values['major_version']==0 and values['groups']==[binding['groups'],1,1]
            and values['local']==[binding['local'],1,1]and binding['groups']==3 and binding['local']==33 and binding['count']==99
            and values['shared_bytes']==0 and values['constant_buffer_valid_mask']in[6,7]
            and cb2==binding['parameters_GPU_address']and u32(q,0x88)>>15==binding['parameters_bytes']==512
            and u32(q,0x80)>>15==65536,'QMD format/geometry/binding identity')
    require(values['local_low_bytes']==values['local_high_bytes']==frame and values['register_count']==registers
            and values['CRS_bytes']==((control+511)&~511)+512,'QMD local/CRS fields')
    require((values['local_low_bytes']+values['local_high_bytes'])*32+values['CRS_bytes']==budget,
            'QMD fields do not reproduce decoded allocation')
    require(u32(q,0x20)==(code_address&0xffffffff),'program offset differs from observed variant low32')
    return {**values,'QMD_SHA256':hashlib.sha256(q).hexdigest(),
            'program_offset_matches_variant_low32':True,'decoded_budget_relation_verified':True}


def analyze(root,build,library,reservation_root=None):
    inp=terminal(root,reservation_root or ROOT,build);d=load(root/'results.json');lm=load(library/'manifest.json')
    require(load(build/'inputs.json')==inp and inp['static_library_SHA256']==sha(library/'libKeplerMetal.a')==lm['static_library_SHA256']
            and inp['library_manifest_SHA256']==sha(library/'manifest.json')
            and inp['source_generator_SHA256']==sha(build/'builder.py'),'capture build provenance')
    require(d['status']=='CAPTURED'and d['device']=='NVIDIA GeForce GTX 880M'and d['registry_id']==4294968458
            and d['driver_SHA256']==DRIVER and d['command_status']==0 and not d['committed']
            and d['user_GPU_command_buffers']==0 and d['created_command_buffers']==1
            and d['encoded_dispatch_calls']==3 and not d['GPU_shader_execution_observed']
            and not d['native_memory_written_by_probe']and not d['packet_replay']and not d['system_modified']
            and not d['performance_benchmark']and d['runs']==[],'capture scope')
    mode,function=d['mode'].split(':');require(mode in['native','reserved']and function==d['function'],'capture mode')
    manifest=load(root/'assets/native-allocation-manifest.json');entry=manifest['certificates'][function]
    cert_file=root/'assets'/entry['file'];cert=load(cert_file);w=cert['metadata_words']
    require(sha(cert_file)==entry['SHA256']==d['certificate_SHA256']
            and sha(root/'assets/control_flow.metallib')==manifest['library_sha256']==d['library_SHA256'],'capture assets')
    if mode=='reserved':allocation_proof(d['import'],root/'assets/control_flow.metallib',cert_file)
    else:require(d['import']=={},'native capture unexpectedly imported a program')
    fields=struct.pack('<32I',*d['variant_words_0_128']);after=struct.pack('<32I',*d['variant_after_words_0_128'])
    import hashlib
    require(hashlib.sha256(fields).hexdigest()==d['variant_SHA256']and hashlib.sha256(after).hexdigest()==d['variant_after_SHA256']
            and d['variant_contract_stable_across_encoding'],'variant snapshots')
    control=4096 if mode=='reserved'else w[11];frame=(w[12]+15)&~15
    expected=frame*64+((control+511)&~511)+512
    for data in[fields,after]:
        require(u64(data,24)==cert['code_bytes']==d['native_code_bytes']
                and u32(data,40)==expected==d['decoded_allocation_word40']==d['decoded_allocation_after_word40']
                and u32(data,44)==cert['code_bytes']//8-1 and u32(data,48)==w[7]==d['native_registers']
                and u32(data,56)==w[14]==d['native_spill_bytes'],'decoded native variant')
    require(u64(fields,16)==d['code_GPU_address']and u64(after,16)==d['code_after_GPU_address'],'variant code address')
    records=[];require(len(d['records'])==3,'capture count')
    for step,r in enumerate(d['records']):
        raw=(root/'outputs'/r['file']).read_bytes();require(r['step']==step and r['saved']and r['range_comparable']
            and r['bytes']==len(raw)and sha(root/'outputs'/r['file'])==r['SHA256'],'raw stream identity')
        before,end=r['before'],r['after']
        require(before['valid']and end['valid']and before['push']==end['push']
                and end['current']-before['current']==len(raw)and end['current']<=before['end'],'read-only cursor interval')
        values=decode_stream(raw,d,frame,w[7],control,expected,u64(after,16))
        records.append({'step':step,**values,'stream_SHA256':r['SHA256']})
    stable=[{k:v for k,v in r.items()if k not in['step','QMD_SHA256','stream_SHA256']}for r in records]
    require(all(r==stable[0]for r in stable),'non-address QMD fields vary across repeats')
    return {'status':'PASS','scope':'Prepared uncommitted native commands; no GPU execution proof',
            'mode':mode,'function':function,'native_frame':w[12],'native_control_word11':w[11],
            'requested_control':control,'decoded_allocation_word40':expected,'native_code_bytes':cert['code_bytes'],
            'certificate_code_SHA256':cert['native_code_sha256'],'records':records,
            'prepared_QMDs_verified':3,'user_GPU_command_buffers':0,'hardware_CRS_consumption_observed':False,
            'static_library_SHA256':inp['static_library_SHA256'],'performance_benchmark':False,'full_objective_complete':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in['root','build','library','out']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--reservation-root',type=Path,help='Existing shared laboratory reservation root')
    a=p.parse_args();out=a.out.resolve();reservation=(a.reservation_root or ROOT).resolve();out.relative_to(reservation/'results');proof=analyze(a.root.resolve(),a.build.resolve(),a.library.resolve(),reservation)
    with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in proof.items()if k!='records'},indent=2))
