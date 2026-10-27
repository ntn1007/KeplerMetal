#!/usr/bin/env python3
"""Diagnose one compiled kernel using its own embedded AIR and native program.
This planner never dispatches and does not turn a candidate into deployment.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,struct,subprocess
from metallib_air import extract,MetallibError
from recognize_native_cas import air_contract,sass_contract,verify_decoder
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--function',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(x):
 (out/'diagnosis.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x,indent=2))
def run(cmd,label,allowed=(0,)):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode in allowed,r.stderr[-4000:];return r
def signed(exe,label,args,allowed=(0,)):
 ex=out/(label+'-execution');r=run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(ex),'--timeout','20','--']+args,label,allowed)
 m=json.loads((ex/'manifest.json').read_text());assert not m['SIGKILL_requested'] and not m['authoritative_ps_status'];return ex,r.returncode
library=out/'input.metallib';shutil.copyfile(a.library,library)
state={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'function':a.function,'input_library_SHA256':sha(library),
       'GPU_dispatch':False,'qualified_for_deployment':False,'source_shader_or_AIR_input':False,
       'scope':'Offline/pipeline candidate diagnosis. GPU correctness and supported application integration must be qualified separately.'}
for name in ['plan_native_metallib_repair.py','metallib_air.py','recognize_native_cas.py','metallib_air_dump.c']:(out/name).write_bytes((ROOT/'tools'/name).read_bytes())
try:module=extract(library.read_bytes(),a.function)
except MetallibError as e:save({**state,'candidate':False,'stage':'container','reason':str(e)});raise SystemExit(0)
(out/'embedded.air').write_bytes(module['wrapped_AIR']);state['embedded_AIR']={k:v for k,v in module.items() if k!='wrapped_AIR'}
dump=out/'metallib_air_dump';vendor=ROOT/'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/drivers/NVMTLDriver/air'
run(['clang','-O2','-I'+str(vendor),str(out/'metallib_air_dump.c'),str(ROOT/'build/air-bitstream.o'),str(ROOT/'build/air-airir.o'),'-o',str(dump)],'build-reader')
ex,_=signed(dump,'read-AIR',[str(out/'embedded.air'),a.function]);typed=json.loads((ex/'execution.stdout').read_text());(out/'typed-air.json').write_text(json.dumps(typed,indent=2)+'\n');AIR=air_contract(typed,a.function);state['AIR']=AIR
if not AIR['qualified']:save({**state,'candidate':False,'stage':'AIR','reason':AIR['reason']});raise SystemExit(0)
ex,status=signed(ROOT/'build/compiler_output_trace','capture-native',[str(library),str(out/'native-capture'),'compute',a.function],(0,4));observation=json.loads((ex/'execution.stdout').read_text());state['native_observation']=observation
if status or not observation['pipeline_created']:save({**state,'candidate':False,'stage':'native_pipeline'});raise SystemExit(0)
assert not observation['gpu_dispatch'] and len(observation['captures'])==1
blob=Path(observation['captures'][0]['file']).read_bytes();offset=8;code=None;metadata=None
while True:
 nxt,kind,size=struct.unpack_from('<QII',blob,offset);assert size<=len(blob)-offset-16
 if kind==0x10005:code=blob[offset+16:offset+16+size]
 if kind==0x10004:metadata=blob[offset+16:offset+16+size]
 if not nxt:break
 offset+=nxt
assert code and metadata;(out/'native.sass').write_bytes(code);(out/'native.metadata').write_bytes(metadata)
decoder=ROOT/'build/envydis-only/envydis/envydis';ex,_=signed(decoder,'decode-native',['-m','gf100','-V','gk104','-i','-n',str(out/'native.sass')]);shutil.copyfile(ex/'execution.stdout',out/'native.asm');listing=(out/'native.asm').read_text()
if not verify_decoder(code,listing,decoder):save({**state,'candidate':False,'stage':'decoder','reason':'Offline decoder missing, unpinned or listing differs'});raise SystemExit(0)
state['decoder_reproduced_listing']=True
SASS=sass_contract(code,listing,AIR['expected_output_component']);state['SASS']=SASS
if (out/'native.sass').read_bytes()!=code or (out/'native.metadata').read_bytes()!=metadata or sha(library)!=state['input_library_SHA256']:
 save({**state,'candidate':False,'stage':'snapshot','reason':'Native snapshot or library changed during diagnosis'});raise SystemExit(0)
state['artifact_SHA256']={p.name:sha(p) for p in [library,out/'embedded.air',out/'typed-air.json',out/'native.asm']}
state['artifact_SHA256'].update({'native.sass':hashlib.sha256(code).hexdigest(),'native.metadata':hashlib.sha256(metadata).hexdigest()})
save({**state,'candidate':SASS['qualified'],'stage':'AIR_and_SASS','native_metadata_preservation_required':True,
      'reason':'Candidate only; matching semantics/structure does not substitute for GPU qualification.' if SASS['qualified'] else SASS['reason']})
