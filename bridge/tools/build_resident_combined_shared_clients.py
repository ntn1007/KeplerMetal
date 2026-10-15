#!/usr/bin/env python3
"""Build adapted clients against an extracted public SDK, without core sources."""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    archive=a.archive.resolve();archive.relative_to(ROOT/'results')
    with tarfile.open(archive)as t:
        for e in t.getmembers():assert e.isfile() and not e.name.startswith('/') and '..'not in Path(e.name).parts
        t.extractall(out)
    sdk=out/'KeplerMetalSDK';manifest=json.loads((sdk/'FILE_MANIFEST.json').read_text())
    for e in manifest['files']:assert sha(sdk/e['path'])==e['SHA256']
    (sdk/'src').rename(out/'audit-source-not-in-client-SDK')
    library_sha=sha(sdk/'lib/libKeplerMetal.a')
    jobs=[('dynamic_bounds','build_cpu_icb_dynamic_bounds_client.py'),
          ('dynamic','build_cpu_icb_dynamic_copy_client.py'),
          ('combined_bounds','build_cpu_icb_combined_shared_bounds_client.py'),
          ('registered','build_cpu_icb_registered_copy_client.py'),('registered_bounds','build_cpu_icb_registered_bounds_client.py'),
          ('async','build_cpu_icb_copy_async_client.py'),('mixed','build_cpu_icb_copy_mixed_client.py'),
          ('refusal','build_cpu_icb_copy_refusal_client.py'),('graph','build_cpu_icb_copy_graph_client.py'),
          ('baseline','build_cpu_icb_gpu_copy_client.py'),('reverse','build_fp64_reverse_client.py'),
          ('arithmetic','build_fp64_client.py'),('cas','build_example.py'),('literal','build_literal_client.py')]

    def build(job):
        name,script=job;argv=['python3',str(sdk/'examples'/script),'--out',str(out/(name+'-application'))]
        r=subprocess.run(argv,capture_output=True,text=True)
        (out/(name+'-build.stdout')).write_text(r.stdout);(out/(name+'-build.stderr')).write_text(r.stderr)
        assert r.returncode==0,(name,r.stderr[-2500:])
        inp=json.loads((out/(name+'-application')/'inputs.json').read_text())
        assert inp.get('static_library_SHA256',inp.get('library_SHA256'))==library_sha
        return {'name':name,'argv':argv,'exit_code':r.returncode,'static_library_SHA256':library_sha}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
        results=list(pool.map(build,jobs))
    for name in ['manifest','grid3d']:
        dest=out/(name+'-application');dest.mkdir();(dest/'runtime').mkdir()
        prefix='cpu_icb_'+name;source=ROOT/'tools'/(prefix+'_probe.mm')
        for f in [source,sdk/'include/KeplerCPUICB.h',ROOT/'src'/(prefix+'.metal'),ROOT/'src'/(prefix+'.json')]:shutil.copyfile(f,dest/f.name)
        old=ROOT/'results'/('cpu-icb-'+name+'-gpu-qualified')
        for n in [prefix+'.metallib']+(['foreign.metallib']if name=='manifest'else[]):shutil.copyfile(old/n,dest/n)
        for n in ['run_sdk_host.py','lab_gpu_reservation.py']:shutil.copyfile(sdk/'runtime'/n,dest/'runtime'/n)
        exe=dest/(prefix+'_probe');argv=['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(sdk/'include'),str(dest/source.name),'-L',str(sdk/'lib'),'-lKeplerMetal','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',str(exe)]
        r=subprocess.run(argv,capture_output=True,text=True);(dest/'build.stdout').write_text(r.stdout);(dest/'build.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr[-2500:]
        commands=[{'label':'build','argv':argv,'exit_code':r.returncode}];(dest/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        inp={'source_hashes':{n:sha(dest/n)for n in [source.name,'KeplerCPUICB.h',prefix+'.metal',prefix+'.json']},
             'library_SHA256':sha(dest/(prefix+'.metallib')),'manifest_SHA256':sha(dest/(prefix+'.json')),
             'executable_SHA256':sha(exe),'static_library_SHA256':library_sha,'core_source_compilations':0,
             'Git_commit':None,'Qwen_job_ids':[],'system_modified':False}
        if name=='manifest':inp['foreign_library_SHA256']=sha(dest/'foreign.metallib')
        (dest/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n')
        results.append({'name':name,'argv':argv,'exit_code':r.returncode,'static_library_SHA256':library_sha})
    (out/'client-builds.json').write_text(json.dumps({'status':'PASS','SDK_archive_SHA256':sha(archive),'static_library_SHA256':library_sha,'core_source_compilations':0,'builds':results},indent=2)+'\n')
    print(json.dumps({'status':'PASS','clients':len(results),'core_source_compilations':0,'static_library_SHA256':library_sha}))


if __name__=='__main__':main()
