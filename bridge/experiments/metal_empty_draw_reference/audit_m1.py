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
    pins={'source':'6f610302224776827626da7bb4cb76cc579c95239d873480d45da867b23dbd72',
          'direct':'d6075548440def70a2a74e274f27604f6eee04a0df68cf7a56685eb71ce81fe3',
          'icb':'c987a10f3b1593eb93b94708df1483b03cc7c0f2c09be5aceafa5fb42925f9d6'}
    for name,digest in pins.items():need(sha(getattr(a,name))==digest,name+' differs')
    modes=[]
    for mode in ('direct','icb'):
        report=json.loads(getattr(a,mode).read_text());need(report['device']=='Apple M1 Max' and report['mode']==mode and report['registry_id']!=0,'device differs')
        names=('direct_normal','direct_zero_count','direct_zero_instances','indexed_normal','indexed_zero_count','indexed_zero_instances')
        need(set(report['results'])==set(names),'case set differs')
        for name in names:
            row=report['results'][name];empty='zero_' in name
            need(row=={'red':0 if empty else 256,'black':256 if empty else 0,'other':0,'completed':True},'pixel summary differs')
        modes.append({'mode':mode,'cases':6,'all_command_buffers_completed':True})
    result={'status':'PASS','device':'Apple M1 Max','input_sha256':pins,'results':modes,'raw_images_retained':False,
            'nvidia_gpu_execution_proved':False,'macOS_version_observed':'27.2 (26B118)','sdk_version_observed':'27.0',
            'host_binary_sha256_observed':'b392058827cd5abf081ab09b0d3b8c1539e62eb49ea3990dccb2dac523ad0bb0'}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
