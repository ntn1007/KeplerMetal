#!/usr/bin/env python3
"""Build an optional native CAS module and library-specific AIR/SASS certificates.
Compilation/capture/diagnosis only: no user GPU dispatch, system installation or
automatic approval for production use. SDK client GPU qualification is separate.
"""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import shutil
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
sdk=out/'KeplerNativeCAS';sdk.mkdir()
for name in ['include','src','lib','assets','examples']:(sdk/name).mkdir()
commands=[]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=60)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 commands.append({'label':label,'argv':argv,'exit_code':r.returncode})
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True)
 assert r.returncode==0,r.stderr[-4000:]
def signed(exe,label,args):
 ex=out/(label+'-execution')
 run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(ex),'--timeout','20','--']+args,label)
 d=json.loads((ex/'manifest.json').read_text());assert d['exit_code']==0 and not d['SIGKILL_requested'] and not d['authoritative_ps_status']
 return ex
for name in ['KeplerNativeCAS.h','KeplerNativeCAS.mm','KeplerNativeCASAdapter.inc','KeplerProgramImport.h']:
 shutil.copyfile(ROOT/'src'/name,sdk/'src'/name)
shutil.copyfile(ROOT/'src/KeplerNativeCAS.h',sdk/'include/KeplerNativeCAS.h')
obj=out/'KeplerNativeCAS.o'
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-fvisibility=hidden','-I',str(sdk/'src'),'-c',str(sdk/'src/KeplerNativeCAS.mm'),'-o',str(obj)],'build-module')
archive=sdk/'lib/libKeplerNativeCAS.a';run(['ar','rcs',str(archive),str(obj)],'archive-module')
fixture=sdk/'examples/cas_client.metal'
common='#include <metal_stdlib>\nusing namespace metal;\nstruct P{uint seed,n,local,groups,variant;};\n'
parts=[common];names=[]
for layout,function in [('minimal','sdk_cas_expected'),('slot1','sdk_cas_slot'),('live_noise','sdk_cas_noise'),('permuted','sdk_cas_swizzle'),('original_compare_control','sdk_keep_comparand')]:
 old='original_compare_control' if layout=='minimal' else layout
 source=(ROOT/'results/native-cas-variants-captured'/old/'test.metal').read_text()
 body=source[source.index('kernel void test('):].replace('kernel void test(','kernel void '+function+'(',1)
 if layout=='minimal':body=body.replace('uint expected=compare;','').replace('a,&expected,','a,&compare,')
 parts.append(body);names.append((layout,function))
fixture.write_text('\n'.join(parts));air=out/'cas_client.air';library=sdk/'assets/cas_client.metallib'
run(['xcrun','metal','-std=macos-metal2.4','-fno-fast-math','-c',str(fixture),'-o',str(air)],'client-metal')
run(['xcrun','metallib',str(air),'-o',str(library)],'client-metallib')
profiles=[]
for layout,function in names:
 diagnosis=out/('diagnosis-'+function)
 run(['python3',str(ROOT/'tools/plan_native_metallib_repair.py'),'--library',str(library),'--function',function,'--out',str(diagnosis)],'plan-'+function)
 state=json.loads((diagnosis/'diagnosis.json').read_text());candidate=state['candidate'];assert candidate==(layout!='original_compare_control')
 cert={'schema':1,'candidate':candidate,'function':function,'intent':'post_CAS_expected' if candidate else 'original_comparand',
       'SASS_only_repair_forbidden':True,'AIR':state['AIR'],'SASS':state.get('SASS',{}),'embedded_AIR':state['embedded_AIR'],
       'library_SHA256':sha(library),'GPU_qualification_pending':True,'scope':'Developer-approved per-function diagnosis; runtime identities/constructor checked, GPU correctness qualified separately'}
 if candidate:
  original=(diagnosis/'native.sass').read_bytes();metadata=(diagnosis/'native.metadata').read_bytes();s=state['SASS'];redirect=s['redirect_offset'];length=len(original)
  assembly=diagnosis/'repair.easm';assembly.write_text(f'''.section #code 0;
.skip {redirect:#x};
long bra #repair_stub;
.skip {length-redirect-8:#x};
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
repair_stub:
long membar cta;
long mov b32 $r{s['expected_register']} $r{s['old_register']};
long bra {redirect+8:#x};
long nop;
long nop;
long nop;
long nop;
''')
  binary=diagnosis/'assembled.bin';signed(ROOT/'results/native-cas-repaired/envyas',function+'-assemble',['-m','gf100','-V','gk104','-i','-o',str(binary),str(assembly)])
  assembled=binary.read_bytes();assert len(assembled)==length+64
  repaired=bytearray(original+assembled[length:]);repaired[redirect:redirect+8]=assembled[redirect:redirect+8]
  assert [i for i in range(0,length,8) if repaired[i:i+8]!=original[i:i+8]]==[redirect]
  assert struct.unpack_from('<Q',repaired,length+16)[0]==(0x2800000000001de4|(s['old_register']<<26)|(s['expected_register']<<14))
  (diagnosis/'repaired.sass').write_bytes(repaired)
  for prefix,data in [('original_code',original),('repaired_code',repaired),('native_metadata',metadata)]:
   cert[prefix+'_base64']=base64.b64encode(data).decode();cert[prefix+'_SHA256']=hashlib.sha256(data).hexdigest()
  decoded=signed(ROOT/'build/envydis-only/envydis/envydis',function+'-decode-repair',['-m','gf100','-V','gk104','-i','-n',str(diagnosis/'repaired.sass')])
  listing=(decoded/'execution.stdout').read_text();assert f'mov b32 $r{s["expected_register"]} $r{s["old_register"]}' in listing
 path=sdk/'assets'/(function+'.certificate.json');path.write_text(json.dumps(cert,indent=2)+'\n')
 profiles.append({'function':function,'layout':'standard' if layout in ['minimal','slot1','original_compare_control'] else 'noise' if layout=='live_noise' else 'permuted',
                  'candidate':candidate,'certificate':path.name,'certificate_SHA256':sha(path),'diagnosis':str(diagnosis)})
manifest={'library':'cas_client.metallib','library_SHA256':sha(library),'profiles':profiles,'GPU_qualification_pending':True,
          'driver_SHA256':'2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054','system_modified':False,'Qwen_job_ids':[]}
(sdk/'assets/client-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
build={'Git_branch':'main','Git_commit':None,'source_SHA256':{str(x.relative_to(sdk)):sha(x) for x in (sdk/'src').iterdir()},
       'static_archive_SHA256':sha(archive),'object_SHA256':sha(obj),'source_transport_provenance':json.loads((ROOT/'results/native-cas-sdk-source-provenance.json').read_text()),
       'commands':commands,'system_modified':False,'GPU_user_dispatch':False}
(sdk/'BUILD_MANIFEST.json').write_text(json.dumps(build,indent=2)+'\n')
print(json.dumps({'SDK':str(sdk),'candidate_functions':sum(x['candidate'] for x in profiles),'rejected_functions':sum(not x['candidate'] for x in profiles),'GPU_user_dispatch':False},indent=2))
