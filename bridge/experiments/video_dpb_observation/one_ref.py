#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Observe a single-reference POC2 software DPB; no GPU submission."""
import argparse,hashlib,json,re,shlex,struct,subprocess
from pathlib import Path,PurePosixPath
import observe
FF='7f6028378534aa10a2dfa07d807ddcc0d18c869bf5c2f64c89efcc18ee88c4ee'
FIX='4b4f9fb55be0741a00991bdf81b3b93147525e3268b0d0a2140e549ed13a4323'
PIX='4c7bf3b3ef3f556bbd08bcae63b319010b112a8c9b13fbc8d299b51f8e45d4c4'
def sha(b):return hashlib.sha256(b).hexdigest()
def need(x,msg):
 if not x:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--remote-ffmpeg',required=True);p.add_argument('--remote-fixture',required=True);p.add_argument('--predictive',type=Path,required=True);p.add_argument('--reference-nv12',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.host),'invalid host')
 for path in (a.remote_ffmpeg,a.remote_fixture):need(path.startswith('/') and not any(x in path for x in '\n\r\0') and '..' not in PurePosixPath(path).parts,'invalid path')
 need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required');pred=json.loads((a.predictive/'validation.json').read_text());need(pred['status']=='PASS_ONE_REF_POC2_H264_CPU','proposal receipt')
 for i,row in enumerate(pred['rows'],1):
  b=(a.predictive/f'p-{i:03d}.bin').read_bytes();need(len(b)==756 and sha(b)==row['proposal_sha256'] and struct.unpack_from('<I',b,0x4c)[0]==i-1 and struct.unpack_from('<I',b,0x38)[0]==2*i,'proposal differs')
 pixels=a.reference_nv12.read_bytes();need(len(pixels)==691200 and sha(pixels)==PIX,'software reference differs');a.out.mkdir();ff=shlex.quote(a.remote_ffmpeg);fixture=shlex.quote(a.remote_fixture)
 def call(name,cmd):
  r=subprocess.run([*observe.SSH,a.host,cmd],capture_output=True,timeout=120);(a.out/(name+'.stdout')).write_bytes(r.stdout);(a.out/(name+'.stderr')).write_bytes(r.stderr);need(r.returncode==0,name+' failed');return r
 identity='uname -m; '+ff+' -version | head -1; shasum -a 256 '+ff+' '+fixture
 before=call('before',identity);dec=call('decode',ff+' -hide_banner -nostdin -loglevel debug -hwaccel none -c:v h264 -threads 1 -debug mmco+pict -f h264 -i '+fixture+' -map 0:v:0 -f framehash -');after=call('after',identity)
 lines=before.stdout.decode().splitlines();need(before.stdout==after.stdout and len(lines)==4 and lines[0]=='arm64' and lines[1].startswith('ffmpeg version 9.0.2 ') and lines[2].split(None,1)==[FF,a.remote_ffmpeg] and lines[3].split(None,1)==[FIX,a.remote_fixture],'identity differs')
 log=dec.stderr.decode();raw=dec.stdout.decode();need('6 frames decoded; 0 decode errors' in log and log.count('After avformat_find_stream_info()')==1 and '#hash: SHA256' in raw,'decode incomplete')
 hashes=re.findall(r'^0,\s*(\d+),\s*(\d+),\s*1,\s*115200,\s*([0-9a-f]{64})$',raw,re.M);need(len(hashes)==6 and [int(x[1]) for x in hashes]==list(range(6)),'frame hashes')
 for i,(_,_,digest) in enumerate(hashes):
  nv12=pixels[115200*i:115200*(i+1)];y=320*240;need(sha(nv12[:y]+nv12[y::2]+nv12[y+1::2])==digest,'pixels differ')
 observe.SLICE=re.compile(r'^slice:(\d+) F mb:(\d+) (I fix IDR|P fix) frame:(\d+) poc:(-?\d+)/(-?\d+) ref:(\d+)/(\d+) ')
 rows=observe.snapshots(log.split('After avformat_find_stream_info()',1)[1]);need(len(rows)==12 and len({x['context'] for x in rows})==1,'slice snapshot count')
 for frame in range(6):
  pair=rows[frame*2:frame*2+2];need([x['slice'] for x in pair]==[1,2] and [x['mb'] for x in pair]==[0,160] and all(x['frame']==frame and x['kind']==('I fix IDR' if frame==0 else 'P fix') and x['top']==x['bottom']==2*frame and not x['long'] for x in pair),'slice metadata')
  for x in pair:
   expected=[] if frame==0 else [(0,frame-1,2*(frame-1))];need([(y[0],y[1],y[2]) for y in x['short']]==expected and all(y[3]!='0x0' for y in x['short']),'short references differ')
 result={'status':'PASS_ONE_REF_POC2_SOFTWARE_DPB','architecture':'arm64','ffmpeg_sha256':FF,'fixture_sha256':FIX,'software_nv12_sha256':PIX,'frames_decoded':6,'slice_snapshots':12,'frame_hashes':[x[2] for x in hashes],'decoded_reference_frames':[i-1 for i in range(1,6)],'proposal_receipt_sha256':sha((a.predictive/'validation.json').read_bytes()),'decode_log_sha256':sha(dec.stderr),'framehash_sha256':sha(dec.stdout),'reference_comparison_same_ffmpeg_binary':True,'hardware_video_execution_proved':False,'system_modified':False,'script_sha256':sha(Path(__file__).read_bytes()),'parser_sha256':sha(Path(observe.__file__).read_bytes())};(a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
