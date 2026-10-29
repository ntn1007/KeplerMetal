#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the CPU-only one-reference fixture under arm64 ASan/UBSan."""
import argparse,json,re,shlex,subprocess
from pathlib import Path,PurePosixPath
from validate_one_reference import NAMES,sha,need
HERE=Path(__file__).resolve().parent
OPTS=['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8']
def main():
 p=argparse.ArgumentParser();p.add_argument('--local',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--host',required=True);p.add_argument('--remote-dir',required=True);a=p.parse_args()
 need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required');need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.host) and re.fullmatch(r'/[A-Za-z0-9_./-]+',a.remote_dir) and '..' not in PurePosixPath(a.remote_dir).parts,'invalid host/path')
 receipt=json.loads((a.local/'validation.json').read_text());need(receipt['status']=='PASS_ONE_REF_POC2_H264_CPU','local receipt');names=[n for n in NAMES if n.endswith(('.h','.cpp'))];need(all(sha(HERE/n)==receipt['source_sha256'][n] for n in names),'local sources differ')
 files=[*(HERE/n for n in names),*(a.local/f'param-{i}.bin' for i in range(2)),*(a.local/f'frame-{i:03d}.avcc' for i in range(6))];hashes={f.name:sha(f) for f in files};need(len(files)==len(hashes),'duplicate names')
 a.out.mkdir();ssh=['ssh','-T',*OPTS,a.host]
 def run(label,cmd):
  r=subprocess.run(list(map(str,cmd)),capture_output=True,timeout=180);(a.out/(label+'.stdout')).write_bytes(r.stdout);(a.out/(label+'.stderr')).write_bytes(r.stderr);need(r.returncode==0 and not r.stderr,label+' failed');return r.stdout.decode()
 run('mkdir',ssh+['mkdir '+shlex.quote(a.remote_dir)]);run('transfer',['scp',*OPTS,*files,a.host+':'+a.remote_dir+'/']);prefix='cd '+shlex.quote(a.remote_dir)+' && '
 def check(label):
  lines=run(label,ssh+[prefix+'shasum -a 256 '+' '.join(hashes)]).splitlines();need({n:d for d,n in (s.split(None,1) for s in lines)}==hashes,label+' differs')
 check('before');flags='-std=c++17 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all ';core='H264Stream.cpp H264Baseline.cpp VideoLayout.cpp VideoPicture.cpp VideoIdr.cpp VideoPredictive.cpp ';cmd=prefix
 for name in ('test_baseline','test_video_idr','test_video_predictive'):
  cmd+='xcrun clang++ '+flags+core+name+'.cpp -o '+name+' && ./'+name+' && '
 cmd+='xcrun clang++ '+flags+core+'predictive_picture_tool.cpp -o tool && ./tool param-0.bin param-1.bin . . && uname -m && shasum -a 256 '+' '.join('p-%03d.bin'%i for i in range(1,6))
 lines=run('test',ssh+[cmd]).splitlines();need(len(lines)==11 and lines[5]=='arm64','test output differs')
 for i in range(5):
  row=json.loads(lines[i]);digest,name=lines[6+i].split(None,1);need(row['frame']==i+1 and digest==receipt['rows'][i]['proposal_sha256'] and name=='p-%03d.bin'%(i+1),'proposal differs')
 check('after');need(all(sha(f)==hashes[f.name] for f in files),'local input changed')
 result={'status':'PASS_MACBOOK_ONE_REF_POC2_ASAN_UBSAN','architecture':'arm64','input_sha256':hashes,'proposal_sha256':[r['proposal_sha256'] for r in receipt['rows']],'local_receipt_sha256':sha(a.local/'validation.json'),'transfer_hashes_match_before_after':True,'gpu_submission':False,'hardware_video_execution_proved':False,'script_sha256':sha(Path(__file__))};(a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
