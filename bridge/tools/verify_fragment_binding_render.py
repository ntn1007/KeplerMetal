#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU oracle for the bounded, signed fragment-transition probe."""
from pathlib import Path
import math
import struct
from public_large_scratch import read, sha
from verify_local_memory import verify_device_identity

MODES=('gpu','native','no_dispatch','no_dispatch_native','disabled','disabled_native','foreign','foreign_native')
EXTRA_MODES=('reverse','reverse_native','missing','missing_native','bad_header','bad_header_native','contracts')


def verify(path):
    path=Path(path); inputs=read(path/'inputs.json'); d=read(path/'results.json'); receipt=read(path/'execution/manifest.json'); mode=d['mode']
    assert mode in MODES+EXTRA_MODES and inputs['mode']==mode and d==read(path/'execution/execution.stdout')
    verify_device_identity(d)
    lease=receipt['GPU_reservation']; assert receipt['exit_code']==0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==receipt['pid'] and not lease['known_signed_processes_live']
    assert sha(path/'application')==inputs['executable_SHA256']==receipt['original_binary_sha256']
    assert sha(path/'execution/application')==receipt['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in inputs['frozen'].items(): assert sha(path/name)==digest,name
    assert receipt['launcher_SHA256']==inputs['frozen']['runtime/run_sdk_host.py'] and receipt['reservation_module_SHA256']==inputs['frozen']['runtime/lab_gpu_reservation.py']
    assert receipt['arguments']==[str(path/'assets'),str(path/'outputs'),mode]
    assert d['status']=='COMPLETED' and d['command_status']==4 and d['native_Apple_ICB_ABI'] is False and d['performance_benchmark'] is False
    reverse=mode.startswith('reverse'); dispatch=not mode.startswith('no_dispatch'); enabled=not mode.startswith('disabled'); native=mode.endswith('native'); invalid=mode.startswith(('foreign','missing','bad_header'))
    assert d['dispatches']==int(dispatch) and d['native_reference'] is native
    assert d['refusals']==(['fragment_root_alias'] if mode=='contracts' else [])
    cert=read(path/'assets/fragment.certificate.json'); assert cert['no_native_call'] and cert['driver_SHA256']==inputs['driver_SHA256']
    assert sha(path/'assets/fragment.metallib')==cert['library_SHA256']
    assert d['program']['code_SHA256']==cert['code_SHA256'] and d['program']['own_CPU_staging_code'] and not d['program']['code_replaced'] and not d['program']['constructor_observer_installed']
    assert sha(path/'outputs/native-program.bin')==cert['code_SHA256']
    assert d['inspection']['observer_restored_before_scope'] and d['inspection']['capture']['constructor_restored']
    ids=d['identities']; addr=d['fragment_addresses']; ctx=d['context_address']; records=d['records_address']
    assert len(ids)==2 and len(set(ids))==2 and all(x>>32==0x4b505352 for x in ids)
    assert len(set(addr+[ctx,records]))==5 and all(0<x<2**40 and x%16==0 for x in addr+[ctx,records])
    missing=mode.startswith('missing'); size=160 if missing else 320; assert d['context_size']==size
    context=bytearray(b'\xa5'*size); struct.pack_into('<4I2Q',context,64,0x4b505243,1,1,64,records,0)
    if not missing:
        assert d['transition_count']==4 and d['transition_table_offset']==128
        actual=(path/'outputs/context.bin').read_bytes(); row=struct.Struct('<QQQII')
        observed=[row.unpack_from(actual,128+i*row.size) for i in range(4)]
        expected=[(old,new,ptr,0,0) for old in ids for new,ptr in zip(ids,addr[:2])]
        assert sorted(observed)==sorted(expected), (observed,expected)
        struct.pack_into('<4I2Q',context,96,0 if mode.startswith('bad_header') else 0x4b504658,1,4,32,ctx+64,0)
        context[128:256]=actual[128:256]
    else: assert d['transition_count']==0
    root=bytearray(b'\xa5'*136); struct.pack_into('<Q',root,64,ctx)
    ident=ids[1 if reverse else 0] if not dispatch or not enabled else 0 if invalid else ids[0 if reverse else 1]
    record=bytearray(b'\xa5'*192); struct.pack_into('<8IQ6I',record,64,0x4b505353,0,3,1,0,0,0,0,ident,*([0]*6))
    output=bytearray(b'\xa5'*132)
    if dispatch: struct.pack_into('<I',output,64,0x4b504600)
    expected_files={'context.bin':context,'root.bin':root,'records.bin':record,'output.bin':output}
    for i,name in enumerate(('params-a.bin','params-b.bin')):
        data=bytearray(b'\xa5'*512); struct.pack_into('<8f',data,256,*(([1,1,1,1] if i==0 else [.5,.5,.5,1])+[0]*4)); expected_files[name]=data
    for name,wanted in expected_files.items(): assert (path/'outputs'/name).read_bytes()==wanted,name
    args=[]
    for name in ('arguments-a.bin','arguments-b.bin'):
        data=(path/'outputs'/name).read_bytes(); assert len(data)==1024 and data[:256]==b'\xa5'*256 and data[280:]==b'\xa5'*(1024-280) and data[256:280]!=b'\xa5'*24,name; args.append(data[256:280])
    assert args[0]!=args[1]
    texture=(path/'outputs/texture.bin').read_bytes(); image=(path/'outputs/image.bin').read_bytes()
    for data in (texture,image): assert len(data)==49664 and data[:256]==data[-256:]==b'\xa5'*256
    tvalues=struct.unpack('<12288f',texture[256:-256]); assert all(x==(.25,.5,.75,1)[i%4] for i,x in enumerate(tvalues))
    wanted=(0,0,0,0) if invalid and dispatch and enabled else ((.125,.25,.375,1) if (dispatch and enabled)!=reverse else (.25,.5,.75,1))
    values=struct.unpack('<12288f',image[256:-256]); maximum=0.0
    for i,value in enumerate(values):
        error=abs(value-wanted[i%4]); assert math.isfinite(value) and error<=2e-6,(i,value,wanted[i%4]); maximum=max(maximum,error)
    return {'status':'PASS','mode':mode,'checked_float_channels':len(values),'texture_channels':len(tvalues),'maximum_error':maximum,'dispatches':int(dispatch),'fragment_rows_checked':0 if missing else 4,'guard_and_record_buffers_checked':len(expected_files)+4,'native_Apple_ICB_ABI':False,'performance_benchmark':False}
