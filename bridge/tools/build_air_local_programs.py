#!/usr/bin/env python3
"""Freeze and build MSL/AIR -> NIR -> SM30 local-memory kernels, offline only."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT/'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5'
ARCHIVES = ['src/nouveau/compiler/libnak.a', 'src/nouveau/compiler/libnak_rs.a',
    'src/compiler/nir/libnir.a', 'src/compiler/libcompiler.a',
    'src/nouveau/headers/libnvidia_headers_c.a', 'src/util/libmesa_util.a',
    'src/util/libmesa_util_simd.a', 'src/util/blake3/libblake3.a',
    'src/c11/impl/libmesa_util_c11.a', 'src/compiler/rust/libcompiler_c_helpers.a',
    'src/compiler/rust/libcompiler_bindings.a']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--entries', nargs='+', default=['local_control','local32','local256',
                                                   'local1024','pressure32','pressure64','pressure96'])
    args = p.parse_args()
    allowed = {'local_control','local32','local256','local1024','pressure32','pressure64','pressure96'}
    if not set(args.entries) <= allowed or len(args.entries) != len(set(args.entries)):
        p.error('Unknown or duplicate qualified entry')
    out = args.out.resolve(); out.relative_to(ROOT/'results'); out.mkdir(exist_ok=False)
    air = out/'source-fork/drivers/NVMTLDriver/air'; air.mkdir(parents=True)
    front = out/'source-fork/tools/nakc'; front.mkdir(parents=True)
    for f in (UPSTREAM/'drivers/NVMTLDriver/air').iterdir():
        if f.suffix in {'.c','.h'}: shutil.copyfile(f,air/f.name)
    for n in ['air_nir.c','air_nir.h']: shutil.copyfile(UPSTREAM/'tools/nakc'/n, front/n)
    for n in ['tools/air_local_compile.c','src/KeplerLocalAIRLowering.inc',
              'src/KeplerResourceABI.h','src/kepler_local_memory.metal',
              'src/opennvda-air-cas-result.patch']:
        shutil.copyfile(ROOT/n,out/Path(n).name)
    commands = []
    def run(label, argv, cwd=ROOT, nak_debug=None):
        argv = list(map(str,argv)); env = os.environ.copy(); env.pop('NAK_DEBUG',None)
        if nak_debug is not None: env['NAK_DEBUG'] = nak_debug
        start = time.monotonic()
        r = subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True,timeout=60)
        (out/(label+'.stdout')).write_text(r.stdout); (out/(label+'.stderr')).write_text(r.stderr)
        commands.append({'label':label,'argv':argv,'cwd':str(cwd),'exit_code':r.returncode,
                         'monotonic_seconds':time.monotonic()-start,'NAK_DEBUG':nak_debug or 'unset'})
        (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        print(label,r.returncode,flush=True)
        if r.returncode: raise SystemExit(r.stderr[-3000:] or r.returncode)
        return r.stdout
    original_sha = sha(UPSTREAM/'tools/nakc/air_nir.c')
    run('apply-CAS-source-fix',['patch','--batch','-p1','-i',out/'opennvda-air-cas-result.patch'],out/'source-fork')
    text = (front/'air_nir.c').read_text()
    assert text.count('nir_block *nb = nir_block_create(c->s);') == 1
    (front/'air_nir.c').write_text(text.replace('nir_block *nb = nir_block_create(c->s);',
                                              'nir_block *nb = nir_block_create(c->impl);'))
    assert sha(UPSTREAM/'tools/nakc/air_nir.c') == original_sha
    build = ROOT/'build/mesa'
    entry = next(e for e in json.loads((build/'compile_commands.json').read_text())
                 if e['file'].endswith('/nak_nir.c'))
    flags = [a for a in shlex.split(entry['command'])[1:]
             if a.startswith(('-I','-D','-std','-f','-W')) and not a.startswith('-Werror')]
    flags = ['-I'+str(out),'-I'+str(front),'-I'+str(air),*flags,'-Werror=implicit-function-declaration']
    objects = []
    for label,source in [('harness',out/'air_local_compile.c'),('air_nir',front/'air_nir.c'),
                         *[(n,air/(n+'.c')) for n in ['bitstream','airir','metallib']]]:
        obj = out/(label+'.o'); objects.append(obj)
        run('compile-'+label,['clang','-O1',*flags,'-c',source,'-o',obj],build)
    compiler = out/'compiler'
    run('link',['clang','-o',compiler,*objects,*[build/n for n in ARCHIVES],
                '-lz','-lpthread','-lc++','-framework','CoreFoundation','-framework','Security'])
    run('sign-offline-compiler',['codesign','--force','--sign','-',compiler])
    run('metal',['xcrun','metal','-std=macos-metal2.3','-c',out/'kepler_local_memory.metal','-o',out/'local_memory.air'])
    run('metallib',['xcrun','metallib',out/'local_memory.air','-o',out/'local_memory.metallib'])
    rows = []
    decoder = ROOT/'build/envydis-only/envydis/envydis'
    programs = [(n,n,None) for n in args.entries]
    if 'pressure32' in args.entries: programs.append(('pressure32_forced_spill','pressure32','spill'))
    for name,semantic,debug in programs:
        case = out/name; case.mkdir()
        info = json.loads(run('translate-'+name,[compiler,out/'local_memory.air',case,semantic,32,2],nak_debug=debug))
        assert info['source_language']=='MSL/AIR' and info['sm']==30 and info['registers']<=63
        assert info['buffer_slots']==3 and info['push_bytes']==48 and info['grid_offset']==24
        assert not info['crs_bytes'] and not info['shared_bytes']
        shutil.copyfile(case/'program.sass',out/(name+'.sass'))
        shutil.copyfile(case/'program.asm',out/(name+'.asm'))
        (out/(name+'.json')).write_text(json.dumps(info,indent=2)+'\n')
        listing = run('decode-'+name,[decoder,'-m','gf100','-V','gk104','-i','-n',out/(name+'.sass')])
        assert '[unknown' not in listing
        rows.append({'name':name,'semantic':semantic,'forced_spill':debug=='spill','info':info,
                     'code_SHA256':sha(out/(name+'.sass'))})
        print(name,json.dumps(info),flush=True)
    sources = [f for f in out.rglob('*') if f.suffix in {'.c','.h','.inc','.metal','.patch'}]
    manifest = {'status':'PASS','GPU_execution':False,'programs':rows,
                'source_SHA256':{str(f.relative_to(out)):sha(f) for f in sources},
                'archives_SHA256':{n:sha(build/n) for n in ARCHIVES},
                'compiler_SHA256':sha(compiler),'builder_SHA256':sha(__file__),
                'upstream_air_nir_SHA256':original_sha,'MSL_SHA256':sha(out/'kepler_local_memory.metal'),
                'AIR_SHA256':sha(out/'local_memory.air'),'decoder_SHA256':sha(decoder),
                'native_resource_profile':'buffers0/1,constant2:16bytes,origin0,1D/fullgroups',
                'full_objective_complete':False}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'status':'PASS','programs':len(rows),'GPU_execution':False}))

if __name__=='__main__': main()
