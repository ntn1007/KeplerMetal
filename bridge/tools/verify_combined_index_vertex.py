#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU check for dual-root indexed and vertex rendering."""
from pathlib import Path
import math
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity
from air_vertex_transition import Binding,State,ROW,make_rows
MODES=('gpu','native','no_dispatch','no_dispatch_native','disabled','disabled_native','draw_first','draw_first_native','reset','reset_native','foreign_vertex','foreign_vertex_native','foreign_index','foreign_index_native','missing_vertex','missing_vertex_native','missing_index','missing_index_native','reverse','reverse_native')


def verify(path):
 path=Path(path);inputs=read(path/'inputs.json');d=read(path/'results.json');receipt=read(path/'execution/manifest.json');mode=d['mode']
 assert mode in MODES and inputs['mode']==mode and d==read(path/'execution/execution.stdout');verify_device_identity(d)
 lease=receipt['GPU_reservation'];assert receipt['exit_code']==0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status']
 assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==receipt['pid'] and not lease['known_signed_processes_live']
 assert sha(path/'application')==inputs['executable_SHA256']==receipt['original_binary_sha256']
 assert sha(path/'execution/application')==receipt['signed_binary_sha256']==lease['signed_binary_sha256']
 for name,digest in inputs['frozen'].items():assert sha(path/name)==digest,name
 assert receipt['launcher_SHA256']==inputs['frozen']['runtime/run_sdk_host.py'] and receipt['reservation_module_SHA256']==inputs['frozen']['runtime/lab_gpu_reservation.py']
 assert receipt['arguments']==[str(path/'assets'),str(path/'outputs'),mode]
 assert d['status']=='COMPLETED' and d['command_status']==4 and d['native_Apple_ICB_ABI'] is False and d['performance_benchmark'] is False
 native=mode.endswith('native');reverse=mode.startswith('reverse');dispatch=not mode.startswith('no_dispatch');enabled=not mode.startswith('disabled');fv=mode.startswith('foreign_vertex');fi=mode.startswith('foreign_index');mv=mode.startswith('missing_vertex');mi=mode.startswith('missing_index');reset=mode.startswith('reset');order=1 if mode.startswith('draw_first') else 2 if reset else 0
 assert d['dispatches']==int(dispatch) and d['native_reference'] is native
 cert=read(path/'assets/combined.certificate.json');assert cert['no_native_call'] and cert['driver_SHA256']==inputs['driver_SHA256'] and sha(path/'assets/combined.metallib')==cert['library_SHA256']
 assert d['program']['code_SHA256']==cert['code_SHA256'] and d['program']['own_CPU_staging_code'] and not d['program']['code_replaced'] and not d['program']['constructor_observer_installed'] and sha(path/'outputs/native-program.bin')==cert['code_SHA256']
 assert d['inspection']['observer_restored_before_scope'] and d['inspection']['capture']['constructor_restored']
 ids=d['identities'];v=d['vertex_addresses'];ix=d['index_addresses'];ctx=d['context_address'];records=d['records_address'];assert len(ids)==2 and len(set(ids))==2 and all(x>>32==0x4b505352 for x in ids)
 assert len(set(v+ix+[ctx,records]))==10 and all(0<x<2**40 and x%16==0 for x in v+ix+[ctx,records])
 a=Binding(11,v[0]-64,64,512);b=Binding(12,v[1]-64,64,512);instance=Binding(13,v[2]-64,64,160);states=[]
 for slot in range(2):
  for state,binding in enumerate((a,b)):
   states.append(State(ids[state],slot,7,((0,binding),(1,instance)),(),(slot+30,64,slot+1),(6,1,0,0,slot)))
 rows=make_rows(states);assert len(rows)==12
 want_index=0 if mi else 4;want_vertex=0 if mv else 12
 assert (d['index_count'],d['transition_count'])==(want_index,want_vertex)
 size=160 if not want_index and not want_vertex else 192+want_index*48+want_vertex*32+(32 if want_index and want_vertex else 0)
 assert d['context_size']==size
 raw=(path/'outputs/context.bin').read_bytes();assert len(raw)==size;context=bytearray(b'\xa5'*size)
 struct.pack_into('<4I2Q',context,64,0x4b505243,1,2,64,records,0)
 if want_index:
  assert d['index_table_offset']==128;struct.pack_into('<4I2Q',context,96,0x4b504958,1,4,48,ctx+64,0)
  for slot in range(2):
   for state in range(2):struct.pack_into('<3Q4IQ',context,128+(slot*2+state)*48,ids[state],ix[slot],6*(2 if slot==0 else 4),slot,slot+1,6,0,0)
 else:assert d['index_table_offset']==0
 if want_vertex:
  head=128+want_index*48 if want_index else 96;table=head+32;assert d['transition_table_offset']==table
  struct.pack_into('<4I2Q',context,head,0x4b505658,1,12,32,ctx+(table-64),0)
  observed=tuple(ROW.unpack_from(raw,table+i*ROW.size)for i in range(12));assert sorted(observed)==sorted(rows) and len(set(observed))==12;context[table:table+12*32]=raw[table:table+12*32]
 else:assert d['transition_table_offset']==0
 root=bytearray(b'\xa5'*136);struct.pack_into('<Q',root,64,ctx)
 record=bytearray(b'\xa5'*256)
 for slot in range(2):
  if dispatch and (reset or fi or mi):value=bytes(64)
  else:
   identity=(0 if dispatch and (fv or mv) else ids[0 if reverse else 1] if dispatch and enabled else ids[1 if reverse else 0])
   value=struct.pack('<8IQ6I',0x4b505353,slot+1,6,1,0,0,slot,0,identity,*([0]*6))
  record[64+slot*64:128+slot*64]=value
 output=bytearray(b'\xa5'*136)
 if dispatch:
  for gid in range(2):struct.pack_into('<I',output,64+gid*4,0x4b504d00^gid^order)
 instance_data=bytearray(b'\xa5'*160);instance_data[64:96]=bytes(32);struct.pack_into('<f',instance_data,80,1)
 def vertex(color):
  data=bytearray(b'\xa5'*512)
  for i,pos in enumerate(((-1,1,.5,1),(0,1,.5,1),(-1,-1,.5,1),(0,-1,.5,1))):struct.pack_into('<8f',data,64+(5+i)*32,*pos,*color)
  return data
 def index(wide):
  data=bytearray(b'\xa5'*160);struct.pack_into('<6I' if wide else '<6H',data,64,5,6,7,7,6,8);return data
 expected={'context.bin':context,'root.bin':root,'records.bin':record,'output.bin':output,'instance.bin':instance_data,'vertex-a.bin':vertex((.75,.125,.25,1)),'vertex-b.bin':vertex((.125,.75,.25,1)),'index16.bin':index(False),'index32.bin':index(True)}
 for name,wanted in expected.items():assert (path/'outputs'/name).read_bytes()==wanted,name
 image=(path/'outputs/image.bin').read_bytes();assert len(image)==49664 and image[:256]==image[-256:]==b'\xa5'*256
 empty=dispatch and(fv or fi or mv or mi or reset);switched=(dispatch and enabled)!=reverse;values=struct.unpack('<12288f',image[256:-256]);maximum=0.0
 for i,value in enumerate(values):
  pixel=i//4;x=pixel%64;component=i%4;wanted=(0.,0.,0.,0.) if empty else ((.125,.75,.25+(1/64 if x>=32 else 0),1.) if switched else (.75,.125,.25+(1/64 if x>=32 else 0),1.));error=abs(value-wanted[component]);assert math.isfinite(value) and error<=2e-6,(i,value,wanted[component]);maximum=max(maximum,error)
 return {'status':'PASS','mode':mode,'checked_float_channels':len(values),'maximum_error':maximum,'producer_dispatches':int(dispatch),'index_rows_checked':want_index,'vertex_rows_checked':want_vertex,'guard_and_record_buffers_checked':len(expected),'native_Apple_ICB_ABI':False,'performance_benchmark':False}
