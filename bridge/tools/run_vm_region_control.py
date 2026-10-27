#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run CPU-only own-process VM controls, with immutable provenance."""
import hashlib,json,subprocess,sys
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(build,out):
 build=Path(build).resolve();out=Path(out).resolve()
 if out.exists() or not out.parent.is_dir():raise ValueError('fresh output path required')
 binary=build/'vm-control';source=build/'source.c';assert binary.is_file() and source.is_file()
 subprocess.run(['codesign','--verify','--strict',str(binary)],check=True,capture_output=True,timeout=15)
 binary_hash,source_hash=sha(binary),sha(source);out.mkdir();rows=[];seen=set()
 for mode in ('positive','positive','reject','invalid'):
  p=subprocess.Popen([str(binary),mode],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  stdout,stderr=p.communicate(timeout=10);assert p.pid not in seen;seen.add(p.pid)
  if mode=='invalid':assert p.returncode==2 and not stdout
  else:
   assert p.returncode==0 and not stderr;d=json.loads(stdout)
   assert d['mode']==mode and d['target_present_before'] and d['adjacent_guards_preserved'] and not d['gpu_or_iokit_called'] and d['cleanup_status']==0
   assert d['target_present_after']==(mode=='reject') and d['target_deallocate_calls']==(0 if mode=='reject' else 1)
  rows.append({'mode':mode,'pid':p.pid,'exit_code':p.returncode,'result':json.loads(stdout) if stdout else None})
 assert sha(binary)==binary_hash and sha(source)==source_hash
 result={'status':'PASS','scope':'own-process anonymous Mach VM only','binary_sha256':binary_hash,'source_sha256':source_hash,'runs':rows,'iokit_mapping_cleanup_proved':False}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
