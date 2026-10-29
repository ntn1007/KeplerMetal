#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the exact Mesa VP comparison on an authenticated ARM Mac with sanitizers."""
import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path, PurePosixPath
from validate import need, sha

HERE=Path(__file__).resolve().parent
NAMES=('H264Stream.h','VideoLayout.h','VideoLayout.cpp','VideoPicture.h','VideoPicture.cpp','compare_video_picture.cpp')
OPTS=['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('out','baseline'): p.add_argument('--'+n,type=Path,required=True)
    for n in ('host','remote-dir'): p.add_argument('--'+n,required=True)
    a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(),'fresh local output required')
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.host) and
         re.fullmatch(r'/[A-Za-z0-9_./-]+',a.remote_dir) and
         '..' not in PurePosixPath(a.remote_dir).parts,'invalid host or remote path')
    receipt=json.loads((a.baseline/'validation.json').read_text())
    need(receipt['status']=='PASS_MESA_VP_BLOCKS_CPU','missing local comparison')
    before={n:sha(HERE/n) for n in NAMES}
    for n in NAMES:
        if n in receipt['source_sha256']: need(before[n]==receipt['source_sha256'][n],'source changed')
    ref=a.baseline/'mesa-vp-reference.private.c'
    need(sha(ref)==receipt['generated_reference_sha256'],'generated reference changed')
    expected={**before,ref.name:sha(ref)}
    a.out.mkdir(); ssh=['ssh','-T',*OPTS,a.host]
    def run(label,args):
        result=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
        (a.out/(label+'.stdout')).write_bytes(result.stdout); (a.out/(label+'.stderr')).write_bytes(result.stderr)
        need(result.returncode==0,label+' failed; inspect retained stderr')
        return result.stdout.decode()
    run('mkdir',ssh+['mkdir '+shlex.quote(a.remote_dir)])
    run('transfer',['scp',*OPTS,*(HERE/n for n in NAMES),ref,a.host+':'+a.remote_dir+'/'])
    prefix='cd '+shlex.quote(a.remote_dir)+' && '
    def check(label):
        lines=run(label,ssh+[prefix+'shasum -a 256 '+' '.join(expected)]).splitlines()
        need({name:digest for digest,name in (line.split(None,1) for line in lines)}==expected,label+' differs')
    check('before')
    cmd=prefix+('xcrun clang -std=gnu11 -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -c mesa-vp-reference.private.c -o reference.o '
        '&& xcrun clang++ -std=c++17 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all '
        'VideoLayout.cpp VideoPicture.cpp compare_video_picture.cpp reference.o -o test '
        '&& ./test && uname -m && xcrun clang++ --version | head -1 && shasum -a 256 test')
    lines=run('test',ssh+[cmd]).splitlines()
    need(not (a.out/'test.stderr').read_bytes(),'sanitizer diagnostics found')
    need(len(lines)==4 and lines[0].startswith('PASS: 4096 Mesa VP picture blocks') and lines[1]=='arm64' and
         lines[2].startswith('Apple clang version '),'remote test differs')
    binary,filename=lines[3].split(None,1); need(filename=='test' and len(binary)==64,'binary identity differs')
    check('after')
    need({n:sha(HERE/n) for n in NAMES}==before and sha(ref)==expected[ref.name],'local input changed')
    result={'status':'PASS_MACBOOK_VP_ASAN_UBSAN','architecture':'arm64','compiler':lines[2],
        'cases':4096,'source_sha256':expected,'binary_sha256':binary,'baseline_receipt_sha256':sha(a.baseline/'validation.json'),
        'transfer_hashes_match_before_after':True,'hardware_video_execution_proved':False,
        'script_sha256':sha(Path(__file__))}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__': main()
