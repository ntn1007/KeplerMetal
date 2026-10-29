#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a request-window witness on the pinned integrated repeat client."""
import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def command(label,argv,out):
    argv=list(map(str,argv));r=subprocess.run(argv,capture_output=True,timeout=90)
    (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
    need(r.returncode==0,label+' failed; inspect retained stderr')
    return {'label':label,'argv':argv,'returncode':r.returncode}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('lab','integrated','calibration','reserved-control','out'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();lab,integrated,cal,ctrl,out=(getattr(a,n).resolve() for n in ('lab','integrated','calibration','reserved_control','out'))
    for path in (integrated,cal,ctrl,out):path.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    base=integrated/'base';old=integrated/'build';b=json.loads((old/'build.json').read_text());c=json.loads((cal/'calibration.json').read_text());r=json.loads((ctrl/'manifest.json').read_text())
    need(b['repeat_integrated'] and b['base_inputs_sha256']==sha(base/'inputs.json') and
         c['status']=='PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION' and c['request_windows_1_2_3_calibrated'] and c['active_arm_calibrated'] and c['free_candidate_match_and_mismatch_calibrated'] and
         r['status']=='PASS_RESERVED_DEBUGGER_CPU' and r['calibration_sha256']==sha(cal/'calibration.json') and
         r['reservation']['state']=='terminal' and r['debugger_and_target_absent_from_process_table'] and
         r['log_sha256']==sha(ctrl/'lldb.log') and r['guard_sha256']==sha(HERE/'lldb_guard.py'),'prerequisite differs')
    for n,h in b['frozen'].items():need(sha(old/n)==h,'old build changed')
    for n,h in b['sources_sha256'].items():need(sha(old/n)==h,'observer source changed')
    for n,h in c['source_sha256'].items():need(sha(HERE/n)==sha(cal/n)==h,'calibration source changed')
    source=old/'registry-repeated.mm';need(sha(source)==b['variant_source_sha256'],'client source changed')
    s=source.read_text();s='#include <cstdint>\nextern "C" { __attribute__((used)) volatile uint32_t kp_request_index = 0; }\n'+s
    pairs=[('    fprintf(stderr,"KP_REPEAT_BEGIN request=1\\n");', '    kp_request_index=1;\n    fprintf(stderr,"KP_REPEAT_BEGIN request=1\\n");'),
           ('    fprintf(stderr,"KP_REPEAT_END request=1\\n");', '    kp_request_index=0;\n    fprintf(stderr,"KP_REPEAT_END request=1\\n");'),
           ('        fprintf(stderr,"KP_REPEAT_BEGIN request=%u\\n",n);', '        kp_request_index=n;\n        fprintf(stderr,"KP_REPEAT_BEGIN request=%u\\n",n);'),
           ('        fprintf(stderr,"KP_REPEAT_END request=%u\\n",n);', '        kp_request_index=0;\n        fprintf(stderr,"KP_REPEAT_END request=%u\\n",n);')]
    for old_text,new_text in pairs:
        need(s.count(old_text)==1,'marker site differs');s=s.replace(old_text,new_text)
    out.mkdir();(out/'registry-request.mm').write_text(s);shutil.copyfile(old/'video_registry_observer.h',out/'video_registry_observer.h')
    cmds=json.loads((integrated/'commands.json').read_text());compile_argv=next(x['argv'] for x in cmds if x['label']=='compile-host');link_argv=next(x['argv'] for x in cmds if x['label']=='link')
    oldsource=str(source);oldobj=str(old/'registry-repeated.o');newobj=str(out/'registry-request.o');host=out/'application'
    need(compile_argv.count(oldsource)==1 and compile_argv[-2:]==['-o',oldobj] and link_argv.count(oldobj)==1 and link_argv[-2:]==['-o',str(old/'application')],'build plan differs')
    records=[];records.append(command('compile',[str(out/'registry-request.mm') if x==oldsource else x for x in compile_argv[:-2]]+['-o',newobj],out))
    records.append(command('link',[newobj if x==oldobj else x for x in link_argv[:-2]]+['-o',host],out))
    for n in ('marker.S','gva_marker.cpp','lldb_witness.py','lldb_guard.py'):shutil.copyfile(HERE/n,out/n)
    marker=out/'marker.dylib';records.append(command('marker',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-Wall','-Wextra','-Werror','-dynamiclib',out/'gva_marker.cpp',out/'marker.S','-o',marker],out))
    ent=out/'entitlements.plist';ent.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow':True}))
    records.append(command('sign-host',['codesign','--force','--sign','-','--entitlements',ent,host],out));records.append(command('sign-marker',['codesign','--force','--sign','-',marker],out))
    for label,item in [('host',host),('marker',marker),('observer',base/'libObserver.dylib')]:records.append(command('verify-'+label,['codesign','--verify','--strict',item],out))
    sym=subprocess.run(['nm','-g',str(host)],capture_output=True,text=True,check=True).stdout
    need(len([x for x in sym.splitlines() if x.endswith(' _kp_request_index')])==1,'marker symbol differs')
    names=('application','marker.dylib','entitlements.plist','marker.S','gva_marker.cpp','lldb_witness.py','lldb_guard.py')
    result={**b,'status':'PREPARED_ONLY','frozen':{n:sha(out/n) for n in names},'request_window_variant':True,
            'parent_build_sha256':sha(old/'build.json'),'calibration_sha256':sha(cal/'calibration.json'),
            'reserved_control_sha256':sha(ctrl/'manifest.json'),'request_source_sha256':sha(out/'registry-request.mm'),
            'builder_sha256':sha(Path(__file__)),'GPU_execution':False,'system_modified':False}
    (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n');(out/'build.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED_REQUEST_WITNESS','GPU_execution':False}))


if __name__=='__main__':main()
