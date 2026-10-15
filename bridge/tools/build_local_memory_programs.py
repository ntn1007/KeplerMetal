#!/usr/bin/env python3
"""Build direct NIR kernels with pinned existing Mesa archives; offline only."""
from pathlib import Path
import argparse,hashlib,json,os,shlex,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
for source in ['tools/local_memory_compile.c','src/KeplerResourceABI.h']:shutil.copyfile(ROOT/source,out/Path(source).name)
build=ROOT/'build/mesa';entry=next(x for x in json.loads((build/'compile_commands.json').read_text())if x['file'].endswith('/nak_nir.c'));flags=[x for x in shlex.split(entry['command'])[1:]if x.startswith(('-I','-D','-std','-f','-W'))and not x.startswith('-Werror')]
archives=['src/nouveau/compiler/libnak.a','src/nouveau/compiler/libnak_rs.a','src/compiler/nir/libnir.a','src/compiler/libcompiler.a','src/nouveau/headers/libnvidia_headers_c.a','src/util/libmesa_util.a','src/util/libmesa_util_simd.a','src/util/blake3/libblake3.a','src/c11/impl/libmesa_util_c11.a','src/compiler/rust/libcompiler_c_helpers.a','src/compiler/rust/libcompiler_bindings.a'];commands=[]
def run(label,argv,env=None):
 argv=list(map(str,argv));child=os.environ.copy();child.update(env or {});r=subprocess.run(argv,cwd=build,env=child,capture_output=True,text=True,timeout=60);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'environment':env or {},'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 if r.returncode:print(r.stderr[-2500:]);raise SystemExit(r.returncode)
 print(label,'PASS',flush=True);return r.stdout
run('compile',['clang','-O1',*flags,'-I',out,'-c',out/'local_memory_compile.c','-o',out/'compiler.o'])
run('link',['clang','-o',out/'compiler',out/'compiler.o',*archives,'-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'])
rows=[]
for semantic,forced in [(x,False)for x in ['local_control','local32','local256','local1024','pressure32','pressure64','pressure96']]+[('pressure32',True)]:
 name=semantic+('_forced_spill'if forced else'');info=json.loads(run(name,[out/'compiler',semantic,out/(name+'.sass'),out/(name+'.asm')],{'NAK_DEBUG':'spill'}if forced else{}));(out/(name+'.json')).write_text(json.dumps(info,indent=2)+'\n');run(name+'-decode',[ROOT/'build/envydis-only/envydis/envydis','-m','gf100','-V','gk104','-i','-n',out/(name+'.sass')]);listing=(out/(name+'-decode.stdout')).read_text();assert '[unknown'not in listing
 rows.append({'name':name,'semantic':semantic,'forced_spill':forced,'info':info,'code_SHA256':sha(out/(name+'.sass'))});print(name,info,flush=True)
(out/'manifest.json').write_text(json.dumps({'status':'PASS','source_SHA256':{p.name:sha(p)for p in [out/'local_memory_compile.c',out/'KeplerResourceABI.h']},'archives_SHA256':{n:sha(build/n)for n in archives},'programs':rows,'GPU_execution':False,'builder_SHA256':sha(__file__)},indent=2)+'\n')
