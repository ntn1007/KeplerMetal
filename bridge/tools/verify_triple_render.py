#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU check for triple-context indexed, vertex and pipeline rendering."""
from pathlib import Path
import math
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity
from air_vertex_transition import Binding,State,ROW,make_rows
MODES=('gpu','native','no_dispatch','no_dispatch_native','vertex_only','vertex_only_native','pipeline_only','pipeline_only_native','pipeline_first','pipeline_first_native','draw_first','draw_first_native','reset','reset_native','foreign_vertex','foreign_vertex_native','foreign_index','foreign_index_native','reverse','reverse_native','contracts','bad_index_header','bad_index_header_native','bad_vertex_header','bad_vertex_header_native','bad_pipeline_header','bad_pipeline_header_native')

def choices(mode):
 assert mode in MODES
 reverse=mode.startswith('reverse');dispatch=not mode.startswith('no_dispatch')
 useB=(not reverse) if dispatch and not mode.startswith('pipeline_only') else reverse
 useFlat=(not reverse) if dispatch and not mode.startswith('vertex_only') else reverse
 return useB,useFlat


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
 native=mode.endswith('native');reverse=mode.startswith('reverse');dispatch=not mode.startswith('no_dispatch');fv=mode.startswith('foreign_vertex');fi=mode.startswith('foreign_index');reset=mode.startswith('reset');badIndex=mode.startswith('bad_index_header');badVertex=mode.startswith('bad_vertex_header');badPipeline=mode.startswith('bad_pipeline_header');vertex=not mode.startswith('pipeline_only');pipeline=not mode.startswith('vertex_only');order=1 if mode.startswith('pipeline_first') else 2 if mode.startswith('draw_first') else 3 if reset else 0
 assert d['dispatches']==int(dispatch) and d['native_reference'] is native
 assert d['refusals']==(['vertex_alias','index_alias','incomplete_root','foreign_pipeline','overlapping_root','tampered_root','prepared_context','restored_scope'] if mode=='contracts' else [])
 cert=read(path/'assets/combined.certificate.json');assert cert['no_native_call'] and cert['driver_SHA256']==inputs['driver_SHA256'] and sha(path/'assets/combined.metallib')==cert['library_SHA256']
 assert d['program']['code_SHA256']==cert['code_SHA256'] and d['program']['own_CPU_staging_code'] and not d['program']['code_replaced'] and not d['program']['constructor_observer_installed'] and sha(path/'outputs/native-program.bin')==cert['code_SHA256']
 assert d['inspection']['observer_restored_before_scope'] and d['inspection']['capture']['constructor_restored']
 ids=d['identities'];v=d['vertex_addresses'];ix=d['index_addresses'];ctx=d['context_address'];records=d['records_address'];assert len(ids)==4 and len(set(ids))==4 and all(x>>32==0x4b505352 for x in ids)
 assert len(set(v+ix+[ctx,records]))==10 and all(0<x<2**40 and x%16==0 for x in v+ix+[ctx,records])
 a=Binding(11,v[0]-64,64,512);b=Binding(12,v[1]-64,64,512);instance=Binding(13,v[2]-64,64,160);states=[]
 for slot in range(2):
  for state in range(4):states.append(State(ids[state],slot,7+state//2,((0,(a,b)[state%2]),(1,instance)),(),(slot+30,64,slot+1),(6,1,0,0,slot)))
 rows=make_rows(states);assert len(rows)==24
 assert (d['index_count'],d['transition_count'],d['pipeline_count'])==(8,24,16)
 assert d['context_size']==1920 and d['index_table_offset']==128 and d['transition_table_offset']==544 and d['pipeline_table_offset']==1344
 raw=(path/'outputs/context.bin').read_bytes();assert len(raw)==1920;context=bytearray(b'\xa5'*1920)
 struct.pack_into('<4I2Q',context,64,0x4b505243,1,2,64,records,0);struct.pack_into('<4I2Q',context,96,0x4b504958,1,8,48,ctx+64,0)
 for slot in range(2):
  for state in range(4):struct.pack_into('<3Q4IQ',context,128+(slot*4+state)*48,ids[state],ix[slot],6*(2 if slot==0 else 4),slot,slot+1,6,0,0)
 struct.pack_into('<4I2Q',context,512,0x4b505658,1,24,32,ctx+480,0)
 observed=tuple(ROW.unpack_from(raw,544+i*ROW.size)for i in range(24));assert sorted(observed)==sorted(rows) and len(set(observed))==24;context[544:1312]=raw[544:1312]
 struct.pack_into('<4I2Q',context,1312,0x4b505050,1,16,32,ctx+1280,0)
 if badIndex:struct.pack_into('<I',context,96,0)
 if badVertex:struct.pack_into('<I',context,512,0)
 if badPipeline:struct.pack_into('<I',context,1312,0)
 prows=[struct.unpack_from('<3Q2I',raw,1344+i*32)for i in range(16)]
 diagonal={src:token for src,dst,token,slot,reserved in prows if src==dst and slot==reserved==0};assert set(diagonal)==set(ids)
 assert diagonal[ids[0]]==diagonal[ids[1]] and diagonal[ids[2]]==diagonal[ids[3]] and diagonal[ids[0]]!=diagonal[ids[2]]
 assert all(token>>32==0x4b and token&0xffffffff for token in diagonal.values())
 expected_rows={(ids[src],ids[dst],diagonal[ids[dst]],slot,0) for slot in range(2) for src in range(4) for dst in range(4) if src%2==dst%2}
 assert set(prows)==expected_rows and len(set(prows))==16;context[1344:1856]=raw[1344:1856]
 root=bytearray(b'\xa5'*144);struct.pack_into('<2Q',root,64,ctx,diagonal[ids[0 if reverse else 2]])
 record=bytearray(b'\xa5'*256)
 for slot in range(2):
  if dispatch and (reset or fi or badIndex):value=bytes(64)
  else:
   useB,useFlat=choices(mode)
   identity=0 if dispatch and (fv or badVertex or badPipeline) else ids[(2 if useFlat else 0)+(1 if useB else 0)]
   value=struct.pack('<8IQ6I',0x4b505353,slot+1,6,1,0,0,slot,0,identity,*([0]*6))
  record[64+slot*64:128+slot*64]=value
 output=bytearray(b'\xa5'*136)
 if dispatch:
  for gid in range(2):struct.pack_into('<I',output,64+gid*4,0x4b505400^gid^order)
 instance_data=bytearray(b'\xa5'*160);instance_data[64:96]=bytes(32);struct.pack_into('<f',instance_data,80,1)
 def vertex_data(colors):
  data=bytearray(b'\xa5'*512)
  for i,(pos,color) in enumerate(zip(((-1,1,.5,1),(0,1,.5,1),(-1,-1,.5,1),(0,-1,.5,1)),colors)):struct.pack_into('<8f',data,64+(5+i)*32,*pos,*color)
  return data
 colorsA=((.75,.125,.25,1),(.5,.375,.25,1),(.25,.625,.25,1),(0,.875,.25,1))
 colorsB=((.125,.75,.25,1),(.375,.5,.25,1),(.625,.25,.25,1),(.875,0,.25,1))
 def index(wide):
  data=bytearray(b'\xa5'*160);struct.pack_into('<6I' if wide else '<6H',data,64,5,6,7,7,6,8);return data
 expected={'context.bin':context,'root.bin':root,'records.bin':record,'output.bin':output,'instance.bin':instance_data,'vertex-a.bin':vertex_data(colorsA),'vertex-b.bin':vertex_data(colorsB),'index16.bin':index(False),'index32.bin':index(True)}
 for name,wanted in expected.items():assert (path/'outputs'/name).read_bytes()==wanted,name
 image=(path/'outputs/image.bin').read_bytes();assert len(image)==49664 and image[:256]==image[-256:]==b'\xa5'*256
 empty=dispatch and(fv or fi or reset or badIndex or badVertex or badPipeline);useB,useFlat=choices(mode)
 values=struct.unpack('<12288f',image[256:-256]);maximum=0.0;flatGroups={}
 for y in range(48):
  for x in range(64):
   u=((x%32)+.5)/32.;vcoord=(y+.5)/48.;slot=x//32;z=.25+slot/64.
   if empty:wanted=(0.,0.,0.,0.)
   elif not useFlat:
    r=(.125+.25*u+.5*vcoord) if useB else (.75-.25*u-.5*vcoord);g=(.75-.25*u-.5*vcoord) if useB else (.125+.25*u+.5*vcoord);wanted=(r,g,z,1.)
   else:
    actual=tuple(values[(y*64+x)*4+i]for i in range(4));allowed=[(c[0],c[1],c[2]+slot/64.,c[3])for c in (colorsB if useB else colorsA)];assert actual in allowed,(x,y,actual)
    key=(slot,u+vcoord>1.);previous=flatGroups.setdefault(key,actual);assert previous==actual,(x,y,previous,actual);wanted=actual
   for channel in range(4):
    value=values[(y*64+x)*4+channel];error=abs(value-wanted[channel]);assert math.isfinite(value) and error<=3e-5,(x,y,channel,value,wanted[channel]);maximum=max(maximum,error)

 return {'status':'PASS','mode':mode,'checked_float_channels':len(values),'maximum_error':maximum,'producer_dispatches':int(dispatch),'index_rows_checked':8,'vertex_rows_checked':24,'pipeline_rows_checked':16,'guard_and_record_buffers_checked':len(expected),'native_Apple_ICB_ABI':False,'performance_benchmark':False}
