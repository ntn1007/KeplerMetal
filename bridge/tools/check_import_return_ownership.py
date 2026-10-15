#!/usr/bin/env python3
"""Compare actual legacy/candidate declarations against the SAME +1 MRC object."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);old=out/'legacy';new=out/'annotated';old.mkdir();new.mkdir();source=ROOT/'src/KeplerProgramImport.h';raw=source.read_text();assert raw.count('NS_RETURNS_RETAINED')in [0,6];raw=raw.replace(' NS_RETURNS_RETAINED','')
(old/'KeplerProgramImport.h').write_text(raw);candidate=raw.replace('NSDictionary **evidence);','NSDictionary **evidence) NS_RETURNS_RETAINED;').replace('NSUInteger length, bool noCopy);','NSUInteger length, bool noCopy) NS_RETURNS_RETAINED;');assert candidate.count('NS_RETURNS_RETAINED')==6;(new/'KeplerProgramImport.h').write_text(candidate);commands=[]
for name in ['return_ownership_fixture.mm','return_ownership_caller.mm']:shutil.copyfile(ROOT/'tools'/name,out/name)
def run(args,label):
 args=[str(x)for x in args];r=subprocess.run(args,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':args,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2000:];return r.stdout
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',old,'-c',out/'return_ownership_fixture.mm','-o',out/'fixture.o'],'MRC-fixture')
result={}
for label,header in [('legacy',old),('annotated',new)]:
 run(['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',header,out/'return_ownership_caller.mm',out/'fixture.o','-framework','Foundation','-framework','Metal','-o',out/(label+'-caller')],label+'-ARC-build');d=json.loads(run([out/(label+'-caller')],label+'-CPU-run'));assert d['CPU_only']and not d['Metal_device_created']and d['created']==6;assert d['destroyed']==(0 if label=='legacy'else 6);assert all(row['alive_after_ARC_pool']==(label=='legacy')for row in d['rows']);result[label]=d
receipt={'status':'PASS','CPU_only':True,'same_MRC_fixture_SHA256':sha(out/'fixture.o'),'legacy_header_SHA256':sha(old/'KeplerProgramImport.h'),'candidate_header_SHA256':sha(new/'KeplerProgramImport.h'),'implementation_source_SHA256':sha(ROOT/'src/KeplerProgramImport.mm'),'implementation_contract':'Actual MRC factories return retained new... objects; CPU fixture models +1 ownership, not the NVIDIA GPU implementation','results':result,'real_GPU_pipeline_lifetime':'NOT_RUN'}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k!='results'}))
