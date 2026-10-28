#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind a CAS SDK qualification to the exact post-backedge recognizer source."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
from recognize_native_cas import sass_contract

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def need(v,why):
 if not v:raise ValueError(why)
def check_diagnostics(generated,overlay,recognizer):
 sources=json.loads((overlay/'inputs.json').read_text())['source_SHA256'];h=sha(recognizer)
 need(h==sources['tools/recognize_native_cas.py']==sha(overlay/'tools/recognize_native_cas.py'),'overlay recognizer differs')
 manifest=json.loads((generated/'KeplerNativeCAS/assets/client-manifest.json').read_text());proof=[]
 for row in manifest['profiles']:
  name=row['function'];d=generated/('diagnosis-'+name);state=json.loads((d/'diagnosis.json').read_text())
  need(sha(d/'recognize_native_cas.py')==h,'captured recognizer differs: '+name)
  if row['candidate']:
   code=(d/'native.sass').read_bytes();listing=(d/'native.asm').read_text();component=state['AIR']['expected_output_component']
   actual=sass_contract(code,listing,component);need(actual==state['SASS'] and actual['qualified'],'current structural diagnosis differs: '+name)
  else:need(not state['AIR']['qualified'] and not state['candidate'],'negative AIR differs: '+name)
  proof.append({'function':name,'candidate':row['candidate'],'recognizer_SHA256':h})
 return h,proof

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('generated','build','final-build','module-overlay','decoder','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--runs',type=Path,nargs=6,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
 generated=a.generated.resolve();overlay=a.module_overlay.resolve();recognizer=Path(__file__).with_name('recognize_native_cas.py')
 h,proof=check_diagnostics(generated,overlay,recognizer)
 cmd=[sys.executable,str(Path(__file__).with_name('audit_cas_sdk_qualification.py')),'--generated',str(generated),'--build',str(a.build.resolve()),'--final-build',str(a.final_build.resolve()),'--module-overlay',str(overlay),'--decoder',str(a.decoder.resolve()),'--runs']+[str(x.resolve()) for x in a.runs]
 child=subprocess.run(cmd,capture_output=True,text=True,timeout=120);need(child.returncode==0,'SDK auditor failed: '+child.stderr[-2000:]);r=json.loads(child.stdout);need(r['status']=='PASS','SDK qualification differs')
 r['recognizer_SHA256']=h;r['diagnosis_source_checked']=proof;r['independent_final_rebuild']=a.final_build.resolve()!=a.build.resolve();r['scope']='Exact regenerated certificates and adapted client, with current recognizer provenance; not a system-driver repair or performance result.'
 with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ('certificates','diagnosis_source_checked')},sort_keys=True))
if __name__=='__main__':main()
