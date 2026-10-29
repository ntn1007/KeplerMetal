#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build own-process client with explicitly armed calibrated heap observer."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def cmd(label,argv,out):
    argv=list(map(str,argv));r=subprocess.run(argv,capture_output=True,timeout=90)
    (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
    need(r.returncode==0,label+' failed; inspect retained stderr')
    return {'label':label,'argv':argv,'returncode':r.returncode}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('lab','parent','heap-calibration','out'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();lab,parent,cal,out=(getattr(a,n).resolve() for n in ('lab','parent','heap_calibration','out'))
    for x in (parent,cal,out):x.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    b=json.loads((parent/'build.json').read_text());c=json.loads((cal/'calibration.json').read_text())
    need(b['request_window_variant'] and c['status']=='PASS_LLDB_WATCHED_TARGET_CPU_CALIBRATION' and
         c['match_and_nonmatch_order_tested'] and sha(cal/'heap-watch.dylib')==c['observer_sha256'], 'prerequisites differ')
    for n,h in b['frozen'].items():need(sha(parent/n)==h,'parent differs')
    for n,h in c['sources_sha256'].items():
        source=(HERE.parent/'video_gva_repeat_sessions'/n) if n=='repeat_gate.h' else HERE/n
        need(sha(cal/n)==sha(source)==h,'calibration source differs: '+n)
    source=parent/'registry-request.mm';need(sha(source)==b['request_source_sha256'],'request host source differs')
    text=source.read_text();old='int main(int argc,char **argv){@autoreleasepool{'
    new='''int main(int argc,char **argv){@autoreleasepool{
    using HeapArm=bool(*)(void*);using HeapDisarm=bool(*)();
    struct HeapScope { HeapDisarm close=nullptr; ~HeapScope(){if(close && !close())fprintf(stderr,"KP_HEAP_DISARM_FAILED\\n");} } heapScope;
    const char *heapMode=getenv("KP_HEAP_TRACK");
    if(heapMode && !strcmp(heapMode,"1")) {
        auto arm=reinterpret_cast<HeapArm>(dlsym(RTLD_DEFAULT,"KPHeapWatchArm"));
        heapScope.close=reinterpret_cast<HeapDisarm>(dlsym(RTLD_DEFAULT,"KPHeapWatchDisarm"));
        if(!arm||!heapScope.close||!arm(reinterpret_cast<void*>(1))){heapScope.close=nullptr;return 90;}
        fprintf(stderr,"KP_HEAP_ARMED\\n");fflush(stderr);
    }'''
    need(text.count(old)==1,'main marker differs');text=text.replace(old,new)
    commands=json.loads((parent/'commands.json').read_text());compile_argv=next(x['argv'] for x in commands if x['label']=='compile');link=next(x['argv'] for x in commands if x['label']=='link')
    oldobj=str(parent/'registry-request.o');oldsrc=str(source);need(compile_argv.count(oldsrc)==1 and compile_argv[-2:]==['-o',oldobj] and link.count(oldobj)==1 and link[-2:]==['-o',str(parent/'application')],'build plan differs')
    out.mkdir();src=out/'registry-track.mm';src.write_text(text);shutil.copyfile(parent/'video_registry_observer.h',out/'video_registry_observer.h')
    obj=out/'registry-track.o';host=out/'application';records=[]
    records.append(cmd('compile',[str(src) if x==oldsrc else x for x in compile_argv[:-2]]+['-o',obj],out))
    records.append(cmd('link',[str(obj) if x==oldobj else x for x in link[:-2]]+['-o',host],out))
    for n in ('entitlements.plist','marker.S','gva_marker.cpp','lldb_witness.py','lldb_guard.py','marker.dylib'):shutil.copyfile(parent/n,out/n)
    shutil.copyfile(cal/'heap-watch.dylib',out/'heap-watch.dylib');shutil.copyfile(HERE/'lldb_target.py',out/'lldb_target.py');shutil.copyfile(HERE/'lldb_tracking.py',out/'lldb_tracking.py');shutil.copyfile(HERE.parent/'video_gva_heap_binding/lldb_binding.py',out/'lldb_binding.py')
    records.append(cmd('sign-host',['codesign','--force','--sign','-','--entitlements',out/'entitlements.plist',host],out))
    for label,path in [('host',host),('marker',out/'marker.dylib'),('heap',out/'heap-watch.dylib')]:records.append(cmd('verify-'+label,['codesign','--verify','--strict',path],out))
    names=('application','entitlements.plist','marker.S','gva_marker.cpp','lldb_witness.py','lldb_guard.py','marker.dylib','heap-watch.dylib','lldb_target.py','lldb_tracking.py','lldb_binding.py')
    result={**b,'frozen':{n:sha(out/n) for n in names},'heap_tracking_variant':True,'heap_calibration_sha256':sha(cal/'calibration.json'),
            'heap_observer_sha256':c['observer_sha256'],'parent_build_sha256':sha(parent/'build.json'),
            'tracking_host_source_sha256':sha(src),'builder_sha256':sha(Path(__file__)),'GPU_execution':False,'system_modified':False}
    (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n');(out/'build.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED_EXPLICIT_HEAP_TRACKER','GPU_execution':False}))


if __name__=='__main__':main()
