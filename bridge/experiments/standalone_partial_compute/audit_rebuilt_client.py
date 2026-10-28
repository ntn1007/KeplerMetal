#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the separately rebuilt public-client reference and GPU run."""
import argparse,hashlib,json,subprocess,sys
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(v,msg):
 if not v:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native',type=Path,required=True);p.add_argument('--auto',type=Path,required=True);p.add_argument('--runtime-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required');rows=[]
 for mode,raw in [('native',a.native),('auto',a.auto)]:
  d=raw.resolve();i=read(d/'inputs.json');m=read(d/'execution/manifest.json');need(i['mode']==mode and i['scenario']==0 and sha(d/'runtime_archive.a')==i['static_library_SHA256'],'Case or archive differs')
  for name in ('client.mm','bootstrap.mm','verify.py','experiment.py'):need(i['frozen']['src/'+name]==sha(HERE/name),'Source differs: '+name)
  need(i['frozen']['src/verify_partial_gpu_dual_copy.py']==sha(BRIDGE/'tools/verify_partial_gpu_dual_copy.py'),'CPU oracle differs')
  for name,digest in read(d/'archive-manifest.json')['source_SHA256'].items():need(i['frozen']['library-src/'+name]==digest==sha(BRIDGE/'src'/name),'Runtime source differs: '+name)
  for f in (d/'execution/application',d/'assets/bootstrap.dylib'):subprocess.run(['codesign','--verify','--strict',str(f)],check=True,capture_output=True)
  v=subprocess.run([sys.executable,'-I',str(d/'src/verify.py'),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Oracle failed: '+v.stderr[-1000:]);r=json.loads(v.stdout);need(r==read(d/'verification.stdout') and r['status']=='PASS','Recorded oracle differs');rows.append((i,m,r,d))
 need(rows[0][0]['static_library_SHA256']==rows[1][0]['static_library_SHA256'] and rows[0][0]['executable_SHA256']==rows[1][0]['executable_SHA256'],'Build differs')
 x,y=rows;need(x[1]['pid']!=y[1]['pid'] and datetime.fromisoformat(x[1]['completed_at'])<=datetime.fromisoformat(y[1]['started_at']),'Host processes overlap')
 fresh=read(a.runtime_build/'manifest.json');tested=read(x[3]/'archive-manifest.json');need(fresh['status']=='PASS' and tested['source_SHA256']==fresh['source_SHA256'] and tested['object_SHA256']==fresh['object_SHA256'] and len(tested['object_SHA256'])==7,'Runtime objects differ')
 for name,digest in fresh['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(x[3]/'runtime_archive.a'),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Archive member differs: '+name)
 symbols=subprocess.run(['nm','-u',str(x[3]/'application')],check=True,capture_output=True,text=True).stdout;need('Kepler' not in symbols and 'KPCPU' not in symbols,'Client imports project symbols')
 result={'status':'PASS','native_control_processes':1,'auto_processes':1,'nonoverlapping':True,'GPU_dispatches':y[2]['GPU_dispatches'],'GPU_invocations':y[2]['GPU_invocations'],'correct_uint32_words':y[2]['correct_uint32_words'],'public_client_imports_project_symbols':False,'runtime_archive_SHA256':x[0]['static_library_SHA256'],'signed_client_SHA256':x[0]['executable_SHA256'],'source_runtime_objects_match':True,'scope':'Archive-rebuilt pinned public-Metal test client, explicitly injected bootstrap, 1D case only.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
