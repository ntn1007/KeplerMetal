#!/usr/bin/env python3
"""Real CPU process/FD lifecycle tests; never imports Metal or submits GPU work."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import shutil
import sys
import time
from lab_gpu_reservation import GPUReservation, ReservationBusy, process_table

p=argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True)
a=p.parse_args(); out=a.out.resolve(); assert not out.exists(); out.mkdir()
root=out/'test-root'; (root/'results').mkdir(parents=True)
records=[]

def blocked(label):
    try:
        other=GPUReservation(root)
    except ReservationBusy as e:
        records.append({'case':label,'refused':True,'reason':str(e)})
    else:
        other.close()
        raise AssertionError('Reservation should have refused '+label)

r=GPUReservation(root)
blocked('simultaneous_reservation')
r.finish(0,False,''); r.close()
r=GPUReservation(root); r.finish(0,False,''); r.close()
records.append({'case':'terminal_release_reacquired','passed':True})

# A reused PID alone must not block; current paths, not stale PID numbers,
# decide whether any previous executable is still present.
registry=root/'results/signed-native-jobs.json'
registry.write_text(json.dumps([{'pid':os.getpid(),'signed_executable':str(out/'never-launched'),
                               'original_binary_sha256':'different-hash'}]))
r=GPUReservation(root); r.finish(0,False,''); r.close()
records.append({'case':'reused_PID_different_path','passed':True})

sleeper=out/'cpu-sleeper'; shutil.copyfile('/bin/sleep',sleeper); sleeper.chmod(0o755)
child=subprocess.Popen([str(sleeper),'2'])
try:
    time.sleep(.1)
    assert child.poll() is None
    actual=process_table().get(child.pid); assert actual and actual['command'].startswith(str(sleeper)+' '),actual
    registry.write_text(json.dumps([{'pid':1,'signed_executable':str(sleeper),
                                   'original_binary_sha256':'different-hash'}]))
    blocked('live_path_different_hash_and_wrong_recorded_PID')
finally:
    child.wait(timeout=4)
registry.write_text('[]')

# A parent actually exits, leaving its CPU child holding the inherited FD.
# The outcome remains unattested even after the orphan child disappears.
owner=out/'orphan-owner.py'
owner.write_text('''import json,sys,subprocess
from pathlib import Path
sys.path.insert(0,sys.argv[2])
from lab_gpu_reservation import GPUReservation
r=GPUReservation(Path(sys.argv[1]))
r.spawning(sys.executable,"CPU-fixture")
c=subprocess.Popen([sys.executable,"-c","import time; time.sleep(2)"],pass_fds=(r.fd,),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
r.bind_child(c.pid)
print(json.dumps({"child_PID":c.pid}),flush=True)
''')
proc=subprocess.Popen([sys.executable,str(owner),str(root),str(Path(__file__).parent)],
                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
line=proc.stdout.readline(); info=json.loads(line); proc.wait(timeout=4)
assert proc.returncode==0 and info['child_PID'] in process_table()
blocked('parent_exited_child_inherited_FD')
deadline=time.monotonic()+5
while info['child_PID'] in process_table() and time.monotonic()<deadline: time.sleep(.1)
assert info['child_PID'] not in process_table(), 'CPU fixture is still live; inspect same handle'
blocked('orphan_outcome_unattested_even_after_disappearance')

# Isolated state-fixture only; the real lab reservation is never overwritten.
state=root/'results/kepler-gpu-reservation.json'; d=json.loads(state.read_text())
d['state']='unresolved'; d['SIGKILL_requested']=True; state.write_text(json.dumps(d))
blocked('unresolved_kill_request_never_silently_released')
result={'status':'PASS','cases':records,'GPU_dispatches':0,'own_CPU_children_terminal':True,
        'module_SHA256':hashlib.sha256(Path(__file__).with_name('lab_gpu_reservation.py').read_bytes()).hexdigest()}
(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
