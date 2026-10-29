#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rerun the earlier POC0/two-reference fixture with the updated source."""
import argparse,json,subprocess
from pathlib import Path
from validate_baseline import EXPECTED,sha,need
from validate_one_reference import NAMES
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--prior',type=Path,required=True);p.add_argument('--local',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required');need(all(sha(a.fixture/n)==h for n,h in EXPECTED.items()),'fixture differs')
 ref=json.loads(a.prior.read_text());local=json.loads((a.local/'validation.json').read_text());need(ref['status']=='PASS_FIVE_BASELINE_P_PROPOSALS_CPU' and local['status']=='PASS_ONE_REF_POC2_H264_CPU','prior/local status')
 sources={n:sha(HERE/n) for n in NAMES};need(sources==local['source_sha256'],'source differs')
 params=[a.baseline/f'param-{i}.bin' for i in range(2)];before=[sha(x) for x in params];need(all(params[i].read_bytes()==__import__('base64').b64decode(json.loads((a.fixture/'fixture.json').read_text())['H264_parameter_sets_base64'][i],validate=True) for i in range(2)),'parameter sets differ')
 a.out.mkdir();flags=['-std=c++17','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all'];src=[HERE/n for n in ('H264Stream.cpp','H264Baseline.cpp','VideoLayout.cpp','VideoPicture.cpp','VideoIdr.cpp','VideoPredictive.cpp')]
 def run(name,cmd):
  r=subprocess.run(list(map(str,cmd)),capture_output=True,timeout=120);(a.out/(name+'.stdout')).write_bytes(r.stdout);(a.out/(name+'.stderr')).write_bytes(r.stderr);need(r.returncode==0,name+' failed');return r.stdout
 run('build',['xcrun','clang++',*flags,*src,HERE/'predictive_picture_tool.cpp','-o',a.out/'tool']);lines=run('prepare',[a.out/'tool',*params,a.fixture,a.out]).decode().splitlines();need(len(lines)==5,'count')
 rows=[]
 for i,line in enumerate(lines,1):
  got=json.loads(line);digest=sha(a.out/f'p-{i:03d}.bin');need(digest==ref['rows'][i-1]['block_sha256'] and got['frame']==i and got['poc']==2*i and got['refs']==(1 if i==1 else 2),'legacy output differs');rows.append({'frame':i,'sha256':digest})
 need(sources=={n:sha(HERE/n) for n in NAMES} and before==[sha(x) for x in params] and all(sha(a.fixture/n)==h for n,h in EXPECTED.items()),'inputs changed')
 out={'status':'PASS_LEGACY_TWO_REFERENCE_REGRESSION','blocks':5,'rows':rows,'prior_receipt_sha256':sha(a.prior),'local_receipt_sha256':sha(a.local/'validation.json'),'source_sha256':sources,'parameter_sha256':before,'gpu_submission':False,'hardware_video_execution_proved':False};(a.out/'validation.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
