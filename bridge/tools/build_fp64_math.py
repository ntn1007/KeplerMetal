#!/usr/bin/env python3
"""Offline-only build/disassembly; no import, Metal context or GPU dispatch."""
from pathlib import Path
import argparse,hashlib,json,shlex,subprocess
ROOT=Path(__file__).resolve().parents[1]
BASE_OPS=['add','mul','fma','div','sqrt','from_i64','from_u64','from_f32']
REVERSE_OPS=[f'to_{target}_{mode}' for target in ['f32','i64','u64'] for mode in ['rn','rz','rp','rm']]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--strided-inputs',action='store_true');p.add_argument('--operations',nargs='+',choices=BASE_OPS+REVERSE_OPS,default=['add','mul','fma','div','sqrt']);a=p.parse_args();assert len(set(a.operations))==len(a.operations);out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label,cwd=ROOT):
 r=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'cwd':str(cwd),'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);return r
source=out/'fp64_math_compile.c';source.write_bytes((ROOT/'tools/fp64_math_compile.c').read_bytes());build=ROOT/'build/mesa';entries=json.loads((build/'compile_commands.json').read_text());e=next(e for e in entries if e['file'].endswith('/nak_nir.c'));flags=[f for f in shlex.split(e['command'])[1:] if f.startswith(('-I','-D','-std','-f','-W')) and not f.startswith('-Werror')]
obj=out/'compiler.o';r=run(['clang','-O1',*flags,'-c',str(source),'-o',str(obj)],'compile',build);assert r.returncode==0,r.stderr[-2000:]
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a']
exe=out/'fp64_math_compile';r=run(['clang','-o',str(exe),str(obj),*archives,'-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'],'link',build);assert r.returncode==0,r.stderr[-2000:]
records=[]
for op in a.operations:
 for local in [32,128,1024]:
  label=f'{op}-l{local}';code=out/(label+'.sass');asm=out/(label+'.asm');r=run([str(exe),op,str(code),str(asm),str(local)]+(['strided'] if a.strided_inputs else []),label+'-generate')
  record={'operation':op,'local':local,'compiled':r.returncode==0,'exit_code':r.returncode}
  if r.returncode==0:
   info=json.loads(r.stdout);assert info['sm']==30 and not info['scratch_bytes'] and not info['crs_bytes'] and not info['shared_bytes'];assert code.stat().st_size==info['code_bytes'] and code.stat().st_size%64==0
   (out/(label+'.info.json')).write_text(json.dumps(info,indent=2)+'\n')
   d=run([str(ROOT/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(code)],label+'-decode');assert d.returncode==0 and '[unknown' not in d.stdout
   record.update(info=info,code_SHA256=sha(code),assembly_SHA256=sha(asm),known_decode=True)
  records.append(record)
data={'records':records,'operations':a.operations,'GPU_execution':False,'compiler_source_SHA256':sha(source),'compiler_executable_SHA256':sha(exe),'Mesa_archives_SHA256':{n:sha(build/n) for n in archives},'Mesa_version':'26.2.4','Mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2'}
(out/'summary.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({'offline':True,'compiled':sum(r['compiled'] for r in records),'attempted':len(records)}))
