#!/usr/bin/env python3
"""Compile/capture native variants without GPU dispatch, preserving originals."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
commands=[];fixtures=[]
def run(cmd,label,allowed=(0,)):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=50)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True);assert r.returncode in allowed,r.stderr[-4000:];return r
def signed(exe,label,args):
 execution=out/(label+'-execution')
 run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),'--timeout','20','--']+args,label)
 m=json.loads((execution/'manifest.json').read_text());assert not m['authoritative_ps_status'] and not m['SIGKILL_requested']
 return execution
upstream=ROOT/'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/drivers/NVMTLDriver/air'
dump_source=out/'native_cas_air_dump.c';shutil.copyfile(ROOT/'tools/native_cas_air_dump.c',dump_source);dump=out/'native_cas_air_dump'
run(['clang','-O2','-I'+str(upstream),str(dump_source),str(ROOT/'build/air-bitstream.o'),str(ROOT/'build/air-airir.o'),'-o',str(dump)],'build-air-dump')
common='#include <metal_stdlib>\nusing namespace metal;\nstruct P{uint seed,n,local,groups,variant;};\n'
sig='kernel void test(constant P&p [[buffer(0)]],device uint4*out [[buffer(1)]],device atomic_uint*global [[buffer(3)]],uint i [[thread_position_in_grid]],uint tid [[thread_index_in_threadgroup]],uint group [[threadgroup_position_in_grid]]){'
for name in ['slot1','live_noise','permuted','original_compare_control']:
 d=out/name;d.mkdir();slot=1 if name=='slot1' else 0;array=2 if slot else 1
 init=f'uint initial=p.seed+group*0x10001u;uint replacement=p.seed^0x55667788u;threadgroup atomic_uint shared[{array}];threadgroup atomic_uint*a=&shared[{slot}];if(tid==0)atomic_store_explicit(a,initial,memory_order_relaxed);threadgroup_barrier(mem_flags::mem_threadgroup);'
 body='uint compare=initial^(p.variant?1u:0u);'
 if name=='live_noise':body+='uint noise=(p.seed*0x9e3779b9u)^(i*17u);'
 if name=='original_compare_control':body+='uint expected=compare;'
 body+='bool success=atomic_compare_exchange_weak_explicit(a,&'+('expected' if name=='original_compare_control' else 'compare')+',replacement,memory_order_relaxed,memory_order_relaxed);threadgroup_barrier(mem_flags::mem_threadgroup);uint final=atomic_load_explicit(a,memory_order_relaxed);'
 store='uint4(i,compare,uint(success),final)' if name=='permuted' else 'uint4(compare,uint(success),final,i^noise)' if name=='live_noise' else 'uint4(compare,uint(success),final,i)'
 source=d/'test.metal';source.write_text(common+sig+init+body+'out[i]='+store+';}\n')
 air=d/'test.air';library=d/'test.metallib'
 run(['xcrun','metal','-std=macos-metal2.4','-fno-fast-math','-c',str(source),'-o',str(air)],name+'-metal')
 run(['xcrun','metallib',str(air),'-o',str(library)],name+'-library')
 ex=signed(dump,name+'-air',[str(air)]);typed=json.loads((ex/'execution.stdout').read_text());(d/'typed-air.json').write_text(json.dumps(typed,indent=2)+'\n')
 capture=out/(name+'-compiler-output');ex=signed(ROOT/'build/compiler_output_trace',name+'-capture',[str(library),str(capture),'compute','test'])
 observation=json.loads((ex/'execution.stdout').read_text());assert observation['pipeline_created'] and not observation['gpu_dispatch'] and len(observation['captures'])==1
 container=Path(observation['captures'][0]['file']).read_bytes();offset=8;code=None
 while offset+16<=len(container):
  next_offset,kind,size=struct.unpack_from('<QII',container,offset);assert size<=len(container)-offset-16
  if kind==0x10005:code=container[offset+16:offset+16+size]
  if not next_offset:break
  assert next_offset>=16+size and offset+next_offset<len(container);offset+=next_offset
 assert code is not None;code_path=d/'native.sass';code_path.write_bytes(code)
 ex=signed(ROOT/'build/envydis-only/envydis/envydis',name+'-decode',['-m','gf100','-V','gk104','-i','-n',str(code_path)])
 shutil.copyfile(ex/'execution.stdout',d/'native.asm')
 fixtures.append({'name':name,'layout':'permuted' if name=='permuted' else 'noise' if name=='live_noise' else 'standard',
  'intent':'original_comparand' if name=='original_compare_control' else 'post_CAS_expected','directory':str(d),
  'hashes':{p.name:sha(p) for p in [source,air,library,code_path,d/'native.asm',d/'typed-air.json']},'GPU_dispatch':False})
 (out/'fixtures.json').write_text(json.dumps(fixtures,indent=2)+'\n')
shutil.copyfile(Path(__file__),out/Path(__file__).name)
(out/'manifest.json').write_text(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fixtures':fixtures,
 'GPU_dispatch':False,'constructor_capture_not_resident_GPU_dump':True,'source_hashes':{p.name:sha(p) for p in [dump_source,out/Path(__file__).name]}},indent=2)+'\n')
