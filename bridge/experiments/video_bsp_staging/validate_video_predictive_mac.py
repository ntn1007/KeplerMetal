#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce CPU-only baseline P-picture proposals on ARM under sanitizers."""
import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path, PurePosixPath
from validate_baseline import EXPECTED, need, sha
from validate_video_predictive import NAMES

HERE=Path(__file__).resolve().parent
SOURCES=tuple(n for n in NAMES if n.endswith(('.h','.cpp')))+('test_baseline.cpp','test_video_idr.cpp')
OPTS=['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('out','local','baseline','idr-regression','fixture'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('host','remote-dir'):p.add_argument('--'+n,required=True)
    a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.host) and re.fullmatch(r'/[A-Za-z0-9_./-]+',a.remote_dir) and
         '..' not in PurePosixPath(a.remote_dir).parts,'invalid host or path')
    local=json.loads((a.local/'validation.json').read_text());baseline=json.loads((a.baseline/'validation.json').read_text())
    idr=json.loads((a.idr_regression/'validation.json').read_text())
    need(local['status']=='PASS_FIVE_BASELINE_P_PROPOSALS_CPU' and local['baseline_sha256']==sha(a.baseline/'validation.json') and
         local['idr_regression_sha256']==sha(a.idr_regression/'validation.json') and idr['status']=='PASS_REAL_IDR_VP_CPU','local receipts differ')
    before={n:sha(HERE/n) for n in SOURCES}
    for n in NAMES:
        if n in before:need(before[n]==local['source_sha256'][n],'source differs')
    need(before['test_baseline.cpp']==baseline['source_sha256']['test_baseline.cpp'] and
         before['test_video_idr.cpp']==idr['source_sha256']['test_video_idr.cpp'],'regression tests differ')
    need({x.name:sha(x) for x in a.fixture.iterdir() if x.is_file()}==EXPECTED,'fixture differs')
    files=[*(HERE/n for n in SOURCES),a.baseline/'param-0.bin',a.baseline/'param-1.bin',
           *(a.fixture/('frame-%03d.avcc'%i) for i in range(6))]
    hashes={f.name:sha(f) for f in files};need(len(hashes)==len(files),'duplicate filenames')
    a.out.mkdir();ssh=['ssh','-T',*OPTS,a.host]
    def run(label,args):
        r=subprocess.run(list(map(str,args)),capture_output=True,timeout=180)
        (a.out/(label+'.stdout')).write_bytes(r.stdout);(a.out/(label+'.stderr')).write_bytes(r.stderr)
        need(r.returncode==0 and not r.stderr,label+' failed; inspect retained stderr')
        return r.stdout.decode()
    run('mkdir',ssh+['mkdir '+shlex.quote(a.remote_dir)])
    run('transfer',['scp',*OPTS,*files,a.host+':'+a.remote_dir+'/'])
    prefix='cd '+shlex.quote(a.remote_dir)+' && '
    def check(label):
        lines=run(label,ssh+[prefix+'shasum -a 256 '+' '.join(hashes)]).splitlines()
        need({n:d for d,n in (s.split(None,1) for s in lines)}==hashes,label+' hashes differ')
    check('before')
    flags='-std=c++17 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all '
    base='H264Stream.cpp H264Baseline.cpp VideoLayout.cpp '
    core=base+'VideoPicture.cpp VideoIdr.cpp VideoPredictive.cpp '
    files_to_hash=' '.join('p-%03d.bin'%i for i in range(1,6))
    cmd=prefix+('xcrun clang++ '+flags+base+'test_baseline.cpp -o baseline-test && ./baseline-test && '
        'xcrun clang++ '+flags+core+'test_video_idr.cpp -o idr-test && ./idr-test && '
        'xcrun clang++ '+flags+core+'test_video_predictive.cpp -o predictive-test && ./predictive-test && '
        'xcrun clang++ '+flags+core+'predictive_picture_tool.cpp -o predictive-tool && '
        './predictive-tool param-0.bin param-1.bin . . && uname -m && '
        'xcrun clang++ --version | head -1 && shasum -a 256 '+files_to_hash)
    lines=run('test',ssh+[cmd]).splitlines();need(len(lines)==12 and lines[5]=='arm64' and lines[6].startswith('Apple clang version '),'remote output differs')
    for i in range(5):
        row=json.loads(lines[i]);digest,name=lines[7+i].split(None,1);prior=local['rows'][i]
        need(row['frame']==i+1 and row['simple']==1 and digest==prior['block_sha256'] and name=='p-%03d.bin'%(i+1),'remote proposal differs')
    check('after');need(all(sha(f)==hashes[f.name] for f in files),'local files changed')
    result={'status':'PASS_MACBOOK_P_PROPOSALS_ASAN_UBSAN','architecture':'arm64','compiler':lines[6],
        'source_and_fixture_sha256':hashes,'blocks_sha256':[r['block_sha256'] for r in local['rows']],
        'local_receipt_sha256':sha(a.local/'validation.json'),'transfer_hashes_match_before_after':True,
        'synthetic_reference_completion_assumed':True,'hardware_video_execution_proved':False,'script_sha256':sha(Path(__file__))}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
