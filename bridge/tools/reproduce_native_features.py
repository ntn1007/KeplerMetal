#!/usr/bin/env python3
"""Native argument-buffer, SIMD and CAS tests. No compiler import or system edits."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--selection',choices=['initial','extended'],default='initial');ap.add_argument('--only',choices=['all','arguments','simd','cas'],default='all');args=ap.parse_args();OUT=args.out.resolve();OUT.relative_to(ROOT/'results');assert not OUT.exists();OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
commands=[];records=[]
def run(cmd,label,timeout=60):
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    (OUT/(label+'.stdout')).write_text(p.stdout);(OUT/(label+'.stderr')).write_text(p.stderr);commands.append({'label':label,'argv':cmd,'exit_code':p.returncode});(OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');return p
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');before=sha(driver)
system_files=[driver,Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'),Path('/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin')]
system_hashes={str(p):sha(p) for p in system_files}
probe=OUT/'native_features_probe';source=ROOT/'tools/native_features_probe.mm';shutil.copyfile(source,OUT/source.name)
for extra in [Path(__file__),ROOT/'tools/verify_native_features.py',ROOT/'src/KeplerSIMD.metalh']:
    if extra.exists():shutil.copyfile(extra,OUT/extra.name)
p=run(['xcrun','clang++','-O2','-std=c++17','-fobjc-arc','-framework','Foundation','-framework','Metal',str(source),'-o',str(probe)],'probe-build');assert p.returncode==0,p.stderr
COMMON='#include <metal_stdlib>\nusing namespace metal;\nstruct P {uint seed,n,local,groups,variant;};\n'
def shader(c):
    kind=c['kind'];op=c.get('op','');N=c.get('resources',4)
    if kind.startswith('argument'):
        mixed=kind in ['argument_mixed','argument_gpu_mixed'];gpu=kind.startswith('argument_gpu')
        decl=f'struct A {{array<device const uint*,{N}> input [[id(0)]];'
        if mixed:decl+=f'array<texture2d<float>,{N}> tex [[id({N})]];array<sampler,2> sam [[id({2*N})]];'
        decl+='};\n'
        producer=f'kernel void produce(constant A &src [[buffer(0)]], device A &dst [[buffer(1)]],constant P &p [[buffer(2)]],uint i [[thread_position_in_grid]]){{if(i<{N}){{dst.input[i]=src.input[(i+p.seed%{N})%{N}];'+(f'dst.tex[i]=src.tex[(i+p.seed%{N})%{N}];' if mixed else '')+'}}\n' if gpu else ''
        body=f'uint b=(i*13+p.seed)%{N};uint x=a.input[b][(i*7+p.seed)&63];uint y=b;'
        if mixed:body+=f'uint t=(i*5+p.seed)%{N};uint2 xy=uint2((i*3+p.seed)%16,(i*5+p.seed)%16);uint s=(i+p.seed)&1;y=uint(a.tex[t].sample(a.sam[s],(float2(xy)+0.5f)/8.0f).x);'
        return COMMON+decl+producer+'kernel void test(constant A &a [[buffer(0)]],device uint4 *out [[buffer(1)]],constant P &p [[buffer(2)]],uint i [[thread_position_in_grid]]){'+body+'out[i]=uint4(x,y,p.seed,i);}\n'
    if kind=='simd':
        if c.get('implementation')=='shuffle_lowering':
            helper=(OUT/'KeplerSIMD.metalh').read_text()
            body={'sum':'uint answer=kepler_simd::sum(value,lane,count);','sum_float':'uint answer=uint(kepler_simd::sum(float(value)*0.25f,lane,count)*4.0f);','min':'uint answer=kepler_simd::minimum(value,lane,count);','max':'uint answer=kepler_simd::maximum(value,lane,count);','prefix':'uint answer=kepler_simd::prefix_exclusive_sum(value,lane);','ballot':'uint answer=kepler_simd::sum((tid&1)?(1u<<lane):0u,lane,count);','all':'uint answer=kepler_simd::minimum(uint(value>50),lane,count);','any':'uint answer=kepler_simd::maximum(uint(value>50),lane,count);','sum_divergent':'uint combined=kepler_simd::sum((tid&1)?value:0u,lane,count);uint answer=(tid&1)?combined:0xdead0000u;'}[op]
            return COMMON+helper+'kernel void test(constant P &p [[buffer(0)]],device uint4 *out [[buffer(1)]],uint i [[thread_position_in_grid]],uint tid [[thread_index_in_threadgroup]],uint lane [[thread_index_in_simdgroup]],uint width [[threads_per_simdgroup]]){uint value=(i*17)%97+(p.seed%97)+1;uint count=min(width,p.local-(tid/width)*width);'+body+'out[i]=uint4(answer,lane,width,i);}\n'
        body={'control':'uint answer=value;','sum':'uint answer=simd_sum(value);','sum_float':'uint answer=uint(simd_sum(float(value)*0.25f)*4.0f);','min':'uint answer=simd_min(value);','max':'uint answer=simd_max(value);','prefix':'uint answer=simd_prefix_exclusive_sum(value);','shuffle':'uint answer=simd_shuffle(value,0);','xor':'uint answer=simd_shuffle_xor(value,1);','ballot':'uint answer=uint(ulong(simd_ballot((tid&1)!=0)));','all':'uint answer=uint(simd_all(value>50));','any':'uint answer=uint(simd_any(value>50));','sum_divergent':'uint answer=0xdead0000u;if(tid&1)answer=simd_sum(value);'}[op]
        return COMMON+'kernel void test(constant P &p [[buffer(0)]],device uint4 *out [[buffer(1)]],uint i [[thread_position_in_grid]],uint tid [[thread_index_in_threadgroup]],uint lane [[thread_index_in_simdgroup]],uint width [[threads_per_simdgroup]]){uint value=(i*17)%97+(p.seed%97)+1;'+body+'out[i]=uint4(answer,lane,width,i);}\n'
    shared=c['address_space']=='threadgroup';contended=c['contended'];index='0' if contended else 'tid';space='threadgroup' if shared else 'device'
    init=f'threadgroup atomic_uint shared[1024];{space} atomic_uint *a=&shared[{index}];if(tid==0)' if shared and contended else (f'threadgroup atomic_uint shared[1024];{space} atomic_uint *a=&shared[tid];' if shared else f'device atomic_uint *a=&global[{"group*p.local" if contended else "i"}];')
    if shared:init+='atomic_store_explicit(a,initial,memory_order_relaxed);threadgroup_barrier(mem_flags::mem_threadgroup);'
    if op=='weak':body='uint compare=initial^(p.variant?1u:0u);bool success=false;for(uint attempt=0;attempt<128;attempt++){success=atomic_compare_exchange_weak_explicit(a,&compare,replacement,memory_order_relaxed,memory_order_relaxed);if(success||compare!=(initial^(p.variant?1u:0u)))break;}uint previous=compare;'
    elif op=='add':body='uint previous=atomic_fetch_add_explicit(a,1u,memory_order_relaxed);bool success=true;'
    else:body=f'uint previous=initial;bool success=!p.variant;if({"tid==0" if contended else "true"}){{if(success)atomic_store_explicit(a,replacement,memory_order_relaxed);}}'
    flag='mem_threadgroup' if shared else 'mem_device'
    return COMMON+'kernel void test(constant P &p [[buffer(0)]],device uint4 *out [[buffer(1)]],device atomic_uint *global [[buffer(3)]],uint i [[thread_position_in_grid]],uint tid [[thread_index_in_threadgroup]],uint group [[threadgroup_position_in_grid]]){uint initial=p.seed+group*0x10001u;uint replacement=p.seed^0x55667788u;'+init+body+f'threadgroup_barrier(mem_flags::{flag});uint final=atomic_load_explicit(a,memory_order_relaxed);out[i]=uint4(previous,uint(success),final,i);'+'}\n'
cases=[]
def add(kind,op='',**kw):cases.append({'kind':kind,'op':op,'local':64,'groups':3,'storage':'private','variant':0,**kw})
for n in [4,32]:
    for kind in (['argument_buffers','argument_gpu','argument_mixed','argument_gpu_mixed'] if args.selection=='extended' else ['argument_buffers','argument_gpu','argument_mixed']):add(kind,resources=n)
for op in ['control','sum','sum_float','min','max','prefix','shuffle','xor','ballot','all','any','sum_divergent']:
    working=op in ['control','shuffle','xor']
    for local in ([32,33,128] if args.selection=='extended' and working and op!='xor' else [32,128] if args.selection=='extended' and op=='xor' else [32]):add('simd',op,local=local,implementation='native')
    if args.selection=='extended' and not working:
        add('simd',op,local=32,implementation='native',runtime_language=0x20002)
        for local in [1,31,32,33,63,128]:add('simd',op,local=local,implementation='shuffle_lowering')
for space in ['device','threadgroup']:
    for op in ['load_store','add','weak']:add('cas',op,address_space=space,contended=False,local=1,groups=1)
    add('cas','weak',address_space=space,contended=False,local=1,groups=1,variant=1)
    if args.selection=='extended':
        for storage in ['private','managed','shared']:
            for op in ['add','weak']:
                for variant in ([0,1] if op=='weak' else [0]):add('cas',op,address_space=space,contended=True,local=32,groups=3,storage=storage,variant=variant)
        for language in [0x10002,0x20000,0x20002]:
            for variant in [0,1]:add('cas','weak',address_space=space,contended=False,local=1,groups=1,variant=variant,runtime_language=language)
if args.only!='all':cases=[c for c in cases if (c['kind'].startswith('argument') if args.only=='arguments' else c['kind']==args.only)]
cache={};halt=False
for number,c in enumerate(cases):
    label=f"{number:03d}-{c['kind']}-{c['op'] or 'resources'}-{c.get('resources',c.get('address_space',''))}-l{c['local']}-v{c['variant']}-{c['storage']}";src=shader(c);key=hashlib.sha256(src.encode()).hexdigest()
    if key not in cache:
        name='shader-'+key[:12];sp=OUT/(name+'.metal');air=OUT/(name+'.air');library=OUT/(name+'.metallib');sp.write_text(src)
        p=run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-fno-fast-math','-c',str(sp),'-o',str(air)],name+'-compile')
        if p.returncode==0:p=run(['xcrun','-sdk','macosx','metallib',str(air),'-o',str(library)],name+'-metallib')
        cache[key]={'library':str(library),'source':str(sp),'compile_exit_code':p.returncode}
    compilation=cache[key];record={'label':label,**c,'source':compilation['source'],'source_sha256':key,'library':compilation['library'],'compile_exit_code':compilation['compile_exit_code']}
    if record['compile_exit_code']:
        record['failure_stage']='offline_compile';records.append(record);print(label,'offline compile failed',flush=True);continue
    c['library']=compilation['library'];c['source']=compilation['source'];plan=OUT/(label+'.plan.json');plan.write_text(json.dumps(c,indent=2)+'\n');execution=OUT/(label+'-execution');execution_results=OUT/(label+'-outputs');execution_results.mkdir()
    p=run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(probe),'--out',str(execution),'--timeout','25','--',str(plan),str(execution_results)],label+'-launch',timeout=45)
    record.update(execution_dir=str(execution),exit_code=p.returncode)
    m=json.loads((execution/'manifest.json').read_text());record['process_manifest']=m
    try:record['result']=json.loads((execution/'execution.stdout').read_text())
    except ValueError:record['failure_stage']='missing_json';record['stderr']=(execution/'execution.stderr').read_text()
    records.append(record);(OUT/'results.json').write_text(json.dumps(records,indent=2)+'\n');result=record.get('result',{});print(label,p.returncode,result.get('failure_stage','PASS'),flush=True)
    if m['authoritative_ps_status']:halt=True;print('HALT: signed child still present',flush=True);break
final={str(p):sha(p) for p in system_files};assert final==system_hashes
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_sha256':before,'system_hashes_before':system_hashes,'system_hashes_after':final,'system_unchanged':True,'probe_sha256':sha(probe),'probe_source_sha256':sha(OUT/source.name),'signed_launcher_sha256':sha(ROOT/'tools/run_signed_probe.py'),'selection':args.selection,'only':args.only,'cases_attempted':len(records),'halted_live_process':halt,'native_only':True,'performance_benchmark':False,'scope':'Function-level numerical qualification; fresh signed processes, no NAK, no driver installation, no global Metal-family qualification'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('DONE',len(records),'cases',flush=True)
