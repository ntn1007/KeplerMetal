#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only one-reference POC2 fixture check; never submit proposal bytes."""
import argparse,ctypes,hashlib,json,re,struct,subprocess
from pathlib import Path
from validate_baseline import fields
HERE=Path(__file__).resolve().parent
PINS={'fixture.h264':'4b4f9fb55be0741a00991bdf81b3b93147525e3268b0d0a2140e549ed13a4323',
      'trace.txt':'8183ad26ddc957ece8349033753a19b732ecc22894da7f28e6bc19106b11db90',
      'packets.json':'04ce8e5b831693b99c4410a1be81bcfe0f9a8ea5b3a3ab566f83887dd1f18709'}
MESA='db6a036b28510c9b1940e5457c6b9c4b15f0dd6217826d6da7e42e01d7374005'
NAMES=('H264Stream.h','H264Stream.cpp','H264Baseline.h','H264Baseline.cpp','VideoLayout.h','VideoLayout.cpp','VideoPicture.h','VideoPicture.cpp','VideoIdr.h','VideoIdr.cpp','VideoPredictive.h','VideoPredictive.cpp','predictive_picture_tool.cpp','test_baseline.cpp','test_video_idr.cpp','test_video_predictive.cpp','validate_one_reference.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,msg):
 if not x:raise ValueError(msg)
def run(out,label,args):
 r=subprocess.run(list(map(str,args)),capture_output=True,timeout=120);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr);need(r.returncode==0,label+' failed');return r.stdout

