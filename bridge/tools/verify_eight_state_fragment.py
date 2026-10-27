#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU oracle for 8-state actual GPU fragment-selection qualification."""
from pathlib import Path
import math
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity
MODES=tuple(f'{p}{i}' for p in ('gpu','native') for i in range(8))
EXTRA_MODES=('foreign','foreign_native','contracts')

def verify(path):
 path=Path(path); inputs=read(path/'inputs.json'); d=read(path/'results.json'); receipt=read(path/'execution/manifest.json'); mode=d['mode']
 assert mode in MODES+EXTRA_MODES and mode==inputs['mode'] and d==read(path/'execution/execution.stdout')
 verify_device_identity(d);lease=receipt['GPU_reservation'];assert receipt['exit_code']==0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status']
 assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==receipt['pid'] and not lease['known_signed_processes_live']
 assert sha(path/'application')==inputs['executable_SHA256']==receipt['original_binary_sha256']
 assert sha(path/'execution/application')==receipt['signed_binary_sha256']==lease['signed_binary_sha256']
 for name,digest in inputs['frozen'].items():assert sha(path/name)==digest,name
 assert receipt['launcher_SHA256']==inputs['frozen']['runtime/run_sdk_host.py'] and receipt['reservation_module_SHA256']==inputs['frozen']['runtime/lab_gpu_reservation.py']
 assert receipt['arguments']==[str(path/'assets'),str(path/'outputs'),mode]
 native=mode.startswith('native') or mode.endswith('native');foreign=mode.startswith('foreign');target=7 if foreign or mode=='contracts' else int(mode[-1])
 assert d['status']=='COMPLETED' and d['command_status']==4 and d['dispatches']==1 and d['native_reference'] is native and d['selected']==target
 assert d['native_Apple_ICB_ABI'] is False and d['performance_benchmark'] is False
 assert d['refusals']==(['nine_states','twenty_four_slots','fragment_root_alias'] if mode=='contracts' else [])
 cert=read(path/'assets/fragment.certificate.json');assert cert['no_native_call'] and cert['driver_SHA256']==inputs['driver_SHA256']
 assert sha(path/'assets/fragment.metallib')==cert['library_SHA256']
 assert d['program']['code_SHA256']==cert['code_SHA256'] and d['program']['own_CPU_staging_code'] and not d['program']['code_replaced'] and not d['program']['constructor_observer_installed']
 assert sha(path/'outputs/native-program.bin')==cert['code_SHA256'] and d['inspection']['observer_restored_before_scope'] and d['inspection']['capture']['constructor_restored']
 ids=d['identities'];addr=d['fragment_addresses'];ctx=d['context_address'];records=d['records_address']
 assert len(ids)==8 and len(set(ids))==8 and all(x>>32==0x4b505352 for x in ids)
 assert len(addr)==9 and len(set(addr+[ctx,records]))==11 and all(0<x<2**40 and x%16==0 for x in addr+[ctx,records])
 assert d['transition_count']==64 and d['transition_table_offset']==128 and d['context_size']==2240
 actual=(path/'outputs/context.bin').read_bytes();row=struct.Struct('<QQQII');observed=[row.unpack_from(actual,128+i*32) for i in range(64)]
 expected=[(old,new,ptr,0,0) for old in ids for new,ptr in zip(ids,addr[:8])];assert sorted(observed)==sorted(expected) and len(set(observed))==64
 context=bytearray(b'\xa5'*2240);struct.pack_into('<4I2Q',context,64,0x4b505243,1,1,64,records,0);struct.pack_into('<4I2Q',context,96,0x4b504658,1,64,32,ctx+64,0);context[128:2176]=actual[128:2176]
 root=bytearray(b'\xa5'*136);struct.pack_into('<Q',root,64,ctx)
 record=bytearray(b'\xa5'*192);struct.pack_into('<8IQ6I',record,64,0x4b505353,0,3,1,0,0,0,0,0 if foreign else ids[target],*([0]*6))
 output=bytearray(b'\xa5'*132);struct.pack_into('<I',output,64,0x4b504600)
 expected_files={'context.bin':context,'root.bin':root,'records.bin':record,'output.bin':output}
 args=[]
 for i in range(8):
  data=bytearray(b'\xa5'*512);struct.pack_into('<8f',data,256,*([(i+1)/8]*3+[1]+[0]*4));expected_files[f'params-{i}.bin']=data
  a=(path/f'outputs/arguments-{i}.bin').read_bytes();assert len(a)==1024 and a[:256]==b'\xa5'*256 and a[280:]==b'\xa5'*744 and a[256:280]!=b'\xa5'*24;args.append(a[256:280])
 assert len(set(args))==8
 for name,wanted in expected_files.items():assert (path/'outputs'/name).read_bytes()==wanted,name
 texture=(path/'outputs/texture.bin').read_bytes();image=(path/'outputs/image.bin').read_bytes()
 for data in (texture,image):assert len(data)==49664 and data[:256]==data[-256:]==b'\xa5'*256
 tvalues=struct.unpack('<12288f',texture[256:-256]);assert all(x==(.25,.5,.75,1)[i%4] for i,x in enumerate(tvalues))
 scale=(target+1)/8;wanted=(0,0,0,0) if foreign else (.25*scale,.5*scale,.75*scale,1)
 values=struct.unpack('<12288f',image[256:-256]);maximum=0.0
 for i,value in enumerate(values):
  error=abs(value-wanted[i%4]);assert math.isfinite(value) and error<=2e-6,(i,value,wanted[i%4]);maximum=max(maximum,error)
 return {'status':'PASS','mode':mode,'checked_float_channels':len(values),'texture_channels':len(tvalues),'maximum_error':maximum,'fragment_rows_checked':len(observed),'dispatches':1,'native_Apple_ICB_ABI':False,'performance_benchmark':False}
