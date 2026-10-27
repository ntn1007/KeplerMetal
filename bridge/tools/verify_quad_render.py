#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent bounded CPU oracle for the quad render path."""
from pathlib import Path
import math,struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity
from air_vertex_transition import Binding,State,ROW,make_rows
MODES=tuple(f'{p}{i}' for p in ('gpu','native') for i in range(8))+('pipeline_first','pipeline_first_native','draw_first','draw_first_native','reverse','reverse_native','no_dispatch','no_dispatch_native','reset','reset_native','foreign_vertex','foreign_vertex_native','foreign_fragment','foreign_fragment_native','foreign_index','foreign_index_native','bad_index_header','bad_index_header_native','bad_vertex_header','bad_vertex_header_native','bad_pipeline_header','bad_pipeline_header_native','bad_fragment_header','bad_fragment_header_native','contracts')

def verify(path):
 path=Path(path);inputs=read(path/'inputs.json');d=read(path/'results.json');receipt=read(path/'execution/manifest.json');mode=d['mode'];assert mode in MODES and inputs['mode']==mode and d==read(path/'execution/execution.stdout');verify_device_identity(d)
 lease=receipt['GPU_reservation'];assert receipt['exit_code']==0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status'];assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==receipt['pid'] and not lease['known_signed_processes_live']
 assert sha(path/'application')==inputs['executable_SHA256']==receipt['original_binary_sha256'] and sha(path/'execution/application')==receipt['signed_binary_sha256']==lease['signed_binary_sha256']
 for name,digest in inputs['frozen'].items():assert sha(path/name)==digest,name
 assert receipt['launcher_SHA256']==inputs['frozen']['runtime/run_sdk_host.py'] and receipt['reservation_module_SHA256']==inputs['frozen']['runtime/lab_gpu_reservation.py'] and receipt['arguments']==[str(path/'assets'),str(path/'outputs'),mode]
 native=mode.startswith('native') or mode.endswith('native');reverse=mode.startswith('reverse');dispatch=not mode.startswith('no_dispatch');fv=mode.startswith('foreign_vertex');ff=mode.startswith('foreign_fragment');fi=mode.startswith('foreign_index');reset=mode.startswith('reset');bi=mode.startswith('bad_index_header');bv=mode.startswith('bad_vertex_header');bp=mode.startswith('bad_pipeline_header');bf=mode.startswith('bad_fragment_header');order=1 if mode.startswith('pipeline_first') else 2 if mode.startswith('draw_first') else 3 if reset else 0
 mask=int(mode[-1]) if mode.startswith(('gpu','native')) else 7
 assert d['status']=='COMPLETED' and d['command_status']==4 and d['native_Apple_ICB_ABI'] is False and d['performance_benchmark'] is False and d['mask']==mask
 assert d['dispatches']==int(dispatch) and d['native_reference'] is native
 assert d['refusals']==(['vertex_alias','index_alias','fragment_alias','incomplete_root','foreign_pipeline','overlapping_root','tampered_root','prepared_context','restored_scope'] if mode=='contracts' else [])
 cert=read(path/'assets/combined.certificate.json');assert cert['no_native_call'] and cert['driver_SHA256']==inputs['driver_SHA256'] and sha(path/'assets/combined.metallib')==cert['library_SHA256']
 assert d['program']['code_SHA256']==cert['code_SHA256'] and d['program']['own_CPU_staging_code'] and not d['program']['code_replaced'] and not d['program']['constructor_observer_installed'] and sha(path/'outputs/native-program.bin')==cert['code_SHA256'];assert d['inspection']['observer_restored_before_scope'] and d['inspection']['capture']['constructor_restored']
 ids=d['identities'];v=d['vertex_addresses'];f=d['fragment_addresses'];ix=d['index_addresses'];ctx=d['context_address'];records=d['records_address'];assert len(ids)==8 and len(set(ids))==8 and all(x>>32==0x4b505352 for x in ids)
 assert len(set(v+f+ix+[ctx,records]))==13 and all(0<x<2**40 and x%16==0 for x in v+f+ix+[ctx,records])
 a=Binding(11,v[0]-64,64,512);b=Binding(12,v[1]-64,64,512);inst=Binding(13,v[2]-64,64,160);states=[]
 for slot in range(2):
  for state in range(8):states.append(State(ids[state],slot,7+(state//4),((0,(a,b)[state%2]),(1,inst)),((0,21+(state//2)%2),),(slot+30,64,slot+1),(6,1,0,0,slot)))
 rows=make_rows(states);assert len(rows)==48
 assert (d['index_count'],d['transition_count'],d['pipeline_count'],d['fragment_count'])==(16,48,32,32)
 assert (d['context_size'],d['index_table_offset'],d['transition_table_offset'],d['pipeline_table_offset'],d['fragment_table_offset'])==(4640,128,928,2496,3552)
 raw=(path/'outputs/context.bin').read_bytes();assert len(raw)==4640;context=bytearray(b'\xa5'*4640)
 struct.pack_into('<4I2Q',context,64,0x4b505243,1,2,64,records,0);struct.pack_into('<4I2Q',context,96,0x4b504958,1,16,48,ctx+64,0)
 for slot in range(2):
  for state in range(8):struct.pack_into('<3Q4IQ',context,128+(slot*8+state)*48,ids[state],ix[slot],6*(2 if slot==0 else 4),slot,slot+1,6,0,0)
 struct.pack_into('<4I2Q',context,896,0x4b505658,1,48,32,ctx+864,0)
 observed=tuple(ROW.unpack_from(raw,928+i*32)for i in range(48));assert sorted(observed)==sorted(rows) and len(set(observed))==48;context[928:2464]=raw[928:2464]
 struct.pack_into('<4I2Q',context,2464,0x4b505050,1,32,32,ctx+2432,0)
 prows=[struct.unpack_from('<3Q2I',raw,2496+i*32)for i in range(32)];diag={src:token for src,dst,token,slot,res in prows if src==dst and slot==res==0};assert set(diag)==set(ids)
 assert len({diag[x] for x in ids[:4]})==1 and len({diag[x] for x in ids[4:]})==1 and diag[ids[0]]!=diag[ids[4]] and all(t>>32==0x4b and t&0xffffffff for t in diag.values())
 expected={(ids[src],ids[dst],diag[ids[dst]],slot,0)for slot in range(2)for src in range(8)for dst in range(8)if src%4==dst%4};assert set(prows)==expected and len(set(prows))==32;context[2496:3520]=raw[2496:3520]
 struct.pack_into('<4I2Q',context,3520,0x4b504658,1,32,32,ctx+3488,0)
 frows=[ROW.unpack_from(raw,3552+i*32)for i in range(32)];expected={(ids[src],ids[dst],f[(dst//2)%2],slot,0)for slot in range(2)for src in range(8)for dst in range(8)if (src&5)==(dst&5)};assert set(frows)==expected and len(set(frows))==32;context[3552:4576]=raw[3552:4576]
 for flag,off in ((bi,96),(bv,896),(bp,2464),(bf,3520)):
  if flag:struct.pack_into('<I',context,off,0)
 root=bytearray(b'\xa5'*144);struct.pack_into('<2Q',root,64,ctx,diag[ids[0 if reverse or not(mask&2) else 4]])
 useB=not reverse if dispatch and mask&1 else reverse;useP=not reverse if dispatch and mask&2 else reverse;useF=not reverse if dispatch and mask&4 else reverse
 record=bytearray(b'\xa5'*256)
 for slot in range(2):
  if dispatch and (reset or fi or bi):value=bytes(64)
  else:
   identity=0 if dispatch and (fv or ff or bv or bp or bf) else ids[(4 if useP else 0)+(2 if useF else 0)+(1 if useB else 0)]
   value=struct.pack('<8IQ6I',0x4b505353,slot+1,6,1,0,0,slot,0,identity,*([0]*6))
  record[64+slot*64:128+slot*64]=value
 output=bytearray(b'\xa5'*136)
 if dispatch:
  for gid in range(2):struct.pack_into('<I',output,64+gid*4,0x4b505400^gid^order)
 instance=bytearray(b'\xa5'*160);instance[64:96]=bytes(32);struct.pack_into('<f',instance,80,1)
 colorsA=((.75,.125,.25,1),(.5,.375,.25,1),(.25,.625,.25,1),(0,.875,.25,1));colorsB=((.125,.75,.25,1),(.375,.5,.25,1),(.625,.25,.25,1),(.875,0,.25,1))
 def vertex_data(colors):
  data=bytearray(b'\xa5'*512)
  for i,(pos,color) in enumerate(zip(((-1,1,.5,1),(0,1,.5,1),(-1,-1,.5,1),(0,-1,.5,1)),colors)):struct.pack_into('<8f',data,64+(5+i)*32,*pos,*color)
  return data
 def index(wide):
  data=bytearray(b'\xa5'*160);struct.pack_into('<6I' if wide else '<6H',data,64,5,6,7,7,6,8);return data
 expectedFiles={'context.bin':context,'root.bin':root,'records.bin':record,'output.bin':output,'instance.bin':instance,'vertex-a.bin':vertex_data(colorsA),'vertex-b.bin':vertex_data(colorsB),'index16.bin':index(False),'index32.bin':index(True)}
 for i,name in enumerate(('params-a.bin','params-b.bin')):
  data=bytearray(b'\xa5'*512);struct.pack_into('<8f',data,256,*(([1,1,1,1] if i==0 else [.5,.25,.75,1])+[0]*4));expectedFiles[name]=data
 for name,wanted in expectedFiles.items():assert (path/'outputs'/name).read_bytes()==wanted,name
 frag=[]
 for name in ('fragment-a.bin','fragment-b.bin'):
  data=(path/'outputs'/name).read_bytes();assert len(data)==1024 and data[:256]==b'\xa5'*256 and data[280:]==b'\xa5'*744 and data[256:280]!=b'\xa5'*24;frag.append(data[256:280])
 assert frag[0]!=frag[1]
 texture=(path/'outputs/texture.bin').read_bytes();image=(path/'outputs/image.bin').read_bytes()
 for data in (texture,image):assert len(data)==49664 and data[:256]==data[-256:]==b'\xa5'*256
 tv=struct.unpack('<12288f',texture[256:-256]);assert all(x==1 for x in tv)
 empty=dispatch and(fv or ff or fi or reset or bi or bv or bp or bf);scale=(.5,.25,.75,1) if useF else (1,1,1,1);values=struct.unpack('<12288f',image[256:-256]);maximum=0.;flatGroups={}
 for y in range(48):
  for x in range(64):
   u=((x%32)+.5)/32.;vcoord=(y+.5)/48.;slot=x//32;z=.25+slot/64.
   if empty:wanted=(0.,0.,0.,0.)
   elif not useP:
    rr=(.125+.25*u+.5*vcoord) if useB else (.75-.25*u-.5*vcoord);gg=(.75-.25*u-.5*vcoord) if useB else (.125+.25*u+.5*vcoord);wanted=(rr*scale[0],gg*scale[1],z*scale[2],1.)
   else:
    actual=tuple(values[(y*64+x)*4+i]for i in range(4));allowed=[(c[0]*scale[0],c[1]*scale[1],(c[2]+slot/64.)*scale[2],c[3]) for c in (colorsB if useB else colorsA)];assert actual in allowed,(x,y,actual,allowed)
    key=(slot,u+vcoord>1.);previous=flatGroups.setdefault(key,actual);assert previous==actual;(wanted)=actual
   for channel in range(4):
    value=values[(y*64+x)*4+channel];error=abs(value-wanted[channel]);assert math.isfinite(value) and error<=3e-5,(x,y,channel,value,wanted[channel]);maximum=max(maximum,error)
 return {'status':'PASS','mode':mode,'checked_float_channels':len(values),'texture_channels':len(tv),'maximum_error':maximum,'producer_dispatches':int(dispatch),'index_rows_checked':16,'vertex_rows_checked':48,'pipeline_rows_checked':32,'fragment_rows_checked':32,'native_Apple_ICB_ABI':False,'performance_benchmark':False}
