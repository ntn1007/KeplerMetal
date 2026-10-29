#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check CPU profile candidates on arm64 with ASan/UBSan and verified transfer."""
import argparse,hashlib,json,re,shlex,subprocess
from pathlib import Path,PurePosixPath
HERE=Path(__file__).resolve().parent
STAGING=HERE.parent/'video_bsp_staging'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def need(x,m):
    if not x: raise ValueError(m)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('local','mesa','out'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('host','remote-dir'):p.add_argument('--'+n,required=True)
    a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.host) and re.fullmatch(r'/[A-Za-z0-9_./-]+',a.remote_dir) and '..' not in PurePosixPath(a.remote_dir).parts,'invalid remote')
    prior=json.loads((a.local/'validation.json').read_text());need(prior['status']=='PASS_FOUR_CPU_DPB_PROFILES' and len(prior['rows'])==20,'prior differs')
    files=[HERE/'profiles.cpp',STAGING/'VideoPicture.cpp',STAGING/'VideoPicture.h',STAGING/'VideoLayout.cpp',STAGING/'VideoLayout.h',STAGING/'H264Stream.h',a.mesa/'mesa-vp-reference.private.c']
    hashes={x.name:sha(x) for x in files};need(len(hashes)==len(files) and hashes['mesa-vp-reference.private.c']==prior['mesa_reference_sha256'],'reference differs')
    for n,h in hashes.items():
        if n in prior['source_sha256']:need(h==prior['source_sha256'][n],'source differs')
    a.out.mkdir();opts=['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8'];ssh=['ssh','-T',*opts,a.host]
    def run(label,cmd):
        x=subprocess.run(list(map(str,cmd)),capture_output=True,timeout=180)
        (a.out/(label+'.stdout')).write_bytes(x.stdout);(a.out/(label+'.stderr')).write_bytes(x.stderr)
        need(x.returncode==0 and not x.stderr,label+' failed');return x.stdout.decode()
    run('mkdir',ssh+['mkdir '+shlex.quote(a.remote_dir)])
    run('transfer',['scp',*opts,*files,a.host+':'+a.remote_dir+'/'])
    prefix='cd '+shlex.quote(a.remote_dir)+' && '
    def check(label):
        entries=run(label,ssh+[prefix+'shasum -a 256 '+' '.join(hashes)]).splitlines()
        need({n:h for h,n in (x.split(None,1) for x in entries)}==hashes,label+' differs')
    check('before')
    cflags='-O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all '
    outputs=['frame-%d-mode-%d.bin'%(f,m) for f in range(1,6) for m in range(4)]
    calls=' && '.join('./profiles %d %d %s'%(f,m,outputs[(f-1)*4+m]) for f in range(1,6) for m in range(4))
    cmd=prefix+'xcrun clang -std=gnu11 '+cflags+'-c mesa-vp-reference.private.c -o mesa.o && xcrun clang++ -std=c++17 -Wall -Wextra -Werror '+cflags+'profiles.cpp VideoPicture.cpp VideoLayout.cpp mesa.o -o profiles && '+calls+' && uname -m && xcrun clang++ --version | head -1 && shasum -a 256 '+' '.join(outputs)
    lines=run('test',ssh+[cmd]).splitlines();need(len(lines)==22 and lines[0]=='arm64' and lines[1].startswith('Apple clang version '),'output differs')
    for line,name,row in zip(lines[2:],outputs,prior['rows']):
        digest,actual=line.split(None,1);need(actual==name and digest==row['sha256'],'profile hash differs')
    check('after');need(all(sha(f)==hashes[f.name] for f in files),'local source changed')
    result={'status':'PASS_ARM64_FOUR_CPU_DPB_PROFILES_ASAN_UBSAN','architecture':'arm64','compiler':lines[1],
      'comparisons':20,'profile_sha256':[r['sha256'] for r in prior['rows']],'source_and_mesa_sha256':hashes,
      'local_receipt_sha256':sha(a.local/'validation.json'),'script_sha256':sha(Path(__file__)),
      'hardware_video_execution_proved':False,'actual_vaapi_execution_observed':False,'system_modified':False}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
