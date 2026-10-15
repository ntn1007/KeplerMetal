#!/usr/bin/env python3
"""Pin and repair one observed native CAS program in our own process.
Keep all original instructions/schedules except one branch redirect, and replay
the displaced membar in a new scheduled block. No NVIDIA system binary changes.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, shutil, struct, subprocess

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();OUT=args.out.resolve();OUT.relative_to(ROOT/'results');assert not OUT.exists();OUT.mkdir()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
commands=[];results=[]
system=[Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'),
        Path('/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin'),
        Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')]
before={str(p):sha(p) for p in system}
def run(cmd,label,allowed=(0,),timeout=55):
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    (OUT/(label+'.stdout')).write_text(p.stdout);(OUT/(label+'.stderr')).write_text(p.stderr)
    commands.append({'label':label,'argv':cmd,'exit_code':p.returncode});(OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print(label,p.returncode,flush=True)
    if p.returncode not in allowed:raise SystemExit(p.stderr[-4000:] or f'{label}: {p.returncode}')
    return p
def signed(exe,label,argv,allowed=(0,)):
    execution=OUT/(label+'-execution');run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),
         '--out',str(execution),'--timeout','20','--']+argv,label+'-launch',allowed,45)
    m=json.loads((execution/'manifest.json').read_text())
    if m['authoritative_ps_status']:raise SystemExit('HALT: signed child remains present')
    return execution,m

vendor=ROOT/'vendor/envytools-f102b82381f3f11cee113d16374c87091db039d9';build=ROOT/'build/envydis-only'
assembler=OUT/'envyas'
run(['clang','-O2','-std=gnu11','-I'+str(vendor/'include'),'-I'+str(build/'include-generated'),
     str(vendor/'envydis/envyas.c'),str(build/'envydis/libenvy.a'),str(build/'util/libenvyutil.a'),
     str(build/'easm/libeasm.a'),str(build/'util/libenvyutil.a'),'-o',str(assembler)],'build-assembler')
assembly=OUT/'trampoline.easm';assembly.write_text('''.section #code 0;
.skip 0x2d0;
long bra #fix_expected;
.skip 0x68;
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
fix_expected:
long membar cta;
long mov b32 $r0 $r4;
long bra 0x2d8;
long nop;
long nop;
long nop;
long nop;
''')
template=OUT/'trampoline.bin';signed(assembler,'assemble',['-m','gf100','-V','gk104','-i','-o',str(template),str(assembly)])
assembled=template.read_bytes();assert len(assembled)==896
original_path=ROOT/'results/air-cas-final/threadgroup-native-compiler/native.sass';original=original_path.read_bytes()
assert sha(original_path)=='ea09f179ff169422f6f3ac8c3b1f85f020c52f5853106e68becbb0f408ef85e3' and len(original)==832
assert struct.unpack_from('<Q',original,0x2d0)[0]==0xe000000000001c05
patched=bytearray(original+assembled[0x340:0x380]);patched[0x2d0:0x2d8]=assembled[0x2d0:0x2d8]
control=bytearray(patched);struct.pack_into('<Q',control,0x350,0x4000000000001de4)
assert patched[0x348:0x350]==original[0x2d0:0x2d8]
assert all(patched[i:i+8]==original[i:i+8] for i in range(0,len(original),8) if i!=0x2d0)
assert all(patched[i:i+8]==original[i:i+8] for i in range(0,len(original),64))
code_paths={}
for name,data in [('replay',original),('trampoline',control),('repaired',patched)]:
    path=OUT/('native-'+name+'.sass');path.write_bytes(data);code_paths[name]=path
wrong=bytearray(original);wrong[0]^=1;wrong_path=OUT/'incorrect-original-pin.sass';wrong_path.write_bytes(wrong)
execution,_=signed(ROOT/'build/envydis-only/envydis/envydis','decode-repaired',
                   ['-m','gf100','-V','gk104','-i','-n',str(code_paths['repaired'])])
listing=(execution/'execution.stdout').read_text().splitlines()
expected={'000002d0':'bra 0x348','00000348':'membar cta','00000350':'mov b32 $r0 $r4','00000358':'bra 0x2d8'}
for address,text in expected.items():assert text in next(line for line in listing if line.startswith(address))

# Compile a separate bridge variant with a byte-exact native-input gate.
# The original audited source/library and all previously validated paths remain.
base=ROOT/'src/KeplerProgramImport.mm';source=base.read_text()
needle='thread_local Context *activeContext=nullptr;';assert source.count(needle)==1
source=source.replace(needle,needle+'\nthread_local NSData *expectedNativeOriginal=nullptr;')
needle=' if(valid)c->targetImports++;';assert source.count(needle)==1
source=source.replace(needle,''' bool expectedMatches=true;
 if(expectedNativeOriginal){expectedMatches=valid&&code.size==expectedNativeOriginal.length&&memcmp(b+code.payload,expectedNativeOriginal.bytes,code.size)==0;valid=valid&&expectedMatches;}
 if(valid)c->targetImports++;''')
needle=' const void*passed=input;NSUInteger size=length;NSMutableData*patched=nil;';assert source.count(needle)==1
source=source.replace(needle,''' if(expectedNativeOriginal)event[@"expected_original_code_identical"]=@(expectedMatches);
 const void*passed=input;NSUInteger size=length;NSMutableData*patched=nil;''')
source+='''\nextern "C" id<MTLComputePipelineState> KPCreatePinnedNativeCASPipeline(
 id<MTLDevice>device,NSURL*library,NSString*function,NSData*originalCode,NSData*newCode,
 KeplerImportConfig config,NSError**error,NSDictionary**evidence){
 if(expectedNativeOriginal||!originalCode.length){fail(error,@"Missing or nested native input contract");return nil;}
 expectedNativeOriginal=originalCode;
 @try{return KPCreatePipeline(device,library,function,newCode,config,error,evidence);}
 @finally{expectedNativeOriginal=nullptr;}
}\n'''
fork=OUT/'PinnedNativeCASImport.mm';fork.write_text(source)
library=OUT/'libPinnedNativeCASImport.dylib'
run(['clang++','-O2','-std=c++17','-fno-objc-arc','-dynamiclib',str(fork),'-I'+str(ROOT/'src'),
     '-framework','Metal','-framework','Foundation','-install_name',str(library),'-o',str(library)],'build-pinned-import')
probe_source=OUT/'air_cas_probe.mm';shutil.copyfile(ROOT/'tools/air_cas_probe.mm',probe_source)
probe=OUT/'air_cas_probe';run(['clang++','-O2','-std=c++17','-fno-objc-arc','-DPINNED_NATIVE_CAS_IMPORT',
     str(probe_source),'-I'+str(ROOT/'src'),str(library),'-framework','Metal','-framework','Foundation',
     '-o',str(probe)],'build-probe')
shutil.copyfile(Path(__file__),OUT/Path(__file__).name)
native_library=ROOT/'results/cas-lowering-final/threadgroup/test.metallib'
configurations=[('negative_native_pin',1,1,1)]
configurations += [(mode,1,1,variant) for mode in ['native','native_replay','native_trampoline'] for variant in [0,1]]
configurations += [('native_repaired',local,groups,variant) for local,groups in [(1,1),(32,3),(33,3),(128,3)] for variant in [0,1]]
for mode,local,groups,variant in configurations:
    name=f'{mode}-l{local}-g{groups}-v{variant}';path=OUT/(name+'.plan.json');output=OUT/(name+'-outputs');output.mkdir()
    code_key='repaired' if mode in ['native_repaired','negative_native_pin'] else 'trampoline' if mode=='native_trampoline' else 'replay'
    plan={'mode':mode,'space':'threadgroup','local':local,'groups':groups,'contended':True,'variant':variant,
          'library':str(native_library),'code':str(code_paths[code_key]),
          'original_code':str(wrong_path if mode=='negative_native_pin' else code_paths['replay'])}
    path.write_text(json.dumps(plan,indent=2)+'\n')
    execution,process=signed(probe,name,[str(path),str(output)],(4,) if mode=='negative_native_pin' else (0,10))
    result=json.loads((execution/'execution.stdout').read_text())
    if mode=='negative_native_pin':
        assert result['failure_stage']=='pipeline' and not result.get('GPU_dispatch')
        assert not any(e.get('code_replaced') for e in result['import']['events'])
    else:
        assert result.get('GPU_dispatch') and len(result['runs'])==3 and not result['guard_mismatches']
        if mode!='native':assert result['import']['contract_verified'] and all(e['expected_original_code_identical'] for e in result['import']['events'])
        if mode=='native_repaired' or not variant:assert result['passed'],result
        else:assert not result['passed'], 'Missing native/control failure: investigate before claiming causal repair'
    results.append({'name':name,'plan':plan,'execution':str(execution),'process':process,'result':result})
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
after={str(p):sha(p) for p in system};assert after==before
manifest={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system_before':before,
          'system_after':after,'system_unchanged':True,'original_native_code_sha256':sha(code_paths['replay']),
          'code_sha256':{k:sha(p) for k,p in code_paths.items()},'new_instruction_block':expected,
          'original_bytes_preserved_except_redirect':True,'all_original_schedule_words_preserved':True,
          'displaced_membar_replayed':True,'stub_delays_cycles':[1,16,16,1,1,1,1],
          'negative_input_pin_rejected':True,'source_sha256':{str(p):sha(p) for p in [base,fork,probe_source,OUT/Path(__file__).name,assembly,native_library]},
          'original_audited_import_library_unchanged':sha(ROOT/'build/import-audit/libKeplerProgramImport.dylib')=='7719a27c9b659d6b4d87e1d6015c51b4d2cefb3238c47eae11073c3dd975dcd6',
          'scope':'Exact shader-byte-pinned correction of native compiler output inside our process, not a general compiler patch or system driver deployment.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'cases':len(results),'repaired_cases':sum(r['plan']['mode']=='native_repaired' for r in results),
                  'known_failures':[r['name'] for r in results if not r['result'].get('passed') and r['plan']['mode']!='negative_native_pin']},indent=2))
