#!/usr/bin/env python3
"""Compiled-library AIR diagnosis and native repair with unchanged metadata.
Input to diagnosis is library+entry name, never a separate shader source/AIR.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,struct,subprocess
from metallib_air import extract,indexed_modules,MetallibError
from recognize_native_cas import air_contract,sass_contract
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[];results=[];entries=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,label,allowed=(0,),timeout=50):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True)
 if r.returncode not in allowed:raise SystemExit(r.stderr[-4000:] or str(r.returncode))
 return r
def signed(exe,label,args,allowed=(0,)):
 ex=out/(label+'-execution');run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(ex),'--timeout','20','--']+args,label,allowed,45)
 m=json.loads((ex/'manifest.json').read_text())
 if m['authoritative_ps_status'] or m['SIGKILL_requested']:raise SystemExit('HALT: child not terminal; do not retry')
 return ex,m
systems=[Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'),Path('/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin'),Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')]
before={str(p):sha(p) for p in systems}
for name in ['metallib_air.py','metallib_air_dump.c','recognize_native_cas.py','air_cas_probe.mm','reproduce_metallib_native_repair.py','run_signed_probe.py']:
 shutil.copyfile(ROOT/'tools'/name,out/name)
vendor=ROOT/'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/drivers/NVMTLDriver/air'
dump=out/'metallib_air_dump';run(['clang','-O2','-I'+str(vendor),str(out/'metallib_air_dump.c'),str(ROOT/'build/air-bitstream.o'),str(ROOT/'build/air-airir.o'),'-o',str(dump)],'build-AIR-dump')
common='#include <metal_stdlib>\nusing namespace metal;\nstruct P{uint seed,n,local,groups,variant;};\n';parts=[common]
names={'slot1':'cas_slot_one','live_noise':'cas_noise_live','permuted':'cas_result_swizzle','original_compare_control':'keep_original_comparand'}
for old,name in names.items():
 source=(ROOT/'results/native-cas-variants-captured'/old/'test.metal').read_text();body=source[source.index('kernel void test('):];parts.append(body.replace('kernel void test(','kernel void '+name+'(',1))
building=out/'fixture-building';building.mkdir();source=building/'fixture.metal';source.write_text('\n'.join(parts))
run(['xcrun','metal','-std=macos-metal2.4','-fno-fast-math','-c',str(source),'-o',str(building/'fixture.air')],'compile-fixture')
library=out/'library.metallib';run(['xcrun','metallib',str(building/'fixture.air'),'-o',str(library)],'link-fixture')
data=library.read_bytes();modules=indexed_modules(data);assert {m['name'] for m in modules}==set(names.values())
(out/'library-index.json').write_text(json.dumps([{k:v for k,v in m.items() if k!='wrapped_AIR'} for m in modules],indent=2)+'\n')
# Negative input checks do not enter the AIR reader or the driver.
rejections=[]
for label,modify in [('module-corrupt',lambda b:b.__setitem__(modules[0]['offset']+24,b[modules[0]['offset']+24]^1)),
                     ('out-of-range-bitcode',lambda b:struct.pack_into('<Q',b,72,0xfffffffffffffff0)),
                     ('wrong-length',lambda b:struct.pack_into('<Q',b,16,len(b)+1))]:
 bad=bytearray(data);modify(bad)
 try:indexed_modules(bytes(bad));raise AssertionError('Malformed library accepted')
 except MetallibError as e:rejections.append({'case':label,'rejected':True,'reason':str(e),'GPU_dispatch':False})
try:extract(data,'absent_entry');raise AssertionError('Missing function accepted')
except MetallibError as e:rejections.append({'case':'absent-entry','rejected':True,'reason':str(e),'GPU_dispatch':False})
(out/'container-negative-checks.json').write_text(json.dumps(rejections,indent=2)+'\n')
for old,name in names.items():
 d=out/name;d.mkdir();module=extract(data,name);(d/'embedded.air').write_bytes(module['wrapped_AIR'])
 ex,_=signed(dump,name+'-AIR',[str(d/'embedded.air'),name]);typed=json.loads((ex/'execution.stdout').read_text());(d/'typed-air.json').write_text(json.dumps(typed,indent=2)+'\n')
 air=air_contract(typed,name);capture=out/(name+'-compiler-output')
 ex,_=signed(ROOT/'build/compiler_output_trace',name+'-capture',[str(library),str(capture),'compute',name]);observed=json.loads((ex/'execution.stdout').read_text());assert observed['pipeline_created'] and not observed['gpu_dispatch'] and len(observed['captures'])==1
 blob=Path(observed['captures'][0]['file']).read_bytes();offset=8;code=None;metadata=None
 while True:
  nxt,kind,length=struct.unpack_from('<QII',blob,offset);assert length<=len(blob)-offset-16
  if kind==0x10005:code=blob[offset+16:offset+16+length]
  if kind==0x10004:metadata=blob[offset+16:offset+16+length]
  if not nxt:break
  offset+=nxt
 assert code and len(metadata)==232;(d/'native.sass').write_bytes(code);(d/'native.metadata').write_bytes(metadata)
 ex,_=signed(ROOT/'build/envydis-only/envydis/envydis',name+'-decode',['-m','gf100','-V','gk104','-i','-n',str(d/'native.sass')]);shutil.copyfile(ex/'execution.stdout',d/'native.asm')
 sass=sass_contract(code,(d/'native.asm').read_text(),air.get('expected_output_component',0));qualified=air['qualified'] and sass['qualified'];assert qualified==(old!='original_compare_control')
 policy={'policy_version':2,'qualified':qualified,'function':name,'AIR':air,'SASS':sass,'SASS_only_repair_forbidden':True,
  'embedded_AIR':{k:v for k,v in module.items() if k!='wrapped_AIR'},
  'hashes':{'library.metallib':sha(library),'typed-air.json':sha(d/'typed-air.json'),'native.sass':sha(d/'native.sass')},
  'layout':'permuted' if old=='permuted' else 'noise' if old=='live_noise' else 'standard',
  'intent':'original_comparand' if old=='original_compare_control' else 'post_CAS_expected','replacement_hashes':{}}
 if qualified:
  off=sass['redirect_offset'];length=len(code);assembly=d/'repair.easm'
  assembly.write_text(f'''.section #code 0;
.skip {off:#x};
long bra #repair_stub;
.skip {length-off-8:#x};
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
repair_stub:
long membar cta;
long mov b32 $r{sass['expected_register']} $r{sass['old_register']};
long bra {off+8:#x};
long nop;
long nop;
long nop;
long nop;
''')
  template=d/'assembled.bin';signed(ROOT/'results/native-cas-repaired/envyas',name+'-assemble',['-m','gf100','-V','gk104','-i','-o',str(template),str(assembly)])
  assembled=template.read_bytes();assert len(assembled)==length+64;patched=bytearray(code+assembled[length:]);patched[off:off+8]=assembled[off:off+8]
  assert all(patched[i:i+8]==code[i:i+8] for i in range(0,length,8) if i!=off)
  assert patched[length+8:length+16]==code[off:off+8];(d/'repaired.sass').write_bytes(patched);policy['replacement_hashes']['repaired']=sha(d/'repaired.sass')
 else:policy['replacement_hashes']['repaired']=sha(d/'native.sass')
 (d/'policy.json').write_text(json.dumps(policy,indent=2)+'\n');entries.append({'name':name,'directory':str(d),'policy':policy})
(out/'policies.json').write_text(json.dumps(entries,indent=2)+'\n')

# Fork the pinned import privately and preserve the native metadata bit-for-bit.
base=ROOT/'results/native-cas-repaired/PinnedNativeCASImport.mm';text=base.read_text();needle='thread_local NSData *expectedNativeOriginal=nullptr;';assert text.count(needle)==1;text=text.replace(needle,needle+'\nthread_local bool keepNativeMetadata=false;')
needle='''  put32(bytes,metadataOffset+28,c->config.registers);
  put32(bytes,metadataOffset+36,c->config.launch_word_9);
  put32(bytes,metadataOffset+44,c->config.launch_word_11);''';assert text.count(needle)==1
text=text.replace(needle,'''  if(keepNativeMetadata){
   c->config={u32(b,metadata.payload+28),u32(b,metadata.payload+36),u32(b,metadata.payload+44)};
   if(c->config.registers<1||c->config.registers>63){c->rejected=true;return nil;}
  }else{
   put32(bytes,metadataOffset+28,c->config.registers);
   put32(bytes,metadataOffset+36,c->config.launch_word_9);
   put32(bytes,metadataOffset+44,c->config.launch_word_11);
  }
  event[@"all_native_metadata_bytes_preserved"]=@(memcmp(bytes+metadataOffset,b+metadata.payload,metadata.size)==0);
  event[@"original_metadata_sha256_scope"]=@"Full metadata compared to the actual incoming native constructor payload, not copied from an offline file";''')
text+='''\nextern "C" id<MTLComputePipelineState> KPCreatePreservingNativeCASPipeline(
 id<MTLDevice>d,NSURL*l,NSString*f,NSData*original,NSData*replacement,NSError**error,NSDictionary**proof){
 if(keepNativeMetadata){fail(error,@"Nested native preservation context");return nil;}
 keepNativeMetadata=true;
 @try{return KPCreatePinnedNativeCASPipeline(d,l,f,original,replacement,{24,576,576},error,proof);}
 @finally{keepNativeMetadata=false;}
}\n'''
fork=out/'PreservingNativeCASImport.mm';fork.write_text(text);dylib=out/'libPreservingNativeCASImport.dylib'
run(['clang++','-O2','-std=c++17','-fno-objc-arc','-dynamiclib',str(fork),'-I'+str(ROOT/'src'),'-framework','Metal','-framework','Foundation','-install_name',str(dylib),'-o',str(dylib)],'build-preserving-import')
probe=out/'compiled_library_cas_probe';run(['clang++','-O2','-std=c++17','-fno-objc-arc','-DPINNED_NATIVE_CAS_IMPORT','-DQUALIFIED_NATIVE_CAS_IMPORT','-DCOMPILED_METALLIB_CAS_IMPORT',str(out/'air_cas_probe.mm'),'-I'+str(ROOT/'src'),str(dylib),'-framework','Metal','-framework','Foundation','-o',str(probe)],'build-probe')
for entry in entries:
 name=entry['name'];d=Path(entry['directory']);policy=entry['policy']
 for local in ([33,128] if policy['qualified'] else [33]):
  for variant in ([0,1] if policy['qualified'] else [1]):
   mode='native_repaired' if policy['qualified'] else 'negative_semantic_policy';case=f'{name}-{mode}-l{local}-v{variant}';directory=out/(case+'-outputs');directory.mkdir()
   plan={'mode':mode,'function':name,'library':str(library),'space':'threadgroup','local':local,'groups':3,'contended':True,
    'variant':variant,'require_native_lock_loop':True,'layout':policy['layout'],'intent':policy['intent'],'policy':str(d/'policy.json'),
    'typed_air':str(d/'typed-air.json'),'original_code':str(d/'native.sass'),'code':str(d/('repaired.sass' if policy['qualified'] else 'native.sass')),'code_kind':'repaired'}
   path=out/(case+'.plan.json');path.write_text(json.dumps(plan,indent=2)+'\n');ex,process=signed(probe,case,[str(path),str(directory)],(0,) if policy['qualified'] else (12,));result=json.loads((ex/'execution.stdout').read_text())
   results.append({'name':case,'fixture':name,'plan':plan,'execution':str(ex),'process':process,'result':result});(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
   if policy['qualified']:
    assert result['passed'] and len(result['runs'])==3 and result['import']['contract_verified'] and result['semantic_policy']['accepted']
    assert all(e['all_native_metadata_bytes_preserved'] and e['expected_original_code_identical'] and e['imported_code_identical'] for e in result['import']['events'])
    assert [e['registers'] for e in result['import']['events']]==[struct.unpack_from('<I', (d/'native.metadata').read_bytes(),28)[0]]
   else:assert not result['GPU_dispatch'] and result['failure_stage']=='semantic_policy'
after={str(p):sha(p) for p in systems};assert after==before
(out/'manifest.json').write_text(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system_before':before,'system_after':after,
 'library_sha256':sha(library),'library_only_semantic_input':True,'external_shader_source_or_AIR_required':False,'all_native_metadata_preserved':True,
 'source_hashes':{p.name:sha(p) for p in out.iterdir() if p.suffix in ['.py','.c','.mm']},
 'scope':'Selected compiled-library functions in own process, AIR semantic gate and original native GPR/launch/shared metadata preserved; not installed compiler repair or transparent application support.'},indent=2)+'\n')
print(json.dumps({'cases':len(results),'repaired_GPU_cases':sum(r['plan']['mode']=='native_repaired' for r in results),'all_children_terminal':True},indent=2))
