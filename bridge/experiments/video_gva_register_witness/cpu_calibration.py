#!/usr/bin/env python3
"""Compile and run CPU-only scalar/flags and cross-image dyld controls."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES=('witness.h','tail.S','calibrate.S','calibrate.cpp','observer.cpp','synthetic_caller.S','interpose_calibrate.cpp')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();need(not out.exists() and out.parent.is_dir(),'fresh output required');out.mkdir()
    for name in NAMES:shutil.copyfile(HERE/name,out/name)
    common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-Wall','-Wextra','-Werror']
    commands=[]
    def run(label,args,env=None):
        args=list(map(str,args));r=subprocess.run(args,capture_output=True,text=True,timeout=60,env=env)
        (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
        commands.append({'label':label,'argv':args,'exit_code':r.returncode});need(r.returncode==0,label+' failed: '+r.stderr[-1000:])
        return r.stdout
    scalar=out/'calibrate';obs=out/'observer.dylib';caller=out/'synthetic.dylib';host=out/'interpose-calibrate'
    run('build-scalar',common+[out/'tail.S',out/'calibrate.S',out/'calibrate.cpp','-o',scalar])
    run('build-observer',common+['-dynamiclib',out/'tail.S',out/'observer.cpp','-o',obs])
    run('build-caller',['xcrun','clang++','-arch','x86_64','-dynamiclib',out/'synthetic_caller.S','-Wl,-install_name,'+str(caller),'-o',caller])
    run('build-host',common+[out/'interpose_calibrate.cpp',caller,'-o',host])
    for n,path in [('scalar',scalar),('observer',obs),('caller',caller),('host',host)]:
        run('sign-'+n,['codesign','--force','--sign','-',path]);run('verify-'+n,['codesign','--verify','--strict',path])
    one=json.loads(run('scalar', [scalar]));need(one['status']=='PASS' and one['scalar_flag_cases']==256 and one['real_nothrow_allocation_bytes']==1536,'scalar result differs')
    env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_'))};env['DYLD_INSERT_LIBRARIES']=str(obs)
    two=json.loads(run('interpose',[host],env));need(two['status']=='PASS' and two['cross_image_interposition'] and two['matching_calls']==1 and two['selector']==9,'interposition result differs')
    files={f.name:sha(f) for f in out.iterdir() if f.is_file()}
    report={'status':'PASS','sources_sha256':{name:sha(out/name) for name in NAMES},'files_sha256':files,'commands':commands,
            'scalar':one,'interposition':two,'GPU_execution':False,'vendor_execution':False}
    (out/'calibration.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PASS','scalar_cases':one['scalar_flag_cases'],'interposition_cases':two['matching_calls'],
                      'GPU_execution':False,'calibration_sha256':sha(out/'calibration.json')}))
if __name__=='__main__':main()
