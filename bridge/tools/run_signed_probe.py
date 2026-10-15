#!/usr/bin/env python3
"""Run an immutable, locally signed copy of a lab executable; preserve live PIDs."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,struct,subprocess,time
from contextlib import nullcontext
from lab_gpu_reservation import GPUReservation,ReservationBusy

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--exe',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--timeout',type=float,default=15)
parser.add_argument('--profile-phases',action='store_true',help='Opt-in diagnostic phase durations, not GPU benchmark timings')
parser.add_argument('arguments',nargs=argparse.REMAINDER)
args=parser.parse_args();exe=args.exe.resolve();exe.relative_to(root)
out=args.out.resolve();out.relative_to(root/'results');assert 0<args.timeout<=60
arguments=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
data=exe.read_bytes();assert data[:4]==b'\xcf\xfa\xed\xfe' and struct.unpack_from('<I',data,12)[0]==2, 'Expected a thin Mach-O executable, not a driver/library'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
originalHash=sha(exe);jobsPath=root/'results/signed-native-jobs.json'
timing=None
if args.profile_phases:
    from lab_phase_timing import PhaseLog
    timing=PhaseLog(out.parent/(out.name+'.launcher-phases.json'),[Path(__file__),Path(__file__).with_name('lab_phase_timing.py'),Path(__file__).with_name('lab_gpu_reservation.py')])
def phase(label,**metadata):return timing.phase(label,**metadata) if timing else nullcontext({})
try:
    with phase('host-reservation'):
        reservation=GPUReservation(root)
except ReservationBusy as error:
    raise SystemExit('BLOCKED: '+str(error))
with phase('history-preflight') as measured:
    jobsRaw=jobsPath.read_bytes() if jobsPath.exists() else b'[]'
    jobs=json.loads(jobsRaw);queries=0
    # The held reservation validated one current process table against every
    # immutable signed path, regardless of hash and historical PID reuse.
    assert reservation.data['bootstrap_process_table_checked'] and not reservation.data['known_signed_processes_live']
    measured.update(registry_bytes_read=len(jobsRaw),registry_entries=len(jobs),ps_queries=queries,process_validation='one global table under reservation; all known signed paths')
assert not out.exists(), 'Use a new output directory; never rewrite a mapped executable'
out.mkdir(parents=True)
with phase('dependency-inspection') as measured:
    dependencies=subprocess.run(['otool','-L',str(exe)],capture_output=True,text=True,timeout=15);assert dependencies.returncode==0
    assert '@executable_path/' not in dependencies.stdout and '@loader_path/' not in dependencies.stdout, 'Relative loader dependencies need a separately qualified layout'
    measured.update(exit_code=dependencies.returncode,stdout_bytes=len(dependencies.stdout.encode()),stderr_bytes=len(dependencies.stderr.encode()))
with phase('copy-and-sign') as measured:
    binary=out/exe.name;shutil.copyfile(exe,binary);binary.chmod(0o755)
    command=['codesign','--force','--sign','-',str(binary)]
    sign=subprocess.run(command,capture_output=True,text=True,timeout=15);assert sign.returncode==0,sign.stderr
    measured.update(binary_bytes_copied=binary.stat().st_size,exit_code=sign.returncode)
stdout=(out/'execution.stdout').open('wb');stderr=(out/'execution.stderr').open('wb')
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
with phase('spawn-and-registration') as measured:
    reservation.spawning(binary,sha(binary))
    p=subprocess.Popen([str(binary)]+arguments,stdout=stdout,stderr=stderr,cwd=root,pass_fds=(reservation.fd,))
    reservation.bind_child(p.pid)
    job={'started_at':started,'original_executable':str(exe),'original_binary_sha256':originalHash,'signed_executable':str(binary),'signed_binary_sha256':sha(binary),'pid':p.pid,'arguments':arguments}
    jobs.append(job);jobsPath.write_text(json.dumps(jobs,indent=2)+'\n');print('Started own-process signed copy, PID',p.pid,flush=True)
    measured.update(child_PID=p.pid,signed_binary_SHA256=job['signed_binary_sha256'])
with phase('child-wait') as measured:
    deadline=time.monotonic()+args.timeout
    while p.poll() is None and time.monotonic()<deadline:time.sleep(.1)
    exitCode=p.poll();requested=exitCode is None
    if requested:p.kill()  # A request, never treated as proof that an uninterruptible child exited.
    measured.update(exit_code=exitCode,SIGKILL_requested=requested)
stdout.close();stderr.close()
with phase('terminal-observation-and-registry') as measured:
    state=subprocess.run(['ps','-o','pid=,ppid=,stat=,etime=,command=','-p',str(p.pid)],capture_output=True,text=True).stdout.strip()
    job.update({'exit_code':exitCode,'SIGKILL_requested':requested,'authoritative_ps_status':state,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    jobsPath.write_text(json.dumps(jobs,indent=2)+'\n')
    measured.update(child_PID=p.pid,still_present=bool(state),stdout_bytes=(out/'execution.stdout').stat().st_size,stderr_bytes=(out/'execution.stderr').stat().st_size)
reservation.finish(exitCode,requested,state)
reservationEvidence=dict(reservation.data)
reservation.close()
manifest={**job,'sign_command':command,'sign_stdout':sign.stdout,'sign_stderr':sign.stderr,'dependency_listing':dependencies.stdout,
          'launcher_sha256':sha(Path(__file__)),'macOS_settings_changed':False,
          'GPU_reservation':reservationEvidence,
          'reservation_module_SHA256':sha(Path(__file__).with_name('lab_gpu_reservation.py')),
          'scope':'Immutable application executable copy only; ad hoc signing is not Apple trust or proof of the earlier hang cause; system drivers/settings unchanged'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if timing:timing.finish('terminal' if exitCode is not None and not state else 'unresolved',child_PID=p.pid,exit_code=exitCode,SIGKILL_requested=requested)
print(json.dumps({'pid':p.pid,'exit_code':exitCode,'still_present':bool(state),'SIGKILL_requested':requested}),flush=True)
if exitCode is not None:raise SystemExit(exitCode)
raise SystemExit(124)
