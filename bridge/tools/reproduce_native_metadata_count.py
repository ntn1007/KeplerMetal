#!/usr/bin/env python3
"""Normalize the identified native instruction-count field in a private fork.
GPR, launch and all other native metadata remain unchanged. No system mutation.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,struct,subprocess
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[];cases=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,label,allowed=(0,)):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode in allowed,r.stderr[-4000:];return r
base=ROOT/'results/metallib-native-preservation';source=(base/'PreservingNativeCASImport.mm').read_text()
needle='''   if(c->config.registers<1||c->config.registers>63){c->rejected=true;return nil;}''';assert source.count(needle)==1
source=source.replace(needle,needle+'''
   uint32_t originalCount=u32(b,metadata.payload),newCount=(uint32_t)(c->code.length/8-1);
   if(originalCount!=code.size/8-1){c->rejected=true;return nil;}
   put32(bytes,metadataOffset,newCount);
   event[@"original_instruction_count"]=@(originalCount);event[@"normalized_instruction_count"]=@(newCount);
   bool unchanged=true;for(size_t i=4;i<metadata.size;i++)if(bytes[metadataOffset+i]!=b[metadata.payload+i])unchanged=false;
   event[@"native_metadata_preserved_except_instruction_count"]=@(unchanged);''')
needle='''if(!((i>=28&&i<32)||(i>=36&&i<40)||(i>=44&&i<48))&&bytes[metadataOffset+i]!=b[metadata.payload+i])preserved=false;''';assert source.count(needle)==1
source=source.replace(needle,'''if(!((keepNativeMetadata&&i<4)||(i>=28&&i<32)||(i>=36&&i<40)||(i>=44&&i<48))&&bytes[metadataOffset+i]!=b[metadata.payload+i])preserved=false;''')
needle='''event[@"decoded_code_bytes"]=@(u64(variant,24));event[@"decoded_registers"]=@(u32(variant,48));''';assert source.count(needle)==1
source=source.replace(needle,needle+'''event[@"decoded_instruction_count"]=@(u32(variant,44));
   if(keepNativeMetadata&&u32(variant,44)!=c->code.length/8-1)c->rejected=true;''')
fork=out/'NormalizedNativeCASImport.mm';fork.write_text(source);dylib=out/'libNormalizedNativeCASImport.dylib'
run(['clang++','-O2','-std=c++17','-fno-objc-arc','-dynamiclib',str(fork),'-I'+str(ROOT/'src'),'-framework','Metal','-framework','Foundation','-install_name',str(dylib),'-o',str(dylib)],'build-import')
src=out/'air_cas_probe.mm';shutil.copyfile(base/src.name,src);probe=out/'normalized_cas_probe'
run(['clang++','-O2','-std=c++17','-fno-objc-arc','-DPINNED_NATIVE_CAS_IMPORT','-DQUALIFIED_NATIVE_CAS_IMPORT','-DCOMPILED_METALLIB_CAS_IMPORT',str(src),'-I'+str(ROOT/'src'),str(dylib),'-framework','Metal','-framework','Foundation','-o',str(probe)],'build-probe')
for name in ['cas_slot_one','cas_noise_live','cas_result_swizzle']:
 for variant in [0,1]:
  previous=base/f'{name}-native_repaired-l33-v{variant}.plan.json';plan=json.loads(previous.read_text());label=f'{name}-v{variant}';path=out/(label+'.plan.json');path.write_text(json.dumps(plan,indent=2)+'\n');outputs=out/(label+'-outputs');outputs.mkdir();execution=out/(label+'-execution')
  run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(probe),'--out',str(execution),'--timeout','20','--',str(path),str(outputs)],label)
  process=json.loads((execution/'manifest.json').read_text());assert not process['SIGKILL_requested'] and not process['authoritative_ps_status'];result=json.loads((execution/'execution.stdout').read_text());cases.append({'name':label,'plan':plan,'process':process,'result':result});(out/'results.json').write_text(json.dumps(cases,indent=2)+'\n')
  assert result['passed'] and result['import']['contract_verified'] and all(e['native_metadata_preserved_except_instruction_count'] and e['decoded_instruction_count']==e['normalized_instruction_count'] for e in result['import']['events'])
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());(out/'manifest.json').write_text(json.dumps({'source_hashes':{p.name:sha(p) for p in [fork,src,out/Path(__file__).name]},'system_modified':False,'native_GPR_and_launch_metadata_unchanged':True,'normalized_field':'metadata.word0 = code_words-1, mapped to FunctionVariant+44 and pipeline performance instruction count','scope':'Six GPU configurations on known library shapes; not general compiler correction or new Metal family.'},indent=2)+'\n')
print(json.dumps({'cases':len(cases),'all_children_terminal':True},indent=2))
