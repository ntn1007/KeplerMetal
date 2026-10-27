#!/usr/bin/env python3
"""Qualify a bounded AIR-aware native CAS repair on separately captured shaders.
No system file, driver, OCLP or global Objective-C class is changed.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,struct,subprocess
from recognize_native_cas import recognize

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();fixtures=a.fixtures.resolve();out=a.out.resolve();fixtures.relative_to(ROOT/'results');out.relative_to(ROOT/'results')
assert not out.exists();out.mkdir();commands=[];cases=[];policies=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
systems=[Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'),
         Path('/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin'),
         Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')]
before={str(p):sha(p) for p in systems}
def run(cmd,label,allowed=(0,),timeout=50):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True)
 if r.returncode not in allowed:raise SystemExit(r.stderr[-5000:] or f'{label}: {r.returncode}')
 return r
def signed(exe,label,args,allowed=(0,)):
 execution=out/(label+'-execution')
 run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),'--timeout','20','--']+args,label,allowed,45)
 m=json.loads((execution/'manifest.json').read_text())
 if m['authoritative_ps_status'] or m['SIGKILL_requested']:raise SystemExit('HALT: signed child not cleanly terminal')
 return execution,m

for source in ['reproduce_semantic_cas_repair.py','recognize_native_cas.py','verify_semantic_cas_repair.py','air_cas_probe.mm','run_signed_probe.py']:
 shutil.copyfile(ROOT/'tools'/source,out/source)
probe=out/'semantic_cas_probe';import_library=ROOT/'results/native-cas-repaired/libPinnedNativeCASImport.dylib'
assert sha(ROOT/'build/import-audit/libKeplerProgramImport.dylib')=='7719a27c9b659d6b4d87e1d6015c51b4d2cefb3238c47eae11073c3dd975dcd6'
run(['clang++','-O2','-std=c++17','-fno-objc-arc','-DPINNED_NATIVE_CAS_IMPORT','-DQUALIFIED_NATIVE_CAS_IMPORT',
 str(out/'air_cas_probe.mm'),'-I'+str(ROOT/'src'),str(import_library),'-framework','Metal','-framework','Foundation','-o',str(probe)],'build-probe')
assembler=ROOT/'results/native-cas-repaired/envyas';decoder=ROOT/'build/envydis-only/envydis/envydis'
for fixture in json.loads((fixtures/'fixtures.json').read_text()):
 name=fixture['name'];d=out/name;d.mkdir();src=Path(fixture['directory'])
 for file in fixture['hashes']:
  assert sha(src/file)==fixture['hashes'][file];shutil.copyfile(src/file,d/file)
 policy=recognize(d,decoder);original=(d/'native.sass').read_bytes()
 if hashlib.sha256(original).hexdigest()!=policy['hashes']['native.sass']:raise SystemExit('Native code changed after diagnosis')
 assert policy['qualified']==(name!='original_compare_control')
 if policy['qualified']:
  match=policy['SASS'];off=match['redirect_offset'];old=match['old_register'];expected=match['expected_register'];length=len(original)
  assembly=d/'repair.easm'
  assembly.write_text(f'''.section #code 0;
.skip {off:#x};
long bra #repair_stub;
.skip {length-off-8:#x};
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
repair_stub:
long membar cta;
long mov b32 $r{expected} $r{old};
long bra {off+8:#x};
long nop;
long nop;
long nop;
long nop;
''')
  template=d/'assembled.bin';signed(assembler,name+'-assemble',['-m','gf100','-V','gk104','-i','-o',str(template),str(assembly)])
  assembled=template.read_bytes();assert len(assembled)==length+64
  repaired=bytearray(original+assembled[length:]);repaired[off:off+8]=assembled[off:off+8]
  nop=bytearray(repaired);struct.pack_into('<Q',nop,length+16,0x4000000000001de4)
  assert repaired[length+8:length+16]==original[off:off+8]
  assert all(original[i:i+8]==repaired[i:i+8] for i in range(0,length,8) if i!=off)
  assert all(original[i:i+8]==repaired[i:i+8] for i in range(0,length,64))
  assert sum(repaired[i:i+8]!=nop[i:i+8] for i in range(0,len(repaired),8))==1
  for kind,data in [('repaired',repaired),('trampoline',nop)]:
   code=d/(kind+'.sass');code.write_bytes(data)
   ex,_=signed(decoder,name+'-decode-'+kind,['-m','gf100','-V','gk104','-i','-n',str(code)])
   shutil.copyfile(ex/'execution.stdout',d/(kind+'.asm'))
  listing=(d/'repaired.asm').read_text().splitlines()
  for address,text in {off:f'bra {length+8:#x}',length+8:'membar cta',length+16:f'mov b32 $r{expected} $r{old}',length+24:f'bra {off+8:#x}'}.items():
   assert text in next(line for line in listing if line.startswith(f'{address:08x}'))
  policy['replacement_hashes']={kind:sha(d/(kind+'.sass')) for kind in ['repaired','trampoline']}
 else:
  # A valid original-comparand shader collides with the defective shader in
  # SASS. Refuse it before importing any code, even with matching SASS bytes.
  policy['replacement_hashes']={'repaired':sha(d/'native.sass')}
 policy['intent']=fixture['intent'];policy['layout']=fixture['layout']
 (d/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
 policies.append({'fixture':name,'directory':str(d),'policy':policy})
(out/'policies.json').write_text(json.dumps(policies,indent=2)+'\n')
original_minimal=ROOT/'results/air-cas-final/threadgroup-native-compiler/native.sass'
assert (out/'original_compare_control/native.sass').read_bytes()==original_minimal.read_bytes()
assert (out/'original_compare_control/test.metallib').read_bytes()!=(ROOT/'results/cas-lowering-final/threadgroup/test.metallib').read_bytes()

def execute(fixture,mode,local,variant,negative=None):
 name=fixture['fixture'];d=Path(fixture['directory']);policy=fixture['policy'];case_name=f'{name}-{mode}-l{local}-v{variant}'+('-'+negative if negative else '')
 plan_path=out/(case_name+'.plan.json');output=out/(case_name+'-outputs');output.mkdir()
 kind='trampoline' if mode=='native_trampoline' else 'repaired'
 code=d/(kind+'.sass') if policy['qualified'] else d/'native.sass'
 plan={'mode':mode,'space':'threadgroup','local':local,'groups':3,'contended':True,'variant':variant,'require_native_lock_loop':True,
       'layout':policy['layout'],'intent':policy['intent'],'library':str(d/'test.metallib'),'air':str(d/'test.air'),
       'source':str(d/'test.metal'),'typed_air':str(d/'typed-air.json'),'original_code':str(d/'native.sass'),
       'code':str(code),'code_kind':kind,'policy':str(d/'policy.json')}
 if negative=='mismatched_library':plan['library']=str(out/'original_compare_control/test.metallib')
 if negative=='missing_policy':plan['policy']=str(out/'no-such-policy.json')
 if negative=='wrong_original_pin':
  wrong=out/'incorrect-original.sass';b=bytearray((d/'native.sass').read_bytes());b[0]^=1;wrong.write_bytes(b);plan['original_code']=str(wrong)
 plan_path.write_text(json.dumps(plan,indent=2)+'\n')
 ex,process=signed(probe,case_name,[str(plan_path),str(output)],(12,) if mode=='negative_semantic_policy' else (0,10))
 r=json.loads((ex/'execution.stdout').read_text())
 record={'name':case_name,'fixture':name,'plan':plan,'execution':str(ex),'process':process,'result':r}
 cases.append(record);(out/'results.json').write_text(json.dumps(cases,indent=2)+'\n')
 if mode=='negative_semantic_policy':
  assert r['failure_stage']=='semantic_policy' and not r['GPU_dispatch'] and not r['semantic_policy']['accepted']
  assert not r.get('import')
 else:
  assert r['GPU_dispatch'] and len(r['runs'])==3 and not r['guard_mismatches']
  if mode!='native':
   assert r['semantic_policy']['accepted'] and r['import']['contract_verified']
   assert all(e['expected_original_code_identical'] and e['imported_code_identical'] for e in r['import']['events'])
  wanted=mode=='native_repaired' or policy['intent']=='original_comparand'
  assert r['passed']==wanted, 'HALT: repaired/oracle/negative expectation differs: '+case_name

# No-dispatch rejection cases precede any new GPU test.
execute(policies[-1],'negative_semantic_policy',33,1)
for negative in ['mismatched_library','missing_policy','wrong_original_pin']:
 execute(policies[0],'negative_semantic_policy',33,1,negative)
# Each fixture is isolated. Equal and unequal operands and two group sizes
# qualify changed shared-address, register allocation and output component.
for fixture in policies:
 for local in [33,128]:
  for variant in [0,1]:
   for mode in (['native','native_trampoline','native_repaired'] if fixture['policy']['qualified'] else ['native']):
    execute(fixture,mode,local,variant)
after={str(p):sha(p) for p in systems};assert after==before
manifest={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fixture_source':str(fixtures),
 'system_before':before,'system_after':after,'system_unchanged':True,'SASS_semantic_collision_verified':True,
 'original_library':{'path':str(import_library),'sha256':sha(import_library)},
 'audited_import_unchanged':sha(ROOT/'build/import-audit/libKeplerProgramImport.dylib')=='7719a27c9b659d6b4d87e1d6015c51b4d2cefb3238c47eae11073c3dd975dcd6',
 'source_hashes':{p.name:sha(p) for p in out.iterdir() if p.suffix in ['.py','.mm']},
 'scope':'Three new AIR-aware, exact-input-pinned native shader repairs in own process, not general compiler repair or automatic support in unmodified applications.'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'attempts':len(cases),'GPU_cases':sum(c['result'].get('GPU_dispatch',False) for c in cases),'terminal_children':True},indent=2))
