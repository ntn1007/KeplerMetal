#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Alter preserved public-client evidence to test the offline oracle."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,tempfile

def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--same',type=Path,required=True);p.add_argument('--separate',type=Path,required=True);p.add_argument('--wrong-client',type=Path,required=True);a=p.parse_args();checks={}
 with tempfile.TemporaryDirectory(prefix='standalone-auto-copy-mutations-') as tmp:
  root=Path(tmp).resolve()
  for kind in ('unchanged','wrong-result','guard','copy-descriptor','ordering','factory-event','native-profile','preflight','unsafe-accept','restore','reservation','missing-refusal'):
   source=(a.wrong_client if kind=='missing-refusal' else a.separate if kind=='ordering' else a.same).resolve();dest=root/kind;shutil.copytree(source,dest);i=json.loads((dest/'inputs.json').read_text());manifest=dest/'execution/manifest.json';m=json.loads(manifest.read_text());library='wrong.metallib' if i['mode']=='wrong-library' else 'partial_dual.metallib';m['arguments']=[str(dest/'assets'/library),str(dest/'outputs'),str(i['scenario']),i['route']];write(manifest,m)
   if kind in ('wrong-result','guard'):
    f=dest/'outputs'/('after.geo.bin' if kind=='guard' else 'after.b.bin');data=bytearray(f.read_bytes());data[0 if kind=='guard' else 64]^=1;f.write_bytes(data)
   elif kind in ('unsafe-accept','restore'):
    f=dest/'execution/execution.stdout';data=json.loads(f.read_text());data['over_limit_refused' if kind=='unsafe-accept' else 'copy_blit_after_end_class']=False if kind=='unsafe-accept' else 'KMAutoBlit_fake';write(f,data)
   elif kind in ('copy-descriptor','ordering','factory-event','native-profile','preflight'):
    f=dest/'events.json';events=json.loads(f.read_text())
    if kind=='factory-event':events=[e for e in events if e['operation']!='automatic_compute_encoder']
    elif kind=='copy-descriptor':next(e for e in events if e['operation']=='GPU_partial_QMD_copy')['descriptor_pairs'][0]['destination']+=256
    elif kind=='ordering':next(e for e in events if e['operation']=='execute_bounded_partial_range')['predecessor_order'][0]['kind']='unordered'
    elif kind=='preflight':next(e for e in events if e['operation']=='prepare_automatic_partial_GPU_copy')['whole_range_preflight_before_initialization']=False
    else:next(e for e in events if e['operation']=='execute_bounded_partial_range')['evidence']['owner_original_profiles'][0]['native_register_count']+=1
    write(f,events)
   elif kind=='reservation':m['GPU_reservation']['state']='unresolved';write(manifest,m)
   elif kind=='missing-refusal':
    f=dest/'execution/execution.stderr';f.write_text(f.read_text().replace('KM_BOOT identity refused','KM_BOOT identity altered'))
   result=subprocess.run([sys.executable,'-I',str(dest/'src/verify.py'),str(dest)],capture_output=True,text=True,timeout=120);ok=result.returncode==0
   if ok!=(kind=='unchanged'):raise ValueError(kind+' unexpected result: '+result.stderr[-1000:])
   checks[kind]='PASS' if ok else 'EXPECTED_REFUSAL'
 print(json.dumps({'status':'PASS','checks':checks,'GPU_dispatch':False},sort_keys=True))
if __name__=='__main__':main()
