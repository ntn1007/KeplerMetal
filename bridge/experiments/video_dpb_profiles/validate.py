#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare four CPU VP profiles with pinned Mesa helpers; never submit to a GPU."""
import argparse, hashlib, json, struct, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'video_bsp_staging'
HERE=Path(__file__).resolve().parent

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,msg):
    if not ok: raise ValueError(msg)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('mesa','predictive','observation','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    mesa=json.loads((a.mesa/'validation.json').read_text()); src=a.mesa/'mesa-vp-reference.private.c'
    pred=json.loads((a.predictive/'validation.json').read_text()); obs=json.loads((a.observation/'validation.json').read_text())
    need(mesa['status']=='PASS_MESA_VP_BLOCKS_CPU' and sha(src)==mesa['generated_reference_sha256'] and
         pred['mesa_reference_sha256']==sha(src),'Mesa reference differs')
    need(pred['status']=='PASS_FIVE_BASELINE_P_PROPOSALS_CPU' and obs['status']=='PASS_SOFTWARE_DPB_SNAPSHOTS' and
         obs['predictive_receipt_sha256']==sha(a.predictive/'validation.json'),'prior receipts differ')
    inputs=[HERE/'profiles.cpp',Path(__file__),ROOT/'VideoPicture.cpp',ROOT/'VideoPicture.h',ROOT/'VideoLayout.cpp',ROOT/'VideoLayout.h',ROOT/'H264Stream.h']
    before={p.name:sha(p) for p in inputs}; a.out.mkdir()
    def run(name,cmd):
        r=subprocess.run(list(map(str,cmd)),capture_output=True,timeout=120)
        (a.out/(name+'.stdout')).write_bytes(r.stdout);(a.out/(name+'.stderr')).write_bytes(r.stderr)
        need(r.returncode==0 and not r.stderr,name+' failed')
    run('build-mesa',['xcrun','clang','-std=gnu11','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all','-c',src,'-o',a.out/'mesa.o'])
    run('build',['xcrun','clang++','-std=c++17','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all',
        '-I',ROOT,HERE/'profiles.cpp',ROOT/'VideoPicture.cpp',ROOT/'VideoLayout.cpp',a.out/'mesa.o','-o',a.out/'profiles'])
    rows=[]
    for frame in range(1,6):
        prior=(a.predictive/('p-%03d.bin'%frame)).read_bytes();need(sha(a.predictive/('p-%03d.bin'%frame))==pred['rows'][frame-1]['block_sha256'],'prior bytes differ')
        observed=obs['rows'][frame-1];need(observed['frame']==frame,'observation differs')
        for mode in range(4):
            out=a.out/('frame-%d-mode-%d.bin'%(frame,mode))
            run('frame-%d-mode-%d'%(frame,mode),[a.out/'profiles',str(frame),str(mode),out])
            data=out.read_bytes(); count=1 if frame==1 else 2; need(len(data)==756,'size differs')
            refs=[struct.unpack_from('<I',data,0x4c+16*i)[0] for i in range(count)]
            orders=[struct.unpack_from('<I',data,0x44+16*i)[0] for i in range(count)]
            expected=observed['short_refs_recent_first'] if mode&1 else observed['proposal_refs_oldest_first']
            base=65536 if mode&2 else 0
            need(refs==expected and orders==[base+2*f for f in expected] and
                 struct.unpack_from('<I',data,0x38)[0]==base+2*frame,'candidate fields differ')
            if mode==0:need(data==prior,'baseline regression differs')
            rows.append({'frame':frame,'mode':mode,'reference_numbers':refs,'poc_base':base,
                         'sha256':sha(out),'different_bytes_from_baseline':sum(a!=b for a,b in zip(data,prior))})
    need({p.name:sha(p) for p in inputs}==before,'source changed')
    result={'status':'PASS_FOUR_CPU_DPB_PROFILES','frames':5,'profiles_per_frame':4,'comparisons':20,
      'same_fixture_original_profile_matches_previous':True,'project_model_and_mesa_bytes_match':True,
      'candidate_reverse_and_offset_inferred_from_ffmpeg_source_and_software_observation':True,
      'actual_vaapi_execution_observed':False,'nvidia_hardware_order_proved':False,'hardware_video_execution_proved':False,
      'gpu_transport_implemented':False,'source_sha256':before,'mesa_reference_sha256':sha(src),
      'predictive_receipt_sha256':sha(a.predictive/'validation.json'),'observation_receipt_sha256':sha(a.observation/'validation.json'),'rows':rows}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
