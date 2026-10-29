#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the exact restricted IDR block on an ARM Mac under sanitizers."""
import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path, PurePosixPath
from validate_baseline import EXPECTED, need, sha
from validate_video_idr import NAMES

HERE=Path(__file__).resolve().parent
SOURCES=tuple(n for n in NAMES if n.endswith(('.h','.cpp')))+('test_baseline.cpp',)
OPTS=['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('out','local','baseline','fixture'): p.add_argument('--'+n,type=Path,required=True)
    for n in ('host','remote-dir'): p.add_argument('--'+n,required=True)
    a=p.parse_args(); need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.host) and
         re.fullmatch(r'/[A-Za-z0-9_./-]+',a.remote_dir) and
         '..' not in PurePosixPath(a.remote_dir).parts,'invalid host or path')
    local=json.loads((a.local/'validation.json').read_text())
    baseline=json.loads((a.baseline/'validation.json').read_text())
    need(local['status']=='PASS_REAL_IDR_VP_CPU' and
         local['baseline_receipt_sha256']==sha(a.baseline/'validation.json'),'local receipt differs')
    before={n:sha(HERE/n) for n in SOURCES}
    for n in NAMES:
        if n in before: need(before[n]==local['source_sha256'][n],'source differs')
    need(before['test_baseline.cpp']==baseline['source_sha256']['test_baseline.cpp'],'baseline test differs')
    need({x.name:sha(x) for x in a.fixture.iterdir() if x.is_file()}==EXPECTED,'fixture differs')
    files=[*(HERE/n for n in SOURCES),a.baseline/'param-0.bin',a.baseline/'param-1.bin',
           a.fixture/'frame-000.avcc',a.fixture/'frame-001.avcc']
    hashes={f.name:sha(f) for f in files}; need(len(hashes)==len(files),'duplicate filenames')
    a.out.mkdir(); ssh=['ssh','-T',*OPTS,a.host]
    def run(label,args):
        r=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
        (a.out/(label+'.stdout')).write_bytes(r.stdout); (a.out/(label+'.stderr')).write_bytes(r.stderr)
        need(r.returncode==0 and not r.stderr,label+' failed; inspect retained stderr')
        return r.stdout.decode()
    run('mkdir',ssh+['mkdir '+shlex.quote(a.remote_dir)])
    run('transfer',['scp',*OPTS,*files,a.host+':'+a.remote_dir+'/'])
    prefix='cd '+shlex.quote(a.remote_dir)+' && '
    def check(label):
        lines=run(label,ssh+[prefix+'shasum -a 256 '+' '.join(hashes)]).splitlines()
        need({n:d for d,n in (s.split(None,1) for s in lines)}==hashes,label+' hashes differ')
    check('before')
    options='-std=c++17 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all '
    base='H264Stream.cpp H264Baseline.cpp VideoLayout.cpp '
    all_sources=base+'VideoPicture.cpp VideoIdr.cpp '
    cmd=prefix+('xcrun clang++ '+options+base+'test_baseline.cpp -o baseline-test && ./baseline-test && '
        'xcrun clang++ '+options+all_sources+'test_video_idr.cpp -o idr-test && ./idr-test && '
        'xcrun clang++ '+options+all_sources+'idr_picture_tool.cpp -o idr-tool && '
        './idr-tool param-0.bin param-1.bin frame-000.avcc idr.bin && '
        '(./idr-tool param-0.bin param-1.bin frame-001.avcc rejected.bin; test $? -eq 5) && '
        'test ! -e rejected.bin && uname -m && xcrun clang++ --version | head -1 && shasum -a 256 idr.bin idr-tool')
    lines=run('test',ssh+[cmd]).splitlines()
    need(len(lines)==5 and lines[1]=='arm64' and lines[2].startswith('Apple clang version '),'remote output differs')
    info=json.loads(lines[0]); block,block_name=lines[3].split(None,1); binary,binary_name=lines[4].split(None,1)
    need(info['is_idr']==1 and info['is_reference']==1 and block==local['block_sha256'] and
         block_name=='idr.bin' and len(binary)==64 and binary_name=='idr-tool','remote IDR differs')
    check('after'); need(all(sha(f)==hashes[f.name] for f in files),'local files changed')
    result={'status':'PASS_MACBOOK_REAL_IDR_ASAN_UBSAN','architecture':'arm64','compiler':lines[2],
        'source_and_fixture_sha256':hashes,'binary_sha256':binary,'block_sha256':block,
        'local_receipt_sha256':sha(a.local/'validation.json'),'transfer_hashes_match_before_after':True,
        'p_frame_refused':True,'hardware_video_execution_proved':False,'script_sha256':sha(Path(__file__))}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__': main()
