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
    pins={'source':'329990c28d6383bc98cea694bee020b1fc396024b7c8cea0a5573b3857e7a4d9',
          'direct':'21f5def7794a045433013ac5a58654e1cb2e7abc6b269cbe47aacc7b34a772a4',
          'icb':'216db96eff99b31f2d43c7fa875961a2d7328d9bc978f0b6a29346bcef53fb14'}
    for name,digest in pins.items():need(sha(getattr(a,name))==digest,name+' differs')
    modes=[]
    for mode in ('direct','icb'):
        report=json.loads(getattr(a,mode).read_text());need(report['device']=='Apple M1 Max' and report['mode']==mode and report['registry_id']!=0,'device differs')
        names=('direct_normal','direct_one','direct_two','indexed_normal','indexed_one','indexed_two')
        need(set(report['results'])==set(names),'case set differs')
        for name in names:
            row=report['results'][name];empty=name.endswith('one') or name.endswith('two')
            need(row=={'red':0 if empty else 256,'black':256 if empty else 0,'other':0,'completed':True},'pixel summary differs')
        modes.append({'mode':mode,'cases':6,'all_command_buffers_completed':True})
    result={'status':'PASS','device':'Apple M1 Max','input_sha256':pins,'results':modes,'raw_images_retained':False,
            'nvidia_gpu_execution_proved':False,'macOS_version_observed':'27.2 (26B123)','sdk_version_observed':'27.0',
            'host_binary_sha256_observed':'1aaef0f03f1892c982bf1b78ac14b0c1c101d13a5f3ae0f8bcd640cfd8c8cdd4'}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
