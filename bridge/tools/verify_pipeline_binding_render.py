#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU checks for a bounded two-pipeline render experiment."""
from pathlib import Path
import math
import struct
from public_large_scratch import read, sha
from verify_local_memory import verify_device_identity

MODES=('gpu','native','no_dispatch','no_dispatch_native','foreign','foreign_native')
EXTRA_MODES=('reverse','reverse_native','reverse_no_dispatch','reverse_no_dispatch_native')


def verify(path):
    path=Path(path);inputs=read(path/'inputs.json');d=read(path/'results.json');receipt=read(path/'execution/manifest.json');mode=d['mode']
    assert mode in MODES+EXTRA_MODES and inputs['mode']==mode and d==read(path/'execution/execution.stdout')
    verify_device_identity(d);lease=receipt['GPU_reservation']
    assert receipt['exit_code']==0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==receipt['pid'] and not lease['known_signed_processes_live']
    assert sha(path/'application')==inputs['executable_SHA256']==receipt['original_binary_sha256']
    assert sha(path/'execution/application')==receipt['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in inputs['frozen'].items():assert sha(path/name)==digest,name
    assert receipt['launcher_SHA256']==inputs['frozen']['runtime/run_sdk_host.py'] and receipt['reservation_module_SHA256']==inputs['frozen']['runtime/lab_gpu_reservation.py']
    assert receipt['arguments']==[str(path/'assets'),str(path/'outputs'),mode]
    assert d['status']=='COMPLETED' and d['command_status']==4 and not d['native_Apple_ICB_ABI'] and not d['performance_benchmark']
    reverse=mode.startswith('reverse');dispatch='no_dispatch' not in mode;foreign=mode.startswith('foreign');native=mode.endswith('native')
    assert d['dispatches']==int(dispatch) and d['native_reference'] is native
    cert=read(path/'assets/vertex.certificate.json');assert cert['no_native_call'] and cert['driver_SHA256']==inputs['driver_SHA256']
    assert sha(path/'assets/vertex.metallib')==cert['library_SHA256']
    assert d['program']['code_SHA256']==cert['code_SHA256'] and d['program']['own_CPU_staging_code'] and not d['program']['code_replaced'] and not d['program']['constructor_observer_installed']
    assert sha(path/'outputs/native-program.bin')==cert['code_SHA256']
    assert d['inspection']['observer_restored_before_scope'] and d['inspection']['capture']['constructor_restored']
    ids=d['identities'];addr=d['vertex_addresses'];ctx=d['context_address'];records=d['records_address']
    assert len(ids)==2 and len(set(ids))==2 and all(x>>32==0x4b505352 for x in ids)
    assert len(set(addr+[ctx,records]))==6 and all(0<x<2**40 and x%16==0 for x in addr+[ctx,records])
    assert d['transition_count']==4 and d['context_size']==320
    context=bytearray(b'\xa5'*320);struct.pack_into('<4I2Q',context,64,0x4b505243,1,1,64,records,0);struct.pack_into('<4I2Q',context,96,0x4b505050,1,4,32,ctx+64,0)
    for i,row in enumerate(((ids[0],ids[0],0x11111),(ids[0],ids[1],0x22222),(ids[1],ids[0],0x11111),(ids[1],ids[1],0x22222))):
        struct.pack_into('<3Q2I',context,128+i*32,*row,0,0)
    root=bytearray(b'\xa5'*144);struct.pack_into('<2Q',root,64,ctx,0x33333 if foreign else 0x11111 if reverse else 0x22222)
    identity=ids[int(reverse)] if not dispatch else 0 if foreign else ids[int(not reverse)]
    record=bytearray(b'\xa5'*192);struct.pack_into('<8IQ6I',record,64,0x4b505353,0,3,1,0,0,0,0,identity,*([0]*6))
    output=bytearray(b'\xa5'*132)
    if dispatch:struct.pack_into('<I',output,64,0x4b505350)
    instance=bytearray(b'\xa5'*160);instance[64:80]=bytes(16)
    vertices=bytearray(b'\xa5'*256)
    for i,(pos,color) in enumerate(zip(((-1,-1,.5,1),(3,-1,.5,1),(-1,3,.5,1)),((1,0,0,1),(0,1,0,1),(0,0,1,1)))):
        struct.pack_into('<8f',vertices,64+i*32,*pos,*color)
    for name,wanted in {'context.bin':context,'root.bin':root,'records.bin':record,'output.bin':output,'instance.bin':instance,'vertex-a.bin':vertices,'vertex-b.bin':vertices}.items():
        assert (path/'outputs'/name).read_bytes()==wanted,name
    image=(path/'outputs/image.bin').read_bytes();assert len(image)==49664 and image[:256]==image[-256:]==b'\xa5'*256
    values=struct.unpack('<12288f',image[256:-256]); assert all(math.isfinite(x) for x in values)
    blank=foreign and dispatch;flat=(dispatch!=reverse) and not blank;maximum=0.0
    if flat:
        color=tuple(values[:4]);assert color in ((1.,0.,0.,1.),(0.,1.,0.,1.),(0.,0.,1.,1.)),color
    for y in range(48):
        for x in range(64):
            wx=(x+.5)/128.;wy=(47-y+.5)/96.
            wanted=(0.,0.,0.,0.) if blank else color if flat else (1.-wx-wy,wx,wy,1.)
            for channel in range(4):
                actual=values[(y*64+x)*4+channel];error=abs(actual-wanted[channel]);maximum=max(maximum,error)
                assert error<=3e-5,(x,y,channel,actual,wanted[channel])
    return {'status':'PASS','mode':mode,'checked_float_channels':len(values),'maximum_error':maximum,'dispatches':int(dispatch),
            'pipeline_state':'blank' if blank else 'flat' if flat else 'smooth','native_Apple_ICB_ABI':False,'performance_benchmark':False}
