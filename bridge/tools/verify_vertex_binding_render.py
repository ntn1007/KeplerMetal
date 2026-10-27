#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU oracle for the isolated signed vertex-setter probe."""
from pathlib import Path
import hashlib
import math
import struct
from public_large_scratch import read, sha
from verify_local_memory import verify_device_identity
from air_vertex_transition import Binding, State, ROW, make_rows

MODES = ('gpu','native','no_dispatch','no_dispatch_native','disabled','disabled_native','foreign','foreign_native')
EXTRA_MODES = ('reverse','reverse_native','reverse_no_dispatch','reverse_no_dispatch_native','contracts')


def verify(path):
    path=Path(path);inputs=read(path/'inputs.json');d=read(path/'results.json');receipt=read(path/'execution/manifest.json');mode=d['mode']
    assert mode in MODES+EXTRA_MODES and inputs['mode']==mode and d==read(path/'execution/execution.stdout')
    verify_device_identity(d)
    lease=receipt['GPU_reservation'];assert receipt['exit_code']==0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==receipt['pid'] and not lease['known_signed_processes_live']
    assert sha(path/'application')==inputs['executable_SHA256']==receipt['original_binary_sha256']
    assert sha(path/'execution/application')==receipt['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in inputs['frozen'].items():assert sha(path/name)==digest,name
    assert receipt['launcher_SHA256']==inputs['frozen']['runtime/run_sdk_host.py'] and receipt['reservation_module_SHA256']==inputs['frozen']['runtime/lab_gpu_reservation.py']
    assert receipt['arguments']==[str(path/'assets'),str(path/'outputs'),mode]
    assert d['status']=='COMPLETED' and d['command_status']==4 and d['native_Apple_ICB_ABI'] is False and d['performance_benchmark'] is False
    reverse=mode.startswith('reverse');dispatch='no_dispatch' not in mode;foreign=mode.startswith('foreign');enabled=not mode.startswith('disabled');native=mode.endswith('native')
    assert d['dispatches']==int(dispatch) and d['native_reference'] is native
    assert d['refusals']==(['vertex_records_overlap','vertex_root_alias'] if mode=='contracts' else [])
    cert=read(path/'assets/vertex.certificate.json');assert cert['no_native_call'] and cert['driver_SHA256']==inputs['driver_SHA256']
    assert sha(path/'assets/vertex.metallib')==cert['library_SHA256']
    assert d['program']['code_SHA256']==cert['code_SHA256'] and d['program']['own_CPU_staging_code'] and not d['program']['code_replaced'] and not d['program']['constructor_observer_installed']
    assert sha(path/'outputs/native-program.bin')==cert['code_SHA256']
    assert d['inspection']['observer_restored_before_scope'] and d['inspection']['capture']['constructor_restored']
    ids=d['identities'];addr=d['vertex_addresses'];ctx=d['context_address'];records=d['records_address']
    assert len(ids)==2 and len(set(ids))==2 and all(x>>32==0x4b505352 for x in ids)
    assert len(set(addr+[ctx,records]))==6 and all(0<x<2**40 and x%16==0 for x in addr+[ctx,records])
    a=Binding(11,addr[0]-64,64,256);b=Binding(12,addr[1]-64,64,256);instance=Binding(13,addr[2]-64,64,160)
    state0=State(ids[0],0,7,((0,a),(1,instance)),(),(),(3,1,0,0));state1=State(ids[1],0,7,((0,b),(1,instance)),(),(),(3,1,0,0))
    rows=make_rows([state0,state1]);assert len(rows)==d['transition_count']==6 and d['context_size']==384
    actual_context=(path/'outputs/context.bin').read_bytes();assert len(actual_context)==384
    observed=tuple(ROW.unpack_from(actual_context,128+i*ROW.size) for i in range(6))
    assert sorted(observed)==sorted(rows) and len(set(observed))==6
    context=bytearray(b'\xa5'*384);struct.pack_into('<4I2Q',context,64,0x4b505243,1,1,64,records,0);struct.pack_into('<4I2Q',context,96,0x4b505658,1,6,32,ctx+64,0);context[128:320]=actual_context[128:320]
    root=bytearray(b'\xa5'*136);struct.pack_into('<Q',root,64,ctx)
    ident=ids[1 if reverse else 0] if not dispatch or not enabled else 0 if foreign else ids[0 if reverse else 1]
    record=bytearray(b'\xa5'*192);struct.pack_into('<8IQ6I',record,64,0x4b505353,0,3,1,0,0,0,0,ident,*([0]*6))
    output=bytearray(b'\xa5'*132)
    if dispatch:struct.pack_into('<I',output,64,0)
    instance_data=bytearray(b'\xa5'*160);instance_data[64:80]=bytes(16)
    def vertex(color):
        data=bytearray(b'\xa5'*256)
        for i,pos in enumerate(((-1,-1,.5,1),(3,-1,.5,1),(-1,3,.5,1))):struct.pack_into('<8f',data,64+i*32,*pos,*color)
        return data
    expected={'context.bin':context,'root.bin':root,'records.bin':record,'output.bin':output,'instance.bin':instance_data,'vertex-a.bin':vertex((.75,.125,.25,1)),'vertex-b.bin':vertex((.125,.75,.25,1))}
    for name,wanted in expected.items():assert (path/'outputs'/name).read_bytes()==wanted,name
    image=(path/'outputs/image.bin').read_bytes();assert len(image)==49664 and image[:256]==image[-256:]==b'\xa5'*256
    switched=(dispatch and enabled) != reverse
    wanted=(0,0,0,0) if foreign and dispatch and enabled else ((.125,.75,.25,1) if switched else (.75,.125,.25,1))
    values=struct.unpack('<12288f',image[256:-256]);maximum=0.0
    for i,value in enumerate(values):
        error=abs(value-wanted[i%4]);assert math.isfinite(value) and error<=2e-6,(i,value,wanted[i%4]);maximum=max(maximum,error)
    return {'status':'PASS','mode':mode,'checked_float_channels':len(values),'maximum_error':maximum,'dispatches':int(dispatch),'vertex_rows_checked':len(rows),'guard_and_record_buffers_checked':len(expected),'native_Apple_ICB_ABI':False,'performance_benchmark':False}
