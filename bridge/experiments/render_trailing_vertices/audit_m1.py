#!/usr/bin/env python3
"""Validate captured M1 public-Metal summaries; raw pixels were not retained."""
import argparse
import hashlib
import json
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','direct','icb','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    pins={'source':'282639cada9e03cfeb3aa198c05258617b76a9eacf15c5357db7d41c63c638bb',
          'direct':'84341833ac5448c8e5d291b9a0e6af873e28e419afb25ad00000db67134feadb',
          'icb':'bb494ab416eea457295e3f2e527723a628dd21ae03c3868d639112d2dc389c7a'}
    for name,digest in pins.items():need(sha(getattr(a,name))==digest,name+' differs')
    modes=[]
    for mode in ('direct','icb'):
        report=json.loads(getattr(a,mode).read_text());need(report['device']=='Apple M1 Max' and report['mode']==mode and report['registry_id']!=0,'device differs')
        names=('direct_normal','direct_four','direct_five','indexed_normal','indexed_four','indexed_five')
        need(set(report['results'])==set(names),'case set differs')
        for name in names:
            row=report['results'][name]
            need(row=={'red':256,'black':0,'other':0,'completed':True},'pixel summary differs')
        modes.append({'mode':mode,'cases':6,'all_command_buffers_completed':True})
    result={'status':'PASS','device':'Apple M1 Max','input_sha256':pins,'results':modes,'raw_images_retained':False,
            'nvidia_gpu_execution_proved':False,'macOS_version_observed':'27.2 (26B123)','sdk_version_observed':'27.0',
            'host_binary_sha256_observed':'2159b907a693dea7258a468ce98e594046f26d48c9f937a2eb1f2b501336e545'}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
