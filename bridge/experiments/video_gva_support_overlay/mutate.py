#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the cohort auditor on temporary modified copies; no native run."""
import argparse,json,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--hosts',type=Path,nargs=13,required=True);a=p.parse_args();checks={}
with tempfile.TemporaryDirectory(prefix='km-gva-board-mutations-') as tmp:
 root=Path(tmp).resolve()
 for kind in ('unchanged','overlay-event','software-byte','wrong-policy','lease'):
  folder=root/kind;folder.mkdir();hosts=[]
  for index,source in enumerate(a.hosts):
   d=folder/str(index);shutil.copytree(source.resolve(),d);mfile=d/'execution/manifest.json';m=json.loads(mfile.read_text())
   if m['arguments']:m['arguments']=[str(d/'assets'),str(d/'outputs'),m['arguments'][-1]]
   mfile.write_text(json.dumps(m));hosts.append(d)
  if kind=='overlay-event':
   f=hosts[4]/'execution/execution.stderr';f.write_text(f.read_text().replace('original=0 present=1 changed=1 key=Mac-F2268DAE','original=0 present=0 changed=0 key=Mac-F2268DAE'))
  elif kind=='software-byte':
   f=hosts[2]/'outputs/vt-frame-000.nv12';data=bytearray(f.read_bytes());data[0]^=1;f.write_bytes(data)
  elif kind=='wrong-policy':(hosts[4]/'assets/factory-policy-choice.json').write_text('{"mode":"wrong-board"}')
  elif kind=='lease':
   f=hosts[4]/'execution/manifest.json';m=json.loads(f.read_text());m['GPU_reservation']['state']='unresolved';f.write_text(json.dumps(m))
  r=subprocess.run([sys.executable,str(HERE/'audit.py'),'--build',str(a.build.resolve()),'--out',str(folder/'audit.json'),'--hosts',*map(str,hosts)],capture_output=True,text=True,timeout=90)
  if (r.returncode==0)!=(kind=='unchanged'):raise ValueError(kind+' unexpected result: '+r.stderr[-1200:])
  checks[kind]='PASS' if not r.returncode else 'EXPECTED_REFUSAL'
print(json.dumps({'status':'PASS','controls':checks,'native_execution':False},sort_keys=True))