def main():
 a=argparse.ArgumentParser();a.add_argument('--fixture',type=Path,required=True);a.add_argument('--mesa',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a=a.parse_args()
 need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required');need(all(sha(a.fixture/n)==h for n,h in PINS.items()) and sha(a.mesa)==MESA,'input pin differs');before={n:sha(HERE/n) for n in NAMES}
 trace=(a.fixture/'trace.txt').read_text();sp=fields(trace.split('Sequence Parameter Set',1)[1].split('Picture Parameter Set',1)[0]);pp=fields(trace.split('Picture Parameter Set',1)[1].split('Stream mapping:',1)[0]);packets=re.split(r'\[trace_headers @ [^\]]+\] Packet:',trace)[1:]
 need(len(packets)==6 and sp['profile_idc']==66 and sp['pic_order_cnt_type']==2 and sp['max_num_ref_frames']==1 and sp['frame_mbs_only_flag']==1 and sp['frame_cropping_flag']==0 and pp['num_ref_idx_l0_default_active_minus1']==0 and pp['entropy_coding_mode_flag']==pp['weighted_pred_flag']==pp['weighted_bipred_idc']==0,'profile differs')
 for i,packet in enumerate(packets):
  slices=[fields(x) for x in packet.split('Slice Header')[1:]]
  need(len(slices)==2 and [s['first_mb_in_slice'] for s in slices]==[0,160] and all(s['slice_type']==(7 if i==0 else 5) and s['frame_num']==i and s['nal_ref_idc']!=0 and s['nal_unit_type']==(5 if i==0 else 1) and s['pic_parameter_set_id']==pp['pic_parameter_set_id'] for s in slices),'slice headers differ')
  if i:need(all(s['num_ref_idx_active_override_flag']==s['ref_pic_list_modification_flag_l0']==s['adaptive_ref_pic_marking_mode_flag']==0 for s in slices),'P controls differ')
 data=(a.fixture/'fixture.h264').read_bytes();pk=json.loads((a.fixture/'packets.json').read_text())['packets'];need(len(pk)==6,'packet count')
 a.out.mkdir();params={};previous=0
 for i,item in enumerate(pk):
  start=int(item['pos']);end=start+int(item['size']);need(start==previous and end<=len(data),'packet boundary');previous=end;blob=data[start:end];starts=list(re.finditer(rb'\x00\x00\x00\x01|\x00\x00\x01',blob));need(starts and starts[0].start()==0,'start code');units=[]
  for j,match in enumerate(starts):
   nal=blob[match.end():starts[j+1].start() if j+1<len(starts) else len(blob)];need(bool(nal),'empty NAL');t=nal[0]&31
   if t in (7,8):need(t not in params or params[t]==nal,'different parameter set');params[t]=nal
   elif t in (1,5,6):units.append(nal)
   else:raise ValueError('unexpected NAL')
  need(sum((x[0]&31) in (1,5) for x in units)==2,'slice count')
  (a.out/f'frame-{i:03d}.avcc').write_bytes(b''.join(struct.pack('>I',len(x))+x for x in units))
 need(previous==len(data) and set(params)=={7,8},'incomplete packet coverage')
 for typ in (7,8):(a.out/f'param-{typ-7}.bin').write_bytes(params[typ])
 flags=['-std=c++17','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all'];sources=[HERE/n for n in ('H264Stream.cpp','H264Baseline.cpp','VideoLayout.cpp','VideoPicture.cpp','VideoIdr.cpp','VideoPredictive.cpp')]
 for name in ('test_baseline','test_video_idr','test_video_predictive'):
  run(a.out,'build-'+name,['xcrun','clang++',*flags,*sources,HERE/(name+'.cpp'),'-o',a.out/name]);run(a.out,name,[a.out/name])
 run(a.out,'build-tool',['xcrun','clang++',*flags,*sources,HERE/'predictive_picture_tool.cpp','-o',a.out/'tool']);lines=run(a.out,'prepare',[a.out/'tool',a.out/'param-0.bin',a.out/'param-1.bin',a.out,a.out]).decode().splitlines();need(len(lines)==5,'proposal count')
 run(a.out,'build-mesa',['xcrun','clang','-std=gnu11','-dynamiclib',a.mesa,'-o',a.out/'mesa.dylib']);lib=ctypes.CDLL(str((a.out/'mesa.dylib').resolve()));fn=lib.mesa_vp_reference;fn.argtypes=[ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(ctypes.c_uint32)];fn.restype=ctypes.c_uint32
 rows=[];w=(sp['pic_width_in_mbs_minus1']+1)*16;h=(sp['pic_height_in_map_units_minus1']+1)*16;need((w,h)==(320,240),'dimensions')
 for i,line in enumerate(lines,1):
  target=i%2;refslot=(i-1)%2;need(json.loads(line)=={'frame':i,'poc':0,'refs':1,'target_slot':target,'simple':1,'caps':0x1113},'proposal metadata')
  x=(ctypes.c_uint32*256)();x[0]=w;x[1]=h;x[2]=2;x[3]=1;x[4]=1;x[5]=target
  x[6]=(sp['direct_8x8_inference_flag']<<1)|(pp['weighted_pred_flag']<<2)|(pp['constrained_intra_pred_flag']<<3)|16
  x[7]=sp['log2_max_frame_num_minus4'];x[8]=2;x[9]=pp['pic_init_qp_minus26']&0xffffffff;x[10]=x[11]=pp['chroma_qp_index_offset']&0xffffffff;x[12]=0;x[13]=i;x[14]=x[15]=2*i
  x[32+refslot]=6;x[64]=refslot;x[65]=3;x[66]=x[67]=2*(i-1);x[68]=i-1
  scale=(ctypes.c_uint8*224)(*([16]*224));aligned=(ctypes.c_uint32*189)();raw=ctypes.cast(aligned,ctypes.POINTER(ctypes.c_uint8));after=ctypes.c_uint32();caps=fn(x,scale,raw,ctypes.byref(after));actual=(a.out/f'p-{i:03d}.bin').read_bytes()
  need(caps==0x1113 and after.value==6 and bytes(raw[:756])==actual,'Mesa output differs')
  need(struct.unpack_from('<II',actual,0x38)==(2*i,2*i) and struct.unpack_from('<I',actual,0x4c)[0]==i-1,'POC/reference differs')
  rows.append({'frame':i,'references':1,'reference_frame':i-1,'target_slot':target,'derived_order':2*i,'proposal_sha256':sha(a.out/f'p-{i:03d}.bin')})
 need({n:sha(HERE/n) for n in NAMES}==before and sha(a.mesa)==MESA and all(sha(a.fixture/n)==h for n,h in PINS.items()),'inputs changed')
 result={'status':'PASS_ONE_REF_POC2_H264_CPU','source_sha256':before,'input_sha256':PINS,'mesa_reference_sha256':MESA,'frames':6,'slice_headers':12,'proposals':5,'proposal_bytes':756,'mesa_bytes_match':True,'ffmpeg_header_trace_matches':True,'simulated_reference_completion':True,'real_surface_ownership_proved':False,'hardware_video_execution_proved':False,'gpu_submission':False,'system_modified':False,'rows':rows}
 (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
