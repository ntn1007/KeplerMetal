#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck explicit slot-3 source provenance and existing CAS GPU receipts."""
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path
from recognize_native_cas import verify_decoder

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def need(v,why):
 if not v:raise ValueError(why)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('generated','previous-generated','build','final-build','module-overlay','decoder','out'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--runs',type=Path,nargs=6,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
 ov=a.module_overlay.resolve();generated=a.generated.resolve();prior=a.previous_generated.resolve();meta=read(ov/'inputs.json');v=meta['derived_variant'];source=ROOT/'experiments/cas_slot3/slot3.metal';data=source.read_bytes();digest=sha(source)
 need(v['source_SHA256']==digest==sha(ov/'results/slot3-source-variant/slot3.metal')==sha(ov/'results/native-cas-variants-captured/slot1/test.metal'),'variant source mismatch')
 need(v['replaced_fixture']=='slot1' and v['kernel_function']=='sdk_cas_slot' and v['physical_address_expected']=='0xc','variant identity')
 need(meta['source_SHA256']['results/native-cas-variants-captured/slot1/test.metal']==digest and meta['source_SHA256']['results/native-cas-variants-captured/fixtures.json']==sha(ov/'results/native-cas-variants-captured/fixtures.json'),'overlay snapshot mismatch')
 original=ov/'results/slot3-source-variant/original-fixtures.json';need(sha(original)==v['previous_manifest_SHA256'],'original fixture manifest mismatch')
 before=[r for r in read(original) if r['name']=='slot1'];after=[r for r in read(ov/'results/native-cas-variants-captured/fixtures.json') if r['name']=='slot1']
 need(len(before)==len(after)==1 and before[0]['hashes']['test.metal']==v['previous_source_SHA256'] and after[0]['hashes']=={'test.metal':digest},'fixture provenance mismatch')
 combined=(generated/'KeplerNativeCAS/examples/cas_client.metal').read_text();body=data.decode();body=body[body.index('kernel void test('):].replace('kernel void test(','kernel void sdk_cas_slot(',1);need(body in combined,'combined shader source mismatch')
 current=generated/'diagnosis-sdk_cas_slot';old=prior/'diagnosis-sdk_cas_slot';state=read(current/'diagnosis.json');oldstate=read(old/'diagnosis.json')
 need(state['candidate'] and oldstate['candidate'] and state['SASS']['shared_address']=='0xc' and oldstate['SASS']['shared_address']=='0x4','expected shared addresses differ')
 need(sha(current/'native.sass')!=sha(old/'native.sass') and verify_decoder((old/'native.sass').read_bytes(),(old/'native.asm').read_text(),a.decoder),'previous SASS identity or decoder differs')
 with tempfile.TemporaryDirectory(prefix='cas-slot3-audit-') as tmp:
  subout=Path(tmp)/'base.json';cmd=[sys.executable,str(Path(__file__).with_name('audit_cas_backedge_sdk.py')),'--generated',str(generated),'--build',str(a.build.resolve()),'--final-build',str(a.final_build.resolve()),'--module-overlay',str(ov),'--decoder',str(a.decoder.resolve()),'--out',str(subout),'--runs']+[str(x.resolve()) for x in a.runs]
  proc=subprocess.run(cmd,capture_output=True,text=True,timeout=180);need(proc.returncode==0,'base audit failed: '+proc.stderr[-2000:]);base=read(subout)
 rows=[]
 for path in a.runs:
  path=path.resolve();host=read(path/'results.json');mode=host['mode']
  if mode not in ('native','execute'):continue
  entries=[x for x in host['runs'] if x['function']=='sdk_cas_slot'];checked={x['file']:x for x in read(path/'independent-verification.json')['records']}
  need(len(entries)==18 and len({x['file'] for x in entries})==18 and {x['local'] for x in entries}=={33,128,1024} and {x['variant'] for x in entries}=={0,1},'slot3 run coverage')
  operations=sum(x['local']*x['groups'] for x in entries);wrong=sum(checked[x['file']]['wrong_words'] for x in entries)
  need(operations==21330 and wrong==(21303 if mode=='native' else 0),'slot3 numerical result differs')
  rows.append({'mode':mode,'dispatches':len(entries),'CAS_operations':operations,'wrong_words':wrong,'result_SHA256':sha(path/'results.json')})
 need(len(rows)==4 and sum(x['mode']=='execute' for x in rows)==2 and sum(x['mode']=='native' for x in rows)==2,'slot3 controls missing')
 result={'status':'PASS','source_SHA256':digest,'previous_source_SHA256':v['previous_source_SHA256'],'slot3_shared_address':'0xc','previous_shared_address':'0x4','slot3_native_SHA256':sha(current/'native.sass'),'previous_native_SHA256':sha(old/'native.sass'),'slot3_repaired_dispatches':sum(x['dispatches'] for x in rows if x['mode']=='execute'),'slot3_correct_CAS_operations':sum(x['CAS_operations'] for x in rows if x['mode']=='execute'),'slot3_native_wrong_words':sum(x['wrong_words'] for x in rows if x['mode']=='native'),'GPU_hosts':base['GPU_hosts'],'all_functions_CAS_operations':base['repaired_and_control_CAS_operations'],'all_functions_uint32_words':base['repaired_and_control_uint32_words'],'recognizer_SHA256':base['recognizer_SHA256'],'separate_rebuild':base['independent_final_rebuild'],'rebuild_object_and_client_match':base['final_object_and_client_identical_to_GPU_tested'],'rows':rows,'scope':'A fourth element of one explicitly allocated threadgroup atomic array; not dynamic offsets or a general driver repair.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
