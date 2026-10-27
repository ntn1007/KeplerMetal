#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run a signed local Metal reference serially; never call a Qwen service."""
import argparse,datetime,hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def run(a):
    root=a.root.resolve();exe=root/'reference';src=root/'reference.mm';out=(root/a.out).resolve()
    if out.parent!=root or out.exists() or platform.system()!='Darwin' or platform.machine()!='arm64' or not os.getuid() or os.getuid()!=os.geteuid():raise ValueError('Fresh local arm64 user directory required')
    if sha(src)!=a.source_sha or sha(exe)!=a.binary_sha:raise ValueError('Reference artifact differs')
    subprocess.run(['codesign','--verify','--strict',str(exe)],check=True,capture_output=True,timeout=15)
    sw=subprocess.check_output(['sw_vers','-productVersion'],text=True).strip();build=subprocess.check_output(['sw_vers','-buildVersion'],text=True).strip();sdk=subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip()
    out.mkdir();records=[]
    for mode in ('negative3d','partial1d','partial3d'):
        folder=out/mode;folder.mkdir();started=now();tick=time.monotonic_ns()
        with (folder/'result.json').open('xb') as stdout,(folder/'stderr.txt').open('xb') as stderr:
            child=subprocess.Popen([str(exe),mode,str(folder)],stdout=stdout,stderr=stderr);code=child.wait()
        completed=now();elapsed=time.monotonic_ns()-tick
        row={'mode':mode,'pid':child.pid,'started_at':started,'completed_at':completed,'elapsed_monotonic_ns':elapsed,'exit_code':code,'kill_requested':False}
        records.append(row)
        if code:break
        data=json.loads((folder/'result.json').read_text())
        if data['pid']!=child.pid or data['mode']!=mode or data['uid']!=os.getuid() or data['euid']!=os.geteuid():raise ValueError('Child identity differs')
        row['result_SHA256']=sha(folder/'result.json');row['output_SHA256']=sha(folder/'output.bin')
    after={'source_SHA256':sha(src),'binary_SHA256':sha(exe)}
    doc={'status':'PASS' if len(records)==3 and all(r['exit_code']==0 for r in records) else 'FAILED',
         'architecture':platform.machine(),'macOS':sw,'macOS_build':build,'SDK':sdk,'user_UID':os.getuid(),
         'source_SHA256':a.source_sha,'binary_SHA256':a.binary_sha,'runner_SHA256':sha(Path(__file__)),
         'after':after,'records':records,'run_scope':'Native Apple Metal reference; no Kepler GPU or Qwen execution','system_modified':False}
    with (out/'manifest.json').open('x') as f:json.dump(doc,f,indent=2);f.write('\n')
    if doc['status']!='PASS' or after!={'source_SHA256':a.source_sha,'binary_SHA256':a.binary_sha}:raise ValueError('Inspect this result before any further run')
    print(json.dumps({'status':'PASS','processes':len(records),'manifest_SHA256':sha(out/'manifest.json')}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',required=True);p.add_argument('--source-sha',required=True);p.add_argument('--binary-sha',required=True);run(p.parse_args())
