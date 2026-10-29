#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run one signed VideoToolbox client under a reserved bounded LLDB witness."""
import argparse,datetime,importlib.util,json,os,re,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
from experiment import SOURCE,SYSTEM,RESERVATION,REFERENCE,EXPECTED,sha,profile

def need(value,message):
    if not value:raise ValueError(message)
def q(value):return json.dumps(str(value))
def main():
    p=argparse.ArgumentParser()
    for n in ('lab','build','calibration','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--mode',choices=('hardware','software'),required=True);a=p.parse_args()
    lab,build,cal,out=(getattr(a,n).resolve() for n in ('lab','build','calibration','out'))
    for path in (build,cal,out):path.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    b=json.loads((build/'build.json').read_text());c=json.loads((cal/'calibration.json').read_text());profile()
    need(b['status']=='PREPARED' and b['calibration_sha256']==sha(cal/'calibration.json') and
         c['status']=='PASS_CPU_ENUMERATION_WITNESS' and b['builder_sha256']==sha(HERE/'experiment.py') and
         b['source_sha256']=={n:sha(v) for n,v in SOURCE.items()} and
         b['build_sha256']=={n:sha(build/n) for n in ('client','observer.dylib')} and
         b['fixture']=={n:sha(build/'fixture'/n) for n in EXPECTED} and sha(build/'reference.nv12')==REFERENCE,
         'frozen build differs')
    for name in ('lldb_witness.py','lldb_guard.py'):
        need(c['sources'][name]==sha(build/name)==sha(HERE/name),'witness differs')
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py';need(sha(leasepath)==RESERVATION,'reservation differs')
    spec=importlib.util.spec_from_file_location('vt_enum_reservation',leasepath);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);lease=module.GPUReservation(lab)
    child=None;terminal=False;finished=False
    try:
        out.mkdir();host=out/'client';shutil.copyfile(build/'client',host);host.chmod(0o755)
        need(sha(host)==b['build_sha256']['client'] and subprocess.run(['codesign','--verify','--strict',str(host)],capture_output=True).returncode==0,'host differs')
        commands=['settings set target.run-args '+' '.join(q(x) for x in (build/'fixture',out/'decoded.nv12',a.mode)),
                  'settings set target.output-path '+q(out/'stdout.json'),'settings set target.error-path '+q(out/'stderr.log'),
                  'command script import '+q(build/'lldb_witness.py'),'command script import '+q(build/'lldb_guard.py'),
                  'breakpoint set -H -K false -n KMTraceReady','breakpoint command add -F lldb_witness.arm 1',
                  'run','script lldb_guard.await_terminal(lldb.debugger)','breakpoint list','quit']
        cmd=['xcrun','lldb','--no-lldbinit','--batch']
        for line in commands:cmd.extend(('-o',line))
        cmd.extend(('--',str(host)));env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};env['KM_TRACE_MODE']='video'
        lease.spawning(host,sha(host));started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'lldb.log').open('wb') as log:
            child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,pass_fds=(lease.fd,),env=env);lease.bind_child(child.pid)
            print(json.dumps({'status':'DEBUGGER_STARTED','pid':child.pid,'mode':a.mode}),flush=True);code=child.wait()
        text=(out/'lldb.log').read_text();entries=re.findall(r'^KP_PROCESS_EXITED pid=(\d+) code=(\d+)$',text,re.M)
        need(len(entries)==1 and entries[0][1]=='0','target exit not established');target_pid=int(entries[0][0]);table=module.process_table()
        need(child.pid not in table and target_pid not in table and not any(row['command']==str(host) or row['command'].startswith(str(host)+' ') for row in table.values()),'debugger or target still present')
        terminal=True
        need(code==0 and 'KM_TRACE_ARM_PASS mode=video' in text and not any(x in text for x in ('KP_GUARD_NO_PROCESS','KP_GUARD_UNRESOLVED','KM_TRACE_ARM_FAIL','KM_TRACE_HIT_FAIL')),'debugger failure')
        result=json.loads((out/'stdout.json').read_text());need(result['mode']==a.mode and not result['observer_loaded'],'client result differs')
        if a.mode=='hardware':need(result['status']=='CREATE_FAILED' and result['create_status']==-12906 and result['frames']==0,'hardware result differs')
        else:need(result['status']=='PASS' and result['frames']==6 and sha(out/'decoded.nv12')==REFERENCE,'software result differs')
        need(profile()==SYSTEM and all(sha(build/n)==b['build_sha256'][n] for n in ('client','observer.dylib')),'profile changed')
        lease.finish(code,False,'');finished=True
        record={'status':'TERMINAL_DEBUGGER','mode':a.mode,'debugger_pid':child.pid,'target_pid':target_pid,'started_at':started,
                'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),
                'build_sha256':sha(build/'build.json'),'host_sha256':sha(host),'lldb_log_sha256':sha(out/'lldb.log'),
                'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),'runner_sha256':sha(Path(__file__)),
                'decoder_status':result['create_status'],'frames':result['frames'],'system_modified':False}
        (out/'manifest.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':record['status'],'mode':a.mode,'decoder_status':record['decoder_status']}),flush=True)
    finally:
        if not finished and lease.fd is not None:
            if child is None or terminal:lease.finish(0,False,'')
            else:lease.finish(None,False,'debugger or target terminal outcome not established')
        lease.close()
if __name__=='__main__':main()
